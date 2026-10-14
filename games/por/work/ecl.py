#!/usr/bin/env python3
"""ECL bytecode decoder + the evidence for the encoding and the block layout.

Everything here is read out of the interpreter in `GAME.OVR`; see
`analysis/data-formats.md` §`ECL*.DAX`. The routines that matter:

    020:35DB  execute loop      -- PC := arg; loop { fetch opcode; dispatch }
    020:32DF  opcode dispatcher -- the complete opcode -> handler table (HANDLER)
    045:0000  operand decoder   -- entry_0000(n), reads n operands, advances PC
    045:013F  operand evaluator -- entry_013F(i), resolves operand i to a value
    045:06BE  address builder   -- entry_06BE(value, extra) = (extra << 8) | value
    045:01C8  block init        -- PC := 0x9900, then reads the 5-entry header
    020:0B1A  operand-count classifier -- used ONLY by the conditional-skip path

    instruction := [u8 opcode] [operand x N]      ; N from OPERANDS below
    operand     := [u8 type] [u8 value]           ; 2 bytes, plus either
                     [u8 extra]                   ;   +1   iff type in EXT_TYPES
                     [u8 text x value]            ;   +value iff type == 0x80

BLOCK LAYOUT. A block opens with a 20-byte header of five 4-byte records, each
written as a `01 [01 lo hi]` instruction. `045:01C8` walks them with five
`entry_0000(1)` + `entry_06BE` pairs and files the five addresses into
`DS:0x4944 / 0x4946 / 0x4948 / 0x494A / 0x494C` -- the block's five script
entry points, which the game later passes to the execute loop (`020:3134`,
`020:3741`, `020:3658`, ...). Writing them as real `01` (GOTO) instructions is
what makes entry #1 also work by falling in at PC 0. All 29 blocks parse.

So a block is NOT a flat instruction stream and never was: it is code reachable
from those five roots, interleaved with data islands. `--walk` follows control
flow from the roots; `--sweep` linear-sweeps and resyncs past islands.

PC is stored biased: the interpreter indexes `buffer[(PC + 0x6700) & 0xFFFF]`
and init sets PC = 0x9900, so block offset = (PC - 0x9900) & 0xFFFF, and the
buffer's 0x9900..0xB6FF address range is exactly its 7,680 bytes
(`045:070B` classifies addresses into regions and names that one).

Usage:
    python3 work/ecl.py --validate            # whole-corpus coverage report
    python3 work/ecl.py ECL1.DAX 0x12         # disassemble one block
    python3 work/ecl.py --text                # every inline string in the corpus
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dax

EXPANDED = os.path.join(os.path.dirname(HERE), 'work', 'expanded')

PC_BASE = 0x9900        # 045:01C8; buffer spans 0x9900..0xB6FF (045:070B)
HDR_ENTRIES = 5         # 045:01C8 reads exactly five
HDR_SIZE = HDR_ENTRIES * 4

# opcode -> handler offset in unit 020, the complete dispatch chain at 020:32DF.
# Opcode 0x1F is absent from it: it has no handler and falls into the
# "illegal opcode" reporter at 020:356D, so it cannot occur in valid code.
HANDLER = {
    0x00: 0x0001, 0x01: 0x00ED, 0x02: 0x010C, 0x03: 0x0123, 0x04: 0x01A0,
    0x05: 0x01A0, 0x06: 0x01A0, 0x07: 0x01A0, 0x08: 0x0237, 0x09: 0x0295,
    0x0A: 0x02E3, 0x0B: 0x044D, 0x0C: 0x03B1, 0x0D: 0x07E1, 0x0E: 0x0822,
    0x0F: 0x091D, 0x10: 0x0960, 0x11: 0x09D5, 0x12: 0x09D5, 0x13: 0x0A6B,
    0x14: 0x0AB5, 0x15: 0x0FEE, 0x16: 0x0C5A, 0x17: 0x0C5A, 0x18: 0x0C5A,
    0x19: 0x0C5A, 0x1A: 0x0C5A, 0x1B: 0x0C5A, 0x1C: 0x133D, 0x1D: 0x13A0,
    0x1E: 0x1512, 0x20: 0x0CDD, 0x21: 0x0D80, 0x22: 0x16FC, 0x23: 0x1798,
    0x24: 0x186C, 0x25: 0x19C9, 0x26: 0x19C9, 0x27: 0x1A81, 0x28: 0x1EA4,
    0x29: 0x20B1, 0x2A: 0x0F44, 0x2B: 0x11B1, 0x2C: 0x27A8, 0x2D: 0x3026,
    0x2E: 0x2AE2, 0x2F: 0x0ED5, 0x30: 0x0ED5, 0x31: 0x2DF9, 0x32: 0x2847,
    0x33: 0x2E44, 0x34: 0x2E1A, 0x35: 0x0FA2, 0x36: 0x2EDB, 0x37: 0x0D80,
    0x38: 0x3167, 0x39: 0x2E90, 0x3A: 0x28F3, 0x3B: 0x2F64, 0x3C: 0x31D8,
    0x3D: 0x2E6F,
}
MAX_OPCODE = 0x3D

# opcode -> fixed operand count, taken from each handler's own
# `MOV AL,n / PUSH AX / CALLF entry_0000` -- i.e. what the code that actually
# runs consumes. Opcodes absent from this table take none.
#
# NB this is NOT the same table as the classifier at 020:0B1A, which an earlier
# pass used as the authority. The classifier disagrees on five opcodes and is
# only ever consulted by the conditional-skip path (020:0C5A), so the handler
# wins. See DIVERGENT below.
OPERANDS = {}
for _n, _ops in [
    (1,  [0x01, 0x02, 0x0A, 0x0E, 0x11, 0x12, 0x1D, 0x20,
          0x2D, 0x32, 0x34, 0x36, 0x38, 0x39, 0x3C]),
    (2,  [0x03, 0x08, 0x09, 0x0F, 0x10, 0x22, 0x25, 0x26, 0x2B]),
    (3,  [0x04, 0x05, 0x06, 0x07, 0x0B, 0x0C, 0x15, 0x21, 0x28, 0x2A,
          0x2F, 0x30, 0x35, 0x37, 0x3B]),
    (4,  [0x14, 0x23]),
    (5,  [0x2E]),
    (6,  [0x1E, 0x2C]),
    (8,  [0x27]),
    (14, [0x29]),
]:
    for _o in _ops:
        OPERANDS[_o] = _n

# Opcodes whose operand count is not fixed: after the listed fixed operands the
# handler evaluates operand number VARCOUNT[op], backs the PC up one byte
# (`DEC word ptr [0x494e]`) and calls entry_0000 again with that value, so the
# instruction carries `fixed + N` operands with N read from the stream.
# This is the construct that desynced every previous linear walk.
#   0x15  020:1035  a menu: 3 fixed + N choices
#   0x25  020:19E6  ON sel GOTO:  2 fixed + N addresses  (020:1A18 selects
#   0x26            ON sel GOSUB: 2 fixed + N addresses   goto vs gosub)
#   0x2B  020:11D8  2 fixed + N
VARCOUNT = {0x15: 3, 0x25: 2, 0x26: 2, 0x2B: 2}

# Where the classifier at 020:0B1A disagrees with the handlers. Recorded because
# it is a real inconsistency in the shipped interpreter, not a reading error: a
# conditional (0x16-0x1B) that guards one of these five instructions skips the
# wrong number of bytes. No block in the corpus does that, so it never fires.
DIVERGENT = {0x0C: (2, 3), 0x15: (0, '3+N'), 0x25: (0, '2+N'),
             0x26: (0, '2+N'), 0x2B: (0, '2+N')}

# Operand types that carry a third byte (entry_0000's inner branches).
EXT_TYPES = {0x01, 0x02, 0x03, 0x81}

# NB: there is deliberately no "valid operand types" whitelist. entry_0000
# gives special handling to 1/2/3 (extra byte), 0x80 (inline text) and 0x81
# (extra byte + computed string); EVERY other type byte falls through its
# if-chain and is simply a plain 2-byte operand.

# Control flow, all from the handlers:
#   0x00  020:009A  sets DS:0x4390 -> the execute loop at 020:35E9 exits
#   0x01  020:0105  PC := entry_06BE(op1)                        GOTO
#   0x02  045:19E8  push PC on the 6-byte-node stack at DS:0x6D36, PC := target
#   0x13  020:0A82  PC := popped node                            RETURN
#   0x25/0x26       ON sel GOTO/GOSUB over the N trailing operands
CONDITIONALS = set(range(0x16, 0x1C))
TERMINATORS = {0x00, 0x13}

# Opcode semantics, each read from its handler (`work/eclops.py <op>`).
# `op1`..`opN` are the evaluated operands; `[opN]` is the ECL address operand N
# encodes. See analysis/data-formats.md §Opcode semantics.
SEMANTICS = {
    0x00: ('END',     'stop the script (sets DS:0x4390)'),
    0x01: ('GOTO',    'PC := [op1]'),
    0x02: ('GOSUB',   'push PC, PC := [op1]'),
    0x03: ('CMP',     'compare op1 with op2 -> the six flags'),
    0x04: ('ADD',     '[op3] := op1 + op2'),
    0x05: ('SUB',     '[op3] := op2 - op1'),
    0x06: ('DIV',     '[op3] := op1 / op2'),
    0x07: ('MUL',     '[op3] := op1 * op2'),
    0x08: ('RANDOM',  '[op2] := Random(min(op1, 254) + 1)'),
    0x09: ('SET',     '[op2] := op1  (string if operand 1 is type >= 0x80)'),
    0x0B: ('ADDMONS', 'append op2 copies of monster type op1 to the encounter'),
    0x0D: ('ENCNEAR', 'range -= 1 (if > 0), then redisplay as 0x0C does'),
    0x0C: ('ENCSHOW', "0x29's setup without the prompt: display only, no result"),
    0x11: ('ASKYN',   'ask a yes/no question'),
    0x12: ('TEXT',    'display text'),
    0x13: ('RETURN',  'PC := popped return address'),
    0x15: ('MENU',    'a menu: prompt + N choices'),
    0x1C: ('DROPITEMS', 'free the pending item list, clear the 0x6752 params'),
    0x16: ('IFEQ',    'run the next instruction only if =='),
    0x17: ('IFNE',    'run the next instruction only if !='),
    0x18: ('IFLT',    'run the next instruction only if <'),
    0x19: ('IFGT',    'run the next instruction only if >'),
    0x1A: ('IFLE',    'run the next instruction only if <='),
    0x1B: ('IFGE',    'run the next instruction only if >='),
    0x25: ('ONGOTO',  'PC := [operand op1+3] of the N trailing addresses'),
    0x26: ('ONGOSUB', 'gosub [operand op1+3] of the N trailing addresses'),
    0x24: ('RUNENC',  'run/redraw the pending encounter; partially read'),
    0x27: ('MKITEMS', '7 params -> DS:0x6752; op8 loads ITEM<n>.dax or rolls N'),
    0x29: ('ENCOUNTER', 'the encounter prompt: 3 messages, 5 flags, result 1-3 in [op4]'),
    0x2A: ('LOADIDX', '[op3] := *([op1] + op2)   -- indexed load'),
    0x35: ('STOREIDX', '*([op2] + op3) := op1     -- indexed store'),
    0x2F: ('AND',     '[op3] := op1 & op2, and compare the result with 0'),
    0x30: ('OR',      '[op3] := op1 | op2, and compare the result with 0'),
}
NAMES = {op: n for op, (n, _d) in SEMANTICS.items()}

# The six flags at DS:0x6D3E-0x6D43, all set together by the comparator
# `045:1929` (numbers) or `045:1853` (strings) from `CMP a, b`:
#   0x6D3E a==b   0x6D3F a!=b   0x6D40 a<b   0x6D41 a>b   0x6D42 a<=b   0x6D43 a>=b
# `020:0C5A` runs the instruction after conditional 0x16+k only when flag k is
# set, so 0x16..0x1B read as ==, !=, <, >, <=, >=.
FLAGS = {0x16: '==', 0x17: '!=', 0x18: '<', 0x19: '>', 0x1A: '<=', 0x1B: '>='}

# Facing values, from the step arithmetic in the forward-range probe
# `045:0489`: only even values occur, which is the script-side confirmation of
# the dungeon view's 4-directional finding.
FACING = {0: 'north (-Y)', 2: 'east (+X)', 4: 'south (+Y)', 6: 'west (-X)'}

# The ECL address space, from the region classifier `045:070B` and the
# load/store pair `045:0E2E` / `045:0C93`. Every region index is a deliberate
# 16-bit wrap, the same trick as the PC's -0x6700 bias.
REGIONS = [
    (0x4900, 0x4D00, 'words at [DS:0x4933] + 0x6E00 + 2*addr'),
    (0x6B00, 0x6F00, 'words at [DS:0x4937] + 0x2A00 + 2*addr'),
    (0x9700, 0x9900, 'words at [DS:0x493B] - 0x2E00 + 2*addr'),
    (0x9900, 0xB700, 'BYTES of the script buffer itself, [DS:0x493F] + 0x6700 + addr'),
]
# Region 4 is everything else: a hand-written window onto game state.
SPECIAL_VARS = {
    0x00B1: 'DS:0x6D34', 0x00FB: 'DS:0x6D30', 0x00FC: 'DS:0x6D32',
    0x033D: 'party facing (DS:0x6A0D)',
    0xC04B: 'party X (DS:0x6A0B, signed)',
    0xC04C: 'party Y (DS:0x6A0C, signed)',
    0xC04D: 'party facing / 2 (DS:0x6A0D >> 1)',
    0xC04E: 'DS:0x6A0E', 0xC04F: 'DS:0x6A0F',
}


class DecodeError(ValueError):
    pass


def read_operand(buf, pc):
    """(type, value, extra, text, size) for the operand starting at `pc`."""
    if pc + 1 >= len(buf):
        raise DecodeError(f'operand truncated at {pc}')
    t, v = buf[pc], buf[pc + 1]
    if t in EXT_TYPES:
        if pc + 2 >= len(buf):
            raise DecodeError(f'operand extra byte truncated at {pc}')
        return t, v, buf[pc + 2], None, 3
    if t == 0x80:
        if pc + 2 + v > len(buf):
            raise DecodeError(f'inline text runs past end at {pc}')
        return t, v, None, unpack_text(buf[pc + 2:pc + 2 + v]), 2 + v
    return t, v, None, None, 2


def read_insn(buf, pc):
    """(opcode, [(type, value, extra, text), ...], size) at `pc`."""
    op = buf[pc]
    if op > MAX_OPCODE or op not in HANDLER:
        raise DecodeError(f'invalid opcode {op:#04x} at {pc}')
    n = OPERANDS.get(op, 0)
    ops = []
    p = pc + 1
    i = 0
    while i < n:
        t, v, e, x, sz = read_operand(buf, p)
        ops.append((t, v, e, x))
        p += sz
        i += 1
        if op in VARCOUNT and i == VARCOUNT[op]:
            # entry_013F returns `value` unchanged for type 0 (immediate); any
            # other type is a memory read, so the length is only known at run
            # time and this instruction cannot be decoded statically.
            if t != 0:
                raise DecodeError(
                    f'{op:#04x} at {pc}: operand count is type {t:#04x}, '
                    f'not an immediate')
            n += v
    return op, ops, p - pc


def address(operand):
    """entry_06BE: the 16-bit address an operand's value/extra bytes encode."""
    t, v, e, x = operand
    return ((e or 0) << 8) | v


