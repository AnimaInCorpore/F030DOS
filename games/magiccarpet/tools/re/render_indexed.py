#!/usr/bin/env python3
"""Render an arbitrary-size indexed image with a 256-entry VGA palette."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def vga_to_rgb(value: int) -> int:
    if not 0 <= value <= 63:
        raise ValueError(f"palette component {value} is outside VGA's 0..63 range")
    return (value << 2) | (value >> 4)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pixels", type=Path)
    parser.add_argument("palette", type=Path)
    parser.add_argument("width", type=int)
    parser.add_argument("height", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    pixels = args.pixels.read_bytes()
    palette = args.palette.read_bytes()
    expected_pixels = args.width * args.height
    if len(pixels) != expected_pixels:
        raise SystemExit(
            f"pixel data is {len(pixels)} bytes, expected {expected_pixels}"
        )
    if len(palette) != 768:
        raise SystemExit(f"palette is {len(palette)} bytes, expected 768")

    rgb_palette: list[int] = []
    for red, green, blue in zip(palette[0::3], palette[1::3], palette[2::3]):
        rgb_palette.extend((vga_to_rgb(red), vga_to_rgb(green), vga_to_rgb(blue)))

    image = Image.frombytes("P", (args.width, args.height), pixels)
    image.putpalette(rgb_palette)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(f"{args.pixels}: {args.width}x{args.height} indexed pixels")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
