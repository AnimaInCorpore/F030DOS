#!/usr/bin/env python3
"""Build img/lol.hdd with the staged English DOS install."""

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
INSTALL = ROOT / "work" / "install" / "LANDS"
WORK = ROOT / "work" / "img_build"
OUT = ROOT / "img" / "lol.hdd"


def main() -> None:
    if not (INSTALL / "MAIN.EXE").is_file():
        raise SystemExit(
            "missing staged install; run python tools/extract_cd.py and "
            "python tools/stage_install.py first")
    if not FLOPPIES.is_dir():
        raise SystemExit(
            f"missing DOS floppy directory {FLOPPIES}; set F030_DOS_FLOPPIES")

    mbr = WORK / "mbr.bin"
    dosimg._verify_mbr(str(ROOT / "work" / "mbr.asm"), str(mbr))
    image = dosimg.DosImage(str(OUT), size_mb=512, floppy_dir=str(FLOPPIES),
                            work_dir=str(WORK), label="LOL_DOS")
    print(f"game files: {image.add_tree('/LANDS', str(INSTALL))}")
    image.add_bytes(b"FILES=80\r\nBUFFERS=30\r\n", "/CONFIG.SYS")
    image.add_bytes(dosimg.expand_autoexec(), "/AUTOEXEC.BAT")
    image.write()

    if "--no-boot" not in sys.argv:
        subprocess.check_call([
            sys.executable, str(ROOT / "work" / "run_qemu.py"),
            "--timeout", "60", "--cat", "::/BOOT.LOG",
        ])
        subprocess.check_call([
            sys.executable, str(ROOT / "work" / "set_boot_mode.py"), "xms",
        ])


if __name__ == "__main__":
    main()
