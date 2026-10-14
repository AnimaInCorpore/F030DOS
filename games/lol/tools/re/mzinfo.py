#!/usr/bin/env python3
"""Audit an MZ executable before choosing an address model for disassembly."""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path


FIELDS = (
    "signature lastpage pages relocs hdrparas minalloc maxalloc "
    "ss sp checksum ip cs reloctab overlay"
).split()


def parse(data: bytes) -> dict[str, int]:
    if data[:2] not in (b"MZ", b"ZM"):
        raise ValueError("not an MZ executable")
    values = struct.unpack_from("<14H", data)
    header = dict(zip(FIELDS, values))
    header["hdrsize"] = header["hdrparas"] * 16
    header["imagesize"] = (
        (header["pages"] - 1) * 512 + header["lastpage"]
        if header["lastpage"] else header["pages"] * 512
    )
    if header["imagesize"] < header["hdrsize"] or header["imagesize"] > len(data):
        raise ValueError("MZ image boundary is outside the file")
    header["loadsize"] = header["imagesize"] - header["hdrsize"]
    return header


def relocations(data: bytes, header: dict[str, int]) -> list[tuple[int, int, int]]:
    pos = header["reloctab"]
    end = pos + header["relocs"] * 4
    if end > len(data):
        raise ValueError("relocation table is outside the file")
    result = []
    for _ in range(header["relocs"]):
        offset, segment = struct.unpack_from("<HH", data, pos)
        target = header["hdrsize"] + (segment << 4) + offset
        result.append((segment, offset, target))
        pos += 4
    return result


def main(path: str) -> None:
    data = Path(path).read_bytes()
    header = parse(data)
    relocs = relocations(data, header)
    entry = header["hdrsize"] + (header["cs"] << 4) + header["ip"]
    stack = header["hdrsize"] + (header["ss"] << 4) + header["sp"]
    markers = []
    for marker in (b"DOS/4G", b"DOS4GW", b"WATCOM", b"Borland", b"FBOV", b"LE"):
        start = 0
        while True:
            found = data.find(marker, start)
            if found < 0:
                break
            markers.append((marker.decode("ascii"), found))
            start = found + 1

    print(f"{path}: {len(data)} bytes on disk")
    print(f"SHA-256: {hashlib.sha256(data).hexdigest()}")
    print("MZ header")
    print(f"  header size    0x{header['hdrsize']:X} ({header['hdrparas']} paragraphs)")
    print(f"  image size     0x{header['imagesize']:X}")
    print(f"  load module    0x{header['loadsize']:X} bytes")
    print(f"  relocations    {header['relocs']} at file 0x{header['reloctab']:X}")
    print(f"  entry CS:IP    {header['cs']:04X}:{header['ip']:04X} (file 0x{entry:X})")
    print(f"  stack SS:SP    {header['ss']:04X}:{header['sp']:04X} (file 0x{stack:X})")
    print(f"  appended data  0x{len(data) - header['imagesize']:X} bytes")
    valid = sum(header["hdrsize"] <= target < header["imagesize"] for _, _, target in relocs)
    print(f"  relocation targets inside MZ image: {valid}/{len(relocs)}")
    print("markers:", ", ".join(f"{name}@0x{offset:X}" for name, offset in markers[:32]) or "none")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tools/re/mzinfo.py EXECUTABLE")
    main(sys.argv[1])
