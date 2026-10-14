; Compact 5x7 diagnostic font and HUD. The layout follows the DOS cockpit
; contract (viewport plus status readouts), while glyph artwork remains local.

        include "inc/wc1.s"

        xdef    hud_draw
        xref    put_pixel
        xref    mission_status
        xref    resource_status
        xref    resource_draw_cockpit_indicators
        xref    resource_flight_ship_shields
        xref    game_target_object
        xref    player_speed
        xref    player_fuel
        xref    player_altitude

        text

hud_draw
        btst    #2,resource_status
        bne     .cockpit

        move.w  #104,d0
        move.w  #7,d1
        move.w  #COL_WHITE,d2
        lea     title_text,a0
        bsr     draw_text

        move.w  #16,d0
        move.w  #172,d1
        move.w  #COL_GREEN,d2
        lea     speed_text,a0
        bsr     draw_text
        move.w  #112,d0
        move.w  #172,d1
        move.w  #COL_AMBER,d2
        lea     nav_text,a0
        bsr     draw_text
        move.w  #236,d0
        move.w  #172,d1
        move.w  #COL_RED,d2
        lea     target_text,a0
        bsr     draw_text
        move.w  game_target_object,d3
        bmi     .target_ready
        addi.w  #'0',d3
        move.w  #278,d0
        move.w  #172,d1
        move.w  #COL_RED,d2
        bsr     draw_char
.target_ready

        move.w  #16,d0
        move.w  #148,d1
        move.w  #COL_PANEL_EDGE,d2
        move.w  mission_status,d3
        cmpi.w  #MISSION_STATUS_DOS_RAW,d3
        beq     .dos_data
        cmpi.w  #MISSION_STATUS_DOS_LZW,d3
        beq     .dos_data
        cmpi.w  #MISSION_STATUS_COMPRESSED,d3
        beq     .compressed
        lea     fallback_text,a0
        bra     .status_ready
.dos_data
        lea     dos_data_text,a0
        bra     .status_ready
.compressed
        lea     compressed_text,a0
.status_ready
        bsr     draw_text

        btst    #0,resource_status
        beq     .done
        move.w  #16,d0
        move.w  #141,d1
        move.w  #COL_GREEN,d2
        lea     palette_text,a0
        bsr     draw_text
.done
        rts

.cockpit
        ; update_lights()/update_bars() are serviced from the retained DOS
        ; cockpit-damage packet.  Weapon energy is not yet consumed by the
        ; Falcon weapon dispatcher, so keep its source startup value at 100.
        moveq   #100,d0
        move.l  d0,-(sp)
        moveq   #0,d0
        move.w  player_fuel,d0
        move.l  d0,-(sp)
        jsr     resource_draw_cockpit_indicators
        addq.l  #8,sp
        bsr     draw_cockpit_readouts
        rts

draw_cockpit_readouts
        move.w  player_speed,d3
        mulu    #10,d3
        move.w  #201,d0
        move.w  #105,d1
        move.w  #COL_WHITE,d2
        bsr     draw_number

        move.w  player_altitude,d3
        move.w  #112,d0
        move.w  #105,d1
        move.w  #COL_WHITE,d2
        bsr     draw_number

        move.w  resource_flight_ship_shields,d3
        move.w  #99,d0
        move.w  #130,d1
        move.w  #COL_WHITE,d2
        bsr     draw_number
        move.w  resource_flight_ship_shields+2,d3
        move.w  #99,d0
        move.w  #140,d1
        move.w  #COL_WHITE,d2
        bsr     draw_number
        rts

; In: d0=x, d1=y, d2=colour, d3=unsigned short value.
draw_number
        movem.l d0-d7/a0-a2,-(sp)
        lea     number_buffer+7,a0
        clr.b   -(a0)
        moveq   #0,d4
        move.w  d3,d4
        tst.w   d4
        bne     .number_digits
        move.b  #'0',-(a0)
        bra     .number_ready
.number_digits
        moveq   #10,d5
.number_loop
        divu.w  d5,d4
        move.l  d4,d6
        swap    d6
        move.b  d6,d7
        addi.b  #'0',d7
        move.b  d7,-(a0)
        andi.l  #$0000ffff,d4
        tst.w   d4
        bne     .number_loop
.number_ready
        move.w  d0,d6
        moveq   #0,d3
