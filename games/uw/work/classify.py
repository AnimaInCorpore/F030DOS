#!/usr/bin/env python3
"""Classify UW.EXE functions by DOS API usage (INT 0x21 AH, INT 0x10/16/1A, etc.)"""
import re, struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_16

D = open('work/expanded/UW.EXE','rb').read()

# parse functions.txt: "seg:off size=N inrefs=N name" and "CODE_TAIL::xxxx size=N inrefs=N name"
fns = []
for line in open('work/ghidra_export/functions.txt'):
    m = re.match(r'([0-9a-f]{4}):([0-9a-f]{4})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)', line)
    if m:
        addr = int(m.group(1),16)*16 + int(m.group(2),16)
        fns.append(dict(addr=addr, size=int(m.group(3)), inrefs=int(m.group(4)),
                        name=m.group(5), space='loader', fileoff=addr-0xE000))
        continue
    m = re.match(r'CODE_TAIL::([0-9a-f]{4,6})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)', line)
    if m:
        addr = int(m.group(1),16)          # tail ghidra addr == file offset
        fns.append(dict(addr=addr, size=int(m.group(2)), inrefs=int(m.group(3)),
                        name=m.group(4), space='tail', fileoff=addr))
fns.sort(key=lambda f: (f['space']!='loader', f['addr']))
print(f'{len(fns)} functions', file=sys.stderr)

def bytes_of(f):
    o, n = f['fileoff'], f['size']
    return D[o:o+n]

md = Cs(CS_ARCH_X86, CS_MODE_16)

report = []
for f in fns:
    b = bytes_of(f)
    ints = {}
    ah = {}
    call_far = 0
    dis = list(md.disasm(b, f['fileoff']))
    for i, ins in enumerate(dis):
        op = ins.op_str
        if ins.mnemonic == 'int':
            ints[op] = ints.get(op,0)+1
            if op.startswith('0x21'):
                ahv = None
                for j in range(i-1, max(i-10,-1), -1):
                    m2 = re.match(r'mov\s+(ah|al),\s*0x([0-9a-f]+)', dis[j].mnemonic+' '+dis[j].op_str)
                    if m2:
                        ahv = int(m2.group(2),16)
                        break
                ah[ahv] = ah.get(ahv,0)+1
        elif ins.mnemonic in ('call','jmp') and op.startswith('0x') and ':' in op:
            call_far += 1
    f['ints'] = ints
    f['ah'] = {k:v for k,v in ah.items()}
    f['call_far'] = call_far
    if ints or (f['inrefs']==0 and f['size']>500):
        report.append(f)

print(f'{len(report)} functions with int calls or big+unreferenced', file=sys.stderr)
for f in report:
    if f['ints']:
        print(f"{f['name']:28s} {f['space']:6s} @file {f['fileoff']:08x} size={f['size']:5d} "
              f"inrefs={f['inrefs']:2d} ints={f['ints']} ah={f['ah']}")
