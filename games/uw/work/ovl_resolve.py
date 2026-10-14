#!/usr/bin/env python3
"""Resolve UW.EXE overlay-pool far calls through the FBOV exeinfo table.

The operand before an overlay-pool far call is not a code segment.  It is a
byte offset into the 159-row FBOV segment table at 0x5D860.  The real image
target is therefore::

    seg  = u16[0x5D860 + V]
    file = 0x3200 + (seg << 4) + off

If that target is an INT 3Fh stub, the stub's two-byte descriptor selects an
entry in the corresponding pool unit::

    body = 0x66B40 + unit_pool_offset + descriptor

This is the UW1 counterpart of F030Underworld2/work/ovl_resolve.py.  It keeps
the key transfer from UW2 executable as a small, independently testable tool.

Usage:
  python work/ovl_resolve.py 0x70:0x066a
  python work/ovl_resolve.py 0x348:0x0084
  python work/ovl_resolve.py --table
  python work/ovl_resolve.py --audit
  python work/ovl_resolve.py --callers 0x1f4aa
"""
import argparse
import collections
import re
import struct
import sys
from pathlib import Path

EXE = Path("work/expanded/UW.EXE")
FUNCS = Path("work/ghidra_export/functions.txt")
HDRSZ = 0x3200
FBOV = 0x66B30
POOLCODE = 0x66B40
EXEINFO = 0x5D860
NSEG = 159

d = EXE.read_bytes()


def exeinfo(v):
    """Return the image segment for exeinfo byte offset *v*, if valid."""
    if v % 8 or not 0 <= v // 8 < NSEG:
        return None
    return struct.unpack_from("<H", d, EXEINFO + v)[0]


def resolve(v, off):
    seg = exeinfo(v)
    if seg is None:
        return None, None
    return seg, HDRSZ + (seg << 4) + off


def func_entries():
    """Return file offsets of exported image and pool function entries."""
    ents = set()
    if not FUNCS.exists():
        return ents
    for line in FUNCS.read_text().splitlines():
        m = re.match(r"([0-9a-fA-F]{4}):([0-9a-fA-F]{4})", line)
        if m:
            seg, off = (int(x, 16) for x in m.groups())
            fa = HDRSZ + ((seg - 0x1000) << 4) + off
            if 0 <= fa < len(d):
                ents.add(fa)
            continue
        m = re.match(r"CODE_TAIL::([0-9a-fA-F]{6})", line)
        if m:
            fa = int(m.group(1), 16)
            if 0 <= fa < len(d):
                ents.add(fa)
    return ents


def call_sites():
    """Yield every byte-pattern lcall in the pool (naive 0x9A scan)."""
    pool = d[POOLCODE:]
    for m in re.finditer(re.escape(b"\x9a"), pool):
        o = m.start()
        if o + 5 > len(pool):
            continue
        off = int.from_bytes(pool[o + 1:o + 3], "little")
        v = int.from_bytes(pool[o + 3:o + 5], "little")
        yield v, off, POOLCODE + o


def overlay_body(fa):
    """Return (pool body file offset, descriptor) for an INT 3Fh stub."""
    if fa is None or not 0 <= fa < len(d) - 4 or d[fa:fa + 2] != b"\xcd\x3f":
        return None, None
    desc = struct.unpack_from("<H", d, fa + 2)[0]
    # UW1 stub headers have a u16 entry count at +0x0c and 5-byte thunks
    # beginning at +0x20.  Walk back to the owning table header.
    for k in range(4000):
        base = fa - 0x20 - 5 * k
        if base < 0:
            break
        if d[base:base + 2] == b"\xcd\x3f" and struct.unpack_from("<H", d, base + 2)[0] == 0:
            nent = struct.unpack_from("<H", d, base + 0x0c)[0]
            if k < nent:
                pool_off = struct.unpack_from("<I", d, base + 4)[0]
                return POOLCODE + pool_off + desc, desc
            break
    return None, desc


