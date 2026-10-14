; N/A - target contract harness for the x86-translated static-frame compositor sub_00014BF6
; (tools/x86x). Not game flow. The harness places the captured DOS state at its DOS virtual
; addresses: the arena at $1E0000 (so pointers stored in DOS memory are valid native
; addresses), shape images and the destination bitmap where DOS held them. It calls the
; generated compositor and writes the arena windows, the bitmap region and the argument log of
; the present boundary (sub_000481AB, a recorded stub) after the call. Expected values are DOS.
;
; Requires a machine with RAM at $1E0000..$400000 and $600000..$A00000 free: Hatari 14 MB.
; Input file COMPIN.BIN (big-endian longs), loaded at INPUT_BASE:
;   ncases, then per case: caseBytes, nwindows { offset len bytes(even) },
;   nshapes { shapePtr headLen spriteOff spriteLen head(even) sprite(even) },
;   pixelsPtr stride regionStart width height, region rows (even).
        include "compose-input.inc"
ARENA           equ $1E0000
ARENA_END       equ $400000
INPUT_BASE      equ $600000
OUTPUT_BASE     equ $900000
        section text,code
        xdef _main
_main:
        lea     stack_end,sp
        lea     program_end,a0
        cmpa.l  #ARENA,a0
        bcc     .failed                 ; the program must sit below the arena
        bsr     load_input
        movea.l #INPUT_BASE,a5
        movea.l #OUTPUT_BASE,a6
        move.l  (a5)+,d7
        subq.l  #1,d7
        move.l  d7,remaining
.case:
        move.l  (a5)+,d0                ; caseBytes
        lea     (a5,d0.l),a0
        move.l  a0,next_case
        bsr     clear_arena
        move.l  (a5)+,d5                ; windows
        move.l  d5,nwin
        lea     wins,a4
        subq.l  #1,d5
.win:
        move.l  (a5)+,d0
        move.l  (a5)+,d1
        move.l  d0,(a4)+
        move.l  d1,(a4)+
        movea.l #ARENA,a1
        adda.l  d0,a1
        bsr     copy_in
        dbra    d5,.win
        move.l  (a5)+,d5                ; shapes
        subq.l  #1,d5
.shape:
        movea.l (a5)+,a3                ; shape pointer
        move.l  (a5)+,d4                ; headLen
        move.l  (a5)+,d2                ; spriteOff
        move.l  (a5)+,d3                ; spriteLen
        movea.l a3,a1
        move.l  d4,d1
        bsr     copy_in
        lea     (a3,d2.l),a1
        move.l  d3,d1
        bsr     copy_in
        dbra    d5,.shape
        movea.l (a5)+,a3                ; pixels
        move.l  (a5)+,reg_stride
        move.l  (a5)+,d0                ; regionStart
        lea     (a3,d0.l),a3
        move.l  a3,reg_ptr
        move.l  (a5)+,reg_w
        move.l  (a5)+,reg_h
        movea.l a3,a1
        bsr     region_in
        clr.l   present_count
        clr.l   present_log
        clr.l   present_log+4
        move.l  a5,save_a5
        move.l  a6,save_a6
        movea.l #ARENA,a0
        bsr     sub_00014BF6
        movea.l save_a6,a6
        movea.l save_a5,a5
        ; outputs: windows after, bitmap region after, present log, present count
        lea     wins,a4
        move.l  nwin,d5
        subq.l  #1,d5
.wout:
        move.l  (a4)+,d0
        move.l  (a4)+,d1
        lea     ARENA,a1
        adda.l  d0,a1
        bsr     copy_out
        dbra    d5,.wout
        movea.l reg_ptr,a1
        bsr     region_out
        lea     present_log,a1
        moveq   #7,d0
.plog:
        move.b  (a1)+,(a6)+
        dbra    d0,.plog
        move.l  present_count,d0
        bsr     write_u32_le
        movea.l next_case,a5
        subq.l  #1,remaining
        bpl     .case
        bsr     write_output
        clr.w   -(sp)
        move.w  #$4c,-(sp)
        trap    #1
.failed:
        move.w  #1,-(sp)
        move.w  #$4c,-(sp)
        trap    #1

