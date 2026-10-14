#!/usr/bin/env python3
r"""The original's own replay flight, one row per integration tick.

The attract demos replay recorded INPUTS, not positions, so the port only
flies the authored path if every shift, clamp and damping quirk lands on the
value the original's did. A picture cannot settle that: a drift of a few
10.22 units per tick is invisible for a hundred frames and then the
helicopter is over a different hill. This reads the numbers instead.

The breakpoint is 00019555 - the instruction after the movement core at
000194E0-0001954F has written [0x19CD4]/[0x19CD8]. Every flight tick reaches
it, replay or live, and at that point the record just consumed is fully
integrated and [0x19ECC] already holds the next cursor. Capturing at an
instruction rather than an instant is the METHOD rule that took the marcher
model from 16.1% to 100.0%; the same applies here, more sharply, because the
frame driver latches, renders and only then integrates.

Reads go through the gdbstub's own `m` packet while it holds the guest, not
through QMP `xp`: one round trip per tick instead of a dozen, and no window
in which the guest could run on between fields of the same row.

    python work/trace_replay_flight.py --records 800 --out work/replay_dos/flight-dos.json

N/A - target artefact: an oracle probe, no DOS routine.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import Qmp, default_hdd, xp_bytes, QEMU, ROOT
from rsp import Rsp
from dump_marcher_tables import (FLAT, REPLAY_PLAYING, linear,
                                 read_resource_names, wait_for_program,
                                 wait_for_flight)

# 00019555, the first instruction after the movement core's four `imul`s have
# landed in [0x19CD4]/[0x19CD8].
FLIGHT_TICK_DONE = 0x00019555

# 00019A4E, the `mov [0x19ED0],1` that arms the replay. Stopping here rather
# than polling [0x19ED0] is what makes the trace start at record 0: the poll
# only notices the replay once the guest has already flown tens of records,
# and a comparison that starts mid-flight cannot tell a wrong start state
# from a drift that began before the first captured row.
REPLAY_ARMED = 0x00019A4E
# The digit 00019A34 patches into the 'demo1.scr' template at 00019A47, and
# the template itself, so the trace records WHICH stream it flew.
DEMO_DIGIT = 0x0002975A
DEMO_NAME = 0x00019A43

# 00007D7F, the first instruction after 00007D74/00007D79 have STORED the
# handler's return into [0x19CF8]/[0x19CFC]. Everything 00007D25 produces is
# settled there and nothing has consumed it: the view angle, its sin/cos pair,
# the slope/offset the backdrop walker uses, and - for variants 6 and 7 - the
# moved camera. 00007D74 looks like the right address and is one instruction
# too early: the slope/offset read there are still the PREVIOUS frame's, which
# scores a correct model as wrong on every frame the roll changed.
VIEW_BASIS_DONE = 0x00007D7F
VIEW_BASE = 0x19CB0
VIEW_SPAN = 0x150
VIEW_FIELDS = {
    "view_sin_0x19CB0":  (0x19CB0, "i"),
    "view_cos_0x19CB4":  (0x19CB4, "i"),
    "pub_sin_0x19CB8":   (0x19CB8, "i"),
    "pub_cos_0x19CBC":   (0x19CBC, "i"),
    "fwd_0x19CC8":       (0x19CC8, "i"),
    "x_0x19CD4":         (0x19CD4, "i"),
    "y_0x19CD8":         (0x19CD8, "i"),
    "frame_x_0x19CDC":   (0x19CDC, "i"),
    "frame_y_0x19CE0":   (0x19CE0, "i"),
    "cam_x_0x19CE4":     (0x19CE4, "i"),
    "cam_y_0x19CE8":     (0x19CE8, "i"),
    "roll_0x19CF0":      (0x19CF0, "i"),
    "pitch_0x19CF4":     (0x19CF4, "i"),
    "slope_0x19CF8":     (0x19CF8, "i"),
    "offset_0x19CFC":    (0x19CFC, "i"),
    "view_angle_0x19D00": (0x19D00, "I"),
    "angle_0x19D04":     (0x19D04, "I"),
    "turn_0x19D08":      (0x19D08, "i"),
    "variant_0x19D86":   (0x19D86, "B"),
    # 00001DB5-00001DE7, the timer ISR's shake. The PRNG at [0x19DB8]
    # steps every tick whether shaking or not; [0x19DC0] is the
    # countdown 00019461 arms, and [0x19DBC] is what 00007DB5 subtracts
    # from the backdrop base.
    "shake_rng_0x19DB8": (0x19DB8, "I"),
    "shake_0x19DBC":     (0x19DBC, "i"),
    "shake_left_0x19DC0": (0x19DC0, "i"),
    "cam_alt_0x19DF8":   (0x19DF8, "B"),
    "alt_0x19DFC":       (0x19DFC, "B"),
    "prevalt_0x19DF6":   (0x19DF6, "B"),
}
# Slot 31's active byte and position - variant 7 aims at it through 000256C8.
SLOT31_ACTIVE = 0x21921 + 31
SLOT31_X = 0x20C6C + 31 * 4
SLOT31_Y = 0x20E74 + 31 * 4

# One contiguous window over the whole flight state, so a row is a single
# read. Offsets are from BASE; the names are the addresses flight.s ports.
BASE = 0x19CC8
SPAN = 0x210
FIELDS = {
    "fwd_0x19CC8":      (0x19CC8, "i"),
    "maxspd_0x19CCC":   (0x19CCC, "i"),
    "lat_0x19CD0":      (0x19CD0, "i"),
    "x_0x19CD4":        (0x19CD4, "i"),
    "y_0x19CD8":        (0x19CD8, "i"),
    "frame_x_0x19CDC":  (0x19CDC, "i"),
    "frame_y_0x19CE0":  (0x19CE0, "i"),
    "roll_0x19CF0":     (0x19CF0, "i"),
    "pitch_0x19CF4":    (0x19CF4, "i"),
    "view_angle_0x19D00": (0x19D00, "I"),
    "angle_0x19D04":    (0x19D04, "I"),
    "turn_0x19D08":     (0x19D08, "i"),
    "collective_0x19D82": (0x19D82, "B"),
    "prevalt_0x19DF6":  (0x19DF6, "B"),
    "variant_0x19D86":  (0x19D86, "B"),
    "axis1_0x19DC8":    (0x19DC8, "i"),
    "axis2_0x19DCC":    (0x19DCC, "i"),
    "alt_0x19DFC":      (0x19DFC, "B"),
    "cursor_0x19ECC":   (0x19ECC, "I"),
    "replay_0x19ED0":   (0x19ED0, "I"),
}


OBJECT_FAN_DONE = 0x00024D9F

# 000234CE, the `jmp 00024B17` that ends 000234A4's update loop: every slot's
# state handler has run for this tick and nothing has drawn yet. Captured
# here the table holds exactly what the next draw pass will read, so one row
# per frame is one object-update pass, in the order the port runs it.
OBJECT_UPDATE_DONE = 0x000234CE
# The per-slot arrays 000234A4's handlers read and write: (name, base, width).
# Index is the slot number, 0..130 (131 entries - slot 130's byte aliases the
# next array's element 0, as PORTING-PLAN "Weapon fire" records).
OBJECT_SLOTS = 131
OBJECT_ARRAYS = (
    ("active",   0x21921, 1), ("heading",  0x2189F, 1),
    ("altitude", 0x21A25, 1), ("prev_alt", 0x21AA7, 1),
    ("phase",    0x21B29, 1), ("target",   0x21BAB, 1),
    ("aux",      0x21DB3, 1), ("timer",    0x21E35, 1),
    ("steer",    0x21EB7, 1), ("flag",     0x21F39, 1),
    ("variant",  0x21F57, 1), ("f9",       0x21F75, 1),
    ("health",   0x21F93, 1), ("sprite",   0x219A3, 1),
    ("speed",    0x1FE34, 4), ("x",        0x20C6C, 4),
    ("y",        0x20E74, 4), ("prev_x",   0x2107C, 4),
    ("prev_y",   0x21284, 4), ("state",    0x20244, 4),
    ("draw",     0x2003C, 4), ("hold",     0x22028, 4),
    ("fire",     0x21FB0, 4),
)
# Scalars the object handlers read or leave behind.
OBJECT_GLOBALS = (
    ("frame_x", 0x19CDC, "i"), ("frame_y", 0x19CE0, "i"),
    ("alt", 0x19DFC, "B"), ("chaf_threat", 0x19D92, "B"),
    ("bull_threat", 0x19D94, "B"), ("threat_blip", 0x19D93, "B"),
    ("flares", 0x19D8F, "B"), ("shake_rng", 0x19DB8, "I"),
    ("cursor", 0x19ECC, "I"),
    ("latch", 0x19D10, "I"), ("candidate", 0x19D18, "I"),
    ("page", 0x19D88, "B"), ("trig1", 0x19DF2, "B"), ("trig2", 0x19DF3, "B"),
)


def read_regs(gdb):
    """`g` packet: the 32-bit x86 general registers, in gdb's own order."""
    reply = gdb.cmd("g")
    if not reply or reply.startswith("E"):
        return None
    names = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi", "eip"]
    out = {}
    for index, name in enumerate(names):
        chunk = reply[index * 8:(index + 1) * 8]
        if len(chunk) < 8:
            return None
        out[name] = int.from_bytes(bytes.fromhex(chunk), "little")
    return out


