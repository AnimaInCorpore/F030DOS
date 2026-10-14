#!/usr/bin/env python3
"""Switch the generated Falcon3 DOS image between bootstrap and game modes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dosimg

ROOT = Path(__file__).resolve().parents[1]
HDD = ROOT / "img" / "falcon3.hdd"
STAGE = ROOT / "work" / "img_build"

HIMEM = (
    b"DEVICE=C:\\DOS\\HIMEM.SYS\r\n"
    b"DOS=HIGH\r\n"
    b"FILES=20\r\n"
    b"BUFFERS=15\r\n"
)
PLAIN = b"FILES=20\r\nBUFFERS=15\r\n"
HEAD = b"@ECHO OFF\r\nPROMPT $P$G\r\nPATH C:\\DOS\r\n"
RUN_GAME = b"C:\r\nCD \\FALCON3\r\nFALCON3.EXE\r\n"

MODES = {
    "bootstrap": (PLAIN, None),
    "falcon3": (HIMEM, HEAD + RUN_GAME),
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in MODES:
        raise SystemExit(f"usage: set_boot_mode.py {{{'|'.join(MODES)}}}")
    if not HDD.is_file() or not (HDD.with_suffix(HDD.suffix + ".geom.json")).is_file():
        raise SystemExit("missing img/falcon3.hdd; build it first")

    config, autoexec = MODES[sys.argv[1]]
    part_off = json.loads((HDD.with_suffix(HDD.suffix + ".geom.json")).read_text())["part_offset"]
    for name, data in (("CONFIG.SYS", config), ("AUTOEXEC.BAT", autoexec)):
        if data is None:
            continue
        staged = STAGE / name
        staged.write_bytes(data)
        result = subprocess.run(
            [dosimg.host_tool("mcopy"), "-o", "-i",
             f"{HDD}@@{part_off}", str(staged), "::/" + name],
            capture_output=True, text=True,
            env=dict(os.environ, MTOOLS_SKIP_CHECK="1"),
        )
        if result.returncode:
            raise SystemExit(f"mcopy failed: {result.stdout}{result.stderr}")
    print(f'{HDD} set to mode "{sys.argv[1]}"')


if __name__ == "__main__":
    main()
