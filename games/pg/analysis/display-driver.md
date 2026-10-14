# Display driver: LIB/DRV/VESA480.DLL

Status: loaded image and export vector are measured. Exports 0, 4, 5, 8, 9 are
read from their full disassembly and confirmed by traced calls; 1 is inferred;
6, 7 and 11 are read from their prologue, clipping and bank-switch code and
their argument records confirmed by traced calls (see "Copy exports" below,
PARTIALLY RESOLVED: scaled and shadow paths not yet exercised); 2, 3, 10 and 12
are still first-pass readings of their instructions.

## Container and load

- File: `game/LIB/DRV/VESA480.DLL`, 19,028 bytes (the only file in `LIB/DRV`).
  `MZ` stub (0x80 bytes), `LX` header at `0x90`: 5 pages of 0x1000, one object
  (link base `0x10000`, virtual size `0x4054`), page data at file `0xA00`, page
  offsets are byte offsets (shift 0), 261 internal 32-bit fixups, no entry point,
  no export names or entry table, resident name `vesa480`.
- The loader is the game's own, not DOS/4GW's: the image sits at RAM
  `0x218AED` (not page aligned) in the oracle at the main menu.
- Applying the fixups at that base (`tools/re/lx_dll.py --ram
  work/qemu_out/pg_menu16.bin`) reproduces the loaded bytes exactly everywhere
  except `0x430..0xBFF` (data written at run time, 1,098 bytes) and 14 bytes
  elsewhere; all code pages match.

## Export vector

The first 52 bytes of the image are 13 link-time addresses. The game copies them,
rebased, into 13 consecutive globals (object-2 offset `0x55B8 + 4*i`, RAM
`0x1E55B8 + 4*i`); all nine of those called indirectly in the decoded code were
checked against the dump. Calls in `PANZER.EXE` through each global:

| i | Global | Image offset | Calls in the EXE | First-pass reading (instructions only) |
|---:|---|---|---:|---|
| 0 | `0x55B8` | `0x10DC` | 1 | **`GetModeInfo() -> ptr`**: returns `base + 0x10C0`, a 28-byte descriptor `{640, 480, 1, 256, 1, 1, 0}` (width, height, then 1, 256, 1, 1, 0 unlabelled) |
| 1 | `0x55BC` | `0x3E7B` | 1 | **`SetMode(desc)`** (inferred): the one observed call passed the descriptor from export 0; the code uses `int 10h` and DPMI `int 31h` and clears a bank cache (`[0x10434] = 0xFFFF`) |
| 2 | `0x55C0` | `0x4044` | 1 | restore text mode: `mov eax,3; int 10h` |
| 3 | `0x55C4` | `0x113C` | (not in decoded code) | `rep stos` fill with an `int 10h` path |
| 4 | `0x55C8` | `0x10EB` | (none) | **wait until in vertical retrace**: picks the CRTC status port (`0x3BA`/`0x3DA`) from `0x3CC` bit 0, loops until bit 3 is set |
| 5 | `0x55CC` | `0x1111` | 5 | **`WaitVsync()`**: waits until bit 3 clears, then until it sets (the start of the next retrace) |
| 6 | `0x55D0` | `0x1263` | 7 | **`BlitToScreen(bmp*, dx0, dy0, dx1, dy1)`**: whole bitmap to a screen rectangle (see below) |
| 7 | `0x55D4` | `0x37B7` | 2 | **`ReadFromScreen(bmp*, sx0, sy0, sx1, sy1)`**: screen rectangle into a bitmap (see below) |
| 8 | `0x55D8` | `0x3D4A` | 1 | **`GetPaletteEntry(index, dest*)`**, cdecl: `out 0x3C7, index`, then three `insb` from `0x3C9` (6-bit VGA components) |
| 9 | `0x55DC` | `0x3D81` | 26 | **`SetPaletteEntry(index, rgb*)`**, cdecl: `out 0x3C8, index`, then three `outsb` to `0x3C9`; interrupts masked inside |
| 10 | `0x55E0` | `0x3DB6` | (none) | invalidates the bank cache (`[0x10434]` and `[0x10430]` = `0xFFFF`) |
| 11 | `0x55E4` | `0x24E0` | 5 | **`BlitRectToScreen(rect*, dx0, dy0, dx1, dy1)`**: sub-rectangle of a bitmap to a screen rectangle (see below) |
| 12 | `0x55E8` | `0x3DE0` | (none) | 640-iteration (`ecx = 0x27F`) loop with `int 10h` |

