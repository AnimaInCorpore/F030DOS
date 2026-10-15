; Route: analysis/functions/falcon-attract.md#attract-route (mission end).
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; The mission-end statistics, 00028261, and the score screen text they fill.
;
; 0002873D is where every way of ending a flight lands - the abort key
; (000189F2), an empty tank (00018E23), a wreck (00018EF6) and the options bar's
; Abort Mission (00026E09). It silences the sound, calls 00028261 below, clears
; the object table and goes back to the attract (00005690), the main menu
; (00005AE3) or the debrief at 00028A1F. 00028261 is where the result is
; decided: how many of the '*' goal objects are gone, how much hull and fuel and
; how many weapons are left, the score those add up to, and which of the seven
; sentences at 000284B1 tells the player how it went.

        include "inc/comanche.s"
        xref    snd_mode, snd_reset

        global  mission_stats, debrief_buf, debrief_score, debrief_goals
        global  debrief_enemies_alive, debrief_last_pct, debrief_goals_done
        global  debrief_enemy_kills
        xref    object_table, flt_fuel, mission_fuel, weapon_ammo, mission_loadout
        xref    mission_wounded, mission_wounded_max, mission_target_count
        xref    ally_wrecked, debrief_text
        xref    key_state, flt_mission_end, exit_requested
        xref    music_resend, music_menu_enter
        xref    object_clear_active, attract_active, attract_next_pass
        xref    hud_variant_x, hud_variant_y
        xref    flt_shake_phase, flt_shake_timer, flt_crash_drop
        xref    roster_buffer, menu_screen_text
        xref    screen_mission_star, screen_enter
        global  input_session_keys, mission_end, mission_flown, debrief_won
        global  roster_save, roster_select_mission, pilot_locate, debrief_number
        global  roster_sort, debrief_pilot

; Offsets into debrief_text, which starts at 000284B1: the seven 0x2F-byte
; messages, then the score screen at 000285FA.
DB_MSG_SUCCESS     = $284B1-$284B1
DB_MSG_ABORTED     = $284E0-$284B1
DB_MSG_RUBBLE      = $2850F-$284B1
DB_MSG_DEFEAT      = $2853E-$284B1
DB_MSG_NO_WINGMAN  = $2856D-$284B1
DB_MSG_NO_FUEL     = $2859C-$284B1
DB_MSG_SETBACK     = $285CB-$284B1
DB_MSG_LEN         = $2F
DB_SCORE           = $2860B-$284B1
DB_PCT_SURVIVED    = $28619-$284B1
DB_PCT_GOALS       = $28633-$284B1
DB_PCT_ENEMIES     = $28653-$284B1
DB_PCT_WEAPONS     = $2866D-$284B1
DB_PCT_FUEL        = $28687-$284B1
DB_MESSAGE         = $286A1-$284B1
DB_SCREEN          = $285FA-$284B1
SCR_ID_DEBRIEF     = 5                          ; screen.s
DEBRIEF_BYTES      = 584                        ; $284B1 up to the 0xFF at $286F8
DB_OBJECTS         = 30                         ; the allocator's slots

; The roster is the DOS file: its dwords are little-endian.
BSWAP   macro
        ror.w   #8,\1
        swap    \1
        ror.w   #8,\1
        endm

        text

; Add d0 to the little-endian dword at (a0).
roster_add32
        move.l  d1,-(sp)
        move.l  (a0),d1
        BSWAP   d1
        add.l   d0,d1
        BSWAP   d1
        move.l  d1,(a0)
        move.l  (sp)+,d1
        rts

; One percentage, 000286F9: 100 * ebx / edx (100 when the total is zero), added
; to the running score, kept in [0002825C], and written right-justified into the
; three-character field at edi - 0xFD for each leading blank, so the text engine
; draws a space - by the `div cl` pair at 0002871E/0002872C. Only the low byte
; of the percentage reaches those two divides: 0002871C clears ah, not eax.
; In: d1 = total (edx), d2 = count (ebx), a1 = the field (edi).
; DOS: flat 000286F9-0002873C, the percentage writer.
; DOS symbol: sub_000286F9
; Record: analysis/functions/browser-attract.md#mission-end-statistics
; JS: dos-pilot.js percentField; fixtures: tools/check-falcon-debrief.py.
; Port: the same arithmetic; the score and last percentage are port variables.
; Preserved: the unsigned 32-bit product and divide, the zero-total 100, the
;   byte-wide digit extraction, and the stop at the first zero quotient.
; Kind: translated.
; Status: ported; checked against 00028261's captured buffers.
debrief_percent
        movem.l d0-d4,-(sp)
        moveq   #100,d0                         ; 000286FB
        tst.l   d1                              ; 00028700 or ebp,ebp
        beq.s   .stored
        mulu.l  d2,d0                           ; 00028704 mul ebx (edx dropped)
        divu.l  d1,d0                           ; 00028708 div ebp, edx = 0
