; Route: analysis/functions/falcon-attract.md#terrain-renderer.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; 68030 CPU reference renderer: y-buffer voxel terrain over the full
; 1024x1024 original Comanche map.
;
; This is the correctness oracle the DSP kernel will be diffed against, so it
; keeps the DOS ring-major walk, per-column occlusion row, and vertical spans
; on the 68030. The Falcon's 320-pixel true-colour surface keeps the DOS
; 192-column walk and presents the DOS displayed source window 16..175
; after each source column expands to two RGB565 pixels; that presentation
; mapping is the platform boundary.
;
; Fixed point: the ring marcher walks the original's own 10.22 map
; coordinates - the top ten bits are the map cell, exactly what the DOS
; shld pair extracts, and 32-bit overflow IS the map wrap. The older
; column-major experiments used 16.16; only diagnostic paths still do.

        include "inc/comanche.s"
        include "dsp/proto.inc"

; The target view's geometry, from 0001B26C and 000079F0. 0001B2AA reserves
; 0x50 = 80 bytes of occlusion, and the first half-sweep's compare is at
; [esp+0x3E] - array index 38 - stepping by two, so the centre pair is 38/39
; and each half covers twenty samples.
; The array index, NOT the stack offset. 0001B345 compares [esp+0x3E] and
; the 0x50-byte array sits at esp+0x18 after six pushes, so the centre entry
; is 0x3E - 0x18 = 38. Taking 0x3E as the index runs the second half-sweep to
; 102 and writes past an 80-byte array.
MFD_VIEW_CENTRE = 38
; 000079F0 starts its source at surface row 162 and steps -0x200 - two rows -
; per panel row, so MFD_VIEW_TOP_ROW in the shared include is the page row the
; panel's top edge shows.

; The column the fan sweeps outward from. The original's two halves cover
; -95..0 and +1..+96 of its 192, so the centre belongs to the descending half.
TERRAIN_CENTRE  = TERRAIN_COLS/2-1
; One DOS source column consumes one authored sky strip. The Falcon walks all
; 192 source columns and crops the recovered source window 16..175 at
; composition.
SKY_STRIP_STEP = 65536                         ; one 16.16 strip per column

        global  render_ring_occlusion
        global  render_scene, render_background, render_reset_surface
        xref    flt_crash_drop, console_draw_rows
        global  render_copy_surface, render_restore_history
        global  render_store_history, render_history_console, terrain_history
        global  sin_table
        global  object_octant_table, object_bearing_correction
        global  colour_palette
        global  flight_palette
        global  original_height_map
        global  original_colour_map
        global  backdrop_build
        global  ring_z_table, ring_page_table, ring_b_table
        global  ring_a_table, ring_invz_table, ring_horizon_table
        global  horizon_table
        global  ring_silhouette, render_page_anchor
        global  backdrop_dy, backdrop_base, render_row_shear, render_nolock_capture, mfd_nolock_buf
        global  margin_left, margin_right
        global  mfd_march_target_view, mfd_view_occl
        global  mfd_target_silhouette
        global  mfd_view_sin, mfd_view_cos
        global  ring_mul_q31_raw, sine_q31
        global  terrain_lowres, sky_enabled

; The surface is 192 source columns wide and the window shows 160 of them
; (16..175), but 00007AA0's row shear reads real columns on either side of it.
; Columns 0..15 and 176..191 are therefore painted too, into two margin
; buffers with the screen's own row stride, so every painter - the sky fill, the
; terrain spans, the sprites - writes a column the same way wherever it is.
; In: d5 = source column 0..191; out: a0 = that column's row 0 (a pixel pair
; wide); clobbers d0.
COLBASE macro
        cmpi.w  #TERRAIN_VIEW_FIRST,d5
        blt.s   .cb_left\@
        cmpi.w  #TERRAIN_VIEW_LAST,d5
        bgt.s   .cb_right\@
        move.l  render_target,a0
        move.w  d5,d0
        subi.w  #TERRAIN_VIEW_FIRST,d0
        bra.s   .cb_add\@
.cb_left\@
        lea     margin_left,a0
        move.w  d5,d0
        bra.s   .cb_add\@
.cb_right\@
        lea     margin_right,a0
        move.w  d5,d0
        subi.w  #TERRAIN_VIEW_LAST+1,d0
.cb_add\@
        lsl.w   #2,d0                           ; two Falcon pixels per column
        adda.w  d0,a0
        endm

        text

; The finished terrain silhouette for one depth ring: 192 bytes of page rows,
; one per DOS source column, as the original archives them. 000254CF forms
; the same pointer as [00022358] + column, where 00025223/0002522E set
; [00022358] to [00019E60] + ring*256 and the marcher wrote that ring's row at
; +0x20.
; In:  d0.w = ring index, 0..ring_steps-1.
; Out: a0 = the ring's row, or zero when the index is out of range.
; DOS: flat 00025223-0002522E and 00024D46-00024D52, the ring's silhouette base.
; DOS symbol: inside loc_00025214
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: resolves the same per-ring row out of the marcher's saved silhouette.
; Preserved: one row per ring, indexed by DOS source column.
; Kind: translated.
; Status: ported; object/terrain occlusion capture remains pending.
render_ring_occlusion
        suba.l  a0,a0
        cmp.w   ring_steps,d0                   ; the LIVE count, not the bound
        bcc     .out
        tst.w   d0
        bmi     .out
        movem.l d1,-(sp)
        moveq   #0,d1
        move.w  d0,d1
        mulu    #TERRAIN_COLS,d1
        lea     ring_silhouette,a0
        adda.l  d1,a0
        movem.l (sp)+,d1
.out
        rts

; The background alone, for the DSP path: the kernel emits terrain spans only,
; so the sky and ground base still come from here. Same division of labour
; render_scene has internally - including publishing the target, which the
; first version skipped: render_clear paints through render_target, and on
; the first DSP frame that was still zero, so the sky fill went to address
; zero and took the vector table with it. In: a0 = back buffer.
; DOS: flat 000196B4 frame entry's background phase and viewport fills.
; DOS symbol: loc_000196B4
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: clears/restores the Falcon RGB565 surface before terrain emission.
; Preserved: authored sky/ground source order and console-independent boundary.
; Kind: translated.
; Status: ported; same-camera capture remains pending.
render_background
        move.l  a0,render_target
        bsr     render_clear
        rts

; Copy a complete RGB565 surface. The original renderer is single-buffered:
; rows that its backdrop fill does not touch persist from the immediately
; preceding frame. Falcon scanout is double-buffered, so that persistence must
; live in a logical terrain surface rather than in either physical buffer.
; In: a0 = destination work surface, a1 = last published surface.
; DOS: flat 00016EC0-00017579's persistent surface between frame calls.
; DOS symbol: inside sub_00016E41
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: the callers below use this primitive to preserve that persistence
; across the Falcon buffer boundary without carrying the cockpit or HUD into
; the next terrain frame.
; Preserved: full surface byte order, copy length, source/destination roles,
; and the terrain-only contents that persist between frames.
; Kind: adapted - double-buffer ownership.
; Status: ported; attract flight sweep remains the acceptance check.
render_copy_surface
        ; Measured 2,457,740 cycles - 7.7% of the frame - across the two calls
        ; render_store_history and render_restore_history make. Do not try to
        ; block-move it: a MOVEM version was built and profiled on 2026-09-01
        ; and came out at 194 cycles per 48 bytes against this loop's 16.0 per
        ; longword, i.e. 16.2 - the copy is ST-RAM bandwidth-bound, not
        ; instruction-bound, so amortising fetch and decode buys nothing and
        ; the extra lea/dbra make it slightly worse. The cost that IS
        ; removable is the second copy, not the copying.
        movem.l d0/a0-a1,-(sp)
        move.w  #FRAME_BYTES/4-1,d0
.copy
        move.l  (a1)+,(a0)+
        dbra    d0,.copy
        movem.l (sp)+,d0/a0-a1
        rts

; Restore the terrain-only surface into a physical work buffer before the next
; attract flight frame. This must not copy display_screen: display_screen has
; already had the cockpit and HUD composited over the terrain.
; In: a0 = destination work surface.
; DOS: flat 00016EC0-00017579's single persistent surface; DOS needs no
; counterpart because it never swaps buffers.
; DOS symbol: inside sub_00016E41
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: reloads the logical terrain surface into the physical work buffer.
; Preserved: the between-frame persistence of rows the backdrop does not touch.
; Kind: adapted - double-buffer ownership.
; Status: ported; attract flight sweep remains the acceptance check.
render_restore_history
        lea     terrain_history,a1
        bsr     render_copy_surface
        rts

; Save the terrain-only surface after terrain composition, before objects and
; cockpit/HUD drawing. This is the Falcon representation of DOS's persistent
; single surface.
; In: a0 = source work surface.
; DOS: flat 00016EC0-00017579's single persistent surface, captured at the
; point 0000D40E transfers it to the visible page - after the object draw
; pass and before the cockpit.
; DOS symbol: inside sub_00016E41
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: saves the logical terrain surface out of the physical work buffer.
; Preserved: what persists and what does not, across the Falcon buffer swap.
; Kind: adapted - double-buffer ownership.
; Status: ported; attract flight sweep remains the acceptance check.
render_store_history
        move.l  a0,a1
        lea     terrain_history,a0
        bsr     render_copy_surface
        rts

; Put a freshly loaded console image on the persistent surface.
;
; Every DOS console load is followed by 0001687D. It sets the Sequencer map
; mask to one plane at a time and calls 00016BB0 four times, which copies
; [00015F78] rows of the decoded image opaquely into the draw page
; [00019CA8]. The flip's partner, 00016B50, then copies the displayed page
; into the other one, so both pages carry it. Nothing redraws those rows
; afterwards: 00006FEF limits the terrain transfer to the image's clear
; words, and 0000D8AE draws no cockpit for variants above 5. So under an
; outside camera, the console that was loaded is what stays on screen below
; the view.
;
; This port's persistent page is terrain_history, so the image goes there.
; Clear pixels are skipped. On DOS those are exactly the pixels the
; transfer overwrites from the separate compose surface; writing index 255
; there would corrupt the terrain rows that persist between frames here.
; CONSOL5S.DTA is clear in all of rows 0-167 and nowhere below, so the
; skipped set is the 168-row view.
; DOS: flat 0001687D-000168D7 with 00016BB0, the console page blit.
; DOS symbol: sub_0001687D
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: draws the loaded console's opaque pixels into terrain_history.
; Preserved: every non-clear pixel of the 240 displayed rows, on the surface
;   that persists, at the point in the variant tail where 000196CF blits.
; Difference: the planar four-pass copy and the 00016B50 page duplication
;   are one RGB565 draw into the single persistent surface.
; Kind: adapted - double-buffer ownership.
; Status: ported; verified against the DEMO1 record 245 fixed-camera pair.
render_history_console
        clr.l   flt_crash_drop                  ; 0001687D's first instruction: [00019DC4] = 0
        move.l  a0,-(sp)
        lea     terrain_history,a0
        move.w  d3,-(sp)
        move.w  #SCREEN_HEIGHT,d3               ; every row: the page keeps them all
        bsr     console_draw_rows
        move.w  (sp)+,d3
        move.l  (sp)+,a0
        rts

; Seed a surface after an attract screen has owned both persistent buffers.
; The normal renderer deliberately preserves the DOS 256-row surface gaps
; between frames, but those gaps cannot contain TPIC/COMA pixels when the first
; flight frame starts. This is a transition operation, not a per-frame clear:
; fill the whole RGB565 target with the active DOS ground entry, then let the
; recovered backdrop routine replace the visible sky rows.
; DOS: flat 0001757E/0001CAD0's viewport base fill, after the attract page is
; left at 00005AE3.
; DOS symbol: loc_0001757E
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: clears one Falcon target at the screen-to-flight boundary before the
; CPU marcher or DSP compositor consumes it.
; Preserved: active palette entry, sky construction, the 168-row terrain
; viewport, and normal persistence after the first terrain frame.
; Kind: adapted - double-buffer transition surface.
; Status: ported. The attract page below the viewport is left standing here,
; but only until the next console load: 0001687D then blits the console over
; it, at pass entry (0000699E) and in every view case's tail (000196CF).
; See render_history_console. An earlier note said the title art was what
; the outside cameras show; the DEMO1 record 245 pair shows consol5s.dta.
render_reset_surface
        movem.l d0-d2/a0,-(sp)
        move.l  a0,render_target
        move.w  flight_palette+510,d1
        move.w  d1,d2
        swap    d2
        move.w  d1,d2
        ; Only the terrain's own 168 rows. The original does not clear the
        ; rows below them here. What they show is whatever console
        ; 0001687D last blitted, and render_history_console reproduces that
        ; blit. Seeding them would have to be undone by the next console
        ; load.
        move.w  #TERRAIN_VIEW_ROWS*SCREEN_WIDTH/2-1,d0
.seed
        move.l  d2,(a0)+
        dbra    d0,.seed
        bsr     render_clear
        ; The two physical buffers are seeded at the transition, but all
        ; replay frames share this one terrain history thereafter.
        move.l  render_target,a0
        bsr     render_store_history
        ; 0000699E: the pass entry's console load is followed by 0001687D, which
        ; blits the console onto the persistent page - and every frame after
        ; this one gets the part below the terrain from that page, not from a
        ; repaint.
        bsr     render_history_console
        movem.l (sp)+,d0-d2/a0
        rts

; DOS: flat 0000D3C0-0000D8F5, complete terrain frame path.
; DOS symbol: sub_0000D3C0
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: runs clear, ring-major terrain march, and indexed-to-RGB565 composition.
; Preserved: camera snapshot, ring order, horizon state, spans, and clipping.
; Kind: adapted - CPU correctness path.
; Status: ported; same-camera image validation remains pending.
render_scene
        move.l  a0,render_target
    ifne MARCHER_ORACLE
        ; Diagnostic build only. Pins the camera to the captured DOS frame in
        ; build/marcher_oracle.s so ring_silhouette below is a function of
        ; this file's instruction stream and the generated tables alone -
        ; nothing the replay does can move it. tools/certify-marcher.py
        ; drives the build and diffs the result against the original's own
        ; silhouette archive at [0x19E60].
        bsr     marcher_oracle_seed
    endc
        ; 0000D950's first instruction is `call 0x7d25`. It builds the view
        ; angle and its Q31 pair, runs the selected variant's handler - which
        ; for variants 6 and 7 MOVES the camera this frame marches from - and
        ; ends in the backdrop's slope, offset and 192-column horizon walk.
        bsr     view_basis_build
        bsr     render_clear
    ifne PARITY_TILE
        ; The parity build renders with the DSP kernel's own arithmetic and
        ; tile windows, so a USE_DSP capture diffs against it to the pixel.
        bsr     render_terrain_parity
    else
        bsr     render_terrain_ring
    endc
        rts

