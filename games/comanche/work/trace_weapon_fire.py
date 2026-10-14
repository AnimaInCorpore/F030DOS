#!/usr/bin/env python3
r"""The original's weapon launches during a replay, one row per shot.

Stops at 0001922E, the `call eax` into the weapon handler table at
[0x19D68 + 4*[0x19D88]], and again at 00019230, the instruction after it.
Between the two the handler has claimed a slot, so diffing the active bytes
at 0x21921 names the slot. Each row records the replay cursor, the page, the
gating bytes the handlers read, and every field the launchers write.

    python3 work/trace_weapon_fire.py --records 284 --out work/replay_dos/weapon-demo1.json

N/A - target artefact: an oracle probe, no DOS routine.
"""
import argparse
import json
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import Qmp, default_hdd, QEMU
from rsp import Rsp
from dump_marcher_tables import linear, wait_for_program
from trace_replay_flight import REPLAY_ARMED, DEMO_NAME, read_block

CALL = 0x0001922E
AFTER = 0x00019230
ACTIVE = 0x21921
LONG_FIELDS = {"speed_1FE34": 0x1FE34, "draw_2003C": 0x2003C,
               "state_20244": 0x20244, "bank_2044C": 0x2044C,
               "x_20C6C": 0x20C6C, "y_20E74": 0x20E74,
               "prev_x_2107C": 0x2107C, "prev_y_21284": 0x21284,
               "vrate_2148C": 0x2148C, "alt824_21694": 0x21694}
BYTE_FIELDS = {"heading_2189F": 0x2189F, "sprite_219A3": 0x219A3,
               "alt_21A25": 0x21A25, "target_21D31": 0x21D31,
               "aux_21DB3": 0x21DB3, "timer_21E35": 0x21E35}
GLOBALS = {"page_19D88": (0x19D88, 1), "latch_19D10": (0x19D10, 1),
           "gate_19E3B": (0x19E3B, 1), "mode_19DB8": (0x19DB8, 1),
           "rail_22880": (0x22880, 4), "rock_19D30": (0x19D30, 4),
           "hell_19D34": (0x19D34, 4), "cursor_19ECC": (0x19ECC, 4),
           "trig1_19DF2": (0x19DF2, 1), "sound_19DF9": (0x19DF9, 1),
           "variant_19D86": (0x19D86, 1), "alt_19DFC": (0x19DFC, 1),
           "angle_19D04": (0x19D04, 4), "pitch_19CF4": (0x19CF4, 4)}


def u(gdb, addr, size, signed=False):
    raw = read_block(gdb, linear(addr), size)
    return int.from_bytes(raw, "little", signed=signed) if raw else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--records", type=int, default=284)
    ap.add_argument("--wait", type=float, default=240.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = int(os.environ.get("QMP_PORT", 4667))
    gport = int(os.environ.get("GDB_PORT", 4668))
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,snapshot=on",
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
           "-gdb", f"tcp:127.0.0.1:{gport}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    rows = []
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, proc, args.wait):
            return 1
        gdb = Rsp(gport, timeout=args.wait)
        gdb.set_break(linear(REPLAY_ARMED))
        if gdb.cont_until_stop() is None:
            return 1
        gdb.clear_break(linear(REPLAY_ARMED))
        stream = (read_block(gdb, linear(DEMO_NAME), 10) or b"").split(b"\0")[0].decode()
        start = {k: u(gdb, a, s) for k, (a, s) in GLOBALS.items()}
        print(f"  armed {stream}; globals at arm: {start}")
        call, after = linear(CALL), linear(AFTER)
        gdb.set_break(call)
        first = True
        limit = args.records * 8 + 13
        while True:
            stop = gdb.cont_until_stop() if first else gdb.cont_from_break(call)
            first = False
            if stop is None:
                break
            cursor = u(gdb, 0x19ECC, 4)
            if cursor is None or cursor > limit:
                break
            before = read_block(gdb, linear(ACTIVE), 0x83)
            row = {k: u(gdb, a, s) for k, (a, s) in GLOBALS.items()}
            row["handler"] = u(gdb, 0x19D68 + 4 * row["page_19D88"], 4)
            gdb.clear_break(call)
            gdb.set_break(after)
            gdb.cont_until_stop()
            gdb.clear_break(after)
            gdb.set_break(call)
            now = read_block(gdb, linear(ACTIVE), 0x83)
            new = [i for i in range(0x83) if now[i] and not before[i]]
            row["new_slots"] = new
            row["after"] = {k: u(gdb, a, s) for k, (a, s) in GLOBALS.items()}
            if new:
                # The launchers scan from 0x82 = 130, one past each 130-entry
                # array, so "slot 130" writes element 0 of the NEXT array and
                # makes index 0 look newly active too. The claimed slot is the
                # highest new index; reading its fields through the same
                # out-of-range addresses gives exactly what the handler wrote.
                s = max(new)
                row["slot"] = {k: u(gdb, a + 4 * s, 4) for k, a in LONG_FIELDS.items()}
                row["slot"].update({k: u(gdb, a + s, 1) for k, a in BYTE_FIELDS.items()})
            rows.append(row)
            print(f"  cursor {cursor} page {row['page_19D88']} handler "
                  f"{row['handler']:#x} slots {new} gate {row['gate_19E3B']} "
                  f"mode {row['mode_19DB8']:#x} rail {row['rail_22880']:#x}")
        gdb.close()
    finally:
        proc.kill()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"stream": stream, "globals_at_arm": start, "rows": rows}, f, indent=1)
    print(f"  wrote {len(rows)} shots -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
