#!/usr/bin/env python3
"""Inspect the fixed-size BLEND palette lookup tables."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from pakinfo import parse_pak


TABLE_SIZE = 256 * 256
TRAILER = bytes.fromhex("E4 D5 02 00")


def parse_blend(data: bytes) -> tuple[int, str]:
    """Validate the 256x256 byte lookup-table shape."""
    if len(data) != TABLE_SIZE:
        raise ValueError(f"expected 0x10000 bytes, got 0x{len(data):X}")
    return len(set(data)), hashlib.sha256(data).hexdigest()


def cps_palette(cps: bytes, name: str) -> bytes:
    if len(cps) < 10:
        raise ValueError(f"{name}: CPS header is truncated")
    file_size, _compression, _pixel_size, palette_size = struct.unpack_from(
        "<HHIH", cps
    )
    if file_size + 2 != len(cps):
        raise ValueError(f"{name}: CPS size field does not match file size")
    if palette_size < 768 or len(cps) < 10 + palette_size:
        raise ValueError(f"{name}: no complete VGA palette")
    return cps[10 : 10 + 768]


def synthesize_table(palette: bytes) -> bytes:
    """Recreate the fixed 22/42 6-bit palette blend table.

    The arithmetic and nearest-colour tie rule mirror the DOS table witness:
    each channel is blended with ``>> 6`` truncation and the last palette
    index wins an equal squared-distance tie.
    """
    if len(palette) != 768:
        raise ValueError(f"expected 768 palette bytes, got {len(palette)}")
    colors = [palette[index : index + 3] for index in range(0, 768, 3)]
    output = bytearray(TABLE_SIZE)
    nearest_cache: dict[tuple[int, int, int], int] = {}
    pos = 0
    for foreground in colors:
        for background in colors:
            target = tuple(
                min(63, ((foreground[channel] * 22) >> 6) + ((background[channel] * 42) >> 6))
                for channel in range(3)
            )
            best_index = nearest_cache.get(target)
            if best_index is None:
                best_distance = 0x7FFF
                best_index = 0x101
                for index, color in enumerate(colors):
                    distance = sum(
                        (target[channel] - color[channel]) ** 2 for channel in range(3)
                    )
                    if distance <= best_distance:
                        best_distance = distance
                        best_index = index
                nearest_cache[target] = best_index
            output[pos] = best_index
            pos += 1
    return bytes(output)


def check_finale_tables(path: Path) -> None:
    """Prove both shipped tables against their finale CPS palette witnesses."""
    data = path.read_bytes()
    entries, _ = parse_pak(data)
    by_name = {entry.name.upper(): entry for entry in entries}
    for table_name, palette_name in (
        ("BLEND.TAB", "RETURN.CPS"),
        ("BLEND2.TAB", "EYE2.CPS"),
    ):
        table_path = path.parent / table_name
        if not table_path.exists():
            raise ValueError(f"palette witness directory has no {table_name}")
        entry = by_name.get(palette_name)
        if entry is None:
            raise ValueError(f"PAK entry not found: {palette_name}")
        palette = cps_palette(data[entry.offset : entry.offset + entry.size], palette_name)
        expected = synthesize_table(palette)
        actual = table_path.read_bytes()
        if actual != expected[:-4] + TRAILER:
            mismatches = sum(a != b for a, b in zip(actual, expected[:-4] + TRAILER))
            raise ValueError(f"{table_name}: {mismatches} bytes differ from the witness")
        print(
            f"  {table_name}: palette={palette_name}; weights=22/42; "
            f"formula=PASS; trailer={TRAILER.hex().upper()}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--check-finale",
        type=Path,
        metavar="FINALE1.PAK",
        help="also prove BLEND.TAB and BLEND2.TAB from finale CPS palettes",
    )
    args = parser.parse_args()
    try:
        data = args.path.read_bytes()
        unique, digest = parse_blend(data)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"error: {exc}")
    print(f"{args.path}: {len(data)} bytes; shape=256x256 bytes; unique={unique}; sha256={digest}; invariant=PASS")
    if args.check_finale:
        try:
            check_finale_tables(args.check_finale)
        except (OSError, ValueError, struct.error) as exc:
            raise SystemExit(f"error: {exc}")


if __name__ == "__main__":
    main()
