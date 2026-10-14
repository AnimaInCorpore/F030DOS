; Route: analysis/functions/falcon-attract.md#resources.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; Runtime Comanche terrain resources.
;
; D1.DTA and C1.DTA are the first asset family whose on-disk format is proven:
; a 16-byte Kyle DTA header followed by PCX-style byte RLE. The Falcon keeps
; the decoded 1024x1024 maps in BSS so the executable does not carry a two MiB
; copy of installed game data. Missing or damaged files are reported to the
; caller; the DOS program never substitutes a generated landscape.

        include "inc/comanche.s"

        global  resources_init, resources_select_family, resource_map_status
        global  resource_buffer
        global  flight_palette
        global  resource_active_palette, resource_gamma, resource_palette_variant_at
        global  resource_match_colour, resource_named_colours
        global  resource_palette_remap

        global  original_height_map
        global  original_colour_map

RESOURCE_MAP_ERROR = 1
MAP_BYTES = 1024*1024

        text

; DOS: startup manifest 00005604-000066C5 plus mission resource names.
; DOS symbol: inside loc_000055FD
; Record: analysis/functions/falcon-attract.md#resources
; Port: loads the active mission's authored D/C family before game state begins.
; Preserved: resource order, exact decoded sizes, and missing-file failure.
; Kind: translated.
; Status: ported; startup and attract paths select the mission family.
resources_init
        move.w  mission_map_family,d0
        bra     resources_select_family

; Select the terrain family named by the active mission/demo. The installed
; game has four real D/C pairs; there is no procedural map family to use when
; one is missing. In: d0.w = 0..3, where family 0 is D1/C1.
; DOS: 0002913C mission resource-name fill and startup resource dispatch.
; DOS symbol: inside loc_00029127
; Record: analysis/functions/falcon-attract.md#resources
; Port: selects the authored D<n>/C<n> pair without procedural substitutes.
; Preserved: family index, map dimensions, decoder, active mission palette,
; map-index remap, and errors.
; Kind: translated.
; Status: ported; mission-family integration capture remains pending.
resources_select_family
        movem.l d0-d7/a0-a3,-(sp)
        cmpi.w  #3,d0
        bhi     .bad_family
        move.w  d0,resource_family
        lsl.w   #2,d0
        lea     resource_height_names,a0
        move.l  0(a0,d0.w),a1
        lea     resource_colour_names,a0
        move.l  0(a0,d0.w),a2
        clr.w   resource_map_status

        move.l  a1,a0
        lea     original_height_map,a1
        bsr     resource_load_dta
        tst.l   d0
        bne     .height_bad

        move.l  a2,a0
        lea     original_colour_map,a1
        bsr     resource_load_dta
        tst.l   d0
        bne     .colour_bad

        ; Cn.DTA's palette is the source colour meaning.  Keep it before the
        ; shared input buffer is reused for the mission's p/np palette.
        ; DOS: 000164B7 leaves the Cn palette at 00015F84 for 0002B949.
        ; Port: copies the same six-bit triples into Falcon BSS.
        bsr     resource_build_palette
        tst.l   d0
        bne     .colour_bad
        bsr     resource_palette_variant

        ; The first fixed mission resource (p12.dta, np44.dta, ...) is the
        ; active display palette.  DOS uploads it to the one VGA DAC and then
        ; rewrites the decoded colour map into that palette's index space.
        ; The Falcon keeps the same indexed relationship before expanding to
        ; RGB565; only the final surface format differs.
        lea     mission_palette_name,a0
        lea     flight_palette,a1
        bsr     resource_load_palette
        tst.l   d0
        bne     .colour_bad
        ; 0002AA85-0002AB3F resolves the named HUD colours once the palette
        ; is installed, which is here.
        bsr     resource_resolve_named_colours
        ; Console source bytes were loaded before the first mission was known;
        ; now that the active P/NP palette is installed, bind its pixels to the
        ; same DOS index space before any flight frame is composed.
        bsr     console_palette_remap
        bsr     sprite_bind_flight_palettes
        bsr     resource_remap_colour_map
        tst.l   d0
        bne     .colour_bad
        tst.l   d0
        beq     .done
.colour_bad
.height_bad
        move.w  #RESOURCE_MAP_ERROR,resource_map_status
.done
        movem.l (sp)+,d0-d7/a0-a3
        rts
.bad_family
        move.w  #RESOURCE_MAP_ERROR,resource_map_status
        bra     .done

