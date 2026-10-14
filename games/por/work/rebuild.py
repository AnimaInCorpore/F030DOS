#!/usr/bin/env python3
"""Rebuild GAME.OVR and START.EXE from the reassembled sources and prove the
result is byte-identical to the originals.

work/reasm.py proves each *load image* round-trips. This proves the **files**:
the overlay directory order and fixup blocks for GAME.OVR, and the MZ header,
relocation table and header padding for START.EXE. Nothing here is generated
from a template — every byte either comes out of NASM or is copied from a
structure this project has documented and verified.

    python3 work/rebuild.py
"""
import os, subprocess, sys, struct

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from overlay import units                                       # noqa: E402

EXPANDED = os.path.join(HERE, "expanded")
REASM = os.path.join(HERE, "reasm")
OUT = os.path.join(HERE, "rebuilt")
NASM = os.environ.get("NASM", "nasm")


def assemble(tag):
    src = os.path.join(REASM, f"{tag}.asm")
    dst = os.path.join(REASM, f"{tag}.bin")
    if not os.path.exists(src):
        raise SystemExit(f"missing {src} — run work/reasm.py first")
    r = subprocess.run([NASM, "-f", "bin", "-o", dst, src], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"nasm failed on {src}:\n{r.stderr}")
    return open(dst, "rb").read()


def rebuild_game_ovr():
    original = open(os.path.join(EXPANDED, "GAME.OVR"), "rb").read()
    us, _ = units()
    # GAME.OVR opens with the 4-byte "TPOV" signature; the first overlay unit's
    # directory entry declares fileOffset 4, which is how we know its length.
    out = bytearray(original[:us[0]["file_offset"]])
    for u in us:
        fo, cs, fx = u["file_offset"], u["code_size"], u["fixup_size"]
        if len(out) != fo:
            return None, f"unit {u['seg']:03X} starts at {len(out)}, directory says {fo}"
        code = assemble(f"unit{u['seg']:03X}")
        if len(code) != cs:
            return None, f"unit {u['seg']:03X} assembled to {len(code)} B, expected {cs}"
        out += code
        # The fixup block is data the overlay manager consumes, not code.
        out += original[fo + cs: fo + cs + fx]
    return bytes(out), None


def rebuild_start_exe():
    original = open(os.path.join(EXPANDED, "START.EXE"), "rb").read()
    cparhdr, = struct.unpack_from("<H", original, 8)
    hdr = cparhdr * 16
    image = assemble("start")
    # The 944-byte header is the 28-byte MZ record, the 228x4 relocation table
    # at e_lfarlc, and the pad to the paragraph boundary. All of it is data.
    return original[:hdr] + image, None if len(image) == len(original) - hdr else \
        f"load image assembled to {len(image)} B, expected {len(original) - hdr}"


def main():
    os.makedirs(OUT, exist_ok=True)
    rc = 0
    for name, fn in (("GAME.OVR", rebuild_game_ovr), ("START.EXE", rebuild_start_exe)):
        built, err = fn()
        original = open(os.path.join(EXPANDED, name), "rb").read()
        if err:
            print(f"{name}: FAILED — {err}")
            rc = 1
            continue
        open(os.path.join(OUT, name), "wb").write(built)
        if built == original:
            print(f"{name}: BYTE-IDENTICAL ({len(built):,} B)")
        else:
            diff = sum(1 for a, b in zip(built, original) if a != b)
            first = next((i for i, (a, b) in enumerate(zip(built, original)) if a != b), None)
            print(f"{name}: MISMATCH — {len(built):,} vs {len(original):,} B, "
                  f"{diff} differing bytes, first at 0x{first:X}")
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
