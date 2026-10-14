#!/usr/bin/env python3
"""N/A - bounded x86-32 -> 68000 translator for recovered PANZER.EXE functions.

Decodes the function's bytes from the hash-checked executable (never from a
listing), finds the instructions reachable from its entry, lowers each through an
explicit rule table and emits vasm source with the DOS address and bytes on every
line. An instruction with no rule stops the translation of that function and is
listed in the report: nothing is guessed. Method: ../F030Method/METHOD.md section
4.3b; rules, conventions and limits: analysis/x86-translation.md.

The translator core (`reachable`, `lower`, `translate`) is build-independent: it
works on a `Build` (image bytes and hash, function table, 32-bit fixup sites ->
(object, offset), the data object held in a0). `pg_build()` is the PANZER.EXE
adapter; another 32-bit flat build supplies its own adapter and its own evidence.
Every lowering carries a rule id; `coverage.py` reports which rules the
fixture-validated functions exercise.

    python3 tools/x86x/translate.py sub_00060907 sub_00060926 --out build/x86x/strings.s
"""
import argparse
from dataclasses import dataclass, field
import hashlib
import json
import re
import sys
from pathlib import Path

import capstone
from capstone import x86

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent / 'F030Method'))
from validation.flags import Node, liveness

# ---- the 68000 model -----------------------------------------------------------------
REG32 = {'eax': 'd0', 'ecx': 'd1', 'edx': 'd2', 'ebx': 'd3', 'esi': 'd4', 'edi': 'd5'}
REG16 = {'ax': 'd0', 'cx': 'd1', 'dx': 'd2', 'bx': 'd3', 'si': 'd4', 'di': 'd5'}
REG8 = {'al': 'd0', 'cl': 'd1', 'dl': 'd2', 'bl': 'd3'}
HIGH8 = {'ah': 'd0', 'ch': 'd1', 'dh': 'd2', 'bh': 'd3'}   # bits 8..15; only `xor ah,ah` has a rule
AREG = {'ebp': 'a6', 'esp': 'sp'}        # address registers: frame and stack pointer
SEGMENTS = ('es', 'ds', 'ss', 'fs', 'gs')
ARENA = 'a0'                             # base of the data object (never written by generated code)
SCRATCH = ('d6', 'd7', 'a1')             # clobbered by lowered instructions
# Conditional jumps -> m68k branches. Valid after cmp/sub (dst - src), where the
# 68000 N, Z, V, C flags equal the x86 SF, ZF, OF, CF; after test/and/or/xor
# (V = C = 0), add and neg. The `CF_CONSUMERS` need a real carry/borrow.
JCC = {'je': 'beq', 'jne': 'bne', 'js': 'bmi', 'jns': 'bpl', 'jl': 'blt', 'jge': 'bge', 'jle': 'ble',
       'jg': 'bgt', 'jb': 'bcs', 'jae': 'bcc', 'jbe': 'bls', 'ja': 'bhi', 'jo': 'bvs', 'jno': 'bvc'}
CF_CONSUMERS = {'jb', 'jae', 'jbe', 'ja'}
PRODUCERS = {'cmp', 'test', 'add', 'sub', 'and', 'or', 'xor', 'inc', 'dec', 'neg', 'shl', 'sal', 'shr', 'sar'}
V_CONSUMERS = {'jl', 'jge', 'jle', 'jg', 'jo', 'jno'}      # read OF, which shifts do not reproduce
ALU = {'add': 'add', 'sub': 'sub', 'and': 'and', 'or': 'or', 'xor': 'eor', 'cmp': 'cmp'}
ALUI = {'add': 'addi', 'sub': 'subi', 'and': 'andi', 'or': 'ori', 'xor': 'eori', 'cmp': 'cmpi'}
# Function ABI shims: the generated body keeps x86 register roles; a shim maps the
# hand-written port's calling convention onto them. in: (m68k reg, x86 reg) or
# (m68k reg, 'stack') for the one dword argument a `ret 4` function pops; out:
# registers whose new value the caller receives. Everything else is preserved.
SHIMS = {
    'sub_00060907': {'in': [('a0', 'eax'), ('a1', 'edx')], 'out': [('d0', 'eax'), ('a1', 'edx')]},
    'sub_00060926': {'in': [('a0', 'eax'), ('a1', 'edx')], 'out': [('d0', 'eax')]},
    'sub_00010976': {'in': [('a1', 'eax'), ('a2', 'edx')], 'out': [('d0', 'eax')]},
    'sub_00048105': {'in': [('d0', 'eax'), ('d1', 'edx'), ('d2', 'ebx'), ('d3', 'ecx'), ('d4', 'stack')],
                     'out': [('d0', 'eax'), ('d1', 'edx')]},
    # clipped shape draw (clip, shape, index, x, y) on the stack, plain ret: the shim drops the arguments
    'sub_00058AB4': {'in': [], 'stack': ['a1', 'a2', 'd0', 'd1', 'd2'], 'out': [('d0', 'eax')]},
    'sub_00058F9E': {'in': [], 'stack': ['a1', 'a2', 'd0', 'd1', 'd2'], 'out': [('d0', 'eax')]},
}


class Unsupported(Exception):
    pass


# Functions the translator does not translate but calls through an explicit, named boundary: the
# call becomes `bsr boundary_<name>` (x86 register roles, DOS stack arguments), the symbol is
# supplied by the harness, and the report lists them. A boundary is a substitution: its contract
# must be verified separately (e.g. by comparing the calls the DOS function received).
BOUNDARY = set()


CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
CS.detail = True


@dataclass
class Build:
    """One DOS build: the image, its function table and its relocation sites."""
    name: str
    image: bytes
    sha256: str
    functions: list = field(default_factory=list)   # sorted (vaddr, file offset, name)
    fixups: dict = field(default_factory=dict)      # vaddr of a 32-bit field -> (object, offset)
    arena_object: int = 2                           # the object whose base a0 holds

    def function(self, name):
        i = next((k for k, f in enumerate(self.functions) if f[2] == name), None)
        if i is None:
            raise Unsupported('not in the function inventory')
        vaddr, file_off, _ = self.functions[i]
        end = self.functions[i + 1][0] if i + 1 < len(self.functions) else vaddr + 0x1000
        return vaddr, file_off, self.image[file_off:file_off + (end - vaddr)]

    def name_of(self, vaddr):
        return next(f[2] for f in self.functions if f[0] == vaddr)


def pg_build():
    """PANZER.EXE (Watcom LE): inventory from work/re/functions.txt, fixups from the LE pages."""
    sys.path.insert(0, str(ROOT / 'tools/re'))
    sys.path.insert(0, str(ROOT / 'work'))
    import disasm_le  # noqa: E402  (fixup sites of the LE image)
    sha = '115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86'
    exe = (ROOT / 'game/EXE/PANZER.EXE').read_bytes()
    if hashlib.sha256(exe).hexdigest() != sha:
        raise SystemExit('wrong DOS build')
    funcs = []
    for line in (ROOT / 'work/re/functions.txt').read_text().splitlines():
        m = re.match(r'(sub_\w+) vaddr=(0x\w+) file=(0x\w+) runtime=(0x\w+)', line)
        if m:
            funcs.append((int(m[2], 16), int(m[3], 16), m[1]))
    return Build('PANZER.EXE', exe, sha, sorted(funcs), disasm_le.FIX, 2)


# ---- operands ------------------------------------------------------------------------
REG, IMM, MEM = x86.X86_OP_REG, x86.X86_OP_IMM, x86.X86_OP_MEM


def rname(op):
    return CS.reg_name(op.reg)


def sized(op, size, what='operand'):
    """m68k data register for a register operand of this size."""
    name = rname(op)
    table = {4: REG32, 2: REG16, 1: REG8}.get(size)
    if table is None or name not in table:
        raise Unsupported(f'{what} register {name} ({size} bytes)')
    return table[name]


def suffix(size):
    return {1: 'b', 2: 'w', 4: 'l'}[size]


def mask(imm, size):
    return imm & ((1 << (8 * size)) - 1)


def fits16(v):
    return -32768 <= v <= 32767


def relocated(ins, build, offset, size):
    """(object, target offset) if the field at offset..offset+size of ins is a 32-bit fixup site."""
    if size != 4:
        return None
    return build.fixups.get(ins.address + offset)


def ea(op, ins, build, scratch='a1'):
    """(lines, disp, areg): the native address of a memory operand is disp(areg) afterwards.

    address = [a0 if the displacement field is relocated into the data object]
              + base + index * scale + displacement. An unrelocated absolute address
              or a segment override is refused. `[ebp+d]`/`[esp+d]` need no lines.
    """
    m = op.mem
    if m.segment:
        raise Unsupported('segment override')
    fix = relocated(ins, build, ins.disp_offset, ins.disp_size)
    if fix:
        if fix[0] != build.arena_object:
            raise Unsupported('displacement relocated to a non-data object')
        disp = fix[1]
    else:
        disp = m.disp
    base = CS.reg_name(m.base) if m.base else None
    index = CS.reg_name(m.index) if m.index else None
    if base in AREG and not fix and not index and fits16(disp):
        return [], disp, AREG[base]
    parts = []                                   # registers to sum into the scratch address
    if fix:
        parts.append(ARENA)
    if base:
        if base in AREG:
            parts.append(AREG[base])
        elif base in REG32:
            parts.append(REG32[base])
        else:
            raise Unsupported(f'memory base {base}')
    if not parts:
        raise Unsupported('absolute address without a relocation')
    lines = [f'movea.l {parts[0]},{scratch}'] + [f'adda.l {p},{scratch}' for p in parts[1:]]
    if index:
        if index not in REG32:
            raise Unsupported(f'index register {index}')
        shift = {1: 0, 2: 1, 4: 2, 8: 3}[m.scale]
        lines.append(f'move.l {REG32[index]},d7')
        if shift:
            lines.append(f'lsl.l #{shift},d7')
        lines.append(f'adda.l d7,{scratch}')
    if not fits16(disp):
        lines.append(f'adda.l #${disp & 0xffffffff:x},{scratch}')
        disp = 0
    return lines, disp, scratch


def load(size, disp, areg, r):
    """r = memory operand (little-endian); 16-bit loads keep the upper word of r."""
    return {4: f'LD32LE {disp},{areg},{r}', 2: f'LD16LE {disp},{areg},{r}', 1: f'move.b {disp}({areg}),{r}'}[size]


def store(size, r, disp, areg):
    return {4: f'ST32LE {r},{disp},{areg}', 2: f'ST16LE {r},{disp},{areg}', 1: f'move.b {r},{disp}({areg})'}[size]


def immediate(ins, build, op, size, r):
    """Lines putting an immediate operand into r (a relocated imm32 becomes a0 + offset)."""
    fix = relocated(ins, build, ins.imm_offset, ins.imm_size)
    if fix:
        if fix[0] != build.arena_object:
            raise Unsupported('immediate relocated to a non-data object')
        return [f'move.l {ARENA},{r}', f'addi.l #${fix[1]:x},{r}']
    return [f'move.{suffix(size)} #${mask(op.imm, size):x},{r}']


# ---- the function -----------------------------------------------------------------------
def reachable(entry, code, base_v, entries=()):
    """Addresses of the instructions reachable from entry (within the code span).

    A `jmp` to another recovered function's entry (in `entries`) is a tail call and
    is not followed; any other control flow leaving the span is refused.
    """
    todo, seen, insns, byte_owners = [entry], set(), {}, {}
    while todo:
        a = todo.pop()
        if a in seen:
            continue
        if not base_v <= a < base_v + len(code):
            raise Unsupported(f'control flow leaves the recovered span at {a:#x}')
        seen.add(a)
        ins = next(CS.disasm(code[a - base_v:a - base_v + 15], a, 1), None)
        if ins is None:
            raise Unsupported(f'undecodable bytes at {a:#x}')
        if a + ins.size > base_v + len(code):
            raise Unsupported(f'{a:X}: instruction crosses recovered span')
        for byte in range(a, a + ins.size):
            if byte in byte_owners:
                raise Unsupported(f'{a:X}: overlapping instruction entry inside {byte_owners[byte]:X}')
        byte_owners.update({byte: a for byte in range(a, a + ins.size)})
        insns[a] = ins
        mn = ins.mnemonic
        if mn == 'ret':
            continue
        if mn == 'jmp' or mn in JCC or mn in ('jecxz', 'loop'):
            if ins.operands[0].type != IMM:
                raise Unsupported(f'{a:X}: indirect jump')
            target = ins.operands[0].imm
            if mn == 'jmp' and target in entries and target != entry:
                continue
            todo.append(target)
            if mn == 'jmp':
                continue
        todo.append(a + ins.size)
    return insns


