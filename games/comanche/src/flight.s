; Route: analysis/functions/falcon-attract.md#replay-flight.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; The original's flight integration, ported arithmetic-for-arithmetic from
; the player handler at DOS 00018F94-0001959E and its core at 000194E0.
;
; Exactness is not taste here: the attract demos replay recorded INPUTS, not
; positions, so the flight only follows the recording if every shift, clamp
; and damping quirk lands on the same values the original's did. Where this
; file rounds, the original rounded.
;
; The state the original keeps, in its units:
;   flt_x, flt_y     positions, 10.22            (DOS 19CD4/19CD8)
;   flt_angle        flight direction, a full 32-bit angle; the top nine
;                    bits index the 512-step Q31 sine table   (19D04)
;   flt_turn         angular velocity per tick               (19D08)
;   flt_fwd          forward velocity, 10.22 per tick        (19CC8)
;   flt_lat          lateral velocity                        (19CD0)
;   flt_roll         visual roll accumulator, +/-133         (19CF0)
;   flt_pitch        visual pitch accumulator, +/-33         (19CF4)
;   player_altitude  half-map-byte units, byte range         (19DFC)
;   flt_prevalt      the frame driver's latch of it          (19DF6)
;   flt_frame_x/y    frame-start 10.22 position snapshot    (19CDC/19CE0)
;   flt_maxspd       forward speed ceiling                   (19CCC)
;
; Inputs per tick, exactly the demo record's fields:
;   flt_axis1        signed word, turn/lateral stick         (19DC8)
;   flt_axis2        signed word, speed stick                (19DCC)
;   flt_collective   byte, the terrain-follow target         (19D82)
;   flt_trig1/2      pending-shot counters, OR'd in          (19DF2/3)
;
; The pieces of the original this pass does not carry, recorded rather than
; hidden: the damage array's spin and sink, and the wounded speed cap. The
; ground-contact rollback and no-damage bounce are carried below; the shipped
; demos fly clean and never enter the damage-specific aftermath.

        include "inc/comanche.s"
        include "inc/snd.s"
        xref    snd_voice, snd_sample_ptr, snd_bank_fx, snd_silence, snd_speech_a
        xref    snd_banks_load, snd_apply_settings
        xref    menu_open

        global  flight_reset, flight_tick, flight_publish
        xref    countermeasure_tick, hud_clearance
        global  flt_x, flt_y, flt_angle, flt_turn, flt_fwd, flt_lat
        global  flt_roll, flt_pitch, flt_prevalt, flt_maxspd
        global  flt_shake_phase, flt_shake_timer, flight_shake_tick
        global  flt_pub_sin, flt_pub_cos
        global  flt_frame_x, flt_frame_y
        global  flt_axis1, flt_axis2, flt_collective, flt_trig1, flt_trig2
        global  flt_torque, flt_fuel, flt_collective_prev, flt_mission_end
        global  flt_death_timer, flt_crash_drop
        global  flight_rotor, flight_menu_silence, flight_announcer, flight_announcer_reset
        global  flight_mission_sound_load, flight_mission_sound_start
        xref    music_theme_load, music_theme_start
        xref    mission_damage, flt_shake_rng, object_target_latch
        xref    player_death_cue, mission_wounded, view_variant, view_select
        xref    object_scan_upper, object_table, object_state_wreckage

        text

; Zero the rates and seed the speed ceiling. Position, angle and altitude are
; the caller's to set - game_init and demo_start have different sources.
;
; The five rates are the set 00019A8B-00019AB3 zeroes when a replay starts,
; and the ceiling is 000063EC's mission-start 0x1800000 (00026B65 stores the
; same value; 00018FAD halves it to 0x800000 while damaged, which is the
; wounded cap this port does not carry).
; DOS: flat 00019A81-00019AB3, replay-start rate reset; 000063EC speed ceiling.
; DOS symbol: inside loc_00019A4D
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: clears per-tick rates while callers seed the recovered start state.
; Preserved: zeroed rates, DOS speed ceiling, altitude latch, and units.
; Difference: 00019A81-00019AB3 zeroes only [00019D10] and the five rates. The
;   axes, triggers and collective cleared below are not in that set - DOS
;   leaves them standing and 00018D20 reseeds the collective at the frame
;   boundary - and [00019D10]'s target latch has no counterpart here. Clearing
;   them is a Falcon start-state choice, recorded rather than claimed as DOS.
; Kind: translated.
; Status: ported; replay-state validation is pending capture.
flight_reset
        clr.l   flt_turn
        clr.l   flt_fwd
        clr.l   flt_lat
        clr.l   flt_roll
        clr.l   flt_pitch
        clr.w   flt_axis1
        clr.w   flt_axis2
        clr.b   flt_trig1
        clr.b   flt_trig2
        clr.b   flt_collective_prev            ; [00019D83], BSS zero until 00018D25
        clr.w   flt_mission_end
        clr.w   player_death_cue                ; 000063E5 [00019E49] = 0
        move.b  #100,flt_death_timer            ; 000063DE [00019E48] = 0x64
        clr.l   flt_crash_drop                  ; 000056B0 [00019DC4] = 0
        clr.b   flt_collective                 ; DOS startup BSS is zero; demo
                                               ; records supply it before tick
        move.l  #$1800000,flt_maxspd
        moveq   #0,d0
        move.b  player_altitude,d0
        move.b  d0,flt_prevalt
        rts

