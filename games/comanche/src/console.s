; Route: analysis/functions/falcon-attract.md#frame-driver.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; DOS origin: the console images named inline at the startup manifest -
;   consol1s.dta through consol5s.dta - selected by the console variant byte
;   [00019D86] that gates almost every entry in the cockpit draw region
;   00006FEF-00007BCD.
; Purpose: load one console image and composite it over the flight view.
; Inputs/outputs: console_init loads it; console_draw paints it into the
;   surface in a0. console_status reports why it is absent.
; Original globals/side effects: none carried over. The original blits the
;   console through the same planar routines as everything else.
; Falcon replacement notes: see the geometry note below.
; Validation: a Hatari capture showing the console over the terrain, with the
;   view visible through it.
;
; This is the cockpit, and it is neither of the two banks that look like it.
; CONS.RLE is 57 small instrument elements - gauges, digit strips, lamps - and
; COMA.RLE is the Comanche itself in nine views, which is what the resource
; base [00019E90] the cockpit blitters read actually points at. The console
; surround is a full-screen .DTA image.
;
; Geometry, established by rendering rather than from a header. The file's own
; header words are 327, 289, 320, 200 - the last two the VGA mode - but the
; pixels are 328 to a row, which is the DOS surface pitch: 0x52 bytes per plane
; times four planes. At 320 or 327 the image shears. Unlike a sprite bank it is
; plain chunky, one byte per pixel left to right, top row first.
;
; Index 255 is the see-through one, covering 44,669 of its 97,034 bytes - the
; whole canopy opening. Index 0 is an ordinary dark colour here, so the sprite
; convention would key out the wrong pixels.

        include "inc/comanche.s"
        include "inc/gemdos.s"

        global  console_init, console_draw, console_select_variant, console_draw_rows
        global  console_status, console_palette, console_rgb
        global  console_palette_remap

; The header's words at +8 and +10 are 327 and 289, and res_open_e forms the
; size as (w+1) x (h+1) - so 328 x 290 = 95,120, which is where the 328 pitch
; comes from as well.
CONSOLE_BYTES   = 100000
CONSOLE_PITCH   = 328
CONSOLE_CLEAR   = 255

CONSOLE_NO_FILE = 1
CONSOLE_BAD     = 2

        text

; DOS: startup console resource chain 00005604-000066C5 and console blit 00025880.
; DOS symbol: inside loc_000055FD
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: loads the authored CONSOL1S image and derives its RGB565 composition.
; Preserved: resource bytes, dimensions, palette data, and failure behavior.
; Kind: translated.
; Status: ported; full cockpit/gauge capture remains pending.
console_init
        clr.w   console_status
        clr.w   console_cache_ready

        move.w  #0,-(sp)
        pea     console_name
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .no_file
        move.w  d0,d7

        ; Staged through the terrain loader's buffer, like every other resource
        ; the port reads after the maps are decoded.
        pea     resource_buffer
        move.l  #RESOURCE_BUFFER_BYTES,-(sp)
        move.w  d7,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d6

        move.w  d7,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp

        tst.l   d6
        bmi     .no_file
        cmpi.l  #17,d6
        bcs     .bad

        lea     resource_buffer,a0
        cmpi.l  #$4B796C65,(a0)                 ; "Kyle"
        bne     .bad
        cmpi.l  #$20445441,4(a0)                ; " DTA"
        bne     .bad

        ; The same PCX-style byte RLE the terrain maps use: a byte with the top
        ; two bits set is a count and the next byte is the value. The stream
        ; begins at 128 - res_open_e reads that much header before the decoder
        ; it falls into starts reading.
        ; The pixel count is the header's, exactly as res_open_e forms it:
        ; (word at +8 plus one) times (word at +10 plus one). Bounding the
        ; decode by the buffer instead swallows the palette that follows the
        ; pixels, and then there is no 0x0C marker left to find.
        moveq   #0,d4
        move.b  9(a0),d4
        lsl.w   #8,d4
        move.b  8(a0),d4
        addq.l  #1,d4                           ; width
        moveq   #0,d3
        move.b  11(a0),d3
        lsl.w   #8,d3
        move.b  10(a0),d3
        addq.l  #1,d3                           ; height
        mulu    d3,d4                           ; pixels
        cmpi.l  #CONSOLE_BYTES,d4
        bhi     .bad
        cmpi.l  #CONSOLE_PITCH*SCREEN_HEIGHT,d4
        bcs     .bad

        lea     128(a0),a0
        move.l  d6,d5
        subi.l  #128,d5                         ; input remaining
        lea     console_image,a1
