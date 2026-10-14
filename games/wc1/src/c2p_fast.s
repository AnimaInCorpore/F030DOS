        include "inc/wc1.s"

        xdef    wc1_indexed_to_rgb565

        section text

; -----------------------------------------------------------------------------
; wc1_indexed_to_rgb565
;
; Target artefact: c2p_present_rgb565; record:
; analysis/functions/c2p-present.md. N/A - platform replacement: the DOS
; program presents indexed VGA data, while the Falcon Videl page is RGB565.
;
; C ABI:
;   4(sp)  = indexed 320x200 source
;   8(sp)  = big-endian RGB565 destination
;   12(sp) = 256-word native-endian RGB565 palette
;
; The source renderer remains indexed. This Falcon-only seam expands eight
; pixels per loop iteration and writes palette words directly, which is the
; byte order already required by the Videl page. a2 is callee-saved under the
; m68k-elf-gcc ABI; d0/d1 are caller-saved and are sufficient for the palette
; index, colour and unrolled loop counter.
; -----------------------------------------------------------------------------
wc1_indexed_to_rgb565
        move.l  4(sp),a0
        move.l  8(sp),a1
        move.l  12(sp),a2
        move.l  a2,-(sp)

        tst.l   a0
        beq     .done
        tst.l   a1
        beq     .done
        tst.l   a2
        beq     .done

        move.w  #(CHUNKY_BYTES/8)-1,d1
.loop
        moveq   #0,d0
        move.b  (a0)+,d0
        move.w  (a2,d0.w*2),d0
        move.w  d0,(a1)+

        moveq   #0,d0
        move.b  (a0)+,d0
        move.w  (a2,d0.w*2),d0
        move.w  d0,(a1)+

        moveq   #0,d0
        move.b  (a0)+,d0
        move.w  (a2,d0.w*2),d0
        move.w  d0,(a1)+

        moveq   #0,d0
        move.b  (a0)+,d0
        move.w  (a2,d0.w*2),d0
        move.w  d0,(a1)+

        moveq   #0,d0
        move.b  (a0)+,d0
        move.w  (a2,d0.w*2),d0
        move.w  d0,(a1)+

        moveq   #0,d0
        move.b  (a0)+,d0
        move.w  (a2,d0.w*2),d0
        move.w  d0,(a1)+

        moveq   #0,d0
        move.b  (a0)+,d0
        move.w  (a2,d0.w*2),d0
        move.w  d0,(a1)+

        moveq   #0,d0
        move.b  (a0)+,d0
        move.w  (a2,d0.w*2),d0
        move.w  d0,(a1)+

        dbra    d1,.loop
.done
        move.l  (sp)+,a2
        rts
