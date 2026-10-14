; Route: analysis/functions/falcon-attract.md#resources
; Record: analysis/functions/falcon-attract.md#resources
; Source boundary: shared by the SG sprite loader (sprite.s) and the sound
; bank loader (sound.s); split out of sprite.s unchanged so the sound layer's
; stand-alone test program links the same routine the game does.

        global  krl_decode

        text

; The KRL byte RLE. In: a0 = source, d2 = source bytes, a1 = destination,
; d0 = destination bytes. Out: d0 = 0 if the full output was produced.
;
; A byte below $C0 is a literal; $C0 or above is a run of `byte & $3F` copies
; of the next byte. This is the same codec decode_dta in resources.s uses for
; the terrain files; the two differ only in framing and bound, and the shared
; description is in ASSET-INVENTORY.md. A count of zero writes nothing and
; still consumes both bytes - that is what `rep stosb` with ECX=0 does in the
; original, so it is not treated as an error here either.
; DOS: flat 0001644B, KRL1/KRL0 decompressor.
; DOS symbol: sub_0001644B
; Record: analysis/functions/falcon-attract.md#resources
; Port: expands the authored KRL byte stream into its exact payload size.
; Preserved: control-byte/literal semantics and output bounds.
; Kind: translated.
; Status: ported; source bank validation is available locally.
krl_decode
        movem.l d1-d4/a0-a1,-(sp)
        move.l  d0,d3                   ; output remaining
.token
        tst.l   d3
        beq     .ok
        tst.l   d2
        beq     .fail
        moveq   #0,d1
        move.b  (a0)+,d1
        subq.l  #1,d2
        cmpi.b  #$c0,d1
        bcc     .run
        move.b  d1,(a1)+
        subq.l  #1,d3
        bra     .token
.run
        andi.w  #$3f,d1
        tst.l   d2
        beq     .fail
        move.b  (a0)+,d4
        subq.l  #1,d2
        tst.w   d1
        beq     .token
        cmp.l   d3,d1
        bhi     .fail                   ; a run past the end is a bad stream
        sub.l   d1,d3
        subq.w  #1,d1
.emit
        move.b  d4,(a1)+
        dbra    d1,.emit
        bra     .token
.ok
        moveq   #0,d0
        bra     .decoded
.fail
        moveq   #-1,d0
.decoded
        movem.l (sp)+,d1-d4/a0-a1
        rts

        end
