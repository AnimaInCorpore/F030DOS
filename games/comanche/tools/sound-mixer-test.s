; N/A - target artefact: a stand-alone test program for src/sound.s, no DOS routine.
; Record: analysis/functions/sound-falcon.md#verification
;
; Reads SNDTEST.SCR from the program's directory, drives the digital effect
; layer through the same entry points the game calls (snd_fx, snd_speech_a/b,
; snd_voice, snd_reset, snd_rate, snd_fill) and writes every byte the mixer
; produces to SNDOUT.BIN. tools/check-falcon-sound.py builds it, runs it under
; Hatari and compares SNDOUT.BIN with the DOS captures (build/sound/digital-*.json)
; and with jsComanche/dos-sound.js.
;
; Script, one op after another (multi-byte values big-endian):
;   00             end
;   01             start a scenario: mixer in the image's initial state, digital on
;   02 id bl dl ecx.l          snd_fx          (00004E8E)
;   03 id                      snd_speech_a    (00004E2E)
;   04 id                      snd_speech_b    (00004E26)
;   05 bank id slot dl ecx.l   snd_voice       (00004F6E), bank 0 SND1, 1 SPEAK1, 2 SPEAK0
;   06 slot dl                 snd_voice with the silence record
;   07 al                      snd_rate        (00004E0C)
;   08                         snd_reset       (000050B4)
;   09 n.w                     snd_fill n bytes, appended to the output
;   0A curve                   0 loud, 1 soft (the displacement at 00005307)
;   0B                         append the soft and the loud table (1024 bytes)
;   0C n.w                     snd_resample n output bytes (the Falcon DMA samples), appended

        include "inc/comanche.s"
        include "inc/gemdos.s"

        global  _main
        global  resource_buffer, menu_settings, frame_count

        xref    snd_mixer_init, snd_banks_load, snd_fx, snd_speech_a, snd_speech_b
        xref    snd_voice, snd_reset, snd_rate, snd_fill, snd_sample_ptr
        xref    snd_bank_fx, snd_bank_speak1, snd_bank_speak0
        xref    snd_silence, snd_digital, snd_curve, snd_tab_loud, snd_tab_soft
        xref    snd_resample, snd_rs_phase, snd_rs_have

SCRIPT_BYTES    = 1024*1024
OUT_BYTES       = 4*1024*1024

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
        move    #$2700,sr

        bsr     snd_mixer_init
        bsr     snd_banks_load

        ; the script
        clr.w   -(sp)
        pea     name_script
        move.w  #61,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .done
        move.w  d0,d7
        pea     script
        move.l  #SCRIPT_BYTES,-(sp)
        move.w  d7,-(sp)
        move.w  #63,-(sp)
        trap    #1
        lea     12(sp),sp
        move.w  d7,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp

        lea     script,a5
        lea     out,a4
.op
        moveq   #0,d0
        move.b  (a5)+,d0
        beq     .finished
        cmpi.b  #1,d0
        beq     .start
        cmpi.b  #2,d0
        beq     .fx
        cmpi.b  #3,d0
        beq     .speecha
        cmpi.b  #4,d0
        beq     .speechb
        cmpi.b  #5,d0
        beq     .voice
        cmpi.b  #6,d0
        beq     .silence
        cmpi.b  #7,d0
        beq     .rate
        cmpi.b  #8,d0
        beq     .reset
        cmpi.b  #9,d0
        beq     .fill
        cmpi.b  #10,d0
        beq     .curve
        cmpi.b  #11,d0
        beq     .tables
        cmpi.b  #12,d0
        beq     .resample
        bra     .finished

.start
        bsr     snd_mixer_init
        move.b  #1,snd_digital
        clr.l   snd_rs_phase
        clr.l   snd_rs_have
        bra     .op
.fx
        moveq   #0,d4
        move.b  (a5)+,d4                ; ebp
        move.b  (a5)+,d1                ; bl
        move.b  (a5)+,d3                ; dl
        bsr     .long
        move.l  d0,d2                   ; ecx
        bsr     snd_fx
        bra     .op
