; Route: analysis/functions/falcon-attract.md#replay-flight.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; Small local flight state used by the CPU reference scene. This is the
; platform-independent boundary the later mission/resource systems can grow
; around; no sound or networking is involved in this first loop.

        include "inc/comanche.s"

        global  game_init, game_tick
        xref    object_launch_flare, object_launch_chaff, weapon_fire_rocket
        xref    flight_menu_silence, flight_rotor
        xref    mfd_zoom, menu_settings, key_state, input_notch, key_queue, menu_bar_text
        global  player_x, player_y, player_heading, player_altitude
        global  exit_requested, input_pending
        global  game_command, console_redraw, console_start_state

        text

; DOS: flat 000290C6-00029359 (mission scalar parser) and 000063A7-000063F6,
; the mission-start block that zeroes the rates and triggers, seeds the
; console page and the speed ceiling, and calls 00015AD9.
; DOS symbol: loc_000290C6
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: copies the parsed mission start tuple into the Falcon flight boundary.
; Preserved: authored X/Y/heading; missing mission data stops instead of guessing.
; Kind: translated.
; Status: ported; full mission-start validation remains pending.
game_init
        ; The DOS mission parser supplies the initial position and heading.
        ; There is no authored universal (64,160,200) start in the game, so a
        ; missing mission is an error and never becomes a synthetic flight.
        move.w  mission_status,d0
        btst    #2,d0                         ; MISSION_STATUS_PARSED
        bne     .mission_start
        move.w  #1,exit_requested
        rts
.mission_start
        move.l  mission_start_x,player_x
        move.l  mission_start_y,player_y
        move.w  mission_start_heading,player_heading
        clr.b   player_altitude                ; DEMO playback overwrites this
        ; Seed the flight integration from the same start: 16.16 up to its
        ; 10.22, the port heading back onto the DOS 512-step angle.
        move.l  player_x,d0
        asl.l   #6,d0
        move.l  d0,flt_x
        move.l  player_y,d0
        asl.l   #6,d0
        move.l  d0,flt_y
        moveq   #0,d0
        move.w  player_heading,d0
        neg.w   d0
        addi.w  #128,d0
        andi.w  #$00ff,d0
        moveq   #24,d1
        asl.l   d1,d0
        move.l  d0,flt_angle
        bsr     flight_reset
        bsr     console_start_state
        move.b  #1,mission_flown                ; 00006A05 [00019D91] = 1
        clr.w   exit_requested
        clr.w   input_held
        clr.w   input_pending
        rts

; The three console selector bytes mission start seeds, in one place because
; both flight entries need them and DOS writes them as one run.
;
; The page bytes are NOT the values the image ships at 0x72E6/0x72E7 (0 and
; 1). Mission start overwrites them, so the right MFD comes up on page 2 -
; the target view - not page 1. That is measured rather than deduced: a
; capture of the original at its first attract replay reads [0x72E7] = 2 with
; the previous-page byte AND the dirty flag both still 0, and the function-key
; chain at 000195B1 sets both of those, so the key path cannot be what put it
; there. 000063C9 is the only other writer.
;
; This has to run on the attract path as well as the real-flight one. The
; port previously seeded [00019D88] inside game_init, which only screen.s
; reaches; the attract enters through demo_start and so never saw it.
; DOS: flat 000063BB-000063C9, the mission-start console selector seeds.
; DOS symbol: inside loc_000062xx
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: seeds the console page and both MFD pages before a flight begins.
; Preserved: all three values and the order DOS writes them in.
; Kind: translated.
; Status: ported; verified against a capture of the original's own bytes.
console_start_state
        move.b  #2,instrument_page              ; 000063BB: [00019D88] = 2
        clr.b   mfd_page_left                   ; 000063C2: [0x72E6] = 0
        move.b  #2,mfd_page_right               ; 000063C9: [0x72E7] = 2
        rts

