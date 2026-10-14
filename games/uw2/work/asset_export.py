#!/usr/bin/env python3
"""Export the first UW2 pixel slice through a target-neutral indexed seam.

The source files stay in their DOS-native encodings.  This converter expands
one type-8 OBJECTS.GR sprite and one T64.TR tile to a self-contained UW2I
asset:

    header   big-endian, fixed size, all u32 offsets 4-byte aligned
    pixels   one byte per pixel, row-major, value is a PALS.DAT entry index
    palette  one 256-entry PALS.DAT palette, in the source 6-bit DAC form

The output is deliberately target-neutral.  A Falcon backend may turn the
palette into hardware words later, but it must not change the shared pixel
surface or this cache format.
"""
import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

from gr8_decode import decode_type8, records as gr_records


MAGIC = b"UW2I"
VERSION = 1
HEADER_SIZE = 44
PALETTE_BYTES = 256 * 3
NO_AUX_PALETTE = 0xFFFF

SOURCE_KIND = {"gr8": 1, "tr": 2}
PIXEL_FORMAT_INDEX8 = 1
PALETTE_FORMAT_PALS6 = 1
HEADER_FORMAT = ">4sHHHHBBBBIHHIIIII"
assert struct.calcsize(HEADER_FORMAT) == HEADER_SIZE


@dataclass(frozen=True)
class IndexedAsset:
    name: str
    source_kind: str
    source_path: Path
    source_record: int
    source_record_bytes: bytes
    width: int
    height: int
    pixels: bytes
    palette_index: int
    palette: bytes
    aux_palette_index: int = NO_AUX_PALETTE

    @property
    def source_bytes(self):
        return self.source_path.read_bytes()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def align4(value):
    return (value + 3) & ~3


def load_palette(pals_path, index):
    data = pals_path.read_bytes()
    start = index * PALETTE_BYTES
    palette = data[start:start + PALETTE_BYTES]
    if len(palette) != PALETTE_BYTES:
        raise ValueError(f"PALS palette {index} is outside {pals_path}")
    if any(value > 63 for value in palette):
        raise ValueError(f"PALS palette {index} contains a non-6-bit value")
    return palette


def gr8_asset(path, allpals_path, pals_path, record_index, palette_index):
    data = path.read_bytes()
    spans = gr_records(data)
    if not 0 <= record_index < len(spans):
        raise ValueError(f"OBJECTS.GR record {record_index} is out of range")
    start, end = spans[record_index]
    if end <= start or end > len(data):
        raise ValueError(f"OBJECTS.GR record {record_index} has invalid bounds")
    record = data[start:end]
    if len(record) < 5 or record[0] != 8:
        raise ValueError(f"OBJECTS.GR record {record_index} is not type 8")
    width, height, aux_index = record[1], record[2], record[3]
    allpals = allpals_path.read_bytes()
    table = allpals[aux_index * 16:aux_index * 16 + 16]
    if len(table) != 16:
        raise ValueError(f"ALLPALS palette {aux_index} is outside {allpals_path}")
    decoded = decode_type8(record, table)
    content = width * height
    if len(decoded) < content:
        raise ValueError(f"OBJECTS.GR record {record_index} decoded short")
    return IndexedAsset(
        name=f"objects-{record_index:03d}",
        source_kind="gr8",
        source_path=path,
        source_record=record_index,
        source_record_bytes=record,
        width=width,
        height=height,
        pixels=decoded[:content],
        palette_index=palette_index,
        palette=load_palette(pals_path, palette_index),
        aux_palette_index=aux_index,
    )


def tr_asset(path, record_index, pals_path, palette_index):
    data = path.read_bytes()
    if len(data) < 4:
        raise ValueError(f"{path} is too short for a TR header")
    version, dimension = data[0], data[1]
    count = struct.unpack_from("<H", data, 2)[0]
    table_end = 4 + 4 * count
    if table_end > len(data):
        raise ValueError(f"{path} has a truncated TR offset table")
    if not 0 <= record_index < count:
        raise ValueError(f"T64.TR record {record_index} is out of range")
    start = struct.unpack_from("<I", data, 4 + 4 * record_index)[0]
    size = dimension * dimension
    end = start + size
    if end > len(data):
        raise ValueError(f"T64.TR record {record_index} is outside the file")
    if start == len(data):
        raise ValueError(f"T64.TR record {record_index} is an empty slot")
    record = data[start:end]
    if len(record) != size:
        raise ValueError(f"T64.TR record {record_index} is short")
    if version != 2:
        raise ValueError(f"unexpected T64.TR version {version}")
    return IndexedAsset(
        name=f"t64-{record_index:03d}",
        source_kind="tr",
        source_path=path,
        source_record=record_index,
        source_record_bytes=record,
        width=dimension,
        height=dimension,
        pixels=record,
        palette_index=palette_index,
        palette=load_palette(pals_path, palette_index),
    )


