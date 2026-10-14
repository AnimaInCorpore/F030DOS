#!/usr/bin/env python3
"""Decode STRINGS.DAT (global string table) of Star Wars: TIE Fighter (1995).

Format: 696 x uint32 LE offsets at 0x0000 (last entry = 0 terminator),
NUL-terminated string pool at 0xAE0 to end of file.

Usage:
    python decode_strings.py [path-to-STRINGS.DAT] [output.txt]
    python decode_strings.py                     # in-place defaults
"""
import struct, sys

def decode(path):
    d = open(path, "rb").read()
    assert d[:4] == struct.pack("<I", 0xAE0), "unexpected first offset"
    n = 0xAE0 // 4
    tbl = struct.unpack(f"<{n}I", d[:0xAE0])
    assert tbl[-1] == 0, "terminator missing"
    strings = []
    for i, o in enumerate(tbl[:-1]):
        assert o >= 0xAE0 and o < len(d), f"bad offset {o:#x} at {i}"
        end = d.index(b"\0", o)
        assert end > o, f"unterminated string at {i}"
        strings.append(d[o:end].decode("latin1"))
    return strings

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "STRINGS.DAT"
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    strs = decode(src)
    if dst:
        with open(dst, "w", encoding="utf-8") as f:
            for i, s in enumerate(strs):
                f.write(f"{i:4d}  {s}\n")
        print(f"{len(strs)} strings -> {dst}")
    else:
        for i, s in enumerate(strs):
            print(f"{i:4d}  {s}")
