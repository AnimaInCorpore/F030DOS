; Route: analysis/functions/falcon-attract.md#attract-route.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; The list-menu driver, DOS 00027DB4, and the screen it selects from.
;
; This is the widget the original's whole out-of-flight flow is built on: the
; main operations menu, campaign select, mission select and the briefing's
; accept/reject pair are all the same routine pointed at different sections of
; the text block at 00029B2C.
;
; Two things about it are ports of structure rather than of code, and both are
; forced rather than chosen:
;
; 1. The original is a blocking loop. 00027DCD redraws, then 00027E9F calls the
;    retrace wait at 00015B78 and 00027EA4 reads the key FIFO, looping until a
;    key ends it. This port cannot block: main.s owns one update and one
;    publish per VBL, and a routine that spins inside a frame would stop the
;    VBL pacing the demo and the flight both depend on. So the loop becomes a
;    per-frame state machine, exactly the accommodation attract.s already makes
;    for the attract cycle, and for the same reason.
;
; 2. Its drawing is Mode X. Two of the four routines it calls - 00026FD9 and
;    00016B50 - are VGA plane selects, and the pointer arithmetic around them
;    is 82-bytes-per-plane row math on a 328-wide page. None of that survives
;    onto a 16-bit linear surface. What does survive, and is what this draws
;    through, is the pair menu.s already ports: the bevelled box at 0002628E
;    and the markup text interpreter at 00027034.
;
; The geometry that IS recovered is the box. menu.s's own caller establishes
; the register convention for 0002628E - bl and bh are X and width in 4-pixel
; Mode X byte units, dl and dh are the top row and the height in rows - so the
; driver's bl=0x0E, bh=0x34, dl=0x1E, dh=0xA0 is 208x160 at (56,30).
;
; The selection geometry at 00027DF7, settled 2026-08-19. It had been recorded
; here as unreconciled, and the obstacle was a mistake in the reading rather
; than anything missing: the highlight's offset was being compared against the
; text's BASELINE when it is a cell top, and the text sits two scanlines into
; its own cell.
;
; On the original's 328-wide Mode X page a scanline is 82 bytes per plane, so
; the 0x3D8 row is exactly 12 scanlines. Decomposed against that:
;
;   0x99C            30 scanlines = the box top, which is dl=0x1E in the
;                    0002628E call four instructions earlier - not a free
;                    constant at all
;   0xB88            36 scanlines = exactly 3 rows
;   0x7B0            24 scanlines = exactly 2 rows, the pilot sub-mode step
;   highlight sel=0  30 + 36 = scanline 66 = line 3's CELL TOP
;   text line L      scanline 32 + 12L, which is that cell top plus 2
;
; So selection N marks text line 3 + N, and [00027DAD] shifts that by two more
; rows. That byte is not decoration: 00028D71 sets it to 1 immediately before
; the main menu's call and 00028D7D clears it straight after, while 00028CEF
; leaves it 0 for the campaign and mission screens. Which is exactly what the
; two layouts need - line 3+2 is "Begin Mission" under the main menu's five
; leading lines, and line 3 is the first name row under the other screens'
; three - and it settles the count too, because the same flag takes the 0xFA
; seed to 0xF8 and turns the 8 this port was measuring into the 7 items the
; main menu actually has.

        include "inc/comanche.s"

        global  screen_enter, screen_frame, screen_active, screen_id
        global  screen_roster_load, roster_buffer
        global  screen_mission_star, screen_mission_next
        xref    debrief_buf, debrief_won, roster_select_mission, pilot_locate
        xref    menu_font_width, menu_lock_text, menu_stats_text, debrief_number
        xref    attract_overview, key_queue, key_state, key_latch
        xref    roster_sort, roster_save, debrief_pilot
        xref    snd_mode, flight_mission_sound_load, flight_mission_sound_start
        xref    name_head_text, name_tail_text, name_plain_keys, name_shift_keys
        xref    name_prompt_text, roster_defaults
        xref    menu_ink, menu_default_ink, menu_ink_carry, attract_blit_x
        global  screen_fill_campaigns, screen_select_campaign

; 0002628E through menu.s's convention: X and width are 4-pixel byte units.
SCR_BOX_X       = $0E*4
SCR_BOX_W       = $34*4
SCR_BOX_Y       = $1E
SCR_BOX_H       = $A0

; 00027E7B advances the text destination by 0x3D8 per line, which is twelve
; 82-byte rows of the original's 328-wide page.
SCR_ROW_H       = 12

; 00028A46-00028A4E: the box is bl=4, bh=0x48, dl=0x1E, dh=0xA0 in 0002628E's
; units (x and width in 4-pixel bytes), and the text starts at page byte 8 of
; row 38 (0x0C34 = 38 * 82 + 8).
DEBRIEF_BOX_X   = 4*4
DEBRIEF_BOX_W   = $48*4
DEBRIEF_BOX_Y   = $1E
DEBRIEF_BOX_H   = $A0
DEBRIEF_TEXT_X  = 8*4+1
DEBRIEF_TEXT_Y  = 38
DB_SCREEN_OFFSET = $285FA-$284B1

; 00029515: the briefing text's box is the score screen's (bl=4, bh=0x48,
; dl=0x1E, dh=0xA0) and its text starts at 0xA45 = row 32, byte 5. The button
; box is bl=0x18, bh=0x20, dl=0xB4, dh=0x1B; its highlight starts at 0x3A4C =
; row 182 of the box's own byte with 0x1E bytes, one row pitch of 12 per line,
; and its text at 0x3B0A = row 184, byte 0x1A.
BRIEF_TEXT_X    = 5*4+1
BRIEF_TEXT_Y    = 32
BRIEF_BTN_X     = $18*4
BRIEF_BTN_W     = $20*4
BRIEF_BTN_Y     = $B4
BRIEF_BTN_H     = $1B
BRIEF_HILITE_Y  = 182
BRIEF_HILITE_W  = 3+$1E*4+2
BRIEF_BTN_TX    = $1A*4+1
BRIEF_BTN_TY    = 184
; 00029D51 and 00029ED9 into the text block, 00029B2C-based.
BRIEF_BTN_TEXT  = $29D51-$29B2C
BRIEF_LOAD_TEXT = $29ED9-$29B2C
; 00026EAC (bl=0x0F, bh=0x32, dl=0x42, dh=0x0F; text at 0x167B = row 70, byte
; 15) and 000294DE (bl=0x19, bh=0x1E, dl=0xCE, dh=0x0F; 0x4360 = row 210,
; byte 28).
LOCK_BOX_X      = $0F*4
LOCK_BOX_W      = $32*4
LOCK_BOX_Y      = $42
LOCK_BOX_H      = $0F
LOCK_TEXT_X     = 15*4+1
LOCK_TEXT_Y     = 70
LOAD_BOX_X      = $19*4
LOAD_BOX_W      = $1E*4
LOAD_BOX_Y      = $CE
LOAD_BOX_H      = $0F
LOAD_TEXT_X     = 28*4+1
LOAD_TEXT_Y     = 210
; The briefing text the 000290C6 wrap builds is a few hundred bytes for the
; longest shipped description; the original's own buffer at 0002FB14 has the
; whole bss behind it.
BRIEF_BUF_BYTES = 4096

; 00028B55-00028BE5: the statistics box is bl=4, bh=0x48, dl=0x41, dh=0x5A and
; its text starts at 0x1860 = row 76, byte 8. The template's own offsets for
; the pieces 00028B7D-00028BC8 patch: the name, the score's eight digits, the
; victories' and the kills' four (of which three and four digits are written).
STATS_BOX_X     = 4*4
STATS_BOX_W     = $48*4
STATS_BOX_Y     = $41
STATS_BOX_H     = $5A
STATS_TEXT_X    = 8*4+1
STATS_TEXT_Y    = 76
STATS_NAME      = $28ABD-$28AB5
STATS_SCORE     = $28AF6-$28AB5
STATS_MISSIONS  = $28B02-$28AB5
STATS_KILLS     = $28B1C-$28AB5
STATS_BYTES     = $28B37-$28AB5

; 00028042-00028074: the name box is bl=0x0A, bh=0x3C, dl=0xCE, dh=0x0F and
; the prompt starts at 0x434F = row 210, byte 11 with ah=1 (pixel 0). The
; buffer sits 0x15 into the prompt (00027FEA - 00027FD5) and is 32 bytes of
; 0xFC ahead of the closing 0xFF; the name is 0x16 characters at most and
; stops growing once it is 0x6C pixels wide.
NAME_BOX_X      = $0A*4
NAME_BOX_W      = $3C*4
NAME_BOX_Y      = $CE
NAME_BOX_H      = $0F
NAME_TEXT_X     = 11*4
NAME_TEXT_Y     = 210
NAME_BUF_OFFSET = $27FEA-$27FD5
NAME_BUF_BYTES  = 32
NAME_MAX        = $16
NAME_WIDTH_MAX  = $6C
KEY_SHIFT_L     = $2A
KEY_SHIFT_R     = $36
KEY_DELETE      = $53
BRIEF_WRAP_W    = $118

; 00027DE6 takes the box from screen byte 0x0E and the text from 0x0F, one
; 4-pixel unit further in, and 00027E5E's `mov ah,2` starts the pen on plane 1 of
; that byte - pixel 1; 0xA4F is two rows below the box's own top row.
SCR_TEXT_DX     = 4+1
SCR_HILITE_W    = 3+$32*4+2
SCR_TEXT_DY     = 2

; 00027E13 seeds the row counter here and increments once per drawn line; what
; is left at the 0xFF is the item count the selection is clamped against.
; 00027E29 takes two off it in the pilot sub-mode, in step with the two rows
; 00027E23 adds to the highlight.
SCR_SEED        = $FA

; 0xB88 / 0x3D8: selection 0 marks the third text line, and 0x7B0 / 0x3D8 is
; the two further rows [00027DAD] adds. See the decomposition above.
SCR_ITEM_LINE0  = 3
SCR_PILOT_ROWS  = 2

; The main operations menu's seven lines are the seven targets 00028D8B
; dispatches on.
SCR_BEGIN_MISSION = 0
SCR_STATS         = 1
SCR_CHOOSE_PILOT  = 2
SCR_OVERVIEW      = 3
SCR_CREDITS       = 5
SCR_DEMO          = 4
SCR_EXIT          = 6

