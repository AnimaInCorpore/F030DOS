; Route: analysis/functions/falcon-attract.md#resources.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; First-mission resource boundary.
;
; DOS origin: flat 0002A104-0002A1AC, with the shared file reader at
; 00015DD0-00015E6D.
; Purpose: probe the numbered mission files and read mission 0 into a stable
; Falcon buffer before game state starts.
; Inputs/outputs: mission_init takes no arguments; mission_status reports
; loaded/error/parsed and mission_bytes reports the raw byte count.
; Original globals/side effects: DOS builds 0.MIS through 9.MIS names, reads
; the selected file into its arena, then parses brace-delimited records.
; Falcon replacement notes: the file boundary is followed by the recovered
; XOR decode, scalar mission contract, and authored object records feeding the
; live mission factory. DOS attract selects a replay but does not execute that
; factory; event-only type state handlers remain explicitly dormant until their
; DOS call graph is ported.
; Validation: Hatari startup with release/0.MIS must set PARSED and use the
; decoded start tuple; without the file it must stop before entering flight.

        include "inc/comanche.s"
        include "inc/gemdos.s"

        global  mission_init, mission_select, mission_status, mission_bytes, mission_index
        global  mission_kind, mission_start_x, mission_start_y
        global  mission_start_heading, mission_object_count
        global  mission_chaff, mission_flare, weapon_ammo, mission_fuel
        global  mission_loadout
        global  mission_object_total
        global  mission_star_count, mission_target_count
        global  mission_obj_x, mission_obj_y
        global  mission_obj_heading, mission_obj_type
        global  mission_damage, mission_wounded, mission_wounded_max
        global  mission_obj_f1, mission_obj_f2, mission_obj_f3
        global  mission_obj_f7, mission_obj_f8, mission_obj_f9
        global  mission_obj_flag
        global  mission_obj_f10
        global  mission_map_family, mission_sky_number
        global  mission_palette_name
        global  mission_probe_campaign, mission_load_campaign
        global  mission_sprite_names, mission_music_names
; The decoded stream itself, for the mission screen's name fill. 0002A1AD
; reads the same buffer the parser does rather than re-reading the file.
        global  mission_buffer

MISSION_BUFFER_BYTES = 16384
MISSION_READ_CHUNK   = 4096
MISSION_TITLE_BYTES  = 32

; The object table holds 130, so there is no point recording more. 0.MIS
; carries 139 placement lines and 1.MIS 127; anything past the table is
; counted and dropped rather than silently ignored - mission_object_count
; reports what was parsed and mission_object_total what the file held.
MISSION_MAX_OBJECTS  = 130
; 00029292's own bound: the record index may not pass 30.
MISSION_DOS_RECORD_MAX = 30
MISSION_RESOURCE_COUNT = 21
MISSION_FIXED_RESOURCES = 11
MISSION_RESOURCE_NAME_BYTES = 16

        text

; Stage campaign 0's stream and parse its first mission.
;
; The catalog walk that finds which files exist is screen_fill_campaigns now,
; and it runs first; this is the load that follows it. Campaign 0 rather than
; "the first file" because that is what the attract flies: 0002A1BB and
; 0002904D both force the campaign index to 0 while [00019ED4] is set.
; DOS: flat 0002A139-0002A14A for the load, 000290C6 for the parse.
; DOS symbol: inside loc_0002A11F
; Record: analysis/functions/falcon-attract.md#resources
; Port: loads the first catalog entry and parses its first record.
; Preserved: file errors, parse-before-start order, parser buffer ownership.
; Kind: translated.
; Status: ported; mission records and resource slots are active for live
; mission entry; the DOS attract path leaves the object table empty.
mission_init
        clr.w   mission_status
        clr.l   mission_bytes
        clr.w   mission_index
        clr.l   mission_kind
        clr.l   mission_start_x
        clr.l   mission_start_y
        clr.w   mission_start_heading
        clr.w   mission_object_count
        clr.w   mission_object_total
        clr.w   mission_star_count              ; 00029240 [0002824B] = 0
        clr.w   mission_target_count            ; 00029256 [00028260] = 0

        ; Campaign 0, and not merely "the first file". 0002A1BB and 0002904D
        ; both force the campaign index to 0 while [00019ED4] is set, which is
        ; the whole time the attract owns the machine - so the stream the demo
        ; passes fly is the first catalog entry's, whatever the roster says.
        moveq   #'0',d0
        bsr     mission_load_campaign
        tst.l   d0
        bmi     .load_failed

        bsr     mission_parse
        tst.l   d0
        bmi     .parse_failed
        move.w  mission_status,d1
        ori.w   #MISSION_STATUS_PARSED,d1
        move.w  d1,mission_status
        rts

.load_failed
        move.w  #MISSION_STATUS_ERROR,mission_status
        rts

.parse_failed
        move.w  #MISSION_STATUS_ERROR,mission_status
        rts

; Re-select a brace-delimited mission in the already decoded catalog. The DOS
; attract path changes the campaign mission number before loading its resource
; names; reusing the decoded stream preserves that boundary on the Falcon.
; In: d0.w = zero-based mission number. Out: mission_status and the selected
; scalar/object/resource fields are updated.
; DOS: flat 0002A104-0002A1AC, selected mission stream setup.
; DOS symbol: sub_0002A104
; Record: analysis/functions/falcon-attract.md#resources
; Port: selects one authored mission and its resource-family metadata.
; Preserved: selected index, D/C family, sky number, and parse-before-start order.
; Kind: translated.
; Status: ported; full campaign/menu selection is not yet wired.
mission_select
        cmpi.w  #9,d0
        bhi     .select_failed
        move.w  d0,mission_index
        move.w  #MISSION_STATUS_LOADED,mission_status
        bsr     mission_parse
        tst.l   d0
        bmi     .select_failed
        move.w  mission_status,d1
        ori.w   #MISSION_STATUS_PARSED,d1
        move.w  d1,mission_status
        rts
.select_failed
        move.w  #MISSION_STATUS_ERROR,mission_status
        rts

; Ask whether one numbered mission file is installed.
;
; 00015CDC is the probe half of the catalog walk: it uppercases the inline
; name, terminates it with a '$' for DOS and asks, and the carry flag is the
; whole answer - nothing is read and no buffer is touched. 0002A121 calls it
; for each digit in turn and 0002A12D skips the file when it comes back set.
; In: d0.b = the file's digit, '0' to '9'.
; Out: d0.l = 0 when the file is there, -1 when it is not.
; DOS: flat 00015CDC, existence probe, called from 0002A121.
; DOS symbol: sub_00015CDC
; Record: analysis/functions/falcon-attract.md#resources
; Port: GEMDOS Fopen/Fclose on the same patched name.
; Preserved: the name, the digit patch, and probing without reading.
; Kind: replaced.
; Status: ported.
mission_probe_campaign
        movem.l d1-d7/a0-a6,-(sp)
        move.b  d0,mission_name

        move.w  #0,-(sp)                    ; read-only
        pea     mission_name
        move.w  #61,-(sp)                   ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .missing

        move.w  d0,d7
        move.w  d7,-(sp)
        move.w  #62,-(sp)                   ; Fclose
        trap    #1
        addq.l  #4,sp
        moveq   #0,d0
        bra     .out
.missing
        moveq   #-1,d0
.out
        movem.l (sp)+,d1-d7/a0-a6
        rts

; Read one campaign's mission file into the stream buffer and decode it.
;
; There is one arena and it always holds the campaign whose missions are
; current: 0002A139 fills it during the catalog walk, 0002A1D1 refills it when
; the mission screen opens, and 00029063 refills it again before the briefing.
; All three patch the same shape of name and follow the read with the same
; decode at 0002A2F8. mission_buffer is that arena here, which is why loading a
; campaign is also what makes mission_select's record index mean anything.
;
; The failure path has no original to copy. 00015E16, 00015E33 and 00015E67
; all take a DOS error to 000164E3, which does not return - a missing or
; unreadable file ends the program rather than reporting anything. This raises
; MISSION_STATUS_ERROR instead, the port's standing equivalent of that exit,
; because a Falcon build that aborts on a probe would end the catalog walk at
; the first gap in the numbering.
; In: d0.b = the campaign's digit, '0' to '9'.
; Out: d0.l = 0 on success, -1 on a read or decode failure.
; DOS: flat 0002A12F-0002A14A, the patched read and its decode.
; DOS symbol: inside loc_0002A11F
; Record: analysis/functions/falcon-attract.md#resources
; Port: the same name patch, a bounded GEMDOS read, and the same XOR decode.
; Preserved: filename shape, digit patch, byte count, and decode-in-place.
; Kind: translated.
; Status: ported; the DOS error exit is replaced, see above.
mission_load_campaign
        movem.l d1-d7/a0-a6,-(sp)
        move.b  d0,mission_name
        clr.l   mission_bytes

        lea     mission_name,a0
        lea     mission_buffer,a1
        bsr     mission_read_file
        tst.l   d0
        bmi     .failed

        move.l  d0,mission_bytes
        move.w  #MISSION_STATUS_LOADED,mission_status
        bsr     mission_decode
        tst.l   d0
        bmi     .failed

        moveq   #0,d0
        bra     .out
.failed
        clr.l   mission_bytes
        move.w  #MISSION_STATUS_ERROR,mission_status
        moveq   #-1,d0
.out
        movem.l (sp)+,d1-d7/a0-a6
        rts

; DOS origin: flat 0002A2F8-0002A31C.
; The original mission path leaves plain ASCII streams beginning with '{'
; alone. Otherwise it XORs each little-endian dword with 0x11120603, whose
; memory byte order is 03 06 12 11. The Falcon keeps that exact stream rule.
; In: mission_buffer and mission_bytes are initialized by mission_init.
; Out: d0 = 0 on success, -1 for an empty/invalid stream.
; DOS: flat 0002A2F8-0002A31C, mission XOR stream decoder.
; DOS symbol: sub_0002A2F8
; Record: analysis/functions/falcon-attract.md#resources
; Port: applies the little-endian `03 06 12 11` dword transform in place.
; Preserved: brace probe, dword stride, key, and decoded byte stream.
; Kind: translated.
; Status: ported; readable 0.MIS validation is complete.
mission_decode
        movem.l d1-d2/a0,-(sp)
        move.l  mission_bytes,d0
        beq     .invalid
        move.b  mission_buffer,d1
        cmpi.b  #$7b,d1                       ; '{'
        beq     .decoded

        addq.l  #3,d0
        lsr.l   #2,d0
        subq.l  #1,d0
        lea     mission_buffer,a0
        move.l  #$03061211,d1
.xor_loop
        eor.l   d1,(a0)
        addq.l  #4,a0
        dbra    d0,.xor_loop

.decoded
        moveq   #0,d0
        bra     .done
.invalid
        moveq   #-1,d0
.done
        movem.l (sp)+,d1-d2/a0
        rts

; DOS origin: flat 000290C6-00029359, using number helper 0002A2BF-0002A2F7.
; Recover the selected mission's title pair, resource-list boundary, start
; tuple, and count of object lines. The first tuple is stored as Falcon
; 16.16 map coordinates: DOS map units are quarter-tile values, so <<14.
; The third tuple value is the original 8-bit turn phase.
; In: decoded mission_buffer and mission_bytes.
; Out: d0 = 0 when the scalar contract is present, -1 on malformed input.
; DOS: flat 000290C6-00029359, selected mission scalar/object parser.
; DOS symbol: loc_000290C6
; Record: analysis/functions/falcon-attract.md#resources
; Port: parses authored title, start tuple, resource fields, and object lines.
; Preserved: decimal syntax, fixed-point shifts, delimiters, and record order.
; Kind: translated.
; Status: ported for attract spawning; event-only type state dispatch remains
; dormant where its target-selection graph is not yet recovered.
mission_parse
        movem.l d1-d7/a0-a6,-(sp)
        lea     mission_buffer,a0
        move.l  mission_bytes,d0
        move.l  a0,d7
        add.l   d0,d7
        move.w  #-1,mission_map_family
        move.w  #-1,mission_sky_number
        lea     mission_palette_name,a1
        moveq   #MISSION_RESOURCE_NAME_BYTES/4-1,d0
        moveq   #0,d1
.clear_palette_name
        move.l  d1,(a1)+
        dbra    d0,.clear_palette_name
        lea     mission_sprite_names,a1
        move.w  #(10*MISSION_RESOURCE_NAME_BYTES)/4-1,d0
        moveq   #0,d1
.clear_sprite_names
        move.l  d1,(a1)+
        dbra    d0,.clear_sprite_names
        lea     mission_music_names,a1
        moveq   #(3*MISSION_RESOURCE_NAME_BYTES)/4-1,d0
.clear_music_names
        move.l  d1,(a1)+
        dbra    d0,.clear_music_names

        ; Later records are selected by walking three delimiters per prior
        ; record: resource-list open, resource-list close, and the following
        ; record boundary. Their titles are presentation data and are not
        ; needed to recover the flight/resource contract.
        move.w  mission_index,d6
        beq     .find_first_open
        lea     mission_buffer,a0
.skip_previous
        bsr     mission_find_delimiter
        bsr     mission_find_delimiter
        bsr     mission_find_delimiter
        subq.w  #1,d6
        bne     .skip_previous
        ; The next delimiter is the selected record's resource-list open.
        bsr     mission_find_delimiter
        bra     .resource_open

        ; The first brace is the catalog/group title; the second is the
        ; mission title used by the selected mission screen.
.find_first_open
        cmpa.l  d7,a0
        bhs     .invalid
        move.b  (a0)+,d1
        cmpi.b  #$7b,d1
        bne     .find_first_open
        subq.l  #1,a0
        lea     mission_catalog_title,a1
        bsr     mission_copy_brace

.find_second_open
        cmpa.l  d7,a0
        bhs     .invalid
        move.b  (a0)+,d1
        cmpi.b  #$7b,d1
        bne     .find_second_open
        subq.l  #1,a0
        lea     mission_title,a1
        bsr     mission_copy_brace

        ; Skip the description and the resource list. Two '<' delimiters
        ; bound the resource names; the following line starts the scalars.
.find_resource_open
        cmpa.l  d7,a0
        bhs     .invalid
        move.b  (a0)+,d1
        cmpi.b  #$3c,d1                       ; '<'
        bne     .find_resource_open
.resource_open
        bsr     mission_resource_scan
.find_resource_close
        cmpa.l  d7,a0
        bhs     .invalid
        move.b  (a0)+,d1
        cmpi.b  #$3c,d1
        bne     .find_resource_close

        ; 00029186-00029188: the family index is bounded at 5 and anything
        ; above it aborts the parse. 0002919A then selects that family's
        ; palette-variant handler from the six-entry table at 0002A984, whose
        ; only non-trivial entry is index 1's night-vision transform at
        ; 0002A99D - the others all point at the bare `ret` at 0002A99C.
        bsr     mission_read_number           ; mission kind/variant
        cmpi.l  #5,d0
        bhi     .invalid
        move.l  d0,mission_kind
        ; Whole map units, not quarter tiles. The DOS record parser at
        ; 000292E8 does `shl eax,0x16` on the same fields, putting the value's
        ; integer part straight into its 10.22 position format, so the port's
        ; 16.16 needs a shift of 16. The earlier 14 made every mission
        ; coordinate a quarter of what the file says.
        bsr     mission_read_number           ; start X, map units
        lsl.l   #8,d0
        lsl.l   #8,d0
        move.l  d0,mission_start_x
        bsr     mission_read_number           ; start Y, map units
        lsl.l   #8,d0
        lsl.l   #8,d0
        move.l  d0,mission_start_y
        bsr     mission_read_number           ; start heading, 8-bit phase
        bsr     mission_heading_import
        move.w  d0,mission_start_heading

        ; 000291D0-00029209: the first three of the five scalar lines are
        ; read, not skipped. The order is the original's exactly - two
        ; countermeasure counts, then SIX weapon loads, then fuel - and
        ; mission_read_number consumes the terminator after each number, so
        ; the reads cross their own line endings the way 0002A2BF's do.
        bsr     mission_read_number           ; 000291D0 -> [0x19D8D]
        move.w  d0,mission_chaff
        bsr     mission_read_number           ; 000291DA -> [0x19D8E]
        move.w  d0,mission_flare
        lea     mission_loadout,a1
        moveq   #5,d6                         ; 000291E9 ecx = 6
.read_loadout
        bsr     mission_read_number           ; 000291F0 -> [0x19D44 + i*4]
        move.l  d0,(a1)+
        dbra    d6,.read_loadout
        bsr     mission_read_number           ; 00029204 -> [0x19D5C]
        move.l  d0,mission_fuel

        ; 0002920E-00029234. These nine numbers used to be crossed as "two
        ; scalar lines" with three mission_skip_line calls, on an assumption
        ; about how the file is laid out. They are not lines and the
        ; assumption cost a record: the original READS them - 00029213's
        ; `mov ecx,8` loop into [00019E38], each value decremented, then one
        ; more into [00019E40] and [00019E44] - and the third skip was eating
        ; the first placement record with them.
        ;
        ; Measured, not deduced: the original parses NINE placement records
        ; for the attract's first mission, `[0x19D64] = 9`, with types
        ; 0,2,2,2,2,2,2,2,2. The type-0 record is dispatch entry 0 at
        ; 00023462, which installs the fixed slot-31 object - the one
        ; 00007CC5's camera aims at and 00024C0A draws in the external views.
        ; This port saw eight records, all type 2, and so had no slot 31 at
        ; all: its variant-7 camera pointed at an object that did not exist.
        bsr     mission_skip_line             ; 0002920E -> 0002A29A
        lea     mission_damage,a1
        moveq   #7,d6                         ; 00029213 ecx = 8
.read_damage
        bsr     mission_read_number           ; 0002921A
        subq.b  #1,d0                         ; 0002921F dec al
        move.b  d0,(a1)+                      ; 00029221 [ebx + 00019E38]
        dbra    d6,.read_damage
        bsr     mission_read_number           ; 0002922A
        move.l  d0,mission_wounded            ; 0002922F [00019E40]
        move.l  d0,mission_wounded_max        ; 00029234 [00019E44]

        ; 00026B96-00026BAC copies the authored loads into the live counters
        ; that 00007476 reads. DOS makes that copy from a mission-script
        ; handler ('A' at 00026B88) and again at 00006876; neither site's
        ; route from the attract is traced, so the port copies here, where the
        ; authored values are established, and records that as the difference.
        lea     mission_loadout,a1
        lea     weapon_ammo,a2
        moveq   #5,d6
.copy_loadout
        move.l  (a1)+,(a2)+
        dbra    d6,.copy_loadout

        clr.w   mission_object_count
.count_objects
        cmpa.l  d7,a0
        bhs     .success
.skip_layout
        cmpa.l  d7,a0
        bhs     .success
        move.b  (a0),d1
        cmpi.b  #$0a,d1
        beq     .consume_layout
        cmpi.b  #$0d,d1
        beq     .consume_layout
        cmpi.b  #$20,d1
        beq     .consume_layout
        cmpi.b  #$09,d1
        bne     .at_object_line
.consume_layout
        addq.l  #1,a0
        bra     .skip_layout
.at_object_line
        cmpi.b  #$3c,d1                       ; next mission/resource block
        beq     .success

        ; Continuation records in the authored mission stream carry a leading
        ; '*'. The DOS reader consumes that marker before reading f0..f10;
        ; leaving it in place shifts every field by one character and turns
        ; the whole placement stream into zeroes.
        moveq   #0,d5
        cmpi.b  #'*',d1
        bne     .record_start
        moveq   #1,d5
        addq.l  #1,a0
