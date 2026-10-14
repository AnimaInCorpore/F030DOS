# Current port review — 2026-09-07

Scope: source inspection of the CPU attract port against the standing porting
rules, with fresh browser proof, function audit, substitution check and
acceptance aggregation. No new DOS or Falcon execution capture was taken.

## Confirmed source differences

1. **Screen-shake timing is tied to rendering.** `src/game.s:218` calls
   `flight_shake_tick` once per game frame. DOS programs timer divisor 0x47B4
   at 00001CEB and advances the PRNG/countdown in the timer ISR at
   00001DB5–00001DE7. Rendering speed therefore changes the target shake
   duration and PRNG phase; it also stops advancing outside game ticks.
   `src/flight.s:445` documents this as a platform boundary, but preserving
   the timer's observable contract requires an independently modeled timer.
2. **JavaScript omits the native shake state.** The crash branch in
   `jsComanche/dos-runtime.js`'s `flightTick` bounces the aircraft but does not
   arm DOS [00019DC0]. Native `src/flight.s:333` does. JavaScript
   `buildBackdropDy(roll, pitch)` has no shake input, whereas native
   `src/render.s:634` subtracts `flt_shake_phase`. A crash/shake fixture is
   needed across DOS, JavaScript and native code; existing selected-state
   replay equality does not establish this contract.
3. **The display-shake consumers are omitted.** DOS 00001DF1–00001DFF
   programs pixel panning and 00015BBC–00015BC2 adds a phase-dependent display
   start offset. `src/flight.s:451` explicitly excludes both; target
   `publish_screen` publishes the buffer address without those offsets.
   Hardware writes need replacement, but the visible displacement needs a
   recovered RGB565 presentation equivalent or an explicit unsupported scope.

These findings were checked against `re/listings/comanche-flat32.lst` and the
current implementation. Their effect on particular authored demo frames has
not been measured in paired captures.

## Fresh verification and limits

- `node tools/prove-browser-attract.js`: PASS, all seven reported checks.
- `python3 tools/audit-function-matrix.py --out build/review-function-audit.json`:
  Unproven, 221 rows. The tool unconditionally leaves counterpart, fixture and
  exact-reach columns Unproven; this is not evidence that all 221 routines are
  behaviorally wrong or lack counterparts.
- `python3 tools/substitutions.py --check`: FAIL, generated inventory stale.
- `python3 tools/acceptance-report.py --skip-browser-proof --output build/review-acceptance.md`:
  replay PASS from retained evidence; function audit, complete frames,
  complete sequence and real-target checks Unproven. This aggregation does
  not rerun native replay or produce new paired DOS/target frames.

The CPU-only milestone intentionally defers DSP; it does not satisfy the
eventual shipping DSP rule. `AGENTS.md` still says the implementation source
tree is reset and contains only a README, contradicting the recreated current
tree and `src/README.md`. The guide needs a current-state correction.

No implementation changes were made by this review. Next verification should
cover timer-phase-coherent crash/shake state and complete displayed pixels,
then complete the reached-function mapping and paired sequence evidence.
