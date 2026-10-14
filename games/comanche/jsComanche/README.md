# JavaScript DOS attract reference

This directory contains the connected browser slice for the recovered
Comanche DOS attract path. It loads campaign `0` missions 0 through 3, installs
the matching authored terrain/sky family before each `DEMO0.SCR` through
`DEMO3.SCR` replay, and uses the shared opening pages from the installed DOS
asset tree.

Run a repository-root server and open `/F030Comanche/jsComanche/`:

```text
python3 -m http.server 8765 --directory C:\Arbeit
```

Run the deterministic proof gate from the repository root:

```text
node tools/prove-browser-attract.js
```

With the retained instruction-bound DOS terrain capture available, also run:

```text
node tools/prove-browser-attract.js --dos-marcher work/qemu_out/marcher-6.json
```

This compares the production marcher against captured non-uniform DOS ring
horizons, excluding the archive columns shared with the rear view. Terrain
camera, increments and map sampling retain raw 10.22 coordinates throughout.

It audits every JavaScript definition for an adjacent DOS record or explicit
target marker, compares the generated Q31 table with the hashed DOS image,
checks the four authored mission/resource families and palette boundaries,
verifies the independent HIGH.DTL projection table and complete 250x192 DOS
terrain traversal, and exercises the pass-one replay transition with a mocked
Canvas.

## Route-first source rule

This JavaScript slice is generated from a traced DOS milestone route. Before a
source function is added or changed, run the authoritative image in QEMU with
the TCG `exec,nochain` execution extension, repeatable inputs, execution
telemetry, and state/memory snapshots; record the
reached DOS entries, indirect callbacks, resource pointers, state transitions,
and frame order. Link the resulting JavaScript function and its future M68k
counterpart to that route record and the durable function record. Unreached or
unexplained code stays dormant/`Unproven`; this browser can validate the DOS
route but cannot invent or define it.

The current route evidence is collected by
`work/run_qemu_exec_trace.py`, `work/trace_attract_report.py`, and
`work/inspect_qemu_state.py`, with reports under `work/qemu_out/`.

The page contains only a 320×240 canvas. It has no mission selector, pause or
restart control, browser keyboard path, persisted file cache, diagnostic
panel, or invented fallback state. Missing or malformed original data stops
the host import boundary.

The runtime preserves the recovered DOS contracts for the supported slice:

- draw-before-tick attract screen transitions and the exact ZOVE/COMA tables;
- the 328×240/328×390 authored pages and 150-row title pan;
- the four fixed replay record streams and their signed 32-bit/16-bit fields;
- 512×150 column-major sky strips, HIGH.DTL projection, Q31 movement, and
  ring-major 192-column terrain occlusion;
- the persistent terrain-only render surface, console, fixed instruments,
  authored HUD, and DOS sight-line walk; and
- the recovered left moving-map MFD and right target-view terrain body, with
  the browser continuity map used before a replay target span is available;
- the recovered palette remap and RGB565 browser-surface adaptation;
- the QEMU-traced replay callback table, transient 130-slot allocator,
  projectile/guidance states, BOOM/BULL/CHAF effects, and destruction handoff.

The browser clock is a labelled 60 Hz fixture cadence only. DOS timer/VBL
cadence is not inferred from `requestAnimationFrame`. Deterministic checks may
use `ComancheRuntime.create(...).advanceTicks(count)` outside the connected
page. The durable function records are in
`analysis/functions/browser-attract.md`.

The connected page follows all four authored attract passes. DOS camera keys
6 and 7 intentionally suppress the cockpit during their chase/fixed-ground
segments; the replay returns to cockpit view when the authored key selects
variant 1 again. Impact shake uses the recovered phase displacement on the
browser's 320×240 crop so the mission continues; exact 328-wide VGA page
parity remains unproven.

Live keyboard input, sound, mission completion, the real menu handoff,
phase-gated frame tails, and Falcon 68030 code remain out of scope.

Beside the attract runtime, four modules carry the routines the Falcon ports of
2026-10-07 implement, as pure functions over explicit state (no DOM, clock or
random source), each transcribed from the DOS listing with the DOS address on the
step: `dos-pilot.js` (mission-end statistics, the pilot record, the ranking sort
and the roster layout), `dos-menu.js` (mission list scan, row colours and lock,
the briefing wrap, Your Stats, the options Game column and the new-pilot name
entry), `dos-damage.js` (the player's death and damage chain) and the data module
`dos-text-data.js`. `flightTick` enters the damage chain; the menu and pilot
modules are not attached to the page, which has no menus. Their records are
`#mission-end-statistics` through `#menu-text-data` in
`analysis/functions/browser-attract.md`; the gate also runs
`tools/prove-browser-menus.js` and, with the DOS captures present,
`tools/check-js-damage.js` (the damage chain against the original flown with
poked damage state) and `tools/check-js-dos-calls.js` (the pure routines against
the original called directly on random inputs, `work/dos_call.py`).

`dos-sound.js` (the DOS sound driver: MS3 music and FM effects as OPL2, MPU-401 and PC speaker
writes, and the digital effect mixer's fill) is not attached to the page either: the browser stays
silent. Its record is `#sound-driver-module` and its siblings, the specification is
`analysis/functions/sound-driver.md`, and `node tools/check-js-sound.js` replays the captures of
`work/trace_sound_writes.py` (the original driven through the same calls) and compares every write,
every returned value, the driver's variables and the mixed bytes. `node tools/export-sound-trace.js
OPENMUS.MS3 --out build/openmus.ev` plays a song through it and writes the OPL2 writes in the
trace format of `../F030OPL2`.
