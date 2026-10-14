; Minimal XBIOS macros used by the Falcon bootstrap.

        macro   Initmouse
        pea     \3
        pea     \2
        move.w  \1,-(sp)
        move.w  #0,-(sp)
        trap    #14
        lea     12(sp),sp
        endm

        macro   Kbdvbase
        move.w  #34,-(sp)
        trap    #14
        addq.l  #2,sp
        endm

        macro   Physbase
        move.w  #2,-(sp)
        trap    #14
        addq.l  #2,sp
        endm

        macro   Vsync
        move.w  #37,-(sp)
        trap    #14
        addq.l  #2,sp
        endm

; Falcon DSP XBIOS calls.  Keep the stack layouts here rather than open-code
; them in the C2P host: the program loader takes a long scratch-buffer
; address between its word ability and filename arguments.
        macro   Dsp_Available
        pea     \2
        pea     \1
        move.w  #106,-(sp)
        trap    #14
        lea     10(sp),sp
        endm

        macro   Dsp_Reserve
        move.l  \2,-(sp)
        move.l  \1,-(sp)
        move.w  #107,-(sp)
        trap    #14
        lea     10(sp),sp
        endm

        macro   Dsp_LoadProgram
        pea     \3
        move.w  \2,-(sp)
        pea     \1
        move.w  #108,-(sp)
        trap    #14
        lea     12(sp),sp
        endm
