; Route: analysis/functions/falcon-attract.md#attract-route (shared CPU contracts).
; Source boundary: this file is active only for the traced CPU attract milestone.
;
; Shared constants for the Falcon-side Comanche port.
; The CPU renderer and flight state use the recovered map/fixed-point
; contracts; the DSP protocol's shared geometry lives in dsp/proto.inc.

        include "inc/cpu.s"

; Shared staging buffer for compressed resources. C2.DTA is the largest
; installed terrain stream (812,397 bytes); the DOS reader keeps one
; compressed file in a shared arena before decoding it, and the sprite loader
; reuses the arena afterwards.
RESOURCE_BUFFER_BYTES = 850000

; The original's Mode X page row is 0x52 bytes per plane - 82 x 4 = 328
; pixels - and the displayed window is 320, which is 80 bytes per plane. The
; two spare bytes are one byte column of margin at each side, so the window
; starts at page x = 4 and
;
;     surface x = page x - PAGE_VIEW_X
;
; Every DOS coordinate that reaches a blitter is a PAGE x: 00025B27 and
; 00025BB6 take one as a pixel, 00025C55 as a byte column, 00025A4D as a byte
; offset, and the authored full-screen images are 328 wide (CONSOL1S.DTA,
; TPIC.DTA and BACK.DTA all carry 327 in their first header word), so their
; first four columns are off-screen left.
;
; The surface is RGB565, so this is 4 PIXELS and 8 BYTES. Subtract it from
; the pixel x before it is doubled into a byte offset; applying it after
; halves the correction.
PAGE_VIEW_X     = 4
; Every row of CONSOL<n>S.DTA: 0001687D blits all of them into the page, and the
; 240 the screen shows are followed in video memory by the rest, which the
; wreck's sinking window (00015BC9 + [00019DC4], up to 45 rows) slides over.
CONSOLE_ROWS    = 290
SCREEN_WIDTH    = 320
SCREEN_HEIGHT   = 240
SCREEN_HALF_W   = SCREEN_WIDTH/2
; Far-horizon reference used by the console geometry. The renderer and object
; placement take their terrain horizon from horizon_table, which the generator
; builds from HIGH.DTL table 3 - the bias 00015AD9 adds per depth step. That
; bias is a curve, not a constant: page row 137 at the far end and 60 at the
; nearest step, which is why one number could only ever be right at one depth.
;
; 77 is the far end of the curve at the original's own 1:1 rows, and the
; transfer is what fixes the anchor. sub_00006FEF walks source and destination
; in one loop - surface [00019E70]+0x2011 stepping `inc dh` against VGA
; [000014C4]+0x39FA stepping `sub 0x52`, 0xB6 times - so surface row 32 is VGA
; row 181, 182 rows, the source rising as the destination falls:
;
;       screen row = 213 - page row
;
; and the far horizon is 213 - floor(136.96) = 77. The surface is stored
; upside down, which is also why the emitter's `inc ch` walks a span UP the
; screen and the marcher's `ja` test lets the occlusion row climb.
;
; The previous 62 came from an anchor of 198, read off the 199-entry scanline
; table at 0002D7F0. That table describes a 192-pitch surface with no reader
; anywhere in the listing and is not the surface the emitter writes, whose
; `inc ch` is a 256-byte stride. Its supporting coincidence - the nearest
; ring's bias landing on CONSOL1S's windshield bottom - has no mechanism
; behind it: at the true anchor the near rows sit at 153, behind the panel,
; which is what a cockpit is for.
; How many screen rows the terrain path may touch at all, and it is not the
; screen. 00007AA0 does not blit a rectangle: it walks a run list built from
; the loaded console image's transparency - lengths and flags at 0x38B20,
; sources at 0x32B20, destinations at 0x34B20, `run_count` at [0x19E4C].
;
; Dumped out of the running original 2026-09-01 at two console variants:
;
;   variant 6 (consol5s)  168 runs, every one len 82 - a full-width rectangle
;   variant 1 (consol1s)  261 runs of 1..60 bytes - the canopy's own shape
;
; Different shapes, IDENTICAL row extent: both run lists start at source
; 0x042E11 and end at 0x04D5xx, stepping the surface's 256-byte row stride -
; surface rows 46..213, which through `screen row = 213 - surface row` is
; screen rows 0..167. So the terrain owns 168 rows and nothing below them.
;
; This matters only where the console is NOT drawn over the rest. 0000D4C4
; skips the cockpit for every view variant except 1, so in the attract's
; chase and fixed cameras the original shows the terrain in these 168 rows
; and, below them, whatever the attract's own title page left on its single
; visible page - the COMANCHE MAXIMUM OVERKILL art. This port used to
; compose terrain down to row 213 and fill the rest, which is the band that
; showed up as "not being painted as terrain" in the outside view.
TERRAIN_VIEW_ROWS = 168
SCREEN_HORIZON  = 77
; DOS sprite/object pages use the same bottom-up surface anchor as the terrain
; transfer: page row 0 appears at Falcon screen row 213. The DSP protocol owns
; the identically-valued terrain constant; this CPU-side name avoids importing
; that mixed-assembler include into every object module.
OBJECT_PAGE_ANCHOR = 213

; How deep the sky image paints: the backdrop's own authored height. The
; asset is 512 column strips of exactly 150 bytes (the directory record's
; width byte names it). The original paints all 150 per column and lets the
; terrain overwrite the overlap, which is what this port does too.
SKY_IMAGE_ROWS  = 150

; Where strip byte 0 lands, and it is off the top of the screen. The fill at
; 00017230 takes the column's horizon byte into dh and then runs 150 times
;
;       dec dh ; lodsb ; mov [edx],al
;
; so strip byte i is written at surface row (h - 1 - i) AND 0xFF. With h the
; small signed quantity backdrop_build computes - at rest byte(0x32 - 0 +
; byte(0 - 0 - 0x32)) = 0 - that subtraction wraps immediately, and through
; screen row = 213 - surface row it comes out as
;
;       screen row = i - 42 - h        (42 = 255 - 213)
;
; Level flight therefore shows strip bytes 42..149 on screen rows 0..107, not
; bytes 0..149 from row 0 down, and the 42 rows above the screen are the
; headroom the sky pans into when the nose comes up. For positive h, the
; source's 8-bit surface address also wraps bytes 0..h-1 to screen rows
; 214-h..213; render_clear keeps that lower segment before the cockpit pass.
; Anchoring byte 0 at row 0 instead is what previously forced render_clear to
; repeat the strip's top pixel upward and put thin vertical lines wherever
; that pixel was a cloud edge.
SKY_TOP_BIAS    = 42
; SKY2.RLE's full strip count, and the reason the backdrop pans. The sourced
; fill at 00016EC0 picks its first strip from the heading -
;   eax = NOT([00019D00]) - 0x30000000, eax >>= 0x17, eax *= 150
; - so the top nine bits of the view angle are a strip index and the bank's
; 512 strips are exactly one revolution. Each DOS source column then takes the
; next strip, wrapping at the bank's end. The Falcon presents those 192 source
; columns as two-pixel slots. The Falcon walks the full 192-column source field
; and crops the recovered displayed source window 16..175 at composition.
SKY_STRIPS      = 512
; The port's heading is 0..255 for a full turn - render.s indexes sin_table
; by it directly - so one heading unit is two strips.
SKY_STRIP_SHIFT = 1

; The strip index goes UP with the heading, not down - the port used to NEG
; here and ran the bank backwards. Superseded 2026-08-18 by render_clear taking
; the original's expression off the 32-bit flt_angle directly, which needs no
; constant and resolves all 512 strips instead of the 256 even ones an 8-bit
; heading can reach. Kept as the derivation that connects the two:
;
;       strip = (415 - 2a) AND 511 = (2h + 159) AND 511,  a = (128 - h) AND 255
;
; equal to the 32-bit form at all 256 byte headings.
; The original's own terrain column count for the high-detail bank: 192 blocks
; at 0000AF50, and the length of the horizon array at 0x3CB40. The Falcon keeps
; that 192-column walk and crops the expanded surface to source columns
; 16..175 only at composition.
TERRAIN_COLS_DOS = 192

