; Route: analysis/functions/falcon-attract.md#attract-route (startup only; menu handoff dormant).
; Record: analysis/functions/falcon-attract.md#attract-route
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; The menu and briefing text engine, ported from 00027034.
;
; The original draws every line of menu, briefing and options text through one
; byte-code interpreter over NUL-terminated strings. It is the most reused
; drawing routine in the image after the sprite blitter - twenty call sites -
; and nothing in the menu layer can be ported before it, so it comes first.
;
; The byte code, all of it:
;
;   $00, $FF   end of string
;   $FC        no-op; the strings are padded with runs of it
;   $FD        advance the pen six pixels (00027185: one byte column of the
;              Mode X page, which is four pixels, then two single-pixel steps)
;   $FE        record a hotspot: the pen position and the caller's id, into
;              8-byte records at 00026550 with the count at 00026590
;   $7C '|'    the next byte selects a colour: r g b p y o, anything else
;              being the default white
;   $01-$0A    the same colours by number - r p w b o r p b o r
;   anything   a glyph, if the font gives it a width; the colour codes are
;              also indexed into the width table, where they read zero, which
;              is how one dispatch handles both
;
; A glyph is `width` columns of four bytes. Each column is a 32-bit mask read
; from bit 0 upward, two bits per row for ten rows: the low bit of the pair
; paints the ink colour and the high bit the shadow. That is where the text's
; one-pixel drop shadow comes from - it is in the font, not in the drawing.
;
; Two deliberate deviations from the original, both platform:
;
; The colours are the exact six-bit triples 0002AA85-0002ABCC asks for, not
; the nearest entry of the installed palette. The original quantises because
; it has one VGA DAC and no choice; the Falcon composes RGB565, so it can have
; the colour the constants name. Over the flight palette the nearest match to
; white is a muddy grey the menu was never meant to be.
;
; The shadow is black. The original writes palette index 0, which in every
; palette this port loads is the reserved sentinel - bright green in the
; C1.DTA palette the flight runs on. A drop shadow drawn in sentinel green is
; not what the original looked like on its own data; black is.

        include "inc/comanche.s"
        xref    snd_apply_sound
        xref    flt_mission_end, exit_requested

        global  menu_text_draw, menu_text_width, menu_ink, menu_default_ink
        global  menu_ink_carry
        global  menu_settings
        global  menu_hotspot_reset, menu_hotspot_count
        global  menu_hotspot_x, menu_hotspot_y, menu_hotspot_id
        global  menu_bar_draw, menu_open, menu_nav, menu_confirm, menu_init
        global  menu_box, menu_fill, menu_message
        xref    menu_about_text, menu_saved_text, menu_file_defaults
        xref    menu_repaired_text, menu_reloaded_text
        xref    mission_wounded, mission_wounded_max, flt_death_timer, player_death_cue
        xref    flt_maxspd, mission_damage, flt_fuel, mission_fuel, weapon_ammo
        xref    mission_loadout, mission_chaff, mission_flare, console_redraw

MENU_HOTSPOTS   = 32
MENU_FONT_ROWS  = 10
MENU_TAB        = 6                             ; the $FD advance
MENU_COLUMNS    = 5                             ; Game Detail Control Options, and the Cheat column the KYLE chord shows
MENU_ROW_H      = 11                            ; 00026F41's multiplier
MENU_SEPARATORS = 4
MENU_TOGGLES    = 7
MENU_RADIOS     = 13
MENU_RADIO_SLOTS = 4

        text

; Draw one marked-up string.
;
; In:  a0 = string, a1 = destination surface, d0 = X, d1 = Y (top row),
;      d2 = the id recorded with any hotspot the string marks
; Out: d0 = the pen X after the last glyph
; DOS: flat 00027034-00027276, markup text interpreter.
; DOS symbol: sub_00027034
; Port: interprets authored menu/briefing strings into Falcon RGB565 glyphs.
; Preserved: control bytes, colour selectors, advances, hotspots, and order.
; Kind: translated.
; Status: ported; true-colour/shadow handling is the documented platform delta.
menu_text_draw
        movem.l d1-d7/a0-a6,-(sp)
        tst.w   menu_font_ok
        beq     .out
        move.w  d0,menu_pen_x
        move.w  d1,menu_pen_y
        move.w  d2,menu_hot_id
        ; The original keeps the colour in ebx (bh), which a caller's push/pop
        ; of eax does not restore, so a screen that draws line after line - the
        ; score screen at 00028A78 - carries one line's colour into the next.
        ; The list menus set it per line; they leave menu_ink_carry clear.
        tst.w   menu_ink_carry
        bne.s   .next
        move.w  menu_default_ink,menu_ink
.next
        moveq   #0,d2
        move.b  (a0)+,d2
        beq     .out                            ; $00 ends it
        cmpi.b  #$FF,d2
        beq     .out
        cmpi.b  #$FC,d2
        beq     .next                           ; padding
        cmpi.b  #$FE,d2
        beq     .hotspot
        cmpi.b  #$FD,d2
        beq     .tab
        cmpi.b  #$7C,d2
        beq     .named
        cmpi.b  #10,d2
        bhi     .glyph
        tst.b   d2
        beq     .next
        ; $01-$0A index the same colours by number.
        add.w   d2,d2
        lea     menu_numbered-2,a2
        move.w  0(a2,d2.w),menu_ink
        bra     .next
.tab
        addi.w  #MENU_TAB,menu_pen_x
        bra     .next
.hotspot
        bsr     menu_hotspot_add
        bra     .next
.named
        moveq   #0,d2
        move.b  (a0)+,d2
        beq     .out
        move.w  menu_default_ink,menu_ink        ; the default, then the letter
        cmpi.b  #'r',d2
        beq     .c_red
        cmpi.b  #'g',d2
        beq     .c_green
        cmpi.b  #'b',d2
        beq     .c_blue
        cmpi.b  #'p',d2
        beq     .c_magenta
        cmpi.b  #'y',d2
        beq     .c_amber
        cmpi.b  #'o',d2
        beq     .c_orange
        bra     .next
.c_red
        move.w  #COL_MENU_RED,menu_ink
        bra     .next
.c_green
        move.w  #COL_MENU_GREEN,menu_ink
        bra     .next
.c_blue
        move.w  #COL_MENU_BLUE,menu_ink
        bra     .next
.c_magenta
        move.w  #COL_MENU_MAGENTA,menu_ink
        bra     .next
.c_amber
        move.w  #COL_MENU_AMBER,menu_ink
        bra     .next
.c_orange
        move.w  #COL_MENU_ORANGE,menu_ink
        bra     .next

.glyph
        cmpi.w  #128,d2
        bcc     .next                           ; outside the font's range
        lea     menu_font_width,a2
        moveq   #0,d3
        move.b  0(a2,d2.w),d3                   ; width
        beq     .next                           ; the colour codes land here
        lea     menu_font_start,a2
        lsl.l   #2,d2
        move.l  0(a2,d2.l),d4
        lea     menu_font_glyphs,a2
        adda.l  d4,a2                           ; this glyph's columns

        ; Destination of the glyph's first column.
        move.l  a1,a3
        moveq   #0,d4
        move.w  menu_pen_y,d4
        mulu.w  #SCREEN_STRIDE,d4
        adda.l  d4,a3
        moveq   #0,d4
        move.w  menu_pen_x,d4
        add.w   d4,d4
        adda.w  d4,a3
        move.w  menu_ink,d6
