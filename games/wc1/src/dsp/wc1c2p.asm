; Legacy WC1 Falcon DSP56001 C2P transport worker (diagnostic only).
;
; C2P_CMD_SCANLINE receives a source row as 107 packed 24-bit words, expands
; its 320 palette indices, forms the Falcon's 20 * (8 planes * 16 pixels)
; big-endian cells, then returns that 320-byte planar row as 107 packed words.
; C2P_CMD_LOOPBACK retains the old exact echo solely for host-port diagnostics.
; The game no longer links this worker; its display path uses RGB565 pages.

        opt     mu,nohdr
        include 'ioequ.inc'
        include 'c2pproto.inc'

X_SEQUENCE      EQU     $0000
X_RAW            EQU     $0040   ; 107 packed input words
X_PIXELS         EQU     $0100   ; 321 unpacked bytes (one zero pad)
X_PLANAR_BYTES   EQU     $0300   ; 320 output bytes plus one zero pad
X_PACKED         EQU     $0500   ; 107 packed planar reply words

C2P_CELLS       EQU     20
C2P_CELL_PIXELS EQU     16
C2P_PLANES      EQU     8

        org     p:$0000
        jmp     c2p_main

        org     p:$0040
c2p_main:
        ; Match Falcon DSP ports: host interface enabled, no external-SRAM
        ; wait states, and no DSP interrupts. All servicing is polling based.
        movep   #1,x:m_pbc
        bclr    #m_hf2,x:m_hcr
        movep   #0,x:m_bcr

c2p_command_loop:
        jclr    #m_hrdf,x:m_hsr,*
        movep   x:m_hrx,a
        move    #>C2P_CMD_PING,x0
        cmp     x0,a
        jeq     c2p_ping
        move    #>C2P_CMD_LOOPBACK,x0
        cmp     x0,a
        jeq     c2p_loopback
        move    #>C2P_CMD_SCANLINE,x0
        cmp     x0,a
        jeq     c2p_scanline
        move    #>C2P_REPLY_BAD_COMMAND,x0
        jsr     c2p_send_word
        jmp     c2p_command_loop

c2p_ping:
        ; Ping returns protocol version in the low bits. The host gates use
        ; of the worker on both this magic and the version value.
        move    #>C2P_REPLY_HELLO,x0
        jsr     c2p_send_word
        move    #>C2P_PROTOCOL_VERSION,x0
        jsr     c2p_send_word
        jmp     c2p_command_loop

c2p_scanline:
        jsr     c2p_receive_raw
        jsr     c2p_unpack_pixels
        jsr     c2p_convert_cells
        jsr     c2p_pack_planar

        move    #>C2P_REPLY_SCANLINE,x0
        jsr     c2p_send_word
        move    x:<X_SEQUENCE,x0
        jsr     c2p_send_word
        move    #X_PACKED,r0
        do      #C2P_SCANLINE_WORDS,c2p_scanline_sent
        jclr    #m_htde,x:m_hsr,*
        movep   x:(r0)+,x:m_htx
c2p_scanline_sent:
        jmp     c2p_command_loop

; C2P_CMD_LOOPBACK is intentionally separate from the production command.
; It remains a stable, byte-exact host-port diagnostic whenever the C2P core
; changes or is optimized.
c2p_loopback:
        jsr     c2p_receive_raw

        move    #>C2P_REPLY_SCANLINE,x0
        jsr     c2p_send_word
        move    x:<X_SEQUENCE,x0
        jsr     c2p_send_word
        move    #X_RAW,r0
        do      #C2P_SCANLINE_WORDS,c2p_loopback_sent
        jclr    #m_htde,x:m_hsr,*
        movep   x:(r0)+,x:m_htx
c2p_loopback_sent:
        jmp     c2p_command_loop

; Fixed length is intentional: a host-port protocol cannot recover after an
; ambiguous variable payload.  The pure jclr/movep DO body drains the host
; port without arithmetic between reads.
c2p_receive_raw:
        jclr    #m_hrdf,x:m_hsr,*
        movep   x:m_hrx,x:<X_SEQUENCE
        move    #X_RAW,r0
        do      #C2P_SCANLINE_WORDS,c2p_receive_done
        jclr    #m_hrdf,x:m_hsr,*
        movep   x:m_hrx,x:(r0)+
c2p_receive_done:
        rts

; Expand the 107 24-bit words into byte-valued X words.  The final stored
; word is the deliberate source-row pad; cell conversion consumes 320 only.
c2p_unpack_pixels:
        move    #X_RAW,r0
        move    #X_PIXELS,r1
        do      #C2P_SCANLINE_WORDS,c2p_unpack_done
        move    x:(r0)+,a
        tfr     a,b
        rep     #16
        asr     a
        move    a1,x:(r1)+
        tfr     b,a
        rep     #8
        asr     a
        move    a1,x:(r1)+
        move    b1,x:(r1)+
c2p_unpack_done:
        rts

; Convert one 16-pixel cell at a time.  x1 is the palette-bit mask for the
; current plane.  Shifting the accumulator before each source index yields
; MSB-first Falcon words: source pixel zero becomes bit 15.
c2p_convert_cells:
        move    #X_PIXELS,r2
        move    #X_PLANAR_BYTES,r3
        move    #C2P_CELL_PIXELS,n2
        move    #>$0000ff,y0
        do      #C2P_CELLS,c2p_cells_done
        move    #>1,x1
        do      #C2P_PLANES,c2p_planes_done
        move    r2,r0
        clr     a
        do      #C2P_CELL_PIXELS,c2p_pixels_done
        asl     a
        move    x:(r0)+,x0
        move    x0,b
        and     x1,b
        ; AND affects b1 only.  Clear B0 before TST or residue from a prior
        ; accumulator use turns a zero palette bit into a false plane bit.
        move    b1,b
        tst     b
        jeq     c2p_pixel_zero
        move    #>1,x0
        add     x0,a
c2p_pixel_zero:
c2p_pixels_done:
        move    a1,b
        rep     #8
        asr     b
        and     y0,b
        move    b1,x:(r3)+
        and     y0,a
        move    a1,x:(r3)+
        move    x1,a
        asl     a
        move    a1,x1
c2p_planes_done:
        move    x:(r2)+n2,x0
c2p_cells_done:
        clr     a
        move    a,x:(r3)        ; byte 320: defined zero transport pad
        rts

; Repack the byte stream as [byte0:byte1:byte2] 24-bit words.  Each source
; byte is intentionally held in its low eight bits before its field shift.
c2p_pack_planar:
        move    #X_PLANAR_BYTES,r0
        move    #X_PACKED,r1
        do      #C2P_SCANLINE_WORDS,c2p_pack_done
        move    x:(r0)+,a
        rep     #16
        asl     a
        move    a1,x0
        move    x:(r0)+,a
        rep     #8
        asl     a
        add     x0,a
        move    a1,x0
        move    x:(r0)+,a
        add     x0,a
        move    a1,x:(r1)+
c2p_pack_done:
        rts

; In: x0 = 24-bit word. Out: host transmit register accepts it.
c2p_send_word:
        jclr    #m_htde,x:m_hsr,*
        movep   x0,x:m_htx
        rts

        end
