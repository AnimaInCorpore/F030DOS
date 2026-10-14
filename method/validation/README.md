# Shared lowering and checkpoint validation

These are host analysis tools, not a game implementation or a new behavioural
authority. Invoke them from F030Method or put that checkout on Python's import
path. They are used in place; the DOS-harness sync does not copy them.

`flags.liveness` computes backward flag requirements over an adapter-supplied
graph. Unknown successors and explicit escapes observe every flag. Adapters
must prove unconditional writes and accurate successors; undefined flag effects,
dynamic zero-count shifts, partial flag writes, unknown calls and exits stay
conservative. The
Panzer General adapter uses Capstone's x86 effects and deliberately does not
claim precise interprocedural return analysis.

`checkpoints.compare` compares ordered `{key, state}` rows using explicit
fields. Keys include route/pass/phase where needed. Empty expected traces,
duplicates and missing/null fields are errors; order, missing/extra records,
types and values are exact. Timestamps outside the selected state are ignored.
No memory or flag bytes are masked. `byte_difference` identifies the first
different byte or length boundary. The consumer still verifies DOS/build/input
identity and supplies endian/width normalization and scope gates.

`profile.summarize` attributes collector-supplied target cycles to source
function IDs and PCs. It rejects mismatched source, generated and linked hashes,
unmapped events and unknown checkpoints. Every logical checkpoint appears in
the denominator, including zero-work checkpoints. It does not collect cycles
itself, estimate hardware performance or establish original-machine cadence.
Runtime/helper/idle events need explicit site records if included; omitted
events must be identified in the collector's scope, never called total frame
cost. A generated source map must be bound to the linked binary by the collector.

```sh
python3 -m unittest validation.test_validation
python3 -m validation.profile source-map.json optimized.events.json
```

## Consumers and checks (2026-10-10)

- Panzer General's production translator uses flag liveness, retains source-PC
  labels (including eliminated comparisons) and optionally emits a JSON map.
  `--conservative` is an equivalent-mechanism diagnostic baseline. It rejects
  overlapping instruction entries and intervening x86 flag writes; optimizes
  dead register comparisons/tests and proven sign/zero result moves. Memory
  reads, unknown exits and call flags are retained. No sequence interiors are
  merged or made dispatchable by this change.
- PG's `tools/x86x/bench_flags.py` runs the actual emitter on Musashi in both
  mechanisms and checks independent integer result/branch models. It emits
  identity-bound cycle events and source-attributed profiles. Synthetic tests
  supplement the native retained-DOS-fixture gates; they do not replace them.
- PG's RNG gate compares fixture checkpoints and reports the first differing
  byte; the geometry gate also reports the first differing byte.
- Comanche's replay comparator uses exact field comparison while retaining its
  DOS replay cursor, source/build checks and 284-record shake boundary. Missing
  fields on both sides now remain Unproven instead of comparing equal.

The algorithms are available to the whole family. Other ports need their own
evidenced graph or trace adapters; no runtime changes are installed there merely
because they are manifest members. Results and commands are recorded in
`analysis/stearcade-implementation.md`.
