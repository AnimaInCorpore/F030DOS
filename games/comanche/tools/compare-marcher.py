#!/usr/bin/env python3
"""Compare a model of the DOS marcher (0000D950) against the original's own
per-column occlusion, captured out of the running game.

STATUS: the model reproduces the original exactly - 17024/17024 columns over
all 152 non-uniform rings of a captured frame, every ring 112/112 with max|e|
of 0. So 0000D950 is now a solved routine and this file is its executable
statement.

Getting there needed one thing that is not a modelling detail at all: the
capture has to be taken at a known instruction. work/dump_marcher_tables.py
froze the machine with QMP `stop`, which is atomic but not phase-coherent -
the frame driver latches, renders, then integrates, so an arbitrary freeze
can pair one frame's camera with another frame's silhouettes. That is
invisible in the shape of the data and showed up only as a model that was
right in form and wrong in numbers, scoring anywhere between 4.8% and 16.1%
with nothing changed but where the freeze landed. Eight structural
hypotheses were tested and eliminated against those scores; none of them was
the fault. Stopping at 0000F317 - the marcher's own `ret`, via QEMU's
gdbstub, `--at-marcher` - took the same model from 16.1% to 100.0% with no
change to the model at all.

The lesson worth carrying: when a model is right in shape and wrong in
numbers, suspect the measurement before the model.

Structurally everything else has been eliminated by measurement: the right
renderer runs ([0x19C94] = 0xD950, since [0x25DD9] is '}'), the marcher is
not self-modified, the 192 column sites map to indices 95..0 then 96..191,
the step order and the turn are as modelled, the page buffer is 256-aligned
and the height map is the one at [0x19E6C].

THE REFERENCE IS ALSO ONLY 112 COLUMNS WIDE, and that is the whole story of why
this looked broken for a while.

0000F2F1 writes the main view's finished 192-byte occlusion to
[0x19E60] + ring*256 + 0x20. Then sub_0001B26C - the side/rear view's own
marcher, called from 00007909 - writes ITS silhouette to the same region at
0001B84E, at + 0x58, for 0x14 dwords = 80 bytes. Byte offsets 0x58..0xA7 are
array indices 56..135, so the middle 80 columns of every ring's reference are
the rear view's, not the main view's.

192 - 80 = 112 usable columns: indices 0..55 and 136..191. Scoring all 192
mixes two different views and produces a number that measures the overlap.

(The rest of the rear-view path is harmless: 00007903 rewrites [0x19D00],
000078FA subtracts from the camera X, and the derived basis in
[0x19CB0]/[0x19CB4] goes stale - but 00007913-0000793D pops every one of them
back, including the basis pair. A sample only sees inconsistent registers if
it lands inside that window, which VALID_COLUMNS does not depend on.)

Inputs, all captured by work/dump_marcher_tables.py and all separately
verified byte-for-byte against the running original:

    dtl_forward_0x1A2CC   per-ring forward increment A
    dtl_lateral_0x19EE4   per-ring lateral increment B
    dtl_slopes/biases     the projection page inputs (00015AD9)
    heightmap-<n>.bin     the 1024x1024 height map at [0x19E6C]
    camera/sin/cos/alt    the frame's own viewpoint

Reference: 0000F2F1 copies the finished 192-byte per-column occlusion to
[0x19E60] + ring*256 + 0x20 at the end of every ring, so silhouettes-<n>.bin
holds the original's answer for every ring of the frame.

TWO TRAPS, both of which cost a step here and are why this file exists:

 1. Rings 0 to roughly 40 are UNIFORMLY ZERO in the reference. A model that
    matches them "192/192" has matched a constant. Score from the first ring
    with structure, which --min-distinct enforces.
 2. The silhouette cannot be read back off the drawn surface instead: the sky
    is composited into the same 256x256 buffer, so the first painted row per
    column is the sky, not the terrain.

Usage:
    python3 work/dump_marcher_tables.py --wait-flight 240 --at-marcher \
            --silhouette --heightmap --surface
    python3 tools/compare-marcher.py work/qemu_out/marcher-6.json

--at-marcher is not optional. Without it the reference and the camera are
from different frames and the score is meaningless.
"""
import argparse
import collections
import json
import os
import statistics
import sys


# 0001B84E overwrites bytes 0x58..0xA7 of each ring's record - array indices
# 56..135 - with the rear view's own 80-byte silhouette.
REAR_VIEW_FIRST, REAR_VIEW_LAST = 0x58 - 0x20, 0x58 - 0x20 + 80 - 1
VALID_COLUMNS = [c for c in range(192)
                 if not REAR_VIEW_FIRST <= c <= REAR_VIEW_LAST]


def s32(v):
    return v - 2**32 if v >= 2**31 else v


def build_page(slope_raw, bias_raw, scalar):
    """00015AD9's page: clamp((k-128)<<24 * slope + bias, 0, 0xFF00) >> 8."""
    slope = (slope_raw * scalar) >> 32          # 00015B17, unsigned mul
    bias = s32(bias_raw)
    page = bytearray()
    for k in range(256):
        e = (((k << 24) - 0x80000000) * slope) >> 32   # 00015B2B, signed
        if e >= 2**31:
            e -= 2**32
        e += bias                                       # 00015B2D
        e = 0 if e < 0 else (0xFF00 if e > 0xFF00 else e)
        page.append((e >> 8) & 0xFF)                    # 00015B44, dh
    return page


