; Route: analysis/functions/falcon-attract.md#attract-route.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; First playable Falcon-side loop. The 68030 owns input, flight state,
; terrain composition, HUD, and the VBL-paced buffer exchange. The CPU
; renderer is the correctness reference for the later DSP span path.

        include "inc/comanche.s"

        xref    snd_init, snd_apply_settings, flight_announcer

        global  main
        global  work_screen, display_screen, frame_count
        global  render_frame_path
    ifne USE_DSP
        global  terrain_begin, terrain_finish
    endc

        text

; DOS: flat 00001538-000018D3, post-bootstrap game entry boundary.
; DOS symbol: inside sub_00001510
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: TOS/Falcon coordinator loads original resources and runs the loop.
; Preserved: resource failure stops; attract/demo and frame order stay explicit.
; Kind: translated.
; Status: ported; emulator startup/capture validation remains pending.
main
        ; 0000554F-000055AF: COMANCHE.CFG, the sound card probe, MODE($FF) and
        ; RATE(2) come before the campaign catalog and the menu file.
        jsr     snd_init

        ; 0000561F builds the campaign catalog before anything else reads a
        ; mission: it is what turns a roster's campaign byte into a filename.
        bsr     screen_fill_campaigns

        ; DOS 00005624-0000568B sets the display mode, installs the retrace
        ; boundary, reads COMANCHE.NAM and COMANCHE.MNU, and only then enters
        ; 00005690. The mode/VBL work belongs to start.s/vbl.s on Falcon; the
        ; two file-backed tables remain in this same order.
        bsr     screen_roster_load
        bsr     menu_init

        ; 00005690 loads each attract resource at the state that consumes it.
        ; The Falcon decodes the reusable SG banks once before that state
        ; machine starts, because GEMDOS file I/O cannot be hidden inside the
        ; VBL-paced compositor. This is a storage/scheduling exception only;
        ; no mission, map, sky or flight state is selected here.
        bsr     sprite_init
        tst.w   sprite_bank_status
        bne     .done
        tst.l   sprite_model
        beq     .done
        tst.w   instrument_status
        bne     .done
        tst.w   hud_status
        bne     .done
        bsr     console_init
        tst.w   console_status
        bne     .done
        ; DOS startup seeds the authored console variant before entering the
        ; attract loop. Keep the value in BSS and make the initialization
        ; explicit so the CPU-only build has no initialized-BSS relocation.
        move.b  #1,hud_console_variant

        ; 00005690 owns the first visible frame. attract_start enters its
        ; fanfare/title state and paints both Falcon buffers through the
        ; platform surface replacement, so no synthetic mission frame is
        ; rendered before the DOS attract flow.
        ; Startup has completed its non-reentrant setup; the original has
        ; interrupts live before this state loop so VBL owns the published
        ; surface while the attract state is painting.
        ; 0000568B: the sound settings are applied once before the state machine
        ; at 00005690, whose first act is MODE(0).
        jsr     snd_apply_settings
        move    #$2300,sr
        bsr     attract_start
        tst.w   exit_requested
        bne     .done
        move.l  frame_count,last_frame
.loop
        ; One update/render is scheduled per completed loop, normally after the
        ; next VBL. This keeps the producer from recycling the scanout buffer
        ; while VIDEL is reading it and preserves one DOS tick per frame.
        ; Wait for the next VBL, but bounded. If the VBL vector never fires -
        ; which is exactly what a mis-installed handler or an emulator option
        ; looks like - the loop must still run and still publish a surface,
        ; rather than hanging with a blank screen and no way to tell why.
.wait_vbl
        move.l  #VBL_WAIT_LIMIT,d1
.spin
        move.l  frame_count,d0
        cmp.l   last_frame,d0
        bne     .got_vbl
        subq.l  #1,d1
        bne     .spin
.got_vbl
        ; DOS advances input, demo playback and flight once per frame before
        ; waiting for the next retrace. Elapsed VBLs are not a simulation
        ; multiplier and are not painted into the game surface.
        move.l  d0,last_frame

        ; Screen states of the attract cycle paint the visible buffer
        ; directly and skip the flight frame entirely; its demo states
        ; return zero and fall through to the normal frame, with the
        ; recorded inputs arriving through game_tick.
        bsr     attract_frame
        tst.w   d0
        bne     .loop

        ; The list menu owns the machine the same way an attract screen does:
        ; it paints and takes input, and the flight frame does not run behind
        ; it. 00006A13's loop head makes the same choice, re-entering 00005AE3
        ; rather than falling into the frame driver.
        bsr     screen_frame
        tst.w   d0
        beq     .no_menu
        move.l  work_screen,d0
        move.l  display_screen,work_screen
        move.l  d0,display_screen
        bsr     publish_screen
        bra     .loop