def to_offset(addr):
    """Block offset for an interpreter address (the biased-PC wrap)."""
    return (addr - PC_BASE) & 0xFFFF


def header(buf):
    """The five script entry points, as block offsets. Raises if malformed."""
    if len(buf) < HDR_SIZE:
        raise DecodeError('block shorter than the 20-byte header')
    out = []
    for i in range(HDR_ENTRIES):
        rec = buf[i * 4:i * 4 + 4]
        if rec[0] != 0x01:
            raise DecodeError(f'header record {i} is not a 01 GOTO')
        out.append(to_offset((rec[3] << 8) | rec[2]))
    return out


def walk(buf, seeds=None):
    """Follow control flow from the five entry points.

    Returns (insns, covered): `insns` maps offset -> (opcode, operands, size),
    `covered` is a per-byte flag.

    The one non-obvious rule is the conditional skip. `020:0C5A` steps the PC
    past a conditional (0x16-0x1B) and then re-enters the decoder for the NEXT
    instruction only when the guard flag is clear -- so a guarded instruction
    is either executed or skipped, and when the guarded instruction is a GOTO,
    an END or a RETURN its fallthrough is live too. Without this rule the walk
    reaches ~16 % of a block; with it, 97.7 %. `if <cond> goto` is simply how
    the scripts are written.
    """
    insns = {}
    covered = bytearray(len(buf))
    # keyed on (pc, guarded): reaching an instruction under a conditional opens
    # a path -- its skip fallthrough -- that reaching it unguarded does not.
    seen = set()
    work = [(s, False) for s in (seeds if seeds is not None else header(buf))]
    while work:
        pc, guarded = work.pop()
        while True:
            if pc >= len(buf) or (pc, guarded) in seen:
                break
            seen.add((pc, guarded))
            try:
                op, ops, sz = read_insn(buf, pc)
            except DecodeError:
                break
            insns[pc] = (op, ops, sz)
            for k in range(pc, min(pc + sz, len(buf))):
                covered[k] = 1
            if op == 0x02:                       # GOSUB -- both paths live
                t = to_offset(address(ops[0]))
                if t < len(buf):
                    work.append((t, False))
            elif op in (0x25, 0x26):              # ON sel GOTO/GOSUB
                for o in ops[VARCOUNT[op]:]:
                    t = to_offset(address(o))
                    if t < len(buf):
                        work.append((t, False))
            if op == 0x01 or op in TERMINATORS:
                if op == 0x01:
                    t = to_offset(address(ops[0]))
                    if t < len(buf):
                        if guarded:
                            work.append((t, False))
                        else:
                            pc, guarded = t, False
                            continue
                    elif not guarded:
                        break
                if not guarded:
                    break
                pc += sz                          # the skip path
                guarded = False
                continue
            guarded = op in CONDITIONALS
            pc += sz
    return insns, covered