; One integration tick. The damping runs first, as the original's does, so a
; centred stick decays the rates before this tick's input tops them up.
; DOS: flat 00019007-0001907C (damping), 0001907C-000191B6 (control inputs
; and their clamps), 00019352-0001941F (terrain follow), 00019424-0001946B
; (collision rollback and bounce) and 000194E0-00019555 (the movement core).
; 00018F94-00019007, the prologue, is the wounded speed cap and the engine
; note written to [00004186]; neither is in this milestone's scope.
; DOS symbol: inside loc_00018FFD
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: 68030 fixed-point translation of damping, controls, terrain follow,
;       collision rollback, altitude smoothing, heading, and movement.
; Preserved: byte carries, clamps, Q31 products, update order, and side effects.
; Differences, each against the instruction it drops:
;   - 0001908A-000190A5 adds a keyboard turn term of +/-0x400000 when the
;     device byte [00025DD7] is 0x30. The replay path feeds [00019DC8]
;     directly at 00018D2C, so no attract tick reaches it; the live keyboard
;     device selection is unrecovered and stays out rather than guessed.
;   - 000190AB-000190B4 adds 0x600000 to the turn rate while damage byte
;     [00019E38] is negative. That array is written only by the damage tail
;     at 000194A3/000194AC, which this port does not carry.
;   - 0001950F/0001951B publish the two table entries to [00019CB8]/[00019CBC].
;     They were recorded here as having no observer; view_select is one -
;     000198A5/000198B6 place variant 7's camera ten map cells back along
;     THIS pair, the flight heading's, not the view's - so both are now
;     carried below as flt_pub_sin/flt_pub_cos.
;   - 00019461's screen-shake arming is now carried, and so is the counter it
;     drives: flight_shake_tick below ports 00001DB5-00001DE7 and
;     backdrop_build consumes the phase where 00007DB5 does. 00015BBC's other
;     consumer - the CRTC start address and the attribute controller's pixel
;     pan - is a VGA display effect with no Falcon equivalent here and stays
;     out; the terrain horizon end is present.
; Kind: translated.
; Status: ported; damage aftermath is explicitly unrecovered below.
flight_tick
        movem.l d0-d7/a0-a1,-(sp)

        ; 00018E10-00018E44: once the tank is below zero the pilot has no say in
        ; the collective. At exactly -0x10E the flight ends (0002873D); before
        ; that the collective is the previous tick's value (00018D25 saved it
        ; into [00019D83]) minus one, so it is dragged down a notch a tick and
        ; stays at zero. The call at 00018E44 as it reaches zero is
        ; sub_0001899A, which re-stages the rotor loop through 00004F6E: here
        ; flight_rotor.
        tst.l   flt_fuel
        bpl     .fuel_ok                        ; 00018E17 jns
        cmpi.l  #-$10e,flt_fuel
        bne     .fuel_drag
        ; 0002873D ends the flight (mission_end in debrief.s); the main loop
        ; acts on the request once the frame is out of the way.
        move.w  #1,flt_mission_end
        bra     .tick_abandoned                 ; `je 0002873D`: nothing else runs
.fuel_drag
        move.b  flt_collective_prev,flt_collective      ; 00018E29/00018E2E
        beq     .fuel_ok                        ; 00018E33/00018E3A
        subq.b  #1,flt_collective               ; 00018E3C/00018E42
        bne     .fuel_ok                        ; 00018E42 jne 00018E49
        bsr     flight_rotor                    ; 00018E44: the collective just reached zero