; Projection scale: row = horizon + (alt/2 + 1 - h) * PROJ_SCALE / z.
;
; The shape of that expression is the original's rather than a model of it.
; DOS builds one 256-byte page per depth step at 00015AD9 with
; row = clamp((k - 128) * slope + bias, 0, 255), and across all 250 steps of
; HIGH.DTL its slope table satisfies dtl2[i] * z_i = 819200 * 2**32 to within
; per-entry rounding, so slope is a constant over z and this port's
; PROJ_SCALE/z is the same curve.
;
; The scalar is recovered too, and it had no writer because it needed none:
; 00019CEC is initialised data, 0x03000000, and the four bytes of its address
; occur exactly once in the whole image - at the read that consumes it. With
; slope_i = high32(dtl2[i] * 03000000) and dtl2[i] * z_i fixed at
; 819200 * 2**32, the projection collapses to
;
;     page row = (h - alt/2 - 1) * 150 / z + bias/256
;
; and the page rows land on the screen UNSCALED and inverted: the DOS mode is
; 328x240 (phase 8b - DTA headers, the CRTC stride, the screenshot writer's
; own header) and the transfer sub_00006FEF maps the surface to it in one
; loop, source row 32 to VGA row 181 over 182 rows, source rising as
; destination falls, so screen row = 213 - page row. An earlier reading took
; the view for a 200-row screen and scaled the package by 240/200, which drew
; every slope 20% too steep; a later one kept 1:1 but anchored at 198 from the
; unread 192-pitch scanline table, which held the whole picture 15 rows high.
; See SCREEN_HORIZON above for why the windshield cross-check that supported
; 198 does not survive contact with the transfer.
;
; The camera term is alt/2 + 1, not alt/2: the marcher's AL bias is
; NOT(alt)>>1 = 127 - floor(alt/2), and the page's (k - 128) then makes the
; level plane h = alt/2 + 1. The depth march runs to 992 map units against
; the original's 985 - 32 unit steps, 28 eight-unit, 23 thirty-two-unit.
PROJ_SCALE      = 150

; The fan half-width, as a 0.15 fraction of the right vector. The original's
; .DTL lateral table satisfies lat = z/100 exactly, 96 columns per half, so
; its half-fan tangent is 96/100; every renderer scales its right vector by
; this before building the fan, which is the one place the number exists.
FAN_HALF_TAN    = $7AE1

; Sprite banks are laid out as elevation bands of azimuth steps. TANK, TURR and
; RADR hold 51 frames = 3 x 17; HELL, HOKE, ROCK and STGR hold 85 = 5 x 17. The
; 17 steps sweep half a turn - narrow tail-on, broadside at the middle, narrow
; head-on - and the other half is the same frames drawn mirrored, which is what
; bit 7 of the DOS sprite index selects at 00025517.
SPRITE_AZIMUTH  = 17

; Set in a sprite index to draw the frame mirrored. The original uses bit 7 of
; its index byte; the counts here pass 127, so it lives in bit 15.
SPRITE_MIRROR   = $8000

; 00024E1D reaches the model record: edi = [ecx*4 + 00020654], then
; edi += [edi+4], then edi += 0x302, and 00024E33 checks the word there is
; 0x4433 - ASCII "3D". The loader keeps the same record at the end of the SG
; bank: 32 azimuth bytes at +0x02 and 16 elevation bytes at +0x22. The frame
; byte is their sum, with bit 7 selecting the mirrored half-turn.

