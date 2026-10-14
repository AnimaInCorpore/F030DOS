#!/usr/bin/env python3
"""Compare a complete DOS PCX page with a 320x240 RGB565 target frame.

The caller must provide the page and pan metadata captured at the same replay
tick/camera.  A valid PCX candidate without that metadata is inventory only;
it cannot silently become a parity result.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRAME_W, FRAME_H = 320, 240


def load_terrain_module():
    path = ROOT / "tools/compare-terrain.py"
    spec = importlib.util.spec_from_file_location("compare_terrain", path)
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dos-pcx", type=Path, required=True)
    ap.add_argument("--target-frame", type=Path, required=True)
    ap.add_argument("--dos-page", required=True)
    ap.add_argument("--target-page", required=True)
    ap.add_argument("--dos-pan-x", type=int, required=True)
    ap.add_argument("--dos-pan-y", type=int, required=True)
    ap.add_argument("--target-pan-x", type=int, required=True)
    ap.add_argument("--target-pan-y", type=int, required=True)
    ap.add_argument("--tick", type=int, required=True)
    ap.add_argument("--camera", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "build/acceptance/frames/complete-frame-comparison.json")
    args = ap.parse_args()
    dos = args.dos_pcx.resolve()
    target = args.target_frame.resolve()
    output = args.out if args.out.is_absolute() else ROOT / args.out
    result: dict[str, Any] = {
        "schema": "f030-complete-frame-comparison-v1",
        "status": "Unproven",
        "tick": args.tick,
        "camera": args.camera,
        "dos": {"path": str(dos.relative_to(ROOT)) if dos.is_relative_to(ROOT) else str(dos), "sha256": sha256(dos), "page": args.dos_page, "pan": [args.dos_pan_x, args.dos_pan_y]},
        "target": {"path": str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target), "sha256": sha256(target), "page": args.target_page, "pan": [args.target_pan_x, args.target_pan_y]},
        "normalization": "PCX palette DAC bytes to RGB565; DOS source window is 320x240 from the supplied pan",
        "pixels": {"compared": 0, "identical": 0, "first_mismatch": None},
        "problems": [],
    }
    if not dos.is_file():
        result["problems"].append("DOS PCX is missing")
    if not target.is_file():
        result["problems"].append("target RGB565 frame is missing")
    if args.dos_page != args.target_page:
        result["problems"].append("page selection differs")
    if [args.dos_pan_x, args.dos_pan_y] != [args.target_pan_x, args.target_pan_y]:
        result["problems"].append("panning differs")
    if not result["problems"]:
        terrain = load_terrain_module()
        width, height, pixels, palette = terrain.load_pcx(dos)
        if palette is None:
            result["problems"].append("DOS PCX has no 0x0C palette block")
        elif args.dos_pan_x < 0 or args.dos_pan_y < 0 or args.dos_pan_x + FRAME_W > width or args.dos_pan_y + FRAME_H > height:
            result["problems"].append(f"DOS pan window is outside {width}x{height} PCX")
        else:
            raw = target.read_bytes()
            expected_bytes = FRAME_W * FRAME_H * 2
            if len(raw) != expected_bytes:
                result["problems"].append(f"target frame is {len(raw)} bytes, expected exactly {expected_bytes}")
            else:
                identical = 0
                first = None
                for y in range(FRAME_H):
                    for x in range(FRAME_W):
                        source = pixels[((args.dos_pan_y + y) * width) + args.dos_pan_x + x]
                        want = terrain.to565(palette[source])
                        got = struct.unpack_from(">H", raw, ((y * FRAME_W) + x) * 2)[0]
                        if want == got:
                            identical += 1
                        elif first is None:
                            first = {"x": x, "y": y, "dos_rgb565": want, "target_rgb565": got, "dos_index": source}
                result["pixels"] = {"compared": expected_bytes // 2, "identical": identical, "first_mismatch": first}
    if not result["problems"]:
        result["status"] = "PASS" if result["pixels"]["identical"] == result["pixels"]["compared"] else "DIVERGENCE"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{result['status']}: complete frame comparison -> {output}")
    if result["pixels"]["first_mismatch"]:
        print(f"  first mismatch: {result['pixels']['first_mismatch']}")
    for problem in result["problems"]:
        print(f"  Unproven: {problem}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
