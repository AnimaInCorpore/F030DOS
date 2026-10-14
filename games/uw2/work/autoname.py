#!/usr/bin/env python3
"""Bulk candidate names for UW2.EXE functions, from cited idioms.

Everything the hand loop did -- disassemble a function, recognise an idiom
(`mov dx,0x1b / imul`, `INT 67h AH=44h`, `shr 6 / and 0x3ff`, a known global),
name it -- is mechanical. This applies the same rules to all 2,239 functions
at once.

**These are CANDIDATES, tier 3.** Every one carries the instruction that
triggered it, so a human can confirm or reject in seconds. They are emitted
separately from tier 1 (read and verified) and tier 2 (string references, which
are facts but not names) and must not be merged without checking:
a rule fires on a *pattern*, and a pattern can lie.

Rules are deliberately narrow. A DOS/EMS/mouse interrupt with a literal
function number is near-certain; "touches the object array" is a hint about
subject matter, not a claim about what the function does with it.
"""
import argparse
import bisect
import re
import struct
from collections import Counter
from pathlib import Path

import capstone

import callgraph as CG                                        # noqa: E402

EXE = Path("work/extracted/D3/UW2.EXE")
FUNCS = Path("work/ghidra_export/functions.txt")
OUT = Path("work/ghidra_export/candidates.txt")
SKEW = 0xD200

DOS = {0x3D: "dos_open", 0x3E: "dos_close", 0x3F: "dos_read", 0x40: "dos_write",
       0x42: "dos_lseek", 0x41: "dos_unlink", 0x39: "dos_mkdir", 0x3B: "dos_chdir",
       0x4E: "dos_findfirst", 0x4F: "dos_findnext", 0x48: "dos_alloc",
       0x49: "dos_free", 0x25: "dos_set_vector", 0x35: "dos_get_vector",
       0x2C: "dos_get_time", 0x2A: "dos_get_date", 0x30: "dos_version",
       0x44: "dos_ioctl", 0x4C: "dos_exit", 0x47: "dos_getcwd"}
EMS = {0x40: "ems_status", 0x41: "ems_page_frame", 0x42: "ems_free_pages",
       0x43: "ems_alloc", 0x44: "ems_map_page", 0x45: "ems_free",
       0x46: "ems_version", 0x47: "ems_save_map", 0x48: "ems_restore_map",
       0x4B: "ems_handle_count", 0x4C: "ems_handle_pages"}
MOUSE = {0x00: "mouse_reset", 0x01: "mouse_show", 0x02: "mouse_hide",
         0x03: "mouse_get_state", 0x04: "mouse_set_pos", 0x0B: "mouse_get_motion"}
# globals whose meaning is established in the analysis docs
GLOBALS = {0x188C: ("level_grid", "level tile grid base"),
           0x2578: ("obj27", "the 256 x 27-byte object array"),
           0x25A6: ("obj8", "the 768 x 8-byte object array"),
           0x4704: ("conv_mem", "conversation VM memory array"),
           0x46FC: ("conv_stack", "conversation VM stack"),
           0x470E: ("conv_fnptr", "conversation VM function-pointer array"),
           0x471E: ("conv_code", "conversation VM code array"),
           0x471A: ("conv_ip", "conversation VM instruction pointer"),
           0x46FA: ("conv_sp", "conversation VM stack index"),
           0x0114: ("ovl_pool_base", "overlay pool file offset")}


# File spans measured elsewhere in the analysis docs. Membership is a fact
# about location, so the tag says "in the span of", not what the function does.
REGIONS = [
    (0x0999D, 0x114D5, "threaded_engine", "ghidra.md 10b: the 101 NEXT handlers"),
    (0x38DF0, 0x39C00, "overlay_mgr",     "ghidra.md 15: INT 3Fh manager code segment"),
    (0x74E15, 0x76800, "conv_vm",         "data-formats.md: loader/parser/VM/registrar"),
    (0x7C38C, 0x7C600, "conv_init",       "the 51 builtin registration sites"),
    (0x8B435, 0x8BD00, "gr_loader",       "gfx_init / gr_archive_load / gr_record_read"),
    (0x927C0, 0x92A00, "level_buf",       "level_buf_alloc and friends"),
]


def region_of(off):
    for lo, hi, tag, why in REGIONS:
        if lo <= off < hi:
            return tag, why
    return None


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


def _length(d, md, start, end):
    """Instruction count to the function's first ret, bounded."""
    n = 0
    for i in md.disasm(d[start:min(end, start + 0x300)], start):
        n += 1
        if i.mnemonic in ("ret", "retf"):
            break
    return n


