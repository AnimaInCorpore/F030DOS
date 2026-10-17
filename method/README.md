# F030Method — the shared method layer of the F030 DOS-game ports

Thirteen sibling projects reverse-engineer a DOS game in order to port it to the
Atari Falcon030. This repo is the family's parent: it owns the documents and
tools that are shared, so that no single game project has to. The hashed,
shipped DOS executable for the selected build is the behavioural authority in
every project; a recovered source tree is supporting evidence, never a
replacement for the DOS oracle.

| Repo | Game | Origin |
|---|---|---|
| `../F030POR` | Pool of Radiance (1988) | `git@github.com:AnimaInCorpore/F030POR.git` |
| `../F030Underworld` | Ultima Underworld (1992) | `git@github.com:AnimaInCorpore/F030Underworld.git` |
| `../F030Underworld2` | Ultima Underworld 2 (1993) | `git@github.com:AnimaInCorpore/F030Underworld2.git` |
| `../F030TieFighter` | TIE Fighter CD (1995) | `git@github.com:AnimaInCorpore/F030TieFighter.git` |
| `../F030F29` | F29 Retaliator (1990) | `git@github.com:AnimaInCorpore/F030F29.git` |
| `../F030Comanche` | Comanche: Maximum Overkill (1992) | `git@github.com:AnimaInCorpore/F030Comanche.git` |
| `../F030Falcon3` | Falcon 3.0 (1995) | `git@github.com:AnimaInCorpore/F030Falcon3.git` |
| `../F030Links386` | Links 386 CD (1995) | `git@github.com:AnimaInCorpore/F030Links386.git` |
| `../F030LOL` | Lands of Lore: The Throne of Chaos (1994) | `git@github.com:AnimaInCorpore/F030LOL.git` |
| `../F030MagicCarpet` | Magic Carpet (1994/1995) | `git@github.com:AnimaInCorpore/F030MagicCarpet.git` |
| `../F030WC1` | Wing Commander (1990) | *local Git repository since 2026-10-14, no remote* |
| `../F030ICR` | IndyCar Racing v1.05 (1994) | `git@github.com:AnimaInCorpore/F030ICR.git` |
| `../F030PanzerGeneral` | Panzer General (1994) | `git@github.com:AnimaInCorpore/F030PanzerGeneral.git` |

**Layout assumption:** all repos are checked out side by side under one
directory — every `../F030*` cross-reference in the docs relies on it, and both
tools resolve the siblings from their own file location, so the workspace can
be `C:\Arbeit`, `~/Work` or anything else. There are no submodules on purpose:
the working tree is the workspace, and this table is the manifest.

The one place the manifest is *executable* is `gen_cross_project.py`'s
`TARGETS`; `dos/sync.py` imports it rather than keeping a second list, so a
project registered in one is known to the other. Sibling `F030*` directories
that are not in `TARGETS` (`F030Arcade`, `F030MXDRV`, `F030TREX`, …) are not
family members and neither tool touches them.

**WC1 is the odd one out only in the evidence it can reuse.** Its plan pairs
`../wc1-re`, a reconstruction of the 1996 *Kilrathi Saga* build — which helps
read code but cannot establish behaviour for the 1990 DOS target — with
`WC.EXE` and the DOS oracle deciding every disagreement. `METHOD.md` §4.2
requires the reconstruction's build and fidelity grade to be recorded in each
function record alongside that DOS evidence. **Correction, 2026-10-10:** the
2026-08-26 description of the local checkout as a "stub" is historical. It now
contains native title/flight/combat sources, resource tools and function records;
see [its current plan](../F030WC1/PORTING.md). The flight depth merge remains
Unproven, and a complete DOS-validated browser/game route is not established.
Source availability does not establish fidelity. **Correction, 2026-10-14:**
"no Git repository, publication skipped at the owner's request" is historical;
the checkout is a local Git repository (no remote) and, at the owner's request,
is part of the F030DOS publication copy. The generated ledger (§0 and the WC1
tail) carries the same correction since 2026-10-17.

## Porting status — reviewed 2026-10-10 (Comanche row 2026-10-17)

This is a review of local sources and existing evidence records, not a fresh
acceptance run of every game. None is documented as a completed, fully
DOS-validated Falcon game. Reassembly, function counts, isolated fixture passes
and emulator demonstrations have different scopes; they are not completion
percentages. The linked project records own the details and next experiments.