.speecha
        moveq   #0,d0
        move.b  (a5)+,d0
        bsr     snd_speech_a
        bra     .op
.speechb
        moveq   #0,d0
        move.b  (a5)+,d0
        bsr     snd_speech_b
        bra     .op
.voice
        moveq   #0,d5
        move.b  (a5)+,d5                ; bank
        moveq   #0,d0
        move.b  (a5)+,d0                ; id
        move.b  (a5)+,d1                ; slot
        move.b  (a5)+,d3                ; dl
        bsr     .long
        move.l  d0,d2                   ; ecx, kept in d2 across the lookup
        moveq   #0,d0
        move.b  -7(a5),d0               ; id again (bank, id, slot, dl, ecx.l precede a5)
        move.l  snd_bank_fx,a0
        tst.b   d5
        beq     .have_bank
        move.l  snd_bank_speak1,a0
        cmpi.b  #1,d5
        beq     .have_bank
        move.l  snd_bank_speak0,a0
.have_bank
        movem.l d1-d3,-(sp)
        bsr     snd_sample_ptr
        movem.l (sp)+,d1-d3
        bsr     snd_voice
        bra     .op
.silence
        move.l  #snd_silence,d0
        move.b  (a5)+,d1
        move.b  (a5)+,d3
        moveq   #0,d2
        bsr     snd_voice
        bra     .op
.rate
        move.b  (a5)+,d0
        bsr     snd_rate
        bra     .op
.reset
        bsr     snd_reset
        bra     .op
.fill
        moveq   #0,d0
        move.b  (a5)+,d0
        lsl.w   #8,d0
        move.b  (a5)+,d0
        movea.l a4,a0
        bsr     snd_fill
        adda.l  d0,a4
        bra     .op
.curve
        move.l  #snd_tab_loud,d0
        tst.b   (a5)+
        beq     .set_curve
        move.l  #snd_tab_soft,d0
.set_curve
        move.l  d0,snd_curve
        bra     .op
.tables
        lea     snd_tab_soft,a0
        move.w  #511,d0
.t1
        move.b  (a0)+,(a4)+
        dbra    d0,.t1
        lea     snd_tab_loud,a0
        move.w  #511,d0
.t2
        move.b  (a0)+,(a4)+
        dbra    d0,.t2
        bra     .op

.resample
        moveq   #0,d3
        move.b  (a5)+,d3
        lsl.w   #8,d3
        move.b  (a5)+,d3
        movea.l a4,a0
        bsr     snd_resample
        movea.l a0,a4
        bra     .op

.long
        move.b  (a5)+,d0
        lsl.l   #8,d0
        move.b  (a5)+,d0
        lsl.l   #8,d0
        move.b  (a5)+,d0
        lsl.l   #8,d0
        move.b  (a5)+,d0
        rts

.finished
        ; SNDOUT.BIN
        move.l  a4,d6
        sub.l   #out,d6
        clr.w   -(sp)
        pea     name_out
        move.w  #60,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .done
        move.w  d0,d7
        pea     out
        move.l  d6,-(sp)
        move.w  d7,-(sp)
        move.w  #64,-(sp)
        trap    #1
        lea     12(sp),sp
        move.w  d7,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
        ; the sentinel, last: SNDDONE.TXT holds the byte count
        clr.w   -(sp)
        pea     name_done
        move.w  #60,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .done
        move.w  d0,d7
        pea     name_done
        move.l  #4,-(sp)
        move.w  d7,-(sp)
        move.w  #64,-(sp)
        trap    #1
        lea     12(sp),sp
        move.w  d7,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
.done
        move.l  savssp,a0
        Super   (a0)
        Pterm0

        data
name_script
        dc.b    "SNDTEST.SCR",0
name_out
        dc.b    "SNDOUT.BIN",0
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
resource_buffer
        ds.b    RESOURCE_BUFFER_BYTES
script
        ds.b    SCRIPT_BYTES
out
        ds.b    OUT_BYTES

        end