def sweep(buf, insns=None):
    """Fill what `walk` did not reach by linear sweep, resyncing one byte at
    a time past anything that will not decode.

    HEURISTIC, and known to be wrong sometimes: a sweep that starts inside a
    data table decodes the table as instructions and then runs on into real
    code, swallowing it. That is exactly how an earlier version of this file
    lost two real TEXT instructions that a naive byte scan had found
    (`ECL7.DAX` 0x17 +1005, `ECL5.DAX` 0x06 +3053) -- both are decoded
    correctly by `walk` now. Use it to look at the leftovers, not as evidence.
    Returns (insns, islands)."""
    insns = dict(insns) if insns else {}
    covered = bytearray(len(buf))
    for off, (_o, _ops, sz) in insns.items():
        for k in range(off, min(off + sz, len(buf))):
            covered[k] = 1
    pc = HDR_SIZE
    while pc < len(buf):
        if covered[pc]:
            pc += 1
            continue
        try:
            op, ops, sz = read_insn(buf, pc)
        except DecodeError:
            pc += 1
            continue
        if any(covered[pc:pc + sz]):     # would overlap known code -- resync
            pc += 1
            continue
        insns[pc] = (op, ops, sz)
        for k in range(pc, min(pc + sz, len(buf))):
            covered[k] = 1
        pc += sz
    return insns, gaps(covered)


