#!/usr/bin/env python3
"""Assemble PALTSR.COM, a DOS TSR that samples the VGA DAC while a program runs
and writes it out by itself.

The palette cannot be read after Comanche exits: returning to text mode resets
the DAC. So this hooks the timer tick and copies the DAC into a resident buffer
about once a second, but ONLY while the BIOS video mode byte at 0040:0049 reads
13h - in text mode it does nothing, so the buffer keeps the last palette the
game had.

It then writes PAL.BIN itself rather than waiting to be run a second time. DOS
is not reentrant, so the write only happens when the InDOS flag is clear, which
is the standard safe window for a TSR. That removes any need to quit the game
or navigate its menus: launch it, let it reach a flight view, and the file is
already on disk.

There is no assembler on this machine, so the bytes are emitted directly and the
result is checked by disassembling it back; see verify().
"""
ORG = 0x100
SIG, TICKS, FLAG, INDOS, BUF, FNAME, RESEND = (
    0x300, 0x304, 0x306, 0x308, 0x310, 0x610, 0x618)
EVERY = 16
PARAS = (RESEND + 15) >> 4


def assemble(labels):
    o = []
    L = {}
    def emit(*b): o.extend(b)
    def w(v): emit(v & 0xFF, (v >> 8) & 0xFF)
    def here(): return ORG + len(o)
    def rel8(target):
        d = labels.get(target, here() + 2) - (here() + 2)
        assert -128 <= d <= 127, (target, d)
        return d & 0xFF

    L['entry'] = here()
    emit(0xB8); w(0x3560); emit(0xCD, 0x21)
    emit(0x8C, 0xC0); emit(0x09, 0xC0)
    emit(0x74, rel8('install'))
    emit(0x26, 0x81, 0x3E); w(SIG); w(0x4150)
    emit(0x75, rel8('install'))
    emit(0x26, 0x81, 0x3E); w(SIG + 2); w(0x584C)
    emit(0x75, rel8('install'))
    emit(0xB8); w(0x4C00); emit(0xCD, 0x21)     # already resident: just exit

    L['install'] = here()
    emit(0xC7, 0x06); w(SIG);     w(0x4150)
    emit(0xC7, 0x06); w(SIG + 2); w(0x584C)
    emit(0xC7, 0x06); w(TICKS);   w(EVERY)
    emit(0xC6, 0x06); w(FLAG);    emit(0x00)
    emit(0xB4, 0x34); emit(0xCD, 0x21)          # AH=34h -> ES:BX = InDOS flag
    emit(0x89, 0x1E); w(INDOS)
    emit(0x8C, 0x06); w(INDOS + 2)
    emit(0xB8); w(0x351C); emit(0xCD, 0x21)
    emit(0x89, 0x1E); w(labels.get('oldvec', 0))
    emit(0x8C, 0x06); w(labels.get('oldvec', 0) + 2)
    emit(0xBA); w(labels.get('handler', 0))
    emit(0xB8); w(0x251C); emit(0xCD, 0x21)
    emit(0x31, 0xD2)
    emit(0xB8); w(0x2560); emit(0xCD, 0x21)
    emit(0xBA); w(PARAS)
    emit(0xB8); w(0x3100); emit(0xCD, 0x21)

    L['handler'] = here()
    emit(0x50, 0x53, 0x51, 0x52, 0x56, 0x57, 0x06, 0x1E)   # ax bx cx dx si di es ds
    emit(0x0E, 0x1F)
    emit(0xB8); w(0x0040); emit(0x8E, 0xC0)
    emit(0x26, 0x80, 0x3E); w(0x0049); emit(0x13)
    emit(0x75, rel8('done'))
    emit(0x0E, 0x07)
    emit(0xFF, 0x0E); w(TICKS)
    emit(0x75, rel8('done'))
    emit(0xC7, 0x06); w(TICKS); w(EVERY)
    emit(0xBA); w(0x3C7); emit(0x30, 0xC0); emit(0xEE)
    emit(0xBA); w(0x3C9); emit(0xBF); w(BUF); emit(0xB9); w(0x300); emit(0xFC)
    L['rdloop'] = here()
    emit(0xEC); emit(0xAA)
    emit(0xE2, rel8('rdloop'))
    emit(0xC6, 0x06); w(FLAG); emit(0x01)
    # DOS is only safe to call when InDOS is clear
    emit(0xC4, 0x1E); w(INDOS)                  # les bx,[INDOS]
    emit(0x26, 0x80, 0x3F); emit(0x00)          # cmp byte es:[bx],0
    emit(0x75, rel8('done'))
    emit(0xB4, 0x3C); emit(0x31, 0xC9); emit(0xBA); w(FNAME); emit(0xCD, 0x21)
    emit(0x72, rel8('done'))
    emit(0x89, 0xC3)
    emit(0xB4, 0x40); emit(0xB9); w(0x300); emit(0xBA); w(BUF); emit(0xCD, 0x21)
    emit(0xB4, 0x3E); emit(0xCD, 0x21)
    L['done'] = here()
    emit(0x1F, 0x07, 0x5F, 0x5E, 0x5A, 0x59, 0x5B, 0x58)
    emit(0x2E, 0xFF, 0x2E); w(labels.get('oldvec', 0))
    L['oldvec'] = here()
    emit(0, 0, 0, 0)
    return bytes(o), L


def verify(image, labels):
    from capstone import Cs, CS_ARCH_X86, CS_MODE_16
    names = {v: k for k, v in labels.items()}
    bad = []
    for i in Cs(CS_ARCH_X86, CS_MODE_16).disasm(image[:0x100], ORG):
        if i.mnemonic in ("je", "jne", "jb", "loop"):
            t = int(i.op_str, 16)
            if t not in names:
                bad.append((i.address, i.mnemonic, t))
    return bad


def main() -> int:
    labels = {}
    for _ in range(6):
        code, labels = assemble(labels)
    image = bytearray(code)
    image += b"\0" * (FNAME - ORG - len(image))
    image += b"PAL.BIN\0"
    bad = verify(bytes(image), labels)
    if bad:
        for a, m, t in bad:
            print(f"  {a:04x} {m} -> {t:#06x} is not a label")
        return 1
    open("tools/dosbox/PALTSR.COM", "wb").write(bytes(image))
    print(f"PALTSR.COM {len(image)} bytes, {PARAS} paragraphs resident; samples "
          f"every {EVERY} ticks in mode 13h and writes PAL.BIN when InDOS is clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
