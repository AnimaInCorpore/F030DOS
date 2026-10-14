; Route: analysis/functions/falcon-attract.md#original-data-loader.
;
; The original's own tables, from the player's COMANCHE.EXE at startup.
;
; The program used to carry these as build/original_test.s, generated from
; the local install by tools/prepare-original-test.py: the Q31 sine, the KF4b
; menu font, the menu/name/debrief texts, the roster and settings defaults,
; the view, bearing and sprite-ramp tables. Every one of them is data of the
; 1990 COMANCHE.EXE at a recorded flat address, so the port now reads them
; from the copy of the game it already needs for its other files, and no byte
; of the original is part of the program. The same generator still writes
; build/original_test.s as host reference; after this routine the storage in
; build/port_tables.s holds exactly those bytes, which is how it is checked.
;
; The shipped COMANCHE.EXE is packed with LZEXE 0.91. The tables are read out
; of the unpacked load image, where flat address F is image offset 0x1700 + F
; (tools/re/carve-flat.py: the extender's code and data selectors both have
; base 0x1700). Only the image is needed, not a rebuilt MZ header or its
; relocations: tools/prepare-original-test.py reads the same unrelocated image
; through re/unpacked/comanche-flat32.bin.

        include "inc/comanche.s"

        global  orig_exe_load, orig_exe_status

        xref    resource_buffer
        xref    sine_q31, sin_table
        xref    menu_font_ok, menu_font_width, menu_font_start, menu_font_glyphs
        xref    menu_text_ok, menu_bar_text, menu_group_text, menu_screen_text
        xref    menu_lock_text, menu_about_text, menu_saved_text
        xref    menu_repaired_text, menu_reloaded_text, menu_stats_text
        xref    name_head_text, name_tail_text, name_plain_keys, name_shift_keys
        xref    name_prompt_text, roster_defaults, menu_file_defaults
        xref    debrief_text, menu_pilot_header
        xref    view_angle_offsets, object_octant_table
        xref    object_bearing_correction
        xref    sprite_ramp_offsets, sprite_ramp_pool
        xref    zove_frames, coma_frames, pan_wobble, attract_gamma
        xref    resource_gamma, snd_rate_tab

; The packed file: the 1990 COMANCHE.EXE as installed from the three disks
; (docs/ASSET-INVENTORY.md), identified by its size and a rotate-and-add
; checksum over every byte, both measured on that file.
ORIG_EXE_BYTES  = 61154
ORIG_EXE_SUM    = $EFA67E1F
; The flat base inside the unpacked load image, and how much of the image the
; tables reach: the Q31 sine at 00032120 ends at flat 00032B20, the last byte
; any table here needs.
ORIG_FLAT_BASE  = $1700
ORIG_IMAGE_NEED = ORIG_FLAT_BASE+$32B20
; Where the two live inside resource_buffer while this runs. The buffer is
; free at startup; nothing else reads it before main's first resource load.
ORIG_IMAGE_AT   = 65536

; The KF4b font block (emit_menu_font): "KF4b", widths at +8, 128 LE word
; offsets relative to the block at +0x88, columns of four bytes each.
ORIG_FONT       = $27276
ORIG_FONT_COLS  = 619

KIND_BYTES      = 0
KIND_LE32       = 1

        text

; Out: orig_exe_status 0 when every table is filled, -1 when COMANCHE.EXE is
; missing, is not the 1990 file, or does not unpack far enough.
;
; DOS: no counterpart - the original has these tables in its own image.
; Record: analysis/functions/falcon-attract.md#original-data-loader
; Port: reads them from the player's COMANCHE.EXE instead of the program.
; Preserved: every byte tools/prepare-original-test.py emitted for these
;   labels, including its font repacking and sin_table's q31[2i] >> 23.
; Kind: N/A - platform replacement (Target artefact: data provisioning).
; Status: ported; checked by tools/check-orig-exe-load.py against
;   build/original_test.s from a Hatari memory dump.
orig_exe_load
        movem.l d0-d7/a0-a6,-(sp)
        move.w  #-1,orig_exe_status

        ; Read one byte more than the file should have, so a longer file is
        ; caught by the length compare.
        move.w  #0,-(sp)                        ; read only
        pea     orig_exe_name
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .done
        move.w  d0,d3
        pea     resource_buffer
        move.l  #ORIG_EXE_BYTES+1,-(sp)
        move.w  d3,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d2
        move.w  d3,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp
        cmpi.l  #ORIG_EXE_BYTES,d2
        bne     .done

        lea     resource_buffer,a0
        move.l  #ORIG_EXE_BYTES-1,d1
        moveq   #0,d0
        moveq   #0,d2
