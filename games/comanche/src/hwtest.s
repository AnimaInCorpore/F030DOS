; Hardware test report (HWTEST=1 builds only).
;
; Kind: N/A - target diagnostic with no DOS counterpart. It changes nothing
; the game does: it reads counters at three points and, after the machine has
; been handed back to TOS, writes HWTEST.TXT next to the program:
;
;   the machine     cookies (_CPU, _MCH, _VDO, _FPU, CT60), TOS version and
;                   whether it is EmuTOS, the monitor (VgetMonitor) and the
;                   Videl timing the port chose, the 68060's CACR and PCR,
;                   where TOS loaded the program and how much TT-RAM was free
;   the clock       VBLs against the 200 Hz system timer: the refresh rate
;   the frames      per kind of flight frame (the attract's recorded flights,
;                   live play): frames, VBLs, frames per second, and how many
;                   VBLs each frame took (1..8, more)
;   the music       OPL2 builds: whether the DSP stream ran, its periods
;                   against the elapsed time, refill protocol errors
;
; Entry points: hwtest_begin (end of init, supervisor), hwtest_loop (head of
; the main loop), hwtest_frame (after each flight frame is published),
; hwtest_end (start of deinit, supervisor), hwtest_write (end of deinit, user
; mode, before Pterm). A flight frame is timed only when the loop iteration
; before it was a flight frame too: the first one after a title screen, a
; menu or a mission end would otherwise carry that screen's time.

        include "inc/gemdos.s"
        include "inc/cpu.s"

    ifne HWTEST

        global  hwtest_begin, hwtest_loop, hwtest_frame, hwtest_end, hwtest_write
        xref    frame_count, demo_active, _main, snd_opl_mode
    ifne OPL2
        xref    opl_host_periods, opl_host_errors
    endc

HW_KINDS        = 2                     ; 0 attract flight, 1 live flight
HW_BUCKETS      = 9                     ; 1..8 VBLs, then more
HW_GAP          = 60                    ; a longer wait is a load, not a frame

; per kind: frames, VBLs, worst, gaps, buckets
K_FRAMES        = 0
K_VBLS          = 4
K_WORST         = 8
K_GAPS          = 12
K_HIST          = 16
K_SIZE          = K_HIST+4*HW_BUCKETS

        text

; ------------------------------------------------------------------ begin
hwtest_begin
        movem.l d0-d2/a0-a2,-(sp)
        move.l  $4ba.w,hw_t0
        move.l  frame_count,hw_v0
        ; cookies
        move.l  $5a0.w,a0
        move.l  a0,d0
        beq.s   .no_jar
.cookie
        move.l  (a0)+,d0
        beq.s   .no_jar
        move.l  (a0)+,d1
        lea     hw_cookie_ids,a1
        lea     hw_cookie_vals,a2
.match
        move.l  (a1)+,d2
        beq.s   .cookie
        cmp.l   d2,d0
        beq.s   .found
        addq.l  #4,a2
        bra.s   .match
.found
        move.l  d1,(a2)
        move.l  #1,hw_cookie_found-hw_cookie_vals(a2)
        bra.s   .cookie
.no_jar
        ; TOS: the OS header's version word, and EmuTOS's 'ETOS' at +$2C
        move.l  $4f2.w,a0
        move.l  8(a0),a0                        ; os_beg: the ROM's own header
        move.w  2(a0),hw_tos
        cmpi.l  #'ETOS',$2c(a0)
        seq     hw_emutos
        move.b  $ffff8006.w,hw_monbits
    ifeq TARGET_CPU-68060
        movec   cacr,d0
        move.l  d0,hw_cacr
        movec   pcr,d0
        move.l  d0,hw_pcr
    endc
        movem.l (sp)+,d0-d2/a0-a2
        rts

; ------------------------------------------------------------------ frame
hwtest_loop
        addq.w  #1,hw_iter
        rts

hwtest_frame
        movem.l d0-d2/a0,-(sp)
        move.l  frame_count,d0
        move.l  hw_last,d1
        move.l  d0,hw_last
        move.w  hw_iter,d2
        clr.w   hw_iter
        tst.w   hw_started
        bne.s   .counted
        move.w  #1,hw_started
        move.l  $4ba.w,hw_tf
    ifne OPL2
        move.l  opl_host_periods,hw_pf
    endc
        bra.s   .out
