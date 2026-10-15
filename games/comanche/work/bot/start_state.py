#!/usr/bin/env python3
"""Any mission's starting state on the port: the Falcon half of
work/trace_mission_start.py.

N/A - target harness. Boots the 060 image under the F030Arcade Hatari, walks
the menus with IKBD keys (Begin Mission, the campaign by its catalog row,
the first mission row, the briefing), and before Accept writes
briefing_mission - the row screen.s hands to mission_select - so any mission
starts whatever the roster has unlocked. A one-shot breakpoint on
object_update_done, the end of the mission's first object pass (the DOS
probe's 000234CE), saves the state the DOS probe dumps.

    python3 work/bot/start_state.py <campaign-row> <mission> <out-dir> [dos.json]

With the DOS probe's json, the slot fields the factory does not write and the
heading sine/cosine are first set to what the original held before its
factory ran (a breakpoint on object_spawn_mission), so the first object pass
starts from the same leftovers in both programs.
"""
import hashlib, json, pathlib, shutil, struct, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from hbot import Session, K, ROOT

DUMP = [("obj", "object_table", 31 * 100), ("flt", "flt_x", 8),
        ("alt", "player_altitude", 1), ("fuel", "mission_fuel", 4), ("fuel_live", "flt_fuel", 4),
        ("chaff", "mission_chaff", 2), ("flare", "mission_flare", 2),
        ("wounded", "mission_wounded", 8), ("stars", "mission_star_count", 2),
        ("targets", "mission_target_count", 2), ("endcue", "object_endcue_hold", 2),
        ("page", "instrument_page", 1), ("objects", "mission_object_count", 2),
        ("loads", "mission_loadout", 24), ("ammo", "weapon_ammo", 24),
        ("damage_table", "mission_damage", 8), ("rng", "flt_shake_rng", 4), ("frame", "flt_frame_x", 8),
        ("pub", "flt_pub_sin", 8), ("angle", "flt_angle", 4), ("palette", "resource_active_palett", 768),
        ("height", "original_height_map", 0x100000), ("colour", "original_colour_map", 0x100000)]