Call counts are the decoded call sites that name the global directly; callers that
copy the pointer first are not counted. The driver talks to the card through BIOS
VESA calls (`int 10h`) and DPMI (`int 31h`) from protected mode, so its behaviour
under the oracle depends on QEMU's VGA BIOS; "640x480" in the name matches the
640x480 frames seen in the oracle.

## Observed calls (oracle, 2026-10-05)

`work/probe_driver_trace.py` set breakpoints on the 13 entry points
(`work/re/driver_trace.json`, at most 30 hits per export; the load address
`0x218AED` was the same in the traced run). Hits in the 45 s run: exports 0 and 1
once each (t = 3.6 s, from `0x17D548`/`0x17D551`), exports 5, 6, 7, 8, 9, 11 at
least 30 times; exports 2, 3, 4, 10 and 12 were not called.

- **Stack calling convention:** the exports are cdecl (`[ebp+8]`, `[ebp+0xC]`),
  not the compiler's register convention. Palette write at t = 3.8 s was called
  for index 0, 1, 2, ... with `rgb* = 0x1EC0C4, +3, +6, ...` from the loop at
  `0x17D7CD`: a 256-entry palette upload from a buffer of 3-byte entries.
  Palette read at t = 9.98 s: index 0, 0x10, 0x20 ... with destination `0x1E5B31,
  +0x30, ...`, from `0x1CA5CE` (the cadence of a fade).
- **Copy exports** (6, 7, 11): arguments are a pointer then four values: export 11
  `(0x1EC61C, 0, 0, 0x27F, 0x1DF)` is a 640x480 rectangle on a `0x14`-byte
  descriptor of the array at `0x1EC61C` (the same `imul edx,0x14` indexing as the
  decoded callers); exports 6 and 7 take `0x1EF030` or `0x1EF01C` (the two 0x4000-
  byte buffers allocated at start) with small values (0xD,0xE; 0x1D,0x16). The
  meaning of the four values is **not established**.
- **Sync:** export 5 (`WaitVsync`) was first hit at t = 3.64 s with a return
  address inside the driver (`0x21CA57`, so the driver calls it itself, probably from
  `SetMode`) and then in a tight sequence from 10.03 s with game return addresses.

## Copy exports 6, 7, 11 (2026-10-06; `work/re/driver_trace2.json`)

All three are cdecl, take the same four trailing destination coordinates and
share one clipping prologue. Layouts below are from the disassembly
(`+0x24E0`, `+0x1263`, `+0x37B7`) and match the 100+ traced calls, where the
records were dumped from guest RAM at each entry.

- **Bitmap descriptor** (5 dwords, `0x14` bytes; the same record the decoded
  callers index with `imul 0x14`): `[0]` pixel base pointer, `[4]` max X
  (width-1), `[8]` max Y (height-1), `[0xC]` unknown (copied to a local, unused
  on the traced paths), `[0x10]` optional shadow-buffer pointer or 0. Traced:
  the screen-sized back buffer is `{p, 0x27F, 0x1DF, 0, 0}`; panel strips are
  `{p, 0x3B, 0x1DF, 0, 0}`, `{p, 4, 0x1DF, 0, 0}`, `{p, 0x36, 0x1DF, 0, 0}`.
  Pixels are 8-bit, rows packed at stride `maxX+1`.
- **Export 11, `BlitRectToScreen(rect*, dx0, dy0, dx1, dy1)`:** `rect` is a
  5-dword record `{desc*, sx0, sy0, sx1, sy1}` naming the source sub-rectangle
  (clipped to `0..maxX`, `0..maxY`; a negative or beyond-range edge rejects the
  call). Destination edges clip to `0..0x27F` / `0..0x1DF`; a call wholly
  outside returns without drawing. Traced calls are 1:1 copies (source and
  destination spans equal), e.g. `(rect {back,0,0,0x3B,0x1DF}, 0xFF,0,0x13A,0x1DF)`
  panel strips and `(rect {back,0x140,0,0x145,0x1DF}, 0x140,0,0x145,0x1DF)` column
  repairs.
- **Export 6, `BlitToScreen(bmp*, dx0, dy0, dx1, dy1)`:** same as 11 with the
  source rectangle fixed to the whole bitmap (`0..maxX`, `0..maxY`). Traced with
  the `0x1EF01C`/`0x1EF030`-class buffers and small cursor-sized rectangles
  (`0x13F,0xEF,0x14D,0xFE`: 15 x 16).
