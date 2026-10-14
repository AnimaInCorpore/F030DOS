#!/usr/bin/env python3
"""Attach at the startup stall, then watch the runtime timer word.

The timer word is reached through a relocated absolute address and the
surrounding protected-mode allocations are not fixed before startup.  This
probe therefore discovers the current code/file delta and timer address after
the no-sound image has reached its steady state, instead of installing a
pre-boot watchpoint at an address that may temporarily hold a loader buffer.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import socket
import struct
import subprocess
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "game" / "EXE" / "PANZER.EXE"
sys.path.insert(0, str(ROOT / "work"))
import run_qemu  # noqa: E402
from probe_tail_write import (  # noqa: E402
    Rsp, parse_registers, parse_segment_dump, xp, rsp_registers,
)


def file_hits(exe: bytes, needle: bytes) -> list[int]:
    hits = []
    start = 0
    while needle:
        hit = exe.find(needle, start)
        if hit < 0:
            break
        hits.append(hit)
        start = hit + 1
    return hits


def locate_timer_wait(qmp, exe: bytes) -> tuple[int, int]:
    """Locate the unique unrelocated prefix of file 0x8F032's wait routine.

    A timed pause can land in the extender IRQ gate, whose relocated bytes
    cannot calibrate the game. Search a stopped RAM snapshot instead, then
    validate the wait's relocated CMP operand and branch at their exact sites.
    This is a runtime-placement witness, not a general file-to-RAM mapping.
    """
    file_entry, compare_offset = 0x8F032, 0x8F068
    prefix = exe[file_entry:0x8F056]
    with tempfile.TemporaryDirectory(prefix="pg-timer-") as directory:
        snapshot = Path(directory) / "ram.bin"
        reply = qmp.hmp(f'pmemsave 0x100000 0xF00000 "{snapshot.as_posix()}"')
        if not snapshot.is_file():
            raise RuntimeError(f"RAM capture failed: {reply}")
        ram = snapshot.read_bytes()
    if len(ram) != 0xF00000:
        raise RuntimeError(f"short RAM snapshot: {len(ram)} bytes")
    candidates = []
    for hit in file_hits(ram, prefix):
        compare = hit + compare_offset - file_entry
        if ram[compare:compare + 2] == b"\x3b\x05" and ram[compare + 6:compare + 8] == b"\x77\xee":
            candidates.append((0x100000 + hit,
                               int.from_bytes(ram[compare + 2:compare + 6], "little")))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one validated timer-wait instance, found {candidates}")
    entry, timer = candidates[0]
    return entry - file_entry, timer


def idt_entry(qmp, base: int, vector: int) -> tuple[int, int, int, bytes]:
    raw = xp(qmp, base + vector * 8, 8)
    if len(raw) != 8:
        return 0, 0, 0, raw
    offset = int.from_bytes(raw[0:2], "little") | (
        int.from_bytes(raw[6:8], "little") << 16)
    selector = int.from_bytes(raw[2:4], "little")
    return offset, selector, raw[5], raw


def descriptor_base(qmp, gdt_base: int, selector: int) -> int:
    raw = xp(qmp, gdt_base + (selector & ~7), 8)
    if len(raw) != 8:
        return 0
    return (int.from_bytes(raw[2:4], "little")
            | (raw[4] << 16) | (raw[7] << 24))


def timer_slots(qmp, timer: int) -> None:
    """Read the tables consumed by the witnessed file 0xAD497 IRQ handler."""
    data_base = timer - 0x21BA
    print(f"timer dispatcher tables (data base 0x{data_base:X}):")
    for index in range(17):
        fields = []
        for name, offset, width in [("state", 0x7610, 2), ("callback", 0x75CC, 4),
                                    ("elapsed", 0x7632, 4), ("period", 0x7676, 4)]:
            raw = xp(qmp, data_base + offset + index * width, width)
            if len(raw) != width:
                raise RuntimeError(f"short timer table read: {name}[{index}]")
            fields.append(f"{name}=0x{int.from_bytes(raw, 'little'):X}")
        print(f"  {index:02d}: " + ", ".join(fields))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdd", type=Path, default=Path(run_qemu.HDD))
    parser.add_argument("--seconds", type=float, default=8.0,
                        help="run before pausing at the startup state")
    parser.add_argument("--watch-seconds", type=float, default=8.0,
                        help="wait for a timer-word write")
    parser.add_argument("--break-callback", action="store_true",
                        help="also break on the candidate increment routine")
    parser.add_argument("--break-idt", action="store_true",
                        help="break on the current protected-mode IRQ0 gate")
    parser.add_argument("--break-common", action="store_true",
                        help="break on the IRQ0 gate's relative-call target")
    parser.add_argument("--step-count", type=int, default=0,
                        help="single-step this many instructions after a stop")
    args = parser.parse_args()

    exe = EXE.read_bytes()
    if hashlib.sha256(exe).hexdigest() != '115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86':
        raise RuntimeError("timer probe requires the recorded unpatched PANZER.EXE build")
    hdd = str(args.hdd.resolve())
    cyls, heads, secs, _part_offset = run_qemu.geometry(hdd)
    qmp_port = run_qemu.free_port()
    rsp_port = run_qemu.free_port()
    drive = (f"file={str(hdd).replace(chr(92), '/')},format=raw,"
             "if=none,id=hd0,cache=writeback")
    command = [run_qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", drive,
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,"
                          f"cyls={cyls},heads={heads},secs={secs}",
               "-boot", "c", "-display", "none", "-vga", "std",
               "-no-reboot", "-gdb", f"tcp:127.0.0.1:{rsp_port}",
               "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,wait=off"]
    print("$", " ".join(command), flush=True)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    qmp = run_qemu.Qmp(qmp_port)
    rsp = None
    try:
        for _ in range(120):
            try:
                rsp = Rsp(rsp_port)
                break
            except OSError:
                time.sleep(0.25)
        if rsp is None:
            raise RuntimeError("GDB RSP never came up")
        print("rsp:", rsp.command("qSupported:multiprocess+;xmlRegisters=i386"),
              flush=True)
        print("initial:", rsp.command("?"), flush=True)
        # Some QEMU builds leave the guest stopped when the RSP client first
        # connects, even without -S.  QMP continue is harmless if it was
        # already running and makes the attach timing deterministic.
        qmp.hmp("cont")
        time.sleep(args.seconds)
        qmp.hmp("stop")
        print("paused:", rsp.command("?"), flush=True)

        raw = qmp.hmp("info registers")
        print("--- startup registers ---")
        print(raw.strip())
        regs = parse_registers(raw)
        segments = parse_segment_dump(raw)
        cs_base = segments.get("CS", (0, 0, 0, 0))[1]
        linear = cs_base + regs.get("EIP", 0)
        current = xp(qmp, linear, 32)
        hits = file_hits(exe, current[:10])
        print(f"current linear EIP: 0x{linear:X}; bytes: {current.hex(' ')}")
        print("current file matches:", [f"0x{x:X}" for x in hits])
        delta, timer = locate_timer_wait(qmp, exe)
        print(f"timer-wait entry: 0x{0x8F032 + delta:X} (file 0x8F032)")

        idt_base_match = re.search(r"\bIDT=\s+([0-9A-Fa-f]+)", raw)
        common = None
        if idt_base_match:
            idt_base = int(idt_base_match.group(1), 16)
            gdt_base_match = re.search(r"\bGDT=\s+([0-9A-Fa-f]+)", raw)
            gdt_base = (int(gdt_base_match.group(1), 16)
                        if gdt_base_match else 0)
            for vector in (0x08, 0x1C):
                offset, selector, attrs, gate = idt_entry(qmp, idt_base, vector)
                print(f"IDT vector 0x{vector:02X}: offset 0x{offset:X}, "
                      f"selector 0x{selector:04X}, attrs 0x{attrs:02X}; "
                      f"{gate.hex(' ')}")
                if vector == 0x08 and gdt_base:
                    handler = descriptor_base(qmp, gdt_base, selector) + offset
                    handler_bytes = xp(qmp, handler, 32)
                    print(f"IRQ0 handler linear: 0x{handler:X}; "
                          f"bytes: {handler_bytes.hex(' ')}; "
                          f"file matches: {[f'0x{x:X}' for x in file_hits(exe, handler_bytes[:10])]}")
                    call_pos = handler_bytes.find(b"\xE8")
                    if call_pos >= 0 and call_pos + 3 <= len(handler_bytes):
                        displacement = struct.unpack_from("<h", handler_bytes,
                                                          call_pos + 1)[0]
                        common_eip = offset + call_pos + 3 + displacement
                        common = descriptor_base(qmp, gdt_base, selector) + common_eip
                        print(f"IRQ0 handler relative-call target: "
                              f"0x{common:X}")

        timer_file = 0x8F06A
        callback = 0x9207B + delta
        callback_code = xp(qmp, callback, 17)
        if (callback_code[:11] != exe[0x9207B:0x92086]
                or callback_code[11:13] != b"\xff\x05"
                or int.from_bytes(callback_code[13:17], "little") != timer):
            raise RuntimeError("candidate callback does not increment the located timer")
        print(f"delta: 0x{delta:X}; timer word: 0x{timer:X} "
              f"(file operand 0x{timer_file:X}); "
              f"candidate increment: 0x{callback:X}")
        print(f"timer before watch: {xp(qmp, timer, 4).hex(' ')}")
        timer_slots(qmp, timer)
        if args.break_callback:
            print("callback breakpoint:",
                  rsp.command(f"Z0,{callback:X},1"), flush=True)
        if args.break_idt and idt_base_match:
            offset, selector, _attrs, _gate = idt_entry(qmp, idt_base, 0x08)
            handler = descriptor_base(qmp, gdt_base, selector) + offset
            print("IRQ0 breakpoint:", rsp.command(f"Z0,{handler:X},1"),
                  flush=True)
        if args.break_common and common is not None:
            print("IRQ0 common breakpoint:",
                  rsp.command(f"Z0,{common:X},1"), flush=True)
        print("watch:", rsp.command(f"Z2,{timer:X},4"), flush=True)
        rsp.sock.settimeout(max(1.0, args.watch_seconds))
        try:
            stop = rsp.command("c")
            print("timer stop:", stop, flush=True)
            if args.step_count:
                rsp.sock.settimeout(5)
                print("--- single-step trace ---")
                for step in range(args.step_count):
                    state = qmp.hmp("info registers")
                    step_regs = parse_registers(state)
                    step_segments = parse_segment_dump(state)
                    step_cs = step_segments.get("CS", (0, 0, 0, 0))
                    step_linear = step_cs[1] + step_regs.get("EIP", 0)
                    step_bytes = xp(qmp, step_linear, 8)
                    step_hits = file_hits(exe, step_bytes[:6])
                    print(f"{step:02d}: linear 0x{step_linear:X}, "
                          f"CS:EIP 0x{step_regs.get('CS', 0):04X}:"
                          f"0x{step_regs.get('EIP', 0):X}, "
                          f"bytes {step_bytes.hex(' ')}, "
                          f"file {[f'0x{x:X}' for x in step_hits]}")
                    step_stop = rsp.command("s")
                    if step_stop.startswith("T") and step_stop != "T05core:01;":
                        print("step stop:", step_stop)
                        if "watch:" in step_stop:
                            break
            after = qmp.hmp("info registers")
            print(after.strip())
            print("timer after:", xp(qmp, timer, 4).hex(' '))
            print("RSP registers:", rsp_registers(rsp.command("g")))
            return 0
        except socket.timeout:
            print(f"no timer-word write within {args.watch_seconds:g}s")
            qmp.hmp("stop")
            after = qmp.hmp("info registers")
            print("after timeout:", after.strip())
            print("timer after:", xp(qmp, timer, 4).hex(' '))
            return 1
    finally:
        try:
            qmp.hmp("quit")
        except Exception:
            pass
        if rsp is not None:
            rsp.close()
        qmp.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
