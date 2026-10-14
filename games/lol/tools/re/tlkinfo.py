#!/usr/bin/env python3
"""Inspect Lands of Lore TLK archives and their embedded VOC streams."""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


VOC_SIGNATURE = b"Creative Voice File\x1A"


@dataclass(frozen=True)
class TlkEntry:
    name: str
    start: int
    end: int
    voc_blocks: int
    block_types: tuple[tuple[int, int], ...]


def parse_voc(data: bytes) -> tuple[int, Counter[int]]:
    """Validate a Creative Voice File chunk and return its block summary."""
    if len(data) < 0x1A or not data.startswith(VOC_SIGNATURE):
        raise ValueError("TLK chunk does not start with a Creative Voice File header")
    data_offset, version, checksum = struct.unpack_from("<HHH", data, 0x14)
    if data_offset != 0x1A:
        raise ValueError(f"unexpected VOC data offset 0x{data_offset:X}")
    if version == 0 or checksum == 0:
        raise ValueError("VOC version/checksum header is empty")

    counts: Counter[int] = Counter()
    pos = data_offset
    while pos < len(data):
        block_type = data[pos]
        pos += 1
        if block_type == 0:
            if pos != len(data):
                raise ValueError("VOC terminator is not the final byte")
            return sum(counts.values()), counts
        if pos + 3 > len(data):
            raise ValueError("VOC block length is truncated")
        block_size = data[pos] | (data[pos + 1] << 8) | (data[pos + 2] << 16)
        pos += 3
        if pos + block_size > len(data):
            raise ValueError("VOC block extends past its TLK chunk")
        counts[block_type] += 1
        pos += block_size
    raise ValueError("VOC stream has no terminal block")


def parse_tlk(data: bytes) -> tuple[int, list[TlkEntry], int]:
    """Parse a TLK directory and validate its contiguous VOC payloads."""
    if len(data) < 4:
        raise ValueError("TLK file is too small for its directory offset")
    directory_end = struct.unpack_from("<I", data)[0]
    if directory_end < 4 or directory_end > len(data):
        raise ValueError("TLK directory offset is outside the file")

    records: list[tuple[str, int]] = []
    pos = 4
    while pos < directory_end:
        name_end = data.find(b"\0", pos, directory_end)
        if name_end < 0:
            raise ValueError("TLK filename is not NUL-terminated")
        if name_end == pos:
            break
        name = data[pos:name_end].decode("ascii")
        pos = name_end + 1
        if pos + 4 > directory_end:
            raise ValueError("TLK entry endpoint is truncated")
        end = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        records.append((name, end))

    padding = data[pos:directory_end]
    if len(padding) != 5 or padding != b"\0" * 5:
        raise ValueError("TLK directory does not have its five zero padding bytes")
    if not records:
        raise ValueError("TLK directory has no entries")

    entries: list[TlkEntry] = []
    start = directory_end
    for name, end in records:
        if end <= start or end > len(data):
            raise ValueError(f"TLK endpoint 0x{end:X} is not increasing or is outside the file")
        block_count, block_types = parse_voc(data[start:end])
        entries.append((TlkEntry(name, start, end, block_count, tuple(sorted(block_types.items())))))
        start = end
    if start != len(data):
        raise ValueError("TLK endpoints do not partition the complete file")
    return directory_end, entries, len(padding)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--show", action="store_true", help="print every archive entry")
    args = parser.parse_args()
    try:
        data = args.path.read_bytes()
        directory_end, entries, padding = parse_tlk(data)
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")

    block_types = Counter()
    for entry in entries:
        block_types.update(dict(entry.block_types))
    print(f"{args.path}: {len(data)} bytes; directory=0x{directory_end:X}; entries={len(entries)}")
    print(f"  five-byte zero padding; payload partition=PASS; VOC blocks={sum(block_types.values())}; types={dict(sorted(block_types.items()))}")
    if args.show:
        for entry in entries:
            print(f"  0x{entry.start:08X}..0x{entry.end:08X} {entry.end - entry.start:7} {entry.name} VOC={entry.voc_blocks} blocks={dict(entry.block_types)}")


if __name__ == "__main__":
    main()
