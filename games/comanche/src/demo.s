; Route: analysis/functions/falcon-attract.md#replay-flight.
; Source boundary: QEMU-traced DOS attract route; CPU-only Falcon counterpart.
;
; DEMO*.SCR playback: the attract mode's recorded flights, byte-exact to the
; DOS reader at 00018CBC. The file is a start state and one 8-byte input
; record per integration tick - not positions - so it only flies true
; through flight.s's exact arithmetic.
;
; File, all little-endian:
;   +0   dword  length = filesize - 4
;   +4   dword  X, 10.22        +8  dword Y        +12 dword flight angle
;   +16  byte   altitude, half-map-byte units
;   +17  8-byte records: key, collective, weapon1 OR, weapon2 OR,
;        int16 axis1, int16 axis2
;
; Playback ends at the length; there is no terminator.
;
; Record byte 0 is not a spare and it is not a hotkey to be discarded. DOS
; pushes it into the four-byte key FIFO at 00001B70 (00018CDB), the frame
; loop pops one byte per iteration at 00006AF4, and a non-zero pop is
; dispatched to the in-flight command chain at 0001959F. The FIFO's other
; producer is the keyboard ISR at 00001BE8, which is why 00018CD2 reads the
; head first: a byte still queued there when a record is consumed is a byte
; the player typed, and 00018CB0 leaves the attract for the menu. The
; recorded keys are commands, not an exit - DEMO0 carries one (record 773),
; DEMO1 eight, DEMO2 nine and DEMO3 nine, at scancodes 0x02, 0x07, 0x08,
; 0x18, 0x1A and 0x1B, spread through the flight rather than parked at the
; end. demo_tick parks the byte and main.s dispatches it where 00006AF4 does.
; The console page keys 0x1A and 0x1B are ported in game_command; 0x18 is
; not - it is the last record of every stream and its case is undecoded.
;
; 0x02, 0x07 and 0x08 are the VIEW selectors, and they are ported too - see
; src/view.s. They are the '1', '6' and '7' keys; 00019696/00019829/00019854
; set [00019D86], and 00007D25 indexes that into the view-angle offsets at
; [00019D94] and the camera handlers at [00007BC9]. Variant 6 (00007C26)
; pulls the viewpoint fifteen map cells back along the view and lifts it to
; byte(2h+12); variant 7 (00007CC5) replaces it outright with
; [00019CE4]/[00019CE8] at altitude [00019DF8] and aims it from a bearing to
; the player. DEMO1 selects variant 6 at record 30 and variant 7 at record
; 206, and returns to the cockpit at 357: 327 of its 777 records - 42% of the
; first attract pass - are flown from outside the helicopter. Until they were
; ported the port drew all 777 from the cockpit, which is what made the
; authored path look like it flew into the hills; the flight itself was, and
; is, exact. See work/trace_replay_flight.py and
; analysis/functions/falcon-attract.md.

        include "inc/comanche.s"

        global  demo_start, demo_tick, demo_active, demo_ended
        global  demo_key

        text

; Load DEMO<n>.SCR and seed the flight state from its header.
; In: d0.w = demo number 0-3. Out: d0.l = 0 on success.
;
; 00019A2D patches the digit of the 'demo1.scr' template at 00019A47 with
; [0002975A] OR 0x30, loads the whole file to 0x0002DB0C through 00015DD0,
; and reads the header from 0x0002DB10 - so the file's own leading dword
; stays put as the length the cursor is compared against, the payload starts
; four bytes in, and the first record is at cursor 13.
; DOS: flat 00019A2D-00019ABD, DEMO<N>.SCR reader and replay-state seed.
; DOS symbol: sub_00019A2D
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: loads the original little-endian header through GEMDOS into Falcon state.
; Preserved: filename template and digit, load layout, length field, 10.22 X/Y,
; full angle, altitude, cursor origin, and the rate reset that follows.
; Difference: 00019A4E sets the replay-mode flag [00019ED0]; demo_active is
;   this port's counterpart and is set below at the same point.
; Kind: translated.
; Status: ported; byte-level replay validation is documented and capture pending.
demo_start
        movem.l d1-d2/a0-a1,-(sp)
        clr.w   demo_active
        clr.w   demo_ended
        clr.b   demo_key
        addi.b  #'0',d0
        lea     demo_name,a0
        move.b  d0,4(a0)                        ; DEMO_.SCR

        move.w  #0,-(sp)
        pea     demo_name
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .fail
        move.w  d0,d2

        pea     demo_buffer
        move.l  #DEMO_BUFFER_BYTES,-(sp)
        move.w  d2,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d1

        move.w  d2,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp

        moveq   #17,d0
        cmp.l   d0,d1
        blt     .fail

        ; Little-endian header into the flight state.
        lea     demo_buffer,a0
        bsr     .le32                           ; length
        move.l  d0,demo_length
        bsr     .le32
        move.l  d0,flt_x
        bsr     .le32
        move.l  d0,flt_y
        bsr     .le32
        move.l  d0,flt_angle
        moveq   #0,d0
        move.b  (a0)+,d0
        move.b  d0,player_altitude

        bsr     flight_reset
        ; 000063BB-000063C9 seeds the console page and both MFD pages at
        ; mission start, and the attract reaches its flight through here.
        jsr     console_start_state
        bsr     flight_publish
        move.l  #13,demo_cursor                 ; first record, past the header
        move.w  #1,demo_active
        moveq   #0,d0
        bra     .out