.number_draw
        moveq   #0,d3
        move.b  (a0)+,d3
        beq     .number_done
        move.w  d6,d0
        bsr     draw_char
        addq.w  #6,d6
        bra     .number_draw
.number_done
        movem.l (sp)+,d0-d7/a0-a2
        rts

; In: a0 string, d0=x, d1=y, d2=colour.
draw_text
        movem.l d0-d6/a0-a2,-(sp)
        move.w  d0,d6
.next
        moveq   #0,d3
        move.b  (a0)+,d3
        beq     .done
        move.w  d6,d0
        bsr     draw_char
        addq.w  #6,d6
        bra     .next
.done
        movem.l (sp)+,d0-d6/a0-a2
        rts

; In: d0=x, d1=y, d2=colour, d3=ASCII.
draw_char
        movem.l d0-d7/a0-a2,-(sp)
        cmpi.b  #'A',d3
        bcs     .digit
        cmpi.b  #'Z',d3
        bhi     .digit
        subi.b  #'A',d3
        mulu    #5,d3
        lea     font_alpha,a1
        adda.w  d3,a1
        bra     .glyph
.digit
        cmpi.b  #'0',d3
        bcs     .blank
        cmpi.b  #'9',d3
        bhi     .blank
        subi.b  #'0',d3
        mulu    #5,d3
        lea     font_digits,a1
        adda.w  d3,a1
        bra     .glyph
.blank
        bra     .done
.glyph
        move.w  d0,d6
        moveq   #4,d7
.column
        moveq   #0,d4
        move.b  (a1)+,d4
        moveq   #6,d5
.row
        btst    d5,d4
        beq     .skip
        move.w  d6,d0
        move.w  d1,d3
        add.w   #6,d3
        sub.w   d5,d3
        move.w  d3,d1
        bsr     put_pixel
.skip
        dbra    d5,.row
        addq.w  #1,d6
        dbra    d7,.column
.done
        movem.l (sp)+,d0-d7/a0-a2
        rts

        data
title_text      dc.b    'WING COMMANDER',0
speed_text      dc.b    'SPEED',0
nav_text        dc.b    'NAV',0
target_text     dc.b    'TGT',0
fallback_text   dc.b    'FALLBACK FLIGHT',0
dos_data_text   dc.b    'DOS MISSION DATA',0
compressed_text dc.b    'PACKET TYPE UNSUPPORTED',0
palette_text    dc.b    'DOS PALETTE LOADED',0

; Each byte is one glyph column, bit 0 is the top pixel.
font_alpha
        dc.b $3e,$09,$09,$09,$3e, $3f,$25,$25,$25,$1a
        dc.b $1e,$21,$21,$21,$12, $3f,$21,$21,$12,$0c
        dc.b $3f,$25,$25,$25,$21, $3f,$05,$05,$05,$01
        dc.b $1e,$21,$29,$29,$3a, $3f,$04,$04,$04,$3f
        dc.b $00,$21,$3f,$21,$00, $10,$20,$21,$1f,$01
        dc.b $3f,$04,$0a,$11,$20, $3f,$20,$20,$20,$20
        dc.b $3f,$02,$04,$02,$3f, $3f,$02,$04,$08,$3f
        dc.b $1e,$21,$21,$21,$1e, $3f,$09,$09,$09,$06
        dc.b $1e,$21,$31,$21,$1e, $3f,$09,$19,$29,$26
        dc.b $26,$29,$29,$29,$12, $01,$01,$3f,$01,$01
        dc.b $1f,$20,$20,$20,$1f, $0f,$10,$20,$10,$0f
        dc.b $1f,$20,$1c,$20,$1f, $33,$0c,$04,$0c,$33
        dc.b $03,$04,$38,$04,$03, $31,$29,$25,$23,$21

font_digits
        dc.b $1e,$25,$29,$31,$1e, $00,$22,$3f,$20,$00
        dc.b $32,$29,$29,$29,$26, $12,$21,$25,$25,$1a
        dc.b $0c,$0a,$09,$3f,$08, $17,$25,$25,$25,$19
        dc.b $1e,$25,$25,$25,$18, $01,$01,$31,$09,$07
        dc.b $1a,$25,$25,$25,$1a, $06,$29,$29,$29,$1e

        bss
        even
number_buffer   ds.b    8

        end