; DOS: flat 00016EC0-00017579 plus viewport fills 0001757E/0001CAD0.
; DOS symbol: inside sub_00016E41
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: selects authored sky strips and fills the Falcon RGB565 background.
; Preserved: view-angle strip origin, roll shear, source rows, and ground order.
; Kind: adapted - platform surface port.
; Status: ported; attract/flight capture remains pending.
render_clear
        movem.l d0-d7/a0-a3,-(sp)
        move.l  render_target,a0

        ; The original backdrop when its image loaded: the authored 150 sky
        ; rows through the sky's own palette - sky_init has already
        ; transposed the bank's 512 column strips into the row-major
        ; sky_image - with the ground base below. One DOS source column is
        ; expanded to two adjacent Falcon pixels, just as 00007AA0 expands a
        ; surface byte through the VGA plane pair.
        ;
        ; DOS origin: the horizon walker at 00007DC3 and the sourced fill at
        ; 00017230 that consumes it. Each of the original's columns takes its
        ; own 150-byte sky strip painted upward from that column's horizon
        ; row, so roll shears the backdrop column by column and pitch shifts
        ; every column together. backdrop_build reproduces that row; this
        ; loop draws each column at its own offset instead of blitting the
        ; image flat from the top.
        ; 00016EC0/00017230 open with `mov esi,[0x19CA4]` and
        ; `or esi,esi / je 0x1757E`: with no sky bank they fall through to the
        ; FLAT VIEWPORT FILL, not to nothing. 000261AF reaches the same fill
        ; the other way - when the sky option [0x25DD8] is not '}' it installs
        ; 0x1757E in all three fill slots. So both cases paint the viewport
        ; with 0001757E's colour and skip the strips, and this port used to
        ; return without painting at all, leaving the previous page showing.
        clr.w   sky_paint
        tst.w   sky_status
        bne     .flat_fill
        tst.w   sky_enabled
        beq     .flat_fill
        move.w  #1,sky_paint
.flat_fill
        ; The ground base, hoisted out of .sky_col. It was written there two
        ; pixels at a time down a 640-byte stride: 160 columns x 168 rows =
        ; 26,880 iterations a frame, each touching a different cache line, and
        ; measured at 5.5% of the whole frame.
        ;
        ; It is one flat block. The fill colour is the constant palette entry
        ; 255, the height d6 is TERRAIN_VIEW_ROWS for every column, and source
        ; columns TERRAIN_VIEW_FIRST..TERRAIN_VIEW_LAST are screen bytes
        ; 0..SCREEN_STRIDE-1 - so the rectangle is contiguous from
        ; render_target. Filling it here writes exactly the same pixels in
        ; exactly the same colour; each column's strip still overwrites its own
        ; rows afterwards, in the same order, because a column's base was
        ; always laid down before its strip and no column touches another's
        ; bytes. Verified 0/76800 pixels changed against the previous build.
        move.l  render_target,a0
        move.w  flight_palette+510,d1           ; 0001757E's [0x2A37E]
        swap    d1
        move.w  flight_palette+510,d1           ; both pixels as one longword
        move.l  d1,d2
        move.l  d1,d3
        move.l  d1,d4
        move.l  d1,d5
        move.l  d1,d6
        move.l  d1,d7
        move.l  d1,a1
        move.l  d1,a2
        move.l  d1,a3
        move.w  #TERRAIN_VIEW_ROWS*SCREEN_STRIDE/40-1,d0
.base_block
        movem.l d1-d7/a1-a3,(a0)                ; 40 bytes a pass
        lea     40(a0),a0
        dbra    d0,.base_block
        ; The margin columns' rows are 16 columns, 64 bytes, of the same colour.
        lea     margin_left,a0
        lea     margin_right,a4
        move.w  #TERRAIN_VIEW_ROWS-1,d0
.base_margin
        movem.l d1-d7/a1-a3,(a0)
        movem.l d1-d7/a1-a3,40(a0)              ; 80 bytes covers 64
        movem.l d1-d7/a1-a3,(a4)
        movem.l d1-d7/a1-a3,40(a4)
        lea     SCREEN_STRIDE(a0),a0
        lea     SCREEN_STRIDE(a4),a4
        dbra    d0,.base_margin
        ; backdrop_build used to be called here. It is 00007D7F onward, the
        ; tail of the routine 0000D950 calls before anything else, so it now
        ; runs from view_basis_build with the slope and offset its own variant
        ; handler produced.
        lea     sky_palette,a2                  ; the sky's own, not the map's
        lea     backdrop_dy,a3
        ; The ground base runs the terrain viewport, which is 168 rows and
        ; not the column: 00007AA0 blits no further, so filling past it paints
        ; rows the original leaves to whatever its single page already held.
        ; A `clear_bottom` variable used to sit here, written unconditionally
        ; to SCREEN_HEIGHT through a dead branch - the stump of the
        ; console-derived fill bound that has been removed from src/console.s.
        move.w  #TERRAIN_VIEW_ROWS,d6
        ; The backdrop's first strip, and this is the original's own expression
        ; rather than a translation of it. 00017251 forms
        ;
        ;       eax = NOT([00019D00]) ; eax -= 0x30000000 ; eax >>= 0x17
        ;
        ; and [00019D00] is [00019D04] plus a per-variant offset that is zero
        ; for the cockpit view, so flt_angle IS that angle here. Taking it
        ; whole keeps all nine bits.
        ;
        ; Two bugs died here. It used to NEG the heading, which ran the bank
        ; backwards - the note then called the negation "the original's", but
        ; the original's NOT lives inside a 32-bit angle, not a heading byte,
        ; so applying it to the byte reversed the pan. The fix for that went
        ; through player_heading and (2h + 159) AND 511, which is arithmetically
        ; right but quantised: an 8-bit heading doubled can only land on EVEN
        ; strips, so half of SKY2.RLE was unreachable and the backdrop stepped
        ; two strips at a time. Off the 32-bit angle all 512 resolve.
        ; 00017251 reads [00019D00] - the view angle, which is the flight
        ; angle only while the cockpit is selected. Off flt_angle the backdrop
        ; panned with the helicopter while the terrain marched with the
        ; camera, and the two external views tore apart.
        move.l  view_angle,d0                   ; the 32-bit angle, not the byte
        not.l   d0
        subi.l  #$30000000,d0
        moveq   #23,d1
        lsr.l   d1,d0
        andi.w  #SKY_STRIPS-1,d0
        move.w  d0,sky_origin
        ; The DOS full-rate fill walks 192 source columns. The Falcon keeps one
        ; authored strip per source column and crops the expanded surface to
        ; source columns 16..175 after the complete source field is walked.
        ;
        ; The fill pairs strips with columns RIGHT to LEFT: 00017271 seeds the
        ; surface column at 0xDF and decrements it while lodsb advances one
        ; 150-byte strip per iteration, so the origin strip lands on the
        ; RIGHTMOST column and column c takes strip origin + 191 - c. Walking
        ; the columns left to right therefore steps the cursor DOWN from
        ; origin + 191. It used to step up from the origin, which mirrored
        ; the whole backdrop and ran the pan against the terrain.
        moveq   #0,d0
        move.w  sky_origin,d0
        addi.w  #TERRAIN_COLS-1,d0
        andi.w  #SKY_STRIPS-1,d0
        swap    d0
        move.l  d0,sky_strip_cursor
        moveq   #0,d5                           ; DOS source column
.sky_col
        move.w  (a3)+,d4                        ; h for this source column
        ; 00016EC0 steps its horizon index by two (000171FF `sub edi,2`) and
        ; its source by two strips (00017202's second `add esi,0x96`), so a
        ; low-detail column pair shares one strip and one horizon entry - the
        ; EVEN one, since edi starts at 0xBE = 190.
        tst.w   terrain_lowres
        beq     .sky_h_ok
        btst    #0,d5
        beq     .sky_h_ok
        move.w  -4(a3),d4
.sky_h_ok
        lea     sky_image,a1
        move.l  sky_strip_cursor,d0
        swap    d0
        andi.w  #SKY_STRIPS-1,d0                ; the bank wraps at 512
        adda.w  d0,a1                           ; this column's strip, row 0

        ; The DOS viewport fill runs before the sourced strip.  It is not only
        ; the ground below the sky: it also owns rows above a positively
        ; pitched strip, where the source image writes nothing.  Leaving those
        ; rows persistent lets the previous TPIC/COMA page survive into the
        ; first replay as a sand-coloured helicopter-shaped block.  The whole
        ; visible window is seeded once by the .base_block fill above, before
        ; any strip is drawn; the strip then overwrites its authored rows.
        ; This is the recovered 0001757E/0001CAD0 fill boundary, not an extra
        ; clear of the hidden console.
        ; 0001757E is the whole of the no-sky path: that fill IS that
        ; routine's `rep stosd` of [0x2A37E], which a capture reads as palette
        ; entry 255 - the entry this fill already uses.
        tst.w   sky_paint
        beq     .sky_advance

        ; This column's top, before the strip row offset is applied: the DOS
        ; fill and the sourced write share a destination column, not a cursor
        ; that carries the fill's full 240-row advance into the next page.
        COLBASE

        ; Where strip byte 0 lands, from the fill's own arithmetic rather than
        ; from the horizon byte directly. 00017230 walks dh DOWN from the
        ; column's horizon while the surface itself is upside down, so byte i
        ; goes to screen row i - SKY_TOP_BIAS - h: the strip hangs 42 rows
        ; above the screen and pitching the nose up slides it DOWN into view,
        ; the opposite of what using h as a top-down offset did.
        neg.w   d4
        subi.w  #SKY_TOP_BIAS,d4                ; screen row of strip byte 0

        ; A positive start row has no source bytes above it.  Leave those
        ; rows untouched, then advance to the first row the DOS strip writes.
        ; Do not fill them with strip byte 0: 00017230 writes exactly 150
        ; bytes and the original surface keeps the rest persistent.
        move.w  d4,d0
        ble     .strip_at_top
        mulu    #SCREEN_STRIDE,d0
        adda.l  d0,a0
.strip_at_top

        ; The image itself, clipped at both ends.
        move.w  #SKY_IMAGE_ROWS,d7              ; rows still to draw
        tst.w   d4
        bge     .no_skip
        move.w  d4,d0
        neg.w   d0                              ; rows scrolled off the top
        cmp.w   d7,d0
        bge     .rows_done
        sub.w   d0,d7
        mulu    #SKY_STRIPS,d0
        adda.l  d0,a1                           ; start further down the strip
.no_skip
        move.w  d4,d0
        bge     .have_row
        moveq   #0,d0
.have_row
        add.w   d7,d0                           ; last row + 1 this column wants
        cmp.w   d6,d0
        ble     .rows_ok
        sub.w   d6,d0
        sub.w   d0,d7                           ; clip at the fill boundary
        ble     .rows_done
.rows_ok
        subq.w  #1,d7
.sky_rows
        move.b  (a1),d1
        move.w  0(a2,d1.w*2),(a0)
        move.w  0(a2,d1.w*2),2(a0)
        adda.w  #SKY_STRIPS,a1
        adda.w  #SCREEN_WIDTH*2,a0
        dbra    d7,.sky_rows
.rows_done

        ; The base was seeded before the strip, so all source gaps already have
        ; the plain DOS viewport colour (index 255 / active palette entry 255).
        ; Do not repaint the tail here: the original draws each visible pixel
        ; once through that fill, then overwrites it only where the sky exists.
        ; 00017230 writes the strip with an 8-bit surface row. When h is
        ; positive, the bytes that run below surface row 0 wrap to the bottom
        ; of the 256-row surface and land at screen rows 214-h..213. The main
        ; segment above was contiguous, so those wrapped rows must be overlaid
        ; after the ground base rather than silently discarded.
        move.w  d4,d0
        addi.w  #SKY_TOP_BIAS,d0                ; d0 = -h
        bpl     .wrap_done                      ; h <= 0: no wrapped segment
        neg.w   d0                              ; total wrapped source rows
        move.w  d0,d1
        cmpi.w  #SKY_IMAGE_ROWS,d0
        ble     .wrap_count_ok
        move.w  #SKY_IMAGE_ROWS,d0
.wrap_count_ok
        move.w  #RING_PAGE_ANCHOR+1,d2
        sub.w   d1,d2                           ; first wrapped screen row
        bpl     .wrap_target_ok
        neg.w   d2                              ; source rows clipped above 0
        cmp.w   d0,d2
        bge     .wrap_done
        sub.w   d2,d0
        move.w  d2,d1                           ; source row to skip
        moveq   #0,d2                           ; clipped target row
        bra     .wrap_source
.wrap_target_ok
        moveq   #0,d1                           ; source starts at row 0
.wrap_source
        ; Only the 168 terrain rows reach the screen (00007AA0); the wrapped
        ; rows land past them and are not displayed.
        cmpi.w  #TERRAIN_VIEW_ROWS,d2
        bge     .wrap_done
        move.w  #TERRAIN_VIEW_ROWS,d3
        sub.w   d2,d3
        cmp.w   d3,d0
        ble     .wrap_fits
        move.w  d3,d0
.wrap_fits
        move.w  d0,-(sp)                        ; COLBASE clobbers d0, the row count
        COLBASE
        move.w  (sp)+,d0
        move.w  d2,d3
        mulu    #SCREEN_STRIDE,d3
        adda.l  d3,a0
        lea     sky_image,a1
        move.l  sky_strip_cursor,d3
        swap    d3
        andi.w  #SKY_STRIPS-1,d3
        adda.w  d3,a1
        mulu    #SKY_STRIPS,d1
        adda.l  d1,a1
        move.w  d0,d7
        subq.w  #1,d7
.wrap_rows
        move.b  (a1),d1
        move.w  0(a2,d1.w*2),(a0)
        move.w  0(a2,d1.w*2),2(a0)
        adda.w  #SKY_STRIPS,a1
        adda.w  #SCREEN_WIDTH*2,a0
        dbra    d7,.wrap_rows
.wrap_done
.sky_advance
        tst.w   terrain_lowres
        bne     .sky_adv_pair
        subi.l  #SKY_STRIP_STEP,sky_strip_cursor ; strips descend as columns
        bra     .sky_adv_done                    ; ascend: the DOS pairing
.sky_adv_pair
        btst    #0,d5
        beq     .sky_adv_done                    ; the odd twin reuses it
        subi.l  #SKY_STRIP_STEP*2,sky_strip_cursor
.sky_adv_done
        addq.w  #1,d5
        cmpi.w  #TERRAIN_COLS,d5
        blt     .sky_col
        movem.l (sp)+,d0-d7/a0-a3
        rts
.sky_skip
        bra     .sky_advance


; The per-column backdrop row, from the original's own arithmetic.
;
; DOS origin: flat 00007D60-00007DC3 (transform, clamp, bias) and the walker
; that follows it to 0000AF4F.
; Purpose: fill backdrop_dy with each screen column's vertical sky offset, and
;   latch the row the backdrop must not paint past.
; Inputs/outputs: reads flt_roll/flt_pitch; writes
;   backdrop_dy[TERRAIN_COLS].
; Original globals/side effects: 00019CF0 roll, 00019CF4 pitch, 00019CF8 slope,
;   00019CFC offset, 00019D80 bias byte, 0x3CB40 the 192-byte horizon array.
; Falcon replacement notes: variant byte 00019D86 is 1 and its handler
;   00007BF0 is a bare ret, so slope IS roll and offset IS pitch. The impact
;   shake 00019DBC now comes from the independent timer contract in shake.s;
;   it is subtracted after the pitch clamp below. The original steps its slope once
;   per its own 192 columns; the Falcon keeps the same 192-column walk and
;   crops only when composing the expanded surface. The walker stores by the
;   EMITTER's column - its step j patches emitter block j and h[95-j], then
;   h[j] - and the fill at 00017230 walks its surface columns right to left
;   with edi in step (both start at 191 and decrement), so h[] is indexed by
;   screen column identically in both consumers and no reversal exists
;   anywhere. An earlier note here claimed the fill consumed h backwards;
;   that misread the fill's column direction.
; Validation: at flt_roll = flt_pitch = 0 every entry is 0 and render_clear
;   reproduces the previous flat blit exactly.
; DOS: flat 00007D60-00007DC3 (transform and clamp), 00007DC3-0000968A
;   (descending half, storing 0x3CB9F down to 0x3CB40) and 0000968A-0000AF4F
;   (the turn and the ascending half, storing 0x3CBA0 up to 0x3CBFF).
; DOS symbol: inside sub_00007D25
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: derives per-column sky offsets from recovered roll/pitch state.
; Preserved: byte arithmetic, variant selection, clamp, and column sequencing.
; Difference: none in the horizon itself. 00007DB5 subtracts the screen-shake
;   phase [00019DBC] from the walker's base before 00007DBE stores it, and
;   that term is now carried - flight_shake_tick ports the timer ISR's
;   generator and countdown, and 00019461's arming is back in the no-damage
;   bounce. It is zero for every frame that has not just hit something, which
;   is why the three-camera verification below is unaffected by adding it.
;   The phase's other two consumers, VGA pixel-pan and CRTC start offset,
;   remain an Unproven presentation contract. The target presentation gate
;   stops an armed shake rather than claiming those visible effects are
;   optional hardware details. See browser-attract.md#shake-timer.
; Kind: translated.
; Status: VERIFIED 2026-08-27 against the original's own memory. The 192-byte
;   horizon array this builds is 0x3CB40, and work/dump_marcher_tables.py
;   dumps it over QMP; the port reproduces it 192/192 at three cameras (roll
;   -133, -111 and +27, each on its pitch clamp, each wrapping through 0/255
;   mid-array). Note with it: the roll clamp of +/-133 at 000190FB caps
;   hi8(|roll| * 0x40) at exactly 0x21, so the byte limit above, while the
;   correct transcription of 00007D98, cannot reach its wrap on this path.
backdrop_build
        movem.l d0-d7/a0,-(sp)

        ; 00007D7F/00007D9A read [00019CF8]/[00019CFC], which 00007D74 and
        ; 00007D79 have just filled from the VARIANT'S handler. For the
        ; cockpit that handler is a bare `ret` and these are the roll and
        ; pitch accumulators, which is what this used to read directly; for
        ; variants 2 to 4 they are swapped and scaled, and for 6 and 7 the
        ; pitch term is zero.
        move.l  view_slope,d1                   ; slope  (00019CF8)
        move.l  view_offset,d2                  ; offset (00019CFC)

        ; lim = byte(0x21 - hi8(|slope| * 0x40)), and the byte is the point.
        ; 00007D93 loads the whole of edx with 0x21 and 00007D98 subtracts ah
        ; from DL alone, so the result is an 8-bit difference zero-extended
        ; back into edx: it never goes negative, it wraps. Past hi8 = 0x21 the
        ; limit therefore jumps to 0xFF, 0xFE, ... and the clamp opens up
        ; instead of closing. This used to read `sub.l`/`bpl`/`moveq #0`,
        ; which pinned pitch to exactly zero over that threshold - a guard the
        ; original does not have, and the opposite of what it does.
        move.l  d1,d3
        bpl     .abs_done
        neg.l   d3
.abs_done
        lsl.l   #6,d3                           ; 00007D91 mul 0x40, low half
        lsr.l   #8,d3                           ; ah
        moveq   #$21,d4                         ; 00007D93 mov edx, 0x21
        sub.b   d3,d4                           ; 00007D98 sub dl, ah
        cmp.l   d4,d2
        ble     .hi_done
        move.l  d4,d2
.hi_done
        neg.l   d4
        cmp.l   d4,d2
        bge     .lo_done
        move.l  d4,d2
.lo_done

        ; 00007DB5, and it comes AFTER the clamp: the shake can push the base
        ; outside the limit the roll just set, which is what makes an impact
        ; visible rather than something the clamp swallows. Zero at rest, so
        ; the three-camera verification above is unaffected.
        sub.l   flt_shake_phase,d2
        move.w  d2,backdrop_base                ; 00007DBE's [00019D80] + 0x32 + shake, for the row shear

        ; The walker's slope is the DOS 8.8 [00019CF8] itself, carried at
        ; 16.16 so its +0x80 round is +0x8000 and the byte extraction is a
        ; plain 16-bit shift. The COLS ratio is 1 and stays only to say the
        ; rate is the DOS walker's own.
        move.l  d1,d3
        asl.l   #8,d3
        muls.l  #TERRAIN_COLS_DOS,d3
        divs.l  #TERRAIN_COLS,d3

        ; 00007DC3 builds the shear from the screen centre outward in the
        ; ring traversal order: unrolled steps 0..95 write columns 95..0 as
        ; offset - dh((step+1)*slope) with `sub al,dh`, the turn at 0000968A
        ; zeroes BOTH the accumulator and the rounded value so column 96 is
        ; offset exactly, and the remaining steps write columns 97..191 as
        ; offset + dh((step-96)*slope) with `add al,dh`. Two half-ramps and a
        ; sign flip make one line through the centre: roll pivots the
        ; horizon mid-screen. An earlier revision stored a single ramp
        ; pivoted at an edge - the tilt was right and the whole backdrop
        ; rode up and down with it, by the shear's full half-width.
        lea     backdrop_dy+(TERRAIN_CENTRE+1)*2,a0
        moveq   #0,d5                           ; xor ebp,ebp
        move.w  #TERRAIN_CENTRE,d7              ; 96 left-half columns
.left
        add.l   d3,d5                           ; 00007DCA: step before use
        move.l  d5,d6
        addi.l  #$8000,d6                       ; the walker's fixed 0x80
        asr.l   #8,d6
        asr.l   #8,d6                           ; dh(step)
        move.w  d2,d0
        sub.w   d6,d0                           ; sub al,dh: offset - dh
        move.w  d0,-(a0)                        ; columns 95 down to 0
        dbra    d7,.left

        lea     backdrop_dy+(TERRAIN_CENTRE+1)*2,a0
        move.w  d2,(a0)+                        ; column 96: dh exactly 0
        moveq   #0,d5                           ; the turn's xor ebp/xor edx
        move.w  #TERRAIN_COLS-TERRAIN_CENTRE-3,d7 ; 95 right-half columns
.right
        add.l   d3,d5
        move.l  d5,d6
        addi.l  #$8000,d6
        asr.l   #8,d6
        asr.l   #8,d6
        move.w  d2,d0
        add.w   d6,d0                           ; add al,dh: offset + dh
        move.w  d0,(a0)+                        ; columns 97 up to 191
        dbra    d7,.right

        movem.l (sp)+,d0-d7/a0
        rts

; 000079F0's source when nothing is locked. 00007860/00007868 skip the target
; march, so the transfer at 00007943 copies the 80 x 44 window of the compose
; surface the main view has just been drawn into - unsheared, objects included.
; Per 00007A0B-00007A94: each panel row is surface row 162 - 2r (`sub edx,0x200`,
; 44 times), each plane pass reads every second byte (`[esi + 2k]`) from columns
; 0x2C/0xAC/0x2D/0xAD, which in the flat numbering the port uses is flat column
; 0x38 + x for panel pixel x. The port's screen column of flat column n is
; (n - 16) * 2, and its screen row is 213 minus the surface row, so panel pixel
; (x, r) is the finished pixel at screen (80 + 2x, 51 + 2r). Taken before
; render_row_shear because the surface the DOS copy reads is the unsheared one.
; DOS: flat 000079F0-00007A94 (the copy), 00007868 (the gate).
; DOS symbol: sub_000079F0
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: keeps the window so the console can show it when the latch is clear.
; Preserved: the window, the 2:1 sampling in both directions, the unsheared source.
; Kind: adapted - chunky true-colour surface.
; Status: ported; checked against DEMO1 record 370.
render_nolock_capture
        movem.l d0-d2/a0-a2,-(sp)
        move.l  work_screen,a0
        lea     51*SCREEN_STRIDE+80*2(a0),a0
        lea     mfd_nolock_buf,a1
        moveq   #44-1,d1
.row
        move.l  a0,a2
        moveq   #80-1,d0
.pixel
        move.w  (a2),(a1)+
        addq.l  #4,a2
        dbra    d0,.pixel
        lea     2*SCREEN_STRIDE(a0),a0
        dbra    d1,.row
        movem.l (sp)+,d0-d2/a0-a2
        rts

; The horizontal half of the roll. 00007DC3-0000968A's unrolled walker writes TWO
; things per step from the same dh: the vertical column offset [0x3CB40 + c]
; (backdrop_dy here) and a source displacement pair at [0x31B20 + 8c]:
;
;       v = byte(0x30 -/+ dh)        left half / right half, 0 at c = 96
;       n = sar(v, 3), carry = bit 2 of v          0000959x  sar al,3 / rcr bl,1
;       A = n + 0x80*carry,  B = n + 1 - carry... (the pair 5,133 / 133,6 / 6,134)
;
; so the flat source column the row starts from is 2n + carry = v >> 2 (floor).
; 00006FEF builds the transfer's run list one SURFACE row at a time - surface
; rows 32..213, [0x19E58] counting them from 0 - and 000070C8 gives every run of
; row k the record at 0x31B30 + 8k, which is column c = k + 2. Screen row y is
; surface row 213 - y, so a screen row reads record c = 183 - y. 00007AA0 then
; copies each row from `surface + run source + [record]`: the terrain is sheared
; horizontally by row with the slope that shears it vertically by column - the
; roll is a rotation done as two shears.
;
; v = 0x30 + (dy[c] - base) in the port's terms, because dy[c] = base -/+ dh
; (base is what 00007DB5-00007DBE leave in [0x19D80], plus 0x32 and the shake).
; A flat mapping is v = 0x30 (n = 6, carry 0, flat column 12); a record with flat
; column F puts the row's content 2*(F-12) pixels to the LEFT of where the flat
; mapping puts it. Measured on DEMO1 record 20, roll 25: the DOS records are
; flat columns 10..14 in five bands of about 40 rows, and the Falcon frame
; without this differed from DOS by exactly +2 pixels in the far band and -2 in
; the near one, 100% and 97% of the pixels in each.
;
; Difference: the DOS surface is 192 columns wide and the window shows 160 of
;   them; a shifted row reads real columns on one side. The sky fill, the terrain
;   spans and the sprites paint columns 0..15 and 176..191 into margin buffers
;   (COLBASE), and the shear takes its row from [margin | window | margin]. The
;   shift is held to 16 columns (the roll clamp's reach on the displayed rows is
;   about 12). A negative n (|dh| > 48, past the clamp on screen rows) would
;   read the neighbouring surface row in DOS (movzx of the sar byte) and is not
;   modelled.
; DOS: flat 00007DC3-0000968A (records), 00006FEF-000070DF (row -> record),
;   00007AA0 (the copy).
; DOS symbol: inside sub_00007D25 / sub_00006FEF / sub_00007AA0
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: copies the persistent surface into work_screen, each terrain row shifted
;   by its record's flat column.
; Preserved: the record formula, the row-to-record mapping, 12 as the neutral
;   column, and that terrain, sky and objects shift together while the cockpit
;   drawn afterwards does not.
; Kind: adapted - chunky true-colour surface.
; Status: ported; checked against DEMO1 record 20.
render_row_shear
        movem.l d0-d7/a0-a6,-(sp)
        lea     terrain_history,a0              ; the surface the frame drew
        move.l  work_screen,a3                  ; the physical buffer
        lea     margin_left,a1
        lea     margin_right,a2
        lea     backdrop_dy,a4
        move.w  backdrop_base,d6
        moveq   #0,d7                           ; screen row y
.row
        cmpi.w  #TERRAIN_VIEW_ROWS,d7
        bhs.s   .plain
        move.w  #183,d0
        sub.w   d7,d0                           ; c = 183 - y
        add.w   d0,d0
        move.w  0(a4,d0.w),d1                   ; dy[c]
        sub.w   d6,d1
        addi.w  #$30,d1                         ; v = 0x30 + (dy - base)
        asr.b   #2,d1                           ; flat column F = floor(v / 4), v as a signed byte
        subi.b  #12,d1
        beq.s   .plain                          ; the flat mapping
        ext.w   d1                              ; delta columns
        ; The window slides over the whole 192-column surface. Sixteen columns
        ; either side exist (margin_left/right); a larger delta would read past
        ; them and is held at the edge.
        cmpi.w  #16,d1
        ble.s   .cap_hi
        moveq   #16,d1
.cap_hi
        cmpi.w  #-16,d1
        bge.s   .cap_lo
        moveq   #-16,d1
.cap_lo
        ; dest[x] = src[x + 2*delta] over [margin 16 | window 160 | margin 16]
        ; columns, a column a long. A window that starts delta columns in takes
        ; the rest of the row from the right margin; one that starts before the
        ; row takes its head from the left one.
        move.l  a0,a5                           ; source row
        move.l  a3,a6                           ; destination row
        tst.w   d1
        bmi.s   .left
        move.w  d1,d2
        asl.w   #2,d2
        adda.w  d2,a5                           ; the window starts delta in
        move.w  #SCREEN_WIDTH/2-1,d2
        sub.w   d1,d2                           ; 160 - delta longs from the row
.copy_row_r
        move.l  (a5)+,(a6)+
        dbra    d2,.copy_row_r
        move.l  a2,a5                           ; and delta from the right margin
        move.w  d1,d2
        subq.w  #1,d2
.copy_margin_r
        move.l  (a5)+,(a6)+
        dbra    d2,.copy_margin_r
        bra.s   .next
.left
        neg.w   d1                              ; e = columns before the row
        move.l  a1,a5
        move.w  #16,d2
        sub.w   d1,d2
        asl.w   #2,d2
        adda.w  d2,a5                           ; the last e longs of the margin
        move.w  d1,d2
        subq.w  #1,d2
.copy_margin_l
        move.l  (a5)+,(a6)+
        dbra    d2,.copy_margin_l
        move.l  a0,a5
        move.w  #SCREEN_WIDTH/2-1,d2
        sub.w   d1,d2                           ; 160 - e longs from the row
.copy_row_l
        move.l  (a5)+,(a6)+
        dbra    d2,.copy_row_l
        bra.s   .next
.plain
        move.l  a0,a5
        move.l  a3,a6
        move.w  #SCREEN_WIDTH/2-1,d2
.copy_plain
        move.l  (a5)+,(a6)+
        dbra    d2,.copy_plain
.next
        lea     SCREEN_STRIDE(a0),a0
        lea     SCREEN_STRIDE(a3),a3
        lea     SCREEN_STRIDE(a1),a1
        lea     SCREEN_STRIDE(a2),a2
        addq.w  #1,d7
        cmpi.w  #SCREEN_HEIGHT,d7
        bne     .row
        movem.l (sp)+,d0-d7/a0-a6
        rts

; ---------------------------------------------------------------------------
; Terrain pass.
;
; A sample is drawn only when it projects strictly above the column's stored
; occlusion row, and its span runs from ONE BELOW its projected row down to
; the stored row - the projected row itself goes to the next accepted
; (deeper) sample, which is the original's convention: the DOS emitter
; paints [old horizon, new top) in bottom-up page rows and stores the new
; top. The projected row is clamped at -1 rather than 0 so a span whose top
; is exactly the screen's top row still leaves that row for a deeper sample,
; as DOS does. Each screen pixel is written at most once, and when the
; stored row goes negative the column is finished - that early-out is what
; keeps a near ridge from costing a full depth march.
; ---------------------------------------------------------------------------


; The horizon row the terrain projection uses at a given depth.
;
; DOS 00015AD9 adds a per-depth bias from HIGH.DTL table 3, so the horizon is a
; curve rather than a constant and anything placed against the terrain has to
; ask for the same row. This routine is the only place that inverts the depth
; schedule; object.s calls it rather than keeping a copy.
;
; In:  d0.l = depth in map units
; Out: d0.l = horizon row
        global  render_horizon_for_depth
; DOS: flat 00015AD9, per-depth projection-page/bias builder.
; DOS symbol: sub_00015AD9
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: looks up the generated HIGH.DTL-derived horizon for object composition.
; Preserved: depth schedule, page bias, clamps, and row orientation.
; Kind: translated.
; Status: ported; object/terrain same-camera validation remains pending.
; Rebuild horizon_table after src/dtl.s has loaded a different .DTL.
;
; horizon_table is the row an object at a given depth is placed against, and
; render_horizon_for_depth above is its only reader. It is derived, not
; loaded: for each of this port's own depth samples it takes the row of the
; first ring the terrain draws at or past that distance.
;
; Two facts make that a table walk rather than a second projection.
; ring_page_table's entry at k = 128 IS the level plane's row - the page's
; (k - 128) term vanishes there - and equals the ring's bias >> 8 exactly,
; which tools/prepare-original-test.py asserts for every ring it generates.
; And ring_z_table is the .DTL's own cumulative depth at 2^23 per world unit,
; the same schedule the marcher walks, so the search needs no conversion
; beyond shifting the sample's distance into those units.
;
; ring_invz_table and ring_horizon_table are generated beside these and have
; no reader in the port, so they are deliberately not rebuilt; a build that
; grows one has to come back here.
;
; In:  ring_steps, ring_page_table and ring_z_table already rebuilt.
; DOS: no counterpart - the original searches its bias column per object at
;   000251E0 instead of keeping this table.
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: re-derives the depth-indexed horizon from the freshly loaded rings.
; Preserved: the same first-ring-at-or-past-depth rule the build-time
;   generator uses, so a reload cannot make the two disagree.
; Kind: replaced - build-time derivation moved to load time.
; Status: ported; a reload leaves object placement on the same projection the
;   terrain draws, which is what the generator asserts at build time.
        global  render_rebuild_horizons
render_rebuild_horizons
        movem.l d0-d7/a0-a4,-(sp)

        ; The last ring's row, as the default for a sample past the schedule.
        moveq   #0,d0
        move.w  ring_steps,d0
        subq.w  #1,d0
        lsl.l   #8,d0                           ; * 256, the page stride
        lea     ring_page_table,a0
        adda.l  d0,a0
        moveq   #0,d4
        move.b  128(a0),d4
        neg.w   d4
        addi.w  #RING_PAGE_ANCHOR,d4            ; d4 = the fallback row

        lea     horizon_table,a1
        moveq   #0,d6                           ; cumulative depth, map units
        moveq   #0,d5                           ; sample index
.sample
        ; The port's own three-tier schedule, from src/dsp/proto.inc so the
        ; reference renderer and the kernel cannot drift apart.
        cmpi.w  #MARCH_NEAR_STEPS,d5
        bcc     .not_near
        addq.l  #1,d6
        bra     .stepped
.not_near
        cmpi.w  #MARCH_NEAR_STEPS+MARCH_FAR_STEPS,d5
        bcc     .far2
        addi.l  #1<<TILE_FAR_SHIFT,d6
        bra     .stepped
.far2
        addi.l  #1<<TILE_FAR2_SHIFT,d6
.stepped
        ; Into table 4's units. The product passes 2^31 well before the last
        ; sample, so every compare below is unsigned.
        move.l  d6,d0
        lsl.l   #8,d0
        lsl.l   #8,d0
        lsl.l   #7,d0                           ; * 2^23
        move.l  d0,d3

        lea     ring_z_table,a2
        lea     ring_page_table,a3
        move.w  d4,d1                           ; the fallback
        moveq   #0,d7
        move.w  ring_steps,d7
        subq.w  #1,d7
.search
        move.l  (a2)+,d0
        cmp.l   d3,d0
        bcs     .next                           ; unsigned: z passes 2^31
        moveq   #0,d1
        move.b  128(a3),d1
        neg.w   d1
        addi.w  #RING_PAGE_ANCHOR,d1
        bra     .found
.next
        lea     256(a3),a3
        dbra    d7,.search
.found
        move.w  d1,(a1)+
        addq.w  #1,d5
        cmpi.w  #DEPTH_SAMPLES,d5
        blo     .sample

        movem.l (sp)+,d0-d7/a0-a4
        rts

render_horizon_for_depth
        move.l  a1,-(sp)
        subq.l  #1,d0
        bpl     .have
        moveq   #0,d0
.have
        cmpi.l  #DEPTH_NEAR_SAMPLES,d0
        blt     .near
        sub.l   #DEPTH_NEAR_SAMPLES,d0
        cmpi.l  #MARCH_FAR_STEPS<<TILE_FAR_SHIFT,d0
        blt     .far
        subi.l  #MARCH_FAR_STEPS<<TILE_FAR_SHIFT,d0
        lsr.l   #TILE_FAR2_SHIFT,d0
        add.l   #DEPTH_NEAR_SAMPLES+MARCH_FAR_STEPS,d0
        bra     .near
.far
        lsr.l   #TILE_FAR_SHIFT,d0
        add.l   #DEPTH_NEAR_SAMPLES,d0
.near
        cmpi.l  #DEPTH_SAMPLES-1,d0
        ble     .bounded
        move.l  #DEPTH_SAMPLES-1,d0
.bounded
        add.l   d0,d0
        lea     horizon_table,a1
        move.w  0(a1,d0.l),d0
        andi.l  #$0000ffff,d0
        move.l  (sp)+,a1
        rts

; One sample of the ring walk: 0000D9E9-0000D9F9.
; In:  d5/d6 the 10.22 position, d4 the page index bias, a0 the
;      ring's page, a4 the height map.
; Out: d0 = the map index, d2.b = the page row.
;
; 0000D9EE/0000D9F2's `shld ebx,edx,0xa` / `shld ebx,edi,0xa` put Y's top ten
; bits above X's top ten. BFEXTU reads those same unsigned ten-bit cells;
; SWAP then LSR.L #6 puts Y in bits 10..19, and OR.W inserts X in 0..9.
; 0000D9F6's `add al, gs:[ebx]` is a BYTE add onto the bias, so the
; page index wraps exactly as the original's does - on D1, whose heights stop
; at 187, it cannot fire - and 0000D9F9 looks the row up in the page.
TERRAIN_SAMPLE  macro
        ; DOS 0000D9EE/0000D9F2: extract exactly the top ten coordinate bits.
        bfextu  d6{0:10},d0
        swap    d0
        lsr.l   #6,d0                           ; Y cell << 10
        bfextu  d5{0:10},d1                     ; X cell
        or.w    d1,d0                           ; the 20-bit map index
        move.w  d4,d1
        add.b   (a4,d0.l),d1                    ; bias + height, byte wrap
        move.b  (a0,d1.w),d2                    ; the page row
        endm

; A sample that rose above its column's horizon: the emitter block the
; original's `ja` reaches, 0000AF50 + 0x30*column (0000F320's for low detail).
; \1 is the horizon entry's displacement from a3, \2 the source columns the
; sample owns (1, or 2 for low detail's pair).
; In:  d0 = map index, d2.b = the new page row p, \1(a3) = the old horizon h.
; Out: the horizon holds p; d3 = 12 and a5 = the colour map again.
;
; The span is [h, p) in page rows - the block starts ch at the OLD horizon,
; enters its Duff's device at 256 - (p - h) and stores the new top before
; the jump - so the boundary row p belongs to the next deeper sample.
; ring_cols holds the column's clip and address (see render_terrain_ring).
; The original needs no clip: its writes wrap inside a 256x256 surface and
; the transfer's window drops what falls outside.
;
; Pitch and roll, the way the original applies them. 00007DC3 writes
; byte(0x32 - dh + bias) into the imm8 of each emitter block's `add ch, 0` at
; 0000AF62 + 0x30*col, and that immediate shifts where the span is DRAWN - it
; is added to ch, the span's start row, after the occlusion has already been
; read and stored. So the horizon moves the picture without moving the
; visibility test, which is why the marchers never read pitch and why the
; horizon above is deliberately left unshifted. The surface is stored upside
; down - screen row = 213 - surface row - so on screen the span moves the
; other way: a positive horizon byte lifts the picture. ring_cols carries it
; as backdrop_dy, per DOS source column; both RGB565 pixels expanded from
; that source byte use the same shear.
;
; DOS: flat 0000AF50-0000D34C and 0000F323-00010793, the per-column span
;   emitters, and 00006BF0-00006FEF, the unrolled vertical span writer.
; DOS symbol: inside loc_0000AF50
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: writes the [old, new) span as RGB565 pairs down one surface column.
; Preserved: the horizon store before the span, the span's rows and length,
;   the per-column shear, and low detail's paired store and four pixels.
; Difference: clipped to the surface rows and the displayed columns 16..175
;   instead of wrapping inside a 256x256 buffer.
; Kind: translated.
; Status: ported; certified with the marcher - see render_terrain_ring.
TERRAIN_PAINT   macro
        moveq   #0,d3
        move.b  (a5,d0.l),d3                    ; colour byte, same map index
        move.l  (a6,d3.w*4),d0                  ; its RGB565 pair
        moveq   #0,d1
        move.b  \1(a3),d1                       ; h
        move.b  d2,\1(a3)                       ; the new horizon
    ifeq \2-2
        move.b  d2,\1+1(a3)                     ; 0000F337's second store
    endc
        move.l  a3,d3
        sub.l   #ring_hz,d3
        lea     (ring_cols+(\1)*8,d3.l*8),a5    ; this column's clip and base
        andi.w  #$00ff,d2
        subq.w  #1,d2                           ; p - 1, the span's top row
        cmp.w   (a5)+,d1
        bge.s   .\@lo
        move.w  -2(a5),d1                       ; clipped below
.\@lo
        cmp.w   (a5)+,d2
        ble.s   .\@hi
        move.w  -2(a5),d2                       ; clipped above
.\@hi
        sub.w   d2,d1
        bgt.s   .\@done                         ; nothing left on the surface
        neg.w   d1                              ; rows - 1
        move.l  (a5),a5
        adda.l  (ring_rowneg,d2.w*4),a5         ; the top row's address
.\@row
        move.l  d0,(a5)
    ifeq \2-2
        move.l  d0,4(a5)                        ; the pair's second column
    endc
        lea     SCREEN_STRIDE(a5),a5
        dbra    d1,.\@row
.\@done
        lea     original_colour_map,a5
        moveq   #12,d3
        endm

; The original's marcher, in its own loop order.
;
; DOS origin: flat 0000D950-0000F317, the 192-column bank.
; Purpose: walk the .DTL's 250 depth rings outermost and all terrain columns
;   of one ring innermost, emitting spans where a sample rises above that
;   column's running horizon.
; Inputs/outputs: reads flt_x/flt_y (the DOS 10.22 camera), flt_angle,
;   altitude, ring_a_table,
;   ring_b_table, ring_page_table and the two original maps; writes
;   spans through TERRAIN_PAINT and leaves ring_silhouette holding every
;   ring's horizon, as bytes of page rows, as the original archives it.
; Original globals/side effects: [00019CD4]/[00019CD8] camera, the per-column
;   horizon the DOS marcher keeps in a stack array, the emitter's [old, new)
;   span convention at 0000AF50.
; Falcon replacement notes: position at ring i column c is
;   origin + z_i*edge + c*(z_i*fanstep), so a ring costs four fixed-point
;   multiplies and every column in it costs an add. That is the whole reason
;   the original can afford a depth curve and the column-major marcher cannot.
;   Computing position from z rather than accumulating it also means the far
;   rings carry no accumulated step error.
; Validation: against render_terrain on the same camera - the two schedules
;   differ by design, so the pictures are not expected to match pixel for
;   pixel, but the silhouette and the span convention must agree.
; DOS: flat 0000D950-0000F317, the 192-column marcher, and 000137F0-00015854,
;   the 96-column one - one parameterised routine here, because the two differ
;   only in the lateral step, the sample count, the paired occlusion store and
;   the width a span is painted at. 000261FE picks between them on [0x25DD9].
; DOS symbol: inside loc_0000D94C
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: walks authored A/B rings on the 68030 and emits RGB565 spans.
; Preserved: ring-major order, Q31 products, sampling, horizon test, and spans.
; Kind: adapted - CPU oracle.
; Status: CERTIFIED 2026-08-31 against the original's own memory - THIS CODE,
;   not a model of it. tools/certify-marcher.py builds with MARCHER_ORACLE=1,
;   which pins the camera to a captured DOS cockpit frame, runs the result
;   under Hatari, and diffs ring_silhouette against the original's archive at
;   [0x19E60]. Two independent cameras, every scored column exact with max|e|
;   of 0:
;
;       marcher-cockpit    alt  54  angle 0xF4062AC6  15120/15120
;       marcher-cockpit2   alt 194  angle 0xCAB17DE2  16352/16352
;
;   Scored over the 112 columns the main view owns - 0001B84E writes the rear
;   view's 80 entries over the middle of every archived row - and over the
;   non-uniform rings only, since a uniform ring matches anything.
;
;   That closes a chain whose first two links were already measured and
;   neither of which ran a 68030 instruction: tools/compare-marcher.py models
;   0000D950 and reproduces the original exactly, and
;   tools/compare-port-tables.py feeds THIS port's .DTL-derived tables and its
;   decoded height map through that model to the same 100%. Each step here was
;   checked against the model: camera source (0000D974), the 8-bit bias wrap
;   (0000D98C/0000D9F6), the shld index pair (0000D9EE), the half-sweeps
;   -95..0 and +1..+96, the strict horizon test (0000D9FB `ja`), and the
;   truncate-then-subtract rounding at 0000D9B7 - that last one was wrong here
;   and is fixed below.
;
;   The LOW-DETAIL path is certified the same way and against the same
;   archive. 000261FE's other branch installs 000137F0, which this routine
;   carries as terrain_lowres rather than as a second code pointer:
;
;       marcher-lowres     alt 197  angle 0xB826CE53  17472/17472
;
;   The capture for it is taken with [0x19C94] poked to 0x000137F0 mid-flight,
;   and it is the 96-column marcher beyond doubt: in the original's own
;   archive occl[2k] == occl[2k+1] for 10080/10080 of the columns the main
;   view owns, against 6229/10080 on the 192-column path, which is 0000F320's
;   second occlusion store showing through.
;
;   The capture must be a COCKPIT frame, view variant [0x19D86] == 1. Early
;   attract records run variant 6, whose look direction is animated apart from
;   the helicopter heading, so [0x19D00] != [0x19D04] and no value of
;   flt_angle reproduces the basis the marcher used. Both external cameras are
;   now ported - see src/view.s - and this routine takes [0x19D00]'s own Q31
;   pair rather than deriving one, so a variant-6 or -7 capture would be
;   comparable too; the certification above stays on cockpit frames because
;   that is where the archive was taken.
render_terrain_ring
        movem.l d2-d7/a0-a6,-(sp)

        ; DOS 00007D25 forms the view basis from the full angle at 00019D00,
        ; then 0000D950 uses its Q31 pair at 00019CB0/00019CB4. view.s owns
        ; that routine now, so this reads the pair rather than re-deriving one
        ; from flt_angle - which was only ever right for the cockpit, where
        ; the variant offset is zero and no handler moves the camera.
        move.l  view_sin,d3                     ; [00019CB0]
        move.l  view_cos,d4                     ; [00019CB4]
        move.l  d3,ring_fwd_x
        move.l  d4,ring_fwd_y

        ; The page index bias, not a camera height: 0000D98C forms
        ; NOT(alt) >> 1 = 127 - alt/2 and parks it in the page pointer's low
        ; byte, and 0000D9F6 adds the terrain height onto it in BYTE
        ; arithmetic. The camera term the old computed row used - alt/2 + 1 -
        ; is the same quantity seen from the other side of the page's
        ; (k - 128), and it is the page that applies it now.
        moveq   #0,d0
        move.b  player_altitude,d0
        asr.w   #1,d0
        neg.w   d0
        addi.w  #127,d0
        andi.w  #$00ff,d0
        move.w  d0,ring_camh

        ; Every column's horizon starts at page row 0, the bottom of the
        ; surface, which is where the original starts it: 0000D976 reserves
        ; 0xC0 bytes of stack and `rep stosd` zeroes 0x30 dwords, so all 192
        ; columns begin at page row 0.
        ;
        ; The horizon is kept as the original keeps it - one BYTE of page row
        ; per column, compared unsigned - so the column loop's test is
        ; 0000D9FB's `cmp ah,[esp+n] / ja` as one `cmp.b / bhi`. An earlier
        ; revision kept it as a word of screen rows, which is the same test
        ; seen from the other side of RING_PAGE_ANCHOR but cost a negate, an
        ; add and two sign extensions on every sample.
        ;
        ; It used to be a per-column console "floor" - the deepest row the
        ; cockpit lets a column show - on the argument that spans below it are
        ; invisible. They are, but the seed is not just a clip: a sample at or
        ; below the seed fails the test and is dropped WITHOUT advancing the
        ; occlusion, so every near ring under the cockpit line was discarded
        ; instead of being drawn and then covered. That left the near band
        ; unpainted and the ground base showing through it as a green block.
        lea     ring_hz,a0
        moveq   #TERRAIN_COLS/4-1,d0
.seed
        clr.l   (a0)+
        dbra    d0,.seed

        ; Per-frame tables the column loop reads instead of recomputing.
        ; Neither changes a value; both move work out of the sample loop.
        ;
        ; ring_pal32: the flight palette's RGB565 entry twice in a longword,
        ; because one DOS source column is two Falcon pixels.
        lea     flight_palette,a0
        lea     ring_pal32,a1
        move.w  #255,d0
.pal
        move.w  (a0)+,d1
        move.w  d1,(a1)+
        move.w  d1,(a1)+
        dbra    d0,.pal

        ; ring_cols: per source column, the page rows a span may cover and the
        ; surface address of page row 0 - the old draw_span's clipping and
        ; addressing, solved once per frame instead of once per span.
        ;
        ; A span covers page rows [h, p) - the emitter's [old, new) - and
        ; page row q lands on screen row RING_PAGE_ANCHOR - q - dy, where dy
        ; is the column's backdrop_dy (the shear 00007DC3 writes into each
        ; emitter's `add ch, imm`; see below). The surface keeps screen rows
        ; 0..TERRAIN_VIEW_ROWS-1, so q is kept to
        ;   [RING_PAGE_ANCHOR - (TERRAIN_VIEW_ROWS-1) - dy, RING_PAGE_ANCHOR - dy]
        ; and q's address is base - q*SCREEN_STRIDE with
        ;   base = target + (RING_PAGE_ANCHOR - dy)*SCREEN_STRIDE + (c - 14)*4.
        ; A column outside the displayed window 16..175 gets an empty range,
        ; so it still advances its horizon and archives it but paints nothing.
        lea     backdrop_dy,a0
        lea     ring_cols,a1
        moveq   #0,d2                           ; source column
.col
        move.w  (a0)+,d1                        ; dy
        move.w  #RING_PAGE_ANCHOR-(TERRAIN_VIEW_ROWS-1),d0
        sub.w   d1,d0
        move.w  d0,(a1)+                        ; lowest page row kept
        move.w  #RING_PAGE_ANCHOR,d0
        sub.w   d1,d0
        move.w  d0,(a1)+                        ; highest page row kept
        move.l  d0,-(sp)
        move.w  d2,d5
        move.l  a0,-(sp)
        COLBASE                                 ; the column's own buffer
        move.l  a0,d3
        move.l  (sp)+,a0
        move.l  (sp)+,d0
        ext.l   d0
        muls.l  #SCREEN_STRIDE,d0
        add.l   d3,d0                           ; page row 0's address
        move.l  d0,(a1)+
.col_next
        addq.w  #1,d2
        cmpi.w  #TERRAIN_COLS,d2
        blt     .col
        ifne    TERRAIN_XSTEP*2-4
        fail    "ring_cols assumes TERRAIN_XSTEP*2 = 4 bytes per source column"
        endc

        ; The three cursors live in memory, not in address registers: the
        ; column loop uses all of them. They advance once per ring, so the
        ; reload costs nothing measurable.
        move.l  #ring_a_table,ring_ap
        move.l  #ring_b_table,ring_bp
        move.l  #ring_page_table,ring_hp
        move.l  #ring_silhouette,ring_silp
        move.w  ring_steps,ring_counter         ; [0x19EE0], whatever .DTL is loaded
        ; The camera in the original's own 10.22, not the published 16.16:
        ; 0000D974 loads [00019CD4]/[00019CD8] and the increments below are
        ; the raw imul high words, so the whole walk stays in DOS units and
        ; the 32-bit wrap is the map wrap.
        move.l  flt_x,ring_cx                   ; the accumulator starts at the
        move.l  flt_y,ring_cy                   ; camera, as the original's does

.ring
        move.l  ring_ap,a0
        move.l  (a0)+,d0                        ; A, raw 10.22
        move.l  a0,ring_ap
        move.l  d0,ring_a
        move.l  ring_bp,a0
        move.l  (a0)+,d0                        ; B, raw 10.22
        move.l  a0,ring_bp
        move.l  d0,ring_b
        ; This ring's 256-byte projection page, advanced once per ring.
        ; It replaces the reciprocal and horizon tables together: both were
        ; the two halves of a row this page already holds, precomputed.
        move.l  ring_hp,a0
        move.l  a0,ring_page
        adda.w  #256,a0
        move.l  a0,ring_hp

        ; The ring centre ACCUMULATES. 0000D99A adds the original .DTL A_i
        ; increment to the previous ring's point rather than recomputing it
        ; from cumulative depth, so its rounding compounds along the march.
        move.l  ring_a,d0
        move.l  ring_fwd_x,d3
        bsr     ring_mul_q31_raw
        add.l   d0,ring_cx
        move.l  ring_a,d0
        move.l  ring_fwd_y,d3
        bsr     ring_mul_q31_raw
        ; 0000D9B1/0000D9B7 truncate FIRST and subtract second: `imul` keeps
        ; edx, then `sub ebx, edx`. Negating the multiplicand instead and
        ; adding is not the same rounding - high32(A*-C) is -high32(A*C)-1
        ; whenever the low half is non-zero, which it was for all 180 rings
        ; of the captured frame - and the -1 accumulates once per ring.
        sub.l   d0,ring_cy                      ; DOS 0000D9B7: sub ebx, edx

        ; The lateral step is the original B_i. All 192 DOS columns are
        ; marched, so there is no presentation-rate rescale in the geometry.
        ;
        ; Low detail doubles it, and doubles it BEFORE the product:
        ; 00013862 and 00013873 are `shl eax,1` on the .DTL word and only
        ; then `imul`. high32(2B * sin) is not 2 * high32(B * sin) once the
        ; low half is non-zero, and the difference accumulates along the
        ; sweep, so the shift has to sit where the original puts it.
        move.l  ring_b,d0
        tst.w   terrain_lowres
        beq     .lat_x_full
        add.l   d0,d0                           ; 00013862
.lat_x_full
        move.l  ring_fwd_y,d3                   ; B * cos
        bsr     ring_mul_q31_raw
        move.l  d0,ring_lat_x
        move.l  ring_b,d0
        tst.w   terrain_lowres
        beq     .lat_y_full
        add.l   d0,d0                           ; 00013873
.lat_y_full
        move.l  ring_fwd_x,d3                   ; B * sin
        bsr     ring_mul_q31_raw
        move.l  d0,ring_lat_y

        ; The column loop's registers, for all four sweeps below:
        ;   d0 map index, d1 page index, d2 page row  (per sample)
        ;   d3 the constant 12 the index shift uses   (scratch while painting)
        ;   d4 the page index bias, d5/d6 the 10.22 position, d7 the count
        ;   a0 this ring's page, a1/a2 the lateral step, a3 the horizon
        ;   a4 the height map, a5 the colour map      (scratch while painting)
        ;   a6 ring_pal32
        move.l  ring_page,a0
        lea     original_height_map,a4
        lea     original_colour_map,a5
        lea     ring_pal32,a6
        move.w  ring_camh,d4
        moveq   #12,d3

        ; Two half-sweeps outward from the centre, which is what the original
        ; does: it pushes the ring's start point at 0000D9B9/0000D9BA, walks 96
        ; columns SUBTRACTING the lateral step, then pops the centre back in
        ; the 40-byte gap after sample 95 and walks the other 96 ADDING it.
        ; Each column's position therefore accumulates from the middle
        ; outward. This port used to walk all 160 from the left edge, which
        ; reaches the same geometry by a different sum and rounds differently
        ; the further right it got.
        ;
        ; Half one takes the centre column itself and then steps; half two
        ; steps first, so the centre is sampled once. That asymmetry is the
        ; original's - its halves cover -95..0 and +1..+96.
        ;
        ; Each half is its own loop, as each of the original's 192 samples is
        ; its own code: 0000D9EB-0000DA05 is one sample, repeated with the
        ; horizon slot as a falling displacement - [esp+0x77], [esp+0x76] ...
        ; - and the `ja` target stepping 48 bytes to that column's emitter.
        ; Unrolling all 192 would not fit the 68030's 256-byte instruction
        ; cache, so the column is a walking horizon pointer instead: -(a3)
        ; for the falling half, (a3)+ for the rising one.
        move.l  ring_cx,d5
        move.l  ring_cy,d6
        move.l  ring_lat_x,d0
        neg.l   d0
        move.l  d0,a1
        move.l  ring_lat_y,d0
        neg.l   d0
        move.l  d0,a2
        tst.w   terrain_lowres
        bne     .low_one

        ; 192 columns, 95 down to 0.
        lea     ring_hz+TERRAIN_CENTRE+1,a3
        moveq   #TERRAIN_CENTRE,d7
.one
        TERRAIN_SAMPLE
        cmp.b   -(a3),d2                        ; 0000D9FB cmp ah,[esp+0x77-n]
        bhi.s   .one_paint                      ; 0000D9FF ja
.one_next
        add.l   a1,d5                           ; 0000DA05 sub edx,esi
        add.l   a2,d6                           ; 0000DA07 sub edi,ebp
        dbra    d7,.one
        bra     .two_start
.one_paint
        TERRAIN_PAINT 0,1
        bra.s   .one_next

.two_start
        move.l  ring_cx,d5
        move.l  ring_cy,d6
        move.l  ring_lat_x,a1
        move.l  ring_lat_y,a2
        add.l   a1,d5                           ; the second half steps before
        add.l   a2,d6                           ; its first sample
        ; 192 columns, 96 up to 191.
        lea     ring_hz+TERRAIN_CENTRE+1,a3
        moveq   #TERRAIN_COLS-TERRAIN_CENTRE-2,d7
.two
        TERRAIN_SAMPLE
        cmp.b   (a3)+,d2
        bhi.s   .two_paint
.two_next
        add.l   a1,d5
        add.l   a2,d6
        dbra    d7,.two
        bra     .archive
.two_paint
        TERRAIN_PAINT -1,1
        bra.s   .two_next

        ; Low detail samples every OTHER source column and gives each sample
        ; the pair (c, c+1). 0000F320's block is 0000AF50's with a second
        ; occlusion store - `mov [esp+0x76],ah` AND `mov [esp+0x77],ah` - so
        ; one marched column owns two of the 192 entries, and its compose
        ; byte is duplicated into the other block at 0001453D. The pair is
        ; always (even, odd), which is why the sweep starts one column in
        ; from the centre: 0000F320 carries compose column 63, the block-A
        ; byte of source column 94, not 95. Both entries of a pair always
        ; hold the same value, so the test reads the even one.
.low_one
        lea     ring_hz+TERRAIN_CENTRE-1,a3     ; 94, the even one of (94,95)
        moveq   #(TERRAIN_CENTRE+1)/2-1,d7
.lone
        TERRAIN_SAMPLE
        cmp.b   (a3),d2
        bhi.s   .lone_paint
.lone_next
        subq.l  #2,a3
        add.l   a1,d5
        add.l   a2,d6
        dbra    d7,.lone
        bra     .low_two_start
.lone_paint
        TERRAIN_PAINT 0,2
        bra.s   .lone_next

.low_two_start
        move.l  ring_cx,d5
        move.l  ring_cy,d6
        move.l  ring_lat_x,a1
        move.l  ring_lat_y,a2
        add.l   a1,d5
        add.l   a2,d6
        lea     ring_hz+TERRAIN_CENTRE+1,a3     ; 96
        moveq   #(TERRAIN_COLS-TERRAIN_CENTRE-1)/2-1,d7
.ltwo
        TERRAIN_SAMPLE
        cmp.b   (a3),d2
        bhi.s   .ltwo_paint
.ltwo_next
        addq.l  #2,a3
        add.l   a1,d5
        add.l   a2,d6
        dbra    d7,.ltwo
        bra     .archive
.ltwo_paint
        TERRAIN_PAINT 0,2
        bra.s   .ltwo_next

        ; The ring's finished horizon is archived, one 192-byte row per ring.
        ; 0000F2E5-0000F2FF does exactly this before restoring the ring centre:
        ; esi = the stack array, edi = [00019E60] + ring*256 + 0x20, and a
        ; 0x30-dword `rep movsd` copies all 192 bytes out. The sprite blitter
        ; reads it back at 000254CF to clip a model against the terrain in
        ; front of it, which is why it is kept and not just a debug trace.
.archive
        move.l  ring_silp,a2
        lea     ring_hz,a1
        moveq   #TERRAIN_COLS/16-1,d0
.save
        move.l  (a1)+,(a2)+
        move.l  (a1)+,(a2)+
        move.l  (a1)+,(a2)+
        move.l  (a1)+,(a2)+
        dbra    d0,.save
        move.l  a2,ring_silp

        subq.w  #1,ring_counter
        bne     .ring

        movem.l (sp)+,d2-d7/a0-a6
        rts

        text
        even
; RING_PAGE_ANCHOR as a linkable word: it comes from the generated include,
; which object.s does not pull in, and the targetability test needs it to
; turn a stored screen row back into a page row.
;
; In TEXT, not BSS. A dc.w in a bss section is zero-filled at load - the
; loader does not carry initialisers from there - which is the same trap
; menu_settings hit, and here it would silently make the anchor 0 and invert
; every terrain-occlusion comparison.
render_page_anchor
        dc.w    RING_PAGE_ANCHOR
        even

; -q * SCREEN_STRIDE for page rows q = 0..255: a span's top row is page row
; p - 1, and its address is the column's page-row-0 address plus this. In
; TEXT beside render_page_anchor, for the reason it gives.
        cnop    0,4
ring_rowneg
ring_rowneg_q   set     0
        rept    256
        dc.l    -ring_rowneg_q*SCREEN_STRIDE
ring_rowneg_q   set     ring_rowneg_q+1
        endr

; The target view's sky: 0001C920.
;
; 0001B29C calls it through [0x19C9C] before the first ring. Forty iterations,
; one per column pair from the right (dl = 0x53 down to 0x2C, edi = 0x4F down
; to 0), each taking the next-but-one of the sky bank's 512 column strips of
; 150 bytes: `add esi, 0x5A` skips the strip's first 90 bytes, 60 `lodsb` store
; the rest downward from page row 0xA5 + [0x3CB78 + edi] (the horizon bytes
; 0001B295 has just zeroed, so 0xA5), and `add esi, 0x96` steps over the
; strip in between. The strip origin is ((~[0x19D00] - 0x14000000) >> 23) * 150
; and a strip pointer reaching the end of the bank wraps to its start.
; 000079F0 then reads page row 162 - 2r for panel row r, so panel row r takes
; strip byte 93 + 2r (rows 0..28; the strip ends there), and each column pair
; gets one byte for both its pixels. Without a sky bank 0001CAD0 paints the
; flat viewport colour instead, which is what the panel's base already holds.
;
; In:  d3.l = the view angle (the DOS [0x19D00])
; DOS: flat 0001C920-0001CAC0, the target view's sourced sky fill.
; DOS symbol: loc_0001C920
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: the same strips, rows and pairing, written straight into the panel.
; Preserved: the strip origin and step, the 60-byte tail of each strip, the
;   wrap at the end of the bank, and the panel row to page row relation.
; Kind: translated.
; Status: ported; checked against record 20's panel.
mfd_target_sky
        tst.w   sky_paint
        beq     .out
        movem.l d0-d7/a0-a3,-(sp)
        move.l  d3,d0
        not.l   d0
        subi.l  #$14000000,d0                   ; 0001C946-0001C948
        moveq   #23,d1
        lsr.l   d1,d0                           ; 0001C94D
        andi.w  #SKY_STRIPS-1,d0                ; the first strip
        lea     sky_palette,a2
        move.l  work_screen,a3
        lea     MFD_Y*SCREEN_STRIDE+MFD_SURFACE_X*2(a3),a3
        move.w  mfd_body_offset,d1              ; 000079FB + [0x19CA8]
        add.w   d1,d1
        adda.w  d1,a3
        moveq   #MFD_VIEW_COLS/2-1,d7           ; 0001C92F: 40 pairs
        moveq   #MFD_VIEW_COLS-2,d6             ; the right-most pair's left pixel
.pair
        lea     sky_image,a0
        adda.w  d0,a0                           ; strip d0
        adda.l  #93*SKY_STRIPS,a0                      ; strip byte 93: panel row 0
        move.l  a3,a1
        move.w  d6,d1
        add.w   d1,d1
        adda.w  d1,a1                           ; the pair's left pixel
        moveq   #28,d5                          ; rows 0..28
.row
        moveq   #0,d1
        move.b  (a0),d1
        add.w   d1,d1
        move.w  0(a2,d1.w),d2                   ; 0001C970 lodsb / 0001C971 store
        move.w  d2,(a1)
        move.w  d2,2(a1)
        adda.l  #2*SKY_STRIPS,a0                ; two strip bytes per panel row
        adda.w  #SCREEN_STRIDE,a1
        dbra    d5,.row
        addq.w  #2,d0                           ; 0001C957/0001CAA1: strip + 2
        andi.w  #SKY_STRIPS-1,d0                ; 0001CA9A/0001CAA7 wrap
        subq.w  #2,d6
        dbra    d7,.pair
        movem.l (sp)+,d0-d7/a0-a3
.out
        rts

; The target view's marcher: 0001B26C.
;
; This is 0000D950 - the routine tools/compare-marcher.py reproduces exactly,
; 17248/17248 columns - with four changes, and nothing else differs. The
; inner loop is instruction-for-instruction the same: the `shld` index pair,
; `add al, gs:[ebx]` in byte arithmetic, `mov ah,[eax]` through the ring's
; projection page, the strict `ja` against the column's occlusion, and
; `sub edx,esi` / `sub edi,ebp` to step.
;
;   1. 80 columns, not 192. 0001B2AA reserves 0x50 bytes of stack where
;      0000D976 reserves 0xC0.
;   2. The forward step is TWO rings: 0001B2DF/0001B2E6 add
;      [ecx*4 + 0x1A2CC] and [ecx*4 + 0x1A2D0] before the multiply, so the
;      view walks the depth table two entries at a time.
;   3. The lateral step is DOUBLED: 0001B308/0001B319 shift B left by one.
;   4. Samples come in COLUMN PAIRS. The compares are [esp+0x3E] then
;      [esp+0x3C] - a step of two where the main view's were 0x77 then 0x76 -
;      and the span writer at 0001C1B0/0001C1B4 stores the new occlusion into
;      BOTH [esp+0x3E] and [esp+0x3F]. So one sample covers two adjacent
;      columns and the compare only ever reads the even one. 40 samples, 80
;      columns. Reading the step of two without the paired store would give a
;      striped picture and a wrong model.
;
; Difference: the original substitutes its camera globals around the call
;   (00007860 pushes eight dwords, overwrites [00019CD4]/[00019CD8]/
;   [00019DFC]/[00019D00]/[00019CF0]/[00019CF4] and pops them back) because
;   its marcher reads them from fixed addresses. This takes them as
;   arguments instead, which is the same computation without the save and
;   restore; the caller therefore does not need 00007860's eight pushes.
;
; In:  d0 = camera X, d1 = camera Y, both raw 10.22
;      d2.b = altitude, d3.l = view angle
; Out: mfd_view_occl holds 80 bytes of page rows for the view.
; DOS: flat 0001B26C-0001B34F, the target view's 80-column marcher.
; DOS symbol: sub_0001B26C
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: marches the recovered 80-column view from a supplied camera.
; Preserved: ring order, the doubled forward and lateral steps, the paired
;   column store, the page lookup, the byte-wide altitude bias, and the
;   strict horizon test.
; Kind: translated.
; Status: ported; called by mfd_draw_target_view after the target latch gate.
;   Its 80-column archive is also consumed by the secondary object pass for
;   the target sprite's per-ring terrain clip.
mfd_march_target_view
        movem.l d0-d7/a0-a6,-(sp)

        ; 0001B29C: `call [0x19C9C]` - the sky fill, before anything marches.
        bsr     mfd_target_sky

        ; 0001B272: the basis comes from the angle's top nine bits, indexing
        ; the same table the flight view uses - 0001B275's stride is 4 and
        ; 00007900 stores the bearing as bearing << 24, so (angle >> 23) * 4
        ; is the same entry sine_q31 gives.
        move.l  d3,d4
        moveq   #23,d5
        lsr.l   d5,d4
        lsl.l   #2,d4
        lea     sine_q31,a4
        move.l  0(a4,d4.l),d6                   ; [00019CB0]
        move.l  512(a4,d4.l),d7                 ; [00019CB4]
        move.l  d6,mfd_view_sin
        move.l  d7,mfd_view_cos

        ; 0001B2D0: the page-index bias, byte-wide, exactly as 0000D98C.
        andi.w  #$00ff,d2
        lsr.w   #1,d2
        neg.w   d2
        addi.w  #127,d2
        andi.w  #$00ff,d2
        move.w  d2,mfd_view_camh

        ; 0001B2AD: the occlusion starts at page row 0 for every column.
        lea     mfd_view_occl,a0
        move.w  #MFD_VIEW_COLS/4-1,d4
.clear
        clr.l   (a0)+
        dbra    d4,.clear

        move.l  d0,mfd_view_cx
        move.l  d1,mfd_view_cy
        move.l  #ring_a_table,mfd_view_ap
        move.l  #ring_b_table,mfd_view_bp
        move.l  #ring_page_table,mfd_view_hp
        ; THREE rings per step, not two: 0001B883 closes the loop with
        ; `add ecx,3 / cmp ecx,[0x19EE0] / jb`, and 0001B838 advances the
        ; projection page by the same 3. The forward step really does read
        ; only A[i] + A[i+1] against that - 0001B2DF/0001B2E6 - so the ring
        ; index runs ahead of the distance the walk actually covered; that is
        ; the original's arithmetic and it is kept.
        moveq   #0,d0
        move.w  ring_steps,d0
        divu.w  #3,d0
        move.w  d0,mfd_view_counter
        clr.w   mfd_view_ring

.ring
        ; 0001B2DF/0001B2E6: A[i] + A[i+1].
        move.l  mfd_view_ap,a0
        move.l  (a0)+,d0
        add.l   (a0)+,d0
        addq.l  #4,a0                           ; 0001B883: the index steps 3
        move.l  a0,mfd_view_ap
        move.l  d0,d4                           ; the doubled forward step

        move.l  d4,d0
        move.l  mfd_view_sin,d3
        bsr     ring_mul_q31_raw
        add.l   d0,mfd_view_cx                  ; 0001B2F4: edi += edx
        move.l  d4,d0
        move.l  mfd_view_cos,d3
        bsr     ring_mul_q31_raw
        sub.l   d0,mfd_view_cy                  ; 0001B2FD: ebx -= edx

        ; 0001B301/0001B312: B[i] << 1. The B cursor advances by three as
        ; well, because the ring index ecx is shared with the forward step.
        move.l  mfd_view_bp,a0
        move.l  (a0)+,d0
        addq.l  #8,a0
        move.l  a0,mfd_view_bp
        add.l   d0,d0                           ; shl eax, 1
        move.l  d0,d4
        move.l  mfd_view_sin,d3
        bsr     ring_mul_q31_raw
        move.l  d0,mfd_view_lat_y               ; esi
        move.l  d4,d0
        move.l  mfd_view_cos,d3
        bsr     ring_mul_q31_raw
        move.l  d0,mfd_view_lat_x               ; ebp

        ; This ring's projection page, advanced three entries with the rings:
        ; 0001B838 `add word [0x19EDD], 3` moves the pointer by 3 * 0x100.
        move.l  mfd_view_hp,a0
        move.l  a0,mfd_view_page
        adda.w  #768,a0
        move.l  a0,mfd_view_hp

        lea     original_height_map,a4
        lea     mfd_view_occl,a3
        ; The same pair the flight marcher samples through - without these
        ; the span writer reads whatever the caller left in a5/a6 as a
        ; colour map and a palette.
        lea     original_colour_map,a5
        lea     flight_palette,a6
        move.w  mfd_view_camh,d4

        ; The two half-sweeps, as 0000D9B9/0000D9BA and 0000E5ED do: the
        ; first takes the centre pair and steps outward subtracting, the
        ; second steps first and adds.
        move.l  mfd_view_cx,d5
        move.l  mfd_view_cy,d6
        move.l  mfd_view_lat_x,d0
        neg.l   d0
        move.l  d0,a1
        move.l  mfd_view_lat_y,d0
        neg.l   d0
        move.l  d0,a2
        move.w  #-2,mfd_view_colstep
        move.w  #MFD_VIEW_CENTRE,d2
        move.w  #MFD_VIEW_COLS/4,mfd_view_colcount
        bsr     .half

        move.l  mfd_view_cx,d5
        move.l  mfd_view_cy,d6
        move.l  mfd_view_lat_x,a1
        move.l  mfd_view_lat_y,a2
        add.l   a1,d5
        add.l   a2,d6
        move.w  #2,mfd_view_colstep
        move.w  #MFD_VIEW_CENTRE+2,d2
        move.w  #MFD_VIEW_COLS/4,mfd_view_colcount
        bsr     .half

        ; 0001B84E copies this step's 0x50-byte target silhouette into the
        ; shared per-ring archive at source offset 0x58. Keep the same
        ; ring-local rows, expanded to Falcon screen coordinates, for the
        ; secondary 00024B17 pass. The target marcher advances three source
        ; rings per step; fill the three corresponding Falcon records so an
        ; object using any ring in that interval sees the same recovered
        ; silhouette rather than the final horizon for the whole view.
        move.w  mfd_view_ring,d0
        mulu    #MFD_VIEW_COLS*2,d0
        lea     mfd_target_silhouette,a1
        adda.w  d0,a1
        moveq   #2,d7
.target_archive_ring
        lea     mfd_view_occl,a0
        move.w  #MFD_VIEW_COLS-1,d0
.target_archive_col
        moveq   #0,d1
        move.b  (a0)+,d1
        move.w  #MFD_VIEW_TOP_ROW,d2
        sub.w   d1,d2
        bpl     .target_archive_row
        moveq   #0,d2
.target_archive_row
        lsr.w   #1,d2
        addi.w  #MFD_Y,d2
        cmpi.w  #MFD_Y,d2
        bcc     .target_archive_top_ok
        move.w  #MFD_Y,d2
.target_archive_top_ok
        cmpi.w  #MFD_Y+MFD_H,d2
        bls     .target_archive_bottom_ok
        move.w  #MFD_Y+MFD_H,d2
.target_archive_bottom_ok
        move.w  d2,(a1)+
        dbra    d0,.target_archive_col
        adda.w  #MFD_VIEW_COLS*2,a1
        dbra    d7,.target_archive_ring
        addq.w  #3,mfd_view_ring

        subq.w  #1,mfd_view_counter
        bne     .ring

        movem.l (sp)+,d0-d7/a0-a6
        rts

.half
.col
        ; 0001B338: the same shld pair - Y's ten bits above X's ten.
        moveq   #22,d1
        move.l  d5,d0
        lsr.l   d1,d0
        move.l  d6,d3
        lsr.l   d1,d3
        lsl.l   #8,d3
        lsl.l   #MAP_SHIFT-8,d3
        add.l   d3,d0
        move.l  d0,a0
        move.l  d0,mfd_view_index               ; kept for the colour below

        ; 0001B340/0001B343: height onto the bias in byte arithmetic, then
        ; the page yields the row.
        moveq   #0,d1
        move.b  0(a4,a0.l),d1
        add.w   d4,d1
        andi.w  #$00ff,d1
        move.l  mfd_view_page,a0
        moveq   #0,d0
        move.b  0(a0,d1.w),d0

        ; 0001B345: strict `ja` against this column's occlusion.
        moveq   #0,d3
        move.b  0(a3,d2.w),d3
        cmp.w   d3,d0
        bls     .hidden
        bsr     .span
        ; 0001C1B0/0001C1B4: the pair, both entries.
        move.b  d0,0(a3,d2.w)
        move.b  d0,1(a3,d2.w)
.hidden
        add.l   a1,d5
        add.l   a2,d6
        add.w   mfd_view_colstep,d2
        subq.w  #1,mfd_view_colcount
        bne     .col
        rts

; One column pair of terrain, from the old horizon up to the new one.
;
; The original marches into the shared 256x256 surface through the same span
; writer the main view uses, and 000079F0 then halves it into the panel -
; -0x200 per panel row is two surface rows, walking down from row 162, and
; every second source byte across. This writes the halved result straight
; into the panel, which is the same picture without the intermediate surface.
;
;   panel row = (MFD_VIEW_TOP_ROW - page row) >> 1, MFD_VIEW_TOP_ROW = 162 + 2:
;   a span covers page rows [old, new) and the panel samples row 162 - 2r (the
;   derivation is in the shared include).
;
; In: d0 = the new page row, d3 = the old one, d2 = the left column of the
; pair. Everything is preserved.
.span
        movem.l d0-d7/a0-a2,-(sp)
        ; The colour at this step, exactly as the main marcher samples it.
        move.l  mfd_view_index,a0
        moveq   #0,d1
        move.b  0(a5,a0.l),d1
        add.w   d1,d1
        move.w  0(a6,d1.w),d7

        ; Top of the span, from the new page row - clamped to the top of the
        ; window, not discarded above it. The original writes the whole span
        ; into the shared 256x256 surface and 000079F0 then copies the 44-row
        ; window out of it, so a span whose top is above row 162 still paints
        ; every row inside the window. Collapsing those two steps means
        ; intersecting the span with the window, which clamps both ends; the
        ; bottom below already does, and rejecting here instead threw away
        ; exactly the spans that fill the panel. A ground-level camera makes
        ; that the common case rather than an edge: 0001B2D0 takes the page
        ; index bias from the TARGET's altitude, so terrain level with the
        ; camera reads page 255 on every ring below about 6, and the panel
        ; stayed black with a marcher that was working.
        move.w  #MFD_VIEW_TOP_ROW,d1
        sub.w   d0,d1
        bpl     .top_in_window
        moveq   #0,d1
        bra     .top_ready
.top_in_window
        lsr.w   #1,d1
        cmpi.w  #MFD_H,d1
        bcc     .span_out                       ; wholly below the window
.top_ready

        ; Bottom, from the old page row, clamped to the panel.
        move.w  #MFD_VIEW_TOP_ROW,d6
        sub.w   d3,d6
        bpl     .bottom_positive
        moveq   #0,d6
.bottom_positive
        lsr.w   #1,d6
        cmpi.w  #MFD_H,d6
        bcs     .bottom_ready
        move.w  #MFD_H,d6
.bottom_ready
        sub.w   d1,d6                           ; rows to paint
        ble     .span_out

        move.l  work_screen,a0
        move.w  d1,d0
        mulu    #SCREEN_STRIDE,d0
        adda.l  d0,a0
        adda.l  #MFD_Y*SCREEN_STRIDE,a0
        move.w  d2,d0
        add.w   d0,d0
        adda.w  d0,a0
        adda.w  #MFD_SURFACE_X*2,a0
        move.w  mfd_body_offset,d0              ; 000079FB + [0x19CA8]
        add.w   d0,d0
        adda.w  d0,a0
        subq.w  #1,d6
.span_row
        move.w  d7,(a0)                         ; the pair, as 0001C1B4 does
        move.w  d7,2(a0)
        adda.w  #SCREEN_STRIDE,a0
        dbra    d6,.span_row
.span_out
        movem.l (sp)+,d0-d7/a0-a2
        rts

; high32(d0 * d3), with d0 a DOS 10.22 .DTL increment and d3 a Q31 angle.
; This IS the original increment: 0000D9A2's `imul` keeps edx, and that edx
; is added to the 10.22 coordinate unshifted. An earlier revision shifted the
; high word by five "to 16.16", which both halved the DOS step (10.22 to
; 16.16 is six bits, not five) and threw away the low-bit exactness; the
; walk now stays in 10.22 so no conversion exists to get wrong.
; DOS: helper inside 0000D950-0000F317, signed high-word product path.
; DOS symbol: inside loc_0000D94C
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: retains the 68030 high 32 bits of the recovered fixed-point product.
; Preserved: signedness, truncation, and intermediate precision.
; Kind: translated.
; Status: ported; exact on every CPU - native 64-bit MULS.L below a 68060,
;   four 16x16 products on it.
ring_mul_q31_raw
        movem.l d1,-(sp)
        MulS64  d3
        move.l  d1,d0
        move.l  (sp)+,d1
        rts

    ifne PARITY_TILE
; ---------------------------------------------------------------------------
; DSP-kernel parity marcher.
;
; Renders the terrain with the kernel's own arithmetic: the 2.22 fan basis,
; 11.13 walking positions, the (dz * rscale) >> 15 projection against the
; generated par_projection table, toroidal 64x64 windows over the map and the
; decimated far pair, and spans of [row+1, occ] - the original's convention,
; where the projected row goes to the next deeper sample. A USE_DSP capture
; diffs against this build pixel for pixel; where this file's render_terrain
; disagrees with the kernel by design - depth schedule, far decimation, the
; floor row painted - this marcher follows the kernel, and render_terrain
; stays the oracle for the game.
;
; Clarity over speed throughout: this is a diagnostic build, and Hatari's
; --mmu core charges instruction execution nothing anyway.
; ---------------------------------------------------------------------------

        ifne    FIX_POS-13
        fail    "parity marcher shifts assume FIX_POS is 13"
        endc
        ifne    FIX_POS+TILE_FAR_SHIFT-15
        fail    "parity marcher shifts assume a 15-bit far index shift"
        endc
; par_span handles the recovered geometry: each DOS source column expands to
; two adjacent RGB565 pixels and the host fill stores the pair as one longword.

; The decimated far map's geometry, kept in step with dsp_host.s.
PAR_DEC_MASK    = ((MAP_MASK+1)>>TILE_FAR_SHIFT)-1

        ifne    PAR_DEC_MASK-255
        fail    "parity far row shift assumes a 256-cell decimated map"
        endc

; DOS: no separate routine; diagnostic partner of 0000D950.
; DOS symbol: inside loc_0000D94C
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: executes the DSP tile/window arithmetic on the CPU for parity testing.
; Preserved: command geometry, fixed-point windows, samples, and span records.
; Kind: adapted - diagnostic build path.
; Status: ported; it does not select game behavior.
render_terrain_parity
        movem.l d2-d7/a0-a6,-(sp)

        ; The kernel's camera and window bases, formed exactly as dsp_host.s
        ; forms them: 16.16 world down to 11.13, integer cells minus half a
        ; window for the bases.
        move.l  player_x,d0
        asr.l   #3,d0
        move.l  d0,par_camx
        move.l  player_y,d0
        asr.l   #3,d0
        move.l  d0,par_camy
        move.l  player_x,d0
        moveq   #16,d1
        asr.l   d1,d0
        move.l  d0,d2
        subi.l  #TILE_NEAR_SIZE/2,d2
        move.l  d2,par_nbx
        asr.l   #TILE_FAR_SHIFT,d0
        subi.l  #TILE_FAR_SIZE/2,d0
        move.l  d0,par_fbx
        move.l  player_y,d0
        asr.l   d1,d0
        move.l  d0,d2
        subi.l  #TILE_NEAR_SIZE/2,d2
        move.l  d2,par_nby
        asr.l   #TILE_FAR_SHIFT,d0
        subi.l  #TILE_FAR_SIZE/2,d0
        move.l  d0,par_fby

        ; The FIX_DIR basis, exactly as dsp_render forms it: the right pair
        ; scaled by the original's fan half-width with the identical
        ; muls/asr, the forward pair unit.
        moveq   #0,d1
        move.w  player_heading,d1
        andi.w  #$00ff,d1
        add.w   d1,d1
        lea     sin_table,a0
        move.w  0(a0,d1.w),d2                   ; sin
        move.w  128(a0,d1.w),d3                 ; cos
        muls    #FAN_HALF_TAN,d2
        muls    #FAN_HALF_TAN,d3
        asr.l   #1,d2
        asr.l   #1,d3
        move.l  d3,par_rightx                   ; right = 0.96 * (cos, -sin)
        move.l  d2,d0
        neg.l   d0
        move.l  d0,par_righty
        move.l  d3,d4                           ; keep the scaled pair for
        move.l  d2,d5                           ; the fan edges
        move.w  0(a0,d1.w),d2                   ; sin again, unit this time
        move.w  128(a0,d1.w),d3                 ; cos
        ext.l   d2
        ext.l   d3
        moveq   #14,d1
        asl.l   d1,d2
        asl.l   d1,d3
        move.l  d2,d0                           ; fan start = dir - right,
        sub.l   d4,d0                           ; dir = (sin, cos)
        move.l  d0,par_fanx
        move.l  d3,d0
        add.l   d5,d0
        move.l  d0,par_fany

        ; Fan step = (right * FIX_FAN_STEP) >> 23: the kernel's fractional
        ; mpy, done wide and shifted down to the same bits.
        move.l  #FIX_FAN_STEP,d0
        MulS64  par_rightx
        moveq   #23,d2
        lsr.l   d2,d0
        moveq   #9,d2
        lsl.l   d2,d1
        or.l    d1,d0
        move.l  d0,par_fanstepx
        move.l  #FIX_FAN_STEP,d0
        MulS64  par_righty
        moveq   #23,d2
        lsr.l   d2,d0
        moveq   #9,d2
        lsl.l   d2,d1
        or.l    d1,d0
        move.l  d0,par_fanstepy

        clr.l   par_col
.pcol
        ; Per-column deltas, near and far both shifted from the fan as the
        ; kernel derives them - the far delta independently, not <<3 of the
        ; truncated near delta.
        move.l  par_fanx,d0
        moveq   #FIX_DIR-FIX_POS,d1
        asr.l   d1,d0
        move.l  d0,par_stepnx
        move.l  par_fanx,d0
        moveq   #FIX_DIR-FIX_POS-TILE_FAR_SHIFT,d1
        asr.l   d1,d0
        move.l  d0,par_stepfx
        move.l  par_fany,d0
        moveq   #FIX_DIR-FIX_POS,d1
        asr.l   d1,d0
        move.l  d0,par_stepny
        move.l  par_fany,d0
        moveq   #FIX_DIR-FIX_POS-TILE_FAR_SHIFT,d1
        asr.l   d1,d0
        move.l  d0,par_stepfy
        move.l  par_fanx,d0
        moveq   #FIX_DIR-FIX_POS-TILE_FAR2_SHIFT,d1
        asr.l   d1,d0
        move.l  d0,par_stepf2x
        move.l  par_fany,d0
        moveq   #FIX_DIR-FIX_POS-TILE_FAR2_SHIFT,d1
        asr.l   d1,d0
        move.l  d0,par_stepf2y

        move.l  par_camx,d5                     ; walking position
        move.l  par_camy,d6
        move.l  par_stepnx,d3
        move.l  par_stepny,d4
        ; The kernel receives the DOS page-row seed for every source column;
        ; this parity marcher uses the same fixed value. It is not the
        ; console-floor clip: the DOS zeroed horizon array before the march.
        moveq   #0,d7
        move.w  #TERRAIN_PAGE_ANCHOR-1,d7       ; host upload / kernel ybuffer
        lea     original_height_map,a2
        lea     original_colour_map,a3
        lea     par_projection,a4
        move.w  #MARCH_NEAR_STEPS-1,d2
.pnear
        add.l   d3,d5
        add.l   d4,d6
        ; near index (pos >> 13) & 63, then the window transform: the world
        ; cell in the window whose residue this is - which is also how a ray
        ; that leaves the window wraps, exactly as the kernel's mask wraps it
        move.l  d5,d0
        asr.l   #8,d0
        asr.l   #5,d0
        andi.l  #TILE_NEAR_MASK,d0
        sub.l   par_nbx,d0
        andi.l  #TILE_NEAR_MASK,d0
        add.l   par_nbx,d0
        andi.l  #MAP_MASK,d0
        move.l  d6,d1
        asr.l   #8,d1
        asr.l   #5,d1
        andi.l  #TILE_NEAR_MASK,d1
        sub.l   par_nby,d1
        andi.l  #TILE_NEAR_MASK,d1
        add.l   par_nby,d1
        andi.l  #MAP_MASK,d1
        lsl.l   #8,d1
        lsl.l   #2,d1
        add.l   d1,d0                           ; source index
        move.b  0(a3,d0.l),par_colour
        moveq   #0,d1
        move.b  0(a2,d0.l),d1                   ; height
        moveq   #0,d0
        move.b  player_altitude,d0
        asr.w   #1,d0                           ; the original's alt/2 + 1 in
        addq.w  #1,d0                           ; map bytes - the AL bias -
        ext.l   d0                              ; as the host sends it
        sub.l   d1,d0                           ; dz
        muls.l  (a4)+,d0                        ; * rscale
        moveq   #15,d1
        asr.l   d1,d0
        add.l   (a4)+,d0                        ; + bias (horizon trim is 0)
        bpl     .pn_clamped
        moveq   #-1,d0                          ; clamp to -1: the top row
.pn_clamped
        cmp.l   d7,d0
        bge     .pn_hidden
        bsr     par_span
        move.l  d0,d7                           ; occlusion row moves up
.pn_hidden
        dbra    d2,.pnear

        ; Far phase: the coarser delta, the decimated pair, 8-unit cells.
        move.l  par_stepfx,d3
        move.l  par_stepfy,d4
        lea     dsp_far_height,a2
        lea     dsp_far_colour,a3
        move.w  #MARCH_FAR_STEPS-1,d2
.pfar
        add.l   d3,d5
        add.l   d4,d6
        move.l  d5,d0
        asr.l   #8,d0
        asr.l   #7,d0                           ; pos >> 15: 4-unit cells
        andi.l  #TILE_FAR_MASK,d0
        sub.l   par_fbx,d0
        andi.l  #TILE_FAR_MASK,d0
        add.l   par_fbx,d0
        andi.l  #PAR_DEC_MASK,d0
        move.l  d6,d1
        asr.l   #8,d1
        asr.l   #7,d1
        andi.l  #TILE_FAR_MASK,d1
        sub.l   par_fby,d1
        andi.l  #TILE_FAR_MASK,d1
        add.l   par_fby,d1
        andi.l  #PAR_DEC_MASK,d1
        lsl.l   #8,d1                           ; 256-cell decimated rows
        add.l   d1,d0
        move.b  0(a3,d0.l),par_colour
        moveq   #0,d1
        move.b  0(a2,d0.l),d1
        moveq   #0,d0
        move.b  player_altitude,d0
        asr.w   #1,d0
        addq.w  #1,d0                           ; alt/2 + 1, the AL bias
        ext.l   d0
        sub.l   d1,d0
        muls.l  (a4)+,d0
        moveq   #15,d1
        asr.l   d1,d0
        add.l   (a4)+,d0
        bpl     .pf_clamped
        moveq   #-1,d0                          ; clamp to -1: the top row
.pf_clamped
        cmp.l   d7,d0
        bge     .pf_hidden
        bsr     par_span
        move.l  d0,d7
.pf_hidden
        dbra    d2,.pfar

        ; Far2 phase: the whole-map tile, 16-unit cells, packed words. No
        ; window transform and no re-basing pair: this marcher already walks
        ; world coordinates - the kernel's VL_F2OFF exists because its
        ; command position is rebased - and the field masks read the same
        ; bits either way. At 16:1 the 64-cell tile IS the torus.
        move.l  par_stepf2x,d3
        move.l  par_stepf2y,d4
        lea     dsp_far2_tile,a2
        move.w  #MARCH_FAR2_STEPS-1,d2
.pfar2
        add.l   d3,d5
        add.l   d4,d6
        move.l  d5,d0
        moveq   #17,d1
        asr.l   d1,d0                           ; pos >> 17: 16-unit cells
        andi.l  #TILE_FAR_MASK,d0
        move.l  d6,d1
        asr.l   #8,d1
        asr.l   #8,d1
        asr.l   #1,d1
        andi.l  #TILE_FAR_MASK,d1
        lsl.l   #6,d1
        add.l   d1,d0
        add.l   d0,d0                           ; word index
        move.w  0(a2,d0.l),d1                   ; packed height:colour
        move.b  d1,par_colour
        lsr.w   #8,d1
        andi.l  #$000000ff,d1
        moveq   #0,d0
        move.b  player_altitude,d0
        asr.w   #1,d0
        addq.w  #1,d0                           ; alt/2 + 1, the AL bias
        ext.l   d0
        sub.l   d1,d0
        muls.l  (a4)+,d0
        moveq   #15,d1
        asr.l   d1,d0
        add.l   (a4)+,d0
        bpl     .pf2_clamped
        moveq   #-1,d0                          ; clamp to -1: the top row
.pf2_clamped
        cmp.l   d7,d0
        bge     .pf2_hidden
        bsr     par_span
        move.l  d0,d7
.pf2_hidden
        dbra    d2,.pfar2

        ; Advance the fan and the column.
        move.l  par_fanx,d0
        add.l   par_fanstepx,d0
        move.l  d0,par_fanx
        move.l  par_fany,d0
        add.l   par_fanstepy,d0
        move.l  d0,par_fany
        addq.l  #1,par_col
        cmpi.l  #TERRAIN_COLS,par_col
        blt     .pcol

        movem.l (sp)+,d2-d7/a0-a6
        rts

; Fill rows d0+1 .. d7 of column par_col with par_colour: the kernel's span
; convention, one below the projected row down to the stored occlusion row
; inclusive - the boundary row goes to the deeper sample, as the DOS
; emitter's [old, new) does. Every register preserved.
; DOS: helper corresponding to the span emission in 00006BF0-00006FEF.
; DOS symbol: inside sub_00006B27
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: composes one parity record into the Falcon RGB565 surface.
; Preserved: record order, occlusion interval, clipping, and source colour.
; Kind: adapted - diagnostic helper.
; Status: ported; CPU oracle remains the game reference.
par_span
        movem.l d0-d5/a0-a1,-(sp)
        moveq   #0,d1
        move.b  par_colour,d1
        add.w   d1,d1
        lea     flight_palette,a0
        move.w  0(a0,d1.w),d3
        move.l  render_target,a1
        addq.l  #1,d0                           ; span starts one below the
        move.l  d0,d4                           ; projected row
        mulu    #SCREEN_STRIDE,d4
        move.l  par_col,d5
        cmpi.l  #TERRAIN_VIEW_FIRST,d5
        blt     .done
        cmpi.l  #TERRAIN_VIEW_LAST,d5
        bgt     .done
        subi.l  #TERRAIN_VIEW_FIRST,d5
        add.l   d5,d5
        add.l   d5,d5                           ; two surface pixels per ray
        add.l   d5,d4
        adda.l  d4,a1
        move.l  d7,d5
        sub.l   d0,d5                           ; occ - (row+1) = count-1
        bmi     .done
        move.w  d3,d4
        swap    d3
        move.w  d4,d3
.row
        move.l  d3,(a1)
        adda.w  #SCREEN_STRIDE,a1
        dbra    d5,.row
.done
        movem.l (sp)+,d0-d5/a0-a1
        rts
    endc

        data
        even

; The selected indexed PNG provides the full 256-entry RGB565 palette. The
; generated include is shared with the DSP host so map indices stay exact.
        include "build/colour_palette.s"

        include "build/original_test.s"
    ifne MARCHER_ORACLE
        include "build/marcher_oracle.s"
    endc

    ifne PARITY_TILE
; The kernel-mirrored projection pairs; regenerated with tables.inc so the
; two cannot drift.
        include "build/dsp_parity.s"
    endc

        bss
        even
; Runtime terrain buffers. resources.s fills these from D1.DTA/C1.DTA before
; the first frame; keeping them in BSS removes the maps from the .TOS file.
original_height_map
        ds.b    1024*1024
        even
original_colour_map
        ds.b    1024*1024
        even
; Logical copy of the DOS terrain surface. It is updated before object/HUD
; composition and restored into whichever Falcon physical buffer is next.
terrain_history
        ds.b    FRAME_BYTES
        even
render_target
        ds.l    1

; The backdrop's per-column vertical offset, and the row it stops at. Both
; are rebuilt once per frame by backdrop_build.
        even
; 000261FE's choice, as a flag rather than a code pointer: '}' at
; [00025DD9] keeps the 192-column marcher 0000D950, anything else installs
; the 96-column 000137F0. Set by dtl_apply_settings, read by the marcher, the
; sky fill and the span writer.
terrain_lowres
        ds.w    1
; 000261CD's choice: '}' at [0x25DD8] installs the three sourced sky fills,
; anything else installs 0x1757E - the flat viewport fill - in all of them.
sky_enabled
        ds.w    1
; 1 while this frame's backdrop is the authored strips rather than that flat
; fill. Local to render_clear; kept in memory because the loop has no spare
; register.
sky_paint
        ds.w    1
        even
backdrop_dy
        ds.w    TERRAIN_COLS
        even
backdrop_base
        ds.w    1
        even
mfd_nolock_buf
        ds.w    80*44
        even
; The columns 0..15 and 176..191 the window does not show; see COLBASE.
        cnop    0,4
margin_left
        ds.b    TERRAIN_VIEW_ROWS*SCREEN_STRIDE
margin_right
        ds.b    TERRAIN_VIEW_ROWS*SCREEN_STRIDE
shear_row
        ds.b    (16+SCREEN_WIDTH/2+16)*4
        even
; 0001B26C's own state. Its occlusion array is the original's 0x50 bytes of
; stack; the cursors match the flight marcher's, which live in memory for the
; same reason - the column loop needs the address registers.
mfd_view_occl
        ds.b    MFD_VIEW_COLS
        even
mfd_view_sin
        ds.l    1
mfd_view_cos
        ds.l    1
