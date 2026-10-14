#!/usr/bin/env python3
"""Disassemble UW2 conversation bytecode (the CNV.ARK code section).

The VM was read out of UW2.EXE, not inferred from the data. Interpreter at
file 0x75A95, in the overlay whose segment base is 0x745A0:

    [0x471a] = IP, in words        [0x46fa] = stack index (SP)
    [0x471e] = code array          [0x46fc] = stack base (far)
    [0x470e] = imported-function pointer array
    [0x4726] = saved SP (frame pointer)   [0x4714] = memory size in words

    entry: refuse to run unless code[0] == 0x22
    loop:  bx = code[IP]; if bx > 0x29 -> halt
           jmp word ptr cs:[bx*2 + 0x187b]

The 42-entry jump table is at file 0x75E1B (= segment base + 0x187B); it was
located by solving for the one base that puts all 42 targets inside the
interpreter -- a unique solution, and entry 0 lands on the instruction
immediately after the dispatch, as it must.

This is NOT the same VM as the threaded-code interpreter in ghidra.md 8-10:
that one dispatches through DAT_1224_0174 with ~111 entries from a different
site. UW2 runs two separate bytecode engines.

All 42 opcodes are decoded from their handlers; the helper address is noted
in the table for the ones that delegate. Strings reach the VM as STRINGS.PAK
ids: op 0x27/0x28 load the text with the game's string loader (lcall
0x148:0x97), run it through the '@'-substitution expander at 0x754F6, and
hand it to the builtin registered under the name "say" / "respond".
"""
import argparse
import struct
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cnv_decode as C  # noqa: E402

# opcode -> (mnemonic, instruction words, behaviour)
# Every entry is read from its handler in UW2.EXE; the helper address is given
# for the ones that delegate.  Binary ops take a = stack[SP-1], b = stack[SP],
# pop one, and leave the result on top.
OPS = {
    0x00: ("nop",     1, "advances IP only                        (0x75AE6)"),
    0x01: ("add",     1, "push a + b                              (0x75E6F)"),
    0x02: ("mul",     1, "push a * b, signed imul                 (0x75ECC)"),
    0x03: ("sub",     1, "push a - b                              (0x75F05)"),
    0x04: ("div",     1, "push a / b, idiv; 0x7FFF if b == 0      (0x75F3E)"),
    0x05: ("mod",     1, "push a % b, idiv rem; 0x7FFF if b == 0  (0x75F8E)"),
    0x06: ("or",      1, "push (a != 0 || b != 0)                 (0x75FDE)"),
    0x07: ("and",     1, "push (a != 0 && b != 0)                 (0x76023)"),
    0x08: ("not",     1, "top = (top == 0); neg/sbb/inc idiom     (0x75B7C)"),
    0x09: ("gt",      1, "push a > b                              (0x76068)"),
    0x0A: ("ge",      1, "push a >= b                             (0x760AA)"),
    0x0B: ("lt",      1, "push a < b                              (0x760EC)"),
    0x0C: ("le",      1, "push a <= b                             (0x7612E)"),
    0x0D: ("eq",      1, "push a == b                             (0x76170)"),
    0x0E: ("ne",      1, "push a != b                             (0x761B2)"),
    0x0F: ("jmp",     2, "IP = operand (absolute, in words)"),
    0x10: ("beq",     2, "pop; if == 0 then IP += 1 + operand"),
    0x11: ("bne",     2, "pop; if != 0 then IP += 1 + operand"),
    0x12: ("bra",     2, "IP += 1 + operand"),
    0x13: ("call",    2, "push IP+2; IP = operand                 (0x761F4)"),
    0x14: ("calli",   2, "far-call [0x470e] + operand*4; result -> [0x4708]  (0x762E4)"),
    0x15: ("ret",     1, "IP = pop; empty stack halts the VM      (0x76222)"),
    0x16: ("pushi",   2, "push the literal operand"),
    0x17: ("pusha",   2, "push [0x4714] + operand + [0x4726] (frame-relative address)"),
    0x18: ("drop",    1, "SP -= 1"),
    0x19: ("swap",    1, "exchange the top two stack slots"),
    0x1A: ("pushbp",  1, "push [0x4726]"),
    0x1B: ("popbp",   1, "[0x4726] = pop"),
    0x1C: ("setbp",   1, "[0x4726] = SP"),
    0x1D: ("setsp",   1, "SP = [0x4726]"),
    0x1E: ("alloc",   1, "SP += top - 1; with the preceding pushi N this reserves N slots"),
    0x1F: ("fetch",   1, "top = memory[top], memory = [0x4704]    (0x7624A)"),
    0x20: ("store",   1, "memory[a] = b; SP -= 2                  (0x762B1)"),
    0x21: ("addm1",   1, "push a + b - 1                          (0x76277)"),
    0x22: ("start",   1, "IP += 1; the interpreter requires code[0] == 0x22"),
    0x23: ("setres",  1, "[0x4708] = top, SP unchanged            (0x75DB2)"),
    0x24: ("getres",  1, "push [0x4708]                           (0x75DC9)"),
    0x25: ("streq",   1, "pop 2 string ids, load+expand both, push strcmp == 0  (0x76361)"),
    0x26: ("halt",    1, "clears the run flag"),
    0x27: ("say",     1, "load string id, @-expand, call the builtin named \"say\"      (0x76442)"),
    0x28: ("respond", 1, "load string id, @-expand, call the builtin named \"respond\"  (0x764EA)"),
    0x29: ("neg",     1, "top = -top                              (0x75EA8)"),
}
MAX_OP = 0x29