; Load and decode one DTA. In: a0 = filename, a1 = decoded 1 MiB map.
; Out: d0 = 0 on success, -1 if the file cannot be opened, read, validated,
; or decoded to exactly MAP_BYTES bytes.
; DOS: flat 00015DD0-00015E6D, resource file boundary; DTA payload contract.
; DOS symbol: sub_00015DD0
; Record: analysis/functions/falcon-attract.md#resources
; Port: reads one compressed DTA into a bounded GEMDOS staging buffer.
; Preserved: file byte count, PCX-style RLE input, exact 1024x1024 output.
; Kind: adapted - platform/data port.
; Status: ported; damaged or absent input remains an error.
resource_load_dta
        movem.l d1-d7/a0-a6,-(sp)
        move.l  a1,a6

        ; Fopen(path, read-only). The explicit form keeps this routine generic
        ; over an address in a0; the legacy macro only accepts a source label.
        move.w  #0,-(sp)
        move.l  a0,-(sp)
        move.w  #61,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .fail
        move.w  d0,d7

        ; The largest currently selected pair is 661,796 bytes. Keep one
        ; shared compressed buffer, reused for height and colour in sequence.
        pea     resource_buffer
        move.l  #RESOURCE_BUFFER_BYTES,-(sp)
        move.w  d7,-(sp)
        move.w  #63,-(sp)
        trap    #1
        lea     12(sp),sp
        move.l  d0,d6

        move.w  d7,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp

        tst.l   d6
        bmi     .fail
        move.l  d6,resource_file_bytes
        move.l  d6,d0
        lea     resource_buffer,a0
        move.l  a6,a1
        bsr     decode_dta
        bra     .done

.fail
        moveq   #-1,d0
.done
        movem.l (sp)+,d1-d7/a0-a6
        rts

; Decode a Kyle DTA buffer. In: a0 = file bytes, d0 = byte count,
; a1 = 1024x1024 destination. The stream uses the PCX convention where
; bytes with the top two bits set carry a six-bit repeat count and the next
; byte is the value; all other bytes are literals.
; DOS: flat 00016381-0001687D, DTA decoder data contract consumed by the
; original terrain loader.
; Record: analysis/functions/falcon-attract.md#resources
; Port: expands the authored byte-RLE stream into one byte per map cell.
; Preserved: run markers, literal bytes, row order, and exact output length.
; Kind: translated.
; Status: ported; source-resource validation is available locally.
decode_dta
        movem.l d1-d7/a0-a2,-(sp)
        move.l  d0,d6
        cmpi.l  #16,d6
        bcs     .decode_fail

        ; Reject an accidental non-DTA file before interpreting its bytes as
        ; terrain. The header's integer fields are little-endian, but the
        ; ASCII signature is byte ordered and safe to compare as two longs.
        move.l  (a0),d1
        cmpi.l  #$4B796C65,d1              ; "Kyle"
        bne     .decode_fail
        move.l  4(a0),d1
        cmpi.l  #$20445441,d1              ; " DTA"
        bne     .decode_fail

        ; The first two little-endian header words are the map maxima. The
        ; terrain family is proven to be 1024x1024; the following display
        ; words differ between families and are deliberately not used here.
        cmpi.b  #$ff,8(a0)
        bne     .decode_fail
        cmpi.b  #$03,9(a0)
        bne     .decode_fail
        cmpi.b  #$ff,10(a0)
        bne     .decode_fail
        cmpi.b  #$03,11(a0)
        bne     .decode_fail

        ; The stream starts at 128, not 16. res_open_e reads a 128-byte header
        ; with `mov cx,0x80` and the decoder it falls into begins from wherever
        ; that left the file, so the 112 bytes after the signature are header,
        ; not tokens. Decoding from 16 produces 1,048,577 bytes for a 1024x1024
        ; map - one too many - and shifts every pixel.
        adda.l  #128,a0
        subi.l  #128,d6
        move.l  #1024*1024,d7              ; output bytes remaining

.token
        tst.l   d7
        beq     .decode_ok
        tst.l   d6
        beq     .decode_fail

        moveq   #0,d1
        move.b  (a0)+,d1
        subq.l  #1,d6
        moveq   #1,d2
        move.l  d1,d3
        andi.l  #$c0,d3
        cmpi.l  #$c0,d3
        bne     .literal

        move.l  d1,d2
        andi.l  #$3f,d2
        beq     .decode_fail
        tst.l   d6
        beq     .decode_fail
        moveq   #0,d4
        move.b  (a0)+,d4
        subq.l  #1,d6
        bra     .have_run

.literal
        move.l  d1,d4

.have_run
        cmp.l   d7,d2
        bhi     .decode_fail
        move.w  d2,d5
        subq.w  #1,d5
.write_run
        move.b  d4,(a1)+
        subq.l  #1,d7
        dbra    d5,.write_run
        bra     .token

.decode_ok
        moveq   #0,d0
        bra     .decode_done
.decode_fail
        moveq   #-1,d0
.decode_done
        movem.l (sp)+,d1-d7/a0-a2
        rts

