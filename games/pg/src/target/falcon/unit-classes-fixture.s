; N/A - isolated target fixture harness, not scenario loading/game boot.
        section text,code
        xdef _main
_main:
        lea     stack_end,sp
        lea     state,a0
        bsr     sub_0003AFF3
        lea     returned,a1
        move.b  d0,(a1)
        lsr.l   #8,d0
        move.b  d0,1(a1)
        lsr.l   #8,d0
        move.b  d0,2(a1)
        lsr.l   #8,d0
        move.b  d0,3(a1)
        clr.w   -(sp)
        pea     filename
        move.w  #$3c,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     failed
        move.w  d0,handle
        lea     spans,a3
        moveq   #2,d4
.span:
        lea     state,a0
        adda.l  (a3)+,a0
        move.l  (a3)+,d0
        bsr     write_output
        dbra    d4,.span
        lea     returned,a0
        moveq   #4,d0
        bsr     write_output
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
write_output:
        movem.l d1-d7/a0-a6,-(sp)
        move.l  d0,requested
        move.l  a0,-(sp)
        move.l  d0,-(sp)
        move.w  handle,-(sp)
        move.w  #$40,-(sp)
        trap    #1
        lea     12(sp),sp
        cmp.l   requested,d0
        bne     failed
        movem.l (sp)+,d1-d7/a0-a6
        rts
        include "unit-classes.s"
        include "rng.s"
        section data,data
filename: dc.b "PGUNIT.OUT",0
        even
spans: incbin "unit-spans.bin"
state: incbin "unit-input.bin"
        section bss,bss
        even
handle: ds.w 1
requested: ds.l 1
returned: ds.b 4
stack: ds.b 8192
stack_end:
