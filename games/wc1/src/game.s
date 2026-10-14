; Small fixed-point flight state. The field names mirror the responsibilities
; of the WC1 object/flight code without pretending that the DOS AI is ported.

        include "inc/wc1.s"

        xdef    game_init
        xdef    game_tick
        xdef    player_x
        xdef    player_y
        xdef    player_z
        xdef    player_heading
        xdef    player_speed
        xdef    player_altitude
        xdef    player_fuel
        xdef    player_health
        xdef    game_frame
        xdef    fire_count
        xdef    game_current_nav
        xdef    game_nav_transitions
        xdef    game_target_object
        xdef    game_service_resources
        xref    input_poll
        xref    input_events
        xref    input_mouse_dx
        xref    input_mouse_dy
        xref    exit_requested
        xref    objects_init
        xref    objects_tick
        xref    object_x
        xref    object_y
        xref    object_z
        xref    object_pitch
        xref    object_yaw
        xref    object_roll
        xref    object_speeds
        xref    object_count
        xref    object_types
        xref    object_active
        xref    objects_set_action_sphere
        xref    mission_entry_nav
        xref    mission_nav_types
        xref    mission_nav_x
        xref    mission_nav_y
        xref    mission_nav_z
        xref    mission_nav_radius
        xref    mission_nav_preload_types
        xref    resource_load_object_shape
        xref    resource_flight_service_capital
        xref    resource_flight_velocity
        xref    resource_flight_velocity_x
        xref    resource_flight_velocity_y
        xref    resource_flight_velocity_z
        xref    resource_flight_weapons_tick
        xref    resource_flight_combat_tick
        xref    resource_flight_ai_tick
        xref    resource_flight_enemy_tick
        xref    resource_flight_background_reset
        xref    resource_flight_background_tick
        xref    resource_flight_player_damage
        xref    resource_flight_combat_housekeep
        xref    resource_flight_fire
        xref    resource_flight_target_visible
        xref    resource_flight_target_distance

        text

game_init
        bsr     objects_init
        move.w  mission_entry_nav,d0
        cmpi.w  #MISSION_NAV_COUNT,d0
        bhs     .invalid_entry_nav
        move.w  d0,game_current_nav
        bra     .entry_nav_ready
.invalid_entry_nav
        move.w  #-1,game_current_nav
.entry_nav_ready
        ; The DOS three-slot policy retains the player first, then the two
        ; shape types supplied by new_sphere_shapes() for the current nav.
        ; Load all three only during mission setup, never from the VBL-critical
        ; draw path. A contact fallback remains for a sparse fixture with no
        ; valid preload descriptors.
        clr.w   d4
        tst.w   object_count
        beq     .player_shape_done
        lea     object_types,a0
        moveq   #0,d0
        move.w  (a0),d0
        bmi     .player_shape_done
        move.l  d0,-(sp)
        jsr     resource_load_object_shape
        addq.l  #4,sp
        tst.w   d0
        beq     .player_shape_done
.player_shape_done
        move.w  game_current_nav,d0
        bmi     .fallback_shapes
        moveq   #1,d7
        moveq   #0,d6
.preload_nav_shapes
        moveq   #0,d5
        move.w  game_current_nav,d5
        lsl.l   #2,d5
        move.l  d6,d3
        add.l   d3,d3
        add.l   d3,d5
        lea     mission_nav_preload_types,a0
        moveq   #0,d0
        move.w  0(a0,d5.l),d0
        bmi     .next_nav_shape
        move.l  d0,-(sp)
        jsr     resource_load_object_shape
        addq.l  #4,sp
        tst.w   d0
        beq     .next_nav_shape
        addq.w  #1,d4
.next_nav_shape
        addq.w  #1,d6
        dbra    d7,.preload_nav_shapes
        tst.w   d4
        bne     .shape_ready

.fallback_shapes
        cmpi.w  #2,object_count
        blo     .shape_ready
.preload_shapes
        moveq   #1,d6
        move.w  object_count,d7
        subq.w  #2,d7
        cmpi.w  #1,d7
        ble     .preload_count_ready
        moveq   #1,d7
.preload_count_ready
        move.l  d6,d5
        add.l   d5,d5
        lea     object_types,a0
        moveq   #0,d0
        move.w  0(a0,d5.l),d0
        move.l  d0,-(sp)
        jsr     resource_load_object_shape
        addq.l  #4,sp
        addq.w  #1,d6
        dbra    d7,.preload_count_ready
