#!/usr/bin/env python3
"""Audit a DOS/4G MZ stub and its optional Watcom LE header."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


FIELDS = (
    "signature lastpage pages relocs hdrparas minalloc maxalloc "
    "ss sp checksum ip cs reloctab overlay"
).split()


def parse_mz(data: bytes) -> dict[str, int]:
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
    start = header["reloctab"]
    end = start + header["relocs"] * 4
    if end > len(data):
        raise ValueError("relocation table is outside the file")
    result = []
    for pos in range(start, end, 4):
        offset, segment = struct.unpack_from("<HH", data, pos)
        result.append((segment, offset,
                       header["hdrsize"] + (segment << 4) + offset))
    return result


def le_summary(data: bytes, header: dict[str, int]) -> None:
    if len(data) < 0x40:
        return
    pointer = struct.unpack_from("<I", data, 0x3C)[0]
    if pointer + 2 > len(data) or data[pointer:pointer + 2] != b"LE":
        print("LE header: none at MZ new-header pointer")
        return

    u32 = lambda off: struct.unpack_from("<I", data, pointer + off)[0]
    u16 = lambda off: struct.unpack_from("<H", data, pointer + off)[0]
    print(f"LE header at file 0x{pointer:X}")
    print(f"  format level     0x{u32(4):X}")
    print(f"  cpu/os type      0x{u16(8):04X}/0x{u16(0xA):04X}")
    print(f"  module flags     0x{u32(0x10):08X}")
    print(f"  object pages     {u32(0x14)} (page size 0x{u32(0x28):X})")
    print(f"  entry            object {u32(0x18)}, offset 0x{u32(0x1C):X}")
    print(f"  stack            object {u32(0x20)}, offset 0x{u32(0x24):X}")
    print(f"  data pages       LE offset 0x{u32(0x80):X}")
    table = u32(0x40)
    count = u32(0x44)
    print(f"  object table     LE offset 0x{table:X}, {count} objects")
    for number in range(1, count + 1):
        values = struct.unpack_from("<6I", data, pointer + table + (number - 1) * 24)
        print(f"    object {number}: size 0x{values[0]:X}, base 0x{values[1]:X}, "
              f"flags 0x{values[2]:X}, pages {values[3]}+{values[4]}")


def main(path: Path, dump_load: Path | None) -> None:
    data = path.read_bytes()
    header = parse_mz(data)
    relocs = relocations(data, header)
    entry = header["hdrsize"] + (header["cs"] << 4) + header["ip"]
    stack = header["hdrsize"] + (header["ss"] << 4) + header["sp"]
    valid = sum(header["hdrsize"] <= target < header["imagesize"]
                for _, _, target in relocs)

    print(f"{path}: {len(data)} bytes on disk")
    print(f"SHA-256: {hashlib.sha256(data).hexdigest()}")
    print("MZ header")
    print(f"  header size    0x{header['hdrsize']:X}")
    print(f"  image size     0x{header['imagesize']:X}")
    print(f"  load module    0x{header['loadsize']:X} bytes")
    print(f"  relocations    {header['relocs']} at file 0x{header['reloctab']:X}")
    print(f"  entry CS:IP    {header['cs']:04X}:{header['ip']:04X} (file 0x{entry:X})")
    print(f"  stack SS:SP    {header['ss']:04X}:{header['sp']:04X} (file 0x{stack:X})")
    print(f"  appended data  0x{len(data) - header['imagesize']:X} bytes")
    print(f"  relocation targets inside MZ image: {valid}/{len(relocs)}")
    if relocs:
        print("  relocation records:")
        for segment, offset, target in relocs:
            print(f"    {segment:04X}:{offset:04X} -> file 0x{target:X}")
    le_summary(data, header)

    if dump_load is not None:
        dump_load.parent.mkdir(parents=True, exist_ok=True)
        dump_load.write_bytes(data[header["hdrsize"]:header["imagesize"]])
        print(f"wrote MZ load module to {dump_load}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--dump-load", type=Path,
                        help="write the DOS-mapped MZ load module")
    args = parser.parse_args()
    main(args.executable, args.dump_load)