; present boundary stub: logs AL of every call (the DOS function is not translated).
boundary_sub_000481AB:
        move.l  present_count,d7
        cmpi.l  #8,d7
        bcc     .full
        lea     present_log,a1
        move.b  d0,(a1,d7.l)
.full:
        addq.l  #1,d7
        move.l  d7,present_count
        rts

; copy_in: a1 = destination, d1 = length, a5 = source (advanced past the even-padded bytes)
copy_in:
        tst.l   d1
        beq     .pad
        move.l  d1,d0
.l:
        move.b  (a5)+,(a1)+
        subq.l  #1,d0
        bne     .l
.pad:
        btst    #0,d1
        beq     .done
        addq.l  #1,a5
.done:
        rts
; copy_out: a1 = source, d1 = length, a6 = output
copy_out:
        tst.l   d1
        beq     .done
        move.l  d1,d0
.l:
        move.b  (a1)+,(a6)+
        subq.l  #1,d0
        bne     .l
.done:
        rts
; region_in / region_out: rows of reg_w bytes, reg_h rows, reg_stride apart, a1 = first byte
region_in:
        move.l  reg_h,d5
        subq.l  #1,d5
.row:
        move.l  reg_w,d0
        subq.l  #1,d0
.px:
        move.b  (a5)+,(a1)+
        dbra    d0,.px
        adda.l  reg_stride,a1
        suba.l  reg_w,a1
        dbra    d5,.row
        move.l  reg_w,d0
        mulu.w  reg_h+2,d0
        btst    #0,d0
        beq     .done
        addq.l  #1,a5
.done:
        rts
region_out:
        move.l  reg_h,d5
        subq.l  #1,d5
.row:
        move.l  reg_w,d0
        subq.l  #1,d0
.px:
        move.b  (a1)+,(a6)+
        dbra    d0,.px
        adda.l  reg_stride,a1
        suba.l  reg_w,a1
        dbra    d5,.row
        rts
clear_arena:
        movea.l #ARENA,a0
        move.l  #(ARENA_END-ARENA)/4-1,d0
        moveq   #0,d1
.l:
        move.l  d1,(a0)+
        subq.l  #1,d0
        bpl     .l
        rts
; N/A - harness file and byte-order adapters
load_input:
        clr.w   -(sp)
        pea     in_name
        move.w  #$3d,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .fail
        move.w  d0,handle
        pea     INPUT_BASE
        move.l  #$300000,-(sp)
        move.w  handle,-(sp)
        move.w  #$3f,-(sp)
        trap    #1
        lea     12(sp),sp
        tst.l   d0
        ble     .fail
        move.w  handle,-(sp)
        move.w  #$3e,-(sp)
        trap    #1
        addq.l  #4,sp
        rts
.fail:
        move.w  #2,-(sp)
        move.w  #$4c,-(sp)
        trap    #1
write_output:
        clr.w   -(sp)
        pea     out_name
        move.w  #$3c,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .fail
        move.w  d0,handle
        move.l  a6,d0
        sub.l   #OUTPUT_BASE,d0
        move.l  d0,result_size
        pea     OUTPUT_BASE
        move.l  d0,-(sp)
        move.w  handle,-(sp)
        move.w  #$40,-(sp)
        trap    #1
        lea     12(sp),sp
        cmp.l   result_size,d0
        bne     .fail
        move.w  handle,-(sp)
        move.w  #$3e,-(sp)
        trap    #1
        addq.l  #4,sp
        rts
.fail:
        move.w  #3,-(sp)
        move.w  #$4c,-(sp)
        trap    #1
write_u32_le:
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        lsr.l   #8,d0
        move.b  d0,(a6)+
        rts
        include "compose.s"

        section data,data
in_name:  dc.b "COMPIN.BIN",0
out_name: dc.b "COMPOUT.BIN",0
        even
        section bss,bss
        even
handle:        ds.w 1
remaining:     ds.l 1
next_case:     ds.l 1
nwin:          ds.l 1
save_a5:       ds.l 1
save_a6:       ds.l 1
result_size:   ds.l 1
reg_ptr:       ds.l 1
reg_stride:    ds.l 1
reg_w:         ds.l 1
reg_h:         ds.l 1
present_count: ds.l 1
present_log:   ds.b 8
wins:          ds.l 32
stack:         ds.b 8192
stack_end:
program_end:   ds.b 2
