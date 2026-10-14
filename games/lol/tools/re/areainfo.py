#!/usr/bin/env python3
"""Validate LoL area VCN tile stores and VMP tile-index tables."""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path

from pakinfo import decode_frame4, parse_pak


@dataclass(frozen=True)
class AreaInfo:
    pak: str
    name: str
    tiles: int
    vmp_entries: int
    min_reference: int
    max_reference: int


def decode_resource(data: bytes) -> bytes:
    if len(data) < 10:
        raise ValueError("area resource header is truncated")
    file_size, compression, decoded_size, palette_size = struct.unpack_from("<HHIH", data)
    if file_size + 2 != len(data) or compression != 4 or palette_size != 0:
        raise ValueError("area resource is not a palette-free Frame4 stream")
    decoded = decode_frame4(data[10:], decoded_size)
    if len(decoded) != decoded_size:
        raise ValueError("area Frame4 payload did not decode to its declared size")
    return decoded


def parse_vcn(data: bytes) -> int:
    if len(data) < 2:
        raise ValueError("VCN data is too small")
    tile_count = struct.unpack_from("<H", data)[0]
    expected = 2 + tile_count + 128 + 384 + tile_count * 32
    if expected != len(data):
        raise ValueError("VCN is not an exact 4bpp tile store")
    return tile_count


def parse_vmp(data: bytes, tile_count: int) -> tuple[int, int, int]:
    if len(data) < 2:
        raise ValueError("VMP data is too small")
    entry_count = struct.unpack_from("<H", data)[0]
    expected = 2 + entry_count * 2
    if expected != len(data):
        raise ValueError("VMP entry count does not match its data size")
    values = struct.unpack_from(f"<{entry_count}H", data, 2)
    references = [value & 0x3FFF for value in values]
    if any(reference >= tile_count for reference in references):
        raise ValueError("VMP references a tile outside its VCN")
    return entry_count, min(references), max(references)


def inspect_pak(path: Path) -> list[AreaInfo]:
    data = path.read_bytes()
    entries, _ = parse_pak(data)
    by_name = {entry.name.upper(): entry for entry in entries}
    result = []
    for vcn_entry in entries:
        if not vcn_entry.name.upper().endswith(".VCN"):
            continue
        stem = vcn_entry.name[:-4].upper()
        vmp_entry = by_name.get(stem + ".VMP")
        if vmp_entry is None:
            raise ValueError(f"{path.name}: missing {stem}.VMP")
        vcn = decode_resource(data[vcn_entry.offset:vcn_entry.offset + vcn_entry.size])
        vmp = decode_resource(data[vmp_entry.offset:vmp_entry.offset + vmp_entry.size])
        tile_count = parse_vcn(vcn)
        entry_count, minimum, maximum = parse_vmp(vmp, tile_count)
        result.append(AreaInfo(path.name, stem, tile_count, entry_count, minimum, maximum))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="an area PAK or DATA directory")
    args = parser.parse_args()
    paths = sorted(args.path.glob("*.PAK")) if args.path.is_dir() else [args.path]
    try:
        results = [info for path in paths for info in inspect_pak(path)]
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")
    for info in results:
        print(f"{info.pak}:{info.name}: VCN tiles={info.tiles}; VMP entries={info.vmp_entries}; refs={info.min_reference}..{info.max_reference}; invariant=PASS")
    print(f"validated {len(results)} VCN/VMP pairs")


if __name__ == "__main__":
    main()
