#!/usr/bin/env python3
"""Render DATA/*.GR sprite records to PNG for visual verification.

Container model (corrected 2026-08-25, see analysis/data-formats.md):
  u8  type=1 (.gr loader selector)
  u16LE record count N @1
  (N+1) x u24LE offsets @3 (4-byte stride)
  table[0] == 3+4*(N+1), table[N] == filelen
  record i spans [table[i], table[i+1])

Record header for raw/flat records (5 B): u8 type, u8 width, u8 height,
u8 b3, u8 b4. Type 8 overlaps b4 with the low byte of its u16 nibble count.
  type=4: raw 8bpp indexed pixels, payload == width*height exactly (verified).
  type=0x0a: flat 4-bit packed indexed pixels, +1 trailing byte.
  type=8: nibble-packed RLE through ALLPALS.DAT[b3*16:b3*16+16].
  PANELS.GR is a loader-level outlier: records 0-2 are raw 8bpp 83x114
  panels with no per-record headers; record 3 is a separate 360-byte blob.
"""
import struct
import sys
from pathlib import Path
from PIL import Image
from gr8_decode import decode_type8

DATA_DIR = Path("work/expanded/DATA")
PAL_PATH = Path("work/expanded/DATA/PALS.DAT")
AUX_PATH = Path("work/expanded/DATA/ALLPALS.DAT")


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u24(b, o):
    return b[o] | (b[o + 1] << 8) | (b[o + 2] << 16)


def load_palette(index=0):
    pal = PAL_PATH.read_bytes()
    entries = pal[index * 768:index * 768 + 768]
    # 6-bit VGA DAC -> 8-bit
    return bytes((v * 255) // 63 for v in entries)


def records(b):
    n = u16(b, 1)
    offs = [u24(b, 3 + 4 * i) for i in range(n + 1)]
    assert offs[0] == 3 + 4 * (n + 1)
    assert offs[-1] == len(b), f"last offset {offs[-1]:#x} != filelen {len(b):#x}"
    return [(offs[i], offs[i + 1]) for i in range(n)]


def load_aux_palette(index):
    aux = AUX_PATH.read_bytes()
    table = aux[index * 16:index * 16 + 16]
    if len(table) != 16:
        raise ValueError(f"auxiliary palette {index} is outside ALLPALS.DAT")
    return table


def render_record(b, start, end, out_path, palette):
    span = end - start
    if span < 5:
        print(f"  skip: span {span} < 5 (empty/degenerate record)")
        return None
    rtype, w, h, b3, b4 = b[start], b[start + 1], b[start + 2], b[start + 3], b[start + 4]
    payload = b[start + 5:end]
    print(f"  type={rtype} w={w} h={h} b3={b3:#04x} b4={b4:#04x} payload_len={len(payload)} w*h={w*h}")
    if rtype == 4:
        if len(payload) != w * h:
            print(f"  MISMATCH: payload {len(payload)} != w*h {w*h}")
            return None
        img = Image.frombytes("P", (w, h), payload)
        img.putpalette(palette)
        img = img.convert("RGB")
    elif rtype == 10:
        # 4-bit packed, 2 px/byte, FLAT stream (no per-row byte alignment)
        # + 1 trailing byte. Render as grayscale (nibble*17) since the real
        # 16-color remap is unknown -- this only tests the packing math.
        expected = (w * h + 1) // 2 + 1
        if len(payload) != expected:
            print(f"  MISMATCH: payload {len(payload)} != expected {expected}")
            return None
        px = bytearray(w * h)
        for i in range(w * h):
            byte = payload[i // 2]
            nib = (byte >> 4) if i % 2 == 0 else (byte & 0xF)
            px[i] = nib * 17
        img = Image.frombytes("L", (w, h), bytes(px)).convert("RGB")
    elif rtype == 8:
        px = decode_type8(b[start:end], load_aux_palette(b3))
        if len(px) < w * h:
            print(f"  MISMATCH: decoded {len(px)} < w*h {w*h}")
            return None
        img = Image.frombytes("P", (w, h), bytes(px[:w * h]))
        img.putpalette(palette)
        img = img.convert("RGB")
    else:
        print(f"  skip: type {rtype} not decodable by this renderer")
        return None
    img.save(out_path)
    print(f"  wrote {out_path} ({w}x{h})")
    return out_path


def render_panel_record(b, start, end, out_path, palette, index):
    """Render one of UW1's three headerless PANELS.GR records."""
    width, height = 83, 114
    payload = b[start:end]
    if len(payload) != width * height:
        print(f"  PANELS record {index}: {len(payload)} B != {width}x{height}")
        return None
    img = Image.frombytes("P", (width, height), payload)
    img.putpalette(palette)
    img = img.convert("RGB")
    img.save(out_path)
    print(f"  PANELS raw record {index}: wrote {out_path} ({width}x{height})")
    return out_path


if __name__ == "__main__":
    fname = sys.argv[1] if len(sys.argv) > 1 else "CHARHEAD.GR"
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    pal_idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    path = DATA_DIR / fname
    b = path.read_bytes()
    recs = records(b)
    print(f"{fname}: {len(recs)} records")
    start, end = recs[idx]
    palette = load_palette(pal_idx)
    out = Path("work") / f"{path.stem}_{idx}_pal{pal_idx}.png"
    if path.name.upper() == "PANELS.GR":
        if idx >= 3:
            print("  PANELS record 3 is 360 B and remains undetermined; no render attempted")
        else:
            render_panel_record(b, start, end, out, palette, idx)
    else:
        render_record(b, start, end, out, palette)
