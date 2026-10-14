; N/A - platform replacement: exact wide integer products on MC68060.
; Record: analysis/functions/cpu-compatibility.md
; The default MC68030 path retains its native 32x32 -> 64 instruction.
; CCR is scratch at these arithmetic seams; every caller consumes the product,
; not the multiply's flags. All non-result registers are preserved.

        ifnd TARGET_CPU
TARGET_CPU = 68030
        endc

        global vector_base
        ifeq TARGET_CPU-68060
        global cpu_muls64, cpu_mulu64
        endc

; In: d0 and source. Out: d1:d0. Source may also be d1.
        macro MulS64
        ifeq TARGET_CPU-68060
        move.l  \1,d1
        jsr     cpu_muls64
        else
        muls.l  \1,d1:d0
        endc
        endm

; In: d0 and d1. Out: d2:d0; preserve the source d1.
        macro MulS64D2
        ifeq TARGET_CPU-68060
        move.l  d1,-(sp)
        jsr     cpu_muls64
        move.l  d1,d2
        move.l  (sp)+,d1
        else
        muls.l  d1,d2:d0
        endc
        endm

        macro MulU64D2
        ifeq TARGET_CPU-68060
        move.l  d1,-(sp)
        jsr     cpu_mulu64
        move.l  d1,d2
        move.l  (sp)+,d1
        else
        mulu.l  d1,d2:d0
        endc
        endm

; Supervisor publication boundary. Leave OS cache policy intact while making
; completed RGB565 writes visible to VIDEL on a copyback-cached accelerator.
        macro ScreenCachePush
        ifeq TARGET_CPU-68060
        cpusha  dc
        endc
        endm
