#!/usr/bin/env python3
"""Inspect Westwood DIP string tables, standalone or inside a PAK."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from pakinfo import parse_pak


def parse_dip(data: bytes) -> tuple[list[int], list[str]]:
    """Parse a 16-bit offset table followed by NUL-terminated CP437 strings."""
    if len(data) < 2:
        raise ValueError("DIP file is too small for an offset table")

    first_offset = struct.unpack_from("<H", data)[0]
    if first_offset == 0 or first_offset & 1:
        raise ValueError(f"invalid first string offset 0x{first_offset:X}")
    slot_count = first_offset // 2
    table_size = slot_count * 2
    if table_size != first_offset or table_size > len(data):
        raise ValueError("offset table does not fit the DIP file")

    offsets = list(struct.unpack_from(f"<{slot_count}H", data))
    if offsets[0] != table_size:
        raise ValueError("first offset is not the table size")
    if any(offset < table_size or offset >= len(data) for offset in offsets):
        raise ValueError("DIP string offset is outside the text area")
    if any(left > right for left, right in zip(offsets, offsets[1:])):
        raise ValueError("DIP string offsets are not nondecreasing")

    strings: list[str] = []
    for offset in offsets:
        end = data.find(b"\0", offset)
        if end < 0:
            raise ValueError(f"DIP string at 0x{offset:X} is not NUL-terminated")
        strings.append(data[offset:end].decode("cp437", "replace"))
    if offsets[-1] != len(data) - 1 or data[-1] != 0:
        raise ValueError("DIP table does not end with its empty sentinel string")
    return offsets, strings


def select_payload(path: Path, entry_name: str | None) -> tuple[bytes, str]:
    data = path.read_bytes()
    try:
        entries, _ = parse_pak(data)
    except (ValueError, struct.error):
        if entry_name:
            raise ValueError("--entry requires a PAK input")
        return data, path.name

    if not entry_name:
        raise ValueError("PAK input requires --entry")
    match = next((entry for entry in entries if entry.name.upper() == entry_name.upper()), None)
    if match is None:
        raise ValueError(f"PAK entry not found: {entry_name}")
    return data[match.offset:match.offset + match.size], match.name


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--entry", help="PAK member to inspect")
    parser.add_argument("--show", action="store_true", help="print indexed strings")
    args = parser.parse_args()
    try:
        data, label = select_payload(args.path, args.entry)
        offsets, strings = parse_dip(data)
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")

    print(f"{label}: {len(data)} bytes; slots={len(offsets)}; table=0x{offsets[0]:X}; strings={sum(bool(s) for s in strings)}")
    print(f"  first text 0x{offsets[0]:04X}; final empty sentinel 0x{offsets[-1]:04X}; invariant=PASS")
    if args.show:
        for index, (offset, value) in enumerate(zip(offsets, strings)):
            print(f"  {index:02d} 0x{offset:04X} {value!r}")


if __name__ == "__main__":
    main()
