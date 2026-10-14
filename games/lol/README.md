# F030LOL — Lands of Lore: The Throne of Chaos for the Atari Falcon030

Reverse-engineering and eventual porting project for the DOS game *Lands of
Lore: The Throne of Chaos* (Westwood Studios, 1993/1994).

The supplied source image is `assets/LOL_CD_001.iso`. It is immutable local
reference material. The English CD runtime is
`game/cd/DATA/ENG/LANDS.EXE`; the installed DOS variant is
`game/cd/DATA/HARDRIVE/MAIN.EXE`. Keep those executables separate until their
differences and loader contracts are understood.

## Current status — reviewed 2026-10-10

Reverse engineering only: no browser game reference or Falcon runtime exists.
The CD executable's TDS debug tail, resident startup resource-loading chain,
EMC2 script framing/control flow and palette-blend lookup have analysis records.
The blend reconstruction is exact over its recorded lookup range; that asset
result does not validate a game route.

The next work is original-run startup/resource-loading evidence and DOS-backed
dynamic script targets/system-call contracts, then the first connected browser
and native slice. See [analysis/resource-loading.md](analysis/resource-loading.md),
[analysis/emc2.md](analysis/emc2.md), [analysis/blend.md](analysis/blend.md) and
[AGENTS.md](AGENTS.md#current-next-steps). This review did not run the DOS game.

## First setup

From the project root, after the supplied ISO is present:

```text
python tools/extract_cd.py
python tools/re/mzinfo.py game/cd/DATA/ENG/LANDS.EXE
python tools/re/mzinfo.py game/cd/DATA/HARDRIVE/MAIN.EXE
python tools/stage_install.py
```

`extract_cd.py` creates the pristine, derived ISO tree under `game/cd/`.
`stage_install.py` creates an ignored English DOS install under
`work/install/LANDS/`; neither script modifies the source image.

## Disassembly starting point

The English `LANDS.EXE` is a 357,509-byte 16-bit MZ executable. Its header is
0x2800 bytes, the DOS-mapped image ends at 0x23B00, and 0x33985 bytes follow
that image. The appended region is identified as Borland C++ TDINFO/TDS v3.16
debugger data and excluded from the load image; its compact coverage and
optimization tables are decoded by `tools/re/tdinfo.py`. The MZ entry is
`0000:0000`, at file offset 0x2800. The first
listing must cover only the MZ load image.

```text
New-Item -ItemType Directory -Force work/listings
ndisasm -b 16 -o 0x2800 -e 0x2800 -k 0x23B00,0x33985 `
  game/cd/DATA/ENG/LANDS.EXE > work/listings/LANDS-loader.lst
```

`re/seeds.txt` is reserved for indirect targets supported by evidence. Read
[`../F030Method/METHOD.md`](../F030Method/METHOD.md) and the generated
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

The builder stages the installed DOS variant as `C:\LANDS` and configures
HIMEM/XMS. The first runtime goal is startup and the title/menu path; the
CD-backed executable and any CD-ROM dependency remain separate test cases.

## Layout

```text
assets/       supplied CD image, local and ignored
game/cd/      exact ISO extraction, derived and ignored
analysis/     measured container and data-format notes
re/           evidence-carrying disassembly seeds
tools/        ISO extraction, install staging and MZ audit helpers
work/         shared DOS oracle plus per-game build/listing/scratch files
```
