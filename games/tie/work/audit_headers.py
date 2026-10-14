#!/usr/bin/env python3
"""Independent MZ + LE/LX header audit for the TIE Fighter executables.

Usage:  python work/audit_headers.py <exe> [<exe> ...]

Reads nothing from the project docs; every number printed here comes from
struct.unpack_from on the raw file.
"""
import struct
import sys

MZ_FIELDS = [
    (0x00, "H", "e_magic"),
    (0x02, "H", "e_cblp"),
    (0x04, "H", "e_cp"),
    (0x06, "H", "e_crlc"),
    (0x08, "H", "e_cparhdr"),
    (0x0A, "H", "e_minalloc"),
    (0x0C, "H", "e_maxalloc"),
    (0x0E, "H", "e_ss"),
    (0x10, "H", "e_sp"),
    (0x12, "H", "e_csum"),
    (0x14, "H", "e_ip"),
    (0x16, "H", "e_cs"),
    (0x18, "H", "e_lfarlc"),
    (0x1A, "H", "e_ovno"),
]


def hexdump(b, base=0, width=16):
    out = []
    for i in range(0, len(b), width):
        chunk = b[i:i + width]
        hx = " ".join(f"{c:02X}" for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        out.append(f"{base + i:08X}  {hx:<{width * 3 - 1}}  |{asc}|")
    return "\n".join(out)


def parse_mz(data, path):
    print("=" * 78)
    print(f"FILE {path}   size = {len(data)} bytes (0x{len(data):X})")
    print("=" * 78)
    print("\n-- raw MZ header bytes, file offset 0x00..0x3F --")
    print(hexdump(data[:0x40], 0))

    mz = {}
    print("\n-- MZ fields (offset, name, value) --")
    for off, fmt, name in MZ_FIELDS:
        (v,) = struct.unpack_from("<" + fmt, data, off)
        mz[name] = v
        raw = " ".join(f"{c:02X}" for c in data[off:off + 2])
        extra = ""
        if name == "e_magic":
            extra = f"  ({data[0:2].decode('latin1')!r})"
        print(f"  0x{off:02X}  {name:<10} = 0x{v:04X} ({v:6d})   raw {raw}{extra}")

    hdr_size = mz["e_cparhdr"] * 16
    if mz["e_cblp"] == 0:
        img_size = mz["e_cp"] * 512
        img_formula = f"e_cp*512 = {mz['e_cp']}*512"
    else:
        img_size = (mz["e_cp"] - 1) * 512 + mz["e_cblp"]
        img_formula = f"(e_cp-1)*512 + e_cblp = ({mz['e_cp']}-1)*512 + {mz['e_cblp']}"
    print("\n-- derived --")
    print(f"  header size      = e_cparhdr*16 = {mz['e_cparhdr']}*16 = {hdr_size} (0x{hdr_size:X})")
    print(f"  DOS image size   = {img_formula} = {img_size} (0x{img_size:X})")
    print(f"  load-module size = image - header = {img_size - hdr_size} (0x{img_size - hdr_size:X})")
    print(f"  file size        = {len(data)} (0x{len(data):X})"
          f"   -> {'image < file (overlay/LE follows)' if img_size < len(data) else 'image covers whole file'}")

    ep_file = hdr_size + (mz["e_cs"] & 0xFFFF) * 16 + mz["e_ip"]
    if mz["e_cs"] >= 0x8000:  # negative segment
        ep_file = hdr_size + (struct.unpack_from("<h", data, 0x16)[0]) * 16 + mz["e_ip"]
    print(f"  MZ entry CS:IP   = {mz['e_cs']:04X}:{mz['e_ip']:04X}"
          f"  -> file offset 0x{ep_file:X} (= hdr {hdr_size:#x} + CS*16 + IP)")
    if 0 <= ep_file < len(data):
        print("  bytes at MZ entry:")
        print(hexdump(data[ep_file:ep_file + 32], ep_file))

    print(f"  MZ stack SS:SP   = {mz['e_ss']:04X}:{mz['e_sp']:04X}")
    print(f"  e_lfarlc         = 0x{mz['e_lfarlc']:X}  (reloc table file offset)")

    # e_lfanew only meaningful when the reloc table does not overlap 0x3C..0x3F
    lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    reloc_end = mz["e_lfarlc"] + 4 * mz["e_crlc"]
    lfanew_ok = mz["e_lfarlc"] >= 0x40 or reloc_end <= 0x3C
    print(f"  dword @0x3C      = 0x{lfanew:08X}  raw {' '.join(f'{c:02X}' for c in data[0x3C:0x40])}")
    print(f"    reloc table spans 0x{mz['e_lfarlc']:X}..0x{reloc_end:X}"
          f"  -> dword@0x3C is {'a real e_lfanew' if lfanew_ok else 'RELOC DATA, not e_lfanew'}")

    print(f"\n-- relocation table: e_crlc = {mz['e_crlc']} entries @ 0x{mz['e_lfarlc']:X}"
          f" (format: offset u16, segment u16) --")
    if mz["e_crlc"]:
        print(hexdump(data[mz["e_lfarlc"]:reloc_end], mz["e_lfarlc"]))
        bad = 0
        for i in range(mz["e_crlc"]):
            o = mz["e_lfarlc"] + 4 * i
            off, seg = struct.unpack_from("<HH", data, o)
            tgt = hdr_size + seg * 16 + off
            ok = hdr_size <= tgt < img_size
            if not ok:
                bad += 1
            if i < 24 or not ok:
                print(f"    [{i:3d}] @0x{o:04X}  {seg:04X}:{off:04X} -> file 0x{tgt:06X}"
                      f"  {'ok' if ok else 'OUT OF IMAGE'}")
        if mz["e_crlc"] > 24:
            print(f"    ... ({mz['e_crlc']} total)")
        print(f"    {mz['e_crlc'] - bad}/{mz['e_crlc']} targets inside the DOS image "
              f"[0x{hdr_size:X}, 0x{img_size:X})")
    else:
        print("    (none)")
    return mz, hdr_size, img_size, lfanew


LE_FIELDS = [
    (0x00, "2s", "signature"),
    (0x02, "B", "byte_order"),
    (0x03, "B", "word_order"),
    (0x04, "I", "format_level"),
    (0x08, "H", "cpu_type"),
    (0x0A, "H", "os_type"),
    (0x0C, "I", "module_version"),
    (0x10, "I", "module_flags"),
    (0x14, "I", "module_num_pages"),
    (0x18, "I", "eip_object"),
    (0x1C, "I", "eip"),
    (0x20, "I", "esp_object"),
    (0x24, "I", "esp"),
    (0x28, "I", "page_size"),
    (0x2C, "I", "last_page_size_or_page_shift"),
    (0x30, "I", "fixup_sect_size"),
    (0x34, "I", "fixup_sect_checksum"),
    (0x38, "I", "loader_sect_size"),
    (0x3C, "I", "loader_sect_checksum"),
    (0x40, "I", "object_table_off"),
    (0x44, "I", "num_objects"),
    (0x48, "I", "object_page_map_off"),
    (0x4C, "I", "object_iter_pages_off"),
    (0x50, "I", "resource_table_off"),
    (0x54, "I", "num_resource_entries"),
    (0x58, "I", "resident_name_table_off"),
    (0x5C, "I", "entry_table_off"),
    (0x60, "I", "module_directives_off"),
    (0x64, "I", "num_module_directives"),
    (0x68, "I", "fixup_page_table_off"),
    (0x6C, "I", "fixup_record_table_off"),
    (0x70, "I", "import_module_table_off"),
    (0x74, "I", "num_import_mod_entries"),
    (0x78, "I", "import_proc_table_off"),
    (0x7C, "I", "per_page_checksum_off"),
    (0x80, "I", "data_pages_off"),
    (0x84, "I", "num_preload_pages"),
    (0x88, "I", "non_res_name_table_off"),
    (0x8C, "I", "non_res_name_table_len"),
    (0x90, "I", "non_res_name_table_cksum"),
    (0x94, "I", "auto_ds_object"),
    (0x98, "I", "debug_info_off"),
    (0x9C, "I", "debug_info_len"),
    (0xA0, "I", "num_instance_preload"),
    (0xA4, "I", "num_instance_demand"),
    (0xA8, "I", "heap_size"),
]

OBJ_FLAGS = [
    (0x0001, "READABLE"), (0x0002, "WRITABLE"), (0x0004, "EXECUTABLE"),
    (0x0008, "RESOURCE"), (0x0010, "DISCARDABLE"), (0x0020, "SHARED"),
    (0x0040, "PRELOAD"), (0x0080, "INVALID"), (0x0100, "ZERO_FILLED"),
    (0x0200, "RESIDENT"), (0x0400, "CONTIGUOUS"), (0x0800, "LOCKABLE"),
    (0x1000, "ALIAS16"), (0x2000, "BIG_32BIT"), (0x4000, "CONFORMING"),
    (0x8000, "IO_PRIV"),
]


def parse_le(data, base, path):
    print("\n" + "=" * 78)
    print(f"LE/LX header @ file offset 0x{base:X}")
    print("=" * 78)
    print(hexdump(data[base:base + 0xC0], base))

    le = {}
    print("\n-- LE fields (LE-relative offset / file offset, name, value) --")
    for off, fmt, name in LE_FIELDS:
        (v,) = struct.unpack_from("<" + fmt, data, base + off)
        le[name] = v
        if fmt == "2s":
            print(f"  +0x{off:02X} @0x{base + off:06X}  {name:<28} = {v!r}")
        else:
            print(f"  +0x{off:02X} @0x{base + off:06X}  {name:<28} = 0x{v:08X} ({v})")

    sig = le["signature"]
    if sig not in (b"LE", b"LX"):
        print(f"  !! signature is {sig!r}, not LE/LX")
        return le
    if sig == b"LE":
        le["last_page_size"] = le["last_page_size_or_page_shift"]
        print(f"  (LE: +0x2C is bytes_on_last_page = {le['last_page_size']})")
    else:
        print(f"  (LX: +0x2C is page_offset_shift = {le['last_page_size_or_page_shift']})")

    print("\n-- derived --")
    print(f"  byte order  = {'little' if le['byte_order'] == 0 else 'big'}")
    print(f"  word order  = {'little' if le['word_order'] == 0 else 'big'}")
    print(f"  cpu_type    = 0x{le['cpu_type']:04X} "
          f"({ {1:'286',2:'386',3:'486',4:'586'}.get(le['cpu_type'],'?') })")
    print(f"  os_type     = 0x{le['os_type']:04X} "
          f"({ {0:'unknown/DOS4G',1:'OS/2',2:'Windows',3:'DOS4G',4:'Windows386'}.get(le['os_type'],'?') })")
    otab = base + le["object_table_off"]
    opm = base + le["object_page_map_off"]
    fpt = base + le["fixup_page_table_off"]
    frt = base + le["fixup_record_table_off"]
    dpo = le["data_pages_off"]   # LE: absolute file offset (not LE-relative)
    print(f"  object table       @ file 0x{otab:X}  ({le['num_objects']} objects)")
    print(f"  object page map    @ file 0x{opm:X}")
    print(f"  fixup page table   @ file 0x{fpt:X}")
    print(f"  fixup record table @ file 0x{frt:X}")
    print(f"  data pages offset  = 0x{dpo:X} (absolute file offset for LE)")
    print(f"  page size          = 0x{le['page_size']:X} ({le['page_size']})")
    print(f"  module pages       = {le['module_num_pages']}")
    est_end = dpo + (le["module_num_pages"] - 1) * le["page_size"] + le.get("last_page_size", le["page_size"])
    print(f"  data pages span    = 0x{dpo:X} .. 0x{est_end:X}   (file size 0x{len(data):X})")

    # object table
    print(f"\n-- object table ({le['num_objects']} entries, 24 B each) @ 0x{otab:X} --")
    print(hexdump(data[otab:otab + 24 * le["num_objects"]], otab))
    objs = []
    for i in range(le["num_objects"]):
        o = otab + 24 * i
        (vsize, reloc_base, flags, page_map_idx, page_map_entries, rsv) = struct.unpack_from("<IIIIII", data, o)
        objs.append(dict(vsize=vsize, base=reloc_base, flags=flags,
                         first_page=page_map_idx, npages=page_map_entries))
        fl = "|".join(n for m, n in OBJ_FLAGS if flags & m)
        pages_needed = (vsize + le["page_size"] - 1) // le["page_size"]
        print(f"  obj#{i + 1}: vsize=0x{vsize:08X} base=0x{reloc_base:08X} flags=0x{flags:04X} [{fl}]")
        print(f"          page_map_index={page_map_idx} page_map_entries={page_map_entries}"
              f"   ceil(vsize/page)={pages_needed}"
              f"   {'CONSISTENT' if pages_needed == page_map_entries else '*** MISMATCH ***'}")
    total_pages = sum(o["npages"] for o in objs)
    print(f"  sum(page_map_entries) = {total_pages}   module_num_pages = {le['module_num_pages']}"
          f"   {'CONSISTENT' if total_pages == le['module_num_pages'] else '*** MISMATCH ***'}")

    eo = le["eip_object"]
    print(f"\n  entry object index = {eo} -> "
          f"{'IN RANGE' if 1 <= eo <= le['num_objects'] else '*** OUT OF RANGE ***'}")

    # page map
    print(f"\n-- object page map @ 0x{opm:X} (LE: 4 B/entry: page# u24-BE + flags u8) --")
    print(hexdump(data[opm:opm + min(4 * le["module_num_pages"], 96)], opm))
    pmap = []
    for i in range(le["module_num_pages"]):
        p = opm + 4 * i
        hi, lo, flg = struct.unpack_from(">HBB", data, p)   # u24 big-endian + flags
        pmap.append((hi << 8 | lo, flg))
    ident = all(pmap[i][0] == i + 1 for i in range(len(pmap)))
    print(f"  first 8 entries: {pmap[:8]}")
    print(f"  page map is identity (entry i -> page i+1): {ident}")

    # entry point file offset
    if 1 <= eo <= le["num_objects"]:
        obj = objs[eo - 1]
        eip = le["eip"]
        page_in_obj = eip // le["page_size"]
        off_in_page = eip % le["page_size"]
        pm_idx = obj["first_page"] - 1 + page_in_obj
        phys_page, flg = pmap[pm_idx]
        ep_file = dpo + (phys_page - 1) * le["page_size"] + off_in_page
        print(f"\n-- entry point --")
        print(f"  eip_object={eo}  eip=0x{eip:X}   object base = 0x{obj['base']:08X}")
        print(f"  linear entry address = base + eip = 0x{obj['base'] + eip:08X}")
        print(f"  page_in_obj={page_in_obj} off_in_page=0x{off_in_page:X} "
              f"page_map_idx={pm_idx} -> physical page {phys_page} (flags {flg})")
        print(f"  entry file offset = data_pages 0x{dpo:X} + (page-1)*0x{le['page_size']:X}"
              f" + 0x{off_in_page:X} = 0x{ep_file:X}")
        print(hexdump(data[ep_file:ep_file + 48], ep_file))
        try:
            from capstone import Cs, CS_ARCH_X86, CS_MODE_32
            md = Cs(CS_ARCH_X86, CS_MODE_32)
            print("  disassembly (CS_MODE_32) at the entry:")
            for ins in md.disasm(data[ep_file:ep_file + 64], obj["base"] + eip):
                print(f"    {ins.address:08X}  {ins.bytes.hex():<16} {ins.mnemonic} {ins.op_str}")
        except ImportError:
            print("  (capstone unavailable)")
        le["_ep_file"] = ep_file

    so = le["esp_object"]
    if 1 <= so <= le["num_objects"]:
        print(f"\n  initial SS:ESP -> object {so} (base 0x{objs[so - 1]['base']:08X}) "
              f"esp=0x{le['esp']:X} -> linear 0x{objs[so - 1]['base'] + le['esp']:08X}")

    le["_objs"] = objs
    le["_pmap"] = pmap
    le["_otab"] = otab
    le["_opm"] = opm
    le["_fpt"] = fpt
    le["_frt"] = frt
    le["_dpo"] = dpo
    return le


def main():
    for path in sys.argv[1:]:
        data = open(path, "rb").read()
        mz, hdr_size, img_size, lfanew = parse_mz(data, path)
        if data[:2] in (b"MZ", b"ZM") and lfanew and lfanew + 2 <= len(data):
            if data[lfanew:lfanew + 2] in (b"LE", b"LX", b"NE", b"PE"):
                parse_le(data, lfanew, path)
            else:
                print(f"\n  dword@0x3C = 0x{lfanew:X} -> "
                      f"{data[lfanew:lfanew + 2]!r}, not a known new-exe signature")
                # search for LE signature
                for probe in range(0, min(len(data), 0x80000)):
                    if data[probe:probe + 2] in (b"LE", b"LX") and data[probe + 2] < 2 and data[probe + 3] < 2:
                        print(f"  candidate LE/LX signature found at 0x{probe:X}")
                        parse_le(data, probe, path)
                        break
        print()


if __name__ == "__main__":
    main()
