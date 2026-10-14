#!/usr/bin/env python3
"""Find stores whose operand size is wider than the BSS slot they write.

The bug this exists for: `move.l d1,aspect_row` against an `aspect_row ds.w 1`
wrote two bytes past the slot and zeroed the high word of the next global,
`object_draw_model_bank`.  Nothing about the source looks wrong at the call
site, and the corruption only shows up as a wrong pointer several routines
later - it cost several sessions to localise by hand.

N/A - target artefact: a port-side consistency check, not a DOS routine.
"""
import re
import sys
from pathlib import Path

SIZES = {'b': 1, 'w': 2, 'l': 4}
UNIT = {'ds.b': 1, 'ds.w': 2, 'ds.l': 4, 'dc.b': 1, 'dc.w': 2, 'dc.l': 4}

root = Path(__file__).resolve().parent.parent
slots = {}          # name -> (bytes, file, line)

label_re = re.compile(r'^([A-Za-z_.][A-Za-z0-9_.]*)\s*$')
res_re = re.compile(r'^\s+(ds\.[bwl])\s+(\S+)')
store_re = re.compile(
    r'^\s+(move|clr|movem|add|sub|and|or|eor|not|neg|tst|cmp)[a-z]*\.([bwl])\s+(.*)$')

for path in sorted((root / 'src').rglob('*.s')):
    pending = None
    for n, raw in enumerate(path.read_text(errors='replace').splitlines(), 1):
        line = raw.split(';')[0].rstrip()
        if not line:
            continue
        m = label_re.match(line)
        if m:
            pending = (m.group(1), n)
            continue
        m = res_re.match(line)
        if m and pending:
            count = m.group(2)
            try:
                count = int(count, 0)
            except ValueError:
                count = None
            if count is not None:
                slots[pending[0]] = (UNIT[m.group(1)] * count, path.name, pending[1])
            pending = None
            continue
        pending = None

bad = []
for path in sorted((root / 'src').rglob('*.s')):
    for n, raw in enumerate(path.read_text(errors='replace').splitlines(), 1):
        line = raw.split(';')[0].rstrip()
        m = store_re.match(line)
        if not m:
            continue
        size = SIZES[m.group(2)]
        # Destination is the last comma-separated operand at depth 0.
        ops, depth, cur = [], 0, ''
        for ch in m.group(3):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            if ch == ',' and depth == 0:
                ops.append(cur.strip())
                cur = ''
            else:
                cur += ch
        ops.append(cur.strip())
        dest = ops[-1]
        if not label_re.match(dest):
            continue
        slot = slots.get(dest)
        if slot and size > slot[0]:
            bad.append((path.name, n, line.strip(), dest, slot))

for f, n, line, dest, slot in bad:
    print(f'{f}:{n}: {line}')
    print(f'    {dest} is {slot[0]} byte(s), declared at {slot[1]}:{slot[2]}')

print(f'{len(slots)} reservations checked, {len(bad)} oversized store(s)')
sys.exit(1 if bad else 0)