def trace_object_fan(gdb, qmp, args, digit, stream, names):
    """One row per 00024D9F, which is one per object that survives the fan.

    Captured AT the store rather than after it, so the registers still hold
    the inputs the quotient was taken from: ecx is the slot, esi the lateral
    as stored at [0002085C] in 12.20, ebp the ring's B already shifted by
    00024D87, and al the v about to reach [00022365]. [00022358] carries
    (ring * 4) << 6 from 00024D06, so the ring divides straight out of it.
    """
    at = linear(OBJECT_FAN_DONE)
    if gdb.set_break(at) != "OK":
        print(f"  breakpoint at {OBJECT_FAN_DONE:#07x} refused")
        return 1
    print(f"  breakpoint armed at {OBJECT_FAN_DONE:#07x}, tracing the fan")
    rows = []
    first = True
    while len(rows) < args.records:
        stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
        first = False
        if stop is None:
            print("  breakpoint stopped being reached")
            break
        regs = read_regs(gdb)
        if regs is None:
            print("  register read refused")
            break
        raw = read_block(gdb, linear(0x22358), 4)
        ring_word = int.from_bytes(raw or b"\0\0\0\0", "little")
        lateral = regs["esi"] - (1 << 32) if regs["esi"] >= (1 << 31) else regs["esi"]
        rows.append({
            "slot": regs["ecx"],
            "lateral_0x2085C": lateral,
            "b_shifted": regs["ebp"],
            "v_0x22365": regs["eax"] & 0xff,
            "ring": ring_word >> 8,
        })
        if len(rows) % 100 == 0:
            print(f"  {len(rows)} fan columns, last slot {rows[-1]['slot']} "
                  f"v {rows[-1]['v_0x22365']}")
    gdb.clear_break(at)
    gdb.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"breakpoint": OBJECT_FAN_DONE, "demo_digit": digit,
                   "demo_stream": stream, "resources": names, "rows": rows},
                  f, indent=1)
    print(f"  wrote {len(rows)} fan columns -> {args.out}")
    return 0