.counted
        sub.l   d1,d0                           ; VBLs since the last flight frame
        lea     hw_kind,a0
        tst.w   demo_active
        bne.s   .kind
        lea     K_SIZE(a0),a0
.kind
        cmpi.w  #1,d2                           ; a screen ran in between
        bne.s   .untimed
        cmpi.l  #HW_GAP,d0
        bls.s   .frame
.untimed
        addq.l  #1,K_GAPS(a0)
        bra.s   .out
.frame
        addq.l  #1,K_FRAMES(a0)
        add.l   d0,K_VBLS(a0)
        cmp.l   K_WORST(a0),d0
        bls.s   .worst
        move.l  d0,K_WORST(a0)
.worst
        subq.l  #1,d0
        bpl.s   .bucket
        moveq   #0,d0                           ; two flips in one VBL
.bucket
        cmpi.l  #HW_BUCKETS-1,d0
        bls.s   .in
        moveq   #HW_BUCKETS-1,d0
.in
        lsl.l   #2,d0
        addq.l  #1,K_HIST(a0,d0.l)
.out
        movem.l (sp)+,d0-d2/a0
        rts

; ------------------------------------------------------------------ end
hwtest_end
        move.l  $4ba.w,hw_t1
        move.l  frame_count,hw_v1
    ifne OPL2
        move.l  opl_host_periods,hw_p1
        move.l  opl_host_errors,hw_errors
    endc
        move.w  snd_opl_mode,hw_opl
        rts

; ------------------------------------------------------------------ write
; User mode, the machine back with TOS: GEMDOS and XBIOS are safe.
hwtest_write
        movem.l d0-d7/a0-a6,-(sp)
        move.w  #89,-(sp)                       ; VgetMonitor
        trap    #14
        addq.l  #2,sp
        move.w  d0,hw_monitor
        Mxalloc #-1,#1                          ; largest free TT-RAM block
        move.l  d0,hw_ttfree
        Mxalloc #-1,#0
        move.l  d0,hw_stfree

        lea     hw_text,a6
        lea     t_head,a0
        bsr     put_str

        ; machine
        lea     t_cpu,a0
        bsr     put_str
        lea     hw_cookie_vals,a1
        lea     hw_cookie_found,a2
        lea     hw_cookie_ids,a3
.cookies
        move.l  (a3)+,d0
        beq.s   .cookies_done
        lea     t_cookie,a0
        bsr     put_str
        move.l  d0,d1
        moveq   #3,d2
.id
        rol.l   #8,d1
        move.b  d1,(a6)+
        dbra    d2,.id
        move.b  #' ',(a6)+
        tst.l   (a2)+
        bne.s   .have
        lea     t_absent,a0
        bsr     put_str
        addq.l  #4,a1
        bra.s   .cookies
.have
        move.b  #'$',(a6)+
        move.l  (a1)+,d0
        bsr     put_hex8
        bsr     put_nl
        bra.s   .cookies
.cookies_done
        lea     t_tos,a0
        bsr     put_str
        moveq   #0,d0
        move.w  hw_tos,d0
        moveq   #4,d1
        bsr     put_hexn
        tst.b   hw_emutos
        beq.s   .not_emutos
        lea     t_emutos,a0
        bsr     put_str
.not_emutos
        bsr     put_nl
        lea     t_monitor,a0
        bsr     put_str
        moveq   #0,d0
        move.w  hw_monitor,d0
        bsr     put_dec
        lea     t_monnames,a0
        move.w  hw_monitor,d0
        cmpi.w  #3,d0
        bls.s   .mon
        moveq   #4,d0
.mon
        bsr     put_nth
        lea     t_videl,a0
        bsr     put_str
        lea     t_rgb,a0
        btst    #6,hw_monbits
        bne.s   .rgb
        lea     t_vga,a0
.rgb
        bsr     put_str
    ifeq TARGET_CPU-68060
        lea     t_cacr,a0
        bsr     put_str
        move.l  hw_cacr,d0
        bsr     put_hex8
        lea     t_pcr,a0
        bsr     put_str
        move.l  hw_pcr,d0
        bsr     put_hex8
        bsr     put_nl
    endc
        lea     t_load,a0
        bsr     put_str
        move.l  #_main,d0
        bsr     put_hex8
        lea     t_inst,a0
        cmpi.l  #$01000000,d0
        bhs.s   .tt
        lea     t_inst_st,a0
