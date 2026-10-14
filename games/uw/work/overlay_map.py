#!/usr/bin/env python3
r"""The FBOV overlay map of UW.EXE: which pool bytes belong to which unit.

Static half -- read out of the binary, not guessed:

  * `FBOV` header at file 0x66B30 -> `exeinfo` = 0x5D860 is a **segment table
    with exactly `segnum` = 159 entries** (it ends at 0x5DD58, where the
    `uwedit.exe` string starts).  Row = `{u16 seg, u16 size_bytes, u16 type,
    u16 flags}`; `seg` is a raw (file-relative) segment that the DOS loader
    relocates by the load segment, `size_bytes/16` chains to the next row.
  * **`type == 3` marks an overlaid segment: 64 of them**, tiling file
    0x5DD90..0x5F2E4 -- exactly the region that holds the `INT 3Fh` thunks.
    Each is a *stub*: a 32-byte header followed by `nent` 5-byte thunks
    (`CD 3F` + u16 + pad), and `0x20 + 5*nent == size_bytes` for all 64.
  * The stub header carries the map:

        +0x00 u32  `CD 3F 00 00`   the stub's own INT 3Fh entry
        +0x04 u32  pool offset     relative to the pool's code start 0x66B40;
                                   the manager adds that base at load time,
                                   so at runtime the field is a file offset
        +0x08 u16  code size
        +0x0A u16  fixup-table size (u16 offsets, descending, 0-terminated)
        +0x0C u16  entry-point count = number of thunks in this stub
        +0x0E..   runtime-only: stub linked list, resident segment, manager
                  callback -- zero on disk

Dynamic half -- the same map, measured (see analysis/qemu-boot.md for the
harness).  With `--int21` the overlay manager's own DOS reads are matched
against the table: every load is one unit read whole, `len == code + fixups`
from `0x66B40 + pool offset`.  With `--coverage` (the x86trace overlay fold)
the bytes that actually executed are attributed per unit.

    python work/overlay_map.py
    python work/overlay_map.py --int21 work/trace/uw.int21 \
                               --coverage work/trace/uw_pool.coverage
"""
import argparse
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'work', 'expanded', 'UW.EXE')
HDRSZ = 0x3200                      # e_cparhdr * 16; file = 0x3200 + seg*16
FBOV = 0x66B30                      # overlay pool header
POOL = FBOV + 0x10                  # first overlay unit
SEGTAB = 0x5D860                    # = FBOV header's exeinfo field
TYPE_OVERLAY = 3


def segment_table(d):
    """The 159 rows, verified against the FBOV header rather than assumed."""
    magic, ovrsize, exeinfo, segnum = struct.unpack_from('<4sIII', d, FBOV)
    if magic != b'FBOV':
        sys.exit('no FBOV pool at 0x%X' % FBOV)
    if exeinfo != SEGTAB:
        sys.exit('exeinfo 0x%X is not the expected segment table' % exeinfo)
    if ovrsize != len(d) - POOL:
        sys.exit('ovrsize 0x%X != pool payload 0x%X' % (ovrsize, len(d) - POOL))
    return [struct.unpack_from('<4H', d, exeinfo + 8 * i) for i in range(segnum)]


def units(d, rows):
    """One record per overlaid segment, in pool order."""
    out = []
    for i, (seg, size, typ, flags) in enumerate(rows):
        if typ != TYPE_OVERLAY:
            continue
        stub = HDRSZ + (seg << 4)
        off, csize, fsize, nent = struct.unpack_from('<IHHH', d, stub + 4)
        if 0x20 + 5 * nent != size:
            sys.exit('row %d: stub size 0x%X != 0x20 + 5*%d' % (i, size, nent))
        out.append(dict(row=i, seg=seg, stub=stub, off=off, code=csize,
                        fixups=fsize, nent=nent, file=POOL + off))
    out.sort(key=lambda u: u['off'])
    return out


def load_log(path):
    """(seek, buffer, length) of every INT 21h AH=3Fh read in the run."""
    reads, seeks = [], {}
    for ln in open(path):
        if ln.startswith('#'):
            continue
        f = ln.split()
        if len(f) != 7:
            continue
        pc, ax, bx, cx, dx, ds, es = [int(x, 16) for x in f]
        if ax >> 8 == 0x42:                       # LSEEK: remember per handle
            seeks[bx] = (cx << 16) | dx
        elif ax >> 8 == 0x3F:
            reads.append((pc, seeks.get(bx), (ds << 4) + dx, cx))
    return reads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', default=EXE)
    ap.add_argument('--int21', help='x86trace INT 21h log of a run')
    ap.add_argument('--coverage', help='trace_overlay.py --out coverage file')
    ap.add_argument('--all', action='store_true', help='list every unit')
    a = ap.parse_args()

    d = open(a.exe, 'rb').read()
    rows = segment_table(d)
    us = units(d, rows)
    types = {}
    for r in rows:
        types[r[2]] = types.get(r[2], 0) + 1
    print('%s: %d segments, types %s' % (os.path.basename(a.exe), len(rows),
                                         dict(sorted(types.items()))))
    print('overlaid (type %d): %d units, %d entry points, %d B code + %d B fixups'
          % (TYPE_OVERLAY, len(us), sum(u['nent'] for u in us),
             sum(u['code'] for u in us), sum(u['fixups'] for u in us)))
    last = us[-1]
    print('pool 0x%X..0x%X; last unit ends 0x%X (+%d B pad)'
          % (POOL, len(d), last['file'] + last['code'] + last['fixups'],
             len(d) - (last['file'] + last['code'] + last['fixups'])))

    loads = {}
    if a.int21:
        by_file = {u['file']: u for u in us}
        matched = other = 0
        for pc, seek, buf, ln in load_log(a.int21):
            u = by_file.get(seek)
            if u is None or ln != u['code'] + u['fixups']:
                if seek is not None and POOL <= seek < len(d):
                    other += 1                    # a pool read that is not one unit
                continue
            matched += 1
            e = loads.setdefault(u['off'], [0, set(), set()])
            e[0] += 1
            e[1].add(buf)
            e[2].add(pc)
        print('\nINT 21h: %d reads matched a unit exactly (len == code+fixups), '
              '%d other pool reads' % (matched, other))
        print('         %d distinct units loaded, from PC %s'
              % (len(loads), sorted('%05x' % p for e in loads.values() for p in e[2])[:3]))

    cov = open(a.coverage, 'rb').read() if a.coverage else None
    if cov:
        tot = sum(1 for i in range(POOL, len(d)) if cov[i] & 1)
        print('executed pool bytes: %d / %d = %.1f%%'
              % (tot, len(d) - POOL, 100.0 * tot / (len(d) - POOL)))

    print('\n row  seg  stub    unit@file  code  fix  ents%s%s'
          % ('  loads' if loads else '', '  exec' if cov else ''))
    for u in us:
        hot = loads.get(u['off'])
        ex = (sum(1 for i in range(u['file'], u['file'] + u['code'])
                  if cov[i] & 1) if cov else None)
        if not a.all and not hot and not ex:
            continue
        line = ('  %3d %04x  %06x  %06x  %5x %4x %4d'
                % (u['row'], u['seg'], u['stub'], u['file'], u['code'],
                   u['fixups'], u['nent']))
        if loads:
            line += '  %5s' % (hot[0] if hot else '-')
        if cov:
            line += '  %4d (%.0f%%)' % (ex, 100.0 * ex / u['code'] if u['code'] else 0)
        print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
