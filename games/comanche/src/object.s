; Route: analysis/functions/falcon-attract.md#object-pass.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; DOS origin: object table 0001FC30-00021FBC, allocator 00023297,
;   spawn-at-parent 000227D8, update pass 000234A4.
; Purpose: the object table and the per-frame pass over it.
; Inputs/outputs: object_update_pass is called from frame_driver at the point
;   the original calls 000234A4. Handlers receive the object pointer in a0 and
;   its 1-based index in d6.
; Original globals/side effects: the DOS table is a structure-of-arrays -
;   14 dword fields of 130 entries at stride 0x208, then 13 byte fields at
;   stride 0x82, all 1-based because every access is `[reg*4 + base-4]`.
; Falcon replacement notes: that layout is 386 addressing, not a contract, and
;   X86-M68K-MAP.md says not to reproduce it field-scattered. One array of
;   structs holds the same fields; the DOS field number of each is in the
;   comment beside it so the map stays followable in both directions.
; Validation: build, frame capture unchanged, and a debugger dump of the table
;   after init showing every slot inactive.

        include "inc/comanche.s"
        include "inc/snd.s"
        ; TERRAIN_COLS for the targetability test's horizon index.
        include "dsp/proto.inc"
        xref    sine_q31, ring_mul_q31_raw, mfd_march_target_view
        xref    sprite_palette_variant, sprite_y_extra
        xref    mfd_target_silhouette, mfd_view_sin, mfd_view_cos, mfd_nolock_buf
        xref    player_x, player_y, player_altitude
        xref    view_sin, view_cos
        ; 000079D1/000079DE draw the RANGE readout through the same two
        ; helpers the flight HUD uses - 00025B27 and 0000D8F5.
        xref    sprite_draw_page, hud_draw_value, hud_bank, hud_palette
        xref    hud_variant_x, hud_variant_y, hud_console_page

        global  object_init, object_update_pass, object_alloc, object_update_done
        global  countermeasure_tick
        global  object_spawn_at_parent, object_scan_upper, object_move
        global  object_state_static, object_state_idle, object_state_wreckage
        global  object_launch_flare, object_launch_chaff, weapon_fire_rocket
        global  object_terrain_probe
        global  object_draw_pass, object_draw_sprite, object_spawn_mission
        global  object_target_cycle, object_target_latch, object_target_default
        global  mfd_draw_target_view
        global  object_target_validate, hud_target_range
        global  object_blast
        global  player_hit_flag, player_death_cue
        global  object_aspect
        global  object_table, mfd_draw_markers, mfd_body_07710
        global  object_endcue_hold
        global  object_fixed_position
        global  object_target_view
        global  weapon_dispatch, weapon_dispatch_done, weapon_banks_load
        global  object_draw_frame

        global  mission_object_count, mission_obj_x, mission_obj_y
        global  mission_obj_heading, mission_obj_type
        global  mission_obj_f1, mission_obj_f2, mission_obj_f3
        global  mission_obj_f7, mission_obj_f8, mission_obj_f9
        global  mission_obj_flag
        global  mission_obj_f10
        global  mission_sprite_banks, mission_sprite_palettes
        global  mission_sprite_status
        global  sprite_palette
        global  object_draw_pair_24e05, object_draw_pair_24fed
        global  object_no_shear, object_project_page
        xref    mission_fuel, flt_fuel
        global  ally_wrecked, object_clear_active

; Sized by 130, not by the allocator's 30. The allocator scans only the first
; 30 slots for a free one, but the update pass walks all 130 - slots past the
; first 30 are populated another way, and an array sized by the allocator's
; bound would silently drop them. That asymmetry is real in the original and is
; the kind of thing that would only show up as missing objects much later.
OBJ_COUNT       = 130
OBJ_ALLOC_LIMIT = 30
; DOS 000227BF scans the disjoint transient/effect pool: 130 down to 31.
OBJ_SCAN_UPPER_LIMIT = 100
OBJECT_BANK_BYTES = 168000
; The selected .DTL's recovered ring count, shared with render.s through the
; generated table. Kept local because the generated include owns the public
; symbol. 00026240 loads medium.dtl for detail byte [00025DD4] = '1', which is
; what the shipped install runs, and its declared count is 180 - confirmed by
; two QMP captures reading [0x19EE0]. This was 250, high.dtl's count, and the
; ring search walked 70 entries past the end of a 180-entry table.
;
; It is no longer a constant. src/dtl.s loads the file the Detail menu names,
; so the count is whatever that file declares - 250, 180 or 100 - and the word
; ring_steps carries it. Baking 180 in here would put the same off-the-end
; walk back the moment the setting moved off medium.
        xref    ring_steps

; Field offsets (OBJ_SPEED .. OBJ_SIZE) live in inc/comanche.s, shared with debrief.s.

        text

; Start a mission's object table the way 000227A6 does: clear the 130 active
; flags and nothing else. Every other per-slot array keeps what it held, so a
; field the allocator at 00023297 never writes (the timer at 00021E35, the
; steering latch 00021EB7, the sprite 000219A3, the previous position, the
; target latch 00021BAB) carries the last mission's value into the next
; mission's objects. That is measured, not argued: DEMO2's tanks start with
; timers 11, 11, 11, 22, 11, 209 and 46, which is where DEMO1 left those slots
; (work/replay_dos/objects-pass1.json, row 0), while DEMO1's own tanks, flown
; from the program image, start at 0.
;
; The first call also lays the program image's values down, because the table
; lives in BSS here and the original's lives in initialised data: every slot's
; altitude and previous altitude 170, sprite 1, and the position and previous
; position (0x40000000, 0xD4800000). The other arrays are zero in the image
; (read from re/unpacked/comanche-flat32.bin, slots 1-130).
; DOS: flat 000227A6-000227BE, object-table reset (called from the attract
; entry at 000056BF); table storage 0001FC30-00021FBC; the fixed-phase byte
; [00019D86] is set to 1 at 0000698D.
; DOS symbol: sub_000227A6
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: clears the 130 Falcon active flags; first call seeds the image.
; Preserved: inactive start state, table capacity, and every other field's
;   carry-over between missions; 386 field layout is native.
; Difference: the Falcon struct also holds state/draw/fire pointers and
;   palettes, which are Falcon addresses and are rewritten by the factory
;   before the slot is next active; the image's DOS pointers are not kept.
; Kind: translated; struct layout is Falcon storage.
; Status: ported; the carry-over is measured against the DEMO2 oracle.
; 000227A6: what a mission's end does to the object table - the 130 active
; flags go to zero, [00022368] (the allied object) and [00022384] (the ally's
; wreck flag) with them; every other array keeps its bytes, the same carry-over
; object_init describes.
; DOS: flat 000227A6-000227BE, object table reset.
; DOS symbol: sub_000227A6
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: the same stores over the Falcon object table.
; Preserved: the 130 flags and nothing else.
; Kind: translated.
; Status: ported.
object_clear_active
        movem.l d0/a0,-(sp)
        lea     object_table,a0
        move.w  #OBJ_COUNT-1,d0
.clear
        clr.b   OBJ_ACTIVE(a0)                  ; 000227AB-000227B2 rep stosb
        lea     OBJ_SIZE(a0),a0
        dbra    d0,.clear
        clr.l   object_ally                     ; 000227B4 [00022368]
        clr.b   ally_wrecked                    ; 000227B9 [00022384]
        movem.l (sp)+,d0/a0
        rts

object_init
        tst.b   object_image_ready
        bne     .image_done
        st      object_image_ready
        lea     object_table,a0
        move.w  #OBJ_COUNT-1,d0
.image
        move.b  #170,OBJ_ALTITUDE(a0)
        move.b  #170,OBJ_PREV_ALT(a0)
        move.b  #1,OBJ_SPRITE(a0)
        move.l  #$40000000,OBJ_X(a0)
        move.l  #$40000000,OBJ_PREV_X(a0)
        move.l  #$D4800000,OBJ_Y(a0)
        move.l  #$D4800000,OBJ_PREV_Y(a0)
        lea     OBJ_SIZE(a0),a0
        dbra    d0,.image
.image_done
        lea     object_table,a0
        move.w  #OBJ_COUNT-1,d0
.clear
        clr.b   OBJ_ACTIVE(a0)                  ; 000227A6: the 130 active flags
        lea     OBJ_SIZE(a0),a0
        dbra    d0,.clear
        move.b  #1,view_variant                 ; 0000698D: [00019D86] = 1
        clr.b   object_chaff_active             ; 0000685E [00019D8F] = 0
        clr.b   object_flare_active             ; 00006865 [00019D90] = 0
        move.l  mission_fuel,flt_fuel           ; 0000686C-00006871 [00019D60] = [00019D5C]
        rts

; DOS 000234A4. Walk every slot, skip the inactive ones, and call the object's
; own state handler through its field-1 pointer.
;
; The original counts DOWN from 130 to 1, so slot 130 is serviced first and
; slot 1 last. That order is kept: a handler may spawn, and a spawn takes the
; highest free slot the allocator finds, so ascending order would let a freshly
; spawned object run in the same frame that created it.
; DOS: flat 000234A4, descending 130-slot object update pass.
; DOS symbol: sub_000234A4
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: calls only active Falcon handlers in the original slot order.
; Preserved: inactive skip, handler dispatch, descending order, spawn timing.
; Kind: translated.
; Route: analysis/functions/falcon-attract.md#object-pass.
; Status: ported; the traced attract transition installs the recovered
; draw/state entries before replay, and the pass walks them in DOS order.
object_update_pass
        movem.l d6-d7/a0-a1,-(sp)
        clr.b   object_threat_chaff             ; 000234A4 [00019D92] = 0
        clr.b   object_threat_bull              ; 000234AB [00019D94] = 0
        move.w  #OBJ_COUNT,d6                   ; 1-based index, high to low
        lea     object_table+(OBJ_COUNT-1)*OBJ_SIZE,a0
.next
        tst.b   OBJ_ACTIVE(a0)
        beq     .skip
        move.l  OBJ_STATE(a0),d7
        beq     .skip
        move.l  d7,a1
        movem.l d6/a0,-(sp)
        jsr     (a1)
        movem.l (sp)+,d6/a0
.skip
        lea     -OBJ_SIZE(a0),a0
        subq.w  #1,d6
        bne     .next
; Probe point for tools/trace-falcon-objects.py: every state has run, nothing
; has drawn - the instant work/trace_replay_flight.py --objects samples DOS at
; 000234CE. Target artefact, no DOS counterpart.
object_update_done
        movem.l (sp)+,d6-d7/a0-a1
        rts

; DOS 00023297. Find a free slot, scanning the first OBJ_ALLOC_LIMIT downward.
; Out: a0 = the slot and d6 = its 1-based index, or a0 = 0 when the table is
; full. Test a0, not the flags - the scan's own DBcc leaves those set by the
; loop counter rather than by the result.
; DOS: flat 00023297, first-30-slot descending allocator.
; DOS symbol: sub_00023297
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: finds a free Falcon object struct and returns its 1-based index.
; Preserved: allocation bound, scan order, full-table result, and slot identity.
; Kind: translated.
; Status: ported; live-mission setup calls the recovered allocator.
object_alloc
        move.w  #OBJ_ALLOC_LIMIT,d6
        lea     object_table+(OBJ_ALLOC_LIMIT-1)*OBJ_SIZE,a0
.next
        tst.b   OBJ_ACTIVE(a0)
        beq     .found                          ; d6 is the index, a0 the slot
        lea     -OBJ_SIZE(a0),a0
        subq.w  #1,d6
        bne     .next
        suba.l  a0,a0                           ; full: a0 = 0
.found
        rts

; DOS 000227D8. Activate a free slot as a child of the object in a1, cloning
; the parent's position and altitude. The original also installs a state and
; draw handler and a model pointer; those are left to the caller here, because
; on the Falcon they are addresses of ported routines rather than the DOS
; constants the original writes.
;
; In:  a1 = parent object
; Out: a0 = new object and d6 = its index, or a0 = 0 if the table was full
; DOS: flat 000227D8, child allocation/position clone.
; DOS symbol: loc_000227D8
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: clones authored parent position/altitude into a free Falcon slot.
; Preserved: inherited coordinates, previous position, active flag, and count.
; Kind: translated.
; Status: ported; caller must supply the recovered state/draw/model handlers.
object_spawn_at_parent
        move.l  a1,-(sp)
        bsr     object_alloc
        bsr     object_clone_fields
        move.l  (sp)+,a1
        rts

; DOS: flat 000227D8-0002283C, the explosion child both 000227BF callers get.
; ebx is the chosen slot and ecx the parent, and what it writes is not a copy
; of the parent but a fresh BOOM effect standing where the parent is:
;   000227DA  aux [00021DB3] = 0          000227E1  active = 1
;   000227E8  state = 000237B0 (wreckage) 000227F3  draw  = 0002519D (frame)
;   000227FE  model A = [00019E88], BOOM  0002280A  sprite [000219A3] = 1
;   00022811-00022833  X, Y and altitude from the parent
; Nothing else is written - not the previous-position copies, not the timer,
; not the destruction byte. The state at 000237B0 only counts the sprite byte
; and the draw handler indexes BOOM's frames by it, so none of them is read.
; 00022839-00022876 then derives a sound from the player's distance; sound is
; outside this milestone.
; DOS symbol: loc_000227D8
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: installs the BOOM wreckage handler pair at the parent's position.
; Preserved: the field set and the stored values, in the original's order.
; Difference: if BOOM.RLE failed to load DOS would never have got here
;   (00006797 jumps to the resource-error exit), so a null bank leaves the
;   child without a model pointer, as object_transition_home does (Target
;   artefact). The distance-keyed sound at 00022839-00022876 is not ported.
; Kind: translated.
; Status: ported. This used to copy the parent and install no handlers, so the
;   child of every destroyed object was an inert active slot that drew nothing.
object_clone_fields
        move.l  a0,d0
        beq     .full
        clr.b   OBJ_AUX(a0)                     ; 000227DA
        move.b  #1,OBJ_ACTIVE(a0)               ; 000227E1
        move.l  #object_state_wreckage,OBJ_STATE(a0)    ; 000227E8
        move.l  #object_draw_frame,OBJ_DRAW(a0)         ; 000227F3
        tst.l   weapon_bank_boom
        beq     .no_boom
        move.l  weapon_bank_boom,OBJ_MODEL_A(a0)        ; 000227FE [00019E88]
        move.l  weapon_palette_boom,OBJ_PALETTE_A(a0)
.no_boom
        move.b  #1,OBJ_SPRITE(a0)               ; 0002280A [000219A3]
        move.l  OBJ_X(a1),OBJ_X(a0)             ; 00022811
        move.l  OBJ_Y(a1),OBJ_Y(a0)             ; 0002281F
        move.b  OBJ_ALTITUDE(a1),OBJ_ALTITUDE(a0)       ; 0002282D
        bsr     object_boom_sound                       ; 00022839-00022876, the parent a1
.full
        rts

; The explosion's sound: SND1 id 1 at the distance class of an object from the
; viewer, silent beyond class 4. In: a1 = the object whose X/Y it is measured at.
; DOS: flat 00022839-0002287C (the tail of the explosion child, parent ecx) and
;   000249EF-00024A32 (the tail of the destruction transition, the object ecx):
;   the same code twice.
; DOS symbol: tails of loc_000227D8 and loc_00024997
; Record: analysis/functions/sound-falcon.md#call-sites
; Port: |viewer X - X| and |viewer Y - Y| as one's-complement magnitudes (cdq/xor),
;   the larger plus half the smaller, >> 29 = the class dl; a class <= 4 calls
;   SND1 id 1 with bl = $FF, ecx = 0.
; Preserved: the one's-complement magnitude, the unsigned max/min order, the
;   shift of 29 and the cut-off at 4; the viewer is the live [00019CD4]/[00019CD8].
; Difference: none in the arithmetic; the sound leaves the simulation untouched
;   (all registers and the flags are kept).
; Kind: translated.
; Status: ported; the effect itself is checked by tools/check-falcon-sound.py.
object_boom_sound
        movem.l d0-d3,-(sp)
        moveq   #31,d3
        move.l  flt_x,d0                        ; 00022839 [00019CD4]
        sub.l   OBJ_X(a1),d0                    ; 0002283E
        move.l  d0,d1
        asr.l   d3,d1                           ; 00022845 cdq: the sign, all ones or zero
        eor.l   d1,d0                           ; 00022846 xor eax,edx
        move.l  d0,d2                           ; 00022848 ebx = |dx|
        move.l  flt_y,d0                        ; 0002284A [00019CD8]
        sub.l   OBJ_Y(a1),d0                    ; 0002284F
        move.l  d0,d1
        asr.l   d3,d1
        eor.l   d1,d0                           ; 00022857 eax = |dy|
        cmp.l   d2,d0                           ; 00022859 cmp eax,ebx
        bhi     .ordered                        ; 0002285B ja
        exg     d0,d2                           ; 0002285D xchg ebx,eax
.ordered
        lsr.l   #1,d2                           ; 0002285E
        add.l   d2,d0                           ; 00022860
        moveq   #29,d1
        lsr.l   d1,d0                           ; 00022862 shr eax,0x1d
        cmpi.l  #4,d0                           ; 00022865
        bhi     .quiet                          ; 00022868 ja
        SndFXDist                               ; 0002286A-00022876
.quiet
        movem.l (sp)+,d0-d3
        rts

; DOS: flat 000227BF-000227D7, the transient/effect allocator: ebx starts at
; 0x82 and ecx counts 0x64 slots down, so it searches 130 back to 31 and
; returns empty-handed rather than falling into the first thirty.
; DOS symbol: sub_000227BF
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: scans the upper hundred slots and enters the shared clone tail.
; Preserved: the descending order, the hundred-slot bound, the free test on
; the active byte, and the exhausted-pool return.
; Kind: translated.
; Status: ported; callers still owe their recovered handler/model triple.
object_scan_upper
        movem.l d7/a1,-(sp)
        move.w  #OBJ_COUNT,d6
        lea     object_table+(OBJ_COUNT-1)*OBJ_SIZE,a0
        move.w  #OBJ_SCAN_UPPER_LIMIT,d7
.next
        tst.b   OBJ_ACTIVE(a0)
        beq     .found
        lea     -OBJ_SIZE(a0),a0
        subq.w  #1,d6
        subq.w  #1,d7
        bne     .next
        suba.l  a0,a0
.found
        bsr     object_clone_fields
        movem.l (sp)+,d7/a1
        rts

; DOS 000248E4-00024914, the object mover.
;
; The original reads the heading byte at 0002189F and does
; `mov eax,[speed] / imul dword [ebx*8 + 00032320] / sub [Y],edx` and then the
; same against [ebx*8 + 00032120] added into X - a 32x32 multiply keeping the
; HIGH dword of the product against the Q31 table, the same -Y-forward pair
; the flight core uses at 00019526-0001954F. Positions are 10.22 on both
; sides, so the high dword is the step as it stands. The table is the exact Q31
; sine_q31 at [heading * 8] bytes (2 * heading entries), cosine 128 entries on
; (00032320 - 00032120 = 0x200 bytes).
;
; The multiply stays 64-bit: speed * sine reaches 0x04000000 * 0x7FFFFFFF.
;
; In: a0 = object
; DOS: flat 000248E4-00024914, object mover.
; DOS symbol: loc_000248E4
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: advances object coordinates with the Q31 heading pair.
; Preserved: 64-bit products, high-dword truncation, the sine-to-X and
;   cosine-to-Y pairing and the Y subtraction.
; Kind: translated.
; Status: ported; checked against the DOS object snapshots in
;   work/replay_dos/objects-demo1.json, bit-exact.
object_move
        movem.l d0-d3/a1,-(sp)
        moveq   #0,d3
        move.b  OBJ_HEADING(a0),d3
        lsl.w   #3,d3                           ; 000248E4 ebx*8
        lea     sine_q31,a1

        move.l  OBJ_SPEED(a0),d0                ; 000248EB [ecx*4 + 0001FE34]
        move.l  512(a1,d3.w),d2                 ; 000248F2 [ebx*8 + 00032320]
        MulS64  d2
        sub.l   d1,OBJ_Y(a0)                    ; 000248F9 `sub`, not add

        move.l  OBJ_SPEED(a0),d0                ; 00024900
        move.l  0(a1,d3.w),d2                   ; 00024907 [ebx*8 + 00032120]
        MulS64  d2
        add.l   d1,OBJ_X(a0)

        movem.l (sp)+,d0-d3/a1
        rts

; The height under an object, and the altitude it is trying to hold.
; DOS 00024915-0002493B.
;
; The original indexes the map with `shld ebx,eax,0xa` twice, taking the top ten
; bits of Y then of X out of its 10.22 coordinates. This port keeps positions in
; 16.16, so the same ten bits come off a `swap` and a mask; the formula below is
; the part that carries meaning.
;
; The target is the sample doubled plus 20, saturating at 255. Doubling is the
; unit conversion - a DOS altitude step is half a map height unit - and the 20
; is the clearance a moving object holds above the ground.
;
; In:  a0 = object
; Out: d0.b = raw map height beneath it, d1.b = altitude it is heading for
; DOS: flat 00024915-0002493B, object terrain sample/clearance target.
; DOS symbol: inside loc_000248E4
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: samples the loaded height map using the original 10-bit map index.
; Preserved: byte height, doubled target, saturation, and map wrapping.
; Kind: translated.
; Status: ported; covered by object-state arithmetic review.
object_ground_sample
        movem.l d2-d3/a3,-(sp)
        lea     original_height_map,a3
        ; 00024915-0002492D: `shld ebx,eax,0xa` twice - the top ten bits of Y,
        ; then of X, as (Y >> 22) << 10 | (X >> 22). The positions are 10.22.
        moveq   #22,d1
        move.l  OBJ_Y(a0),d2
        lsr.l   d1,d2
        lsl.l   #8,d2
        lsl.l   #MAP_SHIFT-8,d2
        move.l  OBJ_X(a0),d3
        lsr.l   d1,d3
        add.l   d3,d2
        moveq   #0,d0
        move.b  0(a3,d2.l),d0
        move.w  d0,d1
        add.w   d1,d1
        addi.w  #20,d1
        cmpi.w  #255,d1
        bls     .fits
        moveq   #-1,d1                          ; the `mov al,0xff` saturate
.fits
        movem.l (sp)+,d2-d3/a3
        rts


; DOS 00024997, the transition both of those paths reach.
;
; It is a respawn, not a death. The original reinstalls the default state
; 000237B0 and the scaled-sprite draw handler 0002519D, sets the sprite index to
; 1, and copies the object's home X, Y and altitude - fields 0002107C, 00021284
; and 00021AA7 - back over its live position. The object carries on from where
; it started.
;
; The port used to clear OBJ_ACTIVE here. That was a stand-in and it was wrong
; in a way that mattered: it drained the table over a mission instead of
; recycling it, so a long flight ended with nothing left to see.
;
; In: a0 = object
; DOS: flat 00024997-000249E9, the shared destruction transition.
; DOS symbol: loc_00024997
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: installs the recovered wreckage handler pair and rolls the object back
; to its latched previous position.
; Preserved: the two handler pointers, the auxiliary-byte clear, the sprite
; index, and the X/Y/altitude restore, in the original's order.
; 000249B4-000249B9 also sets field 2 to the shared bank [00019E88], BOOM,
; which weapon_banks_load binds (000066E2-000067AE). BOOM has no `3D` model
; record: its twenty frames are indexed by the sprite byte that
; object_state_wreckage counts up, which is why the draw handler is 0002519D
; (object_draw_frame), not 0002514D's aspect path.
; Difference: if BOOM.RLE failed to load, DOS would never have reached here -
;   00006797 jumps to the resource-error exit at 00006400. This port keeps
;   field 2 as it was rather than bind a bank that does not exist (Target
;   artefact).
; Kind: translated.
; Status: ported.
; Note: the two `prev = prev` stores and the extra altitude write that used to
; follow the restore had no counterpart at all; 000249C7-000249E9 reads the
; latched triple and writes only X, Y and the altitude byte.
object_transition_home
        move.l  #object_state_wreckage,OBJ_STATE(a0)  ; 00024997 [00020244]=000237B0
        move.l  #object_draw_frame,OBJ_DRAW(a0)       ; 000249A2 [0002003C]=0002519D
        clr.b   OBJ_AUX(a0)                           ; 000249AD [00021DB3]=0
        tst.l   weapon_bank_boom
        beq     .no_boom
        move.l  weapon_bank_boom,OBJ_MODEL_A(a0)      ; 000249B4 [0002044C]=[19E88]
        move.l  weapon_palette_boom,OBJ_PALETTE_A(a0)
.no_boom
        move.b  #1,OBJ_SPRITE(a0)                     ; 000249C0 [000219A3]=1
        move.l  OBJ_PREV_X(a0),OBJ_X(a0)              ; 000249C7
        move.l  OBJ_PREV_Y(a0),OBJ_Y(a0)              ; 000249D5
        move.b  OBJ_PREV_ALT(a0),OBJ_ALTITUDE(a0)     ; 000249E3
        move.l  a1,-(sp)
        move.l  a0,a1
        bsr     object_boom_sound                     ; 000249EF-00024A32, the object ecx
        move.l  (sp)+,a1
        rts


; Roll back to the latched previous position, move one step at the caller's
; heading, resample the map with this routine's own *2+11 law, and leave the
; comparison flags for the steering state to branch on.
;
; 00023B45 is `cmp byte [00021A25 + slot], al` - the object's altitude minus
; the probed ground, in that order. This used to be written as `cmp.b
; OBJ_ALTITUDE(a0),d0`, which on the 68030 is d0 minus the operand and so
; carries the opposite sign for every caller that looks past equality.
; In: a0 = object, OBJ_HEADING already set by the caller.
; Out: flags of (altitude - probed ground), byte-wide.
; DOS: flat 00023AD0-00023B4B, object terrain probe.
; DOS symbol: sub_00023AD0
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: reverts, steps, samples the authored map and sets the same flags.
; Preserved: the previous-position rollback, the heading step, the byte
; `shl 1 / add 0x0B` law with its 0xFF saturation, and the compare order.
; Kind: translated.
; Status: ported; used only by recovered object-state handlers.
object_terrain_probe
        movem.l d0-d1,-(sp)
        move.l  OBJ_PREV_X(a0),OBJ_X(a0)
        move.l  OBJ_PREV_Y(a0),OBJ_Y(a0)
        bsr     object_move
        bsr     object_ground_target_b
        move.b  OBJ_ALTITUDE(a0),d1
        cmp.b   d0,d1                            ; 00023B45 cmp [alt], al
        movem.l (sp)+,d0-d1
        rts

; The altitude a ground unit holds over the map cell it stands in: the sample
; doubled in BYTE arithmetic, plus 0x0B, saturating at 0xFF on the add's carry.
; DOS 00023B1D-00023B43, and the same instructions again at 00023D77-00023D9D.
; The `shl al,1` drops its own carry, so a height of 0x80 or more wraps; only
; the ADD saturates.
; The clearance differs by unit type - 0x0B here, 0x2C in 00024001-00024027
; (the default state), 0x22 in 00023994-000239BA (the ally) - so the add is
; object_ground_target_k's d1.b and object_ground_target_b is the 0x0B entry.
; In:  a0 = object, d1.b = clearance for _k. Out: d0.b = target (d0 bits 8-31
; clear); d1 is clobbered by _b.
; DOS: flat 00023B1D-00023B43, ground clearance target.
; DOS symbol: inside sub_00023AD0
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: the same map index, doubled byte, +0x0B and saturate.
; Preserved: byte wrap of the doubling, carry-only saturation.
; Kind: translated.
; Status: ported.
object_ground_target_b
        moveq   #$0b,d1
object_ground_target_k
        movem.l d2-d4/a3,-(sp)
        lea     original_height_map,a3
        ; 00024915-0002492D: `shld ebx,eax,0xa` twice - the top ten bits of Y,
        ; then of X, as (Y >> 22) << 10 | (X >> 22). The positions are 10.22.
        moveq   #22,d4
        move.l  OBJ_Y(a0),d2
        lsr.l   d4,d2
        lsl.l   #8,d2
        lsl.l   #MAP_SHIFT-8,d2
        move.l  OBJ_X(a0),d3
        lsr.l   d4,d3
        add.l   d3,d2
        moveq   #0,d0
        move.b  0(a3,d2.l),d0
        add.b   d0,d0
        add.b   d1,d0                            ; 00023B3F add al, 0x0B
        bcc     .fits
        moveq   #-1,d0                           ; 00023B43 al = 0xFF
.fits
        movem.l (sp)+,d2-d4/a3
        rts

; DOS: flat 00023B50-00023CE4, dispatch-table index 9. The routine is decoded
; and retained even though no decoded mission currently places that type.
; DOS symbol: inside loc_00023B45
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: runs the recovered latch, health gate, hold countdown and three-probe
; steering, and the two-stage destruction tail.
; Preserved: the 00023B63-00023B85 latch into the previous-position triple,
; the health test against 2, the [00022028] hold decrement, the +0x20/-0x40/
; +0x60 heading probes at 00023C1D-00023C45 and the 00023C93 revert.
; Difference: none; 00023CC8-00023CCA's voice cue (SPEAK1 id 1) is made, see src/sound.s.
; Kind: translated.
; Status: ported but unwired; the spawned effect's handler triple is open.
object_state_static
        tst.b   OBJ_DAMAGE(a0)
        bne     .destruct
        addq.b  #1,OBJ_TIMER(a0)
        move.l  OBJ_X(a0),OBJ_PREV_X(a0)
        move.l  OBJ_Y(a0),OBJ_PREV_Y(a0)
        move.b  OBJ_ALTITUDE(a0),OBJ_PREV_ALT(a0)
        cmpi.b  #2,OBJ_HEALTH(a0)
        bls     .ret
        tst.l   OBJ_HOLD(a0)
        beq     .steer
        subq.l  #1,OBJ_HOLD(a0)
        bra     .ret
.steer
        moveq   #0,d0
        move.b  OBJ_HEADING(a0),d0
        move.w  d0,-(sp)
        tst.b   OBJ_STEER_DIR(a0)
        bmi     .minus
        bne     .plus
        addi.b  #$20,OBJ_HEADING(a0)
        bsr     object_terrain_probe
        beq     .plus
        subi.b  #$40,OBJ_HEADING(a0)
        bsr     object_terrain_probe
        beq     .minus
        addi.b  #$60,OBJ_HEADING(a0)
        bsr     object_terrain_probe
        beq     .plus
.minus
        move.w  (sp)+,d0
        move.b  d0,OBJ_HEADING(a0)
        move.l  OBJ_SPEED(a0),d0
        lsr.l   #8,d0
        lsr.l   #8,d0
        lsr.l   #5,d0
        sub.b   d0,OBJ_HEADING(a0)
        moveq   #-1,d0
        move.b  d0,OBJ_STEER_DIR(a0)
        bra     .revert
.plus
        move.w  (sp)+,d0
        move.b  d0,OBJ_HEADING(a0)
        move.l  OBJ_SPEED(a0),d0
        lsr.l   #8,d0
        lsr.l   #8,d0
        lsr.l   #5,d0
        add.b   d0,OBJ_HEADING(a0)
        moveq   #1,d0
        move.b  d0,OBJ_STEER_DIR(a0)
.revert
        move.l  OBJ_PREV_X(a0),OBJ_X(a0)
        move.l  OBJ_PREV_Y(a0),OBJ_Y(a0)
.ret
        rts
.destruct
        cmpi.b  #1,OBJ_DAMAGE(a0)
        bhi     .stage2
        addq.b  #1,OBJ_DAMAGE(a0)
        move.l  a0,-(sp)
        move.l  a0,a1
        bsr     object_scan_upper
        SndSpeechA 1                            ; 00023CC8-00023CCA: SPEAK1 id 1
        move.l  (sp)+,a0
        rts
.stage2
        addq.b  #1,OBJ_DAMAGE(a0)
        cmpi.b  #$f,OBJ_DAMAGE(a0)
        bne     .ret
        bra     object_transition_home

; DOS: flat 00023CF0-00023F23, the mobile ground unit's state: dispatch types 2
; and 5 (factories 000233DB and 000233F7), which is every tank DEMO1 places.
;
; One tick, in the original's order:
;   00023CF0  destruction byte [00021B29] set -> the damage tail 00023F24
;   00023CFD  timer + 1; latch X, Y and altitude into the previous-tick copies
;   00023D2B  health at or below 6 -> no motion, straight to the aim at 00023E55
;   00023D38  hold [00022028] nonzero -> count it down, same
;   00023D46  move along the heading (000248E4's pair of Q31 products)
;   00023D77  ground target = height*2 + 0x0B, saturating; equal to the
;             object's own altitude -> steer byte [00021EB7] = 0 and done
;   00023DAB  otherwise turn. With a steer direction already latched, take it;
;             with none, probe +0x20, then -0x40 from that, then +0x60 from that
;             through 00023AD0 and take the first heading whose step lands on
;             the object's own altitude, defaulting to minus. The turn is
;             (speed >> 21) + 1 either way, and the move is reverted to the
;             latched position (00023E27).
;   00023E55  the aim, below.
;
; The aim at 00023E55 is the tank's weapon logic. It points
; 000256C8's origin at the viewer's frame snapshot [00019CDC]/[00019CE0] and
; takes the bearing to itself and the distance estimate esi it leaves:
;   limit = (player altitude << 20) + 0x1E000000, plus 0x87 if the object
;           passed this frame's targetability test (00023E78 [00021BAB])
;   esi >= limit             -> nothing
;   [00019DB8] & 0xC and a chaff already in the air [00019D8F] -> nothing
;   [00019D92] = 1           -> the threat flag 00019555 turns into chaff
;   d = bearing - heading - variant [00021F57], as a byte
;   |d| < 0x10 (one's-complement magnitude) -> in the firing arc: fire through
;           the object's own shot routine [00021FB0] on the timer mask
;           [00021F75], with heading + variant and altitude + 6 for the call
;   otherwise -> the variant walks toward the bearing by 3 (00023F0B-00023F23);
;           an exact zero difference leaves it alone
; The variant is the turret: DOS draws the model rotated by it.
;
; In: a0 = object. Out: nothing. Preserves everything the update pass does not.
; DOS: flat 00023CF0-00023F55, mobile ground unit state.
; DOS symbol: sub_00023CF0
; Record: analysis/functions/browser-attract.md#object-pass
; Port: the same tests, moves, probes and aim, positions in the original's own 10.22.
; Preserved: the destruction byte as the first test, the health and hold
;   exits into the aim rather than out of the routine, the three-probe order and
;   its +0x20/-0x40/+0x60 steps, the (speed >> 21) + 1 turn, the steer byte
;   values, the reverted move, the unsigned limit compare, the one's-
;   complement arc test and the variant walk.
; Difference: 00023F34's `mov al,1 / call 00004E2E` (the explosion voice) is
;   sound. The bearing's two inputs are the objects' own 10.22 positions.
; Kind: translated.
; Status: ported; checked against work/replay_dos/objects-demo1.json.
object_state_mobile
        movem.l d0-d7/a1-a2,-(sp)
        tst.b   OBJ_PHASE(a0)                   ; 00023CF0 cmp [00021B29],0
        bne     .damage                         ; 00023CF7
        addq.b  #1,OBJ_TIMER(a0)                ; 00023CFD
        move.l  OBJ_X(a0),OBJ_PREV_X(a0)        ; 00023D03
        move.l  OBJ_Y(a0),OBJ_PREV_Y(a0)        ; 00023D11
        move.b  OBJ_ALTITUDE(a0),OBJ_PREV_ALT(a0)       ; 00023D1F
        cmpi.b  #6,OBJ_HEALTH(a0)               ; 00023D2B
        bls     .aim                            ; 00023D32 jbe 00023E55
        tst.l   OBJ_HOLD(a0)                    ; 00023D38
        bne     .hold                           ; 00023D40
        bsr     object_move                     ; 00023D46-00023D70
        bsr     object_ground_target_b          ; 00023D77-00023D9D
        move.b  OBJ_ALTITUDE(a0),d1
        cmp.b   d0,d1                           ; 00023D9F
        beq     .level                          ; 00023DA5 je 00023E45
        moveq   #0,d2
        move.b  OBJ_HEADING(a0),d2
        move.w  d2,-(sp)                        ; 00023DAB-00023DB1 push eax
        tst.b   OBJ_STEER_DIR(a0)               ; 00023DB2
        bmi     .minus                          ; 00023DB9 js
        bne     .plus                           ; 00023DBB jne
        addi.b  #$20,OBJ_HEADING(a0)            ; 00023DBD
        bsr     object_terrain_probe            ; 00023DC4
        beq     .plus                           ; 00023DC9 je 00023E08
        subi.b  #$40,OBJ_HEADING(a0)            ; 00023DCB
        bsr     object_terrain_probe            ; 00023DD2
        beq     .minus                          ; 00023DD7 je 00023DE7
        addi.b  #$60,OBJ_HEADING(a0)            ; 00023DD9
        bsr     object_terrain_probe            ; 00023DE0
        beq     .plus                           ; 00023DE5 je 00023E08
.minus
        move.w  (sp)+,d2                        ; 00023DE7 pop eax
        move.b  d2,OBJ_HEADING(a0)              ; 00023DE8
        move.l  OBJ_SPEED(a0),d2                ; 00023DEE
        moveq   #21,d3
        lsr.l   d3,d2                           ; 00023DF5 shr eax, 0x15
        addq.l  #1,d2                           ; 00023DF8 inc eax
        sub.b   d2,OBJ_HEADING(a0)              ; 00023DF9
        move.b  #$ff,OBJ_STEER_DIR(a0)          ; 00023DFF
        bra     .revert                         ; 00023E06
.plus
        move.w  (sp)+,d2                        ; 00023E08
        move.b  d2,OBJ_HEADING(a0)              ; 00023E09
        move.l  OBJ_SPEED(a0),d2                ; 00023E0F
        moveq   #21,d3
        lsr.l   d3,d2                           ; 00023E16
        addq.l  #1,d2                           ; 00023E19
        add.b   d2,OBJ_HEADING(a0)              ; 00023E1A
        move.b  #1,OBJ_STEER_DIR(a0)            ; 00023E20
.revert
        move.l  OBJ_PREV_X(a0),OBJ_X(a0)        ; 00023E27
        move.l  OBJ_PREV_Y(a0),OBJ_Y(a0)        ; 00023E35
        bra     .aim                            ; 00023E43
.level
        clr.b   OBJ_STEER_DIR(a0)               ; 00023E45
        bra     .aim                            ; 00023E4C
.hold
        subq.l  #1,OBJ_HOLD(a0)                 ; 00023E4E

.aim
        move.l  flt_frame_x,view_bearing_origin_x       ; 00023E55 [00019CDC]
        move.l  flt_frame_y,view_bearing_origin_y       ; 00023E5F [00019CE0]
        move.l  OBJ_X(a0),d6
        move.l  OBJ_Y(a0),d7
        bsr     view_bearing_point              ; 00023E69 -> 000256C8
        move.b  d0,d3                           ; al, the bearing
        moveq   #0,d2
        move.b  player_altitude,d2              ; 00023E6E movzx edi,[00019DFC]
        moveq   #20,d4
        lsl.l   d4,d2                           ; 00023E75 shl edi, 0x14
        tst.b   OBJ_TARGETABLE(a0)              ; 00023E78 cmp [00021BAB],0
        beq     .no_lock
        addi.l  #$87,d2                         ; 00023E81
.no_lock
        addi.l  #$1e000000,d2                   ; 00023E87
        cmp.l   d2,d1                           ; 00023E8D cmp esi, edi
        bcc     .out                            ; 00023E8F jae 00023F23
        move.b  flt_shake_rng+3,d2              ; 00023E95 test byte [00019DB8],0xC
        andi.b  #$0c,d2
        beq     .threat                         ; 00023E9C
        tst.b   object_chaff_active             ; 00023E9E cmp [00019D8F],0
        bne     .out                            ; 00023EA5
.threat
        move.b  #1,object_threat_chaff          ; 00023EA7 [00019D92]
        move.b  d3,d0
        sub.b   OBJ_HEADING(a0),d0              ; 00023EAE
        move.b  OBJ_VARIANT(a0),d2              ; 00023EB4 ah
        sub.b   d2,d0                           ; 00023EBA
        smi     d4                              ; 00023EBC sets bl
        seq     d5                              ; 00023EBF sete bh
        move.b  d0,d2                           ; 00023EC2 cbw
        bpl     .arc_pos
        not.b   d2                              ; 00023EC4 xor al, ah
.arc_pos
        cmpi.b  #$10,d2                         ; 00023EC6
        bcc     .arc_out                        ; 00023EC8 jae 00023F0B
        move.b  OBJ_F9(a0),d2                   ; 00023ECA
        and.b   OBJ_TIMER(a0),d2                ; 00023ED0 test [timer],al
        bne     .out                            ; 00023ED6
        move.b  OBJ_VARIANT(a0),d2              ; 00023ED9
        add.b   d2,OBJ_HEADING(a0)              ; 00023EDF
        addq.b  #6,OBJ_ALTITUDE(a0)             ; 00023EE5
        move.l  a0,-(sp)
        move.l  OBJ_FIRE(a0),a1                 ; 00023EEC
        jsr     (a1)                            ; 00023EF3 call eax
        move.l  (sp)+,a0
        move.b  OBJ_VARIANT(a0),d2              ; 00023EF6
        sub.b   d2,OBJ_HEADING(a0)              ; 00023EFC
        subq.b  #6,OBJ_ALTITUDE(a0)             ; 00023F02
        bra     .out                            ; 00023F09
.arc_out
        tst.b   d5                              ; 00023F0B or bh,bh
        bne     .out                            ; 00023F0D
        tst.b   d4                              ; 00023F0F or bl,bl
        beq     .variant_up                     ; 00023F11
        subq.b  #3,OBJ_VARIANT(a0)              ; 00023F13
        bra     .out
.variant_up
        addq.b  #3,OBJ_VARIANT(a0)              ; 00023F1C
.out
        movem.l (sp)+,d0-d7/a1-a2
        rts

.damage
        cmpi.b  #1,OBJ_PHASE(a0)                ; 00023F24
        bhi     .stage2                         ; 00023F2B ja 00023F42
        addq.b  #1,OBJ_PHASE(a0)                ; 00023F2D
        move.l  a0,-(sp)
        move.l  a0,a1
        bsr     object_scan_upper               ; 00023F33 -> 000227BF
        SndSpeechA 1                            ; 00023F39-00023F3B: SPEAK1 id 1
        move.l  (sp)+,a0
        bra     .out
.stage2
        addq.b  #1,OBJ_PHASE(a0)                ; 00023F42
        cmpi.b  #$0f,OBJ_PHASE(a0)              ; 00023F48
        bne     .out
        bsr     object_transition_home          ; 00023F4F je 00024997
        bra     .out

; DOS: flat 00023F60-000241B9, the allocator's default state - mission types 1,
; 6, 7 and 8 (factories 00023392, 000233A3, 00023297 itself, 00023413) - the
; free-flying units. It differs from the tank at 00023CF0 in what it does with
; the ground, how it aims and what it does when it is hit:
;   00023F60  variant [00021F57] - 0x10 EVERY tick (the tank's turret walks; this
;             one's spins), latch, timer + 1, and the move FIRST - before the
;             destruction test, so a falling wreck keeps its heading's drift
;   00023FC6  destruction byte set -> the falling-wreck tail 0002414C
;   00023FD3  hold -> count down and undo the move
;   00024001  ground target = height*2 + 0x2C. The difference to the altitude
;             decides: equal - nothing; target above by more than 0x14 - undo the
;             move; above by more than 4 - climb 8 (saturating); below by more
;             than 4 - descend 8 (no clamp)
;   00024076  aim: bearing and distance from the frame snapshot as the tank does
;   00024076  engagement range ((kind ^ 1) << 6 + 0x96) << 0x16 - 0x25800000 on
;             a night mission ([0002A37F] = 1), 0x35800000 otherwise; outside it
;             the heading only jitters by (rng & 3) - 2
;   000240A9  |bearing - heading| < 0xC: fire on the [00021F75] timer mask, then
;             hold 0x0B above the viewer's latched altitude (climb 0x10, cap 0xFE)
;   00024120  wider: a near target (esi <= 0x7800000) jitters by (rng & 7) + 4;
;             a far one (>= 0x19000000) or a wide angle (>= 0x46) jitters as
;             above; else it turns 0x0C toward the bearing
; In: a0 = object. Out: nothing.
; DOS symbol: sub_00023F60
; Record: analysis/functions/browser-attract.md#object-pass
; Port: the same tests, moves and byte arithmetic, positions in the original's own 10.22.
; Preserved: the unconditional variant step and early move, the order of the
;   hold and destruction tests, the three altitude bands, both jitter forms,
;   the unsigned range compare and the arc thresholds 0x0C/0x46.
; Difference: sound at 00024155-0002415D is not ported.
; Kind: translated.
; Status: ported; checked against work/replay_dos/objects-pass1.json.
object_state_unit
        movem.l d0-d7/a1-a2,-(sp)
        subi.b  #$10,OBJ_VARIANT(a0)            ; 00023F60
        move.l  OBJ_X(a0),OBJ_PREV_X(a0)        ; 00023F67
        move.l  OBJ_Y(a0),OBJ_PREV_Y(a0)        ; 00023F75
        move.b  OBJ_ALTITUDE(a0),OBJ_PREV_ALT(a0)       ; 00023F83
        addq.b  #1,OBJ_TIMER(a0)                ; 00023F8F
        bsr     object_move                     ; 00023F95-00023FBF
        tst.b   OBJ_PHASE(a0)                   ; 00023FC6
        bne     object_unit_wreck               ; 00023FCD
        tst.l   OBJ_HOLD(a0)                    ; 00023FD3
        beq     .free
        subq.l  #1,OBJ_HOLD(a0)                 ; 00023FDD
        move.l  OBJ_PREV_X(a0),OBJ_X(a0)        ; 00023FE4
        move.l  OBJ_PREV_Y(a0),OBJ_Y(a0)        ; 00023FF2
        bra     object_unit_out                 ; 00024000
.free
        moveq   #$2c,d1
        bsr     object_ground_target_k          ; 00024001-00024027
        sub.b   OBJ_ALTITUDE(a0),d0             ; 00024029
        beq     .aim                            ; 0002402F
        bcs     .below                          ; 00024031
        cmpi.b  #$14,d0                         ; 00024033
        bls     .near
        move.l  OBJ_PREV_X(a0),OBJ_X(a0)        ; 00024037
        move.l  OBJ_PREV_Y(a0),OBJ_Y(a0)        ; 00024045
.near
        cmpi.b  #4,d0                           ; 00024053
        bls     .aim
        addi.b  #8,OBJ_ALTITUDE(a0)             ; 00024057
        bcc     .aim
        move.b  #$ff,OBJ_ALTITUDE(a0)           ; 00024060
        bra     .aim
.below
        neg.b   d0                              ; 00024069
        cmpi.b  #4,d0
        bls     .aim
        subi.b  #8,OBJ_ALTITUDE(a0)             ; 0002406F
.aim
        move.l  flt_frame_x,view_bearing_origin_x       ; 00024076
        move.l  flt_frame_y,view_bearing_origin_y       ; 00024080
        move.l  OBJ_X(a0),d6
        move.l  OBJ_Y(a0),d7
        bsr     view_bearing_point              ; 0002408A -> 000256C8
        move.b  d0,d3                           ; al, the bearing
        moveq   #0,d2
        move.b  mission_kind+3,d2               ; 0002408F [0002A37F]
        eori.l  #1,d2                           ; 00024096
        lsl.l   #6,d2                           ; 00024099
        addi.l  #$96,d2                         ; 0002409C
        moveq   #22,d4
        lsl.l   d4,d2                           ; 000240A2
        cmp.l   d2,d1                           ; 000240A5 cmp esi, edi
        bcc     object_unit_jitter_a            ; 000240A7 jae 00024100
        move.b  d3,d0
        sub.b   OBJ_HEADING(a0),d0              ; 000240A9
        smi     d4                              ; 000240AF sets bl
        seq     d5                              ; 000240B2 sete bh
        move.b  d0,d2                           ; 000240B5 cbw
        bpl     .arc_pos
        not.b   d2                              ; 000240B7 xor al, ah
.arc_pos
        cmpi.b  #$0c,d2                         ; 000240B9
        bcc     .wide                           ; 000240BB jae 00024120
        move.b  OBJ_F9(a0),d0                   ; 000240BD
        and.b   OBJ_TIMER(a0),d0                ; 000240C3
        bne     .lift                           ; 000240C9
        move.l  a0,-(sp)
        move.l  OBJ_FIRE(a0),a1                 ; 000240CB
        jsr     (a1)                            ; 000240D2
        move.l  (sp)+,a0
.lift
        move.b  flt_prevalt,d0                  ; 000240D4 [00019DF6]
        addi.b  #$0b,d0                         ; 000240D9
        bcc     .lift_ok
        moveq   #-1,d0                          ; 000240DD
.lift_ok
        move.b  OBJ_ALTITUDE(a0),d1
        cmp.b   d0,d1                           ; 000240DF
        bhi     object_unit_out                 ; 000240E5 ja 000240F7
        cmpi.b  #$ef,OBJ_ALTITUDE(a0)           ; 000240E7
        bhi     .cap
        addi.b  #$10,OBJ_ALTITUDE(a0)           ; 000240F0
        bra     object_unit_out
.cap
        move.b  #$fe,OBJ_ALTITUDE(a0)           ; 000240F8
        bra     object_unit_out
.wide
        cmpi.l  #$7800000,d1                    ; 00024120
        bls     object_unit_jitter_b            ; 00024126
        cmpi.l  #$19000000,d1                   ; 00024128
        bcc     object_unit_jitter_a            ; 0002412E
        cmpi.b  #$46,d2                         ; 00024130
        bcc     object_unit_jitter_a            ; 00024132
        tst.b   d5                              ; 00024134 or bh,bh
        bne     object_unit_out                 ; 00024136
        tst.b   d4                              ; 00024138 or bl,bl
        beq     .turn_plus                      ; 0002413A
        subi.b  #$0c,OBJ_HEADING(a0)            ; 0002413C
        bra     object_unit_out
.turn_plus
        addi.b  #$0c,OBJ_HEADING(a0)            ; 00024144
        bra     object_unit_out
object_unit_jitter_a
        move.b  flt_shake_rng+3,d0              ; 00024100 [00019DB8]
        andi.b  #3,d0
        subq.b  #2,d0                           ; 00024107
        add.b   d0,OBJ_HEADING(a0)              ; 00024109
        bra     object_unit_out
object_unit_jitter_b
        move.b  flt_shake_rng+3,d0              ; 00024110
        andi.b  #7,d0
        addq.b  #4,d0                           ; 00024117
        add.b   d0,OBJ_HEADING(a0)              ; 00024119
object_unit_out
        movem.l (sp)+,d0-d7/a1-a2
        rts

; DOS: flat 0002414C-000241B9 (and 00023A08-00023A86 for the ally), the falling
; wreck. Phase 1 becomes 2 once; every tick after that the unit spins by 0x10
; and sinks 4. It is gone (00024997) when it underflows or reaches the ground
; (the doubled map height, no clearance); while the phase is 2 or less and it is
; within 0x0F of the ground it spawns its explosion child once more (000227BF)
; and moves to phase 3. The ally also clears [00019D40] and sets [00022384] on
; its first wreck tick (00023A17-00023A25).
; In: a0 = object, registers saved by the caller's prologue.
; DOS symbol: loc_0002414C
; Record: analysis/functions/browser-attract.md#object-pass
; Port: the same bytes in the same order.
; Difference: none; the voice cue at 0002415B-0002415D (SPEAK1 id 1) is made, see
;   src/sound.s. The ally's own copy of the fall (00023A2F) has no cue of this kind.
; Kind: translated.
; Status: ported.
object_unit_wreck
        cmpi.b  #1,OBJ_PHASE(a0)                ; 0002414C
        bne     object_wreck_fall               ; 00024153
        addq.b  #1,OBJ_PHASE(a0)                ; 00024155
        SndSpeechA 1                            ; 0002415B-0002415D: SPEAK1 id 1
object_wreck_fall
        addi.b  #$10,OBJ_HEADING(a0)            ; 00024162
        subi.b  #4,OBJ_ALTITUDE(a0)             ; 00024169
        bcs     .gone                           ; 00024170
        bsr     object_ground_sample            ; 00024172-00024190
        add.b   d0,d0                           ; 00024192 shl al,1
        move.b  OBJ_ALTITUDE(a0),d1             ; 00024194
        cmp.b   d1,d0                           ; 0002419A cmp al, ah
        bcc     .gone                           ; 0002419C jae 000241B9
        cmpi.b  #2,OBJ_PHASE(a0)                ; 0002419E
        bhi     object_unit_out                 ; 000241A5
        addi.b  #$0f,d0                         ; 000241A7
        cmp.b   d1,d0                           ; 000241A9
        bcs     object_unit_out                 ; 000241AB jae 000241AE
        addq.b  #1,OBJ_PHASE(a0)                ; 000241AE
        move.l  a0,-(sp)
        move.l  a0,a1
        bsr     object_scan_upper               ; 000241B4 -> 000227BF
        move.l  (sp)+,a0
        bra     object_unit_out
.gone
        bsr     object_transition_home          ; 000241B9 -> 00024997
        bra     object_unit_out

; DOS: flat 00023840-00023A86, mission type 4 (factory 00023424): the player's
; wingman. It flies a formation point behind the helicopter and keeps itself
; installed as [00022368], the object the shells and the missiles test.
;   00023840  variant - 0x10, latch, destruction byte -> the wreck at 00023A08
;   00023890  the point it steers for: the frame snapshot, or - with the weapon
;             page at 5 and a target latched ([00019D10]) - that target, 9
;             units above the wingman's altitude (saturating)
;   000238CC  shifted by hi(0xEE800000 * [00019CBC]) in X and hi(0xEE800000 *
;             [00019CB8]) in Y: a point behind the helicopter along its heading
;   000238EE  bearing and distance from there (000256C8); the heading turns 8
;             toward it when more than 4 off, resetting the timer to 0xF
;   00023927  [the timer's own expiry only plays sounds]
;   0002395B  it flies on only farther than 0x19000000 from the point
;   00023994  ground target = height*2 + 0x22, the altitude bands of 00023F60
;             with 0x0F, 4 and 8 (a climb below 4 above is the only clamp)
; DOS symbol: sub_00023840
; Record: analysis/functions/browser-attract.md#object-pass
; Port: the same tests and moves.
; Difference: none; the cues at 00023940 and 00023956 (SPEAK1 id 12 and 10) are made,
;   see src/sound.s. [00022368] is the ally's slot number; object_ally is its
;   pointer, so the latch is compared as the pointer of the slot it names.
; Kind: translated.
; Status: ported; checked against work/replay_dos/objects-pass2.json.
object_state_ally
        movem.l d0-d7/a1-a2,-(sp)
        subi.b  #$10,OBJ_VARIANT(a0)            ; 00023840
        move.l  OBJ_X(a0),OBJ_PREV_X(a0)        ; 00023847
        move.l  OBJ_Y(a0),OBJ_PREV_Y(a0)        ; 00023855
        move.b  OBJ_ALTITUDE(a0),OBJ_PREV_ALT(a0)       ; 00023863
        tst.b   OBJ_PHASE(a0)                   ; 0002386F
        bne     .wreck                          ; 00023876
        move.l  flt_frame_x,view_bearing_origin_x       ; 0002387C
        move.l  flt_frame_y,view_bearing_origin_y       ; 00023886
        cmpi.b  #5,instrument_page              ; 00023890
        bne     .point_ready
        moveq   #0,d0
        move.w  object_target_latch,d0          ; 00023899 movzx ebx,[00019D10]
        beq     .point_ready
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a1
        adda.l  d0,a1
        move.l  OBJ_X(a1),d0                    ; 000238A4
        move.l  d0,view_bearing_origin_x
        move.l  OBJ_Y(a1),d0                    ; 000238B0
        move.l  d0,view_bearing_origin_y
        addi.b  #9,OBJ_ALTITUDE(a0)             ; 000238BC
        bcc     .point_ready
        move.b  #$ff,OBJ_ALTITUDE(a0)           ; 000238C5
.point_ready
        move.l  #$ee800000,d0                   ; 000238CC
        move.l  flt_pub_cos,d2
        MulS64  d2
        add.l   d1,view_bearing_origin_x        ; 000238D7
        move.l  #$ee800000,d0                   ; 000238DD
        move.l  flt_pub_sin,d2
        MulS64  d2
        add.l   d1,view_bearing_origin_y        ; 000238E8
        move.l  OBJ_X(a0),d6
        move.l  OBJ_Y(a0),d7
        bsr     view_bearing_point              ; 000238EE -> 000256C8
        move.l  d1,d4                           ; esi
        sub.b   OBJ_HEADING(a0),d0              ; 000238F3-000238F9
        beq     .steered                        ; 000238FB
        bmi     .left                           ; 000238FD
        cmpi.b  #4,d0                           ; 000238FF
        bls     .steered
        addi.b  #8,OBJ_HEADING(a0)              ; 00023903
        move.b  #$0f,OBJ_TIMER(a0)              ; 0002390A
        bra     .follow
.left
        cmpi.b  #$fc,d0                         ; 00023913
        bge     .steered                        ; 00023915 jge (signed)
        subi.b  #8,OBJ_HEADING(a0)              ; 00023917
        move.b  #$0f,OBJ_TIMER(a0)              ; 0002391E
        bra     .follow
.steered
        subq.b  #1,OBJ_TIMER(a0)                ; 00023927
        bne     .follow                         ; 0002392D
        moveq   #0,d0
        move.b  object_target_latch+1,d0        ; 0002392F movzx ebx,[00019D10]
        beq     .follow                         ; 00023947-0002394B: 0 is no ally index
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a1
        adda.l  d0,a1
        cmpa.l  object_ally,a1                  ; 00023936 cmp ebx,[00022368]
        bne     .other_latch                    ; 0002393C
        SndSpeechA $0c                          ; 0002393E-00023940: SPEAK1 id 12, the ally acknowledges
        bra     .follow                         ; 00023945
.other_latch
        cmpi.b  #5,instrument_page              ; 0002394B [00019D88]
        bne     .follow                         ; 00023952
        SndSpeechA $0a                          ; 00023954-00023956: SPEAK1 id 10, the attack order
.follow
        cmpi.l  #$19000000,d4                   ; 0002395B
        bls     .level
        bsr     object_move                     ; 00023963-0002398D
.level
        moveq   #$22,d1
        bsr     object_ground_target_k          ; 00023994-000239BA
        sub.b   OBJ_ALTITUDE(a0),d0             ; 000239BC
        beq     .out                            ; 000239C2
        bcs     .below                          ; 000239C4
        cmpi.b  #$0f,d0                         ; 000239C6
        bls     .near
        move.l  OBJ_PREV_X(a0),OBJ_X(a0)        ; 000239CA
        move.l  OBJ_PREV_Y(a0),OBJ_Y(a0)        ; 000239D8
.near
        cmpi.b  #4,d0                           ; 000239E6
        bls     .out
        addi.b  #8,OBJ_ALTITUDE(a0)             ; 000239EA
        bcc     .out
        move.b  #$ff,OBJ_ALTITUDE(a0)           ; 000239F3
        bra     .out
.below
        cmpi.b  #$fc,d0                         ; 000239FC
        bge     .out
        subi.b  #8,OBJ_ALTITUDE(a0)             ; 00023A00
.out
        movem.l (sp)+,d0-d7/a1-a2
        rts
.wreck
        cmpi.b  #1,OBJ_PHASE(a0)                ; 00023A08
        bne     .wreck_fall
        addq.b  #1,OBJ_PHASE(a0)                ; 00023A11
        move.b  #1,ally_wrecked                 ; 00023A17 [00022384]
        SndSpeechA 5                            ; 00023A1E-00023A20: SPEAK1 id 5, the ally lost
        clr.l   ally_aux_40                     ; 00023A25 [00019D40]
.wreck_fall
        bra     object_wreck_fall               ; 00023A2F-00023A86

; The three shot routines [00021FB0] points at. Each finds a free slot in the
; transient pool (130 down to 31, a hundred of them - 00022CA1's `mov ecx,0x64 /
; mov ebx,0x82` scan) and turns it into a projectile launched from the object
; in a0, which has had its heading and altitude offset for the call:
;
;   00022CA1  state 000234E0, bank ROCK [00019E7C]
;   00022D33  state 000236D0, bank STGR [00019E84]       (types 2; DEMO1's tanks)
;   00022DD0  state 00024860, bank HELL [00019E80], target [00021D31] = 0x1F
;
; and, in common (00022CBB-00022D32): timer 0, aux [00021DB3] = 8, active 1, draw
; 0002514D, speed 0x04000000, X and Y from the shooter, heading and altitude from
; the shooter. The scan leaves the slot free (and the call a no-op) when all
; hundred are busy.
; In: a0 = shooter. Out: nothing; the shooter's registers are untouched.
; DOS: flat 00022CA1-00022D32 / 00022D33-00022DC4 / 00022DD0-00022E69.
; DOS symbol: none - three adjacent entries
; Record: analysis/functions/browser-attract.md#object-pass
; Port: the same slot scan and field set for each of the three.
; Preserved: the scan's hundred-slot bound and order, every stored value.
; Difference: none beyond the 16.16 lateral and depth and the null-bank
;   return the rocket launcher also has (Target artefact).
; Kind: translated.
; Status: ported; 00022D33 is the one DEMO1 reaches.
object_fire_rock
        movem.l d0-d1/a1-a4,-(sp)
        lea     object_state_shell_rock,a2
        lea     weapon_bank_rock,a3
        lea     weapon_palette_rock,a4
        moveq   #-1,d1
        bra     object_fire_common
object_fire_stinger
        movem.l d0-d1/a1-a4,-(sp)
        lea     object_state_shell_stinger,a2
        lea     weapon_bank_stgr,a3
        lea     weapon_palette_stgr,a4
        moveq   #-1,d1
        bra     object_fire_common
object_fire_hell
        movem.l d0-d1/a1-a4,-(sp)
        lea     object_state_guided,a2
        lea     weapon_bank_hell,a3
        lea     weapon_palette_hell,a4
        moveq   #$1f,d1
object_fire_common
        tst.l   (a3)
        beq     .out
        move.l  a0,a1                           ; the shooter, DOS ecx
        bsr     weapon_slot_scan                ; 00022CA2-00022CB6
        move.l  a0,d0
        beq     .none
        clr.b   OBJ_TIMER(a0)                   ; 00022CBB
        move.b  #8,OBJ_AUX(a0)                  ; 00022CC2
        tst.b   d1
        bmi     .no_target
        move.b  d1,OBJ_TARGET(a0)               ; 00022DF8 [00021D31] = 0x1F
.no_target
        move.b  #1,OBJ_ACTIVE(a0)               ; 00022CC9
        move.l  a2,OBJ_STATE(a0)                ; 00022CD0
        move.l  #object_draw_sprite,OBJ_DRAW(a0)        ; 00022CDB 0002514D
        move.l  (a3),OBJ_MODEL_A(a0)            ; 00022CE6
        move.l  (a4),OBJ_PALETTE_A(a0)
        move.l  #$4000000,OBJ_SPEED(a0)         ; 00022CF2
        move.l  OBJ_X(a1),OBJ_X(a0)             ; 00022CFE
        move.l  OBJ_Y(a1),OBJ_Y(a0)             ; 00022D0C
        move.b  OBJ_HEADING(a1),OBJ_HEADING(a0) ; 00022D1A
        move.b  OBJ_ALTITUDE(a1),OBJ_ALTITUDE(a0)       ; 00022D26
.none
        move.l  a1,a0
.out
        movem.l (sp)+,d0-d1/a1-a4
        rts

; The projectile states the shot routines install. Both begin the same way -
; latch, tick the timer, move - then run the altitude law of their kind and end
; in the shared proximity tail at 0002357B.
;
;   000234E0  rock: timer + 1 and `js` at 0x80 -> 00024997; move; the ground
;             at the new position is height*2 + 1 and the shell is gone at or
;             below it, else it sinks one altitude unit a tick
;   000236D0  stinger: the same, then it homes on the player's altitude
;             [00019DFC]: above it it drops 5 (a borrow ends it), below it it
;             climbs 0x12 (a carry past 0xFF pins it at 0xFE and costs 0x0A
;             timer), level it holds; then the same ground test, no sinking
;
; In: a0 = shell. Out: nothing.
; DOS: flat 000234E0-0002357A and 000236D0-000237A1.
; DOS symbol: loc_000234E0 / loc_000236D0
; Record: analysis/functions/browser-attract.md#object-pass
; Port: the same latch, timer, move, altitude law and ground test.
; Preserved: the order, the byte arithmetic, the exits through 00024997.
; Kind: translated.
; Status: ported; DEMO1's first stinger shell is at record 255.
object_state_shell_rock
        movem.l d0-d7/a1-a2,-(sp)
        bsr     shell_latch                     ; 000234E0-00023502
        addq.b  #1,OBJ_TIMER(a0)                ; 00023508
        bmi     shell_gone                      ; 0002350E js 00024997
        bsr     object_move                     ; 00023514-0002353E
        bsr     object_ground_sample            ; 00023545-00023563
        add.b   d0,d0                           ; 00023565 shl al,1
        addq.b  #1,d0                           ; 00023567 inc al
        cmp.b   OBJ_ALTITUDE(a0),d0             ; 00023569
        bcc     shell_gone                      ; 0002356F jbe 00024997
        subq.b  #1,OBJ_ALTITUDE(a0)             ; 00023575
        bra     shell_proximity

object_state_shell_stinger
        movem.l d0-d7/a1-a2,-(sp)
        bsr     shell_latch                     ; 000236D0-000236F2
        addq.b  #1,OBJ_TIMER(a0)                ; 000236F8
        bmi     shell_gone                      ; 000236FE
        bsr     object_move                     ; 00023704-0002372E
        move.b  OBJ_ALTITUDE(a0),d0             ; 00023735
        cmp.b   player_altitude,d0              ; 0002373B
        beq     .ground                         ; 00023741
        bcs     .climb                          ; 00023743 jb
        subq.b  #5,OBJ_ALTITUDE(a0)             ; 00023745
        bcs     shell_gone                      ; 0002374C jb 00024997
        bra     .ground
.climb
        addi.b  #$12,OBJ_ALTITUDE(a0)           ; 00023754
        bcc     .ground                         ; 0002375B jae
        move.b  #$fe,OBJ_ALTITUDE(a0)           ; 0002375D
        addi.b  #$0a,OBJ_TIMER(a0)              ; 00023764
        bmi     shell_gone                      ; 0002376B js
.ground
        bsr     object_ground_sample            ; 00023771-00023793
        add.b   d0,d0                           ; 00023791 shl al,1
        addq.b  #1,d0                           ; 00023793 inc al
        cmp.b   OBJ_ALTITUDE(a0),d0             ; 00023795
        bcc     shell_gone                      ; 0002379B jbe 00024997
        ; 000237A1 jmp 0002357B

; 0002357B-000236C1, shared by both shells. A shell is gone (00024997) when it
; reaches the player or the allied object [00022368]; it passes otherwise.
;   0002357B  altitude within 0x0F (one's-complement half-difference against
;             the viewer's latched altitude [00019DF6]) and X, Y within
;             0x01400000 (10.22, five map units) of the frame viewer
;             -> a hit on the player (000235CB)
;   00023660  the same three tests against slot [00022368]: a hit costs it 6
;             health, sets its destruction bit on a borrow, and ends the shell
; A hit on the player: if the shake bits [00019DB8] & 0xC are set and a flare is
; up [00019D90], the shell loses its target and is spared (000235DD); if the
; player is already dead [00019E49] it is spared; otherwise the bull threat
; [00019D94] is raised, the shake countdown [00019DC0] is set to 10, the PRNG is
; stirred with the flight X, two of the eight damage cells [00019E38] lose one
; each, the hull [00019E40] loses 2-5 (a negative result sets the dead byte)
; and the shell goes.
shell_proximity
        move.b  OBJ_ALTITUDE(a0),d0             ; 0002357B
        sub.b   flt_prevalt,d0                  ; 00023581 [00019DF6]
        roxr.b  #1,d0                           ; 00023587 rcr al, 1
        bpl     .alt_pos
        not.b   d0                              ; 0002358B xor al, ah
.alt_pos
        cmpi.b  #$0f,d0                         ; 0002358D
        bhi     shell_ally                      ; 0002358F ja 00023660
        move.l  OBJ_X(a0),d0
        sub.l   flt_frame_x,d0                  ; 00023595-0002359C
        bpl     .x_pos
        not.l   d0                              ; 000235A2 cdq / xor
.x_pos
        cmpi.l  #$1400000,d0                    ; 000235A5
        bhi     shell_ally                      ; 000235AA
        move.l  OBJ_Y(a0),d0
        sub.l   flt_frame_y,d0                  ; 000235B0-000235B7
        bpl     .y_pos
        not.l   d0                              ; 000235BD
.y_pos
        cmpi.l  #$1400000,d0                    ; 000235C0
        bhi     shell_ally                      ; 000235C5
shell_player_hit
        move.b  flt_shake_rng+3,d0              ; 000235CB test [00019DB8],0xC
        andi.b  #$0c,d0
        beq     .not_decoyed                    ; 000235D2
        tst.b   object_flare_active             ; 000235D4 cmp [00019D90],0
        beq     .not_decoyed                    ; 000235DB
        clr.b   OBJ_TARGET(a0)                  ; 000235DD
        bra     shell_ally                      ; 000235E4
.not_decoyed
        tst.w   player_death_cue                ; 000235E6 cmp [00019E49],0
        bne     shell_ally                      ; 000235ED
        move.b  #1,object_threat_bull           ; 000235EF [00019D94]
        move.l  #10,flt_shake_timer             ; 000235F6 [00019DC0]
        SndFX   5,$FF,0,0                       ; 00023600-0002360C: the hit, SND1 id 5
        move.l  flt_x,d0                        ; 00023612 [00019CD4]
        add.l   d0,flt_shake_rng                ; 00023617
        moveq   #0,d0
        move.b  flt_shake_rng+3,d0              ; 0002361D movzx eax, byte
        move.l  d0,d1                           ; 00023624
        andi.w  #7,d0                           ; 00023626
        lea     mission_damage,a1
        subq.b  #1,0(a1,d0.w)                   ; 00023628
        lsr.b   #5,d1                           ; 0002362E
        subq.b  #1,0(a1,d1.w)                   ; 00023631
        move.l  flt_shake_rng,d0
        ror.l   #8,d0                           ; 00023637
        move.l  d0,flt_shake_rng
        andi.l  #3,d0                           ; 0002363E-00023643
        addq.b  #2,d0                           ; 00023646
        andi.l  #$ff,d0
        sub.l   d0,mission_wounded              ; 00023648 [00019E40]
        bpl     shell_gone                      ; 0002364E jns 00024997
        move.w  #1,player_death_cue             ; 00023654 [00019E49]
        bra     shell_gone                      ; 0002365B
shell_ally
        ; 00023660: ebx = [00022368], the allied object type 4 installs. It is
        ; zero until a type 4 placement runs, and DOS then compares against the
        ; unused element 0 of each array (slot 130 of the array before it), which
        ; is neither an object nor a value this port holds - so with no ally
        ; installed the test is skipped. Unproven against DOS (Difference).
        move.l  object_ally,d0
        beq     .done
        move.l  d0,a1
        move.b  OBJ_ALTITUDE(a0),d0             ; 00023666
        sub.b   OBJ_ALTITUDE(a1),d0             ; 0002366C
        roxr.b  #1,d0                           ; 00023672
        bpl     .ally_alt_pos
        not.b   d0                              ; 00023676
.ally_alt_pos
        cmpi.b  #$0f,d0                         ; 00023678
        bhi     .done                           ; 0002367A ja 000236C1
        move.l  OBJ_X(a0),d0
        sub.l   OBJ_X(a1),d0                    ; 0002367C-00023683
        bpl     .ax_pos
        not.l   d0                              ; 0002368A
.ax_pos
        cmpi.l  #$1400000,d0                    ; 0002368D
        bhi     .done                           ; 00023692
        move.l  OBJ_Y(a0),d0
        sub.l   OBJ_Y(a1),d0                    ; 00023694-0002369B
        bpl     .ay_pos
        not.l   d0                              ; 000236A2
.ay_pos
        cmpi.l  #$1400000,d0                    ; 000236A5
        bhi     .done                           ; 000236AA
        subi.b  #6,OBJ_HEALTH(a1)               ; 000236AC
        bcc     shell_gone                      ; 000236B3 jae 000236BC
        ori.b   #1,OBJ_PHASE(a1)                ; 000236B5
        bra     shell_gone                      ; 000236BC
.done
        movem.l (sp)+,d0-d7/a1-a2               ; 000236C1 ret
        rts

; 000234E0-00023502 / 000236D0-000236F2: the latch both shells open with.
shell_latch
        move.l  OBJ_X(a0),OBJ_PREV_X(a0)
        move.l  OBJ_Y(a0),OBJ_PREV_Y(a0)
        move.b  OBJ_ALTITUDE(a0),OBJ_PREV_ALT(a0)
        rts

; 00024997, the end of a shell: the wreckage transition, entered from a state
; that has saved its registers.
shell_gone
        bsr     object_transition_home
        movem.l (sp)+,d0-d7/a1-a2
        rts

; DOS: flat 00024860-00024A33 and 00024ABC-00024B16, the guided missile - the
; state 00022DD0 installs for a tank's Hellfire and 00022E70 for the player's
; Stinger (page 3), with the target in [00021D31] (slot 0x1F, the fixed object,
; for a tank's; the latch [00019D10] for the player's).
;   00024860  latch; timer + 1, `js` at 0x80 -> 00024997
;   00024894  target set: bearing from the target to the missile (000256C8),
;             the heading turns toward it by at most 0x19 a tick (the nine-bit
;             difference halved through the borrow)
;   000248E4  move (000248E4-0002490E), then the altitude law: the ground at the
;             new position *2 + 0x14 (byte, saturating), raised to the target's
;             altitude if that is higher; climb 0x10 when more than 10 below it,
;             descend 0x10 when more than 8 above it (a borrow ends the missile)
;   00024985  at or below the doubled ground + 1 -> 00024997; else
;   00024A33  timer < 3: only the ally test (00023660); else the first of slots
;             30..1 within altitude 0x14 and 0x1400000 in X and Y takes 8 off its
;             health (6 when [00019DB8] & 0xC0 is clear), a borrow sets its
;             destruction bit, the missile latches that object's altitude and
;             ends; else the player (00024ACD): altitude within 0x0F and
;             0x1400000 in X and Y of the frame viewer -> the hit chain at
;             000235CB.
; In: a0 = missile. Out: nothing.
; DOS symbol: loc_00024860
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same tests and byte arithmetic, positions in the original's own 10.22.
; Preserved: the turn cap and its sign handling, the max of ground and target
;   altitude, both altitude steps and their asymmetric thresholds, the
;   timer-3 gate and the order slots, then ally, then player.
; Kind: translated.
; Status: ported; DEMO1's Stingers and a tank's Hellfire run this.
object_state_guided
        movem.l d0-d7/a1-a2,-(sp)
        bsr     shell_latch                     ; 00024860-00024882
        addq.b  #1,OBJ_TIMER(a0)                ; 00024888
        bmi     shell_gone                      ; 0002488E
        moveq   #0,d3
        move.b  OBJ_TARGET(a0),d3               ; 00024894 movzx ebx,[00021D31]
        beq     .fly                            ; 0002489D
        subq.w  #1,d3
        mulu    #OBJ_SIZE,d3
        lea     object_table,a1
        adda.l  d3,a1                           ; the target
        move.l  OBJ_X(a1),d0                    ; 000248A6
        move.l  d0,view_bearing_origin_x
        move.l  OBJ_Y(a1),d0                    ; 000248AB
        move.l  d0,view_bearing_origin_y
        move.l  OBJ_X(a0),d6
        move.l  OBJ_Y(a0),d7
        bsr     view_bearing_point              ; 000248B7
        sub.b   OBJ_HEADING(a0),d0              ; 000248BC
        beq     .fly                            ; 000248C2
        ; RCR leaves SF alone, so 000248C6 jns tests the sign of the byte the sub
        ; at 000248BC left, not of the rotated value; the rotate only needs the
        ; sub's borrow in X, which beq/bmi preserve.
        bmi     .rot_down                       ; 000248C6 jns, SF from 000248BC
        roxr.b  #1,d0                           ; 000248C4 rcr al,1
        bra     .turn_up
.rot_down
        roxr.b  #1,d0                           ; 000248C4 rcr al,1
        neg.b   d0                              ; 000248C8
        cmpi.b  #$19,d0
        bls     .down_capped
        moveq   #$19,d0
.down_capped
        sub.b   d0,OBJ_HEADING(a0)              ; 000248D0
        bra     .fly
.turn_up
        cmpi.b  #$19,d0                         ; 000248D8
        bls     .up_capped
        moveq   #$19,d0
.up_capped
        add.b   d0,OBJ_HEADING(a0)              ; 000248DE
.fly
        bsr     object_move                     ; 000248E4-0002490E
        moveq   #$14,d1
        bsr     object_ground_target_k          ; 00024915-0002493B
        moveq   #0,d3
        move.b  OBJ_TARGET(a0),d3               ; 0002493D movzx edx,[00021D31]
        beq     .law                            ; 00024946
        subq.w  #1,d3
        mulu    #OBJ_SIZE,d3
        lea     object_table,a1
        adda.l  d3,a1
        move.b  OBJ_ALTITUDE(a1),d4             ; 00024948
        cmp.b   d4,d0
        bhi     .law                            ; 0002494E ja
        move.b  d4,d0                           ; 00024950
.law
        sub.b   OBJ_ALTITUDE(a0),d0             ; 00024956
        beq     .ground                         ; 0002495C
        bcs     .descend                        ; 0002495E
        cmpi.b  #$0a,d0                         ; 00024960
        bls     .ground
        addi.b  #$10,OBJ_ALTITUDE(a0)           ; 00024964
        bcc     .ground
        move.b  #$ff,OBJ_ALTITUDE(a0)           ; 0002496D
        bra     .ground
.descend
        neg.b   d0                              ; 00024976
        cmpi.b  #8,d0
        bls     .ground
        subi.b  #$10,OBJ_ALTITUDE(a0)           ; 0002497C
        bcs     shell_gone                      ; 00024983
.ground
        bsr     object_ground_sample            ; the cell at 00024985's ebx
        add.b   d0,d0                           ; 00024987 shl al,1
        addq.b  #1,d0                           ; 00024989 inc al
        cmp.b   OBJ_ALTITUDE(a0),d0             ; 0002498B
        bcc     shell_gone                      ; 00024991 not `ja`: falls into 00024997
        cmpi.b  #3,OBJ_TIMER(a0)                ; 00024A33
        bcs     shell_ally                      ; 00024A3A jb 00023660
        lea     object_table+29*OBJ_SIZE,a1     ; 00024A40 ebx = 0x1E
        moveq   #30,d3
.victim
        tst.b   OBJ_ACTIVE(a1)                  ; 00024A45
        beq     .next
        move.b  OBJ_ALTITUDE(a0),d0             ; 00024A4E
        sub.b   OBJ_ALTITUDE(a1),d0
        roxr.b  #1,d0                           ; 00024A5A
        bpl     .alt_pos
        not.b   d0                              ; 00024A5E cbw / xor
.alt_pos
        cmpi.b  #$14,d0                         ; 00024A60
        bhi     .next
        move.l  OBJ_X(a0),d0
        sub.l   OBJ_X(a1),d0                    ; 00024A64-00024A6B
        bpl     .x_pos
        not.l   d0
.x_pos
        cmpi.l  #$1400000,d0                    ; 00024A75
        bhi     .next
        move.l  OBJ_Y(a0),d0
        sub.l   OBJ_Y(a1),d0                    ; 00024A7C-00024A83
        bpl     .y_pos
        not.l   d0
.y_pos
        cmpi.l  #$1400000,d0                    ; 00024A8D
        bhi     .next
        moveq   #8,d0                           ; 00024A94
        move.b  flt_shake_rng+3,d2              ; 00024A96 test [00019DB8],0xC0
        andi.b  #$c0,d2
        bne     .damage
        move.b  d0,d2                           ; 00024A9F
        lsr.b   #2,d2
        sub.b   d2,d0                           ; 00024AA4
.damage
        sub.b   d0,OBJ_HEALTH(a1)               ; 00024AA6
        bcc     .struck
        ori.b   #1,OBJ_PHASE(a1)                ; 00024AAE
.struck
        move.b  OBJ_ALTITUDE(a1),OBJ_PREV_ALT(a0)       ; 00024AB5-00024ABB
        bra     shell_gone                      ; 00024AC1
.next
        lea     -OBJ_SIZE(a1),a1                ; 00024AC6
        subq.w  #1,d3
        bne     .victim
        move.b  OBJ_ALTITUDE(a0),d0             ; 00024ACD
        sub.b   flt_prevalt,d0
        roxr.b  #1,d0                           ; 00024AD9
        bpl     .p_alt
        not.b   d0
.p_alt
        cmpi.b  #$0f,d0                         ; 00024ADF
        bhi     .out
        move.l  OBJ_X(a0),d0
        sub.l   flt_frame_x,d0                  ; 00024AE3-00024AEA
        bpl     .p_x
        not.l   d0
.p_x
        cmpi.l  #$1400000,d0                    ; 00024AF3
        bhi     .out
        move.l  OBJ_Y(a0),d0
        sub.l   flt_frame_y,d0                  ; 00024AFA-00024B01
        bpl     .p_y
        not.l   d0
.p_y
        cmpi.l  #$1400000,d0                    ; 00024B0A
        bhi     .out
        bra     shell_player_hit                ; 00024B11 jmp 000235CB
.out
        movem.l (sp)+,d0-d7/a1-a2               ; 00024B16
        rts

; DOS: flat 00024310-00024470, the timed blast: the state a page-4 weapon
; (000231B2) leaves at its target.
;   00024310  timer + 1; at 0x46 and 0x64 a sound; below 0x78 nothing else
;   00024340  at 0x78: the shake countdown [00019DC0] = 5; the object becomes a
;             BOOM wreckage (state 000237B0, draw 0002519D, model [00019E88],
;             sprite 1) and then, in this same call,
;   00024391  every active slot 30..1 within altitude 0x32 (halved difference,
;             one's-complement) and 0xC800000 (fifty map units) in X and Y loses
;             0x64 health - a borrow sets its destruction bit - and gets an
;             explosion child of its own through 000227BF;
;   000243FE  the player, by the frame snapshot and the latched altitude, within
;             the same bounds: [00019E40] = -1, [00019E49] = 1, shake 10.
; In: a0 = the blast object. Out: nothing.
; DOS symbol: loc_00024310
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same counts, bounds and effects, positions in the original's own 10.22.
; Preserved: the order of the two sounds and the detonation, the 0x64 damage,
;   the per-victim child, the player's kill.
; Difference: none; the four sounds (00024329 SPEAK1 9, 00024330 SND1 2, 00024340
;   SND1 6, 00024469 SND1 5) are made, see src/sound.s.
; Kind: translated.
; Status: ported; DEMO1's page-4 weapons run this.
object_state_bomb
        movem.l d0-d7/a1-a2,-(sp)
        addq.b  #1,OBJ_TIMER(a0)                ; 00024310
        move.b  OBJ_TIMER(a0),d0
        cmpi.b  #$64,d0                         ; 0002431C
        beq     .tick_64                        ; 0002431E
        cmpi.b  #$46,d0                         ; 00024320
        beq     .tick_46                        ; 00024322
        cmpi.b  #$78,d0                         ; 00024324
        bcc     .detonate                       ; 00024326 jae
.out
        movem.l (sp)+,d0-d7/a1-a2
        rts
.tick_46
        SndSpeechA 9                            ; 00024329-0002432B: the countdown cue, SPEAK1 id 9
        bra     .out
.tick_64
        SndFX   2,$FF,0,0                       ; 00024330-0002433B: SND1 id 2
        bra     .out
.detonate
        SndFX   6,$FF,0,0                       ; 00024341-0002434C: the detonation, SND1 id 6
        move.l  #5,flt_shake_timer              ; 00024352
        move.l  #object_state_wreckage,OBJ_STATE(a0)    ; 0002435C
        move.l  #object_draw_frame,OBJ_DRAW(a0)         ; 00024367
        clr.b   OBJ_AUX(a0)                     ; 00024372
        tst.l   weapon_bank_boom
        beq     .no_boom
        move.l  weapon_bank_boom,OBJ_MODEL_A(a0)        ; 00024379
        move.l  weapon_palette_boom,OBJ_PALETTE_A(a0)
.no_boom
        move.b  #1,OBJ_SPRITE(a0)               ; 00024385
        lea     object_table+29*OBJ_SIZE,a1     ; 0002438C
        moveq   #30,d3
.victim
        tst.b   OBJ_ACTIVE(a1)                  ; 00024391
        beq     .next
        move.b  OBJ_ALTITUDE(a0),d0             ; 0002439A
        sub.b   OBJ_ALTITUDE(a1),d0
        roxr.b  #1,d0                           ; 000243A6
        bpl     .alt_pos
        not.b   d0                              ; 000243AA
.alt_pos
        cmpi.b  #$32,d0                         ; 000243AC
        bhi     .next
        move.l  OBJ_X(a0),d0
        sub.l   OBJ_X(a1),d0                    ; 000243B0-000243B7
        bpl     .x_pos
        not.l   d0
.x_pos
        cmpi.l  #$c800000,d0                    ; 000243C1
        bhi     .next
        move.l  OBJ_Y(a0),d0
        sub.l   OBJ_Y(a1),d0                    ; 000243C8-000243CF
        bpl     .y_pos
        not.l   d0
.y_pos
        cmpi.l  #$c800000,d0                    ; 000243D9
        bhi     .next
        subi.b  #$64,OBJ_HEALTH(a1)             ; 000243E0
        bcc     .child
        ori.b   #1,OBJ_PHASE(a1)                ; 000243E9
.child
        movem.l a0-a1/d3,-(sp)                  ; 000243F0-000243FA
        bsr     object_scan_upper               ; a1 = the victim, 000227BF
        movem.l (sp)+,a0-a1/d3
.next
        lea     -OBJ_SIZE(a1),a1                ; 000243FB
        subq.w  #1,d3
        bne     .victim
        move.b  OBJ_ALTITUDE(a0),d0             ; 000243FE
        sub.b   flt_prevalt,d0
        roxr.b  #1,d0                           ; 0002440A
        bpl     .p_alt
        not.b   d0                              ; 0002440E
.p_alt
        cmpi.b  #$32,d0                         ; 00024410
        bhi     .out
        move.l  OBJ_X(a0),d0
        sub.l   flt_frame_x,d0                  ; 00024414-0002441B
        bpl     .p_x
        not.l   d0
.p_x
        cmpi.l  #$c800000,d0                    ; 00024424
        bhi     .out
        move.l  OBJ_Y(a0),d0
        sub.l   flt_frame_y,d0                  ; 0002442B-00024432
        bpl     .p_y
        not.l   d0
.p_y
        cmpi.l  #$c800000,d0                    ; 0002443B
        bhi     .out
        move.l  #-1,mission_wounded             ; 00024442 [00019E40]
        move.w  #1,player_death_cue             ; 0002444C [00019E49]
        move.l  #10,flt_shake_timer             ; 00024453 [00019DC0]
        SndFX   5,$FF,0,0                       ; 0002445E-00024469: the player killed, SND1 id 5
        bra     .out

; 00019C88, the draw handler of the blast object: a bare `ret`.
; DOS: flat 00019C88, `ret`.
; Kind: translated. Status: ported.
object_draw_none
        rts

; The countermeasure chain. 00019555-0001959E closes every flight tick (the
; frame's own object pass has already run, so the threat bytes it set are the
; ones read):
;
;   [00019D93] or [00019D94] set   -> flare branch
;   else [00019D92] set            -> chaff branch
;   flare branch: altitude [00019DFC] above 0x0A and no flare in the air
;                 [00019D90] -> launch a flare (00022A00)
;   chaff branch: altitude above 0x14 and no chaff in the air [00019D8F]
;                 -> launch chaff (00022AA0)
;
; [00019D93] is 000077A0's threat blip, which this port does not draw, so it
; stays zero; [00019D92] is a tank with the player in its aim (00023EA7) and
; [00019D94] a shell that reached the player (000235EF). 0001959F's keys 0x28
; and 0x27 reach the same two launchers by hand; live keys are outside this
; milestone.
; In: nothing. Out: nothing.
; DOS: flat 00019555-0001959E, the countermeasure decision.
; DOS symbol: inside sub_00018F94's tail
; Record: analysis/functions/browser-attract.md#object-pass
; Port: the same three flag tests, altitude gates and in-the-air gates.
; Preserved: the test order (blip, then chaff, then bull), the unsigned altitude
;   compares and which flag selects which launcher.
; Kind: translated.
; Status: ported; DEMO1's tanks raise the chaff flag from its first pass.
countermeasure_tick
        tst.b   object_threat_blip              ; 00019555 cmp [00019D93],0
        bne     .flare
        tst.b   object_threat_chaff             ; 0001955E cmp [00019D92],0
        bne     .chaff
        tst.b   object_threat_bull              ; 00019567 cmp [00019D94],0
        bne     .flare
        rts
.flare
        cmpi.b  #$0a,player_altitude            ; 00019571
        bls     .out                            ; 00019578 jbe 00019587
        tst.b   object_flare_active             ; 0001957A cmp [00019D90],0
        bne     .out
        bra     object_launch_flare             ; 00019581 je 00022A00
.chaff
        cmpi.b  #$14,player_altitude            ; 00019588
        bls     .out                            ; 0001958F jbe 0001959E
        tst.b   object_chaff_active             ; 00019591 cmp [00019D8F],0
        bne     .out
        bra     object_launch_chaff             ; 00019598 je 00022AA0
.out
        rts

; 00022A00 and 00022AA0: drop a flare or a chaff cloud. Each needs one left in
; the load ([00019D8E] / [00019D8D]) and a free slot in the transient pool, then
; takes one off the load, adds one to the in-the-air count ([00019D90] /
; [00019D8F]) and sets up the object:
;
;                  flare (BULL)            chaff (CHAF)
;   timer          0x14                    0x1E
;   state          00024480                000244A0
;   model A        [00019E74]              [00019E78]
;
; and, through the shared tail 00022A54, aux 0, active, draw 0002519D, the
; flight position [00019CD4]/[00019CD8] and altitude [00019DFC]. The tail also
; sets [00019D8A] = 1 and jumps to 000074C0 to redraw the two counters; this
; port repaints the console from the live counts every frame.
; In: nothing. Out: nothing.
; DOS: flat 00022A00-00022A9C (flare) and 00022AA0-00022AF8 (chaff).
; DOS symbol: loc_00022A00 / loc_00022AA0
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same checks and fields, positions in the original's own 10.22.
; Preserved: the empty-load and full-pool exits, the count updates, timers,
;   states, banks and the launch point.
; Difference: [00019D8A] and the 000074C0 redraw are not carried.
; Kind: translated.
; Status: ported; checked against the DOS object snapshots.
object_launch_flare
        tst.w   mission_flare                   ; 00022A00 cmp [00019D8E],0
        beq     .out
        tst.l   weapon_bank_bull
        beq     .out
        bsr     weapon_slot_scan                ; 00022A09-00022A1F
        move.l  a0,d0
        beq     .out
        subq.w  #1,mission_flare                ; 00022A23
        addq.b  #1,object_flare_active          ; 00022A29
        move.b  #$14,OBJ_TIMER(a0)              ; 00022A2F
        move.l  #object_state_flare,OBJ_STATE(a0)       ; 00022A36
        move.b  #1,OBJ_SPRITE(a0)               ; 00022A41
        move.l  weapon_bank_bull,OBJ_MODEL_A(a0)        ; 00022A48 [00019E74]
        move.l  weapon_palette_bull,OBJ_PALETTE_A(a0)
        bra     object_launch_common
.out
        rts
object_launch_chaff
        tst.w   mission_chaff                   ; 00022AA0 cmp [00019D8D],0
        beq     object_launch_none
        tst.l   weapon_bank_chaf
        beq     object_launch_none
        bsr     weapon_slot_scan                ; 00022AA9-00022ABF
        move.l  a0,d0
        beq     object_launch_none
        subq.w  #1,mission_chaff                ; 00022AC3
        addq.b  #1,object_chaff_active          ; 00022AC9
        move.b  #$1e,OBJ_TIMER(a0)              ; 00022ACF
        move.l  #object_state_chaff,OBJ_STATE(a0)       ; 00022AD6
        move.b  #1,OBJ_SPRITE(a0)               ; 00022AE1
        move.l  weapon_bank_chaf,OBJ_MODEL_A(a0)        ; 00022AE8 [00019E78]
        move.l  weapon_palette_chaf,OBJ_PALETTE_A(a0)
object_launch_common
        clr.b   OBJ_AUX(a0)                     ; 00022A5B
        move.b  #1,OBJ_ACTIVE(a0)               ; 00022A62
        move.l  #object_draw_frame,OBJ_DRAW(a0) ; 00022A69
        move.l  flt_x,d0                        ; 00022A74 [00019CD4]
        move.l  d0,OBJ_X(a0)                    ; 00022A79
        move.l  flt_y,d0                        ; 00022A80 [00019CD8]
        move.l  d0,OBJ_Y(a0)                    ; 00022A85
        move.b  player_altitude,OBJ_ALTITUDE(a0)        ; 00022A8C
object_launch_none
        rts

; 00024480 and 000244A0, the two cloud states. Both drop one altitude unit a
; tick and count the timer down, and end the same way - one off the in-the-air
; count and the slot freed - when either reaches zero (`dec byte ... / je`, so
; an altitude of 1 ends it too). The chaff cloud animates in between: its
; sprite byte steps 1..8 and wraps to 1 (000244B0-000244C0); the flare holds
; frame 1.
; In: a0 = the object. Out: nothing.
; DOS: flat 00024480-0002449E (flare) and 000244A0-000244D5 (chaff).
; DOS symbol: loc_00024480 / loc_000244A0
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same decrements, exits and sprite wrap.
; Preserved: the order of the two decrements and the zero tests.
; Kind: translated.
; Status: ported.
object_state_flare
        subq.b  #1,OBJ_ALTITUDE(a0)             ; 00024480
        beq     .expire                         ; 00024486
        subq.b  #1,OBJ_TIMER(a0)                ; 00024488
        beq     .expire                         ; 0002448E
        rts
.expire
        subq.b  #1,object_flare_active          ; 00024491 [00019D90]
        clr.b   OBJ_ACTIVE(a0)                  ; 00024497
        rts
object_state_chaff
        subq.b  #1,OBJ_ALTITUDE(a0)             ; 000244A0
        beq     .expire                         ; 000244A6
        subq.b  #1,OBJ_TIMER(a0)                ; 000244A8
        beq     .expire                         ; 000244AE
        addq.b  #1,OBJ_SPRITE(a0)               ; 000244B0
        cmpi.b  #8,OBJ_SPRITE(a0)               ; 000244B6
        bls     .keep                           ; 000244BD ja 000244C0
        move.b  #1,OBJ_SPRITE(a0)               ; 000244C0
.keep
        rts
.expire
        subq.b  #1,object_chaff_active          ; 000244C8 [00019D8F]
        clr.b   OBJ_ACTIVE(a0)                  ; 000244CE
        rts

; DOS: flat 00023A8C-00023AC7, mission type 3's oil-tank state. Its live path
; is a bare return; destruction counts the phase byte [00021B29] up and hands
; off to the shared transition at 00024997 when it reaches 5.
; DOS symbol: inside loc_00023A86
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: spawns the transient child on the first damage tick, then counts out.
; Preserved: the phase byte's 0/1/>1 branches, the 000227BF child allocation,
; the count to 5 and the 00024997 handoff.
; Difference: none; 00023AAB-00023AAD's voice cue (SPEAK1 id 1) is made, see src/sound.s.
; Kind: translated.
; Status: ported; the transient child's handler triple remains open.
object_state_idle
        tst.b   OBJ_DAMAGE(a0)
        beq     .ret
        cmpi.b  #1,OBJ_DAMAGE(a0)
        bhi     .stage2
        addq.b  #1,OBJ_DAMAGE(a0)
        move.l  a0,-(sp)
        move.l  a0,a1
        bsr     object_scan_upper
        SndSpeechA 1                            ; 00023AAB-00023AAD: SPEAK1 id 1
        move.l  (sp)+,a0
        rts
.stage2
        addq.b  #1,OBJ_DAMAGE(a0)
        cmpi.b  #5,OBJ_DAMAGE(a0)
        bne     .ret
        bra     object_transition_home
.ret
        rts

; Hold the wreckage frame for twenty ticks, then retire the object. Below the
; allocator's thirtieth slot the retirement also walks the end-cue chain: the
; object's own cue byte, a shared hold counter, and a one-shot flag.
;
; 000237CC-000237FD is that chain and nothing else. It reads [00021F39 + slot],
; tests [0002824B], decrements it, tests [00019E49] and sets it. There is no
; mission-target step anywhere in it; this used to decrement a targets-left
; counter between the slot check and the cue, which is a mission mechanic the
; original does not run here. The live-object decrement went the same way:
; 000237BF clears the active byte and keeps no population count, and the
; port's own draw pass recounts the order array every frame regardless.
;
; In: a0 = object, d6 = its 1-based slot number.
; DOS: flat 000237B0-000237FD, wreckage hold and retirement.
; DOS symbol: inside loc_00023771
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: counts the authored wreckage frames out and retires the slot.
; Preserved: the 0x14 hold, the active clear, the 0x1E slot bound, and the
; end-cue byte/hold/flag order.
; Difference: none; 000237F6's `mov al,7 / call 00004E2E` voice cue is made, see
;   src/sound.s.
; Kind: translated.
; Status: ported.
object_state_wreckage
        addq.b  #1,OBJ_SPRITE(a0)               ; 000237B0 inc [000219A3+slot]
        cmpi.b  #$14,OBJ_SPRITE(a0)
        blo     .ret                            ; 000237BD jb
        clr.b   OBJ_ACTIVE(a0)                  ; 000237BF
        cmpi.w  #OBJ_ALLOC_LIMIT,d6
        bhi     .ret                            ; 000237C6 cmp 0x1E / jbe
        tst.b   OBJ_END_CUE(a0)
        beq     .ret                            ; 000237CC/D3
        tst.w   object_endcue_hold
        beq     .ret                            ; 000237D5/DC
        subq.w  #1,object_endcue_hold
        bne     .ret                            ; 000237DE/E4
        tst.w   player_death_cue
        bne     .ret                            ; 000237E6/ED
        move.w  #1,player_death_cue             ; 000237EF
        SndSpeechA 7                            ; 000237F6-000237F8: SPEAK1 id 7, the last goal
.ret
        rts


; Spawn the selected mission's placement records through the recovered DOS
; factory contract. The original call site at 000068A5 copies f1..f10 into the
; temporary block, resolves f2/f3 through 00019EA4, then dispatches the ten-entry
; table at 0002231C. This port stores the same fields in the native object and
; selects the corresponding recovered state/draw pair below.
; DOS: flat 000068A5-00006947, allocator 00023297, factories 00023392-0002349C.
; DOS symbol: loc_000068A5
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: dispatches every parsed placement with authored model A/B banks.
; Preserved: record order, first-30 allocator bound, model slot indices,
; positions, heading, speed, health, factory bytes, and active count.
; Kind: translated; struct layout and palette pointers are Falcon storage.
; Route: analysis/functions/falcon-attract.md#object-pass.
; Status: ported; the traced attract transition calls this factory before
; DEMO<n>, and the active object/callback/effect graph is frame-driven.
object_spawn_mission
        ; 00029240/0002926C seed the end-cue countdown from the mission's '*'
        ; record count. Without it object_state_wreckage's `tst / beq` at
        ; 000237DC always finds zero and the cue can never fire.
        move.w  mission_star_count,object_endcue_hold
        clr.w   player_hit_flag
        clr.w   object_spawn_index
        move.w  mission_object_count,d7
        beq     .done
        moveq   #0,d6
.record
        move.w  d6,object_spawn_index

        ; 000068A6/000068B9: f2 and f3 are indices into the ten resource
        ; pointers, not sprite numbers. A missing authored slot is not replaced
        ; by TANK; the placement is skipped exactly as a null DOS pointer makes
        ; the later model check fail.
        moveq   #0,d0
        move.b  mission_obj_f2,d0
        move.w  d6,d1
        lea     mission_obj_f2,a1
        move.b  0(a1,d6.w),d0
        bsr     object_mission_slot
        tst.w   d0
        bne     .next
        move.l  a1,object_factory_model_a
        move.l  a2,object_factory_palette_a
        move.w  d6,d1
        lea     mission_obj_f3,a1
        moveq   #0,d0
        move.b  0(a1,d6.w),d0
        bsr     object_mission_slot
        tst.w   d0
        bne     .next
        move.l  a1,object_factory_model_b
        move.l  a2,object_factory_palette_b

        ; Dispatch slot 0 is not an allocator call. 00023462 owns fixed
        ; object slot 31; all other table entries call 00023297 and therefore
        ; consume one of the first thirty free slots.
        lea     mission_obj_type,a1
        moveq   #0,d0
        move.b  0(a1,d6.w),d0
        bne     .allocate_standard
        lea     object_table+30*OBJ_SIZE,a0
        move.l  a0,object_factory_object
        bsr     object_factory_fill
        move.l  object_factory_object,a0
        bsr     object_factory_install
        bra     .next

.allocate_standard
        bsr     object_alloc
        tst.l   a0
        beq     .next
        move.l  a0,object_factory_object
        bsr     object_factory_fill
        move.l  object_factory_object,a0
        bsr     object_factory_install
.next
        move.w  object_spawn_index,d6
        addq.w  #1,d6
        cmp.w   d7,d6
        bcs     .record
.done
        rts

; In: d0.b = mission resource-slot index. Out: a1 = SG bank base, a2 = its
; RGB565 palette, d0.w = status. The 10*168000 bank stride is deliberately
; walked with the 68030 address adder rather than truncating it to a word.
; DOS: pointer table at 00019EA4 and object call-site index loads.
; DOS symbol: none - the cited addresses are data
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: resolves the same slot into native bank/palette arrays.
; Preserved: slot bounds, bank stride, palette-slot relation, and status return.
; Kind: adapted - native pointer arrays.
; Status: ported.
object_mission_slot
        movem.l d1-d4,-(sp)
        moveq   #0,d1
        move.b  d0,d1
        cmpi.w  #9,d1
        bhi     .bad
        lea     mission_sprite_banks,a1
        move.w  d1,d2
        beq     .bank_ready
.bank_step
        adda.l  #168000,a1
        subq.w  #1,d2
        bne     .bank_step
.bank_ready
        lea     mission_sprite_palettes,a2
        move.w  d1,d2
        lsl.w   #8,d2
        lsl.w   #1,d2
        adda.w  d2,a2
        lea     mission_sprite_status,a3
        add.w   d1,d1
        move.w  0(a3,d1.w),d0
        movem.l (sp)+,d1-d4
        rts
.bad
        moveq   #-1,d0
        movem.l (sp)+,d1-d4
        rts

; Populate the native struct from the temporary values the call site at
; 000068A5-0000692D copies into the 00022344 block before dispatching.
; DOS: flat 000068A5-0000692D (the temporaries) and 00023297-000232DC (the
; allocator's field writes, including the map_height*2+11 altitude seed).
; DOS symbol: loc_000068A5
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: writes the same authored placement into the Falcon object struct.
; Preserved: field order and sources, the f8 << 21 speed scale, the f1
; indirection through the 00022344 auxiliary table, and the saturating
; altitude seed.
; Difference: the two model pointers and their palettes are Falcon bank
;   addresses resolved through object_mission_slot, where DOS keeps the
;   00019EA4 pointer table entries directly.
; Kind: translated; struct layout and palette pointers are Falcon storage.
; Status: ported; covered by mission parser validation.
object_factory_fill
        move.l  object_factory_model_a,OBJ_MODEL_A(a0)
        move.l  object_factory_model_b,OBJ_MODEL_B(a0)
        move.l  object_factory_palette_a,OBJ_PALETTE_A(a0)
        move.l  object_factory_palette_b,OBJ_PALETTE_B(a0)

        move.w  object_spawn_index,d6
        move.w  d6,d5
        lsl.w   #2,d5
        lea     mission_obj_x,a1
        move.l  0(a1,d5.w),OBJ_X(a0)
        lea     mission_obj_y,a1
        move.l  0(a1,d5.w),OBJ_Y(a0)
        ; 00023297 writes neither the previous position (0002107C/00021284)
        ; nor the sprite (000219A3), timer (00021E35) or steering latch
        ; (00021EB7): they keep what the slot held, which object_init explains.

        lea     mission_obj_heading,a1
        move.b  0(a1,d6.w),OBJ_HEADING(a0)      ; 0002220C -> 0002189F, raw
        clr.b   OBJ_DAMAGE(a0)                  ; 00023351 [00021B29] = 0
        move.b  #1,OBJ_ACTIVE(a0)

        lea     mission_obj_f1,a1
        moveq   #0,d0
        move.b  0(a1,d6.w),d0
        ; 000232DC indexes the five authored bytes at 00022344. f1 is not
        ; copied directly; the table gives the object's auxiliary byte.
        lea     object_aux_table,a1
        move.b  0(a1,d0.w),OBJ_AUX(a0)
        lea     mission_obj_flag,a1
        move.b  0(a1,d6.w),OBJ_FLAG(a0)
        lea     mission_obj_f7,a1
        move.b  0(a1,d6.w),OBJ_HEALTH(a0)
        lea     mission_obj_f8,a1
        moveq   #0,d0
        move.b  0(a1,d6.w),d0
        lsl.l   #5,d0
        lsl.l   #5,d0
        lsl.l   #5,d0                       ; f8 << 15, then <<6 below = <<21
        lsl.l   #6,d0
        move.l  d0,OBJ_SPEED(a0)
        lea     mission_obj_f9,a1
        move.b  0(a1,d6.w),OBJ_F9(a0)
        move.w  d6,d5
        lsl.w   #2,d5
        lea     mission_obj_f10,a1
        move.l  0(a1,d5.w),OBJ_F10(a0)

        bsr     object_ground_sample            ; d0 raw height, d1 target
        ; DOS 00023297 stores (map_height * 2) + 11, saturating at 0xff.
        ; Keep the raw height here: deriving it from the already saturated
        ; target would be wrong for the top terrain row.
        move.b  d0,d1
        add.b   d1,d1
        addi.b  #11,d1
        bcc     .initial_altitude_ready
        moveq   #-1,d1
.initial_altitude_ready
        move.b  d1,OBJ_ALTITUDE(a0)             ; 0002338B [00021A25]
        rts                                     ; [00021AA7] is not written

; The per-type dispatch. 00006939 indexes the ten-entry table at 0002231C with
; the record's type byte and calls through it; each entry writes that type's
; own state and draw pointers into fields 1 and 0.
; DOS: flat 00006932-00006941 and the factory table at 0002231C.
; DOS symbol: inside loc_000068C1
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: selects the recovered state/draw pair for each authored type.
; Preserved: the ten-entry table, its index source, and the per-type pointers.
; Difference: types whose DOS entry reaches an unrecovered handler keep the
;   default pair rather than a substitute; sound and event-only side effects
;   are outside this milestone.
; Kind: translated.
; Status: ported for authored live-mission records.
object_factory_install
        move.w  object_spawn_index,d6
        lea     mission_obj_type,a1
        moveq   #0,d0
        move.b  0(a1,d6.w),d0
        move.l  #object_draw_pair_24fed,OBJ_DRAW(a0)
        move.l  #object_state_unit,OBJ_STATE(a0)        ; 000232EF [00020244] = 00023F60
        move.l  #object_fire_rock,OBJ_FIRE(a0)  ; 000232A8 [00021FB0] = 00022CA1
        cmpi.w  #0,d0
        beq     .fixed
        cmpi.w  #1,d0
        beq     .pair_24e05
        cmpi.w  #2,d0
        beq     .mobile_stinger
        cmpi.w  #5,d0
        beq     .mobile_hell
        cmpi.w  #6,d0
        beq     .pair_24e05_hell
        cmpi.w  #8,d0
        beq     .fire_hell
        cmpi.w  #3,d0
        beq     .oil_tank
        cmpi.w  #4,d0
        beq     .ally
        cmpi.w  #9,d0
        beq     .static
.done
        rts
.ally
        ; 00023424: state 00023840, draw 00024FED, and the slot into [00022368].
        move.l  #object_state_ally,OBJ_STATE(a0)
        move.l  a0,object_ally                  ; 0002343F
        rts
.pair_24e05
        move.l  #object_draw_pair_24e05,OBJ_DRAW(a0)
        rts
.pair_24e05_hell
        ; 000233A3: draw 00024E05, shot routine 00022DD0, state left at 00023F60.
        move.l  #object_draw_pair_24e05,OBJ_DRAW(a0)
.fire_hell
        ; 00023413: shot routine 00022DD0 only.
        move.l  #object_fire_hell,OBJ_FIRE(a0)
        rts
.mobile_stinger
        ; 000233DB: state 00023CF0, shot routine 00022D33.
        move.l  #object_state_mobile,OBJ_STATE(a0)
        move.l  #object_fire_stinger,OBJ_FIRE(a0)
        rts
.mobile_hell
        ; 000233F7: state 00023CF0, shot routine 00022DD0.
        move.l  #object_state_mobile,OBJ_STATE(a0)
        move.l  #object_fire_hell,OBJ_FIRE(a0)
        rts
.static
        move.l  #object_draw_sprite,OBJ_DRAW(a0)
        move.l  #object_state_static,OBJ_STATE(a0)
        rts
.oil_tank
        ; Dispatch slot 3 is 00023446: state 00023A8C and draw 0002514D.
        move.l  #object_draw_sprite,OBJ_DRAW(a0)
        move.l  #object_state_idle,OBJ_STATE(a0)
        rts
.fixed
        ; Type 0 is the fixed slot-31 path at 00023462. The caller supplies
        ; that slot, so only its recovered state/draw pair is installed here.
        move.l  #object_state_fixed,OBJ_STATE(a0)
        move.l  #object_draw_fixed,OBJ_DRAW(a0)
        clr.b   OBJ_AUX(a0)                     ; 00023484 [00021DB3] = 0
        rts


; DOS 00024391-0002445D. Everything within the blast of the object in a0 takes
; damage, and the player is tested separately.
;
; The shape is worth keeping exactly: the test is square, not circular - X and
; Y are compared against the radius independently, with no distance - and the
; vertical test is on half the altitude difference, so it reaches twice as far
; as the constant suggests. Health is a byte and the damage is subtracted from
; it; a borrow, not a comparison, is what marks the object destroyed.
;
; In: a0 = the exploding object.
; DOS: flat 00024391-0002445D, square blast/object damage test.
; DOS symbol: loc_00024391
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: applies authored damage and player-hit tests to the Falcon object table.
; Preserved: independent X/Y bounds, doubled altitude reach, byte health borrow.
; Kind: translated.
; Status: ported; weapon dispatch that calls it remains unrecovered.
object_blast
        movem.l d0-d1/d7/a0-a2,-(sp)
        move.l  a0,a2
        lea     object_table,a1
        move.w  #OBJ_COUNT,d7
.next
        cmpa.l  a1,a2
        beq     .skip                           ; never damages itself
        tst.b   OBJ_ACTIVE(a1)
        beq     .skip

        moveq   #0,d0
        move.b  OBJ_ALTITUDE(a2),d0
        moveq   #0,d1
        move.b  OBJ_ALTITUDE(a1),d1
        sub.w   d1,d0
        bpl     .alt_positive
        neg.w   d0
.alt_positive
        cmpi.w  #BLAST_ALT,d0
        bhi     .skip

        move.l  OBJ_X(a2),d0
        sub.l   OBJ_X(a1),d0
        bpl     .x_positive
        neg.l   d0
.x_positive
        cmpi.l  #BLAST_RADIUS,d0
        bhi     .skip
        move.l  OBJ_Y(a2),d0
        sub.l   OBJ_Y(a1),d0
        bpl     .y_positive
        neg.l   d0
.y_positive
        cmpi.l  #BLAST_RADIUS,d0
        bhi     .skip

        move.b  OBJ_HEALTH(a1),d0
        sub.b   #BLAST_DAMAGE,d0
        move.b  d0,OBJ_HEALTH(a1)
        bcc     .skip                           ; no borrow, still standing
        ori.b   #1,OBJ_DAMAGE(a1)
.skip
        lea     OBJ_SIZE(a1),a1
        subq.w  #1,d7
        bne     .next

        ; The player, against the frame viewer snapshot and the latched
        ; altitude - the same two values the original compares at 0002441B and
        ; 00024404, and the reason both are latched at frame start.
        moveq   #0,d0
        move.b  OBJ_ALTITUDE(a2),d0
        move.w  viewer_altitude_latched,d1
        sub.w   d1,d0                           ; both already DOS units
        bpl     .p_alt
        neg.w   d0
.p_alt
        cmpi.w  #BLAST_ALT,d0
        bhi     .done
        move.l  OBJ_X(a2),d0
        sub.l   flt_frame_x,d0
        bpl     .p_x
        neg.l   d0
.p_x
        cmpi.l  #BLAST_RADIUS,d0
        bhi     .done
        move.l  OBJ_Y(a2),d0
        sub.l   flt_frame_y,d0
        bpl     .p_y
        neg.l   d0
.p_y
        cmpi.l  #BLAST_RADIUS,d0
        bhi     .done
        move.w  #1,player_hit_flag
.done
        movem.l (sp)+,d0-d1/d7/a0-a2
        rts

; A generic damage sweep used to sit here: it walked all 130 slots, cleared
; every object whose damage byte had bit 0 set, and counted the mission's
; targets down as it went. Nothing in the original does that. 000234A4 walks
; the slots and calls each object's own handler, then tail-jumps to 00024B17;
; retirement is 000237BF's `mov byte [00021921+slot], 0` inside the wreckage
; state, reached by that object's own state graph, and the mission target
; count has no writer in the recovered range at all. The sweep was dormant -
; nothing called it - but it was a second, invented object lifetime sitting
; next to the recovered one, so it is gone rather than annotated.
;
; DOS 00024B17. The whole object draw stage: view transform, depth sort, then
; a far-to-near walk calling each object's own draw handler.
;
; The original keeps the sort order in field -2 of the table - the field the
; map recorded as "unknown (zero)", because it holds zero in the image and is
; only ever written at runtime. 00024BDA reads it as `mov ecx,[ebp*4+0001FC2C]`
; and treats the result as an object index, and the loop above it exchanges its
; entries, so it is a draw-order list rather than per-object data. Here it is a
; separate array, since nothing about it wants to live inside the struct.
;
; Sorting is the point of the stage. Objects are drawn farthest first so that
; nearer ones overwrite them, which is the only depth resolution sprites get.
; DOS: flat 00024B17, object transform/sort/draw stage.
; DOS symbol: sub_00024B17
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: transforms, depth-sorts, and dispatches active authored draw handlers.
; Preserved: frame snapshot, far-to-near ordering, the two walk tests, and
;   staging. The range and fan culls live where the original keeps them, in
;   the shared prologue - see object_aspect and object_mark_targetable.
; Kind: translated.
; Status: ported.
object_draw_pass
        ; Cleared per frame so a capture reads this frame's tallies. They are
        ; the proof the cull did something: a cull that silently never fires
        ; leaves frame time and every pixel unchanged, which is exactly how
        ; F030TREX's triangle prepass passed validation while killing nothing.
        bsr     object_view_transform
        bsr     object_depth_sort

        ; 00024BCB walks all 130 order slots descending and skips the
        ; inactive ones inside the loop, which is what happens below.
        ; 00024BD0: the frame's default target is cleared BEFORE the walk, so
        ; what 00024DFC leaves in it is the last object that passed this
        ; frame's test and nothing older. Without this clear the latch seeds
        ; from a stale slot, 0000D449 finds that object's targetability byte
        ; clear and drops the lock in the same frame it was taken - which is
        ; exactly how the right MFD stayed black with a working object pass.
        ; The same DOS routine is called a second time by 00007860 while its
        ; camera globals point at the locked target. That pass is composition
        ; into the MFD, not a second target-selection pass: leave the main
        ; frame's target bytes and default intact while it is active.
        tst.w   object_target_view
        bne     .target_view_state
        clr.w   object_target_default
.target_view_state
        ; DESCENDING, as the comment above says and 00024BDA's `mov ebp,0x82 ...
        ; dec ebp / jne` does: the sort leaves the greatest depth at position
        ; 130, so the walk draws the farthest object first and the nearest
        ; last. This walked object_order upward - nearest first - so anything
        ; behind a nearer object was painted over it, and the last slot that
        ; passed the targetability test (which is what [00019D18] keeps) was
        ; the farthest instead of the nearest.
        move.w  #OBJ_COUNT,d7
        lea     object_order+OBJ_COUNT*2,a2
.next
        move.w  -(a2),d6                        ; 1-based object index
        move.w  d6,d0
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a0
        adda.l  d0,a0
        ; 00024DA4 compares the object's own index against 0x1E, and
        ; 00024DFC stores that index. The DOS arrays are indexed by it
        ; directly, so it is the 1-based slot the order list carries.
        move.w  d6,object_slot_index
        ; 00024BE1 clears [ecx + 0x21BAB] for EVERY slot the walk visits, in
        ; front of the active and depth tests below - so an object that stops
        ; being drawn stops being targetable on the same frame. Clearing it
        ; where the byte is written instead leaves it set on everything the
        ; culls reject.
        tst.w   object_target_view
        bne     .keep_targetable
        clr.b   OBJ_TARGETABLE(a0)
.keep_targetable
        tst.b   OBJ_ACTIVE(a0)
        beq     .skip
        tst.l   OBJ_DEPTH(a0)                   ; behind the viewer
        bmi     .skip

        ; 00024BE8/00024BF1 are the walk's ONLY two tests - active, and a
        ; non-negative depth - and 00024BFC dispatches. Two more used to stand
        ; here, both this port's own: a range cull at OBJ_DRAW_RANGE (992 map
        ; units, reasoned from how far the march reaches) and a fan cull that
        ; dropped anything with |lateral| past its depth, reasoned from "the
        ; surface spans lateral/depth in -1..+1". The original culls on both
        ; counts, but in the shared prologue and at its own bounds:
        ; 00024C45 rejects a depth above 0x1FFFFFFF - 512 map units, not 992 -
        ; and the fan test is 00024D93/00024D9A's band on v, which is about
        ; 50 degrees either side and not 45. Between them the invented pair
        ; drew objects past the point the original stops (with a ring-search
        ; key that has WRAPPED - depth << 3 passes 2^32 at 512 units, which is
        ; exactly why the bound is there) and dropped objects it draws.
        move.l  OBJ_DRAW(a0),d0
        beq     .skip
        move.l  d0,a1
        movem.l d6-d7/a0/a2,-(sp)
        jsr     (a1)
        movem.l (sp)+,d6-d7/a0/a2
        bra     .skip
.skip
        subq.w  #1,d7
        bne     .next
.none
        rts

; DOS 00024B17-00024B7F. Rotate every active object's position into the
; viewer's frame, giving a forward distance and a sideways one.
;
; The original reads the frame viewer snapshot [00019CDC]/[00019CE0] here, not
; the live player position - which is what that snapshot is for, and why
; frame_driver takes it before the renderer runs. Using the live position would
; make objects lag or lead the terrain by a frame.
;
; DOS composes the view rotation from the Q31 pair built by 00007D25. Use the
; same full-angle pair as the CPU terrain path; player_heading is only the
; lossy 8-bit value retained for sprite-bank compatibility.
; DOS: flat 00024B17-00024B7F, object viewer-space transform.
; DOS symbol: sub_00024B17
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: applies the recovered Q31 matrix to the objects' 10.22 coordinates.
; Preserved: depth/lateral signs, frame-start viewer snapshot, and precision.
; Kind: translated.
; Route: analysis/functions/falcon-attract.md#object-pass.
; Status: ported; the same transform is reached by the traced attract pass.
object_view_transform
        movem.l d0-d7/a0-a2,-(sp)
        ; 00024B45/00024B4E read [00019CB0]/[00019CB4] - the VIEW pair
        ; 00007D25 built, not a pair derived from the flight angle. They are
        ; the same in the cockpit and they are not in the two external views,
        ; where the frame looks somewhere the helicopter is not pointing.
        ; 00007860 substitutes the target's camera globals before calling
        ; 00024B17. mfd_draw_target_view installs the equivalent Falcon
        ; 16.16 position and Q31 basis in the ordinary renderer globals, so
        ; this is the same matrix with no second coordinate convention.
        move.l  view_sin,d2
        move.l  view_cos,d3
        move.l  d3,d6                           ; retain cos across helper calls

        lea     object_table,a0
        move.w  #OBJ_COUNT,d7
.object
        tst.b   OBJ_ACTIVE(a0)
        beq     .step

        ; 00024B2E-00024B70, as written: each delta is the 10.22 difference
        ; halved (sar ebx,1), and each product keeps only edx, the high dword of
        ; the signed 64-bit result - so the values are 12.20 and the low bits
        ; are floors. Depth [00020A64] = hi(sin*dx) - hi(cos*dy) is the same
        ; (sin, -cos) forward axis the terrain marcher walks, and lateral
        ; [0002085C] = hi(cos*dx) + hi(sin*dy); an earlier revision stored the
        ; two the other way round and turned the whole object field a quarter
        ; turn against the terrain.
        ; 00024B2E/00024B3D subtract the LIVE [00019CD4]/[00019CD8], which
        ; inside the frame driver's push/pop window is whatever camera
        ; 00007D25 left - the helicopter in the cockpit, fifteen cells behind
        ; it in variant 6, a fixed point on the ground in variant 7. Using the
        ; frame snapshot here drew the objects from the helicopter while the
        ; terrain was marched from the camera.
        move.l  OBJ_X(a0),d0
        sub.l   flt_x,d0                        ; 00024B2E, 10.22
        asr.l   #1,d0                           ; 00024B34 sar ebx, 1
        move.l  d0,a2                           ; ebx
        move.l  OBJ_Y(a0),d1
        sub.l   flt_y,d1                        ; 00024B3D
        asr.l   #1,d1                           ; 00024B43 sar ebp, 1
        move.l  d1,a1                           ; ebp

        move.l  a2,d0
        move.l  d6,d3
        bsr     .hi32                           ; 00024B4A imul ebx by [00019CB4]
        move.l  d0,d4
        move.l  a1,d0
        move.l  d2,d3
        bsr     .hi32                           ; 00024B53 imul ebp by [00019CB0]
        add.l   d0,d4                           ; 00024B55
        move.l  d4,OBJ_LATERAL20(a0)            ; 00024B69 [0002085C]
        asr.l   #4,d4
        move.l  d4,OBJ_LATERAL(a0)              ; the 16.16 readers

        move.l  a2,d0
        move.l  d2,d3
        bsr     .hi32                           ; 00024B5C imul ebx by [00019CB0]
        move.l  d0,d4
        move.l  a1,d0
        move.l  d6,d3
        bsr     .hi32                           ; 00024B65 imul ebp by [00019CB4]
        sub.l   d0,d4                           ; 00024B67
        move.l  d4,OBJ_DEPTH20(a0)              ; 00024B70 [00020A64]
        asr.l   #4,d4
        move.l  d4,OBJ_DEPTH(a0)
.step
        lea     OBJ_SIZE(a0),a0
        subq.w  #1,d7
        bne     .object
        movem.l (sp)+,d0-d7/a0-a2
        rts

.hi32
        movem.l d1,-(sp)
        MulS64  d3
        move.l  d1,d0                           ; edx
        movem.l (sp)+,d1
        rts


; DOS 00024B81-00024BC9, a selection sort that repeatedly moves the largest
; remaining depth to the end. Reproduced as written rather than replaced with
; something faster: 130 entries at one pass per frame is not where the time
; goes, and an unstable reordering would change which sprite wins a tie.
; DOS: flat 00024B81-00024BC9, selection sort of object draw order.
; DOS symbol: inside loc_00024B77
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: sorts the Falcon index array by recovered forward depth.
; Preserved: largest-first selection and stable slot/object identity behavior.
; Kind: translated.
; Route: analysis/functions/falcon-attract.md#object-pass.
; Status: ported; the same far-to-near order is reached by the traced attract pass.
object_depth_sort
        movem.l d0-d7/a0-a2,-(sp)
        ; 00024B77 fills the identity 1..130 - inside the transform loop, at
        ; the join point both the active and the skipped path reach - and
        ; 00024B81 sorts all 130. This used to compact the array to the active
        ; slots and sort only those, on the argument that the draw loop skips
        ; inactive objects anyway so their position was never observable. That
        ; is true, and it still meant carrying a live-object count that the
        ; original does not keep and that four other routines maintained as if
        ; it were game state. The identity fill is the original's and costs
        ; nothing to keep.
        ; Each position's depth is snapshotted beside it. The comparison used
        ; to be a `bsr .depth_of` that re-derived the object address every
        ; time: MOVEM of four registers, `mulu #OBJ_SIZE` and the table read,
        ; measured at 17,028 calls and 1,229,646 cycles - 3.8% of the frame -
        ; for 8,385 comparisons of 130 entries. Nothing writes OBJ_DEPTH
        ; during the sort, so reading it once per entry is the same value the
        ; original reads at every compare, and the two arrays are swapped
        ; together so key[i] is always the depth of order[i].
        ;
        ; The comparison sequence, the `blt` and therefore the tie rule are
        ; untouched: the largest remaining depth still moves to the end and an
        ; equal depth still displaces the incumbent, exactly as 00024B81 does.
        lea     object_order,a2
        lea     object_depth_key,a1
        lea     object_table,a0
        move.w  #OBJ_COUNT,d7
        moveq   #1,d0                           ; 1-based slot number
.fill
        move.w  d0,(a2)+                        ; 00024B77 [i*4+0001FC2C] = i
        move.l  OBJ_DEPTH20(a0),(a1)+           ; and that slot's depth, 12.20 as 00024B81 compares it
        lea     OBJ_SIZE(a0),a0
        addq.w  #1,d0
        subq.w  #1,d7
        bne     .fill

        lea     object_order,a2
        lea     object_depth_key,a1
        move.w  #OBJ_COUNT,d7
        subq.w  #1,d7                           ; last index to place
        ble     .sorted                         ; nothing, or one, to order
.pass
        move.w  d7,d6                           ; best position so far
        move.w  d7,d5
        add.w   d5,d5
        add.w   d5,d5
        move.l  0(a1,d5.w),d4                   ; best depth so far
        move.w  d7,d3
.scan
        subq.w  #1,d3
        bmi     .place
        move.w  d3,d5
        add.w   d5,d5
        add.w   d5,d5
        move.l  0(a1,d5.w),d0
        cmp.l   d4,d0
        blt     .scan
        move.l  d0,d4
        move.w  d3,d6
        bra     .scan
.place
        move.w  d7,d0
        add.w   d0,d0
        move.w  d6,d1
        add.w   d1,d1
        move.w  0(a2,d0.w),d2
        move.w  0(a2,d1.w),d5
        move.w  d5,0(a2,d0.w)
        move.w  d2,0(a2,d1.w)
        add.w   d0,d0                           ; the same two positions again,
        add.w   d1,d1                           ; as longword offsets
        move.l  0(a1,d0.w),d2
        move.l  0(a1,d1.w),d5
        move.l  d5,0(a1,d0.w)
        move.l  d2,0(a1,d1.w)
        subq.w  #1,d7
        bne     .pass
.sorted
        movem.l (sp)+,d0-d7/a0-a2
        rts


; Return the exact DOS projection-page row for the object in a0.
;
; DOS 00024C45/00024D5E selects the first .DTL ring at or beyond the forward
; depth, then indexes that ring's 256-byte page with the byte-wide altitude
; expression. The row is kept in the DOS surface's bottom-up page space: the
; Falcon screen Y is OBJECT_PAGE_ANCHOR minus this value. This routine is
; shared by the pair-order test and the sprite compositor so neither can drift
; to an analytic replacement.
; In: a0 = object. Out: d0 = page row; object_page_valid says whether the
; depth found a DOS ring.
; DOS: flat 00024CC0-00024D73.
; DOS symbol: inside loc_00024CA3
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: performs the same unsigned ring search and page lookup.
; Preserved: depth bias, ring selection, altitude byte arithmetic, and page row.
; Kind: translated.
; Status: ported; used by live-mission object composition.
object_find_page
        movem.l d1-d7/a1,-(sp)
        move.l  OBJ_DEPTH20(a0),d6
        lsl.l   #3,d6                         ; 00024CC7 shl edi, 3: world<<23
        move.l  d6,d3
        cmpi.l  #$1800000,d3
        bcs     .no_near_bias
        subi.l  #$1800000,d3                  ; 00024CCA nearer clip key
.no_near_bias
        lea     ring_z_table,a1
        move.w  ring_steps,d7                 ; [0x19EE0], the loaded .DTL's count
.find_clip
        cmp.l   (a1),d3
        bls     .clip_found
        addq.l  #4,a1
        subq.w  #1,d7
        bne     .find_clip
        bra     .invalid
.clip_found
        ; 00024CFB-00024D06 stores the CLIP ring - the one the 0x1800000
        ; biased key found - as [0x22358], and that is what the sprite
        ; blitter clips against. The search then CONTINUES from the same
        ; cursor for the unbiased key, and that second ring is the one whose
        ; B divides and whose page is read. They are not the same ring
        ; whenever the object is further than the bias: the captured frame
        ; has clip ring 80 and page ring 81. Publishing the page ring for the
        ; clip, which is what this did, clips a model against the wrong
        ; ring's silhouette.
        move.l  a1,d5
        subi.l  #ring_z_table,d5
        lsr.l   #2,d5
        move.w  d5,object_project_ring
.find_ring
        cmp.l   (a1),d6                       ; unbiased key, same cursor
        bls     .ring_found
        addq.l  #4,a1
        subq.w  #1,d7
        bne     .find_ring
        bra     .invalid
.ring_found
        move.l  a1,d7
        subi.l  #ring_z_table,d7
        ; The page/B ring, from the unbiased key. 00024D28 reads this ring's
        ; lateral increment as the projection divisor, and 00024D43/00024D58
        ; take its 256-byte page.
        move.l  d7,d5
        lsr.l   #2,d5
        move.w  d5,object_b_ring
        lsl.l   #6,d7                         ; ring index * 256
        lea     ring_page_table,a1
        adda.l  d7,a1

        moveq   #0,d4
        move.b  player_altitude,d4
        andi.b  #$fe,d4
        not.b   d4
        moveq   #0,d5
        move.b  OBJ_ALTITUDE(a0),d5
        add.b   d5,d4
        roxr.b  #1,d4                         ; DOS ADD carry enters X
        andi.w  #$00ff,d4
        moveq   #0,d0
        move.b  0(a1,d4.w),d0
        move.b  d0,object_project_page
        ; 00024D78-00024D82: rows below 1 and above 0xFD are the page's clamps
        ; and mean the projection left the page; the object is not drawn.
        cmpi.w  #1,d0
        bcs     .page_out
        cmpi.w  #$fe,d0
        bcc     .page_out
        move.b  #1,object_page_valid
        movem.l (sp)+,d1-d7/a1
        rts
.page_out
        clr.b   object_page_valid
        moveq   #0,d0
        movem.l (sp)+,d1-d7/a1
        rts
.invalid
        move.w  #-1,object_project_ring
        clr.b   object_project_page
        clr.b   object_page_valid
        moveq   #0,d0
        movem.l (sp)+,d1-d7/a1
        rts


; The aspect angle: which way an object faces relative to the camera, as a
; 1-based bank frame. DOS 00024C45's tail, which is where the rotation actually
; happens:
;
;   shr ebx,1                 bearing from viewer to object, atan2 by octant
;   add al,[ecx+0002189F]     plus the object's own heading
;   add al,4 / shr al,3       rounded into 32 steps -> [0002237D]
;
; 0002514D then indexes a 32-byte table at model+2 with that, adds an elevation
; lookup from model+0x22, and the sum is the sprite index. The two tables are
; read from the validated '3D' model record in the loaded SG bank.
;
; Note what the byte arithmetic does and why it is kept: the adds and the shift
; are all byte-wide in the original, so the sum wraps at 256 and the result is
; 0..31 by construction. Doing this in words would need an explicit modulo and
; would get the wrap at the half-turn boundary wrong.
;
; In: a0 = object, with OBJ_DEPTH positive - the caller culls behind the camera.
; Out: d0 = 1-based frame in the loaded bank.
; DOS: flat 00024C45-00024D71 and 0002514D, model aspect/elevation lookup.
; DOS symbol: sub_00024C45
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: reads the validated SG `3D` record's azimuth/elevation tables.
; Preserved: octant bearing, byte wrapping, table sum, and mirror bit.
; Kind: translated.
; Status: ported; model/factory availability remains an explicit prerequisite.
object_aspect
        movem.l d1-d7/a1-a2,-(sp)

        ; 00024C45, the shared prologue's first instruction: a forward depth
        ; above 0x1FFFFFFF goes to 00024E03 and the object is not drawn. That
        ; is 512 map units, and the bound is structural rather than a taste in
        ; draw distance - 00024CC7 forms the ring-search key as depth << 3,
        ; which passes 2^32 at exactly 512 units, so one unit further the key
        ; wraps and the search returns a near ring for a far object. This
        ; port's OBJ_DEPTH20 is the same 12.20, so the bound is the same.
        cmpi.l  #OBJ_DEPTH_LIMIT,OBJ_DEPTH20(a0)
        bgt     .none

        ; 00024C58: viewer Y minus object Y, off the LIVE [00019CD8] as the
        ; transform above is - both 10.22, as the original's.
        move.l  flt_y,d1
        sub.l   OBJ_Y(a0),d1                    ; 00024C58
        ; The zero comes FIRST: moveq sets N and Z from its own operand, so
        ; putting it between the difference and the branch made `bpl` always
        ; taken. 00024C64's `sets bl` reads the sign of the subtraction, and
        ; the shift above preserves it - (a-b)<<6 is (a<<6)-(b<<6) mod 2^32 -
        ; so the flags from the move into d3 are the ones to branch on.
        moveq   #0,d4                           ; SETS BL: Y sign bit
        move.l  d1,d3
        bpl     .y_nonnegative
        not.l   d3                              ; CDQ/XOR: one-complement magnitude
        moveq   #1,d4
.y_nonnegative

        ; 00024C6C: viewer X minus object X, with the same one-complement
        ; magnitude and sign bit. The x86 SHLD/SHL pair makes the octant index
        ; (Y-negative << 2) | (X-negative << 1) | (X <= Y).
        move.l  flt_x,d1
        sub.l   OBJ_X(a0),d1                    ; 00024C6C
        moveq   #0,d6
        move.l  d1,d5
        bpl     .x_nonnegative
        not.l   d5
        moveq   #1,d6
.x_nonnegative
        moveq   #0,d7
        move.l  d4,d7
        lsl.l   #2,d7
        move.l  d6,d1
        lsl.l   #1,d1
        or.l    d1,d7
        cmp.l   d3,d5                           ; x magnitude versus y magnitude
        bhi     .octant_ready                   ; original JA: x > y
        addq.l  #1,d7
        exg     d3,d5                           ; numerator=min, denominator=max
.octant_ready
        lea     object_octant_table,a1
        ; 00024C8B is `[ebx*4 + 0x22385]` - the octant selects a DWORD. An
        ; unscaled index read four bytes straddling two entries, which for
        ; octant 1 gave 0x00007F00 where the entry is 0 and every bearing came
        ; out of the wrong quadrant.
        move.l  0(a1,d7.l*4),d7
        move.l  d5,d1
        lsr.l   #8,d1
        lsr.l   #2,d1
        beq     .bearing_base
        move.l  d3,d0
        divu.l  d1,d0
        lea     object_bearing_correction,a1
        moveq   #0,d1
        move.b  0(a1,d0.l),d1
        eor.b   d1,d7
.bearing_base
        addq.l  #1,d7
        lsr.l   #1,d7
        ; 00024CB8/00024CBA: the ONE'S COMPLEMENT of this is kept per object,
        ; and it is the bearing the target view looks along - 000078D5 reads
        ; it and 00007900 shifts it into the view angle. Complemented because
        ; the value computed here is the direction from the object toward the
        ; viewer, and the view wants the opposite.
        not.b   d7
        move.b  d7,OBJ_VIEW_BEARING(a0)
        not.b   d7
        move.b  d7,d0                           ; 00024CA6: AL = BL
        add.b   OBJ_HEADING(a0),d0
        addq.b  #4,d0
        lsr.b   #3,d0
        moveq   #0,d1
        move.b  object_draw_aspect_bias,d1
        add.w   d1,d0                          ; pair B's recovered azimuth tweak
        andi.w  #$001f,d0                       ; 0..31, the aspect step

        ; The DOS prologue selects the projection page for this object's depth
        ; from the .DTL cumulative-depth table, then indexes it with the exact
        ; byte rotation used at 00024D5E-00024D71. It is the elevation byte,
        ; not the projected screen row and not a hand-picked band threshold.
        ; 00024E05/0002514D select the model base through the object record
        ; ([00020654]/[0002044C]), not through the startup TANK pointer. The
        ; active draw handler sets this per object; the fallback keeps field 2
        ; as the exact DOS model-A choice.
        move.l  object_draw_model_bank,a2
        tst.l   a2
        bne     .model_bank_ready
        move.l  OBJ_MODEL_A(a0),a2
        tst.l   a2
        beq     .none
.model_bank_ready
        moveq   #0,d2
        move.b  7(a2),d2
        lsl.l   #8,d2
        move.b  6(a2),d2
        lsl.l   #8,d2
        move.b  5(a2),d2
        lsl.l   #8,d2
        move.b  4(a2),d2
        cmpi.l  #OBJECT_BANK_BYTES-770,d2
        bhi     .none
        adda.l  d2,a2
        add.l   #770,a2
        cmpi.w  #$3344,(a2)
        bne     .none
        ; 00024CC0's search key is the forward depth in the A-accumulator's
        ; own units: [00020A64] holds world<<20 and the `shl edi,3` makes
        ; world<<23 - exactly what ring_z_table's raw table-4 dwords count,
        ; since the marcher's per-ring step is high32(A*sin) = A/2 map units
        ; and table 4 is the file's running total of A. The Falcon depth is
        ; 16.16, so seven left shifts form the same key at 16 fractional
        ; bits against the DOS 20. Both searches compare UNSIGNED - the far
        ; table words pass 2^31, which is why the file "wraps past 512".
        ;
        ; Two searches share one cursor, as 00024CC0-00024D16 do. The first
        ; runs on a key pulled 0x1800000 - three map units - nearer when that
        ; does not underflow (00024CCA jae): it selects the ring whose
        ; archived silhouette clips this sprite, an archive this port does
        ; not keep yet. The elevation search then CONTINUES from that ring
        ; with the unbiased key and the remaining count. A key past ring 249
        ; rejects the object: the DOS scan runs off the table into code
        ; bytes and reaches the same reject at 00024E03.
        move.l  OBJ_DEPTH20(a0),d6
        lsl.l   #3,d6                         ; 00024CC7 shl edi, 3: world<<23, the DOS edi
        move.l  d6,d3
        cmpi.l  #$1800000,d3
        bcs     .no_near_bias
        subi.l  #$1800000,d3                  ; the DOS esi
.no_near_bias
        lea     ring_z_table,a1
        move.w  ring_steps,d7                 ; [0x19EE0], the loaded .DTL's count
.find_clip
        cmp.l   (a1),d3
        bls     .clip_found                   ; 00024CEE jbe: first ring >= key
        addq.l  #4,a1
        subq.w  #1,d7
        bne     .find_clip
        bra     .none
.clip_found
        ; 00024CFB-00024D06: the CLIP ring is what the sprite blitter clips
        ; against, and it is published here rather than at .ring_found. This
        ; is the routine the draw path runs, so publishing it anywhere else
        ; leaves the clip reading a ring from a different call.
        move.l  a1,d5
        subi.l  #ring_z_table,d5
        lsr.l   #2,d5
        move.w  d5,object_project_ring
.find_ring
        cmp.l   (a1),d6                       ; 00024D0C, unbiased, same entry
        bls     .ring_found                   ; re-tested before advancing
        addq.l  #4,a1
        subq.w  #1,d7
        bne     .find_ring
        bra     .none                         ; 00024D16 -> 00024E03
.ring_found
        move.l  a1,d7
        subi.l  #ring_z_table,d7
        ; The unbiased ring: 00024D28's divisor comes from this one, not from
        ; the clip ring above.
        move.l  d7,d5
        lsr.l   #2,d5
        move.w  d5,object_b_ring
        lsl.l   #6,d7                         ; 00024D43: entry*4 -> ring*256
        lea     ring_page_table,a1
        adda.l  d7,a1                         ; long add: ring 128+ pages sit
                                              ; past a signed word's reach

        moveq   #0,d4
        move.b  player_altitude,d4
        andi.b  #$fe,d4
        not.b   d4
        moveq   #0,d5
        move.b  OBJ_ALTITUDE(a0),d5
        add.b   d5,d4
        roxr.b  #1,d4                         ; 68k X == the DOS ADD carry
        andi.w  #$00ff,d4
        moveq   #0,d5
        move.b  0(a1,d4.w),d5
        move.b  d5,object_project_page
        move.b  #1,object_page_valid
        ; 00024D78-00024D82 / 00025251-00025257: a page row below 1 or above
        ; 0xFD is not drawn at all - both variants jump to their no-draw exit.
        ; The two ends are the page's own clamps, so a row that lands on them
        ; is a projection that ran off the page rather than a position on it.
        cmpi.w  #1,d5
        bcs     .page_rejected
        cmpi.w  #$fe,d5
        bcc     .page_rejected

        ; 00024D84 continues straight from this test into the targetability
        ; tail, using the same ring, page row and lateral. It is a separate
        ; routine here only for length; the order is the original's.
        movem.l d0-d7/a0-a2,-(sp)
        bsr     object_mark_targetable
        movem.l (sp)+,d0-d7/a0-a2
        ; 00024D8A/00024D93/00024D9A all jump to 00024E03, which pops the
        ; return address of 00024C45's own caller and returns past it: an
        ; object whose fan position is off the screen is not drawn at all.
        ; The port's equivalent is a zero frame index, which the draw
        ; handlers already treat as no-draw.
        tst.b   object_fan_valid
        beq     .none

        add.b   object_elev_bias,d5           ; 00025... add al,[0002237F]
        andi.w  #$00ff,d5
        lsr.w   #4,d5                         ; 0002504B shr al,4
        moveq   #0,d3
        move.b  2(a2,d0.w),d3                 ; model azimuth table
        move.b  34(a2,d5.w),d4               ; model elevation table + 0x22
        add.b   d4,d3
        move.w  d3,d0
        btst    #7,d0                         ; DOS mirror bit in the index
        beq     .done
        andi.w  #$007f,d0
        ori.w   #SPRITE_MIRROR,d0
        bra     .done
.page_rejected
        clr.b   object_page_valid
.none
        moveq   #0,d0
.done
        movem.l (sp)+,d1-d7/a1-a2
        rts

; A draw handler that puts a sprite where the object is. DOS 0002519D is the
; counterpart: it takes its sprite index from a per-object byte at 000219A3,
; then picks a size band from a distance table and scales. The recovered scale
; path below uses the same distance band and ramp; object factories remain the
; only reason this handler is not active in the mission slice.
;
; In: a0 = object
; DOS: flat 0002519D-000253CD, object projection/scale/sprite draw.
; DOS symbol: inside loc_000250AA
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: projects with the terrain horizon and uses the recovered DTL scale index.
; Preserved: depth/range/fan culls, the recovered fan column [0x22365], the
;   horizon row, the scale ramp, and blit ordering.
; Kind: translated.
; Status: ported for authored live-mission records; event-only factory states
; remain dormant where their target-selection graph is not recovered.
; Is this object a valid target this frame, and where does its designator go?
;
; 00024DA4-00024DFC, the tail of the same routine that projects the object.
; It runs for every object drawn and leaves two per-object bytes plus
; [0x19D18], the seed the target latch takes when it is empty.
;
; The projection is the part worth stating exactly, because two readings of
; it are wrong in ways nothing on screen would show:
;
;   v = 128 + lateral / (B[b_ring] >> 3)
;
; The divisor is the RING'S LATERAL INCREMENT, not the object's depth -
; 00024D28 loads [ebx + 0x19EE4] and it is still in ebp at 00024D87. And the
; ring is the one found from the UNBIASED key, while the silhouette this
; then clips against comes from the 0x1800000-biased ring; the two differ
; whenever the object is beyond the bias.
;
; Verified against a captured frame with an off-centre target (an earlier
; capture had one dead centre, where every candidate formula agrees and
; nothing is proved). Object 27: lateral -19458571, depth 119499752, so key
; 955998016, B ring 81, B >> 3 = 1212253, giving v = 112 - and [0x21BAB] + 0x2E
; reads 112. horizon[v - 32] = 8 with row 76 gives ~(8 + 76) - 0x29 = 130, and
; [0x21C2D] reads 130.
;
; In:  a0 = the object record, with object_b_ring and object_project_page set
;      by the projection above.
; Out: OBJ_TARGETABLE / OBJ_DESIGNATOR written, object_target_default updated.
; DOS: flat 00024DA4-00024DFC, the targetability test.
; DOS symbol: inside sub_00024C45
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: the same tests in the same order against the same tables.
; Preserved: every range test and its bound, the horizon index base, the
;   silhouette clip, and both stored bytes.
; Kind: translated.
; Status: ported and certified. 2026-08-31: the corrected model reproduces a
;   frozen DOS frame's accept/reject on every live slot and its [0x21BAB]
;   byte exactly, and the port's own latch, RANGE readout and target-view
;   panel come up against it. Two faults closed with it, both conversions
;   rather than tests - see the two comments below and X86-M68K-MAP.md.
object_mark_targetable
        movem.l d0-d7/a1-a2,-(sp)
        ; No clear here: 00024DA4 opens on the 0x1E compare. The byte is
        ; cleared once per slot by the walk at 00024BE1.

        ; DOS order: 00024D84-00024D9F computes and publishes v FIRST, and
        ; only then does 00024DA4 test the slot. That matters now that v is
        ; the blit's own x - putting the slot test in front left every slot
        ; past 0x1E without one.
        clr.b   object_fan_valid

        ; 00024D84-00024D8E: v = 128 + lateral / (B[b_ring] >> 3).
        move.w  object_b_ring,d1
        lsl.w   #2,d1
        lea     ring_b_table,a1
        move.l  0(a1,d1.w),d2
        asr.l   #3,d2                           ; shr ebp, 3
        beq     .done                           ; 00024D8A je
        move.l  OBJ_LATERAL20(a0),d3
        ; The dividend is `esi`, reloaded from [0002085C] at 00024D46 - the lateral
        ; AS STORED, 12.20, which is OBJ_LATERAL20 here. The three extra shifts
        ; belong to `edi` alone (00024CC7 `shl edi,3`), the ring search's key. An
        ; earlier revision shifted a 16.16 value seven places, which made every
        ; quotient eight times too big: the accepted band
        ; [5,0xF5) collapsed to lateral/(B>>3) in [-15,+14], which is a few
        ; degrees either side of dead centre, and everything else failed
        ; 00024D93/00024D9A. That is why [00019D18] stayed 0 and the right
        ; MFD stayed black.
        divs.l  d2,d3                           ; idiv: truncates toward zero
        addi.l  #$80,d3                         ; 00024D8E add eax, 0x80
        ; 00024D93/00024D9A: outside [5, 0xF5) is not on screen.
        cmpi.l  #$f5,d3
        bcc     .done
        cmpi.l  #5,d3
        bcs     .done
        move.w  d3,d4                           ; v

        ; 00024D9F stores it in [0x22365], and 0002543A adds that byte to the
        ; blit's destination x - so v IS where the sprite is drawn, not only
        ; a targetability intermediate. Published here for object_draw_sprite;
        ; the flag distinguishes "v is in hand" from the three no-draw exits
        ; above, all of which reach 00024E03 and abort the caller's draw.
        move.w  d4,object_project_x
        move.b  #1,object_fan_valid

        ; The target-view object pass still needs the recovered fan projection,
        ; but its horizon is mfd_view_occl rather than the main 192-column
        ; cockpit horizon. Do not overwrite the main frame's targetability
        ; bytes or latch while composing the secondary view.
        tst.w   object_target_view
        bne     .done

        ; 00024DA4: only the first 0x1E objects can be targets.
        move.w  object_slot_index,d0
        cmpi.w  #$1e,d0
        bhi     .done

        moveq   #0,d5
        move.b  object_project_page,d5          ; the row, [0x22366]

        ; 00024DA9-00024DC0: a = ~(horizon[v - 32] + row) - 0x29, kept only
        ; when it is below 0xC8. The index base is the array MINUS 32, so
        ; v = 128 - the centre of v's range - selects entry 96, the centre of
        ; the 192-entry array. 0x3CB20 against an array at 0x3CB40.
        move.w  d4,d6
        subi.w  #32,d6
        bmi     .done
        cmpi.w  #TERRAIN_COLS,d6
        bcc     .done
        lea     backdrop_dy,a1
        move.w  0(a1,d6.w*2),d7
        add.w   d5,d7
        not.b   d7
        andi.w  #$00ff,d7
        subi.w  #$29,d7
        bcs     .done                           ; the SUB borrowed
        cmpi.w  #$c8,d7
        bcc     .done
        move.b  d7,OBJ_DESIGNATOR(a0)

        ; 00024DCC-00024DD7: v - 0x2E must be above 3 and at most 0xA0.
        move.w  d4,d6
        subi.w  #$2e,d6
        bcs     .done
        cmpi.w  #$a0,d6
        bhi     .done
        cmpi.w  #3,d6
        bls     .done

        ; 00024DDD-00024DF4: reject when the terrain in front is higher than
        ; the object. The silhouette is the CLIP ring's, not this one's -
        ; 00024D06 stored that ring, and the two differ beyond the bias.
        ;
        ; render_ring_occlusion returns the row in a0, which is this routine's
        ; object pointer, so a0 is saved across the call. The row itself is
        ; the original's: bytes of page rows, compared unsigned.
        move.w  object_project_ring,d0
        bmi     .done
        move.l  a0,-(sp)
        bsr     render_ring_occlusion
        move.l  a0,a1
        move.l  (sp)+,a0
        move.l  a1,d0
        beq     .store
        ; 00024DEA indexes the ring row by v, and the row's own 192 entries
        ; start 0x20 into it: 0000F2F7 archives them at [00019E60] + ring*256
        ; + 0x20, and 000254C0's `rol al,1` reaches them with the same 0x20
        ; bias from a byte column. v is therefore a 256-wide surface column
        ; and the source column is v - 0x20 - which is why v = 0x80 is the
        ; centre of a 192-column field. The port stores the 192 alone, so the
        ; bias comes off here, exactly as it already does for the horizon
        ; array eleven lines above. Reading entry v read a column 32 to the
        ; right of the object.
        ;
        ; No bound is needed: 00024DD1-00024DDB has already required
        ; v - 0x2E in (3, 0xA0], so v is in [0x32, 0xCE] and v - 0x20 in
        ; [18, 174] - inside the row on every path that reaches here.
        move.w  d4,d1
        subi.w  #32,d1
        move.b  0(a1,d1.w),d1                   ; 00024DEA: the page row
        andi.w  #$00ff,d1

        cmp.w   d1,d5                           ; 00024DF2 cmp bl,bh
        bcs     .done                           ; 00024DF4 jb: behind terrain

.store
        move.b  d6,OBJ_TARGETABLE(a0)           ; 00024DF6
        move.w  object_slot_index,d0
        move.w  d0,object_target_default        ; 00024DFC
.done
        movem.l (sp)+,d0-d7/a1-a2
        rts

; The right MFD's page 2: the target view.
;
; 00007860 saves the camera basis, position, altitude and view angle, puts
; the LOCKED TARGET's viewpoint in their place, marches, runs the object pass
; and pops all eight dwords back. The port's marcher takes its camera as
; arguments, so there is nothing to save or restore here - that is the whole
; of the difference.
;
; The viewpoint, read by address from 000078BD-00007903:
;
;   angle = bearing << 24              where bearing is the object's 0x21CAF
;   X     = OBJ_X - high32(0x10000000 * sin[bearing])
;   Y     = OBJ_Y + high32(0x10000000 * cos[bearing])
;   alt   = OBJ_ALTITUDE
;
; so the camera sits one 0x10000000 step back along the bearing and looks
; down it. 0001B272 then derives the basis from that angle, and (angle >> 23)
; * 4 lands on the same table entry 000078E1's [ebx*8 + 0x32320] does, which
; is why sine_q31 needs nothing added for it.
;
; 0000789E/000078A8 zero [0x19CF0]/[0x19CF4] for the duration. Those are the
; pitch/roll pair the flight view shears its horizon with; the marcher itself
; never reads them, and this port's does not either, so there is nothing to
; zero.
;
; DOS: flat 00007860-00007942, the target view's camera substitution.
; DOS symbol: sub_00007860
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: marches the recovered view from the locked target's viewpoint.
; Preserved: the gate on an empty latch, the viewpoint arithmetic, and the
;   bearing's angle form.
; Difference: the Falcon composes the target crop directly into RGB565 rather
;   than rendering DOS's shared planar surface and copying it at 000079F0.
;   The secondary 00024B17 pass and its per-ring target silhouette clip are
;   otherwise executed before the RANGE readout at 000079D1/000079DE.
; Kind: translated.
; Status: ported; renders whenever a target is locked.
mfd_draw_target_view
        movem.l d0-d7/a0-a3,-(sp)
        ; 00007860/00007868: no locked target, no march. The original falls
        ; through to its transfer, which without a march re-copies whatever
        ; the surface already held - the main view's, which
        ; render_nolock_capture kept (.no_lock below).
        moveq   #0,d0
        move.w  object_target_latch,d0
        beq     .no_lock
        cmpi.w  #OBJ_COUNT,d0
        bhi     .done
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a0
        adda.l  d0,a0

        moveq   #0,d7
        move.b  OBJ_VIEW_BEARING(a0),d7         ; 000078D5
        move.l  d7,d1
        lsl.l   #3,d1                           ; the original's [ebx*8]
        lea     sine_q31,a1
        move.l  0(a1,d1.l),a2                   ; sin, DOS 0x32120
        move.l  512(a1,d1.l),a3                 ; cos, DOS 0x32320

        ; 000078DC-000078FA: one 0x10000000 step back along the bearing.
        ;
        ; 000078BD/000078C9 read the object's position out of [0x20C6C] /
        ; [0x20E74], the DOS 10.22 the marcher walks in, and the step is
        ; high32(0x10000000 * sin), a 10.22 quantity because the original's
        ; `imul` is against one. (Objects were 16.16 once, and the camera then
        ; needed six left shifts; they are 10.22 now and need none.)
        move.l  #$10000000,d0
        move.l  a2,d3
        bsr     ring_mul_q31_raw
        move.l  OBJ_X(a0),d4
        sub.l   d0,d4                           ; 000078FA sub
        move.l  #$10000000,d0
        move.l  a3,d3
        bsr     ring_mul_q31_raw
        move.l  OBJ_Y(a0),d5
        add.l   d0,d5                           ; 000078E8 add

        moveq   #0,d6
        move.b  OBJ_ALTITUDE(a0),d6             ; 000078B2

        move.l  d4,d0
        move.l  d5,d1
        move.l  d6,d2
        move.l  d7,d3
        lsl.l   #8,d3
        lsl.l   #8,d3
        lsl.l   #8,d3                           ; 00007900: bearing << 24
        jsr     mfd_march_target_view

        ; 0000790E calls the same 00024B17 object pass while the target
        ; camera substitution is still installed. The Falcon marcher takes
        ; arguments, so install the equivalent renderer globals only around
        ; this second pass and restore the cockpit camera before the RANGE
        ; readout and the rest of the HUD continue.
        move.l  flt_x,-(sp)
        move.l  flt_y,-(sp)
        move.b  player_altitude,-(sp)
        move.l  view_sin,-(sp)
        move.l  view_cos,-(sp)
        move.l  d4,flt_x                        ; 000078BD: [00019CD4]/[00019CD8]
        move.l  d5,flt_y
        move.b  d6,player_altitude
        move.l  mfd_view_sin,view_sin
        move.l  mfd_view_cos,view_cos
        move.w  #1,object_target_view
        bsr     object_draw_pass
        clr.w   object_target_view
        move.l  (sp)+,view_cos
        move.l  (sp)+,view_sin
        move.b  (sp)+,player_altitude
        move.l  (sp)+,flt_y
        move.l  (sp)+,flt_x

        ; 000079AF-000079E3: the RANGE readout, under the panel the view was
        ; just composed into. It is gated on the same latch this routine
        ; already tested, so the test is not repeated here.
        ;
        ; The x anchor is a PAGE x in the left panel's coordinates, as
        ; 000079F0's own destination is: 0x37CE is page row 174, byte column
        ; 18, and 18*4 = 72 = MFD_X. Both MFD bodies run through the one
        ; handler table at 0x19E10, so the handler draws at the left panel and
        ; the right one is the same picture MFD_PANEL_STEP further along -
        ; which is the convention mfd_march_target_view's span writer already
        ; follows. Checked against the original rather than assumed: in
        ; work/qemu_out/screen_t55.png the readout measures x 193..227 on
        ; rows 211..215, and 0x75 + MFD_PANEL_STEP - PAGE_VIEW_X puts element
        ; 0x20's 23 pixels at 193 and hud_draw_value's units digit at 227.
        ;
        ; The DOS machine has one VGA DAC, so 00025B27 has no palette to
        ; select; on the Falcon each bank carries its own expansion and the
        ; caller names it. These are HUDS elements, so they take HUDS's
        ; palette - the same selection hud_draw_dynamic makes around its own
        ; 00025B27 calls. Without it the readout draws through whatever the
        ; terrain left installed and comes out grey.
        move.l  sprite_palette,-(sp)
        move.l  #hud_palette,sprite_palette
        moveq   #$20,d0                         ; 000079CA
        move.w  #$75,d1                         ; 000079B9
        add.w   mfd_body_offset,d1              ; 00025B61 + [0x19CA8]
        move.w  #$d7,d2                         ; 000079C3
        move.l  work_screen,a0
        lea     hud_bank,a1
        bsr     sprite_draw_page                ; 000079D1

        ; 000079D6/000079DB: the depth latched at 0000D43D, in whole map
        ; units. The DOS value is world<<20 and `sar eax,0x14` takes it down;
        ; this port's OBJ_DEPTH is world<<16, so the same shift is 16.
        move.l  hud_target_range,d0
        swap    d0
        ext.l   d0
        ble     .range_done                     ; nothing to print behind us
        move.w  #$75,d1
        add.w   mfd_body_offset,d1
        move.w  #$d7,d2
        bsr     hud_draw_value                  ; 000079DE
.range_done
        move.l  (sp)+,sprite_palette
.done
        movem.l (sp)+,d0-d7/a0-a3
        rts
.no_lock
        ; 00007943-000079AA: the same 000079F0 transfer, over the surface the
        ; main view left. 000079AF's RANGE readout is gated on the latch.
        lea     mfd_nolock_buf,a1
        move.l  work_screen,a0
        lea     MFD_Y*SCREEN_STRIDE+(MFD_SURFACE_X+MFD_PANEL_STEP)*2(a0),a0
        moveq   #MFD_H-1,d1
.nl_row
        move.l  a0,a2
        moveq   #MFD_W/2-1,d0
.nl_pair
        move.l  (a1)+,(a2)+
        dbra    d0,.nl_pair
        lea     SCREEN_STRIDE(a0),a0
        dbra    d1,.nl_row
        bra     .done

; Drop the lock when its target is no longer on screen.
;
; 0000D439-0000D45E: the frame driver reads the locked object's targetability
; byte, and 0000D452's `jne` is the only thing that keeps the lock - a zero
; byte falls into 00024D454 and clears [0x19D10]. The byte is rebuilt every
; frame by the object pass, so this is what makes a lock expire when its
; target goes off screen or behind terrain.
; DOS: flat 0000D439-0000D45E, the lock's per-frame validity test.
; DOS symbol: inside loc_0000D433
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: clears the same latch on the same condition.
; Preserved: the test and its consequence; the designator placement that
;   shares the block is separate and not ported.
; Kind: translated.
; Status: ported.
object_target_validate
        movem.l d0-d2/a0-a1,-(sp)
        ; 0000D418: a console variant past 5 skips this whole block - the
        ; clear, the latch validation and the designator stores alike.
        cmpi.b  #5,hud_console_variant
        bhi     .out

        ; 0000D421-0000D428: the designator's x for THIS page half is cleared
        ; every frame, before the latch is read, so a frame that ends without
        ; a lock draws no marker. [0x19D87] is the page half; on the Falcon it
        ; is the work-buffer index, which alternates the same way.
        moveq   #0,d2
        move.b  hud_console_page,d2
        move.w  d2,d1
        lsl.w   #2,d1
        lea     hud_variant_x,a1
        clr.l   0(a1,d1.w)

        moveq   #0,d0
        move.w  object_target_latch,d0
        beq     .out                            ; 0000D439/0000D43B
        move.w  d0,d1
        subq.w  #1,d1
        mulu    #OBJ_SIZE,d1
        lea     object_table,a0
        adda.l  d1,a0
        ; 0000D43D-0000D444: the locked object's depth is latched BEFORE the
        ; validity test, so the frame that drops the lock still latches it.
        ; 000079D6 is the only reader.
        move.l  OBJ_DEPTH(a0),hud_target_range
        tst.b   OBJ_TARGETABLE(a0)              ; 0000D449
        beq     .drop                           ; 0000D452 jne: keep it

        ; 0000D460-0000D478, which this routine used to stop short of: the
        ; locked object's own two bytes become the designator's position -
        ; page x = 2 * [0x21BAB] (00024DF6 stored v - 0x2E, and the marker
        ; sits at twice that) and row = [0x21C2D]. 0000D8AE draws there.
        ; Without these stores the tables stay zero and the null gate at
        ; 0000D8C5 skips the marker on every frame, which is why the port
        ; has never drawn the box the original puts over its target.
        move.w  d2,d1
        lsl.w   #2,d1
        moveq   #0,d0
        move.b  OBJ_TARGETABLE(a0),d0
        add.w   d0,d0                           ; 0000D450 shl eax,1
        move.l  d0,0(a1,d1.w)                   ; [ebx*4 + 0x19D1C]
        lea     hud_variant_y,a1
        move.b  OBJ_DESIGNATOR(a0),0(a1,d2.w)   ; [ebx*4 + 0x19D24]
        bra     .out
.drop
        clr.w   object_target_latch             ; 0000D454
.out
        movem.l (sp)+,d0-d2/a0-a1
        rts

; The locked target, and the key that cycles it.
;
; 0001922C-000192A3. Two things feed it: the live select key at
; [0x1AFF]/[0x1B0C], and a pending count at [0x19DF3] which the demo stream
; ORs in one record at a time. Only the second matters here - the attract
; flies a replay - and it is the one the port already carries, as flt_trig2.
;
; The cycle itself walks 1..0x1E and takes the first object whose
; targetability byte is set, giving up and taking whatever it lands on when
; it comes back to where it started. An empty latch seeds from
; object_target_default, which is the last object that passed the test this
; frame.
;
; Difference: none. The select key is Tab or Return's latch ([0x1AFF] /
;   [0x1B0C], key_latch), and 0001924C's sign gate reads the damage array's
;   entry 2 ([00019E3A], mission_damage+2).
; DOS: flat 0001922C-000192A3, the target latch and its cycle.
; DOS symbol: inside loc_00019230
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: cycles the same range on the same byte, seeded the same way.
; Preserved: the 1..0x1E range and its wrap, the skip on a clear byte, the
;   give-up-at-the-start rule, the seed, the console-phase gate, and the
;   latches surviving a gated tick.
; Kind: translated.
; Status: ported; the key half is Unproven against a keyboard-driven DOS run.
object_target_cycle
        movem.l d0-d2/a0-a1,-(sp)
        lea     key_latch,a1
        move.b  KEY_TAB(a1),d0                  ; 00019230 [00001AFF]
        or.b    KEY_RETURN(a1),d0               ; 00019235 [00001B0C]
        bne     .gate                           ; 0001923B
        ; 0001923D-00019246: a pending count is consumed one per frame.
        tst.b   flt_trig2
        beq     .done
        subq.b  #1,flt_trig2
.gate
        tst.b   mission_damage+2                ; 0001924C [00019E3A]
        bmi     .done
        ; 00019255: not while the console is past phase 5.
        cmpi.b  #5,hud_console_variant
        bhi     .done
        clr.b   KEY_TAB(a1)                     ; 0001925E
        clr.b   KEY_RETURN(a1)                  ; 00019265

        moveq   #0,d0
        move.w  object_target_latch,d0
        bne     .cycle
        ; 00019275: an empty latch takes the frame's last targetable object.
        move.w  object_target_default,object_target_latch
        bra     .done
.cycle
        move.w  d0,d1                           ; where the walk started
.step
        addq.w  #1,d0                           ; 00019287
        cmpi.w  #$1e,d0                         ; 00019288
        bls     .have
        moveq   #1,d0                           ; 0001928D: wrap to 1, not 0
.have
        move.w  d0,d2
        subq.w  #1,d2
        mulu    #OBJ_SIZE,d2
        lea     object_table,a0
        adda.l  d2,a0
        tst.b   OBJ_TARGETABLE(a0)              ; 00019292
        bne     .take
        cmp.w   d1,d0                           ; 0001929B: back to the start
        bne     .step
.take
        move.w  d0,object_target_latch          ; 000192A3
.done
        movem.l (sp)+,d0-d2/a0-a1
        rts

object_draw_sprite
        movem.l d0-d7/a0-a2,-(sp)
        ; 00024E05/00024FED select [0002044C] or [00020654] before their
        ; shared 000253CD tail. A normal 0002514D call selects model A here;
        ; the pair wrappers leave the selected model in the transient slot.
        tst.w   object_draw_override
        bne     .model_selected
        clr.b   object_draw_aspect_bias
        move.l  OBJ_MODEL_A(a0),object_draw_model_bank
        move.l  OBJ_PALETTE_A(a0),object_draw_palette
.model_selected
        ; 00024BF1's test is `js` - a NEGATIVE depth is skipped and zero is
        ; drawn. This read `ble` on the whole-unit value, which also dropped
        ; everything inside one map unit; it existed to protect a divide that
        ; is no longer here.
        tst.l   OBJ_DEPTH(a0)
        bmi     .done

        ; The blit clips, so an off-surface result is handed over rather than
        ; tested for here - except behind the viewer, which is not a clip but a
        ; different sign of the same arithmetic and was rejected above.
        tst.w   sprite_bank_status
        bne     .done
        ; The frame comes from the aspect angle, not from OBJ_SPRITE. That
        ; byte is DOS byte field 1, which the state handlers increment and wrap
        ; against 20, 8 and 7 - an animation counter, not a heading. Nothing
        ; drives it yet.
        ; object_aspect also performs the exact DOS projection-page lookup and,
        ; with it, 00024D84's fan column - so the column below is read after
        ; this call rather than computed before it.
        ;
        ; object_draw_frame is 0002519D: the same 000253CD tail, but its own
        ; projection and a frame index taken from OBJ_SPRITE (000251AE). It
        ; sets object_draw_by_frame and enters here.
        tst.w   object_draw_by_frame
        beq     .by_aspect
        bsr     object_frame_project
        bra     .projected
.by_aspect
        moveq   #0,d1
        bsr     object_aspect
.projected
        tst.w   d0
        beq     .done
        move.w  d0,d6                           ; preserve the frame index

        ; Screen column - the ORIGINAL'S, and it is not a pinhole ratio.
        ; 00024D9F/00025274 store v in [0x22365] and 0002543A adds that byte
        ; to the blit's destination x, so the sprite stands at the fan column
        ; the projection already found. What was here instead formed
        ; `160 + 160 * lateral / depth` from a reasoned-out "the fan spans
        ; lateral/depth in -1..+1", and that is a different fan: B is exactly
        ; z/100 for every one of the 180 rings (measured over the captured
        ; DTL table), so the original's v is `128 + 800 * lateral / z_ring`
        ; and its half-fan is 200 surface pixels of lateral per unit depth,
        ; not 160. Objects were pulled toward the centre by a fifth, growing
        ; with the offset - and off the terrain feature they stand on, which
        ; the marcher places by that same B.
        ;
        ; v is a column on the DOS 256-wide surface whose 192 marched columns
        ; sit at 0x20..0xDF, and this port presents source column c at
        ; surface x (c - TERRAIN_VIEW_FIRST) * 2 - the same conversion
        ; sprite.s uses in reverse to index the terrain clip, and hud.s to
        ; index the shear.
        move.w  object_project_x,d4
        tst.w   object_target_view
        bne     .target_position
        subi.w  #32,d4                          ; surface column -> DOS source
        subi.w  #TERRAIN_VIEW_FIRST,d4
        add.w   d4,d4                           ; two Falcon pixels per column
        moveq   #0,d1
        move.b  object_project_page,d1
        move.w  #OBJECT_PAGE_ANCHOR,d5
        sub.w   d1,d5
        move.w  d5,d1                           ; sprite base row
        bra     .position_ready
.target_position
        ; 000079F0 copies source columns 0x58..0xA7 into the right MFD.
        ; The DOS blitter's v is a surface byte column. The target crop's
        ; deinterleave maps that byte column one-for-one into the Falcon
        ; panel's chunky x coordinate, while the terrain span writer emits
        ; the two source fields explicitly.
        subi.w  #MFD_VIEW_SURFACE_FIRST,d4
        addi.w  #MFD_SURFACE_X+MFD_PANEL_STEP,d4
        moveq   #0,d1
        move.b  object_project_page,d1
        move.w  #MFD_VIEW_TOP_ROW,d5
        sub.w   d1,d5
        ; Signed: a page row above the window's top maps to a NEGATIVE panel
        ; row and sprite_draw_scaled's target clip drops it. This clamped to 0
        ; and shifted logically, which parked an out-of-window missile (page
        ; 242 against a top of 162) on the panel's first row.
        asr.w   #1,d5
        addi.w  #MFD_Y,d5
        move.w  d5,d1
.position_ready
        move.w  d6,d0                           ; restore the frame index

        ; The size band, 00024D21-00024D3E: 2^27 divided by the RING's own
        ; lateral increment, clamped to 0x7F. Not 1600/depth, which is what
        ; stood here: B is z_ring/100 so the two agree to the ring's
        ; quantisation for a near object and disagree badly once the object
        ; sits well inside a coarse far ring - measured over a captured frame,
        ; one object came out at band 2 against the original's 10.
        ;
        ; 00024D3E stores 127 - index, and 000253D2 indexes the runtime ramp
        ; table with that. Read out of the running original at 0x1D7EC (the
        ; shipped image holds CODE there; both the table and the pool at
        ; 0x1DBEC are built at startup): ramp 127 - index is exactly
        ; index + 1 bytes long and its bytes sum to 64 at every one of the
        ; 128 entries. So the ramp resamples the sprite's 64 native source
        ; pixels onto index + 1 destination pixels, and the Falcon blitter's
        ; 8.8 scale for that is (index + 1) * 4.
        moveq   #0,d3
        move.w  object_b_ring,d3
        lsl.w   #2,d3
        lea     ring_b_table,a1
        move.l  0(a1,d3.w),d3                   ; B[b_ring], the DOS divisor
        beq     .done
        ; d7, not d5: d5 is still carrying the sprite's base row, which the
        ; blit call below reads.
        move.l  #$8000000,d7
        divu.l  d3,d7                           ; 00024D2E, unsigned
        cmpi.l  #127,d7
        bls     .scale_index_ok
        moveq   #127,d7
.scale_index_ok
        addq.l  #1,d7
        lsl.l   #2,d7
        move.l  d7,d3
        move.l  object_draw_model_bank,a1
        tst.l   a1
        beq     .done
        tst.l   object_draw_palette
        beq     .done
        ; Arm the terrain clip for this model. 00025223-0002522E points
        ; [00022358] at the object's own ring in the marcher's saved
        ; silhouette, and 000254CF/000254D5 read one entry per surface column
        ; out of it; 000254D9's `cmp bl,bh / jb` then drops every sprite pixel
        ; that sits below the terrain in front of it. Without this a model
        ; behind a ridge draws straight through it.
        tst.w   object_target_view
        bne     .target_occlusion
        move.w  object_project_ring,d0
        bsr     render_ring_occlusion
        move.l  a0,sprite_occl
        bra     .occlusion_ready
.target_occlusion
        moveq   #0,d0
        move.w  object_project_ring,d0
        cmp.w   ring_steps,d0
        bcc     .occlusion_ready
        mulu    #MFD_VIEW_COLS*2,d0
        lea     mfd_target_silhouette,a0
        adda.l  d0,a0
        move.l  a0,sprite_occl
.occlusion_ready

        move.l  work_screen,a0
        move.w  d6,d0                           ; the frame index
        move.w  d4,d1
        move.w  d5,d2
        move.l  sprite_palette,-(sp)
        move.l  object_draw_palette,sprite_palette
        bsr     sprite_draw_scaled
        move.l  (sp)+,sprite_palette
        clr.l   sprite_occl
.done
        movem.l (sp)+,d0-d7/a0-a2
        rts

; The two pair-draw handlers. Both begin with 00024C45's aspect and a test of
; the projected page row against 0x82 (00024E15/00024FF7); they differ in what
; they compose on each side of it, and the difference is in the azimuth term of
; model B, the turret, which the object's variant byte [00021F57] rotates.
;
;   00024FED (type 2 - the tanks)
;     row <= 0x82   A, then B at (variant      ) >> 3      000250AA-00025148
;     row >  0x82   B at (variant + 4) >> 3, then A        00025005-000250A5
;   00024E05 (types 1 and 6 - the free-flying units)
;     row <= 0x82   A, then B' at (-variant + 4) >> 3 and 8 source rows
;                   lower, then B at variant >> 3          00024F06-00024FE8
;     row >  0x82   B at (variant + 4) >> 3, then B' as
;                   above, then A                          00024E1D-00024F01
;
; B' is the turret's mirror image: 00024E7F/00024F7A store 0xF8 in [000253CC],
; which 00025426 adds to the model record's own Y offset and 0002550F clears at
; the end of the blit. Every term is a byte (`add al,4` wraps), and the sum with
; the aspect [0002237D] is masked to 0..31 by the aspect step.
; DOS: flat 00024E05-00024F01 and 00024FED-00025148, the two pair-draw handlers.
; DOS symbol: inside loc_00024E03
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: composes the authored model pair in the recovered order for each entry.
; Preserved: the 0x82 page-row test, the order on each side of it, every
;   azimuth term and the lowered mirrored turret.
; Difference: none. 00024E0F adds [0002237F] to the page row before the test,
;   and 00024C25 writes it - the pitch byte, in view variant 6 - so the helicopter
;   in the chase camera takes a different elevation frame (object_draw_fixed).
; Kind: translated.
; Status: ported. These used to share one body that applied 00024E05's mirrored
;   azimuth to 00024FED's turret and drew only two models for 00024E05, so a
;   tank's turret faced the wrong way in the cockpit view whatever its variant.
object_draw_pair_24fed
        movem.l d0-d7/a0-a2,-(sp)
        bsr     object_pair_project_row
        cmpi.w  #$82,d0                         ; 00024FF7
        bhi     .below
        bsr     object_draw_model_a             ; 000250AA-000250F6 (A first)
        move.b  OBJ_VARIANT(a0),d1
        lsr.b   #3,d1                           ; 0002511E
        bsr     object_draw_model_b
        bra     .done
.below
        move.b  OBJ_VARIANT(a0),d1              ; 00025026
        addq.b  #4,d1                           ; 0002502C
        lsr.b   #3,d1                           ; 0002502E
        bsr     object_draw_model_b
        bsr     object_draw_model_a             ; 0002505F
.done
        clr.w   object_draw_override
        movem.l (sp)+,d0-d7/a0-a2
        rts

object_draw_pair_24e05
        movem.l d0-d7/a0-a2,-(sp)
        bsr     object_pair_project_row
        cmpi.w  #$82,d0                         ; 00024E15
        bhi     .below
        bsr     object_draw_model_a             ; 00024F06-00024F4D
        bsr     .mirrored_turret                ; 00024F53-00024FB1
        move.b  OBJ_VARIANT(a0),d1              ; 00024FB8
        lsr.b   #3,d1
        bsr     object_draw_model_b
        bra     .done
.below
        move.b  OBJ_VARIANT(a0),d1              ; 00024E3E
        addq.b  #4,d1
        lsr.b   #3,d1
        bsr     object_draw_model_b
        bsr     .mirrored_turret                ; 00024E79-00024EB5
        bsr     object_draw_model_a             ; 00024EBB
.done
        clr.w   object_draw_override
        movem.l (sp)+,d0-d7/a0-a2
        rts
.mirrored_turret
        move.b  OBJ_VARIANT(a0),d1              ; 00024E79
        neg.b   d1                              ; 00024E86
        addq.b  #4,d1                           ; 00024E88
        lsr.b   #3,d1                           ; 00024E8A
        move.w  #$f8,d2                         ; 00024E7F [000253CC] = 0xF8
        bra     object_draw_model_b_lowered

; The A half of the pair: field 2's bank with no azimuth tweak.
; DOS: flat 00024EBB-00024F01 / 00024F06-00024F4D, model A composition.
; DOS symbol: inside loc_00024E03
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: binds the authored model A bank and palette and runs the shared tail.
; Preserved: bank/palette source and the zero azimuth bias.
; Kind: translated.
; Status: ported.
object_draw_model_a
        move.l  OBJ_MODEL_A(a0),object_draw_model_bank
        move.l  OBJ_PALETTE_A(a0),object_draw_palette
        clr.b   object_draw_aspect_bias
        move.w  #1,object_draw_override
        bsr     object_draw_sprite
        rts

; The B half: field 3's bank, with the caller's azimuth term (d1.b) added to the
; aspect before it is masked to 0..31, and - for the mirrored turret - the
; caller's extra Y offset in d2.w, which 00025426 adds to the record's own.
; In: a0 = object, d1.b = azimuth term, d2.w = extra Y offset (lowered entry).
; DOS: flat 00024E1D-00024E78 / 00024F53-00024FE8 / 00025005-0002505E, model B.
; DOS symbol: inside loc_00024E03
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: binds the authored model B bank and palette and draws it.
; Preserved: bank/palette source, the byte azimuth term, the Y offset.
; Kind: translated.
; Status: ported.
object_draw_model_b
        moveq   #0,d2
object_draw_model_b_lowered
        move.l  OBJ_MODEL_B(a0),object_draw_model_bank
        move.l  OBJ_PALETTE_B(a0),object_draw_palette
        move.b  d1,object_draw_aspect_bias
        move.w  d2,sprite_y_extra
        move.w  #1,object_draw_override
        bsr     object_draw_sprite
        clr.w   sprite_y_extra                  ; 0002550F [000253CC] = 0
        rts

; Return the same bottom-up projection page row 00024E0A reads out of
; [00022366] for the pair test.
; DOS: flat 00024E0A-00024E15, the pair draw's page-row source.
; DOS symbol: inside loc_00024E03
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: reuses object_find_page so the two cannot drift apart.
; Preserved: the page row and its bottom-up orientation.
; Difference: none; [0002237F], added at 00024E0F, is object_elev_bias.
; Kind: translated.
; Status: ported; covered by object-state arithmetic review.
object_pair_project_row
        bsr     object_find_page
        add.b   object_elev_bias,d0             ; 00024E0F add al,[0002237F]
        andi.w  #$00ff,d0
        rts

; The fixed slot-31 object: it rides the frame-start helicopter position and
; altitude and counts its variant byte down by 0x10 a tick. The distinction is
; observable during view_select's extra frame tail: player_x/player_y may be
; the substituted camera by the time this state runs, while DOS still copies
; the frame-start flight position into slot 31.
; DOS: flat 00023800-0002385A, the fixed-object state; draw gate at 00024C0A.
; DOS symbol: inside loc_000237CC
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: tracks the viewer and holds the recovered draw gate closed.
; Preserved: the 0x10 variant step, the viewer position copy, the altitude
; increment with its saturation, and the [00019D86] draw gate.
; Kind: translated.
; Status: ported; the gate stays closed until the console phase passes 5, and
; the traced attract route never installs this object.
object_state_fixed
        subi.b  #$10,OBJ_VARIANT(a0)
        move.l  flt_frame_x,d0
        move.l  d0,OBJ_X(a0)
        move.l  flt_frame_y,d0
        move.l  d0,OBJ_Y(a0)
        ; 0002381F reads [00019DF6], the altitude latched at frame start, not
        ; the live [00019DFC]. The update pass runs inside the frame driver's
        ; push/pop window, so with an external view selected the live byte is
        ; the CAMERA's altitude and this object would ride that instead of the
        ; helicopter.
        moveq   #0,d0
        move.b  flt_prevalt,d0
        addq.b  #1,d0
        bcc     .alt_ok
        moveq   #-1,d0
.alt_ok
        move.b  d0,OBJ_ALTITUDE(a0)
        ; 00023835: the heading byte is [00019D04] >> 24 - the top byte of the
        ; flight angle in the original's own convention, not this port's
        ; inverted player_heading.
        move.l  flt_angle,d0
        moveq   #24,d1
        lsr.l   d1,d0
        move.b  d0,OBJ_HEADING(a0)
        rts

; The fixed object's position in the original's 10.22, for 000256C8's bearing.
; The object table's layout lives in this file, so the conversion does too.
; Out: d6 = X, d7 = Y.
; DOS: flat 00020C6C/00020E74 + 0x1F*4, the fixed object's position words.
; DOS symbol: none - the cited addresses are data
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: returns the slot-31 position, which is the DOS 10.22 unconverted.
; Preserved: the slot index and the coordinate scale the original reads.
; Kind: adapted - platform accessor.
; Status: ported; exercised by view_handler_fixed.
object_fixed_position
        move.l  a0,-(sp)
        lea     object_table+30*OBJ_SIZE,a0
        move.l  OBJ_X(a0),d6
        move.l  OBJ_Y(a0),d7
        move.l  (sp)+,a0
        rts

; The fixed object's draw gate. 00024C0A tests the console phase byte
; [00019D86] against 5 and draws nothing at or below it.
; In: a0 = object.
; DOS: flat 00024C0A-00024C18, fixed-object draw gate.
; DOS symbol: inside loc_00024C06
; Record: analysis/functions/falcon-attract.md#object-pass
; Port: holds the recovered gate and defers to the pair draw when it opens.
; Preserved: the phase comparison and its unsigned sense.
; Kind: translated.
; Status: ported; the traced attract route never opens the gate.
object_draw_fixed
        cmpi.b  #5,view_variant                 ; 00024C0A
        bls     .done                           ; 00024C11 jbe
        cmpi.b  #6,view_variant                 ; 00024C13
        bne     object_draw_pair_24fed          ; 00024C1A jne 00024FED
        ; 00024C20-00024C3D: the chase camera. The pitch accumulator's low byte
        ; becomes the elevation bias [0002237F], [0002237E] says the blit does
        ; not shear this model by the roll, and the pair draw runs between them.
        move.b  flt_pitch+3,object_elev_bias    ; 00024C25 (eax = [00019CF4], al)
        move.b  #1,object_no_shear              ; 00024C2A
        bsr     object_draw_pair_24fed          ; 00024C31
        clr.b   object_no_shear                 ; 00024C36
        clr.b   object_elev_bias                ; 00024C3D
.done
        rts

; ---------------------------------------------------------------------------
; 0002519D: the frame-indexed draw handler.
; ---------------------------------------------------------------------------

; 0002519D is the sibling of 0002514D. Both end in 000253CD's scale and blit,
; but 0002519D does not look up an aspect: its frame is the object's own
; sprite byte [000219A3] (000251AE), and it runs a projection of its own.
; That projection is not 00024C45's, so it is transcribed rather than shared:
;
;   - the ring search halves [00019EE0] BEFORE the first compare and starts
;     from the table's midpoint when the key is past it (000251D5-000251DD);
;   - the found entry is stepped back two rings (000251F5 `sub ebx, 8`, with
;     a borrow rejecting the draw), and that one ring k supplies the divisor
;     [k*4 + 00019EE4], the clip archive (00025220) and the page row;
;   - the page index is ~[00019DFC] + altitude, rotated through the carry,
;     with no `and 0xFE` (0002523A-00025248);
;   - page rows 0 and 0xFF are rejected (00025251/00025255), and so is a
;     column v = lateral / (B[k] >> 3) + 0x80 outside 5..0xF4
;     (00025259-00025272);
;   - there is no targetability tail: an object drawn this way cannot be
;     locked.
;
; In: a0 = object. The frame goes through object_draw_sprite's shared tail.
; DOS: flat 0002519D-0002528B, frame-indexed projection and draw.
; DOS symbol: loc_0002519D
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: selects the frame-indexed projection and runs the 000253CD tail.
; Preserved: every reject, the ring search order, the two-ring step back, the
;   page index and the column bounds.
; Kind: translated.
; Status: ported; drawn by wreckage (BOOM) since the shared banks load.
object_draw_frame
        move.w  #1,object_draw_by_frame
        bsr     object_draw_sprite
        clr.w   object_draw_by_frame
        rts

; The projection half of 0002519D.
; In: a0 = object. Out: d0 = the frame index, or 0 for no draw; on a draw,
;   object_b_ring, object_project_ring, object_project_page and
;   object_project_x are set for the tail.
; DOS: flat 0002519D-00025274, projection of the frame-indexed draw.
; DOS symbol: loc_0002519D
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same tests on the port's 16.16 depth and lateral.
; Preserved: unsigned ring compares, the midpoint start, the two-ring step,
;   the carry-rotated page index and both column bounds.
; Kind: translated.
; Status: ported.
object_frame_project
        movem.l d1-d7/a1,-(sp)
        clr.b   object_page_valid
        clr.b   object_fan_valid
        cmpi.l  #OBJ_DEPTH_LIMIT,OBJ_DEPTH20(a0) ; 0002519D: > 0x1FFFFFFF
        bgt     .none
        move.l  OBJ_DEPTH20(a0),d6
        lsl.l   #3,d6                           ; 000251C0-000251C7: depth << 3
        lea     ring_z_table,a1                 ; 000251CA
        move.w  ring_steps,d7                   ; 000251CF [00019EE0]
        lsr.w   #1,d7                           ; 000251D5 shr ebp, 1
        beq     .none
        moveq   #0,d1
        move.w  d7,d1
        lsl.l   #2,d1
        cmp.l   -4(a1,d1.l),d6                  ; 000251D7
        bls     .scan
        adda.l  d1,a1                           ; 000251DD lea ebx,[ebx+ebp*4]
.scan
        cmp.l   (a1),d6                         ; 000251E0
        bls     .found
        addq.l  #4,a1
        subq.w  #1,d7
        bne     .scan
        bra     .none                           ; 000251EA
.found
        move.l  a1,d5
        subi.l  #ring_z_table,d5
        subq.l  #8,d5                           ; 000251F5 sub ebx, 8
        bcs     .none                           ; 000251F8 jb
        lsr.l   #2,d5                           ; ring k
        move.w  d5,object_b_ring                ; 00025205 [ebx + 00019EE4]
        move.w  d5,object_project_ring          ; 00025220-0002522E clip

        lea     ring_page_table,a1              ; 00025234 + [00019E5C]
        move.l  d5,d1
        lsl.l   #8,d1
        adda.l  d1,a1
        moveq   #0,d4
        move.b  player_altitude,d4              ; 0002523A
        not.b   d4                              ; 00025240
        move.b  OBJ_ALTITUDE(a0),d1
        add.b   d1,d4                           ; 00025242
        roxr.b  #1,d4                           ; 00025248 rcr bl, 1
        andi.w  #$00ff,d4
        moveq   #0,d1
        move.b  0(a1,d4.w),d1                   ; 0002524A
        move.b  d1,object_project_page
        cmpi.b  #1,d1                           ; 00025251 jb
        bcs     .none
        cmpi.b  #$fe,d1                         ; 00025255 ja
        bhi     .none
        move.b  #1,object_page_valid

        lea     ring_b_table,a1
        move.l  0(a1,d5.l*4),d2
        lsr.l   #3,d2                           ; 0002525C shr ebp, 3
        beq     .none                           ; 0002525F
        move.l  OBJ_LATERAL20(a0),d3            ; the DOS lateral, world<<20
        divs.l  d2,d3                           ; 00025261 idiv ebp
        addi.l  #$80,d3                         ; 00025263
        cmpi.l  #$f5,d3                         ; 00025268 jae
        bcc     .none
        cmpi.l  #5,d3                           ; 0002526F jb
        bcs     .none
        move.w  d3,object_project_x             ; 00025274 [00022365]
        move.b  #1,object_fan_valid
        moveq   #0,d0
        move.b  OBJ_SPRITE(a0),d0               ; 000251AE [00022364]
        bra     .done
.none
        moveq   #0,d0
.done
        movem.l (sp)+,d1-d7/a1
        rts

; ---------------------------------------------------------------------------
; The shared weapon and effect banks.
; ---------------------------------------------------------------------------

; 000066E2-000067AE loads six banks into [00019E74]-[00019E88], in this order,
; each through 00015E6E with its name inline and a jump to the resource-error
; exit at 00006400 if it fails, then a palette translation (0002B903 for the
; first four, 0002B8C5 for BULL and BOOM):
;
;   chaf.rle -> [00019E78]    stgr.rle -> [00019E84]    hell.rle -> [00019E80]
;   rock.rle -> [00019E7C]    bull.rle -> [00019E74]    boom.rle -> [00019E88]
;
; These sit in 353 bytes the static listing never decoded (000066D2-00006832);
; the order and targets above were read from the image bytes around each
; inline name.
; DOS: flat 000066E2-000067AE, the shared bank loads of mission setup.
; DOS symbol: inside loc_00006695
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: loads the same six files through sprite_bank_load and gives each its
;   own RGB565 palette, as sprite_mission_load does for the mission banks.
; Preserved: the six names, their order and their destinations.
; Difference: 0002B903/0002B8C5 translate each bank into the one VGA DAC. The
;   Falcon has no DAC to share, so each bank keeps its own palette (the same
;   adaptation as the mission slots). A failed load leaves that pointer 0
;   instead of taking 00006400's exit; the weapons that need it then do not
;   launch (Target artefact).
; Kind: translated/adapted - true-colour palette.
; Status: ported.
weapon_banks_load
        movem.l d0-d3/a0-a3,-(sp)
        moveq   #0,d3                           ; load step 0..5, DOS order
.bank
        lea     weapon_bank_order,a0
        moveq   #0,d2
        move.b  0(a0,d3.w),d2                   ; destination index 0..5
        lea     weapon_bank_ptrs,a3
        clr.l   0(a3,d2.w*4)
        lea     weapon_palette_ptrs,a3
        clr.l   0(a3,d2.w*4)
        move.l  d2,d0
        mulu.l  #OBJECT_BANK_BYTES,d0
        lea     weapon_bank_store,a1
        adda.l  d0,a1                           ; this bank's buffer
        move.l  d3,d0
        mulu    #WEAPON_BANK_NAME,d0
        lea     weapon_bank_names,a0
        adda.l  d0,a0                           ; this step's name
        move.l  a1,a2
        bsr     sprite_bank_load                ; 00015E6E
        tst.l   d0
        bne     .next                           ; DOS: jb 00006400
        move.l  d2,d0
        lsl.l   #8,d0
        add.l   d0,d0                           ; 512 bytes per palette
        lea     weapon_palette_store,a1
        adda.l  d0,a1
        move.l  a2,a0
        ; 000066FF/00006721/00006743/00006765 follow CHAF, STGR, HELL and ROCK
        ; with `call 0002B903` - the mission palette variant runs, so a night
        ; mission's cloud and shells are recoloured like its models - while
        ; 00006787 and 000067A9 (BULL, BOOM) call `0002B8C5`, which does not:
        ; the fireball keeps its orange.
        clr.w   sprite_palette_variant
        cmpi.w  #4,d3
        bcc     .no_night
        move.w  #1,sprite_palette_variant
.no_night
        bsr     sprite_palette_from_bank        ; 0002B903 / 0002B8C5
        clr.w   sprite_palette_variant
        lea     weapon_bank_ptrs,a3
        move.l  a2,0(a3,d2.w*4)                 ; [00019E74 + 4*index]
        lea     weapon_palette_ptrs,a3
        move.l  a1,0(a3,d2.w*4)
.next
        addq.w  #1,d3
        cmpi.w  #6,d3
        bcs     .bank
        movem.l (sp)+,d0-d3/a0-a3
        rts

; ---------------------------------------------------------------------------
; The trigger dispatch.
; ---------------------------------------------------------------------------

; 000191B6-0001922E, inside the flight handler, after the control inputs and
; before the terrain follow and movement core - so a weapon leaves from the
; position, heading and published sin/cos as they stood before this tick's
; move, with this tick's pitch.
;
;   000191B6  [00019D81] = 0            the sight element flag (hud_weapon)
;   000191BD  page [00019D88] == 0:     [00019DF2] = 0, then the live keys
;   000191EA  otherwise the live keys, then a pending replay count:
;   000191FC  [00019DF2] == 0 -> out; 00019205 dec it
;   0001920B  [00019D81] = 1, clear [00001B29]/[00001B3C], and
;   0001922E  call [00019D68 + 4*page]
;
; The handler table (image, below 0x32B20) is 00022890, 00022B00, 00022F90,
; 00022E70, 000231B2, 000230B0. Pages 1 and 2 - the rocket and the Hellfire -
; are the ones the supported first 284 records of DEMO1 reach (page 2 at
; record 11, page 1 from record 92 after the 0x1A key at 57).
;
; In: nothing. Out: nothing; all registers preserved.
; DOS: flat 000191B6-0001922E, replay weapon dispatch.
; DOS symbol: inside loc_000191B6
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: consumes one pending trigger and calls the page's launcher.
; Preserved: the page-0 key test, the one-per-tick decrement, the sight flag,
;   the latch clears, and the position in the tick.
; Differences:
;   - 000191DF `test [00019DEC], 1` is the game-port button word, 0 on the
;     keyboard device the shipped COMANCHE.MNU selects, so it never fires;
;     the joystick device stays out with the rest of 00018A06.
;   - 00004E8E's firing sound inside the launchers is sound, out of scope.
; Kind: translated.
; Status: ported, pages 0-5; page 0 and the key paths are Unproven against a
;   keyboard-driven DOS run (the attract holds every key released).
weapon_dispatch
        movem.l d0-d7/a0-a6,-(sp)
        clr.b   hud_weapon                      ; 000191B6
        lea     key_state,a1
        lea     key_latch,a2
        tst.b   instrument_page                 ; 000191BD
        bne     .paged
        clr.b   flt_trig1                       ; 000191C6
        tst.b   KEY_SPACE(a1)                   ; 000191CD [00001AA9] jns -> fire
        bpl     .fire
        tst.b   KEY_KP5(a1)                     ; 000191D6 [00001ABC]
        bpl     .fire
        bra     weapon_dispatch_done            ; 000191DF-000191E8: no button word
.paged
        tst.b   KEY_SPACE(a2)                   ; 000191EA [00001B29]
        bne     .fire
        tst.b   KEY_KP5(a2)                     ; 000191F3 [00001B3C]
        bne     .fire
        tst.b   flt_trig1                       ; 000191FC
        beq     weapon_dispatch_done
        subq.b  #1,flt_trig1                    ; 00019205
.fire
        move.b  #1,hud_weapon                   ; 0001920B
        clr.b   KEY_SPACE(a2)                   ; 00019212
        clr.b   KEY_KP5(a2)                     ; 00019219
        moveq   #0,d0
        move.b  instrument_page,d0              ; 00019220
        bne     .not_gun
        bsr     weapon_fire_gun                 ; 00022890
        bra     weapon_dispatch_done
.not_gun
        cmpi.b  #1,d0
        bne     .not_rocket
        bsr     weapon_fire_rocket              ; 00022B00
        bra     weapon_dispatch_done
.not_rocket
        cmpi.b  #2,d0
        bne     .not_hellfire
        bsr     weapon_fire_hellfire            ; 00022F90
        bra     weapon_dispatch_done
.not_hellfire
        cmpi.b  #3,d0
        bne     .not_stinger
        bsr     weapon_fire_stinger             ; 00022E70
        bra     weapon_dispatch_done
.not_stinger
        cmpi.b  #4,d0
        bne     .not_bomb
        bsr     weapon_fire_bomb                ; 000231B2
        bra     weapon_dispatch_done
.not_bomb
        cmpi.b  #5,d0
        bne     weapon_dispatch_done
        bsr     weapon_fire_wingman             ; 000230B0
; A named exit, so a capture can stop once a launch has completed.
weapon_dispatch_done
        movem.l (sp)+,d0-d7/a0-a6
        rts

; The launchers' slot scan: 00022B12-00022B26 / 00022F99-00022FAD. ebx
; starts at 0x82 and ecx counts 0x64, so 130 down to 31. DOS index 130 is
; one past each 130-entry array and aliases element 0 of the next one, but
; consistently for every field, and nothing else touches index 0 - so it
; behaves as an ordinary slot, which is what this port's slot 130 is.
; Out: a0 = the slot, or 0 when all hundred are busy.
; DOS: flat 00022B12-00022B26, launcher slot scan (also 00022F99-00022FAD).
; DOS symbol: inside sub_00022B00
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same hundred slots in the same order.
; Preserved: descending order, bound and free test.
; Kind: translated.
; Status: ported.
weapon_slot_scan
        move.l  d0,-(sp)
        lea     object_table+(OBJ_COUNT-1)*OBJ_SIZE,a0
        moveq   #OBJ_SCAN_UPPER_LIMIT-1,d0
.next
        tst.b   OBJ_ACTIVE(a0)
        beq     .found
        lea     -OBJ_SIZE(a0),a0
        dbra    d0,.next
        suba.l  a0,a0
.found
        move.l  (sp)+,d0
        rts

; The launch position both launchers share, in the original's 10.22 and then
; converted to this port's 16.16:
;
;   rail = -[00022880]                    (stored back: the rails alternate)
;   x = [00019CD4] + high(rail * [00019CBC]) - high(ahead * [00019CB8])
;   y = [00019CD8] + high(rail * [00019CB8]) + high(ahead * [00019CBC])
;
; [00019CB8]/[00019CBC] are the flight heading's sin/cos the movement core
; published last tick (flt_pub_sin/flt_pub_cos). `ahead` is 0x1000000 for the
; rocket and 0x3000000 for the Hellfire.
; In: a0 = slot, d0 = ahead. Out: OBJ_X/OBJ_Y written.
; DOS: flat 00022BAE-00022C0E (rocket), 0002302D-0002308D (Hellfire).
; DOS symbol: inside sub_00022B00
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same four high-dword products on the exact 10.22 flight state.
; Preserved: the rail negation and its order, the product order, the signs.
; Difference: none in the stored position; the result is the original's
;   10.22 and is stored whole.
; Kind: translated.
; Status: ported; checked against the traced launch rows.
weapon_launch_position
        movem.l d0-d5,-(sp)
        move.l  d0,d5                           ; ahead
        move.l  flt_x,d3                        ; 00022BAE / 0002302D
        move.l  flt_y,d4                        ; 00022BBA / 00023039
        move.l  weapon_rail,d0
        neg.l   d0                              ; 00022BCB neg eax
        move.l  d0,weapon_rail                  ; 00022BCD
        move.l  flt_pub_cos,d2
        MulS64  d2                              ; 00022BD2 imul [00019CBC]
        add.l   d1,d3
        move.l  weapon_rail,d0
        move.l  flt_pub_sin,d2
        MulS64  d2                              ; 00022BE4 imul [00019CB8]
        add.l   d1,d4
        move.l  d5,d0
        move.l  flt_pub_sin,d2
        MulS64  d2                              ; 00022BF6 imul [00019CB8]
        sub.l   d1,d3
        move.l  d5,d0
        move.l  flt_pub_cos,d2
        MulS64  d2                              ; 00022C08 imul [00019CBC]
        add.l   d1,d4
        move.l  d3,OBJ_X(a0)
        move.l  d4,OBJ_Y(a0)
        movem.l (sp)+,d0-d5
        rts

; 00022B00: the rocket.
;
;   00022B00  rockets [00019D30] == 0, or [00019E3B] negative -> empty
;   00022B29  empty: [00019D30] = 0, console redraw, out
;   00022B42  a slot: rockets - 1; redraw if page 1; sound 00004E8E
;   00022B72  aux 0, active 1, state 000241C0, draw 0002514D, bank ROCK,
;             speed 0x4000000, the position above with ahead 0x1000000
;   00022C15  heading = ([00019D04] + 0x800000) >> 24 - rounded, unlike
;             the Hellfire's
;   00022C28  altitude = [00019DFC]; 8.24 altitude = altitude << 24
;   00022C3D  vertical rate = -[00019CF4] << 22 (the pitch)
;   00022C4E  with a lock: n = ((|lat| >> 1) + depth) << 2 / speed, and if
;             n != 0 the rate becomes ((alt_t - alt) << 23) / n + 0x1800000
;
; [00019E3B] is entry 3 of the damage array at [00019E38]: 2 at runtime in
; the traced attract (the image holds 10; the mission parser overwrites it).
; |lat| is the one's-complement magnitude (cdq/xor), and both it and the
; depth are the target's last transform in the original's world<<20.
; In: nothing. Out: nothing.
; DOS: flat 00022B00-00022CA0, the rocket launcher.
; DOS symbol: sub_00022B00
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same tests, fields and arithmetic.
; Preserved: the empty-pod clear and redraw, the page-gated redraw, the
;   rounded heading, the 8.24 altitude, the pitch rate and the lead.
; Difference: none; the launch sound at 00022B5E-00022B6C is made, see src/sound.s.
; Kind: translated.
; Status: ported; checked against the traced launch rows.
weapon_fire_rocket
        tst.l   weapon_ammo+4                   ; 00022B00 [00019D30]
        beq     .empty
        tst.b   mission_damage+3                ; 00022B09 [00019E3B]
        bmi     .empty
        tst.l   weapon_bank_rock
        beq     .out
        bsr     weapon_slot_scan                ; 00022B12
        move.l  a0,d0
        beq     .out                            ; 00022B28 ret
        subq.l  #1,weapon_ammo+4                ; 00022B42
        cmpi.b  #1,instrument_page              ; 00022B49
        bne     .no_redraw
        move.b  #1,console_redraw               ; 00022B52 + 000073D0
.no_redraw
        SndFX   4,$FF,0,$20000                  ; 00022B5E-00022B6C: SND1 id 4 at double pitch
        clr.b   OBJ_AUX(a0)                     ; 00022B72 [00021DB3]
        move.b  #1,OBJ_ACTIVE(a0)               ; 00022B79 [00021921]
        move.l  #object_state_rocket,OBJ_STATE(a0)      ; 00022B80
        move.l  #object_draw_sprite,OBJ_DRAW(a0)        ; 00022B8B 0002514D
        move.l  weapon_bank_rock,OBJ_MODEL_A(a0)        ; 00022B96 [00019E7C]
        move.l  weapon_palette_rock,OBJ_PALETTE_A(a0)
        move.l  #$4000000,OBJ_SPEED(a0)         ; 00022BA2 [0001FE34]
        move.l  #$1000000,d0
        bsr     weapon_launch_position
        move.l  flt_angle,d0                    ; 00022C15
        addi.l  #$800000,d0                     ; 00022C1A
        moveq   #24,d1
        lsr.l   d1,d0                           ; 00022C1F
        move.b  d0,OBJ_HEADING(a0)              ; 00022C22 [0002189F]
        moveq   #0,d0
        move.b  player_altitude,d0              ; 00022C28 [00019DFC]
        move.b  d0,OBJ_ALTITUDE(a0)             ; 00022C2D
        moveq   #24,d1
        lsl.l   d1,d0                           ; 00022C33
        move.l  d0,OBJ_ALT_ACC(a0)              ; 00022C36 [00021694]
        move.l  flt_pitch,d0                    ; 00022C3D [00019CF4]
        neg.l   d0
        moveq   #22,d1
        lsl.l   d1,d0                           ; 00022C44
        move.l  d0,OBJ_VRATE(a0)                ; 00022C47 [0002148C]

        move.w  object_target_latch,d0          ; 00022C4E [00019D10]
        beq     .out
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a1
        adda.l  d0,a1
        move.l  OBJ_LATERAL20(a1),d0            ; [ebx*4 + 0002085C], world<<20
        bpl     .lat_abs
        not.l   d0                              ; 00022C60 cdq / xor
.lat_abs
        lsr.l   #1,d0                           ; 00022C63
        move.l  OBJ_DEPTH20(a1),d1
        add.l   d1,d0                           ; 00022C65 [ebx*4 + 00020A64]
        lsl.l   #2,d0                           ; 00022C6C
        divu.l  OBJ_SPEED(a0),d0                ; 00022C71
        beq     .out                            ; 00022C7A
        moveq   #0,d1
        move.b  OBJ_ALTITUDE(a1),d1             ; 00022C7E
        moveq   #0,d2
        move.b  player_altitude,d2              ; 00022C85
        sub.l   d2,d1                           ; 00022C8C
        moveq   #23,d2
        lsl.l   d2,d1                           ; 00022C8E
        divs.l  d0,d1                           ; 00022C92 idiv ebp
        addi.l  #$1800000,d1                    ; 00022C94
        move.l  d1,OBJ_VRATE(a0)                ; 00022C99
        bra     .out
.empty
        clr.l   weapon_ammo+4                   ; 00022B29
        move.b  #1,console_redraw               ; 00022B33 + 000073D0
.out
        rts

; 00022F90: the Hellfire.
;
;   00022F90  Hellfires [00019D34] == 0 -> out (no redraw, unlike the rocket)
;   00022FB0  a slot: Hellfires - 1; redraw if page 2; sound 00004E8E
;   00022FDF  aux 0, timer [00021E35] 0, target [00021D31] = the latch,
;             active 1, state 00024680, draw 0002514D, bank HELL,
;             speed 0x4000000, the position above with ahead 0x3000000
;   00023094  heading = [00019D04] >> 24, not rounded
;   000230A2  altitude = [00019DFC]
; In: nothing. Out: nothing.
; DOS: flat 00022F90-000230AD, the Hellfire launcher.
; DOS symbol: loc_00022F90
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same test, fields and arithmetic.
; Preserved: the silent empty case, the page-gated redraw, the fields and the
;   unrounded heading.
; Difference: none; the launch sound at 00022FCE-00022FD9 is made, see src/sound.s.
; Kind: translated.
; Status: ported; checked against the traced launch rows.
weapon_fire_hellfire
        tst.l   weapon_ammo+8                   ; 00022F90 [00019D34]
        beq     .out
        tst.l   weapon_bank_hell
        beq     .out
        bsr     weapon_slot_scan                ; 00022F99
        move.l  a0,d0
        beq     .out                            ; 00022FAF ret
        subq.l  #1,weapon_ammo+8                ; 00022FB2
        cmpi.b  #2,instrument_page              ; 00022FB9
        bne     .no_redraw
        move.b  #1,console_redraw               ; 00022FC2 + 000073D0
.no_redraw
        SndFX   4,$FF,0,0                       ; 00022FCE-00022FD9: SND1 id 4
        clr.b   OBJ_AUX(a0)                     ; 00022FDF [00021DB3]
        clr.b   OBJ_TIMER(a0)                   ; 00022FE6 [00021E35]
        move.w  object_target_latch,d0
        move.b  d0,OBJ_TARGET(a0)               ; 00022FED -> [00021D31]
        move.b  #1,OBJ_ACTIVE(a0)               ; 00022FF8
        move.l  #object_state_hellfire,OBJ_STATE(a0)    ; 00022FFF
        move.l  #object_draw_sprite,OBJ_DRAW(a0)        ; 0002300A 0002514D
        move.l  weapon_bank_hell,OBJ_MODEL_A(a0)        ; 00023015 [00019E80]
        move.l  weapon_palette_hell,OBJ_PALETTE_A(a0)
        move.l  #$4000000,OBJ_SPEED(a0)         ; 00023021
        move.l  #$3000000,d0
        bsr     weapon_launch_position
        move.l  flt_angle,d0                    ; 00023094
        moveq   #24,d1
        lsr.l   d1,d0                           ; 00023099
        move.b  d0,OBJ_HEADING(a0)              ; 0002309C
        move.b  player_altitude,OBJ_ALTITUDE(a0)        ; 000230A2
.out
        rts

; 00022890: the cannon.
;
;   00022890  rounds [00019D2C] == 0, or the gun's damage byte [00019E3D]
;             negative -> 000228B9: rounds = 0, redraw, out
;   000228A2  a slot (the shared scan); none -> out
;   000228D2  rounds - 2, floored at 0; redraw; firing sound 00004E8E
;   00022903  aux 0, active 1, state 000244E0, draw 0002519D, bank BULL,
;             sprite frame 1, speed 0x8000000, the flight position
;   0002295E  altitude = [00019DFC]; 8.24 altitude = altitude << 24
;   00022973  vertical rate = -[00019CF4] << 22 (the pitch)
;   00022989  heading = [00019D04] >> 24
;   00022992  with a lock: the heading becomes the target's bearing
;             [ebx + 00021CAF], and n = ((|lat| >> 1) + depth) << 2 / speed;
;             if n != 0 the rate becomes ((alt_t - alt) << 23) / n + 0xC00000
; In: nothing. Out: nothing.
; DOS: flat 00022890-000229F0, the cannon launcher.
; DOS symbol: sub_00022890
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same tests, fields and arithmetic as the rocket launcher beside
;   it, with this routine's own speed, rounds, bearing and lead constant.
; Preserved: the empty and damaged exits, the two-round step with its floor,
;   the lock's heading override, and the 0xC00000 lead offset.
; Difference: none; the firing sound at 000228F2-000228FD (SND1 id 7, bl $FE) is
;   made, see src/sound.s.
; Kind: translated.
; Status: ported; Unproven against a keyboard-driven DOS run.
weapon_fire_gun
        tst.l   weapon_ammo                     ; 00022890 [00019D2C]
        beq     .empty
        tst.b   mission_damage+5                ; 00022899 [00019E3D]
        bmi     .empty
        bsr     weapon_slot_scan                ; 000228A2-000228B8
        move.l  a0,d0
        beq     .out
        moveq   #2,d0
        sub.l   d0,weapon_ammo                  ; 000228D2 sub [00019D2C], 2
        bcc     .counted                        ; 000228D9 jae
        clr.l   weapon_ammo                     ; 000228DB
.counted
        move.b  #1,console_redraw               ; 000228E6 + 000073D0
        SndFX   7,$FE,0,0                       ; 000228F2-000228FD: the cannon burst, re-triggering its slot
        clr.b   OBJ_AUX(a0)                     ; 00022903 [00021DB3]
        move.b  #1,OBJ_ACTIVE(a0)               ; 0002290A [00021921]
        move.l  #object_state_bullet,OBJ_STATE(a0)      ; 00022911
        move.l  #object_draw_frame,OBJ_DRAW(a0) ; 0002291C
        move.l  weapon_bank_bull,OBJ_MODEL_A(a0)        ; 00022927 [00019E74]
        move.l  weapon_palette_bull,OBJ_PALETTE_A(a0)
        move.b  #1,OBJ_SPRITE(a0)               ; 00022933 [000219A3]
        move.l  #$8000000,OBJ_SPEED(a0)         ; 0002293A [0001FE34]
        move.l  flt_x,OBJ_X(a0)                 ; 00022946 [00019CD4]
        move.l  flt_y,OBJ_Y(a0)                 ; 00022952 [00019CD8]
        moveq   #0,d0
        move.b  player_altitude,d0              ; 0002295E [00019DFC]
        move.b  d0,OBJ_ALTITUDE(a0)             ; 00022963
        moveq   #24,d1
        lsl.l   d1,d0                           ; 00022969
        move.l  d0,OBJ_ALT_ACC(a0)              ; 0002296C [00021694]
        move.l  flt_pitch,d0                    ; 00022973 [00019CF4]
        neg.l   d0
        moveq   #22,d1
        lsl.l   d1,d0                           ; 0002297A
        move.l  d0,OBJ_VRATE(a0)                ; 0002297D [0002148C]
        move.l  flt_angle,d0                    ; 00022984 [00019D04]
        moveq   #24,d1
        lsr.l   d1,d0                           ; 00022989
        move.b  d0,OBJ_HEADING(a0)              ; 0002298C [0002189F]

        move.w  object_target_latch,d0          ; 00022992 [00019D10]
        beq     .out
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a1
        adda.l  d0,a1                           ; the target, [ebx*4 + ...]
        move.b  OBJ_VIEW_BEARING(a1),OBJ_HEADING(a0)    ; 0002299D-000229A3
        move.l  OBJ_LATERAL20(a1),d0            ; 000229A9, world<<20
        bpl     .lat_abs
        not.l   d0                              ; 000229B0 cdq / xor
.lat_abs
        lsr.l   #1,d0                           ; 000229B3
        move.l  OBJ_DEPTH20(a1),d1
        add.l   d1,d0                           ; 000229B5
        lsl.l   #2,d0                           ; 000229BC
        divu.l  OBJ_SPEED(a0),d0                ; 000229C1
        beq     .out                            ; 000229CA
        moveq   #0,d1
        move.b  OBJ_ALTITUDE(a1),d1             ; 000229CE
        moveq   #0,d2
        move.b  player_altitude,d2              ; 000229D5
        sub.l   d2,d1                           ; 000229DC
        moveq   #23,d2
        lsl.l   d2,d1                           ; 000229DE
        divs.l  d0,d1                           ; 000229E2 idiv ebp
        addi.l  #$c00000,d1                     ; 000229E4
        move.l  d1,OBJ_VRATE(a0)                ; 000229E9
.out
        rts
.empty
        clr.l   weapon_ammo                     ; 000228B9
        move.b  #1,console_redraw               ; 000228C3-000228CA
        rts

; 000244E0: the cannon round in flight.
;
;   000244E0  sprite frame > 1 -> 00024659: it is a burst; count it up and free
;             the slot after frame 7
;   000244ED  latch X, Y and altitude into the previous-tick copies
;   00024515  move along the heading (the 000248E4 mover's arithmetic)
;   00024546  vertical rate -= 0x100000
;   00024551  rate >= 0: 8.24 altitude += rate; a carry frees the slot
;             rate <  0: 8.24 altitude += rate; no carry means it fell through
;             zero - burst at the previous position
;   00024578  altitude byte = the 8.24 value's top byte; the map byte under it
;             doubled plus one at or above the altitude -> frame 3, burst
;   000245BA  the first of slots 30..1 that is active and within 0x14 half
;             altitude steps and 0x1C00000 on both axes loses one health (the
;             byte's borrow sets bit 0 of its phase byte); burst
;   00024621  the burst: frame + 1, and X, Y and altitude back to the latched
;             values
; In: a0 = object. Out: nothing.
; DOS: flat 000244E0-00024677, the cannon round's state.
; DOS symbol: sub_000244E0
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same order, 8.24 altitude and carry tests; the rocket's mover and
;   ground test, this routine's own proximity box and damage.
; Preserved: the frame-count exit, both carry exits, the 8-bit wrap of the
;   terrain compare, and the burst's restore of the latched position.
; Kind: translated.
; Status: ported; Unproven against a keyboard-driven DOS run.
object_state_bullet
        movem.l d0-d5/a1,-(sp)
        cmpi.b  #1,OBJ_SPRITE(a0)               ; 000244E0
        bhi     .burst                          ; 000244E7 ja 00024659
        move.l  OBJ_X(a0),OBJ_PREV_X(a0)        ; 000244ED
        move.l  OBJ_Y(a0),OBJ_PREV_Y(a0)        ; 000244FB
        move.b  OBJ_ALTITUDE(a0),OBJ_PREV_ALT(a0)       ; 00024509
        bsr     object_move                     ; 00024515-0002453F
        subi.l  #$100000,OBJ_VRATE(a0)          ; 00024546
        move.l  OBJ_VRATE(a0),d0                ; 00024551
        bmi     .falling
        add.l   d0,OBJ_ALT_ACC(a0)              ; 0002455C
        bcs     .retire                         ; 00024563 jb 00024668
        bra     .altitude
.falling
        add.l   d0,OBJ_ALT_ACC(a0)              ; 0002456B
        bcc     .restore                        ; 00024572 jae 00024621
.altitude
        move.b  OBJ_ALT_ACC(a0),OBJ_ALTITUDE(a0)        ; 00024578 top byte
        bsr     weapon_ground_hit               ; 00024585-000245A9
        bhi     .scan                           ; 000245AF jbe 00024650
        move.b  #3,OBJ_SPRITE(a0)               ; 00024650
        bra     .restore
.scan
        moveq   #OBJ_ALLOC_LIMIT,d5             ; 000245B5
        lea     object_table+(OBJ_ALLOC_LIMIT-1)*OBJ_SIZE,a1
.next
        tst.b   OBJ_ACTIVE(a1)                  ; 000245BA
        beq     .skip
        moveq   #0,d0
        move.b  OBJ_ALTITUDE(a0),d0             ; 000245C7
        moveq   #0,d1
        move.b  OBJ_ALTITUDE(a1),d1
        sub.w   d1,d0                           ; 000245CD, borrow in bit 8
        asr.w   #1,d0                           ; 000245D3 rcr al, 1
        bpl     .alt_abs
        not.w   d0                              ; 000245D5 cbw / xor al, ah
.alt_abs
        cmpi.w  #$14,d0                         ; 000245D9 ja
        bhi     .skip
        move.l  OBJ_X(a0),d0
        sub.l   OBJ_X(a1),d0                    ; 000245E1
        bpl     .x_abs
        not.l   d0                              ; 000245EF cdq / xor
.x_abs
        cmpi.l  #$1c00000,d0                    ; 000245F2 ja
        bhi     .skip
        move.l  OBJ_Y(a0),d0
        sub.l   OBJ_Y(a1),d0                    ; 000245F9
        bpl     .y_abs
        not.l   d0
.y_abs
        cmpi.l  #$1c00000,d0                    ; 0002460A ja
        bhi     .skip
        subq.b  #1,OBJ_HEALTH(a1)               ; 00024611
        bcc     .restore                        ; 00024618 jae 00024621
        ori.b   #1,OBJ_PHASE(a1)                ; 0002461A
.restore
        addq.b  #1,OBJ_SPRITE(a0)               ; 00024621
        move.l  OBJ_PREV_X(a0),OBJ_X(a0)        ; 00024627
        move.l  OBJ_PREV_Y(a0),OBJ_Y(a0)        ; 00024635
        move.b  OBJ_PREV_ALT(a0),OBJ_ALTITUDE(a0)       ; 00024643
        bra     .done
.skip
        lea     -OBJ_SIZE(a1),a1
        subq.w  #1,d5                           ; 00024670 dec ebx / jne
        bne     .next
        bra     .done                           ; 00024677 ret
.burst
        addq.b  #1,OBJ_SPRITE(a0)               ; 00024659
        cmpi.b  #7,OBJ_SPRITE(a0)               ; 0002465F
        bls     .done                           ; 00024666 jbe
.retire
        clr.b   OBJ_ACTIVE(a0)                  ; 00024668
.done
        movem.l (sp)+,d0-d5/a1
        rts

; 00022E70: the Stinger, page 3. It is the Hellfire (00022F90) with its own
; count [00019D38], the guided state 00024860, the STGR bank [00019E84], no
; empty-case reset and a console redraw only on its own page (00022E99).
; DOS: flat 00022E70-00022F8D, the Stinger launcher.
; DOS symbol: loc_00022E70
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same test, fields and arithmetic.
; Preserved: the silent empty case, the launch point and the latch copy.
; Difference: none; the launch sound at 00022EAE-00022EB9 is made, see src/sound.s.
; Kind: translated.
; Status: ported.
weapon_fire_stinger
        tst.l   weapon_ammo+12                  ; 00022E70 [00019D38]
        beq     .out
        tst.l   weapon_bank_stgr
        beq     .out
        bsr     weapon_slot_scan                ; 00022E79
        move.l  a0,d0
        beq     .out                            ; 00022E8F
        subq.l  #1,weapon_ammo+12               ; 00022E92
        cmpi.b  #3,instrument_page              ; 00022E99
        bne     .no_redraw
        move.b  #1,console_redraw               ; 00022EA2 + 000073D0
.no_redraw
        SndFX   4,$FF,0,0                       ; 00022EAE-00022EB9: SND1 id 4
        clr.b   OBJ_TIMER(a0)                   ; 00022EBF
        clr.b   OBJ_AUX(a0)                     ; 00022EC6
        move.w  object_target_latch,d0
        move.b  d0,OBJ_TARGET(a0)               ; 00022ECD
        move.b  #1,OBJ_ACTIVE(a0)               ; 00022ED8
        move.l  #object_state_guided,OBJ_STATE(a0)      ; 00022EDF
        move.l  #object_draw_sprite,OBJ_DRAW(a0)        ; 00022EEA
        move.l  weapon_bank_stgr,OBJ_MODEL_A(a0)        ; 00022EF5 [00019E84]
        move.l  weapon_palette_stgr,OBJ_PALETTE_A(a0)
        move.l  #$4000000,OBJ_SPEED(a0)         ; 00022F01
        move.l  #$3000000,d0
        bsr     weapon_launch_position
        move.l  flt_angle,d0                    ; 00022F74
        moveq   #24,d1
        lsr.l   d1,d0
        move.b  d0,OBJ_HEADING(a0)              ; 00022F7C
        move.b  player_altitude,OBJ_ALTITUDE(a0)        ; 00022F82
.out
        rts

; 000231B2: the bomb, page 4. It needs ammunition [00019D3C] and a latched
; target [00019D10]; it takes a free slot, one round, and becomes a timed blast
; (state 00024310, draw 00019C88) standing on the target's X and Y at the
; ground there + 0x0B.
; DOS: flat 000231B2-0002328F, the bomb launcher.
; DOS symbol: loc_000231B2
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same tests, fields and arithmetic.
; Preserved: both silent exits, timer and aux zero, the target's position and
;   the byte ground height.
; Difference: none; the voice at 000231FB-000231FD (SPEAK0 id 1) is made, see src/sound.s.
; Kind: translated.
; Status: ported.
weapon_fire_bomb
        tst.l   weapon_ammo+16                  ; 000231B2 [00019D3C]
        beq     .out
        tst.w   object_target_latch             ; 000231BB cmp [00019D10],0
        beq     .out
        bsr     weapon_slot_scan                ; 000231C4
        move.l  a0,d0
        beq     .out                            ; 000231DA
        subq.l  #1,weapon_ammo+16               ; 000231F4
        SndSpeechB 1                            ; 000231FB-000231FD: SPEAK0 id 1
        move.b  #1,console_redraw               ; 00023202 [00019D89] + 000073D0
        clr.b   OBJ_TIMER(a0)                   ; 0002320F
        clr.b   OBJ_AUX(a0)                     ; 00023216
        move.b  #1,OBJ_ACTIVE(a0)               ; 0002321D
        move.l  #object_state_bomb,OBJ_STATE(a0)        ; 00023224
        move.l  #object_draw_none,OBJ_DRAW(a0)  ; 0002322F
        move.l  weapon_bank_hell,OBJ_MODEL_A(a0)        ; 0002323A
        move.l  weapon_palette_hell,OBJ_PALETTE_A(a0)
        moveq   #0,d0
        move.w  object_target_latch,d0          ; 00023246
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a1
        adda.l  d0,a1
        move.l  OBJ_X(a1),OBJ_X(a0)             ; 0002324C
        move.l  OBJ_Y(a1),OBJ_Y(a0)             ; 0002325A
        bsr     object_ground_target_b          ; 00023268-0002328E
        move.b  d0,OBJ_ALTITUDE(a0)             ; 00023290
.out
        rts

; 000230B0: the wingman's Hellfire, page 5. It needs ammunition [00019D40] and
; a live ally [00022368]; without them the count is cleared (000230D0). The
; missile is a player Hellfire (state 00024680, target the latch) launched from
; the ally's position, heading and altitude.
; DOS: flat 000230B0-000231B1, the wingman launcher.
; DOS symbol: loc_000230B0
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same tests, fields and arithmetic.
; Difference: none; the launch sound at 00023118-00023123 is made, see src/sound.s.
; Kind: translated.
; Status: ported.
weapon_fire_wingman
        tst.l   weapon_ammo+20                  ; 000230B0 [00019D40]
        beq     .empty
        tst.l   weapon_bank_hell
        beq     .out
        bsr     weapon_slot_scan                ; 000230B9
        move.l  a0,d0
        beq     .out                            ; 000230CF
        move.l  a0,a1
        move.l  object_ally,d0                  ; 000230EF
        beq     .empty_scan                     ; 000230F7
        move.l  d0,a2
        tst.b   OBJ_ACTIVE(a2)                  ; 000230F9
        beq     .empty_scan                     ; 00023100
        subq.l  #1,weapon_ammo+20               ; 000230E9
        cmpi.b  #5,instrument_page              ; 0002310A
        bne     .no_redraw
        move.b  #1,console_redraw
.no_redraw
        SndFX   4,$FF,1,0                       ; 00023118-00023123: SND1 id 4 at half volume (dl = 1)
        clr.b   OBJ_TIMER(a1)                   ; 00023129
        clr.b   OBJ_AUX(a1)                     ; 00023130
        move.w  object_target_latch,d0
        move.b  d0,OBJ_TARGET(a1)               ; 00023137
        move.b  #1,OBJ_ACTIVE(a1)               ; 00023142
        move.l  #object_state_hellfire,OBJ_STATE(a1)    ; 00023149
        move.l  #object_draw_sprite,OBJ_DRAW(a1)        ; 00023154
        move.l  weapon_bank_hell,OBJ_MODEL_A(a1)        ; 0002315F
        move.l  weapon_palette_hell,OBJ_PALETTE_A(a1)
        move.l  #$4000000,OBJ_SPEED(a1)         ; 00023171
        move.l  OBJ_X(a2),OBJ_X(a1)             ; 0002317D
        move.l  OBJ_Y(a2),OBJ_Y(a1)             ; 0002318B
        move.b  OBJ_HEADING(a2),OBJ_HEADING(a1) ; 00023199
        move.b  OBJ_ALTITUDE(a2),OBJ_ALTITUDE(a1)       ; 000231A5
.out
        rts
.empty_scan
        subq.l  #1,weapon_ammo+20               ; 000230E9 happens before the ally test
.empty
        clr.l   weapon_ammo+20                  ; 000230D0
        move.b  #1,console_redraw               ; 000230DA + 000073D0
        rts

; ---------------------------------------------------------------------------
; The two missile states.
; ---------------------------------------------------------------------------

; The proximity test both missiles end in: 0002428D-000242DA and
; 000247EB-00024838, identical but for what a hit does. Slots 30 down to 1:
;
;   altitude: (self - other) as a nine-bit difference, halved through the
;             borrow (`rcr al,1`), one's-complement magnitude (cbw/xor) <= 15
;   X and Y:  one's-complement magnitude of the 10.22 difference <= 0x1400000
;
; In: a0 = the missile. Out: a1 = the first slot hit, or 0; d5 = its index.
; DOS: flat 0002428D-000242DA, missile proximity test (also 000247EB-00024838).
; DOS symbol: inside loc_000241C0
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same three tests in the same order over the same slots.
; Preserved: the halved nine-bit altitude, the one's-complement magnitudes,
;   the bounds and the descending order.
; Difference: the X/Y differences are formed from the objects' own 10.22
;   positions, as in the original.
; Kind: translated.
; Status: ported.
weapon_hit_scan
        movem.l d0-d1,-(sp)
        moveq   #OBJ_ALLOC_LIMIT,d5
        lea     object_table+(OBJ_ALLOC_LIMIT-1)*OBJ_SIZE,a1
.next
        tst.b   OBJ_ACTIVE(a1)                  ; 0002428D
        beq     .skip
        moveq   #0,d0
        move.b  OBJ_ALTITUDE(a0),d0             ; 00024296
        moveq   #0,d1
        move.b  OBJ_ALTITUDE(a1),d1
        sub.w   d1,d0                           ; 0002429C, borrow in bit 8
        asr.w   #1,d0                           ; 000242A2 rcr al, 1
        bpl     .alt_abs
        not.w   d0                              ; 000242A4 cbw / xor al, ah
.alt_abs
        cmpi.w  #$f,d0                          ; 000242A8 ja
        bhi     .skip
        move.l  OBJ_X(a0),d0
        sub.l   OBJ_X(a1),d0                    ; 000242AC
        bpl     .x_abs
        not.l   d0                              ; 000242BA cdq / xor
.x_abs
        cmpi.l  #$1400000,d0                    ; 000242BD ja
        bhi     .skip
        move.l  OBJ_Y(a0),d0
        sub.l   OBJ_Y(a1),d0                    ; 000242C4
        bpl     .y_abs
        not.l   d0
.y_abs
        cmpi.l  #$1400000,d0                    ; 000242D5 ja
        bhi     .skip
        bra     .done
.skip
        lea     -OBJ_SIZE(a1),a1
        subq.w  #1,d5                           ; 00024302 dec ebx / jne
        bne     .next
        suba.l  a1,a1
.done
        movem.l (sp)+,d0-d1
        rts

; The ground test both missiles make after moving: 00024258-00024282 and
; 000247A9-000247D3. The map byte under the new position, doubled plus one
; in eight bits (`shl al,1 / inc al`); at or below it is a ground hit.
; In: a0. Out: Z/C from `cmp` such that `bls` means hit.
; DOS: flat 00024258-00024282, missile ground test (also 000247A9-000247D3).
; DOS symbol: inside loc_000241C0
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: object_ground_sample's map byte, the same byte arithmetic.
; Preserved: the eight-bit wrap and the unsigned compare.
; Kind: translated.
; Status: ported.
weapon_ground_hit
        movem.l d0-d1,-(sp)
        bsr     object_ground_sample            ; d0 = the map byte
        add.b   d0,d0                           ; 00024278 shl al, 1
        addq.b  #1,d0                           ; 0002427A inc al
        move.b  OBJ_ALTITUDE(a0),d1
        cmp.b   d0,d1                           ; 0002427C cmp [alt], al
        movem.l (sp)+,d0-d1                     ; movem leaves the CCR alone
        rts

; 000241C0: the rocket in flight.
;
;   000241C0  latch X, Y and altitude into the previous-tick copies
;   000241E8  move along the heading (the 000248E4 mover's arithmetic)
;   00024219  vertical rate -= 0x100000
;   00024224  rate >= 0: 8.24 altitude += rate; a carry retires the slot
;             (00024306: active = 0)
;             rate <  0: 8.24 altitude += rate; no carry means it fell
;             through zero - 00024997
;   0002424B  altitude byte = the 8.24 value's top byte
;   00024258  ground test -> 00024997
;   00024288  proximity test; a hit takes 6 off the target's [00021F93],
;             less a quarter (5) unless [00019DB8] & 0xC0, sets its
;             [00021B29] bit 0 on a borrow, and ends in 00024997
; In: a0 = object. Out: nothing.
; DOS: flat 000241C0-0002430D, rocket state.
; DOS symbol: loc_000241C0
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same order, the same 8.24 altitude and carry tests.
; Preserved: the gravity step, both carry exits, the ground and proximity
;   tests and the damage rule.
; Difference: [00019DB8] is the PIT PRNG (flt_shake_rng). Its value at a
;   given frame depends on the timer phase, which is Unproven against DOS
;   (analysis/functions/browser-attract.md#shake-timer), so a hit's 6-or-5
;   is not certified per shot.
; Kind: translated.
; Status: ported.
object_state_rocket
        movem.l d0-d5/a1,-(sp)
        move.l  OBJ_X(a0),OBJ_PREV_X(a0)        ; 000241C0
        move.l  OBJ_Y(a0),OBJ_PREV_Y(a0)        ; 000241CE
        move.b  OBJ_ALTITUDE(a0),OBJ_PREV_ALT(a0)       ; 000241DC
        bsr     object_move                     ; 000241E8-00024212
        subi.l  #$100000,OBJ_VRATE(a0)          ; 00024219
        move.l  OBJ_VRATE(a0),d0                ; 00024224
        bmi     .falling
        add.l   d0,OBJ_ALT_ACC(a0)              ; 0002422F
        bcs     .retire                         ; 00024236 jb
        bra     .altitude
.falling
        add.l   d0,OBJ_ALT_ACC(a0)              ; 0002423E
        bcc     .explode                        ; 00024245 jae
.altitude
        move.b  OBJ_ALT_ACC(a0),OBJ_ALTITUDE(a0)        ; 0002424B top byte
        bsr     weapon_ground_hit               ; 00024258-00024282
        bls     .explode
        bsr     weapon_hit_scan                 ; 00024288-000242DA
        move.l  a1,d0
        beq     .done                           ; 00024305 ret
        moveq   #6,d1                           ; 000242DC
        move.b  flt_shake_rng+3,d2              ; 000242DE byte [00019DB8]
        andi.b  #$c0,d2
        bne     .damage
        move.b  d1,d2                           ; 000242E7
        lsr.b   #2,d2
        sub.b   d2,d1                           ; 000242EC
.damage
        sub.b   d1,OBJ_HEALTH(a1)               ; 000242EE [ebx + 00021F93]
        bcc     .explode                        ; 000242F4
        ori.b   #1,OBJ_PHASE(a1)                ; 000242F6 [ebx + 00021B29]
.explode
        bsr     object_transition_home          ; 000242FD -> 00024997
        bra     .done
.retire
        clr.b   OBJ_ACTIVE(a0)                  ; 00024306
.done
        movem.l (sp)+,d0-d5/a1
        rts

; 00024680: the Hellfire in flight.
;
;   00024680  latch X, Y and altitude
;   000246A8  timer + 1; reaching 0x80 (`js`) -> 00024997
;   000246B4  with a lock [00019D10]: the bearing from the target to the
;             missile through 000256C8, whose esi is left as the distance
;             estimate min/2 + max. Turn toward it by the nine-bit
;             difference halved through the borrow, at most 0x14 a tick.
;   00024708  climb 3 while below 0xFA; then against the target's altitude:
;             target above by more than 4 - climb 8 more (saturating);
;             target below and timer >= 5 - descend
;             (below - 1) / (2 * distance / speed) + 3, flooring at 0
;   00024778  move along the heading
;   000247A9  ground test -> 00024997
;   000247D9  timer <= 5 -> out
;   000247E6  proximity test; a hit takes 0x50 off the target's [00021F93],
;             sets its [00021B29] bit 0 on a borrow, puts the target's
;             altitude into the missile's latched altitude, and 00024997
; In: a0 = object. Out: nothing.
; DOS: flat 00024680-0002485E, Hellfire state.
; DOS symbol: loc_00024680
; Record: analysis/functions/browser-attract.md#weapon-fire
; Port: the same order and byte arithmetic.
; Preserved: the timer exit, the steering and its cap, both climb rules, the
;   descent law, the ground and proximity tests and the hit handling.
; Kind: translated.
; Status: ported.
object_state_hellfire
        movem.l d0-d7/a1,-(sp)
        move.l  OBJ_X(a0),OBJ_PREV_X(a0)        ; 00024680
        move.l  OBJ_Y(a0),OBJ_PREV_Y(a0)        ; 0002468E
        move.b  OBJ_ALTITUDE(a0),OBJ_PREV_ALT(a0)       ; 0002469C
        addq.b  #1,OBJ_TIMER(a0)                ; 000246A8 inc [00021E35]
        bmi     .explode                        ; 000246AE js
        move.w  object_target_latch,d0          ; 000246B4 [00019D10]
        beq     .move                           ; 000246BD
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a1
        adda.l  d0,a1                           ; the target
        move.l  OBJ_X(a1),d0
        move.l  d0,view_bearing_origin_x        ; 000246C3 [0002234C]
        move.l  OBJ_Y(a1),d0
        move.l  d0,view_bearing_origin_y        ; 000246CF [00022350]
        move.l  OBJ_X(a0),d6
        move.l  OBJ_Y(a0),d7
        bsr     view_bearing_point              ; 000246DB -> 000256C8
        move.l  d1,d4                           ; esi, the distance estimate
        sub.b   OBJ_HEADING(a0),d0              ; 000246E0
        beq     .steered                        ; 000246E6
        ; RCR leaves SF alone, so 000246EA jns tests the sign of the byte the sub
        ; at 000246E0 left, not of the rotated value; the rotate only needs the
        ; sub's borrow in X, which beq/bmi preserve.
        bmi     .rot_down                       ; 000246EA jns, SF from 000246E0
        roxr.b  #1,d0                           ; 000246E8 rcr al,1
        bra     .turn_up
.rot_down
        roxr.b  #1,d0                           ; 000246E8 rcr al,1
        neg.b   d0                              ; 000246EC
        cmpi.b  #$14,d0
        bls     .down_capped
        moveq   #$14,d0
.down_capped
        sub.b   d0,OBJ_HEADING(a0)              ; 000246F4
        bra     .steered
.turn_up
        cmpi.b  #$14,d0                         ; 000246FC
        bls     .up_capped
        moveq   #$14,d0
.up_capped
        add.b   d0,OBJ_HEADING(a0)              ; 00024702
.steered
        cmpi.b  #$fa,OBJ_ALTITUDE(a0)           ; 0002470F jae
        bcc     .no_climb
        addq.b  #3,OBJ_ALTITUDE(a0)             ; 00024718
.no_climb
        move.b  OBJ_ALTITUDE(a1),d0             ; 0002471F
        sub.b   OBJ_ALTITUDE(a0),d0             ; 00024725
        bcs     .target_below                   ; 0002472B jb
        cmpi.b  #4,d0                           ; 0002472D jbe
        bls     .move
        addi.b  #8,OBJ_ALTITUDE(a0)             ; 00024731
        bcc     .move                           ; 00024738 jae
        st      OBJ_ALTITUDE(a0)                ; 0002473A = 0xFF
        bra     .move
.target_below
        not.b   d0                              ; 00024743
        moveq   #0,d3
        move.b  d0,d3                           ; 00024745 ebx
        cmpi.b  #5,OBJ_TIMER(a0)                ; 00024748 jb
        bcs     .move
        move.l  d4,d0
        add.l   d0,d0                           ; 00024755 shl eax, 1
        divu.l  OBJ_SPEED(a0),d0                ; 00024757 div [0001FE34]
        exg     d0,d3                           ; 0002475E xchg: d3 = n
        tst.l   d3
        beq     .no_divide                      ; 00024761
        divu.l  d3,d0                           ; 00024765 div ebx
.no_divide
        addq.b  #3,d0                           ; 00024767
        sub.b   d0,OBJ_ALTITUDE(a0)             ; 00024769
        bcc     .move                           ; 0002476F jae
        clr.b   OBJ_ALTITUDE(a0)                ; 00024771
.move
        bsr     object_move                     ; 00024778-000247A2
        bsr     weapon_ground_hit               ; 000247A9-000247D3
        bls     .explode
        cmpi.b  #5,OBJ_TIMER(a0)                ; 000247D9 jbe
        bls     .done
        bsr     weapon_hit_scan                 ; 000247E6-00024838
        move.l  a1,d0
        beq     .done                           ; 0002485E ret
        subi.b  #$50,OBJ_HEALTH(a1)             ; 0002483A
        bcc     .hit_alt
        ori.b   #1,OBJ_PHASE(a1)                ; 00024843
.hit_alt
        move.b  OBJ_ALTITUDE(a1),OBJ_PREV_ALT(a0)       ; 0002484A-00024850
.explode
        bsr     object_transition_home          ; 00024856 / 000246AE -> 00024997
.done
        movem.l (sp)+,d0-d7/a1
        rts

        data
        even
; DOS flat 00022344. The factory's f1 byte is an index into this table;
; entries 0..4 are the authored values used by the mission records.
object_aux_table
        dc.b    $09,$06,$07,$08,$03
        even
; [00022880]: the launch rail offset, 1.5 map units in 10.22. It lives in the
; image and is only ever negated (00022BCB/0002304A), never reset, so which
; side the next weapon leaves from carries across missions and passes.
weapon_rail
        dc.l    $1800000
; 000066E2-000067AE's inline names, in the order it loads them, and the
; [00019E74 + 4*i] slot each one lands in.
WEAPON_BANK_NAME = 10
weapon_bank_names
        dc.b    "CHAF.RLE",0,0
        dc.b    "STGR.RLE",0,0
        dc.b    "HELL.RLE",0,0
        dc.b    "ROCK.RLE",0,0
        dc.b    "BULL.RLE",0,0
        dc.b    "BOOM.RLE",0,0
weapon_bank_order
        dc.b    1,4,3,2,0,5
        even

        bss
        even
; Per-frame cull tallies - see the note in object_draw_pass.
        even
        even

object_table
        ds.b    OBJ_COUNT*OBJ_SIZE
        even
object_image_ready
        ds.b    1
        even
; [00019E74]-[00019E88], the six shared banks, in address order.
weapon_bank_ptrs
weapon_bank_bull
        ds.l    1
weapon_bank_chaf
        ds.l    1
weapon_bank_rock
        ds.l    1
weapon_bank_hell
        ds.l    1
weapon_bank_stgr
        ds.l    1
weapon_bank_boom
        ds.l    1
; Their RGB565 palettes, the Falcon's replacement for the one translated DAC.
weapon_palette_ptrs
weapon_palette_bull
        ds.l    1
weapon_palette_chaf
        ds.l    1
weapon_palette_rock
        ds.l    1
weapon_palette_hell
        ds.l    1
weapon_palette_stgr
        ds.l    1
weapon_palette_boom
        ds.l    1
; 1 while object_draw_frame (0002519D) is running the shared draw tail.
object_draw_by_frame
        ds.w    1
        even
weapon_bank_store
        ds.b    OBJECT_BANK_BYTES*6
        even
weapon_palette_store
        ds.b    512*6
        even
        even
        even
object_order
        ds.w    OBJ_COUNT
        even
; The depth of the object each object_order position names, carried beside it
; through the sort so a comparison is one indexed read. Not game state: it is
; rebuilt from OBJ_DEPTH at every object_depth_sort entry and nothing outside
; that routine reads it.
object_depth_key
        ds.l    OBJ_COUNT
        even
player_hit_flag
        ds.w    1
; DOS [0002824B], consumed by object_state_wreckage's gated one-shot tail.
object_endcue_hold
        ds.w    1
; DOS [000019E49], set once by that same tail.
player_death_cue
        ds.w    1
; The countermeasure chain's inputs and the allied object. [00019D92] and
; [00019D94] are cleared by 000234A4 at the top of every update pass and raised
; by 00023EA7 (a tank has the player in its aim) and 000235EF (a shell reached
; the player); 00019555-0001959E reads them after the flight core. [00019D8F]
; and [00019D90] count the chaff and flares in the air: the launchers
; 00022A00/00022AA0 raise them and the cloud states 00024480/000244A0 lower
; them. [00019D93] is 000077A0's threat blip, which is not drawn here.
; [00022368] is the allied object 00023424 (type 4) installs.
object_threat_chaff
        ds.b    1
object_threat_bull
        ds.b    1
object_chaff_active
        ds.b    1
object_flare_active
        ds.b    1
object_threat_blip
        ds.b    1
        even
object_ally
        ds.l    1
; [00022384] and [00019D40], set when the ally is shot down (00023A17-00023A25);
; nothing recovered reads them yet.
ally_wrecked
        ds.b    1
        even
ally_aux_40
        ds.l    1
; Transient selection made by the DOS draw handlers through 0002236C. The
; Falcon stores the same current bank/palette explicitly while one object is
; projected; it is not a global default model.
object_draw_model_bank
        ds.l    1
object_draw_palette
        ds.l    1
object_draw_override
        ds.w    1
object_draw_pad
        ds.b    1
object_draw_aspect_bias
        ds.b    1
; [0002237F] and [0002237E], set by 00024C25/00024C2A around the chase
; camera's helicopter and cleared after: the elevation bias and the no-shear flag.
object_elev_bias
        ds.b    1
object_no_shear
        ds.b    1
object_target_default
        ds.w    1
; 1 while 00007860's secondary 00024B17 pass is composing the target MFD.
; This is a Falcon routing flag; the DOS side uses the substituted globals.
object_target_view
        ds.w    1
; [0x19D10]: the locked target, or 0 for none. 0000D449-0000D454 also drops
; it when the locked object's targetability byte has gone to zero - the lock
; does not survive the target leaving the screen.
object_target_latch
        ds.w    1
        even
; [0x19D14]: the locked target's depth, latched at 0000D43D and printed by
; 000079DE as the RANGE readout. A long, because OBJ_DEPTH is.
hud_target_range
        ds.l    1
object_slot_index
        ds.w    1
object_project_ring
        ds.w    1
; The unbiased ring: 00024D28's divisor and 00024D58's page come from this
; one, while object_project_ring above is the clip ring.
object_b_ring
        ds.w    1
; [0x22365]: the fan column 00024D9F publishes and 0002543A blits at. The
; byte beside it says whether this frame reached that store - the three exits
; above it all abort the draw.
object_project_x
        ds.w    1
        even
object_project_page
        ds.b    1
object_page_valid
        ds.b    1
object_fan_valid
        ds.b    1
        even
object_spawn_index
        ds.w    1
        even
object_factory_object
        ds.l    1
object_factory_model_a
        ds.l    1
object_factory_model_b
        ds.l    1
object_factory_palette_a
        ds.l    1
object_factory_palette_b
        ds.l    1


        text

; The objects plotted on the map. 000075C9 walks slots 30 down to 1 - the
; mission allocator's own range - and for each active slot whose auxiliary
; byte 00021DB3 is non-zero draws that byte as a sprite element at
;
;   x = 0x6F + high32(lateral * scale),   rejected outside -0x26..+0x26
;   y = 0xCE + high32(-depth  * scale),   rejected outside 0xAE..0xD9
;
; with scale = 0xFFFFFFFF / ([00019C90] >> 5), which is 1023 at the captured
; zoom. Those bounds are the panel: x 73..149 and y 174..217, which is the
; 80 by 44 rectangle at (72, 174) the map view fills.
;
; 0000763A then blinks a second marker over mission targets: when the frame
; counter [00019DE8] has its low two bits clear - one frame in four - and the
; object's flag byte 00021F39 is set, element 0x14 goes over the first at the
; same position. That flag is the '*' the mission parser records.
;
; The port's lateral and depth are 16.16 where the original's are 10.22, so
; the product is taken 26 bits down instead of 32; the scale itself is the
; original's.
; DOS: flat 000075B5-00007666, the map's object markers.
; DOS symbol: inside sub_000075B0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: plots the authored object markers on the recovered map grid.
; Preserved: slot range and order, the aux-byte element, both rejection
; windows, the panel centre, and the one-in-four target blink.
; Difference: 00025B27 reads bank [00019E94], whose writer is not traced; this
;   uses hud_bank, as every other 00025B27 call site in this port does.
; Kind: translated.
; Status: ported; marker capture remains pending.
mfd_draw_markers
        movem.l d0-d7/a0-a6,-(sp)
        ; These are HUDS elements through 00025B27, so they take HUDS's
        ; palette - the DOS machine has one DAC and no selection to make, the
        ; Falcon keeps one expansion per bank. Without this the markers drew
        ; through whatever the terrain left installed, which is the same fault
        ; the RANGE readout had.
        move.l  sprite_palette,-(sp)
        move.l  #hud_palette,sprite_palette
        ; 000075B5: scale = 0xFFFFFFFF / (zoom >> 5).
        move.l  mfd_zoom,d0                     ; [00019C90]
        lsr.l   #5,d0
        beq     .out
        move.l  #$ffffffff,d1
        divu.l  d0,d1
        move.l  d1,d7                           ; the scale

        lea     object_table+(OBJ_ALLOC_LIMIT-1)*OBJ_SIZE,a6
        move.w  #OBJ_ALLOC_LIMIT,d6             ; 000075C9 ecx = 0x1E
.slot
        tst.b   OBJ_ACTIVE(a6)
        beq     .next                           ; 000075CE
        moveq   #0,d5
        move.b  OBJ_AUX(a6),d5                  ; 000075DB [00021DB3]
        beq     .next

        move.l  OBJ_LATERAL(a6),d0
        bsr     .scaled
        move.l  d0,d3                           ; esi
        cmpi.l  #-$26,d3
        ble     .next                           ; 000075F5
        cmpi.l  #$26,d3
        bge     .next                           ; 000075FA

        move.l  OBJ_DEPTH(a6),d0
        neg.l   d0                              ; 00007606
        bsr     .scaled
        addi.l  #$ce,d0                         ; 0000760C
        move.l  d0,d4
        cmpi.l  #$ae,d4
        bls     .next                           ; 00007612
        cmpi.l  #$d9,d4
        bcc     .next                           ; 0000761A

        addi.l  #$6f,d3                         ; 00007622
        add.w   mfd_body_offset,d3              ; 00025B61 + [0x19CA8]
        move.w  d5,d0
        move.w  d3,d1
        move.w  d4,d2
        move.l  work_screen,a0
        lea     hud_bank,a1
        bsr     sprite_draw_page

        ; 0000763A: one frame in four, a second marker over a '*' target.
        move.l  frame_count,d0
        andi.l  #3,d0
        bne     .next
        tst.b   OBJ_FLAG(a6)                    ; 00007646 [00021F39]
        beq     .next
        moveq   #$14,d0                         ; 0000764F
        move.w  d3,d1
        move.w  d4,d2
        move.l  work_screen,a0
        lea     hud_bank,a1
        bsr     sprite_draw_page
.next
        lea     -OBJ_SIZE(a6),a6
        subq.w  #1,d6
        bne     .slot                           ; 0000765F dec / jne
.out
        move.l  (sp)+,sprite_palette
        movem.l (sp)+,d0-d7/a0-a6
        rts

; high32(value * scale) with the port's 16.16 lateral/depth against the original's
; 12.20 ([0002085C]/[00020A64], four more fractional bits): the product comes 28
; bits down rather than 32. This was 26, which put every page-0 marker four times
; too far out; DEMO1 record 370's three markers now land on DOS's. In d0, out d0.
;
; The zoom operand reaches the shared multiply macro in d1. Preserve d3:
; 000075F3 parks the first product in esi and 00007622 still reads that esi
; after the second `imul` at 00007608. This macro leaves d3 untouched.
.scaled
        movem.l d1-d2,-(sp)
        move.l  d7,d1
        MulS64D2
        moveq   #28,d1
        lsr.l   d1,d0
        moveq   #4,d1
        lsl.l   d1,d2
        or.l    d2,d0
        movem.l (sp)+,d1-d2
        rts
; Page 1: element 0x31, then every active upper slot with a marker byte,
; plotted on a fixed scale. The slots are 0x82 down to 0x1F - 130 to 31, the
; half of the table the mission allocator does not use - and the scale is a
; plain `sar cl` with cl = 0x17 on the DOS 10.22 lateral and depth, so
; one pixel per two map units, not the zoom page 0 divides by. The window
; is -0x28 < x < 0x28 and -0x16 < y < 0x16 around (0x6F, 0xC4), both bounds
; exclusive, and the marker is the slot's own 00021DB3 element through
; 00025B27. Unlike page 0 there is no target blink.
;
; The port's lateral and depth are 16.16, six bits below the original's
; 10.22, so the same floor division is a shift of 17.
; DOS: flat 00007710-00007798, MFD page 1.
; DOS symbol: loc_00007710
; Record: analysis/functions/falcon-attract.md#mfd-bodies
; Port: draws the panel element and the upper-slot markers.
; Preserved: element, slot range and order, the shift, both windows with
;   their exclusive bounds, the centre, and the masked blitter.
; Kind: translated.
; Status: ported.
mfd_body_07710
        movem.l d0-d7/a0-a6,-(sp)
        moveq   #$31,d0                         ; 00007710
        jsr     mfd_opaque_panel
        move.l  sprite_palette,-(sp)
        move.l  #hud_palette,sprite_palette
        lea     object_table+(OBJ_COUNT-1)*OBJ_SIZE,a6
        move.w  #OBJ_COUNT,d6                   ; 0000772F ebp = 0x82
.upper
        tst.b   OBJ_ACTIVE(a6)                  ; 00007734 [0x21921]
        beq     .upper_next
        moveq   #0,d5
        move.b  OBJ_AUX(a6),d5                  ; 0000773D [0x21DB3]
        beq     .upper_next
        move.l  OBJ_LATERAL(a6),d3
        ; 0000772D `mov cl,0x17`: the original's lateral and depth are 12.20
        ; (world << 20) and it shifts them 23 down. The port's are 16.16, four
        ; fractional bits fewer, so the same quantity is 19 down. This was 17,
        ; which put every marker four times too far from the centre and out of
        ; the +-0x28/+-0x16 windows - a tank 62 units ahead plots 8 rows up
        ; in DOS and was rejected at 31 here.
        moveq   #19,d0
        asr.l   d0,d3                           ; 00007753 sar esi, cl
        cmpi.l  #-$28,d3
        ble     .upper_next                     ; 00007758
        cmpi.l  #$28,d3
        bge     .upper_next                     ; 0000775D
        move.l  OBJ_DEPTH(a6),d4
        neg.l   d4                              ; 00007766
        asr.l   d0,d4                           ; 00007768
        cmpi.l  #-$16,d4
        ble     .upper_next                     ; 0000776D
        cmpi.l  #$16,d4
        bge     .upper_next                     ; 00007772
        addi.w  #$6f,d3                         ; 00007774
        add.w   mfd_body_offset,d3
        addi.w  #$c4,d4                         ; 00007777
        move.l  d5,d0
        move.w  d3,d1
        move.w  d4,d2
        move.l  work_screen,a0
        lea     hud_bank,a1
        bsr     sprite_draw_page                ; 0000778B -> 00025B27
.upper_next
        lea     -OBJ_SIZE(a6),a6
        subq.w  #1,d6
        cmpi.w  #OBJ_ALLOC_LIMIT,d6
        bne     .upper                          ; 00007793 cmp ebp, 0x1E
        move.l  (sp)+,sprite_palette
        movem.l (sp)+,d0-d7/a0-a6
        rts

        end
