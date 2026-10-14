#!/usr/bin/env python3
"""P4.2 reassembly ratchet (METHOD.md 2.4) -- 16-bit stub and 32-bit obj1.

The core technique of METHOD.md 2.4: emit assembler from the listing, assemble
it, compare PER INSTRUCTION at each line's intended offset, demote every
mismatch to `db`, and repeat. Byte-exactness is the invariant -- the loop always
terminates there. What moves is the score: bytes emitted as real instructions
over total bytes.

  python3 work/ratchet16.py [--out DIR] [--unit stub|obj1] [--range LO HI]
                           [--branch-batch N] [--debug]

`--unit obj1` ratchets the 32-bit code object, seeded from the capstone sweep
(analysis/32bit/functable_v2.txt) and the LE fixup targets rather than from a
single entry point. `--range LO HI` restricts it to a slice, e.g. one module
span from work/ghidra_export/module_map.txt.

Disassembly is seeded recursive descent from the MZ entry (METHOD.md 2.3),
never a linear sweep: a wrong instruction length silently corrupts everything
after it and still looks like a listing.
"""
import os
import re
import struct
import subprocess
import sys

import capstone

OBJ1_RAW = "work/ghidra/z_tie_obj1.raw"
OBJ1_BASE = 0x10000
SWEEP = "analysis/32bit/functable_v2.txt"

EXE = "game/SWTieCD/TIECD/Z_TIE__.EXE"
STUB_OFF = 0x60          # MZ header is 6 paragraphs
STUB_LEN = 10734         # (pages-1)*512 + lastpage - header


def load_stub():
    d = open(EXE, "rb").read()
    hdrpar, ip, cs = struct.unpack_from("<H", d, 8)[0], \
        struct.unpack_from("<H", d, 20)[0], struct.unpack_from("<H", d, 22)[0]
    nrel, relof = struct.unpack_from("<H", d, 6)[0], struct.unpack_from("<H", d, 24)[0]
    rels = [struct.unpack_from("<HH", d, relof + 4 * i)[0] for i in range(nrel)]
    return d[STUB_OFF:STUB_OFF + STUB_LEN], cs * 16 + ip, sorted(rels)


STOP = {"ret", "retf", "iret", "iretd", "hlt", "jmp", "ljmp"}

BITS = 16          # set to 32 by main() for --unit obj1
GUARD = set()      # data-guard offsets, filled by main()


def load_obj1(lo=None, hi=None):
    """-> (code, seeds) for the 32-bit code object, or a slice of it.

    Seeded from the capstone sweep (analysis/32bit/functable_v2.txt) and, when
    present, Ghidra's function starts -- not from one entry point: obj1 is a
    flat object with no single entry, and METHOD.md 2.3 says seed, never sweep.
    """
    raw = open(OBJ1_RAW, "rb").read()
    lo = OBJ1_BASE if lo is None else lo
    hi = OBJ1_BASE + len(raw) if hi is None else hi
    code = raw[lo - OBJ1_BASE:hi - OBJ1_BASE]
    seeds = set()
    for line in open(SWEEP):
        if line.startswith("0x"):
            lin = OBJ1_BASE + (int(line.split()[0], 16) - 0x3D800)
            if lo <= lin < hi:
                seeds.add(lin - lo)
    exp = "work/ghidra_export/obj1_functions.macos.txt"
    if os.path.exists(exp):
        for line in open(exp):
            q = line.split()
            if len(q) >= 4 and len(q[0]) == 8:
                try:
                    a = int(q[0], 16)
                except ValueError:
                    continue
                if lo <= a < hi:
                    seeds.add(a - lo)
    return code, sorted(seeds)


# Two forms: a NUL-terminated C literal, or any long printable block. The
# NUL-only version missed the 144-byte WATCOM banner entirely -- it is a
# multi-line legal notice with no NUL inside the matched window.
STR_RUN = re.compile(rb"[\x20-\x7e]{8,}\x00|[\x20-\x7e\r\n\t]{16,}")


