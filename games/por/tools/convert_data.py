#!/usr/bin/env python3
"""Convert the decoded DOS art into one big-endian Falcon image bank.

Only formats that are fully resolved in analysis/data-formats.md are converted:
the `.DAX` container, its PackBits RLE, and the 17-byte image header with its
4 bpp packed EGA payload. Nothing is guessed here — an unrecognised block is
skipped and counted, never emitted with invented geometry.

Output (`PORI` bank, **big-endian throughout**, mirrored by src/inc/por.s and
checked by tools/check_contracts.py):

    0   char[4] 'PORI'
    4   u16     version = 1
    6   u16     imageCount
    8   u16     paletteCount = 16
    10  u16     flags = 0
    12  u16[16] RGB565 palette
    44  imageCount x 16-byte directory entry:
            u16 width
            u16 height
            u16 sourceId        DAX block id, or PIC/portrait frame index
            u16 reserved = 0
            u32 dataOffset      from file start
            u32 dataBytes       == width * height
    ..  image data, one byte per pixel, palette index 0..15, no padding

Usage:
    python3 tools/convert_data.py <expanded-dir> <out-dir> [name ...]
    python3 tools/convert_data.py --target st <expanded-dir> <out-dir> [name ...]

The pixel data is target-neutral — one byte per pixel, the DOS palette index
preserved verbatim. Only the palette table is encoded per target, and the bank
header records which encoding it carries.
"""
import os, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work"))
from dax import blocks, unrle                        # noqa: E402
from gbimage import EGA, parse_header                # noqa: E402

MAGIC = b"PORI"
VERSION = 1
PALETTE_COUNT = 16
HEADER_BYTES = 12 + PALETTE_COUNT * 2   # 44
DIR_ENTRY_BYTES = 16

# Palette encodings, mirrored by PORI_PAL_* in src/common/inc/por.s. The pixel
# data is target-neutral (one byte per pixel); only the palette table differs,
# so adding a target means adding one encoder here and one back end in src/.
PAL_NONE, PAL_RGB565, PAL_ST = 0, 1, 2


# *** NOT GROUNDED IN THE DOS ORIGINAL. ***
# `EGA` is the standard 16-colour EGA hardware palette, imported from
# work/gbimage.py. No palette file ships with the game, and no attribute-
# controller (0x3C0) write or INT 10h palette call has been found in the
# disassembly so far. If the game programs its own palette, every colour here is
# wrong and this is the single line to change. See PORTING.md §Open risks 1.
def rgb565(rgb):
    """Falcon true colour: 5-6-5 in one big-endian word."""
    r, g, b = rgb
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def st_rgb(rgb):
    """Atari ST/STE: $0RGB, four bits per gun (STE); three on a plain ST."""
    r, g, b = rgb
    return ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)


TARGETS = {
    "falcon": (PAL_RGB565, rgb565),
    "st":     (PAL_ST, st_rgb),
}


def unpack_4bpp(buf, off, height, width_bytes):
    """4 bpp packed -> one byte per pixel. High nibble is the left pixel."""
    stride = width_bytes * 4
    out = bytearray(height * width_bytes * 8)
    w = 0
    for y in range(height):
        row = buf[off + y * stride: off + (y + 1) * stride]
        for byte in row:
            out[w] = byte >> 4; out[w + 1] = byte & 15; w += 2
    return bytes(out)


def images_from_flat(path):
    """BODY* / HEAD* — a bare 17-byte header plus raw pixels."""
    d = open(path, "rb").read()
    h, wb, w, stride = parse_header(d, 0)
    if not (h and wb) or len(d) != 17 + h * stride:
        return []
    return [(w, h, 0, unpack_4bpp(d, 17, h, wb))]


def images_from_pic(path):
    d = open(path, "rb").read()
    n = d[0]
    if n == 0 or len(d) != 1 + n * 3893:
        return []
    out = []
    for i in range(n):
        o = 1 + i * 3893
        h, wb, w, stride = parse_header(d, o + 4)
        if not (h and wb) or 21 + h * stride != 3893:
            return []
        out.append((w, h, i, unpack_4bpp(d, o + 21, h, wb)))
    return out


def images_from_dax(path):
    out, skipped = [], 0
    for bid, off, unp, pak, payload in blocks(path)[2]:
        u = unrle(payload, unp)
        if len(u) < 4:
            skipped += 1; continue
        h, wb, w, stride = parse_header(u, 0)
        if not (h and wb) or h * stride == 0 or (unp - 17) % (h * stride):
            skipped += 1; continue
        count = (unp - 17) // (h * stride)
        for i in range(count):
            out.append((w, h, bid, unpack_4bpp(u, 17 + i * h * stride, h, wb)))
    return out, skipped


def collect(path):
    up = path.upper()
    if up.endswith(".DAX"):
        return images_from_dax(path)
    if up.endswith(".PIC"):
        return images_from_pic(path), 0
    return images_from_flat(path), 0


def build_bank(images, target="falcon"):
    body = bytearray()
    directory = bytearray()
    data_start = HEADER_BYTES + len(images) * DIR_ENTRY_BYTES
    for w, h, sid, pixels in images:
        assert len(pixels) == w * h, "pixel count must equal width*height"
        directory += struct.pack(">HHHHII", w, h, sid, 0,
                                 data_start + len(body), len(pixels))
        body += pixels
    pal_kind, encode = TARGETS[target]
    head = struct.pack(">4sHHHH", MAGIC, VERSION, len(images), PALETTE_COUNT, pal_kind)
    head += b"".join(struct.pack(">H", encode(c)) for c in EGA)
    assert len(head) == HEADER_BYTES
    return bytes(head + directory + body)


def main():
    argv = sys.argv[1:]
    target = "falcon"
    if argv[:1] == ["--target"]:
        target = argv[1]
        argv = argv[2:]
        if target not in TARGETS:
            raise SystemExit(f"unknown target {target}; known: {', '.join(TARGETS)}")
    if len(argv) < 2:
        raise SystemExit("usage: convert_data.py [--target NAME] <expanded-dir> <out-dir> [name ...]")
    src, dst = argv[0], argv[1]
    names = argv[2:] or sorted(os.listdir(src))
    os.makedirs(dst, exist_ok=True)
    total_img = total_skip = total_bytes = 0
    for name in names:
        path = os.path.join(src, name)
        if not os.path.isfile(path):
            continue
        images, skipped = collect(path)
        if not images:
            total_skip += skipped
            continue
        out = os.path.join(dst, os.path.splitext(name)[0][:8].upper() + ".BIN")
        bank = build_bank(images, target)
        with open(out, "wb") as fh:
            fh.write(bank)
        total_img += len(images); total_skip += skipped; total_bytes += len(bank)
        if len(names) <= 8:
            print(f"{name:14s} -> {os.path.basename(out):12s} "
                  f"{len(images)} image(s), {len(bank)} B")
    print(f"{total_img} images converted, {total_skip} blocks skipped "
          f"(not images), {total_bytes} B written to {dst} (target: {target})")


if __name__ == "__main__":
    main()
