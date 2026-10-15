; Route: analysis/functions/sound-falcon.md (the digital effect layer).
; Record: analysis/functions/sound-falcon.md
; Specification: analysis/functions/sound-driver.md sections 4 and 5; the
; executable reference is jsComanche/dos-sound.js, held byte-exact against the
; DOS captures in build/sound/digital-*.json by tools/check-js-sound.js.
;
; The digital effect layer of Comanche: three 8-bit sample slots mixed in
; software at 11,111 Hz (DOS 00004E0C-000053D5). The original mixes into a
; Sound Blaster double buffer from the SB's IRQ; the Falcon plays a ring in
; ST-RAM through its sound DMA at 12,292 Hz, and the 50 Hz VBL refills it.
; Everything that is DOS arithmetic - slot choice, staging, the sum, the dither
; with its error feedback, the two transfer curves - is the original's and
; byte-exact (tools/check-falcon-sound.py). Everything between the mixer's
; output bytes and the DAC is platform: the resampler, the ring, the DMA
; matrix, the interrupt masking. Each routine says which it is.
;
; Registers follow the DOS routines' (eax d0, ebx d1, ecx d2, edx d3, ebp d4,
; esi a0) and every public entry preserves every register it is not documented
; to return - the callers are 68030 game code with live registers, where the
; DOS callers had free ones.
;
; Platform differences common to all request routines (00004EA2, 00004E8E,
; 00004E2E, 00004E26, 00004F6E, 000050B4):
;   - DOS brackets some of them in cli/sti (the SB IRQ runs the fill). Here the
;     fill runs from the VBL (level 4), so each public entry raises the IPL to
;     7 for its whole body and restores the caller's SR - the same exclusion,
;     and it nests.
;   - Sample records and bank offsets are the DOS files' little-endian bytes,
;     read in place with a byte swap (LE16/LE32); nothing is converted at load.
;   - The slot in bl, the shift in dl and the bank ids are only ever 0..2,
;     0..7 and the ids of section 4.2 (every call site of section 5); no
;     routine tests them, as the DOS does not.

        include "inc/comanche.s"
        include "inc/gemdos.s"
        include "inc/xbios.s"

        global  snd_init, snd_shutdown
        global  snd_apply_settings, snd_apply_sound
        global  snd_mode, snd_rate, snd_reset
        global  snd_start, snd_fx, snd_speech_a, snd_speech_b, snd_voice
        global  snd_sample_ptr, snd_fill, snd_vbl, snd_mixer_init
        global  snd_banks_load, snd_bank_load, snd_title_bank_load
        global  snd_bank_fx, snd_bank_speak1, snd_bank_speak0
        global  snd_silence, snd_digital, snd_mode_cur, snd_cfg
        global  snd_slots, snd_dither_ctr, snd_dither_mask, snd_dither_err
        global  snd_curve, snd_tab_loud, snd_tab_soft, snd_dma_on
        global  snd_stats, snd_fm_command, snd_log_buf, snd_log_count
        global  snd_wr, snd_ring, snd_resample, snd_rs_phase, snd_rs_have

        xref    resource_buffer, krl_decode, menu_settings, frame_count
        xref    music_command, music_apply_settings

; ---------------------------------------------------------------------------
; Constants. SL_* is the layout of one slot record (three, SL_SIZE apart); the
; DOS keeps the same fields as parallel dword arrays at 00004142-0000418F.
; ---------------------------------------------------------------------------
SL_PLAY         = 0     ; sample being played   [0000414E + 4s]
SL_LIM          = 4     ; its limit << 16       [0000415A + 4s] (the limit word, as
                        ;   compared against position >> 16 at 00005264)
SL_STEP         = 8     ; step, 16.16           [00004142 + 4s]
SL_POS          = 12    ; position, 16.16       [00004166 + 4s]
SL_NEXT         = 16    ; staged sample         [00004172 + 4s]
SL_NSTEP        = 20    ; its step              [0000417E + 4s]
SL_SHIFT        = 24    ; playing shift         [0000527A / 000052A4 / 000052D0]
SL_BIAS         = 25    ; playing bias          [0000527C / 000052A7 / 000052D3]
SL_NSHIFT       = 26    ; staged shift          [0000418D + s]
SL_NBIAS        = 27    ; staged bias           [0000418A + s]
SL_SIZE         = 32

SILENCE_START   = $40000        ; position 4.0: the record's two header words (00004F1A)

; Platform: the sound DMA ring and its refill.
SND_RING        = 4096          ; bytes, 8-bit signed mono: 333 ms at 12,292 Hz
SND_TARGET      = 1024          ; bytes the refill keeps ahead of the DMA: 83 ms
SND_PRESCALE    = 7             ; Devconnect prescale, 25.175 MHz clock:
                                ;   25,175,000 / 2048 = 12,292.48 Hz
; 11,111.11 Hz (SB time constant 0xA6: 1,000,000 / (256 - 0xA6), 00001FBC)
; over 12,292.48 Hz, 16.16: how far the input stream advances per output sample.
SND_RS_STEP     = 59238
SND_MIX_CHUNK   = 512           ; samples summed per pass of the fill
SND_RS_IN       = 1100          ; resampler input: ceil(1023 * 0.9039) + 2, with slack

; The request log: SND_LOG_ENTRIES (a power of two) records of 16 bytes:
;   +0 kind, +1 bl (slot spec), +2 dl, +3 id (ebp) or al, +4 ecx, +8 eax, +12 VBL count.
SND_LOG_ENTRIES = 512
K_FX            = 1
K_SPEECH_A      = 2
K_SPEECH_B      = 3
K_VOICE         = 4
K_MODE          = 5
K_RESET         = 6
K_RATE          = 7
K_START         = 8

SND_BANK_FX_BYTES       = 80000         ; SND1.RLE decodes to 74,649
SND_BANK_SPEAK1_BYTES   = 200000        ; SPEAK1.RLE decodes to 192,530
SND_BANK_SPEAK0_BYTES   = 24000         ; SPEAK0.RLE decodes to 20,066

        text

; ===========================================================================
; Little-endian reads of the DOS data (platform).
; ===========================================================================
        macro   LE16            ; \1 = source operand, \2 = data register (cleared by the caller)
        move.w  \1,\2
        ror.w   #8,\2
        endm

        macro   LE32            ; \1 = source operand, \2 = data register
        move.l  \1,\2
        ror.w   #8,\2
        swap    \2
        ror.w   #8,\2
        endm

; The request log (platform instrument): every public entry records what it was
; asked, with the VBL count, in a ring a debugger can dump (snd_log_buf,
; snd_log_count). It touches no mixer state. \1 = kind.
        macro   SND_LOG
        move.l  d5,-(sp)
        moveq   #\1,d5
        bsr     snd_log
        move.l  (sp)+,d5
        endm

; A public entry: save the registers, mask the interrupts, run the core,
; restore. \1 = entry, \2 = core, \3 = log kind. The cores clobber d0-d3/a0-a1
; and read d4.
        macro   SND_ENTRY
\1
        movem.l d0-d4/a0-a2,-(sp)
        SND_LOG \3
        move.w  sr,-(sp)
        ori.w   #$0700,sr
        bsr     \2
        move.w  (sp)+,sr
        movem.l (sp)+,d0-d4/a0-a2
        rts
        endm