.tt
        bsr     put_str
        lea     t_ttfree,a0
        bsr     put_str
        move.l  hw_ttfree,d0
        bpl.s   .ttok
        moveq   #0,d0
.ttok
        lsr.l   #8,d0
        lsr.l   #2,d0
        bsr     put_dec
        lea     t_stfree,a0
        bsr     put_str
        move.l  hw_stfree,d0
        lsr.l   #8,d0
        lsr.l   #2,d0
        bsr     put_dec
        lea     t_kb,a0
        bsr     put_str

        ; clock
        move.l  hw_t1,d7
        sub.l   hw_t0,d7
        mulu.l  #5,d7                           ; elapsed ms
        move.l  hw_v1,d6
        sub.l   hw_v0,d6                        ; VBLs
        lea     t_run,a0
        bsr     put_str
        move.l  d7,d0
        divu.l  #1000,d0
        bsr     put_dec
        lea     t_seconds,a0
        bsr     put_str
        move.l  d6,d0
        bsr     put_dec
        lea     t_vbls,a0
        bsr     put_str
        ; refresh in mHz: VBLs*1000*1000/ms, kept in 32 bits
        moveq   #0,d5
        tst.l   d7
        beq.s   .no_rate
        move.l  d6,d0
        mulu.l  #1000,d0
        divu.l  d7,d0                           ; Hz, whole
        move.l  d0,d5
        mulu.l  #1000,d5
        move.l  d6,d1
        mulu.l  #1000,d1
        move.l  d1,d2
        divu.l  d7,d2
        mulu.l  d7,d2
        sub.l   d2,d1                           ; remainder of VBLs*1000/ms
        mulu.l  #1000,d1
        divu.l  d7,d1
        add.l   d1,d5                           ; mHz
.no_rate
        move.l  d5,d0
        moveq   #3,d1
        bsr     put_fixed
        lea     t_hz,a0
        bsr     put_str
        move.l  d5,hw_mhz

        ; frames
        lea     hw_kind,a5
        lea     t_kind0,a4
        moveq   #HW_KINDS-1,d4
.kinds
        move.l  a4,a0
        bsr     put_str
        move.l  K_FRAMES(a5),d0
        bsr     put_dec
        lea     t_frames,a0
        bsr     put_str
        move.l  K_VBLS(a5),d0
        bsr     put_dec
        lea     t_vbls2,a0
        bsr     put_str
        move.l  K_FRAMES(a5),d3
        beq     .no_frames
        move.l  K_VBLS(a5),d2
        beq     .no_frames
        ; fps x100 = frames * Hz / VBLs = (frames*1000/VBLs) * (mHz/10) / 10000
        move.l  d3,d0
        mulu.l  #1000,d0
        divu.l  d2,d0
        move.l  hw_mhz,d1
        divu.l  #10,d1
        mulu.l  d1,d0
        divu.l  #1000,d0
        moveq   #2,d1
        bsr     put_fixed
        lea     t_fps,a0
        bsr     put_str
        move.l  d2,d0
        mulu.l  #100,d0
        divu.l  d3,d0
        moveq   #2,d1
        bsr     put_fixed
        lea     t_per,a0
        bsr     put_str
        move.l  K_WORST(a5),d0
        bsr     put_dec
        lea     t_worst,a0
        bsr     put_str
        move.l  K_GAPS(a5),d0
        bsr     put_dec
        lea     t_gaps,a0
        bsr     put_str
        lea     t_hist,a0
        bsr     put_str
        lea     K_HIST(a5),a3
        moveq   #1,d3
.hist
        move.l  d3,d0
        bsr     put_dec
        cmpi.w  #HW_BUCKETS,d3
        bne.s   .hist_n
        move.b  #'+',(a6)+
.hist_n
        move.b  #':',(a6)+
        move.l  (a3)+,d0
        bsr     put_dec
        move.b  #' ',(a6)+
        addq.w  #1,d3
        cmpi.w  #HW_BUCKETS,d3
        bls.s   .hist
        bsr     put_nl
        bra.s   .kind_next
