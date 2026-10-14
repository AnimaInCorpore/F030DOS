#!/usr/bin/env python3
"""Emit a 32-bit x86 listing for a derived protected-mode image."""

from __future__ import annotations

import argparse
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--origin", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = args.image.read_bytes()
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    decoder.detail = False
    decoder.skipdata = True
    lines = []
    start = args.origin + args.offset
    for instruction in decoder.disasm(data[args.offset :], start):
        encoded = instruction.bytes.hex(" ")
        lines.append(
            f"{instruction.address:08X}  {encoded:<35} "
            f"{instruction.mnemonic:<8} {instruction.op_str}"
        )
    text = "\n".join(lines) + ("\n" if lines else "")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="ascii")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