.column
        move.w  menu_pen_x,d4
        bmi     .column_step                    ; clipped off the left
        cmpi.w  #SCREEN_WIDTH,d4
        bcc     .column_step                    ; and off the right
        move.l  (a2),d5                         ; the column mask
        move.l  a3,a4
        move.w  #MENU_FONT_ROWS-1,d7
.row
        lsr.l   #1,d5
        bcc     .no_ink
        move.w  d6,(a4)
.no_ink
        lsr.l   #1,d5
        bcc     .no_shadow
        move.w  #COL_MENU_SHADOW,(a4)
.no_shadow
        adda.w  #SCREEN_STRIDE,a4
        dbra    d7,.row
.column_step
        addq.l  #4,a2
        addq.l  #2,a3
        addq.w  #1,menu_pen_x
        subq.w  #1,d3
        bne     .column
        bra     .next
.out
        move.w  menu_pen_x,d0
        movem.l (sp)+,d1-d7/a0-a6
        rts

; The pen width of a string, without drawing it. Same walk, no surface.
;
; The original's measurer is not a per-string helper: 000268C5 walks a table
; of block pointers at 000265A0, skips each string's first byte, sums glyph
; widths to 0x00 or 0xFF, keeps the widest line in ebp and the line count in
; cl, and finally stores (widest + 0x12) >> 2 as the box's byte width at
; 000265FF and the line count at 000265F7. Those two stores are the layout
; contract this routine will have to feed when the menu becomes a supported
; path.
;
; In:  a0 = string
; Out: d0 = width in pixels
; DOS: flat 000268C5-00026915, menu block measurement over the width table
; at 0002727E.
; DOS symbol: loc_000268C5
; Port: measures one authored line without drawing it.
; Preserved: the two terminators and an unconditional table add per byte.
; Kind: translated.
; Status: partial; the block measurement at 000268C5 and its two stores at
; 000265FF/000265F7 are not ported - this measures one line, not a block.
menu_text_width
        movem.l d1-d3/a0-a2,-(sp)
        moveq   #0,d0
        tst.w   menu_font_ok
        beq     .out
.next
        moveq   #0,d2
        move.b  (a0)+,d2
        beq     .out
        cmpi.b  #$FF,d2
        beq     .out
        ; 000268E4 adds the table entry for EVERY byte between the
        ; terminators. It does not discount the interpreter's control bytes,
        ; and 0002727E holds real widths for them - 0x7C is 2, 0xFD is 4, and
        ; 126 of the entries above 0x7F are non-zero. Skipping them was this
        ; port's rule, not the original's.
        lea     menu_font_width,a2
        moveq   #0,d3
        move.b  0(a2,d2.w),d3
        add.w   d3,d0
        bra     .next
.out
        movem.l (sp)+,d1-d3/a0-a2
        rts

; ---------------------------------------------------------------------------
; Hotspots: what the original records at 00026550 so the pointer and the
; cursor keys can find the menu items a string laid out. The DOS record is the
; pen's byte offset with the page base and pan subtracted, which is a screen
; position expressed in its own addressing; here it is kept as X and Y, and
; the caller's id rides along unchanged.
; ---------------------------------------------------------------------------

; DOS: flat 00027034 hotspot-list initialization.
; DOS symbol: sub_00027034
; Port: clears the Falcon hotspot count before an authored menu redraw.
; Preserved: per-redraw ownership and item order.
; Kind: translated.
; Status: ported; covered by menu navigation.
menu_hotspot_reset
        clr.w   menu_hotspot_count
        rts

; DOS: flat 00027034-00027276 hotspot recording side effect.
; DOS symbol: sub_00027034
; Port: stores authored pen coordinates and selector IDs in Falcon arrays.
; Preserved: insertion order, coordinates, and packed menu identity.
; Kind: translated.
; Status: ported; covered by menu navigation.
menu_hotspot_add
        movem.l d0/a0,-(sp)
        move.w  menu_hotspot_count,d0
        cmpi.w  #MENU_HOTSPOTS,d0
        bcc     .full
        add.w   d0,d0
        lea     menu_hotspot_x,a0
        move.w  menu_pen_x,0(a0,d0.w)
        lea     menu_hotspot_y,a0
        move.w  menu_pen_y,0(a0,d0.w)
        lea     menu_hotspot_id,a0
        move.w  menu_hot_id,0(a0,d0.w)
        addq.w  #1,menu_hotspot_count
.full
        movem.l (sp)+,d0/a0
        rts

; ---------------------------------------------------------------------------
; The in-flight options bar, 00025DEF's own string at 000265C0 drawn at its
; own pen: the DOS origin is [14C4] + page + pan + 0xF7, and 0xF7 is three
; rows of the 82-byte Mode X pitch plus one byte column, so the pen is X=4,
; Y=3 - the bar sits across the top of the flight view.
;
; What this does not carry yet, because it is the next slice and not this
; one: the four drop-down panels behind the bar's hotspots, their keyboard
; and pointer selection, and the actions under them. The hotspots the bar
; records are exactly the data that selection will read.
;
; In: a1 = destination surface
; DOS: flat 00025DEF, in-flight options-bar composition.
; DOS symbol: sub_00025DEF
; Port: draws the authored options bar over the RGB565 frame when open.
; Preserved: selection, text, highlight, panel order, and closed-state no-op.
; Kind: translated.
; Status: ported; live menu exit remains incomplete.
menu_bar_draw
        movem.l d0-d4/a0-a2,-(sp)
        tst.w   menu_open
        beq     .out
        tst.w   menu_text_ok
        beq     .out
        tst.w   menu_ready
        bne     .ready
        bsr     menu_init
.ready
        ; The bar's own bevelled box first: 0002628E with bl=0, bh=0x50,
        ; dl=0, dh=0x0E - the full 320 pixels, fourteen rows.
        move.l  a1,a0
        moveq   #0,d0
        moveq   #0,d1
        move.w  #SCREEN_WIDTH,d2
        moveq   #14,d3
        bsr     menu_box

        bsr     menu_radio_marks
        bsr     menu_bar_highlight
        bsr     menu_hotspot_reset
        lea     menu_bar_text,a0
        moveq   #4,d0
        moveq   #3,d1
        moveq   #0,d2
        bsr     menu_text_draw
        tst.w   menu_message
        bne.s   .message
        bsr     menu_panel_draw
        bra     .out
.message
        ; 00026DB2-00026DF3 / 00026E25-00026E7C: 00016E41 took the panel away,
        ; 000264B1 drew the bar again, and the box goes over the view.
        move.l  a1,a0
        cmpi.w  #3,menu_message
        bhs     .cheat_box
        cmpi.w  #2,menu_message
        beq.s   .saved
        move.w  #$0F*4,d0                       ; bl=0x0F, bh=0x32, dl=0x1E, dh=0x5A
        move.w  #$1E,d1
        move.w  #$32*4,d2
        move.w  #$5A,d3
        bsr     menu_box
        lea     menu_about_text,a2
        move.w  #16*4+1,d0                      ; 0x812 = row 25, byte 16
        move.w  #25,d1
        bra.s   .lines
