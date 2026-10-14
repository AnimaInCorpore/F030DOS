# F030 Comanche attract-mode acceptance report

**Verdict: NOT CERTIFIED.** The current supported attract-mode slice has passing component evidence, but the required DOS-fidelity gates are not all proven. Missing evidence is reported as **Unproven**; there is no overall PASS claim.

Generated UTC: `2026-09-22T21:34:58+00:00`  
Acceptance gates Unproven: `3/5`; failed: `1/5`  
Re-run command: `python3 tools/acceptance-report.py` (returns exit code 1 while any certification gate is Unproven).

## 1. Scope and identity

This report covers the CPU-only Falcon attract route: authored opening pages, the four recorded DEMO pass families, replay-driven flight, terrain, active objects, cockpit/MFD/HUD and page publication. DSP, live controls, sound, menu handoff and mission completion are outside the certified slice.

| identity | value |
|---|---|
| Git HEAD | `14fb9170e1f7f6175587cdfd188211bed3117351` — comanche: paint each loaded console onto the persistent page |
| Worktree | `dirty`; `14` changed/untracked paths at report time |
| Source snapshot | `337698ab084af04ff84d8b44ff4227da056450e836c82b56033f8a48164bb2e9` over `66` selected source/record files |
| DOS oracle | `re/unpacked/COMANCHE.UNPACKED.EXE`; `4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697`; expected `4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697` |
| DOS flat image | `re/unpacked/comanche-flat32.bin`; `a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c`; expected `a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c` |
| Toolchain manifest | [`build/cpu-toolchain.json`](../build/cpu-toolchain.json); `cf31b39e685aabd2efd998e230b3bff626b58966abe383e04d44834edc824de9` |

The source hash is a filesystem snapshot, not a claim that the worktree is committed. The exact build inputs are therefore recoverable even though the tree is dirty.

### Target binaries

| image | path | size | SHA-256 |
|---|---|---:|---|
| 68030 production | `release/comanche.tos` | 111012 | `f4fee819132866606df82de570c63632478370df9729418c159a362c66b07a3e` |
| 68030 debug/timing | `release/comanche_d.tos` | 168776 | `63008a6907ebd4d42814b204b610e5efddf7e5225e4d362d102b44b7c40838d0` |
| 68060 production | `release/68060/comanche.tos` | 111254 | `b00f380362dc5d6d68e0f7129d2eb7ac07d073bc78f71505e8482747dadd152c` |
| 68060 debug/timing | `release/68060/comanche_d.tos` | 169074 | `cd07d72cbf3dd6b0864b9aa2690976530ae459dae0f6465328862c4b3b6e7d78` |
| 68030 multiply harness | `build/check-cpu-68030/check.tos` | 9934 | `9f7a31c1b33b2f683b40f2046d3689e2f1c0642167bfde12d64233d8d5c86814` |
| 68060 multiply harness | `build/check-cpu-68060/check.tos` | 10128 | `fef2bfdd88ff847d4a5b85f3cffc0c61602ab22eb4582b161460c3396a689981` |

### Toolchain components

| component | executable/image | recorded SHA-256 |
|---|---|---|
| vasm | `/Users/saschaspringer/Work/F030Arcade/third_party/chorensha/tools/vasmm68k_mot_mac` | `46822b2b876e9229936913b33f8bca1cde93c7dcc2476010a68ba52849865675` |
| vlink | `/Users/saschaspringer/Work/F030Arcade/third_party/chorensha/tools/vlink_mac` | `109d58c0d69ef2e152bca3eefb090b2048eb72b1a05a2eaa5d4520078e7ac6aa` |
| hatari | `/opt/homebrew/Cellar/hatari/2.6.1/bin/hatari` | `8833309e8b0a8a5a390bedbaf8ea6781c0996ce945278db413aff1388b25f5fd` |
| EmuTOS | `/Users/saschaspringer/Work/F030Arcade/third_party/tos/etos512de.img` | `0bf89da31af7039b79261383242193fe44afaf3733e05ad6e87bd24a0450a20a` |
| TOS402 | `/Users/saschaspringer/Work/F030Comanche/tools/toolchain/tos402.rom` | `b567366bf2a2201bf39d6e0396affac81ffba15a468cb3ad600d41e1112cdeeb` |

