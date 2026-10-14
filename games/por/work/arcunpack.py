#!/usr/bin/env python3
"""Expand the SEA/PKARC archives into work/expanded/ -- the pure-Python
replacement for `unar` in work/stage.sh (stage.sh calls unar only when this
script is unavailable, so the pipeline runs on macOS and Windows alike).

Reference implementations (The Unarchiver / XADMaster, MacPaw; BSD-3 +
LGPL-2.1 -- reference copies kept in work/arc_ref_*, fetched
2026-08-21 from github.com/MacPaw/unar @ master):
    XADARCParser.m        entry table + method dispatch
    XADCompressHandle.m   LZW layers (methods 8, 9)
    LZW.c / LZW.h         the shared LZW core
    XADPrefixCode.m       prefix-code decoder (Squeeze, method 4)
    XADSqueezeHandle.m    Squeeze header (prefix tree)
    XADRLE90Handle.m      RLE90 layer
    CSInputBuffer.h/.m    the bit reader ("*LE" = LSB-first within a byte)

ARC entry header (29 B, verified against DISKA.ARC @0x00 -- see
work/arcverify.py and analysis/data-formats.md):
    0x00 u8      0x1A magic
    0x01 u8      compression method (0 = end-of-archive; 0x1E/0x82 = dir;
                 0x1F/0x80 = pop directory)
    0x02 char13  filename, NUL-terminated
    0x0F u32LE   compressed size
    0x13 u16LE   DOS date
    0x15 u16LE   DOS time
    0x17 u16LE   CRC-16/ARC of the *expanded* data
    0x19 u32LE   original size
plus 12 more bytes (load/exec/attrs) when method & 0x80. Archive ends with
the 2-byte marker 1A 00.

Method table (XADARCParser.m; bits 7 = Archimedes extra header, so methods
appear as e.g. 0x82):
    1  None (old, stored; uncompressed size == compressed size)
    2  None (stored)
    3  Packed              = RLE90
    4  Squeezed+packed     = Squeeze prefix code -> RLE90
    5  Crunched            = ARC crunch (not used by POR)
    6  Crunched+packed     = ARC crunch -> RLE90 (not used by POR)
    7  Crunched(fast)+pack = ARC crunch (fast hash) -> RLE90 (not used)
    8  Crunched+packed(LZW)= 1 marker byte 0x0C, LZW(4096, clear 256) -> RLE90
    9  Squashed            = LZW(8192, clear 256)
    A  Crushed             = ARC crush -> RLE90 (not used by POR)
    B  Distilled           = ARC distill (not used by POR)

POR's four archives use methods {2,3,4,8,9} only. Every expanded file is
checked against its stored CRC-16/ARC; a single mismatch is fatal, so a
clean run is byte-exact proof, not a plausibility check.

Usage:  python3 work/arcunpack.py          (from the project root)
"""
import os
import struct
import sys

ARCS = ["game/POR/Disk1/DISKA.ARC", "game/POR/Disk1/DISKB.ARC",
        "game/POR/Disk1/SAVE.ARC",  "game/POR/Disk2/DISKC.ARC"]
OUT = "work/expanded"


def crc16_arc(buf):
    crc = 0
    for b in buf:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class BitReader:
    """LSB-first bit reader, bit-for-bit equivalent of CSInputBuffer's
    "*LE" family: bits are taken from each byte low bit first, and
    CSInputSkipBitsLE's byte-boundary fast path consumes exactly the same
    bits as a plain n-bit advance."""

    def __init__(self, data, pos=0):
        self.d = data
        self.pos = pos
        self.acc = 0
        self.nacc = 0

    def _fill(self, need):
        while self.nacc < need:
            if self.pos >= len(self.d):
                raise EOFError("bitstream exhausted")
            self.acc |= self.d[self.pos] << self.nacc
            self.pos += 1
            self.nacc += 8

    def bits(self, n):
        if n == 0:
            return 0
        self._fill(n)
        v = self.acc & ((1 << n) - 1)
        self.acc >>= n
        self.nacc -= n
        return v


class LZW:
    """Port of XADMaster LZW.c (NextLZWSymbol + LZWOutputToInternalBuffer).

    Tree representation: nodes[i] = (chr, parent); literal codes 0..255;
    code 256 reserved as the clear symbol (reservedsymbols=1). Output for a
    code walks the new symbol's parent chain, which yields the standard
    string(prev) + firstbyte(symbol), including the symbol==numsymbols
    self-reference case."""

    def __init__(self, maxsymbols):
        self.max = maxsymbols
        self.res = 1
        self.parent = [-1] * maxsymbols
        self.chr = list(range(256)) + [0] * (maxsymbols - 256)
        self.clear()

    def clear(self):
        self.n = 256 + self.res
        self.prev = -1
        self.symsize = 9

    def _first(self, s):
        while self.parent[s] >= 0:
            s = self.parent[s]
        return self.chr[s]

    def next(self, s):
        # Output for code s is the FULL string of s (walk the new symbol's
        # chain, as LZWOutputToInternalBuffer does after NextLZWSymbol has
        # set prevsymbol=s); the table entry added is string(old)+postfix.
        # The s==n self-reference case needs the entry added first.
        if self.prev < 0:
            if s >= self.n:
                raise ValueError("LZW: invalid first code %d" % s)
            self.prev = s
            return [self.chr[s]]
        if s < self.n:
            postfix = self._first(s)
        elif s == self.n:
            postfix = self._first(self.prev)
        else:
            raise ValueError("LZW: invalid code %d (table %d)" % (s, self.n))
        old = self.prev
        self.prev = s
        if self.n < self.max:
            self.parent[self.n] = old
            self.chr[self.n] = postfix
            self.n += 1
            if self.n < self.max and (self.n & (self.n - 1)) == 0:
                self.symsize += 1
        out = []
        t = s
        while t >= 0:
            out.append(self.chr[t])
            t = self.parent[t]
        out.reverse()
        return out


