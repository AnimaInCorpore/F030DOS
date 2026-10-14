# Panzer General port plan

## Slice 001: Poland map loading and viewport state

Status reviewed 2026-10-10: implementing prerequisites;
**no playable route is supported yet**. Existing DOS/JS/native fixture evidence
is scoped below. The captured tactical-screen presentation is a static display
demonstration; scenario producers, input/timers and the turn loop are not
connected. Documentation review does not rerun or promote these contracts.

The translator/checkpoint tooling added on 2026-10-10 is recorded in
[../analysis/x86-flag-validation.md](../analysis/x86-flag-validation.md) and
[the shared implementation record](../../F030Method/analysis/stearcade-implementation.md).
The synthetic bench establishes no game-speed gain or gameplay support.

DOS route: original launcher, no sound, real CuteMouse `/P`, standalone Poland,
default controls/difficulty. Authority and resource identities:
`analysis/executable.md`, `analysis/scenario-route.md`, `analysis/scenario-loader.md`.
The committed input manifest is `work/routes/poland.json`; the retained DOS
execution trace and resource/state checkpoints establish reachability.
Recovered inventory: `work/re/functions.txt` (all 643 entries).

Integration point: `sub_00037E75` loads SET/STM and produces map/viewport
state, returning at vaddr `0x382DB`. The successful Poland contract now passes
JS and native m68k; complete error/configuration coverage remains open.
First complete bodies to port: `sub_00010976` (extents) and `sub_00048105`
(viewport bounds), with stable records in `analysis/functions/` and shared
DOS input/output fixtures. These are prerequisites, not independent gameplay.

| Required provider | Consumer | Evidence / readiness / next action |
|---|---|---|
| Selected DOS build, LE map | all functions | validated placement; preserve canonical sub IDs |
| QEMU, MS-DOS, CuteMouse, no-sound disk | DOS route | pinned hashes and successful fresh-disk replay in loader notes |
| `sub_00037216` GAME001 loader | `sub_00037E75` | raw reads captured; decoded globals and unit state open |
| `sub_00037E75` SET/STM loader | geometry/rendering | 23 paired reads, globals/six arrays match JS and native; close input producers and other branches |
| `sub_00010976` | loader centering | 7 shared DOS fixtures pass JS and m68k |
| `sub_00048105` | display consumers | 5 shared DOS fixtures pass JS and m68k |
| `sub_00060907` / `sub_00060926` | loaders / unit names | 52 direct DOS cases pass JS and native; other input shapes remain unproven |
| `sub_00063375` / `sub_0006337B` / `sub_0006339F` | unit setup / simulation | 19 shared DOS RNG cases pass JS and native; boot seed producer/order open |
| `sub_0003AFF3` | final scenario unit classes | 400 class bytes, averages and final seed pass JS/native; captured record/equipment producers remain open |
| CRT strings/streams and resource allocation | both loaders | canonical inventory retained; contracts/target seams still open |
| VESA480.DLL exports 6/7/11 | drawing | 16 shared DOS fixtures pass JS and native m68k (`gfx_copy_rect`, unclipped 1:1 copies only); clip/stretch/shadow refused as `Unproven`; Videl/chunky-to-planar display path open |
| TACMAP.SHP/TGF and VESA480.DLL palette/mode exports | drawing | indirect dependencies remain required; preload/reuse and exports 0-5, 8-10, 12 contracts open |
| Input/timer initialization and callbacks | connected flow | DOS prerequisite understood; browser/m68k contracts not implemented |

No reachable dependency is excluded merely because this trace missed it.
Campaign, moves, attacks, turn completion and other scenarios remain unproven.
Audio is deferred by the measured no-sound configuration; required timing
callbacks remain in scope. No invented game-state stubs enter supported flow.

## Commands and gates

