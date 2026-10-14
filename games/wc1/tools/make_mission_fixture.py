#!/usr/bin/env python3
"""Create a tiny, legal Origin-packet mission fixture for Falcon integration tests.

The fixture contains no retail WC1 data or art.  It has the exact byte layout
that LoadMissionData consumes: raw archive sections 0-3, 64 mission slots,
and one populated slot at series 1 / mission 0 (the Falcon boot default).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct


MISSION_INDEX = 4
HEADER_SIZE = 0x18
NAV_SIZE = 0x4D
OBJECTIVE_SIZE = 0x40
SHIP_SIZE = 0x2A
NAV_COUNT = 16
OBJECTIVE_COUNT = 16
SHIP_COUNT = 32
MISSION_COUNT = 64


def put_record(section: bytearray, stride: int, record_index: int, data: bytes) -> None:
    assert len(data) == stride
    start = record_index * stride
    section[start:start + stride] = data


def mission_header() -> bytes:
    return struct.pack("<12h", 0, 0, 0, 1, 2, 3, -1, -1, -1, -1, -1, 0)


def nav_record(name: str, nav_type: int, x: int, y: int, z: int, ships: list[int]) -> bytes:
    encoded_name = name.encode("ascii")[:30].ljust(30, b"\0")
    assert len(ships) == 10
    return struct.pack(
        "<30sbiiiH8s2h10h",
        encoded_name,
        nav_type,
        x,
        y,
        z,
        1024,
        b"\0" * 8,
        -1,
        -1,
        *ships,
    )


def ship_record(
    object_type: int,
    side: int,
    nav: int,
    x: int,
    y: int,
    z: int,
    yaw: int,
    speed: int,
) -> bytes:
    return struct.pack(
        "<hhbbhbiiihhhbhhhhhbbbb",
        object_type,
        side,
        -1,
        0,
        0,
        nav,
        x,
        y,
        z,
        0,
        yaw,
        0,
        0,
        speed,
        0,
        0,
        0,
        0,
        0,
        -1,
        -1,
        -1,
    )


def make_archive() -> bytes:
    header = bytearray(MISSION_COUNT * HEADER_SIZE)
    nav = bytearray(MISSION_COUNT * NAV_COUNT * NAV_SIZE)
    objective = bytearray(MISSION_COUNT * OBJECTIVE_COUNT * OBJECTIVE_SIZE)
    ships = bytearray(MISSION_COUNT * SHIP_COUNT * SHIP_SIZE)

    put_record(header, HEADER_SIZE, MISSION_INDEX, mission_header())

    nav_base = MISSION_INDEX * NAV_COUNT
    empty_ships = [-1] * 10
    put_record(nav, NAV_SIZE, nav_base, nav_record("FIXTURE NAV 1", 1, 0, 0, 0, [0, 1, 2, 3] + empty_ships[4:]))
    put_record(nav, NAV_SIZE, nav_base + 1, nav_record("FIXTURE NAV 2", 1, 0, 0, 0x00100000, empty_ships))

    objective_base = MISSION_INDEX * OBJECTIVE_COUNT
    put_record(objective, OBJECTIVE_SIZE, objective_base, struct.pack("<hh60s", 3, 1, b"FIXTURE OBJECTIVE".ljust(60, b"\0")))

    ship_base = MISSION_INDEX * SHIP_COUNT
    records = (
        ship_record(1, 0, 0, 0, 0, 0, 0, 6),
        ship_record(1, 0, 0, 0x00018000, 0, 0x00024000, 0, 6),
        ship_record(9, 1, 1, -0x00020000, 0, 0x000B0000, 128, 8),
        ship_record(10, 1, 1, 0x0001C000, 0, 0x000D0000, 192, 8),
    )
    for index, record in enumerate(records):
        put_record(ships, SHIP_SIZE, ship_base + index, record)

    sections = (bytes(header), bytes(nav), bytes(objective), bytes(ships))
    directory_size = (len(sections) + 1) * 4
    offsets: list[int] = []
    cursor = directory_size
    for section in sections:
        offsets.append(cursor)
        cursor += len(section)
    result = bytearray(struct.pack("<I", cursor))
    result.extend(b"".join(struct.pack("<I", offset) for offset in offsets))
    result.extend(b"".join(sections))
    assert len(result) == cursor
    return bytes(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, help="directory to receive WC1DATA")
    args = parser.parse_args()
    data_dir = args.output
    data_dir.mkdir(parents=True, exist_ok=True)

    install = bytearray()
    install.extend(b"MODULE.000".ljust(13, b"\0"))
    # The original DOS INSTALL.DAT record for MODULE.000 is ID 16. Its
    # runtime table is advanced by one, making it resource 15 to the DOS
    # campaign code; the Falcon scans the on-disk record directly.
    install.extend(bytes((1, 2, 16)))
    install.extend(b"\0" * 16)
    (data_dir / "INSTALL.DAT").write_bytes(install)
    (data_dir / "MODULE.000").write_bytes(make_archive())
    print(f"wrote raw mission fixture to {data_dir}")


if __name__ == "__main__":
    main()
