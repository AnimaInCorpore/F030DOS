#!/usr/bin/env python3
"""Reassembly ratchet for PANZER.EXE's code object (METHOD.md §2.4).

Re-encodes every decoded instruction with NASM, compares each at its intended
offset with the original bytes, demotes only the mismatching instruction to
`db`, and finally requires the whole object (raw file bytes, before loader
fixups) to rebuild byte-for-byte.  A byte-exact all-`db` rebuild proves
nothing, so the report states the share of real instructions.

    python3 tools/re/ratchet_le.py            # writes work/re/build/object1.asm
    python3 tools/re/ratchet_le.py --baseline # also freezes re/ratchet-baseline.txt

Branches are emitted `$`-relative with an explicit short/near form, so no
absolute address enters the encoding.  Each instruction is assembled in its own
16-byte slot, so one wrong length cannot shift its neighbours.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "re"))
import disasm_le as D  # noqa: E402

NASM = "nasm"
BUILD = ROOT / "work" / "re" / "build"
STRING_OPS = re.compile(r"^(?:rep[a-z]* )?(movs|stos|lods|scas|cmps|ins|outs)[bwd]$")
ALU_IMM = {"add", "or", "adc", "sbb", "and", "sub", "xor", "cmp", "push", "imul"}


def nasm_text(ins) -> str:
    """Intel text for NASM, with encodings forced where the compiler chose wide forms."""
    m, ops = ins.mnemonic, ins.op_str
    m = {"pushal": "pushad", "popal": "popad", "pushfd": "pushfd"}.get(m, m)
    if STRING_OPS.match(m):
        return m
    if not ops:
        return m
    if ins.mnemonic in ("call", "jmp") or ins.group(D.capstone.CS_GRP_JUMP) \
            or m in ("loop", "loope", "loopne", "jecxz", "jcxz"):
        o = ins.operands[0]
        if o.type == D.x86.X86_OP_IMM:
            delta = (o.imm & 0xFFFFFFFF) - ins.address
            if m == "call":
                return f"call $+{delta}"
            form = "short" if ins.size == 2 or m in ("loop", "loope", "loopne", "jecxz", "jcxz") else "near"
            return f"{m} {form} $+{delta}"
    ops = ops.replace(" ptr ", " ").replace("ptr ", "")
    ops = re.sub(r"\b([cdefgs]s):\[", r"[\1:", ops)           # cs:[x] -> [cs:x]
    ops = re.sub(r"st\((\d)\)", r"st\1", ops)
    if ins.imm_size in (2, 4) and m in ALU_IMM:
        mm = re.search(r"(-?0x[0-9a-f]+|-?\d+)$", ops)
        if mm:
            val = int(mm.group(1), 16) if "0x" in mm.group(1) else int(mm.group(1))
            if -128 <= val <= 127 or (val & 0xFFFFFFFF) >= 0xFFFFFF80:
                ops = ops[: mm.start()] + ("strict dword " if ins.imm_size == 4 else "strict word ") + mm.group(1)
    if ins.disp_size == 4 and "[" in ops:
        mm = re.search(r"([+-]) (0x[0-9a-f]+)\]", ops)
        if mm and int(mm.group(2), 16) < 0x80 and ("+" in ops.split("[")[1]):
            ops = ops.replace(mm.group(0), f"{mm.group(1)} dword {mm.group(2)}]")
    return f"{m} {ops}".strip()


def alt_encoding(orig: bytes, got: bytes) -> bool:
    """True when NASM chose the other direction of a reg-reg ALU/MOV form."""
    o, g = orig.lstrip(bytes([0x66])), got.rstrip(bytes(1)).lstrip(bytes([0x66]))
    if len(o) != 2 or len(g) != 2 or len(orig) != len(got.rstrip(bytes(1))):
        return False
    swapped = 0xC0 | ((g[1] & 7) << 3) | ((g[1] >> 3) & 7)
    return (o[0] ^ g[0]) == 2 and o[1] == swapped and (g[1] & 0xC0) == 0xC0


def run_nasm(src: Path, out: Path) -> str:
    r = subprocess.run([NASM, "-f", "bin", "-w-all", "-o", str(out), str(src)],
                       capture_output=True, text=True)
    return r.stderr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    args = ap.parse_args()
    seeds, anti = D.parse_seeds(ROOT / "re" / "seeds.txt")
    entries = [(v, "func" if k in ("ENTRY", "FUNC") else "code") for k, v, _ in seeds]
    insns, funcs, unresolved, tables, conflicts, _ptrs = D.build(entries, set())
    BUILD.mkdir(parents=True, exist_ok=True)

    obj = D.d[D.OBJ1_FILE:D.OBJ1_FILE + D.OBJ1_SIZE]
    items = []                                   # (vaddr, size, text or None)
    for v in sorted(insns):
        ins = next(D.md.disasm(D.d[D.v2f(v):D.v2f(v) + 15], v, 1))
        items.append((v, ins.size, nasm_text(ins), ins))

    # Pass 1: one slot per instruction.
    lines = ["bits 32"]
    for v, size, text, _ in items:
        lines.append(f"{text}")
        lines.append("times (16 - ($-$$) % 16) % 16 db 0")
    (BUILD / "slots.asm").write_text("\n".join(lines) + "\n", encoding="utf-8")
    err = run_nasm(BUILD / "slots.asm", BUILD / "slots.bin")
    demote: dict[int, str] = {}
    alt: dict[int, str] = {}
    if not (BUILD / "slots.bin").exists():
        # Some line did not assemble at all: find those by bisecting on the error text.
        bad = {int(m.group(1)) for m in re.finditer(r"slots\.asm:(\d+): error", err)}
        for ln in bad:
            idx = (ln - 2) // 2
            if 0 <= idx < len(items):
                demote[items[idx][0]] = "does not assemble: " + items[idx][2]
        lines2 = ["bits 32"]
        for v, size, text, _ in items:
            if v in demote:
                lines2.append("db " + ",".join(str(b) for b in D.d[D.v2f(v):D.v2f(v) + size]))
            else:
                lines2.append(text)
            lines2.append("times (16 - ($-$$) % 16) % 16 db 0")
        (BUILD / "slots.asm").write_text("\n".join(lines2) + "\n", encoding="utf-8")
        err = run_nasm(BUILD / "slots.asm", BUILD / "slots.bin")
        if not (BUILD / "slots.bin").exists():
            print(err[:2000])
            return 2
    slots = (BUILD / "slots.bin").read_bytes()
    for i, (v, size, text, ins) in enumerate(items):
        if v in demote:
            continue
        got = slots[i * 16:i * 16 + 16]
        orig = D.d[D.v2f(v):D.v2f(v) + size]
        if got[:size] != orig or any(got[size:]):
            if alt_encoding(orig, got):
                alt[v] = text
            else:
                demote[v] = f"{text} -> {got.rstrip(bytes(1)).hex()} (orig {orig.hex()})"

    # Pass 2: contiguous rebuild of the whole object.
    out = []
    pos = D.OBJ1_BASE
    end = D.OBJ1_BASE + D.OBJ1_SIZE
    ndb_bytes = 0

    def db(lo, hi):
        for k in range(lo, hi, 16):
            chunk = obj[k - D.OBJ1_BASE:min(k + 16, hi) - D.OBJ1_BASE]
            out.append("db " + ",".join(f"0x{b:02X}" for b in chunk))

    for v, size, text, _ in items:
        if v > pos:
            db(pos, v)
            ndb_bytes += v - pos
        if v in demote:
            db(v, v + size)
            ndb_bytes += size
        elif v in alt:
            out.append("db " + ",".join(f"0x{b:02X}" for b in D.d[D.v2f(v):D.v2f(v) + size])
                       + f"    ; {text} [alt-encoding] {v:X}")
        else:
            out.append(f"{text}    ; {v:X}")
        pos = v + size
    if pos < end:
        db(pos, end)
        ndb_bytes += end - pos
    (BUILD / "object1.asm").write_text("bits 32\n" + "\n".join(out) + "\n", encoding="utf-8")
    err = run_nasm(BUILD / "object1.asm", BUILD / "object1.bin")
    rebuilt = (BUILD / "object1.bin").read_bytes() if (BUILD / "object1.bin").exists() else b""
    want = hashlib.sha256(obj).hexdigest()
    got = hashlib.sha256(rebuilt).hexdigest()
    n_ins = len(items)
    n_ok = n_ins - len(demote) - len(alt)
    print(f"instructions {n_ins}; re-encoded exactly {n_ok} ({100 * n_ok / n_ins:.2f}%); "
          f"alternate-encoding (bytes, mnemonic kept) {len(alt)}; demoted to db {len(demote)}")
    print(f"object 1: {D.OBJ1_SIZE} bytes; as db: {ndb_bytes}; "
          f"real-instruction bytes {D.OBJ1_SIZE - ndb_bytes} "
          f"({100 * (D.OBJ1_SIZE - ndb_bytes) / D.OBJ1_SIZE:.1f}%)")
    print(f"rebuilt {len(rebuilt)} bytes; whole-object SHA-256 equal: {want == got}")
    cls = Counter()
    for v, why in demote.items():
        cls[why.split()[0]] += 1
    print("demotions by mnemonic:", cls.most_common(14))
    for v, why in list(demote.items())[:8]:
        print(f"  {v:X}: {why}")
    (BUILD / "demoted.txt").write_text(
        "".join(f"{v:X} {why}" + chr(10) for v, why in sorted(demote.items())), encoding="utf-8")
    if args.baseline and want == got:
        (ROOT / "re" / "ratchet-baseline.txt").write_text(
            f"# Reassembly ratchet baseline for PANZER.EXE object 1 (tools/re/ratchet_le.py).\n"
            f"# A coverage regression below must be an explicit, reviewed correction.\n"
            f"object1_sha256={want}\ninstructions={n_ins}\nexact={n_ok}\n"
            f"alt_encoding={len(alt)}\ndemoted={len(demote)}\nreal_instruction_bytes={D.OBJ1_SIZE - ndb_bytes}\n",
            encoding="utf-8")
        print("froze re/ratchet-baseline.txt")
    return 0 if want == got else 1


if __name__ == "__main__":
    raise SystemExit(main())