.no_menu

        ; 000189C2 polls the Alt keys at the top of every iteration, and a
        ; flight that has ended inside the frame (an empty tank, 00018E23)
        ; lands in the same place, 0002873D. Either way the iteration is
        ; abandoned: nothing of it renders or publishes.
        bsr     input_session_keys
        tst.w   exit_requested
        bne     .done
        tst.w   flt_mission_end
        beq     .no_end
        bsr     mission_end
        bra     .loop
.no_end

        ; 00006A68-00006AA7: the damage announcer and the loop's iteration count,
        ; at the head of each flight loop iteration.
        jsr     flight_announcer

        ; One game frame, in the order the original runs it. The sequence -
        ; and the reasons the two DOS steps that cannot be reproduced literally
        ; are placed where they are - lives in frame.s next to its DOS origin,
        ; rather than being spelled out here where the VBL pacing would bury it.
        ; The DOS surface is persistent but single-buffered. Before a replay
        ; frame starts, restore the terrain-only history into the physical work
        ; buffer. The published buffer is post-cockpit/HUD and is not a valid
        ; terrain source.
        bsr     frame_driver
        tst.w   exit_requested
        bne     .done
        tst.w   flt_mission_end                 ; 00018E23 / 00018EF6 inside the tick
        beq     .frame_ok
        bsr     mission_end
        bra     .loop
.frame_ok

        ; 00006AF4 pops the key FIFO right after 00006AEE's call to the frame
        ; driver returns, and dispatches a non-zero pop to 0001959F in the
        ; same loop iteration as the record that supplied it. This is that
        ; position. It is not inside frame_driver because 0001959F's view
        ; cases call the frame driver themselves - twice - and 00019674's
        ; console path calls 000073D0 straight away, so both still show on
        ; this frame: the dispatch is ahead of the flip below.
        moveq   #0,d0
        move.b  demo_key,d0
        beq     .no_command                     ; 00006B01 `or al,al / je`
        clr.b   demo_key
        bsr     game_command
.no_command

        ; 00006AF4-00006AFD: the live keys. The key interrupt pushes each make
        ; code into the low byte of [00001B70] (key_queue); the loop pops the
        ; newest one a frame and hands it to the same command chain the
        ; replay's keys go through. Not while a replay flies - any key leaves
        ; the attract before it could matter.
        tst.w   demo_active
        bne.s   .no_live_key
        tst.w   menu_open                       ; the bar is its own loop in the original
        bne.s   .no_live_key
        move.w  sr,-(sp)
        ori.w   #$0700,sr                       ; the ISR writes it too
        move.l  key_queue,d0
        move.l  d0,d1
        lsr.l   #8,d1
        move.l  d1,key_queue                    ; 00006AF9 shr [00001B70], 8
        move.w  (sp)+,sr
        andi.w  #$FF,d0
        beq.s   .no_live_key                    ; 00006AFE `or al,al / je`
        bsr     game_command
.no_live_key
        ; The screen shake (00019461 arms it, the timer ISR steps it) moves the
        ; DOS display window over its 328-pixel page. The port presents the
        ; same window offset in the finished frame; the margins DOS would slide
        ; over are not rendered here, which shake_present records. This used to
        ; end the run at the first bounce.
        move.l  work_screen,a0
        bsr     shake_present
        move.l  work_screen,d0
        move.l  display_screen,work_screen
        move.l  d0,display_screen
        bsr     publish_screen
        bra     .loop

.done
        rts

; Terrain by whichever path is up.
;
; The DSP is an accelerator, never a dependency: if it did not come up, or a
; frame fails mid-transfer, this falls back to the CPU renderer - which is also
; the oracle the DSP path is diffed against. A DSP frame that fails after the
; background is drawn leaves that background and the CPU pass draws over it:
; the cost of a wasted clear, against a frame missing its terrain with nothing
; saying why.
;
; In: a0 = back buffer
; DOS: flat 0000D3C0-0000D8F5, frame terrain phase.
; DOS symbol: sub_0000D3C0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: selects the CPU oracle or DSP accelerator at the machine boundary.
; Preserved: the CPU path is the DOS renderer; DSP failure falls back to it.
; Kind: translated.
; Status: ported; CPU/DSP image parity capture remains pending.
render_frame_path
    ifne USE_DSP
        movem.l d0-d1/a0-a1,-(sp)
        tst.w   dsp_status
        bne     .cpu
        bsr     render_background
        move.l  4*2(sp),a0                      ; the saved a0
        bsr     dsp_render
        tst.l   d0
        beq     .ok
.cpu
        move.l  4*2(sp),a0
        bsr     render_scene
.ok
        movem.l (sp)+,d0-d1/a0-a1
        rts
    else
        bra     render_scene
    endc

    ifne USE_DSP
