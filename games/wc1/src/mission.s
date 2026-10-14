; WC1 campaign mission decoder.
;
; The DOS loader in wc1-re/src/cmpgn.c reads six sections from an Origin
; packet archive. This Falcon slice implements the four sections needed to
; enter flight: header, nav points, objectives and the 32 ship records. It
; accepts both raw sections and the Origin LZW format used by the DOS disks.
; Place a legally obtained DOS install in WC1DATA/ beside WC1.TOS. If no
; usable packet is present, a synthetic flight fixture keeps the platform
; testable.

        include "inc/wc1.s"
        include "inc/gemdos.s"

        xdef    mission_init
        xdef    mission_series
        xdef    mission_number
        xdef    mission_status
        xdef    mission_entry_nav
        xdef    mission_home_ship
        xdef    mission_player_ship
        xdef    mission_initial_ships
        xdef    mission_nav_names
        xdef    mission_nav_types
        xdef    mission_nav_x
        xdef    mission_nav_y
        xdef    mission_nav_z
        xdef    mission_nav_radius
        xdef    mission_nav_triggers
        xdef    mission_nav_preload_types
        xdef    mission_nav_ships
        xdef    mission_objective_types
        xdef    mission_objective_indices
        xdef    mission_objective_text
        xdef    mission_ship_types
        xdef    mission_ship_sides
        xdef    mission_ship_leaders
        xdef    mission_ship_mission_types
        xdef    mission_ship_nav_points
        xdef    mission_ship_x
        xdef    mission_ship_y
        xdef    mission_ship_z
        xdef    mission_ship_pitch
        xdef    mission_ship_yaw
        xdef    mission_ship_roll
        xdef    mission_ship_speeds
        xdef    mission_ship_states
        xdef    mission_ship_targets

        text

mission_init
        move.w  #1,mission_series
        clr.w   mission_number
        bsr     mission_clear_runtime
        bsr     mission_load_cache
        tst.w   d0
        bne     .done
        bsr     mission_load_dos
        tst.w   d0
        bne     .done
        bsr     mission_build_fallback
.done
        rts

; Clear the fields which later code may scan. Empty ship and initial slots
; carry the DOS sentinel -1, not zero (Hornet is a valid object type).
mission_clear_runtime
        move.w  #MISSION_STATUS_FALLBACK,mission_status
        move.w  #-1,mission_entry_nav
        move.w  #-1,mission_home_ship
        move.w  #-1,mission_player_ship

        lea     mission_initial_ships,a0
        moveq   #7,d0
.initial
        move.w  #-1,(a0)+
        dbra    d0,.initial

        lea     mission_ship_types,a0
        moveq   #MISSION_SHIP_COUNT-1,d0
.ships
        move.w  #-1,(a0)+
        dbra    d0,.ships

        lea     mission_nav_types,a0
        moveq   #MISSION_NAV_COUNT-1,d0
.nav_types
        clr.b   (a0)+
        dbra    d0,.nav_types
        lea     mission_nav_triggers,a0
        moveq   #MISSION_NAV_COUNT*8-1,d0
.nav_triggers
        move.b  #-1,(a0)+
        dbra    d0,.nav_triggers
        lea     mission_nav_preload_types,a0
        moveq   #MISSION_NAV_COUNT*2-1,d0
.nav_preloads
        move.w  #-1,(a0)+
        dbra    d0,.nav_preloads
        rts

