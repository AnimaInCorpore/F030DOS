#!/usr/bin/env python3
"""Compare a mission's starting state, original (work/trace_mission_start.py)
against port (work/bot/start_state.py).

N/A - target harness. Scalars are compared as values; the 31 object slots
field by field for every slot the original has active (an inactive slot's
other fields are whatever the slot held before, in both programs). Handler
and bank pointers cannot be equal across two machines, so they are compared
as a mapping: each original address must pair with one port symbol, the same
one in every slot and every mission, and each bank pointer with the same
mission sprite slot.

    python3 work/bot/compare_start.py dos.json port.json [pairs.json]
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
import importlib.util as iu

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = iu.spec_from_file_location("tossym", ROOT / "tools/tos-symbols.py")
_m = iu.module_from_spec(_spec); _spec.loader.exec_module(_m)
SYMS = _m.read_symbols(ROOT / "release/68060/comanche_d.tos")
BYVAL = {}
for n, v in SYMS.items():
    if not n.startswith("."):
        BYVAL.setdefault(v, n)

SCALARS = ["x", "y", "alt", "fuel", "fuel_live", "chaff", "flare", "wounded", "wounded_max",
           "stars", "targets", "page", "objects", "loads", "ammo", "damage_table",
           "palette_raw", "height_sha1", "colour_sha1", "frame_x", "frame_y", "pub_sin", "pub_cos",
           "angle"]
FIELDS = ["heading", "active", "sprite", "alt", "damage", "aux", "steer", "flag", "variant",
          "f9", "health", "speed", "x", "y", "prev_x", "prev_y", "hold"]
POINTERS = ["draw", "state", "fire"]


def main():
    dos = json.load(open(sys.argv[1])); port = json.load(open(sys.argv[2]))
    pairs_file = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else None
    pairs = json.load(open(pairs_file)) if pairs_file and pairs_file.exists() else {}
    bad = []
    for k in SCALARS:
        if dos[k] != port[k]:
            bad.append(f"{k}: dos={str(dos[k])[:80]} port={str(port[k])[:80]}")
    # Text base: the fixed slot's state handler is object_state_fixed.
    base = port["slots"][30]["state"] - SYMS["object_state_fixed"]
    banks = base + SYMS["mission_sprite_banks"]
    ob = dos["objects_by_field"]
    for slot in range(1, 32):
        p = port["slots"][slot - 1]
        if ob["active"][slot] != p["active"]:
            bad.append(f"slot {slot} active: dos={ob['active'][slot]} port={p['active']}")
            continue
        if not ob["active"][slot]:
            continue
        for f in FIELDS:
            if ob[f][slot] != p[f]:
                bad.append(f"slot {slot} {f}: dos={ob[f][slot]} port={p[f]}")
        for f in POINTERS:
            d, q = ob[f][slot], p[f]
            name = BYVAL.get(q - base, f"?{q - base:x}") if q else "0"
            key = f"{f}:{d:08x}"
            if pairs.setdefault(key, name) != name:
                bad.append(f"slot {slot} {f}: dos {d:08x} pairs with {pairs[key]} elsewhere, {name} here")
        for f in ("model_a", "model_b"):
            d = ob[f][slot]
            ds = dos["sprite_slots"].index(d) if d in dos["sprite_slots"] else None
            q = p[f] - banks
            ps = q // 168000 if 0 <= q < 10 * 168000 else None   # bank base + its fixed header offset
            if ds != ps:
                bad.append(f"slot {slot} {f}: dos sprite slot {ds} port {ps}")
    if pairs_file:
        pairs_file.write_text(json.dumps(pairs, indent=1, sort_keys=True))
    tag = f"c{dos['campaign']}m{dos['mission']}"
    # The Timer C PRNG is set equal as both passes begin; a timer tick inside
    # either pass moves it there and only there, so it is reported, not judged.
    note = "" if dos.get("rng") == port.get("rng") else " (a Timer C tick moved the PRNG inside one pass)"
    if bad:
        print(f"{tag}: {len(bad)} differences{note}")
        for b in bad:
            print("  " + b)
        return 1
    print(f"{tag}: identical ({sum(dos['objects_by_field']['active'][1:32])} objects){note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