| Port | Current milestone | Remaining boundary |
|---|---|---|
| [Comanche](../F030Comanche/docs/PORTING-PLAN.md) | CPU attract, menus, briefing, live flight, combat and debrief; all 20 mission starts equal the original's; tables read from the player's `COMANCHE.EXE`; ported music driver, played through F030OPL2 in a 68060 build; a playing bot; a 68060 hardware-test build | Overall NOT CERTIFIED; full frames/sequences and live parity open; never run on a real Falcon (`docs/HARDWARE-TEST.md` is the procedure); DSP renderer dormant |
| [Wing Commander](../F030WC1/PORTING.md) | Native title, flight, cockpit, mission loading and cannon combat prototype | Campaign/navigation/missiles and DOS/browser validation incomplete; depth merge Unproven |
| [F29 Retaliator](../F030F29/docs/ENGINE.md) | Hatari-running DSP/blitter scene renderer, flight-state core, custom menu/HUD | Original presentation and complete mission/game behaviour unproven |
| [Pool of Radiance](../F030POR/PORTING.md#slice-status) | Falcon title/image endpoint matches host expansion at 4 MB and 14 MB | Layout/text, dungeon view, script semantics and gameplay unfinished |
| [Ultima Underworld II](../F030Underworld2/PORTING.md) | Browser intro/display slice; separately checked Falcon RGB565 seam | Input/game loop, 3D gameplay and physical scanout not integrated/proven |
| [Panzer General](../F030PanzerGeneral/docs/PORTING-PLAN.md) | DOS/JS/native loader, geometry, RNG and drawing contracts; static Poland-screen demonstration | No playable route; scenario producers, input/timers, movement/combat/turns open |
| [Ultima Underworld](../F030Underworld/README.md) | Byte-exact executable rebuild, asset recovery and original DOS gameplay/save route | Frame/state semantics and first browser/native slice open |
| [TIE Fighter](../F030TieFighter/analysis/todo.md) | Byte-exact executable rebuild, extensive LFD decoding and function identification | Original CD-check execution, renderer/resource semantics and first port slice open |
| [Falcon 3.0](../F030Falcon3/README.md) | DOS overlay loader, dispatch, reload and eviction recovery | No browser reference or Falcon game runtime |
| [Links386](../F030Links386/analysis/executable.md) | P3/EXP recovery and measured startup-loader path; partial resource formats | QEMU segment-override defect blocks trustworthy execution past the gate; no port runtime |
| [Lands of Lore](../F030LOL/README.md) | Startup/resource analysis, EMC2 script framing and exact palette-blend recovery | Live loader/script contracts and first browser/native slice open |
| [Magic Carpet](../F030MagicCarpet/README.md) | LE/fixup recovery, live placement, decoded screen/font/sprite families | Original stops at mouse-driver gate; game route and first port slice open |
| [IndyCar Racing](../F030ICR/README.md) | Verified install/track layout; DOS practice driving; textured-span hot loop identified | Camera/polygon setup and gameplay contracts open; no browser/native runtime |

The STEArcade-derived work is recorded in
[analysis/stearcade-implementation.md](analysis/stearcade-implementation.md).
PG consumes conservative flag analysis and source maps; PG and Comanche consume
exact checkpoint diagnostics. The synthetic benchmark's 28.4% cycle reduction
does not establish a game-speed gain or promote any game's acceptance status.

## What lives here

| File | Role |
|---|---|
| `METHOD.md` | The four-phase playbook — decode → disassemble+prove → understand → port. It keeps a complete recovered-function inventory while concentrating deep analysis on each active route's dependency closure. Supported functions require per-function DOS contracts and parity evidence, direct function-body fidelity without invented defensive behaviour, an emulated DOS keyboard/pointing-device I/O boundary, DOS-authoritative timing/game-flow cadence, assembler/compiler-verified m68k output, and a deterministic, playable browser game runtime. Graphics and sound are the explicit hardware-substitution exceptions; game flow, input, timing and function semantics are not. Hand-maintained, here only; written on F030POR and moved here 2026-08-21. |
| `DEPENDENCIES.md` | Ownership and reproduction records for shared tools, media and sibling code; validation and propagation procedure, including the limits of the current drift checks. |
| `validation/` | Shared conservative flag liveness, exact logical checkpoint comparison and identity-bound source-cost aggregation; PG and Comanche adapters, with separate DOS gates. See `analysis/stearcade-implementation.md`. |
| `templates/port-slice.md` | Reusable active-slice plan: observable route, transitive dependencies, next blocking experiment, parity gates and minimum-target resource budget. Adapt into the game's existing plan. |
| `analysis/f030ct-translator-review.md` | Source-backed review of F030CT's translator: checked placement, context/dispatch recovery, bounded generation and first-divergence diagnosis, including the limits of its reported parity. |
| `analysis/sibling-port-lessons.md` | Leads from the non-DOS Falcon ports for the DOS family: F030OPL2 and Miles audio reuse, DSP-calibrated Hatari, DSP and native-hook gates, 030 measurement idioms, endianness. Paths checked; claims not re-measured. |
| `CROSS-PROJECT.md` | The RE-technique ledger, master-generated copy (no per-project tail). |
| `gen_cross_project.py` | Generates `CROSS-PROJECT.md` here plus a copy in every project, each with its own "What to adopt here" tail. **Edit the body here, then re-run** — never edit a generated copy. |
| `dos/` | Master copies of the shared QEMU DOS-oracle harness: `dosimg.py`, `run_qemu.py`, `mbr.asm`, `gdbstub_probe.py`. |
| `dos/sync.py` | Checks the project copies against the masters (default), pushes updates (`--push`), seeds a new project (`--init`, which also writes a working `build_dos_hdd.py` skeleton and creates `img/`). Members with no harness are listed as `absent` rather than silently skipped. |

## Start the next porting slice

Agent rule: **DOS → recovered contracts → DOS-validated JavaScript reference →
native m68k**, as specified in [METHOD.md §4.3a](METHOD.md#43a-a-browserjavascript-game-reference-is-mandatory).
JavaScript is the executable semantic reference, not a runtime dependency of
the Falcon. DOS remains authoritative over both implementations; neither
matching reference/target results nor a C-like reconstruction can replace DOS
evidence.

1. Read the game's current plan and latest evidence. Name the next connected
   player-visible result and the last verified checkpoint; preserve the game's
   declared target and scope. Use [the slice template](templates/port-slice.md)
   within that plan rather than starting a second status ledger.
2. Follow [METHOD.md](METHOD.md) §0.1–§0.3: map enough of the build to avoid
   mistaking an unseen path for an absent one, then trace the required DOS
   route, its transitive dependencies and the smallest measurement that
   resolves its next blocker. Keep the recovered-function inventory; focus deep
   contract work on the active route.
3. Check required checkouts, media and tools using
   [DEPENDENCIES.md](DEPENDENCIES.md). Run the two drift checks below before
   changing shared files. An `absent` harness or a missing oracle can block the
   active slice even when the checks return success.
4. Automate repeated work inside that slice ([METHOD.md §0.4](METHOD.md#04-automate-the-checked-work-within-each-slice)).
   Use checked bytes and execution contexts, evidenced dispatch tables, and
   source-mapped diagnostics. Where a bounded native translation removes
   transcription work, validate its rules against the same DOS/JavaScript
   contracts; no whole-game compiler is required. Track unsupported work
   explicitly and debug from the first divergent logical checkpoint. The
   [F030CT review](analysis/f030ct-translator-review.md) explains the evidence
   behind this strategy and which SNES assumptions must stay local.
5. Carry that dependency closure through decode, disassembly proof and DOS
   contracts into browser and target parity. Leave unrelated recovered
   functions explicitly identified, unproven or deferred with scope evidence.
   Check target feasibility early; optimize measured bottlenecks after
   correctness. Mark the slice supported only after its cumulative connected
   route and resource gates pass.

## Editing rules

- **`METHOD.md`, `DEPENDENCIES.md`, `templates/`, `analysis/`**: edit here. Projects
  reference the shared policy and dependency guide; their filled-in slice plans
  stay local. Summarize transferable policy changes in the generator's §8 so
  the next regeneration makes them visible to every sibling.
- **`CROSS-PROJECT.md`**: edit `gen_cross_project.py`, then

  ```
  python gen_cross_project.py
  ```

  which rewrites all copies, and

  ```
  python gen_cross_project.py --check
  ```

  which reports drift without writing (exit 1 on drift — the ledger
  equivalent of `dos/sync.py`). A correction made in a project's copy will be
  reinstated wrong on the next run — port it here first (this has happened;
  see `CROSS-PROJECT.md` §5 on flagging not-yet-upstream fixes).
- **`dos/`**: fix bugs here (or copy a project-local fix back here first),
  then `python dos/sync.py --push`. Plain `python dos/sync.py` reports drift
  without changing anything. The per-game halves — `build_dos_hdd.py`,
  `set_boot_mode.py` — belong to the projects and are never touched by sync.

## Feeding findings upstream

The projects are where lessons get paid for; this repo is where the
transferable part is kept. The rule: **when a finding is transferable — a
technique, a trap, a correction — upstream it in the same session that records
it locally.** It is mirrored in every discovered workspace `AGENTS.md`, and
new port repositories must carry the same rule in their agent guide. The local
doc keeps the full detail; the parent gets the transferable core:

| Kind of finding | Goes to |
|---|---|
| RE technique, disassembler trap, tool gotcha, correction to a shared claim | `gen_cross_project.py` `BODY` (§1–§7), then re-run the generator |
| Phase or port policy — fidelity, grounding, seams, verification | `METHOD.md` |
| Fix to the DOS-oracle harness | `dos/`, then `python dos/sync.py --push` |
| Project-local finding (a format, an address, a routine) | stays in the project's `analysis/` — do not upstream |

Two habits keep this honest (both are in `CROSS-PROJECT.md` §5): corrections
are recorded in place with the old wrong reading quoted, and a fix made in a
generated or synced *copy* is flagged loudly until it has been ported here —
otherwise the next regeneration reinstates the error. Both drift directions
are detectable mechanically: `python gen_cross_project.py --check` for the
ledger, `python dos/sync.py` for the harness. When a project completes
an item from its "What to adopt here" list, strike it through in the `ADOPT`
entry here (with what settled it) rather than deleting it.

## Adding a new game

1. Create `F030<Game>` next to the other repos in the workspace (`git init` —
   it is not optional; §5 of the ledger is about correcting the record in
   place, which is only checkable against a history), with the
   family layout: `assets/` (as shipped, never modified), `game/` (extracted
   reference, kept pristine), `work/` (derived, regenerable), `analysis/`
   (one doc per format/component plus a stable function-record ledger), and an
   `AGENTS.md` copied in shape from a sibling (`F030Underworld2`'s is the
   smallest).
2. Read `METHOD.md` §0–§2 before touching the binary, and `CROSS-PROJECT.md`
   before inventing a method. Establish a broad build/function map, preserve
   recovered functions in the inventory, and prioritize detailed analysis by
   the first route's dependency closure; whole-game contracts are not a
   prerequisite for the first supported slice.
3. Register the project in `gen_cross_project.py`: the family table at the top
   of `BODY`, an `ADOPT` entry (a short "What to adopt here" list — start with
   METHOD.md §1's unwrap-and-CRC and §2.1's compiler identification), and a
   `TARGETS` line. Re-run the generator.
4. Seed the DOS oracle: `python dos/sync.py --init F030<Game>`, then write the
   per-game `build_dos_hdd.py` from a sibling's as template
   (`F030Underworld2/work/build_dos_hdd.py` is the cleanest). `--init` writes a
   skeleton with the per-game decisions marked, so this is filling in a block
   rather than adapting a sibling's file. Read the game's own shipped `.BAT`
   and `CONFIG.*` for the launcher path and memory config instead of choosing
   them — Comanche's are the worked example (`F030Comanche/docs/DOS-ORACLE.md`).
   The MS-DOS 6.22 floppy set does not need acquiring: `dosimg.find_floppies()`
   borrows a sibling's in place, or takes `$DOS622`.

   Do this even if the port seems not to need it yet: `python dos/sync.py`
   lists every registered member without a harness as `absent`, and the members
   that sat on that list were the ones with the largest open questions about
   what the original actually does.
5. First milestones, in METHOD.md's order: a scripted unwrap ending in a CRC
   tally; compiler + executable model identified; one image rendered and
   *looked at*. Record the first connected route and its dependency closure in
   the local plan using `templates/port-slice.md`. At the first ported function,
   create its DOS contract and difference record plus the deterministic
   browser-reference fixture; grow both with every supported slice.
