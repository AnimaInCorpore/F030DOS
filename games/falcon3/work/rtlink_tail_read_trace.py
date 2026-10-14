#!/usr/bin/env python3
"""Measure how the RTLink loader reads each overlay segment, including the last.

The directory's final record (segment 71) declares storage through file
0x14F5F0 while FALCON3.EXE ends at 0x14F5E7.  Statically, the resident RTLink
loader seeks with ``INT 21h AX=4200h`` at 1AA3:0332 (file 0x1D962) and reads
``[record+10h]`` paragraphs in chunks with ``INT 21h AH=3Fh`` at 1AA3:036A
(file 0x1D99A).  After the read it tests only CF (1AA3:036C ``jb 038D``); it
never compares AX with CX, unlike the relocation read at 1AA3:0420.

This probe arms breakpoints from boot on both INT 21h sites and on the
instruction after each, then records, per call: the directory record in
effect (``[DS:0A8Ah]`` -> CS-relative 18-byte record), the requested byte
count, the DOS result (AX, CF), the file position, and the destination bytes
around the end of the requested range before and after the read.  It follows
the timed War Room -> Instant Action navigation from qemu-boot.md.

DOS: RTLink loader 1AA3:032B-1AA3:0398 (file 0x1D95B-0x1D9C8); record:
analysis/executable.md "RTLink v1 appended-tail directory".
"""

from __future__ import annotations

import json
import socket
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import work.gdbstub_probe as qemu
from work.file_open_trace import GdbRemote, read_memory, registers

HDD = ROOT / "img" / "falcon3.hdd"
EXE = ROOT / "game" / "FALCON3" / "FALCON3.EXE"
OUT = ROOT / "work" / "qemu_out"

FILE_TO_LINEAR = 0x1AF0          # measured War Room delta, executable.md
RTLINK_FILE = 0x1D630            # file offset of segment 1AA3
RUNTIME_CS = 0x1AA3 + 0x046F     # load-module base segment 0x046F
SEEK_INT, SEEK_RET = 0x0332, 0x0334
READ_INT, READ_RET = 0x036A, 0x036C
WINDOW = 32
NAV = [(20, "spc"), (30, "spc")] + \
      [(36 + i, "right") for i in range(4)] + \
      [(40 + i, "up") for i in range(4)] + [(45, "ret")]
TRACE_SECONDS = 75.0


def linear(ip: int) -> int:
    return RTLINK_FILE + ip + FILE_TO_LINEAR


def word(gdb: GdbRemote, address: int) -> int:
    raw = read_memory(gdb, address, 2)
    return struct.unpack("<H", raw)[0] if len(raw) == 2 else -1


def decode_record(raw: bytes) -> dict:
    return {
        "load_segment": struct.unpack_from("<H", raw, 0)[0],
        "header_paragraphs": raw[4] | raw[5] << 8 | raw[6] << 16,
        "flags": raw[7],
        "memory_paragraphs": struct.unpack_from("<H", raw, 8)[0],
        "relocations": struct.unpack_from("<H", raw, 10)[0],
        "segment": struct.unpack_from("<H", raw, 14)[0],
        "paragraphs": struct.unpack_from("<H", raw, 16)[0],
    }


