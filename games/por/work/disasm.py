#!/usr/bin/env python3
"""16-bit real-mode recursive-descent disassembler for the POR executables.

There is no Ghidra on this machine, so this is the project's disassembler.
It works on linear offsets into the *load image* (the bytes DOS actually maps),
because the same byte can be addressed by many seg:off pairs.

    START.EXE   MZ; load image starts at e_cparhdr*16, entry at e_cs:e_ip.
    GAME.OVR    raw overlay; no header, no declared entry — seed it explicitly.

Relocation entries are used as ground truth for "this word is a segment", which
keeps the walker from disassembling fixup words as code.

    python3 work/disasm.py start  [out.txt]
    python3 work/disasm.py game   [out.txt] [seed ...]
"""
import struct, sys, os, collections
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
from capstone.x86 import X86_OP_IMM, X86_OP_MEM

EXPANDED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expanded")

INT21 = {
    0x09: "print $-string", 0x0a: "buffered input", 0x19: "get default drive",
    0x1a: "set DTA", 0x25: "set interrupt vector", 0x2f: "get DTA",
    0x30: "get DOS version", 0x35: "get interrupt vector", 0x36: "get free space",
    0x39: "mkdir", 0x3b: "chdir", 0x3c: "create file", 0x3d: "open file",
    0x3e: "close file", 0x3f: "read file", 0x40: "write file", 0x41: "delete file",
    0x42: "seek", 0x43: "get/set attributes", 0x44: "ioctl", 0x47: "get cwd",
    0x48: "allocate memory", 0x49: "free memory", 0x4a: "resize memory block",
    0x4b: "EXEC / load overlay", 0x4c: "terminate", 0x4e: "find first",
    0x4f: "find next",
}


class Image:
    def __init__(self, data, base, relocs, name):
        self.data = data          # the load image only
        self.base = base          # file offset of load image start
        self.relocs = relocs      # set of linear offsets holding segment words
        self.name = name


def load_start(path):
    d = open(path, "rb").read()
    cparhdr, = struct.unpack_from("<H", d, 8)
    crlc, = struct.unpack_from("<H", d, 6)
    lfarlc, = struct.unpack_from("<H", d, 0x18)
    ip, cs = struct.unpack_from("<HH", d, 0x14)
    hdr = cparhdr * 16
    relocs = set()
    for i in range(crlc):
        off, seg = struct.unpack_from("<HH", d, lfarlc + i * 4)
        relocs.add(seg * 16 + off)
    return Image(d[hdr:], hdr, relocs, "START.EXE"), cs * 16 + ip


def load_game(path):
    return Image(open(path, "rb").read(), 0, set(), "GAME.OVR")


STOP = {"ret", "retf", "iret", "iretd", "jmp", "ljmp", "hlt"}


