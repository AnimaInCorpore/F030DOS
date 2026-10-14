#!/usr/bin/env python3
"""Test and extract the reconstructed INDYCAR LHA archive."""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


def seven_zip() -> str:
    candidates = [
        shutil.which("7z"),
        shutil.which("7zz"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files\7-Zip\7zz.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit("7-Zip is required to test/extract the LHA archive")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path,
                        default=Path(__file__).resolve().parents[2])
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    archive = project / "work" / "INDYCAR.MERGED"
    output = project / "game" / "installed"
    if not archive.is_file():
        raise SystemExit("run merge_indycar.py before extract_install.py")
    exe = seven_zip()
    subprocess.run([exe, "t", str(archive)], check=True)
    if args.test_only:
        return 0
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([exe, "x", "-y", f"-o{output}", str(archive)], check=True)
    print(f"extracted installed tree to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
