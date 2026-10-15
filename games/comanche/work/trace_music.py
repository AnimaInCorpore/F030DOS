#!/usr/bin/env python3
r"""The original's music as it reaches the AdLib: every OPL register write.

Boots the shipped game under QEMU with an ISA AdLib (YM3812 at 0x388, the
`adlib` device) so the MS3 driver's presence test (0002C1F7) passes for the
installed COMANCHE.CFG music device, and stops at three instructions:

  0002C1B8  the OPL register write: ah = register, al = value
  0002BD00  a song starts: ebx = the song, al = its flags
  0002B9CF  a driver command: ax

each stamped with the count of 65 Hz timer interrupts so far: a breakpoint at
00001D32, the instruction after the ISR's driver call, counts them ([00019DDC]
is reset every frame and cannot stamp a stream). A Sound Blaster 16 is fitted
too, so the digital effects take COMANCHE.CFG's digital device and the FM
driver carries music only, as on the Falcon. --keys sends the menu schedule of
work/trace_mission_live.py; without it the run stays in the opening and the
attract, which play OPENMUS.MS3 and the demo missions' MUS*.RLE. --wav also
records the AdLib's own output.

    python3 work/trace_music.py --seconds 120 --out work/replay_dos/music-attract.json

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
from trace_replay_flight import read_block, read_regs
from trace_mission_live import KEYS

OPL_WRITE = 0x0002C1B8
SONG_START = 0x0002BD00
COMMAND = 0x0002B9CF
TIMER_TICK = 0x00001D32             # 00001D20's ISR, right after it calls the driver


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--seconds", type=float, default=120.0, help="wall-clock length of the capture")
    ap.add_argument("--keys", action="store_true", help="drive the menus into a mission")
    ap.add_argument("--wav", help="also record the AdLib's output here")
    ap.add_argument("--wait", type=float, default=300.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = int(os.environ.get("QMP_PORT", 4687))
    gport = int(os.environ.get("GDB_PORT", 4688))
    audio = (["-audiodev", f"wav,id=snd0,path={os.path.abspath(args.wav)}"] if args.wav
             else ["-audiodev", "none,id=snd0"])
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,snapshot=on",
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           *audio, "-device", "adlib,audiodev=snd0", "-device", "sb16,audiodev=snd0",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
           "-gdb", f"tcp:127.0.0.1:{gport}"]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    events = []
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, proc, args.wait):
            return 1
        lock = threading.Lock()
        if args.keys:
            def keys():
                for when, key in KEYS:
                    delay = t0 + when - time.time()
                    if delay > 0:
                        time.sleep(delay)
                    with lock:
                        qmp.hmp(f"sendkey {key}")
            threading.Thread(target=keys, daemon=True).start()
        gdb = Rsp(gport, timeout=args.wait)
        points = {linear(OPL_WRITE): "opl", linear(SONG_START): "song", linear(COMMAND): "cmd",
                  linear(TIMER_TICK): "tick"}
        tick = 0
        for p in points:
            gdb.set_break(p)
        last = None
        t_end = time.time() + args.seconds
        while time.time() < t_end:
            stop = gdb.cont_until_stop() if last is None else gdb.cont_from_break(last)
            if stop is None:
                break
            r = read_regs(gdb)
            here = linear(r["eip"])
            last = here
            kind = points.get(here)
            if kind == "tick":
                tick += 1
            elif kind == "opl":
                events.append(["opl", tick, (r["eax"] >> 8) & 0xFF, r["eax"] & 0xFF])
            elif kind == "song":
                events.append(["song", tick, r["ebx"], r["eax"] & 0xFF])
            elif kind == "cmd":
                events.append(["cmd", tick, r["eax"] & 0xFFFF])
        gdb.close()
    finally:
        proc.kill()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"events": events}, f)
    n = sum(1 for e in events if e[0] == "opl")
    print(f"  {n} OPL writes, {sum(1 for e in events if e[0] == 'song')} song starts -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
