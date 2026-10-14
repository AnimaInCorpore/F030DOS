; N/A - target differential harness; does not draw to the Videl or run the game.
; Input records (big-endian longs), 52-byte header then payload padded to even:
;   mode, maxX, maxY, bx0 by0 bx1 by1, sx0 sy0 sx1 sy1, payloadLen, outLen
; mode 0: payload = bitmap-rectangle rows, output = screen-rectangle rows
; mode 1: payload = screen-rectangle rows, output = the whole bitmap
        include "draw-input.inc"
        section text,code
        xdef _main
_main:
        lea     stack_end,sp
        lea     inputs,a5
        lea     results,a6
        move.w  #NUM_CASES-1,d7
.case:
        lea     desc,a3
        lea     bitmap,a0
        move.l  a0,(a3)
        move.l  4(a5),4(a3)
        move.l  8(a5),8(a3)
        clr.l   12(a3)
        clr.l   16(a3)
        lea     52(a5),a1               ; payload
        tst.l   (a5)
        bne     .placescreen
        move.l  4(a5),d1
        addq.l  #1,d1                   ; bitmap stride
        move.l  16(a5),d0
        mulu.w  d1,d0
        add.l   12(a5),d0
        lea     bitmap,a0
        adda.l  d0,a0
        move.l  20(a5),d2
        sub.l   12(a5),d2
        addq.l  #1,d2                   ; width
        move.l  24(a5),d3
        sub.l   16(a5),d3               ; height-1
        bra     .doplace
.placescreen:
        move.l  #640,d1
        move.l  32(a5),d0
        mulu.w  d1,d0
        add.l   28(a5),d0
        lea     screen,a0
        adda.l  d0,a0
        move.l  36(a5),d2
        sub.l   28(a5),d2
        addq.l  #1,d2
        move.l  40(a5),d3
        sub.l   32(a5),d3
.doplace:
        move.l  d2,d4                   ; payload rows are packed
        bsr     place
        lea     desc,a0
        lea     screen,a1
        lea     12(a5),a2
        move.l  (a5),d0
        bsr     gfx_copy_rect
        tst.l   d0
        bne     failed
        tst.l   (a5)
        bne     .outbitmap
        move.l  32(a5),d0
        mulu.w  #640,d0
        add.l   28(a5),d0
        lea     screen,a1
        adda.l  d0,a1
        movea.l a6,a0
        move.l  36(a5),d2
        sub.l   28(a5),d2
        addq.l  #1,d2
        move.l  d2,d1                   ; output rows are packed
        move.l  #640,d4
        move.l  40(a5),d3
        sub.l   32(a5),d3
        bsr     place
        bra     .advance
.outbitmap:
        lea     bitmap,a1
        movea.l a6,a0
        move.l  48(a5),d2
        move.l  d2,d1
        move.l  d2,d4
        moveq   #0,d3
        bsr     place
.advance:
        adda.l  48(a5),a6
        move.l  44(a5),d0
        addq.l  #1,d0
        bclr    #0,d0
        lea     52(a5),a5
        adda.l  d0,a5
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
        move.l  #RESULT_LEN,-(sp)
        move.w  d0,-(sp)
        move.w  #$40,-(sp)
        trap    #1
        lea     12(sp),sp
        cmpi.l  #RESULT_LEN,d0
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
; Harness-only row mover (independent of gfx_copy_rect).
; a0 destination, d1 its stride, a1 source, d4 its stride, d2 width (>=1), d3 rows-1.
place:
        movea.l a0,a2
        move.l  d2,d0
.pb:
        move.b  (a1)+,(a2)+
        subq.l  #1,d0
        bne     .pb
        suba.l  d2,a1
        adda.l  d4,a1
        adda.l  d1,a0
        dbra    d3,place
        rts
        include "draw.s"
        section data,data
filename: dc.b "PGDRAW.OUT",0
        even
inputs: incbin "draw-input.bin"
        section bss,bss
        even
handle: ds.w 1
desc: ds.l 5
results: ds.b RESULT_LEN
screen: ds.b 640*480
bitmap: ds.b 640*480
stack: ds.b 8192
stack_end:
