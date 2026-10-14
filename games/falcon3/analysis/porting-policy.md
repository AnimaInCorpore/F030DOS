# Falcon 3 function porting policy

Status: requirements adopted from F030Comanche; implementation parity remains
unestablished. This repository currently contains reverse-engineering tools and
findings, not a supported browser game reference or Falcon runtime.

The authoritative method is [F030Method](../../F030Method/METHOD.md), especially
§4.2 and §4.3a. This policy applies the procedure in
[Comanche's guide](../../F030Comanche/AGENTS.md) and its
[function policy](../../F030Comanche/docs/FUNCTION-PORTING.md) to Falcon 3. It
does not import Comanche addresses, memory boundaries, fixed-point scales,
attract timing or voxel/DSP architecture.

## Recover before implementing

1. Open the actual DOS routine in `work/listings/`, starting from the selected
   hashed `game/FALCON3/FALCON3.EXE` and the reached route. Previous comments,
   TODOs and port code do not establish its meaning.
2. Verify the entry and instruction boundaries. Identify resident code or the
   logical RTLink overlay and range. A sampled segment address is not a stable
   overlay identity; preserve the load/residency witness. The unresolved tail
   mapping in [executable.md](executable.md) must not become an assumed address.
3. Separate file-backed bytes, relocations, initialized data, uninitialized
   state and overlay storage by evidenced address mappings. Do not apply
   Comanche's flat-image/BSS boundary to this segmented executable.
4. Capture runtime values before using them as constants. Shipped values may
   be overwritten by startup, mission selection or overlay activation.
5. Capture at a verified instruction boundary and record PC, segment/overlay
   mapping and execution phase. Arbitrary stopped screenshots cannot establish
   coherent function inputs and outputs. Use the shared DOS harness and record
   the exact breakpoint/capture command; do not assume Comanche-specific probe
   scripts apply here.
6. Recover the contract and implement the executable JavaScript reference.
   Cite source instruction addresses beside each non-obvious operation, in
   addition to the adjacent function-record link. Confirm reference outputs
   and side effects against DOS fixtures before supporting native m68k code.
7. Validate the native function with those same fixtures. Then validate call
   ordering, state transitions and complete frames at matching phases. Inspect
   enlarged crops and difference images for visual discrepancies; compare
   canonical pixels, not browser-scaled screenshots.
8. When stopping, record the decoded entries, dispatch tables, data addresses,
   observed state, evidence and unresolved contract. Keep unsupported paths
   dormant. A task name such as "port HUD" is not a recovered specification.

## Required function record and source links

Create a durable record under `analysis/functions/` for each represented DOS
function. Use its established DOS symbol as the shared ID; do not assign one
until the entry is verified. Record:

- shipped-image SHA-256, build, canonical entry/range, overlay identity where
  relevant, static evidence and a reached execution witness;
- purpose, inputs, outputs, return behaviour, global reads/writes, aliasing,
  callbacks, ordering and dependencies;
- numeric widths, signedness, scales, intermediate precision, wrap/truncation,
  shifts, rounding and observable flag behaviour;
- data layouts, alignment, byte order and pointer/segment interpretation;
- JavaScript and m68k/DSP symbols, including split/merged mappings;
- fixture paths, exact capture/comparison commands and measured scope;
- a difference ledger: prove "no difference" or identify the platform adapter;
  unresolved requirements are **Unproven**, excluded from supported paths.

At every implementation definition, name the DOS ID and entry/range and link
the record. File-level comments and separate maps are insufficient. Helpers
retain parent mappings; merged routines preserve all IDs and separate records.
Hardware-only definitions say `DOS: N/A - platform replacement` or
`Target artefact` and record their logical boundary and hardware checks.

Decode DOS little-endian fields explicitly at resource/state boundaries and
use native numeric values afterward. Decode mixed records field by field;
leave byte streams in their original order. Map segmented DOS pointers and
callback identities explicitly rather than byte-swapping them into native
pointers. JavaScript must preserve wide intermediates and integer semantics;
native code must preserve the recovered precision, not a convenient guessed
fixed-point format.

## Target and acceptance gates

MC68030 is the baseline. Equivalent CPU instruction selections and CPU/DSP
execution choices may vary mechanisms, never game behaviour. The CPU owns
state, input, resource loading, UI, composition and VIDEL presentation. Use
double buffering with VBL publication; verify memory placement, cache handling,
interrupts, input and cleanup on the target. DSP command/status traffic must
not assume direct framebuffer access. Record buffer ownership, message layouts,
memory budgets and measured handshake timing before adopting a DSP workload.

Convert original palette-indexed assets to the declared RGB565 surface through
documented tables. Preserve a canonical DOS pixel/palette fixture and compare
its documented RGB565 conversion with target output. This presentation boundary
does not relax game-state, arithmetic or sequencing contracts.

Accept in order: DOS function entry/exit state → JavaScript fixture parity →
native fixture parity → integrated route/state ordering → full rendered frames
and transitions → measured target performance. CPU/DSP or JavaScript/native
agreement alone is never DOS proof. Report the first differing field/pixel and
retain source/build hashes and exact tested scope. Every optimization reruns
the affected contracts, including frames capable of exposing the change.

The existing reverse-engineering next steps in [AGENTS.md](../AGENTS.md) remain
prerequisites. Select a reached vertical slice and recover its dependencies
before implementing it; no unresolved RTLink mapping or resource contract is
made supported by adopting this document.
