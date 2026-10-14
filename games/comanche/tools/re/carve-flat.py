#!/usr/bin/env python3
"""Carve the 32-bit flat game region out of the unpacked DOS load module.

The unpacked image is three things end to end: a 16-bit real-mode bootstrap, the
32-bit flat program, and the linker's zero-filled BSS.  Only the middle part is
the game.  External tools have no loader for a homebrew DOS extender, so hand
them exactly that region as a raw binary instead.

The address model is the whole point of doing this.  The extender installs its
32-bit code selector (0x20) and data selector (0x08) with the same base, at
image offset 0x1700, so a flat address F is image offset 0x1700 + F.  The carved
file begins at that base, which makes file offset 0 the same thing as flat
address 0.  Load it at base 0x0 and every address rizin, Cutter or objdump
prints is the address the program uses internally, the address disasm.py --flat
prints, and the address docs/X86-M68K-MAP.md records.

Loading it at 0x1700 instead - the obvious-looking choice, since that is where
the region sits in the file - biases every address by 0x1700 and silently
disagrees with every other tool and document in this repository.

See docs/RE-WORKFLOW.md for how the selector bases were measured.
"""
import argparse
import importlib.util
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_EXE = "re/unpacked/COMANCHE.UNPACKED.EXE"
DEFAULT_OUT = "re/unpacked/comanche-flat32.bin"
# Image offset of the shared 32-bit code/data selector base, from the GDT
# builder at 0000:14A7.  This is also where the real-mode bootstrap ends.
SELECTOR_BASE = 0x1700


def load_disassembler():
    """Borrow disasm.py's content-end detection rather than restating it.

    The two tools must agree on where the BSS starts or their coverage
    denominators disagree, which is exactly the kind of quiet inconsistency
    that made the old 386,823-byte denominator look like a failure.
    """
    spec = importlib.util.spec_from_file_location("disasm", HERE / "disasm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Disassembler


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exe", nargs="?", default=DEFAULT_EXE,
                    help=f"unpacked DOS MZ load module (default: {DEFAULT_EXE})")
    ap.add_argument("-o", "--out", default=DEFAULT_OUT,
                    help=f"carved output (default: {DEFAULT_OUT})")
    ap.add_argument("--base", default=f"{SELECTOR_BASE:x}",
                    help="hex image offset of the selector base (default: 1700)")
    ap.add_argument("--content-end", metavar="OFFSET",
                    help="hex image offset where content stops (default: detected)")
    args = ap.parse_args()

    exe = Path(args.exe)
    if not exe.is_file():
        print(f"error: {exe} not found - unpack COMANCHE.EXE first, see "
              f"docs/RE-WORKFLOW.md", file=sys.stderr)
        return 1

    data = exe.read_bytes()
    if data[:2] not in (b"MZ", b"ZM"):
        print(f"error: {exe} has no MZ signature; this is the unpacked load "
              f"module, not the packed original", file=sys.stderr)
        return 1

    # Image offsets throughout this repository are offsets into the LOAD MODULE,
    # not into the file: disasm.py, mzinfo.py and the documented 0x1700 selector
    # base all count from the first byte after the MZ header.  Carving from the
    # file start instead shifts the whole region by the 512-byte header, which
    # is large enough to land inside neighbouring code and small enough that the
    # result still disassembles into plausible-looking instructions.
    hdrsize = struct.unpack_from("<H", data, 8)[0] * 16
    pages, last = struct.unpack_from("<HH", data, 4)
    imagesize = pages * 512 - (512 - last if last else 0)
    image = data[hdrsize:imagesize]

    base = int(args.base, 16)
    if args.content_end is not None:
        end = int(args.content_end, 16)
    else:
        end = load_disassembler()(image).content_end()

    if not base < end <= len(image):
        print(f"error: content region {base:#x}-{end:#x} does not fit a "
              f"{len(image)}-byte image", file=sys.stderr)
        return 1

    region = image[base:end]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(region)

    zeros = region.count(0)
    print(f"file          {len(data)} bytes, MZ header {hdrsize}")
    print(f"load module   {len(image)} bytes")
    print(f"  bootstrap   {base} bytes at image 0x00000 (16-bit, not carved)")
    print(f"  content     {len(region)} bytes at image {base:#07x}")
    print(f"  zero fill   {len(image) - end} bytes at image {end:#07x} (BSS, not carved)")
    print()
    print(f"wrote {out} ({len(region)} bytes)")
    print(f"  {zeros} zero bytes ({100 * zeros / len(region):.1f}%), "
          f"{len(region) - zeros} bytes of material")
    print()
    print("Load at base 0x0 so printed addresses are flat game addresses:")
    print(f"  rizin -a x86 -b 32 -m 0 -e asm.var=false {out}")
    print("In Cutter: Advanced > Raw, arch x86, bits 32, base 0x0, offset 0x0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