## 2. Certification gates

| gate | status | evidence observed | missing evidence / stopping condition |
|---|---|---|---|
| Function provenance and contract audit | **Unproven** | 237 annotated M68k routine headers; 22 browser records; source-header fields complete: PASS; matrix artifact [`build/acceptance/function-audit.json`](../build/acceptance/function-audit.json) | per-routine execution PCs are not mapped to source symbols; JavaScript counterparts are not recorded one-to-one for every reached routine; fixtures/checks are not recorded one-to-one for every reached routine; validated route witness set is **PASS** |
| DOS → JavaScript → 68030/68060 replay | **PASS** | javascript: PASS 284/284; 68030: PASS 284/284; 68060: PASS 284/284; artifact [`build/acceptance/three-way/boundary-comparison.json`](../build/acceptance/three-way/boundary-comparison.json) (`11fc5afd6448ed7520d1fcbc800b3e41bf8f3a6eaced5ba696a3785292306ae8`) | — |
| Complete normalized rendered frames | **DIVERGENCE** | `compare-terrain.py` and [`tools/compare-complete-frame.py`](../tools/compare-complete-frame.py) implement palette/page/window normalization; 66084/76800 pixels; artifact [`build/acceptance/frames/complete-frame-comparison.json`](../build/acceptance/frames/complete-frame-comparison.json) (`6730fdebfdadbf3cfc67b918fc52bb0fa63f5271144a8a1e2d58258d9ca43ee7`) | — |
| Complete supported sequence | **Unproven** | browser witness: 4/4 pass transitions; artifact [`build/acceptance/sequence/browser-sequence.json`](../build/acceptance/sequence/browser-sequence.json) (`0f31306856564e7068f37834e0f3f6841ac40ba3c4346ae12a4c2cbb753d6edb`) | DOS and Falcon all-pass sequence not captured |
| Real stock Falcon and accelerator cache behavior | **Unproven** | Hatari/EmuTOS/Falcon configuration is fingerprinted; CPU arithmetic harness passes | No stock-Falcon performance/memory/input/display/cleanup measurement and no separate cached-vs-published accelerator validation |

The first two component checks below are useful regression checks, but neither can promote the five gates to certified status by itself.

## 3. Component evidence that is currently PASS

### CPU arithmetic

| CPU | result | pairs | exact products | product-stream SHA-256 | harness SHA-256 |
|---:|---|---:|---:|---|---|
| 68030 | **PASS** | 1193 | 4772 | `937041ae93416fedbcada0156326185e874a2557b9c1c7f0057b2645c147872c` | `9f7a31c1b33b2f683b40f2046d3689e2f1c0642167bfde12d64233d8d5c86814` |
| 68060 | **PASS** | 1193 | 4772 | `937041ae93416fedbcada0156326185e874a2557b9c1c7f0057b2645c147872c` | `fef2bfdd88ff847d4a5b85f3cffc0c61602ab22eb4582b161460c3396a689981` |

Both multiply result files are tied to the current `check.tos` hashes and contain the expected 1,193 input pairs / 4,772 exact products.

### Browser and substitution gates

Browser source/provenance gate: **PASS**. It found `6` JavaScript files and `22` browser record anchors. The fresh gate output was:

```
PASS source-audit 6 JavaScript files
PASS DOS image SHA-256 and 640-entry Q31 table
PASS campaign-0 mission/resource families, DTA/SG palettes, DTL and DEMO boundaries
PASS pass-one attract transition, draw-before-replay ordering, SKY2 blue and SKY4 fill
PASS DOS attract active-object factory, projection, draw order and frame-driver ordering
PASS HIGH.DTL projection table and 250x192 DOS terrain traversal
PASS DOS sprite origin and sight-line byte-accumulator arithmetic
PASS shake timer and cropped target presentation continue after impact
```

Generated substitution inventory check: **Unproven** ([`docs/SUBSTITUTIONS.md`](../docs/SUBSTITUTIONS.md)).

### Countdown, replay byte order and CPU-to-CPU frame equality

The timing cases below are separate artifact directories. Each result checks its screen ticks, replay byte order, `publish_screen` checkpoint, debug-program hash and 320×240 RGB565 frame length/hash.

| case | result | screen ticks | frame SHA-256 | debug program SHA-256 | evidence |
|---|---|---|---|---|---|
| 68030 odd opening | **PASS** | `{'2': 480, '3': 600}` | `9d8c571304d6eb9948b3ceaacc0c6f00b65c57ec6031f81d1c9ebcdf22ac9138` | `63008a6907ebd4d42814b204b610e5efddf7e5225e4d362d102b44b7c40838d0` | [`build/acceptance/attract-68030-odd/timing-result.json`](../build/acceptance/attract-68030-odd/timing-result.json); [`build/acceptance/attract-68030-odd/timing-frame.bin`](../build/acceptance/attract-68030-odd/timing-frame.bin) |
| 68060 odd opening | **PASS** | `{'2': 480, '3': 600}` | `9d8c571304d6eb9948b3ceaacc0c6f00b65c57ec6031f81d1c9ebcdf22ac9138` | `cd07d72cbf3dd6b0864b9aa2690976530ae459dae0f6465328862c4b3b6e7d78` | [`build/acceptance/attract-68060-odd/timing-result.json`](../build/acceptance/attract-68060-odd/timing-result.json); [`build/acceptance/attract-68060-odd/timing-frame.bin`](../build/acceptance/attract-68060-odd/timing-frame.bin) |
| 68030 even opening | **PASS** | `{'1': 300}` | `e952470648546124b6be39e1f7697fc626c72b8cef5a361a6ec1337da8dd0474` | `63008a6907ebd4d42814b204b610e5efddf7e5225e4d362d102b44b7c40838d0` | [`build/acceptance/attract-68030-even/timing-result.json`](../build/acceptance/attract-68030-even/timing-result.json); [`build/acceptance/attract-68030-even/timing-frame.bin`](../build/acceptance/attract-68030-even/timing-frame.bin) |
| 68060 even opening | **PASS** | `{'1': 300}` | `e952470648546124b6be39e1f7697fc626c72b8cef5a361a6ec1337da8dd0474` | `cd07d72cbf3dd6b0864b9aa2690976530ae459dae0f6465328862c4b3b6e7d78` | [`build/acceptance/attract-68060-even/timing-result.json`](../build/acceptance/attract-68060-even/timing-result.json); [`build/acceptance/attract-68060-even/timing-frame.bin`](../build/acceptance/attract-68060-even/timing-frame.bin) |

Odd-opening 68030↔68060 frame bytes: **PASS**; frame `9d8c571304d6eb9948b3ceaacc0c6f00b65c57ec6031f81d1c9ebcdf22ac9138`.
Even-opening 68030↔68060 frame bytes: **PASS**; frame `e952470648546124b6be39e1f7697fc626c72b8cef5a361a6ec1337da8dd0474`.

These are target-to-target equality checks. They do not establish DOS pixel fidelity.

## 4. Function provenance and compliance audit

The audit scans every annotated `.s` routine header under `src/` and requires `DOS`, `Record`, `Route`, `Port`, `Preserved`, `Kind` and `Status`; file-level `Route`/`Record` declarations are inherited by routines in that source file, and a routine-local declaration overrides them. `DOS: N/A` is accepted only as an explicit target/platform replacement. It also requires an address-like canonical DOS ID for non-target entries.

M68k headers discovered: `237`. Headers with at least one missing required field or canonical ID: `0`. Missing `Record:`: `0`. Missing canonical DOS ID: `0`.
The route witness set is **present and content-valid**. Until it is valid, this remains a conservative source-wide scan; it does not pretend to know that an unlisted helper was unreached.

No missing M68k header fields were found.

Browser record anchors: `22` headings; JS references `22` distinct anchors across `6` files. This proves annotation coverage for the browser slice, not one-to-one reached-function coverage for M68k. The static scan cannot infer a JavaScript counterpart or fixture for every M68k row; those columns remain **Unproven** outside the representative matrix.

### Representative boundary matrix

This is the shape required for the exhaustive matrix; it is intentionally labelled representative because the gate remains **Unproven** until every reached helper is row-complete.

