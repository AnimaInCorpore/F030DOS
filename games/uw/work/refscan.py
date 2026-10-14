#!/usr/bin/env python3
# Find which functions reference each known file-path string, via 32-bit far pointers.
import struct
D = open('work/expanded/UW.EXE','rb').read()
TAIL = 0x66B30
# runtime far-pointer segment uses runtime linear address:
#   main image: runtime lin = 0x10000 + file_off
#   tail:       runtime lin = 0x76B30 + (file_off - 0x66B30)  (presumed contiguous)
def runtime_lin(off):
    return 0x10000 + off if off < TAIL else 0x76B30 + (off - TAIL)

def farptrs(off):
    L = runtime_lin(off)
    o16, s16 = L & 0xFFFF, (L >> 4) & 0xFFFF
    return {
        'off:seg LE': struct.pack('<HH', o16, s16),
        'seg:off LE': struct.pack('<HH', s16, o16),
    }

def find_all(pat):
    out, j = [], 0
    while True:
        j = D.find(pat, j)
        if j < 0: break
        out.append(j); j += 1
    return out

names = [b'uw.cfg', b'weapons.dat', b'weapons.cm', b'strings.pak', b'lev.ark',
         b'cnv.ark', b'player.dat', b'font5x6i.sys', b'fontbig.sys',
         b'assoc.anm', b'sounds.dat', b'xfer.dat', b'terrain.dat',
         b'grave.dat', b'comobj.dat', b'babglobs.dat', b'uwedit.exe']
for n in names:
    i = D.find(n)
    if i < 0:
        print(n, 'NOT FOUND'); continue
    k = i
    while k > 0 and D[k-1] != 0:
        k -= 1
    hits = {}
    for lbl, p in farptrs(k).items():
        h = find_all(p)
        if h: hits[lbl] = h
    print(f'{n.decode():14s} file {k:#08x} (lin {runtime_lin(k):#08x}, seg {runtime_lin(k)>>4:#06x} off {k&0xffff:#06x})')
    for lbl, h in hits.items():
        print(f'    {lbl:10s} -> { [hex(x) for x in h][:12] }')
    if not hits:
        print('    no static far-ptr reference found')
