; Route: analysis/functions/falcon-attract.md#attract-route, generated only
; after work/qemu_out/attract-trace-report.txt and object-state-walk.txt.
; The attract cycle, shaped exactly as the DOS state machine at 00005690:
; a pass counter whose low bit alternates two openings, a recorded demo
; flight after either, and any key out. Each pass selects its mission
; resource block before DEMO<pass>.SCR, so the four authored demos fly their
; own terrain and sky. The traced route executes the mission object factory
; before DEMO<pass> and reaches the active object/callback/effect graph in the
; flight frame. The digital effect layer (src/sound.s) is wired at the points the
; original calls it, and so is the music driver (src/music.s); the platform's 50 Hz VBL differs from
; the original's ~70 Hz retrace. The state machine still consumes exactly
; one recorded DOS tick per completed frame; only wall-clock presentation
; rate differs.
;
;   pass 1, 3: FANFARE.RLE over BACK.DTA, 480 ticks, then the TPIC.DTA
;              pan with the COMA nine-view rotation, 600 ticks
;   pass 2, 0: RH66SIDE.DTA with the ZOVE.RLE animation, 300 ticks
;   then:      DEMO<pass>.SCR through the exact flight integration
;
; The screens are 328x240 Mode X pages, not 320x200: RH66SIDE.DTA and
; BACK.DTA measure 328x240, the CRTC row stride at 00015B78 is 0x52 per
; plane - 328 pixels - and TPIC.DTA's 390 rows are exactly the 240 shown
; plus the 150 the pan travels. So the view is the left 320 columns of the
; stored image and the full 240 rows, with no letterbox anywhere.
;
; The pan is the CRTC start address: 00015BC9 adds [00019DC4] to it, and
; 00005A79 adds 0x52 - one row - to that counter per tick, clamped at
; 0x300C, which is row 150. This port has no 328-wide page to scroll, so it
; re-blits from the decoded image at the pan row instead. That also erases
; the overlay for free, which the original needs its second page for.
;
; Frame tables extracted from the image: ZOVE cycles 3,3,2,2,1,1 and COMA
; walks 9..1 four ticks each, both one entry per tick with a zero
; terminator; the wobble is a 64-entry 0..4..0 bump, and it rides the
; helicopter, not the pan.

        include "inc/comanche.s"

        xref    snd_mode, snd_reset, snd_apply_settings, snd_title_bank_load
        xref    music_attract_pass, music_side_start, music_fanfare_start
        xref    music_title_start, music_menu_enter, music_resend, music_playing
        xref    snd_bank_fx, snd_sample_ptr, snd_voice
        xref    flight_mission_sound_load, flight_mission_sound_start

        global  attract_start, attract_restart, attract_stop, attract_frame
        global  attract_overview, attract_next_pass, attract_active, attract_blit_x
        global  attract_active
; The Kyle DTA loader and its blitter are shared with the menu screens, which
; is what the original does too: 00028CFB opens rah66.dta through the same
; 00016381/0001687D pair the attract screens go through.
        global  attract_show_image, attract_pan_blit, attract_pan_clear

        text

; Restart the cycle from its first pass. This is the menu's Demo line and only
; that: 00028ECA zeroes [00019ED5] and jumps to 00005690, which increments it
; straight back to 1. Nothing else in the original zeroes that counter - the
; attract entry itself only increments - so the reset belongs here rather than
; in attract_start, where a later mission-end return would silently inherit it
; and send the player back to pass 1 instead of the next map.
; DOS: flat 00028ECA-00028ED1, the main menu's Demo selection.
; DOS symbol: inside loc_00028EC6
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: zeroes the pass and enters the cycle, so the entry advances it to 1.
; Preserved: the zero-then-increment order and its landing pass.
; Kind: translated.
; Status: ported.
attract_restart
        clr.w   attract_pass
        bra     attract_start

; Enter the attract cycle on the pass AFTER the current one. Its first screen
; and every later transition require the named DOS assets; a missing one
; terminates the task rather than showing a fabricated free-flight or screen.
; The counter is not reset here - 00005690 only ever increments it, and at boot
; it starts from a zeroed BSS exactly as [00019ED5] does, so the first cycle is
; pass 1 on both sides.
; DOS: flat 00005690-00005AE3, attract-state entry.
; DOS symbol: loc_00005690
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: starts the authored screen/demo cycle on the next pass.
; Preserved: pass counter, screen order, timers, and any-key exit ownership.
; Kind: translated.
; Status: ported; audio and real-menu handoff remain explicit gaps.
attract_start
        clr.w   demo_active                     ; screens first
        move.w  #1,attract_active
        bsr     attract_next_pass
        rts

; DOS: flat 00005690-00005AE3, attract exit into the real menu.
; DOS symbol: loc_00005690
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: stops replay/screens and re-enters the mission under live control.
; Preserved: any-key exit and the mission-start reseed the DOS path performs.
; Kind: translated.
; Status: partial; the menu chain itself between the two remains unported.
attract_stop
        ; 00005AE3: the common exit to the menu switches the mixer off and clears
        ; its slots (00005AF0 MODE(0), 00005B24 RESET).
        moveq   #0,d0
        jsr     snd_mode
        jsr     snd_reset
        clr.w   attract_untimed
        clr.w   attract_active
        clr.w   attract_screen
        clr.w   demo_active
        clr.w   input_pending
    ifne USE_DSP
        move.w  #2,surface_reseed               ; same heal on any-key exit
    endc
        ; DOS leaves the cycle at 00005AE3, which clears the replay mode and
        ; calls the menu chain at 00028C3E. That chain's menu path reaches the
        ; list menu at 00027DB4 on its main operations screen, which is now
        ; ported, so the attract exit lands there rather than dropping straight
        ; into a flight the player never asked for.
        ;
        ; What sits between 00005AE3 and the list menu - WIN3/RAH66 backgrounds,
        ; the music loads, the pilot roster - is not ported. The menu is entered
        ; over whatever the attract left on screen instead of over its own
        ; background, which is the visible gap and is recorded as such.
        jsr     music_menu_enter                ; 00005AE3 and 00028CA2-00028CE3
        moveq   #0,d0                           ; [00027DAC] = 0, main operations
        jsr     screen_enter
        rts

; Advance the pass counter and enter its opening, DOS order: increment
; first, odd passes open with the title, even with the side art.
; DOS: flat 00005690-00005AE3, pass increment and screen selection.
; DOS symbol: loc_00005690
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: increments the authored four-pass cycle and loads its assets.
; Preserved: odd/even screen choice, pass modulo, and timer values.
; Kind: translated.
; Status: ported; full attract cycle capture verified at VBL 3000/7000/11000.
attract_next_pass
        movem.l d0/a0-a1,-(sp)
        ; 00005692: the mixer is off at the start of every pass.
        moveq   #0,d0
        jsr     snd_mode
        jsr     music_attract_pass              ; 000056C4-000056D8
        move.w  attract_pass,d0
        addq.w  #1,d0
        andi.w  #3,d0
        move.w  d0,attract_pass
        ; 00005690's pass byte is the value later copied into the replay
        ; selector at 000056B7.  Keep that boundary value beside the screen
        ; state as well: the Falcon's image/sprite loaders may run between
        ; the opening and DEMO<N>, but they must not make the replay choose a
        ; different mission.  This is storage scheduling only; the value is
        ; still the recovered 0..3 pass selected above.
        move.w  d0,attract_demo_pass
        btst    #0,d0
        beq     .side
        move.w  #AT_FANFARE,attract_screen
        move.w  #480,attract_timer
        lea     name_back,a0
        bsr     attract_show_image
        jsr     music_fanfare_start             ; 000057EE, 00005851: FANFARE.RLE once
        jsr     snd_apply_settings              ; 00005856: the mixer on for the fanfare screen
        move.w  #1,attract_bank_bad             ; FANFARE.RLE is the tune,
        bra     .entered                        ; not a bank: image alone
.side
        move.w  #300,attract_timer
        bsr     attract_side_enter
        jsr     music_side_start                ; 000056F9, 00005771: MENUMUS2 looped
        jsr     snd_apply_settings              ; 00005765: the mixer on for the side view
.entered
        clr.w   attract_anim
        clr.w   attract_pan
        clr.w   attract_wob
        move.w  #2,attract_step
        move.w  #TITLE_HELI_TOP,attract_heli
        movem.l (sp)+,d0/a0-a1
        rts

; The side screen's setup, 00005776-00005790: RH66SIDE.DTA, then ZOVE.RLE
; remapped against its palette, with the animation cursor at the start.
; Shared by the cycle's even passes and the main menu's RAH-66 Overview.
; DOS: flat 00005776-00005790 and 00028E06-00028E6C.
; DOS symbol: inside loc_00005690
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same two loads and the same cursor reset.
; Preserved: the load order and the overlay held off until both are done.
; Kind: translated.
; Status: ported.
attract_side_enter
        movem.l d0/a0-a1,-(sp)
        move.w  #AT_SIDE,attract_screen
        ; The two setup paints happen before the bank is loaded and remapped,
        ; so hold the overlay off until both are: otherwise they draw the
        ; previous pass's ZOVE through the previous pass's palette.
        move.w  #1,attract_bank_bad
        lea     name_rh66,a0
        bsr     attract_show_image
        ; ZOVE is consumed by the Mode X blitter at 00025880, so it is stored
        ; plane-chunked by row and bottom-up like COMA and CONS, not column
        ; major like TANK. Loading it as the latter drew diagonal hatching.
        lea     name_zove,a0
        lea     attract_bank,a1
        jsr     sprite_bank_load_planar
        move.w  d0,attract_bank_bad
        tst.w   d0
        bne     .done
        lea     attract_bank,a1
        bsr     attract_bank_remap
.done
        movem.l (sp)+,d0/a0-a1
        rts

; The main menu's RAH-66 Overview, 00028E06-00028EC1: the side screen's
; animation without the cycle around it - no count, no demo after it - until a
; key, which hands back to the main menu (00028CE8). The key that chose the
; line is still in the buffer and would end it on the first frame, so it is
; emptied as the credits screen does.
; DOS: flat 00028E06-00028EC1.
; DOS symbol: inside loc_00028DFE
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the side screen's own loop, untimed.
; Preserved: the animation table, its position and the key exit.
; Kind: translated.
; Status: ported.
attract_overview
        clr.w   input_held
        clr.w   input_pending
        clr.w   input_events
        bsr     attract_side_enter
        clr.w   attract_anim
        clr.w   attract_pan
        clr.w   attract_wob
        move.w  #2,attract_step
        move.w  #1,attract_untimed
        move.w  #1,attract_active
        rts

; One attract frame, called from the main loop after the VBL wait. Returns
; d0 = 1 when it owned the frame (the normal flight frame is skipped),
; d0 = 0 when the demo flight below should run as a normal frame.
;
; The original runs one state step per retrace. The Falcon frame loop likewise
; advances the screen state once per completed frame; elapsed VBLs are timing
; telemetry only and must not make a slow render consume several DOS ticks.
; DOS: flat 00005690-00005AE3, one attract tick/ownership decision.
; DOS symbol: loc_00005690
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: advances one authored screen tick or hands control to DEMO<N>.SCR.
; Preserved: one tick per completed frame and the screen-blit-before-input
; exit gate.
; Kind: translated.
; Status: ported; demo-flight capture verified at VBL 3000/7000/11000.
attract_frame
        tst.w   attract_active
        bne     .active
        moveq   #0,d0
        rts
.active
        movem.l d1-d7/a0-a1,-(sp)
        tst.w   attract_screen
        beq     .demo_pass                      ; AT_NONE: the flight

        bsr     attract_paint
        bsr     attract_flip
        ; DOS draws the current animation record first. Its retrace wait and
        ; LOOP decrement come after the blit, so advance the authored frame,
        ; pan and helicopter state only after publishing this frame. Advancing
        ; before the paint skipped ZOVE record 0's timing and started TPIC at
        ; pan row 1 instead of row 0.
        bsr     attract_tick
        subq.w  #1,attract_timer

        ; 000057CD/00005866/00005AA1 poll after the blit and retrace. Use
        ; input_events, not input_pending: input_poll folds pending bits into
        ; the event snapshot and clears pending as its last act.
        bsr     input_poll
        tst.w   input_events
        beq     .screen_no_key
        bsr     attract_stop
        movem.l (sp)+,d1-d7/a0-a1
        moveq   #0,d0
        rts
