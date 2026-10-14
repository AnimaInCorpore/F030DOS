#!/usr/bin/env python3
"""Find the code that reads each data region, and what width it reads it at.

An element width is only useful if it came from the program. This reads the
generated listing and records every memory operand whose displacement lands
inside a data region.

Two things the operand tells us:

  * its size, which is the width the region is actually read at
  * its scale, when the form is `[reg*N + base]`, which is the stride of a
    table being indexed

Agreement between those two is what makes a tag safe. `lea` is excluded: it
forms an address without reading through it, so it says where a region is but
never how wide its elements are.

The listing rather than a fresh sweep, because only the listing knows which
bytes are code. Sweeping a function linearly from its entry looks careful and
is not: screen_mission_load carries the inline string '0.MIS' in its body, and
a sweep decodes straight through it into `add byte ptr [edi + 0x2fb14], bh` -
an invented consumer for krl_input_buffer, at a plausible address, in a real
function. The walker's recursive descent never reaches those bytes, so an
operand present in the listing was reached by control flow from a seed.

The cost is that regions used only by code the walk has not reached cannot be
resolved here. That is the honest bound, and it is reported.
"""

import argparse
import collections
import re
import sys
from pathlib import Path

import annotations

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "re/annotations.txt"
LISTING = ROOT / "re/listings/comanche-flat32.lst"
FLAT_IMAGE = ROOT / "re/unpacked/comanche-flat32.bin"

DATA_KINDS = {"table", "data"}

# `ADDRESS  bytes  mnemonic  operands`, where the bytes column is either hex
# or the walker's "N bytes" placeholder for a span it identified as data.
INSN_RE = re.compile(
    r"^([0-9A-F]{8})\s+(?:[0-9a-f]{2,}|\d+ bytes)\s+(\S+)\s*(.*?)\s*$")
MEM_RE = re.compile(r"\b(byte|word|dword|qword) ptr \[([^\]]*)\]")
SIZES = {"byte": 1, "word": 2, "dword": 4, "qword": 8}


class Access:
    __slots__ = ("site", "size", "scale", "text", "disp", "tier")

    def __init__(self, site, size, scale, text, disp, tier):
        self.site, self.size, self.scale = site, size, scale
        self.text, self.disp, self.tier = text, disp, tier

    @property
    def key(self):
        return (self.site, self.disp, self.size)


def scan(listing):
    """Every non-lea memory operand the walker actually reached."""
    out, insns = [], 0
    for line in listing.read_text(errors="replace").splitlines():
        m = INSN_RE.match(line)
        if not m:
            continue
        site, mnem, ops = int(m.group(1), 16), m.group(2), m.group(3)
        if mnem == "db":
            continue
        insns += 1
        if mnem == "lea":
            continue
        for kind, inner in MEM_RE.findall(ops):
            d = re.search(r"(-\s*)?0x([0-9a-f]+)\s*$", inner)
            if not d or d.group(1):             # no displacement, or negative
                continue
            s = re.search(r"\*\s*(\d)", inner)
            out.append(Access(site, SIZES[kind], int(s.group(1)) if s else 0,
                              f"{mnem} {ops}", int(d.group(2), 16), "listed"))
    return out, insns