.record_start

        ; One placement record. The DOS parser at 00029240 reads eleven fields
        ; in this order and this is where each goes:
        ;
        ;   f0..f3  bytes at [ebx+0002222A], [00022248], [00022284], [000222A2]
        ;   f4      dword at [ebx*4+000220A4], shifted left 22 - X
        ;   f5      dword at [ebx*4+0002211C], shifted left 22 - Y
        ;   f6..f9  bytes at [0002220C], [000222C0], [000222DE], [000222FC]
        ;   f10     dword at [ebx*4+00022194]
        ;
        ; All eleven fields are retained because the factory at 000068A5 consumes
        ; every one of them. f6 is a heading by its range alone: 0.MIS spans 0
        ; to 128 and 1.MIS steps 0, 32, 64 ... 224, which is a 256-unit turn.
        ; The three resource indices and the four factory parameters are not
        ; optional metadata: dropping them makes every object use a made-up
        ; default bank or state.
        ; Both indices are formed BEFORE the first read. mission_read_number
        ; uses d0, d1 and d2 - d2 is its `moveq #10` multiplier - so an index
        ; parked there does not survive the call, and every array write lands
        ; somewhere arbitrary.
        ; 00029292: `cmp ebx, 0x1e / ja` aborts the whole parse once the
        ; record index would pass 30 - the original prints an error and exits
        ; rather than truncating. No shipped mission reaches it (the largest
        ; is 30 records), and the port rejects the mission instead of ending
        ; the program. Worth recording next to it: the original's per-record
        ; byte arrays are 0x1E apart (0002222A to 00022248), so its own 31st
        ; record would write one byte into the next array. That overrun is not
        ; reproduced.
        move.w  mission_object_count,d3
        cmpi.w  #MISSION_DOS_RECORD_MAX,d3
        bhi     .invalid
        cmpi.w  #MISSION_MAX_OBJECTS,d3
        bhs     .record_full
        move.w  d3,d4
        lsl.w   #2,d4

        bsr     mission_read_number           ; f0, the type
        lea     mission_obj_type,a1
        move.b  d0,0(a1,d3.w)
        bsr     mission_read_number           ; f1
        lea     mission_obj_f1,a1
        move.b  d0,0(a1,d3.w)
        bsr     mission_read_number           ; f2
        lea     mission_obj_f2,a1
        move.b  d0,0(a1,d3.w)
        bsr     mission_read_number           ; f3
        lea     mission_obj_f3,a1
        move.b  d0,0(a1,d3.w)
        bsr     mission_read_number           ; f4, X in map units
        lsl.l   #8,d0
        lsl.l   #8,d0
        lsl.l   #6,d0                         ; << 22: the original's 10.22
        lea     mission_obj_x,a1
        move.l  d0,0(a1,d4.w)
        bsr     mission_read_number           ; f5, Y
        lsl.l   #8,d0
        lsl.l   #8,d0
        lsl.l   #6,d0
        lea     mission_obj_y,a1
        move.l  d0,0(a1,d4.w)
        ; f6 is stored raw. 0002930B writes it to [0002220C] and the factory
        ; copies it to the heading byte at 0002189F, which 00024CA8 adds
        ; straight into the model's aspect index. Only the PLAYER's start
        ; heading needs the import, because only player_heading is kept in
        ; this port's inverted convention.
        bsr     mission_read_number           ; f6, heading
        lea     mission_obj_heading,a1
        move.b  d0,0(a1,d3.w)
        bsr     mission_read_number           ; f7
        lea     mission_obj_f7,a1
        move.b  d0,0(a1,d3.w)
        bsr     mission_read_number           ; f8
        lea     mission_obj_f8,a1
        move.b  d0,0(a1,d3.w)
        bsr     mission_read_number           ; f9
        lea     mission_obj_f9,a1
        move.b  d0,0(a1,d3.w)
        bsr     mission_read_number           ; f10
        lea     mission_obj_f10,a1
        move.l  d0,0(a1,d4.w)
        lea     mission_obj_flag,a1
        move.b  d5,0(a1,d3.w)                 ; [00022266], '*' continuation bit
        ; 0002926C counts the '*' records into [0002824B] - the countdown
        ; object_state_wreckage walks down at 000237DE before it raises the
        ; end cue - and 00029266 keeps a second copy in [0002824D].
        tst.w   d5
        beq     .not_starred
        addq.w  #1,mission_star_count
.not_starred
        ; 000292C0-000292CC: a record whose f1 is 2 or 3 counts towards the
        ; mission's target total in [00028260].
        lea     mission_obj_f1,a1
        move.b  0(a1,d3.w),d1
        cmpi.b  #2,d1
        beq     .is_target
        cmpi.b  #3,d1
        bne     .not_target
.is_target
        addq.w  #1,mission_target_count
.not_target
        addq.w  #1,mission_object_count

.record_full
        addq.w  #1,mission_object_total
        bsr     mission_skip_line
        bra     .count_objects

.success
        moveq   #0,d0
        bra     .done
.invalid
        moveq   #-1,d0
.done
        movem.l (sp)+,d1-d7/a0-a6
        rts

; Find the next '<' delimiter. In/out: a0, bounded by d7. The selected
; mission parser uses the same delimiter convention as the DOS resource-list
; copy loop; a malformed stream falls through to the normal bounds check.
; DOS: helper within 000290C6-00029359, mission line scanning.
; DOS symbol: loc_000290C6
; Record: analysis/functions/falcon-attract.md#resources
; Port: scans the staged stream for the parser's delimiter bytes.
; Preserved: stop conditions and bounded buffer behavior.
; Kind: translated.
; Status: ported; covered by mission parser validation.
mission_find_delimiter
.scan
        cmpa.l  d7,a0
        bhs     .found
        cmpi.b  #$3c,(a0)+
        bne     .scan
.found
        rts

; Read the map/sky family numbers and preserve the ten mission sprite names.
; The DOS list is a sequence of 21 newline-delimited names: eleven fixed
; campaign resources followed by ten inline sprite slots at 0002A34C. The
; object factory indexes those slots through f2/f3; replacing them with a
; hard-coded TANK bank was the last fabricated attract path.
; In: a0 just after the opening '<'. Out: a0 points at the closing '<', with
; mission_map_family, mission_sky_number, and mission_sprite_names set.
; DOS: helper within 000290C6-00029359, mission resource-list scan.
; DOS symbol: loc_000290C6
; Record: analysis/functions/falcon-attract.md#resources
; Port: identifies the authored family/sky fields without rewriting literals.
; Preserved: stream order and field boundaries; no fallback names are created.
; Kind: translated.
; Status: ported; authored sprite slots are consumed by live mission setup.
mission_resource_scan
        movem.l d0-d6/a1-a3,-(sp)
        moveq   #0,d6                           ; resource line number
.next
        cmpa.l  d7,a0
        bhs     .out
        cmpi.b  #$3c,(a0)
        beq     .out
        ; CR/LF is not a resource. Consume it before taking the next line so
        ; the destination slot is aligned with the original 21-entry table.
        move.b  (a0),d0
        cmpi.b  #$0a,d0
        beq     .line_break
        cmpi.b  #$0d,d0
        beq     .line_break

        move.l  a0,a2                           ; line start for identity tests
        moveq   #0,d0
        move.b  (a2),d0
        ori.b   #$20,d0                       ; resource names are ASCII
        cmpi.b  #'d',d0
        bne     .not_sky
        moveq   #0,d1
        move.b  1(a0),d1
        subi.b  #'1',d1
        cmpi.b  #3,d1
        bhi     .not_sky
        move.w  d1,mission_map_family
        bra     .identity_done
.not_sky
        cmpi.b  #'s',d0
        bne     .identity_done
        moveq   #0,d1
        move.b  3(a0),d1                       ; SKY digit in SKY<d>.RLE
        subi.b  #'1',d1
        cmpi.b  #3,d1
        bhi     .identity_done
        addq.b  #1,d1
        move.w  d1,mission_sky_number

.identity_done

        ; The first fixed resource is the mission's active VGA palette.  It is
        ; not optional presentation data: 000064C9 installs p12/np44 before
        ; the colour map is remapped by 0002B949.  Keep the authored filename
        ; so the Falcon can make the same palette decision for every mission.
        ; DOS: 000290C6-00029359, fixed resource slot 0.
        ; Port: preserves the name at the mission boundary; GEMDOS loading is
        ; performed by resources_select_family after D/C decoding.
        cmpi.w  #0,d6
        bne     .not_palette
        lea     mission_palette_name,a1
        move.l  a2,a3
        moveq   #MISSION_RESOURCE_NAME_BYTES-1,d3
.copy_palette_name
        move.b  (a3)+,d2
        cmpi.b  #$0a,d2
        beq     .palette_name_done
        cmpi.b  #$0d,d2
        beq     .palette_name_done
        move.b  d2,(a1)+
        dbra    d3,.copy_palette_name
.palette_name_done
        clr.b   (a1)
.not_palette

        ; Lines 11..20 are the ten sprite slots. Copy the authored filename,
        ; including its case and extension, with the same bounded storage
        ; contract as the DOS inline placeholders.
        ; Lines 6, 8 and 10 are the mission's music: the theme, the win and
        ; the lose song. 0002913C copies them into the inline placeholders
        ; 0x67F3 (00006806, [00019E8C]), 0x28A0C and 0x288D5 that the loader
        ; 00015E6E reads (sound-driver.md section 5.9); keep them the same way.
        cmpi.w  #6,d6
        beq.s   .music_name
        cmpi.w  #8,d6
        beq.s   .music_name
        cmpi.w  #10,d6
        bne.s   .not_music
.music_name
        move.w  d6,d1
        subq.w  #6,d1
        lsl.w   #3,d1                           ; (line - 6) / 2 * 16
        lea     mission_music_names,a1
        adda.w  d1,a1
        bra     .copy_name_bounded
.not_music
        cmpi.w  #MISSION_FIXED_RESOURCES,d6
        blo     .skip_line_copy
        cmpi.w  #MISSION_RESOURCE_COUNT,d6
        bhs     .skip_line_copy
        move.w  d6,d1
        subi.w  #MISSION_FIXED_RESOURCES,d1
        lsl.w   #4,d1
        lea     mission_sprite_names,a1
        adda.w  d1,a1
.copy_name_bounded
        moveq   #MISSION_RESOURCE_NAME_BYTES-1,d3
.copy_name
        cmpa.l  d7,a0
        bhs     .copy_done
        move.b  (a0),d2
        cmpi.b  #$0a,d2
        beq     .copy_done
        cmpi.b  #$0d,d2
        beq     .copy_done
        move.b  d2,(a1)+
        addq.l  #1,a0
        dbra    d3,.copy_name
.copy_done
        clr.b   (a1)
        bra     .line_finished
.skip_line_copy
        ; Fixed entries are only inspected; advance to their terminator.
.line_body
        cmpa.l  d7,a0
        bhs     .out
        move.b  (a0)+,d2
        cmpi.b  #$0a,d2
        beq     .line_finished
        cmpi.b  #$0d,d2
        bne     .line_body
.line_finished
        addq.w  #1,d6
        bra     .next
.line_break
        addq.l  #1,a0
        bra     .next
.out
        movem.l (sp)+,d0-d6/a1-a3
        rts

; Convert a heading from the mission's frame to this port's. In/out: d0.
;
; They are not the same frame. The DOS mover at 00024900 does
; `X += speed * [ebx*8+00032120]` and `Y -= speed * [ebx*8+00032320]`, and
; those tables begin 0.000 and 1.000 respectively, so they are sine and
; cosine and DOS heading 0 faces -Y. This port's terrain fan is built from
; F = (sin h, cos h), so its heading 0 faces +Y. The two differ by a
; reflection of the Y axis, and sin(128-h) = sin(h) with cos(128-h) = -cos(h),
; so 128 - h converts between them.
;
; Positions need no conversion: they are absolute map coordinates and both
; renderers index the same height map the same way. Only directions differ,
; which is exactly the kind of difference that shows up as a helicopter flying
; away from its own objectives.
; DOS: helper within 000290C6-00029359, start-heading conversion.
; DOS symbol: loc_000290C6
; Record: analysis/functions/falcon-attract.md#resources
; Port: converts the authored mission phase into the Falcon heading boundary.
; Preserved: byte range, sign/axis convention, and start-state sequencing.
; Kind: translated.
; Status: ported; replay/mission comparison remains capture pending.
mission_heading_import
        neg.w   d0
        addi.w  #128,d0
        andi.w  #$00ff,d0
        rts

