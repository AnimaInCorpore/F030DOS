#!/usr/bin/env python3
"""Map every 4 KB page of PANZER.EXE (LE data pages and tail) into a RAM dump.

Unlike probe_memory.py, which votes one file->RAM delta, this reports a delta
per page and tolerates loader fixups: a page is scored by the fraction of equal
bytes at each candidate placement, so a fully resident page whose 32-bit
operands were rebased still scores high.  Two resident copies of a page are
reported as two placements, not resolved into one.

    python3 work/probe_memory.py --seconds 12 --ram-size 0x1000000 \
        --output work/qemu_out/pg_ram16.bin
    python3 work/probe_ram_map.py work/qemu_out/pg_ram16.bin
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "game" / "EXE" / "PANZER.EXE"
LE_DATA_PAGES = 0x23E00      # file offset of LE page 1
PAGE = 0x1000
LE_PAGES = 111
LE_DECLARED_END = 0x9283D
WIN = 16
MIN_DIVERSE = 6


def windows(exe: bytes, start: int, end: int):
    """Yield (offset_in_block, bytes) windows that are diverse and file-unique."""
    for off in range(0, end - start - WIN + 1, 0x40):
        w = exe[start + off:start + off + WIN]
        if len(set(w)) < MIN_DIVERSE:
            continue
        if exe.find(w) != start + off or exe.find(w, start + off + 1) >= 0:
            continue
        yield off, w


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ram", type=Path)
    ap.add_argument("--min-score", type=float, default=0.5)
    args = ap.parse_args()

    exe = EXE.read_bytes()
    ram = args.ram.read_bytes()
    ram_arr = np.frombuffer(ram, dtype=np.uint8)

    blocks = []
    for n in range(LE_PAGES):
        start = LE_DATA_PAGES + n * PAGE
        blocks.append((f"LE{n + 1:03d}", start,
                       min(start + PAGE, LE_DECLARED_END)))
    pos = LE_DECLARED_END
    while pos < len(exe):
        blocks.append((f"TAIL@{pos:X}", pos, min(pos + PAGE, len(exe))))
        pos += PAGE

    print(f"{'block':<12} {'file':>8} {'placements (ram: score)'}")
    summary = defaultdict(int)
    for name, start, end in blocks:
        src = np.frombuffer(exe[start:end], dtype=np.uint8)
        cands = set()
        for off, w in windows(exe, start, end):
            i = ram.find(w)
            while i >= 0:
                cands.add(i - off)
                i = ram.find(w, i + 1)
        scored = []
        for c in cands:
            if c < 0 or c + len(src) > len(ram):
                continue
            score = float(np.mean(ram_arr[c:c + len(src)] == src))
            if score >= args.min_score:
                scored.append((score, c))
        scored.sort(reverse=True)
        if not scored:
            summary["absent"] += 1
            print(f"{name:<12} {start:>8X} none")
            continue
        summary["resident"] += 1
        if len(scored) > 1:
            summary["multi"] += 1
        txt = "  ".join(f"{c:X}:{s:.2f}(d={c - start:+X})"
                        for s, c in scored[:3])
        print(f"{name:<12} {start:>8X} {txt}")
    print(dict(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
