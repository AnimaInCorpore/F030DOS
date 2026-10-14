#!/usr/bin/env python3
"""Inspect and render Westwood Studios v3 bitmap fonts."""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Font:
    raw: bytes
    size: int
    compression: int
    blocks: int
    info_offset: int
    offset_offset: int
    width_offset: int
    data_offset: int
    height_offset: int
    count: int
    offsets: list[int]
    widths: list[int]
    y_offsets: list[int]
    heights: list[int]


def from_pak(path: Path, entry_name: str) -> bytes:
    from pakinfo import parse_pak

    raw = path.read_bytes()
    entries, _ = parse_pak(raw)
    wanted = entry_name.upper()
    for entry in entries:
        if entry.name.upper() == wanted:
            return raw[entry.offset:entry.offset + entry.size]
    raise ValueError(f"PAK entry not found: {entry_name}")


def parse_font(raw: bytes) -> Font:
    if len(raw) < 0x14:
        raise ValueError("font header is truncated")
    size, = struct.unpack_from("<H", raw, 0)
    compression, blocks = raw[2:4]
    info_offset, offset_offset, width_offset, data_offset, height_offset = struct.unpack_from(
        "<5H", raw, 4
    )
    if size != len(raw):
        raise ValueError(f"header size 0x{size:X} != payload size 0x{len(raw):X}")
    if compression != 0 or blocks != 5:
        raise ValueError(
            f"unsupported Westwood font header: compression={compression}, blocks={blocks}"
        )
    if offset_offset >= width_offset or (width_offset - offset_offset) % 2:
        raise ValueError("invalid glyph-offset array bounds")
    count = (width_offset - offset_offset) // 2
    if width_offset + count > len(raw) or height_offset + count * 2 > len(raw):
        raise ValueError("font index arrays exceed the file")
    offsets = [struct.unpack_from("<H", raw, offset_offset + index * 2)[0] for index in range(count)]
    widths = list(raw[width_offset:width_offset + count])
    y_offsets = [raw[height_offset + index * 2] for index in range(count)]
    heights = [raw[height_offset + index * 2 + 1] for index in range(count)]
    active_offsets = sorted(set(offset for offset in offsets if offset))
    for offset in active_offsets:
        next_offset = next(
            (candidate for candidate in active_offsets if candidate > offset),
            height_offset,
        )
        indices = [index for index, candidate in enumerate(offsets) if candidate == offset]
        expected_sizes = {
            ((widths[index] * 4 + 7) // 8) * heights[index] for index in indices
        }
        if next_offset - offset not in expected_sizes:
            raise ValueError(
                f"glyph data at 0x{offset:X} has size 0x{next_offset - offset:X}; "
                f"expected one of {sorted(expected_sizes)}"
            )
    return Font(
        raw,
        size,
        compression,
        blocks,
        info_offset,
        offset_offset,
        width_offset,
        data_offset,
        height_offset,
        count,
        offsets,
        widths,
        y_offsets,
        heights,
    )


def render(font: Font, output: Path, columns: int = 16, scale: int = 2) -> None:
    from PIL import Image, ImageDraw

    cell_width = max(font.widths, default=0) + 4
    cell_height = max(font.y_offsets[index] + font.heights[index] for index in range(font.count)) + 4
    label_height = 9
    image = Image.new(
        "L",
        (columns * cell_width, ((font.count + columns - 1) // columns) * (cell_height + label_height)),
        0,
    )
    draw = ImageDraw.Draw(image)
    for index, offset in enumerate(font.offsets):
        cell_x = (index % columns) * cell_width
        cell_y = (index // columns) * (cell_height + label_height)
        draw.text((cell_x, cell_y), f"{index:02X}", fill=128)
        if not offset or not font.widths[index] or not font.heights[index]:
            continue
        stride = (font.widths[index] * 4 + 7) // 8
        for row in range(font.heights[index]):
            row_start = offset + row * stride
            for column in range(font.widths[index]):
                value = font.raw[row_start + column // 2]
                nibble = value & 0x0F if column % 2 == 0 else value >> 4
                image.putpixel(
                    (cell_x + 2 + column, cell_y + label_height + font.y_offsets[index] + row),
                    nibble * 17,
                )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST).save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="standalone FNT or PAK file")
    parser.add_argument("--entry", help="PAK entry name when path is a PAK")
    parser.add_argument("--render", type=Path, metavar="PNG")
    args = parser.parse_args()
    raw = (
        from_pak(args.path, args.entry)
        if args.entry
        else args.path.read_bytes()
    )
    font = parse_font(raw)
    info = raw[font.info_offset:font.info_offset + 6]
    active = sum(offset != 0 for offset in font.offsets)
    unique = len(set(offset for offset in font.offsets if offset))
    print(f"{args.path}: {font.size} bytes")
    print(
        "  v3 header: "
        f"compression={font.compression}, blocks={font.blocks}, "
        f"info=0x{font.info_offset:X}, offsets=0x{font.offset_offset:X}, "
        f"widths=0x{font.width_offset:X}, data=0x{font.data_offset:X}, "
        f"heights=0x{font.height_offset:X}"
    )
    print(
        f"  glyphs={font.count}, active={active}, unique_data={unique}, "
        f"max_width={max(font.widths, default=0)}, "
        f"max_height={max(font.heights, default=0)}, info={info.hex(' ')}"
    )
    if args.render:
        render(font, args.render)
        print(f"  rendered: {args.render}")


if __name__ == "__main__":
    main()