.fuel_ok

        ; 00018E49: `dec dword [00019D60]`, once a tick.
        subq.l  #1,flt_fuel

        ; 00018EE3-00018F93: a wrecked Comanche is flown by nobody. [00019E49]
        ; set counts [00019E48] down from 100; at zero the flight ends. The
        ; stick is zeroed. With the hull still non-negative (a hit on the
        ; wingman's side, a bomb) the collective is held at 0xFE and the
        ; helicopter sinks to the ground nose-up; with it negative the rotor
        ; stops, the screen sinks (the CRTC start gains 0x52 a tick, 00018F5F,
        ; and the chase view takes over at 0xE6A) and a wreck puffs from the
        ; fixed object every sixteenth tick.
        tst.w   player_death_cue
        beq     .alive
        moveq   #0,d0
        move.b  player_death_cue+1,d0           ; al = [00019E49]
        sub.b   d0,flt_death_timer              ; 00018EF0 sub [00019E48], al
        bne.s   .death_going
        move.w  #1,flt_mission_end              ; 00018EF6 je 0002873D
        bra     .tick_abandoned
.death_going
        clr.w   flt_axis1                       ; 00018EFC / 00018F06
        clr.w   flt_axis2
        tst.l   mission_wounded                 ; 00018F10
        bmi.s   .rotor_stopped
        move.b  #$fe,flt_collective             ; 00018F19
        cmpi.b  #$fa,player_altitude
        bhi.s   .not_low
        addq.b  #4,player_altitude              ; 00018F29
.not_low
        cmpi.b  #$e6,player_altitude            ; 00018F30
        bcs.s   .alive                          ; jb 00018F94
        move.w  #-$15e,flt_axis2                ; 00018F39 [00019DCC] = -350
        bra.s   .alive
.rotor_stopped
        clr.b   flt_collective                  ; 00018F45
        move.l  #10,flt_shake_timer             ; 00018F4C
        cmpi.b  #1,view_variant                 ; 00018F56
        bne.s   .no_sink
        addi.l  #$52,flt_crash_drop             ; 00018F5F
        cmpi.l  #$e6a,flt_crash_drop            ; 00018F66
        bcs.s   .no_sink                        ; jb
        moveq   #7,d0                           ; 00018F72 call 00019820: the '6' key's
        jsr     view_select                     ; case, the chase view
        SndSpeechA $0b                          ; 00018F77-00018F79: SPEAK1 id 11, the crash cue
.no_sink
        move.l  flt_shake_rng,d0
        andi.l  #$f,d0                          ; 00018F7E test [00019DB8], 0xF
        bne.s   .alive
        lea     object_table+(31-1)*OBJ_SIZE,a1 ; 00018F8A ecx = 0x1F
        jsr     object_scan_upper               ; 00018F8F -> 000227BF
.alive

        ; 00018F94-00018FB6: a damaged engine ([00019E39] negative) sinks the
        ; helicopter a unit a tick above altitude 10 and caps its speed at
        ; 0x800000.
        tst.b   mission_damage+1
        bpl.s   .engine_ok
        cmpi.b  #$0a,player_altitude
        bls.s   .engine_ok
        subq.b  #1,player_altitude              ; 00018FA6
        move.l  #$800000,flt_maxspd             ; 00018FAD [00019CCC]
.engine_ok

        ; 00018FB7-00018FE2: the T gauge's value, [00019D84], a byte the original
        ; computes before its damping chain and nothing in the port's flight
        ; reads back: sar(axis2, 5) one's-complemented when negative (cdq / xor
        ; eax,edx), plus three times the collective, clamped to 0xC8 on an
        ; unsigned compare, halved while the damage byte [00019E39] is negative.
        move.w  flt_axis2,d0
        ext.l   d0
        asr.l   #5,d0
        move.l  d0,d1
        smi     d2
        ext.w   d2
        ext.l   d2
        eor.l   d2,d0                           ; cdq / xor eax, edx
        moveq   #0,d1
        move.b  flt_collective,d1
        move.l  d1,d2
        add.l   d1,d1
        add.l   d2,d1                           ; ebx = collective * 3
        add.l   d1,d0
        cmpi.l  #$c8,d0
        blo.s   .torque_ok                      ; jb
        moveq   #$c8-256,d0                     ; mov al, 0xC8
.torque_ok
        tst.b   mission_damage+1                ; cmp [00019E39], 0 / jns
        bpl.s   .torque_store
        lsr.b   #1,d0                           ; shr al, 1
.torque_store
        move.b  d0,flt_torque

        ; Damping: v -= sar(v, cl) OR (v > 0), the OR into the low byte
        ; exactly as `setg bl / sar eax,cl / or al,bl` leaves it. cl is 5
        ; airborne and 3 near the ground, stepping down between groups.
        moveq   #5,d7
        cmpi.b  #$10,flt_collective
        bhi     .cl_air
        moveq   #3,d7
.cl_air
        lea     flt_fwd,a0
        bsr     .damp                           ; forward, cl
        lea     flt_lat,a0
        bsr     .damp                           ; lateral, cl
        subq.w  #1,d7
        lea     flt_turn,a0
        bsr     .damp                           ; turn, cl-1
        lea     flt_roll,a0
        bsr     .damp                           ; roll, cl-1
        subq.w  #1,d7
        lea     flt_pitch,a0
        bsr     .damp                           ; pitch, cl-2
        bra     .damped

.damp
        ; DOS: flat 00019007-0001907C, signed rate-damping sequence. The
        ; five blocks there are forward, lateral, turn, roll and pitch, with
        ; `dec cl` before turn and again before pitch, and 00019009 picks
        ; cl = 5 or 3 off the collective against 0x10 - the order and the
        ; two decrements above are that sequence, not a restatement of it.
        ; `beq` shortcuts v = 0, where 0001901B's setg is 0 and the whole
        ; block subtracts nothing.
        ; Port: applies the original setg/sar/or/sub operation to one rate.
        ; Preserved: sign-byte behavior and caller-selected shift count.
        ; Status: ported; covered by flight_tick arithmetic review.
        move.l  (a0),d0
        beq     .damp_done
        smi     d1                              ; d1 = $FF if negative
        moveq   #1,d2
        and.b   d1,d2
        eori.b  #1,d2                           ; d2 = 1 when v > 0 (v != 0)
        move.l  d0,d3
        asr.l   d7,d3
        or.b    d2,d3
        sub.l   d3,d0
        move.l  d0,(a0)
