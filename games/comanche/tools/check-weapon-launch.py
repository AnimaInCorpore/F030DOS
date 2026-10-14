#!/usr/bin/env python3
"""Check the port's weapon launches against the original's, shot by shot.

The DOS side is work/trace_weapon_fire.py: one row per call into the weapon
handler table at 0001922E, with the claimed slot's fields straight after the
handler returns. This runs the port's own attract under Hatari, stops at
weapon_dispatch and weapon_dispatch_done,
and dumps the object table immediately before and after every dispatch that
has a trigger pending (the port's 0001922E). Each breakpoint arms the next,
so one run covers every shot. Rows are joined by the replay cursor, and the
slot the port claimed is found by diffing the two tables.

What is compared, per shot: the slot the launcher claimed, its position (the
port keeps 16.16, so DOS 10.22 >> 6), heading, altitude, speed, target byte,
timer, aux byte, the rocket's 8.24 altitude and vertical rate, the
ammunition counts and the rail parity after the launch.

    python3 tools/check-weapon-launch.py work/replay_dos/weapon-demo1.json

N/A - target artefact: a check harness, no DOS routine.
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OBJ_SIZE, OBJ_COUNT = 100, 130
F = {"speed": (0, 4, False), "x": (20, 4, True), "y": (24, 4, True),
     "heading": (36, 1, False), "active": (37, 1, False),
     "alt": (38, 1, False), "timer": (40, 1, False), "aux": (53, 1, False),
     "vrate": (76, 4, True), "alt_acc": (80, 4, False),
     "target": (84, 1, False), "model_a": (12, 4, False)}
GLOBALS = [("cursor", "demo_cursor", 4), ("rail", "weapon_rail", 4),
           ("ammo", "weapon_ammo", 24), ("page", "instrument_page", 1),
           ("latch", "object_target_latch", 2)]


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def build(out):
    r = subprocess.run(["bash", "tools/build-run.sh", "--no-run"], cwd=ROOT,
                       text=True, capture_output=True,
                       env=dict(os.environ, OUTDIR=str(out)))
    if r.returncode:
        sys.exit(f"build failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--out", default="build/weapon-check")
    ap.add_argument("--run-vbls", type=int, default=14000)
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()
    dos = json.loads(pathlib.Path(args.trace).read_text())["rows"]
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.no_build:
        build(out)
    shots = len(dos)
    # One breakpoint at a time, each armed from a DIFFERENT pc than it stops
    # at: arming at the pc just hit re-triggers without the program moving.
    # before_k: weapon_dispatch's entry with a trigger pending on pages 1-5,
    # which is exactly when DOS reaches 0001922E; after_k: its exit in the
    # same call. The two tables name the slot the launch claimed.
    entry = ("b pc = weapon_dispatch && (flt_trig1).b ! 0 && "
             "(instrument_page).b ! 0 :once :file")
    # Started through the GEMDOS drive so symbols load the moment the program's
    # text is resident (Hatari 2.6 refuses `symbols` before that; see
    # tools/capture-target-frame.py).
    (out / "boot.ini").write_text(
        "b GemdosOpcode = $4b && OsCallParam = 0 :trace :once :file program.ini\n")
    (out / "program.ini").write_text("b pc = TEXT :trace :once :file arm.ini\n")
    (out / "arm.ini").write_text(f"symbols comanche_d.tos\n{entry} before_0.ini\n")
    for k in range(shots):
        (out / f"before_{k}.ini").write_text(
            f"savebin shot_{k}_pre.bin object_table ${OBJ_SIZE * OBJ_COUNT:x}\n"
            f"b pc = weapon_dispatch_done :once :file after_{k}.ini\nc\n")
        lines = [f"savebin shot_{k}_tab.bin object_table ${OBJ_SIZE * OBJ_COUNT:x}"]
        lines += [f"savebin shot_{k}_{n}.bin {sym} ${size:x}" for n, sym, size in GLOBALS]
        if k + 1 < shots:
            lines += [f"{entry} before_{k + 1}.ini", "c"]
        else:
            lines.append("quit")
        (out / f"after_{k}.ini").write_text("\n".join(lines) + "\n")
        for f in out.glob(f"shot_{k}_*.bin"):
            f.unlink()
    tos = os.environ.get("TOS", str(ROOT / "tools/toolchain/tos402.rom"))
    hatari = os.environ.get("HATARI") or "hatari"
    timeout = 120 + args.run_vbls // 18
    cmd = (f'cd "{out}" && timeout -k 10 {timeout} "{hatari}" --memsize 14 '
           f'--tos "{tos}" --patch-tos true --mmu true --frameskips 0 '
           '--monitor rgb --machine falcon --dsp off --fast-boot true '
           '--sound off --fast-forward true --cpu-exact true --compatible true '
           '--confirm-quit off --disable-video on '
           f'--run-vbls {args.run_vbls} --harddrive "{out}" --auto "C:\\comanche_d.tos" '
           '--parse boot.ini --log-file hatari.log '
           '--alert-level fatal </dev/null >hatari-stdout.txt 2>&1')
    subprocess.run(cmd, shell=True)

    by_cursor = {r["cursor_19ECC"]: r for r in dos}
    bad = checked = slot_differs = 0
    for k in range(shots):
        tab = out / f"shot_{k}_tab.bin"
        if not tab.is_file():
            print(f"shot {k}: not reached")
            bad += 1
            continue
        g = {n: (out / f"shot_{k}_{n}.bin").read_bytes() for n, _, _ in GLOBALS}
        cursor = int.from_bytes(g["cursor"], "big")
        row = by_cursor.get(cursor)
        if row is None:
            print(f"shot {k}: port fired at cursor {cursor}, DOS did not")
            bad += 1
            continue
        raw = tab.read_bytes()
        pre = (out / f"shot_{k}_pre.bin").read_bytes()
        dos_slot = max(row["new_slots"]) if row["new_slots"] else None
        claimed = [i + 1 for i in range(OBJ_COUNT)
                   if raw[i * OBJ_SIZE + 37] and not pre[i * OBJ_SIZE + 37]]
        slot = max(claimed) if claimed else None
        problems = []
        if (slot is None) != (dos_slot is None):
            problems.append(f"launch {slot} vs DOS {dos_slot}")
        ammo = [int.from_bytes(g["ammo"][i * 4:i * 4 + 4], "big") for i in range(6)]
        rail = s32(int.from_bytes(g["rail"], "big"))
        if ammo[1] != row["after"]["rock_19D30"]:
            problems.append(f"rockets {ammo[1]} vs {row['after']['rock_19D30']}")
        if ammo[2] != row["after"]["hell_19D34"]:
            problems.append(f"hellfires {ammo[2]} vs {row['after']['hell_19D34']}")
        if rail != s32(row["after"]["rail_22880"]):
            problems.append(f"rail {rail:#x} vs {s32(row['after']['rail_22880']):#x}")
        if slot is not None:
            base = (slot - 1) * OBJ_SIZE
            got = {n: int.from_bytes(raw[base + o:base + o + w], "big", signed=sg)
                   for n, (o, w, sg) in F.items()}
            d = row["slot"]
            want = {"x": s32(d["x_20C6C"]), "y": s32(d["y_20E74"]),
                    "heading": d["heading_2189F"], "alt": d["alt_21A25"],
                    "speed": d["speed_1FE34"], "aux": d["aux_21DB3"]}
            if row["handler"] == 0x22b00:
                want["vrate"] = s32(d["vrate_2148C"])
                want["alt_acc"] = d["alt824_21694"]
            else:
                want["timer"] = d["timer_21E35"]
                want["target"] = d["target_21D31"]
            if not got["active"]:
                problems.append(f"slot {slot} not active")
            if not got["model_a"]:
                problems.append(f"slot {slot} has no bank")
            for n, v in want.items():
                if got[n] != v:
                    problems.append(f"{n} {got[n]:#x} vs {v:#x}")
        checked += 1
        status = "PASS" if not problems else "DIFF"
        if slot != dos_slot and slot is not None and dos_slot is not None:
            slot_differs += 1
            status += f" (slot {slot}, DOS {dos_slot})"
        bad += bool(problems)
        print(f"shot {k}: cursor {cursor} handler {row['handler']:#x} slot {slot} "
              f"{status} {'; '.join(problems)}")
    print(f"\n{checked} shots compared, {bad} with field differences, "
          f"{slot_differs} in a different slot number")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
