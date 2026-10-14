        section text,code
        xdef sub_00037E75
; DOS sub_00037E75, vaddr $37e75..$382dc. Record: sub_00037E75.md.
; ABI a0=byte-addressed LE arena at DOS virtual base $1e0000.
; Preserves d1-d7/a0-a6, returns d0=DOS EAX (final outer counter).
; Selected contract: complete binary reads, valid allocated pointers and Poland
; tables, maxima below $ffff. No supported connected game claim.
; pg_open/pg_read/pg_close are explicit target binary-resource adapters.
; pg_read: d0=itemSize,d1=count,d2=handle,a0=destination; d0=items read.
; Adapters preserve all other registers and terminate fixture on I/O failure.
sub_00037E75:
        movem.l d1-d7/a0-a6,-(sp)
        movea.l a0,a6
        lea     -120(sp),sp
        movea.l sp,a5
        movea.l a6,a1
        adda.l  #$1d34c,a1
        movea.l a6,a0
        adda.l  #$1dd72,a0
        bsr     sub_00060907
        movea.l a6,a1
        adda.l  #$cc28,a1
        bsr     sub_00060926
        bsr     pg_open
        move.l  d0,100(a5)
        move.l  d0,d2
        lea     108(a5),a0
        moveq   #1,d0
        moveq   #1,d1
        bsr     pg_read
        movea.l a5,a0
        moveq   #4,d4
.fields:
        moveq   #20,d0
        moveq   #1,d1
        bsr     pg_read
        adda.l  #20,a0
        dbra    d4,.fields
        movea.l a6,a0
        adda.l  #$cc90,a0
        moveq   #2,d0
        moveq   #1,d1
        bsr     pg_read
        subq.l  #2,a0
        moveq   #2,d0
        bsr     pg_read
        movea.l a6,a0
        adda.l  #$cc28,a0
        lea     40(a5),a1
        bsr     sub_00060907
        moveq   #0,d4
.discard:
        movea.l a6,a0
        adda.l  #$21be,a0
        moveq   #0,d0
        move.b  (a0),d0
        cmp.l   d0,d4
        bge     .geometry
        lea     110(a5),a0
        moveq   #2,d0
        moveq   #1,d1
        bsr     pg_read
        addq.l  #1,d4
        bra     .discard
.geometry:
        movea.l a6,a0
        adda.l  #$ccb1,a0
        move.b  1(a0),(a0)
        movea.l a6,a0
        adda.l  #$cc90,a0
        bsr     pg_get16
        subq.l  #1,d0
        subq.l  #8,a0
        bsr     pg_put16
        subq.l  #2,a0
        movea.l a0,a1
        addq.l  #8,a0
        bsr     pg_get16
        movea.l a1,a0
        bsr     pg_put16
        movea.l a6,a0
        lea     112(a5),a1
        lea     114(a5),a2
        bsr     sub_00010976
        movea.l a1,a0
        bsr     pg_get16
        cmpi.l  #640,d0
        bls     .width
        move.l  #640,d0
.width:
        move.l  d0,d4
        movea.l a2,a0
        bsr     pg_get16
        cmpi.l  #426,d0
        bls     .height
        move.l  #426,d0
.height:
        move.l  d0,d5
        move.l  #554,d6
        sub.l   d4,d6
        asr.l   #1,d6
        move.l  #426,d7
        sub.l   d5,d7
        asr.l   #1,d7
        move.l  d4,d2
        add.l   d6,d2
        subq.l  #1,d2
        move.l  d5,d3
        add.l   d7,d3
        subq.l  #1,d3
        movea.l a6,a0
        adda.l  #$28ee8,a0
        moveq   #0,d4
        move.b  (a0),d4
        move.l  d6,d0
        move.l  d7,d1
        movea.l a6,a0
        bsr     sub_00048105
        movea.l a6,a0
        adda.l  #$ccb1,a0
        move.b  2(a0),(a0)
        movea.l a6,a0
        adda.l  #$cc90,a0
        bsr     pg_get16
        addq.l  #1,d0
        move.l  d0,d5
        subq.l  #2,a0
        bsr     pg_get16
        addq.l  #1,d0
        mulu.w  d0,d5
        moveq   #0,d4
