; Falcon keyboard/mouse seam. TOS console input keeps desktop keyboard input
; working in Hatari. Mouse packets are delivered through the documented TOS
; Kbdvbase mouse vector; polling the ACIA directly is not reliable because TOS
; consumes those bytes from its IKBD interrupt handler first.

        include "inc/bios.s"
        include "inc/wc1.s"
        include "inc/xbios.s"

        xdef    input_poll
        xdef    input_init
        xdef    input_shutdown
        xdef    input_events
        xdef    input_mouse_dx
        xdef    input_mouse_dy
        xdef    input_mouse_buttons
        xdef    input_mouse_x
        xdef    input_mouse_y

        text

input_init
        clr.w   input_events
        clr.w   input_mouse_dx
        clr.w   input_mouse_dy
        clr.w   input_mouse_buttons
        clr.w   input_mouse_pending_dx
        clr.w   input_mouse_pending_dy
        clr.w   input_mouse_button_event
        move.w  #FRAME_WIDTH/2,input_mouse_x
        move.w  #FRAME_HEIGHT/2,input_mouse_y

        ; Save TOS's mouse packet vector before taking ownership of it. The
        ; handler is called with A0 pointing at the three-byte relative packet.
        Kbdvbase
        move.l  d0,a0
        move.l  16(a0),input_saved_mouse_vector

        ; topmode=1 makes Y=0 the top of the game surface. Thresholds of one
        ; preserve every relative packet byte as a pixel-space delta.
        move.b  #1,input_mouse_params
        clr.b   input_mouse_params+1
        move.b  #1,input_mouse_params+2
        move.b  #1,input_mouse_params+3
        Initmouse #1,input_mouse_params,input_mouse_handler
        rts

input_shutdown
        move.l  input_saved_mouse_vector,d0
        beq     .done
        move.l  d0,-(sp)
        pea     input_mouse_params
        move.w  #1,-(sp)
        move.w  #0,-(sp)
        trap    #14
        lea     12(sp),sp
        clr.l   input_saved_mouse_vector
.done
        rts

input_poll
        ; The first title poll runs with VBL interrupts enabled. Take a short
        ; IPL-7 critical section while moving the handler's pending bucket to
        ; the frame-visible bucket so a packet cannot arrive between the copy
        ; and the clear.
        move.w  sr,-(sp)
        move.w  #$2700,sr
        clr.w   input_events
        ; The interrupt handler accumulates motion while the foreground is
        ; between polls. Publish that accumulated motion as this frame's
        ; delta, then start a fresh pending bucket. The caller consumes the
        ; published values after this routine returns.
        move.w  input_mouse_pending_dx,input_mouse_dx
        move.w  input_mouse_pending_dy,input_mouse_dy
        clr.w   input_mouse_pending_dx
        clr.w   input_mouse_pending_dy
        tst.w   input_mouse_button_event
        beq     .restore_ipl
        clr.w   input_mouse_button_event
        bset    #INPUT_FIRE,input_events
.restore_ipl
        move.w  (sp)+,sr
.drain
        Bconstat #2
        tst.l   d0
        beq     .finish
        Bconin  #2
        move.l  d0,d1
        andi.w  #$00ff,d0
        move.w  d1,d2
        lsr.w   #8,d2
        ; TOS normally returns the ASCII byte in the low byte. Accept both the
        ; ASCII and scan-code forms for the control keys used by the front end
        ; and flight loop.
        cmpi.w  #28,d0
        beq     .accept
        cmpi.w  #57,d0
        beq     .fire
        cmpi.w  #1,d0
        beq     .quit
        cmpi.w  #28,d2
        beq     .accept
        cmpi.w  #57,d2
        beq     .fire
        cmpi.w  #1,d2
        beq     .quit
        cmpi.w  #'a',d0
        beq     .left
        cmpi.w  #'A',d0
        beq     .left
        cmpi.w  #'d',d0
        beq     .right
        cmpi.w  #'D',d0
        beq     .right
        cmpi.w  #'w',d0
        beq     .faster
        cmpi.w  #'W',d0
        beq     .faster
        cmpi.w  #'s',d0
        beq     .slower
        cmpi.w  #'S',d0
        beq     .slower
        cmpi.w  #' ',d0
        beq     .fire
        cmpi.w  #$0d,d0
        beq     .accept
        cmpi.w  #$1b,d0
        beq     .quit
        bra     .drain
.left
        bset    #INPUT_LEFT,input_events
        bra     .drain
.right
        bset    #INPUT_RIGHT,input_events
        bra     .drain
.faster
        bset    #INPUT_SPEEDUP,input_events
        bra     .drain
.slower
        bset    #INPUT_SLOWDOWN,input_events
        bra     .drain
.fire
        bset    #INPUT_FIRE,input_events
        bra     .drain
.accept
        bset    #INPUT_ACCEPT,input_events
        bra     .drain
.quit
        bset    #INPUT_QUIT,input_events
        bra     .drain

.finish
        ; Keep firing while the left button is held. The handler separately
        ; latches a button-down event so a short click cannot be lost between
        ; two frame polls.
        move.w  input_mouse_buttons,d0
        btst    #MOUSE_BUTTON_LEFT,d0
        beq     .done
        bset    #INPUT_FIRE,input_events
.done
        rts

; TOS calls the installed mouse vector from its IKBD interrupt handler with
; A0 pointing at a complete three-byte relative report:
;   byte 0: $f8-$fb, button state in bits 0/1
;   byte 1: signed X delta
;   byte 2: signed Y delta
; Keep this routine short because it executes at interrupt level.
input_mouse_handler
        movem.l d0-d2/a0,-(sp)
        moveq   #0,d0
        move.b  (a0),d0
        andi.w  #$0003,d0
        move.w  input_mouse_buttons,d2
        move.w  d0,input_mouse_buttons

        moveq   #0,d1
        move.b  1(a0),d1
        ext.w   d1
        add.w   d1,input_mouse_pending_dx
        add.w   d1,input_mouse_x
        bpl     .x_nonnegative
        clr.w   input_mouse_x
        bra     .x_done
.x_nonnegative
        cmpi.w  #FRAME_WIDTH-1,input_mouse_x
        ble     .x_done
        move.w  #FRAME_WIDTH-1,input_mouse_x
.x_done

        moveq   #0,d1
        move.b  2(a0),d1
        ext.w   d1
        add.w   d1,input_mouse_pending_dy
        add.w   d1,input_mouse_y
        bpl     .y_nonnegative
        clr.w   input_mouse_y
        bra     .y_done
.y_nonnegative
        cmpi.w  #FRAME_HEIGHT-1,input_mouse_y
        ble     .y_done
        move.w  #FRAME_HEIGHT-1,input_mouse_y
.y_done

        ; Latch only a new left-button press. input_poll consumes this after
        ; publishing the accumulated motion for the frame.
        btst    #MOUSE_BUTTON_LEFT,d0
        beq     .done
        btst    #MOUSE_BUTTON_LEFT,d2
        bne     .done
        move.w  #1,input_mouse_button_event
.done
        movem.l (sp)+,d0-d2/a0
        rts

        bss
        even
input_events       ds.w    1
input_mouse_dx     ds.w    1
input_mouse_dy     ds.w    1
input_mouse_buttons ds.w   1
input_mouse_x      ds.w    1
input_mouse_y      ds.w    1
input_mouse_pending_dx ds.w 1
input_mouse_pending_dy ds.w 1
input_mouse_button_event ds.w 1
input_saved_mouse_vector ds.l 1
input_mouse_params ds.b 12
                    even

        end
