#!/usr/bin/env python3
"""Audit a DOS/4G Watcom MZ + LE executable.

The audit is deliberately structural.  It decodes the MZ header, LE object
table, object page map and fixup tables, and checks the arithmetic identities
that make the file-to-object mapping trustworthy.  It does not assign a
protected-mode origin to raw file bytes beyond the LE object bases.

Examples::

    python tools/re/audit_le.py game/MagCarp/CARPET/CARPET.EXE
    python tools/re/audit_le.py game/MagCarp/CARPET/CARPET.EXE --stats
    python tools/re/audit_le.py game/MagCarp/CARPET/CARPET.EXE --target 3:0x1234
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from collections import Counter
from pathlib import Path


MZ_FIELDS = (
    "signature lastpage pages relocs hdrparas minalloc maxalloc ss sp "
    "checksum ip cs reloctab overlay"
).split()

SOURCE_TYPES = {
    0: "byte",
    2: "16-bit selector",
    3: "16:16 pointer",
    5: "16-bit offset",
    6: "16:32 pointer",
    7: "32-bit offset",
    8: "32-bit self-relative offset",
}
TARGET_TYPES = {0: "internal", 1: "import ordinal", 2: "import name", 3: "entry"
}


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def parse_mz(data: bytes) -> dict[str, int]:
    values = struct.unpack_from("<14H", data)
    mz = dict(zip(MZ_FIELDS, values))
    mz["header_size"] = mz["hdrparas"] * 16
    mz["image_size"] = ((mz["pages"] - 1) * 512 + mz["lastpage"]
                         if mz["lastpage"] else mz["pages"] * 512)
    if data[:2] not in (b"MZ", b"ZM"):
        raise ValueError("not an MZ executable")
    if not mz["header_size"] <= mz["image_size"] <= len(data):
        raise ValueError("invalid MZ image boundary")
    return mz


def parse_le(data: bytes, base: int) -> dict:
    if data[base:base + 2] != b"LE":
        raise ValueError(f"no LE signature at file 0x{base:X}")

    fields = {
        "format_level": u32(data, base + 0x04),
        "cpu_type": u16(data, base + 0x08),
        "os_type": u16(data, base + 0x0A),
        "module_flags": u32(data, base + 0x10),
        "pages": u32(data, base + 0x14),
        "entry_object": u32(data, base + 0x18),
        "entry_offset": u32(data, base + 0x1C),
        "stack_object": u32(data, base + 0x20),
        "stack_offset": u32(data, base + 0x24),
        "page_size": u32(data, base + 0x28),
        "last_page_size": u32(data, base + 0x2C),
        "object_table": u32(data, base + 0x40),
        "object_count": u32(data, base + 0x44),
        "page_map": u32(data, base + 0x48),
        "resource_table": u32(data, base + 0x50),
        "entry_table": u32(data, base + 0x5C),
        "fixup_page_table": u32(data, base + 0x68),
        "fixup_record_table": u32(data, base + 0x6C),
        "import_module_table": u32(data, base + 0x70),
        "import_proc_table": u32(data, base + 0x78),
        "data_pages": u32(data, base + 0x80),
        "auto_ds_object": u32(data, base + 0x94),
    }
    fields["object_table_file"] = base + fields["object_table"]
    fields["page_map_file"] = base + fields["page_map"]
    fields["fixup_page_table_file"] = base + fields["fixup_page_table"]
    fields["fixup_record_table_file"] = base + fields["fixup_record_table"]
    fields["import_module_table_file"] = base + fields["import_module_table"]
    fields["data_end"] = (fields["data_pages"] +
                           (fields["pages"] - 1) * fields["page_size"] +
                           fields["last_page_size"])

    objects = []
    for index in range(fields["object_count"]):
        offset = fields["object_table_file"] + index * 24
        vsize, obj_base, flags, first, count, _reserved = struct.unpack_from(
            "<IIIIII", data, offset)
        objects.append({"number": index + 1, "vsize": vsize, "base": obj_base,
                        "flags": flags, "first_page": first,
                        "page_count": count})
    fields["objects"] = objects

    page_map = []
    for index in range(fields["pages"]):
        offset = fields["page_map_file"] + index * 4
        hi, lo, flags = struct.unpack_from(">HBB", data, offset)
        page_map.append((hi << 8 | lo, flags))
    fields["page_map_entries"] = page_map
    fields["page_map_identity"] = all(page == index + 1 and flags == 0
                                       for index, (page, flags) in enumerate(page_map))
    fields["fixup_page_offsets"] = [
        u32(data, fields["fixup_page_table_file"] + index * 4)
        for index in range(fields["pages"] + 1)
    ]
    return fields


def object_for_page(objects: list[dict], page_index: int) -> dict | None:
    for obj in objects:
        start = obj["first_page"] - 1
        if start <= page_index < start + obj["page_count"]:
            return obj
    return None


def page_file_offset(le: dict, page_index: int) -> int:
    physical_page = le["page_map_entries"][page_index][0]
    return le["data_pages"] + (physical_page - 1) * le["page_size"]


def page_linear_offset(le: dict, page_index: int) -> int | None:
    obj = object_for_page(le["objects"], page_index)
    if obj is None:
        return None
    within = page_index - (obj["first_page"] - 1)
    return obj["base"] + within * le["page_size"]


def decode_fixup_page(data: bytes, le: dict, page_index: int) -> list[dict]:
    starts = le["fixup_page_offsets"]
    pos = le["fixup_record_table_file"] + starts[page_index]
    end = le["fixup_record_table_file"] + starts[page_index + 1]
    records = []
    while pos < end:
        record_start = pos
        source_byte, flags = data[pos], data[pos + 1]
        pos += 2
        source_type = source_byte & 0x0F
        source_list = bool(source_byte & 0x20)
        if source_list:
            source_count = data[pos]
            pos += 1
            source_offsets = None
        else:
            source_count = 1
            source_offsets = [struct.unpack_from("<h", data, pos)[0]]
            pos += 2

        target_type = flags & 3
        additive = bool(flags & 4)
        if target_type == 0:
            if flags & 0x40:
                target_object = u16(data, pos)
                pos += 2
            else:
                target_object = data[pos]
                pos += 1
            if source_type == 2:
                target_offset = 0
            elif flags & 0x10:
                target_offset = u32(data, pos)
                pos += 4
            else:
                target_offset = u16(data, pos)
                pos += 2
        elif target_type == 1:
            target_object = u16(data, pos) if flags & 0x40 else data[pos]
            pos += 2 if flags & 0x40 else 1
            if flags & 0x80:
                target_offset = data[pos]
                pos += 1
            elif flags & 0x10:
                target_offset = u32(data, pos)
                pos += 4
            else:
                target_offset = u16(data, pos)
                pos += 2
        else:
            target_object = target_offset = -1

        addend = None
        if additive:
            if flags & 0x20:
                addend = u32(data, pos)
                pos += 4
            else:
                addend = u16(data, pos)
                pos += 2

        if source_list:
            source_offsets = [struct.unpack_from("<h", data, pos + 2 * i)[0]
                              for i in range(source_count)]
            pos += 2 * source_count

        records.append({"offset": record_start, "source_type": source_type,
                        "flags": flags, "target_type": target_type,
                        "target_object": target_object,
                        "target_offset": target_offset,
                        "source_offsets": source_offsets, "addend": addend,
                        "size": pos - record_start})
    if pos != end:
        raise ValueError(f"fixup page {page_index} ended at 0x{pos:X}, expected 0x{end:X}")
    return records


def validate(data: bytes, le: dict) -> tuple[list[dict], Counter, Counter, list[dict]]:
    if le["data_end"] != len(data):
        raise ValueError(f"LE data pages end at 0x{le['data_end']:X}, file is 0x{len(data):X}")
    if sum(obj["page_count"] for obj in le["objects"]) != le["pages"]:
        raise ValueError("object page counts do not sum to module page count")
    if le["page_map_identity"]:
        pass
    elif sorted(page for page, _ in le["page_map_entries"]) != list(range(1, le["pages"] + 1)):
        raise ValueError("object page map is neither identity nor a permutation")
    fpt = le["fixup_page_offsets"]
    if fpt != sorted(fpt):
        raise ValueError("fixup page offsets are not monotonic")
    fixup_end = le["fixup_record_table_file"] + fpt[-1]
    if fixup_end != le["import_module_table_file"]:
        raise ValueError(f"fixup records end at 0x{fixup_end:X}, import table is 0x{le['import_module_table_file']:X}")

    all_records = []
    by_source = Counter()
    by_target = Counter()
    target_range_warnings = []
    for page in range(le["pages"]):
        records = decode_fixup_page(data, le, page)
        all_records.extend(records)
        for record in records:
            sites = len(record["source_offsets"])
            by_source[record["source_type"]] += sites
            by_target[record["target_type"]] += sites
            obj_no = record["target_object"]
            if record["target_type"] == 0:
                if not 1 <= obj_no <= len(le["objects"]):
                    raise ValueError(f"fixup targets invalid object {obj_no}")
                if record["target_offset"] >= le["objects"][obj_no - 1]["vsize"]:
                    # Keep the raw u32.  LE records can carry a signed
                    # displacement in a 32-bit field; CARPET has one such
                    # record (-0x91433 as i32) in an otherwise ordinary
                    # internal-fixup stream.  This is a warning for semantic
                    # interpretation, not a table-walk failure.
                    target_range_warnings.append(record)
            for source_offset in record["source_offsets"]:
                # LE source offsets are signed.  A record can be attached to
                # the page containing the end of a relocated field, leaving a
                # small negative offset when the field starts in the previous
                # page.  CARPET has one such 32-bit field at page 8, offset
                # -3; validate the resulting file location instead.
                source_file = page_file_offset(le, page) + source_offset
                if not le["data_pages"] <= source_file < le["data_end"]:
                    raise ValueError("fixup source location lies outside data pages")
    return all_records, by_source, by_target, target_range_warnings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--stats", action="store_true", help="print fixup statistics")
    parser.add_argument("--target", help="list fixups targeting OBJ:OFFSET")
    args = parser.parse_args()

    data = args.executable.read_bytes()
    mz = parse_mz(data)
    le_offset = u32(data, 0x3C)
    le = parse_le(data, le_offset)
    records, by_source, by_target, target_range_warnings = validate(data, le)

    entry_obj = le["objects"][le["entry_object"] - 1]
    entry_page = entry_obj["first_page"] - 1 + le["entry_offset"] // le["page_size"]
    entry_file = (page_file_offset(le, entry_page) +
                  le["entry_offset"] % le["page_size"])
    print(f"file: {args.executable} ({len(data)} bytes, SHA-256 {hashlib.sha256(data).hexdigest()})")
    print(f"MZ: image 0x{mz['header_size']:X}..0x{mz['image_size']:X}, "
          f"entry {mz['cs']:04X}:{mz['ip']:04X} -> file 0x{mz['header_size'] + (mz['cs'] << 4) + mz['ip']:X}, "
          f"relocations {mz['relocs']}")
    print(f"LE: header 0x{le_offset:X}, CPU 0x{le['cpu_type']:X}, "
          f"pages {le['pages']} x 0x{le['page_size']:X} + last 0x{le['last_page_size']:X}")
    print(f"    data pages 0x{le['data_pages']:X}..0x{le['data_end']:X} (exact EOF)")
    print(f"    object table 0x{le['object_table_file']:X}, page map 0x{le['page_map_file']:X} "
          f"({'identity' if le['page_map_identity'] else 'non-identity'})")
    for obj in le["objects"]:
        mapped = obj["page_count"] * le["page_size"]
        unbacked = max(0, obj["vsize"] - mapped)
        mapped_tail = max(0, mapped - obj["vsize"])
        print(f"    obj{obj['number']}: base 0x{obj['base']:X}, vsize 0x{obj['vsize']:X}, "
              f"pages {obj['first_page']}+{obj['page_count']}, mapped 0x{mapped:X}, "
              f"unbacked-at-least 0x{unbacked:X}, mapped-tail 0x{mapped_tail:X}")
    print(f"entry: obj{le['entry_object']}+0x{le['entry_offset']:X} -> "
          f"linear 0x{entry_obj['base'] + le['entry_offset']:X}, file 0x{entry_file:X}")
    print(f"stack: obj{le['stack_object']}+0x{le['stack_offset']:X} -> "
          f"linear 0x{le['objects'][le['stack_object'] - 1]['base'] + le['stack_offset']:X}; "
          f"auto-DS obj{le['auto_ds_object']}")
    print(f"fixups: page table 0x{le['fixup_page_table_file']:X}, records "
          f"0x{le['fixup_record_table_file']:X}..0x{le['import_module_table_file']:X}, "
          f"{len(records)} records / {sum(by_source.values())} source sites")
    if target_range_warnings:
        print(f"  warning: {len(target_range_warnings)} internal target offset(s) "
              "exceed the nominal object virtual size; retain raw u32 values")
    if args.stats:
        print("  source sites by type:", {SOURCE_TYPES.get(k, k): v for k, v in sorted(by_source.items())})
        print("  source sites by target:", {TARGET_TYPES.get(k, k): v for k, v in sorted(by_target.items())})
    if args.target:
        obj_text, offset_text = args.target.split(":", 1)
        target_obj, target_offset = int(obj_text, 0), int(offset_text, 0)
        hits = 0
        for page in range(le["pages"]):
            for record in decode_fixup_page(data, le, page):
                if (record["target_type"] != 0 or
                        record["target_object"] != target_obj or
                        record["target_offset"] != target_offset):
                    continue
                for source_offset in record["source_offsets"]:
                    source_file = page_file_offset(le, page) + source_offset
                    page_linear = page_linear_offset(le, page)
                    source_linear = (page_linear + source_offset
                                     if page_linear is not None else None)
                    raw = ""
                    if 0 <= source_file and source_file + 4 <= len(data):
                        raw = f" raw={data[source_file:source_file + 4].hex().upper()}"
                    print(f"  page {page}, source file 0x{source_file:X}"
                          f"{f', linear 0x{source_linear:X}' if source_linear is not None else ''}"
                          f", source offset {source_offset}{raw}")
                    hits += 1
        print(f"target obj{target_obj}:0x{target_offset:X}: {hits} source sites")


if __name__ == "__main__":
    main()
