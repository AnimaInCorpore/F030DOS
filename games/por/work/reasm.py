#!/usr/bin/env python3
"""Reassembly proof: disassemble an image, emit NASM source, assemble it, and
require the result to be **byte-identical** to the original.

Why this exists
---------------
A disassembly listing is a claim. Coverage percentages do not test it: a wrong
instruction length silently corrupts every byte after it and still "looks like"
a disassembly. Re-encoding and comparing is the only objective proof that the
code/data split and every instruction boundary are right.

The ratchet
-----------
The harness never fails to produce a byte-exact rebuild. Any instruction whose
re-encoding differs from the original bytes is demoted to `db` and the file is
rebuilt, until the output matches exactly. What moves is the **ratio**:

    bytes emitted as real instructions  /  total bytes

That number is the score. It may only go up; byte-exactness is an invariant,
never a goal to be traded away.

Usage:
    python3 work/reasm.py unit 18E          # one GAME.OVR overlay unit
    python3 work/reasm.py start             # START.EXE load image
"""
import json, os, re, subprocess, sys, struct, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from disasm import Image, walk, load_start                      # noqa: E402
from overlay import units                                       # noqa: E402

NASM = os.environ.get("NASM", "nasm")

# capstone Intel -> NASM syntax
SEG_MEM = re.compile(r"\b(cs|ds|es|ss|fs|gs):\[")


def to_nasm(text, targets):
    """Translate one capstone instruction to NASM, or return None if unsupported."""
    m, _, ops = text.partition(" ")
    ops = ops.strip()

    # far call/jump: capstone prints "lcall 0x5bb, 0x0"
    if m in ("lcall", "ljmp"):
        parts = [p.strip() for p in ops.split(",")]
        if len(parts) != 2:
            return None
        return f"{'call' if m == 'lcall' else 'jmp'} far {parts[0]}:{parts[1]}"

    # "word ptr [bx]" / "les di, ptr [bx]": NASM takes the sized operand
    # without "ptr"; dropping the token keeps the encoding identical.
    ops = re.sub(r"\bptr\b", "", ops)
    ops = re.sub(r"  +", " ", ops).strip()
    ops = SEG_MEM.sub(r"[\1:", ops)         # "es:[di]"       -> "[es:di]"

    # branch targets become labels so NASM computes the displacement itself
    if m in ("jmp", "call", "je", "jne", "jb", "jae", "jbe", "ja", "jl", "jge",
             "jle", "jg", "js", "jns", "jo", "jno", "jp", "jnp", "jcxz",
             "loop", "loope", "loopne") and re.fullmatch(r"0x[0-9a-f]+", ops):
        t = int(ops, 16)
        if t in targets:
            # short/near forms differ in size; let the verifier demote if wrong
            return f"{m} L_{t:04X}"
        return None
    return f"{m} {ops}".strip()


def emit(img, insns, labels, forced_data, path, hard=frozenset()):
    """Write NASM source.

    Returns (claims, code_bytes): `claims` is {source_line: (addr, original
    bytes)} for every line that claims to be a re-encoded instruction, and
    `code_bytes` counts the bytes actually written as instruction lines.

    Counting here rather than from `insns` matters. The emitter walks the image
    linearly and only uses `insns[pc]` when the cursor lands exactly on `pc`,
    so any entry the walk found at an offset a longer preceding instruction
    covers is silently skipped. Summing `insns` sizes instead counted those
    twice and over-reported the score by 0.7 % overall (`AGENTS.md`
    §Next steps item 2 carried the inflated figure until 2026-08-22). An
    `INT 3Fh` thunk likewise contributes 2 instruction bytes, not 5 -- its
    operand `dw`/`db` are data.

    `hard` is a set of addresses that are known function entry points (a
    unit's thunk targets). No instruction may span one: if the cursor is on a
    decode that would swallow an entry point, the byte is emitted as `db` and
    the cursor realigns onto the entry. Without this the linear cursor can
    reach an entry from a bogus preceding decode and emit that instead --
    it did so at exactly three of the 758 entry points, each time swallowing a
    `55 89 E5` prologue (`020:11B1`, `0D9:19F7`, `0E2:108F`). The rebuild stayed
    byte-exact throughout, because a wrong decode that re-encodes to the same
    bytes still round-trips; byte-exactness proves the bytes, not that every
    boundary is the one the compiler emitted."""
    n = len(img.data)
    out = ["bits 16", "org 0"]
    claims = {}
    code_bytes = 0
    pc = 0
    pending = bytearray()

    def flush():
        if pending:
            for i in range(0, len(pending), 16):
                out.append("    db " + ",".join(f"0x{b:02x}" for b in pending[i:i + 16]))
            pending.clear()

    while pc < n:
        if pc in labels:
            flush()
            out.append(f"L_{pc:04X}:")
        ent = insns.get(pc)
        if ent and pc not in forced_data:
            size, text, mn = ent
            if mn == "int3f":
                flush()
                out.append("    int 0x3f")
                claims[len(out)] = (pc, img.data[pc:pc + 2])
                out.append(f"    dw 0x{struct.unpack_from('<H', img.data, pc + 2)[0]:04x}")
                out.append(f"    db 0x{img.data[pc + 4]:02x}")
                code_bytes += 2          # the INT itself; the rest is data
                pc += 5
                continue
            asm = to_nasm(text, labels)
            if asm and any(a in hard for a in range(pc + 1, pc + size)):
                asm = None                   # would swallow an entry point
            if asm:
                flush()
                out.append(f"    {asm}")
                claims[len(out)] = (pc, img.data[pc:pc + size])
                code_bytes += size
                pc += size
                continue
        pending.append(img.data[pc])
        pc += 1
    flush()
    open(path, "w").write("\n".join(out) + "\n")
    return claims, code_bytes
    return claims


