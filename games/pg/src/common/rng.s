        section text,code
        xdef sub_00063375
        xdef sub_0006337B
        xdef sub_0006339F
; DOS sub_00063375, vaddr $63375..$6337b. Record: sub_00063375.md.
; a0 = LE object-2 arena; d0 = native seed pointer. Other registers preserved.
sub_00063375:
        move.l  a0,d0
        addi.l  #$74f0,d0
        rts
; DOS sub_0006337B, vaddr $6337b..$6339f. Record: sub_0006337B.md.
; a0 = arena; d0 = 15-bit result. All other registers preserved.
; Three unsigned 16-bit partial products retain modulo-2^32 multiply on 68000.
sub_0006337B:
        movem.l d1-d2/a1,-(sp)
        bsr     sub_00063375
        movea.l d0,a1
        moveq   #0,d0
        move.b  3(a1),d0
        lsl.l   #8,d0
        move.b  2(a1),d0
        lsl.l   #8,d0
        move.b  1(a1),d0
        lsl.l   #8,d0
        move.b  (a1),d0
        move.l  d0,d1
        mulu.w  #$4e6d,d1
        move.l  d0,d2
        swap    d2
        mulu.w  #$4e6d,d2
        mulu.w  #$41c6,d0
        add.l   d2,d0
        swap    d0
        clr.w   d0
        add.l   d1,d0
        addi.l  #$3039,d0
        move.b  d0,(a1)
        ror.l   #8,d0
        move.b  d0,1(a1)
        ror.l   #8,d0
        move.b  d0,2(a1)
        ror.l   #8,d0
        move.b  d0,3(a1)
        ror.l   #8,d0
        swap    d0
        andi.l  #$7fff,d0
        movem.l (sp)+,d1-d2/a1
        rts
; DOS sub_0006339F, vaddr $6339f..$633af. Record: sub_0006339F.md.
; a0=arena, d0=seed argument; returns native seed pointer, preserves others.
sub_0006339F:
        movem.l d1/a1,-(sp)
        move.l  d0,d1
        bsr     sub_00063375
        movea.l d0,a1
        move.b  d1,(a1)
        ror.l   #8,d1
        move.b  d1,1(a1)
        ror.l   #8,d1
        move.b  d1,2(a1)
        ror.l   #8,d1
        move.b  d1,3(a1)
        movem.l (sp)+,d1/a1
        rts
