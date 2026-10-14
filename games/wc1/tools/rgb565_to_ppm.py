#!/usr/bin/env python3
"""Convert one Falcon 320x200 big-endian RGB565 page to an RGB PPM."""

from pathlib import Path
import sys


WIDTH = 320
HEIGHT = 200
FRAME_BYTES = WIDTH * HEIGHT * 2


def expand(value: int, bits: int) -> int:
    maximum = (1 << bits) - 1
    return (value * 255 + maximum // 2) // maximum


def convert(frame_path: Path, output_path: Path) -> None:
    source = frame_path.read_bytes()
    if len(source) != FRAME_BYTES:
        raise ValueError(f"expected {FRAME_BYTES} display bytes, got {len(source)}")

    pixels = bytearray(WIDTH * HEIGHT * 3)
    write = 0
    for offset in range(0, len(source), 2):
        value = int.from_bytes(source[offset:offset + 2], "big")
        pixels[write] = expand((value >> 11) & 0x1F, 5)
        pixels[write + 1] = expand((value >> 5) & 0x3F, 6)
        pixels[write + 2] = expand(value & 0x1F, 5)
        write += 3
    output_path.write_bytes(
        f"P6\n{WIDTH} {HEIGHT}\n255\n".encode("ascii") + pixels)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: rgb565_to_ppm.py FRAME.BIN OUTPUT.PPM")
    convert(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
