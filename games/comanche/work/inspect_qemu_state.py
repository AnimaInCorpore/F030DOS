#!/usr/bin/env python3
"""Inspect selected flat DOS state while the original runs in QEMU."""
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
    img = os.path.join(ROOT, "img")
    hits = sorted(os.path.join(img, n) for n in os.listdir(img)
                  if n.lower().endswith(".hdd")
                  and os.path.exists(os.path.join(img, n + ".geom.json")))
    return hits[0]


class Qmp:
    def __init__(self, port):
        for _ in range(80):
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=2)
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError("QMP never came up")
        self.file = self.sock.makefile("rw")
        self.file.readline()
        self.command({"execute": "qmp_capabilities"})

    def command(self, value):
        self.file.write(json.dumps(value) + "\n")
        self.file.flush()
        while True:
            line = self.file.readline()
            if not line:
                return None
            result = json.loads(line)
            if "event" not in result:
                return result

    def hmp(self, line):
        result = self.command({"execute": "human-monitor-command",
                               "arguments": {"command-line": line}})
        return (result or {}).get("return", "")

    def close(self):
        self.sock.close()


def xp_bytes(qmp, address, count):
    text = qmp.hmp(f"xp /{count}xb {address:#x}")
    values = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        for token in line.split(":", 1)[1].split():
            if token.startswith("0x"):
                try:
                    values.append(int(token, 16))
                except ValueError:
                    pass
    return bytes(values[:count])


def u32_table(qmp, address, count):
    raw = xp_bytes(qmp, address, count * 4)
    return [int.from_bytes(raw[i * 4:i * 4 + 4], "little")
            for i in range(count)]


def print_objects(qmp):
    active = xp_bytes(qmp, 0x6040 + 0x21921, 0x84)
    functions = u32_table(qmp, 0x6040 + 0x20244, 0x83)
    draw_functions = u32_table(qmp, 0x6040 + 0x2003c, 0x83)
    models = u32_table(qmp, 0x6040 + 0x21fb0, 0x83)
    x_pos = u32_table(qmp, 0x6040 + 0x20C6C, 0x83)
    y_pos = u32_table(qmp, 0x6040 + 0x20E74, 0x83)
    depth = u32_table(qmp, 0x6040 + 0x20A64, 0x83)
    kind = xp_bytes(qmp, 0x6040 + 0x2189F, 0x84)
    frame = xp_bytes(qmp, 0x6040 + 0x21A25, 0x84)
    print("active object slots:")
    for index in range(1, 0x83):
        if index < len(active) and active[index]:
            print(f"  slot={index:02x} active={active[index]:02x} "
                  f"fn=0x{functions[index]:05x} "
                  f"draw=0x{draw_functions[index]:05x} "
                  f"model=0x{models[index]:05x} "
                  f"x=0x{x_pos[index]:08x} y=0x{y_pos[index]:08x} "
                  f"depth=0x{depth[index]:08x} "
                  f"kind={kind[index]:02x} frame={frame[index]:02x}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdd", default=default_hdd())
    parser.add_argument("--seconds", type=float, default=45)
    parser.add_argument("--at", action="append", type=float, default=[])
    parser.add_argument("--xp", action="append", default=[],
                        metavar="ADDR:COUNT",
                        help="physical/flat linear address and byte count")
    parser.add_argument("--shot", action="store_true")
    parser.add_argument("--objects", action="store_true")
    args = parser.parse_args()
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = 4611
    command = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", f"file={args.hdd.replace(chr(92), '/')},format=raw,if=none,id=hd0,cache=writeback",
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},heads={g['heads']},secs={g['secs']}",
               "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
               "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
               "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off"]
    print("$", " ".join(command))
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    qmp = Qmp(port)
    start = time.time()
    for when in sorted(args.at):
        wait = when - (time.time() - start)
        if wait > 0:
            time.sleep(wait)
        if process.poll() is not None:
            break
        print(f"\n--- inspect at {time.time() - start:.1f}s ---")
        print(qmp.hmp("info registers").strip())
        if args.objects:
            print_objects(qmp)
        for spec in args.xp:
            addr, _, count = spec.partition(":")
            print(f"xp {addr} {count or 16}")
            print(qmp.hmp(f"xp /{int(count or 16)}xb {int(addr, 0):#x}").strip())
        if args.shot:
            shot = os.path.join(ROOT, "work", "qemu_out", f"inspect_{int(when)}.ppm")
            qmp.hmp(f'screendump "{shot.replace(chr(92), "/")}"')
            print("screenshot:", shot)
    remaining = args.seconds - (time.time() - start)
    if remaining > 0 and process.poll() is None:
        time.sleep(remaining)
    if process.poll() is None:
        qmp.hmp("quit")
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
    qmp.close()


if __name__ == "__main__":
    main()
