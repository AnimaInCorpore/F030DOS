#!/usr/bin/env python3
"""Audit Magic Carpet's indexed TMAPS table and concatenated data blocks."""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path

from decompress_rnc import RncError, unpack


ENTRY_SIZE = 10


def audit(tab_path: Path, dat_path: Path) -> None:
    tab = tab_path.read_bytes()
    dat = dat_path.read_bytes()
    if len(tab) % ENTRY_SIZE:
        raise SystemExit(f"{tab_path}: table is not a multiple of 10 bytes")

    entries = list(struct.iter_unpack("<IIH", tab))
    if not entries or entries[-1][0] != 0 or entries[-1][1] != len(dat):
        raise SystemExit(f"{tab_path}: missing final zero-length EOF sentinel")
    if any(a[1] > b[1] for a, b in zip(entries, entries[1:])):
        raise SystemExit(f"{tab_path}: data offsets are not monotonic")

    formats: Counter[int] = Counter()
    rnc_blocks = 0
    raw_blocks = 0
    type2_grids = 0
    type2_sizes: Counter[tuple[int, int]] = Counter()
    type3_sizes: Counter[tuple[int, int]] = Counter()
    type2_mismatches: list[tuple[int, int, int, int, int]] = []

    for index, (expected_size, offset, table_tag) in enumerate(entries[:-1]):
        end = entries[index + 1][1]
        block = dat[offset:end]
        if block[:4] == b"RNC" + bytes([1]):
            try:
                decoded = unpack(block)
            except RncError as error:
                raise SystemExit(f"record {index}: {error}") from error
            rnc_blocks += 1
        else:
            decoded = block
            raw_blocks += 1

        if len(decoded) != expected_size:
            raise SystemExit(
                f"record {index}: table size {expected_size}, "
                f"decoded size {len(decoded)}"
            )
        if len(decoded) < 6:
            raise SystemExit(f"record {index}: missing six-byte map header")

        map_type, subtype, width, height = struct.unpack_from("<BBHH", decoded)
        formats[map_type] += 1
        if map_type == 2:
            if len(decoded) != 6 + width * height:
                type2_mismatches.append(
                    (index, len(decoded), width, height, len(decoded) - 6 - width * height)
                )
            else:
                type2_grids += 1
            type2_sizes[(width, height)] += 1
        elif map_type == 3:
            type3_sizes[(width, height)] += 1

    print(
        f"{tab_path.stem}: records={len(entries) - 1} table_bytes={len(tab)} "
        f"data_bytes={len(dat)} RNC={rnc_blocks} raw={raw_blocks} "
        f"types={dict(sorted(formats.items()))}"
    )
    print(
        f"  type 2 exact indexed grids={type2_grids}; "
        f"distinct dimensions={len(type2_sizes)}"
    )
    if type2_mismatches:
        print(
            f"  type 2 size exceptions={len(type2_mismatches)}; "
            f"examples={type2_mismatches[:4]}"
        )
    if type3_sizes:
        print(
            f"  type 3 records={sum(type3_sizes.values())}; "
            "payload grammar remains unresolved"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tab", type=Path)
    parser.add_argument("dat", type=Path)
    args = parser.parse_args()
    audit(args.tab, args.dat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