# The listing's walk starts from the recorded seeds, and there are functions
# the store knows about that it never reaches - startup_resource_loads_b is
# one, and it holds the only consumer of handler_table_2231c. Re-running the
# same descent with every recorded function entry as its own seed closes that
# gap without inventing an engine: these instructions are still reached by
# control flow, just from a nearer starting point.
def descend(rows):
    import disasm

    disasm.FLAT = True
    disasm.IMAGE_ORIGIN = 0                 # flat address == offset in the carve
    disasm.INLINE_TERMINATOR = "nul"
    disasm.INLINE_STRING_ROUTINES = (0x15CDC, 0x15D40, 0x15DD0, 0x15E6E, 0x16381)
    disasm.KNOWN_DATA, disasm.KNOWN_DATA_RANGES = {}, []
    for r in regions(rows):
        disasm.KNOWN_DATA[r.addr] = r.name
        disasm.KNOWN_DATA_RANGES.append((r.addr, r.end, r.name))
    disasm.KNOWN_DATA_RANGES.sort()
    disasm.EXPECTED_DATA_HITS = set()

    d = disasm.Disassembler(FLAT_IMAGE.read_bytes())
    # `?func` rows record an approximate entry. Seeding a descent at an
    # address that is a byte or two off decodes the same invented consumers a
    # linear sweep does, so only settled entries are used.
    d.run_to_fixpoint([disasm.Addr(0, r.addr) for r in rows
                       if r.kind == "func" and not r.candidate], scan_calls=2)

    out = []
    for addr, insn in d.insns.items():
        if insn.mnemonic in ("lea", "db"):
            continue
        for kind, inner in MEM_RE.findall(insn.op_str):
            m = re.search(r"(-\s*)?0x([0-9a-f]+)\s*$", inner)
            if not m or m.group(1):
                continue
            s = re.search(r"\*\s*(\d)", inner)
            out.append(Access(addr.off, SIZES[kind], int(s.group(1)) if s else 0,
                              f"{insn.mnemonic} {insn.op_str}",
                              int(m.group(2), 16), "descent"))
    return out, len(d.insns)


# A region no load reaches by displacement is not necessarily unused. Its
# address can be taken instead - `lea`, a `mov reg, imm32`, a `push` - and the
# reads then go through the register, where no displacement names the region.
# Those sites do not give a width, but they give the caller, which is where
# the width has to be read off by hand.
def taken(listing, targets):
    lo = min(r.addr for r in targets)
    hi = max(r.end for r in targets)
    refs = collections.defaultdict(list)
    for line in listing.read_text(errors="replace").splitlines():
        m = INSN_RE.match(line)
        if not m:
            continue
        site, mnem, ops = int(m.group(1), 16), m.group(2), m.group(3)
        if mnem == "db":
            continue
        for value in re.findall(r"0x([0-9a-f]{4,8})\b", ops):
            v = int(value, 16)
            if not lo <= v < hi:
                continue
            for r in targets:
                if r.addr <= v < r.end:
                    refs[r.name].append((site, f"{mnem} {ops}", v))
                    break
    return refs


# Regions reached through a register instead of a displacement. The address is
# materialised once - `mov esi, ADDR`, `add esi, ADDR`, `lea esi, [ADDR]` - and
# every read after that names only the register, so a displacement scan sees
# nothing at all.
#
# Following the register is the whole job, and stopping at the right place is
# what makes it evidence rather than a guess. dma_len_word is the cautionary
# case: `mov esi, 000040E2` is followed twenty lines later by `movzx eax, word
# ptr [esi]`, but `mov esi, eax` sits in between, so that read belongs to a
# different record. A walk that does not watch for the register being written
# would have reported it as a consumer.
#
# Within a basic block this is exact. Across a conditional branch it follows
# the fall-through, which is an approximation - so the walk stops at anything
# unconditional, and the site is reported for reading rather than applied.
def walk(rows, targets, limit=60):
    import disasm
    from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_REG_INVALID

    d = _descender(rows)
    order = sorted(d.insns)
    stops = {"ret", "retf", "iret", "iretd", "jmp", "ljmp", "hlt", "call"}

    def region_of(v):
        for r in targets:
            if r.addr <= v < r.end:
                return r
        return None

    found = collections.defaultdict(list)
    for n, addr in enumerate(order):
        insn = d.insns[addr]
        if insn.mnemonic not in ("mov", "add", "lea"):
            continue
        ops = insn.operands
        if len(ops) != 2 or ops[0].type != 1:          # dest must be a register
            continue
        if insn.mnemonic == "lea":
            value = ops[1].mem.disp if ops[1].type == X86_OP_MEM else None
        else:
            value = ops[1].imm if ops[1].type == X86_OP_IMM else None
        if value is None:
            continue
        row = region_of(value & 0xFFFFFFFF)
        if row is None:
            continue
        reg = insn.reg_name(ops[0].reg)
        base = value & 0xFFFFFFFF

        for follow in order[n + 1:n + 1 + limit]:
            step = d.insns[follow]
            for op in step.operands:
                if op.type != X86_OP_MEM:
                    continue
                if op.mem.base == X86_REG_INVALID:
                    continue
                if step.reg_name(op.mem.base) != reg:
                    continue
                found[row.name].append(
                    (insn.address, base, step.address, op.size, op.mem.disp,
                     op.mem.scale if op.mem.index != X86_REG_INVALID else 0,
                     f"{step.mnemonic} {step.op_str}"))
            _, written = step.regs_access()
            if any(step.reg_name(w) == reg for w in written):
                break                                   # the pointer is gone
            if step.mnemonic in stops:
                break
    return found


