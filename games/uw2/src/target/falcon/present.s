; Falcon RGB565 presentation seam.
;
; Target: MC68030, assembled by vasm 1.7b / M68k backend 2.0d with -m68030,
; Motorola syntax, Atari TOS flat addresses and the normal register ABI used
; by this project.  The source uses only instructions legal on MC68000 too;
; the target restriction is still applied and recorded by the build.
;
; DOS: N/A - platform replacement for the DOS indexed framebuffer's VGA/DAC
; presentation.  Record: uw2_indexed_to_rgb565 in
; analysis/functions/presentation-rgb565.md.

        include "inc/falcon.s"

        xdef    uw2_falcon_build_rgb565_lut
        xdef    uw2_falcon_present_rgb565

        text

; DOS: N/A - target artefact; record: uw2_indexed_to_rgb565.
; Build a 256-entry big-endian RGB565 lookup from source-form PALS.DAT bytes.
;
; Inputs:
;   a0 = 768-byte palette6, RGB triples, each component 0..63
;   a1 = 512-byte word-aligned destination LUT
; Outputs:
;   LUT[i] = round(R*31/63)<<11 | round(G*63/63)<<5 | round(B*31/63)
; Clobbers: condition codes only; d0-d4/a0-a1 are preserved.
uw2_falcon_build_rgb565_lut
        movem.l d0-d4/a0-a1,-(sp)
        move.w  #FALCON_LUT_ENTRIES-1,d0
.palette_loop
        moveq   #0,d1
        move.b  (a0)+,d1
        mulu.w  #31,d1
        add.w   #31,d1
        divu.w  #63,d1
        lsl.w   #8,d1
        lsl.w   #3,d1
        move.w  d1,d4

        moveq   #0,d2
        move.b  (a0)+,d2
        mulu.w  #63,d2
        add.w   #31,d2
        divu.w  #63,d2
        lsl.w   #5,d2
        or.w    d2,d4

        moveq   #0,d3
        move.b  (a0)+,d3
        mulu.w  #31,d3
        add.w   #31,d3
        divu.w  #63,d3
        or.w    d3,d4

        move.w  d4,(a1)+
        dbra    d0,.palette_loop
        movem.l (sp)+,d0-d4/a0-a1
        rts

; DOS: N/A - target artefact; record: uw2_indexed_to_rgb565.
; Expand one complete 320x200 indexed surface to a chunky RGB565 page.
;
; Inputs:
;   a0 = 64,000-byte row-major index8 source
;   a1 = 128,000-byte big-endian RGB565 destination page
;   a2 = 512-byte LUT from uw2_falcon_build_rgb565_lut
; Outputs: destination contains exactly one RGB565 word per source index.
; Clobbers: condition codes only; d0-d7/a0-a2 are preserved.
uw2_falcon_present_rgb565
        movem.l d0-d7/a0-a2,-(sp)
        move.w  #FALCON_FRAME_PIXELS/8-1,d7
.pixel_group
        rept    8
        moveq   #0,d0
        move.b  (a0)+,d0
        add.w   d0,d0
        move.w  (a2,d0.w),(a1)+
        endr
        dbra    d7,.pixel_group
        movem.l (sp)+,d0-d7/a0-a2
        rts

        end
