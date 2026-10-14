; N/A - platform replacement: MC68060 arithmetic compatibility.
; Route: N/A - target compatibility harness.
; Record: analysis/functions/cpu-compatibility.md
; Motorola MC68060 UM appendix C: 32x32 -> 64 MULx is unimplemented.
; These helpers avoid requiring an installed integer emulation package.
        include "inc/cpu.s"
        text

        ifeq TARGET_CPU-68060
; DOS: N/A - exact target arithmetic mechanism, not a game routine.
; Port: unsigned d0 * d1 -> d1:d0 with four unsigned 16-bit products.
; Preserved: all other registers and the full 64 product bits; CCR scratch.
; Kind: replaced.
; Status: validated by tools/check-cpu-compatibility.py.
cpu_mulu64
        movem.l d2-d6,-(sp)
        move.l  d0,d2
        mulu.w  d1,d2                         ; a_lo * b_lo
        move.l  d0,d3
        swap    d3
        mulu.w  d1,d3                         ; a_hi * b_lo
        move.l  d1,d4
        swap    d4
        move.l  d4,d5
        mulu.w  d0,d4                         ; a_lo * b_hi
        move.l  d0,d6
        swap    d6
        mulu.w  d6,d5                         ; a_hi * b_hi

        move.l  d2,d0
        move.l  d3,d6
        swap    d6
        andi.l  #$ffff,d6
        add.l   d6,d5
        swap    d3
        clr.w   d3
        add.l   d3,d0
        moveq   #0,d6                         ; MOVEQ preserves X
        addx.l  d6,d5                         ; carry out of the low half
        move.l  d4,d6
        swap    d6
        andi.l  #$ffff,d6
        add.l   d6,d5
        swap    d4
        clr.w   d4
        add.l   d4,d0
        moveq   #0,d6
        addx.l  d6,d5
        move.l  d5,d1
        movem.l (sp)+,d2-d6
        rts

; DOS: N/A - exact target arithmetic mechanism, not a game routine.
; Port: signed d0 * d1 -> d1:d0 via unsigned product and sign corrections.
; Preserved: all other registers; no rounding, saturation or FPU; CCR scratch.
; Kind: replaced.
; Status: validated by tools/check-cpu-compatibility.py.
cpu_muls64
        movem.l d2-d3,-(sp)
        move.l  d0,d2
        move.l  d1,d3
        bsr     cpu_mulu64
        tst.l   d2
        bpl     .a_positive
        sub.l   d3,d1
.a_positive
        tst.l   d3
        bpl     .b_positive
        sub.l   d2,d1
.b_positive
        movem.l (sp)+,d2-d3
        rts
        endc
        end