.screen_no_key
        ; DOS LOOP tests its saved count, not the key poll's condition codes.
        ; TST input_events above leaves Z set on every no-key frame. The
        ; overview at 00028E7C has no count at all.
        tst.w   attract_untimed
        bne     .owned
        ; 0000587D (fanfare) and 00005ACC (title): the screen also ends when
        ; its song does - command 6 answering 0. Without a music device the
        ; song never advances and both run their full count, as there.
        move.w  attract_screen,d0
        cmpi.w  #AT_FANFARE,d0
        beq.s   .song_ends_it
        cmpi.w  #AT_TITLE,d0
        bne.s   .count
.song_ends_it
        jsr     music_playing
        tst.b   d0
        beq     .expired
.count
        tst.w   attract_timer
        ble     .expired
        bra     .owned

.expired
        ; The screen's run is over. Each successor paints both buffers for
        ; itself, so this frame publishes nothing of its own.
        move.w  attract_screen,d0
        cmpi.w  #AT_FANFARE,d0
        bne     .to_demo
        move.w  #AT_TITLE,attract_screen
        move.w  #600,attract_timer
        clr.w   attract_anim
        clr.w   attract_pan
        clr.w   attract_wob
        move.w  #2,attract_step
        move.w  #TITLE_HELI_TOP,attract_heli
        moveq   #0,d0
        jsr     snd_mode                        ; 00005891: the mixer off after the fanfare
        jsr     music_title_start               ; 00005896-000058B4, 0000596F: OPENMUS once
        jsr     snd_title_bank_load             ; 000058D4: snd1.rle for the title
        lea     name_tpic,a0
        bsr     attract_show_image
        ; 0000594D-00005963: the settings applied, then the rotor loop staged on
        ; slot 2 at half amplitude under the title (SND1 id 3, bl 2, dl 1, ecx 0).
        jsr     snd_apply_settings
        move.l  snd_bank_fx,a0
        move.l  a0,d0
        beq     .no_title_rotor                 ; platform: the bank is not loaded
        moveq   #3,d0
        jsr     snd_sample_ptr                  ; 00005958-00005961
        moveq   #2,d1                           ; 00005952
        moveq   #1,d3                           ; 00005954
        moveq   #0,d2                           ; 00005956
        jsr     snd_voice                       ; 00005963
.no_title_rotor
        tst.w   cockpit_status
        bne     .owned
        lea     cockpit_bank,a1                 ; COMA, against TPIC's palette
        bsr     attract_bank_remap
        bra     .owned
.to_demo
        bsr     attract_start_demo
        bra     .owned

.demo_pass
        bsr     input_poll
        tst.w   input_events
        beq     .demo_no_key
        bsr     attract_stop
        movem.l (sp)+,d1-d7/a0-a1
        moveq   #0,d0
        rts
.demo_no_key
        tst.w   demo_ended
        beq     .flight_frame
        bsr     attract_next_pass
        bra     .owned
.flight_frame
        movem.l (sp)+,d1-d7/a0-a1
        moveq   #0,d0                           ; run the normal frame
        rts
.owned
        movem.l (sp)+,d1-d7/a0-a1
        moveq   #1,d0
        rts

; ---------------------------------------------------------------------------
; One original tick of the current screen.
; ---------------------------------------------------------------------------

; DOS: flat 0000579A-000057E0 (side) and 000059ED-00005AD6 (title), the two
; authored screen tick loops; the fanfare loop at 00005860 has no tick body.
; DOS symbol: loc_0000579A
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: dispatches the authored side/title animation arithmetic.
; Preserved: state-specific update order and timer-independent screen ownership.
; Kind: translated.
; Status: ported; dispatcher covered by the full attract capture.
attract_tick
        move.w  attract_screen,d0
        cmpi.w  #AT_TITLE,d0
        beq     attract_tick_title
        cmpi.w  #AT_SIDE,d0
        beq     attract_tick_side
        rts                                     ; AT_FANFARE: a still

; The ZOVE cycle, one table entry per tick, wrapping on the terminator.
; The DOS side loop reads 0x28E75[idx]; a zero entry rewinds the cursor to
; 0xFF and re-reads entry 0, and the cursor is incremented after the frame
; number is published. The table is six non-zero entries, so that terminator
; wrap is the modulo below - same drawn sequence, same period.
; DOS: flat 0000579A-000057BD, ZOVE animation frame advance (table 0x28E75).
; DOS symbol: loc_0000579A
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: advances the authored ZOVE frame sequence with its terminator behavior.
; Preserved: table contents, wrap period, and one-entry-per-tick timing.
; Kind: translated.
; Status: ported; screen tick covered by the full attract capture.
attract_tick_side
        movem.l d0-d1,-(sp)
        move.w  attract_anim,d0
        addq.w  #1,d0
        moveq   #6,d1
        bsr     attract_mod
        move.w  d0,attract_anim
        movem.l (sp)+,d0-d1
        rts

; The pan and the Comanche over it, 000059F8..00005ABE in order: frame
; advance, entry gate, helicopter step and its two clamps, the wobble at the
; bottom clamp, the pan advance and its clamp, then the end-of-run step
; reversal. 00005A1A is a six-byte instruction, so the frame advance and the
; pan step are not separable at 00005A1B/00005A1C; the whole loop body is
; cited here and the frame advance alone above.
; DOS: flat 000059F8-00005ABE, TPIC pan/COMA animation tick (tables 0x59C8,
; wobble 0x5985).
; DOS symbol: inside loc_000059ED
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: advances authored pan, helicopter motion, gate, and wobble tables.
; Preserved: pan clamp, entry gate, terminal movement, and wobble cadence.
; Kind: translated.
; Status: ported; screen tick covered by the full attract capture.
attract_tick_title
        movem.l d0-d2,-(sp)
        move.w  attract_anim,d0
        addq.w  #1,d0
        moveq   #36,d1
        bsr     attract_mod
        move.w  d0,attract_anim

        ; The sprite is not drawn at all until the pan has travelled to the
        ; row it enters on: 00005A20 compares the pan counter against 0x1DCA,
        ; which is row 93, and jumps past the whole sprite step below it.
        cmpi.w  #TITLE_GATE_ROW,attract_pan
        blt     .pan_step
        move.w  attract_heli,d0
        add.w   attract_step,d0
        cmpi.w  #TITLE_HELI_TOP,d0
        bge     .low_ok
        move.w  #TITLE_HELI_TOP,d0