; Copy a bounded '{...}' title. In: a0 points at '{', a1 is a 32-byte
; destination. Out: a0 points just after '}'.
; DOS: helper within 000290C6-00029359, brace-delimited field copy.
; DOS symbol: loc_000290C6
; Record: analysis/functions/falcon-attract.md#resources
; Port: copies an authored mission string into bounded Falcon storage.
; Preserved: brace termination and overflow reporting; no synthetic text.
; Kind: translated.
; Status: ported; parser validation covers this helper.
mission_copy_brace
        addq.l  #1,a0
        moveq   #0,d6
.copy_loop
        cmpa.l  d7,a0
        bhs     .copy_done
        moveq   #0,d1
        move.b  (a0)+,d1
        cmpi.b  #$7d,d1                       ; '}'
        beq     .copy_done
        cmpi.w  #MISSION_TITLE_BYTES-1,d6
        bge     .copy_loop
        move.b  d1,0(a1,d6.w)
        addq.w  #1,d6
        bra     .copy_loop
.copy_done
        clr.b   0(a1,d6.w)
        rts

; Read one unsigned decimal field and stop after its delimiter. This mirrors
; the original helper's decimal scan without accepting a sign or overflowing
; the small mission scalar fields used here.
; DOS: helper 0002A2BF-0002A2F7, decimal scalar reader.
; DOS symbol: sub_0002A2BF
; Record: analysis/functions/falcon-attract.md#resources
; Port: parses the same signed decimal fields from the staged mission stream.
; Preserved: digit loop, sign handling, terminators, and integer width.
; Kind: translated.
; Status: ported; parser validation covers this helper.
mission_read_number
        moveq   #0,d0
.seek_digit
        cmpa.l  d7,a0
        bhs     .number_done
        moveq   #0,d1
        move.b  (a0)+,d1
        cmpi.w  #$30,d1
        blo     .seek_digit
        cmpi.w  #$39,d1
        bhi     .seek_digit
        subi.w  #$30,d1
        move.l  d1,d0
.next_digit
        cmpa.l  d7,a0
        bhs     .number_done
        moveq   #0,d1
        move.b  (a0)+,d1
        cmpi.w  #$30,d1
        blo     .number_done
        cmpi.w  #$39,d1
        bhi     .number_done
        subi.w  #$30,d1
        moveq   #10,d2
        mulu.w  d2,d0
        add.l   d1,d0
        bra     .next_digit
.number_done
        rts

; Consume through the next LF/CR line terminator, bounded by d7.
; DOS: helper within 000290C6-00029359, line terminator advance.
; DOS symbol: loc_000290C6
; Record: analysis/functions/falcon-attract.md#resources
; Port: advances over the original mission line endings in bounded storage.
; Preserved: line order and parser cursor movement.
; Kind: translated.
; Status: ported; parser validation covers this helper.
mission_skip_line
.skip_loop
        cmpa.l  d7,a0
        bhs     .skip_done
        move.b  (a0)+,d0
        cmpi.b  #$0a,d0
        beq     .skip_done
        cmpi.b  #$0d,d0
        bne     .skip_loop
        cmpa.l  d7,a0
        bhs     .skip_done
        cmpi.b  #$0a,(a0)
        bne     .skip_done
        addq.l  #1,a0
.skip_done
        rts

; DOS origin: flat 00015DD0-00015E6D.
; Read one named file into a bounded buffer. The original reader uses
; 0xFA00-byte reads and loops while a full chunk is returned. The Falcon
; version keeps the same short-read convention but requests 0x1000-byte
; transfers: the larger request is not reliable across the current TOS/Hatari
; GEMDOS boundary. It performs one guard read when the buffer fills, so an
; oversized mission cannot silently overwrite BSS.
; In: a0 = NUL-terminated filename, a1 = destination.
; Out: d0 = byte count, -1 on I/O failure, -2 when the file exceeds the buffer.
; DOS: flat 00015DD0-00015E6D, GEMDOS file reader.
; DOS symbol: sub_00015DD0
; Record: analysis/functions/falcon-attract.md#resources
; Port: replaces DOS open/read/close with bounded GEMDOS transfers.
; Preserved: read-until-short-read, byte count, error propagation, and close.
; Kind: replaced.
; Status: ported; file-path validation is available locally.
mission_read_file
        movem.l d1-d7/a0-a6,-(sp)
        move.l  a1,a6

        move.w  #0,-(sp)                    ; read-only
        move.l  a0,-(sp)
        move.w  #61,-(sp)                   ; Fopen
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .open_failed
        move.w  d0,d7

        moveq   #0,d6                       ; total bytes read
        move.l  a6,a5                       ; current destination
.read_chunk
        move.l  #MISSION_READ_CHUNK,d3
        move.l  #MISSION_BUFFER_BYTES,d2
        sub.l   d6,d2
        cmp.l   d2,d3
        bls     .chunk_size_ready
        move.l  d2,d3
