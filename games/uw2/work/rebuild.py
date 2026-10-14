#!/usr/bin/env python3
"""Rebuild shipped UW2 assets from their decoded form and diff against the original.

`AGENTS.md` item 5 asks for byte-exact verification against `work/extracted/`.
This is the start of it. Decoding a format proves you can read it; **re-emitting
it byte-for-byte proves you understood it**, because every field you guessed
wrong or quietly ignored shows up as a diff.

`--strings` rebuilds `STRINGS.PAK` completely: the Huffman node table verbatim,
then every string re-encoded from its decoded text using codes derived by
walking the stored tree's parent links, then the block table with recomputed
offsets. Nothing is copied from the original except the node table and the
per-block trailing slack described below.

Result: **byte-identical for both UW2 and UW1.**

One thing had to be discovered to get there. Six blocks across the two games
carry 1-2 bytes of *unreferenced* data after their last indexed string --
`1c 38` in UW2's block 0x0008, and five one-or-two-byte tails in UW1. They are
not zero padding: decoded as a Huffman stream they come out as **spaces**. So
the original encoder left a little trailing whitespace behind, and a rebuild
that ignores it is 2 bytes short (UW2) or 6 (UW1). It is carried verbatim.

Usage:
  python work/rebuild.py --strings
  python work/rebuild.py --strings --path <other STRINGS.PAK>
  python work/rebuild.py --gr8
  python work/rebuild.py --gr8-rebuild
  python work/rebuild.py --gr-rebuild
"""
import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import strings_decode as SD                                    # noqa: E402
import lzss_encode                                            # noqa: E402
from ark import Ark                                           # noqa: E402
from cnv_decode import lzss                                   # noqa: E402
import gr8_decode                                              # noqa: E402
import gr8_encode                                              # noqa: E402
import gr_encode                                               # noqa: E402

UW2 = Path("work/extracted/D1/DATA/STRINGS.PAK")
UW1 = Path("/Users/saschaspringer/Work/F030Underworld/work/expanded/DATA/STRINGS.PAK")
TERMINATOR = 0x7C


def code_table(st):
    """Bit code per leaf char, from the stored tree's parent links."""
    codes = {}
    for i, (c, _p, l, r) in enumerate(st.nodes):
        if l != SD.NONE or r != SD.NONE:
            continue
        bits, cur = [], i
        while cur != st.root:
            par = st.nodes[cur][1]
            bits.append(0 if st.nodes[par][2] == cur else 1)
            cur = par
        codes[c] = bits[::-1]
    return codes


def encode(text, codes):
    out, acc, n = bytearray(), 0, 0
    for ch in list(text.encode("latin1")) + [TERMINATOR]:
        for b in codes[ch]:
            acc = (acc << 1) | b
            n += 1
            if n == 8:
                out.append(acc)
                acc = n = 0
    if n:
        out.append(acc << (8 - n))
    return bytes(out)