.damp_done
        rts

.damped
        ; Turn: axis1 << 14, clamped to +/-$4000000.
        move.w  flt_axis1,d0
        ext.l   d0
        moveq   #14,d1
        asl.l   d1,d0
        add.l   flt_turn,d0
        ; 000190AB-000190B4: a damaged tail rotor ([00019E38] negative) adds a
        ; constant yaw before the clamp.
        tst.b   mission_damage
        bpl.s   .rotor_ok
        addi.l  #$600000,d0
.rotor_ok
        cmpi.l  #$4000000,d0
        ble     .turn_hi_ok
        move.l  #$4000000,d0
.turn_hi_ok
        cmpi.l  #-$4000000,d0
        bge     .turn_lo_ok
        move.l  #-$4000000,d0
.turn_lo_ok
        move.l  d0,flt_turn

        ; Rudder: the two keypad rudder keys add a flat -/+$400000 to the turn
        ; rate (000192A9-000192CF). The original applies them AFTER the clamp
        ; above, and deliberately does not re-clamp - a held rudder key can
        ; carry the rate past $4000000. Placing them here rather than at their
        ; own address is the same arithmetic in the same order: between the
        ; clamp at 000190E0 and the rudder at 000192B2 nothing reads or writes
        ; [19D08], the next access being the ground-collision reset at
        ; 000193A3, so no observer exists in between to tell the two apart.
        ; During replay the key array is all-released and this contributes
        ; nothing, so the recorded demos still fly their recorded path.
        move.l  flt_turn,d0
        lea     key_state,a0
        tst.b   $70(a0)                         ; keypad 0, yaw left
        bmi     .rudder_left_done
        sub.l   #$400000,d0
.rudder_left_done
        tst.b   $71(a0)                         ; keypad ., yaw right
        bmi     .rudder_right_done
        add.l   #$400000,d0
.rudder_right_done
        move.l  d0,flt_turn

        ; Roll: (axis1 + 8) >> 4 into +/-133. It reaches the picture now -
        ; backdrop_build turns it into the per-column horizon byte that shears
        ; both the sky and the terrain spans - so this is no longer view state
        ; the renderer ignores.
        move.w  flt_axis1,d0
        ext.l   d0
        addq.l  #8,d0
        asr.l   #4,d0
        add.l   flt_roll,d0
        cmpi.l  #133,d0
        ble     .roll_hi_ok
        move.l  #133,d0
.roll_hi_ok
        cmpi.l  #-133,d0
        bge     .roll_lo_ok
        move.l  #-133,d0
.roll_lo_ok
        move.l  d0,flt_roll

        ; Lateral velocity: the DOS handler adds axis1 << 12 to [19CD0]
        ; immediately after the roll accumulator and clamps it to +/-$800000
        ; (00019118-00019152). The demo axis is the same signed word used by
        ; the turn update; omitting this independent velocity changes the
        ; recorded map path and makes the terrain-follow ladder hit unrelated
        ; ground.
        ; DOS: flat 00019118-00019152, lateral input and clamp.
        ; Port: applies the recovered signed axis shift and bounds.
        ; Preserved: shift count, update order, and +/-$800000 limits.
        ; Status: ported; the live joystick source remains a platform boundary.
        move.w  flt_axis1,d0
        ext.l   d0
        moveq   #12,d1
        asl.l   d1,d0
        add.l   flt_lat,d0
        cmpi.l  #$800000,d0
        ble     .lat_hi_ok
        move.l  #$800000,d0
.lat_hi_ok
        cmpi.l  #-$800000,d0
        bge     .lat_lo_ok
        move.l  #-$800000,d0
.lat_lo_ok
        move.l  d0,flt_lat

        ; Pitch: (16 - axis2) >> 5 into +/-33.
        move.w  flt_axis2,d0
        ext.l   d0
        neg.l   d0
        add.l   #16,d0
        asr.l   #5,d0
        add.l   flt_pitch,d0
        cmpi.l  #33,d0
        ble     .pitch_hi_ok
        moveq   #33,d0
.pitch_hi_ok
        cmpi.l  #-33,d0
        bge     .pitch_lo_ok
        moveq   #-33,d0
.pitch_lo_ok
        move.l  d0,flt_pitch

        ; Forward: -= axis2 << 11, clamped [-max/2, +max].
        move.w  flt_axis2,d0
        ext.l   d0
        moveq   #11,d1
        asl.l   d1,d0
        move.l  flt_fwd,d2
        sub.l   d0,d2
        move.l  flt_maxspd,d3
        cmp.l   d3,d2
        ble     .fwd_hi_ok
        move.l  d3,d2
.fwd_hi_ok
        asr.l   #1,d3
        neg.l   d3
        cmp.l   d3,d2
        bge     .fwd_lo_ok
        move.l  d3,d2