; Blast geometry, from DOS 00024391. The radius constant there is 0x0C800000
; in its 10.22 position format, which is 50.0 map units, and the test is a
; square one - X and Y are compared independently, not by distance. The
; altitude test is `rcr al,1` on the difference against 0x32, i.e. half the
; difference against 50, so the vertical reach is 100.
BLAST_RADIUS    = $0C800000             ; 50.0 in 10.22 (00024391's 0xC800000)
BLAST_ALT       = 100
BLAST_DAMAGE    = 100

; Projectile speed and lifetime are recovered in the map, but the weapon gate
; and handler graph are not yet installed in the Falcon object system. Demo
; trigger bytes stay in the replay record; turning them into a player-specific
; projectile here would be a new mechanic, so no projectile constants are
; exposed by the active path.
;
; How far an object is still drawn - 00024C45's own bound, not a chosen one.
; The original compares the 12.20 forward depth against 0x1FFFFFFF and jumps
; to 00024E03, which returns past its caller: 512 map units. The bound is
; structural. 00024CC7 forms the ring-search key as depth << 3 and that passes
; 2^32 at exactly 512 units, so beyond it the key wraps and the search hands
; back a near ring for a far object. The compared field is OBJ_DEPTH20, the
; original's own 12.20, so the value is the original's 0x1FFFFFFF.
;
; This was OBJ_DRAW_RANGE = 992, reasoned from how far the depth march reaches
; and applied in the draw walk, where the original has no cull at all.
OBJ_DEPTH_LIMIT = $1fffffff

; Sprite scale, recovered end to end 2026-08-18. No longer a stand-in.
;
; The producer, 000251E0: walk .DTL table 4 - the cumulative depth at
; 0001AE84 - for the first entry at or beyond the object's distance, turn the
; hit into an index by subtracting 0001AE84+8, then divide 0x08000000 by table
; 0's entry there (`div [ebx+00019EE4]` at 0002520B). Table 0 is the lateral
; step and dtl0[i] is z_i/100 in the file's 10.22, so the quotient is 3200/z -
; verified across the whole table, ring 20 giving 216 against 216.1. Clamp to
; 0x7F, store NOT(value+0x80) = 127-value into [00022354].
;
; The consumer, 000253CD: that byte is an INDEX, not a multiplier. It reads
; `[eax*4 + 0001D7EC]` and adds 0001DBEC, selecting one of 128 precomputed
; scaling ramps, and the blit walks the ramp one byte per OUTPUT pixel
; subtracting each from a source coordinate. So a ramp's length is its output
; width and the sum of its bytes is the source width.
;
; Read out of the image, both exact: ramp length L[i] = 128 - i for every one
; of the 127 measurable entries, and every ramp sums to 64 source pixels. So
;
;       magnification = L[i]/64 = (128 - (127 - min(3200/z,127)))/64
;                     = (min(3200/z,127) + 1)/64  ~=  50/z
;
; capped at 2x, which is what the 0x7F clamp means and what OBJ_SCALE_MAX
; already said. This port had 56/z from an invented constant, so every sprite
; was 12% oversized. The floor is the shortest ramp, L=2 at index 126, which
; is 2/64 = 8/256; at 50/z that is z = 1600, far beyond the 992-unit march, so
; it never binds - but it is the original's number rather than a chosen one.
SCREEN_STRIDE   = SCREEN_WIDTH*2
SCREEN_WORDS    = SCREEN_WIDTH*SCREEN_HEIGHT
FRAME_BYTES     = SCREEN_WORDS*2

; TERRAIN_COLS and TERRAIN_XSTEP live in src/dsp/proto.inc, which both the
; 68030 and the DSP assembler read, so the ray count cannot drift between the
; reference renderer and the kernel it is the oracle for.

; Map geometry, shared by the renderer and the flight state. The generated
; build/original_test.s reports the same numbers as ORIGINAL_MAP_*; these are
; the ones 68030 code outside render.s can actually see.
MAP_MASK        = $03ff
MAP_SHIFT       = 10
; The supplied 1024x1024 VoxelSpace maps are periodic, and the wrap is the
; mask above: 00019359/00019362's `shld ebx,eax,0xa` pair takes ten bits of
; each coordinate and nothing bounds the coordinates themselves. There is no
; option here to set - a SEAMLESS_WORLD flag once sat at this line, unread by
; any source in the tree, and a build option that carries a behavioural choice
; is exactly what rule one forbids.


; The depth schedule is the DSP kernel's, shared by every renderer and by
; object placement - see proto.inc MARCH_*/TILE_* and the generated header's
; DEPTH_*. The old DEPTH_FAR_SHIFT died with the two-tier schedule; the
; boundaries now scale by TILE_FAR_SHIFT and TILE_FAR2_SHIFT directly.

; Drive the terrain through the DSP when it comes up, falling back to the CPU
; renderer otherwise. 0 builds the CPU-only path, which is what every capture
; in this project has been taken with and remains the oracle.
        ifnd    USE_DSP
USE_DSP         = 0
        endc
; Render the terrain with the DSP kernel's own arithmetic and tile windows,
; on the CPU. This is the diff partner for a USE_DSP capture: same schedule,
; same fixed point, same windows, so the two frames compare to the pixel.
; It is a diagnostic build, not a game mode - render_terrain remains the
; oracle for the game's own look.
        ifnd    PARITY_TILE
PARITY_TILE     = 0
        endc
; Sprite rectangles remembered per buffer for the incremental composition's
; restore pass. Overflow costs one classic backdrop frame, not correctness.
DSP_RLIST_MAX   = 32

; Bound on the VBL wait, so a VBL that never arrives degrades to a free-running
; loop instead of a hang.
VBL_WAIT_LIMIT  = 400000

; The menu text colours, from the six-bit triples 0002AA85-0002ABCC hands to
; the palette matcher, converted to RGB565 rather than quantised: the Falcon
; can have the colour the constants name. Their DOS addresses are 0002A374
; white, 375-377 the greys, 378 blue, 379 red, 37A green, 37B magenta, 37C
; orange, 37D amber. The shadow is the original's palette index 0, drawn as
; black - see the head of src/menu.s.
; These are the AUTHORED six-bit triples 0002AA85-0002AB3F asks for - not
; necessarily what the original draws. It resolves each one to the nearest
; index in the installed palette (0002B820) and draws that index, so the
; painted colour is the palette's entry, which need not be exact. Against
; the attract's np44 palette, measured: GREY_L and GREY_D land exactly,
; GREY_M becomes (1B,1B,1B), BLUE becomes (0F,2F,3F) and GREEN becomes
; (0F,3F,0F). Anything drawing into a palette-indexed surface should go
; through resource_named_colours; these direct expansions are only correct
; where the port owns the colour outright.
COL_MENU_WHITE  = $FFFF                         ; 3F,3F,3F
COL_MENU_GREY_L = $A514                         ; 28,28,28
COL_MENU_GREY_M = $738E                         ; 1C,1C,1C
COL_MENU_GREY_D = $4208                         ; 10,10,10
COL_MENU_BLUE   = $461F                         ; 10,30,3F
COL_MENU_RED    = $FA08                         ; 3F,10,10
COL_MENU_GREEN  = $47E8                         ; 10,3F,10
COL_MENU_MAGENTA = $FA1F                        ; 3F,10,3F
COL_MENU_ORANGE = $FC08                         ; 3F,20,10
COL_MENU_AMBER  = $FF08                         ; 3F,38,10
COL_MENU_SHADOW = $0000

; Mission/resource status. A missing asset is an error: the DOS build does not
; invent a map, palette, cockpit, or mission when a named resource is absent.
MISSION_STATUS_LOADED   = 1
MISSION_STATUS_ERROR    = 2
MISSION_STATUS_PARSED   = 4

; The left multi-function display, from 00007580/00015855/0001591A. The
; destination 0x37CE is byte column 18 of row 174, so pixel (72, 174); the
; row is 20 bytes written outward from its centre times four planes, and
; 0x2C rows tall. The zoom is [00019C90], captured as 0x08000000.
; 000079F0's destination is 0x37CE + [0x14C4] + [0x19CA8]: 0x37CE is row 174
; and byte column 18 of the 0x52-byte row, so PAGE x 72. [0x19CA8] is 0 for
; the left panel and 0x1A for the right - 26 bytes, 104 pixels - which is
; MFD_PANEL_STEP below. As a page x it needs PAGE_VIEW_X taken off before it
; addresses the surface; MFD_SURFACE_X is that.
MFD_X           = 72
MFD_SURFACE_X   = MFD_X-PAGE_VIEW_X
MFD_PANEL_STEP  = $1a*4
MFD_Y           = 174
MFD_W           = 80
MFD_H           = 44
MFD_HALF_W      = MFD_W/2
MFD_ZOOM        = $8000000
MFD_VIEW_COLS   = 80
; 000079F0 copies the target view from source column 0x58 into the
; 80-pixel MFD window. Target-view object sprites use the same crop.
MFD_VIEW_SURFACE_FIRST = $58
; The page row the target TERRAIN's panel row 0 is counted from. This is 162 + 2,
; and the 2 is arithmetic, not a fit. 000079F0 samples surface row 162 - 2r for
; panel row r (start 0xA2 in its 0xA22C/0xA2AC/0xA22D/0xA2AD sources, -0x200 per
; row), and a terrain span writes the half-open page rows [old, new) (the
; unrolled stores at 00006BF0 start at `ch` = old and run new - old of them). Row
; 162 - 2r lies in that span exactly when
;   old <= 162 - 2r <= new - 1   <=>   (164 - new) >> 1 <= r < (164 - old) >> 1
; (r >= ceil((163 - new) / 2) and r <= floor((162 - old) / 2)). So the span's
; first and one-past-last panel rows are (164 - page row) >> 1. The sprites,
; which draw their own rows, sample 162 - 2r directly (sprite_draw_ramped).
; Checked: 164 is the value a shift search against DEMO1 record 20's DOS surface
; found, and the one the derivation gives.
MFD_VIEW_TOP_ROW = 164

; The key array's slots (key_state / key_latch), indexed by the ST scancode the
; IKBD sends. The DOS array at 00001A70 is indexed by the PC scancode; the
; keypad and the keys below are the same physical keys.
KEY_KP7         = $67
KEY_KP8         = $68
KEY_KP9         = $69
KEY_KP4         = $6a
KEY_KP6         = $6c
KEY_KP1         = $6d
KEY_KP2         = $6e
KEY_KP3         = $6f
KEY_KP0         = $70
KEY_KPDOT       = $71
KEY_KPSTAR      = $66
KEY_A           = $1e
KEY_ESCAPE      = $01
KEY_RETURN      = $1c
KEY_TAB         = $0f
KEY_SPACE       = $39
KEY_KP5         = $6b
KEY_ALT         = $38
KEY_Q           = $10

; Field offsets. The DOS field number follows each, counting as the map does.
OBJ_SPEED       = 0     ; .l  field -1, multiplied by sin/cos of the heading
OBJ_DRAW        = 4     ; .l  field 0
OBJ_STATE       = 8     ; .l  field 1, the current state handler
OBJ_MODEL_A     = 12    ; .l  field 2
OBJ_MODEL_B     = 16    ; .l  field 3
; Positions are the original's own 10.22 (map units << 22): the map index is the
; top ten bits and the step of 000248E4 is a Q31 high dword, so nothing here is
; converted. They were 16.16 once, which lost the low six bits of every step
; and let two tanks' steering flip on an equality test 1,800 ticks in.
OBJ_X           = 20    ; .l  field 6
OBJ_Y           = 24    ; .l  field 7
OBJ_PREV_X      = 28    ; .l  field 8
OBJ_PREV_Y      = 32    ; .l  field 9
OBJ_HEADING     = 36    ; .b  byte field 0
OBJ_ACTIVE      = 37    ; .b  byte field 1
OBJ_ALTITUDE    = 38    ; .b  byte field 3
; DOS has ONE byte here, [00021B29], and every reader and writer shares it:
; 00023A8C/00023B50/00023CF0 count it as the destruction stage, 000236B5/
; 000242F6/00024843 set bit 0 on a lethal hit, and 0002439D-0002440A's blast
; does the same. The port used to keep a second byte (offset 39) for the blast
; and the states and a third reading for the weapons, so a rocket's kill never
; reached the state that was waiting for it. They are the same byte.
OBJ_DAMAGE      = 57    ; .b  00021B29, aliased to OBJ_PHASE below
OBJ_TIMER       = 40    ; .b  byte field 11, the state timer
OBJ_HEALTH      = 41    ; .b  displacement 00021F93
OBJ_PREV_ALT    = 42    ; .b  byte field 4, the previous-tick altitude
OBJ_SPRITE      = 43    ; .b  bank entry to draw; DOS reads its own at 000219A3
OBJ_DEPTH       = 44    ; .l  field 5, forward distance from the frame viewer
OBJ_LATERAL     = 48    ; .l  field 4, sideways distance from the frame viewer
; There is no separate "home" position. A second X/Y/altitude triple used to
; sit here, labelled with displacements 0002107C, 00021284 and 00021AA7 - which
; are fields 8 and 9 and byte field 4, the three above. The original keeps one
; copy: 00024860 and 00023B63 latch into it, 00023AD0 and 00023C93 revert from
; it, and 000249C7-000249E9 restores X, Y and altitude out of it. Two fields
; standing for one array meant the factory's placement and the state latch
; wrote different words and the probe read the wrong one.
OBJ_STEER_DIR   = 52    ; .b  00021EB7, steering direction latch
; Factory/state bytes retained from the DOS byte-field arrays. Keeping these
; separate matters: 00023A8C/00023CF0 use 00021B29 as a phase while the blast
; path uses its own destruction bit.
OBJ_AUX         = 53    ; .b  00021DB3, f1-derived factory byte
OBJ_FLAG        = 54    ; .b  00021F39, '*' continuation flag [00022266]
OBJ_VARIANT     = 55    ; .b  00021F57, draw/state variant
OBJ_F9          = 56    ; .b  00021F75, f9 timing mask
OBJ_PHASE       = 57    ; .b  00021B29, type-state phase
OBJ_TARGETABLE  = 58    ; .b  00021BAB, v - 0x2E when this object passed the
                        ;     targetability test THIS frame; 0 otherwise
OBJ_DESIGNATOR  = 59    ; .b  00021C2D, the designator row stored beside it

OBJ_F10         = 60    ; .l  00022028, f10 countdown/parameter
OBJ_END_CUE     = OBJ_FLAG ; 00021F39, wreckage voice-trigger gate
OBJ_HOLD        = OBJ_F10  ; 00022028, state hold countdown
OBJ_PALETTE_A   = 64    ; .l  Falcon RGB565 palette for model A bank
OBJ_PALETTE_B   = 68    ; .l  Falcon RGB565 palette for model B bank
; Past the DOS-derived fields: 58/59 were the last free bytes and 60..71 are
; OBJ_F10 and the two palette pointers, so this goes on the end.
OBJ_VIEW_BEARING = 72   ; .b  00021CAF, ~(bearing to the viewer); the angle
                        ;     00007860's target view looks along
; The launched weapons' own fields (00022B00/00022F90 write them, 000241C0 and
; 00024680 read them). DOS arrays, each 130 entries of the stated width.
OBJ_VRATE       = 76    ; .l  0002148C, field 10: rocket vertical rate, 8.24
OBJ_ALT_ACC     = 80    ; .l  00021694, field 11: rocket altitude, 8.24 - its
                        ;     top byte (00024252 reads [ecx*4 + 00021697]) is
                        ;     the altitude byte