.stored
        add.l   d0,debrief_score                ; 0002870A
        move.l  d0,debrief_last_pct             ; 00028710
        move.w  #$fdfd,(a1)                     ; 00028715
        andi.l  #$ff,d0                         ; 0002871C xor ah,ah: ax = al
        divu.w  #10,d0                          ; 0002871E div cl
        move.l  d0,d3
        swap    d3                              ; remainder
        ori.b   #$30,d3
        move.b  d3,2(a1)                        ; 00028723
        andi.l  #$ff,d0                         ; the quotient, al
        beq.s   .out                            ; 00028726
        divu.w  #10,d0                          ; 0002872C
        move.l  d0,d3
        swap    d3
        ori.b   #$30,d3
        move.b  d3,1(a1)                        ; 00028731
        andi.l  #$ff,d0
        beq.s   .out                            ; 00028734
        ori.b   #$30,d0
        move.b  d0,(a1)                         ; 0002873A
.out
        movem.l (sp)+,d0-d4
        rts

; Decimal digits of d0 into the d1 characters ending at a1 - 00028C25: from the
; last character back, one digit a pass, stopping after the pass that leaves
; the quotient zero. The characters before that are left as they were.
; In: d0 = value, d1 = width (ecx), a1 = first character (edi).
; DOS: flat 00028C25-00028C3D, the number formatter.
; DOS symbol: sub_00028C25
; Record: analysis/functions/browser-attract.md#mission-end-statistics
; JS: dos-pilot.js formatNumber; fixtures: tools/check-falcon-debrief.py.
; Port: the same loop.
; Preserved: the pass that always writes one digit, and the stop on a zero
;   quotient.
; Kind: translated.
; Status: ported.
debrief_number
        movem.l d0-d3/a1,-(sp)
        adda.w  d1,a1                           ; 00028C25 add edi,ecx
        subq.l  #1,a1                           ; 00028C27 dec edi
        subq.w  #1,d1
.digit
        moveq   #0,d2
        moveq   #10,d3
        divul.l d3,d2:d0                        ; 00028C2D clears edx: unsigned 32 / 32
        ori.b   #$30,d2                         ; 00028C31
        move.b  d2,(a1)                         ; 00028C34
        tst.l   d0                              ; 00028C36
        beq.s   .out
        subq.l  #1,a1                           ; 00028C3A
        dbra    d1,.digit                       ; 00028C3B loop
.out
        movem.l (sp)+,d0-d3/a1
        rts

; The statistics, 00028261-000284B0.
;
;   00028261  a negative fuel is zero; the hull counters step up by one - so a
;             hull byte of -1 reads zero - and are held non-negative
;   00028293  over the 30 placed objects: those still active and not of aux 3,
;             6 or 9 are the enemies left; each '*' goal object is a goal, and
;             one that is no longer active is a goal destroyed, worth 100
;   0002830B  every goal destroyed is [0002824E] and adds 1500
;   0002832C  then the percentages, in this order, each adding to the score:
;             goals, hull (and sixteen times it again), enemies killed (and
;             thirty-two each), weapons, fuel
;   00028404  the sentence: rubble if any goal fell; aborted if the hull is
;             left, or out of fuel if the tank is empty too; success if every
;             goal fell, less 1000 and the wingman's sentence if the wingman
;             was lost; defeat if the hull is gone. Copied to 000286A1.
;   0002847A  a lost hull scores nothing; the score is formatted into 0002860B
; In: nothing. Out: debrief_buf holds the patched score screen.
; DOS: flat 00028261-000284B0, the mission statistics.
; DOS symbol: sub_00028261
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same counts, order and arithmetic over the Falcon object table.
; Preserved: every comparison and the order the sentence is overridden in.
; Difference: the screen text is copied from debrief_text into debrief_buf each
;   time. The original patches it in place, but every field is rewritten whole
;   (the percent fields' two leading 0xFD, the score's 0xFC fill, the sentence's
;   0x2F bytes), so the result is the same.
; Kind: translated.
; Status: ported; checked against the original's buffers at a captured cursor.
mission_stats
        movem.l d0-d7/a0-a3,-(sp)

        ; The buffer starts as the image's text.
        lea     debrief_text,a0
        lea     debrief_buf,a1
        move.w  #DEBRIEF_BYTES/4-1,d0
.copy
        move.l  (a0)+,(a1)+
        dbra    d0,.copy

        tst.l   flt_fuel                        ; 00028261
        bpl.s   .fuel_ok
        clr.l   flt_fuel                        ; 0002826A
.fuel_ok
        addq.l  #1,mission_wounded              ; 00028274 inc [00019E40]
        addq.l  #1,mission_wounded_max          ; 0002827A inc [00019E44]
        tst.l   mission_wounded                 ; 00028280
        bpl.s   .hull_ok
        clr.l   mission_wounded                 ; 00028289
.hull_ok
        clr.l   debrief_score                   ; 00028293 [00028258]
        clr.b   debrief_goals_total             ; [0002824D]
        clr.b   debrief_goals                   ; [0002824C]
        clr.l   debrief_enemies_alive           ; [00028250]

        lea     object_table+(DB_OBJECTS-1)*OBJ_SIZE,a0
        moveq   #DB_OBJECTS-1,d7           ; 000282B5 ecx = 0x1E