.fwd_lo_ok
        move.l  d2,flt_fwd

        ; 000191B6-0001922E: the replay trigger dispatch sits here, between the
        ; control inputs and the terrain follow, so a weapon leaves from the
        ; position and heading before this tick's move.
        bsr     weapon_dispatch

        ; 000192CF-000192EE: with the targeting damage entry [00019E3C]
        ; (mission_damage+4) negative, the lock is lost on the ticks the PIT
        ; PRNG's bits 2-4 are all clear.
        tst.b   mission_damage+4                ; 000192CF cmp [00019E3C],0
        bpl.s   .lock_kept                      ; 000192D6 jns
        move.l  flt_shake_rng,d0
        andi.l  #$1c,d0                         ; 000192D8 test [00019DB8],0x1C
        bne.s   .lock_kept
        clr.w   object_target_latch             ; 000192E4 [00019D10] = 0
.lock_kept

        ; DOS: FUN_00018F94 [000192EE-0001934F].
        ; Record: analysis/functions/browser-attract.md#player-damage-chain.
        ; JS: dos-damage.js objectCollision (browser flight remains dormant).
        ; Fixtures: tools/check-falcon-collision.py; 37 DOS outcomes, both CPUs.
        ; This checks the decision, not the crash aftermath or live route.
        ; 000192EE-0001934F: the helicopter against the first thirty objects,
        ; 1-based from the last. An active one within 15 of the altitude (half
        ; the difference, folded to its magnitude), and within 0x1400000 of the
        ; position on both axes, that is not a wreck hold the helicopter off:
        ; the same rollback and bounce a hit on the ground makes (00019424).
        moveq   #30,d6                          ; 000192EE ebx = 0x1E
.obj_loop
        move.w  d6,d0
        subq.w  #1,d0
        mulu    #OBJ_SIZE,d0
        lea     object_table,a0
        adda.l  d0,a0
        tst.b   OBJ_ACTIVE(a0)                  ; 000192F3
        beq.s   .obj_next
        move.b  player_altitude,d0              ; 000192FC
        sub.b   OBJ_ALTITUDE(a0),d0             ; 00019301
        roxr.b  #1,d0                           ; 00019307 rcr al,1: the borrow in
        bpl.s   .alt_mag                        ; 00019309-0001930B cbw / xor al,ah
        not.b   d0
.alt_mag
        cmpi.b  #$0f,d0                         ; 0001930D
        bhi.s   .obj_next
        move.l  flt_x,d0                        ; 00019311
        sub.l   OBJ_X(a0),d0                    ; 00019316
        bpl.s   .x_mag
        not.l   d0                              ; 0001931D-0001931E cdq / xor
.x_mag
        cmpi.l  #$1400000,d0                    ; 00019320
        bhi.s   .obj_next
        move.l  flt_y,d0                        ; 00019327
        sub.l   OBJ_Y(a0),d0                    ; 0001932C
        bpl.s   .y_mag
        not.l   d0
.y_mag
        cmpi.l  #$1400000,d0                    ; 00019336
        bhi.s   .obj_next
        cmpi.l  #object_state_wreckage,OBJ_STATE(a0)    ; 0001933D cmp [..],0x237B0
        bne     .crash                          ; 00019348 je skips; else 0001934A jmp 00019424
.obj_next
        subq.w  #1,d6                           ; 0001934F
        bne.s   .obj_loop

        ; Terrain follow, the original's own byte ladder. h is the map byte
        ; under the position; the x86 computes t = byte(2h + 1), subtracts
        ; the altitude byte, and branches on the byte flags. Keeping this
        ; byte-wide matters when 2h+1 wraps past $FF; the source map reaches
        ; heights where a widened 16-bit comparison gives a different flight.
        move.l  flt_y,d0
        moveq   #22,d1
        asr.l   d1,d0
        andi.l  #MAP_MASK,d0
        lsl.l   #8,d0
        lsl.l   #MAP_SHIFT-8,d0
        move.l  flt_x,d2
        asr.l   d1,d2
        andi.l  #MAP_MASK,d2
        add.l   d2,d0
        lea     original_height_map,a0
        moveq   #0,d3
        move.b  0(a0,d0.l),d3
        add.b   d3,d3
        addq.b  #1,d3                           ; byte(2h + 1)
        moveq   #0,d0
        move.b  player_altitude,d0
        sub.b   d0,d3                           ; byte(t - altitude)
        bcs     .above_ground                   ; t < altitude
        cmpi.b  #2,d3
        bhi     .crash
        add.b   d3,player_altitude              ; shallow penetration: pop
        bra     .alt_done
.crash
        ; 00019424 restores the frame-start 10.22 position and altitude, then
        ; the no-damage branch reverses lateral motion and bounces forward
        ; speed, with the hit's damage below. A wrecked Comanche skips the bounce
        ; and the damage (00019442).
        move.l  flt_frame_x,flt_x
        move.l  flt_frame_y,flt_y
        move.b  flt_prevalt,player_altitude
        tst.w   player_death_cue
        bne     .alt_done                       ; 00019449 jne 000194E0
        neg.l   flt_lat
        neg.l   flt_fwd
        move.l  flt_fwd,d0
        asr.l   #1,d0
        move.l  d0,flt_fwd
        ; 00019461, between the forward halving and the altitude pop: ten
        ; ticks of screen shake. flight_shake_tick turns this into the phase
        ; byte the backdrop subtracts.
        moveq   #10,d0
        move.l  d0,flt_shake_timer
        addq.b  #4,player_altitude
        bcc.s   .bounced
        move.b  #$ff,player_altitude
