#!/usr/bin/env python3
"""Normalize Magic Carpet's compact FLC animation resources."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


FLC_MAGIC = 0xAF12
FRAME_MAGIC = 0xF1FA


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def parse_records(data: bytes) -> tuple[int, int, int, list[bytes]]:
    if len(data) < 12:
        raise ValueError("file is shorter than the compact header")
    if read_u32(data, 0) != 12 or read_u16(data, 4) != FLC_MAGIC:
        raise ValueError("not a Magic Carpet compact FLC resource")

    declared_delta_frames = read_u16(data, 6)
    width = read_u16(data, 8)
    height = read_u16(data, 10)
    position = 12
    records: list[bytes] = []

    # The resource stores one initial full frame before the declared delta
    # count.  Each record's chunk sizes give a reliable end position.  The
    # initial record's size field is an exporter artifact and is ignored.
    for index in range(declared_delta_frames + 1):
        if position + 16 > len(data):
            raise ValueError(f"record {index}: truncated frame header")
        size = read_u32(data, position)
        magic = read_u16(data, position + 4)
        chunks = read_u16(data, position + 6)
        if magic != FRAME_MAGIC:
            raise ValueError(f"record {index}: bad frame magic {magic:#x}")

        chunk_position = position + 16
        for chunk_index in range(chunks):
            if chunk_position + 6 > len(data):
                raise ValueError(f"record {index}, chunk {chunk_index}: truncated header")
            chunk_size = read_u32(data, chunk_position)
            if chunk_size < 6 or chunk_position + chunk_size > len(data):
                raise ValueError(
                    f"record {index}, chunk {chunk_index}: invalid size {chunk_size}"
                )
            chunk_position += chunk_size

        actual_size = chunk_position - position
        record = bytearray(data[position:chunk_position])
        struct.pack_into("<I", record, 0, actual_size)
        records.append(bytes(record))
        if index > 0 and size != actual_size:
            raise ValueError(
                f"record {index}: stored size {size} differs from chunks {actual_size}"
            )
        position = chunk_position

    if position != len(data):
        raise ValueError(f"unconsumed tail: {len(data) - position} bytes")
    return width, height, declared_delta_frames + 1, records


def build_standard_flc(width: int, height: int, frame_count: int, records: list[bytes]) -> bytes:
    header = bytearray(128)
    struct.pack_into(
        "<IHHHHHHI",
        header,
        0,
        0,  # patched after records are appended
        FLC_MAGIC,
        frame_count,
        width,
        height,
        8,
        0,
        14,
    )
    payload = b"".join(records)
    struct.pack_into("<I", header, 0, len(header) + len(payload))
    return bytes(header) + payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    data = args.input.read_bytes()
    width, height, frame_count, records = parse_records(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build_standard_flc(width, height, frame_count, records))
    print(
        f"{args.input.name}: {width}x{height}, records={frame_count}, "
        f"input={len(data)}, output={args.output.stat().st_size}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
