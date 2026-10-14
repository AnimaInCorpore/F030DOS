; Route: analysis/functions/falcon-attract.md#replay-flight.
; Source boundary: the attract's view system; CPU-only milestone.
;
; The view basis, and the two cameras that are not the cockpit.
;
; The attract does not fly from the cockpit. The DEMO streams carry the
; '1'..'7' keys in their record byte, 0001959F turns them into the view
; variant [00019D86], and 00007D25 indexes that variant into TWO tables: the
; view-angle offsets at [00019D94] and the per-variant handlers at [00007BC9].
; Measured on the original over DEMO1: variant 1 for 31 records, then 6 for
; 176, then 7 for 151, then 1 for the remaining 419. 327 of 777 records - 42%
; of the first attract pass - are flown from outside the helicopter.
;
; Variants 6 and 7 are not slope transforms like 2, 3 and 4. They MOVE THE
; VIEWPOINT, which is the reason 0000D3DE/0000D3EA push [00019CD4],
; [00019CD8] and [00019DFC] around the render and pop them back afterwards:
; the camera the frame draws from is not the helicopter, and the frame has to
; end where the helicopter is.
;
;   variant 1  the cockpit; offset 0, handler 00007BF0, a bare `ret`
;   variant 2  look left,  offset -90 degrees, 00007C00
;   variant 3  look right, offset +90 degrees, 00007C10
;   variant 4  look back,  offset 180 degrees, 00007C20
;   variant 5  offset 0, 00007C25, a bare `ret`
;   variant 6  chase camera, 00007C26
;   variant 7  fixed ground camera, 00007CC5
;   variant 8  offset 0, 00007C25
;
; The state, in the original's addresses:
;   view_variant     [00019D86]   1..7, and 0000698D seeds it with 1
;   view_angle       [00019D00]   the direction the frame LOOKS
;   view_sin/cos     [00019CB0]/[00019CB4]  its Q31 pair
;   view_slope       [00019CF8]   what the backdrop walker shears by
;   view_offset      [00019CFC]   and what it pivots around
;   view_cam_x/y     [00019CE4]/[00019CE8]  variant 7's fixed viewpoint
;   view_cam_alt     [00019DF8]   and its altitude
;
; Verified against the original 2026-09-01: work/trace_replay_flight.py
; --view-basis stops at 00007D7F, after 00007D74/00007D79 have stored the
; handler's return, and reads the whole basis once per rendered frame. A model
; of everything below reproduces the original's view angle, its sin/cos, the
; slope/offset pair and the moved camera on 169/169 variant-1 frames, 176/178
; variant-6 frames and 153/153 variant-7 frames of DEMO1 - the two variant-6
; misses being the extra 00007D25 calls view_select's own tail makes, where
; the base is the live position rather than the frame snapshot the model used.

        include "inc/comanche.s"
        xref    hud_threat_clear

        global  view_basis_build, view_select, view_variant
        global  view_angle, view_sin, view_cos, view_slope, view_offset
        global  view_cam_x, view_cam_y, view_cam_alt
        global  view_bearing_point, view_bearing_origin_x, view_bearing_origin_y

        text

