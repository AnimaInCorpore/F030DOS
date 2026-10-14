; Runtime macros for code emitted by tools/x86x/translate.py (x86-32 -> 68000).
; Restricted to 68000 instructions. Conventions (see analysis/x86-translation.md):
;   eax d0, ecx d1, edx d2, ebx d3, esi d4, edi d5, ebp a6; esp is a7.
;   d6, d7 and a1 are scratch and are clobbered (the movs macros borrow a2 and
;   restore it). a0 is the object-2 arena base.
;   x86 memory, the stack included, is little-endian and may be unaligned, so
;   every 32-bit access is four byte accesses and every 16-bit access two.

; LD32LE disp, areg, dreg: dreg = little-endian dword at disp(areg)
LD32LE  macro
        moveq   #0,\3
        move.b  \1+3(\2),\3
        lsl.l   #8,\3
        move.b  \1+2(\2),\3
        lsl.l   #8,\3
        move.b  \1+1(\2),\3
        lsl.l   #8,\3
        move.b  \1(\2),\3
        endm

; ST32LE dreg, disp, areg: little-endian dword at disp(areg) = dreg (dreg preserved)
ST32LE  macro
        move.b  \1,\2(\3)
        ror.l   #8,\1
        move.b  \1,\2+1(\3)
        ror.l   #8,\1
        move.b  \1,\2+2(\3)
        ror.l   #8,\1
        move.b  \1,\2+3(\3)
        ror.l   #8,\1
        endm

; LD16LE disp, areg, dreg: low word of dreg = little-endian word at disp(areg); upper word kept
LD16LE  macro
        move.b  \1+1(\2),\3
        lsl.w   #8,\3
        move.b  \1(\2),\3
        endm

; ST16LE dreg, disp, areg: little-endian word at disp(areg) = low word of dreg (dreg preserved)
ST16LE  macro
        move.b  \1,\2(\3)
        ror.w   #8,\1
        move.b  \1,\2+1(\3)
        ror.w   #8,\1
        endm

; PUSH32 dreg / POP32 dreg: x86 push/pop of a 32-bit register. Stack slots are
; little-endian bytes like all other x86 memory, so `[esp+n]`/`[ebp+n]` operands
; and the argument a `ret n` pops read them with LD32LE/LD16LE.
PUSH32  macro
        subq.l  #4,sp
        ST32LE  \1,0,sp
        endm
POP32   macro
        LD32LE  0,sp,\1
        addq.l  #4,sp
        endm

; IMUL32R sreg, dreg: dreg = dreg * sreg modulo 2^32 (low 32 bits of the signed product
; equal those of the unsigned one). Clobbers d6, d7.
IMUL32R macro
        move.l  \1,d6
        swap    d6
        mulu.w  \2,d6                   ; hi(s) * lo(d)
        move.l  \2,d7
        swap    d7
        mulu.w  \1,d7                   ; hi(d) * lo(s)
        add.l   d7,d6
        swap    d6
        clr.w   d6                      ; cross terms << 16
        mulu.w  \1,\2                   ; lo(d) * lo(s)
        add.l   d6,\2
        endm

; UMUL64: d2:d0 = d0 * d6, unsigned 32 x 32 -> 64 (x86 `mul r/m32`: edx:eax). Four
; 16 x 16 partial products; the stack holds one across the others. Clobbers d6, d7.
; Flags afterwards are not x86's (CF/OF of mul are never read by a rule).
UMUL64  macro
        move.l  d0,d7
        mulu.w  d6,d7                   ; p0 = a.lo * b.lo
        move.l  d7,-(sp)
        move.l  d0,d7
        swap    d7
        mulu.w  d6,d7                   ; p1 = a.hi * b.lo
        move.l  d6,d2
        swap    d2
        mulu.w  d0,d2                   ; p2 = a.lo * b.hi
        swap    d0
        swap    d6
        mulu.w  d6,d0                   ; p3 = a.hi * b.hi (d0)
        add.l   d7,d2                   ; mid = p1 + p2, carry in X
        moveq   #0,d7
        addx.l  d7,d7                   ; d7 = carry of mid
        swap    d7
        add.l   d7,d0                   ; hi += carry << 16
        move.l  d2,d7
        clr.w   d7
        swap    d7
        add.l   d7,d0                   ; hi += mid >> 16
        move.l  d2,d7
        swap    d7
        clr.w   d7                      ; mid << 16
        move.l  d0,d2                   ; d2 = hi
        move.l  (sp)+,d0                ; d0 = p0
        add.l   d7,d0                   ; lo = p0 + (mid << 16), carry in X
        moveq   #0,d7
        addx.l  d7,d7
        add.l   d7,d2                   ; hi += carry
        endm

; SMUL64: d2:d0 = d0 * d6, signed 32 x 32 -> 64 (x86 one-operand `imul r/m32`):
; the unsigned product minus (b << 32) if a < 0 and minus (a << 32) if b < 0.
SMUL64  macro
        move.l  d0,-(sp)                ; a
        move.l  d6,-(sp)                ; b
        UMUL64
        move.l  (sp)+,d7                ; b
        tst.l   (sp)                    ; a < 0 ?
        bpl     .pa\@
        sub.l   d7,d2
