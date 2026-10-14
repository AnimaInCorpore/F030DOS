import sys,struct,capstone
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16)
d=open('/Users/saschaspringer/Work/F030Underworld2/work/extracted/D3/UW2.EXE','rb').read()
a=int(sys.argv[1],16); b=int(sys.argv[2],16)
seen={}
i=a
for ins in md.disasm(d[a:b],a):
    if ins.mnemonic=='lcall' and ','  in ins.op_str:
        seg,off=ins.op_str.split(',')
        try:
            s=int(seg,16); o=int(off,16)
        except: continue
        t=0x2E00+(s<<4)+o
        seen.setdefault(t,[]).append(ins.address)
for t in sorted(seen): print(hex(t), len(seen[t]), [hex(x) for x in seen[t][:4]])
