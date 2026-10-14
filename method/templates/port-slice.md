# Slice <ID>: <observable result>

Copy or adapt this into the game's existing port plan. Replace placeholders;
`TBD` means missing evidence, never a passing gate. Link existing records rather
than duplicating them. This template follows F030Method `METHOD.md` §0.1,
§0.3–§0.4, §4.6 and §4.8; dependency operations are in `DEPENDENCIES.md`.

## Scope and checkpoint

- Status: planned / evidence-blocked / implementing / validating / supported.
- Selected DOS build, executable/media hashes and resource/configuration set:
  <identity record>.
- Starting checkpoint: <last verified connected state, or cold boot>.
- Player route: <ordered inputs/ticks, transition and observable result>.
- Integration point: <symbol and state/ABI contract>.
- Supported modes/devices/states: <explicit scope>.
- Recovered-function inventory: <link; retain all recovered functions, while
  prioritizing detailed contracts by this route's dependency closure>.
- Deferred paths: <inventory IDs and build/configuration evidence that the
  supported route excludes them; one trace's failure to reach a path is not
  exclusion; no stubbed semantic dependencies>.
- DOS route manifest and cumulative replay including earlier slices: <links>.

## Dependency closure

Each row describes a requirement on a provider. Follow prerequisites
transitively; include state initialization, resources, indirect dispatch,
callbacks/interrupts, input/timing, platform seams and build/capture tools.
Record cycles as a group with a defined state owner and initialization order.

| ID | Provider / revision or hash | Consumer / prerequisites | Required contract and evidence | Readiness / next action |
|---|---|---|---|---|
| <ID> | <function record, asset, seam or tool> | <consumer IDs; depends on IDs> | <representation, widths, ownership, fixture> | <missing / available-unvalidated / validated for scope / blocked / stale> |

- Closure review: <unresolved edges and their blocking routes; witnesses for
  reachable paths and build/configuration evidence for excluded paths; who owns
  shared state and when it becomes valid>.
- Function inventory and DOS difference ledger: <links, including unported and
  deferred functions; the inventory is an accountability map, not the analysis
  work queue; evidence grade is separate from readiness>.
- Shared function IDs: <canonical ground-truth DOS names, hashed build and
  verified entries; same IDs in records, JS/m68k annotations, route and fixtures>.
- Tool/environment record: <provider revisions, patches, host, executable
  versions, emulator/target configuration, media hashes and reproduction steps>.
- Indirect transfers: <site/context, pointer producer or table, index domain,
  extent/target/exit evidence; candidate misses stay unproven until DOS-checked>.
- Runtime code instances: <overlay/unpack/patch producer, captured bytes,
  lifetime and invalidation or verified variant selection; or evidenced N/A>.

## Automation within this slice

Keep this section small; use existing reports. Code generation is optional.

- Repeated work to remove: <placement, table recovery, fixture plumbing or a
  bounded lowering rule; why this unlocks the active route>.
- Baseline: <DOS capture, passing semantic JS fixture, current native result
  or explicit missing prerequisite>.
- Implementation choice: <hand-written native code or generator/rule and its
  semantic domain; source contexts kept distinct or safely handled at runtime>.
- If generated: <input/tool/helper hashes and command; deterministic source
  and linked-PC maps to canonical DOS IDs; unresolved-work report by route>.
- Diagnostic stop: <unsupported site/context, operation/target and state;
  target/harness boundary, never an invented DOS function error path>.
- Result: <manual work or diagnosis time saved, parity result, generated code
  and resource cost; continue, narrow or abandon this experiment>.

## Next blocking experiment

- Question: <one unknown that prevents this route>.
- Competing readings: <prediction A and prediction B>.
- Probe: <working directory, command, inputs, stop/checkpoint and run limit>.
- Discriminating observation: <state, bytes, event order or transition>.
- Actual result and evidence: <TBD until run>.
- Decision / next step: <what the result unlocks, or how the probe must change>.
- Independent work available while blocked: <grounded prerequisite>.

## Comparison and delivery gates

List exact commands and evidence paths; unchecked or unavailable is not passed.
Expected canonical outputs come from retained DOS evidence. Presentation
captures supplement raw state/framebuffer/event comparisons.

- Alignment: <logical checkpoint and phase, completed game updates,
  interrupt/input event position; coherent capture or reconstructing replay>.
- Comparison domains: <game state, event/command streams, logical output;
  exact normalization and justified excluded ranges, or none>.
- First divergence: <last equal / first unequal checkpoint, differing byte or
  field, writer/source map, retained reproduction; or evidence of equality>.
- Completion: <full in-scope cycle or enter/leave transition; host frame counts
  and nearest-looking images do not establish completion or parity>.

| Gate | Command / working directory | Expected invariant / scope | Actual result / evidence |
|---|---|---|---|
| Decode | <command> | <all required inputs, structural and independent semantic checks> | TBD |
| Disassemble + prove | <command> | <byte rebuild, address map, classification/data guard separately> | TBD |
| Understand | <capture/replay command> | <DOS entry/exit state, side effects, ordering and fixtures> | TBD |
| Generation, if used | <regenerate/compare and report command> | <identical inputs reproduce sources/maps; no unresolved translation reachable in supported scope> | TBD / evidenced N/A |
| Browser contract | <command> | <executable JavaScript counterpart, same DOS function record; canonical routine/state fixtures equal DOS> | TBD |
| Target contract | <CPU-restricted build and execution commands> | <browser contract gate passed; native target passes the same fixtures, with retained object/listing> | TBD |
| Connected flow | <DOS, browser and target replay commands> | <boot/previous checkpoint through this result via real driver/timing path> | TBD |
| Regression | <affected existing fixture commands> | <earlier supported routes still equal> | TBD |
| Resource envelope | <target measurement command> | <declared timing, memory and stack headroom> | TBD |

## Target feasibility

- Minimum machine: <CPU/clock, RAM, display, required DSP/hardware>.
- Simulation cadence and presentation relationship: <DOS evidence>.
- Peak memory budget: <code/data, simultaneously live resources and converted
  copies, framebuffers, queues, stack, scratch; DSP program/X/Y if applicable>.
- Timing budget: <load versus steady state; simulation, rendering, transfer,
  waits and presentation; required headroom and rationale>.
- Estimate / isolated probe / measured connected route: <label each number,
  record machine settings and distinguish emulator from physical hardware>.
- If over budget: <measured bottleneck, proposed mechanism change and unchanged
  parity fixture; or explicit feasibility blocker>.

## Handoff and support decision

- Required dependencies all validated for scope: <evidence or remaining gaps>.
- Closed substitution list / unresolved differences: <review link>.
- Browser and target implementation symbols: <function inventory link>.
- Changed dependency identities and results made stale: <affected consumers,
  fixtures/caches and revalidation results>.
- Supported result: <precise route and configuration, or why it remains blocked>.
- Remaining work and next attachment symbol: <explicit handoff>.
- Transferable findings upstreamed to F030Method: <links or none>.
