#!/usr/bin/env python3
"""Audit Magic Carpet's 256-byte remap/lighting table banks."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROW_SIZE = 256
EXPECTED_ROWS = 326


def compact_ranges(values: list[int]) -> str:
    """Render sorted integer values as compact inclusive ranges."""
    if not values:
        return "none"
    ranges: list[str] = []
    start = previous = values[0]
    for value in values[1:]:
        if value == previous + 1:
            previous = value
            continue
        ranges.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    ranges.append(str(start) if start == previous else f"{start}-{previous}")
    return ",".join(ranges)


def row_summary(data: bytes) -> tuple[list[int], list[tuple[int, int]], list[int]]:
    rows = [data[offset : offset + ROW_SIZE] for offset in range(0, len(data), ROW_SIZE)]
    uniform = [index for index, row in enumerate(rows) if len(set(row)) == 1]
    identity_counts = [sum(value == index for index, value in enumerate(row)) for row in rows]
    best = sorted(enumerate(identity_counts), key=lambda item: (-item[1], item[0]))[:8]
    return uniform, best, identity_counts


def audit(path: Path) -> bytes:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) % ROW_SIZE:
        raise SystemExit(f"{path}: {len(data)} bytes is not a multiple of 256")
    rows = len(data) // ROW_SIZE
    if rows != EXPECTED_ROWS:
        raise SystemExit(f"{path}: expected {EXPECTED_ROWS} rows, found {rows}")

    uniform, best, identity_counts = row_summary(data)
    print(f"{path.name}: bytes={len(data)} rows={rows} sha256={digest}")
    print(f"  uniform rows={compact_ranges(uniform)}")
    print(
        "  strongest identity rows="
        + ", ".join(f"{row}:{count}/256" for row, count in best)
    )
    print(
        "  identity counts: fade[0:64]="
        f"{min(identity_counts[:64])}..{max(identity_counts[:64])}, "
        "body[64:320]="
        f"{min(identity_counts[64:320])}..{max(identity_counts[64:320])}, "
        "trailer[320:326]="
        f"{min(identity_counts[320:])}..{max(identity_counts[320:])}"
    )
    return data


def compare(left_path: Path, left: bytes, right_path: Path, right: bytes) -> None:
    differing_rows: list[int] = []
    differing_bytes = 0
    for row in range(EXPECTED_ROWS):
        left_row = left[row * ROW_SIZE : (row + 1) * ROW_SIZE]
        right_row = right[row * ROW_SIZE : (row + 1) * ROW_SIZE]
        count = sum(a != b for a, b in zip(left_row, right_row))
        if count:
            differing_rows.append(row)
            differing_bytes += count
    print(
        f"compare {left_path.name} vs {right_path.name}: "
        f"differing_rows={len(differing_rows)}/{EXPECTED_ROWS} "
        f"differing_bytes={differing_bytes}/{len(left)}"
    )
    print(f"  differing row ranges={compact_ranges(differing_rows)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tables", type=Path)
    parser.add_argument("dtables", type=Path, nargs="?")
    args = parser.parse_args()

    tables = audit(args.tables)
    if args.dtables is not None:
        dtables = audit(args.dtables)
        if len(tables) != len(dtables):
            raise SystemExit("table banks have different lengths")
        compare(args.tables, tables, args.dtables, dtables)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
