# Comanche browser attract function records

This is the durable §4.2 record for the connected JavaScript milestone. The
authoritative DOS image is
`re/unpacked/COMANCHE.UNPACKED.EXE`, SHA-256
`4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697`.
The DOS disassembly and captured execution decide behavior. The browser is a
deterministic reference and target-surface adaptation; it is not a second
authority. The CPU-only Falcon counterpart is recorded separately in
`analysis/functions/falcon-attract.md` and is governed by the same DOS route.

The connected path is the DOS attract cycle: campaign `0`, its authored
mission resource families selected by pass 0 through 3, the four supplied
`DEMO<n>.SCR` streams, and the opening pages. Browser timing is a labelled
fixture cadence only. DOS frame/VBL cadence remains `Unproven`; the shake
timer's PIT divisor and state transition are recovered below.

## `shake-timer`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00001D20`: timer ISR entry installed at 00001CB4/00001CC7, verified instruction at 00001D20. Helpers map to 00001DB5–00001DE7; captured exit 00001E03. Same hashed DOS image as above; flat SHA-256 `a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c`. |
| Recovered contract | Read/write three little-endian unsigned dwords: RNG [00019DB8], phase [00019DBC], countdown [00019DC0]. Every timer event XORs RNG with A50A50A0, adds 00050A05 modulo 2^32, rotates right three. If countdown is zero, leave phase untouched; otherwise decrement and publish RNG&3, forcing phase zero when the counter reaches zero. No game-frame dependency. |
| Timing | 00001CEB programs PIT divisor 0x47B4 (18356). The host adapter accumulates 1193182 per 200 Hz host event and emits a PIT event at threshold 200*18356. **Target artefact:** event quantization is at most one 5 ms host interval with no cumulative rate rounding. Physical oscillator accuracy, interrupt latency and initial DOS/target timer phase remain Unproven. This does not recover the game-frame cadence. |
| Implementations | JavaScript `shakeTimerTick`, `advanceShake200Hz`; m68k `src/shake.s` `flight_shake_tick`, `flight_shake_clock`. `src/vbl.s` installs/restores a chained Timer C handler using the current VBR/MFP vector base. Browser RAF elapsed time feeds an independent 200 Hz accumulator; deterministic fixture game ticks do not invent elapsed timer time. |
| Related consumers | 00019461 arms countdown=10 in the no-damage crash path. Both flight implementations now arm it. 00007DB5 subtracts phase **after** pitch clamping; JavaScript `buildBackdropDy` and native `backdrop_build` carry this term. |
| Fixtures | `python3 work/capture_shake_contract.py` captures 40 input/output cases from the running original at verified entry/exit PCs, using a disposable QEMU disk snapshot. Inputs vary unsigned RNG boundaries, idle/active phases and countdowns 0/1/2/10. `python3 tools/check-shake-contract.py` compares JavaScript and both native CPU binaries to `build/shake-contract/dos.json`, and tests timer partitioning, 2000 host ticks and horizon phase subtraction. Generated logs/hashes remain under `build/shake-contract/`. |
| Difference ledger and supported scope | Timer arithmetic is checked against DOS execution. Host clock quantization is explicit; it is not exact interrupt-phase parity. Full display shake remains **Unproven**: 00001DF1–00001DFF programs fine panning and 00015BBC–00015BC2 adds table [00015B60] to display start. The browser target adaptation applies the recovered phase displacement to its 320-wide RGB565 crop, clears the newly exposed crop edge, and keeps the replay running. It does not certify full 328-wide VGA page parity. The retained DOS/JavaScript/Falcon boundary comparison still stops at DEMO1 record 284, before that presentation difference. |

The display offset table starts with little-endian dwords `0,81,164,245`.
These are VGA address units, not RGB565 pixel offsets. The browser converts
them to the nearest whole row using the DOS `0x52` row stride and applies the
phase's `value*2` pixel pan after composition. This is an explicit target
surface adaptation so the attract can continue into later cockpit and mission
passes; it is not a claim of full VGA page parity. Exact recovery still needs
all four phase values with CRTC/attribute-controller state, full page contents
and scanout at matching boundaries, then a complete displayed-window compare.

The detail level is a decision rather than a recovery, and it has to be the
same on both sides. `00026211` selects a `.DTL` from `[00025DD4]` - `'0'` high,
`'1'` medium, anything else low - and the three files declare 250, 180 and 100
rings. The shipped install selects medium; this project builds for HIGH, and
`docs/DOS-ORACLE.md` carries the byte that moves the oracle with it. A capture
taken at the other setting is not comparable: its ring schedule, its projection
pages and its per-ring `B` all differ, and nothing announces the mismatch
except `certify-marcher.py`'s own `ring_steps` line. The browser loads
`HIGH.DTL` and therefore has no runtime Detail menu; `src/dtl.s` does, and
selects the same file.

High was kept deliberately and its cost measured: 128 game frames per 1000
VBLs against medium's 168, so 24% slower for 250 rings against 180 over 985
versus 954 map units - depth resolution rather than draw distance. The
measurement and the decision are recorded in `src/dtl.s`.

## Route-first source boundary

This milestone's JavaScript sources were created only after tracing the route
through the genuine DOS image with QEMU execution telemetry, repeatable attract
inputs, and active-state snapshots. The route reaches the attract/frame driver,
replay/flight integration, mission object factory, callback table, transient
allocator, terrain/object transform and draw pass, and the BULL/CHAF/ROCK/HELL/
STGR/BOOM state handlers, and the view basis with its per-variant handlers.
The durable witnesses are
`work/qemu_out/attract-trace-report.txt`,
`work/qemu_out/object-state-walk.txt`, and the runners
`work/run_qemu_exec_trace.py`, `work/trace_attract_report.py`, and
`work/inspect_qemu_state.py`. Any future JavaScript or M68k source for this
milestone must link to this route or remain dormant/`Unproven`; the Falcon
source mapping is maintained in `falcon-attract.md`.

The view route was traced separately, because full `exec` logging cannot reach
it: 60s costs 1.2 GB and consumes six replay records, and DEMO1's first view
key is at record 30. `work/qemu_out/attract-exec-recheck.log` therefore
establishes reachability only — `00007D25` and `00007BF0` entered, the two
external handlers not — and the behavioural fixtures come from
`work/trace_replay_flight.py --view-basis`, which breaks at `00007D7F` once per
integration tick. Its 800-frame capture of DEMO1 is
`work/replay_dos/view-basis-recheck.json` and the matching flight state is
`work/replay_dos/flight-recheck.json`. Both are derived and gitignored;
regenerate them with those runners rather than expecting them in a clean
checkout.

The executable proof gate is `node tools/prove-browser-attract.js`. It checks
the hashed DOS image, verifies that every JavaScript definition is annotated
as DOS-backed or explicitly target-only, compares the generated Q31 table
against flat data `00032120`, decodes all four mission/resource families, and
exercises the pass-one attract transition and replay boundary. It also asserts
the nine mission placement records with their `0,2,2,2,2,2,2,2,2` types and
slot 31's dispatch, and DEMO1's view-key timeline against the capture above.

The Falcon counterpart is certified separately by
`tools/certify-replay-flight.py`, which runs the port under Hatari and diffs it
against the same DOS traces at the same replay record.

## `browser-host`

| Field | Record |
|---|---|
| DOS identity and evidence | N/A - platform replacement for the browser DOM, `fetch`, Canvas presentation, and lifecycle. The DOS symbols it exposes are recorded by the runtime/source records that it constructs; it does not add game semantics. |
| Recovered function | None. Bind the connected page to the deterministic DOS attract reference and stop on missing/invalid source data. |
| Implementations | `jsComanche/game.js`: `load`; `jsComanche/dos-runtime.js`: `ComancheRuntime.create`; `jsComanche/index.html` and `style.css`: target surface. Falcon counterpart: `src/start.s`, `src/vbl.s`, and `src/main.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Target artefact:** DOM lookup, HTTP asset import, Canvas conversion, `requestAnimationFrame`, and lifecycle cleanup replace DOS process/VGA plumbing. They cannot select alternate missions, synthesize assets, or change valid logical state. |
| Fixtures and status | `tools/prove-browser-attract.js` source-annotation audit and mocked Canvas construction. **Target boundary proved for the connected valid-input path;** real browser timing and DOS wall-clock cadence remain `Unproven`. |

## `sine-table`

| Field | Record |
|---|---|
| DOS identity and evidence | Flat data `00032120-00032B1F`, consumed by `FUN_00007D25` and `FUN_00018F94`; source image SHA-256 is the one at the top of this file. The table is 640 little-endian signed Q31 dwords: 512 revolution entries plus the 128-entry cosine overhang. |
| Recovered function | Shared sine/cosine lookup data. Entry `i+128` supplies the cosine for entry `i`; the overhang is part of the contract. |
| Implementations | `jsComanche/sine-q31.js`: `ComancheSineQ31`. Falcon counterpart: shared Q31 data in `src/render.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **None in the stored values:** the JavaScript typed array is compared byte-for-byte with the DOS flat data. The typed-array container is a target representation only. |
| Fixtures and status | `tools/prove-browser-attract.js#sine-table`; checks all 640 entries and the boundary entries `0`, `128`, `384`, `512`, and `639`. **Verified at the data boundary.** |

## `dos-file-boundary`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00016381` / `FUN_0001687D`, shared DOS resource open/read/decode path; canonical loader evidence in `docs/X86-M68K-MAP.md` and the recovered attract loader. |
| Recovered function | Open named DOS resources, read their authored bytes, and hand them to the format-specific decoder. File names and read order are part of the boundary. |
| Implementations | `jsComanche/dos-fs.js`: `DosFileSystem`; `jsComanche/dos-data.js`: `hostLoader`, `readDosFile`. Falcon counterpart: GEMDOS/native-buffer loaders in `src/resources.s`, `src/mission.s`, and `src/sprite.s`. |
| Difference ledger | **Target artefact:** a per-run `Map` and `fetch` replace DOS handles and the DOS filesystem. No IndexedDB, localStorage, metadata, retry, or alternate source is used. The imported bytes are unchanged. Host HTTP failure handling is outside the DOS function. |
| Fixtures and status | Installed asset tree and exact source hashes in the local asset inventory. **Ported at the byte boundary;** DOS handle timing and missing-file status outside the connected valid asset set remain `Unproven`. |

## `mission-selection`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00028F05` / `FUN_0002A1AD`, canonical range `00028F05-0002A299`; campaign/mission loader evidence in `docs/X86-M68K-MAP.md`. |
| Recovered function | The attract path forces campaign `0`, selects mission `n` for pass `n`, and installs that authored resource family before replaying `DEMO<n>.SCR`. It does not expose a free browser mission selector. |
| Implementations | `jsComanche/dos-data.js`: `loadAttractEvidence`; `game.js`: `load`. Falcon counterpart: `src/attract.s` and `src/mission.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Target artefact:** the first four authored mission records are selected directly from the parsed `0.MIS` stream instead of rendering the DOS text UI. Each pass owns its selected D/C/palette/sky bytes; browser catalog browsing, mission switching, and direct state injection are not supported. |
| Fixtures and status | `0.MIS` parse fixture and attract resource manifest. **Ported for the connected attract selection;** other menu-driven selection remains dormant. |

## `resource-decoders`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00016381` / `FUN_0001687D` resource loader and `FUN_0001644B` SG/KRL decoder family; canonical format evidence in `docs/ASSET-INVENTORY.md`, `docs/X86-M68K-MAP.md`, and the supplied assets. |
| Recovered function | Decode Kyle DTA payloads and palettes, KRL0/KRL1 payloads, SG directories and sprites, SKY's 512×150 column strips, HIGH.DTL's 1,251 little-endian dwords, and DEMO record boundaries. |
| Implementations | `jsComanche/dos-data.js`: `decodeDta`, `decodeKrl`, `parseSgImage`, `parseSkyImage`, `parseDtl`, `parseDemo`, and mission text decoders. Falcon counterpart: `src/resources.s`, `src/mission.s`, and `src/sprite.s`; CPU-only decode boundary. |
| Difference ledger | **Target artefact:** host-side range/shape checks reject malformed imports before the semantic runtime; they are not DOS game branches. DTA palette tails convert stored eight-bit DAC components to six-bit values, while SG bank palettes remain their authored six-bit bytes; both representations retain their widths, order, sentinels, and record layout. No fallback decoder is selected. |
| Fixtures and status | Installed DTA/KRL/SG/DTL/demo asset checks. **Ported at the decoded-data boundary;** malformed-input behavior is not claimed. |

