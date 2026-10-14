#!/usr/bin/env python3
"""Compare DOS, browser and Falcon replay-boundary traces.

The comparison key is the DOS DEMO*.SCR file cursor.  A row is accepted only
when the implementation publishes the same raw DOS 10.22 state at the same
cursor.  The tool records the first unequal field for each implementation so
an aggregate CPU-to-CPU match cannot hide a shared DOS mistake.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

SUPPORTED_RECORDS = 284


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'F030Method'))
from validation.checkpoints import compare as compare_checkpoints
DEFAULT_DOS = ROOT / "work/replay_dos/flight-current.json"
DEFAULT_BROWSER = ROOT / "build/acceptance/three-way/browser-demo1.json"
DEFAULT_FALCON_30 = ROOT / "build/acceptance/three-way/falcon-68030/falcon-68030.json"
DEFAULT_FALCON_60 = ROOT / "build/acceptance/three-way/falcon-68060/falcon-68060.json"

# These are the values published by flight_publish and are deliberately raw;
# no browser coordinate conversion or tolerance is permitted here.
FIELDS = (
    "x_0x19CD4",
    "y_0x19CD8",
    "angle_0x19D04",
    "alt_0x19DFC",
    "turn_0x19D08",
    "fwd_0x19CC8",
    "lat_0x19CD0",
    "roll_0x19CF0",
    "pitch_0x19CF4",
)
VIEW_FIELDS = (
    "variant_0x19D86",
    "view_angle_0x19D00",
)


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def dos_rows(data: Any, wanted: int) -> tuple[dict[int, dict[str, Any]], list[str]]:
    problems: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return {}, ["DOS trace is missing a rows array"]
    rows: dict[int, dict[str, Any]] = {}
    for row in data["rows"]:
        if not isinstance(row, dict):
            continue
        cursor = row.get("cursor_0x19ECC")
        if not isinstance(cursor, int) or cursor < 21 or cursor in rows:
            continue
        if row.get("replay_0x19ED0") != 1:
            continue
        rows[cursor] = row
    expected = [21 + (8 * index) for index in range(wanted)]
    missing = [cursor for cursor in expected if cursor not in rows]
    if missing:
        problems.append(f"DOS trace missing {len(missing)} expected cursors; first {missing[0]}")
    return {cursor: rows[cursor] for cursor in expected if cursor in rows}, problems


def browser_rows(data: Any, wanted: int) -> tuple[dict[int, dict[str, Any]], list[str]]:
    problems: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return {}, ["browser trace is missing a rows array"]
    rows: dict[int, dict[str, Any]] = {}
    for row in data["rows"]:
        if not isinstance(row, dict):
            continue
        post = row.get("post")
        flight = post.get("flight") if isinstance(post, dict) else None
        cursor = post.get("demoCursor") if isinstance(post, dict) else None
        if not isinstance(cursor, int) or cursor < 21 or not isinstance(flight, dict):
            continue
        if cursor not in rows:
            rows[cursor] = {"row": row, "flight": flight, "cursor": cursor}
    expected = [21 + (8 * index) for index in range(wanted)]
    missing = [cursor for cursor in expected if cursor not in rows]
    if missing:
        problems.append(f"browser trace missing {len(missing)} expected cursors; first {missing[0]}")
    return {cursor: rows[cursor] for cursor in expected if cursor in rows}, problems


def falcon_rows(data: Any, wanted: int, label: str) -> tuple[dict[int, dict[str, Any]], list[str]]:
    problems: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return {}, [f"{label} trace is missing a rows array"]
    rows: dict[int, dict[str, Any]] = {}
    for row in data["rows"]:
        if not isinstance(row, dict):
            continue
        cursor = row.get("cursor_0x19ECC")
        if not isinstance(cursor, int) or cursor < 21 or cursor in rows:
            continue
        rows[cursor] = row
    expected = [21 + (8 * index) for index in range(wanted)]
    missing = [cursor for cursor in expected if cursor not in rows]
    if missing:
        problems.append(f"{label} trace missing {len(missing)} expected cursors; first {missing[0]}")
    return {cursor: rows[cursor] for cursor in expected if cursor in rows}, problems


def normalized(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    if kind == "browser":
        trace_row = row.get("row") or {}
        post = trace_row.get("post") or {}
        rendered = trace_row.get("pre") or {}
        view = post.get("view") or {}
        normalized_row = {field: row["flight"].get(field) for field in FIELDS}
        rendered_view = rendered.get("view") or {}
        normalized_row.update({
            "variant_0x19D86": rendered_view.get("variant_0x19D86"),
            "view_angle_0x19D00": rendered_view.get("angle_0x19D00"),
        })
        return normalized_row
    normalized_row = {field: row.get(field) for field in FIELDS}
    if kind == "falcon":
        normalized_row.update({
            "variant_0x19D86": row.get("variant"),
            "view_angle_0x19D00": row.get("view_angle_0x19D00"),
        })
    else:
        normalized_row.update({
            "variant_0x19D86": row.get("variant_0x19D86"),
            "view_angle_0x19D00": row.get("view_angle_0x19D00"),
        })
    return normalized_row


def first_difference(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[str, Any, Any] | None:
    result = compare_checkpoints([{'key': 0, 'state': expected}],
                                [{'key': 0, 'state': actual}], FIELDS + VIEW_FIELDS)
    first = result['first']
    return (first['field'], first['expected'], first['actual']) if first else None


def compare(name: str, kind: str, expected: dict[int, dict[str, Any]],
            actual: dict[int, dict[str, Any]], wanted: int) -> dict[str, Any]:
    compared = 0
    divergence = None
    for tick, cursor in enumerate(21 + (8 * index) for index in range(wanted)):
        if cursor not in expected or cursor not in actual:
            break
        compared += 1
        try:
            diff = first_difference(normalized("dos", expected[cursor]), normalized(kind, actual[cursor]))
        except ValueError as error:
            return {"status": "Unproven", "records_expected": wanted,
                    "records_compared": compared - 1, "first_divergence": None,
                    "problems": [f"cursor {cursor}: {error}"]}
        if diff:
            field, want, got = diff
            divergence = {
                "implementation": name,
                "tick": tick,
                "cursor": cursor,
                "function_ids": actual[cursor].get("row", {}).get("function_ids") if kind == "browser" else ["flight_publish"],
                "field": field,
                "dos": want,
                "actual": got,
            }
            break
    return {
        "status": "PASS" if compared == wanted and divergence is None else "DIVERGENCE" if divergence else "Unproven",
        "records_expected": wanted,
        "records_compared": compared,
        "first_divergence": divergence,
    }


def unproven_comparison(wanted: int, problem: str) -> dict[str, Any]:
    """Represent missing or stale evidence without treating it as a mismatch."""
    return {
        "status": "Unproven",
        "records_expected": wanted,
        "records_compared": 0,
        "first_divergence": None,
        "problems": [problem],
    }


def source_identity() -> dict[str, Any]:
    def command(args: list[str]) -> str | None:
        try:
            return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    return {"git_head": command(["git", "rev-parse", "HEAD"]),
            "git_dirty": bool(command(["git", "status", "--porcelain", "--untracked-files=all"]))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dos", type=Path, default=DEFAULT_DOS)
    parser.add_argument("--browser", type=Path, default=DEFAULT_BROWSER)
    parser.add_argument("--falcon-68030", type=Path, default=DEFAULT_FALCON_30)
    parser.add_argument("--falcon-68060", type=Path, default=DEFAULT_FALCON_60)
    # 284 records is the supported DEMO1 boundary: record index 284 (the 285th)
    # is the no-damage bounce, DOS 00019461, that arms the screen shake. Its
    # display consumers are not recovered, so this cross-machine parity trace
    # stops the armed presentation there; the browser-only target witness uses
    # the documented crop adaptation (analysis/functions/browser-attract.md#shake-timer).
    parser.add_argument("--records", type=int, default=SUPPORTED_RECORDS)
    parser.add_argument("--out", type=Path, default=ROOT / "build/acceptance/three-way/boundary-comparison.json")
    args = parser.parse_args()
    if args.records < 1:
        parser.error('--records must be positive')
    paths = {"dos": args.dos.resolve(), "browser": args.browser.resolve(),
             "68030": args.falcon_68030.resolve(), "68060": args.falcon_68060.resolve()}
    wanted = args.records
    data = {name: load(path) for name, path in paths.items()}
    dos, dos_problems = dos_rows(data["dos"], wanted)
    browser, browser_problems = browser_rows(data["browser"], wanted)
    falcon30, falcon30_problems = falcon_rows(data["68030"], wanted, "68030")
    falcon60, falcon60_problems = falcon_rows(data["68060"], wanted, "68060")
    comparisons = {
        "javascript": compare("javascript", "browser", dos, browser, wanted),
        "68030": compare("68030", "falcon", dos, falcon30, wanted),
        "68060": compare("68060", "falcon", dos, falcon60, wanted),
    }
    problems = dos_problems + browser_problems + falcon30_problems + falcon60_problems
    current_dos_image = ROOT / "assets/extracted/comanche_hdd/UNPACKED.EXE"
    browser_dos_hash = data["browser"].get("dos_image_sha256") if isinstance(data["browser"], dict) else None
    current_dos_hash = sha256(current_dos_image)
    if browser_dos_hash != current_dos_hash:
        problem = "browser trace is not tied to the current DOS oracle image"
        problems.append(problem)
        comparisons["javascript"] = unproven_comparison(wanted, problem)

    current_programs = {
        "68030": ROOT / "release/comanche_d.tos",
        "68060": ROOT / "release/68060/comanche_d.tos",
    }
    build_identity: dict[str, Any] = {"dos_image_sha256": current_dos_hash}
    for name, current_program in current_programs.items():
        artifact = data[name] if isinstance(data[name], dict) else {}
        recorded_program = artifact.get("program")
        recorded_hash = artifact.get("program_sha256")
        artifact_path = Path(recorded_program).resolve() if isinstance(recorded_program, str) else None
        artifact_hash = sha256(artifact_path) if artifact_path else None
        current_hash = sha256(current_program)
        build_identity[name] = {
            "artifact_program": str(artifact_path) if artifact_path else None,
            "artifact_program_sha256": recorded_hash,
            "artifact_bytes_sha256": artifact_hash,
            "current_program": str(current_program),
            "current_program_sha256": current_hash,
        }
        identity_problem = None
        if not artifact_path or artifact_hash is None:
            identity_problem = f"{name} trace does not identify an existing program binary"
        elif recorded_hash != artifact_hash:
            identity_problem = f"{name} trace program hash does not match the captured binary"
        elif current_hash is None:
            identity_problem = f"current {name} debug binary is missing"
        elif recorded_hash != current_hash:
            identity_problem = f"{name} trace is stale: recorded program hash {recorded_hash}, current debug binary hash {current_hash}"
        if identity_problem:
            problems.append(identity_problem)
            comparisons[name] = unproven_comparison(wanted, identity_problem)
    stream_paths = {
        "dos": ROOT / "assets/extracted/comanche_hdd/DEMO1.SCR",
        "browser": ROOT / "assets/extracted/comanche_hdd/DEMO1.SCR",
    }
    for name in ("68030", "68060"):
        program = data[name].get("program") if isinstance(data[name], dict) else None
        candidate = Path(program).resolve().parent / "DEMO1.SCR" if isinstance(program, str) else None
        stream_paths[name] = candidate if candidate and candidate.is_file() else ROOT / ("release/DEMO1.SCR" if name == "68030" else "release/68060/DEMO1.SCR")
    stream_hashes = {name: sha256(path) for name, path in stream_paths.items()}
    if any(value is None for value in stream_hashes.values()):
        problems.append("DEMO1.SCR input stream is missing for one implementation")
    elif len(set(stream_hashes.values())) != 1:
        problems.append("DEMO1.SCR input bytes differ between implementations")
    status = "PASS" if not problems and all(row["status"] == "PASS" for row in comparisons.values()) else "DIVERGENCE" if any(row["status"] == "DIVERGENCE" for row in comparisons.values()) else "Unproven"
    result = {
        "schema": "f030-boundary-comparison-v1",
        "status": status,
        "pass": 1,
        "records_expected": wanted,
        "cursor_contract": "DEMO1.SCR byte cursor: 13 + record_index * 8; first record 21",
        "fields": list(FIELDS + VIEW_FIELDS),
        "function_boundaries": {
            "dos": "FUN_00018F94 / flat 00019555 flight_publish",
            "javascript": ["FUN_00018C29", "FUN_00019A2D", "FUN_00018F94"],
            "68030": "flight_publish",
            "68060": "flight_publish",
        },
        "identity": source_identity(),
        "comparison_tool_sha256": sha256(Path(__file__)),
        "shared_comparison_sha256": sha256(ROOT.parent / 'F030Method/validation/checkpoints.py'),
        "build_identity": build_identity,
        "inputs": {name: {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), "sha256": sha256(path)} for name, path in paths.items()},
        "replay_input": {name: {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), "sha256": stream_hashes[name]} for name, path in stream_paths.items()},
        "problems": problems,
        "comparisons": comparisons,
    }
    output = args.out if args.out.is_absolute() else ROOT / args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{status}: DOS/JavaScript/68030/68060 boundary comparison; output {output}")
    for name, row in comparisons.items():
        divergence = row.get("first_divergence")
        suffix = f" first={divergence}" if divergence else ""
        print(f"  {name}: {row['status']} {row['records_compared']}/{wanted}{suffix}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