.object
        tst.b   OBJ_ACTIVE(a0)                  ; 000282BA
        beq.s   .not_enemy
        move.b  OBJ_AUX(a0),d0
        cmpi.b  #9,d0                           ; 000282C3
        beq.s   .not_enemy
        cmpi.b  #6,d0                           ; 000282CC
        beq.s   .not_enemy
        cmpi.b  #3,d0                           ; 000282D5
        beq.s   .not_enemy
        addq.l  #1,debrief_enemies_alive        ; 000282DE
.not_enemy
        tst.b   OBJ_FLAG(a0)                    ; 000282E4
        beq.s   .next
        addq.b  #1,debrief_goals_total          ; 000282ED
        tst.b   OBJ_ACTIVE(a0)                  ; 000282F3
        bne.s   .next
        addq.b  #1,debrief_goals                ; 000282FC
        addi.l  #100,debrief_score              ; 00028302
.next
        lea     -OBJ_SIZE(a0),a0
        dbra    d7,.object                      ; 00028309 loop

        move.b  debrief_goals_total,d0          ; 0002830B
        cmp.b   debrief_goals,d0                ; 00028310
        seq     d0
        neg.b   d0                              ; sete al: 1 for equal
        move.b  d0,debrief_goals_done           ; 00028319 [0002824E]
        tst.b   d0                              ; 0002831E
        beq.s   .no_bonus
        addi.l  #1500,debrief_score             ; 00028322
.no_bonus

        lea     debrief_buf+DB_PCT_GOALS,a1
        moveq   #0,d1
        move.b  debrief_goals_total,d1          ; 0002832C
        moveq   #0,d2
        move.b  debrief_goals,d2                ; 00028333
        bsr     debrief_percent                 ; 0002833F
        lea     debrief_buf+DB_PCT_SURVIVED,a1
        move.l  mission_wounded_max,d1          ; 00028344
        move.l  mission_wounded,d2              ; 0002834A
        bsr     debrief_percent                 ; 00028355
        move.l  debrief_last_pct,d0             ; 0002835A
        lsl.l   #4,d0                           ; 0002835F
        add.l   d0,debrief_score                ; 00028362

        moveq   #0,d1
        move.w  mission_target_count,d1         ; 00028368 movzx edx,[00028260]
        move.l  d1,d2
        sub.l   debrief_enemies_alive,d2        ; 00028371
        move.l  d2,debrief_enemy_kills          ; 00028377 [00028254]
        move.l  d2,d0
        lsl.l   #5,d0                           ; 0002837F
        add.l   d0,debrief_score                ; 00028382
        lea     debrief_buf+DB_PCT_ENEMIES,a1
        bsr     debrief_percent                 ; 0002838D

        ; Weapons: the authored loads against what is left. The first two are
        ; counted a shift down - the gun's rounds by 7, the rockets by 3 - and
        ; the rest whole.
        lea     mission_loadout,a0
        move.l  (a0),d1
        lsr.l   #7,d1                           ; 00028398 shr edx,7
        move.l  4(a0),d0
        lsr.l   #3,d0                           ; 000283A0 shr eax,3
        add.l   d0,d1                           ; 000283A3
        add.l   8(a0),d1                        ; 000283A5 [00019D4C]
        add.l   12(a0),d1
        add.l   16(a0),d1
        add.l   20(a0),d1                       ; 000283B7 [00019D58]
        lea     weapon_ammo,a0
        move.l  (a0),d2
        lsr.l   #7,d2                           ; 000283CD shr ebx,7
        move.l  4(a0),d0
        lsr.l   #3,d0                           ; 000283D5
        add.l   d0,d2                           ; 000283D8
        add.l   8(a0),d2                        ; 000283DA, edi = 2..5
        add.l   12(a0),d2
        add.l   16(a0),d2
        add.l   20(a0),d2
        lea     debrief_buf+DB_PCT_WEAPONS,a1
        bsr     debrief_percent                 ; 000283E9

        move.l  mission_fuel,d1                 ; 000283EE [0001 9D5C]
        move.l  flt_fuel,d2                     ; 000283F4 [00019D60]
        lea     debrief_buf+DB_PCT_FUEL,a1
        bsr     debrief_percent                 ; 000283FF

        ; The sentence. Each test overrides the one before it.
        lea     debrief_text,a2
        tst.b   debrief_goals                   ; 0002840E
        beq.s   .no_rubble
        lea     DB_MSG_RUBBLE(a2),a0            ; 00028417
        bra.s   .have_default
.no_rubble
        suba.l  a0,a0
.have_default
        tst.l   mission_wounded                 ; 0002841C
        beq.s   .no_aborted
        lea     DB_MSG_ABORTED(a2),a0           ; 00028425
        tst.l   flt_fuel                        ; 0002842A
        bne.s   .no_aborted
        lea     DB_MSG_NO_FUEL(a2),a0           ; 00028433
