#!/usr/bin/env python3
"""Render a Magic Carpet 320x200 indexed screen with its VGA palette."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


WIDTH, HEIGHT, PALETTE_BYTES = 320, 200, 768


def vga_to_rgb(value: int) -> int:
    """Scale a 6-bit VGA DAC component to an 8-bit image component."""
    if not 0 <= value <= 63:
        raise ValueError(f"palette component {value} is outside VGA's 0..63 range")
    return (value << 2) | (value >> 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("screen", type=Path)
    parser.add_argument("palette", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    pixels = args.screen.read_bytes()
    palette = args.palette.read_bytes()
    expected_pixels = WIDTH * HEIGHT
    if len(pixels) != expected_pixels:
        raise SystemExit(f"screen is {len(pixels)} bytes, expected {expected_pixels}")
    if len(palette) != PALETTE_BYTES:
        raise SystemExit(f"palette is {len(palette)} bytes, expected {PALETTE_BYTES}")
    if max(palette) > 63:
        raise SystemExit("palette contains a component above the 6-bit VGA range")

    rgb_palette = []
    for red, green, blue in zip(palette[0::3], palette[1::3], palette[2::3]):
        rgb_palette.extend((vga_to_rgb(red), vga_to_rgb(green),
                            vga_to_rgb(blue)))

    image = Image.frombytes("P", (WIDTH, HEIGHT), pixels)
    image.putpalette(rgb_palette)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(f"{args.screen}: {WIDTH}x{HEIGHT} indexed pixels")
    print(f"{args.palette}: 256 RGB triplets, 6-bit VGA components")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
