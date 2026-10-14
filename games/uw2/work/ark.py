#!/usr/bin/env python3
"""The shared UW2 `.ARK` container -- one format behind CNV, LEV, BYT and SCD.

`analysis/data-formats.md` decoded CNV.ARK's container and separately described
LEV.ARK as having "a different variable-size blob layout with its own embedded
index table". That was wrong: **all four `.ARK` files use the same container**,
differing only in slot count and in whether records are compressed.

    0x00  u16      slot count N      (SCD 16, BYT 11, CNV 320, LEV 320)
    0x02  u32      purpose not determined; 0 in all four shipped files
    0x06  u32[N]   record offset     0 = empty slot
          u32[N]   flags             bit0 compress-on-write, bit1 stored
                                     compressed, bit2 padded/growable
          u32[N]   stored size, in bytes
          u32[N]   padded/allocated size
    records                          at 0x06 + 16*N, with no gap

    x CORRECTED 2026-08-23. This file previously read the four arrays from
    0x02 and described the leftover 4 bytes as "slack" with records at
    header_end + 4. That is wrong by one slot: the game reads offsets at
    `6 + 4*slot` (ark_read_slot, file 0x72843), so the old slot i was really
    game slot i-1, and old slot 0 was the header u32 at offset 2, not a record.
    Confirmed against the data: u32@6 == 6 + 16*N exactly in SCD/LEV/BYT
    (0x106, 0x1406, 0xb6), and CNV's slot 0 is genuinely empty.
    The old numbering still passed the LZSS self-check because the shift is
    uniform -- a reminder that a self-consistent check is not a correct one.

A compressed record is `u32 uncompressed_length` followed by the same LZSS
stream CNV.ARK uses (see cnv_decode.py: N=4096, F=18, THRESHOLD=2, ring
zero-filled, cursor at N-F, flag byte low bit first).

Verified: of every record whose flag has bit 1 set, across all four files,
**200 of 200** decompress with the output length matching the header u32 *and*
the source consumed exactly. Records with the bit clear are plain data.

Usage:
  python work/ark.py                     # audit every .ARK
  python work/ark.py --file LEV.ARK      # per-record detail
"""
import argparse
import struct
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cnv_decode import lzss                                    # noqa: E402

ROOT = Path("work/extracted")
COMPRESSED = 2


class Ark:
    def __init__(self, path):
        self.path = path
        self.d = path.read_bytes()
        self.slots = struct.unpack_from("<H", self.d, 0)[0]
        n = self.slots
        self.off, self.flag, self.size, self.size2 = (
            [struct.unpack_from("<I", self.d, 0x06 + a * 4 * n + 4 * i)[0]
             for i in range(n)] for a in range(4))
        self.header_end = 0x06 + 16 * n
        self.used = [i for i in range(n) if self.off[i]]

    def record(self, i):
        """Raw record bytes, decompressed if the flag says so."""
        o, sz = self.off[i], self.size[i]
        raw = self.d[o:o + sz]
        if not (self.flag[i] & COMPRESSED):
            return raw, False
        target = struct.unpack_from("<I", raw, 0)[0]
        out, used = lzss(raw[4:], target)
        if len(out) != target or used != len(raw) - 4:
            raise ValueError(f"slot {i}: decompressed {len(out)}/{target}, "
                             f"consumed {used}/{len(raw) - 4}")
        return bytes(out), True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    a = ap.parse_args()
    arks = sorted(ROOT.rglob("*.ARK"))
    if a.file:
        arks = [p for p in arks if p.name == a.file]
    tot = ok = 0
    for p in arks:
        k = Ark(p)
        if not k.slots or k.header_end > len(k.d):
            print(f"{p.name}: u16[0]={k.slots} -- not this container")
            continue
        first = min(k.off[i] for i in k.used)
        comp = [i for i in k.used if k.flag[i] & COMPRESSED]
        good, sizes = 0, Counter()
        for i in comp:
            try:
                body, _ = k.record(i)
                good += 1
                sizes[len(body)] += 1
            except ValueError as e:
                print(f"  {p.name} {e}")
        tot += len(comp)
        ok += good
        print(f"{p.name:12s} {len(k.d):8d} B  slots={k.slots:3d} used={len(k.used):3d}  "
              f"header ends 0x{k.header_end:x}, first record 0x{first:x} "
              f"(+{first - k.header_end})")
        print(f"{'':12s} flags {sorted(set(k.flag[i] for i in k.used))}  "
              f"compressed {len(comp):3d}/{len(k.used):3d}, all exact: {good == len(comp)}")
        if a.file:
            print(f"{'':12s} decompressed sizes: {dict(sizes.most_common(6))}")
    print(f"\ncompressed records decoding exactly: {ok}/{tot}")


if __name__ == "__main__":
    main()