.bounced
        ; 0001947B-00019488: half of all hits scream - SPEAK1 id 2 or 3 from the PRNG's
        ; low two bits, none when they are 2 or 3 (00019484 jae skips the call).
        move.b  flt_shake_rng+3,d0              ; 0001947B [00019DB8]
        andi.b  #3,d0                           ; 00019480
        cmpi.b  #2,d0                           ; 00019482
        bcc.s   .no_scream                      ; 00019484 jae
        addq.b  #2,d0                           ; 00019486
        jsr     snd_speech_a                    ; 00019488 (al = 2 or 3; it keeps every register)
.no_scream
        ; 0001948D-000194DB: the hit costs two of the eight damage entries and
        ; up to three hull points. The PIT PRNG is stirred with the east
        ; coordinate first, so which entries is as unpredictable as the timer.
        move.l  flt_x,d0
        add.l   d0,flt_shake_rng                ; 00019492
        moveq   #0,d0
        move.b  flt_shake_rng+3,d0              ; 00019498 movzx eax, byte [19DB8]
        move.l  d0,d1
        andi.w  #7,d0                           ; 000194A1
        lea     mission_damage,a0
        subq.b  #1,0(a0,d0.w)                   ; 000194A3
        lsr.b   #5,d1                           ; 000194A9
        subq.b  #1,0(a0,d1.w)                   ; 000194AC
        move.l  flt_shake_rng,d0
        ror.l   #8,d0                           ; 000194B2
        move.l  d0,flt_shake_rng
        andi.l  #3,d0                           ; 000194B9-000194BE
        sub.l   d0,mission_wounded              ; 000194C1
        bpl.s   .still_alive                    ; 000194C7 jns
        move.w  #1,player_death_cue             ; 000194C9
.still_alive
        SndFX   5,$FF,0,0                       ; 000194D0-000194DB: the thump, SND1 id 5
        bra     .alt_done
.above_ground
        neg.b   d3                              ; clearance = altitude - t
        move.b  d3,hud_clearance                ; 00019391 mov [00019E00], al
        cmpi.b  #6,d3
        bhi     .following
        moveq   #0,d4
        move.b  flt_collective,d4
        cmpi.b  #6,d4
        bhi     .following
        clr.l   flt_turn                        ; full stop on the skids
        clr.l   flt_fwd
        clr.l   flt_lat
        clr.l   flt_roll
        clr.l   flt_pitch
        bra     .alt_done
.following
        moveq   #0,d4
        move.b  flt_collective,d4
        sub.b   d4,d3                           ; clearance - collective
        beq     .alt_done
        bcs     .too_low                        ; clearance < collective
        lsr.b   #4,d3
        addq.b  #4,d3                           ; sink step
        sub.b   d3,player_altitude
        bcc     .alt_done
        clr.b   player_altitude
        bra     .alt_done
.too_low
        neg.b   d3
        lsr.b   #4,d3
        addq.b  #3,d3                           ; climb step
        add.b   d3,player_altitude
        bcc     .alt_done
        move.b  #$ff,player_altitude
        bra     .alt_done
.alt_done
        ; The core. Altitude smoothing first: x86 `add al,prev` followed by
        ; `rcr al,1`. The 68030's extend bit is the same carry-in average.
        moveq   #0,d0
        move.b  player_altitude,d0
        moveq   #0,d1
        move.b  flt_prevalt,d1
        add.b   d1,d0
        roxr.b  #1,d0
        move.b  d0,player_altitude

        ; Angle and position: hi32 products against the Q31 table.
        move.l  flt_turn,d0
        add.l   d0,flt_angle
        move.l  flt_angle,d0
        moveq   #23,d1
        lsr.l   d1,d0                           ; 9-bit table step
        lsl.l   #2,d0
        lea     sine_q31,a0
        move.l  0(a0,d0.l),d2                   ; sin
        move.l  d2,flt_pub_sin                  ; 0001950F: [00019CB8]
        move.l  512(a0,d0.l),d3                 ; cos, +128 entries
        move.l  d3,flt_pub_cos                  ; 0001951B: [00019CBC]
        move.l  flt_fwd,d0
        MulS64  d3                        ; fwd * cos
        sub.l   d1,flt_y
        move.l  flt_fwd,d0
        MulS64  d2                        ; fwd * sin
        add.l   d1,flt_x
        move.l  flt_lat,d0
        MulS64  d3                        ; lat * cos
        add.l   d1,flt_x
        move.l  flt_lat,d0
        MulS64  d2                        ; lat * sin
        add.l   d1,flt_y

        ; 00019555-0001959E: the countermeasure decision closes the tick.
        bsr     countermeasure_tick