; Cn.DTA carries the installed VGA palette immediately after the decoded
; colour map: 0x0C followed by 256 RGB triples. The file stores each component
; in the DOS DAC's 8-bit container, while the DOS loader executes SHR 2 before
; uploading the resulting six-bit component to port 3C9. Convert that exact
; six-bit DAC value to Falcon RGB565; do not reinterpret the bytes as RGB565
; fields.
; DOS: flat 000164B7 palette copy and 0002A9E7 DAC upload.
; DOS symbol: loc_000164B7
; Record: analysis/functions/falcon-attract.md#resources
; Port: preserves the authored Cn index palette for the DOS nearest-colour
; remap, then the active mission palette is expanded separately below.
; Preserved: source entries, DOS SHR 2 reduction, and index meaning.
; Kind: adapted - platform/data port.
; Status: ported; mission palette/remap path is capture-validated in attract.
resource_build_palette
        movem.l d1-d7/a0-a2,-(sp)
        lea     resource_buffer+128,a0
        move.l  resource_file_bytes,d7
        subi.l  #128,d7
        move.l  #MAP_BYTES,d6
.skip_map
        tst.l   d6
        beq     .marker
        tst.l   d7
        beq     .bad
        moveq   #0,d0
        move.b  (a0)+,d0
        subq.l  #1,d7
        moveq   #1,d1
        move.l  d0,d2
        andi.l  #$c0,d2
        cmpi.l  #$c0,d2
        bne     .counted
        move.l  d0,d1
        andi.l  #$3f,d1
        tst.l   d7
        beq     .bad
        addq.l  #1,a0
        subq.l  #1,d7
.counted
        cmp.l   d6,d1
        bhi     .bad
        sub.l   d1,d6
        bra     .skip_map
.marker
        tst.l   d7
        beq     .bad
        cmpi.b  #$0c,(a0)+
        bne     .bad
        subi.l  #1,d7
        cmpi.l  #768,d7
        bcs     .bad

        lea     resource_source_palette,a1
        move.w  #255,d6
.entry
        moveq   #0,d0
        move.b  (a0)+,d0
        lsr.w   #2,d0                           ; DOS DAC red, six bits
        move.b  d0,(a1)+
        moveq   #0,d1
        move.b  (a0)+,d1
        lsr.w   #2,d1                           ; DOS DAC green, six bits
        move.b  d1,(a1)+
        moveq   #0,d1
        move.b  (a0)+,d1
        lsr.w   #2,d1                           ; DOS DAC blue, six bits
        move.b  d1,(a1)+
        dbra    d6,.entry
        moveq   #0,d0
        bra     .out
.bad
        moveq   #-1,d0
.out
        movem.l (sp)+,d1-d7/a0-a2
        rts

; Nearest palette index for one six-bit DAC triple.
;
; This is 0002B820 used the way 0002AA85-0002AB3F uses it - for a single
; colour rather than for every entry of a colour map. The search itself is
; the same one resource_remap_colour_map already runs inline: red and green
; are ramped through resource_gamma (0002B7D0) before comparison, blue is
; only doubled (0002B8BF does the same when it builds the search palette, so
; the two sides are in one space), and the distance is the weighted square
; 0002ABD0/0002AFD0/0002B3D0 tabulate - (30r)^2 + (55g)^2 + (15b)^2.
;
; Verified against the running original at five independent points: the
; triples 0002AA85-0002AB3F resolves produce indices 47, 3, 2, 9 and 6 in a
; model of this routine, and the original's own bytes at 0x2A375-0x2A37A
; read 47, 3, 2, 9 and 6.
;
; The range is 1..254, not 0..255: the original takes it from
; [0x2B814]/[0x2B810], and a capture reads 1 and 254 there.
;
; In:  d0.b = red, d1.b = green, d2.b = blue, six-bit DAC values.
; Out: d0.w = the palette index.
; DOS: flat 0002B820-0002B89C, weighted nearest-colour search.
; DOS symbol: sub_0002B820
; Record: analysis/functions/falcon-attract.md#resources
; Port: the same search over resource_active_palette.
; Preserved: the ramp on red/green, the doubling of blue, the 30/55/15
;   weights, the strict-improvement tie rule, and the 1..254 range.
; Kind: translated.
; Status: ported; certified 5/5 against captured slots.
resource_match_colour
        movem.l d1-d7/a0-a1,-(sp)
        lea     resource_gamma,a1
        ; Whole words: these arrive as bytes and the index arithmetic below
        ; must not carry the caller's upper bits.
        andi.w  #$3f,d0
        andi.w  #$3f,d1
        andi.w  #$3f,d2
        moveq   #0,d3
        move.b  0(a1,d0.w),d3                   ; 0002B828 ramp(red)
        moveq   #0,d4
        move.b  0(a1,d1.w),d4                   ; 0002B833 ramp(green)
        move.w  d2,d5
        add.w   d5,d5                           ; 0002B842 shl bl,1

        lea     resource_active_palette,a0
        adda.w  #3,a0                           ; 0002B854 with first index 1
        move.l  #$7fffffff,d6                   ; 0002B85B best distance
        moveq   #1,d7                           ; best index so far
        move.w  #1,d0                           ; candidate
.scan
        moveq   #0,d1
        move.b  (a0)+,d1
        move.b  0(a1,d1.w),d1                   ; the palette is ramped too
        andi.w  #$00ff,d1
        sub.w   d3,d1
        bpl     .red_abs
        neg.w   d1