; ===========================================================================
; 00004EA2 - start a sample on a slot.
; ===========================================================================
; In:  d0 = sample record, d1.b = slot spec (bl), d3.b = shift (dl),
;      d2 = step (ecx), 0 for the record's own word.
; DOS: flat 00004EA2-00004F6D, start a sample on a slot.
; DOS symbol: sub_00004EA2
; Record: analysis/functions/sound-falcon.md#snd_start
; Port: bl < $80 is the slot; $FF takes the first idle slot (the silence record
;   playing), else the slot already playing this exact record, else slot 0 if
;   dl = 0, else drops the sound; $FE skips the idle search. The slot gets the
;   record, its limit, the step, position 4.0, and (dl, bias[dl]).
; Preserved: the search order (00004EAD-00004EF3), the drop test `dl >= 1`
;   (00004EEE), the record word read when ecx = 0 (00004F0F), the immediate start.
; Difference: the shift and bias are stored in the slot record; the DOS patches
;   them into the mix loop's immediates (0000527A/C, 000052A4/7, 000052D0/3).
;   Same values at the same moment (platform: the 68030 loop reads them from
;   the record). The caller's SR handling is in the public entry.
; Kind: translated.
; Status: ported; byte-exact on the digital captures (tools/check-falcon-sound.py).
        SND_ENTRY snd_start,snd_start_core,K_START

snd_start_core
        lea     snd_slots,a1
        tst.b   d1
        bpl     .place                          ; 00004EA6 jns: bl < $80 names the slot
        cmpi.b  #$fe,d1
        beq     .same                           ; 00004EAB
        moveq   #0,d1                           ; 00004EB2
        cmp.l   #snd_silence,SL_PLAY(a1)        ; 00004EB4 cmp [414E],esi (esi = 40E2)
        beq     .place
        moveq   #1,d1
        cmp.l   #snd_silence,SL_PLAY+SL_SIZE(a1)
        beq     .place
        moveq   #2,d1
        cmp.l   #snd_silence,SL_PLAY+2*SL_SIZE(a1)
        beq     .place
.same                                           ; 00004ED0
        moveq   #0,d1
        cmp.l   SL_PLAY(a1),d0
        beq     .place
        moveq   #1,d1
        cmp.l   SL_PLAY+SL_SIZE(a1),d0
        beq     .place
        moveq   #2,d1
        cmp.l   SL_PLAY+2*SL_SIZE(a1),d0
        beq     .place
        cmpi.b  #1,d3                           ; 00004EEE cmp dl,1 / jae drop
        bhs     .drop
        moveq   #0,d1                           ; 00004EF3 xor bl,bl
.place                                          ; 00004EF5
        andi.l  #$ff,d1                         ; movzx ebx,bl
        lsl.l   #5,d1                           ; * SL_SIZE
        adda.l  d1,a1                           ; a1 = the slot's record
        movea.l d0,a0                           ; esi = eax
        move.l  d0,SL_PLAY(a1)                  ; 00004EFA
        moveq   #0,d1
        LE16    (a0),d1                         ; 00004F01 movzx eax,word [esi]
        swap    d1                              ; limit << 16
        move.l  d1,SL_LIM(a1)                   ; 00004F04
        tst.l   d2
        bne     .have_step                      ; 00004F0B or ecx,ecx
        moveq   #0,d2
        LE16    2(a0),d2                        ; 00004F0F movzx ecx,word [esi+2]
.have_step
        move.l  d2,SL_STEP(a1)                  ; 00004F13
        move.l  #SILENCE_START,SL_POS(a1)       ; 00004F1A
        move.b  d3,SL_SHIFT(a1)                 ; 00004F2D/00004F45/00004F58
        moveq   #0,d1
        move.b  d3,d1                           ; 00004F25 movzx edx,dl
        lea     snd_bias_tab,a0
        move.b  0(a0,d1.w),SL_BIAS(a1)          ; 00004F33/00004F4B/00004F5E
.drop
        rts

