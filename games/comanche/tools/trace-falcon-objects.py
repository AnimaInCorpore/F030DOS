#!/usr/bin/env python3
"""Sample the Falcon object table after every update pass and compare it to DOS.

DOS side: ``work/trace_replay_flight.py --objects`` stops the shipped executable
at 000234CE - every slot's state handler has run, nothing has drawn - and writes
the per-slot arrays one row per pass (``work/replay_dos/objects-demo1.json``).

Falcon side: Hatari's debugger stops at ``object_update_done`` (the same instant,
``src/object.s``), dumps ``object_table`` and the four countermeasure bytes, and
this tool decodes the Falcon struct (``OBJ_*`` in ``src/object.s``).  Rows are
joined by ``demo_cursor``, which both machines step in the same 8-byte records,
so a pass is the same pass on both sides.

Positions are the original's own 10.22 on both sides, compared exactly (a
tolerance in LSBs is available for runs that are not expected to be bit-exact).

N/A - target artefact: an oracle probe, no DOS routine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOS = ROOT / "tools" / "toolchain" / "tos402.rom"

OBJ_COUNT = 130
OBJ_SIZE = 100
# (name, offset, width, signed) - src/object.s OBJ_*.  Names match the keys of
# work/trace_replay_flight.py --objects where DOS has the array.
FIELDS = [
    ("speed", 0, 4, True), ("draw", 4, 4, False), ("state", 8, 4, False),
    ("x", 20, 4, True), ("y", 24, 4, True),
    ("prev_x", 28, 4, True), ("prev_y", 32, 4, True),
    ("heading", 36, 1, False), ("active", 37, 1, False),
    ("altitude", 38, 1, False), ("timer", 40, 1, False),
    ("health", 41, 1, False), ("prev_alt", 42, 1, False),
    ("sprite", 43, 1, False), ("steer", 52, 1, False), ("aux", 53, 1, False),
    ("flag", 54, 1, False), ("variant", 55, 1, False), ("f9", 56, 1, False),
    ("phase", 57, 1, False), ("target_flag", 58, 1, False),
    ("hold", 60, 4, False), ("target", 84, 1, False), ("fire", 88, 4, False),
]
POSITION_FIELDS = {"x", "y", "prev_x", "prev_y"}
# The fields whose DOS array is the same quantity, so a mismatch is a finding.
COMPARED = ["active", "heading", "altitude", "timer", "health", "sprite",
            "steer", "aux", "variant", "f9", "phase", "hold", "speed",
            "x", "y", "prev_x", "prev_y", "prev_alt", "target_flag"]
DOS_NAMES = {"target_flag": "target"}


def write_files(out: Path, program: Path, stop_cursor: int, demo_pass: int,
                poke: tuple[int, int, int] | None = None) -> None:
    (out / "boot.ini").write_text(
        "b GemdosOpcode = $4b && OsCallParam = 0 :trace :once :file program.ini\n")
    (out / "program.ini").write_text("b pc = TEXT :trace :once :file arm.ini\n")
    (out / "arm.ini").write_text(
        f"symbols {program.resolve()}\n"
        f"b pc = object_update_done && (demo_active).w = 1 "
        f"&& (attract_demo_pass).w = {demo_pass} :trace :file sample.ini\n"
        f"b (demo_cursor).l = {stop_cursor} && (attract_demo_pass).w = {demo_pass} "
        f":once :file done.ini\n"
        "b pc = exc_report :once :file failed.ini\n"
        + ("" if poke is None else
           f"b pc = demo_tick && (demo_cursor).l = {poke[0]} "
           f"&& (attract_demo_pass).w = {demo_pass} :once :file poke_on.ini\n"
           f"b pc = demo_tick && (demo_cursor).l = {poke[1]} "
           f"&& (attract_demo_pass).w = {demo_pass} :once :file poke_off.ini\n"))
    if poke is not None:
        # The same held Space on the cannon page the DOS side pokes
        # (work/trace_replay_flight.py --poke-from): key_state[0x39] = 0 and
        # the console page 0, then the released array and the page back.
        released = " ".join(["$ff"] * 0x39)   # short: the debugger line is 256 characters
        (out / "poke_on.ini").write_text(
            f"w instrument_page $00\nw key_state {released} $00\n")
        (out / "poke_off.ini").write_text(
            f"w instrument_page ${poke[2]:02x}\nw key_state {released} $ff\n")
    (out / "sample.ini").write_text(
        "m l demo_cursor 1\n"
        "m b object_threat_chaff 4\n"
        f"m b object_table {OBJ_COUNT * OBJ_SIZE}\n"
        "m b player_altitude 1\n"
        "m w object_target_latch 1\n"
        "m b instrument_page 1\n"
        "m w object_target_default 1\n")
    (out / "done.ini").write_text("quit\n")
    (out / "failed.ini").write_text("r\nd pc 8\nquit\n")


LINE = re.compile(r"^([0-9A-Fa-f]{6,8}): ((?:[0-9A-Fa-f]{2} ?){1,16}|(?:[0-9A-Fa-f]{8} ?){1,4})")


def hex_bytes(line: str, size_hint: str) -> bytes:
    """The data column of one `m` line: bytes, or longs written as 8 digits."""
    match = LINE.match(line)
    if not match:
        return b""
    return bytes.fromhex(match.group(2).replace(" ", ""))


def parse(transcript: str) -> list[dict]:
    """Split the transcript into samples, one per `m l demo_cursor` command."""
    samples: list[dict] = []
    current: dict | None = None
    mode = None
    table = bytearray()
    for raw in transcript.splitlines():
        line = raw.rstrip()
        if line.startswith("> m l demo_cursor"):
            if current is not None and len(table) == OBJ_COUNT * OBJ_SIZE:
                current["table"] = bytes(table)
                samples.append(current)
            current = {}
            table = bytearray()
            mode = "cursor"
            continue
        if line.startswith("> m b object_threat_chaff"):
            mode = "threat"
            continue
        if line.startswith("> m b object_table"):
            mode = "table"
            continue
        if line.startswith("> m b player_altitude"):
            mode = "alt"
            continue
        if line.startswith("> m w object_target_latch"):
            mode = "latch"
            continue
        if line.startswith("> m b instrument_page"):
            mode = "page"
            continue
        if line.startswith("> m w object_target_default"):
            mode = "cand"
            continue
        if line.startswith(">") or current is None or mode is None:
            if line.startswith(">"):
                mode = None
            continue
        data = hex_bytes(line, mode)
        if not data:
            continue
        if mode == "cursor":
            current["cursor"] = int.from_bytes(data[:4], "big")
        elif mode == "threat":
            current["threat_chaff"], current["threat_bull"] = data[0], data[1]
            current["chaff_active"], current["flare_active"] = data[2], data[3]
        elif mode == "alt":
            current["alt"] = data[0]
        elif mode == "latch":
            current["latch"] = int.from_bytes(data[:2], "big")
        elif mode == "page":
            current["page"] = data[0]
        elif mode == "cand":
            current["candidate"] = int.from_bytes(data[:2], "big")
        elif mode == "table":
            table.extend(data)
    if current is not None and len(table) == OBJ_COUNT * OBJ_SIZE:
        current["table"] = bytes(table)
        samples.append(current)
    return samples


def decode(sample: dict) -> dict:
    """Struct-of-arrays, indexed by DOS slot number 1..130 (index 0 unused)."""
    table = sample["table"]
    arrays = {name: [0] * (OBJ_COUNT + 1) for name, *_ in FIELDS}
    for slot in range(1, OBJ_COUNT + 1):
        base = (slot - 1) * OBJ_SIZE
        for name, offset, width, signed in FIELDS:
            value = int.from_bytes(table[base + offset:base + offset + width],
                                   "big", signed=signed)
            arrays[name][slot] = value
    arrays["cursor"] = sample["cursor"]
    for key in ("threat_chaff", "threat_bull", "chaff_active", "flare_active", "alt", "latch", "page", "candidate"):
        arrays[key] = sample.get(key)
    return arrays


def symbol_table(program: Path) -> dict[int, str]:
    """Falcon routine addresses by name, to compare states by what they are."""
    # Hatari prints symbols itself; keep the comparison on the DOS pointers.
    return {}


DOS_STATE_NAME = {
    0x23CF0: "mobile", 0x23F60: "default", 0x24860: "default",
    0x234E0: "shell_rock", 0x236D0: "shell_stinger", 0x237B0: "wreckage",
    0x23800: "fixed", 0x241C0: "rocket", 0x24680: "hellfire",
    0x244A0: "chaff", 0x24480: "bull", 0x23B50: "static", 0x23A8C: "idle",
}


def compare(dos_rows: list[dict], falcon_rows: list[dict], first_only: int,
            tolerance: int, slots: range) -> dict:
    by_cursor = {row["cursor"]: row for row in dos_rows}
    report = {"passes_compared": 0, "fields": {}, "scalars": {}, "first": []}
    for sample in falcon_rows:
        dos = by_cursor.get(sample["cursor"])
        if dos is None:
            continue
        report["passes_compared"] += 1
        for name in COMPARED:
            dos_name = DOS_NAMES.get(name, name)
            for slot in slots:
                theirs = dos[dos_name][slot]
                ours = sample[name][slot]
                if name in POSITION_FIELDS:
                    mine = ours                      # both are the original's 10.22
                elif name == "speed":
                    mine = ours
                else:
                    mine = ours
                    theirs &= 0xFF if name not in ("hold", "speed") else 0xFFFFFFFF
                    if name == "hold":
                        mine &= 0xFFFFFFFF
                if name in POSITION_FIELDS:
                    diff = (mine - theirs + (1 << 31)) % (1 << 32) - (1 << 31)
                    ok = abs(diff) <= tolerance
                else:
                    ok = mine == theirs
                if dos["active"][slot] == 0 and sample["active"][slot] == 0 \
                        and name not in ("active",):
                    continue
                stat = report["fields"].setdefault(name, {"checks": 0, "bad": 0, "slots": {}})
                stat["checks"] += 1
                if not ok:
                    stat["bad"] += 1
                    stat["slots"][slot] = stat["slots"].get(slot, 0) + 1
                    if len(report["first"]) < first_only:
                        report["first"].append(
                            {"cursor": sample["cursor"], "slot": slot, "field": name,
                             "dos": theirs, "falcon": mine})
        for name, key in (("threat_chaff", "chaf_threat"), ("threat_bull", "bull_threat"),
                          ("chaff_active", "flares"), ("latch", "latch"), ("page", "page"),):
            stat = report["scalars"].setdefault(name, {"checks": 0, "bad": 0})
            stat["checks"] += 1
            if sample.get(name) != dos.get(key):
                stat["bad"] += 1
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=int, default=100)
    ap.add_argument("--pass", dest="demo_pass", type=int, default=1)
    ap.add_argument("--program-dir", type=Path, default=ROOT / "release")
    ap.add_argument("--program", default="comanche_d.tos")
    ap.add_argument("--dos", type=Path,
                    default=ROOT / "work" / "replay_dos" / "objects-demo1.json")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "build" / "objects" / "falcon-objects.json")
    ap.add_argument("--run-vbls", type=int, default=20000)
    ap.add_argument("--timeout", type=int, default=1500)
    ap.add_argument("--transcript", type=Path,
                    help="parse an existing transcript instead of running Hatari")
    ap.add_argument("--slots", default="1-130",
                    help="slot range to compare, e.g. 23-31 for the placed objects")
    ap.add_argument("--poke-from", type=int, default=None,
                    help="hold Space on the cannon page from this cursor")
    ap.add_argument("--poke-to", type=int, default=None)
    ap.add_argument("--poke-page", type=int, default=2)
    ap.add_argument("--tolerance", type=int, default=0,
                    help="position difference tolerated, in 10.22 LSB")
    ap.add_argument("--first", type=int, default=25,
                    help="how many first mismatches to list")
    args = ap.parse_args()

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    program_dir = args.program_dir.resolve()
    program = program_dir / args.program
    # demo_cursor = 13 + 8*K, and the last pass K = records-1 is sampled before
    # the next record is consumed; stop once it has been passed.
    stop_cursor = 13 + 8 * args.records
    if args.transcript:
        transcript = args.transcript.read_text(errors="replace")
    else:
        hatari = os.environ.get("HATARI") or shutil.which("hatari")
        if not hatari:
            ap.error("hatari not found; set HATARI")
        tos = Path(os.environ.get("TOS", str(DEFAULT_TOS))).resolve()
        poke = None if args.poke_from is None else (args.poke_from, args.poke_to, args.poke_page)
        write_files(out.parent, program, stop_cursor, args.demo_pass, poke)
        cmd = [hatari, "--machine", "falcon", "--cpulevel", "3", "--memsize", "14",
               "--tos", str(tos), "--patch-tos", "true", "--mmu", "true",
               "--fpu", "none", "--dsp", "off", "--frameskips", "0",
               "--monitor", "rgb", "--fast-boot", "true", "--sound", "off",
               "--fast-forward", "true", "--cpu-exact", "true",
               "--compatible", "true", "--confirm-quit", "off",
               "--disable-video", "on", "--run-vbls", str(args.run_vbls),
               "--harddrive", str(program_dir), "--auto", "C:\\" + args.program,
               "--parse", str(out.parent / "boot.ini"),
               "--log-file", str(out.parent / "hatari.log"),
               "--alert-level", "fatal"]
        try:
            run = subprocess.run(cmd, cwd=out.parent, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, timeout=args.timeout, check=False)
        except subprocess.TimeoutExpired as error:
            print(f"Hatari timed out after {args.timeout}s", file=sys.stderr)
            return 1
        transcript = run.stdout or ""
        (out.parent / "transcript.txt").write_text(transcript)
    samples = parse(transcript)
    falcon = [decode(s) for s in samples]
    # one row per cursor: the first occurrence
    seen, unique = set(), []
    for row in falcon:
        if row["cursor"] in seen:
            continue
        seen.add(row["cursor"])
        unique.append(row)
    print(f"{len(unique)} Falcon passes sampled "
          f"(cursor {unique[0]['cursor'] if unique else '-'}.."
          f"{unique[-1]['cursor'] if unique else '-'})")
    out.write_text(json.dumps({"rows": unique}))
    dos = json.loads(args.dos.read_text())["rows"]
    lo, hi = (int(v) for v in args.slots.split("-"))
    report = compare(dos, unique, args.first, args.tolerance, range(lo, hi + 1))
    print(f"passes compared against DOS: {report['passes_compared']}")
    for name, stat in sorted(report["fields"].items()):
        flag = "ok " if stat["bad"] == 0 else "BAD"
        slots = ",".join(f"{s}:{n}" for s, n in sorted(stat["slots"].items())[:10])
        print(f"  {flag} {name:12s} {stat['checks'] - stat['bad']:6d}/{stat['checks']:<6d} {slots}")
    for name, stat in report["scalars"].items():
        flag = "ok " if stat["bad"] == 0 else "BAD"
        print(f"  {flag} {name:12s} {stat['checks'] - stat['bad']:6d}/{stat['checks']:<6d}")
    for item in report["first"]:
        print("  first:", item)
    return 0 if all(s["bad"] == 0 for s in report["fields"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
