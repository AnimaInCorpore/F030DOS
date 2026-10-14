; N/A - target artefact: a stand-alone test program for the Falcon output path
; of src/sound.s (DMA ring, VBL refill, resampler), no DOS routine.
; Record: analysis/functions/sound-falcon.md#verification
;
; Brings the digital layer up exactly as the game does (snd_init reads
; COMANCHE.CFG, snd_banks_load, snd_apply_sound with the Loud radio), installs a
; VBL handler that calls snd_vbl and chains to TOS's, and plays a timeline:
;
;   VBL  40   SND1 id 1 (explosion), as 00022876 with dl = 0
;   VBL 250   SND1 id 3 staged on slot 2, dl 2 (the rotor loop, 000189A0)
;   VBL 400   SPEAK1 id 6 (the mission-start voice, 00006A0E)
;   VBL 560   Sound Off (the radio's MODE(0)): the output stops
;   VBL 600   done
;
; and writes DMASTAT.TXT (refills, underruns, bytes made, counters), DMARING.BIN (every
; byte the refill wrote into the ring, in order) and the sentinel SNDDONE.TXT.
; tools/check-falcon-dma.py records Hatari's audio output meanwhile.

        include "inc/comanche.s"
        include "inc/gemdos.s"

        global  _main
        global  resource_buffer, menu_settings, frame_count

        xref    snd_init, snd_banks_load, snd_apply_sound, snd_fx, snd_speech_a
        xref    snd_voice, snd_sample_ptr, snd_vbl, snd_shutdown, snd_mode
        xref    snd_bank_fx, snd_digital, snd_stats, snd_wr, snd_ring
        xref    snd_rs_phase, snd_rs_have

LOG_BYTES       = 196608
LOG2_BYTES      = 65536

        text
_main
        move.l  4(sp),a0
        move.l  #256,d0
        add.l   12(a0),d0
        add.l   20(a0),d0
        add.l   28(a0),d0
        Mshrink a0,d0
        Super   0
        move.l  d0,savssp
        lea     main_stack,sp
        move    #$2300,sr

        move.b  #'0',menu_settings+1
        bsr     snd_init
        bsr     snd_banks_load
        move.b  snd_digital,digital_seen

        ; the VBL: log what the refill writes, then TOS's own handler
        movec   vbr,d0
        move.l  d0,a0
        move.l  $70(a0),old_vbl
        move.l  #tvbl,$70(a0)

        ; CPU cost of the refill, by a fixed workload timed in VBLs: first with the
        ; mixer off, then (below) with the rotor, and with the rotor and a voice.
        bsr     workload
        move.l  d0,v_off
        move.l  vblcount,tl_base

        bsr     snd_apply_sound                 ; Sound Loud: the mixer on

        moveq   #40,d0
        bsr     wait_vbl
        moveq   #1,d4
        moveq   #-1,d1
        moveq   #0,d3
        moveq   #0,d2
        move.w  sr,-(sp)
        ori.w   #$0700,sr                       ; the state below and the request are one instant
        move.l  snd_rs_phase,req_phase
        move.l  snd_rs_have,req_have
        move.l  snd_wr,req_wr
        bsr     snd_fx                          ; explosion
        move.w  (sp)+,sr

        move.l  #250,d0
        bsr     wait_vbl
        move.l  snd_bank_fx,a0
        moveq   #3,d0
        bsr     snd_sample_ptr
        moveq   #2,d1
        moveq   #2,d3
        moveq   #0,d2
        bsr     snd_voice                       ; the rotor

        move.l  #255,d0
        bsr     wait_vbl
        bsr     workload                        ; the rotor alone is playing
        move.l  d0,v_rotor

        move.l  #330,d0
        bsr     wait_vbl
        move.l  snd_wr,w_l0                     ; the rotor on the Loud curve, from here ...
        move.l  #395,d0
        bsr     wait_vbl
        move.l  snd_wr,w_l1                     ; ... to here

        move.l  #400,d0
        bsr     wait_vbl
        moveq   #6,d0
        bsr     snd_speech_a
        moveq   #2,d0
        bsr     wait_vbl
        bsr     workload                        ; the rotor and the voice
        move.l  d0,v_voice

        ; Sound Soft (the radio, 00026CFB-00026D13): MODE resets the slots, so the rotor
        ; is staged again, as the Esc bar's close would (0001999D).
        move.l  #470,d0
        bsr     wait_vbl
        move.b  #'1',menu_settings+1
        bsr     snd_apply_sound
        move.l  snd_bank_fx,a0
        moveq   #3,d0
        bsr     snd_sample_ptr
        moveq   #2,d1
        moveq   #2,d3
        moveq   #0,d2
        bsr     snd_voice
        move.l  #485,d0
        bsr     wait_vbl
        move.l  snd_wr,w_s0                     ; the rotor on the Soft curve, from here ...
        move.l  #550,d0
        bsr     wait_vbl
        move.l  snd_wr,w_s1                     ; ... to here

        move.l  #560,d0
        bsr     wait_vbl
        move.b  #'2',menu_settings+1
        bsr     snd_apply_sound                 ; Sound Off

        move.l  #600,d0
        bsr     wait_vbl

        movec   vbr,d0
        move.l  d0,a0
        move.l  old_vbl,$70(a0)
        bsr     snd_shutdown

        ; DMASTAT.TXT: sixteen longs, big-endian: refills, underruns, bytes made, VBLs seen,
        ; logged bytes, digital flag after init, then the resampler phase, its buffered
        ; input bytes and the ring write count at the explosion request, and the
        ; VBLs the fixed workload took with the mixer off, with the rotor, with rotor + voice,
        ; and the ring write count at the start and end of a Loud and a Soft rotor window
        lea     stat_out,a0
        lea     snd_stats,a1
        move.l  (a1)+,(a0)+
        move.l  (a1)+,(a0)+
        move.l  (a1)+,(a0)+
        move.l  vblcount,(a0)+
        move.l  log_len,(a0)+
        moveq   #0,d0
        move.b  digital_seen,d0
        move.l  d0,(a0)+
        move.l  req_phase,(a0)+
        move.l  req_have,(a0)+
        move.l  req_wr,(a0)+
        move.l  v_off,(a0)+
        move.l  v_rotor,(a0)+
        move.l  v_voice,(a0)+
        move.l  w_l0,(a0)+
        move.l  w_l1,(a0)+
        move.l  w_s0,(a0)+
        move.l  w_s1,(a0)+
        lea     name_stat,a0
        lea     stat_out,a1
        moveq   #64,d0
        bsr     write_file
        lea     name_ring,a0
        lea     log,a1
        move.l  #LOG_BYTES,d0
        bsr     write_file
        lea     name_ring2,a0
        lea     log2,a1
        move.l  #LOG2_BYTES,d0
        bsr     write_file
        lea     name_done,a0
        lea     stat_out,a1
        moveq   #4,d0
        bsr     write_file
.hold
        bra     .hold

; A fixed amount of work, timed in VBLs. Out: d0 = VBLs it took.
workload
        move.l  vblcount,d1
        move.l  #8000000,d2
.spin
        subq.l  #1,d2
        bne     .spin
        move.l  vblcount,d0
        sub.l   d1,d0
        rts

; d0 = VBL count to wait for, from the timeline's start
wait_vbl
        add.l   tl_base,d0
.w
        cmp.l   vblcount,d0
        bhi     .w
        rts

; The VBL: refill (it saves what it uses), log the bytes it wrote, chain.
tvbl
        movem.l d0-d3/a0-a2,-(sp)
        addq.l  #1,vblcount
        move.l  snd_wr,d2                   ; bytes written so far, before
        cmp.l   last_wr,d2
        bhs.s   .same_epoch
        move.b  #1,epoch                        ; the DMA was restarted (a MODE call): wr starts over
.same_epoch
        move.l  d2,last_wr
        jsr     snd_vbl
        move.l  snd_wr,d3
        move.l  d3,last_wr
        sub.l   d2,d3                           ; bytes this refill wrote
        beq     .done
        move.l  snd_ring,a0
        lea     log,a1
        tst.b   epoch
        beq.s   .log_base
        lea     log2,a1                         ; the second run of the DMA has its own log
.log_base
        adda.l  d2,a1                           ; the log is indexed like the write count
        move.l  snd_wr,log_len
.copy
        move.l  d2,d0
        andi.l  #4095,d0
        move.b  0(a0,d0.l),(a1)+
        addq.l  #1,d2
        subq.l  #1,d3
        bne     .copy
.done
        movem.l (sp)+,d0-d3/a0-a2
        move.l  old_vbl,-(sp)
        rts

; a0 = name, a1 = bytes, d0 = count
write_file
        movem.l d0-d7/a0-a6,-(sp)
        move.l  d0,d6
        move.l  a1,a3
        clr.w   -(sp)
        move.l  a0,-(sp)
        move.w  #60,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .out
        move.w  d0,d7
        move.l  a3,-(sp)
        move.l  d6,-(sp)
        move.w  d7,-(sp)
        move.w  #64,-(sp)
        trap    #1
        lea     12(sp),sp
        move.w  d7,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
.out
        movem.l (sp)+,d0-d7/a0-a6
        rts

        data
name_stat
        dc.b    "DMASTAT.TXT",0
name_ring
        dc.b    "DMARING.BIN",0
name_ring2
        dc.b    "DMARIN2.BIN",0
name_done
        dc.b    "SNDDONE.TXT",0
menu_settings
        dc.b    '0','0','0','0',0,0,0,0,0,0,0
        even

        bss
        even
savssp
        ds.l    1
frame_count
        ds.l    1
        ds.b    4096
main_stack
old_vbl
        ds.l    1
vblcount
        ds.l    1
log_len
        ds.l    1
last_wr
        ds.l    1
epoch
        ds.b    1
        even
digital_seen
        ds.b    1
        even
stat_out
        ds.l    16
w_l0
        ds.l    1
w_l1
        ds.l    1
w_s0
        ds.l    1
w_s1
        ds.l    1
v_off
        ds.l    1
v_rotor
        ds.l    1
v_voice
        ds.l    1
tl_base
        ds.l    1
req_phase
        ds.l    1
req_have
        ds.l    1
req_wr
        ds.l    1
resource_buffer
        ds.b    RESOURCE_BUFFER_BYTES
log
        ds.b    LOG_BYTES
log2
        ds.b    LOG2_BYTES

        end
