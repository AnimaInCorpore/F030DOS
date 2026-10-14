#!/usr/bin/env python3
"""Build a bootable DOS image containing the Magic Carpet runtime trees."""

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
CARPET = ROOT / "game" / "MagCarp" / "CARPET"
CARPET_CD = ROOT / "game" / "MagCarp" / "CARPET.CD"
WORK = ROOT / "work" / "img_build"
OUT = ROOT / "img" / "magiccarpet.hdd"


def main() -> None:
    if not (CARPET / "CARPET.EXE").is_file():
        raise SystemExit(
            "missing game/MagCarp/CARPET/CARPET.EXE; run "
            "python tools/extract_archive.py first")
    if not CARPET_CD.is_dir():
        raise SystemExit(
            "missing game/MagCarp/CARPET.CD; run "
            "python tools/extract_archive.py first")
    if not FLOPPIES.is_dir():
        raise SystemExit(
            f"missing DOS floppy directory {FLOPPIES}; set F030_DOS_FLOPPIES")

    mbr = WORK / "mbr.bin"
    dosimg._verify_mbr(str(ROOT / "work" / "mbr.asm"), str(mbr))
    image = dosimg.DosImage(str(OUT), size_mb=256, floppy_dir=str(FLOPPIES),
                            work_dir=str(WORK), label="MAGICCARPET")
    print(f"game files: {image.add_tree('/CARPET', str(CARPET))}")
    print(f"CD files: {image.add_tree('/CARPET.CD', str(CARPET_CD))}")
    image.add_bytes(b"FILES=40\r\nBUFFERS=30\r\n", "/CONFIG.SYS")
    then = b"CD \\CARPET\r\n"
    if "--run-game" in sys.argv:
        then += b"CARPET.EXE\r\n"
    then += b"C:\\QUIT.COM\r\n"
    image.add_bytes(dosimg.expand_autoexec(then), "/AUTOEXEC.BAT")
    image.write()

    if "--no-boot" not in sys.argv:
        subprocess.check_call([
            sys.executable, str(ROOT / "work" / "run_qemu.py"),
            "--timeout", "60", "--cat", "::/BOOT.LOG",
        ])


if __name__ == "__main__":
    main()
