#!/usr/bin/env python3
"""Build img/falcon3.hdd with the extracted Falcon 3.0 tree.

The genuine MS-DOS 6.22 floppies are intentionally not included. Put them
under img/ (or set F030_DOS_FLOPPIES) before running this script. The game tree
comes from tools/extract_resources.py and remains a pristine host reference.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dosimg

ROOT = Path(__file__).resolve().parents[1]
FLOPPIES = Path(os.environ.get(
    "F030_DOS_FLOPPIES",
    str(ROOT / "img" / "Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)")))
GAME = ROOT / "game" / "FALCON3"
WORK = ROOT / "work" / "img_build"
OUT = ROOT / "img" / "falcon3.hdd"


def main() -> None:
    if not GAME.is_dir() or not (GAME / "FALCON3.EXE").is_file():
        raise SystemExit(
            "missing game/FALCON3/FALCON3.EXE; run python "
            "tools/extract_resources.py first")
    if not FLOPPIES.is_dir():
        raise SystemExit(
            f"missing DOS floppy directory {FLOPPIES}; set F030_DOS_FLOPPIES")

    mbr = WORK / "mbr.bin"
    dosimg._verify_mbr(str(ROOT / "work" / "mbr.asm"), str(mbr))
    image = dosimg.DosImage(str(OUT), size_mb=64, floppy_dir=str(FLOPPIES),
                            work_dir=str(WORK), label="FALCON3_DOS")
    print(f"game files: {image.add_tree('/FALCON3', str(GAME))}")
    # First boot expands the genuine KWAJ-compressed DOS drivers.  The image is
    # switched to HIMEM/DOS=HIGH after that bootstrap completes.
    image.add_bytes(b"FILES=20\r\nBUFFERS=15\r\n", "/CONFIG.SYS")
    image.add_bytes(dosimg.expand_autoexec(), "/AUTOEXEC.BAT")
    image.write()

    if "--no-boot" not in sys.argv:
        subprocess.check_call([
            sys.executable, str(ROOT / "work" / "run_qemu.py"),
            "--timeout", "60", "--cat", "::/BOOT.LOG",
        ])
        subprocess.check_call([
            sys.executable, str(ROOT / "work" / "set_boot_mode.py"),
            "falcon3",
        ])


if __name__ == "__main__":
    main()
