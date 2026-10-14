#!/usr/bin/env python3
"""Parse a game-shipped `LX` driver DLL (LIB/DRV/VESA480.DLL), apply its fixups at
a chosen load base, and optionally compare the result with an oracle RAM dump.

    python3 tools/re/lx_dll.py [--base 0x218AED] [--ram work/qemu_out/pg_menu16.bin]
                               [--disasm]

The DLL is an MZ stub (0x80 bytes) followed by an `LX` header at 0x90; it has no
entry table and no EIP.  Its single object (link base 0x10000, 0x4054 bytes) starts
with a 13-entry export vector of link-time linear addresses; the game copies that
vector, rebased, into its globals at object-2 offsets 0x55B8..0x55E8
(analysis/executable.md, "Indirect calls").
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parents[2]
DLL = ROOT / "game" / "LIB" / "DRV" / "VESA480.DLL"
LX = 0x90
d = DLL.read_bytes()


def u32(o):
    return struct.unpack_from("<I", d, o)[0]


def u16(o):
    return struct.unpack_from("<H", d, o)[0]


pages = u32(LX + 0x14)
psize = u32(LX + 0x28)
pm_off = LX + u32(LX + 0x48)
fpt, frt = LX + u32(LX + 0x68), LX + u32(LX + 0x6C)
dpo = u32(LX + 0x80)
ot = LX + u32(LX + 0x40)
vsize, link_base = u32(ot), u32(ot + 4)
N_EXPORTS = 13


def image() -> bytes:
    out = bytearray()
    for i in range(pages):
        off, size, _fl = struct.unpack_from("<IHH", d, pm_off + 8 * i)
        out += d[dpo + off:dpo + off + size].ljust(psize, b"\0")
    return bytes(out[:vsize])


def fixups():
    """Yield (image offset of a 32-bit site, target image offset); internal only."""
    for n in range(pages):
        o = frt + u32(fpt + 4 * n)
        end = frt + u32(fpt + 4 * (n + 1))
        while o < end:
            src, flg = d[o], d[o + 1]
            o += 2
            if src & 0x20 or flg & 3:
                raise ValueError(f"unhandled fixup src={src:#x} flags={flg:#x}")
            soff = struct.unpack_from("<h", d, o)[0]
            o += 2
            o += 2 if flg & 0x40 else 1                      # target object
            if src & 0xF == 2:
                toff = 0
            elif flg & 0x10:
                toff, o = u32(o), o + 4
            else:
                toff, o = u16(o), o + 2
            yield n * psize + soff, src & 0xF, toff


def rebased(base: int) -> tuple[bytes, list]:
    img = bytearray(image())
    sites = []
    for site, kind, toff in fixups():
        if kind == 7 and 0 <= site <= len(img) - 4:
            struct.pack_into("<I", img, site, (base + toff) & 0xFFFFFFFF)
            sites.append(site)
    return bytes(img), sites


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=lambda v: int(v, 0), default=0x218AED)
    ap.add_argument("--ram", type=Path)
    ap.add_argument("--disasm", action="store_true")
    a = ap.parse_args()
    raw = image()
    img, sites = rebased(a.base)
    vec = struct.unpack_from(f"<{N_EXPORTS}I", raw, 0)
    print(f"{DLL.name}: {pages} pages, object link base 0x{link_base:X}, "
          f"{vsize} bytes, {len(sites)} 32-bit fixups")
    print("export vector (link-time addresses -> image offsets):")
    for i, v in enumerate(vec):
        print(f"  [{i:2}] 0x{v:X} -> +0x{v - link_base:X}")
    if a.ram:
        ram = a.ram.read_bytes()[a.base:a.base + vsize]
        site_bytes = {s + k for s in sites for k in range(4)}
        diff = [i for i in range(vsize) if ram[i] != img[i]]
        outside = [i for i in diff if i not in site_bytes]
        print(f"RAM at 0x{a.base:X}: equal {vsize - len(diff)} of {vsize}; "
              f"differing bytes outside fixup sites: {len(outside)}")
        if outside:
            print("  first:", [hex(i) for i in outside[:12]])
    if a.disasm:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for i, v in enumerate(vec):
            off = v - link_base
            print(f"--- export {i} +0x{off:X}")
            for ins in list(md.disasm(raw[off:off + 40], link_base + off, 8)):
                print(f"  {ins.address:X} {ins.mnemonic} {ins.op_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
