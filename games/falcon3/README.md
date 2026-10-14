# F030Falcon3 — Falcon 3.0 for the Atari Falcon030

Reverse-engineering and eventual porting project for the DOS flight simulator
*Falcon 3.0*, version 3.05 (Spectrum HoloByte, 1995).

Porting follows [the Comanche-aligned policy](analysis/porting-policy.md):
recovered DOS contracts → DOS-validated JavaScript reference → native 68030,
with RGB565 presentation and measured, parity-checked DSP acceleration. The
project remains reverse-engineering-only; adopting the policy does not establish
a working browser reference or Falcon runtime.

The source distribution currently available in this workspace is
`assets/FALCON3.ISO`. It is local reference material and is intentionally not
part of the repository. The CD contains `FALCON3.RES`, a normal ZIP archive;
the archive contains the installed game tree, including the main
`FALCON3.EXE`.

## Current status — reviewed 2026-10-10

Reverse engineering only: no executable browser game reference or Falcon game
runtime is present. The original RTLink overlay directory, loader reads, thunk
dispatch, caller reload and overlap eviction have DOS-backed records in
[analysis/executable.md](analysis/executable.md). Resource/music inventories
are analysis evidence, not implemented Falcon playback or gameplay.

The next porting boundary is a connected DOS route with recovered function
contracts, JavaScript fixtures and a matching native slice. This review did
not rerun the original or establish a new supported route.

## First setup

Run these commands from the project root after placing the legally obtained CD
image at `assets/FALCON3.ISO`:

```text
tar -xf assets/FALCON3.ISO -C game/cd
python tools/extract_resources.py
python tools/re/mzinfo.py game/FALCON3/FALCON3.EXE
```

`extract_resources.py` verifies every ZIP member CRC before writing the
derived installed tree to `game/FALCON3/`. The tree is ignored because it can
be recreated from the image.

## Disassembly starting point

The main executable is a 16-bit MZ program with a 0x2C00-byte header and a
0x1FB51-byte DOS load image. It has 2,717 relocation records and another
0x12FA96 bytes after the MZ image. Its RTLink v1 directory, on-disk segment
chain and loader read contract are resolved against the DOS oracle, including
the nine bytes the last record declares past end of file. Thunk dispatch,
caller reload and overlap eviction are resolved too. Do not treat the tail as code at a fixed
address; see `analysis/executable.md`.

The MZ entry is `1AA3:076C`, file offset `0x1DD9C`. Once the resource tree is
present, the first conservative listing is:

```text
New-Item -ItemType Directory -Force work/listings
python tools/re/disasm.py game/FALCON3/FALCON3.EXE `
  --no-inline-detect -o work/listings/FALCON3.lst
```

`re/seeds.txt` is reserved for targets supported by evidence. The first
listing is a map of the MZ load image only; overlay work belongs in
`analysis/executable.md` and its follow-up documents.

## DOS oracle

The shared QEMU/MS-DOS harness lives in `work/` and is synchronized from
`../F030Method/dos/`. After genuine MS-DOS 6.22 installation floppies have
been supplied under `img/`, build a bootable image with:

```text
python work/build_dos_hdd.py
python work/run_qemu.py --timeout 60 --shot 20
```

The per-game image builder copies the extracted `game/FALCON3/` tree to
`C:\FALCON3`. It does not modify the CD image or the extracted reference.

## Layout

The [music inventory](analysis/music.md) records the 150 music resources,
preliminary event demand, six strict-reader rejections and the fragmented
Roland initialization data. It defines the next standalone music experiment;
Falcon music playback and game integration remain unverified.

```text
assets/       supplied CD image, local and ignored
game/cd/      extracted CD contents, derived and ignored
game/FALCON3/ installed resource tree, derived and ignored
analysis/     measured container and format notes
re/           evidence-carrying disassembly seeds
tools/re/     MZ and 16-bit x86 analysis helpers
work/         shared DOS oracle plus per-game build/scratch scripts
```

Read [`../F030Method/METHOD.md`](../F030Method/METHOD.md) and the generated
[`analysis/cross-project.md`](analysis/cross-project.md) before changing the
analysis model.