; 00007D25-00007D7F. Build the frame's view basis, run the selected variant's
; handler - which may move the camera - and publish the backdrop's slope and
; offset. 0000D950 calls this as its first instruction, and view_select calls
; it twice more when the variant changes.
;
; DOS: flat 00007D25-00007D7F, view basis and per-variant handler dispatch.
; DOS symbol: sub_00007D25
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: derives the view angle, its Q31 pair, and the backdrop slope/offset.
; Preserved: the offset table, the handler table, the dispatch order, and the
;   camera moves the two external handlers make.
; Kind: translated.
; Status: ported; certified against the original's own basis at three variants.
view_basis_build
        movem.l d0-d3/a0-a1,-(sp)

        ; 00007D25/00007D2A/00007D31: the view angle is the FLIGHT angle plus
        ; the variant's own offset. view_angle_offsets is generated verbatim
        ; from the image at 00019D94 by tools/prepare-original-test.py.
        moveq   #0,d2
        move.b  view_variant,d2
        lsl.w   #2,d2
        lea     view_angle_offsets,a0
        move.l  flt_angle,d0
        add.l   0(a0,d2.w),d0                   ; 00007D31
        move.l  d0,view_angle                   ; 00007D38
        bsr     view_basis_from_angle           ; 00007D3D-00007D5B

        ; 00007D60/00007D65: the handler takes roll in eax and pitch in ecx.
        move.l  flt_roll,d0
        move.l  flt_pitch,d1
        moveq   #0,d2
        move.b  view_variant,d2
        lea     view_handlers,a0
        move.l  0(a0,d2.w*4),a1                 ; 00007D6B
        jsr     (a1)                            ; 00007D72
        move.l  d0,view_slope                   ; 00007D74
        move.l  d1,view_offset                  ; 00007D79

        ; The two external handlers moved [00019CD4]/[00019CD8]. Everything
        ; downstream of here in the original reads those live - 00024B2E and
        ; 00024C58 in the object draw stage do - so republish the port's 16.16
        ; copy of the same variable. frame_driver saves and restores it with
        ; the 10.22 pair, so the frame still ends where the helicopter is, and
        ; for variants 1 to 5 this writes back the value it already held.
        move.l  flt_x,d0
        asr.l   #6,d0
        move.l  d0,player_x
        move.l  flt_y,d0
        asr.l   #6,d0
        move.l  d0,player_y

        ; 00007D7F onward is the clamp, the shake bias and the 192-column
        ; horizon walker. They stayed in backdrop_build when only the cockpit
        ; existed; the routine boundary is here rather than in the original.
        bsr     backdrop_build
        movem.l (sp)+,d0-d3/a0-a1
        rts

; 00007D3D-00007D5B, and the identical block 00007C48-00007C66 the chase
; camera and 00007D03-00007D1B the fixed one both run: the Q31 pair of
; whatever view_angle now holds.
; DOS: flat 00007D3D-00007D5B, view sin/cos from the view angle.
; DOS symbol: inside sub_00007D25
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: reads the DOS Q31 table at the view angle's nine-bit step.
; Preserved: the >> 23 step, the +128-entry cosine, and the table itself.
; Kind: translated.
; Status: ported; certified with view_basis_build.
view_basis_from_angle
        movem.l d0-d1/a0,-(sp)
        move.l  view_angle,d0
        moveq   #23,d1
        lsr.l   d1,d0
        lsl.l   #2,d0
        lea     sine_q31,a0
        move.l  0(a0,d0.l),d1
        move.l  d1,view_sin                     ; [00019CB0]
        move.l  512(a0,d0.l),d1
        move.l  d1,view_cos                     ; [00019CB4]
        movem.l (sp)+,d0-d1/a0
        rts

; ---------------------------------------------------------------------------
; The seven handlers. Each takes d0 = roll, d1 = pitch and returns d0 = slope,
; d1 = offset, which is the original's eax/ecx contract at 00007D60/00007D74.
; ---------------------------------------------------------------------------

; 00007BF0 and 00007C25, both a bare `ret`: the cockpit takes the roll and
; pitch accumulators untransformed.
; DOS: flat 00007BF0 / 00007C25, identity view transform.
; DOS symbol: sub_00007BF0
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: leaves slope and offset as the flight's own roll and pitch.
; Preserved: the identity.
; Kind: translated.
; Status: ported; 169/169 variant-1 frames certified.
view_handler_identity
        rts

; 00007C00: `xchg ecx,eax / neg ecx / sar ecx,2 / shl eax,2`.
; DOS: flat 00007C00, the look-left slope transform.
; DOS symbol: sub_00007C00
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: slope = pitch * 4, offset = -roll / 4.
; Preserved: the exchange, the arithmetic shift, and the sign.
; Kind: translated.
; Status: ported; the attract never selects variant 2, so it is unexercised.
view_handler_left
        exg     d0,d1                           ; xchg ecx, eax
        neg.l   d1                              ; neg ecx
        asr.l   #2,d1                           ; sar ecx, 2
        asl.l   #2,d0                           ; shl eax, 2
        rts

