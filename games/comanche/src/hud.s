; Route: analysis/functions/falcon-attract.md#frame-driver.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; Cockpit composition over the terrain view. Everything drawn here comes from
; the original's own assets at the original's own coordinates; nothing is
; invented. It is deliberately drawn by the 68030 after terrain composition,
; leaving the DSP output contract independent of cockpit decoration.
;
; What this file used to contain, removed 2026-08-17: a placeholder HUD of
; health/fuel/heading/altitude bars, a fabricated centre reticle, horizon and
; compass ticks, a mission-status indicator, an altitude ladder, a speed strip
; and a drawn cockpit sill with canopy uprights - all at chosen coordinates in
; chosen colours, none of them recovered from COMANCHE.EXE. They were bring-up
; scaffolding that made input response visible before the real console loaded.
; The recovered flight overlay is restored below from HUDS.RLE: compass marker
; and heading window, SPEED label/digits, clearance ladder/value, centre ring,
; and the velocity sight line. The DOS tail at 0000D88C is also present: its
; current bank is COMA.RLE at [00019E90], followed by the page-gated variant
; calls at 0000D8AE.

        include "inc/comanche.s"
        include "inc/snd.s"
        ; TERRAIN_COLS / TERRAIN_VIEW_FIRST for the horizon-sheared blit.
        include "dsp/proto.inc"

        xref    resource_named_colours, object_table
        xref    flt_collective, flt_torque, flt_fuel, flt_pitch
        xref    mfd_draw_target_view
        xref    backdrop_dy
        xref    ring_mul_q31_raw, ring_maprow, MAP_COLOUR_DELTA
        xref    weapon_ammo, mission_chaff, mission_flare
        global  mfd_draw_labels
        global  mfd_page_left, mfd_page_right
        global  mfd_page_left_prev, mfd_page_right_prev, mfd_page_dirty
        global  mfd_zoom, mfd_body_offset, mfd_opaque_panel
        global  hud_draw, mfd_draw_panel, mfd_draw_map, instruments_draw, hud_draw_value
        global  hud_clearance
        global  hud_weapon, hud_console_variant, hud_console_page
        global  hud_variant_x, hud_variant_y
        global  hud_threat_clear
        global  cockpit_bank, cockpit_status, cockpit_palette
        global  instrument_palette

        text

; The instrument elements the original places at fixed positions, drawn on top
; of the console panel.
;
; Their coordinates are the original's, read off the cockpit draw code rather
; than chosen: 00007403 sets the page-2 element 0x09 at x=0x10 y=0xEA,
; 00007443 sets element 0x25 at x=0x0C y=0xC9, and 000077BE sets element 0x39
; at x=0x110 y=0xCB. Each is immediately before `call 00025880`. The startup
; path writes page 2 to [00019D88] at 000063BB, so element 0x09 is the first
; mission's recovered page selection; later page selection remains unported.
; coordinate space is the console's own - sprite_blit multiplies Y by 0x52,
; four planes of 82 bytes, which is the 328-pixel pitch CONSOL1S is stored at -
; so they land on this port's screen without conversion.
;
; Y addresses the sprite's BOTTOM edge, which is what sprite_blit already
; expects, because the DOS blitters start at Y + yoff and walk upward.
;
; Four more blits in that region take their index and position from registers -
; the gauges whose needle moves with a value - and are not placed here. Nothing
; about where those go has been recovered, and guessing would put invented
; numbers next to measured ones.
;
; The flight sight is not a CONS element. 0000D857 supplies HUDS element 0x21
; at the velocity-derived point, and 0000D887 calls 00025CA2 to draw the green
; line from the fixed centre (0xA5,0x5A) to that point.  The old attempt to use
; CONS element 0x15 here was wrong: that is a value glyph from the cockpit bank
; and produces a small red block at the lower left.
; DOS: flat 00007403-0000743D, the two page-relative console blits, and
; sub_000077A0 (000077A0-000077B8), the fixed element the frame driver
; reaches through 0000D646. The earlier citation named 00007443 and 000077BE,
; both of which are mid-instruction - inside 00007442 and 000077BD - and
; neither is an entry.
; DOS symbol: loc_00007403
; Record: analysis/functions/falcon-attract.md#frame-driver
; Difference: 00007442-0000745F draws element 1 at X = 0xC + ([00019D88] << 3)
;   through sub_00025C55, and 00007464 onward is the digit chain. Neither is
;   here; both need the page selector and the value sources that follow it.
;   000077BD-000077C7's [00019D93]/[00019D95] shuffle is carried only as the
;   sound's own flag pair, hud_threat_sound (the blip itself is not drawn).
; Port: draws the recovered page-2 element and two fixed elements from CONS.RLE,
; then the recovered velocity sight from HUDS.RLE.
; Preserved: element indices, coordinates, source offsets, and draw order.
; Kind: translated.
; Status: ported for the recovered fixed console elements; the page selector's
; own key writers (00019B83-00019BC3) and the four value-driven console gauge
; blits remain separate.
instruments_draw
        ; 00006ABC counts [00019D89] down and calls 000073D0 while it is set;
        ; the flag is cleared here because this port redraws the console every
        ; frame anyway, so the counter has nothing left to schedule. Keeping
        ; it live matters only as the record of what 00019674 sets.
        clr.b   console_redraw
        tst.w   instrument_status
        bne     .none
        movem.l d0-d3/a0-a1,-(sp)
        move.l  sprite_palette,-(sp)
        move.l  #instrument_palette,sprite_palette
        lea     instrument_bank,a1
        ; 00007403: element = [00019D88] + 7. The selector is real state, not
        ; a constant: 000063BB seeds it with 2 at mission start and the number
        ; keys at 00019B83-00019BC3 move it 0..4, with 00019651/0001966D
        ; handling 5 and the wrap. This used to be a hard `moveq #$09` - the
        ; seeded page's element, fitted rather than derived - so a selector
        ; change could not reach the draw even once its writer is ported.
        moveq   #0,d0
        move.b  instrument_page,d0
        addq.w  #7,d0
        move.w  #$10,d1
        move.w  #$ea,d2
        move.l  work_screen,a0
        jsr     sprite_draw_page_opaque

        lea     instrument_bank,a1
        moveq   #$25,d0
        move.w  #$0c,d1
        move.w  #$c9,d2
        jsr     sprite_draw_page_opaque
        move.l  work_screen,a0
        lea     instrument_bank,a1
        moveq   #$39,d0
        move.w  #$110,d1
        move.w  #$cb,d2
        jsr     sprite_draw_page_opaque
        move.l  (sp)+,sprite_palette
        bsr     hud_threat_sound                ; 000077BD-00007857, the part after the element

        ; 00007464-000074B7 and 000074C0-00007503, the value-driven readouts
        ; the console chain ends with. These are HUDS records through
        ; 00025B27, not CONS ones, so they take HUDS's palette rather than the
        ; instrument palette selected above.
        cmpi.b  #1,hud_console_variant          ; 000073D0/000074C0
        bne     .no_values

        ; 00007442-0000745F: a one-row mark through 00025C55 at
        ; 0xC + ([0x19D88] << 3), on the row 0000742F left in [0x22366]. The
        ; count is [0x22364] = 1, not an element index - 00025C83 loads that
        ; byte as its loop counter.
        moveq   #0,d0
        move.b  instrument_page,d0
        lsl.w   #3,d0
        addi.w  #$0c,d0                         ; 00007425 + 00007453
        move.w  #$c9,d1                         ; 0000742F
        moveq   #1,d2                           ; 00007442
        bsr     hud_draw_solid_column

        move.l  sprite_palette,-(sp)
        move.l  #hud_palette,sprite_palette

        ; 00007476: the live count for the selected weapon, four digits at
        ; x 0x27 walking left from row 0xD6. The index is 00007464's
        ; [0x19D88], the same page selector the element above uses, and its
        ; writers keep it in 0..5, so the original's unbounded index is not
        ; guarded here either.
        moveq   #0,d0
        move.b  instrument_page,d0
        lsl.w   #2,d0
        lea     weapon_ammo,a1
        move.l  0(a1,d0.w),d0
        move.w  #$27,d1                         ; 00007484
        move.w  #$d6,d2                         ; 0000747D
        moveq   #4,d3                           ; 0000748E ecx = 4
        bsr     hud_draw_fixed_digits

        ; 000074C9/000074F0: chaff and flare, two digits each at x 0x133.
        ; The original draws [0x19D8D]/[0x19D8E], which its countermeasure
        ; firing decrements (object_launch_chaff/object_launch_flare) and which
        ; 00026BAE also overwrites with 15/25 from a mission-script handler this
        ; port does not reach. mission_chaff/mission_flare ARE those bytes, as
        ; 000291D5/000291DF parse them, so the live count is drawn.
        move.w  mission_chaff,d0
        move.w  #$133,d1                        ; 000074D0
        move.w  #$b8,d2                         ; 000074DA
        moveq   #2,d3                           ; 00007504 ecx = 2
        bsr     hud_draw_fixed_digits
        move.w  mission_flare,d0
        move.w  #$133,d1                        ; 000074E6
        move.w  #$c1,d2                         ; 000074F7
        moveq   #2,d3
        bsr     hud_draw_fixed_digits
        move.l  (sp)+,sprite_palette
.no_values
        movem.l (sp)+,d0-d3/a0-a1
.none
        rts