; The generated cache has already decompressed the packet and converted each
; known scalar field to 68030 byte order. It is deliberately validated as a
; fixed versioned layout before any record is trusted. Missing or stale cache
; files fall through to the direct DOS reader below.
mission_load_cache
        movem.l d1-d7/a0-a2,-(sp)
        move.w  #-1,mission_cache_handle

        Fopen   cache_path,#0
        tst.l   d0
        bmi     .done
        move.w  d0,mission_cache_handle
        Fread   mission_cache_handle,#FALCON_CACHE_HEADER_BYTES,mission_cache_header
        cmpi.l  #FALCON_CACHE_HEADER_BYTES,d0
        bne     .close_fail

        lea     mission_cache_header,a0
        cmpi.b  #'W',(a0)+
        bne     .close_fail
        cmpi.b  #'C',(a0)+
        bne     .close_fail
        cmpi.b  #'F',(a0)+
        bne     .close_fail
        cmpi.b  #'1',(a0)+
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #FALCON_CACHE_VERSION,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #FALCON_CACHE_HEADER_BYTES,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #FALCON_CACHE_MISSION_COUNT,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #MISSION_NAV_COUNT,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #MISSION_OBJECTIVE_COUNT,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #MISSION_SHIP_COUNT,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #FALCON_MISSION_HEADER_BYTES,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #FALCON_MISSION_NAV_BYTES,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #FALCON_MISSION_OBJECTIVE_BYTES,d0
        bne     .close_fail
        bsr     read_be_word
        cmpi.w  #FALCON_MISSION_SHIP_BYTES,d0
        bne     .close_fail
        bsr     read_be_long
        cmpi.l  #FALCON_CACHE_HEADER_BYTES,d0
        bne     .close_fail
        move.l  d0,mission_cache_header_offset
        bsr     read_be_long
        cmpi.l  #FALCON_CACHE_HEADER_BYTES+FALCON_CACHE_MISSION_COUNT*FALCON_MISSION_HEADER_BYTES,d0
        bne     .close_fail
        move.l  d0,mission_cache_nav_offset
        bsr     read_be_long
        cmpi.l  #FALCON_CACHE_HEADER_BYTES+FALCON_CACHE_MISSION_COUNT*(FALCON_MISSION_HEADER_BYTES+FALCON_MISSION_NAV_BLOCK_BYTES),d0
        bne     .close_fail
        move.l  d0,mission_cache_objective_offset
        bsr     read_be_long
        cmpi.l  #FALCON_CACHE_HEADER_BYTES+FALCON_CACHE_MISSION_COUNT*(FALCON_MISSION_HEADER_BYTES+FALCON_MISSION_NAV_BLOCK_BYTES+FALCON_MISSION_OBJECTIVE_BLOCK_BYTES),d0
        bne     .close_fail
        move.l  d0,mission_cache_ship_offset
        bsr     read_be_long
        cmpi.l  #FALCON_CACHE_TOTAL_BYTES,d0
        bne     .close_fail
        move.l  d0,mission_cache_size

        moveq   #0,d0
        move.w  mission_series,d0
        lsl.w   #2,d0
        add.w   mission_number,d0
        cmpi.w  #FALCON_CACHE_MISSION_COUNT,d0
        bhs     .close_fail
        move.w  d0,mission_index

        mulu    #FALCON_MISSION_HEADER_BYTES,d0
        add.l   mission_cache_header_offset,d0
        move.l  #FALCON_MISSION_HEADER_BYTES,d1
        bsr     mission_read_cache
        tst.w   d0
        beq     .close_fail
        bsr     mission_decode_header_be
        tst.w   d0
        beq     .close_fail

        moveq   #0,d0
        move.w  mission_index,d0
        mulu    #FALCON_MISSION_NAV_BLOCK_BYTES,d0
        add.l   mission_cache_nav_offset,d0
        move.l  #FALCON_MISSION_NAV_BLOCK_BYTES,d1
        bsr     mission_read_cache
        tst.w   d0
        beq     .close_fail
        bsr     mission_decode_nav_be

        moveq   #0,d0
        move.w  mission_index,d0
        mulu    #FALCON_MISSION_OBJECTIVE_BLOCK_BYTES,d0
        add.l   mission_cache_objective_offset,d0
        move.l  #FALCON_MISSION_OBJECTIVE_BLOCK_BYTES,d1
        bsr     mission_read_cache
        tst.w   d0
        beq     .close_fail
        bsr     mission_decode_objectives_be

        moveq   #0,d0
        move.w  mission_index,d0
        mulu    #FALCON_MISSION_SHIP_BLOCK_BYTES,d0
        add.l   mission_cache_ship_offset,d0
        move.l  #FALCON_MISSION_SHIP_BLOCK_BYTES,d1
        bsr     mission_read_cache
        tst.w   d0
        beq     .close_fail
        bsr     mission_decode_ships_be

        Fclose  mission_cache_handle
        move.w  #-1,mission_cache_handle
        ; The cache is converted from this DOS packet, so retain the existing
        ; data-backed HUD state rather than introduce a game-visible format.
        move.w  #MISSION_STATUS_DOS_LZW,mission_status
        moveq   #1,d0
        bra     .finish
.close_fail
        Fclose  mission_cache_handle
        move.w  #-1,mission_cache_handle
.done
        clr.w   d0
.finish
        movem.l (sp)+,d1-d7/a0-a2
        rts

; Read an exact range from the validated cache. In: d0 = file offset,
; d1 = byte count. Out: d0 = boolean. The cache has no compressed streams.
mission_read_cache
        movem.l d1-d2,-(sp)
        move.l  d1,d2
        Fseek   d0,mission_cache_handle,#0
        tst.l   d0
        bmi     .fail
        Fread   mission_cache_handle,d2,mission_io
        cmp.l   d2,d0
        bne     .fail
        moveq   #1,d0
        bra     .done
.fail
        clr.w   d0
.done
        movem.l (sp)+,d1-d2
        rts

; Try to locate the logical mission archive exactly as the DOS game does:
; INSTALL.DAT maps logical id MISSION_ARCHIVE_LOGICAL (16) to MODULE.000, the
; first campaign archive.  Byte 15 of each 16-byte record is the logicalFile
; field being compared below.  Both raw and Origin-LZW sections are consumed.
; Out: d0 = 1 success, 0 means use the synthetic fixture.
mission_load_dos
        movem.l d1-d7/a0-a2,-(sp)
        move.w  #-1,mission_archive_handle
        move.w  #MISSION_STATUS_FALLBACK,mission_status
        clr.w   mission_used_compression

        Fopen   install_path,#0
        tst.l   d0
        bmi     .done
        move.w  d0,mission_install_handle
        Fread   mission_install_handle,#MISSION_INSTALL_MAX,mission_install
        move.l  d0,mission_install_size
        Fclose  mission_install_handle
        tst.l   d0
        bmi     .done
        tst.l   mission_install_size
        ble     .done

        ; INSTALL.DAT has 16-byte records ending at an empty name.
        lea     mission_install,a0
        move.l  mission_install_size,d7
        lsr.l   #4,d7
        subq.w  #1,d7
        bmi     .done
.find_record
        tst.b   (a0)
        beq     .done
        cmpi.b  #MISSION_ARCHIVE_LOGICAL,15(a0)
        beq     .record_found
        lea     16(a0),a0
        dbra    d7,.find_record
        bra     .done

.record_found
        ; The disk name has no required NUL terminator. Form a TOS path under
        ; WC1DATA and append one ourselves.
        lea     archive_path+8,a1
        moveq   #12,d7
