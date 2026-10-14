# F030Comanche agent guide

## Project mission

This repository is an independent Atari Falcon030 porting and reverse-
engineering workspace for *Comanche: Maximum Overkill*. The Falcon 68030 owns
game state, input, resource loading, UI, composition, and VIDEL presentation.
The DSP56001 takes measured, regular per-pixel workloads - see rule four for
what that now includes and what it still excludes.

## Current implementation

The sources removed on 2026-08-25 have since been recreated for the CPU-only
attract milestone in `src/`, with its executable JavaScript reference in
`jsComanche/`. The active implementation includes authored opening resources,
replay-selected terrain/sky, terrain rendering, objects, console and HUD.
Status reviewed 2026-10-10: later native slices also include menus/briefing,
live command keys, weapons/player damage, mission-end/pilot logic and the digital
effect layer, with separate function evidence in `docs/PORTING-PLAN.md` and
`analysis/functions/`. These extensions do not establish a complete playable
route. Music/FM, networking and DSP remain outside the current acceptance slice;
the original silent playable scope remains the first game acceptance target.
The hashed DOS execution remains the authority, not either implementation.
Acceptance is NOT CERTIFIED: function-level mapping, complete frames/sequences
and real-target validation remain incomplete. Leave missing contracts stopped
or dormant. The shake ISR's PIT divisor is recovered; game-frame wall-clock
cadence and live keyboard parity are not. The browser's frame scheduler remains
an explicitly labelled fixture. See `analysis/functions/browser-attract.md#shake-timer`
for timer evidence and the unsupported display-shake boundary.

## The four standing rules

Confirmed by the project owner; every change is measured against them.

1. **The CPU path implements the recovered DOS behaviour.** Not "as close as
   practical" and not an instruction-by-instruction translation: the 68030
   renderer's functions and mechanics are recovered from the DOS binary, with
   exactly one class of exception: the Falcon's 16-bit true-colour surface of
   rule three. Where the disassembly yields the
   original's arithmetic, constants, assets or sequencing, the port adopts
   them exactly - the flight integration, the projection package, the attract
   cycle and the demo playback are ports of recovered code, not
   reinterpretations. Any other deviation exists only where the platforms
   genuinely differ, and each one is recorded in the docs next to what the
   original does (`docs/X86-M68K-MAP.md`, `docs/DSP-EXECUTION-PLAN.md`).

   **Behaviour is not build-selectable.** Confirmed by the project owner on
   2026-08-18: `USE_DSP` and `PARITY_TILE` choose which machine renders the terrain -
   neither changes what the picture should be. A flag that selects between
   two candidate behaviours is a decision that has not been made, and it
   hides the one that is wrong: the marcher had a column-major alternative
   and a 320-ray geometry the original never had, the backdrop tilt could be
   switched off, and three console optimisations could each be turned on
   against a renderer that had not been checked with them off. Recover the
   original's behaviour, implement that, and delete the alternative. If two
   readings of the listing are both plausible, the answer is more
   disassembly, not a flag.

   The optimisations are worth a specific warning, because one of them cost
   real time here. `CONSOLE_BOUND` seeded the marcher's occlusion at the row
   the cockpit covers, on the reasoning that spans below it cannot be seen.
   They cannot - but the seed is not a clip: a sample at or below it fails
   the visibility test and is dropped WITHOUT advancing the occlusion, so
   every near ring under the cockpit line was discarded rather than drawn and
   then covered, and the ground base showed through the gap. The original
   zeroes its horizon array (`0000D976`) and starts every column at page row
   0. An optimisation that changes what the renderer draws is not an
   optimisation.
2. **The DSP carries the voxel terrain.** The 56001 kernel is the terrain
   speedup - march and record emission on the DSP, composition on the 68030 -
   held pixel-exact against the parity oracle at every phase. The CPU
   renderer remains the correctness reference and the fallback, never the
   shipping path.
3. **The Falcon's 16-bit true-colour mode is the target surface.** All
   rendering composes RGB565 - terrain fills, palette conversions of the
   original's 256-colour assets, screens, sprites, HUD. One palette-indexed
   asset family, expanded through generated RGB565 tables at load or fill
   time; no plane conversions, no VGA emulation.

The project is a porting scaffold, not a source-compatible rebuild. Replace
DOS-specific startup, memory management, protected-mode setup, and hardware
access with Falcon/TOS implementations behind small interfaces.

## Mandatory function records and browser reference

