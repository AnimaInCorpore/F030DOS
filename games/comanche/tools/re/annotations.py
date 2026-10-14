#!/usr/bin/env python3
"""Validate re/annotations.txt and project it into the analysis tools.

The annotation file is the system of record; Cutter and rizin are workbenches
whose state is regenerated from it.  That direction matters.  A binary project
database accumulates hundreds of small findings that no one can review, and the
one thing this binary has already proved is that a plausible-looking wrong
answer survives unless something checks it against the bytes.

check         validate every row against the carved image and print the ledger
export-rizin  emit a rizin script that recreates the annotations as flags,
              functions, data definitions and comments
export-ghidra emit a Ghidra script that does the same, so a Ghidra project
              starts from what has already been proved instead of cold

A ? candidate is exported as a comment only.  It never defines a function or a
data type, so an unproven guess cannot become load-bearing by accident.  That
rule is the same in both exporters and is the reason they are generated rather
than hand-maintained: the store is the one place a promotion has to happen.
"""
import argparse
import base64
import json
import re
import struct
import sys
from pathlib import Path

DEFAULT_STORE = "re/annotations.txt"
DEFAULT_IMAGE = "re/unpacked/comanche-flat32.bin"
KINDS = {"func", "table", "data", "string", "pad"}
NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")


class Row:
    __slots__ = ("kind", "candidate", "addr", "extent", "name", "evidence", "line", "width")

    def __init__(self, kind, candidate, addr, extent, name, evidence, line):
        self.kind = kind
        # Element width in bytes, from an `elem=N` tag in the evidence. It is
        # what decides whether a region has to be byte-swapped for a 68k, and
        # how: a dword table needs a 4-byte swap, a word table a 2-byte one, a
        # byte array and a string none at all. Nothing else in the store can
        # answer that, and getting it wrong is silent.
        m = WIDTH_RE.search(evidence)
        self.width = int(m.group(1)) if m else None
        self.candidate = candidate
        self.addr = addr
        self.extent = extent          # None when the end is not established
        self.name = name
        self.evidence = evidence
        self.line = line

    @property
    def end(self):
        return self.addr + (self.extent or 0)


# A distinct tag, not `width=`: evidence prose already says things like
# "width=1012" about pixels, and a validator that reads those as element
# widths turns a description into an error.
WIDTH_RE = re.compile(r"\belem=(\d+)\b")
ELEMENT_WIDTHS = {1, 2, 4}


def parse(path: Path):
    rows, errors = [], []
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        text = raw.split("#", 1)
        body = text[0].strip()
        evidence = text[1].strip() if len(text) > 1 else ""
        if not body:
            continue
        parts = body.split()
        if len(parts) != 4:
            errors.append(f"{path}:{n}: expected 4 columns, got {len(parts)}: {body!r}")
            continue
        kind, addr, extent, name = parts
        candidate = kind.startswith("?")
        kind = kind.lstrip("?")
        if kind not in KINDS:
            errors.append(f"{path}:{n}: unknown kind {kind!r}, expected one of {sorted(KINDS)}")
            continue
        if not NAME_RE.match(name):
            errors.append(f"{path}:{n}: {name!r} is not a valid identifier")
            continue
        try:
            addr_v = int(addr, 16)
            extent_v = None if extent == "-" else int(extent, 16)
        except ValueError:
            errors.append(f"{path}:{n}: address/extent must be hex: {addr!r} {extent!r}")
            continue
        if not evidence:
            errors.append(f"{path}:{n}: {name} has no evidence after #")
            continue
        rows.append(Row(kind, candidate, addr_v, extent_v, name, evidence, n))
    return rows, errors


def validate(rows, image_size):
    """Catch the mistakes that would otherwise be discovered as wrong analysis."""
    errors = []
    seen = {}
    for r in rows:
        if r.name in seen:
            errors.append(f"line {r.line}: duplicate name {r.name} (also line {seen[r.name]})")
        seen[r.name] = r.line
        if not 0 <= r.addr < image_size:
            errors.append(f"line {r.line}: {r.name} at {r.addr:08X} is outside the "
                          f"{image_size}-byte content region")
        elif r.end > image_size:
            errors.append(f"line {r.line}: {r.name} extends to {r.end:08X}, past the "
                          f"content region")

    for r in rows:
        if r.width is None:
            continue
        if r.kind not in ("table", "data"):
            errors.append(f"line {r.line}: {r.name} is a {r.kind}, which has no "
                          f"element width")
        elif r.width not in ELEMENT_WIDTHS:
            errors.append(f"line {r.line}: {r.name} has width={r.width}, expected "
                          f"one of {sorted(ELEMENT_WIDTHS)}")
        elif r.extent and r.extent % r.width:
            errors.append(f"line {r.line}: {r.name} is {r.extent:#x} bytes, not a "
                          f"multiple of width={r.width}")

    # Overlap check, sized rows only. Two owners for one byte means at least one
    # of them is wrong, and it is cheaper to find out here than in a listing.
    sized = sorted((r for r in rows if r.extent), key=lambda r: r.addr)
    for a, b in zip(sized, sized[1:]):
        if b.addr < a.end:
            errors.append(f"line {b.line}: {b.name} at {b.addr:08X} overlaps "
                          f"{a.name} ({a.addr:08X}-{a.end:08X})")
    return errors