OBJ_TARGET      = 84    ; .b  00021D31, byte field 9: the latch at launch
; The per-object shot routine [ecx*4 + 00021FB0]. 00023297 installs 00022CA1
; in every allocated slot and the type factories 000233A3/000233B3/000233DB/
; 000233F7/00023413 override it; 00023EF3 calls it through the pointer.
OBJ_FIRE        = 88    ; .l  field at 00021FB0
; The transform's results exactly as 00024B69/00024B70 store them, 12.20. The
; port's OBJ_LATERAL/OBJ_DEPTH above are these shifted down four (floor), kept
; for the readers that were written against 16.16; the ring search at
; 00024CC7 and the column divide at 00024D84 compare against tables to the
; last bit, and a depth one 16.16 unit off put a missile one ring and one
; scale step away from DOS's in the target view.
OBJ_LATERAL20   = 92    ; .l  [0002085C], 12.20
OBJ_DEPTH20     = 96    ; .l  [00020A64], 12.20
OBJ_SIZE        = 100

; The pilot roster, COMANCHE.NAM (src/screen.s loads it, src/debrief.s updates and
; saves it): 8 records of 43 bytes in the form ' |b<FD><FD><digit>|g <name>', then
; the scalars and tables below. Offsets are from the file start, DOS 00029582.
SCR_CAMPAIGN_DIGITS = $21B                      ; 00029D47 - 00029B2C, in menu_screen_text
ROSTER_BYTES        = 1450
ROSTER_STRIDE       = 43
ROSTER_PILOTS       = 8
ROSTER_NAME         = 9
ROSTER_NAME_CHARS   = $16                       ; ecx at 00028D52
ROSTER_CURRENT      = $17F                      ; 00029701 - 00029582
ROSTER_CAMPAIGNS    = $180                      ; 00029702 - 00029582
ROSTER_HEADER       = $12                       ; 00029582 - 00029570
ROSTER_PROGRESS     = $188                      ; 0002970A, 10 bytes a pilot: the mission chosen per campaign
ROSTER_SELECTED     = $1D8                      ; 0002975A, the mission chosen last
ROSTER_COUNT        = $1DA                      ; 0002975C, a dword a pilot: missions won (the ranking key)
ROSTER_SCORE        = $1FA                      ; 0002977C, a dword a pilot
ROSTER_KILLS        = $21A                      ; 0002979C, a dword a pilot
ROSTER_MISSIONS     = $23A                      ; 000297BC, 100 bytes a pilot: 10 campaigns x 10 missions won
ROSTER_CAMPAIGN_DONE = $55A                     ; 00029ADC, 10 bytes a pilot
ROSTER_RANK         = $1F                       ; 000295A1 - 00029582: where a name record takes its rank byte