def main() -> None:
    exe = EXE.read_bytes()
    g = json.loads(HDD.with_suffix(HDD.suffix + ".geom.json").read_text())
    gdb_port, qmp_port = qemu.free_port(), qemu.free_port()
    cmd = [
        qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
        "-drive", f"file={HDD.as_posix()},format=raw,if=none,id=hd0,cache=writeback",
        "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                   f"heads={g['heads']},secs={g['secs']}",
        "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
        "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,wait=off",
        "-gdb", f"tcp:127.0.0.1:{gdb_port}", "-S",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "rtlink_tail_read_trace.json"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    events: list[dict] = []
    false_hits = 0
    position: dict[int, int] = {}
    gdb = qmp = None
    try:
        for _ in range(50):
            try:
                gdb = GdbRemote(gdb_port)
                break
            except OSError:
                time.sleep(0.1)
        qmp = qemu.Qmp(qmp_port)
        sites = {linear(ip): ip for ip in (SEEK_INT, SEEK_RET, READ_INT, READ_RET)}
        for address in sites:
            if gdb.request(f"Z0,{address:x},1") != "OK":
                raise RuntimeError(f"breakpoint insertion failed at {address:#x}")
        start = time.monotonic()
        stop_flag = threading.Event()

        def drive():
            for at, key in NAV:
                time.sleep(max(0.0, start + at - time.monotonic()))
                qmp.hmp(f"sendkey {key}")
            time.sleep(max(0.0, start + TRACE_SECONDS - time.monotonic()))
            stop_flag.set()
            gdb.sock.sendall(b"\x03")

        threading.Thread(target=drive, daemon=True).start()
        pending = None
        while True:
            stop = gdb.request("c")
            if stop_flag.is_set() or not stop.startswith("T"):
                break
            regs = registers(gdb)
            cs, ip = regs["CS"] & 0xFFFF, regs["EIP"] & 0xFFFF
            here = (cs << 4) + ip
            if cs != RUNTIME_CS or sites.get(here) != ip:
                false_hits += 1
            elif ip == SEEK_INT:
                pending = {"kind": "seek", "handle": regs["EBX"] & 0xFFFF,
                           "requested": (regs["ECX"] & 0xFFFF) << 16 | regs["EDX"] & 0xFFFF}
            elif ip == SEEK_RET and pending and pending["kind"] == "seek":
                pending["result"] = (regs["EDX"] & 0xFFFF) << 16 | regs["EAX"] & 0xFFFF
                pending["cf"] = regs["EFLAGS"] & 1
                position[pending["handle"]] = pending["result"]
                events.append(pending)
                pending = None
            elif ip == READ_INT:
                sp = ((regs["SS"] & 0xFFFF) << 4) + (regs["ESP"] & 0xFFFF)
                caller_ds = word(gdb, sp + 4)             # push ds at 1AA3:0334
                rec_ptr = word(gdb, (caller_ds << 4) + 0x0A8A)
                record = decode_record(read_memory(gdb, (cs << 4) + rec_ptr, 18))
                handle, count = regs["EBX"] & 0xFFFF, regs["ECX"] & 0xFFFF
                dest = (regs["DS"] & 0xFFFF) << 4
                lo = max(0, count - WINDOW)
                pending = {"kind": "read", "handle": handle, "count": count,
                           "dest_segment": regs["DS"] & 0xFFFF, "record": record,
                           "file_position": position.get(handle, -1),
                           "window_offset": lo,
                           "before": read_memory(gdb, dest + lo, count - lo).hex()}
            elif ip == READ_RET and pending and pending["kind"] == "read":
                dest = pending["dest_segment"] << 4
                lo, count = pending["window_offset"], pending["count"]
                pending["returned"] = regs["EAX"] & 0xFFFF
                pending["cf"] = regs["EFLAGS"] & 1
                pending["after"] = read_memory(gdb, dest + lo, count - lo).hex()
                pos = pending["file_position"]
                if pos >= 0:
                    pending["file_bytes"] = exe[pos + lo:pos + count].hex()
                    position[pending["handle"]] = pos + pending["returned"]
                events.append(pending)
                pending = None
                out.write_text(json.dumps({"events": events}, indent=2) + "\n")
            # Step off the breakpoint without re-reporting it, then re-arm.
            gdb.request(f"z0,{here:x},1") if here in sites else None
            gdb.request("s")
            if here in sites:
                gdb.request(f"Z0,{here:x},1")
        qmp.hmp(f"screendump {(OUT / 'rtlink_tail_read_trace_end.ppm').as_posix()}")
    except (ConnectionError, OSError, socket.timeout) as exc:
        print(f"trace ended with guest disconnect: {exc}")
    finally:
        out.write_text(json.dumps({"false_hits": false_hits, "events": events},
                                  indent=2) + "\n")
        reads = [e for e in events if e["kind"] == "read"]
        short = [e for e in reads if e.get("returned", e["count"]) != e["count"]]
        print(f"{len(events)} events, {len(reads)} reads, {len(short)} short, "
              f"{false_hits} false hits -> {out}")
        for e in short:
            print(f"  segment {e['record']['segment']} pos {e['file_position']:#x} "
                  f"count {e['count']:#x} returned {e['returned']:#x} cf {e['cf']}")
        for obj in (gdb, qmp):
            if obj is not None:
                obj.close()
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
