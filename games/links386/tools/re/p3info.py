#!/usr/bin/env python3
"""Audit Phar Lap P2/P3 EXP containers embedded in a DOS executable."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


FIELDS = (
    ("level", "H"),
    ("header_size", "H"),
    ("file_size", "I"),
    ("checksum16", "H"),
    ("runtime_offset", "I"),
    ("runtime_size", "I"),
    ("relocation_offset", "I"),
    ("relocation_size", "I"),
    ("segment_info_offset", "I"),
    ("segment_info_size", "I"),
    ("segment_info_entry_size", "H"),
    ("load_offset", "I"),
    ("load_size", "I"),
    ("symbol_offset", "I"),
    ("symbol_size", "I"),
    ("gdt_offset", "I"),
    ("gdt_size", "I"),
    ("ldt_offset", "I"),
    ("ldt_size", "I"),
    ("idt_offset", "I"),
    ("idt_size", "I"),
    ("tss_offset", "I"),
    ("tss_size", "I"),
    ("minimum_extra", "I"),
    ("maximum_extra", "I"),
    ("base_load_offset", "I"),
    ("initial_esp", "I"),
    ("initial_ss", "H"),
    ("initial_eip", "I"),
    ("initial_cs", "H"),
    ("initial_ldt", "H"),
    ("initial_tss", "H"),
    ("flags", "H"),
    ("memory_requirements", "I"),
    ("checksum32", "I"),
    ("stack_size", "I"),
)


def parse(data: bytes, offset: int) -> dict[str, int | bytes]:
    if data[offset : offset + 2] not in (b"P2", b"P3"):
        raise ValueError(f"no P2/P3 signature at 0x{offset:X}")
    values: dict[str, int | bytes] = {"signature": data[offset : offset + 2]}
    pos = offset + 2
    for name, fmt in FIELDS:
        size = struct.calcsize("<" + fmt)
        if pos + size > len(data):
            raise ValueError(f"truncated header at 0x{offset:X}")
        values[name] = struct.unpack_from("<" + fmt, data, pos)[0]
        pos += size
    end = offset + int(values["file_size"])
    if end > len(data):
        raise ValueError(
            f"EXP at 0x{offset:X} ends at 0x{end:X}, past file size 0x{len(data):X}"
        )
    if int(values["header_size"]) < 0x180:
        raise ValueError(f"unexpected short P3 header at 0x{offset:X}")
    for label in ("runtime", "load"):
        sub_offset = int(values[f"{label}_offset"])
        sub_size = int(values[f"{label}_size"])
        if sub_offset + sub_size > int(values["file_size"]):
            raise ValueError(f"{label} block escapes EXP at 0x{offset:X}")
    return values


def emit(index: int, offset: int, values: dict[str, int | bytes]) -> None:
    print(f"EXP {index} @ file 0x{offset:X}")
    print(f"  signature              {values['signature'].decode('ascii')}")
    for name, _ in FIELDS:
        value = values[name]
        if isinstance(value, int):
            print(f"  {name:24} {value} (0x{value:X})")
        else:
            print(f"  {name:24} {value!r}")
    end = offset + int(values["file_size"])
    load_start = offset + int(values["load_offset"])
    entry = load_start + int(values["initial_eip"])
    print(f"  file end               0x{end:X}")
    print(f"  load image on disk    0x{load_start:X}..0x{load_start + int(values['load_size']):X}")
    print(f"  initial entry file    0x{entry:X}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--all", action="store_true", help="walk adjacent EXP files")
    parser.add_argument("--dump-load-dir", type=Path)
    args = parser.parse_args()

    data = args.executable.read_bytes()
    offset = args.offset
    index = 0
    while offset < len(data):
        values = parse(data, offset)
        emit(index, offset, values)
        if args.dump_load_dir:
            args.dump_load_dir.mkdir(parents=True, exist_ok=True)
            start = offset + int(values["load_offset"])
            end = start + int(values["load_size"])
            out = args.dump_load_dir / f"{args.executable.stem}.exp{index}.load"
            out.write_bytes(data[start:end])
            print(f"  wrote load image       {out}")
        next_offset = offset + int(values["file_size"])
        index += 1
        if not args.all or next_offset == len(data):
            if args.all and next_offset == len(data):
                print(f"adjacent EXP stream ends exactly at 0x{next_offset:X}")
            break
        if next_offset <= offset:
            raise ValueError("non-advancing EXP file size")
        offset = next_offset


if __name__ == "__main__":
    main()
