#!/usr/bin/env python3
"""Seeded recursive-descent over PANZER.EXE's code object (LE object 1).

Addresses are LE linear addresses ("vaddr", object 1 base 0x10000); the load
placement the DOS oracle measured is vaddr + 0x16D000 (RAM 0x17D000 for page 1,
see analysis/executable.md).  Function symbols are `sub_<vaddr>`, tied to the
SHA-256 recorded in analysis/executable.md.

    python3 tools/re/disasm_le.py                # validate seeds, descend, report
    python3 tools/re/disasm_le.py --functions work/re/functions.txt

Rules (METHOD.md §2.3): seeds come only from re/seeds.txt; a seed that lands
outside object 1, inside a known-data region, or mid-instruction is an error.
Indirect jumps resolve only through a jump table whose extent a preceding
`cmp reg,N` / `ja` proves and whose entries are all fixups into object 1;
everything else is listed as unresolved, not guessed.  Known data (pointer-table
fixup runs, the Watcom banner) is asserted never to be decoded.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

import capstone
from capstone import x86

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "work"))
import le_map as L  # noqa: E402

OBJ1_BASE, OBJ2_BASE = 0x10000, 0x80000
OBJ1_FILE = L.page_off(1)
OBJ1_SIZE = L.objs[0][0]
d = L.d
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.detail = True


def v2f(v: int) -> int:
    return OBJ1_FILE + v - OBJ1_BASE


def f2v(f: int) -> int:
    return f - OBJ1_FILE + OBJ1_BASE


def in_obj1(v: int) -> bool:
    return OBJ1_BASE <= v < OBJ1_BASE + OBJ1_SIZE


def load_fixups() -> dict[int, tuple[int, int]]:
    """vaddr of each 32-bit fixup site in object 1 -> (target object, offset)."""
    out = {}
    for n in range(1, L.objs[0][4] + 1):
        for soff, kind, obj, toff in L.fixups(n):
            if kind == 7:
                out[OBJ1_BASE + (n - 1) * L.page_size + soff] = (obj, toff)
    return out


FIX = load_fixups()


def load_data_fixups() -> dict[int, tuple[int, int]]:
    """vaddr of each 32-bit fixup site in object 2 (initialised data) -> target."""
    out = {}
    first, count = L.objs[1][3], L.objs[1][4]
    for n in range(first, first + count):
        for soff, kind, obj, toff in L.fixups(n):
            if kind == 7:
                out[OBJ2_BASE + (n - first) * L.page_size + soff] = (obj, toff)
    return out


DFIX = load_data_fixups()


def resolve_pointers(unresolved, insns):
    """Resolve `call dword ptr [abs]` through statically visible values.

    A pointer location may be initialised by a fixup in object 2 and/or written
    by `mov [loc], imm32-with-fixup`.  A location with any other write (a
    register store, `xchg`, `lea`) is reported as having an unknown writer and
    contributes only the targets seen; sites with unknown writers are partial.
    Returns {call vaddr: (location, targets, unknown_writers)}.
    """
    writes: dict[tuple[int, int], list] = {}
    for v in sorted(insns):
        ins = next(md.disasm(d[v2f(v):v2f(v) + 15], v, 1))
        for i, o in enumerate(ins.operands):
            if o.type == x86.X86_OP_MEM and not o.mem.base and not o.mem.index \
                    and ins.disp_size == 4 and (v + ins.disp_offset) in FIX:
                loc = FIX[v + ins.disp_offset]
                dest = i == 0 and ins.mnemonic in ("mov", "xchg", "add", "sub", "inc",
                                                   "dec", "and", "or", "xor", "adc", "sbb")
                if not dest:
                    continue
                tgt = None
                if ins.mnemonic == "mov" and len(ins.operands) == 2 \
                        and ins.operands[1].type == x86.X86_OP_IMM and ins.imm_size == 4:
                    f = v + ins.imm_offset
                    if f in FIX and FIX[f][0] == 1:
                        tgt = OBJ1_BASE + FIX[f][1]
                    elif ins.operands[1].imm == 0:
                        continue                      # null-initialisation
                writes.setdefault(loc, []).append((v, tgt))
    out = {}
    for v, why in unresolved:
        if not why.startswith("call dword ptr [0x"):
            continue
        ins = next(md.disasm(d[v2f(v):v2f(v) + 15], v, 1))
        if ins.disp_size != 4 or (v + ins.disp_offset) not in FIX:
            continue
        loc = FIX[v + ins.disp_offset]
        targets, unknown = set(), 0
        if loc[0] == 2:
            site = OBJ2_BASE + loc[1]
            if site in DFIX and DFIX[site][0] == 1:
                targets.add(OBJ1_BASE + DFIX[site][1])
        for _, t in writes.get(loc, []):
            if t is None:
                unknown += 1
            else:
                targets.add(t)
        out[v] = (loc, targets, unknown)
    return out


def parse_seeds(path: Path):
    seeds, anti = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        kind, *rest = line.split()
        kv = dict(r.split("=", 1) for r in rest if "=" in r)
        if kind in ("ENTRY", "FUNC", "CODE"):
            seeds.append((kind, int(kv["vaddr"], 0), kv))
        elif kind == "ANTISEED":
            anti.append((int(kv["vaddr"], 0), kv))
    return seeds, anti


def known_data() -> list[tuple[int, int, str]]:
    """Regions inside object 1 that must never be decoded."""
    regions = []
    # Watcom start stub banner: EB xx then text.
    for m in re.finditer(rb"WATCOM C/C\+\+32 Run-Time system[^\x00]*\x00?", d):
        regions.append((f2v(m.start()), f2v(m.end()), "watcom banner"))
    # Runs of >= 4 consecutive 32-bit fixups into object 1 are pointer tables.
    sites = sorted(FIX)
    run = [sites[0]]
    for s in sites[1:] + [None]:
        if s is not None and s == run[-1] + 4 and FIX[s][0] == 1:
            run.append(s)
            continue
        if len(run) >= 4 and all(FIX[x][0] == 1 for x in run):
            regions.append((run[0], run[-1] + 4, f"pointer table x{len(run)}"))
        run = [s] if s is not None else []
    # NUL-terminated printable text of >= 10 characters.  Searched in the whole
    # object, so a decoded instruction that overlaps one is flagged.
    obj = d[OBJ1_FILE:OBJ1_FILE + OBJ1_SIZE]
    for m in re.finditer(rb"[ -~]{10,}\x00", obj):
        regions.append((OBJ1_BASE + m.start(), OBJ1_BASE + m.end(), "text"))
    return regions


def table_extent(block: list, mem_disp_vaddr: int, fix_site: int):
    """Entries of a switch table, or None if not proven.

    block is the preceding decoded instructions of the same linear run; the
    bound must be a `cmp reg, imm` followed by ja/jae/jb/jbe within it.
    """
    for i in range(len(block) - 1, 0, -1):
        ins = block[i]
        if ins.mnemonic in ("ja", "jae", "jg", "jge") and i > 0:
            prev = block[i - 1]
            if prev.mnemonic == "cmp" and prev.operands[1].type == x86.X86_OP_IMM:
                n = prev.operands[1].imm + 1
                if ins.mnemonic in ("jae", "jge"):
                    n = prev.operands[1].imm
                return n
            return None
    return None


def descend(entries, dead: set[int]):
    insns: dict[int, int] = {}           # vaddr -> length, decoded instructions
    covered: dict[int, int] = {}         # byte vaddr -> owning insn vaddr
    funcs: dict[int, str] = {}
    unresolved: list[tuple[int, str]] = []
    resolved_tables: list[tuple[int, int, int]] = []
    conflicts: list[tuple[int, int]] = []
    work = list(entries)
    seen = set()
    while work:
        start, role = work.pop()
        if start in seen or not in_obj1(start):
            continue
        seen.add(start)
        if role == "func":
            funcs.setdefault(start, "call")
        v = start
        block = []
        while in_obj1(v):
            if v in insns:
                break
            f = v2f(v)
            ins = next(md.disasm(d[f:f + 15], v, 1), None)
            if ins is None:
                conflicts.append((v, -1))
                break
            if any(b in covered for b in range(v + 1, v + ins.size)) or v in covered:
                conflicts.append((v, covered.get(v, v)))
                break
            insns[v] = ins.size
            for b in range(v, v + ins.size):
                covered[b] = v
            block.append(ins)
            g = ins.group
            nxt = v + ins.size
            is_jmp = ins.mnemonic == "jmp"
            is_jcc = ins.group(capstone.CS_GRP_JUMP) and not is_jmp
            if ins.mnemonic == "call" or is_jmp or is_jcc:
                op = ins.operands[0]
                if op.type == x86.X86_OP_IMM:
                    tgt = op.imm & 0xFFFFFFFF
                    work.append((tgt, "func" if ins.mnemonic == "call" else "code"))
                elif op.type == x86.X86_OP_MEM and is_jmp and (op.mem.index or op.mem.base):
                    site = v + ins.disp_offset
                    n = table_extent(block[:-1], op.mem.disp, site)
                    ok = False
                    if n and site in FIX and FIX[site][0] == 1:
                        base = OBJ1_BASE + FIX[site][1]
                        ents = [base + 4 * k for k in range(n)]
                        if all(e in FIX and FIX[e][0] == 1 for e in ents):
                            ok = True
                            resolved_tables.append((v, base, n))
                            for e in ents:
                                work.append((OBJ1_BASE + FIX[e][1], "code"))
                    if not ok:
                        unresolved.append((v, "jmp table (extent not proven)"))
                else:
                    unresolved.append((v, f"{ins.mnemonic} {ins.op_str}"))
            if is_jmp or ins.mnemonic in ("ret", "retf", "iretd", "ud2", "hlt"):
                break
            v = nxt
    return insns, funcs, unresolved, resolved_tables, conflicts


PROLOGUES = (re.compile(b"(?:[" + re.escape(bytes([0x53, 0x51, 0x52, 0x56, 0x57])) + b"])*"
                        + re.escape(bytes([0x55, 0x89, 0xE5]))),
             re.compile(re.escape(bytes([0x55, 0x8B, 0xEC]))))


def gap_candidates(insns, cov, data):
    """Uncovered, prologue-shaped, cleanly decoding routines.  Evidence grade:
    shape only -- they are reported, never promoted to seeds automatically."""
    out = []
    taken = set(cov)
    v = OBJ1_BASE
    end = OBJ1_BASE + OBJ1_SIZE
    while v < end:
        if v in taken or not any(p.match(d[v2f(v):v2f(v) + 12]) for p in PROLOGUES):
            v += 1
            continue
        a, ok, n_ins = v, False, 0
        seen = []
        while a < end and a not in taken and not any(lo <= a < hi for lo, hi, _ in data):
            ins = next(md.disasm(d[v2f(a):v2f(a) + 15], a, 1), None)
            if ins is None:
                break
            seen.append((a, ins.size))
            n_ins += 1
            a += ins.size
            if ins.mnemonic in ("ret", "retf", "iretd"):
                ok = True
                break
            if ins.mnemonic == "jmp" and ins.operands[0].type != x86.X86_OP_IMM:
                break
            if n_ins > 4000:
                break
        if ok and n_ins >= 6:
            out.append((v, a - v))
            for x, sz in seen:
                taken.update(range(x, x + sz))
            v = a
        else:
            v += 1
    return out


def build(entries, dead, resolve_ptrs=True):
    """descend(), then feed statically resolved data-pointer calls back in.

    Targets come from object-2 fixups (initialised pointer tables) and
    `mov [loc], imm32-with-fixup`; each is a function entry with relocation-aware
    evidence.  Iterated to a fixed point.  Returns descend()'s tuple plus
    {call vaddr: (location, targets, unknown_writers)}.
    """
    extra: list[tuple[int, str]] = []
    ptrs: dict = {}
    while True:
        insns, funcs, unresolved, tables, conflicts = descend(entries + extra, dead)
        if not resolve_ptrs:
            return insns, funcs, unresolved, tables, conflicts, ptrs
        ptrs = resolve_pointers(unresolved, insns)
        new = [(t, "func") for _, tg, _ in ptrs.values() for t in tg
               if t not in insns and (t, "func") not in extra]
        if not new:
            return insns, funcs, unresolved, tables, conflicts, ptrs
        extra += new


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pointers", action="store_true",
                    help="do not follow statically resolved data-pointer calls")
    ap.add_argument("--seeds", type=Path, default=ROOT / "re" / "seeds.txt")
    ap.add_argument("--functions", type=Path)
    ap.add_argument("--gaps", type=Path,
                    help="write unreferenced prologue-shaped candidates (NOT seeds)")
    args = ap.parse_args()

    seeds, anti = parse_seeds(args.seeds)
    data = known_data()
    errors = []
    entries = []
    for kind, v, kv in seeds:
        if not in_obj1(v):
            errors.append(f"seed 0x{v:X} outside object 1")
            continue
        for lo, hi, why in data:
            if lo <= v < hi:
                errors.append(f"seed 0x{v:X} inside known data ({why})")
        entries.append((v, "func" if kind in ("ENTRY", "FUNC") else "code"))
    insns, funcs, unresolved, tables, conflicts, ptrs = build(
        entries, {a for a, _ in anti}, not args.no_pointers)
    dyn = {int(m.group(1), 16) for m in re.finditer(
        r"^DYNPTR loc=(0x[0-9A-Fa-f]+)", args.seeds.read_text(encoding="utf-8"), re.M)}
    external = sum(1 for loc, _t, _u in ptrs.values() if loc[0] == 2 and loc[1] in dyn)
    complete = sum(1 for _, t, u in ptrs.values() if t and not u)
    partial = sum(1 for _, t, u in ptrs.values() if t and u)
    unknown = sum(1 for _, t, u in ptrs.values() if not t)

    decoded = sum(insns.values())
    cov = set()
    for a_, n_ in insns.items():
        cov.update(range(a_, a_ + n_))
    bad = []
    for lo, hi, why in data:
        hit = sum(1 for b in range(lo, hi) if b in cov)
        if hit:
            bad.append((lo, hi, why, hit))
    print(f"seeds: {len(seeds)} (anti-seeds {len(anti)}); known-data regions: {len(data)}")
    print(f"object 1: 0x{OBJ1_SIZE:X} bytes; decoded {decoded} bytes in {len(insns)} "
          f"instructions = {100 * decoded / OBJ1_SIZE:.1f}%")
    print(f"functions (call targets + func seeds): {len(funcs)}")
    print(f"jump tables resolved: {len(tables)}; unresolved indirect sites: {len(unresolved)}")
    print(f"data-pointer call sites: {len(ptrs)} (all targets known {complete}; "
          f"partial, unknown writers {partial}; none known {unknown}); "
          f"of those, into a runtime-loaded module (DYNPTR): {external}")
    print(f"decode conflicts (mid-instruction or invalid): {len(conflicts)}")
    for a, b in conflicts:
        print(f"  0x{a:X} lands inside the instruction at 0x{b:X}")
    print(f"known-data regions wrongly decoded: {len(bad)}")
    for e in errors:
        print("ERROR", e)
    for lo, hi, why, hit in bad[:20]:
        print(f"ERROR decoded {hit} bytes of {why} at 0x{lo:X}")
    for v, why in unresolved[:10]:
        print(f"  unresolved 0x{v:X}: {why}")
    if args.gaps:
        cands = gap_candidates(insns, cov, data)
        args.gaps.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"cand_{v:08X} vaddr=0x{v:X} bytes={n}" for v, n in cands]
        args.gaps.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
        print(f"gap candidates (unreferenced, prologue-shaped, decode to ret): "
              f"{len(cands)} covering {sum(n for _, n in cands)} bytes -> {args.gaps}")
    if args.functions:
        args.functions.parent.mkdir(parents=True, exist_ok=True)
        with args.functions.open("w", encoding="utf-8") as fh:
            for v in sorted(funcs):
                fh.write(f"sub_{v:08X} vaddr=0x{v:X} file=0x{v2f(v):X} "
                         f"runtime=0x{v + 0x16D000:X}\n")
        print("wrote", args.functions)
    return 1 if errors or bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