.layers:
        movea.l a6,a0
        adda.l  #$21be,a0
        moveq   #0,d0
        move.b  (a0),d0
        cmp.l   d0,d4
        bge     .stm
        subq.l  #5,a0
        moveq   #0,d0
        move.b  (a0),d0
        mulu.w  #15,d0
        add.l   d4,d0
        movea.l a6,a0
        adda.l  #$ba94,a0
        adda.l  d0,a0
        moveq   #0,d6
        move.b  (a0),d6
        movea.l a6,a0
        adda.l  #$21c0,a0
        adda.l  d6,a0
        tst.b   (a0)
        bne     .next_layer
        movea.l a6,a0
        adda.l  #$cca1,a0
        adda.l  d6,a0
        moveq   #0,d7
        move.b  (a0),d7
        cmpi.b  #1,d7
        beq     .read_layer
        cmpi.b  #2,d7
        bne     .next_layer
.read_layer:
        move.l  d6,d0
        lsl.l   #2,d0
        movea.l a6,a0
        adda.l  #$cba0,a0
        adda.l  d0,a0
        bsr     pg_get32
        movea.l a6,a0
        adda.l  #$cb88,a0
        cmpi.b  #1,d7
        beq     .pointer_slot
        addq.l  #4,a0
.pointer_slot:
        bsr     pg_put32
        bsr     pg_virtual_pointer
        move.l  d7,d0
        move.l  d5,d1
        move.l  100(a5),d2
        bsr     pg_read
.next_layer:
        addq.l  #1,d4
        bra     .layers
.stm:
        movea.l a6,a0
        adda.l  #$cc28,a0
        lea     40(a5),a1
        bsr     sub_00060907
        movea.l a6,a0
        adda.l  #$1dd72,a0
        movea.l a6,a1
        adda.l  #$1d34c,a1
        bsr     sub_00060907
        movea.l a6,a1
        adda.l  #$cc2a,a1
        bsr     sub_00060926
        bsr     pg_open
        move.l  d0,104(a5)
        move.l  d0,d2
        movea.l a6,a0
        adda.l  #$cb84,a0
        bsr     pg_get32
        bsr     pg_virtual_pointer
        moveq   #2,d0
        move.l  d5,d1
        bsr     pg_read
        move.l  104(a5),d0
        bsr     pg_close
        movea.l a6,a0
        adda.l  #$17934,a0
        bsr     pg_get32
        bsr     pg_virtual_pointer
        movea.l a0,a4
        moveq   #2,d0
        move.l  d5,d1
        move.l  100(a5),d2
        bsr     pg_read
        move.l  100(a5),d0
        bsr     pg_close
        movea.l a6,a0
        adda.l  #$cc90,a0
        bsr     pg_get16
        move.l  d0,d6
        subq.l  #2,a0
        bsr     pg_get16
        move.l  d0,d7
        moveq   #0,d4
.column:
        cmp.l   d6,d4
        bhi     .done
        moveq   #0,d5
.row:
        cmp.l   d7,d5
        bhi     .next_column
        move.l  d6,d0
        addq.l  #1,d0
        andi.l  #$ffff,d0
        mulu.w  d5,d0
        add.l   d4,d0
        add.l   d0,d0
        movea.l a4,a0
        adda.l  d0,a0
        andi.b  #$7f,1(a0)
        addq.l  #1,d5
        bra     .row
.next_column:
        addq.l  #1,d4
        bra     .column
.done:
        move.l  d4,d0
        lea     120(sp),sp
        movem.l (sp)+,d1-d7/a0-a6
        rts

; N/A - byte-order and virtual-pointer representation adapters.
; No game decisions; accept odd addresses as the DOS byte arena does.
pg_get16:
        moveq   #0,d0
        move.b  1(a0),d0
        lsl.w   #8,d0
        move.b  (a0),d0
        rts
pg_put16:
        move.b  d0,(a0)
        ror.w   #8,d0
        move.b  d0,1(a0)
        ror.w   #8,d0
        rts
pg_get32:
        moveq   #0,d0
        move.b  3(a0),d0
        lsl.l   #8,d0
        move.b  2(a0),d0
        lsl.l   #8,d0
        move.b  1(a0),d0
        lsl.l   #8,d0
        move.b  (a0),d0
        rts
pg_put32:
        move.b  d0,(a0)
        ror.l   #8,d0
        move.b  d0,1(a0)
        ror.l   #8,d0
        move.b  d0,2(a0)
        ror.l   #8,d0
        move.b  d0,3(a0)
        ror.l   #8,d0
        rts
pg_virtual_pointer:
        subi.l  #$1e0000,d0
        movea.l a6,a0
        adda.l  d0,a0
        rts
