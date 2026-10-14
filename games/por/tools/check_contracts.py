#!/usr/bin/env python3
"""Static porting contracts: the target-neutral source and the host converter
must agree on the `PORI` bank layout, and a generated bank must parse by those
constants alone.

Run with `make test`. Any drift between src/common/inc/por.s and
tools/convert_data.py is a build failure, not a runtime surprise.
"""
import os, re, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import convert_data as cv                                      # noqa: E402

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: source says {got}, converter says {want}")


def parse_por_s():
    text = open(os.path.join(ROOT, "src", "common", "inc", "por.s")).read()
    out = {}
    for m in re.finditer(r"^(\w+)\s*=\s*(.+?)\s*(?:;.*)?$", text, re.M):
        name, expr = m.group(1), m.group(2).strip()
        if expr.startswith("'") and expr.endswith("'"):
            out[name] = int.from_bytes(expr[1:-1].encode("ascii"), "big")
            continue
        expr = re.sub(r"\$([0-9a-fA-F]+)", lambda x: str(int(x.group(1), 16)), expr)
        try:
            out[name] = eval(expr, {"__builtins__": {}}, dict(out))
        except Exception:
            pass
    return out


def main():
    s = parse_por_s()
    need = ["PORI_MAGIC", "PORI_VERSION", "PORI_HEADER_BYTES", "PORI_PALETTE_COUNT",
            "PORI_DIR_ENTRY_BYTES", "PORI_OFF_PALETTE", "SURFACE_BYTES"]
    missing = [n for n in need if n not in s]
    if missing:
        print(f"POR Falcon contracts: cannot parse {', '.join(missing)} from src/inc/por.s")
        return 1

    check("PORI_MAGIC", s["PORI_MAGIC"], int.from_bytes(cv.MAGIC, "big"))
    check("PORI_VERSION", s["PORI_VERSION"], cv.VERSION)
    check("PORI_HEADER_BYTES", s["PORI_HEADER_BYTES"], cv.HEADER_BYTES)
    check("PORI_PALETTE_COUNT", s["PORI_PALETTE_COUNT"], cv.PALETTE_COUNT)
    check("PORI_DIR_ENTRY_BYTES", s["PORI_DIR_ENTRY_BYTES"], cv.DIR_ENTRY_BYTES)
    check("PORI_OFF_PALETTE", s["PORI_OFF_PALETTE"], 12)
    for name, val in (("PORI_PAL_NONE", cv.PAL_NONE),
                      ("PORI_PAL_RGB565", cv.PAL_RGB565),
                      ("PORI_PAL_ST", cv.PAL_ST)):
        if name not in s:
            FAILURES.append(f"{name} missing from src/common/inc/por.s")
        else:
            check(name, s[name], val)

    # The indexed surface must match the DOS frame the assets describe.
    check("SURFACE_BYTES", s["SURFACE_BYTES"], 320 * 200)

    # Target back ends: each must define its own presentation constants and must
    # not leak them into the target-neutral header.
    for leaked in ("FRAME_BYTES", "LUT_ENTRIES", "CHUNKY_BYTES"):
        if leaked in s:
            FAILURES.append(f"{leaked} is target-specific but defined in "
                            f"src/common/inc/por.s")
    fal = os.path.join(ROOT, "src", "target", "falcon", "inc", "falcon.s")
    if os.path.exists(fal):
        ft = open(fal).read()
        for req in ("FRAME_BYTES", "LUT_ENTRIES"):
            if not re.search(rf"^{req}\s*=", ft, re.M):
                FAILURES.append(f"falcon back end does not define {req}")
        mo = re.search(r"^LUT_ENTRIES\s*=\s*(\d+)", ft, re.M)
        if mo and int(mo.group(1)) % cv.PALETTE_COUNT:
            FAILURES.append(f"LUT_ENTRIES {mo.group(1)} is not a multiple of "
                            f"the {cv.PALETTE_COUNT}-entry palette")

    # Round-trip: build a bank from the real title screen and walk it using
    # only the constants above.
    expanded = os.path.join(ROOT, "work", "expanded")
    title = os.path.join(expanded, "TITLE.DAX")
    if not os.path.exists(title):
        FAILURES.append("work/expanded/TITLE.DAX missing — run `make data`")
    else:
        images, _ = cv.collect(title)
        bank = cv.build_bank(images, "falcon")
        magic, version, count, palcount, flags = struct.unpack_from(">4sHHHH", bank, 0)
        if magic != cv.MAGIC:
            FAILURES.append(f"bank magic {magic!r}")
        if version != s["PORI_VERSION"]:
            FAILURES.append(f"bank version {version}")
        if palcount != s["PORI_PALETTE_COUNT"]:
            FAILURES.append(f"bank palette count {palcount}")
        if flags != cv.PAL_RGB565:
            FAILURES.append(f"falcon bank declares palette encoding {flags}, "
                            f"expected {cv.PAL_RGB565}")
        for i in range(count):
            off = s["PORI_HEADER_BYTES"] + i * s["PORI_DIR_ENTRY_BYTES"]
            w, h, sid, res, doff, dbytes = struct.unpack_from(">HHHHII", bank, off)
            if dbytes != w * h:
                FAILURES.append(f"image {i}: dataBytes {dbytes} != {w}*{h}")
            if doff + dbytes > len(bank):
                FAILURES.append(f"image {i}: data runs past end of bank")
            if max(bank[doff:doff + dbytes]) >= palcount:
                FAILURES.append(f"image {i}: pixel index >= palette size")
        if count and (w, h) != (320, 200):
            FAILURES.append(f"title image is {w}x{h}, expected 320x200")

    if FAILURES:
        print("POR Falcon contracts: FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("POR Falcon contracts: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
