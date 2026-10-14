; Minimal GEMDOS macros used by the Falcon bootstrap.

        macro   Cconws
        pea     \1
        move.w  #9,-(sp)
        trap    #1
        addq.l  #6,sp
        endm

        macro   Pterm0
        clr.w   -(sp)
        trap    #1
        endm

        macro   Super
        pea     \1
        move.w  #32,-(sp)
        trap    #1
        addq.l  #6,sp
        endm

        ; Release the unused tail of the TPA assigned at program launch.
        ; Without this, GEMDOS has no free ST-RAM block from which to allocate
        ; Videl-visible framebuffers.
        macro   Mshrink
        move.l  \2,-(sp)
        move.l  \1,-(sp)
        clr.w   -(sp)
        move.w  #74,-(sp)
        trap    #1
        lea     12(sp),sp
        endm

        macro   Mxalloc
        move.w  \2,-(sp)
        move.l  \1,-(sp)
        move.w  #68,-(sp)
        trap    #1
        addq.l  #8,sp
        endm

        macro   Mfree
        move.l  \1,-(sp)
        move.w  #73,-(sp)
        trap    #1
        addq.l  #6,sp
        endm

        macro   Fopen
        move.w  \2,-(sp)
        pea     \1
        move.w  #61,-(sp)
        trap    #1
        addq.l  #8,sp
        endm

        macro   Fcreate
        move.w  \2,-(sp)
        pea     \1
        move.w  #60,-(sp)
        trap    #1
        addq.l  #8,sp
        endm

        macro   Fclose
        move.w  \1,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
        endm

        macro   Fread
        pea     \3
        move.l  \2,-(sp)
        move.w  \1,-(sp)
        move.w  #63,-(sp)
        trap    #1
        lea     12(sp),sp
        endm

        macro   Fwrite
        pea     \3
        move.l  \2,-(sp)
        move.w  \1,-(sp)
        move.w  #64,-(sp)
        trap    #1
        lea     12(sp),sp
        endm

        macro   Fseek
        move.w  \3,-(sp)
        move.w  \2,-(sp)
        move.l  \1,-(sp)
        move.w  #66,-(sp)
        trap    #1
        lea     10(sp),sp
        endm

        ; Console status / input, used by the title endpoint to leave on a key.
        macro   Cconis
        move.w  #11,-(sp)
        trap    #1
        addq.l  #2,sp
        endm

        macro   Cnecin
        move.w  #8,-(sp)
        trap    #1
        addq.l  #2,sp
        endm