.sum
        rol.l   #5,d0
        move.b  (a0)+,d2
        add.l   d2,d0
        subq.l  #1,d1
        bpl     .sum
        cmpi.l  #ORIG_EXE_SUM,d0
        bne     .done

        bsr     orig_exe_unpack
        tst.l   d0
        bne     .done

        ; a5 = flat address 0 inside the unpacked image.
        lea     resource_buffer+ORIG_IMAGE_AT+ORIG_FLAT_BASE,a5
        lea     orig_exe_copies,a6
.copy
        move.l  (a6)+,d0                        ; flat address
        bmi     .copied
        move.l  (a6)+,a1                        ; destination
        move.w  (a6)+,d1                        ; count
        move.w  (a6)+,d2                        ; kind
        lea     (a5,d0.l),a0
        subq.w  #1,d1
        tst.w   d2
        bne     .le32
.byte
        move.b  (a0)+,(a1)+
        dbra    d1,.byte
        bra     .copy
.le32
        move.l  (a0)+,d0                        ; the 68030 reads it unaligned
        ror.w   #8,d0
        swap    d0
        ror.w   #8,d0
        move.l  d0,(a1)+
        dbra    d1,.le32
        bra     .copy
.copied

        bsr     orig_exe_font
        tst.l   d0
        bne     .done
        move.w  #1,menu_font_ok
        move.w  #1,menu_text_ok

        ; sin_table: the renderer's 8.8 view sine, every second entry of the
        ; DOS Q31 table shifted right 23 (emit_tables), 320 words.
        lea     sine_q31,a0
        lea     sin_table,a1
        move.w  #320-1,d1
.sin
        move.l  (a0),d0
        addq.l  #8,a0
        asr.l   #8,d0
        asr.l   #8,d0
        asr.l   #7,d0
        move.w  d0,(a1)+
        dbra    d1,.sin

        clr.w   orig_exe_status
.done
        movem.l (sp)+,d0-d7/a0-a6
        rts

; LZEXE 0.91 decompression of the load image, stopping once ORIG_IMAGE_NEED
; bytes are out. Out: d0 = 0, or -1 when the stream ends first.
;
; The format, as unlzexe and the lzexe crate's do_decompress read it: the
; packer's eight-word block at CS:0 holds the compressed program size in
; paragraphs at +8, and the stream starts that many paragraphs below CS.
; Control bits come LSB first from little-endian 16-bit words, interleaved
; with literal and offset bytes from the same position:
;   1           literal byte
;   0 0 b b     match of 2..5 bytes, offset = byte | $FF00
;   0 1         match, lo/hi bytes: offset = lo | (hi & $F8) << 5 | $E000,
;               length (hi & 7) + 2; length 2 means a length byte follows:
;               0 ends the stream, 1 is a segment mark, n is n + 1 bytes.
; Offsets are negative 16-bit distances back into the output.
;
; DOS: no counterpart - DOS runs the LZEXE stub; this is its data format.
; Record: analysis/functions/falcon-attract.md#original-data-loader
; Kind: N/A - platform replacement.
orig_exe_unpack
        lea     resource_buffer,a0
        moveq   #0,d0
        move.w  8(a0),d0                        ; e_cparhdr, little-endian
        ror.w   #8,d0
        moveq   #0,d1
        move.w  $16(a0),d1                      ; e_cs
        ror.w   #8,d1
        move.l  d0,d2
        add.l   d1,d2
        lsl.l   #4,d2                           ; CS:0, the LZEXE block
        moveq   #0,d3
        move.w  8(a0,d2.l),d3                   ; compressed size, paragraphs
        ror.w   #8,d3
        add.l   d1,d0
        sub.l   d3,d0
        lsl.l   #4,d0                           ; (hdr + cs - size) << 4
        adda.l  d0,a0                           ; a0 = the stream

        lea     resource_buffer+ORIG_IMAGE_AT,a1
        lea     ORIG_IMAGE_NEED(a1),a2
        bsr     .reload
