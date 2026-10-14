#!/usr/bin/env python3
r"""What the guest reads from memory the machine does not have.

The sound driver's tick can read through the wild envelope pointer of patch 255
(0x61800004 after the game's start-up relocation, `analysis/functions/sound-driver.md`
section 3.8): the byte it gets decides whether the tick rewrites that channel's pitch. QMP's
`xp` refuses non-RAM addresses, so this puts `mov al, [addr]; ret` in the guest's heap and
CALLS it through the gdbstub like work/trace_sound_writes.py does, for a few addresses:

    python3 work/measure_open_bus.py

On QEMU's `-M pc -m 16` every address above the 16 MB read 0x00 (not 0xFF).

N/A - target artefact: an oracle probe, no DOS routine.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import default_hdd
import trace_sound_writes as t

ADDRESSES = (0x61800000, 0x61800004, 0x61800005, 0x61800010, 0x61801000, 0x01000000,
             0x02000000, 0x04000000, 0x80000000, 0xC0000000, 0xFFFF0000)


def main():
    guest = t.Guest(default_hdd(), adlib=True, qmp_port=4757, gdb_port=4758)
    try:
        d = t.Direct(guest)
        d.prepare()
        code = (guest.peek32(t.HEAP_LOW) + 0x1000) & ~0xF
        for addr in ADDRESSES:
            guest.poke(code, bytes([0xA0]) + struct.pack("<I", addr) + bytes([0xC3]))   # mov al, [addr]; ret
            ret = d.call(code, {"eax": 0x12345600})
            print(f"  [{addr:#010x}] -> {ret & 0xFF:#04x}")
    finally:
        guest.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