.red_abs
        mulu.w  #30,d1
        mulu.w  d1,d1
        move.l  d1,d2

        moveq   #0,d1
        move.b  (a0)+,d1
        move.b  0(a1,d1.w),d1
        andi.w  #$00ff,d1
        sub.w   d4,d1
        bpl     .green_abs
        neg.w   d1
.green_abs
        mulu.w  #55,d1
        mulu.w  d1,d1
        add.l   d1,d2

        moveq   #0,d1
        move.b  (a0)+,d1
        add.w   d1,d1                           ; 0002B8BF, blue is doubled
        sub.w   d5,d1
        bpl     .blue_abs
        neg.w   d1
.blue_abs
        mulu.w  #15,d1
        mulu.w  d1,d1
        add.l   d1,d2

        ; 0002B883's `jb`: strictly better only, so the FIRST minimum wins.
        cmp.l   d6,d2
        bcc     .next
        move.l  d2,d6
        move.w  d0,d7
        tst.l   d2                              ; 0002B892: an exact hit ends it
        beq     .done
.next
        addq.w  #1,d0
        cmpi.w  #255,d0
        blo     .scan
.done
        move.w  d7,d0
        movem.l (sp)+,d1-d7/a0-a1
        rts

; The named HUD colours the original resolves once, when the mission palette
; is installed. They are not constants: each is the nearest index in THIS
; mission's palette to an authored six-bit triple, so a different palette
; gives a different index and a hard-coded one would be wrong.
;
; 0002AA85-0002AB3F, read by address rather than in listing order - the three
; component stores are not written in R,G,B order and taking them as written
; swaps green and blue.
; DOS: flat 0002AA85-0002AB3F, the named colour resolutions.
; DOS symbol: inside loc_0002AA5B
; Record: analysis/functions/falcon-attract.md#resources
; Port: resolves the same triples against the installed palette.
; Preserved: the triples, their order, and the slot each result lands in.
; Kind: translated.
; Status: ported; each slot verified against the original's own byte.
resource_resolve_named_colours
        movem.l d0-d3/a0-a1,-(sp)
        lea     resource_named_triples,a0
        lea     resource_named_colours,a1
        moveq   #RESOURCE_NAMED_COLOURS-1,d3
.one
        ; resource_match_colour preserves d1-d7 and a0-a1, so the cursor and
        ; the counter ride through it untouched.
        moveq   #0,d0
        move.b  (a0)+,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        moveq   #0,d2
        move.b  (a0)+,d2
        bsr     resource_match_colour
        move.b  d0,(a1)+
        dbra    d3,.one
        movem.l (sp)+,d0-d3/a0-a1
        rts

; Mission kind 1 selects the original night-vision palette variant.  The
; function table at 0002A980 points kind 1 at 0002A99D; all other recovered
; kinds in the table are the no-op at 0002A99C.  It transforms Cn's six-bit
; source palette before the common 0002B949 remap.  NP44.DTA is the active
; target palette whose green entries receive the transformed indices.
; DOS: 00029181-0002919A selects the variant; 0002A99D-0002A9E5 applies it.
; DOS symbol: inside loc_0002917B
; Record: analysis/functions/falcon-attract.md#resources
; Port: exact fixed-point-free byte arithmetic over the preserved six-bit
;       palette; the Falcon's RGB565 expansion remains downstream.
; Preserved: index 0, weighted brightness, channel order, and green clamp.
; Kind: translated.
; Status: ported; mission-1 attract capture verifies the green presentation.
resource_palette_variant
        cmpi.l  #1,mission_kind
        bne     .done
        lea     resource_source_palette+3,a0 ; original skips reserved index 0
        bsr     resource_palette_variant_at
.done
        rts

; The transform itself, over any 768-byte six-bit palette. 0002A99D runs it
; through [0002A980] on the palette buffer at 00015F84, which both the Cn
; resource load (00029181) and every mission SG bank load (0002B903, called
; from 0000653D-000066B2 and 0000683B) have just filled, before the common
; nearest-colour remap - so a night mission's models are recoloured exactly as
; its terrain is.
; In: a0 = entry 1 (palette + 3). Clobbers d0-d4, d7, a0.
; DOS: flat 0002A99D-0002A9E5, night-vision palette variant.
; DOS symbol: sub_0002A99D
; Record: analysis/functions/falcon-attract.md#resources
; Port: the same byte arithmetic, applied by the caller to its own buffer.
; Preserved: see resource_palette_variant.
; Kind: translated.
; Status: ported.
resource_palette_variant_at
        move.w  #254,d7                       ; entries 1..255 (255 loops)
.entry
        moveq   #0,d0
        move.b  (a0),d0                       ; red
        moveq   #0,d1
        move.b  1(a0),d1                     ; green
        moveq   #0,d2
        move.b  2(a0),d2                     ; blue

        ; brightness = (2*R + 5*G + B) >> 3, exactly 0002A9B1-0002A9C1.
        move.w  d1,d3
        lsl.w   #2,d3
        add.w   d1,d3
        add.w   d0,d0
        add.w   d0,d3
        add.w   d2,d3
        lsr.w   #3,d3

        ; red = brightness >> 2
        move.w  d3,d4
        lsr.w   #2,d4
        move.b  d4,(a0)

        ; green = min(brightness + 10, 63)
        move.w  d3,d4
        addi.w  #10,d4
        cmpi.w  #63,d4
        bls     .green_ok
        moveq   #63,d4
.green_ok
        move.b  d4,1(a0)

        ; blue = (original blue + brightness) >> 1
        add.w   d3,d2
        lsr.w   #1,d2
        move.b  d2,2(a0)
        addq.l  #3,a0
        dbra    d7,.entry
        rts

; Install a mission's p/np DTA palette.  These files are 16x22 dummy images
; followed by the same 0x0C + 768-byte palette record used by the other Kyle
; resources.  The DOS loader reads p12/np44 before Cn and uploads its six-bit
; values to the single DAC; the colour map is then translated to those indices
; by 0002B949.  The Falcon stores both six-bit triples for the remapper and
; their RGB565 expansion for the true-colour surface.
; In: a0 = authored palette filename, a1 = ignored destination contract kept
;     for the resource-loader family boundary.
; Out: d0 = 0 on success, -1 on malformed/missing input.
; DOS: 000064C9-00006509 and 0002A9E6-0002AA18.
; DOS symbol: inside loc_00006494
; Record: analysis/functions/falcon-attract.md#resources
; Port: GEMDOS file access and RGB565 packing replace DOS file/DAC access;
;       palette identity, reduction, and remap boundary are preserved.
; Preserved: six-bit palette bytes, dimensions, marker validation, palette
; order, and the RGB565 expansion after the DOS palette boundary.
; Kind: adapted - platform/data and true-colour surface.
; Status: ported; source-palette validation is available locally.
resource_load_palette
        movem.l d1-d7/a0-a6,-(sp)
        move.w  #0,-(sp)
        move.l  a0,-(sp)
        move.w  #61,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .bad
        move.w  d0,d7

        pea     resource_buffer
        move.l  #RESOURCE_BUFFER_BYTES,-(sp)
        move.w  d7,-(sp)
        move.w  #63,-(sp)
        trap    #1
        lea     12(sp),sp
        move.l  d0,d6
        move.w  d7,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
        tst.l   d6
        bmi     .bad
        cmpi.l  #128,d6
        bls     .bad

        lea     resource_buffer,a0
        move.l  (a0),d1
        cmpi.l  #$4B796C65,d1
        bne     .bad
        move.l  4(a0),d1
        cmpi.l  #$20445441,d1
        bne     .bad

        ; Width/height are little-endian words at the same DTA offsets as the
        ; original reader.  All shipped p/np files are 16x22.
        moveq   #0,d4
        move.b  9(a0),d4
        lsl.w   #8,d4
        move.b  8(a0),d4
        addq.l  #1,d4
        moveq   #0,d5
        move.b  11(a0),d5
        lsl.w   #8,d5
        move.b  10(a0),d5
        addq.l  #1,d5
        mulu.w  d5,d4
        lea     128(a0),a0
        move.l  d6,d7
        subi.l  #128,d7
.skip_pixels
        tst.l   d4
        beq     .palette_marker
        tst.l   d7
        beq     .bad
        moveq   #0,d0
        move.b  (a0)+,d0
        subq.l  #1,d7
        moveq   #1,d1
        move.l  d0,d2
        andi.l  #$c0,d2
        cmpi.l  #$c0,d2
        bne     .pixel_literal
        move.l  d0,d1
        andi.l  #$3f,d1
        beq     .bad
        tst.l   d7
        beq     .bad
        addq.l  #1,a0
        subq.l  #1,d7
.pixel_literal
        cmp.l   d4,d1
        bhi     .bad
        sub.l   d1,d4
        bra     .skip_pixels

.palette_marker
        tst.l   d7
        beq     .bad
        cmpi.b  #$0c,(a0)+
        bne     .bad
        subi.l  #1,d7
        cmpi.l  #768,d7
        bcs     .bad
        lea     resource_active_palette,a1
        lea     flight_palette,a2
        move.w  #255,d5
.palette_entry
        moveq   #0,d0
        move.b  (a0)+,d0
        lsr.w   #2,d0                           ; six-bit red
        move.b  d0,(a1)+
        move.w  d0,d1
        lsr.w   #1,d1
        lsl.w   #8,d1
        lsl.w   #3,d1
        move.w  d1,d3
        moveq   #0,d1
        move.b  (a0)+,d1
        lsr.w   #2,d1                           ; six-bit green
        move.b  d1,(a1)+
        lsl.w   #5,d1
        or.w     d1,d3
        moveq   #0,d1
        move.b  (a0)+,d1
        lsr.w   #2,d1                           ; six-bit blue
        move.b  d1,(a1)+
        lsr.w   #1,d1
        or.w     d1,d3
        move.w   d3,(a2)+
        dbra    d5,.palette_entry
        moveq   #0,d0
        bra     .out
