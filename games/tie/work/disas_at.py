#!/usr/bin/env python3
r"""Ad hoc x86-32 disassembly of a Z_TIE__.EXE file-offset range (obj1/obj2).

Raw operands in the file are unrelocated (LE fixups patch them at load
time -- analysis/DOS4G-header.md §Fixups), so an absolute-address operand
shown here is the *unrelocated* dword; cross-check what it resolves to with
`python work/audit_fixups.py --target=OBJ:OFF`. File-offset -> linear mapping
per analysis/ztie.md §4 (obj1 code 0x3D800..0xE8800 base linear 0x10000; obj2
data 0xE8800..0xFBD47 base linear 0xC0000).

Usage: python work/disas_at.py <file_off_hex> [len_hex] [--before n_hex]
"""
import sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

PATH = "game/SWTieCD/TIECD/Z_TIE__.EXE"
data = open(PATH, "rb").read()


def linear(file_off):
    if 0x3D800 <= file_off < 0xE8800:
        return 0x10000 + (file_off - 0x3D800)
    if 0xE8800 <= file_off < 0xFBD47:
        return 0xC0000 + (file_off - 0xE8800)
    return None


def main():
    off = int(sys.argv[1], 16)
    length = int(sys.argv[2], 16) if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else 0x80
    before = 0
    if '--before' in sys.argv:
        before = int(sys.argv[sys.argv.index('--before') + 1], 16)
    start = off - before
    cs = Cs(CS_ARCH_X86, CS_MODE_32)
    for i in cs.disasm(data[start:start + before + length], start):
        marker = '  <== target' if i.address <= off < i.address + i.size else ''
        lin = linear(i.address)
        linstr = f'{lin:08x}' if lin is not None else '?'
        print(f'file {i.address:06x}  lin {linstr}  {i.bytes.hex():<16} '
              f'{i.mnemonic} {i.op_str}{marker}')


if __name__ == '__main__':
    main()
