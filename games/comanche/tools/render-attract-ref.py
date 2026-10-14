#!/usr/bin/env python3
"""Render the attract screens straight from the installed assets.

The oracle for src/attract.s. Everything the Falcon shows during the attract
cycle comes from three Kyle DTA screens and two RLE sprite banks; if a capture
disagrees with what this script draws from the same bytes, the port's decoder,
palette or placement is wrong, and the difference says which.

The DTA screens carry their palette inside the same RLE stream as the pixels:
128-byte header (width-1 and height-1 as words at +8 and +10), the run-length
payload, then a 0x0C tag and 256 six-bit RGB triples. That is the format
attract_show_image implements, written here independently so a shared mistake
cannot hide.

  python3 tools/render-attract-ref.py --outdir build/ref

Reads assets/extracted/comanche_hdd by default.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

DEFAULT_ROOT = Path("assets/extracted/comanche_hdd")


# --------------------------------------------------------------------------
# Kyle DTA screens
# --------------------------------------------------------------------------

def rle_unpack(src: bytes, want: int) -> bytearray:
    """Token < 0xC0 is a literal; otherwise (token & 0x3F) copies of the next
    byte. A zero-length run is a no-op, not a terminator."""
    out = bytearray()
    i = 0
    while len(out) < want and i < len(src):
        tok = src[i]
        i += 1
        if tok < 0xC0:
            out.append(tok)
            continue
        n = tok & 0x3F
        if n == 0:
            continue
        out.extend(bytes([src[i]]) * n)
        i += 1
    return out


def load_dta(path: Path):
    """The payload is run-length encoded; the palette behind it is NOT.

    The 0x0C marker and its 256 RGB triples sit raw in the last 769 bytes of
    the file. This function used to unpack w*h+769 bytes through rle_unpack
    and read the palette out of the result, which turns every component of
    0xC0 or more into a run token and shifts the rest of the table down.
    src/attract.s made the same assumption, so the two agreed with each other
    and the agreement meant nothing - the whole point of writing this from the
    disassembly was that a shared mistake would have to be made twice, and it
    was. BACK.DTA carries such a byte in entry 1, so its palette was wrong from
    the second colour on and its logo rendered in horizontal bands.

    Reading the tail raw reproduces the frame COMANCHE.EXE draws of itself at
    zero differing pixels of 76,800 - see tools/oracle-capture.sh.
    """
    raw = path.read_bytes()
    w = struct.unpack_from("<H", raw, 8)[0] + 1
    h = struct.unpack_from("<H", raw, 10)[0] + 1
    pixels = bytes(rle_unpack(raw[128:-769], w * h)[: w * h])
    pal = None
    if raw[-769] == 0x0C:
        tail = raw[-768:]
        pal = [tuple(tail[i * 3 : i * 3 + 3]) for i in range(256)]
    return w, h, pixels, pal


# --------------------------------------------------------------------------
# KRL sprite banks
# --------------------------------------------------------------------------

def krl_unpack(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw[:4] not in (b"KRL1", b"KRL0"):
        raise ValueError(f"{path}: not a KRL container")
    size = struct.unpack_from("<I", raw, 4)[0]
    return bytes(rle_unpack(raw[8:], size))


class Bank:
    """'SG' directory: count at +2, palette offset at +4, then 8-byte records
    of width, height, signed x and y origin, and a dword data offset.

    The DOS blitter at 00025880 consumes a row as four plane chunks of
    width/4 bytes and walks the destination UPWARD, so a frame is stored
    bottom row first, and within a row the pixels of each plane in turn.
    """

    def __init__(self, data: bytes):
        self.data = data
        if data[:2] != b"SG":
            raise ValueError("not an SG bank")
        self.count = struct.unpack_from("<H", data, 2)[0]
        self.pal_off = struct.unpack_from("<I", data, 4)[0]
        self.pal = None
        if data[self.pal_off] == 0x0C:
            p = self.pal_off + 1
            self.pal = [tuple(data[p + i * 3 : p + 3 + i * 3]) for i in range(256)]

    def record(self, i: int):
        o = i * 8
        w = self.data[o]
        h = self.data[o + 1]
        xo = struct.unpack_from("<b", self.data, o + 2)[0]
        yo = struct.unpack_from("<b", self.data, o + 3)[0]
        off = struct.unpack_from("<I", self.data, o + 4)[0]
        return w, h, xo, yo, off

    def frame_planar(self, i: int):
        """Decode frame i out of its plane-chunked, bottom-up storage into a
        top-down (w, h, rows) image."""
        w, h, xo, yo, off = self.record(i)
        if w == 0 or h == 0:
            return w, h, xo, yo, []
        # Plane p holds every fourth pixel starting at p; a width that is not a
        # multiple of four gives the low planes one pixel more.
        counts = [(w - p + 3) // 4 for p in range(4)]
        stride = sum(counts)
        rows = []
        for r in range(h):
            base = off + r * stride
            row = [0] * w
            c = base
            for p in range(4):
                for k in range(counts[p]):
                    row[p + k * 4] = self.data[c]
                    c += 1
            rows.append(row)
        rows.reverse()  # stored bottom-up
        return w, h, xo, yo, rows


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

# The ramp 0002B820 puts red and green through before measuring a colour
# distance, verbatim from 0002B7D0: six bits in, 0..127 out.
GAMMA = [
    0, 1, 2, 4, 5, 7, 8, 10, 12, 13, 15, 17, 19, 21, 23, 25,
    27, 29, 31, 33, 35, 37, 40, 42, 44, 46, 49, 51, 54, 56, 58, 61,
    63, 66, 68, 71, 73, 76, 78, 80, 83, 85, 87, 90, 92, 94, 96, 98,
    100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 119, 121, 123, 124, 126, 127,
]


def match_key6(c6):
    r, g, b = c6
    return GAMMA[r & 63], GAMMA[g & 63], (b & 63) * 2


def translation_table(bank_pal6, screen_pal8):
    """0002B949's table: every bank index as the nearest entry of the palette
    the screen installed. Weighted squared error, weights 30/55/15, measured
    in six-bit DAC space; candidates 1..254 in order, first minimum wins, an
    exact match stops the search, 0 and 255 pass through."""
    cand = [match_key6(tuple(v >> 2 for v in c)) for c in screen_pal8]
    table = list(range(256))
    for i in range(1, 255):
        kr, kg, kb = match_key6(bank_pal6[i])
        best, best_i = None, 0
        for j in range(1, 255):
            cr, cg, cb = cand[j]
            d = (30 * (cr - kr)) ** 2 + (55 * (cg - kg)) ** 2 + (15 * (cb - kb)) ** 2
            if best is None or d < best:
                best, best_i = d, j
                if d == 0:
                    break
        table[i] = best_i
    return table


def rgb565_roundtrip(c):
    """The Falcon stores RGB565 converted from the six-bit DAC values exactly
    as attract.s does, so the oracle must lose the same bits."""
    # The DTA and bank palettes are eight bits per component, not the VGA
    # DAC's six: CONSOL1S.DTA reaches 252 and TPIC 188. console.s already
    # converts them as 8-bit; attract.s reading them as 6-bit is what turns
    # COMA's near-black ground into full green.
    r, g, b = c
    r5, g6c, b5 = r >> 3, g >> 2, b >> 3
    return (r5 << 3) | (r5 >> 2), (g6c << 2) | (g6c >> 4), (b5 << 3) | (b5 >> 2)


def write_png(path: Path, w: int, h: int, rgb_rows):
    import zlib

    raw = bytearray()
    for row in rgb_rows:
        raw.append(0)
        for px in row:
            raw.extend(px)

    def chunk(tag, payload):
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def compose(img_w, img_h, pixels, pal, top_row, view_w=320, view_h=240):
    """The DOS view: view_w columns from the left of the stored image, view_h
    rows starting at top_row."""
    rows = []
    for y in range(view_h):
        sy = min(top_row + y, img_h - 1)
        base = sy * img_w
        rows.append([rgb565_roundtrip(pal[pixels[base + x]]) for x in range(view_w)])
    return rows


def blit_sprite(rows, bank, index, x_ref, y_bottom, pal, table, view_h=240):
    """The original's placement: X = x_ref - record.x_off is the left edge and
    y_bottom + record.y_off is the BOTTOM row, because the blitter walks up.
    Indices are the bank's, translated into the screen palette `pal` - the
    payload rewrite 0002B9BA does once, at install."""
    w, h, xo, yo, frame = bank.frame_planar(index)
    if not frame:
        return
    # 00025880 computes the destination byte column as
    #   (x_ref - signed_x_offset) >> 2
    # and each VGA plane expands that byte column to four physical pixels.
    # Keep the expanded Falcon surface at the same four-pixel edge; treating
    # x_ref - xo as a free pixel coordinate leaves ZOVE three pixels too far
    # right in the side opening.
    left = ((x_ref - xo) // 4) * 4
    bottom = y_bottom + yo
    top = bottom - h + 1
    for r in range(h):
        y = top + r
        if not (0 <= y < view_h):
            continue
        for c in range(w):
            x = left + c
            if 0 <= x < len(rows[y]):
                rows[y][x] = rgb565_roundtrip(pal[table[frame[r][c]]])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--outdir", type=Path, default=Path("build/ref"))
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    # The side screen: RH66SIDE.DTA with ZOVE.RLE animating in its black plate.
    w, h, px, pal = load_dta(args.root / "RH66SIDE.DTA")
    print(f"RH66SIDE.DTA {w}x{h}")
    zove = Bank(krl_unpack(args.root / "ZOVE.RLE"))
    print(f"ZOVE.RLE {zove.count} frames, records:", end=" ")
    for i in range(1, min(zove.count, 8)):
        print(zove.record(i)[:4], end=" ")
    print()
    ztab = translation_table(zove.pal, pal)
    print(f"  ZOVE translation: {sum(1 for i in range(256) if ztab[i] == i)}/256"
          " entries are themselves")
    for frame in (1, 2, 3):
        rows = compose(w, h, px, pal, 0)
        blit_sprite(rows, zove, frame, 0xAF, 0x4B, pal, ztab)
        write_png(args.outdir / f"side_zove{frame}.png", 320, 240, rows)

    # The title: TPIC.DTA panned, COMA.RLE flying over it.
    w, h, px, pal = load_dta(args.root / "TPIC.DTA")
    print(f"TPIC.DTA {w}x{h}")
    coma = Bank(krl_unpack(args.root / "COMA.RLE"))
    print(f"COMA.RLE {coma.count} frames, records:", end=" ")
    for i in range(1, min(coma.count, 10)):
        print(coma.record(i)[:4], end=" ")
    print()
    # The three moments the state machine makes: the pan before the gate at
    # buffer row 93 opens (no sprite drawn at all), the gate itself with the
    # Comanche entering at the top edge, and the pan saturated at row 150 -
    # 150 + 240 = 390, exactly TPIC's height - with the sprite clamped at 248.
    ctab = translation_table(coma.pal, pal)
    print(f"  COMA translation: {sum(1 for i in range(256) if ctab[i] == i)}/256"
          " entries are themselves")
    for name, pan, spry, idx in (
        ("title_open", 40, None, 9),
        ("title_gate", 93, 0x5D, 5),
        ("title_end", 150, 0xF8, 1),
    ):
        rows = compose(w, h, px, pal, pan)
        if spry is not None:
            blit_sprite(rows, coma, idx, 0xA0, spry - pan, pal, ctab)
        write_png(args.outdir / f"{name}.png", 320, 240, rows)

    # The first opening's still.
    w, h, px, pal = load_dta(args.root / "BACK.DTA")
    print(f"BACK.DTA {w}x{h}")
    write_png(args.outdir / "back.png", 320, 240, compose(w, h, px, pal, 0))
    print(f"wrote references to {args.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