def _descender(rows):
    import disasm

    disasm.FLAT = True
    disasm.IMAGE_ORIGIN = 0
    disasm.INLINE_TERMINATOR = "nul"
    disasm.INLINE_STRING_ROUTINES = (0x15CDC, 0x15D40, 0x15DD0, 0x15E6E, 0x16381)
    disasm.KNOWN_DATA, disasm.KNOWN_DATA_RANGES = {}, []
    for r in regions(rows):
        disasm.KNOWN_DATA[r.addr] = r.name
        disasm.KNOWN_DATA_RANGES.append((r.addr, r.end, r.name))
    disasm.KNOWN_DATA_RANGES.sort()
    disasm.EXPECTED_DATA_HITS = set()

    seeds = [disasm.Addr(0, r.addr) for r in rows
             if r.kind == "func" and not r.candidate]
    try:                                    # the resolved indirect targets too,
        for line in (ROOT / "re/seeds-flat.txt").read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:                        # so the walk covers the listing too
                seeds.append(disasm.Addr(0, int(line, 16)))
    except FileNotFoundError:
        pass

    d = disasm.Disassembler(FLAT_IMAGE.read_bytes())
    d.run_to_fixpoint(seeds, scan_calls=2)
    return d


def regions(rows):
    return [r for r in rows
            if r.kind in DATA_KINDS and r.extent not in (None, 0)]


def index(accesses, targets):
    """Attach each access to the region containing its displacement."""
    bounds = sorted((r.addr, r.end, r) for r in targets)
    hits = collections.defaultdict(list)
    for a in accesses:
        for lo, hi, row in bounds:
            if lo <= a.disp < hi:
                hits[row.name].append(a)
                break
    return hits


