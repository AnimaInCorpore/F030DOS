; First-flight object instantiation.
;
; This is the Falcon equivalent of the player/initial-ship setup in
; wc1-re/src/brains.c:prepare_mission() plus the roster replacement owned by
; set_up_action_sphere(). It does not port the complete WC1 behaviour
; dispatcher yet, but preserves the important data ownership rule: object 0
; is the player, persistent initial companions follow, and nav-local records
; are rebuilt when the active sphere changes.

        include "inc/wc1.s"

        xdef    objects_init
        xdef    objects_spawn_nav
        xdef    objects_set_action_sphere
        xdef    objects_tick
        xdef    object_count
        xdef    object_types
        xdef    object_sides
        xdef    object_mission_indices
        xdef    object_x
        xdef    object_y
        xdef    object_z
        xdef    object_pitch
        xdef    object_yaw
        xdef    object_roll
        xdef    object_speeds
        xdef    object_active

        xref    mission_player_ship
        xref    mission_initial_ships
        xref    mission_entry_nav
        xref    mission_nav_types
        xref    mission_nav_triggers
        xref    mission_nav_ships
        xref    mission_ship_types
        xref    mission_ship_sides
        xref    mission_ship_nav_points
        xref    mission_ship_x
        xref    mission_ship_y
        xref    mission_ship_z
        xref    mission_ship_pitch
        xref    mission_ship_yaw
        xref    mission_ship_roll
        xref    mission_ship_speeds
        xref    mission_nav_x
        xref    mission_nav_y
        xref    mission_nav_z
        xref    resource_flight_velocity
        xref    resource_flight_velocity_x
        xref    resource_flight_velocity_y
        xref    resource_flight_velocity_z
        xref    resource_flight_combat_reset
        xref    resource_flight_combat_spawn

        text

objects_init
        clr.w   object_count
        moveq   #0,d0
        move.w  mission_player_ship,d0
        cmpi.w  #MISSION_SHIP_COUNT,d0
        bhs     .done
        moveq   #-1,d1
        bsr     object_spawn_mission
.load_entry_nav
        moveq   #0,d0
        move.w  mission_entry_nav,d0
        bsr     objects_set_action_sphere
.done
        rts

; Recreate the player companions which prepare_mission() establishes before
; entering an action sphere. They have no sphere owner, so a later nav change
; leaves them in the compact active roster while only nav-local records are
; replaced.
objects_spawn_initial
        movem.l d0-d1/d7/a0,-(sp)
        lea     mission_initial_ships,a0
        moveq   #7,d7
.initial
        moveq   #0,d0
        move.w  (a0)+,d0
        bmi     .next
        cmpi.w  #MISSION_SHIP_COUNT,d0
        bhs     .next
        cmp.w   mission_player_ship,d0
        beq     .next
        moveq   #-1,d1
        bsr     object_spawn_mission
.next
        dbra    d7,.initial
        movem.l (sp)+,d0-d1/d7/a0
        rts

; Compact Falcon counterpart of brains.c:set_up_action_sphere(). The current
; port does not yet preserve the DOS behaviour dispatcher, so it rebuilds the
; persistent player/initial roster and then adds this nav point's ten mission
; entries. This retains the DOS data lifetime: nav-local ships disappear on a
; sphere transition, while player and initial companions remain active.
; In: d0.w = nav point index.
objects_set_action_sphere
        movem.l d0-d7/a0-a1,-(sp)
        cmpi.w  #MISSION_NAV_COUNT,d0
        bhs     .done
        move.w  d0,d6
        ; set_up_action_sphere() reconstructs the compact roster.  Rebuild
        ; its source shield/armor runtime state at the same boundary, then
        ; restore object zero before adding persistent and nav-local ships.
        jsr     resource_flight_combat_reset
        lea     object_types,a0
        moveq   #0,d0
        move.w  (a0),d0
        move.l  d0,-(sp)
        clr.l   d0
        move.l  d0,-(sp)
        jsr     resource_flight_combat_spawn
        lea     8(sp),sp
        move.w  #1,object_count
        bsr     objects_spawn_initial
        move.w  d6,d0
        bsr     objects_spawn_nav
        move.w  d6,d0
        bsr     objects_apply_nav_triggers
