#!/usr/bin/env python3
"""Emit the context block for a function-reading pass, straight from symbols.py.

Two reading rounds showed yield depends heavily on how much the reader already
knows: round 2 was told round 1's findings by hand and produced deeper results,
including the level grid's cell layout. Hand-feeding does not scale and I will
eventually forget something, so this generates the brief from the verified
tier-1 names plus the established globals, and is current by construction.

  python work/agent_brief.py --addrs 0x1234 0x5678 ...   # ready-to-send brief
  python work/agent_brief.py --globals                   # just the fact sheet
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import symbols                                             # noqa: E402

GLOBALS = """- DGROUP is file 0x68E80; a DS-relative [0xNNNN] is file 0x68E80+0xNNNN.
- Image/overlay boundary is file 0x71B80. `lcall SEG:OFF` -> file
  0x2E00+(SEG<<4)+OFF is valid ONLY when the CALL SITE is below 0x71B80.
  Above that is the Borland FBOV overlay pool, whose segment numbers are
  resolved by the overlay manager at load time: such far calls CANNOT be
  mapped to a file offset. Do not compute one, and do not assert a mapping
  from a coincidence of offsets.
- Objects: 1024 records. Index 0..255 -> 27-byte records at far ptr [0x2578];
  256..1023 -> 8-byte records at [0x25a6]. A reference is a 10-bit index in
  bits 6..15 of a word (`shr 6; and 0x3ff`). `mov dx,0x1b`+`imul` indexes the
  27-byte array. Word 0 bits 0..8 = item id (512 types, COMOBJ.DAT; property
  records are 11 bytes at 0x6b64 + id*11). Current object far ptr [0x2246].
  Byte +9 coarse angle, word +0x0b goal/target, byte +0x15 anim state.
- Level: 64x64 grid of 4-byte cells at far ptr [0x188c]. Cell byte 0 bits 0-3
  tile type (10 types), bits 4-7 floor height (15 = solid), byte 1 bits 2-5
  floor texture, byte 2 bits 0-5 wall texture.
- Conversation VM: memory [0x4704], stack [0x46fc], fn-ptr array [0x470e],
  code [0x471e], IP [0x471a], SP [0x46fa], frame [0x4726].
- Graphics: segment 0x0085 is the blitter (ES=0xA000). Its far entries save
  SS:SP to cs:[0x43f0]/[0x43f2] and switch to stack 0x372c:0x4fa8. Clip window
  [0x3df4],[0x3df6],[0x3df8],[0x3dfa]. 16-byte sprite records in segment
  0x5f1c: flag +0, x +2, y +4, w +5, h +7, layer +9, shape +0x0b.
- Cursor: hide depth [0x26c], drawn flag [0x26e], position [0x268]/[0x26a],
  extents [0x2300],[0x2302],[0x2384],[0x238e], id stack [0x23be] via [0x282].
- EMS handle [0x22c0]. Assets live in EMS, not conventional memory.
- Filenames with numbers are built in OCTAL (3-bit digit groups): CUTS\\csXXX
  and uwrNN.xmi both do it, so no filename digit exceeds 7.
- INT 21h DOS, INT 67h EMS, INT 33h mouse, INT 10h BIOS video, INT 3Fh overlay."""

RULES = """RULES (these outrank coverage):
- Name ONLY from evidence quotable as a specific instruction with its address.
- "unknown" is a good answer. A plausible guess is worse than nothing.
- Do NOT assert an address mapping you have not computed. If a far call comes
  from the overlay pool, say so and stop; matching offsets are a hint, not a
  derivation.
- Don't infer purpose from size, position or neighbouring code alone.
- Prefer descriptive over interpretive unless you can cite the link."""

OUTPUT = """OUTPUT per address, nothing else:
  ADDR: 0x......
  NAME: <snake_case or "unknown">
  EVIDENCE: <the decisive instruction(s) with addresses>
  BEHAVIOUR: <1-2 sentences, mechanical>
Be terse; your reply is data."""


def known():
    rows = [(o, n) for o, n, k, _w in sorted(symbols.TIER1) if k == "code"]
    out = ["Already identified here (cite these when a target calls one):"]
    for o, n in rows:
        out.append(f"  {o:#08x}  {n}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addrs", nargs="*", default=[])
    ap.add_argument("--globals", action="store_true")
    a = ap.parse_args()
    if a.globals:
        return print(GLOBALS)
    print("Reverse-engineer a 1993 DOS game binary, 16-bit x86 real mode.\n")
    print("FILE: /Users/saschaspringer/Work/F030Underworld2/work/extracted/D3/UW2.EXE")
    print("Addresses are RAW FILE OFFSETS. Disassemble with capstone CS_MODE_16;")
    print("near call/jmp targets it prints are already correct file offsets.")
    print("Decompiled C is available per function:")
    print("    python3 work/decomp.py 0x<file_offset>")
    print("It prints a QUALITY line first. Measured over all 2,231 functions,")
    print("63% are clean, 25% carry a Ghidra warning, 6% contain bad-instruction")
    print("data and 18% are drowned in `undefined2`. If QUALITY says BAD or POOR,")
    print("do not trust the C -- read the instructions with capstone instead.")
    print("Either way VERIFY anything load-bearing against the instructions.\n")
    if a.addrs:
        print("ANALYSE: " + ", ".join(a.addrs) + "\n")
    print("Established facts (prior verified work on this same binary):")
    print(GLOBALS + "\n")
    print(known() + "\n")
    print(RULES + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