; [00027DAC], the screen id the driver and its back-out both key on.
SCR_ID_MAIN       = 0
SCR_ID_CAMPAIGN   = 1
SCR_ID_MISSION    = 2
; Pilot select is an internal id here only. The original leaves [00027DAC] at 0
; for it - 00028216 sets no screen id and it is reached after 00028D7D has
; cleared the sub-mode - and distinguishes it from the main menu purely by the
; base it hands the driver. Escape therefore does not back out of it, exactly
; as on the main menu; Return is the only way out.
SCR_ID_PILOT      = 3
; Credits is not a list at all: 00028DB5 loads credit1.dta, 00028DEB waits for
; a key and 00028DF9 goes back to the menu. No box, no lines, no selection.
SCR_ID_CREDITS    = 4
; The mission-end score screen, 00028A1F: a picture, the 0002628E box over it
; and the result text, until Escape. No list, no selection.
SCR_ID_DEBRIEF    = 5
; The two screens the mission list leads to. Neither is a list: 00026E90's
; message box for a locked mission, and the briefing screen at 0002936C, whose
; own two-line list is [00027DAC] = 3 in the original.
SCR_ID_LOCKED     = 6
SCR_ID_BRIEFING   = 7
; 00028B37, Your Stats.
SCR_ID_STATS      = 8
; 0002800C, the new pilot's name.
SCR_ID_NAME       = 9

; The mission screen's name rows. 0002A1E7 writes from 00029D95, which is
; 00029D95-00029B2C into the block, and 0002A27E advances 0x20 per row for at
; most the ten 0002A1F7 allows.
SCR_MISSION_ROW0    = $269
SCR_MISSION_STRIDE  = $20
SCR_MISSION_MAX     = 10

; The campaign screen's own rows. 0002A11A starts the row cursor at 00029C03,
; which is 00029C03-00029B2C into the block, and 0002A17B advances 0x20 for
; each file that was found - not for each file that was tried.
SCR_CAMPAIGN_ROW0   = $D7
SCR_CAMPAIGN_STRIDE = $20
SCR_CAMPAIGN_MAX    = 10

; 0002A18F's list-position-to-filename-digit table. It lives INSIDE the text
; block, in the eleven zero bytes between the campaign screen's 0xFF at
; 00029D45 and the briefing pair's first line at 00029D51, and it is safe
; there because no screen renders that gap: the section walk keys on 0xFF and
; nothing points the driver at section 3 - 00029404 reads the accept/reject
; pair directly. Kept in the same place here rather than lifted into a
; variable, because a table the original overlays on its own data is exactly
; the kind of fact a separate array would quietly lose.

; COMANCHE.NAM, the pilot roster. 8 records of 43 bytes in the form
; ' |b<FD><FD><digit>|g <name>' - the name nine bytes in, the campaign digit at
; five - then the scalars, of which [00029701] is the selected pilot and the
; eight bytes at [00029702] are the campaign each pilot is on.

; 00029B44 - 00029B2C: the first 0xFC of the header's "RAH-66 Pilot" fill.
SCR_PILOT_NAME      = $18

        text

; Enter a screen. d0 = screen id, the original's [00027DAC]: 0 main operations,
; 1 campaign select, 2 mission select, 3 loading.
;
; The text block's sections are 0xFF-separated and section 0 is a five-byte
; pad, so screen N is section N+1. Walking to it rather than holding a table of
; pointers is what the original does - [00027DB0] is set by the caller and the
; draw loop simply runs to the next 0xFF.
; DOS: flat 00027DB4 entry, list-menu setup.
; DOS symbol: sub_00027DB4
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: selects the screen's section and starts the per-frame state machine.
; Preserved: screen id, initial selection, and the section walk.
; Kind: translated.
; Status: partial; only the main operations screen has a dispatch.
screen_enter
        movem.l d0-d2/a0-a1,-(sp)
        move.w  d0,screen_id
        clr.w   screen_sel
        move.w  #1,screen_active

        ; [00027DAD]. 00028D71 sets it for the main menu's call and 00028D7D
        ; clears it after; 00028CEF leaves it 0 for the campaign and mission
        ; screens. It is what makes one fixed geometry serve both layouts.
        clr.w   screen_pilot_mode
        tst.w   d0
        bne     .not_main
        move.w  #1,screen_pilot_mode
.not_main

        ; Each screen brings its own background, through the same loader the
        ; attract screens use: 00028CE8 loads rah66.dta for the main menu and
        ; 00028EDB loads mission.dta before the campaign chain. Without one the
        ; screen would sit on whatever was left in the buffers.
        ; Only the two mission-chain screens change the backdrop. 00028216
        ; loads nothing at all for pilot select - it is entered from the main
        ; menu, which is already on rah66.dta - so it keeps that one.
        lea     name_rah66_menu,a0
        cmpi.w  #SCR_ID_DEBRIEF,d0
        beq     .debrief_background
        cmpi.w  #SCR_ID_CREDITS,d0
        beq     .credits_background
        cmpi.w  #SCR_ID_CAMPAIGN,d0
        beq     .mission_background
        cmpi.w  #SCR_ID_MISSION,d0
        beq     .mission_background
        cmpi.w  #SCR_ID_LOCKED,d0
        beq     .locked_background
        cmpi.w  #SCR_ID_BRIEFING,d0
        bne     .have_background
.mission_background
        lea     name_mission_dta,a0
        bra     .have_background
.locked_background
        ; 00026E98 restores the picture and takes nothing from it but the keys:
        ; the key that chose the mission is still pending, as at the credits.
        clr.w   input_held
        clr.w   input_pending
        clr.w   input_events
        bra     .mission_background
.debrief_background
        ; 00028A1F is reached with the picture 000288C3 ('lose3.dta') or 000289FA
        ; ('win3.dta') already loaded; 000288EA / 00028A19 pick it by which of
        ; the two record updates ran. Escape alone leaves, and the key that
        ; ended the flight is still in the buffer.
        lea     name_lose3,a0
        tst.b   debrief_won
        beq     .debrief_picked
        lea     name_win3,a0
.debrief_picked
        clr.w   input_held
        clr.w   input_pending
        clr.w   input_events
        bra     .have_background
.credits_background
        lea     name_credits,a0
        ; 00028DE4 empties the key buffer before 00028DEB starts waiting on it,
        ; because the keypress that opened this screen is still there and would
        ; close it again on the very next frame.
        clr.w   input_held
        clr.w   input_pending
        clr.w   input_events
.have_background
        jsr     attract_show_image

        ; The pilot screen is not in the text block at all: 00028231 points the
        ; driver at the roster's own header instead, and it walks straight on
        ; into the 43-byte records.
        cmpi.w  #SCR_ID_PILOT,d0
        bne     .not_pilot
        lea     roster_screen,a0
        bra     .found
.not_pilot
        ; Credits sets no base at all. 00028DB5 loads its image, waits and
        ; returns; it never writes [00027DB0], so the driver's base is still
        ; the main menu's when it comes back. This used to fall through to the
        ; table below and read an entry past the end of it - four entries, ids
        ; up to four - and the value it found happened not to matter only
        ; because screen_draw short-circuits this screen to the image.
        cmpi.w  #SCR_ID_CREDITS,d0
        beq     .no_fill
        cmpi.w  #SCR_ID_DEBRIEF,d0
        beq     .no_fill
        cmpi.w  #SCR_ID_LOCKED,d0
        beq     .no_fill
        cmpi.w  #SCR_ID_BRIEFING,d0
        beq     .no_fill
        cmpi.w  #SCR_ID_STATS,d0
        beq     .stats_fill
        cmpi.w  #SCR_ID_NAME,d0
        beq     .no_fill
.block_base
        lea     menu_screen_text,a0
        move.w  d0,d2
        add.w   d2,d2
        lea     screen_base_map,a1
        adda.w  0(a1,d2.w),a0
.found
        move.l  a0,screen_base

        ; 00028F3A resolves the mission list into the screen's rows before
        ; 00028F3F draws it. Without this the rows draw as the 0xFC fill they
        ; ship as, which is what they did before.
        ; 00028D3C fills the header's pilot name before the main menu is drawn,
        ; and 00028F3A resolves the mission list before that screen is.
        tst.w   screen_id
        bne     .not_main_fill
        bsr     screen_fill_pilot
.not_main_fill
        ; 00028F16 opens campaign select ON the campaign that pilot is already
        ; flying rather than on the first, by passing [00029702 + pilot] in as
        ; the driver's incoming selection.
        cmpi.w  #SCR_ID_CAMPAIGN,screen_id
        bne     .no_seed
        bsr     screen_roster_campaign
        move.w  d0,screen_sel
.no_seed
        cmpi.w  #SCR_ID_MISSION,screen_id
        bne     .no_fill
        bsr     screen_fill_missions
        bsr     screen_mission_colours
        bra     .no_fill
.stats_fill
        ; 00028B3C-00028BC8, then 00028C0B empties the key buffer before it
        ; waits on one.
        bsr     stats_patch
        clr.w   input_held
        clr.w   input_pending
        clr.w   input_events
.no_fill
        movem.l (sp)+,d0-d2/a0-a1
        rts

; Load the pilot roster, COMANCHE.NAM, exactly as 00005604's startup does:
; `mov eax,00029582 / call 00015DD0` with the inline filename. The image ships
; a default roster at that address and the file overwrites it, which is why the
; two are byte-compatible; this port has no image copy, so a missing file
; leaves the buffer zeroed and the name fill below simply writes nothing.
; DOS: flat 00005604, roster load into 00029582.
; DOS symbol: inside loc_000055FD
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: reads the same 1,450 bytes into its own buffer.
; Preserved: file name, size and record layout.
; Kind: translated.
; Status: partial; the save side at 00027D92 is not ported.
screen_roster_load
        movem.l d0-d7/a0-a6,-(sp)

        ; The header belongs to the image, not to the file, so it is copied in
        ; front of the load target rather than read from disk.
        lea     menu_pilot_header,a0
        lea     roster_screen,a1
        moveq   #ROSTER_HEADER-1,d0
.header
        move.b  (a0)+,(a1)+
        dbra    d0,.header

        ; The image carries a roster of its own at 00029582 and the file
        ; overwrites it (00005604), so a missing or short file leaves the
        ; image's records standing, as it does in the original.
        lea     roster_defaults,a0
        lea     roster_buffer,a1
        move.w  #ROSTER_BYTES-1,d0
.defaults
        move.b  (a0)+,(a1)+
        dbra    d0,.defaults

        move.w  #0,-(sp)                        ; read-only
        pea     name_roster
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .out
        move.w  d0,d7

        move.l  #roster_buffer,-(sp)            ; buf
        move.l  #ROSTER_BYTES,-(sp)             ; count
        move.w  d7,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp

        move.w  d7,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp
.out
        movem.l (sp)+,d0-d7/a0-a6
        rts

