#!/usr/bin/env python3
"""Patch only a Phar Lap P3 runtime stack-count/size field in a derived file."""

from __future__ import annotations

import argparse
from pathlib import Path

from p3info import parse


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("executable", type=Path)
    ap.add_argument("--offset", type=lambda v: int(v, 0), required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--size-kb", type=int, required=True)
    args = ap.parse_args()

    if args.count < 4 or args.size_kb < 1:
        raise SystemExit("count must be >= 4 and size-kb must be >= 1")
    data = bytearray(args.executable.read_bytes())
    values = parse(data, args.offset)
    runtime = args.offset + int(values["runtime_offset"])
    if data[runtime : runtime + 2] != b"DX":
        raise ValueError(f"unexpected runtime signature at 0x{runtime:X}")
    # RunTimeParameterBlock: min/max real-mode, min/max INT buffer sizes,
    # interrupt-stack count at +0x0A and size in KB at +0x0C.
    data[runtime + 0x0A : runtime + 0x0C] = args.count.to_bytes(2, "little")
    data[runtime + 0x0C : runtime + 0x0E] = args.size_kb.to_bytes(2, "little")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"patched P3 runtime at 0x{runtime:X}: "
          f"int_stack_count={args.count}, int_stack_size_kb={args.size_kb}")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