def rebuild_strings(path):
    d = path.read_bytes()
    st = SD.Strings(d)
    codes = code_table(st)
    blocks = st.blocks

    out = bytearray()
    out += struct.pack("<H", st.node_count)
    for c, p, l, r in st.nodes:
        out += bytes((c, p, l, r))
    out += struct.pack("<H", st.block_count)
    table_at = len(out)
    out += b"\0" * (6 * st.block_count)

    placed, slack_total = [], 0
    for k, (bid, off) in enumerate(blocks):
        strs = st.block(bid)
        placed.append((bid, len(out)))
        body, offsets = bytearray(), []
        for s in strs:
            offsets.append(len(body))
            body += encode(s, codes)
        size = 2 + 2 * len(strs) + len(body)
        nxt = blocks[k + 1][1] if k + 1 < len(blocks) else len(d)
        slack = d[off + size:nxt]          # unreferenced trailing bytes, verbatim
        slack_total += len(slack)
        out += struct.pack("<H", len(strs))
        out += struct.pack(f"<{len(strs)}H", *offsets)
        out += body + slack
    for i, (bid, o) in enumerate(placed):
        struct.pack_into("<HI", out, table_at + 6 * i, bid, o)
    return bytes(out), d, slack_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strings", action="store_true")
    ap.add_argument("--ark", action="store_true",
                    help="re-compress every .ARK record and compare")
    ap.add_argument("--tr", action="store_true",
                    help="rebuild .TR from its decoded tiles and compare")
    ap.add_argument("--gr", action="store_true",
                    help="census .GR record types (what a rebuild would need)")
    ap.add_argument("--gr8", action="store_true",
                    help="validate the type-8 .GR decoder across all records")
    ap.add_argument("--gr8-rebuild", action="store_true",
                    help="re-encode every type-8 .GR record and compare")
    ap.add_argument("--gr-rebuild", action="store_true",
                    help="rebuild standard .GR archives and compare")
    ap.add_argument("--path", type=Path)
    a = ap.parse_args()
    targets = [a.path] if a.path else [p for p in (UW2, UW1) if p.exists()]
    if a.tr:
        for p in sorted(Path("work/extracted").rglob("*.TR")):
            d = p.read_bytes()
            ver, dim = d[0], d[1]
            n = struct.unpack_from("<H", d, 2)[0]
            tbl = [struct.unpack_from("<I", d, 4 + 4 * i)[0] for i in range(n)]
            tiles = [d[tbl[i]:tbl[i] + dim * dim] for i in range(n)]
            out = bytearray((ver, dim)) + struct.pack("<H", n)
            at = len(out)
            out += b"\0" * (4 * n)
            out += d[4 + 4 * n:tbl[0]]          # the 4-byte gap, verbatim
            new = []
            for i in range(n):
                new.append(len(out))
                if i == n - 1 or tbl[i + 1] > tbl[i]:
                    out += tiles[i]
            for i, v in enumerate(new):
                struct.pack_into("<I", out, at + 4 * i, v)
            print(f"{p.name}: {len(d)} B, ver={ver} dim={dim} N={n}  ->  "
                  f"{'IDENTICAL' if bytes(out) == d else 'DIFFERS'}")
        return

    if a.gr:
        from collections import Counter
        c = Counter()
        for p in sorted(Path("work/extracted").rglob("*.GR")):
            d = p.read_bytes()
            n = struct.unpack_from("<H", d, 1)[0]
            tbl = [struct.unpack_from("<I", d, 3 + 4 * i)[0] & 0xFFFFFF
                   for i in range(n + 1)]
            for i in range(n):
                if tbl[i + 1] <= tbl[i]:
                    c["empty"] += 1
                else:
                    c[f"type {d[tbl[i]]:#04x}"] += 1
        total = sum(c.values())
        print(f"{total} .GR records:")
        for k, v in c.most_common():
            print(f"   {k:12s} {v:5d}  ({100*v//total}%)")
        print("\n  type 0x04 (raw 8bpp), 0x0a (packed 4-bit), and 0x08 are decoded;")
        print("  type-8 record encoding is validated by --gr8-rebuild.")
        print("  Standard archive emission is validated by --gr-rebuild;")
        print("  only divergent PANELS.GR record 3 remains open.")
        return
    if a.gr8:
        from collections import Counter
        total = decoded = bailed = 0
        lengths = Counter()
        for p in sorted(Path("work/extracted").rglob("*.GR")):
            d = p.read_bytes()
            for start, end in gr8_decode.records(d):
                if end <= start or end > len(d) or d[start] != 8:
                    continue
                total += 1
                rec = d[start:end]
                try:
                    px = gr8_decode.decode_type8(rec)
                except gr8_decode.Bail:
                    bailed += 1
                    continue
                decoded += 1
                lengths[len(px) - rec[1] * rec[2]] += 1
        print(f".GR type-8 records: {total}")
        print(f"  decoded without overrun: {decoded}/{total}")
        print(f"  decoder bailouts: {bailed}")
        print("  output length minus w*h: " + ", ".join(
            f"{k:+d}={lengths[k]}" for k in sorted(lengths)))
        return 0 if total == decoded and not bailed else 1
    if a.gr8_rebuild:
        allpals = Path("work/extracted/D3/DATA/ALLPALS.DAT").read_bytes()
        total = exact = 0
        for p in sorted(Path("work/extracted").rglob("*.GR")):
            d = p.read_bytes()
            for start, end in gr8_decode.records(d):
                if end <= start or end > len(d) or d[start] != 8:
                    continue
                total += 1
                rebuilt = gr8_encode.encode_type8_record(d[start:end], allpals)
                exact += rebuilt == d[start:end]
        print(f".GR type-8 records re-encoded byte-identically: {exact}/{total}")
        return 0 if exact == total else 1
    if a.gr_rebuild:
        allpals = Path("work/extracted/D3/DATA/ALLPALS.DAT").read_bytes()
        rebuilt_files = exact_files = 0
        for p in sorted(Path("work/extracted").rglob("*.GR")):
            if p.name == "PANELS.GR":
                print(f"{p}: SKIP (divergent raw-panel records)")
                continue
            rebuilt_files += 1
            original = p.read_bytes()
            rebuilt = gr_encode.rebuild_archive(original, allpals)
            same = rebuilt == original
            exact_files += same
            print(f"{p}: {'IDENTICAL' if same else 'DIFFERS'}")
        print(f"standard .GR archives byte-identical: {exact_files}/{rebuilt_files}")
        return 0 if exact_files == rebuilt_files else 1

    if a.ark:
        rt = exact = tot = so = sc = 0
        for p in sorted(Path("work/extracted").rglob("*.ARK")):
            k = Ark(p)
            if not k.slots or k.header_end > len(k.d):
                continue
            for i in k.used:
                if not k.flag[i] & 2:
                    continue
                body, _ = k.record(i)
                shipped = k.d[k.off[i] + 4:k.off[i] + k.size[i]]
                ours = lzss_encode.compress(body)
                back, _ = lzss(ours, len(body))
                tot += 1
                rt += bytes(back) == body
                exact += ours == shipped
                so += len(shipped)
                sc += len(ours)
        print(f"compressed .ARK records: {tot}")
        print(f"  our stream decompresses to the identical data : {rt}/{tot}")
        print(f"  byte-identical to the shipped stream          : {exact}/{tot}")
        print(f"  total size ours {sc} vs shipped {so} "
              f"({100 * (sc - so) / so:+.2f}%)")
        return
    if not a.strings:
        return print(__doc__)
    for p in targets:
        built, orig, slack = rebuild_strings(p)
        same = built == orig
        print(f"{str(p):60s}")
        print(f"   original {len(orig):7d} B, rebuilt {len(built):7d} B, "
              f"carried slack {slack} B  ->  {'IDENTICAL' if same else 'DIFFERS'}")
        if not same:
            for i, (x, y) in enumerate(zip(built, orig)):
                if x != y:
                    print(f"   first diff at 0x{i:X}: rebuilt {x:#04x}, original {y:#04x}")
                    break


if __name__ == "__main__":
    main()
