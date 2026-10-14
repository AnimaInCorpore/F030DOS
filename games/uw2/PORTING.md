# Getting UW2 ready to port

*Status reviewed 2026-10-10 against the existing source/evidence records;
this is not a new acceptance run. `AGENTS.md` §Findings log records the
experiments. Phase numbering is `../F030Method/METHOD.md`'s.*

The current port remains the browser intro/display slice plus a separately
checked native RGB565 seam. Its host/target page fixture passes; connected
keyboard/character consumption, game-loop/3D gameplay and physical Falcon
scanout remain open. The original DOS game's playable route and exact executable
rebuild do not establish browser/native gameplay. See [README.md](README.md)
for the short status and the fidelity boundaries below for evidence scope.

## Where this project actually is

UW2 has extensive data recovery and a completed byte-level executable audit;
semantic recovery and port integration remain open. The old `Next steps` list obscured that shape
by mixing twenty completed findings into five open items.

| | state |
|---|---|
| Distribution unwrapped | by hand, **no script, no CRC**, 305 derived files committed because they are not reproducible |
| `UW2.EXE` model | RESOLVED — header, relocations, entry `0x11520`, DGROUP `0x68E80`, Ghidra skew `0xD200`, `FBOV` pool at `0x71B80` |
| `UW2.EXE` **byte-exact rebuild** | **RESOLVED** — one-pass ratchet plus whole-file audit, SHA-256 match |
| Data formats | `STRINGS.PAK`, `T64.TR` rebuild **byte-identical**; `.ARK`/LZSS 200/200 decode, 9/200 re-encode; standard `.GR` archives **rebuild 34/34 byte-identically**, including type 8 **736/736**; LPF/ANIM container and intro frame payload **resolved**; `PANELS.GR` record 3 open; `VOIC*`/`SDFX*` untouched |
| Understanding | The final byte-level audit identifies 3,445 entries (below); semantic function/VM recovery remains incomplete. Earlier naming/orphan tallies belong to their historical analysis runs, not a current port-completion percentage |
| Dynamic oracle | WORKS — boots, drives through character creation into 3D gameplay |
| Port | **canvas-only browser intro/display slice plus an assembled/Hatari-verified Falcon RGB565 seam** — `src/common/indexed_surface.h`, `src/target/falcon/present.s`, `work/cutscene_export.py`, `browser/`; browser keyboard events now terminate at the emulated BIOS `INT 16h` queue, while the recovered keyboard consumer, character consumer, game loop integration and physical Falcon scanout are not yet integrated |

## The phase-2 gate — complete

**Run the reassembly ratchet on `UW2.EXE`.** **DONE 2026-08-24** — it was
filed last (old item 5) and was the phase-2 gate: METHOD.md §0 is explicit that without a byte-exact
rebuild *"you do not have a disassembly, you have a plausible listing — and a
plausible listing is worse than none, because it looks like evidence."*

Before the ratchet, everything this project had built on the code side rested on an unproven
listing: the 111-slot threaded-VM table at `0x54FD4`, the 101 NEXT sequences,
the handler census that concluded `0x065C` is a fixed-point engine, the call
graph, the 17 verified names. Each was cross-checked in its own way and several
were confirmed live — that is real evidence and it is not being dismissed. But
it is *per-finding* evidence, and the ratchet is the *whole-image* one. A single
wrong instruction length silently corrupts every byte after it and still looks
like a listing.