def trace_objects(gdb, qmp, args, digit, stream, names):
    """One row per 000234CE: the whole object table after the update pass."""
    at = linear(OBJECT_UPDATE_DONE)
    if gdb.set_break(at) != "OK":
        print(f"  breakpoint at {OBJECT_UPDATE_DONE:#07x} refused")
        return 1
    print(f"  breakpoint armed at {OBJECT_UPDATE_DONE:#07x}, tracing objects")
    rows = []
    first = True
    while len(rows) < args.records:
        stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
        first = False
        if stop is None:
            print("  breakpoint stopped being reached")
            break
        row = {}
        failed = False
        for name, base, width in OBJECT_ARRAYS:
            raw = read_block(gdb, linear(base), OBJECT_SLOTS * width)
            if raw is None:
                failed = True
                break
            if width == 1:
                row[name] = list(raw)
            else:
                row[name] = list(struct.unpack(f"<{OBJECT_SLOTS}i", raw))
        if failed:
            print("  memory read refused")
            break
        for name, addr, code in OBJECT_GLOBALS:
            raw = read_block(gdb, linear(addr), struct.calcsize(code))
            row[name] = struct.unpack("<" + code, raw)[0] if raw else None
        rows.append(row)
        if args.poke_from is not None:
            # A held fire key on the cannon page, for the cursors in
            # [--poke-from, --poke-to): 00019D88 is the console page, 00001AA9
            # the Space slot (released = 0xFF). The stop is after the pass, and
            # [00019ECC] already names the next record, so this lands before
            # that record's weapon dispatch at 000191B6.
            cur = row["cursor"]
            if args.poke_from <= cur < args.poke_to:
                write_block(gdb, linear(0x19D88), b"\x00")
                write_block(gdb, linear(0x1AA9), b"\x00")
            elif cur == args.poke_to:
                write_block(gdb, linear(0x19D88), bytes([args.poke_page]))
                write_block(gdb, linear(0x1AA9), b"\xff")
        if len(rows) % 50 == 0:
            print(f"  {len(rows)} update passes, cursor {row['cursor']}")
    gdb.clear_break(at)
    gdb.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"breakpoint": OBJECT_UPDATE_DONE, "skip": args.skip,
                   "demo_digit": digit, "demo_stream": stream,
                   "resources": names, "rows": rows}, f)
    print(f"  wrote {len(rows)} object passes -> {args.out}")
    return 0