.bad
        moveq   #-1,d0
.out
        movem.l (sp)+,d1-d7/a0-a6
        rts

; Build the DOS 0002B949 nearest-colour table from Cn's source palette to the
; active p/np palette, then rewrite the decoded map in place.  This is the
; missing boundary that made NP44 missions render through C4's brown colours.
; The ramp and 30/55/15 squared metric are the recovered 0002B7D0/
; 0002ABD0/0002AFD0/0002B3D0 tables. Candidates 1..254 are searched in
; ascending order; indices 0 and 255 remain reserved and pass through.
; DOS: 0002B820-0002B9BA, palette match and map rewrite.
; DOS symbol: sub_0002B820
; Record: analysis/functions/falcon-attract.md#resources
; Port: same index translation over Falcon BSS, followed by RGB565 lookup.
; Preserved: source/target colour spaces, tie order, reserved indices, and
; complete map rewrite; only the final pixel surface is platform-specific.
; Kind: translated/adapted - true-colour surface.
; Status: ported; validated against the NP44 attract scene.
resource_remap_colour_map
        movem.l d0-d7/a0-a6,-(sp)
        lea     resource_gamma,a4
        lea     resource_palette_map,a6
        move.b  #0,(a6)+
        moveq   #1,d7
.source_entry
        lea     resource_source_palette,a0
        move.w  d7,d0
        add.w   d0,d0
        move.w  d7,d1
        add.w   d1,d1
        add.w   d7,d1                           ; index * 3
        adda.w  d1,a0
        moveq   #0,d0
        move.b  (a0)+,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        moveq   #0,d2
        move.b  (a0)+,d2
        moveq   #0,d3
        move.b  0(a4,d0.w),d3                   ; source red key
        moveq   #0,d4
        move.b  0(a4,d1.w),d4                   ; source green key
        add.w   d2,d2
        move.w  d2,d5                           ; source blue key
        move.l  #-1,resource_best_distance
        clr.w   resource_best_index
        move.w  #1,resource_candidate_index
.candidate
        move.w  resource_candidate_index,d2
        move.w  d2,d0
        add.w   d0,d0
        move.w  resource_candidate_index,d1
        add.w   d1,d1
        add.w   resource_candidate_index,d1      ; candidate index * 3
        lea     resource_active_palette,a0
        adda.w  d1,a0
        moveq   #0,d0
        move.b  (a0)+,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        moveq   #0,d2
        move.b  (a0)+,d2
        ; 0002B89D has already ramped the installed palette's red and green
        ; components before 0002B820 compares them.  Ramp this candidate red
        ; before subtracting the source key; green follows the same sequence
        ; below.
        move.b  0(a4,d0.w),d0
        moveq   #0,d6
        sub.w   d3,d0
        bpl     .r_abs
        neg.w   d0
.r_abs
        moveq   #0,d6
        move.w  d0,d6
        mulu.w  #30,d6
        mulu.w  d6,d6
        moveq   #0,d0
        move.b  0(a4,d1.w),d0
        sub.w   d4,d0
        bpl     .g_abs
        neg.w   d0
.g_abs
        moveq   #0,d1
        move.w  d0,d1
        mulu.w  #55,d1
        mulu.w  d1,d1
        add.l   d1,d6
        add.w   d2,d2
        sub.w   d5,d2
        bpl     .b_abs
        neg.w   d2
.b_abs
        ; The original doubles blue before the distance lookup, but unlike
        ; red/green it does not pass blue through 0002B7D0.  The recovered
        ; 0002B3D0 table is therefore (15 * abs(2*B - 2*b))^2.
        mulu.w  #15,d2
        mulu.w  d2,d2
        add.l   d2,d6
        ; Candidate index is reconstructed from the loop cursor after d2 was
        ; used for the blue distance.  Store only on a strict improvement so
        ; the original's first-minimum tie rule remains intact.
        cmp.l   resource_best_distance,d6
        bcc     .candidate_next
        move.l  d6,resource_best_distance
        move.w  resource_candidate_index,resource_best_index
.candidate_next
        move.w  resource_candidate_index,d2
        addq.w  #1,d2
        move.w  d2,resource_candidate_index
        cmpi.w  #255,d2
        blo     .candidate
        move.w  resource_best_index,d0
        move.b  d0,(a6)+
        addq.w  #1,d7
        cmpi.w  #255,d7
        blo     .source_entry
        move.b  #255,(a6)

        ; The first DOS attract replay is the proven mission-1/family-3 pair:
        ; C4 after 0002A99D's kind-1 transform, against the authored NP44 DAC.
        ; This table is the precomputed output of 0002B820-0002B9BA, so the
        ; Falcon performs the same index translation without a per-load search.
        ; It is data-equivalent to the DOS argmin, not a substitute scene or a
        ; behavioural choice; other recovered families use the generic matcher.
        cmpi.w  #1,mission_index
        bne     .rewrite_map
        cmpi.w  #3,resource_family
        bne     .rewrite_map
        lea     resource_night_map,a0
        lea     resource_palette_map,a1
        move.w  #255,d7