.chunk_size_ready
        tst.l   d3
        beq     .buffer_full

        ; Fread takes (handle, count, buf), so buf is pushed first and ends up
        ; furthest from the stack pointer. Pushed the other way round, GEMDOS
        ; reads the file to whatever address the count happens to be - here
        ; 4096, in the middle of low memory - and still returns the byte count,
        ; so the caller sees a successful read into an untouched buffer.
        move.l  a5,-(sp)                    ; buf
        move.l  d3,-(sp)                    ; count
        move.w  d7,-(sp)
        move.w  #63,-(sp)                   ; Fread
        trap    #1
        lea     12(sp),sp
        tst.l   d0
        bmi     .io_failed
        beq     .close_success
        add.l   d0,d6
        adda.l  d0,a5

        ; A partial final chunk is followed by a zero-byte read at EOF. The
        ; bounded loop avoids depending on a caller-saved register surviving
        ; the GEMDOS trap for the short-read comparison.
        bra     .read_chunk

.buffer_full

        ; Exactly-full files need a one-byte probe to distinguish EOF from
        ; truncation. The guard byte is never part of the mission stream.
        lea     mission_overflow,a0
        move.l  a0,-(sp)                    ; buf
        move.l  #1,-(sp)                    ; count
        move.w  d7,-(sp)
        move.w  #63,-(sp)
        trap    #1
        lea     12(sp),sp
        tst.l   d0
        bmi     .io_failed
        bne     .too_large

.close_success
        move.l  d6,d4
        move.w  d7,-(sp)
        move.w  #62,-(sp)                   ; Fclose
        trap    #1
        addq.l  #4,sp
        move.l  d4,d0
        bra     .done

.too_large
        moveq   #-2,d4
        bra     .close_with_result
.io_failed
        moveq   #-1,d4
.close_with_result
        move.w  d7,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
        move.l  d4,d0
        bra     .done

.open_failed
        moveq   #-2,d0                       ; missing file
        bra     .done

.done
        movem.l (sp)+,d1-d7/a0-a6
        rts

        data
        even
mission_name
        dc.b    "0.MIS",0

        bss
        even
mission_status
        ds.w    1
mission_index
        ds.w    1
mission_map_family
        ds.w    1
mission_sky_number
        ds.w    1
mission_palette_name
        ds.b    MISSION_RESOURCE_NAME_BYTES
        even
        even
mission_bytes
        ds.l    1
mission_kind
        ds.l    1
mission_start_x
        ds.l    1
; A long, because every access is one: mission_parse writes it with move.l,
; mission_init clears it with clr.l, and game.s reads it with move.l into
; player_y. Declared as a word it was two bytes short, so the long write ran
; into mission_start_heading and the long read brought it back - player_y's
; fractional half was the start heading, 0 to 255 of a 16.16 unit. Harmless
; only by accident of ordering: mission_parse happens to write the heading
; after the Y it had just been overwritten by.
mission_start_y
        ds.l    1
mission_start_heading
        ds.w    1
        even
; 000291D5/000291DF: the authored countermeasure counts, drawn by
; 000074C0-00007503. 000291F0's six weapon loads and 00029204's fuel follow.
mission_chaff
        ds.w    1
mission_flare
        ds.w    1
        even
mission_loadout
        ds.l    6
mission_fuel
        ds.l    1
; [0x19D2C]: the live counters 00007476 reads, copied from the authored loads.
weapon_ammo
        ds.l    6
; [00019E38], the authored eight-entry damage array, each value already
; decremented as 0002921F does. Its readers are 000190AB's damage yaw and
; 000194A3's damage tail, both in paths this milestone does not carry; the
; values are parsed because the original parses them and because skipping
; them cost a placement record.
mission_damage
        ds.b    8
        even
; [00019E40]/[00019E44], read at 00018F10.
mission_wounded
        ds.l    1
mission_wounded_max
        ds.l    1
mission_object_count
        ds.w    1
mission_object_total
        ds.w    1
; [0002824B]/[0002824D]: how many '*' records the selected mission holds.
; object_state_wreckage counts this down and raises the end cue at zero.
mission_star_count
        ds.w    1
; [00028260]: records whose f1 is 2 or 3, the mission's target total.
mission_target_count
        ds.w    1
        even

; Placements taken from the mission stream, one entry per parsed record.
mission_obj_x
        ds.l    MISSION_MAX_OBJECTS
mission_obj_y
        ds.l    MISSION_MAX_OBJECTS
mission_obj_heading
        ds.b    MISSION_MAX_OBJECTS
mission_obj_type
        ds.b    MISSION_MAX_OBJECTS
mission_obj_f1
        ds.b    MISSION_MAX_OBJECTS
mission_obj_f2
        ds.b    MISSION_MAX_OBJECTS
mission_obj_f3
        ds.b    MISSION_MAX_OBJECTS
mission_obj_f7
        ds.b    MISSION_MAX_OBJECTS
mission_obj_f8
        ds.b    MISSION_MAX_OBJECTS
mission_obj_f9
        ds.b    MISSION_MAX_OBJECTS
mission_obj_flag
        ds.b    MISSION_MAX_OBJECTS
        even
mission_obj_f10
        ds.l    MISSION_MAX_OBJECTS
        even
; The ten names copied from the selected mission's resource list. The Falcon
; keeps them in native storage; only the filename representation differs from
; DOS's inline writable placeholders.
mission_sprite_names
        ds.b    10*MISSION_RESOURCE_NAME_BYTES
        even
; Resource lines 6, 8 and 10: the theme, the win song and the lose song.
mission_music_names
        ds.b    3*MISSION_RESOURCE_NAME_BYTES
        even
mission_catalog_title
        ds.b    MISSION_TITLE_BYTES
mission_title
        ds.b    MISSION_TITLE_BYTES
        even
mission_buffer
        ds.b    MISSION_BUFFER_BYTES
mission_overflow
        ds.b    1

        end
