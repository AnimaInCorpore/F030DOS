; Target-neutral drawing on the indexed surface.
;
; Everything the port draws stays 8-bit indexed with the DOS palette index
; preserved verbatim. Only the target back end turns this surface into hardware
; pixels, which is what keeps the output comparable to a host render of the same
; source bytes on any target.
;
; 68000-clean: this file must assemble for a plain ST as well as a Falcon.

        include "inc/por.s"

        xdef    surface_clear
        xdef    blit_centred

        text

; Fill the indexed surface with one index.
;   a0 = indexed surface, d0.b = index
surface_clear
        movem.l d0-d1/a0,-(sp)
        and.l   #$ff,d0
        move.l  d0,d1
        lsl.l   #8,d1
        or.l    d1,d0                   ; index in both low bytes
        move.l  d0,d1
        swap    d1
        or.l    d1,d0                   ; ... and in all four
        move.w  #SURFACE_BYTES/16-1,d1
.loop
        rept    4
        move.l  d0,(a0)+
        endr
        dbra    d1,.loop
        movem.l (sp)+,d0-d1/a0
        rts

; Copy one image into the indexed surface, centred.
;
; *** NOT GROUNDED IN THE DOS ORIGINAL. ***
; The DOS blitter (GAME.OVR unit 18E, entry_19A5) takes an explicit position in
; 8-row and 1-byte units from its caller; it does not centre anything. Centring
; is a scaffold for the slice-1 title endpoint only. Replace it with the DOS
; positioning rule before any real screen is composed — see PORTING.md
; §Nothing without a source.
;
; Images larger than the surface are refused rather than clipped — a wrong-size
; asset is a bug in the converter, not something to paper over at runtime.
;   a0 = source pixels, a1 = indexed surface
;   d0.w = width, d1.w = height
;   returns d0.w = 0 on success, -1 if it does not fit
blit_centred
        movem.l d1-d5/a0-a2,-(sp)
        cmpi.w  #SURFACE_WIDTH,d0
        bhi     .too_big
        cmpi.w  #SURFACE_HEIGHT,d1
        bhi     .too_big

        move.w  d0,d2                   ; keep width
        move.w  #SURFACE_WIDTH,d3
        sub.w   d0,d3
        lsr.w   #1,d3                   ; x offset
        move.w  #SURFACE_HEIGHT,d4
        sub.w   d1,d4
        lsr.w   #1,d4                   ; y offset

        move.l  a1,a2
        mulu.w  #SURFACE_STRIDE,d4
        add.l   d4,a2
        ext.l   d3
        add.l   d3,a2

        move.w  #SURFACE_STRIDE,d5
        sub.w   d2,d5                   ; destination row advance
        subq.w  #1,d1                   ; height - 1 for dbra
.row
        move.w  d2,d0
        subq.w  #1,d0
.pixel
        move.b  (a0)+,(a2)+
        dbra    d0,.pixel
        add.w   d5,a2
        dbra    d1,.row

        moveq   #0,d0
        bra     .done
.too_big
        moveq   #-1,d0
.done
        movem.l (sp)+,d1-d5/a0-a2
        rts


        end
