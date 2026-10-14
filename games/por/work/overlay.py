#!/usr/bin/env python3
"""Turbo Pascal overlay directory: partition GAME.OVR using START.EXE.

Each overlaid Pascal unit keeps a small resident *stub segment* in START.EXE.
Layout, verified against all 38 units (see analysis/executables.md):

    +0x00  CD 3F 00 00     INT 3Fh, DW 0000 — the "load this unit" stub
    +0x04  u32LE fileOffset    start of the unit's code inside GAME.OVR
    +0x08  u16LE codeSize
    +0x0A  u16LE fixupSize     bytes of segment-fixup table after the code
    +0x0C  u16LE entryCount    number of 5-byte thunks at +0x20
    +0x0E  u16LE               TBD
    +0x10  16 B zero
    +0x20  entryCount x (CD 3F, u16LE offsetInUnit, 00)

Chain invariant, exact for all 38 units:
    fileOffset + codeSize + fixupSize == fileOffset(next unit)
and the last unit ends exactly at the end of GAME.OVR.
"""
import struct, os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
EXPANDED = os.path.join(HERE, "expanded")
HDR_MAGIC = bytes([0xCD, 0x3F, 0x00, 0x00])


def load_image(path):
    d = open(path, "rb").read()
    return d[struct.unpack_from("<H", d, 8)[0] * 16:]


def units(start_exe=None, game_ovr=None):
    img = load_image(start_exe or os.path.join(EXPANDED, "START.EXE"))
    ovr_size = os.path.getsize(game_ovr or os.path.join(EXPANDED, "GAME.OVR"))
    out = []
    for seg in range(len(img) // 16):
        a = seg * 16
        if img[a:a + 4] != HDR_MAGIC:
            continue
        fo, = struct.unpack_from("<I", img, a + 4)
        code, fixup, entries, unk = struct.unpack_from("<HHHH", img, a + 8)
        if fo >= ovr_size or fo + code + fixup > ovr_size:
            continue
        thunks = []
        for i in range(entries):
            t = a + 0x20 + i * 5
            if img[t:t + 2] != bytes([0xCD, 0x3F]):
                break
            thunks.append(struct.unpack_from("<H", img, t + 2)[0])
        out.append(dict(seg=seg, file_offset=fo, code_size=code, fixup_size=fixup,
                        entry_count=entries, unknown=unk, thunks=thunks))
    out.sort(key=lambda u: u["file_offset"])
    return out, ovr_size


def main():
    us, ovr_size = units()
    ok = 0
    for i, u in enumerate(us):
        end = u["file_offset"] + u["code_size"] + u["fixup_size"]
        nxt = us[i + 1]["file_offset"] if i + 1 < len(us) else ovr_size
        ok += end == nxt
    print(f"{len(us)} overlay units; chain exact for {ok}/{len(us)}; "
          f"covers 0..{us[-1]['file_offset'] + us[-1]['code_size'] + us[-1]['fixup_size']} "
          f"of {ovr_size} B")
    print(f"{'seg':>4} {'fileOff':>8} {'code':>7} {'fixup':>6} {'entries':>7} {'+14':>5}")
    for u in us:
        print(f"{u['seg']:4X} {u['file_offset']:8d} {u['code_size']:7d} "
              f"{u['fixup_size']:6d} {u['entry_count']:7d} {u['unknown']:5d}")
    tot = sum(u["code_size"] for u in us)
    print(f"total code {tot} B, fixups {sum(u['fixup_size'] for u in us)} B, "
          f"{sum(u['entry_count'] for u in us)} entry thunks")
    if len(sys.argv) > 1:
        json.dump(us, open(sys.argv[1], "w"), indent=1)
        print(f"wrote {sys.argv[1]}")


if __name__ == "__main__":
    main()
