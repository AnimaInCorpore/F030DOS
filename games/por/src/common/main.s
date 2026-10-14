; Target-neutral frame loop.
;
; Slice 1 — presentation endpoint: stage one converted image bank, draw into the
; indexed surface, hand it to the target back end, and idle until a key is
; pressed. This file names no hardware: everything target-specific arrives
; through the contract in PORTING.md §Target back ends.
;
; 68000-clean — the Atari ST is a live target.

        include "inc/por.s"
        include "inc/gemdos.s"

        xdef    main
        xref    resource_load_bank
        xref    resource_image
        xref    resource_status
        xref    resource_write_status
        xref    surface_clear
        xref    blit_centred
        xref    bank_buffer
        ; --- target contract (src/target/<name>/) ---
        xref    render_surface          ; long: the indexed 320x200 surface
        xref    target_build_lut        ; a0 = bank base
        xref    target_present          ; a0 = surface, a1 = hidden page
        xref    target_flip             ; publish the drawn page
        xref    target_hidden_page      ; long: page target_present writes into
        xref    target_frame_count      ; long: incremented once per vertical blank

        text

main
        move.w  #STATUS_OK,resource_status
        lea     title_name,a0
        bsr     resource_load_bank
        tst.l   d0
        bmi     .report

        move.l  bank_buffer,a0
        bsr     target_build_lut

        moveq   #0,d0                   ; image 0 = the title screen
        bsr     resource_image
        tst.w   d0
        bmi     .report

        ; d1/d2 hold the geometry, a0 the pixels. Draw the frame at IPL 7 so
        ; the publication below cannot be split by the VBL.
        move.w  #$2700,sr
        move.l  a0,-(sp)
        move.l  render_surface,a0
        moveq   #0,d0
        bsr     surface_clear
        move.l  render_surface,a1
        move.l  (sp)+,a0
        move.w  d1,d0
        move.w  d2,d1
        bsr     blit_centred
        tst.w   d0
        bmi     .unmask_and_report

        move.l  render_surface,a0
        move.l  target_hidden_page,a1
        bsr     target_present
        bsr     target_flip
        move.w  #$2300,sr

.report
        bsr     resource_write_status
        tst.w   resource_status
        bne     .done

        ; Idle on the published page. The frame clock keeps ticking so a
        ; headless capture run always finds a stable, complete frame.
        move.l  target_frame_count,last_frame
.loop
        Cconis
        tst.l   d0
        bne     .drain
        move.l  target_frame_count,d0
        move.l  d0,last_frame
        bra     .loop
.drain
        Cnecin
.done
        rts

.unmask_and_report
        move.w  #$2300,sr
        bra     .report

        data
        even
title_name      dc.b    'PORCACHE\TITLE.BIN',0
        even

        bss
        even
last_frame      ds.l    1

        end
