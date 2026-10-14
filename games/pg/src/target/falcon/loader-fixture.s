; N/A - isolated target contract harness, not the playable game.
        include "loader-input.inc"
        section text,code
        xdef _main
_main:
        lea     stack_end,sp
        lea     string_inputs,a5
        lea     string_results,a6
        move.w  #NUM_STRINGS-1,d7
.string:
        lea     4(a5),a2
        lea     string_scratch+1,a0
        moveq   #63,d1
.copy_dest:
        move.b  (a2)+,(a0)+
        dbra    d1,.copy_dest
        lea     string_scratch+67,a1
        moveq   #63,d1
.copy_src:
        move.b  (a2)+,(a1)+
        dbra    d1,.copy_src
        lea     string_scratch+1,a0
        lea     string_scratch+67,a1
        movea.l a1,a4
        cmpi.b  #1,(a5)
        bne     .append
        bsr     sub_00060907
        bra     .string_result
.append:
        bsr     sub_00060926
.string_result:
        cmpa.l  d0,a0
        seq     d0
        andi.l  #1,d0
        move.l  d0,d4
        move.l  a1,d5
        sub.l   a4,d5
        moveq   #63,d1
.string_bytes:
        move.b  (a0)+,(a6)+
        dbra    d1,.string_bytes
        movea.l a6,a0
        move.l  d4,d0
        bsr     pg_put32
        addq.l  #4,a0
        move.l  d5,d0
        bsr     pg_put32
        addq.l  #8,a6
        adda.l  #132,a5
        dbra    d7,.string
        lea     state,a0
        bsr     sub_00037E75
        lea     eax_bytes,a0
        bsr     pg_put32
        clr.w   -(sp)
        pea     filename
        move.w  #$3c,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     failed
        move.w  d0,output_handle
        lea     string_results,a0
        move.l  #NUM_STRINGS*72,d0
        bsr     write_output
        lea     eax_bytes,a0
        moveq   #4,d0
        bsr     write_output
        lea     spans,a3
        move.w  #NUM_SPANS-1,d4
.span:
        lea     state,a0
        adda.l  (a3)+,a0
        move.l  (a3)+,d0
        bsr     write_output
        dbra    d4,.span
        lea     read_trace,a0
        move.l  #NUM_READS*12,d0
        bsr     write_output
        cmpi.w  #NUM_READS,read_count
        bne     failed
        cmpi.w  #2,open_count
        bne     failed
        cmpi.w  #2,close_count
        bne     failed
        move.w  output_handle,-(sp)
        move.w  #$3e,-(sp)
        trap    #1
        addq.l  #4,sp
        clr.w   -(sp)
        move.w  #$4c,-(sp)
        trap    #1
failed:
        move.w  #1,-(sp)
        move.w  #$4c,-(sp)
        trap    #1

; N/A - GEMDOS binary-resource adapter. DOS path spelling maps to the same
; pristine resource basename in the harness directory, with native handles.
pg_open:
        movem.l d1-d7/a0-a6,-(sp)
        movea.l a0,a1
        movea.l a0,a2
.scan:
        move.b  (a2)+,d1
        beq     .name
        cmpi.b  #92,d1
        beq     .separator
        cmpi.b  #47,d1
        bne     .scan
.separator:
        movea.l a2,a1
        bra     .scan
.name:
        clr.w   -(sp)
        move.l  a1,-(sp)
        move.w  #$3d,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     failed
        addq.w  #1,open_count
        movem.l (sp)+,d1-d7/a0-a6
        rts
pg_read:
        movem.l d1-d7/a0-a6,-(sp)
        cmpi.w  #NUM_READS,read_count
        bhs     failed
        move.l  d0,item_size
        move.l  d1,item_count
        mulu.w  d1,d0
        move.l  d0,requested_bytes
        move.l  a0,-(sp)
        move.l  d0,-(sp)
        move.w  d2,-(sp)
        move.w  #$3f,-(sp)
        trap    #1
        lea     12(sp),sp
        cmp.l   requested_bytes,d0
        bne     failed
        moveq   #0,d0
        move.w  read_count,d0
        mulu.w  #12,d0
        lea     read_trace,a0
        adda.l  d0,a0
        move.l  item_size,d0
        bsr     pg_put32
        addq.l  #4,a0
        move.l  item_count,d0
        bsr     pg_put32
        addq.l  #4,a0
        bsr     pg_put32
        addq.w  #1,read_count
        movem.l (sp)+,d1-d7/a0-a6
        rts
pg_close:
        movem.l d1-d7/a0-a6,-(sp)
        move.w  d0,-(sp)
        move.w  #$3e,-(sp)
        trap    #1
        addq.l  #4,sp
        tst.l   d0
        bmi     failed
        addq.w  #1,close_count
        movem.l (sp)+,d1-d7/a0-a6
        rts
write_output:
        movem.l d1-d7/a0-a6,-(sp)
        move.l  d0,requested_bytes
        move.l  a0,-(sp)
        move.l  d0,-(sp)
        move.w  output_handle,-(sp)
        move.w  #$40,-(sp)
        trap    #1
        lea     12(sp),sp
        cmp.l   requested_bytes,d0
        bne     failed
        movem.l (sp)+,d1-d7/a0-a6
        rts
        include "geometry.s"
        include "strings.s"
        include "loader.s"

        section data,data
filename: dc.b "PGLOAD.OUT",0
        even
spans: incbin "loader-spans.bin"
string_inputs: incbin "loader-strings.bin"
state: incbin "loader-input.bin"
        section bss,bss
        even
output_handle: ds.w 1
open_count: ds.w 1
close_count: ds.w 1
read_count: ds.w 1
item_size: ds.l 1
item_count: ds.l 1
requested_bytes: ds.l 1
eax_bytes: ds.b 4
read_trace: ds.b NUM_READS*12
string_results: ds.b NUM_STRINGS*72
string_scratch: ds.b 132
stack: ds.b 8192
stack_end:
