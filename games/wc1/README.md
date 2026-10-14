# Wing Commander 1 for Atari Falcon

This repository is the beginning of a native Atari Falcon030 port of the 1990
DOS version of *Wing Commander 1*. The hashed DOS `WC.EXE` binary and captured
DOS execution are the behavioural authority. The source reconstruction in the
sibling [`wc1-re`](../wc1-re) tree is graded supporting evidence, and
[`F030Comanche`](../F030Comanche) is a Falcon 68030/Videl implementation
reference; neither can overrule the DOS result.

`wc1-re` reconstructs the game **as shipped in the 1996 *Kilrathi Saga* Win32
re-release**, not the 1990 DOS build this port targets and whose data files it
loads. Its fidelity is graded per function (`make report` scores machine-code
similarity against the retail executable), not uniform. The delta is
unmeasured rather than known to be small. Every browser or Falcon function
therefore requires a `METHOD.md` §4.2 record with its DOS identity/contract/fixtures
and a difference ledger; `analysis/wcexe.md` provides the binary evidence that
adjudicates the record. This requirement does not certify existing code.

## Current status — reviewed 2026-10-10

The native title/flight/combat prototype is substantial: original art, mission
loading, cockpit, mobile fighters, cannon projectiles and damage are implemented.
It is no longer the "stub" described by historical family notes. Campaign
rooms/save flow, missiles, complete navigation/behaviour and cockpit interaction
remain unfinished. The diagnostic flight depth merge and complete DOS-validated
browser/game route remain Unproven. Hatari presentation checks do not decide
DOS behaviour. [PORTING.md](PORTING.md) owns the detailed boundaries below.

This status review did not rerun target tests or promote the prototype to a
supported game. **Correction, 2026-10-14:** the checkout is now a Git
repository (local, no remote) and, at the owner's request, part of the F030DOS
publication copy (`games/wc1`); the earlier "no Git repository, publication
skipped" note is historical.

