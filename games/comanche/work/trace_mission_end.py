#!/usr/bin/env python3
r"""The original's mission-end statistics, captured at an instruction.

A replay is running; at a chosen cursor the Alt and A slots of the key array
([0x1AA8], [0x1A8E]) are written as held, which 000189C2 turns into
`jmp 0002873D` (000189F2) - the mission-abort path. 0002873D calls the
statistics routine 00028261 at 00028772; this stops at 00028777, after it,
and dumps what it left: the counters at 0x28250-0x28260, the message and
score buffers at 0x2860B-0x286D0, the hull and fuel globals and the pilot
roster.

    python3 work/trace_mission_end.py --cursor 213 --out work/replay_dos/mission-end-r25.json

N/A - target artefact: an oracle probe, no DOS routine.
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import Qmp, default_hdd, QEMU
from rsp import Rsp
from dump_marcher_tables import linear, wait_for_program
from trace_replay_flight import (REPLAY_ARMED, DEMO_NAME, OBJECT_UPDATE_DONE,
                                 read_block, write_block)

AFTER_STATS = 0x00028777            # the instruction after `call 00028261`
KEY_ALT = 0x1AA8                    # 0x1A70 + PC scancode 0x38
KEY_A = 0x1A8E                      # 0x1A70 + PC scancode 0x1E
REGIONS = {
    "counters_28250": (0x28250, 0x20),
    "buffers_285FA": (0x285FA, 0x120),
    "score_2860B": (0x2860B, 0x20),
    "roster_29570": (0x29570, 0x5C0),
    "pilot_29B2C": (0x29ADC, 0x60),
    "globals_19D2C": (0x19D2C, 0x40),
    "globals_19D5C": (0x19D5C, 0x10),
    "hull_19E40": (0x19E40, 0x10),
    "ed4_19ED4": (0x19ED4, 0x04),
    "flag_22384": (0x22384, 0x04),
    "flag_19D91": (0x19D91, 0x04),
    "dmg_19E38": (0x19E38, 0x40),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--cursor", type=int, required=True,
                    help="[0x19ECC] value after which Alt+A is held")
    ap.add_argument("--wait", type=float, default=240.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = int(os.environ.get("QMP_PORT", 4677))
    gport = int(os.environ.get("GDB_PORT", 4678))
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,snapshot=on",
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
           "-gdb", f"tcp:127.0.0.1:{gport}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    result = {}
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, proc, args.wait):
            return 1
        gdb = Rsp(gport, timeout=args.wait)
        gdb.set_break(linear(REPLAY_ARMED))
        if gdb.cont_until_stop() is None:
            return 1
        gdb.clear_break(linear(REPLAY_ARMED))
        result["stream"] = (read_block(gdb, linear(DEMO_NAME), 10) or b"").split(b"\0")[0].decode()
        at = linear(OBJECT_UPDATE_DONE)
        gdb.set_break(at)
        first = True
        while True:
            stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
            first = False
            if stop is None:
                print("  breakpoint stopped being reached")
                return 1
            cur = int.from_bytes(read_block(gdb, linear(0x19ECC), 4), "little")
            if cur >= args.cursor:
                break
        gdb.clear_break(at)
        write_block(gdb, linear(KEY_ALT), b"\x00")
        write_block(gdb, linear(KEY_A), b"\x00")
        result["cursor"] = cur
        end = linear(AFTER_STATS)
        gdb.set_break(end)
        if gdb.cont_until_stop() is None:
            print("  00028777 never reached")
            return 1
        for name, (addr, size) in REGIONS.items():
            raw = read_block(gdb, linear(addr), size)
            result[name] = raw.hex() if raw else None
        gdb.close()
    finally:
        proc.kill()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(f"  cursor {result['cursor']}; wrote {len(result) - 2} regions -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
