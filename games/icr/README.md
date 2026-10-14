# F030ICR — IndyCar Racing for the Atari Falcon030

Reverse-engineering and eventual porting project for Papyrus's *IndyCar
Racing*, using the supplied v1.05 three-disk DOS distribution.

The floppy images in `assets/` are immutable local reference material. The
installed game tree belongs under `game/` and is derived from those images;
generated listings, DOS images and probes belong under `work/`.

## Current status — reviewed 2026-10-10

Reverse engineering only: no JavaScript game reference or Falcon runtime exists.
The supplied disks now produce a verified base install and eight separate track
trees. `game/installed/INDYCAR.EXE` is the authority, established from the
launcher/install records and identified by hash in
[analysis/executable.md](analysis/executable.md).

Original DOS execution reaches copy protection, menus, track selection and a
practice cockpit; scripted input drives the car out of the pits. The runtime
mapping, live framebuffer/palette and self-modifying textured-span hot loop
are identified. Polygon setup, scene/camera ownership and full race/input/replay
contracts remain open. See [analysis/runtime.md](analysis/runtime.md),
[analysis/menu-flow.md](analysis/menu-flow.md) and
[analysis/renderer.md](analysis/renderer.md). These are observations of DOS,
not native gameplay. This review did not rerun them.

## First setup

Preserve each disk boundary and the per-track directory layout. The install
reconstruction is recorded in [analysis/installer.md](analysis/installer.md),
with source/installed hashes in `analysis/`. `UCC.EXE`, `SD.EXE` and
`INSTALL.EXE` are support programs; the game authority is `INDYCAR.EXE`.
Reproduce the derived install from the supplied disks with:

```text
python tools/re/extract_media.py
python tools/re/merge_indycar.py
python tools/re/extract_install.py
```

Keep the separate track expansion described in
[analysis/tracks.md](analysis/tracks.md); flattening those repeated filenames
caused the original game's disk error.

The shared method and generated technique ledger are authoritative:
[`../F030Method/METHOD.md`](../F030Method/METHOD.md) and
[`analysis/cross-project.md`](analysis/cross-project.md).

## DOS oracle

The shared QEMU/MS-DOS harness is in `work/`. The per-game builder is configured
for `game/installed`, `game/tracks` and HIMEM/XMS without EMS; it is no longer an
unfilled skeleton. With the recorded genuine MS-DOS 6.22 media available, run:

```text
python work/build_dos_hdd.py --no-boot
python work/run_qemu.py --timeout 60 --shot 20
```

The builder is seeded by `python ../F030Method/dos/sync.py --init F030ICR`.
Its shared files are synchronized from `../F030Method/dos/`; do not edit those
copies directly.

## Layout

```text
assets/       supplied floppy images, local and ignored
game/         exact extracted/install tree, derived and ignored
analysis/     measured media, executable and runtime notes
re/           evidence-carrying disassembly seeds
work/         shared DOS oracle plus per-game build/listing/scratch files
```