mfd_view_cx
        ds.l    1
mfd_view_cy
        ds.l    1
mfd_view_ap
        ds.l    1
mfd_view_bp
        ds.l    1
mfd_view_hp
        ds.l    1
mfd_view_page
        ds.l    1
mfd_view_lat_x
        ds.l    1
mfd_view_lat_y
        ds.l    1
mfd_view_index
        ds.l    1
mfd_view_camh
        ds.w    1
mfd_view_counter
        ds.w    1
mfd_view_colstep
        ds.w    1
mfd_view_colcount
        ds.w    1
mfd_view_ring
        ds.w    1
        even
; 0001B84E's target-view silhouette archive, in Falcon screen rows. The DOS
; record is 256 bytes per ring and the rear-view copy occupies source bytes
; 0x58..0xA7; this compact table retains that 80-column window for the live
; 00024B17 target pass, with three records per target marcher step.
mfd_target_silhouette
        ds.w    MFD_VIEW_COLS*RING_STEPS
        even
; The strip the backdrop's left edge sits on this frame, from the heading.
sky_origin
        ds.w    1
sky_strip_cursor
        ds.l    1

; Ring-major marcher state. The Q31 basis and camera height are per frame; the
; raw A/B cursors, projection page, ring origin and lateral step are per ring;
; ring_hz is the per-column running horizon the original keeps in a stack
; array and archives each ring as its sprite-clip silhouette.
        even