.tick_abandoned
        movem.l (sp)+,d0-d7/a0-a1
        rts

; Push the flight state into the coordinates the renderers read: 10.22 down
; to 16.16, and the 512-step angle onto the 256-step heading with the DOS
; -Y-forward axis flipped to this port's +Y.
; DOS: 00019CD4/00019CD8/00019D04 to renderer-facing globals.
; DOS symbol: none - the cited addresses are data
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: converts the 10.22 flight state to Falcon 16.16 and byte heading.
; Preserved: full-angle source, -Y axis conversion, and published state units.
; Kind: translated.
; Status: ported; renderer integration capture remains pending.
flight_publish
        movem.l d0-d1,-(sp)
        move.l  flt_x,d0
        asr.l   #6,d0
        move.l  d0,player_x
        move.l  flt_y,d0
        asr.l   #6,d0
        move.l  d0,player_y
        move.l  flt_angle,d0
        moveq   #24,d1
        lsr.l   d1,d0                           ; DOS heading byte
        neg.w   d0
        addi.w  #128,d0
        andi.w  #$00ff,d0
        move.w  d0,player_heading
        movem.l (sp)+,d0-d1
        rts

; ---------------------------------------------------------------------------
; The flight's sound requests that are not tied to one event elsewhere.
; ---------------------------------------------------------------------------

; The rotor loop switch. SND1 id 3 is staged on slot 2 at a quarter of the
; amplitude and plays again every time it ends (staged = playing), or the
; silence record is staged in its place when the collective is zero.
; Called at mission start (000069E0), when the fuel runs out (00018E44) and
; when the options bar closes (0001999D).
; DOS: flat 0001899A-000189BD.
; DOS symbol: sub_0001899A
; Record: analysis/functions/sound-falcon.md#call-sites
; Port: bl = 2, dl = 2, ecx = 0; eax = [SND1 + 0xC] + SND1 (id 3), or the silence
;   record 000040E2 when [00019D82] (flt_collective) is 0; VOICE (00004F6E).
; Preserved: the arguments and the test of the collective, in the original's order.
; Difference: nothing is staged when SND1 is not loaded (the DOS cannot reach here
;   without it: 000064A8 stops the program on a missing file). The routine keeps
;   every register and the flags.
; Kind: translated.
; Status: ported.
flight_rotor
        move.w  ccr,-(sp)
        movem.l d0-d3/a0,-(sp)
        move.l  snd_bank_fx,a0                  ; 000189A0 mov esi,[00019E98]
        move.l  a0,d0
        beq     .none                           ; platform: the bank is not loaded
        moveq   #3,d0
        jsr     snd_sample_ptr                  ; 000189A6/000189A9: eax = [esi+0xC] + esi
        moveq   #2,d1                           ; 0001899A bl = 2
        moveq   #2,d3                           ; 0001899C dl = 2
        moveq   #0,d2                           ; 0001899E ecx = 0
        tst.b   flt_collective                  ; 000189AB cmp [00019D82],0
        bne     .stage                          ; 000189B2 jne 00004F6E
        move.l  #snd_silence,d0                 ; 000189B8 eax = 000040E2
.stage
        jsr     snd_voice                       ; 000189B2/000189BD
.none
        movem.l (sp)+,d0-d3/a0
        move.w  (sp)+,ccr
        rts

; The in-flight options bar opening: slot 2 (the rotor loop, or a speech cue)
; is told to go silent after the sample it is on.
; DOS: flat 00025DEF-00025DFD (the VOICE call at the head of sub_00025DEF).
; DOS symbol: sub_00025DEF
; Record: analysis/functions/sound-falcon.md#call-sites
; Port: VOICE with eax = 000040E2, bl = 2, dl = 0, ecx = 0.
; Preserved: the arguments. The music pause that follows (00025E02-00025E06) belongs
;   to the music driver and is not ported.
; Kind: translated.
; Status: ported.
flight_menu_silence
        move.w  ccr,-(sp)
        movem.l d0-d3,-(sp)
        move.l  #snd_silence,d0                 ; 00025DEF
        moveq   #2,d1                           ; 00025DF4
        moveq   #0,d3                           ; 00025DF6
        moveq   #0,d2                           ; 00025DF8
        jsr     snd_voice                       ; 00025DFD
        movem.l (sp)+,d0-d3
        move.w  (sp)+,ccr
        rts

; The flight loop's damage announcer, once per loop iteration before the frame.
; Every 32nd iteration of [00019DE8] it walks the six damage cells from the gun
; down to the tail rotor (ecx = 6..1): a cell that has gone negative and has not
; been announced yet sets its flag and speaks the warning of the table 00019E28
; (08 04 0D 0F 0D 0E, SPEAK1 ids). Then the counter advances.
; DOS: flat 00006A68-00006AA7 (the call is 00006A99); counter [00019DE8]; flags
;   [00019E30..35] (zeroed at mission load by 0000688B); cells [00019E38..3D].
; Record: analysis/functions/sound-falcon.md#call-sites
; Port: the same walk over mission_damage and flight_announced.
; Preserved: the mask, the order ecx = 6..1, the flag set before the call.
; Difference: [00019DE8] is a counter of this loop's iterations that only this
;   routine reads (the HUD's blink reads the VBL count in its place, a recorded
;   deviation in hud.s); the options bar being open skips the iteration, as the
;   DOS bar is a loop of its own that does not reach 00006A68.
; Kind: translated.
; Status: ported.
flight_announcer
        movem.l d0-d2/a0-a2,-(sp)
        tst.w   menu_open
        bne     .out
        move.l  flight_iteration,d0
        andi.l  #$1f,d0                         ; 00006A68 test [00019DE8],0x1F
        bne     .count
        moveq   #6,d1                           ; 00006A74 ecx = 6
        lea     flight_announced,a0
        lea     mission_damage,a1
        lea     announcer_ids,a2
.cell
        tst.b   -1(a0,d1.w)                     ; 00006A79 [ecx + 00019E2F], flags 1..6 at 00019E30
        bne     .next                           ; 00006A80
        tst.b   -1(a1,d1.w)                     ; 00006A82 [ecx + 00019E37], cells 0..5 at 00019E38
        bpl     .next                           ; 00006A89 jns
        move.b  #1,-1(a0,d1.w)                  ; 00006A8B
        moveq   #0,d0
        move.b  -1(a2,d1.w),d0                  ; 00006A92 [ecx + 00019E27], ids at 00019E28
        jsr     snd_speech_a                    ; 00006A99
.next
        subq.w  #1,d1                           ; 00006A9F loop
        bne     .cell
.count
        addq.l  #1,flight_iteration             ; 00006AA1
.out
        movem.l (sp)+,d0-d2/a0-a2
        rts

; 0000688B-00006894: the six announcement flags start every mission clear.
; DOS: flat 0000688B-00006894.
; Record: analysis/functions/sound-falcon.md#call-sites
flight_announcer_reset
        clr.l   flight_announced
        clr.w   flight_announced+4
        rts

; The sound half of a mission load: the announcement flags (0000688B) and the
; three sample banks (000064A8, 0000681D, 00006859).
; DOS: flat 0000688B-00006894, 000064A8, 0000681D, 00006859.
; Record: analysis/functions/sound-falcon.md#call-sites
; Port: flight_announcer_reset, then snd_banks_load.
; Kind: translated.
flight_mission_sound_load
        bsr     flight_announcer_reset
        jsr     music_theme_load                ; 000067EE-00006806: [00019E8C]
        jmp     snd_banks_load

; The sound half of a mission start, after the first frame is up: the settings
; applied (a MODE call, which resets the slots), the rotor switch, and the
; mission-start voice, with the mission music between them (00006A00).
; DOS: flat 000069DB-00006A0E.
; Record: analysis/functions/sound-falcon.md#call-sites
; Port: snd_apply_settings (000069DB), flight_rotor (000069E0), music_theme_start
;   (000069EF-00006A00), SPEAK1 id 6 (00006A0C-00006A0E).
; Kind: translated.
flight_mission_sound_start
        jsr     snd_apply_settings              ; 000069DB
        bsr     flight_rotor                    ; 000069E0
        jsr     music_theme_start               ; 000069EF-00006A00
        SndSpeechA 6                            ; 00006A0C-00006A0E: the mission-start voice
        rts

; 00019E28: which spoken warning each damage cell has (SPEAK1 ids), cell 0 first:
; tail rotor, engine, target select, rocket launcher, target lock, gun.
announcer_ids
        dc.b    $08,$04,$0d,$0f,$0d,$0e
        even

        bss
        even
; [00019CB8]/[00019CBC], the movement core's own sin/cos of the flight
; heading. view_select's camera placement is their reader.
flt_pub_sin
        ds.l    1
flt_pub_cos
        ds.l    1
flt_x
        ds.l    1
flt_y
        ds.l    1
flt_angle
        ds.l    1
flt_turn
        ds.l    1
flt_fwd
        ds.l    1
flt_lat
        ds.l    1
flt_roll
        ds.l    1
flt_pitch
        ds.l    1
flt_maxspd
        ds.l    1
flt_prevalt
        ds.b    1
        even
flt_frame_x
        ds.l    1
flt_frame_y
        ds.l    1
flt_axis1
        ds.w    1
flt_axis2
        ds.w    1
flt_collective
        ds.b    1
flt_collective_prev
        ds.b    1
flt_torque
        ds.b    1
        even
flt_fuel
        ds.l    1
flt_mission_end
        ds.w    1
; [00019E48]: the wreck's countdown, [00019DC4]: how far its screen has sunk.
flt_death_timer
        ds.b    1
        even
flt_crash_drop
        ds.l    1
flt_trig1
        ds.b    1
flt_trig2
        ds.b    1
        even
; [00019DE8]: flight loop iterations since the start, and [00019E30..35]: which
; damage warnings have been spoken.
flight_iteration
        ds.l    1
flight_announced
        ds.b    6
        even

        end
