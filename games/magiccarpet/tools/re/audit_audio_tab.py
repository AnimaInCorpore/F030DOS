#!/usr/bin/env python3
"""Audit Magic Carpet's decompressed sound/music directory tables."""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path


RECORD_SIZE = 32
NAME_SIZE = 26


def audit(tab_path: Path, dat_path: Path | None) -> None:
    tab = tab_path.read_bytes()
    if len(tab) < RECORD_SIZE or (len(tab) - RECORD_SIZE) % RECORD_SIZE:
        raise SystemExit(f"{tab_path}: invalid 32-byte directory layout")

    header_name, declared_total, header_tag = struct.unpack_from("<26sIH", tab, 0)
    records: list[tuple[str, int, int]] = []
    for offset in range(RECORD_SIZE, len(tab), RECORD_SIZE):
        raw_name, size, parameter = struct.unpack_from("<26sIH", tab, offset)
        name = raw_name.split(bytes([0]), 1)[0].decode("ascii", "replace")
        records.append((name, size, parameter))

    sum_sizes = sum(size for _, size, _ in records)
    if declared_total != sum_sizes:
        raise SystemExit(
            f"{tab_path}: header total {declared_total} differs from entries {sum_sizes}"
        )

    print(
        f"{tab_path.stem}: records={len(records)} table_bytes={len(tab)} "
        f"declared_member_bytes={declared_total} extensions="
        f"{dict(Counter(Path(name).suffix.upper() for name, _, _ in records))}"
    )
    print(f"  parameters={dict(Counter(parameter for _, _, parameter in records))}")
    print(f"  first={records[:3]}")
    print(f"  last={records[-3:]}")
    if dat_path is not None:
        dat_size = dat_path.stat().st_size
        relation = "matches" if dat_size == sum_sizes else "differs"
        print(f"  {dat_path.name}: {dat_size} bytes ({relation} entry sum)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tab", type=Path)
    parser.add_argument("dat", type=Path, nargs="?")
    args = parser.parse_args()
    audit(args.tab, args.dat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
