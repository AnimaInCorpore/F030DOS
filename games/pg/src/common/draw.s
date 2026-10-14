; Clipped-rectangle copy between a bitmap and a 640x480 8-bit chunky screen.
; Contract: analysis/display-driver.md "Copy exports 6, 7, 11" (VESA480.DLL).
; This is a target-side equivalent of the DOS driver exports, not a DOS function:
; it implements only the DOS-measured domain (tests/fixtures/dos-draw.json) and
; refuses everything else with d0 = -1, never drawing: shadow-buffer descriptors,
; clipped or out-of-range rectangles, and stretched (unequal-span) copies are
; Unproven. The chunky screen is a memory model; the Videl display path is open.
; Restricted to 68000 instructions.
;
; In:  a0 = bitmap descriptor { pixels.l, maxX.l, maxY.l, unknown.l, shadow.l }
;      a1 = screen base (640 bytes per row, 480 rows)
;      a2 = rectangles, eight longs { bx0, by0, bx1, by1, sx0, sy0, sx1, sy1 }
;           (bitmap rectangle, then screen rectangle)
;      d0 = 0 copy bitmap -> screen (exports 6 and 11)
;           1 copy screen -> bitmap (export 7)
; Out: d0 = 0 copied, -1 refused. All other registers preserved.
        section text,code
        xdef gfx_copy_rect
gfx_copy_rect:
        movem.l d1-d7/a2-a6,-(sp)
        move.l  d0,d7                   ; direction
        tst.l   16(a0)
        bne     .refuse                 ; shadow-buffer copy is Unproven
        move.l  4(a0),d5                ; maxX
        move.l  8(a0),d6                ; maxY
        cmpi.l  #$7ffe,d5
        bhi     .refuse
        cmpi.l  #$7ffe,d6
        bhi     .refuse
        movem.l (a2),d0-d3              ; bx0 by0 bx1 by1
        tst.l   d0
        bmi     .refuse
        tst.l   d1
        bmi     .refuse
        cmp.l   d5,d2
        bgt     .refuse
        cmp.l   d6,d3
        bgt     .refuse
        cmp.l   d0,d2
        blt     .refuse
        cmp.l   d1,d3
        blt     .refuse
        move.l  16(a2),d4               ; sx0
        bmi     .refuse
        tst.l   20(a2)
        bmi     .refuse
        cmpi.l  #639,24(a2)
        bgt     .refuse
        cmpi.l  #479,28(a2)
        bgt     .refuse
        move.l  24(a2),d6               ; sx1
        sub.l   d4,d6                   ; sx1-sx0
        bmi     .refuse
        move.l  d2,d4
        sub.l   d0,d4                   ; bx1-bx0
        cmp.l   d4,d6
        bne     .refuse                 ; stretched copy is Unproven
        move.l  28(a2),d6
        sub.l   20(a2),d6               ; sy1-sy0
        bmi     .refuse
        move.l  d3,d4
        sub.l   d1,d4                   ; by1-by0
        cmp.l   d4,d6
        bne     .refuse
        move.l  d4,d6                   ; d6 = rows-1 for dbra (<= 479)
        move.l  d2,d4
        sub.l   d0,d4
        addq.l  #1,d4                   ; d4 = width
        addq.l  #1,d5                   ; d5 = bitmap stride
        move.l  d1,d2
        mulu.w  d5,d2                   ; by0 * stride (both < 65536)
        add.l   d0,d2
        movea.l (a0),a3
        adda.l  d2,a3                   ; a3 = first bitmap byte
        move.l  20(a2),d2
        mulu.w  #640,d2
        add.l   16(a2),d2
        movea.l a1,a4
        adda.l  d2,a4                   ; a4 = first screen byte
        tst.l   d7
        bne     .tobitmap
        move.l  d5,d1                   ; source = bitmap
        move.l  #640,d2
        bra     .rows
.tobitmap:
        exg     a3,a4                   ; source = screen
        move.l  #640,d1
        move.l  d5,d2
.rows:
        movea.l a3,a5
        movea.l a4,a6
        move.l  d4,d3                   ; bytes left in this row
        move.l  a5,d0
        move.l  a6,d5                   ; d5 (bitmap stride) is dead inside the row loop
        or.l    d5,d0
        btst    #0,d0
        bne     .bytes                  ; 68000: no unaligned word access
        move.l  d3,d0
        lsr.l   #1,d0
        beq     .bytes
        subq.w  #1,d0
.words:
        move.w  (a5)+,(a6)+
        dbra    d0,.words
        btst    #0,d3
        beq     .next
        move.b  (a5)+,(a6)+
        bra     .next
.bytes:
        subq.w  #1,d3
.byte:
        move.b  (a5)+,(a6)+
        dbra    d3,.byte
.next:
        adda.l  d1,a3
        adda.l  d2,a4
        dbra    d6,.rows
        moveq   #0,d0
        bra     .done
.refuse:
        moveq   #-1,d0
.done:
        movem.l (sp)+,d1-d7/a2-a6
        rts
