#!/usr/bin/env python3
"""Decode the LE fixup page table + fixup record table of Z_TIE__.EXE.

Answers: are the raw operands in the file unrelocated, and do fixup records
patch them at load time?  Usage (note the '=' — space-separated forms are
silently ignored):

    python work/audit_fixups.py [--stats] [--page=N] [--target=OBJ:OFF]
"""
import struct
import sys

PATH = "game/SWTieCD/TIECD/Z_TIE__.EXE"
data = open(PATH, "rb").read()
LE = 0x2A50

def u32(o):
    return struct.unpack_from("<I", data, o)[0]

num_pages = u32(LE + 0x14)
page_size = u32(LE + 0x28)
otab = LE + u32(LE + 0x40)
nobj = u32(LE + 0x44)
opm = LE + u32(LE + 0x48)
fpt = LE + u32(LE + 0x68)
frt = LE + u32(LE + 0x6C)
dpo = u32(LE + 0x80)

objs = []
for i in range(nobj):
    vsize, base, flags, first, npg, _ = struct.unpack_from("<IIIIII", data, otab + 24 * i)
    objs.append(dict(vsize=vsize, base=base, flags=flags, first=first, npages=npg))

pmap = []
for i in range(num_pages):
    hi, lo, flg = struct.unpack_from(">HBB", data, opm + 4 * i)
    pmap.append(hi << 8 | lo)

def page_file_off(idx0):           # idx0 = 0-based page-map index
    return dpo + (pmap[idx0] - 1) * page_size

def obj_of_page(idx0):
    for n, o in enumerate(objs, 1):
        if o["first"] - 1 <= idx0 < o["first"] - 1 + o["npages"]:
            return n, o
    return None, None

def linear_of_page(idx0):
    n, o = obj_of_page(idx0)
    return o["base"] + (idx0 - (o["first"] - 1)) * page_size

SRC = {0: "byte", 2: "16-bit selector", 3: "16:16 ptr", 5: "16-bit off",
       6: "16:32 ptr", 7: "32-bit off", 8: "32-bit self-rel off"}
TGT = {0: "internal", 1: "import ordinal", 2: "import name", 3: "int entry"}

fpe = [u32(fpt + 4 * i) for i in range(num_pages + 1)]

def decode_page(idx0, verbose=False, want=None):
    """Decode all fixup records for page idx0. Returns list of dicts."""
    start, end = frt + fpe[idx0], frt + fpe[idx0 + 1]
    p = start
    out = []
    while p < end:
        rec_start = p
        src = data[p]; flags = data[p + 1]; p += 2
        stype = src & 0x0F
        srclist = bool(src & 0x20)
        if srclist:
            cnt = data[p]; p += 1
            srcoffs = None
        else:
            cnt = 1
            srcoffs = [struct.unpack_from("<h", data, p)[0]]; p += 2
        tt = flags & 3
        additive = bool(flags & 4)
        if tt == 0:                     # internal
            if flags & 0x40:
                objn = struct.unpack_from("<H", data, p)[0]; p += 2
            else:
                objn = data[p]; p += 1
            if stype == 2:              # 16-bit selector: no offset
                toff = 0
            elif flags & 0x10:
                toff = struct.unpack_from("<I", data, p)[0]; p += 4
            else:
                toff = struct.unpack_from("<H", data, p)[0]; p += 2
        elif tt == 1:                   # import by ordinal
            objn = struct.unpack_from("<H", data, p)[0] if flags & 0x40 else data[p]
            p += 2 if flags & 0x40 else 1
            if flags & 0x80:
                toff = data[p]; p += 1
            elif flags & 0x10:
                toff = struct.unpack_from("<I", data, p)[0]; p += 4
            else:
                toff = struct.unpack_from("<H", data, p)[0]; p += 2
        else:
            objn = -1; toff = -1
        addval = None
        if additive:
            if flags & 0x20:
                addval = struct.unpack_from("<I", data, p)[0]; p += 4
            else:
                addval = struct.unpack_from("<H", data, p)[0]; p += 2
        if srclist:
            srcoffs = [struct.unpack_from("<h", data, p + 2 * i)[0] for i in range(cnt)]
            p += 2 * cnt
        rec = dict(off=rec_start, src=src, stype=stype, flags=flags, tt=tt,
                   additive=additive, objn=objn, toff=toff, add=addval,
                   srcoffs=srcoffs, size=p - rec_start)
        out.append(rec)
        if verbose:
            print(f"  @0x{rec_start:06X} src=0x{src:02X}({SRC.get(stype,'?')}) "
                  f"flags=0x{flags:02X}({TGT.get(tt,'?')}{',additive' if additive else ''}) "
                  f"-> obj{objn}:0x{toff:X} srcoffs={[hex(s) for s in srcoffs]}"
                  f"{f' add=0x{addval:X}' if addval is not None else ''}")
    return out, start, end