; 00007C10: the same pair with the other sign.
; DOS: flat 00007C10, the look-right slope transform.
; DOS symbol: sub_00007C10
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: slope = -pitch * 4, offset = roll / 4.
; Preserved: the exchange, the arithmetic shift, and the sign.
; Kind: translated.
; Status: ported; the attract never selects variant 3, so it is unexercised.
view_handler_right
        exg     d0,d1
        neg.l   d0                              ; neg eax
        asr.l   #2,d1                           ; sar ecx, 2
        asl.l   #2,d0                           ; shl eax, 2
        rts

; 00007C20: `neg ecx / neg eax`.
; DOS: flat 00007C20, the look-back slope transform.
; DOS symbol: sub_00007C20
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: slope = -roll, offset = -pitch.
; Preserved: both negations.
; Kind: translated.
; Status: ported; the attract never selects variant 4, so it is unexercised.
view_handler_back
        neg.l   d1
        neg.l   d0
        rts

; 00007C26, variant 6: the chase camera.
;
; Three things, in this order. The view angle drops by four times the turn
; rate, so the camera trails a turn instead of following it. The viewpoint
; then moves 0x0F000000 - fifteen map cells in the original's 10.22 - straight
; BACK along that view, which is the negative of the flight's own
; (sin, -cos) forward axis. Finally the altitude is lifted to byte(2h + 12) if
; the ground under the new viewpoint is higher, so the camera never sinks into
; a hill it is looking over.
;
; DOS: flat 00007C26-00007CC4, the chase camera.
; DOS symbol: sub_00007C26
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: trails the view by the turn rate, pulls the camera back, clamps it up.
; Preserved: the turn * 4 lag, the 0x0F000000 step, its axis, the byte(2h+12)
;   clamp with its 0xFF saturation and its `jb` skip, and the returned pair -
;   roll survives, pitch is zeroed.
; Difference: 00007C35-00007C46 subtracts a further 0xA0000000 from the view
;   angle while the player-destroyed byte [00019E49] is set. Its only writers
;   are 000194C9's damage tail, 00023654, 000237EF and 0002444C - all in
;   handlers this milestone does not carry - so the byte is zero for every
;   frame the attract reaches, and src/flight.s already treats the same flag
;   as zero at 00019442. Carrying the branch would need state with no writer.
; Kind: translated.
; Status: ported; 176/178 DEMO1 frames certified against the original.
view_handler_chase
        movem.l d2-d4/a0,-(sp)
        move.l  d0,-(sp)                        ; 00007C26 push eax

        move.l  flt_turn,d2
        asl.l   #2,d2                           ; 00007C2C shl eax, 2
        move.l  view_angle,d3
        sub.l   d2,d3                           ; 00007C2F
        move.l  d3,view_angle
        bsr     view_basis_from_angle           ; 00007C48-00007C66

        ; 00007C6B-00007C87. The forward axis is (sin, -cos), so adding cos to
        ; Y and subtracting sin from X is fifteen cells behind the helicopter.
        move.l  #$0F000000,d0
        move.l  view_cos,d3
        MulS64  d3
        add.l   d1,flt_y                        ; 00007C76
        move.l  #$0F000000,d0
        move.l  view_sin,d3
        MulS64  d3
        sub.l   d1,flt_x                        ; 00007C87

        ; 00007C8D-00007CBB, the same ten-bit map index the flight's own
        ; terrain follow builds, at the camera rather than the helicopter.
        move.l  flt_y,d2
        moveq   #22,d3
        asr.l   d3,d2
        andi.l  #MAP_MASK,d2
        lsl.l   #8,d2
        lsl.l   #MAP_SHIFT-8,d2
        move.l  flt_x,d4
        asr.l   d3,d4
        andi.l  #MAP_MASK,d4
        add.l   d4,d2
        lea     original_height_map,a0
        moveq   #0,d3
        move.b  0(a0,d2.l),d3
        add.b   d3,d3                           ; 00007CAB shl al, 1
        addi.b  #12,d3                          ; 00007CAD add al, 0x0c
        bcc     .no_saturate                    ; 00007CAF jae
        move.b  #$ff,d3                         ; 00007CB1
