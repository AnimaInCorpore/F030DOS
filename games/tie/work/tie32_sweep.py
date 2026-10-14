
from capstone import *
D = open('tie.exe','rb').read()
r0, r1 = 0x39EC, 0x7B30
cs = Cs(CS_ARCH_X86, CS_MODE_32); cs.detail = True
R_ESP = 30
JCC = {'jz','jnz','je','jne','jl','jg','jle','jge','ja','jb','jc','jnc','js','jns','jo','jno','jp','jnp','loop','loopz','loopnz'}
MAXLEN = 8192

def extract(a):
    bal, nins, skips, targs = 0, 0, 0, []
    for i in cs.disasm(D[a:r1], a, 0):
        b0 = i.bytes[0]; op = i.mnemonic
        if op == 'db':
            skips += 1
            if skips >= 3: return None, 'invalid-bytes', targs
            continue
        skips = 0; nins += 1
        o0 = i.operands[0] if i.operands else None
        if   b0 in (0x50,0x51,0x52,0x53,0x54,0x55,0x56,0x57): bal = None if bal is None else bal+4
        elif b0 in (0x68,0x6A): bal = None if bal is None else bal+4
        elif b0 in (0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F): bal = None if bal is None else bal-4
        elif b0 in (0x61,0x63): bal = None if bal is None else bal-4
        elif b0 in (0x60,0x62): bal = None if bal is None else bal-2
        elif b0 == 0xC7: bal = None if bal is None else bal-4
        elif b0 == 0x9C: bal = None if bal is None else bal+4
        elif b0 == 0x9D: bal = None if bal is None else bal-4
        elif b0 == 0x83 and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            adj = -i.operands[1].imm if op.startswith('sub') else i.operands[1].imm
            bal = None if bal is None else bal+adj
        elif b0 == 0x81 and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            adj = -i.operands[1].imm if op.startswith('sub') else i.operands[1].imm
            bal = None if bal is None else bal+adj
        elif op in ('mov','xchg','lea') and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            bal = 0 if (op == 'mov' and i.operands[1].type == CS_OP_REG) else None
        if op in ('call','jmp') and i.operands:
            t = i.operands[0]
            if t.type == CS_OP_IMM and r0 <= t.imm < r1: targs.append(t.imm)
        elif op in JCC and i.operands and i.operands[0].type == CS_OP_IMM:
            t = i.operands[0].imm
            if r0 <= t < r1: targs.append(t)
        if b0 in (0xC3,0xC2,0xCB):
            if b0 == 0xC2 and len(i.bytes) >= 3:
                imm = int.from_bytes(i.bytes[1:3],'little')
                ok = (bal is not None and bal == imm) or bal is None or (bal % 4 == 0)
            else:
                ok = (bal is None) or (bal % 4 == 0)
            if ok and nins >= 2: return i.address, nins, targs
            return None, 'ret-balance(%s)' % bal, targs
        if op == 'jmp' and bal == 0 and nins >= 3 and i.operands and i.operands[0].type == CS_OP_IMM and i.operands[0].imm > i.address:
            return i.address, nins, targs
        if nins > MAXLEN//2: break
    return None, 'no-epilogue', targs

fns = {}
def try_add(a):
    if a in fns: return
    res = extract(a)
    end, info = res[0], str(res[1])
    if end is None: return
    st, en = a, end
    for k, (e2, _, _) in list(fns.items()):
        if st <= e2 and k <= en: return
    fns[st] = (en, info, [])
    if len(res) == 3:
        for t in res[2]: try_add(t)
trig = {0x55,0x53,0x56,0x57,0x50,0x51,0x52,0x54,0x8B,0x8D,0x89,0x9C}
for f in range(r0, r1-12):
    if D[f] in trig: try_add(f)
tot = 0
with open('tie32.txt','w') as out:
    for st in sorted(fns):
        en, info, _ = fns[st]
        tot += en-st+1
        out.write('0x%06x  %7d  %s\n' % (st, en-st+1, info))
print('TIE.EXE 32-bit image: %d functions, %d/%d bytes (%.1f%%)' % (len(fns), tot, r1-r0, 100.0*tot/(r1-r0)))
