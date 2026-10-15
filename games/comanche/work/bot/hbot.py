#!/usr/bin/env python3
"""Hatari session for the Comanche port (work/bot): launch, keys, state snapshots, frames.

N/A - target harness. State comes from the running program's own symbols
through Hatari's debugger (`parse` of a savebin script, run atomically
between emulation steps); input goes in as IKBD key events on the control
FIFO, so the game sees exactly what a player's keyboard would send.
"""
import os, pathlib, re, shutil, struct, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[2]          # F030Comanche
W = ROOT.parent
HATARI = pathlib.Path(os.environ.get("HATARI", W / "F030Arcade/third_party/hatari/build/src/hatari"))
FB2PNG = ROOT / "tools/fb2png.js"

# (name, symbol, bytes)
STATE = [
    ("flt", "flt_x", 24),            # x y angle turn fwd lat
    ("alt", "player_altitude", 1),
    ("coll", "flt_collective", 1),
    ("hull", "mission_wounded", 8),  # wounded, max
    ("dmg", "mission_damage", 8),
    ("fuel", "flt_fuel", 4),
    ("mend", "flt_mission_end", 2),
    ("iter", "flight_iteration", 4),
    ("obj", "object_table", 130 * 100),
    ("lock", "object_target_latch", 2),
    ("page", "instrument_page", 1),
    ("ammo", "weapon_ammo", 24),
    ("chaff", "mission_chaff", 2),
    ("flare", "mission_flare", 2),
    ("scr", "screen_active", 2),
    ("sid", "screen_id", 2),
    ("menu", "menu_open", 2),
    ("attr", "attract_active", 2),
    ("demo", "demo_active", 2),
    ("vbl", "frame_count", 4),
    ("view", "view_variant", 1),
    ("notch", "input_notch", 1),
    ("keys", "key_state", 128),
    ("pend", "input_pending", 2),
    ("evts", "input_events", 2),
    ("msg", "menu_message", 2),
    ("mcol", "menu_col", 2),
    ("mrow", "menu_row", 2),
    ("mready", "menu_ready", 2),
    ("ssel", "screen_sel", 2),
    ("scount", "screen_count", 2),
    ("ink", "screen_mission_ink", 10),
]

OBJ_SIZE = 100


def s32(b, o=0):
    return struct.unpack_from(">i", b, o)[0]


def u32(b, o=0):
    return struct.unpack_from(">I", b, o)[0]


def s16(b, o=0):
    return struct.unpack_from(">h", b, o)[0]


class Obj:
    def __init__(self, slot, b):
        self.slot = slot  # 1-based, as the target latch counts
        self.x = u32(b, 20)
        self.y = u32(b, 24)
        self.heading = b[36]
        self.active = b[37]
        self.alt = b[38]
        self.health = b[41]
        self.aux = b[53]
        self.goal = b[54]
        self.variant = b[55]
        self.targetable = b[58]
        self.state = u32(b, 8)

    def __repr__(self):
        return (f"#{self.slot} act={self.active} goal={self.goal} aux={self.aux} "
                f"hp={self.health} x={self.x>>22} y={self.y>>22} alt={self.alt} tg={self.targetable}")


class State:
    def __init__(self, raw):
        f = raw["flt"]
        self.x, self.y = u32(f, 0), u32(f, 4)
        self.angle = u32(f, 8)
        self.turn = s32(f, 12)
        self.fwd = s32(f, 16)
        self.lat = s32(f, 20)
        self.alt = raw["alt"][0]
        self.coll = raw["coll"][0]
        self.hull, self.hull_max = s32(raw["hull"], 0), s32(raw["hull"], 4)
        self.damage = list(raw["dmg"])
        self.fuel = s32(raw["fuel"])
        self.mission_end = s16(raw["mend"])
        self.iter = u32(raw["iter"])
        self.all = [Obj(i + 1, raw["obj"][i * OBJ_SIZE:(i + 1) * OBJ_SIZE]) for i in range(130)]
        self.objs = self.all[:30]
        self.lock = s16(raw["lock"])
        self.page = raw["page"][0]
        self.ammo = [s32(raw["ammo"], 4 * i) for i in range(6)]
        self.chaff = s16(raw["chaff"])
        self.flare = s16(raw["flare"])
        self.screen = s16(raw["scr"])
        self.screen_id = s16(raw["sid"])
        self.menu = s16(raw["menu"])
        self.attract = s16(raw["attr"])
        self.demo = s16(raw["demo"])
        self.vbl = u32(raw["vbl"])
        self.view = raw["view"][0]
        self.notch = raw["notch"][0]
        self.keys = raw["keys"]
        self.pending = s16(raw["pend"]) & 0xFFFF
        self.events = s16(raw["evts"]) & 0xFFFF
        self.message = s16(raw["msg"])
        self.menu_col = s16(raw["mcol"])
        self.menu_row = s16(raw["mrow"])
        self.menu_ready = s16(raw["mready"])
        self.sel = s16(raw["ssel"])
        self.count = s16(raw["scount"])
        self.ink = raw["ink"].decode("latin-1")

    @property
    def goals(self):
        return [o for o in self.objs if o.goal]

    @property
    def flying(self):
        return not self.screen and not self.attract and not self.demo

    def summary(self):
        g = self.goals
        return (f"vbl={self.vbl} it={self.iter} coll={self.coll} notch={self.notch} pos=({self.x>>22},{self.y>>22}) ang={self.angle>>23} "
                f"fwd={self.fwd} alt={self.alt} hull={self.hull}/{self.hull_max} fuel={self.fuel} "
                f"lock={self.lock} page={self.page} ammo={self.ammo} goals={sum(1 for o in g if o.active)}/{len(g)} "
                f"scr={self.screen}:{self.screen_id} attr={self.attract} demo={self.demo} menu={self.menu}")


class Session:
    def __init__(self, release, out, cpu="060", ff=True, prg="comanche_d.tos", extra=()):
        self.d = pathlib.Path(release).resolve()
        self.out = pathlib.Path(out).resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.snapdir = self.out / "snap"
        self.snapdir.mkdir(exist_ok=True)
        shutil.copy(self.d / prg, self.d / "BOT.TOS")
        self.fifo = self.out / "ctl.fifo"
        if self.fifo.exists():
            self.fifo.unlink()
        self.log = self.out / "dbg.txt"
        if self.log.exists():
            self.log.unlink()
        (self.d / "bot.ini").write_text(f"logfile {self.log}\nsymbols autoload exec\n")
        self.snap_ini = self.out / "snap.ini"
        lines = [f"savebin {self.snapdir}/{n}.bin {sym} ${ln:x}" for n, sym, ln in STATE]
        lines.append(f"savebin {self.snapdir}/done.bin frame_count $4")
        self.snap_ini.write_text("\n".join(lines) + "\n")
        if cpu == "060":
            tos = W / "F030Arcade/third_party/tos/etos512de.img"
            cpuopt = ["--cpulevel", "6", "--cpuclock", "32", "--fpu", "internal",
                      "--ttram", "64", "--addr24", "false"]
        else:
            tos = ROOT / "tools/toolchain/tos402.rom"
            cpuopt = ["--cpulevel", "3", "--cpuclock", "16", "--fpu", "none"]
        cmd = [str(HATARI), "--machine", "falcon", "--memsize", "14", "--tos", str(tos), *cpuopt,
               "--cpu-exact", "true", "--compatible", "true", "--patch-tos", "true",
               "--fast-boot", "true", "--dsp", "off", "--monitor", "rgb", "--frameskips", "0",
               "--sound", "off", "--fast-forward", "true" if ff else "false",
               "--disable-video", "on", "--confirm-quit", "off",
               "--cmd-fifo", str(self.fifo), "--parse", "bot.ini",
               "--log-file", str(self.out / "hatari.log"), "--alert-level", "fatal",
               "--debug-except", "bus,address,illegal,zerodiv,chk,trapv,privilege,linef,linea",
               "--harddrive", str(self.d), "--auto", "C:\\BOT.TOS", *extra]
        self.stdout = open(self.out / "stdout.txt", "w")
        self.p = subprocess.Popen(cmd, cwd=self.d, stdin=subprocess.DEVNULL,
                                  stdout=self.stdout, stderr=subprocess.STDOUT)
        t0 = time.time()
        while not self.fifo.exists():
            if time.time() - t0 > 30:
                raise RuntimeError("no control fifo")
            time.sleep(0.1)
        self.held = set()

    def alive(self):
        return self.p.poll() is None

    def send(self, line):
        with open(self.fifo, "w") as f:
            f.write(line + "\n")

    def down(self, code):
        if code not in self.held:
            self.send(f"hatari-event keydown 0x{code:02x}")
            self.held.add(code)

    def up(self, code):
        if code in self.held:
            self.send(f"hatari-event keyup 0x{code:02x}")
            self.held.discard(code)

    def hold(self, codes):
        """Make exactly `codes` (among a managed set) held."""
        for c in list(self.held):
            if c not in codes:
                self.up(c)
        for c in codes:
            self.down(c)

    def tap(self, code, t=0.12):
        self.send(f"hatari-event keydown 0x{code:02x}")
        time.sleep(t)
        self.send(f"hatari-event keyup 0x{code:02x}")
        time.sleep(0.05)

    def chord(self, mod, code, t=0.15):
        self.send(f"hatari-event keydown 0x{mod:02x}")
        time.sleep(0.05)
        self.send(f"hatari-event keydown 0x{code:02x}")
        time.sleep(t)
        self.send(f"hatari-event keyup 0x{code:02x}")
        time.sleep(0.05)
        self.send(f"hatari-event keyup 0x{mod:02x}")
        time.sleep(0.05)

    def state(self, timeout=10):
        done = self.snapdir / "done.bin"
        if done.exists():
            done.unlink()
        self.send(f"hatari-debug parse {self.snap_ini}")
        t0 = time.time()
        while not (done.exists() and done.stat().st_size == 4):
            if time.time() - t0 > timeout or not self.alive():
                return None
            time.sleep(0.01)
        raw = {}
        for n, _, ln in STATE:
            b = (self.snapdir / f"{n}.bin").read_bytes()
            if len(b) != ln:
                return None
            raw[n] = b
        return State(raw)

    def shot(self, name):
        before = self.log.stat().st_size if self.log.exists() else 0
        self.send("hatari-debug m $ffff8200 16")
        m = None
        for _ in range(100):
            new = self.log.read_text(errors="replace")[before:] if self.log.exists() else ""
            m = re.search(r"^FFFF8200: ((?:[0-9a-fA-F]{2} ){16})", new, re.M)
            if m:
                break
            time.sleep(0.05)
        if not m:
            return None
        bb = [int(x, 16) for x in m.group(1).split()]
        addr = (bb[1] << 16) | (bb[3] << 8) | bb[13]
        binf = self.out / f"{name}.bin"
        if binf.exists():
            binf.unlink()
        self.send(f"hatari-debug savebin {binf} ${addr:x} $25800")
        for _ in range(100):
            if binf.exists() and binf.stat().st_size == 0x25800:
                break
            time.sleep(0.05)
        ppm = self.out / f"{name}.ppm"
        subprocess.run(["node", str(FB2PNG), str(binf), str(ppm), "320", "240"], capture_output=True)
        png = self.out / f"{name}.png"
        subprocess.run(["magick", str(ppm), str(png)], capture_output=True)
        ppm.unlink(missing_ok=True)
        binf.unlink(missing_ok=True)
        return png

    def symbol(self, addr, cache={}):
        """Name of the code at addr, from the debugger's disassembly."""
        if addr in cache:
            return cache[addr]
        before = self.log.stat().st_size if self.log.exists() else 0
        self.send(f"hatari-debug d ${addr:x} 1")
        name = None
        for _ in range(60):
            new = self.log.read_text(errors="replace")[before:] if self.log.exists() else ""
            m = re.search(r"^([A-Za-z_.][\w.]*):\s*$", new, re.M)
            if m:
                name = m.group(1); break
            if re.search(rf"^0*{addr:x} ", new, re.M | re.I):
                name = f"${addr:x}"; break
            time.sleep(0.05)
        cache[addr] = name or f"${addr:x}"
        return cache[addr]

    def heightmap(self):
        """The loaded 1024x1024 height map (row-major, Y rows of X)."""
        f = self.out / "height.bin"
        if f.exists():
            f.unlink()
        self.send(f"hatari-debug savebin {f} original_height_map $100000")
        for _ in range(200):
            if f.exists() and f.stat().st_size == 0x100000:
                break
            time.sleep(0.05)
        return f.read_bytes()

    def close(self):
        try:
            self.send("hatari-shortcut quit")
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


# ST scancodes
K = dict(ESC=0x01, RET=0x1C, SPACE=0x39, TAB=0x0F, ALT=0x38, A=0x1E, Q=0x10,
         KP8=0x68, KP2=0x6E, KP4=0x6A, KP6=0x6C, KP5=0x6B, STAR=0x66,
         UP=0x48, DOWN=0x50, LEFT=0x4B, RIGHT=0x4D,
         Z=0x2C, X=0x2D, C=0x2E, V=0x2F, B=0x30, N=0x31,
         F1=0x3B, K1=0x02, K2=0x03, BS=0x0E, E=0x12, D=0x20, CHAFF=0x27, FLARE=0x28)
