; Route: analysis/functions/falcon-attract.md#attract-route (N/A - TOS/Falcon platform boundary).
; Record: analysis/functions/falcon-attract.md#attract-route
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; Minimal Falcon030 startup and video-mode scaffold for Comanche.
; The game systems will grow around this file as the DOS port is translated.

        include "inc/gemdos.s"
        include "inc/xbios.s"
        include "inc/cpu.s"

        xref    snd_shutdown, music_shutdown
    ifne HWTEST
        xref    hwtest_begin, hwtest_end, hwtest_write
    endc
        global  _main
        global  work_screen, display_screen
        global  vector_base

SCREEN_WIDTH  = 320
SCREEN_HEIGHT = 240
SCREEN_BYTES  = SCREEN_WIDTH*SCREEN_HEIGHT*2*2
SCREEN_ALLOC_BYTES = SCREEN_BYTES+$ff

        xref    orig_exe_load, orig_exe_status

        text

; DOS: N/A - TOS process entry replacing the DOS bootstrap handoff.
; Port: enters the Falcon supervisor/video boundary, then the game loop.
; Preserved: startup, game, teardown ordering; DOS extender setup is omitted.
; Kind: replaced.
; Status: ported; validation is the native build/start path.
_main
        ; TOS initially gives the process its whole remaining TPA. Release
        ; everything after text/data/BSS before asking GEMDOS for ST-RAM.
        move.l  4(sp),a0
        move.l  #256,d0
        add.l   12(a0),d0
        add.l   20(a0),d0
        add.l   28(a0),d0
        Mshrink a0,d0
        ; The original's own tables from the player's COMANCHE.EXE, before
        ; init: nothing has been changed yet if the file is missing, and the
        ; Timer C hook that drives the DOS PRNG (flight_shake_tick) is not yet
        ; counting, so the load's duration does not shift the PRNG's phase.
        ; Record: analysis/functions/falcon-attract.md#original-data-loader
        jsr     orig_exe_load
        tst.w   orig_exe_status
        bne     .no_original
        bsr     init
        tst.w   init_failed
        bne     .init_failed
        bsr     main
        bsr     deinit
        Pterm0
.init_failed
        Pterm0
.no_original
        ; Target artefact: the one message the port prints. The game needs
        ; the player's own copy, so say which file is missing or wrong.
        pea     no_original_text
        move.w  #9,-(sp)                        ; Cconws
        trap    #1
        addq.l  #6,sp
        move.w  #1,-(sp)                        ; Cconin: wait for a key
        trap    #1
        addq.l  #2,sp
        Pterm0

; DOS: N/A - platform replacement; the original bootstrap `seg:off` startup
; has no game-side flat function to translate.
; Port: saves TOS/Falcon video, vectors, palette, and supervisor state.
; Preserved: resources are restored on exit; PC hardware setup is replaced.
; Kind: replaced.
; Status: ported; debugger/capture validation pending.
init
        ; VIDEL can only scan ST-RAM.  Allocate both RGB565 pages explicitly
        ; before entering supervisor mode, since executable BSS may be placed
        ; in TT-RAM on an accelerator-equipped Falcon.
        Mxalloc #SCREEN_ALLOC_BYTES,#0
        tst.l   d0
        ble     .screen_alloc_failed
        add.l   #$ff,d0
        clr.b   d0
        move.l  d0,scanout_base
        move.l  d0,work_screen
        move.l  d0,d1
        add.l   #SCREEN_WIDTH*SCREEN_HEIGHT*2,d1
        move.l  d1,display_screen

        bra     .screen_allocated
.screen_alloc_failed
        move.w  #1,init_failed
        rts
.screen_allocated

        Super   0
        move.l  d0,savssp

        ; Move the supervisor stack into our own BSS before anything else runs.
        ;
        ; Super(0) leaves the supervisor stack where the user stack was, at the
        ; top of the TPA - and on this machine the TPA top is inside TOS's
        ; screen. Measured on a 14 MB Falcon under TOS 4.02: screen base
        ; $DE0B00, RAM top $E00000, and Super(0) handed us a stack at $DF80D2,
        ; some 30 KB inside that buffer. TOS still owns the IKBD interrupt and
        ; draws the mouse cursor through line-A from it, so every cursor update
        ; wrote over our stack. It corrupted a saved return address, the next
        ; RTS left for TOS, and the program vanished with no exception at all -
        ; which is what limited every run to a handful of frames.
        ;
        ; Keep the return address: init was reached with BSR.
        move.l  (sp),a0
        lea     main_stack,sp
        move.l  a0,-(sp)

        move    #$2700,sr

        lea     $ffff9800.w,a0
        lea     old_palette,a1
        move    #256-1,d7
