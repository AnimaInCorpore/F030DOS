#!/usr/bin/env python3
"""Gold Box image header + 4bpp EGA decoder, and a PNG dumper.

Image header (17 B) — the same struct appears in `.PIC` frames, in the bare
`BODY*`/`HEAD*` files and inside RLE-expanded `.DAX` blocks:

    u16LE height        rows
    u16LE widthBytes    width_px = widthBytes * 8;  bytes/row = widthBytes * 4
    u32LE 0             zero except TITLE.DAX blocks 0x01/0x02 (= 1)
    u8    frameCount    repeat count for multi-element blocks
    8 B   cgaRemap      16-entry x 4-bit CGA colour-reduction table, CGA-only

Trailing fields resolved from the DOS code and checked corpus-wide by
`work/imghdr.py`; see `analysis/executables.md` §Unit `18E`.

Payload: height * widthBytes * 4 bytes, 4 bits per pixel, **high nibble is the
left pixel**, values indexing the standard 16-colour EGA palette.

Verified: 441 of 1044 `.DAX` blocks satisfy `unpackedSize == 17 + h*wb*4`
exactly; a further 50 are arrays of N same-geometry elements after one header.

Usage:
    python3 work/gbimage.py <file> [outdir]        # .PIC / BODY* / HEAD*
    python3 work/gbimage.py --dax <file.DAX> [outdir]
"""
import os, struct, sys

EGA = [(0,0,0),(0,0,170),(0,170,0),(0,170,170),(170,0,0),(170,0,170),(170,85,0),
       (170,170,170),(85,85,85),(85,85,255),(85,255,85),(85,255,255),(255,85,85),
       (255,85,255),(255,255,85),(255,255,255)]

def parse_header(buf, off=0):
    h, wb = struct.unpack_from("<HH", buf, off)
    return h, wb, wb * 8, wb * 4

def to_png(buf, off, h, wb, path, scale=2):
    from PIL import Image
    w, stride = wb * 8, wb * 4
    px = []
    for y in range(h):
        row = buf[off + y * stride: off + (y + 1) * stride]
        for b in row:
            px.append(EGA[b >> 4]); px.append(EGA[b & 15])
    im = Image.new("RGB", (w, h)); im.putdata(px)
    if scale != 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)
    return w, h

def dump_pic(path, outdir):
    d = open(path, "rb").read()
    n = d[0]
    assert len(d) == 1 + n * 3893, f"{path}: unexpected size for {n} frames"
    base = os.path.splitext(os.path.basename(path))[0]
    for i in range(n):
        o = 1 + i * 3893
        tag = struct.unpack_from("<I", d, o)[0]
        h, wb, w, _ = parse_header(d, o + 4)
        to_png(d, o + 4 + 17, h, wb, f"{outdir}/{base}_f{i}.png")
        print(f"  frame {i}: tag=0x{tag:08x} {w}x{h}")

def dump_flat(path, outdir):
    d = open(path, "rb").read()
    h, wb, w, _ = parse_header(d, 0)
    base = os.path.basename(path)
    to_png(d, 17, h, wb, f"{outdir}/{base}.png")
    print(f"  {w}x{h}")

def dump_dax(path, outdir):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dax import blocks, unrle
    _, _, bs = blocks(path)
    base = os.path.splitext(os.path.basename(path))[0]
    for bid, off, unp, pak, pay in bs:
        u = unrle(pay, unp)
        h, wb, w, stride = parse_header(u, 0)
        if not (h and wb) or (unp - 17) % (h * stride):
            print(f"  id 0x{bid:02x}: not an image block ({unp} B)"); continue
        n = (unp - 17) // (h * stride)
        for i in range(n):
            to_png(u, 17 + i * h * stride, h, wb, f"{outdir}/{base}_{bid:02x}_{i}.png")
        print(f"  id 0x{bid:02x}: {n} x {w}x{h}")

if __name__ == "__main__":
    a = sys.argv[1:]
    dax = a and a[0] == "--dax"
    if dax: a = a[1:]
    src = a[0]; out = a[1] if len(a) > 1 else "work/probe"
    os.makedirs(out, exist_ok=True)
    print(src)
    if dax: dump_dax(src, out)
    elif src.upper().endswith(".PIC"): dump_pic(src, out)
    else: dump_flat(src, out)
