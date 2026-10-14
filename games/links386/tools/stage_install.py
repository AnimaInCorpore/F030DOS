#!/usr/bin/env python3
"""Stage the files named by the Links CD installation manifest."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "game" / "cd"
DEFAULT_OUTPUT = ROOT / "work" / "install" / "LINKS386"


def manifest_files(path: Path, profile: str) -> list[str]:
    sections = ["MIN_INSTALL"]
    if profile == "max":
        sections.append("MAX_INSTALL")
    result: list[str] = []
    active = None
    seen = set()
    found_sections = set()
    for raw in path.read_text(encoding="ascii").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            active = line[1:-1].strip().upper()
            found_sections.add(active)
            continue
        if active not in sections or not line.lower().startswith("file"):
            continue
        _, value = line.split("=", 1)
        value = value.strip().replace("\\", "/")
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    missing = [section for section in sections if section not in found_sections]
    if missing:
        raise SystemExit(f"missing [{missing[0]}] in {path}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", choices=("min", "max"), default="min")
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    manifest = source / "INSTALL.INI"
    if not manifest.is_file():
        raise SystemExit(f"missing {manifest}; run tools/extract_cd.py first")

    names = manifest_files(manifest, args.profile)
    # The default staging tree is entirely derived. Clear it so switching from
    # --profile max back to the minimum install cannot leave optional courses
    # in the supposedly minimum tree. A caller-provided output is left alone
    # and receives the listed files only.
    if output == DEFAULT_OUTPUT.resolve() and output.is_dir():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    copied = 0
    total = 0
    for name in names:
        src = (source / name).resolve()
        if source not in src.parents or not src.is_file():
            raise SystemExit(f"manifest member missing from CD: {name}")
        # The installer manifest names source subdirectories, but the installed
        # game keeps these files in its root directory.
        dst = output / Path(name).name
        shutil.copyfile(src, dst)
        copied += 1
        total += dst.stat().st_size
    print(f"staged {copied} files, {total} bytes ({args.profile}) to {output}")


if __name__ == "__main__":
    main()
