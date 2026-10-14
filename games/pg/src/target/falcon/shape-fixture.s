; N/A - target contract harness for the x86-translated clipped shape draw
; sub_00058AB4 (tools/x86x). Not game flow. Stages each DOS witness (clip record,
; bitmap descriptor, shape image, destination region before the call), calls the
; generated function through its shim and writes the region after the call and
; the returned EAX. Expected values come from DOS (tests/fixtures/dos-shape.*).
;
; Input record (big-endian longs): clipX0 clipY0 clipX1 clipY1 maxX maxY index x y
; regionX0 regionY0 regionX1 regionY1 headBytes regionBytes recordBytes function
; (0 = sub_00058AB4, 1 = sub_00058F9E) spriteOffset spriteBytes, then the image
; header and table (even-padded), the sprite bytes (even-padded), the region rows
; before the call (even-padded) and the 256-byte pixel table that sub_00058F9E
; reads at arena offset $6e48. The image is rebuilt in `image`: header at 0, the
; sprite at spriteOffset, everything else left from the previous case.
        include "shape-input.inc"
        section text,code
        xdef _main
_main:
        lea     stack_end,sp
        lea     fixtures,a5
        lea     results,a6
        move.w  #NUM_CASES-1,remaining
.next:
        ; bitmap descriptor { pixels, maxX, maxY, 0, 0 } and clip { desc, x0, y0, x1, y1 }, little-endian
        lea     desc,a3
        move.l  #bitmap,d0
        bsr     put_le32
        move.l  16(a5),d0
        bsr     put_le32
        move.l  20(a5),d0
        bsr     put_le32
        moveq   #0,d0
        bsr     put_le32
        bsr     put_le32
        lea     clip,a3
        move.l  #desc,d0
        bsr     put_le32
        move.l  (a5),d0
        bsr     put_le32
        move.l  4(a5),d0
        bsr     put_le32
        move.l  8(a5),d0
        bsr     put_le32
        move.l  12(a5),d0
        bsr     put_le32
        ; the shape image: header and table at 0, the sprite at its offset
        lea     76(a5),a3               ; image header bytes
        lea     image,a4
        movea.l a4,a1
        move.l  52(a5),d0               ; headBytes
        subq.l  #1,d0
.copy_head:
        move.b  (a3)+,(a1)+
        dbra    d0,.copy_head
        lea     76(a5),a3
        move.l  52(a5),d0
        addq.l  #1,d0
        bclr    #0,d0
        adda.l  d0,a3                   ; sprite bytes
        movea.l a4,a1
        adda.l  68(a5),a1               ; image + spriteOffset
        move.l  72(a5),d0               ; spriteBytes (< 65536)
        subq.l  #1,d0
.copy_sprite:
        move.b  (a3)+,(a1)+
        dbra    d0,.copy_sprite
        move.l  72(a5),d0               ; a3 is past the sprite; skip its pad byte
        btst    #0,d0
        beq     .sprite_even
        addq.l  #1,a3
.sprite_even:                           ; a3 = region rows before the call
        ; the region rows before the call -> bitmap
        bsr     region_setup
.copy_in:
        move.l  d4,d0                   ; row width - 1
.copy_in_row:
        move.b  (a3)+,(a1)+
        dbra    d0,.copy_in_row
        adda.l  d5,a1
        dbra    d3,.copy_in
        ; the pixel table follows the region rows (even-padded) -> arena + $6e48
        move.l  56(a5),d0               ; regionBytes: a3 is already past the rows (copy_in)
        btst    #0,d0
        beq     .table_even
        addq.l  #1,a3
.table_even:
        lea     arena,a0
        lea     $6e48(a0),a1
        move.w  #255,d0
.copy_table:
        move.b  (a3)+,(a1)+
        dbra    d0,.copy_table
        ; call: a0 = arena, a1 = clip, a2 = shape, d0 = index, d1 = x, d2 = y
        lea     arena,a0
        lea     clip,a1
        movea.l a4,a2
        move.l  24(a5),d0
        move.l  28(a5),d1
        move.l  32(a5),d2
        tst.l   64(a5)
        bne     .second
        bsr     sub_00058AB4
        bra     .called
.second:
        bsr     sub_00058F9E
.called:
        move.l  d0,d7                   ; EAX
        ; the region rows after the call -> results, then EAX little-endian
        bsr     region_setup
.copy_out:
        move.l  d4,d0
.copy_out_row:
        move.b  (a1)+,(a6)+
        dbra    d0,.copy_out_row
        adda.l  d5,a1
        dbra    d3,.copy_out
        move.l  d7,d0
        bsr     write_u32_le
        adda.l  60(a5),a5               ; recordBytes
        subq.w  #1,remaining
        bpl     .next
        ; write results
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

; region_setup: a1 = bitmap + regionY0 * (maxX+1) + regionX0; d4 = width-1; d3 = height-1;
; d5 = stride - width (advance between rows). Uses a5 header.
region_setup:
        move.l  16(a5),d5
        addq.l  #1,d5                   ; stride
        move.l  40(a5),d0               ; regionY0
        mulu.w  d5,d0
        add.l   36(a5),d0               ; + regionX0
        lea     bitmap,a1
        adda.l  d0,a1
        move.l  44(a5),d4
        sub.l   36(a5),d4               ; width - 1
        move.l  48(a5),d3
        sub.l   40(a5),d3               ; height - 1
        sub.l   d4,d5
        subq.l  #1,d5                   ; stride - width
        rts

; N/A - byte-order adapters, outside the contract body.
put_le32:
        move.b  d0,(a3)+
        lsr.l   #8,d0
        move.b  d0,(a3)+
        lsr.l   #8,d0
        move.b  d0,(a3)+
        lsr.l   #8,d0
        move.b  d0,(a3)+
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
        include "shape.s"

        section data,data
filename: dc.b "PGSHAPE.OUT",0
        even
fixtures: incbin "shape-input.bin"
        section bss,bss
        even
remaining: ds.w 1
handle: ds.w 1
result_size: ds.l 1
desc: ds.b 20
clip: ds.b 20
results: ds.b RESULT_LEN
arena: ds.b $7000
image: ds.b $40000
bitmap: ds.b 640*480
stack: ds.b 8192
stack_end:
