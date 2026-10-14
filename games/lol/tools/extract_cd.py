#!/usr/bin/env python3
"""Extract the supplied ISO9660 image into the pristine reference tree."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "assets" / "LOL_CD_001.iso"
DEFAULT_OUTPUT = ROOT / "game" / "cd"


def archive_tool() -> str:
    for name in ("7z", "7zz", "7za"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        Path(r"C:\Program Files\7-Zip\7z.exe"),
        Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    raise SystemExit("7-Zip (7z/7zz/7za) is required to read this ISO")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise SystemExit(f"missing source image: {source}")
    if output == source or output in source.parents:
        raise SystemExit("output must not be the source image or its parent")

    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([archive_tool(), "x", "-y", str(source), f"-o{output}"],
                   check=True)
    files = [p for p in output.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    exe = output / "DATA" / "ENG" / "LANDS.EXE"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest() if exe.is_file() else "(missing)"
    print(f"extracted {len(files)} files, {total} bytes to {output}")
    print(f"LANDS.EXE SHA-256: {digest}")


if __name__ == "__main__":
    main()
