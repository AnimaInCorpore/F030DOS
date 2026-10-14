#!/usr/bin/env python3
"""Map Z_TIE__.EXE's code object to its original C source modules (P1.3).

The image was built with assert()-style diagnostics, so obj2 holds the 38
source-file names of the LucasArts "X" presentation library (XFILM.C,
XACTDELT.C, ...).  Every reference to one of those strings is an LE fixup with
that string as its target, and the linker laid each module out contiguously --
so the span of a module's own reference sites bounds that module's code.

Each reference site is the imm32 of a `mov eax, <file>` in a call to the
(file, line) trace logger at 0x9F20C, and the preceding `mov edx, imm32` in the
same setup carries the SOURCE LINE NUMBER -- so the image yields (file, line)
pairs, not just file names.

    python3 work/module_map.py [--functions <ghidra_export.txt>] [--lines]
                               [--names <out.txt>]

Output: one line per module, [min..max] of its reference sites in obj1, with
overlap between modules reported (they should not overlap if the layout
assumption holds).  --lines adds the (file, line) anchor table and the
monotonicity check that validates it.  --names writes an "0xADDR<TAB>NAME" map
for every function that falls inside a module span, for TieNameByModule.java.

The names encode ONLY what the binary states: which translation unit a function
belongs to, and the lowest source line its own trace calls report. They say
nothing about what the function does -- that still needs a 4-style anchor.
"""
import os
import re
import collections
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_fixups as af          # noqa: E402  (prints its header on import)

NAME_RE = re.compile(rb"[A-Za-z0-9_\-]{1,20}\.[Cc]\x00")


def source_names(data):
    """-> {obj2 offset: filename} for every '*.C' string in the data object."""
    obj2 = af.objs[1]
    out = {}
    for m in NAME_RE.finditer(data):
        off = m.start()
        if not af.dpo <= off:
            continue
        lin = obj2["base"] + (off - 0xE8800)
        if obj2["base"] <= lin < obj2["base"] + obj2["vsize"]:
            out[lin - obj2["base"]] = m.group()[:-1].decode()
    return out


def reference_sites():
    """-> {(objn, target_off): [linear source addresses]} over every fixup."""
    sites = {}
    for idx0 in range(af.num_pages):
        n, _o = af.obj_of_page(idx0)
        if n != 1:                     # only code-object sources matter here
            continue
        base = af.linear_of_page(idx0)
        recs, _s, _e = af.decode_page(idx0)
        for rec in recs:
            if rec["tt"] != 0:
                continue
            key = (rec["objn"], rec["toff"])
            for so in rec["srcoffs"]:
                sites.setdefault(key, []).append(base + so)
    return sites


TRACE_LOGGER = 0x9F20C          # (file, line) logger; `ret 4`, it does return


def line_anchors(sites, names, raw, base=0x10000):
    """-> {module: [(linear addr, source line)]}.

    At each site the fixup patches the imm32 of `mov eax, <file>` (opcode B8 one
    byte earlier); the line is the imm32 of the nearest preceding
    `mov edx, imm32` (BA).  That back-scan is a heuristic -- its validation is
    the monotonicity check in main(): if it were mis-reading bytes, address
    order would not track line order.
    """
    out = collections.defaultdict(list)
    for off, name in names.items():
        for a in sites.get((2, off), []):
            s = a - 1 - base
            if s < 0 or raw[s] != 0xB8:
                continue
            for back in range(2, 26):
                p = s - back
                if p < 0:
                    break
                if raw[p] == 0xBA:
                    ln = struct.unpack_from("<I", raw, p + 1)[0]
                    if 0 < ln < 20000:
                        out[name].append((a, ln))
                    break
    return out


