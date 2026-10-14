#!/usr/bin/env python3
"""Independent MZ-header / relocation-table audit for a 16-bit DOS EXE.

Parses the MZ container with struct.unpack_from only - no assumptions taken
from any document.  Prints every field with its file offset, decodes the full
relocation table as (offset u16, segment u16) pairs, and checks the image /
overlay-pool arithmetic.

Usage: python work/mz_audit.py <exe> [...]
"""
import struct
import sys

MZ_FIELDS = [
    (0x00, "e_magic",   "H"),
    (0x02, "e_cblp",    "H"),
    (0x04, "e_cp",      "H"),
    (0x06, "e_crlc",    "H"),
    (0x08, "e_cparhdr", "H"),
    (0x0A, "e_minalloc","H"),
    (0x0C, "e_maxalloc","H"),
    (0x0E, "e_ss",      "H"),
    (0x10, "e_sp",      "H"),
    (0x12, "e_csum",    "H"),
    (0x14, "e_ip",      "H"),
    (0x16, "e_cs",      "H"),
    (0x18, "e_lfarlc",  "H"),
    (0x1A, "e_ovno",    "H"),
]


def hexdump(data, base=0, length=None):
    if length is None:
        length = len(data)
    out = []
    for off in range(0, length, 16):
        chunk = data[off:off + 16]
        hexs = " ".join("%02x" % b for b in chunk)
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append("%08X  %-47s  |%s|" % (base + off, hexs, txt))
    return "\n".join(out)


def audit(path):
    with open(path, "rb") as fh:
        data = fh.read()
    fsize = len(data)
    print("=" * 78)
    print("FILE  %s" % path)
    print("SIZE  %d bytes (0x%X)" % (fsize, fsize))
    print("=" * 78)
    print()
    print("--- raw first 64 bytes ---")
    print(hexdump(data, 0, 64))
    print()

    f = {}
    print("--- MZ header fields ---")
    print("%-6s %-11s %-8s %-8s %s" % ("off", "field", "hex", "dec", "raw"))
    for off, name, fmt in MZ_FIELDS:
        (val,) = struct.unpack_from("<" + fmt, data, off)
        f[name] = val
        raw = " ".join("%02x" % b for b in data[off:off + 2])
        print("0x%02X   %-11s 0x%04X   %-8d %s" % (off, name, val, val, raw))
    print()

    magic = data[0:2]
    print("magic bytes: %r  -> %s" % (magic, "MZ ok" if magic == b"MZ" else "NOT MZ"))

    header_size = f["e_cparhdr"] * 16
    image_size = (f["e_cp"] - 1) * 512 + f["e_cblp"]
    if f["e_cblp"] == 0:                      # DOS convention: 0 == full page
        image_size = f["e_cp"] * 512
    entry = header_size + (f["e_cs"] << 4) + f["e_ip"]
    stack = header_size + (f["e_ss"] << 4) + f["e_sp"]
    swapped_entry = header_size + (f["e_ip"] << 4) + f["e_cs"]

    print()
    print("--- derived ---")
    print("header size          = e_cparhdr*16      = %d * 16 = 0x%X (%d)"
          % (f["e_cparhdr"], header_size, header_size))
    print("image size           = (e_cp-1)*512+e_cblp = (%d-1)*512+%d = 0x%X (%d)"
          % (f["e_cp"], f["e_cblp"], image_size, image_size))
    print("  e_cp/e_cblp count the HEADER too, so this IS the file offset of the")
    print("  end of the DOS-mapped image; the loader maps file 0x%X..0x%X."
          % (header_size, image_size))
    print("tail after image     = 0x%X .. 0x%X = %d bytes"
          % (image_size, fsize, fsize - image_size))
    print("entry file offset    = hdr + (e_cs<<4) + e_ip = 0x%X + 0x%X + 0x%X = 0x%X"
          % (header_size, f["e_cs"] << 4, f["e_ip"], entry))
    print("  [SWAPPED reading, for comparison: hdr + (e_ip<<4) + e_cs = 0x%X]"
          % swapped_entry)
    print("initial SS:SP        = %04X:%04X -> file 0x%X"
          % (f["e_ss"], f["e_sp"], stack))
    print("e_lfarlc             = 0x%X" % f["e_lfarlc"])
    print("bytes at 0x3C (would-be e_lfanew) = %s  (0x%08X)"
          % (" ".join("%02x" % b for b in data[0x3C:0x40]),
             struct.unpack_from("<I", data, 0x3C)[0]))
    print("  0x3C is INSIDE the reloc table (starts 0x%X) -> not an e_lfanew"
          % f["e_lfarlc"] if f["e_lfarlc"] <= 0x3C else "  0x3C precedes reloc table")

    # ---- entry bytes -------------------------------------------------
    print()
    print("--- 64 bytes at computed entry 0x%X ---" % entry)
    print(hexdump(data[entry:entry + 64], entry))
    print()
    print("--- 32 bytes at SWAPPED-reading entry 0x%X (for contrast) ---"
          % swapped_entry)
    print(hexdump(data[swapped_entry:swapped_entry + 32], swapped_entry))

    # ---- relocation table --------------------------------------------
    print()
    print("--- relocation table ---")
    rl = f["e_lfarlc"]
    n = f["e_crlc"]
    tbl_end = rl + n * 4
    print("e_lfarlc = 0x%X, e_crlc = %d -> table 0x%X..0x%X (%d bytes)"
          % (rl, n, rl, tbl_end, n * 4))
    print("header slack after table: 0x%X..0x%X = %d bytes"
          % (tbl_end, header_size, header_size - tbl_end))
    slack = data[tbl_end:header_size]
    print("slack all zero? %s" % (set(slack) in ({0}, set()),))
    if set(slack) - {0}:
        nz = [(tbl_end + i, b) for i, b in enumerate(slack) if b]
        print("  non-zero slack bytes (first 20): %s"
              % ["0x%X=%02x" % t for t in nz[:20]])

    relocs = []
    for i in range(n):
        o, s = struct.unpack_from("<HH", data, rl + i * 4)
        relocs.append((o, s))
    print("first 8 entries (offset, segment) -> target file offset:")
    for i, (o, s) in enumerate(relocs[:8]):
        raw = " ".join("%02x" % b for b in data[rl + i * 4:rl + i * 4 + 4])
        tgt = header_size + (s << 4) + o
        print("  [%3d] raw %s  off=0x%04X seg=0x%04X  -> file 0x%X" % (i, raw, o, s, tgt))
    print("last 4 entries:")
    for i in range(max(0, n - 4), n):
        o, s = relocs[i]
        raw = " ".join("%02x" % b for b in data[rl + i * 4:rl + i * 4 + 4])
        tgt = header_size + (s << 4) + o
        print("  [%3d] raw %s  off=0x%04X seg=0x%04X  -> file 0x%X" % (i, raw, o, s, tgt))

    targets = [header_size + (s << 4) + o for (o, s) in relocs]
    in_image = [t for t in targets if header_size <= t <= image_size - 2]
    oob = [t for t in targets if not (header_size <= t <= image_size - 2)]
    print()
    print("targets: min 0x%X  max 0x%X" % (min(targets), max(targets)))
    print("all inside [header 0x%X, image end 0x%X)? %s  (%d in, %d out)"
          % (header_size, image_size, not oob, len(in_image), len(oob)))
    if oob:
        print("  out-of-image targets (first 20): %s" % ["0x%X" % t for t in oob[:20]])
    print("unique targets? %s  (%d entries, %d distinct)"
          % (len(set(targets)) == len(targets), len(targets), len(set(targets))))
    dup = {}
    for t in targets:
        dup[t] = dup.get(t, 0) + 1
    dups = sorted([(t, c) for t, c in dup.items() if c > 1])
    if dups:
        print("  duplicate targets (first 10): %s" % ["0x%X x%d" % t for t in dups[:10]])
    print("unique (offset,segment) pairs? %s" % (len(set(relocs)) == len(relocs),))
    segs = sorted({s for (o, s) in relocs})
    print("distinct segments in table: %d  (min 0x%04X max 0x%04X)"
          % (len(segs), segs[0], segs[-1]))
    offs = sorted({o for (o, s) in relocs})
    print("distinct offsets in table: %d (min 0x%04X max 0x%04X)"
          % (len(offs), offs[0], offs[-1]))
    print("offsets >= 0x10 (i.e. NOT expressible as a u8)? %d of %d entries"
          % (sum(1 for (o, s) in relocs if o > 0xFF), n))

    # ---- what the WRONG UW1 format would have said --------------------
    bad = []
    for i in range(n):
        page, o8, pad = struct.unpack_from("<HBB", data, rl + i * 4)
        bad.append((page, o8, pad))
    bad_pad = {p for (_, _, p) in bad}
    print()
    print("[contrast] under the withdrawn '(page u16, offset u8, pad u8)' reading,")
    print("           the 'pad' byte would take %d distinct values %s"
          % (len(bad_pad), sorted(bad_pad)[:12]))

    # ---- reloc 0 vs entry --------------------------------------------
    print()
    print("--- reloc[0] vs entry point ---")
    o0, s0 = relocs[0]
    t0 = header_size + (s0 << 4) + o0
    print("reloc[0] = off 0x%04X seg 0x%04X -> file 0x%X" % (o0, s0, t0))
    print("entry    = 0x%X ; delta = %+d" % (entry, t0 - entry))
    (patched,) = struct.unpack_from("<H", data, t0)
    print("word at reloc[0] target = 0x%04X (%d)" % (patched, patched))
    dgroup_file = header_size + (patched << 4)
    print("if that is DGROUP: DGROUP file offset = 0x%X + (0x%04X<<4) = 0x%X"
          % (header_size, patched, dgroup_file))
    print("  -> in image? %s ; 64 bytes there:"
          % (header_size <= dgroup_file < image_size))
    print(hexdump(data[dgroup_file:dgroup_file + 64], dgroup_file))

    # ---- overlay pool -------------------------------------------------
    print()
    print("--- overlay pool / tail ---")
    for probe, label in ((image_size, "image end (e_cp/e_cblp)"),
                         (header_size + image_size, "hdr+image")):
        if 0 <= probe < fsize - 16:
            sig = data[probe:probe + 4]
            print("bytes at 0x%X (%s): %s  %r"
                  % (probe, label, " ".join("%02x" % b for b in data[probe:probe + 16]), sig))
    fb = data.find(b"FBOV")
    while fb != -1:
        sig, ovrsize, exeinfo, segnum = struct.unpack_from("<4sIII", data, fb)
        print("FBOV at file 0x%X: ovrsize=0x%X exeinfo=0x%X segnum=%d"
              % (fb, ovrsize, exeinfo, segnum))
        print("  raw: %s" % " ".join("%02x" % b for b in data[fb:fb + 16]))
        print("  ovrsize+16 = 0x%X ; filesize-FBOV = 0x%X ; equal? %s"
              % (ovrsize + 16, fsize - fb, ovrsize + 16 == fsize - fb))
        print("  FBOV == image_size? %s (image_size=0x%X, delta %+d)"
              % (fb == image_size, image_size, fb - image_size))
        print("  exeinfo == image_size? %s (delta %+d)"
              % (exeinfo == image_size, exeinfo - image_size))
        fb = data.find(b"FBOV", fb + 1)
    print()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        audit(p)
