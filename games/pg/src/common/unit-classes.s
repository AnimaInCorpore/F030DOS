        section text,code
        xdef sub_0003AFF3
; DOS sub_0003AFF3, vaddr $3aff3..$3b291. Record: sub_0003AFF3.md.
; a0=LE object-2 arena; d0=1 (DOS EAX); all other registers preserved.
; Uses the same PRNG state and conditional call order as DOS.
sub_0003AFF3:
        movem.l d1-d7/a0-a6,-(sp)
        movea.l a0,a6
        moveq   #0,d4
.side:
        moveq   #0,d6
        moveq   #0,d7
        moveq   #0,d5
.slot:
        move.l  d5,d0
        mulu.w  #98,d0
        move.l  d4,d1
        mulu.w  #49,d1
        add.l   d1,d0
        movea.l a6,a3
        adda.l  #$11c54,a3
        adda.l  d0,a3
        movea.l a6,a4
        adda.l  #$10694,a4
        move.l  d5,d0
        add.l   d0,d0
        add.l   d4,d0
        adda.l  d0,a4
        move.b  #$ff,(a4)
        tst.b   $1f(a3)
        beq     .next
        addq.l  #1,d6
        moveq   #0,d0
        move.b  $28(a3),d0
        add.l   d0,d7
        moveq   #0,d0
        move.b  $16(a3),d0
        lsl.w   #8,d0
        move.b  $15(a3),d0
        mulu.w  #50,d0
        movea.l a6,a1
        adda.l  #$179c4,a1
        adda.l  d0,a1
        moveq   #0,d1
        move.b  (a1),d1
        cmpi.b  #7,d1
        beq     .seven
        cmpi.b  #11,d1
        bhs     .next
        movea.l a6,a1
        adda.l  #$28eed,a1
        moveq   #0,d3
        move.b  (a1),d3
        move.l  d3,d0
        add.l   d0,d0
        add.l   d4,d0
        movea.l a6,a1
        adda.l  #$2c13,a1
        adda.l  d0,a1
        moveq   #0,d2
        move.b  (a1),d2
        movea.l a6,a0
        bsr     sub_0006337B
        andi.l  #$ff,d0
        mulu.w  #100,d0
        lsr.l   #8,d0
        cmp.l   d2,d0
        blt     .seven
        tst.l   d4
        beq     .normal
        movea.l a6,a1
        adda.l  #$2b84,a1
        cmpi.b  #41,(a1)
        bhi     .special
        movea.l a6,a0
        bsr     sub_0006337B
        btst    #0,d0
        beq     .special
        cmpi.b  #6,d3
        beq     .special
        cmpi.b  #38,d3
        beq     .special
        cmpi.b  #8,d1
        bhs     .one
.special:
        cmpi.b  #30,d3
        bne     .normal
        cmpi.b  #3,d1
        beq     .one
.normal:
        move.b  d1,(a4)
        bra     .next
.one:
        move.b  #1,(a4)
        bra     .next
.seven:
        move.b  #7,(a4)
.next:
        addq.l  #1,d5
        cmpi.l  #200,d5
        blo     .slot
        moveq   #0,d0
        tst.w   d6
        beq     .average
        move.l  d6,d0
        lsr.l   #1,d0
        add.l   d7,d0
        andi.l  #$ffff,d0
        divu.w  d6,d0
        andi.l  #$ffff,d0
.average:
        movea.l a6,a1
        adda.l  #$1dd92,a1
        move.l  d4,d2
        add.l   d2,d2
        adda.l  d2,a1
        move.b  d0,(a1)
        lsr.w   #8,d0
        move.b  d0,1(a1)
        addq.l  #1,d4
        cmpi.l  #2,d4
        blo     .side
        moveq   #1,d0
        movem.l (sp)+,d1-d7/a0-a6
        rts