@dataclass
class Lowered:
    rule: str          # rule id, for the coverage report
    lines: list        # m68k lines
    flags: object = False  # True: the last line leaves the x86 flags in CCR; 'cz': only Z, N and C (shifts)
    carry: bool = False  # True: the 68000 X flag equals the x86 CF afterwards (for a following adc/sbb)


FLAG_BITS = {name: 1 << i for i, name in enumerate(('CF', 'PF', 'AF', 'ZF', 'SF', 'OF', 'DF'))}
ALL_FLAGS = sum(FLAG_BITS.values())


def flag_effects(ins):
    """N/A - decoder flag effects, with conservative zero-count shift handling."""
    reads = writes = 0
    for name, bit in FLAG_BITS.items():
        for effect in ('TEST', 'PRIOR'):
            if ins.eflags & getattr(x86, f'X86_EFLAGS_{effect}_{name}', 0):
                reads |= bit
        for effect in ('MODIFY', 'RESET', 'SET'):
            if ins.eflags & getattr(x86, f'X86_EFLAGS_{effect}_{name}', 0):
                writes |= bit
        if ins.eflags & getattr(x86, f'X86_EFLAGS_UNDEFINED_{name}', 0):
            # Undefined does not prove the measured DOS CPU discards the old
            # bit. Preserve its dependency until an observed contract settles it.
            reads |= bit
            writes &= ~bit
    if ins.mnemonic in ('shl', 'sal', 'shr', 'sar', 'rol', 'ror', 'rcl', 'rcr'):
        count = ins.operands[-1]
        # A runtime count can be zero, preserving all input flags. Rotates
        # also wrap counts by operand width; keep those conservatively live.
        if count.type != IMM or not (count.imm & 31) or ins.mnemonic in ('rol', 'ror', 'rcl', 'rcr'):
            reads |= writes
            writes = 0
    return reads, writes


def flag_graph(insns):
    """N/A - local CFG; calls and exits observe all flags until ABI proof exists."""
    nodes = {}
    for pc, ins in insns.items():
        reads, writes = flag_effects(ins)
        if ins.mnemonic in ('call', 'ret'):
            reads, writes = ALL_FLAGS, 0
        successors = [] if ins.mnemonic in ('ret', 'jmp') else [pc + ins.size]
        if ins.mnemonic in JCC or ins.mnemonic in ('jmp', 'jecxz', 'loop'):
            successors.append(ins.operands[0].imm)
        nodes[pc] = Node(reads, writes, tuple(successors), ins.mnemonic in ('call', 'ret'))
    return nodes


def preserves_ccr(lines):
    """N/A - whitelist of emitted forms that preserve N/Z/V/C; unknown macros fail."""
    for line in lines:
        op = line.split()[0].lower()
        if op in ('movea.l', 'movea.w', 'lea', 'adda.l', 'suba.l', 'nop'):
            continue
        if op in ('addq.l', 'subq.l') and line.rsplit(',', 1)[-1].strip() in ('sp', 'a7'):
            continue
        return False
    return True


def keeps_result_nz(producer, between, lowered, captured):
    """N/A - N/Z survive moves of the producer's exact result width/register.

    This intentionally excludes comparisons, masked tests, high-byte registers,
    macros and paths with different entries. Moves clear C/V, so callers may
    use this proof only for sign/zero conditions.
    """
    ops = producer.operands
    if not ops or ops[0].type != REG:
        return False
    if producer.mnemonic == 'test':
        if len(ops) != 2 or ops[1].type != REG or ops[0].reg != ops[1].reg:
            return False
    elif producer.mnemonic not in ('add', 'sub', 'and', 'or', 'xor', 'inc', 'dec', 'neg', 'shl', 'sal', 'shr', 'sar'):
        return False
    table = {1: REG8, 2: REG16, 4: REG32}.get(ops[0].size, {})
    if rname(ops[0]) not in table:
        return False
    result = table[rname(ops[0])]
    prefix = f'move.{suffix(ops[0].size)} {result},'
    for ins in between:
        lines = lowered[ins.address].lines
        if ins.address in captured:
            return False  # its eventual tst of the captured predicate changes N/Z
        if ins.mnemonic in JCC or preserves_ccr(lines):
            continue
        if len(lines) != 1 or not lines[0].startswith(prefix):
            return False
    return True


