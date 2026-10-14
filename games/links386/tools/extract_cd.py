#!/usr/bin/env python3
"""Extract the supplied ISO9660 CD image into the pristine reference tree."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "assets" / "Links 386 CD (1995)(Access Software).iso"
DEFAULT_OUTPUT = ROOT / "game" / "cd"


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
    tar = shutil.which("tar")
    if tar is None:
        raise SystemExit("tar is required to read the ISO9660 image")
    subprocess.run([tar, "-xf", str(source), "-C", str(output)], check=True)

    exe = output / "LCD.EXE"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest() if exe.is_file() else "(missing)"
    files = [p for p in output.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print(f"extracted {len(files)} files, {total} bytes to {output}")
    print(f"LCD.EXE SHA-256: {digest}")


if __name__ == "__main__":
    main()