.copy_name
        move.b  (a0)+,(a1)+
        dbra    d7,.copy_name
        clr.b   (a1)

        Fopen   archive_path,#0
        tst.l   d0
        bmi     .done
        move.w  d0,mission_archive_handle

        Fread   mission_archive_handle,#8,mission_packet_header
        cmpi.l  #8,d0
        bne     .close_fail
        lea     mission_packet_header,a0
        bsr     read_le_long
        move.l  d0,mission_packet_size
        bsr     read_le_long
        andi.l  #$00ffffff,d0
        move.l  d0,mission_packet_dir_size
        cmpi.l  #8,d0
        blo     .close_fail
        cmpi.l  #MISSION_PACKET_DIR_MAX,d0
        bhi     .close_fail
        btst    #0,d0
        bne     .close_fail
        btst    #1,d0
        bne     .close_fail
        cmp.l   mission_packet_size,d0
        bhi     .close_fail

        Fseek   #0,mission_archive_handle,#0
        tst.l   d0
        bmi     .close_fail
        Fread   mission_archive_handle,mission_packet_dir_size,mission_packet_dir
        cmp.l   mission_packet_dir_size,d0
        bne     .close_fail

        ; DOS computes missionIndex = mission + series * 4. Its archive has
        ; 64 slots; only a valid slot may drive the fixed record offsets below.
        moveq   #0,d0
        move.w  mission_series,d0
        lsl.w   #2,d0
        add.w   mission_number,d0
        cmpi.w  #64,d0
        bhs     .close_fail
        move.w  d0,mission_index

        mulu    #MISSION_HEADER_BYTES,d0
        move.w  #0,mission_read_section
        move.l  d0,mission_read_offset
        move.l  #MISSION_HEADER_BYTES,mission_read_length
        bsr     mission_read_raw
        tst.w   d0
        beq     .close_fail
        bsr     mission_decode_header
        tst.w   d0
        beq     .close_fail

        moveq   #0,d0
        move.w  mission_index,d0
        mulu    #MISSION_NAV_COUNT*MISSION_NAV_BYTES,d0
        move.w  #1,mission_read_section
        move.l  d0,mission_read_offset
        move.l  #MISSION_NAV_COUNT*MISSION_NAV_BYTES,mission_read_length
        bsr     mission_read_raw
        tst.w   d0
        beq     .close_fail
        bsr     mission_decode_nav

        moveq   #0,d0
        move.w  mission_index,d0
        mulu    #MISSION_OBJECTIVE_COUNT*MISSION_OBJECTIVE_BYTES,d0
        move.w  #2,mission_read_section
        move.l  d0,mission_read_offset
        move.l  #MISSION_OBJECTIVE_COUNT*MISSION_OBJECTIVE_BYTES,mission_read_length
        bsr     mission_read_raw
        tst.w   d0
        beq     .close_fail
        bsr     mission_decode_objectives

        moveq   #0,d0
        move.w  mission_index,d0
        mulu    #MISSION_SHIP_COUNT*MISSION_SHIP_BYTES,d0
        move.w  #3,mission_read_section
        move.l  d0,mission_read_offset
        move.l  #MISSION_SHIP_COUNT*MISSION_SHIP_BYTES,mission_read_length
        bsr     mission_read_raw
        tst.w   d0
        beq     .close_fail
        bsr     mission_decode_ships

        Fclose  mission_archive_handle
        move.w  #-1,mission_archive_handle
        tst.w   mission_used_compression
        beq     .raw_status
        move.w  #MISSION_STATUS_DOS_LZW,mission_status
        bra     .status_ready
.raw_status
        move.w  #MISSION_STATUS_DOS_RAW,mission_status
.status_ready
        moveq   #1,d0
        bra     .finish

.close_fail
        ; A compressed mission packet is valid DOS data but is intentionally
        ; not mistaken for a malformed archive. The fallback remains usable.
        cmpi.w  #MISSION_STATUS_COMPRESSED,mission_status
        beq     .close
        move.w  #MISSION_STATUS_FALLBACK,mission_status
.close
        Fclose  mission_archive_handle
        move.w  #-1,mission_archive_handle
.done
        clr.w   d0
.finish
        movem.l (sp)+,d1-d7/a0-a2
        rts

; Read one exact byte range from an Origin packet section into mission_io.
; The packet directory stores 24-bit little-endian offsets with a compression
; tag in the high byte. Type 0 is copied directly; type 1 is the LSB-first
; Origin LZW used by the supplied DOS release.
mission_read_raw
        movem.l d1-d4/a0,-(sp)
        bsr     mission_select_section
        tst.w   d0
        beq     .fail
        tst.w   mission_section_compression
        beq     .raw
        cmpi.w  #1,mission_section_compression
        beq     .lzw
        move.w  #MISSION_STATUS_COMPRESSED,mission_status
        bra     .fail
.raw
        move.l  mission_section_size,d1
        sub.l   mission_read_offset,d1
        blo     .fail
        cmp.l   mission_read_length,d1
        blo     .fail
        move.l  mission_section_offset,d0
        add.l   mission_read_offset,d0
        Fseek   d0,mission_archive_handle,#0
        tst.l   d0
        bmi     .fail
        Fread   mission_archive_handle,mission_read_length,mission_io
        cmp.l   mission_read_length,d0
        bne     .fail
        moveq   #1,d0
        bra     .done
.lzw
        bsr     mission_read_lzw
        bra     .done
.fail
        clr.w   d0
.done
        movem.l (sp)+,d1-d4/a0
        rts

; Decompress a type-1 Origin packet into a bounded scratch block, then copy
; the requested mission record range. The first four section bytes are the
; little-endian decoded size; the following bytes are an LZW stream.
mission_read_lzw
        movem.l d1-d7/a0-a2,-(sp)
        move.l  mission_section_size,d0
        cmpi.l  #4,d0
        blo     .fail

        move.l  mission_section_offset,d0
        Fseek   d0,mission_archive_handle,#0
        tst.l   d0
        bmi     .fail
        Fread   mission_archive_handle,#4,mission_lzw_header
        cmpi.l  #4,d0
        bne     .fail
        lea     mission_lzw_header,a0
        bsr     read_le_long
        move.l  d0,mission_lzw_output_size
        beq     .fail
        cmpi.l  #MISSION_DECOMPRESS_MAX,d0
        bhi     .fail

        move.l  mission_read_offset,d1
        cmp.l   d0,d1
        bhi     .fail
        move.l  d0,d2
        sub.l   d1,d2
        cmp.l   mission_read_length,d2
        blo     .fail

        move.l  mission_section_size,d1
        subq.l  #4,d1
        beq     .fail
        cmpi.l  #MISSION_COMPRESSED_MAX,d1
        bhi     .fail
        move.l  mission_section_offset,d0
        addq.l  #4,d0
        Fseek   d0,mission_archive_handle,#0
        tst.l   d0
        bmi     .fail
        Fread   mission_archive_handle,d1,mission_compressed
        cmp.l   d1,d0
        bne     .fail

        lea     mission_compressed,a0
        move.l  mission_section_size,d0
        subq.l  #4,d0
        move.l  mission_lzw_output_size,d1
        bsr     mission_lzw_decode
        tst.w   d0
        beq     .fail

        lea     mission_decompressed,a0
        adda.l  mission_read_offset,a0
        lea     mission_io,a1
        moveq   #0,d0
        move.w  mission_read_length,d0
        subq.w  #1,d0
