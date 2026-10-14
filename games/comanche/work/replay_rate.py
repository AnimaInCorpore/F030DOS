#!/usr/bin/env python3
"""How fast does the guest consume DEMO<n>.SCR records?

00018CBC reads the replay cursor from [0x19ECC] and 00018D15 writes it back
eight bytes on, one record per frame, so the cursor's rate is the replay's
frame rate.

    python work/replay_rate.py --seconds 30

**Measured 2026-08-28: 324 records in 2.0 seconds - 162 records/second.**
That is the answer to "how fast does QEMU run this", not "how fast did the
original run". QEMU's TCG has no 486 timing model, and the replay is paced by
rendering, so the guest consumes a 775-record demo in under five seconds
where a real 486 took the best part of a minute. **Do not use the DOS oracle
for wall-clock questions** - it settles what the program computes, never how
long it took. The port's own pace, one record per ~33 VBLs, has to be judged
against the hardware or against a timing capture, not against this.

N/A - target artefact: an oracle measurement, no DOS routine.
"""
import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg
from inspect_qemu_state import Qmp, default_hdd, xp_bytes, QEMU, ROOT

FLAT = 0x6040
CURSOR = 0x19ECC
REPLAY_MODE = 0x19ED0


def u32(qmp, addr):
    raw = xp_bytes(qmp, FLAT + addr, 4)
    return int.from_bytes(raw, "little") if raw else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--wait", type=float, default=120.0)
    args = ap.parse_args()

    import json
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = 4615
    command = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,"
                         "cache=writeback",
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                          f"heads={g['heads']},secs={g['secs']}",
               "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
               "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off"]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    try:
        qmp = Qmp(port)
        deadline = time.time() + args.wait
        while time.time() < deadline and u32(qmp, REPLAY_MODE) != 1:
            time.sleep(0.5)
        if u32(qmp, REPLAY_MODE) != 1:
            print("no replay started")
            return 1
        time.sleep(1.0)
        t0 = time.time()
        c0 = u32(qmp, CURSOR)
        print(f"replay running, cursor {c0} (record {c0 // 8})")
        samples = []
        while time.time() - t0 < args.seconds:
            time.sleep(2.0)
            if u32(qmp, REPLAY_MODE) != 1:
                print("  replay ended")
                break
            t = time.time() - t0
            c = u32(qmp, CURSOR)
            samples.append((t, c))
            print(f"  {t:5.1f}s cursor {c} (record {c // 8})")
        if len(samples) >= 2:
            dt = samples[-1][0]
            dr = (samples[-1][1] - c0) / 8.0
            print(f"\n{dr:.0f} records in {dt:.1f}s = "
                  f"{dr / dt:.2f} records/second")
            print(f"one record per {70.0 / (dr / dt) * 1000 / 70:.1f} ms "
                  f"({(dr / dt):.2f} fps)")
        qmp.hmp("quit")
    finally:
        if proc.poll() is None:
            proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