.cheat_box
        ; 00026E90's own box, the one the locked-mission message uses.
        move.w  #$0F*4,d0
        move.w  #$42,d1
        move.w  #$32*4,d2
        move.w  #$0F,d3
        bsr     menu_box
        lea     menu_repaired_text,a2
        cmpi.w  #4,menu_message
        bne.s   .cheat_text
        lea     menu_reloaded_text,a2
.cheat_text
        move.w  #15*4+1,d0
        move.w  #70,d1
        bra     .lines
.saved
        move.w  #$16*4,d0                       ; bl=0x16, bh=0x24, dl=0x42, dh=0x0F
        move.w  #$42,d1
        move.w  #$24*4,d2
        move.w  #$0F,d3
        bsr     menu_box
        lea     menu_saved_text,a2
        move.w  #22*4+1,d0                      ; 0x1682 = row 70, byte 22
        move.w  #70,d1
.lines
        ; 00026E68: one line a pass, twelve rows apart, to the 0xFF.
        move.w  d0,d4
        move.w  d1,d3
.line
        move.l  a2,a0
        move.w  d4,d0
        move.w  d3,d1
        moveq   #0,d2
        bsr     menu_text_draw
        addi.w  #12,d3
.step
        move.b  (a2)+,d0
        beq.s   .next_line
        cmpi.b  #$FF,d0
        bne.s   .step
        bra.s   .out
.next_line
        bra.s   .line
.out
        movem.l (sp)+,d0-d4/a0-a2
        rts

; The light-grey block behind the selected column's label. 000264BE: from the
; selected hotspot's byte column less one, two rows above the text, twelve
; rows tall, ending two byte columns short of the next hotspot.
;
; In: a1 = surface
; DOS: flat 000264BE, selected-column highlight fill.
; DOS symbol: inside sub_000264B1
; Port: fills the authored highlight rectangle in the Falcon surface.
; Preserved: selected column geometry and colour.
; Kind: translated.
; Status: ported; covered by menu_bar_draw.
menu_bar_highlight
        movem.l d0-d4/a0-a2,-(sp)
        move.w  menu_col,d0
        addq.w  #1,d0
        cmp.w   menu_hotspot_count,d0
        bhi     .out                            ; no successor: nothing to span
        move.w  menu_col,d0
        add.w   d0,d0
        lea     menu_hotspot_x,a2
        move.w  0(a2,d0.w),d1                   ; this hotspot
        move.w  2(a2,d0.w),d2                   ; the next
        andi.w  #$FFFC,d1                       ; the record keeps byte columns
        andi.w  #$FFFC,d2
        sub.w   d1,d2
        subq.w  #5,d2                           ; 3 left pixels, minus 2 bytes
        ble     .out
        subq.w  #3,d1
        bmi     .out
        move.l  a1,a0
        move.w  d1,d0
        moveq   #1,d1                           ; text row 3, less two
        move.w  d2,d3
        moveq   #12,d4
        move.w  #COL_MENU_GREY_L,d2
        bsr     menu_fill
.out
        movem.l (sp)+,d0-d4/a0-a2
        rts

; The open column's panel: box, the highlight under the selected row, and the
; group's strings. 00026F21, in its order.
;
; In: a1 = surface
; DOS: menu panel composition within 00025DEF.
; DOS symbol: sub_00025DEF
; Port: draws the authored panel, radio marks, and markup rows.
; Preserved: row count, panel geometry, selector order, and text source.
; Kind: translated.
; Status: ported; live action handlers remain incomplete.
menu_panel_draw
        movem.l d0-d7/a0-a6,-(sp)
        move.w  menu_col,d7
        cmp.w   menu_hotspot_count,d7
        bcc     .out
        move.w  d7,d0
        add.w   d0,d0
        lea     menu_hotspot_x,a2
        move.w  0(a2,d0.w),d6
        andi.w  #$FFFC,d6                       ; the hotspot's byte column
        lea     menu_width,a2
        move.w  0(a2,d0.w),d5                   ; panel width, pixels
        lea     menu_rows,a2
        move.w  0(a2,d0.w),d4                   ; rows

        ; The box: 00026F49 passes the width and rows*11+3 at row 15, from one
        ; byte column left of the label.
        move.l  a1,a0
        move.w  d6,d0
        subq.w  #4,d0
        moveq   #15,d1
        move.w  d5,d2
        move.w  d4,d3
        mulu.w  #MENU_ROW_H,d3
        addq.w  #3,d3
        bsr     menu_box

        ; The row highlight: twelve rows from row 16, stepping eleven, inset
        ; one pixel at the left and three at the right of the panel.
        move.l  a1,a0
        move.w  d6,d0
        subq.w  #3,d0
        move.w  menu_row,d1
        mulu.w  #MENU_ROW_H,d1
        addi.w  #16,d1
        move.w  d5,d3
        subq.w  #3,d3
        moveq   #12,d4
        move.w  #COL_MENU_GREY_L,d2
        bsr     menu_fill

        ; The strings, green by default, eleven rows apart from row 18.
        move.w  d7,d0
        add.w   d0,d0
        lea     menu_rows,a2
        move.w  0(a2,d0.w),d4                   ; menu_fill took the register
        move.w  d7,d0
        lsl.w   #2,d0
        lea     menu_group,a2
        move.l  0(a2,d0.w),a3
        moveq   #0,d3                           ; row
.line
        move.l  a3,a0
        move.w  d6,d0
        addq.w  #2,d0                           ; the inherited sub-column
        move.w  d3,d1
        mulu.w  #MENU_ROW_H,d1
        addi.w  #18,d1
        moveq   #0,d2
        move.w  #COL_MENU_GREEN,menu_default_ink
        bsr     menu_text_draw
        move.w  #COL_MENU_WHITE,menu_default_ink
        bsr     menu_next_string
        addq.w  #1,d3
        cmp.w   d4,d3
        blo     .line
.out
        movem.l (sp)+,d0-d7/a0-a6
        rts

; a3 -> the next string of a group, past its terminator.
; DOS: helper within 00027034 string-list traversal.
; DOS symbol: sub_00027034
; Port: advances to the next authored NUL/terminator-delimited menu string.
; Preserved: markup terminators and source order.
; Kind: translated.
; Status: ported; covered by menu panel rendering.
menu_next_string
        tst.b   (a3)+
        bne     menu_next_string
        rts