.copy
        move.b  (a0)+,(a1)+
        dbra    d0,.copy
        move.w  #1,mission_used_compression
        moveq   #1,d0
        bra     .done
.fail
        clr.w   d0
.done
        movem.l (sp)+,d1-d7/a0-a2
        rts

; Select the requested section and validate the enclosing range. Out: d0 bool.
mission_select_section
        movem.l d1-d4/a0,-(sp)
        moveq   #0,d0
        move.w  mission_read_section,d0
        move.l  mission_packet_dir_size,d1
        lsr.l   #2,d1
        subq.l  #1,d1
        cmp.l   d1,d0
        bhs     .fail
        move.l  d1,d3

        lsl.l   #2,d0
        lea     mission_packet_dir+4,a0
        adda.l  d0,a0
        bsr     mission_decode_packet_entry
        move.l  d0,mission_section_offset
        move.w  d1,mission_section_compression

        moveq   #0,d2
        move.w  mission_read_section,d2
        addq.w  #1,d2
        cmp.l   d3,d2
        beq     .last
        lea     4(a0),a0
        bsr     mission_decode_packet_entry
        move.l  d0,d2
        bra     .size
.last
        move.l  mission_packet_size,d2
.size
        sub.l   mission_section_offset,d2
        ble     .fail
        move.l  d2,mission_section_size
        moveq   #1,d0
        bra     .done
.fail
        clr.w   d0
.done
        movem.l (sp)+,d1-d4/a0
        rts

; In: a0 = little-endian directory entry. Out: d0 = 24-bit offset, d1 = tag.
mission_decode_packet_entry
        moveq   #0,d0
        move.b  (a0),d0
        moveq   #0,d2
        move.b  1(a0),d2
        lsl.l   #8,d2
        or.l    d2,d0
        moveq   #0,d2
        move.b  2(a0),d2
        lsl.l   #8,d2
        lsl.l   #8,d2
        or.l    d2,d0
        moveq   #0,d1
        move.b  3(a0),d1
        rts

; Header section. Out: d0 = boolean after checking player and entry-nav.
mission_decode_header
        movem.l d1-d7/a0-a1,-(sp)
        lea     mission_io,a0
        bsr     read_le_word
        move.w  d0,mission_entry_nav
        bsr     read_le_word
        move.w  d0,mission_home_ship
        bsr     read_le_word
        move.w  d0,mission_player_ship
        lea     mission_initial_ships,a1
        moveq   #7,d7
.initial
        bsr     read_le_word
        move.w  d0,(a1)+
        dbra    d7,.initial

        moveq   #0,d0
        move.w  mission_entry_nav,d0
        cmpi.w  #MISSION_NAV_COUNT,d0
        bhs     .invalid
        moveq   #0,d0
        move.w  mission_player_ship,d0
        cmpi.w  #MISSION_SHIP_COUNT,d0
        bhs     .invalid
        moveq   #1,d0
        bra     .done
.invalid
        clr.w   d0
.done
        movem.l (sp)+,d1-d7/a0-a1
        rts

; Decode the 16 x 0x4d nav records. Triggers and the two preload object types
; are retained so the Falcon action-sphere layer can follow the same mission
; ownership transition as set_up_action_sphere().
mission_decode_nav
        movem.l d0-d7/a0-a6,-(sp)
        lea     mission_io,a0
        lea     mission_nav_names,a1
        lea     mission_nav_types,a2
        lea     mission_nav_x,a3
        lea     mission_nav_y,a4
        lea     mission_nav_z,a5
        lea     mission_nav_radius,a6
        moveq   #0,d6
.nav
        moveq   #29,d7
.name
        move.b  (a0)+,(a1)+
        dbra    d7,.name
        move.b  (a0)+,(a2)+
        bsr     read_le_long
        move.l  d0,(a3)+
        bsr     read_le_long
        move.l  d0,(a4)+
        bsr     read_le_long
        move.l  d0,(a5)+
        bsr     read_le_word
        move.w  d0,(a6)+
        move.l  a1,-(sp)

        move.l  d6,d5
        lsl.l   #3,d5
        lea     mission_nav_triggers,a1
        adda.l  d5,a1
        moveq   #7,d7
.trigger
        move.b  (a0)+,(a1)+
        dbra    d7,.trigger

        move.l  d6,d5
        lsl.l   #2,d5
        lea     mission_nav_preload_types,a1
        adda.l  d5,a1
        bsr     read_le_word
        move.w  d0,(a1)+
        bsr     read_le_word
        move.w  d0,(a1)+

        move.l  d6,d5
        mulu    #20,d5
        lea     mission_nav_ships,a1
        adda.l  d5,a1
        moveq   #9,d7
.ship
        bsr     read_le_word
        move.w  d0,(a1)+
        dbra    d7,.ship
        move.l  (sp)+,a1
        addq.w  #1,d6
        cmpi.w  #MISSION_NAV_COUNT,d6
        blo     .nav
        movem.l (sp)+,d0-d7/a0-a6
        rts

mission_decode_objectives
        movem.l d0-d7/a0-a3,-(sp)
        lea     mission_io,a0
        lea     mission_objective_types,a1
        lea     mission_objective_indices,a2
        lea     mission_objective_text,a3
        moveq   #MISSION_OBJECTIVE_COUNT-1,d7