def verdict(row, accs):
    """What the accesses support, and how strongly."""
    sizes = collections.Counter(a.size for a in accs)
    scales = {a.scale for a in accs if a.scale}
    at_base = [a for a in accs if a.disp == row.addr]

    if not sizes:
        return None, "no read reaches it"

    # A scaled index at the base is the strongest form: it names the stride
    # and the read width at once. A scale larger than the read is not a
    # conflict - it is a record stride with narrower fields inside, which is
    # still an array of that field width for byte-order purposes.
    for a in at_base:
        if a.scale and a.scale % a.size == 0 and row.extent % a.size == 0:
            stride = "" if a.scale == a.size else f", {a.scale}-byte records"
            return a.size, f"indexed `{a.text}` at {a.site:08X}{stride}"

    if len(sizes) == 1:
        w = next(iter(sizes))
        if scales and any(s % w for s in scales):
            return None, (f"read {w}-wide but indexed by "
                          f"{sorted(scales)} - conflicting stride")
        if row.extent % w:
            return None, (f"read {w}-wide but extent {row.extent:X} "
                          f"is not a multiple")
        best = at_base[0] if at_base else accs[0]
        where = "at its base" if at_base else f"at +{best.disp - row.addr:X}"
        return w, f"`{best.text}` {where}, {best.site:08X}"

    # More than one width is not automatically a mixed region. A narrow read
    # at a displacement a wider read also covers is a sub-field peek - `cmp
    # byte ptr [x], 0` against the low byte of a dword flag - and says nothing
    # about the element width. Judge each displacement by its widest read, and
    # if those agree and tile the region, the region is that wide.
    widest = {}
    for a in accs:
        widest[a.disp] = max(widest.get(a.disp, 0), a.size)
    outer = {}
    for disp, w in widest.items():
        for off in range(disp, disp + w):
            if off not in outer or widest.get(off, 0) < w:
                outer.setdefault(off, disp)
    slots = {d: w for d, w in widest.items() if outer.get(d, d) == d}

    uniform = set(slots.values())
    if len(uniform) == 1:
        w = uniform.pop()
        aligned = all((d - row.addr) % w == 0 for d in slots)
        if aligned and row.extent % w == 0:
            peeks = len(widest) - len(slots)
            note = f", {peeks} narrower read{'' if peeks == 1 else 's'} " \
                   f"into a wider slot" if peeks else ""
            return w, (f"{len(slots)} {w}-byte slots, every one read {w} wide"
                       f"{note}")

    spread = ", ".join(f"{n}x{s}-byte" for s, n in sorted(sizes.items()))
    return None, f"read at mixed widths ({spread})"


def fieldmap(row, accs):
    """Per-displacement view of a region read at more than one width.

    A row read at several widths is usually not an array at all - it is a run
    of separate variables that happened to be recorded as one region, the way
    the object table was before it was split. The distinction that matters is
    whether a narrow read sits at a displacement a wide read also covers: `cmp
    byte ptr [x]` against the low byte of a dword flag is a sub-field peek and
    says nothing about the element width, while a byte read at a displacement
    no dword covers is a genuinely byte-wide field.
    """
    by_disp = collections.defaultdict(collections.Counter)
    for a in accs:
        by_disp[a.disp][a.size] += 1

    fields, covered = [], {}
    for disp in sorted(by_disp):
        widest = max(by_disp[disp])
        for off in range(disp, disp + widest):
            covered.setdefault(off, disp)

    for disp in sorted(by_disp):
        widest = max(by_disp[disp])
        owner = covered.get(disp)
        sub = owner is not None and owner != disp
        fields.append((disp, widest, dict(by_disp[disp]), sub))
    return fields


