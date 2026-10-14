#!/usr/bin/env python3
"""Probe DATA/*.GR sprite archives: dump container + per-record headers.

Container (verified, analysis/data-formats.md):
  u8  type=1 (.gr loader selector)
  u16LE record count N @1
  (N+1) x u24LE file offsets @3 (4-byte stride: 3-byte value + 1 pad)
  record i spans [table[i], table[i+1])
"""
import struct
import sys
from pathlib import Path

DATA_DIR = Path("work/expanded/DATA")


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u24(b, o):
    return b[o] | (b[o + 1] << 8) | (b[o + 2] << 16)


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def probe(path, max_records=6, header_len=12):
    b = path.read_bytes()
    version = b[0]
    n = u16(b, 1)
    tbl_off = 3
    offsets = [u24(b, tbl_off + 4 * i) for i in range(n + 1)]
    print(f"\n=== {path.name} ({len(b)} B) type={version} N={n} first_off={offsets[0]:#06x} "
          f"expect_first={3+4*(n+1):#06x} match={offsets[0] == 3+4*(n+1)}")
    mono = all(offsets[i] <= offsets[i + 1] for i in range(len(offsets) - 1))
    print(f"    monotonic={mono} last_off={offsets[-1]:#x} filelen={len(b):#x} "
          f"last_match={offsets[-1] == len(b)}")
    if path.name.upper() == "PANELS.GR":
        for i in range(min(max_records, n)):
            off = offsets[i]
            span = offsets[i + 1] - off
            if i < 3 and span == 83 * 114:
                print(f"    rec{i:3d} off={off:#07x} span={span:#06x} raw=83x114 headerless")
            else:
                print(f"    rec{i:3d} off={off:#07x} span={span:#06x} raw layout undetermined")
        return b, offsets
    for i in range(min(max_records, n)):
        off = offsets[i]
        span = offsets[i + 1] - off
        hdr = b[off:off + header_len]
        h0 = u32(hdr, 0) if len(hdr) >= 4 else None
        h1 = u32(hdr, 4) if len(hdr) >= 8 else None
        h2 = u32(hdr, 8) if len(hdr) >= 12 else None
        hexstr = " ".join(f"{x:02x}" for x in hdr)
        print(f"    rec{i:3d} off={off:#07x} span={span:#06x} ({span:6d})  hdr[{hexstr}]  "
              f"u32_0={h0:#010x} u32_1={h1:#010x} u32_2={h2:#010x}" if h0 is not None else
              f"    rec{i:3d} off={off:#07x} span={span:#06x} hdr[{hexstr}]")
    return b, offsets


if __name__ == "__main__":
    files = sorted(DATA_DIR.glob("*.GR"))
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for f in files:
        if only and f.stem.upper() not in [o.upper() for o in only]:
            continue
        probe(f)