.next
        cmpa.l  a2,a1
        bhs     .enough
        bsr     .bit
        beq     .match
        move.b  (a0)+,(a1)+
        bra     .next
.match
        bsr     .bit
        bne     .long
        bsr     .bit
        move.w  d0,d1
        add.w   d1,d1
        bsr     .bit
        or.w    d0,d1
        addq.w  #2,d1                           ; 2..5
        moveq   #0,d2
        move.b  (a0)+,d2
        ori.w   #$FF00,d2
        bra     .copy
.long
        moveq   #0,d2
        move.b  (a0)+,d2                        ; lo
        moveq   #0,d3
        move.b  (a0)+,d3                        ; hi
        move.w  d3,d4
        andi.w  #$F8,d4
        lsl.w   #5,d4
        or.w    d4,d2
        ori.w   #$E000,d2
        andi.w  #7,d3
        addq.w  #2,d3
        move.w  d3,d1
        cmpi.w  #2,d1
        bne     .copy
        moveq   #0,d1
        move.b  (a0)+,d1
        beq     .ended                          ; 0: end of stream
        cmpi.w  #1,d1
        beq     .next                           ; 1: segment mark
        addq.w  #1,d1
.copy
        ext.l   d2
        lea     (a1,d2.l),a3
        subq.w  #1,d1
.run
        move.b  (a3)+,(a1)+
        dbra    d1,.run
        bra     .next
.enough
        moveq   #0,d0
        rts
.ended
        moveq   #-1,d0
        rts

; One control bit into d0 (and the Z flag); d6 holds the word, d7 the count.
.bit
        moveq   #0,d0
        lsr.w   #1,d6
        addx.w  d0,d0
        subq.w  #1,d7
        bne     .bit_done
        move.w  d0,-(sp)
        bsr     .reload
        move.w  (sp)+,d0
.bit_done
        tst.w   d0
        rts
.reload
        move.b  1(a0),d6
        lsl.w   #8,d6
        move.b  (a0),d6
        addq.l  #2,a0
        moveq   #16,d7
        rts

; Repack the KF4b font the way emit_menu_font does: menu_font_width is the
; block's width table, and the glyphs with a width are copied one after the
; other into menu_font_glyphs, menu_font_start holding each one's byte offset
; there (zero for an empty glyph). In: a5 = flat 0. Out: d0 = 0 or -1.
;
; DOS: the font block 00027276 that the text engine 00027034 draws from.
; Record: analysis/functions/falcon-attract.md#original-data-loader
; Kind: N/A - platform replacement.
orig_exe_font
        lea     ORIG_FONT(a5),a0                ; a5 is free from here on
        cmpi.l  #'KF4b',(a0)
        bne     .bad
        lea     8(a0),a1                        ; widths
        lea     $88(a0),a2                      ; LE word offsets
        lea     menu_font_width,a3
        lea     menu_font_start,a4
        lea     menu_font_glyphs,a6
        moveq   #0,d5                           ; columns so far
        moveq   #0,d4                           ; character
.char
        moveq   #0,d1
        move.b  (a1)+,d1
        move.b  d1,(a3)+
        moveq   #0,d2
        move.w  (a2)+,d2
        ror.w   #8,d2
        tst.w   d1
        bne     .glyph
        clr.l   (a4)+
        bra     .next
.glyph
        move.l  d5,d0
        lsl.l   #2,d0
        move.l  d0,(a4)+
        add.w   d1,d5
        cmpi.w  #ORIG_FONT_COLS,d5
        bhi     .bad
        lea     (a0,d2.l),a5
        subq.w  #1,d1
.column
        move.l  (a5)+,d0
        ror.w   #8,d0
        swap    d0
        ror.w   #8,d0
        move.l  d0,(a6)+
        dbra    d1,.column
.next
        addq.w  #1,d4
        cmpi.w  #128,d4
        blo     .char
        cmpi.w  #ORIG_FONT_COLS,d5
        bne     .bad
        moveq   #0,d0
        rts
.bad
        moveq   #-1,d0
        rts

        data
        even

; flat address, destination, count, kind. The addresses and lengths are
; tools/prepare-original-test.py's (emit_sine_q31, emit_menu_strings,
; emit_tables), where each one's DOS reader is recorded; the lengths of the
; 0xFF-terminated texts are the 1990 image's.
orig_exe_copies
        dc.l    $32120,sine_q31
        dc.w    640,KIND_LE32
        dc.l    $265C0,menu_bar_text
        dc.w    55,KIND_BYTES
        dc.l    $26607,menu_group_text
        dc.w    $267F2-$26607,KIND_BYTES
        dc.l    $29B2C,menu_screen_text
        dc.w    $3C4,KIND_BYTES
        dc.l    $269D5,menu_lock_text
        dc.w    40,KIND_BYTES
        dc.l    $2691C,menu_about_text
        dc.w    160,KIND_BYTES
        dc.l    $269BC,menu_saved_text
        dc.w    25,KIND_BYTES
        dc.l    $26A6C,menu_repaired_text
        dc.w    37,KIND_BYTES
        dc.l    $26A47,menu_reloaded_text
        dc.w    37,KIND_BYTES
        dc.l    $28AB5,menu_stats_text
        dc.w    130,KIND_BYTES
        dc.l    $27FC0,name_head_text
        dc.w    9,KIND_BYTES
        dc.l    $27FC9,name_tail_text
        dc.w    12,KIND_BYTES
        dc.l    $19E9,name_plain_keys
        dc.w    128,KIND_BYTES
        dc.l    $1969,name_shift_keys
        dc.w    128,KIND_BYTES
        dc.l    $27FD5,name_prompt_text
        dc.w    54,KIND_BYTES
        dc.l    $29582,roster_defaults
        dc.w    1450,KIND_BYTES
        dc.l    $25DBC,menu_file_defaults
        dc.w    35,KIND_BYTES
        dc.l    $284B1,debrief_text
        dc.w    584,KIND_BYTES
        dc.l    $29570,menu_pilot_header
        dc.w    $12,KIND_BYTES
        dc.l    $19D94,view_angle_offsets
        dc.w    9,KIND_LE32
        dc.l    $22385,object_octant_table
        dc.w    8,KIND_LE32
        dc.l    $223A5,object_bearing_correction
        dc.w    2048,KIND_BYTES
        dc.l    $1D7EC,sprite_ramp_offsets
        dc.w    128,KIND_LE32
        dc.l    $1DBEC,sprite_ramp_pool
        dc.w    8256+512,KIND_BYTES
        ; Tables the sources used to carry as dc.b/dc.l, cited where they are
        ; declared: src/attract.s, src/resources.s, src/sound.s.
        dc.l    $28E75,zove_frames
        dc.w    6,KIND_BYTES
        dc.l    $59C8,coma_frames
        dc.w    36,KIND_BYTES
        dc.l    $5985,pan_wobble
        dc.w    64,KIND_BYTES
        dc.l    $2B7D0,attract_gamma
        dc.w    64,KIND_BYTES
        dc.l    $2B7D0,resource_gamma
        dc.w    64,KIND_BYTES
        dc.l    $4998,snd_rate_tab
        dc.w    18,KIND_LE32
        dc.l    -1

orig_exe_name
        dc.b    "COMANCHE.EXE",0
        even

        bss
        even
orig_exe_status
        ds.w    1
