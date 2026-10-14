#!/usr/bin/env python3
"""Reduce QEMU's built-in execution log to the DOS attract call surface."""
import argparse
import collections


RANGES = [
    ("attract-cycle", 0x05690, 0x05AE3),
    ("attract-state", 0x059ED, 0x05AD6),
    ("frame-driver", 0x0D3C0, 0x0D8F5),
    ("terrain-setup", 0x07D25, 0x0AF4E),
    ("terrain-renderer", 0x0D950, 0x0F317),
    ("terrain-setup-96", 0x107A0, 0x10FFF),
    ("terrain-renderer-96", 0x137F0, 0x13FFF),
    ("replay-load", 0x18C29, 0x18F94),
    ("flight", 0x18F94, 0x1959E),
    ("replay-actions", 0x191B6, 0x192AA),
    ("dynamic-bank-load", 0x066E2, 0x067A4),
    ("weapon-factory", 0x22A00, 0x23297),
    ("replay-feed", 0x19A2D, 0x19B80),
    ("object-pass", 0x234A4, 0x234D3),
    ("object-sort-draw", 0x24B17, 0x24C45),
    ("object-update-static", 0x23A8C, 0x23B50),
    ("object-update-mobile", 0x23CF0, 0x23F60),
    ("object-update-projectile", 0x234E0, 0x237B0),
    ("object-update-fx", 0x237B0, 0x23840),
    ("object-update-player", 0x23800, 0x23840),
    ("object-update-timed", 0x241C0, 0x24480),
    ("object-update-effect-a", 0x24480, 0x244A0),
    ("object-update-effect-b", 0x244A0, 0x24680),
    ("object-update-guided-a", 0x24680, 0x24860),
    ("object-update-guided-b", 0x24860, 0x24997),
    ("object-destroy-transition", 0x24997, 0x24AC1),
    ("object-draw-model", 0x24FED, 0x2514D),
    ("object-draw-sprite", 0x2514D, 0x2519D),
    ("object-draw-fx", 0x24C0A, 0x24C45),
    ("object-init", 0x23297, 0x234A4),
    ("sprite-console", 0x25880, 0x25DBC),
    ("sight-line", 0x25CA2, 0x25D31),
    ("palette", 0x2B820, 0x2B9BA),
    ("mission-transition", 0x28C3E, 0x28F05),
    ("mission-select", 0x28F05, 0x2A299),
    ("reset-surface", 0x19681, 0x196C0),
    ("post-object-7AA0", 0x07AA0, 0x07D25),
    ("post-object-18D20", 0x18D20, 0x18F94),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    parser.add_argument("--base", default="0x6040",
                        help="runtime linear address corresponding to flat 0")
    parser.add_argument("--top", type=int, default=80,
                        help="number of top executed PCs to print")
    parser.add_argument("--pc", action="append", default=[],
                        help="flat DOS PC to count exactly (repeatable)")
    args = parser.parse_args()
    base = int(args.base, 0)
    requested = [int(value, 0) for value in args.pc]
    counts = collections.Counter()
    starts = collections.Counter()
    pcs = collections.Counter()
    event_count = 0
    first = []
    last = collections.deque(maxlen=20)
    with open(args.log, "r", errors="ignore") as stream:
        for line in stream:
            if not line.startswith("Trace"):
                continue
            try:
                pc = int(line.split("[", 1)[1].split("/", 2)[1], 16)
            except (IndexError, ValueError):
                continue
            event_count += 1
            flat = pc - base
            pcs[flat] += 1
            if len(first) < 20:
                first.append((event_count, pc, flat))
            last.append((event_count, pc, flat))
            for name, lo, hi in RANGES:
                if lo <= flat < hi:
                    counts[name] += 1
                if flat == lo:
                    starts[name] += 1

    print(f"trace events: {event_count}")
    if requested:
        print("requested PCs:")
        for flat in requested:
            print(f"  flat=0x{flat:05x} count={pcs[flat]} runtime=0x{flat + base:06x}")
    print("range events:")
    for name, lo, hi in RANGES:
        print(f"  {name:22s} {counts[name]:10d}  entry={starts[name]:8d} "
              f"flat=[0x{lo:05x},0x{hi:05x})")
    print("top PCs in the flat image:")
    for flat, count in pcs.most_common(args.top):
        if 0 <= flat < 0x400000:
            print(f"  {count:10d}  flat=0x{flat:06x}  runtime=0x{flat + base:06x}")
    print("last trace PCs:")
    for n, pc, flat in last:
        print(f"  {n:10d}  flat=0x{flat:06x}  runtime=0x{pc:06x}")


if __name__ == "__main__":
    main()
