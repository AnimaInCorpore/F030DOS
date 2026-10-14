#!/usr/bin/env python3
r"""Make the unmodified original write its own screenshot of one replay frame.

The complete-frame gate needs a DOS page taken at a known replay record, not at
an instant. `000165FD` is the game's own 328x240 PCX writer and the frame loop
already calls its gate, `000189C2`, once per frame from `00006AE9`. The gate
wants Alt (`[0x1AA8]`, scancode 0x38) and P (`[0x1A89]`, 0x19) down and the
KYLE feature byte `[0x265ED]` anything but 0xFF. So this stops the guest at
`00006AE9` until `[0x19ECC]` holds the requested cursor, writes those three
bytes through the gdbstub, lets the writer run, releases P at `000189E2` (the
wait-for-release loop right after the call), restores the bytes and lets the
game close the file. No byte of the executable is patched.

Which frame lands in the file, from the listing:

  * 00015B78 writes the CRTC start from `[0x19CAC]`, the page just drawn plus
    one byte, and only then flips `[0x19CA8]` (00015BF7-00015C01) to the page
    the next frame will draw.
  * 0001667B reads `[0x19CA8] XOR 0x7D00` - the page on screen. At 00006AE9 of
    loop N+1 that is loop N's completed frame, drawn from the state before
    loop N's record and published after it, with `[0x19ECC]` already past it.
  * The CRTC start is page + 1 byte, and a Mode X byte is four pixels, so the
    displayed 320-pixel window starts at page x = 4 (pan x 4, y 0) unless the
    shake table `[0x15B60 + 4*[0x19DBC]]` or `[0x19DC4]` adds to it; both are
    read and recorded.

The guest writes to a scratch COPY of the oracle disk image; the committed
image is never modified.

    python3 work/capture_dos_frame.py --record 20 --out build/frame-pair/dos

N/A - target artefact: an oracle probe, no DOS routine.
"""
import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import Qmp, default_hdd, QEMU, ROOT
from rsp import Rsp
from dump_marcher_tables import linear, read_resource_names, wait_for_program
from trace_replay_flight import (REPLAY_ARMED, DEMO_DIGIT, DEMO_NAME,
                                 read_block)
import dosimg

FRAME_GATE_CALL = 0x00006AE9     # call 000189C2 inside the flight loop
SNAP_RELEASE_WAIT = 0x000189E2   # waits for P's release after 000165FD
KEY_ALT = 0x1AA8                 # [scancode 0x38 + 0x1A70]
KEY_P = 0x1A89                   # [scancode 0x19 + 0x1A70]
FEATURE = 0x265ED                # KYLE toggle, 0xFF = off
CURSOR = 0x19ECC
VARIANT = 0x19D86
PAGE = 0x19CA8
START = 0x19CAC
SHAKE_INDEX = 0x19DBC
SHAKE_TABLE = 0x15B60
START_EXTRA = 0x19DC4
FRAME_COUNT = 0x19DE8
SNAP_NAME = 0x165F0


def u32(gdb, addr):
    raw = read_block(gdb, linear(addr), 4)
    return struct.unpack("<I", raw)[0] if raw else None


def u8(gdb, addr):
    raw = read_block(gdb, linear(addr), 1)
    return raw[0] if raw else None


def poke(gdb, addr, value):
    reply = gdb.cmd(f"M{linear(addr):x},1:{value:02x}")
    if reply != "OK":
        raise RuntimeError(f"write {addr:#x} refused: {reply!r}")


def copy_snap(hdd, part_off, name, dest):
    """mcopy the writer's file out of wherever the game's cwd put it."""
    env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    for directory in ("::/COMANCHE", "::"):
        target = f"{directory}/{name}"
        # mtools interprets a Windows destination like C:\... as DOS drive C.
        # Use the destination directory as cwd and pass only the host basename.
        p = subprocess.run([dosimg.host_tool("mcopy"), "-o", "-n", "-i",
                            f"{hdd}@@{part_off}", target, os.path.basename(dest)],
                           cwd=os.path.dirname(os.path.abspath(dest)),
                           capture_output=True, text=True, env=env)
        if p.returncode == 0 and os.path.isfile(dest):
            return target
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hdd", default=default_hdd())
    ap.add_argument("--record", type=int, required=True,
                    help="replay record index; the capture is taken when "
                         "[0x19ECC] = record*8 + 13, i.e. after that record")
    ap.add_argument("--skip", type=int, default=0,
                    help="Nth replay arm (0 = the attract's first, DEMO1)")
    ap.add_argument("--variant", type=int, default=1,
                    help="required [0x19D86]; refuse any other camera")
    ap.add_argument("--wait", type=float, default=240.0)
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    scratch = os.path.join(out, "oracle-scratch.hdd")
    shutil.copyfile(args.hdd, scratch)
    shutil.copyfile(args.hdd + ".geom.json", scratch + ".geom.json")
    with open(scratch + ".geom.json", encoding="utf-8") as f:
        geometry = json.load(f)
    part_off = geometry["part_offset"]

    want_cursor = args.record * 8 + 13
    port = int(os.environ.get("QMP_PORT", 4627))
    gdb_port = int(os.environ.get("GDB_PORT", 4628))
    command = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", f"file={scratch},format=raw,if=none,id=hd0,"
                         "cache=writethrough",
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,"
                          f"cyls={geometry['cyls']},heads={geometry['heads']},"
                          f"secs={geometry['secs']}",
               "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
               "-qmp", f"tcp:127.0.0.1:{port},server=on,wait=off",
               "-gdb", f"tcp:127.0.0.1:{gdb_port}"]
    print("$", " ".join(command))
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL,
                               stderr=subprocess.STDOUT)
    meta = {"record": args.record, "cursor_wanted": want_cursor}
    try:
        qmp = Qmp(port)
        if not wait_for_program(qmp, process, args.wait):
            return 1
        gdb = Rsp(gdb_port, timeout=args.wait)
        armed = linear(REPLAY_ARMED)
        gdb.set_break(armed)
        for index in range(args.skip + 1):
            if (gdb.cont_until_stop() if not index
                    else gdb.cont_from_break(armed)) is None:
                print("  the replay never armed")
                return 1
        gdb.clear_break(armed)
        name = read_block(gdb, linear(DEMO_NAME), 10) or b""
        meta["demo_stream"] = name.split(b"\0")[0].decode("latin-1")
        meta["demo_digit"] = u8(gdb, DEMO_DIGIT)
        meta["resources"] = [n.strip() for n in read_resource_names(qmp)[:4]
                             if n]
        print(f"  replay armed: {meta['demo_stream']} {meta['resources']}")

        gate = linear(FRAME_GATE_CALL)
        gdb.set_break(gate)
        first = True
        while True:
            stop = gdb.cont_until_stop() if first else gdb.cont_from_break(gate)
            first = False
            if stop is None:
                print("  00006AE9 stopped being reached")
                return 1
            cursor = u32(gdb, CURSOR)
            if cursor >= want_cursor:
                break
        gdb.clear_break(gate)
        variant = u8(gdb, VARIANT)
        page = u32(gdb, PAGE)
        start = u32(gdb, START)
        shake_index = u32(gdb, SHAKE_INDEX)
        shake_add = u32(gdb, SHAKE_TABLE + 4 * (shake_index or 0))
        extra = u32(gdb, START_EXTRA)
        meta.update({
            "cursor": cursor, "variant": variant,
            "frame_count_0x19DE8": u32(gdb, FRAME_COUNT),
            "page_0x19CA8": page, "start_0x19CAC": start,
            "displayed_page": page ^ 0x7D00 if page is not None else None,
            "shake_index_0x19DBC": shake_index, "shake_add": shake_add,
            "start_extra_0x19DC4": extra,
            "feature_0x265ED": u8(gdb, FEATURE),
            "detail_0x25DD4": u8(gdb, 0x25DD4),
            "rings_0x19EE0": u32(gdb, 0x19EE0),
            "view_angle_0x19D00": u32(gdb, 0x19D00),
            "registers_at_capture": qmp.hmp("info registers"),
            "keys": [u8(gdb, KEY_ALT), u8(gdb, KEY_P)],
        })
        print(f"  stopped at 00006AE9: cursor {cursor} variant {variant} "
              f"page {page:#x} start {start:#x} shake {shake_index}/"
              f"{shake_add} extra {extra}")
        if cursor != want_cursor or variant != args.variant:
            print(f"  refusing: wanted cursor {want_cursor} variant "
                  f"{args.variant}")
            return 1
        # CRTC start as 00015BB7-00015BC9 computes it for the page on screen.
        crtc = ((page ^ 0x7D00) + 1 + (shake_add or 0) + (extra or 0))
        meta["crtc_start"] = crtc
        pan_bytes = crtc - (page ^ 0x7D00)
        meta["pan"] = [4 * (pan_bytes % 82), pan_bytes // 82]

        saved = {a: u8(gdb, a) for a in (KEY_ALT, KEY_P, FEATURE)}
        poke(gdb, KEY_ALT, 0x38)
        poke(gdb, KEY_P, 0x19)
        if saved[FEATURE] == 0xFF:
            poke(gdb, FEATURE, 0x00)
        release = linear(SNAP_RELEASE_WAIT)
        gdb.set_break(release)
        if gdb.cont_until_stop() is None:
            print("  the writer never returned to 000189E2")
            return 1
        gdb.clear_break(release)
        poke(gdb, KEY_P, 0x99)
        poke(gdb, KEY_ALT, 0xB8)
        poke(gdb, FEATURE, saved[FEATURE])
        snap = (read_block(gdb, linear(SNAP_NAME), 12) or b"").split(b"\0")[0]
        meta["snap_name_after"] = snap.decode("latin-1")
        gdb.cmd("D")
        gdb.close()
        time.sleep(3)
        qmp.hmp("quit")
        process.wait(timeout=20)
    finally:
        if process.poll() is None:
            process.kill()

    pcx = os.path.join(out, "SNAP_001.PCX")
    target = copy_snap(scratch, part_off, "SNAP_001.PCX", pcx)
    if target is None:
        print("  SNAP_001.PCX not found on the scratch image")
        return 1
    meta["pcx"] = pcx
    meta["pcx_size"] = os.path.getsize(pcx)
    meta["guest_path"] = target
    os.remove(scratch)
    with open(os.path.join(out, "dos-frame.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print(f"  wrote {pcx} ({meta['pcx_size']} bytes), pan {meta['pan']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