; The terrain in two halves, so frame_driver can lay CPU work under the
; march - the whole of phase 3. terrain_begin paints the background and gets
; a march running; terrain_finish collects the records over that background.
; Between the two calls the caller runs everything that does not read the
; terrain pixels.
;
; Two shapes share these entry points. The default overlap launches THIS
; frame's march in begin and collects it in finish, so the terrain-independent
; CPU work between them is the cover. With DSP_PIPELINE=1, finish collects
; the march launched LAST frame and immediately launches this frame's, so the
; march's cover is the entire remaining frame - at the price of the terrain
; lagging the HUD by one more frame than the original's own deliberate skew.
;
; Either way a failure latches dsp_status and the CPU renderer takes the
; frame (and every one after it), exactly as render_frame_path does.
;
; In: a0 = back buffer.
;
; Since the incremental composition landed, begin no longer paints the
; background: the buffer already holds the static backdrop and last frame's
; terrain, and the only preparation the new frame needs is restoring the
; spans last frame's sprites covered - the terrain part of those rects is
; about to be repainted by records, the rest reverts to template. The
; silhouette repair itself rides the tops strip inside the collect.
; DOS: flat 0000D3C0-0000D8F5, terrain phase split for DSP scheduling.
; DOS symbol: sub_0000D3C0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: restores incremental Falcon surfaces and launches the DSP command.
; Preserved: background, horizon history, and frame-owned camera inputs.
; Kind: adapted - platform split.
; Status: ported; CPU reference remains the correctness path.
terrain_begin
        movem.l d0-d1/a0-a1,-(sp)
        clr.w   terrain_cpu_frame
        clr.l   dsp_record_list
        tst.w   dsp_status
        bne     .cpu
        move.l  4*2(sp),a0
        tst.w   dsp_rlist_overflow
        bne     .heal
        tst.w   surface_reseed
        beq     .incremental
.heal
        ; A spilled sprite list heals with one classic backdrop; an attract
        ; transition arms surface_reseed for two, one per buffer, and the
        ; HUD repaints the console on the same frames.
        bsr     render_background
        move.l  4*2(sp),a0
        bsr     dsp_hist_reset
        clr.w   dsp_rlist_overflow
        bra     .launch
.incremental
        bsr     dsp_restore_rects
.launch
        move.l  4*2(sp),a0
        bsr     dsp_launch
        tst.l   d0
        beq     .ok
.cpu
        ; The march never started; the reference renderer takes the whole
        ; frame now - a full classic repaint, so the buffer's silhouette
        ; history resets to match.
        move.l  4*2(sp),a0
        bsr     render_scene
        move.l  4*2(sp),a0
        bsr     dsp_hist_reset
        move.w  #1,terrain_cpu_frame
.ok
        movem.l (sp)+,d0-d1/a0-a1
        rts

; In: a0 = back buffer.
; DOS: flat 0000D3C0-0000D8F5, terrain phase completion.
; DOS symbol: sub_0000D3C0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: collects DSP terrain records or reruns the CPU renderer on failure.
; Preserved: terrain pixels are emitted once and composition stays on CPU.
; Kind: adapted - platform split.
; Status: ported; DSP parity capture remains pending.
terrain_finish
        movem.l d0-d1/a0-a1,-(sp)
        tst.w   terrain_cpu_frame
        bne     .out
        move.l  4*2(sp),a0
        bsr     dsp_collect
        tst.l   d0
        bne     .fallback
        ; Arm sprite recording into this buffer's list for the object draw
        ; pass that follows; the buffer's next frame restores what lands.
        move.l  4*2(sp),a0
        bsr     dsp_arm_rlist
        bra     .out
.fallback
        ; A failed collect latched dsp_status; the frame still needs terrain,
        ; and render_scene redraws background and march both - so the
        ; silhouette history resets with it.
        move.l  4*2(sp),a0
        bsr     render_scene
        move.l  4*2(sp),a0
        bsr     dsp_hist_reset
        move.w  #1,terrain_cpu_frame
.out
        movem.l (sp)+,d0-d1/a0-a1
        rts
    endc


; Point VIDEL at the completed surface. The VBL handler does this too, but
; doing it here as well means the display is correct even when the VBL vector
; is not being reached - the two writes are idempotent and always agree.
        global  publish_screen
; DOS: flat 00015B78-00015C14, retrace/page publication.
; DOS symbol: sub_00015B78
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: publishes the completed RGB565 buffer through Falcon VIDEL/VBL state.
; Preserved: one completed surface is presented per game frame.
; Kind: replaced.
; Status: ported; native VBL capture validation pending.
publish_screen
        ScreenCachePush
        move.b  display_screen+1,$ffff8201.w
        move.b  display_screen+2,$ffff8203.w
        move.b  display_screen+3,$ffff820d.w
        rts

        bss
        even
last_frame
        ds.l    1
; Armed by attract transitions: heal this many coming frames' surfaces (the
; screens painted over both buffers). Decremented by hud_draw, the frame's
; last consumer.
        global  surface_reseed
surface_reseed
        ds.w    1
        even
    ifne USE_DSP
; Set by terrain_begin when the CPU renderer took the whole frame, so
; terrain_finish knows there is nothing to collect and hud_draw knows the
; console needs repainting.
        global  terrain_cpu_frame
terrain_cpu_frame
        ds.w    1
        even
    endc
        end
