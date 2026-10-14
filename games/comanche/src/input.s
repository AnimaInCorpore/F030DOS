; Route: analysis/functions/falcon-attract.md#frame-driver.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; Keyboard input for the Falcon port.
;
; The original keeps a 128-byte key-state array at 00001A70, indexed by
; scancode, filled with 0xFF at 00001900 and cleared to zero while a key is
; down; every consumer tests it with a sign check, so "held" is "non-negative"
; (docs/X86-M68K-MAP.md:622). This file reproduces that array and its sign
; convention, because the live control path at 00018E49 is written against it
; and nothing else it does would be faithful without it.
;
; Owning the IKBD vector is not a platform flourish. The BIOS console queue
; delivers key MAKES only - there is no break event in it - so a control
; scheme built on held keys latches every key on forever when it is fed from
; Bconin. The original owns its keyboard interrupt too, as an IDT gate
; installed at 00001921. The polled ACIA drain and the console queue are kept
; below as fallbacks for configurations that deliver neither.
;
; The event-bit word remains for the attract cycle's any-key exit and for the
; options bar, which are edge-triggered rather than held.

        include "inc/comanche.s"
        include "inc/bios.s"

        global  input_init, input_deinit, input_poll, input_axes
        global  input_events, input_held, input_pending
        global  key_state, key_latch, ikbd_handler, key_queue, input_notch

; MFP channel 6, the keyboard/MIDI ACIA.
IKBD_VECTOR     = $118

; DOS 00018E49-00018EE3 loads 0x0000015E and 0xFFFFFEA2 - +/-350 - into the
; two axis words for every direction it tests. It is one magnitude, not a
; ramp: the original's keyboard control is full deflection or centred.
AXIS_STEP       = 350

; The ST separates the cursor block from the numeric keypad; the PC does not,
; and the original reads one scancode for both. These are the keypad slots the
; ST cursor keys are folded onto, so 00018E49's table can be ported verbatim.

        text

; Fill the key array with the released value and take the IKBD vector.
; DOS: flat 00001900-00001921, key-array init and keyboard gate installation.
; DOS symbol: inside sub_000018E9
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: mirrors the 0xFF fill and takes the Falcon's MFP keyboard vector.
; Preserved: released-is-negative convention and interrupt ownership of keys.
; Kind: translated.
; Status: ported; the DOS ISR body itself is a platform replacement.
input_init
        lea     key_state,a0
        move.w  #127,d0
.fill
        st      (a0)+                           ; $FF: released, as 00001900 does
        dbra    d0,.fill
        lea     key_latch,a0
        move.w  #127,d0
.latch
        clr.b   (a0)+
        dbra    d0,.latch
        clr.b   input_notch
        clr.w   input_held
        clr.w   input_pending
        clr.w   input_events

        ; The PC keyboard controller the original reads sends key events and
        ; nothing else. The IKBD is a whole peripheral: left to its defaults it
        ; interleaves three-byte relative mouse packets into the same stream,
        ; and their delta bytes decode as perfectly ordinary scancodes. That is
        ; not hypothetical - it was measured here, with the packets marking
        ; scancodes $00/$01/$07/$13 held and their arrival tripping the
        ; any-key attract exit on the first frame. Silence both reporting
        ; modes so the byte stream carries what 00001A70 expects.
        moveq   #$12,d0                         ; IKBD: disable mouse
        bsr     ikbd_command
        moveq   #$1a,d0                         ; IKBD: disable joysticks
        bsr     ikbd_command

        move.l  vector_base,a0
        move.l  IKBD_VECTOR(a0),saved_ikbd
        move.l  #ikbd_handler,IKBD_VECTOR(a0)
        ScreenCachePush
        rts

; Send one command byte to the IKBD, waiting for the ACIA transmitter.
; DOS: N/A - the PC keyboard controller needs no equivalent configuration.
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: Falcon peripheral setup so the key stream is keys only.
; Preserved: nothing; this exists because the two keyboards differ.
; Kind: replaced.
; Status: ported.
ikbd_command
.wait
        btst    #1,$fffffc00.w                  ; transmitter ready
        beq     .wait
        move.b  d0,$fffffc02.w
        rts