; ===========================================================================
; 00004F6E - stage a sample as the slot's next one.
; ===========================================================================
; In:  d0 = sample record, d1.b = slot (0..2), d3.b = shift, d2 = step or 0.
; DOS: flat 00004F6E-00004FBA, stage a sample as the slot's next.
; DOS symbol: sub_00004F6E
; Record: analysis/functions/sound-falcon.md#snd_voice
; Port: stores the record, step (the record's word when ecx = 0), shift and
;   bias[shift] as the slot's staged sample; the mixer takes it when the playing
;   one ends. A slot still holding the silence record starts it at once (the
;   tail jump into 00004EA2).
; Preserved: the order of the stores (00004F7D-00004F9A) and the idle test
;   (00004FA0).
; Difference: as snd_start.
; Kind: translated.
; Status: ported; byte-exact on the digital captures.
        SND_ENTRY snd_voice,snd_voice_core,K_VOICE

snd_voice_core
        lea     snd_slots,a1
        movea.l d0,a0                           ; 00004F70 esi = eax
        move.l  d1,-(sp)                        ; the slot, for the tail jump
        andi.l  #$ff,d1                         ; movzx ebx,bl
        lsl.l   #5,d1
        adda.l  d1,a1
        tst.l   d2
        bne     .have_step                      ; 00004F75 or ecx,ecx
        moveq   #0,d2
        LE16    2(a0),d2                        ; 00004F79
.have_step
        move.l  a0,SL_NEXT(a1)                  ; 00004F7D
        move.l  d2,SL_NSTEP(a1)                 ; 00004F84
        move.b  d3,SL_NSHIFT(a1)                ; 00004F8B
        moveq   #0,d1
        move.b  d3,d1                           ; 00004F91 movzx edx,dl
        lea     snd_bias_tab,a0
        move.b  0(a0,d1.w),SL_NBIAS(a1)         ; 00004F94-00004F9A
        cmp.l   #snd_silence,SL_PLAY(a1)        ; 00004FA0
        bne     .staged
        move.l  (sp)+,d1
        bra     snd_start_core                  ; 00004FB1 jmp 00004EA2 (eax = the record still)
.staged
        addq.l  #4,sp
        rts

; ===========================================================================
; 000050B4 - reset.
; ===========================================================================
; DOS: flat 000050B4-000051B6, reset the three slots.
; DOS symbol: sub_000050B4
; Record: analysis/functions/sound-falcon.md#snd_reset
; Port: every staged sample becomes the silence record (step 0, shift 0, bias
;   0), and every slot not already playing it switches to it (limit from the
;   record's word, step 0, position 4.0).
; Preserved: the order of the two passes, the unchanged shift/bias of the
;   playing sample (they are the patched immediates, which 000050B4 leaves).
; Kind: translated.
; Status: ported; byte-exact on the digital captures.
        SND_ENTRY snd_reset,snd_reset_core,K_RESET

snd_reset_core
        lea     snd_slots,a1
        moveq   #2,d0
.staged
        move.l  #snd_silence,SL_NEXT(a1)        ; 000050B7-000050CB
        clr.l   SL_NSTEP(a1)                    ; 000050D5-000050E9
        clr.b   SL_NSHIFT(a1)                   ; 000050F3-000050FA
        clr.b   SL_NBIAS(a1)                    ; 00005108-00005116
        lea     SL_SIZE(a1),a1
        dbra    d0,.staged
        lea     snd_slots,a1
        moveq   #2,d0
.playing
        cmp.l   #snd_silence,SL_PLAY(a1)        ; 00005123 cmp [414E],ebx
        beq     .next
        move.l  #snd_silence,SL_PLAY(a1)        ; 0000512B
        moveq   #0,d1
        LE16    snd_silence,d1                  ; 00005131 movzx eax,word [ebx]
        swap    d1
        move.l  d1,SL_LIM(a1)                   ; 00005134
        move.l  SL_NSTEP(a1),SL_STEP(a1)        ; 00005139-0000513F
        move.l  #SILENCE_START,SL_POS(a1)       ; 00005145
.next
        lea     SL_SIZE(a1),a1
        dbra    d0,.playing
        rts

; ===========================================================================
; 00004E0C - the dither mask.
; ===========================================================================
; In: d0.b = index 0..$11 into the mask table.
; DOS: flat 00004E0C-00004E25, select the dither mask.
; DOS symbol: sub_00004E0C
; Record: analysis/functions/sound-falcon.md#snd_rate
; Port: [00004194] = dword [00004998 + 4 * index]; an index above $11 does nothing.
; Preserved: the table (18 dwords), the range test.
; Kind: translated.
; Status: ported; byte-exact on the digital-mix capture (five masks).
snd_rate
        movem.l d0-d1/a0,-(sp)
        SND_LOG K_RATE
        cmpi.b  #$11,d0
        bhi     .out                            ; 00004E0F
        moveq   #0,d1
        move.b  d0,d1                           ; 00004E11 movzx eax,al
        lsl.w   #2,d1
        lea     snd_rate_tab,a0
        move.l  0(a0,d1.w),snd_dither_mask      ; 00004E18-00004E1F
.out
        movem.l (sp)+,d0-d1/a0
        rts

; ===========================================================================
; 00004E2E / 00004E26 - speech cues.
; ===========================================================================
; In: d0.b = id (al), 1-based in the bank.
; DOS: flat 00004E26-00004E86, SFXB (SPEAK0 [00019EA0]) and SFXA (SPEAK1
;   [00019E9C]) share the body from 00004E34.
; DOS symbol: sub_00004E2E / sub_00004E26
; Record: analysis/functions/sound-falcon.md#snd_speech
; Port: nothing if the bank is not loaded (00004E34) or slot 2's staged sample
;   differs from the one it is playing (00004E39-00004E45: a one-shot is
;   pending there); slot 2, or slot 1 when slots 0 and 1 are both idle
;   (00004E47-00004E61); skipped if the record is already playing on slot 0 or
;   1 (00004E70-00004E7E); started with dl = 0, ecx = 0.
; Preserved: every test, in order.
; Kind: translated.
; Status: ported; byte-exact on the digital-speech and digital-mix captures.
snd_speech_a
        movem.l d0-d4/a0-a2,-(sp)
        SND_LOG K_SPEECH_A
        move.l  snd_bank_speak1,a0              ; 00004E2E
        bra.s   snd_speech_enter
snd_speech_b
        movem.l d0-d4/a0-a2,-(sp)
        SND_LOG K_SPEECH_B
        move.l  snd_bank_speak0,a0              ; 00004E26
snd_speech_enter
        move.w  sr,-(sp)
        ori.w   #$0700,sr
        bsr     snd_speech_core
        move.w  (sp)+,sr
        movem.l (sp)+,d0-d4/a0-a2
        rts

snd_speech_core
        move.l  a0,d1
        beq     .out                            ; 00004E34 cmp esi,0 / je
        lea     snd_slots,a1
        move.l  SL_NEXT+2*SL_SIZE(a1),d1        ; 00004E39 ebx = [0000417A]
        cmp.l   SL_PLAY+2*SL_SIZE(a1),d1        ; 00004E3F cmp [00004156],ebx
        bne     .out                            ; 00004E45
        moveq   #2,d1                           ; 00004E47 bl = 2
        cmp.l   #snd_silence,SL_PLAY(a1)        ; 00004E49
        bne     .have_slot
        cmp.l   #snd_silence,SL_PLAY+SL_SIZE(a1) ; 00004E55
        bne     .have_slot
        moveq   #1,d1                           ; 00004E61
.have_slot
        andi.l  #$ff,d0                         ; 00004E64 movzx eax,al
        moveq   #0,d3                           ; 00004E67 dl = 0
        moveq   #0,d2                           ; 00004E69 ecx = 0
        lsl.l   #2,d0
        LE32    0(a0,d0.l),d0                   ; 00004E6B mov eax,[esi+eax*4]
        add.l   a0,d0                           ; 00004E6E add eax,esi
        cmp.l   SL_PLAY(a1),d0                  ; 00004E70
        beq     .out
        cmp.l   SL_PLAY+SL_SIZE(a1),d0          ; 00004E78
        beq     .out
        bra     snd_start_core                  ; 00004E80 call 00004EA2
.out
        rts

; ===========================================================================
; 00004E8E - an effect from the SND1 bank.
; ===========================================================================
; In: d4 = id (ebp), 1-based; d1.b = slot spec, d3.b = shift, d2 = step or 0.
; DOS: flat 00004E8E-00004EA1 (the FM branch at 00004E87-00004E8D).
; DOS symbol: sub_00004E8E
; Record: analysis/functions/sound-falcon.md#snd_fx
; Port: with the digital flag [00019DF9] set, eax = [SND1 + 4 * id] + SND1 and
;   the start routine; with it clear the same id goes to the FM driver's
;   command entry (snd_fm_command), where the music driver will sit.
; Preserved: the flag test, the unscaled 1-based id (00004E9D), the tail into
;   00004EA2.
; Difference: no test of the bank pointer, as in the DOS (00004E97). The
;   FM driver (0002B9CF) is not in this layer: snd_fm_command is an empty
;   routine until it is ported (analysis/functions/sound-driver.md section 10).
; Kind: translated.
; Status: ported; byte-exact on the digital captures.
        SND_ENTRY snd_fx,snd_fx_core,K_FX

snd_fx_core
        tst.b   snd_digital
        beq     .fm                             ; 00004E8E-00004E95
        movea.l snd_bank_fx,a0                  ; 00004E97
        move.l  d4,d0
        lsl.l   #2,d0
        LE32    0(a0,d0.l),d0                   ; 00004E9D mov eax,[esi+ebp*4]
        add.l   a0,d0                           ; 00004EA0
        bra     snd_start_core
.fm
        move.l  d4,d0                           ; 00004E87 mov eax,ebp
        bra     snd_fm_command                  ; 00004E89 jmp 0002B9CF

; The FM/music driver's command entry (DOS 0002B9CF, ax = command): the music
; driver's own, src/music.s.
; DOS: flat 0002B9CF, music/FM command entry.
; Port: music_command (d0.w = ax).
snd_fm_command
        jmp     music_command

; ===========================================================================
; The sample of a bank.
; ===========================================================================
; In:  a0 = bank (the pointer variables [00019E98/9C/A0]), d0 = id (1-based).
; Out: d0 = the record's address: bank + dword [bank + 4 * id].
; DOS: the inline `mov eax,[esi+ebp*4] / add eax,esi` at 00004E9D, 00004E6B and
;   000189A6 (the flight rotor, id 3).
; Record: analysis/functions/sound-falcon.md#snd_sample_ptr
; Port: the same two instructions with the little-endian dword read.
; Kind: translated.
; Status: ported; used by snd_fx/snd_speech inline and by the rotor callers.
snd_sample_ptr
        lsl.l   #2,d0
        LE32    0(a0,d0.l),d0
        add.l   a0,d0
        rts

; ===========================================================================
; 00005220 - the mixer fill.
; ===========================================================================
; In: d0.l = output bytes, a0 = destination (unsigned 8-bit, 0x80 = silence).
; DOS: flat 00005220-0000531A, with the restaging stubs 000051C0-00005213,
;   00005320-00005373, 00005380-000053D3.
; DOS symbol: sub_00005220
; Record: analysis/functions/sound-falcon.md#snd_fill
; Port: for every output byte, each slot contributes the byte at position >> 16
;   of its sample, shifted right by its shift and plus its bias (8-bit wrap),
;   then the position advances by the step; a slot whose position >> 16 has
;   reached its limit first takes its staged sample (limit, step, shift, bias,
;   position 4.0). t = sum + err[counter & mask] + 1; err[...] = (t >> 2) & $FF;
;   the output is curve[t >> 1]; the counter increments. The curve is the loud
;   or the soft table of 00004C0A / 00004A0A.
; Preserved: all of it, including the 8-bit wrap of each contribution and the
;   one limit test per slot per output byte (not repeated after a restage).
; Difference: (1) the DOS fills one 0x800-byte half of the SB's double buffer
;   per call; this fills any count into any buffer (the 68030 VBL needs ~220
;   bytes per refill, the test harness 0x800). (2) The DOS loop interleaves the
;   three slots per output byte; this sums slot by slot over a pass of up to 512
;   bytes into a word buffer and runs the dither pass over it. The slots share
;   nothing but the sum, so the output is the same. (3) A slot with step 0 and
;   position below its limit reads one byte forever; its contribution is
;   computed once per pass. (4) The hook calls at 00005201/00005361/000053C1
;   ([000040F2/F6/FA]) point at a bare `ret` in all four mixer modes
;   (00004E0B), so they are omitted.
; Kind: translated.
; Status: ported; byte-exact on the digital captures (233,472 bytes).
snd_fill
        movem.l d0-d7/a0-a6,-(sp)
        move.l  d0,-(sp)                        ; bytes left
.next
        move.l  (sp),d6
        beq     .out
        cmpi.l  #SND_MIX_CHUNK,d6
        bls     .piece
        move.l  #SND_MIX_CHUNK,d6
.piece
        sub.l   d6,(sp)
        bsr     snd_mix_piece                   ; d6 = n, a0 = output, advances it
        bra     .next
.out
        addq.l  #4,sp
        movem.l (sp)+,d0-d7/a0-a6
        rts

; One pass of up to SND_MIX_CHUNK output bytes. In: d6 = n, a0 = output.
snd_mix_piece
        move.l  d6,a5                           ; n
        lea     snd_sumbuf,a1
        move.w  d6,d0
        subq.w  #1,d0
        moveq   #0,d1
.clear
        move.w  d1,(a1)+
        dbra    d0,.clear
        suba.l  a4,a4                           ; the constant contribution of idle slots
        lea     snd_slots,a6
        bsr     .slot
        lea     SL_SIZE(a6),a6
        bsr     .slot
        lea     SL_SIZE(a6),a6
        bsr     .slot

        ; The dither pass: 000052DD-0000530B for each byte.
        lea     snd_sumbuf,a1
        move.l  a5,d7
        subq.w  #1,d7
        move.l  a4,d2                           ; constants
        move.l  snd_dither_ctr,d3
        move.l  snd_dither_mask,d4
        movea.l snd_curve,a2                    ; the displacement at 00005307
        lea     snd_dither_err,a3
.dither
        moveq   #0,d0
        move.w  (a1)+,d6
        add.w   d2,d6                           ; the three contributions
        move.l  d3,d1
        and.l   d4,d1                           ; 000052E3 and ebx,[00004194]
        addq.l  #1,d3                           ; 000052E9 inc [00004190]
        move.b  0(a3,d1.l),d0                   ; 000052EF add al,[ebx+00004198]
        add.w   d0,d6                           ; (adc ah,0)
        addq.w  #1,d6                           ; 000052F8 inc eax
        move.w  d6,d0
        lsr.w   #2,d0                           ; 000052F9 shr eax,2
        move.b  d0,0(a3,d1.l)                   ; 000052FC the new error byte
        lsr.w   #1,d6                           ; 00005302 rcl ax,1: (t >> 2) << 1 | bit 1 of t = t >> 1
        move.b  0(a2,d6.w),(a0)+                ; 00005305/0000530B
        dbra    d7,.dither
        move.l  d3,snd_dither_ctr
        rts

; One slot's contribution to the n bytes of the pass. In: a6 = slot record,
; a5 = n; adds into snd_sumbuf, or into a4 for a slot that reads one byte.
.slot
        move.l  SL_POS(a6),d2
        move.l  SL_LIM(a6),d4
        move.l  SL_STEP(a6),d3
        movea.l SL_PLAY(a6),a3
        moveq   #0,d5
        move.b  SL_SHIFT(a6),d5
        move.b  SL_BIAS(a6),d6
        moveq   #0,d0
        tst.l   d3
        bne     .general
        cmp.l   d4,d2
        bhs     .general                        ; restages on the first byte
        move.l  d2,d1                           ; step 0, below the limit: one byte for ever
        swap    d1
        andi.l  #$ffff,d1
        move.b  0(a3,d1.l),d0                   ; 00005270-00005276
        lsr.b   d5,d0                           ; 00005278 shr al,shift
        add.b   d6,d0                           ; 0000527B add al,bias
        adda.w  d0,a4
        rts
.general
        lea     snd_sumbuf,a1
        move.l  a5,d7
        subq.w  #1,d7
.byte
        cmp.l   d4,d2                           ; 00005261-0000526A
        bhs     .restage
.mix
        move.l  d2,d1
        swap    d1
        andi.l  #$ffff,d1                       ; position >> 16
        move.b  0(a3,d1.l),d0                   ; 00005270-00005276
        lsr.b   d5,d0                           ; 00005278
        add.b   d6,d0                           ; 0000527B
        add.l   d3,d2                           ; 0000527F add [00004166],esi
        add.w   d0,(a1)+                        ; 000052A8 add ax,dx
        dbra    d7,.byte
        move.l  d2,SL_POS(a6)
        move.l  d4,SL_LIM(a6)
        move.l  d3,SL_STEP(a6)
        move.l  a3,SL_PLAY(a6)
        move.b  d5,SL_SHIFT(a6)
        move.b  d6,SL_BIAS(a6)
        rts
.restage                                        ; 000051C0-00005213: the staged one plays
        movea.l SL_NEXT(a6),a3                  ; 000051C1
        moveq   #0,d4
        LE16    (a3),d4                         ; 000051C7
        swap    d4
        move.l  SL_NSTEP(a6),d3                 ; 000051CF-000051D5
        moveq   #0,d5
        move.b  SL_NSHIFT(a6),d5                ; 000051DB-000051E0
        move.b  SL_NBIAS(a6),d6                 ; 000051E5-000051EA
        move.l  #SILENCE_START,d2               ; 000051EF
        bra     .mix

; ===========================================================================
; 00004FE4 - the mixer mode.
; ===========================================================================
; In: d0.b = mode: 0 off, 1..4 the Sound Blaster types (identical), $FF only
;   prepares the buffers.
; DOS: flat 00004FE4-000050AF, start/stop the mixer.
; DOS symbol: sub_00004FE4
; Record: analysis/functions/sound-falcon.md#snd_mode
; Port: the transfer curve returns to the loud table (00004FE6-00004FEB); a
;   running mode is stopped (00004FF0-00004FF9); the buffers are rebuilt
;   silent; a mode above 4 returns here; otherwise the mode is recorded, the
;   slots are reset (000050A3), and for 1..4 the output is started.
; Preserved: the order, the `jbe` limit of 4 (00005079), the unchanged
;   [00004E0A] for a mode above 4.
; Difference: "stop", "rebuild the buffers" and "start" are the DMA path of the
;   platform: snd_dma_stop clears the ring and stops the Falcon DMA,
;   snd_dma_start restarts it from a silent ring (the DOS: DMA channel 1, two
;   0x800 halves of 0x80, the SB's DSP started with time constant 0xA6). The
;   dither counter and error table are not touched, as in the DOS.
; Kind: translated.
; Status: ported; DMA output verified in Hatari (analysis/functions/sound-falcon.md).
snd_mode
        movem.l d0-d2/a0-a2,-(sp)
        SND_LOG K_MODE
        move.b  d0,d2
        move.l  #snd_tab_loud,snd_curve         ; 00004FE6/00004FEB
        tst.b   snd_mode_cur
        beq     .nothing_running                ; 00004FF0-00004FF5
        bsr     snd_dma_stop                    ; 00004FF9 call [0000412A]
.nothing_running
        cmpi.b  #4,d2
        bhi     .out                            ; 00005079/0000507C
        move.b  d2,snd_mode_cur                 ; 00005082
        bsr     snd_reset                       ; 000050A3
        tst.b   d2
        beq     .out                            ; mode 0: [000040FE] is the bare `ret`
        bsr     snd_dma_start                   ; 000050A8 call [000040FE]
.out
        movem.l (sp)+,d0-d2/a0-a2
        rts

; ===========================================================================
; 000267F3 (sound half) and 00026CE3/00026CF9/00026D19 - Sound Loud/Soft/Off.
; ===========================================================================
; In: menu_settings+1 holds the radio's character, '0' Loud, '1' Soft, '2' Off.
; DOS: flat 00026843-0002687C (the sound half of the apply routine 000267F3);
;   00026CE3-00026D2B does the same for a live radio click.
; DOS symbol: loc_00026843
; Record: analysis/functions/sound-falcon.md#snd_apply_sound
; Port: '0': MODE([00019DF9]); '1': MODE([00019DF9]) then the soft curve
;   ([00005307] = 00004A0A); '2': MODE(0); any other character does nothing.
; Preserved: the three tests in order and the curve patch after the mode call.
; Kind: translated.
; Status: ported; the menu wiring is in menu.s.
snd_apply_sound
        movem.l d0-d1,-(sp)
        move.b  menu_settings+1,d1              ; 00026843 mov al,[00025DD5]
        cmpi.b  #'0',d1
        bne     .not_loud
        move.b  snd_digital,d0                  ; 0002684C
        bsr     snd_mode                        ; 00026851
        bra     .out
.not_loud
        cmpi.b  #'1',d1
        bne     .not_soft
        move.b  snd_digital,d0                  ; 0002685C
        bsr     snd_mode                        ; 00026861
        move.l  #snd_tab_soft,snd_curve         ; 00026866-0002686B
        bra     .out
.not_soft
        cmpi.b  #'2',d1
        bne     .out
        moveq   #0,d0                           ; 00026876
        bsr     snd_mode                        ; 00026878
.out
        movem.l (sp)+,d0-d1
        rts

; 000267F3 as a whole: the music half (000267F3-00026842, music_apply_settings
; in src/music.s: [00025DD6] picks the music level and sends FM command
; 0x5000 / 0x4000), then the sound half.
; DOS: flat 000267F3-0002687C, apply the sound settings.
; DOS symbol: sub_000267F3
; Record: analysis/functions/sound-falcon.md#snd_apply_sound
; Port: music_apply_settings, then snd_apply_sound.
; Kind: translated.
; Status: ported.
snd_apply_settings
        jsr     music_apply_settings
        bra     snd_apply_sound

; ===========================================================================
; Startup (DOS 000054F7-000055AF, sound part).
; ===========================================================================
; DOS: flat 00005528-000055AF: COMANCHE.CFG into 000053D8, DET, MODE(0xFF),
;   RATE(2).
; DOS symbol: inside loc_000054F7
; Record: analysis/functions/sound-falcon.md#snd_init
; Port: reads COMANCHE.CFG (10 bytes), [00019DF9] = byte 1 & $F, DET (the SB
;   probe 00004FBB: only 1..4 are tried), MODE($FF) when DET succeeds else
;   [00019DF9] = 0 (000055A6), then RATE(2). The music device bytes (2..) and
;   the music driver startup (000055B4-000055D8) are not part of this layer.
; Preserved: the order; a failed DET clears [00019DF9] and skips MODE.
; Difference: (1) DET is "the Falcon's sound system can be locked and a ring
;   allocated" (snd_det) in place of the SB DSP reset/IRQ probe. (2) A missing
;   COMANCHE.CFG leaves all ten digits 0 (digital off, music device none); the
;   DOS prints "Please type SOUNDSET" and exits (00005528-0000553A). So does a
;   missing SOUNDSET.EXE (000054FD-0000550A): neither file belongs to a Falcon
;   install (platform).
; Kind: translated.
; Status: ported; verified with and without the file in Hatari.
snd_init
        movem.l d0-d7/a0-a6,-(sp)
        bsr     snd_mixer_init
        ; COMANCHE.CFG
        clr.w   -(sp)
        pea     snd_cfg_name
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .no_cfg
        move.w  d0,d3
        pea     snd_cfg
        move.l  #10,-(sp)
        move.w  d3,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d4
        move.w  d3,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp
        cmpi.l  #10,d4
        beq     .have_cfg
        lea     snd_cfg,a0                      ; a short file is no file
        moveq   #9,d0
.zero
        clr.b   (a0)+
        dbra    d0,.zero
.have_cfg
.no_cfg
        moveq   #0,d0
        move.b  snd_cfg+1,d0
        andi.b  #$0f,d0                         ; 0000558A-0000558F
        move.b  d0,snd_digital                  ; 00005591
        bsr     snd_det                         ; 00005596
        tst.l   d0
        beq     .no_digital                     ; 0000559B or al,al
        moveq   #-1,d0
        bsr     snd_mode                        ; 0000559F MODE(0xFF)
        bra     .rate
.no_digital
        clr.b   snd_digital                     ; 000055A6
.rate
        moveq   #2,d0
        bsr     snd_rate                        ; 000055AD/000055AF RATE(2)
        movem.l (sp)+,d0-d7/a0-a6
        rts

; DET (00004FBB): d0.b = the configured digital type. Out: d0 = -1 if the
; mixer's output exists, 0 if not.
; DOS: flat 00004FBB-00004FCF.
; Port: types 1..4 try the Falcon DMA path (snd_dma_open); type 0 and >4 fail.
; Record: analysis/functions/sound-falcon.md#snd_init
snd_det
        cmpi.b  #4,d0
        bhi     .fail                           ; 00004FBD/00004FC0
        tst.b   d0
        beq     .fail                           ; type 0: the probe table's `ret` (00004E0B) with eax = 0
        bra     snd_dma_open
.fail
        moveq   #0,d0
        rts

; ===========================================================================
; Shutdown (DOS 00006B28-00006B2A: MODE(0) at exit).
; ===========================================================================
; DOS: flat 00006B27-00006B2A.
; Record: analysis/functions/sound-falcon.md#snd_init
; Port: MODE(0), then the sound system is released.
; Kind: translated.
snd_shutdown
        movem.l d0-d2/a0-a2,-(sp)
        moveq   #0,d0
        bsr     snd_mode                        ; 00006B2A
        bsr     snd_dma_stop                    ; (platform) even if a mode byte was already 0
        tst.l   snd_ring
        beq     .out
        Unlocksnd
        clr.l   snd_ring
.out
        movem.l (sp)+,d0-d2/a0-a2
        rts

; ===========================================================================
; The banks (DOS 000058D4/000064A8 snd1.rle, 0000681D speak0.rle, 00006859 speak1.rle).
; ===========================================================================
; In: a0 = file name, a1 = destination, d1 = capacity in bytes.
; Out: d0 = 0 loaded, -1 not loaded (file missing, not KRL0/KRL1, bigger than
;   the buffer, or a bad stream).
; DOS: flat 00015E6E-00015F6C (LOADALLOC of a KRL0/KRL1 resource) and 0001644B
;   (the KRL1 decoder, krl_decode).
; DOS symbol: sub_00015E6E
; Record: analysis/functions/sound-falcon.md#snd_bank_load
; Port: reads the file through GEMDOS into the shared staging buffer, checks
;   'KRL0'/'KRL1' and the declared size, and expands it to a1 (a copy for KRL0,
;   krl_decode for KRL1).
; Preserved: the container reading of the DOS loader and the decoder; the bank
;   keeps its own little-endian 'K1' layout.
; Difference: the DOS allocates the bank from its bump allocator without a
;   bound; the port decodes into a fixed buffer and reports "not loaded" when
;   the declared size does not fit (platform).
; Kind: translated.
; Status: ported; the decoded banks are identical to tools/check-js-sound.js's.
snd_bank_load
        movem.l d1-d7/a0-a6,-(sp)
        movea.l a1,a6
        move.l  d1,d7
        clr.w   -(sp)
        move.l  a0,-(sp)
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .fail
        move.w  d0,d6
        pea     resource_buffer
        move.l  #RESOURCE_BUFFER_BYTES,-(sp)
        move.w  d6,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d5
        move.w  d6,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp
        tst.l   d5
        bmi     .fail
        cmpi.l  #8,d5
        blo     .fail
        lea     resource_buffer,a0
        move.l  (a0),d0
        LE32    4(a0),d1                        ; the decoded size
        cmp.l   d7,d1
        bhi     .fail
        cmpi.l  #$4B524C31,d0                   ; 'KRL1'
        beq     .krl1
        cmpi.l  #$4B524C30,d0                   ; 'KRL0'
        bne     .fail
        move.l  d5,d2
        subq.l  #8,d2
        cmp.l   d1,d2
        blo     .fail                           ; stored: the bytes after the header
        lea     8(a0),a0
        movea.l a6,a1
        move.l  d1,d0
        beq     .ok
.copy
        move.b  (a0)+,(a1)+
        subq.l  #1,d0
        bne     .copy
        bra     .ok
.krl1
        move.l  d5,d2
        subq.l  #8,d2                           ; source bytes
        lea     8(a0),a0
        movea.l a6,a1
        move.l  d1,d0                           ; output bytes
        jsr     krl_decode
        tst.l   d0
        bne     .fail
.ok
        moveq   #0,d0
        bra     .out
.fail
        moveq   #-1,d0
.out
        movem.l (sp)+,d1-d7/a0-a6
        rts

; The three banks at mission load (DOS 000064A8, 0000681D, 00006859, in that
; order). A bank that does not load leaves its pointer 0 - "not loaded", which
; 00004E34 tests for the speech banks; with no SND1 the digital layer is off
; (snd_digital = 0, effects to the FM entry), the DOS's own no-digital route.
; DOS: flat 000064A8, 0000681D, 00006859.
; Record: analysis/functions/sound-falcon.md#snd_bank_load
; Port: loads SND1.RLE, SPEAK0.RLE, SPEAK1.RLE into their buffers.
; Difference: the DOS stops with a file error when one is missing (platform).
; Kind: translated.
snd_banks_load
        movem.l d0-d1/a0-a1,-(sp)
        bsr     snd_title_bank_load
        lea     snd_name_speak0,a0
        lea     snd_buf_speak0,a1
        move.l  #SND_BANK_SPEAK0_BYTES,d1
        bsr     snd_bank_load
        move.l  #snd_buf_speak0,d1
        tst.l   d0
        beq     .speak0
        moveq   #0,d1
.speak0
        move.l  d1,snd_bank_speak0              ; [00019EA0]
        lea     snd_name_speak1,a0
        lea     snd_buf_speak1,a1
        move.l  #SND_BANK_SPEAK1_BYTES,d1
        bsr     snd_bank_load
        move.l  #snd_buf_speak1,d1
        tst.l   d0
        beq     .speak1
        moveq   #0,d1
.speak1
        move.l  d1,snd_bank_speak1              ; [00019E9C]
        movem.l (sp)+,d0-d1/a0-a1
        rts

; SND1.RLE alone (the title screen's load at 000058D4, and the first of the
; mission's three).
; DOS: flat 000058D4, 000064A8; pointer [00019E98].
snd_title_bank_load
        movem.l d0-d1/a0-a1,-(sp)
        lea     snd_name_fx,a0
        lea     snd_buf_fx,a1
        move.l  #SND_BANK_FX_BYTES,d1
        bsr     snd_bank_load
        move.l  #snd_buf_fx,d1
        tst.l   d0
        beq     .loaded
        moveq   #0,d1
        clr.b   snd_digital
.loaded
        move.l  d1,snd_bank_fx                  ; [00019E98]
        movem.l (sp)+,d0-d1/a0-a1
        rts

; ===========================================================================
; The mixer's initial state: the image's bytes at 00004142-000041B7 and the two
; transfer curves of 00004A0A/00004C0A.
; ===========================================================================
; DOS: the data at 00004142-00004998 of the flat image (static, below 0x32B20).
; Record: analysis/functions/sound-falcon.md#snd_mixer_init
; Port: slots idle on the silence record (limit 0, step 0, position 4.0,
;   staged = silence, shift/bias 0); dither counter 0, mask 0, all 2048 error
;   bytes $80; the curve table; the curve pointer on the loud one.
; Preserved: every value above is the image's byte; the curves are the
;   recovered formulas (Loud: clamp(i - 128, 0, 255); Soft: i >> 1, i = 0..511),
;   equal to the image bytes (checked by tools/check-falcon-sound.py).
; Kind: translated.
snd_mixer_init
        movem.l d0-d1/a0-a1,-(sp)
        lea     snd_slots,a0
        moveq   #2,d0
.slot
        move.l  #snd_silence,SL_PLAY(a0)
        clr.l   SL_LIM(a0)
        clr.l   SL_STEP(a0)
        move.l  #SILENCE_START,SL_POS(a0)
        move.l  #snd_silence,SL_NEXT(a0)
        clr.l   SL_NSTEP(a0)
        clr.l   SL_SHIFT(a0)                    ; shift, bias, staged shift, staged bias
        lea     SL_SIZE(a0),a0
        dbra    d0,.slot
        clr.l   snd_dither_ctr
        clr.l   snd_dither_mask
        lea     snd_dither_err,a0
        move.w  #2048/4-1,d0
        move.l  #$80808080,d1
.err
        move.l  d1,(a0)+
        dbra    d0,.err
        lea     snd_tab_soft,a0
        lea     snd_tab_loud,a1
        moveq   #0,d0
.curves
        move.w  d0,d1
        lsr.w   #1,d1
        move.b  d1,(a0)+                        ; soft: i >> 1
        move.w  d0,d1
        subi.w  #128,d1
        bpl     .pos
        moveq   #0,d1
.pos
        cmpi.w  #255,d1
        bls     .fits
        move.w  #255,d1
.fits
        move.b  d1,(a1)+                        ; loud: clamp(i - 128, 0, 255)
        addq.w  #1,d0
        cmpi.w  #512,d0
        bne     .curves
        move.l  #snd_tab_loud,snd_curve
        clr.b   snd_mode_cur
        movem.l (sp)+,d0-d1/a0-a1
        rts

; ===========================================================================
; The Falcon output path (platform replacement for the Sound Blaster's DMA
; double buffer and its IRQ; no DOS counterpart).
; ===========================================================================
; The mixer's bytes (11,111 Hz) go through a linear resampler to 12,292.48 Hz
; (the Falcon's 25.175 MHz clock / 2048, XBIOS prescale 7 - the nearest rate the
; DAC offers to 11,111 Hz) into a 4096-byte ring in ST-RAM, played by the sound
; DMA in repeat mode, mono, 8-bit signed (the mixer's unsigned byte xor $80).
; The 50 Hz VBL keeps the ring SND_TARGET bytes ahead of the DMA's play
; position. The DSP is not touched: only the DMA -> DAC route is connected.

; XBIOS sound set-up, once. Out: d0 = -1 if the ring exists, 0 if the sound
; system is locked by someone else or no ST-RAM is left.
snd_dma_open
        movem.l d1-d2/a0-a2,-(sp)
        Locksnd
        cmpi.l  #1,d0
        bne     .fail
        Mxalloc #SND_RING,#0                    ; ST-RAM, like the screens
        tst.l   d0
        ble     .unlock
        move.l  d0,snd_ring
        Buffoper #0                             ; stop what an earlier program left
        Setmode #2                              ; 8-bit mono
        Settracks #0,#0
        Setmontracks #0                         ; the DAC monitors track 0
        Soundcmd #4,#2                          ; adder input: the matrix, not the ADC
        Devconnect #0,#8,#0,#SND_PRESCALE,#1    ; DMA playback -> DAC, 25.175 MHz, no handshake
        moveq   #-1,d0
        bra     .out
.unlock
        Unlocksnd
.fail
        moveq   #0,d0
.out
        movem.l (sp)+,d1-d2/a0-a2
        rts

; Start from a silent ring.
snd_dma_start
        movem.l d0-d2/a0-a2,-(sp)
        tst.l   snd_ring
        beq     .out
        move.w  sr,-(sp)
        ori.w   #$0700,sr
        clr.b   snd_dma_on
        movea.l snd_ring,a0
        move.w  #SND_RING/4-1,d0
        moveq   #0,d1
.clear
        move.l  d1,(a0)+                        ; signed silence
        dbra    d0,.clear
        ScreenCachePush
        move.l  #SND_TARGET,snd_wr              ; the silent ring already is the lead
        clr.l   snd_played
        clr.l   snd_last
        clr.l   snd_rs_phase
        clr.l   snd_rs_have
        move.w  (sp)+,sr
        move.l  snd_ring,d1
        move.l  d1,d2
        add.l   #SND_RING,d2
        Setbuffer #0,d1,d2
        Buffoper #3                             ; playback, repeat
        move.b  #1,snd_dma_on
.out
        movem.l (sp)+,d0-d2/a0-a2
        rts

snd_dma_stop
        movem.l d0-d2/a0-a2,-(sp)
        tst.l   snd_ring
        beq     .out
        clr.b   snd_dma_on
        Buffoper #0
.out
        movem.l (sp)+,d0-d2/a0-a2
        rts

; The 50 Hz refill. Called from the VBL handler with interrupts at level 4; it
; saves what it uses.
; DOS: N/A - platform replacement for the Sound Blaster IRQ that calls 00005220
;   (000020D5).
; Record: analysis/functions/sound-falcon.md#snd_vbl
; Port: reads the DMA frame counter ($FF8909/0B/0D, until two reads agree),
;   accounts the bytes played since the last call (mod ring), and renders
;   SND_TARGET minus the lead into the ring.
; Difference (platform): a lead below 0 (the DMA overtook the writer) skips the
;   writer to the play position instead of replaying stale ring bytes.
snd_vbl
        tst.b   snd_dma_on
        beq     .none
        movem.l d0-d7/a0-a6,-(sp)
        addq.l  #1,snd_stat_vbl
.read
        moveq   #0,d0
        move.b  $ffff8909.w,d0
        lsl.l   #8,d0
        move.b  $ffff890b.w,d0
        lsl.l   #8,d0
        move.b  $ffff890d.w,d0
        moveq   #0,d1
        move.b  $ffff8909.w,d1
        lsl.l   #8,d1
        move.b  $ffff890b.w,d1
        lsl.l   #8,d1
        move.b  $ffff890d.w,d1
        cmp.l   d0,d1
        bne     .read
        sub.l   snd_ring,d0
        andi.l  #SND_RING-1,d0                  ; the play position in the ring
        move.l  d0,d1
        sub.l   snd_last,d1
        andi.l  #SND_RING-1,d1                  ; bytes since the last refill
        add.l   d1,snd_played
        move.l  d0,snd_last
        move.l  snd_wr,d2
        sub.l   snd_played,d2                   ; lead
        bpl     .lead_ok
        move.l  snd_played,snd_wr               ; underrun: resynchronise
        moveq   #0,d2
        addq.l  #1,snd_stat_under
.lead_ok
        move.l  #SND_TARGET,d3
        sub.l   d2,d3                           ; bytes to render
        ble     .done
        add.l   d3,snd_stat_made
        move.l  snd_wr,d0
        andi.l  #SND_RING-1,d0
        movea.l snd_ring,a0
        adda.l  d0,a0
        move.l  #SND_RING,d1
        sub.l   d0,d1                           ; bytes to the end of the ring
        cmp.l   d1,d3
        bls     .one
        sub.l   d1,d3
        move.l  d3,-(sp)
        move.l  d1,d3
        bsr     snd_resample
        move.l  (sp)+,d3
        movea.l snd_ring,a0
        bsr     snd_resample
        bra     .rendered
.one
        bsr     snd_resample
.rendered
        ScreenCachePush
        move.l  #SND_TARGET,d3
        sub.l   d2,d3
        add.l   d3,snd_wr
.done
        movem.l (sp)+,d0-d7/a0-a6
.none
        rts

; Render d3 output bytes (8-bit signed, 12,292 Hz) to a0 (advanced).
; Platform: the linear interpolator between the mixer's 11,111 Hz bytes.
;   out = a + ((c - a) * f >> 15) with f = frac(phase) >> 1, a and c the two
;   input bytes around phase (16.16 over snd_rs_buf); the mixer is run for as
;   many new input bytes as the pass needs, and the unused tail of the input
;   (always 1 or 2 bytes) is kept for the next pass.
snd_resample
        movem.l d0-d7/a1-a2,-(sp)
        move.l  d3,d7
        beq     .out
        move.l  snd_rs_phase,d4
        move.l  d7,d0
        subq.l  #1,d0
        mulu.w  #SND_RS_STEP,d0                 ; (n - 1) * step
        add.l   d4,d0
        swap    d0
        andi.l  #$ffff,d0                       ; the last input index used
        addq.l  #2,d0                           ; ... and its neighbour: input bytes needed
        move.l  snd_rs_have,d1
        sub.l   d1,d0
        ble     .have_enough
        movem.l d0-d1/a0,-(sp)
        lea     snd_rs_buf,a1
        adda.l  d1,a1
        movea.l a1,a0
        bsr     snd_fill                        ; d0 new mixer bytes after the kept ones
        movem.l (sp)+,d0-d1/a0
        add.l   d0,d1
        move.l  d1,snd_rs_have
.have_enough
        lea     snd_rs_buf,a1
        move.l  #SND_RS_STEP,d5
        subq.w  #1,d7
.sample
        move.l  d4,d1
        swap    d1                              ; the input index
        moveq   #0,d2
        moveq   #0,d3
        move.b  0(a1,d1.w),d2                   ; a
        move.b  1(a1,d1.w),d3                   ; c
        move.w  d4,d1
        lsr.w   #1,d1                           ; f, 15 bits
        sub.w   d2,d3
        muls.w  d1,d3
        moveq   #15,d1
        asr.l   d1,d3
        add.w   d3,d2
        eori.b  #$80,d2                         ; unsigned mixer byte -> signed DMA sample
        move.b  d2,(a0)+
        add.l   d5,d4
        dbra    d7,.sample
        move.l  d4,d0
        swap    d0
        andi.l  #$ffff,d0                       ; whole input bytes consumed
        move.l  snd_rs_have,d1
        sub.l   d0,d1                           ; kept
        lea     snd_rs_buf,a1
        lea     0(a1,d0.l),a2
        move.l  d1,snd_rs_have
        subq.w  #1,d1
.keep
        move.b  (a2)+,(a1)+
        dbra    d1,.keep
        andi.l  #$ffff,d4
        move.l  d4,snd_rs_phase
.out
        movem.l (sp)+,d0-d7/a1-a2
        rts

; Record one request. In: d5 = kind, d0-d4 as the entry saw them. Keeps everything.
; DOS: N/A - platform instrument (a ring for a debugger; no counterpart in the original).
snd_log
        movem.l d6/a3,-(sp)
        move.l  snd_log_count,d6
        andi.l  #SND_LOG_ENTRIES-1,d6
        lsl.l   #4,d6
        lea     snd_log_buf,a3
        adda.l  d6,a3
        move.b  d5,(a3)
        move.b  d1,1(a3)
        move.b  d3,2(a3)
        move.b  d4,3(a3)
        move.l  d2,4(a3)
        move.l  d0,8(a3)
        move.l  frame_count,12(a3)
        addq.l  #1,snd_log_count
        movem.l (sp)+,d6/a3
        rts

; ===========================================================================
; Data (initialised: the image's static bytes).
; ===========================================================================
        data
        even
; 000040E2: the silence record. Little-endian limit 15, step 0, then eleven
; bytes of 0x80 (positions 4..14 are the playable ones).
snd_silence
        dc.b    15,0,0,0
        dc.b    $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80
        even
; 00004A02: bias[shift].
snd_bias_tab
        dc.b    $00,$40,$60,$70,$78,$7c,$7e,$7e
; 00004998: the dither mask for RATE(0..17), filled from the player's
; COMANCHE.EXE at startup (src/origexe.s); storage in this file's BSS.
snd_cfg_name
        dc.b    "COMANCHE.CFG",0
snd_name_fx
        dc.b    "SND1.RLE",0
snd_name_speak0
        dc.b    "SPEAK0.RLE",0
snd_name_speak1
        dc.b    "SPEAK1.RLE",0
        even

        bss
        even
        global  snd_rate_tab
snd_rate_tab
        ds.l    18
        even
snd_slots
        ds.b    3*SL_SIZE
snd_dither_ctr
        ds.l    1                               ; [00004190]
snd_dither_mask
        ds.l    1                               ; [00004194]
snd_dither_err
        ds.b    2048                            ; [00004198..]
snd_curve
        ds.l    1                               ; the displacement at 00005307, as a pointer
snd_tab_soft
        ds.b    512                             ; 00004A0A
snd_tab_loud
        ds.b    512                             ; 00004C0A
snd_mode_cur
        ds.b    1                               ; [00004E0A]
snd_digital
        ds.b    1                               ; [00019DF9]
snd_dma_on
        ds.b    1                               ; platform: the refill is live
        even
snd_cfg
        ds.b    10                              ; [000053D8..000053E1]
        even
snd_bank_fx
        ds.l    1                               ; [00019E98] SND1
snd_bank_speak1
        ds.l    1                               ; [00019E9C] SPEAK1
snd_bank_speak0
        ds.l    1                               ; [00019EA0] SPEAK0
snd_sumbuf
        ds.w    SND_MIX_CHUNK
snd_ring
        ds.l    1                               ; ST-RAM, SND_RING bytes
snd_wr
        ds.l    1                               ; bytes written since the DMA started
snd_played
        ds.l    1                               ; bytes the DMA has played
snd_last
        ds.l    1                               ; its position at the last refill
snd_rs_phase
        ds.l    1                               ; resampler position in the input, 16.16
snd_rs_have
        ds.l    1                               ; valid bytes of snd_rs_buf
snd_log_count
        ds.l    1
snd_log_buf
        ds.b    SND_LOG_ENTRIES*16
snd_stats
snd_stat_vbl
        ds.l    1                               ; refills run
snd_stat_under
        ds.l    1                               ; underruns resynchronised
snd_stat_made
        ds.l    1                               ; output bytes rendered
snd_rs_buf
        ds.b    SND_RS_IN
        even
snd_buf_fx
        ds.b    SND_BANK_FX_BYTES
snd_buf_speak1
        ds.b    SND_BANK_SPEAK1_BYTES
snd_buf_speak0
        ds.b    SND_BANK_SPEAK0_BYTES
        even

        end