```text
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd \
  --out work/qemu_out/geometry-3 --script work/routes/poland.json \
  --seconds 60 --file-io --geometry-contracts
python3 work/check_file_io.py work/qemu_out/geometry-3
python3 tools/collect-geometry-fixtures.py work/qemu_out/geometry-3/route.json
node tests/geometry-reference.mjs
python3 tools/check-native-geometry.py --out build/geometry-native-final
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd \
  --out work/qemu_out/poland-fields-4 --script work/routes/poland.json \
  --seconds 60 --file-io --loader-state
python3 tools/collect-loader-fixture.py work/qemu_out/poland-fields-4/route.json
node tests/loader-reference.mjs
python3 tools/check-native-loader.py --out build/loader-native-final
node tests/rng-reference.mjs
python3 tools/check-native-rng.py --out build/rng-native-1
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd \
  --out work/qemu_out/poland-unit-classes-1 --script work/routes/poland.json \
  --seconds 60 --file-io --loader-state
python3 tools/collect-unit-classes-fixture.py work/qemu_out/poland-unit-classes-1/route.json
node tests/unit-classes-reference.mjs
python3 tools/check-native-unit-classes.py --out build/unit-classes-native-1
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd \
  --out work/qemu_out/draw-1 --script work/routes/poland.json \
  --seconds 60 --draw-contracts
python3 tools/collect-draw-fixtures.py work/qemu_out/draw-1/route.json
node tests/draw-reference.mjs
python3 tools/check-native-draw.py --out build/n-draw
python3 tools/check-native-rng.py --out build/n-rng-tr --translated
python3 tools/check-native-loader.py --out build/n-load-tr --translated
python3 tools/check-native-geometry.py --out build/n-geom-tr --translated
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd   --out work/qemu_out/shape-1 --script work/routes/poland.json   --seconds 60 --shape-contracts
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd \
  --out work/qemu_out/shape-2 --script work/routes/poland.json \
  --seconds 60 --shape-contracts axis_turn
python3 tools/collect-shape-fixtures.py work/qemu_out/shape-1/route.json work/qemu_out/shape-2/route.json
python3 tools/check-native-shape.py --out build/n-shape-1
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd \
  --out work/qemu_out/compose-6 --script work/routes/poland.json \
  --seconds 60 --compose-contracts
python3 tools/collect-compose-fixtures.py work/qemu_out/compose-6/route.json
python3 tools/check-native-compose.py --out build/n-comp-1
python3 tools/x86x/coverage.py --out build/x86x/coverage.txt --assemble
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd \
  --out work/qemu_out/frame-2 --script work/routes/poland.json \
  --seconds 60 --file-io
python3 tools/collect-frame-fixture.py work/qemu_out/frame-2 poland_tactical
python3 tools/check-native-frame.py --out build/n-frame-vga --monitor vga
python3 tools/check-native-frame.py --out build/n-frame-rgb --monitor rgb
```

Windows toolchain (verified 2026-10-06): set `VASM`, `VLINK` and `HATARI` to the Windows
builds in `../F030Comanche/tools/toolchain/` (`vasmm68k_mot.exe`, `vlink.exe`, `hatari.exe`)
and put `C:\msys64\ucrt64\bin` on `PATH` (the Hatari build needs its runtime DLLs). Sources
declare explicit section types (`section data,data`); an untyped section makes the
`ataritos` link fail with error 138. The checkers pass Hatari a bare `.TOS` name with
`cwd` set to the output directory; an absolute path stops the autostart. The QEMU oracle needs
`C:\Program Files\qemu` on `PATH` and `work/dos_files/ctmouse.exe` (analysis/executable.md).

Output directories must be fresh. Fixture expected values are collected from
DOS; they are never generated from JavaScript or native implementations.
The native executable is an explicitly labeled contract harness and does not
stand in for the game. Browser runtime integration begins once state producers
and consumers close; a fixture page is not the phase-4 playable deliverable.

Actual prerequisite results: 12/12 DOS fixtures equal in Node and the browser
lab at `web/index.html`; 12/12 equal in native Falcon030 Hatari, comparing all
196 canonical output bytes. Common assembly passes `-m68000` restriction.
Native result metadata, source/tool/ROM/program hashes, listing and linker map
are retained under each fresh `build/geometry-native*/` output. Emulator results
are distinct from physical hardware and from connected gameplay parity.
The two common routines occupy 188 code bytes; the linked contract harness has
632 text bytes, 780 data bytes and 218,024 BSS bytes, including its test arena
and stack. Those are measured build sizes, not a projected game budget.
The loader/string harness matches 6,779 DOS bytes. Its text is 1,586 bytes,
data 2,235,196 bytes and BSS 12,368 bytes. Data contains a deliberately sparse
2,228,224-byte fixture arena to preserve captured virtual pointer values;
this test representation is not the eventual game allocation design.
RNG native comparison passes 19 cases/152 bytes. Unit-class setup passes the
Poland boundary's 412 bytes, including the final random seed. No timing or
physical Falcon claim follows from these isolated emulator fixtures.