.no_saturate
        sub.b   player_altitude,d3              ; 00007CB3
        bcs     .above_ground                   ; 00007CB9 jb: camera is higher
        add.b   d3,player_altitude              ; 00007CBB
.above_ground

        move.l  (sp)+,d0                        ; 00007CC1 pop eax: roll
        moveq   #0,d1                           ; 00007CC2 xor ecx, ecx
        movem.l (sp)+,d2-d4/a0
        rts

; 00007CC5, variant 7: the fixed ground camera.
;
; The viewpoint is not derived at all - it is the point view_select dropped
; when the key was pressed, ten map cells behind the helicopter and twelve
; above the ground there. The view angle is a BEARING: 000256C8's octant atan2
; from that point to object slot 31 - the fixed object that rides the
; helicopter - plus half a turn, so the camera looks back at what it is
; filming. Roll and pitch are both zeroed, which is why the horizon stays
; level in this view however the helicopter is banking.
;
; DOS: flat 00007CC5-00007D24, the fixed ground camera.
; DOS symbol: sub_00007CC5
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: substitutes the stored viewpoint and aims it at the player object.
; Preserved: the viewpoint and altitude substitution, the bearing origin copy
;   to [0002234C]/[00022350], the +0x80 half turn, the << 24, and the zeroed
;   slope and offset.
; Kind: translated.
; Status: ported; 153/153 DEMO1 frames certified against the original.
view_handler_fixed
        move.l  d2,-(sp)
        move.l  view_cam_x,d2
        move.l  d2,flt_x                        ; 00007CC5
        move.l  d2,view_bearing_origin_x        ; 00007CCF [0002234C]
        move.l  view_cam_y,d2
        move.l  d2,flt_y                        ; 00007CD4
        move.l  d2,view_bearing_origin_y        ; 00007CDE [00022350]
        move.b  view_cam_alt,player_altitude    ; 00007CE3

        bsr     view_bearing_to_player          ; 00007CED ecx=0x1F, 00007CF2
        addi.b  #$80,d0                         ; 00007CF7 add al, 0x80
        andi.l  #$ff,d0
        moveq   #24,d1
        lsl.l   d1,d0                           ; 00007CF9 shl eax, 0x18
        move.l  d0,view_angle                   ; 00007CFC
        bsr     view_basis_from_angle           ; 00007D01-00007D1B

        moveq   #0,d0                           ; 00007D20 xor eax, eax
        moveq   #0,d1                           ; 00007D22 xor ecx, ecx
        move.l  (sp)+,d2
        rts

; 000256C8 with ecx = 0x1F. The octant atan2 from [0002234C]/[00022350] to
; object slot 31, returned one's-complemented - the direction from the camera
; toward the player, in the sense the view wants.
;
; This is the original's OWN second copy of the arithmetic object_aspect
; ports from 00024C45: same octant table at 00022385, same ratio correction at
; 000223A5, different origin. It is transcribed rather than shared because DOS
; has two routines here, not one called twice.
;
; Out: d0.b = the bearing byte.
; DOS: flat 000256C8-00025726, octant bearing from the stored origin.
; DOS symbol: sub_000256C8
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: the same octant/ratio bearing against the Falcon object table.
; Preserved: the sign bits, the one's-complement magnitudes, the octant index,
;   the >> 10 ratio, the table XOR, the round, and the final NOT.
; Kind: translated.
; Status: ported; exercised through view_handler_fixed's 153/153 certification.
view_bearing_to_player
        movem.l d1-d7/a1,-(sp)
        ; Slot 31 is the fixed object. object_fixed_position owns that layout
        ; and returns its X/Y already in the original's 10.22.
        bsr     object_fixed_position           ; d6 = X, d7 = Y
        bsr     view_bearing_point
        movem.l (sp)+,d1-d7/a1
        rts

