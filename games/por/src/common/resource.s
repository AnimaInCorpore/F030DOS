; PORI image-bank loading.
;
; The bank is produced by tools/convert_data.py from the formats resolved in
; analysis/data-formats.md. Layout constants live in inc/por.s and are checked
; against the converter by tools/check_contracts.py.

        include "inc/por.s"
        include "inc/gemdos.s"

        xdef    resource_load_bank
        xdef    resource_image
        xdef    resource_status
        xdef    resource_write_status
        xdef    bank_buffer

        text

; Read a whole file into the staging buffer.
;   a0 = filename (NUL-terminated)
;   returns d0.l = bytes read, or negative on error
resource_load_bank
        movem.l d1-d2/a0-a2,-(sp)
        move.l  bank_buffer,a2
        Fopen   (a0),#0
        tst.l   d0
        bmi     .open_failed
        move.w  d0,d1                   ; handle
        Fread   d1,#PORI_MAX_BYTES,(a2)
        move.l  d0,-(sp)
        Fclose  d1
        move.l  (sp)+,d0
        bra     .done
.open_failed
        move.w  #STATUS_OPEN_FAILED,resource_status
        moveq   #-1,d0
.done
        movem.l (sp)+,d1-d2/a0-a2
        rts

; Validate the bank header and resolve one image.
;   d0.w = image index
;   returns d0.w = 0 on success (resource_status carries the failure code),
;           a0   = pixel pointer
;           d1.w = width, d2.w = height
resource_image
        movem.l a1-a2,-(sp)
        move.l  bank_buffer,a1
        cmpi.l  #PORI_MAGIC,PORI_OFF_MAGIC(a1)
        bne     .bad_magic
        cmpi.w  #PORI_VERSION,PORI_OFF_VERSION(a1)
        bne     .bad_version
        move.w  PORI_OFF_COUNT(a1),d2
        beq     .no_images
        cmp.w   d2,d0
        bhs     .no_images

        ; directory entry = header + index * PORI_DIR_ENTRY_BYTES
        mulu.w  #PORI_DIR_ENTRY_BYTES,d0
        lea     PORI_HEADER_BYTES(a1),a2
        add.l   d0,a2
        move.w  PORI_DIR_WIDTH(a2),d1
        move.w  PORI_DIR_HEIGHT(a2),d2
        move.l  PORI_DIR_OFFSET(a2),d0
        move.l  a1,a0
        add.l   d0,a0                   ; pixel pointer
        move.w  #STATUS_OK,resource_status
        moveq   #0,d0
        bra     .done
.bad_magic
        move.w  #STATUS_BAD_MAGIC,resource_status
        bra     .fail
.bad_version
        move.w  #STATUS_BAD_VERSION,resource_status
        bra     .fail
.no_images
        move.w  #STATUS_NO_IMAGES,resource_status
.fail
        moveq   #-1,d0
.done
        movem.l (sp)+,a1-a2
        rts

; Publish the status word so a headless Hatari run can assert the resource
; path independently of the captured frame. Mirrors ../F030WC1's DSP wire
; smoke test, which reports through a file for the same reason.
resource_write_status
        movem.l d0-d2/a0-a2,-(sp)
        Fcreate status_name,#0
        tst.l   d0
        bmi     .done
        move.w  d0,d1
        Fwrite  d1,#2,resource_status
        Fclose  d1
.done
        movem.l (sp)+,d0-d2/a0-a2
        rts

        data
        even
status_name     dc.b    'PORSTAT.BIN',0
        even

        bss
        even
bank_buffer     ds.l    1
resource_status ds.w    1

        end