.no_aborted
        tst.b   debrief_goals_done              ; 00028438
        beq.s   .not_won
        lea     DB_MSG_SUCCESS(a2),a0           ; 00028441
        tst.b   ally_wrecked                    ; 00028446
        beq.s   .not_won
        lea     DB_MSG_NO_WINGMAN(a2),a0        ; 0002844F
        subi.l  #1000,debrief_score             ; 00028454
        bcc.s   .not_won                        ; 0002845E jae
        clr.l   debrief_score                   ; 00028460
.not_won
        tst.l   mission_wounded                 ; 0002846A
        bne.s   .have_message
        lea     DB_MSG_DEFEAT(a2),a0            ; 00028473
.have_message
        lea     debrief_buf+DB_MESSAGE,a1
        moveq   #DB_MSG_LEN-1,d0
.message
        move.b  (a0)+,(a1)+                     ; 00028478 rep movsb
        dbra    d0,.message
        tst.l   mission_wounded                 ; 0002847A
        bne.s   .score_kept
        clr.l   debrief_score                   ; 00028483
.score_kept
        lea     debrief_buf+DB_SCORE,a1
        move.l  #$fcfcfcfc,(a1)                 ; 0002848D-0002849C
        move.l  #$fcfcfcfc,4(a1)
        move.l  debrief_score,d0                ; 0002849C
        moveq   #8,d1                           ; 000284A6 ecx = 8
        bsr     debrief_number                  ; 000284AB

        movem.l (sp)+,d0-d7/a0-a3
        rts

; The session keys, 000189C2-00018A05, as the flight loop polls them every
; iteration: with Alt held (key [000 1AA8]), A is Abort Mission - 000189F2 jumps
; to 0002873D - and Q is Exit to DOS - 000189FF to 00006B14. Alt+P, which writes
; the screen to SNAP_nnn.PCX through 000165FD, is the original's debugging
; screenshot and has no Falcon counterpart here; capture goes through Hatari.
; DOS: flat 000189C2-00018A05, the Alt-key poll.
; DOS symbol: sub_000189C2
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: the key array's held test, the two jumps as requests the main loop acts on.
; Preserved: Alt gating both keys and A taking precedence over Q.
; Difference: Alt+P is not carried (see above).
; Kind: translated.
; Status: ported; Unproven against a keyboard-driven DOS run, checked by poking
;   the key array on both machines.
input_session_keys
        lea     key_state,a0
        tst.b   KEY_ALT(a0)                     ; 000189C9 js 00018A05
        bmi.s   .out
        tst.b   KEY_A(a0)                       ; 000189EB-000189F2
        bmi.s   .not_abort
        move.w  #1,flt_mission_end              ; jns 0002873D
        rts
.not_abort
        tst.b   KEY_Q(a0)                       ; 000189F8-000189FF
        bmi.s   .out
        move.w  #1,exit_requested               ; jns 00006B14
.out
        rts

