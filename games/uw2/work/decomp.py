#!/usr/bin/env python3
"""Pull one function's decompiled C out of the 12 MB Ghidra export, by file offset.

`work/ghidra_export/uw_c.c` has sat unused all session because there was no way
to find anything in it: it is keyed by `// @ seg:off` headers (and
`// @ CODE_TAIL::xxxxxx` for the overlay pool), not by the file offsets every
other tool here speaks. This indexes it once and looks functions up the way the
rest of the project addresses code.

  python work/decomp.py 0x1f955
  python work/decomp.py --index          # how many functions are actually in there

Reading the C is faster than raw disassembly **for most functions, not all**.
Measured over all 2,231: 63% are clean, 25% carry a Ghidra WARNING, 6% contain
bad-instruction data, and 18% are so full of `undefined2`/`extraout` that the
C is harder to read than the assembly. Ghidra struggles with 16-bit segmented
code, so this is not a defect in the export so much as the shape of the target.

Every lookup therefore prints a QUALITY line first, so a reader knows straight
away whether to trust the C or drop to `capstone`. And it is Ghidra's
reconstruction either way, not ground truth: anything load-bearing still gets
checked against the instructions with work/verify_claim.py.
"""
import argparse
import re
import sys
from pathlib import Path

SRC = Path("work/ghidra_export/uw_c.c")
SKEW = 0xD200


def index():
    """file offset -> (line number, header text)"""
    out = {}
    for n, line in enumerate(SRC.read_text(errors="replace").splitlines()):
        m = re.match(r"//\s*@\s*([0-9a-f]{4}):([0-9a-f]{4})\s*$", line)
        if m:
            out[int(m.group(1), 16) * 16 + int(m.group(2), 16) - SKEW] = (n, line)
            continue
        m = re.match(r"//\s*@\s*CODE_TAIL::([0-9a-f]+)\s*$", line)
        if m:
            out[int(m.group(1), 16)] = (n, line)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("addr", nargs="?")
    ap.add_argument("--index", action="store_true")
    ap.add_argument("--lines", type=int, default=120)
    a = ap.parse_args()
    idx = index()
    if a.index or not a.addr:
        print(f"{SRC}: {len(idx)} functions indexed")
        lo, hi = min(idx), max(idx)
        print(f"  file-offset range {lo:#08x}..{hi:#08x}")
        img = sum(1 for k in idx if k < 0x71B80)
        print(f"  in the mapped image: {img};  in the overlay pool: {len(idx)-img}")
        return
    want = int(a.addr, 0)
    if want not in idx:
        near = min(idx, key=lambda k: abs(k - want))
        print(f"no function starts exactly at {want:#08x}; nearest is {near:#08x} "
              f"({near-want:+d})")
        want = near
    start, hdr = idx[want]
    lines = SRC.read_text(errors="replace").splitlines()
    body = []
    for line in lines[start + 1:start + 1 + a.lines]:
        if re.match(r"//\s*@\s", line):
            break
        body.append(line)
    blob = "\n".join(body)
    warn = "WARNING" in blob
    bad = "bad instruction data" in blob or "halt_baddata" in blob
    undef = blob.count("undefined")
    if bad:
        q = "BAD -- contains bad-instruction data; do NOT trust this C, use capstone"
    elif warn or undef >= 10:
        q = (f"POOR -- {'Ghidra warning; ' if warn else ''}{undef} `undefined` "
             f"tokens; cross-read the disassembly")
    else:
        q = "OK -- no warnings; still verify anything load-bearing"
    print(f"// file {want:#08x}   {hdr}")
    print(f"// QUALITY: {q}")
    print(blob)


if __name__ == "__main__":
    main()