.objective
        bsr     read_le_word
        move.w  d0,(a1)+
        bsr     read_le_word
        move.w  d0,(a2)+
        moveq   #59,d6
.text
        move.b  (a0)+,(a3)+
        dbra    d6,.text
        dbra    d7,.objective
        movem.l (sp)+,d0-d7/a0-a3
        rts

; Decode packed 0x2a ship records. The DOS runtime expands several fields
; into 32-bit enums; Falcon keeps disk-width values until AI/ship ports need
; their runtime form.
mission_decode_ships
        movem.l d0-d7/a0-a1,-(sp)
        lea     mission_io,a0
        moveq   #0,d6
.ship
        move.l  d6,d5
        add.l   d5,d5
        lea     mission_ship_types,a1
        bsr     read_le_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_sides,a1
        bsr     read_le_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_leaders,a1
        move.b  (a0)+,0(a1,d6.l)
        addq.w  #1,a0                 ; disk field_05
        lea     mission_ship_mission_types,a1
        bsr     read_le_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_nav_points,a1
        move.b  (a0)+,0(a1,d6.l)

        move.l  d6,d4
        lsl.l   #2,d4
        lea     mission_ship_x,a1
        bsr     read_le_long
        move.l  d0,0(a1,d4.l)
        lea     mission_ship_y,a1
        bsr     read_le_long
        move.l  d0,0(a1,d4.l)
        lea     mission_ship_z,a1
        bsr     read_le_long
        move.l  d0,0(a1,d4.l)

        lea     mission_ship_pitch,a1
        bsr     read_le_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_yaw,a1
        bsr     read_le_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_roll,a1
        bsr     read_le_word
        move.w  d0,0(a1,d5.l)
        addq.w  #1,a0                 ; formation spot
        lea     mission_ship_speeds,a1
        bsr     read_le_word
        move.w  d0,0(a1,d5.l)
        lea     8(a0),a0              ; rating, pilot, field_2c, field_2e
        lea     mission_ship_states,a1
        move.b  (a0)+,0(a1,d6.l)
        addq.w  #2,a0                 ; leader and formation indexes
        lea     mission_ship_targets,a1
        move.b  (a0)+,0(a1,d6.l)

        addq.w  #1,d6
        cmpi.w  #MISSION_SHIP_COUNT,d6
        blo     .ship
        movem.l (sp)+,d0-d7/a0-a1
        rts

; Big-endian counterparts for the generated cache. They retain the same
; structure-of-arrays runtime layout as the DOS reader, so game/object code
; does not depend on whether the cache or original packet supplied a mission.
mission_decode_header_be
        movem.l d1-d7/a0-a1,-(sp)
        lea     mission_io,a0
        bsr     read_be_word
        move.w  d0,mission_entry_nav
        bsr     read_be_word
        move.w  d0,mission_home_ship
        bsr     read_be_word
        move.w  d0,mission_player_ship
        lea     mission_initial_ships,a1
        moveq   #7,d7
.initial
        bsr     read_be_word
        move.w  d0,(a1)+
        dbra    d7,.initial

        moveq   #0,d0
        move.w  mission_entry_nav,d0
        cmpi.w  #MISSION_NAV_COUNT,d0
        bhs     .invalid
        moveq   #0,d0
        move.w  mission_player_ship,d0
        cmpi.w  #MISSION_SHIP_COUNT,d0
        bhs     .invalid
        moveq   #1,d0
        bra     .done
.invalid
        clr.w   d0
.done
        movem.l (sp)+,d1-d7/a0-a1
        rts

; Cache nav records include one explicit byte after type so their 32-bit
; coordinates are naturally aligned in the generated file.
mission_decode_nav_be
        movem.l d0-d7/a0-a6,-(sp)
        lea     mission_io,a0
        lea     mission_nav_names,a1
        lea     mission_nav_types,a2
        lea     mission_nav_x,a3
        lea     mission_nav_y,a4
        lea     mission_nav_z,a5
        lea     mission_nav_radius,a6
        moveq   #0,d6
.nav
        moveq   #29,d7
.name
        move.b  (a0)+,(a1)+
        dbra    d7,.name
        move.b  (a0)+,(a2)+
        addq.w  #1,a0                 ; cache alignment byte
        bsr     read_be_long
        move.l  d0,(a3)+
        bsr     read_be_long
        move.l  d0,(a4)+
        bsr     read_be_long
        move.l  d0,(a5)+
        bsr     read_be_word
        move.w  d0,(a6)+
        move.l  a1,-(sp)

        move.l  d6,d5
        lsl.l   #3,d5
        lea     mission_nav_triggers,a1
        adda.l  d5,a1
        moveq   #7,d7
.trigger
        move.b  (a0)+,(a1)+
        dbra    d7,.trigger

        move.l  d6,d5
        lsl.l   #2,d5
        lea     mission_nav_preload_types,a1
        adda.l  d5,a1
        bsr     read_be_word
        move.w  d0,(a1)+
        bsr     read_be_word
        move.w  d0,(a1)+

        move.l  d6,d5
        mulu    #20,d5
        lea     mission_nav_ships,a1
        adda.l  d5,a1
        moveq   #9,d7
.ship
        bsr     read_be_word
        move.w  d0,(a1)+
        dbra    d7,.ship
        move.l  (sp)+,a1
        addq.w  #1,d6
        cmpi.w  #MISSION_NAV_COUNT,d6
        blo     .nav
        movem.l (sp)+,d0-d7/a0-a6
        rts

mission_decode_objectives_be
        movem.l d0-d7/a0-a3,-(sp)
        lea     mission_io,a0
        lea     mission_objective_types,a1
        lea     mission_objective_indices,a2
        lea     mission_objective_text,a3
        moveq   #MISSION_OBJECTIVE_COUNT-1,d7
.objective
        bsr     read_be_word
        move.w  d0,(a1)+
        bsr     read_be_word
        move.w  d0,(a2)+
        moveq   #59,d6
.text
        move.b  (a0)+,(a3)+
        dbra    d6,.text
        dbra    d7,.objective
        movem.l (sp)+,d0-d7/a0-a3
        rts

; The cache adds padding after navpoint and formation spot. All retained
; scalar fields therefore arrive directly in 68030 byte order and at aligned
; record offsets, avoiding the direct loader's LZW and byte-swap work.
mission_decode_ships_be
        movem.l d0-d7/a0-a1,-(sp)
        lea     mission_io,a0
        moveq   #0,d6
.ship
        move.l  d6,d5
        add.l   d5,d5
        lea     mission_ship_types,a1
        bsr     read_be_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_sides,a1
        bsr     read_be_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_leaders,a1
        move.b  (a0)+,0(a1,d6.l)
        addq.w  #1,a0                 ; DOS field_05
        lea     mission_ship_mission_types,a1
        bsr     read_be_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_nav_points,a1
        move.b  (a0)+,0(a1,d6.l)
        addq.w  #1,a0                 ; cache alignment byte

        move.l  d6,d4
        lsl.l   #2,d4
        lea     mission_ship_x,a1
        bsr     read_be_long
        move.l  d0,0(a1,d4.l)
        lea     mission_ship_y,a1
        bsr     read_be_long
        move.l  d0,0(a1,d4.l)
        lea     mission_ship_z,a1
        bsr     read_be_long
        move.l  d0,0(a1,d4.l)

        lea     mission_ship_pitch,a1
        bsr     read_be_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_yaw,a1
        bsr     read_be_word
        move.w  d0,0(a1,d5.l)
        lea     mission_ship_roll,a1
        bsr     read_be_word
        move.w  d0,0(a1,d5.l)
        addq.w  #1,a0                 ; formation spot
        addq.w  #1,a0                 ; cache alignment byte
        lea     mission_ship_speeds,a1
        bsr     read_be_word
        move.w  d0,0(a1,d5.l)
        lea     8(a0),a0              ; rating, pilot, field_2c, field_2e
        lea     mission_ship_states,a1
        move.b  (a0)+,0(a1,d6.l)
        addq.w  #2,a0                 ; leader and formation indexes
        lea     mission_ship_targets,a1
        move.b  (a0)+,0(a1,d6.l)

        addq.w  #1,d6
        cmpi.w  #MISSION_SHIP_COUNT,d6
        blo     .ship
        movem.l (sp)+,d0-d7/a0-a1
        rts

; A no-data boot still needs a valid scene for Falcon hardware testing. This
; uses only object enum values, never mission dialogue, artwork or data.
mission_build_fallback
        bsr     mission_clear_runtime
        move.w  #MISSION_STATUS_FALLBACK,mission_status
        clr.w   mission_entry_nav
        clr.w   mission_home_ship
        clr.w   mission_player_ship
        move.w  #1,mission_initial_ships
        move.b  #1,mission_nav_types
        move.b  #1,mission_nav_types+1
        move.l  #$00100000,mission_nav_z+4

        move.w  #1,mission_ship_types       ; Rapier player
        move.w  #1,mission_ship_types+2     ; Rapier wingman
        move.w  #9,mission_ship_types+4     ; Salthi
        move.w  #10,mission_ship_types+6    ; Dralthi
        move.w  #0,mission_ship_sides
        move.w  #0,mission_ship_sides+2
        move.w  #1,mission_ship_sides+4
        move.w  #1,mission_ship_sides+6
        move.b  #0,mission_ship_nav_points
        move.b  #0,mission_ship_nav_points+1
        move.b  #1,mission_ship_nav_points+2
        move.b  #1,mission_ship_nav_points+3
        move.l  #$00018000,mission_ship_x+4
        move.l  #$00024000,mission_ship_z+4
        move.l  #-$00020000,mission_ship_x+8
        move.l  #$000b0000,mission_ship_z+8
        move.l  #$0001c000,mission_ship_x+12
        move.l  #$000d0000,mission_ship_z+12
        move.w  #6,mission_ship_speeds
        move.w  #6,mission_ship_speeds+2
        move.w  #8,mission_ship_speeds+4
        move.w  #8,mission_ship_speeds+6
        rts

; Little-endian scalar helpers. They advance A0 so parsers stay byte-layout
; driven rather than relying on host C alignment.
read_le_word
        moveq   #0,d0
        move.b  (a0)+,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        lsl.w   #8,d1
        or.w    d1,d0
        rts

read_le_long
        moveq   #0,d0
        move.b  (a0)+,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        lsl.l   #8,d1
        or.l    d1,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        lsl.l   #8,d1
        lsl.l   #8,d1
        or.l    d1,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        lsl.l   #8,d1
        lsl.l   #8,d1
        lsl.l   #8,d1
        or.l    d1,d0
        rts

; The generated Falcon cache stores all scalar fields in the 68030's native
; byte order. Keep these byte-driven helpers so cache parsing is insensitive
; to section placement and does not rely on assembler data alignment.
read_be_word
        moveq   #0,d0
        move.b  (a0)+,d0
        lsl.w   #8,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        or.w    d1,d0
        rts

read_be_long
        moveq   #0,d0
        move.b  (a0)+,d0
        lsl.l   #8,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        or.l    d1,d0
        lsl.l   #8,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        or.l    d1,d0
        lsl.l   #8,d0
        moveq   #0,d1
        move.b  (a0)+,d1
        or.l    d1,d0
        rts

