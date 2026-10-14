#!/usr/bin/env python3
"""Convert a legacy Falcon 320x200 8-plane page to an RGB PPM."""

from __future__ import annotations

from pathlib import Path
import sys


WIDTH = 320
HEIGHT = 200
PLANES = 8
CELL_PIXELS = 16
CELL_BYTES = PLANES * 2
ROW_BYTES = WIDTH
FRAME_BYTES = ROW_BYTES * HEIGHT


def palette_from_ilbm(path: Path) -> list[tuple[int, int, int]]:
    data = path.read_bytes()
    if data[:4] != b"FORM" or data[8:12] != b"ILBM":
        raise ValueError(f"{path} is not an ILBM FORM")
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset:offset + 4]
        length = int.from_bytes(data[offset + 4:offset + 8], "big")
        offset += 8
        if offset + length > len(data):
            raise ValueError("truncated ILBM chunk")
        if chunk_id == b"CMAP":
            colours = [(0, 0, 0)] * 256
            for index in range(min(256, length // 3)):
                base = offset + index * 3
                colours[index] = tuple(data[base:base + 3])
            return colours
        offset += length + (length & 1)
    raise ValueError("ILBM has no CMAP")


def convert(frame_path: Path, palette_path: Path, output_path: Path) -> None:
    source = frame_path.read_bytes()
    if len(source) != FRAME_BYTES:
        raise ValueError(f"expected {FRAME_BYTES} display bytes, got {len(source)}")
    palette = palette_from_ilbm(palette_path)
    pixels = bytearray(WIDTH * HEIGHT * 3)
    write = 0
    for row in range(HEIGHT):
        row_base = row * ROW_BYTES
        for cell in range(WIDTH // CELL_PIXELS):
            cell_base = row_base + cell * CELL_BYTES
            plane_words = [
                int.from_bytes(source[cell_base + plane * 2:
                                      cell_base + plane * 2 + 2], "big")
                for plane in range(PLANES)
            ]
            for pixel in range(CELL_PIXELS):
                mask = 0x8000 >> pixel
                index = sum((1 << plane) for plane, word in
                            enumerate(plane_words) if word & mask)
                red, green, blue = palette[index]
                pixels[write:write + 3] = bytes((red, green, blue))
                write += 3
    output_path.write_bytes(
        f"P6\n{WIDTH} {HEIGHT}\n255\n".encode("ascii") + pixels)


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: planar_to_ppm.py FRAME.BIN GAME.PAL OUTPUT.PPM")
    convert(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))


if __name__ == "__main__":
    main()