; ---------------------------------------------------------------------------
; The bevelled box, 0002628E, as the original draws it row by row:
;
;   row 0         mid grey ([0002A376]) over w-1 pixels; the last is not touched
;   rows 1..h-2   the interior, the pixels under it darkened (the original
;                 halves each palette entry and matches the result back into
;                 the palette through the table 0002AA18 builds at 0005CE20;
;                 RGB565 halves the channels and keeps the answer)
;   row h-1       dark grey ([0002A375]) across the width
;   rows h, h+1   black from pixel 1 to the end - the shadow
;   column 0      mid grey on rows 0..h-2
;   column w-2/-1 dark grey and black on rows 1..h-1
;
; In: a0 = surface, d0 = X, d1 = top row, d2 = width, d3 = height
; ---------------------------------------------------------------------------
; DOS: flat 0002628E-000264B0, bevelled menu box fill.
; DOS symbol: sub_0002628E
; Port: draws the authored border/interior in RGB565.
; Preserved: row order, dimensions, edges, shadow and resolved menu colours.
; Difference: the interior is darkened per RGB565 pixel, not through the
;   original's nearest-palette-entry table, so a darkened pixel can differ from
;   the original's by one palette step; the named colours are the exact triples
;   rather than the nearest palette entries (see the header).
; Kind: translated.
; Status: ported; checked against the original's debrief box.
menu_box
        movem.l d0-d7/a0-a2,-(sp)
        tst.w   d2
        ble     .out
        tst.w   d3
        ble     .out
        move.l  a0,a1
        move.w  d1,d4
        mulu.w  #SCREEN_STRIDE,d4
        adda.l  d4,a1
        move.w  d0,d4
        add.w   d4,d4
        adda.w  d4,a1                           ; a1 = pixel (0,0) of the box
        move.w  d2,d6
        subq.w  #1,d6                           ; width - 1, for the loops
        move.w  d3,d7                           ; height

        ; Row 0: width - 1 pixels of mid grey.
        move.l  a1,a2
        move.w  d6,d4
        subq.w  #1,d4
        bmi.s   .top_done
.top
        move.w  #COL_MENU_GREY_M,(a2)+
        dbra    d4,.top
.top_done

        ; Rows 1..h-2: the interior.
        move.w  d7,d5
        subq.w  #2,d5
        ble.s   .bottom
        lea     SCREEN_STRIDE(a1),a2
        subq.w  #1,d5
.irow
        move.l  a2,a0
        move.w  d6,d4
.ipx
        move.w  (a0),d1
        lsr.w   #1,d1
        andi.w  #$7BEF,d1                       ; halve each channel in place
        move.w  d1,(a0)+
        dbra    d4,.ipx
        lea     SCREEN_STRIDE(a2),a2
        dbra    d5,.irow

        ; Row h-1: dark grey across the whole width.
.bottom
        move.w  d7,d4
        subq.w  #1,d4
        mulu.w  #SCREEN_STRIDE,d4
        lea     0(a1,d4.l),a2
        move.w  d6,d4
.brow
        move.w  #COL_MENU_GREY_D,(a2)+
        dbra    d4,.brow
        move.w  #COL_MENU_GREY_D,(a2)           ; the last pixel too

        ; Rows h and h+1: black from pixel 1 on.
        move.w  d7,d4
        mulu.w  #SCREEN_STRIDE,d4
        lea     2(a1,d4.l),a2
        move.w  d6,d4
        subq.w  #1,d4
        bmi.s   .shadow2
.shadow1
        clr.w   (a2)+
        dbra    d4,.shadow1
.shadow2
        move.w  d7,d4
        addq.w  #1,d4
        mulu.w  #SCREEN_STRIDE,d4
        lea     2(a1,d4.l),a2
        move.w  d6,d4
        subq.w  #1,d4
        bmi.s   .left
.shadow3
        clr.w   (a2)+
        dbra    d4,.shadow3

        ; Column 0: mid grey on rows 0..h-2.
.left
        move.l  a1,a2
        move.w  d7,d4
        subq.w  #2,d4
        bmi.s   .right
.lcol
        move.w  #COL_MENU_GREY_M,(a2)
        lea     SCREEN_STRIDE(a2),a2
        dbra    d4,.lcol

        ; Columns w-2 and w-1: dark grey and black on rows 1..h-1.
.right
        move.w  d6,d4
        add.w   d4,d4
        lea     -2(a1,d4.w),a2                  ; pixel w-2, row 0
        lea     SCREEN_STRIDE(a2),a2
        move.w  d7,d4
        subq.w  #2,d4
        bmi.s   .out
.rcol
        move.w  #COL_MENU_GREY_D,(a2)
        clr.w   2(a2)
        lea     SCREEN_STRIDE(a2),a2
        dbra    d4,.rcol
.out
        movem.l (sp)+,d0-d7/a0-a2
        rts

; A flat rectangle. In: a0 = surface, d0 = X, d1 = Y, d2 = colour,
; d3 = width, d4 = height
; DOS: flat 0002628E, helper within menu box/panel composition.
; Port: fills a Falcon RGB565 rectangle with the selected authored colour.
; Preserved: clipping and rectangle extents; plane writes are platform-specific.
; Kind: adapted - platform surface port.
; Status: ported; covered by menu rendering.
menu_fill
        movem.l d0-d5/a0-a2,-(sp)
        tst.w   d3
        ble     .out
        tst.w   d4
        ble     .out
        move.l  a0,a1
        move.w  d1,d5
        mulu.w  #SCREEN_STRIDE,d5
        adda.l  d5,a1
        move.w  d0,d5
        add.w   d5,d5
        adda.w  d5,a1
        subq.w  #1,d4
.row
        move.l  a1,a2
        move.w  d3,d5
        subq.w  #1,d5
.px
        move.w  d2,(a2)+
        dbra    d5,.px
        adda.w  #SCREEN_STRIDE,a1
        dbra    d4,.row
.out
        movem.l (sp)+,d0-d5/a0-a2
        rts

; ---------------------------------------------------------------------------
; What 000268C5 does at load: walk each group to its 0xFF, count the strings
; into the row count and take the widest into the panel width. The bytes at
; 000265F7 that look like these counts are dead initialisers - see the map.
; ---------------------------------------------------------------------------
; DOS: flat 0002615C-00026D2C, menu setup/default selectors.
; DOS symbol: loc_0002615C
; Port: initializes authored menu strings, hotspots, radio groups, and colours.
; Preserved: shipped defaults, selector offsets, and markup data.
; Kind: translated.
; Status: partial; mission/menu action integration remains incomplete.
menu_init
        movem.l d0-d7/a0-a6,-(sp)
        move.w  #1,menu_ready
        move.w  #COL_MENU_WHITE,menu_default_ink
        lea     menu_group_text,a3
        moveq   #0,d7                           ; column
.group
        move.w  d7,d0
        lsl.w   #2,d0
        lea     menu_group,a2
        move.l  a3,0(a2,d0.w)
        moveq   #0,d5                           ; rows
        moveq   #0,d6                           ; widest
.string
        move.l  a3,a0
        bsr     menu_text_width
        cmp.w   d6,d0
        bls     .not_wider
        move.w  d0,d6
.not_wider
        addq.w  #1,d5
.scan
        move.b  (a3)+,d0
        beq     .string_done
        cmpi.b  #$FF,d0
        bne     .scan
        bra     .group_done
.string_done
        bra     .string
.group_done
        move.w  d7,d0
        add.w   d0,d0
        lea     menu_rows,a2
        move.w  d5,0(a2,d0.w)
        ; (widest + 0x12) >> 2 byte columns, which is the width in pixels
        ; rounded down to four - eighteen pixels of border around the text.
        addi.w  #$12,d6
        andi.w  #$FFFC,d6
        lea     menu_width,a2
        move.w  d6,0(a2,d0.w)
        addq.w  #1,d7
        cmpi.w  #MENU_COLUMNS,d7
        blo     .group

        bsr     menu_load_settings
        bsr     menu_radio_init
        bsr     menu_apply_options

        ; 00026211's reload, on the settings the file just supplied. The
        ; detail byte selects one of three depth schedules and nothing else in
        ; the port reads it, so without this the Detail menu writes a byte
        ; that changes nothing. A load failure leaves the generated MEDIUM
        ; tables in place and reports through dtl_status.
        bsr     dtl_apply_settings

        ; One text pass so the first frame's highlight has hotspots, exactly
        ; as 00025E75 draws the bar before entering the loop.
        bsr     menu_hotspot_reset
        lea     menu_bar_text,a0
        moveq   #4,d0
        moveq   #3,d1
        moveq   #0,d2
        move.l  work_screen,a1
        bsr     menu_text_draw
        movem.l (sp)+,d0-d7/a0-a6
        rts

