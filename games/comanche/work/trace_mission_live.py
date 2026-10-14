#!/usr/bin/env python3
r"""A real mission's end on the original, captured at instructions.

Drives the shipped game from the attract through the menus into a mission with
`sendkey` (the schedule `work/run_qemu.py --key` used: Esc at 20 s, then Return
every six seconds up to Begin Mission, campaign, mission and Accept), waits for
the flight loop to start (`mov [0x19D91], 1` at 00006A05), lets it run for
--frames object-update passes, then holds Alt+A: 000189F2 jumps to 0002873D.
It stops at

  00028777  after the statistics 00028261            (stage "stats")
  00028A1F  the debrief screen's first instruction   (stage "debrief")
  00005AE3  the main menu, after Esc ends the debrief (stage "menu")

and dumps the statistics, the pilot roster block and the two inline file
names at each.

    python3 work/trace_mission_live.py --frames 300 --out work/replay_dos/mission-live-f300.json

N/A - target artefact: an oracle probe, no DOS routine.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import Qmp, default_hdd, QEMU
from rsp import Rsp
from dump_marcher_tables import linear, wait_for_program
from trace_replay_flight import OBJECT_UPDATE_DONE, read_block, write_block
from capture_dos_frame import (copy_snap, SNAP_RELEASE_WAIT, KEY_ALT as SNAP_ALT,
                               KEY_P, FEATURE, SNAP_NAME)

FLIGHT_LOOP = 0x00006A05            # mov byte [0x19D91], 1
MISSION_END = 0x0002873D
AFTER_STATS = 0x00028777
DEBRIEF = 0x00028A1F
SHOWN = 0x00028A98                  # the Esc wait loop: the screen is up
MENU = 0x00005AE3
KEY_ALT = 0x1AA8
KEY_A = 0x1A8E
KEYS = [(20, "esc"), (30, "ret"), (36, "ret"), (42, "ret"), (48, "ret"), (54, "ret")]
REGIONS = {
    "counters_28250": (0x28250, 0x20),
    "screen_285FA": (0x285FA, 0x100),
    "roster_29570": (0x29570, 0xA90),
    "globals_19D2C": (0x19D2C, 0x40),
    "hull_19E40": (0x19E40, 0x10),
    "flags_19D88": (0x19D88, 0x10),
    "ed4_19ED4": (0x19ED4, 0x04),
    "flag_22384": (0x22384, 0x04),
    "name_lose_288C3": (0x288C3, 0x10),
    "name_theme_288D5": (0x288D5, 0x10),
    "name_lose_289FA": (0x289FA, 0x10),
    "name_theme_28A0C": (0x28A0C, 0x10),
    "state_27DAA": (0x27DAA, 0x08),
    "loads_19D44": (0x19D44, 0x18),
    "fuel_19D5C": (0x19D5C, 0x08),
    "frame_19DDC": (0x19DDC, 0x04),
}


def dump(gdb):
    out = {}
    for name, (addr, size) in REGIONS.items():
        raw = read_block(gdb, linear(addr), size)
        out[name] = raw.hex() if raw else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--frames", type=int, default=300,
                    help="object-update passes of flight before Alt+A; 0 lets "
                         "the flight end by itself")
    ap.add_argument("--wait", type=float, default=300.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-debrief", action="store_true",
                    help="stop after the statistics")
    ap.add_argument("--win", action="store_true",
                    help="clear the thirty object slots' active flags with the Alt+A "
                         "poke, so every goal is destroyed and the hull is intact")
    ap.add_argument("--pcx", action="store_true",
                    help="have the game write its own SNAP_001.PCX of the debrief "
                         "(Alt+P, 000165FD) on a scratch copy of the disk")
    args = ap.parse_args()
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = int(os.environ.get("QMP_PORT", 4687))
    gport = int(os.environ.get("GDB_PORT", 4688))
    drive = f"file={args.hdd},format=raw,if=none,id=hd0,snapshot=on"
    scratch = None
    if args.pcx:
        scratch = os.path.abspath(args.out.rsplit(".", 1)[0] + "-scratch.hdd")
        shutil.copyfile(args.hdd, scratch)
        drive = f"file={scratch},format=raw,if=none,id=hd0,cache=writethrough"
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", drive,
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
           "-gdb", f"tcp:127.0.0.1:{gport}"]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    stages = {}
    lock = threading.Lock()
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, proc, args.wait):
            return 1

        def keys():
            for when, key in KEYS:
                delay = t0 + when - time.time()
                if delay > 0:
                    time.sleep(delay)
                with lock:
                    qmp.hmp(f"sendkey {key}")
                print(f"  [{time.time() - t0:5.1f}s] sendkey {key}")
        threading.Thread(target=keys, daemon=True).start()

        gdb = Rsp(gport, timeout=args.wait)
        flight = linear(FLIGHT_LOOP)
        gdb.set_break(flight)
        first = True
        while True:
            # The attract's demo flights enter the same loop with [0x19ED4] = 1;
            # a flown mission is the entry with it clear.
            stop = gdb.cont_until_stop() if first else gdb.cont_from_break(flight)
            first = False
            print(f"  [{time.time() - t0:5.1f}s] flight-loop stop {stop!r}")
            if stop is None:
                print("  the flight loop never started")
                return 1
            ed4 = read_block(gdb, linear(0x19ED4), 1)
            print(f"      [0x19ED4] = {ed4!r}")
            if ed4 == b"\x00":
                break
        gdb.clear_break(flight)
        print(f"  [{time.time() - t0:5.1f}s] mission flight loop entered")
        if args.frames:
            at = linear(OBJECT_UPDATE_DONE)
            gdb.set_break(at)
            first = True
            for _ in range(args.frames):
                stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
                first = False
                if stop is None:
                    print("  update pass stopped being reached")
                    return 1
            gdb.clear_break(at)
            stages["flight_frames"] = args.frames
            write_block(gdb, linear(KEY_ALT), b"\x00")
            write_block(gdb, linear(KEY_A), b"\x00")
            if args.win:
                write_block(gdb, linear(0x21922), b"\x00" * 30)   # active[1..30]
        else:
            stages["flight_frames"] = "until the flight ends by itself"
        gdb.set_break(linear(MISSION_END))
        if gdb.cont_until_stop() is None:
            print("  0002873D never reached")
            return 1
        gdb.clear_break(linear(MISSION_END))
        stages["enter"] = dump(gdb)
        print(f"  [{time.time() - t0:5.1f}s] stage enter captured")
        for name, addr in (("stats", AFTER_STATS), ("debrief", DEBRIEF)):
            if name == "debrief" and args.no_debrief:
                break
            gdb.set_break(linear(addr))
            if gdb.cont_until_stop() is None:
                print(f"  {addr:08X} never reached")
                break
            stages[name] = dump(gdb)
            print(f"  [{time.time() - t0:5.1f}s] stage {name} captured")
            gdb.clear_break(linear(addr))
            if name == "stats":
                # release the keys again so the debrief's own poll does not
                # see Alt+A held
                write_block(gdb, linear(KEY_ALT), b"\xff")
                write_block(gdb, linear(KEY_A), b"\xff")
        if "debrief" in stages:
            gdb.set_break(linear(SHOWN))
            if gdb.cont_until_stop() is not None:
                gdb.clear_break(linear(SHOWN))
                shot = os.path.abspath(args.out.rsplit(".", 1)[0] + "-debrief.ppm")
                with lock:
                    qmp.hmp(f"screendump {shot}")
                stages["debrief_screendump"] = shot
                stages["shown"] = dump(gdb)
                if args.pcx:
                    saved = {a: read_block(gdb, linear(a), 1)[0]
                             for a in (SNAP_ALT, KEY_P, FEATURE)}
                    write_block(gdb, linear(SNAP_ALT), b"\x38")
                    write_block(gdb, linear(KEY_P), b"\x19")
                    if saved[FEATURE] == 0xFF:
                        write_block(gdb, linear(FEATURE), b"\x00")
                    gdb.set_break(linear(SNAP_RELEASE_WAIT))
                    if gdb.cont_until_stop() is not None:
                        gdb.clear_break(linear(SNAP_RELEASE_WAIT))
                        write_block(gdb, linear(KEY_P), b"\x99")
                        write_block(gdb, linear(SNAP_ALT), b"\xb8")
                        write_block(gdb, linear(FEATURE), bytes([saved[FEATURE]]))
                        stages["snap_name"] = (read_block(gdb, linear(SNAP_NAME), 12) or b"").split(b"\0")[0].decode("latin-1")
                        stages["pcx_written"] = True
                    else:
                        print("  the PCX writer never returned")
                print(f"  [{time.time() - t0:5.1f}s] screendump {shot}")
            with lock:
                qmp.hmp("sendkey esc")
            gdb.set_break(linear(MENU))
            if gdb.cont_until_stop() is not None:
                stages["menu"] = dump(gdb)
                print(f"  [{time.time() - t0:5.1f}s] stage menu captured")
        gdb.close()
        if args.pcx and stages.get("pcx_written"):
            time.sleep(3)
            with lock:
                qmp.hmp("quit")
            proc.wait(timeout=20)
            with open(args.hdd + ".geom.json", encoding="utf-8") as f:
                part_off = json.load(f)["part_offset"]
            pcx = os.path.abspath(args.out.rsplit(".", 1)[0] + "-debrief.pcx")
            if copy_snap(scratch, part_off, "SNAP_001.PCX", pcx):
                stages["pcx"] = pcx
                print(f"  wrote {pcx}")
    finally:
        proc.kill()
        if scratch and os.path.exists(scratch):
            os.remove(scratch)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(stages, f, indent=1)
    print(f"  wrote {sorted(stages)} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
