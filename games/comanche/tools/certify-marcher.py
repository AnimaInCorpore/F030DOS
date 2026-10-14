#!/usr/bin/env python3
"""Run src/render.s's OWN marcher at a captured DOS camera and diff its
silhouette against the original's.

This is the last link in the terrain chain. Already measured, both 100%:

  * tools/compare-marcher.py      - a Python model of 0000D950 vs the original
  * tools/compare-port-tables.py  - the port's tables and height map through
                                    that model, vs the original

Neither runs a single 68030 instruction, which is exactly what src/render.s's
status note said was missing. This builds the port with MARCHER_ORACLE=1 -
which pins flt_x/flt_y/flt_angle/altitude to the captured frame - runs it
under Hatari, dumps ring_silhouette, and scores it the way the other two
score: page rows, over the 112 columns the main view owns (0001B84E's rear
view overwrites the middle 80 of every ring), skipping uniform rings.

    python3 tools/certify-marcher.py work/qemu_out/marcher-cockpit.json

The build and the emulator run go to their own directory, never release/, so
a capture cannot swap the program under another probe that is already running.
"""
import argparse
import collections
import json
import os
import pathlib
import statistics
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

# 0001B84E writes the rear view's 80 entries over the middle of every ring's
# archived row, so those columns are not the main marcher's output.
REAR_VIEW_FIRST, REAR_VIEW_LAST = 56, 135
VALID_COLUMNS = [c for c in range(192)
                 if not REAR_VIEW_FIRST <= c <= REAR_VIEW_LAST]
TERRAIN_COLS = 192


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, cwd=str(ROOT), text=True,
                          capture_output=True, **kw)


def build(outdir: pathlib.Path) -> None:
    env = dict(os.environ, MARCHER_ORACLE="1", OUTDIR=str(outdir))
    r = subprocess.run(["bash", "tools/build-run.sh", "--no-run"], cwd=str(ROOT),
                       text=True, capture_output=True, env=env)
    if r.returncode != 0:
        sys.exit(f"build failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    print(f"built {outdir}/comanche_d.tos with MARCHER_ORACLE=1")


def run_hatari(outdir: pathlib.Path, vbl: int, dumps: list) -> None:
    """dumps: (filename, symbol, byte count)."""
    tos = os.environ.get("TOS", str(ROOT / "tools" / "toolchain" / "tos402.rom"))
    hatari = os.environ.get("HATARI") or "hatari"
    probe = ["symbols comanche_d.tos"]
    for name, symbol, size in dumps:
        probe.append(f"savebin {name} {symbol} ${size:x}")
    probe.append("quit")
    (outdir / "probe.ini").write_text("\n".join(probe) + "\n")
    # Arm after TOS startup, then capture the completed main terrain at its
    # object-pass boundary. A VBL alone can hit an opening screen or a march.
    (outdir / "dbg.ini").write_text(
        "b VBL = 600 :once :file arm.ini\n")
    (outdir / "arm.ini").write_text(
        "symbols comanche_d.tos\n"
        "b pc = object_draw_pass && (attract_screen).w = 0 && "
        "(object_target_view).w = 0 :once :file probe.ini\n")
    for name, _, _ in dumps:
        (outdir / name).unlink(missing_ok=True)
    timeout = 120 + vbl // 40
    cmd = (f'cd "{outdir}" && timeout -k 10 {timeout} "{hatari}" '
           f'--memsize 14 --tos "{tos}" --patch-tos true '
           '--frameskips 0 --monitor rgb --machine falcon --dsp off '
           '--fast-boot true --sound off --fast-forward true --cpu-exact true '
           '--compatible true --confirm-quit off --disable-video on '
           f'--run-vbls {max(vbl + 200, 8000)} --parse dbg.ini --log-file hatari.log '
           '--alert-level fatal comanche_d.tos </dev/null '
           '>hatari-stdout.txt 2>&1')
    # The same two Windows traps tools/certify-replay-flight.py documents: the
    # command is POSIX - `&&`, `timeout -k`, `</dev/null` - and shell=True
    # hands it to cmd.exe, and the checked-in hatari.exe is an MSYS2/UCRT64
    # build that exits 0 writing no log when its runtime DLLs are missing.
    env = dict(os.environ)
    if os.name == "nt":
        ucrt = r"C:\msys64\ucrt64\bin"
        if os.path.isdir(ucrt) and ucrt.lower() not in env.get("PATH", "").lower():
            env["PATH"] = ucrt + os.pathsep + env.get("PATH", "")
        subprocess.run(["bash", "-c", cmd], env=env)
    else:
        subprocess.run(cmd, shell=True, env=env)
    stdout_path = outdir / "hatari-stdout.txt"
    if not stdout_path.exists():
        sys.exit(f"Hatari produced no output at {stdout_path}; "
                 "check HATARI and TOS point at real files")
    log = stdout_path.read_text(errors="replace")
    if "Loaded" not in log or "symbols" not in log:
        print(log[-1500:], file=sys.stderr)
        sys.exit("Hatari did not load the program's symbols")


def generated_table(label: str, directive: str) -> list:
    """Pull one dc.l/dc.b table out of build/original_test.s by label."""
    text = (ROOT / "build" / "original_test.s").read_text()
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip() == label)
    out = []
    for l in lines[i + 1:]:
        s = l.strip()
        if s.startswith(directive):
            out += [int(v) for v in s[len(directive):].split(",")]
        elif s and not s.startswith(";") and not s.startswith("even"):
            break
    return out