def unpack_text(raw):
    """Decode the 6-bit packed text the type-0x80 operand carries inline.

    State machine from unit 045:0x1186 -- four 6-bit codes per three bytes:
        s1: cur >> 2
        s2: ((prev << 6) + (cur >> 2)) >> 2
        s3: ((prev << 4) + (cur >> 4)) >> 2
        s4: cur & 0x3F                      (consumes no new byte)
    Each code becomes a character via unit 045:0x06E3, which is plain 6-bit
    ASCII -- `code > 0x1F ? code : code + 0x40`, i.e. the printable range
    0x20-0x5F packed into six bits (space/digits/punctuation keep their value;
    0x00-0x1F become '@' and 'A'-'Z'). A zero code terminates the string."""
    out = []
    state = 1
    prev = 0
    i = 0
    while i < len(raw):
        cur = raw[i]
        code = None
        if state == 1:
            code = (cur >> 2) & 0x3F
        elif state == 2:
            code = (((prev << 6) + (cur >> 2)) >> 2) & 0x3F
        elif state == 3:
            code = (((prev << 4) + (cur >> 4)) >> 2) & 0x3F
        if code is not None:
            if code == 0:
                return ''.join(out)
            out.append(chr(code if code > 0x1F else code + 0x40))
        prev = cur
        i += 1
        state = state + 1 if state < 4 else 1
        if state == 4:                      # emits without consuming a byte
            code = cur & 0x3F
            if code == 0:
                return ''.join(out)
            out.append(chr(code if code > 0x1F else code + 0x40))
            state = 1
    return ''.join(out)