; The end of a flight, 0002873D.
;
;   0002873D  the music/sound switch-off (0002B9CF, 00004FE4, 000050B4,
;             0002BEDC): the mixer's MODE(0) here and its RESET after the
;             statistics; the music driver's two calls are not ported
;   00028772  the statistics
;   0002877C  the object table's active flags to zero
;   00028795  the target designator tables to zero
;   000287AB  in the attract cycle ([00019ED4] = 1) on to the next pass, 00005690;
;             otherwise, with no flight under way ([00019D91] = 0), to the menu
;             at 00005AE3; otherwise the pilot's record and the debrief
; In: nothing. Out: nothing.
; DOS: flat 0002873D-000287C5.
; DOS symbol: loc_0002873D
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: the same calls in the same order, minus the music driver's and the 0x0C14
;   stack reset (the port's loop does not nest).
; Preserved: the order, and the three-way choice at the end.
; Kind: translated.
; Status: ported; the attract path and the statistics are checked against the
;   original, the pilot branch below against its captured records.
mission_end
        clr.w   flt_mission_end
        jsr     music_resend                    ; 0002873D-00028743: [00019DF0]
        moveq   #0,d0
        jsr     snd_mode                        ; 0002876B-0002876D: the mixer off
        ; 0002874D-00028761: the shake's phase and countdown and the wreck's
        ; sunk screen are cleared before anything else is drawn.
        clr.l   flt_shake_phase                 ; [00019DBC]
        clr.l   flt_shake_timer                 ; [00019DC0]
        clr.l   flt_crash_drop                  ; [00019DC4]
        bsr     mission_stats                   ; 00028772
        jsr     snd_reset                       ; 00028777: the slots cleared
        bsr     object_clear_active             ; 0002877C
        clr.l   hud_variant_x                   ; 00028795-000287A6
        clr.l   hud_variant_x+4
        clr.b   hud_variant_y
        clr.b   hud_variant_y+1
        tst.w   attract_active                  ; 000287AB cmp [00019ED4],1
        beq.s   .not_attract
        bra     attract_next_pass               ; 000287B2 je 00005690
.not_attract
        tst.b   mission_flown                   ; 000287B8 cmp [00019D91],0
        bne.s   .flown
        jsr     music_menu_enter                ; 00005AE3 and the menu chain's music
        moveq   #0,d0                           ; 000287BF je 00005AE3: the menu
        jmp     screen_enter
.flown
        clr.b   mission_flown                   ; 000287C5

        ; 000287CC-000287E2: an intact hull and every goal destroyed is a win.
        tst.l   mission_wounded
        beq.s   .not_won
        tst.b   debrief_goals_done              ; 000287D5 cmp [0002824E],0
        beq.s   .not_won
        bra     pilot_record_won                ; 000287DC jne 000288ED
.not_won
        bra     pilot_record_lost               ; 000287E2

; The pilot's record after a mission that was not won, 000287E2-000288E8.
;
;   000287E2  a hull still standing (an aborted flight, or one that ran dry)
;             only has its kills added up
;   000287EF  a lost hull on a campaign not yet completed ([00029ADC + 10 * pilot
;             + campaign] clear) takes back the won flags of the mission it was
;             flown on and the one before, when those missions are gated behind
;             their predecessor ([00029F18] star), and says so
;   0002887B  the kills are added, the roster is ranked and saved, and the
;             losing picture shown
; DOS: flat 000287E2-000288E8.
; DOS symbol: loc_000287E2
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: the same arithmetic over the Falcon roster buffer.
; Preserved: the order of the tests and the two-mission setback walk.
; Kind: translated.
; Status: ported; checked against the captured abort and crash records.
pilot_record_lost
        move.b  #0,debrief_won
        bsr     pilot_locate                    ; d4 = pilot, d5 = campaign digit
        tst.l   mission_wounded                 ; 000287E2
        bne     pilot_tally
        ; 000287EF-0002880B: [29ADC + 10 * pilot + digit] = 1 skips the setback.
        lea     roster_buffer,a5
        move.w  d4,d0
        mulu.w  #10,d0
        add.w   d5,d0
        cmpi.b  #1,ROSTER_CAMPAIGN_DONE(a5,d0.w) ; 00028810
        beq     pilot_tally
        ; 00028819-00028847: the mission flag index, 100 * pilot + 10 * digit
        ; + the mission chosen last, and the gate row.
        move.w  d4,d0
        mulu.w  #100,d0                         ; 00028832
        move.w  d5,d1
        mulu.w  #10,d1                          ; 0002882E
        add.w   d1,d0
        moveq   #0,d6
        move.b  ROSTER_SELECTED(a5),d6          ; 00028840 [0002975A]
        add.w   d6,d0                           ; the flag index, eax
        moveq   #2-1,d7                         ; 0002883B ecx = 2
.setback
        lea     screen_mission_star,a0
        tst.b   0(a0,d6.w)                      ; 00028849 [ebx + 00029F18]
        beq.s   .setback_next
        tst.b   ROSTER_MISSIONS(a5,d0.w)        ; 00028852
        beq.s   .setback_next
        clr.b   ROSTER_MISSIONS(a5,d0.w)        ; 0002885B
        lea     debrief_buf+DB_MESSAGE,a1       ; 00028863-00028872: the sentence
        lea     debrief_text+DB_MSG_SETBACK,a0
        moveq   #DB_MSG_LEN-1,d2
.setback_msg
        move.b  (a0)+,(a1)+
        dbra    d2,.setback_msg
.setback_next
        subq.w  #1,d0                           ; 00028875 dec eax
        subq.w  #1,d6                           ; 00028876 dec ebx
        bmi     pilot_tally                     ; 00028877 js 0002887B
        dbra    d7,.setback                     ; 00028879 loop
pilot_tally
        ; 0002887B-00028892: the kills of this flight are added.
        lea     roster_buffer,a5
        move.w  d4,d0
        lsl.w   #2,d0
        move.l  debrief_enemy_kills,d1
        lea     ROSTER_KILLS(a5,d0.w),a0
        move.l  d1,d0
        bsr     roster_add32                    ; 00028887
        bra     pilot_record_done

; The pilot's record after a won mission, 000288ED-000289A4.
;
;   000288ED  the mission chosen last is marked won ([000297BC + 100 * pilot +
;             10 * digit + mission]) and the pilot's won count goes up
;   00028949  a mission with a promotion byte ([00029F2C + mission]) completes
;             the campaign ([00029ADC + 10 * pilot + digit]) and stamps that byte
;             into the first free or equal one of the ten bytes at the end of
;             the pilot's name record
;   000289A6  the score and kills are added
; DOS: flat 000288ED-000289F2.
; DOS symbol: loc_000288ED
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: the same arithmetic over the Falcon roster buffer.
; Preserved: the mission index read from [0002970A + 10 * pilot + digit], not
;   from [0002975A], and the search for the rank byte's place.
; Kind: translated.
; Status: ported; Unproven against a won mission on the original.
pilot_record_won
        move.b  #1,debrief_won
        bsr     pilot_locate
        lea     roster_buffer,a5
        move.w  d4,d0
        mulu.w  #10,d0
        add.w   d5,d0                           ; 00028905-0002890C ebp
        move.w  d0,d7
        moveq   #0,d6
        move.b  ROSTER_PROGRESS(a5,d0.w),d6     ; 00028930 [ebp + 0002970A] = ecx
        move.w  d4,d1
        mulu.w  #100,d1                         ; 00028927
        move.w  d5,d2
        mulu.w  #10,d2                          ; 0002891E
        add.w   d2,d1
        add.w   d6,d1                           ; 00028937
        move.b  #1,ROSTER_MISSIONS(a5,d1.w)     ; 00028939
        move.w  d4,d1
        lsl.w   #2,d1
        lea     ROSTER_COUNT(a5,d1.w),a0
        moveq   #1,d0
        bsr     roster_add32                    ; 00028940
        lea     screen_mission_next,a0
        tst.b   0(a0,d6.w)                      ; 00028949 [edi + 00029F2C]
        beq     .scored
        move.b  #1,ROSTER_CAMPAIGN_DONE(a5,d7.w) ; 00028973
        move.w  d4,d1
        mulu.w  #ROSTER_STRIDE,d1               ; 00028986
        lea     ROSTER_RANK(a5),a1
        adda.w  d1,a1                           ; 00028988 + 000295A1
        move.b  0(a0,d6.w),d3                   ; 0002898D bl
        moveq   #10-1,d2                        ; 00028993 ecx = 10
.rank
        addq.l  #1,a1                           ; 00028998
        cmpi.b  #$fc,(a1)                       ; 00028999
        beq.s   .rank_store
        cmp.b   (a1),d3                         ; 0002899E
        beq.s   .rank_store
        dbra    d2,.rank                        ; 000289A2 loop
.rank_store
        move.b  d3,(a1)                         ; 000289A4
.scored
        move.w  d4,d1
        lsl.w   #2,d1
        lea     ROSTER_SCORE(a5,d1.w),a0
        move.l  debrief_score,d0
        bsr     roster_add32                    ; 000289B2
        lea     ROSTER_KILLS(a5,d1.w),a0
        move.l  debrief_enemy_kills,d0
        bsr     roster_add32                    ; 000289BE
pilot_record_done
        ; 00028898-000288E8 / 000289CF-00028A19: the roster is ranked and
        ; saved, then the picture and the score screen follow.
        lea     roster_buffer,a5
        moveq   #0,d0
        move.b  ROSTER_CURRENT(a5),d0
        move.b  d0,debrief_pilot                ; [00027DAA] = [00029701]
        bsr     roster_sort                     ; 00029F36
        bsr     roster_save                     ; 00015D40 over 00029582
.show
        moveq   #SCR_ID_DEBRIEF,d0              ; 00028A1F
        jmp     screen_enter

; The mission just chosen from the list, 00028FE6-00029010: it becomes the
; pilot's progress byte for the campaign they are on ([0002970A + 10 * pilot +
; digit]) and the mission chosen last ([0002975A]), which the pilot record
; update reads back at the end of the flight.
; In: d0.b = the chosen row.
; DOS: flat 00028FE6-00029010.
; DOS symbol: inside loc_00028F3F
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same two stores.
; Preserved: the two destinations.
; Kind: translated.
; Status: ported.
roster_select_mission
        movem.l d0-d1/d4-d5/a0/a5,-(sp)
        move.b  d0,d1
        bsr     pilot_locate
        move.w  d4,d0
        mulu.w  #10,d0                          ; 00028FD2
        add.w   d5,d0                           ; 00028FD9
        move.b  d1,ROSTER_PROGRESS(a5,d0.w)     ; 0002900A
        move.b  d1,ROSTER_SELECTED(a5)          ; 00029010