def lower(ins, build, labels, rename):
    """Lower one instruction (these rules are the whole policy)."""
    mn, ops = ins.mnemonic, ins.operands
    n = len(ops)
    kinds = tuple(o.type for o in ops)
    size = ops[0].size if ops else 0
    s = suffix(size) if size in (1, 2, 4) else None

    if any(o.type == REG and rname(o) in HIGH8 for o in ops) and mn not in ('adc', 'sbb')             and not (mn == 'xor' and kinds == (REG, REG) and rname(ops[0]) == rname(ops[1])):
        return lower_high8(ins, build)
    if mn == 'xor' and kinds == (REG, REG) and rname(ops[0]) == rname(ops[1]) and rname(ops[0]) in HIGH8:
        return Lowered('xor.ah.ah', [f'andi.w #$ff,{HIGH8[rname(ops[0])]}'])     # flags: not x86's (Z depends on al)
    if mn in ('push', 'pop') and kinds == (REG,):
        name = rname(ops[0])
        if name in SEGMENTS:     # flat model: segment registers are never read, only the stack effect is kept
            return Lowered(f'{mn}.seg', ['subq.l #4,sp' if mn == 'push' else 'addq.l #4,sp'])
        if name == 'ebp':        # the frame pointer goes through d7 (stack slots are little-endian bytes)
            return Lowered(f'{mn}.ebp', ['move.l a6,d7', 'PUSH32 d7'] if mn == 'push' else ['POP32 d7', 'movea.l d7,a6'])
        r = sized(ops[0], 4)
        return Lowered(f'{mn}.r32', [f'PUSH32 {r}' if mn == 'push' else f'POP32 {r}'])
    if mn == 'push' and kinds == (IMM,):
        return Lowered('push.imm', immediate(ins, build, ops[0], 4, 'd7') + ['PUSH32 d7'])
    if mn == 'push' and kinds == (MEM,) and size == 4:
        pre, disp, ar = ea(ops[0], ins, build)
        return Lowered('push.m32', pre + [load(4, disp, ar, 'd7'), 'PUSH32 d7'])
    if mn in ('cld', 'nop'):
        return Lowered(mn, [])

    if mn == 'mov' and n == 2:
        a, b = ops
        if kinds == (REG, REG) and (rname(a) in AREG or rname(b) in AREG):
            if (rname(a), rname(b)) == ('ebp', 'esp'):
                return Lowered('mov.ebp.esp', ['movea.l sp,a6'])
            if (rname(a), rname(b)) == ('esp', 'ebp'):
                return Lowered('mov.esp.ebp', ['movea.l a6,sp'])
            raise Unsupported(f'`{mn} {ins.op_str}`: frame/stack pointer form')
        if kinds == (REG, IMM):
            return Lowered('mov.r.imm', immediate(ins, build, b, size, sized(a, size)))
        if kinds == (REG, REG):
            return Lowered('mov.r.r', [f'move.{s} {sized(b, size)},{sized(a, size)}'])
        if kinds == (REG, MEM):
            pre, disp, ar = ea(b, ins, build)
            return Lowered('mov.r.m', pre + [load(size, disp, ar, sized(a, size))])
        if kinds == (MEM, REG):
            pre, disp, ar = ea(a, ins, build)
            return Lowered('mov.m.r', pre + [store(size, sized(b, size), disp, ar)])
        if kinds == (MEM, IMM):
            pre, disp, ar = ea(a, ins, build)
            if size == 1:
                return Lowered('mov.m.imm', pre + [f'move.b #${mask(b.imm, 1):x},{disp}({ar})'])
            return Lowered('mov.m.imm', pre + immediate(ins, build, b, size, 'd7') + [store(size, 'd7', disp, ar)])
    if mn in ('movzx', 'movsx') and n == 2 and size in (2, 4):
        r, src = sized(ops[0], size), ops[1].size
        ext = {(1, 2): ['ext.w'], (1, 4): ['ext.w', 'ext.l'], (2, 4): ['ext.l']}[(src, size)]
        zero = {(1, 2): f'andi.w #$ff,{r}', (1, 4): f'andi.l #$ff,{r}', (2, 4): f'andi.l #$ffff,{r}'}[(src, size)]
        if ops[1].type == MEM:
            pre, disp, ar = ea(ops[1], ins, build)
            fetch = pre + [load(src, disp, ar, r)]
        elif ops[1].type == REG:
            from_ = sized(ops[1], src)
            fetch = [] if from_ == r else [f'move.{suffix(src)} {from_},{r}']
        else:
            raise Unsupported(f'{mn} operand form')
        return Lowered(mn, fetch + ([f'{e} {r}' for e in ext] if mn == 'movsx' else [zero]))
    if mn == 'lea' and kinds == (REG, MEM) and size == 4:
        pre, disp, ar = ea(ops[1], ins, build)
        return Lowered('lea', pre + [f'lea {disp}({ar}),a1', f'move.l a1,{sized(ops[0], 4)}'])

    if mn == 'imul' and size == 4 and n >= 2:
        r = sized(ops[0], 4)
        if n == 3 and ops[2].type == IMM:
            c = ops[2].imm & 0xffffffff
            if ops[1].type == MEM:
                pre, disp, ar = ea(ops[1], ins, build)
                pre = pre + [load(4, disp, ar, r)]
            elif ops[1].type == REG:
                src = sized(ops[1], 4)
                pre = [] if src == r else [f'move.l {src},{r}']
            else:
                raise Unsupported('imul operand form')
            return Lowered('imul.imm', pre + [f'IMUL32 ${c & 0xffff:x},${c >> 16:x},{r}'])
        if kinds == (REG, REG):
            return Lowered('imul.r.r', [f'IMUL32R {sized(ops[1], 4)},{r}'])
        if kinds == (REG, MEM):
            pre, disp, ar = ea(ops[1], ins, build)
            return Lowered('imul.r.m', pre + [load(4, disp, ar, 'd6'), f'IMUL32R d6,{r}'])

    if mn in ('add', 'sub') and kinds == (REG, IMM) and rname(ops[0]) == 'esp':
        k = ops[1].imm if mn == 'add' else -ops[1].imm
        if not fits16(k) or k % 2:
            raise Unsupported('stack adjustment size')
        return Lowered('esp.adjust', [f'lea {k}(sp),sp'])        # no flags: a jump after it is refused
    if mn in ALU and n == 2:
        if kinds == (REG, IMM):
            return Lowered('alu.r.imm', [f'{ALUI[mn]}.{s} #${mask(ops[1].imm, size):x},{sized(ops[0], size)}'], True, mn in ('add', 'sub'))
        if kinds == (REG, REG):
            return Lowered('alu.r.r', [f'{ALU[mn]}.{s} {sized(ops[1], size)},{sized(ops[0], size)}'], True, mn in ('add', 'sub'))
        if kinds == (REG, MEM):
            pre, disp, ar = ea(ops[1], ins, build)
            return Lowered('alu.r.m', pre + [load(size, disp, ar, 'd7'), f'{ALU[mn]}.{s} d7,{sized(ops[0], size)}'], True, mn in ('add', 'sub'))
        if kinds == (MEM, IMM) and size == 1:
            pre, disp, ar = ea(ops[0], ins, build)
            return Lowered('alu.m8.imm', pre + [f'{ALUI[mn]}.b #${mask(ops[1].imm, 1):x},{disp}({ar})'], True)
        if kinds == (MEM, IMM):          # load, operate, store: the store leaves other flags
            pre, disp, ar = ea(ops[0], ins, build)
            op = [load(size, disp, ar, 'd7'), f'{ALUI[mn]}.{s} #${mask(ops[1].imm, size):x},d7']
            if mn == 'cmp':
                return Lowered('cmp.m.imm', pre + op, True)
            return Lowered('alu.m.imm', pre + op + [store(size, 'd7', disp, ar)])
        if kinds == (MEM, REG):
            pre, disp, ar = ea(ops[0], ins, build)
            r = sized(ops[1], size)
            if mn == 'cmp':
                return Lowered('cmp.m.r', pre + [load(size, disp, ar, 'd7'), f'cmp.{s} {r},d7'], True)
            if size == 1:
                return Lowered('alu.m8.r', pre + [f'{ALU[mn]}.b {r},{disp}({ar})'], True)
            return Lowered('alu.m.r', pre + [load(size, disp, ar, 'd7'), f'{ALU[mn]}.{s} {r},d7', store(size, 'd7', disp, ar)])
    if mn in ('inc', 'dec') and n == 1:
        q = 'addq' if mn == 'inc' else 'subq'
        if kinds == (REG,):
            return Lowered(f'{mn}.r', [f'{q}.{s} #1,{sized(ops[0], size)}'], True)
        pre, disp, ar = ea(ops[0], ins, build)
        if size == 1:
            return Lowered(f'{mn}.m8', pre + [f'{q}.b #1,{disp}({ar})'], True)
        return Lowered(f'{mn}.m', pre + [load(size, disp, ar, 'd7'), f'{q}.{s} #1,d7', store(size, 'd7', disp, ar)])
    if mn in ('adc', 'sbb') and n == 2 and ops[0].type == REG:   # X must equal CF: translate() checks the predecessor
        op = 'addx' if mn == 'adc' else 'subx'
        if kinds == (REG, REG) and rname(ops[0]) in HIGH8 and rname(ops[0]) == rname(ops[1]):
            h = HIGH8[rname(ops[0])]                          # rol leaves X alone; the high byte is doubled in place
            return Lowered(f'{mn}.ah.ah', [f'rol.w #8,{h}', f'{op}.b {h},{h}', f'rol.w #8,{h}'])
        if kinds == (REG, REG):
            return Lowered(mn, [f'{op}.{s} {sized(ops[1], size)},{sized(ops[0], size)}'])
        if kinds == (REG, IMM):                               # move does not change X
            return Lowered(f'{mn}.imm', [f'move.{s} #${mask(ops[1].imm, size):x},d7', f'{op}.{s} d7,{sized(ops[0], size)}'])
    if mn in ('mul', 'imul') and n == 1 and size == 4:    # edx:eax = eax * operand (64-bit product)
        macro = 'UMUL64' if mn == 'mul' else 'SMUL64'
        if kinds == (REG,):
            return Lowered(f'{mn}.64', [f'move.l {sized(ops[0], 4)},d6', macro])
        pre, disp, ar = ea(ops[0], ins, build)
        return Lowered(f'{mn}.64', pre + [load(4, disp, ar, 'd6'), macro])
    if mn in ('neg', 'not') and kinds == (REG,):
        return Lowered(mn, [f'{mn}.{s} {sized(ops[0], size)}'], mn == 'neg', mn == 'neg')
    if mn in ('shl', 'sal', 'shr', 'sar') and n == 2 and ops[0].type == REG:
        op = {'shl': 'lsl', 'sal': 'lsl', 'shr': 'lsr', 'sar': 'asr'}[mn]
        r = sized(ops[0], size)
        if ops[1].type == IMM:
            k = ops[1].imm & 31
            if k == 0:
                raise Unsupported('shift count 0')
            return Lowered('shift.imm', [f'{op}.{s} #{k},{r}'] if k <= 8 else [f'moveq #{k},d7', f'{op}.{s} d7,{r}'], 'cz', True)
        if ops[1].type == REG and rname(ops[1]) == 'cl':
            if r == 'd1':
                raise Unsupported('shift of ecx by cl')
            return Lowered('shift.cl', ['move.l d1,d7', 'andi.l #31,d7', f'{op}.{s} d7,{r}'])   # count 0 leaves x86 flags: no 'cz'
    if mn == 'test' and n == 2:
        if kinds == (REG, REG):
            a, b = sized(ops[0], size), sized(ops[1], size)
            return Lowered('test.r.r', [f'tst.{s} {a}'] if a == b else [f'move.{s} {a},d7', f'and.{s} {b},d7'], True)
        if kinds == (REG, IMM):
            return Lowered('test.r.imm', [f'move.{s} {sized(ops[0], size)},d7', f'andi.{s} #${mask(ops[1].imm, size):x},d7'], True)
        if kinds == (MEM, IMM):
            pre, disp, ar = ea(ops[0], ins, build)
            return Lowered('test.m.imm', pre + [load(size, disp, ar, 'd7'), f'andi.{s} #${mask(ops[1].imm, size):x},d7'], True)

    if mn == 'repne scasb':
        # compares al with [edi]; the macro uses al = d0, ecx = d1, edi = d5 and leaves flags undefined
        if rname(ops[0]) != 'al' or not ops[1].mem.base or CS.reg_name(ops[1].mem.base) != 'edi' or ops[1].mem.disp:
            raise Unsupported('repne scasb operand form')
        return Lowered('repne.scasb', ['REPNE_SCASB'])
    if mn in ('rep stosb', 'rep stosd', 'stosb', 'stosd'):
        if ops[0].mem.base is None or CS.reg_name(ops[0].mem.base) != 'edi' or ops[0].mem.disp:
            raise Unsupported(f'{mn} operand form')
        return Lowered(mn.replace(' ', '.'), [mn.replace(' ', '_').upper()])   # al/eax = d0, edi d5, ecx d1
    if mn == 'xlatb':                                             # al = [ebx + al]
        return Lowered('xlatb', ['movea.l d3,a1', 'moveq #0,d7', 'move.b d0,d7', 'move.b 0(a1,d7.l),d0'])
    if mn in ('rep movsd', 'rep movsw', 'rep movsb', 'movsd', 'movsw', 'movsb'):
        if ops[0].mem.base is None or ops[1].mem.base is None or ops[0].mem.disp or ops[1].mem.disp \
                or CS.reg_name(ops[0].mem.base) != 'edi' or CS.reg_name(ops[1].mem.base) != 'esi' or ops[1].mem.segment:
            raise Unsupported(f'{mn} operand form')
        macro = mn.replace(' ', '_').upper()           # REP_MOVSD/W/B, MOVSD/W/B (esi d4, edi d5, ecx d1)
        return Lowered(mn.replace(' ', '.'), [macro])

    if mn in JCC and kinds == (IMM,):
        return Lowered('jcc', [f'{JCC[mn]} {labels[ops[0].imm]}'])
    if mn == 'jecxz' and kinds == (IMM,):
        return Lowered('jecxz', ['tst.l d1', f'beq {labels[ops[0].imm]}'])
    if mn == 'loop' and kinds == (IMM,):                           # ecx -= 1; branch while ecx != 0
        return Lowered('loop', ['subq.l #1,d1', f'bne {labels[ops[0].imm]}'])
    if mn in ('ror', 'rol') and kinds == (REG, IMM):
        k, r = ops[1].imm & 31, sized(ops[0], size)
        if k == 0:
            raise Unsupported('rotate count 0')
        if size == 4 and k == 16:
            return Lowered('rotate', [f'swap {r}'])
        return Lowered('rotate', [f'{mn}.{s} #{k},{r}'] if k <= 8 else [f'moveq #{k},d7', f'{mn}.{s} d7,{r}'])
    if mn == 'jmp' and kinds == (IMM,):
        if ops[0].imm not in labels:                                  # tail call to a recovered function
            return Lowered('jmp.tail', [f'bra {rename(ops[0].imm)}'])
        return Lowered('jmp', [f'bra {labels[ops[0].imm]}'])
    if mn == 'leave':
        return Lowered('leave', ['movea.l a6,sp', 'POP32 d7', 'movea.l d7,a6'])
    if mn == 'cwde':
        return Lowered('cwde', ['ext.l d0'])
    if mn == 'cdq':                                                   # edx = sign of eax (0 or -1)
        return Lowered('cdq', ['move.l d0,d2', 'add.l d2,d2', 'subx.l d2,d2'])
    if mn == 'call' and kinds == (IMM,):
        if ops[0].imm not in {f[0] for f in build.functions}:
            raise Unsupported(f'call target {ops[0].imm:#x} is not a recovered function')
        if build.name_of(ops[0].imm) in BOUNDARY:
            return Lowered('call.boundary', [f'bsr boundary_{build.name_of(ops[0].imm)}'])
        return Lowered('call', [f'bsr {rename(ops[0].imm)}'])
    if mn == 'ret':
        if not ops:
            return Lowered('ret', ['rts'])
        k = ops[0].imm                         # `ret n`: pop the return address, then n argument bytes
        if not 0 < k <= 32760 or k % 2:
            raise Unsupported('ret argument size')
        return Lowered('ret.n', ['movea.l (sp)+,a1', f'lea {k}(sp),sp', 'jmp (a1)'])
    raise Unsupported(f'no lowering rule for `{mn} {ins.op_str}`')


