#!/usr/bin/env python3
"""Render a raw indexed tile collection as a contact sheet."""

from __future__ import annotations

import argparse
import math
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
    parser.add_argument("tile_width", type=int)
    parser.add_argument("tile_height", type=int)
    parser.add_argument("columns", type=int)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    data = args.pixels.read_bytes()
    tile_size = args.tile_width * args.tile_height
    if tile_size <= 0 or len(data) % tile_size:
        raise SystemExit("pixel data is not an integral number of requested tiles")
    palette = args.palette.read_bytes()
    if len(palette) != 768:
        raise SystemExit(f"palette is {len(palette)} bytes, expected 768")
    if args.columns <= 0:
        raise SystemExit("columns must be positive")

    tile_count = len(data) // tile_size
    rows = math.ceil(tile_count / args.columns)
    image = Image.new("P", (args.columns * args.tile_width, rows * args.tile_height))
    rgb_palette: list[int] = []
    for red, green, blue in zip(palette[0::3], palette[1::3], palette[2::3]):
        rgb_palette.extend((vga_to_rgb(red), vga_to_rgb(green), vga_to_rgb(blue)))
    image.putpalette(rgb_palette)

    for index in range(tile_count):
        tile = Image.frombytes(
            "P", (args.tile_width, args.tile_height),
            data[index * tile_size:(index + 1) * tile_size],
        )
        tile.putpalette(rgb_palette)
        x = (index % args.columns) * args.tile_width
        y = (index // args.columns) * args.tile_height
        image.paste(tile, (x, y))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(f"{args.pixels}: {tile_count} {args.tile_width}x{args.tile_height} tiles")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
