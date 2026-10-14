#!/usr/bin/env python3
"""Audit the RTLink v1 segment directory embedded in FALCON3.EXE.

The RTLink v1 directory consists of 18-byte records in the resident MZ
image.  Each record points at a paragraph-aligned segment header in the
executable tail.  The header begins with that segment's relocation records;
the code/data block follows after the relocation list rounded to paragraphs.

This tool is deliberately an auditor, not a decoder or a rewriter.  It keeps
the original executable untouched and reports the invariants used to identify
the directory and its storage chain.
"""

from __future__ import annotations

import argparse
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path


RECORD_SIZE = 18


@dataclass
class Segment:
    index: int
    load_segment: int
    filename_offset: int
    header_offset: int
    flags: int
    unknown1: int
    relocations: int
    unknown2: int
    code_offset: int
    paragraphs: int
    declared_end: int
    stored_end: int


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def parse_mz(data: bytes) -> tuple[int, int, list[tuple[int, int]]]:
    if data[:2] != b"MZ":
        raise ValueError("not an MZ executable")
    header_size = u16(data, 8) * 16
    reloc_count = u16(data, 6)
    reloc_table = u16(data, 24)
    relocations = [
        (u16(data, reloc_table + i * 4),
         u16(data, reloc_table + i * 4 + 2))
        for i in range(reloc_count)
    ]
    return header_size, reloc_table, relocations