def split(row, accs):
    """Propose per-field rows for a region read at more than one width.

    Consecutive slots of the same width become one run; a stretch no read
    reaches becomes its own row and stays untagged, because nothing has said
    how wide it is. The first run keeps the region's name so existing evidence
    that refers to it still resolves; later runs are named for their address,
    which is the convention the dispatch slots already use.
    """
    widest = {}
    for a in accs:
        widest[a.disp] = max(widest.get(a.disp, 0), a.size)
    slots, cursor = [], row.addr
    for disp in sorted(widest):
        if disp < cursor:                    # a peek inside a slot already taken
            continue
        if disp > cursor:
            slots.append((cursor, disp - cursor, None))
        slots.append((disp, widest[disp], widest[disp]))
        cursor = disp + widest[disp]
    if cursor < row.end:
        slots.append((cursor, row.end - cursor, None))

    runs = []
    for addr, length, w in slots:
        if runs and runs[-1][2] == w and runs[-1][0] + runs[-1][1] == addr:
            runs[-1] = (runs[-1][0], runs[-1][1] + length, w)
        else:
            runs.append((addr, length, w))
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="include regions that already declare a width")
    ap.add_argument("--descend", action="store_true",
                    help="also seed the walk at every recorded function entry, "
                         "reaching consumers the committed listing misses")
    ap.add_argument("--walk", action="store_true",
                    help="follow registers loaded with a region address")
    ap.add_argument("--apply-split", metavar="NAMES",
                    help="comma-separated regions to split into per-field rows")
    ap.add_argument("--split", action="store_true",
                    help="propose per-field rows for the mixed-width regions")
    ap.add_argument("--fields", metavar="NAME",
                    help="print the per-displacement field map for one region")
    ap.add_argument("--apply", action="store_true",
                    help="write the established widths into the store")
    ap.add_argument("--sites", type=int, default=0,
                    help="list up to N access sites per region")
    args = ap.parse_args()

    rows, errors = annotations.parse(STORE)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    targets = [r for r in regions(rows) if args.all or r.width is None]
    accesses, insns = scan(LISTING)
    source = f"{insns} in {LISTING.name}"
    if args.descend:
        extra, n = descend(rows)
        seen = {a.key for a in accesses}
        added = [a for a in extra if a.key not in seen]
        accesses += added
        source += f", {n} by descent from settled entries (+{len(added)} operands)"
    hits = index(accesses, regions(rows))

    if args.walk:
        todo = [r for r in regions(rows) if r.width is None]
        got = walk(rows, todo)
        for row in sorted(todo, key=lambda r: r.addr):
            hitlist = got.get(row.name, [])
            print(f"\n{row.name}  {row.addr:08X}+{row.extent:X}"
                  f"  {len(hitlist)} read(s) through a pointer")
            seen = set()
            for setup, base, site, size, disp, scale, text in hitlist:
                field = base + disp - row.addr
                key = (field, size, text)
                if key in seen:
                    continue
                seen.add(key)
                print(f"    +{field:<5X} {size}-byte"
                      f"{f' scale {scale}' if scale else '':9}  {site:08X}  "
                      f"{text}   (pointer set {setup:08X} = {base:08X})")
        return 0

    if args.apply_split:
        text = STORE.read_text()
        for want in args.apply_split.split(","):
            row = next((r for r in regions(rows) if r.name == want), None)
            if row is None or row.width is not None:
                print(f"skipping {want}", file=sys.stderr)
                continue
            accs = hits.get(row.name, [])
            runs = split(row, accs)
            # Not text.splitlines()[row.line - 1]: each split inserts lines,
            # so a line number from the original parse points somewhere else
            # by the second region. Find the row by what identifies it.
            pat = re.compile(r"^\??(?:table|data|string)\s+%08X\s+\S+\s+%s\s+#.*$"
                             % (row.addr, re.escape(row.name)), re.M)
            found = pat.search(text)
            if not found:
                print(f"cannot locate {want}", file=sys.stderr)
                continue
            old = found.group(0)
            out = [f"# {row.name} was one row read at more than one width. Split "
                   f"by the widths its", f"# consumers use, the runs below cover "
                   f"its {row.extent:#x} bytes exactly.", f"# Was: {old.strip()}"]
            for addr, length, w in runs:
                name = row.name if addr == row.addr else f"{row.name}_{addr:05x}"
                here = [a for a in accs if addr <= a.disp < addr + length]
                if w:
                    best = max(here, key=lambda a: a.size)
                    ev = (f"{length // w} {w}-byte slot"
                          f"{'' if length // w == 1 else 's'} at +{addr - row.addr:X}, "
                          f"read by `{best.text}` at {best.site:08X}"
                          f"  elem={w}")
                    kind = "table"
                else:
                    ev = (f"{length} bytes at +{addr - row.addr:X} that no read "
                          f"reaches, so nothing has said how wide they are")
                    kind = "data "
                out.append(f"{kind}  {addr:08X}  {length:<5X} {name:24} # {ev}")
            text = text.replace(old, "\n".join(out), 1)
        STORE.write_text(text)
        print("split applied")
        return 0

    if args.split:
        for row in sorted(regions(rows), key=lambda r: r.addr):
            if row.width is not None:
                continue
            accs = hits.get(row.name, [])
            if not accs:
                continue
            runs = split(row, accs)
            known = sum(l for _, l, w in runs if w)
            print(f"\n{row.name}  {row.addr:08X}+{row.extent:X}  "
                  f"{known}/{row.extent} bytes covered by a read")
            for addr, length, w in runs:
                name = row.name if addr == row.addr else f"{row.name}_{addr:05x}"
                tag = f"elem={w}" if w else "unread, width unknown"
                print(f"  {'table' if w else 'data ':5} {addr:08X}  "
                      f"{length:<5X} {name:32} {tag}")
        return 0

    if args.fields:
        row = next((r for r in regions(rows) if r.name == args.fields), None)
        if row is None:
            print(f"no region named {args.fields}", file=sys.stderr)
            return 1
        accs = hits.get(row.name, [])
        print(f"{row.name}  {row.addr:08X}+{row.extent:X}")
        prev_end = row.addr
        for disp, widest, counts, sub in fieldmap(row, accs):
            if disp > prev_end and not sub:
                print(f"  {prev_end:08X} +{prev_end-row.addr:<4X} "
                      f"{disp-prev_end:>4} bytes  - no read reaches")
            spread = " ".join(f"{n}x{s}" for s, n in sorted(counts.items()))
            note = "  sub-field of a wider read" if sub else ""
            print(f"  {disp:08X} +{disp-row.addr:<4X} {widest:>4}-byte  "
                  f"{spread}{note}")
            if not sub:
                prev_end = max(prev_end, disp + widest)
        if prev_end < row.end:
            print(f"  {prev_end:08X} +{prev_end-row.addr:<4X} "
                  f"{row.end-prev_end:>4} bytes  - no read reaches")
        return 0

    resolved, conflicting, unreached = [], [], []
    for row in sorted(targets, key=lambda r: r.addr):
        accs = hits.get(row.name, [])
        width, why = verdict(row, accs)
        entry = (row, width, why, accs)
        if width:
            resolved.append(entry)
        elif accs:
            conflicting.append(entry)
        else:
            unreached.append(entry)

    def show(title, group):
        if not group:
            return
        print(f"\n{title} ({len(group)})")
        for row, width, why, accs in group:
            tag = f"elem={width}" if width else "-"
            n = len({a.site for a in accs})
            if accs and all(a.tier == "descent" for a in accs):
                why += "  [descent only]"
            print(f"  {row.addr:08X} {row.extent:>5X} {row.name:26} {tag:7}"
                  f" {n:>3} site{' ' if n == 1 else 's'}  {why}")
            for a in accs[:args.sites]:
                print(f"{'':14}{a.site:08X}  {a.text}   [in {a.func}]")

    if args.apply:
        text = STORE.read_text()
        for row, width, why, accs in resolved:
            line = text.splitlines()[row.line - 1]
            if "elem=" in line:
                continue
            note = why.replace("`", "")
            if any(a.tier == "descent" for a in accs) and \
                    all(a.tier == "descent" for a in accs):
                note += ", reached by descent from a settled entry rather " \
                        "than by the committed listing's walk"
            text = text.replace(line, f"{line.rstrip()}. {note}  elem={width}", 1)
        STORE.write_text(text)
        print(f"tagged {len(resolved)} rows in {STORE.name}\n")

    show("width established by a consumer", resolved)
    show("consumers found, width not settled", conflicting)
    show("no consumer reaches these", unreached)

    if unreached:
        refs = taken(LISTING, [row for row, *_ in unreached])
        print("\n  address-taken sites for those:")
        for row, *_ in unreached:
            got = refs.get(row.name, [])
            if not got:
                print(f"    {row.name:26} nothing names its address either")
            for site, text, v in got[:4]:
                at = "" if v == row.addr else f" (+{v - row.addr:X})"
                print(f"    {row.name:26} {site:08X}  {text}{at}")

    print(f"\n{len(resolved)} resolved, {len(conflicting)} ambiguous, "
          f"{len(unreached)} unreached, of {len(targets)} examined")
    print(f"from {len(accesses)} memory operands over reached instructions: "
          f"{source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