; The campaign the selected pilot is on, [00029702 + [00029701]].
; Out: d0 = the campaign, 0 when there is no usable roster.
; DOS: flat 00028F16-00028F1D.
; DOS symbol: inside loc_00028F05
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same two indexed byte reads.
; Preserved: index source and array base.
; Kind: translated.
; Status: ported; the save back to the file at 00027D92 is not.
screen_roster_campaign
        move.l  a0,-(sp)
        moveq   #0,d0
        lea     roster_buffer,a0
        moveq   #0,d0
        move.b  ROSTER_CURRENT(a0),d0
        cmpi.w  #ROSTER_PILOTS,d0
        blo     .indexed
        moveq   #0,d0
        bra     .out
.indexed
        lea     ROSTER_CAMPAIGNS(a0),a0
        move.b  0(a0,d0.w),d0
        andi.w  #$00FF,d0
.out
        move.l  (sp)+,a0
        rts

; Store screen_sel back as the selected pilot, 00028240.
; DOS: flat 00028216-00028240, pilot-list selection store.
; DOS symbol: sub_00028216
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: writes the selected record's current-pilot byte in the Falcon roster.
; Preserved: selection bounds, byte offset, and no-op on an invalid roster.
; Kind: translated.
; Status: ported; persistent COMANCHE.NAM save remains unrecovered.
screen_roster_set_pilot
        movem.l d0/a0,-(sp)
        move.w  screen_sel,d0
        cmpi.w  #ROSTER_PILOTS,d0
        bhs     .out                            ; the DEL prompt is not a pilot
        lea     roster_buffer,a0
        move.b  d0,ROSTER_CURRENT(a0)
.out
        movem.l (sp)+,d0/a0
        rts

; Store screen_sel back as the selected pilot's campaign, 00028F2F.
; DOS: flat 00028F28-00028F2F, campaign byte store for the selected pilot:
; the roster index [00029701] indexes the campaign array at 00029702.
; DOS symbol: inside loc_00028F05
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: writes the same roster record in Falcon storage.
; Preserved: current-pilot lookup, campaign byte and selection value.
; Kind: translated.
; Status: ported; persistent COMANCHE.NAM save remains unrecovered.
screen_roster_set_campaign
        movem.l d0-d1/a0,-(sp)
        lea     roster_buffer,a0
        moveq   #0,d0
        move.b  ROSTER_CURRENT(a0),d0
        cmpi.w  #ROSTER_PILOTS,d0
        bhs     .out
        move.w  screen_sel,d1
        lea     ROSTER_CAMPAIGNS(a0),a0
        move.b  d1,0(a0,d0.w)
.out
        movem.l (sp)+,d0-d1/a0
        rts

; Copy the selected pilot's name into the main menu's header row.
;
; 00028D3C-00028D5C: the pilot index at [00029701] times the 0x2B record
; stride, plus 0002958B - the name field, nine bytes into the record - then
; 0x16 bytes into 00029B44, which is the first 0xFC of the header's fill.
; DOS: flat 00028D3C-00028D5C, roster name into the main menu header.
; DOS symbol: loc_00028D3C
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same index, stride, field offset, length and destination.
; Preserved: all five, and the 0xFC fill that shows through when blank.
; Kind: translated.
; Status: ported.
screen_fill_pilot
        movem.l d0-d2/a0-a1,-(sp)

        lea     roster_buffer,a0
        moveq   #0,d0
        move.b  ROSTER_CURRENT(a0),d0           ; [00029701]
        cmpi.w  #ROSTER_PILOTS,d0
        bhs     .out                            ; a corrupt index selects nobody
        mulu.w  #ROSTER_STRIDE,d0
        lea     0(a0,d0.w),a0
        lea     ROSTER_NAME(a0),a0

        lea     menu_screen_text,a1
        lea     SCR_PILOT_NAME(a1),a1
        moveq   #ROSTER_NAME_CHARS-1,d1
.copy
        move.b  (a0)+,(a1)+
        dbra    d1,.copy
.out
        movem.l (sp)+,d0-d2/a0-a1
        rts

; Build the campaign list out of the mission files that are actually there.
;
; This is a startup step, 0000561F, and it is the reason the campaign screen
; has anything on it at all: the rows at 00029C03 ship as 0xFC fill. 0002A104
; walks "0.MIS" through "9.MIS", probes each name, reads and decodes the ones
; that exist, and lays that file's own catalog title - the first {...} in the
; stream, ahead of any mission - over the row. A file that is not installed
; leaves no row and no gap, because 0002A17B only advances the cursor when it
; wrote one.
;
; The routine has two products and the second is the one that matters. The
; rows are what the player reads; the digit table 0002A18F fills is what every
; later stage indexes, because the campaign a pilot carries in the roster is a
; POSITION IN THIS LIST and the filename cannot be derived from it. With both
; shipped files installed the two happen to agree and the mapping looks like an
; identity - which is precisely why it has to be built rather than assumed.
;
; DOS: flat 0002A104-0002A1AC, the campaign catalog.
; DOS symbol: sub_0002A104
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same probe/read/decode/title walk into the same rows and table.
; Preserved: probe order, the ten-file cap, the row origin and 0x20 stride, the
; two-space prefix over the shipped fill, the 0xFF end marker one row on, and
; the digit table.
; Kind: translated.
; Status: ported.
screen_fill_campaigns
        movem.l d0-d7/a0-a6,-(sp)
        clr.w   screen_campaign_count

        lea     menu_screen_text,a1
        lea     SCR_CAMPAIGN_ROW0(a1),a1        ; 0002A11A
        moveq   #'0',d5                         ; [0002A126], the digit
        moveq   #SCR_CAMPAIGN_MAX-1,d4          ; 0002A115's ten
.file
        move.b  d5,d0
        bsr     mission_probe_campaign
        tst.l   d0
        bmi     .next                           ; 0002A12D

        ; A file that probed present and then would not read is where the DOS
        ; reader gives up on the program (00015E33 to 000164E3). The nearest
        ; thing that is not fatal is to give up on the list, which is also what
        ; 0002A1AA does for the malformed case just below.
        move.b  d5,d0
        bsr     mission_load_campaign
        tst.l   d0
        bmi     .done

        ; The catalog title is the first {...} in the stream. 0002A15F and
        ; 0002A167 abandon the whole walk when either brace is missing rather
        ; than skipping the file, so a malformed stream ends the list here.
        lea     mission_buffer,a0
        move.l  a0,a2
        adda.l  mission_bytes,a2                ; one past the stream
.find_open
        cmpa.l  a2,a0
        bhs     .done
        move.b  (a0)+,d0
        cmpi.b  #$7B,d0
        bne     .find_open
        move.l  a0,a3                           ; first byte of the title
.find_close
        cmpa.l  a2,a0
        bhs     .done
        move.b  (a0)+,d0
        cmpi.b  #$7D,d0
        bne     .find_close

        move.l  a0,d0
        subq.l  #1,d0
        sub.l   a3,d0                           ; 0002A169's length

        ; 0002A170's two spaces, then the title straight over the row's own
        ; 0xFC fill. Unlike the mission rows this neither pads nor terminates:
        ; what the title does not cover stays fill, which is what makes a short
        ; catalog name sit in a full-width row.
        move.b  #' ',0(a1)
        move.b  #' ',1(a1)
        lea     2(a1),a5

        ; 0002A178 copies the whole title, and so does this. A clamp to the
        ; row was written here first and taken out again: DOS does not wrap the
        ; copy either - it runs straight on into the rows after it, exactly as
        ; a 68030 does - so there is no platform boundary to justify one, and a
        ; bound the original does not have is a second behaviour for malformed
        ; input that nobody has checked against the first.
        move.w  d0,d1
        subq.w  #1,d1
        bmi     .copied
.copy
        move.b  (a3)+,(a5)+
        dbra    d1,.copy
.copied
        ; 0002A17E ends the list at the row after this one. The next campaign
        ; found overwrites the marker; the last one leaves it standing.
        lea     SCR_CAMPAIGN_STRIDE(a1),a6
        clr.b   0(a6)
        clr.b   1(a6)
        move.b  #$FF,2(a6)
        clr.b   3(a6)

        ; 0002A18F, and the count 0002A100 keeps beside it.
        move.w  screen_campaign_count,d0
        lea     menu_screen_text,a0
        lea     SCR_CAMPAIGN_DIGITS(a0),a0
        move.b  d5,0(a0,d0.w)
        addq.w  #1,screen_campaign_count

        move.l  a6,a1                           ; 0002A17B
.next
        addq.b  #1,d5                           ; 0002A19B
        dbra    d4,.file
.done
        movem.l (sp)+,d0-d7/a0-a6
        rts

; Point the mission stream at one campaign's file.
;
; 0002A1AD and 00029038 open with the same four instructions - selected pilot,
; that pilot's campaign, the digit table, patch the name - and then read. This
; is that lookup and that read, without the row rebuild the first one goes on
; to do.
;
; In: d0.w = the campaign's position in the list screen_fill_campaigns built.
; Out: d0.l = 0 when that campaign's file is loaded and decoded, -1 otherwise,
; in which case the buffer still holds whatever it held before.
; DOS: flat 0002A1AD-0002A1E1 and 0002903F-00029073, the same lookup twice.
; DOS symbol: sub_0002A1AD
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the digit-table lookup and the load.
; Preserved: the table, the lookup, the load, and load-before-parse.
; Kind: translated.
; Status: ported.
screen_select_campaign
        movem.l d1/a0,-(sp)

        ; 0002A1C6 indexes the table with the campaign byte and nothing else,
        ; and so does this. A bound against screen_campaign_count was written
        ; here first and taken out: the byte can only be 0 to 255, the table
        ; sits 0x21B into a 0x3C4 block, so even a roster left behind by an
        ; installation with more campaign files reads inside the block - and
        ; what it reads is a text byte that is not a digit, which patches a
        ; name that does not open. That is the original's own outcome, reached
        ; the original's own way, and it needs no rule of its own.
        lea     menu_screen_text,a0
        lea     SCR_CAMPAIGN_DIGITS(a0),a0
        move.b  0(a0,d0.w),d0
        bsr     mission_load_campaign

        movem.l (sp)+,d1/a0
        rts

; Write the mission titles into the mission screen's own rows.
;
; 0002A1AD does exactly this, and it writes into the text block rather than
; into a side table: the rows at 00029D95 ship as 0xFC fill and the names are
; laid over them at runtime. The block is data here too, so this writes into it
; the same way. Everything about the row is the original's - the "|g  " colour
; prefix at 0002A273, the 0x20 stride at 0002A27E, the 0xFC pad and the NUL at
; 0002A28A - and so is the scan: skip the catalog title's closing brace, then
; take each following {...} in order, at most ten.
;
; The file it scans is the selected pilot's own campaign, which is what the
; first four instructions are for. That was the gap: the port had exactly one
; stream, the one startup left in the buffer, so the screen listed campaign 0's
; missions whichever campaign had just been chosen.
; DOS: flat 0002A1AD-0002A299, per-pilot mission list into the screen rows.
; DOS symbol: sub_0002A1AD
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same read, then the same rows out of the same stream.
; Preserved: the per-pilot campaign lookup, row origin, stride, colour prefix,
; fill byte, the ten cap, and the two flags each entry carries.
; Kind: translated.
; Status: ported; the description pointers 0002A25C keeps for the briefing are.
; not, because no briefing screen reads them yet.
screen_fill_missions
        movem.l d0-d7/a0-a6,-(sp)

        ; 0002A1AD-0002A1E1: selected pilot, that pilot's campaign, the digit
        ; table, read.
        ;
        ; The original cannot fail here and does not test for it. 00015E16
        ; takes a failed open to 000164E3 and never comes back, so there is no
        ; DOS behaviour to copy for a missing file - mission_load_campaign
        ; raises MISSION_STATUS_ERROR instead, which is this port's platform
        ; error return and which main.s already refuses to start on.
        ; The rows below are then skipped on the zero byte count.
        bsr     screen_roster_campaign
        bsr     screen_select_campaign

        move.l  mission_bytes,d7
        beq     .done

        lea     menu_screen_text,a1
        lea     SCR_MISSION_ROW0(a1),a1
        lea     mission_buffer,a0
        move.l  a0,d6
        add.l   d7,d6
        move.l  d6,a2                           ; one past the stream

        ; 0002A1FE skips to the first '}' - the catalog title's close - so the
        ; group name is not taken as the first mission.
.first_close
        cmpa.l  a2,a0
        bhs     .done
        move.b  (a0)+,d0
        cmpi.b  #$7D,d0
        bne     .first_close

        moveq   #SCR_MISSION_MAX-1,d5
        moveq   #0,d4                           ; the row, [0002A100]
.entry
        ; 0002A212 plants an end marker at this row before looking for a title,
        ; so a row with no title behind it terminates the screen.
        clr.b   0(a1)
        clr.b   1(a1)
        move.b  #$FF,2(a1)
        clr.b   3(a1)

        move.l  a0,a3
.find_open
        cmpa.l  a2,a3
        bhs     .done
        move.b  (a3)+,d0
        cmpi.b  #$7B,d0
        bne     .find_open
        move.l  a3,a4                           ; first byte of the title
.find_close
        cmpa.l  a2,a3
        bhs     .done
        move.b  (a3)+,d0
        cmpi.b  #$7D,d0
        bne     .find_close

        move.l  a3,d0
        subq.l  #1,d0
        sub.l   a4,d0                           ; title length, brace excluded

        ; 0002A234. A '}' followed by '*' marks a mission that is not open
        ; until the one before it has been flown - 00028F95 reads this array to
        ; decide whether the row is drawn locked - and a digit after the star is
        ; kept as digit+1, so that zero can mean "no digit at all". Both shipped
        ; catalogs star their back half and put a digit on the last entry only.
        lea     screen_mission_star,a5
        clr.b   0(a5,d4.w)
        lea     screen_mission_next,a6
        clr.b   0(a6,d4.w)
        cmpa.l  a2,a3
        bhs     .flags_done
        cmpi.b  #'*',(a3)
        bne     .flags_done
        move.b  #1,0(a5,d4.w)
        lea     1(a3),a5
        cmpa.l  a2,a5
        bhs     .flags_done
        move.b  (a5),d1
        cmpi.b  #'0',d1
        blo     .flags_done
        cmpi.b  #'9',d1
        bhi     .flags_done
        subi.b  #'0',d1
        addq.b  #1,d1
        move.b  d1,0(a6,d4.w)
.flags_done

        move.b  #$7C,0(a1)                      ; 0002A273's "|g  "
        move.b  #'g',1(a1)
        move.b  #' ',2(a1)
        move.b  #' ',3(a1)
        lea     4(a1),a5

        move.w  d0,d1
        subq.w  #1,d1
        bmi     .copied
.copy
        move.b  (a4)+,(a5)+
        dbra    d1,.copy
.copied
        ; 0002A28A pads what is left of the row and terminates it, so a short
        ; title does not leave the previous row's tail behind it.
        lea     SCR_MISSION_STRIDE-1(a1),a6
        cmpa.l  a6,a5
        bhs.s   .padded                         ; 0002A286/0002A288: nothing to pad,
.pad                                            ; and then no terminator either
        move.b  #$FC,(a5)+
        cmpa.l  a6,a5
        blo     .pad
        clr.b   (a6)
.padded

        ; 0002A25C keeps the first byte after the brace for the briefing.
        lea     screen_mission_desc,a5
        move.w  d4,d1
        lsl.w   #2,d1
        move.l  a3,0(a5,d1.w)
        lea     SCR_MISSION_STRIDE(a1),a1
        addq.w  #1,d4                           ; 0002A263
        move.l  a3,a0                           ; 0002A26A: scan on from here
        dbra    d5,.entry
.done
        movem.l (sp)+,d0-d7/a0-a6
        rts

; One frame of the list menu. Draws the screen and consumes one input edge.
;
; Out: d0 = nonzero while the menu owns the machine.
; DOS: flat 00027DCD-00027FBF, the redraw/key loop.
; DOS symbol: loc_00027DCD
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: one pass of that loop per completed frame, with the same key set.
; Preserved: selection wrap, the 0xFA row counter, and the Return/Escape exits.
; Kind: translated.
; Status: partial; Tab and the pointer are not ported.
screen_frame
        tst.w   screen_active
        bne     .active
        moveq   #0,d0
        rts
.active
        movem.l d1-d7/a0-a6,-(sp)

        ; Poll here. The menu owns the machine, so neither attract_frame nor
        ; game_tick runs, and those are the only other callers of input_poll -
        ; without this the event word is whatever attract left in it and no key
        ; ever reaches the selection.
        bsr     input_poll

        move.l  work_screen,a1
        bsr     screen_draw
        bsr     screen_input

        movem.l (sp)+,d1-d7/a0-a6
        move.w  screen_active,d0
        rts

; Draw the box and every line of the section, counting selectable rows the way
; 00027E13 does. a1 = surface.
; DOS: flat 00027DCD-00027E8B, list-menu redraw and row count.
; DOS symbol: loc_00027DCD
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: paints one Falcon back buffer using the authored text block and menu
;       geometry; the outer blocking loop is VBL-scheduled by main.s.
; Preserved: section walk, row count, highlight position and selection clamp.
; Kind: adapted - cooperative frame scheduling replaces DOS blocking redraw.
; Status: partial; unrecovered list item screens remain inert.
screen_draw
        movem.l d0-d7/a0-a6,-(sp)

        ; Lay the background down first, every frame. The buffers alternate and
        ; the highlight moves, so painting it once at entry would leave the old
        ; selection bar behind on whichever buffer is not being drawn into.
        jsr     attract_pan_clear
        moveq   #0,d0
        move.w  #4,attract_blit_x     ; CRTC start = page + 1 byte
        jsr     attract_pan_blit
        clr.w   attract_blit_x

        ; Credits is the image and nothing over it.
        cmpi.w  #SCR_ID_CREDITS,screen_id
        beq     .drawn
        cmpi.w  #SCR_ID_DEBRIEF,screen_id
        beq     .debrief
        cmpi.w  #SCR_ID_LOCKED,screen_id
        beq     .locked
        cmpi.w  #SCR_ID_BRIEFING,screen_id
        beq     .briefing
        cmpi.w  #SCR_ID_STATS,screen_id
        beq     .stats
        cmpi.w  #SCR_ID_NAME,screen_id
        beq     .name

        move.l  a1,a0
        move.w  #SCR_BOX_X,d0
        move.w  #SCR_BOX_Y,d1
        move.w  #SCR_BOX_W,d2
        move.w  #SCR_BOX_H,d3
        bsr     menu_box

        move.l  screen_base,a2
        move.w  #SCR_BOX_Y+SCR_TEXT_DY,d6       ; pen Y

        ; The count seed, and the two 00027E29 takes off it in the sub-mode.
        move.b  #SCR_SEED,d7
        tst.w   screen_pilot_mode
        beq     .seeded
        subq.b  #SCR_PILOT_ROWS,d7
.seeded
        ; The line the highlight marks: 00027DF7's 3 rows past the box top,
        ; plus the 2 more 00027E23 adds in the sub-mode, plus the selection.
        move.w  #SCR_ITEM_LINE0,d4
        tst.w   screen_pilot_mode
        beq     .line0_ok
        addq.w  #SCR_PILOT_ROWS,d4
.line0_ok
        add.w   screen_sel,d4                   ; the marked line
        moveq   #0,d5                           ; the line being drawn
.line
        move.b  (a2),d0
        cmpi.b  #$FF,d0
        beq     .done

        addq.b  #1,d7                           ; 00027E73, after the draw
        cmp.w   d4,d5
        bne     .no_highlight
        ; 00026FD9: twelve rows of the highlight colour [00025DB8], three
        ; pixels of the first byte (planes 1-3), fifty whole bytes and two
        ; pixels of the last - 205 pixels from one in from the box edge, with no
        ; bevel and no shadow, from the cell's top two rows above its text.
        move.l  a1,a0
        move.w  #SCR_BOX_X+1,d0
        move.w  d6,d1
        subq.w  #2,d1
        move.w  #COL_MENU_GREY_L,d2
        move.w  #SCR_HILITE_W,d3
        move.w  d4,-(sp)                        ; the marked line, kept
        moveq   #SCR_ROW_H,d4
        bsr     menu_fill
        move.w  (sp)+,d4
.no_highlight
        move.l  a2,a0
        move.w  #SCR_BOX_X+SCR_TEXT_DX,d0
        move.w  d6,d1
        moveq   #0,d2
        bsr     menu_text_draw

        add.w   #SCR_ROW_H,d6
        addq.w  #1,d5

        ; Advance past this line's terminator to the next one.
.advance
        move.b  (a2)+,d0
        beq     .line
        cmpi.b  #$FF,d0
        bne     .advance
        subq.l  #1,a2                           ; leave the 0xFF for .line
        bra     .line
.done
        ; 00027E81 tests for the terminator AFTER drawing and counting a line,
        ; so the line carrying the 0xFF is counted too. This loop tests before
        ; drawing, so it owes that one count - without it the main menu reports
        ; six items where 00028D8B dispatches seven.
        addq.b  #1,d7

        ; 00027E8B clamps the selection against the count the loop just built.
        move.b  d7,screen_count+1
        move.w  screen_count,d0
        move.w  screen_sel,d1
        cmp.w   d0,d1
        blo     .sel_ok
        clr.w   screen_sel
.sel_ok
.drawn
        movem.l (sp)+,d0-d7/a0-a6
        rts

        ; 00028A4E-00028A8A: the box, then the score screen a line at a time -
        ; 00027034 per line, the pen down 0x3D8 (twelve rows) each - from the
        ; text 00028261 patched, to the 0xFF that closes it.
.debrief
        move.l  a1,a0
        move.w  #DEBRIEF_BOX_X,d0
        move.w  #DEBRIEF_BOX_Y,d1
        move.w  #DEBRIEF_BOX_W,d2
        move.w  #DEBRIEF_BOX_H,d3
        bsr     menu_box
        lea     debrief_buf+DB_SCREEN_OFFSET,a2
        move.w  #DEBRIEF_TEXT_Y,d6
        move.w  #COL_MENU_GREEN,menu_ink        ; 00028A72 mov bh,[0002A37A]
        move.w  #1,menu_ink_carry
.debrief_line
        cmpi.b  #$FF,(a2)
        bne.s   .debrief_text
        clr.w   menu_ink_carry
        bra     .drawn
.debrief_text
        move.l  a2,a0
        move.w  #DEBRIEF_TEXT_X,d0
        move.w  d6,d1
        moveq   #0,d2
        bsr     menu_text_draw
        add.w   #SCR_ROW_H,d6
.debrief_advance
        tst.b   (a2)+
        bne     .debrief_advance
        bra     .debrief_line

        ; 00028042-00028074: the box, the prompt and the name with its cursor.
.name
        ; 00028032: the cursor is a '_' in the buffer, and the byte after it is
        ; blanked, so a backspace shows no stale letter.
        lea     name_text+NAME_BUF_OFFSET,a2
        move.w  name_cursor,d0
        move.b  #'_',0(a2,d0.w)
        move.b  #$FC,1(a2,d0.w)
        move.l  a1,a0
        move.w  #NAME_BOX_X,d0
        move.w  #NAME_BOX_Y,d1
        move.w  #NAME_BOX_W,d2
        move.w  #NAME_BOX_H,d3
        bsr     menu_box
        lea     name_text,a0
        move.w  #NAME_TEXT_X,d0
        move.w  #NAME_TEXT_Y,d1
        moveq   #0,d2
        bsr     menu_text_draw
        bra     .drawn

        ; 00028B55-00028C04: the box and the patched template a line a pass.
.stats
        move.l  a1,a0
        move.w  #STATS_BOX_X,d0
        move.w  #STATS_BOX_Y,d1
        move.w  #STATS_BOX_W,d2
        move.w  #STATS_BOX_H,d3
        bsr     menu_box
        lea     stats_buf,a2
        move.w  #STATS_TEXT_Y,d6
        move.w  #COL_MENU_GREEN,menu_ink        ; 00028BEC mov bh,[0002A37A]
        move.w  #1,menu_ink_carry
.stats_line
        cmpi.b  #$FF,(a2)
        beq.s   .stats_done
        move.l  a2,a0
        move.w  #STATS_TEXT_X,d0
        move.w  d6,d1
        moveq   #0,d2
        bsr     menu_text_draw
        add.w   #SCR_ROW_H,d6
.stats_advance
        move.b  (a2)+,d0
        beq     .stats_line
        cmpi.b  #$FF,d0
        bne     .stats_advance
        subq.l  #1,a2
        bra     .stats_line
.stats_done
        clr.w   menu_ink_carry
        bra     .drawn

        ; 00026EAC-00026EDA: a box and one line, over the bare picture.
.locked
        move.l  a1,a0
        move.w  #LOCK_BOX_X,d0
        move.w  #LOCK_BOX_Y,d1
        move.w  #LOCK_BOX_W,d2
        move.w  #LOCK_BOX_H,d3
        bsr     menu_box
        lea     menu_lock_text,a0
        move.w  #LOCK_TEXT_X,d0
        move.w  #LOCK_TEXT_Y,d1
        moveq   #0,d2
        bsr     menu_text_draw
        bra     .drawn

        ; 00029394-00029514. Once the accept line has been chosen, 000294C8
        ; restores the picture and draws the loading box where the briefing
        ; was.
.briefing
        tst.w   briefing_loading
        beq.s   .briefing_page
        move.l  a1,a0
        move.w  #LOAD_BOX_X,d0
        move.w  #LOAD_BOX_Y,d1
        move.w  #LOAD_BOX_W,d2
        move.w  #LOAD_BOX_H,d3
        bsr     menu_box
        lea     menu_screen_text+BRIEF_LOAD_TEXT,a0
        move.w  #LOAD_TEXT_X,d0
        move.w  #LOAD_TEXT_Y,d1
        moveq   #0,d2
        bsr     menu_text_draw
        bra     .drawn
.briefing_page
        ; 00029515: the box, then the text lines 00029543 walks from 0002FB14
        ; with the colour [0002A37A] and each line's own markup carried on
        ; into the next, to the 0xFF the builder closed it with.
        move.l  a1,a0
        move.w  #DEBRIEF_BOX_X,d0
        move.w  #DEBRIEF_BOX_Y,d1
        move.w  #DEBRIEF_BOX_W,d2
        move.w  #DEBRIEF_BOX_H,d3
        bsr     menu_box
        lea     briefing_buf,a2
        move.w  #BRIEF_TEXT_Y,d6
        move.w  #COL_MENU_GREEN,menu_ink
        move.w  #1,menu_ink_carry
.brief_line
        cmpi.b  #$FF,(a2)
        beq.s   .brief_text_done
        move.l  a2,a0
        move.w  #BRIEF_TEXT_X,d0
        move.w  d6,d1
        moveq   #0,d2
        bsr     menu_text_draw
        add.w   #SCR_ROW_H,d6
.brief_advance
        move.b  (a2)+,d0
        beq     .brief_line
        cmpi.b  #$FF,d0
        bne     .brief_advance
        subq.l  #1,a2                           ; leave the 0xFF for .brief_line
        bra     .brief_line
.brief_text_done
        clr.w   menu_ink_carry

        ; 000293A8-000293E5: the button box and the flat highlight 00026FD9
        ; fills under the chosen line, a pitch of twelve rows a line.
        move.l  a1,a0
        move.w  #BRIEF_BTN_X,d0
        move.w  #BRIEF_BTN_Y,d1
        move.w  #BRIEF_BTN_W,d2
        move.w  #BRIEF_BTN_H,d3
        bsr     menu_box
        move.w  screen_sel,d1
        mulu    #SCR_ROW_H,d1
        add.w   #BRIEF_HILITE_Y,d1
        move.l  a1,a0
        move.w  #BRIEF_BTN_X+1,d0
        move.w  #COL_MENU_GREY_L,d2
        move.w  #BRIEF_HILITE_W,d3
        moveq   #SCR_ROW_H,d4
        bsr     menu_fill

        ; 000293EA-0002941B: the two lines, 0x3D8 apart.
        lea     menu_screen_text+BRIEF_BTN_TEXT,a2
        move.w  #BRIEF_BTN_TY,d6
.brief_btn
        cmpi.b  #$FF,(a2)
        beq     .drawn
        move.l  a2,a0
        move.w  #BRIEF_BTN_TX,d0
        move.w  d6,d1
        moveq   #0,d2
        bsr     menu_text_draw
        add.w   #SCR_ROW_H,d6
.brief_btn_advance
        move.b  (a2)+,d0
        beq     .brief_btn
        cmpi.b  #$FF,d0
        bne     .brief_btn_advance
        subq.l  #1,a2
        bra     .brief_btn

; One input edge. Up/left step back, down/right step on, both wrapping the way
; 00027ED2 and 00027EF4 do; Return selects; Escape backs out.
; DOS: flat 00027ED2-00027FBF, list-menu key dispatch.
; DOS symbol: loc_00027ED2
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: consumes the Falcon-normalized input event word once per frame.
; Preserved: navigation direction, wrapping, Return dispatch and Escape chain.
; Kind: adapted - IKBD event boundary replaces the PC FIFO.
; Status: partial; pointer/Tab/Del branches remain unrecovered.
screen_input
        movem.l d0-d2/a0,-(sp)
        move.w  input_events,d2

        ; 00027EAD / 00027EC1: Space and an unshifted Tab step on, a shifted
        ; Tab steps back - the same moves as Down and Up, so they are folded
        ; into those two event bits. The latch is the make code the key
        ; interrupt left (00001BA0); reading it is consuming it.
        lea     key_latch,a0
        tst.b   KEY_SPACE(a0)
        beq.s   .no_space
        clr.b   KEY_SPACE(a0)
        bset    #3,d2
.no_space
        tst.b   KEY_TAB(a0)
        beq.s   .no_tab
        clr.b   KEY_TAB(a0)
        lea     key_state,a0
        move.b  KEY_SHIFT_L(a0),d0
        and.b   KEY_SHIFT_R(a0),d0              ; 00027EB4-00027EB9
        bmi.s   .tab_next
        bset    #2,d2                           ; a shift is down: back
        bra.s   .no_tab
.tab_next
        bset    #3,d2
.no_tab

        ; 00028A91-00028AB0: the debrief waits for Escape, [0001B70] = 1, and
        ; goes back to the menu, 00005AE3.
        cmpi.w  #SCR_ID_DEBRIEF,screen_id
        bne     .not_debrief
        btst    #14,d2
        beq     .out
        moveq   #SCR_ID_MAIN,d0
        bsr     screen_enter
        bra     .out
.not_debrief
        ; 00028DEB waits on any key and 00028DF9 returns to the menu.
        cmpi.w  #SCR_ID_CREDITS,screen_id
        bne     .list_keys
        tst.w   d2
        beq     .out
        moveq   #SCR_ID_MAIN,d0
        bsr     screen_enter
        bra     .out
.list_keys
        cmpi.w  #SCR_ID_NAME,screen_id
        beq     .name_input
        cmpi.w  #SCR_ID_STATS,screen_id
        beq     .locked_to_main
        cmpi.w  #SCR_ID_LOCKED,screen_id
        beq     .locked_input
        cmpi.w  #SCR_ID_BRIEFING,screen_id
        beq     .briefing_input

        ; 00027F1E-00027F35: Delete on the pilot list opens the name entry for
        ; the marked slot, whoever is in it.
        cmpi.w  #SCR_ID_PILOT,screen_id
        bne.s   .not_delete
        lea     key_latch,a0
        tst.b   KEY_DELETE(a0)
        beq.s   .not_delete
        clr.b   KEY_DELETE(a0)
        move.w  screen_sel,d0
        bsr     name_enter
        bra     .out
.not_delete
        move.w  screen_count,d0
        beq     .out                            ; nothing countable yet

        btst    #2,d2                           ; up
        bne     .prev
        btst    #0,d2                           ; left
        bne     .prev
        btst    #3,d2                           ; down
        bne     .next
        btst    #1,d2                           ; right
        bne     .next
        bra     .keys
.prev
        subq.w  #1,screen_sel
        bpl     .out
        move.w  d0,screen_sel
        subq.w  #1,screen_sel
        bra     .out
.next
        addq.w  #1,screen_sel
        move.w  screen_sel,d1
        cmp.w   d0,d1
        blo     .out
        clr.w   screen_sel
        bra     .out
.keys
        btst    #13,d2                          ; Return
        bne     .select
        btst    #14,d2                          ; Escape
        beq     .out

        ; 00027F58 reads [00027DAC] and backs out one screen: id 1 returns to
        ; 00028D1E, the main operations menu, and id 2 returns to 00028F05,
        ; campaign select. Id 0 is not an exit at all - it falls into 00025DEF,
        ; the options bar - so Escape on the main menu does nothing here rather
        ; than inventing a way out of the menu the original does not have.
        move.w  screen_id,d0
        beq     .out
        subq.w  #1,d0
        bsr     screen_enter
        bra     .out

.select
        move.w  screen_id,d1
        beq     .main_ops
        cmpi.w  #SCR_ID_CAMPAIGN,d1
        beq     .campaign_chosen
        cmpi.w  #SCR_ID_MISSION,d1
        beq     .mission_chosen
        cmpi.w  #SCR_ID_PILOT,d1
        beq     .pilot_chosen
        bra     .out

.pilot_chosen
        ; 00027F8A-00027FB3: a slot whose name begins with a space is empty,
        ; and Return on it opens the name entry instead of choosing it.
        lea     roster_buffer,a0
        move.w  screen_sel,d0
        mulu.w  #ROSTER_STRIDE,d0
        cmpi.b  #' ',ROSTER_NAME(a0,d0.w)
        bne.s   .pilot_real
        move.w  screen_sel,d0
        bsr     name_enter
        bra     .out
.pilot_real
        ; 00028240 stores the driver's returned index as the selected pilot and
        ; 00028DA4 goes straight back to the main menu, which redraws with that
        ; pilot's name in its header.
        bsr     screen_roster_set_pilot
        moveq   #SCR_ID_MAIN,d0
        bsr     screen_enter
        bra     .out

.main_ops
        move.w  screen_sel,d1
        cmpi.w  #SCR_BEGIN_MISSION,d1
        beq     .begin
        cmpi.w  #SCR_EXIT,d1
        beq     .exit
        cmpi.w  #SCR_DEMO,d1
        beq     .demo
        cmpi.w  #SCR_CHOOSE_PILOT,d1
        beq     .choose_pilot
        cmpi.w  #SCR_CREDITS,d1
        beq     .credits
        cmpi.w  #SCR_STATS,d1
        beq     .stats_chosen
        cmpi.w  #SCR_OVERVIEW,d1
        beq     .overview
        bra     .out
.stats_chosen
        moveq   #SCR_ID_STATS,d0
        bsr     screen_enter
        bra     .out
.overview
        ; 00028DFE: the side screen's animation, until a key.
        clr.w   screen_active
        jsr     attract_overview
        bra     .out
.choose_pilot
        ; 00028D9F calls 00028216, which points the driver at the roster.
        moveq   #SCR_ID_PILOT,d0
        bsr     screen_enter
        bra     .out
.credits
        ; 00028DB5 shows credit1.dta until a key.
        moveq   #SCR_ID_CREDITS,d0
        bsr     screen_enter
        bra     .out
.begin
        ; 00028D8B's al=0 loads MISSION.DTA and falls into campaign select at
        ; 00028F05 - it does not start flying. The port follows that chain now
        ; rather than short-cutting to the mission it parsed at startup.
        moveq   #SCR_ID_CAMPAIGN,d0
        bsr     screen_enter
        bra     .out
.campaign_chosen
        ; 00028F2F stores the chosen campaign back into the pilot's roster slot.
        ; That store is ported; what is not is 00027D92's write of the roster
        ; back to COMANCHE.NAM, so the choice survives the session and not the
        ; program. 00028F3A's per-pilot mission list is also still unported, so
        ; the mission screen is entered directly.
        move.w  screen_sel,screen_campaign
        bsr     screen_roster_set_campaign
        moveq   #SCR_ID_MISSION,d0
        bsr     screen_enter
        bra     .out
.mission_chosen
        ; 00028FE6-00029010 records the row as the pilot's progress and the
        ; mission chosen last, and 00029016 turns a row drawn in orange away
        ; with 00026E90's message instead of going on.
        move.w  screen_sel,d0
        jsr     roster_select_mission           ; 00028FE6-00029010
        move.w  screen_sel,briefing_mission
        lea     screen_mission_ink,a0
        move.w  briefing_mission,d0
        cmpi.b  #'o',0(a0,d0.w)                 ; 00029016
        bne.s   .not_locked
        moveq   #SCR_ID_LOCKED,d0
        bsr     screen_enter
        bra     .out
.not_locked
        ; 00029038-00029359 composes the briefing, and 0002936C shows it.
        bsr     briefing_build
        clr.w   briefing_loading
        moveq   #SCR_ID_BRIEFING,d0
        bsr     screen_enter
        bra     .out

        ; 0002807E-00028129: one key a pass from the queue, newest first.
.name_input
        move.l  key_queue,d0
        move.l  d0,d1
        lsr.l   #8,d0
        move.l  d0,key_queue                    ; 0002808A shr [1b70], 8
        andi.w  #$FF,d1                         ; bl
        beq     .out
        cmpi.b  #1,d1                           ; Esc leaves the list as it was
        beq     .name_cancel
        cmpi.b  #$1C,d1
        beq     .name_accept
        cmpi.b  #$0E,d1
        bne.s   .name_char
        tst.w   name_cursor                     ; 000280AD
        beq     .out
        subq.w  #1,name_cursor
        bra     .out
.name_char
        lea     name_plain_keys,a0              ; 000280C4 [ebx + 000019E9]
        move.b  0(a0,d1.w),d2
        beq     .out
        lea     key_state,a0                    ; 000280CE-000280E2
        move.b  KEY_SHIFT_L(a0),d0
        and.b   KEY_SHIFT_R(a0),d0
        bmi.s   .name_plain
        lea     name_shift_keys,a0
        move.b  0(a0,d1.w),d2
.name_plain
        lea     name_text+NAME_BUF_OFFSET,a0
        move.w  name_cursor,d0
        move.b  d2,0(a0,d0.w)                   ; 000280E9
        cmpi.w  #NAME_MAX,d0                    ; 000280EF
        bhs     .out
        ; 000280FC-0002811D: the characters so far, by the font's widths.
        moveq   #0,d3
        move.w  d0,d4
        lea     menu_font_width,a2
.name_width
        moveq   #0,d2
        move.b  (a0)+,d2
        moveq   #0,d5
        move.b  0(a2,d2.w),d5
        add.l   d5,d3
        dbra    d4,.name_width
        cmpi.l  #NAME_WIDTH_MAX,d3
        bhs     .out
        addq.w  #1,name_cursor                  ; 00028123
        bra     .out
.name_accept
        move.w  name_cursor,d0                  ; 0002812E
        beq.s   .name_cancel
        lea     name_text+NAME_BUF_OFFSET,a0
        move.b  #$FC,0(a0,d0.w)
        bsr     name_create
.name_cancel
        ; 0002820B-00028215: the picture restored, back to the pilot list at
        ; the slot [00027DAA] names - which the sort has moved if it ran.
        moveq   #SCR_ID_PILOT,d0
        bsr     screen_enter
        moveq   #0,d0
        move.b  debrief_pilot,d0
        move.w  d0,screen_sel
        bra     .out

        ; 00028C12-00028C20: any key, and the main menu again.
.locked_to_main
        tst.w   d2
        beq     .out
        moveq   #SCR_ID_MAIN,d0
        bsr     screen_enter
        bra     .out

        ; 00026EEF-00026F12: any key closes the message, and 00028F3F draws
        ; the list again.
.locked_input
        tst.w   d2
        beq     .out
        moveq   #SCR_ID_MISSION,d0
        bsr     screen_enter
        bra     .out

        ; 00029422-000294D2.
.briefing_input
        move.w  briefing_loading,d0
        beq.s   .brief_keys
        ; The loading box is on the published frame by the time the second of
        ; these runs; the load itself takes the time of many.
        cmpi.w  #2,d0
        beq.s   .brief_go
        move.w  #2,briefing_loading
        bra     .out
.brief_go
        clr.w   briefing_loading
        bsr     screen_mission_start
        bra     .out
.brief_keys
        btst    #2,d2                           ; up
        bne.s   .brief_prev
        btst    #0,d2                           ; left
        bne.s   .brief_prev
        btst    #3,d2                           ; down
        bne.s   .brief_next
        btst    #1,d2                           ; right
        bne.s   .brief_next
        btst    #14,d2                          ; Escape: 00029496-000294A2
        bne.s   .brief_back
        btst    #13,d2                          ; Return: 000294A7
        beq     .out
        cmpi.w  #1,screen_sel                   ; 000294B0
        beq.s   .brief_back
        move.w  #1,briefing_loading             ; 000294C8
        bra     .out
.brief_prev
        ; 00029450: dec, and a step off the top lands on the last line.
        subq.w  #1,screen_sel
        bpl     .out
        move.w  #1,screen_sel
        bra     .out
.brief_next
        ; 0002946D: inc, and a step off the bottom lands on the first.
        addq.w  #1,screen_sel
        cmpi.w  #2,screen_sel
        blo     .out
        clr.w   screen_sel
        bra     .out
.brief_back
        moveq   #SCR_ID_MISSION,d0
        bsr     screen_enter
        bra     .out
.demo
        ; 00028ECA zeroes the pass counter and jumps back to 00005690, which
        ; increments it again - so Demo always lands on pass 1, never on the
        ; pass the cycle had reached.
        clr.w   screen_active
        jsr     attract_restart
        bra     .out
.exit
        clr.w   screen_active
        move.w  #1,exit_requested
.out
        movem.l (sp)+,d0-d2/a0
        rts