LST = re.compile(r"^\s*(\d+) ([0-9A-F]{8}) ((?:[0-9A-F]{2})+)")


def listing_bytes(path):
    """Parse a NASM -l listing into {line: emitted bytes}."""
    out, last = {}, None
    for raw in open(path, errors="replace"):
        mo = LST.match(raw)
        if mo:
            last = int(mo.group(1))
            out[last] = bytes.fromhex(mo.group(3))
        elif last is not None:
            cont = re.match(r"^\s+([0-9A-F]{8}) ((?:[0-9A-F]{2})+)", raw)
            if cont:
                out[last] += bytes.fromhex(cont.group(2))
            else:
                last = None
    return out


def assemble(src, dst, lst):
    # -Wno-label-redef-late: NASM >= 3.0 makes pass-1/pass-2 label shifts a
    # hard error; 2.16 warned. A shifted branch is exactly what the ratchet
    # demotes via the listing, so the check must not abort the pass first.
    # (NASM's -W has no "class:state" form; "-Wno-x" is the real syntax.)
    r = subprocess.run([NASM, "-f", "bin", "-o", dst, "-l", lst,
                        "-Wno-label-redef-late", src],
                       capture_output=True, text=True)
    return r.returncode == 0, r.stderr


def roundtrip(img, insns, labels, tag, outdir, hard=frozenset()):
    """Demote exactly the instructions NASM re-encodes differently, until the
    rebuilt image is byte-identical to the original."""
    os.makedirs(outdir, exist_ok=True)
    src = os.path.join(outdir, f"{tag}.asm")
    binp = os.path.join(outdir, f"{tag}.bin")
    lstp = os.path.join(outdir, f"{tag}.lst")
    forced = set()
    for attempt in range(1, 25):
        claims, code_bytes = emit(img, insns, labels, forced, src, hard)
        ok, err = assemble(src, binp, lstp)
        if not ok:
            # NASM refused a line: demote exactly the instruction on that line
            # nasm's "file:line: severity: message"; the file may itself
            # contain colons (Windows drive letters), so anchor on the
            # severity word rather than line-start.
            bad = {int(mo.group(1)) for mo in re.finditer(r":(\d+): error:", err)}
            newly = {claims[ln][0] for ln in bad if ln in claims}
            if not newly:
                first = err.strip().splitlines()[0] if err.strip() else "(no message)"
                print(f"  {tag}: nasm error not attributable to a claim: {first}")
                return None
            forced |= newly
            continue

        gen = listing_bytes(lstp)
        newly = {addr for ln, (addr, orig) in claims.items()
                 if gen.get(ln) != orig}
        if newly:
            forced |= newly
            continue

        got = open(binp, "rb").read()
        if got == img.data:
            return forced, attempt, code_bytes
        # every claim re-encoded exactly yet the image differs: emitter bug
        d = next(i for i in range(min(len(got), len(img.data)))
                 if got[i] != img.data[i]) if got != img.data else -1
        print(f"  {tag}: all claims match but image differs at 0x{d:X} "
              f"(len {len(got)} vs {len(img.data)})")
        return None
    return None


def build_unit(seg):
    ovr = open(os.path.join(HERE, "expanded", "GAME.OVR"), "rb").read()
    us, _ = units()
    u = next(x for x in us if x["seg"] == seg)
    fo, cs, fx = u["file_offset"], u["code_size"], u["fixup_size"]
    fixups = {struct.unpack_from("<H", ovr, fo + cs + 2 * i)[0] for i in range(fx // 2)}
    img = Image(ovr[fo:fo + cs], fo, {f for f in fixups if f < cs}, f"unit {seg:03X}")
    seeds = [t for t in u["thunks"] if t < cs]
    return img, seeds


def main():
    what = sys.argv[1]
    if what == "unit":
        seg = int(sys.argv[2], 16)
        img, seeds = build_unit(seg)
        tag = f"unit{seg:03X}"
    else:
        img, entry = load_start(os.path.join(HERE, "expanded", "START.EXE"))
        seeds = [entry]
        tag = "start"

    seen, starts, insns, calls, farcalls, ints, ports, thunks = walk(img, seeds)
    labels = set(starts) | set(calls)
    for pc, (size, text, mn) in insns.items():
        mo = re.fullmatch(r"\w+ (0x[0-9a-f]+)", text)
        if mo:
            t = int(mo.group(1), 16)
            if 0 <= t < len(img.data):
                labels.add(t)

    res = roundtrip(img, insns, labels, tag, os.path.join(HERE, "reasm"),
                    hard=frozenset(seeds))
    if res is None:
        print(f"{tag}: NO byte-exact rebuild")
        return 1
    forced, attempts, code_bytes = res
    # Record which instructions were demoted, and how big they were. These are
    # bytes the disassembly *did* recover as code -- NASM just re-encodes them
    # differently -- so they are not part of the unexplained residue, and
    # work/dbmap.py needs to tell the two apart.
    json.dump({f"{pc:04X}": insns[pc][0] for pc in sorted(forced)},
              open(os.path.join(HERE, "reasm", f"{tag}.forced.json"), "w"))
    total = len(img.data)
    print(f"{tag}: BYTE-EXACT rebuild in {attempts} pass(es); "
          f"{code_bytes}/{total} bytes ({100*code_bytes/total:.1f}%) emitted as "
          f"instructions, {len(forced)} demoted to db")
    return 0


if __name__ == "__main__":
    sys.exit(main())
