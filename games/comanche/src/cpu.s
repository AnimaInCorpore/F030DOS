; N/A - platform replacement: MC68060 arithmetic compatibility.
; Route: N/A - target compatibility harness.
; Record: analysis/functions/cpu-compatibility.md
; Motorola MC68060 UM appendix C: 32x32 -> 64 MULx is unimplemented.
; These helpers avoid requiring an installed integer emulation package.
        include "inc/cpu.s"
        text

        ifeq TARGET_CPU-68060
; The unsigned product a*b of d0 and d1, left in d3:d0 (high:low). Four
; 16x16 products: lo = a_lo*b_lo, hi = a_hi*b_hi, and the two middle terms
; summed with their carry out (bit 48) kept, then split across the halves.
; Clobbers d1/d2/d4; the callers below save and set registers around it.
        macro   MULU64_BODY
        move.l  d0,d2                         ; a
        move.l  d0,d3
        swap    d3                            ; a_hi
        move.l  d1,d4
        swap    d4                            ; b_hi
        mulu.w  d1,d0                         ; a_lo * b_lo
        mulu.w  d4,d2                         ; a_lo * b_hi
        mulu.w  d3,d1                         ; a_hi * b_lo
        mulu.w  d4,d3                         ; a_hi * b_hi
        add.l   d2,d1                         ; middle sum; X = its bit 32
        moveq   #0,d2                         ; MOVEQ preserves X
        addx.l  d2,d2                         ; that carry, worth 2^48
        swap    d2
        move.l  d1,d4
        clr.w   d4
        swap    d4                            ; middle >> 16
        add.l   d4,d2                         ; cannot carry: < 2^17 + 2^16
        swap    d1
        clr.w   d1                            ; middle << 16
        add.l   d1,d0                         ; low half; X = carry into high
        addx.l  d2,d3                         ; high half
        endm

; DOS: N/A - exact target arithmetic mechanism, not a game routine.
; Port: unsigned d0 * d1 -> d1:d0 with four unsigned 16-bit products.
; Preserved: all other registers and the full 64 product bits; CCR scratch.
; Kind: replaced.
; Status: validated by tools/check-cpu-compatibility.py.
cpu_mulu64
        movem.l d2-d4,-(sp)
        MULU64_BODY
        move.l  d3,d1
        movem.l (sp)+,d2-d4
        rts

; DOS: N/A - exact target arithmetic mechanism, not a game routine.
; Port: signed d0 * d1 -> d1:d0 via the unsigned product and sign corrections:
;   for each negative operand, subtract the other operand from the high half,
;   which is the two's-complement product modulo 2^64, INT_MIN included.
; Preserved: all other registers; no rounding, saturation or FPU; CCR scratch.
; Kind: replaced.
; Status: validated by tools/check-cpu-compatibility.py.
cpu_muls64
        movem.l d2-d6,-(sp)
        move.l  d0,d5                         ; a
        move.l  d1,d6                         ; b
        MULU64_BODY
        tst.l   d5
        bpl.s   .a_positive
        sub.l   d6,d3
.a_positive
        tst.l   d6
        bpl.s   .b_positive
        sub.l   d5,d3
.b_positive
        move.l  d3,d1
        movem.l (sp)+,d2-d6
        rts
        endc
        end
