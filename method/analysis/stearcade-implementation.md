# STEArcade ideas implemented in the DOS family

2026-10-10. Scope: shared host validation tools, the existing Panzer General
bounded translator and two consumers (PG and Comanche). No new supported game
functions, DOS timing model, whole-game translator or hardware target is claimed.
See `analysis/stearcade-translator-review.md` for the source-backed rationale.

## Implementation and reproduction

`validation/` owns conservative graph flag liveness, exact logical checkpoint
comparison, first-byte diagnostics and identity-bound source-cost aggregation.
The modules have no external Python dependencies. They are imported from the
master checkout, not copied to each project. See `validation/README.md` for
schemas and limitations.

PG `tools/x86x/translate.py` consumes liveness with Capstone's x86 flag effects.
Unknown call/return contracts stay fully live; undefined effects and
variable/zero-count shifts retain input flags. Dead comparisons/tests are removed
only for register and immediate operands. Native CCR reuse crosses only proven preserving forms or
same-width moves of a sign/zero producer's exact result. No uncertain joins or
code gaps are crossed. Unexpected overlapping entries and intervening x86 flag
writes reject translation. Every source instruction keeps a unique target label;
branch labels are global and function-qualified to survive vasm local-label
scope changes. JSON maps report DOS ID/PC, bytes, rule and emitted-line count;
line counts are not cycle estimates. `--conservative` selects the diagnostic
baseline, not different game behaviour.

The production-emitter bench (`tools/x86x/bench_flags.py`) covers 84 arithmetic,
test and move/branch sequence forms at 8/16/32 bits with 24 vectors each, in
conservative and optimized mechanisms: **4,032 native executions pass** against
independent width/result/branch models. It measures **69.90 vs 50.05 Musashi
68000 cycles/case (28.4% fewer)** for these synthetic sequences. This is neither
DOS parity nor Falcon hardware timing. An inventory scan found no emitted PG
game routine benefiting from these particular flag patterns; do not infer a
game-speed gain from the synthetic result. Coverage remains 344 implemented
of 643 inventory functions, 142 closed under calls; evidence grades are not
promoted by the optimization tests.

Commands from PG (choose a Python environment containing Capstone and
machine68k; vasm/vlink default to the local F030Arcade tools):

```sh
python3 tools/x86x/test_translate.py
python3 tools/x86x/bench_flags.py --out build/flags-bench
python3 tools/x86x/translate.py sub_00010976 sub_00048105 \
  --out build/x86x/geometry.s --source-map build/x86x/geometry.source.json
python3 tools/check-native-rng.py --out build/flags-rng --translated
python3 tools/check-native-geometry.py --out build/flags-geometry --translated
```

RNG passes 19 retained DOS cases/152 bytes and geometry passes 12/196 bytes on
Falcon030 Hatari. The loader also passes 6,779 bytes, shape drawing passes 32
cases/271,911 bytes, and the compositor passes one fixture/316,428 bytes with
its existing present-boundary stub and 14 MB arena. All 344 implemented
inventory functions assemble with `-m68000`. JavaScript RNG, geometry, loader
and display-driver contract checks pass; these remain the pre-existing scopes.
Shared tests cover loops, unknown exits, partial flags,
duplicate/missing/reordered checkpoints, exact types, stale maps and unmapped
cost events. PG pipeline tests include changed flags, sign/zero versus carry,
zero-count shifts, undefined flags, captured-branch clobbers and a jump into an
instruction interior. Synthetic evidence artifacts remain ignored under PG
`build/stearcade-*`; their maps and profiles
retain input/generated identities, with the bench also recording linked bytes.

Comanche `tools/test-compare-boundary-traces.py` checks missing fields on both
sides, first divergent cursor/field and timestamp-independent alignment. The
cached DEMO1 JavaScript/DOS comparison passes 284 records. Current cached native
traces are stale and remain **Unproven**; this review does not refresh them or
certify Falcon gameplay. Neither consumer drops its existing build identity,
DOS authority or support-boundary checks.

Local bench reproduction used the existing STEArcade Python 3.14 environment
for machine68k and the host's Capstone 5.0.7 package; no packages were installed:

```sh
PYTHONPATH=/opt/homebrew/lib/python3.14/site-packages \
  ../STEArcade/venv/bin/python tools/x86x/bench_flags.py \
  --out build/stearcade-flags-20261010-conservative-af
```

The bench result retains backend, assembler/linker, runtime macro, collector
and shared-analysis content hashes plus seed 1030. The dependency remains
optional host tooling, not an STEArcade or Python dependency of a Falcon game.
