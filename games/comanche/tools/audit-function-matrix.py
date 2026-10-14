#!/usr/bin/env python3
"""Emit the implementation-wide reached-function audit matrix.

The source-header scan supplies identities and links, but it does not invent a
JavaScript counterpart, a fixture, or reachability.  Rows remain Unproven
until those facts are explicitly recorded.  This is intentional: an address
range report is not a substitute for a per-function route witness.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_acceptance_module():
    path = ROOT / "tools/acceptance-report.py"
    spec = importlib.util.spec_from_file_location("acceptance_report", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def section_text(path: Path, fragment: str) -> str:
    text = path.read_text(errors="replace")
    for match in re.finditer(r"^(#{1,6})\s+(.+?)\s*$", text, re.M):
        heading = re.sub(r"[^a-z0-9]+", "-", match.group(2).lower()).strip("-")
        if heading != fragment.lower():
            continue
        tail = text[match.end():]
        next_heading = re.search(r"^#{1,6}\s+", tail, re.M)
        return tail[:next_heading.start()] if next_heading else tail
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "build/acceptance/function-audit.json")
    args = ap.parse_args()
    acceptance = load_acceptance_module()
    headers = acceptance.parse_source_headers()
    route = acceptance.route_inventory()
    rows: list[dict[str, Any]] = []
    for header in headers:
        fields = header["fields"]
        record_value = fields.get("Record", "Unproven")
        record_path = None
        fragment = None
        if record_value != "Unproven":
            match = re.match(r"([^#]+)(?:#([A-Za-z0-9_-]+))?$", record_value)
            if match:
                record_path = ROOT / match.group(1)
                fragment = match.group(2)
        record_section = section_text(record_path, fragment) if record_path and fragment and record_path.is_file() else ""
        contract = "linked record present" if record_section else "Unproven"
        # These two fields must be explicit per reached routine.  A broad
        # Falcon record, or a browser file containing a similarly named
        # method, is not accepted as a one-to-one mapping.
        javascript = "Unproven"
        fixtures = "Unproven"
        missing = list(header["missing"])
        if contract == "Unproven":
            missing.append("recovered contract")
        missing.extend(("JavaScript counterpart", "associated fixtures", "exact reach witness"))
        rows.append({
            "source": f"{header['path']}:{header['line']}",
            "m68k_counterpart": header["symbol"],
            "canonical_dos_id": fields.get("DOS", "Unproven"),
            "recovered_contract": contract,
            "record": record_value,
            "javascript_counterpart": javascript,
            "fixtures": fixtures,
            "reach": "Unproven",
            "missing": sorted(set(missing)),
            "status": "Unproven",
        })
    problems = [
        "per-routine execution PCs are not mapped to source symbols",
        "JavaScript counterparts are not recorded one-to-one for every reached routine",
        "fixtures/checks are not recorded one-to-one for every reached routine",
    ]
    result = {
        "schema": "f030-function-audit-v1",
        "status": "Unproven",
        "source_header_count": len(headers),
        "rows": rows,
        "route_witnesses": [{"path": row["path"], "sha256": sha256(ROOT / row["path"])} for row in route["rows"]],
        "problems": problems,
    }
    output = args.out if args.out.is_absolute() else ROOT / args.out
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Unproven: {len(rows)} function rows emitted; {len(rows)} require explicit reached-function mapping -> {output}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
