#!/usr/bin/env python3
"""Trace DOS file opens around the Falcon3 War Room -> flight transition.

The static listing contains direct ``INT 21h`` sites. With the measured MZ
file-to-linear mapping (+0x1AF0), this probe attaches after DOS has loaded the
game, sets software breakpoints on every INT 21h opcode in the MZ image, and
reads DS:DX when AH=3Dh (open) is about to execute.
"""

from __future__ import annotations

import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HDD = ROOT / "img" / "falcon3.hdd"
GDB_PORT = 4567
QMP_PORT = 4557
EXE = ROOT / "game" / "FALCON3" / "FALCON3.EXE"
FILE_TO_LINEAR = 0x1AF0
MZ_START = 0x2C00
MZ_END = 0x1FB51
STARTUP_WAIT = 15.0
NAV_AFTER_ATTACH = 5.0
TRACE_WINDOW = 90.0
sys.path.insert(0, str(ROOT))
# The bundled QEMU is not always on PATH in a fresh desktop shell.
bundled_qemu = Path(r"C:\Program Files\Qemu\qemu-system-i386.exe")
if bundled_qemu.exists():
    os.environ.setdefault("QEMU_SYSTEM_I386", str(bundled_qemu))
import work.gdbstub_probe as qemu


class GdbRemote:
    def __init__(self, port: int):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=30)
        self.sock.settimeout(120)
        # QEMU may send an initial stop reply as soon as the connection opens.
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
            expected = sum(body) & 0xFF
            if int(checksum, 16) != expected:
                self.sock.sendall(b"-")
                raise ValueError("bad GDB remote checksum")
            self.sock.sendall(b"+")
            return bytes(body).decode("ascii", errors="replace")
        finally:
            if timeout is not None:
                self.sock.settimeout(old)

    def request(self, body: str):
        packet = body.encode("ascii")
        checksum = sum(packet) & 0xFF
        self.sock.sendall(b"$" + packet + f"#{checksum:02x}".encode("ascii"))
        return self._read_packet()

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def registers(gdb: GdbRemote):
    raw = gdb.request("g")
    if raw.startswith("E"):
        raise RuntimeError(f"GDB register read failed: {raw}")
    values = struct.unpack("<16I", bytes.fromhex(raw[:16 * 8]))
    names = ("EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI",
             "EIP", "EFLAGS", "CS", "SS", "DS", "ES", "FS", "GS")
    return dict(zip(names, values))


def read_memory(gdb: GdbRemote, address: int, count: int) -> bytes:
    raw = gdb.request(f"m{address:x},{count:x}")
    if raw.startswith("E"):
        return b""
    return bytes.fromhex(raw)


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "unnamed"


def main() -> None:
    geometry = json.loads(HDD.with_suffix(HDD.suffix + ".geom.json").read_text())
    g = geometry
    qemu.kill_strays()
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
    out = ROOT / "work" / "qemu_out" / "file_open_trace.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        print(f"waiting {STARTUP_WAIT:.0f}s for the game startup ...",
              flush=True)
        time.sleep(STARTUP_WAIT)
        gdb = GdbRemote(GDB_PORT)
        print("GDB target attached; setting INT 21h breakpoints ...", flush=True)
        data = EXE.read_bytes()
        int21_offsets = [
            off for off in range(MZ_START, MZ_END - 1)
            if data[off:off + 2] == b"\xcd\x21"
        ]
        for off in int21_offsets:
            address = off + FILE_TO_LINEAR
            reply = gdb.request(f"Z0,{address:x},1")
            if reply != "OK":
                raise RuntimeError(
                    f"breakpoint insertion failed at file {off:#x}: {reply}")
        print(f"set {len(int21_offsets)} INT 21h breakpoints", flush=True)
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
            print("navigation sent; tracing file opens ...", flush=True)

        import threading
        threading.Thread(target=navigate, daemon=True).start()
        print("tracing startup and waiting for scheduled navigation ...",
              flush=True)
        deadline = time.monotonic() + TRACE_WINDOW
        try:
            while time.monotonic() < deadline:
                stop = gdb.request("c")
                if stop.startswith(("W", "X")):
                    break
                if not stop.startswith("T"):
                    print("unexpected GDB stop reply:", stop)
                    break
                regs = registers(gdb)
                ah = (regs["EAX"] >> 8) & 0xFF
                before = {
                    "handle": regs["EBX"] & 0xFFFF,
                    "count": regs["ECX"] & 0xFFFF,
                    "segment": regs["DS"] & 0xFFFF,
                    "offset": regs["EDX"] & 0xFFFF,
                }
                name = ""
                if ah == 0x3D:
                    address = (before["segment"] << 4) + before["offset"]
                    raw_name = read_memory(gdb, address, 128)
                    name = raw_name.split(b"\0", 1)[0].decode(
                        "ascii", errors="replace")
                    event = {
                        "cs": regs["CS"] & 0xFFFF,
                        "ip": regs["EIP"] & 0xFFFF,
                        "ah": ah,
                        "ds": regs["DS"] & 0xFFFF,
                        "dx": regs["EDX"] & 0xFFFF,
                        "name": name,
                    }
                    events.append(event)
                    # Flush after every open so a debugger stop or manual
                    # termination cannot discard an otherwise useful trace.
                    out.write_text(json.dumps(events, indent=2) + "\n")
                    print(f"  {event['cs']:04x}:{event['ip']:04x} "
                          f"AH=3d DS:DX={event['ds']:04x}:{event['dx']:04x} "
                          f"{name!r}", flush=True)
                # The raw remote protocol does not automatically step over a
                # software breakpoint like GDB does.  Without this one-step,
                # the next `c` would stop on the same INT 21h forever.
                stepped = gdb.request("s")
                if not stepped.startswith("T"):
                    print("unexpected single-step reply:", stepped)
                    break
        except (ConnectionError, OSError, socket.timeout) as exc:
            print(f"trace ended with guest disconnect: {exc}")
        out.write_text(json.dumps(events, indent=2) + "\n")
        print(f"saved {len(events)} open events to {out}")
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
