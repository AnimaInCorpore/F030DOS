; Minimal real-Falcon/Hatari verification executable for WC1C2P.LOD.
;
; It keeps the gameplay binary clean: this program enters supervisor mode,
; invokes the same bounded host loader used by WC1, then prints the specific
; result on TOS console output.  `make dsp-wire-smoke` is therefore a direct
; check of the actual DSP host port rather than an inferred CPU fallback.

        include "../src/inc/gemdos.s"

        xdef    _main
        xref    dsp_c2p_init
        xref    dsp_c2p_convert
        xref    dsp_c2p_status
        xref    dsp_c2p_vector_index
        xref    dsp_c2p_vector_actual
        xref    dsp_c2p_vector_expected

        text

_main
        Super   0
        move.l  d0,saved_ssp
        bsr     dsp_c2p_init

        ; Run the production 200-row host streamer after its per-row golden
        ; tests.  BSS is zeroed by TOS, so a successful return proves all
        ; 200 packets complete without requiring a fourth game framebuffer.
        tst.w   dsp_c2p_status
        bne     .record
        pea     frame_planar
        pea     frame_chunky
        bsr     dsp_c2p_convert
        addq.l  #8,sp
.record
        move.l  saved_ssp,a0
        Super   (a0)

        ; Hatari's console redirection does not consistently forward GEMDOS
        ; Cconws output.  Persist the signed result as one big-endian word so
        ; the Make target can assert the actual hardware test outcome.
        bsr     write_status

        tst.w   dsp_c2p_status
        beq     .pass
        cmpi.w  #-1,dsp_c2p_status
        beq     .absent
        cmpi.w  #-2,dsp_c2p_status
        beq     .reserve
        cmpi.w  #-3,dsp_c2p_status
        beq     .load
        cmpi.w  #-4,dsp_c2p_status
        beq     .timeout
        cmpi.w  #-5,dsp_c2p_status
        beq     .protocol
        Cconws  loopback_message
        Pterm0
.pass
        Cconws  pass_message
        Pterm0
.absent
        Cconws  absent_message
        Pterm0
.reserve
        Cconws  reserve_message
        Pterm0
.load
        Cconws  load_message
        Pterm0
.timeout
        Cconws  timeout_message
        Pterm0
.protocol
        Cconws  protocol_message
        Pterm0

write_status
        move.w  dsp_c2p_status,d1
        move.w  d1,status_word
        move.w  dsp_c2p_vector_index,vector_index
        move.l  dsp_c2p_vector_actual,vector_actual
        move.l  dsp_c2p_vector_expected,vector_expected
        Fcreate status_filename,#0
        tst.l   d0
        blt     .done
        move.w  d0,d1
        Fwrite  d1,#12,status_word
        Fclose  d1
.done
        rts

        data
status_filename
        dc.b    'DSPWIRE.BIN',0
        even
pass_message
        dc.b    'WC1 DSP C2P wire: PASS',13,10,0
absent_message
        dc.b    'WC1 DSP C2P wire: DSP absent',13,10,0
reserve_message
        dc.b    'WC1 DSP C2P wire: reserve failed',13,10,0
load_message
        dc.b    'WC1 DSP C2P wire: LOD load failed',13,10,0
timeout_message
        dc.b    'WC1 DSP C2P wire: host timeout',13,10,0
protocol_message
        dc.b    'WC1 DSP C2P wire: protocol mismatch',13,10,0
loopback_message
        dc.b    'WC1 DSP C2P wire: payload mismatch',13,10,0

        bss
        even
saved_ssp
        ds.l    1
status_word
        ds.w    1
vector_index
        ds.w    1
vector_actual
        ds.l    1
vector_expected
        ds.l    1
frame_chunky
        ds.b    64000
frame_planar
        ds.b    64000

        end