SPRITE_TAIL = 0x000253CD


def trace_sprites(gdb, qmp, args, digit, stream, names):
    """One row per entry to 000253CD, the scaled-sprite blit every object draw
    ends in: the slot (ecx), and the byte/dword parameters the caller left in
    [00022364] frame, [00022365] column v, [00022366] page row, [00022354]
    scale index, [00022358] occlusion pointer, [0002236C] model, plus the
    cursor so a row can be joined to the port's own call."""
    at = linear(SPRITE_TAIL)
    if gdb.set_break(at) != "OK":
        print(f"  breakpoint at {SPRITE_TAIL:#07x} refused")
        return 1
    print(f"  breakpoint armed at {SPRITE_TAIL:#07x}, tracing sprite draws")
    rows = []
    first = True
    last_cursor = -1
    while True:
        stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
        first = False
        if stop is None:
            break
        regs = read_regs(gdb)
        raw = read_block(gdb, linear(0x22354), 0x40)
        cur = read_block(gdb, linear(0x19ECC), 4)
        if regs is None or raw is None or cur is None:
            print("  read refused")
            break
        cursor = int.from_bytes(cur, "little")
        row = {
            "cursor": cursor, "slot": regs["ecx"],
            "frame_22364": raw[0x22364 - 0x22354], "v_22365": raw[0x22365 - 0x22354],
            "row_22366": raw[0x22366 - 0x22354],
            "scale_22354": struct.unpack_from("<I", raw, 0)[0],
            "model_2236c": struct.unpack_from("<I", raw, 0x2236C - 0x22354)[0],
            "aspect_2237d": raw[0x2237D - 0x22354], "bias_2237f": raw[0x2237F - 0x22354],
            "eax": regs["eax"], "edi": regs["edi"], "esi": regs["esi"],
        }
        extra = read_block(gdb, linear(0x19DF0), 0x10)
        row["alt_19DFC"] = extra[0x19DFC - 0x19DF0] if extra else None
        row["prevalt_19DF6"] = extra[0x19DF6 - 0x19DF0] if extra else None
        slot_alt = read_block(gdb, linear(0x21A25 + regs["ecx"]), 1)
        row["slot_alt"] = slot_alt[0] if slot_alt else None
        rows.append(row)
        last_cursor = max(last_cursor, cursor)
        if cursor > args.records * 8 + 13:
            break
    gdb.clear_break(at)
    gdb.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"breakpoint": SPRITE_TAIL, "demo_digit": digit,
                   "demo_stream": stream, "resources": names, "rows": rows}, f)
    print(f"  wrote {len(rows)} sprite draws -> {args.out}")
    return 0


def trace_peek(gdb, qmp, args, digit, stream, names):
    """Stop at --peek-at once [00019ECC] reaches --peek-cursor and write
    --peek-len bytes from --peek-addr (linear flat addresses)."""
    at = linear(args.peek_at)
    if gdb.set_break(at) != "OK":
        print(f"  breakpoint at {args.peek_at:#07x} refused")
        return 1
    first = True
    while True:
        stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
        first = False
        if stop is None:
            print("  breakpoint stopped being reached")
            return 1
        cur = read_block(gdb, linear(0x19ECC), 4)
        if cur is not None and int.from_bytes(cur, "little") >= args.peek_cursor:
            args.peek_hit -= 1
            if args.peek_hit <= 0:
                break
    raw = read_block(gdb, linear(args.peek_addr), args.peek_len)
    gdb.clear_break(at)
    gdb.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(raw or b"")
    print(f"  wrote {len(raw or b'')} bytes at {args.peek_addr:#x} (cursor "
          f"{int.from_bytes(cur, 'little')}) -> {args.out}")
    return 0


