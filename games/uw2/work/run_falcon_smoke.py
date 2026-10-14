#!/usr/bin/env python3
"""Run the assembled RGB565 fixture in Hatari and compare its page.

The first debugger pass reads a register that the smoke program deliberately
leaves live, deriving the TOS load base from the linked symbol offset.  The
second pass reads the status word and saves the generated page.  This keeps
the check independent of TOS's current TPA placement while preserving the
target-execution evidence required by the porting method.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path

from check_falcon_present import check_listing, check_map, expected_frame


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUILD = ROOT / "build" / "falcon"
DEFAULT_HATARI = Path("/opt/homebrew/bin/hatari")
DEFAULT_TOS = ROOT / ".." / "F030Arcade" / "third_party" / "tos" / "tos404.img"
PROGRAM_NAME = "uw2-falcon-smoke.tos"


def run_hatari(hatari: Path, tos: Path, program: Path, parse: Path,
               log: Path, vbl: int, timeout: int) -> None:
    command = [
        str(hatari),
        "--memsize", "14",
        "--tos", str(tos),
        "--fast-boot", "true",
        "--cpu-exact", "true",
        "--compatible", "true",
        "--patch-tos", "true",
        "--monitor", "rgb",
        "--machine", "falcon",
        "--confirm-quit", "off",
        "--mmu", "true",
        "--fast-forward", "true",
        "--sound", "off",
        "--disable-video", "on",
        "--run-vbls", str(vbl + 50),
        "--parse", str(parse),
        "--log-file", str(log),
        str(program),
    ]
    try:
        subprocess.run(command, cwd=program.parent, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"Hatari did not finish within {timeout}s") from exc


def symbol_offset(map_text: str, symbol: str) -> int:
    match = re.search(r"0x([0-9a-fA-F]+)\s+" + re.escape(symbol) + r"\s*:", map_text)
    if not match:
        raise SystemExit(f"link map has no symbol {symbol}")
    return int(match.group(1), 16)


def register_value(log: Path, register: str) -> int:
    text = log.read_text()
    match = re.search(r"\b" + register + r"\s+([0-9A-Fa-f]{8})\b", text)
    if not match:
        raise SystemExit(f"Hatari register log has no {register}: {log}")
    return int(match.group(1), 16)


def status_word(log: Path) -> bool:
    text = log.read_text()
    return bool(re.search(r"[0-9A-Fa-f]{8}:\s+a5\s+5a\b", text, re.IGNORECASE))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD)
    ap.add_argument("--hatari", type=Path,
                    default=Path(os.environ.get("HATARI", str(DEFAULT_HATARI))))
    ap.add_argument("--tos", type=Path,
                    default=Path(os.environ.get("TOS", str(DEFAULT_TOS))))
    ap.add_argument("--vbl", type=int, default=800)
    ap.add_argument("--timeout", type=int, default=45)
    args = ap.parse_args()

    build = args.build_dir.resolve()
    listing = build / "present.lst"
    link_map = build / "uw2-falcon-smoke.map"
    program = build / PROGRAM_NAME
    if not args.hatari.is_file() or not args.tos.is_file() or not program.is_file():
        raise SystemExit("Hatari, TOS image, and smoke program are required")
    check_listing(listing)
    check_map(link_map)

    map_text = link_map.read_text()
    pixels_offset = symbol_offset(map_text, "falcon_smoke_pixels")
    status_offset = symbol_offset(map_text, "falcon_smoke_status")
    frame_offset = symbol_offset(map_text, "falcon_smoke_frame")
    frame_bytes = len(expected_frame())

    with tempfile.TemporaryDirectory(prefix="uw2-falcon-smoke-") as temp:
        temp_dir = Path(temp)
        first_log = temp_dir / "registers.log"
        first_parse = temp_dir / "debug.ini"
        first_probe = temp_dir / "probe.ini"
        first_parse.write_text(
            f"logfile {first_log}\n"
            f"b VBL = {args.vbl} :once :file {first_probe}\n"
        )
        first_probe.write_text("r\nquit\n")
        run_hatari(args.hatari.resolve(), args.tos.resolve(), program.resolve(),
                   first_parse, temp_dir / "hatari.log", args.vbl, args.timeout)
        runtime_base = register_value(first_log, "A0") - pixels_offset

        second_log = temp_dir / "status.log"
        second_parse = temp_dir / "debug.ini"
        second_probe = temp_dir / "probe.ini"
        capture = build / "hatari-smoke-frame.bin"
        second_parse.write_text(
            f"logfile {second_log}\n"
            f"b VBL = {args.vbl} :once :file {second_probe}\n"
        )
        second_probe.write_text(
            f"m ${runtime_base + status_offset:X} 2\n"
            f"savebin {capture} ${runtime_base + frame_offset:X} ${frame_bytes:X}\n"
            "quit\n"
        )
        run_hatari(args.hatari.resolve(), args.tos.resolve(), program.resolve(),
                   second_parse, temp_dir / "hatari.log", args.vbl, args.timeout)
        if not status_word(second_log):
            raise SystemExit("Hatari smoke status word was not A55A")

    captured = capture.read_bytes()
    expected = expected_frame()
    if captured != expected:
        raise SystemExit(
            f"Hatari smoke mismatch: expected {len(expected)} bytes, "
            f"captured {len(captured)} bytes"
        )
    print(f"Hatari smoke: PASS (base=${runtime_base:X}, {len(captured)} bytes byte-identical)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
