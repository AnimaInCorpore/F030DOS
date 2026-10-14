#!/usr/bin/env python3
"""Validate the CMZ/WLL geometry resources in Lands of Lore level PAKs."""

from __future__ import annotations

import argparse
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from pakinfo import decode_frame4, parse_pak


@dataclass(frozen=True)
class CmzInfo:
    compressed_size: int
    decompressed_size: int
    bytes_per_block: int
    wall_types: int


@dataclass(frozen=True)
class WllInfo:
    shape_index: int
    records: int
    wall_types: int
    vmp_min: int
    vmp_max: int


def parse_cmz(data: bytes) -> CmzInfo:
    if len(data) < 10:
        raise ValueError("CMZ header is truncated")
    file_size, compression, decoded_size, palette_size = struct.unpack_from("<HHIH", data)
    if file_size + 2 != len(data):
        raise ValueError("CMZ file-size field does not match the entry")
    if compression != 4 or palette_size != 0:
        raise ValueError("CMZ is not a Frame4 stream without a palette")
    decoded = decode_frame4(data[10:], decoded_size)
    if len(decoded) != decoded_size or decoded_size < 6:
        raise ValueError("CMZ Frame4 payload did not decode to its declared size")
    bytes_per_block = struct.unpack_from("<H", decoded, 4)[0]
    expected_size = 6 + 1024 * bytes_per_block
    if bytes_per_block not in (4, 9) or expected_size != len(decoded):
        raise ValueError("CMZ does not contain 1024 blocks of 4 or 9 bytes")
    wall_bytes = decoded[6:6 + 1024 * 4]
    return CmzInfo(len(data), len(decoded), bytes_per_block, len(set(wall_bytes)))


def parse_wll(data: bytes) -> WllInfo:
    if len(data) < 2 or (len(data) - 2) % 12:
        raise ValueError("WLL does not contain a 2-byte header plus 12-byte records")
    shape_index = struct.unpack_from("<H", data)[0]
    records = (len(data) - 2) // 12
    wall_types = set()
    vmp_values = []
    for index in range(records):
        offset = 2 + index * 12
        wall_types.add(struct.unpack_from("<H", data, offset)[0])
        vmp_values.append(data[offset + 2])
    if any(value > 6 for value in vmp_values):
        raise ValueError("WLL contains a VMP page outside 0..6")
    return WllInfo(shape_index, records, len(wall_types), min(vmp_values), max(vmp_values))


def inspect_level(path: Path) -> tuple[int, CmzInfo, WllInfo]:
    match = re.fullmatch(r"L(\d{2})\.PAK", path.name.upper())
    if not match:
        raise ValueError(f"not an L##.PAK file: {path.name}")
    level = int(match.group(1))
    data = path.read_bytes()
    entries, _ = parse_pak(data)
    wanted = {f"LEVEL{level}.CMZ", f"LEVEL{level}.WLL"}
    selected = {entry.name.upper(): data[entry.offset:entry.offset + entry.size] for entry in entries if entry.name.upper() in wanted}
    if set(selected) != wanted:
        raise ValueError(f"{path.name} is missing CMZ/WLL geometry entries")
    return level, parse_cmz(selected[f"LEVEL{level}.CMZ"]), parse_wll(selected[f"LEVEL{level}.WLL"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="an L##.PAK or DATA directory")
    args = parser.parse_args()
    paths = sorted(args.path.glob("L??.PAK")) if args.path.is_dir() else [args.path]
    if not paths:
        raise SystemExit("error: no L##.PAK files found")
    try:
        results = [inspect_level(path) for path in paths]
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")
    for level, cmz, wll in results:
        print(f"L{level:02}: CMZ {cmz.compressed_size}->{cmz.decompressed_size} bytes, blocks=1024x{cmz.bytes_per_block}, wall_types={cmz.wall_types}; WLL shape={wll.shape_index}, records={wll.records}, wall_types={wll.wall_types}, VMP={wll.vmp_min}..{wll.vmp_max}")
    print(f"validated {len(results)} level geometry packages")


if __name__ == "__main__":
    main()
