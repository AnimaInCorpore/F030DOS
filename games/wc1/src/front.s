; Native Falcon Title_Sequence() front end.
;
; The 3Space star/camera foundation, original title time line, subtitle and
; credit artwork, logo zoom, Escape-to-menu behaviour, and settled New Game
; endpoint are native. Dust, ships, sorting, and music remain later ports.

        include "inc/wc1.s"

        xdef    front_run
        xref    frame_count
        xref    work_screen
        xref    render_screen
        xref    resource_palette_rgb565
        xref    input_poll
        xref    input_events
        xref    input_mouse_x
        xref    input_mouse_y
        xref    flip_pages
        xref    resource_draw_intro_frame
        xref    resource_reset_intro_scene
        xref    resource_draw_title_screen
        xref    resource_draw_mouse_cursor
        xref    wc1_indexed_to_rgb565

        text

; Out: d0 = 1 to start a new campaign flight, 0 to return to TOS.
front_run
        movem.l d1-d7/a0-a2,-(sp)
        clr.w   front_selection
        clr.w   front_intro_phase
        clr.w   front_intro_tick
        clr.w   front_intro_credit
        jsr     resource_reset_intro_scene

        ; The first cinematic page is published through the same VBL ownership
; path as flight, rather than writing the visible page.
        move.w  #$2300,sr
        bsr     front_present_current
        move.w  #$2700,sr
        bsr     flip_pages
        ; GEMDOS/TOS can leave the key used to launch the .TOS program in the
        ; console queue. Drain it after the first page is visible so it cannot
        ; accidentally skip a future menu selection.
        bsr     input_poll
        move.w  #$2300,sr
        move.l  frame_count,front_last_frame
        bsr     front_advance
.loop
        move.l  #VBL_WAIT_LIMIT,d1
.wait
        move.l  frame_count,d0
        cmp.l   front_last_frame,d0
        bne     .frame_ready
        subq.l  #1,d1
        bne     .wait
.frame_ready
        move.l  d0,d7
        sub.l   front_last_frame,d7
        move.l  d0,front_last_frame
        tst.l   d7
        bne.s   .elapsed_ready
        moveq   #1,d7
.elapsed_ready
        move.l  d7,front_elapsed

        move.w  #$2700,sr
        bsr     input_poll
        move.w  input_events,d0
        btst    #INPUT_QUIT,d0
        bne     .quit_or_skip
        cmpi.w  #FRONT_PHASE_MENU,front_intro_phase
        bne     .present
        btst    #INPUT_FIRE,d0
        bne     .accept
        btst    #INPUT_ACCEPT,d0
        bne     .accept
.present
        ; The hidden indexed and RGB565 pages are disjoint from the page
        ; currently scanned by Videl. Let VBL continue while the foreground
        ; builds this next page; vbl.s saves all foreground registers and only
        ; publishes pending_screen at the edge.
        move.w  #$2300,sr
        bsr     front_catch_up
        bsr     front_present_current
        move.w  #$2700,sr
        bsr     flip_pages
        bsr     front_advance
        move.w  #$2300,sr
        bra     .loop
.quit_or_skip
        cmpi.w  #FRONT_PHASE_MENU,front_intro_phase
        beq     .cancel
        bsr     front_enter_menu
        move.w  #$2300,sr
        bsr     front_present_current
        move.w  #$2700,sr
        bsr     flip_pages
        move.w  #$2300,sr
        bra     .loop
.accept
        move.w  #$2300,sr
        moveq   #1,d0
        bra     .done
.cancel
        move.w  #$2300,sr
        clr.w   d0
.done
        movem.l (sp)+,d1-d7/a0-a2
        rts

; Render one static title-menu page into the hidden buffer.
front_present_current
        cmpi.w  #FRONT_PHASE_MENU,front_intro_phase
        beq     front_present_menu
        bra     front_present_intro

; Render one original-title endpoint page into the hidden buffer.
front_present_menu
        move.l  render_screen,a0
        moveq   #0,d0
        move.w  front_selection,d0
        move.l  d0,-(sp)              ; uint16_t selection (C stack slot)
        move.l  a0,-(sp)              ; uint16_t *target
        jsr     resource_draw_title_screen
        addq.l  #8,sp
        bsr     front_draw_mouse_cursor
        bsr     front_present_frame
        rts

; Render the original TITLE.VGA font/logo frames and the first native 3Space
; layer into the indexed back buffer. resource_draw_intro_frame() owns the
; seven PLANETS.VGA stars, title camera, action effects, and credit hazards.
front_present_intro
        moveq   #0,d0
        cmpi.w  #FRONT_PHASE_LOGO,front_intro_phase
        bne.s   .credit_index
        move.w  front_intro_tick,d0
        bra.s   .push_index
.credit_index
        move.w  front_intro_credit,d0
.push_index
        move.l  d0,-(sp)              ; uint16_t index / credit
        moveq   #0,d0
        move.w  front_intro_phase,d0
        cmpi.w  #FRONT_PHASE_CREDIT_SPACE,d0
        bne.s   .stage_ready
        moveq   #FRONT_PHASE_SPACE,d0
