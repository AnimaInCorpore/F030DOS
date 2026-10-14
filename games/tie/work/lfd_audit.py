#!/usr/bin/env python3
"""Whole-tree LFD audit: container invariants + payload decode for every record.

  python3 work/lfd_audit.py [root]      # default: game/SWTieCD/TIECD

Prints the record-type census and, for each decoded type, how many records the
model in work/lfd_delt.py accepts.  Any FAIL line is a broken invariant --
this is the regression check behind analysis/LFD.md.
"""
import collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lfd
from lfd_delt import (decode_delt, decode_anim, decode_pltt, decode_panl,
                      decode_text, decode_film, decode_ship_header,
                      check_voc, check_gmid)

DECODERS = {
    "DELT": lambda r, w: decode_delt(r.data),
    "ANIM": lambda r, w: decode_anim(r.data),
    "PLTT": lambda r, w: decode_pltt(r.data),
    "PANL": lambda r, w: decode_panl(r.data),
    "TEXT": lambda r, w: decode_text(r.data),
    "VOIC": lambda r, w: check_voc(r.data),
    "BLAS": lambda r, w: check_voc(r.data),
    "GMID": lambda r, w: check_gmid(r.data),
    "FILM": lambda r, w: decode_film(r.data),
    "SHIP": lambda r, w: decode_ship_header(r.data),
}


def main(root):
    files = rmap = norrmap = 0
    census = collections.Counter()
    ok = collections.Counter()
    fails = []
    for path in lfd.iter_lfd(root):
        files += 1
        try:
            records, entries = lfd.load(path)
        except ValueError as exc:
            fails.append((path, "-", f"container: {exc}"))
            continue
        if entries is None:
            norrmap += 1
        else:
            rmap += 1
        width = 640 if os.sep + "CP640" + os.sep in path else 320
        for r in records:
            census[r.type] += 1
            dec = DECODERS.get(r.type)
            if dec is None:
                continue
            try:
                dec(r, width)
                ok[r.type] += 1
            except Exception as exc:
                fails.append((path, r.id, str(exc)))
    print(f"files: {files}   with RMAP index: {rmap}   without: {norrmap}")
    print("record census:")
    for t, n in census.most_common():
        mark = f"  decoded {ok[t]}/{n}" if t in DECODERS else ""
        print(f"   {t:5} {n:5}{mark}")
    print(f"failures: {len(fails)}")
    for f in fails[:20]:
        print("   FAIL", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "game/SWTieCD/TIECD"))