Cost is low and known, because UW1 already paid it. Same compiler, same linker,
same overlay model, so `../F030Underworld/work/reasm/uwreasm.py`'s two hard
parts port unchanged: the hand-built ModRM macros for Borland's direction-bit
encodings (7.6 % of UW1's code — NASM will not emit `8b ec` for `mov bp,sp`)
and `$`-relative branch emission (so a flat `nasm -f bin` rebuild of a segmented
program is exact). UW1 reached **99.98 %** real mnemonics on 561,744 B in four
passes, ~25 s. UW2 is 675,968 B of the same shape.

Two things the ratchet must carry from day one, not retrofitted:

- **Per-instruction comparison at each line's intended offset** using `nasm -l`.
  A whole-file diff reports one short instruction as 100,000 wrong bytes. POR's
  first ratchet demoted everything after the first mismatch and reported a
  byte-exact rebuild at 1 % real instructions — technically passing, actually
  meaningless.
- **A known-data guard**, UW1's `known_data()` shape: MZ header + relocation
  table, DGROUP `0x68E80..0x71B80`, the overlay-manager data segment
  `0x669A0..0x670B0`, the thunk block `0x670E0..0x68E80`, the `exeinfo` segment
  table `0x66B40..0x670B0`, and the typed embedded/FBOV data ranges. The
  ratchet proves *re-encodability*; the guard proves *code-ness*. They are
  orthogonal — data that happens to decode re-encodes byte-exact and inflates
  the score honestly-looking (F29 measured a sweep reaching 66.2 % coverage by
  eating six known-data regions).

By-products, free: the `0xD200` skew and the relocation model get re-verified
mechanically, and the indirect-call/jump-table targets become an explicit seed
set. The final audit leaves no unclassified byte; the remaining port work is
semantic recovery rather than a hidden disassembly gap.

**Gate: phase 2 and the mechanical phase-3 map are complete.** The UW2 ratchet
rebuilds the full file byte-identically; see `analysis/reassembly.md`. The
final descent has 157,847 byte-exact mnemonic instructions, 0 forced `db`
fallbacks, and 3,445 function entries. The automated whole-file audit
classifies all 675,968 bytes as either decoded instructions or explicit
data/padding, with 0 unclassified bytes and 0 code/guard overlaps. Remaining
work is semantic function/VM recovery and port integration, not byte-level
reachability.

## The critical path to a first pixel

METHOD.md §0 permits presentation to run ahead of phase 3 *once a data format is
verified*. Three of UW2's data formats are verified to byte-exact rebuild
already, and the type-8 decoder is validated across all 736 records, so this
can proceed now that the ratchet gate is closed:

**`.GR` record type `0x08` — RESOLVED for decoding and record-level encoding.** It is nibble-packed,
RLE-compressed 16-colour data through the record-selected auxiliary palette;
`work/gr8_decode.py` decodes 736/736 without overruns, and
`work/gr8_encode.py` re-encodes 736/736 byte-identically. The standard archive
emitter is now proven by `work/rebuild.py --gr-rebuild`:
all 34 ordinary `.GR` archives rebuild byte-identically. `PANELS.GR` record 3
remains open, but it does not block a first-pixel renderer.

What is already ruled out and must not be re-walked:

- the type byte is dispatched by no `cmp al,N` (no 96-byte window compares
  against 4, 8 and `0x0a`);
- the decoder is not on the load path — `gr_record_read` reads records raw and
  only checks the byte count;
- it is not one of the four bit-depth doors at `BX=0x04/06/08/0A`; those are
  keyed on a *bitmap depth code* (record byte 0, values 0–5), not the `.GR`
  type byte, and none produces type 8's ~2 bpp packing (256 pixels in 65 bytes).

The decoded output is `w*h`, `w*h+1`, or `w*h+2` bytes (119/452/165 records);
the caller consumes only `w*h`, matching the original scratch-buffer behavior.

**Next move:** use `work/rsp_break.py` while `work/drive.py` holds the game in
3D gameplay, and trigger an inventory/object sprite specifically. The
2026-08-25 live check hit the dispatch entry at `0x112CC` with `BX=0x000A`,
proving the probe is on the right path; the starting-room interaction simply
selected the already-resolved flat 4-bit format. Type 8 still needs an object
sprite scene. A clean follow-up captured DOS mouse position `(596,119)` at the
`INT 33h AX=3` boundary, aimed the room container at `(400,130)`, and sampled
all six visible inventory cells; all seven interactions remained `BX=0x000A`.
The next target is therefore a populated inventory or later level/object scene,
not another starting-room click. This is the §3.4 pattern — static analysis
has narrowed this to a point and cannot close it.

**First target-neutral pixel slice — implemented 2026-08-25.**
`work/asset_export.py` expands `OBJECTS.GR` type-8 record 0 and `D2/DATA/T64.TR`
tile 0 into `UW2I` assets. The shared representation is one row-major byte per
pixel, where each byte is a `PALS.DAT` palette-entry index; the attached palette
is the original 256-entry 6-bit DAC data. Type 8 is already translated through
its `ALLPALS.DAT` auxiliary table before export, while T64 pixels are copied as
their source palette indices. The fixed big-endian header records dimensions,
source kind/record, palette and auxiliary-palette identifiers, aligned pixel
and palette offsets, and source-record length.

The C-side seam is `src/common/indexed_surface.h`; it contains no video-memory
address or Falcon palette-word assumption. `analysis/pixel-fixtures.json` stores
source-file hashes, source-record hashes, dimensions, logical pixel hashes,
palette hashes, and final asset hashes. Reproduce and verify the slice with:

```text
python3 work/asset_export.py --check --out-dir work/pixel_assets
```

This proves deterministic host expansion and a stable target-neutral cache. The
Falcon presentation seam is now assembled and Hatari-verified separately; it
does not yet prove physical Videl scanout or equality with a DOS game frame.
The canvas-only browser display is the current acceptance slice. It imports the
connected DOS cutscene files through the virtual filesystem and presents their
indexed frames; the next port-side step is to feed one recovered game frame
through the same seam, then extend the function-record/fixture method into the
main menu and gameplay.

## Fidelity boundary for the first slice

Grounded in the shipped data and executable: the `.GR` container, type-8 RLE
decoder and auxiliary palette translation, the `T64.TR` tile container, the
source palette bytes, and the two fixture outputs. The host converter is
reproducible and its logical pixels are hashed in `analysis/pixel-fixtures.json`.

Target artefact: `UW2I` is a new cache representation. Its one-byte indices and
source-form 6-bit palette preserve the logical surface, while its fixed header,
big-endian fields, alignment, and source metadata are port plumbing.

Verified target artefact: `src/target/falcon/present.s` assembles with the
declared MC68030 restriction, and `make hatari-smoke` produces a complete
128,000-byte page byte-identical to the host contract. Unproven: physical Videl
timing/register setup, scanout on a real Falcon, palette-update timing, and
equality against a DOS game framebuffer rather than the synthetic seam fixture.

## Intro cutscene milestone — browser path connected 2026-08-25

The DOS startup/intro path is now the first complete function-level browser
slice. The LPF/ANIM container and delta payload are resolved in
`analysis/data-formats.md`; `work/cutscene_export.py` emits the checked-in
`analysis/cutscene-fixtures.json`; and `browser/uw2-cutscene.js` is the
function-level JavaScript counterpart. The page at `browser/index.html` is the
game itself for this milestone: it loads the connected DOS cutscene files from
the virtual filesystem, presents `CS000.N01`, `CS000.N12`, `CS000.N02`, and
`LBACK000.BYT`, then loops the verified display phases on a 320×200 canvas.

The required DOS functions and browser counterparts are recorded in
[`analysis/functions/cutscene-intro.md`](analysis/functions/cutscene-intro.md):

| DOS function | Browser counterpart | milestone status |
|---|---|---|
| `0x811FC cutscene_chunk_filename` | explicit connected source filenames | DOS filename construction remains analysis evidence; no unused browser helper is retained |
| `0x828E3 cutscene_run` | `parseLPF` / `decodeRecord` / `decodeFrames` | Verified at the indexed frame boundary for the connected fixtures |
| `0x82B35 cutscene_play` | canvas display scheduler | Ported for the verified display slice; full command/text/audio/input/timing semantics Unproven |
| `0x83150 cutscene_load_lback` | explicit `LBACK000.BYT` path / `readLback` | Verified source and 64,000-byte indexed background boundary |

The comparison order is mandatory: canonical DOS-derived indexed frame hash,
then browser presentation, then Falcon output. RGB565 conversion is an explicit
target artefact, not a replacement equality surface. Run the milestone checks
with:

```text
python3 work/cutscene_export.py --check
node --check browser/uw2-cutscene.js
node --check browser/uw2-reference.js
node --check browser/uw2-game.js
```

The source and decoder checks remain host-side and report no status into the
game screen. The canvas display advances through the connected indexed frames.
No browser key is a pause, restart, menu, or game-state shortcut.

## Mandatory input-driver rule — applies to every port

The browser, host and Falcon must execute the recovered DOS function-level
flow and feed/read it through the same recovered keyboard and pointing-device
I/O contract. A physical device event is only transport input; it must first be
converted into the DOS driver's documented position/motion, button/key,
queue, polling/acknowledgement and error data. A DOM click or key must never
call a menu helper, mutate game state, synthesize a DOS transition, reorder
events, or bypass an unported function.

This rule is mandatory even when the browser provides an extra convenience
control. A keyboard shortcut for a DOS mouse-only menu is a labelled test
harness control unless and until the DOS keyboard driver and its consumer have
been recovered and the shortcut is proven to feed that same path. It cannot be
part of a supported game-flow fixture or improve the DOS flow. The current DOS
evidence identifies the mouse boundary as `INT 33h` subfunctions `AX=0`,
`AX=3`, and `AX=0x0B`; the keyboard game contract remains `Unproven` for this
slice and must not be guessed. Graphics and sound are the explicit exceptions:
Canvas/Videl and audio backends may replace hardware mechanisms after their
logical contracts are recovered, but never game state or flow.
The current DOS input contract and open consumer coverage are recorded in
[`analysis/functions/input-drivers.md`](analysis/functions/input-drivers.md).

## Character-entry milestone — not loaded in the canvas runtime

The browser runtime does not display captured character screens or expose a
fixture entry into character creation. The recovered character functions and
their captures remain analysis evidence until their DOS consumer, input
ordering, drawing side effects and timing are connected to the game flow.
The canvas runtime does expose the recovered keyboard transport boundary:
browser key events become BIOS AX words in the emulated queue, but no browser
routine polls or consumes them on behalf of an unrecovered DOS consumer.

The durable function records, exact DOS ranges, browser counterparts, source
hashes, capture evidence, and difference ledger are in
[`analysis/functions/character-creation.md`](analysis/functions/character-creation.md).
The recorded functions are:

| DOS function / contract | Browser counterpart | status |
|---|---|---|
| `FUN_CODE_TAIL__07bb2d` `0x07BB2D–0x07BB4A` | function record only; no supported browser call yet | Identified; the recovered DOS input consumer and complete setup/cleanup side effects remain `Unproven`. |
| `FUN_CODE_TAIL__07b8a4` `0x07B8A4–0x07BB2C` | function record only; not loaded by the canvas runtime | Source strings and sex-screen evidence exist; later creation records and the supported input path are not implemented. |
| `FUN_CODE_TAIL__07b2f8` `0x07B2F8–0x07B533` | function record only; not loaded by the canvas runtime | The recovered choice consumer and exact drawing/timing/allocation side effects remain `Unproven`. |

The source and capture fixtures remain optional analysis evidence and are not
loaded by the canvas runtime. A passing browser display fixture does not
overrule the DOS executable or prove the Falcon target.

The input adapter is not a second game authority. It must terminate at the
emulated DOS driver and the recovered consumer; it cannot skip a creation
function or create a state transition absent from the recovered DOS flow. The
same mandatory rule applies to every future browser, host, and Falcon input
layer.

## Chosen Falcon graphics mode

The first backend will use **Falcon Videl 320×200, chunky 16-bit RGB565**, with
60 Hz timing as the initial presentation target. This keeps the verified DOS
framebuffer geometry while avoiding a permanent indexed-to-planar conversion in
the visible page.

The common `UW2I` surface remains indexed and row-major because that is the
game's logical representation and because it preserves palette semantics. The
Falcon backend will maintain a 256-entry indexed-to-RGB565 lookup table and
expand the surface into a chunky RGB565 page before publishing it at VBL. One
page is 128,000 bytes; a front/back pair costs 256,000 bytes of ST-RAM.

UW2 does contain explicit palette fades and palette-range updates
(`work/symbols.py` `palette_fade_*` / `palette_set_range`), but no evidence yet
of continuous 3D palette cycling. Fades and palette swaps are not a blocker:
they invalidate the RGB565 lookup/page and trigger a re-expansion before the
next presentation. If true palette cycling is found later, the same path stays
semantically correct; only its measured per-frame conversion cost matters.

The conversion and byte order are now verified by the MC68030 Hatari smoke
fixture. This is still not a hardware proof: exact Videl timing/register
values, physical scanout, and captured-page equality for a recovered DOS game
frame remain to be measured on the Falcon target.

## Porting unit: one recovered function at a time

The port will be **function-by-function and behavior-first**, not an
instruction translator. The byte-exact reassembly is the proof artifact for
the DOS image; it is not the Falcon implementation. The hashed shipped
`UW2.EXE` binary and captured DOS execution remain the sole behavioural
authority: Ghidra, reassembly, the browser implementation and Falcon code are
evidence or implementations, never replacements for DOS. Each migrated
function gets the durable `METHOD.md` §4.2 record containing:

- DOS file hash, offset and segment:offset entry, recovered name,
  callers/callees, purpose, inputs, outputs, globals, memory ownership, side
  effects, arithmetic/ordering rules, and DOS fixtures;
- evidence status: disassembly, data invariant, runtime observation, or
  inference, with unresolved behavior left explicit;
- browser and target implementation symbols/files, or an explicit
  `not implemented` state; and
- a difference ledger for every browser/Falcon change from DOS, including its
  reason, Grounded/Target artefact/Unproven category, equality fixture or
  hardware measurement, and explicit `none` where no difference exists.

Those differences include little-endian x86 versus big-endian 68000 data,
unaligned x86 accesses versus 68000 alignment faults, segmented/far pointers
versus flat addresses, 16-bit wraparound and flag-dependent idioms, and the
different register/condition-code sets. They must be expressed in the
function's contract or implementation rather than hidden in a broad runtime
compatibility layer. Shared behavior belongs in `src/common/`; DOS, Videl,
and other hardware substitutions belong at the target seam.

The deterministic browser reference starts with the function record, before or
with the Falcon implementation. Its controllable state/framebuffer experiment
is the convenient way to identify a function's role, inputs, side effects,
coupling and likely Falcon seam; it creates hypotheses, not authority. A
finding joins the record only when a DOS capture, disassembly fact, or other
graded DOS evidence confirms it. The same fixture then proves DOS → browser →
Falcon equality; a Falcon-only function cannot enter a supported path.

### m68k implementation gate — no guessed output

`m68k` is a family, not a complete target. Every Falcon routine must declare
the exact CPU (MC68030 for Falcon-specific code), assembler/compiler and
version, syntax/dialect, ABI/calling convention, memory/alignment and privilege
assumptions, and output format. The declared toolchain is the instruction-set
gate: build with the CPU restriction enabled and fail on unsupported
instructions or addressing modes. Keep the source, build command/configuration,
object or binary hash, and assembler listing/disassembly with the function
record. Then run the same contract fixtures in a 68030 emulator or on the
Falcon and compare canonical outputs and side effects.

A hand-written snippet that has not passed those gates is **Illustrative**, not
a 68000 counterpart and not `Ported` or `Verified`. JavaScript fixture success
proves the function contract boundary; it does not prove m68k legality or
execution. Shared code must assemble for the lowest declared CPU. MC68030
extensions belong only in the Falcon target seam, with their fallback boundary
recorded. This rule prevents a plausible mnemonic—such as the 68040-only
`MOVE16`—from entering a Falcon030 implementation by assumption.

### First browser function records — IDENTIFIED 2026-08-25

The first-pixel browser records below remain deliberately small and complete.
The connected intro records are maintained in
`analysis/functions/cutscene-intro.md`; both slices use the same strict host
adapter and virtual DOS filesystem, and neither hides an unsupported DOS
function behind the game page.

| Function record | DOS identity and evidence | Browser implementation | Difference ledger |
|---|---|---|---|
| `uw2_dos_file_boundary` | DOS file handles and byte streams are the source contract for the connected cutscene loader. | `browser/uw2-fs.js`: normalized names, `Map`-cached `Uint8Array` files, integer handles, `open/read/seek/tell/close`, and host-only persistence. | **Target artefact:** the browser uses host `fetch` for four known source files; memory mode is clean for tests, while persistent mode stores bytes in versioned IndexedDB and only path/size/source-variant/SHA-256 metadata in localStorage. |
| `uw2_cutscene_decode` | LPF/ANIM structure and delta records are grounded by disassembly, shipped files, and the checked-in analysis fixtures. | `browser/uw2-cutscene.js`: `parseLPF`, `decodeRecord`, `decodeFrames`, `readLback`. | **Ported/Verified at the indexed frame boundary** for `CS000.N01`, `CS000.N12`, `CS000.N02`, and `LBACK000.BYT`; the browser does not run the fixture hash gate. |
| `uw2_indexed_to_rgb565` | DOS produces the indexed framebuffer; RGB565 is a target presentation artefact. | `browser/uw2-cutscene.js`: `paletteToRgb565`, `frameToRgb565`, `drawFrame`; `src/target/falcon/present.s` provides the Falcon seam. | **Target artefact:** indexed LPF pixels and palette bytes are converted for canvas/Falcon presentation; DOS VGA timing and physical Videl scanout remain Unproven. |

The checked-in manifests remain analysis/build oracles. The browser page does
not compute hashes, report fixture status, or expose a validation surface.

## DOS timing and game-flow cadence

Timing is part of the authoritative function contract whenever it affects input
sampling, timer callbacks, animation, audio, frame publication, races, or game
state. UW2 contains a recovered `INT 8` PIT scheduler (`analysis/subsystems.md`
and `analysis/ghidra.md` §17) with a runtime divisor, drift-free accumulators,
and runtime timer-slot periods. The port must capture/replay those DOS values
and preserve the original tick/input/frame ordering. It must not assume that a
60 Hz browser or monitor refresh is the DOS game tick.

The browser's deterministic runner must own simulation ticks.
`requestAnimationFrame`, `Date`, `performance.now`, host timers, and physical
VBL may pace presentation of an already scheduled replay, but may not define
game-flow order or silently drop, duplicate, accelerate, or delay authoritative
DOS ticks. The current 60 Hz Falcon/Videl choice is a presentation target only.
Exact DOS cadence and its relationship to display refresh remain `Unproven`
until runtime evidence is captured; the intro's 180–240 ms fixture cadence is
a labelled presentation fixture, not DOS timing parity.

## Function-body fidelity

Each JavaScript and Falcon function counterpart must preserve the recovered DOS
function as closely as the evidence permits. Do not pollute the function body
with `throw` paths, assertions, validation, clamps, defaults, retries, logging
branches, or other error handling absent from DOS. Preserve fall-through,
returns, widths, wrapping, side effects, ordering, and known unsupported-input
behaviour. An unrepresentable case is `Unproven`/`Unsupported`, not an excuse
to add a convenient semantic branch.

Assertions, hashes, diagnostics and failure reports belong in build, fixture and
parity harnesses. API, memory-safety, endian, alignment and resource checks
required at a host/target boundary are labelled `Target artefact`, kept outside
the semantic function, and cannot change valid DOS results. See
[`analysis/functions/translation-policy.md`](analysis/functions/translation-policy.md).

The supported browser deliverable is the game screen itself: it must boot the
DOS-derived virtual filesystem, run the verified display path, accept physical
input only through the emulated DOS I/O boundary, and present the logical
framebuffer. The current page satisfies the connected display gate with the
intro/cutscene loop. Its keyboard queue is connected to BIOS `INT 16h` and
`fn_24358`, but no unrecovered consumer is called speculatively. The next gate
is the recovered main-menu/character consumer, then handedness and the
remaining character-creation states, and only then the connected 3D
starting-room path.

## Then, and only then, the port

The ratchet, `.GR` pipeline, first target-neutral asset slice, and deterministic
MC68030/Hatari RGB565 seam are complete for the standard archive family. The
remaining format proof gap is the divergent `PANELS.GR` record 3, not type-8
pixel encoding or archive emission.

1. **Maintain the function-record ledger and analysis fixtures** — every
   supported function records its DOS contract and difference ledger, and the
   browser experiment or analysis fixture lands before or with the Falcon half.
   The canvas runtime does not load fixture manifests or report their status.
   Extend the audit whenever a target artefact, unproven claim, or observed DOS
   difference is added (METHOD.md §4.2–§4.3a).
2. **Keep the browser reference runnable.** `browser/index.html` is the
   convenient first test vehicle: the same supported function path must run
   without Falcon hardware. Within a page, cache hits and persistent reloads
   must expose the same bytes; `?fs=memory` selects the clean in-memory mode.
   Its host adapter is the only place allowed to fetch or import files; the
   semantic core remains on the virtual DOS filesystem.
3. **The target seam for renderers.** `src/common/` is target-neutral
   and 68000-clean, `src/target/<name>/` the only code that turns indices into
   hardware pixels, seam at an **8-bit indexed surface**. UW2's own pipeline
   already ends in 8bpp — the four bit-depth doors all expand *to* 8 bpp — so
   the game's native representation and the family's seam agree. Do not bake
   in the Falcon.
4. **Converters decode, never transcode.** `.GR`/`T64.TR`/`STRINGS.PAK`/`.ARK`
   readers already exist as Python; the port's converters emit big-endian,
   explicitly aligned, one byte per pixel, palette encoded per target with the
   cache header recording which. Widen narrow fields while there.
5. **First slice: one `.GR` sprite and one `T64.TR` tile on screen, verified by
   equality** — host expansion vs. browser logical surface first, then against
   a captured Falcon framebuffer, byte-identical, with each hash retained as a
   regression (METHOD.md §4.5). Say precisely what each comparison proves:
   browser and target agree at the common seam; it does **not** by itself prove
   the output matches DOS. That needs the DOS oracle, which this project has.
6. **Decide what a threaded-VM engine means for the port before writing engine
   code.** This is UW2's genuinely novel porting question and no sibling has
   faced it. The game's logic runs as token streams through a 111-slot
   dispatch table with 101 NEXT sites and no central loop. Two shapes are
   possible — port the *handlers* and keep the streams as data, or compile the
   streams away — and they have completely different fidelity arguments. Answer
   it with the disassembly, in a doc, before either is implemented. METHOD.md
   §4.1's third rule applies with force: **behaviour is not build-selectable**;
   if two readings are both plausible the answer is more disassembly, not a
   flag.

## Repo hygiene that is blocking a clean checkout

Small, unglamorous, and currently makes the project unreproducible for anyone
who clones it:

- **`work/stage.py`, ending in a CRC tally.** The zip → LZH → 305-file
  expansion is by hand, no command recorded, and no LZH CRC was ever checked.
  The 305 derived files are committed *because* they cannot be regenerated —
  which inverts METHOD.md §1.2. One script ending in "305 entries, 305 OK, 0
  bad" fixes the reproducibility, the verification and the commit all at once.
- **Two upstreamables have been pending since 2026-08-21** and the family rule
  is same-session:
  - `work/mouse_driver.asm` — a from-scratch `INT 33h` driver (AX=0/3/0Bh)
    against the 8042. UW1 hits the identical missing-driver wall. Belongs in
    `../F030Method/dos/`.
  - `work/rsp_break.py` — QEMU's gdbstub enabled live over QMP, driven by a
    hand-rolled RSP client: breakpoint an entry, read the return address off
    the stack, works whether the call was direct or computed. **No sibling has
    this**, it is what walked the 5-hop chain up from the mouse-read code, and
    it is the instrument the `.GR` type-8 hunt above depends on. Upstreaming it
    is not bookkeeping — it is the highest-value single transfer available in
    the family right now.

## Order of work

```
  ratchet on UW2.EXE  ────────────────────────►  phase 2 gate (DONE)
      │                                              │
      │  (both use the oracle)                        │
      ▼                                              ▼
  `.GR` decode + first-pixel slice              semantic recovery / PANELS.GR
      │                                              │
      ▼                                              ▼
  converters + target seam ──► first sprite ──► threaded-VM decision
                                on screen
      ▲
  work/stage.py + upstream mouse_driver/rsp_break  (do these first; they are
                                                     an afternoon each)
```