def var_name(addr):
    """A readable name for an ECL address: the special game-state variables by
    name, the four wrap-biased regions by index, anything else raw."""
    if addr in SPECIAL_VARS:
        return f'{addr:04X}<{SPECIAL_VARS[addr]}>'
    for i, (lo, hi, _how) in enumerate(REGIONS):
        if lo <= addr < hi:
            if i == 3:
                return f'code+{addr - PC_BASE:04x}'
            return f'r{i}[{(addr - lo) // 1:#x}]'
    return f'{addr:04X}'


def fmt_operand(t, v, e, text):
    if t == 0x80:
        return f'"{text}"'
    if t == 0x00:
        return f'#{v:#04x}'
    if e is None:
        return f'?{t:02x}:{v:02x}'
    return f'{var_name((e << 8) | v)}'


def payload(fname, block_id):
    d, base, blks = dax.blocks(os.path.join(EXPANDED, fname))
    for bid, off, unp, pak, raw in blks:
        if bid == block_id:
            return dax.unrle(raw, unp)[2:]      # skip the 2-byte header
    raise SystemExit(f'{fname}: no block 0x{block_id:02x}')


def each_block():
    for k in range(1, 9):
        fname = f'ECL{k}.DAX'
        d, base, blks = dax.blocks(os.path.join(EXPANDED, fname))
        for bid, off, unp, pak, raw in blks:
            yield fname, bid, dax.unrle(raw, unp)[2:]