.low_ok
        cmpi.w  #TITLE_HELI_LOW,d0
        ble     .high_ok
        ; Clamped at the bottom of its travel, and only there, the helicopter
        ; picks up the 64-entry bump - two ticks per entry.
        move.w  #TITLE_HELI_LOW,d0
        move.w  attract_wob,d1
        addq.w  #1,attract_wob
        lsr.w   #1,d1
        andi.w  #63,d1
        lea     pan_wobble,a0
        moveq   #0,d2
        move.b  0(a0,d1.w),d2
        add.w   d2,d0
.high_ok
        move.w  d0,attract_heli

.pan_step
        addq.w  #1,attract_pan
        cmpi.w  #TITLE_PAN_LAST,attract_pan
        ble     .pan_ok
        move.w  #TITLE_PAN_LAST,attract_pan
        subq.w  #1,attract_heli                 ; 00005A8C, once the pan stops
.pan_ok
        ; The last 45 ticks reverse the climb, the last 40 double it.
        move.w  attract_timer,d0
        cmpi.w  #45,d0
        bge     .step_done
        move.w  #-1,attract_step
        cmpi.w  #40,d0
        bge     .step_done
        move.w  #-2,attract_step
.step_done
        movem.l (sp)+,d0-d2
        rts

; d0 = d0 mod d1, both small positives.
; DOS: no counterpart instruction - 000057A8/00005A05 wrap the cursor with
; the frame table's zero terminator instead. The recovered tables hold six and
; thirty-six non-zero entries, so this modulo reproduces that wrap exactly.
; DOS: flat 000057A8-000057BD / 00005A05-00005A1A, frame-cursor wrap.
; DOS symbol: inside loc_0000579A
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: wraps the authored animation cursor without substituting a new sequence.
; Preserved: divisor and zero-based result.
; Kind: translated.
; Status: ported; covered by attract tick validation.
attract_mod
        cmp.w   d1,d0
        blt     .done
        sub.w   d1,d0
        bra     attract_mod
.done
        rts

; ---------------------------------------------------------------------------
; Painting one frame of the current screen into the back buffer.
; ---------------------------------------------------------------------------

; DOS: flat 00005690-00005AE3 screen paint dispatch.
; DOS symbol: loc_00005690
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: paints authored background/side/title assets into Falcon buffers.
; Preserved: asset choice, overlay order, pan position, and palette ownership.
; Kind: adapted - platform surface port.
; Status: ported; screen composition covered by the full attract capture.
attract_paint
        movem.l d0-d2/a0-a1,-(sp)
        move.w  attract_screen,d0
        cmpi.w  #AT_TITLE,d0
        beq     .title
        cmpi.w  #AT_SIDE,d0
        beq     .side
        bra     .done                           ; the still needs no repaint

.side
        moveq   #0,d0
        bsr     attract_pan_blit
        tst.w   attract_bank_bad
        bne     .done
        move.w  attract_anim,d1
        lea     zove_frames,a0
        moveq   #0,d0
        move.b  0(a0,d1.w),d0
        beq     .done                           ; the table's zero terminator
        lea     attract_bank,a1
        move.w  #ZOVE_X,d1
        move.w  #ZOVE_Y,d2
        bsr     attract_overlay
        bra     .done

.title
        move.w  attract_pan,d0
        bsr     attract_pan_blit
        cmpi.w  #TITLE_GATE_ROW,attract_pan
        blt     .done                           ; DOS tests the current pan
        tst.w   cockpit_status
        bne     .done
        move.w  attract_anim,d1
        lea     coma_frames,a0
        moveq   #0,d0
        move.b  0(a0,d1.w),d0
        beq     .done                           ; the table's zero terminator
        lea     cockpit_bank,a1
        move.w  #COMA_X,d1
        move.w  attract_heli,d2
        sub.w   attract_pan,d2                  ; buffer row to screen row
        bsr     attract_overlay
.done
        movem.l (sp)+,d0-d2/a0-a1
        rts

; Draw sprite d0 of bank a1 at DOS reference X=d1, bottom row Y=d2, through
; the screen's palette. 00025880 copies every byte of the record, so the
; opaque draw is the right one: the near-black ground of these frames is
; what hides the trail the original leaves behind the climbing helicopter.
;
; The bank palettes shipped inside COMA.RLE and ZOVE.RLE are never in the
; DAC when that blitter runs - 0002B8C5 only copies them into a buffer and
; builds a nearest-colour translation table from them - so the indices land
; in the palette the screen installed. COMA's index 0 is a bright green
; marker in its own palette and black in TPIC's, which is exactly the green
; column that stood at the sprite's right edge until this was recovered.
; DOS: flat 00025880 overlay sprite blit in the attract screens.
; DOS symbol: sub_00025880
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: draws the authored COMA/ZOVE overlay through its selected RGB565 palette.
; Preserved: frame, position, palette remap, and clipping.
; Kind: adapted - platform surface port.
; Status: ported; overlay covered by the full attract capture.
attract_overlay
        movem.l d0-d3/a0-a1,-(sp)
        move.l  #attract_spal,sprite_palette
        move.l  work_screen,a0
        jsr     sprite_draw_opaque
        move.l  #flight_palette,sprite_palette
        movem.l (sp)+,d0-d3/a0-a1
        rts

