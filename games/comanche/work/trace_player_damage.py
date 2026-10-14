#!/usr/bin/env python3
r"""The original's player damage and death chain, captured at instructions.

A replay is running; at a chosen cursor the probe changes the player's damage
state through the gdbstub and records what the flight handler does with it, one
row per event. Breakpoints:

  00019555  end of the flight tick (the instruction after the movement core)
  00019424  a crash begins: position and altitude are about to be restored
  0001947B  the crash's damage tail (00019424's bounce is done)
  000194E0  the movement core: the crash's damage is done
  0002873D  the flight ended (the wreck's countdown reached zero)

Scenarios (--scenario):

  wreck    [00019E49] = 1, [00019E48] = 0x64, hull [00019E40] = -1 at --from:
           the death block 00018EE3 with the rotor stopped
  sinking  the same with the hull left alone (positive): the sinking wreck
  crash    from --from, [00019DFC] is forced to 0 at the end of every tick for
           --ticks ticks, so every following tick meets the ground: each crash
           gives a 00019424 / 0001947B / 000194E0 triple with the RNG the tail
           really used
  engine   from --from, damage cells [00019E39] (engine) and [00019E38] (tail
           rotor) are set to 0xFF: the damaged-engine cap 00018F94 and the
           tail-rotor yaw 000190AB
  collide  from --from, at 000192EE (the start of the collision test against the
           thirty mission objects) the player's position and altitude are set to
           a sample offset from one active mission object; the next stop is
           00019424 when the original found a collision and 00019352 when not.
           The samples sweep the box edges (|dx|, |dy| around 0x1400000) and the
           altitude difference (around 0x1F/0x20 each way)

The game runs on a snapshot of the disk image: nothing is written back to it.

    python3 work/trace_player_damage.py --scenario wreck --skip 1 --from 400 \
        --out work/replay_dos/damage-wreck.json

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
from trace_replay_flight import (REPLAY_ARMED, DEMO_NAME, DEMO_DIGIT, read_block,
                                 write_block, read_regs)

FLIGHT_TICK_DONE = 0x00019555
CRASH_ENTRY = 0x00019424
DAMAGE_TAIL = 0x0001947B
CORE = 0x000194E0
MISSION_END = 0x0002873D

# One window over the flight and damage state: 00019CC8 .. 00019F08.
BASE = 0x19CC8
SPAN = 0x240
FIELDS = {
    "fwd_19CC8": (0x19CC8, "i"), "maxspd_19CCC": (0x19CCC, "i"),
    "lat_19CD0": (0x19CD0, "i"), "x_19CD4": (0x19CD4, "i"),
    "y_19CD8": (0x19CD8, "i"), "frame_x_19CDC": (0x19CDC, "i"),
    "frame_y_19CE0": (0x19CE0, "i"), "roll_19CF0": (0x19CF0, "i"),
    "pitch_19CF4": (0x19CF4, "i"), "angle_19D04": (0x19D04, "I"),
    "turn_19D08": (0x19D08, "i"), "collective_19D82": (0x19D82, "B"),
    "collective_prev_19D83": (0x19D83, "B"), "torque_19D84": (0x19D84, "B"),
    "variant_19D86": (0x19D86, "B"),
    "rng_19DB8": (0x19DB8, "I"), "phase_19DBC": (0x19DBC, "i"),
    "countdown_19DC0": (0x19DC0, "i"), "drop_19DC4": (0x19DC4, "I"),
    "axis1_19DC8": (0x19DC8, "i"), "axis2_19DCC": (0x19DCC, "i"),
    "prevalt_19DF6": (0x19DF6, "B"), "alt_19DFC": (0x19DFC, "B"),
    "cell0_19E38": (0x19E38, "B"), "cell1_19E39": (0x19E39, "B"),
    "cell2_19E3A": (0x19E3A, "B"), "cell3_19E3B": (0x19E3B, "B"),
    "cell4_19E3C": (0x19E3C, "B"), "cell5_19E3D": (0x19E3D, "B"),
    "cell6_19E3E": (0x19E3E, "B"), "cell7_19E3F": (0x19E3F, "B"),
    "hull_19E40": (0x19E40, "i"), "hull_max_19E44": (0x19E44, "i"),
    "timer_19E48": (0x19E48, "B"), "cue_19E49": (0x19E49, "B"),
    "cursor_19ECC": (0x19ECC, "I"), "replay_19ED0": (0x19ED0, "I"),
}
ACTIVE = 0x21921
STATE = 0x20244
OBJECT_ALT = 0x21A25
OBJECT_X = 0x20C6C
OBJECT_Y = 0x20E74
SLOTS = 131


def snapshot(gdb):
    raw = read_block(gdb, linear(BASE), SPAN)
    if raw is None:
        raise RuntimeError("memory read refused")
    row = {}
    for name, (addr, code) in FIELDS.items():
        off = addr - BASE
        row[name] = raw[off] if code == "B" else struct.unpack_from("<" + code, raw, off)[0]
    active = read_block(gdb, linear(ACTIVE), SLOTS)
    states = read_block(gdb, linear(STATE), SLOTS * 4)
    row["wreck_puffs"] = sum(
        1 for slot in range(31, SLOTS)
        if active and active[slot] and struct.unpack_from("<I", states, slot * 4)[0] == 0x237B0)
    row["active_transients"] = sum(1 for slot in range(31, SLOTS) if active and active[slot])
    return row


def poke(gdb, address, value, code):
    write_block(gdb, linear(address), struct.pack("<" + code, value))


COLLIDE_LOOP = 0x000192EE       # ebx = 0x1E: the collision test over the mission objects
AFTER_COLLIDE = 0x00019352      # the loop's fall-through: the terrain follow begins
BOX = 0x1400000
# (dx, dy, da): the player's offset from the chosen object, da = altitude difference
SAMPLES = (
    [(d, 0, 0) for d in (0, 1, -1, BOX - 1, BOX, BOX + 1, BOX + 2,
                         -(BOX - 1), -BOX, -(BOX + 1), -(BOX + 2))]
    + [(0, d, 0) for d in (BOX - 1, BOX, BOX + 1, BOX + 2,
                           -(BOX - 1), -BOX, -(BOX + 1), -(BOX + 2))]
    + [(0, 0, d) for d in (-0x22, -0x21, -0x20, -0x1F, -0x1E, -1, 1,
                           0x1D, 0x1E, 0x1F, 0x20, 0x21)]
    + [(BOX, BOX, 0), (-BOX, -BOX, 0), (BOX + 1, BOX + 1, 0), (-(BOX + 1), -(BOX + 1), 0),
       (BOX, -BOX, 0x1F), (-BOX, BOX, -0x20)]
)


def object_table(gdb):
    """Slots 0..30 as the collision test reads them."""
    active = read_block(gdb, linear(ACTIVE), 31)
    altitude = read_block(gdb, linear(OBJECT_ALT), 31)
    xs = struct.unpack("<31i", read_block(gdb, linear(OBJECT_X), 31 * 4))
    ys = struct.unpack("<31i", read_block(gdb, linear(OBJECT_Y), 31 * 4))
    states = struct.unpack("<31I", read_block(gdb, linear(STATE), 31 * 4))
    return [{"slot": slot, "active": active[slot], "altitude": altitude[slot],
             "x": xs[slot], "y": ys[slot], "state": states[slot]} for slot in range(31)]


def run_collide(gdb, args, result):
    """At every 000192EE from --from, set the player at a sample offset from
    one active mission object and see which way the original goes."""
    watched = {COLLIDE_LOOP: "collide", AFTER_COLLIDE: "terrain", CRASH_ENTRY: "crash"}
    for address in watched:
        gdb.set_break(linear(address))
    samples = []
    result["samples"] = samples
    pending = None
    last = None
    index = 0
    started = False
    while index < len(SAMPLES) or pending:
        stop = gdb.cont_until_stop() if last is None else gdb.cont_from_break(linear(last))
        if stop is None:
            print("  no further stop")
            break
        regs = read_regs(gdb)
        eip = regs["eip"] if regs else None
        last = eip
        kind = watched.get(eip)
        if kind is None:
            last = None
            continue
        if pending:
            # the first stop after the loop was entered decides it
            pending["outcome"] = "collision" if kind == "crash" else "none"
            samples.append(pending)
            pending = None
            if kind == "crash":
                # the crash path continues; wait for the next loop entry
                pass
            if kind != "collide":
                continue
        if kind != "collide":
            continue
        cursor = int.from_bytes(read_block(gdb, linear(0x19ECC), 4), "little")
        if not started:
            if cursor < args.start:
                continue
            started = True
            result["poked_at_cursor"] = cursor
        table = object_table(gdb)
        # an active mission object, not an explosion, with room for the altitude sweep
        choices = [o for o in table[1:] if o["active"] and o["state"] != 0x237B0
                   and 0x30 <= o["altitude"] <= 0xB0]
        if not choices:
            continue
        target = choices[0]
        dx, dy, da = SAMPLES[index]
        index += 1
        px = (target["x"] + dx + (1 << 31)) % (1 << 32) - (1 << 31)
        py = (target["y"] + dy + (1 << 31)) % (1 << 32) - (1 << 31)
        pa = target["altitude"] + da
        poke(gdb, 0x19CD4, px, "i")
        poke(gdb, 0x19CD8, py, "i")
        poke(gdb, 0x19DFC, pa, "B")
        pending = {"cursor": cursor, "slot": target["slot"], "dx": dx, "dy": dy, "da": da,
                   "player": {"x": px, "y": py, "altitude": pa}, "objects": table}
    return len(samples)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdd", default=default_hdd())
    parser.add_argument("--scenario", required=True,
                        choices=["wreck", "sinking", "crash", "engine", "collide"])
    parser.add_argument("--skip", type=int, default=0,
                        help="trace the Nth replay arm (the attract cycles demo1, demo2, demo3, demo0)")
    parser.add_argument("--from", dest="start", type=int, required=True,
                        help="replay cursor [00019ECC] at which the poke is made")
    parser.add_argument("--ticks", type=int, default=60)
    parser.add_argument("--wait", type=float, default=240.0)
    parser.add_argument("--out", required=True)
    parser.add_argument("--screendump-drop", type=int, default=0, metavar="ROWS",
                        help="once the wreck's sunk window [00019DC4] has gone down this many "
                             "rows, write the display as a PPM beside --out (-N-<tick>.ppm), "
                             "for three consecutive ticks")
    args = parser.parse_args()
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    port = int(os.environ.get("QMP_PORT", 4687))
    gport = int(os.environ.get("GDB_PORT", 4688))
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,snapshot=on",
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
           "-gdb", f"tcp:127.0.0.1:{gport}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    events = []
    result = {"scenario": args.scenario, "from": args.start, "events": events}
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, proc, args.wait):
            return 1
        gdb = Rsp(gport, timeout=args.wait)
        armed = linear(REPLAY_ARMED)
        gdb.set_break(armed)
        for index in range(args.skip + 1):
            stop = gdb.cont_until_stop() if index == 0 else gdb.cont_from_break(armed)
            if stop is None:
                print("  the replay never armed")
                return 1
        gdb.clear_break(armed)
        result["demo_digit"] = (read_block(gdb, linear(DEMO_DIGIT), 1) or b"\0")[0]
        result["stream"] = (read_block(gdb, linear(DEMO_NAME), 10) or b"").split(b"\0")[0].decode()
        print(f"  replay armed: {result['stream']}")
        if args.scenario == "collide":
            run_collide(gdb, args, result)
        else:
            points = {FLIGHT_TICK_DONE: "tick", MISSION_END: "end"}
            if args.scenario == "crash":
                points.update({CRASH_ENTRY: "crash", DAMAGE_TAIL: "tail", CORE: "core"})
            for address in points:
                gdb.set_break(linear(address))
            poked = False
            dumps = 0
            ticks_after = 0
            unexpected = 0
            last = None
            while True:
                stop = gdb.cont_until_stop() if last is None else gdb.cont_from_break(linear(last))
                if stop is None:
                    print("  no further stop")
                    break
                regs = read_regs(gdb)
                eip = regs["eip"] if regs else None      # the stub reports the offset in the flat code segment
                last = eip
                if eip not in points:
                    # a stop that is none of ours (the stub's own, or a stale reply):
                    # run on rather than guess
                    unexpected += 1
                    print(f"  stop at {eip:#x} is not a breakpoint of ours ({stop[:40]!r}); continuing")
                    if unexpected > 20:
                        break
                    last = None
                    continue
                kind = points[eip]
                if kind == "core" and not (events and events[-1]["kind"] in ("tail", "crash")):
                    continue                    # the movement core reached without a crash
                row = snapshot(gdb)
                row["at"] = f"{eip:08X}"
                row["kind"] = kind
                events.append(row)
                if (kind == "tick" and args.screendump_drop
                        and row["drop_19DC4"] >= args.screendump_drop * 82
                        and dumps < 3):
                    path = os.path.abspath(args.out).replace(".json", f"-{args.screendump_drop}-{dumps}.ppm")
                    row["screendump"] = path
                    row["screendump_reply"] = qmp.hmp(f"screendump {path}")
                    dumps += 1
                if kind == "end":
                    print("  the flight ended")
                    break
                if kind != "tick":
                    continue
                if row["replay_19ED0"] != 1:
                    print("  the replay ended")
                    break
                if not poked and row["cursor_19ECC"] >= args.start:
                    poked = True
                    result["poked_at_cursor"] = row["cursor_19ECC"]
                    if args.scenario in ("wreck", "sinking"):
                        poke(gdb, 0x19E49, 1, "B")
                        poke(gdb, 0x19E48, 0x64, "B")
                        if args.scenario == "wreck":
                            poke(gdb, 0x19E40, 0xFFFFFFFF, "I")
                    elif args.scenario == "engine":
                        poke(gdb, 0x19E38, 0xFF, "B")
                        poke(gdb, 0x19E39, 0xFF, "B")
                elif poked:
                    ticks_after += 1
                if poked and args.scenario == "crash" and ticks_after < args.ticks:
                    poke(gdb, 0x19DFC, 0, "B")
                if ticks_after >= args.ticks:
                    break
        gdb.close()
    finally:
        proc.kill()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f)
    print(f"  {len(events)} events -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
