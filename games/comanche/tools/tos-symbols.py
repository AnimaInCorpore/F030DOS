#!/usr/bin/env python3
"""Symbols of a GEMDOS (DRI/GST) executable: name -> value, with the long-name
extension. N/A - target artefact: an analysis helper, no DOS routine."""
import struct
import sys


def read_symbols(path):
    b = open(path, "rb").read()
    text, data, bss, symtab = struct.unpack_from(">IIII", b, 2)
    syms = {}
    off = 28 + text + data
    end = off + symtab
    while off < end:
        name = b[off:off + 8].split(b"\0")[0].decode("latin-1")
        stype, value = struct.unpack_from(">HI", b, off + 8)
        if stype & 0x0048 == 0x0048:          # GST long-name continuation
            name += b[off + 14:off + 22].split(b"\0")[0].decode("latin-1")
            off += 14
            name_full = b[off - 14 + 0:off - 14 + 8].split(b"\0")[0].decode("latin-1") + \
                b[off:off + 14].split(b"\0")[0].decode("latin-1")
            # the continuation record holds the next 14 name bytes
            name = name_full
            off += 14
            syms[name] = value
            continue
        syms[name] = value
        off += 14
    return syms


if __name__ == "__main__":
    syms = read_symbols(sys.argv[1])
    for n in sys.argv[2:]:
        print(n, hex(syms.get(n, -1)))
