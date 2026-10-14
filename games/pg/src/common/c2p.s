; Chunky 8-bit to Falcon Videl 8-bit interleaved bitplane conversion.
; Layout (measured in the host check, tools/check-native-frame.py): each group of
; 16 pixels becomes 8 big-endian words, plane 0 (pixel bit 0) first; within a
; word the leftmost pixel is bit 15. Rows are contiguous: 640 pixels = 40 groups
; = 640 bytes of video memory per row, so a 640 x 480 frame is 307,200 bytes.
; Straightforward shift/extend code (about 2.5 s for a frame at 16 MHz); a
; faster conversion is future work and must keep this routine's output.
; Restricted to 68000 instructions.
;
; In:  a0 = chunky source, a1 = planar destination, d0.l = groups of 16 pixels
;      (19200 for 640 x 480; must be 1..65536)
; Out: all registers preserved.
        section text,code
        xdef gfx_c2p_groups
gfx_c2p_groups:
        movem.l d0-d7/a0-a2,-(sp)
        subq.l  #1,d0
        move.w  d0,d7
.group:
        moveq   #0,d1
        moveq   #0,d2
        moveq   #0,d3
        moveq   #0,d4
        movea.l a0,a2
        moveq   #15,d6
.low:
        move.b  (a2)+,d0
        lsr.b   #1,d0
        roxl.w  #1,d1
        lsr.b   #1,d0
        roxl.w  #1,d2
        lsr.b   #1,d0
        roxl.w  #1,d3
        lsr.b   #1,d0
        roxl.w  #1,d4
        dbra    d6,.low
        move.w  d1,(a1)+
        move.w  d2,(a1)+
        move.w  d3,(a1)+
        move.w  d4,(a1)+
        moveq   #0,d1
        moveq   #0,d2
        moveq   #0,d3
        moveq   #0,d4
        movea.l a0,a2
        moveq   #15,d6
.high:
        move.b  (a2)+,d0
        lsr.b   #4,d0
        lsr.b   #1,d0
        roxl.w  #1,d1
        lsr.b   #1,d0
        roxl.w  #1,d2
        lsr.b   #1,d0
        roxl.w  #1,d3
        lsr.b   #1,d0
        roxl.w  #1,d4
        dbra    d6,.high
        move.w  d1,(a1)+
        move.w  d2,(a1)+
        move.w  d3,(a1)+
        move.w  d4,(a1)+
        lea     16(a0),a0
        dbra    d7,.group
        movem.l (sp)+,d0-d7/a0-a2
        rts
