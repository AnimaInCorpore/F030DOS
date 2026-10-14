# Rendering path: from game state to the screen

Status: the screen-output boundary is measured; the code that draws the tactical
map into the back buffer is `TBD` (not yet located). Nothing here is ported.

## Measured: who calls the display driver (2026-10-06)

Return addresses of every traced call to the VESA480.DLL copy exports during
the Poland route (`work/qemu_out/draw-1/route.json` and
`work/re/driver_trace.json`), mapped to the recovered inventory
(`work/re/functions.txt`; `runtime = vaddr + 0x16D000`). Only six call sites in
four functions reach the driver, which is the whole screen-output boundary of
this route:

| Function | Export | Call site (runtime) | Observed behaviour |
|---|---|---|---|
| `sub_00049549` | 7, then 6 | `0x1B6707`, `0x1B67B8` | read a 15 x 16 screen rectangle into a buffer, then write the pointer image: the mouse-pointer save-under / draw pair (also at the other buffer pair, `0x1EF01C`/`0x1EF030`) |
| `sub_000497C9` | 6 | `0x1B6810` | whole 640 x 480 frame to the screen (once, at 16 s: a full-frame present) |
| `sub_00049F86` | 6 | `0x1B7456` | bitmap to screen (once) |
| `sub_0004A485` | 11 | `0x1B74BF`, `0x1B7523`, `0x1B7A47` | rectangle of the back buffer descriptor (`{0x21CB5D, 0x27F, 0x1DF}`) or a panel strip to the same screen position: dirty-rectangle flush of the back buffer and the side-panel strips |

So the game composes into memory bitmaps (the 640 x 480 back buffer plus panel
strips and cursor buffers) and these functions copy rectangles to the screen.
Everything drawn on the tactical map (terrain, hexes, units, the text bar) is
written into those bitmaps by code that does **not** call the driver, and that
code is still unlocated.

## Measured: the bitmaps and the static-frame compositor (2026-10-06)

`work/probe_writers.py` (`drive_menu.py --writers`, run `work/qemu_out/writers-6`)
puts write watchpoints on eight pixels of the back-buffer bitmap from the
`axis_turn` checkpoint and records the writer's EIP, registers and EBP chain.
Result for the tactical screen (t = 38 to 44 s, 1,680 stops): every write to
those pixels comes from `sub_00058EB8` (the row-copy loop, `0x1C5F38..0x1C5F64`)
called by `sub_00058AB4`, called from `sub_00014BF6` at its return sites
`0x181C2D`, `0x181C53`, `0x181C9F` (three of four calls), about 280 stops a
second: the static frame is re-composed continuously.

- **`sub_00014BF6`** makes four calls to `sub_00058AB4`, each pushing a rectangle
  record, a source pointer (`[0x178F4]`, `[0x1790C]`, `[0x178F8]`, `[0x1791C]`)
  and zeros; it then makes four more calls (one per record index) whose purpose is
  `TBD`. The record indices are bytes `[0x28EEA]=4`, `[0x28EE6]=3`,
  `[0x28EE7]=2`, `[0xCCBC]=1` at the tactical screen.
- **The `0xC61C` array holds rectangle records, not bitmap descriptors**:
  five dwords `{descriptor*, x0, y0, x1, y1}` (the `rect` argument of driver
  export 11). Records 1 to 4 are the bottom strip (y 0x1BE..0x1DF), the left strip
  (x 0..0x13), the top bar (y 0..0x13) and the right panel (x 0x23F..0x27F) of
  the back-buffer descriptor `0x1EC3C4`: the border and side-panel art. Record 5
  is `{0x1EC3D8, 0, 0, 0x22A, 0x1A9}`.
- **Descriptors at the tactical screen:** `0x1EC3C4` is the 640 x 480 back buffer
  (pixels `0x21CB5D`); `0x1EC3D8` is a **555 x 426** bitmap (`maxX = 0x22A`,
  `maxY = 0x1A9`; pixels `0x277E90`): the **map view**; `0x1EC3EC` is 16 x 16
  (pixels `0x218934`, pointer-sized).
- **The map-view bitmap is the displayed map (RESOLVED, measured).** At every
  settled capture (`work/qemu_out/settled-1`: tactical at 43 s, then 50 s and
  58 s, all identical) it equals the screen at offset (20, 20) in 236,355 of
  236,430 pixels; the 75 differing pixels are exactly the 15 x 16 mouse pointer
  (bitmap x 299..313, y 224..239). It is all zero until the `axis_turn`
  checkpoint (34 s) and complete by 43 s in an unobserved run; so it is the
  intermediate the screen is copied from. (An earlier version of this note
  claimed it did not match the screen; that came from using 556 x 427 instead of
  the correct 555 x 426.)

