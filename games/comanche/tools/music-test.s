; N/A - target artefact: a stand-alone test program for src/music.s, no DOS routine.
; Record: analysis/functions/sound-driver.md section 9
;
; Reads MUSTAB.BIN (the original's image bytes 0002C48C-0002DA00, written by
; tools/check-falcon-music.py from the unpacked image) and MUSIC.SCR from the
; program's directory, drives the music driver through its public entries and
; writes, for every op, what the driver did to MUSOUT.BIN. The checker compares
; that with the original's captures (build/sound/*.json).
;
; Script (big-endian):
;   00                      end
;   01 n.w {addr.l len.w bytes [pad]}*n   a scenario: the driver block to the
;                           image's bytes, the DOS arena cleared, then each
;                           span placed at its DOS address
;   02 ax.w n.w status*n [pad]           music_command, the OPL status reads
;                           answered in order
;   03 al.w ebx.l           music_start (the song at DOS address ebx)
;   04                      music_stop
;   05                      music_tick
;   06 addr.l len.w bytes [pad]           place bytes in the arena
; Output per op (02-06): n.w writes, al.b, status reads left.b, checksum.l,
; then n x (register.b, value.b).

        include "inc/comanche.s"
        include "inc/gemdos.s"

        global  _main
        global  snd_cfg, snd_bank_load, menu_settings, mission_music_names

        xref    music_command, music_start, music_stop, music_tick
        xref    music_mem, music_log, music_log_count, music_log_on
        xref    music_status_hook

SCRIPT_BYTES    = 6*1024*1024
OUT_BYTES       = 2*1024*1024
ARENA_BASE      = $400000
ARENA_BYTES     = $40000
MUS_BASE        = $2C48C
MUS_BYTES       = $2DA00-$2C48C

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

        lea     name_tables,a0
        lea     tables,a1
        move.l  #MUS_BYTES,d1
        bsr     read_file
        lea     name_script,a0
        lea     script,a1
        move.l  #SCRIPT_BYTES,d1
        bsr     read_file
        tst.l   d0
        bmi     .done

        move.l  #status_answer,music_status_hook
        move.w  #1,music_log_on
        lea     script,a5
        lea     out,a4
.op
        moveq   #0,d0
        move.b  (a5)+,d0
        beq     .finished
        clr.l   music_log_count
        cmpi.b  #1,d0
        beq     .scenario
        cmpi.b  #2,d0
        beq     .command
        cmpi.b  #3,d0
        beq     .start
        cmpi.b  #4,d0
        beq     .stop
        cmpi.b  #5,d0
        beq     .tick
        cmpi.b  #6,d0
        beq     .place
        bra     .finished

.scenario
        lea     music_mem,a0
        move.w  #MUS_BYTES-1,d1
.clear_block
        clr.b   (a0)+
        dbra    d1,.clear_block
        ; The image's bytes, then the tick vector cleared: the image holds the
        ; code address 0002B9F6 there, which src/music.s keeps as a 0 flag.
        lea     tables,a0
        lea     music_mem,a1
        move.w  #MUS_BYTES-1,d1
.image
        move.b  (a0)+,(a1)+
        dbra    d1,.image
        clr.l   music_mem
        lea     arena,a0
        move.l  #ARENA_BYTES/4-1,d1
.clear_arena
        clr.l   (a0)+
        subq.l  #1,d1
        bpl.s   .clear_arena
        move.w  (a5)+,d6
        bra.s   .spans_next
.spans
        bsr     place
.spans_next
        dbra    d6,.spans
        bra     .op

.place
        bsr     place
        bra     .emit_none

.command
        move.w  (a5)+,d0                        ; ax
        move.w  (a5)+,d1                        ; status answers
        move.l  a5,status_next
        move.w  d1,status_left
        adda.w  d1,a5
        btst    #0,d1
        beq.s   .even
        addq.l  #1,a5
.even
        bsr     music_command
        move.b  d0,d7
        bra     .emit
.start
        move.w  (a5)+,d0                        ; al
        move.l  (a5)+,d1                        ; ebx
        lea     arena,a0
        adda.l  d1,a0
        suba.l  #ARENA_BASE,a0
        bsr     music_start
        moveq   #0,d7
        bra     .emit
.stop
        bsr     music_stop
        moveq   #0,d7
        bra     .emit
.tick
        bsr     music_tick
        moveq   #0,d7
        bra     .emit

.emit_none
        moveq   #0,d7
.emit
        move.l  music_log_count,d1
        move.w  d1,(a4)+
        move.b  d7,(a4)+
        move.b  status_left+1,(a4)+
        clr.w   status_left
        bsr     checksum
        move.l  d0,(a4)+
        lea     music_log,a0
        bra.s   .pair_next
