# F030Links386 — Links 386 CD for the Atari Falcon030

Reverse-engineering and eventual porting project for the DOS golf game
*Links 386 CD*, version 2.00 (Access Software, 1995).

The supplied source image is
`assets/Links 386 CD (1995)(Access Software).iso`. It is local reference
material and is intentionally not part of the repository. The CD root carries
the installed game executable `LCD.EXE`, the launch scripts, and the installer
manifest.

## Current status — reviewed 2026-10-10

Reverse engineering only; no browser game reference or Falcon runtime exists.
The appended P3/EXP structure and packed-image expansion are recovered, and
the DOS startup trace reaches the MZ/EXP loader path. Course-record headers
and MDmd resources are partially decoded.

The current execution blocker is a documented QEMU CS-segment-override defect,
isolated by `work/segtest/`. The resulting `10049` fault is not evidence of game
behaviour. A correct emulator must pass that reproducer before execution past
the gate is trusted. See [analysis/executable.md](analysis/executable.md),
[analysis/resource-formats.md](analysis/resource-formats.md) and
[AGENTS.md](AGENTS.md#current-next-steps). This review did not retest candidate
emulators or promote a port slice.

## First setup

Run these commands from the project root after placing the legally obtained CD
image at the path above:

```text
python tools/extract_cd.py
python tools/re/mzinfo.py game/cd/LCD.EXE
python tools/stage_install.py
```

`extract_cd.py` creates the pristine, derived CD tree at `game/cd/` using the
system `tar` ISO reader. `stage_install.py` copies the files named by the
CD's `[MIN_INSTALL]` section in `INSTALL.INI` to `work/install/LINKS386/` for
static analysis and the DOS oracle. Neither script modifies the source image.

## Disassembly starting point

`LCD.EXE` is an MZ executable with a 0x1400-byte header and entry `0020:0000`
at file offset `0x1600`. Its DOS-mapped MZ image ends at `0x2C524`; the
0x5D747 bytes after that boundary are not assigned a fixed runtime address yet.
The file contains a `DOS/4G` banner, so the protected-mode loader and the
appended payload must be understood before a flat 32-bit listing is trusted.

The first conservative listing is the 16-bit MZ load image only:

```text
New-Item -ItemType Directory -Force work/listings
python tools/re/mzinfo.py game/cd/LCD.EXE --dump-load work/listings/LCD.load
ndisasm -b 16 -o 0x1400 work/listings/LCD.load > work/listings/LCD-loader.lst
```

If `ndisasm` is unavailable, the repository's Capstone-based equivalent is:

```text
python tools/re/disasm16.py work/listings/LCD.load --origin 0x1400 --output work/listings/LCD-loader.lst
```

The appended region is a stream of two Phar Lap `P3` records. Audit and split
their load images with:

```text
python tools/re/p3info.py game/cd/LCD.EXE --offset 0x2C524 --all --dump-load-dir work/listings
```

The second record is packed. Expand it before fixed-address 32-bit
disassembly:

```text
python tools/re/exp_unpack.py game/cd/LCD.EXE --offset 0x2FC5F \
  --output work/listings/LCD.exp1.expanded.load
python tools/re/disasm32.py work/listings/LCD.exp1.expanded.load \
  --origin 0 --offset 0x7F064 \
  --output work/listings/LCD.exp1-entry32-expanded.lst
```

The helper validates that the packed `0x59E0C`-byte load image expands to the
P3 header's declared `0x9AA84`-byte memory image.

`re/seeds.txt` is reserved for indirect targets supported by evidence. Keep
protected-mode and appended-region seeds out until their address model is
measured. Read [`../F030Method/METHOD.md`](../F030Method/METHOD.md) and the
generated [`analysis/cross-project.md`](analysis/cross-project.md) first.

## DOS oracle

The shared QEMU/MS-DOS harness is synchronized into `work/`. After genuine
MS-DOS 6.22 installation floppies have been supplied under `img/`, build a
bootable image with:

```text
python work/build_dos_hdd.py --no-boot
python work/run_qemu.py --timeout 60 --shot 20
```

The builder copies the minimum installed tree to `C:\LINKS386`. The CD video
and course payloads remain outside the first image; add them only when a test
requires them.

## Layout

```text
assets/       supplied CD image, local and ignored
game/cd/      exact CD extraction, derived and ignored
analysis/     measured container and format notes
re/           evidence-carrying disassembly seeds
tools/        CD extraction, install staging and MZ helpers
work/         shared DOS oracle plus per-game build/listing/scratch files
```
