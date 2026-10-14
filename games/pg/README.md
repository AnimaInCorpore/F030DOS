# F030PanzerGeneral — Panzer General for the Atari Falcon030

Reverse-engineering and eventual porting project for SSI's *Panzer General*
(1994), using the supplied six-disk DOS archive.

The ZIP and its floppy images in `assets/` are immutable local reference
material. The installed game tree belongs under `game/` and is derived from
those images; generated listings, DOS images and probes belong under `work/`.

## Current status — reviewed 2026-10-10

No playable route is supported. The JavaScript reference and native m68k
harnesses pass retained DOS contracts for geometry, the successful Poland
SET/STM loader and strings, RNG/unit classes, and bounded drawing/composition.
A Falcon display demonstration presents a captured Poland tactical screen;
it does not execute a connected scenario or turn loop. The browser is a contract
lab, not a playable game.

GAME001 state producers, initialization/input/timers, movement, attacks, turn
completion and campaign flow remain open. The bounded translator now uses
shared conservative flag analysis, source-PC maps and checkpoint diagnostics;
its synthetic cycle reduction does not establish a game-speed gain or new
supported functions. See [docs/PORTING-PLAN.md](docs/PORTING-PLAN.md),
[analysis/x86-flag-validation.md](analysis/x86-flag-validation.md) and the
shared [implementation record](../F030Method/analysis/stearcade-implementation.md).
This documentation review does not rerun native or DOS acceptance checks.

## First setup

Verify the outer ZIP member CRCs, preserve all six disk images and keep the
patch disk separate from the base distribution. Extract the FAT12 images
without flattening their boundaries, then record the archive, disk and
extracted-file hashes in `analysis/`. Establish the selected executable and
build variant from the shipped installer/launcher before disassembling; do not
silently mix patched and unpatched executables or resource trees.

The shared method and generated technique ledger are authoritative:
[`../F030Method/METHOD.md`](../F030Method/METHOD.md) and
[`analysis/cross-project.md`](analysis/cross-project.md).

## DOS oracle

The shared QEMU/MS-DOS harness is in `work/`; the per-game builder is configured
for the recovered unpatched tree. The game requires a DOS mouse driver to
install its startup timer callback. Stage the pinned CuteMouse binary using
the identity and recipe in [analysis/executable.md](analysis/executable.md#driver-identity-and-staging),
then run with the DOS-generated no-sound configuration:

```text
python3 work/build_dos_hdd.py --use-no-sound --run-game --hold --no-boot
python3 work/run_qemu.py --timeout 28 --key 8:spc --key 12:spc --key 16:spc --shot 26
```

This reaches the original game's main menu. `--without-mouse` reproduces the
previous SSI splash stall; `--out` selects a separate working disk. The project
has begun the JavaScript reference and native Falcon port with geometry,
the successful Poland SET/STM loader and its string helpers, validated
against shared DOS fixtures. The connected game is not
yet playable; see [the port plan](docs/PORTING-PLAN.md).

The original can also enter the standalone Poland scenario through captured
keyboard/PS/2 input. See [the scenario route](analysis/scenario-route.md) for
its replay schedule, tactical-map checkpoints and measured resource requests.

The builder was seeded by
`python ../F030Method/dos/sync.py --init F030PanzerGeneral`. Its shared files
are synchronized from `../F030Method/dos/`; do not edit those copies directly.

## First port contracts

`node tests/geometry-reference.mjs` checks 12 captured DOS fixtures against
the JavaScript functions. `python3 tools/check-native-geometry.py --out
build/geometry-native-new` builds a 68000-restricted native contract executable
and checks the same outputs in 4 MB Falcon030 Hatari. Use a fresh output path.
The native toolchain is pinned by content hashes in the result metadata; the
default provider is F030Arcade's macOS vasm/vlink, overridable with VASM/VLINK.

`node tests/loader-reference.mjs` checks the Poland loader's globals, six
arrays and all 23 reads, plus 52 direct string contracts. Run
`python3 tools/check-native-loader.py --out build/loader-native-new` for the
same DOS outputs under 4 MB Falcon030 Hatari. This is an isolated contract
harness; GAME001 decoding, initialization and rendering integration remain open.
The scenario unit-class routine and DOS random-state helpers also have native
and JavaScript counterparts. `node tests/rng-reference.mjs` and
`node tests/unit-classes-reference.mjs` check their shared DOS fixtures;
`tools/check-native-rng.py` and `tools/check-native-unit-classes.py` run the
native checks with a fresh `--out` directory. Final seed equality is checked
alongside class bytes, so later simulation consumes the same random state.

Serve the repository root with `python3 -m http.server 8087 --bind 127.0.0.1`
and open `/web/` for the browser contract lab. It checks the reference; it is
not the playable phase-4 deliverable. Original assets remain local and pristine.

## Layout

```text
assets/       supplied ZIP, local and ignored
game/         exact extracted/install tree, derived and ignored
analysis/     measured media, executable and runtime notes
re/           evidence-carrying disassembly seeds
work/         shared DOS oracle plus per-game build/listing/scratch files
```
