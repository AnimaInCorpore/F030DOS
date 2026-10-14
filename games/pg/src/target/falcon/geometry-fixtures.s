; N/A - target contract harness, not game flow or a DOS game function.
; Stages oracle inputs, calls the ported bodies, writes canonical result bytes.
        include "geometry-input.inc"
        section text,code
        xdef _main
_main:
        lea     stack_end,sp
        lea     fixtures,a5
        lea     results,a6
        move.w  #NUM_FIXTURES-1,remaining
.next:
        cmpi.b  #1,(a5)
        bne     .viewport
        lea     state,a0
        movea.l a0,a3
        adda.l  #$ccb1,a3
        move.b  1(a5),(a3)
        movea.l a0,a3
        adda.l  #$cc88,a3
        move.b  2(a5),(a3)
        move.b  3(a5),1(a3)
        move.b  4(a5),-2(a3)
        move.b  5(a5),-1(a3)
        moveq   #0,d0
        move.b  1(a5),d0
        mulu.w  #24,d0
        lea     $21d6(a0),a3
        adda.l  d0,a3
        lea     8(a5),a4
        moveq   #23,d1
.copy_record:
        move.b  (a4)+,(a3)+
        dbra    d1,.copy_record
        lea     scratch+1,a1
        lea     scratch+3,a2
        tst.b   6(a5)
        beq     .separate
        movea.l a1,a2
.separate:
        move.b  32(a5),(a1)
        move.b  33(a5),1(a1)
        move.b  34(a5),(a2)
        move.b  35(a5),1(a2)
        bsr     sub_00010976
        move.b  (a1),(a6)+
        move.b  1(a1),(a6)+
        move.b  (a2),(a6)+
        move.b  1(a2),(a6)+
        bsr     write_u32_le
        bra     .advance
.viewport:
        lea     state,a0
        moveq   #0,d0
        move.b  1(a5),d0
        mulu.w  #20,d0
        movea.l a0,a3
        adda.l  #$c61c,a3
        adda.l  d0,a3
        movea.l a3,a4
        lea     20(a5),a1
        moveq   #19,d1
.copy_row:
        move.b  (a1)+,(a3)+
        dbra    d1,.copy_row
        lea     4(a5),a1
        bsr     read_u32_le
        move.l  d0,d6
        bsr     read_u32_le
        move.l  d0,d7
        bsr     read_u32_le
        move.l  d0,d2
        bsr     read_u32_le
        move.l  d0,d3
        lea     40(a5),a1
        bsr     read_u32_le
        move.l  d0,d4
        move.l  d6,d0
        move.l  d7,d1
        bsr     sub_00048105
        move.l  d0,d6
        move.l  d1,d7
        movea.l a4,a3
        moveq   #19,d0
.result_row:
        move.b  (a3)+,(a6)+
        dbra    d0,.result_row
        move.l  d6,d0
        bsr     write_u32_le
        move.l  d7,d0
        bsr     write_u32_le
.advance:
        adda.l  #64,a5
        subq.w  #1,remaining
        bpl     .next
        clr.w   -(sp)
        pea     filename
        move.w  #$3c,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .failed
        move.w  d0,handle
        move.l  a6,d0
        sub.l   #results,d0
        move.l  d0,result_size
        pea     results
        move.l  d0,-(sp)
        move.w  handle,-(sp)
        move.w  #$40,-(sp)
        trap    #1
        lea     12(sp),sp
        cmp.l   result_size,d0
        bne     .failed
        move.w  handle,-(sp)
        move.w  #$3e,-(sp)
        trap    #1
        addq.l  #4,sp
        clr.w   -(sp)
        move.w  #$4c,-(sp)
        trap    #1
.failed:
        move.w  #1,-(sp)
        move.w  #$4c,-(sp)
        trap    #1

; N/A - target fixture byte-order adapters, outside the game contract bodies.
read_u32_le:
        moveq   #0,d0
        move.b  3(a1),d0
        lsl.l   #8,d0
        move.b  2(a1),d0
        lsl.l   #8,d0
        move.b  1(a1),d0
        lsl.l   #8,d0
        move.b  (a1),d0
        addq.l  #4,a1
        rts
write_u32_le:
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        rts
        include "geometry.s"

        section data,data
filename: dc.b "PGGEOM.OUT",0
        even
fixtures: incbin "geometry-input.bin"
        section bss,bss
        even
remaining: ds.w 1
handle: ds.w 1
result_size: ds.l 1
scratch: ds.b 16
results: ds.b NUM_FIXTURES*28
state: ds.b $33240
stack: ds.b 8192
stack_end:
