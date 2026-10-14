#!/usr/bin/env python3
"""Capture trustworthy DOS reads for the COCKPIT loader.

The earlier probe left the INT 21h breakpoint installed while asking the raw
GDB stub to single-step.  That can stop on the same breakpoint again.  This
probe explicitly removes each breakpoint for the one instruction being
stepped, then reinstalls it, so AH=3Dh/3Fh/42h results are real DOS results.
"""

from __future__ import annotations

import json
import hashlib
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HDD = ROOT / "img" / "falcon3.hdd"
EXE = ROOT / "game" / "FALCON3" / "FALCON3.EXE"
GDB_PORT = 4567
QMP_PORT = 4557
FILE_TO_LINEAR = 0x1AF0
MZ_START = 0x2C00
MZ_END = 0x1FB51
STARTUP_WAIT = 15.0
NAV_AFTER_ATTACH = 5.0
TRACE_WINDOW = 90.0
DISPATCH = {
    "open": 0x152BD,
    "read": 0x152F5,
    "seek": 0x1534D,
}
DISPATCH_RETURNS = {
    "open": 0x152DE,
    "read": 0x15311,
    "seek": 0x1535F,
}
SEGMENT7_FILE_START = 0x26180
SEGMENT7_LOAD = 0x1E10
LOADER_RETURNS = {
    "multi": 0x29735,
    "packed": 0x2982E,
    "stream2": 0x2995C,
    "stream4": 0x29AB1,
    "stream5": 0x29C38,
}
HANDLER_SEGMENT = 0x7A1D
HANDLERS = {
    "literal": 0x1280,
    "sentinel_ab": 0x12D3,
    "planar": 0x1334,
    "sentinel_zero": 0x135F,
}

sys.path.insert(0, str(ROOT))
bundled_qemu = Path(r"C:\Program Files\Qemu\qemu-system-i386.exe")
if bundled_qemu.exists():
    os.environ.setdefault("QEMU_SYSTEM_I386", str(bundled_qemu))
import work.gdbstub_probe as qemu


class GdbRemote:
    def __init__(self, port: int):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=30)
        self.sock.settimeout(120)
        try:
            self._read_packet(timeout=1.0)
        except socket.timeout:
            pass

    def _read_packet(self, timeout=None):
        old = self.sock.gettimeout()
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            while True:
                ch = self.sock.recv(1)
                if not ch:
                    raise ConnectionError("GDB remote socket closed")
                if ch == b"$":
                    break
                if ch in (b"+", b"-"):
                    continue
            body = bytearray()
            while True:
                ch = self.sock.recv(1)
                if ch == b"#":
                    break
                body.extend(ch)
            checksum = self.sock.recv(2)
            if int(checksum, 16) != (sum(body) & 0xFF):
                self.sock.sendall(b"-")
                raise ValueError("bad GDB remote checksum")
            self.sock.sendall(b"+")
            return bytes(body).decode("ascii", errors="replace")
        finally:
            if timeout is not None:
                self.sock.settimeout(old)

    def request(self, body: str):
        packet = body.encode("ascii")
        self.sock.sendall(b"$" + packet + f"#{sum(packet) & 0xFF:02x}".encode())
        return self._read_packet()

    def close(self):
        self.sock.close()


def registers(gdb: GdbRemote) -> dict[str, int]:
    raw = gdb.request("g")
    values = struct.unpack("<16I", bytes.fromhex(raw[:16 * 8]))
    names = ("EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI",
             "EIP", "EFLAGS", "CS", "SS", "DS", "ES", "FS", "GS")
    return dict(zip(names, values))


def read_memory(gdb: GdbRemote, address: int, count: int) -> bytes:
    raw = gdb.request(f"m{address:x},{count:x}")
    return b"" if raw.startswith("E") else bytes.fromhex(raw)


def breakpoint_address(file_offset: int) -> int:
    return file_offset + FILE_TO_LINEAR


def tail_address(file_offset: int) -> int:
    return (SEGMENT7_LOAD << 4) + (file_offset - SEGMENT7_FILE_START)


def step_over_breakpoint(gdb: GdbRemote, address: int) -> dict[str, int]:
    removed = gdb.request(f"z0,{address:x},1")
    if removed != "OK":
        raise RuntimeError(f"breakpoint removal failed at {address:#x}: {removed}")
    stop = gdb.request("s")
    if not stop.startswith("T"):
        raise RuntimeError(f"single-step failed at {address:#x}: {stop}")
    inserted = gdb.request(f"Z0,{address:x},1")
    if inserted != "OK":
        raise RuntimeError(f"breakpoint restore failed at {address:#x}: {inserted}")
    return registers(gdb)


def continue_to(gdb: GdbRemote, current: int, target: int) -> dict[str, int]:
    """Run from a stopped breakpoint to a temporary breakpoint at target."""
    removed = gdb.request(f"z0,{current:x},1")
    if removed != "OK":
        raise RuntimeError(f"breakpoint removal failed at {current:#x}: {removed}")
    inserted = gdb.request(f"Z0,{target:x},1")
    if inserted != "OK":
        raise RuntimeError(f"temporary breakpoint failed at {target:#x}: {inserted}")
    stop = gdb.request("c")
    gdb.request(f"z0,{target:x},1")
    restored = gdb.request(f"Z0,{current:x},1")
    if restored != "OK":
        raise RuntimeError(f"breakpoint restore failed at {current:#x}: {restored}")
    if not stop.startswith("T"):
        raise RuntimeError(f"run to {target:#x} failed: {stop}")
    return registers(gdb)


def main() -> None:
    geometry = json.loads(HDD.with_suffix(HDD.suffix + ".geom.json").read_text())
    qemu.kill_strays()
    g = geometry
    cmd = [
        qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
        "-drive", f"file={HDD.as_posix()},format=raw,if=none,id=hd0,cache=writeback",
        "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                   f"heads={g['heads']},secs={g['secs']}",
        "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
        "-qmp", f"tcp:127.0.0.1:{QMP_PORT},server=on,wait=off",
        "-gdb", f"tcp:127.0.0.1:{GDB_PORT}",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    gdb = None
    qmp = None
    events = []
    buffer_dumps = []
    cockpit_read_files = []
    last_cockpit_read_seen = False
    handles: dict[int, str] = {}
    output = ROOT / "work" / "qemu_out"
    output.mkdir(parents=True, exist_ok=True)
    try:
        print(f"waiting {STARTUP_WAIT:.0f}s for startup ...", flush=True)
        time.sleep(STARTUP_WAIT)
        gdb = GdbRemote(GDB_PORT)
        dispatch_addresses = {
            kind: breakpoint_address(off) for kind, off in DISPATCH.items()
        }
        dispatch_returns = {
            kind: breakpoint_address(off) for kind, off in DISPATCH_RETURNS.items()
        }
        points = set(dispatch_addresses.values())
        points.update(dispatch_addresses.values())
        return_addresses = {
            name: tail_address(off) for name, off in LOADER_RETURNS.items()
        }
        handler_addresses = {
            name: (HANDLER_SEGMENT << 4) + offset
            for name, offset in HANDLERS.items()
        }
        points.update(return_addresses.values())
        points.update(handler_addresses.values())
        for address in sorted(points):
            reply = gdb.request(f"Z0,{address:x},1")
            if reply != "OK":
                raise RuntimeError(f"breakpoint insertion failed at {address:#x}: {reply}")
        print(f"set {len(points)} breakpoints; dispatch={dispatch_addresses}", flush=True)
        qmp = qemu.Qmp(QMP_PORT)

        def navigate():
            time.sleep(NAV_AFTER_ATTACH)
            qmp.hmp("sendkey spc")
            time.sleep(10.0)
            qmp.hmp("sendkey spc")
            time.sleep(6.0)
            for key in (["right"] * 4) + (["up"] * 4):
                qmp.hmp(f"sendkey {key}")
                time.sleep(0.8)
            qmp.hmp("sendkey ret")
            print("navigation sent", flush=True)

        threading.Thread(target=navigate, daemon=True).start()
        deadline = time.monotonic() + TRACE_WINDOW
        while time.monotonic() < deadline:
            stop = gdb.request("c")
            if stop.startswith(("W", "X")):
                break
            if not stop.startswith("T"):
                print("unexpected stop:", stop, flush=True)
                break
            regs_before = registers(gdb)
            eip = ((regs_before["CS"] & 0xFFFF) << 4) + (regs_before["EIP"] & 0xFFFF)
            kind = next((k for k, v in dispatch_addresses.items() if v == eip), None)
            loader = next((k for k, v in return_addresses.items() if v == eip), None)
            handler = next((k for k, v in handler_addresses.items() if v == eip), None)
            if kind == "open":
                address = ((regs_before["DS"] & 0xFFFF) << 4) + (regs_before["EDX"] & 0xFFFF)
                raw = read_memory(gdb, address, 128)
                name = raw.split(b"\0", 1)[0].decode("ascii", errors="replace")
                after = continue_to(gdb, dispatch_addresses[kind], dispatch_returns[kind])
                handle = after["EAX"] & 0xFFFF
                ok = handle != 0xFFFF
                if ok:
                    handles[handle] = name
                event = {"type": "open", "name": name, "handle": handle,
                         "ok": ok, "ds": regs_before["DS"] & 0xFFFF,
                         "dx": regs_before["EDX"] & 0xFFFF}
                events.append(event)
                print("open", event, flush=True)
                continue
            if kind == "read":
                handle = regs_before["EBX"] & 0xFFFF
                segment = regs_before["DS"] & 0xFFFF
                offset = regs_before["EDX"] & 0xFFFF
                requested = regs_before["ECX"] & 0xFFFF
                after = continue_to(gdb, dispatch_addresses[kind], dispatch_returns[kind])
                returned = after["EAX"] & 0xFFFF
                ok = returned != 0xFFFF
                event = {"type": "read", "name": handles.get(handle, "<unknown>"),
                         "handle": handle, "segment": segment, "offset": offset,
                         "requested": requested, "returned": returned, "ok": ok,
                         "cs": regs_before["CS"] & 0xFFFF,
                         "ip": regs_before["EIP"] & 0xFFFF,
                         "ss": regs_before["SS"] & 0xFFFF,
                         "sp": regs_before["ESP"] & 0xFFFF}
                if ok and event["name"] == "COCKPIT" and returned:
                    payload = read_memory(gdb, (segment << 4) + offset, returned)
                    path = output / (
                        f"cockpit_read_{len(cockpit_read_files):02d}_"
                        f"{segment:04x}_{offset:04x}_{returned:04x}.bin"
                    )
                    path.write_bytes(payload)
                    cockpit_read_files.append(str(path))
                    event["data_path"] = str(path)
                    event["data_sha256"] = hashlib.sha256(payload).hexdigest()
                    event["data_hex"] = payload[:32].hex()
                    event["stack_hex"] = read_memory(
                        gdb, (event["ss"] << 4) + event["sp"], 64
                    ).hex()
                    table = read_memory(gdb, (regs_before["CS"] << 4) + 0x2AC8, 16)
                    event["handler_table"] = []
                    for index, name in enumerate(HANDLERS):
                        off = int.from_bytes(table[index * 4:index * 4 + 2], "little")
                        seg = int.from_bytes(table[index * 4 + 2:index * 4 + 4], "little")
                        address = (seg << 4) + off
                        handler_addresses[name] = address
                        event["handler_table"].append({"handler": name,
                                                        "segment": seg,
                                                        "offset": off,
                                                        "address": address})
                        if address not in points:
                            reply = gdb.request(f"Z0,{address:x},1")
                            if reply == "OK":
                                points.add(address)
                events.append(event)
                if event["name"] == "COCKPIT":
                    print("read", event, flush=True)
                    if segment == 0x7D0D and offset == 0x5DC0 and returned == 0x2F2B:
                        last_cockpit_read_seen = True
                continue
            if kind == "seek":
                after = continue_to(gdb, dispatch_addresses[kind], dispatch_returns[kind])
                continue
            if loader:
                regs = step_over_breakpoint(gdb, eip)
                ds = regs["DS"] & 0xFFFF
                base = (ds << 4) + 0x5DC0
                blob = read_memory(gdb, base, 0x10000)
                path = output / f"cockpit_loader_{len(buffer_dumps):02d}_{loader}_ds{ds:04x}.bin"
                path.write_bytes(blob)
                buffer_dumps.append({"loader": loader, "ds": ds,
                                     "base": base, "path": str(path),
                                     "sha256": __import__("hashlib").sha256(blob).hexdigest()})
                print("loader return", buffer_dumps[-1], flush=True)
                continue
            if handler:
                ds = regs_before["DS"] & 0xFFFF
                si = regs_before["ESI"] & 0xFFFF
                cs = regs_before["CS"] & 0xFFFF
                state = read_memory(gdb, (cs << 4) + 0x82A, 8)
                count = regs_before["ECX"] & 0xFFFF
                payload_len = min(max(count, int.from_bytes(state[0:2], "little")), 8192)
                payload = read_memory(gdb, (ds << 4) + si, payload_len)
                path = output / f"cockpit_handler_{len(cockpit_read_files):02d}_{handler}.bin"
                path.write_bytes(payload)
                events.append({
                    "type": "handler",
                    "handler": handler,
                    "cs": cs,
                    "ip": regs_before["EIP"] & 0xFFFF,
                    "ds": ds,
                    "si": si,
                    "es": regs_before["ES"] & 0xFFFF,
                    "di": regs_before["EDI"] & 0xFFFF,
                    "cx": count,
                    "bp": regs_before["EBP"] & 0xFFFF,
                    "state_82a": int.from_bytes(state[0:2], "little"),
                    "state_830": int.from_bytes(state[4:6], "little"),
                    "state_832": state[6],
                    "payload_path": str(path),
                    "payload_sha256": hashlib.sha256(payload).hexdigest(),
                })
                print("handler", events[-1], flush=True)
                step_over_breakpoint(gdb, eip)
                if last_cockpit_read_seen:
                    break
                continue
            # Capture a loader buffer at its return point, then execute the
            # return instruction and leave the breakpoint armed.
            step_over_breakpoint(gdb, eip)
        (output / "cockpit_io_trace.json").write_text(
            json.dumps({"events": events, "buffer_dumps": buffer_dumps}, indent=2) + "\n"
        )
        print(f"saved {len(events)} events", flush=True)
    finally:
        if gdb is not None:
            gdb.close()
        if qmp is not None:
            qmp.close()
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