.stage_ready
        cmpi.w  #FRONT_PHASE_TAIL,d0
        bne.s   .push_stage
        moveq   #FRONT_PHASE_SPACE,d0
.push_stage
        move.l  d0,-(sp)              ; uint16_t resource stage
        move.l  render_screen,-(sp)   ; uint8_t *DOS indexed source
        jsr     resource_draw_intro_frame
        lea     12(sp),sp
        bsr     front_draw_mouse_cursor
        bsr     front_present_frame
        rts

front_draw_mouse_cursor
        moveq   #0,d0
        move.w  input_mouse_y,d0
        move.l  d0,-(sp)              ; int16_t y
        moveq   #0,d0
        move.w  input_mouse_x,d0
        move.l  d0,-(sp)              ; int16_t x
        move.l  render_screen,-(sp)   ; uint8_t *target
        jsr     resource_draw_mouse_cursor
        lea     12(sp),sp
        rts

; Title animation has the same complete-frame contract as flight. Expand the
; indexed page through the loaded palette into the hidden RGB565 page.
front_present_frame
        move.l  #resource_palette_rgb565,-(sp) ; uint16_t *RGB565 palette
        move.l  work_screen,-(sp)             ; uint8_t *RGB565 destination
        move.l  render_screen,-(sp)           ; uint8_t *indexed source
        jsr     wc1_indexed_to_rgb565
        lea     12(sp),sp
        rts

; Advance exactly once after every published cinematic frame. The catch-up
; helper below may first apply elapsed VBLs while rendering was busy, so these
; remain source logical counts rather than Falcon transfer latency. They are
; copied from nav.c: 25 opening subtitles, 110 establishing frames, 100
; logo-zoom frames, 11*(70 credit + 40 space), then 150 frames.
front_advance
        moveq   #1,d0

front_advance_elapsed
        tst.w   d0
        beq     .done
        subq.w  #1,d0
        cmpi.w  #FRONT_PHASE_MENU,front_intro_phase
        beq     .done
        addq.w  #1,front_intro_tick
        cmpi.w  #FRONT_PHASE_OPENING,front_intro_phase
        beq     .opening
        cmpi.w  #FRONT_PHASE_SPACE,front_intro_phase
        beq     .space
        cmpi.w  #FRONT_PHASE_LOGO,front_intro_phase
        beq     .logo
        cmpi.w  #FRONT_PHASE_CREDIT,front_intro_phase
        beq     .credit
        cmpi.w  #FRONT_PHASE_CREDIT_SPACE,front_intro_phase
        beq     .credit_space
        ; Only the fixed post-credit space interval remains here.
        cmpi.w  #150,front_intro_tick
        blo     .tick_done
        bra     front_enter_menu
.opening
        cmpi.w  #25,front_intro_tick
        blo     .tick_done
        move.w  #FRONT_PHASE_SPACE,front_intro_phase
        clr.w   front_intro_tick
        bra     .tick_done
.space
        cmpi.w  #110,front_intro_tick
        blo     .tick_done
        move.w  #FRONT_PHASE_LOGO,front_intro_phase
        clr.w   front_intro_tick
        bra     .tick_done
.logo
        cmpi.w  #100,front_intro_tick
        blo     .tick_done
        move.w  #FRONT_PHASE_CREDIT,front_intro_phase
        clr.w   front_intro_tick
        clr.w   front_intro_credit
        bra     .tick_done
.credit
        cmpi.w  #70,front_intro_tick
        blo     .tick_done
        move.w  #FRONT_PHASE_CREDIT_SPACE,front_intro_phase
        clr.w   front_intro_tick
        bra     .tick_done
.credit_space
        cmpi.w  #40,front_intro_tick
        blo     .tick_done
        addq.w  #1,front_intro_credit
        cmpi.w  #11,front_intro_credit
        bhs.s   .tail
        move.w  #FRONT_PHASE_CREDIT,front_intro_phase
        clr.w   front_intro_tick
        bra     .tick_done
.tail
        move.w  #FRONT_PHASE_TAIL,front_intro_phase
        clr.w   front_intro_tick
.tick_done
        bra     front_advance_elapsed
.done
        rts

; The source title advances once per completed Draw_3Space_Frame(). If a
; Falcon page conversion spans multiple VBLs, do not replay the missed source
; frames in a burst: that produces a fast slideshow even though the visible
; page rate is low. front_advance below remains the sole logical step.
front_catch_up
        rts

front_enter_menu
        move.w  #FRONT_PHASE_MENU,front_intro_phase
        clr.w   front_intro_tick
        rts

FRONT_PHASE_OPENING      = 0
FRONT_PHASE_SPACE        = 1
FRONT_PHASE_LOGO         = 2
FRONT_PHASE_CREDIT       = 3
FRONT_PHASE_CREDIT_SPACE = 4
FRONT_PHASE_TAIL         = 5
FRONT_PHASE_MENU         = 6

        bss
        even
front_selection  ds.w    1
front_intro_phase ds.w   1
front_intro_tick  ds.w   1
front_intro_credit ds.w  1
front_last_frame ds.l    1
front_elapsed ds.l    1

        end
