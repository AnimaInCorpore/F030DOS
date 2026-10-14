#!/usr/bin/env python3
"""A call graph for UW2.EXE, built from raw bytes rather than from Ghidra.

Ghidra reports `inrefs=0` for **1,044 of 2,239** functions -- it loses the
trail wherever a call is computed, or crosses into the overlay pool. Scanning
the file for call opcodes and resolving them arithmetically recovers a large
part of that, which is what a semantic pass needs: once one function is named,
its callers are the next things worth reading.

Two opcodes are scanned:

  9A off seg   far call  -> file = 0x2E00 + (seg << 4) + off
  E8 rel16     near call -> file = site + 3 + rel   (near calls cannot leave
                            their segment, and blocks are contiguous in the
                            file, so file-space arithmetic is valid)

**This is a candidate graph, not a disassembly.** A byte scan cannot tell an
opcode from data that happens to be 0x9A or 0xE8. The filter that makes it
usable is requiring the target to land *exactly* on a known function start;
see --stats for the resulting noise estimate, which runs around 1%.

Two things it cannot see, both stated rather than papered over:
  * calls through Borland's INT 3Fh overlay thunks (`CALLF 0x0000:xxxx` in
    Ghidra's export) -- the thunk's target lives in the overlay pool and has
    no fixed file address, so these edges are simply absent;
  * computed/indirect calls, the same ones Ghidra misses.

Usage:
  python work/callgraph.py --stats
  python work/callgraph.py --callers 0x75863
  python work/callgraph.py --callees 0x74e15
  python work/callgraph.py --orphans          # Ghidra inrefs=0 but reachable here
"""
import argparse
import bisect
import collections
import re
import struct
from pathlib import Path

EXE = Path("work/extracted/D3/UW2.EXE")
FUNCS = Path("work/ghidra_export/functions.txt")
SKEW = 0xD200
HDR = 0x2E00


def functions():
    out = []
    for line in FUNCS.read_text().splitlines():
        m = re.match(r"([0-9a-f]{4}):([0-9a-f]{4})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)", line)
        if m:
            out.append((int(m.group(1), 16) * 16 + int(m.group(2), 16) - SKEW,
                        m.group(5), int(m.group(4))))
            continue
        m = re.match(r"CODE_TAIL::([0-9a-f]+)\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)", line)
        if m:
            out.append((int(m.group(1), 16), m.group(4), int(m.group(3))))
    out.sort()
    return out


def build(d, funcs):
    starts = [f[0] for f in funcs]
    fset = set(starts)

    def owner(o):
        k = bisect.bisect_right(starts, o) - 1
        return starts[k] if k >= 0 else None

    sites = []
    for m in re.finditer(re.escape(b"\x9a"), d):
        o = m.start()
        if o + 5 <= len(d):
            off, seg = struct.unpack_from("<HH", d, o + 1)
            sites.append((o, HDR + (seg << 4) + off, "far"))
    for m in re.finditer(re.escape(b"\xe8"), d):
        o = m.start()
        if o + 3 <= len(d):
            sites.append((o, o + 3 + struct.unpack_from("<h", d, o + 1)[0], "near"))
    callers = collections.defaultdict(set)
    callees = collections.defaultdict(set)
    kept = 0
    for o, t, kind in sites:
        if t in fset:
            c = owner(o)
            if c is not None:
                callers[t].add(c)
                callees[c].add(t)
                kept += 1
    return callers, callees, len(sites), kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--callers")
    ap.add_argument("--callees")
    ap.add_argument("--orphans", action="store_true")
    a = ap.parse_args()
    d = EXE.read_bytes()
    funcs = functions()
    names = {f[0]: f[1] for f in funcs}
    ghidra = {f[0]: f[2] for f in funcs}
    callers, callees, nsites, kept = build(d, funcs)

    if a.callers or a.callees:
        t = int((a.callers or a.callees), 0)
        src = callers if a.callers else callees
        rel = "callers of" if a.callers else "callees of"
        print(f"{rel} {t:#07x} {names.get(t, '(not a known function start)')}")
        for x in sorted(src.get(t, ())):
            print(f"   {x:#08x}  {names.get(x, '?'):32s} ghidra_inrefs={ghidra.get(x, '?')}")
        return

    if a.orphans:
        rec = sorted(t for t in callers if ghidra.get(t, 0) == 0)
        print(f"{len(rec)} functions Ghidra called unreferenced that have a "
              f"resolvable caller here:")
        for t in rec[:40]:
            print(f"   {t:#08x}  {names.get(t,'?'):32s} "
                  f"{len(callers[t])} caller(s)")
        if len(rec) > 40:
            print(f"   ... and {len(rec)-40} more")
        return

    expected = nsites * len(funcs) / len(d)
    print(f"{EXE}: {len(funcs)} functions")
    print(f"  call-opcode candidates scanned : {nsites}")
    print(f"  edges landing on a function start: {kept}")
    print(f"  distinct callees               : {len(callers)}")
    print(f"  Ghidra inrefs=0 overall        : {sum(1 for f in funcs if f[2] == 0)}"
          f"/{len(funcs)}")
    print(f"  of those, reachable here       : "
          f"{sum(1 for t in callers if ghidra.get(t, 0) == 0)}")
    print(f"  expected chance hits           : ~{expected:.0f} of {kept} "
          f"({100*expected/kept:.1f}%) -- a random byte pointing exactly at one "
          f"of {len(funcs)} starts")


if __name__ == "__main__":
    main()