; ---------------------------------------------------------------------------
; Expressing a sprite bank in the screen's palette.
;
; A bank's own palette never reaches the DAC. What 0002B8C5 does instead is
; build a 256-entry translation table from it to the installed palette
; (0002B949, nearest colour per entry through 0002B820) and then rewrite the
; bank's whole pixel payload through that table in place - 0002B9BA, two
; bytes at a time to the end of the data. Only then does the blitter's plain
; `rep movsb` land in the right colours.
;
; ZOVE.RLE hardly needs it: its palette is RH66SIDE.DTA's own, divided by
; four, so 227 of its 256 entries translate to themselves. COMA.RLE is
; authored against something else entirely - 4 of 256 entries land within
; four units of TPIC's - and drawn untranslated the Comanche comes out as
; coloured noise with the shape of a helicopter in it.
;
; This port composes the two tables instead of rewriting the payload: one
; RGB565 entry per bank index, already looked up through the screen palette.
; Same pixels on screen, and COMA.RLE stays intact for the cockpit that also
; reads it.
;
; The metric is the original's exactly. Distance is the sum over channels of
; (weight * difference) squared, weights 30, 55 and 15, computed in six-bit
; DAC space with red and green passed through the 0002B7D0 ramp and blue
; doubled. Candidates are searched 1..254 in order, the first minimum wins,
; and an exact match stops the search; indices 0 and 255 are not searched for
; and pass through as themselves.
;
; In: a1 = bank
; DOS: flat 0002B820-0002B89D, weighted nearest-colour bank remap.
; DOS symbol: sub_0002B820
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: maps authored bank indices into the active Falcon screen palette.
; Preserved: channel weights, candidate search, and index rewrite semantics.
; Kind: translated.
; Status: ported; palette remap covered by the full attract capture.
attract_bank_remap
        movem.l d0-d7/a0-a6,-(sp)
        bsr     attract_build_weights

        ; The bank's palette sits behind the 0x0C marker its header points at.
        moveq   #0,d0
        move.b  7(a1),d0
        lsl.l   #8,d0
        move.b  6(a1),d0
        lsl.l   #8,d0
        move.b  5(a1),d0
        lsl.l   #8,d0
        move.b  4(a1),d0
        lea     0(a1,d0.l),a0
        cmpi.b  #$0C,(a0)+
        bne     .identity

        lea     attract_spal,a6
        lea     attract_gamma,a4
        lea     attract_weights,a5
        move.w  attract_pal,(a6)+               ; index 0 is never searched
        addq.l  #3,a0                           ; and never read, either
        moveq   #1,d7
.entry
        moveq   #0,d0
        move.b  (a0)+,d0
        andi.w  #63,d0
        moveq   #0,d4
        move.b  0(a4,d0.w),d4                   ; key red
        moveq   #0,d0
        move.b  (a0)+,d0
        andi.w  #63,d0
        moveq   #0,d5
        move.b  0(a4,d0.w),d5                   ; key green
        moveq   #0,d6
        move.b  (a0)+,d6
        andi.w  #63,d6
        add.w   d6,d6                           ; key blue

        lea     attract_cand+8,a1               ; candidates 1..254
        moveq   #-1,d2                          ; no best yet
        move.w  attract_pal,d1
.cand
        moveq   #0,d0
        move.b  (a1),d0
        sub.w   d4,d0
        bpl     .red_abs
        neg.w   d0
.red_abs
        add.w   d0,d0
        add.w   d0,d0
        move.l  0(a5,d0.w),d3
        moveq   #0,d0
        move.b  1(a1),d0
        sub.w   d5,d0
        bpl     .green_abs
        neg.w   d0
.green_abs
        add.w   d0,d0
        add.w   d0,d0
        add.l   WEIGHT_G(a5,d0.w),d3
        moveq   #0,d0
        move.b  2(a1),d0
        sub.w   d6,d0
        bpl     .blue_abs
        neg.w   d0
.blue_abs
        add.w   d0,d0
        add.w   d0,d0
        add.l   WEIGHT_B(a5,d0.w),d3
        cmp.l   d2,d3
        bcc     .next_cand
        move.l  d3,d2
        move.w  4(a1),d1
        tst.l   d3
        beq     .have                           ; exact: the search stops
.next_cand
        lea     8(a1),a1
        cmpa.l  #attract_cand+255*8,a1
        blo     .cand
.have
        move.w  d1,(a6)+
        addq.w  #1,d7
        cmpi.w  #255,d7
        blo     .entry
        move.w  attract_pal+2*255,(a6)          ; index 255, likewise reserved
        bra     .out

.identity
        ; No palette in the bank: draw it through the screen's own table, which
        ; is what the port did before this was recovered.
        lea     attract_pal,a0
        lea     attract_spal,a1
        move.w  #255,d0
.copy
        move.w  (a0)+,(a1)+
        dbra    d0,.copy
.out
        movem.l (sp)+,d0-d7/a0-a6
        rts

; The three squared-difference tables 0002ABD0/0002AFD0/0002B3D0 hold, built
; once rather than carried as three kilobytes of constants. Differences are
; bounded by 127 because every key channel is, so half of each original table
; - the wrapped negative half - is never reached.
; DOS: flat 0002ABD0/0002AFD0/0002B3D0, squared colour tables.
; DOS symbol: none - the cited addresses are data
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: builds the exact weighted channel-difference lookup tables.
; Preserved: RGB weights, wrapped byte differences, and square arithmetic.
; Kind: translated.
; Status: ported; covered by palette remap review.
attract_build_weights
        movem.l d0-d1/a0-a2,-(sp)
        tst.w   attract_w_ready
        bne     .out
        move.w  #1,attract_w_ready
        lea     attract_weights,a0
        lea     WEIGHT_G(a0),a1
        lea     WEIGHT_B(a0),a2
        moveq   #0,d0
.step
        move.w  d0,d1
        mulu.w  #30,d1
        mulu.l  d1,d1
        move.l  d1,(a0)+
        move.w  d0,d1
        mulu.w  #55,d1
        mulu.l  d1,d1
        move.l  d1,(a1)+
        move.w  d0,d1
        mulu.w  #15,d1
        mulu.l  d1,d1
        move.l  d1,(a2)+
        addq.w  #1,d0
        cmpi.w  #WEIGHT_SPAN,d0
        blo     .step