def walk(img, seeds, limit=None):
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = True
    data, n = img.data, len(img.data)
    seen = set()                       # linear offsets already decoded
    starts = set()                     # discovered routine entries
    insns = {}                         # linear -> (size, text, mnemonic)
    calls = collections.Counter()
    thunks = {}
    farcalls = collections.Counter()
    ints = collections.Counter()
    ports = collections.Counter()
    queue = list(seeds)
    starts.update(seeds)

    while queue:
        pc = queue.pop()
        if pc in seen or pc < 0 or pc >= n:
            continue
        ah = None
        while 0 <= pc < n and pc not in seen:
            if pc in img.relocs:
                break
            chunk = data[pc:pc + 16]
            got = md.disasm(chunk, pc, count=1)
            ins = next(iter(got), None)
            if ins is None or ins.mnemonic in ("(bad)",):
                break
            seen.add(pc)
            insns[pc] = (ins.size, f"{ins.mnemonic} {ins.op_str}".strip(), ins.mnemonic)

            m, ops = ins.mnemonic, ins.operands
            # Turbo Pascal overlay stub: INT 3Fh is followed by a 3-byte
            # descriptor (DW offset, DB 0), not by code. Step over it and keep
            # going, exactly as the overlay manager's IRET does.
            if m == "int" and ops and ops[0].type == X86_OP_IMM and ops[0].imm == 0x3F:
                off = struct.unpack_from("<H", data, pc + 2)[0]
                thunks[pc] = (off, data[pc + 4])
                insns[pc] = (5, f"int 3Fh  ; overlay stub -> +{off:04X}", "int3f")
                seen.update(range(pc, pc + 5))
                pc += 5
                continue
            if m == "mov" and len(ops) == 2 and ops[1].type == X86_OP_IMM \
                    and ins.op_str.startswith("ah,"):
                ah = ops[1].imm & 0xFF
            elif m == "int" and ops and ops[0].type == X86_OP_IMM:
                v = ops[0].imm
                ints[(v, ah if v == 0x21 else None)] += 1
            elif m in ("in", "out"):
                ports[ins.op_str] += 1
            elif m == "call":
                if ops and ops[0].type == X86_OP_IMM:
                    t = ops[0].imm
                    if 0 <= t < n:
                        calls[t] += 1; starts.add(t)
                        if t not in seen:
                            queue.append(t)

            elif m in ("lcall", "ljmp") and len(ops) == 2 \
                    and ops[0].type == X86_OP_IMM and ops[1].type == X86_OP_IMM:
                # capstone emits far targets as (segment, offset)
                lin = ops[0].imm * 16 + ops[1].imm
                farcalls[(ops[0].imm, ops[1].imm)] += 1
                if 0 <= lin < n:
                    starts.add(lin)
                    if lin not in seen:
                        queue.append(lin)
            elif m in ("jmp", "je", "jne", "jb", "jae", "jbe", "ja", "jl", "jge",
                       "jle", "jg", "js", "jns", "jo", "jno", "jp", "jnp",
                       "jcxz", "loop", "loope", "loopne"):
                if ops and ops[0].type == X86_OP_IMM:
                    t = ops[0].imm
                    if 0 <= t < n and t not in seen:
                        queue.append(t)

            pc += ins.size
            if m in STOP:
                break
            if limit and len(seen) > limit:
                queue = []
                break
    return seen, starts, insns, calls, farcalls, ints, ports, thunks


def emit(img, insns, starts, path):
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    with open(path, "w") as fh:
        fh.write(f"; {img.name} — recursive descent, {len(insns)} instructions, "
                 f"{len(starts)} routine entries\n")
        fh.write(f"; linear offsets are into the load image "
                 f"(file offset = linear + 0x{img.base:X})\n\n")
        for pc in sorted(insns):
            size, text, m = insns[pc]
            if pc in starts:
                fh.write(f"\n; ---- routine @ {pc:06X} (file {pc + img.base:06X})\n")
            raw = img.data[pc:pc + size].hex()
            fh.write(f"{pc:06X}  {raw:<14s}  {text}\n")


def main():
    which = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else f"work/{which}16.txt"
    if which == "start":
        img, entry = load_start(os.path.join(EXPANDED, "START.EXE"))
        seeds = [entry]
    else:
        img = load_game(os.path.join(EXPANDED, "GAME.OVR"))
        seeds = [int(x, 0) for x in sys.argv[3:]] or [0x26]
    seen, starts, insns, calls, farcalls, ints, ports, thunks = walk(img, seeds)
    emit(img, insns, starts, out)
    print(f"{img.name}: {len(insns)} instructions covering {len(seen)} bytes of "
          f"{len(img.data)} ({100*len(seen)//len(img.data)}%), "
          f"{len(starts)} routine entries -> {out}")
    if ints:
        print("  interrupts:")
        for (v, ah), c in sorted(ints.items(), key=lambda x: -x[1])[:16]:
            note = f" AH={ah:02X} {INT21.get(ah,'?')}" if v == 0x21 and ah is not None else ""
            print(f"    int {v:02X}h{note}  x{c}")
    if ports:
        print("  port I/O:", dict(ports.most_common(8)))
    if thunks:
        print(f"  overlay stubs: {len(thunks)} INT 3Fh sites reached")
        import json
        with open(out.replace(".txt", "_thunks.json"), "w") as fh:
            json.dump({f"{k:06X}": [v[0], v[1]] for k, v in sorted(thunks.items())}, fh, indent=0)
    if farcalls:
        print("  far calls:", [f"{s:04X}:{o:04X} x{c}" for (s, o), c in farcalls.most_common(6)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
