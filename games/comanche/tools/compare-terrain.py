#!/usr/bin/env python3
"""Diff a frame the ORIGINAL drew against the same frame from this port.

This compares a real DOS snapshot against a real Falcon capture. The removed
Node renderer and its pinned camera were not references: they contained
hand-authored geometry and colours, so they could not establish parity.

It needs no new DOS-side harness, because the game already has one.
`000165FD` writes the visible page out as `SNAP_001.PCX` - 328x240, eight bits
per pixel, 128-byte header, PCX run-length payload, and the DAC read back
behind an `0x0C` marker with each component shifted up by two. That is the
format every `.DTA` in the game is in, down to the field offsets - a .DTA is
a PCX with the four manufacturer bytes replaced by the tag `Kyle`, which is
why one decoder reads both.

Getting the original to write one - **and this has not yet been made to
work**, so treat it as the reading of the code rather than a recipe:

  1. run COMANCHE.EXE and start a mission;
  2. press Escape for the options bar and type K, Y, L, E - the four scancodes
     0002601B compares the shift register at 00001B70 against, newest in the
     low byte, and the author's name;
  3. Escape back to the game;
  4. hold Alt and press P.

The gate at 000189C2 wants scancodes 0x38 and 0x19 - Alt and P - in the key
array at 00001A70 to read as pressed, and the feature byte [000265ED] to be
anything but 0xFF. That byte is toggled at 0002602C, behind a second gate on
[00001A7E], scancode 0x0E, Backspace.

Twelve driven attempts produced no file. Two facts complicate it and neither
is settled: the compare sits inside the menu's redraw loop, so the byte
toggles once per frame for as long as the register still reads KYLE, making
the parity depend on when the next key arrives; and the Backspace gate reads
as open only while that key's array entry is non-negative, which depends on
whether the array is zero-initialised or starts as all-released - pressing
Backspace once to satisfy it closes it for the rest of the run.

Settling this wants visibility into [000265ED], which means a DOSBox with the
debugger compiled in. The rest of this tool is validated and ready for the
file whenever it can be produced.

Then, against a Hatari capture of the port at the same viewpoint:

  python3 tools/compare-terrain.py SNAP_001.PCX release/f0.bin

`--demo-camera` is an inspection aid for the first recorded demo start. Normal
verification must capture the attract cycle's actual DEMO<N> flight; it does
not use a build-selectable camera.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

PORT_W, PORT_H = 320, 240


def rle_unpack(src: bytes, want: int) -> bytearray:
    """PCX run-length: a byte below 0xC0 is a literal, otherwise the low six
    bits are a repeat count for the byte after it."""
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


def load_pcx(path: Path):
    """Reads both the SNAP PCX the game writes and the .DTA assets it ships.

    They agree from +8 onward - xmax and ymax as words, a 128-byte header, the
    PCX run-length payload, and the palette behind an 0x0C marker. What differs
    is the first eight bytes: a PCX opens `0A 05 01 08` and then real xmin and
    ymin words, while a .DTA spends all eight on the ASCII tag `Kyle DTA`. So
    the origin fields of a .DTA are the letters ` DTA` and have to be read as
    zero, not subtracted - doing otherwise measures RH66SIDE at -17112 wide."""
    raw = path.read_bytes()
    kyle = raw[:8] == b"Kyle DTA"
    if raw[0] != 0x0A and not kyle:
        raise ValueError(f"{path}: neither PCX nor Kyle DTA "
                         f"(first bytes {raw[:8]!r})")
    xmax, ymax = struct.unpack_from("<HH", raw, 8)
    xmin, ymin = (0, 0) if kyle else struct.unpack_from("<HH", raw, 4)
    w, h = xmax - xmin + 1, ymax - ymin + 1
    # The payload is run-length encoded. The palette behind it is NOT: the
    # 0x0C marker and its 256 triples sit raw in the last 769 bytes of the
    # file. Unpacking w*h+769 bytes and reading the palette out of the result
    # - which this did - turns every component of 0xC0 or more into a run
    # token and shifts the table down from there. It is the same mistake
    # src/attract.s and render-attract-ref.py both carried, and in a tool whose
    # whole purpose is to be the outside opinion it would have corrupted the
    # original's own colours before any comparison began.
    pixels = bytes(rle_unpack(raw[128:-769], w * h)[: w * h])
    pal = None
    if raw[-769] == 0x0C:
        tail = raw[-768:]
        pal = [tuple(tail[i * 3: i * 3 + 3]) for i in range(256)]
    return w, h, pixels, pal


def to565(c):
    """The port's own conversion, so a difference is a difference in the
    picture and not in the arithmetic that describes it."""
    r, g, b = c
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def load_port(path: Path):
    d = path.read_bytes()
    need = PORT_W * PORT_H * 2
    if len(d) < need:
        raise ValueError(f"{path}: {len(d)} bytes, expected at least {need}")
    return [[struct.unpack_from(">H", d, (y * PORT_W + x) * 2)[0]
             for x in range(PORT_W)] for y in range(PORT_H)]


def write_png(path: Path, rows):
    import zlib
    raw = bytearray()
    for row in rows:
        raw.append(0)
        for px in row:
            raw.extend(px)

    def chunk(tag, payload):
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    w, h = len(rows[0]), len(rows)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def rgb(v):
    return (((v >> 11) & 31) << 3, ((v >> 5) & 63) << 2, (v & 31) << 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("original", nargs="?", type=Path,
                    help="SNAP_nnn.PCX written by the game")
    ap.add_argument("port", nargs="?", type=Path,
                    help="a 320x240 RGB565 frame dump from grab-frames.sh")
    ap.add_argument("--rows", default="0:240",
                    help="row band to compare, e.g. 6:78 for sky only")
    ap.add_argument("--out", type=Path, default=Path("build/terrain-diff.png"))
    ap.add_argument("--demo-camera", action="store_true",
                    help="print DEMO0.SCR's recorded start viewpoint and exit")
    args = ap.parse_args()

    if args.demo_camera:
        d = Path("assets/extracted/comanche_hdd/DEMO0.SCR").read_bytes()
        x, y, ang = struct.unpack_from("<iiI", d, 4)
        print("DEMO0.SCR recorded start state (inspection only):")
        print(f"  X   = {x} (0x{x & 0xFFFFFFFF:08X}), 10.22 -> {x / (1 << 22):.4f}")
        print(f"  Y   = {y} (0x{y & 0xFFFFFFFF:08X}), 10.22 -> {y / (1 << 22):.4f}")
        print(f"  ang = 0x{ang:08X}")
        print(f"  alt = {d[16]}")
        print("Use the attract cycle for the parity capture; no BENCH_* camera")
        print("switch exists in the port.")
        return 0

    if not args.original or not args.port:
        ap.error("both a PCX and a port frame are required")

    w, h, px, pal = load_pcx(args.original)
    print(f"{args.original}: {w}x{h}, palette {'present' if pal else 'ABSENT'}")
    if not pal:
        print("  no 0x0C palette block - cannot compare colours", file=sys.stderr)
        return 2
    if h < PORT_H:
        print(f"  only {h} rows; the port has {PORT_H}", file=sys.stderr)

    got = load_port(args.port)
    r0, r1 = (int(v) for v in args.rows.split(":"))
    r1 = min(r1, h, PORT_H)

    # The original's page is 328 wide; the port shows its left 320 columns,
    # the same window the attract screens use.
    diff_rows = []
    total = same = 0
    for y in range(PORT_H):
        row = []
        for x in range(PORT_W):
            want = to565(pal[px[y * w + x]]) if y < h else 0
            have = got[y][x]
            inband = r0 <= y < r1
            if inband:
                total += 1
                if want == have:
                    same += 1
            if want == have:
                row.append(rgb(want) if inband else tuple(c // 3 for c in rgb(want)))
            else:
                row.append((255, 0, 255) if inband else (60, 0, 60))
        diff_rows.append(row)

    pct = 100.0 * same / total if total else 0.0
    print(f"rows {r0}..{r1 - 1}: {same} of {total} pixels identical ({pct:.2f}%)")
    print(f"  {total - same} differ")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_png(args.out, diff_rows)
    print(f"wrote {args.out} - magenta marks a differing pixel, dimmed outside "
          f"the band")
    return 0 if same == total else 1


if __name__ == "__main__":
    sys.exit(main())