.shape_ready
        move.l  object_x,player_x
        move.l  object_y,player_y
        move.l  object_z,player_z
        ; Set_up_ship_info() maps a mission record's pitch field to the
        ; physical yaw axis. player_heading remains only the lightweight star
        ; field phase; all flight movement now uses the complete i/j/k frame.
        move.w  object_pitch,player_heading
        andi.w  #TURN_MASK,player_heading
        move.w  #6,player_speed
        tst.w   object_speeds
        ble     .speed_ready
        move.w  object_speeds,player_speed
.speed_ready
        move.w  #100,player_altitude
        move.w  #100,player_fuel
        move.w  #100,player_health
        clr.l   game_frame
        clr.w   fire_count
        clr.w   game_nav_transitions
        move.w  #-1,game_target_object
        move.w  #-1,game_resource_nav_pending
        clr.w   exit_requested
        jsr     resource_flight_background_reset
        rts

game_tick
        ; DOS house_keep_objects() collides a dynamic projectile before the
        ; frame's movement. That keeps damageCapacity-counter/2 exact for a
        ; newly fired cannon bolt, then the independent weapon pool advances.
        jsr     resource_flight_combat_tick
        move.w  resource_flight_player_damage,d1
        clr.w   resource_flight_player_damage
        tst.w   d1
        beq     .no_player_damage
        sub.w   d1,player_health
        bgt     .no_player_damage
        clr.w   player_health
.no_player_damage
        jsr     resource_flight_weapons_tick
        jsr     resource_flight_ai_tick
        ; fire() runs during the source object update before movement. The
        ; compact Falcon dispatcher keeps its recovered range/facing gate and
        ; fixed cannon salvo here; the next collision pass consumes the shot.
        jsr     resource_flight_enemy_tick
        bsr     input_poll
        move.w  input_events,d0
        addq.l  #1,game_frame

        btst    #INPUT_QUIT,d0
        beq     .not_quit
        move.w  #1,exit_requested
.not_quit
        btst    #INPUT_LEFT,d0
        beq     .not_left
        subq.w  #4,player_heading
        subq.w  #4,object_pitch
.not_left
        btst    #INPUT_RIGHT,d0
        beq     .not_right
        addq.w  #4,player_heading
        addq.w  #4,object_pitch
.not_right
        ; IKBD relative motion is accumulated for this frame. Horizontal
        ; motion follows the existing yaw/heading control; vertical motion
        ; changes the source pitch field (stored as object_yaw).
        move.w  input_mouse_dx,d1
        beq     .not_mouse_x
        add.w   d1,player_heading
        add.w   d1,object_pitch
.not_mouse_x
        move.w  input_mouse_dy,d1
        beq     .not_mouse_y
        add.w   d1,object_yaw
.not_mouse_y
        andi.w  #TURN_MASK,player_heading

        btst    #INPUT_SPEEDUP,d0
        beq     .not_faster
        cmpi.w  #20,player_speed
        bge     .not_faster
        addq.w  #1,player_speed
.not_faster
        btst    #INPUT_SLOWDOWN,d0
        beq     .not_slower
        cmpi.w  #1,player_speed
        ble     .not_slower
        subq.w  #1,player_speed
.not_slower

        btst    #INPUT_FIRE,d0
        beq     .not_fire
        ; fire_fixed_projectile_weapon() fires every enabled projectile mount
        ; in the player's source loadout. Keep its hardpoint/frame maths in C
        ; and pass one 32-bit ABI cell per scalar, right to left.
        moveq   #0,d1
        move.w  object_types,d1
        move.l  d1,-(sp)
        moveq   #0,d1
        move.w  player_speed,d1
        move.l  d1,-(sp)
        moveq   #0,d1
        move.w  object_roll,d1
        move.l  d1,-(sp)
        moveq   #0,d1
        move.w  object_yaw,d1
        move.l  d1,-(sp)
        moveq   #0,d1
        move.w  object_pitch,d1
        move.l  d1,-(sp)
        move.l  player_z,-(sp)
        move.l  player_y,-(sp)
        move.l  player_x,-(sp)
        jsr     resource_flight_fire
        lea     32(sp),sp
        add.w   d0,fire_count