.copy_palette
        move.l  (a0)+,(a1)+
        dbra    d7,.copy_palette
        clr.l   $ffff9800.w

        ; The ST palette, shift mode and line width are separate from the
        ; Falcon palette saved above. A desktop left in ST-compatible mode
        ; reads all three, so restoring only the Falcon side hands back a
        ; machine that looks wrong in exactly the modes this program does not
        ; use itself - which is why the gap was easy to miss.
        movem.l $ffff8240.w,d0-d7
        movem.l d0-d7,old_st_palette
        move.b  $ffff8260.w,old_res
        move.b  $ffff820f.w,old_linewid

        move.b  $ffff8201.w,old_screen+1
        move.b  $ffff8203.w,old_screen+2
        move.b  $ffff820d.w,old_screen+3

        move.l  $ffff820e.w,d0
        move.l  $ffff8264.w,d1
        movem.l $ffff8282.w,d2-d5
        movem.l $ffff82a2.w,d6-a0
        move.l  $ffff82c0.w,a1
        move    $ffff820a.w,a2
        movem.l d0-a2,old_videl

        ; Take the exception vectors this port can actually trip, and the two
        ; interrupt vectors TOS owns that are not the VBL. Saved first so
        ; deinit can hand every one of them back.
        ; An accelerator OS may relocate the vector table. Keep its VBR and
        ; cache policy; install and restore handlers in that actual table.
        movec   vbr,d0
        move.l  d0,vector_base
        move.l  d0,a0
        move.l  $8(a0),old_bus_error
        move.l  $c(a0),old_address_error
        move.l  $10(a0),old_illegal
        move.l  $68(a0),old_hbl
        move.l  $134(a0),old_timer_a

        move.l  #exc_bus,$8(a0)
        move.l  #exc_address,$c(a0)
        move.l  #exc_illegal,$10(a0)
        ScreenCachePush

        jsr     vbl_install
        ; The key array needs make AND break events, which the BIOS console
        ; queue does not carry, so input_init takes the MFP keyboard vector
        ; and saves it for input_deinit. The polled paths in input_poll stay
        ; as the fallback. The original owns its keyboard gate too (00001921).
        bsr     input_init

; 320x240 true colour. RGB/TV and VGA use different timing values on VIDEL.
        btst    #6,$ffff8006.w
        beq     .set_vga_mode

        move.l  #$10800b1,$ffff8282.w
        move.l  #$3b001a,$ffff8286.w
        move.l  #$b100e3,$ffff828a.w
        move.l  #$1f601ec,$ffff82a2.w
        move.l  #$c000c,$ffff82a6.w
        move.l  #$1ec01f0,$ffff82aa.w
        move.w  #$200,$ffff820a.w
        move.w  #$181,$ffff82c0.w
        clr.w   $ffff8266.w
        move.w  #$100,$ffff8266.w
        clr.w   $ffff82c2.w
        bra     .video_ready

.set_vga_mode
        move.l  #$fc00a9,$ffff8282.w
        move.l  #$2502f3,$ffff8286.w
        move.l  #$a800c0,$ffff828a.w
        move.l  #$41a0406,$ffff82a2.w
        move.l  #$460046,$ffff82a6.w
        move.l  #$4060416,$ffff82aa.w
        move.w  #$200,$ffff820a.w
        move.w  #$182,$ffff82c0.w
        clr.w   $ffff8266.w
        move.w  #$100,$ffff8266.w
        move.w  #5,$ffff82c2.w

.video_ready
        move.w  #SCREEN_WIDTH,$ffff8210.w
        clr.w   $ffff820e.w
    ifne HWTEST
        jsr     hwtest_begin                    ; target diagnostic (src/hwtest.s)
    endc
        move    #$2300,sr
        rts

; DOS: N/A - platform replacement; the original bootstrap shutdown has no
; game-side flat function to translate.
; Port: restores TOS vectors, VIDEL state, palettes, and supervisor stack.
; Preserved: the host desktop is returned to its pre-game state.
; Kind: replaced.
; Status: ported; validation is the native teardown path.
deinit
        move    #$2700,sr
    ifne HWTEST
        jsr     hwtest_end
    endc
        jsr     snd_shutdown                    ; 00006B28-00006B2A MODE(0); the sound system is released
        jsr     music_shutdown                  ; 00006B2F-00006B38 stop, device 0
        clr.w   $ffff820e.w
        clr.b   $ffff8265.w

        lea     old_palette,a0
        lea     $ffff9800.w,a1
        move    #256-1,d7
