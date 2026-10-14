; C-callable GEMDOS file primitives for the freestanding resource loader.
;
; m68k-elf-gcc passes 32-bit arguments on the stack. The wrappers deliberately
; use only caller-saved registers so they preserve the normal C ABI while the
; existing assembly startup remains the owner of TOS/supervisor state.

        include "inc/gemdos.s"

        xdef    wc_fopen
        xdef    wc_fclose
        xdef    wc_fread
        xdef    wc_fseek

        text

; int32_t wc_fopen(const char *path, int32_t mode)
wc_fopen
        move.l  4(sp),a0
        move.l  8(sp),d1
        move.w  d1,-(sp)
        move.l  a0,-(sp)
        move.w  #61,-(sp)
        trap    #1
        addq.l  #8,sp
        rts

; int32_t wc_fclose(int32_t handle)
wc_fclose
        move.l  4(sp),d0
        move.w  d0,-(sp)
        move.w  #62,-(sp)
        trap    #1
        addq.l  #4,sp
        rts

; int32_t wc_fread(int32_t handle, uint32_t count, void *destination)
wc_fread
        move.l  4(sp),d0
        move.l  8(sp),d1
        move.l  12(sp),a0
        move.l  a0,-(sp)
        move.l  d1,-(sp)
        move.w  d0,-(sp)
        move.w  #63,-(sp)
        trap    #1
        lea     12(sp),sp
        rts

; int32_t wc_fseek(int32_t offset, int32_t handle, int32_t whence)
wc_fseek
        move.l  4(sp),d0
        move.l  8(sp),d1
        move.l  12(sp),a0
        move.w  a0,-(sp)
        move.w  d1,-(sp)
        move.l  d0,-(sp)
        move.w  #66,-(sp)
        trap    #1
        lea     10(sp),sp
        rts

        end
