; Route: analysis/functions/falcon-attract.md#resources.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; DOS origin: sprite_blit 00025880, sprite_blit_masked 0002599E,
;   res_open_d 00015E6E, krl1_inflate 0001644B.
; Purpose: load an SG sprite bank from an installed .RLE resource and draw
;   from it into the Falcon surface.
; Inputs/outputs: sprite_bank_load takes a filename and a bank buffer;
;   sprite_draw takes a bank, a sprite index and a position.
; Original globals/side effects: the DOS blitters read the parameter block
;   [00022364] index, [00022366] Y and [0002587C] X, plus the resource base
;   [00019E90]. Those are globals only because each call site is a `mov` to a
;   fixed address; nothing depends on their being global, so they are register
;   arguments here.
; Falcon replacement notes: see the two format notes below.
; Validation: the bank is checked structurally at load - see
;   sprite_bank_validate - and the draw path by a Hatari frame capture.
;
; Every multi-byte field in a bank is little-endian, because this is x86 data
; read verbatim. Widths, heights and the signed offsets are single bytes and
; need nothing; the count word and every dword offset are assembled a byte at
; a time below. Reading them as 68k words is not a subtle error - TANK's length
; 0x0001084E comes back as 0x4E080100 and fails the size check outright.
;
; There is one palette in play at a time, and a bank's indices only mean
; anything against it. That is the original's arrangement: the VGA DAC holds a
; single 256-entry palette, and a bank carries a palette of its own only so
; that 0002B8C5 can build a nearest-colour table from it and REWRITE THE
; BANK'S PIXELS into the installed one at load. The translation is the thing
; that makes one DAC work, not an assumption that every bank was authored
; against the same colours - COMA agrees with TPIC on four entries of 256.
;
; So a bank is translated into the palette it will be composited over -
; src/attract.s does that for the attract overlays, and sky_palette_build does
; the same for the flight backdrop. What does not work is reading a bank's
; indices through its private palette after the DOS DAC has installed the
; mission palette; that is what put the sand/white sky and dark gaps into the
; night replay.
;
; The .RLE container is compressed, so the file bytes are not the runtime
; layout. ASSET-INVENTORY.md carries the format; the parts that matter here:
;
;   file:  "KRL1" or "KRL0", dword decompressed size, then the payload
;   bank:  'SG', count word at +2, palette offset dword at +4, then a 1-based
;          directory of 8-byte records - width, height, signed X and Y
;          offsets, and a dword offset to the pixel data
;
; The pixel layout in the file is COLUMN major: pixel (x,y) sits at
; data[x*height + y], so a column is contiguous and columns run left to right.
; The stored row order is bottom first. DOS starts each column at its bottom
; edge and walks the VGA surface upward; the Falcon surface is top-down, so
; column-major SG banks are normalized once at load time by reversing each
; column. HUDS sprite 0x15 is the visible proof: without that reversal SPEED
; is upside down in the Falcon capture.
;
; It is worth being explicit about why the blitter does not say so. 00025880
; consumes each scanline as four chunks of width/4 bytes, one per VGA plane,
; and walks the destination upward with `sub edi,0x52`. Applied to the file
; bytes that yields diagonal hatching. Both descriptions are correct about
; different buffers: the game builds a planar copy at load, and the blitter
; reads that copy. Only the file layout matters here, because a chunky 16-bit
; surface wants neither the plane interleave nor the upward walk. The
; column-major banks do not need the planar interleave, but they do need the
; same vertical orientation normalized for a top-down chunky surface. Planar
; banks are deplaned into that same form.
;
; The DOS X offset is applied as `neg` then `shr 2`, which quantises a sprite's
; horizontal position to four pixels. The Falcon surface expands each VGA
; plane byte back to its four physical pixels, so preserve that quantisation
; at the true-colour boundary rather than treating the source coordinate as a
; free pixel position.

        include "inc/comanche.s"
        include "dsp/proto.inc"

        xref    object_target_view
        xref    krl_decode
        xref    backdrop_dy
        xref    mission_kind, resource_palette_variant_at

; sprite_blit's mode flags. The two are independent in the original: it has an
; opaque quantised blitter (00025880), a masked quantised one (0002599E) and a
; masked pixel-placed one (00025B27).
BLIT_MASKED      = 1
BLIT_QUANTISE_BIT = 1
BLIT_QUANTISE_X  = 1<<BLIT_QUANTISE_BIT

        global  sprite_init, sprite_bank_load, sprite_mission_load
        global  sprite_palette_variant, sprite_y_extra
        global  sprite_draw, sprite_draw_opaque, sprite_draw_scaled
        global  sprite_overlay
        global  sprite_bank, sprite_bank_status, sprite_model
        global  cockpit_bank, cockpit_status, sprite_bank_load_planar
        global  sprite_palette, sprite_occl, sprite_palette_from_bank, cockpit_palette
        global  sprite_bind_flight_palettes, instrument_palette
        global  instrument_bank, instrument_status, instrument_page
        global  sprite_draw_page, sprite_draw_page_opaque
        global  sprite_draw_page_masked_quantised
        global  hud_bank, hud_status, hud_palette
        global  mission_sprite_banks, mission_sprite_palettes
        global  mission_sprite_status
        global  flight_palette

; COMA is the largest installed bank at 166,666 bytes decoded.
BANK_BYTES      = 168000
MISSION_RESOURCE_NAME_BYTES = 16

; The largest frame that gets rewritten: COMA's are 188x98 = 18,424 bytes.
DEPLANE_SCRATCH = 24000

SPRITE_NO_FILE  = 1
SPRITE_BAD_BANK = 2

        text

; Load the default bank. Deliberately not folded into resources_init: a missing
; sprite file must not stop the terrain from loading, because the port has to
; boot outside C:\COMANCHE and already does that for the maps.
; DOS: 00005920/000067C6 resource-bank setup and instrument bank selection.
; DOS symbol: inside loc_0000591C
; Record: analysis/functions/falcon-attract.md#resources
; Port: loads authored TANK/COMA/CONS banks and validates their model records.
; Preserved: bank order, SG/KRL layout, palette ownership, and missing-file errors.
; Kind: translated.
; Status: ported; mission-specific banks are loaded at each mission boundary.
sprite_init
        clr.l   sprite_occl                     ; no terrain clip until armed
        clr.w   sprite_bank_status
        lea     sprite_name_tank,a0
        lea     sprite_bank,a1
        bsr     sprite_bank_load
        move.w  d0,sprite_bank_status
        tst.l   d0
        bne     .no_model
        bsr     sprite_model_find
.no_model

        ; COMA.RLE, the Comanche in nine views, loaded at 00005920.
        ;
        ; The note here used to say 00005920 is the single writer of the
        ; blitters' resource base [00019E90], and therefore that COMA.RLE is
        ; what they read. It is not the single writer - there are four, at
        ; 0000575B, 00005920, 000067C6 and 00028E51 - so that base holds
        ; whichever bank was installed last. 000067C6 stores the base returned
        ; for the inline name "cons.rle", which is the one the instrument
        ; elements come from.
        clr.w   cockpit_status
        lea     sprite_name_coma,a0
        lea     cockpit_bank,a1
        bsr     sprite_bank_load_planar
        move.w  d0,cockpit_status
        tst.l   d0
        bne     .no_cockpit_palette
        lea     cockpit_bank,a0
        lea     cockpit_palette,a1
        bsr     sprite_palette_from_bank
.no_cockpit_palette

        ; CONS.RLE, the 57 instrument elements. Same KRL1 container and 'SG'
        ; directory as the sprite banks: two-byte magic, word count of 57,
        ; dword offset to the palette, then 57 eight-byte records of width,
        ; height, signed X and Y origin and a data offset. Every one of the 56
        ; gaps between consecutive data offsets is exactly width*height, which
        ; is what confirms the layout rather than its shape.
        clr.w   instrument_status
        lea     sprite_name_cons,a0
        lea     instrument_bank,a1
        bsr     sprite_bank_load_planar
        move.w  d0,instrument_status

        ; HUDS.RLE is the authored flight-overlay bank. Keep it separate from
        ; CONS.RLE: the DOS frame's [00019E94] base points at this bank.
        clr.w   hud_status
        lea     sprite_name_huds,a0
        lea     hud_bank,a1
        bsr     sprite_bank_load
        move.w  d0,hud_status
        tst.l   d0
        bne     .done
        lea     hud_bank,a0
        lea     hud_palette,a1
        bsr     sprite_palette_from_bank
.done
        rts

; Load the ten sprite slots named by the selected mission resource list. The
; DOS startup reset at 0002911C clears the ten inline names/pointers and the
; mission parser fills them from entries 11..20; 000068A6 then indexes those
; pointers with object fields f2 and f3. The Falcon keeps the same slot order,
; but stores decoded banks in a bounded native array and gives each bank its
; own RGB565 palette because the Falcon has no VGA DAC to serialize through.
; In: mission_sprite_names contains the selected list.
; DOS: flat 0002911C, 0002A34C, 000068A6-000068C7.
; DOS symbol: inside loc_00029119
; Record: analysis/functions/falcon-attract.md#resources
; Port: decodes exactly the authored slots before object_spawn_mission runs.
; Preserved: slot numbering, missing-resource status, SG validation, and model
; record contents. Storage is the Falcon-only exception.
; Kind: translated/adapted - native storage and true-colour palette.
; Status: ported; active mission slots are consumed by the object factory.
sprite_mission_load
        movem.l d1-d7/a0-a6,-(sp)
        lea     mission_sprite_names,a0
        lea     mission_sprite_banks,a1
        lea     mission_sprite_palettes,a2
        lea     mission_sprite_status,a3
        moveq   #0,d7
.slot
        move.l  a0,a4
        move.l  a1,a5
        tst.b   (a0)
        bne     .load
        move.w  #SPRITE_NO_FILE,(a3)
        bra     .next
.load
        bsr     sprite_bank_load
        move.w  d0,(a3)
        tst.l   d0
        bne     .next
        move.l  a5,a0
        move.l  a2,a1
        move.w  #1,sprite_palette_variant       ; 0002B903, not 0002B8C5
        ; The palette path ends in resource_palette_remap, which does not keep
        ; a3-a5 or d7. The loop's cursors live there, so they are held here:
        ; one slot's remap used to move the name cursor seven slots on, and the
        ; three empty slots after the last bank then opened the mission text
        ; as file names.
        movem.l d7/a3-a5,-(sp)
        bsr     sprite_palette_from_bank
        movem.l (sp)+,d7/a3-a5
        clr.w   sprite_palette_variant
.next
        adda.w  #MISSION_RESOURCE_NAME_BYTES,a4
        move.l  a4,a0
        adda.l  #BANK_BYTES,a5
        move.l  a5,a1
        adda.l  #512,a2
        addq.l  #2,a3
        addq.w  #1,d7
        cmpi.w  #10,d7
        bcs     .slot
        movem.l (sp)+,d1-d7/a0-a6
        rts

; The SG palette pointer is also the boundary of the optional DOS model
; record. TANK.RLE's '3D' record begins at palette + 770: one marker byte and
; 768 six-bit palette bytes. The object handler indexes this record directly
; at the original's model+2 and model+0x22 offsets; no frame bands are
; inferred from the rendered silhouette.
; DOS: flat 00024E1D and model pointer 00020654, `3D` record lookup.
; DOS symbol: inside loc_00024E03
; Record: analysis/functions/falcon-attract.md#resources
; Port: locates the validated model record inside the loaded SG bank.
; Preserved: pointer arithmetic, marker word, azimuth/elevation table offsets.
; Kind: translated.
; Status: ported; model asset loading is required before object drawing.
sprite_model_find
        lea     sprite_bank,a0
        moveq   #0,d0
        move.b  7(a0),d0
        lsl.l   #8,d0
        move.b  6(a0),d0
        lsl.l   #8,d0
        move.b  5(a0),d0
        lsl.l   #8,d0
        move.b  4(a0),d0
        cmpi.l  #BANK_BYTES-770,d0
        bhi     .missing
        adda.l  d0,a0
        add.l   #770,a0
        cmpi.w  #$3344,(a0)                   ; bytes '3D'
        bne     .missing
        move.l  a0,sprite_model
        rts