.out
        movem.l (sp)+,d0-d1/d4-d5/a0/a5
        rts

; The selected pilot and the digit of the campaign file they are on:
; [00029701], and [00029D47 + [00029702 + pilot]] - '0'.
; Out: d4 = pilot, d5 = digit.
pilot_locate
        lea     roster_buffer,a5
        moveq   #0,d4
        move.b  ROSTER_CURRENT(a5),d4           ; 000288ED movzx ebx,[00029701]
        moveq   #0,d0
        move.b  ROSTER_CAMPAIGNS(a5,d4.w),d0    ; 000288F4
        lea     menu_screen_text+SCR_CAMPAIGN_DIGITS,a0
        moveq   #0,d5
        move.b  0(a0,d0.w),d5                   ; 000288FB
        subi.w  #$30,d5
        rts

; The roster ranked by missions won, 00029F36-0002A0AC: a selection sort that
; walks the position from the last pilot to the second, finds the pilot with
; the fewest wins among those up to it (the earliest of equals loses to the
; later: `jae` keeps the first found, scanning down) and swaps the two whole
; records - campaign byte, the ten progress and ten completion bytes, the three
; dwords, the name record and the hundred mission flags. [00027DAA] follows the
; selected pilot to wherever they land.
; DOS: flat 00029F36-0002A0A8.
; DOS symbol: sub_00029F36
; Record: analysis/functions/browser-attract.md#roster-ranking
; Port: the same passes and swaps; JS: dos-pilot.js rosterSort.
; Preserved: the strict `jb` on the key, the scan order, and the swap set.
; Kind: translated.
; Fixtures: tools/check-falcon-roster.py; 41 DOS cases on both CPU cores.
; Status: function outputs checked; whole debrief route remains Unproven.
roster_sort
        movem.l d0-d7/a0-a6,-(sp)
        lea     roster_buffer,a5
        moveq   #8,d7                           ; 00029F37 ebx = 8
