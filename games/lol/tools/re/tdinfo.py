#!/usr/bin/env python3
"""Audit Borland Turbo Debugger TDINFO/TDS data in an MZ file."""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path


COUNT_NAMES = (
    "names",
    "types",
    "members",
    "symbols",
    "globals",
    "modules",
    "locals",
    "scopes",
    "lines",
    "source_files",
    "segments",
    "correlations",
)


V316_EXTENSION_SIZE = 0x20
V316_RECORD_SIZES = {
    "class": 15,
    "parent": 2,
    "scope_class": 4,
    "module_class": 4,
    "coverage_map": 2,
    "coverage_offset": 2,
    "browser_definition": 8,
    "optimized_symbol": 9,
    "module_flags": 4,
}


def mz_image_end(data: bytes) -> int:
    if data[:2] not in (b"MZ", b"ZM"):
        raise ValueError("not an MZ executable")
    last_page, pages = struct.unpack_from("<HH", data, 2)
    image_end = (pages - 1) * 512 + (last_page or 512)
    if image_end > len(data):
        raise ValueError("MZ image boundary is outside the file")
    return image_end


def mz_header_size(data: bytes) -> int:
    return struct.unpack_from("<H", data, 8)[0] * 16


def locate(data: bytes) -> tuple[int, int]:
    """Return (TDINFO offset, MZ image end), accepting .TDS or MZ input."""
    image_end = 0
    if data[:2] in (b"MZ", b"ZM"):
        image_end = mz_image_end(data)
        if data[image_end:image_end + 2] == b"\xfbR":
            return image_end, image_end
        start = image_end
    else:
        start = 0

    tdinfo = data.find(b"\xfbR", start)
    if tdinfo < 0:
        raise ValueError("TDINFO signature FB 52 not found")
    return tdinfo, image_end


def audit(path: str) -> None:
    data = Path(path).read_bytes()
    base, image_end = locate(data)
    tail = data[base:]
    if len(tail) < 0x30:
        raise ValueError("TDINFO header is truncated")

    magic, minor, major, pool_size = struct.unpack_from("<HBBI", tail)
    counts = dict(zip(COUNT_NAMES, struct.unpack_from("<12H", tail, 8)))
    extension_size = struct.unpack_from("<H", tail, 0x2E)[0]
    records_start = 0x30 + extension_size
    record_sizes = {
        "symbols": 9,
        "modules": 16,
        "source_files": 6,
        "lines": 4,
        "scopes": 12,
        "segments": 16,
        "correlations": 8,
        "types": 8,
        "members": 5,
    }
    records_size = sum(counts[name] * size for name, size in record_sizes.items())
    pool_offset = len(data) - pool_size - base
    pool = tail[pool_offset:]
    names = pool.split(b"\0")
    if names and names[-1] == b"":
        names.pop()

    print(f"{path}: {len(data)} bytes on disk")
    print(f"TDINFO at file 0x{base:X}, version {major}.{minor:02d}")
    if image_end:
        print(f"MZ image end 0x{image_end:X}; tail 0x{len(data) - image_end:X} bytes")
    print(f"  extension 0x{extension_size:X} bytes")
    print("  counts:", ", ".join(f"{name}={value}" for name, value in counts.items()))
    print(f"  standard records: file 0x{base + records_start:X}..0x{base + records_start + records_size:X}")
    print(f"  name pool: file 0x{base + pool_offset:X}..0x{len(data):X} ({pool_size} bytes)")
    post_records = records_start + records_size
    post_record_size = pool_offset - post_records
    if major == 3 and minor == 16 and extension_size == V316_EXTENSION_SIZE:
        # Borland C++ 3.x uses the compact 16-bit extension shape. The
        # coverage-offset count is at 0x3C, the name-pool offset at 0x3E,
        # and the remaining extension words are browser/optimizer flags.
        class_count, parent_count, global_class_count, overload_count = struct.unpack_from(
            "<4H", tail, 0x30
        )
        scope_class_count, module_class_count, coverage_count = struct.unpack_from(
            "<3H", tail, 0x38
        )
        name_pool_relative = struct.unpack_from("<I", tail, 0x3E)[0]
        browser_count, optimized_count, debug_flags = struct.unpack_from(
            "<3H", tail, 0x42
        )
        post_tables = {
            "class": class_count * V316_RECORD_SIZES["class"],
            "parent": parent_count * V316_RECORD_SIZES["parent"],
            "scope_class": scope_class_count * V316_RECORD_SIZES["scope_class"],
            "module_class": module_class_count * V316_RECORD_SIZES["module_class"],
            "coverage_map": counts["segments"] * V316_RECORD_SIZES["coverage_map"],
            "coverage_offset": coverage_count * V316_RECORD_SIZES["coverage_offset"],
            "browser_definition": browser_count
            * V316_RECORD_SIZES["browser_definition"],
            "optimized_symbol": optimized_count * V316_RECORD_SIZES["optimized_symbol"],
            "module_flags": counts["modules"] * V316_RECORD_SIZES["module_flags"],
        }
        table_size = sum(post_tables.values())
        table_end = post_records + table_size
        layout_ok = (
            table_end == pool_offset
            and name_pool_relative == pool_offset - records_start
        )
        print(
            "  v3.16 extension: "
            f"classes={class_count}, parents={parent_count}, "
            f"scope_classes={scope_class_count}, module_classes={module_class_count}, "
            f"coverage_offsets={coverage_count} (0x{coverage_count:X}), "
            f"browser={browser_count}, optimized={optimized_count}, "
            f"debug_flags=0x{debug_flags:04X}"
        )
        print(
            "  v3.16 post-record tables: "
            + ", ".join(f"{name}=0x{size:X}" for name, size in post_tables.items())
        )
        print(
            f"  v3.16 table end: file 0x{base + table_end:X}; "
            f"name-pool offset check={'PASS' if layout_ok else 'FAIL'}"
        )
        if not layout_ok:
            raise ValueError(
                "v3.16 post-record tables do not end at the name pool or "
                "the extension name-pool offset disagrees"
            )
        if global_class_count or overload_count:
            print(
                "  v3.16 reserved extension counts: "
                f"global_classes={global_class_count}, overloads={overload_count}"
            )
    else:
        print(f"  unclassified bytes before name pool: 0x{post_record_size:X}")
    print(f"  name NULs: {pool.count(bytes([0]))} (header names_count={counts['names']})")

    # The standard 9-byte symbol records are sufficient to prove that the
    # debug addresses refer to the loaded image. The v3.16 post-record table
    # arithmetic above additionally accounts for the compact C++ extension.
    symbol_classes = Counter()
    in_image = 0
    bad_names = 0
    symbols_start = records_start
    header_size = mz_header_size(data) if image_end else 0
    for index in range(counts["symbols"]):
        offset = symbols_start + index * 9
        name_index, _type, symbol_offset, segment, bitfield = struct.unpack_from(
            "<HHHHB", tail, offset
        )
        symbol_classes[bitfield & 7] += 1
        if not 1 <= name_index <= len(names):
            bad_names += 1
        if image_end:
            target = header_size + (segment << 4) + symbol_offset
            if header_size <= target < image_end:
                in_image += 1
    if image_end:
        print(f"  symbols resolving inside MZ image: {in_image}/{counts['symbols']}")
    print(f"  symbol name indices outside pool: {bad_names}")
    print("  symbol classes:", ", ".join(f"{key}={value}" for key, value in sorted(symbol_classes.items())))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tools/re/tdinfo.py EXECUTABLE_OR_TDS")
    try:
        audit(sys.argv[1])
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")
