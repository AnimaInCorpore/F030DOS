#!/usr/bin/env python3
"""Validate area DAT decoration-property tables."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from pakinfo import parse_pak


RECORD_SIZE = 72


def parse_dat(data: bytes) -> int:
    if len(data) < 2:
        raise ValueError("DAT file is too small")
    count = struct.unpack_from("<H", data)[0]
    if len(data) != 2 + count * RECORD_SIZE:
        raise ValueError("DAT count does not match its 72-byte records")
    return count


def inspect(path: Path) -> tuple[str, int] | None:
    data = path.read_bytes()
    entries, _ = parse_pak(data)
    dat = next((entry for entry in entries if entry.name.upper().endswith(".DAT")), None)
    if dat is None:
        return None
    return dat.name, parse_dat(data[dat.offset:dat.offset + dat.size])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="an area PAK or DATA directory")
    args = parser.parse_args()
    paths = sorted(args.path.glob("*.PAK")) if args.path.is_dir() else [args.path]
    try:
        results = []
        for path in paths:
            result = inspect(path)
            if result is not None:
                results.append((path.name, *result))
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")
    total = 0
    for pak, name, count in results:
        total += count
        print(f"{pak}:{name}: records={count}; stride={RECORD_SIZE}; invariant=PASS")
    print(f"validated {len(results)} DAT tables, {total} records")


if __name__ == "__main__":
    main()
