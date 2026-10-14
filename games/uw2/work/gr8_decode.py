#!/usr/bin/env python3
"""Decode .GR type 8 (and type 6) records. Spec from ghidra.md S25.

Chain: shape_draw 0x1D543 -> thunk 0x250B3 -> dispatch 0x112CC -> 0x9499 (type 8).

  header:  u8 format, u8 width, u8 height, u8 aux_palette_index
  payload: u16LE nibble_count, then ceil(count/2) bytes, two 4-bit pixels each,
           HIGH nibble first  (type 8; type 6 packs 5-bit pixels, 8 per 5 bytes)

The unpacked nibble stream is then RLE-decoded (0x954D). Every emitted value
goes through xlatb against the 16-byte aux palette the setup at 0x9423 copies
to 0x65c:0.

Lengths use a nibble-escape ladder:
    n in 1..15      -> that value
    0, then b!=0    -> (b << 4) | next          (8-bit)
    0, then 0       -> four nibbles             (16-bit; the `add si,dx`, dx=3)

Control values:
    >2   run of `control` copies, then a literal group
    2    the next N items are run-only (implemented in the original by
         patching cs:0x1a6 to 0xC3 so the recursive call returns before the
         literal group)
    1    no run, straight to the literal group
    0    escape to a wider run length, then the literal group
"""
import struct
import sys
from pathlib import Path


class Bail(Exception):
    pass


class Nib:
    def __init__(self, nibbles):
        self.n = nibbles
        self.i = 0

    def get(self):
        if self.i >= len(self.n):
            raise Bail("nibble stream exhausted")
        v = self.n[self.i]
        self.i += 1
        return v

    def peek_done(self, end):
        return self.i >= end

    def length(self):
        """The nibble-escape ladder (0x958E / 0x959D / 0x9607)."""
        v = self.get()
        if v:
            return v
        v = self.get()
        if v:
            return (v << 4) | self.get()
        a, b, c, d2 = self.get(), self.get(), self.get(), self.get()
        return (a << 12) | (b << 8) | (c << 4) | d2


def unpack4(payload):
    count = struct.unpack_from("<H", payload, 0)[0]
    src = payload[2:]
    out = []
    for i in range((count + 1) >> 1):
        if i >= len(src):
            raise Bail("source exhausted during nibble unpack")
        b = src[i]
        out.append(b >> 4)
        out.append(b & 0xF)
    return count, out[:count]


def rle(nibbles, xlat):
    """The stage at 0x954D.

    Control byte, then optionally a run, then always a literal group:
        ctl > 2  -> run of `ctl`
        ctl == 2 -> the next N items are run-only (0x95D3 patches 0x9566 to RET)
        ctl == 1 -> no run
        ctl == 0 -> run length escapes wider (0x95BF / 0x959D)
    All three widen the same way; the 16-bit form is 4 nibbles, big-endian.
    """
    s = Nib(nibbles)
    end = len(nibbles)
    out = bytearray()

    def read4():
        return (s.get() << 12) | (s.get() << 8) | (s.get() << 4) | s.get()

    def wider():
        """0x958E / 0x9607: one nibble, or escape again to 16-bit."""
        v = s.get()
        return ((v << 4) | s.get()) if v else read4()

    def literal_count():
        v = s.get()
        return v if v else wider()

    def emit_run(n):
        out.extend([xlat[s.get()]] * n)

    def do_literals():
        for _ in range(literal_count()):
            out.append(xlat[s.get()])

    def one_run(ctl):
        """The run part only -- what a patched call to 0x9554 performs."""
        if ctl > 2:
            emit_run(ctl)
        elif ctl == 0:
            v = s.get()
            emit_run(((v << 4) | s.get()) if v else read4())
        # ctl == 1 emits no run

    while not s.peek_done(end):
        ctl = s.get()
        if ctl == 2:
            v = s.get()
            n = v if v else wider()
            for _ in range(n):
                if s.peek_done(end):
                    break
                one_run(s.get())
        else:
            one_run(ctl)
        do_literals()
    return bytes(out)


