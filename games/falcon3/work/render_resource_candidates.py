from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "game" / "FALCON3"
OUT_DIR = ROOT / "work" / "qemu_out"


def palette() -> list[int]:
    # Index intensity is only a diagnostic view; it does not claim to be the
    # game's VGA palette.
    return [v for i in range(256) for v in (i, i, i)]


def save_indexed(name: str, width: int, pixels: bytes) -> None:
    height = len(pixels) // width
    pixels = pixels[: width * height]
    image = Image.frombytes("P", (width, height), pixels)
    image.putpalette(palette())
    out = OUT_DIR / name
    image.resize((width * 2, height * 2), Image.Resampling.NEAREST).save(out)
    print(f"{name}: {width}x{height}")


def unpack_1bpp(data: bytes, width: int, height: int) -> bytes:
    out = bytearray(width * height)
    row_bytes = (width + 7) // 8
    for y in range(height):
        row = data[y * row_bytes:(y + 1) * row_bytes]
        for x in range(width):
            out[y * width + x] = 255 if row[x // 8] & (0x80 >> (x & 7)) else 0
    return bytes(out)


def unpack_2bpp(data: bytes, width: int, height: int) -> bytes:
    out = bytearray(width * height)
    row_bytes = (width + 3) // 4
    for y in range(height):
        row = data[y * row_bytes:(y + 1) * row_bytes]
        for x in range(width):
            shift = 6 - 2 * (x & 3)
            out[y * width + x] = ((row[x // 4] >> shift) & 3) * 85
    return bytes(out)


def unpack_4plane(data: bytes, width: int, height: int) -> bytes:
    plane_size = width * height // 8
    out = bytearray(width * height)
    for plane in range(4):
        source = data[plane * plane_size:(plane + 1) * plane_size]
        for y in range(height):
            row = source[y * (width // 8):(y + 1) * (width // 8)]
            for x in range(width):
                if row[x // 8] & (0x80 >> (x & 7)):
                    out[y * width + x] |= 1 << plane
    return bytes(v * 17 for v in out)


def main() -> None:
    for resource in ("WARROOM", "COCKPIT", "TITLEPIC", "TITLE"):
        data = (RESOURCE_DIR / resource).read_bytes()
        stem = resource.lower()
        if len(data) >= 64000:
            save_indexed(f"{stem}_raw0_320x200.png", 320, data[:64000])
            save_indexed(f"{stem}_raw_tail_320x200.png", 320, data[-64000:])
        if len(data) >= 32000:
            save_indexed(
                f"{stem}_planar4_320x200.png", 320,
                unpack_4plane(data[:32000], 320, 200),
            )
        if len(data) >= 16000:
            save_indexed(
                f"{stem}_2bpp_320x200.png", 320,
                unpack_2bpp(data[:16000], 320, 200),
            )
        if len(data) >= 8000:
            save_indexed(
                f"{stem}_1bpp_320x200.png", 320,
                unpack_1bpp(data[:8000], 320, 200),
            )


if __name__ == "__main__":
    main()