.missing
        clr.l   sprite_model
        rts

; As sprite_bank_load, but for a bank whose pixels are stored plane-chunked by
; row rather than column major. Both layouts are real and they are not
; interchangeable - see the note at the head of this file - so the planar ones
; are rewritten into the column-major form at load and one draw path serves
; everything after that.
;
; In:  a0 = filename, a1 = bank buffer of BANK_BYTES
; DOS: 00025880 planar blitter input path; no separate game-side entry.
; DOS symbol: sub_00025880
; Record: analysis/functions/falcon-attract.md#resources
; Port: marks an authored bank for load-time deplaning into Falcon chunky data.
; Preserved: source row/plane layout and post-load pixel meaning.
; Kind: replaced - platform format replacement.
; Status: ported; capture validation remains pending.
sprite_bank_load_planar
        movem.l d1/a0-a1,-(sp)
        move.w  #1,bank_is_planar
        bsr     sprite_bank_load
        clr.w   bank_is_planar
        movem.l (sp)+,d1/a0-a1
        rts

; Convert an SG bank's authored six-bit palette to the Falcon RGB565 table
; used by sprite_blit. HUDS is green in its own palette; retaining that
; authored palette is the true-colour replacement for the DOS DAC state while
; leaving the terrain palette available to TANK/COMA/CONS callers.
; In: a0 = decoded SG bank, a1 = 256-word RGB565 destination.
; DOS: 0002B8C5/0002B949 palette installation before HUD drawing.
; DOS symbol: sub_0002B8C5
; Record: analysis/functions/falcon-attract.md#resources
; Port: expands the bank palette directly before mission selection, then
; remaps it through the active flight palette after mission selection.
; Preserved: source palette order and six-bit component meaning.
; Kind: adapted - palette surface replacement.
; Status: ported; mission-boundary remap follows the DOS bank loader.
sprite_palette_from_bank
        movem.l d0-d4/a0-a2,-(sp)
        moveq   #0,d0
        move.b  7(a0),d0
        lsl.l   #8,d0
        move.b  6(a0),d0
        lsl.l   #8,d0
        move.b  5(a0),d0
        lsl.l   #8,d0
        move.b  4(a0),d0
        adda.l  d0,a0
        cmpi.b  #$0c,(a0)+
        bne     .bad
        ; 0002B903 copies the bank's palette to the work buffer at 00015F84 and
        ; runs the mission's palette variant [0002A980] over it before the
        ; nearest-colour remap; a night mission's models are recoloured the way
        ; its terrain is. 0002B8C5, which the cockpit, instrument and HUD banks
        ; and the weapon banks go through, makes no such call.
        tst.w   sprite_palette_variant
        beq     .no_variant
        cmpi.l  #1,mission_kind
        bne     .no_variant
        lea     sprite_variant_palette,a2
        move.w  #191,d0                     ; 768 bytes
.copy_variant
        move.l  (a0)+,(a2)+
        dbra    d0,.copy_variant
        lea     sprite_variant_palette+3,a0
        bsr     resource_palette_variant_at
        lea     sprite_variant_palette,a0
.no_variant
        ; sprite_init runs before a mission palette exists. Later bank loads
        ; take the same nearest-colour path as the explicit rebind below.
        tst.w   resource_active_palette+3
        bne     .active
        move.w  #255,d4
.entry
        moveq   #0,d0
        move.b  (a0)+,d0                    ; red, six bits -> RGB565
        lsr.w   #1,d0
        lsl.w   #8,d0
        lsl.w   #3,d0
        moveq   #0,d1
        move.b  (a0)+,d1                    ; green
        lsl.w   #5,d1
        or.w     d1,d0
        moveq   #0,d1
        move.b  (a0)+,d1                    ; blue
        lsr.w   #1,d1
        or.w     d1,d0
        move.w   d0,(a1)+
        dbra    d4,.entry
        bra     .bad
.active
        bsr     resource_palette_remap
.bad
        movem.l (sp)+,d0-d4/a0-a2
        rts

; Rebind the default cockpit, instrument and HUD banks after a mission's
; P/NP palette has been loaded. DOS translates these banks before their first
; flight blit; the Falcon keeps the source bytes and translates the lookup.
; DOS: 00005920/000067C6 and 0002B8C5-0002B9BA.
; DOS symbol: inside loc_0000591C
; Record: analysis/functions/falcon-attract.md#resources
; Port: repeats only the palette lookup for retained banks.
; Preserved: bank palette pointers, target indices and draw-time ownership.
; Kind: adapted - true-colour surface.
; Status: ported; called by every mission resource selection.
sprite_bind_flight_palettes
        movem.l d0-d7/a0-a2,-(sp)
        lea     cockpit_bank,a0
        lea     cockpit_palette,a1
        bsr     sprite_palette_rebind_bank
        lea     instrument_bank,a0
        lea     instrument_palette,a1
        bsr     sprite_palette_rebind_bank
        lea     hud_bank,a0
        lea     hud_palette,a1
        bsr     sprite_palette_rebind_bank
        movem.l (sp)+,d0-d7/a0-a2
        rts

; The palette record at the end of an SG bank. 0002B8DB reads the dword at
; +4, adds the bank base, requires the byte there to be 0x0C, steps past it
; and copies 0xC0 dwords - 768 bytes, 256 six-bit RGB triples.
; In: a0 = bank base, a1 = destination RGB565 palette.
; DOS: flat 0002B8DB-0002B8FF, SG bank palette record.
; DOS symbol: inside sub_0002B8C5
; Record: analysis/functions/falcon-attract.md#resources
; Port: resolves the same record and expands it through resource_palette_remap.
; Preserved: the +4 offset, the 0x0C tag, and the 768-byte payload.
; Difference: DOS copies the six-bit triples to a scratch buffer and builds a
;   nearest-colour translation table from them; the Falcon expands them to
;   RGB565 directly, which is the rule-three surface boundary.
; Kind: translated/adapted - RGB565 bank palette.
; Status: ported; covered by sprite_bank_load.
sprite_palette_rebind_bank
        movem.l d0/a0-a1,-(sp)
        moveq   #0,d0
        move.b  7(a0),d0
        lsl.l   #8,d0
        move.b  6(a0),d0
        lsl.l   #8,d0
        move.b  5(a0),d0
        lsl.l   #8,d0
        move.b  4(a0),d0
        adda.l  d0,a0
        cmpi.b  #$0c,(a0)+
        bne     .done
        bsr     resource_palette_remap
.done
        movem.l (sp)+,d0/a0-a1
        rts

; As sprite_bank_load, but the payload is taken as-is: no SG validation, no
; deplane. SKY*.RLE lives in the same KRL container yet is not a sprite bank
; - a 320x240 byte image starts at +16, past a prefix that merely resembles
; an SG header.
;
; In:  a0 = filename, a1 = buffer of BANK_BYTES
; DOS: backdrop resource path around 00016EC0; raw KRL payload boundary.
; DOS symbol: inside sub_00016E41
; Record: analysis/functions/falcon-attract.md#resources
; Port: loads an authored non-SG image payload without inventing a sprite header.
; Preserved: KRL decompression, payload offset, dimensions, and error handling.
; Kind: translated.
; Status: ported; sky-family capture remains pending.
sprite_bank_load_raw
        movem.l d1/a0-a1,-(sp)
        move.w  #1,bank_is_raw
        bsr     sprite_bank_load
        clr.w   bank_is_raw
        movem.l (sp)+,d1/a0-a1
        rts

; The mission backdrop. Loaded like any bank; consumed by render_clear as an
; indexed image. An absent or malformed file leaves sky_status nonzero, and
; main refuses to enter a frame rather than drawing an invented substitute.
;
; The payload is NOT a 320x240 raster. It is 512 COLUMN STRIPS of
; SKY_IMAGE_ROWS (150) bytes - column major, like TANK and HUDS - which is
; the shape the original's per-column backdrop walker consumes, and the
; extra width is sampling margin for its roll shear. The Falcon renderer walks
; all 192 DOS source columns, expands each selected source column to two RGB565
; pixels, and crops the recovered source window 16..175 only at composition.
; The
; directory record even names the strip length - its width byte is 150. The
; transpose below rewrites ALL 512 strips
; into a row-major image once, at load, the same way
; sprite_bank_load_planar rewrites the planar banks.
;
; It used to keep only the leftmost 320, on the grounds that which 320 the
; original anchors was not recovered. It is recovered now, and the answer is
; that it does not anchor any of them: the sourced fill at 00016EC0 derives
; its first strip from the view angle's top nine bits and walks on from
; there, wrapping at the bank's end. 512 strips is one revolution. Keeping
; 320 of them is what made the sky a painted backdrop that stayed put while
; the helicopter turned.
        global  sky_init, sky_select_family, sky_status, sky_bank, sky_palette, sky_image, sky_rgb
; DOS: flat 00016EC0-00017579, backdrop resource initialization boundary.
; DOS symbol: inside sub_00016E41
; Record: analysis/functions/falcon-attract.md#resources
; Port: selects the active mission's authored sky family and transposes its
; source strips.
; Preserved: 512-strip image, source order, and palette data.
; Kind: translated.
; Status: ported; mission-driven family selection is wired at startup.
sky_init
        move.w  mission_sky_number,d0            ; parsed mission resource list

; In: d0.w = sky number 1..4. The mission/demo resource list selects this
; alongside its D/C terrain family; the sky is not a fixed global backdrop.
; DOS: flat 00016EC0-00017579, sourced backdrop family selection.
; DOS symbol: inside sub_00016E41
; Record: analysis/functions/falcon-attract.md#resources
; Port: loads SKY1.RLE-SKY4.RLE selected by the mission/demo resource record.
; Preserved: source strip origin is supplied later by the view angle.
; Kind: translated.
; Status: ported; same-camera backdrop verification remains pending.
sky_select_family
        movem.l d0-d2/a0-a2,-(sp)
        move.w  #1,sky_status
        cmpi.w  #1,d0
        bcs     .none
        cmpi.w  #4,d0
        bhi     .none
        subi.w  #1,d0
        lsl.w   #2,d0
        lea     sky_names,a0
        move.l  0(a0,d0.w),a0
        lea     sky_bank,a1
        bsr     sprite_bank_load_raw
        tst.l   d0
        bne     .none
        lea     sky_bank+16,a0                  ; column strips
        lea     sky_image,a1
        move.w  #SKY_STRIPS-1,d1
.col
        move.l  a1,a2
        move.w  #SKY_IMAGE_ROWS-1,d2
.px
        move.b  (a0)+,(a2)
        lea     SKY_STRIPS(a2),a2
        dbra    d2,.px
        addq.l  #1,a1
        dbra    d1,.col
        bsr     sky_palette_build
        tst.l   d0
        bne     .none
        bsr     sky_rgb_build
        clr.w   sky_status
.none
        movem.l (sp)+,d0-d2/a0-a2
        rts

