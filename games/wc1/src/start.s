; Falcon030/TOS startup and VIDEL setup.
;
; This follows F030Comanche's proven ownership model: save the desktop state,
; move the supervisor stack out of TOS-owned memory, install one VBL hook, and
; restore every touched register before terminating.

        include "inc/wc1.s"
        include "inc/gemdos.s"
        include "inc/xbios.s"

        xdef    _main
        xref    main
        xref    vbl_install
        xref    vbl_remove
        xref    work_screen
        xref    display_screen
        xref    render_screen

        text

_main
        ; TOS initially gives a .TOS program the entire available TPA. Shrink
        ; that block to our text/data/BSS footprint before Mxalloc so the two
        ; Videl pages can be allocated from free, Videl-visible ST-RAM.
        move.l  4(sp),a0
        move.l  #$100,d0
        add.l   12(a0),d0
        add.l   20(a0),d0
        add.l   28(a0),d0
        Mshrink a0,d0
        bsr     falcon_init
        bsr     main
        bsr     falcon_deinit
        Pterm0

falcon_init
        ; Falcon allocation must happen in user mode. F030Arcade uses Mxalloc
        ; for this seam. Mode 0 requests the current/default RAM pool, which
        ; is ST-RAM on a plain Falcon and therefore remains Videl-visible;
        ; mode 2 is TT-RAM-only and fails on machines without TT-RAM.
        Mxalloc #FRAME_BYTES,#0
        tst.l   d0
        ble     .allocation_failed
        move.l  d0,work_screen
        Mxalloc #FRAME_BYTES,#0
        tst.l   d0
        ble     .allocation_failed_first
        move.l  d0,display_screen
        ; The DOS renderer and resource decoder retain this separate indexed
        ; surface. The presentation step expands it to RGB565 in work_screen.
        Mxalloc #CHUNKY_BYTES,#0
        tst.l   d0
        ble     .allocation_failed_second
        move.l  d0,render_screen

        Super   0
        move.l  d0,saved_ssp
        ; GEMDOS is allowed to clobber A0 while servicing Super(0). Once it
        ; has switched us, the active stack still contains falcon_init's BSR
        ; return address, so recover it here as F030Comanche does.
        move.l  (sp),a0
        lea     supervisor_stack_end,sp
        move.l  a0,-(sp)
        move.w  #$2700,sr

        ; Save the display base and video state. True-colour mode does not use
        ; the Falcon palette registers; GAME.PAL is converted to RGB565 by the
        ; presentation routine instead.
        move.b  $ffff8201.w,saved_screen+1
        move.b  $ffff8203.w,saved_screen+2
        move.b  $ffff820d.w,saved_screen+3
        move.b  $ffff8260.w,saved_res
        move.b  $ffff820a.w,saved_hz
        move.w  $ffff8210.w,saved_line_width

        ; Save VIDEL timing/control registers as one contiguous block, as in
        ; the reference port.
        move.l  $ffff820e.w,d0
        move.l  $ffff8264.w,d1
        movem.l $ffff8282.w,d2-d5
        movem.l $ffff82a2.w,d6-a0
        move.l  $ffff82c0.w,a1
        move.w  $ffff820a.w,a2
        movem.l d0-a2,saved_videl

        ; Keep the two 128 KiB RGB565 pages and the separate indexed surface
        ; out of static BSS. TOS places BSS immediately below the TPA top;
        ; Mxalloc keeps the Videl pages visible on a minimally configured
        ; 4 MiB Falcon.
        clr.l   pending_screen
        bsr     vbl_install
        bsr     set_falcon_video
        move.w  #$2300,sr
        rts

.allocation_failed_second
        Mfree   display_screen
.allocation_failed_first
        Mfree   work_screen
.allocation_failed
        Cconws  allocation_error
        Pterm0

; 320x200 Falcon 16-bit true-colour mode. Each scanline is 320 RGB565 words.
; Timing values are the proven 320x200 RGB/TV and VGA 50 Hz families; Falcon
; shift mode $0100 enables true colour.
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

falcon_deinit
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

        ; The stack used by falcon_init was relocated after Super(0). Once
        ; Super(saved_ssp) switches back to TOS's user stack, an ordinary RTS
        ; would pop the stale return address from before that relocation.
        ; Follow F030Comanche: terminate directly after releasing ownership.
        move.w  #$2300,sr
        move.l  saved_ssp,a0
        Super   (a0)
        ; Return to user mode before releasing the pages, matching the
        ; allocator ownership pattern used by F030Arcade.
        Mfree   render_screen
        Mfree   work_screen
        Mfree   display_screen
        Pterm0

allocation_error
        dc.b    'WC1 Falcon: not enough ST-RAM for framebuffers',13,10,0

        bss
        even
saved_ssp       ds.l    1
saved_screen    ds.l    1
saved_res       ds.b    1
saved_hz        ds.b    1
saved_line_width ds.w   1
saved_videl     ds.l    11

        even
supervisor_stack
                ds.b    8192
supervisor_stack_end

        end
