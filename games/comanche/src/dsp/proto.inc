; Route: dormant/Unproven DSP route; no supported Falcon attract source.
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; Comanche 68030 <-> DSP56001 frame protocol.
;
; This file is included by BOTH assemblers: ASM56000 for the DSP kernel and
; vasm for the 68030 host side. Keep it to `NAME EQU value` lines, `;`
; comments, and simple integer arithmetic - that is the intersection of the
; two syntaxes. Anything richer belongs in the side-specific include.
;
; The point of a single file is that a field layout cannot drift between the
; producer and the consumer. If a field is added, both sides recompile.

; The protocol version carries the ray geometry, so a host and a kernel
; built for different widths refuse each other loudly at the version check
; instead of rendering a half-width frame into full-width offsets. Base 2:
; version 1 was the 8.16-position protocol; base 4 was the pre-1:1 span
; convention, where records started at the projected row and the floor was
; the first covered row - a stale .lod from that world would paint every
; span one row off, which is exactly what this check exists to refuse; base
; 6 was the 8:1/32:1 far tiling, whose lane shifts and schedule a stale
; kernel would apply to 4:1/16:1 tiles. Version 10 cropped source columns
; 14..173; version 11 crops the displayed window 16..175.
CMD_VERSION     EQU     11

; ---------------------------------------------------------------------------
; Geometry, and it is the original's rather than a choice. The DOS renderer
; marches 192 columns and its transfer gives each source byte two adjacent
; screen pixels, so a terrain column is two pixels wide. Measured off the
; game's own screenshots the horizontal runs in the terrain band are
; overwhelmingly even - 2px 2839, 4px 860, 6px 385, 8px 190 against 582
; single-pixel runs - which is what a 2:1 column produces.
;
; The Falcon surface presents each recovered source column as two adjacent
; pixels. The DOS field is 192 columns wide (384 expanded pixels). The
; transfer (00007AA0, runs built at 00007035-000070DF) lays source column c at
; page x 2*(c - 14): page byte b carries compose-block bytes 23+b and 151+b,
; which are columns 14+2b and 15+2b. The 328-pixel logical line is displayed
; from page x 4, because 00015BB7 programs the CRTC start from [0x19CAC], and
; that is [0x19CA8] + 1 byte (00015C06). So the visible 320 pixels are source
; columns 16..175. Measured on paired DOS/Falcon frames on 2026-09-22: the
; terrain matched the DOS page at x 0 when this port cropped from 14, and the
; cockpit matched at PAGE_VIEW_X. See docs/PORTING-PLAN.md, "The second pair".
; The marcher still walks all 192 columns so its bearings and horizon state
; remain the DOS ones; only the final surface crop is platform-specific.
; ---------------------------------------------------------------------------

TERRAIN_COLS    EQU     192
TERRAIN_XSTEP   EQU     2
TERRAIN_VIEW_FIRST EQU 16
TERRAIN_VIEW_LAST  EQU 175
TERRAIN_PAGE_ANCHOR EQU 213

; ---------------------------------------------------------------------------
; Command block: 68030 -> DSP, a fixed number of 24-bit words, in this order.
;
; Fixed length is deliberate. Both sides drive the transfer from a counted
; loop rather than a parser, and a port with no framing cannot resynchronise
; after a variable-length record goes wrong.
; ---------------------------------------------------------------------------

CMD_W_VERSION   EQU     0       ; CMD_VERSION, rejected if it does not match
CMD_W_SEQUENCE  EQU     1       ; frame sequence number, wraps freely
CMD_W_CAM_X     EQU     2       ; camera position, tile-local, FIX_POS below
CMD_W_CAM_Y     EQU     3
CMD_W_CAM_Z     EQU     4       ; camera height above the map datum
CMD_W_DIR_X     EQU     5       ; forward vector, FIX_DIR signed fractional
CMD_W_DIR_Y     EQU     6
CMD_W_RIGHT_X   EQU     7       ; right vector, FIX_DIR; the per-column fan is
CMD_W_RIGHT_Y   EQU     8       ; derived from these two on the DSP
CMD_W_HORIZON   EQU     9       ; screen row of the horizon, integer pixels
CMD_W_PITCH     EQU     10      ; signed row offset added to every projection
CMD_W_SCALE     EQU     11      ; projection scale, applied before 1/z
CMD_W_TILE_ORG  EQU     12      ; near-tile origin, packed as (y<<12)|x

; Tile payload. When CMD_W_TILE_WORDS is non-zero the DSP reads that many more
; words immediately after this block and writes them into the tile from
; CMD_W_TILE_DEST, stepping by CMD_W_TILE_STRIDE. The count lives inside the
; fixed block on purpose: the transfer stays a counted loop on both sides, so
; the port never has to resynchronise, which is the same reason the block
; itself is fixed length.
;
; The stride is what lets one mechanism carry both edges. The tile is row
; major, so a row strip is contiguous and a column strip steps by the tile
; width; sending either is the same loop with a different stride.
CMD_W_TILE_DEST EQU     13      ; first tile index to write
CMD_W_TILE_WORDS EQU    14      ; payload words following this block, 0 = none
CMD_W_TILE_STRIDE EQU   15      ; index step between payload words
CMD_W_FLAGS     EQU     16      ; CMD_F_* below
CMD_W_F2OFF_X   EQU     17      ; world minus camera-local, FIX_POS, the pair
CMD_W_F2OFF_Y   EQU     18      ; that turns the rebased position back into
                                ; whole-map coordinates: the command keeps 9
                                ; integer bits and the map needs 10
CMD_W_COUNT     EQU     19      ; total words; keep last

; Command flags.
CMD_F_RENDER    EQU     $000001 ; render a frame from this command
CMD_F_TILE_MOVE EQU     $000002 ; near-tile origin changed
CMD_F_HALT      EQU     $000004 ; leave the frame loop, return to idle
CMD_F_TILE_FAR  EQU     $000008 ; payload goes to the far tile in Y, not near
CMD_F_TILE_FAR2 EQU     $000020 ; payload goes to the resident whole-map tile
                                ; in X, above the near window; sent once at
                                ; init, never again
CMD_F_TILE_FLOOR EQU    $000010 ; legacy protocol word; the faithful kernel
                                ; seeds every column at the DOS page anchor.
                                ; The host still sends the fixed-size block so
                                ; old command framing cannot desynchronise,
                                ; but the values are no longer a console clip.

; ---------------------------------------------------------------------------
; Result block: DSP -> 68030. One header word, then RECT_WORDS per rectangle,
; terminated by RECT_END so the host can drain without a prior count.
; ---------------------------------------------------------------------------

RES_W_STATUS    EQU     0       ; RES_S_* below
RES_W_SEQUENCE  EQU     1       ; echoes CMD_W_SEQUENCE, so a stale frame is
RES_W_COUNT     EQU     2       ; visible rather than silently composited

RES_S_IDLE      EQU     $000000
RES_S_BUSY      EQU     $000001
RES_S_DONE      EQU     $000002
RES_S_BADVER    EQU     $0000FF ; command version mismatch, nothing rendered

; Rectangle record: two 24-bit words.
;
;   word 0   fb_offset:24     byte offset into the back buffer
;   word 1   width:8 | height:8 | colour:8
;
; A 320x240 16-bit surface is 153,600 bytes, so 24 bits of offset is ample.
; The best-quality path emits one rectangle per surface pixel column. Width is
; therefore 1 and the host expands each record with a word store.

RECT_WORDS      EQU     2
RECT_SHIFT_W    EQU     16      ; width  field position in word 1
RECT_SHIFT_H    EQU     8       ; height field position
RECT_SHIFT_C    EQU     0       ; colour field position
RECT_END        EQU     $FFFFFF ; sentinel in word 0, no word 1 follows

; Largest result the DSP will emit in one frame. The host reserves this much
; and the DSP stops emitting at the limit rather than overrunning; a frame
; that hits the cap is a bug worth seeing, not a corruption worth hiding.
RECT_MAX        EQU     2048

; ---------------------------------------------------------------------------
; Fixed-point formats. Referenced from the command block above as FIX_*.
;
; The 56001 multiplies fractionally: mpy leaves x*y/2**23 in a1. Every format
; here is chosen so the inner loop needs that one multiply and no shifts.
; ---------------------------------------------------------------------------

; Ray position, 11.13: eleven integer bits, thirteen fractional. The integer
; width is what forced 13 rather than the earlier 16: the far tile is
; addressed as (pos >> (FIX_POS+TILE_FAR_SHIFT)) & TILE_FAR_MASK, which
; needs the position to carry the world coordinate modulo the tile's span -
; nine integer bits at the original 8:1 tiling, eight at today's 4:1 - and
; an 8.16 word carried too few, so the far index repeated early and the
; upper half of the far tile could never be addressed.
; Thirteen fractional bits still walk a 60-sample march with accumulated error
; below a thousandth of a map unit, and the sine table behind the directions
; only carries eight fractional bits anyway.
; The camera words arrive in this format, masked to 24 bits by the host; the
; kernel masks every index to its tile, so no origin subtraction exists on
; either side.
FIX_POS         EQU     13

; Direction words, 2.22 signed. Not 1.23, for two reasons found the hard way:
; cos(0) is exactly +1.0, which 1.23 cannot represent - the host's shift
; wrapped it to -1.0 and every axis-aligned heading rendered backwards - and
; the fan edges are dir +/- right, magnitude up to sqrt(2), which needs the
; integer bit even where the basis vectors alone would fit.
; A unit of depth advances the position by the direction, so the per-step
; delta is the direction shifted from 22 fractional bits down to 13.
FIX_DIR         EQU     22