; The accepted mission, started: 00029038's N.MIS patch and load, and
; 00005B33's resources before the frame loop runs. Both halves matter:
; selecting the record only sets the family and sky numbers, and without the
; loads behind them the player flies whatever map the attract happened to
; leave staged - which is how this first came out on the attract's night
; terrain regardless of the choice.
; In: briefing_mission = the row chosen.
; DOS: flat 00029038-00029359 and 00005B33.
; DOS symbol: inside loc_00028F3F
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same loads in the same order; a failed one leaves the briefing up.
; Preserved: parse, family, sky, objects, loadout.
; Kind: translated.
; Status: ported.
screen_mission_start
        movem.l d0-d7/a0-a6,-(sp)
        moveq   #0,d0
        jsr     snd_mode                        ; 00005B35: the mixer off once the menu returns
        move.w  briefing_mission,d0
        bsr     mission_select
        move.w  mission_status,d0
        btst    #1,d0                           ; MISSION_STATUS_ERROR
        bne     .fail
        btst    #2,d0                           ; MISSION_STATUS_PARSED
        beq     .fail

        move.w  mission_map_family,d0
        bsr     resources_select_family
        tst.w   resource_map_status
        bne     .fail
        move.w  mission_sky_number,d0
        beq     .fail
        bsr     sky_select_family
        tst.w   sky_status
        bne     .fail

        ; DOS 00005B33 has installed the selected mission resource block before
        ; 00006895 spawns its objects. Decode the ten authored SG slots at the
        ; same boundary; object_spawn_mission consumes f2/f3, never TANK as a
        ; universal fallback.
        bsr     sprite_mission_load
        bsr     weapon_banks_load               ; 000066E2-000067AE
        jsr     flight_mission_sound_load       ; 0000688B, 000064A8, 0000681D, 00006859
        bsr     object_init
        bsr     object_spawn_mission
        clr.w   screen_active
        bsr     game_init
        jsr     flight_mission_sound_start      ; 000069DB-00006A0E
    ifne USE_DSP
        ; 00005B33 enters the selected mission only after its D/C/SKY
        ; resources are installed. Rebind the Falcon DSP scene cache at that
        ; same boundary; dsp_init is idempotent after the kernel load and does
        ; not change the DOS-visible mission behaviour.
        bsr     dsp_init
        tst.l   d0
        bne     .fail
    endc
        move.w  #2,surface_reseed
        bra     .leave
.fail
.leave
        movem.l (sp)+,d0-d7/a0-a6
        rts

; The mission list's row colours, 00028F46-00028FBA, and the selection the
; list opens on, 00028FBA-00028FE1.
; A row is blue once its mission has been flown, green while it is the next
; one, and orange while it is starred and the missions before it have not all
; been flown: [ebx + 00029F18] is the star from 0002A256 and the number of
; flown rows so far is what the row is compared with. The colour letter goes
; into the row's own markup and into the array 00029016 tests. The list opens
; on the mission that pilot chose last, [0002970A + 10 * pilot + digit].
; DOS: flat 00028F46-00028FE1.
; DOS symbol: inside loc_00028F3F
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same walk over the pilot's hundred mission flags.
; Preserved: the three colours, the edx/ebx compare, the end-of-rows exit.
; Kind: translated.
; Status: ported.
screen_mission_colours
        movem.l d0-d7/a0-a5,-(sp)
        jsr     pilot_locate                    ; d4 = pilot, d5 = digit, a5 = roster
        move.w  d4,d0
        mulu.w  #100,d0                         ; 00028F75
        move.w  d5,d1
        mulu.w  #10,d1                          ; 00028F6C
        add.w   d1,d0
        lea     ROSTER_MISSIONS(a5,d0.w),a0     ; 00028F79 esi
        lea     menu_screen_text+SCR_MISSION_ROW0+1,a1  ; 00028F80 edi
        lea     screen_mission_star,a2
        lea     screen_mission_ink,a3
        moveq   #0,d3                           ; ebx
        moveq   #0,d2                           ; edx
        moveq   #SCR_MISSION_MAX-1,d7
.row
        move.b  (a0)+,d0                        ; 00028F8E
        moveq   #'g',d1                         ; 00028F8F
        cmp.w   d2,d3
        beq.s   .reached
        tst.b   0(a2,d3.w)                      ; 00028F95
        beq.s   .reached
        moveq   #'o',d1                         ; 00028F9E
.reached
        tst.b   d0
        beq.s   .not_flown
        moveq   #'b',d1                         ; 00028FA4
        addq.w  #1,d2                           ; 00028FA6
.not_flown
        tst.b   (a1)                            ; 00028FA7
        beq.s   .rows_done
        move.b  d1,(a1)                         ; 00028FAC
        move.b  d1,0(a3,d3.w)                   ; 00028FAE
        lea     SCR_MISSION_STRIDE(a1),a1       ; 00028FB4
        addq.w  #1,d3
        dbra    d7,.row
.rows_done
        move.w  d4,d0
        mulu.w  #10,d0                          ; 00028FD2
        add.w   d5,d0                           ; 00028FD9
        moveq   #0,d1
        move.b  ROSTER_PROGRESS(a5,d0.w),d1     ; 00028FDB
        move.w  d1,screen_sel
        movem.l (sp)+,d0-d7/a0-a5
        rts

; The new pilot's name box, 0002800C-0002802B: the buffer blank, the cursor at
; its start, and the queue's newest key dropped as 0002800C's `mov [1b70], 0`
; does - here the whole queue, because the port's menus read their keys from
; the event word and nothing else drains it the way 00027DD2's redraw does.
; In: d0 = the pilot slot.
; DOS: flat 0002800C-0002802B.
; DOS symbol: sub_0002800C
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same set-up; the loop is screen_input's name entry.
; Preserved: the 0xFC blank buffer and the zero cursor.
; Kind: translated.
; Status: ported.
name_enter
        movem.l d0-d2/a0-a1,-(sp)
        move.b  d0,debrief_pilot                ; [00027DAA]
        clr.l   key_queue
        clr.w   name_cursor
        lea     name_prompt_text,a0
        lea     name_text,a1
        move.w  #NAME_BUF_OFFSET+NAME_BUF_BYTES+1-1,d0
.copy
        move.b  (a0)+,(a1)+
        dbra    d0,.copy
        lea     name_text+NAME_BUF_OFFSET,a1
        moveq   #NAME_BUF_BYTES-1,d0
.blank
        move.b  #$FC,(a1)+
        dbra    d0,.blank
        moveq   #SCR_ID_NAME,d0
        bsr     screen_enter
        movem.l (sp)+,d0-d2/a0-a1
        rts

; The new pilot: 00028145-000281FE. The slot's progress, completion, counts,
; campaign and mission flags are cleared, the record becomes the head, the
; name and the tail, the roster is ranked (which may move the slot) and written.
; In: name_text holds the name; debrief_pilot = the slot.
; DOS: flat 00028145-000281F9.
; DOS symbol: inside loc_0002812E
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same stores, then roster_sort and roster_save.
; Preserved: the order and every length (10, 10, 4x3, 9+22+12, 100).
; Kind: translated.
; Status: ported.
name_create
        movem.l d0-d3/a0-a2,-(sp)
        lea     roster_buffer,a2
        moveq   #0,d1
        move.b  debrief_pilot,d1                ; 00028145 [00027DAA]
        move.w  d1,d0
        mulu.w  #10,d0                          ; 0002814C
        lea     ROSTER_PROGRESS(a2,d0.w),a0
        lea     ROSTER_CAMPAIGN_DONE(a2,d0.w),a1
        moveq   #10-1,d2
.clear10
        clr.b   (a0)+                           ; 00028158
        clr.b   (a1)+                           ; 0002815F
        dbra    d2,.clear10
        move.w  d1,d0
        lsl.w   #2,d0
        clr.l   ROSTER_COUNT(a2,d0.w)           ; 00028170
        clr.l   ROSTER_SCORE(a2,d0.w)           ; 0002817B
        clr.l   ROSTER_KILLS(a2,d0.w)           ; 00028186
        clr.b   ROSTER_CAMPAIGNS(a2,d1.w)       ; 00028191
        move.w  d1,d0
        mulu.w  #ROSTER_STRIDE,d0               ; 00028198
        lea     0(a2,d0.w),a1                   ; 000281A1
        lea     name_head_text,a0
        moveq   #9-1,d2
.head
        move.b  (a0)+,(a1)+                     ; 000281B1
        dbra    d2,.head
        lea     name_text+NAME_BUF_OFFSET,a0
        moveq   #$16-1,d2
.name
        move.b  (a0)+,(a1)+                     ; 000281BD
        dbra    d2,.name
        lea     name_tail_text,a0
        moveq   #12-1,d2
.tail
        move.b  (a0)+,(a1)+                     ; 000281C9
        dbra    d2,.tail
        move.w  d1,d0
        mulu.w  #100,d0                         ; 000281D2
        lea     ROSTER_MISSIONS(a2,d0.w),a0
        moveq   #25-1,d2
.flags
        clr.l   (a0)+                           ; 000281E8
        dbra    d2,.flags
        jsr     roster_sort                     ; 000281EA
        jsr     roster_save                     ; 000281F9
        movem.l (sp)+,d0-d3/a0-a2
        rts

; The pilot's statistics screen text, 00028B3C-00028BC8: the template with the
; four placeholders blanked to 0xFC, the pilot's name copied in (0x21 bytes
; from the record's name field) and the three numbers from the roster's
; arrays - the score into eight digits, the missions won into three and the
; enemies killed into four, right-aligned as 00028C25 writes them.
; DOS: flat 00028B3C-00028BC8.
; DOS symbol: inside loc_00028B37
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same patches into stats_buf.
; Preserved: the blanking, the copy length and each number's width.
; Kind: translated.
; Status: ported.
stats_patch
        movem.l d0-d4/a0-a3,-(sp)
        lea     menu_stats_text,a0
        lea     stats_buf,a1
        move.w  #STATS_BYTES-1,d0
.copy
        move.b  (a0)+,(a1)+
        dbra    d0,.copy
        lea     stats_buf,a1
        ; 00028B3C-00028B50: [00028B02], [00028B1C], [00028AF6], [00028AFA].
        move.l  #$FCFCFCFC,d1
        move.l  d1,STATS_MISSIONS(a1)
        move.l  d1,STATS_KILLS(a1)
        move.l  d1,STATS_SCORE(a1)
        move.l  d1,STATS_SCORE+4(a1)
        lea     roster_buffer,a2
        moveq   #0,d2
        move.b  ROSTER_CURRENT(a2),d2           ; 00028B62 [00029701]
        move.w  d2,d3
        mulu.w  #ROSTER_STRIDE,d3
        lea     ROSTER_NAME(a2,d3.w),a0         ; 00028B72: 0002958B + 0x2B * pilot
        lea     STATS_NAME(a1),a3
        moveq   #$21-1,d0
