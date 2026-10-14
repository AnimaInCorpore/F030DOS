#!/usr/bin/env python3
"""Emit --known-data arguments for disasm.py from the annotation store.

Every table, data, string and pad row with an established extent becomes a
barrier, so the descent stops at it instead of walking through and inflating
coverage.

pad rows count for the same reason the others do, and more plainly: a run
recorded as this linker's 0x80 fill is established as not being code, so a
descent that walks into one has gone wrong and every instruction it decodes
there is false coverage. They were left out until the dma_len_word row was
split and the 12 fill bytes behind it became a pad row, which took them out
from behind the barrier and made the omission visible.
Addresses are passed in the notation disasm.py prints; it converts them to
image offsets itself.

    python3 tools/re/disasm.py ... $(python3 tools/re/known-data-args.py)
"""
import re
import sys

def main() -> int:
    args = []
    path = sys.argv[1] if len(sys.argv) > 1 else "re/annotations.txt"
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^(table|data|string|pad)\s+([0-9A-Fa-f]{8})\s+(\S+)\s+(\S+)", line)
        if not m or m.group(3) == "-":
            continue
        name = m.group(4)
        args.append(f"--known-data {int(m.group(2), 16):x}:{int(m.group(3), 16):x}={name}")
    print(" ".join(args))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