ring_fwd_x
        ds.l    1                            ; DOS Q31 sin
ring_fwd_y
        ds.l    1                            ; DOS Q31 cos
ring_a
        ds.l    1                            ; raw DOS 10.22 A_i
ring_b
        ds.l    1                            ; raw DOS 10.22 B_i
ring_cx
        ds.l    1
ring_cy
        ds.l    1
ring_lat_x
        ds.l    1
ring_lat_y
        ds.l    1
ring_ap
        ds.l    1
ring_bp
        ds.l    1
ring_hp
        ds.l    1
        even
ring_camh
        ds.w    1
ring_page
        ds.l    1
ring_counter
        ds.w    1
        even
ring_silp
        ds.l    1
; The running horizon: one byte of page row per DOS source column, the
; original's 0xC0-byte stack array. Longword-aligned for the archive copy.
        cnop    0,4
ring_hz
        ds.b    TERRAIN_COLS
; Per frame: each flight palette entry as an RGB565 pair.
ring_pal32
        ds.l    256
; Per frame, per source column: the lowest and highest page row a span may
; cover (words) and page row 0's surface address (long). See
; render_terrain_ring.
ring_cols
        ds.l    2*TERRAIN_COLS
; One finished horizon per ring, 192 bytes of page rows each - the same
; bytes, in the same units, the original keeps at [00019E60] + ring*256 +
; 0x20, written by 0000F2FF and read back by the sprite blitter at 000254CF.
; The port stores the 192 alone, without the 0x20 lead and the 0x20 tail
; that pad each DOS row to 256.
ring_silhouette
        ds.b    TERRAIN_COLS*RING_STEPS
        even