.restore_palette
        move.l  (a0)+,(a1)+
        dbra    d7,.restore_palette

        movem.l old_st_palette,d0-d7
        movem.l d0-d7,$ffff8240.w
        move.b  old_res,$ffff8260.w
        move.b  old_linewid,$ffff820f.w

        move.l  vector_base,a0
        move.l  old_bus_error,$8(a0)
        move.l  old_address_error,$c(a0)
        move.l  old_illegal,$10(a0)
        move.l  old_hbl,$68(a0)
        move.l  old_timer_a,$134(a0)
        ScreenCachePush

        bsr     input_deinit
        jsr     vbl_remove
        Vsync
        move.b  old_screen+1,$ffff8201.w
        move.b  old_screen+2,$ffff8203.w
        move.b  old_screen+3,$ffff820d.w

        movem.l old_videl,d0-a2
        move.l  d0,$ffff820e.w
        move.l  d1,$ffff8264.w
        movem.l d2-d5,$ffff8282.w
        movem.l d6-a0,$ffff82a2.w
        move.l  a1,$ffff82c0.w
        move    a2,$ffff820a.w
        move    #$2300,sr

        move.l  savssp,a0
        Super   (a0)
    ifne HWTEST
        jsr     hwtest_write                    ; HWTEST.TXT, the machine TOS's again
    endc
        ; Terminate from here rather than returning. The supervisor stack was
        ; relocated in init, so the RTS that used to carry us back to _main
        ; would pop from the user stack this Super() call just switched to.
        Pterm0
        rts

; Exception landing pad for the three vectors this port can actually trip.
;
; There was none before, and init above already records what that costs: a
; corrupted return address once made this program "vanish with no exception at
; all", and the absence was itself the hard part of the diagnosis. An
; unhandled bus error on a Falcon either reboots or wanders; either way the
; evidence is gone by the time anyone looks.
;
; The handler records which vector fired and the PC out of the exception frame,
; then floods the visible surface so the failure is unmistakable on hardware
; and in a headless capture alike. SR sits at 0(sp) and PC at 2(sp) in every
; frame format these three produce on the 68030, so one fetch serves all three.
;
; It deliberately does not RTE. Returning from a bus error without having fixed
; anything re-executes the faulting instruction and faults again, which turns a
; single legible crash into a loop. Holding instead leaves the machine in the
; state that failed, which is what a debugger wants to see.
;
; One consequence is worth knowing before using this: holding at IPL 7 masks the
; VBL, so under Hatari the VBL count stops advancing and neither `--run-vbls`
; nor a `b VBL = N` breakpoint will ever fire. tools/grab-frame.sh therefore
; cannot capture a crashed frame - it will hang until its timeout. Headless
; crash detection wants Hatari's `--debug-except`, which traps the exception
; before this handler runs. The red screen is for hardware and for an
; interactive emulator session.
EXC_FILL = $F800                        ; bright red, 5-6-5

; DOS: N/A - Falcon bus-error diagnostic boundary.
; Port: records the exception and holds on a visible diagnostic surface.
; Preserved: failure is explicit; no guessed recovery or game state follows.
; Kind: replaced.
; Status: ported; validation is an intentional fault only.
exc_bus
        moveq   #2,d0
        bra     exc_report
; DOS: N/A - Falcon address-error diagnostic boundary.
; Port: routes the vector to the shared diagnostic landing pad.
; Preserved: failure is explicit; no guessed recovery or game state follows.
; Kind: replaced.
; Status: ported; validation is an intentional fault only.
exc_address
        moveq   #3,d0
        bra     exc_report
; DOS: N/A - Falcon illegal-instruction diagnostic boundary.
; Port: routes the vector to the shared diagnostic landing pad.
; Preserved: failure is explicit; no guessed recovery or game state follows.
; Kind: replaced.
; Status: ported; validation is an intentional fault only.
exc_illegal
        moveq   #4,d0
        bra     exc_report