## Bounded x86 to 68000 translation

`tools/x86x/translate.py` emits 68000 source from recovered x86 functions through a typed rule
table (analysis/x86-translation.md). Three RNG functions, the two string helpers and the two
geometry functions (`ebp` frames, stack locals, a stack argument) are generated and pass the same
DOS fixtures as the hand-written ports in Hatari (`check-native-rng.py`, `check-native-loader.py`
and `check-native-geometry.py` with `--translated`). `tools/x86x/coverage.py` reports the
inventory coverage (2026-10-06: 344 of 643 functions implemented, 142 closed under calls, 12
DOS-validated) and, per lowering rule, whether a validated function exercises it; a rule no
fixture has exercised is `Unproven` however many functions use it (52 validated, 23 Unproven).
The static-frame compositor `sub_00014BF6` (with its present call a recorded boundary stub) passes
one connected DOS witness (316,428 bytes) in a 14 MB Hatari with the arena at the DOS virtual base
(`check-native-compose.py`); the Falcon needs RAM at `$1E0000` for this.
The clipped shape draws `sub_00058AB4` and `sub_00058F9E` with their row copies have **no
hand-written port**: their only implementation is generated, and `check-native-shape.py` compares
it with 32 DOS witnesses (23 clipped) captured by `work/probe_shape_contracts.py` from two route
runs (271,911 bytes equal). The first run of that gate found, and the fixture fixed, a wrong
`mov ah, al` rule. Generated code is derived
(under `build/`), never edited by hand, and must pass the DOS fixtures before it counts.

## Display-path demonstration (first Falcon program that shows something)

`src/target/falcon/showframe.s` is **not the game**: it shows one captured DOS frame
(the Poland tactical screen, `tests/fixtures/dos-frame-poland_tactical.*`: 640 x 480
indexed pixels from the oracle's framebuffer, palette recovered from the matching
screendump, 164 of 256 entries used) so the Falcon video path can be measured. It
selects 640 x 480 x 8 with `Setscreen` (VGA `0x1B`, or interlaced PAL `0x12B` on RGB/TV by
`Montype`), uploads the palette with `VsetRGB`, converts chunky to interleaved bitplanes
with `src/common/c2p.s` (`gfx_c2p_groups`, 68000-only, about 2.5 s a frame, unoptimized),
waits for a key and restores the previous mode.

Verified in Hatari (Falcon030, 4 MB, TOS 4.02), both monitor types: the 307,200 video bytes
equal an independent host conversion of the DOS pixels; the readback mode word and
`Physbase` match the request and the Videl base registers; all 256 Videl palette entries
equal the DOS palette (6-bit truncation). Not verified: real hardware, monitor timing
and refresh, whether the picture is stable on a physical VGA/RGB display, the interlaced
mode's visible height. The converter is far too slow for per-frame use.

## Minimum target and resources

Declared initial target is Falcon030, 68030 at 16 MHz, 4 MB ST-RAM,
RGB display; DSP is not required
by these CPU-only geometry functions. No other project target policy is changed.
Common geometry assembly is additionally restricted to 68000 instructions.
The fixture harness reserves a 209,472-byte DOS object-2 arena, an 8 KiB stack
and small fixture/results buffers. This is an isolated test allocation, not a
game memory budget. Full simultaneous resource/framebuffer and simulation
timing budgets remain open; no gameplay performance/Falcon hardware claim.

Completed SET/STM loader snapshots are now
retained in `work/qemu_out/poland-state-1` and described in the loader note.
Next close the GAME001 decoded-unit/state producers, layer-table/allocation
initialization and TACMAP/VESA480 display consumers. SET/STM successful data
consumption is implemented; copied pointer tables are isolated fixture inputs,
not connected boot. Preserve original indexed graphics and the measured viewport.
GAME001's 223 paired reads cover 447 bytes, 22 unit rows and all header fields
(analysis/scenario-fields.md). Naming/derived-unit fields, country/equipment
initialization, map-objective lists and complete parent side effects remain
open. Class setup and its random transition are now implemented prerequisites.
