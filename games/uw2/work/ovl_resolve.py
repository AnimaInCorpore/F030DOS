#!/usr/bin/env python3
"""Resolve overlay-pool far calls to image addresses via the FBOV exeinfo table.

THE RULE (ghidra.md S19, established 2026-08-23):

    Overlay-pool code far-calls as `lcall V:off`, where V is NOT a segment. It
    is the **byte offset into the FBOV `exeinfo` table** at file 0x66B40 (the
    overlay manager's DS:0x01A0, ghidra.md S15). The real image segment is the
    u16 stored there:

        seg  = u16 at 0x66B40 + V          (V must be a multiple of 8, V/8 < 174)
        file = 0x2E00 + (seg << 4) + off

This supersedes AGENTS.md's earlier conclusion that those small V values were
"a separate namespace resolved by the overlay manager at load time" and could
not be mapped statically. They can: 95% of the pool's 4,269 call sites land on
a known function entry, an INT 3Fh stub, or a `push bp; mov bp,sp` prologue.

Targets that land on `CD 3F` are calls into an overlay, routed through the
resident stub block. Those resolve the rest of the way (ghidra.md S20). Each
overlay has a resident block at `0x2E00 + (seg << 4)`:

    +0x00  u16    CD 3F           the block's own trap
    +0x02  u16    0x0000
    +0x04  u32    the overlay's code offset within the pool
    +0x08  u16    the overlay's size in bytes
    +0x0a  u16    (not identified)
    +0x0c  u32    stub count
    +0x10  16 B   runtime descriptor -- zero in the file (S15's +0x10/+0x18/+0x1a)
    +0x20  5 B x N  stub table:  CD 3F <u16 descriptor> 00

and the body of stub k is

    file = 0x71B90 + hdr[+0x04] + descriptor        (0x71B90 = pool + its 16-byte header)

All **930** stubs in the binary resolve to a `push bp; mov bp,sp` prologue
under that formula.

Usage:
  python work/ovl_resolve.py 0x18:0x48f4      # resolve one V:off
  python work/ovl_resolve.py --table          # dump the 174 exeinfo entries
  python work/ovl_resolve.py --audit          # classify every pool call site
  python work/ovl_resolve.py --callers 0x7F44 # which pool sites call this file addr
"""
import argparse
import collections
import re
import struct
import sys
from pathlib import Path

EXE = Path("work/extracted/D3/UW2.EXE")
FUNCS = Path("work/ghidra_export/functions.txt")
EXEINFO = 0x66B40
NSEG = 174
POOL = 0x71B80
POOLCODE = 0x71B90  # the pool's own 16-byte header precedes the code
IMGBASE = 0x2E00
SKEW = 0xD200

d = EXE.read_bytes()


def exeinfo(v):
    """Image segment for table byte-offset v, or None if v is not a valid offset."""
    if v % 8 or not 0 <= v // 8 < NSEG:
        return None
    return struct.unpack_from("<H", d, EXEINFO + v)[0]


def resolve(v, off):
    seg = exeinfo(v)
    if seg is None:
        return None, None
    return seg, IMGBASE + (seg << 4) + off


def func_entries():
    ents = set()
    if not FUNCS.exists():
        return ents
    for line in FUNCS.read_text().splitlines():
        m = re.match(r"([0-9a-f]{4}):([0-9a-f]{4})", line)
        if m:
            fa = int(m.group(1), 16) * 16 + int(m.group(2), 16) - SKEW
            if 0 <= fa < len(d):
                ents.add(fa)
    return ents


def call_sites():
    """Every (V, off, file-address-of-site) in the pool. Naive 0x9A scan."""
    pool = d[POOL:]
    for m in re.finditer(re.escape(b"\x9a"), pool):
        o = m.start()
        if o + 5 > len(pool):
            continue
        off = int.from_bytes(pool[o + 1:o + 3], "little")
        v = int.from_bytes(pool[o + 3:o + 5], "little")
        yield v, off, POOL + o


def overlay_body(fa):
    """For a file address that is an INT 3Fh stub, the pool address it reaches.

    Walks back to the owning block header: stubs start at +0x20 on a 5-byte
    stride, so the header base is the stub address minus 0x20 minus 5*k.
    """
    if d[fa:fa + 2] != b"\xcd\x3f":
        return None, None
    desc = struct.unpack_from("<H", d, fa + 2)[0]
    for k in range(4000):
        base = fa - 0x20 - 5 * k
        if base < 0:
            return None, desc
        if d[base:base + 2] == b"\xcd\x3f" and struct.unpack_from("<H", d, base + 2)[0] == 0:
            n = struct.unpack_from("<I", d, base + 0xc)[0]
            if k < n:
                return POOLCODE + struct.unpack_from("<I", d, base + 4)[0] + desc, desc
            return None, desc
    return None, desc


