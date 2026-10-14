#!/usr/bin/env python3
"""Gold Box `.DAX` container reader + RLE codec probe.

Container (verified against all 89 DAX files in work/expanded/):

    [u16LE tableSize]                  # bytes, always 9 * blockCount
    [blockCount x 9-byte block record]:
        u8    blockId                  # high bit = variant flag (see analysis)
        u32LE offset                   # relative to end of header (2 + tableSize)
        u16LE unpackedSize
        u16LE packedSize
    [packed blocks, contiguous, in table order]

Invariants checked: offsets start at 0, are strictly cumulative
(off[k+1] == off[k] + packed[k]), and 2 + tableSize + sum(packed) == filesize.

Payload codec: PackBits-style RLE on signed control bytes —
    n = int8(ctrl)
    n <  0 : emit the next single byte (-n) times
    n >= 0 : copy the next (n + 1) bytes literally
"""
import os, struct, sys, collections

EXPANDED = "work/expanded"

def blocks(path):
    d = open(path, "rb").read()
    tbl = struct.unpack_from("<H", d, 0)[0]
    if tbl % 9:
        raise ValueError(f"{path}: table size {tbl} not a multiple of 9")
    base = 2 + tbl
    out = []
    for i in range(tbl // 9):
        bid, off, unp, pak = struct.unpack_from("<BIHH", d, 2 + i * 9)
        out.append((bid, off, unp, pak, d[base + off: base + off + pak]))
    return d, base, out

def unrle(buf, want=None):
    out = bytearray()
    i = 0
    while i < len(buf) and (want is None or len(out) < want):
        n = buf[i] - 256 if buf[i] > 127 else buf[i]
        i += 1
        if n < 0:
            if i >= len(buf): break
            out += bytes([buf[i]]) * (-n)
            i += 1
        else:
            out += buf[i:i + n + 1]
            i += n + 1
    return bytes(out)

def main():
    files = sorted(f for f in os.listdir(EXPANDED) if f.upper().endswith(".DAX"))
    nblk = ok_c = bad_c = ok_r = bad_r = 0
    ids = collections.Counter()
    for f in files:
        p = os.path.join(EXPANDED, f)
        size = os.path.getsize(p)
        try:
            d, base, bs = blocks(p)
        except Exception as e:
            print(f"CONTAINER {f}: {e}"); bad_c += 1; continue
        exp, prob = 0, []
        for bid, off, unp, pak, payload in bs:
            if off != exp: prob.append(f"off {off} != {exp}")
            exp += pak
        if base + exp != size: prob.append(f"end {base+exp} != size {size}")
        if prob: print(f"CONTAINER {f}: {'; '.join(prob)}"); bad_c += 1
        else: ok_c += 1
        for bid, off, unp, pak, payload in bs:
            nblk += 1; ids[bid] += 1
            if len(unrle(payload, unp)) == unp: ok_r += 1
            else: bad_r += 1
    print(f"{len(files)} DAX files: container OK {ok_c}, bad {bad_c}")
    print(f"{nblk} blocks: RLE length matches unpackedSize {ok_r}, mismatched {bad_r}")
    print(f"distinct block ids: {len(ids)}; high-bit-set ids: {sum(v for k,v in ids.items() if k & 0x80)}")
    return 1 if (bad_c or bad_r) else 0

if __name__ == "__main__":
    sys.exit(main())
