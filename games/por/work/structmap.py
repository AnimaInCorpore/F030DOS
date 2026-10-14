#!/usr/bin/env python3
"""Which struct offsets does the overlay code actually use, and where?

Phase-3 work on a record format stalls on the same question every time: of the
~285 bytes in a character record or 63 in an item, which offsets does the game
touch at all, and which routine should be read first? This counts every
`ES:[DI + disp]` in the disassembly and reports the busiest displacements with
the units that use them, so the next field to chase is the one with the most
weight behind it rather than the next one along.

It found `+0x108` that way -- the most-referenced offset in the corpus (230
references, 13 units) and, until then, completely unknown
(`analysis/data-formats.md` §The `+0x108` per-combat state block).

**A caveat that matters.** The displacement alone does not say which structure
is being indexed: item records, character records, the 22 B combat block and
the ECL operand tables all appear in the same tally, and some `+disp` sites are
an *array base* inside a record rather than a scalar field (`+0x17` is one --
see the same file). Treat a row as "this offset is worth reading", never as
"this field belongs to that record".

Usage:
    python3 work/structmap.py                # busiest offsets, all units
    python3 work/structmap.py 0x108          # every site for one offset
    python3 work/structmap.py --unit 0BE     # restrict to one unit
"""
import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LISTING = os.path.join(HERE, 'game16.txt')
LINE = re.compile(r'^([0-9A-F]{3}):([0-9A-F]{4})  [0-9a-f]+\s+(.*)$')
DISP = re.compile(r'es:\[di \+ (0x[0-9a-f]+)\]')

# Offsets this project has already read, so the report shows what is left.
KNOWN = {
    0x10: 'char STR', 0x11: 'char INT', 0x12: 'char WIS', 0x13: 'char DEX',
    0x14: 'char CON', 0x15: 'char CHA', 0x16: 'char STR%',
    0x2A: 'item next ptr', 0x2E: 'item type -> ITEMS', 0x30: 'char age?',
    0x32: 'item magic value (signed) / char MAX HP', 0x39: 'item quantity',
    0x84: 'char NPC bit + 7-bit value', 0x96: 'char class levels',
    0xAC: 'char exp?', 0xC8: 'char inventory head', 0xCC: 'char weapon?',
    0xD4: 'char armor?', 0x7F: 'char 9 B list head',
    0x104: 'char next participant', 0x108: 'char combat block (22 B)',
    0x11B: 'char CURRENT HP',
    0x10C: 'char status?', 0x10D: 'char runtime bool (1 on disk)',
    0x10E: 'char mode byte',
}


def scan(unit=None):
    count = collections.Counter()
    units = collections.defaultdict(set)
    sites = collections.defaultdict(list)
    for ln in open(LISTING):
        m = LINE.match(ln)
        if not m:
            continue
        u, addr, text = m.group(1), m.group(2), m.group(3).rstrip()
        if unit and u != unit:
            continue
        for mo in DISP.finditer(text):
            d = int(mo.group(1), 16)
            count[d] += 1
            units[d].add(u)
            sites[d].append(f'{u}:{addr}  {text}')
    return count, units, sites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('offset', nargs='?', help='e.g. 0x108')
    ap.add_argument('--unit', help='restrict to one unit, e.g. 0BE')
    ap.add_argument('--top', type=int, default=30)
    args = ap.parse_args()
    count, units, sites = scan(args.unit.upper() if args.unit else None)
    if args.offset:
        d = int(args.offset, 16)
        print(f'+0x{d:03X}: {count[d]} references in {len(units[d])} units'
              + (f'  -- {KNOWN[d]}' if d in KNOWN else '  -- not yet read'))
        ops = collections.Counter(s.split()[1] for s in sites[d])
        print('  opcode mix:', dict(ops))
        for s in sites[d][:40]:
            print('   ', s)
        if len(sites[d]) > 40:
            print(f'    ... {len(sites[d]) - 40} more')
        return
    print(f'{"offset":>7} {"refs":>5} {"units":>5}  meaning')
    for d, n in count.most_common(args.top):
        print(f'  +0x{d:03X} {n:5d} {len(units[d]):5d}  '
              f'{KNOWN.get(d, "")}')
    unread = [(d, n) for d, n in count.most_common() if d not in KNOWN]
    print(f'\nbusiest offsets with no reading yet: '
          + ', '.join(f'+0x{d:03X}({n})' for d, n in unread[:10]))


if __name__ == '__main__':
    main()