.token
        tst.l   d5
        beq     .decoded
        tst.l   d4
        beq     .decoded
        moveq   #0,d0
        move.b  (a0)+,d0
        subq.l  #1,d5
        move.w  d0,d1
        andi.w  #$c0,d1
        cmpi.w  #$c0,d1
        bne     .literal
        andi.w  #$3f,d0
        beq     .token
        tst.l   d5
        beq     .decoded
        move.b  (a0)+,d2
        subq.l  #1,d5
        cmp.l   d4,d0
        bhi     .decoded
        sub.l   d0,d4
        subq.w  #1,d0
.run
        move.b  d2,(a1)+
        dbra    d0,.run
        bra     .token
.literal
        move.b  d0,(a1)+
        subq.l  #1,d4
        bra     .token
.decoded

        ; Its source palette follows the pixels behind an 0x0C marker. The DOS
        ; loader reduces these DTA bytes to six-bit DAC values and translates
        ; the console payload into the currently installed flight palette;
        ; retain that source table here and bind its RGB565 lookup after the
        ; mission palette is installed.
        move.w  #CONSOLE_BAD,console_status
        tst.l   d5
        beq     .no_palette
        cmpi.b  #$0c,(a0)
        bne     .no_palette
        addq.l  #1,a0
        lea     console_source_palette,a2
        move.w  #255,d1
.entry
        moveq   #0,d0
        move.b  (a0)+,d0                        ; red, 8-bit
        lsr.w   #2,d0                           ; DOS DTA -> six-bit DAC
        move.b  d0,(a2)+
        moveq   #0,d2
        move.b  (a0)+,d2                        ; green
        lsr.w   #2,d2
        move.b  d2,(a2)+
        moveq   #0,d3
        move.b  (a0)+,d3                        ; blue
        lsr.w   #2,d3
        move.b  d3,(a2)+
        dbra    d1,.entry
        bsr     console_palette_remap
        bsr     console_build_row_spans
        move.w  #1,console_cache_ready
        bsr     console_build_cache
        clr.w   console_status
.no_palette
        rts

.no_file
        move.w  #CONSOLE_NO_FILE,console_status
        rts
.bad
        move.w  #CONSOLE_BAD,console_status
        rts

; Rebind the retained console source palette after resources_select_family has
; installed the mission's P/NP DAC equivalent. The original's single VGA DAC
; makes this load-time translation mandatory; RGB565 only removes the shared
; hardware register, not the source-index relationship.
; DOS: flat 0002B8C5-0002B9BA, console bank translation.
; DOS symbol: sub_0002B8C5
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: calls the common six-bit nearest-colour implementation and keeps the
; console pixels in their authored index space.
; Preserved: source entries, index order and active mission palette.
; Kind: adapted - true-colour surface.
; Status: ported; invoked at every mission resource boundary.
console_palette_remap
        lea     console_source_palette,a0
        lea     console_palette,a1
        bsr     resource_palette_remap
        tst.w   console_cache_ready
        beq.s   .out
        bsr     console_build_cache
.out
        rts

; The composed console, once per palette: every opaque pixel of the rows the
; screen shows, already through the palette into RGB565, and for each row the
; runs of opaque pixels as (first x, count) word pairs ended by a zero count.
; console_draw_rows then copies runs instead of testing and converting 76,800
; source pixels a frame. The pixels it writes are exactly the ones the per-pixel
; loop wrote - every index but CONSOLE_CLEAR, through console_palette - so the
; composed frame is identical to the pixel; a hole in the middle of a row ends
; one run and begins the next.
; DOS: N/A - target artefact; a derived index over the authored CONSOL1S.DTA
;   and the installed palette, consumed only by console_draw_rows.
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: expands the image and its transparent runs at load and remap time.
; Preserved: nothing claimed; the composed pixels are unchanged by it.
; Kind: replaced - load-time index over an authored asset.
; Status: ported; checked frame-identical against the per-pixel loop.
console_build_cache
        movem.l d0-d5/a0-a4,-(sp)
        lea     console_image,a0
        adda.w  #PAGE_VIEW_X,a0                 ; the display shows from column 4
        lea     console_palette,a1
        lea     console_rgb,a2
        lea     console_run_pool,a3
        lea     console_run_ptr,a4
        moveq   #0,d5                           ; row
.row
        move.l  a3,(a4)+                        ; this row's run list
        moveq   #0,d0                           ; x
