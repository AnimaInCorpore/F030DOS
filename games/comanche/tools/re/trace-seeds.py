#!/usr/bin/env python3
"""Turn a QEMU `-d exec,nochain` log into disassembler seeds.

Every address it emits is one QEMU actually executed, so unlike a heuristic
seed each is proof that the bytes there are code. That is what makes a
trace-seeded listing worth merging into the heuristic one: it settles
code-versus-data at every point it touches.

THE ONE THING TO GET RIGHT. A trace line reads

    Trace 0: <host> [<cs_base>/<pc>/<flags>/<...>]

and `pc` is the **linear** address, not EIP. The flat address is
`pc - cs_base`, with cs_base 0x00006040 for this game's flat selector.
Reading `pc` as a flat address shifts every seed by 0x6040 and the
disassembler then renders tables as overlapping nonsense - which is how the
mistake was caught here rather than believed.

Usage:
    python3 tools/re/trace-seeds.py work/qemu_out/attract-exec.log \\
        -o re/seeds-flat-traced.txt
"""
import argparse
import collections
import re

LINE = re.compile(rb'\[([0-9a-f]{8})/0*([0-9a-f]{1,16})/')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--cs-base", default="6040",
                    help="flat selector base in hex (default 6040)")
    ap.add_argument("--content-end", default="32B20",
                    help="hex flat offset where real content stops")
    args = ap.parse_args()
    base = int(args.cs_base, 16)
    end = int(args.content_end, 16)

    seen = collections.Counter()
    blocks = 0
    with open(args.log, "rb") as f:
        tail = b""
        while True:
            chunk = f.read(1 << 24)
            if not chunk:
                break
            data = tail + chunk
            cut = data.rfind(b"\n")
            if cut < 0:
                tail = data
                continue
            for m in LINE.finditer(data[:cut]):
                if int(m.group(1), 16) != base:
                    continue
                flat = int(m.group(2), 16) - base
                if 0 <= flat < end:
                    seen[flat] += 1
                    blocks += 1
            tail = data[cut + 1:]

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("# Block entry points proven executed by a QEMU exec trace.\n")
        f.write(f"# source: {args.log}\n")
        f.write(f"# {blocks} block executions, {len(seen)} distinct entries.\n")
        f.write(f"# flat address = linear pc - cs_base ({base:#07x}); see the\n")
        f.write("# header of tools/re/trace-seeds.py for why that matters.\n")
        for a, c in sorted(seen.items()):
            f.write(f"{a:08X}  # exec {c}\n")
    print(f"{blocks} block executions, {len(seen)} distinct entries -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
