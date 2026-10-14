; Route: analysis/functions/browser-attract.md#shake-timer
; Record: analysis/functions/browser-attract.md#shake-timer
; CPU timer contract, independently captured in the shipped DOS timer ISR.
        include "inc/comanche.s"
        global flight_shake_tick, flight_shake_clock, shake_present
        global flt_shake_rng, flt_shake_phase, flt_shake_timer
        xref    flt_crash_drop, console_rgb
        global shake_clock_accumulator, shake_presentation_unproven
        text

; DOS: FUN_00001D20, verified ISR entry 00001D20; body 00001DB5-00001DE7.
; Record: analysis/functions/browser-attract.md#shake-timer
; Port: advances the DOS PRNG, countdown and phase once per PIT event.
; Preserved: unsigned 32-bit wrap, rotate, unconditional RNG and final zero.
; Kind: translated.
; Status: checked against captured DOS ISR cases by tools/check-shake-contract.py.
flight_shake_tick
        move.l  d0,-(sp)
        move.l  flt_shake_rng,d0
        eori.l  #$a50a50a0,d0                   ; 00001DBA
        addi.l  #$00050a05,d0                   ; 00001DBF
        ror.l   #3,d0                           ; 00001DC4
        move.l  d0,flt_shake_rng                 ; 00001DC7
        andi.l  #3,d0                           ; 00001DD1
        tst.l   flt_shake_timer                 ; 00001DD4
        beq     .done
        subq.l  #1,flt_shake_timer               ; 00001DDD
        bne     .store
        moveq   #0,d0                           ; 00001DE5
.store
        move.l  d0,flt_shake_phase               ; 00001DE7
.done
        move.l  (sp)+,d0
        rts

; DOS: N/A - platform replacement for the PIT divisor at 00001CEB.
; Record: analysis/functions/browser-attract.md#shake-timer
; Port: maps TOS 200 Hz Timer C events to the DOS PIT event stream.
; Preserved: rational long-term rate; independent of rendering and VBL.
; Difference: events are quantized to 5 ms; hardware clock phase is Unproven.
; Kind: replaced.
; Status: rational event counts tested; physical clock phase remains Unproven.
flight_shake_clock
        ; Target boundary: remember an unsupported display phase even if its
        ; countdown expires while the foreground renderer is still busy.
        tst.l   flt_shake_timer
        beq     .advance
        move.w  #1,shake_presentation_unproven
.advance
        addi.l  #1193182,shake_clock_accumulator
        cmpi.l  #200*$47b4,shake_clock_accumulator
        bcs     .done
        subi.l  #200*$47b4,shake_clock_accumulator
        bra     flight_shake_tick
.done
        rts

; The displayed window under shake. 00015BB3-00015BE6 program the CRTC start
; address from the page just drawn ([00019CAC], page + 1 byte), PLUS the
; dword at [ebx*4 + 00015B60] for ebx = the phase [00019DBC] (0, 81, 164, 245 -
; one 82-byte row each, less a byte on the odd entries), PLUS [00019DC4]; and
; 00001DF1-00001E00, run from the timer ISR, writes the phase << 1 to the
; attribute controller's pixel pan, which in a 256-colour mode is `<< 1` for a
; pixel. Page rows are 82 bytes of four pixels, so for phase p
;
;     start = 1 + t[p]  ->  row = start / 82, byte = start % 82
;     window x = 4 * byte + p,   window y = row
;
; p=0 (4,0)  p=1 (1,1)  p=2 (6,2)  p=3 (3,3), against the resting (4,0). In
; the port's own surface (window origin at page x 4) the window moves by
;
;     p=0 (0,0)   p=1 (-3,+1)   p=2 (+2,+2)   p=3 (-1,+3)
;
; The DOS page is 328 pixels wide and 240 rows, and its margins hold real
; pixels the window slides over. The port renders the 320x240 window only, so
; the margins - up to three pixels left, two right, and three rows below - are
; not recovered; they take the nearest edge pixel instead. That is the whole
; deviation, it lasts the ten timer ticks 00019461 arms, and it is recorded
; as Unproven in shake_presentation_unproven rather than claimed equal.
; In: a0 = the finished frame (320x240 RGB565). Preserves everything.
; DOS: flat 00015BB3-00015BE6, 00001DF1-00001E00 and the table at 00015B60.
; DOS symbol: loc_00015BB3
; Record: analysis/functions/browser-attract.md#shake-timer
; Port: moves the published window by the offset the CRTC start and pixel pan
;   would, in the frame itself.
; Preserved: the phase source, the four window offsets.
; Difference: the page margins are not rendered (edge replicate). The rows
;   below the page that the wreck's sinking window slides over -
;   [00019DC4] is up to 45 rows - are the console image's own lower rows, as a
;   capture of the original at 40 rows of sink shows.
; Kind: adapted - platform surface replacement.
; Status: ported; the margin content is Unproven.
shake_present
        movem.l d0-d7/a0-a3,-(sp)
        moveq   #0,d4                           ; dx
        moveq   #0,d5                           ; dy
        move.l  flt_shake_phase,d0
        beq.s   .no_phase
        cmpi.l  #3,d0
        bhi     .out
        lea     shake_offsets,a1
        add.w   d0,d0
        move.b  0(a1,d0.w),d4                   ; dx
        ext.w   d4
        move.b  1(a1,d0.w),d5                   ; dy
        ext.w   d5
        move.w  #1,shake_presentation_unproven
