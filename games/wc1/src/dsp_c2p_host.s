; Bounded 68030 host for the legacy WC1 DSP56001 C2P diagnostic.
;
; The game now presents RGB565 directly and does not link this module. The
; standalone smoke target still loads WC1C2P.LOD, proves the worker version,
; and verifies an entire 107-word scanline loopback plus known C2P
; input/output vectors, making the old transport independently testable.

        include "inc/xbios.s"
        include "dsp/c2pproto.inc"

        xdef    dsp_c2p_init
        xdef    dsp_c2p_convert
        xdef    dsp_c2p_status
        xdef    dsp_c2p_vector_index
        xdef    dsp_c2p_vector_actual
        xdef    dsp_c2p_vector_expected

; Falcon DSP host port: status at $FFFFA202, 24-bit data at $FFFFA204.
ISR_RXDF                = 0
ISR_TXDE                = 1
DSP_C2P_TIMEOUT         = 200000

; The worker's X map is 107 packed inputs, 321 unpacked indices, 321 planar
; bytes (including pad), and 107 packed replies.  Reserve a round 1K words
; so a later implementation can retain cell state without changing the host
; memory contract.
DSP_C2P_X_WORDS         = 1536
DSP_C2P_Y_WORDS         = 0
DSP_C2P_LOD_BYTES       = 4096

DSP_C2P_OK              = 0
DSP_C2P_ERR_ABSENT      = -1
DSP_C2P_ERR_RESERVE     = -2
DSP_C2P_ERR_LOAD        = -3
DSP_C2P_ERR_TIMEOUT     = -4
DSP_C2P_ERR_PROTOCOL    = -5
DSP_C2P_ERR_LOOPBACK    = -6

DSP_C2P_SELFTEST_SEQ    = $13579b
DSP_C2P_SELFTEST_SEED   = $010203
DSP_C2P_SELFTEST_STEP   = $010101

        text

; In: d1 = a 24-bit protocol word.  Out: d0 = DSP_C2P_OK or timeout.
dsp_c2p_put
        move.l  d2,-(sp)
        move.l  #DSP_C2P_TIMEOUT,d2
.wait
        btst    #ISR_TXDE,$ffffa202.w
        bne     .ready
        subq.l  #1,d2
        bne     .wait
        move.l  (sp)+,d2
        moveq   #DSP_C2P_ERR_TIMEOUT,d0
        rts
.ready
        move.l  d1,$ffffa204.w
        move.l  (sp)+,d2
        moveq   #DSP_C2P_OK,d0
        rts

; Out: d0 = DSP_C2P_OK or timeout, d1 = zero-extended 24-bit word.
dsp_c2p_get
        move.l  d2,-(sp)
        move.l  #DSP_C2P_TIMEOUT,d2
.wait
        btst    #ISR_RXDF,$ffffa202.w
        bne     .ready
        subq.l  #1,d2
        bne     .wait
        move.l  (sp)+,d2
        moveq   #DSP_C2P_ERR_TIMEOUT,d0
        rts
.ready
        move.l  $ffffa204.w,d1
        andi.l  #$00ffffff,d1
        move.l  (sp)+,d2
        moveq   #DSP_C2P_OK,d0
        rts

; Send a fixed, non-repeating-enough scanline and demand the exact reply.
; This checks command framing, the sequence field, all 24 bits and the final
; 320-pixel pad word.  It does not touch either Videl page.
;
; Out: d0 = DSP_C2P_OK or DSP_C2P_ERR_{TIMEOUT,PROTOCOL,LOOPBACK}.
dsp_c2p_loopback
        movem.l d2-d3,-(sp)
        move.l  #C2P_CMD_LOOPBACK,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        move.l  #DSP_C2P_SELFTEST_SEQ,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done

        move.l  #DSP_C2P_SELFTEST_SEED,d3
        moveq   #C2P_SCANLINE_WORDS-1,d2
.send
        move.l  d3,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        addi.l  #DSP_C2P_SELFTEST_STEP,d3
        andi.l  #$00ffffff,d3
        dbra    d2,.send

        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmpi.l  #C2P_REPLY_SCANLINE,d1
        beq     .reply_magic_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .done
.reply_magic_ok
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmpi.l  #DSP_C2P_SELFTEST_SEQ,d1
        beq     .reply_sequence_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .done
.reply_sequence_ok
        move.l  #DSP_C2P_SELFTEST_SEED,d3
        moveq   #C2P_SCANLINE_WORDS-1,d2
.receive
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmp.l   d3,d1
        beq     .word_ok
        moveq   #DSP_C2P_ERR_LOOPBACK,d0
        bra     .done
.word_ok
        addi.l  #DSP_C2P_SELFTEST_STEP,d3
        andi.l  #$00ffffff,d3
        dbra    d2,.receive
        moveq   #DSP_C2P_OK,d0
.done
        movem.l (sp)+,d2-d3
        rts

