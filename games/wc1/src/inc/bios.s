; Minimal BIOS keyboard macros.

        macro   Bconstat
        move.w  \1,-(sp)
        move.w  #1,-(sp)
        trap    #13
        addq.l  #4,sp
        endm

        macro   Bconin
        move.w  \1,-(sp)
        move.w  #2,-(sp)
        trap    #13
        addq.l  #4,sp
        endm