def decode_type8(rec, xlat=None):
    if xlat is None:
        xlat = bytes(range(16))
    count, nib = unpack4(rec[4:])
    return rle(nib, xlat)


def _ror16(v, n):
    v &= 0xFFFF
    return ((v >> n) | (v << (16 - n))) & 0xFFFF


def _rol16(v, n):
    v &= 0xFFFF
    return ((v << n) | (v >> (16 - n))) & 0xFFFF


def _shr_ah(ax, n):
    """shr ah, n -- the high byte only."""
    return (ax & 0x00FF) | ((((ax >> 8) & 0xFF) >> n) << 8)


def unpack5(payload):
    """Type 6's unpack at 0x94F7: 5 source bytes -> 8 five-bit values.

    Transcribed instruction for instruction rather than re-derived, because the
    original threads one 16-bit AX through ror/shr/xchg and the intermediate
    high bits matter.
    """
    count = struct.unpack_from("<H", payload, 0)[0]
    src = payload[2:]
    out = []
    p = 0
    need = ((count + 7) >> 3) * 5
    if need > len(src):
        raise Bail("source exhausted during 5-bit unpack")
    for _ in range((count + 7) >> 3):
        ax = src[p]; p += 1                      # lodsb / xor ah,ah
        ax = _ror16(ax, 3); out.append(ax & 0xFF)
        ax = (ax & 0xFF00) | src[p]; p += 1      # lodsb
        ax = _shr_ah(ax, 5)
        ax = _ror16(ax, 6); out.append(ax & 0xFF)
        ax = (ax >> 3) & 0xFFFF                  # shr ax,3
        ax = ((ax & 0xFF) << 8) | (ax >> 8)      # xchg al,ah
        out.append(ax & 0xFF)
        ax = (ax & 0xFF00) | src[p]; p += 1
        ax = _shr_ah(ax, 7)
        ax = _ror16(ax, 4); out.append(ax & 0xFF)
        ax = (ax & 0xFF00) | src[p]; p += 1
        ax = _shr_ah(ax, 4)
        ax = _ror16(ax, 7); out.append(ax & 0xFF)
        ax = ax & 0xFF00                         # xor al,al
        ax = _rol16(ax, 5); out.append(ax & 0xFF)
        ax = (ax & 0xFF00) | src[p]; p += 1
        ax = _shr_ah(ax, 6)
        ax = _ror16(ax, 5); out.append(ax & 0xFF)
        ax = (ax >> 11) & 0xFFFF                 # shr ax,0xb
        out.append(ax & 0xFF)
    return count, out[:count]


def decode_type6(rec, xlat=None):
    if xlat is None:
        xlat = bytes(range(32))
    count, vals = unpack5(rec[4:])
    return rle(vals, xlat)


def records(b):
    n = struct.unpack_from("<H", b, 1)[0]
    t = [b[3 + 4 * i] | (b[4 + 4 * i] << 8) | (b[5 + 4 * i] << 16) for i in range(n + 1)]
    return [(t[i], t[i + 1]) for i in range(n)]


if __name__ == "__main__":
    root = Path("work/extracted")
    files = sorted(root.glob("D*/DATA/*.GR"))
    tot = ok = bail = mismatch = 0
    for f in files:
        b = f.read_bytes()
        for i, (s, e) in enumerate(records(b)):
            if e <= s or e > len(b):
                continue
            rec = b[s:e]
            if not rec or rec[0] != 8:
                continue
            tot += 1
            w, h = rec[1], rec[2]
            try:
                px = decode_type8(rec)
            except Bail as ex:
                bail += 1
                if bail <= 3:
                    print(f"  BAIL {f.name}#{i} {w}x{h}: {ex}")
                continue
            if len(px) == w * h:
                ok += 1
            else:
                mismatch += 1
                if mismatch <= 5:
                    print(f"  SIZE {f.name}#{i} {w}x{h}={w*h} got {len(px)}")
    print(f"\ntype-8 records: {tot}   exact w*h: {ok}   wrong size: {mismatch}   bailed: {bail}")