; Verify the production C2P command without relying on the CPU converter at
; runtime.  The input has palette bits 0..7 in the first eight source pixels
; and palette index 255 at pixel 319.  It therefore checks MSB-first plane
; order, 24-bit repacking, the final cell, and the one-byte transport pad.
;
; Out: d0 = DSP_C2P_OK or DSP_C2P_ERR_{TIMEOUT,PROTOCOL,LOOPBACK}.
dsp_c2p_vector_test
        movem.l d2-d3,-(sp)
        move.l  #C2P_CMD_SCANLINE,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        move.l  #DSP_C2P_SELFTEST_SEQ,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done

        move.l  #$010204,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        move.l  #$081020,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        move.l  #$408000,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        ; DBRA executes its body counter+1 times: three leading words and
        ; 103 zero words occupy positions 0..105, leaving word 106 for the
        ; pixel-319 edge vector below.
        moveq   #C2P_SCANLINE_WORDS-5,d2
.zero_input
        clr.l   d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        dbra    d2,.zero_input
        move.l  #$00ff00,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done

        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmpi.l  #C2P_REPLY_SCANLINE,d1
        beq     .reply_magic_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .done
.reply_magic_ok
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmpi.l  #DSP_C2P_SELFTEST_SEQ,d1
        beq     .reply_sequence_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .done
.reply_sequence_ok
        clr.w   dsp_c2p_vector_index
        clr.l   dsp_c2p_vector_actual
        clr.l   dsp_c2p_vector_expected
        move.l  #$800040,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$002000,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$100008,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$000400,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$020001,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        clr.l   d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done

        moveq   #94,d2
.zero_output
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        dbra    d2,.zero_output
        move.l  #$000001,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$000100,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$010001,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$000100,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$010001,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        move.l  #$000100,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        bsr     dsp_c2p_full_vector_test
.done
        movem.l (sp)+,d2-d3
        rts

; Full-row golden test.  This has deliberately varied all palette-index bits
; across all 20 cells; every one of the 107 returned 24-bit words must match
; a stream produced by the 68030 C2P oracle before DSP presentation is used.
dsp_c2p_full_vector_test
        movem.l d2-d3/a0,-(sp)
        move.l  #C2P_CMD_SCANLINE,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        move.l  #DSP_C2P_SELFTEST_SEQ+1,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        lea     dsp_c2p_full_source,a0
        moveq   #C2P_SCANLINE_WORDS-1,d2
.send
        move.l  (a0)+,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        dbra    d2,.send

        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmpi.l  #C2P_REPLY_SCANLINE,d1
        beq     .reply_magic_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .done
.reply_magic_ok
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmpi.l  #DSP_C2P_SELFTEST_SEQ+1,d1
        beq     .reply_sequence_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .done
.reply_sequence_ok
        clr.w   dsp_c2p_vector_index
        clr.l   dsp_c2p_vector_actual
        clr.l   dsp_c2p_vector_expected
        lea     dsp_c2p_full_expected,a0
        moveq   #C2P_SCANLINE_WORDS-1,d2
.receive
        move.l  (a0)+,d3
        bsr     dsp_c2p_expect_word
        tst.l   d0
        bne     .done
        dbra    d2,.receive
        moveq   #DSP_C2P_OK,d0
.done
        movem.l (sp)+,d2-d3/a0
        rts

; In: d3 = expected 24-bit word.  Out: status in d0.
dsp_c2p_expect_word
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmp.l   d3,d1
        beq     .equal
        move.l  d1,dsp_c2p_vector_actual
        move.l  d3,dsp_c2p_vector_expected
        moveq   #DSP_C2P_ERR_LOOPBACK,d0
        bra     .done
.equal
        addq.w  #1,dsp_c2p_vector_index
.done
        rts

; Convert a complete 320x200 indexed frame through the validated DSP worker.
; C ABI: 4(sp)=source indexed bytes, 8(sp)=Falcon planar destination.  The
; host packs/receives a row directly, so no fourth 64 KiB staging page is
; needed on a stock 4 MiB Falcon.  On any error, status is latched negative;
; the caller overwrites the incomplete page with the CPU C2P fallback.
;
; Out: d0 = DSP_C2P_OK or a DSP_C2P_ERR_* value.
dsp_c2p_convert
        movem.l d1-d5/a0-a1,-(sp)
        move.l  32(sp),a0
        move.l  36(sp),a1
        move.l  dsp_c2p_sequence,d3
        andi.l  #$00ffffff,d3
        move.l  #C2P_SCREEN_HEIGHT-1,d5
.row
        move.l  #C2P_CMD_SCANLINE,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .failed
        move.l  d3,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .failed

        ; 106 complete three-pixel words cover bytes 0..317.
        moveq   #C2P_SCANLINE_WORDS-2,d2
