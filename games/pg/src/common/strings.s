        section text,code
        xdef sub_00060907
        xdef sub_00060926
; DOS sub_00060907, vaddr $60907..$60926. Record: sub_00060907.md.
; ABI a0=destination, a1=source; d0=original destination, a1=advanced source.
; Restores a0, preserves other registers. Pairwise byte order matches DOS.
sub_00060907:
        move.l  d1,-(sp)
        move.l  a0,d0
.pair:
        move.b  (a1),d1
        move.b  d1,(a0)
        beq     .done
        move.b  1(a1),d1
        addq.l  #2,a1
        move.b  d1,1(a0)
        addq.l  #2,a0
        tst.b   d1
        bne     .pair
.done:
        movea.l d0,a0
        move.l  (sp)+,d1
        rts
; DOS sub_00060926, vaddr $60926..$6095d. Record: sub_00060926.md.
; ABI a0=destination, a1=source; returns d0=destination. Preserves a0/a1.
sub_00060926:
        movem.l a0-a1,-(sp)
.end:
        tst.b   (a0)+
        bne     .end
        subq.l  #1,a0
        bsr     sub_00060907
        movem.l (sp)+,a0-a1
        move.l  a0,d0
        rts
