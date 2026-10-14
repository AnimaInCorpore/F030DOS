#!/usr/bin/env python3
"""Trace calls into the 13 VESA480.DLL exports in the no-sound oracle.

Breakpoints at base+offset (base 0x218AED, analysis/display-driver.md); each hit
records registers, the return address and 8 stack dwords, then steps over.  Only
the first --per-export hits of each export are kept.  Output: work/re/driver_trace.json

    python3 work/build_dos_hdd.py --use-no-sound --run-game --hold --mouse-stub --no-boot
    python3 work/probe_driver_trace.py --seconds 40
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import run_qemu  # noqa: E402
from probe_tail_write import Rsp, rsp_registers  # noqa: E402

BASE = 0x218AED
OFFS = [0x10DC, 0x3E7B, 0x4044, 0x113C, 0x10EB, 0x1111, 0x1263, 0x37B7, 0x3D4A, 0x3D81, 0x3DB6, 0x24E0, 0x3DE0]

ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=float, default=40.0)
ap.add_argument("--per-export", type=int, default=30)
ap.add_argument("--out", type=Path, default=ROOT / "work" / "re" / "driver_trace.json")
a = ap.parse_args()
cyls, heads, secs, _ = run_qemu.geometry(run_qemu.HDD)
gp = run_qemu.free_port()
drive = (f"file={str(run_qemu.HDD).replace(chr(92), '/')},format=raw,if=none,id=hd0,cache=writeback")
cmd = [run_qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16", "-drive", drive, "-device",
       f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={cyls},heads={heads},secs={secs}", "-boot", "c",
       "-display", "none", "-vga", "std", "-no-reboot", "-gdb", f"tcp:127.0.0.1:{gp}", "-S"]
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(1.0)
rsp = Rsp(gp)
at = {BASE + o: i for i, o in enumerate(OFFS)}
for ad in at:
    rsp.command(f"Z0,{ad:X},1")


def mem(addr, n):
    r = rsp.command(f"m{addr:X},{n:X}")
    return bytes.fromhex(r) if r and not r.startswith("E") else b""


rsp.sock.sendall(b"$c#63")
t0 = time.monotonic()
log, count = [], {i: 0 for i in range(13)}
try:
    while time.monotonic() - t0 < a.seconds:
        rsp.sock.settimeout(max(0.5, a.seconds - (time.monotonic() - t0)))
        try:
            rsp._packet()
        except Exception:
            break
        regs = rsp_registers(rsp.command("g"))
        eip = regs["EIP"]
        i = at.get(eip)
        if i is not None:
            count[i] += 1
            if count[i] <= a.per_export:
                st = mem(regs["ESP"], 36)
                dw = [int.from_bytes(st[k:k + 4], "little") for k in range(0, len(st) - 3, 4)]
                structs = {}
                if i in (6, 7, 11) and len(dw) > 1:
                    # arg1 is a pointer to a 5-dword rect record whose first dword
                    # points to a 5-dword bitmap descriptor (analysis/display-driver.md)
                    rec = mem(dw[1], 20)
                    if len(rec) == 20:
                        structs["rect"] = rec.hex()
                        desc = mem(int.from_bytes(rec[:4], "little"), 20)
                        structs["desc"] = desc.hex()
                log.append({"t": round(time.monotonic() - t0, 2), "export": i, "n": count[i], **structs,
                            "eax": regs["EAX"], "ebx": regs["EBX"], "ecx": regs["ECX"],
                            "edx": regs["EDX"], "esi": regs["ESI"], "edi": regs["EDI"],
                            "ebp": regs["EBP"], "stack": dw})
            if count[i] == a.per_export:
                rsp.command(f"z0,{eip:X},1")
        if i is None or count[i] < a.per_export or True:
            if i is not None and count[i] < a.per_export:
                rsp.command(f"z0,{eip:X},1"); rsp.command("s"); rsp.command(f"Z0,{eip:X},1")
            elif i is not None:
                rsp.command("s")
        rsp.sock.sendall(b"$c#63")
finally:
    proc.kill()
a.out.parent.mkdir(parents=True, exist_ok=True)
a.out.write_text(json.dumps({"base": BASE, "counts": count, "hits": log}, indent=0), encoding="utf-8")
print("hits per export:", count)
