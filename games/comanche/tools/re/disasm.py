#!/usr/bin/env python3
"""Recursive-descent disassembler for a DOS MZ load module.

Two address models, because a DOS extender uses both.

Real mode / 16-bit protected mode (the default) works in (segment, offset)
pairs.  Near branches wrap inside their 64 KB segment, so the target has to be
masked to 16 bits relative to the segment the instruction lives in -
disassembling on a flat linear address gets this wrong.

Flat 32-bit mode (--flat ORIGIN) works in a single 32-bit offset measured from
the base of the extender's 32-bit code/data selector.  ORIGIN is the image
offset that selector base maps to, so the printed addresses are exactly the
offsets the program uses internally.  For Comanche the extender installs both
its 32-bit code selector (0x20) and its 32-bit data selector (0x08) with the
same base, image offset 0x1700 - so one origin covers code and data pointers
alike.  See docs/RE-WORKFLOW.md for how that was measured.

Recursive descent deliberately does not guess: it follows only control flow it
can prove, and reports what it could not reach.  Indirect jumps (jump tables,
computed calls, the far-call dispatch vectors) leave gaps - those are listed at
the end so they can be seeded by hand via --seed.
"""
import argparse
import re
import struct
import sys
from collections import defaultdict

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_16, CS_MODE_32, CS_AC_WRITE
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG
except ImportError:
    sys.exit("capstone is required: python -m pip install capstone")

# Routines that consume inline data are binary-specific. Supply them with
# --inline-string/--inline-record when the target uses this idiom.
INLINE_STRING_ROUTINES = ()
# Terminator convention for those inline strings.  "high" is the F29 idiom this
# tool was first written against; Comanche's resource loaders use "nul".  Set it
# to match the binary, and check the emitted db line ends at the terminator and
# not a few bytes past it - an over-read silently eats the first bytes of the
# next instruction.
INLINE_TERMINATOR = "high"

# Routines that consume a FIXED-length record placed inline after the call
# site, rather than a terminator-scanned string.  0x6680 does `pop si / lodsw
# / lodsw / lodsb / lodsw` - a 2+2+1+2 = 7 byte record - before continuing.
# See docs/GAME-LOOP.md, the state-handler section.
INLINE_RECORD_ROUTINES = {}

TERMINATORS = {"ret", "retf", "iret", "iretd", "jmp", "ljmp", "hlt"}
UNCONDITIONAL = {"jmp", "ljmp"}
CONDITIONAL = {
    "ja", "jae", "jb", "jbe", "jc", "jcxz", "je", "jecxz", "jg", "jge", "jl",
    "jle", "jna", "jnae", "jnb", "jnbe", "jnc", "jne", "jng", "jnge", "jnl",
    "jnle", "jno", "jnp", "jns", "jnz", "jo", "jp", "jpe", "jpo", "js", "jz",
    "loop", "loope", "loopne", "loopnz", "loopz",
}
CALLS = {"call", "lcall"}
FAR = {"lcall", "ljmp"}
# Opcodes that essentially never appear in hand-written game code.  Used to
# reject byte-scan candidates that are really data.
JUNK_OPS = {"aaa", "aad", "aam", "aas", "daa", "das", "into", "salc", "hlt",
            "arpl", "bound", "lock", "in", "out", "iret", "sahf", "lahf"}
# The same idea for 32-bit code, minus the opcodes a DOS game legitimately
# uses.  `in`/`out` carry every VGA and PIC access, so rejecting them would
# throw away exactly the hardware routines a port needs to read; `lock` and
# `iret` belong to the extender's own interrupt plumbing.  What is left is the
# BCD/legacy group, which a 32-bit compiler never emits.
JUNK_OPS_32 = {"aaa", "aad", "aam", "aas", "daa", "das", "into", "salc",
               "arpl", "bound"}
# Registers this program genuinely uses to hold a function pointer.  See
# resolve_register_calls for why the list is this short.
FUNCTION_POINTER_REGS = set()

# Optional data guard supplied with --known-data ADDR[:LENGTH][=DESCRIPTION].
# ADDR is in the notation this tool prints - a flat address under --flat - and
# is converted to a linear image offset once, at parse time.  With a length the
# region becomes a barrier: the descent stops rather than walking into it.
KNOWN_DATA = {}
KNOWN_DATA_RANGES = []              # sorted (start_linear, end_linear, name)
EXPECTED_DATA_HITS = set()
FAR_IMM = re.compile(r"^\s*(0x[0-9a-f]+)\s*:\s*(0x[0-9a-f]+)\s*$", re.I)

# Flat 32-bit model, selected by --flat ORIGIN.  IMAGE_ORIGIN is the image
# offset that flat address 0 maps to; the segment half of every Addr is then
# unused and printed addresses match the program's own 32-bit offsets.
FLAT = False
IMAGE_ORIGIN = 0


def _known_data_at(linear):
    """The known-data region containing this linear offset, or None."""
    if not KNOWN_DATA_RANGES:
        return None
    lo, hi = 0, len(KNOWN_DATA_RANGES)
    while lo < hi:                      # rightmost start <= linear
        mid = (lo + hi) // 2
        if KNOWN_DATA_RANGES[mid][0] <= linear:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return None
    start, end, name = KNOWN_DATA_RANGES[lo - 1]
    return name if start <= linear < end else None


class Addr(tuple):
    """(segment, offset), ordered and hashable, with a linear view.

    In flat mode the segment is always 0 and the offset is a full 32-bit
    value, so the same type serves both address models and nothing downstream
    has to know which one is in use.
    """
    __slots__ = ()

    def __new__(cls, seg, off):
        if FLAT:
            return super().__new__(cls, (0, off & 0xFFFFFFFF))
        return super().__new__(cls, (seg & 0xFFFF, off & 0xFFFF))

    @property
    def seg(self):
        return self[0]

    @property
    def off(self):
        return self[1]

    @property
    def linear(self):
        if FLAT:
            return IMAGE_ORIGIN + self[1]
        return (self[0] << 4) + self[1]

    def __str__(self):
        if FLAT:
            return f"{self[1]:08X}"
        return f"{self[0]:04X}:{self[1]:04X}"


def segment_for_linear(linear: int) -> int:
    """Choose a canonical 64-KiB real-mode window for a flat image offset."""
    return (linear >> 16) << 12


def addr_for_linear(linear: int) -> Addr:
    """The Addr naming an image offset under the active address model."""
    if FLAT:
        return Addr(0, linear - IMAGE_ORIGIN)
    seg = segment_for_linear(linear)
    return Addr(seg, linear - (seg << 4))


class Disassembler:
    def __init__(self, image: bytes):
        self.image = image
        self.md = Cs(CS_ARCH_X86, CS_MODE_32 if FLAT else CS_MODE_16)
        self.md.detail = True
        # `call rel16` in a 16-bit segment, `call rel32` in a 32-bit one.
        self.call_len = 5 if FLAT else 3
        self.junk_ops = JUNK_OPS_32 if FLAT else JUNK_OPS
        self.insns = {}                     # Addr -> capstone insn
        self.xrefs = defaultdict(set)       # Addr -> {Addr, ...}
        self.call_targets = set()
        self.indirect = []                  # (Addr, mnemonic, op_str)
        self.interrupts = defaultdict(set)
        self.far_refs = set()               # far pointers seen as immediates
        self.zero_landings = set()
        self.data_landings = set()          # branch targets that land in zero fill
        self.strings = {}                   # start Addr -> end Addr of inline strings/records
        self.inline_string_routines = {Addr(0, o) for o in INLINE_STRING_ROUTINES}
        self.inline_record_routines = {Addr(0, o): n for o, n in INLINE_RECORD_ROUTINES.items()}

    def _read(self, addr: Addr, n: int = 16) -> bytes:
        return self.image[addr.linear:addr.linear + n]

    # A run of zero bytes decodes happily as `add [eax], al` forever, so a
    # branch that lands in BSS or in table padding produces a long stretch of
    # plausible-looking listing and counts as coverage.  Real code does not
    # contain this many zeros at an instruction boundary.
    ZERO_SLED = 8

    def _is_zero_fill(self, addr: Addr) -> bool:
        window = self._read(addr, self.ZERO_SLED)
        return len(window) == self.ZERO_SLED and not any(window)

    def run(self, seeds: list[Addr]) -> None:
        worklist = list(seeds)
        while worklist:
            addr = worklist.pop()
            regs = {}                       # reg -> immediate, for `mov r,imm / jmp r`
            while True:
                if addr in self.insns or not (0 <= addr.linear < len(self.image)):
                    break
                if self._is_zero_fill(addr):
                    self.zero_landings.add(addr)
                    break
                region = _known_data_at(addr.linear)
                if region is not None:
                    # A walk that reaches an established table has gone wrong
                    # upstream - a bad seed, or a function whose end the
                    # descent could not see. Stopping here keeps the table out
                    # of the coverage figure and records where it happened, so
                    # the cause can be found instead of being averaged away.
                    self.data_landings.add((addr, region))
                    break
                decoded = next(self.md.disasm(self._read(addr), addr.off, 1), None)
                if decoded is None:
                    break
                self.insns[addr] = decoded
                mnem = decoded.mnemonic

                if mnem == "int":
                    try:
                        self.interrupts[int(decoded.op_str, 0)].add(addr)
                    except ValueError:
                        pass

                target = self._target(addr, decoded, regs)
                if mnem in CALLS or mnem in CONDITIONAL or mnem in UNCONDITIONAL:
                    if target is None:
                        self.indirect.append((addr, mnem, decoded.op_str))
                    else:
                        self.xrefs[target].add(addr)
                        if mnem in CALLS:
                            self.call_targets.add(target)
                        if mnem in FAR:
                            self.far_refs.add(target)
                        if target not in self.insns and 0 <= target.linear < len(self.image):
                            worklist.append(target)

                if mnem in TERMINATORS:
                    break
                if mnem == "int" and decoded.op_str.strip() == "0x20":
                    break

                self._track_regs(decoded, regs)
                nxt = Addr(addr.seg, addr.off + decoded.size)

                # Inline-string idiom: the callee pops the return address as a
                # string pointer and resumes past the terminator, so execution
                # continues after the string, not after the call.
                if mnem == "call" and target in self.inline_string_routines:
                    end = self._skip_string(nxt)
                    if end is not None:
                        self.strings[nxt] = end
                        nxt = end
                    else:
                        break
                # Same idiom, but the callee consumes a fixed-length record
                # instead of scanning for a terminator.
                elif mnem == "call" and target in self.inline_record_routines:
                    end = Addr(nxt.seg, nxt.off + self.inline_record_routines[target])
                    self.strings[nxt] = end
                    nxt = end
                addr = nxt

    def reset(self) -> None:
        """Clear analysis state but keep the learned inline-string routines."""
        self.insns.clear()
        self.xrefs.clear()
        self.call_targets.clear()
        self.indirect.clear()
        self.interrupts.clear()
        self.far_refs.clear()
        self.zero_landings.clear()
        self.data_landings.clear()
        self.strings.clear()

    def run_to_fixpoint(self, seeds: list[Addr], max_passes: int = 8,
                        scan_calls: int = 0, detect_inline: bool = True) -> int:
        """Alternate descent and inline-string detection until nothing new.

        An unrecognised inline-string routine derails the sweep into the string
        bytes, so each newly detected one typically unlocks further code, which
        may in turn reveal more such routines.

        With scan_calls set, byte-scanned call targets are added to the seed
        set as well; the value is the minimum number of call sites a target
        needs before it is trusted.
        """
        seeds = list(seeds)
        if scan_calls:
            seeds.extend(self.scan_call_targets(min_sites=scan_calls))
        passes = 0
        while passes < max_passes:
            passes += 1
            self.reset()
            self.run(seeds)
            found = self._detect_inline_string_routines() if detect_inline else set()
            new = found - self.inline_string_routines
            extra = (self.resolve_register_calls()
                     | self.resolve_pointer_calls()
                     | self.resolve_stored_pointers()) - set(seeds)
            if not new and not extra:
                break
            self.inline_string_routines |= new
            seeds.extend(extra)
        return passes

    def _scan_direct_calls(self):
        """Every `call rel` encoding in the raw bytes, as (pos, target, after).

        Both byte scans below need the same thing and the encoding differs by
        address model, so the width lives here rather than in two places.
        Candidates are not filtered - the callers decide what to trust.
        """
        width = self.call_len - 1
        fmt = "<i" if FLAT else "<h"
        for pos in range(len(self.image) - width):
            if self.image[pos] != 0xE8:
                continue
            rel = struct.unpack_from(fmt, self.image, pos + 1)[0]
            after = addr_for_linear(pos + self.call_len)
            yield pos, Addr(after.seg, after.off + rel), after

    def _detect_inline_string_routines(self) -> set:
        """Call targets whose call sites are consistently followed by text.

        A routine taking an inline string is called from many places, and at
        every one of them the following bytes are a high-bit-terminated string.
        That pattern does not occur by chance across several call sites.

        The scan is over raw bytes, not over discovered call sites: a routine
        we have not reached yet is exactly the one worth detecting, and relying
        on the descent to find it first would be circular.
        """
        sites_by_target = defaultdict(list)
        for pos, target, after in self._scan_direct_calls():
            sites_by_target[target].append(after)

        found = set()
        for target, sites in sites_by_target.items():
            if len(sites) < 3:
                continue
            good = sum(1 for s in sites if self._looks_like_string(s))
            if good >= max(3, int(len(sites) * 0.8)):
                found.add(target)
        return found

    def scan_call_targets(self, min_sites: int = 1, probe: int = 10) -> set:
        """Byte-scan the image for `call rel16` targets that look like code.

        Recursive descent only finds a routine once something reaches it, so a
        function whose only callers sit in unreached code stays invisible even
        though its call sites are plainly there in the bytes.  Scanning for the
        call encoding directly breaks that circle.

        Every candidate is probed before being accepted: disassembling from it
        has to yield `probe` instructions with no decode failure and no opcode
        that real program text does not contain.  Raising min_sites to 2 asks
        for corroboration from a second call site, which trades reach for
        certainty.
        """
        sites = defaultdict(int)
        for _pos, target, _after in self._scan_direct_calls():
            sites[target] += 1

        accepted = set()
        for target, count in sites.items():
            if count < min_sites or not 0 <= target.linear < len(self.image):
                continue
            if self._probe_code(target, probe):
                accepted.add(target)
        return accepted

    def resolve_register_calls(self) -> set:
        """Targets for `call reg` / `jmp reg`, from immediates loaded into reg.

        Eleven `call bp` sites survive the descent because the register is
        loaded in a different basic block than the call, so the intra-run
        constant propagation never sees it.  The inference that works is the
        other way round: if the program loads a constant into bp anywhere and
        elsewhere does `call bp`, that constant is a function entry.

        Only bp qualifies, and the restriction is not cosmetic - it was
        measured.  Admitting bx as well takes coverage from 41.8 % to 48.5 %
        but drags in five regions that are provably data, including both
        archive indices; adding di brings in the EGA palette and the segment
        table too.  The reason is that those registers hold data pointers in
        most contexts, so `mov si, 0xFC00` (the palette) would be seeded as
        code merely because `jmp si` occurs elsewhere - and that `jmp si` is
        the inline-string return, not a function pointer at all.
        """
        indirect_regs = {ops.strip() for _, mnem, ops in self.indirect
                         if ops.strip() in FUNCTION_POINTER_REGS}
        if not indirect_regs:
            return set()

        found = set()
        for addr, insn in self.insns.items():
            if insn.mnemonic != "mov" or len(insn.operands) != 2:
                continue
            dst, src = insn.operands
            if dst.type != X86_OP_REG or src.type != X86_OP_IMM:
                continue
            if insn.reg_name(dst.reg) not in indirect_regs:
                continue
            target = Addr(addr.seg, src.imm)
            if 0 <= target.linear < len(self.image) and self._probe_code(target, 10):
                found.add(target)
        return found

    def resolve_stored_pointers(self) -> set:
        """Code addresses the program writes somewhere, as seeds.

            mov dword ptr [ecx*4 + 00020244], 000237B0
            push 0000DA05

        A handler installed into a table, or a return address pushed before a
        computed jump, is a code entry as surely as a call target - and neither
        resolver above can see it, because nothing ever calls it directly. The
        object state handlers are the case that matters: 0x237B0 spans 0x10F0
        bytes of individual state routines, every one installed through field 1
        and none of them reachable by a scan for `call rel32`.

        The filter is deliberately narrow, because an immediate that happens to
        land in the code region is not evidence of anything on its own:

          - the destination is memory, or the instruction is a push, so an
            arithmetic constant that resembles an address is not admitted
          - the target is not inside a region the store already calls data
          - the target decodes, and a short probe from it stays decodable

        The last of those is the same _probe_code the call scanner uses, and it
        is what keeps a run of table bytes that happens to point at itself from
        seeding a walk through data.
        """
        from capstone.x86 import X86_OP_IMM, X86_OP_MEM

        out = set()
        for addr, insn in self.insns.items():
            ops = insn.operands
            if insn.mnemonic == "push":
                if len(ops) != 1 or ops[0].type != X86_OP_IMM:
                    continue
                value = ops[0].imm
            elif insn.mnemonic == "mov":
                if len(ops) != 2 or ops[0].type != X86_OP_MEM:
                    continue
                if ops[1].type != X86_OP_IMM:
                    continue
                value = ops[1].imm
            else:
                continue

            value &= 0xFFFFFFFF
            target = addr_for_linear(IMAGE_ORIGIN + value) if FLAT else None
            if target is None or target in self.insns:
                continue
            if not (0 <= target.linear < len(self.image)):
                continue
            if _known_data_at(target.linear) is not None:
                continue
            if self._is_zero_fill(target):
                continue
            if not self._probe_code(target, 8):
                continue
            out.add(target)
        return out

    def resolve_pointer_calls(self) -> set:
        """Targets for calls that go through a pointer held in memory.

        Two shapes, and both are ordinary in this program:

            call dword ptr [0002A980]
            mov ebx, dword ptr [0002A980] / call ebx

        The pointer itself is a constant in the image, so the target is
        statically knowable - but a scan for direct `call rel` encodings cannot
        see the edge at all, and the register resolver above only follows
        immediates. That blind spot hid the whole resource palette remap at
        0002B949, reached by exactly the second shape at 00006501, through a
        DAC capture and two emulator sessions before it was found by reading.

        The guard against seeding data is the same one the immediate resolver
        uses, plus one more that matters here: a slot still holding zero is a
        vector filled at runtime, not a pointer, and there are many of those.
        """
        # Any register the program actually calls through qualifies here, not
        # just the ones FUNCTION_POINTER_REGS admits for immediates. The
        # evidence is different in kind: `mov si,0xFC00` is a data pointer that
        # only looks like a function pointer because `jmp si` occurs elsewhere,
        # whereas a slot in memory that holds a code address and is loaded into
        # a register that gets called is a function pointer by construction.
        wanted_regs = {ops.strip() for _, mnem, ops in self.indirect
                       if ops.strip().isalpha()}

        slots = set()
        for addr, insn in self.insns.items():
            ops = insn.operands
            if insn.mnemonic in CALLS or insn.mnemonic in UNCONDITIONAL:
                # call/jmp through a memory operand with no base or index:
                # the displacement is the pointer's own address.
                if len(ops) == 1 and ops[0].type == X86_OP_MEM:
                    mem = ops[0].mem
                    if mem.base == 0 and mem.index == 0:
                        slots.add(Addr(addr.seg, mem.disp))
            elif insn.mnemonic == "mov" and len(ops) == 2:
                dst, src = ops
                if (dst.type == X86_OP_REG and src.type == X86_OP_MEM
                        and insn.reg_name(dst.reg) in wanted_regs
                        and src.mem.base == 0 and src.mem.index == 0):
                    slots.add(Addr(addr.seg, src.mem.disp))

        width = 4 if FLAT else 2
        found = set()
        for slot in slots:
            if not (0 <= slot.linear <= len(self.image) - width):
                continue
            value = int.from_bytes(
                self.image[slot.linear:slot.linear + width], "little")
            if value == 0:
                continue                    # a vector filled at runtime
            target = Addr(slot.seg, value)
            if not (0 <= target.linear < len(self.image)):
                continue
            if self._probe_code(target, 10):
                found.add(target)
        return found

    def _probe_code(self, addr: Addr, want: int) -> bool:
        """True if `want` instructions decode cleanly from addr."""
        if self._is_zero_fill(addr):
            return False
        window = self.image[addr.linear:addr.linear + want * 8]
        decoded = list(self.md.disasm(window, addr.off, want))
        if len(decoded) < want:
            return False
        return not any(i.mnemonic in self.junk_ops for i in decoded)

    def _looks_like_string(self, start: Addr, minlen: int = 3, maxlen: int = 200) -> bool:
        pos, n = start.linear, 0
        while pos < len(self.image) and n < maxlen:
            b = self.image[pos]
            if INLINE_TERMINATOR == "nul":
                if b == 0:
                    return n >= minlen
                if not (32 <= b < 127 or b in (9, 10, 13)):
                    return False
                n += 1
                pos += 1
                continue
            c = b & 0x7F
            if not (32 <= c < 127 or c in (9, 10, 13)):
                return False
            n += 1
            if b & 0x80:
                return n >= minlen
            pos += 1
        return False

    def _skip_string(self, start: Addr) -> Addr | None:
        """End of an inline string, or None if unterminated.

        The terminator convention is per-binary and getting it wrong is not a
        cosmetic error.  Comanche's resource loaders take NUL-terminated names,
        but scanning for the F29-style high-bit terminator runs past the NUL and
        stops on the first byte of the following instruction that happens to
        have bit 7 set - typically the 0x82 of a `jb rel32`.  Decoding then
        resumes two bytes into a real instruction and produces a plausible
        stream of nonsense, which is how a misdecoded filename came to be
        reported as `jmp dword ptr [ebx + 0x19e98]`.
        """
        pos = start.linear
        limit = min(pos + 512, len(self.image))
        while pos < limit:
            done = self.image[pos] == 0 if INLINE_TERMINATOR == "nul" \
                else self.image[pos] & 0x80
            if done:
                return Addr(start.seg, start.off + (pos - start.linear) + 1)
            pos += 1
        return None

    @staticmethod
    def _track_regs(insn, regs: dict) -> None:
        """Track `mov reg, imm`; forget a register on any other write to it."""
        ops = insn.operands
        if insn.mnemonic == "mov" and len(ops) == 2 and ops[1].type == X86_OP_IMM:
            if ops[0].type == X86_OP_REG:
                regs[insn.reg_name(ops[0].reg)] = ops[1].imm & 0xFFFF
                return
        for op in ops:
            if op.type == X86_OP_REG and op.access & CS_AC_WRITE:
                regs.pop(insn.reg_name(op.reg), None)

    def _target(self, addr: Addr, insn, regs: dict | None = None) -> Addr | None:
        """Resolve a direct branch target, or None when indirect."""
        if insn.mnemonic in FAR:
            m = FAR_IMM.match(insn.op_str)
            if m:
                return Addr(int(m.group(1), 16), int(m.group(2), 16))
            return None                     # lcall [mem] etc.
        if not insn.operands:
            return None
        # `mov ax,imm / jmp ax` - constant propagation resolves these.
        if regs and insn.operands[0].type == X86_OP_REG:
            if insn.mnemonic in CALLS | CONDITIONAL | UNCONDITIONAL:
                name = insn.reg_name(insn.operands[0].reg)
                if name in regs:
                    return Addr(addr.seg, regs[name])
            return None
        if insn.operands[0].type != X86_OP_IMM:
            return None
        # Near branch: capstone computed off + rel without wrapping.  Addr
        # masks it back into the segment the instruction lives in (16-bit) or
        # keeps the full 32-bit offset (flat).
        return Addr(addr.seg, insn.operands[0].imm)

    def zero_runs(self, minimum: int = 4096):
        """Zero-filled runs of at least `minimum` bytes, as (start, length).

        A linker emits the BSS as part of the MZ load module, so a large share
        of the file can be address space that was never written to disk in any
        meaningful sense.  Counting it in a coverage denominator makes every
        percentage look like a failure and hides real progress.
        """
        runs, pos, n = [], 0, len(self.image)
        while pos < n:
            if self.image[pos]:
                pos += 1
                continue
            end = pos
            while end < n and not self.image[end]:
                end += 1
            if end - pos >= minimum:
                runs.append((pos, end - pos))
            pos = end
        return runs

    def content_end(self) -> int:
        """Image size with a trailing BSS-shaped zero run removed.

        Only the last such run is trimmed, and only when it actually runs to
        the end: interior zero blocks are ordinary uninitialised tables and
        stay in the denominator.
        """
        for start, length in reversed(self.zero_runs()):
            if start + length >= len(self.image) - 16:
                return start
        return len(self.image)

    def coverage(self):
        """Bytes accounted for, and the runs we never reached.

        Inline strings count as accounted for - they are identified data, not
        an unexplored gap.
        """
        spans = [(a.linear, a.linear + i.size) for a, i in self.insns.items()]
        spans += [(a.linear, e.linear) for a, e in self.strings.items()]
        spans.sort()
        covered, gaps, prev_end = 0, [], 0
        for lo, hi in spans:
            if lo > prev_end:
                gaps.append((prev_end, lo - prev_end))
            covered += max(0, hi - max(lo, prev_end))
            prev_end = max(prev_end, hi)
        if prev_end < len(self.image):
            gaps.append((prev_end, len(self.image) - prev_end))
        return covered, gaps

    def listing(self, out) -> None:
        labels = {}
        for target in sorted(self.xrefs):
            prefix = "sub" if target in self.call_targets else "loc"
            if FLAT:
                labels[target] = f"{prefix}_{target.off:08X}"
            else:
                labels[target] = f"{prefix}_{target.seg:04X}_{target.off:04X}"

        prev_end = None
        for addr in sorted(self.insns):
            insn = self.insns[addr]
            lin = addr.linear
            if prev_end is not None and lin != prev_end:
                out.write(f"\n; ---- {lin - prev_end} bytes not reached ----\n\n")
            if addr in labels:
                refs = " ".join(str(r) for r in sorted(self.xrefs[addr])[:6])
                more = "" if len(self.xrefs[addr]) <= 6 else f" (+{len(self.xrefs[addr]) - 6})"
                out.write(f"\n{labels[addr]}:\t\t\t; xrefs: {refs}{more}\n")
            target = self._target(addr, insn)
            comment = f"\t; -> {labels[target]}" if target in labels else ""
            out.write(
                f"{addr}  {insn.bytes.hex():<16}  {insn.mnemonic:<7} {insn.op_str}{comment}\n"
            )
            prev_end = lin + insn.size

            nxt = Addr(addr.seg, addr.off + insn.size)
            if nxt in self.strings:
                end = self.strings[nxt]
                raw = self.image[nxt.linear:end.linear]
                text = "".join(chr(b & 0x7F) if 32 <= (b & 0x7F) < 127 else f"\\x{b:02x}"
                               for b in raw)
                out.write(f"{nxt}  {len(raw):>3} bytes         db      '{text}'\n")
                prev_end = end.linear


