; Route: analysis/functions/falcon-attract.md#frame-driver.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; DOS origin: flat 0000D3C0-0000D8F5 (frame_driver)
; Purpose: sequence one game frame in the order the original runs it.
; Inputs/outputs: reads and updates the flight state in game.s; renders into
;   work_screen. Leaves the completed surface ready for the caller to publish.
; Original globals/side effects: latches [00019DFC] into [00019DF6]; copies the
;   10.22 viewer position into [00019CDC]/[00019CE0]; saves the viewpoint
;   across the terrain render and restores it afterwards. The Falcon also keeps
;   a 16.16 copy for the object compositor.
; Falcon replacement notes: see the ordering note below.
; Validation: build plus Hatari captures through the authored attract flight.
;
; The DOS order, from the recovered driver:
;
;   latch altitude into the frame-start latch
;   viewer position -> frame snapshot
;   push viewer X, Y, altitude
;   call [00019C94]        render terrain
;   call 000234A4          object update pass, tail-jumping into
;        00024B17          object transform and draw pass
;   pop  altitude, Y, X
;   call 00007AA0          surface blit to the visible page
;   call 00018D20          demo/input
;   variant-gated cockpit sprites
;
; Two of those steps cannot be reproduced literally, and the reasons matter
; more than the steps.
;
; The DOS blit publishes the terrain to VRAM and the cockpit is then drawn on
; top of the *visible* surface - single-buffered compositing. The Falcon
; composites into a back buffer and publishes it at VBL, so the cockpit has to
; be drawn before the flip rather than after it. What is preserved is the
; observable result and, more importantly, the phase: the terrain is rendered
; from the viewpoint as it stood *before* this frame's input, and the cockpit
; is drawn *after* it. The original therefore carries a deliberate one-frame
; skew between the terrain view and the HUD, and this keeps it.
;
; That is the substantive behavioural change against the previous loop, which
; polled input first and so had terrain and HUD agreeing on the same input.
;
; The recovered object update/draw stage has a counterpart at this point.
; The traced attract transition enters with authored factory records already
; installed, so replay frames execute the same object/callback/effect pass as
; DOS. Live keyboard and menu handoff remain outside this milestone.

        include "inc/comanche.s"

        global  frame_driver
        global  viewer_altitude_latched, frame_viewer_x, frame_viewer_y

        text

