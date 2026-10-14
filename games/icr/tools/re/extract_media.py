#!/usr/bin/env python3
"""Verify and extract the supplied IndyCar Racing FAT12 floppy images.

The source images are immutable.  This tool keeps their disk boundaries by
writing one directory per disk below ``game/disks`` and emits a reproducible
JSON manifest in ``work/media-manifest.json``.  It intentionally handles only
the simple root-directory FAT12 layout used by this distribution; unexpected
filesystem features fail closed instead of being silently flattened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


DISK_NAMES = [
    "IndyCar Racing v1.05 - Papyrus - Disk 1 of 3.img",
    "IndyCar Racing v1.05 - Papyrus - Disk 2 of 3.img",
    "IndyCar Racing v1.05 - Papyrus - Disk 3 of 3.img",
]
EXPECTED_SIZE = 1_474_560


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def fat12_entry(fat: bytes, cluster: int) -> int:
    offset = cluster + cluster // 2
    if offset + 1 >= len(fat):
        raise ValueError(f"FAT12 entry {cluster} is outside the FAT")
    word = fat[offset] | (fat[offset + 1] << 8)
    return (word >> 4) if cluster & 1 else (word & 0xFFF)


def read_disk(path: Path, output: Path | None) -> dict:
    image = path.read_bytes()
    if len(image) != EXPECTED_SIZE:
        raise ValueError(f"{path.name}: expected {EXPECTED_SIZE} bytes, got {len(image)}")
    if image[510:512] != b"\x55\xAA":
        raise ValueError(f"{path.name}: missing 55 AA boot signature")

    bps = u16(image, 11)
    spc = image[13]
    reserved = u16(image, 14)
    fats = image[16]
    root_entries = u16(image, 17)
    total_sectors = u16(image, 19)
    spf = u16(image, 22)
    if (bps, spc, reserved, fats, root_entries, total_sectors, spf) != (
        512, 1, 1, 2, 224, 2880, 9
    ):
        raise ValueError(f"{path.name}: unsupported BPB geometry")

    fat_start = reserved * bps
    fat_size = spf * bps
    fat_copies = [image[fat_start + i * fat_size : fat_start + (i + 1) * fat_size]
                  for i in range(fats)]
    if any(fat != fat_copies[0] for fat in fat_copies[1:]):
        raise ValueError(f"{path.name}: FAT copies differ")
    fat = fat_copies[0]

    root_start = (reserved + fats * spf) * bps
    root_size = root_entries * 32
    root = image[root_start : root_start + root_size]
    data_start_sector = reserved + fats * spf + (root_size + bps - 1) // bps
    data_start = data_start_sector * bps
    max_cluster = 2 + (total_sectors - data_start_sector) // spc

    files = []
    used_clusters: set[int] = set()
    for index in range(root_entries):
        entry = root[index * 32 : (index + 1) * 32]
        first = entry[0]
        if first == 0:
            break
        if first == 0xE5:
            continue
        attr = entry[11]
        if attr & 0x08 or attr & 0x10:
            raise ValueError(f"{path.name}: volume label or directory is unsupported")
        if attr & 0x0F == 0x0F:
            raise ValueError(f"{path.name}: long filename entry is unsupported")
        raw_name = entry[:8].decode("ascii").rstrip()
        raw_ext = entry[8:11].decode("ascii").rstrip()
        name = raw_name + (("." + raw_ext) if raw_ext else "")
        if not name or any(c in name for c in '\\/:*?"<>|'):
            raise ValueError(f"{path.name}: invalid 8.3 name {name!r}")
        size = struct.unpack_from("<I", entry, 28)[0]
        cluster = u16(entry, 26)
        chain: list[int] = []
        if size:
            if cluster < 2 or cluster >= max_cluster:
                raise ValueError(f"{path.name}: {name}: invalid first cluster {cluster}")
            current = cluster
            while 2 <= current < 0xFF8:
                if current >= max_cluster:
                    raise ValueError(f"{path.name}: {name}: cluster {current} is out of range")
                if current in chain:
                    raise ValueError(f"{path.name}: {name}: cyclic cluster chain")
                chain.append(current)
                current = fat12_entry(fat, current)
                if len(chain) > max_cluster:
                    raise ValueError(f"{path.name}: {name}: unreasonable cluster chain")
            if current < 0xFF8:
                raise ValueError(f"{path.name}: {name}: bad chain terminator {current:#x}")
            overlap = used_clusters.intersection(chain)
            if overlap:
                raise ValueError(f"{path.name}: {name}: shared clusters {sorted(overlap)}")
            used_clusters.update(chain)
        capacity = len(chain) * bps * spc
        if size > capacity:
            raise ValueError(f"{path.name}: {name}: size exceeds cluster chain")

        chunks = []
        for current in chain:
            sector = data_start_sector + (current - 2) * spc
            begin = sector * bps
            chunks.append(image[begin : begin + bps * spc])
        data = b"".join(chunks)[:size]
        record = {
            "name": name,
            "size": size,
            "first_cluster": cluster,
            "clusters": len(chain),
            "sha256": sha256(data),
        }
        files.append(record)
        if output is not None:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    return {
        "image": path.name,
        "image_size": len(image),
        "image_sha256": sha256(image),
        "oem": image[3:11].decode("ascii", "replace"),
        "bpb": {
            "bytes_per_sector": bps,
            "sectors_per_cluster": spc,
            "reserved_sectors": reserved,
            "fat_count": fats,
            "root_entries": root_entries,
            "total_sectors": total_sectors,
            "sectors_per_fat": spf,
        },
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    assets = project / "assets"
    output_root = project / "game" / "disks"
    manifests = []
    for number, filename in enumerate(DISK_NAMES, 1):
        source = assets / filename
        if not source.is_file():
            raise SystemExit(f"missing source image: {source}")
        output = None if args.check_only else output_root / f"disk{number}"
        record = read_disk(source, output)
        record["disk"] = number
        manifests.append(record)
        print(f"disk {number}: {record['image_sha256']} ({len(record['files'])} files)")
        for item in record["files"]:
            print(f"  {item['name']:12} {item['size']:7} {item['sha256']}")

    if not args.check_only:
        manifest_path = project / "work" / "media-manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({"disks": manifests}, indent=2) + "\n",
                                  encoding="utf-8")
        print(f"wrote {output_root}")
        print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