def pointer_table_guard(lo, hi):
    """Offsets of function-pointer tables, from the LE fixup table itself.

    Not a heuristic: a run of fixup SOURCE sites in obj1 spaced exactly 4 bytes
    apart is an array of relocatable dwords, i.e. a jump/dispatch table -- data.
    Without this the ratchet decodes them as instructions and scores them as
    code; all 116 B of the four FILM/typeCode dispatch tables (analysis/LFD.md
    6b) were being counted that way.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import audit_fixups as af
    except Exception:
        return set()
    sites = []
    for i in range(af.num_pages):
        n, _o = af.obj_of_page(i)
        if n != 1:
            continue
        base = af.linear_of_page(i)
        recs, _s, _e = af.decode_page(i)
        for r in recs:
            if r["tt"] == 0 and r["stype"] == 7:
                for so in r["srcoffs"]:
                    sites.append(base + so)
    sites.sort()
    out, run = set(), [sites[0]] if sites else []
    for a in sites[1:]:
        if a - run[-1] == 4:
            run.append(a)
        else:
            if len(run) >= 3:
                for x in run:
                    out.update(range(x, x + 4))
            run = [a]
    if len(run) >= 3:
        for x in run:
            out.update(range(x, x + 4))
    return {a - lo for a in out if lo <= a < hi}


def data_guard(code):
    """Offsets that are almost certainly DATA, not code.

    Without this the score is inflated: string literals decode into x86 that
    re-encodes identically, so they pass the ratchet and get counted as "real
    instructions". In this stub the 144-byte `WATCOM C Run-Time system code`
    banner did exactly that, along with `Not enough memory`, `Stack Overflow!`
    and 24 more -- 342 of 666 bytes of obvious text.

    Deliberately conservative, and a heuristic, not a proof: NUL-terminated
    printable runs of >= 8, and zero runs of >= 8. Anything it misses still
    inflates the net score; anything it wrongly flags only deflates it.
    """
    out = set()
    for m in STR_RUN.finditer(code):
        out.update(range(m.start(), m.end()))
    z = 0
    for i, b in enumerate(code):
        if b == 0:
            z += 1
        else:
            if z >= 8:
                out.update(range(i - z, i))
            z = 0
    if z >= 8:
        out.update(range(len(code) - z, len(code)))
    return out


def gaps_of(code, covered):
    out, i = [], 0
    while i < len(code):
        if i in covered:
            i += 1
            continue
        j = i
        while j < len(code) and j not in covered:
            j += 1
        out.append((i, j - i))
        i = j
    return out


def orphan_seeds(code, covered):
    """Start of each not-yet-covered region (work/sweep32.py's orphan scan).

    NOT a linear sweep: each is only a seed for recursive descent, and a descent
    is accepted (in main) only if it terminates on a real tail instruction. The
    ratchet is the backstop -- a bad seed costs score, never correctness, because
    anything that fails to re-encode is demoted to `db`.

    `55 8B EC` prologue anchoring, which works on other targets, is useless here:
    that pattern occurs exactly ONCE in this stub (Watcom's 16-bit codegen barely
    uses bp frames).
    """
    return [off for off, _n in gaps_of(code, covered) if off not in GUARD]


_MD = None


def _md():
    """One capstone instance. Building it per descend() call -- i.e. per orphan
    seed, per round -- is what made the 700 KB object intractable."""
    global _MD
    if _MD is None:
        _MD = capstone.Cs(capstone.CS_ARCH_X86,
                          capstone.CS_MODE_32 if BITS == 32 else capstone.CS_MODE_16)
        _MD.detail = True
    return _MD


def descend(code, entry, seen=None):
    """Seeded recursive descent -> {offset: (length, mnemonic, op_str)}."""
    md = _md()
    out = {}
    seen = set() if seen is None else seen
    queue = list(entry) if isinstance(entry, (list, set)) else [entry]
    while queue:
        pc = queue.pop()
        while 0 <= pc < len(code) and pc not in seen:
            seen.add(pc)
            ins = next(md.disasm(code[pc:pc + 16], pc), None)
            if ins is None:
                break
            out[pc] = (ins.size, ins.mnemonic, ins.op_str)
            m, ops = ins.mnemonic, ins.op_str
            if m in ("call", "jmp") or m.startswith("j"):
                if re.fullmatch(r"0x[0-9a-f]+", ops):
                    t = int(ops, 16)
                    if 0 <= t < len(code) and t not in seen:
                        queue.append(t)
            if m in STOP:
                break
            pc += ins.size
    return out


def to_nasm(off, size, mnem, ops, labels):
    """capstone Intel -> NASM, or None if this instruction should stay `db`."""
    ops = ops.replace("ptr ", "")
    # capstone writes `word cs:[bx]`; NASM wants `word [cs:bx]`
    ops = re.sub(r"\b(cs|ds|es|ss|fs|gs):\[", r"[\1:", ops)
    if mnem in ("call", "jmp") or (mnem.startswith("j") and mnem != "jmp"):
        # capstone prints small branch targets in decimal ("0", "8"), not hex --
        # missing that emitted them as ABSOLUTE immediates via the indirect path
        # below, which shifted every later label and cascaded into ~200 bogus
        # call mismatches.
        if re.fullmatch(r"0x[0-9a-f]+|\d+", ops):
            t = int(ops, 0)
            if t in labels:
                if mnem == "call":
                    return f"call {'near ' if size == 3 else ''}L_{t:04x}"
                if mnem == "jmp":
                    return f"jmp {'short' if size == 2 else 'near'} L_{t:04x}"
                return f"{mnem} {'short' if size == 2 else 'near'} L_{t:04x}"
            return None                   # direct branch to a non-instruction
        if mnem in ("call", "jmp"):
            # indirect forms (`call bx`, `jmp word [si+4]`) need no label and
            # NASM encodes them the same way -- 369 B of the first run's losses
            return f"{mnem} {ops}"
        return None
    if mnem in ("nop", "ret", "retf", "iret", "cld", "std", "cli", "sti", "pushf",
                "popf", "cbw", "cwd", "leave", "into", "hlt", "sahf", "lahf"):
        return mnem if not ops else f"{mnem} {ops}"
    return f"{mnem} {ops}".strip()


def emit(code, insns, demoted, forced=None):
    """-> (source text, [(line_index, offset, expected_bytes)])."""
    forced = forced or {}
    labels = set(insns)
    lines = [f"bits {BITS}", "org 0", ""]
    index = []
    off = 0
    while off < len(code):
        if off in labels:
            lines.append(f"L_{off:04x}:")
        item = insns.get(off)
        text = None
        if item and off not in demoted:
            text = to_nasm(off, item[0], item[1], item[2], labels)
        if text and off in forced:
            text = forced[off]
        if text:
            size = item[0]
            index.append((len(lines), off, code[off:off + size]))
            lines.append(f"    {text}")
            off += size
        else:
            index.append((len(lines), off, code[off:off + 1]))
            lines.append(f"    db 0x{code[off]:02x}")
            off += 1
    return "\n".join(lines) + "\n", index


LST = re.compile(r"^\s*(\d+)\s+([0-9A-F]{8})\s+([0-9A-F<>\-]*)")

IMM = re.compile(r"(,\s*)(-?(?:0x[0-9a-f]+|\d+))\s*$")


def variants(text):
    """Candidate encodings for one instruction, widest-intent first.

    NASM picks an operand size when the source does not force one, and its
    choice does not always match the original compiler's. `strict byte` /
    `strict word` force it. Only the trailing immediate is touched -- branches
    are position-dependent and handled by the label path instead.
    """
    out = [text]
    m = IMM.search(text)
    if m:
        for kw in ("strict byte ", "strict word ", "strict dword "):
            out.append(text[:m.start()] + m.group(1) + kw + m.group(2))
    # Memory displacement width. Watcom emits `lea eax,[eax]` as 8D 40 00 -- an
    # explicit zero disp8 -- where NASM picks the shorter 8D 00.
    # NASM wants the size keyword BEFORE the register: `[byte eax+0]`, not
    # `[eax+byte 0]` (which it rejects outright).
    m2 = re.search(r"\[([a-z][a-z0-9]*)\]", text)
    if m2:
        for kw in ("byte", "dword"):
            out.append(text[:m2.start()] + f"[{kw} {m2.group(1)}+0]" + text[m2.end():])
    m3 = re.search(r"\[([a-z][a-z0-9]*)\s*([+-])\s*(0x[0-9a-f]+|\d+)\]", text)
    if m3:
        for kw in ("byte", "dword"):
            out.append(text[:m3.start()]
                       + f"[{kw} {m3.group(1)}{m3.group(2)}{m3.group(3)}]"
                       + text[m3.end():])
    return out


def probe_variants(cands, outdir):
    """Assemble every candidate once and return {index: bytes}.

    Safe to batch: none of these forms is position-dependent.
    """
    lines = [f"bits {BITS}"]
    for t in cands:
        lines.append(f"    {t}")
    src = "\n".join(lines) + "\n"
    asm = os.path.join(outdir, "probe.asm")
    lst = os.path.join(outdir, "probe.lst")
    binf = os.path.join(outdir, "probe.bin")
    open(asm, "w").write(src)
    r = subprocess.run(["nasm", "-f", "bin", "-l", lst, "-o", binf, asm],
                       capture_output=True, text=True)
    bad = {int(m) for m in re.findall(r"probe\.asm:(\d+):", r.stderr)}
    if r.returncode and not bad:
        return {}
    if bad:                       # drop the offenders and retry once
        keep = [i for i in range(len(cands)) if i + 2 not in bad]
        lines = [f"bits {BITS}"] + [f"    {cands[i]}" for i in keep]
        open(asm, "w").write("\n".join(lines) + "\n")
        r = subprocess.run(["nasm", "-f", "bin", "-l", lst, "-o", binf, asm],
                           capture_output=True, text=True)
        if r.returncode:
            return {}
        mapping = {i + 2: keep[i] for i in range(len(keep))}
    else:
        mapping = {i + 2: i for i in range(len(cands))}
    out = {}
    for line in open(lst):
        m = LST.match(line)
        if not m:
            continue
        ln, hexb = int(m.group(1)), m.group(3).replace("-", "")
        if ln in mapping and hexb and all(c in "0123456789ABCDEF" for c in hexb):
            out[mapping[ln]] = bytes.fromhex(hexb)
    return out


def assemble(src, outdir):
    os.makedirs(outdir, exist_ok=True)
    asm, binf, lst = (os.path.join(outdir, n) for n in ("stub.asm", "stub.bin", "stub.lst"))
    open(asm, "w").write(src)
    # NASM's default optimiser is LEFT ON deliberately. UW1's harness uses -O0
    # (its analysis/reassembly.md 7) because it emits explicit `strict` sizes;
    # this emitter instead takes the size NASM picks, and -O0 measurably HURTS
    # here: 81.6% -> 75.6%. Revisit only alongside explicit size forcing.
    r = subprocess.run(["nasm", "-f", "bin", "-l", lst, "-o", binf, asm],
                       capture_output=True, text=True)
    if r.returncode:
        return None, None, r.stderr
    emitted = {}
    for line in open(lst):
        m = LST.match(line)
        if not m:
            continue
        ln, addr, hexb = int(m.group(1)), int(m.group(2), 16), m.group(3)
        hexb = hexb.replace("-", "")
        if hexb and all(c in "0123456789ABCDEF" for c in hexb):
            emitted[ln] = (addr, bytes.fromhex(hexb))
    return open(binf, "rb").read(), emitted, None


def main():
    global BITS
    outdir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "work/ratchet"
    unit = sys.argv[sys.argv.index("--unit") + 1] if "--unit" in sys.argv else "stub"
    # 1 for the stub (small, every point counts); 32 for obj1 -- at 700 KB a
    # batch of 1 would need thousands of passes, and 512 costs 0.7 points for no
    # time saving (93.1% vs 93.8%, both ~70 s).
    bbatch = int(sys.argv[sys.argv.index("--branch-batch") + 1]) \
        if "--branch-batch" in sys.argv else (32 if "obj1" in sys.argv else 1)
    if unit == "obj1":
        BITS = 32
        lo = hi = None
        if "--range" in sys.argv:
            i = sys.argv.index("--range")
            lo, hi = int(sys.argv[i + 1], 16), int(sys.argv[i + 2], 16)
        code, entry = load_obj1(lo, hi)
        print(f"obj1 slice {len(code)} B "
              f"({(lo or OBJ1_BASE):#08x}..{(hi or OBJ1_BASE + len(code)):#08x}), "
              f"{len(entry)} seeds")
    else:
        code, entry, rels = load_stub()
        print(f"stub {len(code)} B, entry {entry:#06x}, {len(rels)} relocations")
    global GUARD
    GUARD = data_guard(code)
    if unit == "obj1":
        ptab = pointer_table_guard(lo or OBJ1_BASE, (lo or OBJ1_BASE) + len(code))
        print(f"data guard: {len(GUARD)} B strings/zero runs "
              f"+ {len(ptab)} B fixup-derived pointer tables")
        GUARD |= ptab
    else:
        print(f"data guard: {len(GUARD)} B look like strings/zero runs "
              f"({100*len(GUARD)/len(code):.1f}%)")
    insns = descend(code, entry)
    covered = {o + k for o, v in insns.items() for k in range(v[0])}
    print(f"recursive descent from the entry: {len(insns)} instructions, "
          f"{len(covered)} bytes ({100*len(covered)/len(code):.1f}%)")
    from_entry = len(covered)
    round_ = 0
    orphan_max = int(sys.argv[sys.argv.index("--orphan-rounds") + 1]) \
        if "--orphan-rounds" in sys.argv else 1000
    while round_ < orphan_max:
        seeds = orphan_seeds(code, covered)
        if not seeds:
            break
        round_ += 1
        added = {}
        for s0 in seeds:
            if s0 in covered or s0 in added:
                continue
            run = descend(code, [s0])
            if not run:
                continue
            last = max(run)
            if run[last][1] not in STOP and run[last][1] != "int":
                continue                      # not a well-formed tail: reject
            for o, v in run.items():
                if o not in insns:
                    added[o] = v
        if not added:
            break
        insns.update(added)
        covered = {o + k for o, v in insns.items() for k in range(v[0])}
        if round_ <= 6 or round_ % 100 == 0:
            print(f"  orphan round {round_}: {len(seeds)} seeds, +{len(added)} "
                  f"instructions -> {len(covered)} bytes "
                  f"({100*len(covered)/len(code):.1f}%)")
    print(f"  coverage: {from_entry} B from the entry, "
          f"{len(covered) - from_entry} B from the orphan scan")

    demoted, forced, passno = set(), {}, 0
    labelset = set(insns)          # hoisted: rebuilding this per instruction is O(n^2)
    while True:
        passno += 1
        src, index = emit(code, insns, demoted, forced)
        out, emitted, err = assemble(src, outdir)
        if err:
            # An unassemblable line is just another mismatch: capstone's Intel
            # syntax is not always NASM's. Map nasm's line numbers back to
            # offsets and demote those, rather than aborting the run.
            errlines = {int(m) for m in re.findall(r"stub\.asm:(\d+):", err)}
            byline = {ln + 1: off for ln, off, _e in index}
            hit = {byline[l] for l in errlines if l in byline and byline[l] in insns}
            if not hit:
                print("nasm error with no attributable line:\n" + err[:1500])
                return 1
            print(f"pass {passno}: nasm rejected {len(errlines)} lines "
                  f"-> demoting {len(hit)}")
            demoted |= hit
            continue
        bad = []
        shown = 0
        for ln, off, expect in index:
            got = emitted.get(ln + 1)
            if got is None or got[1] != expect:
                if off in insns and off not in demoted:
                    bad.append(off)
                    if "--debug" in sys.argv and shown < 6:
                        g = got[1].hex(" ") if got else "(no listing line)"
                        print(f"    MISMATCH {off:#06x} {insns[off][1]:<6} "
                              f"expect {expect.hex(' '):<12} got {g:<12} "
                              f"| {src.splitlines()[ln].strip()}")
                        shown += 1
        real = sum(insns[o][0] for o in insns
                   if o not in demoted and to_nasm(o, *insns[o], labelset))
        exact = out == code
        print(f"pass {passno}: byte-exact={exact}  mismatched lines={len(bad)}  "
              f"real-instruction bytes={real}/{len(code)} ({100*real/len(code):.1f}%)")
        if bad:
            # Rescue pass: many "mismatches" are only NASM choosing a different
            # operand width. Try forced-width variants before demoting.
            cands, owner = [], []
            for off in bad:
                if off in forced:
                    continue
                base = to_nasm(off, *insns[off], labelset)
                if base is None:
                    continue
                for v in variants(base)[1:]:
                    cands.append(v); owner.append(off)
            if cands:
                got = probe_variants(cands, outdir)
                rescued = 0
                for i, off in enumerate(owner):
                    if off in forced:
                        continue
                    want = code[off:off + insns[off][0]]
                    if got.get(i) == want:
                        forced[off] = cands[i]; rescued += 1
                if rescued:
                    print(f"  rescued {rescued} instructions by forcing the operand width")
                    bad = [o for o in bad if o not in forced]
        if bad:
            # A single drifting instruction shifts every later label, so its
            # downstream branches all look wrong. Demoting them together is
            # METHOD.md 2.4's trap -- it throws away hundreds of correct
            # instructions to fix one. Non-branch mismatches are
            # position-independent and genuinely wrong, so demote them all;
            # branch mismatches get demoted one at a time, earliest first, and
            # the rest are re-tested once the drift ahead of them is gone.
            nonbranch = [o for o in bad
                         if not (insns[o][1] == "call" or insns[o][1].startswith("j"))]
            branch = sorted(o for o in bad if o not in nonbranch)
            bad = nonbranch + branch[:bbatch]
        if not bad:
            if not exact:
                print("  WARNING: no per-line mismatch but the image differs -- "
                      "listing parse is incomplete, not byte-exact")
                return 1
            import collections as _c
            lost = _c.Counter()
            for o in sorted(demoted):
                lost[insns[o][1]] += insns[o][0]
            uncov = sum(n for _o, n in gaps_of(code, {o + k for o, v in insns.items()
                                                      for k in range(v[0])}))
            # Count guarded BYTES, not guarded instruction starts: an
            # instruction can begin outside a string and run into it.
            in_guard = 0
            for o in insns:
                if o in demoted or not to_nasm(o, *insns[o], labelset):
                    continue
                in_guard += sum(1 for k in range(insns[o][0]) if o + k in GUARD)
            net = real - in_guard
            print(f"\nRATCHET COMPLETE: byte-exact ({passno} passes)")
            print(f"  gross: {real}/{len(code)} B emitted as instructions "
                  f"({100*real/len(code):.1f}%)")
            print(f"  NET:   {net}/{len(code)} B ({100*net/len(code):.1f}%) "
                  f"-- excluding {in_guard} B the data guard flags as "
                  f"strings/zero runs that merely re-encode")
            print(f"  demoted {sum(lost.values())} B in {len(demoted)} instructions: "
                  f"{dict(lost.most_common(8))}")
            print(f"  never reached by descent: {uncov} B (data: the WATCOM banner, "
                  f"strings, tables)")
            print(f"  source: {outdir}/stub.asm")
            return 0
        demoted |= set(bad)


if __name__ == "__main__":
    sys.exit(main())