.out
        movem.l (sp)+,d0-d1/a0-a2
        rts

; Swap and publish, the main loop's flip in attract clothing.
; DOS: flat 00015B78-00015C14, page publication for attract screens.
; DOS symbol: sub_00015B78
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: copies/publishes the completed Falcon attract buffer at VBL boundary.
; Preserved: screen ownership and no-flight frame result.
; Kind: adapted - platform surface port.
; Status: ported; screen tick covered by the full attract capture.
attract_flip
        movem.l d0/a0,-(sp)
        move.l  work_screen,d0
        move.l  display_screen,work_screen
        move.l  d0,display_screen
        bsr     publish_screen
        movem.l (sp)+,d0/a0
        rts

; ---------------------------------------------------------------------------
; Kyle DTA screen images: 128-byte header (width-1, height-1 words at +8),
; RLE payload, then the 0x0C palette. Decoded once into attract_image and
; blitted as the left 320 columns of its 328-wide rows.
; ---------------------------------------------------------------------------

; In: a0 = filename. Decodes into attract_image/attract_pal and paints
; both buffers, so the per-tick flip always lands on a finished backdrop.
; Failure terminates the attract task: the DOS build has no black-screen
; substitute for a missing named resource.
; DOS: flat 00005690-00005AE3 authored screen loader/painter.
; DOS symbol: loc_00005690
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: loads a named original DTA image into the attract image buffer.
; Preserved: dimensions, source rows, palette, and failure-to-draw behavior.
; Kind: translated.
; Status: ported; image loader covered by the full attract capture.
attract_show_image
        movem.l d0-d7/a0-a6,-(sp)
        clr.w   attract_img_ok

        move.w  #0,-(sp)
        move.l  a0,-(sp)
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .painted
        move.w  d0,d7

        pea     resource_buffer
        move.l  #RESOURCE_BUFFER_BYTES,-(sp)
        move.w  d7,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d6

        move.w  d7,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp

        moveq   #0,d0
        cmpi.l  #128,d6
        ble     .painted

        lea     resource_buffer,a0
        moveq   #0,d4
        move.b  9(a0),d4                        ; width-1, little-endian
        lsl.w   #8,d4
        move.b  8(a0),d4
        addq.w  #1,d4                           ; width
        moveq   #0,d5
        move.b  11(a0),d5
        lsl.w   #8,d5
        move.b  10(a0),d5
        addq.w  #1,d5                           ; height
        move.w  d4,attract_img_w
        move.w  d5,attract_img_h
        mulu.w  d4,d5                           ; payload bytes
        move.l  d5,attract_img_len
        cmpi.l  #ATTRACT_IMAGE_BYTES,d5
        bhi     .painted

        ; RLE: token < $C0 literal; else a run of (token & $3F) copies.
        lea     128(a0),a0
        lea     resource_buffer,a1
        adda.l  d6,a1                           ; end of file
        lea     attract_image,a2
        move.l  d5,d3                           ; bytes wanted
.unpack
        tst.l   d3
        ble     .palette
        cmp.l   a1,a0
        bge     .painted
        moveq   #0,d0
        move.b  (a0)+,d0
        cmpi.b  #$C0,d0
        bcc     .run
        move.b  d0,(a2)+
        subq.l  #1,d3
        bra     .unpack
.run
        andi.w  #$3F,d0
        beq     .unpack
        move.b  (a0)+,d1
        sub.l   d0,d3
        subq.w  #1,d0
.runfill
        move.b  d1,(a2)+
        dbra    d0,.runfill
        bra     .unpack

.palette
        ; The palette is $0C then 256 RGB triples, and it is NOT part of the
        ; run-length stream: it sits raw in the last 769 bytes of the file.
        ; Unpacking it as RLE - which this did, and tools/render-attract-ref.py
        ; did identically, which is why they agreed - expands every component
        ; of $C0 or more into a run and shifts the whole table down from there.
        ; BACK.DTA's first such byte is in entry 1, so its entire palette was
        ; wrong and its logo came out in horizontal bands; TPIC's is in entry
        ; 179 and RH66SIDE's in 225, so those corrupted only their high indices
        ; and looked close enough to pass. Measured against a frame the game
        ; drew of itself: reading the tail raw reproduces COMANCHE.EXE's own
        ; screen at 0 differing pixels of 76,800.
        ;
        ; The components are EIGHT bits, not the VGA DAC's six - CONSOL1S.DTA
        ; reaches 252 and TPIC 188 - which is how console.s already reads the
        ; same field.
        lea     resource_buffer,a0
        adda.l  d6,a0                           ; end of file
        suba.l  #769,a0                         ; the $0C marker
        cmpi.b  #$0C,(a0)+
        bne     .painted
        lea     attract_pal,a2
        lea     attract_cand,a3
        lea     attract_gamma,a4
        move.w  #255,d3
.pal
        moveq   #0,d0
        move.b  (a0)+,d0                        ; red
        moveq   #0,d1
        move.b  (a0)+,d1                        ; green
        moveq   #0,d2
        move.b  (a0)+,d2                        ; blue

        move.w  d0,d5
        lsr.w   #3,d5
        lsl.w   #6,d5                           ; red 5 bits at 11
        move.w  d1,d6
        lsr.w   #2,d6
        add.w   d6,d5
        lsl.w   #5,d5                           ; green 6 bits at 5
        move.w  d2,d6
        lsr.w   #3,d6
        add.w   d6,d5
        move.w  d5,(a2)+

        ; The same entry in the space 0002B820 matches colours in: the DAC's
        ; six bits, red and green through the 64-entry ramp at 0002B7D0 and
        ; blue simply doubled. Kept beside the RGB565 word so the search
        ; below walks one array.
        lsr.w   #2,d0
        lsr.w   #2,d1
        lsr.w   #2,d2
        move.b  0(a4,d0.w),(a3)
        move.b  0(a4,d1.w),1(a3)
        add.w   d2,d2
        move.b  d2,2(a3)
        move.w  d5,4(a3)
        lea     8(a3),a3

        dbra    d3,.pal
        move.w  #1,attract_img_ok