.pair
        move.b  2(a0),(a4)+
        move.b  3(a0),(a4)+
        addq.l  #4,a0
.pair_next
        dbra    d1,.pair
        bra     .op

.finished
        clr.w   -(sp)
        pea     name_out
        move.w  #60,-(sp)                       ; Fcreate
        trap    #1
        addq.l  #8,sp
        move.w  d0,d7
        move.l  a4,d0
        sub.l   #out,d0
        pea     out
        move.l  d0,-(sp)
        move.w  d7,-(sp)
        move.w  #64,-(sp)                       ; Fwrite
        trap    #1
        lea     12(sp),sp
        move.w  d7,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
        clr.w   -(sp)
        pea     name_done
        move.w  #60,-(sp)
        trap    #1
        addq.l  #8,sp
        move.w  d0,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
.done
        move.l  savssp,-(sp)
        move.w  #32,-(sp)
        trap    #1
        addq.l  #6,sp
        Pterm0

; One span from the script at a5 into the arena: addr.l len.w bytes [pad].
place
        move.l  (a5)+,d0
        moveq   #0,d1
        move.w  (a5)+,d1
        lea     arena,a0
        adda.l  d0,a0
        suba.l  #ARENA_BASE,a0
        move.l  d1,d2
        bra.s   .next
.byte
        move.b  (a5)+,(a0)+
.next
        subq.l  #1,d2
        bpl.s   .byte
        btst    #0,d1
        beq.s   .out
        addq.l  #1,a5
.out
        rts

; The OPL status the driver reads: the next answer of the current command.
status_answer
        tst.w   status_left
        beq.s   .none
        move.l  a0,-(sp)
        move.l  status_next,a0
        moveq   #0,d0
        move.b  (a0)+,d0
        move.l  a0,status_next
        move.l  (sp)+,a0
        subq.w  #1,status_left
        rts
.none
        moveq   #-1,d0
        rts

; d0.l = sum over the compared bytes of byte * (offset + 1): the driver's
; variables without its pointers (whose byte order is the Falcon's) and the
; countdown word, and the OPL state bytes.
checksum
        movem.l d1-d4/a0-a1,-(sp)
        moveq   #0,d0
        lea     ranges,a1
.range
        move.l  (a1)+,d1                        ; first flat address
        beq.s   .out
        move.l  (a1)+,d2                        ; one past the last
.byte
        lea     music_mem,a0
        move.l  d1,d3
        sub.l   #MUS_BASE,d3
        moveq   #0,d4
        move.b  0(a0,d3.l),d4
        addq.l  #1,d3
        mulu.l  d3,d4
        add.l   d4,d0
        addq.l  #1,d1
        cmp.l   d2,d1
        blo.s   .byte
        bra.s   .range
.out
        movem.l (sp)+,d1-d4/a0-a1
        rts

; The game-side loader the driver's game calls use; the harness never calls
; them (it places songs itself).
snd_bank_load
        moveq   #-1,d0
        rts

; read_file: a0 = name, a1 = buffer, d1 = size. Out: d0 = bytes or negative.
read_file
        movem.l d1-d2/a0-a1,-(sp)
        clr.w   -(sp)
        move.l  a0,-(sp)
        move.w  #61,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi.s   .out
        move.w  d0,d2
        move.l  a1,-(sp)
        move.l  d1,-(sp)
        move.w  d2,-(sp)
        move.w  #63,-(sp)
        trap    #1
        lea     12(sp),sp
        move.l  d0,-(sp)
        move.w  d2,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
        move.l  (sp)+,d0
.out
        movem.l (sp)+,d1-d2/a0-a1
        rts

        data
        even
; The compared bytes, as flat [first, end) pairs (tools/check-falcon-music.py
; has the same list).
ranges
        dc.l    $2C49C,$2C4A2                   ; flags, playing, paused, command
        dc.l    $2C4A4,$2C4E8                   ; notes, links, patches, loaded, device
        dc.l    $2C568,$2C5D3                   ; offsets .. effect ticks
        dc.l    $2D10D,$2D11F                   ; OPL level and B0 shadow
        dc.l    0
name_tables
        dc.b    "MUSTAB.BIN",0
name_script
        dc.b    "MUSIC.SCR",0
name_out
        dc.b    "MUSOUT.BIN",0
name_done
        dc.b    "MUSDONE.TXT",0
        even

        bss
        even
snd_cfg
        ds.b    10
        even
menu_settings
        ds.b    4
mission_music_names
        ds.b    48
savssp
        ds.l    1
status_next
        ds.l    1
status_left
        ds.w    1
tables
        ds.b    MUS_BYTES
        even
        ds.b    4096
main_stack
        ds.l    1
script
        ds.b    SCRIPT_BYTES
out
        ds.b    OUT_BYTES
arena
        ds.b    ARENA_BYTES

        end