; ---------------------------------------------------------------------------
; Navigation, 00026044-000260F9. Left and right step the column and reset the
; row; up and down step the row, remembering the direction so a separator can
; be stepped over again. The column wraps against the hotspot count less one,
; because the bar's trailing marker is the end position and not an item.
;
; In: d0 = 0 left, 1 right, 2 up, 3 down
; ---------------------------------------------------------------------------
; DOS: flat 0002615C menu keyboard navigation.
; DOS symbol: loc_0002615C
; Port: moves through the authored hotspot/group rows with Falcon event bits.
; Preserved: wrap/skip behavior and separator handling.
; Kind: translated.
; Status: partial; full DOS input event table is not yet ported.
menu_nav
        movem.l d0-d3/a0-a2,-(sp)
        tst.w   menu_ready
        beq     .out
        move.w  menu_hotspot_count,d3
        subq.w  #1,d3                           ; items, not positions
        ble     .out
        cmpi.w  #MENU_COLUMNS,d3
        bls     .cols_ok
        move.w  #MENU_COLUMNS,d3
.cols_ok
        tst.w   d0
        beq     .left
        cmpi.w  #1,d0
        beq     .right
        cmpi.w  #2,d0
        beq     .up
        bra     .down
.left
        clr.w   menu_row
        subq.w  #1,menu_col
        bpl     .out
        move.w  d3,menu_col
        subq.w  #1,menu_col
        bra     .out
.right
        clr.w   menu_row
        addq.w  #1,menu_col
        move.w  menu_col,d1
        cmp.w   d3,d1
        blo     .out
        clr.w   menu_col
        bra     .out
.up
        move.w  #-1,menu_dir
        subq.w  #1,menu_row
        bpl     .skip
        bsr     menu_row_count
        subq.w  #1,d1
        move.w  d1,menu_row
        bra     .skip
.down
        move.w  #1,menu_dir
        addq.w  #1,menu_row
        bsr     menu_row_count
        move.w  menu_row,d2
        cmp.w   d1,d2
        blo     .skip
        clr.w   menu_row
.skip
        bsr     menu_skip_separator
.out
        movem.l (sp)+,d0-d3/a0-a2
        rts

; ---------------------------------------------------------------------------
; Choosing the selected line, 00026AB6. The dispatcher is a flat chain of
; comparisons against the same packed (column << 4) | row the navigation uses.
;
; Seven of its cases are the boolean options, and all seven work the same
; startling way: they `xor al,6` the FIRST CHARACTER OF THE STRING - `'{' ^ 6`
; is `'}'` - and mirror the result into a settings byte. The brace in the text
; is the flag; drawing the line is what reads the setting. This port keeps
; that, because the alternative is a second source of truth that has to be
; pushed back into the string before every draw anyway.
;
; The offsets below are written as DOS addresses less the group base, so a
; change to where the blob starts cannot silently shift them - which is
; exactly what had gone wrong: the group begins at 00026607 with "About
; |yComanche", not at 00026618, because the eight runtime row counts at
; 000265F7 and eight widths at 000265FF sit in between. Starting seventeen
; bytes late cost the Game column its first line, and driving the original
; is what showed it.
;
; The radio groups below are the same idea one step out: they record which
; line of a group carries the mark, and menu_radio_marks puts it there before
; every redraw.
;
; What no case here does is act on the Game column - see the note in the body.
; DOS: flat 00026CC2/00026CE3/00026D2C/00026BD5 selector handlers.
; DOS symbol: loc_00026CC2
; Port: writes the selected authored radio/toggle setting.
; Preserved: selector identity and stored value range.
; Kind: translated.
; Status: partial; mission abort/exit actions remain unrecovered.
menu_confirm
        movem.l d0-d2/a0-a2,-(sp)
        tst.w   menu_ready
        beq     .out
        move.w  menu_col,d0
        lsl.w   #4,d0
        or.w    menu_row,d0                     ; the packed selector

        ; The Game column, 00026D8B-00026E8F: the five lines are the selectors 0-4.
        ;   0  About Comanche - the credits box over the flight view (not ported)
        ;   1  Return to Game - the bar closes, as Escape closes it
        ;   2  Save Menu Settings - writes COMANCHE.MNU and says so (not ported)
        ;   3  Abort Mission  - 0002873D, as Alt+A
        ;   4  Exit to DOS    - 00006B14, as Alt+Q
        ; (The earlier reading here, that 00026AB6 has no case for them, was a
        ; miscount: it numbered the four lines below the header.)
        cmpi.w  #1,d0
        beq     .game_return
        cmpi.w  #3,d0
        beq     .game_abort
        cmpi.w  #4,d0
        beq     .game_exit
        cmpi.w  #4,d0
        bls     .game_box
        cmpi.w  #$40,d0                         ; 00026B49: the Cheat column
        beq     .cheat_repair
        cmpi.w  #$41,d0                         ; 00026B88
        beq     .cheat_reload

        ; The radio groups first: 00026CC2, 00026CE3, 00026D2C and 00026BD5
        ; all just write an ASCII digit into a settings byte. Here the setting
        ; is the offset of the line that carries the mark, which is the same
        ; fact in the form the redraw wants.
        lea     menu_radios,a0
        moveq   #MENU_RADIOS-1,d1
.rprobe
        move.w  (a0)+,d2
        cmp.w   d0,d2
        beq     .radio
        addq.l  #4,a0
        dbra    d1,.rprobe
        bra     .toggles
.radio
        moveq   #0,d2
        move.w  (a0)+,d2                        ; slot = the group
        move.w  d2,-(sp)
        add.w   d2,d2
        lea     menu_setting,a1
        move.w  (a0),0(a1,d2.w)                 ; the chosen line's offset
        move.w  (sp)+,d2                        ; the group again
        ; 00026CC6/00026CD1/00026CDC (detail), 00026CE7/00026CFD/00026D1D (sound),
        ; 00026D30/00026D52/00026D74 (music) and 00026BDA.. (control) also write the
        ; line's digit into the settings byte [00025DD4 + group]; the line is the
        ; selector's row, counted from the first radio of its column (rows 0, 0, 4, 8).
        move.w  d0,d1
        andi.w  #$0f,d1
        cmpi.w  #2,d2
        blo.s   .row_is_digit
        move.w  d2,d0
        subq.w  #1,d0
        lsl.w   #2,d0
        sub.w   d0,d1
.row_is_digit
        addi.w  #'0',d1
        lea     menu_settings,a1
        move.b  d1,0(a1,d2.w)
        cmpi.w  #1,d2
        bne     .out
        jsr     snd_apply_sound                 ; 00026CEE-00026CF3, 00026D04-00026D13, 00026D24-00026D26
        bra     .out