**JavaScript is the executable semantic reference in the middle.** Follow
`../F030Method/METHOD.md` §4.3a: DOS execution → recovered contracts →
DOS-validated JavaScript reference → native m68k implementing the same
contracts. Both implementations link directly to the same DOS function record.
A target game function cannot become supported before its JavaScript reference
passes the DOS fixtures and the target passes those same contracts. JavaScript
is not shipped as a Falcon runtime or mechanically translated into assembly;
C-like pseudocode is an analysis aid, not a substitute for the executable
reference. Keep DOS numeric and byte-order semantics explicit; hardware
adapters retain their recorded Target artefact boundary. DOS always decides
when either implementation disagrees.

The hashed shipped DOS binary and its captured execution are the sole
behavioural authority. The listing, `docs/X86-M68K-MAP.md`, parity renderers,
and Falcon code are evidence or implementations; none may overrule DOS. The
map remains the index, but every function represented in browser, 68030 or DSP
code must also have the `METHOD.md` §4.2 function record: DOS identity and
evidence, recovered purpose/contract and fixtures, implementation symbols, and
an explicit difference ledger against DOS. Record and prove even “no
difference”; an unresolved difference is `Unproven` and cannot enter a
supported path. The deterministic browser reference is mandatory from the
first function: use its controlled experiments to identify function roles,
contracts, side effects and Falcon seams, then confirm each finding against DOS
before recording it. Its fixtures land before or with every supported Falcon
slice; CPU/DSP parity remains a local check, not a DOS oracle.

## The porting procedure

Confirmed by the project owner on 2026-08-27 as **the** way functions are
ported here. It is not a checklist to satisfy after the fact; each step
exists because skipping it produced a wrong port in this repository.

1. **Start at the DOS listing, not at the port.** Open the routine in
   `re/listings/`, read it, and let it say what it does. Do not start from a
   comment, a TODO or a previous reading - `000075A1` was recorded here as
   "the HUD crosshair, not decoded" and is nothing of the kind; it is part of
   the MFD marker path, which was already ported. A port's own note is
   evidence about the port, not about DOS.

2. **Check the entry is an entry.** A cited address that lands mid-instruction
   is a misread boundary. Two records here named `00007443` and `000077BE`,
   both interior bytes.

3. **Separate static data from runtime state, by address.** The flat content
   region ends at exactly `0x32B20`. Tables below it - the label coordinates
   at `0x72D4`, the MFD handler pointers at `0x19E10` - are in the image and
   are transcribed. Anything at or after it is BSS, exists only in a running
   game, and must be captured.

4. **Do not trust a shipped value as a runtime value.** The image ships
   `[0x72E7] = 1`; mission start overwrites it with 2, so the attract's right
   MFD is on a different page than the file suggests. Read the byte out of
   the running original before building on it.

5. **Capture at an instruction, not an instant.** `stop` is atomic but not
   phase-coherent - a frame driver latches, renders, then integrates, so an
   arbitrary freeze pairs one frame's inputs with another frame's outputs.
   Use `work/dump_marcher_tables.py --break-at`/`--at-marcher` (QEMU's gdbstub
   through `work/rsp.py`) and cross-check the PC through QMP. This is worth
   more than any amount of re-reading: the marcher model went 16.1% -> 100.0%
   on the breakpoint alone, with no change to the model.

6. **Transcribe with the address on the step, not just on the routine.**
   Every non-obvious line carries the DOS address it came from, so a later
   reader can check one instruction without re-deriving the routine. The
   §4.2 record on the routine is still mandatory; this is in addition.

7. **Verify against the original, and zoom before concluding.** Two
   "differences" recorded here from 320x240 thumbnails were not differences
   at all - the compass letters were being drawn, at a different heading.
   Crop the region from both, scale it up, and put them one above the other.

8. **When you stop, record the decode, not the intention.** A gap written
   down as "port the right MFD" is worth nothing; the same gap written as the
   handler table, the page, the routine it dispatches to and what that
   routine actually does starts the next attempt from a specification. If a
   routine turns out to be larger than the slice you are in, say so and stop
   at the decode rather than starting it unannounced.

The rule that binds them: **never write 68030 code without the DOS routine in
front of you.** Fitted constants, plausible guards and "this must be roughly
what it did" are the failure mode this procedure exists to prevent - see rule
one and `no-invention` in the docs.

## Implementation-source links

Apply `docs/FUNCTION-PORTING.md` for function-level granularity, explicit
numeric/endian contracts, adjacent provenance comments, and the separation of
shared behavior from CPU/platform mechanisms. Its additional mapping and
fixture requirements remain subject to implementation-wide audit; a complete
header alone is not proof of DOS parity.