def disassemble(buf):
    insns, _cov = walk(buf)
    reached = set(insns)
    insns, islands = sweep(buf, insns)
    entries = header(buf)
    for i, e in enumerate(entries):
        print(f'; entry {i}  DS:{0x4944 + 2 * i:04X}  ->  +{e:04x}')
    isl = {s: n for s, n in islands}
    for off in sorted(set(insns) | set(isl)):
        if off in isl:
            print(f'+{off:04x}  ;; {isl[off]} bytes not reached as code')
            continue
        op, ops, sz = insns[off]
        parts = ' '.join(fmt_operand(*o) for o in ops)
        name = NAMES.get(op, '')
        tag = '' if off in reached else '   ; swept, not reached from an entry'
        print(f'+{off:04x}  {op:02x} {name:<8}{parts}{tag}')


def validate():
    """Coverage of the whole corpus, and the header check."""
    hdr_ok = 0
    tot = w_cov = s_cov = 0
    n_isl = isl_bytes = 0
    rows = []
    for fname, bid, p in each_block():
        try:
            header(p)
            hdr_ok += 1
        except DecodeError as exc:
            print(f'  {fname} 0x{bid:02x}: header FAILED -- {exc}')
            continue
        insns, cov = walk(p)
        wc = sum(cov) - HDR_SIZE
        islands = gaps(cov)
        insns2, islands2 = sweep(p, insns)
        sc = len(p) - HDR_SIZE - sum(n for _s, n in islands2)
        rows.append((fname, bid, len(p) - HDR_SIZE, wc, sc, len(islands)))
        tot += len(p) - HDR_SIZE
        w_cov += wc
        s_cov += sc
        n_isl += len(islands)
        isl_bytes += sum(n for _s, n in islands)
    print(f'20-byte 5-entry header parses     : {hdr_ok}/{len(rows)} blocks')
    print(f'decoded by control flow alone     : {w_cov:6d}/{tot} '
          f'= {w_cov / tot * 100:.1f}% of payload')
    print(f'  left over: {isl_bytes} B in {n_isl} islands '
          f'({isl_bytes / tot * 100:.1f}%) -- mostly trailing data tables')
    print(f'+ heuristic linear resync (guesses): {s_cov:6d}/{tot} '
          f'= {s_cov / tot * 100:.1f}%')
    worst = sorted(rows, key=lambda r: r[3] / r[2])[:5]
    print('lowest control-flow coverage:')
    for f, b, n, wc, sc, ni in worst:
        print(f'  {f} 0x{b:02x}  {wc}/{n} = {wc / n * 100:.1f}%  '
              f'({ni} islands)')


