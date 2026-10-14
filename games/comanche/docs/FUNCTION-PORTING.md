# Function-level porting and verification

This document makes the existing DOS → JavaScript → m68k method concrete for
the supported Comanche attract slice. It supplements the
[priority plan](PORTING-PLAN.md), [semantic map](X86-M68K-MAP.md), and
[CPU compatibility record](../analysis/functions/cpu-compatibility.md).
It specifies requirements; it does not certify existing implementations.

Shared host comparison tools are in `../F030Method/validation/`. The replay
comparator imports their exact-field check while retaining DOS-cursor alignment,
build identities and the existing shake boundary. Missing fields on both sides
remain Unproven; elapsed timestamps do not define a match. Run
`python3 tools/test-compare-boundary-traces.py` for its negative controls. See
`../F030Method/analysis/stearcade-implementation.md` for the shared translator
bench and its explicitly synthetic performance scope.

## Unit of work

Use a reached DOS function and its recovered contract as the default unit of
implementation, review, and verification. Port small dependency groups of
functions and their required helpers, then verify their integration. The
hashed DOS executable and captured execution remain the authority.

Verify entries before assigning IDs. Shared tails, alternate entries, and
indirect callbacks may cross disassembler function boundaries. A native
routine may split or combine DOS routines if the record preserves every
canonical ID, mapped range, entry/exit boundary, and side effect. Helpers retain
their parent mapping; platform adapters have an explicit `DOS: N/A` identity.
Do not invent a `FUN_` identity for an internal label or an uncertain entry.

For every reached function, require:

- canonical DOS ID, verified range, image identity, and execution witness;
- inputs, outputs, return behavior, global reads/writes, aliases, and callbacks;
- field layouts, arithmetic semantics, and relevant flag dependencies;
- JavaScript and m68k counterparts, including split/merged mappings;
- specific fixtures, capture commands, and a ledger of platform differences;
- explicit unresolved requirements marked **Unproven**.

## Numeric and memory contracts

Record each field's width, signedness, fixed-point scale, byte order, alignment,
and interpretation. Record intermediate widths, overflow/truncation points,
shift counts, rounding, carry/borrow use, and partial-register behavior where
observable. A mathematically equivalent expression is insufficient if it
changes one of these boundaries. Preserve the timing of snapshots and writes:
frame-start flight state and the temporarily substituted camera are distinct.

Decode little-endian DOS numeric fields explicitly at the resource boundary;
use native values afterward. For example, bytes `78 56 34 12` decode to
`0x12345678`, which m68k stores in the opposite byte order. Arithmetic results
need no additional swap. Decode mixed records field by field; byte streams,
tags, palette channels, and compressed payload bytes retain their ordering.
Map DOS addresses and callback IDs to native pointers/dispatch entries rather
than treating byte-swapped DOS addresses as valid native pointers.

Keep authoritative fixed-point state at DOS precision. In particular, retain
10.22 flight accumulation through all displacement terms and convert to 16.16
only at the documented rendering boundary. Compare decoded canonical fields,
not raw dumps with different byte orders or native structure layouts.
JavaScript must explicitly preserve integer wrap and wide intermediates too.

## Adjacent source comments

Every implementation definition must name its canonical DOS identity and link
to its durable record. File-level headers or a separate map alone are
insufficient. Use the existing source-header vocabulary; this illustrative
template contains placeholders, not evidence for a specific routine:

```asm
; DOS: <established DOS ID and verified entry/range>
; Record: analysis/functions/<record>.md#<anchor>
; Route: <specific reached-route witness and boundary>
; Port: <native symbol and role>
; Preserved: <inputs, outputs, state effects and ordering>
; Arithmetic: <widths, signedness, scale, wrap/shift/rounding rules>
; JS: <reference symbol; explain any split/merged mapping>
; Fixtures: <specific fixture IDs/paths and comparison command>
; Difference: <documented platform adaptation, or none established>
; Kind: <direct, adapted, or target artefact>
; Status: <implemented scope and unresolved requirements>
```

JavaScript comments must carry the same DOS ID and record link. Cite DOS
instruction addresses beside non-obvious operations. Detailed layouts and
contracts belong in the linked record; comments should summarize and locate
them. Store measured results and exact source/build hashes in acceptance
artifacts. A comment saying “ported” or “PASS” is not parity evidence.

The current header scanner validates only part of this schema. Completing
per-routine JS/fixture/reach mappings and machine validation remains an audit
task; documenting these requirements does not establish compliance.

## CPU and platform boundaries

Keep shared game behavior separate from CPU instruction mechanisms and machine
support. MC68030 remains the baseline. Build-time CPU selection may choose
equivalent arithmetic or cache routines; it cannot change game precision or
behavior. Later Motorola 68k models retain the big-endian resource boundary,
but instruction availability, alignment, exceptions, and cache publication
must be checked for each supported model and board.

Every CPU build must pass the same DOS fixtures and normalized frame checks.
CPU-to-CPU equality is supplementary. Validate cache behavior, memory placement,
display publication, interrupts, input, and cleanup on the actual platform.
Support for another CPU does not establish support for another computer.

## Acceptance order and next milestone

Verify function entry/exit state with identical inputs, then replay ordering,
then complete rendered frames and sequence transitions. Compare at matching
function boundaries, replay cursors, and publication phases; report the first
divergence with the function, field, expected value, and actual value.

The retained 284-record DEMO1 comparison checks selected flight fields, view
variant, and view angle across DOS, JavaScript, 68030, and 68060. It stops
before record index 284, the no-damage bounce at `00019461`, because that
cross-machine comparison still lacks full VGA display-shake parity. The
JavaScript browser reference now applies a documented cropped-surface target
adaptation and continues through the authored cockpit and later passes; the
Falcon path remains stopped at the unsupported display boundary. See
`../analysis/functions/browser-attract.md#shake-timer`. Its PASS does not
establish exhaustive function coverage or complete pixel parity. The
[acceptance report](ACCEPTANCE-REPORT.md) records the measured scope and hashes.

The next milestone is paired complete-frame evidence: first a cockpit frame,
then the fixed-camera transition. Capture the same replay cursor and rendering
phase, record camera/page/panning, normalize the DOS palette through the
documented RGB565 conversion, and compare terrain, objects, cockpit, and HUD
together. Retain the first differing pixel and a difference image. Extend the
fixtures through chase/fixed-camera transitions, replay commands, all supported
passes, and buffer reuse. Function audit and stock-Falcon/accelerator checks
remain required independently; missing evidence stays **Unproven**.
