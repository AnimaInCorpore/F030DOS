; Route: analysis/functions/falcon-attract.md#terrain-renderer.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; The detail level, at runtime.
;
; The original ships HIGH.DTL, MEDIUM.DTL and LOW.DTL - 250, 180 and 100 depth
; rings in one 5004-byte layout - and 00026211 picks one by the settings byte
; [00025DD4], reloading only when it differs from the cached copy at
; [00025DAB]. 00015DD0 reads the chosen file to 0x19EE0, so the file's own
; first dword becomes the ring count [0x19EE0], and every later consumer
; indexes FIXED absolute offsets into it:
;
;   +4     0x19EE4   table 0, the per-ring lateral increment   (0000D9BB)
;   +1004  0x1A2CC   table 1, the per-ring forward increment   (0000D99B)
;   +2004  0x1A6B4   table 2, the projection slope             (00015ADA)
;   +3004  0x1AA9C   table 3, the projection bias              (00015B0A)
;   +4004  0x1AE84   table 4, the cumulative depth             (000251E0)
;
; Those offsets are the file's own table boundaries only for a 250-entry
; file; for MEDIUM and LOW they land partway into the next table, and the
; original reads them there anyway. This port keeps that, because the tables
; it derives have to be the ones the original derives.
;
; 00015AD9 then builds one 256-byte projection page per ring out of tables 2
; and 3. dtl_build_pages below is that routine.
;
; Why this exists at all: the port had MEDIUM.DTL's tables generated into the
; binary at build time by tools/prepare-original-test.py, so the Detail menu
; wrote a byte nothing read. The generated tables are still the initial
; contents - a build with no .DTL staged still runs, and it is the
; configuration tools/certify-marcher.py measured - and this file overwrites
; them in place when the setting selects a different file.
;
; This port ships HIGH, and the cost of that is measured rather than assumed.
; A/B from one binary, flipping only COMANCHE.MNU's detail byte so the runtime
; reload does the work, counting replay records consumed between VBL 3400 and
; 4400 with build/rate.sh:
;
;   HIGH    250 rings   128 game frames / 1000 VBL
;   MEDIUM  180 rings   168 game frames / 1000 VBL
;
; High is 24% slower, and medium runs 1.31x the rate.
;
; Re-measured after the five console images were staged. That costs a flat 8
; frames at either detail level, so the ratio survives it: the first reading
; here was 136 against 176, taken when only CONSOL1S was present and
; console_select_variant therefore had nothing to load.
;
; What it buys is depth resolution and not draw distance: 250 rings against
; 180 over 985 versus 954 map units, so the far ring moves about 3% while the
; sampling between here and there gets 39% finer. 39% more rings costing 24%
; also says the marcher is not the whole frame, and that a further ring
; increase would not scale linearly either.
;
; Decision, 2026-09-03: keep HIGH. It is a runtime setting, so reversing it is
; the same one byte in COMANCHE.MNU that selects it - no rebuild - but the
; oracle's byte has to move with it or nothing measured is comparable. See
; docs/DOS-ORACLE.md.

        include "inc/comanche.s"
        include "inc/gemdos.s"

        global  dtl_apply_settings, dtl_status, dtl_reload
        ; ring_steps is defined with the tables it counts, in the
        ; generated build/original_test.s that render.s includes -
        ; initialised there, because a dc.w in BSS is zero-filled at
        ; load and every ring walk would terminate at once.
        xref    ring_steps

        xref    ring_a_table, ring_b_table, ring_z_table, ring_page_table
        xref    menu_settings
        ; The horizon tables are rebuilt in render.s: they need the
        ; generated depth schedule and RING_PAGE_ANCHOR, which live
        ; with the tables there, and render_horizon_for_depth is the
        ; routine that reads what they build.
        xref    render_rebuild_horizons
        xref    terrain_lowres, sky_enabled

; The file is one dword of count and five 1000-byte tables.
DTL_FILE_BYTES  = 5004
DTL_COUNT_OFF   = 0
DTL_LATERAL_OFF = 4
DTL_FORWARD_OFF = 1004
DTL_SLOPE_OFF   = 2004
DTL_BIAS_OFF    = 3004
DTL_DEPTH_OFF   = 4004