; Origin packet compression type 1. This is the 9-to-12-bit LSB-first LZW
; stream in wc1-re/src/sdl/resources.c, expressed here without dynamic
; allocation so a stock Falcon can decode the campaign archives in ST-RAM.
; In: a0 = compressed stream, d0 = compressed bytes, d1 = decoded bytes.
; Out: d0 = 1 on an exact decode, 0 on malformed or oversized data.
mission_lzw_decode
        move.l  a0,mission_lzw_input
        move.l  a0,d2
        add.l   d0,d2
        move.l  d2,mission_lzw_input_end
        clr.l   mission_lzw_bit_buffer
        clr.w   mission_lzw_bit_count
        lea     mission_decompressed,a0
        move.l  a0,mission_lzw_output
        move.l  a0,d2
        add.l   d1,d2
        move.l  d2,mission_lzw_output_end

        moveq   #9,d0
        bsr     mission_lzw_read_code
        tst.w   d1
        beq     .fail
        cmpi.w  #ORIGIN_LZW_CLEAR_CODE,d0
        bne     .fail
.reset
        move.w  #9,mission_lzw_code_width
        move.w  #$200,mission_lzw_code_threshold
        move.w  #ORIGIN_LZW_FIRST_CODE,mission_lzw_dictionary_size
        move.w  #ORIGIN_LZW_CLEAR_CODE,mission_lzw_previous
.next_code
        moveq   #0,d0
        move.w  mission_lzw_code_width,d0
        bsr     mission_lzw_read_code
        tst.w   d1
        beq     .fail
        cmpi.w  #ORIGIN_LZW_STOP_CODE,d0
        beq     .stop
        cmpi.w  #ORIGIN_LZW_CLEAR_CODE,d0
        beq     .reset
        cmp.w   mission_lzw_dictionary_size,d0
        bhi     .fail
        move.w  d0,mission_lzw_code
        clr.w   mission_lzw_special_code
        move.w  d0,d2
        cmp.w   mission_lzw_dictionary_size,d2
        bne     .decoded
        move.w  mission_lzw_previous,d2
        move.w  #1,mission_lzw_special_code
.decoded
        cmpi.w  #ORIGIN_LZW_CLEAR_CODE,d2
        beq     .fail
        move.w  d2,d0
        bsr     mission_lzw_expand_code
        tst.w   d1
        beq     .fail

        move.w  mission_lzw_previous,d2
        cmpi.w  #ORIGIN_LZW_CLEAR_CODE,d2
        beq     .no_dictionary
        move.w  mission_lzw_dictionary_size,d3
        cmpi.w  #ORIGIN_LZW_MAX_CODES,d3
        bhs     .fail
        lea     mission_lzw_prefix,a0
        move.w  d3,d4
        add.w   d4,d4
        move.w  d2,0(a0,d4.w)
        lea     mission_lzw_value,a0
        move.b  mission_lzw_first_value,0(a0,d3.w)
        addq.w  #1,mission_lzw_dictionary_size
        tst.w   mission_lzw_special_code
        beq     .width
        moveq   #0,d0
        move.b  mission_lzw_first_value,d0
        bsr     mission_lzw_write_byte
        tst.w   d1
        beq     .fail
.width
        move.w  mission_lzw_dictionary_size,d2
        cmp.w   mission_lzw_code_threshold,d2
        bne     .no_dictionary
        cmpi.w  #12,mission_lzw_code_width
        bhs     .no_dictionary
        addq.w  #1,mission_lzw_code_width
        move.w  mission_lzw_code_threshold,d2
        add.w   d2,d2
        move.w  d2,mission_lzw_code_threshold
.no_dictionary
        move.w  mission_lzw_code,mission_lzw_previous
        bra     .next_code
.stop
        move.l  mission_lzw_output,a0
        cmpa.l  mission_lzw_output_end,a0
        bne     .fail
        moveq   #1,d0
        rts
.fail
        clr.w   d0
        rts

; In: d0.w = code width. Out: d0.w = decoded code, d1 = boolean.
mission_lzw_read_code
        move.w  d0,d4
.need_bits
        move.w  mission_lzw_bit_count,d1
        cmp.w   d4,d1
        bhs     .extract
        move.l  mission_lzw_input,a0
        cmpa.l  mission_lzw_input_end,a0
        bhs     .fail
        moveq   #0,d2
        move.b  (a0)+,d2
        move.l  a0,mission_lzw_input
        moveq   #0,d3
        move.w  mission_lzw_bit_count,d3
        lsl.l   d3,d2
        or.l    d2,mission_lzw_bit_buffer
        addq.w  #8,mission_lzw_bit_count
        bra     .need_bits
.extract
        moveq   #1,d2
        moveq   #0,d3
        move.w  d4,d3
        lsl.l   d3,d2
        subq.l  #1,d2
        move.l  mission_lzw_bit_buffer,d0
        and.l   d2,d0
        move.l  mission_lzw_bit_buffer,d2
        lsr.l   d4,d2
        move.l  d2,mission_lzw_bit_buffer
        sub.w   d4,mission_lzw_bit_count
        moveq   #1,d1
        rts
.fail
        clr.w   d1
        rts

; Expand one LZW code to the decoded output. d0 receives the first byte and
; d1 reports success. The byte stack bounds the dictionary chain at 4096.
mission_lzw_expand_code
        clr.w   mission_lzw_stack_size
        lea     mission_lzw_stack,a0
.chain
        cmpi.w  #ORIGIN_LZW_FIRST_CODE,d0
        blo     .literal
        cmpi.w  #ORIGIN_LZW_MAX_CODES,d0
        bhs     .fail
        move.w  mission_lzw_stack_size,d1
        cmpi.w  #ORIGIN_LZW_MAX_CODES,d1
        bhs     .fail
        lea     mission_lzw_value,a1
        move.b  0(a1,d0.w),d2
        move.b  d2,0(a0,d1.w)
        addq.w  #1,mission_lzw_stack_size
        add.w   d0,d0
        lea     mission_lzw_prefix,a1
        move.w  0(a1,d0.w),d0
        bra     .chain