; Hand the vector back. Safe to call even if install never ran.
; DOS: N/A - Falcon interrupt teardown, no DOS counterpart in a game exit.
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: restores the displaced TOS IKBD vector idempotently.
; Preserved: host interrupt ownership after the game exits.
; Kind: replaced.
; Status: ported.
input_deinit
        tst.l   saved_ikbd
        beq     .done
        move.l  a0,-(sp)
        move.l  vector_base,a0
        move.l  saved_ikbd,IKBD_VECTOR(a0)
        ScreenCachePush
        move.l  (sp)+,a0
        clr.l   saved_ikbd
.done
        rts

; DOS: 000189C2-00018A06 and 000280C1, event/scancode input boundary.
; DOS symbol: sub_000189C2
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: drains any queued host key sources into the shared event word.
; Preserved: make/break state and any-key attract exit; PC timing is replaced.
; Kind: translated.
; Status: ported; analogue controllers remain stopped.
input_poll
; With the vector installed the handler below owns the byte stream and both of
; these normally find nothing. They are kept because they cost a status read
; per frame and they are the only thing that would still deliver a key if the
; MFP wiring were not being emulated.
        Bconstat #2
        tst.l   d0
        beq     .read_acia
        Bconin  #2
        move.w  d0,d1
        lsr.w   #8,d1
        move.w  d1,d0
        andi.w  #$00ff,d0
        bsr     process_scan

.read_acia
.read_more
        btst    #0,$fffffc00.w
        beq     .snapshot
        moveq   #0,d0
        move.b  $fffffc02.w,d0
        bsr     process_scan
        bra     .read_more

.snapshot
        move.w  input_held,d0
        or.w    input_pending,d0
        move.w  d0,input_events
        clr.w   input_pending
        rts

; One byte per interrupt: bit 7 is the release flag, the low seven bits are
; the make code. Channel 6's in-service bit is cleared explicitly because the
; MFP is run in software-EOI mode.
; DOS: 00001B96 keyboard interrupt boundary; the Falcon MFP replaces the PC ISR.
; DOS symbol: inside sub_00001950
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: consumes raw IKBD bytes into the key array without going through GEMDOS.
; Preserved: release-bit interpretation and nonblocking event ownership.
; Kind: replaced - platform replacement for the DOS gate at 00001921.
; Status: ported.
ikbd_handler
        movem.l d0-d2/a0,-(sp)
.next
        btst    #0,$fffffc00.w
        beq     .eoi
        moveq   #0,d0
        move.b  $fffffc02.w,d0
        bsr     process_scan
        bra     .next
.eoi
        bclr    #6,$fffffa11.w                  ; MFP channel 6 in-service
        movem.l (sp)+,d0-d2/a0
        rte

; Decode one raw IKBD scan code in d0 into the key array and the edge events.
; DOS: 00001900-00001921 array maintenance; 00001BA6-00001BE6 collective
; steps; 00019988/00019BEF collective keys.
; DOS symbol: inside sub_000018E9
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: maintains the recovered key array and the two collective notch keys.
; Preserved: array indexing, sign convention, and the 0x20/0x00 notch values.
; Kind: translated.
; Status: ported; the in-flight command chain at 0001959F is not.
process_scan
        move.w  d0,d1
        andi.w  #$007f,d1

        ; The ST's scancodes run $01-$72. Anything outside that is not a key -
        ; an IKBD status or reset packet, or a stray byte - and must not be
        ; allowed to mark an array slot, because every slot in range is a
        ; control the flight path reads. Mouse and joystick reporting are off
        ; (input_init), so this is the remaining protocol guard rather than
        ; the main line of defence.
        tst.w   d1
        beq     .done
        cmpi.w  #$72,d1
        bhi     .done

        ; Fold the ST cursor block onto the keypad codes the PC shares with
        ; it, so 00018E49's table reads one slot per direction as it does on
        ; the original. This is the one place the two keyboards differ.
        cmpi.w  #$48,d1
        bne     .not_up
        moveq   #KEY_KP8,d1
.not_up
        cmpi.w  #$50,d1
        bne     .not_down
        moveq   #KEY_KP2,d1
