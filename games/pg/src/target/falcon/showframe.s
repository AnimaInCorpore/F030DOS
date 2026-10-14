; Show one captured DOS frame (indexed pixels + palette) on the Falcon030 Videl.
; Not the game and not a renderer: a display-path demonstration. It sets a
; 640x480 256-colour mode (VGA, or interlaced PAL on RGB/TV), uploads the
; palette, converts the chunky frame to bitplanes, writes PGFRAME.OUT (header
; physbase.l mode.w montype.w, then the 307,200 video bytes) for the host check,
; waits for a key, and restores the previous video mode.
        section text,code
        xdef _main
_main:
        lea     stack_end,sp
        move.w  #89,-(sp)               ; Montype
        trap    #14
        addq.l  #2,sp
        move.w  d0,montype
        cmp.w   #2,d0
        beq     .vga
        cmp.w   #1,d0
        beq     .rgb
        cmp.w   #3,d0
        bne     failed                  ; monochrome: no 640x480x8 mode
.rgb:
        move.w  #$12b,mode              ; 8 planes, 80 columns, PAL, interlace
        bra     .modeset
.vga:
        move.w  #$1b,mode               ; 8 planes, 80 columns, VGA
.modeset:
        move.w  #-1,-(sp)               ; Vsetmode(-1): current mode
        move.w  #88,-(sp)
        trap    #14
        addq.l  #4,sp
        move.w  d0,oldmode
        move.w  #2,-(sp)                ; Physbase
        trap    #14
        addq.l  #2,sp
        move.l  d0,oldphys
        move.w  #3,-(sp)                ; Logbase
        trap    #14
        addq.l  #2,sp
        move.l  d0,oldlog
        lea     fb_raw,a0
        move.l  a0,d0
        add.l   #255,d0
        and.l   #-256,d0
        move.l  d0,fb
        move.w  mode,-(sp)              ; Setscreen(log, phys, 3, mode)
        move.w  #3,-(sp)
        move.l  d0,-(sp)
        move.l  d0,-(sp)
        move.w  #5,-(sp)
        trap    #14
        lea     14(sp),sp
        pea     palette                 ; VsetRGB(0, 256, longs 00RRGGBB)
        move.w  #256,-(sp)
        clr.w   -(sp)
        move.w  #93,-(sp)
        trap    #14
        lea     10(sp),sp
        lea     pixels,a0
        movea.l fb,a1
        move.l  #19200,d0
        bsr     gfx_c2p_groups
        move.w  #2,-(sp)                ; Physbase after the mode switch
        trap    #14
        addq.l  #2,sp
        move.l  d0,physbase
        move.w  #-1,-(sp)
        move.w  #88,-(sp)
        trap    #14
        addq.l  #4,sp
        move.w  d0,curmode
        clr.w   -(sp)                   ; Fcreate
        pea     filename
        move.w  #$3c,-(sp)
        trap    #1
        addq.l  #8,sp
        tst.l   d0
        bmi     .wait
        move.w  d0,handle
        pea     header
        move.l  #8,-(sp)
        move.w  d0,-(sp)
        move.w  #$40,-(sp)
        trap    #1
        lea     12(sp),sp
        move.l  fb,-(sp)
        move.l  #640*480,-(sp)
        move.w  handle,-(sp)
        move.w  #$40,-(sp)
        trap    #1
        lea     12(sp),sp
        move.w  handle,-(sp)
        move.w  #$3e,-(sp)
        trap    #1
        addq.l  #4,sp
.wait:
        move.w  #8,-(sp)                ; Cnecin: wait for a key
        trap    #1
        addq.l  #2,sp
        move.w  oldmode,-(sp)           ; restore the previous video mode
        move.w  #3,-(sp)
        move.l  oldphys,-(sp)
        move.l  oldlog,-(sp)
        move.w  #5,-(sp)
        trap    #14
        lea     14(sp),sp
        clr.w   -(sp)
        move.w  #$4c,-(sp)
        trap    #1
failed:
        move.w  #1,-(sp)
        move.w  #$4c,-(sp)
        trap    #1
        include "c2p.s"
        section data,data
filename: dc.b "PGFRAME.OUT",0
        even
palette: incbin "frame.palette.bin"
pixels: incbin "frame.pixels"
        section bss,bss
        even
handle: ds.w 1
oldmode: ds.w 1
mode: ds.w 1
header:
physbase: ds.l 1
curmode: ds.w 1
montype: ds.w 1
oldphys: ds.l 1
oldlog: ds.l 1
fb: ds.l 1
fb_raw: ds.b 640*480+256
stack: ds.b 4096
stack_end:
