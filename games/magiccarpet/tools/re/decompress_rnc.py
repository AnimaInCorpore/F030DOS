#!/usr/bin/env python3
"""Decode the RNC1 resources used by Magic Carpet.

The game stores several small resources in Rob Northen Compression format.
This tool deliberately handles RNC1 only: it validates the 18-byte header,
the packed CRC, the unpacked CRC, and the declared output size before writing
the decoded bytes.
"""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path


class RncError(ValueError):
    """Raised when an RNC stream is malformed or fails verification."""


def crc16(data: bytes) -> int:
    """RNC's CRC-16/IBM variant, processed least-significant bit first."""

    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


@dataclass(frozen=True)
class RncHeader:
    unpacked_size: int
    packed_size: int
    unpacked_crc: int
    packed_crc: int
    flags: int
    chunks: int


def read_header(data: bytes) -> RncHeader:
    if len(data) < 18 or data[:4] != b"RNC\x01":
        raise RncError("not an RNC1 stream")
    _, unpacked_size, packed_size, unpacked_crc, packed_crc, flags = struct.unpack(
        ">IIIHHH", data[:18]
    )
    if 18 + packed_size != len(data):
        raise RncError(
            f"header declares {packed_size} packed bytes, "
            f"but file has {len(data) - 18}"
        )
    if crc16(data[18:]) != packed_crc:
        raise RncError(
            f"packed CRC mismatch: expected 0x{packed_crc:04X}, "
            f"got 0x{crc16(data[18:]):04X}"
        )
    return RncHeader(
        unpacked_size,
        packed_size,
        unpacked_crc,
        packed_crc,
        flags >> 8,
        flags & 0xFF,
    )


class BitStream:
    """RNC's little-endian bit reader with delayed raw-byte reads."""

    def __init__(self, data: bytes, start: int, end: int):
        self.data = data
        self.offset = start
        self.end = end
        self.bits = 0
        self.bits_on_buffer = 0

    def read_byte(self) -> int:
        if self.offset >= self.end:
            raise RncError("RNC byte stream ended early")
        byte = self.data[self.offset]
        self.offset += 1
        return byte

    def _fill(self) -> None:
        b1 = self.read_byte() if self.offset < self.end else 0
        b2 = self.read_byte() if self.offset < self.end else 0
        b3 = self.data[self.offset] if self.offset < self.end else 0
        b4 = self.data[self.offset + 1] if self.offset + 1 < self.end else 0
        self.bits = (b4 << 24) | (b3 << 16) | (b2 << 8) | b1
        self.bits_on_buffer = 16

    def read_bits(self, count: int) -> int:
        if not 0 <= count <= 16:
            raise RncError(f"invalid RNC bit count {count}")
        value = 0
        bit_value = 1
        for _ in range(count):
            if self.bits_on_buffer == 0:
                self._fill()
            if self.bits & 1:
                value |= bit_value
            self.bits >>= 1
            self.bits_on_buffer -= 1
            bit_value <<= 1
        return value

    def resync(self) -> None:
        """Refresh look-ahead bytes while preserving the remaining bit count."""

        remaining = self.bits & ((1 << self.bits_on_buffer) - 1)
        b0 = self.data[self.offset] if self.offset < self.end else 0
        b1 = self.data[self.offset + 1] if self.offset + 1 < self.end else 0
        b2 = self.data[self.offset + 2] if self.offset + 2 < self.end else 0
        self.bits = ((b2 << 16) | (b1 << 8) | b0) << self.bits_on_buffer
        self.bits |= remaining


@dataclass(frozen=True)
class HuffmanLeaf:
    code: int
    code_length: int
    value: int


def reverse_bits(value: int, count: int) -> int:
    result = 0
    for _ in range(count):
        result = (result << 1) | (value & 1)
        value >>= 1
    return result


def make_huffman(lengths: list[int]) -> list[HuffmanLeaf]:
    if not lengths or any(length > 16 for length in lengths):
        raise RncError("invalid RNC Huffman code lengths")
    counts = [0] * 17
    for length in lengths:
        if length:
            counts[length] += 1
    next_code = [0] * 17
    code = 0
    for length in range(1, 17):
        code = (code + counts[length - 1]) << 1
        next_code[length] = code
    leaves = []
    for value, length in enumerate(lengths):
        if length:
            leaves.append(HuffmanLeaf(
                reverse_bits(next_code[length], length), length, value
            ))
            next_code[length] += 1
    return leaves


def read_huffman_table(stream: BitStream) -> list[HuffmanLeaf]:
    count = stream.read_bits(5)
    if count > 18:
        raise RncError(f"invalid RNC Huffman table size {count}")
    # RNC permits an empty distance/length table when a chunk contains only
    # literal data.  Such a table is valid as long as it is never decoded.
    if count == 0:
        return []
    return make_huffman([stream.read_bits(4) for _ in range(count)])


def read_huffman_value(table: list[HuffmanLeaf], stream: BitStream) -> int:
    if not table:
        raise RncError("RNC Huffman value requested from an empty table")
    code = 0
    for length in range(1, 17):
        code |= stream.read_bits(1) << (length - 1)
        for leaf in table:
            if leaf.code_length == length and leaf.code == code:
                if leaf.value < 2:
                    return leaf.value
                extra = stream.read_bits(leaf.value - 1)
                return extra | (1 << (leaf.value - 1))
    raise RncError("RNC Huffman code did not match a table leaf")


def unpack(data: bytes) -> bytes:
    header = read_header(data)
    if header.chunks == 0:
        raise RncError("RNC stream declares no chunks")
    stream = BitStream(data, 18, len(data))
    stream.read_bits(2)
    output = bytearray()

    for _ in range(header.chunks):
        raw_table = read_huffman_table(stream)
        distance_table = read_huffman_table(stream)
        length_table = read_huffman_table(stream)
        tuple_count = stream.read_bits(16)
        if tuple_count == 0:
            raise RncError("RNC chunk declares no tuples")

        for tuple_index in range(tuple_count):
            raw_count = read_huffman_value(raw_table, stream)
            for _ in range(raw_count):
                output.append(stream.read_byte())
            if raw_count:
                stream.resync()

            if tuple_index + 1 != tuple_count:
                distance = read_huffman_value(distance_table, stream) + 1
                length = read_huffman_value(length_table, stream) + 2
                if distance > len(output):
                    raise RncError("RNC back-reference points before output")
                for _ in range(length):
                    output.append(output[-distance])

    if len(output) != header.unpacked_size:
        raise RncError(
            f"decoded {len(output)} bytes, expected {header.unpacked_size}"
        )
    result = bytes(output)
    if crc16(result) != header.unpacked_crc:
        raise RncError(
            f"unpacked CRC mismatch: expected 0x{header.unpacked_crc:04X}, "
            f"got 0x{crc16(result):04X}"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--out-dir", type=Path)
    args = parser.parse_args()

    for path in args.inputs:
        packed = path.read_bytes()
        raw = unpack(packed)
        header = read_header(packed)
        print(
            f"{path}: RNC1 packed={header.packed_size} "
            f"unpacked={header.unpacked_size} chunks={header.chunks} CRC=ok"
        )
        if args.out_dir:
            output = args.out_dir / f"{path.name}.raw"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(raw)
            print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
