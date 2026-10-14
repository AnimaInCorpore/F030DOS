"""Verify and stage Panzer General's supplied ZIP and FAT12 floppy images.

The ZIP and files under assets/ are immutable.  This script only writes the
regenerable work/media/ tree and a JSON manifest there.  It deliberately keeps
the five distribution disks and the patch disk in separate directories.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "assets" / "Panzer General (1994)[3.5][us]_ima.zip"
OUT = ROOT / "work" / "media"
EXPECTED_ARCHIVE_SHA256 = "7D5D1DDF1513852A379BB77628711EABAA0C3760D7E360052F56FB20E9844FFF"
EXPECTED_MEMBERS = {
    "disk1.ima": (1_474_560, 0xDCE3F66B),
    "disk2.ima": (1_474_560, 0x5F41B4D2),
    "disk3.ima": (1_474_560, 0xE5F164EA),
    "disk4.ima": (1_474_560, 0x5513427D),
    "disk5.ima": (1_474_560, 0xE880F856),
    "disk patch.ima": (1_474_560, 0x654D211F),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def fat12_entry(fat: bytes, cluster: int) -> int:
    """Return one FAT12 entry, including the odd/even nibble packing."""
    pos = cluster + cluster // 2
    raw = fat[pos] | (fat[pos + 1] << 8)
    return (raw >> 4) if cluster & 1 else (raw & 0xFFF)


def ascii_field(raw: bytes) -> str:
    return raw.decode("ascii", "replace").rstrip(" \x00")


def short_name(entry: bytes) -> str:
    stem = ascii_field(entry[0:8])
    ext = ascii_field(entry[8:11])
    return f"{stem}.{ext}" if ext else stem


def read_fat12(image: bytes, disk_name: str, out_dir: Path) -> dict:
    if len(image) != 1_474_560:
        raise ValueError(f"{disk_name}: unexpected image size {len(image)}")
    if image[510:512] != b"\x55\xAA":
        raise ValueError(f"{disk_name}: missing 0x55AA boot signature")

    bps = struct.unpack_from("<H", image, 11)[0]
    spc = image[13]
    reserved = struct.unpack_from("<H", image, 14)[0]
    fat_count = image[16]
    root_entries = struct.unpack_from("<H", image, 17)[0]
    total_sectors = struct.unpack_from("<H", image, 19)[0]
    sectors_per_fat = struct.unpack_from("<H", image, 22)[0]
    if (bps, spc, reserved, fat_count, root_entries, total_sectors, sectors_per_fat) != (
        512,
        1,
        1,
        2,
        224,
        2880,
        9,
    ):
        raise ValueError(f"{disk_name}: unsupported BPB geometry")

    fat_offset = reserved * bps
    fat_size = sectors_per_fat * bps
    root_offset = (reserved + fat_count * sectors_per_fat) * bps
    root_size = root_entries * 32
    data_offset = root_offset + root_size
    data_sectors = total_sectors - (data_offset // bps)
    fat0 = image[fat_offset : fat_offset + fat_size]
    fat1 = image[fat_offset + fat_size : fat_offset + 2 * fat_size]
    if fat0 != fat1:
        raise ValueError(f"{disk_name}: FAT copies differ")

    label = ascii_field(image[43:54])
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for index in range(root_entries):
        entry = image[root_offset + index * 32 : root_offset + (index + 1) * 32]
        first = entry[0]
        if first == 0:
            break
        if first == 0xE5:
            continue
        attributes = entry[11]
        if attributes == 0x0F or attributes & 0x08:
            continue
        name = short_name(entry)
        cluster = struct.unpack_from("<H", entry, 26)[0]
        size = struct.unpack_from("<I", entry, 28)[0]
        if attributes & 0x10:
            raise ValueError(f"{disk_name}: unexpected directory entry {name}")
        if cluster < 2 and size:
            raise ValueError(f"{disk_name}: file {name} has invalid start cluster")

        chunks = []
        chain = []
        current = cluster
        while size and current < 0xFF8:
            if current < 2 or current >= 2 + data_sectors:
                raise ValueError(f"{disk_name}: {name} has invalid cluster {current}")
            if current in chain:
                raise ValueError(f"{disk_name}: {name} has a FAT loop")
            chain.append(current)
            sector = (data_offset // bps) + (current - 2) * spc
            start = sector * bps
            chunks.append(image[start : start + spc * bps])
            current = fat12_entry(fat0, current)
        data = b"".join(chunks)[:size]
        if len(data) != size:
            raise ValueError(f"{disk_name}: {name} chain yielded {len(data)} bytes, expected {size}")
        target = out_dir / name
        target.write_bytes(data)
        entries.append(
            {
                "name": name,
                "size": size,
                "start_cluster": cluster,
                "clusters": len(chain),
                "attributes": f"{attributes:02X}",
                "sha256": sha256(data),
                "prefix": data[:16].hex(" ").upper(),
            }
        )

    return {
        "label": label,
        "sha256": sha256(image),
        "size": len(image),
        "geometry": {
            "bytes_per_sector": bps,
            "sectors_per_cluster": spc,
            "reserved_sectors": reserved,
            "fat_count": fat_count,
            "root_entries": root_entries,
            "total_sectors": total_sectors,
            "sectors_per_fat": sectors_per_fat,
        },
        "files": entries,
    }


def main() -> int:
    if not ARCHIVE.is_file():
        raise SystemExit(f"missing archive: {ARCHIVE}")
    archive_bytes = ARCHIVE.read_bytes()
    archive_sha = sha256(archive_bytes)
    if archive_sha != EXPECTED_ARCHIVE_SHA256:
        raise SystemExit(f"archive SHA-256 mismatch: {archive_sha}")

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "archive": {
            "path": str(ARCHIVE.relative_to(ROOT)),
            "size": len(archive_bytes),
            "sha256": archive_sha,
            "tool": f"Python {sys.version.split()[0]} zipfile",
            "crc_check": "pending",
        },
        "disks": {},
    }
    with ZipFile(ARCHIVE) as archive:
        names = {info.filename for info in archive.infolist()}
        if names != set(EXPECTED_MEMBERS):
            raise SystemExit(f"unexpected ZIP members: {sorted(names)}")
        bad = archive.testzip()
        if bad is not None:
            raise SystemExit(f"ZIP CRC failure in {bad}")
        manifest["archive"]["crc_check"] = "ok"
        for info in archive.infolist():
            expected_size, expected_crc = EXPECTED_MEMBERS[info.filename]
            if (info.file_size, info.CRC) != (expected_size, expected_crc):
                raise SystemExit(f"ZIP metadata mismatch for {info.filename}")
            image = archive.read(info)
            disk_key = "patch" if info.filename == "disk patch.ima" else info.filename[:-4]
            disk_dir = OUT / disk_key
            image_path = OUT / ("disk-patch.ima" if disk_key == "patch" else info.filename)
            image_path.write_bytes(image)
            inventory = read_fat12(image, info.filename, disk_dir)
            inventory["archive_member"] = info.filename
            inventory["zip_crc32"] = f"{info.CRC:08X}"
            inventory["image_path"] = str(image_path.relative_to(ROOT))
            manifest["disks"][disk_key] = inventory

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"archive: CRC ok, SHA-256 {archive_sha}")
    for disk_key, disk in manifest["disks"].items():
        names = ", ".join(item["name"] for item in disk["files"])
        print(f"{disk_key}: {disk['sha256']} | {names}")
    print(f"manifest: {OUT / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
