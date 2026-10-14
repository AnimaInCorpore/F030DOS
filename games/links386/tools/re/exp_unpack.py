#!/usr/bin/env python3
"""Expand a Phar Lap P3 load image packed with the linker -pack option."""

from __future__ import annotations

import argparse
from pathlib import Path

from p3info import parse


def expand_packed(stream: bytes, expected_size: int) -> bytes:
    """Decode Phar Lap's simple P3 run/pattern encoding."""

    source = memoryview(stream)
    pos = 0
    output = bytearray()
    while pos < len(source):
        if pos + 2 > len(source):
            raise ValueError(f"truncated count word at packed offset 0x{pos:X}")
        count = int.from_bytes(source[pos : pos + 2], "little")
        pos += 2
        repeated = bool(count & 0x8000)
        count &= 0x7FFF
        if count == 0:
            raise ValueError(f"zero-length token at packed offset 0x{pos - 2:X}")

        if not repeated:
            end = pos + count
            if end > len(source):
                raise ValueError(
                    f"literal token overruns packed image at 0x{pos - 2:X}"
                )
            output.extend(source[pos:end])
            pos = end
            continue

        if pos >= len(source):
            raise ValueError(f"missing pattern length at packed offset 0x{pos - 2:X}")
        pattern_size = source[pos]
        pos += 1
        if pattern_size == 0:
            output.extend(b"\x00" * count)
            continue

        end = pos + pattern_size
        if end > len(source):
            raise ValueError(
                f"pattern token overruns packed image at 0x{pos - 3:X}"
            )
        pattern = bytes(source[pos:end])
        pos = end
        repeats, remainder = divmod(count, pattern_size)
        output.extend(pattern * repeats)
        output.extend(pattern[:remainder])

        if len(output) > expected_size:
            raise ValueError(
                f"expanded image exceeds declared size 0x{expected_size:X}"
            )

    if len(output) != expected_size:
        raise ValueError(
            f"expanded image is 0x{len(output):X} bytes, "
            f"expected 0x{expected_size:X}"
        )
    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = args.executable.read_bytes()
    values = parse(data, args.offset)
    if values["signature"] != b"P3":
        raise ValueError("this helper currently accepts P3 records only")

    load_start = args.offset + int(values["load_offset"])
    load_end = load_start + int(values["load_size"])
    packed = data[load_start:load_end]
    expanded_size = int(values["memory_requirements"])

    if int(values["flags"]) & 1:
        image = expand_packed(packed, expanded_size)
        mode = "packed"
    else:
        image = packed
        if len(image) != expanded_size:
            raise ValueError(
                f"unpacked load image is 0x{len(image):X} bytes, "
                f"expected 0x{expanded_size:X}"
            )
        mode = "raw"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(image)
    entry = int(values["initial_eip"])
    entry_bytes = image[entry : entry + 16]
    print(f"{args.executable}: P3 @ 0x{args.offset:X}")
    print(f"  mode                 {mode}")
    print(f"  packed load size     0x{len(packed):X}")
    print(f"  expanded image size  0x{len(image):X}")
    print(f"  initial EIP          0x{entry:X}")
    print(f"  entry bytes          {entry_bytes.hex(' ')}")
    print(f"  wrote                {args.output}")


if __name__ == "__main__":
    main()