; HIGH.DTL's count, and the largest any consumer must be sized for.
DTL_MAX_STEPS   = 250

; 00019CEC, initialised data with exactly one reader. comanche.s already
; carries the derivation; this is the value 00015AE5 loads.
DTL_PROJ_SCALAR = $03000000

DTL_STATUS_OK    = 0
DTL_STATUS_ERROR = 1

        text

; Apply the settings block's detail byte, reloading the depth tables when it
; has changed. This is 00026211-00026273: compare [00025DD4] against the
; cached [00025DAB], load high/medium/low on a difference, rebuild, and cache.
;
; DOS: flat 00026211-00026278, the detail-level reload and its cache.
; DOS symbol: inside loc_000261AF
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: reloads the selected .DTL and rebuilds every table derived from it.
; Preserved: the '0'/'1'/else selection, the changed-only guard, and the cache
;   write that follows a successful load.
; Difference: 00026283/00026288's two tail calls - the sound bank rebind at
;   0002B9CF and 00001C79 - are not this file's business and are not called
;   here; the detail byte does not reach them.
; Kind: translated.
; Status: ported; a missing or short .DTL is reported through dtl_status, and
;   main stops when the first load fails rather than drawing no world.
dtl_apply_settings
        movem.l d0-d1/a0,-(sp)

        ; 000261F4/000261FE/00026207 first, and unconditionally - the marcher
        ; choice is not behind the detail-byte guard. '}' at [0x25DD9] keeps
        ; the 192-column marcher 0000D950; anything else installs the
        ; 96-column 000137F0, which samples every other source column, gives
        ; each sample the pair (c, c+1), and duplicates its compose block at
        ; 0001453D. The port carries that as a flag rather than a code
        ; pointer, because its marcher is one parameterised routine.
        lea     menu_settings,a0
        move.b  5(a0),d0                        ; [0x25DD9]
        moveq   #1,d1
        cmpi.b  #'}',d0
        bne     .lowres
        moveq   #0,d1
.lowres
        move.w  d1,terrain_lowres

        ; 000261CD, the other half of the same block: '}' at [0x25DD8]
        ; installs the sourced sky fills 0x17230/0x1C920/0x16EC0, anything
        ; else leaves 0x1757E/0x1CAD0/0x1757E - the flat viewport fill - in
        ; all three slots.
        move.b  4(a0),d0                        ; [0x25DD8]
        moveq   #0,d1
        cmpi.b  #'}',d0
        bne     .sky_off
        moveq   #1,d1
.sky_off
        move.w  d1,sky_enabled

        lea     menu_settings,a0
        move.b  (a0),d0                         ; [0x25DD4]
        cmp.b   dtl_cached,d0                   ; 00026216 against [0x25DAB]
        beq     .done                           ; 0002621C: unchanged
        bsr     dtl_reload
        tst.w   dtl_status
        bne     .done                           ; a failed load keeps the cache
        lea     menu_settings,a0
        move.b  (a0),dtl_cached                 ; 00026278
.done
        movem.l (sp)+,d0-d1/a0
        rts

; Load the .DTL the detail byte selects and rebuild everything derived from
; it. Out: dtl_status.
;
; DOS: flat 0002621E-0002626E, the three-way file selection.
; DOS symbol: inside loc_00026211
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: reads the selected file into one staging buffer and rebuilds.
; Preserved: '0' selects high, '1' medium, anything else low - so a corrupt
;   settings byte lands on low detail, as the original's `jne` chain does.
; Kind: translated.
; Status: ported; the read is GEMDOS rather than 00015DD0's DOS call.
dtl_reload
        movem.l d0-d2/a0-a1,-(sp)
        clr.w   dtl_status

        lea     menu_settings,a0
        move.b  (a0),d0
        lea     dtl_name_low,a0                 ; 0002625C, the else branch
        cmpi.b  #'0',d0
        bne     .not_high
        lea     dtl_name_high,a0                ; 0002622C
        bra     .have_name
.not_high
        cmpi.b  #'1',d0
        bne     .have_name
        lea     dtl_name_medium,a0              ; 0002624A