def lzw_decompress(data, maxsymbols, outsize):
    """XADCompressHandle with flags 0x8C/0x8D: block mode, clear code 256,
    byte-boundary skip after each clear, symbols LSB-first."""
    br = BitReader(data)
    lzw = LZW(maxsymbols)
    out = bytearray()
    counter = 0
    while outsize is None or len(out) < outsize:
        try:
            s = br.bits(lzw.symsize)
        except EOFError:
            break
        counter += 1
        if s == 256:
            if counter % 8:
                br.bits(lzw.symsize * (8 - counter % 8))
            lzw.clear()
            counter = 0
            continue
        out.extend(lzw.next(s))
    return bytes(out[:outsize]) if outsize else bytes(out)


def rle90(data, outsize):
    """XADRLE90Handle: 0x90 0x00 -> literal 0x90; 0x90 c (c>=2) -> emit the
    previous literal c-1 times; 0x90 0x01 is invalid."""
    out = bytearray()
    prev = 0
    count = 0
    i = 0
    n = len(data)
    while len(out) < outsize:
        if count:
            count -= 1
            out.append(prev)
            continue
        if i >= n:
            raise EOFError("RLE90: input exhausted")
        b = data[i]
        i += 1
        if b != 0x90:
            prev = b
            out.append(b)
        else:
            if i >= n:
                raise EOFError("RLE90: truncated escape")
            c = data[i]
            i += 1
            if c == 0:
                prev = 0x90
                out.append(prev)
            elif c == 1:
                raise ValueError("RLE90: invalid control 0x90 0x01")
            else:
                count = c - 2
                out.append(prev)
    return bytes(out[:outsize])


def squeeze(data):
    """XADSqueezeHandle: u16LE m; numnodes = 2m; numnodes int16LE values.
    Internal node id i has children at array positions 2i (bit 0) and 2i+1
    (bit 1); a negative value -v at a position is a leaf of value v-1.
    Symbol 256 ends the stream. Bits LSB-first."""
    m, = struct.unpack_from("<H", data, 0)
    numnodes = 2 * m
    nodes = struct.unpack_from("<%dh" % numnodes, data, 2)
    br = BitReader(data, 2 + 2 * numnodes)
    out = bytearray()
    while True:
        idx = 0
        while True:
            b = br.bits(1)
            v = nodes[2 * idx + b]
            if v < 0:
                sym = -v - 1
                break
            idx = v
        if sym == 256:
            break
        out.append(sym)
    return bytes(out)


def decompress(method, payload, outsize):
    m = method & 0x7F
    if m in (1, 2):
        return payload[:outsize]
    if m == 3:
        return rle90(payload, outsize)
    if m == 4:
        return rle90(squeeze(payload), outsize)
    if m == 8:
        if payload[0] != 0x0C:
            raise ValueError("LZW layer: expected marker 0x0C, got %02X"
                             % payload[0])
        return rle90(lzw_decompress(payload[1:], 4096, None), outsize)
    if m == 9:
        return lzw_decompress(payload, 8192, outsize)
    raise ValueError("unsupported ARC method %d" % m)


def parse_entries(arcfile):
    d = open(arcfile, "rb").read()
    o = 0
    n = len(d)
    while o < n:
        if d[o] != 0x1A:
            raise ValueError("%s: bad magic %02X at offset %X"
                             % (arcfile, d[o], o))
        o += 1
        method = d[o]
        o += 1
        if method == 0x00:
            return
        name = d[o:o + 13].split(b"\0")[0].decode("latin1")
        o += 13
        csz, = struct.unpack_from("<I", d, o); o += 4
        dt, tm, crc = struct.unpack_from("<HHH", d, o); o += 6
        if method == 1:
            osz = csz
        else:
            osz, = struct.unpack_from("<I", d, o); o += 4
        extra = b""
        if method & 0x80:
            extra = d[o:o + 12]
            o += 12
        payload = d[o:o + csz]
        o += csz
        yield method, name, payload, crc, osz, extra


def clean_name(name):
    # XADARCParser strips one trailing space/period from 8.3 names.
    if len(name) > 1 and name[-1] in " .":
        name = name[:-1]
    return name


def main():
    if os.path.isdir(OUT):
        for f in os.listdir(OUT):
            p = os.path.join(OUT, f)
            if os.path.isdir(p) and not os.path.islink(p):
                import shutil
                shutil.rmtree(p)
            else:
                os.remove(p)
    else:
        os.makedirs(OUT)

    total = 0
    methods = {}
    for arc in ARCS:
        for method, name, payload, crc, osz, _extra in parse_entries(arc):
            m = method & 0x7F
            # 0x1E/0x82 are directory entries (no payload), 0x1F/0x80 pop the
            # directory stack. None of the four POR archives use directories.
            if m in (0x1E, 0x1F, 0x80, 0x82):
                continue
            else:
                data = decompress(method, payload, osz)
                if len(data) != osz:
                    print("SIZE  %s method=%d got %d want %d (%s)"
                          % (name, method, len(data), osz, arc))
                    return 1
                got = crc16_arc(data)
                if got != crc:
                    print("CRC   %s method=%d got %04X want %04X (%s)"
                          % (name, method, got, crc, arc))
                    return 1
                p = os.path.join(OUT, clean_name(name))
                with open(p, "wb") as f:
                    f.write(data)
                total += 1
                methods[method] = methods.get(method, 0) + 1
    print("%d files expanded to %s; methods %s"
          % (total, OUT, dict(sorted(methods.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
