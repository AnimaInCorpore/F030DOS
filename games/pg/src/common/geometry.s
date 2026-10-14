        section text,code
        xdef sub_00010976
        xdef sub_00048105

; DOS: sub_00010976, vaddr $10976..$10a18, file $58c1a..$58cbc.
; Record: analysis/functions/sub_00010976.md. Same DOS fixtures as JavaScript.
; ABI: a0 = LE object-2 arena, a1/a2 = width/height output word pointers.
; Returns d0 = full unsigned height (DOS EAX). Preserves all other registers.
; Writes low word, width then height; accepts odd and aliased output pointers.
sub_00010976:
        movem.l d1-d4/a3-a4,-(sp)
        movea.l a0,a3
        adda.l  #$ccb1,a3
        moveq   #0,d2
        move.b  (a3),d2
        mulu.w  #24,d2
        lea     $21d6(a0),a4
        adda.l  d2,a4
        movea.l a0,a3
        adda.l  #$cc86,a3
        moveq   #0,d3
        move.b  3(a3),d3
        lsl.w   #8,d3
        move.b  2(a3),d3
        moveq   #0,d0
        move.b  2(a4),d0
        addq.l  #1,d0
        mulu.w  d0,d3
        moveq   #0,d4
        move.b  (a4),d4
        add.l   d4,d3
        moveq   #0,d0
        move.b  1(a3),d0
        lsl.w   #8,d0
        move.b  (a3),d0
        moveq   #0,d4
        move.b  11(a4),d4
        addq.l  #1,d4
        mulu.w  d4,d0
        moveq   #0,d4
        move.b  7(a4),d4
        addq.l  #1,d4
        add.l   d4,d0
        move.b  d3,(a1)
        lsr.w   #8,d3
        move.b  d3,1(a1)
        move.b  d0,(a2)
        move.l  d0,d4
        lsr.w   #8,d4
        move.b  d4,1(a2)
        movem.l (sp)+,d1-d4/a3-a4
        rts

; DOS: sub_00048105, vaddr $48105..$48174, file $903a9..$90418.
; Record: analysis/functions/sub_00048105.md. Same DOS fixtures as JavaScript.
; ABI: a0 = word-aligned LE object-2 arena (DOS base is also aligned);
; d0,d1,d2,d3 = DOS EAX,EDX,EBX,ECX bounds;
; d4 = stack index value. Returns d0=index.low_byte*20, d1=d3.low_word.
; Preserves d2-d7/a0-a6. Ordinary RTS replaces DOS ret 4 stack convention.
; Selected row's four preceding bytes remain untouched. No game clamps.
sub_00048105:
        movem.l d4-d6/a3,-(sp)
        andi.l  #$ff,d4
        mulu.w  #20,d4
        movea.l a0,a3
        adda.l  #$c620,a3
        adda.l  d4,a3
        move.l  d0,d5
        ror.w   #8,d5
        move.w  d5,(a3)+
        clr.w   (a3)+
        move.l  d1,d5
        ror.w   #8,d5
        move.w  d5,(a3)+
        clr.w   (a3)+
        move.l  d2,d5
        ror.w   #8,d5
        move.w  d5,(a3)+
        clr.w   (a3)+
        move.l  d3,d5
        ror.w   #8,d5
        move.w  d5,(a3)+
        clr.w   (a3)+
        move.l  d4,d0
        move.l  d3,d1
        andi.l  #$ffff,d1
        movem.l (sp)+,d4-d6/a3
        rts