def parse_addr(text: str) -> Addr:
    if ":" in text:
        seg, off = text.split(":", 1)
        if FLAT:
            # A selector is not a paragraph and its base is whatever the
            # extender put in the GDT, so SEG:OFF cannot be reinterpreted as a
            # flat offset without knowing which selector was meant.
            raise SystemExit(
                f"--flat takes plain 32-bit offsets, not selector form: {text}\n"
                "Pass the offset within the selector's segment, e.g. 1538.")
        return Addr(int(seg, 16), int(off, 16))
    return Addr(0, int(text, 16))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", help="DOS MZ executable")
    ap.add_argument("-o", "--out", default="re/listings/comanche.lst")
    ap.add_argument("--seed", action="append", default=[],
                    help="extra entry point as SEG:OFF hex, or a plain 32-bit "
                         "offset under --flat (repeatable)")
    ap.add_argument("--seeds", default=None,
                    help="file of resolved indirect targets, one address per "
                         "line (default: re/seeds.txt, or re/seeds-flat.txt "
                         "under --flat)")
    ap.add_argument("--flat", metavar="ORIGIN", default=None,
                    help="disassemble as 32-bit flat code whose selector base "
                         "is at image offset ORIGIN (hex). For Comanche the "
                         "extender's 32-bit code and data selectors both sit "
                         "at 1700")
    ap.add_argument("--content-end", metavar="OFFSET", default=None,
                    help="hex image offset where real content stops, "
                         "excluding the linker's zero-filled BSS from the "
                         "coverage denominator (default: detected)")
    ap.add_argument("--callgraph", type=int, nargs="?", const=20, default=0,
                    metavar="N",
                    help="print the N routines that call the most others, with "
                         "their callers and callees. Finding the game loop by "
                         "hunting for tables does not work; the call graph "
                         "shows it structurally")
    ap.add_argument("--scan-calls", type=int, nargs="?", const=1, default=2,
                    metavar="MIN_SITES",
                    help="also seed byte-scanned call targets; the value is how "
                         "many call sites a target needs before it is trusted. "
                         "The default of 2 is the highest setting that leaves "
                         "every known data region alone; 1 reaches 66%% but "
                         "disassembles data regions as code")
    ap.add_argument("--no-inline-detect", action="store_true",
                    help="do not guess inline-string routines. The idiom is "
                         "binary-specific; in a binary that does not use it "
                         "the detector only produces false positives that can "
                         "make the sweep skip real code as if it were text")
    ap.add_argument("--inline-string", action="append", default=[], metavar="OFFSET",
                    help="hex routine offset that consumes an inline string")
    ap.add_argument("--inline-terminator", choices=["high", "nul"], default="high",
                    help="how those inline strings end: a high-bit-set final byte "
                         "(the F29 idiom, default) or a NUL (Comanche)")
    ap.add_argument("--inline-record", action="append", default=[], metavar="OFFSET:LENGTH",
                    help="hex routine offset and fixed inline record length")
    ap.add_argument("--function-pointer-reg", action="append", default=[], metavar="REG",
                    help="register used for indirect calls, repeatable")
    ap.add_argument("--known-data", action="append", default=[], metavar="OFFSET[=DESCRIPTION]",
                    help="data address to guard against false code reachability")
    args = ap.parse_args()

    global INLINE_STRING_ROUTINES, INLINE_RECORD_ROUTINES
    global FUNCTION_POINTER_REGS, KNOWN_DATA, KNOWN_DATA_RANGES, EXPECTED_DATA_HITS
    global FLAT, IMAGE_ORIGIN, INLINE_TERMINATOR
    # Set before the first Addr is built: it decides the address model.
    if args.flat is not None:
        FLAT = True
        IMAGE_ORIGIN = int(args.flat, 16)
    if args.seeds is None:
        args.seeds = "re/seeds-flat.txt" if FLAT else "re/seeds.txt"
    INLINE_STRING_ROUTINES = tuple(int(value, 16) for value in args.inline_string)
    INLINE_TERMINATOR = args.inline_terminator
    INLINE_RECORD_ROUTINES = {}
    for value in args.inline_record:
        offset, length = value.split(":", 1)
        INLINE_RECORD_ROUTINES[int(offset, 16)] = int(length, 0)
    FUNCTION_POINTER_REGS = set(args.function_pointer_reg)
    KNOWN_DATA = {}
    KNOWN_DATA_RANGES = []
    for value in args.known_data:
        location, separator, description = value.partition("=")
        description = description if separator else "known data"
        address, _, length = location.partition(":")
        start = Addr(0, int(address, 16)).linear
        extent = int(length, 16) if length else 1
        KNOWN_DATA[start] = description
        KNOWN_DATA_RANGES.append((start, start + extent, description))
    KNOWN_DATA_RANGES.sort()
    EXPECTED_DATA_HITS = set()

    file_seeds = []
    try:
        for line in open(args.seeds, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if line:
                file_seeds.append(parse_addr(line))
    except FileNotFoundError:
        pass

    data = open(args.exe, "rb").read()
    lastpage, pages = struct.unpack_from("<HH", data, 2)
    hdrsize = struct.unpack_from("<H", data, 8)[0] * 16
    imagesize = (pages - 1) * 512 + lastpage if lastpage else pages * 512
    image = data[hdrsize:imagesize]
    ip, cs = struct.unpack_from("<HH", data, 20)

    # The MZ entry is a real-mode CS:IP. It says nothing about where the
    # 32-bit code starts, so under --flat the seeds have to be supplied.
    seeds = [] if FLAT else [Addr(cs, ip)]
    seeds += [parse_addr(s) for s in args.seed] + file_seeds
    if not seeds:
        sys.exit(f"--flat needs at least one --seed, or entries in {args.seeds}")
    d = Disassembler(image)
    passes = d.run_to_fixpoint(seeds, scan_calls=args.scan_calls,
                               detect_inline=not args.no_inline_detect)

    covered, gaps = d.coverage()
    total = len(image)
    if args.content_end is not None:
        content = int(args.content_end, 16)
    else:
        content = d.content_end()
    content -= IMAGE_ORIGIN
    strbytes = sum(e.linear - a.linear for a, e in d.strings.items())
    model = f"flat 32-bit, origin {IMAGE_ORIGIN:#07x}" if FLAT else "16-bit seg:off"
    print(f"load module {total} bytes, {model}, entry {seeds[0]}, {passes} passes")
    if content != total:
        print(f"content region {content} bytes "
              f"({total - content - IMAGE_ORIGIN} bytes of trailing zero fill excluded)")
    print(f"reached {len(d.insns)} instructions, {covered} bytes ({covered * 100 / content:.1f}% coverage)")
    print(f"call targets: {len(d.call_targets)}   branch targets: {len(d.xrefs)}")
    print(f"inline strings: {len(d.strings)} totalling {strbytes} bytes, "
          f"from {len(d.inline_string_routines)} routines")
    print("  " + " ".join(str(r) for r in sorted(d.inline_string_routines)))
    print()

    reached = set()
    for a, insn in d.insns.items():
        reached.update(range(a.linear, a.linear + insn.size))
    violations = [(off, name) for off, name in KNOWN_DATA.items()
                  if off in reached and off not in EXPECTED_DATA_HITS]
    if violations:
        print(f"WARNING: {len(violations)} known data regions were disassembled "
              f"as code - the extra coverage is not real")
        for off, name in sorted(violations):
            print(f"  {off:#06x}  {name}")
    elif KNOWN_DATA:
        print(f"data check: all {len(KNOWN_DATA) - len(EXPECTED_DATA_HITS)} "
              f"known data regions left alone")

    # Where the descent tried to enter a table and was stopped. Each of these
    # is a real defect upstream - a seed that is not code, or a function whose
    # end could not be seen - so they are listed rather than counted.
    if d.data_landings:
        by_region = {}
        for addr, name in d.data_landings:
            by_region.setdefault(name, []).append(addr)
        print(f"barrier: {len(d.data_landings)} walks stopped at "
              f"{len(by_region)} known data regions")
        for name in sorted(by_region)[:15]:
            where = " ".join(str(a) for a in sorted(by_region[name])[:4])
            print(f"  {name:24} entered at {where}")
        if len(by_region) > 15:
            print(f"  ...and {len(by_region) - 15} more")
    print()

    if d.interrupts:
        print("DOS/BIOS interrupts used")
        for num in sorted(d.interrupts):
            sites = sorted(d.interrupts[num])
            shown = " ".join(str(s) for s in sites[:8])
            more = "" if len(sites) <= 8 else f" (+{len(sites) - 8} more)"
            print(f"  int {num:#04x}  {len(sites):3d} sites: {shown}{more}")
        print()

    if d.zero_landings:
        # Not noise to suppress: something branched here, so either the
        # target is patched at runtime or the branch was decoded from data.
        shown = " ".join(str(a) for a in sorted(d.zero_landings)[:10])
        more = "" if len(d.zero_landings) <= 10 else f" (+{len(d.zero_landings) - 10})"
        print(f"branches into zero fill: {len(d.zero_landings)} targets, "
              f"descent stopped at each")
        print(f"  {shown}{more}")
        print()

    if d.indirect:
        counts = defaultdict(list)
        for addr, mnem, ops in d.indirect:
            counts[f"{mnem} {ops}"].append(addr)
        print(f"indirect control flow: {len(d.indirect)} sites, {len(counts)} distinct forms")
        for form, sites in sorted(counts.items(), key=lambda kv: -len(kv[1]))[:15]:
            shown = " ".join(str(s) for s in sites[:5])
            more = "" if len(sites) <= 5 else f" (+{len(sites) - 5})"
            print(f"  {len(sites):4d}x  {form:<28} at {shown}{more}")
        print()

    if args.callgraph:
        # Attribute every call to the routine it sits in.
        #
        # "The nearest call target at or below the site" is not good enough: the
        # last routine before a large unreached region then collects every call
        # site in that region, and the result is a confident-looking top entry
        # that is pure artefact. So an owner only extends over *contiguously
        # reached* instructions - a gap ends it, and sites past the gap belong
        # to nobody.
        owner_of = {}
        current = None
        prev_end = None
        for addr in sorted(d.insns, key=lambda a: a.linear):
            if prev_end is not None and addr.linear != prev_end:
                current = None                  # a gap: the routine ended
            if addr in d.call_targets:
                current = addr
            if current is not None:
                owner_of[addr] = current
            prev_end = addr.linear + d.insns[addr].size

        callees = defaultdict(set)
        for target in sorted(d.xrefs):
            if target not in d.call_targets:
                continue
            for site in d.xrefs[target]:
                insn = d.insns.get(site)
                if insn is None or insn.mnemonic not in CALLS:
                    continue
                owner = owner_of.get(site)
                if owner is not None and owner != target:
                    callees[owner].add(target)

        ranked = sorted(callees.items(), key=lambda kv: -len(kv[1]))
        print(f"call graph: {len(d.call_targets)} routines, "
              f"{sum(len(v) for v in callees.values())} edges")
        print(f"the {args.callgraph} routines that call the most others")
        print()
        for owner, targets in ranked[:args.callgraph]:
            callers = [c for c in d.xrefs.get(owner, ())
                       if d.insns.get(c) is not None
                       and d.insns[c].mnemonic in CALLS]
            print(f"  {owner}  calls {len(targets):2d}, called from {len(callers)}")
            shown = " ".join(str(t) for t in sorted(targets)[:10])
            print(f"      -> {shown}{' ...' if len(targets) > 10 else ''}")
        print()

    def filler_run_bytes(block: bytes, value: int = 0x80, minimum: int = 16) -> int:
        """Bytes belonging to long runs of this program's padding byte.

        Zero is not the only filler here: the linker pads with 0x80, and one
        10,496-byte region is 96.7% of it.  Counted as material, that region
        ranked third in the work list while holding about a kilobyte of code.
        Only runs are discounted, so a genuine 0x80 inside real data still
        counts.
        """
        total, i, n = 0, 0, len(block)
        while i < n:
            if block[i] != value:
                i += 1
                continue
            j = i
            while j < n and block[j] == value:
                j += 1
            if j - i >= minimum:
                total += j - i
            i = j
        return total

    # Rank by non-zero material, not by size.  A third of this image is zero,
    # and the largest gap by size is 77% zero fill - it held 6,103 bytes of
    # material while ranking first, and sent three separate sessions to the
    # wrong region.  Size is still printed, because a gap that is mostly zero is
    # itself worth knowing about.
    ranked = []
    for start, size in gaps:
        block = d.image[start:start + size]
        material = size - block.count(0) - filler_run_bytes(block)
        if material <= 0:
            continue
        printable = sum(1 for b in block if 32 <= b < 127)
        pointers = sum(1 for k in range(0, size - 3, 4)
                       if 0x1538 <= int.from_bytes(block[k:k + 4], "little") < len(d.image))
        ranked.append((material, start, size, printable, pointers))
    ranked.sort(reverse=True)
    empty = len(gaps) - len(ranked)
    print(f"unreached regions ({len(gaps)} total, {empty} entirely zero), "
          f"top 15 by material")
    print(f"  {'linear':>9} {'size':>7} {'material':>9}  composition")
    for material, start, size, printable, pointers in ranked[:15]:
        print(f"  {start:#09x} {size:7d} {material:9d}  "
              f"zero {100 * (size - material) / size:3.0f}%  "
              f"ascii {100 * printable / size:3.0f}%  "
              f"ptr-like dwords {pointers}")
    rest = sum(r[0] for r in ranked[15:])
    if rest:
        print(f"  ...and {len(ranked) - 15} smaller regions holding {rest} bytes")

    with open(args.out, "w", encoding="utf-8") as fh:
        d.listing(fh)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
