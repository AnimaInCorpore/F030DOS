#!/usr/bin/env python3
"""Audit DATA/CNV.ARK and recover the conversation VM's builtin table from UW2.EXE.

Three independent things, all measured (analysis/data-formats.md, "CNV.ARK"):

1. --header   The archive container: u16 count + four parallel u32[320] arrays
              (offset / slot-flag / size / size-again), then the record pool.
2. --records  Per-record header byte profile across every populated record.
              Byte +0x0F is the conversation id and equals (slot - 1) for all
              of them, which is the third independent confirmation of the
              CNV-slot <-> STRINGS.PAK-block mapping (see strings_decode.py).
3. --builtins The 51 named builtins the conversation VM registers, read out of
              UW2.EXE's overlay code: a contiguous run of 51 identical
              `PUSH seg / PUSH off / PUSH name / CALLF <thunk>` sequences.
              Names are resolved against DGROUP; the (seg, off) pair is a far
              pointer into the INT 3Fh overlay thunk table.

Nothing here decompresses a record body -- see the doc for exactly how far
that got and what is still unknown.
"""
import argparse
import re
import struct
from collections import Counter
from pathlib import Path

CNV = Path("work/extracted/D4/DATA/CNV.ARK")
EXE = Path("work/extracted/D3/UW2.EXE")
DGROUP = 0x68E80          # AGENTS.md, verified against the Borland CRT banner
SLOTS = 320
REG_CALL = "CALLF 0x0000:3031"   # the routine all 51 registration sites call
DISASM = Path("work/ghidra_export/disasm.txt")


def arrays(d):
    """The four parallel u32[320] header arrays."""
    return [[struct.unpack_from("<I", d, 0x02 + a * 4 * SLOTS + 4 * i)[0]
             for i in range(SLOTS)] for a in range(4)]


def cmd_header(d):
    off, flag, size, size2 = arrays(d)
    nz = [i for i in range(SLOTS) if off[i]]
    hdr_end = 0x02 + 4 * 4 * SLOTS
    print(f"{CNV}: {len(d)} B (0x{len(d):x})")
    print(f"  slots={SLOTS}  populated={len(nz)}  header ends 0x{hdr_end:x}  "
          f"first record 0x{off[nz[0]]:x}  slack={off[nz[0]] - hdr_end} B")
    print(f"  offsets ascending: {[off[i] for i in nz] == sorted(off[i] for i in nz)}")
    print(f"  flag array: value on populated slots = "
          f"{sorted({flag[i] for i in nz})}, on empty slots = "
          f"{sorted({flag[i] for i in range(SLOTS) if not off[i]})}")
    print(f"  size == size2 except slot(s): {[i for i in range(SLOTS) if size[i] != size2[i]]}")
    gaps = {i: (off[nz[k + 1]] if k + 1 < len(nz) else len(d)) - off[i]
            for k, i in enumerate(nz)}
    print(f"  size == gap-to-next-record: {sum(1 for i in nz if size[i] == gaps[i])}/{len(nz)}")
    tot = sum(size[i] for i in nz)
    print(f"  sum(size)={tot}  pool={len(d) - off[nz[0]]}  "
          f"records tile the pool: {tot == len(d) - off[nz[0]]}")


def cmd_records(d):
    off, flag, size, _ = arrays(d)
    nz = [i for i in range(SLOTS) if off[i]]
    print(f"record header byte profile over {len(nz)} records")
    print(f"  {'pos':>4} {'distinct':>8} {'constant':>9}")
    for p in range(0x14):
        vals = {d[off[i] + p] for i in nz}
        const = f"0x{vals.pop():02x}" if len(vals) == 1 else ""
        print(f"  0x{p:02x} {len({d[off[i] + p] for i in nz}):8d} {const:>9}")
    ok = sum(1 for i in nz if d[off[i] + 0x0F] == (i - 1) & 0xFF)
    print(f"\n  byte +0x0F == (slot - 1): {ok}/{len(nz)}   <- conversation id")
    ratio = [struct.unpack_from('<I', d, off[i])[0] / size[i] for i in nz]
    print(f"  u32 @+0x00 > record size for {sum(1 for i in nz if struct.unpack_from('<I', d, off[i])[0] > size[i])}"
          f"/{len(nz)} records, ratio {min(ratio):.2f}..{max(ratio):.2f}")


def dgroup_string(exe, off):
    e = DGROUP + off
    while e < len(exe) and 32 <= exe[e] < 127:
        e += 1
    return exe[DGROUP + off:e].decode("latin1")


def cmd_builtins(exe):
    lines = DISASM.read_text().split("\n")
    regs = []
    for i in range(len(lines) - 3):
        if (lines[i].startswith("PUSH 0x") and lines[i + 1].startswith("PUSH 0x")
                and lines[i + 2].startswith("PUSH 0x")
                and lines[i + 3].startswith(REG_CALL)):
            regs.append((int(lines[i][5:], 16), int(lines[i + 1][5:], 16),
                         int(lines[i + 2][5:], 16)))
    print(f"{len(regs)} builtin registrations (every {REG_CALL} site in the file)\n")
    print(f"  {'seg':>6} {'off':>6}  name")
    for seg, o, name in regs:
        print(f"  {seg:#06x} {o:#06x}  {dgroup_string(exe, name)}")

    thunks = {m.start() for m in re.finditer(re.escape(b"\xcd\x3f"), exe)}
    print(f"\nINT 3Fh thunk table: {len(thunks)} entries, "
          f"0x{min(thunks):X}..0x{max(thunks):X}, "
          f"gap histogram {Counter(b - a for a, b in zip(sorted(thunks), sorted(thunks)[1:])).most_common(3)}")
    offs = [o for _, o, _ in regs]
    print(f"all registration offsets ≡ 2 (mod 5): {all(o % 5 == 2 for o in offs)} "
          f"(the thunk stride)")
    # The load-time segment base is not statically known; fit it and report the
    # fit quality against the null, rather than pretending it is derived.
    sc = [(sum(1 for s, o, _ in regs if 0x2E00 + ((s + b) << 4) + o in thunks), b)
          for b in range(0, 0x8000)]
    best = max(sc)
    print(f"best-fit segment base 0x{best[1]:X}: {best[0]}/{len(regs)} far pointers land "
          f"exactly on a thunk (mean over all 32768 bases: {sum(s for s, _ in sc) / len(sc):.2f})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--header", action="store_true")
    ap.add_argument("--records", action="store_true")
    ap.add_argument("--builtins", action="store_true")
    a = ap.parse_args()
    if not (a.header or a.records or a.builtins):
        a.header = a.records = a.builtins = True
    d = CNV.read_bytes()
    if a.header:
        cmd_header(d)
        print()
    if a.records:
        cmd_records(d)
        print()
    if a.builtins:
        cmd_builtins(EXE.read_bytes())


if __name__ == "__main__":
    main()