def filler_run_bytes(block: bytes, value: int = 0x80, minimum: int = 16) -> int:
    """Bytes in long runs of this program's padding byte.

    Zero is not the only filler: the linker pads with 0x80, and 10,368 bytes of
    the content region sit in three such runs. Counted as material they inflate
    the remaining work and misrank it. Only runs are discounted, so a genuine
    0x80 inside real data still counts.
    """
    total, i, n = 0, 0, len(block)
    while i < n:
        if block[i] != value:
            i += 1
            continue
        j = i
        while j < n and block[j] == value:
            j += 1
        if j - i >= minimum:
            total += j - i
        i = j
    return total


def alignment_filler_bytes(block: bytes, minimum: int = 6) -> int:
    """Bytes in runs of the linker's `2E 8B C0` alignment padding.

    The 0x80 runs above are reserved buffers; this is the other filler, a
    `cs: mov eax,eax` the linker repeats between routines to align the next
    one. 2,438 bytes of the content region sit in 372 such runs, none of them
    long enough for the 0x80 rule to catch and every one of them counted as
    material outstanding.

    Two of them is the minimum, because a single one is as likely to be a real
    `mov eax,eax` inside a routine as it is to be padding, and runs are what
    the linker emits.
    """
    pad = bytes((0x2E, 0x8B, 0xC0))
    total, i, n = 0, 0, len(block)
    while i + 3 <= n:
        if block[i:i + 3] != pad:
            i += 1
            continue
        j = i
        while j + 3 <= n and block[j:j + 3] == pad:
            j += 3
        if j - i >= minimum:
            total += j - i
        i = j
    return total


def material_bytes(block: bytes) -> int:
    """Bytes in a block that count as material: not zero, not filler runs."""
    return (len(block) - block.count(0) - filler_run_bytes(block)
            - alignment_filler_bytes(block))


def ledger(rows, image: bytes):
    """What is classified, what is left, measured against real material.

    Zero bytes are reported separately.  A third of the content region is zero,
    and counting it as work outstanding makes the remaining job look half again
    as large as it is.

    Numerator and denominator must use the SAME definition of material, and for
    a long time they did not: this counted each row's whole extent but divided
    by material, so a row over a mostly-zero region credited its zeros as
    classified material even though those bytes were never in the denominator.
    `object_table_dwords` alone is 7,280 bytes of extent carrying 1,300 bytes of
    material, and `dma_buffer_8k` is 8,192 bytes of pure zero; together the rows
    like that overstated progress by about 41,000 bytes, which read as 89.7%
    when the real figure was 64.7%. Each row now contributes only the material
    inside its own extent.
    """
    total = len(image)
    zeros = image.count(0)
    filler = filler_run_bytes(image)
    align = alignment_filler_bytes(image)
    by_kind, classified, padded = {}, 0, 0
    for r in rows:
        if not r.extent:
            continue
        # `pad` is knowledge, not progress against material: the zero and 0x80
        # runs it names are already excluded from the denominator, so counting
        # it here would credit the same bytes twice. It is reported separately
        # rather than in the breakdown, so the breakdown sums to `classified`.
        if r.kind == "pad":
            padded += r.extent
        else:
            held = material_bytes(image[r.addr:r.addr + r.extent])
            by_kind[r.kind] = by_kind.get(r.kind, 0) + held
            classified += held

    material = total - zeros - filler - align
    print(f"content region     {total:>8} bytes")
    print(f"  zero fill        {zeros:>8} bytes ({100*zeros/total:.1f}%)")
    print(f"  0x80 padding     {filler:>8} bytes ({100*filler/total:.1f}%)")
    print(f"  2E8BC0 alignment {align:>8} bytes ({100*align/total:.1f}%)")
    print(f"  material         {material:>8} bytes")
    print()
    print(f"classified         {classified:>8} bytes ({100*classified/material:.1f}% of material)")
    for kind in sorted(by_kind):
        print(f"  {kind:<15} {by_kind[kind]:>8} bytes")
    if padded:
        print(f"  (plus {padded} bytes named as pad, already outside material)")
    unsized = sum(1 for r in rows if not r.extent)
    candidates = sum(1 for r in rows if r.candidate)
    print(f"\n{len(rows)} rows, {unsized} without an established extent, "
          f"{candidates} unproven candidates")
    swappable = [r for r in rows if r.kind in ("table", "data") and r.extent]
    declared = [r for r in swappable if r.width]
    print()
    print(f"element width declared for {len(declared)} of {len(swappable)} "
          f"table/data rows, "
          f"{sum(r.extent for r in declared)} of "
          f"{sum(r.extent for r in swappable)} bytes")
    undeclared = [r for r in swappable if not r.width]
    if undeclared:
        print(f"  {len(undeclared)} rows still need one before they can be "
              f"byte-swapped for the 68k")
    print(f"remaining          {material - classified:>8} bytes of material to classify")