.have_name
        bsr     dtl_read_file
        tst.w   dtl_status
        bne     .done
        bsr     dtl_rebuild
.done
        movem.l (sp)+,d0-d2/a0-a1
        rts

; Read one .DTL into dtl_file. In: a0 = filename. Out: dtl_status.
;
; A short read is an error rather than a partial table: the count dword would
; still parse and the marcher would walk rings whose increments were never
; written, which draws a plausible landscape out of stale memory.
;
; DOS: flat 00015DD0-00015E6D, the resource file read.
; DOS symbol: sub_00015DD0
; Record: analysis/functions/falcon-attract.md#resources
; Port: GEMDOS open/read/close into the fixed-size staging buffer.
; Preserved: the whole file is read at once and its first dword is the count.
; Kind: adapted - platform file boundary.
; Status: ported; a missing file is an error, not a generated schedule.
dtl_read_file
        movem.l d1-d3/a0-a1,-(sp)

        move.w  #0,-(sp)                        ; read only
        move.l  a0,-(sp)
        move.w  #61,-(sp)                       ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .fail
        move.w  d0,d3

        pea     dtl_file
        move.l  #DTL_FILE_BYTES,-(sp)
        move.w  d3,-(sp)
        move.w  #63,-(sp)                       ; Fread
        trap    #1
        lea     12(sp),sp
        move.l  d0,d2

        move.w  d3,-(sp)
        move.w  #62,-(sp)                       ; Fclose
        trap    #1
        addq.l  #4,sp

        cmpi.l  #DTL_FILE_BYTES,d2
        bne     .fail
        bra     .done
.fail
        move.w  #DTL_STATUS_ERROR,dtl_status
.done
        movem.l (sp)+,d1-d3/a0-a1
        rts

; Rebuild every table the loaded .DTL feeds. Out: dtl_status.
;
; The file is little-endian and the 68030 is not, so each dword is swapped as
; it is copied. The generated tables already hold their values the right way
; round, which is why this is the only place the byte order is handled.
;
; DOS: flat 00015AD9-00015B53 plus the fixed table offsets its callers use.
; DOS symbol: sub_00015AD9
; Record: analysis/functions/falcon-attract.md#terrain-renderer
; Port: rewrites the ring tables and projection pages from the loaded file.
; Preserved: the ring count is the file's own first dword, the table offsets
;   are the original's absolute ones, and the pages are 00015B24's arithmetic.
; Kind: translated.
; Status: ported; certified by re-running tools/certify-marcher.py, which
;   scores the rebuilt tables the same way it scores the generated ones.
dtl_rebuild
        movem.l d0-d7/a0-a6,-(sp)

        ; The count is the file's own first dword. A file whose count is zero
        ; or past HIGH.DTL's 250 is refused rather than clamped: every array
        ; below is sized for 250 and a larger count would write past all of
        ; them.
        lea     dtl_file+DTL_COUNT_OFF,a0
        bsr     dtl_swap_long
        tst.l   d0
        beq     .bad
        cmpi.l  #DTL_MAX_STEPS,d0
        bhi     .bad
        move.w  d0,ring_steps

        moveq   #0,d7
        move.w  ring_steps,d7                   ; the ring count, 1..250

        ; Tables 1, 0 and 4 are copied straight through, swapped.
        lea     dtl_file+DTL_FORWARD_OFF,a0
        lea     ring_a_table,a1
        move.w  d7,d1
        bsr     dtl_copy_swap
        lea     dtl_file+DTL_LATERAL_OFF,a0
        lea     ring_b_table,a1
        move.w  d7,d1
        bsr     dtl_copy_swap
        lea     dtl_file+DTL_DEPTH_OFF,a0
        lea     ring_z_table,a1
        move.w  d7,d1
        bsr     dtl_copy_swap

        bsr     dtl_build_pages
        bsr     render_rebuild_horizons
        bra     .done
.bad
        move.w  #DTL_STATUS_ERROR,dtl_status
.done
        movem.l (sp)+,d0-d7/a0-a6
        rts