; The backdrop as render_clear draws it: every strip pixel already through
; sky_palette and doubled into the RGB565 longword of its two Falcon pixels,
; one strip after another (column-major), so the fill reads a column with
; (a1)+. Built once here, where the image and its palette are both final;
; nothing changes either until the next family is selected.
; DOS: N/A - platform replacement; a lookup the backdrop fill (00017230)
;   performs per pixel, done once per load.
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Kind: replaced.
; Status: ported; render_clear's output is unchanged.
sky_rgb_build
        movem.l d0-d3/a0-a3,-(sp)
        lea     sky_image,a0
        lea     sky_palette,a2
        lea     sky_rgb,a1
        move.w  #SKY_STRIPS-1,d1
.strip
        move.l  a0,a3
        move.w  #SKY_IMAGE_ROWS-1,d2
.row
        moveq   #0,d0
        move.b  (a3),d0
        move.w  0(a2,d0.w*2),d3
        swap    d3
        move.w  0(a2,d0.w*2),d3
        move.l  d3,(a1)+
        lea     SKY_STRIPS(a3),a3
        dbra    d2,.row
        addq.l  #1,a0
        dbra    d1,.strip
        movem.l (sp)+,d0-d3/a0-a3
        rts

; SKY*.RLE carries its own source palette, but it is not the framebuffer's
; palette. DOS resolves it through the one active DAC before the backdrop
; walker consumes its pixels.
;
; The container is an ordinary bank: 'SG', a count word, and at +4 the dword
; offset of a 0x0C palette block - 76,816 for SKY2, exactly where the
; 512x150 column-major image at +16 ends. Its components are six-bit, like
; every other bank's,
; while C1.DTA's terrain palette is eight-bit, and the two agree on one entry
; of 256. Drawing the sky's indices through the terrain's table is what put
; horizontal noise across the whole backdrop.
;
; The original resolves it with one VGA DAC: 0002B8C5 translates the bank into
; the installed palette and rewrites its pixels into that index space at load.
; The Falcon keeps the source bank intact, but sky_palette_build performs the
; same nearest-colour translation while creating the RGB565 lookup, so every
; sky byte reaches the same active mission colour as DOS.
;
; DOS: flat 0002B8C5 weighted nearest-colour remap at bank load.
; DOS symbol: sub_0002B8C5
; Record: analysis/functions/falcon-attract.md#resources
; Port: builds the active-palette RGB565 lookup for the translated sky bank.
; Preserved: six-bit source triples, 0002B820's search/order/metric, and index
; order; only the final framebuffer word is platform-specific.
; Kind: adapted - platform colour port.
; Status: ported; night-flight capture validates the selected SKY4/NP44 pair.
sky_palette_build
        movem.l d0-d7/a0-a6,-(sp)
        lea     sky_bank,a2
        moveq   #0,d0
        move.b  7(a2),d0                        ; palette offset, little-endian
        lsl.l   #8,d0
        move.b  6(a2),d0
        lsl.l   #8,d0
        move.b  5(a2),d0
        lsl.l   #8,d0
        move.b  4(a2),d0
        cmpi.l  #BANK_BYTES-769,d0
        bhi     .bad
        lea     0(a2,d0.l),a0
        cmpi.b  #$0C,(a0)+
        bne     .bad

        lea     sky_palette,a1
        ; The bank stores six-bit triples immediately after the marker. The
        ; common DOS palette boundary consumes them in place and emits the
        ; lookup the RGB565 sky walker uses.
        ;
        ; A night mission's sky goes through the palette variant first, like a
        ; model bank (0002B903) and unlike the 0002B8C5 banks: the original's
        ; sky pixels, read out of its memory after load, are the green-tinted
        ; entries - source (0,0,0) -> DAC (0,10,0), (1,1,1) -> (0,11,1),
        ; (2,2,3) -> (0,12,2), (19,19,23) -> (4,29,22) - where the untinted
        ; nearest-colour search picks the grey and black entries (the star's
        ; centre came out grey).
        cmpi.l  #1,mission_kind
        bne.s   .sky_remap
        move.l  a0,a2
        lea     sprite_variant_palette,a3
        move.w  #191,d0
.sky_copy
        move.l  (a2)+,(a3)+
        dbra    d0,.sky_copy
        movem.l a0-a1,-(sp)
        lea     sprite_variant_palette+3,a0
        bsr     resource_palette_variant_at
        movem.l (sp)+,a0-a1
        lea     sprite_variant_palette,a0
.sky_remap
        bsr     resource_palette_remap
        ; SKY4's night source uses index 1 as its clear field: the DOS replay
        ; leaves that field at the viewport colour (the authored non-1 marks
        ; remain visible against it).  The Falcon keeps the same opaque write
        ; count, but binds that translated index to the active DOS clear entry
        ; instead of exposing the bank's near-black source colour.  This is a
        ; mission-kind presentation rule, not a selectable renderer variant.
        cmpi.l  #1,mission_kind
        bne     .done
        cmpi.w  #4,mission_sky_number
        bne     .done
        move.w  flight_palette+510,sky_palette+2
.done
        moveq   #0,d0
        movem.l (sp)+,d0-d7/a0-a6
        rts
.bad
        moveq   #-1,d0
        movem.l (sp)+,d0-d7/a0-a6
        rts
; DOS: inline startup resource-name table around 00005604-000066C5.
; DOS symbol: inside loc_000055FD
; Record: analysis/functions/falcon-attract.md#resources
; Port: four Falcon pointers to the authored SKY1.RLE-SKY4.RLE names.
; Preserved: family numbering and file names; pointer representation is native.
; Kind: adapted - data-table address replacement.
; Status: ported; selected-family capture remains pending.
sky_names
        dc.l    sky_name_1,sky_name_2,sky_name_3,sky_name_4
sky_name_1
        dc.b    "SKY1.RLE",0
sky_name_2
        dc.b    "SKY2.RLE",0
sky_name_3
        dc.b    "SKY3.RLE",0
sky_name_4
        dc.b    "SKY4.RLE",0
        even

; In:  a0 = filename, a1 = bank buffer of BANK_BYTES
; Out: d0 = 0 on success, SPRITE_NO_FILE or SPRITE_BAD_BANK otherwise
; DOS: flat 00015E6E/0001644B resource open/decompress boundary.
; DOS symbol: sub_00015E6E
; Record: analysis/functions/falcon-attract.md#resources
; Port: reads and validates one authored KRL/SG bank through GEMDOS.
; Preserved: file errors, decompressed size, little-endian directory, and pixels.
; Kind: translated.
; Status: ported; bank capture validation remains pending.
sprite_bank_load
        movem.l d1-d7/a1-a6,-(sp)
        move.l  a1,a6

        move.w  #0,-(sp)
        move.l  a0,-(sp)
        move.w  #61,-(sp)               ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .no_file
        move.w  d0,d7

        ; The compressed file is staged in the terrain loader's buffer. That
        ; buffer has done its job by the time sprites load, and the largest
        ; installed .RLE is 89,158 bytes against its 700,000, so a second large
        ; buffer would be dead weight for the whole run.
        pea     resource_buffer
        move.l  #RESOURCE_BUFFER_BYTES,-(sp)
        move.w  d7,-(sp)
        move.w  #63,-(sp)               ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d6

        move.w  d7,-(sp)
        move.w  #62,-(sp)               ; Fclose
        trap    #1
        addq.l  #4,sp

        tst.l   d6
        bmi     .no_file
        cmpi.l  #8,d6
        bcs     .bad_bank

        lea     resource_buffer,a0
        move.l  (a0),d0
        cmpi.l  #$4B524C31,d0           ; "KRL1"
        beq     .krl1
        cmpi.l  #$4B524C30,d0           ; "KRL0"
        bne     .bad_bank

        ; KRL0 is stored; DOS 00015F28 copies it out verbatim.
        moveq   #0,d1
        move.b  7(a0),d1
        lsl.l   #8,d1
        move.b  6(a0),d1
        lsl.l   #8,d1
        move.b  5(a0),d1
        lsl.l   #8,d1
        move.b  4(a0),d1
        cmpi.l  #BANK_BYTES,d1
        bhi     .bad_bank
        cmp.l   d6,d1
        bhi     .bad_bank
        lea     8(a0),a0
        move.l  a6,a1
        move.l  d1,d0
        bsr     copy_bytes
        bra     .have_bank

.krl1
        ; The declared length can be smaller than the stream - eight installed
        ; banks leave data undecoded and are still complete - so the decode is
        ; bounded by this field and never by the bytes remaining.
        moveq   #0,d1
        move.b  7(a0),d1
        lsl.l   #8,d1
        move.b  6(a0),d1
        lsl.l   #8,d1
        move.b  5(a0),d1
        lsl.l   #8,d1
        move.b  4(a0),d1
        cmpi.l  #BANK_BYTES,d1
        bhi     .bad_bank
        lea     8(a0),a0
        move.l  d6,d2
        subq.l  #8,d2                   ; input bytes available
        move.l  a6,a1
        move.l  d1,d0                   ; output bytes wanted
        jsr     krl_decode
        tst.l   d0
        bne     .bad_bank

.have_bank
        tst.w   bank_is_raw
        bne     .laid_out               ; raw payload: no SG structure to check
        move.l  a6,a0
        bsr     sprite_bank_validate
        tst.l   d0
        bne     .bad_bank
        tst.w   bank_is_planar
        beq     .column_major
        move.l  a6,a0
        bsr     sprite_bank_deplane
        bra     .laid_out
.column_major
        ; TANK.RLE and HUDS.RLE are column-major SG banks. Their first byte
        ; for each column is the DOS bottom pixel; normalize it to the
        ; Falcon's top-down surface just as sprite_bank_deplane does for the
        ; plane-chunked banks.
        move.l  a6,a0
        bsr     sprite_bank_flip_rows
.laid_out
        moveq   #0,d0
        bra     .done

.no_file
        moveq   #SPRITE_NO_FILE,d0
        bra     .done
.bad_bank
        moveq   #SPRITE_BAD_BANK,d0
.done
        movem.l (sp)+,d1-d7/a1-a6
        rts

; a0 = source, a1 = destination, d0 = byte count
; DOS: helper within 0001644B KRL/resource copy path.
; DOS symbol: sub_0001644B
; Record: analysis/functions/falcon-attract.md#resources
; Port: copies bounded decompressed bytes between Falcon staging buffers.
; Preserved: byte count and source/destination order.
; Kind: translated.
; Status: ported; covered by sprite_bank_load.
copy_bytes
        movem.l d0/a0-a1,-(sp)
        tst.l   d0
        beq     .done
.byte
        move.b  (a0)+,(a1)+
        subq.l  #1,d0
        bne     .byte
.done
        movem.l (sp)+,d0/a0-a1
        rts

