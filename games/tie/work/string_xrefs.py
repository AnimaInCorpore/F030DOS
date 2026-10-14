#!/usr/bin/env python3
"""P1.3: cross-reference obj2 string literals to the obj1 functions using them.

  python3 work/string_xrefs.py [--annotate work/ghidra/obj1_notes.txt]

A string-pool cross-reference is one of the verified anchors UW1's method
allows (analysis/functions.md 4). This finds them mechanically: every fixup
whose TARGET lands inside a string typed by work/type_obj2.py is a code site
referencing that string; map the site to its enclosing function.

It names nothing by itself -- it produces evidence. What a function *does* with
a string it references is still an inference, so the output is an annotation
list, and only unambiguous cases should ever become names.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_fixups as af          # noqa: E402
import type_obj2                   # noqa: E402

OBJ2_BASE = 0xC0000


def string_at(blob, off):
    """The NUL-terminated string starting EXACTLY at `off`, or None.

    Read from the fixup target, not from the enclosing typed run: a binary
    table sitting immediately before a literal shares its run and its NUL, so
    run-based extraction reported "PPPPHHHHPPPHHHoptions.cfg" where the code
    actually points at "options.cfg".
    """
    n = len(blob)
    if off < 0 or off >= n:
        return None
    j = off
    while j < n and 0x20 <= blob[j] <= 0x7E:
        j += 1
    if j >= n or blob[j] != 0 or j - off < 4:
        return None
    return blob[off:j].decode("latin1")


def main():
    blob, kind, _lo, _hi = type_obj2.classify()

    fns = []
    for line in open("work/ghidra_export/obj1_functions.macos.txt"):
        q = line.split()
        if len(q) >= 4 and len(q[0]) == 8:
            try:
                fns.append((int(q[0], 16), int(q[1]), q[3]))
            except ValueError:
                pass
    fns.sort()
    fstarts = [a for a, _s, _n in fns]

    def owner(addr):
        import bisect
        i = bisect.bisect_right(fstarts, addr) - 1
        if i < 0:
            return None
        a, size, name = fns[i]
        return (a, name) if addr < a + max(size, 1) else None

    hits = collections.defaultdict(set)
    for i in range(af.num_pages):
        objn, _o = af.obj_of_page(i)
        if objn != 1:
            continue
        base = af.linear_of_page(i)
        recs, _s, _e = af.decode_page(i)
        for r in recs:
            if r["tt"] != 0 or r["objn"] != 2:
                continue
            text = string_at(blob, r["toff"])
            if text is None:
                continue
            for so in r["srcoffs"]:
                ow = owner(base + so)
                if ow:
                    hits[ow].add(text)

    print(f"distinct strings referenced from code: "
          f"{len({t for v in hits.values() for t in v})}")
    print(f"obj1 functions referencing at least one: {len(hits)} of {len(fns)}")
    single = {k: v for k, v in hits.items() if len(v) == 1}
    print(f"  of which reference exactly one string: {len(single)}")
    unnamed = {k: v for k, v in hits.items() if k[1].startswith("FUN_")}
    print(f"  still unnamed (FUN_*): {len(unnamed)}")

    if "--annotate" in sys.argv:
        out = sys.argv[sys.argv.index("--annotate") + 1]
        with open(out, "w") as fh:
            for (addr, name), texts in sorted(hits.items()):
                joined = " | ".join(sorted(texts)[:6])[:200].replace("\n", " ")
                fh.write(f"0x{addr:08x}\t{name}\t{joined}\n")
        print(f"\nwrote {out} ({len(hits)} annotations)")

    print("\nsample -- unnamed functions with exactly one string reference:")
    shown = 0
    for (addr, name), texts in sorted(single.items()):
        if not name.startswith("FUN_"):
            continue
        t = list(texts)[0]
        if len(t) < 8:
            continue
        print(f"   {addr:#08x}  {t[:60]!r}")
        shown += 1
        if shown >= 12:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
