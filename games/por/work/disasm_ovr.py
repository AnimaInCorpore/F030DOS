#!/usr/bin/env python3
"""Disassemble GAME.OVR unit by unit, seeded from the overlay directory.

Each Turbo Pascal overlay unit is a self-contained code image. Its entry points
are exactly the thunk offsets recorded in that unit's resident stub segment in
START.EXE, so this is a seeded recursive descent, not a blind linear sweep.

The unit's fixup table (a list of in-unit offsets holding segment words) is fed
to the walker as relocations so fixup targets are never decoded as opcodes.

    python3 work/disasm_ovr.py [out.txt]
"""
import os, sys, struct, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from disasm import Image, walk, INT21                          # noqa: E402
from overlay import units                                      # noqa: E402

EXPANDED = os.path.join(HERE, "expanded")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "work/game16.txt"
    ovr = open(os.path.join(EXPANDED, "GAME.OVR"), "rb").read()
    us, _ = units()

    tot_code = tot_seen = tot_ins = tot_fn = 0
    ints = collections.Counter()
    ports = collections.Counter()
    farcalls = collections.Counter()
    rows = []
    with open(out, "w") as fh:
        fh.write("; GAME.OVR — per-unit seeded recursive descent\n")
        fh.write("; 38 Turbo Pascal overlay units; entry points are the resident\n")
        fh.write("; INT 3Fh thunk offsets recorded in START.EXE (work/overlay.py)\n")
        for u in us:
            fo, cs, fx = u["file_offset"], u["code_size"], u["fixup_size"]
            code = ovr[fo:fo + cs]
            fixups = set()
            for i in range(fx // 2):
                v, = struct.unpack_from("<H", ovr, fo + cs + 2 * i)
                if v < cs:
                    fixups.add(v)
            seeds = [t for t in u["thunks"] if t < cs]
            img = Image(code, fo, fixups, f"unit {u['seg']:03X}")
            seen, starts, insns, calls, fc, it, po, th = walk(img, seeds)
            tot_code += cs; tot_seen += len(seen); tot_ins += len(insns); tot_fn += len(starts)
            ints.update(it); ports.update(po); farcalls.update(fc)
            pct = 100 * len(seen) // cs if cs else 0
            rows.append((u["seg"], cs, len(seeds), len(starts), len(insns), pct))
            fh.write(f"\n\n;=== unit {u['seg']:03X}: GAME.OVR {fo}..{fo+cs} "
                     f"({cs} B), {len(seeds)} entry thunks, "
                     f"{len(insns)} insns, {pct}% covered ===\n")
            for pc in sorted(insns):
                size, text, m = insns[pc]
                if pc in starts:
                    fh.write(f"\n; -- {u['seg']:03X}:{pc:04X} (GAME.OVR {fo+pc:06X})"
                             f"{'  [ENTRY]' if pc in seeds else ''}\n")
                fh.write(f"{u['seg']:03X}:{pc:04X}  {code[pc:pc+size].hex():<14s} {text}\n")

    print(f"GAME.OVR: {tot_ins} instructions, {tot_fn} routines, "
          f"{tot_seen}/{tot_code} code bytes covered ({100*tot_seen//tot_code}%) -> {out}")
    print(f"{'unit':>5} {'code':>7} {'seeds':>6} {'fns':>5} {'insns':>7} {'cov':>4}")
    for seg, cs, sd, fn, ins, pct in rows:
        print(f"{seg:5X} {cs:7d} {sd:6d} {fn:5d} {ins:7d} {pct:3d}%")
    if ints:
        print("\ninterrupts:")
        for (v, ah), c in sorted(ints.items(), key=lambda x: -x[1])[:14]:
            note = f" AH={ah:02X} {INT21.get(ah, '?')}" if v == 0x21 and ah is not None else ""
            print(f"  int {v:02X}h{note}  x{c}")
    if ports:
        print("port I/O:", dict(ports.most_common(12)))


if __name__ == "__main__":
    main()