; One in-flight command, dispatched from the record's key byte.
;
; 0001959F is a scancode chain. Two of its cases are recovered and ported
; here, and they are the two the shipped DEMO streams actually carry:
;
;   0x1A '['  00019649  dec [00019D88]; if it went negative, set 5
;   0x1B ']'  0001965E  inc [00019D88]; if it reached 6, set 0
;   both      00019674  [00019D89] = 1, then call 000073D0
;
; [00019D88] is the console page selector instruments_draw already reads as
; element = page + 7 (00007403), and [00019D89] is the redraw counter the
; frame loop decrements at 00006ABC. Until these were ported the port held
; page 2 for the whole attract while the original stepped it.
;
; The rest of the chain is not ported and is named so the gap is legible:
; 0x28/0x27 jump to the weapon paths at 00022A00/00022AA0; 0x3B-0x40 and
; 0x41-0x44/0x57/0x58 select the left and right MFD pages through
; [000072E6]/[000072E7].
;
; 0x02-0x09 are the VIEW selectors and they ARE ported, in src/view.s: they
; set [00019D86], which 00007D25 indexes into the view-angle offsets at
; [00019D94] and the camera handlers at [00007BC9]. Variants 6 and 7 move the
; camera, which is why 0000D3DE/0000D3EA push the viewpoint around the render
; at all.
;
; In: d0.b = the scancode. Out: nothing; unhandled codes are ignored, which
; is what the chain's final fall-through does.
; DOS: flat 00019645-00019680, the console page cases of the command chain.
; DOS symbol: loc_00019645
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: steps the recovered console page and flags the console for redraw.
; Preserved: both wraps, the redraw flag, and the draw call that follows.
; Kind: translated.
; Status: partial; the weapon, MFD and console-variant cases are not ported.
game_command
        ; 0001959F/000195A8: ' and ; drop a flare and a chaff cloud by hand, the
        ; two launchers countermeasure_tick also reaches.
        cmpi.b  #$28,d0
        bne.s   .not_flare
        jmp     object_launch_flare             ; 000195A3 jmp 00022A00
.not_flare
        cmpi.b  #$27,d0
        bne.s   .not_chaff
        jmp     object_launch_chaff             ; 000195AC jmp 00022AA0
.not_chaff
        cmpi.b  #$1a,d0
        bne     .not_page_down
        subq.b  #1,instrument_page              ; 00019649
        bpl     .page_done                      ; 0001964F jns
        move.b  #5,instrument_page              ; 00019651
        bra     .page_done
.not_page_down
        cmpi.b  #$1b,d0
        bne     .not_page_up
        addq.b  #1,instrument_page              ; 0001965E
        cmpi.b  #6,instrument_page
        bcs     .page_done                      ; 0001966B jb
        clr.b   instrument_page                 ; 0001966D
.page_done
        move.b  #1,console_redraw               ; 00019674
        bra     .done

        ; The twelve function keys, which the shipped DEMO streams do carry:
        ; the captured original had F9 lit on the right MFD, which is page 2,
        ; and it can only have got there from this chain.
        ;
        ; Both cases do the same three things - push the current page down to
        ; the previous slot, take the new one, and redraw the labels - and the
        ; previous slot is not bookkeeping: 000072EB draws the OLD page's
        ; label un-highlighted and the new one highlighted, so without it the
        ; old highlight is never cleared.
        ;
        ; DOS spells the codes out as a compare chain. F1-F6 are contiguous so
        ; a range test is the same function of the input; F7-F12 are NOT
        ; (0x41-0x44, then 0x57 and 0x58 for F11/F12), and those two are
        ; tested separately exactly as 00019635/0001963D do.
.not_page_up
        ; 0001959F's view cases, 0x02..0x09 - the '1'..'8' keys. They select
        ; the view variant [00019D86], which 00007D25 turns into the frame's
        ; whole camera. The shipped DEMO streams use them: DEMO1 sends 0x07 at
        ; record 30, 0x08 at 206 and 0x02 at 357.
        move.b  d0,d1
        subi.b  #2,d1
        cmpi.b  #7,d1
        bhi     .not_view
        jsr     view_select
        rts
