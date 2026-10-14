#!/usr/bin/env python3
"""Audit a decompressed Magic Carpet level record."""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path


LEVEL_SIZE = 0x979C
HEADER_SIZE = 48
RESERVED_START = 0x30
ENTITY_START = 0x442
ENTITY_SIZE = 18
ENTITY_SLOTS = 2095
FOOTER_START = 0x9790


def audit(path: Path) -> None:
    data = path.read_bytes()
    if len(data) != LEVEL_SIZE:
        raise SystemExit(f"{path}: {len(data)} bytes, expected {LEVEL_SIZE}")
    if any(data[RESERVED_START:ENTITY_START]):
        raise SystemExit("reserved 0x30..0x441 block is not zero-filled")

    header = struct.unpack_from("<12I", data, 0)
    records = [
        struct.unpack_from("<9H", data, ENTITY_START + index * ENTITY_SIZE)
        for index in range(ENTITY_SLOTS)
    ]
    empty = sum(not any(record) for record in records)
    padding = sum(
        record[0] == 0 or record[0] in (0x100, 0x101)
        for record in records
        if any(record)
    )
    active = [
        record for record in records
        if any(record) and 0 < record[0] < 0x100
    ]
    footer = struct.unpack_from("<6H", data, FOOTER_START)

    print(
        f"{path.name}: bytes={len(data)} header={HEADER_SIZE} "
        f"reserved={ENTITY_START - RESERVED_START} "
        f"entities={ENTITY_SLOTS}x{ENTITY_SIZE} footer={len(data) - FOOTER_START}"
    )
    print(f"  GEN_MAP/header={header}")
    print(
        f"  active={len(active)} empty={empty} padding_or_zero_class={padding} "
        f"classes={dict(sorted(Counter(record[0] for record in active).items()))}"
    )
    print(f"  footer={footer}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", type=Path)
    args = parser.parse_args()
    audit(args.level)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