def comment(text: str, addr: str) -> str:
    """A rizin comment that survives arbitrary evidence text.

    Evidence routinely contains ';' and '@', which rizin's parser treats as a
    command separator and an address specifier, so a raw CCu silently truncates
    the comment or executes part of it. base64 removes the question.
    """
    encoded = base64.b64encode(text.encode()).decode()
    return f"CCu base64:{encoded} @ {addr}\n"


def export_rizin(rows, out):
    """Emit a rizin script, applied with: rizin -i <file>, or `. <file>` inside.

    Two rizin behaviours shape this output. Lines starting with '#' are not
    comments - the parser fails on them and reports the whole file as one bad
    command. And plain `af` on a raw blob follows control flow until it runs
    out, which made a documented 158-byte routine come back as 2168 bytes
    spanning 88 KB; `af+` with an explicit `afb+` block uses the extent this
    store establishes instead of rizin's guess.
    """
    w = out.write
    w("echo [annotations] generated by tools/re/annotations.py - edit "
      "re/annotations.txt and regenerate\n")
    w("fs annotations\n\n")
    for r in rows:
        addr = f"0x{r.addr:08x}"
        if r.candidate:
            # Comment only. A candidate must not create a function or a type,
            # so it cannot become load-bearing without being promoted first.
            w(comment(f"candidate {r.name}: {r.evidence}", addr))
            w("\n")
            continue
        size = f" {r.extent}" if r.extent else ""
        if r.kind == "func":
            if r.extent:
                w(f"af+ {r.name} @ {addr}\n")
                w(f"afb+ {addr} {addr} {r.extent}\n")
            else:
                # No established extent, so let analysis propose one. Expect it
                # to over-reach; establishing the real end is the work.
                w(f"af @ {addr}\n")
                w(f"afn {r.name} @ {addr}\n")
        elif r.kind == "table":
            w(f"f obj.{r.name}{size} @ {addr}\n")
            if r.extent and r.extent % 4 == 0:
                w(f"Cd 4 {r.extent // 4} @ {addr}\n")
        elif r.kind == "string":
            w(f"f str.{r.name}{size} @ {addr}\n")
            w(f"Cs @ {addr}\n")
        else:
            w(f"f obj.{r.name}{size} @ {addr}\n")
        w(comment(r.evidence, addr))
        w("\n")


GHIDRA_PREAMBLE = '''\
# Comanche annotations, generated by tools/re/annotations.py.
# Edit re/annotations.txt and regenerate; do not edit this file.
#
# Run it against a project created from tools/re/carve-flat.py output:
#
#   analyzeHeadless <proj_dir> <proj_name> \\
#       -import re/unpacked/comanche-flat32.bin \\
#       -processor x86:LE:32:default \\
#       -loader BinaryLoader -loader-baseAddr 0 \\
#       -postScript apply_annotations.py
#
# The carved image is the 32-bit flat region and its addresses ARE the flat
# addresses every document in this repository uses, so it loads at base 0 and
# nothing here is rebased. Do NOT point this at the packed or the unpacked
# load module: those carry the MZ header and the 16-bit bootstrap ahead of the
# flat region, every address below would be short by the carve offset, and the
# result would look plausible because the names would still land on code.
#
# GhidraDosToolbox's loader and INT mapping are for 16-bit real-mode DOS. This
# image is 32-bit protected mode reached through a custom extender, so that
# extension does not apply to it; the bootstrap it would help with is already
# classified in re/listings/comanche-bootstrap.lst.
import json

from ghidra.program.model.symbol import SourceType
from ghidra.program.model.address import AddressSet

# The store's addresses are absolute in the flat region. If a project was
# deliberately loaded somewhere else, set this to that base.
BASE = 0

ROWS = json.loads(
'''


