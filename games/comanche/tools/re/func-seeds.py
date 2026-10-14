#!/usr/bin/env python3
"""Emit --seed arguments for disasm.py from the annotation store's func rows.

A routine the store has identified is a known entry point, and some of them
cannot be reached any other way. span_writer_unrolled is the clearest case:
1,023 bytes entered only through `lea ebx,[ebx*4+00006BF0] / jmp ebx`, a
computed target no scan can resolve, with no direct call anywhere. One seed at
its head walks the whole run.

Only settled rows are emitted. A `?func` records an approximate entry, and a
descent seeded a byte or two off decodes plausible nonsense - the same failure
that put an invented consumer for krl_input_buffer on record earlier.

    python3 tools/re/disasm.py ... $(python3 tools/re/func-seeds.py)
"""
import re
import sys

ROW = re.compile(r"^(\??)func\s+([0-9A-Fa-f]{8})\s+(\S+)\s+(\S+)")


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "re/annotations.txt"
    seeds = []
    for line in open(path, encoding="utf-8"):
        m = ROW.match(line)
        if not m or m.group(1):          # skip candidates
            continue
        seeds.append(f"--seed {int(m.group(2), 16):x}")
    print(" ".join(seeds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