def overlay_blocks():
    """Yield (row, V, segment, stub-header-file-offset) for type-3 rows."""
    for row in range(NSEG):
        seg, size, typ, _flags = struct.unpack_from("<4H", d, EXEINFO + row * 8)
        if typ != 3:
            continue
        base = HDRSZ + (seg << 4)
        if d[base:base + 2] == b"\xcd\x3f":
            yield row, row * 8, seg, base


def classify(fa, entries):
    if fa is None or not 0 <= fa < len(d):
        return "unresolved"
    if d[fa:fa + 2] == b"\xcd\x3f":
        return "INT 3Fh stub"
    if fa in entries:
        return "function entry"
    if d[fa:fa + 3] == b"\x55\x8b\xec":
        return "prologue"
    if fa >= POOLCODE:
        return "in pool"
    return "other image"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="V:off, e.g. 0x70:0x066a")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--callers", help="file address, e.g. 0x1f4aa")
    ap.add_argument("--entries", action="store_true",
                    help="list every overlay function entry reached by a stub")
    a = ap.parse_args()
    entries = func_entries()

    if a.table:
        print(f"{'V':>7} {'idx':>4} {'seg':>7} {'seg file base':>14}")
        for row in range(NSEG):
            v = row * 8
            seg = struct.unpack_from("<H", d, EXEINFO + v)[0]
            print(f"{v:#7x} {row:4} {seg:#7x} {HDRSZ + (seg << 4):#14x}")
        return

    if a.audit:
        counts = collections.Counter()
        total = 0
        for v, off, _site in call_sites():
            _seg, fa = resolve(v, off)
            counts[classify(fa, entries)] += 1
            total += 1
        print(f"{total} pool call sites")
        for label, n in counts.most_common():
            print(f"{n:7} {100 * n / total:5.1f}%  {label}")
        return

    if a.entries:
        seen = {}
        for row, v, seg, base in overlay_blocks():
            nent = struct.unpack_from("<H", d, base + 0x0c)[0]
            for k in range(nent):
                stub = base + 0x20 + k * 5
                if d[stub:stub + 2] != b"\xcd\x3f":
                    break
                body, desc = overlay_body(stub)
                if body is not None:
                    seen[body] = (row, v, seg, k, desc, stub)
        print(f"{len(seen)} distinct overlay function entries")
        for body in sorted(seen):
            row, v, seg, k, desc, stub = seen[body]
            print(f"  {body:#08x}  row {row:3} (V={v:#06x}, seg={seg:#06x}) "
                  f"stub {k:3} desc {desc:#06x} @ {stub:#08x}")
        return

    if a.callers:
        want = int(a.callers, 0)
        hits = []
        for v, off, site in call_sites():
            _seg, fa = resolve(v, off)
            if fa == want:
                hits.append((v, off, site, "direct"))
                continue
            body, _desc = overlay_body(fa)
            if body == want:
                hits.append((v, off, site, "via stub"))
        print(f"{len(hits)} pool call sites target file {want:#08x}")
        for v, off, site, how in hits[:100]:
            print(f"  site {site:#08x}  lcall {v:#06x}:{off:#06x}  [{how}]")
        return

    if not a.target:
        sys.exit("give V:off, or --table / --audit / --callers / --entries")
    vs, os_ = a.target.split(":")
    v, off = int(vs, 0), int(os_, 0)
    seg, fa = resolve(v, off)
    if seg is None:
        sys.exit(f"{v:#x} is not a valid exeinfo byte offset "
                 f"(must be a multiple of 8, index < {NSEG})")
    print(f"lcall {v:#06x}:{off:#06x}")
    print(f"  exeinfo[{v:#x}] (idx {v // 8}) = segment {seg:#06x}")
    print(f"  file {fa:#08x}  [{classify(fa, entries)}]")
    if d[fa:fa + 2] == b"\xcd\x3f":
        body, desc = overlay_body(fa)
        print(f"  overlay stub, call descriptor {desc:#06x}")
        if body is not None:
            tag = "prologue" if d[body:body + 3] == b"\x55\x8b\xec" else "?"
            print(f"  -> overlay body at file {body:#08x}  [{tag}]")


if __name__ == "__main__":
    main()
