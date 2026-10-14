#!/usr/bin/env python3
"""Emit --seed arguments for the routines the walk never enters.

Some code has no caller a scan can see: an interrupt handler reached through a
vector, or a routine whose only entry is a computed jump. It sits in the image
unreached, and no amount of resolving pointers finds it.

What does find it is the linker. It pads between routines with `2E 8B C0`, a
`cs: mov eax,eax`, so an unreached run that OPENS with that filler is a run
that starts where a routine starts. That is the filter here, and it is a
deliberately narrow one: an unreached run of plain bytes decodes as plausible
instructions just as readily - 01 02 03 04 at 00004C8B disassembles happily as
`add dword ptr [edx],eax` - so decoding cleanly proves nothing on its own and
is used only as a second check after the filler has been found.

    python3 tools/re/disasm.py ... $(python3 tools/re/gap-seeds.py)
"""
import re
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/re"))
import annotations                                          # noqa: E402

IMAGE = ROOT / "re/unpacked/comanche-flat32.bin"
LISTING = ROOT / "re/listings/comanche-flat32.lst"
STORE = ROOT / "re/annotations.txt"
CONTENT = 207648
FILLER = bytes((0x2E, 0x8B, 0xC0))
# Deliberately shorter than disasm.py's list. in, out, cli, iret and hlt are
# junk in application code and are exactly what this generator is looking for:
# the routines with no visible caller are interrupt handlers and device
# drivers. 00001D1B is `push eax / mov al,0x60 / out 0x20,al / cli`, an ISR
# acknowledging the PIC, and the longer list rejected it.
JUNK = {"aaa", "aad", "aam", "aas", "daa", "das", "into", "salc",
        "bound", "arpl"}
INSN = re.compile(r"^([0-9A-F]{8})\s+([0-9a-f]{2,})\s")


def main() -> int:
    image = IMAGE.read_bytes()
    rows, _ = annotations.parse(STORE)

    reached = set()
    for line in LISTING.read_text(errors="replace").splitlines():
        m = INSN.match(line)
        if m:
            a = int(m.group(1), 16)
            reached.update(range(a, a + len(m.group(2)) // 2))

    claimed = set()
    for r in rows:
        if r.kind in ("table", "data", "string", "pad") and r.extent:
            claimed.update(range(r.addr, r.end))

    gap = [i for i in range(CONTENT)
           if i not in reached and i not in claimed and image[i] not in (0, 0x80)]
    if not gap:
        return 0

    runs, start, prev = [], gap[0], gap[0]
    for i in gap[1:]:
        if i > prev + 8:
            runs.append((start, prev - start + 1))
            start = i
        prev = i
    runs.append((start, prev - start + 1))

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    seeds = []
    for addr, length in runs:
        if image[addr:addr + 3] != FILLER:
            continue
        entry = addr
        while image[entry:entry + 3] == FILLER:
            entry += 3
        if entry >= addr + length:
            continue                                # filler all the way down
        decoded = list(md.disasm(image[entry:entry + 64], entry, 8))
        if len(decoded) < 8 or any(i.mnemonic in JUNK for i in decoded):
            continue
        seeds.append(f"--seed {entry:x}")
    print(" ".join(seeds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
