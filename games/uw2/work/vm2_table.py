#!/usr/bin/env python3
"""Enumerate the threaded-code VM's dispatch table (the *second* VM).

analysis/ghidra.md sections 8-10 found this engine live, on the oracle, and
left the table "fitted, not measured". This locates it in the file and
enumerates it exactly.

The inner interpreter is the classic threaded-code NEXT:

    AD              lodsw                  ; ax = [ds:si], si += 2   (fetch token)
    93              xchg bx, ax
    FF A7 F4 24     jmp word ptr [bx+0x24f4]

Every one of the 101 `jmp [bx+0x24f4]` sites in UW2.EXE is a complete NEXT,
so tokens are *byte* offsets into the table (bx is not scaled) -- the script
stream stores opcode*2.

The table is at 0x4FCE:0x24F4 and the handlers at 0x065C:0000, in the file's
own (pre-relocation) segment numbering, so both are pure file arithmetic:

    file = 0x2E00 + (segment << 4) + offset          (0x2E00 = e_cparhdr*16)

    handlers  0x065C:0000  -> 0x93C0
    table     0x4FCE:24F4  -> 0x54FD4

section 10 got the same table by adding a live DS reading to a boot delta;
that route still cross-checks (see --verify) but is not needed.

This is NOT the conversation VM (ghidra.md section 11, 42 opcodes, its own
table at 0x75E1B). UW2 runs two bytecode engines.
"""
import argparse
import functools
import re
import struct
from collections import Counter
from pathlib import Path

import capstone

EXE = Path("work/extracted/D3/UW2.EXE")
NEXT = b"\xad\x93\xff\xa7\xf4\x24"
TABLE = 0x54FD4      # derived above
CODE_BASE = 0x93C0   # file offset of the handlers' segment:0000
SLOTS = 111
DELTA = 0x2F50       # the boot that section 10 measured DS on


def load():
    d = EXE.read_bytes()
    sites = [m.start() for m in re.finditer(re.escape(NEXT), d)]
    return d, sites


def table(d):
    return list(struct.unpack_from(f"<{SLOTS}H", d, TABLE))


COND = {"je", "jne", "jz", "jnz", "jb", "jbe", "ja", "jae", "jl", "jle", "jg",
        "jge", "js", "jns", "jo", "jno", "jc", "jnc", "jp", "jnp", "jcxz",
        "loop", "loope", "loopne"}


@functools.lru_cache(maxsize=None)
def operand_counts(entry, stop_at_next=True, depth=0):
    """Inline-operand width of one handler, **in bytes**.

    Walks every path from the handler's entry to its terminating NEXT and adds
    up what each path takes from SI.  Three things this has to get right, each
    of which was wrong in an earlier version and made the stream undecodable:

      * the stream is **byte-granular** -- handlers use `lodsb` as well as
        `lodsw`, so counting `lodsw`s and multiplying by two is meaningless;
      * `movsb`/`movsw` also consume from SI;
      * a handler may consume through a **subroutine** it calls, so `call` is
        followed and the callee's own consumption (paths to `ret`) added.

    Returns the set of widths: one element = fixed width, several = the
    handler takes a runtime-determined amount (a loop), None present = a path
    leaves the VM instead of reaching a NEXT.
    """
    out, seen, stack = set(), set(), [(entry, 0)]
    while stack:
        a, n = stack.pop()
        if (a, n) in seen or len(seen) > 4000:
            continue
        seen.add((a, n))
        ins = list(_MD.disasm(_EXE[a:a + 16], a))
        if not ins:
            out.add(None)
            continue
        i = ins[0]
        m = i.mnemonic
        if m == 'lodsw':
            if stop_at_next and _EXE[a + 1:a + 6] == NEXT[1:]:
                out.add(n)
            else:
                stack.append((a + i.size, n + 2))
            continue
        if m in ('lodsb', 'movsb'):
            stack.append((a + i.size, n + 1))
            continue
        if m == 'movsw':
            stack.append((a + i.size, n + 2))
            continue
        if m == 'call':
            try:
                t = int(i.op_str, 16)
            except ValueError:
                out.add(None)
                continue
            sub = operand_counts(t, False, depth + 1) if depth < 3 else frozenset({None})
            if len(sub) != 1 or None in sub:
                out.add(None)
                continue
            stack.append((a + i.size, n + next(iter(sub))))
            continue
        if m in COND or m == 'jmp':
            try:
                t = int(i.op_str, 16)
            except ValueError:
                out.add(None)
                continue
            stack.append((t, n))
            if m != 'jmp':
                stack.append((a + i.size, n))
            continue
        if m in ('ret', 'retf', 'iret'):
            out.add(None if stop_at_next else n)
            continue
        stack.append((a + i.size, n))
    return frozenset(out)