.pa\@:
        tst.l   d7                      ; b < 0 ?
        bpl     .pb\@
        sub.l   (sp),d2
.pb\@:
        addq.l  #4,sp
        endm

; IMUL32 clo, chi, dreg: dreg = dreg * (chi<<16 | clo) modulo 2^32 (unsigned partial
; products give the same low 32 bits as a signed 32-bit multiply). Clobbers d6, d7.
IMUL32  macro
        move.l  \3,d6
        mulu.w  #\1,d6                  ; x.lo * c.lo
        move.l  \3,d7
        swap    d7
        mulu.w  #\1,d7                  ; x.hi * c.lo
        mulu.w  #\2,\3                  ; x.lo * c.hi
        add.l   d7,\3
        swap    \3
        clr.w   \3
        add.l   d6,\3
        endm

; MOVSB / MOVSD: one x86 `movsb`/`movsd` with the direction flag clear: copy 1 or 4
; bytes from [esi] (d4) to [edi] (d5) and advance both. A dword is copied as four
; bytes in address order, which differs from DOS only when the destination starts
; inside the source dword (ledger: Unproven). Borrows a2 across the copy. Flags
; afterwards are not x86's.
MOVSB   macro
        move.l  a2,-(sp)
        movea.l d4,a1
        movea.l d5,a2
        move.b  (a1)+,(a2)+
        move.l  a1,d4
        move.l  a2,d5
        movea.l (sp)+,a2
        endm
MOVSD   macro
        move.l  a2,-(sp)
        movea.l d4,a1
        movea.l d5,a2
        move.b  (a1)+,(a2)+
        move.b  (a1)+,(a2)+
        move.b  (a1)+,(a2)+
        move.b  (a1)+,(a2)+
        move.l  a1,d4
        move.l  a2,d5
        movea.l (sp)+,a2
        endm

MOVSW   macro
        move.l  a2,-(sp)
        movea.l d4,a1
        movea.l d5,a2
        move.b  (a1)+,(a2)+
        move.b  (a1)+,(a2)+
        move.l  a1,d4
        move.l  a2,d5
        movea.l (sp)+,a2
        endm

; REP_MOVSB / REP_MOVSW / REP_MOVSD: `rep movs*`: ecx (d1) items, ecx ends at 0.
REP_MOVSW macro
        move.l  a2,-(sp)
        movea.l d4,a1
        movea.l d5,a2
.rep\@:
        tst.l   d1
        beq     .end\@
        subq.l  #1,d1
        move.b  (a1)+,(a2)+
        move.b  (a1)+,(a2)+
        bra     .rep\@
.end\@:
        move.l  a1,d4
        move.l  a2,d5
        movea.l (sp)+,a2
        endm
REP_MOVSB macro
        move.l  a2,-(sp)
        movea.l d4,a1
        movea.l d5,a2
.rep\@:
        tst.l   d1
        beq     .end\@
        subq.l  #1,d1
        move.b  (a1)+,(a2)+
        bra     .rep\@
.end\@:
        move.l  a1,d4
        move.l  a2,d5
        movea.l (sp)+,a2
        endm
REP_MOVSD macro
        move.l  a2,-(sp)
        movea.l d4,a1
        movea.l d5,a2
.rep\@:
        tst.l   d1
        beq     .end\@
        subq.l  #1,d1
        move.b  (a1)+,(a2)+
        move.b  (a1)+,(a2)+
        move.b  (a1)+,(a2)+
        move.b  (a1)+,(a2)+
        bra     .rep\@
.end\@:
        move.l  a1,d4
        move.l  a2,d5
        movea.l (sp)+,a2
        endm

; STOSB / STOSD / REP_STOSB / REP_STOSD: x86 `stos*` with the direction flag clear:
; store al (d0) or eax (d0, little-endian bytes) at [edi] (d5), advance edi; the rep
; forms repeat ecx (d1) times and leave ecx = 0. Flags afterwards are not x86's.
STOSB   macro
        movea.l d5,a1
        move.b  d0,(a1)+
        move.l  a1,d5
        endm
STOSD   macro
        movea.l d5,a1
        ST32LE  d0,0,a1
        addq.l  #4,d5
        endm
REP_STOSB macro
        movea.l d5,a1
.rep\@:
        tst.l   d1
        beq     .end\@
        subq.l  #1,d1
        move.b  d0,(a1)+
        bra     .rep\@
.end\@:
        move.l  a1,d5
        endm
REP_STOSD macro
        movea.l d5,a1
.rep\@:
        tst.l   d1
        beq     .end\@
        subq.l  #1,d1
        ST32LE  d0,0,a1
        addq.l  #4,a1
        bra     .rep\@
.end\@:
        move.l  a1,d5
        endm

; REPNE_SCASB: x86 `repne scasb al, es:[edi]` in the flat model, al = d0, ecx = d1,
; edi = d5. Stops after the first byte equal to al (edi points past it) or when ecx
; reaches 0. Flags afterwards are undefined: the translator never lets a jump read them.
; Clobbers a1.
REPNE_SCASB macro
        movea.l d5,a1
.rep\@:
        tst.l   d1
        beq     .end\@
        subq.l  #1,d1
        cmp.b   (a1)+,d0
        bne     .rep\@
.end\@:
        move.l  a1,d5
        endm