| canonical DOS ID | recovered contract | JavaScript counterpart | M68k counterpart | fixtures / checks |
|---|---|---|---|---|
| `FUN_00005690` | attract state, authored transition | `AttractRuntime.enterNextPass / advanceScreen` | `attract_tick / attract_next_pass` | browser gate; timing-result.json |
| `FUN_00018C29 / FUN_00019A2D` | DEMO header and per-record replay boundary | `AttractRuntime.enterDemo / advanceDemoInput` | `demo_start / demo_tick` | flight-demo1.json; flight-dos.json |
| `FUN_00018F94` | flight integration from replay axes | `AttractRuntime.flightTick` | `flight_tick` | flight-demo1.json; flight-dos.json |
| `FUN_0000D3C0` | frame ordering and publication boundary | `AttractRuntime.advanceAuthoritativeTick` | `frame_driver` | timing-frame.bin; browser trace |
| `FUN_0000D950` | HIGH.DTL terrain ring walk | `AttractRuntime.drawTerrainStage / drawTerrain` | `render_terrain_ring` | compare-marcher.py; flight traces |
| `FUN_000234A4` | descending object update/state dispatch | `AttractRuntime.updateObjectPass / updateObjectState` | `object_update_pass` | browser object-pass proof |
| `FUN_00024B17` | object transform, ordering and draw | `AttractRuntime.objectTransform / objectDraw` | `object_draw_pass` | browser object-pass proof |
| `FUN_00025880` | planar sprite and cockpit composition | `drawOpaqueSprite / AttractRuntime.drawConsole` | `sprite_draw / sprite_blit` | browser composition proof |
| `FUN_0002B820` | palette remap and RGB565 conversion boundary | `nearestPaletteMap / buildPaletteLookup` | `resource_palette_remap` | browser palette proof; compare-terrain.py |

Route witness contents are checked, not just their filenames. A range report must show positive execution counts for the attract/frame/replay/flight/terrain/object/composition families; the object snapshot must show the traced state and draw targets.

| route witness | status | size | SHA-256 | missing requirements |
|---|---|---:|---|---|
| `work/qemu_out/attract-trace-report.txt` | **PASS** | 5695 | `0a86705bcc5b881d9d0c1e5f019bae3a949d38ff5280b8e272bd27c8ff6aaed0` | — |
| `work/qemu_out/object-state-walk.txt` | **PASS** | 10751 | `855c142ba8c872f5378f5fb21c68fa9ae22035b541b251b25da1b2efce8623d4` | — |

Validated route witness set: **PASS**. The generated reached-function matrix is [`build/acceptance/function-audit.json`](../build/acceptance/function-audit.json): **Unproven**. The source-header scan is a prerequisite only; it cannot infer a JavaScript counterpart or fixture for a reached helper without this matrix.

## 5. Three-way replay boundary

Existing DOS fixture records: [`work/replay_dos/flight-demo1.json`](../work/replay_dos/flight-demo1.json), [`work/replay_dos/flight-dos.json`](../work/replay_dos/flight-dos.json), [`work/replay_dos/view-demo1.json`](../work/replay_dos/view-demo1.json) and [`work/replay_dos/replay-passes.json`](../work/replay_dos/replay-passes.json). Existing tools include [`tools/certify-replay-flight.py`](../tools/certify-replay-flight.py) and [`tools/compare-marcher.py`](../tools/compare-marcher.py).

| fixture | rows/replays | DOS breakpoint | SHA-256 |
|---|---:|---:|---|
| `work/replay_dos/flight-demo1.json` | 790 | 103765 | `ad6b203af23c80ef0c04e2a11769ee71740d4c128dca3e64e10312615754494c` |
| `work/replay_dos/flight-dos.json` | 800 | 103765 | `9ec94ea5d44b2e0c693655d2426f7fbd4c1c87e751a2ac5d957deb4a9c3229a3` |
| `work/replay_dos/view-demo1.json` | 500 | 32127 | `7efe2928367f2b73bb5ff744cd7fb42589ef9d4401deb740c507c529a10fb5dd` |
| `work/replay_dos/replay-passes.json` | 4 | — | `7c9ecd7b442a90ecc9a4e2b4e9a9504d5f9b9c00ca32c9c30fcf4152805a6a5a` |

