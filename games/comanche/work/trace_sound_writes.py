#!/usr/bin/env python3
r"""The original's sound driver, captured at its port writes.

Comanche's music and FM effects are one driver (0002B9CF-0002C4A0; spec
analysis/functions/sound-driver.md, records #sound-driver-* in
analysis/functions/browser-attract.md) whose only outputs are port writes, and its
digital effects are a software mixer (00004E0C-000053D5) whose output is a buffer:

  OPL2   0002C1B8   the register write helper: ah = register, al = value
                    (out 0x388 <- ah, delay, out 0x389 <- al, delay)
         0002C20E, 0002C237   the two status reads of the detection (al after `in`)
  MPU    0002BF88   one data byte to 0x330 after the 0x331 ready poll
         0002BFD9   one command byte to 0x331, then the wait for the acknowledge
  PC spk 0002C436, 0002C440, 0002C455, 0002C45C, 0002C469, 0002C475, 0002C47B
                    the `out`s (before), and the `in al, 0x61`s (after)
  digital 00005220  the mixer fill: 0x800 bytes of the Sound Blaster's half buffer

This probe stops the original at those instructions through QEMU's gdbstub
(work/rsp.py) and logs every write. Two modes:

  direct    stop the original as a demo replay arms (so the game, its stack and
            its timer are alive), put the driver's data (0002C48C-0002DC00) and the
            mixer's records back to the bytes the image ships, and then CALL the
            driver's own entries with chosen inputs, one op at a time, with
            interrupts off so the PIT cannot tick behind the probe's back: select
            a device, start a song, run N ticks (a tick is exactly what the timer
            ISR does at 00001D2C: `call [0002C48C]`), request an effect, stop; for
            the digital layer load the banks, request samples and run the fill.
            Each op records the writes it caused in order, the returned al and
            every byte that changed in the driver's variable windows. The song
            bytes are poked above the allocator's current top (a bump pointer at
            [0002572B]) exactly as the game's loader (00015E6E) leaves them: the
            'MS3-KGF' signature at the buffer address, KRL0 stripped, KRL1
            run-length decoded.

  natural   boot the game with an emulated AdLib and log what the game itself does:
            every entry of the driver (0002B9CF, 0002BD00, 0002BEDC) and of the
            digital layer (00004E2E/4E26/4E8E/4F6E/4FE4/4E0C/4FBB/50B4) with its
            registers, every card write, and every timer ISR entry (00001D20), in
            one ordered stream; at every driver and ISR entry also the driver's
            variables (437 bytes) and the song's bytes at its cursor, which is what
            lets a replay put an interrupt that arrived inside a driver call where
            it arrived. The gdbstub is connected BEFORE the program is resident (the
            start-up detection and device selection are in the first 2.5 s); stops
            before the signature at 00025880 is in memory are DOS's own code on the
            same linear addresses and are stepped over.

The two hardware gaps and what the probe does about each:

  * OPL: QEMU's `-device adlib` is a real YM3812 model, so the driver's own
    detection (0002C1EA: reads 0x388 status after timer 1 starts) passes with
    no help (status 00 then C0). The writes are taken at the helper entry;
    nothing is forced. With --no-adlib the card is absent and the detection
    reads 0xFF twice.
  * MPU-401: QEMU has no MPU-401 on the ISA bus, so 0x331 reads 0xFF forever
    and the ready poll at 0002BF96 would never end. With --mpu the probe
    breaks at 0002BF88 (data byte) and 0002BFD9 (command byte), logs `al`, and
    skips the routine (EIP := return address, ESP += 4). 0002BFD9 returns
    al = 0xFE, the MPU-401's acknowledge byte. Nothing else is forced. The
    driver reaches the card only through these two routines.
  * No Sound Blaster is attached: the game's own probe (00004FBB) fails and
    [00019DF9] is 0, so effects take the FM path; the digital scenarios poke
    [00019DF9] = 1 and call the mixer's fill themselves.

    python3 work/trace_sound_writes.py direct --scenario openmus --out build/sound/openmus.json
    python3 work/trace_sound_writes.py direct --scenario openmus-mpu --mpu --out build/sound/openmus-mpu.json
    python3 work/trace_sound_writes.py natural --seconds 400 --out build/sound-natural/natural-attract.json
    node tools/check-js-sound.js [--natural build/sound-natural/natural-attract.json]

N/A - target artefact: an oracle probe, no DOS routine.
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_qemu_state import Qmp, default_hdd, QEMU, ROOT
from rsp import Rsp
from dump_marcher_tables import linear, wait_for_program
from trace_replay_flight import REPLAY_ARMED, read_block, write_block, read_regs

# --- the driver, flat addresses -------------------------------------------
CMD = 0x0002B9CF          # ax = command; ah high nibble selects
START = 0x0002BD00        # al = flags, ebx = song buffer
STOP = 0x0002BEDC
TICK_VECTOR = 0x0002C48C  # [vector] is what the timer ISR calls
OPL_WRITE = 0x0002C1B8
MPU_DATA = 0x0002BF88
MPU_COMMAND = 0x0002BFD9
RETURN_STOP = 0x0002C48B  # a padding nop nothing reaches: the injected calls "return" here
# The OPL detection's two status reads: stopped on the instruction after each
# `in al, dx` (0002C20D, 0002C236) with the status in AL.
OPL_STATUS_1 = 0x0002C20E
OPL_STATUS_2 = 0x0002C237
# The PC speaker's port instructions: stopped BEFORE each `out` (AL is the value),
# and on the instruction after each `in al, 0x61` (AL is what the port returned).
SPEAKER_OUT = {0x0002C436: 0x61, 0x0002C440: 0x61, 0x0002C455: 0x61, 0x0002C45C: 0x61,
               0x0002C469: 0x43, 0x0002C475: 0x42, 0x0002C47B: 0x42}
SPEAKER_IN = (0x0002C434, 0x0002C43E, 0x0002C453, 0x0002C45A)
DELAY_LOOPS = 0x00001C8E
EFFECT_ENTRY = 0x00004E8E # ebp = effect; with [00019DF9] = 0 it is `mov eax, ebp; jmp 0002B9CF`
ISR_ENTRY = 0x00001D20
GAME_TICK = 0x00019DDC    # the ISR's own increment (it is reset by the game, so not monotone)
DIGITAL_FLAG = 0x00019DF9
HEAP_LOW = 0x0002572B     # the allocator's low bump pointer
HEAP_LIMIT = 0x000014DC

# The driver's data: 0002C48C (tick vector) .. 0002DC00, all inside the image. The
# last 0x400 bytes (0002D7F0..) are not the driver's: the game relocates a table of
# 256 dwords there at start-up (000055F2-00005602, += 0x40000). They are included
# because an effect number above 0x7F reads its "patch" pointer out of that table;
# the probe puts the image's bytes back over them like everything else.
STATE_LO = 0x0002C48C
STATE_HI = 0x0002DC00
# The part of it that is per-run state rather than constant tables, for the delta log.
STATE_VARS = [(0x0002C48C, 0x0002C5D9), (0x0002D10D, 0x0002D163), (0x0002D404, 0x0002D408),
              # the digital layer: slots, staged samples, dither (00004142-000041B7) ...
              (0x00004142, 0x000041B8),
              # ... the immediates the mix loop is patched with, and the curve's address
              (0x0000527A, 0x0000527D), (0x000052A4, 0x000052A8), (0x000052D0, 0x000052D4),
              (0x00005307, 0x0000530B),
              # ... the double buffer's pointers and the three bank variables, the mode flag
              (0x00004FD4, 0x00004FE0), (0x00019E98, 0x00019EA4), (0x00019DF9, 0x00019DFA)]
# Image bytes the digital scenarios start from (the mixer's records, tables and code patches).
MIXER_RESTORE = [(0x000040E2, 0x00004200), (0x00004FD4, 0x00004FE4), (0x00005220, 0x00005320),
                 (0x00019DF9, 0x00019DFA), (0x00019E98, 0x00019EA4)]
MIXER_FILL = 0x00005220
MIXER_RESET = 0x000050B4
MIXER_RATE = 0x00004E0C
SPEECH_A = 0x00004E2E
SPEECH_B = 0x00004E26
VOICE = 0x00004F6E

FLAT_IMAGE = os.path.join(ROOT, "re", "unpacked", "comanche-flat32.bin")
ASSETS = os.path.join(ROOT, "assets", "extracted", "comanche_hdd")

REG_NUMBERS = {"eax": 0, "ecx": 1, "edx": 2, "ebx": 3, "esp": 4, "ebp": 5,
               "esi": 6, "edi": 7, "eip": 8, "eflags": 9}

# One entry point per stopped address in natural mode: name -> (address, registers worth keeping)
NATURAL_POINTS = {
    "cmd": CMD, "start": START, "stop": STOP,
    "opl": OPL_WRITE, "mpu_data": MPU_DATA, "mpu_cmd": MPU_COMMAND,
    "fx_4e2e": 0x00004E2E, "fx_4e26": 0x00004E26, "fx_4e8e": 0x00004E8E,
    "voice_4f6e": 0x00004F6E, "mixer_4fe4": 0x00004FE4, "mixer_4e0c": 0x00004E0C,
    "probe_4fbb": 0x00004FBB, "reset_50b4": 0x000050B4, "isr": ISR_ENTRY,
}


def load_krl(name):
    """The bytes the game's loader (00015E6E / 00015DD0) leaves in memory for
    a music file: KRL0 is stored (header dropped), KRL1 is run-length decoded
    (0001644B: a byte below 0xC0 is literal, otherwise count = byte & 0x3F and
    the next byte repeats count times), a bare .MS3 is read as it is."""
    with open(os.path.join(ASSETS, name), "rb") as f:
        raw = f.read()
    tag = raw[:4]
    if tag == b"KRL0":
        size = struct.unpack_from("<I", raw, 4)[0]
        out = raw[8:8 + size]
    elif tag == b"KRL1":
        size = struct.unpack_from("<I", raw, 4)[0]
        out = bytearray()
        p = 8
        while len(out) < size:
            b = raw[p]
            p += 1
            if b < 0xC0:
                out.append(b)
            else:
                out.extend(bytes([raw[p]]) * (b & 0x3F))
                p += 1
        out = bytes(out[:size]) if len(out) >= size else bytes(out)
    else:
        out = raw
    return out


def load_song(name):
    out = load_krl(name)
    if out[:10] != b"MS3-KGF'91":
        raise RuntimeError(f"{name} does not decode to an MS3 song")
    return out


class Guest:
    def __init__(self, hdd, adlib=True, qmp_port=4717, gdb_port=4718, wait=240.0):
        with open(hdd + ".geom.json", encoding="utf-8") as f:
            g = json.load(f)
        qmp_port = int(os.environ.get("QMP_PORT", qmp_port))
        gdb_port = int(os.environ.get("GDB_PORT", gdb_port))
        cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", f"file={hdd},format=raw,if=none,id=hd0,snapshot=on",
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                          f"heads={g['heads']},secs={g['secs']}",
               "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
               "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,wait=off",
               "-gdb", f"tcp:127.0.0.1:{gdb_port}"]
        if adlib:
            cmd += ["-audiodev", "none,id=snd0", "-device", "adlib,audiodev=snd0"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        self.qmp = Qmp(qmp_port)
        if not wait_for_program(self.qmp, self.proc, wait):
            raise RuntimeError("the program never became resident")
        self.gdb = Rsp(gdb_port, timeout=wait)
        with open(FLAT_IMAGE, "rb") as f:
            self.flat = f.read()

    def close(self):
        try:
            self.gdb.close()
        finally:
            self.proc.kill()
            self.proc.wait()

    # memory by flat address -------------------------------------------------
    def peek(self, address, count):
        out = b""
        while count > 0:
            n = min(count, 0x400)
            raw = read_block(self.gdb, linear(address), n)
            if raw is None:
                raise RuntimeError(f"read of {n} bytes at {address:#x} refused")
            out += raw
            address += n
            count -= n
        return out

    def poke(self, address, data):
        data = bytes(data)
        for i in range(0, len(data), 0x400):
            write_block(self.gdb, linear(address + i), data[i:i + 0x400])

    def peek32(self, address):
        return struct.unpack("<I", self.peek(address, 4))[0]

    def poke32(self, address, value):
        self.poke(address, struct.pack("<I", value & 0xFFFFFFFF))

    # registers ---------------------------------------------------------------
    def set_reg(self, name, value):
        reply = self.gdb.cmd(f"P{REG_NUMBERS[name]:x}={struct.pack('<I', value & 0xFFFFFFFF).hex()}")
        if reply != "OK":
            raise RuntimeError(f"register write {name} refused: {reply!r}")

    def regs(self):
        return read_regs(self.gdb)

    def run_to(self, resume, watched, handler, limit=2_000_000):
        """Continue until one of `watched` (flat addresses) is the stop; call
        handler(address, regs) for every one, and stop when it returns True."""
        last = resume
        for _ in range(limit):
            stop = self.gdb.cont_until_stop() if last is None else self.gdb.cont_from_break(linear(last))
            if stop is None:
                raise RuntimeError("the guest stopped answering")
            regs = self.regs()
            eip = regs["eip"]
            last = eip if eip in watched else None
            if eip not in watched:
                continue
            if handler(eip, regs):
                return regs
        raise RuntimeError("too many stops")


# ---------------------------------------------------------------------------
# natural mode
# ---------------------------------------------------------------------------
NATURAL_STATE = [(0x0002C48C, 0x0002C5D9), (0x0002D10D, 0x0002D163), (0x0002D404, 0x0002D408)]
SONG_WINDOW = 0x4000
CURSOR_WINDOW = 0xA0      # bytes read at every song start (the longest shipped song is 13012)


def run_natural(args):
    """Boot the game with a real AdLib and log what it does to the sound driver.

    The gdbstub is connected BEFORE the program is resident, so the start-up
    detection and device selection are in the log. A stop at one of our addresses
    before the flat image is resident is some other code of DOS or its drivers and
    is ignored. Every ISR entry (00001D20) is an event: the replay of a log is "a
    tick for every ISR", which is what the original does at 00001D2C."""
    with open(args.hdd + ".geom.json", encoding="utf-8") as f:
        g = json.load(f)
    qmp_port = int(os.environ.get("QMP_PORT", 4727))
    gdb_port = int(os.environ.get("GDB_PORT", 4728))
    cmd = [QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
           "-drive", f"file={args.hdd},format=raw,if=none,id=hd0,snapshot=on",
           "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                      f"heads={g['heads']},secs={g['secs']}",
           "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
           "-qmp", f"tcp:127.0.0.1:{qmp_port},server=on,wait=off",
           "-gdb", f"tcp:127.0.0.1:{gdb_port}"]
    if not args.no_adlib:
        cmd += ["-audiodev", "none,id=snd0", "-device", "adlib,audiodev=snd0"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    events = []
    result = {"mode": "natural", "events": events}
    try:
        qmp = Qmp(qmp_port)
        gdb = Rsp(gdb_port, timeout=240)
        with open(FLAT_IMAGE, "rb") as f:
            flat = f.read()
        signature = flat[0x25880:0x25890]
        points = dict(NATURAL_POINTS)
        points.update({"opl_status_1": OPL_STATUS_1, "opl_status_2": OPL_STATUS_2})
        for a in SPEAKER_OUT:
            points[f"spk_out_{a:x}"] = a
        for a in SPEAKER_IN:
            points[f"spk_in_{a:x}"] = a
        by_addr = {addr: name for name, addr in points.items()}
        for addr in by_addr:
            gdb.set_break(linear(addr))
        resident = False
        isr = 0
        t0 = time.time()
        last = None
        ignored = 0

        def peek(address, count):
            return read_block(gdb, linear(address), count)

        def poke_reg(name, value):
            reply = gdb.cmd(f"P{REG_NUMBERS[name]:x}={struct.pack('<I', value & 0xFFFFFFFF).hex()}")
            if reply != "OK":
                raise RuntimeError(f"register write {name} refused: {reply!r}")

        while time.time() - t0 < args.seconds:
            stop = gdb.cont_until_stop() if last is None else gdb.cont_from_break(linear(last))
            if stop is None:
                break
            regs = read_regs(gdb)
            eip = regs["eip"]
            name = by_addr.get(eip)
            last = eip if name else None
            if os.environ.get("SOUND_PROBE_VERBOSE") and (ignored < 20):
                print(f"  stop {stop[:12]!r} eip={eip:#x} name={name} t={time.time() - t0:.1f}", flush=True)
            if name is None:
                # some other code of DOS hit a breakpoint address (only possible before the
                # program is resident, while the same linear addresses are DOS's own): step
                # over it, `c` would stop on it again at once
                if gdb.step() is None:
                    break
                continue
            if not resident:
                if peek(0x25880, 16) != signature:
                    ignored += 1
                    continue
                resident = True
                result["resident_at_s"] = round(time.time() - t0, 2)
            ev = {"isr": isr, "at": name}
            if name in ("isr", "cmd", "start", "stop"):
                # the driver's variables at the entry: what the replay of an interrupted call has to
                # reproduce at the moment the ISR arrived, and what every call starts from
                state = b"".join(peek(lo, hi - lo) for lo, hi in NATURAL_STATE)
                ev["state"] = state.hex()
                # the song's bytes at the cursor, as they are NOW: the game reuses the buffer
                # at 0002DB10 (it is also the demo buffer), so a song can change under the player
                cursor = struct.unpack_from("<I", state, 0x2C490 - 0x2C48C)[0]
                if state[0x2C49E - 0x2C48C] and cursor:
                    ev["cursor_bytes"] = (peek(cursor, CURSOR_WINDOW) or b"").hex()
            if name == "isr":
                isr += 1
                ev["isr"] = isr
                events.append(ev)
                continue
            ev["game_tick"] = struct.unpack("<I", peek(GAME_TICK, 4))[0]
            esp_word = struct.unpack("<I", peek(regs["esp"], 4))[0]
            if name == "opl":
                ev["reg"] = (regs["eax"] >> 8) & 0xFF
                ev["val"] = regs["eax"] & 0xFF
                ev["caller"] = esp_word
            elif name in ("opl_status_1", "opl_status_2"):
                ev["val"] = regs["eax"] & 0xFF
            elif name.startswith("spk_"):
                ev["val"] = regs["eax"] & 0xFF
            elif name in ("mpu_data", "mpu_cmd"):
                ev["val"] = regs["eax"] & 0xFF
                ev["caller"] = esp_word
                poke_reg("esp", regs["esp"] + 4)         # the MPU does not exist: acknowledge for the guest
                poke_reg("eip", esp_word)
                if name == "mpu_cmd":
                    poke_reg("eax", (regs["eax"] & ~0xFF) | 0xFE)
                last = None
            else:
                for r in ("eax", "ebx", "ecx", "edx", "ebp", "esi"):
                    ev[r] = regs[r]
                ev["caller"] = esp_word
                if name == "start" and regs["ebx"]:
                    ev["song"] = (peek(regs["ebx"], SONG_WINDOW) or b"").hex()
                if name == "cmd" and "delay_1c8e" not in result:
                    result["delay_1c8e"] = struct.unpack("<H", peek(DELAY_LOOPS, 2))[0]
            events.append(ev)
        result["isr_count"] = isr
        result["ignored_stops_before_resident"] = ignored
        result["image_sha256"] = hashlib.sha256(flat).hexdigest()
        gdb.close()
    finally:
        proc.kill()
        proc.wait()
    write_json(args.out, result)
    print(f"  {len(events)} events, {isr} ISR entries -> {args.out}")
    return 0


# ---------------------------------------------------------------------------
# direct mode
# ---------------------------------------------------------------------------
class Direct:
    def __init__(self, guest, mpu=False):
        self.g = guest
        self.mpu = mpu
        self.writes = []
        self.callers = []
        self.shadow = None
        self.base_esp = None

    def prepare(self):
        """Stop the game where its state is alive and put the driver's data back
        to the image's own bytes."""
        g = self.g
        armed = linear(REPLAY_ARMED)
        g.gdb.set_break(armed)
        if g.gdb.cont_until_stop() is None:
            raise RuntimeError("the replay never armed")
        g.gdb.clear_break(armed)
        self.base_esp = g.regs()["esp"]
        self.live_diff = self.diff_against_image()
        g.poke(STATE_LO, g.flat[STATE_LO:STATE_HI])
        for lo, hi in MIXER_RESTORE:
            g.poke(lo, g.flat[lo:hi])
        self.digital = g.peek(DIGITAL_FLAG, 1)[0]
        self.delay = struct.unpack("<H", g.peek(DELAY_LOOPS, 2))[0]
        for addr in (OPL_WRITE, RETURN_STOP, OPL_STATUS_1, OPL_STATUS_2, *SPEAKER_OUT, *SPEAKER_IN):
            g.gdb.set_break(linear(addr))
        if self.mpu:
            for addr in (MPU_DATA, MPU_COMMAND):
                g.gdb.set_break(linear(addr))
        self.shadow = self.read_vars()

    def diff_against_image(self):
        """What the running game had changed in the driver's data before the probe
        wrote the image's bytes back (informative: tells whether the shipped
        tables are what actually runs)."""
        live = self.g.peek(STATE_LO, STATE_HI - STATE_LO)
        shipped = self.g.flat[STATE_LO:STATE_HI]
        out = []
        for i, (a, b) in enumerate(zip(live, shipped)):
            if a != b:
                out.append([STATE_LO + i, b, a])
        return out

    def read_vars(self):
        blob = {}
        for lo, hi in STATE_VARS:
            blob[lo] = self.g.peek(lo, hi - lo)
        return blob

    def delta(self):
        now = self.read_vars()
        out = []
        for lo, data in now.items():
            old = self.shadow[lo]
            for i, (a, b) in enumerate(zip(old, data)):
                if a != b:
                    out.append([lo + i, b])
        self.shadow = now
        return out

    def call(self, entry, regs):
        """Run the routine at `entry` with `regs`, returning its eax and the
        writes it made. The return address is RETURN_STOP, a breakpoint."""
        g = self.g
        self.writes = []
        self.callers = []
        sp = ((self.base_esp - 0x100) & ~3) - 4   # well below the guest's own stack use
        g.poke32(sp, RETURN_STOP)
        for name in ("eax", "ebx", "ecx", "edx", "ebp", "esi", "edi"):
            g.set_reg(name, regs.get(name, 0))
        g.set_reg("esp", sp)
        g.set_reg("eflags", 0x002)               # IF = 0: no PIT tick behind our back
        g.set_reg("eip", entry)
        watched = {OPL_WRITE, RETURN_STOP, OPL_STATUS_1, OPL_STATUS_2, *SPEAKER_OUT, *SPEAKER_IN}
        if self.mpu:
            watched |= {MPU_DATA, MPU_COMMAND}

        def handler(eip, r):
            if eip == RETURN_STOP:
                return True
            if eip in (OPL_STATUS_1, OPL_STATUS_2):
                self.writes.append(["s", r["eax"] & 0xFF])
                return False
            if eip in SPEAKER_IN:
                self.writes.append(["i", 0x61, r["eax"] & 0xFF])
                return False
            if eip in SPEAKER_OUT:
                self.writes.append(["p", SPEAKER_OUT[eip], r["eax"] & 0xFF])
                return False
            caller = g.peek32(r["esp"])
            if eip == OPL_WRITE:
                self.writes.append(["o", (r["eax"] >> 8) & 0xFF, r["eax"] & 0xFF])
            else:
                kind = "m" if eip == MPU_DATA else "c"
                self.writes.append([kind, r["eax"] & 0xFF])
                g.set_reg("esp", r["esp"] + 4)
                g.set_reg("eip", caller)
                if eip == MPU_COMMAND:
                    g.set_reg("eax", (r["eax"] & ~0xFF) | 0xFE)
            self.callers.append(caller)
            return False

        first = None
        final = g.run_to(first, watched, handler)
        return final["eax"]


def op_command(d, ax):
    return {"op": "command", "ax": ax}, lambda: d.call(CMD, {"eax": ax})


SCENARIOS = {}


def scenario(name):
    def deco(fn):
        SCENARIOS[name] = fn
        return fn
    return deco


def sel(dev):
    """The game's own device bring-up (000055BD-000055D8): detect (cmd 8), then select (cmd 3)."""
    return [("command", 0x8000 | dev), ("command", 0x3000 | dev)]


def song(file, flags, ticks, dev=3, until_end=False, volume=None, effects=(), base=None):
    ops = sel(dev)
    if volume is not None:
        ops.append(("command", 0x7000 | volume))
    ops.append(("start", file, flags) if base is None else ("start", file, flags, base))
    ops.extend(("tick",) for _ in range(ticks))
    ops.append(("stop",))
    return ops


@scenario("select-adlib")
def _(): return sel(3)


@scenario("select-sb")
def _(): return sel(2)


@scenario("openmus")
def _(): return song("OPENMUS.MS3", 0, 760)


@scenario("menumus1")
def _(): return song("MENUMUS1.MS3", 2, 40)


@scenario("menumus2")
def _(): return song("MENUMUS2.MS3", 2, 2100)


@scenario("fanfare")
def _(): return song("FANFARE.RLE", 0, 300)


@scenario("musday")
def _(): return song("MUSDAY.RLE", 0, 10210)


@scenario("musnight")
def _(): return song("MUSNIGHT.RLE", 0, 3150)


@scenario("musvolc")
def _(): return song("MUSVOLC.RLE", 0, 8870)


@scenario("muswin")
def _(): return song("MUSWIN.RLE", 0, 2900)


@scenario("muslose")
def _(): return song("MUSLOSE.RLE", 0, 2260)


@scenario("bigwin")
def _(): return song("BIGWIN.RLE", 0, 11720)


@scenario("winmus")
def _(): return song("WINMUS.RLE", 0, 1320)


@scenario("openmus-mpu")
def _(): return song("OPENMUS.MS3", 0, 760, dev=4)


@scenario("fanfare-mpu")
def _(): return song("FANFARE.RLE", 0, 300, dev=4)


@scenario("musday-mpu")
def _(): return song("MUSDAY.RLE", 0, 400, dev=4)


@scenario("openmus-speaker")
def _(): return song("OPENMUS.MS3", 0, 760, dev=1)


@scenario("fanfare-speaker")
def _(): return song("FANFARE.RLE", 0, 300, dev=1)


@scenario("openmus-none")
def _(): return song("OPENMUS.MS3", 0, 50, dev=5)


@scenario("select-bad")
def _(): return [("command", 0x3000), ("command", 0x3006), ("command", 0x8006), ("command", 0x9000),
                 ("command", 0xF123), ("command", 0x6000), ("command", 0x3003), ("command", 0x6000)]


def first_note_param_offset(name):
    """Offset in the song of the velocity byte of its first 9n event."""
    data = load_song(name)
    p = 0x30
    while not (data[p] == 0xFF and data[p + 1] == 0x2F):
        status = data[p] & 0xF0
        if status == 0x90:
            return p + 2
        length = {0x80: 1, 0xB0: 3}.get(status, 2)
        q = p + length
        q += 2 if data[q] & 0x80 else 1
        p = q
    raise RuntimeError("no note")


@scenario("wrap-inc-bx")
def _():
    # The event reader's `inc bx` (0002BDED) is a 16-bit increment: when the byte after
    # a note's velocity is at xxxxFFFF the delay is read from xxxx0000 instead. Place
    # OPENMUS so that its first note's velocity byte is at 0x42FFFF, and give 0x420000
    # a delay of 5, a note off (80 00) and the end marker.
    base = 0x42FFFF - first_note_param_offset("OPENMUS.MS3")
    return sel(3) + [("poke_bytes", 0x420000, bytes([0x05, 0x80, 0x00, 0xFF, 0x2F, 0x00])),
                     ("start", "OPENMUS.MS3", 0, base)] + [("tick",)] * 60 + [("stop",)]


def digital_setup(banks=("SND1.RLE", "SPEAK1.RLE", "SPEAK0.RLE"), rate=2):
    """What the game has done by the time a mission flies: the digital flag set,
    the three banks loaded (their variables [00019E98]/[00019E9C]/[00019EA0]), the
    dither mask chosen (00004E0C, al = 2 at 000055AF) and the mixer reset."""
    variables = {"SND1.RLE": 0x19E98, "SPEAK1.RLE": 0x19E9C, "SPEAK0.RLE": 0x19EA0}
    ops = [("digital", 1)]
    ops += [("bank", variables[b], b) for b in banks]
    ops += [("rate", rate), ("reset",)]
    return ops


def fills(n):
    return [("fill",)] * n


@scenario("digital-explosion")
def _():
    # SND1 id 1 (0002286D..00022876): bl = 0xFF, dl = the distance class 0..4, ecx = 0
    ops = digital_setup()
    ops += [("fx", 1, 0xFF, 0, 0)] + fills(16)
    ops += [("reset",), ("fx", 1, 0xFF, 3, 0)] + fills(16)
    return ops


@scenario("digital-launch")
def _():
    # SND1 id 4: rocket at double pitch (00022B62), Hellfire / Stinger native, wingman dl = 1
    ops = digital_setup()
    ops += [("fx", 4, 0xFF, 0, 0x20000)] + fills(6)
    ops += [("reset",), ("fx", 4, 0xFF, 0, 0)] + fills(7)
    ops += [("reset",), ("fx", 4, 0xFF, 1, 0)] + fills(7)
    return ops


@scenario("digital-cannon")
def _():
    # SND1 id 7 with bl = 0xFE (00022890): fired again while the first burst plays
    ops = digital_setup()
    ops += [("fx", 7, 0xFE, 0, 0)] + fills(1) + [("fx", 7, 0xFE, 0, 0)] + fills(2)
    ops += [("fx", 5, 0xFF, 0, 0)] + fills(5)
    return ops


@scenario("digital-rotor")
def _():
    # 00005952-00005963 / 000189A0-000189B2: SND1 id 3 staged on slot 2 forever (VOICE)
    ops = digital_setup()
    ops += [("voice", 0x19E98, 3, 2, 2, 0)] + fills(12)
    ops += [("voice", 0x19E98, 3, 2, 1, 0)] + fills(2) + [("silence_voice", 2, 2)] + fills(3)
    return ops


@scenario("digital-speech")
def _():
    # SPEAK1 id 4 (engine failed, 00006A99), id 6 (mission start 00006A0E), SPEAK0 id 2
    ops = digital_setup()
    ops += [("speecha", 4)] + fills(10)
    ops += [("reset",), ("speecha", 6)] + fills(3) + [("speechb", 2)] + fills(8)
    return ops


@scenario("digital-mix")
def _():
    # slot choice: three at once, a fourth dropped (dl = 1) or stealing slot 0 (dl = 0),
    # the same sample twice, a speech cue with slot 2 busy, the soft curve, other dither masks
    ops = digital_setup()
    ops += [("fx", 1, 0xFF, 0, 0), ("fx", 4, 0xFF, 0, 0), ("fx", 5, 0xFF, 2, 0)] + fills(2)
    ops += [("fx", 7, 0xFF, 1, 0), ("fx", 7, 0xFF, 0, 0)] + fills(2)
    ops += [("fx", 7, 0xFF, 0, 0), ("speecha", 1), ("speechb", 1)] + fills(2)
    ops += [("poke32", 0x5307, 0x4A0A)] + fills(3)
    for rate in (0, 1, 5, 9, 17):
        ops += [("rate", rate)] + fills(1)
    ops += [("reset",)] + fills(2)
    return ops


@scenario("detect-absent")
def _(): return [("command", 0x8003), ("command", 0x8002), ("command", 0x8004), ("command", 0x8001),
                 ("command", 0x8005), ("command", 0x8000), ("command", 0x3003)] + [("tick",)] * 3


def synthetic_song(links=(), patches=(), events=b""):
    """An MS3 song built here (not from a shipped file) to reach what the shipped songs never do:
    the Bn and Dn events, an unknown status, a two-byte delay, a delay of 0, channels above 9, a
    channel link, a program change in the middle. `links` and `patches` are (channel, value) pairs."""
    header = bytearray(b"MS3-KGF'91 \n\r\x1a" + bytes(0x30 - 14))
    for channel, value in links:
        header[0x10 + channel] = value
    for channel, value in patches:
        header[0x20 + channel] = value
    return bytes(header) + events + b"\xff\x2f\x00"


ODD_EVENTS = bytes([
    0xC0, 0x20, 0x00,                 # program change: patch 0x20 on channel 0, delay 0
    0x90, 0x3C, 0x50, 0x00,           # note on, delay 0 (the next event is in the same tick)
    0xB0, 0x07, 0x64, 0x01,           # a controller: three bytes and a delay, ignored
    0xD0, 0x40, 0x00,                 # channel pressure: ignored
    0xA0, 0x3C, 0x40, 0x01,           # an unknown status: skipped like a Dn
    0xE0, 0x05, 0x02,                 # pitch offset 5 on channel 0, delay 2
    0x80, 0x00,                       # note off
    0x91, 0x44, 0x40, 0x81, 0x20,     # channel 1, a two-byte delay (160 ticks)
    0x81, 0x03,                       # note off channel 1
    0x9A, 0x30, 0x50, 0x02,           # channels above 9: the arrays are ten long
    0x8A, 0x01,
    0x9F, 0x30, 0x50, 0x02,
    0x8F, 0x01,
    0xE1, 0xFE, 0x00,                 # negative pitch offset on channel 1
    0x91, 0x40, 0x7F, 0x03,
    0xC1, 0x70, 0x00,                 # program change in the middle of a note
    0x91, 0x40, 0x7F, 0x03,
    0x81, 0x00,
])
LINK_EVENTS = bytes([
    0x90, 0x30, 0x60, 0x05, 0x80, 0x05,
    0xC1, 0x70, 0x00,
    0x90, 0x34, 0x60, 0x05, 0x80, 0x00,
    0xE0, 0x03, 0x01, 0x90, 0x38, 0x70, 0x09, 0x80, 0x00,
])


@scenario("synthetic-events")
def _():
    song = synthetic_song(links=[(1, 4)], patches=[(0, 0x31), (1, 0x58), (2, 0x5A), (3, 0x70)], events=ODD_EVENTS)
    return sel(3) + [("start_bytes", "synthetic-events", song, 2)] + [("tick",)] * 520 + [("stop",)]


@scenario("synthetic-links")
def _():
    song = synthetic_song(links=[(0, 2), (1, 3)], patches=[(0, 0x31), (1, 0x58), (2, 0x5A)], events=LINK_EVENTS)
    return sel(3) + [("start_bytes", "synthetic-links", song, 0)] + [("tick",)] * 60 + [("stop",)]


@scenario("device-switch")
def _():
    # every device's shutdown routine: 4 -> 3 -> 1 -> 4 -> 2 -> 5 -> 3 with a song and an effect running
    ops = sel(4) + [("start", "OPENMUS.MS3", 0)] + [("tick",)] * 30
    for dev in (3, 1, 4, 2, 5, 3):
        ops += sel(dev) + [("effect", 4)] + [("tick",)] * 6
    return ops + [("stop",)]


@scenario("effects-mpu")
def _(): return effect_ops([1, 2, 4, 5, 6, 7], ticks=30, dev=4)


@scenario("effects-speaker")
def _(): return effect_ops([1, 2, 4, 5, 6, 7], ticks=30, dev=1)


@scenario("openmus-volume")
def _(): return song("OPENMUS.MS3", 0, 120, volume=0x55)


def effect_ops(ids, ticks=24, dev=3):
    ops = sel(dev)
    for i in ids:
        ops.append(("effect", i))
        ops.extend(("tick",) for _ in range(ticks))
    return ops


@scenario("effects")
def _(): return effect_ops(range(25), ticks=40)


@scenario("effects-volume")
def _():
    ops = sel(3)
    for i in (0, 4, 5, 24):
        for nib in (1, 8, 15):
            ops.append(("effect", (nib << 8) | i))
            ops.extend(("tick",) for _ in range(40))
    return ops


@scenario("effect-over-music")
def _():
    ops = sel(3) + [("start", "OPENMUS.MS3", 0)]
    ops += [("tick",)] * 100
    ops.append(("effect", 4))
    ops += [("tick",)] * 60
    ops.append(("effect", 5))
    ops += [("tick",)] * 60
    ops.append(("stop",))
    return ops


@scenario("queue-and-loop")
def _():
    ops = sel(3) + [("start", "FANFARE.RLE", 0)]
    ops += [("tick",)] * 20
    ops.append(("start", "OPENMUS.MS3", 1))       # queued behind the fanfare
    ops += [("tick",)] * 400
    ops.append(("start", "MENUMUS2.MS3", 2))
    ops += [("tick",)] * 30
    ops += [("command", 0x4000)] + [("tick",)] * 5 + [("command", 0x5000)] + [("tick",)] * 30
    ops.append(("command", 0x6000))
    ops.append(("stop",))
    return ops


def run_direct(args):
    ops_list = SCENARIOS[args.scenario]()
    guest = Guest(args.hdd, adlib=not args.no_adlib)
    try:
        d = Direct(guest, mpu=args.mpu)
        d.prepare()
        hp = guest.peek32(HEAP_LOW)
        limit = guest.peek32(HEAP_LIMIT)
        base = (hp + 0x1F) & ~0xF
        ops_out = []
        song_base = {}
        bank_base = {}
        ticks_run = 0
        for n, op in enumerate(ops_list):
            kind = op[0]
            # the clock of a direct capture is the number of ticks run so far (a `tick` op is one
            # timer interrupt: 65.0 Hz); every write of this op carries that tick
            rec = {"i": n, "op": kind, "tick": ticks_run}
            d.writes = []
            d.callers = []
            if kind == "command":
                rec["ax"] = op[1]
                ret = d.call(CMD, {"eax": op[1]})
            elif kind == "start":
                name, flags = op[1], op[2]
                if len(op) > 3:
                    base = op[3]
                    song_base.pop(name, None)
                if name not in song_base:
                    data = load_song(name)
                    if base + len(data) >= limit:
                        raise RuntimeError("no room above the heap")
                    guest.poke(base, data)
                    song_base[name] = (base, len(data))
                    base = (base + len(data) + 0x1F) & ~0xF
                at, size = song_base[name]
                rec.update({"file": name, "al": flags, "ebx": at, "size": size})
                ret = d.call(START, {"eax": flags, "ebx": at})
            elif kind == "start_bytes":
                label, data, flags = op[1], op[2], op[3]
                if base + len(data) >= limit:
                    raise RuntimeError("no room above the heap")
                guest.poke(base, data)
                rec.update({"label": label, "al": flags, "ebx": base, "size": len(data), "hex": data.hex()})
                ret = d.call(START, {"eax": flags, "ebx": base})
                base = (base + len(data) + 0x1F) & ~0xF
            elif kind == "stop":
                ret = d.call(STOP, {})
            elif kind == "tick":
                vector = guest.peek32(TICK_VECTOR)
                rec["vector"] = vector
                ret = d.call(vector, {})
                ticks_run += 1
            elif kind == "effect":
                rec["ebp"] = op[1]
                if guest.peek(DIGITAL_FLAG, 1)[0]:
                    raise RuntimeError("[00019DF9] is non-zero: the effect would go to the digital mixer")
                ret = d.call(EFFECT_ENTRY, {"ebp": op[1]})
            elif kind == "digital":
                rec["flag"] = op[1]
                guest.poke(DIGITAL_FLAG, bytes([op[1]]))
                ret = 0
            elif kind == "poke_bytes":
                if guest.peek(op[1], len(op[2])) != bytes(len(op[2])):
                    raise RuntimeError("the region is not free")
                rec["address"], rec["bytes"] = op[1], op[2].hex()
                guest.poke(op[1], op[2])
                ret = 0
            elif kind == "poke32":
                rec["address"], rec["value"] = op[1], op[2]
                guest.poke32(op[1], op[2])
                ret = 0
            elif kind == "bank":
                variable, name = op[1], op[2]
                data = load_krl(name)
                if base + len(data) >= limit:
                    raise RuntimeError("no room above the heap")
                guest.poke(base, data)
                guest.poke32(variable, base)
                rec.update({"variable": variable, "file": name, "at": base, "size": len(data)})
                bank_base[variable] = base
                base = (base + len(data) + 0x1F) & ~0xF
                ret = 0
            elif kind == "rate":
                rec["al"] = op[1]
                ret = d.call(MIXER_RATE, {"eax": op[1]})
            elif kind == "reset":
                ret = d.call(MIXER_RESET, {})
            elif kind == "fx":
                rec.update({"ebp": op[1], "bl": op[2], "dl": op[3], "ecx": op[4]})
                ret = d.call(EFFECT_ENTRY, {"ebp": op[1], "ebx": op[2], "edx": op[3], "ecx": op[4]})
            elif kind in ("speecha", "speechb"):
                rec["al"] = op[1]
                ret = d.call(SPEECH_A if kind == "speecha" else SPEECH_B, {"eax": op[1]})
            elif kind == "voice":
                variable, ident, slot, shift, step = op[1:6]
                bank = bank_base[variable]
                ptr = (guest.peek32(bank + 4 * ident) + bank) & 0xFFFFFFFF
                rec.update({"eax": ptr, "bl": slot, "dl": shift, "ecx": step, "id": ident})
                ret = d.call(VOICE, {"eax": ptr, "ebx": slot, "edx": shift, "ecx": step})
            elif kind == "silence_voice":
                rec.update({"eax": 0x40E2, "bl": op[1], "dl": op[2], "ecx": 0})
                ret = d.call(VOICE, {"eax": 0x40E2, "ebx": op[1], "edx": op[2], "ecx": 0})
            elif kind == "fill":
                ret = d.call(MIXER_FILL, {})
                end = guest.peek32(0x4FD8)
                rec["pcm"] = guest.peek(end - 0x800, 0x800).hex()
            else:
                raise RuntimeError(kind)
            rec["ret_al"] = ret & 0xFF
            rec["writes"] = d.writes
            rec["callers"] = [f"{c:08X}" for c in d.callers]
            rec["delta"] = d.delta()
            ops_out.append(rec)
        result = {"mode": "direct", "scenario": args.scenario, "mpu": args.mpu,
                  "image_sha256": hashlib.sha256(guest.flat).hexdigest(),
                  "digital_flag": d.digital,
                  "delay_1c8e": d.delay,
                  "windows": [[lo, hi] for lo, hi in STATE_VARS],
                  "live_vs_image": d.live_diff,
                  "heap_base": hp,
                  "ops": ops_out}
    finally:
        guest.close()
    write_json(args.out, result)
    total = sum(len(o["writes"]) for o in ops_out)
    print(f"  {args.scenario}: {len(ops_out)} ops, {total} writes -> {args.out}")
    return 0


def write_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    n = sub.add_parser("natural")
    n.add_argument("--hdd", default=default_hdd())
    n.add_argument("--seconds", type=float, default=40)
    n.add_argument("--no-adlib", action="store_true")
    n.add_argument("--out", required=True)
    d = sub.add_parser("direct")
    d.add_argument("--hdd", default=default_hdd())
    d.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    d.add_argument("--mpu", action="store_true",
                   help="stub the MPU-401 routines 0002BF88/0002BFD9 (there is no MPU-401 in QEMU)")
    d.add_argument("--no-adlib", action="store_true",
                   help="no AdLib device in the guest: the detection finds nothing (status 0xFF)")
    d.add_argument("--out", required=True)
    args = ap.parse_args()
    return run_natural(args) if args.mode == "natural" else run_direct(args)


if __name__ == "__main__":
    raise SystemExit(main())
