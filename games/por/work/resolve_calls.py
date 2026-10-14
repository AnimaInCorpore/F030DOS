#!/usr/bin/env python3
"""Decode every `CALLF` in a unit's code to its real segment:offset.

Ghidra's disassembly labels any `CALLF` whose segment it doesn't recognise as
`"0x0000:XXXX"`, which looks exactly like a load-time-fixed-up placeholder --
it is not. `XXXX` there is `realSegment * 16 + realOffset`, a flattened
linear address Ghidra derives from bytes that are already fully resolved on
disk. This project spent real effort mistaking that display convention for
an unresolved reference (`analysis/executables.md` §`func_0x000018cf`); this
script reads the actual 4 operand bytes instead, so a Ghidra `func_0x0000XXXX`
name never has to be treated as a dead end again.

For each `CALLF`, the target segment is classified against
`work/overlay_map.json`:
  - matches the *current* unit's own `seg`         -> "self"
  - matches *another* unit's `seg`, offset in       -> "unit XXX thunk #N"
    its thunk-table range (+0x20 .. +0x20+5*count)
  - matches another unit's `seg`, offset outside    -> "unit XXX +offset (not a thunk)"
  - matches nothing in overlay_map.json             -> "resident (START.EXE?)"
    -- for these, also reports the file offset in START.EXE under the
       0x740-paragraph DGROUP-adjacent convention this project has verified
       repeatedly (`analysis/executables.md` §DGROUP base), so the target
       bytes can be read immediately.

Usage:
    python3 work/resolve_calls.py 131            # one unit, by hex seg
    python3 work/resolve_calls.py 131 --context 6  # + a few code bytes at each target
    python3 work/resolve_calls.py --all           # every unit, summary counts only
"""
import argparse
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERLAY = os.path.join(ROOT, 'work', 'overlay_map.json')
GAME_OVR = os.path.join(ROOT, 'work', 'expanded', 'GAME.OVR')
START_EXE = os.path.join(ROOT, 'work', 'expanded', 'START.EXE')


def load_units():
    units = json.load(open(OVERLAY))
    by_seg = {u['seg']: u for u in units}
    return units, by_seg


def classify(seg, off, by_seg):
    u = by_seg.get(seg)
    if u is None:
        return 'resident', None
    thunk_lo = 0x20
    thunk_hi = 0x20 + 5 * u['entry_count']
    if thunk_lo <= off < thunk_hi and (off - thunk_lo) % 5 == 0:
        idx = (off - thunk_lo) // 5
        target = u['thunks'][idx] if idx < len(u['thunks']) else None
        tstr = f'0x{target:04x}' if isinstance(target, int) and target != 65535 else 'FFFF'
        return 'thunk', (idx, tstr)
    return 'nonthunk', None


def resident_file_offset(seg, off):
    """START.EXE file offset for an absolute runtime seg:off. `physical`
    here is really "linear offset into the load image" in this project's own
    convention (work/start16.txt's header: "file offset = linear + 0x3B0"),
    confirmed against 05BB:006E -> linear 0x5C1E and 05BB:1692 -> a real
    Move intrinsic at file offset 0x75F2 = 0x7242 + 0x3B0. An earlier version
    of this function had the +/- backwards; fixed and re-verified against
    both of those samples before trusting it further."""
    linear = seg * 16 + off
    return linear + 0x3B0


def scan_unit(seg, data, units, by_seg, ctx_bytes=0):
    u = by_seg[seg]
    base = u['file_offset']
    end = base + u['code_size']
    region = data[base:end]
    rows = []
    i = 0
    while i < len(region) - 4:
        if region[i] == 0x9a:
            off, tseg = struct.unpack_from('<HH', region, i + 1)
            # This is a byte scan, not a real disassembler: it does not track
            # instruction boundaries, so a 0x9A occurring inside a preceding
            # multi-byte instruction's operand (or in inline data) can be
            # mistaken for a CALLF opcode. Every *verified* real target this
            # project has found sits at a small, plausible segment (units are
            # 0x016..0x198, the resident runtime is 0x05BB, and a few more
            # like 0x026B/0x01D7 have turned up) -- so segments above 0x1000
            # are near-certainly false positives from unaligned scanning, not
            # real far calls. Skip them rather than report noise.
            if tseg > 0x1000 and tseg not in by_seg:
                i += 1
                continue
            kind, info = classify(tseg, off, by_seg)
            row = {'unit_off': i, 'seg': tseg, 'off': off, 'kind': kind}
            if kind == 'thunk':
                row['thunk_idx'], row['thunk_target'] = info
            if kind == 'resident':
                fo = resident_file_offset(tseg, off)
                row['start_exe_offset'] = fo
                if 0 <= fo < len(open(START_EXE, 'rb').read()):
                    pass
            rows.append(row)
            i += 5
        else:
            i += 1
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('seg', nargs='?', help='unit seg in hex, e.g. 131 or 18e')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--context', type=int, default=0,
                    help='print N bytes of the resolved target for resident calls')
    args = ap.parse_args()

    units, by_seg = load_units()
    game = open(GAME_OVR, 'rb').read()
    start = open(START_EXE, 'rb').read()

    if args.all:
        totals = {'self': 0, 'thunk': 0, 'nonthunk': 0, 'resident': 0}
        for u in units:
            rows = scan_unit(u['seg'], game, units, by_seg)
            for r in rows:
                k = 'self' if r['seg'] == u['seg'] else r['kind']
                totals[k] = totals.get(k, 0) + 1
        print(f'{len(units)} units scanned. CALLF classification:')
        for k, v in totals.items():
            print(f'  {k:10s}: {v}')
        return

    if not args.seg:
        sys.exit('usage: resolve_calls.py <seg-hex> | --all')
    seg = int(args.seg, 16)
    if seg not in by_seg:
        sys.exit(f'no unit with seg=0x{seg:x} in {OVERLAY}')

    rows = scan_unit(seg, game, units, by_seg, args.context)
    print(f'unit 0x{seg:x}: {len(rows)} CALLF instructions\n')
    for r in rows:
        kind = 'self' if r['seg'] == seg else r['kind']
        loc = f"unit-rel 0x{r['unit_off']:04x}"
        tgt = f"{r['seg']:04x}:{r['off']:04x}"
        if kind == 'thunk':
            desc = f"-> unit 0x{r['seg']:x} thunk #{r['thunk_idx']} (target {r['thunk_target']})"
        elif kind == 'self':
            desc = '-> self (this unit)'
        elif kind == 'nonthunk':
            desc = f'-> unit 0x{r["seg"]:x}, offset not a thunk slot'
        else:
            fo = r['start_exe_offset']
            if 0 <= fo < len(start) - args.context:
                extra = f'  START.EXE@0x{fo:x}: {start[fo:fo+max(args.context,8)].hex(" ")}' if args.context else f'  START.EXE@0x{fo:x}'
            else:
                fo2 = r['seg'] * 16 + r['off'] + 0x3b0
                extra = f'  (out of START.EXE range; raw file offset if seg is absolute: 0x{fo2:x})'
            desc = f'-> resident{extra}'
        print(f'{loc}: CALLF {tgt}  {desc}')


if __name__ == '__main__':
    main()