def march(dump, heightmap):
    """0000D950, exactly. Verified 17024/17024 against the original."""
    st = dump["state"]
    rings = st["ring_count_0x19EE0"]
    A = dump["dtl_forward_0x1A2CC"]
    B = dump["dtl_lateral_0x19EE4"]
    pages = [build_page(dump["dtl_slopes"][i], dump["dtl_biases"][i],
                        st["proj_scalar_0x19CEC"]) for i in range(rings)]
    cb0 = s32(st["sin_0x19CB0"])
    cb4 = s32(st["cos_0x19CB4"])
    # 0000D974/0000D97A: the marcher reads the camera straight out of
    # [0x19CD4]/[0x19CD8]. Not the latched [0x19CDC] pair - that is the frame
    # driver's copy, and while the two are equal at the 0000F317 breakpoint
    # (0000D413's integration has not run yet), the authority is what D974
    # reads.
    x = st["camera_x_0x19CD4"]
    y = st["camera_y_0x19CD8"]
    camh = ((~st["altitude_0x19DFC"]) & 0xFF) >> 1      # 0000D98C
    occl = [0] * 192                                    # 0000D96B
    per_ring = []
    for i in range(rings):
        x = (x + hi(A[i], cb0)) & 0xFFFFFFFF            # 0000D9A2/A8
        y = (y - hi(A[i], cb4)) & 0xFFFFFFFF            # 0000D9B1/B7
        esi = hi(B[i], cb0)                             # 0000D9C2/C8
        ebp = hi(B[i], cb4)                             # 0000D9D1/D7
        for half in (0, 1):
            cx, cy = x, y
            if half:                                    # 0000E5ED steps first
                cy = (cy + esi) & 0xFFFFFFFF
                cx = (cx + ebp) & 0xFFFFFFFF
            for step in range(96):
                col = 95 - step if half == 0 else 96 + step
                if col > 191:
                    break
                idx = (((cy >> 22) & 0x3FF) << 10) | ((cx >> 22) & 0x3FF)
                row = pages[i][(camh + heightmap[idx]) & 0xFF]   # 0000D9F6/F9
                if row > occl[col]:                             # 0000D9FB ja
                    occl[col] = row
                sign = -1 if half == 0 else 1                   # 0000DA05/07
                cy = (cy + sign * esi) & 0xFFFFFFFF
                cx = (cx + sign * ebp) & 0xFFFFFFFF
        per_ring.append(list(occl))
    return per_ring


def hi(a, b):
    return ((s32(a) * s32(b)) >> 32) & 0xFFFFFFFF


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--all-columns", action="store_true",
                    help="score all 192 columns instead of the 112 the main "
                         "view still owns; only useful to reproduce the "
                         "misleading number")
    ap.add_argument("--min-distinct", type=int, default=4,
                    help="skip rings whose reference has fewer distinct "
                         "values than this; a uniform ring scores 192/192 "
                         "against anything")
    args = ap.parse_args()
    with open(args.dump, encoding="utf-8") as f:
        dump = json.load(f)
    out = os.path.dirname(args.dump)
    for key, name in (("heightmap_file", "height map"),
                      ("silhouettes_file", "silhouettes")):
        if key not in dump:
            sys.exit(f"{args.dump}: no {name}; re-capture with "
                     "--heightmap --silhouette")
    heightmap = open(os.path.join(out, dump["heightmap_file"]), "rb").read()
    sil = open(os.path.join(out, dump["silhouettes_file"]), "rb").read()

    model = march(dump, heightmap)
    scored, skipped, exact_total, cells = [], 0, 0, 0
    for i, mine in enumerate(model):
        ref = list(sil[i * 256 + 0x20:i * 256 + 0x20 + 192])
        if len(ref) < 192:
            break
        if len(collections.Counter(ref)) < args.min_distinct:
            skipped += 1
            continue
        cols = range(192) if args.all_columns else VALID_COLUMNS
        err = [mine[c] - ref[c] for c in cols]
        ex = sum(1 for e in err if e == 0)
        exact_total += ex
        cells += len(err)
        scored.append((i, ex, statistics.mean(err), max(abs(e) for e in err)))
    print(f"{skipped} rings skipped as uniform (they match anything)")
    print(f"{len(scored)} rings scored\n")
    for i, ex, mean, worst in scored[:3] + scored[len(scored) // 2:][:2] + scored[-2:]:
        print(f"  ring {i:3d}: exact {ex:3d}/{len(VALID_COLUMNS) if not args.all_columns else 192}"
              f"  mean {mean:+7.2f}  max|e| {worst}")
    if cells:
        print(f"\noverall: {exact_total}/{cells} columns exact "
              f"({exact_total / cells:.1%})")
        if args.all_columns:
            print("Scored over all 192 columns: 80 of them are the rear "
                  "view's (0001B84E). This number is not a measurement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
