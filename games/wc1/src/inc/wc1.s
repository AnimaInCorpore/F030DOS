; Shared Falcon/WC1 constants.
;
; The original DOS renderer is 320x200 indexed colour. The Falcon presents the
; completed frame in 16-bit true colour, so the CPU renders a linear 8-bit
; index buffer and expands it through the loaded palette at the page boundary.

GAME_WIDTH      = 320
GAME_HEIGHT     = 200
FRAME_WIDTH     = 320
FRAME_HEIGHT    = 200
CHUNKY_BYTES    = FRAME_WIDTH*FRAME_HEIGHT
CHUNKY_STRIDE   = FRAME_WIDTH
FRAME_STRIDE    = FRAME_WIDTH*2
; Falcon true-colour mode stores one big-endian RGB565 word per pixel.
FRAME_LINE_WORDS = FRAME_WIDTH
FRAME_BYTES     = FRAME_STRIDE*FRAME_HEIGHT
VIEW_TOP        = 0
VIEW_BOTTOM     = GAME_HEIGHT-1
VIEW_CENTRE_X   = GAME_WIDTH/2

; The recovered WC1 source uses short-sized state for most game quantities.
; WC1's MultiplyFixed(), Vector_magnitude(), and FixedToShortSaturating()
; establish a signed 24.8 world-coordinate representation. Heading remains
; one byte of a turn.
FIX_SHIFT       = 8
TURN_MASK       = $00ff

INPUT_LEFT      = 0
INPUT_RIGHT     = 1
INPUT_SPEEDUP   = 2
INPUT_SLOWDOWN  = 3
INPUT_FIRE      = 4
INPUT_ACCEPT    = 5
INPUT_QUIT      = 15

; IKBD relative-mouse packet button bits. The left button shares the existing
; fire/accept action so the title endpoint and flight loop need no separate
; mouse-only dispatch path.
MOUSE_BUTTON_LEFT = 0

; Indexed diagnostic colours. WC1 asset pixels retain their source palette
; index verbatim; these values are used only by the temporary radar/HUD path.
COL_BLACK       = $00
COL_SPACE       = $00
COL_SPACE_MID   = $01
COL_SPACE_LIGHT = $02
COL_STAR        = $0f
COL_CYAN        = $0b
COL_GREEN       = $0a
COL_AMBER       = $0e
COL_RED         = $04
COL_PANEL       = $03
COL_PANEL_EDGE  = $0d
COL_WHITE       = $0f

VBL_VECTOR      = $70
VBL_WAIT_LIMIT  = $40000

; Mission packet layout, recovered from wc1-re/src/cmpgn.c. The original
; files are Intel-endian archives; mission.s converts fields on load.
MISSION_SERIES_COUNT     = 3
MISSIONS_PER_SERIES      = 4
; The DOS runtime advances its INSTALL.DAT table pointer by one after it has
; indexed it. Campaign data set 0 calls resource 15 there, which is the
; on-disk MODULE.000 record with logicalFile id 16.
MISSION_ARCHIVE_LOGICAL  = 16
MISSION_HEADER_BYTES     = $18
MISSION_NAV_BYTES        = $4d
MISSION_OBJECTIVE_BYTES  = $40
MISSION_SHIP_BYTES       = $2a
MISSION_NAV_COUNT        = 16
MISSION_OBJECTIVE_COUNT  = 16
MISSION_SHIP_COUNT       = 32
MISSION_PACKET_DIR_MAX   = $200
MISSION_INSTALL_MAX      = $800
MISSION_COMPRESSED_MAX   = $20000
MISSION_DECOMPRESS_MAX   = $15000

; Generated Falcon mission cache.  These records are host-converted from the
; exact DOS layouts above: multi-byte fields are big-endian and the two
; unaligned DOS records gain explicit padding before their long fields.
FALCON_CACHE_VERSION             = 1
FALCON_CACHE_HEADER_BYTES        = $40
FALCON_CACHE_MISSION_COUNT       = 64
FALCON_MISSION_HEADER_BYTES      = $18
FALCON_MISSION_NAV_BYTES         = $4e
FALCON_MISSION_OBJECTIVE_BYTES   = $40
FALCON_MISSION_SHIP_BYTES        = $2c
FALCON_MISSION_NAV_BLOCK_BYTES   = MISSION_NAV_COUNT*FALCON_MISSION_NAV_BYTES
FALCON_MISSION_OBJECTIVE_BLOCK_BYTES = MISSION_OBJECTIVE_COUNT*FALCON_MISSION_OBJECTIVE_BYTES
FALCON_MISSION_SHIP_BLOCK_BYTES  = MISSION_SHIP_COUNT*FALCON_MISSION_SHIP_BYTES
FALCON_CACHE_TOTAL_BYTES = FALCON_CACHE_HEADER_BYTES+FALCON_CACHE_MISSION_COUNT*(FALCON_MISSION_HEADER_BYTES+FALCON_MISSION_NAV_BLOCK_BYTES+FALCON_MISSION_OBJECTIVE_BLOCK_BYTES+FALCON_MISSION_SHIP_BLOCK_BYTES)

MISSION_STATUS_FALLBACK  = 1
MISSION_STATUS_DOS_RAW   = 2
MISSION_STATUS_DOS_LZW   = 3
MISSION_STATUS_COMPRESSED = 4

ORIGIN_LZW_CLEAR_CODE    = $100
ORIGIN_LZW_STOP_CODE     = $101
ORIGIN_LZW_FIRST_CODE    = $102
ORIGIN_LZW_MAX_CODES     = $1000

; prepare_mission() creates the player then considers its eight initial ship
; slots. Keep that exact first-flight capacity separate from the larger 32
; packed mission record table.
FLIGHT_OBJECT_MAX        = 9
