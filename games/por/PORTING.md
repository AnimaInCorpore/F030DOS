# Porting Pool of Radiance to the Falcon030

Roadmap and per-slice plan. `AGENTS.md` holds the verified facts about the DOS
original; this file holds the plan for reproducing it on Falcon hardware.

Status reviewed 2026-10-10: only the Falcon image-presentation endpoint is
implemented and checked (128,000-byte host/target equality at 4 MB and 14 MB).
The [slice table](#slice-status) records the unfinished layout, text, dungeon,
character/script and input work. This review does not rerun `make title-smoke`
or establish a playable route. [README.md](README.md) provides the short overview.

## The authority problem

**Pool of Radiance has no reconstructed C source.** The hashed DOS binaries
are the behavioural authority, and every slice must carry its canonical source
range and evidence grade through to the port.

That is not a blocker for all of the work, but it is a hard boundary through
the middle of it:

| | authority available today | can be ported now |
|---|---|---|
| Container/codec/pixel formats | decoded and verified (`analysis/data-formats.md`) | **yes** |
| Screen layout, palette, timing | partly — assets plus recovered renderer and timing routines | slice by slice |
| Game rules, combat, scripts, saves | `GAME.OVR`, partitioned into 38 units with residue classified | only after the required routine contract is read |

**Update:** `GAME.OVR` is no longer opaque. It is 38 Turbo Pascal overlay units
with exact bounds and 774 known entry points (`work/overlay_map.json`,
`analysis/executables.md`). The authority exists now; it still has to be read
routine by routine before any rule is ported.

**Rule for this project: do not invent rules.** A subsystem is ported after the
DOS routine that implements it has been read, or not at all. Where a placeholder
is unavoidable to keep something on screen, it is labelled as one here and in
the source, and it never becomes the reference.

## Function records and browser discovery

For every function represented in browser or Falcon code, maintain the
`METHOD.md` §4.2 record: DOS file hash/range and evidence, recovered purpose
and complete contract, DOS fixtures, implementation symbols, and a difference
ledger against the DOS function. Record and prove even “no difference”; an
unresolved item is `Unproven` and cannot enter a supported path. The
deterministic browser reference starts with the first function and lands its
fixtures before or with the Falcon slice. Use its controlled experiments to
identify the function's role, inputs, state effects and likely target seam, but
promote a result to the record only when DOS capture or other graded DOS
evidence confirms it.

## Nothing without a source

**Nothing enters the port that has no ground-truth source in the DOS original.**
Not placeholder rules, not guessed constants, not invented layout, not
"reasonable" defaults. If the authority has not been read yet, the correct
output is *nothing* — an unimplemented slice, not an approximation.

Three categories, and every non-trivial thing in the port must be in one of
them explicitly:

| category | meaning | how it is marked |
|---|---|---|
| **Grounded** | traced to a DOS routine or a verified file format | cite the hashed source image, canonical range, behavioural contract and evidence grade in the source comment |
| **Target artefact** | exists only to serve the Falcon and makes no claim about the original (build system, cache container, framebuffer handling) | no citation needed; it is not pretending to be DOS behaviour |
| **Unproven** | needed to make something run, but not yet traced | **must** carry a `*** NOT GROUNDED IN THE DOS ORIGINAL ***` comment at the definition and an entry in §Open risks |

An unproven item is a debt with a name, never a silent default. It may not be
cited as a reference by anything else, and it may not be used to justify a
second assumption.

The current source authorities are:

- `START.EXE` — SHA-256 `f15fd31ae489d765b4120624d172b070ea0c85b1e8ade954b58189a271cce48f`;
- `GAME.OVR` — SHA-256 `cbb4cdc4d245e7a3abfc1c9d2323c93d146d67b061a04d1dea0b495c829247fe`.

Every port citation records one classification grade: **executed and
content-matched**, **evidence-backed control flow + reassembly ratchet + clear
data guard**, or **sweep-inferred**. The grade classifies the cited bytes; the
behavioural contract remains a separate requirement.

### Closed platform-substitution list

The current substitution surface is limited to:

- TOS process startup, shutdown, exception restoration and memory ownership;
- GEMDOS file access;
- VIDEL framebuffer ownership, VBL publication and indexed-to-RGB565 expansion;
- the `PORI` target cache, build-time data conversion and capture diagnostics.

These paths are target artefacts and cannot change valid-input game semantics.
Adding a category requires reviewing this list as a whole against the DOS
contract; game logic, arithmetic, ordering and layout rules never enter it.

### Current audit (2026-08-24)

| item | where | category |
|---|---|---|
| `.DAX` container, RLE codec, image header, 4 bpp packed high-nibble-first | `tools/convert_data.py` | **grounded** — verified formats, and the pixel order is confirmed by `entry_02AD` in unit `18E` |
| `PORI` bank layout, `make` targets, framebuffer/VBL ownership, RGB565 expansion | `tools/convert_data.py`, `src/start.s`, `src/vbl.s`, `src/present.s` | **target artefact** |
| 16-colour EGA palette | `work/gbimage.py` → `tools/convert_data.py` | **grounded** — byte-complete scan of both binaries finds no `0x3C0` write and no `AH=10h` anywhere; the game never programs a palette (`analysis/dos-oracle.md` §8) |
| `blit_centred` centring rule | `src/present.s` | **unproven** — the DOS blitter takes an explicit 8-row/1-byte position and does not centre |

The remaining unproven item is labelled at its definition.

## Fidelity policy

Two different standards apply, and mixing them up is the main way a port like
this goes wrong.

**Game logic — preserve observable semantics over the declared supported
scope.** The DOS routine is the authority for *what* is computed; the Falcon
code may be restructured, renamed and written idiomatically in 68030 assembly.
A transliteration is not the goal. Every rule, table, ordering, boundary
condition and arithmetic result the player can observe must survive. A claim
of 100 % fidelity is made only after the comparison chain proves it.

**Graphics and sound hardware — investigated only far enough to reproduce the
observable result on the current target.** The DOS register programming is
evidence, not a specification. The Falcon owns its own video and audio path,
and the target's capabilities may widen later, so nothing is designed around
EGA's limits.

### Where the line falls

The split is not "pixels vs. numbers" — it is **observable vs. mechanism**:

- **Logic** — anything that changes what the player can see, hear, or decide
  on. Sprite transparency, draw order, what is on screen at all, which frame
  of an animation plays, how long a message stays up.
- **Adaptation** — anything that only changes *how* those observable pixels
  and samples reach the hardware. Bitplane layout, map-mask registers, row
  tables, palette register programming, DMA and timer plumbing.

Worked example from this project: `entry_02AD` in overlay unit `18E` expands
packed 4 bpp art into four EGA bitplanes. It is **pure adaptation** — it exists
only because EGA has bitplanes, and the Falcon has none, so it is *not* ported.
The single fact worth extracting from it is that the **high nibble is the left
pixel** (`analysis/executables.md` §Unit 18E). That is "investigate far enough
to reproduce", exactly.

By contrast `entry_19A5` positions sprites in **8-row and 1-byte units**. That
is not a hardware detail — it constrains where anything can be placed on
screen, so it is a layout rule and it is preserved.

### Two consequences worth stating

1. **Numeric fidelity is bit-exact even though the code is not.** "Semantic,
   not instruction-level" does not license 32-bit arithmetic where the DOS
   original wraps at 16 bits. Combat rolls, RNG, saving throws and any
   accumulator the player can observe keep the original width and overflow
   behaviour — the width comes from the DOS contract, not the target type.
2. **Verification has to move from diffing to behaviour.** If the port is not
   a transliteration, instruction-level comparison proves nothing, so logic
   fidelity can only be shown by running both and comparing results. That makes
   the **DOS dynamic oracle a prerequisite, not an optional extra** — see
   §Slice status 5 and `AGENTS.md` §Next steps. Presentation already has an
   exact check (`make title-smoke`); logic has none yet, and cannot until
   `img/` boots.

## Target back ends

The port target is **not fixed**. Atari ST and Atari Falcon030 are both live
possibilities, and nothing outside a target directory may assume either.

```
src/common/            target-neutral, 68000-clean
    main.s             frame loop
    resource.s         PORI bank loading (GEMDOS)
    surface.s          drawing on the 8-bit indexed surface
    inc/por.s          formats and surface geometry — no hardware constants
src/target/falcon/     Videl, RGB565 presentation, VBL page flip
src/target/st/         contract only; no code until someone targets an ST
```

Build with `make TARGET=falcon` (default) or `make TARGET=st`.

**The seam is the indexed surface.** Everything the port draws is 8-bit
indexed with the DOS palette index preserved verbatim; a target back end is the
only code that turns indices into hardware pixels. That keeps the back end small
— the contract is eight symbols, listed in `src/target/st/README.md` — and it is
why the Falcon back end needs no palette registers while an ST back end will
need both a chunky-to-planar converter and real palette loading.

Two rules hold this in place:

- **`src/common/` is assembled `-m68000`.** Not a style preference: a 68000
  takes an address error on misaligned word access, so if the ST is a live
  target the shared code must be 68000-clean from the start. `make test` and the
  build enforce it; only `src/target/<name>/` may raise the CPU.
- **`src/common/inc/por.s` carries no hardware constants.** `make test` fails if
  `FRAME_BYTES`, `LUT_ENTRIES` or similar leak into it.

On the data side the same seam applies: pixel data is target-neutral (one byte
per pixel), and only the palette table is encoded per target.
`tools/convert_data.py --target {falcon,st}` picks the encoder, and the `PORI`
header records which encoding a bank carries (`PORI_PAL_*`), so a wrong-target
bank can be refused rather than displayed in the wrong colours.

No ST code is written yet, on purpose — see §Nothing without a source. The
folder and the contract are the commitment; the second back end is not.

## Presentation contract

The target presentation contract is:

- Everything the port draws stays **8-bit indexed**, with the DOS palette index
  preserved verbatim. No Falcon palette registers are used.
- The completed indexed surface is expanded to **16-bit RGB565** into a hidden
  page at the frame boundary; the VBL handler publishes that page so the three
  Videl base bytes are never observed half-updated.
- Falcon video is 320×200 true colour, one big-endian RGB565 word per pixel.
- No VGA/EGA bitplane emulation anywhere: the DOS 4 bpp packed pixels are
  unpacked to one byte per pixel **on the host**, by `tools/convert_data.py`.

This contract is what makes verification exact rather than visual — see
§Verification below.

## Data pipeline

```
assets/*.7z ──7zz──► game/POR/*.img ──7zz──► game/POR/Disk*/  (pristine)
                                                   │
                                              unar │  work/stage.sh
                                                   ▼
                                          work/expanded/  (257 files, CRC-checked)
                                                   │
                              tools/convert_data.py │  make falcon-data
                                                   ▼
                                     release/PORCACHE/*.BIN  (PORI banks, big-endian)
                                                   │
                                   src/resource.s  │  GEMDOS Fread at runtime
                                                   ▼
                                    indexed surface ──► RGB565 page ──► Videl
```

`tools/convert_data.py` converts **only** formats resolved in
`analysis/data-formats.md`. An unrecognised block is skipped and counted, never
emitted with invented geometry. `src/inc/por.s` and the converter must agree on
the `PORI` layout; `make test` fails the build if they drift.

### Data representation policy

The DOS files are little-endian, packed, and shaped for an 8086. Nothing in the
port consumes them in that form. The converter **decodes into named fields and
re-emits**; it never copies a DOS record and byte-swaps it in place. That is
what keeps a later change of target cheap.

Rules:

- **Decode, don't transcode.** Parse the DOS structure field by field, then
  write the target's representation. A converter that memcpy's a record has
  baked the source layout into the output.
- **Emit big-endian** for every multi-byte field. The `PORI` bank already is,
  header and directory alike (`struct.pack(">…")` throughout). Byte order is a
  property of the *output* stage, so switching targets means changing one stage,
  not re-deriving formats.
- **Store values, not encodings.** Packed 4 bpp becomes one byte per pixel —
  endian-neutral, alignment-neutral, and identical work for any target. Do the
  same for any other bit-packed field rather than passing the packing through.
- **Align for the target, explicitly.** This matters more than endianness here:
  the DOS records are **285 B** (character), **63 B** (item) and **9 B**
  (spell) — all odd, so in an array every other record starts on an odd
  address. The 68030 tolerates misaligned word access but pays for it, and the
  68000 does not tolerate it at all. Pad records to even (or 4-byte) boundaries
  in the converter and record the padded layout in `src/inc/por.s`.
- **The DOS layout stays documented in `analysis/data-formats.md`**, unchanged.
  The cache format is a target artefact and may be revised freely; the decoded
  DOS layout is the durable knowledge and must not be edited to suit a target.

## Slice status

| slice | state | verified by |
|---|---|---|
| **1. Presentation endpoint** — boot a Falcon, stage a converted bank, expand and publish one page | **DONE** | `make title-smoke` — 128,000 bytes identical to the host expansion, at both `MEMSIZE=14` and `MEMSIZE=4` |
| 2. Image bank completeness — all 62 `.PIC`, 62 portraits, 491 image `.DAX` blocks | not started | round-trip every converted image against `work/gbimage.py` |
| 3. Screen composition — the real POR screen layout (viewport, portrait strip, text window) | blocked | needs the layout constants from `GAME.OVR` |
| 4. Font and text window | blocked | no font file ships; glyphs are presumably in `GAME.OVR` or an undecoded block |
| 5. Dungeon view — `GEO*`/`WALLDEF*`/`8X8D*` | blocked | The full pipeline is traced end to end, including geometry: `GEO` (all 4 planes confirmed/narrowed) → `WALLDEF` (5 wall-types × 10 pre-drawn depth sprites) → `entry_0219`'s per-slot sprite table → `entry_0614`'s 3-rank/2-side sweep, each rank×side now mapped to its exact sprite slot (`analysis/executables.md` §The depth×side → sprite-slot mapping) → `entry_0219` calls back into `entry_015D` (unit `18A`, confirmed byte-for-byte, no separate pixel-copy routine exists) → an `8X8D*.DAX` tile frame, blitted via unit `18E`'s own image-record conventions. Enough is now known to reconstruct the on-screen layout in a converter without further RE, modulo the still-open style-byte meaning. Still open: the `0xcd2`-range style bytes |
| 6. Character/monster records — 285 B / 63 B / 9 B | 285 B record partially decoded | found the roster routine (unit `0C9`) — name, all 6 ability scores + 18/percentile STR, and 5 more fields inferred from UI-label order, all cross-checked against a real save (`analysis/data-formats.md` §The 285 B character/monster record); most of the record (HP, saves, spells, inventory) still undecoded; 63 B item and 9 B spell records untouched |
| 7. `ECL*` script interpreter | blocked | container **and** per-instruction encoding resolved (units `045`/`020`; decoder `work/ecl.py`) — full opcode→operand-count table, operand addressing modes, conditionals. Validated on the whole corpus: 29/29 blocks' first scripts decode cleanly. Type-`0x80` operands carry inline 6-bit-packed text. The inline text is fully decoded — 2,904 strings / 146,873 chars of real game prose recovered (`work/ecl.py --text`). Still blocking a port: the block-level layout (walking past the first script covers only ~6 %, so later script entry points are unlocated) and the 60 opcodes' semantics (`analysis/data-formats.md` §`ECL*.DAX`) |
| 8. Input, timing, audio | not started | audio deliberately deferred until its DOS interface contract is recovered |

Slices 3–7 all reduce to the same prerequisite: reading `GAME.OVR`. The first
disassembly pass is done and the file is partitioned into 38 units with known
entry points; the remaining work is decompiling the units that own each
slice. Unit **`18E`** is the EGA renderer; decompiling it has now settled open
risks 1 (`analysis/dos-oracle.md` §8), 2 and 3 below
(`analysis/executables.md` §Unit `18E`).

## Verification

The presentation contract makes the check an equality, not a judgement:

1. `tools/convert_data.py` produces indexed pixels and an RGB565 palette.
2. The Falcon expands those pixels through that palette.
3. `tools/check_frame.py` performs the same expansion on the host and requires
   the captured Videl page to be **byte-identical**.

`make title-smoke` runs the whole chain — build, convert, boot Hatari, capture
the published page at a VBL breakpoint, compare, and assert the on-target
resource self-check wrote `STATUS_OK` to `PORSTAT.BIN`.

Never accept a frame because it looks right. `analysis/tools.md` records the
case that motivated this: a planar interpretation of the DOS pixels satisfied
every size identity and rendered as pure noise.

## Memory

Design target is a **stock 4 MB Falcon**. Current
allocation, all from the default (ST-RAM) pool via `Mxalloc` after `Mshrink`:

| block | bytes |
|---|---|
| two RGB565 pages | 2 × 128,000 |
| indexed surface | 64,000 |
| `PORI` staging buffer | 196,608 |
| supervisor stack | 8,192 |

≈ 525 KB. Verified at `MEMSIZE=4`: same Videl base (`$0219D8`) and an identical
frame as at `MEMSIZE=14`. The staging buffer is sized for `TITLE.BIN`
(128,076 B) with headroom; slice 2 will need a streaming policy rather than a
whole-bank read once the full art set is loaded.

## Open risks

1. ~~The EGA palette is an assumption.~~ **RESOLVED.** A byte-complete scan of
   both binaries (`START.EXE` and `GAME.OVR`, 100 % of the code) finds no
   `0x3C0` (Attribute Controller) write and no `INT 10h AH=10h` anywhere. The
   game never programs a palette; the standard EGA 16-colour default that
   `AH=00h`'s mode set loads is the real answer, not an assumption. See
   `analysis/dos-oracle.md` §8.
2. ~~The 9 unknown image-header bytes may carry a per-image colour remap.~~
   **RESOLVED.** They are not a per-image remap in the sense that mattered
   here: byte 0 is a repeat count for multi-element blocks (`8X8D*` etc.),
   and the other 8 are a 16-entry CGA-only colour-reduction table that the
   EGA renderer path never reads. Slice 2 art needs `frameCount`, not
   `cgaRemap`. See `analysis/executables.md` §The 9 unknown header bytes and
   `analysis/data-formats.md` §Image header + pixel format.
3. ~~`.PIC` frame 0 vs. overlays — whether index 0 is transparent.~~
   **RESOLVED.** Transparency at blit time is real, EGA-live, and
   parameterised (a caller-supplied colour-key index, not hardcoded to 0) —
   `entry_02AD` builds a mask, `entry_08F5`/`entry_0D9F`/`entry_1EBA`/
   `FUN_0000_27a6` apply it as `dest = (dest & mask) | src`. All 19 real
   callers of the load entry point (`entry_011B`) were read from raw
   disassembly: transparency is requested by only 2 of the 6 calling units,
   and where requested the index is colour 0 in 6 of 7 cases and colour 13 in
   the seventh. See `analysis/executables.md` §Who calls `entry_011B`?.
4. **No streaming policy yet.** Reading a whole bank per screen will not scale
   to the 2.4 MB expanded set on a 4 MB machine.