The canonical ground-truth DOS function name **is the function ID**, shared
across the inventory, function record, JavaScript/m68k annotations, route
manifest and fixtures. Use an evidenced original symbol or, for this stripped
binary, its established disassembly name tied to the hashed image and verified
entry/range. Target routine names and descriptive titles are aliases. Helpers
retain the parent DOS ID and mapped range; merged routines list each DOS ID
without dropping separate records. Target-only adapters are explicitly N/A;
never invent a DOS ID for them. See `../F030Method/METHOD.md` §4.2.

Every JavaScript/browser and 68000/m68k function source that implements or exposes a recovered DOS function must carry an adjacent comment or docstring linking to the durable function record and naming the disassembled DOS function symbol plus canonical range/entry (for example, `DOS: FUN_0000_1234; record: <stable-function-record>`). Use the same stable function ID in both implementation sources; a separate map or file-level comment is not enough. Code with no DOS counterpart must say `N/A - platform replacement` or `Target artefact` at the definition.


The priority roadmap is `docs/PORTING-PLAN.md`. Recover the DOS behaviour
needed by the next playable vertical slice, record its flat x86 addresses and
contracts in `docs/X86-M68K-MAP.md`, implement and verify the matching 68030
behaviour, and only then optimize measured bottlenecks. A complete playable
CPU-side mission takes priority over higher heuristic disassembly coverage or
further DSP kernel work. `PORTING.md` is the subordinate DSP performance plan,
not the current project schedule.

The initial playable scope deliberately excludes sound, music, networking, and
network-facing services. Keep those assets and observations documented, but do
not add sound or network dependencies to the first game loop, build, runtime,
or acceptance checks. They are later phases.

4. **Nothing is drawn twice, and regular per-pixel work belongs on the DSP.**
   The Falcon's cheapest cycle is the one not spent: overdraw, redundant
   clears and work on pixels that are occluded, off-screen or out of range
   come out first. What survives that and is regular enough to stream is a
   DSP candidate - not the terrain march alone. The measurement discipline in
   rule two still governs which: on 2026-08-16 the object pass measured
   44.1 ms of a 122.1 ms frame, more than the whole terrain stage, and no
   phase of the DSP plan had looked at it. Move work by the numbers, not by
   the shape of the problem.

## Repository map

- `src/` — recreated CPU-only Falcon attract sources; DSP remains dormant.
- `tools/` — Falcon build/run helpers and generic DOS reverse-engineering tools.
- `docs/` — durable findings and workflows. Update the appropriate document
  whenever an important asset, format, size, or runtime-boundary fact is
  established.
- `docs/PORTING-PLAN.md` — priority DOS-to-Falcon roadmap and acceptance gates.
- `docs/X86-M68K-MAP.md` — durable semantic map from recovered DOS flat
  addresses to Falcon implementations or platform replacements.
- `re/` — committed seeds/notes plus ignored generated listings and unpacked
  outputs.
- `reference/f030f29/` and `tools/re/reference_f29/` — F29 Retaliator
  comparison material only. Do not assume its formats or constants apply to
  Comanche.
- `assets/` — legally obtained local source material and ignored derivatives;
  never commit original game data or generated binaries.
- `docs/DOS-ORACLE.md` — running the **original** headless on genuine MS-DOS
  6.22 under QEMU: what `work/build_dos_hdd.py` / `set_boot_mode.py` /
  `run_qemu.py` do, what was verified 2026-08-23, and how this differs from
  `tools/oracle-capture.sh`'s DOSBox route. **Read the last section before
  writing the word "oracle" in a commit message**: `docs/DSP-EXECUTION-PLAN.md`
  uses it for the CPU renderer checking the DSP renderer, which is a parity
  check between two of our own implementations and is not DOS ground truth.
- `docs/CROSS-PROJECT.md` — the shared RE-technique ledger of the
  projects in the `../F030Method/README.md` manifest. **Generated**
  by `../F030Method/gen_cross_project.py` — edit the body there and re-run;
  never edit the copy. Read it before inventing a method, and upstream
  transferable findings from here the same way. The parent repo
  (`../F030Method`) also holds `METHOD.md` (the family's four-phase
  decode → disassemble+prove → understand → port playbook) and the master
  copies of the shared QEMU DOS-oracle harness (`dos/`, with `sync.py`).

## Comanche asset and disassembly rules