.scan
        cmpi.w  #SCREEN_WIDTH,d0
        bge.s   .row_done
        moveq   #0,d1
        move.b  0(a0,d0.w),d1
        cmpi.w  #CONSOLE_CLEAR,d1
        bne.s   .run_start
        addq.w  #1,d0
        bra.s   .scan
.run_start
        move.w  d0,(a3)+                        ; first x
        move.w  d0,d2                           ; the run's start
.run
        moveq   #0,d1
        move.b  0(a0,d0.w),d1
        cmpi.w  #CONSOLE_CLEAR,d1
        beq.s   .run_end
        add.w   d1,d1
        move.w  0(a1,d1.w),d3
        move.w  d0,d4
        add.w   d4,d4
        move.w  d3,0(a2,d4.w)
        addq.w  #1,d0
        cmpi.w  #SCREEN_WIDTH,d0
        blt.s   .run
.run_end
        sub.w   d2,d0
        move.w  d0,(a3)+                        ; count
        add.w   d2,d0                           ; back to the absolute x
        bra.s   .scan
.row_done
        clr.w   (a3)+                           ; the end marker's start...
        clr.w   (a3)+                           ; ...and its zero count
        adda.w  #CONSOLE_PITCH,a0
        adda.w  #SCREEN_STRIDE,a2
        addq.w  #1,d5
        cmpi.w  #CONSOLE_ROWS,d5
        blt     .row
        movem.l (sp)+,d0-d5/a0-a4
        rts

; Per row, the first opaque pixel and how many pixels span it to the last one.
; console_draw walks only that, which skips the rows of the canopy that are
; clear all the way across and trims the ragged ones at the edges. A row with
; nothing opaque stores a count of 0.
;
; This is transparency handling, not a visibility bound: the pixels it stops
; visiting hold CONSOLE_CLEAR, which the copy loop discarded anyway, so the
; composed frame is identical to the pixel.
;
; A per-column "floor" table used to be built here as well - the lowest row
; each column could ever show - together with a solid-row boundary and a
; ground-fill row count derived from it. Nothing in the original computes any
; of them: 00006FEF transfers the whole surface and the console image is
; composited over it. The floor's own consumer had already been removed from
; the marcher's occlusion seed (see src/render.s, and rule one's note on
; CONSOLE_BOUND); what was left wrote three values that no CPU-path reader
; used. They are gone rather than kept warm for a path that might read them.
; DOS: N/A - target artefact; a source-side index over the authored
; CONSOL1S.DTA transparency, consumed only by this file's copy loop.
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: records each console row's opaque span once at load time.
; Preserved: nothing claimed; the composed pixels are unchanged by it.
; Kind: replaced - load-time index over an authored asset.
; Status: ported; covered by console_draw.
console_build_row_spans
        movem.l d0-d3/a0-a2,-(sp)
        lea     console_rows,a2
        moveq   #0,d0                           ; row
.brow
        lea     console_image,a0
        move.w  d0,d3
        mulu    #CONSOLE_PITCH,d3
        adda.l  d3,a0

        moveq   #0,d1                           ; first opaque x
.bfirst
        cmpi.b  #CONSOLE_CLEAR,0(a0,d1.w)
        bne     .bhave_first
        addq.w  #1,d1
        cmpi.w  #SCREEN_WIDTH,d1
        blt     .bfirst
        moveq   #0,d1                           ; none opaque at all
        moveq   #0,d2
        bra     .bstore
.bhave_first
        move.w  #SCREEN_WIDTH-1,d2              ; last opaque x
.blast
        cmpi.b  #CONSOLE_CLEAR,0(a0,d2.w)
        bne     .bhave_last
        subq.w  #1,d2
        bra     .blast
.bhave_last
        sub.w   d1,d2
        addq.w  #1,d2                           ; count
.bstore
        move.w  d1,(a2)+
        move.w  d2,(a2)+
        addq.w  #1,d0
        cmpi.w  #SCREEN_HEIGHT,d0
        blt     .brow

        movem.l (sp)+,d0-d3/a0-a2
        rts


; Composite the console over the surface in a0.
;
; The image is 295 rows against the display's 240, and the rows to take are the
; ones from the TOP. Its first 137 rows are the clear index - the canopy opening
; the view shows through - and the panel begins below them. Aligning the image's
; bottom to the screen's instead leaves only a slit to fly by, which is not what
; the original shows: DOS displays 200 rows of this image, so the opening is
; most of the screen and the console a band across the foot of it.
; DOS: console composition around 00006FEF/00025880.
; DOS symbol: sub_00006FEF
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: draws the authored console into the Falcon RGB565 back buffer.
; Preserved: source placement, clipping, and draw-after-terrain ordering.
; Kind: translated.
; Status: ported; full cockpit capture remains pending.
console_draw
        ; The rows below the terrain's 168 are on the persistent page since the
        ; console was blitted there (render_history_console, 0001687D), and the
        ; copy that makes the frame brings them along. Only the part of the
        ; console that overlaps the terrain - the canopy's edges, which the
        ; shear must not move - is drawn over it each frame.
        move.w  #TERRAIN_VIEW_ROWS,d3
        bra     console_draw_rows

