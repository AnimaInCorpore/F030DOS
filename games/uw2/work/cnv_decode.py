#!/usr/bin/env python3
"""Decompress and parse DATA/CNV.ARK conversation records.

Both the compression and the record layout were read out of UW2.EXE, not
guessed -- see analysis/data-formats.md, "CNV.ARK". The layout comes from the
import-table parser at file 0x75863, which the load path at 0x74E15 calls
after reading a record into a 0x5000-byte buffer:

  [0x46f2] += 4                 -> skip 4 bytes
  u32  code size in words       -> malloc(words * 2)     = the bytecode array
  u16                           -> global 0x4712
  u16                           -> global 0x3498         = STRINGS.PAK block id
  u16  memory size in words     -> malloc((words+0x800)*2)
  u16  import count
  then, per import:
      u16   name length (no NUL in the stream)
      char  name[length]
      u16   -> table entry +0x1A   (the dispatch slot; see below)
      u16   -> table entry +0x18   (non-zero = live; the register routine's
                                    loop terminator tests this word)
      u16, u16
  then  code_words * 2 bytes of bytecode.

The register routine at 0x765E6 walks that table with a 32-byte stride,
strcmp()s the name, and stores the builtin's far pointer at
[0x470e] + entry[+0x1A] * 4 -- so an import's first field is its index into
the VM's function-pointer array.

Compression: textbook LZSS (Okumura), ring N=4096, F=18, THRESHOLD=2, ring
window starting at N-F and zero-filled. Flag byte low bit first; 1 = literal,
0 = a 2-byte (offset, length) pair, offset = i | ((j & 0xF0) << 4),
length = (j & 0x0F) + 3. The stream starts at record + 4; the u32 at record + 0
is the uncompressed length.

Usage:
  python work/cnv_decode.py                 # verify all records
  python work/cnv_decode.py --imports 2     # one conversation's import table
  python work/cnv_decode.py --dump 2 out.bin
"""
import argparse
import re
import struct
from pathlib import Path

CNV = Path("work/extracted/D4/DATA/CNV.ARK")
SLOTS = 320
N, F, THRESHOLD = 4096, 18, 2
IDENT = re.compile(rb"^[A-Za-z_][A-Za-z0-9_]*$")


def arrays(d):
    return [[struct.unpack_from("<I", d, 0x02 + a * 4 * SLOTS + 4 * i)[0]
             for i in range(SLOTS)] for a in range(4)]


def lzss(src, outlen):
    """Okumura LZSS, as the EXE's loader implements it."""
    ring = bytearray(N)
    r = N - F
    out = bytearray()
    p = 0
    while len(out) < outlen and p < len(src):
        flags = src[p]
        p += 1
        for bit in range(8):
            if len(out) >= outlen or p >= len(src):
                break
            if (flags >> bit) & 1:
                c = src[p]
                p += 1
                out.append(c)
                ring[r] = c
                r = (r + 1) % N
            else:
                i, j = src[p], src[p + 1]
                p += 2
                o = i | ((j & 0xF0) << 4)
                for k in range((j & 0x0F) + THRESHOLD + 1):
                    c = ring[(o + k) % N]
                    out.append(c)
                    ring[r] = c
                    r = (r + 1) % N
    return out, p


class Conversation:
    def __init__(self, raw):
        self.raw = raw
        self.unknown0 = struct.unpack_from("<I", raw, 0)[0]
        self.code_words = struct.unpack_from("<I", raw, 4)[0]
        self.unknown8 = struct.unpack_from("<H", raw, 8)[0]
        self.string_block = struct.unpack_from("<H", raw, 0x0A)[0]
        self.mem_words = struct.unpack_from("<H", raw, 0x0C)[0]
        count = struct.unpack_from("<H", raw, 0x0E)[0]
        self.imports = []
        q = 0x10
        for _ in range(count):
            ln = struct.unpack_from("<H", raw, q)[0]
            name = bytes(raw[q + 2:q + 2 + ln])
            slot, live, f2, f3 = struct.unpack_from("<4H", raw, q + 2 + ln)
            self.imports.append((name.decode("latin1"), slot, live, f2, f3))
            q += 2 + ln + 8
        self.code_offset = q
        self.code = raw[q:q + 2 * self.code_words]

    def tiles_exactly(self):
        return self.code_offset + 2 * self.code_words == len(self.raw)


def load(d, slot):
    off, _, size, _ = arrays(d)
    raw_rec = d[off[slot]:off[slot] + size[slot]]
    outlen = struct.unpack_from("<I", raw_rec, 0)[0]
    out, used = lzss(raw_rec[4:], outlen)
    return Conversation(out), (len(out) == outlen, used == len(raw_rec) - 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--imports", type=int, metavar="SLOT")
    ap.add_argument("--dump", nargs=2, metavar=("SLOT", "FILE"))
    a = ap.parse_args()
    d = CNV.read_bytes()
    off, _, size, _ = arrays(d)
    populated = [i for i in range(SLOTS) if off[i]]

    if a.imports is not None:
        c, _ = load(d, a.imports)
        print(f"conversation slot {a.imports}: strings block 0x{c.string_block:04X}, "
              f"{c.code_words} code words, {c.mem_words} memory words, "
              f"{len(c.imports)} imports")
        for name, slot, live, f2, f3 in c.imports:
            print(f"  [{slot:3d}] live={live} {f2:#06x} {f3:#06x}  {name}")
        return
    if a.dump:
        c, _ = load(d, int(a.dump[0]))
        Path(a.dump[1]).write_bytes(c.raw)
        print(f"wrote {len(c.raw)} B to {a.dump[1]}")
        return

    exact = names_ok = tiles = block_ok = 0
    all_names, counts, maxoff = set(), set(), 0
    for s in populated:
        c, (len_ok, src_ok) = load(d, s)
        exact += len_ok and src_ok
        tiles += c.tiles_exactly()
        block_ok += c.string_block == 0x0E00 + s - 1
        counts.add(len(c.imports))
        if all(IDENT.match(n.encode()) for n, *_ in c.imports):
            names_ok += 1
            all_names.update(n for n, *_ in c.imports)
    n = len(populated)
    print(f"{CNV}: {n} populated conversation records")
    print(f"  LZSS output length == u32@+0 AND source fully consumed : {exact}/{n}")
    print(f"  every import name is a valid identifier                : {names_ok}/{n}")
    print(f"  0x10 + import table + 2*code_words == uncompressed len : {tiles}/{n}")
    print(f"  u16 @+0x0A == STRINGS.PAK block 0x0E00 + slot - 1      : {block_ok}/{n}")
    print(f"  import count per conversation: {sorted(counts)}  distinct names: {len(all_names)}")


if __name__ == "__main__":
    main()
