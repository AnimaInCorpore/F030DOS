import capstone, sys
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
d = open('/Users/saschaspringer/Work/F030Underworld2/work/extracted/D3/UW2.EXE','rb').read()
addr = int(sys.argv[1],16)
n = int(sys.argv[2],16) if len(sys.argv)>2 else 0x120
for i in md.disasm(d[addr:addr+n], addr):
    print("%06x  %-18s %s %s" % (i.address, i.bytes.hex(), i.mnemonic, i.op_str))