.pass
        move.w  d7,d6                           ; ecx
        move.w  d7,d5                           ; eax: the position of the minimum
        subq.w  #1,d6
        beq     .sorted                         ; 00029F41
        move.w  d7,d0
        subq.w  #1,d0
        lsl.w   #2,d0
        move.l  ROSTER_COUNT(a5,d0.w),d4        ; 00029F47 esi = key[ebx]
        BSWAP   d4
.scan
        move.w  d6,d0
        subq.w  #1,d0
        lsl.w   #2,d0
        move.l  ROSTER_COUNT(a5,d0.w),d3        ; 00029F4E edi = key[ecx]
        BSWAP   d3
        cmp.l   d4,d3                           ; 00029F55
        bcc.s   .not_smaller                    ; 00029F57 jae
        move.l  d3,d4                           ; 00029F59
        move.w  d6,d5                           ; 00029F5B
.not_smaller
        subq.w  #1,d6
        bne.s   .scan                           ; 00029F5D loop
        ; Swap pilot d7 with pilot d5 (both 1-based here).
        move.w  d7,d1
        subq.w  #1,d1                           ; b = ebx - 1
        move.w  d5,d2
        subq.w  #1,d2                           ; a = eax - 1
        move.b  ROSTER_CAMPAIGNS(a5,d1.w),d0    ; 00029F5F-00029F6B
        move.b  ROSTER_CAMPAIGNS(a5,d2.w),ROSTER_CAMPAIGNS(a5,d1.w)
        move.b  d0,ROSTER_CAMPAIGNS(a5,d2.w)
        movem.w d1-d2,-(sp)
        ; 00029F75-00029FBF: the progress row, ten bytes.
        lea     ROSTER_PROGRESS(a5),a0
        moveq   #10,d3
        moveq   #10,d0                          ; 00029F84-00029FB6: two dwords and a word
        bsr     .swap_rows
        ; 00029FBD-00029FEF: the completion row, ten bytes.
        lea     ROSTER_CAMPAIGN_DONE(a5),a0
        moveq   #10,d3
        moveq   #10,d0                          ; 00029FBD-00029FEF: two dwords and a word
        bsr     .swap_rows
        movem.w (sp)+,d1-d2
        ; 00029FF8-0002A030: the three dwords.
        lsl.w   #2,d1
        lsl.w   #2,d2
        lea     ROSTER_COUNT(a5),a0
        bsr     .swap_dword
        lea     ROSTER_SCORE(a5),a0
        bsr     .swap_dword
        lea     ROSTER_KILLS(a5),a0
        bsr     .swap_dword
        lsr.w   #2,d1
        lsr.w   #2,d2
        ; 0002A039-0002A053: [00027DAA] follows the selected pilot.
        move.b  debrief_pilot,d0
        cmp.b   d2,d0
        bne.s   .not_a
        move.b  d1,debrief_pilot                ; 0002A041
        bra.s   .followed
.not_a
        cmp.b   debrief_pilot,d1                ; 0002A049
        bne.s   .followed
        move.b  d2,debrief_pilot                ; 0002A051
.followed
        ; 0002A056-0002A07D: the name record, 0x2B >> 2 = ten dwords.
        move.l  a5,a0                           ; the file start
        moveq   #ROSTER_STRIDE,d3
        moveq   #40,d0                          ; 0002A072: 43 >> 2 dwords, at stride 43
        bsr     .swap_rows
        ; 0002A07F-0002A0A6: the hundred mission flags.
        lea     ROSTER_MISSIONS(a5),a0
        moveq   #100,d3
        moveq   #100,d0                         ; 0002A09B: 100 >> 2 dwords
        bsr     .swap_rows
        subq.w  #1,d7                           ; 0002A037, and 00029F3C again
        bra     .pass
.sorted
        bsr     roster_format                   ; 0002A0AD
        movem.l (sp)+,d0-d7/a0-a6
        rts
; FUN_00029F36 helper; record: analysis/functions/browser-attract.md#roster-ranking.
; a0 = table, d3 = row stride, d0 = bytes exchanged, d1/d2 = pilots.
.swap_rows
        movem.l d0/d1/d2/a1/a2,-(sp)
        mulu.w  d3,d1
        mulu.w  d3,d2
        lea     0(a0,d1.l),a1
        lea     0(a0,d2.l),a2
        ; The ten-byte progress/completion rows include a trailing word;
        ; only the name exchange truncates its 43-byte stride to 40 bytes.
        move.w  d0,d3
        subq.w  #1,d3
