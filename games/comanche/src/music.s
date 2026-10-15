; Route: analysis/functions/sound-driver.md section 3 (the music and FM driver).
; Record: analysis/functions/sound-driver.md
; Specification: analysis/functions/sound-driver.md sections 3, 5.9, 7 and 10;
; the executable reference is jsComanche/dos-sound.js, held write-for-write
; against the original's captures (build/sound/*.json) by
; tools/check-js-sound.js. This file is checked against the same captures by
; tools/check-falcon-music.py.
;
; Kyle Freeman's MS3 music and FM effect driver (DOS 0002B9CF-0002C4A0): MS3
; songs and the FM effect table played on an OPL2 (devices 2 and 3), driven by
; the 65 Hz timer tick. Everything the original computes - the sequencer, the
; channel links, the patch loads, the velocity scaling, the pitch envelopes,
; the effect channels, every OPL2 register and value - is the original's. Its
; only output is the stream of (register, value) pairs, which goes to
; music_opl_write, the one point a synthesiser attaches to.
;
; Layout. The driver's variables and tables are one block, mus_mem, that
; mirrors flat 0002C48C-0002DA00; a field is addressed as D_<name>(a5) with
; a5 = mus_mem and D_<name> = its flat address - 0002C48C, so every offset in
; this file can be read against the listing. The tables (0002C619 and
; 0002C70D-0002DA00: the effect voice orders, the 128 patches, the F-number
; table, the operator maps, the effect table, the patch scale/transpose bytes,
; the pitch envelopes and their pointer table) are copied in by src/origexe.s
; from the player's own COMANCHE.EXE; no byte of them is in this program. The
; game's start-up relocation of the dwords at 0002D7F0 (000055E8-00005602) is
; not applied: the one dword the driver can reach there, patch 255's envelope
; pointer at 0002D9E2, lies outside the image before and after it.
;
; Differences, all platform:
;   - Pointers the original keeps as little-endian dwords in the block (the
;     song, the cursor, the envelope cursors, the effect half) are big-endian
;     longs here, at the same offsets, and they hold DOS flat addresses: a song
;     is given with the address the original would have it at (music_start),
;     and every byte is fetched through mus_song_byte / mus_env_byte, which
;     translate. That keeps the 16-bit `inc bx` at 0002BDED and the
;     out-of-image envelope of patch 255 (sound-driver.md section 11, item 5:
;     it reads as 0x00, QEMU's open bus) exactly the original's.
;   - Devices 1 (PC speaker) and 4 (MPU-401) have nothing behind their ports
;     on a Falcon; their detect answers 0 and their select fails, as the
;     original's do on a PC without the hardware (capture detect-absent).
;     Device 5 and devices 2/3 are the original's.
;   - The original's timer interrupt can land inside a driver call; here the
;     public entries mask interrupts for their body, so a tick lands before or
;     after a call, never inside it (sound-driver.md section 11, item 9).
;   - The OPL write's settling delays (0002C1C2-0002C1E5) belong to the bus,
;     not the stream: the sink is called once per pair.

        include "inc/comanche.s"

        global  music_command, music_start, music_stop, music_tick
        global  music_set_volume, music_playing, music_startup
        global  music_mem, music_opl_write, music_opl_status
        global  music_log, music_log_count, music_log_on
        global  music_tick_count
        global  music_resend, music_apply_settings, music_radio, music_bar_open
        global  music_shutdown, music_attract_pass, music_side_start
        global  music_fanfare_start, music_title_start, music_menu_enter
        global  music_theme_load, music_theme_start, music_debrief_start
        global  music_enable

        xref    snd_cfg, snd_bank_load, menu_settings, mission_music_names
    ifnd OPL2
OPL2 = 0
    endc
    ifne OPL2
        xref    opl_host_write, opl_host_running
    endc

MUS_BASE        = $2C48C                ; flat address of mus_mem's first byte
MUS_END         = $2DA00                ; one past the last byte any table needs
MUS_BYTES       = MUS_END-MUS_BASE

; The driver's variables (sound-driver.md section 3.2) and tables, by flat
; address. The leading D_ is the offset inside mus_mem.
D_TICKVEC       = $2C48C-MUS_BASE       ; .w here: 0 = the `ret` 0002B9F6, 1 = 0002BBF2
D_CURSOR        = $2C490-MUS_BASE       ; .l DOS address of the next event
D_SONG          = $2C494-MUS_BASE       ; .l the song playing (DOS address, 0 = none)
D_QUEUED        = $2C498-MUS_BASE       ; .l the song queued behind it
D_FLAGS         = $2C49C-MUS_BASE       ; .b flags the song was started with
D_QFLAGS        = $2C49D-MUS_BASE       ; .b flags of the queued song
D_PLAYING       = $2C49E-MUS_BASE       ; .b 0xFF while a song runs
D_PAUSED        = $2C49F-MUS_BASE       ; .b 0xFF while paused
D_COMMAND       = $2C4A0-MUS_BASE       ; .w the ax of the last command (LE: al, ah)
D_COUNTDOWN     = $2C4A2-MUS_BASE       ; .w ticks to the next event
D_NOTE          = $2C4A4-MUS_BASE       ; 16 last note per channel (written only)
D_LINK          = $2C4B4-MUS_BASE       ; 10 channel links
D_SONGPATCH     = $2C4C4-MUS_BASE       ; 10 the song's patch per channel
D_LOADED        = $2C4D4-MUS_BASE       ; 10 the patch loaded (0xFF none)
D_DEVICE        = $2C4E4-MUS_BASE       ; .b the selected device
D_ENVPTR        = $2C4E8-MUS_BASE       ; 10 .l envelope cursors
D_ENVSTART      = $2C528-MUS_BASE       ; 10 .l envelope starts
D_PITCHOFS      = $2C568-MUS_BASE       ; 10 En pitch offsets
D_BASENOTE      = $2C578-MUS_BASE       ; 10 pitch keyed (plus transpose)
D_SENTNOTE      = $2C588-MUS_BASE       ; 10 pitch last sent (0xFF none)
D_TRANSPOSE     = $2C598-MUS_BASE       ; 10
D_MASTER        = $2C5A8-MUS_BASE       ; .b music master volume
D_SCALE         = $2C5A9-MUS_BASE       ; 16 velocity scale per channel
D_KEYON         = $2C5B9-MUS_BASE       ; 16 channel keyed on
D_VOICE         = $2C5C9-MUS_BASE       ; 10 effect ticks left (non-zero: an effect's)
D_VOICEORDER    = $2C619-MUS_BASE       ; 6 x 8 effect channel order per device
D_PATCHES       = $2C70D-MUS_BASE       ; 128 x 16 OPL patches
D_FNUM          = $2CF0D-MUS_BASE       ; 256 LE words, F-number and block
D_OPLMODLEVEL   = $2D10D-MUS_BASE       ; 9 the patch's byte 1 per voice
D_OPLSHADOW     = $2D116-MUS_BASE       ; 9 the B0 shadow per voice
D_OPLOP1        = $2D11F-MUS_BASE       ; 9 first operator offsets
D_OPLOP2        = $2D128-MUS_BASE       ; 9 second (carrier) operator offsets
D_OPLVOICEOF    = $2D131-MUS_BASE       ; 16 music channel -> OPL voice (>= 9 none)
D_FXBASE        = $2D404-MUS_BASE       ; .l which half of an effect (DOS address)
FX_TABLE        = $2D408                ; flat: the effect table, 8 bytes an id
D_TRANSPOSETAB  = $2D4D0-MUS_BASE       ; 128 transpose per patch
D_SCALETAB      = $2D550-MUS_BASE       ; 128 scale per patch
DEFAULT_ENV     = $2D5D0                ; flat: `00 80`
D_ENVTABLE      = $2D5E6-MUS_BASE       ; 128 LE dwords, envelope per patch

LOG_ENTRIES     = 16384                 ; music_log: (tick.w, reg.b, value.b)

; The song buffers and the flat addresses their songs are played at (the
; cursor's address space, src/music.s header). A and B are the original's BSS
; buffers 0002DB10 and 0002DF10 (A is also its demo buffer: a song plays from
; it only while no demo is recorded, which is so here as there). The theme and
; the debrief song come from the original's bump allocator, at addresses that
; depend on the run (003BE7CC in the captures); here they are played at
; 64 KB-aligned addresses, so the 16-bit cursor step of 0002BDED cannot wrap
; inside them - in the original it would only for a velocity byte that lands
; on a 64 KB boundary of the heap.
MUSIC_A_DOS     = $2DB10
MUSIC_B_DOS     = $2DF10
MUSIC_THEME_DOS = $400000
MUSIC_END_DOS   = $410000
MUSIC_A_BYTES   = 8192
MUSIC_B_BYTES   = 2048
MUSIC_THEME_BYTES = 16384

        text

; ===========================================================================
; Public entries. Each masks interrupts for its body (the tick runs from the
; Timer C interrupt) and preserves every register it does not return.
; ===========================================================================

; The command entry, 0002B9CF. In: d0.w = ax (command << 12 | parameter).
; Out: d0.b = al. 0-2 effect, 3 select, 4 pause, 5 resume, 6 playing,
; 7 volume, 8 detect, 9-15 none (al = 0).
; DOS: flat 0002B9CF-0002B9F2 and the table at 0002C5D9.
; Kind: translated.
; Status: ported; tools/check-falcon-music.py.
music_command
        movem.l d1-d7/a0-a6,-(sp)
        move.w  sr,-(sp)
        ori.w   #$0700,sr
        lea     music_mem,a5
        move.w  d0,d7                           ; ax
        moveq   #-3,d0                          ; log marker 0xFD: a command, its ah
        move.w  d7,d1
        lsr.w   #8,d1
        bsr     music_log_marker
        move.b  d7,D_COMMAND(a5)                ; al
        move.w  d7,d1
        lsr.w   #8,d1
        move.b  d1,D_COMMAND+1(a5)              ; ah
        lsr.w   #4,d1                           ; the handler: ah >> 4
        andi.w  #$000f,d1
        moveq   #0,d0
        move.b  d7,d0                           ; al
        add.w   d1,d1
        move.w  .table(pc,d1.w),d1
        jsr     .table(pc,d1.w)
        move.w  (sp)+,sr
        movem.l (sp)+,d1-d7/a0-a6
        rts
.table
        dc.w    cmd_effect-.table,cmd_effect-.table,cmd_effect-.table
        dc.w    cmd_select-.table,cmd_pause-.table,cmd_resume-.table
        dc.w    cmd_query-.table,cmd_volume-.table,cmd_detect-.table
        dc.w    cmd_none-.table,cmd_none-.table,cmd_none-.table
        dc.w    cmd_none-.table,cmd_none-.table,cmd_none-.table,cmd_none-.table

; Start a song, 0002BD00. In: d0.b = flags (bit 0 queue, bit 1 loop),
; a0 = the song in memory (its `MS3-KGF` signature), d1.l = the flat address
; the original would have it at (the cursor's address space; 0 with a0 = 0
; does nothing, as ebx = 0 does).
; DOS: flat 0002BD00-0002BD74.
; Kind: translated.
music_start
        movem.l d0-d7/a0-a6,-(sp)
        move.w  sr,-(sp)
        ori.w   #$0700,sr
        lea     music_mem,a5
        tst.l   d1
        beq.s   .unmarked
        move.b  d0,d6
        moveq   #-2,d0                          ; log marker 0xFE: a song start
        move.b  d6,d1
        bsr     music_log_marker
        move.b  d6,d0
        move.l  6(sp),d1                        ; the caller's d1 (above the saved SR)
.unmarked
        move.l  a0,d2
        sub.l   d1,d2                           ; port - DOS for this song
        tst.l   d1
        beq.s   .out                            ; 0002BD00 or ebx,ebx / jz
        btst    #0,d0
        beq.s   .now
        tst.b   D_PLAYING(a5)
        beq.s   .now
        move.b  d0,D_QFLAGS(a5)                 ; 0002BD11
        move.l  d1,D_QUEUED(a5)                 ; 0002BD16
        move.l  d2,mus_queued_delta
        bra.s   .out
.now
        move.l  d2,mus_song_delta
        bsr     mus_begin
.out
        move.w  (sp)+,sr
        movem.l (sp)+,d0-d7/a0-a6
        rts

; Stop the music, 0002BEDC.
; Kind: translated.
music_stop
        movem.l d0-d7/a0-a6,-(sp)
        move.w  sr,-(sp)
        ori.w   #$0700,sr
        lea     music_mem,a5
        bsr     mus_stop
        move.w  (sp)+,sr
        movem.l (sp)+,d0-d7/a0-a6
        rts

; The game's own store into the master volume, [0002C5A8] = d0.b (00026818,
; 000267FC, 00026D37, 00026D59: the menu's Loud and Soft).
; Kind: translated.
music_set_volume
        move.b  d0,music_mem+D_MASTER
        rts

; Out: d0.b = [0002C49E], what command 6 reports (0xFF while a song runs).
music_playing
        moveq   #0,d0
        move.b  music_mem+D_PLAYING,d0
        rts

; The timer interrupt's call, 00001D2C `call [0002C48C]`. Runs in the Timer C
; interrupt (src/shake.s), once per 65 Hz tick.
; Kind: translated; the vector is a word flag.
music_tick
        addq.w  #1,music_tick_count
        tst.w   music_mem+D_TICKVEC
        beq.s   .ret                            ; 0002B9F6: ret
        movem.l d0-d7/a0-a6,-(sp)
        lea     music_mem,a5
        bsr     mus_tick
        movem.l (sp)+,d0-d7/a0-a6
.ret
        rts

; Startup, 000055B4-000055D8: detect the configured music device (COMANCHE.CFG
; byte 2 & 0x0F) with command 0x80 | device and select it with 0x30 | device
; when the detect returned non-zero, after [00019DF0] = 0x5000.
; DOS: flat 000055B4-000055DD.
; Kind: translated.
music_startup
        movem.l d0-d1,-(sp)
        move.w  #$5000,music_enable             ; 000055B4 [00019DF0] = 0x5000
        moveq   #0,d1
        move.b  snd_cfg+2,d1
        andi.b  #$0f,d1                         ; 000055C2
        move.w  d1,d0
        ori.w   #$8000,d0                       ; 000055C4 mov ah,0x80
        bsr     music_command
        tst.b   d0
        beq.s   .out                            ; 000055CB or al,al / je
        move.w  d1,d0
        ori.w   #$3000,d0                       ; 000055D6 mov ah,0x30
        bsr     music_command
.out
        movem.l (sp)+,d0-d1
        rts

; ===========================================================================
; The game's music calls, at the original's sites (sound-driver.md 5.1-5.9).
; Each preserves every register.
; ===========================================================================

; [00019DF0] again: the last music-enable command, 0x5000 (resume) or 0x4000
; (pause), sent as is at 000056D8, 00005AE3, 0002627D and 0002873D.
; Kind: translated.
music_resend
        move.l  d0,-(sp)
        move.w  music_enable,d0
        bsr     music_command
        move.l  (sp)+,d0
        rts

; The music half of the settings apply, 000267F3-00026842: [00025DD6] '0'
; Loud (volume 0xFA, resume), '1' Soft (0x64, resume), '2' Off (pause).
; Kind: translated.
music_apply_settings
        move.l  d0,-(sp)
        move.b  menu_settings+2,d0              ; 000267F3 mov al,[00025DD6]
        cmpi.b  #'0',d0
        bne.s   .not_loud
        move.b  #$fa,music_mem+D_MASTER         ; 000267FC
        bra.s   .resume
.not_loud
        cmpi.b  #'1',d0
        bne.s   .not_soft
        move.b  #$64,music_mem+D_MASTER         ; 00026818
.resume
        move.w  #$5000,music_enable
        bra.s   .send
.not_soft
        cmpi.b  #'2',d0
        bne.s   .out
        move.w  #$4000,music_enable             ; 00026834
.send
        bsr     music_resend
.out
        move.l  (sp)+,d0
        rts

; A Music radio of the options bar, 00026D30-00026D85: d0.b = its line,
; '0' Loud, '1' Soft, '2' Off (menu.s has stored the digit). Soft is 0x73
; here and 0x64 in the apply above - the original's own disagreement
; (sound-driver.md section 11, item 7).
; Kind: translated.
music_radio
        move.l  d0,-(sp)
        cmpi.b  #'0',d0
        bne.s   .not_loud
        move.b  #$fa,music_mem+D_MASTER         ; 00026D37
        bra.s   .resume
.not_loud
        cmpi.b  #'1',d0
        bne.s   .off
        move.b  #$73,music_mem+D_MASTER         ; 00026D59
.resume
        move.w  #$5000,music_enable
        bra.s   .send
.off
        move.w  #$4000,music_enable             ; 00026D7B
.send
        bsr     music_resend
        move.l  (sp)+,d0
        rts

; The options bar opens (00025E02): pause the music.
music_bar_open
        move.l  d0,-(sp)
        move.w  #$4000,d0
        bsr     music_command
        move.l  (sp)+,d0
        rts

; Program exit, 00006B2F-00006B38: stop the song, then select device 0 - the
; tick vector back to the `ret`.
music_shutdown
        move.l  d0,-(sp)
        bsr     music_stop
        move.w  #$3000,d0
        bsr     music_command
        move.l  (sp)+,d0
        rts

; The start of every attract pass, 000056C4-000056D8: stop, no song, then
; [00019DF0].
music_attract_pass
        bsr     music_stop                      ; 000056C4 call 0002BEDC
        clr.l   music_mem+D_SONG                ; 000056C9
        bra     music_resend                    ; 000056D8

; The even pass's side screen, 000056F9 and 00005771: MENUMUS2.MS3 raw to the
; 0x2DB10 buffer, played looped.
music_side_start
        movem.l d0-d1/a0-a1,-(sp)
        lea     name_menumus2,a0
        bsr     music_load_a
        moveq   #2,d0
        bra     music_play_a

; The odd pass's fanfare screen, 000057EE-00005805 and 00005851: FANFARE.RLE
; into the theme ([00019E8C]), played once.
music_fanfare_start
        movem.l d0-d1/a0-a1,-(sp)
        lea     name_fanfare,a0
        bsr     music_load_theme
        moveq   #0,d0
        bra     music_play_theme

; The title after the fanfare, 00005896-000058B4 and 0000596F: stop, no song,
; OPENMUS.MS3 raw to 0x2DB10, played once.
music_title_start
        movem.l d0-d1/a0-a1,-(sp)
        bsr     music_stop                      ; 00005896
        clr.l   music_mem+D_SONG                ; 0000589B
        lea     name_openmus,a0
        bsr     music_load_a                    ; 000058AA
        moveq   #0,d0
        bra     music_play_a                    ; 0000596F

; Every way into the main menu (00005AE3 and the menu chain's 00028CA2-
; 00028CE3): [00019DF0], then MENUMUS1.MS3 to 0x2DB10 and MENUMUS2.MS3 to
; 0x2DF10, the first played once and the second queued behind it, looped.
music_menu_enter
        movem.l d0-d1/a0-a1,-(sp)
        bsr     music_resend                    ; 00005AE3
        lea     name_menumus1,a0
        bsr     music_load_a                    ; 00028CA2
        lea     name_menumus2,a0
        lea     music_buf_b,a1
        move.l  #MUSIC_B_BYTES,d1
        bsr     music_load_raw                  ; 00028CB9
        seq     d0
        move.b  d0,-(sp)
        moveq   #0,d0
        lea     music_buf_a,a0
        move.l  #MUSIC_A_DOS,d1
        tst.w   music_a_ok
        bne.s   .a
        moveq   #0,d1                           ; a missing file: no song
.a
        bsr     music_start                     ; 00028CD7
        moveq   #3,d0
        lea     music_buf_b,a0
        move.l  #MUSIC_B_DOS,d1
        tst.b   (sp)+
        bne.s   .b
        moveq   #0,d1
.b
        bsr     music_start                     ; 00028CE3
        movem.l (sp)+,d0-d1/a0-a1
        rts

; A mission's music, 000067EE-00006806: its resource line 6 into the theme.
music_theme_load
        movem.l d0-d1/a0-a1,-(sp)
        lea     mission_music_names,a0
        bsr     music_load_theme
        movem.l (sp)+,d0-d1/a0-a1
        rts

; The mission's music starts, 000069EF-00006A00: looped, unless the music
; device of COMANCHE.CFG is the literal '1' (the PC speaker).
music_theme_start
        cmpi.b  #'1',snd_cfg+2
        beq.s   .out                            ; 000069EF cmp [53DA],'1' / je
        movem.l d0-d1/a0-a1,-(sp)
        moveq   #2,d0
        bra     music_play_theme
.out
        rts

; The debrief's song, 000288C3-000288D5 / 000289FA-00028A0C and 00028A23: the
; mission's lose (line 10) or win (line 8) song, looped. In: d0.b = 0 lost,
; else won.
music_debrief_start
        movem.l d0-d1/a0-a1,-(sp)
        lea     mission_music_names+2*16,a0     ; lose
        tst.b   d0
        beq.s   .picked
        lea     mission_music_names+1*16,a0     ; win
.picked
        lea     music_buf_end,a1
        move.l  #MUSIC_THEME_BYTES,d1
        jsr     snd_bank_load                   ; 00015E6E
        tst.l   d0
        bne.s   .out                            ; nothing loaded: no song
        moveq   #2,d0
        lea     music_buf_end,a0
        move.l  #MUSIC_END_DOS,d1
        bsr     music_start
.out
        movem.l (sp)+,d0-d1/a0-a1
        rts

; Tails of the four starters above (they have pushed d0-d1/a0-a1).
music_play_a
        lea     music_buf_a,a0
        move.l  #MUSIC_A_DOS,d1
        tst.w   music_a_ok
        bne.s   music_play_tail
        moveq   #0,d1                           ; no song: ebx = 0 does nothing
        bra.s   music_play_tail
music_play_theme
        lea     music_buf_theme,a0
        move.l  #MUSIC_THEME_DOS,d1
        tst.w   music_theme_ok
        bne.s   music_play_tail
        moveq   #0,d1
music_play_tail
        bsr     music_start
        movem.l (sp)+,d0-d1/a0-a1
        rts

; a0 = name: the raw MS3 into the 0x2DB10 buffer (00015DD0).
music_load_a
        lea     music_buf_a,a1
        move.l  #MUSIC_A_BYTES,d1
        bsr     music_load_raw
        seq     d0
        ext.w   d0
        move.w  d0,music_a_ok
        rts

; a0 = name: a KRL0/KRL1 song into the theme buffer (00015E6E).
music_load_theme
        lea     music_buf_theme,a1
        move.l  #MUSIC_THEME_BYTES,d1
        jsr     snd_bank_load
        tst.l   d0
        seq     d0
        ext.w   d0
        move.w  d0,music_theme_ok
        rts

; A file read raw (00015DD0): a0 = name, a1 = buffer, d1 = capacity.
; Out: d0 = 0 when read (and Z set), -1 when missing.
music_load_raw
        movem.l d1-d3/a0-a2,-(sp)
        move.l  a1,a2
        move.l  d1,d3
        clr.w   -(sp)
        move.l  a0,-(sp)
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi.s   .fail
        move.w  d0,d2
        move.l  a2,-(sp)
        move.l  d3,-(sp)
        move.w  d2,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d3
        move.w  d2,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp
        tst.l   d3
        bmi.s   .fail
        moveq   #0,d0
        bra.s   .out
.fail
        moveq   #-1,d0
.out
        movem.l (sp)+,d1-d3/a0-a2
        tst.l   d0
        rts

; ===========================================================================
; Commands. Entered with a5 = music_mem, d0.b = al; return al in d0.b.
; ===========================================================================

; Command 9..15, 0002B9F3: al = 0.
cmd_none
        moveq   #0,d0
        rts

; Command 4, 0002BBC1: silence the music and refuse key-ons.
cmd_pause
        bsr     mus_silence
        st      D_PAUSED(a5)
        moveq   #-1,d0
        rts

; Command 5, 0002BBD0.
cmd_resume
        clr.b   D_PAUSED(a5)
        moveq   #-1,d0
        rts

; Command 6, 0002BBBB: al = [0002C49E].
cmd_query
        moveq   #0,d0
        move.b  D_PLAYING(a5),d0
        rts

; Command 7, 0002BB01: the master volume.
cmd_volume
        move.b  d0,D_MASTER(a5)
        moveq   #-1,d0
        rts

; Command 8, 0002BBDA: the detect of device al (0..5), through its column of
; the table at 0002C6F5; above 5 it is command 9.
cmd_detect
        cmpi.b  #5,d0
        bhi.s   cmd_none                        ; 0002BBE4 jna / jmp 0002B9F3
        tst.b   d0
        beq.s   .ret                            ; device 0: 0002B9F6, al as it was
        cmpi.b  #2,d0
        beq     opl_detect
        cmpi.b  #3,d0
        beq     opl_detect
        cmpi.b  #5,d0
        beq.s   .ret                            ; 0002C482: xor ah,ah (al kept)
        moveq   #0,d0                           ; 1, 4: nothing on a Falcon
.ret
        rts

; Command 3, 0002B9F7-0002BB00: select device al.
cmd_select
        tst.b   D_DEVICE(a5)
        beq.s   .switch                         ; 0002B9FC
        lea     D_VOICE(a5),a0                  ; 0002BA00 rep stosw x5
        moveq   #9,d1
.clear
        clr.b   (a0)+
        dbra    d1,.clear
        bsr     mus_silence                     ; 0002BA0F
        bsr     dev_silence                     ; 0002BA14 call [0002C681]
.switch
        move.b  D_COMMAND(a5),d1                ; 0002BA1A bl = al
        beq.s   .disable
        cmpi.b  #5,d1
        bhi.s   .disable
        cmpi.b  #1,d1
        beq.s   .disable_dev                    ; no speaker
        cmpi.b  #4,d1
        beq.s   .disable_dev                    ; no MPU-401
        move.b  d1,D_DEVICE(a5)                 ; 0002BA36
        clr.b   D_PAUSED(a5)                    ; 0002BA93
        ; 0002BA9A: init. Device 5's is a `ret` that leaves al = 0x82, the low
        ; byte of its detect routine's address from the last column copy.
        moveq   #-$7e,d0                        ; 0x82
        cmpi.b  #5,d1
        beq.s   .inited
        bsr     opl_init
.inited
        tst.b   d0
        beq.s   .disable                        ; 0002BAA0
        bsr     mus_stop                        ; 0002BAA4
        moveq   #0,d1
.reset
        st      D_MASTER(a5)                    ; 0002BAB0
        clr.l   D_SONG(a5)                      ; 0002BAB7
        clr.b   D_PLAYING(a5)                   ; 0002BAC1
        clr.b   D_SENTNOTE(a5,d1.w)
        clr.b   D_VOICE(a5,d1.w)
        clr.b   D_KEYON(a5,d1.w)
        move.w  d1,d2
        lsl.w   #2,d2
        move.l  #DEFAULT_ENV,D_ENVPTR(a5,d2.w)
        move.l  #DEFAULT_ENV,D_ENVSTART(a5,d2.w)
        addq.w  #1,d1
        cmpi.w  #10,d1
        blo.s   .reset
        move.w  #1,D_TICKVEC(a5)                ; 0002BAF4 0002BBF2
        moveq   #-1,d0
        rts
.disable_dev
        ; The device would be stored and its init run; on a Falcon there is
        ; nothing to init, which is the original's failed-init exit.
        move.b  d1,D_DEVICE(a5)
        clr.b   D_PAUSED(a5)
.disable
        clr.w   D_TICKVEC(a5)                   ; 0002BA29
        moveq   #0,d0
        rts

; Commands 0-2, 0002BB09-0002BB50: effect al. The second half's dword is
; tested at 0002D40C + al (the original indexes it with al, not 8 * al).
cmd_effect
        move.l  #FX_TABLE+4,D_FXBASE(a5)        ; 0002BB09-0002BB13
        moveq   #0,d1
        move.b  d0,d1
        add.l   #FX_TABLE+4,d1
        move.l  d1,d2
        bsr     mus_rom_le32                    ; 0002BB26 cmp dword [ebx],0
        tst.l   d2
        beq.s   .first
        move.w  d0,-(sp)
        bsr     fx_half
        move.w  (sp)+,d0
.first
        move.l  #FX_TABLE,D_FXBASE(a5)          ; 0002BB35-0002BB3F
        bsr     fx_half
        moveq   #-1,d0
        rts

; One half of effect d0.b, 0002BB51-0002BBBA: the first free channel of the
; device's order (the last one when all are busy), then the patch and the key.
fx_half
        moveq   #0,d4
        move.b  D_DEVICE(a5),d4
        lsl.w   #3,d4                           ; ebp = device * 8
        moveq   #8,d5                           ; ah
.find
        moveq   #0,d1
        move.b  D_VOICEORDER(a5,d4.w),d1        ; ch = bl
        tst.b   D_KEYON(a5,d1.w)
        beq.s   .found
        addq.w  #1,d4
        subq.b  #1,d5
        bne.s   .find
.found
        move.w  d1,d4                           ; ebp = the channel
        move.w  d1,d6                           ; ch
        moveq   #0,d1
        move.b  d0,d1
        lsl.w   #3,d1                           ; bx = al << 3 (16-bit)
        add.l   D_FXBASE(a5),d1                 ; the entry
        move.l  d1,a4
        move.l  a4,d2
        bsr     mus_rom_byte                    ; byte 0: the effect's ticks
        move.b  d2,D_VOICE(a5,d4.w)
        move.l  a4,d2
        addq.l  #1,d2
        bsr     mus_rom_byte
        subq.b  #1,d2                           ; byte 1 - 1: the patch
        move.b  d2,d0
        bsr     mus_load_patch                  ; 0002BB93 call 0002BF43 (ch = d6)
        ; 0002BB9A-0002BBB5: the volume nibble of the command, times byte 3.
        move.b  D_COMMAND+1(a5),d3              ; ah
        andi.b  #$0f,d3
        lsl.b   #4,d3
        bne.s   .vol
        st      d3                              ; 0002BBA9 mov ah,0xff
.vol
        move.l  a4,d2
        addq.l  #3,d2
        bsr     mus_rom_byte
        andi.w  #$00ff,d2
        andi.w  #$00ff,d3
        mulu    d3,d2                           ; ax = al * ah
        lsr.w   #8,d2
        move.b  d2,d7                           ; cl = ah
        move.l  a4,d2
        addq.l  #2,d2
        bsr     mus_rom_byte
        move.b  d2,d5                           ; ah = byte 2: the pitch
        bra     mus_key                         ; 0002BBB5 call 0002BC8B

; ===========================================================================
; The core.
; ===========================================================================

; Start the song at D_SONG's successor, 0002BD1D-0002BD74. In: d0.b = flags,
; d1.l = the song's DOS address, mus_song_delta set for it.
mus_begin
        move.b  d0,D_FLAGS(a5)                  ; 0002BD1D
        move.l  d1,D_SONG(a5)                   ; 0002BD22
        move.l  d1,d3
        addi.l  #$10,d3                         ; esi = ebx + 0x10
        moveq   #0,d4
.links
        move.l  d3,d2
        bsr     mus_song_byte
        move.b  d2,D_LINK(a5,d4.w)              ; 0002BD37 rep movsb
        addq.l  #1,d3
        addq.w  #1,d4
        cmpi.w  #10,d4
        blo.s   .links
        addq.l  #6,d3                           ; 0002BD39
        moveq   #0,d4
.patches
        move.l  d3,d2
        bsr     mus_song_byte
        move.b  d2,D_SONGPATCH(a5,d4.w)         ; 0002BD45
        st      D_LOADED(a5,d4.w)               ; 0002BD4B
        addq.l  #1,d3
        addq.w  #1,d4
        cmpi.w  #10,d4
        blo.s   .patches
        addq.l  #6,d3                           ; 0002BD56
        move.l  d3,D_CURSOR(a5)                 ; 0002BD59
        bsr     mus_stop                        ; 0002BD5F
        move.w  #1,D_COUNTDOWN(a5)              ; 0002BD64
        st      D_PLAYING(a5)                   ; 0002BD6D
        rts

; 0002BEDC: not playing, nothing queued, the channels silenced.
mus_stop
        clr.b   D_PLAYING(a5)
        clr.b   D_QFLAGS(a5)
        ; fall into mus_silence

; 0002BF12-0002BF39: channels 0..9: pitch offset 0, and key off unless an
; effect owns the channel.
mus_silence
        moveq   #0,d6                           ; ch
.next
        clr.b   D_PITCHOFS(a5,d6.w)             ; 0002BF18
        tst.b   D_VOICE(a5,d6.w)
        bne.s   .skip                           ; 0002BF24
        moveq   #0,d5                           ; ah = 0
        moveq   #0,d7                           ; cl = 0
        move.w  d6,-(sp)
        bsr     mus_key
        move.w  (sp)+,d6
.skip
        addq.w  #1,d6
        cmpi.w  #10,d6
        blo.s   .next
        rts

; Key a channel, 0002BC8B-0002BCE9. In: d6.w = ch, d5.b = ah (0 = off),
; d7.b = cl (velocity). Out: d5.b = ah as the original leaves it.
mus_key
        tst.b   D_PAUSED(a5)
        bne.s   .off                            ; 0002BC8E
        tst.b   d5
        beq.s   .off                            ; 0002BC97
        moveq   #0,d0
        move.b  D_SCALE(a5,d6.w),d0             ; 0002BC9C
        moveq   #0,d1
        move.b  D_MASTER(a5),d1
        mulu    d1,d0                           ; 0002BCA2 mul byte
        lsr.w   #8,d0                           ; ah
        add.b   d7,d7                           ; 0002BCA8 shl cl,1
        addq.b  #1,d0                           ; 0002BCAA inc ah
        andi.w  #$00ff,d0
        moveq   #0,d1
        move.b  d7,d1
        mulu    d1,d0                           ; 0002BCAE mul cl
        lsr.w   #8,d0
        move.b  d0,d7                           ; 0002BCB0 cl = ah
        move.w  d6,d0
        lsl.w   #2,d0
        move.l  D_ENVSTART(a5,d0.w),D_ENVPTR(a5,d0.w)   ; 0002BCB2
        move.b  #1,D_KEYON(a5,d6.w)             ; 0002BCC0
        add.b   D_TRANSPOSE(a5,d6.w),d5         ; 0002BCC8
        move.b  d5,D_BASENOTE(a5,d6.w)          ; 0002BCCE
        st      D_SENTNOTE(a5,d6.w)             ; 0002BCD4
        bra     dev_note
.off
        moveq   #0,d5                           ; 0002BCE1 mov ah,0
        clr.b   D_KEYON(a5,d6.w)
        bra     dev_note

; Load patch d0.b on channel d6.w, 0002BF43-0002BF87 (with d1 = 1 also
; recorded as the song's patch: 0002BF3A).
mus_load_patch_song
        move.b  d0,D_SONGPATCH(a5,d6.w)         ; 0002BF3D
mus_load_patch
        moveq   #0,d1
        move.b  d0,d1
        move.b  d1,D_LOADED(a5,d6.w)            ; 0002BF49
        move.w  d1,d2
        lsl.w   #2,d2
        addi.l  #D_ENVTABLE+MUS_BASE,d2
        bsr     mus_rom_le32                    ; 0002BF4F [2D5E6 + 4*patch]
        move.w  d6,d0
        lsl.w   #2,d0
        move.l  d2,D_ENVSTART(a5,d0.w)
        move.l  d2,D_ENVPTR(a5,d0.w)
        move.l  #D_SCALETAB+MUS_BASE,d2
        add.l   d1,d2
        bsr     mus_rom_byte                    ; 0002BF64
        move.b  d2,D_SCALE(a5,d6.w)
        move.l  #D_TRANSPOSETAB+MUS_BASE,d2
        add.l   d1,d2
        bsr     mus_rom_byte                    ; 0002BF70
        move.b  d2,D_TRANSPOSE(a5,d6.w)
        move.b  D_LOADED(a5,d6.w),d0            ; 0002BF7C
        bra     dev_patch

; The tick, 0002BBF2-0002BC7B.
mus_tick
        tst.b   D_PLAYING(a5)
        beq.s   .channels
        bsr     mus_sequencer                   ; 0002BBFB
.channels
        moveq   #9,d6                           ; ebx = 9
.channel
        move.b  D_BASENOTE(a5,d6.w),d5          ; 0002BC05 ah
        tst.b   D_VOICE(a5,d6.w)
        beq.s   .offset                         ; 0002BC12
        subq.b  #1,D_VOICE(a5,d6.w)             ; 0002BC14
        cmpi.b  #2,D_VOICE(a5,d6.w)
        bne.s   .offset
        moveq   #0,d5                           ; 0002BC23 mov ah,0
        move.w  d6,-(sp)
        bsr     mus_key                         ; 0002BC28
        move.w  (sp)+,d6
        ; The OPL write helper returns with ax = 0 (its delay loop counts ax
        ; down), so ah is 0 here after the key-off: the pitch pass below sends
        ; pitch 0 (sound-driver.md section 3.4, "Quirk").
        moveq   #0,d5
.offset
        add.b   D_PITCHOFS(a5,d6.w),d5          ; 0002BC2E
        move.w  d6,d4
        lsl.w   #2,d4
.env
        move.l  D_ENVPTR(a5,d4.w),d2            ; 0002BC34
        bsr     mus_env_byte
        cmpi.b  #$80,d2
        beq.s   .pitch                          ; hold
        cmpi.b  #$81,d2
        bne.s   .step
        move.l  D_ENVSTART(a5,d4.w),D_ENVPTR(a5,d4.w)   ; 0002BC50 loop
        bra.s   .env
.step
        add.b   d2,d5                           ; 0002BC45
        addq.l  #1,D_ENVPTR(a5,d4.w)
.pitch
        cmp.b   D_SENTNOTE(a5,d6.w),d5          ; 0002BC62
        beq.s   .done
        move.b  d5,D_SENTNOTE(a5,d6.w)
        move.w  d6,-(sp)
        bsr     dev_pitch                       ; 0002BC71 call [0002C6B9]
        move.w  (sp)+,d6
.done
        subq.w  #1,d6
        bpl.s   .channel                        ; 0002BC79 jns
        rts                                     ; 0002BC7B: the end slot, a `ret`

; The sequencer, 0002BE68-0002BEDB.
mus_sequencer
        subq.w  #1,D_COUNTDOWN(a5)
        bne     .ret
.event
        bsr     mus_read_event                  ; 0002BE71
        tst.b   d0
        beq     mus_end_of_song                 ; 0002BE78
        move.w  d3,D_COUNTDOWN(a5)              ; 0002BE7A dx
        cmpi.b  #$ff,d6
        beq.s   .next                           ; 0002BE81 ch = 0xFF
        andi.w  #$00ff,d6
.channel
        tst.b   D_VOICE(a5,d6.w)
        bne.s   .link                           ; 0002BE89 cmp [..],bh
        clr.b   D_VOICE(a5,d6.w)
        move.b  D_LOADED(a5,d6.w),d0
        cmp.b   D_SONGPATCH(a5,d6.w),d0
        beq.s   .key                            ; 0002BE9E
        move.b  D_SONGPATCH(a5,d6.w),d0
        movem.w d5-d7,-(sp)
        bsr     mus_load_patch                  ; 0002BEAE call 0002BF43
        movem.w (sp)+,d5-d7
.key
        movem.w d5-d7,-(sp)
        add.b   d5,d5                           ; 0002BEB7 shl ah,1
        bsr     mus_key
        movem.w (sp)+,d5-d7
.link
        moveq   #0,d0
        move.b  D_LINK(a5,d6.w),d0              ; 0002BEC3
        beq.s   .next
        subq.b  #1,d0
        move.w  d0,d6
        bra.s   .channel
.next
        tst.w   D_COUNTDOWN(a5)
        beq.s   .event                          ; 0002BED9
.ret
        rts

; The end of the song, 0002BE0F-0002BE67.
mus_end_of_song
        move.w  #1,D_COUNTDOWN(a5)
        bsr     mus_silence
        clr.b   D_PLAYING(a5)
        btst    #0,D_QFLAGS(a5)
        beq.s   .loop
        move.l  D_QUEUED(a5),d1                 ; 0002BE2D
        move.b  D_QFLAGS(a5),d0
        clr.b   D_QFLAGS(a5)
        move.l  mus_queued_delta,mus_song_delta
        bra     mus_begin
.loop
        btst    #1,D_FLAGS(a5)
        beq.s   .none
        move.l  D_SONG(a5),d1                   ; 0002BE4D
        move.b  D_FLAGS(a5),d0
        bra     mus_begin
.none
        clr.l   D_SONG(a5)                      ; 0002BE5D
        rts

; Read the next event, 0002BD75-0002BE0E.
; Out: d0.b = 0 at the end (FF 2F), else 1 with d6.b = ch (0xFF: keys
; nothing), d5.b = ah (the note), d7.b = cl (the velocity), d3.w = dx (the
; delay to the next event).
mus_read_event
        move.l  D_CURSOR(a5),d4                 ; ebx
        move.l  d4,d2
        bsr     mus_song_byte
        move.b  d2,d0                           ; al: the status
        move.l  d4,d2
        addq.l  #1,d2
        bsr     mus_song_byte
        move.b  d2,d5                           ; ah
        cmpi.b  #$ff,d0
        bne.s   .event
        cmpi.b  #$2f,d5
        bne.s   .event
        moveq   #0,d0                           ; 0002BD86
        rts
.event
        move.l  d4,d3                           ; edx = ebx
        moveq   #0,d6
        move.b  d0,d6
        andi.b  #$0f,d6                         ; ch = bl = al & 0x0F
        move.w  d6,d1                           ; ebx, the channel index
        move.b  d0,d7
        andi.b  #$f0,d7                         ; cl
        cmpi.b  #$90,d7
        bne.s   .not_on
        move.b  d5,D_NOTE(a5,d1.w)              ; 0002BD9D
        addq.l  #1,d3
        bra.s   .data
.not_on
        cmpi.b  #$80,d7
        bne.s   .other
        moveq   #0,d5                           ; 0002BDAB
        moveq   #0,d7
        move.b  d5,D_NOTE(a5,d1.w)
        addq.l  #1,d3
        move.l  d3,d4                           ; ebx = edx
        bra.s   .delay
.other
        cmpi.b  #$c0,d7
        bne.s   .not_patch
        move.b  d5,d0                           ; 0002BDBF al = ah
        move.l  d3,-(sp)
        bsr     mus_load_patch_song             ; 0002BDC2 call 0002BF3A
        move.l  (sp)+,d3
        bra.s   .keyless
.not_patch
        cmpi.b  #$e0,d7
        bne.s   .not_bend
        move.b  d5,D_PITCHOFS(a5,d1.w)          ; 0002BDD6
        bra.s   .keyless
.not_bend
        cmpi.b  #$b0,d7
        bne.s   .keyless
        addq.l  #1,d3                           ; 0002BDE5
.keyless
        st      d6                              ; 0002BDE6 ch = 0xFF
.data
        move.l  d3,d4                           ; 0002BDE8 ebx = edx
        addq.l  #1,d4
        move.l  d4,d2
        bsr     mus_song_byte
        move.b  d2,d7                           ; cl = [ebx]
        addq.w  #1,d4                           ; 0002BDED inc bx: 16 bits
.delay
        move.l  d4,d2                           ; 0002BDEF
        bsr     mus_song_byte
        moveq   #0,d3
        move.b  d2,d3
        bpl.s   .short
        andi.b  #$7f,d3                         ; 0002BDF6
        addq.l  #1,d4
        move.l  d4,d2
        bsr     mus_song_byte
        lsl.w   #7,d3                           ; dh = dl, dl = 0, dx >>= 1
        or.b    d2,d3                           ; 0002BE03 dl |= al (b1 unmasked)
.short
        addq.l  #1,d4                           ; 0002BE05
        move.l  d4,D_CURSOR(a5)
        moveq   #1,d0
        rts

; ===========================================================================
; The OPL2 device (2 and 3), 0002C1B8-0002C431.
; ===========================================================================

; The device's routines by slot. A device other than 2, 3 has `ret` slots
; (device 5 and the empty device 0); 1 and 4 never get selected here.
dev_note
        bsr.s   dev_is_opl
        beq.s   opl_note
        rts
dev_pitch
        bsr.s   dev_is_opl
        beq     opl_pitch
        rts
dev_patch
        bsr.s   dev_is_opl
        beq     opl_patch
        rts
dev_silence
        bsr.s   dev_is_opl
        beq     opl_silence
        rts
; Z set when the selected device is the OPL2.
dev_is_opl
        cmpi.b  #2,D_DEVICE(a5)
        beq.s   .yes
        cmpi.b  #3,D_DEVICE(a5)
.yes
        rts

; One register write, 0002C1B8: d0.b = register, d1.b = value. The helper
; leaves ax = 0; its callers here reload what they need.
opl_out
        movem.l d0-d2/a0-a1,-(sp)
        bsr     music_opl_write
        movem.l (sp)+,d0-d2/a0-a1
        rts

; Table 3, 0002C3C9-0002C431: key on (d5 = ah != 0, d7 = cl) or off, on music
; channel d6.
opl_note
        moveq   #0,d4
        move.b  D_OPLVOICEOF(a5,d6.w),d4        ; ch
        cmpi.b  #9,d4
        bhs.s   .ret
        move.b  D_OPLOP2(a5,d4.w),d3            ; dh
        tst.b   d5
        beq.s   .off
        move.b  d7,d2
        lsr.b   #2,d2                           ; 0002C3E1 shr cl,2
        addi.b  #$20,d2
        cmpi.b  #$3f,d2
        blo.s   .level
        moveq   #$3f,d2
.level
        move.b  D_OPLMODLEVEL(a5,d4.w),d1       ; 0002C3EE
        or.b    d2,d1
        eori.b  #$3f,d1
        moveq   #$40,d0
        or.b    d3,d0
        bsr     opl_out                         ; 40 + carrier
        move.b  D_OPLSHADOW(a5,d4.w),d1
        ori.b   #$20,d1
        move.b  d1,D_OPLSHADOW(a5,d4.w)
        moveq   #-$50,d0                        ; 0xB0
        or.b    d4,d0
        bra     opl_out
.off
        move.b  D_OPLSHADOW(a5,d4.w),d1         ; 0002C41A
        andi.b  #$df,d1
        move.b  d1,D_OPLSHADOW(a5,d4.w)
        moveq   #-$50,d0
        or.b    d4,d0
        bra     opl_out
.ret
        rts

; Table 4, 0002C380-0002C3C8: pitch d5 (ah) on music channel d6.
opl_pitch
        moveq   #0,d4
        move.b  D_OPLVOICEOF(a5,d6.w),d4
        cmpi.b  #9,d4
        bhs.s   .ret
        moveq   #0,d0
        move.b  d5,d0
        add.w   d0,d0
        move.b  D_FNUM(a5,d0.w),d1              ; al: the LE word's low byte
        move.b  D_FNUM+1(a5,d0.w),d2            ; ah
        move.b  D_OPLSHADOW(a5,d4.w),d3
        andi.b  #$e0,d3
        or.b    d3,d2
        move.b  d2,D_OPLSHADOW(a5,d4.w)
        moveq   #-$60,d0                        ; 0xA0
        or.b    d4,d0
        bsr     opl_out
        move.b  D_OPLSHADOW(a5,d4.w),d1
        moveq   #-$50,d0
        or.b    d4,d0
        bra     opl_out
.ret
        rts

; Table 5, 0002C254-0002C311: patch d0.b on music channel d6.
opl_patch
        moveq   #0,d4
        move.b  D_OPLVOICEOF(a5,d6.w),d4
        cmpi.b  #9,d4
        bhs     .ret
        moveq   #0,d2
        move.b  d0,d2
        lsl.w   #4,d2
        lea     D_PATCHES(a5,d2.w),a0           ; the patch
        move.b  D_OPLOP2(a5,d4.w),d3            ; dh
        move.b  D_OPLOP1(a5,d4.w),d7            ; dl
        move.b  D_OPLSHADOW(a5,d4.w),d1
        andi.b  #$df,d1                         ; not stored back
        moveq   #-$50,d0
        or.b    d4,d0
        bsr     opl_out                         ; B0: key off
        move.b  (a0),d1
        moveq   #$20,d0
        or.b    d3,d0
        bsr     opl_out
        move.b  2(a0),d1
        moveq   #$60,d0
        or.b    d3,d0
        bsr     opl_out
        move.b  3(a0),d1
        moveq   #-$80,d0
        or.b    d3,d0
        bsr     opl_out
        move.b  4(a0),d1
        moveq   #-$20,d0                        ; 0xE0
        or.b    d3,d0
        bsr     opl_out
        move.b  5(a0),d1
        moveq   #$20,d0
        or.b    d7,d0
        bsr     opl_out
        move.b  6(a0),d1
        eori.b  #$3f,d1
        moveq   #$40,d0
        or.b    d7,d0
        bsr     opl_out
        move.b  7(a0),d1
        moveq   #$60,d0
        or.b    d7,d0
        bsr     opl_out
        move.b  8(a0),d1
        moveq   #-$80,d0
        or.b    d7,d0
        bsr     opl_out
        move.b  9(a0),d1
        moveq   #-$20,d0
        or.b    d7,d0
        bsr     opl_out
        move.b  10(a0),d1
        moveq   #-$40,d0                        ; 0xC0
        or.b    d4,d0
        bsr     opl_out
        move.b  1(a0),D_OPLMODLEVEL(a5,d4.w)    ; 0002C308
.ret
        rts

; Table 2, 0002C354-0002C37E: every voice's carrier level 3F and B0 0.
opl_silence
        moveq   #0,d4
.voice
        move.b  D_OPLOP2(a5,d4.w),d0
        ori.b   #$40,d0
        moveq   #$3f,d1
        bsr     opl_out
        moveq   #-$50,d0
        or.b    d4,d0
        moveq   #0,d1
        bsr     opl_out
        addq.w  #1,d4
        cmpi.w  #9,d4
        blo.s   .voice
        rts

; Table 0, 0002C312-0002C353: 01 = 20, 08 = 00, BD = C0, silence, then the B0
; shadow 1F and patch 0 on channels 0..8. Out: d0.b = 0xFF.
opl_init
        moveq   #1,d0
        moveq   #$20,d1
        bsr     opl_out
        moveq   #8,d0
        moveq   #0,d1
        bsr     opl_out
        moveq   #-$43,d0                        ; 0xBD
        moveq   #-$40,d1                        ; 0xC0
        bsr     opl_out
        bsr     opl_silence
        moveq   #0,d6
.channel
        move.b  #$1f,D_OPLSHADOW(a5,d6.w)       ; 0002C33D [2D116 + ebx]
        moveq   #0,d0
        bsr     opl_patch                       ; ch = bl
        addq.w  #1,d6
        cmpi.w  #9,d6
        blo.s   .channel
        moveq   #-1,d0
        rts

; Table 6, 0002C1EA-0002C253: is an OPL2 there? Out: d0.b = 0xFF or 0.
opl_detect
        moveq   #4,d0
        moveq   #$60,d1
        bsr     opl_out
        moveq   #4,d0
        moveq   #-$80,d1
        bsr     opl_out
        bsr     music_opl_status
        andi.b  #$e0,d0
        move.b  d0,d6                           ; bh
        moveq   #2,d0
        moveq   #-1,d1
        bsr     opl_out
        moveq   #4,d0
        moveq   #$21,d1
        bsr     opl_out
        bsr     music_opl_status
        andi.b  #$e0,d0
        eori.b  #$c0,d0
        move.b  d0,d7                           ; bl
        moveq   #4,d0
        moveq   #$60,d1
        bsr     opl_out
        moveq   #4,d0
        moveq   #-$80,d1
        bsr     opl_out
        or.b    d7,d6
        bne.s   .absent
        moveq   #-1,d0
        rts
.absent
        moveq   #0,d0
        rts

; ===========================================================================
; Memory.
; ===========================================================================

; d2.l = a DOS address in the current song -> d2.b = its byte.
mus_song_byte
        move.l  a0,-(sp)
        move.l  d2,a0
        adda.l  mus_song_delta,a0
        moveq   #0,d2
        move.b  (a0),d2
        move.l  (sp)+,a0
        rts

; d2.l = a flat address -> d2.b = the image's byte there, through mus_mem, or
; 0x00 for an address outside it (the out-of-image envelope of patch 255).
mus_env_byte
mus_rom_byte
        subi.l  #MUS_BASE,d2
        cmpi.l  #MUS_BYTES,d2
        bhs.s   .open
        move.l  a0,-(sp)
        lea     music_mem,a0
        move.b  0(a0,d2.l),d2
        move.l  (sp)+,a0
        andi.l  #$ff,d2
        rts
.open
        addq.l  #1,music_open_bus
        moveq   #0,d2
        rts

; d2.l = a flat address -> d2.l = the little-endian dword there (each byte
; through mus_rom_byte). Preserves everything else.
mus_rom_le32
        movem.l d0-d1/d3,-(sp)
        move.l  d2,d3
        moveq   #3,d0
        moveq   #0,d1
.byte
        move.l  d3,d2
        add.l   d0,d2
        bsr     mus_rom_byte
        lsl.l   #8,d1
        or.b    d2,d1
        dbra    d0,.byte
        move.l  d1,d2
        movem.l (sp)+,d0-d1/d3
        rts

; ===========================================================================
; The OPL2 attachment point.
; ===========================================================================

; One register write, d0.b = register, d1.b = value. With music_log_on set
; (the test harness, or a capture build), the pair is appended to music_log
; with the tick count it was made in. The synthesiser attaches here.
; Kind: N/A - platform attachment point (Target artefact).
music_opl_write
        ; Register 4 drives the status the detect reads (music_opl_status).
        cmpi.b  #4,d0
        bne.s   .not_timer
        btst    #7,d1
        beq.s   .no_reset
        clr.b   music_chip_status               ; IRQ reset: flags clear
        bra.s   .not_timer
.no_reset
        btst    #0,d1
        beq.s   .not_timer
        move.b  #$c0,music_chip_status          ; timer 1 started: IRQ, T1 (expired)
.not_timer
    ifne OPL2
        tst.w   opl_host_running
        beq.s   .no_synth
        jsr     opl_host_write                  ; F030OPL2: decoded into the DSP's stream
.no_synth
    endc
        tst.w   music_log_on
        beq.s   .out
        move.l  music_log_count,d2
        cmpi.l  #LOG_ENTRIES,d2
        bhs.s   .out
        lsl.l   #2,d2
        lea     music_log,a0
        move.w  music_tick_count,0(a0,d2.l)
        move.b  d0,2(a0,d2.l)
        move.b  d1,3(a0,d2.l)
        addq.l  #1,music_log_count
.out
        rts

; A marker in music_log (register 0xFD/0xFE, which the driver never writes),
; so a capture build can cut the stream at commands and song starts.
music_log_marker
        movem.l d0-d2/a0,-(sp)
        tst.w   music_log_marks
        beq.s   .out
        move.l  music_log_count,d2
        cmpi.l  #LOG_ENTRIES,d2
        bhs.s   .out
        lsl.l   #2,d2
        lea     music_log,a0
        move.w  music_tick_count,0(a0,d2.l)
        move.b  d0,2(a0,d2.l)
        move.b  d1,3(a0,d2.l)
        addq.l  #1,music_log_count
.out
        movem.l (sp)+,d0-d2/a0
        rts

; The OPL2 status port as the detect reads it (0002C20D, 0002C236). A test
; harness answers through music_status_hook. A synthesiser behind
; music_opl_write sets music_chip_present, and the status is then a YM3812's
; as the detect drives it: 0x00 once the timers are reset (04 <- 80), 0xC0
; once timer 1 has run (04 <- 21; the detect's wait outlasts its 80 us).
; With neither, the reads answer 0xFF: the detect fails, as on a PC without
; the card (capture detect-absent), the tick vector stays `ret`, no song ever
; ends and the fanfare and title screens run their full counts (section 7).
; Out: d0.b = status.
music_opl_status
        move.l  music_status_hook,d0
        beq.s   .chip
        move.l  a0,-(sp)
        move.l  d0,a0
        jsr     (a0)
        move.l  (sp)+,a0
        rts
.chip
        tst.w   music_chip_present
        beq.s   .absent
        moveq   #0,d0
        move.b  music_chip_status,d0
        rts
.absent
        moveq   #-1,d0
        rts

        global  music_status_hook, music_open_bus, music_chip_present

        data
        even
music_status_hook
        dc.l    0
; Set by a synthesiser behind music_opl_write. MUSIC_CHIP=1 builds the virtual
; status in without one, so the game's music path runs into music_log.
    ifnd MUSIC_CHIP
MUSIC_CHIP = 0
    endc
music_chip_present
        dc.w    MUSIC_CHIP
music_chip_status
        dc.b    $ff
        even
music_log_on
        dc.w    MUSIC_CHIP                      ; a MUSIC_CHIP build logs from the start
music_log_marks
        dc.w    MUSIC_CHIP                      ; ... with the song and command markers

name_menumus1
        dc.b    "MENUMUS1.MS3",0
name_menumus2
        dc.b    "MENUMUS2.MS3",0
name_openmus
        dc.b    "OPENMUS.MS3",0
name_fanfare
        dc.b    "FANFARE.RLE",0
        even

        bss
        even
music_enable
        ds.w    1                               ; [00019DF0]
music_a_ok
        ds.w    1
music_theme_ok
        ds.w    1
music_buf_a
        ds.b    MUSIC_A_BYTES
music_buf_b
        ds.b    MUSIC_B_BYTES
music_buf_theme
        ds.b    MUSIC_THEME_BYTES
music_buf_end
        ds.b    MUSIC_THEME_BYTES
; flat 0002C48C-0002DA00 (see the header); src/origexe.s fills the tables.
music_mem
        ds.b    MUS_BYTES
        even
mus_song_delta
        ds.l    1                               ; port address - DOS address, current song
mus_queued_delta
        ds.l    1                               ; the same for the queued song
music_open_bus
        ds.l    1
music_tick_count
        ds.w    1
music_log_count
        ds.l    1
music_log
        ds.l    LOG_ENTRIES

        end
