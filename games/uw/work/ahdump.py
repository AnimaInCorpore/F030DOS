#!/usr/bin/env python3
"""For a list of Ghidra seg:off functions, dump the INT 0x21 AH codes used."""
import re
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
D=open('work/expanded/UW.EXE','rb').read()
md=Cs(CS_ARCH_X86,CS_MODE_16)
def fileoff(seg,off):
    a=int(seg,16)*16+int(off,16)
    return a-0xE000  # loader: ghidra linear = file + 0xE000
DOS={0x00:0,0x01:1,0x02:2,0x03:3,0x04:4,0x0A:10,0x0B:11,0x0C:12,0x0E:14,0x19:25,
     0x20:32,0x21:33,0x25:37,0x26:38,0x2A:42,0x2C:44,0x30:48,0x31:49,0x33:51,
     0x36:54,0x37:55,0x38:56,0x3A:58,0x3C:60,0x3D:61,0x3E:62,0x3F:63,0x40:64,
     0x41:65,0x42:66,0x43:67,0x44:68,0x45:69,0x46:70,0x47:71,0x48:72,0x49:73,
     0x4A:74,0x4B:75,0x4C:76,0x4D:77,0x4E:78,0x4F:79,0x50:80,0x51:81,0x52:82,
     0x53:83,0x54:84,0x56:86,0x57:87,0x58:88,0x59:89,0x5A:90,0x5B:91,0x5C:92,
     0x5D:93,0x5E:94,0x5F:95,0x60:96,0x61:97,0x62:98,0x67:103}
targets=[l.split() for l in open('work/wraplist.txt')]
for seg,off in targets:
    fo=fileoff(seg,off)
    # find function size from functions.txt
    sz=64
    m=re.match(rf'{re.escape(seg)}:{re.escape(off)}\s+size=(\d+)',
               open('work/ghidra_export/functions.txt').read())
    if m: sz=int(m.group(1))
    b=D[fo:fo+sz]
    dis=list(md.disasm(b,fo))
    ahs=[]
    for i,ins in enumerate(dis):
        if ins.mnemonic=='int' and ins.op_str.startswith('0x21'):
            ah=None
            for j in range(i-1,max(i-12,-1),-1):
                mm=re.match(r'mov\s+(ah|al),\s*0x([0-9a-f]{1,2})',dis[j].mnemonic+' '+dis[j].op_str)
                if mm:
                    ah=int(mm.group(2),16); break
            ahs.append(ah)
    print(f'{seg}:{off}  AH={["0x%02x"%a if a is not None else "?" for a in ahs]}')
