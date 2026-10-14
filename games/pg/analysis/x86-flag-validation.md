# Bounded translator flag validation

2026-10-10; supplements `x86-translation.md`. The production pipeline now uses
shared conservative flag liveness from `../F030Method/validation/`, removes dead
register comparisons/tests and reuses N/Z after same-width moves of a producer's
exact result. Unknown calls, returns, conditional shift writes and memory reads
stay conservative, including undefined flag effects. Overlapping instruction
entries and intervening x86 flag writes reject translation. Unique source-PC
labels and `--source-map` expose
bytes/rules/emitted-line counts for build-bound profiling; `--conservative` is
an equivalent-mechanism diagnostic.

`tools/x86x/test_translate.py` and `bench_flags.py` test the actual pipeline.
The 84-form/24-vector bench passes 4,032 executions with 28.4% fewer simulated
cycles in the synthetic cases; no current emitted PG routine benefits from
these patterns, so no game-speed gain is claimed. Retained DOS gates remain
mandatory. Reproduction/evidence: `../F030Method/analysis/stearcade-implementation.md`.