def trace_regs(gdb, qmp, args, digit, stream, names):
    """One row per stop at --peek-at while [00019ECC] == --peek-cursor: the
    x86 registers and the blitter's own bytes ([00022364] frame, [00022365] v,
    [00022366] page row, [0002237C] start row, [00022354] scale, [0002237E])."""
    at = linear(args.peek_at)
    if gdb.set_break(at) != "OK":
        print(f"  breakpoint at {args.peek_at:#07x} refused")
        return 1
    rows = []
    first = True
    while True:
        stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
        first = False
        if stop is None:
            break
        cur = int.from_bytes(read_block(gdb, linear(0x19ECC), 4) or b"\0", "little")
        if cur > args.peek_cursor:
            break
        if cur != args.peek_cursor:
            continue
        regs = read_regs(gdb)
        blk = read_block(gdb, linear(0x22354), 0x40) or b"\0" * 0x40
        rows.append({"cursor": cur, "regs": regs,
                     "scale_22354": struct.unpack_from("<I", blk, 0)[0],
                     "frame_22364": blk[0x10], "v_22365": blk[0x11],
                     "row_22366": blk[0x12], "start_2237C": blk[0x28],
                     "noshear_2237E": blk[0x2A], "bias_2237F": blk[0x2B],
                     "model_2236C": struct.unpack_from("<I", blk, 0x18)[0]})
    gdb.clear_break(at)
    gdb.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"at": args.peek_at, "rows": rows}, f)
    print(f"  wrote {len(rows)} stops -> {args.out}")
    return 0


MARK_TEST = 0x00024DA4


def trace_marks(gdb, qmp, args, digit, stream, names):
    """One row per entry to 00024DA4 (the targetability test), up to the
    cursor --peek-cursor: slot, column v [00022365], page row [00022366], the
    column's shear byte [0x3CB20 + v], the silhouette byte at [00022358] + v,
    and the candidate and latch words afterwards."""
    at = linear(MARK_TEST)
    if gdb.set_break(at) != "OK":
        print(f"  breakpoint at {MARK_TEST:#07x} refused")
        return 1
    rows = []
    first = True
    while True:
        stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
        first = False
        if stop is None:
            break
        regs = read_regs(gdb)
        cur = int.from_bytes(read_block(gdb, linear(0x19ECC), 4) or b"\0", "little")
        if cur > args.peek_cursor:
            break
        blk = read_block(gdb, linear(0x22358), 0x10)
        sil_ptr = struct.unpack_from("<I", blk, 0)[0] if blk else 0
        v = (read_block(gdb, linear(0x22365), 1) or b"\0")[0]
        row = (read_block(gdb, linear(0x22366), 1) or b"\0")[0]
        shear = (read_block(gdb, linear(0x3CB20 + v), 1) or b"\0")[0]
        sil = (read_block(gdb, linear(sil_ptr + v), 1) or b"\0")[0] if sil_ptr else None
        dep = read_block(gdb, linear(0x20A64 + 4 * regs["ecx"]), 4)
        lat = read_block(gdb, linear(0x2085C + 4 * regs["ecx"]), 4)
        rows.append({"cursor": cur, "slot": regs["ecx"], "v": v, "row": row,
                     "shear": shear, "sil": sil, "sil_ptr": sil_ptr,
                     "eax": regs["eax"],
                     "depth": struct.unpack("<i", dep)[0] if dep else None,
                     "lateral": struct.unpack("<i", lat)[0] if lat else None})
    gdb.clear_break(at)
    gdb.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"breakpoint": MARK_TEST, "rows": rows}, f)
    print(f"  wrote {len(rows)} targetability tests -> {args.out}")
    return 0


RING_STEP = 0x0000D9D9


