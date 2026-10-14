; Indexed-surface drawing and the RGB565 presentation step.
;
; Everything the port draws stays 8-bit indexed with the DOS palette index
; preserved verbatim; only target_present touches display words. That keeps
; the Falcon output comparable to a host render of the same source bytes.

        include "inc/falcon.s"

        xdef    target_build_lut
        xdef    target_present
        xdef    palette_lut

        text

; Expand the bank's RGB565 palette into a 256-entry word lookup so the
; presentation inner loop needs no masking. Entries 16..255 mirror index & 15,
; matching the 4 bpp source data.
;   a0 = bank base
target_build_lut
        movem.l d0-d2/a0-a2,-(sp)
        lea     PORI_OFF_PALETTE(a0),a1
        lea     palette_lut,a2
        moveq   #0,d0                   ; destination index
.outer
        move.l  a1,a0                   ; restart at palette entry 0
        moveq   #PORI_PALETTE_COUNT-1,d1
.inner
        move.w  (a0)+,(a2)+
        dbra    d1,.inner
        add.w   #PORI_PALETTE_COUNT,d0
        cmpi.w  #LUT_ENTRIES,d0
        blo     .outer
        movem.l (sp)+,d0-d2/a0-a2
        rts

; Expand the whole indexed surface into a hidden RGB565 page.
;   a0 = indexed source (SURFACE_BYTES)
;   a1 = RGB565 destination page
target_present
        movem.l d0/d7/a0-a2,-(sp)
        lea     palette_lut,a2
        moveq   #0,d0
        move.w  #SURFACE_BYTES/8-1,d7
.loop
        rept    8
        move.b  (a0)+,d0
        add.w   d0,d0
        move.w  (a2,d0.w),(a1)+
        endr
        dbra    d7,.loop
        movem.l (sp)+,d0/d7/a0-a2
        rts

        bss
        even
palette_lut     ds.w    LUT_ENTRIES

        end