; DOS: flat 00006FEF/00025880, helper within the console blit/composition path.
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: copies authored console rows into RGB565 with Falcon pitch handling.
; Preserved: row order, source clipping, and palette conversion.
; Kind: adapted - platform composition port.
; Status: ported; covered by console_draw.
console_draw_rows
        tst.w   console_status
        bne     .done
        tst.w   d3
        beq     .done
        movem.l d0-d7/a0-a6,-(sp)
        lea     console_rgb,a1
        lea     console_run_ptr,a4
        subq.w  #1,d3
.row
        move.l  (a4)+,a5                        ; this row's runs
.run
        move.w  (a5)+,d0                        ; first x
        move.w  (a5)+,d1                        ; count
        beq     .row_done
        add.w   d0,d0
        lea     0(a1,d0.w),a2                   ; source
        lea     0(a0,d0.w),a3                   ; destination
        ; The surface rows are long-aligned; an odd first pixel puts both
        ; pointers on a word, so take one pixel to bring them to a long.
        btst    #1,d0
        beq.s   .aligned
        move.w  (a2)+,(a3)+
        subq.w  #1,d1
        beq     .run
.aligned
        ; d1 = pixels left. Twelve at a time, then longs, then the odd word.
.chunk
        cmpi.w  #12,d1
        blt.s   .chunk_done
        movem.l (a2)+,d2/d4-d7/a6               ; not d3: the row count
        movem.l d2/d4-d7/a6,(a3)
        lea     24(a3),a3
        subi.w  #12,d1
        bra.s   .chunk
.chunk_done
.long
        cmpi.w  #2,d1
        blt.s   .long_done
        move.l  (a2)+,(a3)+
        subq.w  #2,d1
        bra.s   .long
.long_done
        tst.w   d1
        beq     .run
        move.w  (a2),(a3)
        bra     .run
.row_done
        adda.w  #SCREEN_STRIDE,a1
        adda.w  #SCREEN_STRIDE,a0
        dbra    d3,.row
        movem.l (sp)+,d0-d7/a0-a6
.done
        rts

; 0001969D and its five siblings load consol<n>s.dta by patching the digit of
; an inline name, exactly as 00019A34 patches the DEMO digit. In: d0.b = 1..5.
; DOS: flat 0001969D/00019770/000197A0/000197D0/00019800/00019830/000198BC,
;   the view cases' console image loads through 00016381.
; DOS symbol: inside loc_0001959F
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: reloads the named console image and rebinds it to the live palette.
; Preserved: the filename template, its digit, and the reload on every select.
; Difference: 00016381 is the DOS resource opener; this reuses console_init's
;   GEMDOS path, which is the same file through the platform's own boundary.
; Kind: translated.
; Status: ported; only variants 1 and 5 are reachable from the shipped demos.
console_select_variant
        movem.l d0-d1/a0,-(sp)
        addi.b  #'0',d0
        lea     console_name,a0
        move.b  d0,6(a0)                        ; CONSOL<n>S.DTA
        bsr     console_init
        bsr     console_palette_remap
        movem.l (sp)+,d0-d1/a0
        rts

        data
        even
console_name
        dc.b    "CONSOL1S.DTA",0
        even

        bss
        even
console_status
        ds.w    1
; 1 once console_init has decoded the image, so a palette remap may rebuild
; the composed cache from it.
console_cache_ready
        ds.w    1
        even
console_bytes
        ds.l    1
console_palette
        ds.w    256
        even
console_source_palette
        ds.b    768
        even
console_rows
        ds.w    SCREEN_HEIGHT*2                 ; first opaque x, then count
        even
console_image
        ds.b    CONSOLE_BYTES
        even
; The composed rows: every row of the image as 320 RGB565 pixels, and the run lists.
console_rgb
        ds.b    SCREEN_STRIDE*CONSOLE_ROWS
console_run_ptr
        ds.l    CONSOLE_ROWS
console_run_pool
        ds.b    CONSOLE_ROWS*(SCREEN_WIDTH/2*4+4)
        even

        end