Boundary comparison command output: **PASS**.

```
PASS: DOS/JavaScript/68030/68060 boundary comparison; output /Users/saschaspringer/Work/F030Comanche/build/acceptance/three-way/boundary-comparison.json
  javascript: PASS 284/284
  68030: PASS 284/284
  68060: PASS 284/284
```

The comparison joins the same DEMO1.SCR byte cursor and checks raw DOS 10.22 position, angle, altitude, turn, forward/lateral velocity, roll and pitch at each flight-publish row. The browser trace also carries the exact input bytes and framebuffer hash for each tick.

The supported DEMO1 range is the first 284 records. Record index 284 is the no-damage bounce at 00019461 that arms the screen shake; from the next timer tick DOS pans its display through 00001DF1 and 00015BBC, which the cross-machine target has not recovered. The parity comparison therefore stops the armed presentation there, while the browser-only witness continues with its documented crop adaptation. Rows past the bounce are outside the cross-machine scope; they are not evidence of divergence. The flight arithmetic beyond it was measured separately at the DOS breakpoint by `work/trace_replay_flight.py` (see `docs/PORTING-PLAN.md`).

**First divergence:**

- `javascript`: none across `284` rows
- `68030`: none across `284` rows
- `68060`: none across `284` rows

The required future trace row is: replay/pass ID, tick, canonical DOS function ID, input bytes, pre-state, post-state, return/output words, target CPU and surface/page publication hash. The checker must stop at the first unequal row rather than summarize only aggregate agreement.

## 6. Complete-frame normalization

The available comparator is [`tools/compare-terrain.py`](../tools/compare-terrain.py). It documents the DOS 8-bit PCX surface, 328-pixel source page/window and the port's left 320-pixel view. Its palette normalization is the documented RGB565 conversion: `((R >> 3) << 11) | ((G >> 2) << 5) | (B >> 3)`.

Normalizer implementation present: **PASS**. Retained valid 328×240 DOS PCX candidates: `1088` (`1085` with a palette block) across `18` ignored build directories.

Candidate groups (inventory only; not accepted as paired parity evidence):

- `build/demo0`: `309` files
- `build/frame-pair/dos-r19`: `1` files
- `build/frame-pair/dos-r20`: `1` files
- `build/frame-pair/dos-r20b`: `1` files
- `build/frame-pair/dos-r21`: `1` files
- `build/frame-pair/dos-r245`: `1` files
- `build/oracle`: `258` files
- `build/oracle-cdrive`: `13` files
- `build/oracle-natural`: `13` files
- `build/oracle-now`: `13` files
- `build/oracle-tilt`: `48` files
- `build/oracle2`: `245` files
- `build/pinned`: `47` files
- `build/pinned2`: `40` files
- `build/pinned3`: `40` files
- `build/qemu-oracle`: `3` files
- `build/sky-oracle`: `39` files
- `build/verify-default`: `15` files
- sample: [`build/oracle-tilt/SNAP_001.PCX`](../build/oracle-tilt/SNAP_001.PCX); `eeeabcca5982328335bad2d7c4ed395ba87587bf42d01a0aa7a5a5f0f4bf7057`

The page/pan-aware acceptance artifact is [`build/acceptance/frames/complete-frame-comparison.json`](../build/acceptance/frames/complete-frame-comparison.json): **DIVERGENCE**.

The complete-frame gate requires one 320×240 RGB565 target dump and one DOS 328×240 PCX from the same replay tick and camera, with page and pan metadata recorded on both sides. It compares every terrain, object, cockpit, MFD and HUD pixel after the documented six-bit palette conversion; an absent pair remains **Unproven**.

## 7. Complete supported sequence

The recorded pass map is:

| pass index | key | replay | resources |
|---:|---:|---|---|
| 0 | `1` | `demo1.scr` | `Np44.dta, d4.dta, c4.dta, sky4.rle` |
| 1 | `2` | `demo2.scr` | `p34.dta, d3.dta, c3.dta, sky4.rle` |
| 2 | `3` | `demo3.scr` | `p23.dta, d2.dta, c2.dta, sky3.rle` |
| 3 | `0` | `demo0.scr` | `p12.dta, d1.dta, c1.dta, sky2.rle` |

