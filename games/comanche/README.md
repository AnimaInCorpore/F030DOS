# F030Comanche

An Atari Falcon030 porting and reverse-engineering project for *Comanche:
Maximum Overkill*.

The long-term rendering target is a VoxelSpace-style height-field renderer
accelerated by the Falcon's Motorola DSP56001. The 68030 remains responsible
for the game, input, resource, UI, and video-control work while the DSP handles
the predictable ray-marching and terrain-span workload.

The CPU renderer follows the recovered DOS terrain walk and resource tables;
the DSP is an accelerator for that same result.

Stock Falcon/68030 remains the primary target (currently 14 MB ST-RAM).
`TARGET_CPU=68060 bash tools/build-run.sh` builds a separate accelerator image
in `release/68060/`; the same prefix on `tools/run.sh` selects it in Hatari.
The default build keeps native 68030 arithmetic. The 68060 image uses exact
multiword products and explicit cache publication, preserving DOS fixed-point
semantics. See [CPU compatibility and validation](analysis/functions/cpu-compatibility.md)
for requirements and the distinction between numerical fidelity and RGB565
presentation conversion.

The hashed DOS executable and captured execution are the behavioural authority.
Every represented function requires a DOS contract/difference record and a
deterministic browser reference counterpart before entering a supported route;
this is a requirement, not a completed implementation-wide audit. The browser harness is used to
exercise and compare a route already traced in DOS before the Falcon port, then
to compare DOS → browser → target fixtures. Neither its Canvas output nor the
Falcon code may overrule the DOS result. Its file boundary is a virtual DOS
filesystem: the
browser stores binary assets in IndexedDB and keeps only hashes/profile metadata
in `localStorage`.

The Falcon source tree was recreated for the CPU attract milestone. Its
source-selection record is `analysis/functions/falcon-attract.md`: the DOS
route was traced first with QEMU TCG `exec,nochain`. Later slices added menus,
live command keys, weapons/damage, mission-end and pilot/briefing logic, and
the digital effect layer. Their existence does not certify a complete playable
mission or close the implementation-wide DOS-fidelity gates. The DSP terrain
renderer remains dormant; the DSP plays the music only in an `OPL2=1` build.
Nothing has run on a real Falcon yet: `HWTEST=1` builds an image that writes a
measurement report, and [docs/HARDWARE-TEST.md](docs/HARDWARE-TEST.md) is the
procedure for the 68060 image's first hardware run.
[docs/PLAYING.md](docs/PLAYING.md) is the player's guide: installation, setup
and keys (packed as `COMANCHE.TXT` in the F030DOS release).

## Priority focus

The first recreation milestone is the DOS attract cycle: its authored opening
screens, selected terrain/sky resources, `DEMO<n>.SCR` replay, terrain renderer,
fixed console, and authored flight HUD. That milestone is now runnable in
`jsComanche/` as a browser implementation tied to the retained DOS fixtures;
its explicit logical-tick scheduler uses a labelled 60 Hz fixture clock
because the DOS wall-clock cadence is still Unproven. The Falcon DOS-route
recreation is present. Complete-frame comparisons have been made and later
renderer corrections are recorded; full-frame/sequence acceptance and real
hardware validation remain open. Selected state equality is component evidence.

Each Falcon subsystem must map back to documented DOS flat addresses, data
contracts, or runtime observations. The project does not mechanically
translate x86 instructions and does not wait for a speculative 100%
disassembly; it recovers, ports, and compares one complete vertical slice at a
time.

See [docs/PORTING-PLAN.md](docs/PORTING-PLAN.md) for the governing roadmap and
[docs/X86-M68K-MAP.md](docs/X86-M68K-MAP.md) for the translation index. DSP
terrain acceleration remains the long-term renderer target, but resumes only
after the corresponding CPU behaviour is correct and measurable.

## Faithful DOS-source rule

Port the behaviour of the hashed DOS binary, not the disassembly text. Falcon
code may use native registers, layouts, and platform interfaces, but it must
implement the same mechanics, data, fixed-point arithmetic, sequencing, and
observable results. Missing contracts are recovered from further DOS evidence
or left stopped or dormant; they are never filled with synthetic data, guessed
behaviour, or a selectable alternative.

## Route-first milestone rule

Before creating or changing JavaScript or M68k source for a milestone, trace
that milestone's actual route through the authoritative DOS executable. Use
QEMU's TCG `exec,nochain` execution extension and repeatable inputs to enumerate reached entries,
indirect callbacks, resource reads, state transitions, and frame order; retain
the trace report and state snapshots as the milestone route record. Only then
create the JavaScript and M68k sources whose contracts are on that route, with
each source linked to its DOS function record and map row. A function that is
not reached or not yet explained remains dormant/`Unproven` and cannot support
the milestone. Browser experiments and Falcon code validate the traced route;
they do not define it.

## Project status — reviewed 2026-10-10

**Overall acceptance remains NOT CERTIFIED.** The CPU attract implementation
includes opening screens, replay-driven flight, terrain/sky, objects/effects,
console/MFD/HUD and page publication, with an executable JavaScript reference.
Native extensions now include pilot/main/campaign/mission menus and briefing,
live command keys, weapons, player damage and mission-end statistics/debrief.
The browser has DOS-backed contracts for many of these functions; it is not a
general playable mission runtime. Pointer selection and other integration and
behaviour gaps remain recorded in [docs/PORTING-PLAN.md](docs/PORTING-PLAN.md).

The digital effect layer is wired into the native game. Isolated DOS/JS/native
mixer and Hatari DMA checks are recorded in
[analysis/functions/sound-falcon.md](analysis/functions/sound-falcon.md).
The music driver (`src/music.s`) is ported and wired in; it replays the
original's OPL2 captures write for write (`tools/check-falcon-music.py`). The
default build has no synthesiser, so only the digital effects sound; an
`OPL2=1 TARGET_CPU=68060` build plays the music through F030OPL2's DSP kernel
(linked from `../F030OPL2`, GPL-3.0, not part of this repository), with the
effects mixed into its stream. Physical Falcon audio remains unproven. This later-phase
work does not broaden the first silent playable acceptance scope; networking
remains deferred and DSP terrain acceleration remains dormant.

The shared checkpoint comparator now rejects missing fields on both sides.
Its retained JavaScript/DOS DEMO1 comparison passes 284 records; cached native
traces are stale and remain Unproven until recaptured for their source/build
identity. See [the shared implementation record](../F030Method/analysis/stearcade-implementation.md).
Full function mapping, complete frames/sequences, live input/cadence and real
stock/accelerator validation remain open. The browser clock is a labelled fixture.

[docs/ACCEPTANCE-REPORT.md](docs/ACCEPTANCE-REPORT.md) is the retained generated
2026-09-22 snapshot, not a certification of today's source. Its results are bound
to the hashes in that report. Reproduce with `python3 tools/acceptance-report.py`
after refreshing the required captures; documentation review alone does not
refresh evidence or promote a supported route.

## Architecture

The port is deliberately split into three layers:

| Area | Responsibility |
|---|---|
| `src/` | CPU attract and live/menu/combat/debrief extensions, plus digital effects; DSP remains dormant |
| `tools/` | Falcon build/run harness, DSP build wrapper, framebuffer capture, and generic DOS RE helpers |
| `reference/f030f29/` | Copied F29 Retaliator source and documentation used as comparison material; it is not part of the Comanche build |

The planned frame path is:

1. The 68030 reads input, advances game state, and prepares camera parameters.
2. The 68030 submits one compact frame command to the DSP through the Falcon
   host interface.
3. The DSP ray-marches the heightmap, applies the VoxelSpace occlusion buffer,
   and produces terrain pixels or column spans.
4. The 68030 presents the completed back buffer through VIDEL and draws the
   HUD, objects, and other non-terrain elements.

The DSP design assumes optional expanded X/Y memory for local heightmap and
colour-map data. The CPU renderer remains the correctness reference and the
runtime fallback when the DSP is unavailable.

## Build and run

For the current browser attract milestone, serve the repository root and open
`http://localhost:8000/jsComanche/`:

```bash
python3 -m http.server 8000
```

The page reads only the installed DOS tree under
`assets/extracted/comanche_hdd/`; missing or malformed files stop the attract
runtime. It renders the authored opening sequence and recorded terrain flight,
but does not provide speculative live flight controls or a synthetic
terrain/object fallback.

The Falcon CPU-only source tree is active, so the Falcon build/run commands
below assemble and run the traced attract slice. DSP commands remain separate
and are not part of this supported link.

Run these commands from Git Bash or another POSIX-like shell because the build
scripts are Bash scripts:

```bash
bash tools/build-run.sh
bash tools/run.sh
bash tools/grab-frame.sh 5000 build/frame.png
```

The repository includes local copies of vasm, vlink, Hatari, a TOS 4.02 ROM,
DOSBox, and the DSP56001 assembler tools. Hatari also needs the MSYS2 UCRT
runtime on `PATH`; the supplied run/capture scripts set the development-machine
path used by the copied Hatari build.

The DSP build currently contains a host-interface echo/acknowledge stub. It
does not render terrain yet, but it assembles into `release/comanche.lod` with:

```bash
bash tools/build-dsp.sh
```

Select another DSP source when experimenting:

```bash
DSP_SOURCE=src/dsp/experiment.asm bash tools/build-dsp.sh
```

Tool paths can be overridden with `VASM`, `VLINK`, `HATARI`, `TOS`, `DOSBOX`,
and `ASM56K`. See [docs/FALCON-TOOLCHAIN.md](docs/FALCON-TOOLCHAIN.md) for the
local toolchain layout.

The emulator is intentionally started with a generous development memory size.
The eventual release target is much tighter, so memory use must be checked
separately against the intended Falcon configuration.

## DOS reverse engineering

Keep a legally obtained DOS distribution outside committed output. The
archive is a three-disk FAT12 distribution; the extraction layers and measured
code/data sizes are recorded in
[docs/ASSET-INVENTORY.md](docs/ASSET-INVENTORY.md).

The ready-to-copy installed game directory is generated at
`assets/extracted/comanche_hdd/`. Copy it to a DOS hard disk as
`C:\COMANCHE\`. The original archive and all generated game data remain
ignored and are not committed.

Do not disassemble the packed executable directly. First unpack the installed
main executable with a standard `UNLZEXE` implementation:

```bash
unlzexe assets/extracted/comanche_hdd/COMANCHE.EXE \
  re/unpacked/COMANCHE.UNPACKED.EXE
python tools/re/mzinfo.py re/unpacked/COMANCHE.UNPACKED.EXE
python tools/re/codemap.py re/unpacked/COMANCHE.UNPACKED.EXE
python tools/re/disasm.py re/unpacked/COMANCHE.UNPACKED.EXE \
  --seed 0000:09BC
```

See [docs/RE-WORKFLOW.md](docs/RE-WORKFLOW.md) for the working procedure.
The F29-specific archive, model, sound, and renderer decoders in
`tools/re/reference_f29/` are adaptation examples only; do not assume their
formats are Comanche formats without evidence.

## Repository notes

- `build/` and `release/` contain generated files.
- No byte of the original is committed or built into the program:
  `src/origexe.s` reads the original's tables from the player's
  `COMANCHE.EXE` at startup and `src/dtl.s` the ring tables from the
  selected .DTL ([record](analysis/functions/falcon-attract.md#original-data-loader)).
  `tools/build-run.sh` stages `COMANCHE.EXE` with the other runtime files.
  `tools/prepare-original-test.py` writes the assembled `build/port_tables.s`
  (constants and storage only) and, from the local install, the host
  reference `build/original_test.s`; `tools/check-orig-exe-load.py` checks
  the loaded tables against it in Hatari.
- `src/README.md` documents the active Falcon source tree.
- `tools/README.md` documents the helper scripts.
- [docs/PORTING-PLAN.md](docs/PORTING-PLAN.md) is the priority project roadmap.
- [docs/X86-M68K-MAP.md](docs/X86-M68K-MAP.md) maps recovered DOS behaviour to
  Falcon code.
- [PORTING.md](PORTING.md) is the implementation guide for the DSP-assisted
  VoxelSpace renderer after CPU correctness and profiling gates are met.

## License

Copyright (C) 2026 Sascha Springer.

The port's own work in this repository - the Falcon sources, the JavaScript
reference, the tools and scripts, the analysis records and the documentation -
is free software under the GNU General Public License, version 3 or (at your
option) any later version; see [COPYING](COPYING). It is distributed in the
hope that it will be useful, but WITHOUT ANY WARRANTY. The licence matches
F030OPL2's, so an `OPL2=1` build, which links F030OPL2's decoder, stream host
and DSP kernel, can be distributed as one GPL-3.0-or-later program; whoever
distributes it must offer the corresponding source of both (this repository's
or F030DOS's `games/comanche`, and `../F030OPL2`) at the commits it was built
from.

Not covered, because they are not the port's to license:

- *Comanche: Maximum Overkill* itself (NovaLogic, 1992): its program, data,
  music and text. None of it is in this repository or in the program; the
  program reads the player's own copy at startup. The sources and records
  cite the original's addresses, constants and short code fragments by design;
  the licence grants no rights in the original.
- Third-party tools and documents kept here for convenience, under their own
  terms: `tools/toolchain/` (assemblers, DOSBox, Hatari, a TOS ROM), the
  Motorola manuals `docs/M68000PRM.pdf` and `docs/MC68000UM.pdf`, and the
  F29 documents copied into `reference/f030f29/`, which follow F030F29's
  terms (no licence chosen there yet).
- F030OPL2, which keeps its own copyright and licence notices.
