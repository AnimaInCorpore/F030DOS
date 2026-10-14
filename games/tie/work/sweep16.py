#!/usr/bin/env python3
"""16-bit function sweep for DOS4G hybrid halves + pure 16-bit EXEs.

Usage: sweep16.py <file> <base_addr> <region_start> <region_end> [outdir prefix]
base_addr: linear address the region_start file offset loads at (for target math).
"""
import sys, bisect
from capstone import *

src, baddr, r0, r1 = sys.argv[1], int(sys.argv[2],16), int(sys.argv[3],16), int(sys.argv[4],16)
D = open(src,'rb').read()
assert r0 <= r1 <= len(D)
# base: file offset -> linear address
def addr(off): return baddr + (off - r0)
def off(ad):  return r0 + (ad - baddr)

cs = Cs(CS_ARCH_X86, CS_MODE_16)
cs.detail = True
MAXLEN = 4096
R_ESP = 28          # CS_REG_ESP numeric in capstone 5
JCC = {'jz','jnz','je','jne','jl','jg','jle','jge','ja','jb','jc','jnc','js','jns',
       'jo','jno','jp','jnp','loop','loopz','loopnz'}

def extract(a):
    o = off(a)
    if o < 0 or o + 4 > len(D): return None, 'oob', []
    bal, nins, skips, targs = 0, 0, 0, []
    for i in cs.disasm(D[o:o+MAXLEN], a, 0):
        b0 = i.bytes[0]
        op = i.mnemonic
        if op == 'db':
            skips += 1
            if skips >= 3: return None, 'invalid-bytes', targs
            continue
        skips = 0
        nins += 1
        o0 = i.operands[0] if i.operands else None
        if   b0 in (0x50,0x51,0x52,0x53,0x54,0x55,0x56,0x57): bal = None if bal is None else bal + 2
        elif b0 == 0x68: bal = None if bal is None else bal + 2          # push imm16
        elif b0 in (0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F): bal = None if bal is None else bal - 2
        elif b0 == 0x60: bal = None if bal is None else bal - 4          # push dword [reg]
        elif b0 == 0x61: bal = None if bal is None else bal - 4          # pop dword [reg]
        elif b0 == 0x62: bal = None if bal is None else bal - 2          # push word [reg]
        elif b0 == 0x63: bal = None if bal is None else bal - 4          # push dword [reg]
        elif b0 in (0x06,0x07,0x0E,0x16,0x17,0x1E,0x1F): bal = None if bal is None else bal + 2  # push seg
        elif b0 in (0x0F,0x15,0x1D,0x27,0x2F,0x37,0x3F): bal = None if bal is None else bal - 2  # pop seg
        elif b0 == 0x83 and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            adj = -i.operands[1].imm if op.startswith('sub') else i.operands[1].imm
            bal = None if bal is None else bal + adj                     # add/sub sp,imm8
        elif b0 == 0x81 and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            adj = -i.operands[1].imm if op.startswith('sub') else i.operands[1].imm
            bal = None if bal is None else bal + adj
        elif op in ('mov','xchg','lea') and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            bal = 0 if (op == 'mov' and i.operands[1].type == CS_OP_REG) else None
        if op in ('call','jmp') and i.operands:
            t = i.operands[0]
            if t.type == CS_OP_IMM and r0 <= off(t.imm) < r1: targs.append(t.imm)
            elif t.type == CS_OP_MEM:
                d = t.mem.base == 0 and t.mem.disp or None
                if d is not None and r0 <= off(d) < r1: targs.append(d)
        elif op in JCC and i.operands and i.operands[0].type == CS_OP_IMM:
            t = i.operands[0].imm
            if r0 <= off(t) < r1: targs.append(t)
        if b0 in (0xC3, 0xC2, 0xCB):                                  # ret / ret imm / retf
            if b0 == 0xC2 and len(i.bytes) >= 3:
                imm = int.from_bytes(i.bytes[1:3], 'little')
                ok = (bal is not None and bal == imm) or bal is None or (bal % 2 == 0)
            else:
                ok = (bal is None) or (bal % 2 == 0)
            if ok and nins >= 2: return i.address, nins, targs
            return None, 'ret-balance(%s)' % bal, targs
        if op == 'jmp' and bal == 0 and nins >= 3 and i.operands \
           and i.operands[0].type == CS_OP_IMM and i.operands[0].imm > i.address:
            return i.address, nins, targs                             # tail jmp
        if nins > MAXLEN // 2: break
    return None, 'no-epilogue', targs

def main():
    fns = {}
    def try_add(a):
        if a in fns: return
        end, info, targs = extract(a)
        if end is None: return
        st, en = a, end
        for k, (e2, _, _) in list(fns.items()):
            if st <= e2 and k <= en: return        # overlap: skip
        fns[st] = (en, info, [])
        for t in targs:
            try_add(t)
    trig = {0x55,0x53,0x56,0x57,0x50,0x51,0x52,0x54,0x8B,0x8D,0x89,0x9C,0x98,
            0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F}
    for f in range(r0, r1 - 12):
        if D[f] in trig:
            try_add(addr(f))
    # emit
    tot = 0
    out = open(sys.argv[5] if len(sys.argv) > 5 else 'sweep16_out.txt', 'w')
    for st in sorted(fns):
        en, info, _ = fns[st]
        tot += en - st + 1
        out.write('0x%06x  %7d  %s\n' % (st, en - st + 1, info))
    print('region 0x%06x..0x%06x: %d functions, %d bytes (%.1f%%)' %
          (r0, r1, len(fns), tot, 100.0 * tot / (r1 - r0)))

main()
