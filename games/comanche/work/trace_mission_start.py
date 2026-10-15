#!/usr/bin/env python3
r"""Any mission's starting state on the original, for every campaign.

Drives the shipped game into a mission the way work/trace_mission_live.py
does (Esc, then Return up to Accept), but chooses the mission itself instead
of taking the one the roster opens on:

  00028F3A  after campaign select, before 0002A1AD reads that campaign's file:
            the pilot's campaign byte [00029702 + pilot] is set to the index
            whose digit ([00029D47 + i]) is --campaign;
  00028FBA  after the row colours: every row is made flown ('b'), so the
            00029016 lock test passes whatever the roster says;
  00029038  after the lock test, before the briefing parse: [0002975A], the
            mission the parse reads at 00029086/000290A9, is set to --mission.

It then stops at the end of the mission's first object pass (000234CE with
[0x19ED4] clear: 000069CC's frame_driver call, after 000068A5's object factory
and 0000694D's start altitude, before anything is drawn) and dumps the player's mission scalars, the 31 object slots field by
field, the palette source, and digests of the height and colour maps.

    python3 work/trace_mission_start.py --campaign 0 --mission 7 --out work/replay_dos/start-c0m7.json

N/A - target artefact: an oracle probe, no DOS routine.
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import Qmp, default_hdd, QEMU
from rsp import Rsp
from dump_marcher_tables import linear, wait_for_program
from trace_replay_flight import read_block, write_block, read_regs
from trace_mission_live import KEYS
from trace_replay_flight import OBJECT_UPDATE_DONE

CAMPAIGN_SET = 0x00028F3A
INK_DONE = 0x00028FBA
MISSION_SET = 0x00029038
PASS_START = 0x000234A4

# Per-slot arrays, indexed by the 1-based slot (31 is the fixed object).
BYTES = {"heading": 0x2189F, "active": 0x21921, "sprite": 0x219A3, "alt": 0x21A25,
         "damage": 0x21B29, "aux": 0x21DB3, "steer": 0x21EB7, "flag": 0x21F39,
         "variant": 0x21F57, "f9": 0x21F75, "health": 0x21F93, "timer": 0x21E35,
         "prev_alt": 0x21AA7}
DWORDS = {"speed": 0x1FE34, "draw": 0x2003C, "state": 0x20244, "model_a": 0x2044C,
          "model_b": 0x20654, "x": 0x20C6C, "y": 0x20E74, "prev_x": 0x2107C,
          "prev_y": 0x21284, "fire": 0x21FB0, "hold": 0x22028}
SCALARS = {"x": (0x19CD4, "<I"), "y": (0x19CD8, "<I"), "alt": (0x19DFC, "<B"),
           "fuel": (0x19D5C, "<i"), "fuel_live": (0x19D60, "<i"),
           "chaff": (0x19D8D, "<B"), "flare": (0x19D8E, "<B"),
           "wounded": (0x19E40, "<i"), "wounded_max": (0x19E44, "<i"),
           "stars": (0x2824B, "<B"), "targets": (0x28260, "<B"),
           "page": (0x19D88, "<B"), "objects": (0x19D64, "<I"),
           "frame_x": (0x19CDC, "<I"), "frame_y": (0x19CE0, "<I"),
           "rng": (0x19DB8, "<I"),
           "pub_sin": (0x19CB8, "<i"), "pub_cos": (0x19CBC, "<i"), "angle": (0x19D04, "<I")}


def read_big(gdb, addr, size, chunk=0x800):
    out = bytearray()
    while len(out) < size:
        n = min(chunk, size - len(out))
        b = read_block(gdb, addr + len(out), n)
        if b is None:
            return None
        out += b
    return bytes(out)


def slot_fields(gdb):
    objs = {k: list(read_block(gdb, linear(a), 32)) for k, a in BYTES.items()}
    for k, a in DWORDS.items():
        objs[k] = list(struct.unpack("<32I", read_block(gdb, linear(a), 128)))
    return objs


def dump(gdb):
    st = {}
    for k, (a, f) in SCALARS.items():
        st[k] = struct.unpack(f, read_block(gdb, linear(a), struct.calcsize(f)))[0]
    st["loads"] = list(struct.unpack("<6i", read_block(gdb, linear(0x19D44), 24)))
    st["ammo"] = list(struct.unpack("<6i", read_block(gdb, linear(0x19D2C), 24)))
    st["damage_table"] = list(read_block(gdb, linear(0x19E38), 8))
    st["sprite_slots"] = list(struct.unpack("<10I", read_block(gdb, linear(0x19EA4), 40)))
    st["objects_by_field"] = slot_fields(gdb)
    st["palette_raw"] = read_block(gdb, linear(0x2A380), 768).hex()
    for name, ptr in (("height", 0x19E6C), ("colour", 0x19E68)):
        base = struct.unpack("<I", read_block(gdb, linear(ptr), 4))[0]
        raw = read_big(gdb, linear(base), 0x100000)
        st[f"{name}_sha1"] = hashlib.sha1(raw).hexdigest() if raw else None
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--campaign", type=int, required=True, help="the file digit, 0 or 1")
    ap.add_argument("--mission", type=int, required=True, help="0-based row")
    ap.add_argument("--wait", type=float, default=300.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
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
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, proc, args.wait):
            return 1
        lock = threading.Lock()
        stop_keys = threading.Event()

        def keys():
            # The schedule, then a Return every six seconds until the flight
            # starts: a key that lands while a menu is still drawing is lost.
            sched = list(KEYS) + [(KEYS[-1][0] + 6 * i, "ret") for i in range(1, 8)]
            for when, key in sched:
                delay = t0 + when - time.time()
                if delay > 0:
                    time.sleep(delay)
                if stop_keys.is_set():
                    return
                with lock:
                    qmp.hmp(f"sendkey {key}")
        threading.Thread(target=keys, daemon=True).start()

        gdb = Rsp(gport, timeout=args.wait)
        flight = linear(OBJECT_UPDATE_DONE)
        # The object pass runs every attract frame too; it is armed only once
        # the mission is chosen.
        points = [linear(CAMPAIGN_SET), linear(INK_DONE), linear(MISSION_SET)]
        for p in points:
            gdb.set_break(p)
        seen = []
        last = None
        while True:
            stop = gdb.cont_until_stop() if last is None else gdb.cont_from_break(last)
            if stop is None:
                print(f"  [{time.time() - t0:5.1f}s] never reached the mission object pass (last stop {last:x}, reply {stop!r})")
                return 1
            eip = read_regs(gdb)["eip"]
            here = linear(eip)
            attract = read_block(gdb, linear(0x19ED4), 1) != b"\x00"
            last = here
            if here == linear(CAMPAIGN_SET):
                pilot = read_block(gdb, linear(0x29701), 1)[0]
                digits = read_block(gdb, linear(0x29D47), 10)
                idx = digits.find(bytes([0x30 + args.campaign]))
                if idx < 0:
                    print(f"  campaign {args.campaign} not in the catalog {digits!r}")
                    return 1
                write_block(gdb, linear(0x29702 + pilot), bytes([idx]))
                seen.append(f"campaign pilot={pilot} index={idx}")
            elif here == linear(INK_DONE):
                write_block(gdb, linear(0x29F22), b"b" * 10)
                seen.append("ink")
            elif here == linear(PASS_START) and not attract:
                # The Timer C PRNG the pass's jitter branches read: what it
                # holds as the pass begins, for the port to start from.
                pre["rng"] = struct.unpack("<I", read_block(gdb, linear(0x19DB8), 4))[0]
                gdb.clear_break(linear(PASS_START))
                seen.append("pass start")
                last = None
            elif here in (linear(MISSION_SET), linear(PASS_START), flight) and attract:
                seen.append("attract parse")
            elif here == linear(MISSION_SET):
                write_block(gdb, linear(0x2975A), bytes([args.mission]))
                seen.append("mission")
                # What the slots and the heading sine/cosine hold before the
                # factory runs: left over from the attract, and read by the
                # first object pass wherever the factory does not write.
                pre = slot_fields(gdb)
                pre["pub_sin"], pre["pub_cos"] = struct.unpack("<2i", read_block(gdb, linear(0x19CB8), 8))
                gdb.set_break(linear(PASS_START))
                gdb.set_break(flight)
            elif here == flight:
                break
            else:
                print(f"  unexpected stop at {here:08x}")
                return 1
            print(f"  [{time.time() - t0:5.1f}s] {seen[-1]}")
        stop_keys.set()
        print(f"  [{time.time() - t0:5.1f}s] first mission object pass")
        state = dump(gdb)
        state["campaign"], state["mission"], state["route"] = args.campaign, args.mission, seen
        state["pre"] = pre
        gdb.close()
    finally:
        proc.kill()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