_EXE = EXE.read_bytes()
_MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--operands", action="store_true",
                    help="derive each handler's inline-operand count by CFG walk")
    a = ap.parse_args()
    d, sites = load()
    entries = set(s + 6 for s in sites)
    lo, hi = min(sites), max(sites) + 6
    T = table(d)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)

    if a.operands:
        fixed, variable, undet = {}, {}, []
        for i, v in enumerate(T):
            s = operand_counts(CODE_BASE + v)
            if None in s:
                undet.append(i)
            elif len(s) == 1:
                fixed[i] = next(iter(s))
            else:
                variable[i] = (min(s), max(s))
        print(f"fixed-width handlers      : {len(fixed)}/{SLOTS}")
        print(f"  operand widths, in BYTES: "
              f"{sorted(Counter(fixed.values()).items())}")
        print(f"variable-width (loops)    : {len(variable)}  {sorted(variable)[:8]}")
        print(f"reaches ret (terminators) : {undet}")
        return

    if a.list:
        print(f"{'tok':>5} {'slot':>4} {'off':>7} {'file':>8}  disassembly")
        for i, v in enumerate(T):
            addr = CODE_BASE + v
            ins = list(md.disasm(d[addr:addr + 12], addr))
            txt = " ; ".join(f"{x.mnemonic} {x.op_str}" for x in ins[:2])
            mark = "*" if addr in entries else " "
            print(f"0x{2*i:03x} {i:4d} 0x{v:05x} 0x{addr:06X}{mark} {txt}")
        print("\n* = lands exactly on a handler entry (the byte after a NEXT)")
        return

    print(f"{EXE}: threaded-code VM")
    print(f"  NEXT sequences (lodsw/xchg bx,ax/jmp [bx+0x24f4]) : {len(sites)}")
    bare = len(re.findall(re.escape(b"\xff\xa7\xf4\x24"), d))
    print(f"  bare `jmp [bx+0x24f4]` sites                      : {bare} "
          f"({'all are complete NEXTs' if bare == len(sites) else 'MISMATCH'})")
    print(f"  handler region  file 0x{lo:X}..0x{hi:X}  "
          f"= segment offsets 0x{lo-CODE_BASE:X}..0x{hi-CODE_BASE:X}")
    print(f"  table @file 0x{TABLE:X}, {SLOTS} slots, "
          f"values {min(T)}..{max(T)}, {len(set(T))} distinct targets")

    if a.verify:
        print("\n  invariants:")
        nxt = struct.unpack_from("<H", d, TABLE + 2 * SLOTS)[0]
        print(f"   slot {SLOTS} (one past the end) = {nxt} -> out of range, "
              f"so the table is exactly {SLOTS} slots")
        print(f"   max entry + code base == region end          : "
              f"0x{CODE_BASE + max(T):X} == 0x{hi:X}  {CODE_BASE + max(T) == hi}")
        hits = sum(1 for v in T if CODE_BASE + v in entries)
        sc = [(sum(1 for v in T if cb + v in entries), cb)
              for cb in range(0x2E00, 0x12000)]
        best = max(sc)
        uniq = sum(1 for s, _ in sc if s == best[0]) == 1
        print(f"   entries landing on a handler entry           : {hits}/{SLOTS}")
        print(f"   best code base over 0x2E00..0x12000          : 0x{best[1]:X} "
              f"({best[0]}/{SLOTS}), unique maximum: {uniq}, "
              f"runner-up {sorted(sc, reverse=True)[1][0]}")
        seg = (CODE_BASE + DELTA) >> 4
        print(f"   implied runtime segment ((base+delta)>>4)     : 0x{seg:04X} "
              f"-- ghidra.md section 9 recorded segment 0C31 from a live trace")
        ok = sum(1 for v in set(T)
                 if list(md.disasm(d[CODE_BASE + v:CODE_BASE + v + 8], CODE_BASE + v)))
        print(f"   distinct targets that disassemble             : {ok}/{len(set(T))}")
        c = Counter(T)
        v, n = c.most_common(1)[0]
        print(f"   most-shared target 0x{CODE_BASE+v:X} used by {n} slots "
              f"-- section 10 measured 13 slots sharing FUN_1724_03ec+0x24")


if __name__ == "__main__":
    main()
