#!/usr/bin/env python3
"""Run the shipped DOS original with QEMU's built-in TCG execution trace.

This is the Windows fallback for F030Method/dos/trace/x86trace: it uses
QEMU's supported ``-d exec,nochain`` diagnostic extension rather than a
compiled plugin.  The guest is still the unmodified COMANCHE.EXE image; only
the host-side execution log is enabled.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

QEMU = dosimg.host_tool("qemu-system-i386")
ROOT = dosimg.find_project_root(__file__)


def default_hdd():
    hits = sorted(
        p for p in (
            os.path.join(ROOT, "img", n)
            for n in os.listdir(os.path.join(ROOT, "img"))
            if n.lower().endswith(".hdd")
        )
        if os.path.exists(p + ".geom.json")
    )
    return hits[0] if hits else os.path.join(ROOT, "img", "dos.hdd")


def geometry(hdd):
    with open(hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    return g["cyls"], g["heads"], g["secs"]


class Qmp:
    def __init__(self, port):
        self.sock = None
        for _ in range(80):
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=2)
                break
            except OSError:
                time.sleep(0.25)
        if self.sock is None:
            raise RuntimeError("QMP never came up")
        self.file = self.sock.makefile("rw")
        self.file.readline()
        self.command({"execute": "qmp_capabilities"})

    def command(self, obj):
        try:
            self.file.write(json.dumps(obj) + "\n")
            self.file.flush()
            while True:
                line = self.file.readline()
                if not line:
                    return None
                value = json.loads(line)
                if "event" in value:
                    continue
                return value
        except (OSError, ValueError):
            return None

    def hmp(self, command):
        result = self.command({
            "execute": "human-monitor-command",
            "arguments": {"command-line": command},
        })
        return (result or {}).get("return", "")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdd", default=default_hdd())
    parser.add_argument("--seconds", type=float, default=45)
    parser.add_argument("--log", required=True)
    parser.add_argument("--key", action="append", default=[], metavar="SEC:KEY")
    parser.add_argument("--shot", action="append", type=float, default=[])
    args = parser.parse_args()

    cyls, heads, secs = geometry(args.hdd)
    port = 4607
    log = os.path.abspath(args.log)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    command = [
        QEMU,
        "-M", "pc", "-cpu", "486", "-m", "16",
        "-drive", f"file={args.hdd.replace(chr(92), '/')},format=raw,if=none,id=hd0,cache=writeback",
        "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={cyls},heads={heads},secs={secs}",
        "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
        "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
        "-d", "exec,nochain", "-D", log,
    ]
    print("$", " ".join(command))
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    qmp = Qmp(port)
    start = time.time()
    events = [(float(k.split(":", 1)[0]), "key", k.split(":", 1)[1])
              for k in args.key]
    events += [(t, "shot", None) for t in args.shot]
    events.sort()
    for when, kind, value in events:
        wait = when - (time.time() - start)
        if wait > 0:
            time.sleep(wait)
        if process.poll() is not None:
            break
        if kind == "key":
            print(f"  key {value} @ {time.time() - start:.1f}s")
            qmp.hmp(f"sendkey {value}")
        else:
            shot = os.path.join(os.path.dirname(log), f"exec_shot_{int(when)}.ppm")
            print(f"  shot @ {time.time() - start:.1f}s -> {shot}")
            qmp.hmp(f'screendump "{shot.replace(chr(92), "/")}"')
            print(qmp.hmp("info registers").strip())
    remaining = args.seconds - (time.time() - start)
    if remaining > 0 and process.poll() is None:
        time.sleep(remaining)
    if process.poll() is None:
        qmp.hmp("quit")
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
    qmp.close()
    print("trace bytes:", os.path.getsize(log) if os.path.exists(log) else "missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
