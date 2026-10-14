; Falcon030 presentation constants.
;
; The Falcon presents the completed indexed surface in 16-bit true colour, one
; big-endian RGB565 word per pixel, so it never programs a palette register.
; These constants are target-private: nothing in src/common/ may reference them.

        include "../../common/inc/por.s"

FRAME_WIDTH      = SURFACE_WIDTH
FRAME_HEIGHT     = SURFACE_HEIGHT
FRAME_LINE_WORDS = FRAME_WIDTH
FRAME_STRIDE     = FRAME_WIDTH*2
FRAME_BYTES      = FRAME_STRIDE*FRAME_HEIGHT

VBL_VECTOR       = $70
VBL_WAIT_LIMIT   = $40000

; Index -> RGB565 lookup, one word per possible index byte so the expansion
; inner loop needs no masking.
LUT_ENTRIES      = 256
LUT_BYTES        = LUT_ENTRIES*2
