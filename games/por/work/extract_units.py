#!/usr/bin/env python3
"""Split GAME.OVR into per-unit images plus their entry-point lists, ready for
`make decompile`. Both come from the overlay directory in START.EXE, so nothing
here is guessed — see work/overlay.py.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from overlay import units                                       # noqa: E402

ovr = open(os.path.join(HERE, "expanded", "GAME.OVR"), "rb").read()
us, _ = units()
bins = os.path.join(HERE, "ghidra", "units")
ents = os.path.join(HERE, "ghidra", "entries")
os.makedirs(bins, exist_ok=True)
os.makedirs(ents, exist_ok=True)
for u in us:
    tag = f"unit{u['seg']:03X}"
    fo, cs = u["file_offset"], u["code_size"]
    open(os.path.join(bins, tag + ".bin"), "wb").write(ovr[fo:fo + cs])
    with open(os.path.join(ents, tag + ".entries"), "w") as fh:
        for s in sorted({t for t in u["thunks"] if t < cs}):
            fh.write(f"{s:04x}\n")
print(f"{len(us)} unit images + entry lists written to work/ghidra/")
