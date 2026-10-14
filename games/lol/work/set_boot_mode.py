#!/usr/bin/env python3
"""Rewrite the boot files inside img/lol.hdd without rebuilding the image."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dosimg


ROOT = Path(__file__).resolve().parents[1]
MSYS = Path(os.environ.get("F030_MSYS_BIN", r"C:\msys64\mingw64\bin"))
HDD = ROOT / "img" / "lol.hdd"
STAGE = ROOT / "work" / "img_build"

GEOM = HDD.with_suffix(HDD.suffix + ".geom.json")
if not GEOM.is_file():
    raise SystemExit(f"missing geometry sidecar: {GEOM}")
PART_OFF = json.loads(GEOM.read_text())["part_offset"]

MEMCFG = (b"DEVICE=C:\\DOS\\HIMEM.SYS\r\n"
          b"DOS=HIGH\r\n"
          b"FILES=80\r\n"
          b"BUFFERS=30\r\n")
HEAD = b"@ECHO OFF\r\nPROMPT $P$G\r\nPATH C:\\DOS\r\n"

MODES = {
    "bootstrap": (b"FILES=80\r\nBUFFERS=30\r\n", dosimg.expand_autoexec()),
    "xms": (MEMCFG, HEAD +
            b"ECHO === xms === > C:\\BOOT.LOG\r\n"
            b"VER >> C:\\BOOT.LOG\r\n"
            b"C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n"
            b"ECHO === xms done === >> C:\\BOOT.LOG\r\n"
            b"C:\\QUIT.COM\r\n"),
    "game": (MEMCFG, HEAD +
             b"ECHO === lands === > C:\\BOOT.LOG\r\n"
             b"C:\r\nCD \\LANDS\r\n"
             b"MAIN.EXE\r\n"
             b"ECHO --- MAIN.EXE returned --- >> C:\\BOOT.LOG\r\n"
             b"C:\\QUIT.COM\r\n"),
    "shell": (MEMCFG, HEAD + b"C:\r\nCD \\LANDS\r\n"),
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in MODES:
        raise SystemExit(f"usage: set_boot_mode.py {{{'|'.join(MODES)}}}")
    config, autoexec = MODES[sys.argv[1]]
    mcopy = MSYS / "mcopy.exe"
    if not mcopy.is_file():
        raise SystemExit(f"missing mcopy.exe under {MSYS}; set F030_MSYS_BIN")
    for name, data in (("CONFIG.SYS", config), ("AUTOEXEC.BAT", autoexec)):
        path = STAGE / name
        path.write_bytes(data)
        result = subprocess.run(
            [str(mcopy), "-o", "-i", f"{HDD}@@{PART_OFF}", str(path), "::/" + name],
            capture_output=True, text=True,
            env=dict(os.environ, MTOOLS_SKIP_CHECK="1"))
        if result.returncode:
            raise SystemExit(f"mcopy failed: {result.stdout}{result.stderr}")
    print(f"img/lol.hdd set to mode {sys.argv[1]!r}")


if __name__ == "__main__":
    main()
