; Route: analysis/functions/falcon-attract.md#frame-driver (N/A - Falcon VBL platform boundary).
; Record: analysis/functions/falcon-attract.md#frame-driver
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; Falcon VBL handler. It publishes the current display buffer and provides a
; monotonically increasing frame counter for timing and diagnostics.
;
; It must chain to the handler it displaced. TOS does its own per-frame work on
; this vector, including advancing _frclock at $466, and a handler that ends in
; RTE silently stops all of it. The failure does not look like a video bug: the
; program keeps rendering until it next calls a TOS routine that waits on the
; frame clock - Bconstat/Bconin from input_poll, or the Vsync in the deinit
; path - and then blocks there forever with interrupts still enabled. Captures
; taken after that point are all the same frame, which can otherwise be
; mistaken for a stable game state.
;
; The vector is saved and restored here rather than by the startup module, so
; the saved address and the handler that returns through it are the same
; module's business and cannot be linked apart.

        include "inc/cpu.s"
        xref    snd_vbl
        global  vbl, vbl_install, vbl_remove
        global  vector_base
        global  display_screen, frame_count
        global  flight_shake_clock

VBL_VECTOR      = $70

        text

; Install the handler, remembering the vector it displaces. Supervisor only.
; DOS: flat 00015B78-00015C14, retrace boundary; Falcon vector is the platform port.
; DOS symbol: sub_00015B78
; Port: saves and installs the TOS-compatible Falcon VBL handler.
; Preserved: display publication occurs at the frame boundary and TOS chains.
; Kind: replaced.
; Status: ported; native VBL capture validation pending.
vbl_install
        move.l  a0,-(sp)
        move.l  vector_base,a0
        move.l  VBL_VECTOR(a0),saved_vbl
        move.l  #vbl,VBL_VECTOR(a0)
        ; Target artefact: Timer C source 5 uses the MFP's current vector
        ; base, not an assumed VBR=0 or MFP base=$40. Leave its 200 Hz setup
        ; and TOS acknowledgement untouched, and tail-chain the old handler.
        move.l  d0,-(sp)
        moveq   #0,d0
        move.b  $fffffa17.w,d0
        andi.w  #$f0,d0
        addq.w  #5,d0
        lsl.w   #2,d0
        adda.w  d0,a0
        move.l  a0,shake_timer_vector
        move.l  (a0),saved_shake_timer
        move.l  #shake_timer_interrupt,(a0)
        move.l  (sp)+,d0
        ScreenCachePush
        move.l  (sp)+,a0
        rts

; Put the previous handler back. Safe to call even if install never ran.
; DOS: flat 00015B78-00015C14, shutdown side of the retrace boundary.
; DOS symbol: sub_00015B78
; Port: restores the displaced TOS VBL vector safely and idempotently.
; Preserved: host interrupt ownership after the game exits.
; Kind: replaced.
; Status: ported; native teardown validation pending.
vbl_remove
        tst.l   saved_vbl
        beq     .done
        move.l  a0,-(sp)
        move.l  vector_base,a0
        move.l  saved_vbl,VBL_VECTOR(a0)
        move.l  shake_timer_vector,a0
        move.l  saved_shake_timer,(a0)
        ScreenCachePush
        move.l  (sp)+,a0
        clr.l   saved_vbl
.done
        rts

; DOS: flat 00015B78-00015C14, vsync/page-flip routine.
; DOS symbol: sub_00015B78
; Port: writes the Falcon VIDEL base, counts frames, and tail-chains TOS.
; Preserved: publication timing and monotonic frame count; VGA CRTC is replaced.
; Kind: replaced.
; Status: ported; native VBL capture validation pending.
vbl
        ; Also covers an interrupt between the buffer-pointer exchange and
        ; publish_screen. CPUSHA changes no general-purpose register.
        ScreenCachePush
        move.b  display_screen+1,$ffff8201.w
        move.b  display_screen+2,$ffff8203.w
        move.b  display_screen+3,$ffff820d.w
        addq.l  #1,frame_count

        ; Platform: the sound DMA ring's refill (src/sound.s; it keeps every register
        ; and does nothing while the mixer is off).
        jsr     snd_vbl

        ; Tail-chain: push the saved vector and return to it with the exception
        ; frame still in place, so TOS's handler sees the stack it expects and
        ; its RTE ends the interrupt. No register may be touched here, which is
        ; why the null check is a memory TST rather than a load.
        tst.l   saved_vbl
        beq     .no_chain
        move.l  saved_vbl,-(sp)
        rts
.no_chain
        rte

; DOS: N/A - platform replacement for timer ISR entry 00001D20.
; Record: analysis/functions/browser-attract.md#shake-timer
; Port: runs the rational PIT adapter independently of game rendering.
; Preserved: all registers, TOS Timer C service and its interrupt acknowledgement.
; Kind: replaced.
; Status: emulator timer/teardown check required; physical phase Unproven.
shake_timer_interrupt
        bsr     flight_shake_clock
        move.l  saved_shake_timer,-(sp)
        rts

        bss
        even
frame_count
        ds.l    1
saved_vbl
        ds.l    1
saved_shake_timer
        ds.l    1
shake_timer_vector
        ds.l    1

        end
