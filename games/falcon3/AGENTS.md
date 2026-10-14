# F030Falcon3 — working rules

## Goal

Disassemble and understand the DOS game *Falcon 3.0* v3.05 well enough to
port its observable behaviour to an Atari Falcon030. The current project is
reverse-engineering-only; no Falcon runtime code is claimed yet.

## Standing porting rules

Apply the evidence-first policy of `../F030Comanche/AGENTS.md` through the
Falcon 3-specific procedure in `analysis/porting-policy.md`. These are
requirements for future implementations, not claims of current parity.

1. The CPU implements recovered DOS behaviour exactly: arithmetic, constants,
   assets, state effects and sequencing. Replace DOS startup, allocation and
   hardware behind small Falcon/TOS interfaces, recording every platform
   difference. Never invent missing behaviour or make competing readings
   build-selectable; resolve them against DOS or leave the path Unproven.
2. The 68030 is the correctness reference and owns state, input, resources,
   UI, composition and presentation. Move measured, regular rendering work to
   the DSP56001 only after the CPU contract is proved; require identical
   outputs under the same fixtures. Falcon 3 has no established DSP workload
   yet: Comanche's voxel kernel is not evidence for this game's renderer.
3. Target Falcon 16-bit RGB565 presentation. Retain original indexed assets
   and expand through documented palette conversions at load/fill time; do
   not introduce planar conversion or VGA emulation as the target renderer.
   This surface exception does not permit reduced simulation precision.
4. Remove redundant clears and overdraw only when observable behaviour stays
   identical. Measure before optimizing or moving work to the DSP; retain a
   correct CPU fallback. A visibility shortcut that changes state or pixels
   is a behavioural change, not an optimization.

The first playable scope is graphics, input, state, missions, local resources
and HUD. Sound, music and networking remain later phases, without dependencies
in the first runtime or its acceptance checks.

## Source and derived data

- `assets/FALCON3.ISO` is the supplied source image. Never modify it.
- `game/cd/` is an exact ISO extraction and `game/FALCON3/` is the verified
  `FALCON3.RES` extraction. Both are derived and ignored.
- `work/` contains regenerable listings, DOS images, probes and scratch.
- `analysis/` contains measured facts and one document per format or runtime
  component. Record `RESOLVED`, `IDENTIFIED`, `PARTIALLY RESOLVED` or `TBD`.

## Disassembly rules

1. Parse the MZ header and relocations before widening code coverage.
2. Keep the 0x1FB51-byte MZ load image separate from the appended
   0x12FA96-byte region until the RTLink overlay contract is demonstrated.
3. Add indirect targets to `re/seeds.txt` only with evidence and a note in
   the relevant analysis document.
4. Treat a re-encodable byte range as evidence of encoding, not automatically
   evidence that the range is code; guard proven data regions.
5. Run the original under the DOS oracle and compare observations with static
   analysis before naming game subsystems.

The shared method and technique ledger are authoritative:
`../F030Method/METHOD.md` and `analysis/cross-project.md`.

## Mandatory function-level port policy

The hashed shipped DOS executable and its captured
execution are the sole behavioural authority. Reassembly, decompiler output,
a recovered source tree, the browser reference, and 68000 code are evidence or
implementations; none may overrule DOS. For every function represented in
browser or target code, maintain the `METHOD.md` §4.2 function record: DOS
identity and evidence, recovered contract and fixtures, browser/target symbols,
and an explicit difference ledger against DOS. Record and prove even “no
difference”; an unresolved difference is `Unproven` and cannot enter a
supported path. Start the deterministic browser reference with the first
function; use its controlled experiments to identify function roles, contracts,
side effects and Falcon seams, then confirm each finding against DOS before
recording it. Land its fixtures before or with each supported target slice.

**JavaScript is the executable semantic reference in the middle:** DOS
execution → recovered contracts → DOS-validated JavaScript → native m68k
implementing the same contracts (`METHOD.md` §4.3a). No target game function
is supported until its JavaScript reference passes DOS fixtures and the target
passes those same contracts. Pseudocode is an analysis aid, not a substitute;
JavaScript is neither mechanically translated nor shipped as a Falcon runtime.

Use the canonical evidenced DOS function name as the function ID throughout
records, inventories, fixtures and both implementations. Verify entries before
assigning IDs; for overlays include the logical overlay identity and captured
residency mapping. Helpers retain parent IDs/ranges, merged implementations
retain every separate record, and target-only adapters have an explicit N/A
identity. Never invent a DOS symbol for an uncertain boundary.

Follow `analysis/porting-policy.md` for instruction-level provenance, numeric
and endian contracts, phase-coherent captures and acceptance order. Never write
68030 game code without the corresponding DOS routine in front of you.
## Implementation-source links

Every JavaScript/browser and 68000/m68k function source that implements or exposes a recovered DOS function must carry an adjacent comment or docstring linking to the durable function record and naming the disassembled DOS function symbol plus canonical range/entry (for example, `DOS: FUN_0000_1234; record: <stable-function-record>`). Use the same stable function ID in both implementation sources; a separate map or file-level comment is not enough. Code with no DOS counterpart must say `N/A - platform replacement` or `Target artefact` at the definition.


## Current next steps

1. Complete compiler/runtime identification and the resident code/data
   boundaries. The RTLink overlay contract (directory, loader, thunk
   dispatch, caller reload, parent chaining, overlap eviction) is resolved in
   `analysis/executable.md` (2026-09-13); reach overlay code through its
   thunk table, never through fixed tail addresses.
2. Extend the working startup/Instant Action DOS oracle into repeatable
   campaign and Red Flag observations with captured state.
3. Decode and render one still-open raw resource format before porting it.

## Cross-port documentation rule

When a change or investigation establishes a confirmed finding, correction,
tool/workflow lesson, or other fact that can help more than this repository,
update the authoritative shared documentation in the same session and
regenerate any derived copies. Always do this; do not leave transferable
findings only in chat, code, or generated output. Keep project-specific details
in the local canonical document and upstream the reusable rule with its
evidence, scope, and status.