def gaps(covered):
    """[(start, length)] of the byte runs `covered` leaves unset, past the
    header."""
    out = []
    i = HDR_SIZE
    while i < len(covered):
        if covered[i]:
            i += 1
            continue
        j = i
        while j < len(covered) and not covered[j]:
            j += 1
        out.append((i, j - i))
        i = j
    return out


_PRINTABLE = set(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?\'"-:;()/&$@#*+[]')


def all_text():
    """Every inline string in the corpus, from real decoded instructions."""
    seen = {}
    for fname, bid, p in each_block():
        try:
            insns, _cov = walk(p)      # control flow only: `sweep` guesses
        except DecodeError:
            continue
        for off in sorted(insns):
            op, ops, sz = insns[off]
            for t, v, e, x in ops:
                if t == 0x80 and x:
                    seen.setdefault(x, (fname, bid, off, op))
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', help='e.g. ECL1.DAX')
    ap.add_argument('block', nargs='?', help='block id, e.g. 0x12')
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--text', action='store_true',
                    help='dump every inline string in the corpus')
    args = ap.parse_args()
    if args.text:
        seen = all_text()
        for s, (fname, bid, i, op) in sorted(seen.items(),
                                             key=lambda kv: kv[1]):
            print(f'{fname} 0x{bid:02x} +{i:<6d} {op:02x} {s}')
        print(f'\n{len(seen)} distinct strings, '
              f'{sum(len(s) for s in seen)} characters', file=sys.stderr)
        return
    if args.validate or not args.file:
        validate()
        return
    disassemble(payload(args.file, int(args.block, 0)))


if __name__ == '__main__':
    main()