; 000256C8 itself: the bearing from the stored origin [0002234C]/[00022350]
; to a point. DOS passes the object in ecx; this takes its position.
;
; It also leaves esi = min/2 + max of the two one's-complement magnitudes
; (000256FF-00025703), a distance estimate the Hellfire state reads straight
; after the call (00024751). That is returned in d1.
;
; In:  d6 = X, d7 = Y, both 10.22. Out: d0.b = the bearing byte (upper bits
;      clear), d1.l = the distance estimate.
; DOS: flat 000256C8-00025726, octant bearing from the stored origin.
; DOS symbol: sub_000256C8
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: the same octant/ratio bearing, and the esi it leaves.
; Preserved: as view_bearing_to_player, plus the unsigned min/2 + max.
; Kind: translated.
; Status: ported; shared by the fixed camera and the Hellfire.
view_bearing_point
        movem.l d2-d7/a1,-(sp)
        moveq   #0,d4                           ; 000256D7 sets bl: Y sign
        move.l  d7,d1
        sub.l   view_bearing_origin_y,d1        ; 000256D1
        move.l  d1,d3
        bpl     .y_nonnegative
        not.l   d3                              ; 000256DA cdq / xor eax, edx
        moveq   #1,d4
.y_nonnegative

        moveq   #0,d2                           ; the X sign
        move.l  d6,d1
        sub.l   view_bearing_origin_x,d1        ; 000256E6
        move.l  d1,d5
        bpl     .x_nonnegative
        not.l   d5
        moveq   #1,d2
.x_nonnegative

        ; 000256F1/000256F5: (Ysign << 2) | (Xsign << 1), then the compare
        ; adds the "x is not greater" bit.
        move.l  d4,d1
        lsl.l   #1,d1
        or.l    d2,d1
        lsl.l   #1,d1
        cmp.l   d3,d5
        bhi     .octant_ready                   ; 000256F9 ja
        addq.l  #1,d1
        exg     d3,d5
.octant_ready
        move.l  d3,d7                           ; 000256FF esi = min
        lsr.l   #1,d7                           ; 00025701
        add.l   d5,d7                           ; 00025703 + max
        lea     object_octant_table,a1
        move.l  0(a1,d1.l*4),d1                 ; 00025705
        move.l  d5,d0
        lsr.l   #8,d0
        lsr.l   #2,d0                           ; 0002570C shr ebp, 0x0a
        beq     .no_correction                  ; 0002570F je
        move.l  d3,d5
        divu.l  d0,d5                           ; 00025715 div ebp
        lea     object_bearing_correction,a1
        moveq   #0,d0
        move.b  0(a1,d5.l),d0
        eor.b   d0,d1                           ; 00025717 xor bl, [...]
.no_correction
        addq.l  #1,d1                           ; 0002571D inc ebx
        lsr.l   #1,d1                           ; 0002571E shr ebx, 1
        move.b  d1,d0                           ; 00025722 mov al, bl
        not.b   d0                              ; 00025724 not al
        andi.l  #$ff,d0
        move.l  d7,d1                           ; esi
        movem.l (sp)+,d2-d7/a1
        rts

; ---------------------------------------------------------------------------
; The view keys.
; ---------------------------------------------------------------------------

