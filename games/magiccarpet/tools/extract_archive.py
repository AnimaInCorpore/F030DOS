#!/usr/bin/env python3
"""Verify and extract the supplied Magic Carpet Plus ZIP archive."""

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
                        default=Path("assets/Magic_Carpet_Plus_1995.zip"))
    parser.add_argument("--output", type=Path, default=Path("game"))
    args = parser.parse_args()

    if not args.source.is_file():
        raise SystemExit(f"missing source archive: {args.source}")

    digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
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

    files = [info for info in infos if not info.is_dir()]
    total = sum(info.file_size for info in files)
    print(f"source SHA-256: {digest}")
    print(f"verified {len(infos)} ZIP members, {len(files)} files, "
          f"{total} uncompressed bytes")
    print(f"extracted to {args.output}")


if __name__ == "__main__":
    main()