def trace_rings(gdb, qmp, args, digit, stream, names):
    """One row per ring of the terrain walk in the iteration whose cursor
    [00019ECC] equals --peek-cursor: at 0000D9D9 edi/ebx hold the ring's centre
    (the position accumulators after 0000D9A8/0000D9B7) and esi/ebp the
    lateral step (B*sin, B*cos), ecx the ring index. Registers are read AT the
    instruction, so they are the values the marcher uses."""
    at = linear(RING_STEP)
    if gdb.set_break(at) != "OK":
        print(f"  breakpoint at {RING_STEP:#07x} refused")
        return 1
    rows = []
    first = True
    while True:
        stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
        first = False
        if stop is None:
            break
        cur = int.from_bytes(read_block(gdb, linear(0x19ECC), 4) or b"\0", "little")
        if cur > args.peek_cursor:
            break
        if cur != args.peek_cursor:
            continue
        regs = read_regs(gdb)
        rows.append({"cursor": cur, "ring": regs["ecx"], "x": regs["edi"],
                     "y": regs["ebx"], "step_sin": regs["esi"],
                     "step_cos": regs["ebp"]})
    basis = read_block(gdb, linear(0x19CB0), 8) or b"\0" * 8
    camera = read_block(gdb, linear(0x19CD4), 8) or b"\0" * 8
    gdb.clear_break(at)
    gdb.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"breakpoint": RING_STEP, "basis_19CB0": list(struct.unpack("<II", basis)),
                   "camera_19CD4": list(struct.unpack("<II", camera)), "rows": rows}, f)
    print(f"  wrote {len(rows)} ring rows -> {args.out}")
    return 0


def write_block(gdb, addr, data):
    """RSP `M`: write `data` at the linear address `addr` while the guest is held."""
    reply = gdb.cmd(f"M{addr:x},{len(data):x}:{data.hex()}")
    if reply != "OK":
        raise RuntimeError(f"memory write refused: {reply!r}")


def read_block(gdb, addr, count):
    """`m` packet: hex bytes, or None when the stub refuses the range."""
    reply = gdb.cmd(f"m{addr:x},{count:x}")
    if not reply or reply.startswith("E") or len(reply) < count * 2:
        return None
    return bytes.fromhex(reply[:count * 2])


def decode_row(raw):
    row = {}
    for name, (addr, code) in FIELDS.items():
        off = addr - BASE
        if code == "B":
            row[name] = raw[off]
        else:
            row[name] = struct.unpack_from("<" + code, raw, off)[0]
    return row


def trace_view_basis(gdb, qmp, args, digit, stream, names):
    """One row per 00007D25 call, which is one per rendered frame."""
    at = linear(VIEW_BASIS_DONE)
    if gdb.set_break(at) != "OK":
        print(f"  breakpoint at {VIEW_BASIS_DONE:#07x} refused")
        return 1
    print(f"  breakpoint armed at {VIEW_BASIS_DONE:#07x}, tracing the basis")
    rows = []
    first = True
    while len(rows) < args.records:
        stop = gdb.cont_until_stop() if first else gdb.cont_from_break(at)
        first = False
        if stop is None:
            print("  breakpoint stopped being reached")
            break
        raw = read_block(gdb, linear(VIEW_BASE), VIEW_SPAN)
        if raw is None:
            print("  memory read refused")
            break
        row = {}
        for name, (addr, code) in VIEW_FIELDS.items():
            off = addr - VIEW_BASE
            row[name] = (raw[off] if code == "B"
                         else struct.unpack_from("<" + code, raw, off)[0])
        cursor = read_block(gdb, linear(0x19ECC), 4)
        row["cursor_0x19ECC"] = int.from_bytes(cursor or b"\0", "little")
        row["slot31_active"] = (read_block(gdb, linear(SLOT31_ACTIVE), 1)
                                or b"\0")[0]
        pos = read_block(gdb, linear(SLOT31_X), 4)
        row["slot31_x"] = struct.unpack("<i", pos)[0] if pos else None
        pos = read_block(gdb, linear(SLOT31_Y), 4)
        row["slot31_y"] = struct.unpack("<i", pos)[0] if pos else None
        rows.append(row)
        if len(rows) % 100 == 0:
            print(f"  {len(rows)} frames, variant "
                  f"{row['variant_0x19D86']}, cursor {row['cursor_0x19ECC']}")
    gdb.clear_break(at)
    gdb.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"breakpoint": VIEW_BASIS_DONE, "skip": args.skip,
                   "demo_digit": digit, "demo_stream": stream,
                   "resources": names, "rows": rows}, f)
    print(f"  wrote {len(rows)} basis frames -> {args.out}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hdd", default=default_hdd())
    parser.add_argument("--records", type=int, default=800)
    parser.add_argument("--view-basis", action="store_true",
                        help="trace 00007D25's outputs at 00007D74 instead of "
                             "the flight state: the view angle, its sin/cos, "
                             "the backdrop slope/offset, and the camera the "
                             "selected variant left behind")
    parser.add_argument("--fan", action="store_true",
                        help="trace 00024D9F's fan column instead: the "
                             "slot, its stored 12.20 lateral, the ring's "
                             "shifted B, and the v the sprite is drawn at")
    parser.add_argument("--objects", action="store_true",
                        help="trace the whole object table at 000234CE, one "
                             "row per update pass: every per-slot array the "
                             "state handlers touch")
    parser.add_argument("--sprites", action="store_true",
                        help="trace every entry to 000253CD, the scaled-sprite "
                             "blit: slot, frame, column, row and scale")
    parser.add_argument("--regs", action="store_true",
                        help="registers and blitter bytes at --peek-at for --peek-cursor")
    parser.add_argument("--rings", action="store_true",
                        help="one row per ring of the terrain walk at --peek-cursor")
    parser.add_argument("--marks", action="store_true",
                        help="trace every entry to 00024DA4, the targetability test")
    parser.add_argument("--poke-from", type=int, default=None,
                        help="with --objects: hold Space on the cannon page from this cursor")
    parser.add_argument("--poke-to", type=int, default=None,
                        help="with --poke-from: release at this cursor")
    parser.add_argument("--poke-page", type=int, default=2,
                        help="the console page to restore at --poke-to")
    parser.add_argument("--peek-addr", type=lambda v: int(v, 0), default=None,
                        help="flat address to dump once --peek-cursor is reached")
    parser.add_argument("--peek-len", type=lambda v: int(v, 0), default=256)
    parser.add_argument("--peek-at", type=lambda v: int(v, 0), default=0x234CE,
                        help="instruction to stop at (default 000234CE)")
    parser.add_argument("--peek-cursor", type=int, default=0)
    parser.add_argument("--peek-hit", type=int, default=1,
                        help="which qualifying stop to dump (2 = the second pass "
                             "at the same instruction, e.g. the target view's)")
    parser.add_argument("--skip", type=int, default=0,
                        help="trace the Nth replay arm rather than the first; "
                             "the attract cycles demo1, demo2, demo3, demo0")
    parser.add_argument("--replays", type=int, default=0,
                        help="report the first N replay arms - which DEMO "
                             "stream each attract pass opens and which "
                             "terrain family is loaded under it - and exit "
                             "without tracing the flight")
    parser.add_argument("--wait", type=float, default=180.0)
    parser.add_argument("--out", default=os.path.join(
        ROOT, "work", "replay_dos", "flight-dos.json"))
    args = parser.parse_args()

    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        geometry = json.load(f)
    port = int(os.environ.get("QMP_PORT", 4617))
    gdb_port = int(os.environ.get("GDB_PORT", 4618))
    command = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,"
                         "cache=writeback",
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,"
                          f"cyls={geometry['cyls']},heads={geometry['heads']},"
                          f"secs={geometry['secs']}",
               "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
               "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
               "-gdb", f"tcp:127.0.0.1:{gdb_port}"]
    print("$", " ".join(command))
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, process, args.wait):
            return 1

        if args.replays:
            # Arm before the FIRST replay rather than after it: the pass the
            # attract opens with is the one the port has to match, and
            # wait_for_flight can only ever see a replay already running.
            gdb = Rsp(gdb_port, timeout=args.wait)
            armed = linear(REPLAY_ARMED)
            if gdb.set_break(armed) != "OK":
                print(f"  breakpoint at {REPLAY_ARMED:#07x} refused")
                return 1
            seen = []
            for index in range(args.replays):
                stop = (gdb.cont_until_stop() if not index
                        else gdb.cont_from_break(armed))
                if stop is None:
                    print("  no further replay armed")
                    break
                digit = (read_block(gdb, linear(DEMO_DIGIT), 1) or b"\0")[0]
                raw = read_block(gdb, linear(DEMO_NAME), 10) or b""
                stream = raw.split(b"\0")[0].decode("latin-1", "replace")
                names = [n.strip() for n in read_resource_names(qmp)[:4] if n]
                print(f"  replay {index}: [0x2975A]={digit} {stream} "
                      f"-> {' '.join(names)}")
                seen.append({"index": index, "digit": digit,
                             "stream": stream, "resources": names})
            gdb.clear_break(armed)
            gdb.close()
            os.makedirs(os.path.dirname(args.out), exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump({"replays": seen}, f, indent=1)
            print(f"  wrote {len(seen)} replay arms -> {args.out}")
            return 0

        gdb = Rsp(gdb_port, timeout=args.wait)

        # Stop as a replay ARMS, not once one is running. Polling [0x19ED0]
        # can only ever catch a flight already tens of records in, and a
        # comparison that starts mid-flight cannot separate a wrong start
        # state from a drift that began before the first captured row.
        armed = linear(REPLAY_ARMED)
        if gdb.set_break(armed) != "OK":
            print(f"  breakpoint at {REPLAY_ARMED:#07x} refused")
            return 1
        print(f"  waiting for replay arm {args.skip} at {REPLAY_ARMED:#07x}")
        for index in range(args.skip + 1):
            if (gdb.cont_until_stop() if not index
                    else gdb.cont_from_break(armed)) is None:
                print("  the replay never armed")
                return 1
        gdb.clear_break(armed)
        digit = (read_block(gdb, linear(DEMO_DIGIT), 1) or b"\0")[0]
        name = (read_block(gdb, linear(DEMO_NAME), 10) or b"")
        stream = name.split(b"\0")[0].decode("latin-1", "replace")
        print(f"  replay armed: [0x2975A]={digit} stream={stream!r}")
        names = read_resource_names(qmp)
        print("  active mission resources:",
              " ".join(n.strip() for n in names[:4] if n))

        if args.view_basis:
            return trace_view_basis(gdb, qmp, args, digit, stream, names)
        if args.regs:
            return trace_regs(gdb, qmp, args, digit, stream, names)
        if args.rings:
            return trace_rings(gdb, qmp, args, digit, stream, names)
        if args.marks:
            return trace_marks(gdb, qmp, args, digit, stream, names)
        if args.peek_addr is not None:
            return trace_peek(gdb, qmp, args, digit, stream, names)
        if args.sprites:
            return trace_sprites(gdb, qmp, args, digit, stream, names)
        if args.objects:
            return trace_objects(gdb, qmp, args, digit, stream, names)
        if args.fan:
            return trace_object_fan(gdb, qmp, args, digit, stream, names)

        reply = gdb.set_break(linear(FLIGHT_TICK_DONE))
        if reply != "OK":
            print(f"  breakpoint refused: {reply!r}")
            return 1
        print(f"  breakpoint armed at {FLIGHT_TICK_DONE:#07x}, tracing")

        rows = []
        started = time.time()
        first = True
        while len(rows) < args.records:
            stop = (gdb.cont_until_stop() if first
                    else gdb.cont_from_break(linear(FLIGHT_TICK_DONE)))
            first = False
            if stop is None:
                print("  breakpoint stopped being reached")
                break
            raw = read_block(gdb, linear(BASE), SPAN)
            if raw is None:
                print("  memory read refused")
                break
            row = decode_row(raw)
            if row["replay_0x19ED0"] != REPLAY_PLAYING:
                print(f"  replay ended after {len(rows)} ticks")
                break
            rows.append(row)
            if len(rows) % 100 == 0:
                print(f"  {len(rows)} ticks, cursor "
                      f"{row['cursor_0x19ECC']} "
                      f"({time.time() - started:.0f}s)")
        gdb.clear_break(linear(FLIGHT_TICK_DONE))
        gdb.close()

        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"breakpoint": FLIGHT_TICK_DONE,
                       "skip": args.skip,
                       "demo_digit": digit, "demo_stream": stream,
                       "resources": names, "rows": rows}, f)
        print(f"  wrote {len(rows)} ticks -> {args.out}")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
