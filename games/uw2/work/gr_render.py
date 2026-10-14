#!/usr/bin/env python3
"""Render DATA/*.GR sprite records to PNG for visual verification.

Container model (matches UW1's corrected model exactly -- see
analysis/data-formats.md here for the UW2-specific diff):
  u8  type   -- shared-loader extension-table index: 1=.gr 2=.tr 3=.cr 4=.sr 5=.ar
               (not a per-format "version"; UW2's T64.TR carries this same
               byte with value 2, confirming the shared loader is identical)
  u16LE record count N @1
  (N+1) x u24LE table entries @3, 4-byte stride (3-byte value + 1 pad)
  table[0] == 3+4*(N+1) always; table[N] == filesize exactly
  record i spans [table[i], table[i+1])

Record header (5 B): u8 type, u8 width, u8 height, u8 b3, u8 b4
  type=4: raw 8bpp indexed pixels, payload == width*height exactly.
  PANELS.GR is NOT in this format: no per-record headers, records 0-2 are raw
  8bpp 79x112 (the UI panels); record 3 (336 B) is undetermined.
  type=0x0a: 4-bit packed indexed pixels, flat nibble stream (no per-row
             byte alignment), +1 trailing byte (purpose TBD). Generic remap
             and transparency remain open; CURSORS.GR record 0 is separately
             capture-backed through ALLPALS.DAT auxiliary palette 23.
  type=8: nibble-packed 16-colour RLE through the aux palette at byte +3
          (ALLPALS.DAT[aux*16..+16]) -- RESOLVED, see work/gr8_decode.py
          and analysis/data-formats.md.
"""
import struct
import sys
from pathlib import Path
from PIL import Image
from gr8_decode import decode_type8

ROOT = Path("work/extracted")
PAL_PATH = Path("work/extracted/D3/DATA/PALS.DAT")
AUX_PATH = Path("work/extracted/D3/DATA/ALLPALS.DAT")


def find_data_file(name):
    hits = list(ROOT.glob(f"D*/DATA/{name}"))
    if not hits:
        sys.exit(f"{name} not found under {ROOT}/D*/DATA/")
    return hits[0]


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def u24(b, o):
    return b[o] | (b[o + 1] << 8) | (b[o + 2] << 16)


def load_palette(index=0):
    pal = PAL_PATH.read_bytes()
    entries = pal[index * 768:index * 768 + 768]
    return bytes((v * 255) // 63 for v in entries)  # 6-bit VGA DAC -> 8-bit


def load_aux_palette(index):
    """Return the record's 16-entry nibble-to-PALS index translation."""
    aux = AUX_PATH.read_bytes()
    start = index * 16
    table = aux[start:start + 16]
    if len(table) != 16:
        raise ValueError(f"aux palette {index} is outside ALLPALS.DAT")
    return table


def records(b):
    n = u16(b, 1)
    table_end = 3 + 4 * n
    offs = [u24(b, 3 + 4 * i) for i in range(n + 1)]
    bounds = offs
    return [(bounds[i], bounds[i + 1]) for i in range(n)]


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
        # Type 8's u16 nibble count starts at record byte +4, so b4 is its
        # low byte and is not a separate header field.
        encoded = b[start + 4:end]
        count = struct.unpack_from("<H", encoded, 0)[0]
        expected = 2 + (count + 1) // 2
        if len(encoded) != expected:
            print(f"  MISMATCH: encoded payload {len(encoded)} != expected {expected}")
            return None
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


if __name__ == "__main__":
    fname = sys.argv[1] if len(sys.argv) > 1 else "SPELLS.GR"
    idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    pal_idx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    path = find_data_file(fname)
    b = path.read_bytes()
    recs = records(b)
    print(f"{fname} ({path}): {len(recs)} records")
    start, end = recs[idx]
    palette = load_palette(pal_idx)
    out = Path("work") / f"{path.stem}_{idx}_pal{pal_idx}.png"
    render_record(b, start, end, out, palette)