## Measured: who draws the map view (2026-10-06)

`drive_menu.py --writers map` (route `poland-settled.json`, run
`work/qemu_out/writers-map-4`, 4,922 stops) watches three map-view pixels. The
watchpoints slow the guest, so the whole map is drawn around 40 to 45 s instead
of before 43 s. Sample values changed at 40.5 s (unit pixel), 41.8 s (forest) and
45.4 s (terrain), each written by the row-copy loop `sub_00058EB8` through
`sub_00058AB4` called from **`sub_00010A64`**. Writers seen, with call chains:

| Writer chain | Stops | Reading |
|---|---:|---|
| `sub_00058EB8` <- `sub_00058AB4` <- `sub_00010A64` | 2,347 | opaque shape draw, map view renderer |
| `sub_00059476` <- `sub_00058F9E` <- `sub_00010A64` | 1,626 | second draw primitive of the renderer (masked or transparent: `TBD`) |
| `sub_0005C5EB` <- `sub_0005C77E` <- `sub_0004736D` | 522 | clipped rectangle fill (clears the view before the map is drawn) |
| `sub_00058EB8` <- `sub_00058AB4` <- `sub_000595A9` <- `sub_00014CD9` | 124 | a later partial redraw; changed the unit sample at 52.5 s |
| `sub_0005A948` <- `sub_00048174` | 96 | `TBD` |

- **`sub_00010A64`** (`0x44E` bytes) is the map-view renderer. It calls the two
  shape primitives eleven times (`sub_00058AB4` x5, `sub_00058F9E` x2) and
  `sub_000485BE` x3, `sub_00010EB2` x2 (`TBD`).
- **`sub_00058AB4`** is a clipped shape draw: `(clip, shape, index, x, y)` as
  stack arguments. `clip` is a rectangle record `{descriptor*, x0, y0, x1, y1}`;
  `shape` is a loaded shape-file image whose table of 8-byte entries starts at
  `+8` (`[shape + 8 + 8*index]` is the sprite's offset); each sprite has a header
  with bounds at `+8..+0x14` and data at `+0x18`. The static frame compositor
  `sub_00014BF6` uses it for the border and side-panel art
  (`[0x178F4]`, `[0x1790C]`, `[0x178F8]`, `[0x1791C]` are loaded shape images,
  index `[0x28EEF]` and zeros). The in-sprite pixel encoding is `TBD`.

## Consequence for the port

The display layer is small and now has a measured contract (display-driver.md)
and a native counterpart (`gfx_copy_rect`, `c2p.s`). Their game-side callers
above still need function records and fixtures. The large unknown is the
composition layer.

## Route to a playable slice (not started beyond the items marked done)

1. **Done:** map loader state, geometry, RNG, unit classes, copy exports, a
   Falcon video path demo (docs/PORTING-PLAN.md).
2. Locate the composition code (done to the primitive level: the static-frame
   compositor is `sub_00014BF6`, the map-view renderer `sub_00010A64`, the shape
   primitives `sub_00058AB4` and `sub_00058F9E`; both primitives and their row
   copies `sub_00058EB8`/`sub_00059476` have function records, 32 DOS witnesses
   (`tests/fixtures/dos-shape.*`, 23 clipped) and a passing x86-translated
   native implementation (`analysis/x86-translation.md`); the shape pixel
   encoding as a documented format is next; the compositor `sub_00014BF6` also
   has a record, a DOS witness and a passing translated gate with its present
   call as a recorded boundary). A write
   trace over one tactical frame (an x86 execution trace of the oracle, or
   breakpoints on the descriptors' pixel base) gives the writer set; the
   candidates are the sprite, tile and text drawers. Record each with a
   `METHOD.md` section 4.2 function record.
3. Resource formats for what they draw: the shape format first (header, sprite
   table, pixel encoding), measured against the DOS output of `sub_00058AB4`;
   then TACMAP (`.SHP`/`.TGF`) terrain and unit sprites, fonts, the panel.
4. Port the composition of one static tactical frame from the loaded Poland
   state and compare the whole frame with the DOS frame
   (`tests/fixtures/dos-frame-poland_tactical.*`) byte for byte.
5. Input: pointer and hex selection (the cursor functions above, the timer
   callback, mouse state).
6. Game rules for one turn: movement, combat, turn completion, then the AI
   turn; each with DOS fixtures. Campaign and other scenarios stay out of scope
   until the slice is closed.
7. Replace the chunky-to-planar demo conversion with a fast one and measure the
   frame time on the target.

Items 2 to 6 are the bulk of the work. None may be claimed as supported before
its differences against the DOS capture are measured.
