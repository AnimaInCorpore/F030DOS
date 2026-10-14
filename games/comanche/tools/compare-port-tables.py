#!/usr/bin/env python3
"""Run the certified model of 0000D950 on THE PORT'S tables instead of the
original's, and score it against the original's own silhouettes.

Why this is stronger than the field-by-field table comparison that came
before it: matching `ring_a_table` against a dump of 0x1A2CC proves the
bytes agree, and nothing about whether the port's package is *complete* or
whether the pieces are being combined the way the original combines them. A
table can be right and still be indexed wrong, scaled wrong, or paired with
the wrong companion. Feeding the port's tables through the routine that is
now known to reproduce the original exactly (tools/compare-marcher.py,
17024/17024) tests them in use, end to end, against the original's answer.

What this does and does not certify: it covers the port's DATA - the .DTL
derived A/B increments and the built projection pages - and the height map
it loads from D1.DTA. It does NOT execute a line of 68030; src/render.s's
own instruction stream is audited against the model separately, and the
port's rendered output still needs a same-camera surface diff.

    python3 tools/compare-port-tables.py work/qemu_out/marcher-6.json
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
import pathlib
cm = importlib.import_module("compare-marcher")
prep = importlib.import_module("prepare-original-test")


def parse_table(text, label, directive):
    """Pull one dc.l/dc.b table out of the generated assembly by label."""
    start = re.search(rf"^{label}\s*$", text, re.M)
    if not start:
        sys.exit(f"{label}: not found in the generated tables")
    values = []
    for line in text[start.end():].splitlines()[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if not stripped.startswith(directive):
            break
        for item in stripped[len(directive):].split(","):
            values.append(int(item.strip(), 0))
    return values


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--tables", default="build/original_test.s")
    ap.add_argument("--assets", default="assets/extracted/comanche_hdd",
                    help="where the installed D<n>.DTA family lives")
    ap.add_argument("--min-distinct", type=int, default=4)
    args = ap.parse_args()

    with open(args.dump, encoding="utf-8") as f:
        dump = json.load(f)
    out = os.path.dirname(args.dump)
    if "silhouettes_file" not in dump or "heightmap_file" not in dump:
        sys.exit("capture with --at-marcher --silhouette --heightmap")
    sil = open(os.path.join(out, dump["silhouettes_file"]), "rb").read()
    captured_hm = open(os.path.join(out, dump["heightmap_file"]), "rb").read()

    text = open(args.tables, encoding="utf-8").read()
    port_a = parse_table(text, "ring_a_table", "dc.l")
    port_b = parse_table(text, "ring_b_table", "dc.l")
    port_pages = parse_table(text, "ring_page_table", "dc.b")
    rings = dump["state"]["ring_count_0x19EE0"]
    print(f"port tables: A={len(port_a)} B={len(port_b)} "
          f"pages={len(port_pages)} bytes ({len(port_pages)//256} rings); "
          f"original runs {rings} rings")

    # The height map is not in the .TOS - resources.s loads it from D1.DTA at
    # run time - so the asset is what the port will march over. Check it
    # against what the original had in memory rather than assuming the loader
    # is transparent.
    # D<n>.DTA is a 16-byte Kyle header plus PCX-style byte RLE - 561859
    # bytes on disk for a 1 MiB map - so it has to be DECODED before it can
    # be compared. Comparing the file to memory directly just reports that
    # compressed bytes are not uncompressed bytes, which is not a finding.
    #
    # And do not assume WHICH family: the whole installed set is decoded and
    # matched. The attract demo flies D4, not D1, so checking D1 alone
    # reports a 1.4% match and looks like a broken decoder when the decoder
    # is exact. The mission file names its own map (mission.s parses the
    # "D<n>.DTA" resource name), so the family is data, not a constant.
    heightmap = captured_hm
    families = sorted(pathlib.Path(args.assets).glob("D*.DTA"))
    for path in families:
        try:
            decoded = bytes(prep.decode_dta(path))
        except Exception as exc:                       # noqa: BLE001
            print(f"height map: {path.name} did not decode ({exc})")
            continue
        if decoded == captured_hm:
            print(f"height map: {path.name} decodes to the original's memory "
                  f"exactly ({len(decoded)} bytes) - the RLE reading is right, "
                  f"and this is the family the captured flight is using")
            heightmap = decoded
            break
    else:
        print(f"height map: none of {len(families)} installed families decodes "
              f"to the captured memory - scoring against the capture")

    # Everything below is the certified model, with the port's tables
    # substituted for the captured ones.
    st = dump["state"]
    x, y = st["camera_x_0x19CD4"], st["camera_y_0x19CD8"]
    cb0, cb4 = cm.s32(st["sin_0x19CB0"]), cm.s32(st["cos_0x19CB4"])
    camh = ((~st["altitude_0x19DFC"]) & 0xFF) >> 1
    occl = [0] * 192
    exact_total = cells = skipped = scored = 0
    worst_ring = (0, 0)
    for i in range(rings):
        x = (x + cm.hi(port_a[i], cb0)) & 0xFFFFFFFF
        y = (y - cm.hi(port_a[i], cb4)) & 0xFFFFFFFF
        esi, ebp = cm.hi(port_b[i], cb0), cm.hi(port_b[i], cb4)
        page = port_pages[i * 256:(i + 1) * 256]
        for half in (0, 1):
            cx, cy = x, y
            if half:
                cy = (cy + esi) & 0xFFFFFFFF
                cx = (cx + ebp) & 0xFFFFFFFF
            for step in range(96):
                col = 95 - step if half == 0 else 96 + step
                idx = (((cy >> 22) & 0x3FF) << 10) | ((cx >> 22) & 0x3FF)
                row = page[(camh + heightmap[idx]) & 0xFF]
                if row > occl[col]:
                    occl[col] = row
                sign = -1 if half == 0 else 1
                cy = (cy + sign * esi) & 0xFFFFFFFF
                cx = (cx + sign * ebp) & 0xFFFFFFFF
        ref = list(sil[i * 256 + 0x20:i * 256 + 0x20 + 192])
        if len(collections.Counter(ref)) < args.min_distinct:
            skipped += 1
            continue
        err = [occl[c] - ref[c] for c in cm.VALID_COLUMNS]
        ex = sum(1 for e in err if e == 0)
        exact_total += ex
        cells += len(err)
        scored += 1
        if len(err) - ex > worst_ring[1]:
            worst_ring = (i, len(err) - ex)
    print(f"\n{skipped} rings skipped as uniform, {scored} scored")
    if worst_ring[1]:
        print(f"worst ring {worst_ring[0]}: {worst_ring[1]} columns wrong")
    print(f"overall: {exact_total}/{cells} columns exact "
          f"({exact_total / cells:.1%})" if cells else "nothing scored")
    return 0 if cells and exact_total == cells else 1


if __name__ == "__main__":
    raise SystemExit(main())
