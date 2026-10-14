#!/usr/bin/env python3
"""Dump the Falcon port's published frame at a replay cursor, under Hatari.

The DOS half of a complete-frame pair is `work/capture_dos_frame.py`: the
original's own PCX writer, run from `00006AE9` when `[0x19ECC]` holds the
cursor. Its page is loop N's completed frame, taken after loop N consumed its
record. The port's equivalent instant is the `publish_screen` call at the end
of the main loop (`src/main.s`): `frame_driver` has rendered and consumed the
record, the buffers have been exchanged, and `d0` holds the buffer being
published. So this stops there, gated on `demo_cursor`, and saves 320x240
big-endian RGB565 from `d0` - no second pass to dereference the pointer.

The program and its assets are staged into the output directory through
`tools/build-run.sh`'s OUTDIR, so the probe never writes into `release/`.

    python3 tools/capture-target-frame.py --record 20 --out build/frame-pair/falcon-r20

N/A - target artefact: a capture harness, no DOS routine.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FRAME_BYTES = 320 * 240 * 2
SCALARS = [
    ("cursor.bin", "demo_cursor", 4),
    ("active.bin", "demo_active", 2),
    ("pass.bin", "attract_demo_pass", 2),
    ("variant.bin", "view_variant", 1),
    ("ws.bin", "work_screen", 4),
    ("ds.bin", "display_screen", 4),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", type=int, required=True,
                    help="replay record index; demo_cursor = record*8 + 13")
    ap.add_argument("--pass", dest="demo_pass", type=int, choices=range(4), default=1,
                    help="DEMO stream to capture (default: 1, the first attract pass)")
    ap.add_argument("--variant", type=int, choices=range(1, 8), default=1,
                    help="required camera variant (default: 1, cockpit)")
    ap.add_argument("--arm-vbl", type=int, default=1500,
                    help="VBL at which the cursor breakpoint is armed "
                         "(symbols cannot load before the program has)")
    ap.add_argument("--run-vbls", type=int, default=9000)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()
    if args.record < 1 or args.arm_vbl < 1 or args.run_vbls <= args.arm_vbl:
        ap.error("record and arm-vbl must be positive; run-vbls must exceed arm-vbl")

    out = (ROOT / args.out).resolve() if not os.path.isabs(args.out) else pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave an earlier successful identity beside it.
    (out / "target-frame.json").unlink(missing_ok=True)
    if not args.no_build:
        r = subprocess.run(["bash", "tools/build-run.sh", "--no-run"],
                           cwd=ROOT, text=True, capture_output=True,
                           env=dict(os.environ, OUTDIR=str(out), TARGET_CPU="68030"))
        if r.returncode != 0:
            sys.exit(f"build failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    cursor = args.record * 8 + 13
    probe = ["r", f"savebin frame.bin d0 ${FRAME_BYTES:x}"]
    probe += [f"savebin {name} {symbol} ${size:x}" for name, symbol, size in SCALARS]
    probe.append("quit")
    (out / "dump.ini").write_text("\n".join(probe) + "\n")
    # The program is started through Hatari's GEMDOS drive, so symbols can be
    # loaded the moment its text is in RAM (`b pc = TEXT`) instead of at a guessed
    # VBL: Hatari 2.6 refuses `symbols` until the program is resident, and a
    # fixed arm VBL either races the load or misses the cursor.
    (out / "boot.ini").write_text(
        "b GemdosOpcode = $4b && OsCallParam = 0 :trace :once :file program.ini\n")
    (out / "program.ini").write_text("b pc = TEXT :trace :once :file arm.ini\n")
    (out / "arm.ini").write_text(
        "symbols comanche_d.tos\n"
        f"b pc = publish_screen && (demo_cursor).l = {cursor} "
        f"&& (demo_active).w = 1 && (attract_demo_pass).w = {args.demo_pass} "
        f"&& (view_variant).b = {args.variant} :once :file dump.ini\n")
    for name in ["frame.bin"] + [n for n, _, _ in SCALARS]:
        (out / name).unlink(missing_ok=True)

    tos = str(pathlib.Path(os.environ.get(
        "TOS", str(ROOT / "tools" / "toolchain" / "tos402.rom"))).resolve())
    hatari = shutil.which(os.environ.get("HATARI") or "hatari")
    if hatari is None:
        sys.exit("Hatari executable is missing; set HATARI or add hatari to PATH")
    timeout = 120 + args.run_vbls // 20
    cmd = [hatari, "--memsize", "14", "--tos", tos, "--patch-tos", "true",
           "--mmu", "true", "--frameskips", "0", "--monitor", "rgb",
           "--machine", "falcon", "--dsp", "off", "--cpulevel", "3",
           "--fpu", "none", "--fast-boot", "true", "--sound", "off",
           "--fast-forward", "true", "--cpu-exact", "true", "--compatible", "true",
           "--confirm-quit", "off", "--disable-video", "on", "--run-vbls",
           str(args.run_vbls), "--harddrive", str(out), "--auto", "C:\\comanche_d.tos",
           "--parse", "boot.ini", "--log-file", "hatari.log",
           "--alert-level", "fatal"]
    # Keep the Windows runner's UCRT dependency without shell redirection.
    env = dict(os.environ)
    if os.name == "nt":
        env["PATH"] = r"C:\msys64\ucrt64\bin" + os.pathsep + env.get("PATH", "")
    try:
        with (out / "hatari-stdout.txt").open("w") as log:
            run = subprocess.run(cmd, cwd=out, stdin=subprocess.DEVNULL,
                                 stdout=log, stderr=subprocess.STDOUT, timeout=timeout, env=env)
    except (subprocess.TimeoutExpired, OSError) as error:
        sys.exit(f"Hatari capture failed: {error}; see {out / 'hatari-stdout.txt'}")

    frame = out / "frame.bin"
    if not frame.is_file() or frame.stat().st_size != FRAME_BYTES:
        print((out / "hatari-stdout.txt").read_text(errors="replace")[-1500:],
              file=sys.stderr)
        sys.exit(f"no {FRAME_BYTES}-byte frame at cursor {cursor}")
    meta = {"record": args.record, "cursor_wanted": cursor,
            "pass_wanted": args.demo_pass, "variant_wanted": args.variant,
            "command": cmd, "hatari_returncode": run.returncode,
            "sha256": {"program": hashlib.sha256((out / "comanche_d.tos").read_bytes()).hexdigest(),
                       "tos": hashlib.sha256(pathlib.Path(tos).read_bytes()).hexdigest(),
                       "hatari": hashlib.sha256(pathlib.Path(hatari).read_bytes()).hexdigest(),
                       "capture_tool": hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                       "frame": hashlib.sha256(frame.read_bytes()).hexdigest()},
            "breakpoint": "publish_screen (src/main.s main loop)",
            "frame": str(frame.relative_to(ROOT)) if frame.is_relative_to(ROOT) else str(frame)}
    for name, symbol, size in SCALARS:
        raw = (out / name).read_bytes() if (out / name).is_file() else b""
        meta[symbol] = int.from_bytes(raw, "big") if len(raw) == size else None
    problems = []
    for symbol, expected in [("demo_cursor", cursor), ("demo_active", 1),
                             ("attract_demo_pass", args.demo_pass),
                             ("view_variant", args.variant)]:
        if meta[symbol] != expected:
            problems.append(f"{symbol}: expected {expected}, captured {meta[symbol]}")
    if meta["display_screen"] is None or meta["display_screen"] == 0:
        problems.append("published display pointer is missing or null")
    if run.returncode != 0:
        problems.append(f"Hatari exited with status {run.returncode}")
    meta["problems"] = problems
    meta["status"] = "CAPTURED" if not problems else "Unproven"
    (out / "target-frame.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps(meta, indent=1))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