The deterministic browser sequence witness is [`build/acceptance/sequence/browser-sequence.json`](../build/acceptance/sequence/browser-sequence.json): **PASS**.
It observed `[{'cycle': 0, 'pass': 1, 'demoIndex': 1, 'records': 777, 'traced': 777}, {'cycle': 1, 'pass': 2, 'demoIndex': 2, 'records': 676, 'traced': 676}, {'cycle': 2, 'pass': 3, 'demoIndex': 3, 'records': 908, 'traced': 908}, {'cycle': 3, 'pass': 0, 'demoIndex': 0, 'records': 774, 'traced': 774}]`, `8` transition events, `15` replay command keys, and `5899` frame hashes while checking terrain-buffer identity.

The certification gate remains **Unproven** unless the same transition/camera/replay/buffer assertions are captured for DOS and both Falcon CPU builds. The current browser witness does exercise external-camera selectors, but it is not a substitute for paired DOS and current-hash Falcon captures.

## 8. Real-target and cache validation

The recorded target environment is Hatari Falcon mode with 14 MB, DSP off, EmuTOS/TOS assets and the local vasm/vlink toolchain. That is a useful emulator regression environment, not a stock-Falcon measurement.

Still **Unproven**:

- stock 68030 frame time, memory headroom and input latency;
- Videl display/page behavior and cleanup across repeated attract transitions;
- accelerator cache-on/cache-off behavior, cache publication ordering and performance separately from numerical equality.

## 9. Repeatable procedure

Build the desired debug images, then run these serially so each artifact has a stable directory. The two Hatari replay captures are intentionally explicit: the 68060 interpreter may take several minutes.

```sh
TARGET_CPU=68030 OUTDIR=release bash tools/build-run.sh
TARGET_CPU=68060 OUTDIR=release/68060 bash tools/build-run.sh
python3 tools/check-cpu-compatibility.py
python3 tools/check-attract-timing.py --cpu 68030 --artifact-dir build/acceptance/attract-68030-odd
python3 tools/check-attract-timing.py --cpu 68060 --artifact-dir build/acceptance/attract-68060-odd
python3 tools/check-attract-timing.py --cpu 68030 --even-pass --artifact-dir build/acceptance/attract-68030-even
python3 tools/check-attract-timing.py --cpu 68060 --even-pass --artifact-dir build/acceptance/attract-68060-even
node tools/prove-browser-attract.js
python3 tools/audit-function-matrix.py --out build/acceptance/function-audit.json || true
node tools/trace-browser-replay.js --pass 1 --records 284 --out build/acceptance/three-way/browser-demo1.json
python3 tools/trace-falcon-replay.py --cpu 68030 --records 284 --run-vbls 50000 --out build/acceptance/three-way/falcon-68030/falcon-68030.json
python3 tools/trace-falcon-replay.py --cpu 68060 --records 284 --run-vbls 270000 --timeout 2400 --out build/acceptance/three-way/falcon-68060/falcon-68060.json
python3 tools/compare-boundary-traces.py --records 284
node tools/trace-browser-sequence.js build/acceptance/sequence/browser-sequence.json || true
python3 tools/acceptance-report.py
```

The final command is expected to return 1 for this snapshot. That failure is the acceptance signal that the report still contains **Unproven** gates, not a hidden overall PASS.

## 10. Evidence references

- DOS route and contract record: [`analysis/functions/falcon-attract.md`](../analysis/functions/falcon-attract.md)
- Browser function records and fixture boundary: [`analysis/functions/browser-attract.md`](../analysis/functions/browser-attract.md)
- DOS oracle capture and palette/page normalization notes: [`docs/DOS-ORACLE.md`](../docs/DOS-ORACLE.md)
- CPU arithmetic distinction and target notes: [`analysis/functions/cpu-compatibility.md`](../analysis/functions/cpu-compatibility.md)
- Build/run procedure: [`tools/README.md`](../tools/README.md)