.not_view
        movem.l d1-d2,-(sp)

        move.b  d0,d1                           ; 000195B1: F1-F6, left MFD
        subi.b  #$3b,d1
        cmpi.b  #6,d1
        bcc     .not_left
        move.b  mfd_page_left,d2
        move.b  d2,mfd_page_left_prev           ; 000195BC
        move.b  d1,mfd_page_left                ; 000195C1
        bra     .mfd_selected
.not_left
        move.b  d0,d1                           ; 000195FB: F7-F10
        subi.b  #$41,d1
        cmpi.b  #4,d1
        bcs     .right
        cmpi.b  #$57,d0                         ; 00019635: F11
        bne     .not_f11
        moveq   #4,d1
        bra     .right
.not_f11
        cmpi.b  #$58,d0                         ; 0001963D: F12
        bne     .mfd_none
        moveq   #5,d1
.right
        move.b  mfd_page_right,d2
        move.b  d2,mfd_page_right_prev          ; 00019606
        move.b  d1,mfd_page_right               ; 0001960B
.mfd_selected
        move.b  #1,mfd_page_dirty               ; 000195C7 / 00019611
        movem.l (sp)+,d1-d2
        jsr     mfd_draw_labels                 ; 000195CE / 00019617 -> 0x72EB
        rts
.mfd_none
        movem.l (sp)+,d1-d2
        bra     game_command_keys
.done
        rts

; The keyboard half of the command chain, 00019AFF-00019C88: what the flying
; keys do when they are not the replay's. Two layouts, picked by the
; ThrustMaster WCS option [00025DDD] - the default one first.
;
;   Q A  left / right MFD page down (not while Alt is held: Alt+Q quits)
;   W S  left / right MFD page up
;   Z X C V B N  weapon page 0-5 (the gun, rockets, Hellfire, Stinger, bomb,
;        wingman) through [00019D88], and the console redraws
;   M    two rockets at once (00022B00 twice)
;
; and with the option on, the WCS's own buttons: B W R T C F for the six
; weapon pages, and S / M / G the map zoom presets 0x10000000, 0x8000000 and
; 0x4000000. 0x1E there also clears [00019D85].
; In: d0.b = the scancode. Out: nothing; unmatched codes are ignored.
; DOS: flat 00019AFF-00019C88.
; DOS symbol: loc_00019AFF
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: the same comparisons in the same order.
; Preserved: the Alt gate, the page wraps, both layouts, the zoom presets.
; Not carried: 000199B0-00019AFE - I, U and O record, replay and save a flight
;   as DEMO1.SCR (a development feature, reached only while [000265ED] is not
;   0xFF) - and 0x24's joystick calibration, which has no keyboard device.
; Kind: translated.
; Status: ported; Unproven against a keyboard-driven DOS run.
game_command_keys
        movem.l d1-d2,-(sp)
        cmpi.b  #'}',menu_settings+9            ; 00019AFF [00025DDD]
        beq     .wcs

        tst.b   key_state+KEY_ALT               ; 00019B0C [00001AA8]
        bpl     .not_qa                         ; held reads non-negative
        cmpi.b  #$10,d0                         ; Q
        bne.s   .not_q
        moveq   #0,d1
        move.b  mfd_page_left,d1
        subq.b  #1,d1
        bpl   .left_pick
        moveq   #5,d1
        bra   .left_pick
.not_q
        cmpi.b  #$1e,d0                         ; A
        bne.s   .not_qa
        moveq   #0,d1
        move.b  mfd_page_right,d1
        subq.b  #1,d1
        bpl   .right_pick
        moveq   #5,d1
        bra   .right_pick
.not_qa
        cmpi.b  #$11,d0                         ; W
        bne.s   .not_w
        moveq   #0,d1
        move.b  mfd_page_left,d1
        addq.b  #1,d1
        cmpi.b  #5,d1
        bls   .left_pick
        moveq   #0,d1
        bra   .left_pick
.not_w
        cmpi.b  #$1f,d0                         ; S
        bne.s   .not_s
        moveq   #0,d1
        move.b  mfd_page_right,d1
        addq.b  #1,d1
        cmpi.b  #5,d1
        bls   .right_pick
        moveq   #0,d1
        bra   .right_pick
.not_s
        move.b  d0,d1
        subi.b  #$2c,d1                         ; Z..N = 0x2C..0x31
        cmpi.b  #6,d1
        bcc.s   .not_page
        move.b  d1,instrument_page
        move.b  #1,console_redraw               ; 00019674
        bra     .out
.not_page
        cmpi.b  #$32,d0                         ; M
        bne     .out
        movem.l d0-d7/a0-a6,-(sp)
        jsr     weapon_fire_rocket              ; 00019BE3
        jsr     weapon_fire_rocket              ; 00019BE8
        movem.l (sp)+,d0-d7/a0-a6
        bra     .out

.wcs
        cmpi.b  #$1e,d0                         ; 00019BEF
        bne.s   .wcs_b
        clr.b   input_notch                     ; [00019D85] = 0
.wcs_b
        moveq   #0,d1
        cmpi.b  #$30,d0                         ; B
        beq.s   .wcs_page
        moveq   #1,d1
        cmpi.b  #$11,d0                         ; W
        beq.s   .wcs_page
        moveq   #2,d1
        cmpi.b  #$13,d0                         ; R
        beq.s   .wcs_page
        moveq   #3,d1
        cmpi.b  #$14,d0                         ; T
        beq.s   .wcs_page
        moveq   #4,d1
        cmpi.b  #$2e,d0                         ; C
        beq.s   .wcs_page
        moveq   #5,d1
        cmpi.b  #$21,d0                         ; F
        beq.s   .wcs_page
        cmpi.b  #$1f,d0                         ; S
        bne.s   .wcs_not_s
        move.l  #$10000000,mfd_zoom            ; 00019C5E
.wcs_not_s
        cmpi.b  #$32,d0                         ; M
        bne.s   .wcs_not_m
        move.l  #$08000000,mfd_zoom            ; 00019C6C
.wcs_not_m
        cmpi.b  #$22,d0                         ; G
        bne     .out
        move.l  #$04000000,mfd_zoom            ; 00019C7A
        bra     .out
.wcs_page
        move.b  d1,instrument_page
        move.b  #1,console_redraw
        bra     .out

.left_pick
        move.b  mfd_page_left,mfd_page_left_prev        ; 000195B7-000195C1
        move.b  d1,mfd_page_left
        bra   .picked
.right_pick
        move.b  mfd_page_right,mfd_page_right_prev      ; 00019601-0001960B
        move.b  d1,mfd_page_right
.picked
        move.b  #1,mfd_page_dirty
        movem.l (sp)+,d1-d2
        jmp     mfd_draw_labels                 ; 000195CE / 00019617 -> 0x72EB
.out
        movem.l (sp)+,d1-d2
        rts