.fail
        moveq   #-1,d0
.out
        movem.l (sp)+,d1-d2/a0-a1
        rts

.le32
        moveq   #0,d0
        move.b  3(a0),d0
        lsl.l   #8,d0
        move.b  2(a0),d0
        lsl.l   #8,d0
        move.b  1(a0),d0
        lsl.l   #8,d0
        move.b  (a0),d0
        addq.l  #4,a0
        rts

; Feed one record into the flight inputs. Ends the demo at the recorded
; length, exactly `cursor >= length`.
; DOS: flat 00018CBC-00018D1B, DEMO<N>.SCR per-frame record consumer.
; DOS symbol: loc_00018CBC
; Record: analysis/functions/falcon-attract.md#replay-flight
; Port: feeds the recorded key/collective/triggers/axes to flight_tick once.
; Preserved: eight-byte record layout, little-endian axes, EOF transition.
; Differences:
;   - 00018CDB pushes the key byte into the four-byte FIFO at 00001B70; this
;     port parks it in demo_key, a one-byte slot, because main.s pops exactly
;     one per iteration as 00006AF4 does and nothing here produces the second
;     producer the FIFO exists for. 00018CD2's "already queued" test - which
;     leaves the attract - therefore has no state to read; attract_frame makes
;     that decision from input_events instead, one frame earlier in the tick.
;   - 00018CD2/00018CB0: a key already queued when a record is consumed leaves
;     the attract for the menu. This port makes the same decision from
;     input_events in attract_frame, one frame earlier in the tick.
;   - 00018D0A zeroes the third axis [00019DD0], read at 00018E02 only when
;     the device byte [00025DDE] is 0x7D. No such device is ported, so there
;     is no state to clear.
; Kind: translated.
; Status: ported; attract-cycle capture remains pending.
demo_tick
        movem.l d0-d1/a0,-(sp)
        tst.w   demo_active
        beq     .out
        move.l  demo_cursor,d0
        cmp.l   demo_length,d0
        blt     .feed
        clr.w   demo_active
        move.w  #1,demo_ended
        bra     .out
.feed
        lea     demo_buffer+4,a0
        adda.l  d0,a0
        addq.l  #8,demo_cursor

        ; +0 key. 00018CDB pushes it into the 00001B70 FIFO; the frame loop
        ; pops it at 00006AF4 and dispatches it to 0001959F in the same
        ; iteration. This port has no FIFO, so the byte is parked here and
        ; frame_driver dispatches it at the equivalent point.
        move.b  (a0),demo_key
        move.b  1(a0),flt_collective
        move.b  2(a0),d1
        or.b    d1,flt_trig1
        move.b  3(a0),d1
        or.b    d1,flt_trig2
        move.b  5(a0),d1                        ; axis1, little-endian
        lsl.w   #8,d1
        move.b  4(a0),d1
        move.w  d1,flt_axis1
        move.b  7(a0),d1
        lsl.w   #8,d1
        move.b  6(a0),d1
        move.w  d1,flt_axis2
.out
        movem.l (sp)+,d0-d1/a0
        rts

        data
demo_name
        dc.b    "DEMO0.SCR",0
        even

        bss
        even
DEMO_BUFFER_BYTES = 8200
demo_buffer
        ds.b    DEMO_BUFFER_BYTES
        even
demo_length
        ds.l    1
demo_cursor
        ds.l    1
; The record's key byte, waiting for frame_driver to dispatch it.
demo_key
        ds.b    1
        even
demo_active
        ds.w    1
demo_ended
        ds.w    1

        end