.no_phase
        ; 00015BC9 adds [00019DC4] to the start address as well: the wreck's
        ; sinking screen, 0x52 - one row - a tick (00018F5F), so the window
        ; slides down the page a row at a time.
        move.l  flt_crash_drop,d0
        beq.s   .no_drop
        divu.w  #82,d0
        add.w   d0,d5
        move.w  #1,shake_presentation_unproven
.no_drop
        move.w  d4,d0
        or.w    d5,d0
        beq     .out
        move.l  a0,a2                           ; the frame
        moveq   #0,d6                           ; destination row
.row
        move.w  d6,d0
        add.w   d5,d0                           ; source row = y + dy
        move.l  a2,a1
        cmpi.w  #239,d0
        ble     .row_ok
        ; Below the page's 240 rows the original's video memory holds the rest
        ; of the console image 0001687D blitted (CONSOLE_ROWS of them); a
        ; window slid down over them shows its dark lower panel.
        move.l  #console_rgb,a1
        cmpi.w  #CONSOLE_ROWS-1,d0
        ble     .row_ok
        move.w  #CONSOLE_ROWS-1,d0
.row_ok
        mulu    #SCREEN_STRIDE,d0
        adda.l  d0,a1                           ; the source row...
        lea     shake_row,a3
        move.w  #(SCREEN_STRIDE/4)-1,d1
.copy
        move.l  (a1)+,(a3)+                     ; ...copied aside first, because
        dbra    d1,.copy                        ; the last rows read themselves
        move.w  d6,d0
        mulu    #SCREEN_STRIDE,d0
        lea     0(a2,d0.l),a1                   ; the destination row
        lea     shake_row,a3
        move.w  #SCREEN_WIDTH-1,d7
        moveq   #0,d3                           ; x
.pixel
        move.w  d3,d0
        add.w   d4,d0                           ; source column = x + dx, clamped
        bge     .col_lo
        moveq   #0,d0
.col_lo
        cmpi.w  #SCREEN_WIDTH-1,d0
        ble     .col_ok
        move.w  #SCREEN_WIDTH-1,d0
.col_ok
        add.w   d0,d0
        move.w  0(a3,d0.w),(a1)+
        addq.w  #1,d3
        dbra    d7,.pixel
        addq.w  #1,d6
        cmpi.w  #240,d6
        bcs     .row
.out
        movem.l (sp)+,d0-d7/a0-a3
        rts

        data
        even
shake_offsets
        dc.b    0,0, -3,1, 2,2, -1,3

        bss
        even
shake_row
        ds.b    SCREEN_STRIDE
        even
flt_shake_rng
        ds.l 1
flt_shake_phase
        ds.l 1
flt_shake_timer
        ds.l 1
shake_clock_accumulator
        ds.l 1
; Target artefact: sticky unsupported-presentation gate, not DOS game state.
shake_presentation_unproven
        ds.w 1
        end
