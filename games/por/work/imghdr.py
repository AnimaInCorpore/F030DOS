#!/usr/bin/env python3
"""Scan every 17-byte Gold Box image header and check the two trailing fields
resolved from the DOS code (`analysis/executables.md` §Unit `18E`,
`entry_24ED`/`entry_02AD`/`entry_007B`):

    u16LE height
    u16LE widthBytes
    u32LE 0             zero except TITLE.DAX blocks 0x01/0x02 (= 1)
    u8    frameCount     repeat count for multi-element blocks
    8 B   cgaRemap       16-entry x 4-bit CGA colour-reduction table

Checks, across every `.DAX` image block, `.PIC` frame and bare `BODY*`/`HEAD*`
file in `work/expanded/`:
  - the "zero" field is 0, flagging the known TITLE.DAX exception separately
  - every cgaRemap nibble is in 0-3 (a CGA colour-reduction table can only
    ever produce 4 values; a wider range would disprove the reading)

Usage: python3 work/imghdr.py
"""
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dax

EXPANDED = os.path.join(os.path.dirname(HERE), "work", "expanded")
KNOWN_NONZERO = {("TITLE.DAX", 0x01), ("TITLE.DAX", 0x02)}


def headers():
    """Yield (source, tag, 17-byte header) for every image header found."""
    for f in sorted(os.listdir(EXPANDED)):
        p = os.path.join(EXPANDED, f)
        if f.upper().endswith(".DAX"):
            try:
                _, _, blks = dax.blocks(p)
            except Exception:
                continue
            for bid, off, unp, pak, raw in blks:
                data = dax.unrle(raw, unp)
                if len(data) < 17:
                    continue
                h, wb = struct.unpack_from("<HH", data, 0)
                stride = h * wb * 4
                if h and wb and stride and (len(data) - 17) % stride == 0:
                    yield f, bid, data[0:17]
        elif f.upper().startswith(("BODY", "HEAD")):
            data = open(p, "rb").read()
            if len(data) >= 17:
                yield f, None, data[0:17]
        elif f.upper().startswith("PIC") and f.upper().endswith(".PIC"):
            data = open(p, "rb").read()
            for i in range(data[0]):
                base = 1 + i * 3893
                hdr = data[base + 4: base + 4 + 17]
                if len(hdr) == 17:
                    yield f, i, hdr


def main():
    total = bad = 0
    frame_counts = collections.Counter()
    for src, tag, hdr in headers():
        total += 1
        h, wb, zero = struct.unpack_from("<HHI", hdr, 0)
        frame_count = hdr[8]
        remap = hdr[9:17]
        frame_counts[frame_count] += 1
        if zero != 0 and (src, tag) not in KNOWN_NONZERO:
            print(f"ZERO     {src} tag={tag} zero field=0x{zero:08x} (unexpected)")
            bad += 1
        nibbles = [b >> 4 for b in remap] + [b & 0xF for b in remap]
        if max(nibbles) > 3:
            print(f"REMAP    {src} tag={tag} nibble out of 0-3: {remap.hex()}")
            bad += 1
    print(f"{total} headers, {total - bad} OK, {bad} bad")
    print(f"frameCount distribution: {dict(sorted(frame_counts.items()))}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
