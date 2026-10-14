#!/usr/bin/env python3
"""Check the port's target-view marcher against the original's own occlusion.

The port's 0001B26C is modelled here in Python from src/render.s and driven by
the camera the ORIGINAL used, captured at 0000790E - the instruction after
00007909's `call 0x1b26c`, so the marcher has just finished and 00007913 has
not yet popped the substituted camera back. The ground truth is the original's
own archive: 0001B84E writes each step's 80-byte occlusion to
[0x19E60] + ring*256 + 0x58, three ring slots per step.

    python work/dump_marcher_tables.py --break-at 0x790E --surface \
        --silhouette --heightmap --wait-flight 150 --outdir work/mfd_out
    python work/compare_mfd_march.py work/mfd_out

N/A - target artefact: a parity harness, not a DOS routine.
"""
import json
import os
import sys

MASK32 = 0xFFFFFFFF


def s32(v):
    v &= MASK32
    return v - (1 << 32) if v & 0x80000000 else v


def high32(a, b):
    """high 32 bits of the signed 64-bit product - the 68030 muls.l d3,d1:d0."""
    return (s32(a) * s32(b)) >> 32 & MASK32


def check_bearings(d, root):
    """Check object_aspect's octant bearing against the original's own bytes.

    00024CBA stores the bearing for every object the pass walks into
    [ecx + 0x21CAF], and the capture reads that array back with the object
    positions and the camera the pass ran with - [0x19CDC]/[0x19CE0], latched
    at 0000D3CA before the renderer, because 0000D413 advances [0x19CD4]
    afterwards. Slots the walk never reaches keep a stale byte: 00024BCB
    counts 0x82 down to 1, so slot 0 is never visited, and an inactive slot
    fails 00024BE8 before the handler runs.
    """
    import struct
    raw = open(os.path.join(root, "re", "unpacked", "comanche-flat32.bin"),
               "rb").read()
    octants = struct.unpack_from("<8I", raw, 0x22385)
    corr = raw[0x223A5:0x223A5 + 2048]
    st = d["state"]
    vx, vy = st["frame_x_0x19CDC"], st["frame_y_0x19CE0"]

    def bearing(ox, oy):
        dy = (vy - oy) & MASK32
        ysign = 1 if dy & 0x80000000 else 0
        my = (~dy) & MASK32 if ysign else dy
        dx = (vx - ox) & MASK32
        xsign = 1 if dx & 0x80000000 else 0
        mx = (~dx) & MASK32 if xsign else dx
        oct_i = (ysign << 2) | (xsign << 1)
        if mx > my:
            lo, hi = my, mx
        else:
            oct_i |= 1
            lo, hi = mx, my
        b = octants[oct_i]
        q = hi >> 10                              # 00024C92 shr ebp, 0xa
        if q:                                     # 00024C95 je
            b = (b & ~0xFF) | ((b ^ corr[lo // q]) & 0xFF)
        return (~((b + 1) >> 1)) & 0xFF           # 00024CA3/00024CB8

    X = d["target_x_0x20C6C"]
    Y = d["target_y_0x20E74"]
    stored = d["target_bear_0x21CAF"]
    ok = bad = 0
    for i in range(min(len(X), len(stored))):
        if X[i] == 0x40000000:                    # an unplaced slot
            continue
        want = stored[i]
        got = bearing(X[i], Y[i])
        if got == want:
            ok += 1
        else:
            bad += 1
            print(f"  slot {i:2d} at ({X[i] >> 22:4d},{Y[i] >> 22:4d}): "
                  f"stored {want:3d}, model {got:3d}")
    print(f"bearings: {ok} match, {bad} differ "
          f"(slot 0 and unplaced slots keep a stale byte)")


def main(outdir):
    d = json.load(open(os.path.join(outdir, "marcher-5.json"), encoding="utf-8"))
    st = d["state"]
    A = d["dtl_forward_0x1A2CC"]
    B = d["dtl_lateral_0x19EE4"]
    rings = st["ring_count_0x19EE0"]
    sin = st["sin_0x19CB0"]
    cos = st["cos_0x19CB4"]
    alt = st["altitude_0x19DFC"]
    cx = st["camera_x_0x19CD4"]
    cy = st["camera_y_0x19CD8"]

    pages = open(os.path.join(outdir, d["pages_file"]), "rb").read()
    height = open(os.path.join(outdir, d["heightmap_file"]), "rb").read()
    sil = open(os.path.join(outdir, d["silhouettes_file"]), "rb").read()

    camh = ((~alt) & 0xFF) >> 1          # 0001B2D5 `not al / shr al,1`
    print(f"rings={rings} alt={alt} camh={camh} "
          f"cam=({cx:#010x},{cy:#010x}) sin={sin:#010x} cos={cos:#010x}")

    occl = [0] * 80
    ai = bi = pi = 0
    steps = rings // 3
    matched = total = 0
    first_bad = None
    for k in range(steps):
        a = (A[ai] + A[ai + 1]) & MASK32
        ai += 3
        cx = (cx + high32(a, sin)) & MASK32
        cy = (cy - high32(a, cos)) & MASK32
        b = (B[bi] * 2) & MASK32
        bi += 3
        lat_y = high32(b, sin)
        lat_x = high32(b, cos)
        page = pi * 256
        pi += 3

        for start_x, start_y, col0, step in (
                (cx, cy, 38, -2),
                ((cx + lat_x) & MASK32, (cy + lat_y) & MASK32, 40, +2)):
            x, y, col = start_x, start_y, col0
            dx = -lat_x if step < 0 else lat_x
            dy = -lat_y if step < 0 else lat_y
            for _ in range(20):
                idx = ((x >> 22) & 0x3FF) | (((y >> 22) & 0x3FF) << 10)
                p = pages[page + ((height[idx] + camh) & 0xFF)]
                if p > occl[col]:
                    occl[col] = p
                    occl[col + 1] = p
                x = (x + dx) & MASK32
                y = (y + dy) & MASK32
                col += step

        want = list(sil[(3 * k) * 256 + 0x58:(3 * k) * 256 + 0x58 + 80])
        same = sum(1 for i in range(80) if want[i] == occl[i])
        matched += same
        total += 80
        if same != 80 and first_bad is None:
            first_bad = k
            print(f"  first mismatch at step {k} (ring {3*k}): {same}/80")
            print(f"    dos  {want[:16]}")
            print(f"    port {occl[:16]}")
    print(f"{matched}/{total} column-steps match "
          f"({100.0 * matched / total:.1f}%)")
    final = list(sil[(3 * (steps - 1)) * 256 + 0x58:][:80])
    print("dos  final:", final[:20])
    print("port final:", occl[:20])
    check_bearings(d, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "work/mfd_out"))
