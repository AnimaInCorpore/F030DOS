#!/usr/bin/env python3
"""P1.3 -- slice Z_TIE__.EXE's two LE objects into flat, load-ready images for
Ghidra's per-object import (analysis/ztie.md SS4, todo.md P1.3).

obj1 (code): file 0x3D800..0xE8800 (0xAB000 B) -- straight slice, base linear
0x10000. obj2 (data): file 0xE8800..EOF (0x13547 B physical) + zero-filled BSS
pad up to vsize 0x46470 (what the LE loader itself does at load time), base
linear 0xC0000.

Reuses work/audit_fixups.py's verified LE-header parse (objs table, page_file_off)
rather than re-deriving it, and asserts the page map is identity before treating
either object as one contiguous file slice (a reordered page map would make a
flat slice wrong -- ztie.md SS1 already records "identity page map", checked
again here at build time).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import audit_fixups as af  # noqa: E402  (reuses its LE parse: af.data, af.objs, af.page_file_off)

OUT_DIR = os.path.join(os.path.dirname(__file__), "ghidra")
OUT1 = os.path.join(OUT_DIR, "z_tie_obj1.raw")
OUT2 = os.path.join(OUT_DIR, "z_tie_obj2.raw")

data = af.data
objs = af.objs
assert len(objs) == 2, objs
obj1, obj2 = objs
assert obj1["base"] == 0x10000 and obj2["base"] == 0xC0000, objs

# Identity page map: page-map index i must resolve to physical page i (pmap[i]==i+1),
# i.e. page_file_off(i) == dpo + i*page_size for every page. If this ever fails, a
# flat slice is wrong and this script must switch to per-page assembly.
for i in range(af.num_pages):
    expected = af.dpo + i * af.page_size
    got = af.page_file_off(i)
    assert got == expected, f"page {i}: file_off=0x{got:X} != identity 0x{expected:X}"

file1_start = af.page_file_off(obj1["first"] - 1)
file2_start = af.page_file_off(obj2["first"] - 1)
size1 = obj1["npages"] * af.page_size
assert (file1_start, file2_start, size1) == (0x3D800, 0xE8800, 0xAB000), \
    (hex(file1_start), hex(file2_start), hex(size1))

os.makedirs(OUT_DIR, exist_ok=True)

obj1_bytes = data[file1_start:file2_start]
assert len(obj1_bytes) == size1
with open(OUT1, "wb") as f:
    f.write(obj1_bytes)

obj2_physical = data[file2_start:]
assert len(obj2_physical) == len(data) - file2_start == 0x13547, len(obj2_physical)
pad = obj2["vsize"] - len(obj2_physical)
assert 0 <= pad, pad
obj2_bytes = obj2_physical + b"\x00" * pad
assert len(obj2_bytes) == obj2["vsize"] == 0x46470
with open(OUT2, "wb") as f:
    f.write(obj2_bytes)

# Worked check (ztie.md SS4 pattern): "You must run TIE.EXE for the game.\n" is at
# file 0xE881A = obj2 offset 0x1A.
needle = b"You must run TIE.EXE for the game.\n"
got = obj2_bytes[0x1A:0x1A + len(needle)]
assert got == needle, f"obj2[0x1A:] = {got!r}, expected {needle!r}"

print(f"obj1: file 0x{file1_start:X}..0x{file2_start:X} ({size1} B) -> {OUT1}, base 0x{obj1['base']:X}")
print(f"obj2: file 0x{file2_start:X}..EOF physical {len(obj2_physical)} B + "
      f"0x{pad:X} B BSS pad = 0x{len(obj2_bytes):X} B -> {OUT2}, base 0x{obj2['base']:X}")
print("worked check ok: obj2[0x1A:] = \"You must run TIE.EXE for the game.\\n\"")