GHIDRA_BODY = '''\
)


def addr(value):
    return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(
        BASE + value)


def main():
    listing = currentProgram.getListing()
    functions = currentProgram.getFunctionManager()
    symbols = currentProgram.getSymbolTable()
    made_func = made_label = made_comment = skipped = 0

    for row in ROWS:
        at = addr(row["addr"])
        extent = row["extent"]

        # A candidate carries evidence and nothing else. Creating a function or
        # a label for one would let an unproven reading look identical to a
        # proved one in the listing, which is the failure this store exists to
        # prevent.
        if row["candidate"]:
            listing.setComment(at, 3, "candidate %s: %s" % (row["name"], row["evidence"]))
            made_comment += 1
            continue

        listing.setComment(at, 3, row["evidence"])
        made_comment += 1

        if row["kind"] == "func":
            existing = functions.getFunctionAt(at)
            if existing is not None:
                existing.setName(row["name"], SourceType.USER_DEFINED)
                made_func += 1
                continue
            body = None
            if extent:
                # Use the extent the store establishes rather than letting
                # Ghidra follow control flow off the end of the routine. The
                # rizin exporter had to do the same for the same reason: a
                # documented 158-byte routine came back as 2168 bytes.
                body = AddressSet(at, addr(row["addr"] + extent - 1))
            try:
                if body is not None:
                    functions.createFunction(row["name"], at, body,
                                             SourceType.USER_DEFINED)
                else:
                    createFunction(at, row["name"])
                made_func += 1
            except Exception as exc:
                # Overlapping bodies and addresses inside an existing function
                # are expected while the store and Ghidra's own analysis
                # disagree. Say so rather than failing the whole run.
                print("skip func %s at %08x: %s" % (row["name"], row["addr"], exc))
                skipped += 1
                symbols.createLabel(at, row["name"], SourceType.USER_DEFINED)
        else:
            symbols.createLabel(at, row["name"], SourceType.USER_DEFINED)
            made_label += 1

    print("annotations: %d functions, %d labels, %d comments, %d skipped"
          % (made_func, made_label, made_comment, skipped))


main()
'''


def export_ghidra(rows, out):
    """Emit a Ghidra script that recreates the store in a fresh project.

    The rows travel as embedded JSON rather than as generated statements.
    Evidence text contains quotes, backslashes and non-ASCII, and every scheme
    that formats it into source has to get all three right; json.dumps already
    does, and the repr() around it is valid Python by construction.
    """
    payload = json.dumps([
        {
            "kind": r.kind,
            "candidate": r.candidate,
            "addr": r.addr,
            "extent": r.extent,
            "name": r.name,
            "evidence": r.evidence,
        }
        for r in rows
    ], indent=1)
    out.write(GHIDRA_PREAMBLE)
    out.write(repr(payload))
    out.write("\n")
    out.write(GHIDRA_BODY)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["check", "export-rizin", "export-ghidra"])
    ap.add_argument("--store", default=DEFAULT_STORE)
    ap.add_argument("--image", default=DEFAULT_IMAGE,
                    help="carved flat region from tools/re/carve-flat.py")
    ap.add_argument("-o", "--out", help="output path for export-rizin (default: stdout)")
    args = ap.parse_args()

    store = Path(args.store)
    if not store.is_file():
        print(f"error: {store} not found", file=sys.stderr)
        return 1
    rows, errors = parse(store)

    image = b""
    img_path = Path(args.image)
    if img_path.is_file():
        image = img_path.read_bytes()
    elif args.command == "check":
        print(f"error: {img_path} not found - run tools/re/carve-flat.py first",
              file=sys.stderr)
        return 1

    if image:
        errors += validate(rows, len(image))
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1

    if args.command == "check":
        print(f"{store}: {len(rows)} rows, no errors\n")
        ledger(rows, image)
        return 0

    exporter = export_ghidra if args.command == "export-ghidra" else export_rizin

    if args.out:
        # LF, always. rizin's `.` reads the script as one buffer and does not
        # split CRLF lines, so a Windows-newline script arrives as a single
        # unparseable command. Python tolerates either, so one rule covers both.
        with open(args.out, "w", newline="\n", encoding="utf-8") as fh:
            exporter(rows, fh)
        print(f"wrote {args.out} ({len(rows)} rows)")
        if args.command == "export-ghidra":
            print("apply with analyzeHeadless -postScript, or in the GUI's "
                  "Script Manager; see the header of the generated file")
        else:
            print(f"apply in Cutter or rizin with:  . {args.out}")
    else:
        exporter(rows, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
