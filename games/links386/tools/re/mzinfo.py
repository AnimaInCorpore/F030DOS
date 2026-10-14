#!/usr/bin/env python3
"""Audit an MZ executable before choosing an address model for disassembly."""

from __future__ import annotations

import argparse
import hashlib
import struct
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


def main(path: str, dump_load: Path | None = None) -> None:
    data = Path(path).read_bytes()
    header = parse(data)
    relocs = relocations(data, header)
    entry = header["hdrsize"] + (header["cs"] << 4) + header["ip"]
    stack = header["hdrsize"] + (header["ss"] << 4) + header["sp"]
    markers = []
    for marker in (b"DOS/4G", b"WATCOM"):
        start = 0
        while True:
            found = data.find(marker, start)
            if found < 0:
                break
            markers.append((marker.decode("ascii"), found))
            start = found + 1
    # Only treat LE/LX as a container marker when the MZ header actually
    # provides the optional new-header pointer. Random ASCII "LE" pairs are
    # common in a DOS image and are not evidence of an extender format.
    if header["reloctab"] >= 0x40 and len(data) >= 0x40:
        new_header = struct.unpack_from("<I", data, 0x3C)[0]
        if data[new_header:new_header + 2] in (b"LE", b"LX"):
            markers.append((data[new_header:new_header + 2].decode("ascii"), new_header))

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
    print("markers:", ", ".join(f"{name}@0x{offset:X}" for name, offset in markers[:24]) or "none")
    if dump_load is not None:
        dump_load.parent.mkdir(parents=True, exist_ok=True)
        dump_load.write_bytes(data[header["hdrsize"]:header["imagesize"]])
        print(f"wrote MZ load module to {dump_load}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable")
    parser.add_argument("--dump-load", type=Path,
                        help="write the DOS-mapped load module without the MZ header")
    args = parser.parse_args()
    main(args.executable, args.dump_load)
