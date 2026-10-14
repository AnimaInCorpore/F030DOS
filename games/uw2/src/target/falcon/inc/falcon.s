; Falcon030 presentation constants.
;
; Target: Atari Falcon030, MC68030, Motorola syntax, TOS .TOS output.
; The source is intentionally 68000-clean; the Makefile still assembles this
; target with -m68030 so the declared Falcon CPU is checked by the toolchain.

        include "../../common/inc/uw2.s"

FALCON_FRAME_WIDTH       = UW2_FRAME_WIDTH
FALCON_FRAME_HEIGHT      = UW2_FRAME_HEIGHT
FALCON_FRAME_PIXELS      = UW2_FRAME_BYTES
FALCON_RGB565_BYTES      = FALCON_FRAME_PIXELS*2
FALCON_LUT_ENTRIES       = UW2_PALETTE_ENTRIES
FALCON_LUT_BYTES         = FALCON_LUT_ENTRIES*2

        if FALCON_FRAME_WIDTH<>320
        fail    "Falcon presentation contract requires 320 pixels per row"
        endif

        if FALCON_FRAME_HEIGHT<>200
        fail    "Falcon presentation contract requires 200 rows"
        endif