## `attract-cycle`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00005690`, canonical range `00005690-00005AE3`; attract state entry, pass counter, screen timers, screen ownership, and transition order recovered from the disassembly and historical DOS capture. |
| Recovered function | Increment pass modulo four. Odd passes use `BACK.DTA`/fanfare for 480 ticks then `TPIC.DTA`/COMA for 600; even passes use `RH66SIDE.DTA`/ZOVE for 300. Draw current screen first, then advance the animation, pan, timer, and successor state. The first pass after a zero counter is pass one. |
| Implementations | `jsComanche/dos-runtime.js`: `AttractRuntime.enterNextPass`, `enterTitle`, `advanceAuthoritativeTick`, `advanceScreen`, `drawScreen`. Falcon counterpart: `src/attract.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Target artefact:** decoded 328-wide pages are copied into the left 320 browser columns; DOS CRTC page movement is replaced by source-row selection. **Grounded behavior:** ZOVE `3,3,2,2,1,1`, COMA 9-to-1 four ticks each, pan gate row 93, terminal row 150, helicopter/wobble arithmetic, and draw-before-tick order are retained. Browser presentation cadence is a 60 Hz fixture, not DOS timing. |
| Fixtures and status | `DEMO`/opening asset fixture, screen transition trace, and `advanceTicks`. **Ported/adapted for the connected screen path;** DOS wall-clock cadence is `Unproven`. |

## `frame-driver`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0000D3C0`, canonical range `0000D3C0-0000D8F5`; recovered frame order in `docs/X86-M68K-MAP.md`. |
| Recovered function | Save the viewer snapshot, render terrain from the current frame state, enter the active-object pass, publish the surface, consume the replay/input boundary, and compose cockpit/HUD in the recovered order. Attract installs the selected mission's authored object records before `DEMO<n>` and therefore exercises the real object pass. |
| Implementations | `jsComanche/dos-runtime.js`: `advanceAuthoritativeTick`, `prepareFlightFrame`, `drawDemo`. Falcon counterpart: `src/frame.s` and `src/main.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Grounded behavior:** render uses the frame-start viewer snapshot, enters `FUN_000234A4` with the selected mission's active slots, then consumes one replay record before cockpit/HUD composition. **Target artefact:** sound and physical VGA publication remain outside this slice. Browser canvas conversion occurs after the logical frame. |
| Fixtures and status | Ordered state/frame trace plus QEMU TCG execution/object-slot evidence. **Ported for the recorded attract path;** live keyboard input, sound, and menu handoff remain outside this browser fixture. |

## `object-pass`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_000068A5-00006947`, `FUN_00023297-000234A4`, `FUN_00023A8C`, `FUN_00023B50`, `FUN_00023CF0`, `FUN_00023F60`, `FUN_00023840`, `FUN_00024B17-00024C09`, `FUN_00024C45-000253CD`; QEMU TCG `exec,nochain` trace and active-object snapshots in `work/qemu_out/attract-trace-report.txt`, `work/qemu_out/object-state-2.txt`, and the confirmation snapshots. |
| Recovered function | Load the mission placement records — **nine** for the attract's first mission, `[0x19D64] = 9`, types `0,2,2,2,2,2,2,2,2` — resolve f2/f3 through the trailing ten mission SG-bank slots, allocate standard objects in slots 30 down, run each authored state handler in descending slot order, transform to viewer space, select-sort far-to-near, choose the HIGH.DTL ring/page, select the SG `3D` aspect frame, and draw the scaled masked sprite(s). The type-0 record is dispatch entry 0 at `00023462` and installs the fixed slot-31 object that `00007CC5`'s camera aims at and `00024C0A` draws in the external views. The type-4 state follows its separate viewer-seeking and terrain-clearance path; it is not an alias of `00023F60`. |
| Implementations | `jsComanche/dos-data.js`: named placement fields, mission `objectBanks`, and the six common transient banks; `jsComanche/dos-runtime.js`: mission factories, `00023A8C/00023B50/00023CF0/00023F60/00023840`, dynamic allocators, replay callback dispatch, `000234E0/000236D0/000237B0/000241C0/00024480/000244A0/00024680/00024860`, the `00022A00/00022AA0` BULL/CHAF factories, per-frame effect flags, collision/destruction transitions, bearing/aspect/projection, and model/effect drawing. Falcon counterpart: `src/object.s`, `src/mission.s`, and `src/sprite.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Grounded behavior:** `00024C45`'s aspect block is the same routine as `000256C8` with the other origin and direction — `00024C58`/`00024C71` take the live viewpoint minus the object — and carried the same four errors until it was re-transcribed: `00024C7D`/`00024C81`'s doubled octant index, `00024C85`'s `ja` skipping the increment when abs(dx) IS greater, `00024C9D`'s XOR into `bl` alone, and `00024C9B`'s unclamped quotient. The sprite's 8.8 scale and its fan column both divide by the RING's lateral increment `B[ring]` at `[00019EE4]`, not by the object's own depth: `00024D21` takes `2^27 / B` saturated at 127, and `00024D84`-`00024D9E` takes `v = lateral / (B >> 3) + 0x80` culled outside `[5, 0xF5)`, whose dividend is the lateral AS STORED in 12.20 — four shifts from 16.16, not seven, since `00024CC7`'s three belong to the ring search's key. A null return culls the caller's draw, as `00024E03` does by popping its caller's return address. `00024B17`'s walk tests only active and depth sign; the 992-unit range cull that stood here was invented, and the original's is `00024C45`'s `0x1FFFFFFF`, structural because `depth << 3` wraps at exactly 512. DOS bearing tables at flat `00022385/000223A5` carried in full — all 2048 correction bytes, of which `0..1023` is the arctan ramp and the rest is what `00025715`'s unclamped quotient reaches when the two magnitudes are within a map unit; `000256C8` transcribed at the instruction, with `000256F5`'s doubled octant index, `000256F9`'s increment on the comparison the `ja` does not take, `000256FF`'s `(minor >> 1) + major` distance, and `00025717`'s XOR into `bl` alone with the bits above it still reaching `0002571E`'s shift. This record previously described a reading that agreed with 0 of 153 captured DOS variant-7 frames; the current one reproduces 153/153. Exact aspect octant selection, the half-delta Q31 object transform, unsigned HIGH.DTL table-4 ring search in DOS depth units, byte-wide altitude rotation, the `0x1fffffff` depth gate, model-B pair bias, asymmetric `00023CF0` terrain probes, `00023F60` home-point restore, `00023840` distance gate and `+0x22` clearance, the 130-slot update order, the six common bank pointer assignments, the `[00019D68]` replay callback selector, the transient state addresses, the BULL/CHAF quotas/timers, and their altitude gates are retained. **Target artefact:** 16.16 object storage, normalized SG pixels, RGB565 words, and clipped Canvas writes replace DOS arrays, VGA plane operations, and the scaled column blitter. **2026-10-06, Falcon ahead of this reference:** `00023CF0`'s aim and fire (`00023E55-00023F23`), the shot routines `00022CA1/00022D33/00022DD0`, the shells `000234E0/000236D0` and the countermeasure chain `00019555-0001959E` / `00022A00` / `00022AA0` / `00024480` / `000244A0` are ported in `src/object.s` and checked against `work/replay_dos/objects-demo1.json`; `objectStateMobile` above still returns at the health and hold tests (DOS falls into the aim) and carries none of them - **Unproven** here. `000227D8` installs a BOOM wreckage pair rather than cloning its parent. See `docs/PORTING-PLAN.md`, "The mobile ground unit, the countermeasure chain and four blitter faults". **2026-10-07, two projection faults closed while carrying the targetability test (`#target-cycle`):** `objectFindPage` applied `00024C45`'s `0x1FFFFFFF` gate to the ring-search key (the transform's depth shifted left by three) instead of to `[00020A64]` itself, which dropped every object beyond 64 map units where the original draws to 512 (the rings end near 492); and `objectFanColumn` divided a quarter of the stored lateral (`lateral * 16`) by `B >> 3`, where `00024D84` divides the lateral as stored (`lateralDos`, 12.20) - on DEMO1 slot 26 at record 1 that gave column 129 against the original's 132 (`[00021BAB]` = 86). Both now read `[00020A64]`/`[0002085C]` as the original does. |
| Fixtures and status | `objectAspect` agrees with the certified `000256C8` block on 800/800 captured frames, and `objectFanColumn` reproduces `v` on 400/400 objects captured at `00024D9F` by `work/trace_replay_flight.py --fan`, which reads the registers so the quotient's own inputs are measured rather than inferred. Pass-one proof asserts the nine DEMO1 placement records and their `0,2,2,2,2,2,2,2,2` types, slot 31 with its `00023800`/`00024C0A` dispatch, TANK/TURR f2/f3 resolution on the first type-2 record, column-major bank layout, state `00023CF0`, draw `00024FED`, projection table, one-record frame order, and a DEMO1 callback allocation. The Falcon reports the same nine records and an active slot 31 at every certified VBL. QEMU confirms nonzero `000234A4`, `00024B17`, `00023CF0`, `00023F60`, `00023840`, `00024FED`, `0002514D`, and transient states `000234E0`, `000237B0`, `000241C0`, `00024480`, `000244A0`, `00024680`, and `00024860`. **Ported for the traced attract object/effect graph; live keyboard, sound, and non-attract menu paths remain outside this fixture.** |

## `view-basis`

