#!/usr/bin/env python3
"""Compare a DAC dump taken from the running DOS game against every candidate
resource palette, and say which one it is.

The dump is 768 bytes of six-bit components straight off the VGA DAC, so a
resource palette has to be shifted right two to be comparable: res_open_e's
0x0C path stores `shr al,2` of the file's eight-bit components.

    python3 tools/compare-dac.py tools/dosbox/PAL.BIN
"""
import struct, sys, glob, os

def dta_palette(path):
    d = open(path, "rb").read()
    if d[:8] != b"Kyle DTA":
        return None
    w = struct.unpack("<H", d[8:10])[0] + 1
    h = struct.unpack("<H", d[10:12])[0] + 1
    produced, i = 0, 128
    while produced < w * h and i < len(d):
        b = d[i]; i += 1
        if b >= 0xC0:
            if i >= len(d): return None
            produced += b & 0x3F; i += 1
        else:
            produced += 1
    if i >= len(d) or d[i] != 0x0C or i + 769 > len(d):
        return None
    return [c >> 2 for c in d[i + 1 : i + 769]]

def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"{path} does not exist yet.\n")
        print("It is written by PALTSR.COM, which capture-dac.conf runs twice:")
        print("once before the game to install a timer hook that samples the")
        print("DAC while it runs, and once after to write what it captured.\n")
        print("If it is missing, the session did not reach the second run -")
        print("usually because the DOSBox window was closed while the game was")
        print("still up. Quit the game so you land back at the DOS prompt and")
        print("let the session finish at its pause.")
        return 1
    dump = open(path, "rb").read()
    if len(dump) < 768:
        print(f"{path}: {len(dump)} bytes, expected 768")
        return 1
    dac = list(dump[:768])
    root = "assets/extracted/comanche_hdd"
    rows = []
    for path in sorted(glob.glob(os.path.join(root, "*.DTA"))):
        pal = dta_palette(path)
        if pal is None:
            continue
        exact = sum(1 for a, b in zip(dac, pal) if a == b)
        close = sum(1 for a, b in zip(dac, pal) if abs(a - b) <= 1)
        rows.append((exact, close, os.path.basename(path)))
    rows.sort(reverse=True)
    print(f"{'resource':14} {'exact/768':>10} {'within 1':>10}")
    for exact, close, name in rows[:12]:
        print(f"  {name:12} {exact:10} {close:10}")
    if not rows:
        print("\nno resource carries a palette")
        return 1

    best, _, name = rows[0]
    runner = rows[1][0] if len(rows) > 1 else 0
    # A dump taken after the game exits has its first 64 entries overwritten by
    # the BIOS text-mode reset, so a genuine match can be as low as 576/768.
    # What identifies it is the margin over everything else, and that the
    # mismatches form one contiguous run at the bottom of the palette.
    if best > 700:
        print(f"\nthe DAC holds {name}'s palette")
    elif best > 400 and best > runner * 4:
        pal = dta_palette(os.path.join(root, name))
        bad = [k for k in range(256) if dac[k * 3:k * 3 + 3] != pal[k * 3:k * 3 + 3]]
        contiguous = bad == list(range(bad[0], bad[-1] + 1)) if bad else True
        print(f"\nthe DAC holds {name}'s palette, with {len(bad)} entries overwritten")
        if contiguous and bad:
            print(f"entries {bad[0]}-{bad[-1]} differ, one contiguous run - that is the")
            print("BIOS text-mode reset, so this dump was taken after the game exited.")
            print("The rest matches exactly, which is enough to identify it.")
    else:
        print("\nno resource palette matches the dump")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