def lower_high8(ins, build):
    """8-bit `mov`/ALU instructions with an `ah`/`bh`/`ch`/`dh` operand (bits 8..15 of d0..d3).

    A high-byte source is read into d7 (`move.w`, `lsr.w #8`). A high-byte destination
    is computed in d6 and written back with two `ror.w #8` around a `move.b`, which
    leaves CCR unlike x86, so only `cmp` keeps x86 flags there.
    """
    mn, ops = ins.mnemonic, ins.operands
    if len(ops) != 2 or ops[0].size != 1 or (mn not in ALU and mn not in ('mov', 'test')):
        raise Unsupported(f'`{mn} {ins.op_str}`: high-byte register form')
    dst, src = ops
    if mn == 'test':                            # both operands are registers here: d7 = a & b
        parts = []
        for o in (dst, src):
            if o.type == REG and rname(o) in HIGH8:
                parts.append(f'high:{HIGH8[rname(o)]}')
            elif o.type == REG and rname(o) in REG8:
                parts.append(REG8[rname(o)])
            else:
                raise Unsupported(f'`{mn} {ins.op_str}`: high-byte register form')
        first, second = parts
        lines = []
        if first.startswith('high:'):
            lines += [f'move.w {first[5:]},d7', 'lsr.w #8,d7']
        else:
            lines += [f'move.b {first},d7']
        if second.startswith('high:'):
            lines += [f'move.w {second[5:]},d6', 'lsr.w #8,d6', 'and.b d6,d7']
        else:
            lines += [f'and.b {second},d7']
        return Lowered('test.ah', lines, True)
    pre = []
    if dst.type == MEM:                          # the destination address first: ea may use d7
        pre, disp, ar = ea(dst, ins, build)
        d = f'{disp}({ar})'
    elif dst.type == REG and rname(dst) in REG8:
        d = REG8[rname(dst)]
    elif dst.type == REG and rname(dst) in HIGH8:
        d = None
    else:
        raise Unsupported(f'`{mn} {ins.op_str}`: high-byte register form')
    if src.type == IMM:
        operand = f'#${mask(src.imm, 1):x}'
    elif src.type == REG and rname(src) in REG8:
        operand = REG8[rname(src)]
    elif src.type == REG and rname(src) in HIGH8:
        pre, operand = pre + [f'move.w {HIGH8[rname(src)]},d7', 'lsr.w #8,d7'], 'd7'
    elif src.type == MEM and d is None:
        pre2, disp, ar = ea(src, ins, build)
        pre, operand = pre + pre2, f'{disp}({ar})'
        if mn == 'xor':                          # eor takes a data-register source only
            pre, operand = pre + [f'move.b {operand},d7'], 'd7'
    else:
        raise Unsupported(f'`{mn} {ins.op_str}`: high-byte register form')
    if d is None:                                # high byte is the destination
        h = HIGH8[rname(dst)]
        if mn == 'mov':                          # read the source first: `mov ah,al` reads the register it rotates
            if operand != 'd7':
                pre = pre + [f'move.b {operand},d7']
            return Lowered('mov.ah', pre + [f'ror.w #8,{h}', f'move.b d7,{h}', f'ror.w #8,{h}'])
        opcode = ALUI[mn] if operand.startswith('#') else ALU[mn]
        value = [f'move.w {h},d6', 'lsr.w #8,d6', f'{opcode}.b {operand},d6']
        if mn == 'cmp':
            return Lowered('cmp.ah', pre + value, True)
        return Lowered('alu.ah', pre + value + [f'ror.w #8,{h}', f'move.b d6,{h}', f'ror.w #8,{h}'])
    # the high byte is the source (now d7); the destination is an 8-bit register or memory operand
    if mn == 'mov':
        return Lowered('mov.r.ah', pre + [f'move.b d7,{d}'])
    if mn == 'cmp':
        return Lowered('cmp.r.ah', pre + ([f'cmp.b d7,{d}'] if not d.endswith(')') else [f'move.b {d},d6', 'cmp.b d7,d6']), True)
    return Lowered('alu.r.ah', pre + [f'{ALU[mn]}.b d7,{d}'], True)


