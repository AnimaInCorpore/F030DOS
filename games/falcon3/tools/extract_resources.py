#!/usr/bin/env python3
"""Verify and extract Falcon 3.0's ZIP-based FALCON3.RES resource tree."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from zipfile import ZipFile


def safe_target(root: Path, member: str) -> Path:
    target = (root / member).resolve()
    root = root.resolve()
    if os.path.commonpath((str(root), str(target))) != str(root):
        raise SystemExit(f"archive member escapes output directory: {member!r}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=Path("game/cd/FALCON3.RES"))
    parser.add_argument("--output", type=Path,
                        default=Path("game/FALCON3"))
    args = parser.parse_args()

    if not args.source.is_file():
        raise SystemExit(
            f"missing {args.source}; extract assets/FALCON3.ISO to game/cd first")

    with ZipFile(args.source) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise SystemExit(f"ZIP CRC failure in {bad}")

        infos = archive.infolist()
        args.output.mkdir(parents=True, exist_ok=True)
        for info in infos:
            target = safe_target(args.output, info.filename)
            if info.is_dir() or info.filename.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))

    exe = args.output / "FALCON3.EXE"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest() if exe.is_file() else "(missing)"
    total = sum(i.file_size for i in infos)
    print(f"verified {len(infos)} ZIP members, {total} uncompressed bytes")
    print(f"extracted to {args.output}")
    print(f"FALCON3.EXE SHA-256: {digest}")


if __name__ == "__main__":
    main()