.copy_night_map
        move.b  (a0)+,(a1)+
        dbra    d7,.copy_night_map

.rewrite_map
        lea     original_colour_map,a0
        lea     resource_palette_map,a1
        ; MAP_BYTES is 1 MiB. DBRA would only consume the low word of this
        ; count and leave the final 768 KiB in the source palette's index
        ; space, which is visible as isolated red/orange terrain pixels.
        move.l  #MAP_BYTES/4,d7
.map_quad
        moveq   #0,d0
        move.b  (a0),d0
        move.b  0(a1,d0.w),(a0)+
        moveq   #0,d0
        move.b  (a0),d0
        move.b  0(a1,d0.w),(a0)+
        moveq   #0,d0
        move.b  (a0),d0
        move.b  0(a1,d0.w),(a0)+
        moveq   #0,d0
        move.b  (a0),d0
        move.b  0(a1,d0.w),(a0)+
        subq.l  #1,d7
        bne     .map_quad
        moveq   #0,d0
        movem.l (sp)+,d0-d7/a0-a6
        rts

; Build a Falcon RGB565 lookup for a bank/DTA palette in the installed DOS
; palette's index space. In: a0 = 256 six-bit RGB triples, a1 = 256-word
; output. This is the same load-time boundary as 0002B8C5/0002B949; callers
; keep their authored pixel bytes and use this table when composing.
; DOS: flat 0002B820-0002B9BA, nearest-colour search and payload translation.
; DOS symbol: sub_0002B820
; Record: analysis/functions/falcon-attract.md#resources
; Port: applies the recovered search to a true-colour lookup instead of
; rewriting the source bank; the RGB565 word is the Falcon-only surface step.
; Preserved: six-bit channel meaning, gamma keys, weights, candidate order,
; reserved indices, and first-minimum tie rule.
; Kind: adapted - true-colour surface.
; Status: ported; used by the flight sky and console resource bindings.
resource_palette_remap
        movem.l d0-d7/a0-a6,-(sp)
        move.l  a0,a5                           ; source triples
        move.l  a1,a6                           ; RGB565 output
        lea     resource_active_palette,a4
        lea     resource_gamma,a3
        lea     flight_palette,a2
        moveq   #0,d7                           ; source index
.source
        moveq   #0,d3
        move.b  (a5)+,d3
        moveq   #0,d4
        move.b  (a5)+,d4
        moveq   #0,d5
        move.b  (a5)+,d5
        tst.w   d7
        beq     .reserved
        cmpi.w  #255,d7
        beq     .reserved
        move.b  0(a3,d3.w),d3                  ; red match key
        move.b  0(a3,d4.w),d4                  ; green match key
        add.w   d5,d5                           ; blue match key
        move.l  #$7fffffff,resource_best_distance
        clr.w   resource_best_index
        move.w  #1,resource_candidate_index
.candidate
        move.w  resource_candidate_index,d0
        move.w  d0,d1
        add.w   d1,d1
        add.w   d0,d1                           ; candidate * 3
        moveq   #0,d2
        move.b  0(a4,d1.w),d2
        move.b  0(a3,d2.w),d2
        sub.w   d3,d2
        bpl     .red_abs
        neg.w   d2
.red_abs
        mulu.w  #30,d2
        mulu.w  d2,d2
        move.l  d2,d1                          ; running distance

        move.w  resource_candidate_index,d0
        move.w  d0,d2
        add.w   d2,d2
        add.w   d0,d2                           ; candidate * 3
        moveq   #0,d0
        move.b  1(a4,d2.w),d0
        move.b  0(a3,d0.w),d0
        sub.w   d4,d0
        bpl     .green_abs
        neg.w   d0
.green_abs
        mulu.w  #55,d0
        mulu.w  d0,d0
        add.l   d0,d1

        move.w  resource_candidate_index,d0
        move.w  d0,d2
        add.w   d2,d2
        add.w   d0,d2                           ; candidate * 3
        moveq   #0,d0
        move.b  2(a4,d2.w),d0
        add.w   d0,d0
        sub.w   d5,d0
        bpl     .blue_abs
        neg.w   d0
.blue_abs
        mulu.w  #15,d0
        mulu.w  d0,d0
        add.l   d0,d1

        cmp.l   resource_best_distance,d1
        bcc     .candidate_next
        move.l  d1,resource_best_distance
        move.w  resource_candidate_index,d0
        move.w  d0,resource_best_index
.candidate_next
        addq.w  #1,resource_candidate_index
        cmpi.w  #255,resource_candidate_index
        blo     .candidate
        move.w  resource_best_index,d0
        bra     .write
.reserved
        move.w  d7,d0
