#!/usr/bin/env python3
"""Validate the per-level TLC color-remap tables."""

from __future__ import annotations

import argparse
from pathlib import Path

from pakinfo import parse_pak


TABLE_ROWS = 21
ROW_SIZE = 256


def parse_tlc(data: bytes) -> tuple[int, int]:
    if len(data) != TABLE_ROWS * ROW_SIZE:
        raise ValueError(f"expected {TABLE_ROWS * ROW_SIZE} bytes, got {len(data)}")
    return TABLE_ROWS, ROW_SIZE


def inspect(path: Path) -> tuple[str, int, int]:
    data = path.read_bytes()
    entries, _ = parse_pak(data)
    tlc = next((entry for entry in entries if entry.name.upper().endswith(".TLC")), None)
    if tlc is None:
        raise ValueError(f"{path.name}: no TLC member")
    rows, width = parse_tlc(data[tlc.offset:tlc.offset + tlc.size])
    return tlc.name, rows, width


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="an L##.PAK or DATA directory")
    args = parser.parse_args()
    paths = sorted(args.path.glob("L??.PAK")) if args.path.is_dir() else [args.path]
    try:
        results = [(path.name, *inspect(path)) for path in paths]
    except (OSError, ValueError) as exc:
        raise SystemExit(f"error: {exc}")
    for pak, name, rows, width in results:
        print(f"{pak}:{name}: {rows}x{width} byte remap table; invariant=PASS")
    print(f"validated {len(results)} TLC tables")


if __name__ == "__main__":
    main()
