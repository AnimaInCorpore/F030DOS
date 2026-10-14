#!/usr/bin/env python3
"""Print the digital layer's request log (src/sound.s snd_log_buf) dumped from Hatari.

N/A - target artefact: a debugging aid, no DOS routine.
Record: analysis/functions/sound-falcon.md#verification

    savebin log.bin snd_log_buf $2000      (Hatari debugger, e.g. a `b VBL = N :file` action)
    savebin cnt.bin snd_log_count 4
    python3 tools/decode-sound-log.py log.bin cnt.bin [--summary]

Each 16-byte record: kind, bl, dl, id (ebp / al), ecx, eax, VBL count (big-endian
longs). The kinds are K_* of src/sound.s. --summary prints one line per distinct
(kind, arguments) with its count and first VBL instead of the whole list.
"""
import struct
import sys

KINDS = {1: "fx", 2: "speech_a", 3: "speech_b", 4: "voice", 5: "mode", 6: "reset", 7: "rate", 8: "start"}
ENTRIES = 512


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    summary = "--summary" in sys.argv
    log = open(args[0], "rb").read()
    count = struct.unpack(">I", open(args[1], "rb").read()[:4])[0]
    first = max(0, count - ENTRIES)
    rows = []
    for n in range(first, count):
        rec = log[(n % ENTRIES) * 16:(n % ENTRIES) * 16 + 16]
        kind, bl, dl, ident, ecx, eax, vbl = struct.unpack(">BBBBIII", rec)
        rows.append((n, KINDS.get(kind, f"?{kind}"), bl, dl, ident, ecx, eax, vbl))
    print(f"{count} requests logged" + (f", the last {ENTRIES} kept" if count > ENTRIES else ""))
    if not summary:
        for n, kind, bl, dl, ident, ecx, eax, vbl in rows:
            print(f"#{n:5d} VBL {vbl:6d}  {kind:9s} id/al {ident:3d} bl {bl:02X} dl {dl} ecx {ecx:08X} eax {eax:08X}")
        return
    seen = {}
    for n, kind, bl, dl, ident, ecx, eax, vbl in rows:
        if kind in ("fx",):
            key = (kind, f"id {ident} bl {bl:02X} dl {dl} ecx {ecx:#x}")
        elif kind in ("speech_a", "speech_b"):
            key = (kind, f"id {eax & 0xFF}")
        elif kind == "voice":
            key = (kind, f"slot {bl} dl {dl} ecx {ecx:#x}")
        elif kind in ("mode", "rate"):
            key = (kind, f"al {eax & 0xFF:02X}")
        else:
            key = (kind, "")
        entry = seen.setdefault(key, [0, vbl])
        entry[0] += 1
    for (kind, text), (n, vbl) in sorted(seen.items(), key=lambda kv: kv[1][1]):
        print(f"{kind:9s} {text:40s} x{n:<5d} first at VBL {vbl}")


if __name__ == "__main__":
    main()