.toggles
        lea     menu_toggles,a0
        moveq   #MENU_TOGGLES-1,d1
.probe
        move.w  (a0)+,d2
        cmp.w   d0,d2
        beq     .toggle
        addq.l  #2,a0
        dbra    d1,.probe
        bra     .out
.toggle
        moveq   #0,d2
        move.w  (a0),d2
        lea     menu_group_text,a1
        eori.b  #6,0(a1,d2.l)
        move.b  0(a1,d2.l),d0                   ; 00026AC6 and its six siblings:
        lea     menu_option_targets,a0          ; the flipped character is also
        lea     menu_settings+4,a1              ; stored into [00025DD8 + n]
        moveq   #MENU_OPTION_COUNT-1,d1
.setting
        cmp.w   (a0)+,d2
        beq.s   .setting_found
        addq.l  #1,a1
        dbra    d1,.setting
        bra     .out
.setting_found
        move.b  d0,(a1)
        bra     .out
.cheat_repair
        ; 00026B4D-00026B87: the hull back to its maximum, the wreck's countdown
        ; and cue cleared, the speed ceiling restored and every damage cell 0x0A.
        move.l  mission_wounded_max,mission_wounded     ; [00019E44] -> [00019E40]
        move.b  #$64,flt_death_timer
        clr.w   player_death_cue                ; [00019E49] is a byte: its pair is 0
        move.l  #$1800000,flt_maxspd
        lea     mission_damage,a0
        moveq   #8-1,d1
.cells
        move.b  #$0a,(a0)+
        dbra    d1,.cells
        move.w  #3,menu_message                 ; 00026B7D-00026B82: "All Damage Repaired"
        bra     .out
.cheat_reload
        ; 00026B8C-00026BD4: fuel and the six weapon stores back to the
        ; mission's own, the chaff and flares to 15 and 25, the console redrawn.
        move.l  mission_fuel,flt_fuel           ; [00019D5C] -> [00019D60]
        lea     mission_loadout,a0
        lea     weapon_ammo,a1
        moveq   #6-1,d1
.stores
        move.l  (a0)+,(a1)+
        dbra    d1,.stores
        move.w  #$0f,mission_chaff              ; [00019D8D]
        move.w  #$19,mission_flare              ; [00019D8E]
        move.b  #1,console_redraw               ; [00019D89]/[00019D8A] = 2
        move.w  #4,menu_message                 ; "Weapons and Fuel Reloaded"
        bra     .out
.game_box
        ; 00026E21 (0) and 00026D8B (2): a box over the bar, until a key.
        tst.w   d0
        bne.s   .game_save
        move.w  #1,menu_message                 ; About Comanche
        bra     .out
.game_save
        bsr     menu_save_settings              ; 00026D99
        move.w  #2,menu_message                 ; 00026DB2
        bra     .out
.game_return
        clr.w   menu_open                       ; 00026E1B jmp 0002615C
        bra     .out
.game_abort
        clr.w   menu_open
        move.w  #1,flt_mission_end              ; 00026E09 je 0002873D
        bra     .out
.game_exit
        clr.w   menu_open
        move.w  #1,exit_requested               ; 00026E11 je 00006B14
        bra     .out
.out
        movem.l (sp)+,d0-d2/a0-a2
        rts

; Put the radio marks where the settings say, which is what 00025EA5 does
; before every redraw: a space into every line of a group, then a backtick
; into the selected one. The font's backtick is the selected-radio glyph, so
; this is the whole of drawing a radio button.
; DOS: menu redraw radio-mark handlers around 00026CC2-00026D2C.
; DOS symbol: loc_00026CC2
; Port: places marks according to the authored settings bytes.
; Preserved: group membership, selected row, and redraw order.
; Kind: translated.
; Status: ported; covered by menu rendering.
menu_radio_marks
        movem.l d0-d2/a0-a2,-(sp)
        lea     menu_group_text,a1
        lea     menu_radios,a0
        moveq   #MENU_RADIOS-1,d1
.clear
        addq.l  #4,a0                           ; past selector and slot
        moveq   #0,d2
        move.w  (a0)+,d2
        move.b  #' ',0(a1,d2.l)
        dbra    d1,.clear
        lea     menu_setting,a2
        moveq   #MENU_RADIO_SLOTS-1,d1
.set
        moveq   #0,d2
        move.w  (a2)+,d2
        beq     .next                           ; a group with no mark yet
        move.b  #'`',0(a1,d2.l)
.next
        dbra    d1,.set
        movem.l (sp)+,d0-d2/a0-a2
        rts

; Mark the line each group is set to - 00025EB3-00025F7D, and it runs the
; opposite way round from what this used to do.
;
; The original holds four setting CHARACTERS at 00025DD4 (detail, sound,
; music, control) and drives the marks from them: for each group it writes
; 0x20 into every one of that group's mark slots, then compares the setting
; character against '0', '1', '2', ... and writes 0x60 into the slot that
; matches. 0x60 is a back-tick - which is why the authored strings carry one.
; It is the mark, written in, not authored text.
;
; The slots are the addresses already in menu_radios: 000266B8/000266C5/
; 000266D2 for sound at 00025F07, and 00026712/0002672A/00026743/00026755 for
; control at 00025EC1. The character selects the Nth entry of its group in
; table order.
;
; This used to scan the strings for the back-tick and infer the setting from
; where it found it, which is the dataflow inverted: it made the authored text
; the source of truth and left a setting no way to move a mark. The handlers
; at 00026BD9-00026BFA and 00026CC6 write these characters, so the original's
; direction is the one that has to hold.
;
; The four characters are recovered, not asserted: a QMP capture of the
; running game reads 00025DD4-00025DD7 as '1','0','0','3', and 00026211,
; 00025F07, 00025F42 and 00025EC1 resolve those four bytes as detail, sound,
; music and control respectively - Detail Medium, Sound Loud, Music Loud,
; Keyboard.
; DOS: flat 00025EB3-00025F7D, the settings-to-mark writer; setting bytes at
; 00025DD4-00025DD7; group slots as listed in menu_radios.
; DOS symbol: inside loc_00025EA5
; Port: clears each group's marks, then writes the back-tick into the set line.
; Preserved: the 0x20 clear, the 0x60 mark, the group slots, and the
; character-selects-the-Nth-entry rule.
; Difference: the COMANCHE.CFG parser that fills 00025DD4-00025DD7 is not
;   traced, so menu_settings is initialised from the captured values rather
;   than read from the file. The image's own bytes are '2','1','1','4', which
;   the shipped configuration overrides.
; Kind: translated.
; Status: ported; the settings file parser remains open.
; Read COMANCHE.MNU's settings tail, then push its toggles into the menu text.
;
; 00005675 loads the file to 0x25DBC and the settings block is that + 0x18.
; A missing or short file leaves the image's own defaults standing, which is
; what the original does - 00005672's `jb` skips the load on the probe's
; carry.
; DOS: flat 00005665-0000567E, the COMANCHE.MNU load.
; DOS symbol: inside loc_000055xx startup
; Record: analysis/functions/falcon-attract.md#resources
; Port: GEMDOS Fopen/Fread of the same file into the same block.
; Preserved: the file, its +0x18 settings offset, and the leave-defaults
;   behaviour when it is absent.
; Kind: translated.
; Status: ported; the block matches a capture of the running original.
menu_load_settings
        movem.l d0-d2/a0-a1,-(sp)
        ; The image's own 35 bytes are what 00025DBC holds until the file
        ; replaces them, and what 00026D99 writes back if it never did.
        lea     menu_file_defaults,a0
        lea     menu_file_buffer,a1
        moveq   #MENU_FILE_BYTES-1,d0
