; N/A - platform replacement: call-site macros for the digital effect layer (src/sound.s).
; Record: analysis/functions/sound-falcon.md#call-sites
;
; Every game call site of 00004E8E / 00004E2E / 00004E26 loads the DOS registers
; (ebp, bl, dl, ecx / al) and calls. The 68030 callers have live registers and
; live condition codes, which the DOS callers did not, so each macro keeps both:
; no sound call changes the state of the code around it (the layer's entries
; preserve every register, these keep the flags).
;
;   SndFX     id,bl,dl,ecx    snd_fx       - DOS: mov ebp,id / mov bl,bl / mov dl,dl / mov ecx,ecx / call 00004E8E
;   SndSpeechA id             snd_speech_a - DOS: mov al,id / call 00004E2E (SPEAK1)
;   SndSpeechB id             snd_speech_b - DOS: mov al,id / call 00004E26 (SPEAK0)
;
; Constants are given as the DOS immediates (bl $FF or $FE, dl 0..7).

        xref    snd_fx, snd_speech_a, snd_speech_b

        macro   SndFX
        move.w  ccr,-(sp)
        movem.l d1-d4,-(sp)
        moveq   #\1,d4                  ; ebp
        move.b  #\2,d1                  ; bl
        move.b  #\3,d3                  ; dl
        move.l  #\4,d2                  ; ecx
        jsr     snd_fx
        movem.l (sp)+,d1-d4
        move.w  (sp)+,ccr
        endm

        macro   SndSpeechA
        move.w  ccr,-(sp)
        move.l  d0,-(sp)
        moveq   #\1,d0                  ; al
        jsr     snd_speech_a
        move.l  (sp)+,d0
        move.w  (sp)+,ccr
        endm

        macro   SndSpeechB
        move.w  ccr,-(sp)
        move.l  d0,-(sp)
        moveq   #\1,d0                  ; al
        jsr     snd_speech_b
        move.l  (sp)+,d0
        move.w  (sp)+,ccr
        endm

; The distance-keyed explosion (00022871-00022876, 00024A27-00024A2C):
; d0.b = dl (0..4), ebp 1, bl $FF, ecx 0.
        macro   SndFXDist
        move.w  ccr,-(sp)
        movem.l d1-d4,-(sp)
        moveq   #1,d4
        moveq   #-1,d1
        move.b  d0,d3
        moveq   #0,d2
        jsr     snd_fx
        movem.l (sp)+,d1-d4
        move.w  (sp)+,ccr
        endm
