#!/usr/bin/env python3
"""Rewrite the derived Links DOS boot files after the bootstrap pass.

The first boot expands the genuine DOS ``.??_`` files in AUTOEXEC.BAT.  A
second boot can then load the expanded HIMEM/EMM386 drivers from CONFIG.SYS;
DOS/4G needs that memory-manager setup before LCD.EXE is launched.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dosimg


ROOT = Path(__file__).resolve().parents[1]
HDD = ROOT / "img" / "links386.hdd"
STAGE = ROOT / "work" / "img_build"
PART_OFF = json.loads((HDD.with_suffix(HDD.suffix + ".geom.json")).read_text())["part_offset"]

MEMCFG = (b"DEVICE=C:\\DOS\\HIMEM.SYS\r\n"
          b"DEVICE=C:\\DOS\\EMM386.EXE NOEMS\r\n"
          b"DOS=HIGH,UMB\r\n"
          b"FILES=30\r\n"
          b"BUFFERS=30\r\n")


def autoexec(game: bool, mouse_driver: str | None = None) -> bytes:
    out = [b"@ECHO OFF\r\n", b"PROMPT $P$G\r\n", b"PATH C:\\DOS\r\n",
           b"ECHO === ems === > C:\\BOOT.LOG\r\n",
           b"VER >> C:\\BOOT.LOG\r\n",
           b"C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n"]
    if game:
        if mouse_driver:
            out.append((mouse_driver + " >> C:\\BOOT.LOG\r\n").encode())
        out += [b"C:\r\n", b"CD \\LINKS386\r\n", b"GOLFCD.BAT\r\n"]
    else:
        out += [b"ECHO === ems done === >> C:\\BOOT.LOG\r\n"]
    out.append(b"C:\\QUIT.COM\r\n")
    return b"".join(out)


def install(name: str, data: bytes) -> None:
    stage = STAGE / ("mode_" + name)
    stage.write_bytes(data)
    env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    p = subprocess.run([
        dosimg.host_tool("mcopy"), "-o", "-i", f"{HDD}@@{PART_OFF}",
        str(stage), "::/" + name,
    ], capture_output=True, text=True, env=env)
    if p.returncode:
        raise SystemExit(f"mcopy failed: {p.stdout}{p.stderr}")


def main() -> None:
    if len(sys.argv) not in {2, 3} or sys.argv[1] not in {"ems", "game"}:
        raise SystemExit("usage: python work/set_boot_mode.py {ems|game} [--no-mouse]")
    no_mouse = len(sys.argv) == 3 and sys.argv[2] == "--no-mouse"
    if len(sys.argv) == 3 and not no_mouse:
        raise SystemExit("usage: python work/set_boot_mode.py {ems|game} [--no-mouse]")
    if no_mouse and sys.argv[1] != "game":
        raise SystemExit("--no-mouse is only valid with game mode")
    if not HDD.is_file():
        raise SystemExit(f"missing {HDD}; build it first")
    mouse_driver = None
    if sys.argv[1] == "game" and not no_mouse:
        candidates = ("MOUSE33.COM", "FAKEMOUS.COM")
        for candidate in candidates:
            mouse = STAGE / candidate
            if mouse.is_file():
                mouse_driver = candidate
                install(candidate, mouse.read_bytes())
                break
        if mouse_driver is None:
            raise SystemExit(f"missing derived mouse driver in {STAGE}")
    install("CONFIG.SYS", MEMCFG)
    install("AUTOEXEC.BAT", autoexec(sys.argv[1] == "game", mouse_driver))
    suffix = " without mouse driver" if no_mouse else ""
    print(f"img/links386.hdd set to mode {sys.argv[1]!r}{suffix}")


if __name__ == "__main__":
    main()
