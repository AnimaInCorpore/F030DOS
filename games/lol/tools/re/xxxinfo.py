#!/usr/bin/env python3
"""Validate the 12-byte automap legend records in level PAKs."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from pakinfo import parse_pak


def parse_xxx(data: bytes) -> int:
    if not data or len(data) % 12:
        raise ValueError("XXX size is not a multiple of 12")
    for offset in range(0, len(data), 12):
        struct.unpack_from("<6H", data, offset)
    return len(data) // 12


def inspect(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    entries, _ = parse_pak(data)
    xxx = next((entry for entry in entries if entry.name.upper().endswith(".XXX")), None)
    if xxx is None:
        raise ValueError(f"{path.name}: no XXX member")
    return xxx.name, parse_xxx(data[xxx.offset:xxx.offset + xxx.size])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="an L##.PAK or DATA directory")
    args = parser.parse_args()
    paths = sorted(args.path.glob("L??.PAK")) if args.path.is_dir() else [args.path]
    try:
        results = [(path.name, *inspect(path)) for path in paths]
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")
    total = 0
    for pak, name, records in results:
        total += records
        print(f"{pak}:{name}: records={records}; stride=12; invariant=PASS")
    print(f"validated {len(results)} XXX tables, {total} records")


if __name__ == "__main__":
    main()
