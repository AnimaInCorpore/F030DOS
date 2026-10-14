#!/usr/bin/env python3
"""Build schema-aware big-endian Falcon caches from staged DOS WC1 data.

The original files mix strings, pixels, compressed streams, byte-sized state,
and little-endian scalar records.  A blanket byte swap would corrupt most of
them.  This tool converts only records whose complete DOS layout is known.
Its first cache is the campaign packet used at flight startup: every mission
is decompressed once on the host and written as aligned big-endian records for
direct 68030 access.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import zlib


MISSION_ARCHIVE_RECORD_ID = 16
MISSION_COUNT = 64
NAV_COUNT = 16
OBJECTIVE_COUNT = 16
SHIP_COUNT = 32

DOS_HEADER_SIZE = 0x18
DOS_NAV_SIZE = 0x4D
DOS_OBJECTIVE_SIZE = 0x40
DOS_SHIP_SIZE = 0x2A

FALCON_HEADER_SIZE = 0x18
FALCON_NAV_SIZE = 0x4E
FALCON_OBJECTIVE_SIZE = 0x40
FALCON_SHIP_SIZE = 0x2C
CACHE_HEADER_SIZE = 0x40

PACKET_OFFSET_MASK = 0x00FFFFFF
LZW_CLEAR_CODE = 0x100
LZW_STOP_CODE = 0x101
LZW_FIRST_CODE = 0x102
LZW_MAX_CODES = 0x1000


def read_lzw_code(source: bytes, bit_position: int, width: int) -> tuple[int, int]:
    if bit_position + width > len(source) * 8:
        raise ValueError("truncated Origin LZW stream")
    value = 0
    for bit in range(width):
        source_bit = bit_position + bit
        value |= ((source[source_bit >> 3] >> (source_bit & 7)) & 1) << bit
    return value, bit_position + width


def decode_origin_lzw(source: bytes, output_size: int) -> bytes:
    bit_position = 0
    code, bit_position = read_lzw_code(source, bit_position, 9)
    if code != LZW_CLEAR_CODE:
        raise ValueError("Origin LZW stream does not start with CLEAR")

    output = bytearray()
    while True:
        code_width = 9
        code_width_threshold = 1 << code_width
        dictionary = {value: bytes((value,)) for value in range(256)}
        dictionary_size = LZW_FIRST_CODE
        previous: bytes | None = None
        while True:
            code, bit_position = read_lzw_code(source, bit_position, code_width)
            if code == LZW_STOP_CODE:
                if len(output) != output_size:
                    raise ValueError(
                        f"Origin LZW size mismatch: {len(output)} != {output_size}"
                    )
                return bytes(output)
            if code == LZW_CLEAR_CODE:
                break
            if code in dictionary:
                word = dictionary[code]
            elif code == dictionary_size and previous is not None:
                word = previous + previous[:1]
            else:
                raise ValueError(f"invalid Origin LZW code {code}")
            output.extend(word)
            if len(output) > output_size:
                raise ValueError("Origin LZW output exceeds declared size")
            if previous is not None:
                if dictionary_size >= LZW_MAX_CODES:
                    raise ValueError("Origin LZW dictionary overflow")
                dictionary[dictionary_size] = previous + word[:1]
                dictionary_size += 1
                if dictionary_size == code_width_threshold and code_width < 12:
                    code_width += 1
                    code_width_threshold <<= 1
            previous = word


def decode_packet_sections(packet: bytes) -> list[bytes]:
    if len(packet) < 8:
        raise ValueError("packet is shorter than its header")
    declared_size, directory_entry = struct.unpack_from("<II", packet)
    directory_size = directory_entry & PACKET_OFFSET_MASK
    if declared_size != len(packet) or directory_size < 8 or directory_size % 4:
        raise ValueError("invalid packet header")
    section_count = directory_size // 4 - 1
    if section_count <= 0:
        raise ValueError("packet has no sections")

    sections: list[bytes] = []
    for section in range(section_count):
        entry = struct.unpack_from("<I", packet, 4 + section * 4)[0]
        next_entry = (
            struct.unpack_from("<I", packet, 8 + section * 4)[0]
            if section + 1 < section_count
            else declared_size
        )
        compression = entry >> 24
        offset = entry & PACKET_OFFSET_MASK
        end = next_entry & PACKET_OFFSET_MASK
        if offset < directory_size or end <= offset or end > declared_size:
            raise ValueError(f"invalid packet section {section}")
        encoded = packet[offset:end]
        if compression == 0:
            sections.append(encoded)
        elif compression == 1 and len(encoded) >= 4:
            output_size = struct.unpack_from("<I", encoded)[0]
            sections.append(decode_origin_lzw(encoded[4:], output_size))
        else:
            raise ValueError(f"unsupported packet compression {compression}")
    return sections


def find_mission_archive(data_dir: Path) -> Path:
    install = (data_dir / "INSTALL.DAT").read_bytes()
    for offset in range(0, len(install) - 15, 16):
        record = install[offset:offset + 16]
        if record[0] == 0:
            break
        if record[15] == MISSION_ARCHIVE_RECORD_ID:
            name = record[:13].split(b"\0", 1)[0].decode("ascii")
            if not name or "/" in name or "\\" in name:
                raise ValueError("unsafe mission archive name in INSTALL.DAT")
            return data_dir / name
    raise ValueError("MODULE.000 record was not found in INSTALL.DAT")


def expected_size(record_size: int, record_count: int) -> int:
    return record_size * record_count


def convert_header(record: bytes) -> bytes:
    return struct.pack(">12h", *struct.unpack("<12h", record))


def convert_nav(record: bytes) -> bytes:
    name = record[:30]
    nav_type = record[30]
    x, y, z = struct.unpack_from("<iii", record, 31)
    radius = struct.unpack_from("<H", record, 43)[0]
    triggers = record[45:53]
    preload_types = struct.unpack_from("<2h", record, 53)
    mission_ships = struct.unpack_from("<10h", record, 57)
    converted = struct.pack(
        ">30sBxiiiH8s2h10h",
        name,
        nav_type,
        x,
        y,
        z,
        radius,
        triggers,
        *preload_types,
        *mission_ships,
    )
    assert len(converted) == FALCON_NAV_SIZE
    return converted


def convert_objective(record: bytes) -> bytes:
    objective_type, index, description = struct.unpack("<hh60s", record)
    return struct.pack(">hh60s", objective_type, index, description)


def convert_ship(record: bytes) -> bytes:
    fields = struct.unpack("<hhbbhbiiihhhbhhhhhbbbb", record)
    converted = struct.pack(
        ">hhbbhbxiiihhhbxhhhhhbbbb",
        *fields,
    )
    assert len(converted) == FALCON_SHIP_SIZE
    return converted


def convert_records(section: bytes, source_size: int, destination_size: int,
                    count: int, convert) -> bytes:
    if len(section) != expected_size(source_size, count):
        raise ValueError(
            f"unexpected mission section size {len(section)}; expected "
            f"{expected_size(source_size, count)}"
        )
    output = bytearray(expected_size(destination_size, count))
    for index in range(count):
        source_offset = index * source_size
        destination_offset = index * destination_size
        output[destination_offset:destination_offset + destination_size] = convert(
            section[source_offset:source_offset + source_size]
        )
    return bytes(output)


def build_mission_cache(data_dir: Path) -> bytes:
    archive_path = find_mission_archive(data_dir)
    archive = archive_path.read_bytes()
    sections = decode_packet_sections(archive)
    if len(sections) < 4:
        raise ValueError("mission archive lacks sections 0-3")

    headers = convert_records(
        sections[0], DOS_HEADER_SIZE, FALCON_HEADER_SIZE, MISSION_COUNT,
        convert_header,
    )
    navs = convert_records(
        sections[1], DOS_NAV_SIZE, FALCON_NAV_SIZE, MISSION_COUNT * NAV_COUNT,
        convert_nav,
    )
    objectives = convert_records(
        sections[2], DOS_OBJECTIVE_SIZE, FALCON_OBJECTIVE_SIZE,
        MISSION_COUNT * OBJECTIVE_COUNT, convert_objective,
    )
    ships = convert_records(
        sections[3], DOS_SHIP_SIZE, FALCON_SHIP_SIZE,
        MISSION_COUNT * SHIP_COUNT, convert_ship,
    )

    header_offset = CACHE_HEADER_SIZE
    nav_offset = header_offset + len(headers)
    objective_offset = nav_offset + len(navs)
    ship_offset = objective_offset + len(objectives)
    total_size = ship_offset + len(ships)
    cache_header = struct.pack(
        ">4s10H6I",
        b"WCF1",
        1,
        CACHE_HEADER_SIZE,
        MISSION_COUNT,
        NAV_COUNT,
        OBJECTIVE_COUNT,
        SHIP_COUNT,
        FALCON_HEADER_SIZE,
        FALCON_NAV_SIZE,
        FALCON_OBJECTIVE_SIZE,
        FALCON_SHIP_SIZE,
        header_offset,
        nav_offset,
        objective_offset,
        ship_offset,
        total_size,
        zlib.crc32(archive) & 0xFFFFFFFF,
    )
    assert len(cache_header) == 48
    return cache_header.ljust(CACHE_HEADER_SIZE, b"\0") + headers + navs + objectives + ships


def write_if_changed(path: Path, contents: bytes) -> None:
    if path.is_file() and path.read_bytes() == contents:
        return
    path.write_bytes(contents)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="staged WC1DATA directory")
    parser.add_argument("destination", type=Path, help="generated WC1CACHE directory")
    args = parser.parse_args()

    cache = build_mission_cache(args.source)
    args.destination.mkdir(parents=True, exist_ok=True)
    output = args.destination / "MISSION.BIN"
    write_if_changed(output, cache)
    print(f"wrote {output} ({len(cache)} bytes; big-endian mission cache)")


if __name__ == "__main__":
    main()
