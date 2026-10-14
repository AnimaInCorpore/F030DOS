#!/usr/bin/env python3
"""P4.2: re-encode Z_TIE__.EXE's LE fixup tables and verify byte for byte.

  python3 work/build_fixups.py

The fixup page table and the 27,438 fixup records are 240 KB -- the largest
region work/build_ztie.py still copies verbatim. work/audit_fixups.py already
decodes them; this re-encodes each record from those decoded fields and compares
against the original bytes, the same ratchet idea applied to data instead of
instructions. A record that does not round-trip is reported with its offset, so
the failure is localised rather than "the table differs".
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_fixups as af          # noqa: E402  (prints its header on import)


def encode(rec):
    """Re-encode one decoded fixup record. Mirrors audit_fixups.decode_page."""
    src, flags = rec["src"], rec["flags"]
    stype, tt = rec["stype"], rec["tt"]
    srclist = bool(src & 0x20)
    out = bytearray((src, flags))
    if srclist:
        out.append(len(rec["srcoffs"]))
    else:
        out += struct.pack("<h", rec["srcoffs"][0])
    if tt == 0:
        if flags & 0x40:
            out += struct.pack("<H", rec["objn"])
        else:
            out.append(rec["objn"])
        if stype == 2:
            pass
        elif flags & 0x10:
            out += struct.pack("<I", rec["toff"])
        else:
            out += struct.pack("<H", rec["toff"])
    elif tt == 1:
        if flags & 0x40:
            out += struct.pack("<H", rec["objn"])
        else:
            out.append(rec["objn"])
        if flags & 0x80:
            out.append(rec["toff"])
        elif flags & 0x10:
            out += struct.pack("<I", rec["toff"])
        else:
            out += struct.pack("<H", rec["toff"])
    if rec["additive"]:
        if flags & 0x20:
            out += struct.pack("<I", rec["add"])
        else:
            out += struct.pack("<H", rec["add"])
    if srclist:
        for so in rec["srcoffs"]:
            out += struct.pack("<h", so)
    return bytes(out)


def rebuild():
    """-> (fixup page table bytes, fixup record table bytes, (lo,hi) of each)."""
    fpt_lo, fpt_hi = af.fpt, af.fpt + 4 * (af.num_pages + 1)
    fpt = b"".join(struct.pack("<I", af.fpe[i]) for i in range(af.num_pages + 1))
    parts = []
    for i in range(af.num_pages):
        recs, _s, _e = af.decode_page(i)
        for r in recs:
            parts.append(encode(r))
    frt_lo = af.frt + af.fpe[0]
    frt_hi = af.frt + af.fpe[af.num_pages]
    return fpt, b"".join(parts), (fpt_lo, fpt_hi), (frt_lo, frt_hi)


def main():
    data = af.data
    frt = af.frt

    # 1. fixup page table: num_pages+1 u32 entries
    fpt_lo, fpt_hi = af.fpt, af.fpt + 4 * (af.num_pages + 1)
    rebuilt_fpt = b"".join(struct.pack("<I", af.fpe[i]) for i in range(af.num_pages + 1))
    fpt_ok = rebuilt_fpt == data[fpt_lo:fpt_hi]
    print(f"fixup page table  {fpt_lo:#08x}..{fpt_hi:#08x}  "
          f"{fpt_hi - fpt_lo:>7} B  round-trips: {fpt_ok}")

    # 2. fixup records, page by page
    total = ok = 0
    bad = []
    parts = []
    for i in range(af.num_pages):
        recs, start, end = af.decode_page(i)
        for r in recs:
            total += 1
            enc = encode(r)
            orig = data[r["off"]:r["off"] + r["size"]]
            parts.append(enc)
            if enc == orig:
                ok += 1
            elif len(bad) < 8:
                bad.append((r["off"], orig.hex(" "), enc.hex(" ")))
    frt_lo, frt_hi = frt + af.fpe[0], frt + af.fpe[af.num_pages]
    rebuilt_frt = b"".join(parts)
    frt_ok = rebuilt_frt == data[frt_lo:frt_hi]
    print(f"fixup records     {frt_lo:#08x}..{frt_hi:#08x}  "
          f"{frt_hi - frt_lo:>7} B  {ok}/{total} records round-trip, "
          f"whole table: {frt_ok}")
    for off, o, e in bad:
        print(f"    MISMATCH @{off:#08x}\n      orig {o}\n      enc  {e}")

    span = fpt_hi - fpt_lo + (frt_hi - frt_lo)
    print(f"\nregenerable from decoded structures: {span} B "
          f"of the 241,072 B LE region ({100*span/241072:.1f}%)")
    return 0 if (fpt_ok and frt_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