def info(op):
    return OPS[op]


def decode(conv):
    """Linear sweep. Returns [(ip, op, operand_or_None)]."""
    words = struct.unpack_from(f"<{conv.code_words}H", conv.code, 0)
    out, ip = [], 0
    while ip < len(words):
        op = words[ip]
        if op > MAX_OP:
            raise ValueError(f"invalid opcode {op:#06x} at word {ip}")
        _, width, _ = info(op)
        arg = words[ip + 1] if width == 2 else None
        out.append((ip, op, arg))
        ip += width
    if ip != len(words):
        raise ValueError(f"sweep overran: {ip} != {len(words)}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", type=int, help="disassemble one conversation")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--opcodes", action="store_true", help="print the opcode table")
    a = ap.parse_args()

    if a.opcodes:
        print(f"{'op':>4} {'mnemonic':<9} {'words':>5}  note")
        for op in range(MAX_OP + 1):
            m, w, note = info(op)
            print(f"0x{op:02X} {m:<9} {w:>5}  {note}")
        return

    d = C.CNV.read_bytes()
    off, _, _, _ = C.arrays(d)
    populated = [i for i in range(320) if off[i]]

    if a.slot is not None:
        conv, _ = C.load(d, a.slot)
        fns = {s: n for n, s, _, k, _ in conv.imports if k == 0x111}
        print(f"conversation slot {a.slot}: {conv.code_words} words, "
              f"strings block 0x{conv.string_block:04X}")
        for ip, op, arg in decode(conv)[:a.limit]:
            m, _, _ = info(op)
            if op == 0x14:
                text = f"{m} {fns.get(arg, arg)}"
            elif arg is not None:
                text = f"{m} {arg:#06x}"
            else:
                text = m
            print(f"  {ip:5d}  {text}")
        return

    clean = 0
    hist, calls = Counter(), Counter()
    for s in populated:
        conv, _ = C.load(d, s)
        fns = {sl: n for n, sl, _, k, _ in conv.imports if k == 0x111}
        try:
            ins = decode(conv)
        except ValueError as e:
            print(f"  slot {s}: {e}")
            continue
        clean += 1
        for _, op, arg in ins:
            hist[op] += 1
            if op == 0x14:
                calls[fns.get(arg, f"?{arg}")] += 1
    n = len(populated)
    print(f"conversations disassembling cleanly to exactly code_words: {clean}/{n}")
    print(f"  instructions: {sum(hist.values())}")
    print(f"  opcodes never used: {[hex(x) for x in range(MAX_OP + 1) if x not in hist]}")
    print(f"  calli operands resolving to a declared function import: "
          f"{sum(v for k, v in calls.items() if not str(k).startswith('?'))}"
          f"/{sum(calls.values())}")


if __name__ == "__main__":
    main()