; DOS: flat 0000D3C0-0000D8F5, frame_driver.
; DOS symbol: sub_0000D3C0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: sequences terrain, object update/draw, input, cockpit, menu.
; Preserved: snapshot timing, one-frame input skew, and restored viewpoint.
; Kind: translated.
; Status: ported; event-only object/HUD gaps remain explicit below.
frame_driver
        ; 1. Latch the viewer altitude. The original's first instruction is
        ;    `mov al,[00019DFC] / mov [00019DF6],al`, and this was recorded as
        ;    latching the heading. It is not: 00018F29 raises [00019DFC] by 4
        ;    against a ceiling of 0xE6 and 00018FA6 lowers it by 1 against a
        ;    floor of 0xA. A heading wraps; only an altitude clamps. The object
        ;    draw prologue confirms it by differencing this against each
        ;    object's own altitude byte to get a screen row.
        moveq   #0,d0
        move.b  player_altitude,d0
        move.w  d0,viewer_altitude_latched
        move.b  d0,flt_prevalt                  ; [00019DFC] -> [00019DF6]
        move.l  flt_x,flt_frame_x              ; [00019CD4] -> [00019CDC]
        move.l  flt_y,flt_frame_y              ; [00019CD8] -> [00019CE0]

        ; 2. Snapshot the viewer position. In the original this snapshot - not
        ;    the live viewer position - is what the proximity and blast tests
        ;    compare against, so it has to be taken here and left alone for the
        ;    rest of the frame.
        move.l  player_x,frame_viewer_x
        move.l  player_y,frame_viewer_y

        ; 3. Save the viewpoint across the render. 0000D3DE pushes [00019CD4]
        ;    and [00019CD8] - the 10.22 X and Y, which are flt_x/flt_y here,
        ;    not their published 16.16 copies - and 0000D3EA pushes the
        ;    altitude byte [00019DFC]. 0000D3FC-0000D408 pops all three back
        ;    in the reverse order, so the renderer and the object pass are
        ;    free to modify them and the frame ends where it started.
        ;
        ;    This used to push player_heading, on a reading of 0000D3EA that
        ;    step 1 above had already disproved: [00019DFC] is the altitude.
        ;    The heading is not saved by the original at all.
        move.l  flt_x,-(sp)
        move.l  flt_y,-(sp)
        moveq   #0,d0
        move.b  player_altitude,d0
        move.w  d0,-(sp)
        ; The port's 16.16 copy of the same two variables. view_basis_build
        ; republishes it when an external view moves the camera, so it has to
        ; be restored with them or the helicopter would stay where the camera
        ; was left.
        move.l  player_x,-(sp)
        move.l  player_y,-(sp)

        ; 4. Terrain. On the DSP path this is two halves with the object
        ;    update pass laid between them: terrain_begin paints the
        ;    background and puts the march in flight, terrain_finish collects
        ;    the records. The update pass runs while the DSP marches - a
        ;    deliberate deviation from the DOS sequence like the two above
        ;    it, and a safe one: the pass mutates game state, not pixels, and
        ;    the terrain command's viewpoint was latched before it runs. The
        ;    CPU-only build keeps the original order exactly.
        ;    The terrain and the objects are drawn into the persistent logical
        ;    surface itself, the way DOS draws into its one surface and only
        ;    copies it - sheared, 00007AA0 - to the visible page. Until the
        ;    copy below, work_screen names that surface, so everything the
        ;    two passes draw lands on it and nothing is copied twice.
        move.l  work_screen,frame_real_work
        move.l  #terrain_history,work_screen
        move.l  work_screen,a0
    ifne USE_DSP
        bsr     terrain_begin
    else
        bsr     render_frame_path
    endc

        ; 5. Object update pass - DOS `call 000234A4`. Walks all 130 slots and
        ;    calls each active object's own state handler. The traced attract
        ;    transition has already spawned the authored records through
        ;    000068A5-00006947, including the callback/effect entries reached
        ;    by the route witness.
        ;    There is no separate reap call: the DOS original has no generic
        ;    sweep, and deactivation is each object's own state handler's job -
        ;    000237BF's active-byte clear inside object_state_wreckage, for
        ;    anything that dies the way the oil tank does.
        bsr     object_update_pass

    ifne USE_DSP
        ; The march has had the update pass as cover; take its records now,
        ; before anything draws over where they land.
        move.l  work_screen,a0
        bsr     terrain_finish
    endc

        ; 5b. Object draw stage - DOS 00024B17. Transforms every active object
        ;     into the viewer's frame, depth sorts them, and draws far to near.
        ;     It runs after the terrain and before the cockpit, which is the
        ;     only ordering that puts objects over the ground and under the
        ;     canopy, and it reads the frame viewer snapshot rather than the
        ;     live position - see object_view_transform for why that matters.
        bsr     object_draw_pass

        ; DOS keeps one surface between frames and 00007AA0 copies it to the
        ; visible page; only the cockpit at 0000D418 onward is drawn on that
        ; copy. The objects are not: 000234A4 ends in `jmp 0x24b17`, so the
        ; draw pass runs inside the same call, ahead of 0000D40E's transfer,
        ; and its pixels are part of what persists into the next frame. Store
        ; the history here rather than before the draw pass, which excluded
        ; them and was justified by a note that had the boundary in the wrong
        ; place.
        ; The window the right MFD shows when nothing is locked is taken from
        ; the unsheared surface (00007943), then 00007AA0's copy shears every
        ; row by its own displacement record into the physical buffer the
        ; cockpit is drawn on.
        bsr     render_nolock_capture
        move.l  frame_real_work,work_screen
        bsr     render_row_shear

        ; 6. Restore the viewpoint - 0000D3FC-0000D408, reverse push order.
        move.l  (sp)+,player_y
        move.l  (sp)+,player_x
        move.w  (sp)+,d0
        move.b  d0,player_altitude
        move.l  (sp)+,flt_y
        move.l  (sp)+,flt_x

        ; 7. Input and flight state. The original polls input after the blit,
        ;    so the input read here affects the terrain of the *next* frame and
        ;    the cockpit of this one.
        bsr     game_tick

        ; 7b. The replay record's key byte USED to be dispatched here. It is
        ;     not any more, and the reason is 0001959F's view cases: their
        ;     shared tail at 000196FD calls the frame driver itself, twice, so
        ;     dispatching from inside the driver would recurse. 00006AF4 pops
        ;     the FIFO right AFTER 00006AEE's call to this driver returns,
        ;     which is main.s's loop, and that is where it now happens - the
        ;     original's own position, before the buffer flip so a console page
        ;     change still shows on this frame.

        ; 0001922C-000192A3: the target latch, cycled by the select key or by
        ; the pending count the replay stream ORs in. It runs with the rest
        ; of the per-frame input handling, before anything reads the lock.
        ; 00019255 skips the whole block while [0x19D86] > 5, and 0000D418
        ; skips 0000D433's expiry the same way: an external view holds no
        ; lock, so neither the cycle nor the drop runs in variants 6 and 7.
        cmpi.b  #5,view_variant
        bhi     .no_target
        jsr     object_target_cycle

        ; 0000D433-0000D45E: the frame driver drops the lock when the locked
        ; object's targetability byte has gone to zero, so a target that
        ; leaves the screen is not still locked next frame. The designator
        ; placement that follows it there is not ported; this half is, because
        ; it is latch state rather than drawing.
        jsr     object_target_validate
.no_target

        ; 8. Cockpit and HUD, drawn after input for the reason above - and
        ;    only for console variant 1. 0000D4C4 sends anything else to
        ;    0000D8AE, whose own first test is `[0x19D86] > 5` and which
        ;    therefore returns at once for the two external views. In variants
        ;    6 and 7 the frame ends with the terrain and the objects and no
        ;    cockpit over them, which is the whole point of an outside camera.
        ;    Variants 2 to 4 reach 0000D8B7's marker restore, which is the
        ;    single-page erase this port has no counterpart for.
        cmpi.b  #1,view_variant
        bne     .no_cockpit
        bsr     hud_draw
.no_cockpit

        ; 9. The options bar over everything, when it is open. The DOS build
        ; draws it after its own cockpit pass for the same reason.
        move.l  work_screen,a1
        bsr     menu_bar_draw
        rts

        bss
        even

; The physical work buffer, while work_screen names the persistent surface.
frame_real_work
        ds.l    1

; [00019DF6] - the viewer altitude latched at frame start. Named turn_input
; until 00024C45 showed [00019DFC] to be the altitude rather than the heading.
viewer_altitude_latched
        ds.w    1
        even

; Falcon object-pass copy of the viewer position in 16.16. The flight rollback
; uses flt_frame_x/flt_frame_y for the original [00019CDC]/[00019CE0] 10.22
; contract; this second copy keeps the object compositor's surface units.
frame_viewer_x
        ds.l    1
frame_viewer_y
        ds.l    1

        end