.send_three
        moveq   #0,d1
        move.b  (a0)+,d1
        lsl.l   #8,d1
        moveq   #0,d4
        move.b  (a0)+,d4
        or.l    d4,d1
        lsl.l   #8,d1
        moveq   #0,d4
        move.b  (a0)+,d4
        or.l    d4,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .failed
        dbra    d2,.send_three

        ; Pixel bytes 318 and 319, plus the protocol's defined zero pad.
        moveq   #0,d1
        move.b  (a0)+,d1
        lsl.l   #8,d1
        moveq   #0,d4
        move.b  (a0)+,d4
        or.l    d4,d1
        lsl.l   #8,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .failed

        bsr     dsp_c2p_get
        tst.l   d0
        bne     .failed
        cmpi.l  #C2P_REPLY_SCANLINE,d1
        beq     .reply_magic_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .failed
.reply_magic_ok
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .failed
        cmp.l   d3,d1
        beq     .reply_sequence_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .failed
.reply_sequence_ok

        ; 106 complete words produce planar bytes 0..317.
        moveq   #C2P_SCANLINE_WORDS-2,d2
.receive_three
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .failed
        move.l  d1,d4
        lsr.l   #8,d4
        lsr.l   #8,d4
        move.b  d4,(a1)+
        move.l  d1,d4
        lsr.l   #8,d4
        move.b  d4,(a1)+
        move.b  d1,(a1)+
        dbra    d2,.receive_three

        ; Final packed word supplies bytes 318, 319, and its ignored pad.
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .failed
        move.l  d1,d4
        lsr.l   #8,d4
        lsr.l   #8,d4
        move.b  d4,(a1)+
        move.l  d1,d4
        lsr.l   #8,d4
        move.b  d4,(a1)+

        addq.l  #1,d3
        andi.l  #$00ffffff,d3
        dbra    d5,.row
        move.l  d3,dsp_c2p_sequence
        moveq   #DSP_C2P_OK,d0
        bra     .done
.failed
        move.w  d0,dsp_c2p_status
.done
        movem.l (sp)+,d1-d5/a0-a1
        rts

; Load and validate the worker.  The status is kept in BSS for debugger or
; UI diagnostics; callers only need the return code and must not retry every
; frame after a failure.
;
; Out: d0 = DSP_C2P_OK, otherwise one DSP_C2P_ERR_* value.
dsp_c2p_init
        movem.l d1-d3/a0-a2,-(sp)
        moveq   #DSP_C2P_ERR_ABSENT,d0
        move.w  d0,dsp_c2p_status

        Dsp_Available dsp_c2p_xavail,dsp_c2p_yavail
        move.l  dsp_c2p_xavail,d1
        cmpi.l  #DSP_C2P_X_WORDS,d1
        blt     .done
        move.l  dsp_c2p_yavail,d1
        tst.l   d1
        blt     .done

        moveq   #DSP_C2P_ERR_RESERVE,d0
        move.w  d0,dsp_c2p_status
        Dsp_Reserve #DSP_C2P_X_WORDS,#DSP_C2P_Y_WORDS
        tst.l   d0
        bne     .done

        moveq   #DSP_C2P_ERR_LOAD,d0
        move.w  d0,dsp_c2p_status
        Dsp_LoadProgram dsp_c2p_lod_name,#0,dsp_c2p_lod_buffer
        tst.l   d0
        bne     .done

        ; Dsp_LoadProgram may leave a bootstrap response queued.  Drain a
        ; finite number before sending a request, so an old word cannot
        ; masquerade as the C2P hello reply.
        moveq   #8,d2
.drain
        btst    #ISR_RXDF,$ffffa202.w
        beq     .drained
        move.l  $ffffa204.w,d1
        dbra    d2,.drain
.drained
        move.l  #C2P_CMD_PING,d1
        bsr     dsp_c2p_put
        tst.l   d0
        bne     .done
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmpi.l  #C2P_REPLY_HELLO,d1
        beq     .hello_magic_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .done
.hello_magic_ok
        bsr     dsp_c2p_get
        tst.l   d0
        bne     .done
        cmpi.l  #C2P_PROTOCOL_VERSION,d1
        beq     .version_ok
        moveq   #DSP_C2P_ERR_PROTOCOL,d0
        bra     .done
.version_ok
        bsr     dsp_c2p_loopback
        tst.l   d0
        bne     .done
        bsr     dsp_c2p_vector_test
.done
        move.w  d0,dsp_c2p_status
        movem.l (sp)+,d1-d3/a0-a2
        rts

        data
dsp_c2p_lod_name
        dc.b    'WC1C2P.LOD',0
        even
        include "dsp/c2p_test_vector.inc"

        bss
        even
dsp_c2p_status ds.w    1
dsp_c2p_vector_index
                ds.w    1
dsp_c2p_vector_actual
                ds.l    1
dsp_c2p_vector_expected
                ds.l    1
dsp_c2p_sequence
                ds.l    1
dsp_c2p_xavail ds.l    1
dsp_c2p_yavail ds.l    1
dsp_c2p_lod_buffer
                ds.b    DSP_C2P_LOD_BYTES

        end
