#!/usr/bin/env python3
"""Extract LFD image resources to PNG (todo P2.1).

  python3 work/lfd_extract.py <out_dir> <file.lfd> [more...]

DELT -> one PNG, ANIM -> one PNG per frame, PANL -> one PNG (320 or 640 wide,
picked from the CP320/CP640 directory the file sits in).

Palette: a record's colours are looked up in the palette built from this file's
own PLTT records.  A same-named PLTT is applied last if present, because most
LFDs carry several palettes and only one belongs to a given image (applying all
of them in file order recolours e.g. AWARDS.LFD's `medlroom` wrongly).  Which
PLTT the game actually loads when is driven by the FILM records -- still TBD.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lfd
from lfd_delt import (decode_delt, decode_anim, decode_pltt, decode_panl,
                      decode_film, write_png)


def film_palettes(records):
    """-> {(type, name) of a referenced record: [PLTT names its FILM loads]}.

    A FILM block list *is* the set of resources one scene uses, so it answers
    which palettes are live for a given image -- the question the same-name
    heuristic below only guesses at (analysis/LFD.md).  Frame-accurate ordering
    would need the chunk opcodes, which are still TBD, so the palettes are
    applied in block order.
    """
    out = {}
    for r in records:
        if r.type != "FILM":
            continue
        _ver, _frames, blocks = decode_film(r.data)
        plts = [n for t, n, _ in blocks if t == "PLTT"]
        for t, n, _ in blocks:
            if t in ("DELT", "ANIM", "CUST"):
                out.setdefault((t, n), plts)
    return out


def palette_for(records, rec, by_film):
    """Palette for one record: the PLTTs its FILM loads if it is in one, else
    every PLTT in the file; in both cases a same-named PLTT is applied last."""
    wanted = by_film.get((rec.type, rec.name))
    pal = [(0, 0, 0)] * 256
    for r in records:
        if r.type != "PLTT" or r.name == rec.name:
            continue
        if wanted is None or r.name in wanted:
            pal, _ = decode_pltt(r.data, pal)
    for r in records:
        if r.type == "PLTT" and r.name == rec.name:
            pal, _ = decode_pltt(r.data, pal)
    return pal


def _emit(out_dir, name, w, h, rows, pal):
    """Skip the two empty frames in the tree (ANIM:cursors frame 4 of
    EMPIRE.LFD / INSTALL.LFD: a 10-byte DELT, degenerate box, no spans)."""
    if w <= 0 or h <= 0:
        print(f"   skip {name}: empty frame, box {w}x{h}")
        return False
    write_png(os.path.join(out_dir, name + ".png"), w, h, rows, pal)
    return True


def main(out_dir, paths):
    os.makedirs(out_dir, exist_ok=True)
    written = 0
    for path in paths:
        records, _ = lfd.load(path)
        # Prefix with the parent dir and keep the extension: CP320/CAMERA.LFD
        # and CP640/CAMERA.LFD hold identically named records, and so do the
        # EMPEROR.LFD/.LFB twins.
        parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
        stem = parent + "_" + os.path.basename(path).replace(".", "_")
        by_film = film_palettes(records)
        for r in records:
            pal = palette_for(records, r, by_film)
            if r.type == "DELT":
                _l, _t, w, h, rows = decode_delt(r.data)
                if not _emit(out_dir, f"{stem}_{r.name}", w, h, rows, pal):
                    continue
                written += 1
            elif r.type == "ANIM":
                for i, (_l, _t, w, h, rows) in enumerate(decode_anim(r.data)):
                    if _emit(out_dir, f"{stem}_{r.name}_{i:03d}", w, h, rows, pal):
                        written += 1
            # PANL is deliberately NOT rendered: its pixel encoding is not
            # recoverable statically (analysis/LFD.md 5) and the earlier
            # renderer produced plausible-looking but wrong images.
    print(f"{written} PNGs -> {out_dir}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
