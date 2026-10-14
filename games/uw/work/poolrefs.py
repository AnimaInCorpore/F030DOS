#!/usr/bin/env python3
"""Find references to the embedded string pool (file 0x5F000..0x62000) via
separate 16-bit (off,seg) immediate pairs, per uwexe.md §10.

Address model (verified 2026-08-19, re-tiling of memory_layout.txt):
  loader image: file F in [0x3200,0x66B30) -> seg = 0x1000+(((F-0x3200)&~0xF)>>4),
                off = F - ((seg-0x1000)*16 + 0x3200)
                i.e. F = (seg-0x1000)*16 + off + 0x3200
  tail: CODE_TAIL raw == file offset (>= 0x66B30)
  functions.txt raw addr: loader = (seg-0x1000)*16+off (= F-0x3200); tail = F
"""
import re, struct, bisect

F = open('work/expanded/UW.EXE','rb').read()

def segoff_of(F0):
    seg = 0x1000 + (((F0-0x3200) & ~0xF) >> 4)
    off = F0 - ((seg-0x1000)*16 + 0x3200)
    return seg, off

# --- string pool entries
strs = []
for line in open('work/uw_strings.txt'):
    m = re.match(r'0x([0-9a-fA-F]{5,6})\s+(.*)', line)
    if not m: continue
    off = int(m.group(1),16)
    s = m.group(2).strip()
    if 0x5F000 <= off < 0x62000 and len(s) >= 3:
        strs.append((off, s))
print(f"# {len(strs)} pool strings in 0x5F000..0x62000")

# --- function table (raw addr coords; see header)
fns = []
for line in open('work/ghidra_export/functions.txt'):
    m = re.match(r'([0-9a-fA-F]{4,5}):([0-9a-fA-F]{4})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)', line)
    if m:
        a = (int(m.group(1),16)-0x1000)*16 + int(m.group(2),16)  # == fileoff-0x3200
        fns.append([a, m.group(4), m.group(1)+':'+m.group(2)])
    else:
        m = re.match(r'CODE_TAIL::([0-9a-fA-F]{4,6})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)', line)
        if m:
            a = int(m.group(1),16)  # == fileoff
            fns.append([a, m.group(4), 'CODE_TAIL::'+m.group(1)])
fns.sort()
fstarts = [f[0] for f in fns]

def hit_raw(fileoff):
    return fileoff - 0x3200 if fileoff < 0x66B30 else fileoff

def enclosing_fn(fileoff):
    r = hit_raw(fileoff)
    i = bisect.bisect_right(fstarts, r) - 1
    if i >= 0:
        return fns[i][1], fns[i][2]
    return None, None

def in_code(fileoff):
    if fileoff < 0x3100 or fileoff > 0x89250: return False
    if 0x5F000 <= fileoff < 0x62000: return False   # the pool itself
    return True

report = []
for off, s in strs:
    seg, o = segoff_of(off)
    hits = []
    for pat, order in ((struct.pack('<HH', o, seg), 'off,seg'),
                       (struct.pack('<HH', seg, o), 'seg,off')):
        i = F.find(pat)
        while i != -1:
            if in_code(i):
                hits.append((i, order))
            i = F.find(pat, i+1)
    hits.sort()
    report.append((off, s, hits))

total = sum(len(r[2]) for r in report)
print(f"# total hits: {total}\n")
for off, s, hits in report:
    if not hits: continue
    disp = s if len(s) < 44 else s[:41]+'...'
    print(f"0x{off:05X}  {disp!r}: {len(hits)} hit(s)")
    for h, order in hits[:12]:
        fn, addr = enclosing_fn(h)
        print(f"    file {h:#07x} ({order})  in {fn} @ {addr}")
    if len(hits) > 12:
        print(f"    ... +{len(hits)-12} more")
