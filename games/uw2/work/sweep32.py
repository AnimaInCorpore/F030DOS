#!/usr/bin/env python3
"""P1.2 — full 32-bit image function sweep for Z_TIE__.EXE (DOS4GOLX hybrid).

Image: file 0x3F000..0xFBD46 (0xBCD47 B), runtime linear base 0x7E000.
All output addresses = file offsets (rizin base 0x3F000 convention).
runtime = 0x7E000 + (file_off - 0x3F000)

Method: anchor-driven extraction to fixpoint + step-1 orphan prologue scan.
A function = linear disasm ending at ret/ret-imm with tracked stack balance
(<=0 or unknown after mov-esp). E8/E9 near targets + absolute [disp] targets
enqueue new candidates. v1 anchors from functable.txt included.
"""
import sys, bisect
from capstone import *

BASE, RBASE = 0x3F000, 0x7E000
IMG = open(sys.argv[1] if len(sys.argv) > 1 else r'C:\Arbeit\F030TieFighter\work\z_tie_32.raw','rb').read()
IMG_SIZE = len(IMG)
END = BASE + IMG_SIZE
assert IMG_SIZE == 0xBCD47, hex(IMG_SIZE)

# strings.txt: rizin `iz` with broken section init — vaddr column is a constant
# garbage (0x3efff); paddr = image-relative offset (verified: paddr 0xA981A =
# file 0xE881A = actual "You must run TIE.EXE" location). file = 0x3F000 + paddr.
regions = []
for line in open(r'C:\Arbeit\F030TieFighter\analysis\32bit\strings.txt', encoding='latin1'):
    p = line.split()
    if len(p) >= 4 and p[1].startswith('0x'):
        off, ln = int(p[1],16), int(p[3])
        # rizin also flags push-opcode runs (53 51 52 56 57 55 = "SQRVWU") as
        # 6-byte strings; those are code. Real strings here are longer.
        if 0 <= off < IMG_SIZE and ln >= 12:
            regions.append((off, off + ln))
regions.sort()
starts_ = [a for a,_ in regions]
def in_str(off_rel):
    i = bisect.bisect_right(starts_, off_rel) - 1
    return i >= 0 and starts_[i] <= off_rel < regions[i][1]

anchors = {0x3F002:'entry', 0xAAE83:'crt-main'}
for line in open(r'C:\Arbeit\F030TieFighter\analysis\32bit\functable.txt', encoding='latin1'):
    if line.startswith('0x'):
        try: anchors.setdefault(int(line.split()[0],16),'v1')
        except: pass

cs = Cs(CS_ARCH_X86, CS_MODE_32)
cs.detail = True
MAXLEN = 8192
R_ESP = 30
JCC = {'jz','jnz','je','jne','jl','jg','jle','jge','ja','jb','jc','jnc','js','jns',
       'jo','jno','jp','jnp','loop','loopz','loopnz'}

def extract(start):
    """Return (end_file, reason, targets). end_file is None on failure."""
    if in_str(start - BASE): return None, 'string', []
    rel = start - BASE
    bal, nins, skips, targs = 0, 0, 0, []
    for i in cs.disasm(IMG[rel:rel+MAXLEN], start, 0):
        b0 = i.bytes[0]                     # int
        op = i.mnemonic
        if op == 'db':                      # invalid byte
            skips += 1
            if skips >= 3: return None, 'invalid-bytes', targs
            continue
        skips = 0
        nins += 1
        o0 = i.operands[0] if i.operands else None
        if   b0 in (0x50,0x51,0x52,0x53,0x54,0x55,0x56,0x57): bal = None if bal is None else bal + 4
        elif b0 == 0x68: bal = None if bal is None else bal + 4          # push imm32
        elif b0 == 0x6A: bal = None if bal is None else bal + 4          # push imm8
        elif b0 in (0x58,0x59,0x5A,0x5B,0x5C,0x5D,0x5E,0x5F): bal = None if bal is None else bal - 4
        elif b0 in (0x61,0x63): bal = None if bal is None else bal - 4   # pop/push dword [reg]
        elif b0 in (0x60,0x62): bal = None if bal is None else bal - 2   # push word [reg]
        elif b0 == 0x66 and i.bytes[1:2] in (b'\x50',b'\x51',b'\x52',b'\x53',b'\x54',b'\x55',b'\x56',b'\x57'):
            bal = None if bal is None else bal + 2                       # 66 push word reg
        elif b0 == 0x66 and i.bytes[1:2] in (b'\x58',b'\x59',b'\x5A',b'\x5B',b'\x5C',b'\x5D',b'\x5E',b'\x5F'):
            bal = None if bal is None else bal - 2                       # 66 pop word reg
        elif b0 == 0xC7: bal = None if bal is None else bal - 4          # leave
        elif b0 == 0x9C: bal = None if bal is None else bal + 4          # pushfd
        elif b0 == 0x9D: bal = None if bal is None else bal - 4          # popfd
        elif b0 == 0x83 and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            adj = -i.operands[1].imm if op.startswith('sub') else i.operands[1].imm
            bal = None if bal is None else bal + adj                     # add/sub esp,imm8
        elif b0 == 0x81 and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            adj = -i.operands[1].imm if op.startswith('sub') else i.operands[1].imm
            bal = None if bal is None else bal + adj                     # add/sub esp,imm32
        elif op in ('mov','xchg','lea') and o0 is not None and o0.type == CS_OP_REG and o0.reg == R_ESP:
            bal = 0 if (op == 'mov' and i.operands[1].type == CS_OP_REG) else None
        # targets (capstone resolves near rel against base=start)
        if op in ('call','jmp') and i.operands:
            o = i.operands[0]
            if o.type == CS_OP_IMM:
                if BASE <= o.imm < END: targs.append(o.imm)
            elif o.type == CS_OP_MEM:
                d = o.mem.disp
                if RBASE <= d < RBASE + IMG_SIZE: targs.append(BASE + d - RBASE)
        elif op in JCC and i.operands and i.operands[0].type == CS_OP_IMM:
            t = i.operands[0].imm
            if BASE <= t < END: targs.append(t)
        if b0 in (0xC3, 0xC2, 0xCB):                                 # ret / ret imm / retf
            if b0 == 0xC2 and len(i.bytes) >= 3:                     # ret imm16: pops args too
                imm = int.from_bytes(i.bytes[1:3], 'little', signed=False)
                ok = (bal is None) or (bal == imm) or (bal % 4 == 0)
            else:
                ok = (bal is None) or (bal % 4 == 0)                # clean stack (± multiples of 4;
                                                                    # positive = early-return locals)
            if ok and nins >= 2:
                return i.address, nins, targs
            return None, 'ret-balance(%s)' % bal, targs
        if op == 'jmp' and bal == 0 and nins >= 3 and i.operands \
           and i.operands[0].type == CS_OP_IMM and i.operands[0].imm > i.address:
            return i.address, nins, targs                            # tail-jmp block end
        if nins > MAXLEN // 2: break
    return None, 'no-epilogue', targs

def main():
    fns = {}
    queue, seen = list(anchors), set()
    while queue:
        s = queue.pop()
        if s in seen or s in fns: continue
        seen.add(s)
        if not (BASE <= s < END): continue
        end, info, targs = extract(s)
        if end is None: continue
        if any(st <= end and st > s or (st <= s and en >= s) for st,(en,_,_) in fns.items()):
            continue
        fns[s] = (end, info, anchors.get(s,'xref'))
        for t in targs:
            if t not in seen: queue.append(t)
    # orphan scan (step 1)
    covered = bytearray(IMG_SIZE)
    for st,(en,_,_) in fns.items():
        covered[st-BASE:en-BASE+1] = b'\x01'*(en-st+1)
    orphans = 0
    f = BASE
    while f < END - 12:
        i = f - BASE
        if not covered[i] and not in_str(i) and IMG[i] in (0x55,0x53,0x56,0x57,0x50,0x51,0x52,0x54,0x8B,0x8D,0x89,0x9C):
            end, info, targs = extract(f)
            if end is not None:
                if not any(f <= en and st <= end for st,(en,_,_) in fns.items()):
                    fns[f] = (end, info, 'orphan')
                    covered[f-BASE:end-BASE+1] = b'\x01'*(end-f+1)
                    orphans += 1
                    for t in targs:
                        if t not in seen:
                            seen.add(t); queue.append(t)
        f += 1
    spans = sorted((st, en) for st,(en,_,_) in fns.items())
    merged, tot = [], 0
    for st, en in spans:
        if merged and st <= merged[-1][1] + 1:
            if en > merged[-1][1]: merged[-1] = (merged[-1][0], en)
        else:
            merged.append([st, en])
    tot = sum(b-a+1 for a,b in merged)
    with open(r'C:\Arbeit\F030TieFighter\analysis\32bit\functable_v2.txt','w') as out:
        for st in sorted(fns):
            en, why, origin = fns[st]
            out.write('0x%06x  %7d  %-12s %s\n' % (st, en-st+1, origin, why))
    print('functions: %d (orphans %d), union covered: %d/%d (%.1f%%), merged spans: %d' %
          (len(fns), orphans, tot, IMG_SIZE, 100.0*tot/IMG_SIZE, len(merged)))
    v1 = set()
    for line in open(r'C:\Arbeit\F030TieFighter\analysis\32bit\functable.txt', encoding='latin1'):
        if line.startswith('0x'):
            try: v1.add(int(line.split()[0],16))
            except: pass
    fset = set(fns)
    print('v1=%d  v1&v2=%d  v2-only=%d  v1-only=%d' %
          (len(v1), len(v1 & fset), len(fset - v1), len(v1 - fset)))
    miss = sorted(v1 - fset)
    if miss:
        inside = 0
        ss = sorted(fset)
        for a in miss:
            j = bisect.bisect_right(ss, a) - 1
            if j >= 0 and a < fns[ss[j]][0] + 1: inside += 1
        print('v1-only starts: %d, of which inside a v2 function: %d' % (len(miss), inside))

main()
