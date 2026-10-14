#!/usr/bin/env python3
"""Capture Falcon flight-publish rows from a current debug image.

Hatari's debugger runs ``sample.ini`` at the translated equivalent of the DOS
flight boundary.  The resulting rows are joined to DOS/JavaScript by the
DEMO*.SCR file cursor, not by wall-clock VBLs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOS = ROOT.parent / "F030Arcade" / "third_party" / "tos" / "etos512de.img"

FIELDS = [
    ("flt_x", 4, True, "x_0x19CD4"),
    ("flt_y", 4, True, "y_0x19CD8"),
    ("flt_angle", 4, False, "angle_0x19D04"),
    ("flt_turn", 4, True, "turn_0x19D08"),
    ("flt_fwd", 4, True, "fwd_0x19CC8"),
    ("flt_lat", 4, True, "lat_0x19CD0"),
    ("flt_roll", 4, True, "roll_0x19CF0"),
    ("flt_pitch", 4, True, "pitch_0x19CF4"),
    ("player_altitude", 1, False, "alt_0x19DFC"),
    ("demo_cursor", 4, False, "cursor_0x19ECC"),
    ("demo_active", 2, False, "demo_active"),
    ("attract_demo_pass", 2, False, "pass"),
    ("view_variant", 1, False, "variant"),
    ("view_angle", 4, False, "view_angle_0x19D00"),
    ("player_x", 4, True, "player_x"),
    ("player_y", 4, True, "player_y"),
]

# The eight flight dwords are adjacent in the target's data segment. Reading
# them as one block cuts debugger traffic almost in half, which matters on the
# slow 68060 interpreter while leaving the decoded fields and their signedness
# unchanged.
FLIGHT_BLOCK = [
    ("flt_x", 4, True, "x_0x19CD4", 0),
    ("flt_y", 4, True, "y_0x19CD8", 4),
    ("flt_angle", 4, False, "angle_0x19D04", 8),
    ("flt_turn", 4, True, "turn_0x19D08", 12),
    ("flt_fwd", 4, True, "fwd_0x19CC8", 16),
    ("flt_lat", 4, True, "lat_0x19CD0", 20),
    ("flt_roll", 4, True, "roll_0x19CF0", 24),
    ("flt_pitch", 4, True, "pitch_0x19CF4", 28),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_debugger_files(out: Path, program: Path, last_cursor: int) -> None:
    (out / "boot.ini").write_text(
        "b GemdosOpcode = $4b && OsCallParam = 0 :trace :once :file program.ini\n",
        encoding="utf-8",
    )
    (out / "program.ini").write_text(
        "b pc = TEXT :trace :once :file arm.ini\n", encoding="utf-8"
    )
    (out / "arm.ini").write_text(
        f"symbols {program.resolve()}\n"
        "b pc = flight_publish :trace :file sample.ini\n"
        f"b demo_cursor = {last_cursor} :once :file done.ini\n"
        "b pc = exc_report :once :file failed.ini\n",
        encoding="utf-8",
    )
    commands = ["m b flt_x 32"]
    commands.extend(f"m b {symbol} {size}" for symbol, size, _, _ in FIELDS[8:])
    (out / "sample.ini").write_text("\n".join(commands) + "\n", encoding="utf-8")
    (out / "done.ini").write_text("quit\n", encoding="utf-8")
    (out / "failed.ini").write_text("r\nd pc 8\nquit\n", encoding="utf-8")


def parse_rows(log: str, wanted: int) -> list[dict]:
    command = re.compile(r"^>\s+m\s+b\s+(\w+)\s+(\d+)")
    values: dict[str, int] = {}
    rows: list[dict] = []
    last_symbol = None
    last_size = None
    pending_tokens: list[str] = []
    by_symbol = {symbol: (size, signed, name) for symbol, size, signed, name in FIELDS}
    for line in log.splitlines():
        line = line.strip()
        match = command.match(line)
        if match:
            last_symbol = match.group(1)
            last_size = int(match.group(2))
            pending_tokens = []
            continue
        if last_symbol is None or last_symbol not in by_symbol or ":" not in line:
            continue
        _, payload = line.split(":", 1)
        tokens = [token for token in payload.split() if re.fullmatch(r"[0-9A-Fa-f]{2}", token)]
        if last_symbol == "flt_x" and last_size == 32:
            pending_tokens.extend(tokens)
            if len(pending_tokens) < 32:
                continue
            raw = bytes.fromhex("".join(pending_tokens[:32]))
            for symbol, size, signed, _, offset in FLIGHT_BLOCK:
                values[symbol] = int.from_bytes(raw[offset:offset + size], "big", signed=signed)
            last_symbol = None
            last_size = None
            pending_tokens = []
            continue
        size, signed, _ = by_symbol[last_symbol]
        if len(tokens) < size:
            continue
        raw = bytes.fromhex("".join(tokens[:size]))
        values[last_symbol] = int.from_bytes(raw, "big", signed=signed)
        last_symbol = None
        last_size = None
        pending_tokens = []
        if len(values) != len(FIELDS):
            continue
        row = {name: values[symbol] for symbol, _, _, name in FIELDS}
        rows.append(row)
        values = {}
        # Do not stop at ``wanted`` raw samples: the first publish is the
        # attract-mode setup sample (cursor 0), so filtering it first is
        # necessary to retain exactly ``wanted`` replay records.

    # View commands can re-enter the frame driver. Keep the first published
    # row for each replay cursor so a cursor remains a single join key.
    unique = []
    seen = set()
    for row in rows:
        cursor = row["cursor_0x19ECC"]
        if cursor < 21 or cursor in seen or row["demo_active"] != 1:
            continue
        seen.add(cursor)
        unique.append(row)
    return unique[:wanted]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, choices=(68030, 68060), required=True)
    # 284 records is the supported DEMO1 boundary: record index 284 (the 285th)
    # is the no-damage bounce, DOS 00019461, that arms the screen shake. Its
    # display consumers are not recovered, so the Falcon parity trace stops the
    # armed presentation there; the browser-only target witness uses the
    # documented crop adaptation (analysis/functions/browser-attract.md#shake-timer).
    ap.add_argument("--records", type=int, default=284)
    ap.add_argument("--program-dir", type=Path)
    ap.add_argument("--program", default="comanche_d.tos")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--run-vbls", type=int)
    ap.add_argument("--timeout", type=int, default=480)
    ap.add_argument("--transcript", type=Path,
                    help="parse an existing Hatari debugger transcript without rerunning it")
    args = ap.parse_args()

    program_dir = (args.program_dir or (ROOT / ("release" if args.cpu == 68030 else "release/68060"))).resolve()
    program = program_dir / args.program
    if not program.is_file():
        ap.error(f"missing debug program: {program}")
    out = (args.out or (ROOT / f"build/acceptance/three-way/falcon-{args.cpu}.json")).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    run_vbls = args.run_vbls or (24000 if args.cpu == 68030 else 160000)
    hatari = os.environ.get("HATARI") or shutil.which("hatari")
    if not hatari:
        ap.error("hatari not found; set HATARI")
    tos = Path(os.environ.get("TOS", str(DEFAULT_TOS))).resolve()
    if not tos.is_file():
        ap.error(f"missing TOS image: {tos}; set TOS")

    last_cursor = 21 + (8 * (args.records - 1))
    write_debugger_files(out.parent, program, last_cursor)
    log_path = out.parent / f"falcon-{args.cpu}.hatari.log"
    command = [
        hatari,
        # Hatari expects the CPU suffix (3/6), not the full 68030/68060
        # number.  The latter is the label used in the artifact filenames.
        "--machine", "falcon", "--cpulevel", str((args.cpu // 10) % 10),
        "--memsize", "14", "--tos", str(tos), "--patch-tos", "true",
        "--mmu", "true", "--fpu", "none", "--dsp", "off", "--frameskips", "0",
        "--monitor", "rgb", "--fast-boot", "true", "--sound", "off",
        "--fast-forward", "true", "--cpu-exact", "true", "--compatible", "true",
        "--confirm-quit", "off", "--disable-video", "on", "--run-vbls", str(run_vbls),
        "--harddrive", str(program_dir), "--auto", r"C:\comanche_d.tos",
        "--parse", str(out.parent / "boot.ini"), "--log-file", str(log_path),
        "--alert-level", "fatal",
    ]
    (out.parent / f"falcon-{args.cpu}.command.json").write_text(
        json.dumps(command, indent=2) + "\n", encoding="utf-8"
    )
    if args.transcript:
        transcript_path = args.transcript.resolve()
        if not transcript_path.is_file():
            ap.error(f"missing debugger transcript: {transcript_path}")
        transcript = transcript_path.read_text(errors="replace")
        hatari_log = ""
    else:
        try:
            completed = subprocess.run(
                command, cwd=out.parent, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, timeout=args.timeout, check=False,
            )
        except subprocess.TimeoutExpired as error:
            (out.parent / f"falcon-{args.cpu}.stdout.txt").write_text(
                (error.stdout or "") if isinstance(error.stdout, str) else "", encoding="utf-8"
            )
            print(f"Hatari timed out after {args.timeout}s", file=sys.stderr)
            return 1
        transcript = completed.stdout or ""
        (out.parent / f"falcon-{args.cpu}.stdout.txt").write_text(transcript, encoding="utf-8")
        # Hatari's debugger transcript is emitted on stdout; --log-file only
        # contains the emulator's runtime log.  Keep both in the artifact, but
        # parse the transcript for memory samples.
        hatari_log = log_path.read_text(errors="replace") if log_path.is_file() else ""
    rows = parse_rows(transcript, args.records)
    result = {
        "implementation": "falcon",
        "cpu": args.cpu,
        "program": str(program),
        "program_sha256": sha256(program),
        "tos": str(tos),
        "tos_sha256": sha256(tos),
        "run_vbls": run_vbls,
        "records_requested": args.records,
        "records_captured": len(rows),
        "status": "PASS" if len(rows) == args.records else "UNPROVEN",
        "rows": rows,
    }
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['status']} MC{args.cpu}: {len(rows)}/{args.records} flight-publish rows -> {out}")
    if not rows:
        print(transcript[-3000:] or hatari_log[-3000:], file=sys.stderr)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
