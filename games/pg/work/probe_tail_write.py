#!/usr/bin/env python3
"""Catch the first protected-mode write into the measured PANZER tail.

This is intentionally a one-shot witness.  The target addresses come from
``probe_memory.py``'s measured startup placement; the stopped CPU state then
identifies the segment bases, copy registers, and instruction immediately
following the first write.
"""

from __future__ import annotations

import argparse
import re
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "game" / "EXE" / "PANZER.EXE"
DEFAULT_TARGETS = (0x1B7599, 0x1B8599, 0x1B9599, 0x1BA599)
import sys
sys.path.insert(0, str(ROOT / "work"))
import run_qemu  # noqa: E402


class Rsp:
    def __init__(self, port: int):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=30)
        self.sock.settimeout(30)

    def _packet(self) -> str:
        while True:
            byte = self.sock.recv(1)
            if not byte:
                raise RuntimeError("GDB RSP connection closed")
            if byte == b"+":
                continue
            if byte != b"$":
                continue
            data = bytearray()
            while True:
                byte = self.sock.recv(1)
                if byte == b"#":
                    break
                data.extend(byte)
            checksum = self.sock.recv(2)
            want = f"{sum(data) & 0xFF:02x}".encode()
            if checksum.lower() != want:
                raise RuntimeError("bad RSP checksum")
            self.sock.sendall(b"+")
            return data.decode()

    def command(self, command: str) -> str:
        payload = command.encode()
        packet = b"$" + payload + b"#" + f"{sum(payload) & 0xFF:02x}".encode()
        self.sock.sendall(packet)
        return self._packet()

    def close(self) -> None:
        self.sock.close()


def parse_segment_dump(text: str) -> dict[str, tuple[int, int, int, int]]:
    answer = {}
    for name, selector, base, limit, flags in re.findall(
            r"\b(ES|CS|SS|DS|FS|GS)\s*=\s*([0-9A-Fa-f]+)\s+"
            r"([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]+)", text):
        answer[name] = tuple(int(v, 16) for v in
                             (selector, base, limit, flags))
    return answer


def parse_registers(raw: str) -> dict[str, int]:
    answer = {}
    for name, value in re.findall(r"\b(EAX|ECX|EDX|EBX|ESP|EBP|ESI|EDI|EIP|"
                                  r"EFL|CS|SS|DS|ES|FS|GS)\s*=\s*([0-9A-Fa-f]+)",
                                  raw):
        answer[name] = int(value, 16)
    return answer


def rsp_registers(raw: str) -> dict[str, int]:
    names = ("EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI",
             "EIP", "EFLAGS", "CS", "SS", "DS", "ES", "FS", "GS")
    values = [int.from_bytes(bytes.fromhex(raw[i:i + 8]), "little")
              for i in range(0, min(len(raw), 16 * 8), 8)]
    return dict(zip(names, values))


def xp(qmp, address: int, count: int) -> bytes:
    raw = qmp.hmp(f"xp /{count}xb 0x{address:X}")
    values = []
    for token in raw.split():
        if token.lower().startswith("0x"):
            token = token[2:]
        if len(token) == 2 and all(c in "0123456789abcdefABCDEF" for c in token):
            values.append(token)
    return bytes.fromhex("".join(values[:count]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=30.0,
                        help="maximum time to wait for the first write")
    parser.add_argument("--target", action="append", type=lambda v: int(v, 0),
                        default=None, help="linear address to watch (repeatable)")
    args = parser.parse_args()
    targets = tuple(args.target) if args.target else DEFAULT_TARGETS

    hdd = run_qemu.HDD
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
               "-no-reboot", "-S", "-gdb", f"tcp:127.0.0.1:{rsp_port}",
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
        rsp.sock.settimeout(max(1.0, args.seconds))
        print("rsp:", rsp.command("qSupported:multiprocess+;xmlRegisters=i386"),
              flush=True)
        print("initial stop:", rsp.command("?"), flush=True)
        for target in targets:
            print(f"watch 0x{target:X}:",
                  rsp.command(f"Z2,{target:X},4"), flush=True)
        try:
            stop = rsp.command("c")
        except socket.timeout:
            print(f"continue: no watchpoint within {args.seconds:g}s", flush=True)
            return 2
        print("continue:", stop, flush=True)
        raw = qmp.hmp("info registers")
        print("--- info registers ---")
        print(raw.strip())
        regs = parse_registers(raw)
        segments = parse_segment_dump(raw)
        print("--- parsed GDB registers ---")
        print(regs)
        print("--- parsed segment descriptors ---")
        print(segments)
        raw_rsp = rsp.command("g")
        print("RSP registers:", rsp_registers(raw_rsp), flush=True)
        exe = EXE.read_bytes()

        cs = segments.get("CS", (0, 0, 0, 0))
        linear_eip = cs[1] + regs.get("EIP", 0)
        print(f"linear EIP: 0x{linear_eip:X}")
        code = xp(qmp, max(0, linear_eip - 0x40), 0x80)
        print(f"code @0x{max(0, linear_eip - 0x40):X}: {code.hex(' ')}")
        for name, reg_name in (("DS", "ESI"), ("ES", "EDI")):
            if name in segments and reg_name in regs:
                base = segments[name][1]
                address = base + regs[reg_name]
                print(f"{name}:{reg_name} -> 0x{address:X} "
                      f"({xp(qmp, address, 32).hex(' ')})")
        if (0x1B7599 in targets
                and all(name in segments for name in ("DS", "ES"))):
            copied = regs.get("EAX", 0)
            source_end = segments["DS"][1] + regs.get("ESI", 0)
            destination_end = segments["ES"][1] + regs.get("EDI", 0)
            source_start = source_end - copied
            destination_start = destination_end - copied
            source = xp(qmp, source_start, copied)
            tail_start = 0x9283D
            expected = exe[tail_start:tail_start + copied]
            file_start = 0x922A4
            file_expected = exe[file_start:file_start + copied]
            print(f"copy range: 0x{source_start:X}..0x{source_end:X} -> "
                  f"0x{destination_start:X}..0x{destination_end:X}; "
                  f"{len(source)} bytes")
            print(f"source head: {source[:32].hex(' ')}")
            print(f"source == PANZER tail start: {source == expected}")
            print(f"source == PANZER file 0x{file_start:X}: "
                  f"{source == file_expected}")
            if source:
                hit = exe.find(source[:32])
                print(f"source head/file match: "
                      f"0x{hit:X}" if hit >= 0 else
                      "source head/file match: none")
        for target in targets:
            print(f"target 0x{target:X}: {xp(qmp, target, 32).hex(' ')}")

        needle = code[0x40:0x50]
        hits = []
        start = 0
        while needle:
            hit = exe.find(needle, start)
            if hit < 0:
                break
            hits.append(hit)
            start = hit + 1
        print("code/file matches:", [f"0x{x:X}" for x in hits])
        return 0
    finally:
        try:
            qmp.hmp("quit")
        except Exception:
            pass
        if rsp is not None:
            rsp.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