def main():
    data = af.data
    names = source_names(data)
    sites = reference_sites()
    mods = []
    for off, name in sorted(names.items()):
        addrs = sorted(sites.get((2, off), []))
        if not addrs:
            continue
        mods.append((min(addrs), max(addrs), name, len(addrs)))
    mods.sort()

    print(f"\n{len(mods)} source modules with reference sites, by address:\n")
    prev_end = prev_name = None
    overlaps = 0
    for lo, hi, name, n in mods:
        flag = ""
        if prev_end is not None and lo <= prev_end:
            flag = f"   <-- OVERLAPS {prev_name}"
            overlaps += 1
        print(f"  {lo:#08x}..{hi:#08x}  {hi - lo:6} B  {n:4} refs  {name}{flag}")
        prev_end, prev_name = hi, name
    print(f"\noverlapping module spans: {overlaps}")

    if "--lines" in sys.argv:
        raw = af.data[af.dpo:]                      # obj1 image starts at dpo
        anchors = line_anchors(sites, names, raw)
        print("\n(file, line) anchors -- address order vs line order:\n")
        tot = inv_tot = pair_tot = 0
        for name in sorted(anchors, key=lambda n: -len(anchors[n])):
            v = sorted(anchors[name])
            lines = [l for _a, l in v]
            inv = sum(1 for i in range(len(lines))
                      for j in range(i + 1, len(lines)) if lines[i] > lines[j])
            pairs = len(lines) * (len(lines) - 1) // 2
            tot += len(v); inv_tot += inv; pair_tot += pairs
            if len(v) >= 10:
                print(f"  {name:<12} {len(v):4} anchors  lines {min(lines):5}..{max(lines):<5}"
                      f"  {100 * inv / pairs if pairs else 0:5.1f}% out of order")
        print(f"\ntotal anchors: {tot}   overall out-of-order pairs: "
              f"{inv_tot}/{pair_tot} = {100 * inv_tot / pair_tot:.1f}%")

    if "--names" in sys.argv:
        out_path = sys.argv[sys.argv.index("--names") + 1]
        fn_path = sys.argv[sys.argv.index("--functions") + 1]
        raw = af.data[af.dpo:]
        anchors = line_anchors(sites, names, raw)
        line_at = {}
        for m, v in anchors.items():
            for a, l in v:
                line_at[a] = l
        fns = []
        for line in open(fn_path):
            q = line.split()
            if len(q) >= 4 and len(q[0]) == 8:
                try:
                    fns.append((int(q[0], 16), int(q[1]), q[3]))
                except ValueError:
                    pass
        used, rows = set(), []
        for addr, size, cur in sorted(fns):
            mod = next((m for m in mods if m[0] <= addr <= m[1]), None)
            if mod is None or not cur.startswith("FUN_"):
                continue
            stem = mod[2].rsplit(".", 1)[0]
            inside = [l for a, l in line_at.items() if addr <= a < addr + max(size, 1)]
            base = f"{stem}_L{min(inside):04d}" if inside else f"{stem}_{addr:06x}"
            name = base
            n = 2
            while name in used:
                name = f"{base}_{n}"; n += 1
            used.add(name)
            rows.append((addr, name))
        with open(out_path, "w") as fh:
            for addr, name in rows:
                fh.write(f"0x{addr:08x}\t{name}\n")
        withline = sum(1 for _a, n in rows if "_L" in n)
        print(f"\nnames written: {len(rows)} -> {out_path} "
              f"({withline} carry a source line, {len(rows) - withline} address-only)")

    if "--functions" in sys.argv:
        path = sys.argv[sys.argv.index("--functions") + 1]
        fns = []
        for line in open(path):
            q = line.split()
            if len(q) >= 4 and len(q[0]) == 8:
                try:
                    fns.append((int(q[0], 16), int(q[1]), q[3]))
                except ValueError:
                    pass
        counts = {}
        for a, _s, _n in fns:
            hit = next((m[2] for m in mods if m[0] <= a <= m[1]), None)
            counts[hit] = counts.get(hit, 0) + 1
        inside = sum(v for k, v in counts.items() if k)
        print(f"\nfunctions inside a module span: {inside} of {len(fns)}")
        for name, c in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"   {c:5}  {name or '(outside every span)'}")


if __name__ == "__main__":
    main()
