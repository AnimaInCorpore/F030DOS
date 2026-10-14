#!/usr/bin/env python3
"""Stage an English hard-drive install tree from the extracted CD."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "game" / "cd"
DEFAULT_OUTPUT = ROOT / "work" / "install" / "LANDS"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    data = source / "DATA"
    harddrive = data / "HARDRIVE"
    required = [data / "ENG" / "LANDS.EXE", harddrive / "MAIN.EXE",
                harddrive / "ENG.LM"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("missing extracted CD files:\n" + "\n".join(missing))

    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(data, output / "DATA", dirs_exist_ok=True)
    # MAIN.EXE is the installed DOS variant. Keep the CD LANDS.EXE beside it
    # for controlled comparison, not as a silent replacement.
    shutil.copyfile(harddrive / "MAIN.EXE", output / "MAIN.EXE")
    shutil.copyfile(data / "ENG" / "LANDS.EXE", output / "LANDS.EXE")
    shutil.copyfile(harddrive / "ENG.LM", output / "ENG.LM")
    for name in ("LOLCD.EXE", "VISBIOS.COM", "VWWSD.386", "VDSPD.386",
                 "SETUP.EXE"):
        path = harddrive / name
        if path.is_file():
            shutil.copyfile(path, output / name)

    files = [p for p in output.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    print(f"staged {len(files)} files, {total} bytes to {output}")


if __name__ == "__main__":
    main()
