; VBL page publication and frame clock.

        include "inc/wc1.s"

        xdef    vbl_install
        xdef    vbl_remove
        xdef    vbl
        xdef    frame_count
        xref    pending_screen

        text

; Target artefact: vbl_install; record:
; analysis/functions/FalconVblPresentation.md. N/A - platform replacement:
; Falcon Videl publication replaces DOS VGA presentation ownership.
vbl_install
        ; A Falcon/TOS session may relocate the exception vectors through VBR.
        ; Writing physical $70 leaves the live VBL chain untouched and silently
        ; presents TOS's desktop page instead of the completed Falcon page.
        movec   vbr,d0
        move.l  d0,vbl_vector_base
        move.l  d0,a0
        move.l  VBL_VECTOR(a0),saved_vbl
        move.l  #vbl,VBL_VECTOR(a0)
        rts

; Target artefact: vbl_remove; record:
; analysis/functions/FalconVblPresentation.md. N/A - platform replacement:
; restores the Falcon/TOS interrupt ownership boundary on exit.
vbl_remove
        tst.l   saved_vbl
        beq     .done
        move.l  vbl_vector_base,a0
        move.l  saved_vbl,VBL_VECTOR(a0)
        clr.l   saved_vbl
.done
        rts

vbl
        ; The TOS VBL routine is reached by tail chaining and does not promise
        ; to preserve the interrupted foreground registers. Retain them here
        ; so ordinary (IPL 3) foreground code may safely perform GEMDOS
        ; resource work between VBL-paced frames.
        movem.l d0-d7/a0-a6,saved_vbl_registers
        addq.l  #1,frame_count
        tst.l   saved_vbl
        beq     .publish_rte
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
        ; TOS 4.04 republishes its desktop page in its own VBL handler. Apply
        ; the Falcon page only after that chain, still at the VBL boundary.
        bsr     .publish_pending
        move.l  saved_vbl_return,-(sp)
        movem.l saved_vbl_registers,d0-d7/a0-a6
        move.w  saved_vbl_sr,sr
        rts

.publish_rte
        bsr     .publish_pending
        movem.l saved_vbl_registers,d0-d7/a0-a6
        rte

; The foreground publishes one longword before it flips its logical pointers.
; This routine writes the three Videl base bytes as one VBL-owned transaction.
.publish_pending
        tst.l   pending_screen
        beq     .done
        move.b  pending_screen+1,$ffff8201.w
        move.b  pending_screen+2,$ffff8203.w
        move.b  pending_screen+3,$ffff820d.w
        clr.l   pending_screen
.done
        rts

        bss
        even
saved_vbl      ds.l    1
vbl_vector_base ds.l   1
frame_count    ds.l    1
saved_vbl_return ds.l  1
saved_vbl_sr   ds.w    1
                even
saved_vbl_registers ds.l 15

        end
