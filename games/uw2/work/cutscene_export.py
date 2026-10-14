#!/usr/bin/env python3
"""Build the deterministic UW2 intro cutscene fixture manifest.

The source files are the shipped DOS files.  This tool only decodes the
LPF/ANIM record stream into the logical 320x200 indexed framebuffer and emits
hashes; it does not replace the DOS executable as the behavioural authority.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


WIDTH = 320
HEIGHT = 200
FRAME_BYTES = WIDTH * HEIGHT
LPF_DIR = 0x0500
LPF_PAGE_BASE = 0x0B00
LPF_PAGE_STRIDE = 0x10000
LPF_PALETTE = (0x0100, 0x0500)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def parse_lpf(data):
    if data[:4] != b"LPF ":
        raise ValueError("not an LPF file")
    pages = u16(data, 0x06)
    records_total = u32(data, 0x08)
    if u16(data, 0x14) != WIDTH or u16(data, 0x16) != HEIGHT:
        raise ValueError("intro fixture is not 320x200")
    records = {}
    page_modes = []
    for page_index in range(pages):
        base, count, nbytes = struct.unpack_from(
            "<3H", data, LPF_DIR + 6 * page_index
        )
        page = LPF_PAGE_BASE + page_index * LPF_PAGE_STRIDE
        page_base, page_count, page_nbytes, padding = struct.unpack_from(
            "<4H", data, page
        )
        if (page_base, page_count, page_nbytes) != (base, count, nbytes):
            raise ValueError("LPF page header does not repeat its directory entry")
        if padding != 0:
            raise ValueError("LPF page padding word is not zero")
        sizes = [u16(data, page + 8 + 2 * i) for i in range(count)]
        payload = page + 8 + 2 * count
        size_sum = sum(sizes)
        if nbytes == size_sum:
            mode = "payload"
        elif nbytes == size_sum + 8 + 2 * count:
            mode = "whole-page"
        else:
            mode = "unbalanced"
        page_modes.append({
            "index": page_index,
            "base_record": base,
            "record_count": count,
            "declared_bytes": nbytes,
            "size_sum": size_sum,
            "balance": mode,
        })
        for record_offset, size in enumerate(sizes):
            end = payload + size
            if end > len(data):
                raise ValueError("LPF record extends beyond the file")
            record_index = base + record_offset
            if record_index in records:
                raise ValueError("LPF record appears in two pages")
            records[record_index] = data[payload:end]
            payload = end
    if len(records) != records_total or set(records) != set(range(records_total)):
        raise ValueError("LPF directory does not cover the record range")
    return {
        "pages": pages,
        "record_count": records_total,
        "palette": data[LPF_PALETTE[0]:LPF_PALETTE[1]],
        "records": records,
        "page_modes": page_modes,
    }


def decode_record(record, previous):
    """Decode one ANIM delta record, preserving the previous framebuffer."""
    if not record:
        return previous[:]
    if len(record) < 4:
        raise ValueError("short LPF record")
    output = bytearray(previous)
    position = u16(record, 2) if record[1] else 0
    if position & 1:
        position += 1
    cursor = 4
    while cursor < len(record):
        raw = record[cursor]
        cursor += 1
        count = raw if raw < 0x80 else raw - 0x100
        if count > 0:
            end = cursor + count
            if end > len(record) or position + count > FRAME_BYTES:
                raise ValueError("LPF dump exceeds source or framebuffer")
            output[position:position + count] = record[cursor:end]
            cursor = end
            position += count
        elif count == 0:
            if cursor + 2 > len(record):
                raise ValueError("short LPF run")
            count = record[cursor]
            value = record[cursor + 1]
            cursor += 2
            if position + count > FRAME_BYTES:
                raise ValueError("LPF run exceeds framebuffer")
            output[position:position + count] = bytes([value]) * count
            position += count
        else:
            count &= 0x7F
            if count:
                position += count
                if position > FRAME_BYTES:
                    raise ValueError("LPF short skip exceeds framebuffer")
                continue
            if cursor + 2 > len(record):
                raise ValueError("short LPF long operation")
            raw16 = u16(record, cursor)
            cursor += 2
            signed16 = raw16 if raw16 < 0x8000 else raw16 - 0x10000
            if signed16 > 0:
                position += signed16
                if position > FRAME_BYTES:
                    raise ValueError("LPF long skip exceeds framebuffer")
            elif signed16 == 0:
                break
            else:
                count = raw16 & 0x7FFF
                if count >= 0x4000:
                    count -= 0x4000
                    if cursor >= len(record) or position + count > FRAME_BYTES:
                        raise ValueError("LPF long run exceeds source or framebuffer")
                    value = record[cursor]
                    cursor += 1
                    output[position:position + count] = bytes([value]) * count
                    position += count
                else:
                    end = cursor + count
                    if end > len(record) or position + count > FRAME_BYTES:
                        raise ValueError("LPF long dump exceeds source or framebuffer")
                    output[position:position + count] = record[cursor:end]
                    cursor = end
                    position += count
    return bytes(output)


def decode_lpf(data):
    parsed = parse_lpf(data)
    previous = bytes(FRAME_BYTES)
    frames = []
    for index in range(parsed["record_count"]):
        previous = decode_record(parsed["records"][index], previous)
        frames.append(previous)
    parsed["frames"] = frames
    return parsed


def segment_entry(root, filename):
    path = root / "work/extracted/D4/CUTS" / filename
    data = path.read_bytes()
    decoded = decode_lpf(data)
    return {
        "name": filename,
        "source": str(path),
        "source_sha256": sha256(data),
        "width": WIDTH,
        "height": HEIGHT,
        "page_count": decoded["pages"],
        "record_count": decoded["record_count"],
        "palette_sha256": sha256(decoded["palette"]),
        "page_modes": decoded["page_modes"],
        "frame_sha256": [sha256(frame) for frame in decoded["frames"]],
    }


def build_manifest(root):
    cuts = root / "work/extracted/D4/CUTS"
    script = cuts / "CS000.N00"
    # The shipped dump splits the CUTS directory across the D3 and D4
    # extraction roots.  LBACK000 is present in D3, while CS000.Nxx is in D4.
    background = root / "work/extracted/D3/CUTS/LBACK000.BYT"
    return {
        "format": "UW2 intro cutscene fixture manifest",
        "version": 1,
        "script": {
            "name": script.name,
            "source": str(script),
            "source_sha256": sha256(script.read_bytes()),
            "bytes": script.stat().st_size,
        },
        "segments": [
            segment_entry(root, "CS000.N01"),
            segment_entry(root, "CS000.N12"),
            segment_entry(root, "CS000.N02"),
        ],
        "background": {
            "name": background.name,
            "source": str(background),
            "source_sha256": sha256(background.read_bytes()),
            "pixel_sha256": sha256(background.read_bytes()),
            "width": WIDTH,
            "height": HEIGHT,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dump-manifest", action="store_true")
    parser.add_argument("--fixtures", type=Path,
                        default=Path("analysis/cutscene-fixtures.json"))
    args = parser.parse_args()
    root = Path(".")
    manifest = build_manifest(root)
    if args.dump_manifest:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        for segment in manifest["segments"]:
            print(segment["name"], segment["record_count"],
                  segment["source_sha256"])
    if args.check:
        expected = json.loads(args.fixtures.read_text())
        if expected != manifest:
            print("cutscene fixtures: FAIL")
            return 1
        print("cutscene fixtures: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