.row_byte
        move.b  (a1),d0
        move.b  (a2),(a1)+
        move.b  d0,(a2)+
        dbra    d3,.row_byte
        movem.l (sp)+,d0/d1/d2/a1/a2
        rts
; a0 = the table, d1/d2 = byte offsets of the two dwords.
.swap_dword
        move.l  0(a0,d1.w),d0
        move.l  0(a0,d2.w),0(a0,d1.w)
        move.l  d0,0(a0,d2.w)
        rts

; The ranking numbers back into the name records, 0002A0AD-0002A0FE: for each
; pilot from the last, the won count's three decimal digits go to the record's
; bytes 3..5, a zero tens or hundreds digit as the blank 0xFD, and [00029701]
; takes [00027DAA].
; DOS: flat 0002A0AD-0002A0FE.
; DOS symbol: loc_0002A0AD
; Record: analysis/functions/browser-attract.md#roster-ranking
; Port: the same digits; JS: dos-pilot.js rosterRefreshRanks.
; Preserved: the blank for a zero digit even under a non-zero hundreds digit.
; Kind: translated.
; Status: ported.
roster_format
        movem.l d0-d4/a0-a1,-(sp)
        lea     roster_buffer,a1
        moveq   #8-1,d4                         ; 0002A0AD ecx = 8
.record
        move.w  d4,d0
        lsl.w   #2,d0
        move.l  ROSTER_COUNT(a1,d0.w),d0        ; 0002A0BC
        BSWAP   d0
        move.w  d4,d3
        mulu.w  #ROSTER_STRIDE,d3
        lea     0(a1,d3.w),a0                   ; the record
        moveq   #10,d1
        moveq   #0,d2
        divul.l d1,d2:d0                        ; 0002A0C5: edx = 0, unsigned 32 / 32
        ori.b   #$30,d2
        move.b  d2,5(a0)                        ; 0002A0CA
        moveq   #0,d2
        divul.l d1,d2:d0                        ; 0002A0CF: edx = 0, quotient and remainder
        ori.b   #$30,d2
        cmpi.b  #$30,d2
        bne.s   .tens
        move.b  #$fd,d2                         ; 0002A0D9
.tens
        move.b  d2,4(a0)                        ; 0002A0DB
        moveq   #0,d2
        divul.l d1,d2:d0                        ; 0002A0E0: edx = 0; native on both CPUs
        ori.b   #$30,d2
        cmpi.b  #$30,d2
        bne.s   .hundreds
        move.b  #$fd,d2                         ; 0002A0EA
.hundreds
        move.b  d2,3(a0)                        ; 0002A0EC
        dbra    d4,.record
        move.b  debrief_pilot,d0                ; 0002A0F4
        move.b  d0,ROSTER_CURRENT(a1)           ; 0002A0F9
        movem.l (sp)+,d0-d4/a0-a1
        rts

; The roster written back to COMANCHE.NAM, 00015D40: the file is created
; (truncated) and the 1,450 bytes at 00029582 written whole. A failure takes
; the original to its error exit 000164E3; the port keeps what it has in memory
; and goes on, because there is nothing a handheld Falcon session could do with
; a refusal that the roster in RAM does not already hold.
; DOS: flat 00015D40-00015DC7, file write.
; DOS symbol: sub_00015D40
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: Fcreate / Fwrite / Fclose of the same bytes.
; Preserved: create-and-truncate, one write of the whole record block.
; Difference: a failed create or short write does not stop the program.
; Kind: adapted - GEMDOS replaces INT 21h.
; Status: ported.
roster_save
        movem.l d0-d2/a0-a2,-(sp)
        clr.w   -(sp)                           ; attributes
        pea     debrief_name_roster
        move.w  #60,-(sp)                       ; Fcreate
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi.s   .out
        move.w  d0,d2
        pea     roster_buffer
        move.l  #ROSTER_BYTES,-(sp)
        move.w  d2,-(sp)
        move.w  #64,-(sp)                       ; Fwrite
        trap    #1
        lea     12(sp),sp
        move.w  d2,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp
.out
        movem.l (sp)+,d0-d2/a0-a2
        rts

        data
debrief_name_roster
        dc.b    "COMANCHE.NAM",0
        even

        bss
        even
; [00019D91]: a mission is being flown (set by game_init, cleared at its end).
mission_flown
        ds.b    1
; The debrief picks the winning picture.
debrief_won
        ds.b    1
; [00027DAA]: the pilot the ranking is tracking.
debrief_pilot
        ds.b    1
        even
; [00028250] enemies still active, [00028254] enemy targets destroyed.
debrief_enemies_alive
        ds.l    1
debrief_enemy_kills
        ds.l    1
; [00028258] the score, [0002825C] the last percentage.
debrief_score
        ds.l    1
debrief_last_pct
        ds.l    1
; [0002824C] goals destroyed, [0002824D] goals, [0002824E] all destroyed.
debrief_goals
        ds.b    1
debrief_goals_total
        ds.b    1
debrief_goals_done
        ds.b    1
        even
debrief_buf
        ds.b    DEBRIEF_BYTES
        end