; The threat warning's voice. 000077A0 ends with a walk over the object table: any
; active object 31..130 whose aux byte is set and whose last view transform lies
; inside the centre window (|lateral| < 0x14 and |-depth| < 0x0F after >> 24) sets
; [00019D93] and gets its blip drawn; the routine speaks SPEAK0 id 2 when the flag
; is up now and was not at the start of the pass.
; DOS: flat 000077BD-00007857 (the walk 000077CE-00007841, the cue 00007843-00007857).
; DOS symbol: tail of sub_000077A0
; Record: analysis/functions/sound-falcon.md#call-sites
; Port: the same test over object_table, with the flag pair kept in
;   threat_sound_now/threat_sound_prev - the sound's own copies of [00019D93]/[00019D95].
; Preserved: the walk order 130..31, the three-part active/aux/window test, the
;   strict window limits, the shuffle before the clear (000077BD-000077C7) and the
;   rising-edge cue.
; Difference: the real [00019D93] is not touched. It also drives the blip
;   (000077E8-00007836 draw it; this port does not) and the countermeasure chain
;   (object_threat_blip, 00019555), whose behaviour would change if it were
;   computed; the sound needs only the edge, so it runs on its own copy.
;   000196BE's clear of [00019D93] clears the copy too (hud_threat_clear).
; Kind: translated - partial (sound only).
; Status: ported.
hud_threat_sound
        movem.l d0-d3/a0,-(sp)
        move.b  threat_sound_now,threat_sound_prev      ; 000077BD-000077C2
        clr.b   threat_sound_now                        ; 000077C7
        lea     object_table+(130-1)*OBJ_SIZE,a0        ; 000077D0 ebp = 0x82
        move.w  #130-30-1,d3
        moveq   #24,d2                                  ; 000077CE cl = 0x18
.object
        tst.b   OBJ_ACTIVE(a0)                          ; 000077D5
        beq     .next
        tst.b   OBJ_AUX(a0)                             ; 000077DE
        beq     .next
        move.l  OBJ_LATERAL20(a0),d0                    ; 000077ED
        asr.l   d2,d0                                   ; 000077F4
        cmpi.l  #-$14,d0                                ; 000077F6
        ble     .next                                   ; 000077F9
        cmpi.l  #$14,d0                                 ; 000077FB
        bge     .next                                   ; 000077FE
        move.l  OBJ_DEPTH20(a0),d1                      ; 00007800
        neg.l   d1                                      ; 00007807
        asr.l   d2,d1                                   ; 00007809
        cmpi.l  #-$0f,d1                                ; 0000780B
        ble     .next                                   ; 0000780E
        cmpi.l  #$0f,d1                                 ; 00007810
        bge     .next                                   ; 00007813
        move.b  #1,threat_sound_now                     ; 00007836
.next
        lea     -OBJ_SIZE(a0),a0                        ; 0000783D dec ebp
        dbra    d3,.object                              ; 0000783E-00007841
        tst.b   threat_sound_now                        ; 00007843
        beq     .out
        tst.b   threat_sound_prev                       ; 0000784C
        bne     .out
        SndSpeechB 2                                    ; 00007855-00007857
.out
        movem.l (sp)+,d0-d3/a0
        rts

; 000196BE: the view change zeroes [00019D93].
hud_threat_clear
        clr.b   threat_sound_now
        rts


; Both MFD bodies, and the map zoom that sits in front of them.
;
; 0000D64B-0000D689 is the held-key zoom. [0x1AA3] and [0x1AA4] are the
; key-state bytes 00001B96 writes for scancodes 0x33 and 0x34 - ',' and '.' -
; and a held key reads non-negative. ',' zooms out by 0x800000 up to
; 0x10000000, '.' zooms in down to 0x2000000; both are tested every frame, so
; holding one steps the zoom once per frame. 00019C5E-00019C7A's three preset
; keys (0x1F, 0x32, 0x22) live in the unported console-key dispatcher that
; also moves [0x19D88], and are not here.
;
; 0000D693-0000D6FC then draws the left body, moves [0x19CA8] 0x1A bytes -
; 104 pixels - right, draws the right body and moves it back. Every routine
; a body calls adds [0x19CA8] to its destination (00015855, 000079F0 and the
; three sprite blitters 00025880/0002599E/00025B27 all do), so a handler
; draws the same picture on either side. The port's [0x19CA8] is
; mfd_body_offset, in pixels.
;
; Each body is the handler table at 0x19E10 indexed by the side's page byte,
; with two overrides, in this order:
;   [0x1AA5] non-negative - scancode 0x35, '/', held - forces 00007690;
;   [0x19E3E] (left) / [0x19E3F] (right) negative forces 00007670.
; The second pair is entries 6 and 7 of the damage array 0002921A parses,
; each value already decremented, so an authored 0 disables that MFD from
; mission start. The first captured attract reads [0x1AA5] = 0xFF and the
; pair as 5 and 1, which is why neither fires there.
;
; 0000D689/0000D6C6 also store the side, 0 then 1, to [0x19C8C]. Nothing in
; the image reads that dword, so it is not carried.
; DOS: flat 0000D64B-0000D6FC, map zoom keys and the MFD body dispatch.
; DOS symbol: inside sub_0000D3E0's frame body (the 0000D4C4 cockpit branch)
; Record: analysis/functions/falcon-attract.md#mfd-bodies
; Port: steps the zoom and dispatches each side through the recovered table.
; Preserved: key bytes and sign tests, zoom step and both bounds, the table,
;   the override order, the 104-pixel side offset and left-then-right order.
; Kind: translated.
; Status: ported; all six pages and both overrides reach a ported handler.
mfd_draw_panel
        movem.l d0-d1/a0-a1,-(sp)
        tst.b   key_state+$33                   ; 0000D64B [0x1AA3]
        bmi     .no_zoom_out
        cmpi.l  #$10000000,mfd_zoom             ; 0000D654
        bcc     .no_zoom_out                    ; 0000D65E jae
        addi.l  #$800000,mfd_zoom               ; 0000D660
.no_zoom_out
        tst.b   key_state+$34                   ; 0000D66A [0x1AA4]
        bmi     .no_zoom_in
        cmpi.l  #$2000000,mfd_zoom              ; 0000D673
        bls     .no_zoom_in                     ; 0000D67D jbe
        subi.l  #$800000,mfd_zoom               ; 0000D67F
.no_zoom_in

        clr.w   mfd_body_offset
        move.b  mfd_page_left,d0                ; 0000D693 [0x72E6]
        moveq   #6,d1                           ; 0000D6AF [0x19E3E]
        bsr     .body
        move.w  #MFD_PANEL_STEP,mfd_body_offset ; 0000D6BF +0x1A
        move.b  mfd_page_right,d0               ; 0000D6D0 [0x72E7]
        moveq   #7,d1                           ; 0000D6EC [0x19E3F]
        bsr     .body
        clr.w   mfd_body_offset                 ; 0000D6FC -0x1A
        movem.l (sp)+,d0-d1/a0-a1
        rts

; In: d0.b = page, d1 = damage entry.
.body
        andi.w  #$ff,d0
        add.w   d0,d0
        add.w   d0,d0
        lea     mfd_body_table(pc),a0
        move.l  0(a0,d0.w),a0                   ; 0000D69A [ebx*4 + 0x19E10]
        tst.b   key_state+$35                   ; 0000D6A1 [0x1AA5]
        bmi     .no_hold
        lea     mfd_body_07690,a0               ; 0000D6AA
.no_hold
        lea     mission_damage,a1
        tst.b   0(a1,d1.w)                      ; 0000D6AF
        bpl     .no_fail
        lea     mfd_body_07670,a0               ; 0000D6B8
.no_fail
        jmp     (a0)                            ; 0000D6BD call eax

; 0x19E10, static content read back unchanged from the running original.
mfd_body_table
        dc.l    mfd_body_075B0                  ; page 0
        dc.l    mfd_body_07710                  ; page 1
        dc.l    mfd_draw_target_view            ; page 2, 00007860
        dc.l    mfd_body_076B0                  ; page 3
        dc.l    mfd_body_07530                  ; page 4
        dc.l    mfd_body_07690                  ; page 5

; Page 0: the map, then every nearby object plotted on it. 000075B0 calls
; 00007580 for the map and then walks the first thirty slots plotting
; markers.
; DOS: flat 000075B0-00007666, MFD page 0.
; DOS symbol: sub_000075B0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: draws the recovered map view and its object markers.
; Preserved: the draw order and the slot range.
; Kind: translated.
; Status: ported.
mfd_body_075B0
        bsr     mfd_draw_map
        jmp     mfd_draw_markers        ; cross-module, out of BSR's reach

; Pages whose body is one opaque CONS element over the whole panel. 00007670
; and 00007690 are a bare element-and-jmp; 00007530, 000076B0 and 00007710
; open the same way and then draw over it. The element's bottom-left is the
; left panel's (0x48, 0xAE) in every case; the side offset moves it.
; In: d0 = element.
mfd_opaque_panel
        movem.l d0-d3/a0-a1,-(sp)
        move.l  sprite_palette,-(sp)
        move.l  #instrument_palette,sprite_palette
        move.w  #$48,d1
        add.w   mfd_body_offset,d1
        move.w  #$ae,d2
        move.l  work_screen,a0
        lea     instrument_bank,a1
        jsr     sprite_draw_page_opaque         ; 00025880
        move.l  (sp)+,sprite_palette
        movem.l (sp)+,d0-d3/a0-a1
        rts

; The override body for a damaged MFD: element 0x32 and nothing else.
; DOS: flat 00007670-00007688, the failed-MFD body.
; DOS symbol: sub_00007670
; Record: analysis/functions/falcon-attract.md#mfd-bodies
; Port: draws the same CONS element at the same panel origin.
; Preserved: element, coordinates, the opaque blitter.
; Kind: translated.
; Status: ported.
mfd_body_07670
        moveq   #$32,d0
        bra     mfd_opaque_panel