if __name__ == "__main__":
    args = sys.argv[1:]
    print(f"num_pages={num_pages} page_size=0x{page_size:X} objs={nobj} "
          f"fpt=0x{fpt:X} frt=0x{frt:X} dpo=0x{dpo:X}")
    for n, o in enumerate(objs, 1):
        print(f"  obj{n}: base=0x{o['base']:08X} vsize=0x{o['vsize']:X} "
              f"pages {o['first']}..{o['first']+o['npages']-1} "
              f"file 0x{page_file_off(o['first']-1):X}..")
    print(f"fixup page table: {num_pages+1} u32 entries, last=0x{fpe[-1]:X}, "
          f"frt+last=0x{frt+fpe[-1]:X}  (import_module_table @ 0x{LE+u32(LE+0x70):X})")

    if "--stats" in args:
        tot = 0; bysrc = {}; bytt = {}
        for i in range(num_pages):
            recs, s, e = decode_page(i)
            tot += len(recs)
            for r in recs:
                bysrc[r["stype"]] = bysrc.get(r["stype"], 0) + len(r["srcoffs"])
                bytt[r["tt"]] = bytt.get(r["tt"], 0) + len(r["srcoffs"])
            if e != frt + fpe[i + 1]:
                print(f"  page {i}: record walk overran")
        print(f"total fixup records = {tot}")
        print("  sources by type:", {SRC.get(k, k): v for k, v in sorted(bysrc.items())})
        print("  targets by type:", {TGT.get(k, k): v for k, v in sorted(bytt.items())})

    for a in args:
        if a.startswith("--page="):
            i = int(a.split("=")[1], 0)
            n, o = obj_of_page(i)
            print(f"\n== page {i} (obj{n}, linear 0x{linear_of_page(i):X}, "
                  f"file 0x{page_file_off(i):X}) ==")
            recs, s, e = decode_page(i, verbose=True)
            print(f"  {len(recs)} records, bytes 0x{s:X}..0x{e:X}")
        if a.startswith("--target="):
            os_, off_ = a.split("=")[1].split(":")
            to, tf = int(os_, 0), int(off_, 0)
            print(f"\n== fixups targeting obj{to}:0x{tf:X} (linear "
                  f"0x{objs[to-1]['base']+tf:X}) ==")
            hits = 0
            for i in range(num_pages):
                recs, s, e = decode_page(i)
                for r in recs:
                    if r["tt"] == 0 and r["objn"] == to and r["toff"] == tf:
                        for so in r["srcoffs"]:
                            fo = page_file_off(i) + so
                            lin = linear_of_page(i) + so
                            raw = data[fo:fo + 4] if 0 <= so <= page_size - 4 else b""
                            print(f"  page {i} (obj{obj_of_page(i)[0]}) srcoff=0x{so:X}"
                                  f" -> file 0x{fo:X} linear 0x{lin:X}"
                                  f"  src={SRC.get(r['stype'])}"
                                  f"  raw dword in file = {raw.hex().upper()}"
                                  f" (0x{struct.unpack('<I',raw)[0]:08X})" if len(raw) == 4 else "")
                            hits += 1
            print(f"  {hits} source sites")