def check_runtime_tables(outdir: pathlib.Path, rings: int) -> None:
    steps = outdir / "steps.bin"
    if steps.exists():
        got = int.from_bytes(steps.read_bytes(), "big")
        print(f"ring_steps: {got} "
              f"({'matches' if got == rings else 'DIFFERS from'} the "
              f"capture's {rings})")
    for name, label, directive, width in (
            ("pages.bin", "ring_page_table", "dc.b", 1),
            ("atab.bin", "ring_a_table", "dc.l", 4),
            ("btab.bin", "ring_b_table", "dc.l", 4)):
        got = outdir / name
        if not got.exists():
            continue
        want = generated_table(label, directive)
        raw = got.read_bytes()
        n = len(raw) // width
        mine = [int.from_bytes(raw[i * width:(i + 1) * width], "big",
                               signed=(width == 4)) for i in range(n)]
        ref = [v if width == 1 else (v if v < 2**31 else v - 2**32)
               for v in want[:n]]
        bad = [i for i in range(min(n, len(ref))) if mine[i] != ref[i]]
        print(f"{label}: {n - len(bad)}/{n} entries match the generated table"
              + ("" if not bad else
                 f"  first bad index {bad[0]}: runtime {mine[bad[0]]} "
                 f"generated {ref[bad[0]]}"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--vbl", type=int, default=5200,
                    help="VBL budget (at least 8000); capture stops at the "
                         "first completed main-view terrain pass")
    ap.add_argument("--outdir", default="build/oracle-run")
    ap.add_argument("--min-distinct", type=int, default=4)
    ap.add_argument("--all-columns", action="store_true")
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    outdir = (ROOT / args.outdir).resolve()
    dump = json.loads(pathlib.Path(args.dump).read_text())
    st = dump["state"]
    rings = st["ring_count_0x19EE0"]
    out = os.path.dirname(os.path.abspath(args.dump))
    if "silhouettes_file" not in dump:
        sys.exit(f"{args.dump}: no silhouettes; re-capture with --silhouette")
    ref_all = open(os.path.join(out, dump["silhouettes_file"]), "rb").read()

    if not args.no_build:
        r = subprocess.run([sys.executable, "tools/gen-marcher-oracle.py",
                            args.dump], cwd=str(ROOT), text=True,
                           capture_output=True)
        if r.returncode != 0:
            sys.exit(r.stderr or r.stdout)
        print(r.stdout.strip())
        build(outdir)

    # One byte of page row per column, as the original archives it.
    sil_bytes = TERRAIN_COLS * rings
    run_hatari(outdir, args.vbl, [
        ("sil.bin", "ring_silhouette", sil_bytes),
        ("hmap.bin", "original_height_map", 1 << 16),
        ("dy.bin", "backdrop_dy", TERRAIN_COLS * 2),
        ("pages.bin", "ring_page_table", rings * 256),
        ("atab.bin", "ring_a_table", rings * 4),
        ("btab.bin", "ring_b_table", rings * 4),
        ("steps.bin", "ring_steps", 2),
    ])

    # The oracle build forces src/dtl.s to load the .DTL at runtime, so these
    # four are what the loader and 00015AD9's page builder produced. They must
    # equal what tools/prepare-original-test.py generated from the same file:
    # a byte-order slip or a wrong table offset shows up here as a table
    # difference rather than as a subtly wrong landscape.
    check_runtime_tables(outdir, rings)
    got = outdir / "sil.bin"
    if not got.exists() or got.stat().st_size != sil_bytes:
        sys.exit(f"{got}: expected {sil_bytes} bytes, got "
                 f"{got.stat().st_size if got.exists() else 'nothing'}")
    mine_raw = got.read_bytes()

    # The map the port had loaded has to be the one the capture marched, or
    # the diff measures the wrong terrain.
    hm = (outdir / "hmap.bin")
    if hm.exists() and "heightmap_file" in dump:
        ref_hm = open(os.path.join(out, dump["heightmap_file"]), "rb").read()
        n = min(hm.stat().st_size, len(ref_hm))
        same = hm.read_bytes()[:n] == ref_hm[:n]
        print(f"height map: first {n} bytes "
              f"{'identical to' if same else 'DIFFER from'} the original's")
        if not same:
            sys.exit("the port marched a different terrain family than the "
                     "capture; pick a --vbl inside the same mission")

    # The backdrop's per-column horizon, against the original's own 192-byte
    # array at 0x3CB40. DOS stores byte(pitch - shake - dh); the port keeps
    # the same quantity 16-bit signed, so the comparison is mod 256.
    dy = outdir / "dy.bin"
    ref_dy = dump.get("horizon_0x3CB40")
    if dy.exists() and ref_dy and len(ref_dy) == TERRAIN_COLS:
        mine_dy = [int.from_bytes(dy.read_bytes()[c * 2:c * 2 + 2], "big",
                                  signed=True) & 0xFF
                   for c in range(TERRAIN_COLS)]
        bad = [c for c in range(TERRAIN_COLS) if mine_dy[c] != ref_dy[c]]
        print(f"backdrop_dy: {TERRAIN_COLS - len(bad)}/{TERRAIN_COLS} columns "
              f"exact against 0x3CB40")
        if bad:
            print("  first mismatches: " + ", ".join(
                f"col {c} port {mine_dy[c]} orig {ref_dy[c]}" for c in bad[:5]))

    scored, skipped, exact_total, cells = [], 0, 0, 0
    for i in range(rings):
        ref = list(ref_all[i * 256 + 0x20:i * 256 + 0x20 + TERRAIN_COLS])
        if len(ref) < TERRAIN_COLS:
            break
        base = i * TERRAIN_COLS
        mine = list(mine_raw[base:base + TERRAIN_COLS])
        if len(collections.Counter(ref)) < args.min_distinct:
            skipped += 1
            continue
        cols = range(TERRAIN_COLS) if args.all_columns else VALID_COLUMNS
        err = [mine[c] - ref[c] for c in cols]
        ex = sum(1 for e in err if e == 0)
        exact_total += ex
        cells += len(err)
        scored.append((i, ex, statistics.mean(err), max(abs(e) for e in err)))

    width = TERRAIN_COLS if args.all_columns else len(VALID_COLUMNS)
    print(f"\n{skipped} rings skipped as uniform, {len(scored)} scored\n")
    for i, ex, mean, worst in (scored[:3] + scored[len(scored) // 2:][:2]
                               + scored[-2:]):
        print(f"  ring {i:3d}: exact {ex:3d}/{width}  mean {mean:+7.2f}  "
              f"max|e| {worst}")
    if not cells:
        sys.exit("nothing scored")
    print(f"\noverall: {exact_total}/{cells} columns exact "
          f"({exact_total / cells:.1%})")
    return 0 if exact_total == cells else 1


if __name__ == "__main__":
    raise SystemExit(main())