def parallel_moves(moves):
    """Lines that assign every (src, dst) at once (sources read before any destination is written)."""
    pairs = [(s, d) for s, d in moves if s != d]
    return [f'move.l {s},-(sp)' for s, _ in pairs] + [f'move.l (sp)+,{d}' for _, d in reversed(pairs)]


def translate(name, build, *, optimize=True):
    vaddr, file_off, code = build.function(name)
    insns = reachable(vaddr, code, vaddr, {f[0] for f in build.functions})
    order = sorted(insns)
    for a in order:                                # a fall-through must land on emitted code
        ins = insns[a]
        if ins.mnemonic not in ('ret', 'jmp') and a + ins.size not in insns:
            raise Unsupported(f'{a:X}: falls through into unreachable bytes')
    targets = {x.operands[0].imm for x in insns.values()
               if (x.mnemonic in JCC or x.mnemonic in ('jmp', 'jecxz', 'loop')) and x.operands[0].type == IMM
               and x.operands[0].imm in insns}
    # Source-PC labels are global, so branch labels must not depend on vasm's
    # last-global-label scope. Function IDs keep concatenated routines unique.
    labels = {t: f'x86_branch_{name}_{t:X}' for t in targets}
    spec = SHIMS.get(name)
    body = f'x86_{name}' if spec else name

    def rename(v):
        callee = build.name_of(v)
        return f'x86_{callee}' if callee in SHIMS else callee

    lowered = {a: lower(insns[a], build, labels, rename) for a in order}
    # Flag rule. A conditional jump reads the flags of the nearest preceding flag-setting
    # instruction (`producer`), whose lowering leaves the same flags in CCR. Between them
    # there may be other conditional jumps (Bcc leaves CCR alone) or, in capture mode,
    # instructions that do not change the x86 flags and are not control flow: then the
    # condition is captured right after the producer (`Scc d7`, `movea.l d7,a2`) and the
    # jump tests a2. Nothing in the chain may be a branch target (flags from several paths).
    # One captured condition per producer; a `call` in between is refused (a2 is not saved).
    CONTROL = set(JCC) | {'jmp', 'call', 'ret', 'jecxz', 'loop'}
    capture = {}                                   # producer address -> (m68k condition, jump address)
    captured = {}                                  # jump address -> m68k condition
    for i, a in enumerate(order):
        ins = insns[a]
        if ins.mnemonic not in JCC:
            continue
        j = i - 1
        neutral = False
        while j >= 0 and insns[order[j]].mnemonic not in PRODUCERS:
            m = insns[order[j]].mnemonic
            if flag_effects(insns[order[j]])[1]:
                raise Unsupported(f'{a:X}: intervening `{m}` changes x86 flags')
            if m in JCC and not neutral:
                j -= 1
                continue
            if m in CONTROL:
                raise Unsupported(f'{a:X}: `{ins.mnemonic}` is not directly after a flag-setting instruction')
            neutral |= not (optimize and preserves_ccr(lowered[order[j]].lines))
            j -= 1
        if j < 0:
            raise Unsupported(f'{a:X}: `{ins.mnemonic}` has no flag-setting instruction before it')
        prod = insns[order[j]]
        if any(order[k] + insns[order[k]].size != order[k + 1] for k in range(j, i)):
            raise Unsupported(f'{a:X}: flag chain crosses a noncontiguous code range')
        if any(order[k] in targets for k in range(j + 1, i + 1)) or not lowered[prod.address].flags:
            raise Unsupported(f'{a:X}: `{ins.mnemonic}` is not directly after a flag-setting instruction')
        if prod.mnemonic in ('inc', 'dec') and ins.mnemonic in CF_CONSUMERS:
            raise Unsupported(f'{a:X}: `{ins.mnemonic}` needs CF, which inc/dec leave unchanged on x86')
        if lowered[prod.address].flags == 'cz' and ins.mnemonic in V_CONSUMERS:
            raise Unsupported(f'{a:X}: `{ins.mnemonic}` needs OF, which a shift does not reproduce')
        if optimize and neutral and ins.mnemonic in ('je', 'jne', 'js', 'jns'):
            if keeps_result_nz(prod, [insns[order[k]] for k in range(j + 1, i)], lowered, captured):
                neutral = False
        if neutral:
            cond = JCC[ins.mnemonic][1:]
            if prod.address in capture and capture[prod.address][0] != cond:
                raise Unsupported(f'{a:X}: a second captured condition after {prod.address:X}')
            capture[prod.address] = (cond, a)
            captured[a] = cond
    # Carry rule: adc/sbb must directly follow an instruction whose lowering leaves X = CF.
    for i, a in enumerate(order):
        ins = insns[a]
        if ins.mnemonic not in ('adc', 'sbb'):
            continue
        prev = insns[order[i - 1]] if i else None
        if a in targets or prev is None or prev.address + prev.size != a or not lowered[prev.address].carry:
            raise Unsupported(f'{a:X}: `{ins.mnemonic}` is not directly after an instruction that leaves X = CF')
    for a, (cond, _) in capture.items():
        lowered[a] = Lowered(lowered[a].rule, lowered[a].lines + [f's{cond} d7', 'movea.l d7,a2'], lowered[a].flags, lowered[a].carry)
    for a, cond in captured.items():
        lowered[a] = Lowered('jcc.captured', ['move.l a2,d7', 'tst.b d7', f'bne {labels[insns[a].operands[0].imm]}'])

    _, live_out = liveness(flag_graph(insns), ALL_FLAGS)
    removed = []
    if optimize:
        for a in order:
            ins = insns[a]
            # Only register/immediate comparisons: memory reads may fault or
            # access devices and must not disappear. Retain every entry label.
            if ins.mnemonic in ('cmp', 'test') and all(op.type in (REG, IMM) for op in ins.operands):
                if not live_out[a] & flag_effects(ins)[1]:
                    lowered[a] = Lowered('flags.dead', [])
                    removed.append(a)

    end = insns[order[-1]].address + insns[order[-1]].size
    out = [f'; {name}  vaddr ${vaddr:x}..${end:x}  file ${file_off:x}',
           f'        xdef {body}' if not spec else f'; shim {name}: hand-written ABI -> x86 register roles',
           f'{body}:']
    for a in order:
        ins = insns[a]
        out.append(f'x86_pc_{name}_{a:X}:')
        if a in labels:
            out.append(f'{labels[a]}:')
        lines = lowered[a].lines
        if not lines:
            out.append(f'        ; {a:X} {ins.bytes.hex()} {ins.mnemonic} {ins.op_str}')
            continue
        out.append(f'        {lines[0]:<40}; {a:X} {ins.bytes.hex()} {ins.mnemonic} {ins.op_str}')
        out += [f'        {l}' for l in lines[1:]]
    if spec:
        rets = {bool(insns[a].operands) for a in order if insns[a].mnemonic == 'ret'}
        if len(rets) != 1:
            raise Unsupported('shim: the function mixes ret and ret n')
        out += shim(name, body, spec, caller_cleans=not rets.pop())
    return out, {'name': name, 'vaddr': vaddr, 'end': end, 'instructions': len(order),
                 'bytes': sum(insns[a].size for a in order), 'rules': sorted({l.rule for l in lowered.values()}),
                 'deadFlagInstructions': removed, 'conditionCaptures': len(capture),
                 'sourceMap': [{'functionId': name, 'pc': a, 'bytes': insns[a].bytes.hex(),
                                'label': f'x86_pc_{name}_{a:X}', 'rule': lowered[a].rule,
                                'emittedLines': len(lowered[a].lines)} for a in order]}