.name
        move.b  (a0)+,(a3)+
        dbra    d0,.name
        lsl.w   #2,d2                           ; ebx*4
        move.l  ROSTER_SCORE(a2,d2.w),d0        ; 00028B8B [ebx*4 + 0002977C]
        bsr.s   .le
        move.l  a1,a3
        adda.w  #STATS_SCORE,a1
        moveq   #8,d1
        jsr     debrief_number
        move.l  a3,a1
        move.l  ROSTER_COUNT(a2,d2.w),d0        ; 00028BA1 [ebx*4 + 0002975C]
        bsr.s   .le
        adda.w  #STATS_MISSIONS,a1
        moveq   #3,d1
        jsr     debrief_number
        move.l  a3,a1
        move.l  ROSTER_KILLS(a2,d2.w),d0        ; 00028BB7 [ebx*4 + 0002979C]
        bsr.s   .le
        adda.w  #STATS_KILLS,a1
        moveq   #4,d1
        jsr     debrief_number
        movem.l (sp)+,d0-d4/a0-a3
        rts
.le
        ror.w   #8,d0                           ; the roster's dwords are
        swap    d0                              ; little-endian
        ror.w   #8,d0
        rts

; The briefing text, 00029063-00029119: an empty blue line, the mission's
; name, then its description wrapped to 0x118 pixels with the font's own
; widths, the whole closed by 0xFF.
; The description is the text after the mission's closing brace in the
; campaign file, from the first line past the one carrying the star
; (0002A25C kept the pointer, 000290B1 reads it, 0002A29A moves on). Runs of
; white space fold to one space, '^' ends a paragraph and '<' ends the
; description. A line that overflows is broken at the last space seen, or
; after the character that overflowed it when there was none.
; In: briefing_mission = the row.
; DOS: flat 00029078-00029119.
; DOS symbol: inside loc_00029038
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same builder into briefing_buf; the list rows give it the name.
; Preserved: the markup bytes, the 28-byte name, the fold, the 0x118 limit and
;   both break rules.
; Kind: translated.
; Status: ported.
briefing_build
        movem.l d0-d7/a0-a5,-(sp)
        lea     briefing_buf,a1                 ; 00029078 edi = 0002FB14
        move.b  #$7C,(a1)+                      ; 0002907D stosw '|b'
        move.b  #'b',(a1)+
        clr.b   (a1)+                           ; 00029085
        moveq   #0,d0
        move.w  briefing_mission,d0             ; 00029086 [0002975A]
        lsl.w   #5,d0                           ; 0002908D
        lea     menu_screen_text+SCR_MISSION_ROW0+4,a0  ; 00029092 0x29D99
        adda.w  d0,a0
        moveq   #$1C-1,d1                       ; 00029098
.name
        move.b  (a0)+,(a1)+                     ; 0002909E
        dbra    d1,.name
        clr.b   (a1)+                           ; 000290A2
        move.b  #$7C,(a1)+                      ; 000290A7 stosw '|g'
        move.b  #'g',(a1)+
        move.w  briefing_mission,d0
        lsl.w   #2,d0
        lea     screen_mission_desc,a0
        move.l  0(a0,d0.w),a0                   ; 000290B1
        bsr     briefing_skip_line              ; 000290B8
        move.l  a0,a2                           ; 000290BD esi
        moveq   #$20,d1                         ; 000290C0 ah
        moveq   #0,d2                           ; ecx, the line's width
        sub.l   a3,a3                           ; ebx, the last space seen
        sub.l   a4,a4                           ; ebp, where it was written
        lea     menu_font_width,a5
.char
        move.b  (a2)+,d0                        ; 000290C6
        cmpi.b  #'<',d0
        beq     .end
        cmpi.b  #$0A,d0
        beq     .char
        cmpi.b  #$20,d0
        bhs.s   .kept
        cmpi.b  #$20,d1                         ; 000290D3
        beq     .char
        moveq   #$20,d0                         ; 000290D8
.kept
        cmpi.b  #$20,d0                         ; 000290DA
        bne.s   .not_space
        move.l  a2,a3                           ; 000290DE
        move.l  a1,a4                           ; 000290E0
.not_space
        move.b  d0,d1                           ; 000290E2
        cmpi.b  #'^',d0
        bne.s   .store
        moveq   #0,d0                           ; 000290E8
        moveq   #$20,d1
        moveq   #0,d2
        sub.l   a3,a3
.store
        move.b  d0,(a1)+                        ; 000290F0
        moveq   #0,d3
        move.b  d0,d3
        moveq   #0,d4
        move.b  0(a5,d3.w),d4                   ; 000290F4
        add.l   d4,d2                           ; 000290FE
        cmpi.l  #BRIEF_WRAP_W,d2                ; 00029100
        bls     .char
        moveq   #0,d2                           ; 00029108
        move.l  a3,d3
        beq.s   .no_break
        move.l  a3,a2                           ; 0002910E
        move.l  a4,a1                           ; 00029110
.no_break
        sub.l   a3,a3                           ; 00029112
        clr.b   (a1)+                           ; 00029116
        bra     .char
.end
        move.b  #$FF,(a1)+                      ; 00029119
        movem.l (sp)+,d0-d7/a0-a5
        rts

; 0002A29A: on to the start of the next line that has anything on it. Finds
; the next CR in the next 0xA0 bytes, steps over a following LF, and goes round
; again while the line begins with a control byte, a blank or a ';'.
; DOS: flat 0002A29A-0002A2B7.
; DOS symbol: sub_0002A29A
; Record: analysis/functions/falcon-attract.md#attract-route
; Port: the same scan. A line with no CR in range ends the original in the
;   error exit at 00029359; this returns with the pointer where it stopped,
;   which the shipped files never reach.
; Preserved: the window, the LF step, the two skip tests.
; Kind: translated.
; Status: ported.
briefing_skip_line
        move.l  d1,-(sp)
.again
        move.w  #$A0-1,d1                       ; 0002A29B
.scan
        cmpi.b  #$0D,(a0)+                      ; 0002A2A0 repne scasb
        beq.s   .found
        dbra    d1,.scan
        bra.s   .out
.found
        cmpi.b  #$0A,(a0)                       ; 0002A2A6
        bne.s   .no_lf
        addq.l  #1,a0
.no_lf
        cmpi.b  #$20,(a0)                       ; 0002A2AC
        bls.s   .again
        cmpi.b  #';',(a0)                       ; 0002A2B1
        beq.s   .again
.out
        move.l  (sp)+,d1
        rts

        data
; Screen id to text-block base. The original does not compute this and neither
; can this port any more: it writes an ABSOLUTE base into [00027DB0] per
; screen, and those bases are
;   00028D1E  00029B32  main operations
;   00028F11  00029BEC  campaign select
;   00028F4B  00029D81  mission select
; which are these offsets into the block. This used to count 0xFF terminators
; to reach the same places - correct while the block was the image's, wrong the
; moment screen_fill_campaigns runs, because 0002A17E plants an 0xFF of its own
; one row past the last campaign found. Two installed campaigns end the
; campaign screen seven rows early, and every screen after it in the count
; moves: mission select would have landed on the leftover fill rows. A walk
; over a block the program writes into is a walk over a moving target, and the
; original never took one.
;
; Three entries and three screens: pilot select is pointed at the roster and
; Credits is turned away before this is read, so there is no id that indexes
; past the end of it.
screen_base_map
        dc.w    $006,$0C0,$255

; 00028D00 and 00028EE5, inline after their loader calls.
name_rah66_menu
        dc.b    "RAH66.DTA",0
        even
name_mission_dta
        dc.b    "MISSION.DTA",0
        even
; 000288C3 and 000289FA, inline after their loader calls.
name_lose3
        dc.b    "LOSE3.DTA",0
        even
name_win3
        dc.b    "WIN3.DTA",0
        even
; 00028DBF, inline after its loader call.
name_credits
        dc.b    "CREDIT1.DTA",0
        even
; 00005604, inline after its loader call.
name_roster
        dc.b    "COMANCHE.NAM",0
        even

        bss
        even
screen_active
        ds.w    1
screen_id
        ds.w    1
screen_sel
        ds.w    1
screen_count
        ds.w    1
screen_base
        ds.l    1
; The campaign the player chose. Superseded: 00028F2F keeps this per pilot in
; the roster at [00029702], which screen_roster_set_campaign now writes. This
; word is the pre-roster session copy - still stored at .campaign_chosen, read
; by nothing.
screen_campaign
        ds.w    1
; [00027DAD], the pilot sub-mode: 1 on the main operations screen only.
screen_pilot_mode
        ds.w    1
; [0002A100] at the end of the catalog walk: how many of the ten mission files
; are installed, and therefore how far the digit table and the campaign rows
; are filled.
screen_campaign_count
        ds.w    1
        even
; [00029F18] and [00029F2C], one byte per mission row: whether the entry is
; gated behind the one before it, and the digit that followed its star plus
; one. 00028F95 reads the first to colour the row.
screen_mission_star
        ds.b    SCR_MISSION_MAX
screen_mission_next
        ds.b    SCR_MISSION_MAX
        even
; [00029F22]: the colour letter each row was drawn in.
screen_mission_ink
        ds.b    SCR_MISSION_MAX
        even
; [00029EF0]: where each row's description begins in the campaign file.
screen_mission_desc
        ds.l    SCR_MISSION_MAX
; [0002975A], the row being briefed; [0002FB14], the briefing text; and the
; two-step state that puts the loading box up before the load starts.
briefing_mission
        ds.w    1
briefing_loading
        ds.w    1
briefing_buf
        ds.b    BRIEF_BUF_BYTES
        even
; The statistics screen's patched copy of the template at 00028AB5.
stats_buf
        ds.b    STATS_BYTES
        even
; The name entry's copy of the prompt and buffer at 00027FD5, and [0002800B].
name_text
        ds.b    NAME_BUF_OFFSET+NAME_BUF_BYTES+2
        even
name_cursor
        ds.w    1
; These two are ONE region and must stay adjacent and in this order. 00028231
; points the driver at 00029570 and the records it walks into begin at
; 00029582, eighteen bytes later, so the header is not a separate string - it
; is the first three lines of the same screen. Declared apart or reordered, the
; driver walks off the header into whatever the linker put next.
roster_screen
        ds.b    ROSTER_HEADER
; 00029582, the COMANCHE.NAM load target.
roster_buffer
        ds.b    ROSTER_BYTES
        even

        end