The current vertical slice is executable: a 68030/TOS program with a
VBL-paced 16-bit true-colour title menu and flight view, Falcon keyboard input,
fixed-point flight state, and an indexed software cockpit/HUD renderer. The
68030 draws one 320x200 DOS-indexed buffer, expands it through the loaded
palette to a 128,000-byte RGB565 page, and VBL publishes the completed page.
Startup follows the DOS
title timing through its original `TITLE.VGA` opening subtitle, credits, and
three-part logo zoom before reaching the **Start Vega Campaign** menu entry;
press Escape to skip to that menu, then Return or Space to enter the current
flight slice. It now includes the original seven-sprite `PLANETS.VGA`
constellation layer and the DOS title camera's 24.8 pitch/projection sweep;
the hidden-page Falcon presentation keeps the VBL alive during conversion and
advances one source title frame per completed page, avoiding accelerated
replay when a transfer spans multiple VBLs;
the first title action sphere also renders its three Dralthi and one Hornet
from the original `SHIPTYPE.V10`/`V00` frames, with canned records 32–35,
fighter view selection, rotation, scale, and depth order. Its scripted
Dralthi destruction now hands off to the original `OBJECTS.VGA` `EXPLOSION1`
frames and scaling sequence; the Hornet's seven two-laser bursts use the
original `OBJECTS.VGA` laser packet, source hardpoints, velocity, and lifetime.
The credits now switch to action sphere 17's source stock-memory asteroid set:
original `OBJECTS.VGA` section-16 animation frames, 20 hazard slots, initial
three-hazard field, source camera speed transition, and far-to-near drawing.
The DOS field is time-seeded; the Falcon currently uses a repeatable seed while
preserving its source placement ranges and spawn cadence. Record 32 also now
completes its source seven-sprite packet-four/packet-five debris burst and its
eight-particle constellation-dust pass. Asteroid collision fragments and music
are still pending. It can load the initial
campaign mission's headers, nav points, objectives, and 32 ship records from
the original DOS `MODULE.000`, including its Origin LZW compression. It also
loads `GAME.PAL`'s 256-entry ILBM palette into a Falcon RGB565 lookup table,
including the DOS cockpit reset of slots 185-191 (`$BF` is dark blue rather
than raw-palette black);
selects the player cockpit through the DOS
`INSTALL.DAT` logical-file table; and renders the original cockpit background,
source section-seven bar/lamp frames, four cockpit readouts, target-lock, and
cached mobile-fighter shapes directly from their DOS sparse-run data using
the DOS 3Space eye-frame projection, 62-view fighter lattice, and 8.8 scale
calculation. Flight movement now follows each mission record's three-axis
`Set_up_ship_info()` orientation rather than a quadrant approximation. Space
fires the player hull's original fixed-gun loadout from its source hardpoints:
laser, neutron, and mass-driver bolts retain their `OBJECTS.VGA` art,
lifetime, velocity, and refire delay in the DOS-sized dynamic-object budget.
Before movement, those bolts now use the DOS combined-radius collision test;
an impact becomes the original six-frame `LASER_SPARK`, drains the target's
source fore/aft shield and directional armor, and lets shields recharge at
their original per-hull cadence. Post-armor NPC damage now follows the source
`internal_damage()` event loop, including accumulated damage, pilot/system
state, capital-ship accumulation, and the retained `EXPLOSION1` animation;
destroyed contacts leave the active roster while their effect completes.
Enemy fighter cannon fire now uses the recovered fighter loadouts, source
lifetime/range and facing gates, owner-aware collision, and the player-side
`your_internal_damage()` table before reducing the Falcon health state.
Hostile fighter records also turn toward the player through the source local
frame, using bounded yaw/pitch steps before their weapon gate runs.
The compact `check_target()` seam keeps the current visible contact and
otherwise acquires the nearest visible hostile; the diagnostic cockpit shows
its active object slot as `TGT`. Flight now also uses the DOS
`generate_stars()` layout: eight moving dust records and seven far-star
records are projected from `PLANETS.VGA`, with source-style size/streak frame
selection and off-screen respawn.
The current stock-RAM cache retains the player type and the two shape types
preloaded by the active nav point. Capital ships now use a separate bounded
per-view packet cache, with SHIP.Vxx section I/O serviced outside rendering.
It has an **Unproven diagnostic** bounded depth merge for the represented
3Space stars/dust, ships, cannon effects, and `EXPLOSION1` objects; it does
not yet prove the DOS allocator slot/tie order or cover every object class.
Remaining work includes music; save/pilot/campaign rooms; scanner/VDU/comms
cockpit interaction; the complete flight behaviour dispatcher and pilot goals;
capital onboard explosions/shockwaves; missiles; and complete navigation
behaviour.

## Build

The default paths use the toolchain already checked out by the sibling
`F030Arcade` project on this workstation. Override them for another machine:

```sh
make VASM=/path/to/vasmm68k_mot VLINK=/path/to/vlink
make M68K_CC=/path/to/m68k-elf-gcc build
make test
```

The C resource layer is freestanding and requires a bare-metal 68030 C
compiler such as Homebrew's `m68k-elf-gcc`; its object files are linked into
the same TOS executable by VLINK. It does not add a MiNT or ELF runtime
requirement to the game.

The optional `make dsp-wire-smoke` target assembles `release/WC1C2P.LOD`, the
legacy DSP56001 transport diagnostic. It uses `dosbox-staging` and the
`ASM56000` tools in the sibling `F030Comanche` checkout; set `DOSBOX` or
`ASM56K` when they live elsewhere.

## Original DOS data

The port contains no game data. Put your legally obtained `WC_Disk1.zip`,
`WC_Disk2.zip`, and `WC_Disk3.zip` in the repository root, then stage them
for a local run:

```sh
make data
make falcon-data-smoke
make resource-smoke
make truecolor-smoke
make dsp-wire-smoke TOS=/path/to/tos404.img
```

