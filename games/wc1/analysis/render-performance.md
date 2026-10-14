# Renderer performance notes

## Falcon-specific lesson adopted from F030Arcade

`../F030Arcade`'s renderer work points to three constraints that apply to WC1:

1. decode and cache resource data outside the hot draw loop;
2. use native 68030 stores and unrolled loops at a platform-owned pixel
   boundary; and
3. treat generated/JIT plotters as a later, profiled optimization because the
   68030's direct-mapped 256-byte instruction cache makes a larger “fast” loop
   capable of evicting itself.

The direct-store and cache-size guidance is documented in
`../F030Arcade/PORTING.md`'s self-modifying-renderer and expanded-cache
sections. Its measured Timer-A renderer profiling in
`../F030Arcade/games/snowbros/PROGRESS.md` is also the model for a later WC1
per-pass profiler.

## Adopted optimization: RGB565 presentation

WC1 already keeps the game renderer indexed, as required by its DOS resource
and transparency contracts. The old target build compiled `src/c2p.c` with
the host-neutral byte-order implementation. On the 68030 that generated a
per-pixel sequence containing a palette load, a copy, a shift, two byte stores,
and pointer arithmetic.

The target now builds `src/c2p_fast.s`. It retains the same indexed source,
palette, byte order, frame size, null-pointer behavior, and page-flip seam, but
does eight pixels per loop and writes each palette entry with one native
`move.w`. This is a Falcon platform replacement, not a DOS function
translation; the function record is
`analysis/functions/c2p-present.md`.

The object disassembly makes the local saving explicit: the former compiler
loop had the index clear/load, palette address arithmetic, colour copy and
shift, two byte stores, pointer increment, compare and branch in its one-pixel
body. The target loop has four pixel instructions (`moveq`, indexed byte load,
indexed word palette load, native word store), repeated eight times, followed
by one `dbra`. This is an instruction-shape improvement, not a whole-game
throughput measurement.

The transformed sprite path also has a restricted Falcon fast path for
`angle == 0`, used by scaled flight effects and eligible flight objects. Its
source coordinate samples still come from the exact `rle_round_ratio()` rule,
but the separable X/Y maps are built once per object. The inner loop then
reuses a single decoded scratch row instead of dividing twice and recomputing
its row offset for every destination pixel. Rotated objects stay on the
original general path until a separate fixture-backed optimization is proven.

The title callback deliberately fences this path out. A capture after the
first version of the optimization showed that faster title drawing advanced
the VBL-coupled attract sequence to a later credit frame at the established
VBL-2800 checkpoint. That violates the accepted title cadence even though the
individual pixels are valid. This is the same timeline gate documented by
`../F030Arcade/PORTING.md`: renderer speedups must be checked for simulation
and presentation phase drift, not only visual corruption.

The host `src/c2p.c` and `tools/c2p_smoke.c` remain in place as the
architecture-neutral golden-pixel check. This keeps the optimization
observable without making a host compiler's byte order part of the target
contract.

## Validation and limits

- `make test` checks that the target assembly owns the Falcon symbol and that
  the host reference remains present.
- `make truecolor-smoke` checks all 64,000 pixels and 128,000 output bytes.
- `make build` checks vasm/vlink integration.
- Hatari title captures at the established VBL checkpoint must remain
  pixel-identical.

WC1 does not yet have a Timer-A per-pass profile, so these changes are
justified by the generated instruction shape and bounded contracts, not by a
claimed whole-game percentage. The rotated sparse-shape sampler remains the
next likely renderer hotspot; replacing its per-pixel divisions needs a
separate DOS-fixture-backed investigation.

A 1,200-VBL Hatari `--benchmark` comparison was intentionally not promoted to
a speed claim: the old C-linked image measured 102.7 VBL/s and the current
image 102.1 VBL/s, while the normal 600-VBL smoke runs vary around 101–102
VBL/s. The run includes title simulation and changed surrounding code layout,
so it cannot isolate either renderer kernel. Add a WC1 Timer-A per-pass probe
before publishing a whole-game percentage.