def encode_asset(asset):
    """Return one deterministic, self-contained UW2I asset."""
    if len(asset.pixels) != asset.width * asset.height:
        raise ValueError(f"{asset.name}: pixel count does not equal dimensions")
    if len(asset.palette) != PALETTE_BYTES:
        raise ValueError(f"{asset.name}: palette must contain 768 bytes")
    if asset.source_kind not in SOURCE_KIND:
        raise ValueError(f"{asset.name}: unknown source kind {asset.source_kind}")
    pixel_offset = HEADER_SIZE
    palette_offset = align4(pixel_offset + len(asset.pixels))
    padding = b"\0" * (palette_offset - (pixel_offset + len(asset.pixels)))
    header = struct.pack(
        HEADER_FORMAT,
        MAGIC,
        VERSION,
        HEADER_SIZE,
        asset.width,
        asset.height,
        SOURCE_KIND[asset.source_kind],
        PIXEL_FORMAT_INDEX8,
        PALETTE_FORMAT_PALS6,
        0,
        asset.source_record,
        asset.palette_index,
        asset.aux_palette_index,
        pixel_offset,
        len(asset.pixels),
        palette_offset,
        len(asset.palette),
        len(asset.source_record_bytes),
    )
    return header + asset.pixels + padding + asset.palette


def manifest_entry(asset):
    encoded = encode_asset(asset)
    return {
        "name": asset.name,
        "source": str(asset.source_path),
        "source_kind": asset.source_kind,
        "source_record": asset.source_record,
        "source_sha256": sha256(asset.source_bytes),
        "source_record_sha256": sha256(asset.source_record_bytes),
        "width": asset.width,
        "height": asset.height,
        "palette_index": asset.palette_index,
        "aux_palette_index": asset.aux_palette_index,
        "pixel_sha256": sha256(asset.pixels),
        "palette_sha256": sha256(asset.palette),
        "asset_sha256": sha256(encoded),
        "asset_bytes": len(encoded),
    }


def default_paths():
    return {
        "objects": Path("work/extracted/D3/DATA/OBJECTS.GR"),
        "t64": Path("work/extracted/D2/DATA/T64.TR"),
        "allpals": Path("work/extracted/D3/DATA/ALLPALS.DAT"),
        "pals": Path("work/extracted/D3/DATA/PALS.DAT"),
    }


def build_assets(paths, objects_record=0, tile_record=0, palette_index=0):
    return [
        gr8_asset(paths["objects"], paths["allpals"], paths["pals"],
                  objects_record, palette_index),
        tr_asset(paths["t64"], tile_record, paths["pals"], palette_index),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="compare output with analysis/pixel-fixtures.json")
    ap.add_argument("--dump-manifest", action="store_true",
                    help="print the reproducible fixture manifest as JSON")
    ap.add_argument("--out-dir", type=Path,
                    help="also emit .uw2i assets into this generated directory")
    ap.add_argument("--fixtures", type=Path,
                    default=Path("analysis/pixel-fixtures.json"))
    ap.add_argument("--objects-record", type=int, default=0)
    ap.add_argument("--tile-record", type=int, default=0)
    ap.add_argument("--palette", type=int, default=0)
    a = ap.parse_args()

    paths = default_paths()
    assets = build_assets(paths, a.objects_record, a.tile_record, a.palette)
    entries = [manifest_entry(asset) for asset in assets]
    manifest = {
        "format": "UW2I fixture manifest",
        "version": VERSION,
        "palette_format": "PALS.DAT 6-bit DAC entries",
        "assets": entries,
    }

    if a.out_dir:
        a.out_dir.mkdir(parents=True, exist_ok=True)
        for asset in assets:
            out = a.out_dir / f"{asset.name}.uw2i"
            out.write_bytes(encode_asset(asset))
            print(f"wrote {out} ({len(encode_asset(asset))} B)")

    if a.dump_manifest:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        for entry in entries:
            print(f"{entry['name']}: {entry['width']}x{entry['height']} "
                  f"pixels={entry['pixel_sha256']} asset={entry['asset_sha256']}")

    if a.check:
        expected = json.loads(a.fixtures.read_text())
        if expected != manifest:
            print(f"fixture mismatch: {a.fixtures}")
            return 1
        print(f"pixel fixtures: PASS ({len(entries)} assets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
