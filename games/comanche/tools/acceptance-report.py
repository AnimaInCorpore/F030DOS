#!/usr/bin/env python3
"""Generate the repeatable acceptance report for the supported attract slice.

The report is deliberately conservative.  It fingerprints the DOS oracle,
source snapshot, toolchain and target binaries; reruns the deterministic
browser gate; checks the recorded CPU/countdown evidence; and leaves any
DOS-fidelity gate as ``Unproven`` until its required evidence exists.

The command writes docs/ACCEPTANCE-REPORT.md and returns 1 while any
certification gate is Unproven.  That is expected for the current milestone.
Use --skip-browser-proof only for an offline report inspection; it cannot
produce a certifying result.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DEFAULT = ROOT / "docs/ACCEPTANCE-REPORT.md"
# 284 records is the supported DEMO1 boundary: record index 284 (the 285th)
# is the no-damage bounce, DOS 00019461, that arms the screen shake. Its
# display consumers are not recovered, so the cross-machine parity trace stops
# the armed presentation there; the browser-only target witness continues via
# its documented crop adaptation (analysis/functions/browser-attract.md#shake-timer).
SUPPORTED_RECORDS = 284
DOS_EXE = ROOT / "re/unpacked/COMANCHE.UNPACKED.EXE"
DOS_FLAT = ROOT / "re/unpacked/comanche-flat32.bin"

DOS_SHA256 = "4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697"
DOS_FLAT_SHA256 = "a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c"
FRAME_BYTES = 320 * 240 * 2

SOURCE_PATTERNS = (
    "AGENTS.md",
    "README.md",
    "jsComanche/**/*.js",
    "jsComanche/**/*.html",
    "jsComanche/**/*.css",
    "src/**/*.s",
    "src/**/*.inc",
    "analysis/functions/*.md",
    "docs/DOS-ORACLE.md",
    "docs/PORTING-PLAN.md",
    "docs/SUBSTITUTIONS.md",
    "docs/X86-M68K-MAP.md",
    "tools/README.md",
    "tools/acceptance-report.py",
    "tools/build-run.sh",
    "tools/run.sh",
    "tools/prove-browser-attract.js",
    "tools/check-cpu-compatibility.py",
    "tools/check-attract-timing.py",
    "tools/certify-replay-flight.py",
    "tools/compare-boundary-traces.py",
    "tools/compare-complete-frame.py",
    "tools/trace-browser-replay.js",
    "tools/trace-browser-sequence.js",
    "tools/audit-function-matrix.py",
    "tools/trace-falcon-replay.py",
    "tools/certify-marcher.py",
    "tools/compare-marcher.py",
    "tools/compare-port-tables.py",
    "tools/compare-terrain.py",
    "tools/substitutions.py",
)

BUILD_FILES = (
    ("68030 production", "release/comanche.tos"),
    ("68030 debug/timing", "release/comanche_d.tos"),
    ("68060 production", "release/68060/comanche.tos"),
    ("68060 debug/timing", "release/68060/comanche_d.tos"),
    ("68030 multiply harness", "build/check-cpu-68030/check.tos"),
    ("68060 multiply harness", "build/check-cpu-68060/check.tos"),
)

TIMING_CASES = (
    ("68030 odd opening", "build/acceptance/attract-68030-odd", "build/acceptance/attract-68030-odd/timing-result.json", {"2": 480, "3": 600}),
    ("68060 odd opening", "build/acceptance/attract-68060-odd", "build/acceptance/attract-68060-odd/timing-result.json", {"2": 480, "3": 600}),
    ("68030 even opening", "build/acceptance/attract-68030-even", "build/acceptance/attract-68030-even/timing-result.json", {"1": 300}),
    ("68060 even opening", "build/acceptance/attract-68060-even", "build/acceptance/attract-68060-even/timing-result.json", {"1": 300}),
)

ROUTE_REQUIREMENTS = (
    (
        "work/qemu_out/attract-trace-report.txt",
        "range-count report",
        ("attract-cycle", "frame-driver", "terrain-renderer", "replay-load",
         "flight", "object-pass", "object-sort-draw", "sprite-console",
         "palette", "mission-select", "post-object-7AA0"),
    ),
    (
        "work/qemu_out/object-state-walk.txt",
        "active-object snapshot",
        ("active object slots:", "fn=0x23cf0", "fn=0x23f60", "fn=0x23840",
         "draw=0x24fed", "draw=0x2514d"),
    ),
)

FUNCTION_ROWS = (
    ("FUN_00005690", "attract state, authored transition", "AttractRuntime.enterNextPass / advanceScreen", "attract_tick / attract_next_pass", "browser gate; timing-result.json"),
    ("FUN_00018C29 / FUN_00019A2D", "DEMO header and per-record replay boundary", "AttractRuntime.enterDemo / advanceDemoInput", "demo_start / demo_tick", "flight-demo1.json; flight-dos.json"),
    ("FUN_00018F94", "flight integration from replay axes", "AttractRuntime.flightTick", "flight_tick", "flight-demo1.json; flight-dos.json"),
    ("FUN_0000D3C0", "frame ordering and publication boundary", "AttractRuntime.advanceAuthoritativeTick", "frame_driver", "timing-frame.bin; browser trace"),
    ("FUN_0000D950", "HIGH.DTL terrain ring walk", "AttractRuntime.drawTerrainStage / drawTerrain", "render_terrain_ring", "compare-marcher.py; flight traces"),
    ("FUN_000234A4", "descending object update/state dispatch", "AttractRuntime.updateObjectPass / updateObjectState", "object_update_pass", "browser object-pass proof"),
    ("FUN_00024B17", "object transform, ordering and draw", "AttractRuntime.objectTransform / objectDraw", "object_draw_pass", "browser object-pass proof"),
    ("FUN_00025880", "planar sprite and cockpit composition", "drawOpaqueSprite / AttractRuntime.drawConsole", "sprite_draw / sprite_blit", "browser composition proof"),
    ("FUN_0002B820", "palette remap and RGB565 conversion boundary", "nearestPaletteMap / buildPaletteLookup", "resource_palette_remap", "browser palette proof; compare-terrain.py"),
)

REQUIRED_HEADER_FIELDS = ("DOS", "Record", "Route", "Port", "Preserved", "Kind", "Status")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def link(path: str) -> str:
    return f"[`{path}`](../{path})"


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand_source_files() -> list[Path]:
    found: set[Path] = set()
    for pattern in SOURCE_PATTERNS:
        if any(mark in pattern for mark in "*?["):
            candidates = ROOT.glob(pattern)
        else:
            candidates = (ROOT / pattern,)
        for candidate in candidates:
            if candidate.is_file():
                found.add(candidate)
    return sorted(found, key=rel)


def source_manifest() -> tuple[str, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    blob = bytearray()
    for path in expand_source_files():
        digest = sha256_file(path)
        assert digest is not None
        size = path.stat().st_size
        name = rel(path)
        rows.append({"path": name, "size": size, "sha256": digest})
        blob.extend(f"{name}\t{size}\t{digest}\n".encode())
    return hashlib.sha256(blob).hexdigest(), rows


def run_command(command: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT,
                                   timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return completed.returncode, completed.stdout.strip()


def git_identity() -> dict[str, Any]:
    code, head = run_command(["git", "rev-parse", "HEAD"])
    _, subject = run_command(["git", "show", "-s", "--format=%s", "HEAD"])
    _, status = run_command(["git", "status", "--porcelain", "--untracked-files=all"])
    changed = [line for line in status.splitlines() if line.strip()]
    return {
        "head": head if code == 0 else "Unproven",
        "subject": subject or "Unproven",
        "dirty": bool(changed),
        "changed_count": len(changed),
    }


def parse_source_headers() -> list[dict[str, Any]]:
    headers: list[dict[str, Any]] = []
    label_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)$")
    field_re = re.compile(r"^(DOS|Record|Route|Port|Preserved|Difference|Kind|Status):\s*(.*)$")

    def valid_record_reference(value: str) -> bool:
        match = re.match(r"([^#]+)(?:#([A-Za-z0-9_-]+))?$", value.strip())
        if not match:
            return False
        record_path = ROOT / match.group(1)
        if not record_path.is_file():
            return False
        fragment = match.group(2)
        if not fragment:
            return True
        record_text = record_path.read_text(errors="replace")
        for heading in re.findall(r"^#{1,6}\s+(.+?)\s*$", record_text, re.M):
            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            if slug == fragment.lower():
                return True
        return False

    for path in sorted((ROOT / "src").rglob("*.s"), key=rel):
        lines = path.read_text(errors="replace").splitlines()
        file_fields: dict[str, str] = {}
        for line in lines:
            text = line.strip()
            if not text:
                continue
            if not text.startswith(";"):
                break
            field = field_re.match(text[1:].strip())
            if field:
                file_fields[field.group(1)] = field.group(2).strip()
        for index, line in enumerate(lines):
            match = label_re.match(line)
            if not match:
                continue
            comments: list[str] = []
            cursor = index - 1
            while cursor >= 0:
                text = lines[cursor].strip()
                if not text:
                    cursor -= 1
                    continue
                if not text.startswith(";"):
                    break
                comments.append(text[1:].strip())
                cursor -= 1
            fields: dict[str, str] = dict(file_fields)
            for comment in reversed(comments):
                field = field_re.match(comment)
                if field:
                    fields[field.group(1)] = field.group(2).strip()
            if "DOS" not in fields:
                continue
            dos = fields["DOS"]
            target_only = dos.lower().startswith("n/a")
            canonical = target_only or bool(re.search(r"\b[0-9a-f]{5,8}\b", dos, re.I))
            missing = [field for field in REQUIRED_HEADER_FIELDS if not fields.get(field)]
            if fields.get("Record") and not valid_record_reference(fields["Record"]):
                missing.append("Record")
            if not canonical:
                missing.append("canonical DOS ID")
            headers.append({
                "path": rel(path),
                "line": index + 1,
                "symbol": match.group(1),
                "fields": fields,
                "missing": missing,
            })
    return headers


def browser_record_inventory() -> dict[str, Any]:
    browser = ROOT / "analysis/functions/browser-attract.md"
    text = browser.read_text(errors="replace") if browser.is_file() else ""
    headings = sorted(set(re.findall(r"^## `([^`]+)`", text, re.M)))
    js_files = sorted((ROOT / "jsComanche").glob("*.js"))
    refs: set[str] = set()
    for path in js_files:
        refs.update(re.findall(r"record:\s*(analysis/functions/browser-attract\.md#[A-Za-z0-9_-]+)", path.read_text(errors="replace")))
    return {"headings": headings, "js_files": [rel(path) for path in js_files], "refs": sorted(refs)}


def browser_gate(skip: bool) -> dict[str, Any]:
    if skip:
        return {"status": "Unproven", "output": "Skipped by --skip-browser-proof"}
    code, output = run_command(["node", "tools/prove-browser-attract.js"], timeout=180)
    lines = output.splitlines()
    passed = code == 0 and any(line.startswith("PASS source-audit") for line in lines)
    return {"status": "PASS" if passed else "Unproven", "output": output or "No output"}


def substitutions_check() -> dict[str, Any]:
    code, output = run_command([sys.executable, "tools/substitutions.py", "--check"], timeout=120)
    return {"status": "PASS" if code == 0 else "Unproven", "output": output or "No output"}


def check_cpu_result(cpu: int) -> dict[str, Any]:
    result_path = ROOT / f"build/check-cpu-{cpu}/result.json"
    program_path = ROOT / f"build/check-cpu-{cpu}/check.tos"
    result: dict[str, Any] = {}
    problems: list[str] = []
    if result_path.is_file():
        try:
            result = json.loads(result_path.read_text())
            if not isinstance(result, dict):
                problems.append("result JSON is not an object")
                result = {}
        except json.JSONDecodeError as exc:
            problems.append(f"invalid JSON: {exc}")
    else:
        problems.append(f"missing {rel(result_path)}")
    actual_program = sha256_file(program_path)
    if actual_program != result.get("program_sha256"):
        problems.append("result is not tied to the current harness binary")
    if result.get("cpu") != cpu or result.get("pairs") != 1193 or result.get("products") != 4772:
        problems.append("expected 1,193 pairs / 4,772 products not present")
    if result.get("status") != "PASS":
        problems.append("harness result is not PASS")
    return {
        "status": "PASS" if not problems else "Unproven",
        "result_path": rel(result_path),
        "program_path": rel(program_path),
        "result": result,
        "program_sha256": actual_program,
        "problems": problems,
    }


def check_timing_case(label: str, directory: str, result_rel: str,
                      expected_ticks: dict[str, int]) -> dict[str, Any]:
    result_path = ROOT / result_rel
    run_dir = ROOT / directory
    problems: list[str] = []
    result: dict[str, Any] = {}
    if result_path.is_file():
        try:
            result = json.loads(result_path.read_text())
            if not isinstance(result, dict):
                problems.append("result JSON is not an object")
                result = {}
        except json.JSONDecodeError as exc:
            problems.append(f"invalid JSON: {exc}")
    else:
        problems.append(f"missing {result_rel}; run the timing check with --artifact-dir")
    expected_cpu = 68060 if "68060" in label else 68030
    expected_pass = 2 if "even" in label else 1
    cpu = result.get("cpu")
    program_path = ROOT / ("release/comanche_d.tos" if cpu == 68030 else "release/68060/comanche_d.tos")
    actual_program = sha256_file(program_path)
    frame_path = run_dir / "timing-frame.bin"
    actual_frame = sha256_file(frame_path)
    expected_frame = result.get("frame_sha256")
    ticks = {str(key): int(value) for key, value in result.get("screen_ticks", {}).items()} if isinstance(result.get("screen_ticks"), dict) else {}
    if result.get("status") != "PASS":
        problems.append("timing result is not PASS")
    if cpu != expected_cpu:
        problems.append(f"result CPU {cpu!r} != expected {expected_cpu}")
    if result.get("pass") != expected_pass:
        problems.append(f"result pass {result.get('pass')!r} != expected {expected_pass}")
    if ticks != expected_ticks:
        problems.append(f"screen ticks {ticks!r} != {expected_ticks!r}")
    if result.get("checkpoint") != "publish_screen":
        problems.append("first-flight publication checkpoint missing")
    if result.get("replay_byte_order") != "PASS":
        problems.append("replay byte-order check missing")
    if result.get("program_sha256") != actual_program:
        problems.append("timing result is not tied to the current debug binary")
    if actual_frame != expected_frame or not frame_path.is_file() or frame_path.stat().st_size != FRAME_BYTES:
        problems.append("frame artifact is missing, incomplete, or not tied to timing-result.json")
    return {
        "label": label,
        "directory": directory,
        "result_path": result_rel,
        "result": result,
        "frame_path": rel(frame_path),
        "frame_sha256": actual_frame,
        "program_path": rel(program_path),
        "program_sha256": actual_program,
        "problems": problems,
        "status": "PASS" if not problems else "Unproven",
    }


def replay_fixture_inventory() -> dict[str, Any]:
    paths = [
        "work/replay_dos/flight-demo1.json",
        "work/replay_dos/flight-dos.json",
        "work/replay_dos/view-demo1.json",
        "work/replay_dos/replay-passes.json",
    ]
    rows: list[dict[str, Any]] = []
    for name in paths:
        path = ROOT / name
        row: dict[str, Any] = {"path": name, "exists": path.is_file(), "sha256": sha256_file(path)}
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                if isinstance(data.get("rows"), list):
                    row["rows"] = len(data["rows"])
                if isinstance(data.get("replays"), list):
                    row["replays"] = len(data["replays"])
                if "breakpoint" in data:
                    row["breakpoint"] = data["breakpoint"]
            except json.JSONDecodeError:
                row["parse"] = "Unproven"
        rows.append(row)
    return {"rows": rows}


def dos_pcx_inventory() -> dict[str, Any]:
    """Inventory retained DOS PCX candidates without treating them as paired proof."""
    candidates: list[Path] = []
    palette_candidates: list[Path] = []
    groups: Counter[str] = Counter()
    for path in sorted((ROOT / "build").rglob("SNAP_*.PCX"), key=rel):
        raw = path.read_bytes()
        if len(raw) < 128 or raw[:4] != bytes((0x0A, 5, 1, 8)):
            continue
        xmin, ymin, xmax, ymax = struct.unpack_from("<HHHH", raw, 4)
        if (xmax - xmin + 1, ymax - ymin + 1) != (328, 240):
            continue
        candidates.append(path)
        groups[rel(path.parent)] += 1
        if len(raw) >= 769 and raw[-769] == 0x0C:
            palette_candidates.append(path)
    tilt = [path for path in candidates if rel(path).startswith("build/oracle-tilt/")]
    sample = tilt[0] if tilt else (candidates[0] if candidates else None)
    return {
        "candidates": candidates,
        "palette_candidates": palette_candidates,
        "groups": dict(sorted(groups.items())),
        "sample": rel(sample) if sample else None,
        "sample_sha256": sha256_file(sample) if sample else None,
    }


def route_inventory() -> dict[str, Any]:
    """Validate the route witnesses instead of treating their names as proof."""
    rows: list[dict[str, Any]] = []
    for path_text, kind, requirements in ROUTE_REQUIREMENTS:
        path = ROOT / path_text
        text = path.read_text(errors="replace") if path.is_file() else ""
        missing: list[str] = []
        if not path.is_file():
            missing.append("file is absent")
        elif not text.strip():
            missing.append("file is empty")
        if kind == "range-count report":
            for name in requirements:
                match = re.search(rf"^\s*{re.escape(name)}\s+(\d+)\s+entry=", text, re.M)
                if not match:
                    missing.append(f"{name}: no positive range count")
                elif int(match.group(1)) <= 0:
                    missing.append(f"{name}: count is zero")
        else:
            missing.extend(token for token in requirements if token not in text)
        rows.append({
            "path": path_text,
            "kind": kind,
            "exists": path.is_file(),
            "size": path.stat().st_size if path.is_file() else None,
            "sha256": sha256_file(path),
            "missing": missing,
            "status": "PASS" if not missing else "Unproven",
        })
    return {"rows": rows, "status": "PASS" if all(row["status"] == "PASS" for row in rows) else "Unproven"}


def three_way_inventory() -> dict[str, Any]:
    """Run and validate the cursor-keyed DOS/JS/Falcon boundary comparison."""
    artifact = ROOT / "build/acceptance/three-way/boundary-comparison.json"
    code, output = run_command(
        [sys.executable, "tools/compare-boundary-traces.py", "--out", str(artifact)],
        timeout=180,
    )
    result: dict[str, Any] = {}
    problems: list[str] = []
    if artifact.is_file():
        try:
            loaded = json.loads(artifact.read_text())
            if isinstance(loaded, dict):
                result = loaded
            else:
                problems.append("boundary artifact is not a JSON object")
        except json.JSONDecodeError as exc:
            problems.append(f"invalid boundary artifact: {exc}")
    else:
        problems.append("boundary artifact is absent")
    if code != 0 and result.get("status") == "PASS":
        problems.append("boundary comparison command failed after reporting PASS")
    if result.get("status") != "PASS":
        problems.append(f"comparison status is {result.get('status', 'Unproven')}")
    if result.get("records_expected") != SUPPORTED_RECORDS:
        problems.append(f"expected {SUPPORTED_RECORDS} supported DEMO1 boundary records are not present")
    inputs = result.get("inputs") if isinstance(result.get("inputs"), dict) else {}
    for name in ("dos", "browser", "68030", "68060"):
        row = inputs.get(name) if isinstance(inputs.get(name), dict) else {}
        path_text = row.get("path")
        path = ROOT / path_text if isinstance(path_text, str) and not Path(path_text).is_absolute() else Path(path_text) if isinstance(path_text, str) else None
        actual = sha256_file(path) if path else None
        if not path or actual is None:
            problems.append(f"{name} boundary input is missing")
        elif actual != row.get("sha256"):
            problems.append(f"{name} boundary input changed after comparison")
    status = "PASS" if not problems else "DIVERGENCE" if result.get("status") == "DIVERGENCE" else "Unproven"
    return {
        "status": status,
        "path": rel(artifact),
        "sha256": sha256_file(artifact),
        "result": result,
        "problems": problems,
        "output": output or "No output",
    }


def complete_frame_inventory() -> dict[str, Any]:
    """Validate the explicit page/pan-aware complete-frame artifact."""
    artifact = ROOT / "build/acceptance/frames/complete-frame-comparison.json"
    if not artifact.is_file():
        return {
            "status": "Unproven",
            "path": rel(artifact),
            "sha256": None,
            "result": {},
            "problems": ["no page/pan/tick-paired DOS PCX and target frame artifact"],
        }
    try:
        result = json.loads(artifact.read_text())
    except json.JSONDecodeError as exc:
        return {
            "status": "Unproven",
            "path": rel(artifact),
            "sha256": sha256_file(artifact),
            "result": {},
            "problems": [f"invalid complete-frame artifact: {exc}"],
        }
    if not isinstance(result, dict):
        return {
            "status": "Unproven",
            "path": rel(artifact),
            "sha256": sha256_file(artifact),
            "result": {},
            "problems": ["complete-frame artifact is not a JSON object"],
        }
    status = result.get("status")
    return {
        "status": status if status in ("PASS", "DIVERGENCE") else "Unproven",
        "path": rel(artifact),
        "sha256": sha256_file(artifact),
        "result": result,
        "problems": result.get("problems", []) if isinstance(result.get("problems"), list) else ["complete-frame problems field is invalid"],
    }


def sequence_inventory() -> dict[str, Any]:
    """Read the all-pass sequence witness, if the harness has produced one."""
    artifact = ROOT / "build/acceptance/sequence/browser-sequence.json"
    if not artifact.is_file():
        return {"status": "Unproven", "path": rel(artifact), "sha256": None,
                "result": {}, "problems": ["no complete sequence artifact"]}
    try:
        result = json.loads(artifact.read_text())
    except json.JSONDecodeError as exc:
        return {"status": "Unproven", "path": rel(artifact), "sha256": sha256_file(artifact),
                "result": {}, "problems": [f"invalid sequence artifact: {exc}"]}
    if not isinstance(result, dict):
        return {"status": "Unproven", "path": rel(artifact), "sha256": sha256_file(artifact),
                "result": {}, "problems": ["sequence artifact is not a JSON object"]}
    status = result.get("status")
    problems = result.get("errors", []) if isinstance(result.get("errors"), list) else ["sequence errors field is invalid"]
    if result.get("external_camera_support") != "PASS":
        problems = list(problems) + ["external-camera selectors are not exercised by a supported implementation"]
    boundary = result.get("supported_boundary")
    if isinstance(boundary, dict):
        problems = list(problems) + [f"browser witness stops at the supported boundary: pass {boundary.get('pass')} record {boundary.get('record')} ({boundary.get('reason')})"]
    return {"status": status if status in ("PASS", "DIVERGENCE") else "Unproven",
            "path": rel(artifact), "sha256": sha256_file(artifact),
            "result": result, "problems": problems}


def function_audit_inventory() -> dict[str, Any]:
    """Require a generated reached-function matrix, not only source headers."""
    artifact = ROOT / "build/acceptance/function-audit.json"
    if not artifact.is_file():
        return {
            "status": "Unproven",
            "path": rel(artifact),
            "sha256": None,
            "result": {},
            "problems": ["no generated reached-function matrix; source-header scan is not sufficient"],
        }
    try:
        result = json.loads(artifact.read_text())
    except json.JSONDecodeError as exc:
        return {"status": "Unproven", "path": rel(artifact), "sha256": sha256_file(artifact),
                "result": {}, "problems": [f"invalid function-audit artifact: {exc}"]}
    if not isinstance(result, dict):
        return {"status": "Unproven", "path": rel(artifact), "sha256": sha256_file(artifact),
                "result": {}, "problems": ["function-audit artifact is not a JSON object"]}
    status = result.get("status")
    problems = result.get("problems", []) if isinstance(result.get("problems"), list) else ["function-audit problems field is invalid"]
    if result.get("source_header_count") != len(parse_source_headers()):
        problems = list(problems) + ["function-audit matrix is not tied to the current source header count"]
    return {"status": status if status in ("PASS", "DIVERGENCE") else "Unproven",
            "path": rel(artifact), "sha256": sha256_file(artifact),
            "result": result, "problems": problems}


def toolchain_inventory() -> dict[str, Any]:
    path = ROOT / "build/cpu-toolchain.json"
    if not path.is_file():
        return {"status": "Unproven", "path": rel(path), "sha256": None, "data": {}}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"status": "Unproven", "path": rel(path), "sha256": sha256_file(path), "data": {}}
    return {"status": "PASS", "path": rel(path), "sha256": sha256_file(path), "data": data}


def format_hash(value: str | None) -> str:
    return value if value else "Unproven"


def status_cell(value: str) -> str:
    return value


def build_report(skip_browser: bool) -> tuple[str, dict[str, Any]]:
    source_hash, source_rows = source_manifest()
    git = git_identity()
    headers = parse_source_headers()
    missing_headers = [row for row in headers if row["missing"]]
    missing_records = [row for row in headers if "Record" in row["missing"]]
    missing_ids = [row for row in headers if "canonical DOS ID" in row["missing"]]
    browser_records = browser_record_inventory()
    browser = browser_gate(skip_browser)
    substitutions = substitutions_check()
    cpu = {cpu: check_cpu_result(cpu) for cpu in (68030, 68060)}
    timing = [check_timing_case(*case) for case in TIMING_CASES]
    timing_by_label = {row["label"]: row for row in timing}
    odd_equal = (
        timing_by_label["68030 odd opening"]["status"] == "PASS"
        and timing_by_label["68060 odd opening"]["status"] == "PASS"
        and timing_by_label["68030 odd opening"]["frame_sha256"] == timing_by_label["68060 odd opening"]["frame_sha256"]
        and (ROOT / timing_by_label["68030 odd opening"]["frame_path"]).read_bytes() == (ROOT / timing_by_label["68060 odd opening"]["frame_path"]).read_bytes()
    )
    even_equal = (
        timing_by_label["68030 even opening"]["status"] == "PASS"
        and timing_by_label["68060 even opening"]["status"] == "PASS"
        and timing_by_label["68030 even opening"]["frame_sha256"] == timing_by_label["68060 even opening"]["frame_sha256"]
        and (ROOT / timing_by_label["68030 even opening"]["frame_path"]).read_bytes() == (ROOT / timing_by_label["68060 even opening"]["frame_path"]).read_bytes()
    )
    route = route_inventory()
    route_artifacts = [row["path"] for row in route["rows"]]
    route_present = route["status"] == "PASS"
    pcx = dos_pcx_inventory()
    terrain_tool = ROOT / "tools/compare-terrain.py"
    terrain_text = terrain_tool.read_text(errors="replace") if terrain_tool.is_file() else ""
    normalizer_present = all(marker in terrain_text for marker in (
        "def load_pcx", "def to565", "PORT_W, PORT_H = 320, 240",
        "328 wide", "raw[-769] == 0x0C",
    ))
    replay = replay_fixture_inventory()
    replay_passes = next((row for row in replay["rows"] if row["path"].endswith("replay-passes.json")), {})
    three_way = three_way_inventory()
    complete_frames = complete_frame_inventory()
    sequence = sequence_inventory()
    function_audit = function_audit_inventory()
    toolchain = toolchain_inventory()
    gate_status = {
        "function audit": "PASS" if not missing_headers and route_present and function_audit["status"] == "PASS" else "Unproven",
        "three-way replay": three_way["status"],
        "complete frames": complete_frames["status"],
        # The current witness is intentionally browser-only.  It can expose a
        # missing camera/transition path, but it cannot certify DOS/Falcon
        # sequence fidelity by itself.
        "complete sequence": "PASS" if sequence["status"] == "PASS" and sequence["result"].get("scope") == "all-three" else "Unproven",
        "real target": "Unproven",
    }
    evidence = {
        "source_hash": source_hash,
        "source_rows": source_rows,
        "git": git,
        "headers": headers,
        "missing_headers": missing_headers,
        "missing_records": missing_records,
        "missing_ids": missing_ids,
        "browser_records": browser_records,
        "browser": browser,
        "substitutions": substitutions,
        "cpu": cpu,
        "timing": timing,
        "odd_equal": odd_equal,
        "even_equal": even_equal,
        "route_artifacts": route_artifacts,
        "route_present": route_present,
        "route": route,
        "pcx": pcx,
        "normalizer_present": normalizer_present,
        "replay": replay,
        "replay_passes": replay_passes,
        "three_way": three_way,
        "complete_frames": complete_frames,
        "sequence": sequence,
        "function_audit": function_audit,
        "toolchain": toolchain,
        "gate_status": gate_status,
    }
    unproven_count = sum(value == "Unproven" for value in gate_status.values())
    failed_count = sum(value in ("DIVERGENCE", "FAIL") for value in gate_status.values())
    generated = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    lines: list[str] = []
    add = lines.append
    add("# F030 Comanche attract-mode acceptance report")
    add("")
    add("**Verdict: NOT CERTIFIED.** The current supported attract-mode slice has passing component evidence, but the required DOS-fidelity gates are not all proven. Missing evidence is reported as **Unproven**; there is no overall PASS claim.")
    add("")
    add(f"Generated UTC: `{generated}`  ")
    add(f"Acceptance gates Unproven: `{unproven_count}/5`; failed: `{failed_count}/5`  ")
    add("Re-run command: `python3 tools/acceptance-report.py` (returns exit code 1 while any certification gate is Unproven).")
    add("")
    add("## 1. Scope and identity")
    add("")
    add("This report covers the CPU-only Falcon attract route: authored opening pages, the four recorded DEMO pass families, replay-driven flight, terrain, active objects, cockpit/MFD/HUD and page publication. DSP, live controls, sound, menu handoff and mission completion are outside the certified slice.")
    add("")
    add("| identity | value |")
    add("|---|---|")
    add(f"| Git HEAD | `{git['head']}` — {git['subject']} |")
    add(f"| Worktree | `{'dirty' if git['dirty'] else 'clean'}`; `{git['changed_count']}` changed/untracked paths at report time |")
    add(f"| Source snapshot | `{source_hash}` over `{len(source_rows)}` selected source/record files |")
    add(f"| DOS oracle | `{rel(DOS_EXE)}`; `{format_hash(sha256_file(DOS_EXE))}`; expected `{DOS_SHA256}` |")
    add(f"| DOS flat image | `{rel(DOS_FLAT)}`; `{format_hash(sha256_file(DOS_FLAT))}`; expected `{DOS_FLAT_SHA256}` |")
    add(f"| Toolchain manifest | {link(toolchain['path'])}; `{format_hash(toolchain['sha256'])}` |")
    add("")
    add("The source hash is a filesystem snapshot, not a claim that the worktree is committed. The exact build inputs are therefore recoverable even though the tree is dirty.")
    add("")
    add("### Target binaries")
    add("")
    add("| image | path | size | SHA-256 |")
    add("|---|---|---:|---|")
    for label, path_text in BUILD_FILES:
        path = ROOT / path_text
        add(f"| {label} | `{path_text}` | {path.stat().st_size if path.is_file() else 'Unproven'} | `{format_hash(sha256_file(path))}` |")
    add("")
    add("### Toolchain components")
    add("")
    if toolchain["data"]:
        add("| component | executable/image | recorded SHA-256 |")
        add("|---|---|---|")
        for name, data in toolchain["data"].items():
            add(f"| {name} | `{data.get('path', 'Unproven')}` | `{data.get('sha256', 'Unproven')}` |")
    else:
        add("Toolchain manifest: **Unproven**.")
    add("")
    add("## 2. Certification gates")
    add("")
    add("| gate | status | evidence observed | missing evidence / stopping condition |")
    add("|---|---|---|---|")
    function_audit_missing = "; ".join(function_audit["problems"]) if function_audit["problems"] else "—"
    add(f"| Function provenance and contract audit | **{gate_status['function audit']}** | {len(headers)} annotated M68k routine headers; {len(browser_records['headings'])} browser records; source-header fields complete: {'PASS' if not missing_headers else 'Unproven'}; matrix artifact {link(function_audit['path'])} | {function_audit_missing}; validated route witness set is **{route['status']}** |")
    three_way_result = three_way["result"]
    three_way_comparisons = three_way_result.get("comparisons", {}) if isinstance(three_way_result, dict) else {}
    three_way_observed = "; ".join(
        f"{name}: {row.get('status', 'Unproven')} {row.get('records_compared', 0)}/{row.get('records_expected', SUPPORTED_RECORDS)}"
        for name, row in three_way_comparisons.items()
    ) or "no comparison rows"
    three_way_missing = "; ".join(three_way["problems"]) if three_way["problems"] else "—"
    add(f"| DOS → JavaScript → 68030/68060 replay | **{gate_status['three-way replay']}** | {three_way_observed}; artifact {link(three_way['path'])} (`{format_hash(three_way['sha256'])}`) | {three_way_missing} |")
    frame_result = complete_frames["result"]
    frame_pixels = frame_result.get("pixels", {}) if isinstance(frame_result, dict) else {}
    frame_observed = f"{frame_pixels.get('identical', 0)}/{frame_pixels.get('compared', 0)} pixels" if frame_pixels else "no paired pixels"
    frame_missing = "; ".join(complete_frames["problems"]) if complete_frames["problems"] else "—"
    add(f"| Complete normalized rendered frames | **{gate_status['complete frames']}** | `compare-terrain.py` and {link('tools/compare-complete-frame.py')} implement palette/page/window normalization; {frame_observed}; artifact {link(complete_frames['path'])} (`{format_hash(complete_frames['sha256'])}`) | {frame_missing} |")
    sequence_result = sequence["result"]
    sequence_passes = sequence_result.get("observed_passes", []) if isinstance(sequence_result, dict) else []
    sequence_observed = f"browser witness: {len(sequence_passes)}/4 pass transitions; artifact {link(sequence['path'])} (`{format_hash(sequence['sha256'])}`)" if sequence_result else "no sequence witness"
    sequence_missing = "; ".join(sequence["problems"]) if sequence["problems"] else "DOS and Falcon all-pass sequence not captured"
    add(f"| Complete supported sequence | **{gate_status['complete sequence']}** | {sequence_observed} | {sequence_missing} |")
    add("| Real stock Falcon and accelerator cache behavior | **Unproven** | Hatari/EmuTOS/Falcon configuration is fingerprinted; CPU arithmetic harness passes | No stock-Falcon performance/memory/input/display/cleanup measurement and no separate cached-vs-published accelerator validation |")
    add("")
    add("The first two component checks below are useful regression checks, but neither can promote the five gates to certified status by itself.")
    add("")
    add("## 3. Component evidence that is currently PASS")
    add("")
    add("### CPU arithmetic")
    add("")
    add("| CPU | result | pairs | exact products | product-stream SHA-256 | harness SHA-256 |")
    add("|---:|---|---:|---:|---|---|")
    for target in (68030, 68060):
        row = cpu[target]
        result = row["result"]
        add(f"| {target} | **{row['status']}** | {result.get('pairs', 'Unproven')} | {result.get('products', 'Unproven')} | `{result.get('sha256', 'Unproven')}` | `{format_hash(row['program_sha256'])}` |")
    add("")
    add("Both multiply result files are tied to the current `check.tos` hashes and contain the expected 1,193 input pairs / 4,772 exact products.")
    add("")
    add("### Browser and substitution gates")
    add("")
    add(f"Browser source/provenance gate: **{browser['status']}**. It found `{len(browser_records['js_files'])}` JavaScript files and `{len(browser_records['headings'])}` browser record anchors. The fresh gate output was:")
    add("")
    add("```")
    add(browser["output"])
    add("```")
    add("")
    add(f"Generated substitution inventory check: **{substitutions['status']}** ({link('docs/SUBSTITUTIONS.md')}).")
    add("")
    add("### Countdown, replay byte order and CPU-to-CPU frame equality")
    add("")
    add("The timing cases below are separate artifact directories. Each result checks its screen ticks, replay byte order, `publish_screen` checkpoint, debug-program hash and 320×240 RGB565 frame length/hash.")
    add("")
    add("| case | result | screen ticks | frame SHA-256 | debug program SHA-256 | evidence |")
    add("|---|---|---|---|---|---|")
    for row in timing:
        result = row["result"]
        add(f"| {row['label']} | **{row['status']}** | `{result.get('screen_ticks', 'Unproven')}` | `{format_hash(row['frame_sha256'])}` | `{format_hash(row['program_sha256'])}` | {link(row['result_path'])}; {link(row['frame_path'])} |")
    add("")
    add(f"Odd-opening 68030↔68060 frame bytes: **{'PASS' if odd_equal else 'Unproven'}**; frame `{timing_by_label['68030 odd opening']['frame_sha256'] if odd_equal else 'Unproven'}`.")
    add(f"Even-opening 68030↔68060 frame bytes: **{'PASS' if even_equal else 'Unproven'}**; frame `{timing_by_label['68030 even opening']['frame_sha256'] if even_equal else 'Unproven'}`.")
    add("")
    add("These are target-to-target equality checks. They do not establish DOS pixel fidelity.")
    add("")
    add("## 4. Function provenance and compliance audit")
    add("")
    add("The audit scans every annotated `.s` routine header under `src/` and requires `DOS`, `Record`, `Route`, `Port`, `Preserved`, `Kind` and `Status`; file-level `Route`/`Record` declarations are inherited by routines in that source file, and a routine-local declaration overrides them. `DOS: N/A` is accepted only as an explicit target/platform replacement. It also requires an address-like canonical DOS ID for non-target entries.")
    add("")
    add(f"M68k headers discovered: `{len(headers)}`. Headers with at least one missing required field or canonical ID: `{len(missing_headers)}`. Missing `Record:`: `{len(missing_records)}`. Missing canonical DOS ID: `{len(missing_ids)}`.")
    route_description = "present and content-valid" if route_present else "missing or content-invalid"
    add(f"The route witness set is **{route_description}**. Until it is valid, this remains a conservative source-wide scan; it does not pretend to know that an unlisted helper was unreached.")
    add("")
    if missing_headers:
        add("Unresolved headers:")
        add("")
        for row in missing_headers:
            missing = ", ".join(row["missing"])
            add(f"- `{row['symbol']}` at `{row['path']}:{row['line']}` — missing `{missing}`")
        add("")
    else:
        add("No missing M68k header fields were found.")
        add("")
    add(f"Browser record anchors: `{len(browser_records['headings'])}` headings; JS references `{len(browser_records['refs'])}` distinct anchors across `{len(browser_records['js_files'])}` files. This proves annotation coverage for the browser slice, not one-to-one reached-function coverage for M68k. The static scan cannot infer a JavaScript counterpart or fixture for every M68k row; those columns remain **Unproven** outside the representative matrix.")
    add("")
    add("### Representative boundary matrix")
    add("")
    add("This is the shape required for the exhaustive matrix; it is intentionally labelled representative because the gate remains **Unproven** until every reached helper is row-complete.")
    add("")
    add("| canonical DOS ID | recovered contract | JavaScript counterpart | M68k counterpart | fixtures / checks |")
    add("|---|---|---|---|---|")
    for dos_id, contract, js_name, m68k_name, fixtures in FUNCTION_ROWS:
        add(f"| `{dos_id}` | {contract} | `{js_name}` | `{m68k_name}` | {fixtures} |")
    add("")
    add("Route witness contents are checked, not just their filenames. A range report must show positive execution counts for the attract/frame/replay/flight/terrain/object/composition families; the object snapshot must show the traced state and draw targets.")
    add("")
    add("| route witness | status | size | SHA-256 | missing requirements |")
    add("|---|---|---:|---|---|")
    for row in route["rows"]:
        missing = ", ".join(row["missing"]) if row["missing"] else "—"
        add(f"| `{row['path']}` | **{row['status']}** | {row['size'] if row['size'] is not None else 'Unproven'} | `{format_hash(row['sha256'])}` | {missing} |")
    add("")
    add(f"Validated route witness set: **{route['status']}**. The generated reached-function matrix is {link(function_audit['path'])}: **{function_audit['status']}**. The source-header scan is a prerequisite only; it cannot infer a JavaScript counterpart or fixture for a reached helper without this matrix.")
    add("")
    add("## 5. Three-way replay boundary")
    add("")
    add(f"Existing DOS fixture records: {link('work/replay_dos/flight-demo1.json')}, {link('work/replay_dos/flight-dos.json')}, {link('work/replay_dos/view-demo1.json')} and {link('work/replay_dos/replay-passes.json')}. Existing tools include {link('tools/certify-replay-flight.py')} and {link('tools/compare-marcher.py')}.")
    add("")
    add("| fixture | rows/replays | DOS breakpoint | SHA-256 |")
    add("|---|---:|---:|---|")
    for row in replay["rows"]:
        count = row.get("rows", row.get("replays", "Unproven")) if row.get("exists") else "Unproven"
        breakpoint = row.get("breakpoint", "—") if row.get("exists") else "Unproven"
        add(f"| `{row['path']}` | {count} | {breakpoint} | `{format_hash(row['sha256'])}` |")
    add("")
    add(f"Boundary comparison command output: **{three_way['status']}**.")
    add("")
    add("```")
    add(three_way["output"])
    add("```")
    add("")
    add("The comparison joins the same DEMO1.SCR byte cursor and checks raw DOS 10.22 position, angle, altitude, turn, forward/lateral velocity, roll and pitch at each flight-publish row. The browser trace also carries the exact input bytes and framebuffer hash for each tick.")
    add("")
    add(f"The supported DEMO1 range is the first {SUPPORTED_RECORDS} records. Record index {SUPPORTED_RECORDS} is the no-damage bounce at 00019461 that arms the screen shake; from the next timer tick DOS pans its display through 00001DF1 and 00015BBC, which the cross-machine target has not recovered. The parity comparison therefore stops the armed presentation there, while the browser-only witness continues with its documented crop adaptation. Rows past the bounce are outside the cross-machine scope; they are not evidence of divergence. The flight arithmetic beyond it was measured separately at the DOS breakpoint by `work/trace_replay_flight.py` (see `docs/PORTING-PLAN.md`).")
    add("")
    add("**First divergence:**")
    add("")
    for name in ("javascript", "68030", "68060"):
        row = three_way_comparisons.get(name, {})
        divergence = row.get("first_divergence") if isinstance(row, dict) else None
        if divergence:
            add(f"- `{name}`: tick `{divergence.get('tick')}`, cursor `{divergence.get('cursor')}`, function `{divergence.get('function_ids')}`, field `{divergence.get('field')}`, DOS `{divergence.get('dos')}`, actual `{divergence.get('actual')}`")
        elif row.get("status") == "PASS":
            add(f"- `{name}`: none across `{row.get('records_compared', 0)}` rows")
        else:
            add(f"- `{name}`: **Unproven** — no complete boundary trace")
    add("")
    add("The required future trace row is: replay/pass ID, tick, canonical DOS function ID, input bytes, pre-state, post-state, return/output words, target CPU and surface/page publication hash. The checker must stop at the first unequal row rather than summarize only aggregate agreement.")
    add("")
    add("## 6. Complete-frame normalization")
    add("")
    add(f"The available comparator is {link('tools/compare-terrain.py')}. It documents the DOS 8-bit PCX surface, 328-pixel source page/window and the port's left 320-pixel view. Its palette normalization is the documented RGB565 conversion: `((R >> 3) << 11) | ((G >> 2) << 5) | (B >> 3)`.")
    add("")
    add(f"Normalizer implementation present: **{'PASS' if normalizer_present else 'Unproven'}**. Retained valid 328×240 DOS PCX candidates: `{len(pcx['candidates'])}` (`{len(pcx['palette_candidates'])}` with a palette block) across `{len(pcx['groups'])}` ignored build directories.")
    if pcx["groups"]:
        add("")
        add("Candidate groups (inventory only; not accepted as paired parity evidence):")
        add("")
        for directory, count in pcx["groups"].items():
            add(f"- `{directory}`: `{count}` files")
        if pcx["sample"]:
            add(f"- sample: {link(pcx['sample'])}; `{pcx['sample_sha256']}`")
    add("")
    add(f"The page/pan-aware acceptance artifact is {link(complete_frames['path'])}: **{complete_frames['status']}**.")
    add("")
    add("The complete-frame gate requires one 320×240 RGB565 target dump and one DOS 328×240 PCX from the same replay tick and camera, with page and pan metadata recorded on both sides. It compares every terrain, object, cockpit, MFD and HUD pixel after the documented six-bit palette conversion; an absent pair remains **Unproven**.")
    add("")
    add("## 7. Complete supported sequence")
    add("")
    add("The recorded pass map is:")
    add("")
    add("| pass index | key | replay | resources |")
    add("|---:|---:|---|---|")
    replay_path = ROOT / "work/replay_dos/replay-passes.json"
    if replay_path.is_file():
        try:
            for row in json.loads(replay_path.read_text()).get("replays", []):
                add(f"| {row.get('index', 'Unproven')} | `{row.get('digit', 'Unproven')}` | `{row.get('stream', 'Unproven')}` | `{', '.join(row.get('resources', []))}` |")
        except json.JSONDecodeError:
            add("| Unproven | Unproven | Unproven | invalid replay-passes.json |")
    else:
        add("| Unproven | Unproven | Unproven | missing replay-passes.json |")
    add("")
    sequence_result = sequence["result"]
    add(f"The deterministic browser sequence witness is {link(sequence['path'])}: **{sequence['status']}**.")
    if sequence_result:
        add(f"It observed `{sequence_result.get('observed_passes', [])}`, `{len(sequence_result.get('transition_events', []))}` transition events, `{sum(sequence_result.get('command_key_counts', {}).values())}` replay command keys, and `{sequence_result.get('buffer_reuse', {}).get('frame_hashes_observed', 0)}` frame hashes while checking terrain-buffer identity.")
        boundary = sequence_result.get("supported_boundary")
        if isinstance(boundary, dict):
            add("")
            add(f"The witness stopped at the supported boundary, pass `{boundary.get('pass')}` record `{boundary.get('record')}`: {boundary.get('reason')}. The later passes are reachable only through the rest of pass 1, so the sequence gate cannot progress until the display shake is recovered.")
    add("")
    add("The certification gate remains **Unproven** unless the same transition/camera/replay/buffer assertions are captured for DOS and both Falcon CPU builds. The current browser witness does exercise external-camera selectors, but it is not a substitute for paired DOS and current-hash Falcon captures.")
    add("")
    add("## 8. Real-target and cache validation")
    add("")
    add("The recorded target environment is Hatari Falcon mode with 14 MB, DSP off, EmuTOS/TOS assets and the local vasm/vlink toolchain. That is a useful emulator regression environment, not a stock-Falcon measurement.")
    add("")
    add("Still **Unproven**:")
    add("")
    add("- stock 68030 frame time, memory headroom and input latency;")
    add("- Videl display/page behavior and cleanup across repeated attract transitions;")
    add("- accelerator cache-on/cache-off behavior, cache publication ordering and performance separately from numerical equality.")
    add("")
    add("## 9. Repeatable procedure")
    add("")
    add("Build the desired debug images, then run these serially so each artifact has a stable directory. The two Hatari replay captures are intentionally explicit: the 68060 interpreter may take several minutes.")
    add("")
    add("```sh")
    add("TARGET_CPU=68030 OUTDIR=release bash tools/build-run.sh")
    add("TARGET_CPU=68060 OUTDIR=release/68060 bash tools/build-run.sh")
    add("python3 tools/check-cpu-compatibility.py")
    add("python3 tools/check-attract-timing.py --cpu 68030 --artifact-dir build/acceptance/attract-68030-odd")
    add("python3 tools/check-attract-timing.py --cpu 68060 --artifact-dir build/acceptance/attract-68060-odd")
    add("python3 tools/check-attract-timing.py --cpu 68030 --even-pass --artifact-dir build/acceptance/attract-68030-even")
    add("python3 tools/check-attract-timing.py --cpu 68060 --even-pass --artifact-dir build/acceptance/attract-68060-even")
    add("node tools/prove-browser-attract.js")
    add("python3 tools/audit-function-matrix.py --out build/acceptance/function-audit.json || true")
    add(f"node tools/trace-browser-replay.js --pass 1 --records {SUPPORTED_RECORDS} --out build/acceptance/three-way/browser-demo1.json")
    add(f"python3 tools/trace-falcon-replay.py --cpu 68030 --records {SUPPORTED_RECORDS} --run-vbls 50000 --out build/acceptance/three-way/falcon-68030/falcon-68030.json")
    add(f"python3 tools/trace-falcon-replay.py --cpu 68060 --records {SUPPORTED_RECORDS} --run-vbls 270000 --timeout 2400 --out build/acceptance/three-way/falcon-68060/falcon-68060.json")
    add(f"python3 tools/compare-boundary-traces.py --records {SUPPORTED_RECORDS}")
    add("node tools/trace-browser-sequence.js build/acceptance/sequence/browser-sequence.json || true")
    add("python3 tools/acceptance-report.py")
    add("```")
    add("")
    add("The final command is expected to return 1 for this snapshot. That failure is the acceptance signal that the report still contains **Unproven** gates, not a hidden overall PASS.")
    add("")
    add("## 10. Evidence references")
    add("")
    add(f"- DOS route and contract record: {link('analysis/functions/falcon-attract.md')}")
    add(f"- Browser function records and fixture boundary: {link('analysis/functions/browser-attract.md')}")
    add(f"- DOS oracle capture and palette/page normalization notes: {link('docs/DOS-ORACLE.md')}")
    add(f"- CPU arithmetic distinction and target notes: {link('analysis/functions/cpu-compatibility.md')}")
    add(f"- Build/run procedure: {link('tools/README.md')}")
    add("")
    return "\n".join(lines) + "\n", evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_DEFAULT,
                        help="report path relative to the project root")
    parser.add_argument("--skip-browser-proof", action="store_true",
                        help="do not run node tools/prove-browser-attract.js")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    report, evidence = build_report(args.skip_browser_proof)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    print(f"WROTE {rel(output)}")
    for name, result in evidence["gate_status"].items():
        print(f"{result:9} {name}")
    return 1 if any(value != "PASS" for value in evidence["gate_status"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