.done
        movem.l (sp)+,d0-d7/a0-a1
        rts

; set_up_action_sphere() applies four (type,target-nav) trigger pairs after
; it has entered the new sphere. Mission data uses -1 for an unused trigger.
; In: d0.w = nav point index.
objects_apply_nav_triggers
        movem.l d0-d3/d7/a0-a1,-(sp)
        lsl.l   #3,d0
        lea     mission_nav_triggers,a0
        adda.l  d0,a0
        moveq   #3,d7
.trigger
        moveq   #0,d1
        move.b  (a0)+,d1
        moveq   #0,d2
        move.b  (a0)+,d2
        cmpi.b  #$ff,d1
        beq     .next
        cmpi.w  #MISSION_NAV_COUNT,d2
        bhs     .next
        lea     mission_nav_types,a1
        move.b  d1,0(a1,d2.w)
.next
        dbra    d7,.trigger
        movem.l (sp)+,d0-d3/d7/a0-a1
        rts

; Instantiate the ten mission records attached to one nav point. This is the
; initial subset of brains.c:set_up_action_sphere(): it makes the recovered
; nav missionShips table drive the active flight roster before wave triggers
; and the full behaviour dispatcher are ported. In: d0.w = nav point index.
objects_spawn_nav
        movem.l d1-d7/a0,-(sp)
        cmpi.w  #MISSION_NAV_COUNT,d0
        bhs     .done
        move.w  d0,d6
        mulu    #MISSION_SHIP_COUNT*2,d0
        lea     mission_nav_ships,a0
        adda.w  d0,a0
        moveq   #9,d7
.ship
        moveq   #0,d0
        move.w  (a0)+,d0
        bmi     .next
        cmpi.w  #MISSION_SHIP_COUNT,d0
        bhs     .next
        move.w  d6,d1
        bsr     object_spawn_mission
.next
        dbra    d7,.ship
.done
        movem.l (sp)+,d1-d7/a0
        rts

; In: d0.w = mission record index, d1.b = owning nav point (-1 means the
; player/initial persistent roster). Silently ignores invalid/empty slots.
object_spawn_mission
        movem.l d1-d7/a0-a2,-(sp)
        moveq   #0,d7
        move.w  object_count,d7
        moveq   #0,d5
        move.w  d0,d5
        lea     object_mission_indices,a0
        moveq   #0,d4
.existing
        cmp.w   d4,d7
        beq     .capacity
        moveq   #0,d3
        move.b  (a0)+,d3
        cmp.b   d3,d5
        beq     .done
        addq.w  #1,d4
        bra     .existing
.capacity
        cmpi.w  #FLIGHT_OBJECT_MAX,d7
        bhs     .done

        moveq   #0,d6
        move.w  d0,d6
        add.w   d6,d6
        lea     mission_ship_types,a0
        move.w  0(a0,d6.w),d1
        bmi     .done
        move.l  d7,d4
        add.l   d4,d4
        lea     object_types,a1
        move.w  d1,0(a1,d4.l)
        lea     mission_ship_sides,a0
        lea     object_sides,a1
        move.w  0(a0,d6.w),0(a1,d4.l)

        ; set_objects_data() initializes the live shield and armor arrays
        ; from ObjectTypeData. The Falcon retains those native-endian values
        ; in resources.c, indexed by this compact active slot.
        moveq   #0,d0
        move.w  d1,d0
        move.l  d0,-(sp)
        move.l  d7,d0
        move.l  d0,-(sp)
        jsr     resource_flight_combat_spawn
        lea     8(sp),sp
        move.l  d5,d0

        lea     object_mission_indices,a1
        move.b  d0,0(a1,d7.w)
        lea     object_spawn_nav_points,a1
        move.b  d1,0(a1,d7.w)
        move.l  d0,d5
        lsl.l   #2,d5
        lea     mission_ship_x,a0
        move.l  0(a0,d5.l),d1
        lea     mission_ship_y,a0
        move.l  0(a0,d5.l),d2
        lea     mission_ship_z,a0
        move.l  0(a0,d5.l),d3

        ; set_sphere_point() adds the ship offset to its mission nav position.
        lea     mission_ship_nav_points,a0
        moveq   #0,d4
        move.b  0(a0,d0.w),d4
        bmi     .store
        cmpi.w  #MISSION_NAV_COUNT,d4
        bhs     .store
        lsl.l   #2,d4
        lea     mission_nav_x,a0
        add.l   0(a0,d4.l),d1
        lea     mission_nav_y,a0
        add.l   0(a0,d4.l),d2
        lea     mission_nav_z,a0
        add.l   0(a0,d4.l),d3
