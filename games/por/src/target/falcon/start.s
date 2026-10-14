; Falcon030/TOS startup and VIDEL setup.
;
; Ownership model taken from ../F030WC1/src/start.s, which took it from
; F030Comanche: shrink the TPA, allocate the pages, save the desktop video
; state, move the supervisor stack out of TOS-owned memory, install one VBL
; hook, and restore every touched register before terminating.

        include "inc/falcon.s"
        include "../../common/inc/gemdos.s"

        xdef    _main
        xdef    render_surface
        xdef    target_hidden_page
        xdef    target_flip
        xdef    pending_screen
        xref    main
        xref    vbl_install
        xref    vbl_remove
        xref    bank_buffer

        text

_main
        ; TOS hands a .TOS program the whole TPA. Shrink to our own footprint
        ; first, so Mxalloc has free, Videl-visible ST-RAM to hand back.
        move.l  4(sp),a0
        move.l  #$100,d0
        add.l   12(a0),d0
        add.l   20(a0),d0
        add.l   28(a0),d0
        Mshrink a0,d0
        bsr     target_init
        bsr     main
        bsr     target_deinit
        Pterm0

target_init
        ; Falcon allocation happens in user mode. Mode 0 is the default pool,
        ; which is ST-RAM on a plain Falcon and therefore Videl-visible;
        ; mode 2 is TT-RAM only and fails on machines without it.
        Mxalloc #FRAME_BYTES,#0
        tst.l   d0
        ble     .alloc_failed
        move.l  d0,target_hidden_page
        Mxalloc #FRAME_BYTES,#0
        tst.l   d0
        ble     .alloc_failed_1
        move.l  d0,display_screen
        ; The indexed surface the DOS-side renderer draws into. Presentation
        ; expands it to RGB565 in work_screen at the page boundary.
        Mxalloc #SURFACE_BYTES,#0
        tst.l   d0
        ble     .alloc_failed_2
        move.l  d0,render_surface
        ; Resource bank staging buffer.
        Mxalloc #PORI_MAX_BYTES,#0
        tst.l   d0
        ble     .alloc_failed_3
        move.l  d0,bank_buffer

        Super   0
        move.l  d0,saved_ssp
        ; GEMDOS may clobber A0 while servicing Super(0); the active stack
        ; still holds target_init's BSR return address, so recover it here.
        move.l  (sp),a0
        lea     supervisor_stack_end,sp
        move.l  a0,-(sp)
        move.w  #$2700,sr

        ; Save display base and video state. True colour does not use the
        ; Falcon palette registers — the bank palette is expanded instead.
        move.b  $ffff8201.w,saved_screen+1
        move.b  $ffff8203.w,saved_screen+2
        move.b  $ffff820d.w,saved_screen+3
        move.b  $ffff8260.w,saved_res
        move.b  $ffff820a.w,saved_hz
        move.w  $ffff8210.w,saved_line_width

        ; Save the VIDEL timing/control registers as one contiguous block.
        move.l  $ffff820e.w,d0
        move.l  $ffff8264.w,d1
        movem.l $ffff8282.w,d2-d5
        movem.l $ffff82a2.w,d6-a0
        move.l  $ffff82c0.w,a1
        move.w  $ffff820a.w,a2
        movem.l d0-a2,saved_videl

        clr.l   pending_screen
        bsr     vbl_install
        bsr     set_falcon_video
        move.w  #$2300,sr
        rts

.alloc_failed_3
        Mfree   render_surface
.alloc_failed_2
        Mfree   display_screen
.alloc_failed_1
        Mfree   target_hidden_page
.alloc_failed
        Cconws  allocation_error
        Pterm0

; 320x200 Falcon 16-bit true colour. One RGB565 word per pixel. Timing values
; are the proven 320x200 RGB/TV and VGA families; shift mode $0100 selects
; true colour.
set_falcon_video
        btst    #6,$ffff8006.w
        beq     .vga

        move.l  #$fe00c9,$ffff8282.w
        move.l  #$27002e,$ffff8286.w
        move.l  #$8f00d9,$ffff828a.w
        move.l  #$20d0201,$ffff82a2.w
        move.l  #$17004d,$ffff82a6.w
        move.l  #$1dd0207,$ffff82aa.w
        move.w  #$200,$ffff820a.w
        move.w  #$181,$ffff82c0.w
        clr.w   $ffff8266.w
        move.w  #$100,$ffff8266.w
        clr.w   $ffff82c2.w
        bra     .common

.vga
        move.l  #$170011,$ffff8282.w
        move.l  #$2020e,$ffff8286.w
        move.l  #$d0012,$ffff828a.w
        move.l  #$4eb04d1,$ffff82a2.w
        move.l  #$3f00f5,$ffff82a6.w
        move.l  #$41504e7,$ffff82aa.w
        move.w  #$200,$ffff820a.w
        move.w  #$186,$ffff82c0.w
        clr.w   $ffff8266.w
        move.w  #$100,$ffff8266.w
        move.w  #5,$ffff82c2.w

.common
        move.w  #FRAME_LINE_WORDS,$ffff8210.w
        clr.w   $ffff820e.w
        rts

target_deinit
        move.w  #$2700,sr
        bsr     vbl_remove
        move.b  saved_screen+1,$ffff8201.w
        move.b  saved_screen+2,$ffff8203.w
        move.b  saved_screen+3,$ffff820d.w
        move.b  saved_res,$ffff8260.w
        move.b  saved_hz,$ffff820a.w
        move.w  saved_line_width,$ffff8210.w

        movem.l saved_videl,d0-a2
        move.l  d0,$ffff820e.w
        move.l  d1,$ffff8264.w
        movem.l d2-d5,$ffff8282.w
        movem.l d6-a0,$ffff82a2.w
        move.l  a1,$ffff82c0.w
        move.w  a2,$ffff820a.w

        ; target_init relocated the stack after Super(0). Once Super(saved_ssp)
        ; switches back, an ordinary RTS would pop a stale return address, so
        ; terminate directly here as F030Comanche does.
        move.w  #$2300,sr
        move.l  saved_ssp,a0
        Super   (a0)
        ; Back in user mode before releasing the pages.
        Mfree   bank_buffer
        Mfree   render_surface
        Mfree   target_hidden_page
        Mfree   display_screen
        Pterm0

allocation_error
        dc.b    'POR Falcon: not enough ST-RAM for framebuffers',13,10,0
        even

; Publish the page just drawn. The VBL handler applies pending_screen at the
; blanking edge so the three Videl base bytes are never seen half-updated.
target_flip
        move.l  target_hidden_page,d0
        move.l  display_screen,target_hidden_page
        move.l  d0,display_screen
        move.l  display_screen,pending_screen
        rts

        bss
        even
render_surface     ds.l   1
target_hidden_page ds.l   1
display_screen     ds.l   1
pending_screen     ds.l   1
saved_ssp        ds.l   1
saved_screen     ds.l   1
saved_res        ds.b   1
saved_hz         ds.b   1
saved_line_width ds.w   1
saved_videl      ds.l   11

        even
supervisor_stack
                 ds.b   8192
supervisor_stack_end

        end