def wait_screen(s, sid, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = s.state()
        if st and st.screen and st.screen_id == sid:
            return st
        time.sleep(0.3)
    return None


def walk_to(s, row, key_up=K['UP'], key_down=K['DOWN']):
    st = s.state()
    for _ in range(12):
        if st.sel == row:
            return True
        s.tap(key_down if st.sel < row else key_up); time.sleep(0.4)
        st = s.state()
    return st.sel == row


# Port offset and width of each DOS slot field the factory leaves alone.
LEFTOVER = {"sprite": (43, 1), "variant": (55, 1), "steer": (52, 1), "timer": (40, 1),
            "prev_alt": (42, 1), "prev_x": (28, 4), "prev_y": (32, 4)}


def address(s, name):
    # `e` answers on Hatari's stdout, not the debugger log file.
    out = s.out / "stdout.txt"
    s.stdout.flush()
    before = out.stat().st_size
    s.send(f"hatari-debug e {name}")
    import re
    for _ in range(100):
        new = out.read_text(errors="replace")[before:]
        m = re.search(r"\$([0-9a-fA-F]+) \(hex\)", new)
        if m:
            return int(m.group(1), 16)
        time.sleep(0.05)
    raise SystemExit(f"no address for {name}")


def inject_ini(s, pre, path):
    table = address(s, "object_table")
    lines = []
    for slot in range(1, 32):
        for f, (off, n) in LEFTOVER.items():
            v = pre[f][slot]
            lines.append(f"w ${table + (slot - 1) * 100 + off:x} "
                         + " ".join(f"${b:02x}" for b in v.to_bytes(n, "big")))
    for f in ("pub_sin", "pub_cos"):
        a = address(s, f"flt_{f}")
        lines.append(f"w ${a:x} " + " ".join(f"${b:02x}" for b in (pre[f] & 0xFFFFFFFF).to_bytes(4, "big")))
    path.write_text("\n".join(lines) + "\n")
    # The Timer C PRNG as the original's pass began, set as the port's begins.
    a = address(s, "flt_shake_rng")
    (path.parent / "rng.ini").write_text(
        f"w ${a:x} " + " ".join(f"${b:02x}" for b in pre["rng"].to_bytes(4, "big")) + "\n")


def main():
    crow, mission, out = int(sys.argv[1]), int(sys.argv[2]), pathlib.Path(sys.argv[3])
    pre = json.load(open(sys.argv[4]))["pre"] if len(sys.argv) > 4 else None
    rel = ROOT / "release/68060"
    nam = rel / "COMANCHE.NAM"
    keep = nam.read_bytes()
    s = Session(str(rel), out)
    dumpdir = out / "start"
    if dumpdir.exists():
        shutil.rmtree(dumpdir)
    dumpdir.mkdir()
    ini = out / "start.ini"
    ini.write_text("".join(f"savebin {dumpdir}/{n}.bin {sym} ${ln:x}\n" for n, sym, ln in DUMP)
                   + f"savebin {dumpdir}/done.bin frame_count $4\n")
    try:
        time.sleep(6); s.tap(K['SPACE']); time.sleep(2)
        st = wait_screen(s, 0)
        if not st or not walk_to(s, 0):
            raise SystemExit("main menu not reached")
        s.tap(K['RET']); time.sleep(2)
        if not wait_screen(s, 1) or not walk_to(s, crow):
            raise SystemExit("campaign screen not reached")
        s.tap(K['RET']); time.sleep(2)
        if not wait_screen(s, 2) or not walk_to(s, 0):
            raise SystemExit("mission screen not reached")
        s.tap(K['RET']); time.sleep(2)
        if not wait_screen(s, 7):
            raise SystemExit("briefing not reached")
        s.send(f"hatari-debug w briefing_mission 0 {mission}")
        if pre:
            inject_ini(s, pre, out / "inject.ini")
            s.send(f"hatari-debug b pc = object_spawn_mission :once :trace :file {out / 'inject.ini'}")
            s.send(f"hatari-debug b pc = object_update_pass :once :trace :file {out / 'rng.ini'}")
        s.send(f"hatari-debug b pc = object_update_done :once :trace :file {ini}")
        time.sleep(0.5)
        s.tap(K['RET'])
        t0 = time.time()
        while not ((dumpdir / "done.bin").exists() and (dumpdir / "done.bin").stat().st_size == 4):
            if time.time() - t0 > 60:
                raise SystemExit("the mission never started")
            time.sleep(0.2)
        time.sleep(0.5)
        raw = {n: (dumpdir / f"{n}.bin").read_bytes() for n, _, _ in DUMP}
    finally:
        s.close()
        nam.write_bytes(keep)
    be = lambda f, b: struct.unpack(">" + f, b)
    st = {
        "x": be("I", raw["flt"][0:4])[0], "y": be("I", raw["flt"][4:8])[0], "alt": raw["alt"][0],
        "fuel": be("i", raw["fuel"])[0], "fuel_live": be("i", raw["fuel_live"])[0],
        "chaff": be("h", raw["chaff"])[0], "flare": be("h", raw["flare"])[0],
        "wounded": be("i", raw["wounded"][:4])[0], "wounded_max": be("i", raw["wounded"][4:])[0],
        "stars": be("h", raw["stars"])[0], "endcue": be("h", raw["endcue"])[0],
        "targets": be("h", raw["targets"])[0], "page": raw["page"][0],
        "objects": be("h", raw["objects"])[0],
        "loads": list(be("6i", raw["loads"])), "ammo": list(be("6i", raw["ammo"])),
        "damage_table": list(raw["damage_table"]), "palette_raw": raw["palette"].hex(),
        "height_sha1": hashlib.sha1(raw["height"]).hexdigest(),
        "colour_sha1": hashlib.sha1(raw["colour"]).hexdigest(),
        "frame_x": be("I", raw["frame"][:4])[0], "frame_y": be("I", raw["frame"][4:])[0],
        "pub_sin": be("i", raw["pub"][:4])[0], "pub_cos": be("i", raw["pub"][4:])[0],
        "angle": be("I", raw["angle"])[0], "rng": be("I", raw["rng"])[0],
        "mission": mission, "campaign_row": crow,
    }
    objs = []
    for i in range(31):
        b = raw["obj"][i * 100:(i + 1) * 100]
        u = lambda o: struct.unpack_from(">I", b, o)[0]
        objs.append(dict(speed=u(0), draw=u(4), state=u(8), model_a=u(12), model_b=u(16),
                         x=u(20), y=u(24), prev_x=u(28), prev_y=u(32), heading=b[36],
                         active=b[37], alt=b[38], timer=b[40], health=b[41], sprite=b[43],
                         steer=b[52], aux=b[53], flag=b[54], variant=b[55], f9=b[56],
                         damage=b[57], hold=u(60), fire=u(88)))
    st["slots"] = objs
    (out / "start.json").write_text(json.dumps(st, indent=1))
    print(f"wrote {out / 'start.json'}")


if __name__ == "__main__":
    main()