.not_fire

        ; DOS fix_velocity() scales the full mission i/j/k forward axis by
        ; the 8.8 ship speed. This replaces the temporary four-sector motion
        ; and carries the player through all three 24.8 world axes.
        moveq   #0,d0
        move.w  player_speed,d0
        move.l  d0,-(sp)
        moveq   #0,d0
        move.w  object_roll,d0
        move.l  d0,-(sp)
        moveq   #0,d0
        move.w  object_yaw,d0
        move.l  d0,-(sp)
        moveq   #0,d0
        move.w  object_pitch,d0
        move.l  d0,-(sp)
        jsr     resource_flight_velocity
        lea     16(sp),sp
        move.l  resource_flight_velocity_x,d0
        add.l   d0,player_x
        move.l  resource_flight_velocity_y,d0
        add.l   d0,player_y
        move.l  resource_flight_velocity_z,d0
        add.l   d0,player_z
        ; Object slot zero is the player instantiated by prepare_mission's
        ; player path; keep it in lockstep with the Falcon input integrator.
        move.l  player_x,object_x
        move.l  player_y,object_y
        move.l  player_z,object_z
        move.l  player_y,d0
        asr.l   #FIX_SHIFT,d0
        move.w  d0,player_altitude
        bsr     game_update_action_sphere
        bsr     objects_tick
        jsr     resource_flight_background_tick
        ; replenish_shields() belongs to the post-movement half of the DOS
        ; object loop, so it remains after ship motion rather than folded
        ; into the pre-movement collision pass above.
        jsr     resource_flight_combat_housekeep
        bsr     game_update_target
        rts

; ReleaseStaleNavTarget() finds the first active nav point whose proximity
; sphere contains the player, then calls set_up_action_sphere() only when it
; differs from the current sphere. This is the original three-axis 24.8
; radius comparison now that the Falcon flight seam owns a full forward vector.
game_update_action_sphere
        movem.l d0-d7/a0-a1,-(sp)
        moveq   #0,d7
.nav
        lea     mission_nav_types,a0
        moveq   #0,d0
        move.b  0(a0,d7.w),d0
        cmpi.w  #1,d0
        bne     .next

        move.l  d7,d3
        lsl.l   #2,d3
        lea     mission_nav_x,a0
        move.l  0(a0,d3.l),d0
        sub.l   player_x,d0
        bpl     .x_positive
        neg.l   d0
.x_positive
        asr.l   #FIX_SHIFT,d0
        cmpi.l  #$7fff,d0
        bgt     .next
        move.w  d0,d1
        mulu    d1,d1

        lea     mission_nav_y,a0
        move.l  0(a0,d3.l),d0
        sub.l   player_y,d0
        bpl     .y_positive
        neg.l   d0
.y_positive
        asr.l   #FIX_SHIFT,d0
        cmpi.l  #$7fff,d0
        bgt     .next
        move.w  d0,d2
        mulu    d2,d2
        add.l   d2,d1
        bcs     .next

        lea     mission_nav_z,a0
        move.l  0(a0,d3.l),d0
        sub.l   player_z,d0
        bpl     .z_positive
        neg.l   d0
.z_positive
        asr.l   #FIX_SHIFT,d0
        cmpi.l  #$7fff,d0
        bgt     .next
        move.w  d0,d2
        mulu    d2,d2
        add.l   d2,d1
        bcs     .next

        move.l  d7,d2
        add.l   d2,d2
        lea     mission_nav_radius,a0
        moveq   #0,d0
        move.w  0(a0,d2.l),d0
        mulu    d0,d0
        cmp.l   d0,d1
        bgt     .next

        cmp.w   game_current_nav,d7
        beq     .done
        move.w  d7,d0
        bsr     objects_set_action_sphere
        move.w  d7,game_current_nav
        jsr     resource_flight_background_reset
        ; Nav-local records were rebuilt, so an old active-slot index cannot
        ; be retained as a target even if the compact roster still has it.
        move.w  #-1,game_target_object
        addq.w  #1,game_nav_transitions
        move.w  d7,game_resource_nav_pending
        bra     .done
.next
        addq.w  #1,d7
        cmpi.w  #MISSION_NAV_COUNT,d7
        blo     .nav
.done
        movem.l (sp)+,d0-d7/a0-a1
        rts

; Compact source check_target() subset. The full cockpit path first retains a
; current visible target; only when it has left the 3Space target list does it
; choose the nearest visible enemy, falling back to any visible contact.
; game_target_object is an active object-slot index (or -1), not a mission
; record index, exactly like g_acShipTarget_0059ce60[0].
game_update_target
        movem.l d0-d7/a0-a1,-(sp)
        move.w  game_target_object,d6
        cmpi.w  #1,d6
        blt     .find
        cmp.w   object_count,d6
        bge     .find
        lea     object_active,a0
        tst.b   0(a0,d6.w)
        beq     .find
        move.l  d6,d1
        add.l   d1,d1
        lea     object_types,a0
        cmpi.w  #21,0(a0,d1.l)
        bgt     .find
        bsr     game_target_visible
        tst.w   d0
        bne     .done
.find
        moveq   #-1,d5                 ; nearest visible contact
        moveq   #-1,d4                 ; nearest visible hostile
        move.l  #-1,d3                 ; nearest-contact distance
        move.l  #-1,d2                 ; nearest-hostile distance
        moveq   #1,d7
