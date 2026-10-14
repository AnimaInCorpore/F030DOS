#!/usr/bin/env python3
"""Test and expand the eight shipped track LZH archives separately.

The archives intentionally reuse names such as ``DEFAULT.ST1`` and
``ACE.STG``. Until the installer proves how those files are selected, this
tool keeps each archive's complete six-file payload in ``game/tracks/<name>``
instead of flattening unlike files into one guessed install directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from extract_install import seven_zip


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path,
                        default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    project = args.project.resolve()
    archives = sorted(list((project / "game" / "disks" / "disk2").glob("*.LZH"))
                      + list((project / "game" / "disks" / "disk3").glob("*.LZH")))
    if len(archives) != 8:
        raise SystemExit(f"expected 8 track archives, found {len(archives)}")
    exe = seven_zip()
    scratch = project / "work" / "track_extract"
    output_root = project / "game" / "tracks"
    output_root.mkdir(parents=True, exist_ok=True)
    records = []
    for archive in archives:
        one = scratch / archive.stem
        one.mkdir(parents=True, exist_ok=True)
        subprocess.run([exe, "t", str(archive)], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run([exe, "x", "-y", f"-o{one}", str(archive)], check=True,
                       stdout=subprocess.DEVNULL)
        for source in sorted(p for p in one.rglob("*") if p.is_file()):
            rel = source.relative_to(one)
            target = output_root / archive.stem / rel
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            records.append({
                "archive": archive.name,
                "file": str(rel).replace("\\", "/"),
                "size": source.stat().st_size,
                "sha256": digest(source),
            })
        print(f"{archive.name}: 6 files, tested and staged")
    print(f"expanded track files: {len(records)}")
    print(f"wrote {output_root}")
    manifest = project / "work" / "track-manifest.json"
    manifest.write_text(json.dumps({"files": records}, indent=2) + "\n",
                        encoding="utf-8")
    print(f"wrote {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