; DOS: N/A - Falcon exception reporting service.
; Port: captures the vector/PC/register state and paints a diagnostic fill.
; Preserved: an unrecoverable fault remains stopped, never a fake game frame.
; Kind: replaced.
; Status: ported; validation is an intentional fault only.
exc_report
        ; Stop the sound DMA first: it would loop its ring for ever behind the
        ; diagnostic ($FF8901 bit 0 is the playback enable; no XBIOS here).
        clr.b   $ffff8901.w
        movem.l d0-d7/a0-a6,exc_regs+4          ; before anything below clobbers them
        move.w  d0,exc_vector
        move.l  2(sp),exc_pc

        ; Before the surfaces exist there is nothing safe to paint, and
        ; writing through a null pointer would replace this crash with a less
        ; informative one.
        move.l  display_screen,d1
        beq     .hold
        move.l  d1,a0

        ; Colour the flood by vector, so a capture says which fault this was
        ; without a debugger: red bus, green address, blue illegal. A single
        ; red screen only says "something", and the three have entirely
        ; different causes.
        move.w  #EXC_FILL,d1
        cmpi.w  #3,d0
        bne     .not_address
        move.w  #$07E0,d1
.not_address
        cmpi.w  #4,d0
        bne     .have_colour
        move.w  #$001F,d1
.have_colour
        move.w  d1,d3
        swap    d1
        move.w  d3,d1
        move.w  #SCREEN_WIDTH*SCREEN_HEIGHT/2-1,d2
.fill
        move.l  d1,(a0)+
        dbra    d2,.fill

        ; The faulting PC as 32 white pixels on the top row, most significant
        ; first. The address is the whole diagnosis and it is otherwise only
        ; reachable by dumping BSS, which needs a symbol address that moves
        ; with every build.
        ; Row 0 is the faulting PC, rows 2..16 are d0-d7 then a0-a6, each as
        ; 32 white pixels most significant first. A bus error names an address
        ; that is wrong, and the register that carried it is the whole answer;
        ; recovering it any other way means finding a BSS symbol whose address
        ; moves with every build.
        move.l  display_screen,a0
        lea     exc_regs,a1
        move.l  exc_pc,(a1)                     ; slot 0 is the PC
        moveq   #15,d4                          ; 16 rows: PC then 15 registers
.row
        move.l  (a1)+,d1
        moveq   #31,d2
.bit
        moveq   #0,d3
        btst    d2,d1
        beq     .store
        move.w  #$FFFF,d3
.store
        move.w  d3,(a0)+
        dbra    d2,.bit
        adda.w  #SCREEN_WIDTH*2-64,a0            ; next row, past the 32 pixels
        dbra    d4,.row

        ; Point VIDEL at the painted surface directly rather than relying on
        ; the VBL to publish it. Lowering IPL here to let the VBL run would
        ; chain into TOS's handler from a context that has just crashed - the
        ; same line-A path init above documents as writing through whatever it
        ; finds - and that hung the machine outright when tried. The three
        ; register writes are all the publication that is actually needed.
        ScreenCachePush
        move.b  display_screen+1,$ffff8201.w
        move.b  display_screen+2,$ffff8203.w
        move.b  display_screen+3,$ffff820d.w
        ; Spin rather than STOP. STOP halts the CPU, and with IPL 7 masking
        ; every source nothing ever wakes it - under Hatari that also stops
        ; emulated time, so --run-vbls never reaches its limit and a headless
        ; run hangs instead of reporting. Spinning keeps the machine legible to
        ; a debugger and a frame grab while still never returning.
.hold
        bra     .hold

        bss
        even
vector_base
        ds.l    1

; Which vector fired and where. Read these from a Hatari dump after a crash:
; 2 = bus error, 3 = address error, 4 = illegal instruction.
exc_regs
        ds.l    16
exc_vector
        ds.w    1
        even
exc_pc
        ds.l    1

; Supervisor stack, relocated here out of TOS's screen buffer; see init. TOS's
; own interrupt handlers still run on it, so it is sized for their frames as
; well as ours rather than for this program's call depth alone.
MAIN_STACK_BYTES = 8192
        ds.b    MAIN_STACK_BYTES
        even
main_stack

savssp
        ds.l    1
old_screen
        ds.l    1
old_palette
        ds.l    256
old_videl
        ds.l    11
old_vbl
        ds.l    1
old_st_palette
        ds.l    8
old_res
        ds.b    1
old_linewid
        ds.b    1
        even
old_bus_error
        ds.l    1
old_address_error
        ds.l    1
old_illegal
        ds.l    1
old_hbl
        ds.l    1
old_timer_a
        ds.l    1

        even

init_failed
        ds.w    1
        even
scanout_base
        ds.l    1
work_screen
        ds.l    1
display_screen
        ds.l    1

        ds.b    4096

        data
no_original_text
        dc.b    13,10,"Comanche needs COMANCHE.EXE of the 1990 DOS game",13,10
        dc.b    "(61,154 bytes) in this folder, with the game's other files.",13,10
        dc.b    "Press a key.",13,10,0
        even

        end