.defaults
        move.b  (a0)+,(a1)+
        dbra    d0,.defaults
        move.w  #0,-(sp)                        ; read-only
        pea     menu_file_name
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .done
        move.w  d0,d2                           ; handle

        pea     menu_file_buffer
        move.l  #MENU_FILE_BYTES,-(sp)
        move.w  d2,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d1                           ; bytes actually read

        move.w  d2,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp

        cmpi.l  #MENU_FILE_BYTES,d1
        bne     .done                           ; short file: keep the defaults
        lea     menu_file_buffer+MENU_SETTINGS_IN_FILE,a0
        lea     menu_settings,a1
        moveq   #MENU_SETTING_BYTES-1,d0
.copy
        move.b  (a0)+,(a1)+
        dbra    d0,.copy
.done
        movem.l (sp)+,d0-d2/a0-a1
        rts

; Save Menu Settings: 00026D8F-00026D99 writes the 0x23 bytes at 00025DBC to
; Comanche.MNU - the file as it was read, with the settings block as it stands
; now.
; DOS: flat 00026D8F-00026D99, 00015D40 over [00025DBC], 0x23 bytes.
; DOS symbol: inside loc_00026D8B
; Record: analysis/functions/falcon-attract.md#menu
; Port: GEMDOS Fcreate/Fwrite/Fclose of the same bytes.
; Preserved: the file, its length and the settings offset.
; Difference: a failed create or short write does not stop the program.
; Kind: adapted - GEMDOS replaces INT 21h.
; Status: ported.
menu_save_settings
        movem.l d0-d2/a0-a1,-(sp)
        lea     menu_settings,a0
        lea     menu_file_buffer+MENU_SETTINGS_IN_FILE,a1
        moveq   #MENU_SETTING_BYTES-1,d0
.copy
        move.b  (a0)+,(a1)+
        dbra    d0,.copy
        clr.w   -(sp)                           ; attributes
        pea     menu_file_name
        move.w  #60,-(sp)                       ; Fcreate
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi.s   .out
        move.w  d0,d2
        pea     menu_file_buffer
        move.l  #MENU_FILE_BYTES,-(sp)
        move.w  d2,-(sp)
        move.w  #64,-(sp)                       ; Fwrite
        trap    #1
        lea     12(sp),sp
        move.w  d2,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp
.out
        movem.l (sp)+,d0-d2/a0-a1
        rts

; 000268A5-000268BE: the seven toggle characters into the menu text.
; DOS: flat 000268A5-000268BE, settings-to-menu-text propagation.
; DOS symbol: inside loc_00026878
; Record: analysis/functions/falcon-attract.md#menu
; Port: writes the same seven bytes at the same offsets.
; Preserved: the source order, which is by source address and not the order
;   menu_toggles lists.
; Kind: translated.
; Status: ported; the three HUD gates now read what the original reads.
menu_apply_options
        movem.l d0-d2/a0-a2,-(sp)
        lea     menu_option_targets,a0
        lea     menu_settings+4,a1              ; 0x25DD8
        lea     menu_group_text,a2
        moveq   #MENU_OPTION_COUNT-1,d0
.one
        moveq   #0,d1
        move.w  (a0)+,d1
        move.b  (a1)+,0(a2,d1.l)
        dbra    d0,.one
        movem.l (sp)+,d0-d2/a0-a2
        rts

menu_radio_init
        movem.l d0-d5/a0-a2,-(sp)
        lea     menu_group_text,a1

        ; 00025EB3/00025EF2/00025F00: every mark slot to a space first.
        lea     menu_radios,a0
        moveq   #MENU_RADIOS-1,d1
.clear
        addq.l  #4,a0                           ; past selector and group
        moveq   #0,d3
        move.w  (a0)+,d3
        move.b  #' ',0(a1,d3.l)                 ; 0x20
        dbra    d1,.clear

        ; 00025ECA/00025ED5/...: the back-tick into each group's set line.
        lea     menu_radios,a0
        moveq   #MENU_RADIOS-1,d1
        moveq   #0,d4                           ; index within the group
        moveq   #-1,d0                          ; group last seen
.entry
        addq.l  #2,a0                           ; past the selector
        moveq   #0,d2
        move.w  (a0)+,d2                        ; group
        moveq   #0,d3
        move.w  (a0)+,d3                        ; slot offset
        cmp.w   d0,d2
        beq     .same_group
        move.w  d2,d0
        moveq   #0,d4                           ; a new group restarts at 0
.same_group
        lea     menu_settings,a2
        moveq   #0,d5
        move.b  0(a2,d2.w),d5
        subi.w  #'0',d5                         ; character selects the Nth
        cmp.w   d4,d5
        bne     .not_set
        move.b  #'`',0(a1,d3.l)                 ; 0x60
        move.w  d2,d5
        add.w   d5,d5
        lea     menu_setting,a2
        move.w  d3,0(a2,d5.w)
.not_set
        addq.w  #1,d4
        dbra    d1,.entry
        movem.l (sp)+,d0-d5/a0-a2
        rts

; d1 = the open column's row count.
; DOS: flat 0002615C, helper within menu navigation's authored row tables.
; Port: returns the row count for the selected authored menu group.
; Preserved: group boundaries and separator rows.
; Kind: translated.
; Status: ported; covered by menu navigation.
menu_row_count
        move.w  menu_col,d1
        add.w   d1,d1
        lea     menu_rows,a2
        move.w  0(a2,d1.w),d1
        rts

; 00025FA3: the packed (column << 4) | row against the four separator rows,
; stepping again in the stored direction on a match.
; DOS: helper within 0002615C menu navigation.
; DOS symbol: loc_0002615C
; Port: skips authored separator rows when moving the menu cursor.
; Preserved: direction, wrap, and separator semantics.
; Kind: translated.
; Status: ported; covered by menu navigation.
menu_skip_separator
        movem.l d0-d2/a0/a2,-(sp)
        moveq   #3,d2                           ; bounded, not a search
.again
        move.w  menu_col,d0
        lsl.w   #4,d0
        or.w    menu_row,d0
        lea     menu_separators,a0
        moveq   #MENU_SEPARATORS-1,d1
.probe
        cmp.b   (a0)+,d0
        beq     .step
        dbra    d1,.probe
        bra     .out
.step
        move.w  menu_row,d0
        add.w   menu_dir,d0
        bpl     .low_ok
        bsr     menu_row_count
        subq.w  #1,d1
        move.w  d1,d0
.low_ok
        move.w  d0,menu_row
        bsr     menu_row_count
        move.w  menu_row,d0
        cmp.w   d1,d0
        blo     .bounded
        clr.w   menu_row
.bounded
        dbra    d2,.again
.out
        movem.l (sp)+,d0-d2/a0/a2
        rts
        data