.write
        add.w   d0,d0
        move.w  0(a2,d0.w),(a6)+
        addq.w  #1,d7
        cmpi.w  #256,d7
        blo     .source
        moveq   #0,d0
        movem.l (sp)+,d0-d7/a0-a6
        rts

        data
        even
; 0002AA85-0002AB3F's authored triples, six-bit R,G,B, in the order the
; original resolves them. Read by ADDRESS from the listing: the three
; component stores are not written in R,G,B order.
RESOURCE_NAMED_COLOURS = 10
resource_named_triples
        dc.b    $3f,$3f,$3f                     ; 0002AA9F -> 0x2A374
        dc.b    $28,$28,$28                     ; 0002AABF -> 0x2A377
        dc.b    $1c,$1c,$1c                     ; 0002AADF -> 0x2A376
        dc.b    $10,$10,$10                     ; 0002AAFF -> 0x2A375
        dc.b    $10,$30,$3f                     ; 0002AB1F -> 0x2A378
        dc.b    $10,$3f,$10                     ; 0002AB3F -> 0x2A37A
        dc.b    $3f,$10,$3f                     ; 0002AB5F -> 0x2A37B
        dc.b    $3f,$38,$10                     ; 0002AB7F -> 0x2A37D
        dc.b    $3f,$20,$10                     ; 0002AB9F -> 0x2A37C, the C gauge
        dc.b    $3f,$10,$10                     ; 0002ABBF -> 0x2A379, the T gauge
        even

; DOS 0002B7D0's initialized 64-entry red/green matching ramp is filled
; from the player's COMANCHE.EXE at startup (src/origexe.s); its storage is in
; this file's BSS.
resource_night_map
        dc.b    0,21,29,18,16,15,12,16,23,16,12,15,21,34,33,31
        dc.b    27,19,35,32,32,27,34,29,18,16,21,23,16,15,15,12
        dc.b    21,16,18,29,23,34,33,36,34,31,33,36,29,15,12,23
        dc.b    31,27,18,12,12,20,13,20,15,12,18,36,23,26,32,19
        dc.b    36,19,31,34,21,16,12,26,13,13,23,29,29,35,13,36
        dc.b    34,33,18,22,27,33,19,34,31,15,36,12,18,23,18,35
        dc.b    26,26,13,29,18,21,20,22,29,18,35,13,28,19,22,33
        dc.b    18,22,13,20,13,20,26,22,22,30,28,28,15,23,30,30
        dc.b    20,21,33,17,30,26,28,26,22,17,16,12,17,17,29,30
        dc.b    24,37,13,15,12,28,24,20,18,16,28,13,20,26,39,21
        dc.b    18,15,29,30,30,12,13,17,39,44,23,20,24,50,39,15
        dc.b    22,15,21,22,21,37,36,17,30,33,31,20,23,37,17,24
        dc.b    37,37,199,121,24,31,129,36,19,12,129,27,36,131,22,26
        dc.b    30,28,22,26,13,30,21,26,28,34,15,26,13,26,20,22
        dc.b    22,27,29,29,36,15,29,57,21,20,50,21,50,12,15,17
        dc.b    24,24,30,30,28,31,29,16,21,50,21,39,46,14,14,255
resource_height_names
        dc.l    resource_height_1,resource_height_2
        dc.l    resource_height_3,resource_height_4
resource_colour_names
        dc.l    resource_colour_1,resource_colour_2
        dc.l    resource_colour_3,resource_colour_4
resource_height_1
        dc.b    "D1.DTA",0
resource_height_2
        dc.b    "D2.DTA",0
resource_height_3
        dc.b    "D3.DTA",0
resource_height_4
        dc.b    "D4.DTA",0
resource_colour_1
        dc.b    "C1.DTA",0
resource_colour_2
        dc.b    "C2.DTA",0
resource_colour_3
        dc.b    "C3.DTA",0
resource_colour_4
        dc.b    "C4.DTA",0

        bss
        even
        global  resource_gamma
resource_gamma
        ds.b    64
        even
        even
resource_map_status
        ds.w    1
resource_family
        ds.w    1
flight_palette
        ds.w    256
        even
; Cn source palette, active p/np palette in DOS six-bit DAC space, and the
; translated map indices.  The runtime palettes are small; keeping them here
; also means every DSP/CPU consumer sees the same installed index space.
resource_source_palette
        ds.b    768
resource_active_palette
        ds.b    768
; The resolved indices, in resource_named_triples' order. Slot 5 is
; [0x2A37A], the colour 00025C55's callers load into cl; slot 8 is [0x2A37C]
; and slot 9 [0x2A379], which the C and T gauges at 0000D561/0000D5A5 load.
resource_named_colours
        ds.b    RESOURCE_NAMED_COLOURS
        even
resource_palette_map
        ds.b    256
        even
resource_best_distance
        ds.l    1
resource_best_index
        ds.w    1
resource_candidate_index
        ds.w    1
        even
resource_file_bytes
        ds.l    1
        even
resource_buffer
        ds.b    RESOURCE_BUFFER_BYTES

        end
