#!/usr/bin/env python3
"""Stop the no-sound oracle at its startup stall, dump RAM and registers, and
walk the call chain from the stack (return addresses preceded by `call rel32`).

    python3 work/build_dos_hdd.py --use-no-sound --run-game --hold --no-boot
    python3 work/probe_stall_stack.py --seconds 12

Object 1 is resident at physical 0x17D000 (file 0x582A4); see work/le_map.py.
"""

from __future__ import annotations

import argparse
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import run_qemu  # noqa: E402

OBJ1_RAM, OBJ1_FILE = 0x17D000, 0x582A4
RAM_SIZE = 0x1000000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--output", type=Path,
                    default=ROOT / "work" / "qemu_out" / "pg_stall.bin")
    args = ap.parse_args()

    cyls, heads, secs, _ = run_qemu.geometry(run_qemu.HDD)
    port = run_qemu.free_port()
    drive = (f"file={str(run_qemu.HDD).replace(chr(92), '/')},format=raw,"
             "if=none,id=hd0,cache=writeback")
    cmd = [run_qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16", "-drive",
           drive, "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={cyls},"
           f"heads={heads},secs={secs}", "-boot", "c", "-display", "none",
           "-vga", "std", "-no-reboot", "-qmp",
           f"tcp:127.0.0.1:{port},server=on,wait=off"]
    out = args.output.resolve()
    run_qemu.stale(str(out))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    qmp = run_qemu.Qmp(port)
    try:
        time.sleep(args.seconds)
        qmp.hmp("stop")
        regs = qmp.hmp("info registers")
        qmp.hmp(f'pmemsave 0x0 0x{RAM_SIZE:X} "{str(out).replace(chr(92), "/")}"')
        deadline = time.monotonic() + 5
        while not out.exists() or out.stat().st_size != RAM_SIZE:
            if time.monotonic() > deadline:
                raise RuntimeError("RAM dump missing")
            time.sleep(0.05)
    finally:
        qmp.hmp("quit")
        qmp.close()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
    print(regs)
    ram = out.read_bytes()

    def reg(name):
        m = re.search(rf"\b{name}\s*=\s*([0-9a-fA-F]+)", regs)
        return int(m.group(1), 16) if m else None

    def seg_base(name):
        m = re.search(rf"^{name}\s*=\w+\s+([0-9a-fA-F]+)", regs, re.M)
        return int(m.group(1), 16) if m else 0

    esp, eip = reg("ESP"), reg("EIP")
    ss_base, cs_base = seg_base("SS"), seg_base("CS")
    print(f"EIP={eip:X} (CS base {cs_base:X}) ESP={esp:X} (SS base {ss_base:X})")
    lo, hi = OBJ1_RAM, OBJ1_RAM + 0x63000
    sp = ss_base + esp
    print("stack frames that return into object 1 after a call rel32:")
    for i in range(0, 0x400, 4):
        v = struct.unpack_from("<I", ram, sp + i)[0]
        lin = v + cs_base if cs_base and v < 0x1000000 and not lo <= v < hi else v
        if lo <= lin < hi and ram[lin - 5] == 0xE8:
            rel = struct.unpack_from("<i", ram, lin - 4)[0]
            target = (lin + rel) & 0xFFFFFFFF
            print(f"  [esp+{i:03X}] ret {lin:X} (file {lin - OBJ1_RAM + OBJ1_FILE:X}, "
                  f"obj1+{lin - OBJ1_RAM:X}) called {target:X} "
                  f"(file {target - OBJ1_RAM + OBJ1_FILE:X})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
