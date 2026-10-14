#!/usr/bin/env python3
"""Check a claimed instruction really occurs in a function. Trust, then verify.

Names arriving from anywhere other than one's own reading -- a subagent, a
teammate, a community wiki -- carry the same risk this project's grounding rule
exists for: a plausible sentence that no instruction supports. This makes
checking cheap enough that there is no excuse for skipping it.

  python work/verify_claim.py 0x13147 "cmp si, 0x58"
  python work/verify_claim.py --batch claims.txt      # "0xADDR<TAB>needle" lines
  python work/verify_claim.py --map 0x85:0x48f4=0x7F44 --from 0x7d36
  python work/verify_claim.py --map 0x18:0x48f4=0x7F44 --from 0x93d47   # refused

--map checks a claimed `SEG:OFF -> file address` mapping by recomputing it. A
parallel reading pass once asserted `0x18:0x48f4 -> 0x7F44`; the instruction it
cited was real, so the instruction check passed, but the mapping is arithmetic
and the arithmetic was wrong (`0x7874`). Instruction-level checking cannot see
a reasoning error -- this can. --from gives the CALL SITE, and if that site is
in the overlay pool the mapping is refused outright rather than computed,
because overlay segment numbers resolve at load time (ghidra.md 14).

A claim passes only if the needle EXACTLY equals an instruction in that function
(entry to first ret, bounded). Matching is on normalised text, so "cmp si,0x58"
and "cmp si, 0x58" are the same claim.
"""
import argparse
import re
import sys
from pathlib import Path

import capstone
import struct

EXE = Path("work/extracted/D3/UW2.EXE")
HDR = 0x2E00


def norm(s):
    return re.sub(r"\s+", "", s).lower()


def body(d, md, addr, limit=0x2000):
    """Disassemble a function.

    The limit was 0x300, which silently truncated large functions and produced
    false FAILs -- a claim about an instruction past the window looked like a
    disagreement with the binary when it was only a short scan. Raised, and
    check() now says when the scan ended on the limit rather than a return.
    """
    out = []
    hit_limit = True
    for i in md.disasm(d[addr:addr + limit], addr):
        out.append((i.address, f"{i.mnemonic} {i.op_str}"))
        if i.mnemonic in ("ret", "retf", "iret"):
            hit_limit = False
            break
    return out, hit_limit


def check(d, md, addr, needle):
    """Exact match on the whole normalised instruction text.

    Substring matching was the original behaviour and it produces FALSE
    PASSES: the needle "and al, 0xf" matches the instruction "and al, 0xf0",
    which is a different instruction. Any claim that only substring-matches is
    reported as a NEAR MISS, not a pass.
    """
    ins, hit_limit = body(d, md, addr)
    n = norm(needle)
    near = None
    for a, txt in ins:
        t = norm(txt)
        if n == t:
            return True, a, txt, len(ins), None
        if near is None and n in t:
            near = (a, txt)
    return False, None, None, (len(ins), hit_limit), near


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("addr", nargs="?")
    ap.add_argument("needle", nargs="?")
    ap.add_argument("--batch", type=Path)
    ap.add_argument("--map", help="SEG:OFF=EXPECTED, e.g. 0x85:0x48f4=0x7F44")
    ap.add_argument("--from", dest="site", help="file offset of the call site")
    a = ap.parse_args()
    d = EXE.read_bytes()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)

    if a.map:
        where, _, exp = a.map.partition("=")
        segtxt, _, offtxt = where.partition(":")
        seg, off, expected = int(segtxt, 0), int(offtxt, 0), int(exp, 0)
        image_end = ((struct.unpack_from("<H", d, 0x04)[0] - 1) * 512
                     + struct.unpack_from("<H", d, 0x02)[0])
        if a.site and int(a.site, 0) >= image_end:
            print(f"REFUSED  call site {int(a.site,0):#08x} is at/past the image "
                  f"end {image_end:#07x}: it is in the FBOV overlay pool, whose "
                  f"segment numbers resolve at load time. This mapping cannot be "
                  f"computed from the file at all.")
            return 1
        got = HDR + (seg << 4) + off
        ok = got == expected
        print(f"{'PASS' if ok else 'FAIL'}  {seg:#06x}:{off:#06x} -> computed "
              f"{got:#08x}, claimed {expected:#08x}")
        if not ok:
            print(f"        0x2E00 + ({seg:#x}<<4) + {off:#x} = {got:#x}")
        return 0 if ok else 1

    claims = []
    if a.batch:
        for line in a.batch.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                p = line.split("\t")
                if len(p) >= 2:
                    claims.append((int(p[0], 16), p[1]))
    elif a.addr:
        claims.append((int(a.addr, 0), a.needle))
    else:
        return print(__doc__)

    ok = 0
    for addr, needle in claims:
        good, at, txt, n, near = check(d, md, addr, needle)
        if good:
            ok += 1
            print(f"PASS {addr:#08x}  {needle!r} -> {at:#08x} {txt!r}")
        else:
            n_ins, hit_limit = n if isinstance(n, tuple) else (n, False)
            warn = "  [scan hit the size limit -- function may be longer]" if hit_limit else ""
            if near:
                print(f"FAIL {addr:#08x}  {needle!r} NOT FOUND exactly in {n_ins} "
                      f"instructions -- NEAR MISS at {near[0]:#08x} {near[1]!r} "
                      f"(substring only; not the same instruction){warn}")
            else:
                print(f"FAIL {addr:#08x}  {needle!r} NOT FOUND in {n_ins} instructions{warn}")
    print(f"\n{ok}/{len(claims)} claims verified")
    return 0 if ok == len(claims) else 1


if __name__ == "__main__":
    sys.exit(main())