def overlay_blocks():
    """(index, V, segment, header file address) for every exeinfo overlay block."""
    for i in range(NSEG):
        seg = struct.unpack_from("<H", d, EXEINFO + i * 8)[0]
        b = IMGBASE + (seg << 4)
        if 0 <= b < len(d) - 0x20 and d[b:b + 2] == b"\xcd\x3f":
            yield i, i * 8, seg, b


def classify(fa, ents):
    if fa is None or not 0 <= fa < len(d):
        return "unresolved"
    if d[fa:fa + 2] == b"\xcd\x3f":
        return "INT 3Fh stub"
    if fa in ents:
        return "function entry"
    if d[fa:fa + 3] == b"\x55\x8b\xec":
        return "prologue"
    if fa >= POOL:
        return "in pool"
    return "other image"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="V:off, e.g. 0x18:0x48f4")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--callers", help="file address, e.g. 0x7F44")
    ap.add_argument("--entries", action="store_true",
                    help="emit every overlay function entry the stubs reach")
    a = ap.parse_args()
    ents = func_entries()

    if a.table:
        print(f"{'V':>7} {'idx':>4} {'seg':>7} {'seg file base':>14}")
        for i in range(NSEG):
            v = i * 8
            seg = struct.unpack_from("<H", d, EXEINFO + v)[0]
            print(f"{v:#7x} {i:4} {seg:#7x} {IMGBASE + (seg << 4):#14x}")
        return

    if a.audit:
        cls = collections.Counter()
        for v, off, _ in call_sites():
            _, fa = resolve(v, off)
            cls[classify(fa, ents)] += 1
        tot = sum(cls.values())
        print(f"{tot} pool call sites")
        for k, n in cls.most_common():
            print(f"   {n:6}  {100 * n / tot:5.1f}%  {k}")
        return

    if a.entries:
        seen = {}
        for i, v, seg, b in overlay_blocks():
            n = struct.unpack_from("<I", d, b + 0xc)[0]
            if n > 4000:
                continue
            for k in range(n):
                sa = b + 0x20 + k * 5
                if d[sa:sa + 2] != b"\xcd\x3f":
                    break
                body, desc = overlay_body(sa)
                if body is not None:
                    seen[body] = (i, v, k, desc, sa)
        print(f"{len(seen)} distinct overlay function entries")
        for body in sorted(seen):
            i, v, k, desc, sa = seen[body]
            print(f"  {body:#08x}   overlay {i:3} (V={v:#06x}) stub {k:3} "
                  f"desc {desc:#06x}  stub@{sa:#08x}")
        return

    if a.callers:
        want = int(a.callers, 0)
        # A call into an overlay names the STUB, not the body, so resolve one
        # more hop before comparing -- otherwise every overlay function reports
        # zero callers.
        hits = []
        for v, off, site in call_sites():
            _, fa = resolve(v, off)
            if fa is None:
                continue
            if fa == want:
                hits.append((v, off, site, "direct"))
                continue
            body, _ = overlay_body(fa)
            if body == want:
                hits.append((v, off, site, "via stub"))
        print(f"{len(hits)} pool call sites target file {want:#08x}")
        for v, off, site, how in hits[:60]:
            print(f"   site {site:#08x}   lcall {v:#06x}:{off:#06x}   [{how}]")
        return

    if not a.target:
        sys.exit("give V:off, or --table / --audit / --callers")
    vs, os_ = a.target.split(":")
    v, off = int(vs, 0), int(os_, 0)
    seg, fa = resolve(v, off)
    if seg is None:
        sys.exit(f"{v:#x} is not a valid exeinfo byte offset "
                 f"(must be a multiple of 8, index < {NSEG})")
    print(f"lcall {v:#06x}:{off:#06x}")
    print(f"  exeinfo[{v:#x}] (idx {v // 8}) = segment {seg:#06x}")
    print(f"  file {fa:#08x}   [{classify(fa, ents)}]")
    if d[fa:fa + 2] == b"\xcd\x3f":
        body, desc = overlay_body(fa)
        print(f"  overlay stub, manager call descriptor {desc:#06x}")
        if body is not None:
            tag = "prologue" if d[body:body + 3] == b"\x55\x8b\xec" else "?"
            print(f"  -> overlay body at file {body:#08x}   [{tag}]")


if __name__ == "__main__":
    main()
