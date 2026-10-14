#!/usr/bin/env python3
"""Run the port's OWN attract replay under Hatari and diff its flight state
against the original's, at the same record.

The demos replay recorded INPUTS, so a picture cannot settle whether the port
flies the authored path: a few 10.22 units of drift per tick are invisible for
a hundred frames and then the helicopter is over a different hill. Two things
have to hold, and only the second needs an emulator:

  * the arithmetic - work/trace_replay_flight.py captures the original's own
    [0x19CD4]/[0x19CD8]/[0x19D04]/[0x19DFC] per integration tick;
  * the running port - this dumps flt_x/flt_y/flt_angle/player_altitude and
    demo_cursor out of Hatari and looks the cursor up in that trace.

The cursor is the join. It is the record index the original and the port have
both consumed, so the comparison never has to assume the two are at the same
frame - it reads which record the port is on and asks the original what it
had after that one.

    python3 tools/certify-replay-flight.py work/replay_dos/flight-demo1.json \
        --vbl 3500 --vbl 4000 --vbl 4500

N/A - target artefact: a check harness, no DOS routine.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (symbol, bytes, signed). demo_cursor is the record index * 8 + 13, the same
# quantity the original keeps at [0x19ECC].
DUMPS = [
    ("x.bin", "flt_x", 4, True),
    ("y.bin", "flt_y", 4, True),
    ("angle.bin", "flt_angle", 4, False),
    ("alt.bin", "player_altitude", 1, False),
    ("cursor.bin", "demo_cursor", 4, False),
    ("length.bin", "demo_length", 4, False),
    ("active.bin", "demo_active", 2, False),
    ("pass.bin", "attract_demo_pass", 2, False),
    ("family.bin", "resource_family", 2, False),
    ("sky.bin", "mission_sky_number", 2, False),
    ("variant.bin", "view_variant", 1, False),
    ("vangle.bin", "view_angle", 4, False),
    ("vsin.bin", "view_sin", 4, True),
    ("vcos.bin", "view_cos", 4, True),
    ("vslope.bin", "view_slope", 4, True),
    ("voffset.bin", "view_offset", 4, True),
    ("vcamx.bin", "view_cam_x", 4, True),
    ("vcamy.bin", "view_cam_y", 4, True),
    ("nobj.bin", "mission_object_count", 2, False),
]

# The whole object table, so slot 31 - the fixed object variant 7 aims at -
# can be read without an address expression Hatari's savebin will not take.
OBJ_SIZE = 100
OBJ_COUNT = 130
OBJ_X, OBJ_Y, OBJ_ACTIVE = 20, 24, 37


def build(outdir: pathlib.Path) -> None:
    env = dict(os.environ, OUTDIR=str(outdir))
    r = subprocess.run(["bash", "tools/build-run.sh", "--no-run"],
                       cwd=str(ROOT), text=True, capture_output=True, env=env)
    if r.returncode != 0:
        sys.exit(f"build failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    print(f"built {outdir}/comanche_d.tos")


def run_hatari(outdir: pathlib.Path, vbl: int, at_render=False) -> dict:
    tos = os.environ.get("TOS", str(ROOT / "tools" / "toolchain" / "tos402.rom"))
    hatari = os.environ.get("HATARI") or "hatari"
    probe = ["symbols comanche_d.tos"]
    for name, symbol, size, _ in DUMPS:
        probe.append(f"savebin {name} {symbol} ${size:x}")
    probe.append(f"savebin objtab.bin object_table ${OBJ_SIZE*OBJ_COUNT:x}")
    probe.append("savebin objtype.bin mission_obj_type $82")
    probe.append("quit")
    (outdir / "probe.ini").write_text("\n".join(probe) + "\n")
    # Capture at an INSTRUCTION, not at a VBL. The DOS side of this
    # comparison stops at 00019555, the end of the flight integration; a
    # Falcon sample taken at an arbitrary VBL can land inside the render,
    # where an external view has moved flt_x/flt_y to the camera and the
    # frame driver has not popped them back yet. The numbers then look like a
    # drift and are a phase difference - the same trap the marcher's 16.1%
    # was. flight_publish runs immediately after flight_tick, which is the
    # port's own 00019555.
    (outdir / "arm.ini").write_text(
        "symbols comanche_d.tos\n"
        f"b pc = {'render_clear' if at_render else 'flight_publish'} "
        ":once :file probe.ini\n"
        "c\n")
    (outdir / "dbg.ini").write_text(f"b VBL = {vbl} :once :file arm.ini\n")
    for name, _, _, _ in DUMPS:
        (outdir / name).unlink(missing_ok=True)
    (outdir / "objtab.bin").unlink(missing_ok=True)
    timeout = 120 + vbl // 40
    cmd = (f'cd "{outdir}" && timeout -k 10 {timeout} "{hatari}" '
           f'--memsize 14 --tos "{tos}" --patch-tos true '
           '--frameskips 0 --monitor rgb --machine falcon --dsp off '
           '--fast-boot true --sound off --fast-forward true --cpu-exact true '
           '--compatible true --confirm-quit off --disable-video on '
           f'--run-vbls {vbl + 200} --parse dbg.ini --log-file hatari.log '
           '--alert-level fatal comanche_d.tos </dev/null '
           '>hatari-stdout.txt 2>&1')
    # The command is a POSIX one - `&&`, `timeout -k`, `</dev/null`. On
    # Windows shell=True hands it to cmd.exe, whose own `timeout` takes no -k
    # and which has no /dev/null, so the run dies before Hatari starts and
    # leaves no stdout file to read. Send it to bash explicitly there; the
    # checked-in toolchain and build-run.sh already assume one is present.
    env = dict(os.environ)
    if os.name == "nt":
        # The checked-in hatari.exe is an MSYS2/UCRT64 build and needs its
        # runtime DLLs on PATH. Without them it exits 0 having written no log
        # at all, which reads as a Hatari failure rather than a missing
        # dependency - tools/grab-frame.sh carries the same line for the same
        # reason.
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
    if "symbols" not in log:
        print(log[-1500:], file=sys.stderr)
        sys.exit("Hatari did not load the program's symbols")
    out = {}
    table = outdir / "objtab.bin"
    if table.exists() and table.stat().st_size == OBJ_SIZE * OBJ_COUNT:
        raw = table.read_bytes()
        base = 30 * OBJ_SIZE
        out["slot31_active"] = raw[base + OBJ_ACTIVE]
        out["slot31_x"] = int.from_bytes(raw[base + OBJ_X:base + OBJ_X + 4],
                                         "big", signed=True)
        out["slot31_y"] = int.from_bytes(raw[base + OBJ_Y:base + OBJ_Y + 4],
                                         "big", signed=True)
        out["active_slots"] = sum(1 for i in range(OBJ_COUNT)
                                  if raw[i * OBJ_SIZE + OBJ_ACTIVE])
    else:
        out["slot31_active"] = out["slot31_x"] = out["slot31_y"] = None
        out["active_slots"] = None
    for name, symbol, size, signed in DUMPS:
        path = outdir / name
        if not path.exists() or path.stat().st_size != size:
            out[symbol] = None
            continue
        out[symbol] = int.from_bytes(path.read_bytes(), "big", signed=signed)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("trace", help="work/trace_replay_flight.py output")
    ap.add_argument("--view", help="a --view-basis trace of the same replay; "
                                   "the view angle, its Q31 pair and the "
                                   "backdrop slope/offset are checked against "
                                   "it at the same record")
    ap.add_argument("--vbl", type=int, action="append", default=[])
    ap.add_argument("--outdir", default="build/replay-run")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--at-render", action="store_true",
                    help="stop at render_clear instead of flight_publish, so "
                         "flt_x/flt_y/player_altitude are the CAMERA the frame "
                         "marches from rather than the helicopter the frame "
                         "driver pops back. This is the only way to check the "
                         "two external handlers' moved viewpoint.")
    args = ap.parse_args()

    trace = json.loads(pathlib.Path(args.trace).read_text())
    print(f"original: {trace.get('demo_stream')} "
          f"{' '.join(n.strip() for n in trace['resources'][:4] if n)}")
    # cursor -> the state the original had after consuming that record
    by_cursor, prev = {}, 0
    for row in trace["rows"]:
        cursor = row["cursor_0x19ECC"]
        if cursor <= prev:
            break
        prev = cursor
        by_cursor[cursor] = row

    view = {}
    if args.view:
        vt = json.loads(pathlib.Path(args.view).read_text())
        for row in vt["rows"]:
            view.setdefault(row["cursor_0x19ECC"], []).append(row)
        print(f"view trace: {len(vt['rows'])} frames of "
              f"{vt.get('demo_stream')}")

    outdir = (ROOT / args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    if not args.no_build:
        build(outdir)

    bad = 0
    for vbl in sorted(args.vbl) or [3500]:
        got = run_hatari(outdir, vbl, args.at_render)
        cursor = got["demo_cursor"]
        print(f"\nVBL {vbl}: pass={got['attract_demo_pass']} "
              f"family={got['resource_family']} sky={got['mission_sky_number']} "
              f"demo_active={got['demo_active']} "
              f"cursor={cursor} of {got['demo_length']}")
        print(f"  variant={got['view_variant']} "
              f"cam=({got['view_cam_x']},{got['view_cam_y']}) "
              f"active slots={got['active_slots']} "
              f"slot31 active={got['slot31_active']} "
              f"({got['slot31_x']},{got['slot31_y']})")
        types = outdir / "objtype.bin"
        if types.exists():
            raw = types.read_bytes()[:got["mission_object_count"] or 0]
            import collections
            print(f"  mission records={got['mission_object_count']} "
                  f"types={dict(collections.Counter(raw))}")
        if not got["demo_active"]:
            print("  not in the replay flight at this VBL")
            continue
        if args.at_render:
            rows = view.get(cursor)
            if not rows:
                print(f"  the view trace has no frame at cursor {cursor}")
                bad += 1
                continue
            record = (cursor - 13) // 8
            fields = (("variant", got["view_variant"], "variant_0x19D86"),
                      ("camera x", got["flt_x"], "x_0x19CD4"),
                      ("camera y", got["flt_y"], "y_0x19CD8"),
                      ("camera alt", got["player_altitude"], "alt_0x19DFC"),
                      ("view angle", got["view_angle"], "view_angle_0x19D00"),
                      ("slope", got["view_slope"], "slope_0x19CF8"),
                      ("offset", got["view_offset"], "offset_0x19CFC"))
            hit = next((r for r in rows
                        if all(m == r[k] for _, m, k in fields)), None)
            if hit is not None:
                print(f"  record {record} variant {got['view_variant']}: "
                      "the marched camera matches on all seven fields")
                continue
            bad += 1
            best = rows[0]
            for label, mine, key in fields:
                print(f"  record {record} {label:11s} port={mine:<12} "
                      f"dos={best[key]:<12} "
                      f"{'match' if mine == best[key] else 'DIFFERS'}")
            continue

        want = by_cursor.get(cursor)
        if want is None:
            print(f"  the trace has no record at cursor {cursor} - "
                  "capture more records, or the port is on another pass")
            bad += 1
            continue
        record = (cursor - 13) // 8
        for label, mine, theirs in (
                ("x", got["flt_x"], want["x_0x19CD4"]),
                ("y", got["flt_y"], want["y_0x19CD8"]),
                ("angle", got["flt_angle"], want["angle_0x19D04"]),
                ("altitude", got["player_altitude"], want["alt_0x19DFC"])):
            same = mine == theirs
            bad += 0 if same else 1
            print(f"  record {record} {label:9s} port={mine:<12} "
                  f"dos={theirs:<12} {'match' if same else 'DIFFERS'}")

        # The view basis, and it is a record BEHIND the flight state. Both
        # machines build the basis at the top of the frame and consume the
        # record at the bottom, so the basis this sample sees was built with
        # the previous cursor. Looking it up under `cursor` compares two
        # different frames and reports a correct port as wrong.
        #
        # Several rendered frames can share a cursor - the view keys re-run
        # the frame twice - so any row at that record counts.
        rows = view.get(cursor - 8)
        if rows is None:
            if view:
                print(f"  the view trace has no frame at cursor {cursor - 8}")
            continue
        fields = (("variant", got["view_variant"], "variant_0x19D86"),
                  ("view angle", got["view_angle"], "view_angle_0x19D00"),
                  ("view sin", got["view_sin"], "view_sin_0x19CB0"),
                  ("view cos", got["view_cos"], "view_cos_0x19CB4"),
                  ("slope", got["view_slope"], "slope_0x19CF8"),
                  ("offset", got["view_offset"], "offset_0x19CFC"))
        hit = next((r for r in rows
                    if all(mine == r[key] for _, mine, key in fields)), None)
        if hit is not None:
            print(f"  record {record} view basis  variant "
                  f"{got['view_variant']}: all six fields match")
            continue
        bad += 1
        best = rows[0]
        for label, mine, key in fields:
            print(f"  record {record} {label:11s} port={mine:<12} "
                  f"dos={best[key]:<12} "
                  f"{'match' if mine == best[key] else 'DIFFERS'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