def parse_directory(data: bytes, directory_offset: int) -> list[Segment]:
    records: list[Segment] = []
    offset = directory_offset
    expected_index = 2
    while offset + RECORD_SIZE <= len(data):
        load_segment, filename_offset = struct.unpack_from("<HH", data, offset)
        file_paragraphs = int.from_bytes(data[offset + 4:offset + 7], "little")
        flags = data[offset + 7]
        unknown1, relocations, unknown2, index, paragraphs = struct.unpack_from(
            "<HHHHH", data, offset + 8
        )
        if index != expected_index:
            break
        header_offset = file_paragraphs * 16
        code_offset = header_offset + ((relocations + 3) // 4) * 16
        declared_end = code_offset + paragraphs * 16
        records.append(Segment(
            index=index,
            load_segment=load_segment,
            filename_offset=filename_offset,
            header_offset=header_offset,
            flags=flags,
            unknown1=unknown1,
            relocations=relocations,
            unknown2=unknown2,
            code_offset=code_offset,
            paragraphs=paragraphs,
            declared_end=declared_end,
            stored_end=min(declared_end, len(data)),
        ))
        offset += RECORD_SIZE
        expected_index += 1
    if len(records) < 5:
        raise ValueError(f"only {len(records)} consecutive RTLink records found")
    return records


def find_directory(data: bytes) -> int:
    """Find the longest run of 18-byte records numbered 2, 3, ... ."""
    candidates: list[tuple[int, int]] = []
    for offset in range(0, len(data) - RECORD_SIZE * 5):
        if u16(data, offset + 14) != 2:
            continue
        try:
            records = parse_directory(data, offset)
        except (struct.error, ValueError):
            continue
        if len(records) >= 5:
            candidates.append((len(records), offset))
    if not candidates:
        raise ValueError("no RTLink v1 segment directory found")
    return max(candidates)[1]


def rtlink_segment_start(
    data: bytes,
    header_size: int,
    relocations: list[tuple[int, int]],
    directory_offset: int,
) -> int:
    """Return the segment start used by filename offsets in the directory."""
    before = []
    for offset, segment in relocations:
        file_offset = header_size + (segment << 4) + offset
        if file_offset < directory_offset:
            before.append((file_offset, segment))
    if not before:
        raise ValueError("could not locate the RTLink segment anchor")
    return header_size + before[-1][1] * 16


def read_c_string(data: bytes, offset: int) -> str:
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError(f"unterminated string at 0x{offset:x}")
    return data[offset:end].decode("ascii", errors="replace")


def audit_relocations(data: bytes, segments: list[Segment]) -> tuple[int, int]:
    total = 0
    invalid = 0
    for segment in segments:
        for i in range(segment.relocations):
            offset = u16(data, segment.header_offset + i * 4)
            target_segment = u16(data, segment.header_offset + i * 4 + 2)
            total += 1
            if (offset == 0 and target_segment == 0xffff):
                continue
            if (offset == 0 and target_segment == 0):
                invalid += 1
            if target_segment < segment.load_segment:
                invalid += 1
    return total, invalid


def parse_thunks(data: bytes, filename_offset: int) -> tuple[int, int, int]:
    """Parse E8 / EA / offset / segment / zero-based-index thunk records."""
    position = data.find(b"\xe8", filename_offset)
    if position < 0:
        raise ValueError("no RTLink thunk list found after filename")
    start = position
    count = 0
    invalid = 0
    while position + 10 <= len(data) and data[position] == 0xE8:
        if data[position + 3] != 0xEA:
            break
        segment_index = u16(data, position + 8)
        if segment_index == 0:
            invalid += 1
        count += 1
        position += 10
        while position < len(data) and data[position] == 0:
            position += 1
    return start, position, count - invalid


def audit(path: Path, directory_offset: int | None) -> dict:
    data = path.read_bytes()
    header_size, reloc_table, mz_relocations = parse_mz(data)
    directory_offset = find_directory(data) if directory_offset is None else directory_offset
    segments = parse_directory(data, directory_offset)
    anchor = rtlink_segment_start(data, header_size, mz_relocations, directory_offset)
    filename_field_offset = anchor + segments[0].filename_offset
    # FALCON3's field points at a one-byte empty prefix immediately before
    # the stored name.  Preserve that measured field location in the JSON,
    # while resolving the actual C string for thunk-list discovery.
    filename_file_offset = filename_field_offset
    if data[filename_file_offset] == 0:
        filename_file_offset += 1
    filename = read_c_string(data, filename_file_offset)
    relocation_total, relocation_invalid = audit_relocations(data, segments)
    thunk_start, thunk_end, thunk_count = parse_thunks(data, filename_file_offset)

    chain_breaks = []
    for previous, current in zip(segments, segments[1:]):
        if previous.declared_end != current.header_offset:
            chain_breaks.append({
                "previous": previous.index,
                "previous_end": previous.declared_end,
                "current": current.index,
                "current_header": current.header_offset,
            })

    return {
        "file": str(path),
        "file_size": len(data),
        "mz_header_size": header_size,
        "mz_relocation_table": reloc_table,
        "directory_offset": directory_offset,
        "directory_size": len(segments) * RECORD_SIZE,
        "directory_end": directory_offset + len(segments) * RECORD_SIZE,
        "rtlink_segment_start": anchor,
        "filename_field_offset": filename_field_offset,
        "filename_file_offset": filename_file_offset,
        "filename": filename,
        "segment_count": len(segments),
        "first_segment": segments[0].index,
        "last_segment": segments[-1].index,
        "segment_relocation_total": relocation_total,
        "segment_relocation_invalid": relocation_invalid,
        "thunk_start": thunk_start,
        "thunk_end": thunk_end,
        "thunk_count": thunk_count,
        "declared_storage_start": segments[0].header_offset,
        "declared_storage_end": segments[-1].declared_end,
        "stored_storage_end": len(data),
        "declared_tail_shortfall": len(data) - segments[-1].declared_end,
        "chain_breaks": chain_breaks,
        "segments": [asdict(segment) for segment in segments],
    }


def print_report(result: dict) -> None:
    print(f"file: {result['file']} ({result['file_size']} bytes)")
    print(f"RTLink v1 directory: 0x{result['directory_offset']:x}"
          f"..0x{result['directory_end']:x}"
          f" ({result['segment_count']} records, 18 bytes each)")
    print(f"RTLink segment anchor: 0x{result['rtlink_segment_start']:x}")
    print(f"filename: {result['filename']!r}"
          f" at 0x{result['filename_file_offset']:x}")
    print(f"segment indices: {result['first_segment']}..{result['last_segment']}")
    print(f"segment relocations: {result['segment_relocation_total']}"
          f" ({result['segment_relocation_invalid']} invalid)")
    print(f"far-call thunks: {result['thunk_count']}"
          f" at 0x{result['thunk_start']:x}..0x{result['thunk_end']:x}")
    print(f"declared segment storage: 0x{result['declared_storage_start']:x}"
          f"..0x{result['declared_storage_end']:x}")
    print(f"stored file end: 0x{result['stored_storage_end']:x}"
          f" (declared end delta {result['declared_tail_shortfall']:+d})")
    print(f"chain breaks: {len(result['chain_breaks'])}")
    print()
    print("index loadseg header code size relocs declared-end")
    for segment in result["segments"]:
        print(f"{segment['index']:5d} {segment['load_segment']:07x}"
              f" {segment['header_offset']:07x} {segment['code_offset']:07x}"
              f" {segment['paragraphs'] * 16:5x} {segment['relocations']:6d}"
              f" {segment['declared_end']:07x}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=Path)
    parser.add_argument("--directory", type=lambda value: int(value, 0),
                        help="directory file offset; otherwise auto-detect")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit(args.exe, args.directory)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)


if __name__ == "__main__":
    main()