; Reject anything that is not a well-formed SG bank before its bytes are used
; as geometry. In: a0 = bank. Out: d0 = 0 if valid.
;
; The checks are the two invariants that hold across all 21 installed banks:
; the header's palette pointer lands on the $0C marker, and every record's
; pixel data lies inside the sprite area. The first is the one that actually
; proves a decode correct, because the marker sits at a byte position the
; decoder never consults, and it is cheap enough to repeat at runtime.
; DOS: SG bank reader/consumer contract around 00025880.
; DOS symbol: sub_00025880
; Record: analysis/functions/falcon-attract.md#resources
; Port: checks authored count, offsets, dimensions, and payload bounds.
; Preserved: directory invariants; invalid data stops rather than becoming a bank.
; Kind: translated.
; Status: ported; covered by sprite_bank_load.
sprite_bank_validate
        movem.l d1-d4/a1,-(sp)
        cmpi.w  #$5347,(a0)             ; 'SG'
        bne     .bad
        moveq   #0,d1
        move.b  3(a0),d1
        lsl.w   #8,d1
        move.b  2(a0),d1
                                ; count
        beq     .bad
        cmpi.w  #255,d1
        bhi     .bad
        moveq   #0,d2
        move.b  7(a0),d2
        lsl.l   #8,d2
        move.b  6(a0),d2
        lsl.l   #8,d2
        move.b  5(a0),d2
        lsl.l   #8,d2
        move.b  4(a0),d2
                                ; palette offset
        ; The palette block follows the record table, so its offset cannot lie
        ; inside it: 8 bytes of header and 8 per record, count + 1 of them.
        ; This used to demand an offset of at least 769 - a whole palette's
        ; worth of leading bytes - which has no counterpart in the original's
        ; loader (00015E6E checks nothing here) and refused CHAF.RLE and
        ; BULL.RLE, whose palettes sit at 0x1B4 and 0x148 in banks of 1206
        ; and 1097 bytes. They are valid banks the countermeasure launchers
        ; need.
        moveq   #0,d4
        move.w  d1,d4
        addq.l  #1,d4
        lsl.l   #3,d4
        cmp.l   d4,d2
        bcs     .bad
        cmpi.l  #BANK_BYTES-769,d2
        bhi     .bad
        lea     0(a0,d2.l),a1
        cmpi.b  #$0c,(a1)
        bne     .bad

        ; Every record must describe pixels inside the sprite area. The SKY
        ; backdrops fail this deliberately: they are single 320x240 images and
        ; the byte width field cannot hold 320, so a bank of them is not a
        ; sprite bank and is refused rather than drawn as garbage.
        moveq   #1,d3
.check
        move.l  d3,d4
        lsl.l   #3,d4
        moveq   #0,d0
        move.b  0(a0,d4.l),d0           ; width
        beq     .next
        moveq   #0,d1
        move.b  1(a0,d4.l),d1           ; height
        beq     .next
        mulu    d1,d0
        moveq   #0,d1
        move.b  7(a0,d4.l),d1
        lsl.l   #8,d1
        move.b  6(a0,d4.l),d1
        lsl.l   #8,d1
        move.b  5(a0,d4.l),d1
        lsl.l   #8,d1
        move.b  4(a0,d4.l),d1
        add.l   d1,d0
        cmp.l   d2,d0
        bhi     .bad
.next
        addq.l  #1,d3
        moveq   #0,d1
        move.b  3(a0),d1
        lsl.w   #8,d1
        move.b  2(a0),d1
        cmp.w   d3,d1
        bcc     .check
        moveq   #0,d0
        bra     .checked
.bad
        moveq   #-1,d0
.checked
        movem.l (sp)+,d1-d4/a1
        rts

; Rewrite a planar bank into the column-major form the draw path expects.
;
; A planar row is four chunks holding the pixels where x mod 4 equals the chunk
; index. 000258C6 sets the chunk length to `width >> 2` and the four `rep
; movsb` runs read one after another, so the chunks are EQUAL and a row is
; 4 * (width >> 2) bytes - the low two bits of the width are simply not drawn.
; That is what this now does.
;
; That case does not arise. Every frame's stored payload in all 21 installed
; banks is exactly width * height bytes, measured from the gaps between
; consecutive data offsets, so a width that is not a multiple of four would
; make 00025880 shear by width mod 4 per row. The three banks it draws -
; CONS.RLE, COMA.RLE and ZOVE.RLE - have every width a multiple of four, and
; every bank that does not (TANK, HELL, HOKE, ROCK, STGR, TURR, RADR, LH66,
; HUDS, BOOM, BULL, CHAF, SPIN, FUEL) is drawn by one of the column-major
; routines instead. The split holds across the whole installed set, which is
; what makes it evidence rather than a coincidence.
;
; The ceil form this used to carry was verified against the rendered banks,
; which is why it survived; it is indistinguishable from the original's on
; every bank that reaches here, and the original's is now what runs.
;
; In: a0 = bank
; DOS: flat 00025880, planar bank preparation before sprite blit.
; DOS symbol: sub_00025880
; Record: analysis/functions/falcon-attract.md#resources
; Port: rewrites authored plane-chunked pixels into Falcon column-major pixels.
; Preserved: source pixel coordinates and transparent index semantics.
; Kind: replaced - platform format replacement.
; Status: ported; capture validation remains pending.
sprite_bank_deplane
        movem.l d0-d7/a0-a6,-(sp)
        move.l  a0,a4
        moveq   #0,d7
        move.b  3(a4),d7
        lsl.w   #8,d7
        move.b  2(a4),d7                        ; frame count
        beq     .done
        moveq   #1,d6
.frame
        move.l  d6,d0
        lsl.l   #3,d0
        lea     0(a4,d0.l),a3                   ; the record
        moveq   #0,d4
        move.b  (a3),d4                         ; width
        beq     .next
        moveq   #0,d5
        move.b  1(a3),d5                        ; height
        beq     .next
        move.l  d4,d0
        mulu    d5,d0
        cmpi.l  #DEPLANE_SCRATCH,d0
        bhi     .next                           ; larger than the scratch
        moveq   #0,d0
        move.b  7(a3),d0
        lsl.l   #8,d0
        move.b  6(a3),d0
        lsl.l   #8,d0
        move.b  5(a3),d0
        lsl.l   #8,d0
        move.b  4(a3),d0
        lea     0(a4,d0.l),a0                   ; pixel data

        ; Chunk starts, accumulated. 000258C6 sets the chunk length to
        ; `width >> 2` and the four `rep movsb` runs read one after another,
        ; so the chunks are EQUAL and a row is 4 * (width >> 2) bytes. This
        ; used to split with ceil, which differs whenever the width is not a
        ; multiple of four - a rule the original does not have. Unreachable
        ; with the shipped data either way (every bank this deplaner sees has
        ; all widths divisible by four), so taking the original's form costs
        ; nothing and removes the invented one.
        lea     plane_start,a2
        move.w  d4,d2
        lsr.w   #2,d2                           ; 000258C6 `shr ebp, 2`
        moveq   #0,d0                           ; running start
        moveq   #0,d1                           ; plane
.plane
        move.w  d1,d3
        add.w   d3,d3
        move.w  d0,0(a2,d3.w)
        add.w   d2,d0
        addq.w  #1,d1
        cmpi.w  #4,d1
        blo     .plane

        ; scratch[c*H + r] = data[(H-1-r)*W + start[c and 3] + (c >> 2)]
        ;
        ; The row reversal is not cosmetic. A planar bank is stored bottom row
        ; first, because the blitter that consumes it walks the destination
        ; upward with `sub edi,0x52`. Preserving the file's row order draws the
        ; helicopter upside down - which is exactly what it did.
        lea     deplane_scratch,a1
        moveq   #0,d2                           ; column
.column
        move.w  d2,d3
        andi.w  #3,d3
        add.w   d3,d3
        move.w  0(a2,d3.w),d3                   ; chunk start
        move.w  d2,d0
        lsr.w   #2,d0
        add.w   d0,d3                           ; offset of this column in a row
        move.l  a0,a6
        adda.w  d3,a6                           ; source, its first stored row
        move.w  d5,d0
        subq.w  #1,d0
        mulu    d4,d0
        adda.l  d0,a6                           ; start at the LAST stored row
        move.w  d2,d0
        mulu    d5,d0
        move.l  a1,a5
        adda.l  d0,a5                           ; destination column
        move.w  d5,d1
        subq.w  #1,d1
.row
        move.b  (a6),(a5)+
        suba.w  d4,a6                           ; up one planar row: bottom first
        dbra    d1,.row
        addq.w  #1,d2
        cmp.w   d4,d2
        blo     .column

        ; Back over the original, which is the same size either way.
        move.l  d4,d0
        mulu    d5,d0
        move.l  a1,a5
        move.l  a0,a6
.copy_back
        move.b  (a5)+,(a6)+
        subq.l  #1,d0
        bne     .copy_back
.next
        addq.w  #1,d6
        cmp.w   d7,d6
        bls     .frame
.done
        movem.l (sp)+,d0-d7/a0-a6
        rts


; Reverse each column of a column-major SG bank in place. The authored TANK
; and HUDS banks are already chunky and column-contiguous, but their rows are
; stored bottom first for the DOS blitter's upward walk. This makes them
; column-contiguous and top-down for the Falcon blitter.
; In: a0 = validated SG bank.
; DOS: 00025880/0002599E source order and upward destination walk.
; DOS symbol: sub_00025880
; Record: analysis/functions/falcon-attract.md#resources
; Port: load-time orientation normalization for the RGB565 surface.
; Preserved: directory, offsets, transparency indices, and column order.
; Kind: adapted - platform surface port.
; Status: ported; HUDS/SPEED orientation capture is verified.
sprite_bank_flip_rows
        movem.l d0-d7/a0-a6,-(sp)
        move.l  a0,a4
        moveq   #0,d7
        move.b  3(a4),d7
        lsl.w   #8,d7
        move.b  2(a4),d7                 ; frame count
        moveq   #1,d6
.frame
        move.l  d6,d0
        lsl.l   #3,d0
        lea     0(a4,d0.l),a3
        moveq   #0,d4
        move.b  (a3),d4                  ; width
        beq     .next
        moveq   #0,d5
        move.b  1(a3),d5                 ; height
        beq     .next
        moveq   #0,d0
        move.b  7(a3),d0
        lsl.l   #8,d0
        move.b  6(a3),d0
        lsl.l   #8,d0
        move.b  5(a3),d0
        lsl.l   #8,d0
        move.b  4(a3),d0
        lea     0(a4,d0.l),a0            ; first column
        moveq   #0,d2                    ; column
.column
        move.w  d2,d0
        mulu    d5,d0
        move.l  a0,a1
        adda.l  d0,a1                   ; left end of this column
        move.l  a1,a2
        move.w  d5,d0
        subq.w  #1,d0
        adda.w  d0,a2                   ; right end of this column
        move.w  d5,d1
        lsr.w   #1,d1
        subq.w  #1,d1                   ; DBRA count for height / 2 swaps
        bmi     .column_done
.swap
        move.b  (a1),d0
        move.b  (a2),d3
        move.b  d3,(a1)
        move.b  d0,(a2)
        addq.l  #1,a1
        subq.l  #1,a2
        dbra    d1,.swap
.column_done
        addq.w  #1,d2
        cmp.w   d4,d2
        blo     .column
.next
        addq.w  #1,d6
        cmp.w   d7,d6
        bls     .frame
.done
        movem.l (sp)+,d0-d7/a0-a6
        rts


; The original has three of these and they are not interchangeable. All three
; take the same 8-byte record - width, height, signed/unsigned X offset, Y
; offset, dword data offset - and all three anchor Y at the sprite's BOTTOM
; edge and walk the destination upward, but they differ in two ways that show
; on screen:
;
;   00025880  bank [00019E90], plane-chunked source, OPAQUE.
;             000258A0 forms X - xoff and 000258A6 shifts it right by two,
;             so the sprite lands on a four-pixel VGA byte boundary.
;   0002599E  the same, with `or al,al / je` per byte - index 0 transparent.
;   00025B27  bank [00019E94], COLUMN-MAJOR source, transparent, and placed
;             at full pixel resolution: 00025B94 takes the plane from the low
;             two bits of X - xoff and 00025B9F takes the byte column from the
;             rest, so nothing is quantised.
;
; The console's fixed elements and the attract overlays go through 00025880
; (00007420, 0000743D, 000077B8, 000057C3, 00005A74); the HUD's own elements
; and the value glyphs go through 00025B27 (0000D882, 000074A7, 0000751D,
; 00007633, 0000778B). This port normalises the plane-chunked banks to
; column-major at load, so one writer serves both - but the placement rule
; still has to follow the caller's routine, and until now every sprite was
; being quantised, including the HUD elements the original places to the
; pixel.
;
; Draw one sprite, index 0 transparent, placed to the pixel.
; In: a0 = destination surface, a1 = bank, d0 = sprite index (1-based),
;     d1 = X, d2 = Y, in the DOS parameter block's terms.
; DOS: flat 00025B27-00025BB5, column-major masked sprite blit.
; DOS symbol: sub_00025B27
; Record: analysis/functions/falcon-attract.md#resources
; Port: selects an authored SG frame and draws it into the RGB565 surface.
; Preserved: frame index, offsets, per-pixel placement, clipping,
; transparency, and source order.
; Kind: translated.
; Status: ported; authored cockpit capture verified in Hatari attract flight;
; authored object blits are exercised only by live mission setup.
sprite_draw
        moveq   #BLIT_MASKED,d3
        bra     sprite_blit

