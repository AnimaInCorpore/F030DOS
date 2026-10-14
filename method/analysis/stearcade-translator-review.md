# STEArcade translator: lessons for the DOS ports

Source review, 2026-10-10. Inspected STEArcade HEAD
`28fe0cbffc9689577ac47f894dce32206b6b5850`; its working tree has Bubble
Bobble renderer/documentation changes and untracked tools. No parity tests,
gameplay or performance measurements were rerun. STEArcade is an external
technique provider, not a DOS-family member or behavioural authority.

## Transferable mechanisms

- `engine/translate.py:compile_code` centralizes discovery consumers, return
  analysis, flag liveness, CCR analysis and emission. Test sequences use that
  same compiler entry, avoiding a test-only lowering path.
- `engine/z80x.py:ret_targets` follows flags through calls and proven balanced
  returns. Stack modification, inconsistent depths and foreign entries reject
  precise return analysis. For x86, recover its own stack/calling conventions
  and preserve conservative flag requirements when proof fails.
- CCR reuse is a forward must-analysis; guest-flag liveness is a backward
  analysis. `compile_code` recomputes liveness after identifying native CCR
  consumers. This can remove redundant flag materialization, but native moves
  also clobber flags: never infer equivalence from similar instruction names.
- `Emitter.boundaries` protects entries, hooks and branch/call targets from
  sequence merging. Interior merged PCs become `z80_badpc` dispatch entries;
  missing targets also trap. Coverage PCs seed discovery but are not all joins.
  The DOS analogue needs verified byte boundaries and indirect-entry evidence;
  coverage alone does not prove an entry impossible.
- `engine/xbench.py` compares opcode vectors and short random sequences on
  Musashi with the Z80 reference across six layouts, checking registers,
  memory, next PC and live flags. Adapt this test structure to a bounded x86
  lowering pilot, retaining the separate DOS-validated JavaScript reference.
- `engine/xdiff.py` aligns two builds by translated guest instructions and
  logical interrupt checkpoints. This prevents a faster target from appearing
  wrong simply because it has advanced further. It is an optimization
  regression check, not original-machine validation; Comanche's DOS interrupt
  phase and cadence still require recovered execution evidence.
- `engine/xprof.py` charges target instructions to original source PCs and
  reports cycles per guest game frame, with idle work separated. Use equivalent
  source attribution to decide whether lowering or rendering dominates before
  optimizing; simulated cycle counts still require Falcon measurements.

## Limits and Comanche application

STEArcade's architecture reports 1.08–1.73x translator gains across different
games after its recent register/flag/merge changes. These are reported Musashi
results, not a prediction for x86 or Falcon030. Its Z80 register packing,
banked-ROM rules, interrupt adapters and planar Blitter renderer cannot simply
be imported into Comanche's x86-32 semantics and RGB565 composition.

Its comparisons exclude dead stack storage and, in Galaga's build comparison,
interrupt-saved flag bytes. Such exclusions need observation/aliasing proof in
each DOS route: coroutine stacks, memory reads or original captures can make
apparently dead storage observable. Its discovery also uses heuristic table
termination, so table completeness must be established independently.

For Comanche, the useful next experiment is one recovered routine or recurring
arithmetic idiom: retained instruction-phase DOS fixtures, passing JavaScript
contract, assembler-verified native lowering, then conservative/optimized
comparison with source-PC diagnostics and measured target cost. This review
does not authorize whole-game translation or change support/acceptance status.
