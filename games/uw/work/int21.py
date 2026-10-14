#!/usr/bin/env python3
"""Find all INT 0x21 call sites; classify AH; map each to nearest ghidra function."""
import re, bisect
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
D=open('work/expanded/UW.EXE','rb').read()
md=Cs(CS_ARCH_X86,CS_MODE_16)

# load function table
fns=[]
for line in open('work/ghidra_export/functions.txt'):
    m=re.match(r'([0-9a-f]{4}):([0-9a-f]{4})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)',line)
    if m:
        a=int(m.group(1),16)*16+int(m.group(2),16)
        fns.append([a,a+int(m.group(3)),m.group(4),m.group(1)+':'+m.group(2),'loader'])
    else:
        m=re.match(r'CODE_TAIL::([0-9a-f]{4,6})\s+size=(\d+)\s+inrefs=(\d+)\s+(\S+)',line)
        if m:
            a=int(m.group(1),16)
            fns.append([a,a+int(m.group(2)),m.group(3),m.group(1),'tail'])
fns.sort()
starts=[f[0] for f in fns]

def ghidra_addr(fileoff):
    return fileoff+0xE000 if fileoff<0x66B30 else fileoff  # tail ghidra addr == fileoff

DOSAH={0x01:'READ_STDIN',0x02:'WRITE_STDOUT',0x0A:'RAW_INPUT',0x0B:'KB_STATUS',
0x0C:'CRLF_OUT',0x0E:'TEXT_OUT',0x19:'VER',0x20:'TICK',0x21:'TICKC',
0x25:'SETINT',0x26:'GETINT',0x2A:'DATE',0x2C:'SETTIME',0x30:'SETDRIVE',
0x31:'CURDRIVE',0x33:'FARCALL',0x36:'GETDIR',0x37:'SETDIR',0x38:'SETALARM',
0x3A:'TIMEDATE',0x3C:'FOPEN',0x3D:'FCLOSE',0x3E:'FOPEN',0x3F:'FIO',
0x40:'FCLOSE',0x41:'FINDNEXT',0x42:'FSEEK',0x43:'FSTAT',0x44:'FCTRL',
0x46:'FMOVE',0x47:'FINDFIRST',0x48:'FALLOC',0x49:'FFREE',0x4A:'MEMAVAIL',
0x4B:'EXEC',0x4C:'EXIT',0x4D:'ENV',0x4E:'EXIT2',0x4F:'SBRK',0x50:'ALLOCMEM',
0x51:'FREEMEM',0x52:'SETBRK',0x53:'CBREAK',0x54:'NOCBREAK',0x56:'COPYFILE',
0x57:'RENAME',0x58:'SETBRK2',0x59:'FREE',0x5A:'ALLOC',0x5B:'NEWALLOC',
0x5C:'FREE2',0x5D:'RELOC',0x5E:'DELETE',0x5F:'MKDIR'}

# scan the whole image in chunks; find int 0x21; look back for MOV AH/AL imm
CH=0x4000
seen=set()
for base in range(0x1000,0x89250,CH):
    end=min(base+CH,0x89250)
    dis=list(md.disasm(D[base:end],base))
    for i,ins in enumerate(dis):
        if ins.mnemonic=='int' and re.match(r'0x21',ins.op_str):
            if ins.address in seen: continue
            seen.add(ins.address)
            ah=None
            for j in range(i-1,max(i-15,-1),-1):
                mm=re.match(r'mov\s+(ah|al),\s*0x([0-9a-f]{1,2})',dis[j].mnemonic+' '+dis[j].op_str)
                if mm:
                    ah=int(mm.group(2),16); break
            fo=ins.address  # file offset (we disassembled at base=fo)
            ga=ghidra_addr(fo)
            idx=bisect.bisect_right(starts,ga)-1
            fn='?'
            if idx>=0 and ga<fns[idx][1]:
                fn=fns[idx][3]+' '+fns[idx][2]
            name=DOSAH.get(ah,'AH?')
            ahs='0x%02x'%ah if ah is not None else '??'
            print(f'file {fo:08x}  AH={ahs} {name:10s}  in {fn}')