; Page 5, and the '/'-held override: element 0x33 and nothing else.
; DOS: flat 00007690-000076A8, MFD page 5.
; DOS symbol: loc_00007690
; Record: analysis/functions/falcon-attract.md#mfd-bodies
; Port: draws the same CONS element at the same panel origin.
; Preserved: element, coordinates, the opaque blitter.
; Kind: translated.
; Status: ported.
mfd_body_07690
        moveq   #$33,d0
        bra     mfd_opaque_panel

; Page 3: element 0x38, then two two-digit readouts through 00007504 at x 0x8E
; - [0x2824D] on row 0xC6 above [0x2824B] on row 0xD0. The mission parser
; counts the '*' records into both (00029266/0002926C); 000237DE counts only
; [0x2824B] down as starred objects are retired. So the upper number is the
; mission's starred total and the lower the ones still standing. The port
; holds them as mission_star_count and object_endcue_hold.
; DOS: flat 000076B0-00007702, MFD page 3.
; DOS symbol: loc_000076B0
; Record: analysis/functions/falcon-attract.md#mfd-bodies
; Port: draws the panel element and both counters through the 00007504 port.
; Preserved: element, both anchors and rows, the byte reads, two digits each.
; Kind: translated.
; Status: ported.
mfd_body_076B0
        movem.l d0-d3,-(sp)
        moveq   #$38,d0                         ; 000076B0
        bsr     mfd_opaque_panel
        move.l  sprite_palette,-(sp)
        move.l  #hud_palette,sprite_palette
        moveq   #0,d0
        move.b  mission_star_count+1,d0         ; 000076CD movzx [0x2824D]
        move.w  #$8e,d1                         ; 000076D4
        add.w   mfd_body_offset,d1
        move.w  #$c6,d2                         ; 000076DE
        moveq   #2,d3                           ; 00007504 ecx = 2
        bsr     hud_draw_fixed_digits
        moveq   #0,d0
        move.b  object_endcue_hold+1,d0         ; 000076F4 movzx [0x2824B]
        move.w  #$d0,d2                         ; 000076FB
        moveq   #2,d3
        bsr     hud_draw_fixed_digits
        move.l  (sp)+,sprite_palette
        movem.l (sp)+,d0-d3
        rts

; Page 4: element 0x2A, then - on three frames in four - one overlay per
; negative entry among the first six of the damage array. 0000754D skips
; the overlays when [0x19DE8] & 3 is ZERO, the reverse sense of the map's
; target blink at 0000763A. The element is incremented before each test, so
; entry i selects 0x2B + i, and 0002599E is the masked, byte-aligned blitter,
; so each overlay lands on the base element at the same origin.
; DOS: flat 00007530-0000757B, MFD page 4.
; DOS symbol: loc_00007530
; Record: analysis/functions/falcon-attract.md#mfd-bodies
; Port: draws the base element and the per-entry overlays.
; Preserved: elements, origin, the frame gate and its sense, entry order,
;   the sign test and the masked quantised blitter.
; Difference: [0x19DE8] is read as frame_count, as the map's blink is.
; Kind: translated.
; Status: ported.
mfd_body_07530
        movem.l d0-d7/a0-a2,-(sp)
        moveq   #$2a,d0                         ; 00007530
        bsr     mfd_opaque_panel
        move.l  frame_count,d0
        andi.l  #3,d0                           ; 0000754D
        beq     .systems_done                   ; 00007557 je
        move.l  sprite_palette,-(sp)
        move.l  #instrument_palette,sprite_palette
        lea     mission_damage,a2               ; ebx = 0 over [0x19E38]
        moveq   #$2a,d4
        moveq   #6-1,d7                         ; 00007559 ecx = 6
.system
        addq.w  #1,d4                           ; 00007560 inc [0x22364]
        tst.b   (a2)+                           ; 00007566
        bpl     .system_next                    ; 0000756D jns
        move.l  d4,d0
        move.w  #$48,d1
        add.w   mfd_body_offset,d1
        move.w  #$ae,d2
        move.l  work_screen,a0
        lea     instrument_bank,a1
        jsr     sprite_draw_page_masked_quantised ; 00007571 -> 0002599E
.system_next
        dbra    d7,.system                      ; 00007579
        move.l  (sp)+,sprite_palette
.systems_done
        movem.l (sp)+,d0-d7/a0-a2
        rts


; The left multi-function display: a top-down moving map of the terrain the
; helicopter is over, sampled live from the authored colour map.
;
; 00007580 is the call site - it invokes 00015855 with the zoom in ebx and a
; destination of 0x37CE, then blits element 3 over the result. 00015855 forms
; the view basis, offsets the origin, and calls 0001591A once per Mode X
; plane, advancing a quarter step between planes; 0001591A samples one row.
;
; Geometry, all read off those two routines:
;
;   basis      esi = high32(zoom * [00019CB0]),  ebp = high32(zoom * [00019CB4])
;              with the zoom [00019C90] captured as 0x08000000
;   origin     X = [00019CD4] + 8*esi,  Y = [00019CD8] - 8*ebp   (0001587B)
;   per pixel  X += ebp/4, Y += esi/4                            (000158AA)
;   per row    X -= esi/4, Y += ebp/4                            (00015ABD)
;   sample     index = (Y>>22)<<10 | (X>>22) into [00019E64]     (0001592A)
;   extent     20 bytes per row written outward from the centre - 0x0A..0x13
;              forward, 0x09..0x00 backward - times four planes, so 80 pixels
;              wide, and 0x2C = 44 rows
;   position   destination 0x37CE is byte column 18, row 174: pixel (72, 174)
;
; [00019E64] is the COLOUR map, captured as 0x00209FC0 - exactly the height
; map at [00019E6C] plus 1 MB, which is how the pair is laid out. This draws
; the same bytes through the active RGB565 palette.
;
; The original walks four planes because its surface is planar; a chunky
; surface has no reason to, so this walks the 80 columns once. Same samples,
; same order along each row.
; DOS: flat 00007580-000075AD and 00015855-00015AD8, the left MFD map view.
; DOS symbol: sub_00007580
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: samples the authored colour map on the recovered rotated grid.
; Preserved: basis, zoom, origin offset, pixel and row steps, sample index,
; extent and screen position, element 3's own-ship blit at 000075A1, the
; live zoom [00019C90], and the [00019CA8] side offset - so the same routine
; serves page 0 on either MFD.
; Kind: adapted - chunky true-colour surface.
; Status: ported; same-camera capture remains pending.
mfd_draw_map
        movem.l d0-d7/a0-a6,-(sp)

        ; 0001587B-0001586D read [00019CB0]/[00019CB4] as they stand: the view
        ; basis 00007D25 built from the angle the frame STARTED with
        ; ([00019D00]), not from the angle the flight tick has since advanced
        ; ([00019D04]). They differ by one table step whenever the turn is large
        ; enough to cross a 2^23 boundary, which is a different sample grid.
        ; Measured against DEMO1 record 20's left MFD: the grid from the
        ; post-tick angle matches 57.6% of the DOS pixels, the one from
        ; [00019CB0] 99.6%.
        move.l  view_sin,d2                     ; [00019CB0]
        move.l  view_cos,d3                     ; [00019CB4]

        ; esi/ebp: high 32 of zoom * each.
        move.l  d3,d1                           ; retain cos across first call
        move.l  mfd_zoom,d0                     ; [00019C90]
        move.l  d2,d3
        bsr     ring_mul_q31_raw
        move.l  d0,d6                           ; esi
        move.l  mfd_zoom,d0                     ; [00019C90]
        move.l  d1,d3
        bsr     ring_mul_q31_raw
        move.l  d0,d7                           ; ebp

        ; Origin, 0001587B: X += 8*esi, Y -= 8*ebp.
        move.l  d6,d0
        asl.l   #3,d0
        move.l  flt_x,d4
        add.l   d0,d4                           ; row-centre X
        move.l  d7,d0
        asl.l   #3,d0
        move.l  flt_y,d5
        sub.l   d0,d5                           ; row-centre Y

        ; Quarter steps: per pixel (ebp/4, esi/4), per row (-esi/4, +ebp/4).
        move.l  d7,d2
        asr.l   #2,d2                           ; pixel dX
        move.l  d6,d3
        asr.l   #2,d3                           ; pixel dY

        ; Back up from the row centre to its left edge: 40 pixels.
        move.l  d2,d0
        muls.l  #MFD_HALF_W,d0
        sub.l   d0,d4
        move.l  d3,d0
        muls.l  #MFD_HALF_W,d0
        sub.l   d0,d5

        move.l  work_screen,a0
        ; MFD_X is a page x - see MFD_SURFACE_X. This write goes straight to
        ; the surface rather than through sprite_draw_page, so it takes the
        ; view-window margin off itself; it was missed when the rest of the
        ; layer was moved and sat four pixels right of the bezel around it.
        lea     MFD_Y*SCREEN_STRIDE+MFD_SURFACE_X*2(a0),a0
        move.w  mfd_body_offset,d0              ; 0001585B + [0x19CA8]
        add.w   d0,d0
        adda.w  d0,a0
        lea     ring_maprow,a3                  ; each map row's address
        lea     flight_palette,a4
        move.w  #MFD_H-1,d7
.row
        move.l  a0,a5
        move.l  d4,a1                           ; this row's walking X
        move.l  d5,a2                           ; and Y
        move.w  #MFD_W-1,d6
