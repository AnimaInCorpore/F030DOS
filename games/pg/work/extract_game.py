"""Recover the unpatched game tree through the supplied DOS DEARJ utility.

The distribution archives use DEARJ's append-at-volume-boundary convention.
The companion probe builds a temporary DOS image, runs the shipped
DEARJ.EXE over DATA.A00 through DATA.A04 in one output directory, and exits
only after the guest has completed. This script then pulls that output from
the image, restores the archive paths from the ARJ directories, and verifies
the observed entry counts, continuation map, sizes and CRC reports.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zlib
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "work" / "media"
GAME = ROOT / "game"
PROBE = ROOT / "work" / "probe_dearj.py"
PROBE_WORK = ROOT / "work" / "dearj_probe"
FLAT = PROBE_WORK / "out_final"
LOGS = PROBE_WORK / "logs_final"
ARCHIVES = [
    MEDIA / "disk1" / "DATA.A00",
    MEDIA / "disk2" / "DATA.A01",
    MEDIA / "disk3" / "DATA.A02",
    MEDIA / "disk4" / "DATA.A03",
    MEDIA / "disk5" / "DATA.A04",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def find_7zip() -> str:
    for name in ("7zz", "7z", "7z.exe"):
        found = shutil.which(name)
        if found:
            return found
    common = Path(r"C:\Program Files\7-Zip\7z.exe")
    if common.is_file():
        return str(common)
    raise SystemExit("7-Zip 26+ not found; install it or put 7z/7zz on PATH")


def parse_arj_entries(seven: str, archive: Path) -> list[dict]:
    result = subprocess.run(
        [seven, "l", "-slt", str(archive)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        check=True,
    )
    entries = []
    for block in result.stdout.split("\n\n"):
        if "Folder = -" not in block:
            continue
        path = re.search(r"^Path = (.+)$", block, re.MULTILINE)
        size = re.search(r"^Size = (\d+)$", block, re.MULTILINE)
        crc = re.search(r"^CRC = ([0-9A-F]+)$", block, re.MULTILINE)
        if not (path and size and crc):
            continue
        entries.append(
            {
                "volume": archive.name,
                "path": path.group(1).replace("\\", "/"),
                "size": int(size.group(1)),
                "crc32": crc.group(1),
            }
        )
    return entries


def run_probe() -> None:
    if not PROBE.is_file():
        raise SystemExit(f"missing {PROBE}")
    env = dict(os.environ)
    qemu = Path(r"C:\Program Files\qemu\qemu-system-i386.exe")
    if "QEMU_SYSTEM_I386" not in env and qemu.is_file():
        env["QEMU_SYSTEM_I386"] = str(qemu)
    result = subprocess.run(
        [sys.executable, str(PROBE)],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode:
        print(result.stdout, file=sys.stderr)
        raise SystemExit(f"DOS DEARJ probe failed with exit {result.returncode}")


def pull_probe_output() -> None:
    mcopy = shutil.which("mcopy") or str(Path(r"C:\msys64\mingw64\bin\mcopy.exe"))
    if not Path(mcopy).is_file():
        raise SystemExit("mcopy not found; install mtools or set it on PATH")
    geometry = json.loads((PROBE_WORK / "dearj.hdd.geom.json").read_text(encoding="utf-8"))
    image = f"{PROBE_WORK / 'dearj.hdd'}@@{geometry['part_offset']}"
    for directory in (FLAT, LOGS):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
    env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    subprocess.run(
        [mcopy, "-s", "-m", "-i", image, "::/OUT/*", FLAT.relative_to(ROOT).as_posix() + "/"],
        cwd=ROOT,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for index in range(len(ARCHIVES)):
        log = LOGS / f"A{index:02d}.LOG"
        subprocess.run(
            [mcopy, "-i", image, f"::/A{index:02d}.LOG", log.relative_to(ROOT).as_posix()],
            cwd=ROOT,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )


def main() -> int:
    if not all(path.is_file() for path in ARCHIVES):
        raise SystemExit("run work/stage_media.py first")
    existing = [p for p in GAME.rglob("*") if p.name != ".gitkeep"]
    if existing:
        raise SystemExit(f"refusing to overwrite non-empty game tree: {existing[0]}")

    seven = find_7zip()
    entries = [entry for archive in ARCHIVES for entry in parse_arj_entries(seven, archive)]
    by_path: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        by_path[entry["path"].upper()].append(entry)
    expected_split = {
        "DAT/A_036_6.SHP": ["DATA.A00", "DATA.A01"],
        "DAT/A_079_2.SHP": ["DATA.A01", "DATA.A02"],
        "DAT/FINALE.SHP": ["DATA.A02", "DATA.A03"],
        "EXE/GM2.BNK": ["DATA.A03", "DATA.A04"],
    }
    split = {
        path: [entry["volume"] for entry in parts]
        for path, parts in by_path.items()
        if len(parts) > 1
    }
    if (len(entries), len(by_path), split) != (889, 885, expected_split):
        raise SystemExit(
            f"unexpected ARJ inventory: {len(entries)} entries, {len(by_path)} logical files, {split}"
        )

    run_probe()
    pull_probe_output()
    flat_files = {path.name.upper(): path for path in FLAT.iterdir() if path.is_file()}
    if len(flat_files) != 885:
        raise SystemExit(f"DOS DEARJ produced {len(flat_files)} files, expected 885")

    logs = [log.read_bytes().decode("cp437", "replace") for log in sorted(LOGS.glob("A*.LOG"))]
    crc_ok = sum(log.count("CRC OK") for log in logs)
    crc_bad = sum(log.upper().count(token) for log in logs for token in ("CRC ERROR", "CRC BAD"))
    if (len(logs), crc_ok, crc_bad) != (5, 889, 0):
        raise SystemExit(f"unexpected DEARJ CRC report: {len(logs)} logs, {crc_ok} ok, {crc_bad} bad")

    GAME.mkdir(parents=True, exist_ok=True)
    files = []
    for upper_path in sorted(by_path):
        parts = by_path[upper_path]
        relative = Path(parts[0]["path"])
        flat_name = relative.name.upper()
        source = flat_files.get(flat_name)
        if source is None:
            raise SystemExit(f"DEARJ output missing {relative}")
        data = source.read_bytes()
        expected_size = sum(part["size"] for part in parts)
        if len(data) != expected_size:
            raise SystemExit(f"size mismatch for {relative}: {len(data)} != {expected_size}")
        if len(parts) == 1:
            actual_crc = f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"
            if actual_crc != parts[0]["crc32"]:
                raise SystemExit(f"CRC mismatch for {relative}: {actual_crc} != {parts[0]['crc32']}")
        target = GAME / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append(
            {
                "path": relative.as_posix(),
                "size": len(data),
                "sha256": sha256(data),
                "volumes": [part["volume"] for part in parts],
                "arj_crc32": [part["crc32"] for part in parts],
            }
        )

    manifest = {
        "source": {
            "archives": [str(path.relative_to(ROOT)) for path in ARCHIVES],
            "archive_sha256": [sha256(path.read_bytes()) for path in ARCHIVES],
            "command": "python work/extract_game.py",
            "utility": str((MEDIA / "disk1" / "DEARJ.EXE").relative_to(ROOT)),
            "utility_sha256": sha256((MEDIA / "disk1" / "DEARJ.EXE").read_bytes()),
            "arj_crc_check": "DOS DEARJ 2.30: 889 CRC OK, 0 bad",
        },
        "logical_files": len(files),
        "archive_entries": len(entries),
        "split_files": split,
        "uncompressed_bytes": sum(item["size"] for item in files),
        "files": files,
    }
    manifest_path = MEDIA / "game-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("DOS DEARJ CRC: 889 ok, 0 bad")
    print(f"logical files: {len(files)} from {len(entries)} volume entries")
    print(f"game bytes: {manifest['uncompressed_bytes']}")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