; The same two, taking the original's PAGE x rather than a surface x.
;
; Every DOS blitter argument is a page coordinate on the 328-wide Mode X page
; and the displayed window is the middle 320, so a page x is one byte column
; right of the surface x - see PAGE_VIEW_X. These wrappers are what the
; flight console and HUD call, so the conversion lives in one place instead
; of being spelled out at fifteen call sites.
;
; The menu and screen paths deliberately still call sprite_draw directly.
; Their coordinates are page coordinates too - 0002628E's bl is an X in
; four-pixel byte units, so the driver's bl=0x0E is page 56 - but nothing has
; been measured there yet, and shifting them on the strength of the flight
; measurement would be a guess dressed as a fix.
; DOS: the same 00025B27 / 00025880 entries, called with page coordinates.
; Record: analysis/functions/falcon-attract.md#frame-driver
; Port: subtracts the view window's left margin, then draws.
; Preserved: everything sprite_draw preserves; only the origin differs.
; Kind: adapted - platform surface origin.
; Status: ported.
; d1 is restored on the way out. sprite_blit preserves every register, so a
; caller that keeps its own running x in d1 - hud_draw_value steps one digit
; at a time - would otherwise see it four pixels lower after every call and
; walk the digits left across the label. That is what happened.
sprite_draw_page
        move.w  d1,-(sp)
        subi.w  #PAGE_VIEW_X,d1
        moveq   #BLIT_MASKED,d3
        bsr     sprite_blit
        move.w  (sp)+,d1
        rts

sprite_draw_page_opaque
        move.w  d1,-(sp)
        subi.w  #PAGE_VIEW_X,d1
        moveq   #BLIT_QUANTISE_X,d3
        bsr     sprite_blit
        move.w  (sp)+,d1
        rts

; 0002599E: the fourth combination - plane-chunked like 00025880, so the left
; edge lands on the four-pixel VGA byte boundary, but index 0 transparent.
; 000075A8 is its call site, the map's own-ship marker.
sprite_draw_page_masked_quantised
        move.w  d1,-(sp)
        subi.w  #PAGE_VIEW_X,d1
        moveq   #BLIT_MASKED|BLIT_QUANTISE_X,d3
        bsr     sprite_blit
        move.w  (sp)+,d1
        rts

; Draw one sprite opaquely, on the original's four-pixel boundary.
; DOS: flat 00025880-0002590E, plane-chunked opaque sprite blit.
; DOS symbol: sub_00025880
; Record: analysis/functions/falcon-attract.md#resources
; Port: draws an authored frame without transparent-pixel testing.
; Preserved: source traversal, four-pixel destination placement, and clipping.
; Kind: translated.
; Status: ported; capture validation remains pending.
sprite_draw_opaque
        moveq   #BLIT_QUANTISE_X,d3

; d3: BLIT_MASKED treats index 0 as transparent, BLIT_QUANTISE_X snaps the
; left edge to the four-pixel VGA byte boundary. 0002599E is the fourth
; combination - masked and quantised - and has no call site in this port yet.
;
; The sprite spans destination rows [Y + yoff - height + 1, Y + yoff]: all
; three DOS blitters start at Y + yoff and walk upward, so that field
; addresses the sprite's bottom edge, not its top.
; DOS: flat 00025880/0002599E/00025B27, the shared sprite pixel writer.
; DOS symbol: sub_00025880
; Record: analysis/functions/falcon-attract.md#resources
; Port: writes authored source columns into Falcon 16-bit pixels.
; Preserved: offsets, mirror, clipping, transparency, and source order.
; Kind: adapted - platform surface port.
; Status: ported; capture validation remains pending.
sprite_blit
        movem.l d0-d7/a0-a6,-(sp)
        ; The clipping below needs every data register, so the mask flag is
        ; parked in an address register until the inner loop wants it.
        move.l  d3,a6
        tst.w   d0
        beq     .done
        moveq   #0,d4
        move.b  3(a1),d4
        lsl.w   #8,d4
        move.b  2(a1),d4
        cmp.w   d0,d4
        bcs     .done                   ; index past the directory

        move.l  d0,d4
        lsl.l   #3,d4
        lea     0(a1,d4.l),a2           ; the record
        moveq   #0,d4
        move.b  (a2),d4                 ; width
        beq     .done
        moveq   #0,d5
        move.b  1(a2),d5                ; height
        beq     .done
        moveq   #0,d6
        move.b  7(a2),d6
        lsl.l   #8,d6
        move.b  6(a2),d6
        lsl.l   #8,d6
        move.b  5(a2),d6
        lsl.l   #8,d6
        move.b  4(a2),d6
        lea     0(a1,d6.l),a3           ; pixel data, column major

        move.b  2(a2),d6
        ext.w   d6
        sub.w   d6,d1                   ; left edge = X - X offset
        btst    #BLIT_QUANTISE_BIT,d3
        beq     .x_placed
        andi.w  #$fffc,d1               ; 000258A6 `shr eax,2`: the byte edge
.x_placed
        move.b  3(a2),d6
        ext.w   d6
        add.w   d6,d2
        sub.w   d5,d2
        addq.w  #1,d2                   ; top edge

        ; Vertical clip. d7 counts source rows skipped at the top.
        moveq   #0,d7
        tst.w   d2
        bge     .top_ok
        move.w  d2,d7
        neg.w   d7
        cmp.w   d5,d7
        bcc     .done
        sub.w   d7,d5
        moveq   #0,d2
        bra     .rows_set
.top_ok
        cmpi.w  #SCREEN_HEIGHT,d2
        bcc     .done
.rows_set
        move.w  d2,d6
        add.w   d5,d6
        cmpi.w  #SCREEN_HEIGHT,d6
        bls     .height_ok
        move.w  #SCREEN_HEIGHT,d5
        sub.w   d2,d5
.height_ok
        tst.w   d5
        beq     .done

        ; Horizontal clip. d0 counts source columns skipped at the left.
        moveq   #0,d0
        tst.w   d1
        bge     .left_ok
        move.w  d1,d0
        neg.w   d0
        cmp.w   d4,d0
        bcc     .done
        sub.w   d0,d4
        moveq   #0,d1
        bra     .cols_set
.left_ok
        cmpi.w  #SCREEN_WIDTH,d1
        bcc     .done
.cols_set
        move.w  d1,d6
        add.w   d4,d6
        cmpi.w  #SCREEN_WIDTH,d6
        bls     .width_ok
        move.w  #SCREEN_WIDTH,d4
        sub.w   d1,d4
.width_ok
        tst.w   d4
        beq     .done

        ; Source: a column is `height` bytes, so skip whole columns for the
        ; left clip and rows within a column for the top clip. The column
        ; stride stays the stored height even after the vertical clip.
        moveq   #0,d6
        move.b  1(a2),d6                ; stored height = column stride
        move.w  d0,d3
        mulu    d6,d3
        add.l   d3,a3
        adda.w  d7,a3

        ; Destination: row d2, column d1, two bytes per pixel.
        move.w  d2,d3
        mulu    #SCREEN_STRIDE,d3
        add.l   d3,a0
        move.w  d1,d3
        add.w   d3,d3
        adda.w  d3,a0

        ; Whichever palette is installed. The DOS machine has one VGA DAC, so
        ; a sprite is always displayed through the palette the screen last set
        ; - the attract screens draw their overlays through their own screen's
        ; palette, and the bank palettes shipped inside COMA.RLE and ZOVE.RLE
        ; are never in the DAC when the blitter runs.
        move.l  sprite_palette,a4
        move.w  d6,d3
        sub.w   d5,d3                   ; source bytes to skip per column
        move.l  a6,d2                   ; the flags, back from their parking
        andi.w  #BLIT_MASKED,d2
        subq.w  #1,d4                   ; column counter
.column
        move.l  a0,a5                   ; top of this destination column
        move.w  d5,d6
        subq.w  #1,d6
.pixel
        moveq   #0,d1
        move.b  (a3)+,d1
        bne     .write
        tst.w   d2
        bne     .step                   ; masked: index 0 leaves the surface
        move.w  (a4),(a5)                ; opaque: index 0 is a real colour
        bra     .step
.write
        add.w   d1,d1
        move.w  0(a4,d1.w),(a5)
.step
        adda.w  #SCREEN_STRIDE,a5
        dbra    d6,.pixel
        adda.w  d3,a3                   ; past the clipped tail of the column
        addq.l  #2,a0                   ; next destination column
        dbra    d4,.column
.done
        movem.l (sp)+,d0-d7/a0-a6
        rts


; 000253CD-0002560x, as written. The scale index [00022354] selects one of the
; 128 ramps (sprite_ramp_offsets / sprite_ramp_pool, verbatim from the image):
; ramp r is 128 - r bytes summing to 64, and BOTH axes walk the same ramp - each
; destination column consumes `ramp[k]` source columns (00025502-000254F9) and
; each destination row `ramp[j]` source rows (000254E5-000254E7), so a zero
; repeats a source line and a 4 skips three. The anchors are consumed the same
; way: the X offset is subtracted ramp entry by ramp entry until it goes
; negative (00025430-00025438), the Y offset likewise (0002544E-00025456), so
; where the sprite starts is a count of ramp entries, not a product. A sprite
; taller or wider than 64 reads on into the next ramp.
;
; In: d0.w index (mirror bit already stripped), d3.w scale (index+1)*4, a1 the
;   bank; blit_x/blit_y the anchor (page pixel x, screen row of the page row),
;   blit_dest the surface, blit_mirror, sprite_occl, sprite_y_extra and
;   object_no_shear as 00025606 / 000253CC / 0002237E have them.
; Each destination column is one surface byte column, two screen pixels (00007AA0
; expands it): flat column n sits at screen x (n - 48) * 2, page row r (byte) at
; screen row 213 - r, and only n in 48..207 and r in 46..213 are displayed.
; The terrain silhouette test (000254D9 `cmp bl,bh / jb`) and the roll shear
; (000254C4) are per flat column n.
; DOS: flat 000253CD-00025668.
; DOS symbol: sub_000253CD
; Record: analysis/functions/falcon-attract.md#resources
; Port: transcribes the ramp walk onto the Falcon RGB565 surface.
; Preserved: both ramps, the byte-wide anchor arithmetic and its exits, the row
;   counter's wrap, the silhouette compare, the shear, the mirror's reversed walk.
; Difference: columns outside n 48..207 and rows outside 46..213 are not
;   written (they never reach the screen); DOS writes them into the surface.
; Kind: translated; target is chunky RGB565.
; Status: ported; checked against DEMO1 records 20 and 120 explosions.
sprite_draw_ramped
        movem.l d0-d7/a0-a6,-(sp)
        move.w  d3,d4
        lsr.w   #2,d4                           ; index + 1
        move.w  #128,d5
        sub.w   d4,d5                           ; ramp r
        bmi     .rdone
        lea     sprite_ramp_offsets,a5
        move.l  0(a5,d5.w*4),d5
        lea     sprite_ramp_pool,a5
        adda.l  d5,a5
        move.l  a5,blit_ramp

        moveq   #0,d4
        move.w  d0,d4
        lsl.l   #3,d4
        lea     0(a1,d4.l),a2                   ; the record
        moveq   #0,d4
        move.b  (a2),d4                         ; source width
        beq     .rdone
        moveq   #0,d5
        move.b  1(a2),d5                        ; source height
        beq     .rdone
        move.w  d5,blit_h
        moveq   #0,d6
        move.b  7(a2),d6
        lsl.l   #8,d6
        move.b  6(a2),d6
        lsl.l   #8,d6
        move.b  5(a2),d6
        lsl.l   #8,d6
        move.b  4(a2),d6
        lea     0(a1,d6.l),a3                   ; esi: pixel data, column major
        mulu    d5,d4                           ; 00025491 mul ah
        lea     0(a3,d4.l),a0
        move.l  a0,blit_data_end                ; 00025495 [00022370]

        ; X anchor, 00025430-0002543A (mirrored 00025529-00025533).
        moveq   #0,d4
        move.b  2(a2),d4
        move.l  blit_ramp,a6
        tst.w   blit_mirror
        bne.s   .xa_mirror
        moveq   #1,d5                           ; mov dl, 1