; One 256-byte projection page per ring, 00015AD9's own arithmetic:
;
;   slope_i = high32(table2[i] * 0x03000000)          unsigned, 00015B17
;   page[k] = clamp(high32(((k - 128) << 24) * slope_i) + table3[i],
;                   0, 0xFF00) >> 8                   00015B24-00015B46
;
; Both multiplies keep the HIGH half of a 64-bit product. Reading either as a
; shift makes every row saturate, which is the shape of the bug that would
; look like a flat world rather than a wrong one.
dtl_build_pages
        movem.l d0-d7/a0-a4,-(sp)
        lea     dtl_file+DTL_SLOPE_OFF,a0       ; esi = 0x1A6B4
        lea     dtl_file+DTL_BIAS_OFF,a1        ; 0x1AA9C
        lea     ring_page_table,a2              ; edi = [0x19E5C]
        moveq   #0,d7
        move.w  ring_steps,d7
        subq.w  #1,d7
.ring
        move.l  a1,a3
        bsr     dtl_swap_long_a3                ; the ring's bias
        move.l  d0,a4                           ; [0x19CC4], constant per ring
        addq.l  #4,a1

        move.l  a0,a3
        bsr     dtl_swap_long_a3
        addq.l  #4,a0
        move.l  #DTL_PROJ_SCALAR,d1
        MulU64D2                        ; 00015B17: unsigned, keep edx
        move.l  d2,d3                           ; ebp = the ring's slope

        moveq   #0,d4                           ; ebx = 0
        move.w  #255,d5
.row
        move.l  d4,d0
        subi.l  #$80000000,d0                   ; 00015B26: (k - 128) << 24
        MulS64  d3                        ; 00015B2B: signed, keep edx
        move.l  a4,d0
        add.l   d0,d1                           ; 00015B2D: + bias
        bpl     .nonneg                         ; 00015B33 `jns`
        moveq   #0,d1                           ; 00015B35
.nonneg
        cmpi.l  #$0000ff00,d1                   ; 00015B37
        bls     .clamped
        move.l  #$0000ff00,d1                   ; 00015B3F
.clamped
        lsr.l   #8,d1                           ; 00015B44 takes dh
        move.b  d1,(a2)+
        addi.l  #$01000000,d4                   ; 00015B47
        dbra    d5,.row
        dbra    d7,.ring

        movem.l (sp)+,d0-d7/a0-a4
        rts

; Copy d1.w little-endian dwords from (a0) to (a1), swapping each.
dtl_copy_swap
        movem.l d0-d2/a0-a1,-(sp)
        subq.w  #1,d1
        bmi     .done
.one
        move.l  (a0)+,d0
        rol.w   #8,d0
        swap    d0
        rol.w   #8,d0
        move.l  d0,(a1)+
        dbra    d1,.one
.done
        movem.l (sp)+,d0-d2/a0-a1
        rts

; The same swap for one dword. In: a0/a3/a4 = source. Out: d0.
dtl_swap_long
        move.l  (a0),d0
        bra     dtl_swap_d0
dtl_swap_long_a3
        move.l  (a3),d0
        bra     dtl_swap_d0
dtl_swap_long_a4
        move.l  (a4),d0
dtl_swap_d0
        rol.w   #8,d0
        swap    d0
        rol.w   #8,d0
        rts

        data
        even
; 0002622C, 0002624A and 00026266, the three filenames the original passes to
; 00015DD0. Upper case because that is how they are staged.
dtl_name_high
        dc.b    'HIGH.DTL',0
        even
dtl_name_medium
        dc.b    'MEDIUM.DTL',0
        even
dtl_name_low
        dc.b    'LOW.DTL',0
        even

; [00025DAB], the cached detail byte 00026216 compares against, with the
; image's own initial value: $63, 'c', which no settings byte selects, so the
; first application always loads a .DTL - in the original and here. The ring
; tables are storage until then (build/port_tables.s); the program carries no
; generated copy any more.
;
; This port is built for high detail by project decision: build-run.sh stages
; COMANCHE.MNU with '0'. The shipped install selects '1' and then loads
; medium, exactly as 00026211 does; the install's own byte is what has to say
; '0', on the oracle as well as on the target, or the two are not comparable.
dtl_cached
        dc.b    $63
        even

        bss
        even
dtl_status
        ds.w    1
dtl_file
        ds.b    DTL_FILE_BYTES
        even

        end
