#!/usr/bin/env python3
"""Index the decompiled corpus: map every Ghidra function back to its overlay
unit and, where it is one, to the resident entry thunk that reaches it.

Phase 3 of the project plan is "know what every routine does". This produces the
worklist for that: 1,100-odd functions are unusable as a flat pile, but grouped
by unit and tagged with their resident entry identity they become tractable.

    python3 work/funcmap.py            # writes work/ghidra_export/index.txt
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from overlay import units                                       # noqa: E402

EXPORT = os.path.join(HERE, "ghidra_export")
ADDR = re.compile(r"^(\w+):(\w+)\s+(\S+)\s+body=(\d+)")


def main():
    us, _ = units()
    by_seg = {u["seg"]: u for u in us}
    rows = []
    total_fn = entry_fn = 0
    for u in us:
        tag = f"unit{u['seg']:03X}"
        path = os.path.join(EXPORT, f"{tag}.bin_functions.txt")
        if not os.path.exists(path):
            continue
        thunks = {t: i for i, t in enumerate(u["thunks"]) if t < u["code_size"]}
        for line in open(path):
            mo = ADDR.match(line.strip())
            if not mo:
                continue
            off = int(mo.group(2), 16)
            name, size = mo.group(3), int(mo.group(4))
            total_fn += 1
            idx = thunks.get(off)
            if idx is not None:
                entry_fn += 1
            rows.append((u["seg"], off, name, size, idx))

    out = os.path.join(EXPORT, "index.txt")
    with open(out, "w") as fh:
        fh.write("# unit:offset  size  entry#  name        (entry# = index in the "
                 "unit's resident INT 3Fh thunk table, '-' if internal)\n")
        for seg, off, name, size, idx in rows:
            fh.write(f"{seg:03X}:{off:04X}  {size:6d}  "
                     f"{('#%d' % idx) if idx is not None else '-':>5}  {name}\n")

    declared = sum(len([t for t in u["thunks"] if t < u["code_size"]]) for u in us)
    print(f"{total_fn} functions across {len(us)} units -> {out}")
    print(f"  {entry_fn} are resident entry points ({declared} usable thunks declared)")
    print(f"  {total_fn - entry_fn} are internal functions found by analysis")
    # largest unnamed functions are the best phase-3 targets
    big = sorted((r for r in rows if r[2].startswith("FUN_")), key=lambda r: -r[3])[:10]
    if big:
        print("  largest internal functions (phase-3 targets):")
        for seg, off, name, size, idx in big:
            print(f"    {seg:03X}:{off:04X}  {size:5d} B  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