The supplied distribution is three FAT12 floppy images. The canonical local
post-install tree is `assets/extracted/comanche_hdd/`, representing
`C:\COMANCHE\`. The raw images, floppy files, rebuilt SFX, and extracted LHA
payload are retained below `assets/extracted/001758_comanche/`.

The executable order is mandatory:

1. Reconstruct `OVERKILL.EXE` from `OVERKILL.000 + OVERKILL.001 + OVERKILL.002`.
2. Extract its LHA payload.
3. Select the real `COMANCHE.EXE` from the installed tree.
4. Unpack its LZEXE 0.91 wrapper with `UNLZEXE` or an equivalent tool.
5. Run `mzinfo.py`, `codemap.py`, and `disasm.py` on the unpacked MZ file.

Never treat `OVERKILL.EXE` as game code, and never use the packed
`COMANCHE.EXE` as a normal disassembly input. The packed executable is 61,154
bytes and the unpacked load image is 386,823 bytes, but 173,287 bytes of that
are zero-filled BSS and 5,888 bytes are the real-mode bootstrap. The program
is the 207,648-byte flat region at image offset `0x1700`; quote that figure,
not the load-module size, and never treat either as an instruction count.

The unpacked program has a 386 protected-mode/custom DOS-extender path, then
runs as a flat 32-bit program with one code and one data selector sharing a
base. `tools/re/disasm.py` covers both halves: `seg:off` for the bootstrap,
`--flat 1700` for the game. Use `--no-inline-detect` for Comanche. Do not
interpret heuristic coverage as proof of code/data boundaries.

See `docs/ASSET-INVENTORY.md` for measured sizes and paths and
`docs/RE-WORKFLOW.md` for the current analysis procedure.

## Falcon implementation rules

- Keep the 68030-side renderer correct before optimizing it on the DSP.
- Use double buffering and publish the display buffer at VBL.
- Treat the DSP host interface as a command/status path, not a per-pixel bus.
- Keep a CPU-compositing or smaller-map fallback until Falcon memory, DSP
  memory, cache behaviour, and host-handshake timing are measured.
- Do not assume that DSP X/Y memory can directly or cheaply access the VIDEL
  framebuffer.
- For the first playable milestone, implement graphics, input, game state,
  missions, local resource loading, and HUD only. Leave sound/music and all
  networking deferred.
- Keep fixed-point formats, shared command blocks, ownership transitions, and
  buffer sizes explicit in shared includes or documentation.

## Build and verification

Run from Git Bash or another POSIX-like shell:

```bash
bash tools/build-run.sh
bash tools/build-dsp.sh
```

Use `bash tools/run.sh` for Hatari execution and
`bash tools/grab-frame.sh <vbl> build/frame.png` for framebuffer capture.
Generated build, emulator, disassembly, and extracted-game-data outputs are
ignored by git.

Build the recreated CPU attract milestone from current sources. Generated
output or deleted source text is not a substitute for the DOS contracts.

`USE_DSP` and `PARITY_TILE` select rendering mechanisms; see rule one.
`TARGET_CPU=68030` (default) or `68060` selects equivalent CPU instructions and
platform cache handling, never a precision or game-behaviour choice. Stock
Falcon030 remains primary; see `analysis/functions/cpu-compatibility.md`.
Do not add a flag to carry a behavioural choice.

For changes to reverse-engineering tools, verify them against the supplied
asset-derived files when available. For Falcon changes, build the affected
target and run the smallest relevant emulator or capture check. Record
important discoveries and changed assumptions in `docs/`, not only in chat or
generated listings.

**Capture a frame the game actually renders.** The pinned benchmark camera
was removed with the other flags, so verification means the attract cycle's
demo flight - roughly VBL 3000-4900 for the first pass, after the fanfare and
title screens. This matters more than it sounds: the anchor work of
2026-08-18 was verified against a pinned level camera, reported as done, and
the very next demo frame showed a green block across the lower third that the
pinned camera could not produce. A level camera cannot show the backdrop tilt
either - the horizon byte collapses to zero and the picture is identical to
the tilt being off. If a capture cannot distinguish the change from its
absence, it has not verified anything.

## Safe repository practices

- Inspect `git status` before editing and preserve unrelated user changes.
- Use `apply_patch` for source and documentation edits.
- Do not use destructive commands such as `git reset --hard` or broad
  recursive deletion.
- Do not commit ignored game data, unpacked binaries, generated listings,
  screenshots, or emulator artifacts.
- Keep commits focused; do not include pre-existing dirty files unless the
  user explicitly asks for them to be committed.

## Cross-port documentation rule

When a change or investigation establishes a confirmed finding, correction,
tool/workflow lesson, or other fact that can help more than this repository,
update the authoritative shared documentation in the same session and
regenerate any derived copies. Always do this; do not leave transferable
findings only in chat, code, or generated output. Keep project-specific details
in the local canonical document and upstream the reusable rule with its
evidence, scope, and status.

This applies equally to browser-only milestones: a browser decoder or
renderer that settles an asset shape, palette convention, frame order, or
platform boundary must update the cross-port map and the relevant asset/plan
document before the task is handed off. If there is only one agent guide in a
checkout, this section is that guide's required update rule; nested agent
guides, when present, must carry the same wording and obligation.
