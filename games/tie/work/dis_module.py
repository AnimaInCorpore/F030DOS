#!/usr/bin/env python3
"""Disassemble an obj1 address range, annotated with (file, line) anchors.

  python3 work/dis_module.py <MODULE.C|loHex> [hiHex]

Anchors come from work/module_map.py (the 0x9F20C trace-logger calls), so the
listing carries the original source line numbers in the margin.
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
import module_map as mm
import audit_fixups as af

BASE = 0x10000


def main():
    raw = open(os.path.join(os.path.dirname(__file__), "ghidra", "z_tie_obj1.raw"), "rb").read()
    names = mm.source_names(af.data)
    sites = mm.reference_sites()
    anchors = mm.line_anchors(sites, names, raw)

    arg = sys.argv[1]
    if arg.upper().endswith(".C"):
        mod = arg.upper()
        addrs = [a for a, _l in anchors[mod]]
        lo, hi = min(addrs), max(addrs)
        lo -= 0x100                      # a little lead-in before the first anchor
    else:
        lo = int(arg, 16); hi = int(sys.argv[2], 16)
        mod = None

    line_at = {}
    for m, v in anchors.items():
        for a, l in v:
            line_at[a] = (m, l)

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    print(f"; obj1 {lo:#08x}..{hi:#08x}" + (f"  ({mod})" if mod else ""))
    for i in md.disasm(raw[lo - BASE:hi - BASE + 16], lo):
        mark = ""
        for a, (m, l) in line_at.items():
            if i.address <= a < i.address + i.size:
                mark = f"   <== {m}:{l}"
        print(f"  {i.address:08x}  {i.bytes.hex():<14} {i.mnemonic:<7} {i.op_str}{mark}")


if __name__ == "__main__":
    main()