.literal
        cmpi.w  #$00ff,d0
        bhi     .fail
        move.b  d0,mission_lzw_first_value
        bsr     mission_lzw_write_byte
        tst.w   d1
        beq     .fail
.pop
        tst.w   mission_lzw_stack_size
        beq     .done
        subq.w  #1,mission_lzw_stack_size
        move.w  mission_lzw_stack_size,d1
        moveq   #0,d0
        move.b  0(a0,d1.w),d0
        bsr     mission_lzw_write_byte
        tst.w   d1
        beq     .fail
        bra     .pop
.done
        moveq   #0,d0
        move.b  mission_lzw_first_value,d0
        moveq   #1,d1
        rts
.fail
        clr.w   d1
        rts

; In: d0.b = byte. Out: d1 = boolean. The decoder needs an exact output
; length, so attempting to exceed the packet's declared decoded size fails.
mission_lzw_write_byte
        move.l  mission_lzw_output,a0
        cmpa.l  mission_lzw_output_end,a0
        bhs     .fail
        move.b  d0,(a0)+
        move.l  a0,mission_lzw_output
        moveq   #1,d1
        rts
.fail
        clr.w   d1
        rts

        data
install_path    dc.b    'WC1DATA\INSTALL.DAT',0
archive_path    dc.b    'WC1DATA\',0,0,0,0,0,0,0,0,0,0,0,0,0,0
; Keep every path component within the Falcon/TOS 8.3 naming limit.
cache_path      dc.b    'WC1CACHE\MISSION.BIN',0
                even

        bss
        even
mission_series              ds.w    1
mission_number              ds.w    1
mission_status              ds.w    1
mission_entry_nav           ds.w    1
mission_home_ship           ds.w    1
mission_player_ship         ds.w    1
mission_initial_ships       ds.w    8

mission_nav_names           ds.b    MISSION_NAV_COUNT*30
mission_nav_types           ds.b    MISSION_NAV_COUNT
                even
mission_nav_x               ds.l    MISSION_NAV_COUNT
mission_nav_y               ds.l    MISSION_NAV_COUNT
mission_nav_z               ds.l    MISSION_NAV_COUNT
mission_nav_radius          ds.w    MISSION_NAV_COUNT
mission_nav_triggers        ds.b    MISSION_NAV_COUNT*8
                even
mission_nav_preload_types   ds.w    MISSION_NAV_COUNT*2
mission_nav_ships           ds.w    MISSION_NAV_COUNT*10

mission_objective_types     ds.w    MISSION_OBJECTIVE_COUNT
mission_objective_indices   ds.w    MISSION_OBJECTIVE_COUNT
mission_objective_text      ds.b    MISSION_OBJECTIVE_COUNT*60
                even

mission_ship_types          ds.w    MISSION_SHIP_COUNT
mission_ship_sides          ds.w    MISSION_SHIP_COUNT
mission_ship_leaders        ds.b    MISSION_SHIP_COUNT
mission_ship_mission_types  ds.w    MISSION_SHIP_COUNT
mission_ship_nav_points     ds.b    MISSION_SHIP_COUNT
                even
mission_ship_x              ds.l    MISSION_SHIP_COUNT
mission_ship_y              ds.l    MISSION_SHIP_COUNT
mission_ship_z              ds.l    MISSION_SHIP_COUNT
mission_ship_pitch          ds.w    MISSION_SHIP_COUNT
mission_ship_yaw            ds.w    MISSION_SHIP_COUNT
mission_ship_roll           ds.w    MISSION_SHIP_COUNT
mission_ship_speeds         ds.w    MISSION_SHIP_COUNT
mission_ship_states         ds.b    MISSION_SHIP_COUNT
mission_ship_targets        ds.b    MISSION_SHIP_COUNT
                even

mission_install_handle      ds.w    1
mission_archive_handle      ds.w    1
mission_cache_handle        ds.w    1
mission_install_size        ds.l    1
mission_packet_size         ds.l    1
mission_packet_dir_size     ds.l    1
mission_cache_header_offset ds.l    1
mission_cache_nav_offset    ds.l    1
mission_cache_objective_offset ds.l 1
mission_cache_ship_offset   ds.l    1
mission_cache_size          ds.l    1
mission_index               ds.w    1
mission_read_section        ds.w    1
mission_read_offset         ds.l    1
mission_read_length         ds.l    1
mission_section_offset      ds.l    1
mission_section_size        ds.l    1
mission_section_compression ds.w    1
mission_used_compression    ds.w    1
                even
mission_packet_header       ds.b    8
mission_cache_header        ds.b    FALCON_CACHE_HEADER_BYTES
mission_packet_dir          ds.b    MISSION_PACKET_DIR_MAX
mission_install             ds.b    MISSION_INSTALL_MAX
mission_io                  ds.b    FALCON_MISSION_SHIP_BLOCK_BYTES
                even
mission_lzw_header          ds.b    4
mission_lzw_output_size     ds.l    1
mission_lzw_input           ds.l    1
mission_lzw_input_end       ds.l    1
mission_lzw_output          ds.l    1
mission_lzw_output_end      ds.l    1
mission_lzw_bit_buffer      ds.l    1
mission_lzw_bit_count       ds.w    1
mission_lzw_code_width      ds.w    1
mission_lzw_code_threshold  ds.w    1
mission_lzw_dictionary_size ds.w    1
mission_lzw_previous        ds.w    1
mission_lzw_code            ds.w    1
mission_lzw_special_code    ds.w    1
mission_lzw_stack_size      ds.w    1
mission_lzw_first_value     ds.b    1
                even
mission_lzw_prefix          ds.w    ORIGIN_LZW_MAX_CODES
mission_lzw_value           ds.b    ORIGIN_LZW_MAX_CODES
mission_lzw_stack           ds.b    ORIGIN_LZW_MAX_CODES
                even
mission_compressed          ds.b    MISSION_COMPRESSED_MAX
mission_decompressed        ds.b    MISSION_DECOMPRESS_MAX

        end
