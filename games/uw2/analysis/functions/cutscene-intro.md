# UW2 intro cutscene function records

Updated 2026-08-25. These are function-level records for the first playable
browser milestone. The authoritative DOS image is
`work/extracted/D3/UW2.EXE`, SHA-256
`b07d9fde7bfb8a44e0c75388ad1bbbcd99207841f056f711a78ea51af90ea120`.
The ranges below are the byte ranges in that recovered, byte-exact image and
the reassembled listing; they are not instruction-to-instruction translation
units.

The browser counterpart is required before a function enters this milestone's
supported path. The complete recovered DOS inventory remains authoritative and
continues separately for functions not needed here.

The browser's physical keyboard and pointer events are not DOS game input by
themselves. Any supported input must pass through an emulated DOS driver/I/O
contract and then the recovered consumer. The canvas runtime exposes no
browser controls or diagnostic UI. Graphics and sound remain the explicit
target-mechanism exceptions, with their logical contracts recorded separately.

This record does not claim a Falcon/m68k implementation. Any target routine
must first declare the exact CPU and toolchain, assemble with that CPU
restriction, retain the source/build/listing evidence, and pass the same
contract fixtures in a 68030 emulator or on the Falcon. Until then, a
hand-written m68k snippet is **Illustrative** only; it is not a counterpart and
must not be marked **Ported** or **Verified**. The JavaScript implementation
helps expose and test the function contract, but cannot establish m68k
instruction legality or target execution.

## `cutscene_chunk_filename`

| Field | Record |
|---|---|
| DOS identity | `UW2.EXE` offset `0x811FC`, range `0x811FC..0x8124E` inclusive; `FUN@0x811FC` |
| Purpose | Fill the `CUTS\csXXX.nXX` template using the scene and chunk parameters. The scene uses three octal digits; the chunk uses two. |
| Inputs | destination template buffer in `SI`; scene/ cutscene number at `SS:BP+8`; chunk number at `SS:BP+0xA` |
| Output | `AX = SI`, with ASCII digits written into the template at offsets 7–9 and 0xC–0xD |
| Side effects | Writes only the caller-provided filename buffer. The octal grouping is observable and must not be changed to decimal. |
| Evidence | Reassembled bytes at the range above; shipped `CSxxx.Nxx` filenames; the live N00 fixture loads `N12`, `N10`, and `N13` from decimal values 10, 8, and 11. |
| Browser counterpart | None in the canvas runtime; the connected source filenames are explicit in `browser/uw2-game.js`. |
| Status | **Verified DOS evidence; not a retained browser helper.** |

### Difference ledger

- **Grounded / none:** same three-bit grouping and zero padding; no logical
  difference is claimed.
- **Target artefact:** the current canvas runtime retains no filename-builder
  counterpart; its four connected DOS paths are explicit and are normalized by
  the in-memory file boundary before opening.
- **Unproven:** none for the recovered digit construction; the broader set of
  callers that may pass scene/chunk values remains outside this slice.

## `cutscene_run`

| Field | Record |
|---|---|
| DOS identity | `UW2.EXE` offset `0x828E3`, range `0x828E3..0x82B34` inclusive; `FUN@0x828E3` |
| Purpose | Open a `CSxxx.Nxx` chunk, initialize the EMS/page-frame state, read the 0x400-byte LPF header/palette, stream records, and drive the cutscene surface/side effects. |
| Inputs | cutscene/chunk state in `SI` and four display/clip words at `SS:BP+8..+0xE`; exact caller-wide meaning of the four words is not yet complete. |
| Output | DOS status/last display result in `AX`; writes EMS state, palette staging, frame counters, and the VGA surface through callees. |
| Side effects | EMS bank mapping, file handle use, VGA palette load, clipping/pan state, frame timing and sound/text hooks. |
| Evidence | Reassembled range, `work/symbols.py`, DOS/QEMU intro capture, LPF directory measurements, and deterministic decoding of the connected intro files. |
| Browser counterpart | `browser/uw2-cutscene.js`: `parseLPF`, `decodeRecord`, `decodeFrames`; `browser/uw2-game.js`: `render`; `browser/uw2-fs.js`: virtual `open/read/seek/tell/close`. |
| Status | **Ported/Verified at the logical frame boundary** for `CS000.N01`, `CS000.N12`, and `CS000.N02`; full EMS scheduling, VGA register timing, speech, and sound are **Unproven**. |

### Difference ledger

- **Grounded / preserved:** LPF page directory order, record sizes, 320×200
  indexed framebuffer, persistent delta state, zero-length repeat frames, and
  palette bytes. The analysis fixtures record the connected source/frame hashes.
- **Target artefact:** resident `Uint8Array` records replace DOS EMS page
  mapping; the virtual DOS filesystem replaces DOS handles; the canvas replaces
  VGA memory; `paletteToRgb565`/`frameToRgb565` produces the selected Falcon
  chunky RGB565 display representation.
