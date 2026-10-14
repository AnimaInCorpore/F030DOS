#!/usr/bin/env python3
"""Run the no-sound oracle with execution breakpoints at runtime (RAM) addresses
and log each hit with registers.  Object 1 is at RAM 0x17D000 (work/le_map.py).

    python3 work/probe_break_trace.py --seconds 14 0x1B7AEF 0x1B7C59 0x1B7C65
"""
from __future__ import annotations
import argparse, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import run_qemu  # noqa: E402
from probe_tail_write import Rsp, rsp_registers  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("addresses", nargs="+", type=lambda v: int(v, 0))
ap.add_argument("--seconds", type=float, default=14.0)
a = ap.parse_args()
cyls, heads, secs, _ = run_qemu.geometry(run_qemu.HDD)
gp = run_qemu.free_port()
drive = (f"file={str(run_qemu.HDD).replace(chr(92), '/')},format=raw,"
         "if=none,id=hd0,cache=writeback")
cmd = [run_qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16", "-drive", drive,
       "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={cyls},heads={heads},secs={secs}",
       "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
       "-gdb", f"tcp:127.0.0.1:{gp}", "-S"]
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(1.0)
rsp = Rsp(gp)
rsp.command("QStartNoAckMode") if False else None
for ad in a.addresses:
    print("Z0", hex(ad), rsp.command(f"Z0,{ad:X},1"), flush=True)
rsp.sock.settimeout(a.seconds + 5)
rsp.sock.sendall(b"$c#63")
t0 = time.monotonic()
hits = []
try:
    while time.monotonic() - t0 < a.seconds:
        rsp.sock.settimeout(max(0.5, a.seconds - (time.monotonic() - t0)))
        try:
            stop = rsp._packet()
        except Exception as e:
            print("end:", type(e).__name__); break
        regs = rsp_registers(rsp.command("g"))
        print(f"[{time.monotonic()-t0:6.2f}s] stop {stop[:3]} EIP={regs.get('EIP',0):X} "
              f"EAX={regs.get('EAX',0):X} EBX={regs.get('EBX',0):X} ESP={regs.get('ESP',0):X}", flush=True)
        # step over the breakpoint: remove, single-step, reinsert
        eip = regs["EIP"]
        rsp.command(f"z0,{eip:X},1"); rsp.command("s")
        rsp.command(f"Z0,{eip:X},1")
        rsp.sock.sendall(b"$c#63")
finally:
    proc.kill()
