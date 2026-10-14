# F030MagicCarpet — Magic Carpet for the Atari Falcon030

Reverse-engineering and eventual porting project for Bullfrog's DOS game
*Magic Carpet* (1994), using the supplied Magic Carpet Plus (1995) distribution.

The source archive is `assets/Magic_Carpet_Plus_1995.zip`. It is immutable local
reference material and is intentionally not part of the repository. The archive
contains the executable, DOS/4G runtime, game data, levels, intro/movie data and
the small CD-side tree.

## Current status — reviewed 2026-10-10

Reverse engineering only: no browser game reference or Falcon runtime exists.
MZ/LE container arithmetic, object/page maps and fixup decoding are recorded;
live byte matches establish protected-mode placement. Demand loading and an
internal fixup's runtime meaning remain open. Screen/palette, font, sprite and
animation families have decoded contracts.

Original startup currently stops at its DOS mouse-driver check. Reproduce the
next title/menu/game transition with the required driver before deriving game
contracts or beginning a port slice. See [analysis/executable.md](analysis/executable.md),
[analysis/qemu-boot.md](analysis/qemu-boot.md) and
[analysis/resources.md](analysis/resources.md). This review did not rerun the
original or change evidence grades.

## First setup

From the project root, after the supplied archive is present:

```text
python tools/extract_archive.py
python tools/re/mzinfo.py game/MagCarp/CARPET/CARPET.EXE
python tools/re/mzinfo.py game/MagCarp/CARPET/CARPET.EXE --dump-load work/listings/CARPET.mz.load
```
`extract_archive.py` verifies every ZIP member CRC before writing the exact,
derived tree under `game/`. Neither script modifies the source archive.

## Disassembly starting point

`CARPET.EXE` is a Watcom DOS/4G executable with a small 16-bit MZ loader and a
protected-mode LE image. The MZ image ends at file offset `0x2992`; the LE
header begins at `0x2998`. Start with the MZ loader only:

```text
New-Item -ItemType Directory -Force work/listings
python tools/re/mzinfo.py game/MagCarp/CARPET/CARPET.EXE --dump-load work/listings/CARPET.mz.load
ndisasm -b 16 -o 0x0 work/listings/CARPET.mz.load > work/listings/CARPET-loader.lst
```

The MZ entry is `0000:0216`, at file offset `0x276`, or offset `0x216` in the
headerless load dump. `re/seeds.txt` is reserved for indirect targets supported
by evidence. The LE object table, page map, fixups and measured placement are
now recorded in [analysis/executable.md](analysis/executable.md); use that map
for bounded 32-bit listings rather than inferring an origin from bytes.

Read [`../F030Method/METHOD.md`](../F030Method/METHOD.md) and the generated
[`analysis/cross-project.md`](analysis/cross-project.md) before widening the
analysis.

## DOS oracle

The shared QEMU/MS-DOS harness is synchronized into `work/`. After genuine
MS-DOS 6.22 installation floppies have been supplied under `img/`, build a
bootable image with:

```text
python work/build_dos_hdd.py --no-boot
python work/run_qemu.py --timeout 60 --shot 20
```

The builder stages the extracted game tree as `C:\CARPET` and the CD-side
files as `C:\CARPET.CD`. Add `--run-game` to the builder only when a runtime
experiment is intended; the default boot path exits through `QUIT.COM`.

## Layout

```text
assets/       supplied archive, local and ignored
game/         exact archive extraction, derived and ignored
analysis/     measured container and data-format notes
re/           evidence-carrying disassembly seeds
tools/        archive extraction and MZ/LE audit helpers
work/         shared DOS oracle plus per-game build/listing/scratch files
```