- **Target artefact / not hidden:** browser scheduling uses a deterministic
  180–240 ms presentation cadence, not a claim about the DOS timer, game-flow tick,
  monitor refresh, or VBL cadence. The browser scheduler must be replaced or
  driven by captured DOS timer events before this slice can claim timing parity.
- **Unproven:** the four unbalanced LPF pages outside the connected fixtures,
  every N00 visual command, speech VOC timing, and exact DOS palette-register
  update ordering.

## `cutscene_play`

| Field | Record |
|---|---|
| DOS identity | `UW2.EXE` offset `0x82B35`, range `0x82B35..0x83024` inclusive; `FUN@0x82B35` |
| Purpose | Select and orchestrate cutscene IDs, display regions, chunk/script progression, input/exit behavior, and related sound/text operations. The recovered call sites use IDs 0, 1, 2, and 9; ID 9 is the game-loop exit call. |
| Inputs | cutscene ID in `SS:BP+6`; global cutscene and viewport state. |
| Output | DOS status/control flow; the ID 9 path returns to the game loop boundary. |
| Side effects | Sets `[0x5CE4]`, chooses the full or narrowed display region, calls chunk/background work, waits for input/timing, and invokes text/sound paths. |
| Evidence | Reassembled range, `work/symbols.py`, `analysis/qemu-boot.md`, and the N00 script parse. The browser does not infer unobserved command semantics from a screenshot. |
| Browser counterpart | `browser/uw2-game.js`: `makePhase`, `advance`, and the connected canvas display phase list. |
| Status | **Ported for the verified intro attract slice**; the full selector/script command set, text, audio, input skip rules, and exact exit semantics remain **Unproven**. |

### Difference ledger

- **Grounded / preserved:** the browser loads the four connected DOS source
  files through the in-memory file boundary and presents their verified intro
  assets in a repeatable canvas loop.
- **Target artefact:** the browser uses a canvas presentation scheduler for the
  connected display fixture; no browser key changes its phase or frame state.
- **Target artefact:** phase cadence and loop transition are explicit browser
  state, not an invisible compatibility layer.
- **Unproven:** N00 command effects, all text/speech/audio effects, exact waits,
  and the real main-menu transition. Those functions/commands remain in the DOS
  inventory with status `Unproven` until their behavior is captured.

## `cutscene_load_lback`

| Field | Record |
|---|---|
| DOS identity | `UW2.EXE` offset `0x83150`, range `0x83150..0x8338F` inclusive; `FUN@0x83150` |
| Purpose | Build `CUTS\lbackNNN.byt`, load the 64,000-byte indexed background, pan the VGA display, narrow the clip rectangle for the visible strip, then perform the full-screen blit. |
| Inputs | display pan/position words at `SS:BP+6` and `SS:BP+8`, background number at `SS:BP+0xA`; current global display state at `[0x1072]`, `[0x5CE8]`, `[0x5CEA]`. |
| Output | `AX` is the DOS load/blit result; the VGA framebuffer and clip/pan registers are changed. |
| Side effects | File I/O, VGA CRTC/attribute-controller pan through `0x4A7F`, clip flag `[0x0DC4]`, and full-screen indexed blit. |
| Evidence | Reassembled range, `work/symbols.py`, `analysis/ghidra.md` §30, `LBACK000.BYT` size/hash, and the captured exterior frame. |
| Browser counterpart | `browser/uw2-cutscene.js`: `readLback`; `browser/uw2-game.js`: the explicit `LBACK000.BYT` phase, rendered with `CS000.N02`'s palette. |
| Status | **Verified** for filename, exact 64,000-byte load, and indexed pixels against the analysis fixture; VGA pan/clip/blit timing is **Target artefact/Unproven**. |

### Difference ledger

- **Grounded / preserved:** octal filename, exact 320×200 byte count, indexed
  pixel order, source hash and background pixel hash.
- **Target artefact:** no VGA hardware pan or clip flag exists in the browser;
  the background is drawn as a full canvas and the target Falcon display path
  performs the RGB565 conversion.
- **Unproven:** equality of the DOS VGA page after pan/clip side effects and
  the exact background palette-selection sequence outside this captured intro.

## Milestone acceptance

The page is accepted for this slice only when all of the following remain true:

1. `python3 work/cutscene_export.py --check` passes as the analysis oracle.
2. The browser DOM contains only the 320×200 game canvas; no fixture or status
   surface is loaded.
3. The game canvas advances through `CS000.N01`, `CS000.N12`, `CS000.N02`, and
   `LBACK000.BYT`, then loops.
4. Browser key events enter the emulated BIOS queue and do not change the
   canvas state without a recovered DOS consumer.
5. Functions outside this slice remain documented in the complete DOS
   inventory and are not presented as already ported.