; DOS: flat 00018D20 -> 00018F94, per-frame input/demo dispatch and flight call.
; DOS symbol: sub_00018D20
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: consumes one replay record or stops the unrecovered live-control path.
; Preserved: one input/integration tick per frame and post-render input order.
; Kind: translated.
; Status: partial; joystick semantics and weapon dispatch remain unrecovered.
game_tick
        ; DOS calls the input/demo handler once from the frame driver. The
        ; outer loop then waits for one retrace, so one rendered frame consumes
        ; one recorded input record and one flight integration. VBL pacing is
        ; not a simulation multiplier: doing catch-up integrations here makes
        ; a slow Falcon fly a different demo.
        ; The independent Timer C adapter advances shake; never advance the
        ; PIT state from rendered frames (browser-attract.md#shake-timer).

        tst.w   demo_active
        beq     .keyboard
        bsr     demo_tick
        bsr     flight_tick
        bra     .integrated

.keyboard
        bsr     input_poll

        ; Read the event word into a register before testing it. btst on a
        ; memory operand addresses a BYTE, and the byte at a word's address is
        ; the high one on a 68k, so `btst #0,input_events` tests bit 8. Bits
        ; 12-15 happen to survive that because they land in the high byte -
        ; which is worse than failing, since it makes the four direction bits
        ; look like the odd ones out rather than the rule.
        move.w  input_events,d1

        ; Escape opens and closes the options bar. The bar's own "Return to
        ; Game Esc" line says so, and 00027DD2's redraw loop is what the
        ; original sits in while it is up.
        ; The Game column's two boxes (00026DF8, 00026E81) wait for any key and
        ; hand the bar back as it was.
        tst.w   menu_message
        beq.s   .no_message
        tst.w   d1
        beq     .integrated
        clr.w   menu_message
        bra     .integrated
.no_message
        btst    #14,d1
        beq     .no_toggle
        eori.w  #1,menu_open
        ; Esc is handler 00019988: it calls the bar (00025DEF) - which silences
        ; slot 2 as it opens (00025DFD) - and, when the bar returns, the rotor
        ; switch (0001999D).
        tst.w   menu_open
        beq     .bar_closed
        jsr     flight_menu_silence
        bra     .no_toggle
.bar_closed
        jsr     flight_rotor
.no_toggle

        ; While the bar is up the original is inside that redraw loop and the
        ; flight handler is not being called at all, so the machine holds its
        ; state instead of flying on under the panel. Navigation steps on key
        ; edges; menu_confirm acts on the selector menu_nav has moved to.
        tst.w   menu_open
        beq     .live_flight

        ; 00026012-0002603F: with Backspace down, the four makes K Y L E in the
        ; queue (0x25152612) show or hide the Cheat column. The feature byte
        ; [000265ED] IS the 'C' of the bar's "Cheat" - 0xFF ends the bar's
        ; text there, 0x43 spells the word - and 00026005 clears the queue's
        ; low byte on the redraw so the chord is taken once.
        tst.b   key_state+$0E                   ; held reads non-negative
        bmi.s   .no_kyle
        cmpi.l  #$25152612,key_queue
        bne.s   .no_kyle
        lea     menu_bar_text+$2D,a0
        cmpi.b  #$FF,(a0)
        bne.s   .kyle_off
        move.b  #'C',(a0)                       ; 0002602C
        bra.s   .kyle_done
.kyle_off
        move.b  #$FF,(a0)                       ; 00026038
.kyle_done
        clr.b   key_queue+3
.no_kyle

        moveq   #0,d0
        btst    #0,d1
        bne     .nav
        moveq   #1,d0
        btst    #1,d1
        bne     .nav
        moveq   #2,d0
        btst    #2,d1
        bne     .nav
        moveq   #3,d0
        btst    #3,d1
        beq     .no_nav
.nav
        move.w  d1,-(sp)
        bsr     menu_nav
        move.w  (sp)+,d1
.no_nav
        btst    #13,d1
        beq     .integrated
        bsr     menu_confirm
        bra     .integrated

.live_flight
        ; The live path is the original's own. 00018D20 rebuilds the two axis
        ; words and the collective from the key array and falls into the same
        ; handler the replay feeds, so this differs from the branch above only
        ; in where the axes come from. The shipped COMANCHE.MNU selects
        ; control device '3' - the keyboard - which is why the keypad table at
        ; 00018E49 is the live contract and not a stand-in for a joystick.
        bsr     input_axes
        bsr     flight_tick

        ; There is no synthetic escape in the DOS live-flight handler. Mission
        ; exit is dispatched by the options bar's Abort entry at 00025DEF /
        ; 00027DD2; until that chain is recovered, Q must remain ordinary
        ; unmapped input rather than becoming a second behaviour.

.integrated
        bsr     flight_publish

        rts

        bss
        even
; Last frame's input word, so the menu steps once per press.
menu_prev_events
        ds.w    1
        even
; [00019D89]: the console redraw flag 00019674 sets and the frame loop
; consumes at 00006ABC.
console_redraw
        ds.b    1
        even
player_x
        ds.l    1
player_y
        ds.l    1
player_heading
        ds.w    1
player_altitude
        ds.b    1
        even
exit_requested
        ds.w    1

        end