; Height difference is pre-scaled by this before the projection multiply, and
; the reciprocal table carries PROJ*2**15/z, so that
;   (dz << 8) * (PROJ*2**15/z) / 2**23  =  dz*PROJ/z
; lands in a1 as a row count with nothing left to shift.
FIX_DZ          EQU     8
FIX_PROJ        EQU     15

; 2**23/(COLS/2) rounded, the per-column fan step. The rounding error is a
; fraction of one in 2**23 per column, below the position format's least bit
; across the whole fan. The fan spans the right vector twice across
; TERRAIN_COLS columns, so each column advances by right/(COLS/2).
FIX_FAN_STEP    EQU     (8388608+(TERRAIN_COLS/4))/(TERRAIN_COLS/2)


; The tile is toroidal, which is the whole reason a 128x128 window is
; affordable. Every index is masked, so the window wraps: when the camera
; leaves the tile by one unit the strip that falls off the back and the strip
; that appears at the front land on the same index, and only that strip has to
; be sent. A full load is 16,384 words and about 48 KB through the port - a
; startup cost - while one unit of movement is 128 words for the near tile and
; a sixty-fourth of a far strip, which is under a kilobyte a frame at one unit
; per frame.
;
; Near tile: full resolution, resident in X memory, power of two so the
; address is a shift and a mask rather than a multiply.
;
; This was 128x128 and 16,384 words, on the reasoning that it exactly fills a
; 16 KWord X memory. Exactly filling it is the problem: Dsp_Available on a
; Falcon under Hatari reports 16,040 X words free, because XBIOS keeps 344 for
; itself, so the reserve failed and every DSP frame fell back to the CPU -
; silently, and with a pixel-identical frame, which is what made it look like
; a match rather than a failure.
;
; 64x64 fits with room to spare. The cost is the full-detail radius: the near
; march has to stop at the tile edge, so it drops from 64 steps to 32 and the
; far march makes up the distance. Total reach is unchanged at 256 units.
TILE_NEAR_BITS  EQU     6
TILE_NEAR_SIZE  EQU     64
TILE_NEAR_MASK  EQU     63
TILE_NEAR_WORDS EQU     4096    ; 64*64, against the 16,040 X words offered

; Far tile: decimated, resident in Y memory alongside the working set. 4:1
; rather than the earlier 8:1 - the far field was the visibly low-res part
; of the frame, and halving the cell doubles the lateral and depth sampling
; where it shows most, at the cost of the far reach moving from 256 to 128
; units (the resident whole-map tier picks up from there at 16:1).
TILE_FAR_BITS   EQU     6
TILE_FAR_SIZE   EQU     64
TILE_FAR_MASK   EQU     63
TILE_FAR_SHIFT  EQU     2       ; 4:1 decimation, so 64 samples span 256 units
TILE_FAR_WORDS  EQU     4096

; Far2 tile: the whole map at 16:1, resident in the X half above the near
; tile. At this decimation 64 samples span the full 1024-unit torus exactly,
; so the tile IS the map: the window never moves, it is uploaded exactly
; once at init, and the 64-cell field mask wraps precisely at the map's own
; period - the earlier 32:1 tile needed 2x2 replication to make that true,
; this one does not.
TILE_FAR2_SHIFT EQU     4       ; 16:1 decimation
TILE_FAR2_WORDS EQU     4096    ; 64x64, the whole torus, no replication

; Depth march: unit steps through the near tile, then decimated steps beyond,
; then coarse steps through the resident whole-map tile. Named MARCH_* rather
; than DEPTH_*: inc/comanche.s already owns DEPTH_NEAR, DEPTH_FAR and
; DEPTH_STEP for the 68030 reference renderer's bring-up scene.
; The near march cannot walk further than the tile's half-width or it wraps
; onto terrain behind the camera. 32 near steps at one unit, 24 far steps at
; four, then 54 far2 steps at sixteen: 992 map units, the range the
; original's 250 .DTL steps cover at about 985.
MARCH_NEAR_STEPS EQU    32
MARCH_FAR_STEPS EQU     24
MARCH_FAR2_STEPS EQU    54

; A map sample is one packed word: spare:8 | height:8 | colour:8.
;
; The height sits at bits 8-15 rather than the top byte for two reasons the
; inner loop cares about: bit 23 stays clear, so the sample never reads as
; negative on the DSP (heights past 127 once arrived as sign bits), and
; `packed & $FF00` IS the projection's pre-scaled height term - the kernel
; computes dz<<8 as (camz<<8) - (packed & $FF00) with no shift at all.
MAP_SHIFT_H     EQU     8
MAP_SHIFT_C     EQU     0

; Viewport rows. Shared because the ybuffer is initialised to the bottom row
; on the DSP and the host clips against the same number.
SCREEN_ROWS     EQU     240
