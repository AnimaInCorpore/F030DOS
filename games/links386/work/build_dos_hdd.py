#!/usr/bin/env python3
"""Build a bootable DOS image containing the staged minimum Links install."""

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
INSTALL = ROOT / "work" / "install" / "LINKS386"
WORK = ROOT / "work" / "img_build"
OUT = ROOT / "img" / "links386.hdd"


def main() -> None:
    if not (INSTALL / "LCD.EXE").is_file():
        raise SystemExit(
            "missing staged install; run python tools/extract_cd.py and "
            "python tools/stage_install.py first")
    if not FLOPPIES.is_dir():
        raise SystemExit(
            f"missing DOS floppy directory {FLOPPIES}; set F030_DOS_FLOPPIES")

    mbr = WORK / "mbr.bin"
    dosimg._verify_mbr(str(ROOT / "work" / "mbr.asm"), str(mbr))
    image = dosimg.DosImage(str(OUT), size_mb=64, floppy_dir=str(FLOPPIES),
                            work_dir=str(WORK), label="LINKS386_DOS")
    print(f"game files: {image.add_tree('/LINKS386', str(INSTALL))}")
    image.add_bytes(b"FILES=40\r\nBUFFERS=20\r\n", "/CONFIG.SYS")
    then = b"CD \\LINKS386\r\n"
    if "--run-game" in sys.argv:
        then += b"GOLFCD.BAT\r\n"
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
