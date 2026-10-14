#!/usr/bin/env python3
"""P1.3 -- build per-object Ghidra function-start seed lists.

Two independent seed sources, converted to linear addresses under each
object's own base (analysis/ztie.md SS4):
  1. analysis/32bit/functable_v2.txt -- 4,030 capstone recursive-descent
     starts (file offsets, already true file offsets -- work/README.md
     "Address conventions").
  2. work/audit_fixups.py's decoded fixup table -- 27,438 records, all
     'internal' targets (verified via --stats: 100% internal/32-bit-offset).
     Each target is already (objn, obj-relative-offset); a fixup target is a
     real cross-reference site, not necessarily a function start, but a very
     high-precision seed set (every one is something else's operand).

Output: work/ghidra/obj{1,2}_seeds.txt, one hex linear address per line,
sorted, deduplicated, bounds-checked against that object's own [base, base+vsize).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import audit_fixups as af  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUNCTABLE = os.path.join(ROOT, "analysis", "32bit", "functable_v2.txt")
OUT_DIR = os.path.join(os.path.dirname(__file__), "ghidra")

obj1, obj2 = af.objs
FILE1_START, FILE2_START = 0x3D800, 0xE8800
FILE2_END = FILE2_START + 0x13547  # physical EOF; BSS carries no seeds
assert af.page_file_off(obj1["first"] - 1) == FILE1_START
assert af.page_file_off(obj2["first"] - 1) == FILE2_START

seeds1, seeds2 = set(), set()


def add_from_file_offset(fo):
    if FILE1_START <= fo < FILE2_START:
        seeds1.add(obj1["base"] + (fo - FILE1_START))
    elif FILE2_START <= fo < FILE2_END:
        seeds2.add(obj2["base"] + (fo - FILE2_START))
    # else: outside both objects (MZ stub / LE header / fixup tables) -- not a seed


# Source 1: sweep starts
n_rows = 0
with open(FUNCTABLE) as f:
    for line in f:
        parts = line.split()
        if not parts or not parts[0].startswith("0x"):
            continue
        n_rows += 1
        add_from_file_offset(int(parts[0], 16))

# Source 2: fixup targets (all internal, objn/toff already object-relative)
n_fixups = 0
for i in range(af.num_pages):
    recs, _, _ = af.decode_page(i)
    for r in recs:
        if r["tt"] != 0:  # internal only (stats already showed 100%, but don't assume silently)
            continue
        n_fixups += len(r["srcoffs"])
        objn, toff = r["objn"], r["toff"]
        if objn == 1 and 0 <= toff < obj1["vsize"]:
            seeds1.add(obj1["base"] + toff)
        elif objn == 2 and 0 <= toff < obj2["vsize"]:
            seeds2.add(obj2["base"] + toff)

os.makedirs(OUT_DIR, exist_ok=True)
for name, seeds, base, vsize in (("obj1", seeds1, obj1["base"], obj1["vsize"]),
                                  ("obj2", seeds2, obj2["base"], obj2["vsize"])):
    bad = [s for s in seeds if not (base <= s < base + vsize)]
    assert not bad, (name, [hex(b) for b in bad[:5]])
    path = os.path.join(OUT_DIR, f"{name}_seeds.txt")
    with open(path, "w") as f:
        for s in sorted(seeds):
            f.write("0x%X\n" % s)
    print(f"{name}: {len(seeds)} unique seeds -> {path}")

print(f"(from {n_rows} sweep rows, {n_fixups} fixup source sites)")
