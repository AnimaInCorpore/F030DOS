#!/usr/bin/env python3
"""Screendump the original at fixed times, for measuring the view window.

The marcher dump only shoots when a terrain run list exists, so it never
captures the attract's full-screen images. Those are what settle where the
displayed 320-pixel window sits on the 328-pixel Mode X page: the authored
images are 328 wide, so correlating a screendump against the decoded asset
says directly which source columns reach the screen.
"""
import argparse, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg
from inspect_qemu_state import Qmp, default_hdd

QEMU = dosimg.host_tool("qemu-system-i386")
ROOT = dosimg.find_project_root(__file__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--at", action="append", type=float, default=[])
    ap.add_argument("--outdir", default=os.path.join(ROOT, "work", "qemu_out"))
    args = ap.parse_args()
    times = sorted(args.at) or [20.0, 25.0, 30.0, 35.0, 40.0]
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = 4615
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,cache=writeback",
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    os.makedirs(args.outdir, exist_ok=True)
    try:
        qmp = Qmp(port)
        start = time.time()
        for when in times:
            w = when - (time.time() - start)
            if w > 0:
                time.sleep(w)
            if p.poll() is not None:
                break
            shot = os.path.join(args.outdir, f"attract-{int(when)}.ppm")
            qmp.hmp("stop")
            qmp.hmp(f'screendump "{shot}"')
            qmp.hmp("cont")
            print(f"  {when:5.1f}s -> {shot}")
        qmp.hmp("quit")
    finally:
        if p.poll() is None:
            p.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
