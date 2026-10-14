#!/usr/bin/env python3
"""Render DATA/*.TR terrain-tile records to PNG for visual verification.

Container (matches UW1's F16/F32/W16/W64.TR model exactly, analysis/data-formats.md
in the sibling project -- see analysis/data-formats.md here for the UW2 diff):
  u8  version=2
  u8  tile dimension (dim) @1
  u16LE record count N @2
  N x u32LE file offsets @4, uniform stride = dim*dim
  dim x dim raw tile bytes per record, no per-record header

UW2 ships a single T64.TR (dim=64, N=264) instead of UW1's four separate
F16/F32/W16/W64 files -- 256 real tiles (stride 4096) + 8 trailing empty
placeholder slots (offset[i] == offset[i-1] == filelen for the last 8).
"""
import struct
import sys
from pathlib import Path
from PIL import Image

ROOT = Path("work/extracted")
PAL_PATH = Path("work/extracted/D3/DATA/PALS.DAT")


def find_data_file(name):
    hits = list(ROOT.glob(f"D*/DATA/{name}"))
    if not hits:
        sys.exit(f"{name} not found under {ROOT}/D*/DATA/")
    return hits[0]


def load_palette(index=0):
    pal = PAL_PATH.read_bytes()
    entries = pal[index * 768:index * 768 + 768]
    return bytes((v * 255) // 63 for v in entries)  # 6-bit VGA DAC -> 8-bit


def records(b):
    version, dim = b[0], b[1]
    n = struct.unpack_from("<H", b, 2)[0]
    offs = struct.unpack_from(f"<{n}I", b, 4)
    return version, dim, [(offs[i], offs[i] + dim * dim) for i in range(n)]


if __name__ == "__main__":
    fname = sys.argv[1] if len(sys.argv) > 1 else "T64.TR"
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    pal_idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    path = find_data_file(fname)
    b = path.read_bytes()
    version, dim, recs = records(b)
    real = sum(1 for s, e in recs if e <= len(b) and e > s)
    print(f"{fname}: version={version} dim={dim} {len(recs)} table slots, {real} non-empty")
    start, end = recs[idx]
    if end > len(b) or start == recs[idx - 1][0] if idx else False:
        sys.exit(f"record {idx} is empty/out of range ({start:#x}..{end:#x}, filelen {len(b):#x})")
    palette = load_palette(pal_idx)
    payload = b[start:end]
    img = Image.frombytes("P", (dim, dim), payload)
    img.putpalette(palette)
    img = img.convert("RGB")
    out = Path("work") / f"{path.stem}_{idx}_pal{pal_idx}.png"
    img.save(out)
    print(f"wrote {out} ({dim}x{dim})")
