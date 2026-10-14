; Indexed software renderer.
;
; Its 8-bit target is expanded to RGB565 at the Falcon presentation boundary.
; The active mobile-fighter pass uses the original sparse shapes and the DOS
; 3Space projection/frame selector.

        include "inc/wc1.s"

        xdef    render_frame
        xdef    put_pixel
        xdef    fill_rect
        xdef    render_target
        xref    resource_status
        xref    resource_draw_cockpit
        xref    resource_draw_flight_scene
        xref    resource_draw_target_lock

        text

; Target artefact: render_frame; N/A - platform replacement. The platform
; wrapper clears the Falcon indexed surface, invokes the recovered 3Space
; scene seam, then applies Falcon/DOS-resource overlays.
render_frame
        move.l  a0,render_target
        bsr     render_clear
        bsr     render_cockpit
        bsr     render_scene
        bsr     render_fighter
        rts

render_clear
        movem.l d0-d7/a0-a1,-(sp)
        move.l  render_target,a0
        moveq   #0,d7
.row
        move.w  #COL_SPACE,d0
        cmpi.w  #55,d7
        blt     .colour_ready
        move.w  #COL_SPACE_MID,d0
        cmpi.w  #125,d7
        blt     .colour_ready
        move.w  #COL_SPACE_LIGHT,d0
.colour_ready
        move.b  d0,d1
        lsl.w   #8,d0
        move.b  d1,d0
        move.w  d0,d1
        swap    d0
        move.w  d1,d0
        move.w  #FRAME_WIDTH/4-1,d6
.longs
        move.l  d0,(a0)+
        dbra    d6,.longs
        addq.w  #1,d7
        cmpi.w  #FRAME_HEIGHT,d7
        blt     .row
        movem.l (sp)+,d0-d7/a0-a1
        rts

; DOS: 1990 canonical entry/range TBD; record:
; analysis/functions/FlightSceneDepthMerge.md. The scene helper is explicitly
; Unproven and remains inside the diagnostic flight slice until DOS overlay
; identity and an oracle fixture are recovered.
render_scene
        jsr     resource_draw_flight_scene
        rts

render_fighter
        ; COCKPIT.VGA section zero is a real WC1 target-lock shape. The C
        ; packet service retains its DOS palette indices through presentation.
        jsr     resource_draw_target_lock
        rts

render_cockpit
        btst    #2,resource_status
        beq     .diagnostic
        jsr     resource_draw_cockpit
        rts
.diagnostic
        move.w  #0,d0
        move.w  #160,d1
        move.w  #FRAME_WIDTH,d2
        move.w  #40,d3
        move.w  #COL_PANEL,d4
        bsr     fill_rect
        move.w  #0,d0
        move.w  #160,d1
        move.w  #FRAME_WIDTH,d2
        move.w  #2,d3
        move.w  #COL_PANEL_EDGE,d4
        bsr     fill_rect

        move.w  #8,d0
        move.w  #170,d1
        move.w  #84,d2
        move.w  #24,d3
        move.w  #COL_BLACK,d4
        bsr     fill_rect
        move.w  #228,d0
        move.w  #170,d1
        move.w  #84,d2
        move.w  #24,d3
        move.w  #COL_BLACK,d4
        bsr     fill_rect
        move.w  #112,d0
        move.w  #190,d1
        move.w  #96,d2
        move.w  #3,d3
        move.w  #COL_PANEL_EDGE,d4
        bsr     fill_rect
        rts

; In: d0.w=x, d1.w=y, d2.b=palette index. Clipped to the chunky frame.
put_pixel
        movem.l d0-d4/a0-a1,-(sp)
        cmpi.w  #FRAME_WIDTH-1,d0
        bhi     .done
        cmpi.w  #FRAME_HEIGHT-1,d1
        bhi     .done
        move.l  render_target,a0
        move.w  d1,d3
        mulu    #CHUNKY_STRIDE,d3
        move.w  d0,d4
        add.w   d4,d3
        adda.l  d3,a0
        move.b  d2,(a0)
.done
        movem.l (sp)+,d0-d4/a0-a1
        rts

; In: d0=x, d1=y, d2=width, d3=height, d4.b=palette index.
fill_rect
        movem.l d0-d7/a0-a2,-(sp)
        move.l  render_target,a0
        move.w  d1,d5
        mulu    #CHUNKY_STRIDE,d5
        moveq   #0,d6
        move.w  d0,d6
        add.l   d6,d5
        adda.l  d5,a0
        move.w  d3,d7
        subq.w  #1,d7
.row
        move.w  d2,d6
        subq.w  #1,d6
        move.w  d4,d5
.pixel
        move.b  d5,(a0)+
        dbra    d6,.pixel
        move.w  #CHUNKY_STRIDE,d5
        move.w  d2,d6
        sub.w   d6,d5
        adda.w  d5,a0
        dbra    d7,.row
        movem.l (sp)+,d0-d7/a0-a2
        rts

        bss
        even
render_target   ds.l    1
        end