.pixel
        ; 0001592A's shld pair: Y's top ten bits pick the row, X's the byte
        ; in it - the marcher's TERRAIN_SAMPLE read, of the colour map.
        move.l  a2,d0
        bfextu  d0{0:10},d0                     ; Y cell
        movea.l (a3,d0.w*4),a6                  ; its row (height map)
        move.l  a1,d1
        bfextu  d1{0:10},d1                     ; X cell
        moveq   #0,d0
        move.b  (MAP_COLOUR_DELTA.l,a6,d1.w),d0 ; the colour-map byte
        move.w  0(a4,d0.w*2),(a5)+
        add.l   d2,a1                           ; per pixel
        add.l   d3,a2
        dbra    d6,.pixel

        sub.l   d3,d4                           ; per row: X -= esi/4
        add.l   d2,d5                           ;          Y += ebp/4
        adda.w  #SCREEN_STRIDE,a0
        dbra    d7,.row

        ; 00007590-000075A8: the own-ship marker, over the map it just drew.
        ; Element 3 of the instrument bank at page x 0x70, bottom row 0xCE,
        ; through 0002599E - the masked, plane-chunked blitter, so the left
        ; edge snaps to the four-pixel byte boundary the way the console's
        ; other fixed elements do. It is the white cross at the centre of the
        ; original's left panel.
        move.l  sprite_palette,-(sp)
        move.l  #instrument_palette,sprite_palette
        moveq   #3,d0                           ; 000075A1
        move.w  #$70,d1                         ; 00007590
        add.w   mfd_body_offset,d1              ; 000259B1 + [0x19CA8]
        move.w  #$ce,d2                         ; 0000759A
        move.l  work_screen,a0
        lea     instrument_bank,a1
        jsr     sprite_draw_page_masked_quantised
        move.l  (sp)+,sprite_palette

        movem.l (sp)+,d0-d7/a0-a6
        rts

; DOS: 0000D857-0000D887. The original uses HUDS element 0x21 for the small
; ring and 00025CA2 for the green sight line.  The latter is a VGA-plane line
; writer; the Falcon equivalent writes the same pixels directly to RGB565.
; Inputs: flt_fwd/flt_lat in the original 10.22 velocity units.
; DOS symbol: inside loc_0000D852
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: draws the recovered dynamic HUDS ring and sight line on the Falcon
; chunky surface after the fixed indicator family.
; Preserved: velocity-derived endpoint, HUDS element, draw order, and green
; line rasterization; the COMA tail follows this routine in DOS order.
; Kind: adapted - chunky true-colour surface.
; Status: ported; COMA tail and its page-gated branch follow below.
hud_draw_dynamic
        tst.w   hud_status
        bne     .none
        movem.l d0-d3/a0-a1,-(sp)

        ; Preserve the original order: target sprite, then line back to the
        ; fixed sight centre.  DOS computes -fwd and +lat with arithmetic
        ; shifts, so the negative values round exactly as the x86 path does.
        move.l  flt_lat,d1
        asr.l   #8,d1
        asr.l   #8,d1
        asr.l   #3,d1
        addi.w  #$a5,d1
        move.l  flt_fwd,d2
        neg.l   d2
        asr.l   #8,d2
        asr.l   #8,d2
        asr.l   #3,d2
        addi.w  #$5a,d2

        move.l  sprite_palette,-(sp)
        move.l  #hud_palette,sprite_palette
        ; 0000D4B2 draws the horizon reference before 0000D4B7 reaches
        ; 0000D703's compass and speed chain, so it goes first here too.
        bsr     hud_draw_horizon_line
        bsr     hud_draw_authored

        moveq   #$21,d0
        move.l  work_screen,a0
        lea     hud_bank,a1
        jsr     sprite_draw_page
        move.l  (sp)+,sprite_palette

        ; The line is the last operation in the DOS sight path, after the
        ; target ring and the other HUDS elements.
        bsr     hud_draw_sight_line
        bsr     hud_draw_variant_tail
        movem.l (sp)+,d0-d3/a0-a1
.none
        rts