; 0001959F's scancode cases 0x02..0x09 - the '1'..'8' keys - and the shared
; tail at 000196B4 they all end in.
;
; Each case guards on the variant already being the one requested and returns
; if so, EXCEPT 0x08, which has no guard at 0001984E and therefore re-places
; the fixed camera every time it is pressed. 0x09 tests [00019D86] against 8,
; a value nothing in the image ever writes, and then sets 7 - so the '8' key
; always re-selects variant 7 without moving its camera. Both quirks are the
; original's and are kept.
;
; In: d0.b = the scancode, 0x02..0x09.
; DOS: flat 00019689-00019907, the view cases of the in-flight command chain.
; DOS symbol: inside loc_0001959F
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: selects the view variant, its console image, and re-runs the frame.
; Preserved: the scancode-to-variant map, the per-case guards, the console
;   image each case loads, variant 7's camera placement, and the tail's two
;   extra basis builds and frame runs.
; Differences, each against the instruction it drops:
;   - 000196CF's 0001687D blit is carried by render_history_console. Its
;     partner 00016B50 (0001971A) and 00019715's 00015B78 are the VGA
;     page-pair duplication and the flip; the Falcon keeps one persistent
;     surface and publishes a linear RGB565 buffer at VBL, so they have no
;     separate counterpart.
;   - 0001970B/00019756 call 000072C4, which is not decoded. It runs only for
;     variant 1 and only on this path.
;   - DOS is single-buffered, so its two extra 0000D3C0 runs are visible in
;     turn. The Falcon composes into the back buffer and publishes once, so
;     only the last of them reaches the screen. The game state both runs
;     produce - including the two replay records they consume - is identical.
; Kind: translated.
; Status: ported; the variant/camera half is certified, the tail is not.
view_select
        movem.l d0-d2/a0,-(sp)
        moveq   #0,d1
        move.b  d0,d1
        subi.b  #2,d1
        cmpi.b  #7,d1
        bhi     .out                            ; not one of 0x02..0x09
        cmpi.b  #7,d1
        beq     .key_eight                      ; 0x09 -> 000198D8

        addq.b  #1,d1                           ; 0x02 -> variant 1, and so on
        cmpi.b  #7,d1
        beq     .place_camera                   ; 0x08 has no guard
        cmp.b   view_variant,d1
        beq     .out                            ; each other case's `je`
        bra     .take

.key_eight
        ; 000198DC: the guard tests 8, which nothing writes, so this always
        ; falls through; 000198E5 then sets 7 WITHOUT re-placing the camera.
        cmpi.b  #8,view_variant
        beq     .out
        moveq   #7,d1
        bra     .take

.place_camera
        ; 0001985B-000198B6, and it runs before the variant is even used: the
        ; camera is dropped at the helicopter's own position, ten map cells
        ; back along the flight heading, twelve above the ground under it.
        move.l  flt_y,d0
        moveq   #22,d2
        asr.l   d2,d0
        andi.l  #MAP_MASK,d0
        lsl.l   #8,d0
        lsl.l   #MAP_SHIFT-8,d0
        move.l  flt_x,d2
        asr.l   #8,d2
        asr.l   #8,d2
        asr.l   #6,d2                           ; 22, in three legal shifts
        andi.l  #MAP_MASK,d2
        add.l   d2,d0
        lea     original_height_map,a0
        moveq   #0,d2
        move.b  0(a0,d0.l),d2
        add.b   d2,d2                           ; 00019879 shl al, 1
        addi.b  #10,d2                          ; 0001987B add al, 0x0a
        bcc     .alt_ok                         ; 0001987D jae
        move.b  #$ff,d2
.alt_ok
        move.b  d2,view_cam_alt                 ; 00019881 [00019DF8]

        move.l  flt_x,view_cam_x                ; 00019886
        move.l  flt_y,view_cam_y                ; 00019890
        ; 0001989A-000198B6: ten map cells back along the pair the movement
        ; core published at 0001950F/0001951B - the FLIGHT heading's sin and
        ; cos, not the view's.
        move.l  #$2800000,d0
        move.l  flt_pub_cos,d2
        MulS64  d2
        add.l   d1,view_cam_y                   ; 000198A5
        move.l  #$2800000,d0
        move.l  flt_pub_sin,d2
        MulS64  d2
        sub.l   d1,view_cam_x                   ; 000198B6
        moveq   #7,d1

