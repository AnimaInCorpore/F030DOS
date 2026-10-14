#!/usr/bin/env python3
"""Decode DATA/STRINGS.PAK -- the global Huffman-coded string table.

Format, measured from the file (analysis/data-formats.md, "STRINGS.PAK"):

  u16LE  node_count                      (181 in BOTH UW1 and UW2)
  node_count x { u8 char, u8 parent, u8 left, u8 right }   @0x02
        0xFF in left AND right marks a leaf; the last node is the root
        (parent == 0xFF).  Leaves come first, sorted by char.
  u16LE  block_count                     @0x02 + 4*node_count
  block_count x { u16LE block_id, u32LE file_offset }, ascending by both
  per block, at file_offset:
        u16LE  string_count
        string_count x u16LE  byte offset of that string, relative to the
                              END of this per-block offset array
        Huffman bit stream: MSB-first, 0 = left child, 1 = right child,
        walk from the root, emit the leaf char, restart at the root.
        A '|' (0x7C) leaf terminates the string.  Every string starts on a
        byte boundary, so a block's strings are independently addressable.

Verification (both games, see the doc): the block table ends exactly where
the first block begins, and the last string's final byte lands exactly on
EOF -- zero unaccounted bytes.

Usage:
  python work/strings_decode.py                  # summary + coverage proof
  python work/strings_decode.py --dump out.txt   # every string, by block
  python work/strings_decode.py --block 0x0e01   # one block
"""
import argparse
import struct
import sys
from pathlib import Path

DEFAULT_PAK = Path("work/extracted/D1/DATA/STRINGS.PAK")
TERMINATOR = 0x7C  # '|'
NONE = 0xFF


class Strings:
    def __init__(self, data):
        self.d = data
        self.node_count = struct.unpack_from("<H", data, 0)[0]
        self.nodes = [struct.unpack_from("<4B", data, 2 + 4 * i)
                      for i in range(self.node_count)]
        self.root = self.node_count - 1
        p = 2 + 4 * self.node_count
        self.block_count = struct.unpack_from("<H", data, p)[0]
        p += 2
        self.blocks = [struct.unpack_from("<HI", data, p + 6 * i)
                       for i in range(self.block_count)]
        self.block_table_end = p + 6 * self.block_count
        self.last_byte = 0  # highest byte index consumed by any string

    @property
    def leaves(self):
        return sorted(c for c, _, l, r in self.nodes if l == NONE and r == NONE)

    def _decode(self, base, pos):
        out = []
        node = self.root
        bit = 0
        while True:
            byte = self.d[base + pos + (bit >> 3)]
            b = (byte >> (7 - (bit & 7))) & 1
            bit += 1
            node = self.nodes[node][2] if b == 0 else self.nodes[node][3]
            char, _, left, right = self.nodes[node]
            if left == NONE and right == NONE:
                if char == TERMINATOR:
                    self.last_byte = max(self.last_byte,
                                         base + pos + ((bit + 7) >> 3))
                    return "".join(out)
                out.append(chr(char))
                node = self.root

    def block(self, block_id):
        off = dict(self.blocks)[block_id]
        n = struct.unpack_from("<H", self.d, off)[0]
        offsets = struct.unpack_from(f"<{n}H", self.d, off + 2)
        base = off + 2 + 2 * n
        return [self._decode(base, o) for o in offsets]

    def all_blocks(self):
        return {bid: self.block(bid) for bid, _ in self.blocks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pak", nargs="?", type=Path, default=DEFAULT_PAK)
    ap.add_argument("--dump", type=Path, help="write every string to this file")
    ap.add_argument("--block", help="print one block (hex or decimal id)")
    args = ap.parse_args()

    s = Strings(args.pak.read_bytes())

    if args.block is not None:
        bid = int(args.block, 0)
        for i, text in enumerate(s.block(bid)):
            print(f"[{i:4d}] {text!r}")
        return

    blocks = s.all_blocks()
    total = sum(len(v) for v in blocks.values())
    leaves = s.leaves
    print(f"{args.pak}: {len(s.d)} B (0x{len(s.d):x})")
    print(f"  huffman   : {s.node_count} nodes = {len(leaves)} leaves "
          f"+ {s.node_count - len(leaves)} internal "
          f"(full tree 2L-1: {2 * len(leaves) - 1 == s.node_count})")
    print(f"  alphabet  : {''.join(chr(c) if 32 <= c < 127 else f'<{c:02x}>' for c in leaves)}")
    print(f"  blocks    : {s.block_count}, ids 0x{min(blocks):x}..0x{max(blocks):x}")
    print(f"  block tbl ends 0x{s.block_table_end:x}, first block 0x{s.blocks[0][1]:x} "
          f"-> contiguous: {s.block_table_end == s.blocks[0][1]}")
    print(f"  strings   : {total}, {sum(len(t) for v in blocks.values() for t in v)} chars")
    print(f"  coverage  : last string byte 0x{s.last_byte:x}, EOF 0x{len(s.d):x} "
          f"-> {len(s.d) - s.last_byte} B unaccounted")

    if args.dump:
        with args.dump.open("w", encoding="utf-8") as fh:
            for bid in sorted(blocks):
                fh.write(f"=== block 0x{bid:04x} ({len(blocks[bid])} strings) ===\n")
                for i, text in enumerate(blocks[bid]):
                    fh.write(f"[{i:4d}] {text}\n")
        print(f"  dumped    : {args.dump}")


if __name__ == "__main__":
    sys.exit(main())
