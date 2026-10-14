#!/usr/bin/env python3
r"""The original's first mission with the pilot doing nothing, sampled.

Enters the mission the way work/trace_mission_live.py does (the same sendkey
schedule: Esc, then Return up to Accept), waits for the flight loop
(00006A05 with [0x19ED4] clear), and then stops at the object pass's end
(000234CE) every --every passes for --frames passes, reading the player's
hull, altitude and position and the thirty placed objects' active flag,
position and altitude. Nothing is written into the game: no key is pressed
after Accept, so the helicopter stays on its pad. --hover instead writes the
collective notch [0x19D85] = 0x20 once the flight loop runs - the store the
keypad-* command makes at 0001998C - so it lifts off and hovers there.

It answers one question about the port: what the mission's own units do to a
pilot who never moves - whether they come, when they fire, and what it costs.

    python3 work/trace_mission_idle.py --frames 1500 --every 10 --out work/replay_dos/mission-idle.json

N/A - target artefact: an oracle probe, no DOS routine.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import Qmp, default_hdd, QEMU
from rsp import Rsp
from dump_marcher_tables import linear, wait_for_program
from trace_replay_flight import OBJECT_UPDATE_DONE, read_block, write_block
from trace_mission_live import FLIGHT_LOOP, KEYS

# Addresses read off 000192F3-00019345 (the object collision walk, ebx = slot)
# and the flight state it compares them with.
ACTIVE = 0x21921      # byte [ebx + 0x21921]
ALT = 0x21A25         # byte [ebx + 0x21A25]
OBJ_X = 0x20C6C       # dword [ebx*4 + 0x20C6C]
OBJ_Y = 0x20E74       # dword [ebx*4 + 0x20E74]
HULL = 0x19E40        # dword, [0x19E44] its maximum
PLAYER_X = 0x19CD4
PLAYER_Y = 0x19CD8
PLAYER_ALT = 0x19DFC


def sample(gdb):
    hull = read_block(gdb, linear(HULL), 8)
    pos = read_block(gdb, linear(PLAYER_X), 8)
    alt = read_block(gdb, linear(PLAYER_ALT), 1)
    act = read_block(gdb, linear(ACTIVE), 31)
    oalt = read_block(gdb, linear(ALT), 31)
    ox = read_block(gdb, linear(OBJ_X), 4 * 31)
    oy = read_block(gdb, linear(OBJ_Y), 4 * 31)
    if None in (hull, pos, alt, act, oalt, ox, oy):
        return None
    objs = []
    for slot in range(1, 31):
        objs.append({
            "slot": slot, "active": act[slot], "alt": oalt[slot],
            "x": struct.unpack_from("<I", ox, 4 * slot)[0],
            "y": struct.unpack_from("<I", oy, 4 * slot)[0],
        })
    return {
        "hull": struct.unpack_from("<i", hull, 0)[0],
        "hull_max": struct.unpack_from("<i", hull, 4)[0],
        "x": struct.unpack_from("<I", pos, 0)[0],
        "y": struct.unpack_from("<I", pos, 4)[0],
        "alt": alt[0],
        "objects": objs,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--frames", type=int, default=1500)
    ap.add_argument("--every", type=int, default=10)
    ap.add_argument("--wait", type=float, default=300.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hover", action="store_true")
    args = ap.parse_args()
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = int(os.environ.get("QMP_PORT", 4687))
    gport = int(os.environ.get("GDB_PORT", 4688))
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,snapshot=on",
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
           "-gdb", f"tcp:127.0.0.1:{gport}"]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    rows = []
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, proc, args.wait):
            return 1
        lock = threading.Lock()

        def keys():
            for when, key in KEYS:
                delay = t0 + when - time.time()
                if delay > 0:
                    time.sleep(delay)
                with lock:
                    qmp.hmp(f"sendkey {key}")
        threading.Thread(target=keys, daemon=True).start()

        gdb = Rsp(gport, timeout=args.wait)
        flight = linear(FLIGHT_LOOP)
        gdb.set_break(flight)
        first = True
        while True:
            stop = gdb.cont_until_stop() if first else gdb.cont_from_break(flight)
            first = False
            if stop is None:
                print("  the flight loop never started")
                return 1
            if read_block(gdb, linear(0x19ED4), 1) == b"\x00":
                break
        gdb.clear_break(flight)
        print(f"  [{time.time() - t0:5.1f}s] mission flight loop entered")
        if args.hover:
            write_block(gdb, linear(0x19D85), b"\x20")     # 0001998C
        at = linear(OBJECT_UPDATE_DONE)
        gdb.set_break(at)
        first = True
        for frame in range(1, args.frames + 1):
            stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
            first = False
            if stop is None:
                print(f"  update pass stopped being reached at frame {frame}")
                break
            if frame % args.every == 0:
                row = sample(gdb)
                if row is None:
                    print("  read failed")
                    break
                row["frame"] = frame
                rows.append(row)
                if row["hull"] != (rows[-2]["hull"] if len(rows) > 1 else row["hull_max"]):
                    print(f"  frame {frame}: hull {row['hull']}")
        gdb.close()
    finally:
        proc.kill()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"frames": args.frames, "every": args.every, "hover": args.hover,
                   "rows": rows}, f)
    print(f"  wrote {len(rows)} samples -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