- **Export 7, `ReadFromScreen(bmp*, sx0, sy0, sx1, sy1)`:** the inverse of 6; the
  screen rectangle is read into the whole bitmap (`xchg edi,esi` before the
  copy). Traced with the same rectangles as 6 (read-then-draw pairs: a
  save-under for a 15 x 16 object such as the pointer).
- **Scaling:** if the destination span differs from the source span in either
  axis, the code takes a 16.16 fixed-point stretch path (`idiv` ratio at
  `+0x2691`/`+0x13C0`/`+0x3876`); no traced call took it. `TBD`.
- **Shadow copy:** when descriptor `[0x10]` is nonzero the 1:1 path compares each
  source word with the same position in the shadow (`[esi+ebx]`, `ebx = [0x10] -
  [0]`) and writes only changed words to the screen and shadow (a dirty-write
  filter); with 0 it is a plain `rep movs`. All traced descriptors had 0. `TBD`.
- **Bank mechanics (not part of the port contract):** the 64 KB window is chosen
  per row from two tables (`[0x107FC + 2*y]` bank, `[0x1043C + 2*y]` offset,
  granularity step `[0x1403C]`) through VESA `int 10h` `AX=4F05h`; `[0x10430]` is
  the cached write bank, `[0x10434]` the cached read bank (export 7 sets
  both windows, BX=0 and BX=1, and resets `[0x10434]` to `0xFFFF` otherwise);
  `[0x10438]` is a re-entrancy counter with a second state set at `+0x10E3C`.
  These are hardware-adapter details; the observable behaviour is the clipped
  screen-space copy above.

**DOS fixtures (RESOLVED for the measured domain).** `work/probe_draw_contracts.py`
(`drive_menu.py --draw-contracts`) breaks on exports 6, 7 and 11 in the connected
Poland route, records the arguments, descriptor and source pixels, and reads the
screen before and after from the emulated VGA's linear framebuffer (PCI BAR0,
`0xFD000000`; verified byte-consistent with `screendump` through the palette).
The retained 16 witnesses (`tests/fixtures/dos-draw.json`, 6 x export 6, 5 x
export 7, 5 x export 11, from `work/qemu_out/draw-1`) are all unclipped, equal-span,
shadow-free copies and in every one the output equals the source bytes exactly
(15 x 16 pointer rectangles, a full 640 x 480 frame, strips up to 241 x 98).
`web/reference/draw.mjs` reproduces all 16 (`node tests/draw-reference.mjs`) and
throws `Unproven` for clipping, rejection, stretch and shadow. No m68k
implementation yet.

`src/common/draw.s` (`gfx_copy_rect`, 124 code bytes, `-m68000`) is the native
counterpart for the same measured domain: one routine for all three exports
(direction flag), refusing shadow, clipped, out-of-range and stretched requests
with `-1`. `python3 tools/check-native-draw.py --out build/n-draw` runs it in
Hatari (Falcon030, 4 MB) against the same 16 DOS fixtures: 337,430 output bytes
equal. It works on a chunky 640 x 480 memory buffer; the Falcon's 8-bit Videl
mode is bitplane-interleaved, so the chunky-to-planar and palette path is not
implemented or measured.

Port consequence: the Falcon draw layer implements these three as clipped
rectangle copies between a bitmap and the 640 x 480 8-bit screen (Videl). The
stretch and shadow paths stay `Unproven` until a DOS fixture exercises them;
no supported path may rely on them.

## Consequences for the port

- **Not game code, not in the EXE:** every draw in a route goes through exports
  6, 7 and 11 (copy to the banked frame buffer) and 9 (palette). The port needs
  its own equivalent of this layer (a chunky-to-planar or Videl path on the
  Falcon); it does not translate the driver's `int 10h` and DPMI calls.
- **Contract surface:** the 13-entry vector is the boundary to specify and test
  (arguments, bank/cache state in `[0x10430]`, `[0x10434]`, the palette format).
  Fixtures can be captured by tracing calls to `0x1E55B8 + 4*i` in the oracle.
- **Hardware adapter:** per the method, a hardware adapter has no DOS function ID
  and is a target-only artefact; the game-side callers (about 49 sites) are the
  ported functions.

## Open

1. Trace the arguments of exports 2, 3, 10, 12 (never called on the route); capture a DOS fixture (bitmap bytes in, screen bytes out) for exports 6/7/11, including a scaled and a shadow-buffer call if the game ever makes one.
2. Identify `[0x10430]` and `[0x10434]` (a bank number and a cache flag?).
3. Role of `EXE/A32GFX.DLL` (45,056 bytes, `LX`-tagged, Miles Design copyright text):
   not seen to be loaded here; do not assume it is the display driver.