.candidate
        cmp.w   object_count,d7
        bge     .choose
        lea     object_active,a0
        tst.b   0(a0,d7.w)
        beq     .next_candidate
        move.l  d7,d1
        add.l   d1,d1
        lea     object_types,a0
        cmpi.w  #21,0(a0,d1.l)
        bgt     .next_candidate
        move.w  d7,d6
        bsr     game_target_visible
        tst.w   d0
        beq     .next_candidate
        move.l  resource_flight_target_distance,d0
        tst.w   d5
        bmi     .set_contact
        cmp.l   d3,d0
        bge     .contact_ready
.set_contact
        move.w  d7,d5
        move.l  d0,d3
.contact_ready
        move.l  d7,d1
        add.l   d1,d1
        lea     object_sides,a0
        move.w  0(a0,d1.l),d1
        lea     object_sides,a1
        cmp.w   (a1),d1
        beq     .next_candidate
        tst.w   d4
        bmi     .set_hostile
        cmp.l   d2,d0
        bge     .next_candidate
.set_hostile
        move.w  d7,d4
        move.l  d0,d2
.next_candidate
        addq.w  #1,d7
        bra     .candidate
.choose
        tst.w   d4
        bmi     .no_hostile
        move.w  d4,game_target_object
        bra     .done
.no_hostile
        move.w  d5,game_target_object
.done
        movem.l (sp)+,d0-d7/a0-a1
        rts

; In: d6.w active mission object index. Out: d0.w non-zero if the contact is
; within check_target()'s 12,000-unit visible list; the C helper publishes its
; 24.8 distance for the nearest-contact comparison above.
game_target_visible
        movem.l d2-d5/a0-a1,-(sp)
        move.l  d6,d5
        lsl.l   #2,d5
        lea     object_x,a0
        move.l  0(a0,d5.l),d0
        sub.l   player_x,d0
        lea     object_y,a0
        move.l  0(a0,d5.l),d1
        sub.l   player_y,d1
        lea     object_z,a0
        move.l  0(a0,d5.l),d2
        sub.l   player_z,d2
        moveq   #0,d3
        move.w  object_roll,d3
        move.l  d3,-(sp)
        moveq   #0,d3
        move.w  object_yaw,d3
        move.l  d3,-(sp)
        moveq   #0,d3
        move.w  object_pitch,d3
        move.l  d3,-(sp)
        move.l  d2,-(sp)
        move.l  d1,-(sp)
        move.l  d0,-(sp)
        jsr     resource_flight_target_visible
        lea     24(sp),sp
        move.w  d0,d6
        movem.l (sp)+,d2-d5/a0-a1
        move.w  d6,d0
        rts

; Called at IPL 3 by main.s after the masked state update. The VBL trampoline
; protects its foreground register context while C/GEMDOS fills the two
; nav preload slots and re-affirms the player slot for the next action sphere.
; No packet load occurs from
; render_frame or the VBL handler itself.
game_service_resources
        movem.l d0-d7/a0,-(sp)
        jsr     resource_flight_service_capital
        move.w  game_resource_nav_pending,d7
        bmi     .done
        move.w  #-1,game_resource_nav_pending
        cmpi.w  #MISSION_NAV_COUNT,d7
        bhs     .done
        moveq   #1,d6
        moveq   #0,d5
.preload
        move.l  d7,d3
        lsl.l   #2,d3
        move.l  d5,d2
        add.l   d2,d2
        add.l   d2,d3
        lea     mission_nav_preload_types,a0
        moveq   #0,d0
        move.w  0(a0,d3.l),d0
        bmi     .next
        move.l  d0,-(sp)
        jsr     resource_load_object_shape
        addq.l  #4,sp
.next
        addq.w  #1,d5
        dbra    d6,.preload
.player
        tst.w   object_count
        beq     .done
        lea     object_types,a0
        moveq   #0,d0
        move.w  (a0),d0
        bmi     .done
        move.l  d0,-(sp)
        jsr     resource_load_object_shape
        addq.l  #4,sp
.done
        movem.l (sp)+,d0-d7/a0
        rts

        bss
        even
player_x        ds.l    1
player_y        ds.l    1
player_z        ds.l    1
player_heading  ds.w    1
player_speed    ds.w    1
player_altitude ds.w    1
player_fuel     ds.w    1
player_health   ds.w    1
game_frame      ds.l    1
fire_count      ds.w    1
game_current_nav ds.w   1
game_nav_transitions ds.w 1
game_target_object ds.w 1
game_resource_nav_pending ds.w 1

        end