; The remaining flight-console calls after 0000D887: the weapon element at the
; sight centre, and the target designator.
;
; **The bank was wrong, and that is what the gate was hiding (2026-08-31).**
; Both blits here go through 0002599E, and 0002599E's first instruction is
; `mov esi, [0x19E90]` - the same pointer 00025880 and 0002590F read, and NOT
; the [0x19E94] that 00025B27/00025BB6 read for the HUDS glyphs. Read out of
; the running original at a frame that holds a lock, [0x19E90] is 0x3B59A8
; whose SG header declares **57 elements**: CONS.RLE, the instrument bank, not
; COMA.RLE's nine views. This port drew from COMA, got a helicopter across the
; frame, and was given a `phase == 5` gate to suppress it - a gate the
; original does not have. 0000D4B7-0000D4CB reaches 0000D88C for console
; variant 1, which is what the attract runs, and 0000D8AE's only test is
; `[0x19D86] > 5`.
;
; Difference, and it is the single-buffered erase rather than a picture:
; 0002590F at 0000D8E3 copies the page UNDER the marker into element
; 5 + [0x19D87] (it reads the page and writes the bank, programming the
; graphics controller's read-map select), and 0000D350-0000D385 blits that
; element back opaquely at the top of the next frame. That is DOS restoring
; its single page before redrawing. The Falcon repaints the whole surface
; every frame, so the save and the restore have nothing to do; element 4,
; the marker itself, is the visible half and is what is drawn here.
; DOS: flat 0000D88C-0000D8F4.
; DOS symbol: inside loc_0000D852
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: draws the weapon element and the target designator from the bank the
; original's blitter actually reads.
; Preserved: bank, element indices, coordinates, the variant limit, the null
;   gate and the draw order.
; Kind: translated; the save/restore pair is dropped as a platform difference.
; Status: ported.
hud_draw_variant_tail
        tst.w   instrument_status
        bne     .done
        move.l  sprite_palette,-(sp)
        move.l  #instrument_palette,sprite_palette

        ; 0000D88C-0000D8A9: element [0x19D81] + 1 at page (0xA4, 0x5A),
        ; through 0002599E - index 0 transparent, left edge on the four-pixel
        ; byte boundary.
        moveq   #0,d0
        move.b  hud_weapon,d0
        addq.w  #1,d0
        move.w  #$a4,d1
        move.w  #$5a,d2
        move.l  work_screen,a0
        lea     instrument_bank,a1
        jsr     sprite_draw_page_masked_quantised

        ; 0000D8AE-0000D8F4: the target designator. Its one gate is the
        ; console variant; its position comes from the two tables
        ; object_target_validate fills from the locked object, and a zero x
        ; means no lock this frame.
        cmpi.b  #5,hud_console_variant
        bhi     .restore
        moveq   #0,d3
        move.b  hud_console_page,d3
        move.w  d3,d4
        lsl.w   #2,d4
        lea     hud_variant_x,a2
        move.l  0(a2,d4.w),d0                   ; 0000D8BE
        beq     .restore                        ; 0000D8C5/0000D8C7
        move.w  d0,d1                           ; 0000D8C9: the page x
        lea     hud_variant_y,a2
        moveq   #0,d2
        move.b  0(a2,d3.w),d2                   ; 0000D8CE/0000D8D5: the row
        ; 0000D8E3's element 5 + half is the save-under, which this port has
        ; no use for - see the header. 0000D8E8-0000D8EF's element 4 at the
        ; same x and row is the marker.
        moveq   #4,d0
        move.l  work_screen,a0
        lea     instrument_bank,a1
        jsr     sprite_draw_page_masked_quantised
.restore
        move.l  (sp)+,sprite_palette
.done
        rts

; DOS: 0000D703-0000D852 and 0000D8F5.  The two option bytes are the authored
; menu strings at 000267C1 (HID Indicators) and 000267D2 (HID Compass).  The
; Falcon keeps those strings as the menu's source of truth, just as the DOS
; compares do, while the sprite calls below use the HUDS palette.
; DOS symbol: loc_0000D703
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: emits the recovered compass, SPEED, clearance ladder, and value calls
; through the RGB565 HUDS bank.
; Preserved: option gates, element numbers, coordinates, arithmetic, and order;
; the variant-specific tail remains separate.
; Kind: adapted - chunky true-colour surface.
; Status: ported for the authored compass, speed and ladder elements.
hud_draw_authored
        movem.l d0-d7/a0-a3,-(sp)

        ; 0000D703: compass marker (HUDS 2) and the heading ribbon window
        ; (HUDS 1 through the DOS 00025A4D partial blitter).
        cmpi.b  #'{',menu_group_text+($267d2-$26607)
        beq     .indicators
        moveq   #2,d0
        move.w  #$a4,d1
        move.w  #5,d2
        move.l  work_screen,a0
        lea     hud_bank,a1
        jsr     sprite_draw_page
        bsr     hud_draw_compass_window

.indicators
        ; 0000D743: the authored HUD indicator switch gates the speed and
        ; altitude family, including the visible SPEED label.
        cmpi.b  #'{',menu_group_text+($267c1-$26607)
        beq     .out
        ; [00019E00], the clearance the readout shows, is stored by the flight
        ; tick at 00019391 (flight_tick), not recomputed here: the readout
        ; therefore lags the position it is drawn at by one tick, as DOS's does.

        ; 0000D7B7: HUDS element 0x15 is the SPEED label, not a CONS glyph.
        moveq   #$15,d0
        move.w  #$42,d1
        move.w  #$88,d2
        move.l  work_screen,a0
        lea     hud_bank,a1
        jsr     sprite_draw_page

        ; 0000D7D4: abs(max(forward,lateral)) >> 17, rendered by D8F5.
        move.l  flt_fwd,d0
        bpl     .speed_fwd_positive
        neg.l   d0
.speed_fwd_positive
        move.l  flt_lat,d3
        bpl     .speed_lat_positive
        neg.l   d3
.speed_lat_positive
        cmp.l   d0,d3
        bls     .speed_max_ready
        move.l  d3,d0
.speed_max_ready
        lsr.l   #8,d0
        lsr.l   #8,d0
        lsr.l   #1,d0
        move.w  #$42,d1
        move.w  #$88,d2
        bsr     hud_draw_value

        ; 0000D7F4: fixed ladder at x=0x120, y=0x78.  00025C55 then marks
        ; the current clearance upward from that bottom edge.
        moveq   #4,d0
        move.w  #$120,d1
        move.w  #$78,d2
        move.l  work_screen,a0
        lea     hud_bank,a1
        jsr     sprite_draw_page
        moveq   #0,d3
        move.b  hud_clearance,d3
        lsr.w   #2,d3
        addq.w  #1,d3
        move.w  #$120,d0
        move.w  #$78,d1
        move.w  d3,d2
        bsr     hud_draw_solid_column

        ; 0000D82B/0000D852: clearance value beside the ladder. The DOS
        ; routine clamps (2*clearance - 10) below zero before D8F5.
        moveq   #0,d3
        move.b  hud_clearance,d3
        lsr.w   #2,d3
        addq.w  #1,d3
        move.w  #$7b,d2
        sub.w   d3,d2
        moveq   #0,d0
        move.b  hud_clearance,d0
        add.w   d0,d0
        subi.w  #10,d0
        bpl     .clearance_value_ready
        clr.w   d0
.clearance_value_ready
        move.w  #$110,d1
        bsr     hud_draw_value

.out
        movem.l (sp)+,d0-d7/a0-a3
        rts

; Falcon equivalent of the DOS 00025A4D heading-window blitter. The DOS path
; selects source column (angle >> 25), then emits 64 columns from HUDS 1 at
; the five-pixel top ribbon. The authored record is column-major and is
; normalized to top-down rows by sprite_init.
; DOS: flat 00025A4D-00025BEA, heading-window/HUDS compass blit.
; DOS symbol: sub_00025A4D
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: emits the same authored columns into the Falcon RGB565 surface.
; Preserved: angle selection, source window, column count and five-row height.
; Kind: adapted - chunky true-colour surface.
; Status: ported; exact DOS/port frame capture matches the compass window.
hud_draw_compass_window
        movem.l d0-d7/a0-a3,-(sp)
        move.l  flt_angle,d0
        lsr.l   #8,d0
        lsr.l   #8,d0
        lsr.l   #8,d0
        lsr.l   #1,d0
        andi.w  #$7f,d0
        mulu    #5,d0
        lea     hud_bank,a1
        lea     8(a1),a2
        moveq   #0,d1
        move.b  7(a2),d1
        lsl.l   #8,d1
        move.b  6(a2),d1
        lsl.l   #8,d1
        move.b  5(a2),d1
        lsl.l   #8,d1
        move.b  4(a2),d1
        adda.l  d1,a1
        adda.l  d0,a1
        moveq   #0,d6                           ; source column
        ; 0000D729 sets [0x22365] = 0x21 and 00025A8D adds it to the row
        ; base as a BYTE offset, so the window starts at page 0x21 * 4 = 132
        ; and therefore at surface 132 - PAGE_VIEW_X = 128. This was a
        ; hand-centred 136, which put the ribbon eight pixels right.
        move.w  #$21*4-PAGE_VIEW_X,d7
.col
        move.w  #5-1,d5
        move.w  #5,d4                           ; top row after normalization
.row
        moveq   #0,d0
        move.b  (a1)+,d0
        beq     .blank
        move.w  d0,d1
        add.w   d1,d1
        move.l  work_screen,a0
        move.w  d4,d2
        mulu    #SCREEN_STRIDE,d2
        adda.l  d2,a0
        move.w  d7,d2
        add.w   d2,d2
        adda.w  d2,a0
        move.l  sprite_palette,a3
        move.w  0(a3,d1.w),(a0)
.blank
        addq.w  #1,d4
        dbra    d5,.row
        addq.w  #1,d7
        addq.w  #1,d6
        cmpi.w  #64,d6
        blo     .col
        movem.l (sp)+,d0-d7/a0-a3
        rts

; The `xor edx,edx / div ecx` both digit paths open with: an unsigned 32-bit
; divide by ten yielding quotient AND remainder.
;
; Not DIVUL.L. The 64/32 divide is one of the integer instructions a 68060
; does not implement, so every digit took an exception into the 68060
; software package - while 32/32 DIVU.L and 32x32->32 MULU.L are hardware on
; the 68030, 68040 and 68060 alike. `div ecx` with EDX cleared is a 32-bit
; dividend, so this pair covers exactly the range the original does; it is
; the same arithmetic, not a narrowing of it.
;
; In: d4 = dividend. Out: d4 = quotient (EAX), d3 = remainder (EDX).
;   Clobbers d5. Both callers carry the quotient across sprite_draw_page,
;   which is the original's `push eax` / `pop eax` around 00025B27.
; DOS: flat 0000D901-0000D903 and 00007499-0000749B, the shared digit divide.
; DOS symbol: inside sub_0000D8F5 and loc_00007493
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: same unsigned quotient and remainder, without the 68060 trap.
; Preserved: the unsigned 32-bit dividend range, the quotient and the
;   remainder, for every value either caller can present.
; Kind: translated.
; Status: ported; covered by the HUD and console digit captures.
hud_divmod10
        move.l  d4,d3                           ; the dividend
        divu.l  #10,d4                          ; EAX after `div ecx`
        move.l  d4,d5
        mulu.l  #10,d5
        sub.l   d5,d3                           ; EDX after `div ecx`
        rts

; Recreate the value helper at 0000D8F5. It draws units, tens and (when
; needed) hundreds from HUDS records 0x16..0x1F, right-aligned at x+8.
; In: d0=value, d1=x anchor, d2=bottom y.
; DOS: flat 0000D8F5-0000D950, numeric HUD helper.
; DOS symbol: sub_0000D8F5
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: dispatches the same HUDS digit records through the Falcon blitter.
; Preserved: decimal decomposition, right alignment, record indices and order.
; Kind: adapted - chunky true-colour surface.
; Status: ported; digit orientation is covered by the HUD capture check.
hud_draw_value
        ; 0000D8F5 zeroes edx before every `div ecx`, so each divide takes a
        ; clean 32-bit dividend. This used to feed DIVU.W a d4 whose high word
        ; still held the previous divide's remainder - `move.w d3,d4` sets only
        ; the low half - so the second digit came out of a garbage dividend and
        ; the tens position rendered as the wrong element or not at all. It is
        ; what made the HUD read "SPEED:1 1" where the original reads
        ; "SPEED:106". hud_divmod10 is the 32-bit divide `div ecx` actually is.
        movem.l d0-d5/a0-a2,-(sp)
        addq.w  #8,d1
        move.l  d0,d4                           ; the value
        bsr     hud_divmod10                    ; d3 = value % 10, d4 = / 10
        move.w  d3,d0
        addi.w  #$16,d0                         ; 0000D905 add dl, 0x16
        move.l  work_screen,a0
        lea     hud_bank,a1
        jsr     sprite_draw_page

        subq.w  #4,d1                           ; 0000D927 sub [0x2587C], 4
        bsr     hud_divmod10
        move.w  d3,d0
        addi.w  #$16,d0
        move.l  work_screen,a0
        lea     hud_bank,a1
        jsr     sprite_draw_page

        ; 0000D935 is `cmp al, 9`, and 0000D939/0000D93B are `add al, 0x16`
        ; and a BYTE store to [0x22364]. Both are the low byte of the
        ; quotient, not the whole dword: a quotient of 0x100 leaves AL = 0,
        ; so the original draws element 0x16 where a 32-bit test returns.
        ; The HUD's own values never reach it, but the width is the
        ; original's and costs nothing to keep.
        cmpi.b  #9,d4                           ; 0000D935 cmp al, 9 / ja
        bhi     .out
        subq.w  #4,d1
        moveq   #0,d0
        move.b  d4,d0                           ; 0000D939 add al, 0x16
        addi.w  #$16,d0
        move.l  work_screen,a0
        lea     hud_bank,a1
        jsr     sprite_draw_page
.out
        movem.l (sp)+,d0-d5/a0-a2
        rts

; The console's fixed-width decimal readouts. 00007493 and 00007509 are the
; same loop at two lengths: divide by ten, draw element 0x0A + remainder at
; the anchor, step the anchor five pixels left, repeat. There is no
; leading-zero suppression - 0000D8F5's `cmp al,9` test is absent here, which
; is why the original shows `0011` and not `11`.
; In: d0 = value, d1 = x anchor, d2 = bottom row, d3 = digit count.
; DOS: flat 0000748E-000074B7 and 00007504-0000752D, fixed-width digit loops.
; DOS symbol: inside loc_00007403 and sub_00007504
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: dispatches the same HUDS records 0x0A..0x13 through the Falcon blitter.
; Preserved: digit order, the five-pixel step, the element base, and the count.
; Kind: adapted - chunky true-colour surface.
; Status: ported; the console capture covers the ammo and countermeasure
;   readouts it draws.
; The count lives in d7 and not in d3: sprite_draw_page loads d3 with its
; blitter flags and does not restore it, so a d3 loop counter is reset to 1
; by every digit and `dbra` never reaches -1. That hung the frame.
hud_draw_fixed_digits
        movem.l d0-d7/a0-a1,-(sp)
        move.l  d0,d4
        move.w  d3,d7
        subq.w  #1,d7
        bmi     .digits_out
.digit
        bsr     hud_divmod10            ; 0000749B: remainder, then quotient
        move.w  d3,d0
        addi.w  #$0a,d0                 ; 0000749D add dl, 0xA
        move.l  work_screen,a0
        lea     hud_bank,a1
        jsr     sprite_draw_page
        subq.w  #5,d1                   ; 000074AD sub [0x2587C], 5
        dbra    d7,.digit
.digits_out
        movem.l (sp)+,d0-d7/a0-a1
        rts

; Falcon equivalent of 00025C55, which writes one solid HUD colour upward
; from the supplied bottom edge.
; In: d0=x, d1=bottom y, d2=count.
; DOS: flat 00025C55-00025CA2, solid HUD column writer.
; DOS symbol: sub_00025C55
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: clips the same upward walk to the Falcon RGB565 surface.
; Preserved: bottom-origin, upward count, the two-pixel width, and the
;   authored colour.
; Kind: adapted - framebuffer bounds replace VGA address wrap.
; Status: ported; width and colour both corrected against the listing.
;
; Two things here were wrong until they were read off 00025C55 rather than
; assumed:
;
;   WIDTH. 00025C59 writes 0x302 to the sequencer at 0x3C4 - map mask 0x03,
;   so planes 0 AND 1 - and then addresses a BYTE column, [0x2587C] >> 2. In
;   Mode X byte column c plane p is pixel 4c + p, so the bar covers pixels
;   (x & ~3) and (x & ~3) + 1. It is two pixels wide, and this drew one.
;
;   COLOUR. Every caller loads cl from [0x2A37A], and that byte is not a
;   constant: 0002AB25-0002AB3F resolves it, when the mission palette is
;   installed, to the nearest index in THAT palette to the authored six-bit
;   triple (0x10, 0x3F, 0x10). It reads 6 for the attract's np44 palette, and
;   a different mission palette gives a different index. This drew a
;   hard-coded RGB565 green instead - the right colour by accident and the
;   wrong mechanism, so it could not follow the palette.
hud_draw_solid_column
        move.l  d3,-(sp)
        moveq   #0,d3
        move.b  resource_named_colours+5,d3     ; [0x2A37A]
        bsr     hud_draw_column_index
        move.l  (sp)+,d3
        rts

; 00025C55 with cl in d3: d0 = x, d1 = bottom y, d2 = count, d3 = palette index.
hud_draw_column_index
        movem.l d0-d4/a0-a1,-(sp)
        subq.w  #1,d2
        ; The resolved index through the mission palette. flight_palette and
        ; resource_active_palette are filled from the same entries in one
        ; loop - RGB565 and six-bit - so the index the search returned is the
        ; index to use here.
        moveq   #0,d4
        move.b  d3,d4                           ; cl, the palette index
        add.w   d4,d4
        lea     flight_palette,a1
        move.w  0(a1,d4.w),d4
        andi.w  #~3,d0                          ; 00025C6E: shr edi, 2
        subi.w  #PAGE_VIEW_X,d0                 ; page x -> surface x
.loop
        tst.w   d1
        bmi     .next
        cmpi.w  #SCREEN_HEIGHT,d1
        bhs     .next
        move.l  work_screen,a0
        move.w  d1,d3
        mulu    #SCREEN_STRIDE,d3
        adda.l  d3,a0
        move.w  d0,d3
        add.w   d3,d3
        adda.w  d3,a0
        ; planes 0 and 1 of the byte column
        tst.w   d0
        bmi     .next
        cmpi.w  #SCREEN_WIDTH,d0
        bhs     .next
        move.w  d4,(a0)
        move.w  d0,d3
        addq.w  #1,d3
        cmpi.w  #SCREEN_WIDTH,d3
        bhs     .next
        move.w  d4,2(a0)
.next
        subq.w  #1,d1
        dbra    d2,.loop
        movem.l (sp)+,d0-d4/a0-a1
        rts

; Falcon RGB565 equivalent of DOS 00025CA2.  Bresenham's integer walk is the
; same endpoint walk as the original shallow/steep split, with the DOS centre
; and target coordinates kept in page pixels.
; DOS: flat 00025CA2-00025D4B, sight-line rasterizer (00025D31 is the
; fifth byte of 00025D2D; the routine's `ret` is at 00025D4B).
; DOS symbol: sub_00025CA2
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: walks the same endpoints on the chunky RGB565 surface.
; Preserved: shallow/steep branch, endpoint inclusion and integer step order.
; Kind: adapted - framebuffer surface replaces planar writes.
; Status: ported; exact endpoint capture remains pending.
hud_draw_sight_line
        movem.l d0-d7/a0,-(sp)
        move.w  d1,hud_target_x
        move.w  d2,hud_target_y

        move.w  hud_target_x,d2
        subi.w  #$a5,d2
        moveq   #1,d4
        tst.w   d2
        bpl     .x_sign
        neg.w   d2
        moveq   #-1,d4
.x_sign
        move.w  d4,hud_line_sx

        move.w  hud_target_y,d3
        subi.w  #$5a,d3
        moveq   #1,d5
        tst.w   d3
        bpl     .y_sign
        neg.w   d3
        moveq   #-1,d5
.y_sign
        move.w  d5,hud_line_sy

        tst.w   d2
        bne     .not_point
        tst.w   d3
        beq     .point
.not_point
        cmp.w   d3,d2
        bcs     .steep

        ; Shallow: x is the major axis and y advances when the accumulated
        ; fractional slope crosses one whole pixel.
        moveq   #0,d6
        move.w  d3,d6
        swap    d6
        move.w  d2,d4
        addq.w  #1,d4
        divu.w  d4,d6
        andi.l  #$0000ffff,d6             ; keep quotient; DIVU leaves remainder high
        ; 00025D09-00025D10: the step is the MIDDLE byte of the quotient plus
        ; 0x100 (`mov bl,ah`), the accumulator is a byte that starts at 0x80
        ; and a carry out of `add bh,bl` advances the minor axis.
        addi.l  #$100,d6
        lsr.l   #8,d6
        andi.l  #$ff,d6
        moveq   #$80-256,d7
        move.w  #$a5,d0
        move.w  #$5a,d1
        move.w  d2,d4
        addq.w  #1,d4
        subq.w  #1,d4
.h_loop
        bsr     hud_plot_sight_pixel
        add.w   hud_line_sx,d0
        add.b   d6,d7                     ; 00025D3F add bh,bl
        bcc     .h_no_y                   ; jae
        add.w   hud_line_sy,d1
.h_no_y
        dbra    d4,.h_loop
        bra     .done

.steep
        moveq   #0,d6
        move.w  d2,d6
        swap    d6
        move.w  d3,d4
        addq.w  #1,d4
        divu.w  d4,d6
        andi.l  #$0000ffff,d6             ; keep quotient; DIVU leaves remainder high
        addi.l  #$100,d6                  ; 00025D57: the middle byte, as above
        lsr.l   #8,d6
        andi.l  #$ff,d6
        moveq   #$80-256,d7
        move.w  #$a5,d0
        move.w  #$5a,d1
        move.w  d3,d4
        addq.w  #1,d4
        subq.w  #1,d4
.v_loop
        bsr     hud_plot_sight_pixel
        add.w   hud_line_sy,d1
        add.b   d6,d7                     ; 00025D8D add bh,bl
        bcc     .v_no_x                   ; jae
        add.w   hud_line_sx,d0
.v_no_x
        dbra    d4,.v_loop
        bra     .done

.point
        move.w  #$a5,d0
        move.w  #$5a,d1
        bsr     hud_plot_sight_pixel
.done
        movem.l (sp)+,d0-d7/a0
        rts

; DOS: flat 00025D2D-00025D33, the sight-line pixel write - the colour
; byte [0002A37A] stored at [edi + esi>>2] inside 00025CA2-00025D4B.
; DOS symbol: inside loc_00025D1B
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: bounds-checks and writes one RGB565 crosshair pixel.
; Preserved: pixel coordinates and colour; off-surface writes are a Falcon
;       safety exception because DOS deliberately wrapped its page address.
; Kind: adapted - bounded chunky surface.
; Status: ported; covered by the sight-line caller.
hud_plot_sight_pixel
        movem.l d0-d2/a0-a1,-(sp)
        ; The endpoints are PAGE pixels - 00025CBB/00025CC1 address the Mode
        ; X page - so the view window's margin comes off here, as it does at
        ; every other page-x writer in this file. Without it the line began
        ; four pixels right of the sight centre: DOS captures show it leaving
        ; the gap of the fixed cross, the port showed it leaving the cross's
        ; right arm.
        subi.w  #PAGE_VIEW_X,d0
        tst.w   d0
        bmi     .skip
        cmpi.w  #SCREEN_WIDTH,d0
        bhs     .skip
        tst.w   d1
        bmi     .skip
        cmpi.w  #SCREEN_HEIGHT,d1
        bhs     .skip
        move.l  work_screen,a0
        move.w  d1,d2
        mulu    #SCREEN_STRIDE,d2
        adda.l  d2,a0
        add.w   d0,d0
        adda.w  d0,a0
        ; 00025D2D: the colour is the byte [0x2A37A], the mission palette's
        ; nearest index to the authored green - the source
        ; hud_draw_solid_column already reads - not a fixed RGB565 value.
        moveq   #0,d2
        move.b  resource_named_colours+5,d2     ; [0x2A37A]
        add.w   d2,d2
        lea     flight_palette,a1
        move.w  0(a1,d2.w),(a0)                 ; 00025D33
.skip
        movem.l (sp)+,d0-d2/a0-a1
        rts


; The F, C and T gauges, 0000D4D1-0000D5AB: bars at page x 0x110, 0x30 and 0x38,
; each a 0x16-row black column from page row 0xBC upward (cl = 0) and then the
; level over it - C: [00019D82] >> 3 + 1 rows in [0002A37C], T: [00019D84] >> 3 + 1
; rows in [0002A379], F: ([00019CF4] << 2 + [00019D60]) >> 8 + 1 in [0002A37C]
; (drawn only while (frame & 1) + ([00019D60] >= 0) is not zero; [00019D60]
; starts at the mission's fuel field [00019D5C] and loses one per tick), all
; clamped to 0x16. The console art carries a baked bar in each; the original
; paints over it every frame and so does this. The fuel-exhausted branch
; (00018E10-00018E44) is not ported.
; DOS: flat 0000D4D1-0000D5AB.
; DOS symbol: inside sub_0000D3C0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: draws the two bars through the solid column writer.
; Preserved: the clear, the level formula, the clamp, both colours.
; Kind: translated.
; Status: ported; checked against DEMO1 record 20.
hud_draw_gauges
        movem.l d0-d3,-(sp)
        ; 0000D4D1-0000D52D, the F gauge: cleared, then drawn while
        ; (frame & 1) + ([00019D60] >= 0) is not zero, `[00019CF4] << 2 +
        ; [00019D60]` rows' worth of fuel, negative to zero, >> 8, + 1, clamped.
        move.w  #$110,d0
        bsr     .bar_clear
        move.l  frame_count,d1
        andi.w  #1,d1                           ; 0000D4F0 and al,1
        move.l  flt_fuel,d2
        smi     d3
        addq.b  #1,d3                           ; setns bl: 1 when [00019D60] >= 0
        andi.w  #1,d3
        add.w   d3,d1                           ; 0000D501
        beq.s   .fuel_done                      ; 0000D503
        move.l  flt_pitch,d3
        asl.l   #2,d3                           ; 0000D50A shl eax, 2
        add.l   d2,d3                           ; 0000D50D
        bpl.s   .fuel_pos
        moveq   #0,d3                           ; 0000D515
.fuel_pos
        lsr.l   #8,d3                           ; 0000D517
        move.b  d3,d2                           ; al
        move.w  #$110,d0
        move.b  resource_named_colours+8,d3     ; 0000D527 [0002A37C]
        bsr.s   .bar_level_al
.fuel_done
        moveq   #$30,d0
        bsr.s   .bar_clear
        move.b  flt_collective,d2               ; 0000D551 [00019D82]
        move.b  resource_named_colours+8,d3     ; 0000D566 [0002A37C]
        bsr.s   .bar_level
        moveq   #$38,d0
        bsr.s   .bar_clear
        move.b  flt_torque,d2                   ; 0000D590 [00019D84]
        move.b  resource_named_colours+9,d3     ; 0000D5A5 [0002A379]
        bsr.s   .bar_level
        movem.l (sp)+,d0-d3
        rts
.bar_clear
        movem.l d0-d3,-(sp)
        move.w  #$bc,d1
        moveq   #$16,d2
        moveq   #0,d3                           ; xor cl, cl
        bsr     hud_draw_column_index
        movem.l (sp)+,d0-d3
        rts
.bar_level
        lsr.b   #3,d2                           ; shr al, 3
.bar_level_al
        andi.w  #$ff,d3
        addq.b  #1,d2                           ; inc al
        cmpi.b  #$16,d2
        bls.s   .level_ok                       ; jbe
        moveq   #$16,d2
.level_ok
        andi.w  #$ff,d2
        move.w  #$bc,d1
        bra     hud_draw_column_index

; DOS: flat 000073D0-00007909, the console/HUD composition region entered
; through the [00019D86] gate at 000073D0.
; DOS symbol: sub_000073D0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: composes the authored console and recovered fixed instruments in RGB565.
; Preserved: draw-after-input ordering; unrecovered gauges are omitted.
; Kind: translated.
; Status: partial; no invented HUD geometry is emitted.
hud_draw
        ; 000073D0's own first instruction: `cmp byte [0x19D86],1 / jne
        ; 0x74B7`, and 0x74B7 is a bare `ret`. The routine has fourteen
        ; callers, so the gate lives here as well as at frame_driver's
        ; 0000D4C4 - game_command's console-page path reaches it directly.
        cmpi.b  #1,view_variant
        bne     .not_cockpit
        move.l  work_screen,a0

        ; An incremental branch used to sit here: on a DSP frame it repainted
        ; only the canopy art above the console's "solid row" and returned
        ; early, on the reasoning that the block below persisted in the
        ; buffers. That partial repaint, its solid-row boundary and the
        ; per-column floor it came from are all absent from the original -
        ; 00006FEF transfers the whole surface every frame and the console is
        ; composited over it - so the branch went with them. Both machines
        ; compose the same full console.

        ; The real console, when its image loaded. COMA.RLE is NOT this - it is
        ; the Comanche itself in nine views, which is merely what the cockpit
        ; blitters' resource base points at. The surround is a .DTA image.
        ;
        ; Without CONSOL1S.DTA the frame is bare terrain. That is the honest
        ; state of a missing asset: the original has no such mode, so there is
        ; nothing to draw that would be 1:1 with it.
        tst.w   console_status
        bne     .no_console
        bsr     console_draw
        ; 00007580 draws the left panel's map view over the console art, from
        ; the same console region 000073D0 gates.
        bsr     mfd_draw_panel
        move.l  work_screen,a0
        bsr     instruments_draw
        bsr     hud_draw_gauges
        ; 000072EB's labels sit on the console art, so they follow it. The
        ; DOS console is repainted whenever the page changes and the labels
        ; are redrawn from the key handler; this port repaints every frame,
        ; so they are drawn every frame from the same page bytes.
        jsr     mfd_draw_labels
.no_console
        bsr     hud_draw_dynamic
.not_cockpit
        rts

        bss
        even
hud_target_x
        ds.w    1
hud_target_y
        ds.w    1
hud_line_sx
        ds.w    1
hud_line_sy
        ds.w    1
hud_clearance
        ds.b    1
        even
; DOS startup values 0000698D/0000560E/000063BB. Weapon selection remains
; unchanged in the attract replay because its gameplay dispatcher is deferred;
; the byte is still the original zero start state, not a visual substitute.
hud_weapon
        ds.b    1
hud_console_variant
        ds.b    1
hud_console_page
        ds.b    1
        even
hud_variant_x
        ds.l    6
hud_variant_y
        ds.b    6
        even

        text

; The twelve function-key labels across the bottom of the console, and the
; page each one selects.
;
; 000072EB draws exactly four elements, and the pairing is the whole trick:
; each MFD gets its PREVIOUS page's label drawn un-highlighted and its
; CURRENT page's label drawn highlighted, so the two blits together move the
; highlight without repainting the strip. The elements come in off/on pairs -
; left page n is 0x0D + n*2 off and 0x0E + n*2 on, right page n is 0x19 + n*2
; and 0x1A + n*2 - which is why the index arithmetic is `page*2 + base`.
;
; All three coordinate tables are static image data below the 0x32B20 content
; boundary and are transcribed rather than fitted:
;
;   0x72D4  y      166,166,166,226,226,226   two rows of three
;   0x72DA  x/4    21,28,35,21,28,35         left MFD  -> 84,112,140
;   0x72E0  x/4    47,54,61,47,54,61         right MFD -> 188,216,244
;
; DOS: flat 000072EB-000073C0, the four function-key label blits.
; DOS symbol: sub_000072EB
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: draws the same four CONS elements at the same coordinates.
; Preserved: element pairing, the previous/current order, both x tables, the
;   shared y table, the <<2 on x, and the [00019D86] console-phase gate.
; Kind: translated.
; Status: ported. The labels track the page bytes; what each PAGE then draws
;   into the MFD body is mfd_draw_panel's dispatch, which carries all six.
; The page-x margin below was measured as a +4 fault across this layer; it is
; now taken off at every page-x writer (sprite_draw_page and its two
; variants, hud_draw_solid_column, the horizon line, and - last, 2026-09-28 -
; the sight line's hud_plot_sight_pixel).
;
; DOS's Mode X page row is 0x52 bytes per plane - 82 x 4 = 328 pixels - and
; the visible window is 320, which is 80 bytes per plane. The two spare bytes
; are one byte column of margin at each side, so the window starts at page
; x = 4 and screen x = page x - 4. The offset is exactly ONE MODE X BYTE
; COLUMN; that is why it is 4 and not some arbitrary number.
;
; Every blitter here takes a page x - 00025B27 and 00025BB6 as a pixel,
; 00025C55 as a byte column, 00025A4D as a byte offset - and this port used to
; pass them through unchanged.
;
; Note the surface is 16-bit: 4 pixels is 8 BYTES. The
; correction belongs on the pixel x before it is doubled, not on the byte
; offset after - applying it to the byte offset halves it and leaves the
; layer 2 pixels out instead of 4.
;
; Four independent measurements against a DOS capture, all agreeing on +4:
; the SPEED label (page 44, DOS screen 40, port 44); the F1 highlight (DOS
; 71..88, port 75..92, same width); the sight line (page 0xA5 = 165, DOS
; screen 161); and the console ART correlated over three element-free strips,
; which prefers +4 in all three with a clear margin.
;
; The fix is one fact applied at every page-x-to-surface-x conversion, and it
; lives in the flight-side wrappers rather than in sprite_draw, because the
; menu and screen paths share that blitter and have not been measured. The
; sight line was the conversion that got missed: re-measured 2026-09-28 in the
; attract at VBL 4000, it left the fixed cross four pixels right of the gap
; the DOS captures show it leaving from.

; The dashed horizon reference across the sight, HUDS element 5.
;
; 0000D49A-0000D4B2 draws it at the sight centre (0xA5, 0x5A) through
; 00025BB6 - not the ordinary element blitter. What makes 00025BB6 different
; is one instruction: 00025C32 reads `[edi + 0x3CB4E]` with edi = x >> 1 and
; subtracts 0x52 times that from the row, so every column of the line is
; lifted by the same per-column horizon shear the terrain and sky use. That
; is why the line follows the horizon instead of lying flat.
;
; The index mapping is not a guess. The DOS displacement is 0x3CB4E against
; an array that starts at 0x3CB40, so the entry is (page x >> 1) + 14, and
; page x 0 is terrain column 14. This port holds a SURFACE x, which is page
; x - PAGE_VIEW_X, so the same entry is (surface x >> 1) + 16. That is
; TERRAIN_VIEW_FIRST, the column the span writer puts at surface x 0, so the
; two conversions check each other.
;
; Element 5 is 87 x 1 with hotspot (43,0): ten six-pixel dashes with
; three-pixel gaps, centred on the sight.
;
; DOS: flat 0000D49A-0000D4B2 with sub_00025BB6, horizon-sheared element blit.
; DOS symbol: sub_00025BB6
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: emits the same element with the same per-column shear into RGB565.
; Preserved: element, coordinates, hotspot handling, the x>>1 table index and
;   its +14 displacement, the upward row walk, and the option gate.
; Kind: adapted - chunky true-colour surface.
; Status: ported.
hud_draw_horizon_line
        movem.l d0-d7/a0-a3,-(sp)
        tst.w   hud_status
        bne     .done
        ; 0000D491: the third authored HUD option, beside Indicators and
        ; Compass. '{' is off, as it is for the other two.
        cmpi.b  #'{',menu_group_text+($267ac-$26607)
        beq     .done

        lea     hud_bank,a1
        lea     8*5(a1),a2                      ; 00025BE5: element 5's record
        moveq   #0,d5
        move.b  (a2),d5                         ; width
        moveq   #0,d6
        move.b  1(a2),d6                        ; height
        moveq   #0,d3
        move.b  2(a2),d3                        ; hotspot x
        moveq   #0,d4
        move.b  3(a2),d4                        ; hotspot y
        moveq   #0,d0
        move.b  7(a2),d0
        lsl.l   #8,d0
        move.b  6(a2),d0
        lsl.l   #8,d0
        move.b  5(a2),d0
        lsl.l   #8,d0
        move.b  4(a2),d0
        lea     0(a1,d0.l),a2                   ; 00025C16: the element data

        move.w  #$a5,d0
        sub.w   d3,d0                           ; 00025BFF: x -= hotspot x
        subi.w  #PAGE_VIEW_X,d0                 ; page x -> surface x
        move.w  #$5a,d1
        add.w   d4,d1                           ; 00025C08: y += hotspot y
        tst.w   d5
        beq     .done
        subq.w  #1,d5
        lea     backdrop_dy,a3
.col
        ; 00025C2E/00025C32/00025C3F: row -= table[(x >> 1) + 14].
        move.w  d0,d2
        lsr.w   #1,d2
        addi.w  #TERRAIN_VIEW_FIRST,d2
        cmpi.w  #TERRAIN_COLS,d2
        bhs     .flat
        move.w  0(a3,d2.w*2),d7
        ext.l   d7
        bra     .have_shear
.flat
        moveq   #0,d7
.have_shear
        move.w  d1,d3
        sub.w   d7,d3                           ; the sheared bottom row
        move.w  d6,d7
        subq.w  #1,d7
.row
        moveq   #0,d2
        move.b  (a2)+,d2                        ; 00025C41
        beq     .row_next                       ; 00025C44: 0 is transparent
        tst.w   d0
        bmi     .row_next
        cmpi.w  #SCREEN_WIDTH,d0
        bhs     .row_next
        tst.w   d3
        bmi     .row_next
        cmpi.w  #SCREEN_HEIGHT,d3
        bhs     .row_next
        move.l  work_screen,a0
        move.w  d3,d4
        mulu    #SCREEN_STRIDE,d4
        adda.l  d4,a0
        move.w  d0,d4
        add.w   d4,d4
        adda.w  d4,a0
        add.w   d2,d2
        move.l  sprite_palette,a1
        move.w  0(a1,d2.w),(a0)
        lea     hud_bank,a1
.row_next
        subq.w  #1,d3                           ; 00025C49: upward
        dbra    d7,.row
        addq.w  #1,d0                           ; 00025C4F
        dbra    d5,.col                         ; 00025C50
.done
        movem.l (sp)+,d0-d7/a0-a3
        rts

; What each MFD PAGE draws. All six are dispatched by mfd_draw_panel.
;
; 0000D693-0000D6FC dispatches both MFD bodies through a six-entry handler
; table at 0x19E10, indexed by the page byte. The table is static content and
; a capture of the running original reads it back unchanged:
;
;   page 0  0x075B0   the moving map          mfd_body_075B0
;   page 1  0x07710   upper-slot threat scope mfd_body_07710 (object.s)
;   page 2  0x07860   the target view         mfd_draw_target_view
;   page 3  0x076B0   the '*' goal counters   mfd_body_076B0
;   page 4  0x07530   the systems diagram     mfd_body_07530
;   page 5  0x07690   the key-help panel      mfd_body_07690
;   override 0x07670  the failed-MFD panel    mfd_body_07670
;
; The left body is drawn, [0x19CA8] is advanced by 0x1A - 26 bytes, which is
; 104 pixels in the original's Mode X, the distance between the two MFDs -
; the right body is drawn, and the offset is taken back off. Two override
; tests can replace the chosen handler ([0x1AA5] and [0x19E3E]/[0x19E3F]);
; neither fires in the captured attract, where they read 0xFF, 5 and 1.
;
; Page 2 is not a small routine.
; 00007860 pushes the camera basis, position, altitude and view angle, swaps
; in the LOCKED TARGET's own viewpoint - position from [ecx*4 + 0x20C6C] and
; [ecx*4 + 0x20E74], altitude from [ecx + 0x21A25], bearing from
; [ecx + 0x21CAF] with 0x32120/0x32320 as the sin/cos pair, ecx being the
; target index [0x19D10] - then calls 0001B26C and 00024B17 and pops all
; eight saved dwords back. The Falcon target handler preserves that order, with
; the object pass drawing directly into the RGB565 right-panel crop and using
; the archived target silhouette for terrain clipping. So the target view is a
; SECOND full terrain march from a second viewpoint, plus the object pass, not
; an overlay.
;
; That is also where compare-marcher.py's excluded columns come from:
; 0001B26C writes its own silhouette over byte offsets 0x58..0xA7 of every
; ring's record, so 80 of the 192 reference columns belong to this view.
; The two facts are the same fact, recorded here so the next reader does not
; have to rediscover it from the scoring harness.

mfd_draw_labels
        ; 000072EB gates the whole routine on the console phase byte. Without
        ; it the labels would paint over the menu and briefing screens, which
        ; share this surface.
        cmpi.b  #1,hud_console_variant
        bne     .done
        tst.w   instrument_status
        bne     .done
        movem.l d0-d3/a0-a1,-(sp)
        move.l  sprite_palette,-(sp)
        move.l  #instrument_palette,sprite_palette

        moveq   #$0d,d3                         ; 00007302: left, off
        move.b  mfd_page_left_prev,d0
        bsr     .label_left
        moveq   #$0e,d3                         ; 00007334: left, on
        move.b  mfd_page_left,d0
        bsr     .label_left
        moveq   #$19,d3                         ; 00007366: right, off
        move.b  mfd_page_right_prev,d0
        bsr     .label_right
        moveq   #$1a,d3                         ; 00007398: right, on
        move.b  mfd_page_right,d0
        bsr     .label_right

        move.l  (sp)+,sprite_palette
        movem.l (sp)+,d0-d3/a0-a1
.done
        rts

.label_left
        lea     mfd_label_x_left,a1
        bra     .label
.label_right
        lea     mfd_label_x_right,a1
.label
        ; The DOS index is a byte and the tables have six entries; a page
        ; outside 0..5 cannot be produced by the key cases below, but the
        ; read would leave the table if one ever were, so bound it where DOS
        ; bounds it - at the writer.
        ; Whole longs throughout. The page arrives as a byte through a
        ; `move.b`, which leaves the top three bytes of d0 as whatever the
        ; caller had there, and sprite_draw_opaque takes its element in a
        ; LONG - so a word-sized `move.w d0,d1` here carries that garbage
        ; into the index and the blitter reads far outside the bank. That is
        ; what the red screen was.
        andi.l  #$ff,d0
        move.l  d0,d1
        add.l   d1,d1                           ; 00007302: page*2
        add.l   d3,d1                           ; + the off/on base
        moveq   #0,d2
        move.b  0(a1,d0.w),d2
        lsl.l   #2,d2                           ; 0000731D: shl eax, 2
        moveq   #0,d3
        move.b  mfd_label_y(pc,d0.w),d3
        move.l  d1,d0
        move.l  d2,d1
        move.l  d3,d2
        move.l  work_screen,a0
        lea     instrument_bank,a1
        jsr     sprite_draw_page_opaque
        rts

mfd_label_y
        dc.b    166,166,166,226,226,226         ; 0x72D4
mfd_label_x_left
        dc.b    21,28,35,21,28,35               ; 0x72DA, x = entry << 2
mfd_label_x_right
        dc.b    47,54,61,47,54,61               ; 0x72E0
        even

        data
        even
; 0x72E6-0x72EA in the image, and these are its shipped values - the right
; MFD starts on page 1, the left on page 0. They are initialised data, not
; BSS: zeroing them would start the right MFD on a page the original never
; starts on.
mfd_page_left
        dc.b    0                               ; 0x72E6
mfd_page_right
        dc.b    1                               ; 0x72E7
mfd_page_left_prev
        dc.b    0                               ; 0x72E8
mfd_page_right_prev
        dc.b    0                               ; 0x72E9
mfd_page_dirty
        dc.b    0                               ; 0x72EA
        even
; [0x19C90], the map zoom 00007580 and 000075B5 read. Static content at
; 0x19C90 that ships as 0x08000000; 0000D660/0000D67F step it at runtime.
mfd_zoom
        dc.l    MFD_ZOOM
; [0x19CA8] in pixels: 0 while the left MFD body draws, MFD_PANEL_STEP while
; the right one does. 00005604 zeroes it; 0000D6BF/0000D6FC move it.
mfd_body_offset
        dc.w    0
        even

threat_sound_now
        ds.b    1
threat_sound_prev
        ds.b    1
        even

        end