.painted
        tst.w   attract_img_ok
        bne     .image_ok
        move.w  #1,exit_requested
        clr.w   attract_active
        movem.l (sp)+,d0-d7/a0-a6
        rts
.image_ok
        bsr     attract_pan_clear
        moveq   #0,d0
        bsr     attract_pan_blit
        bsr     attract_paint
        bsr     attract_flip
        bsr     attract_pan_clear
        moveq   #0,d0
        bsr     attract_pan_blit
        bsr     attract_paint
        movem.l (sp)+,d0-d7/a0-a6
        rts

; Clear the destination before a valid full-screen image is copied. This is
; only the destination preparation; missing images return before this routine
; is used as a substitute.
; DOS: flat 00005A79 CRTC-pan background transfer.
; DOS symbol: loc_00005A79
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: clears the Falcon back buffer region before the authored pan blit.
; Preserved: pan row and source/destination ordering; CRTC addressing is replaced.
; Kind: adapted - platform surface port.
; Status: ported; pan clear covered by the full attract capture.
attract_pan_clear
        movem.l d0-d1/a0,-(sp)
        move.l  work_screen,a0
        move.w  #SCREEN_WIDTH*SCREEN_HEIGHT/2-1,d0
        moveq   #0,d1
.clr
        move.l  d1,(a0)+
        dbra    d0,.clr
        movem.l (sp)+,d0-d1/a0
        rts

; Blit the 240 view rows of the decoded image from image row d0. The stored
; pitch is the image's own width - 328 for every screen the cycle shows -
; and the view is its left 320 columns, the DOS window into the Mode X page.
; DOS: flat 00005A79-00005AD6 TPIC row-pan transfer.
; DOS symbol: loc_00005A79
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: re-blits the authored TPIC image at the recovered pan row.
; Preserved: row clamp, image origin, and overlay timing.
; Kind: adapted - platform surface port.
; Status: ported; panned image covered by the full attract capture.
attract_pan_blit
        movem.l d0-d7/a0-a2,-(sp)
        tst.w   attract_img_ok
        beq     .done
        move.w  attract_img_h,d1
        sub.w   #SCREEN_HEIGHT,d1
        bpl     .have_range
        moveq   #0,d1
.have_range
        cmp.w   d1,d0                           ; clamp the pan to the art
        ble     .row_ok
        move.w  d1,d0
.row_ok
        lea     attract_image,a0
        moveq   #0,d1
        move.w  attract_img_w,d1
        mulu.w  d0,d1
        adda.l  d1,a0
        moveq   #0,d6
        move.w  attract_blit_x,d6               ; the window's first page column
        adda.l  d6,a0
        move.l  work_screen,a1
        lea     attract_pal,a2
        moveq   #0,d5
        move.w  attract_img_w,d5
        subi.w  #SCREEN_WIDTH,d5                ; source bytes past the view
        move.w  #SCREEN_HEIGHT-1,d3
.row
        move.w  #SCREEN_WIDTH/4-1,d4
.px
    rept 4
        moveq   #0,d6
        move.b  (a0)+,d6
        add.w   d6,d6
        move.w  0(a2,d6.w),(a1)+
    endr
        dbra    d4,.px
        adda.w  d5,a0
        dbra    d3,.row
.done
        movem.l (sp)+,d0-d7/a0-a2
        rts

; The side screen leads straight into its demo; so does the title.
; DOS: flat 00005690 plus 00018CBC, demo selection at pass completion.
; DOS symbol: loc_00005690
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: selects the authored mission family/sky and DEMO<N>.SCR replay.
; Preserved: pass-to-file mapping, start state, and one-record-per-frame feed.
; Kind: translated.
; Status: ported, and the pass-to-mission mapping is now MEASURED against the
;   original rather than argued. 0002913C fills the active mission's resource
;   names through a table of 21 pointers at 0x2A320; dumping them out of the
;   running game at its first attract replay gives
;   "Np44.dta d4.dta c4.dta sky4.rle". Replaying this port's own walk over
;   0.MIS - mission_find_delimiter counting three '<' per prior record -
;   mission_select(1) yields exactly that list, capital N included, while
;   mission_select(0) yields p12/d1/c1/sky2.
;
;   So the first attract pass flies mission ONE, and attract_next_pass's
;   pre-increment is what makes that happen: attract_pass starts at 0 in BSS
;   and is incremented BEFORE it is copied to attract_demo_pass. Had it been
;   read before incrementing, the attract would fly D1 under a sky2 palette -
;   a different landscape entirely, and the kind of difference that looks
;   like a renderer fault. work/dump_marcher_tables.py prints the resource
;   names on every capture so this stays checked rather than remembered.
attract_start_demo
        movem.l d0-d7,-(sp)
        ; 00005AE3-00005B35 on the way to a demo: [00019DF0] to the music
        ; driver, MODE(0), RESET, then (the menu being skipped in the attract)
        ; MODE(0) again.
        jsr     music_resend                    ; 00005AE3-00005AE9
        moveq   #0,d0
        jsr     snd_mode                        ; 00005AF0
        jsr     snd_reset                       ; 00005B24
        moveq   #0,d0
        jsr     snd_mode                        ; 00005B35
        ; The DOS attract pass selects mission N before opening DEMO<N>.SCR.
        ; Recover the selected resource list, then load its real D/C pair,
        ; palette and sky before feeding the recorded flight inputs.
        move.w  attract_demo_pass,d7

        ; 0002A1BB and 0002904D both force the campaign index to 0 while
        ; [00019ED4] is set, which is the whole time the attract owns the
        ; machine - so the demo passes fly the first catalog entry's missions,
        ; never the campaign the player was last looking at. That case is real
        ; here: backing out of the mission screen leaves that campaign's stream
        ; in the buffer and the next attract pass would fly it.
        moveq   #0,d0
        jsr     screen_select_campaign

        move.w  d7,d0
        bsr     mission_select
        move.w  mission_status,d0
        btst    #1,d0
        bne     .asset_bad
        btst    #2,d0
        beq     .asset_bad
        move.w  mission_map_family,d0
        jsr     resources_select_family
        tst.w   resource_map_status
        bne     .asset_bad
        move.w  mission_sky_number,d0
        beq     .asset_bad
        jsr     sky_select_family
        tst.w   sky_status
        bne     .asset_bad
        ; The traced attract route reaches the same authored factory pass as
        ; the DOS flight frame: 000068A5-00006947 resolves f2/f3 through the
        ; selected mission's ten SG slots and installs the object handlers
        ; before DEMO<n> starts. This is not a synthetic foreground object;
        ; object_spawn_mission consumes only parsed placement records, and the
        ; route witness includes the factory, callback and effect entries.
        bsr     object_init
        jsr     sprite_mission_load
        bsr     weapon_banks_load               ; 000066E2-000067AE
        jsr     flight_mission_sound_load       ; 0000688B, 000064A8, 0000681D, 00006859
        bsr     object_spawn_mission
        move.w  attract_demo_pass,d0
        bsr     demo_start
        tst.l   d0
        bne     .asset_bad
        jsr     flight_mission_sound_start      ; 000069DB-00006A0E, once the first frame is set up

        ; The screen compositor has painted both persistent surfaces with
        ; TPIC/RH66SIDE. Before the first replay terrain frame, seed each
        ; target from the active ground entry and rebuild its backdrop. This
        ; is required for the CPU build as well as DSP: a screen-history pixel
        ; must never survive into the terrain band while the marcher fills it.
        move.l  work_screen,a0
        bsr     render_reset_surface
        move.l  display_screen,a0
        bsr     render_reset_surface

    ifne USE_DSP
        ; The original selects the mission resource block before its first
        ; flight tick. The DSP scene cache is a Falcon replacement for the
        ; DOS renderer's direct map reads, so it must be rebound at this same
        ; boundary; otherwise a later pass would march the previous mission's
        ; far tiles while the CPU path sampled the selected map.
        bsr     dsp_init
        tst.l   d0
        bne     .asset_bad
    endc
