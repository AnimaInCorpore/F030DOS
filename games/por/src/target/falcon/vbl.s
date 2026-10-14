; VBL page publication and frame clock.

        include "inc/falcon.s"

        xdef    vbl_install
        xdef    vbl_remove
        xdef    vbl
        xdef    target_frame_count
        xref    pending_screen

        text

vbl_install
        move.l  VBL_VECTOR.w,saved_vbl
        move.l  #vbl,VBL_VECTOR.w
        rts

vbl_remove
        tst.l   saved_vbl
        beq     .done
        move.l  saved_vbl,VBL_VECTOR.w
        clr.l   saved_vbl
.done
        rts

vbl
        ; The TOS VBL routine is reached by tail chaining and does not promise
        ; to preserve the interrupted foreground registers. Retain them here
        ; so ordinary (IPL 3) foreground code may safely perform GEMDOS
        ; resource work between VBL-paced frames.
        movem.l d0-d7/a0-a6,saved_vbl_registers
        ; The foreground publishes one longword before it flips its logical
        ; pointers. Apply that value here, at the VBL edge, so the three Videl
        ; base bytes cannot be observed half-updated by the scanout.
        tst.l   pending_screen
        beq     .no_flip
        move.b  pending_screen+1,$ffff8201.w
        move.b  pending_screen+2,$ffff8203.w
        move.b  pending_screen+3,$ffff820d.w
        clr.l   pending_screen
.no_flip
        addq.l  #1,target_frame_count
        tst.l   saved_vbl
        beq     .return
        ; Let the original handler finish its RTE normally, but redirect that
        ; exception return through a tiny post-chain trampoline. The VBL
        ; exception frame begins with SR then PC on 68030, so only the saved
        ; PC is replaced; the original address is restored with RTS below.
        move.w  (sp),saved_vbl_sr
        move.l  2(sp),saved_vbl_return
        move.l  #.after_tos_vbl,2(sp)
        move.l  saved_vbl,-(sp)
        rts
.after_tos_vbl
        move.l  saved_vbl_return,-(sp)
        movem.l saved_vbl_registers,d0-d7/a0-a6
        move.w  saved_vbl_sr,sr
        rts
.return
        movem.l saved_vbl_registers,d0-d7/a0-a6
        rte

        bss
        even
saved_vbl      ds.l    1
target_frame_count ds.l 1
saved_vbl_return ds.l  1
saved_vbl_sr   ds.w    1
                even
saved_vbl_registers ds.l 15

        end
