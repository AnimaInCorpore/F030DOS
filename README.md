# F030DOS

DOS games ported to the Atari Falcon030. Each port starts from the shipped DOS
executable: its functions are recovered, their behaviour is measured on the
original running in an emulator (the DOS oracle), checked in a JavaScript
reference, and re-implemented in 68030 code (and DSP56001 code where the
picture or sound needs it). The original's data is read from the player's own
copy at run time; none of it is part of this repository.

This project is developed with AI coding agents (Claude Code): much of the
analysis, tools, runtimes and documentation was written by them under the
author's direction. Correctness is checked against the DOS original rather
than taken on trust; [method/METHOD.md](method/METHOD.md) is the procedure
every port follows.

**Status: preview.** None of the games is complete. No license has been
chosen yet: the code is published for reading, all rights reserved. How the
repository was screened is in [docs/PUBLICATION.md](docs/PUBLICATION.md).

| game | directory | state |
|---|---|---|
| Comanche: Maximum Overkill (1992) | [games/comanche](games/comanche/README.md) | CPU attract plus live-flight, menu, mission-end and combat extensions; JS reference; not certified, DSP renderer dormant |
| F29 Retaliator (1990) | [games/f29](games/f29/README.md) | DSP/blitter scene renderer, flight-state core, custom menu and HUD; original presentation and missions not reproduced |
| Pool of Radiance (1988) | [games/por](games/por/README.md) | title image matches the host expansion at 4 MB and 14 MB; layout, text, dungeon view and scripts open |
| Wing Commander (1990) | [games/wc1](games/wc1/README.md) | title, opening, mission loading, cockpit, fighters, cannon combat and damage; campaign, navigation and missiles unfinished, depth merge unproven |
| Ultima Underworld II (1993) | [games/uw2](games/uw2/README.md) | browser intro/display slice; Falcon RGB565 presenter checked in a smoke harness |
| Panzer General (1994) | [games/pg](games/pg/README.md) | DOS/JS/native loader, geometry, RNG and drawing contracts; static Poland screen; no playable route |
| Ultima Underworld (1992) | [games/uw](games/uw/README.md) | byte-exact executable rebuild, asset recovery, DOS gameplay route; no port slice yet |
| TIE Fighter CD (1995) | [games/tie](games/tie/README.md) | byte-exact executable rebuild, LFD decoding, function identification; no port slice yet |
| Falcon 3.0 (1995) | [games/falcon3](games/falcon3/README.md) | DOS overlay loader, dispatch, reload and eviction recovered; no runtime |
| Links 386 CD (1995) | [games/links386](games/links386/README.md) | P3/EXP recovery and startup loader; DOS execution blocked by an emulator defect |
| Lands of Lore (1994) | [games/lol](games/lol/README.md) | startup/resource analysis, EMC2 script framing, palette blend; no port slice yet |
| Magic Carpet (1994) | [games/magiccarpet](games/magiccarpet/README.md) | LE/fixup recovery, screen/font/sprite formats; original stops at the mouse-driver gate |
| IndyCar Racing (1994) | [games/icr](games/icr/README.md) | install/track layout, DOS practice driving, textured-span hot loop identified; no runtime |

The states follow F030Method's review of 2026-10-10 and each port's own
README; they are measured in the patched Hatari of F030Arcade, not on a real
Falcon. None of the games is complete.

## Download

[Release 0.1-preview](https://github.com/AnimaInCorpore/F030DOS/releases/tag/v0.1-preview):
`F030DOS-0.1-preview.zip` with the Falcon programs of Comanche, F29
Retaliator, Pool of Radiance and Wing Commander and a `README.TXT` (what each
game needs from your copy, each game's state, SHA-256 sums). No game data is
included: copy the files of your own DOS installation next to each program as
`README.TXT` says. Requirements: a Falcon030 with 14 MB of RAM and an RGB or
VGA monitor. Comanche, Pool of Radiance and Wing Commander were checked
against their games' files and contain none of them; F29's program could not
be checked (its game files were not at hand), and `README.TXT` says so.

## Where development happens

This repository is a screened copy. Each port is developed in its own
repository (F030Comanche, F030F29, F030POR, F030WC1, ... next to this checkout) and the
shared method in F030Method; `tools/publication.py` imports their committed
sources and keeps out everything that is the game or derived from it:

- game media, disk images and DOS installation media;
- extracted, unpacked or converted game data, string dumps and recorded
  traces or captures of the original;
- disassembly and decompiler output of the game program, data tables copied
  from it, Ghidra projects and reassembly output;
- vendored third-party trees and binaries (toolchains, ROMs, DOS extenders,
  manuals).

[docs/publication-inventory.json](docs/publication-inventory.json) records the
decision and the reason for every path of every imported commit.

## Layout

    games/<game>/        one port, as imported from its repository
    method/              F030Method: METHOD.md, CROSS-PROJECT.md, the DOS-oracle harness (dos/), validation/
    tools/publication.py import, sync and check the screened copy
    tools/release.py     packs a release
    docs/                publication status and inventory
    Makefile             build / run / release

Links between the ports' documents still use the development layout
(`../F030Method/...`, `../F030Arcade/...`); in this repository F030Method is
`method/`.

## Requirements

- macOS or Linux with `make`, `bash` and Python 3. Comanche's build also needs
  the `capstone` module (`python3 -m pip install capstone`); pass `PYTHON=` if
  it is installed for another Python.
- A checkout of [F030Arcade](https://github.com/AnimaInCorpore/F030Arcade)
  next to this one (`../F030Arcade`, or pass `ARCADE=`): its `third_party/`
  provides vasm, vlink, the DSP56000 assembler, the TOS images and the
  patched Hatari that every run, screenshot and measurement uses.
- Your own copy of each game, placed as the port's README describes (usually
  `games/<game>/assets/`, which is ignored).

## Build and run

```sh
make list                 # the ports, their programs and what they need
make f29                  # games/f29/release/f29.tos and 3d.lod
make run-f29              # run it in the patched Hatari
make comanche             # needs games/comanche/assets/extracted/comanche_hdd and re/unpacked (see its README)
make por                  # por.tos; make -C games/por data falcon-data converts your copy into PORCACHE
make wc1                  # wc1.tos; make -C games/wc1 data unpacks your disks into WC1DATA
```

## Release

```sh
make release VERSION=0.1  # release/F030DOS-0.1/ and release/F030DOS-0.1.zip
```

Put each game's files where its README says first (`games/<game>/assets/`,
or the extracted folders the port names), so the check below can run; a game
whose files are absent is packed with "not checked" in `README.TXT`.

`tools/release.py` builds the ports that have a Falcon program, checks each is
a TOS executable, compares it with the game files present locally (any
32-byte block of the game inside a program stops the release; blocks with
fewer than 8 distinct byte values and counting sequences are ignored) and writes a
`README.TXT` with what each player has to supply, each game's state and the
SHA-256 of every file. No game data is packed.

Then tag `v<version>` and attach the zip to a GitHub release (`gh release
create v<version> release/F030DOS-<version>.zip`) with short notes: what is
new, what is fixed, and how it was measured. Update the Download section
above in the same commit as the tag.

## Keeping the copy current

```sh
make status                               # imported commit vs. each repository's HEAD
python3 tools/publication.py sync comanche          # dry run: what would change
python3 tools/publication.py sync comanche --apply  # copy / merge / withdraw, update the inventory
python3 tools/publication.py stage                  # index exactly the candidates
make check                                # mechanical publication checks
```
