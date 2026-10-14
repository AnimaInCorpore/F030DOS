#!/usr/bin/env python3
"""Trace the active COCKPIT loader and its resident stream callbacks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import struct
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HDD = ROOT / "img" / "falcon3.hdd"
GDB_PORT = 4567
QMP_PORT = 4557
FILE_TO_LINEAR = 0x1AF0
STARTUP_WAIT = 15.0
NAV_AFTER_ATTACH = 3.0
TRACE_WINDOW = 65.0

# The five copies are the loaded variants of the static chunked-resource
# loader.  The second one is the variant containing the COCKPIT chunk-5 path
# in the captured Instant Action snapshot, but all are retained to identify
# the actual pathname at runtime.
LOADER_ENTRIES = {
    "loader_0": 0x25CAD,
    "loader_1": 0x25DBD,
    "loader_2": 0x25EA0,
    "loader_3": 0x25FCE,
    "loader_4": 0x26123,
}
CALLBACKS = {
    "stream_read": (0x13DB << 4) + 0x7F18,
    "stream_copy": (0x13DB << 4) + 0x7FD7,
    "state8_setup": (0x13DB << 4) + 0x81F9,
    "state0_reset": (0x13DB << 4) + 0x8188,
    "stream_runner": (0x13DB << 4) + 0x8001,
}
HANDLER = (0x7A1D << 4) + 0x1334
DISPATCH = {
    "open": FILE_TO_LINEAR + 0x152BD,
    "read": FILE_TO_LINEAR + 0x152F5,
    "seek": FILE_TO_LINEAR + 0x1534D,
}
DISPATCH_RETURNS = {
    "open": FILE_TO_LINEAR + 0x152DE,
    "read": FILE_TO_LINEAR + 0x15311,
    "seek": FILE_TO_LINEAR + 0x1535F,
}

sys.path.insert(0, str(ROOT))
bundled_qemu = Path(r"C:\Program Files\Qemu\qemu-system-i386.exe")
if bundled_qemu.exists():
    os.environ.setdefault("QEMU_SYSTEM_I386", str(bundled_qemu))
import work.gdbstub_probe as qemu
from work.trace_cockpit_io import GdbRemote, continue_to, read_memory, registers


def path_from_regs(gdb: GdbRemote, regs: dict[str, int]) -> str:
    address = ((regs["DS"] & 0xFFFF) << 4) + (regs["EDX"] & 0xFFFF)
    raw = read_memory(gdb, address, 128)
    return raw.split(b"\0", 1)[0].decode("ascii", errors="replace")


def resource_path(gdb: GdbRemote, regs: dict[str, int]) -> str:
    address = ((regs["DS"] & 0xFFFF) << 4) + 0x454
    raw = read_memory(gdb, address, 128)
    return raw.split(b"\0", 1)[0].decode("ascii", errors="replace")


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
    events: list[dict] = []
    handles: dict[int, str] = {}
    cockpit_active = False
    stream_dumps: dict[str, str] = {}
    try:
        print(f"waiting {STARTUP_WAIT:.0f}s for startup ...", flush=True)
        time.sleep(STARTUP_WAIT)
        gdb = GdbRemote(GDB_PORT)
        points = {
            **LOADER_ENTRIES,
            "stream_copy": CALLBACKS["stream_copy"],
            "state8_setup": CALLBACKS["state8_setup"],
            "state0_reset": CALLBACKS["state0_reset"],
            "planar_handler": HANDLER,
            **DISPATCH,
            **DISPATCH_RETURNS,
        }
        for address in sorted(set(points.values())):
            reply = gdb.request(f"Z0,{address:x},1")
            if reply != "OK":
                raise RuntimeError(f"breakpoint insertion failed at {address:#x}: {reply}")
        print(f"set {len(set(points.values()))} breakpoints", flush=True)
        qmp = qemu.Qmp(QMP_PORT)

        def navigate() -> None:
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
            before = registers(gdb)
            physical = ((before["CS"] & 0xFFFF) << 4) + (before["EIP"] & 0xFFFF)
            label = next((name for name, value in points.items() if value == physical), None)
            event: dict = {
                "label": label,
                "linear": physical,
                "cs": before["CS"] & 0xFFFF,
                "ip": before["EIP"] & 0xFFFF,
                "ds": before["DS"] & 0xFFFF,
                "si": before["ESI"] & 0xFFFF,
                "di": before["EDI"] & 0xFFFF,
                "bx": before["EBX"] & 0xFFFF,
                "cx": before["ECX"] & 0xFFFF,
                "dx": before["EDX"] & 0xFFFF,
                "state": int.from_bytes(read_memory(
                    gdb, (0x13DB << 4) + 0x7DB4, 2), "little"
                ) if label in CALLBACKS else None,
            }
            if label in LOADER_ENTRIES:
                event["pathname"] = resource_path(gdb, before)
                if event["pathname"].upper() == "COCKPIT":
                    cockpit_active = True
            elif physical == DISPATCH["open"]:
                name = path_from_regs(gdb, before)
                after = continue_to(gdb, physical, DISPATCH_RETURNS["open"])
                handle = after["EAX"] & 0xFFFF
                handles[handle] = name
                event.update({"pathname": name, "handle": handle})
            elif physical == DISPATCH["read"]:
                handle = before["EBX"] & 0xFFFF
                event.update({"handle": handle, "name": handles.get(handle, "<unknown>"),
                              "requested": before["ECX"] & 0xFFFF})
                after = continue_to(gdb, physical, DISPATCH_RETURNS["read"])
                event["returned"] = after["EAX"] & 0xFFFF
            elif physical == DISPATCH["seek"]:
                continue_to(gdb, physical, DISPATCH_RETURNS["seek"])
            elif label in CALLBACKS:
                event["stack_hex"] = read_memory(
                    gdb, ((before["SS"] & 0xFFFF) << 4) + (before["ESP"] & 0xFFFF), 48
                ).hex()
                words = struct.unpack("<24H", bytes.fromhex(event["stack_hex"]))
                if label == "stream_copy" and cockpit_active:
                    length_offset, length_segment = words[2], words[3]
                    source_offset, source_segment = words[4], words[5]
                    length_raw = read_memory(
                        gdb, (length_segment << 4) + length_offset, 2
                    )
                    input_length = int.from_bytes(length_raw, "little")
                    event.update({
                        "length_ptr": [length_segment, length_offset],
                        "source_ptr": [source_segment, source_offset],
                        "input_length": input_length,
                    })
                    if input_length:
                        payload = read_memory(
                            gdb, (source_segment << 4) + source_offset,
                            min(input_length, 8192),
                        )
                        key = f"{source_segment:04x}:{source_offset:04x}:{input_length:04x}"
                        if key not in stream_dumps:
                            path = ROOT / "work" / "qemu_out" / (
                                f"cockpit_stream_{len(stream_dumps):02d}_"
                                f"{source_segment:04x}_{source_offset:04x}_"
                                f"{input_length:04x}.bin"
                            )
                            path.write_bytes(payload)
                            stream_dumps[key] = str(path)
                        event["payload_path"] = stream_dumps[key]
            elif label == "planar_handler" and cockpit_active:
                address = ((before["DS"] & 0xFFFF) << 4) + (before["ESI"] & 0xFFFF)
                input_length = before["ECX"] & 0xFFFF
                payload = read_memory(gdb, address, min(input_length, 8192))
                key = f"handler:{before['DS'] & 0xFFFF:04x}:{before['ESI'] & 0xffff:04x}:{input_length:04x}"
                if key not in stream_dumps:
                    path = ROOT / "work" / "qemu_out" / (
                        f"cockpit_planar_{len(stream_dumps):02d}_"
                        f"{before['DS'] & 0xffff:04x}_{before['ESI'] & 0xffff:04x}_"
                        f"{input_length:04x}.bin"
                    )
                    path.write_bytes(payload)
                    stream_dumps[key] = str(path)
                event.update({
                    "input_length": input_length,
                    "input_ptr": [before["DS"] & 0xFFFF, before["ESI"] & 0xFFFF],
                    "output_ptr": [before["ES"] & 0xFFFF, before["EDI"] & 0xFFFF],
                    "handler_state": read_memory(gdb, (0x7A1D << 4) + 0x82A, 10).hex(),
                    "payload_path": stream_dumps[key],
                })
            events.append(event)
            if label in LOADER_ENTRIES or (label in {"stream_copy", "planar_handler"} and cockpit_active):
                print(event, flush=True)
            if label == "state0_reset" and cockpit_active:
                break
            if physical in DISPATCH.values():
                continue
            # Remove/reinsert the current software breakpoint while executing
            # the instruction at the stop address.
            gdb.request(f"z0,{physical:x},1")
            stepped = gdb.request("s")
            if not stepped.startswith("T"):
                raise RuntimeError(f"single-step failed at {physical:#x}: {stepped}")
            gdb.request(f"Z0,{physical:x},1")
        (ROOT / "work" / "qemu_out" / "cockpit_pipeline_trace.json").write_text(
            json.dumps({"events": events, "stream_dumps": stream_dumps}, indent=2) + "\n"
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