This extracts the three disks to ignored `release/WC1DATA/`. The current
loader uses `INSTALL.DAT` to find `MODULE.000`; the rest of the extracted
files supply the current cockpit, ship-shape, palette, and future audio
slices. `make falcon-data-smoke` also creates and validates the ignored
`release/WC1CACHE/MISSION.BIN`: a schema-aware, aligned big-endian cache of
the 64 campaign records used by the current flight slice. The Falcon prefers
this cache at startup and safely falls back to direct DOS packet/LZW loading
when it is absent or invalid. Strings, pixels, sparse shape streams, and
unknown packed data are deliberately left in their original byte form until
their layouts are ported and validated.
`make resource-smoke` then validates the current palette, cockpit packet, and
sparse-shape decoder directly against that staged data on the build host.
`make truecolor-smoke` validates indexed-to-RGB565 expansion and big-endian
framebuffer words. The legacy `make c2p-smoke` alias remains available for
scripts that used the old target name. `make dsp-wire-smoke` is retained as an
isolated DSP transport diagnostic; the game presentation path no longer
depends on it.
For an asset-free integration check, use `make clean && make fixture` instead;
the target deliberately refuses to overwrite staged DOS data.

To run under Hatari, provide a Falcon-capable TOS image:

```sh
make smoke TOS=/path/to/tos404.img
make run TOS=/path/to/tos404.img
```

At the title screen, `Return`, `Space`, or the left mouse button starts the
Vega campaign slice and `Escape` exits. In flight, `A`/`D` turn, `W`/`S` change
speed, `Space` or the left mouse button fires, and `Escape` quits. Relative
mouse motion steers horizontally and vertically.
The Falcon renderer also composites a visible mouse pointer over the title and
flight pages.

## Porting rules

- The 1990 DOS `WC.EXE` binary and captured execution are the authority for
  game semantics and data layouts. `wc1-re` is supporting evidence only.
- The Falcon owns video, input, timing, memory placement, and audio hardware;
  DOS VGA, BIOS, and extender code is not translated literally.
- Falcon output uses 16-bit RGB565 true colour. Rendering remains linear 8-bit
  indexed data until the final palette expansion, preserving the recovered
  DOS assets without making the renderer or shape decoder emulate VGA
  bitplanes. The legacy DSP C2P diagnostic is not part of the game path.
- DOS `short`-sized state remains 16-bit where the recovered source depends on
  it; Falcon pointers and addresses are 32-bit.
- Every ported function gets a durable DOS contract/difference record, a
  deterministic browser fixture, and a Falcon validation target before it is
  folded into a supported main-loop path. The browser harness is also used to
  investigate function roles and side effects; its hypotheses are confirmed
  against DOS before entering the record.
- Original game data is supplied separately by the user and is never committed
  to this repository.

## Documentation

| Document | Content |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Project strategy, workspace rules, conventions, toolchain, verification harness, and the numbered task list. **Start here.** |
| [PORTING.md](PORTING.md) | Working roadmap and the per-slice porting plan. |
| [docs/DOS-SOURCE-MAP.md](docs/DOS-SOURCE-MAP.md) | DOS-function record index and Falcon-owner map. |
| [analysis/data-formats.md](analysis/data-formats.md) | Verified DOS data formats: `INSTALL.DAT`, the Origin packet container, Origin LZW, `GAME.PAL`, `MODULE.000`, plus the measured packet inventory. |
| [analysis/wcexe.md](analysis/wcexe.md) | Static identity of the DOS `WC.EXE` (Borland TC++ 1990, VROOM overlays). |
| [analysis/hatari.md](analysis/hatari.md) | The dynamic oracle: Falcon machine model, frame capture, and its gotchas. |

Findings go into `analysis/` as they are made, not into the chat log; verified
bytes are quoted, and anything unproven is marked `TBD`.