.store
        move.l  d7,d4
        lsl.l   #2,d4
        lea     object_x,a0
        move.l  d1,0(a0,d4.l)
        lea     object_y,a0
        move.l  d2,0(a0,d4.l)
        lea     object_z,a0
        move.l  d3,0(a0,d4.l)

        lea     mission_ship_pitch,a0
        lea     object_pitch,a1
        move.l  d7,d4
        add.l   d4,d4
        move.w  0(a0,d6.w),0(a1,d4.l)
        lea     mission_ship_yaw,a0
        lea     object_yaw,a1
        move.w  0(a0,d6.w),0(a1,d4.l)
        lea     mission_ship_roll,a0
        lea     object_roll,a1
        move.w  0(a0,d6.w),0(a1,d4.l)
        lea     mission_ship_speeds,a0
        lea     object_speeds,a1
        move.w  0(a0,d6.w),0(a1,d4.l)
        addq.w  #1,object_count
.done
        movem.l (sp)+,d1-d7/a0-a2
        rts

; Minimal motion seam for non-player spawned records. It follows each loaded
; Set_up_ship_info orientation through the exact 24.8 fix_velocity() vector,
; while leaving WC1's manoeuvre/AI selection to the later brains.c port.
objects_tick
        movem.l d0-d7/a0-a2,-(sp)
        moveq   #0,d7
        move.w  object_count,d7
        subq.w  #2,d7
        bmi     .done
        moveq   #1,d6
.object
        lea     object_active,a0
        tst.b   0(a0,d6.w)
        beq     .next
        move.l  d6,d3
        add.l   d3,d3
        lea     object_speeds,a0
        moveq   #0,d0
        move.w  0(a0,d3.l),d0
        move.l  d0,-(sp)
        lea     object_roll,a0
        moveq   #0,d0
        move.w  0(a0,d3.l),d0
        move.l  d0,-(sp)
        lea     object_yaw,a0
        moveq   #0,d0
        move.w  0(a0,d3.l),d0
        move.l  d0,-(sp)
        lea     object_pitch,a0
        moveq   #0,d0
        move.w  0(a0,d3.l),d0
        move.l  d0,-(sp)
        jsr     resource_flight_velocity
        lea     16(sp),sp
        move.l  d6,d2
        lsl.l   #2,d2
        lea     object_x,a1
        move.l  resource_flight_velocity_x,d0
        add.l   d0,0(a1,d2.l)
        lea     object_y,a1
        move.l  resource_flight_velocity_y,d0
        add.l   d0,0(a1,d2.l)
        lea     object_z,a1
        move.l  resource_flight_velocity_z,d0
        add.l   d0,0(a1,d2.l)
.next
        addq.w  #1,d6
        dbra    d7,.object
.done
        movem.l (sp)+,d0-d7/a0-a2
        rts

        bss
        even
object_count             ds.w    1
object_types             ds.w    FLIGHT_OBJECT_MAX
object_sides             ds.w    FLIGHT_OBJECT_MAX
object_mission_indices   ds.b    FLIGHT_OBJECT_MAX
object_spawn_nav_points  ds.b    FLIGHT_OBJECT_MAX
                even
object_x                 ds.l    FLIGHT_OBJECT_MAX
object_y                 ds.l    FLIGHT_OBJECT_MAX
object_z                 ds.l    FLIGHT_OBJECT_MAX
object_pitch             ds.w    FLIGHT_OBJECT_MAX
object_yaw               ds.w    FLIGHT_OBJECT_MAX
object_roll              ds.w    FLIGHT_OBJECT_MAX
object_speeds            ds.w    FLIGHT_OBJECT_MAX
object_active             ds.b    FLIGHT_OBJECT_MAX

        end
