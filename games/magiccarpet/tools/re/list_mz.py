#!/usr/bin/env python3
"""Emit a bounded Capstone 16-bit listing for an MZ load module.

This is a portable fallback for the documented ``ndisasm -b 16`` command.
It intentionally lists only the MZ load image; it never decodes the appended
LE header or protected-mode data pages.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from capstone import CS_ARCH_X86, CS_MODE_16, Cs
except ImportError:
    raise SystemExit("capstone is required: python -m pip install capstone")

from mzinfo import parse_mz


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = args.executable.read_bytes()
    mz = parse_mz(data)
    image = data[mz["hdrsize"]:mz["imagesize"]]
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    lines = [f"; source: {args.executable}",
             f"; bounded MZ load image: file 0x{mz['hdrsize']:X}..0x{mz['imagesize']:X}",
             "; addresses below are load-image offsets; LE payload is excluded"]
    for insn in md.disasm(image, 0):
        lines.append(f"{insn.address:08X}  {insn.bytes.hex():<24} "
                     f"{insn.mnemonic:<8} {insn.op_str}")
    text = "\n".join(lines) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
