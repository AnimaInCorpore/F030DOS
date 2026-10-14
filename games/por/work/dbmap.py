#!/usr/bin/env python3
"""Classify every `db` byte the reassembly still emits, per overlay unit.

`make reasm` proves the disassembly byte-exact and reports what fraction of
each unit came out as real instructions; the rest is `db`. That residue is the
phase-3 worklist (`AGENTS.md` §Next steps item 3) -- but it is not all
*unexplained*. Every unit starts with a header and a thunk table, Turbo Pascal
string constants live in the code segment, and `case` statements leave offset
tables behind. This separates the residue into what is already accounted for
and what genuinely is not, so the worklist is the second number, not the first.

Classification, in the order applied:
  header  -- [0, 0x20 + 5*entry_count), the unit header and thunk table
             (`work/resolve_calls.py`, `analysis/executables.md`)
  strtab  -- Turbo Pascal `ShortString` constants: a length byte L followed by
             L printable bytes, chained back to back
  demoted -- an instruction the disassembly DID recover, demoted to `db` only
             because NASM re-encodes it differently (`<unit>.forced.json`,
             written by `work/reasm.py`). Recovered code, not residue
  offtab  -- runs of >= 3 u16LE values that are all instruction starts in this
             same unit and not all the same: a `case`/dispatch offset table,
             and therefore also a list of entry points into code the linear
             pass may have missed. Zero is excluded -- offset 0 is a valid
             instruction start, so a run of zero words otherwise reads as a
             perfect table, which is how the first version of this file
             reported six imaginary tables in unit 0B6
  zeros   -- runs of >= 4 zero bytes (alignment/padding)
  unknown -- everything else. This is the real worklist.

Usage:
    python3 work/dbmap.py              # corpus summary
    python3 work/dbmap.py 18A          # one unit, with the unknown runs listed
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REASM = os.path.join(HERE, 'reasm')
OVERLAY = os.path.join(HERE, 'overlay_map.json')

LST = re.compile(r'^\s*\d+ ([0-9A-F]{8}) ([0-9A-F]+)(-?)\s*(.*)$')
PRINTABLE = set(range(0x20, 0x7F)) | {0x0A, 0x0D}


def parse_lst(path):
    """(code, kind) -- the assembled bytes and a per-byte 'i'/'d' flag."""
    size = 0
    spans = []
    kind = None
    for ln in open(path):
        m = LST.match(ln)
        if not m:
            continue
        off, hexb, _cont, src = int(m.group(1), 16), m.group(2), m.group(3), m.group(4)
        src = src.strip()
        if src:                                  # a new source line
            kind = 'd' if src.startswith('db ') or src.startswith('dw ') else 'i'
        if kind is None:
            continue
        data = bytes.fromhex(hexb)
        spans.append((off, data, kind))
        size = max(size, off + len(data))
    code = bytearray(size)
    flag = bytearray(b'?' * size)
    starts = set()
    for off, data, k in spans:
        code[off:off + len(data)] = data
        for i in range(len(data)):
            flag[off + i] = ord(k)
        if k == 'i':
            starts.add(off)
    return bytes(code), flag, starts


def classify(code, flag, starts, hdr_end, demoted):
    """offset -> category, for every byte flagged 'd'."""
    cat = [None] * len(code)
    isdb = [f == ord('d') for f in flag]
    for i in range(min(hdr_end, len(code))):
        if isdb[i]:
            cat[i] = 'header'
    for off, size in demoted.items():
        for j in range(off, min(off + size, len(code))):
            if isdb[j] and not cat[j]:
                cat[j] = 'demoted'
    # Pascal ShortString chains
    i = hdr_end
    while i < len(code):
        if not isdb[i] or cat[i]:
            i += 1
            continue
        n = code[i]
        if 1 <= n <= 60 and i + 1 + n <= len(code):
            body = code[i + 1:i + 1 + n]
            if all(b in PRINTABLE for b in body) and all(
                    isdb[j] and not cat[j] for j in range(i, i + 1 + n)):
                for j in range(i, i + 1 + n):
                    cat[j] = 'strtab'
                i += 1 + n
                continue
        i += 1
    # u16 offset tables pointing at instruction starts in this unit
    i = hdr_end
    while i + 1 < len(code):
        if not isdb[i] or cat[i]:
            i += 1
            continue
        j, hits = i, []
        while (j + 1 < len(code) and isdb[j] and isdb[j + 1] and not cat[j]
               and not cat[j + 1]):
            v = code[j] | (code[j + 1] << 8)
            if v == 0 or v not in starts:
                break
            hits.append(v)
            j += 2
        if len(hits) >= 3 and len(set(hits)) >= 3:
            for k in range(i, j):
                cat[k] = 'offtab'
            i = j
        else:
            i += 1
    # zero padding
    i = hdr_end
    while i < len(code):
        if not isdb[i] or cat[i] or code[i]:
            i += 1
            continue
        j = i
        while j < len(code) and isdb[j] and not cat[j] and code[j] == 0:
            j += 1
        if j - i >= 4:
            for k in range(i, j):
                cat[k] = 'zeros'
        i = j
    for i in range(len(code)):
        if isdb[i] and not cat[i]:
            cat[i] = 'unknown'
    return cat


def runs(cat, want):
    out, i = [], 0
    while i < len(cat):
        if cat[i] != want:
            i += 1
            continue
        j = i
        while j < len(cat) and cat[j] == want:
            j += 1
        out.append((i, j - i))
        i = j
    return out


def main():
    units = {u['seg']: u for u in json.load(open(OVERLAY))}
    only = int(sys.argv[1], 16) if len(sys.argv) > 1 else None
    order = ('header', 'demoted', 'strtab', 'offtab', 'zeros', 'unknown')
    tot = {k: 0 for k in order}
    code_total = insn_total = 0
    rows = []
    for seg in sorted(units):
        path = os.path.join(REASM, f'unit{seg:03X}.lst')
        if not os.path.exists(path):
            continue
        code, flag, starts = parse_lst(path)
        hdr_end = 0x20 + 5 * units[seg]['entry_count']
        fp = os.path.join(REASM, f'unit{seg:03X}.forced.json')
        demoted = ({int(k, 16): v for k, v in json.load(open(fp)).items()}
                   if os.path.exists(fp) else {})
        cat = classify(code, flag, starts, hdr_end, demoted)
        n = {k: sum(1 for c in cat if c == k) for k in tot}
        for k in tot:
            tot[k] += n[k]
        code_total += len(code)
        insn_total += sum(1 for f in flag if f == ord('i'))
        rows.append((seg, len(code), n))
        if only is not None and seg == only:
            print(f'unit {seg:03X}: {len(code)} B, header ends 0x{hdr_end:X}')
            for k in order:
                print(f'  {k:8s} {n[k]:6d} B')
            print('  offset tables (each entry is a real code entry point):')
            for off, ln in runs(cat, 'offtab'):
                vals = [code[off + i] | (code[off + i + 1] << 8)
                        for i in range(0, ln, 2)]
                print(f'    +{off:04X} x{len(vals):<3d} '
                      + ' '.join(f'{v:04X}' for v in vals[:12])
                      + (' ...' if len(vals) > 12 else ''))
            print('  unknown runs, largest first:')
            for off, ln in sorted(runs(cat, 'unknown'), key=lambda r: -r[1])[:15]:
                print(f'    +{off:04X} {ln:5d} B  '
                      + ' '.join(f'{b:02x}' for b in code[off:off + min(ln, 16)]))
            return
    db_total = sum(tot.values())
    print(f'overlay code            {code_total:7d} B')
    print(f'  real instructions     {insn_total:7d} B'
          f'  ({insn_total / code_total * 100:.1f} %)')
    print(f'  db residue            {db_total:7d} B'
          f'  ({db_total / code_total * 100:.1f} %)')
    for k in order:
        print(f'    {k:8s}            {tot[k]:7d} B'
              f'  ({tot[k] / db_total * 100:5.1f} % of the residue)')
    print(f'\nreal worklist: {tot["unknown"]} B unexplained '
          f'({tot["unknown"] / code_total * 100:.1f} % of overlay code)')
    worst = sorted(rows, key=lambda r: -r[2]['unknown'])[:8]
    print('units with the most unexplained bytes:')
    for seg, n, d in worst:
        print(f'  unit {seg:03X}  {d["unknown"]:6d} B of {n}')


if __name__ == '__main__':
    main()