.no_frames
        bsr     put_nl
.kind_next
        lea     K_SIZE(a5),a5
        lea     t_kind1,a4
        dbra    d4,.kinds

        ; music
        lea     t_music,a0
        bsr     put_str
    ifne OPL2
        tst.w   hw_opl
        bne.s   .dsp
        lea     t_nodsp,a0
        bsr     put_str
        bra     .music_done
.dsp
        lea     t_dsp,a0
        bsr     put_str
        move.l  hw_p1,d0
        sub.l   hw_pf,d0
        move.l  d0,d3
        bsr     put_dec
        lea     t_periods,a0
        bsr     put_str
        ; a period is 768 frames at 49,169.92 Hz: 15.619 ms
        move.l  d3,d0
        mulu.l  #15619,d0
        divu.l  #1000,d0                        ; ms of sound sent
        move.l  d0,d2
        divu.l  #100,d0
        moveq   #1,d1
        bsr     put_fixed
        lea     t_of,a0
        bsr     put_str
        move.l  hw_t1,d0
        sub.l   hw_tf,d0
        mulu.l  #5,d0                           ; ms since the first frame
        move.l  d0,d1
        divu.l  #100,d0
        moveq   #1,d1
        bsr     put_fixed
        lea     t_secs2,a0
        bsr     put_str
        move.l  hw_errors,d0
        bsr     put_dec
        lea     t_errors,a0
        bsr     put_str
.music_done
    else
        lea     t_nobuild,a0
        bsr     put_str
    endc

        ; HWTEST.TXT
        Fcreate hw_name,#0
        tst.l   d0
        bmi.s   .out
        move.w  d0,d7
        move.l  a6,d6
        sub.l   #hw_text,d6
        Fwrite  d7,d6,hw_text
        Fclose  d7
.out
        movem.l (sp)+,d0-d7/a0-a6
        rts

; ------------------------------------------------------------------ text
; a0 = zero-terminated string -> a6
put_str
        move.b  (a0)+,(a6)+
        bne.s   put_str
        subq.l  #1,a6
        rts

put_nl
        move.b  #13,(a6)+
        move.b  #10,(a6)+
        rts

; a0 = strings separated by zero bytes, d0.w = index
put_nth
.skip
        subq.w  #1,d0
        bmi.s   put_str
.z
        tst.b   (a0)+
        bne.s   .z
        bra.s   .skip

; d0.l unsigned -> decimal
put_dec
        movem.l d0-d2/a0,-(sp)
        lea     hw_digits+12,a0
        clr.b   -(a0)
.div
        move.l  d0,d1
        divu.l  #10,d0
        move.l  d0,d2
        mulu.l  #10,d2
        sub.l   d2,d1
        addi.b  #'0',d1
        move.b  d1,-(a0)
        tst.l   d0
        bne.s   .div
        bsr     put_str
        movem.l (sp)+,d0-d2/a0
        rts

; d0.l unsigned with d1 decimals (1..3) -> "w.ddd"
put_fixed
        movem.l d0-d3,-(sp)
        moveq   #10,d2
        cmpi.w  #1,d1
        beq.s   .p
        moveq   #100,d2
        cmpi.w  #2,d1
        beq.s   .p
        move.l  #1000,d2
.p
        move.l  d0,d3
        divu.l  d2,d0
        bsr     put_dec
        move.b  #'.',(a6)+
        mulu.l  d2,d0
        sub.l   d0,d3                           ; the fraction
.frac
        divu.l  #10,d2
        move.l  d3,d0
        divu.l  d2,d0                           ; the next digit
        move.l  d0,d1
        addi.b  #'0',d1
        move.b  d1,(a6)+
        mulu.l  d2,d0
        sub.l   d0,d3
        cmpi.l  #1,d2
        bne.s   .frac
        movem.l (sp)+,d0-d3
        rts

put_hex8
        moveq   #8,d1
; d0.l, d1 = digits
put_hexn
        movem.l d0-d2,-(sp)
        move.l  d1,d2
        subq.w  #1,d2
        neg.w   d1
        addq.w  #8,d1
        lsl.w   #2,d1
        rol.l   d1,d0                           ; skip the unused high digits