.not_down
        cmpi.w  #$4b,d1
        bne     .not_left
        moveq   #KEY_KP4,d1
.not_left
        cmpi.w  #$4d,d1
        bne     .not_right
        moveq   #KEY_KP6,d1
.not_right

        lea     key_state,a0
        btst    #7,d0
        bne     .release

        clr.b   0(a0,d1.w)                      ; held reads as non-negative
        move.l  a1,-(sp)                        ; the IKBD handler saves only a0
        lea     key_latch,a1
        move.b  d0,0(a1,d1.w)                   ; 00001BA0 [ebx + 00001AF0] = the make code
        move.l  (sp)+,a1
        ; 00001BE8-00001BF4: [00001B70] = ([00001B70] << 8) | the make code, so
        ; the newest key is the low byte and a reader pops it with a shift.
        move.l  d2,-(sp)
        move.l  key_queue,d2
        lsl.l   #8,d2
        move.b  d0,d2
        move.l  d2,key_queue
        move.l  (sp)+,d2
        bset    #15,input_pending               ; DOS attract exits on any key

        ; 00001BA6-00001BE6, in the key interrupt itself: six makes step the
        ; collective notch by 0x10. D, keypad + and = take it down while it is
        ; at least 0x10; E, keypad - and - take it up while it is below 0xE6.
        ; The DOS tests PC scancodes 0x20/0x4E/0x0D and 0x12/0x4A/0x0C, and
        ; the ST's codes for those six keys are the same numbers.
        cmpi.w  #$20,d1                         ; 00001BA6 D
        beq     .notch_down
        cmpi.w  #$4e,d1                         ; 00001BAB keypad +
        beq     .notch_down
        cmpi.w  #$0d,d1                         ; 00001BB0 =
        beq     .notch_down
        cmpi.w  #$12,d1                         ; 00001BC7 E
        beq     .notch_up
        cmpi.w  #$4a,d1                         ; 00001BCC keypad -
        beq     .notch_up
        cmpi.w  #$0c,d1                         ; 00001BD1 -
        beq     .notch_up

        ; The collective is a notch on the keyboard device, read back through
        ; (notch & $F0) + 5; these two command keys set it outright.
        cmpi.w  #KEY_KPSTAR,d1
        beq     .notch_high
        cmpi.w  #KEY_A,d1
        beq     .notch_low
        cmpi.w  #KEY_ESCAPE,d1
        beq     .make_menu
        cmpi.w  #KEY_RETURN,d1
        beq     .make_confirm
        ; Edge bits for the four directions. The options bar steps once per
        ; press where the flight reads held state, and on the original these
        ; are the same keys doing double duty - 0002615C navigates on the very
        ; scancodes 00018E49 tests as array slots - so they come from the same
        ; normalised slots rather than from a second set of keys. Pending only:
        ; holding a direction must not run the selection off the end.
        cmpi.w  #KEY_KP4,d1
        beq     .dir_left
        cmpi.w  #KEY_KP6,d1
        beq     .dir_right
        cmpi.w  #KEY_KP8,d1
        beq     .dir_up
        cmpi.w  #KEY_KP2,d1
        beq     .dir_down
        bra     .done

        ; BSET on memory is a byte operation numbered within the byte at the
        ; address, and a word's first byte is its HIGH one: bits 13-15 above
        ; land where they are meant to by that rule, bits 0-3 need the low
        ; byte. Written to input_pending itself they became bits 8-11, which
        ; nothing reads, and the options bar could not be stepped at all.
.dir_left
        bset    #0,input_pending+1
        bra     .done
.dir_right
        bset    #1,input_pending+1
        bra     .done
.dir_up
        bset    #2,input_pending+1
        bra     .done
.dir_down
        bset    #3,input_pending+1
        bra     .done

.release
        st      0(a0,d1.w)                      ; $FF, as the DOS ISR writes
        bra     .done

.notch_down
        cmpi.b  #$10,input_notch                ; 00001BB5
        bcs     .done                           ; 00001BBC jb
        subi.b  #$10,input_notch                ; 00001BBE
        bra     .done
.notch_up
        cmpi.b  #$e6,input_notch                ; 00001BD6
        bcc     .done                           ; 00001BDD jae
        addi.b  #$10,input_notch                ; 00001BDF
        bra     .done