The consolidated implementation and function record are under
[`view-select`](#view-select). The audit's `work/replay_dos/view-basis-recheck.json`
was captured at `00007D7F`; its DEMO1 selector timeline is retained in the proof
gate. The merged browser uses explicit raw DOS camera coordinates and the
published `flight.pubSin`/`pubCos` pair, rather than a second camera object that
mutates helicopter coordinates. The recovered shake generator and independent
clock remain under [`shake-timer`](#shake-timer); its target presentation
uncertainty is unchanged.

## `terrain-setup`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00007D25`, canonical range `00007D7F-0000AF4E` — the clamp, shake bias and horizon walk from `00007D7F` onward; `00007D25-00007D7F` is the basis build and is recorded separately under `view-basis`. Identical setup family at `000107A0`. Q31 table and horizon evidence are in `docs/X86-M68K-MAP.md`. |
| Recovered function | Build the 192-column backdrop displacement from the published slope/offset pair `[00019CF8]/[00019CFC]`, not from the roll and pitch accumulators: the two agree only while variant 1's identity handler is selected. |
| Implementations | `jsComanche/dos-runtime.js`: `buildBackdropDy`, and the basis read in `drawTerrain`/`renderClear`. Falcon counterpart: `src/render.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Grounded behavior:** `00007D93`/`00007D98` load the whole of `edx` with `0x21` and subtract `ah` from `dl` alone, so past `hi8 = 0x21` the limit wraps to `0xFF` and the clamp opens instead of closing. This carried `if (limit < 0) limit = 0` until it was closed, the same form `src/render.s` carried before it was closed there. **Unreached on this route:** across the 800 captured frames `abs(slope)` peaks at 133 and `(133 * 0x40) >> 8` is exactly `0x21`, so the limit bottoms out at 0 without crossing. **Target artefact:** a linear `Int16Array` and Canvas surface replace DOS self-modified span blocks, VGA row tables, and planar addresses. Signed shifts, Q31 table indices, 192 columns, and backdrop tilt are retained. Bounds checks exist only at the browser surface boundary. |
| Fixtures and status | `sine-q31.js`, `HIGH.DTL`, fixed camera horizon fixtures, and the 800-frame slope/offset capture. **Ported/adapted;** target hardware timing is unproven. |

## `terrain-renderer`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0000D950`, canonical range `0000D950-0000F317`; matching detail family at `000137F0` and `0001B26C`. |
| Recovered function | March 250 rings in ring-major order. Accumulate the ring centre, sample all 192 columns, use the `NOT(altitude)>>1` page byte (`127-floor(altitude/2)`), pack 10.22 map coordinates, compare strict `ja`, and emit `[old horizon,new top)` at screen row `213-page`. The basis is `[00019CB0]/[00019CB4]` as `00007D25` published it, and the centre is the live `[00019CD4]/[00019CD8]`, which the external handlers move — `00024B2E` and `00024C58` read them live for the same reason. Re-deriving either from the flight angle pins the march to the cockpit. |
| Implementations | `jsComanche/dos-runtime.js`: `buildRingPageTable`, `readMapIndex`, `AttractRuntime.drawTerrain`, `drawTerrainSample`, `drawTerrainSpan`. Falcon counterpart: `src/render.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Grounded behavior:** `00007AA0` transfers the rendered surface through a run list built from the loaded console image's transparency, and it spans exactly 168 rows — surface 46..213, screen 0..167 — at both captured variants: `consol1s` gives 261 shaped runs (row 0 `[0,1]`, row 84 `[1,80]`, row 167 `[18,47]`) and `consol5s` 168 full-width ones, one per row. Below it the original leaves its page standing, and the terrain never reaches there however the horizon is sheared; this clipped at `VIEW_H - 1` and drew into rows 168..239 where the original shows page art. The bound is `TERRAIN_TRANSFER_ROWS` and the proof gate asserts it by writing past it. Authoritative HIGH.DTL projection, full 192-column march, ring accumulation, strict occlusion, and map wrapping are retained. **Target artefact:** the run list's per-row horizontal shape is reproduced by the console overlay's own transparency rather than by walking the list, and its two passes through VGA plane masks `0x302`/`0xC02` have no counterpart — the same picture by a different mechanism. A 320×240 RGB565-equivalent linear surface crops source columns 16..175 (the displayed DOS window) at two pixels per source column; span and coordinate bounds prevent writes outside that surface. DOS's persistent render surface is represented by `terrainSurface`, seeded once at replay entry and copied back only before console/HUD composition. |
| Fixtures and status | HIGH.DTL projection preparation, Q31 table, map wrap, and fixed-camera framebuffer hash fixtures. The Falcon counterpart is certified against a cockpit capture at the same detail level by `tools/certify-marcher.py`: 20608/20608 columns exact over 184 scored rings with `max abs(e) 0`, `ring_page_table` 64000/64000, `ring_a_table` and `ring_b_table` 250/250, the height map identical and `backdrop_dy` 192/192. The capture must be view variant 1 — an external camera animates the look direction apart from the heading, so `[0x19D00] != [0x19D04]` and no `flt_angle` reproduces the basis; `work/dump_marcher_tables.py --cockpit` gates on it. **Ported/adapted for the browser surface;** exact DOS VGA page equality is not claimed. |

### Terrain coordinate correction (2026-09-08)

The connected browser showed tall green streaks because `drawTerrain` added
raw 10.22 DTL products to a 16.16 camera and `drawTerrainSample` then extracted
16.16 cells. The traversal fixture repeated that same mixed-scale start.
The DOS listing loads raw camera registers at `0000D974/0000D97A`, accumulates
signed high products at `0000D9A2-0000D9D7`, and packs their top ten bits at
`0000D9EE/0000D9F2`. The browser now uses `view_camera_dos_x/y` throughout the
march and that raw SHLD-equivalent cell lookup. Other consumers retain their
explicit 16.16 `readMapIndex` interface. Y subtracts the high product after
multiplication (`0000D9B1/0000D9B7`); negating the operand before multiplication
changes rounding and mishandles the signed minimum.

The corrected traversal fixture failed on the old first sample (ring 0,
column 95: X 33748017 versus 2144801172; Y -10698695 versus -617597846).
Map-lookup fixtures separately exercise cell edges and signed wrap. Run
`node tools/prove-browser-attract.js --dos-marcher work/qemu_out/marcher-6.json`
to additionally feed the production marcher the retained DOS camera, DTL
tables, projection pages and height map, and compare the non-uniform ring
horizons against the captured execution archive. On 2026-09-08 this passed
**16,800/16,800** scored columns across 150 non-uniform rings, matching the
independent `tools/compare-marcher.py` result on that retained fixture; the
ordinary browser proof gate also passed. The capture provenance and
rear-view overlap restriction are documented in `docs/DOS-ORACLE.md` and
`tools/compare-marcher.py`. This is a terrain horizon check, not complete-frame
or sequence certification. No m68k implementation changed.

Validation identities (SHA-256):

| Artifact | Hash |
|---|---|
| `jsComanche/dos-runtime.js` | `978e7859afbb9e6162a689e7c80d7faa74e2e3d31d152caceaf2e2655eccee65` |
| `work/qemu_out/marcher-6.json` | `7c5d0bd95daaee412acf20037b42f5a6b51bea38f9b74a9b107f06845cd21e47` |
| `pages-6.bin` | `637d3b5e48a7d108c36bfe419a1c3e8b410319535df2d3dd9f4c22de439499b0` |
| `heightmap-6.bin` | `cf4af1f71091d6063473c2eb73148e4851b9f8bbffdf4435d251d3a216a42e80` |
| `silhouettes-6.bin` | `3c8c33a46d5bf68df96615ececa7ba23d562f501bde986fa80f70f6857e783bf` |

The connected browser was visually checked in the demo flight: the vertical
streaks were replaced by terrain contours, both cockpit MFD bodies show live
terrain, the first impact no longer freezes the target, and DEMO1 returns to
cockpit view at its later selector. The runtime script URL was bumped to
`attract=7` so an already-open page fetches the corrected source instead of
reusing its cached script. Full VGA shake and target-model frame parity remain
separate Unproven presentation gates.

## `palette-remap`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0002B820` / `FUN_0002B949`, canonical range `0002B820-0002B9BA`; palette observations in `docs/X86-M68K-MAP.md`. |
| Recovered function | Preserve indices 0 and 255, search target indices 1..254 in order, use the gamma-weighted six-bit RGB metric (30/55/15), and keep the first minimum. Mission kind 1 applies the recovered night palette transform before the remap. |
| Implementations | `jsComanche/dos-runtime.js`: `nearestPaletteMap`, `missionColourPalette`, `remapColourMap`, `buildPaletteLookup`. Falcon counterpart: `src/resources.s` and `src/sprite.s`; CPU-only palette boundary. |
| Difference ledger | **Target artefact:** RGB565 words replace VGA DAC writes after the same six-bit palette selection. No alternate metric, candidate order, or behavior flag exists. |
| Fixtures and status | Active palette, C/D map, SG-bank and night-kind fixtures. **Ported/adapted.** |

## `sprite-and-console-composition`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00025880`, canonical range `00025880-00025DBC`, plus the recovered console/HUD call sites. |
| Recovered function | Decode planar-bottom-first CONS/COMA/ZOVE records and column-major bottom-first HUDS and mission-object records; apply DOS bottom-origin coordinates, opaque/masked semantics, console transparency index 255, and the recovered draw order. |
| Implementations | `jsComanche/dos-runtime.js`: `decodePlanarFrame`, `decodeColumnFrame`, `drawOpaqueSprite`, `drawMaskedSprite`, `drawScaledMaskedSprite`, `drawConsole`, `drawFixedInstruments`, `drawHeadingWindow`. `jsComanche/dos-data.js`: per-bank pixel-layout classification. Falcon counterpart: `src/sprite.s`, `src/hud.s`, and `src/console.s`; CPU-only RGB565 surface adaptation. |
| Difference ledger | **Target artefact:** decoded linear pixel lookups and clipped writes replace DOS plane/register operations. The clip is a browser memory boundary only; valid in-surface pixel order and transparency are retained. |
| Fixtures and status | CONSOL1S, CONS, COMA, ZOVE, and HUDS decoded assets; the browser proof now requires the active scaled sprite pass to change framebuffer pixels over a replay window, not merely construct object records. **Ported/adapted for the connected attract screens and cockpit.** |

## `mfd-map`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00007580`, canonical range `00007580-00007666`, with the map marcher at `00015855-00015AD8`; source coordinates and 80x44 extent are recovered in `src/hud.s`. |
| Recovered function | Form the Q31 heading basis at the captured zoom `0x08000000`, offset the raw 10.22 flight position, sample the authored colour map on the rotated 80x44 grid, then place the own-ship and active-object markers. |
| Implementations | `jsComanche/dos-runtime.js`: `drawMfdMap`, `drawMfdMarkers`, `drawMfdStage`. Falcon counterpart: `src/hud.s:mfd_draw_map` and `mfd_draw_markers`; CPU-only RGB565 surface adaptation. |
| Difference ledger | **Grounded behavior:** raw coordinate arithmetic, map addressing, panel geometry, marker indices and blink cadence are retained. **Target artefact:** four DOS plane passes become one chunky RGB565 pass; the browser may reuse this authored map in the right panel until its target-view marcher has a visible span. |
| Fixtures and status | MFD interior-pixel proof in `tools/prove-browser-attract.js`. **Ported/adapted for the connected cockpit.** |

## `mfd-target-view`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00007860`, canonical range `00007860-000079E3`, calling `FUN_0001B26C`, canonical range `0001B26C-0001B34F`; target camera, range anchor and 80x44 window are recovered in `src/object.s` and `src/render.s`. |
| Recovered function | Substitute the selected target's camera, use its recovered view bearing and altitude, fill the sky (`0001B29C` calls `[00019C9C]` = `0001C920` before the first ring: forty column pairs from the right, each the next-but-one of the sky bank's 512 strips of 150 bytes from `((~[00019D00] - 0x14000000) >> 23)`, strip bytes 90-149 stored down from page row `0xA5`, wrapping modulo 512 strips; `000079F0` reads page row `162 - 2r` for panel row r, so panel row r takes strip byte `93 + 2r`, rows 0-28), march the second 80-column terrain view with the three-ring cursor advance and strict horizon test over it, and draw the HUDS `RANGE` readout in the right panel. |
| Implementations | `jsComanche/dos-runtime.js`: `drawMfdTargetView`, `drawMfdTargetTerrain`, `drawMfdTargetSky` (`FUN_0001C920`, `0001C920-0001CAC0`). Falcon counterpart: `src/object.s:mfd_draw_target_view`, `src/render.s:mfd_march_target_view` and `mfd_target_sky`. |
| Difference ledger | **Grounded behavior:** target-camera arithmetic, 10.22 map samples, paired columns, panel row conversion and range placement are retained. **Target artefact:** the browser keeps the right body populated with the authored moving map before replay target state is available or when the target marcher emits no visible span; the target model/object pass is not yet composed into this browser panel. **2026-10-07:** the sky is transcribed from `0001C920` and written before the terrain, both pixels of a pair alike. The listing's loop stores one byte per row at page column `dl = 0x2C + pair`; how the pair's second pixel (`000079F0` reads column `0xAC + pair` for it) gets its value was not resolved from the listing. What supports writing both is the data: in `work/mfd_out/surface-5.bin` (the page buffer at `0000790E`, after the target march) columns `c` and `c + 0x80` are equal on every row from 100 to 165, and the panel rows of `build/acceptance/frames/dos-demo1-r20.pcx` are pairwise equal where terrain or sky fills them. None of the four captured panels (r10, r19, r20, r21) shows a sky pixel - index 255, the SKY4 viewport fill, does not occur in any of them - so the strip choice is checked against the listing and the Falcon's `mfd_target_sky` only (**Unproven** against a DOS frame). The sky counts as painted, so the moving-map fallback above can no longer replace a panel the original would show as sky. The flat viewport fill `0001CAD0` (sky option off) is not carried: the shipped settings turn the sky on. |
| Fixtures and status | MFD interior-pixel proof plus the existing target-view marcher fixtures. **Ported/adapted for connected replay;** complete DOS target-model frame parity remains Unproven. |

## `demo-replay`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00018C29` / `FUN_00019A2D`, canonical replay load/feed ranges documented in `docs/X86-M68K-MAP.md`. |
| Recovered function | Read the 13-byte header, then fixed 8-byte records: key, collective, trigger bytes, and signed axes. Feed one record after each drawn replay frame; the stream has no invented terminator. Pass-to-file mapping is `DEMO0..DEMO3`; header and velocity positions remain DOS 10.22 until the browser's explicit 16.16 surface conversion. |
| Implementations | `jsComanche/dos-data.js`: `parseDemo`; `jsComanche/dos-runtime.js`: `enterDemo`, `advanceDemoInput`, `applyReplayKey`. Falcon counterpart: `src/demo.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Grounded behavior:** each record's key byte is dispatched, not just `1A`/`1B` and `27`/`28`. Keys `0x02..0x09` reach `00019689`'s view cases — see `view-basis` — and were dropped here until they were carried, which drew every frame of the attract from the cockpit. **Target artefact:** validated imported bytes are held in a `Map`; no live keyboard path is attached. Replay records, widths, signedness, cursor order, and draw-before-consume sequencing are retained. |
| Fixtures and status | All four supplied DEMO streams and the ordered replay trace. The proof gate asserts DEMO1's view-key timeline `30:6 206:7 357:1` against `work/replay_dos/view-basis-recheck.json`. **Ported for attract replay;** live input remains `Unproven` and absent. |

## `flight-integration`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00018F94`, canonical range `00018F94-0001959E`; altitude/angle and replay observations in `docs/PORTING-PLAN.md` and `docs/X86-M68K-MAP.md`. |
| Recovered function | Apply the DOS damping, signed axis increments and clamps, terrain collision/clearance response, altitude averaging, 32-bit angle wrap, and Q31 movement in the recovered order. Altitude is the byte state; the angle is the full dword state; DOS 10.22 position products are shifted six bits at the browser 16.16 boundary. `0001950F`/`0001951B` publish the heading's sin/cos pair to `[00019CB8]/[00019CBC]`; variant 7's camera placement steps back along that published pair rather than re-deriving it, which against the capture disagrees on 2 of 800 frames because the basis build runs a tick later. |
| Implementations | `jsComanche/dos-runtime.js`: `damp`, `clamp`, `AttractRuntime.flightTick`. Falcon counterpart: `src/flight.s` and `src/game.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Grounded behavior:** replay keys `1A/1B` and the direct `27/28` effect paths, OR-accumulated trigger bytes, one-per-frame consumption, target selection, callback dispatch, and the post-flight BULL/CHAF effect gates are retained for the attract stream. **Target artefact:** JavaScript signed arithmetic and the shared Q31 table replace x86 instructions and DOS memory. Live keyboard input is not attached to a host (`keyEvent` is the seam), but the flight handler reads the key arrays where the original does: `weaponDispatch`, `targetCycle` and `rudderAndLockLoss` sit between the control clamps (`000191B6`) and the terrain follow, exactly where `000191B6-000192EE` are, so a weapon leaves from the previous tick's position, heading, altitude and this tick's pitch; the rudder keys KP0/KP. (`[00001AC2]`/`[00001AC3]`, `000192A9-000192C5`) step the turn rate by 0x400000 a tick without a new clamp. The fuel branch `00018E10-00018E49` is `applyFuelState` (`#fuel-exhausted`). **Damage, 2026-10-07:** `flightTick` now enters the death block `00018EE3-00018F93`, the damaged-engine cap and T gauge `00018F94-00019002`, the tail-rotor yaw `000190AB-000190B4` and, for ground contact, the crash response `00019424-000194DB` through `dos-damage.js` (`#player-damage-chain`); the object collision test `000192EE-0001934F` is transcribed there but not entered. |
| Fixtures and status | DEMO header/record state traces, callback-table state allocation, and fixed terrain samples. **Ported for the recorded attract inputs;** live keyboard/control paths remain outside this fixture. |

## `cockpit-hud`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0000D703`, canonical range `0000D703-0000D887`; fixed elements at `00007403`, `00007443`, `000077BE`; digit tail `0000D8F5-0000D950`. |
| Recovered function | Draw the fixed console, authored compass, speed and clearance indicators, ladder, reticle and dynamic sight line in the recovered order. The shipped attract configuration reaches the authored HUD family; the phase-gated COMA tail is not entered. |
| Implementations | `jsComanche/dos-runtime.js`: `drawHudAuthored`, `drawHudValue`, `drawDynamicHud`, `hudClearance`, `drawConsole`, `drawFixedInstruments`. Falcon counterpart: `src/hud.s`, `src/console.s`, and `src/sprite.s`; CPU-only RGB565 surface adaptation. |
| Difference ledger | **Grounded behavior:** no build-selectable HUD flags; the recovered shipped path runs directly. **Target artefact:** RGB565 words and clipped Canvas writes replace the DOS VGA page. |
| Fixtures and status | HUDS/CONS/CONSOL1S assets and sight-line frame hashes. **Ported/adapted for attract phase 1.** |

## `sight-line`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00025CA2`, canonical range `00025CA2-00025D31`; integer shallow/steep walk and green word `0x47E8` recovered in `docs/X86-M68K-MAP.md`. |
| Recovered function | Draw the inclusive endpoint line from the fixed reticle centre to the velocity target using the `+1` denominator, the DOS `+0x100` quotient bias, and the eight-bit `BH:BL` fractional walk seeded at `0x80`. |
| Implementations | `jsComanche/dos-runtime.js`: `drawSightLine`, `plotSightPixel`. Falcon counterpart: `src/hud.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Target artefact:** out-of-surface writes are clipped instead of wrapping through DOS VGA memory. In-surface arithmetic and colour are unchanged. |
| Fixtures and status | Zero-length, shallow, steep, and fixed HUD target fixtures. **Ported/adapted.** |

## `fixture-scheduler`

| Field | Record |
|---|---|
| DOS identity and evidence | N/A - platform replacement for presentation scheduling; DOS cadence is the open timing question cited by `FUN_00005690`/`FUN_0000D3C0`. |
| Recovered function | None. A browser-only scheduler presents a deterministic logical tick stream for fixture inspection. |
| Implementations | `jsComanche/dos-runtime.js`: `FixtureScheduler`. Falcon counterpart: `src/vbl.s` and `src/main.s`; Falcon cadence remains a separate timing gate. |
| Difference ledger | **Target artefact / Unproven:** 60 Hz is a labelled fixture upper bound and RAF is presentation only. Each presented frame admits at most one logical tick; the scheduler does not catch up by integrating multiple replay records in one frame. This preserves the DOS one-frame/one-integration order without claiming a DOS timer or VBL rate. The connected page has no pause/restart controls. |
| Fixtures and status | `advanceTicks(count)` for deterministic tests. **Diagnostic-only; not a DOS counterpart.** |

## `weapon-fire`

| Field | Record |
|---|---|
| DOS identity and evidence | Dispatch `000191B6`–`0001922E` inside the flight handler `FUN_00018F94`; handler table `[00019D68]` (image) = `00022890`, `00022B00`, `00022F90`, `00022E70`, `000231B2`, `000230B0`, indexed by page `[00019D88]`. Rocket launcher `FUN_00022B00` (`00022B00`–`00022CA0`), Hellfire launcher `00022F90`–`000230AD`, rocket state `000241C0`–`0002430D`, Hellfire state `00024680`–`0002485E`, frame-indexed draw `0002519D`–`0002528B`, shared bank loads `000066E2`–`000067AE` (in 353 bytes the static listing did not decode; read from the image around each inline name), bearing `FUN_000256C8` (its `esi` distance estimate). Evidence: `work/trace_weapon_fire.py` stops at `0001922E` and `00019230` in the shipped executable under QEMU and records every shot of DEMO1's supported first 284 records (`work/replay_dos/weapon-demo1.json`, 35 shots). |
| Recovered contract | One pending trigger `[00019DF2]` per tick; page 0 discards it; otherwise decrement, set `[00019D81]` (the sight element flag) and call the page's launcher. Launchers: ammunition test (rocket also `[00019E3B]` = damage entry 3, 2 at runtime against the image's 10), slot scan 130→31, fields as transcribed in `src/object.s`, alternating rail `[00022880]` = ±0x1800000 (image data, only ever negated), launch point from `[00019CD4]`/`[00019CD8]` and the published `[00019CB8]`/`[00019CBC]`. Rocket: heading rounded (+0x800000), 8.24 altitude, rate = −pitch<<22 or, with a lock, ((alt_t − alt)<<23)/n + 0x1800000 with n = ((∣lat∣>>1 + depth)<<2)/speed. States: prev latch, move (the `000248E4` mover), rocket gravity 0x100000/tick with carry exits, Hellfire timer/steer (≤0x14, nine-bit halved difference)/climb/descent law, ground test 2h+1, proximity test over slots 30..1 (halved nine-bit altitude ≤15, ∣dx∣,∣dy∣ ≤ 0x1400000), damage 6 (5 unless `[00019DB8]`&0xC0) or 0x50 to `[00021F93]`, borrow sets `[00021B29]` bit 0, then `00024997`, which now binds BOOM and `0002519D`. |
| Implementations | m68k: `src/object.s` `weapon_dispatch`, `weapon_fire_rocket`, `weapon_fire_hellfire`, `weapon_launch_position`, `weapon_slot_scan`, `object_state_rocket`, `object_state_hellfire`, `weapon_hit_scan`, `weapon_ground_hit`, `weapon_banks_load`, `object_draw_frame`/`object_frame_project`, `object_transition_home`; `src/view.s` `view_bearing_point`; hook in `src/flight.s` `flight_tick`. JavaScript: `weaponDispatch` (`000191B6-0001922E`, all six pages, live keys and pending count), `fireCannon` (`00022890`), `objectStateBullet` and `objectBulletBurst` (`000244E0`), `keyEvent` (the ISR's array stores `00001B91-00001BA0`); `spawnWeaponObject`, `objectStateTimedProjectile`, `objectStateGuided` remain the earlier loose model for pages 1-5 and are **not** ports of those launchers (see ledger). |
| Fixtures | `python3 tools/check-weapon-launch.py work/replay_dos/weapon-demo1.json` runs the port under Hatari, dumps the object table before and after every dispatch with a trigger pending, and compares each launch with the DOS row at the same replay cursor. 2026-09-22: **35/35 launches exact** in every compared field (X/Y as 10.22>>6, heading, altitude, speed, aux, rocket 8.24 altitude and vertical rate including the lead, Hellfire target and timer, rocket and Hellfire counts, rail parity). **Cannon, 2026-10-07:** `work/replay_dos/objects-gun-dos.json` is the DOS object table traced while Space was held on console page 0 at replay cursors 101-124 of DEMO1 (`work/trace_replay_flight.py --objects --records 45 --poke-from 101 --poke-to 125`, the same poke `tools/trace-falcon-objects.py --poke-from` replays on the Falcon), with a lock on slot 26 so the rounds take the target's view bearing and the lead rate. `node tools/check-js-objects.js --gun` applies the same poke to the JavaScript at the same instant (after the object pass, before the tick's dispatch) and compares slots 127-129 on active, x, y, heading, altitude, sprite and speed (plus previous position and altitude, aux, state, draw, phase, timer, steer) and the lock, candidate, console page and pending trigger counts, over all 45 frames: **every field agrees** (three rounds, 10 frames each from launch through burst; `f9`, `health`, `hold` and `variant` above slot 30 alias neighbouring DOS arrays and are ignored). |
| Difference ledger | **Sound:** `00004E8E` launch sounds not carried (sound phase). **Live keys, 2026-10-07:** both the Falcon (`weapon_dispatch`, `key_state`/`key_latch`) and the JavaScript (`weaponDispatch`, `keyState`/`keyLatch`) carry the dispatch's key half: page 0 fires while Space `[00001AA9]` or KP5 `[00001ABC]` reads non-negative (or the game-port word `[00019DEC]` bit 0, which the keyboard device never sets), any other page fires on a make latch `[00001B29]`/`[00001B3C]` without spending a pending count, the latches clear on a fire, and `[00019D81]` is the sight flag. The held-Space half is checked by the cannon fixture above; the make-latch half and the KP5/Return paths are **Unproven** against a keyboard-driven DOS run (the attract holds every key released). **Pages:** `00022890` (the cannon) is ported in both and checked; `00022E70`, `000231B2`, `000230B0` are ported in `src/object.s` and **Unproven** in the JavaScript, which still routes pages 1-5 to the earlier loose launch model (now called from the dispatch's own position, before the tick's move, with the previous tick's altitude and angle, as the original does). The cannon's two unported effects are the count redraw (`[00019D89]`, `000073D0`) and the firing sound (`00004E8E`). **Positions:** objects are 16.16 (10.22>>6), as `object_move` records; the proximity and mover arithmetic inherit that. **Damage RNG:** `[00019DB8]` is the PIT PRNG, whose phase is Unproven (`#shake-timer`). **Slot numbers:** 22 of 35 launches claim a different slot than DOS. DOS index 130 is one past every 130-entry array, so its "active" byte is `[000219A3]` (slot 0's sprite byte). In DOS, a BULL flare launched at cursor 21 by the countermeasure tail holds it until cursor 253 (write watchpoint: `00022A69` sets, `000244D5` clears). The port has no countermeasures: `000077A0`'s threat scan sets `[00019D93]` for any active slot 31..130 with a non-zero aux byte in radar range, and `00019555`–`0001959E` then launches BULL (`00022A00`) or, on `[00019D92]` from `00023EA7`, CHAF (`00022AA0`), with states `00024480`/`000244A0`. None of that chain is ported. Missile lifetimes also decide slot reuse and are **not yet traced per tick** against DOS. **JavaScript:** the cannon (`00022890`/`000244E0`) is transcribed from the listing - the 8.24 altitude and its rate, the two-round step with its floor, the damage-cell and empty exits, the lock's bearing and lead - and the other pages' launch and states are the earlier model (flight angle instead of the published pair, no rail, no ammunition, no 8.24 ballistics, fixed ±3/±8 altitude steps) and are **Unproven**; they must be rewritten from this record before the browser can claim those functions. |

## `target-cycle`

| Field | Record |
|---|---|
| DOS identity and evidence | Target cycle `FUN_00018F94` inside `00019230-000192A3`; lock-loss `000192CF-000192E4`; rudder `000192A9-000192C5`; frame-driver validation `FUN_0000D3C0` `0000D418-0000D47F`; per-object bookkeeping `FUN_00024B17` `00024B81-00024C09` and the targetability tail `FUN_00024C45` `00024DA4-00024E02`; console-select clear `000196B4-000196BE`; per-ring horizon archive `0000F2DE-0000F2FF`. |
| Recovered function | `[00019D10]` is the target latch (0 = none) and `[00019D18]` the candidate the last object to pass `00024DA4` leaves. Each tick `00019230` takes a make latch of Tab `[00001AFF]` or Return `[00001B0C]`, or else consumes one pending count `[00019DF3]`; a negative targeting cell `[00019E3A]` (damage array entry 2) or a console variant past 5 (`[00019D86]`) gates it and leaves the latches; otherwise it clears the latches and either seeds an empty latch from `[00019D18]` or walks `latch + 1 .. 0x1E` (wrapping to 1) to the first object whose `[00021BAB]` is set, falling back to the object it started from. `000192CF`: with the targeting cell `[00019E3C]` negative, the lock drops whenever `[00019DB8] & 0x1C` is zero. After the tick `0000D418` latches the locked object's depth `[00020A64]` into `[00019D14]` and clears the lock when `[00021BAB]` is zero. Every draw pass `00024BD0`/`00024BE1` clears `[00019D18]` and every `[00021BAB]`, and each drawn object that reaches `00024C45` stores its view bearing `[00021CAF]` (the `000256C8` routine with the live viewpoint minus the object) and, for slots up to 0x1E, passes `00024DA4`: designator `~(backdrop[v - 0x20] + page) - 0x29` in `[0, 0xC8)`, `v - 0x2E` in `(3, 0xA0]`, and the object's page row not below the clip ring's archived horizon byte at column `v - 0x20`; then `[00021BAB] = v - 0x2E` and `[00019D18]` = the slot, the nearest drawn target winning. Every console select (all seven cases of `00019689`, including the two external-camera keys) clears the latch and the threat blip (`000196B4`-`000196BE`); `000196CF`'s `0001687D` also zeroes the wreck's screen drop `[00019DC4]`. |
| Implementations | `jsComanche/dos-runtime.js`: `targetCycle`, `rudderAndLockLoss`, `validateTargetLatch`, `objectProjectionPass`, `objectProjectionEffects`, `objectMarkTargetable`, the `ringHorizon` archive in `drawTerrain`, the latch clear in `applyViewKey`, and `targetSlot`, which is now a view of the latch (31 for none). Falcon counterpart: `src/object.s` `object_target_cycle`, `object_target_validate`, `object_mark_targetable`. |
| Difference ledger | **Grounded behavior:** all of the above, at the listing's addresses. **Not carried:** the designator box stores (`0000D421-0000D428`, `0000D460-0000D478`) that feed the HUD marker; `00024DB0` reads `[v + 0003CB20]` for `v` outside `0x20..0xDF`, a neighbouring BSS byte, so a `v` outside the array is rejected without reading it (exact, because `00024DD1-00024DDB` needs `v` in `0x32..0xCE`; only the unobservable `[00021C2D]` store differs); `00007860`'s second object pass for the target MFD re-runs `00024B17` with the target's camera and overwrites `[00021BAB]`/`[00019D18]` after the tick, which the next frame's state handlers (`00023E78`) and the oracle rows see - the JavaScript has no target-view object pass, so `check-js-objects.js` rows carry that pass's values (82 against the browser's 80-56 for slot 26 while locked) unless `--inject-target` supplies them. The older loose selector (slot order over mission objects) is gone; the replay's trigger-2 byte now walks the real targetability bytes. **Difference from the Falcon source:** `object_mark_targetable` rejects `v < 0x20` (`bmi`) and `v >= 0xE0` with a guard the listing lacks; the result is the same for the reason above. `weapon_fire_gun` tests `weapon_bank_bull` for null (`tst.l`, `beq .out`) before the slot scan, which `00022890` does not do. |
| Fixtures and status | `node tools/check-js-objects.js --gun`: the lock, candidate, page and pending counts agree with `work/replay_dos/objects-gun-dos.json` on all 45 frames (the lock is taken at record 7 from the candidate, held through the cannon's rounds, and dropped by the console select at record 30). `--pass 1`: `[00021BAB]` agrees on 93.2 % of mission slot-frames (84.7 % before; the rest is the second object pass). **Ported for the attract's keyless path;** the Tab/Return latches and the damage-gated paths are **Unproven** against a keyboard-driven or damaged DOS run. |

## `fuel-exhausted`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00018D20` `00018E10-00018E49`; `[00019D60]` loaded from `[00019D5C]` at `0000686C-00006871`; collective saved to `[00019D83]` at `00018D20-00018D25`; abort chain `0002873D`; engine-out voice `0001899A`. |
| Recovered function | The tank `[00019D60]` (the mission's fifth numeric line, 5000 on DEMO1) loses one a tick (`00018E49`, `dec dword`). While it is negative the pilot has no collective: the collective is last tick's `[00019D83]` less one while non-zero (`00018E29-00018E3C`; reaching zero calls `0001899A`, a sound request), and at exactly `0xFFFFFEF2` (-270) `00018E23` jumps to `0002873D`, which tears the mission down. |
| Implementations | `jsComanche/dos-runtime.js`: `applyFuelState` (called after the record's fields are applied and before `flightTick`), `flight.fuel`, `flight.collectivePrev`, `flight.missionEnd`. Falcon counterpart: `src/flight.s` `flight_tick` head. |
| Difference ledger | **Not carried:** the engine-out voice and the runtime's hand-off to `0002873D`'s chain. The chain itself (statistics, pilot record, ranking, the route to the attract driver, the menu or the debrief) is now transcribed as pure functions in `#mission-end-statistics`, `#mission-end-route` and `#roster-ranking`; `applyFuelState` still only records the request in `flight.missionEnd` and every later tick stops (a guard the original lacks only because it never returns). The tank is 5000 ticks deep, so no attract pass reaches it. |
| Fixtures and status | None captured: the branch is **Unproven** against DOS. |

## `mission-end-statistics`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00028261`, canonical range `00028261-000284B0`, with the percentage writer `FUN_000286F9` (`000286F9-0002873C`) and the number formatter `FUN_00028C25` (`00028C25-00028C3D`). Callers `000056BA` (the attract driver) and `00028772` (`0002873D`). The text it patches is the 584-byte image at flat `000284B1-000286F8`: seven 0x2F-byte sentences (success `000284B1`, aborted `000284E0`, rubble `0002850F`, defeat `0002853E`, no wingman `0002856D`, out of fuel `0002859C`, setback `000285CB`), the score screen at `000285FA` and the live sentence slot `000286A1`. Same hashed DOS image as the top of this file. |
| Recovered function | A negative tank is zero (`00028268`); the hull counters `[00019E40]`/`[00019E44]` step up by one and the first is held non-negative (`00028274-00028289`). Over slots 0x1E down to 1 (`000282B5`, `loop`): an active object whose aux byte `[00021DB3+n]` is not 3, 6 or 9 is an enemy left (`[00028250]`); each goal object (`[00021F39+n]`, the mission file's `*`) adds one to the goal total `[0002824D]` and, when no longer active, one to `[0002824C]` and 100 to the score. All goals destroyed (`[0002824E]`, a `sete`, true for zero goals too) adds 1500. The percentages follow in this order, each adding to the score `[00028258]` and leaving itself in `[0002825C]`: goals, hull (then sixteen times it again, `00028362`), enemy targets killed (`[00028254]` = target byte `[00028260]` minus enemies left, then 32 each), weapons (the first load counted shifted down 7, the second 3, the other four whole), fuel. The sentence: rubble when a goal fell; aborted when the hull stands, out of fuel when the tank is also empty; success when every goal fell, less 1000 (clamped at zero) and the wingman's sentence when `[00022384]` says the wingman was lost; defeat when the hull is gone, which also zeroes the score. The sentence is copied to `000286A1` (`rep movsb`, 0x2F) and the score is formatted as eight digits at `0002860B` over a `0xFC` fill. A percentage is `100 * count` in the low dword divided by the total (or 100 for a zero total), and only the low byte reaches the digit fields: `0xFD 0xFD digit`, then tens, then hundreds. |
| Implementations | `jsComanche/dos-pilot.js`: `missionStatistics`, `percentField`, `formatNumber` (and the data module `jsComanche/dos-text-data.js`, `#menu-text-data`). Falcon counterpart: `src/debrief.s` `mission_stats`, `debrief_percent`, `debrief_number`. |
| Difference ledger | **Grounded behavior:** every comparison, the order the sentence is overridden in, the byte-wide digit extraction (`000286F9` clears `ah`, not `eax`), the unsigned 32-bit products and the zero-total 100 are as listed. The routine returns a patched copy of the image instead of patching in place; every field is rewritten whole (the percent fields' two `0xFD` and digit, the score's eight bytes, the sentence's 0x2F), so the result is the same bytes. The sentence's `esi` is never uninitialised in the original: a standing hull sets the aborted sentence at `00028425` and a lost one the defeat sentence at `00028473`. **Not carried:** nothing audible or visible. **Falcon, no disagreement found:** `mission_stats` carries the same counts and order; `mission_target_count` is a word where `[00028260]` is a byte and `00029256`/`000292CC` add to it as a byte, which differs only past 255 targets. |
| Fixtures and status | **Checked against DOS execution.** `work/dos_call.py` points the running original's EIP at `00028261`, `000286F9` and `00028C25` with chosen memory and registers and reads the result at their `ret` (`node tools/check-js-dos-calls.js`, also run by the proof gate; the fixtures `work/replay_dos/dos-call-*.json` are derived and gitignored and the check reports SKIP when absent): 80 random mission situations (goal totals and kills, hull gone or standing, empty and negative tanks, wingman lost, six weapon loads, every sentence the routine can end with) agree with `missionStatistics` on the whole 584-byte screen image, every counter `[0002824C-0002825C]`, the clamped fuel and the stepped hull counters; 60 number-format cases (values to 0xFFFFFFFF, widths 1-10, short and long) and 80 percentage cases (zero totals, counts past the total, 32-bit products) agree byte for byte. Four DOS captures taken at instruction `00028777` (`work/trace_mission_end.py` at replay cursors 213 and 2405, `work/trace_mission_live.py` at a live abort and a live win) also agree from the mission's own records: the patched score screen, `[00028250]`, `[00028254]`, `[00028258]` and `[0002825C]` (scores 1895, 1913, 1896 and 7028); their object table is rebuilt from the mission file (aux from the second field, `*` for goals, enemies are the records whose second field is 2 or 3, which reproduces the captured `[00028260]` of 8 and 26). The rubble sentence of `0002850F` is never the one shown - a standing hull always overrides it with the aborted sentence and a lost one with the defeat sentence - and both machines agree. **Ported and checked against DOS.** |

### Native debrief numeric contracts (2026-10-10)

The `mission-end-statistics` formatters now have native execution evidence
for both declared CPUs. `00028C2D` clears EDX before dividing EDX:EAX by ten;
the 32-bit dividend therefore suffices. `debrief_number` previously used
`divu.l d3,d2:d0`, selecting the unsupported 64-bit dividend form on MC68060.
It now uses `divul.l`, retaining the unsigned quotient and remainder exactly.
The percentage writer already uses the 32-bit quotient form and preserves
DOS's low-32-bit product (`00028704-00028708`) and low-byte digit extraction.

Fresh captures from the hashed original:

```
python3 work/dos_call.py format-number --count 80 --out work/replay_dos/dos-call-format-number.json
python3 work/dos_call.py percent --count 80 --out work/replay_dos/dos-call-percent.json
node tools/check-js-dos-calls.js --routine format-number
node tools/check-js-dos-calls.js --routine percent
python3 tools/check-falcon-debrief.py
```

All 80 number cases and 80 percentage cases match in JavaScript, MC68030 and
MC68060. Native comparison covers every byte of the output buffer, including
untouched margins, plus the percentage's wrapped score and full last value.
Number inputs include zero, decimal transitions, 16/32-bit boundaries and
`0xFFFFFFFF`, at widths 1..10; percentage inputs include zero totals and
wrapped products. The harness extracts the production bodies verbatim and
archives commands, logs and source/fixture/program/output hashes under
`build/check-debrief-{68030,68060}/`. A pre-change source captured with
`cp src/debrief.s build/debrief-before-number.s` before the correction fails
`--cpu 68060 --source build/debrief-before-number.s` by never reaching the
test exit; the corrected body reaches it and compares exactly. This is
function evidence, not proof of the complete debrief UI or mission route.

## `mission-end-route`

| Field | Record |
|---|---|
| DOS identity and evidence | `loc_0002873D` (entered from `000189F2` Alt+A, `00018E23` fuel, `00018EF6` wreck and `00026E09` the options menu), range `0002873D-00028A1F`: the pilot record paths `000287E2-000288E8` (not won) and `000288ED-000289CF` (won), then the roster write `00015D40` and the debrief `00028A1F`. Live captures `work/replay_dos/mission-live-abort300.json` and `mission-live-win300.json` hold the roster before and after. |
| Recovered function | The shake phase, countdown and screen drop `[00019DBC]`, `[00019DC0]`, `[00019DC4]` go to zero (`0002874D-00028761`); the statistics run (`00028772`); `000227A6` zeroes the 130 active bytes from `00021922`, `[00022368]` and `[00022384]`; the designator box `[00019D1C..28]` goes to zero (`00028795-000287A6`). `[00019ED4] == 1` (the attract cycle) leaves for `00005690`; no flight under way (`[00019D91] == 0`) for the menu `00005AE3`; otherwise `[00019D91]` clears and a standing hull with every goal destroyed (`00028810`-`000287DC`) takes the won path, anything else the not-won path. **Not won** (`000287E2`): a standing hull (an abort or an empty tank) only has its kills added (`[0002979C + 4 * pilot]`, `0002887B-00028887`); a lost hull on a campaign not yet completed (`[00029ADC + 10 * pilot + digit] != 1`) walks the mission chosen last and the one before: where the mission is gated (`[00029F18+mission]`) and its won flag (`[000297BC + 100 * pilot + 10 * digit + mission]`) is set, the flag clears and the setback sentence replaces the debrief's. **Won** (`000288ED`): the campaign's progress byte `[0002970A + 10 * pilot + digit]` (not `[0002975A]`) names the mission; its won flag is set and the pilot's won count steps; a mission with a promotion byte (`[00029F2C+mission]`) completes the campaign and stamps the byte into the first record byte among 32..41 that is blank (`0xFC`) or equal; then score and kills are added. Both paths end in the ranking sort (`00029F36`, `[00027DAA] = [00029701]`), the file write and the debrief. |
| Implementations | `jsComanche/dos-pilot.js`: `missionEnd`, `pilotRecordWon`, `pilotRecordLost`, `pilotCampaign`. Falcon counterpart: `src/debrief.s` `mission_end`, `pilot_record_won`, `pilot_record_lost`, `pilot_locate`. |
| Difference ledger | **Grounded behavior:** the order of the steps, the three-way choice, both record updates and the setback walk are as listed. **Not carried:** every sound call (`0002B9CF`, `00004FE4`, `000050B4`, `0002BEDC`), the stack reset, the file write and the screens; `[00029D47..]` (the campaign digits `0002A104-0002A1A9` leave) is an input - the runtime has no campaign menu to produce it; `[00022368]` is cleared as `dword22368` because its purpose is only partly recovered. The browser runtime does not call `missionEnd`: its fuel and wreck branches record `flight.missionEnd` and stop the tick (`#fuel-exhausted`, `#player-damage-chain`), as before. **Falcon, disagreement:** `pilot_record_lost`, `pilot_record_won` and `pilot_record_done` skip the whole update when `roster_ok` is clear; the original has no such test (a missing COMANCHE.NAM leaves the buffer zeroed and `0002873D` still updates it). The Falcon also keeps flying the tick after the wreck's countdown reaches zero (`flt_mission_end` set, `bra .alive`) where `00018EF6` leaves for `0002873D` at once, and `mission_end` does not zero the shake phase, the shake countdown and the screen drop (`flt_shake_phase`, `flt_shake_timer`, `flt_crash_drop`) the way `0002874D-00028761` do. |
| Fixtures and status | **Checked against DOS execution.** The pilot-record paths were called directly (`work/dos_call.py pilot-record`: `000287E2` to `00028898` and `000288ED` to `000289CF`, 160 random rosters with won and lost flights, gated and ungated missions, campaigns completed or not, promotion bytes and half-filled rank slots - 18 of the 80 not-won cases take the setback walk and 53 of the 80 won cases stamp a rank byte): `pilotRecordLost` and `pilotRecordWon` leave the 1,450-byte roster and the debrief sentence exactly as the original does in all 160. The whole chain, from the captured roster at `0002873D`'s entry through the statistics, the record update, the ranking and the debrief text, agrees with the original over a live abort and a live win (`work/replay_dos/mission-live-abort300.json`, `mission-live-win300.json`: 0 differing bytes of the 1,450 in both; the Falcon source recorded the won path as Unproven). The road out of `0002873D` was run in the original too: `000287AB` to the stops `00005690`, `00005AE3`, `000287E2` and `000288ED` on 60 random `[00019ED4]`, `[00019D91]`, hull and goal-flag values (`missionEndRoute` agrees on the road and on whether `[00019D91]` is cleared), and `000227A6` on 20 random active tables (`clearMissionObjects` clears slots 1..130, `[00022368]` and `[00022384]` and nothing else). **Unproven** against DOS: the statistics-to-record glue inside `missionEnd` beyond what the live win and abort exercise, the designator-box zeroing (`00028795-000287A6`) and the sound calls. |

## `roster-ranking`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00029F36`, range `00029F36-0002A0AC`, and the digit refresh `0002A0AD-0002A0FE`; the roster is the 1,450-byte file COMANCHE.NAM at flat `00029582` (written by `00015D40` with `ebx = 0x5AA`, `000288A2`, `000281F4`). Offsets from `00029582`: eight 43-byte name records (`+0`; 0x20, bar-b, three rank-number characters, bar-g, 0x20, the 22-character name from `+9`, a 0x20 at `+0x1F`, ten rank-byte slots `+0x20..+0x29` filled `0xFC`, a 0 at `+0x2A`), the selected pilot `[00029701]` at `+0x17F`, one campaign byte a pilot `[00029702]` at `+0x180`, ten progress bytes a pilot `[0002970A]` at `+0x188`, the mission chosen last `[0002975A]` at `+0x1D8`, little-endian dwords missions won `[0002975C]` at `+0x1DA`, score `[0002977C]` at `+0x1FA`, kills `[0002979C]` at `+0x21A`, 100 mission-won flags a pilot `[000297BC]` at `+0x23A` and ten campaign-completed bytes a pilot `[00029ADC]` at `+0x55A`. |
| Recovered function | A selection sort over the eight pilots by missions won: for ebx = 8 down to 2 (1-based) find, scanning ebx-1 down to 1, the pilot with the strictly fewest wins starting from ebx's own count (`jae` keeps the first found, `00029F57`), then swap that pilot with ebx. The swap exchanges the campaign byte, the ten progress and ten completion bytes, the three dwords, the 100 mission flags, and the name record as `ecx = 0x2B >> 2` = TEN dwords (`0002A072`): the record's bytes 40, 41 (the last two rank slots) and 42 (the 0) do not move. `[00027DAA]` follows the selected pilot (`0002A039-0002A053`). The refresh then writes each pilot's won count as three decimal characters into record bytes 3..5, a zero tens or hundreds digit as the blank `0xFD` (`0002A0D4`, `0002A0E5`), and `[00029701] = [00027DAA]`. |
| Implementations | `jsComanche/dos-pilot.js`: `ROSTER` (the layout), `rosterSort`, `rosterRefreshRanks`, `rosterGet32`, `rosterSet32`. Falcon counterpart: `src/debrief.s` `roster_sort`, `roster_format`, `roster_add32` and the `ROSTER_*` constants of `src/inc/comanche.s`. |
| Difference ledger | **Falcon, disagreement (DOS wins):** `roster_sort` swaps the whole `ROSTER_STRIDE` = 43-byte name record (`src/debrief.s`, `moveq #ROSTER_STRIDE,d3` into `.swap_rows`); `0002A057-0002A072` swaps `0x2B >> 2` = 10 dwords, 40 bytes. The last two rank slots and the terminator therefore stay with the seat, not the pilot, in the original; this shows only for a pilot with nine or ten rank bytes (campaign completions), which the shipped campaigns do not give. All layout offsets agree with the Falcon's constants. **Not carried:** the file write. |
| Fixtures and status | **Checked against DOS execution.** `00029F36` was called directly in the original on 61 rosters (the shipped file and 60 random ones: counts with ties and zeros, every field distinct per pilot, a random selected pilot) and `rosterSort` leaves the same 1,450 bytes and the same `[00027DAA]` in all 61 - including the name record's last three bytes, which stay with the seat: the original swaps ten dwords, so the Falcon's 43-byte swap is the disagreement. The shipped COMANCHE.NAM is a fixed point of the sort. An independent array-of-pilots transcription of the scan and the swap, and the descending order, are checked in `tools/prove-browser-menus.js`. **Ported and checked against DOS.** |

### Native roster correction (2026-10-10)

The historical Falcon disagreement in `roster-ranking` above is superseded
by the current source and instruction-level test. Inspection of
`re/listings/comanche.lst` at `00029F84-00029FEF` shows two dwords **and a word**
exchanged for each ten-byte progress/completion row. The existing native
helper rounded every exchange down to a multiple of four, preserving the
name record's correct 40-byte exchange but incorrectly swapping only eight
bytes of those ten-byte rows. `roster_sort` now passes the exchange length
separately from the record stride: 10/10, 43/40 and 100/100. The last three
name bytes continue to stay with their seat.

The rank refresh's DOS divisions (`0002A0C5`, `0002A0CF`, `0002A0E0`) have
zero high dividend. `roster_format` uses `divul.l` for the unsigned 32-bit
dividend with quotient and remainder; the former `divu.l d1,d2:d0` selected
the 64-bit dividend instruction and did not reach the harness exit on the
68060. This is an instruction mechanism correction, preserving DOS arithmetic.

Reproduce fresh evidence with:

```
python3 work/dos_call.py roster-sort --out work/replay_dos/dos-call-roster-sort.json
node tools/check-js-dos-calls.js --routine roster-sort
python3 tools/check-falcon-roster.py
```

The native harness extracts the production sort, refresh, byte-swap macro
and layout constants, assembles for the declared CPU and compares every
roster byte and selected pilot against the same DOS cases used by JavaScript.
Build commands, program/source/fixture/output hashes and debugger logs live
in ignored `build/check-roster-{68030,68060}/`. The pre-change source is a
negative control (`--source build/roster-before.s`, made with
`git show HEAD:src/debrief.s` before this change): case 1 differs at byte 400,
the first progress row's ninth byte. This function check does not prove the
whole mission/debrief route, file writes, graphics, timing or real hardware.

Both MC68030 and MC68060 match all 41 DOS cases, all 1,450 roster bytes and
the selected pilot. JavaScript matches the same 41 cases. The connected browser
proof gate passes; missing unrelated DOS captures are reported as SKIP.

## `player-damage-chain`

### Native collision decision contracts (2026-10-10)

The current native flight already contains `000192EE-0001934F`; the historical
missing-collision note is superseded. Fresh instruction-bound DOS captures
from `work/trace_player_damage.py --scenario collide --skip 1 --from 400
--out work/replay_dos/damage-collide.json` yield 37 box/altitude boundary cases.
`node tools/check-js-damage.js --scenario collide` and
`python3 tools/check-falcon-collision.py` agree with all 37 on JavaScript and
both MC68030/MC68060. The native harness extracts the existing block, supplies
the captured player and thirty-object table with big-endian numeric fields,
and observes only its crash or terrain exit. It preserves the subtraction's
borrow into `roxr.b`, the one's-complement magnitudes and unsigned box tests.
The wreck handler pointer is represented by a test identity constant; it is
only compared, never called. Commands, hashes and logs are retained in
`build/check-collision-{68030,68060}/`. Crash aftermath, live object evolution
and the whole flight route remain separately Unproven; the browser's flight
collision branch remains dormant as recorded below.

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00018F94` and its caller `FUN_00018D20`: the death block `00018EE3-00018F93`, the damaged engine `00018F94-00018FB6`, the T gauge `00018FB7-00019002`, the tail-rotor yaw `000190AB-000190B4`, the object collision test `000192EE-0001934F`, the crash response `00019424-000194DB` (restore, bounce, damage), the repair item `00026B49-00026B87`; chase view case `00019820`, wreck puff `000227BF`. The shake RNG `[00019DB8]` is the PIT source of `#shake-timer`. DOS captures: `work/trace_player_damage.py` (scenarios wreck, sinking, crash, engine, collide). |
| Recovered function | **Death block.** `[00019E49]` (set by `000194C9` when the hull goes negative, and by the shell hit `00023654`) arms it. `[00019E48]` (0x64 from `000063DE`) loses that byte a tick; zero leaves for `0002873D`. The stick `[00019DC8]`, `[00019DCC]` is zeroed. Hull `[00019E40]` still non-negative: collective `0xFE`, altitude +4 while it is `0xFA` or less, and from `0xE6` the speed stick is `0xFFFFFEA2`. Hull negative: collective 0, shake 10, with the cockpit view the screen drop `[00019DC4]` gains `0x52` a tick and at `0xE6A` the chase view is selected (the key-7 case, sound `0x0B`), and when `[00019DB8] & 0xF` is 0 a wreck puff is made from slot 0x1F (`000227BF`). **Engine** (`[00019E39]` negative): altitude -1 above 10 and the speed ceiling `[00019CCC]` = `0x800000`. **T gauge** `[00019D84]`: the stick sar 5 one's-complemented (`cdq / xor`) plus three times the collective, clamped to `0xC8`, halved by a damaged engine; `00018FE7-00019002` also derives the engine pitch word. **Tail rotor** (`[00019E38]` negative): `+0x600000` to the turn rate before its clamp. **Object collision** (slots 0x1E..1, active, state not `000237B0`): the half altitude difference of `sub / rcr / cbw / xor` at most 0xF (the player up to 0x1F above, 0x20 below), and the one's-complement magnitude of the 10.22 differences in X and Y at most `0x1400000` (one unit wider on the side the object is ahead). **Crash response** (ground, when the byte difference is above 2, `0001937E`; or an object): the frame-start position and the previous altitude return; a wreck stops there; otherwise lateral and forward speed negate and forward halves, shake 10, altitude +4 saturating, then `[00019DB8] += x`, cells `[low byte & 7]` and `[low byte >> 5]` each decrement (byte wrap), `[00019DB8]` rotates right 8, the hull loses `[00019DB8] & 3`, and a negative hull sets `[00019E49]`. |
| Implementations | `jsComanche/dos-damage.js`: `deathBlock`, `engineDamage`, `torqueGauge`, `tailRotorYaw`, `objectCollision`, `crashResponse`, `repairAll`, each over one explicit state object. `jsComanche/dos-runtime.js`: `flightTick` enters the death block, engine, T gauge, tail rotor and (for ground contact) `crashResponse` at the listing's points through `damageView` and `applyDamageRequests`. Falcon counterpart: `src/flight.s` `flight_tick`. |
| Difference ledger | **Grounded behavior:** the arithmetic and order above, with the requests the original makes of other subsystems (end of flight, chase view, wreck puff, sounds) returned as data. The chase view's own tail (`000196B4-000196CF`, shared by all seven view-select cases) also zeroes the screen drop through `0001687D`, which `applyViewKey` now does; it also clears the target latch and threat blip for the two external-camera keys, which the browser had restricted to variants 1-6 (the listing sends all seven cases to `000196B4`; the DOS object fixtures are unchanged by it). **Not carried:** sound; the engine pitch word `[00004186]` beyond its value; the nested frames the chase view's tail runs inside the original's tick (`00019820` -> `000196B4` calls the frame driver `0000D3C0` again, which consumes one more replay record and ticks the wreck's countdown once more, so the original's cursor jumps by two records on that tick) - the browser takes the view change as part of one tick, which is why the capture check compares rows from that tick on only by the countdown and the drop. **Injected input:** `[00019DB8]` is read as given and only stirred where the listing stirs it (`00019492`, `000194B2`); its wall-clock evolution is `#shake-timer`'s Unproven part. The browser fixture has no timer, so its value after a crash is whatever the stir leaves, and `tools/check-js-objects.js --all` figures for DEMO2, DEMO3 and DEMO0 move slightly because DEMO1's first crash (record 284) now stirs it in the prelude; DEMO1's own figures and every captured DOS flight are unchanged. **Dormant:** `objectCollision` is transcribed and proved against DOS (37 of 37 samples) but NOT called by `flightTick`. With it entered, DEMO2 crashes at tick 280 into the browser's slot-27 Hokum, where the captured DOS flight (`work/replay_dos/flight-dos.json`) flies on and the unwired reference matches it for all 676 ticks; the browser's mobile objects (states `00023F60`, `00023CF0`) are not DOS-exact in position (their motion takes the wall-clock RNG) and the test must wait for that. **Falcon, disagreements:** `flight_tick` has no counterpart to `000192EE-0001934F` at all (it goes from the lock-loss test straight to the terrain follow), so the Falcon never collides with an object; `flt_crash_drop` is never zeroed by a view selection (`0001687D`) or by `0002873D` (`00028761`), only by `flight_reset`; after the wreck's countdown reaches zero `flight_tick` continues the tick (see `#mission-end-route`). The rest of the block, the engine cap, the tail rotor, the T gauge and the crash tail agree with the listing line by line. |
| Fixtures and status | **Checked against DOS execution** (`work/trace_player_damage.py`, QEMU on a snapshot of the genuine image, breakpoints at `00019555`, `00019424`, `0001947B`, `000194E0`, `000192EE`, `00019352` and `0002873D`; captures `work/replay_dos/damage-*.json`, derived and gitignored; `node tools/check-js-damage.js`, also run by the proof gate, reports SKIP when they are absent): **crash** - the player's altitude forced to 0 at the end of 40 ticks of DEMO0 gives 26 crashes including the fatal one (hull 1 to -2) and 14 crashes of a wreck; for each, `crashResponse` run on the state at `00019424` with the RNG the tail read gives the restored position, altitude, both speeds, the shake countdown, the two decremented cells, the hull, the death cue and the stirred RNG of `000194E0` exactly (26 of 26, none stepped by the timer ISR in between), and the browser runtime flown to the same cursor agrees tick for tick on position, altitude, speed ceiling, T gauge, turn and angle over all 40 ticks, with damaged tail rotor and engine in play; **wreck** - `[00019E49]` set and the hull forced to -1: 98 ticks compared by records consumed on the countdown, collective, stick, screen drop (0x52 a tick, zero after the chase view), view variant, altitude, position, torque, turn and angle, the chase view at the same record, and the flight ending at the same record; **sinking** (hull left positive, 99 ticks, the same fields: collective 0xFE, +4 altitude to 0xE6, then the -0x15E stick) and **engine** (cells `[00019E38]` and `[00019E39]` set to 0xFF, 60 ticks: the speed cap, the one-unit sink, the T gauge and the tail rotor's yaw); **collide** - the player placed at 37 offsets from a mission object at `000192EE` (box edges in X and Y either side, corners, altitude differences around 0x1F and 0x20 each way): `objectCollision` agrees with the original's path (`00019424` or `00019352`) at 37 of 37, including the box being one unit wider on the side the object is ahead and the altitude test's 0x1F/0x20 asymmetry. `tools/prove-browser-menus.js` also exercises each function on its own, and `tools/prove-browser-attract.js` calls `flightTick` for a ground crash and a 100-tick wreck. **Unproven:** the repair item `repairAll` (no capture), sound, the object collision inside the browser's flight (dormant, above), and the wall-clock RNG. The unwired reference still matches `work/replay_dos/flight-dos.json` (DEMO2) position and altitude for 676 of 676 ticks, and the flights of all four demos are tick for tick identical to the earlier reference over their first 700 ticks (only the hull, the cells and `[00019DB8]` differ after DEMO1's first crash at record 284). |

## `mission-list-scan`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0002A1AD`, range `0002A1AD-0002A299`, reading the campaign file `FUN_00015DD0` left at `0003CC20` (`[00015DC8]` bytes) after `FUN_0002A2F8` (`0002A2F8-0002A31C`) decoded it: when the first byte is not `{` every dword is XORed with `0x11120603`. |
| Recovered function | After the campaign title's first `}` the routine finds up to ten `{...}` titles (`repne scasb` against one shared remaining count). Per mission k it stores the star `[00029F18+k]` (1 when the byte after the `}` is `*`), the promotion byte `[00029F2C+k]` (digit + 1 when that `*` is followed by a digit), the text pointer `[00029EF0+4k]` (just after the `}`), and a 0x20-byte name slot at `00029D95 + 0x20 k`: `7C 67 20 20`, the title, `0xFC` pad to the slot's last byte, 0. The slot after the last title keeps the end marker `00 00 FF 00` written at the top of every pass (`0002A212`). A title that fills the slot gets no pad and no terminator (`0002A286` je / js). |
| Implementations | `jsComanche/dos-menu.js`: `decodeMissionImage`, `scanMissionList`. Falcon counterpart: `src/screen.s` `screen_fill_missions`. |
| Difference ledger | **Grounded behavior:** as above. The decode pads the image to whole dwords with zero bytes where the original decodes whatever its read buffer held past the file's end; those bytes are never read by the routines below. **Falcon, disagreement:** `screen_fill_missions` always writes a 0 at slot byte 0x1F (`clr.b (a6)`), including for a title that fills the slot where the original writes none, and bounds-checks every scan against the stream end where the original relies on the shared count; neither shows for the shipped files (the longest title is 23 characters). The campaign digit table `[00029D47..]` (`0002A104-0002A1A9`) is not recovered here. |
| Fixtures and status | **Checked against DOS execution.** `0002A1E6-0002A299` was run in the original on 42 campaign files (the shipped 0.MIS and 1.MIS and 40 generated ones: zero to twelve titles, names of 1, 27, 28 and 31 characters, stars with and without digits, a missing closing brace) and `scanMissionList` leaves the same name slots (including the end marker), star and promotion bytes, text pointers and count in all 42; `0002A2F8` decoded 30 random buffers (plain-text first byte or not, lengths 1 to 1000) identically to `decodeMissionImage`; and `0002A29A` took 60 random texts (blank, indented and `;` lines, CR or CRLF, a line longer than 0xA0) to the same end offset or the same error exit as `skipLine`. The proof gate also compares the shipped files with an independent regular-expression reading. **Ported and checked against DOS.** |

## `mission-list-gate`

| Field | Record |
|---|---|
| DOS identity and evidence | `loc_00028F3F`, range `00028F3F-00029033`: the row colours `00028F46-00028FB8`, the list's opening selection `00028FBA-00028FE1`, the choice store `00028FE6-00029010` and the lock test `00029016-00029033`; the message routine `FUN_00026E90` (`00026E90-00026F20`) with the text at `000269D5`. |
| Recovered function | The colour letter of row ebx is green `g` (0x67) by default; orange `o` (0x6F) when edx (the number of won missions passed so far) differs from ebx and the row is a star mission; blue `b` (0x62) when the row's own won flag (`[000297BC + 100 * pilot + 10 * digit + row]`) is set, which also counts it. The letter is stored in the row's name slot byte 1 and in `[00029F22+row]`, up to the first slot whose byte 1 is zero. The menu returns the row `ecx` (`00028FE1`, `call 00027DB4`); it is stored first as the campaign's progress byte `[0002970A + 10 * pilot + digit]` and as `[0002975A]`; then `[00029F22+ecx] == 0x6F` (orange) shows the message "You must finish GREEN missions." (`esi = 000269D5`, `00026E90` skips the menu bar redraw for this text, waits for a key or button and clears `[00019DF2]`/`[00019DF3]`) and returns to the list (`00029033 jmp 00028F3F`); any other row goes to the briefing. |
| Implementations | `jsComanche/dos-menu.js`: `missionRowColours`, `missionListSelection`, `missionListChoice`. Falcon counterpart: `src/screen.s` `screen_mission_colours`, the `.mission_chosen` case of `screen_input`, `src/debrief.s` `roster_select_mission`. |
| Difference ledger | **Grounded behavior:** the rule, the store-before-test order (a refused locked row is still recorded), and the break at the first empty slot. **Not carried:** the box geometry (`bl = 0x0F, bh = 0x32, dl = 0x42, dh = 0x0F`), the key wait and the redraw. **Falcon, no disagreement found:** `screen_mission_colours` follows the same loop and exits. |
| Fixtures and status | **Checked against DOS execution.** `00028F46-00028FBA` (the row colours) was run in the original on 60 random rosters, star tables and list lengths (0, 1, 3, 7, 10 titles) and `missionRowColours` leaves the same name slots and the same `[00029F22]` colours; `00028FBA-00028FE1` (the row the list opens on) on 40 random rosters: the byte handed to the menu agrees; `00028FE6` to `00029016-00029038` (the choice store and the lock test) on 50 random rosters, rows and colour tables: the roster bytes and the locked/unlocked branch agree. The expected strings of six hand-made patterns are also asserted in `tools/prove-browser-menus.js`. **Not checked:** the lock message's box and key wait (`00026E90`), which are drawing. **Ported and checked against DOS.** |

## `mission-briefing`

| Field | Record |
|---|---|
| DOS identity and evidence | `loc_00029038`, range `00029038-00029119`, with the line skipper `FUN_0002A29A` (`0002A29A-0002A2B9`) and the width table `[0002727E]` (256 bytes, data in the hashed image). The campaign file's digit is patched into `0.MIS` at `0002906D` from `[00029D47 + [00029702 + pilot]]` (the attract forces index 0, `00029054`). |
| Recovered function | The output buffer at `0002FB14` starts with the bytes 7C 62 0, the mission's 28-byte name from `[00029D99 + 0x20 k]` (the name, its `0xFC` pad and the slot's 0 terminator), 0, 7C 67. The description starts at the first line after the title line (`0002A29A` from `[00029EF0+4k]`: scan up to 0xA0 bytes for a CR, step over one LF, skip lines that begin at or below 0x20 or with `;`; no CR within 0xA0 bytes is the mission-file error exit `00029359`). Then per source byte: `<` ends the text; LF is dropped; any other control byte becomes a single 0x20 and is dropped after a 0x20 (`000290CF-000290D8`); a 0x20 records the break point (source after it, output at it); `^` becomes a 0 byte and resets the line; the byte is stored and its width added to the line's; past `0x118` the output is rewound to the recorded space (replaced by a 0) and the source to the byte after it, or - with no space recorded - a 0 follows the overflowing character. The text ends 0xFF. |
| Implementations | `jsComanche/dos-menu.js`: `buildBriefing`, `wrapBriefing` (the loop `000290C0-00029119`), `skipLine`. Falcon counterpart: `src/screen.s` `briefing_build`, `briefing_skip_line`. |
| Difference ledger | **Grounded behavior:** the wrap, both break rules, the fold (the previous byte `ah` is the last byte processed even after a rewind, so a control byte right after the rewound space is folded against that byte, not against the space) and the 28-byte name copy are carried. The recorded break source is an offset, `-1` meaning none, where the original tests the pointer for zero. **Fixture:** the task note names campaign 0, mission 0 of 0.MIS for the four-line screen the original shows; those lines are the first mission of **1.MIS** ("Werewolves on Patrol"; the pilots' campaign byte selects file 1), while 0.MIS's first mission is "Oil Tank Holiday". **Falcon, no disagreement found** in the builder; `briefing_skip_line` returns instead of taking the error exit when no CR is in range (recorded in its own header). |
| Fixtures and status | **Checked against DOS execution.** The wrap loop `000290C0-00029119` was run in the original on 60 random texts (words up to about 70 characters, runs of blanks, CR, LF and tab, `^` breaks, no break point in a line) and `wrapBriefing` leaves the same output bytes and ends at the same source offset in all 60; `0002A29A` as above. The first mission of 1.MIS wraps to exactly "If you're going to see the world, it might as well" / "be from behind enemy lines. Fortunately it's night" / "and the enemy hasn't spotted you yet. Pick'em off" / "one by one, and let your wingman have some fun." (the original's own screen, trailing blank aside); all 20 briefings of both campaign files give 127 lines, none wider than 0x118 by the image's width table, each ending where the next word does not fit (except before a `^`), with no text lost. **Not checked:** the 28-byte name head (`00029078-000290A7`) beyond its transcription from the listing. **Ported and checked against DOS.** |

## `menu-your-stats`

| Field | Record |
|---|---|
| DOS identity and evidence | `loc_00028B37`, range `00028B37-00028C20`; template `000028AB5-00028B36` (130 bytes, data in the image); numbers through `FUN_00028C25`. |
| Recovered function | Four dwords of the template (`[00028B02]`, `[00028B1C]`, `[00028AF6]`, `[00028AFA]`) are set to `0xFCFCFCFC`; the pilot's record bytes 9..41 (0x21 bytes from `0002958B + 0x2B * pilot`) are copied over the template from `00028ABD`; the pilot's score (8 digits at `00028AF6`), missions won (3 at `00028B02`) and kills (4 at `00028B1C`) are formatted right-justified, the characters before the first digit staying `0xFC`. Any key returns to the main menu (`00028C12-00028C20`). |
| Implementations | `jsComanche/dos-menu.js`: `yourStatsScreen`. Falcon counterpart: `src/screen.s` `stats_patch`. |
| Difference ledger | **Grounded behavior:** the blanking, the 0x21-byte copy and the three widths. The template is copied; the original patches it in place (every patched byte is rewritten each time). **Not carried:** the box and drawing. **Falcon, no disagreement found.** |
| Fixtures and status | **Checked against DOS execution.** `00028B3C-00028BCD` was run in the original on 30 random rosters and pilots (scores, victories and kills up to 0xFFFFFFFF, so the number fields keep only their low digits) and `yourStatsScreen` leaves the same 130-byte template in all 30. The shipped roster's first pilot (score 5523, 1 mission, 120 kills) is also asserted in the proof gate. **Not checked:** the box and drawing. **Ported and checked against DOS.** |

## `menu-options-game`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00026AB6`, range `00026AB6-00026E8F`: the seven switch toggles `00026AB6-00026B49`, the Game column's items `00026D8B-00026E8F` (Save Menu Settings, Abort Mission, Exit to DOS, Return, About Comanche); the settings block `[00025DBC..00025DDE]` (35 bytes, shipped as Comanche.MNU), the file writer `FUN_00015D40`, the box `FUN_0002628E`, the texts at `0002691C` (About), `000269BC` (Menu Settings Saved). |
| Recovered function | Key code 0x2E, 0x2D, 0x14, 0x15, 0x30, 0x31, 0x32 flip the brace in the menu text at `[0002677A]`, `[00026767]`, `[000266A0]`, `[000266A9]`, `[000267AC]`, `[000267C1]`, `[000267D2]` (`xor al, 6`: `{` 0x7B and `}` 0x7D) and store the new character into `[00025DDE]`, `[00025DDD]`, `[00025DD8]`, `[00025DD9]`, `[00025DDA]`, `[00025DDB]`, `[00025DDC]`. Item 2 writes the 35 bytes at `00025DBC` to Comanche.MNU and shows "Menu Settings Saved" (box registers `bl = 0x16, bh = 0x24, dl = 0x42, dh = 0x0F`); 3 jumps to `0002873D`; 4 to `00006B14`; 1 returns into the options bar (`pop ebx; jmp 0002615C`); 0 shows the About box (`bl = 0x0F, bh = 0x32, dl = 0x1E, dh = 0x5A`). The same routine's repair (0x40) and reload (0x41) items are `#player-damage-chain`'s `repairAll` and the loads copy `[00019D44..58]` to `[00019D2C..40]`. |
| Implementations | `jsComanche/dos-menu.js`: `optionsToggle`, `optionsGameAction`, `SWITCHES`; `jsComanche/dos-damage.js`: `repairAll`. Falcon counterpart: `src/menu.s` `menu_confirm` (toggle store and game boxes), `menu_save_settings`, `menu_option_targets`. |
| Difference ledger | **Grounded behavior:** the seven pairs and the XOR, the 35 bytes and the file name, and the action each item takes. The menu text's braces start from the settings block when the menu opens (`000268A5-000268BE`), not from the image's own text, so the caller supplies `menu.braces` from the file. **Not carried:** the boxes, the key wait, the sound items (`0x20-0x26`), the joystick calibration (`0x2F`), the controller and detail radios, the reload item's `[00019D8D]`/`[00019D8E]`. **Falcon, no disagreement found:** the seven target offsets map to `[00025DD8..DE]` in the order above. |
| Fixtures and status | **Checked against DOS execution** for the toggles: `00026AB6` was run to its `ret` at `00026E8F` on 28 random settings blocks and brace states (each of the seven keys at least twice) and `optionsToggle` leaves the same 35 settings bytes and the same menu-text braces. The proof gate asserts the seven brace addresses lie in the image, the toggle-back, the shipped COMANCHE.MNU's 35 bytes and the action each Game item takes. The Game column's dispatch was run too (`00026D8B` with key codes 0, 1, 2, 3, 4 and four unused codes, a fresh original each time because its drawing paths write through the game's screen pointers and leave memory - code included - zeroed): 3 leaves for `0002873D`, 4 for `00006B14`, 1 for `0002615C`, 2 calls the file writer `00015D40` with `edx = 00025DBC` and `ebx = 0x23` (35 bytes; the inline name `Comanche.MNU` is read from the image), 0 and the unused codes end at `00026E8F`; `optionsGameAction` agrees. **Unproven:** the boxes and their texts' placement, and the Save item's own return path (its drawing wrecked the probe's state before it reached `00026E06`). |

## `pilot-name-entry`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0002800C`, range `0002800C-0002820B` (key loop `0002807E-00028129`, record creation `0002812E-000281FE`); the key FIFO `[00001B70]` fed by the keyboard ISR `FUN_00001B80` (`00001BE8-00001BFA`); scancode to character tables `[000019E9]` (shift released) and `[00001969]` (shift held), the name field `[00027FEA]` (32 bytes), the cursor `[0002800B]`, the record head `00027FC0` (9 bytes) and tail `00027FC9` (12 bytes). |
| Recovered function | The field starts `0xFC` (32 bytes) and the cursor 0; every pass the cursor's place holds `_` (0x5F) and the next byte `0xFC`. Keys come newest first from the FIFO (`bl = [00001B70]`, then `shr [00001B70], 8`; the ISR pushes make codes only, shifting the dword up a byte). Esc leaves; Return with an empty name leaves, otherwise `0xFC` goes to the cursor's place and the pilot is made; Backspace steps back unless at the start; another key looks up `[000019E9 + code]` (0 = no character, ignored) or, when either shift key reads pressed (`[00001A9A]` and `[00001AA6]` are 0x80 and up when released: the AND being negative means both released), `[00001969 + code]`, stores it at the cursor, and advances unless the cursor is 0x16 or the field's characters so far are at least 0x6C wide in the table at `0002727E`. The pilot: slot `[00027DAA]`'s progress and completion bytes, count, score, kills and campaign byte go to zero, the record is head (9) + the first 0x16 field bytes + tail (12), the 100 mission flags clear, the roster is ranked (`00029F36`, which carries `[00027DAA]`) and written. |
| Implementations | `jsComanche/dos-menu.js`: `nameEntryStart`, `nameEntryShowCursor`, `nameEntryKey`, `createPilot`, `keyFifoPush`, `keyFifoPop`. Falcon counterpart: `src/screen.s` `name_enter`, the name cases of `screen_input`, `name_create`. |
| Difference ledger | **Grounded behavior:** the FIFO order, the shift rule, the 0x16 and 0x6C stops and the creation order. The key `code` is limited to the tables' 128 entries: the ISR never queues a release code, so no queued code is 0x80 or above. **Not carried:** the box, the cursor blink (none in the listing), the wait for the next key. **Falcon, no disagreement found:** the Falcon draws the cursor each frame instead of at the top of each key pass, which gives the same record; the pilot is built by the same stores. |
| Fixtures and status | **Checked against DOS execution.** The real routine `0002800C` was driven in the original with scripted keys through `[00001B70]` (the loop at `0002807E` stopped, a scancode and the shift states poked, resumed): 36 sessions - a few letters, shifted letters, Backspace and invalid keys, 30 wide capitals (the 0x6C width stop), 40 narrow letters (the 0x16 stop), Backspace at the start, Return and Esc - and `nameEntryKey` plus `createPilot` leave the same roster (1,450 bytes, 22 sessions created a pilot), the same 32-byte field, the same `[0002800B]` and the same `[00027DAA]` after the ranking in all 36. The key FIFO's own push (`00001BE8`) is not run in the original; the proof gate asserts the newest-first order. **Ported and checked against DOS.** |

## `menu-text-data`

| Field | Record |
|---|---|
| DOS identity and evidence | Flat data of the hashed image: `000284B1-000286F8` (debrief image), `00028AB5-00028B36` (Your Stats template), `0002727E-0002737D` (character widths), `000019E9-00001A68` and `00001969-000019E8` (scancode tables), `00027FC0-00027FD4` (record head and tail), `00027FD5-0002800A` (name prompt), `0002691C-000269FC` (About, Saved, locked-mission texts) and `00025DBC-00025DDE` (default settings block). |
| Recovered function | Static text and tables with the original's pad (`0xFC`), blank (`0xFD`), end (`0xFF`) and line (0) codes and colour escapes (bar plus a letter) kept as bytes. |
| Implementations | `jsComanche/dos-text-data.js`: `ComancheDOSText`. Falcon counterpart: the same ranges in the image-derived text blocks of `src/debrief.s`, `src/screen.s` and `src/menu.s`. |
| Difference ledger | **None in the stored values:** every entry is compared byte for byte with the image by the proof gate. The typed-array container is a target representation only. |
| Fixtures and status | `tools/prove-browser-menus.js` (12 ranges). **Verified at the data boundary.** |

## Out of declared scope

Live keyboard/input consumption, sound, mission completion, real menu handoff,
and phase-gated frame tails are outside this browser fixture. The CPU-only
Falcon source slice is active in `src/`; its TOS/VIDEL timing and pixel parity
remain separate validation gates recorded in
`analysis/functions/falcon-attract.md`.
Authored mission-object creation, replay-triggered dynamic allocation, state,
collision/destruction, projection, sorting, and draw are implemented for the
connected attract passes. No browser replacement is allowed to alter the
connected attract state.

## `view-select`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0001959F` selector cases `00019689-00019907`, shared basis builder `FUN_00007D25`, chase handler `00007C26`, fixed-ground handler `00007CC5`, and bearing helper `FUN_000256C8`; recovered selector/camera contract in `analysis/functions/falcon-attract.md`. |
| Recovered function | Map replay keys `0x02..0x08` to view variants 1..7. Variants 2..5 alter the angle/horizon basis; variant 6 trails the flight by `turn*4`, moves 15 map cells behind it, and raises the camera over terrain; variant 7 uses the stored ten-cell-back camera and aims at object slot 31. Key `0x09` re-selects variant 7 without replacing its stored camera. |
| Implementations | `jsComanche/dos-runtime.js`: `applyViewKey`, `buildViewBasis`, `placeFixedCamera`, `viewBearingToPoint`, and the view-backed `renderClear`, `drawTerrain`, `objectTransform`, `objectFindPage`, `objectAspect`, and cockpit gate. Falcon counterpart: `src/view.s`, `src/frame.s`, `src/main.s`; CPU-only route record: `analysis/functions/falcon-attract.md`. |
| Difference ledger | **Grounded behavior:** selector mapping, signed Q31 angle offsets, published flight basis for fixed-camera placement, DOS raw-coordinate camera movement, table-driven bearing, live camera terrain/object projection, byte-wrapped camera terrain lift (00007CAB/00019879 discard shift carry before saturating add carry), loaded console composition for every view, and external-view instrument suppression are retained. **Target artefact:** the browser keeps one deterministic frame per fixture tick; DOS selector commands re-enter its frame tail and may publish intermediate single-buffered frames. |
| Fixtures and status | `tools/prove-browser-attract.js` exercises variants 1..7 and the `0x09` quirk; `tools/trace-browser-replay.js` records selector function IDs and view state; `tools/trace-browser-sequence.js` records variant changes. **Ported for connected replay;** DOS/Falcon complete external-camera frame parity remains `Unproven`. |

Three things carried by the Falcon are outside this fixture, each because the
route does not reach them rather than because they were not read:

- The 96-column marcher and `0001453D`'s copy of compose block A over block B,
  which is how one marched column becomes four screen pixels. That is the
  `LOW.DTL` path; this milestone runs high detail and never enters it.
- `[0x25DD8]`, sky on/off. `000261AF` leaves `0x1757E` - a flat viewport fill
  of `[0x2A37E]` - in all three slots unless the byte is `'}'`, and
  `00016EC0`/`00017230` fall through to the same fill when no sky bank is
  loaded. The shipped `COMANCHE.MNU` settings block is `'1003}}}}}{{'`, so the
  byte IS `'}'` and every campaign-0 attract mission carries a sky bank
  (`sky2`, `sky4`, `sky2`, `sky4`). The fill is unreachable here and the
  browser's unconditional sky matches; a settings block that disabled the sky
  would need it.
- The runtime Detail menu. `src/dtl.s` reloads the ring tables and the
  projection pages when `[0x25DD4]` changes; the browser loads `HIGH.DTL` once
  and has no menu to honour.

The `1.71 pixels per column` reading recorded elsewhere was wrong and is not a
gap here: `sub_00007AA0` copies each span twice through plane masks `0x302`
and `0xC02`, so one source byte is two pixels, which is the geometry this
port already had.

## Sound driver (2026-10-07)

The audio of the original is two layers, recovered here in full: the music and FM driver `0002B9CF-0002C4A0` (this section's `sound-driver-core`, `-ms3`, `-effects`, `-opl`, `-mpu`, `-speaker`) and the digital effect layer `00004E0C-000051B6` with the mixer fill `00005220` (`sound-driver-digital`). The long-form specification, with the data formats, the device model, every call site and the 68030 interface, is `analysis/functions/sound-driver.md`; this section carries the §4.2 records of the JavaScript routines in `jsComanche/dos-sound.js`. Silent sound stays the supported default of the browser runtime: nothing here is connected to the attract cycle, and the module takes the timer tick, the card's answers and the placement of the song buffers as explicit inputs.

## `sound-driver-module`

| Field | Record |
|---|---|
| DOS identity and evidence | The driver image: code `0002B9CF-0002C4A0` (plus the unreferenced 0002BFAB), variables and tables `0002C48C-0002D800`, effect table `0002D408`, patch table `0002C70D`, F-number table `0002CF0D`; mixer `00004E0C-000051B6`, `00005220-000053D5`, slots `00004142-000041B7`. Same hashed DOS image as above, flat SHA-256 `a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c`. The timer ISR `FUN_00001D20` calls `[0002C48C]` once per PIT interrupt (`00001D2C`); the PIT divisor `0x47B4` (`00001CEB`) gives 1193182/18356 = 65.0 Hz. |
| Recovered function | One memory image, the flat image's own bytes `00000000-00032B20`, holds the driver's variables and constant tables at the addresses the listing uses, so the original's aliasing (a channel nibble above 9 indexes past a ten-byte array into the next one) is reproduced rather than guarded against. Song and bank buffers are placed above it by the caller at flat addresses (`placeSong`) exactly where the loader `00015E6E` leaves them. The registers are explicit, because the original reads what its callees leave behind. |
| Implementations | `jsComanche/dos-sound.js`: `Machine` (memory, registers, stack), `create` (all routines as closures over one machine, exposed as `command`, `start`, `stop`, `tick`, `effect`, `fx`, `speechA`, `speechB`, `voice`, `resetMixer`, `setRate`, `fill`, `placeSong`, `takeWrites`, `read`), `decodeMusicFile` (`#sound-driver-ms3`). Oracle probe `work/trace_sound_writes.py`; proof tool `tools/check-js-sound.js`. No Falcon counterpart yet: the 68030 interface is specified in `analysis/functions/sound-driver.md`. |
| Difference ledger | **Target artefact (inputs, never invented):** the tick is the caller's `tick()` call, there is no clock inside; the OPL status the detection reads (`hooks.oplStatus`), the MPU-401 acknowledge (`hooks.mpuAck`, 0xFE) and port 0x61 (`hooks.port61`) come from the caller; the delay-loop calibration `[00001C8E]` (`options.delayLoops`) only changes the MPU time-out word `[0002D161]`. **Not carried:** the calibrated delay loops inside the port helpers (they change the time between writes, not the writes), `cli` and `sti`, the DMA and DSP programming of the Sound Blaster (`00001F49`, `00002050`), and the PC speaker's `in al, 0x61` beyond its value. **Unproven:** timing between a write and the chip's reaction, and what the card does with the writes (the capture is the original's output, not its sound). |
| Fixtures and status | `python3 work/trace_sound_writes.py direct --scenario NAME --out build/sound/NAME.json`, then `node tools/check-js-sound.js` (derived, git-ignored; the tool exits non-zero on any difference). 38 direct captures (49956 driver calls, 51827 port writes, 233472 mixed bytes) identical, and one natural run of the game (`natural-attract`: 17757 timer ticks, 16381 driver calls, 65 song starts, 139775 OPL2 writes, 1551 timer interrupts that arrived inside a driver call placed from the original's variables) identical, at the last run; `tools/prove-browser-menus.js` runs it with the other DOS captures and reports SKIP when they are absent. See each record for what the captures cover. |

## `sound-driver-core`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0002B9CF` [0002B9CF-0002B9F2] the command entry (`ax` saved at `[0002C4A0]`, high nibble of `ah` indexes the dword table `0002C5D9`: 0..2 effect `0002BB09`, 3 select `0002B9F7`, 4 pause `0002BBC1`, 5 resume `0002BBD0`, 6 query `0002BBBB`, 7 volume `0002BB01`, 8 detect `0002BBDA`, others `0002B9F3`); `FUN_0002BBF2` [0002BBF2-0002BC7B] the tick; `FUN_0002BC8B` [0002BC8B-0002BCE9] key on or off; `FUN_0002BF3A`/`0002BF43` [0002BF3A-0002BF87] patch load; `FUN_0002BF12` [0002BF12-0002BF39] silence; `FUN_0002BEDC` [0002BEDC-0002BEEF] stop; `FUN_0002BD00` [0002BD00-0002BD74] start. The device tables are seven dword slots (`0002C649, 0002C665, 0002C681, 0002C69D, 0002C6B9, 0002C6D5, 0002C6F1`: init, end of tick, silence, note, pitch, patch, detect) each followed by one column per device 0..5 (`0002C64D`+4*device, and so on). |
| Recovered function | **Select (command 3, AL = device 1..5):** a device already selected is shut down (effect flags cleared, music silenced, its silence routine), the seven slots are copied from the new device's column, the pause flag is cleared and the init routine called; a zero result leaves the tick vector at the empty routine `0002B9F6` and returns 0, otherwise the music is stopped, the ten channels' state reset (master volume `[0002C5A8]` = 0xFF, every pitch-envelope cursor at `0002D5D0`) and `[0002C48C]` = `0002BBF2`; AL = 0xFF. For device 5 the init routine is a bare `ret`, so the result is whatever the last slot copy left in AL (0x82), which counts as success. **Tick:** run the sequencer if `[0002C49E]` is non-zero; then for channels 9 down to 0: an effect's remaining time `[0002C5C9+ch]` counts down and keys the channel off when it reaches 2; the pitch is the base note `[0002C578+ch]` plus the E-event offset `[0002C568+ch]` plus the next step of the patch's pitch envelope (0x80 holds the last value, 0x81 loops to the start); a pitch different from `[0002C588+ch]` goes to the pitch routine. **Key** (`ch`, `ah` = note or 0, `cl` = velocity): paused or note 0 is a key-off; else `hi = (scale[ch] * master) >> 8`, `cl = ((hi + 1) * (cl << 1)) >> 8`, the envelope cursor is rewound, `[0002C5B9+ch]` set, the note plus `[0002C598+ch]` stored as base note and `[0002C588+ch]` invalidated (so the next tick sends the pitch). **Patch load** (`al`): `[0002C4D4+ch]` = patch, the envelope pointer `[0002D5E6+4*patch]` to both cursors, scale `[0002D550+patch]`, transpose `[0002D4D0+patch]`, then the device's patch routine. |
| Implementations | `jsComanche/dos-sound.js`: `command`, `cmdSelect`, `disable`, `cmdPause`, `cmdResume`, `cmdQuery`, `cmdVolume`, `cmdDetect`, `unsupported`, `musicTick`, `keyChannel`, `loadPatch`, `silence`, `stopMusic`, `startMusic`, `begin`, `noop`, `noneDetect`, `callSlot`; the table slots are read from the memory image and resolved to routines by code address. |
| Difference ledger | **Grounded behavior:** every register the original leaves behind is carried, which is what two traps need: the OPL write helper returns with AX = 0, so after a key-off in the tick's effect expiry AH is 0 and the pitch routine is called with note 0 (`#sound-driver-opl`); and `cmdSelect` on device 5 returns the low byte of the last copied slot (0x82), not a value the init routine computed. Both were found by the first capture that disagreed. **Unproven:** none inside the transcribed routines; what the music sounds like is not claimed. |
| Fixtures and status | Captures `select-adlib`, `select-sb`, `select-bad` (device 0, 6, command 9 and 15, query), `openmus-none` (device 5), `queue-and-loop` (queue behind a playing song, loop, pause, resume, query), `openmus-volume` (command 7): all identical in writes, returned AL and the variables' changes after every call. |

## `sound-driver-ms3`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00015E6E` [00015E6E-00015F6C] the music loader (file prefix `KRL0` stored or `KRL1` run-length coded, dword size, payload; `0001644B` is the decoder), `FUN_0002BD75` [0002BD75-0002BE0E] the event reader, `FUN_0002BE68` [0002BE68-0002BEDB] the sequencer (end of song `0002BE0F-0002BE67`). Song files: `OPENMUS.MS3`, `MENUMUS1.MS3`, `MENUMUS2.MS3` (bare), `FANFARE.RLE` (KRL0), `MUSDAY`, `MUSNIGHT`, `MUSVOLC`, `MUSWIN`, `MUSLOSE`, `WINMUS`, `BIGWIN.RLE` (KRL1). |
| Recovered function | **Song** (all numbers little endian, the pointer given to `0002BD00` is the `M` of the signature): 0x00 `MS3-KGF'91 ` and `0A 0D 1A` (14 bytes), 0x0E a word the driver never reads, 0x10 ten bytes channel links (a non-zero byte n makes every event of that channel also play on channel n-1), 0x1A six unused, 0x20 ten bytes of initial patch per channel, 0x2A six unused, 0x30 the events. **Events:** status byte then data then the delay in ticks to the NEXT event. `9n note vel delay`; `8n delay` (note off, the note is not named); `Cn patch delay` (loaded at once and made the channel's patch); `Dn x delay` (ignored); `En x delay` (a pitch offset for the channel, added to its pitch every tick until the next E); `Bn x y delay` (ignored); any other status as `Dn`. The delay is one byte below 0x80, or two bytes `((b0 & 0x7F) << 7) or b1` (the original takes `b1` unmasked). `FF 2F` ends the song. A delay of 0 chains the next event in the same tick. **Playing:** `[0002C4A2]` counts ticks (starts at 1, so the first tick reads the first event); an event on a channel that holds an effect (`[0002C5C9+ch]` non-zero) is dropped; a note-on first loads the channel's song patch if it is not the loaded one, then keys at note*2. **Flags** of `0002BD00` (AL): bit 0 queues the song behind one that plays (`[0002C49D]`, `[0002C498]`), bit 1 loops it. At the end the channels are silenced and the queued song starts, else the song restarts if it loops, else `[0002C494]` is cleared. A song of only `FF 2F` with flags 2 therefore restarts, and silences all channels, on every tick. |
| Implementations | `jsComanche/dos-sound.js`: `decodeMusicFile`, `readEvent`, `sequencer`, `endOfSong`, `begin`, `startMusic`. |
| Difference ledger | **Grounded behavior:** including the 16-bit `inc bx` at `0002BDED` (a note whose velocity byte is at xxxxFFFF reads its delay from xxxx0000 and continues there: scenario `wrap-inc-bx` places OPENMUS so its first note does, and the original's and the JavaScript's writes are the same). **Not carried:** the loader's file I/O and allocation (`25777`); the caller supplies the decoded bytes. **Unproven:** the word at 0x0E and the unused header bytes (never read here; the editor that made the files may use them); the three songs MUSVOLC, WINMUS and BIGWIN are referenced by no code and by neither shipped mission. |
| Fixtures and status | Every shipped song played to its end and past it: `openmus`, `menumus1` (an empty song), `menumus2` (looped once), `fanfare`, `musday` (10191 ticks), `musnight`, `musvolc`, `muswin`, `muslose`, `winmus`, `bigwin`, `wrap-inc-bx`, `queue-and-loop`; and two songs built by the probe to reach what no shipped song does (`synthetic-events`: Bn and Dn events, an unknown status A0, a two-byte delay, delays of 0, channels above 9 that alias the next arrays, a negative pitch offset, a program change in the middle of a note, the loop flag; `synthetic-links`: channel links 0 to 1 to 2 with different patches); writes and variable changes identical on all, on the OPL device. |

## `sound-driver-effects`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0002BB09` [0002BB09-0002BB50] command 0..2, `FUN_0002BB51` [0002BB51-0002BBBA] one half of an effect; table `0002D408` of 25 entries of 8 bytes (two 4-byte voice records each: duration in ticks, patch + 1, pitch, volume factor); voice lists `0002C619` + 8*device (OPL: channels 7 6 5 4 3 2 1 9); callers `FUN_00004E8E` [00004E8E-00004EA0] with `[00019DF9]` = 0. |
| Recovered function | `ax` of the command: AL = effect, the low nibble of AH a volume nibble (`nibble << 4`, 0xFF when 0). The second half is played first when the dword at `0002D40C + AL` (not `+ 8*AL`: the original indexes it with AL) is non-zero, then the first half. A half takes the first free channel of the device's list (all busy: the last one), marks it an effect's for `duration` ticks, loads patch `(byte 1) - 1`, and keys it at pitch `byte 2` with `cl = (byte 3 * volume) >> 8`. The tick keys the channel off when the time reaches 2. Effects ids 1..7 are the ones the game asks for when no digital device exists (`#sound-driver-digital`); entries 8..24 and the zero entries are never reached by the game. |
| Implementations | `jsComanche/dos-sound.js`: `cmdEffect`, `effectHalf`, `effect`. |
| Difference ledger | **Grounded behavior:** the `0002D40C + AL` presence test is carried as it is, so an effect with one voice (id 1) also plays a second half made of zeros: duration 0, patch 0xFF, pitch 0, which loads patch 0xFF (the bytes at `0002D6FD`, an out-of-table patch) and keys it off; the capture contains those register writes. The first half then takes the same channel again, so patch 255's envelope pointer (the dword at `0002D9E2`, `0x61800004` after the game's start-up relocation of the table at `0002D7F0`) is read only by a tick that arrives between the halves, which happens in the natural run: the machine reads 0x00 there (open bus on QEMU's 16 MB PC) and the JavaScript's `openBusReads` counts it. **Not carried:** the digital branch of `00004E8E` (`#sound-driver-digital`). **Unproven:** which game events reach effects 8..24 (none found), and what the effects sound like. |
| Fixtures and status | `effects` (ids 0..24 on the OPL, 40 ticks each), `effects-volume` (volume nibbles 1, 8, 15), `effect-over-music` (an effect taking channels from a playing song and the song's events being dropped on them): identical. |

## `sound-driver-opl`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0002C1B8` [0002C1B8-0002C1E9] the write helper (AH to port 0x388, AL to 0x389, a calibrated delay after each); `FUN_0002C312` [0002C312-0002C353] init, `FUN_0002C354` [0002C354-0002C37E] silence, `FUN_0002C380` [0002C380-0002C3C8] pitch, `FUN_0002C3C9` [0002C3C9-0002C431] note, `FUN_0002C254` [0002C254-0002C311] patch, `FUN_0002C1EA` [0002C1EA-0002C253] detect. Devices 2 and 3 use these routines. Tables: patches `0002C70D` (128 of 16 bytes), F-numbers `0002CF0D` (256 words), per-voice state `0002D10D`, `0002D116` (the B0 shadow), operator offsets `0002D11F` and `0002D128`, channel to voice map `0002D131`. |
| Recovered function | **Init:** reg 01 = 20, reg 08 = 0, reg BD = C0, every voice's level register 0x3F and B0 cleared, then every voice's B0 shadow set to 1F and patch 0 loaded. **Patch (16 bytes):** bytes 0 2 3 4 are registers 20, 60, 80, E0 of the operator at `[0002D128]` (the carrier), bytes 5 7 8 9 the same for the operator at `[0002D11F]`, byte 6 is that operator's level written inverted (`xor 3F`) to register 40, byte 10 is C0, byte 1 is kept in `[0002D10D+voice]` for the key-on; the load first clears the key bit in B0. **Key on:** level register of the carrier = `(byte 1 or min((cl >> 2) + 0x20, 0x3F)) xor 0x3F`, then B0 with key bit 0x20 set. **Pitch:** the word at `0002CF0D + 2*ah` (F-number low byte to A0; high bits and block to B0 with the shadow's key bit). **Key off:** B0 with the key bit cleared. Music channels 0..7 are voices 0..7, channel 9 is voice 8, channel 8 and 10..15 have none (map value 0x63). **Detect:** reg 04 = 60, 80; read status; reg 02 = FF, reg 04 = 21; wait; read status; reg 04 = 60, 80; present when the first status and 0xE0 is 0 and the second and 0xE0 is 0xC0. |
| Implementations | `jsComanche/dos-sound.js`: `opl`, `oplInit`, `oplSilence`, `oplPitch`, `oplNote`, `oplPatch`, `oplDetect`. |
| Difference ledger | **Grounded behavior:** `opl()` returns with AX = 0 because the delay loops after the data write count AX down from `[00001C8E]` (`0002C1DB-0002C1E3`); the caller `0002BC28` reads AH after the note routine and passes it on as the pitch. **Not carried:** the delays. **Observation (arithmetic on the shipped table, assuming the chip's 49716 Hz sample rate):** the F-number table is 24 entries per octave starting at F-number 0x83 and a note n plays at index 2n, which puts MIDI note 60 at 198 Hz and note 69 at 334 Hz, about 4.8 semitones below concert pitch; not an error of the port. |
| Fixtures and status | All OPL captures (every song, `effects`, `select-*`); the detection with a real YM3812 model (`-device adlib`: status 0x00 then 0xC0) and with no card (`detect-absent`: both status reads 0xFF, AL = 0 for devices 2 and 3; the speaker answers 0xFF without looking, device 5 returns 5, device 0 returns 0, the MPU-401's answer is the probe's 0xFE). The OPL status reads are inputs taken from the capture. |

## `sound-driver-mpu`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0002BF88` [0002BF88-0002BFA9] one byte to data port 0x330 after the ready poll of 0x331; `FUN_0002BFD9` [0002BFD9-0002C01C] one byte to command port 0x331, then the acknowledge from 0x330; `FUN_0002BFAA` a bare `ret` (the callee of every `mov al, 0xD0` and `0xDF`); `FUN_0002C135` [0002C135-0002C189] init, `FUN_0002C0FA` [0002C0FA-0002C134] silence, `FUN_0002C01E` [0002C01E-0002C07C] note, `FUN_0002C07D` [0002C07D-0002C0C9] pitch, `FUN_0002C0CA` [0002C0CA-0002C0F9] patch, `FUN_0002C18A` [0002C18A-0002C1B7] detect. Device 4. |
| Recovered function | **Init:** the Roland MT-32 SysEx at `0002D163` (`F0 41 10 16 12`, address 20 00 00, "Maximum Overkill" padded to 20 characters, checksum, `F7`; byte FC resets the running checksum, FD is replaced by it, FF ends the list) then the UART-mode command 0x3F and its acknowledge. **Silence:** `Bn 7B 00` on the 16 MIDI channels, then the init. **Note:** `9c note vel` or `8c note 40` with the MIDI channel `[0002D141+ch]` (music channels 0..7 are MIDI 1..8, 9 is 9, others none) and the note `ah >> 1`. **Pitch:** a pitch bend `Ec lo hi` from P = `((pitch - base + 0x18) and 0xFF) * 0xAA`: lo is the low 7 bits of 2P, hi bits 8..14 of 4P. **Patch:** `Cc program` with `[0002D183 + patch] - 1`. **Detect:** command 0xFF twice at most, expecting 0xFE. The intelligent-mode prefixes 0xD0 and 0xDF are never sent. |
| Implementations | `jsComanche/dos-sound.js`: `mpuData`, `mpuCommand`, `mpuPrefix`, `mpuInit`, `mpuSilence`, `mpuNote`, `mpuPitch`, `mpuPatch`, `mpuDetect`. |
| Difference ledger | **Target artefact:** QEMU has no MPU-401, so the probe stops at `0002BF88` and `0002BFD9`, logs AL and returns at once; `0002BFD9` returns 0xFE. The byte stream is therefore the original's own; whether the MT-32 reacts is not tested. **Not carried:** the ready and acknowledge polling, `cli` and `sti`. **Unproven:** the time-out path of `0002BFD9` (it pops 16-bit registers off a 32-bit frame; never taken here). |
| Fixtures and status | `openmus-mpu`, `fanfare-mpu`, `musday-mpu` (a song), `effects-mpu` (effects 1, 2, 4, 5, 6, 7 on the MPU-401's channel list), `device-switch` (the shutdown of every device in turn, with a song and an effect running, which reaches the MPU-401's silence routine): identical, bytes and command bytes separately. |

## `sound-driver-speaker`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_0002C432` [0002C432-0002C43A] init, `FUN_0002C43C` [0002C43C-0002C442] silence, `FUN_0002C443` [0002C443-0002C45E] note, `FUN_0002C45F` [0002C45F-0002C47D] pitch, `FUN_0002C47F` [0002C47F-0002C481] detect. Device 1. |
| Recovered function | One voice (channel 0 only): note on loads PIT channel 2 (mode 3, `out 0x43, B6`, then the word at `0002D203 + 2*ah` to port 0x42 low byte then high byte) and sets bits 0 and 1 of port 0x61; note off clears bit 1. |
| Implementations | `jsComanche/dos-sound.js`: `speakerInit`, `speakerSilence`, `speakerNote`, `speakerPitch`, `speakerDetect`. |
| Difference ledger | **Grounded behavior:** the writes to ports 0x43, 0x42 and 0x61. **Input:** the value `in al, 0x61` returns is taken from the capture. |
| Fixtures and status | `openmus-speaker`, `fanfare-speaker`, `effects-speaker`, `device-switch`: identical. |

## `sound-driver-digital`

| Field | Record |
|---|---|
| DOS identity and evidence | `FUN_00004E2E` / `00004E26` [00004E26-00004E86] speech cue from the bank `[00019E9C]` (SPEAK1) / `[00019EA0]` (SPEAK0); `FUN_00004E8E` [00004E8E-00004EA0] effect from the bank `[00019E98]` (SND1); `FUN_00004EA2` [00004EA2-00004F6D] start a sample on a slot; `FUN_00004F6E` [00004F6E-00004FBA] stage the next sample on a slot; `FUN_000050B4` [000050B4-000051B6] reset; `FUN_00004E0C` [00004E0C-00004E25] dither mask; `FUN_00005220` [00005220-0000531A] the fill with its restage blocks `000051C0`, `00005320`, `00005380`. |
| Recovered function | **Banks** (`K1` after loading): `'K1'`, a word count, then count dwords at +4: the offset from the bank start of sample N (1-based) is the dword at `bank + 4*N`. **Sample record:** word limit, word step (16.16, 0xFFFF about 1.0, 0x8000 half rate), unsigned 8-bit samples from record + 4 to record + limit - 1. **Slots:** three, idle when they point at the silence record `000040E2`. `00004EA2`: BL below 0x80 names the slot; 0xFF takes the first idle slot, else the slot already playing the same sample, else (DL = 0) slot 0, else the sound is dropped; 0xFE skips the idle search. DL is a right shift 0..7 patched into the mix loop with its bias from `00004A02`. **Fill:** per output byte the three slots' samples (shifted, biased, the position advanced by the step, a slot past its limit taking its staged sample) are summed, the dither error of the previous pass added, `(sum + 1) >> 2` stored as the next error and `(sum + 1) >> 1` indexes the 512-byte curve at the displacement of `00005307` (`4C0A` loud, `4A0A` soft). The Sound Blaster plays 8-bit mono at 11111 Hz (time constant 0xA6, `00001FBC`), two halves of 0x800 bytes. |
| Implementations | `jsComanche/dos-sound.js`: `stageSample`, `speech`, `digitalEffect`, `stageVoice`, `resetMixer`, `setRate`, `fill`. |
| Difference ledger | **Grounded behavior:** the mix loop's patched immediates live in the memory image at `0000527A/C`, `000052A4/7`, `000052D0/3` as in the original. **Target artefact:** the SB programming (`00001F49`, DMA, IRQ) is not here; `fill()` is called by the caller where the SB IRQ would call it, and returns the bytes the original wrote to the half buffer. The buffer pointers `[00004FD4]` (0x20E2 or 0x30E2 by the 64 KB test of `00005023-0000505E`) are inputs from the image. **Unproven:** the bank contents' meaning (call context only); the identical treatment of device modes 1..4. |
| Fixtures and status | `digital-explosion` (SND1 id 1 at full volume and at distance class 3), `digital-launch` (id 4 at double pitch, native, attenuated), `digital-cannon` (id 7 re-triggered with BL = 0xFE, id 5), `digital-rotor` (id 3 staged on slot 2 and looped through the restage, then silenced), `digital-speech` (SPEAK1 id 4, id 6, SPEAK0 id 2), `digital-mix` (slot choice, drop and steal, the soft curve, dither masks 0, 1, 5, 9, 17): 233472 mixed bytes identical, and the slots', the staged samples' and the dither's variables after every call. |
