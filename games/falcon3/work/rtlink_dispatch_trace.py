#!/usr/bin/env python3
"""Trace RTLink overlay selection, caller reloads and eviction in the oracle.

Static reading of the resident RTLink segment 1AA3 (file 0x1D630):

- 303 ten-byte thunks at file 0x1E99D are ``call 058D; jmp far target; dw
  index``.  The dispatcher 1AA3:058D pushes a 6-byte frame (index, caller IP,
  caller CS) on the overlay return stack ``[0A74h]:[0A72h]+[0A70h]``, points
  the caller's far return at 1AA3:0701 (option bit 0 of ``[0C0Dh]``) and calls
  the load entry 1AA3:021C with AX = index.
- 1AA3:0705 pops the frame, restores the caller's return address and, while
  frames remain, calls 021C for the index of the frame below.
- 021C returns at once when the record is loaded (flag 02h) or has no memory;
  otherwise 1AA3:0275 scans every record and 1AA3:02A2 unloads each loaded one
  whose paragraph range overlaps the new record (01B2 refuses flag 10h).
- 1AA3:08B5 preloads flag-01h records; 0936/098D save and restore the loaded
  set.

Breaking on every overlay call would slow the guest past the timed
navigation, so this probe breaks only where a load is actually needed
(1AA3:0275), at each eviction (1AA3:02A2) and at the save/restore bodies.
At the end it reads the live option word, the cache flag, the cache hook at
1C97:0003 and the flag-20h callback operand at 1AA3:0383.

DOS: RTLink dispatcher 1AA3:058D-060F, return handler 1AA3:0701-076B, load
entry 1AA3:021C-02C5, unload 1AA3:01B2-021A; record: analysis/executable.md
"Overlay selection and eviction".
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import work.gdbstub_probe as qemu
from work.file_open_trace import GdbRemote, read_memory, registers
from work.rtlink_tail_read_trace import (HDD, NAV, OUT, RUNTIME_CS,
                                         TRACE_SECONDS, linear, word)

DIRECTORY = 0x0C1F
RECORD = 18
LOAD_NEEDED = 0x0275
EVICT = 0x02A2
SAVE, RESTORE = 0x0936, 0x098D
CALLER_NAMES = {0x0606: "dispatcher call", 0x0757: "return reload",
                0x08BF: "startup preload", 0x09BC: "restore"}
HOOK_LINEAR = (0x1C97 + 0x046F) << 4


def index_of(record_ptr: int) -> int:
    return (record_ptr - DIRECTORY) // RECORD


def main() -> None:
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
    out = OUT / "rtlink_dispatch_trace.json"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    events: list[dict] = []
    final: dict = {}
    false_hits = 0
    gdb = qmp = None
    try:
        for _ in range(50):
            try:
                gdb = GdbRemote(gdb_port)
                break
            except OSError:
                time.sleep(0.1)
        qmp = qemu.Qmp(qmp_port)
        sites = {linear(ip): ip for ip in (LOAD_NEEDED, EVICT, SAVE, RESTORE)}
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
        base = RUNTIME_CS << 4
        while True:
            stop = gdb.request("c")
            if stop_flag.is_set() or not stop.startswith("T"):
                break
            regs = registers(gdb)
            cs, ip = regs["CS"] & 0xFFFF, regs["EIP"] & 0xFFFF
            here = (cs << 4) + ip
            depth = word(gdb, base + 0x0A70)
            if cs != RUNTIME_CS or sites.get(here) != ip:
                false_hits += 1
            elif ip == LOAD_NEEDED:
                bp = ((regs["SS"] & 0xFFFF) << 4) + (regs["EBP"] & 0xFFFF)
                ret_ip, ret_cs = word(gdb, bp + 20), word(gdb, bp + 22)
                record = word(gdb, base + 0x0A8A)
                event = {"kind": "load", "t": round(time.monotonic() - start, 2),
                         "index": index_of(record),
                         "segment": index_of(record) + 2,
                         "via": CALLER_NAMES.get(ret_ip, f"{ret_cs:04x}:{ret_ip:04x}"),
                         "depth_frames": depth // 6,
                         "flags": read_memory(gdb, base + record + 7, 1).hex()}
                if depth >= 6:
                    stack = (word(gdb, base + 0x0A74) << 4) + word(gdb, base + 0x0A72)
                    top = stack + depth - 6
                    event["top_frame"] = {"index": word(gdb, top),
                                          "caller": f"{word(gdb, top + 4):04x}:"
                                                    f"{word(gdb, top + 2):04x}"}
                events.append(event)
            elif ip == EVICT:
                new = regs["EBX"] & 0xFFFF
                old = regs["ESI"] & 0xFFFF
                raw_new = read_memory(gdb, base + new, RECORD)
                raw_old = read_memory(gdb, base + old, RECORD)
                events.append({
                    "kind": "evict", "t": round(time.monotonic() - start, 2),
                    "evicted_index": regs["EAX"] & 0xFFFF,
                    "evicted_segment": index_of(old) + 2,
                    "for_segment": index_of(new) + 2,
                    "evicted_range": [int.from_bytes(raw_old[0:2], "little"),
                                      int.from_bytes(raw_old[8:10], "little")],
                    "new_range": [int.from_bytes(raw_new[0:2], "little"),
                                  int.from_bytes(raw_new[8:10], "little")],
                    "evicted_flags": raw_old[7], "depth_frames": depth // 6})
            else:
                events.append({"kind": "save" if ip == SAVE else "restore",
                               "t": round(time.monotonic() - start, 2),
                               "depth_frames": depth // 6})
            out.write_text(json.dumps({"events": events}, indent=2) + "\n")
            gdb.request(f"z0,{here:x},1") if here in sites else None
            gdb.request("s")
            if here in sites:
                gdb.request(f"Z0,{here:x},1")
        final = {
            "options_0C0D": word(gdb, base + 0x0C0D),
            "cache_flag_0A84": read_memory(gdb, base + 0x0A84, 1).hex(),
            "hook_1C97_0000": read_memory(gdb, HOOK_LINEAR, 6).hex(),
            "callback_1AA3_0383": read_memory(gdb, base + 0x0383, 5).hex(),
            "stack_limit_0A76": word(gdb, base + 0x0A76),
            "loaded_flags": {index_of(DIRECTORY + i * RECORD) + 2:
                             read_memory(gdb, base + DIRECTORY + i * RECORD + 7, 1).hex()
                             for i in range(70)},
        }
        qmp.hmp(f"screendump {(OUT / 'rtlink_dispatch_trace_end.ppm').as_posix()}")
    except (ConnectionError, OSError, socket.timeout) as exc:
        print(f"trace ended with guest disconnect: {exc}")
    finally:
        out.write_text(json.dumps({"false_hits": false_hits, "final": final,
                                   "events": events}, indent=2) + "\n")
        kinds = {k: sum(e["kind"] == k for e in events)
                 for k in ("load", "evict", "save", "restore")}
        print(f"{kinds}, {false_hits} false hits -> {out}")
        for obj in (gdb, qmp):
            if obj is not None:
                obj.close()
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
