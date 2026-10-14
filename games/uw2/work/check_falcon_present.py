#!/usr/bin/env python3
"""Check the Falcon RGB565 seam's host contract and assembled evidence.

The arithmetic here is deliberately the same integer rounding contract as the
browser's paletteToRgb565()/frameToRgb565() path in
browser/uw2-cutscene.js. It does not pretend to execute 68000 instructions;
the listing/map checks prove the declared CPU/toolchain artifact exists, while
the optional Hatari run is the execution gate for Ported/Verified status.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


WIDTH = 320
HEIGHT = 200
PIXELS = WIDTH * HEIGHT


def round_ratio(value: int, scale: int) -> int:
    return (value * scale + 31) // 63


def rgb565(r: int, g: int, b: int) -> int:
    return (round_ratio(r, 31) << 11) | (round_ratio(g, 63) << 5) | round_ratio(b, 31)


def smoke_palette() -> bytes:
    row = bytes((0, 0, 0, 1, 2, 3, 7, 13, 19, 15, 27, 39,
                 23, 31, 47, 31, 45, 55, 39, 53, 7, 63, 63, 63))
    return row * 32


def expected_frame() -> bytes:
    palette = smoke_palette()
    lut = bytearray()
    for index in range(256):
        offset = index * 3
        lut.extend(rgb565(palette[offset], palette[offset + 1], palette[offset + 2]).to_bytes(2, "big"))
    pixels = bytes(range(256)) * (PIXELS // 256)
    assert len(pixels) == PIXELS
    frame = bytearray()
    for index in pixels:
        frame.extend(lut[index * 2:index * 2 + 2])
    return bytes(frame)


def check_listing(path: Path) -> None:
    text = path.read_text()
    required = [
        "uw2_falcon_build_rgb565_lut",
        "uw2_falcon_present_rgb565",
        "mulu.w  #31",
        "divu.w  #63",
        "dbra",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise SystemExit(f"listing missing required evidence: {', '.join(missing)}")


def check_map(path: Path) -> None:
    text = path.read_text()
    for symbol in ("_main", "uw2_falcon_build_rgb565_lut", "uw2_falcon_present_rgb565", "falcon_smoke_frame"):
        if symbol not in text:
            raise SystemExit(f"link map missing symbol: {symbol}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listing", type=Path, required=True)
    ap.add_argument("--map", type=Path, required=True)
    ap.add_argument("--capture", type=Path,
                    help="Hatari/Falcon smoke frame to compare byte-for-byte")
    args = ap.parse_args()
    check_listing(args.listing)
    check_map(args.map)
    frame = expected_frame()
    print(f"Falcon host contract: PASS ({WIDTH}x{HEIGHT}, {len(frame)} bytes)")
    expected_hash = hashlib.sha256(frame).hexdigest()
    print(f"smoke frame SHA-256: {expected_hash}")
    print(f"assembled listing: {args.listing}")
    print(f"link map: {args.map}")
    if args.capture:
        captured = args.capture.read_bytes()
        if captured != frame:
            first = next((i for i, (a, b) in enumerate(zip(frame, captured)) if a != b), min(len(frame), len(captured)))
            raise SystemExit(
                f"Hatari smoke mismatch at byte {first}: "
                f"expected {len(frame)} B/{expected_hash}, "
                f"captured {len(captured)} B/{hashlib.sha256(captured).hexdigest()}"
            )
        print(f"Hatari smoke: PASS ({len(captured)} bytes byte-identical)")
    else:
        print("execution status: UNPROVEN until Hatari/Falcon reads the smoke symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
