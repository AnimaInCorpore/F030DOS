import re, sys

def load_blocks(path):
    blocks = []
    with open(path) as f:
        for line in f:
            m = re.match(r'^(CODE_\d+)\s+([0-9a-f]{4}):([0-9a-f]{4,8})\s+\.\.\s+([0-9a-f]{4}):([0-9a-f]{4,8})\s+\((\d+) bytes', line.strip())
            if m:
                name, seg1, off1, seg2, off2, size = m.groups()
                seg1 = int(seg1,16); off1=int(off1,16); seg2=int(seg2,16); off2=int(off2,16); size=int(size)
                assert seg1==seg2, f"seg mismatch {line}"
                blockFileStart = ((seg1-0x1000)<<4) + off1 + 0x3200
                blocks.append((name, seg1, off1, off2, size, blockFileStart))
    return blocks

blocks = load_blocks('work/ghidra_export/memory_layout.txt')
print("total blocks:", len(blocks), file=sys.stderr)

def find_block(F):
    for name, seg, off1, off2, size, bfs in blocks:
        if bfs <= F < bfs+size:
            return name, seg, off1, off2, size, bfs
    return None

def true_segoff(F):
    b = find_block(F)
    if not b: return None
    name, seg, off1, off2, size, bfs = b
    off = off1 + (F - bfs)
    return dict(block=name, seg=seg, off=off, blockFileStart=bfs, blockFileEnd=bfs+size-1, size=size)

targets = [0x138ef, 0x13b19, 0x13b7e, 0x13eb2, 0x1500d, 0x15a7c, 0x21d68,
           0x3d9ca, 0x3d9d3, 0x3d9db, 0x3db02]
for F in targets:
    r = true_segoff(F)
    if r:
        print(f"file 0x{F:x} -> {r['block']} {r['seg']:04x}:{r['off']:04x}  (block file 0x{r['blockFileStart']:x}..0x{r['blockFileEnd']:x}, size {r['size']})")
    else:
        print(f"file 0x{F:x} -> NOT FOUND")
