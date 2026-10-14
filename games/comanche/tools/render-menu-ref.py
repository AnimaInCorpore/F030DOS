#!/usr/bin/env python3
"""The oracle for src/menu.s: the DOS text engine at 00027034, in Python.

Written from the disassembly rather than from the 68k, so a mistake shared by
both would have to be made twice. It emits the exact set of pixel writes a
marked-up string produces, which is what a capture is checked against - the
background under menu text is the live flight view, so only the written
pixels can be compared.

  python3 tools/render-menu-ref.py --check release/f0.bin
  python3 tools/render-menu-ref.py --ascii

The font is read from the unpacked image, the same source the build generates
`menu_font_*` from.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

FLAT = Path("re/unpacked/comanche-flat32.bin")
FONT_BASE = 0x27276
BAR_STRING = 0x265C0
SCREEN_W, SCREEN_H = 320, 240
FONT_ROWS = 10
TAB = 6

# 0002AA85-0002ABCC, six-bit triples, as RGB565 - see src/inc/comanche.s.
WHITE = 0xFFFF
RED = 0xFA08
GREEN = 0x47E8
BLUE = 0x461F
MAGENTA = 0xFA1F
ORANGE = 0xFC08
AMBER = 0xFF08
SHADOW = 0x0000

NAMED = {ord("r"): RED, ord("g"): GREEN, ord("b"): BLUE,
         ord("p"): MAGENTA, ord("y"): AMBER, ord("o"): ORANGE}
# 00027108's chain, codes 1..10 in order.
NUMBERED = [RED, MAGENTA, WHITE, BLUE, ORANGE, RED, MAGENTA, BLUE, ORANGE, RED]


class Font:
    def __init__(self, raw: bytes, base: int = FONT_BASE):
        if raw[base:base + 4] != b"KF4b":
            raise ValueError("no KF4b signature")
        self.raw = raw
        self.base = base
        self.height = raw[base + 4]
        self.width = list(raw[base + 8:base + 8 + 128])
        self.offset = list(struct.unpack_from("<128H", raw, base + 0x88))

    def columns(self, code: int):
        w = self.width[code]
        if not w:
            return []
        o = self.base + self.offset[code]
        return list(struct.unpack_from(f"<{w}I", self.raw, o))


def draw(font: Font, text: bytes, x: int, y: int, ink0: int = WHITE):
    """Return (writes, hotspots, end_x). writes is [(x, y, colour)] in the
    order the original makes them - a later write wins, as on the surface."""
    writes = []
    hotspots = []
    ink = ink0
    i = 0
    while i < len(text):
        b = text[i]
        i += 1
        if b in (0x00, 0xFF):
            break
        if b == 0xFC:
            continue
        if b == 0xFE:
            hotspots.append((x, y))
            continue
        if b == 0xFD:
            x += TAB
            continue
        if b == 0x7C:
            if i >= len(text):
                break
            ink = NAMED.get(text[i], WHITE)
            i += 1
            continue
        if 1 <= b <= 10:
            ink = NUMBERED[b - 1]
            continue
        for mask in font.columns(b):
            if 0 <= x < SCREEN_W:
                v = mask
                for r in range(FONT_ROWS):
                    if v & 1:
                        writes.append((x, y + r, ink))
                    v >>= 1
                    if v & 1:
                        writes.append((x, y + r, SHADOW))
                    v >>= 1
            x += 1
    return writes, hotspots, x


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", type=Path, default=FLAT)
    ap.add_argument("--string", type=lambda s: int(s, 0), default=BAR_STRING)
    ap.add_argument("--x", type=int, default=4)
    ap.add_argument("--y", type=int, default=3)
    ap.add_argument("--check", type=Path, help="a 320x240 RGB565 frame dump")
    ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--ink", type=lambda s: int(s, 0), default=WHITE,
                    help="the colour in force on entry. 00026F97 sets green "
                         "once before a panel's whole group, so every line "
                         "after the first inherits whatever the last colour "
                         "code left - only the first line of Game carries |g")
    args = ap.parse_args()

    if not args.flat.is_file():
        print(f"{args.flat} absent", file=sys.stderr)
        return 2
    raw = args.flat.read_bytes()
    font = Font(raw)
    end = raw.index(b"\xff", args.string)
    text = raw[args.string:end]
    writes, hotspots, endx = draw(font, text, args.x, args.y, args.ink)
    print(f"string {args.string:08X}: {len(text)} bytes, {len(writes)} pixel writes, "
          f"pen {args.x} -> {endx}, {len(hotspots)} hotspots at "
          + ", ".join(f"({hx},{hy})" for hx, hy in hotspots))

    if args.ascii:
        grid = [[" "] * (endx + 2) for _ in range(args.y + FONT_ROWS + 1)]
        for x, y, c in writes:
            grid[y][x] = "#" if c != SHADOW else "."
        print("\n".join("".join(r) for r in grid))

    if args.check:
        d = args.check.read_bytes()

        def got(x, y):
            return struct.unpack_from(">H", d, (y * SCREEN_W + x) * 2)[0]

        # A later write wins, exactly as on the surface.
        final = {}
        for x, y, c in writes:
            final[(x, y)] = c
        bad = [(x, y, c, got(x, y)) for (x, y), c in sorted(final.items())
               if got(x, y) != c]
        print(f"checked {len(final)} pixels against {args.check}: "
              f"{len(bad)} differ")
        for x, y, want, have in bad[:12]:
            print(f"  ({x},{y}) want {want:04X} have {have:04X}")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
