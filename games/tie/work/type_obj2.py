#!/usr/bin/env python3
"""P4.2/P2.x: classify object 2 (data) of Z_TIE__.EXE.

  python3 work/type_obj2.py

obj2 is the last large region work/build_ztie.py copies verbatim (79,175 B
file-backed). Emitting it as one undifferentiated `db` blob would make the build
"complete" while proving nothing -- METHOD.md 2.4's trap in data form. This
classifies every byte from evidence already in hand:

  pointer   a 32-bit fixup SOURCE site in obj2 -- the LE fixup table says so
  string    NUL-terminated printable run >= 4 -- high confidence, a real C literal
  printable an unterminated printable block >= 16 -- LOW confidence. It catches
            real prose (the 921 B message block at obj2+0x4B) but also binary
            tables that happen to fall in 0x20..0x7E, e.g.
            "sPPPPPPPPPDDHHHHHH..." and ",-./,-./BJFNREBRJRFVJV". Kept as its
            own class so the two are never conflated.
  zero      run of >= 8 NUL bytes
  unknown   everything else -- reported, never guessed at
"""
import collections
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_fixups as af          # noqa: E402

OBJ2_BASE = 0xC0000


def classify():
    """-> (blob, kind list, file lo, file hi). Shared by main() and emit()."""
    data = af.data
    obj2 = af.objs[1]
    lo = af.page_file_off(obj2["first"] - 1)
    hi = len(data)
    blob = data[lo:hi]
    n = len(blob)
    kind = ["unknown"] * n
    for i in range(af.num_pages):
        objn, _o = af.obj_of_page(i)
        if objn != 2:
            continue
        base = af.linear_of_page(i)
        recs, _s, _e = af.decode_page(i)
        for r in recs:
            if r["stype"] != 7:
                continue
            for so in r["srcoffs"]:
                off = (base + so) - OBJ2_BASE
                if 0 <= off + 3 < n:
                    for k in range(4):
                        if kind[off + k] == "unknown":
                            kind[off + k] = "pointer"
    for m in re.finditer(rb"[\x20-\x7e]{4,}\x00", blob):
        for i in range(m.start(), m.end()):
            if kind[i] == "unknown":
                kind[i] = "string"
    for m in re.finditer(rb"[\x20-\x7e\r\n\t]{16,}", blob):
        for i in range(m.start(), m.end()):
            if kind[i] == "unknown":
                kind[i] = "printable"
    z = 0
    for i, b in enumerate(blob + b"\xff"):
        if i < n and b == 0:
            z += 1
            continue
        if z >= 8:
            for k in range(i - z, i):
                if kind[k] == "unknown":
                    kind[k] = "zero"
        z = 0
    return blob, kind, lo, hi


def emit(blob, kind):
    """NASM source for obj2: typed where known, raw db where not."""
    out = ["bits 32", "org 0", ""]
    i, n = 0, len(blob)
    while i < n:
        k = kind[i]
        j = i
        while j < n and kind[j] == k:
            j += 1
        chunk = blob[i:j]
        if k == "pointer":
            for p in range(0, len(chunk) - 3, 4):
                out.append(f"    dd 0x{struct.unpack_from('<I', chunk, p)[0]:08x}")
            rem = len(chunk) % 4
            if rem:
                out.append("    db " + ",".join(f"0x{b:02x}" for b in chunk[-rem:]))
        elif k == "zero":
            out.append(f"    times {len(chunk)} db 0")
        else:
            for p in range(0, len(chunk), 16):
                out.append("    db " + ",".join(f"0x{b:02x}" for b in chunk[p:p + 16]))
        i = j
    return "\n".join(out) + "\n"


def main():
    data = af.data
    obj2 = af.objs[1]
    lo = af.page_file_off(obj2["first"] - 1)
    hi = len(data)
    blob = data[lo:hi]
    n = len(blob)
    kind = ["unknown"] * n

    # 1. pointers: fixup source sites whose page belongs to obj2
    ptr = 0
    for i in range(af.num_pages):
        objn, _o = af.obj_of_page(i)
        if objn != 2:
            continue
        base = af.linear_of_page(i)
        recs, _s, _e = af.decode_page(i)
        for r in recs:
            if r["stype"] != 7:
                continue
            for so in r["srcoffs"]:
                off = (base + so) - OBJ2_BASE
                if 0 <= off + 3 < n:
                    for k in range(4):
                        if kind[off + k] == "unknown":
                            kind[off + k] = "pointer"
                            ptr += 1

    # 2. strings
    for m in re.finditer(rb"[\x20-\x7e]{4,}\x00", blob):
        for i in range(m.start(), m.end()):
            if kind[i] == "unknown":
                kind[i] = "string"
    for m in re.finditer(rb"[\x20-\x7e\r\n\t]{16,}", blob):
        for i in range(m.start(), m.end()):
            if kind[i] == "unknown":
                kind[i] = "printable"

    # 3. zero runs
    z = 0
    for i, b in enumerate(blob + b"\xff"):
        if i < n and b == 0:
            z += 1
            continue
        if z >= 8:
            for k in range(i - z, i):
                if kind[k] == "unknown":
                    kind[k] = "zero"
        z = 0

    c = collections.Counter(kind)
    print(f"obj2 file-backed region: file {lo:#08x}..{hi:#08x} = {n} B "
          f"(virtual size {obj2['vsize']:#x}, the rest is BSS)\n")
    for k in ("pointer", "string", "printable", "zero", "unknown"):
        print(f"  {k:<9} {c[k]:>7} B  {100*c[k]/n:5.1f}%")
    typed = n - c["unknown"]
    print(f"\n  typed from evidence: {typed}/{n} B ({100*typed/n:.1f}%)")

    # largest unknown runs, so the next pass knows where to look
    runs, i = [], 0
    while i < n:
        if kind[i] != "unknown":
            i += 1
            continue
        j = i
        while j < n and kind[j] == "unknown":
            j += 1
        runs.append((i, j - i))
        i = j
    runs.sort(key=lambda t: -t[1])
    print(f"\n  {len(runs)} unknown runs; largest:")
    for off, ln in runs[:8]:
        sample = blob[off:off + 16]
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in sample)
        print(f"    obj2+{off:#07x} {ln:>6} B  {sample.hex(' ')[:35]:<35} |{txt}|")
    # emit + verify: the typed source must re-assemble to the original bytes
    if "--emit" in sys.argv:
        import subprocess
        outdir = "work/obj2"
        os.makedirs(outdir, exist_ok=True)
        src = emit(blob, kind)
        asm = os.path.join(outdir, "obj2.asm")
        binf = os.path.join(outdir, "obj2.bin")
        open(asm, "w").write(src)
        r = subprocess.run(["nasm", "-f", "bin", "-o", binf, asm],
                           capture_output=True, text=True)
        if r.returncode:
            print("nasm error:\n" + r.stderr[:800])
            return 1
        got = open(binf, "rb").read()
        print(f"\nemitted {asm} -> {binf} ({len(got)} B); "
              f"byte-identical: {got == blob}")
        return 0 if got == blob else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