; Fan interpolation state: the current column's ray step and the per-column
; increment, all 16.16 map units. Written once per frame, read per column.
fan_dx
        ds.l    1
fan_dy
        ds.l    1
fan_step_x
        ds.l    1
fan_step_y
        ds.l    1

    ifne PARITY_TILE
; Parity marcher state, in the kernel's formats: camera and fan in 11.13 and
; 2.22, window bases in cells. Memory rather than registers because the
; marcher spends its registers on the walk and this build's speed is not a
; measurement anyway.
par_camx
        ds.l    1
par_camy
        ds.l    1
par_fanx
        ds.l    1
par_fany
        ds.l    1
par_fanstepx
        ds.l    1
par_fanstepy
        ds.l    1
par_rightx
        ds.l    1
par_righty
        ds.l    1
par_stepnx
        ds.l    1
par_stepny
        ds.l    1
par_stepfx
        ds.l    1
par_stepfy
        ds.l    1
par_stepf2x
        ds.l    1
par_stepf2y
        ds.l    1
par_nbx
        ds.l    1
par_nby
        ds.l    1
par_fbx
        ds.l    1
par_fby
        ds.l    1
par_col
        ds.l    1
par_colour
        ds.b    1
        even
    endc

; The sky's anchor and the terrain's are the same fact seen twice: both come
; from screen row = RING_PAGE_ANCHOR - surface row, the sky through a strip
; index that starts one row below the horizon byte and wraps immediately.
; SKY_TOP_BIAS is 255 - RING_PAGE_ANCHOR and cannot be edited independently -
; moving the anchor without it would slide the backdrop off the terrain.
; Checked here rather than in the header because the anchor arrives with the
; generated include below the code.
    ifne SKY_TOP_BIAS-(255-RING_PAGE_ANCHOR)
        fail "SKY_TOP_BIAS must be 255 - RING_PAGE_ANCHOR"
    endc

        end
