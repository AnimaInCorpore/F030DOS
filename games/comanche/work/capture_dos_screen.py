#!/usr/bin/env python3
r"""The original's own screenshot of a menu screen, reached with sendkey.

Drives the shipped game with a timed key schedule (the `work/run_qemu.py --key`
convention, SEC:KEY), waits until --at seconds, then stops at the next entry to
the key gate 000189C2 and does what capture_dos_frame.py does for a flight
frame: Alt+P down, the KYLE feature byte non-0xFF, let 000165FD write
SNAP_001.PCX to a scratch copy of the disk, release, read it back with mtools.
The 328-wide page is saved as it is; the display window's pan is whatever
the screen's CRTC start made it, so compare against a Falcon frame by
searching the pan, not by assuming it.

    python3 work/capture_dos_screen.py --key 20:esc --at 30 --out build/frame-pair/dos-menu-main

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
from trace_replay_flight import read_block, write_block
from capture_dos_frame import (copy_snap, SNAP_RELEASE_WAIT, KEY_ALT, KEY_P,
                               FEATURE)

KEY_GATE = 0x000189C2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--key", action="append", default=[], metavar="SEC:KEY")
    ap.add_argument("--at", type=float, required=True,
                    help="seconds after launch at which to take the picture")
    ap.add_argument("--wait", type=float, default=240.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    scratch = os.path.join(out, "oracle-scratch.hdd")
    shutil.copyfile(args.hdd, scratch)
    shutil.copyfile(args.hdd + ".geom.json", scratch + ".geom.json")
    with open(scratch + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = int(os.environ.get("QMP_PORT", 4697))
    gport = int(os.environ.get("GDB_PORT", 4698))
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", f"file={scratch},format=raw,if=none,id=hd0,cache=writethrough",
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
           "-gdb", f"tcp:127.0.0.1:{gport}"]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    meta = {}
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, proc, args.wait):
            return 1
        lock = threading.Lock()

        def keys():
            for item in args.key:
                when, key = item.split(":", 1)
                delay = t0 + float(when) - time.time()
                if delay > 0:
                    time.sleep(delay)
                with lock:
                    qmp.hmp(f"sendkey {key}")
                print(f"  [{time.time() - t0:5.1f}s] sendkey {key}")
        threading.Thread(target=keys, daemon=True).start()
        delay = t0 + args.at - time.time()
        if delay > 0:
            time.sleep(delay)
        gdb = Rsp(gport, timeout=args.wait)
        # The program is running; ask for the next entry to the gate.
        gdb.set_break(linear(KEY_GATE))
        if gdb.cont_until_stop() is None:
            print("  the key gate never ran")
            return 1
        gdb.clear_break(linear(KEY_GATE))
        saved = {a: read_block(gdb, linear(a), 1)[0] for a in (KEY_ALT, KEY_P, FEATURE)}
        write_block(gdb, linear(KEY_ALT), b"\x38")
        write_block(gdb, linear(KEY_P), b"\x19")
        if saved[FEATURE] == 0xFF:
            write_block(gdb, linear(FEATURE), b"\x00")
        gdb.set_break(linear(SNAP_RELEASE_WAIT))
        if gdb.cont_until_stop() is None:
            print("  the PCX writer never returned")
            return 1
        gdb.clear_break(linear(SNAP_RELEASE_WAIT))
        write_block(gdb, linear(KEY_P), b"\x99")
        write_block(gdb, linear(KEY_ALT), b"\xb8")
        write_block(gdb, linear(FEATURE), bytes([saved[FEATURE]]))
        meta["page"] = int.from_bytes(read_block(gdb, linear(0x19CA8), 4), "little")
        meta["start"] = int.from_bytes(read_block(gdb, linear(0x19CAC), 4), "little")
        meta["extra"] = int.from_bytes(read_block(gdb, linear(0x19DC4), 4), "little")
        gdb.cmd("D")
        gdb.close()
        time.sleep(3)
        qmp.hmp("quit")
        proc.wait(timeout=20)
    finally:
        if proc.poll() is None:
            proc.kill()
    pcx = os.path.join(out, "SNAP_001.PCX")
    if not copy_snap(scratch, g["part_offset"], "SNAP_001.PCX", pcx):
        print("  SNAP_001.PCX not found")
        return 1
    os.remove(scratch)
    with open(os.path.join(out, "dos-screen.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print(f"  wrote {pcx}; page {meta['page']:#x} start {meta['start']:#x} extra {meta['extra']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