.ok
        clr.w   attract_screen                  ; AT_NONE: flight frames now
    ifne USE_DSP
        ; The screens painted over both persistent buffers; the solid
        ; console and the histories are stale. Heal one frame per buffer,
        ; console included.
        move.w  #2,surface_reseed
    endc
.out
        movem.l (sp)+,d0-d7
        rts
.asset_bad
        bsr     attract_stop
        bra     .out

        data
name_back
        dc.b    "BACK.DTA",0
name_tpic
        dc.b    "TPIC.DTA",0
name_rh66
        dc.b    "RH66SIDE.DTA",0
        even
name_zove
        dc.b    "ZOVE.RLE",0
        even
; The ZOVE cycle at 00028E75, the COMA nine-view walk at 000059C8, the
; 64-entry pan wobble at 00005985 and the red/green matching ramp 0002B820
; puts colours through, 0002B7D0 (six-bit in, 0..127 out, slightly convex):
; data of the original, filled from the player's COMANCHE.EXE at startup by
; src/origexe.s into storage at the end of this file. Each animation table is
; terminated by a zero the original wraps on; the counts are the entries
; before it.
; Attract screen states.
AT_NONE         = 0
AT_SIDE         = 1
AT_FANFARE      = 2
AT_TITLE        = 3

; The overlay placements the original self-modifies into its blitter, and
; the pan limits, all in the units 00005690 keeps them in.
ZOVE_X          = $AF                           ; 00005776
ZOVE_Y          = $4B                           ; 00005780
COMA_X          = $A0                           ; 000059ED
TITLE_HELI_TOP  = $5D                           ; 0000592A and 00005A40
TITLE_HELI_LOW  = $F8                           ; 00005A47
TITLE_GATE_ROW  = 93                            ; 0x1DCA / 0x52
TITLE_PAN_LAST  = 150                           ; 0x300C / 0x52

; The colour-match tables: one span per channel, the green and blue spans
; offset from the red one so a single base register reaches all three.
WEIGHT_SPAN     = 128
WEIGHT_G        = WEIGHT_SPAN*4
WEIGHT_B        = WEIGHT_SPAN*8

        bss
        even
        global  zove_frames, coma_frames, pan_wobble, attract_gamma
zove_frames
        ds.b    6
coma_frames
        ds.b    36
pan_wobble
        ds.b    64
attract_gamma
        ds.b    64
        even
        even
attract_active
        ds.w    1
; The page column the displayed window starts at: 0 for the attract's own
; screens, 4 for the menu chain's, whose pages the CRTC starts one byte in.
attract_blit_x
        ds.w    1
attract_screen
        ds.w    1
attract_pass
        ds.w    1
attract_demo_pass
        ds.w    1
attract_timer
        ds.w    1
; 1 while the RAH-66 Overview runs the side screen without its count.
attract_untimed
        ds.w    1
attract_anim
        ds.w    1
attract_pan
        ds.w    1
attract_heli
        ds.w    1
attract_step
        ds.w    1
attract_wob
        ds.w    1
attract_img_ok
        ds.w    1
attract_img_len
        ds.l    1
attract_img_w
        ds.w    1
attract_img_h
        ds.w    1
attract_bank_bad
        ds.w    1
        even
; The largest screen is TPIC's 328x390, plus the in-stream palette and a
; run's worth of decoder slack.
ATTRACT_IMAGE_BYTES = 328*390+769+64
attract_image
        ds.b    ATTRACT_IMAGE_BYTES
        even
attract_pal
        ds.w    256
; The bank's indices as screen colours - what attract_bank_remap builds and
; every overlay draws through.
attract_spal
        ds.w    256
; The screen palette in the form the colour search wants: match key in the
; first three bytes, the RGB565 word at +4, eight bytes apart so one pointer
; walks it.
attract_cand
        ds.b    256*8
attract_w_ready
        ds.w    1
        even
attract_weights
        ds.l    WEIGHT_SPAN*3
attract_bank
        ds.b    168000
        even

        end
