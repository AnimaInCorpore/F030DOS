#!/usr/bin/env python3
"""Compare a captured Falcon RGB565 frame against the host expansion of the
same DOS source bytes.

The Falcon page and the host reference are produced from one source: the
converter's indexed pixels and the converter's RGB565 palette. If the Falcon
presentation step is faithful, the two are byte-identical — so this is an
equality check, not a similarity score.

    python3 tools/check_frame.py release/frame.bin work/expanded/TITLE.DAX [index]
"""
import os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import convert_data as cv                                       # noqa: E402

WIDTH, HEIGHT = 320, 200


def main():
    if len(sys.argv) < 3:
        raise SystemExit("usage: check_frame.py FRAME.BIN SOURCE [image-index]")
    frame_path, source = sys.argv[1], sys.argv[2]
    index = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    captured = open(frame_path, "rb").read()
    if len(captured) != WIDTH * HEIGHT * 2:
        raise SystemExit(f"frame is {len(captured)} B, expected {WIDTH*HEIGHT*2}")

    images, _ = cv.collect(source)
    if index >= len(images):
        raise SystemExit(f"{source} has {len(images)} image(s), asked for {index}")
    w, h, sid, pixels = images[index]

    palette = [cv.rgb565(c) for c in cv.EGA]
    # Reproduce blit_centred, then present_indexed.
    surface = bytearray(WIDTH * HEIGHT)
    ox, oy = (WIDTH - w) // 2, (HEIGHT - h) // 2
    for y in range(h):
        surface[(oy + y) * WIDTH + ox:(oy + y) * WIDTH + ox + w] = pixels[y * w:(y + 1) * w]
    expected = bytearray()
    for p in surface:
        expected += struct.pack(">H", palette[p & 0x0F])

    if bytes(expected) == captured:
        print(f"frame matches host expansion of {os.path.basename(source)} "
              f"image {index} ({w}x{h}): {len(captured)} bytes identical")
        return 0

    diff = sum(1 for a, b in zip(expected, captured) if a != b)
    first = next(i for i, (a, b) in enumerate(zip(expected, captured)) if a != b)
    px = first // 2
    print(f"MISMATCH: {diff} of {len(captured)} bytes differ; first at byte {first} "
          f"(pixel {px % WIDTH},{px // WIDTH})")
    print(f"  expected {expected[first & ~1]:02x}{expected[(first & ~1)+1]:02x}  "
          f"captured {captured[first & ~1]:02x}{captured[(first & ~1)+1]:02x}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
