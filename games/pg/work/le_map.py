#!/usr/bin/env python3
"""Correct LE page map for PANZER.EXE, checked against a RAM dump.

PANZER.EXE is DOS/4GW (the first 0x344A4 bytes) followed by the game's own
bound executable: an MZ stub at 0x344A4 and its `LE` header at +0x2998.  The
LE header's data-pages offset is relative to the start of that bound executable
(0x344A4), not to file offset 0.  METHOD/ledger identity
`base + data_pages_off + (pages-1)*page_size + last_page_bytes == filesize`
holds only with that base.

    python3 work/le_map.py                         # header + identity checks
    python3 work/le_map.py work/qemu_out/pg_ram16.bin   # + RAM/fixup check
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "game" / "EXE" / "PANZER.EXE"
LE = 0x36E3C

d = EXE.read_bytes()


def u32(o: int) -> int:
    return struct.unpack_from("<I", d, o)[0]


def u16(o: int) -> int:
    return struct.unpack_from("<H", d, o)[0]


num_pages = u32(LE + 0x14)
page_size = u32(LE + 0x28)
last_bytes = u32(LE + 0x2C)
otab, nobj, opm = LE + u32(LE + 0x40), u32(LE + 0x44), LE + u32(LE + 0x48)
fpt, frt = LE + u32(LE + 0x68), LE + u32(LE + 0x6C)
dpo = u32(LE + 0x80)
objs = [struct.unpack_from("<6I", d, otab + 24 * i) for i in range(nobj)]


def base_for_identity() -> int:
    return len(d) - (dpo + (num_pages - 1) * page_size + last_bytes)


BASE = base_for_identity()


def page_off(n: int) -> int:
    """Absolute file offset of 1-based LE page n (identity page map)."""
    return BASE + dpo + (n - 1) * page_size


def page_len(n: int) -> int:
    return last_bytes if n == num_pages else page_size


def fixups(n: int):
    """Yield (page_offset, kind, size, target_obj, target_off) for page n."""
    lo = u32(fpt + 4 * (n - 1))
    hi = u32(fpt + 4 * n)
    o = frt + lo
    while o < frt + hi:
        src, flg = d[o], d[o + 1]
        o += 2
        if src & 0x20:
            raise ValueError("source-list fixups not handled")
        soff = struct.unpack_from("<h", d, o)[0]
        o += 2
        if flg & 3 != 0:
            raise ValueError(f"non-internal fixup type {flg & 3}")
        if flg & 0x40:
            obj, o = u16(o), o + 2
        else:
            obj, o = d[o], o + 1
        if src & 0xF == 2:      # 16-bit selector: no target offset
            toff = 0
        elif flg & 0x10:
            toff, o = u32(o), o + 4
        else:
            toff, o = u16(o), o + 2
        yield soff, src & 0xF, obj, toff


def main() -> int:
    print(f"LE header 0x{LE:X}; bound exe base 0x{BASE:X}; "
          f"MZ there: {d[BASE:BASE + 2]!r}; LE offset in it: 0x{LE - BASE:X}")
    print(f"identity: 0x{BASE:X}+0x{dpo:X}+{num_pages - 1}*0x{page_size:X}"
          f"+0x{last_bytes:X} = 0x{BASE + dpo + (num_pages - 1) * page_size + last_bytes:X}"
          f" (EOF 0x{len(d):X})")
    for i, (vs, base, fl, first, cnt, _) in enumerate(objs, 1):
        print(f"object {i}: base 0x{base:X} vsize 0x{vs:X} flags 0x{fl:X} "
              f"pages {first}..{first + cnt - 1} -> file 0x{page_off(first):X}")
    entry_obj, entry_off = u32(LE + 0x18), u32(LE + 0x1C)
    obj_first = objs[entry_obj - 1][3]
    ent = page_off(obj_first + (entry_off >> 12)) + (entry_off & 0xFFF)
    print(f"entry obj{entry_obj}+0x{entry_off:X} -> file 0x{ent:X}: "
          f"{d[ent:ent + 24]!r}")
    kinds = {}
    total = 0
    for n in range(1, num_pages + 1):
        for _s, k, *_ in fixups(n):
            kinds[k] = kinds.get(k, 0) + 1
            total += 1
    print(f"fixups: {total} by source type {kinds}")

    if len(sys.argv) > 1:
        ram = Path(sys.argv[1]).read_bytes()
        delta = 0x124D5C - 0x9283D + 0x9283D   # measured RAM - old tail offset
        # Anchor: LE page 1 must sit at page_off(1) + delta in RAM.
        ok = bad = missing = 0
        for n in range(1, num_pages + 1):
            f0 = page_off(n)
            src = d[f0:f0 + page_len(n)]
            ram0 = f0 + delta
            if ram0 + len(src) > len(ram):
                missing += 1
                continue
            got = ram[ram0:ram0 + len(src)]
            sites = set()
            for soff, k, *_ in fixups(n):
                width = 4 if k == 7 else 2
                for j in range(width):
                    sites.add(soff + j)
            diff = {i for i in range(len(src)) if src[i] != got[i]}
            outside = diff - sites
            if outside:
                bad += 1
                print(f"page {n}: {len(outside)} differing bytes outside "
                      f"fixup sites, first at +0x{min(outside):X}")
            else:
                ok += 1
        print(f"pages whose differences lie only on fixup sites: {ok}; "
              f"others: {bad}; not in dump: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
