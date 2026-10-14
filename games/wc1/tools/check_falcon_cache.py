#!/usr/bin/env python3
"""Validate the generated big-endian mission cache without target hardware."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from convert_data import build_mission_cache


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument(
        "--source", type=Path, metavar="WC1DATA",
        help="rebuild the cache from this DOS data and require byte equality",
    )
    args = parser.parse_args()
    data = args.cache.read_bytes()
    if len(data) < 64:
        raise SystemExit("cache is shorter than the Falcon header")
    fields = struct.unpack_from(">4s10H6I", data)
    magic = fields[0]
    version, header_size, missions, navs, objectives, ships = fields[1:7]
    header_record, nav_record, objective_record, ship_record = fields[7:11]
    header_offset, nav_offset, objective_offset, ship_offset, total_size, _crc = fields[11:]
    assert magic == b"WCF1"
    assert version == 1 and header_size == 64
    assert (missions, navs, objectives, ships) == (64, 16, 16, 32)
    assert (header_record, nav_record, objective_record, ship_record) == (24, 78, 64, 44)
    assert total_size == len(data)
    assert header_offset == 64
    assert nav_offset == header_offset + missions * header_record
    assert objective_offset == nav_offset + missions * navs * nav_record
    assert ship_offset == objective_offset + missions * objectives * objective_record
    assert total_size == ship_offset + missions * ships * ship_record

    if args.source is not None:
        assert data == build_mission_cache(args.source), \
            "cache differs from a complete fresh conversion of the DOS packet"

    # The initial campaign selection is series 1, mission 0 (index four).
    entry_nav, _home, player_ship = struct.unpack_from(">3h", data, header_offset + 4 * header_record)
    assert 0 <= entry_nav < navs and 0 <= player_ship < ships
    print(
        f"WC1 Falcon cache: {len(data)} bytes, mission 4 entry-nav={entry_nav} "
        f"player={player_ship}" + ("; source-equivalent" if args.source else "")
    )


if __name__ == "__main__":
    main()