.xa
        move.b  (a6)+,d6
        subq.b  #1,d5                           ; dec dl
        sub.b   d6,d4                           ; sub al, cl
        bcc.s   .xa                             ; jae
        bra.s   .xa_done
.xa_mirror
        moveq   #-1,d5                          ; mov dl, 0xFF
.xam
        move.b  (a6)+,d6
        addq.b  #1,d5                           ; inc dl
        sub.b   d6,d4
        bcc.s   .xam
.xa_done
        move.w  blit_x,d6
        tst.w   object_target_view
        bne.s   .v_target
        asr.w   #1,d6
        addi.w  #48,d6                          ; [00022365], the fan column
        bra.s   .v_ready
.v_target
        subi.w  #MFD_SURFACE_X+MFD_PANEL_STEP-MFD_VIEW_SURFACE_FIRST,d6 ; panel pixel -> surface column
.v_ready
        add.b   d6,d5                           ; 0002543A add dl,[00022365]
        move.b  d5,blit_col

        ; Y anchor, 00025446-0002547E (mirrored 00025547-0002556F).
        moveq   #0,d4
        move.b  3(a2),d4
        add.b   sprite_y_extra+1,d4             ; 00025426 add ah,[000253CC]
        move.l  blit_ramp,a6
        tst.w   object_target_view
        bne.s   .page_target
        move.w  #OBJECT_PAGE_ANCHOR,d6
        sub.w   blit_y,d6                       ; [00022366], the page row
        bra.s   .page_ready
.page_target
        moveq   #0,d6
        move.b  object_project_page,d6          ; [00022366]: the panel row halves it
.page_ready
        tst.b   d4
        bpl.s   .ypos
        neg.b   d4
        moveq   #-1,d7                          ; neg dh (dh was 1)
.yn
        move.b  (a6)+,d5
        addq.b  #1,d7
        sub.b   d5,d4
        bcc.s   .yn
        add.b   d6,d7
        bcs     .rdone                          ; 0002545E jb 0002550F
        bra.s   .y_done
.ypos
        moveq   #0,d7                           ; dec dh (dh was 1)
.yp
        move.b  (a6)+,d5
        subq.b  #1,d7
        sub.b   d5,d4
        bcc.s   .yp
        add.b   d6,d7
        bcc     .rdone                          ; 00025478 jae 0002550F
        addq.b  #1,d7                           ; 0002547E inc dh
.y_done
        move.b  d7,blit_row0                    ; 00025480 [0002237C]

        move.l  blit_ramp,a6                    ; the column ramp, 0002549E
        move.b  blit_col,d6                     ; n
        move.l  sprite_palette,a4
        move.l  a3,a0                           ; esi, this column's first byte
.column
        move.l  a6,blit_colramp
        moveq   #0,d0
        move.b  d6,d0
        tst.w   object_target_view
        bne     .col_target
        cmpi.w  #32,d0
        bcs     .col_next                       ; off the surface's left edge
        cmpi.w  #223,d0
        bhi     .col_next
        cmpi.w  #48,d0
        bcs.s   .col_left
        cmpi.w  #207,d0
        bhi.s   .col_right
        move.w  d0,d1
        subi.w  #48,d1
        lsl.w   #2,d1                           ; (n - 48) * 2 pixels * 2 bytes
        move.l  blit_dest,a3
        adda.w  d1,a3
        bra.s   .col_placed
.col_left
        ; Columns the window does not show still exist: 00007AA0's row shear
        ; reads them (render_row_shear), so they go to the margin buffers.
        move.w  d0,d1
        subi.w  #32,d1
        lsl.w   #2,d1
        lea     margin_left,a3
        adda.w  d1,a3
        bra.s   .col_placed
.col_right
        move.w  d0,d1
        subi.w  #208,d1
        lsl.w   #2,d1
        lea     margin_right,a3
        adda.w  d1,a3
.col_placed
        subi.w  #32,d0                          ; c, the backdrop column
        tst.b   object_no_shear
        bne.s   .no_shear
        lea     backdrop_dy,a1
        move.w  d0,d1
        add.w   d1,d1
        move.b  1(a1,d1.w),d4                   ; 000254C4 [eax + 0003CB20]
        bra.s   .shear_ready
.no_shear
        move.b  backdrop_base+1,d4              ; 00025619/0002561F [00019D80] + 0x32
.shear_ready
        moveq   #0,d5
        move.l  sprite_occl,a1
        move.l  a1,d1
        beq.s   .sil_ready
        move.b  0(a1,d0.w),d5                   ; 000254CF-000254D5 bh
        bra.s   .sil_ready
.col_target
        ; The target panel: surface columns 0x58..0xA7 are its 80 pixels
        ; (000079F0), unsheared, and its silhouette is held as the panel's own
        ; screen rows (mfd_target_silhouette), allowed down to that row.
        subi.w  #MFD_VIEW_SURFACE_FIRST,d0
        bmi     .col_next
        cmpi.w  #MFD_W,d0
        bcc     .col_next
        move.w  d0,d1
        add.w   d1,d1
        move.l  blit_dest,a3
        adda.w  d1,a3
        adda.l  #MFD_Y*SCREEN_STRIDE+(MFD_SURFACE_X+MFD_PANEL_STEP)*2,a3
        moveq   #0,d4                           ; no shear
        moveq   #0,d5
        move.l  sprite_occl,a1
        move.l  a1,d1
        beq.s   .sil_target_none
        add.w   d0,d0
        move.w  0(a1,d0.w),blit_sil
        bra.s   .sil_ready
.sil_target_none
        move.w  #$7fff,blit_sil
.sil_ready
        move.l  a0,a2                           ; esi for the rows
        move.l  a0,a1
        moveq   #0,d1
        move.w  blit_h,d1
        adda.l  d1,a1                           ; edi, this column's end
        ; The port stores every object bank's columns top row first
        ; (sprite_bank_flip_rows / sprite_bank_deplane), where DOS keeps the
        ; bottom row first and walks it with dh upward. Reading the stored
        ; column backwards from its end is the same walk: the byte DOS's esi
        ; reads is at column start + (h - 1) - (esi - column start).
        move.l  a0,d3
        add.l   d3,d3
        add.l   d1,d3
        subq.l  #1,d3                           ; the reversed read's base
        move.l  a6,blit_colramp
        move.l  blit_ramp,a5                    ; the row ramp, 000254B2
        move.b  blit_row0,d1                    ; bl
        move.b  d1,d2
        add.b   d4,d2                           ; dh += shear
        move.l  d3,d4
.row
        tst.w   object_target_view
        bne.s   .row_visible
        cmp.b   d5,d1                           ; 000254D9 cmp bl, bh
        bcs.s   .row_skip                       ; jb: below the terrain's top
.row_visible
        move.l  d4,a6
        suba.l  a2,a6
        move.b  (a6),d0
        beq.s   .row_skip                       ; transparent
        tst.w   object_target_view
        bne.s   .store_target
        moveq   #0,d3
        move.b  d2,d3
        subi.w  #46,d3
        cmpi.w  #167,d3
        bhi.s   .row_skip                       ; not one of the 168 rows shown
        move.w  #167,d7
        sub.w   d3,d7
        mulu    #SCREEN_STRIDE,d7
        andi.w  #$00ff,d0
        add.w   d0,d0
        move.w  0(a4,d0.w),d0
        move.w  d0,0(a3,d7.l)
        move.w  d0,2(a3,d7.l)
        bra.s   .row_skip
.store_target
        ; surface row r is panel row (162 - r) / 2 when that is whole, 000079F0
        ; taking every second row down from 162.
        moveq   #0,d3
        move.b  d2,d3
        neg.w   d3
        addi.w  #162,d3                         ; 000079F0's first row, [edx] = ... + 0xA2xx
        bmi.s   .row_skip
        btst    #0,d3
        bne.s   .row_skip
        lsr.w   #1,d3                           ; panel row k
        cmpi.w  #MFD_H,d3
        bcc.s   .row_skip
        move.w  d3,d7
        addi.w  #MFD_Y,d7
        cmp.w   blit_sil,d7
        bgt.s   .row_skip                       ; below the terrain in front
        mulu    #SCREEN_STRIDE,d3
        andi.w  #$00ff,d0
        add.w   d0,d0
        move.w  0(a4,d0.w),0(a3,d3.l)
.row_skip
        moveq   #0,d0
        move.b  (a5)+,d0
        adda.l  d0,a2                           ; 000254E7 add esi, eax
        addq.b  #1,d2                           ; inc dh
        addq.b  #1,d1                           ; inc bl
        beq.s   .col_next                       ; 000254EE je
        cmpa.l  a1,a2
        bcs     .row                            ; 000254F2 jb
.col_next
        move.l  blit_colramp,a6
        moveq   #0,d0
        move.b  (a6)+,d0                        ; 000254F9 mov ah,[ecx]
        mulu    blit_h,d0                       ; f6e4 mul ah
        adda.l  d0,a0
        tst.w   blit_mirror
        bne.s   .step_left
        addq.b  #1,d6                           ; 00025502 add dl,0x80 / adc
        bra.s   .step_done
.step_left
        subq.b  #1,d6                           ; 000255F1 sub dl,0x80 / sbb
.step_done
        cmpa.l  blit_data_end,a0
        bcs     .column                         ; 00025507 jb
.rdone
        movem.l (sp)+,d0-d7/a0-a6
        rts