def shim(name, body, spec, caller_cleans):
    """The hand-written calling convention as a wrapper around the generated body.

    spec['in']: (m68k reg, x86 reg) register inputs, moved all at once; spec['stack']:
    m68k registers holding the DOS stack arguments in argument order (pushed last
    first, little-endian); spec['out']: (m68k reg, x86 reg) results. A `ret n` body
    pops its arguments; after a plain `ret` the shim drops them (caller_cleans).
    """
    outputs = {m for m, _ in spec['out']}
    saved = [r for r in ['d0', 'd1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7', 'a1', 'a2', 'a6'] if r not in outputs]
    regs = '/'.join(saved)
    stack_args = list(spec.get('stack', [])) + [m for m, x in spec['in'] if x == 'stack']
    register_in = [(m, REG32[x]) for m, x in spec['in'] if x != 'stack']
    if set(stack_args) & {d for _, d in register_in}:
        raise Unsupported('shim: a stack argument source is overwritten by a register input')
    out = [f'        xdef {name}', f'{name}:', f'        movem.l {regs},-(sp)']
    out += ['        ' + l for l in parallel_moves(register_in)]
    for m in reversed(stack_args):
        out += [f'        move.l {m},d7', '        PUSH32 d7']
    out += [f'        bsr {body}']
    if stack_args and caller_cleans:
        out.append(f'        lea {4 * len(stack_args)}(sp),sp')
    out += ['        ' + l for l in parallel_moves([(REG32[x], m) for m, x in spec['out']])]
    out += [f'        movem.l (sp)+,{regs}', '        rts']
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('functions', nargs='+')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--report', type=Path)
    ap.add_argument('--source-map', type=Path, help='machine-readable source labels and lowering costs')
    ap.add_argument('--conservative', action='store_true', help='diagnostic baseline without flag optimizations')
    ap.add_argument('--boundary', action='append', default=[],
                    help='function called through harness symbol boundary_<name> instead of being translated')
    args = ap.parse_args()
    BOUNDARY.update(args.boundary)
    build = pg_build()
    source = [f'; Generated by tools/x86x/translate.py from {build.name} sha256 {build.sha256}',
              '; Do not edit. Conventions and limits: analysis/x86-translation.md.',
              '        include "x86rt.i"', '        section text,code']
    source += [f'; boundary (not translated, harness-provided): boundary_{b}' for b in sorted(BOUNDARY)]
    report, failed, sites = [], 0, []
    for name in args.functions:
        try:
            lines, info = translate(name, build, optimize=not args.conservative)
        except Unsupported as error:
            failed += 1
            report.append(f'UNSUPPORTED {name}: {error}')
            continue
        source += lines
        sites += info['sourceMap']
        report.append(f'TRANSLATED {name}: {info["instructions"]} instructions, {info["bytes"]} bytes, '
                      f'${info["vaddr"]:x}..${info["end"]:x}; rules {" ".join(info["rules"])}')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if not failed:
        generated = '\n'.join(source) + '\n'
        args.out.write_text(generated)
        if args.source_map:
            args.source_map.parent.mkdir(parents=True, exist_ok=True)
            args.source_map.write_text(json.dumps({'sourceSha256': build.sha256,
                'generatedSha256': hashlib.sha256(generated.encode()).hexdigest(),
                'generatorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'flagAnalysisSha256': hashlib.sha256((ROOT.parent / 'F030Method/validation/flags.py').read_bytes()).hexdigest(),
                'capstoneVersion': capstone.__version__,
                'optimized': not args.conservative, 'sites': sites}, indent=2) + '\n')
    text = '\n'.join(report) + '\n'
    if args.report:
        args.report.write_text(text)
    sys.stdout.write(text)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