.take
        move.b  d1,view_variant
        ; Every case loads its own console image: consol1s..consol4s for
        ; variants 1..4, consol5s for 5, 6 and 7 alike.
        move.b  d1,d0
        cmpi.b  #5,d0
        bcs     .console_digit
        moveq   #5,d0
.console_digit
        jsr     console_select_variant

        ; 000196B4-0001975B, the shared tail.
        clr.w   object_target_latch             ; 000196B4 [00019D10] = 0
        ; 000196BE clears [00019D93]. The byte itself is not computed (src/hud.s
        ; keeps the sound's own copy of it, which this clears).
        jsr     hud_threat_clear
        jsr     console_palette_remap           ; 000196CA -> 0002B949
        ; 000196CF -> 0001687D: the loaded console onto the persistent page.
        ; Without this, variants 6 and 7 kept the attract title page below
        ; the view instead of consol5s.dta's banner.
        bsr     render_history_console
        bsr     view_rerun_frame                ; 000196D4-000196FD
        bsr     view_rerun_frame                ; 0001971F-00019748
.out
        movem.l (sp)+,d0-d2/a0
        rts

; One of the tail's two repeats: build the basis with the viewpoint saved and
; restored around it, then run a whole frame.
; DOS: flat 000196D4-000196FD, the tail's saved-viewpoint frame run.
; DOS symbol: inside loc_000196B4
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: repeats the basis build and the frame driver as the original does.
; Preserved: the push/pop of X, Y and altitude, and the frame that follows.
; Kind: translated.
; Status: ported; the frame it produces is not separately certified.
view_rerun_frame
        move.l  flt_x,-(sp)                     ; 000196D4
        move.l  flt_y,-(sp)                     ; 000196DA
        moveq   #0,d0
        move.b  player_altitude,d0
        move.w  d0,-(sp)                        ; 000196E0/000196E5
        bsr     view_basis_build                ; 000196E6 -> 00007D25
        move.w  (sp)+,d0                        ; 000196EB
        move.b  d0,player_altitude
        move.l  (sp)+,flt_y                     ; 000196F1
        move.l  (sp)+,flt_x                     ; 000196F7
        ; The DOS surface persists between frames because it is the only one,
        ; and frame_driver draws into that persistent surface itself, so the
        ; repeat marches over the previous pass's terrain without a restore.
        jsr     frame_driver                    ; 000196FD -> 0000D3C0
        rts

        data
        even
; [00007BC9], the per-variant handler table. Entry 0 is never indexed - the
; variant is 1..8 - and in the image its slot is the tail of the preceding
; instruction rather than a pointer, so the identity stands in for it here.
view_handlers
        dc.l    view_handler_identity           ; 0 - not reachable
        dc.l    view_handler_identity           ; 1  00007BF0
        dc.l    view_handler_left               ; 2  00007C00
        dc.l    view_handler_right              ; 3  00007C10
        dc.l    view_handler_back               ; 4  00007C20
        dc.l    view_handler_identity           ; 5  00007C25
        dc.l    view_handler_chase              ; 6  00007C26
        dc.l    view_handler_fixed              ; 7  00007CC5
        dc.l    view_handler_identity           ; 8  00007C25

        bss
        even
; [00019D86]. 0000698D seeds it with 1 - object_init does that, because the
; same instruction sits in the object-table reset there.
view_variant
        ds.b    1
; [00019DF8], variant 7's camera altitude.
view_cam_alt
        ds.b    1
        even
view_angle
        ds.l    1
view_sin
        ds.l    1
view_cos
        ds.l    1
view_slope
        ds.l    1
view_offset
        ds.l    1
view_cam_x
        ds.l    1
view_cam_y
        ds.l    1
; [0002234C]/[00022350], the bearing origin 000256C8 measures from. 00007CC5
; writes it here; 0002387C's object state is its other DOS writer and is not
; on this milestone's path.
view_bearing_origin_x
        ds.l    1
view_bearing_origin_y
        ds.l    1

        end
