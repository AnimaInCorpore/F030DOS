#!/usr/bin/env python3
"""Inspect Westwood PAK directories and optionally render one CPS entry."""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Entry:
    name: str
    offset: int
    size: int


def parse_pak(data: bytes) -> tuple[list[Entry], int]:
    """Parse an offset + NUL-terminated-name directory."""
    raw: list[tuple[str, int]] = []
    pos = 0
    directory_end = None
    while pos + 4 <= len(data):
        offset = struct.unpack_from("<I", data, pos)[0]
        pos += 4
        end = data.find(b"\0", pos)
        if end < 0:
            raise ValueError("unterminated PAK filename")
        name = data[pos:end].decode("ascii", "replace")
        pos = end + 1
        if not name:
            directory_end = pos
            terminal = offset
            break
        raw.append((name, offset))
    else:
        raise ValueError("PAK directory has no empty-name terminator")

    if directory_end is None or terminal != len(data):
        raise ValueError(f"PAK terminal offset 0x{terminal:X} != file size 0x{len(data):X}")
    if not raw or raw[0][1] < directory_end:
        raise ValueError("PAK first data offset precedes the directory")
    if any(a >= b for (_, a), (_, b) in zip(raw, raw[1:])):
        raise ValueError("PAK data offsets are not strictly increasing")

    entries = [
        Entry(name, offset, next_offset - offset)
        for (name, offset), (_, next_offset) in zip(raw, raw[1:] + [("", terminal)])
    ]
    return entries, directory_end


def decode_frame4(src: bytes, dst_size: int) -> bytes:
    """Decode the mixed-reference Westwood Frame4/LCW stream."""
    dst = bytearray()
    pos = 0
    while len(dst) < dst_size and pos < len(src):
        remaining = dst_size - len(dst)
        code = src[pos]
        pos += 1
        if not code & 0x80:
            length = min(remaining, (code >> 4) + 3)
            if pos >= len(src):
                break
            distance = ((code & 0x0F) << 8) | src[pos]
            pos += 1
            ref = len(dst) - distance
            for i in range(length):
                dst.append(dst[ref + i] if 0 <= ref + i < len(dst) else 0)
        elif code & 0x40:
            length = (code & 0x3F) + 3
            if code == 0xFE:
                if pos + 2 >= len(src):
                    break
                length = min(remaining, src[pos] | (src[pos + 1] << 8))
                pos += 2
                dst.extend([src[pos]] * length)
                pos += 1
            elif code == 0xFF:
                if pos + 3 >= len(src):
                    break
                length = min(remaining, src[pos] | (src[pos + 1] << 8))
                pos += 2
                source = src[pos] | (src[pos + 1] << 8)
                pos += 2
                for i in range(length):
                    dst.append(dst[source + i] if source + i < len(dst) else 0)
            else:
                if pos + 1 >= len(src):
                    break
                source = src[pos] | (src[pos + 1] << 8)
                pos += 2
                length = min(remaining, length)
                for i in range(length):
                    dst.append(dst[source + i] if source + i < len(dst) else 0)
        elif code != 0x80:
            length = min(remaining, code & 0x3F)
            dst.extend(src[pos:pos + length])
            pos += length
        else:
            break
    return bytes(dst)


def decode_cps(data: bytes) -> tuple[bytes, list[int]]:
    if len(data) < 10:
        raise ValueError("CPS header is truncated")
    file_size, compression, pixels_size, palette_size = struct.unpack_from("<HHIH", data)
    if file_size + 2 != len(data):
        raise ValueError(f"CPS size field 0x{file_size:X} != payload size 0x{len(data) - 2:X}")
    if palette_size < 768 or len(data) < 10 + palette_size:
        raise ValueError("CPS does not contain a 768-byte VGA palette")
    palette = []
    for value in data[10:10 + 768]:
        palette.append((value & 0x3F) * 4)
    payload = data[10 + palette_size:]
    if compression == 4:
        pixels = decode_frame4(payload, pixels_size)
    elif compression == 0:
        pixels = payload[:pixels_size]
    else:
        raise ValueError(f"unsupported CPS compression {compression}")
    if len(pixels) != pixels_size:
        raise ValueError(f"CPS decoded {len(pixels)} bytes, expected {pixels_size}")
    return pixels, palette


def render_cps(data: bytes, output: Path) -> None:
    from PIL import Image

    pixels, palette = decode_cps(data)
    if len(pixels) < 320 * 200:
        raise ValueError("CPS image is smaller than 320x200")
    image = Image.frombytes("P", (320, 200), pixels[:320 * 200])
    image.putpalette(palette)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(output)


def inspect_file(path: Path, entry_name: str | None, render_path: Path | None) -> None:
    data = path.read_bytes()
    entries, directory_end = parse_pak(data)
    print(f"{path}: {len(data)} bytes, {len(entries)} entries")
    print(f"  directory end 0x{directory_end:X}; first data 0x{entries[0].offset:X}; terminal 0x{len(data):X}")
    for entry in entries:
        print(f"  0x{entry.offset:08X}..0x{entry.offset + entry.size:08X} {entry.size:7} {entry.name}")
    if entry_name or render_path:
        wanted = entry_name or "VIRGIN.CPS"
        match = next((entry for entry in entries if entry.name.upper() == wanted.upper()), None)
        if match is None:
            raise ValueError(f"PAK entry not found: {wanted}")
        payload = data[match.offset:match.offset + match.size]
        if render_path:
            render_cps(payload, render_path)
            print(f"  rendered {match.name} -> {render_path}")
        else:
            print(f"  selected {match.name}: {len(payload)} bytes")


def verify_tree(root: Path) -> None:
    files = sorted(root.rglob("*.PAK"))
    total_entries = 0
    for path in files:
        entries, directory_end = parse_pak(path.read_bytes())
        total_entries += len(entries)
        print(f"{path.relative_to(root)}: {len(entries)} entries, directory 0x{directory_end:X}, OK")
    print(f"verified {len(files)} PAK files, {total_entries} entries")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--entry")
    parser.add_argument("--render-cps", type=Path, metavar="PNG")
    parser.add_argument("--verify-tree", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify_tree:
            verify_tree(args.path)
        else:
            inspect_file(args.path, args.entry, args.render_cps)
    except (OSError, ValueError, struct.error) as exc:
        raise SystemExit(f"error: {exc}")


if __name__ == "__main__":
    main()
