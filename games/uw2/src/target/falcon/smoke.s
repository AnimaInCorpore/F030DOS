; Headless TOS smoke harness for the Falcon RGB565 seam.
;
; This is a target execution fixture, not game logic.  It builds a varied
; 256-entry 6-bit palette, fills a complete 320x200 index surface, invokes the
; two target functions, and leaves the result in exported symbols for Hatari's
; debugger.  The host-side expected hashes live in
; analysis/functions/presentation-rgb565.md.

        include "inc/falcon.s"

        xdef    _main
        xdef    falcon_smoke_status
        xdef    falcon_smoke_lut
        xdef    falcon_smoke_pixels
        xdef    falcon_smoke_frame
        xref    uw2_falcon_build_rgb565_lut
        xref    uw2_falcon_present_rgb565

        text

_main
        lea     falcon_smoke_palette,a0
        lea     falcon_smoke_lut,a1
        bsr     uw2_falcon_build_rgb565_lut

        lea     falcon_smoke_pixels,a0
        moveq   #0,d0
        move.w  #FALCON_FRAME_PIXELS/16-1,d7
.fill_pixels
        rept    16
        move.b  d0,(a0)+
        addq.b  #1,d0
        endr
        dbra    d7,.fill_pixels

        lea     falcon_smoke_pixels,a0
        lea     falcon_smoke_frame,a1
        lea     falcon_smoke_lut,a2
        bsr     uw2_falcon_present_rgb565

        move.w  #$A55A,falcon_smoke_status
.wait
        bra     .wait

        data
        even

; Thirty-two repetitions of eight distinct triples exercise all channel
; rounding paths while keeping the fixture source compact and reviewable.
falcon_smoke_palette
        rept    32
        dc.b    0,0,0, 1,2,3, 7,13,19, 15,27,39
        dc.b    23,31,47, 31,45,55, 39,53,7, 63,63,63
        endr

        bss
        even
falcon_smoke_status   ds.w    1
        even
falcon_smoke_lut      ds.w    FALCON_LUT_ENTRIES
        even
falcon_smoke_pixels   ds.b    FALCON_FRAME_PIXELS
        even
falcon_smoke_frame    ds.b    FALCON_RGB565_BYTES

        end
