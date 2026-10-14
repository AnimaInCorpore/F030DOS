#!/usr/bin/env python3
"""Audit a decompressed DAT/TAB pair using the game's row-RLE grammar."""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path


def decode_glyph(data: bytes, start: int, end: int, width: int,
                 height: int) -> tuple[bytearray, int]:
    """Decode the normal-mode row RLE used by the font drawing routine."""

    pixels = bytearray(width * height)
    position = start
    for row in range(height):
        column = 0
        while True:
            if position >= end:
                raise ValueError("glyph row stream ended before row terminator")
            token = data[position]
            position += 1
            if token == 0:
                break
            if token < 0x80:
                run = token
            else:
                column += 0x100 - token
                run = data[position] if position < end else 0
                position += 1
            if column + run > width:
                raise ValueError(
                    f"glyph run exceeds width: column {column}, run {run}, "
                    f"width {width}"
                )
            if position + run > end:
                raise ValueError("glyph literal run exceeds record")
            pixels[row * width + column:row * width + column + run] = \
                data[position:position + run]
            position += run
            column += run
    if position >= end or data[position] != 0x7F:
        raise ValueError("glyph record is missing its 0x7F terminator")
    return pixels, position


def audit(tab_path: Path, dat_path: Path) -> None:
    tab = tab_path.read_bytes()
    dat = dat_path.read_bytes()
    if len(tab) % 6:
        raise SystemExit(f"{tab_path}: {len(tab)} bytes is not a 6-byte table")

    entries = list(struct.iter_unpack("<IH", tab))
    declared = int.from_bytes(dat[:2], "little") if len(dat) >= 2 else -1
    if declared != len(entries):
        raise SystemExit(
            f"{tab_path}: DAT declares {declared} glyphs, "
            f"TAB contains {len(entries)} entries"
        )
    offsets = [offset for offset, _ in entries]
    if offsets[0] != 0 or any(a > b for a, b in zip(offsets, offsets[1:])):
        raise SystemExit(f"{tab_path}: offsets are not monotonic from zero")
    if offsets[-1] > len(dat):
        raise SystemExit(f"{tab_path}: final offset exceeds DAT size")

    widths = [dimensions & 0xFF for _, dimensions in entries[1:]]
    heights = [dimensions >> 8 for _, dimensions in entries[1:]]
    ends = offsets[2:] + [len(dat)]
    markers = 0
    literal_values = Counter()
    rendered_pixels = 0
    for index, (offset, dimensions) in enumerate(entries[1:], 1):
        end = ends[index - 1]
        width, height = dimensions & 0xFF, dimensions >> 8
        pixels, marker = decode_glyph(dat, offset, end, width, height)
        if marker + 1 != end:
            raise SystemExit(
                f"{tab_path}: glyph {index} has trailing bytes after 0x7F"
            )
        markers += 1
        literal_values.update(value for value in pixels if value)
        rendered_pixels += sum(value != 0 for value in pixels)
    payload_bytes = len(dat) - offsets[1]
    print(
        f"{tab_path.stem}: glyphs={declared} tab_bytes={len(tab)} "
        f"dat_bytes={len(dat)} payload_start=0x{offsets[1]:X} "
        f"payload_bytes={payload_bytes}"
    )
    print(
        f"  dimensions: width={min(widths)}..{max(widths)} "
        f"height={min(heights)}..{max(heights)}; "
        f"0x7F record markers={markers}/{len(entries) - 1}; "
        f"decoded pixels={rendered_pixels}; "
        f"literal values={','.join(f'0x{x:02X}' for x in sorted(literal_values))}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pairs", nargs=2, type=Path, metavar=("TAB_RAW", "DAT_RAW"))
    args = parser.parse_args()
    audit(*args.pairs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