def analyse(d, md, start, end):
    """Walk a function and return (candidate_name, evidence) or None."""
    total = _length(d, md, start, end)
    ah = al = ax = None
    calls = 0
    ins_n = 0
    hits = []
    for i in md.disasm(d[start:min(end, start + 0x300)], start):
        ins_n += 1
        m = i.mnemonic
        o = i.op_str
        if m == "mov":
            mm = re.match(r"(ah|al|ax|dx|bx),\s*(0x[0-9a-f]+|\d+)$", o)
            if mm:
                v = int(mm.group(2), 16) if mm.group(2).startswith("0x") else int(mm.group(2))
                if mm.group(1) == "ah":
                    ah = v
                elif mm.group(1) == "al":
                    al = v
                elif mm.group(1) == "ax":
                    ax = v
                if mm.group(1) == "dx" and v == 0x1B:
                    hits.append(("obj27_index", f"mov dx,0x1b at {i.address:#x}"))
        if m == "int":
            n = int(o, 16)
            fn = ah if ah is not None else (ax >> 8 if ax is not None else None)
            # Only *name* a function after an interrupt when the function is
            # thin enough to be a wrapper for it. c0_startup does INT 21h
            # AH=30h early and is emphatically not "dos_version" -- naming a
            # large routine after an incidental call is how a pattern lies.
            thin = total <= 12          # the WHOLE function, not the prefix
            hit = None
            if n == 0x21 and fn in DOS:
                hit = (DOS[fn], f"int 0x21 AH={fn:#04x} at {i.address:#x}")
            elif n == 0x67 and fn in EMS:
                hit = (EMS[fn], f"int 0x67 AH={fn:#04x} at {i.address:#x}")
            elif n == 0x33:
                fn2 = ax if ax is not None else al
                if fn2 in MOUSE:
                    hit = (MOUSE[fn2], f"int 0x33 AX={fn2:#06x} at {i.address:#x}")
            elif n == 0x10:
                hit = ("bios_video", f"int 0x10 at {i.address:#x}")
            if hit:
                return hit if thin else (f"does_{hit[0]}",
                                         hit[1] + f" (function is {total} instructions,"
                                                  " so this is a hint, not a name)")
        if m == "call" or m == "lcall":
            calls += 1
        mg = re.search(r"\[(0x[0-9a-f]{3,4})\]", o)
        if mg:
            g = int(mg.group(1), 16)
            if g in GLOBALS:
                hits.append((GLOBALS[g][0], f"{GLOBALS[g][1]} [{g:#06x}] at {i.address:#x}"))
        if m in ("ret", "retf"):
            break
    if ins_n <= 2:
        return "stub", f"{ins_n} instruction(s)"
    if ins_n <= 8 and calls == 1:
        return "thin_wrapper", f"{ins_n} instructions, exactly 1 call"
    if hits:
        tag = Counter(h[0] for h in hits).most_common(1)[0][0]
        return f"touches_{tag}", hits[0][1]
    r = region_of(start)
    if r:
        return f"in_{r[0]}", r[1]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--no-propagate", action="store_true",
                    help="skip the call-graph propagation pass")
    ap.add_argument("--validate", action="store_true",
                    help="run the rules against symbols.py's hand-verified tier 1")
    a = ap.parse_args()
    d = EXE.read_bytes()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    fns = functions()
    starts = [f[0] for f in fns]

    if a.validate:
        import symbols
        ok = bad = silent = 0
        for off, nm, kind, _why in sorted(symbols.TIER1):
            if kind != "code":
                continue
            k = bisect.bisect_right(starts, off) - 1
            end = starts[k + 1] if k + 1 < len(starts) else off + 0x200
            r = analyse(d, md, off, end)
            if r is None:
                silent += 1
                continue
            got = r[0]
            good = (got in nm or nm.split("_")[0] in got
                    or got.startswith(("in_", "touches_", "does_"))
                    or got in ("thin_wrapper", "stub"))
            ok += good
            bad += not good
            if not good:
                print(f"   MISLEADING: {nm} ({off:#08x}) -> {got}")
        print(f"against {ok+bad+silent} hand-verified names: "
              f"consistent {ok}, misleading {bad}, silent {silent}")
        return
    rows = []
    for k, (off, name, inref) in enumerate(fns):
        end = starts[k + 1] if k + 1 < len(starts) else off + 0x200
        r = analyse(d, md, off, end)
        if r:
            rows.append((off, name, inref, r[0], r[1]))
    # ---- pass 2: propagate a subsystem tag along the call graph -----------
    # A function that calls into a subsystem is very likely part of it. This is
    # weaker than an idiom match -- it says "related to", not "is" -- so the
    # tag is prefixed `calls_` and the specific callee is quoted.
    if not a.no_propagate:
        import symbols
        # Generic utilities are called from everywhere, so propagating from
        # them tags half the binary with something that says nothing: a
        # function is not a "rand routine" because it calls rand.
        GENERIC = {"rand", "heap", "dos", "stub"}
        seed = {}
        for off, nm, kind, _ in symbols.TIER1:
            if kind == "code" and nm.split("_")[0] not in GENERIC:
                seed[off] = nm.split("_")[0]
        for off, _n, _i, cand, _w in rows:
            if cand.startswith("in_"):
                seed.setdefault(off, cand[3:].split("_")[0])
        callers, callees, _, _ = CG.build(d, fns)
        have = {r[0] for r in rows}
        by_off = {f[0]: f for f in fns}
        for _round in range(2):
            new = []
            for off, name, inref in fns:
                if off in have or off in seed:
                    continue
                tags = [(seed[c], c) for c in callees.get(off, ()) if c in seed]
                if not tags:
                    continue
                tag, who = Counter(t for t, _ in tags).most_common(1)[0][0], tags[0][1]
                nm = by_off.get(who, (0, "?", 0))[1]
                new.append((off, name, inref, f"calls_{tag}",
                            f"calls {who:#08x} ({nm}), a {tag} routine"))
            for r in new:
                rows.append(r)
                have.add(r[0])
                seed[r[0]] = r[3][6:]
        rows.sort()

    kinds = Counter(r[3] for r in rows)
    print(f"{len(fns)} functions, {len(rows)} candidates ({100*len(rows)//len(fns)}%)")
    for k, v in kinds.most_common(14):
        print(f"   {k:24s} {v:5d}")
    if a.emit:
        with OUT.open("w") as fh:
            fh.write("# TIER 3 -- machine-generated CANDIDATES with the idiom that\n"
                     "# triggered each. NOT verified. Confirm before promoting to\n"
                     "# tier 1 in symbols.py. A rule fires on a pattern, and a\n"
                     "# pattern can lie.\n\n")
            for off, name, inref, cand, why in rows:
                fh.write(f"{off:06X}  {cand:22s} inrefs={inref:<4d} {name:30s} # {why}\n")
        print(f"   wrote {OUT}")


if __name__ == "__main__":
    main()
