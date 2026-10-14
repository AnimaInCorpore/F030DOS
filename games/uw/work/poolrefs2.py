#!/usr/bin/env python3
"""Locate users of embedded string-pool entries (file 0x5F000..0x62000).
Borland huge-model: far refs are (off,seg) as separate 16-bit immediates.
1) decode all code with capstone (16-bit); for every instruction carrying a
   16-bit immediate equal to a pool offset, check +/- 14 instructions for the
   matching segment immediate.
2) raw-scan far call/jmp (0x9A/0xEA) pairs for exact (off,seg)/(seg,off)."""
import re, bisect, struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_16, CS_OP_IMM

D = open('work/expanded/UW.EXE','rb').read()
md = Cs(CS_ARCH_X86, CS_MODE_16)

def segoff_of(F0):
    seg = 0x1000 + (((F0-0x3200) & ~0xF) >> 4)
    off = F0 - ((seg-0x1000)*16 + 0x3200)
    return seg, off

strs = []
for line in open('work/uw_strings.txt'):
    m = re.match(r'0x([0-9a-fA-F]{5,6})\s+(.*)', line)
    if not m: continue
    off = int(m.group(1),16)
    if 0x5F000 <= off < 0x62000:
        strs.append((off, m.group(2).strip()))
print(f"# {len(strs)} pool strings")

fns = []
for line in open('work/ghidra_export/functions.txt'):
    m = re.match(r'([0-9a-fA-F]{4,5}):([0-9a-fA-F]{4})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)', line)
    if m:
        fns.append([(int(m.group(1),16)-0x1000)*16 + int(m.group(2),16), m.group(4), m.group(1)+':'+m.group(2)])
    else:
        m = re.match(r'CODE_TAIL::([0-9a-fA-F]{4,6})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)', line)
        if m:
            fns.append([int(m.group(1),16), m.group(4), 'CODE_TAIL::'+m.group(1)])
fns.sort(key=lambda f: f[0])
fstarts = [f[0] for f in fns]
def raw(F0): return F0-0x3200 if F0 < 0x66B30 else F0
def enclosing(F0):
    i = bisect.bisect_right(fstarts, raw(F0)) - 1
    return (fns[i][1], fns[i][2]) if i >= 0 else (None, '?')

regions = [(0x3100, 0x66B30), (0x66B30, 0x89250)]
# per-region flat instruction lists: (addr, [imm values])
rlists = []
for rs, re_ in regions:
    lst = []
    a = rs
    while a < re_:
        c = min(0x4000, re_-a)
        for ins in md.disasm(D[a:a+c+16], a):
            if ins.address >= a+c: break  # crosses chunk boundary; re-decoded next
            imms = []
            for tok in re.findall(r'-?0x[0-9a-fA-F]+', ins.op_str):
                v = int(tok, 16)
                if 0 <= v < 0x10000:
                    imms.append(v)
            lst.append((ins.address, imms, ins.mnemonic))
        a += c
    rlists.append(lst)
print(f"# decoded {sum(len(l) for l in rlists)} instructions")

WIN = 14
# index every imm16 by value -> (region, k)
immidx = {}
for ri, lst in enumerate(rlists):
    for k, (a, imms, mn) in enumerate(lst):
        for v in imms:
            immidx.setdefault(v, []).append((ri, k))

out = []
for off, s in strs:
    seg, o = segoff_of(off)
    hits = []
    for ri, k in immidx.get(o, []):
        lst = rlists[ri]
        for j in range(max(0, k-WIN), min(len(lst), k+WIN+1)):
            if seg in lst[j][1]:
                a = lst[k][0]
                hits.append((a, f'imm pair off@{a:#x}+seg@{lst[j][0]:#x} (d={j-k})'))
                break
    # far call/jmp raw scan
    for pat, order in ((struct.pack('<HH', o, seg), 'off,seg'),
                       (struct.pack('<HH', seg, o), 'seg,off')):
        i = D.find(pat)
        while i != -1:
            if 0x3100 <= i < 0x89250 and not (0x5F000 <= i < 0x62000) and D[i-1] in (0x9A, 0xEA):
                hits.append((i, f'far 0x{D[i-1]:02X} ({order})'))
            i = D.find(pat, i+1)
    if hits:
        disp = s if len(s) < 44 else s[:41]+'...'
        out.append(f"0x{off:05X}  {disp!r}")
        seen = set()
        for h, kind in hits:
            fn, addr = enclosing(h)
            key = (h, fn)
            if key in seen: continue
            seen.add(key)
            out.append(f"    file {h:#07x} [{kind}]  in {fn} @ {addr}")
        out.append("")

print(f"# strings with refs: {sum(1 for l in out if l.startswith('0x'))}\n")
print("\n".join(out))