.notch_high
        move.b  #$20,input_notch                ; DOS 0001998C
        bra     .done
.notch_low
        clr.b   input_notch                     ; DOS 00019BF3
        bra     .done
.make_confirm
        bset    #13,input_pending
        bra     .done
.make_menu
        ; Pending only, never held: a held Escape must not retoggle the bar
        ; every frame, and nothing releases these edge bits.
        bset    #14,input_pending
        bra     .done
.done
        rts

; Rebuild the two axis words and the collective from the key array.
; DOS: flat 00018D2A-00018D3F and 00018E49-00018EE3, live control read.
; DOS symbol: inside sub_00018D20
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: ports the axis reset, the notch collective and the eight-way table.
; Preserved: the from-zero rebuild, the +/-350 magnitude, and the test order.
; Kind: translated.
; Status: ported; the analogue device path at 00018A06 remains stopped.
input_axes
        ; 00018D2A-00018D31 clears both axes at the top of every tick, so a
        ; released key stops contributing on the very next frame rather than
        ; decaying. The damping in flight_tick is what decays the rates.
        ; 00018D20-00018D25 first saves the collective into [00019D83]; the
        ; fuel-gone branch at 00018E29 reads it back.
        move.b  flt_collective,flt_collective_prev
        clr.w   flt_axis1
        clr.w   flt_axis2

        ; 00018D36-00018D3F. The shipped COMANCHE.MNU selects control device
        ; '3' at offset 0x1B, the keyboard, so the analogue throttle at
        ; 00018D95 never runs and this notch is the whole collective input.
        moveq   #0,d0
        move.b  input_notch,d0
        andi.w  #$00f0,d0
        addq.w  #5,d0
        move.b  d0,flt_collective

        lea     key_state,a0

        ; 00018E49-00018EE3, in the original's own order: the four diagonals
        ; first, then the four cardinals, each store overwriting the last. A
        ; held KP7 with a held KP6 therefore ends up forward-and-right, which
        ; is what the sequence produces on the original.
        tst.b   KEY_KP7(a0)
        bmi     .no_kp7
        move.w  #-AXIS_STEP,flt_axis1
        move.w  #-AXIS_STEP,flt_axis2
.no_kp7
        tst.b   KEY_KP9(a0)
        bmi     .no_kp9
        move.w  #AXIS_STEP,flt_axis1
        move.w  #-AXIS_STEP,flt_axis2
.no_kp9
        tst.b   KEY_KP1(a0)
        bmi     .no_kp1
        move.w  #-AXIS_STEP,flt_axis1
        move.w  #AXIS_STEP,flt_axis2
.no_kp1
        tst.b   KEY_KP3(a0)
        bmi     .no_kp3
        move.w  #AXIS_STEP,flt_axis1
        move.w  #AXIS_STEP,flt_axis2
.no_kp3
        tst.b   KEY_KP4(a0)
        bmi     .no_kp4
        move.w  #-AXIS_STEP,flt_axis1
.no_kp4
        tst.b   KEY_KP6(a0)
        bmi     .no_kp6
        move.w  #AXIS_STEP,flt_axis1
.no_kp6
        tst.b   KEY_KP8(a0)
        bmi     .no_kp8
        move.w  #-AXIS_STEP,flt_axis2
.no_kp8
        tst.b   KEY_KP2(a0)
        bmi     .no_kp2
        move.w  #AXIS_STEP,flt_axis2
.no_kp2
        rts

        bss
        even
input_events
        ds.w    1
input_held
        ds.w    1
input_pending
        ds.w    1
input_notch
        ds.b    1
        even
saved_ikbd
        ds.l    1
; The original's 00001A70, one byte per scancode.
key_state
        ds.b    128
; 00001AF0 + scancode: the make code of the last press, left set until a
; reader clears it (00001BA0). Only the fire, target-cycle and weapon-select
; readers consume it; the array above is the held state.
key_latch
        ds.b    128
; [00001B70]: the last four make codes, newest in the low byte. The pilot's
; name entry (0002800C) is the one reader here that wants keys one at a time.
        even
key_queue
        ds.l    1

        end
