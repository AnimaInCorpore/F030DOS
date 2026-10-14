; Target-neutral POR constants.
;
; NOTHING IN THIS FILE MAY ASSUME A TARGET. Pool of Radiance renders 320x200
; indexed EGA; every port draws into a linear 8-bit index surface with the DOS
; palette index preserved verbatim, and only the target back end turns that
; surface into hardware pixels. Falcon RGB565 constants live in
; src/target/falcon/inc/falcon.s; an ST back end would add its own.
;
; Code in src/common/ must also stay **68000-clean** — the Atari ST is a live
; target, so 68020+ instructions and misaligned word access belong in
; src/target/<name>/ only. See PORTING.md §Target back ends.

GAME_WIDTH      = 320
GAME_HEIGHT     = 200
SURFACE_WIDTH   = 320
SURFACE_HEIGHT  = 200
SURFACE_STRIDE  = SURFACE_WIDTH
SURFACE_BYTES   = SURFACE_WIDTH*SURFACE_HEIGHT

; ---------------------------------------------------------------------------
; `PORI` image bank, produced by tools/convert_data.py from the resolved DOS
; formats. Big-endian throughout. tools/check_contracts.py asserts that these
; constants and the converter agree — change both together, never one alone.
; ---------------------------------------------------------------------------
PORI_MAGIC          = 'PORI'
PORI_VERSION        = 1

PORI_OFF_MAGIC      = 0         ; char[4]
PORI_OFF_VERSION    = 4         ; u16
PORI_OFF_COUNT      = 6         ; u16  image count
PORI_OFF_PALCOUNT   = 8         ; u16  palette entries
PORI_OFF_FLAGS      = 10        ; u16  palette encoding, PORI_PAL_*
PORI_OFF_PALETTE    = 12        ; u16[PORI_PALETTE_COUNT] RGB565
PORI_PALETTE_COUNT  = 16
PORI_HEADER_BYTES   = 44

; Palette encoding of the PORI_OFF_PALETTE table. A bank is built for one
; target's palette format and says which, so a wrong-target bank is refused
; rather than displayed in the wrong colours.
PORI_PAL_NONE       = 0
PORI_PAL_RGB565     = 1         ; Falcon true colour, big-endian word per entry
PORI_PAL_ST         = 2         ; Atari ST/STE $0RGB word per entry (reserved)

PORI_DIR_ENTRY_BYTES = 16
PORI_DIR_WIDTH      = 0         ; u16
PORI_DIR_HEIGHT     = 2         ; u16
PORI_DIR_SOURCEID   = 4         ; u16  DAX block id / frame index
PORI_DIR_RESERVED   = 6         ; u16
PORI_DIR_OFFSET     = 8         ; u32  from bank start
PORI_DIR_BYTES      = 12        ; u32  == width*height

; Largest bank the loader will accept. TITLE.BIN is 128,076 B; this leaves
; headroom without threatening the stock 4 MB Falcon target.
PORI_MAX_BYTES      = $30000

; Status codes written to PORSTAT.BIN by the headless self-check.
STATUS_OK           = 0
STATUS_OPEN_FAILED  = 1
STATUS_BAD_MAGIC    = 2
STATUS_BAD_VERSION  = 3
STATUS_NO_IMAGES    = 4
