#!/usr/bin/env python3
"""Validate UW1 ``.GR`` decoding and byte-exact re-emission.

Usage:
  python work/rebuild.py --gr
  python work/rebuild.py --gr8
  python work/rebuild.py --gr8-rebuild
  python work/rebuild.py --gr-rebuild
"""
import argparse
import struct
from collections import Counter
from pathlib import Path

import gr8_decode
import gr8_encode
import gr_encode


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "expanded" / "DATA"


def iter_records(path):
    data = path.read_bytes()
    for index, (start, end) in enumerate(gr8_decode.records(data)):
        yield data, index, start, end


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gr", action="store_true", help="census .GR record types")
    ap.add_argument("--gr8", action="store_true", help="validate type-8 decoding")
    ap.add_argument("--gr8-rebuild", action="store_true",
                    help="validate byte-exact type-8 record encoding")
    ap.add_argument("--gr-rebuild", action="store_true",
                    help="validate byte-exact standard archive emission")
    args = ap.parse_args()
    paths = sorted(DATA.glob("*.GR"))
    allpals = (DATA / "ALLPALS.DAT").read_bytes()

    if args.gr:
        counts = Counter()
        for path in paths:
            for data, _index, start, end in iter_records(path):
                if end <= start:
                    counts["empty"] += 1
                else:
                    counts[f"type {data[start]:#04x}"] += 1
        total = sum(counts.values())
        print(f"{total} .GR records:")
        for key, value in counts.most_common():
            print(f"  {key:12s} {value:5d} ({100 * value // total}%)")
        return 0

    if args.gr8 or args.gr8_rebuild:
        total = decoded = exact = bailouts = 0
        lengths = Counter()
        for path in paths:
            for data, index, start, end in iter_records(path):
                if end <= start or data[start] != 8:
                    continue
                total += 1
                record = data[start:end]
                try:
                    pixels = gr8_decode.decode_type8(record)
                    decoded += 1
                    lengths[len(pixels) - record[1] * record[2]] += 1
                    if args.gr8_rebuild:
                        exact += gr8_encode.encode_type8_record(
                            record, allpals) == record
                except gr8_decode.Bail as exc:
                    bailouts += 1
                    print(f"BAIL {path.name}#{index}: {exc}")
        print(f".GR type-8 records: {total}")
        print(f"  decoded without overrun: {decoded}/{total}")
        print(f"  decoder bailouts: {bailouts}")
        print("  output length minus w*h: " + ", ".join(
            f"{key:+d}={lengths[key]}" for key in sorted(lengths)))
        if args.gr8_rebuild:
            print(f"  records re-encoded byte-identically: {exact}/{total}")
            return 0 if exact == total and decoded == total else 1
        return 0 if decoded == total and not bailouts else 1

    if args.gr_rebuild:
        rebuilt = exact = 0
        for path in paths:
            if path.name == "PANELS.GR":
                print(f"{path.name}: SKIP (divergent raw-panel records)")
                continue
            rebuilt += 1
            original = path.read_bytes()
            same = gr_encode.rebuild_archive(original, allpals) == original
            exact += same
            print(f"{path.name}: {'IDENTICAL' if same else 'DIFFERS'}")
        print(f"standard .GR archives byte-identical: {exact}/{rebuilt}")
        return 0 if exact == rebuilt else 1

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