; Draw one sprite scaled, index 0 transparent. Always masked: the opaque path
; exists for cockpit panels, which are drawn at native size and never scaled.
;
; In: a0 = destination surface, a1 = bank, d0 = sprite index (1-based),
;     d1 = X, d2 = Y, d3 = scale in 8.8 where 256 is native size.
;
; The original scales differently, and it is worth saying how. 0002519D
; searches a distance ramp in the .DTL file for a band, divides 0x08000000 by
; that band's entry, clamps to 127, and hands the result to 000253CD as a
; byte index. Corrected 2026-08-21: 000253CD's own mechanism is now decoded -
; it indexes sprite_scale_offsets/sprite_scale_masks, two static tables whose
; construction makes every row sum to exactly 64 regardless of index, which
; is what makes "index+1 source columns out of 64" the real DOS law rather
; than an approximation of it. The scale below reproduces that law exactly
; (checked at index 0, 20, 64 and 127 against the raw table bytes), not just
; in shape.
;
; The record's X and Y offsets scale with the sprite. They are half-extents in
; practice, so leaving them at native size would make a shrinking sprite drift
; away from the point it is anchored to.
; DOS: flat 0002519D/000253CD, distance-band sprite scaler and blit.
; DOS symbol: inside loc_000250AA
; Record: analysis/functions/falcon-attract.md#resources
; Port: uses the recovered DTL scale relation with Falcon 8.8 output scale.
; Preserved: distance index, ramp length, frame width, offsets, and clipping.
; Kind: translated.
; Status: ported; authored object detail-level capture verified in Hatari
; attract flight checkpoints.
sprite_draw_scaled
        movem.l d0-d7/a0-a6,-(sp)
        ; Stash the arguments rather than digging them back out of the movem
        ; frame later: the clipping below needs every register, and an offset
        ; into that frame is the kind of thing that silently reads the wrong
        ; one.
        move.w  d1,blit_x
        move.w  d2,blit_y
        move.l  a0,blit_dest
        tst.w   d0
        beq     .done

        ; Bit 15 asks for the mirrored half of the azimuth sweep - a bank holds
        ; half a turn and the rest is these same frames reflected. Strip it
        ; BEFORE the bounds check, or every mirrored frame reads as an index of
        ; 32768 and is rejected without drawing anything.
        clr.w   blit_mirror
        move.w  d0,d4
        andi.w  #SPRITE_MIRROR,d4
        beq     .not_mirrored
        move.w  #1,blit_mirror
        andi.w  #SPRITE_MIRROR-1,d0
.not_mirrored
        moveq   #0,d4
        move.b  3(a1),d4
        lsl.w   #8,d4
        move.b  2(a1),d4
        cmp.w   d0,d4
        bcs     .done
        tst.w   d3
        ble     .done

        ; The surface blit proper: 000253CD resamples by the DOS ramps rather
        ; than by a uniform scale. The target panel's copy still goes through
        ; the rectangle path below.
        bsr     sprite_draw_ramped
        bra     .done

        ; The index is a word everywhere it is checked, so take only a word
        ; here. Taking the long instead trusts the caller's high half, and a
        ; caller that returned its result with move.w leaves that half stale -
        ; the bounds check still passes and the record address is wild.
        moveq   #0,d4
        move.w  d0,d4
        lsl.l   #3,d4
        lea     0(a1,d4.l),a2                   ; the record
        moveq   #0,d4
        move.b  (a2),d4                         ; source width
        beq     .done
        moveq   #0,d5
        move.b  1(a2),d5                        ; source height
        beq     .done
        move.w  d4,blit_src_w
        move.w  d5,blit_src_h
        moveq   #0,d6
        move.b  7(a2),d6
        lsl.l   #8,d6
        move.b  6(a2),d6
        lsl.l   #8,d6
        move.b  5(a2),d6
        lsl.l   #8,d6
        move.b  4(a2),d6
        lea     0(a1,d6.l),a3                   ; pixel data, column major

        ; Scaled extents, and the step through the source they imply.
        move.w  d4,d6
        muls.w  d3,d6
        asr.l   #8,d6
        move.w  d6,d0                           ; destination width
        beq     .done
        move.w  d5,d7
        muls.w  d3,d7
        asr.l   #8,d7
        move.w  d7,d1                           ; destination height
        beq     .done

        ; 32-bit divides, not 16. The step is source/destination in 16.16, and
        ; that passes 16 bits as soon as the sprite shrinks - which is the
        ; normal case - so DIVU.W overflows and leaves the step unwritten.
        moveq   #0,d6
        move.w  d4,d6
        swap    d6                              ; source width in 16.16
        moveq   #0,d2
        move.w  d0,d2
        divu.l  d2,d6
        moveq   #0,d7
        move.w  d5,d7
        swap    d7                              ; source height in 16.16
        moveq   #0,d2
        move.w  d1,d2
        divu.l  d2,d7
        move.l  d6,blit_sx_step
        move.l  d7,blit_sy_step

        ; Anchors, scaled with the sprite. X is the centre, Y the bottom edge.
        move.b  2(a2),d6
        ext.w   d6
        muls.w  d3,d6
        asr.l   #8,d6
        ; A destination column is one surface byte column, which 00007AA0
        ; expands to two screen pixels (one to one in the target panel, whose
        ; copy takes a column per pixel), so the anchor in pixels is twice it.
        tst.w   object_target_view
        bne.s   .anchor_x_ready
        add.w   d6,d6
.anchor_x_ready
        move.w  blit_x,d4
        sub.w   d6,d4
        move.b  3(a2),d6
        add.b   sprite_y_extra+1,d6             ; 00025426 add ah,[000253CC]
        ext.w   d6
        muls.w  d3,d6
        asr.l   #8,d6
        move.w  blit_y,d5
        add.w   d6,d5
        sub.w   d1,d5
        addq.w  #1,d5                           ; top row

    ifne USE_DSP
        ; Record the unclipped destination rectangle for the incremental
        ; composition's restore pass, when a list is armed. This is dormant
        ; in the CPU-only attract milestone; its symbols belong to the later
        ; DSP accelerator route and must not leak into the CPU link.
        move.l  dsp_record_list,d6
        beq     .no_record
        move.l  d6,a5
        move.w  (a5),d6
        cmpi.w  #DSP_RLIST_MAX,d6
        blt     .record_fits
        move.w  #1,dsp_rlist_overflow
        bra     .no_record
.record_fits
        addq.w  #1,(a5)
        lsl.w   #3,d6
        lea     2(a5,d6.w),a5
        move.w  d4,(a5)+                        ; left
        move.w  d5,(a5)+                        ; top
        move.w  d0,(a5)+                        ; width
        move.w  d1,(a5)+                        ; height
.no_record
    endc

        ; The target-view call to 00024B17 draws into the DOS surface that
        ; 000079F0 subsequently crops to the right MFD. The Falcon composes
        ; that crop directly, so use the same 80x44 window here; otherwise a
        ; target sprite can spill across the cockpit even when its terrain
        ; span is correctly contained.
        tst.w   object_target_view
        beq     .screen_clip
        moveq   #0,d2                           ; source Y accumulator
        move.w  #MFD_Y,d6
        cmp.w   d6,d5
        bge     .target_top_ok
        sub.w   d5,d6
        cmp.w   d1,d6
        bcc     .done
        sub.w   d6,d1
        move.l  blit_sy_step,d2
        ext.l   d6                              ; muls.l reads all 32 bits
        muls.l  d6,d2
        move.w  #MFD_Y,d5
.target_top_ok
        move.w  d5,d6
        add.w   d1,d6
        cmpi.w  #MFD_Y+MFD_H,d6
        bls     .target_rows_ok
        move.w  #MFD_Y+MFD_H,d1
        sub.w   d5,d1
.target_rows_ok
        tst.w   d1
        ble     .done

        moveq   #0,d3                           ; source X accumulator
        move.w  #MFD_SURFACE_X+MFD_PANEL_STEP,d6
        cmp.w   d6,d4
        bge     .target_left_ok
        sub.w   d4,d6
        cmp.w   d0,d6
        bcc     .done
        sub.w   d6,d0
        move.l  blit_sx_step,d3
        ext.l   d6                              ; muls.l reads all 32 bits
        muls.l  d6,d3
        move.w  #MFD_SURFACE_X+MFD_PANEL_STEP,d4
.target_left_ok
        move.w  d4,d6
        add.w   d0,d6
        cmpi.w  #MFD_SURFACE_X+MFD_PANEL_STEP+MFD_W,d6
        bls     .target_cols_ok
        move.w  #MFD_SURFACE_X+MFD_PANEL_STEP+MFD_W,d0
        sub.w   d4,d0
.target_cols_ok
        tst.w   d0
        ble     .done
        bra     .clip_ready

.screen_clip
        ; No vertical clip here. DOS shears every destination column by the
        ; backdrop's per-column offset (000254C4 `add dh,[eax + 0x3CB20]`), so
        ; where a column's rows land - and what of them the surface keeps -
        ; is only known per column; .column does it. The rectangle's top row
        ; (d5) stays in page space, unsheared, which is also the space the
        ; terrain silhouette test below compares in.
        moveq   #0,d2                           ; sy accumulator, 16.16
        tst.w   d1
        ble     .done

        ; Horizontal clip, likewise.
        moveq   #0,d3                           ; sx accumulator, 16.16
        tst.w   d4
        bge     .left_ok
        move.w  d4,d6
        neg.w   d6
        lsr.w   #1,d6                           ; two pixels per column
        ext.l   d6                              ; muls.l below reads all 32 bits
        cmp.w   d0,d6
        bcc     .done
        sub.w   d6,d0
        move.l  blit_sx_step,d3
        muls.l  d6,d3
        moveq   #0,d4
        bra     .cols_set
.left_ok
        cmpi.w  #SCREEN_WIDTH,d4
        bcc     .done
.cols_set
        move.w  d0,d6
        add.w   d6,d6                           ; the columns' width in pixels
        add.w   d4,d6
        cmpi.w  #SCREEN_WIDTH,d6
        bls     .cols_ok
        move.w  #SCREEN_WIDTH,d0
        sub.w   d4,d0
        lsr.w   #1,d0
.cols_ok
        tst.w   d0
        ble     .done

.clip_ready
        ; Mirroring reverses the walk through the source columns rather than the
        ; walk across the destination: the destination stepping, and every clip
        ; already applied to it, then stay exactly as they are.
        tst.w   blit_mirror
        beq     .not_reversed
        moveq   #0,d6
        move.w  blit_src_w,d6
        swap    d6                              ; source width in 16.16
        sub.l   blit_sx_step,d6
        sub.l   d3,d6                           ; past the columns already clipped
        move.l  d6,d3
        move.l  blit_sx_step,d6
        neg.l   d6
        move.l  d6,blit_sx_step
.not_reversed
        move.l  d2,blit_sy_start
        move.w  d1,blit_rows
        move.w  d5,blit_top_row                 ; first screen row drawn
        move.w  d4,blit_left_col                ; first screen column drawn

        move.l  blit_dest,a0
        move.w  d4,d6
        add.w   d6,d6
        adda.w  d6,a0                           ; the first column; each
                                                ; column adds its own row

        ; Object banks carry their own authored palette. Generic HUD/cockpit
        ; callers still select sprite_palette before entering this routine; the
        ; object handler temporarily points it at the selected mission slot.
        move.l  sprite_palette,a4
        move.l  blit_sx_step,d6
        move.l  blit_sy_step,d7
        subq.w  #1,d0                           ; column counter
.column
        move.l  d3,d1
        swap    d1                              ; source column index
        andi.l  #$0000ffff,d1
        mulu    blit_src_h,d1
        lea     0(a3,d1.l),a1                   ; base of that source column

        move.l  blit_sy_start,d2
        move.w  blit_rows,d5

        ; Terrain clip. When a silhouette row is armed, this column's entry is
        ; the lowest screen row the terrain in front of the model still lets
        ; through; 000254D9 compares the sprite's own row against it and skips
        ; while the sprite is below. That skip is a contiguous run at the
        ; bottom of the column - the test is monotonic in the row - so the
        ; whole of it comes off the row count here rather than costing a
        ; compare per pixel. Same pixels written, in the same order.
        ;
        ; The source column is the DOS one: this port presents 192 source
        ; columns as two pixels each and crops to the recovered page window
        ; starting at TERRAIN_VIEW_FIRST, so screen x >> 1 plus that first
        ; column is the entry 000254C0's `rol al,1` reaches on the DOS surface.
        move.l  sprite_occl,a6
        move.l  a6,d1
        beq     .no_clip
        tst.w   object_target_view
        bne     .target_clip_column
        move.w  blit_left_col,d1
        asr.w   #1,d1
        addi.w  #TERRAIN_VIEW_FIRST,d1
        cmpi.w  #TERRAIN_COLS,d1
        bcc     .no_clip                        ; outside the marched field
        move.b  0(a6,d1.w),d1                   ; the column's page row
        andi.w  #$00ff,d1
        neg.w   d1
        add.w   render_page_anchor,d1           ; as a screen row
        bra     .clip_row_test
