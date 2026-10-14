#!/usr/bin/env python3
"""Print one ECL opcode handler's disassembly with its far calls resolved.

The handlers live in overlay unit `020` and are reached from the dispatcher at
`020:32DF` (map: `HANDLER` in `work/ecl.py`). Reading them raw is awkward
because every interesting call is a `CALLF <unit>:<thunk offset>` that has to
be run through the unit's thunk table at `+0x20`, 5 bytes per slot, before it
names a routine -- see `work/resolve_calls.py` and
`analysis/executables.md` §Units `045` and `020`. This does that inline so a
handler reads as a call graph instead of a wall of magic numbers.

Usage:
    python3 work/eclops.py 09          # handler for opcode 0x09
    python3 work/eclops.py 09 --calls  # just the resolved call list
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ecl

LISTING = os.path.join(HERE, 'game16.txt')
OVERLAY = os.path.join(HERE, 'overlay_map.json')

# Routines named while reading the interpreter; see analysis/data-formats.md
# §`ECL*.DAX` and analysis/executables.md §Units `045` and `020`.
KNOWN = {
    (0x045, 0x0000): 'entry_0000(n) decode n operands',
    (0x045, 0x013F): 'entry_013F(i) evaluate operand i',
    (0x045, 0x01C8): 'block init (PC=0x9900, read 5-entry header)',
    (0x045, 0x0353): 'ECL loader',
    (0x045, 0x06BE): 'addr = (extra<<8)+value',
    (0x045, 0x06E3): '6-bit code -> ASCII',
    (0x045, 0x070B): 'classify address -> region 0..4',
    (0x045, 0x0C93): 'STORE value at ECL address',
    (0x045, 0x0E2E): 'LOAD value from ECL address',
    (0x045, 0x0F81): 'STORE string at ECL address',
    (0x045, 0x1186): 'read inline 6-bit packed text',
    (0x045, 0x1853): 'compare strings -> the six flags',
    (0x045, 0x1929): 'compare numbers -> the six flags',
    (0x045, 0x1991): 'GOSUB: push PC, jump',
    (0x020, 0x0B1A): 'operand-count classifier (skip path only)',
    (0x020, 0x32DF): 'opcode dispatcher',
    (0x020, 0x35DB): 'execute loop',
}

GLOBALS = {
    0x4390: 'stop-script flag (execute loop exits)',
    0x493F: 'far ptr -> ECL script buffer (7,680 B)',
    0x494E: 'ECL program counter (biased -0x6700)',
    0x6A0B: 'party X', 0x6A0C: 'party Y', 0x6A0D: 'party facing',
    0x6D34: 'ECL var 0x00B1', 0x6D30: 'ECL var 0x00FB', 0x6D32: 'ECL var 0x00FC',
    0x6D36: 'GOSUB stack head',
    0x6D3E: 'flag ==', 0x6D3F: 'flag !=', 0x6D40: 'flag <',
    0x6D41: 'flag >', 0x6D42: 'flag <=', 0x6D43: 'flag >=',
    0x6D45: 'current opcode',
    0x6DCB: 'operand type table', 0x6E0B: 'operand extra table',
    0x6E4B: 'operand value table', 0x6E8E: 'operand string table (256 B stride)',
}


def thunks():
    return {u['seg']: u for u in json.load(open(OVERLAY))}


def resolve(seg, off, by_seg):
    u = by_seg.get(seg)
    if u is None:
        return f'resident {seg:04X}:{off:04X}'
    lo = 0x20
    if lo <= off < lo + 5 * u['entry_count'] and (off - lo) % 5 == 0:
        i = (off - lo) // 5
        t = u['thunks'][i] if i < len(u['thunks']) else None
        if isinstance(t, int) and t != 0xFFFF:
            note = KNOWN.get((seg, t))
            return f'unit {seg:03X}:{t:04X}' + (f'  -- {note}' if note else '')
    return f'unit {seg:03X}:+{off:04X} (not a thunk slot)'


def handler_range(op):
    start = ecl.HANDLER[op]
    others = sorted(set(ecl.HANDLER.values()))
    after = [s for s in others if s > start]
    return start, (after[0] if after else 0x3700)


def listing():
    """offset -> (raw bytes, text) for unit 020, primary decode only.

    game16.txt carries alternate-alignment decodes as well as the real ones
    (they appear under their own `; -- 020:XXXX` labels), so filtering by
    address range alone yields a mix of real instructions and junk. Walking
    the chain by instruction length keeps only the decode that is actually
    reachable, which is what a handler read has to be based on."""
    out = {}
    for ln in open(LISTING):
        m = re.match(r'^020:([0-9A-F]{4})  ([0-9a-f]+)\s+(.*)$', ln)
        if m:
            out.setdefault(int(m.group(1), 16), (m.group(2), m.group(3).rstrip()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('opcode')
    ap.add_argument('--calls', action='store_true')
    args = ap.parse_args()
    op = int(args.opcode, 16)
    lo, hi = handler_range(op)
    by_seg = thunks()
    code = listing()
    shared = [f'{o:#04x}' for o, h in ecl.HANDLER.items()
              if h == ecl.HANDLER[op] and o != op]
    print(f'; opcode {op:#04x} {ecl.NAMES.get(op, "")} -> handler 020:{lo:04X}'
          f'  ({ecl.OPERANDS.get(op, 0)} operands'
          + (f' + N from operand {ecl.VARCOUNT[op]}' if op in ecl.VARCOUNT else '')
          + ')')
    if shared:
        print(f'; shared with {", ".join(shared)}')
    pc = lo
    while pc < hi and pc in code:
        by, tx = code[pc]
        note = ''
        cf = re.match(r'lcall (0x[0-9a-f]+), (0x[0-9a-f]+)', tx)
        if cf:
            note = '   ; ' + resolve(int(cf.group(1), 0), int(cf.group(2), 0), by_seg)
        else:
            g = re.search(r'\[0x([0-9a-f]{4})\]', tx)
            if g and int(g.group(1), 16) in GLOBALS:
                note = '   ; ' + GLOBALS[int(g.group(1), 16)]
        if not args.calls or note:
            print(f'020:{pc:04X}  {tx}{note}')
        pc += len(by) // 2


if __name__ == '__main__':
    main()