.h
        rol.l   #4,d0
        move.b  d0,d1
        andi.w  #15,d1
        move.b  hw_hex(pc,d1.w),(a6)+
        dbra    d2,.h
        movem.l (sp)+,d0-d2
        rts
hw_hex  dc.b    "0123456789ABCDEF"
        even

        data
hw_name         dc.b    "HWTEST.TXT",0
t_head          dc.b    "Comanche Falcon port - hardware test report (HWTEST=1)",13,10
            ifeq TARGET_CPU-68060
                dc.b    "Build: 68060 image"
            else
                dc.b    "Build: 68030 image"
            endc
            ifne OPL2
                dc.b    ", OPL2 music on the DSP"
            endc
                dc.b    13,10,13,10,0
t_cpu           dc.b    "[machine]",13,10,0
t_cookie        dc.b    "cookie ",0
t_absent        dc.b    "absent",13,10,0
t_tos           dc.b    "TOS version $",0
t_emutos        dc.b    " (EmuTOS)",0
t_monitor       dc.b    "monitor ",0
t_monnames      dc.b    " (mono)",13,10,0
                dc.b    " (RGB/colour)",13,10,0
                dc.b    " (VGA)",13,10,0
                dc.b    " (TV)",13,10,0
                dc.b    " (unknown)",13,10,0
t_videl         dc.b    "Videl timing used: ",0
t_rgb           dc.b    "RGB/TV",13,10,0
t_vga           dc.b    "VGA",13,10,0
t_cacr          dc.b    "68060 CACR $",0
t_pcr           dc.b    "  PCR $",0
t_load          dc.b    "program loaded at $",0
t_inst          dc.b    " (TT-RAM)",13,10,0
t_inst_st       dc.b    " (ST-RAM)",13,10,0
t_ttfree        dc.b    "free at exit: TT-RAM ",0
t_stfree        dc.b    " KB, ST-RAM ",0
t_kb            dc.b    " KB",13,10,13,10,0
t_run           dc.b    "[clock]",13,10,"run ",0
t_seconds       dc.b    " s, ",0
t_vbls          dc.b    " VBLs, refresh ",0
t_hz            dc.b    " Hz",13,10,13,10,"[frames]",13,10,0
t_kind0         dc.b    "attract flights: ",0
t_kind1         dc.b    "live flight:     ",0
t_frames        dc.b    " frames, ",0
t_vbls2         dc.b    " VBLs, ",0
t_fps           dc.b    " fps, ",0
t_per           dc.b    " VBLs a frame, worst ",0
t_worst         dc.b    ", not timed (after a screen or load) ",0
t_gaps          dc.b    0
t_hist          dc.b    13,10,"  VBLs per frame: ",0
t_music         dc.b    13,10,"[music]",13,10,0
t_nodsp         dc.b    "the DSP stream did not start (OPLDATA.BIN missing, or the DSP was busy)",13,10,0
t_dsp           dc.b    "DSP stream: ",0
t_periods       dc.b    " periods since the first frame = ",0
t_of            dc.b    " s of sound in ",0
t_secs2         dc.b    " s, protocol errors ",0
t_errors        dc.b    13,10,0
t_nobuild       dc.b    "not an OPL2 build",13,10,0
        even
hw_cookie_ids   dc.b    "_CPU_MCH_VDO_FPUCT60_SND"
                dc.l    0
        even

        bss
        even
hw_cookie_vals  ds.l    6
hw_cookie_found ds.l    6
hw_emutos       ds.b    1
hw_monbits      ds.b    1
        even
hw_tos          ds.w    1
hw_monitor      ds.w    1
hw_opl          ds.w    1
hw_started      ds.w    1
hw_iter         ds.w    1
hw_cacr         ds.l    1
hw_pcr          ds.l    1
hw_ttfree       ds.l    1
hw_stfree       ds.l    1
hw_t0           ds.l    1
hw_t1           ds.l    1
hw_tf           ds.l    1
hw_v0           ds.l    1
hw_v1           ds.l    1
hw_pf           ds.l    1
hw_p1           ds.l    1
hw_errors       ds.l    1
hw_last         ds.l    1
hw_mhz          ds.l    1
hw_kind         ds.b    K_SIZE*HW_KINDS
hw_digits       ds.b    12
hw_text         ds.b    4096

    endc
