; N/A - target differential harness; does not initialize connected game state.
        include "rng-input.inc"
        section text,code
        xdef _main
_main:
        lea     stack_end,sp
        lea     inputs,a5
        lea     results,a6
        move.w  #NUM_CASES-1,d7
.case:
        lea     state,a0
        lea     $74f0(a0),a4
        move.b  4(a5),(a4)
        move.b  5(a5),1(a4)
        move.b  6(a5),2(a4)
        move.b  7(a5),3(a4)
        lea     8(a5),a1
        moveq   #0,d0
        move.b  3(a1),d0
        lsl.l   #8,d0
        move.b  2(a1),d0
        lsl.l   #8,d0
        move.b  1(a1),d0
        lsl.l   #8,d0
        move.b  (a1),d0
        cmpi.b  #2,(a5)
        beq     .random
        cmpi.b  #3,(a5)
        beq     .seed
        bsr     sub_00063375
        bra     .pointer
.seed:
        bsr     sub_0006339F
.pointer:
        cmpa.l  d0,a4
        bne     failed
        move.l  #$1e74f0,d0
        bra     .result
.random:
        bsr     sub_0006337B
.result:
        move.b  (a4),(a6)+
        move.b  1(a4),(a6)+
        move.b  2(a4),(a6)+
        move.b  3(a4),(a6)+
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        adda.l  #12,a5
        dbra    d7,.case
        clr.w   -(sp)
        pea     filename
        move.w  #$3c,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     failed
        move.w  d0,handle
        pea     results
        move.l  #NUM_CASES*8,-(sp)
        move.w  d0,-(sp)
        move.w  #$40,-(sp)
        trap    #1
        lea     12(sp),sp
        cmpi.l  #NUM_CASES*8,d0
        bne     failed
        move.w  handle,-(sp)
        move.w  #$3e,-(sp)
        trap    #1
        addq.l  #4,sp
        clr.w   -(sp)
        move.w  #$4c,-(sp)
        trap    #1
failed:
        move.w  #1,-(sp)
        move.w  #$4c,-(sp)
        trap    #1
        include "rng.s"
        section data,data
filename: dc.b "PGRNG.OUT",0
        even
inputs: incbin "rng-input.bin"
        section bss,bss
        even
handle: ds.w 1
results: ds.b NUM_CASES*8
state: ds.b $7500
stack: ds.b 8192
stack_end:
