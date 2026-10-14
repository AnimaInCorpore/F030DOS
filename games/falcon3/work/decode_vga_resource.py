from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "game" / "FALCON3"
OUT_DIR = ROOT / "work" / "qemu_out"


def flat_palette(mode: str) -> list[int]:
    if mode == "grayscale":
        return [v for i in range(256) for v in (i, i, i)]
    if mode == "high_contrast":
        # Make the commonly used bright VGA indices easy to inspect while
        # preserving the indexed nature of the source pixels.
        colors = []
        for i in range(256):
            if i == 0:
                colors.append((0, 0, 0))
            elif i >= 240:
                colors.append((255, 255, 255))
            elif i >= 224:
                colors.append((192, 192, 192))
            else:
                colors.append((i, i, i))
        return [v for color in colors for v in color]
    raise ValueError(mode)


def decode(name: str) -> None:
    source = RESOURCE_DIR / name
    data = source.read_bytes()
    width = int.from_bytes(data[0:2], "little")
    height = int.from_bytes(data[2:4], "little")
    payload = data[4:]
    if len(payload) != width * height:
        raise ValueError(
            f"{name}: header says {width}x{height}, "
            f"but payload is {len(payload)} bytes"
        )

    image = Image.frombytes("P", (width, height), payload)
    for mode in ("grayscale", "high_contrast"):
        rendered = image.copy()
        rendered.putpalette(flat_palette(mode))
        output = OUT_DIR / f"{source.stem.lower()}_{mode}.png"
        rendered.resize((width * 2, height * 2), Image.Resampling.NEAREST).save(output)
        print(f"{name}: {width}x{height}, {len(payload)} pixels -> {output}")


if __name__ == "__main__":
    for resource in ("VICTEXT", "HTLINFBK.BIN"):
        decode(resource)