; 00025DD4-00025DDE, the whole settings block: four radio characters then
; seven brace toggles.
;
; These are NOT from COMANCHE.CFG - that was a wrong reading, and the earlier
; comment here said so. 00005566-00005585 parses COMANCHE.CFG and it sets the
; SOUND hardware up: [0x53DB] & 0xF becomes the port (<<4, +0x200 - 0x220 for
; the shipped file) and [0x53DC] & 7 the IRQ. The file's ten digits are
; "0132700000" and none of them reaches 0x25DD4.
;
; The real source is COMANCHE.MNU. 00005675 loads it to 0x25DBC and the
; settings block at 0x25DD4 is therefore the file at +0x18 - and the shipped
; 35-byte file's bytes 24..34 are exactly '1','0','0','3' then '}' x5 and
; '{' x2, which is what a capture of the running original reads back. Twelve
; little-endian words precede them.
;
; The defaults below are the IMAGE's own bytes, which is what the original
; runs with when the file is absent; menu_load_settings overwrites them when
; it is present.
MENU_SETTING_BYTES = 11
MENU_SETTINGS_IN_FILE = 24
MENU_FILE_BYTES = 35
menu_settings
        dc.b    '2','1','1','4'
        dc.b    '{','{','{','{','{','{','{'
        even
; 00025FA3's four constants: (column << 4) | row for every row that is a
; `|` $F9 separator image rather than an item - Detail's one, and the three
; in the sound and control column.
menu_separators
        dc.b    $13,$23,$27,$2C
        even
; 00026AB6's boolean cases: the packed selector, then the offset of the brace
; it flips inside menu_group_text. The DOS addresses are 000266A0, 000266A9,
; 00026767, 0002677A, 000267AC, 000267C1 and 000267D2.
MENU_GROUP_ORIGIN = $26607
menu_toggles
        dc.w    $14,$266A0-MENU_GROUP_ORIGIN    ; Clouds
        dc.w    $15,$266A9-MENU_GROUP_ORIGIN    ; Small Pixels
        dc.w    $2D,$26767-MENU_GROUP_ORIGIN    ; ThrustMaster WCS
        dc.w    $2E,$2677A-MENU_GROUP_ORIGIN    ; Rotor Control (pedals)
        dc.w    $30,$267AC-MENU_GROUP_ORIGIN    ; Artificial Horizon
        dc.w    $31,$267C1-MENU_GROUP_ORIGIN    ; HID Indicators
        dc.w    $32,$267D2-MENU_GROUP_ORIGIN    ; HID Compass
; 000268A5-000268BE copies settings bytes 4..10 into the menu text, and the
; order is NOT menu_toggles' order - it is by source address:
;   [0x25DD8]->[0x266A0]  [0x25DD9]->[0x266A9]  [0x25DDA]->[0x267AC]
;   [0x25DDB]->[0x267C1]  [0x25DDC]->[0x267D2]  [0x25DDD]->[0x26767]
;   [0x25DDE]->[0x2677A]
; so the two grey/joystick entries come last, after the three HUD ones.
menu_option_targets
        dc.w    $266A0-MENU_GROUP_ORIGIN        ; Clouds
        dc.w    $266A9-MENU_GROUP_ORIGIN        ; Small Pixels
        dc.w    $267AC-MENU_GROUP_ORIGIN        ; Artificial Horizon
        dc.w    $267C1-MENU_GROUP_ORIGIN        ; HID Indicators
        dc.w    $267D2-MENU_GROUP_ORIGIN        ; HID Compass
        dc.w    $26767-MENU_GROUP_ORIGIN        ; ThrustMaster WCS
        dc.w    $2677A-MENU_GROUP_ORIGIN        ; Rotor Control
MENU_OPTION_COUNT = 7

menu_file_name
        dc.b    "COMANCHE.MNU",0
        even

; The radio groups: selector, settings slot, and the offset of the line's
; first character inside menu_group_text. 00026CC2 writes '0'..'2' into
; 00025DD4 for detail, 00026CE3 and 00026D2C the same into 00025DD5 and
; 00025DD6 for sound and music, and 00026BD5 '0'..'3' into 00025DD7 for the
; controller. Holding the chosen line's offset instead of the digit is the
; same fact in the form the redraw wants.
menu_radios
        dc.w    $10,0,$2666E-MENU_GROUP_ORIGIN  ; Detail High
        dc.w    $11,0,$2667C-MENU_GROUP_ORIGIN  ; Detail Medium
        dc.w    $12,0,$2668C-MENU_GROUP_ORIGIN  ; Detail Low
        dc.w    $20,1,$266B8-MENU_GROUP_ORIGIN  ; Sound Loud
        dc.w    $21,1,$266C5-MENU_GROUP_ORIGIN  ; Sound Soft
        dc.w    $22,1,$266D2-MENU_GROUP_ORIGIN  ; Sound Off
        dc.w    $24,2,$266E5-MENU_GROUP_ORIGIN  ; Music Loud
        dc.w    $25,2,$266F2-MENU_GROUP_ORIGIN  ; Music Soft
        dc.w    $26,2,$266FF-MENU_GROUP_ORIGIN  ; Music Off
        dc.w    $28,3,$26712-MENU_GROUP_ORIGIN  ; ThrustMaster Joystick
        dc.w    $29,3,$2672A-MENU_GROUP_ORIGIN  ; Flightstick w/Throttle
        dc.w    $2A,3,$26743-MENU_GROUP_ORIGIN  ; Normal Joystick
        dc.w    $2B,3,$26755-MENU_GROUP_ORIGIN  ; Keyboard
; $01-$0A, in the order 00027108 tests them.
menu_numbered
        dc.w    COL_MENU_RED,COL_MENU_MAGENTA,COL_MENU_WHITE
        dc.w    COL_MENU_BLUE,COL_MENU_ORANGE,COL_MENU_RED
        dc.w    COL_MENU_MAGENTA,COL_MENU_BLUE,COL_MENU_ORANGE
        dc.w    COL_MENU_RED

        bss
        even
menu_file_buffer
        ds.b    MENU_FILE_BYTES
        even
        even
menu_open
        ds.w    1
; 0 none, 1 About Comanche, 2 Menu Settings Saved: the box waiting for a key.
menu_message
        ds.w    1
menu_pen_x
        ds.w    1
menu_pen_y
        ds.w    1
menu_ink_carry
        ds.w    1
menu_ink
        ds.w    1
menu_hot_id
        ds.w    1
menu_hotspot_count
        ds.w    1
menu_hotspot_x
        ds.w    MENU_HOTSPOTS
menu_hotspot_y
        ds.w    MENU_HOTSPOTS
menu_hotspot_id
        ds.w    MENU_HOTSPOTS
menu_default_ink
        ds.w    1
menu_ready
        ds.w    1
        global  menu_col, menu_row
menu_col
        ds.w    1
menu_row
        ds.w    1
menu_dir
        ds.w    1
menu_rows
        ds.w    MENU_COLUMNS
menu_width
        ds.w    MENU_COLUMNS
        even
menu_group
        ds.l    MENU_COLUMNS
        even
; Per radio group, the offset of the line that carries the mark.
menu_setting
        ds.w    MENU_RADIO_SLOTS

        end