.target_clip_column
        move.w  blit_left_col,d1
        subi.w  #MFD_SURFACE_X+MFD_PANEL_STEP,d1
        cmpi.w  #MFD_W,d1
        bcc     .no_clip
        add.w   d1,d1
        move.w  0(a6,d1.w),d1                   ; target MFD screen row
.clip_row_test
        sub.w   blit_top_row,d1
        addq.w  #1,d1                           ; rows above it, inclusive
        ble     .column_done                    ; wholly behind the terrain
        cmp.w   d5,d1
        bge     .no_clip
        move.w  d1,d5
.no_clip
        ; The roll shear. 000254C0-000254C4 take the column's x, look up the
        ; backdrop's per-column vertical offset and add it to the destination
        ; row - the same offset the terrain spans of that column carry, so a
        ; model stands on the ground it is over however far the helicopter
        ; rolls. The terrain puts page row q at screen row
        ; RING_PAGE_ANCHOR - q - dy, which makes this column's first row
        ; blit_top_row - dy. The target view draws into its own unrolled
        ; surface and takes no shear.
        moveq   #0,d4
        tst.w   object_target_view
        bne     .sheared
        move.w  blit_left_col,d1
        asr.w   #1,d1
        addi.w  #TERRAIN_VIEW_FIRST,d1
        cmpi.w  #TERRAIN_COLS,d1
        bcc     .sheared
        add.w   d1,d1
        lea     backdrop_dy,a2
        move.w  0(a2,d1.w),d4                   ; this column's dy
        ; 000254A4/000254AB: [0002237E] set sends the blit to 00025606, which
        ; takes the walker's base [00019D80] + 0x32 for every column instead of
        ; 000254C4's `add dh,[eax + 0x3CB20]`: the chase camera's helicopter
        ; is not sheared by the roll.
        tst.b   object_no_shear
        beq.s   .sheared
        move.w  backdrop_base,d4
.sheared
        move.w  blit_top_row,d1
        sub.w   d4,d1                           ; first screen row of the column
        tst.w   object_target_view
        bne     .rows_clipped                   ; already clipped to the panel
        tst.w   d1
        bge     .row0_ok
        neg.w   d1
        ext.l   d1                              ; muls.l below reads all 32 bits
        cmp.w   d5,d1
        bcc     .column_done                    ; the whole column is above
        sub.w   d1,d5
        move.l  d7,d4
        muls.l  d1,d4                           ; skipped source rows
        add.l   d4,d2
        moveq   #0,d1
        bra     .bottom_clip
.row0_ok
        ; The compose surface is 00007AA0's source and it copies only the 168
        ; terrain rows (surface rows 46..213), so a model standing below them
        ; is not displayed: in the external views, which draw no cockpit, what
        ; shows there is the page's title art. This clipped at the whole
        ; screen and let a near explosion paint over it.
        cmpi.w  #TERRAIN_VIEW_ROWS,d1
        bcc     .column_done
.bottom_clip
        move.w  d1,d4
        add.w   d5,d4
        cmpi.w  #TERRAIN_VIEW_ROWS,d4
        bls     .rows_clipped
        move.w  #TERRAIN_VIEW_ROWS,d5
        sub.w   d1,d5
.rows_clipped
        move.w  d1,d4
        mulu    #SCREEN_STRIDE,d4
        move.l  a0,a5
        adda.l  d4,a5
        subq.w  #1,d5
        tst.w   object_target_view
        beq.s   .pixel_wide
.pixel
        move.l  d2,d1
        swap    d1
        andi.l  #$0000ffff,d1
        moveq   #0,d4
        move.b  0(a1,d1.l),d4
        beq     .skip
        add.w   d4,d4
        move.w  0(a4,d4.w),(a5)
.skip
        adda.w  #SCREEN_STRIDE,a5
        add.l   d7,d2
        dbra    d5,.pixel
        bra.s   .column_done
.pixel_wide
        move.l  d2,d1
        swap    d1
        andi.l  #$0000ffff,d1
        moveq   #0,d4
        move.b  0(a1,d1.l),d4
        beq     .skip_wide
        add.w   d4,d4
        move.w  0(a4,d4.w),d4
        move.w  d4,(a5)
        move.w  d4,2(a5)                        ; the surface byte's second pixel
.skip_wide
        adda.w  #SCREEN_STRIDE,a5
        add.l   d7,d2
        dbra    d5,.pixel_wide

.column_done
        addq.w  #2,blit_left_col
        addq.l  #2,a0
        tst.w   object_target_view
        bne.s   .advance_done
        addq.l  #2,a0                           ; two pixels a column
.advance_done
        add.l   d6,d3
        dbra    d0,.column
.done
        movem.l (sp)+,d0-d7/a0-a6
        rts


; A row of consecutive bank entries drawn across the top of the surface,
; over a four-pixel loader-status block. This is the verification the sprite
; path needs and cannot get any other way: a capture showing recognisable,
; correctly oriented sprites is what distinguishes a working blit from one
; that is merely not crashing. It draws nothing when the bank failed to load,
; so a build without the installed tree is unaffected.
;
; Nothing in the original draws this. It uses sprite_blit, which is the port
; of 00025880, but the status block, the fixed row of consecutive elements
; and their placement are the harness, not recovered composition - so it is
; labelled as such rather than carrying 00025880's record, which the earlier
; header did.
; DOS: N/A - target artefact; diagnostic harness over the 00025880 port.
; DOS symbol: sub_00025880
; Record: analysis/functions/falcon-attract.md#resources
; Port: draws consecutive bank entries and the loader status for a capture.
; Preserved: nothing claimed; this exists to make a capture legible.
; Kind: replaced - diagnostic harness.
; Status: ported; no caller in the milestone build.
sprite_overlay
        movem.l d0-d3/a0-a1,-(sp)

        ; A four-pixel status block at the top left, so a capture says which of
        ; the two failure modes it is looking at rather than just showing an
        ; empty sky: green loaded, red no file, yellow bank rejected.
        move.l  work_screen,a0
        adda.w  #16*SCREEN_STRIDE,a0
        move.w  #$07E0,d3               ; green
        move.w  sprite_bank_status,d0
        cmpi.w  #1,d0
        bne     .not_missing
        move.w  #$F800,d3               ; red
.not_missing
        cmpi.w  #2,d0
        bne     .not_bad
        move.w  #$FFE0,d3               ; yellow
.not_bad
        moveq   #3,d1
.mark_row
        moveq   #3,d2
.mark_col
        move.w  d3,(a0)+
        dbra    d2,.mark_col
        adda.w  #SCREEN_STRIDE-8,a0
        dbra    d1,.mark_row

        tst.w   sprite_bank_status
        bne     .done

        ; Back to the surface base: the status block above walked a0 forward,
        ; and sprite_draw takes the surface itself, not a point inside it.
        move.l  work_screen,a0
        lea     sprite_bank,a1
        moveq   #1,d0                   ; first directory entry
        move.w  #24,d1                  ; X of the first sprite
.next
        move.w  #64,d2                  ; Y is the bottom edge, per the blit
        movem.l d0-d1,-(sp)
        bsr     sprite_draw
        movem.l (sp)+,d0-d1
        addi.w  #46,d1
        addq.w  #1,d0
        cmpi.w  #7,d0
        bcs     .next
.done
        movem.l (sp)+,d0-d3/a0-a1
        rts

        data
        even
; The palette sprite_blit renders through. The flight's shared palette by
; default; the attract screens point it at their own screen palette for the
; length of an overlay draw, which is what the single DOS DAC does for them.
sprite_palette
        dc.l    flight_palette
        even
sprite_name_tank
        dc.b    "TANK.RLE",0
        even
sprite_name_coma
        dc.b    "COMA.RLE",0
        even
sprite_name_cons
        dc.b    "CONS.RLE",0
        even
sprite_name_huds
        dc.b    "HUDS.RLE",0
        even

        bss
        even
bank_is_raw
        ds.w    1
sky_status
        ds.w    1
; The decompressed SKY container; the 512x150 column-major image starts at
; +16 and the palette block behind it.
sky_bank
        ds.b    BANK_BYTES
        even
; The backdrop's 512 strips, transposed row-major at load. render_clear takes
; a SCREEN_WIDTH window of it whose origin is the heading.
sky_image
        ds.b    SKY_STRIPS*SKY_IMAGE_ROWS
        even
; SKY2.RLE's own palette as RGB565 - see sky_palette_build.
sky_palette
        ds.w    256
; sky_image through sky_palette, a doubled pixel a longword, strip-major -
; see sky_rgb_build.
        even
sky_rgb
        ds.l    SKY_STRIPS*SKY_IMAGE_ROWS

sprite_bank
        ds.b    BANK_BYTES
        even
sprite_model
        ds.l    1
        even
sprite_bank_status
        ds.w    1
        even
; Ten native mission slots mirror DOS's ten pointer entries at 00019EA4.
; Each bank is retained for the whole selected mission because objects can
; refer to both f2 and f3 after the resource-list load has completed.
mission_sprite_banks
        ds.b    10*BANK_BYTES
        even
mission_sprite_palettes
        ds.w    10*256
        even
mission_sprite_status
        ds.w    10
        even
blit_sx_step
        ds.l    1
blit_sy_step
        ds.l    1
blit_sy_start
        ds.l    1
blit_src_h
        ds.w    1
blit_src_w
        ds.w    1
blit_top_row
        ds.w    1
blit_left_col
        ds.w    1
; DOS [00022358]: the ring silhouette row the terrain clip reads, or zero
; when no clip is armed. Set by object_draw_sprite around the model blit.
sprite_occl
        ds.l    1
        even
blit_mirror
        ds.w    1
blit_rows
        ds.w    1
blit_x
        ds.w    1
blit_y
        ds.w    1
        even
blit_dest
        ds.l    1
        even
blit_ramp
        ds.l    1
blit_data_end
        ds.l    1
blit_h
        ds.w    1
blit_sil
        ds.w    1
blit_colramp
        ds.l    1
blit_col
        ds.b    1
blit_row0
        ds.b    1
        even
bank_is_planar
        ds.w    1
; Non-zero while sprite_mission_load binds a mission SG bank: 0002B903's
; palette-variant call. sprite_variant_palette is its work copy, 00015F84.
sprite_palette_variant
        ds.w    1
; 000253CC: a byte added to the model record's own Y offset by 00025426; the
; pair draws set it to 0xF8 for the mirrored turret and 0002550F clears it.
sprite_y_extra
        ds.w    1
        even
sprite_variant_palette
        ds.b    768
        even
cockpit_status
        ds.w    1
        even
plane_start
        ds.w    4
        even
deplane_scratch
        ds.b    DEPLANE_SCRATCH
        even
cockpit_bank
        ds.b    BANK_BYTES
        even
cockpit_palette
        ds.w    256
        even
; 00019D88 - the console page selector. 000063BB seeds it with 2 at mission
; start; 00019B83-00019BC3 are its number-key writers, which are not ported.
; instruments_draw reads it as 00007403 does, element = page + 7.
instrument_page
        ds.b    1
        even
instrument_status
        ds.w    1
        even
instrument_bank
        ds.b    BANK_BYTES
        even
instrument_palette
        ds.w    256
        even
hud_status
        ds.w    1
        even
hud_palette
        ds.w    256
        even
hud_bank
        ds.b    BANK_BYTES

        end
