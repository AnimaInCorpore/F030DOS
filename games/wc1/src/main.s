; Falcon frame loop. Game state and rendering never touch the display buffer;
; only this module and the VBL handler publish a completed page.

        include "inc/wc1.s"

        xdef    main
        xdef    work_screen
        xdef    display_screen
        xdef    render_screen
        xdef    pending_screen
        xdef    exit_requested
        xdef    flip_pages
        xref    frame_count
        xref    input_init
        xref    input_shutdown
        xref    input_mouse_x
        xref    input_mouse_y
        xref    game_init
        xref    game_tick
        xref    game_service_resources
        xref    render_frame
        xref    hud_draw
        xref    mission_init
        xref    mission_player_ship
        xref    mission_ship_types
        xref    resource_init
        xref    resource_palette_rgb565
        xref    resource_load_title
        xref    resource_load_cockpit
        xref    resource_load_flight_weapons
        xref    resource_draw_mouse_cursor
        xref    object_types
        xref    front_run
        xref    wc1_indexed_to_rgb565

        text

main
        jsr     input_init
        jsr     resource_init
        jsr     resource_load_title
        bsr     front_run
        tst.w   d0
        beq     .done
        bsr     mission_init
        ; InitializeCockpitResources() uses the loaded player type as its
        ; cockpit mode for normal campaign series. Keep that DOS ordering:
        ; mission data chooses PCSHIP.Vxx through INSTALL.DAT, then the
        ; generic resource service retains its primary shape.
        moveq   #0,d1
        move.w  mission_player_ship,d1
        bmi     .default_cockpit
        cmpi.w  #MISSION_SHIP_COUNT,d1
        bhs     .default_cockpit
        add.w   d1,d1
        lea     mission_ship_types,a0
        moveq   #0,d0
        move.w  0(a0,d1.w),d0
        bmi     .default_cockpit
        bra     .load_cockpit
.default_cockpit
        clr.l   d0
.load_cockpit
        move.l  d0,-(sp)
        jsr     resource_load_cockpit
        addq.l  #4,sp
        bsr     game_init
        ; Fixed projectile shape packets are selected from ObjectTypeData's
        ; player loadout once game_init has instantiated object slot zero.
        ; This startup load is deliberately outside the masked VBL frame loop.
        moveq   #0,d0
        move.w  object_types,d0
        move.l  d0,-(sp)
        jsr     resource_load_flight_weapons
        addq.l  #4,sp

        move.w  #$2700,sr
        move.l  render_screen,a0
        bsr     render_frame
        bsr     hud_draw
        bsr     main_draw_mouse_cursor
        bsr     present_flight_frame
        bsr     flip_pages
        move.w  #$2300,sr

        move.l  frame_count,last_frame
.loop
.wait_vbl
        move.l  #VBL_WAIT_LIMIT,d1
.wait
        move.l  frame_count,d0
        cmp.l   last_frame,d0
        bne     .frame_ready
        subq.l  #1,d1
        bne     .wait
.frame_ready
        move.l  d0,last_frame

        ; The TOS VBL handler we tail-chain into is not a transparent ABI
        ; boundary: it may clobber foreground registers. Keep the complete
        ; update/render/publication transaction at IPL 7 and enable VBL only
        ; while waiting above. This is also the natural ownership boundary for
        ; the two-page renderer.
        move.w  #$2700,sr
        bsr     game_tick
        tst.w   exit_requested
        bne     .done_masked
        ; game_tick may have entered a different action sphere. Perform its
        ; bounded GEMDOS preload work with VBLs enabled; vbl.s now restores
        ; the interrupted foreground register set after it tail-chains TOS.
        move.w  #$2300,sr
        bsr     game_service_resources
        move.w  #$2700,sr
        move.l  render_screen,a0
        bsr     render_frame
        bsr     hud_draw
        bsr     main_draw_mouse_cursor
        bsr     present_flight_frame
        bsr     flip_pages
        move.w  #$2300,sr
        bra     .loop

.done_masked
        move.w  #$2300,sr
        jsr     input_shutdown
        rts

.done
        jsr     input_shutdown
        rts

flip_pages
        move.l  work_screen,d0
        move.l  display_screen,work_screen
        move.l  d0,display_screen
        move.l  display_screen,pending_screen
        rts

main_draw_mouse_cursor
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

; Expand the indexed render surface into the hidden RGB565 Videl page. The
; source palette remains byte-for-byte faithful to the DOS assets, while the
; display no longer depends on Falcon palette registers or the DSP.
present_flight_frame
        move.l  #resource_palette_rgb565,-(sp)
        move.l  work_screen,-(sp)
        move.l  render_screen,-(sp)
        jsr     wc1_indexed_to_rgb565
        lea     12(sp),sp
        rts

        bss
        even
work_screen     ds.l    1
display_screen  ds.l    1
pending_screen  ds.l    1
render_screen   ds.l    1
last_frame      ds.l    1
exit_requested  ds.w    1

        end
