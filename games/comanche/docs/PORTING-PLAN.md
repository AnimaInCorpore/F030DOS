# DOS-to-Falcon porting plan

## Native correction verified from DOS (2026-10-10)

Native checks now cover debrief arithmetic and object collisions.
`debrief_number` now uses unsigned 32-bit quotient/remainder division because
DOS clears the high dividend (`00028C2D`); the former 64-bit instruction did
not complete on the 68060. Both CPUs and JavaScript match 80 fresh DOS number
cases and 80 percentage cases, including output margins and score counters
(`tools/check-falcon-debrief.py`). The already implemented object collision
block matches all 37 fresh DOS box/altitude boundary decisions on both CPUs
(`tools/check-falcon-collision.py`); its older missing-source note is stale.
These checks establish function contracts, not complete playable-route or
graphics acceptance. Reproduction and limits are recorded under
`mission-end-statistics` and `player-damage-chain` in the browser function record.

`FUN_00029F36`'s shared native row exchange had rounded the ten-byte campaign
progress/completion rows down to eight bytes. DOS swaps their trailing word
too (`00029F84-00029FEF`), while its 43-byte name stride deliberately exchanges
only 40 bytes (`0002A072`). Exchange size and stride are now separate.
The rank refresh uses a native unsigned 32-bit quotient/remainder division,
matching DOS's zero-high dividend and avoiding the 64-bit divide on 68060.
Fresh DOS captures and JavaScript agree on 41 rosters; the native harness is
`python3 tools/check-falcon-roster.py`. Its negative control fails the old
source on case 1, byte 400. See the correction under
[`roster-ranking`](../analysis/functions/browser-attract.md#native-roster-correction-2026-10-10).
Full playable-game and graphics-fidelity acceptance remain incomplete.

This is the priority roadmap for F030Comanche. The hashed shipped DOS binary
and its captured execution are the behavioural authority. The first Falcon
source slice has now been recreated from the DOS attract route; its durable
source-selection record is `../analysis/functions/falcon-attract.md`. The
active validation milestone is the DOS attract cycle, beginning with its
authored opening resources and replay-driven terrain flight. The browser and
Falcon CPU paths exercise that route; DSP acceleration is a later
optimization workstream governed by `../PORTING.md`; it must not get ahead of
recovering and validating the game itself.

## The 68060 image made playable (2026-10-14)

The full route - menus, briefing, live flight, damage, debrief - runs on the
accelerator image in Hatari's 060/TT-RAM profile. The image now loads into
TT-RAM, and the marcher, target view, map MFD, sky fill, depth sort and wide
products do the same work in fewer instructions with byte-identical buffers:
live cockpit flight went from about 17 to 21 fps there, the attract cockpit
benchmark from 7.9 to 18.75. The target-view silhouette archive's stride and
sign-extension bug (it wrote into the persistent console page) is fixed. The
68030 image runs the same source, 1.78 -> 2.14 fps in the cockpit. Emulator
figures only. See [PERFORMANCE-2026-10-14-68060.md](PERFORMANCE-2026-10-14-68060.md).

## Current status — reviewed 2026-10-10

The CPU attract route remains the acceptance baseline, with native menu/live
command/weapon/damage/mission-end extensions and matching JavaScript function
contracts added since its recreation. The digital effect mixer is implemented
and checked separately; music/FM and real-hardware audio remain open
([sound-falcon.md](../analysis/functions/sound-falcon.md)). DSP remains dormant.

Overall acceptance is **NOT CERTIFIED**. Complete implementation provenance,
frames/sequences, live keyboard/cadence and real stock/accelerator validation
remain incomplete. The browser is not a general playable-mission runtime.
The generated [acceptance report](ACCEPTANCE-REPORT.md) is a hash-bound
2026-09-22 snapshot. Current cached native replay traces are stale under the
shared comparison tool; missing/stale evidence remains Unproven. This status
review does not refresh those captures. The dated findings below own individual
contracts and corrections; isolated passes do not close the connected game route.

## Priority rule

The [function-level porting specification](FUNCTION-PORTING.md) defines the
unit of work, numeric/endian contracts, adjacent provenance comments, CPU
boundaries, and verification order. Its requirements apply to each reached
function; existing annotation coverage does not establish compliance. The
next attract acceptance milestone is complete DOS/Falcon frame comparison at
matching replay and publication boundaries, beginning with cockpit and
fixed-camera frames. Selected replay-state equality is component evidence.

The baseline remains a 16 MHz MC68030 Falcon with 14 MB ST-RAM. The optional
MC68060 build changes arithmetic and platform mechanisms only; it must pass the
same DOS numerical contracts. See the [CPU compatibility record](../analysis/functions/cpu-compatibility.md)
for exact wide multiplication, vector/cache handling and validation scope.
This work does not change the priority of completing the DOS-derived game route
or make DSP support a dependency of the current CPU milestone.

Work should be selected in this order:

1. choose the next playable or attract vertical slice and trace its actual DOS
   route with repeatable inputs;
2. enumerate every reached function, indirect callback, resource read, state
   transition, and frame-order boundary in a route record;
3. record the recovered x86 routine, data, and resource contracts for that
   route;
4. build or extend the deterministic JavaScript reference from those traced
   contracts and confirm its function-level hypotheses against DOS;
5. create and verify the matching 68030/M68k sources from the same route and
   function records;
6. integrate the slice on the Falcon CPU reference path; and
7. optimize only code proven to be a frame-time bottleneck.

A higher disassembly coverage percentage, an isolated DSP kernel, or a faster
approximate renderer does not take priority over an end-to-end behaviour gap.
Do not wait for a perfect disassembly of the whole executable either: recover,
port, and compare one complete subsystem at a time.

### Route-first source rule

No JavaScript or M68k source is created for a milestone until the milestone's
authoritative DOS route has been traced. The route trace must use QEMU's TCG
`exec,nochain` execution extension (or the documented equivalent for a later target), a
repeatable input schedule, and state/memory snapshots sufficient to resolve
indirect calls, resource pointers, callback tables, and per-frame ordering.
The durable route record names the trace command, DOS image hash, reached
addresses, data/resource witnesses, and the JavaScript/M68k symbols generated
from each contract. A source outside that route is `dormant`/`Unproven` and is
not part of the milestone; a browser or Falcon experiment can validate the
route but cannot promote an untraced guess into source.

## Faithful DOS-source rule

Port the behaviour of the hashed DOS binary, not the disassembly text. The
recovered disassembly, decoded data/resources, browser implementation and
observed call/state contracts are graded evidence; captured execution resolves
what the DOS program does. Falcon code may reorganize registers, memory, and
platform interfaces, but it must preserve the DOS mechanic and observable
sequencing. Do not replace an unrecovered or inconvenient mechanic with a
plausible approximation, synthetic data, or a new build option; recover more
evidence, or leave that path stopped or dormant until it can be ported
faithfully. Every difference must be justified by a genuine Falcon platform
boundary and recorded in the function's ledger against the DOS contract.

## Current baseline

The executable preparation and address model are established:

- the authoritative `re/unpacked/COMANCHE.UNPACKED.EXE` source image is
  SHA-256 `4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697`;

- `OVERKILL.EXE` is only the installer payload wrapper;
- the installed `COMANCHE.EXE` must be unpacked from LZEXE 0.91 before use;
- the real game is the 207,648-byte 32-bit flat content region based at image
  offset `0x1700`;
- flat offset `0x1538` is the game entry point;
- the current recursive flat pass reaches 33,614 instructions and 120,430
  bytes, 58.0% of the content region, measured with the annotation store used
  as a data barrier so that tables are not counted as code. Nothing is left
  over: 120,514 bytes are decoded, 69,750 more are identified as data by a row,
  17,384 are padding, and no byte is neither - including no byte inside a
  routine that the walk fails to decode. The annotation ledger classifies
  99.96% of the material bytes, with 45 left, an artifact of counting filler
  both globally and per row; those two measure different things -
  the pass measures what recursive descent reaches, the ledger what has been
  identified, including data the pass will never walk into.

The previous scaffold was removed on 2026-08-25. Current `src/` implements
the recreated CPU attract slice described above; the historical removal is
not the current implementation state. Unrecovered live-game paths remain
outside this milestone. Shake timer arithmetic now has captured DOS fixtures;
complete display-shake presentation remains stopped pending full-page/panning
recovery (`analysis/functions/browser-attract.md#shake-timer`).

## First recreation milestone: DOS attract cycle

The first Falcon/browser implementation milestone is the attract cycle because
it supplies a deterministic authored camera path without inventing live input
or mission state. The browser slice is now implemented in `jsComanche/`: it
loads campaign 0's authored mission resource family for each attract pass,
renders the authored opening pages, plays the exact screen-bank animation and
pan schedule, then replays
`DEMO<n>.SCR` through the recovered terrain/sky and flight contracts. It draws
the current state before advancing one authored tick, matching the DOS frame
driver's ordering. The browser admits at most one logical tick per presented
frame, so a slow render cannot accelerate the replay through catch-up ticks.
Its nominal 60 Hz clock remains a labelled fixture upper bound, not recovered
DOS timing; ordered traces record replay bytes, events, state checkpoints, and
logical framebuffer hashes.

The browser surface is an explicit platform adaptation: DOS's 328-wide Mode X
page is represented by the left 320 columns on a 320×240 RGB565-equivalent
surface, and the decoded screen/bank pixels are presented with Canvas nearest-
neighbour scaling. The adaptation does not change source bytes, fixed-point
arithmetic, ring-major terrain order, palette matching, replay timing, or the
post-terrain frame composition contract.

The slice remains smaller than the first playable mission. It deliberately
leaves live flight input, sound, mission completion and the real menu handoff
dormant. The replay-driven weapon/effect children are included in the attract
slice because QEMU reaches their callback and state handlers. The fixed `CONSOL1S.DTA` console,
the three recovered opaque `CONS.RLE` elements, and the authored `HUDS.RLE`
compass/speed/clearance/reticle path are active because the DOS frame reaches
them. The phase-gated `0000D88C` COMA tail and null-gated variant tables remain
dormant in attract phase 1. The recovered DOS keyboard path is Unproven, so
the browser does not attach DOM keys to state. The connected page contains
only the canvas: there is no mission selector, pause/restart control,
persisted file cache, or diagnostic panel. The attract replay uses campaign
0 mission `n` with `DEMO<n>.SCR` on pass `n`; it does not synthesize a camera
path when a fixture is absent. The complete
browser function records are in
[`analysis/functions/browser-attract.md`](../analysis/functions/browser-attract.md).

The milestone exit gate is route-first and structural: the QEMU route manifest
comes first and names the reached DOS functions, callbacks, resource reads,
state transitions, and frame order; every displayed byte or field then comes
from an installed DOS file, malformed/truncated input stops the load, the
decoded record counts and boundaries are reported, and the browser symbols are
linked to the DOS map rows and fixtures. Browser output is a checked recreation
slice, not a DOS frame-parity claim or proof that the Falcon implementation
source is complete. Resource geometry follows the loader's decoded payload
boundary rather than a display-mode field or allocation capacity; the confirmed
`CONSOL1S.DTA` case is recorded in
[`ASSET-INVENTORY.md`](ASSET-INVENTORY.md).

## Browser milestone boundary discovered and shared

The implementation confirmed the following facts at the cross-port boundary:

- `SKY<n>.RLE` is an SG special case containing 512 column-major strips of
  150 bytes, not a 320×240 raster; the source strip origin is derived from the
  full 32-bit view angle and the visible terrain columns consume the centred
  192-strip window.
- DTA palettes carry 8-bit components representing six-bit DAC values shifted
  left by two, while SG bank palettes are six-bit. Bank pixels must be matched
  into the active mission palette with the recovered gamma/weighted metric
  before RGB565 composition.
- The opening sequence is a 328×240 authored page boundary with a 150-row
  TPIC pan; the overlay anchor is bottom-left and the animation tick follows
  the draw. These are shared contracts for any browser, Falcon CPU, or future
  DSP composition path.
- `CONSOL1S.DTA` decodes to 328×290 bytes with source row zero at the visible
  frame's row zero; index `255` is transparent while index `0` is ordinary
  console ink. `CONS.RLE` is the planar-bottom-first bank for fixed elements
  `0x09 @ (0x10,0xEA)`, `0x25 @ (0x0C,0xC9)`, and `0x39 @ (0x110,0xCB)`.
- `HUDS.RLE` is a separate column-major, bottom-first bank. Its authored
  overlay uses element `1` for the 64-column compass window, `2` for the
  marker, `0x15` for `SPEED`, `4` for the clearance ladder, digits `0x16`–`0x1F`,
  and `0x21` for the velocity reticle. The sight line is the DOS
  `00025CA2` shallow/steep integer walk in fixed green `0x47E8`; it is not a
  fabricated cockpit primitive.

The local runnable proof is documented in
[`jsComanche/README.md`](../jsComanche/README.md).

## The translation target: a semantic twin

The 68030 source must match the observable behaviour of the DOS program, not
its instruction sequence. Register allocation, stack layout, memory ownership,
and platform calls should be native to the Falcon. Preserve the contracts that
can affect results:

- integer width, signedness, truncation, carry, and overflow behaviour;
- fixed-point formats, rounding direction, and intermediate precision;
- structure sizes, table indexing, sentinel values, and state transitions;
- file read order and decoded resource records where order is significant;
- update order, timer units, input edges, and renderer inputs;
- visible clipping, palette, projection, sprite ordering, and HUD results.

Replace the DOS extender, XMS/VCPI management, segment setup, VGA access,
interrupt installation, and DOS allocator with small Falcon interfaces. They
are runtime mechanisms, not game semantics.

Source generation follows the traced milestone route: create the JavaScript
counterpart and the M68k counterpart only for DOS entries, callbacks, data
contracts, and resource reads reached by that route. Keep the route manifest,
function records, and implementation symbols linked; do not generate a broad
scaffold and call its untraced branches part of the milestone.

Each recovered or ported function belongs in
[`X86-M68K-MAP.md`](X86-M68K-MAP.md), which is the index rather than the whole
record. Each function also needs the durable `METHOD.md` §4.2 record: DOS image
hash and canonical range, evidence/observation, recovered purpose and full
contract, DOS fixtures, browser and Falcon symbols, and a difference ledger
against DOS. State and prove even “no difference”; unresolved differences are
`Unproven`. A 68030 source comment may link to the record but cannot replace it.
The deterministic browser reference is mandatory from the first function, but
the DOS route trace comes before source generation. Use browser experiments to
exercise and compare the traced role, inputs, side effects and Falcon seam;
confirm the result against the route witness before recording it. Its fixtures
land before or with the Falcon half of every supported slice.
Helpers inherit the parent DOS address only when the record says that
explicitly; Falcon/TOS platform replacements use `N/A - platform replacement`.
A ported function may combine or split DOS routines when the record explains
that decision, but no function may hide a guessed mechanic behind a generic
file comment.

## Phases and exit gates

| Phase | Work | Exit gate |
|---|---|---|
| 0. Reproducible reference | Preserve hashes, unpacking steps, binary boundaries, seeds, and separate bootstrap/flat listings. | A clean local extraction reproduces the measured executable layout and listings. |
| 1. Structural recovery | Resolve indirect control flow and classify startup, main-loop, file, timer, input, renderer, mission, object, UI, sound, and network regions. | Every routine exercised by startup and the selected first mission is named or classified with evidence. |
| 2. Dynamic oracle | Trace the original after its protected-mode handoff. Record file operations, decoded records, call order, state snapshots, fixed-point values, renderer inputs, indirect targets, and frame order under repeatable actions. | A durable route manifest names the reached DOS functions/data/resources and can replay startup, menu selection, mission load, and several scripted frames. |
| 3. Falcon boundaries | Define small interfaces for memory, files, timing, input, video, diagnostics, sound, and networking. | Game-side modules contain no direct DOS, extender, or PC hardware dependency. |
| 4. Browser-backed, address-mapped 68030 port | Generate the JavaScript and M68k sources from the traced route, then port leaf routines and subsystem coordinators while keeping the x86-to-68k map, route manifest, and difference ledger current. | Each supported function has DOS → browser fixtures, browser → target checks, and a route witness; each completed subsystem passes its decoder, state, or frame comparison before integration. |
| 5. First playable mission (deferred) | Integrate missions, flight state, terrain and objects, weapons, collisions, HUD, menus, and completion/failure paths on the CPU renderer only after their DOS contracts and fixtures are recovered. | One mission can be started, played, won or lost, and restarted without sound; this is not the current browser milestone. |
| 6. Rendering fidelity | Recover the original palette, projection/detail constants, terrain traversal, clipping, sprite composition, and presentation timing. | Fixed cameras and scripted sequences match golden state and image evidence within documented platform differences. |
| 7. Measured DSP acceleration | Profile the correct CPU build and move only regular terrain hot paths to the DSP. Keep the CPU oracle and fallback. | DSP output matches the CPU path and improves measured frame time on the target hardware profile. |
| 8. Deferred systems | Add sound and music after the silent game is stable. Networking remains outside the initial scope. | Audio does not change core game-state behaviour or become a required asset for silent mode. |

## Reverse-engineering workstream

Use `RE-WORKFLOW.md` as the executable procedure. The productive order is:

1. follow the call graph from flat entry `0x1538` through initialization;
2. resolve the remaining indirect calls and jump tables when their targets can
   be proved statically or observed dynamically;
3. identify the DOS file, memory, timer, keyboard, and video wrappers;
4. find the outer main-loop and mode/state dispatch;
5. trace the files and routines used to enter the first mission;
6. recover data layouts beside the code that consumes them;
7. trace the complete route for the selected milestone, including indirect
   targets and frame-order boundaries;
8. capture stable inputs and outputs for each subsystem before generating its
   JavaScript and M68k sources.

Do not chase coverage through ambiguous bytes. Known tables must be guarded as
data, and every new seed must include its evidence. Generated complete listings
remain ignored; durable addresses, names, contracts, and confidence belong in
the mapping document and appropriate format documentation.

Static and dynamic analysis have different jobs. Static analysis establishes
control flow, constants, table shape, global references, and candidate data
structures. A 32-bit-aware debugger establishes computed targets, runtime
patching, file-read chronology, decoded records, timing behaviour, and the
state passed between large subsystems.

## 68030 implementation order

Port vertical slices rather than translating the 207,648-byte content region
from beginning to end:

1. trace the milestone route and publish its DOS entry/data/resource manifest;
2. platform-independent file and memory contracts used by game resources;
3. first-mission resource selection and decoding;
4. outer mode loop, timing, and stable input snapshot;
5. mission initialization and helicopter state;
6. terrain/camera inputs and CPU rendering parity;
7. objects, sprites, weapons, collisions, and mission rules;
8. cockpit/HUD, menus, completion, failure, and restart;
9. only then measured renderer acceleration.

Prefer clear 68030 assembly organized by subsystem over a mechanical x86
translation. In particular, audit little-endian file fields, unaligned x86
loads, implicit x86 flag use, partial-register writes, and sign extension at
every translated boundary.

## Silent sound boundary

Sound calls should be preserved behind an interface so game code does not need
another structural rewrite later. The silent implementation should provide at
least initialization, play, stop, update, completion/status, and shutdown
operations. It must:

- return deterministic success or a documented unavailable status;
- allocate stable logical channel or effect identifiers if callers retain
  them;
- report an effect as complete when game logic waits for completion;
- avoid opening sound/music assets or programming Falcon audio hardware;
- contain no timing side effect on simulation, mission, or UI state.

If analysis proves that a sound call controls gameplay timing or a state
transition, reproduce that logical contract independently of audio playback.
Network entry points should be omitted from the first loop or return an
explicit local-only result.

**Phase 8 recovery (2026-10-07).** The sound driver and its call interface are
recovered and checked against the running original: `analysis/functions/sound-driver.md`
(formats, devices, all 80 call sites, the 68030 interface), the JavaScript reference
`jsComanche/dos-sound.js` and `node tools/check-js-sound.js`. What it establishes for the
boundary above: the only game logic that reads a sound result is two screen lengths
(the fanfare loop `0000587D`, 480 frames, and the title loop `00005ACC`, 600 frames, which end early
when command `0x6000` returns 0 - the song has finished); everything else is fire and forget.
A silent implementation must return a fixed answer to that query, and the choice is a decision
about those two durations, not about sound. The audio target is the sibling project `../F030OPL2`:
`tools/export-sound-trace.js` writes the driver's OPL2 writes in its trace format.

**Phase 8, the digital layer on the Falcon (2026-10-07).** The three-slot effect mixer, its request routines and every
digital call site of `sound-driver.md` section 5 that exists in the port are on the Falcon: `src/sound.s`, hooked from the
attract cycle, the mission start, the flight loop, the weapons, the wrecks, the timed blast, the options bar and the Sound
Loud/Soft/Off radios (`analysis/functions/sound-falcon.md`, "Call sites"). The mixer arithmetic is the original's and is
checked byte for byte: `tools/check-falcon-sound.py` runs the 68030 mixer in Hatari through the same call sequences as the
DOS captures of `build/sound/digital-*.json` (233,472 of 233,472 mixed bytes, also with every fill cut into unequal pieces),
against `jsComanche/dos-sound.js` on random call sequences (1,812,480 bytes), against the image's two curves and against an
integer model of the resampler. What the original does with a Sound Blaster DMA double buffer the Falcon does with a 4 KB
ST-RAM ring, a linear 11,111 -> 12,292 Hz resampler and the 50 Hz VBL refill (`tools/check-falcon-dma.py` plays a timeline
in Hatari, records Hatari's own audio output and checks the ring against the model and the WAV against the ring). The silent
boundary above stands for everything the music driver still owns: the title and fanfare screens keep their fixed 480/600
frames, and a machine without the digital device (`COMANCHE.CFG` byte 1 = 0, or no sound system to lock) is silent as before.
No sound call changes simulation state or timing; the layer keeps registers and flags, and the request log
(`snd_log_buf`, `tools/decode-sound-log.py`) shows what the game asked for. Open: nothing was auditioned or run on a real
Falcon; the music driver and its hooks; the DOS wall-clock cadence of the cues (the port's frames are slower).

## Verification ladder

Every subsystem should have the smallest applicable comparison:

1. **Binary and format:** exact offsets, byte counts, checksums, sentinels, and
   decoded record boundaries.
2. **Routine:** identical results for captured inputs, including edge cases
   for signed arithmetic and fixed point.
3. **State:** selected game-state snapshots after a fixed input sequence.
4. **Frame:** fixed-camera framebuffer captures and documented tolerances.
5. **Loop:** scripted startup, mission selection, play, failure/success, and
   restart under Hatari.
6. **Hardware:** frame time, memory use, VIDEL/VBL ownership, and DSP transport
   on the intended Falcon profile.

The CPU renderer remains the correctness oracle for DSP work. Performance
numbers from Hatari are diagnostic only; hardware-sensitive decisions require
measurement on a real Falcon or a specifically documented target setup.

## The faithfulness inventory

**Reading note, 2026-08-18.** Passages further down this file name build flags
- `TERRAIN_HALF`, `TELEMETRY`, `BENCHMARK_CAMERA`, `FLAT_HORIZON`, the
`BENCH_*` switches - that no longer exist. They are records of measurements
taken while those flags did exist and are left as written, because rewriting
them would falsify the evidence they carry. Only `USE_DSP` and `PARITY_TILE`
remain; everything else was folded to its DOS behaviour and the alternative
deleted. Where such a passage reads as an instruction, it is not one.


Standing rule one was sharpened on 2026-08-18: the CPU path IS the
disassembly, with the 16-bit true-colour surface as the one class of
exception, and behaviour is not build-selectable. This is the list of places
the port is still not that. It is a working inventory - entries leave it by
being implemented against the listing, not by being argued down.

**Current boundary, 2026-08-25.** The active renderer, sky backdrop, flight
integration, mission resource-family selection, replay reader, palette loading,
authored mission object factory/draw dispatch, replay callback table, transient
weapon/effect states, and object bearing/scale tables now use recovered DOS data. The old analytic
sine/atan tables, gradient/cloud backdrop, generated map/palette fallbacks,
pinned-camera renderer, and painted telemetry were removed. A subsystem whose
DOS contract is not recovered now stops or stays dormant: live joystick input,
live keyboard input, sound, mission completion, and the real menu exit
are not replaced with guesses.

**The terrain marcher is settled, 2026-08-27.** `0000D950` is no longer an
open question. `tools/compare-marcher.py` reproduces it exactly - 17,248 of
17,248 columns over all 152 non-uniform rings, every ring 112/112 with a
maximum error of 0 - and the port's own generated tables score the same when
substituted for the original's, which tests the depth/projection package in
use rather than field by field. What it took was not more disassembly but a
capture taken at an instruction (`--at-marcher`); see `docs/DOS-ORACLE.md`.
One real deviation fell out of the certified reference: `0000D9B7` truncates
first and subtracts second, where the port negated the multiplicand and added,
and `high32(A*-C)` is `-high32(A*C)-1` whenever the low half is non-zero.

Still not certified: the port's own **rendered output**. The arithmetic and
the data are proven; a same-camera surface diff needs a diagnostic capture
path on the `PARITY_TILE` precedent, not a behaviour flag.

**The console layer was four pixels out, 2026-08-27.** Every DOS coordinate
reaching a blitter is a page x on a 328-pixel page whose displayed window is
the middle 320, so `surface x = page x - PAGE_VIEW_X`. The port passed page
coordinates straight through, art included, and measured +4 four different
ways before it was corrected. See `docs/X86-M68K-MAP.md`. The menu and screen
paths are still unconverted and unmeasured.

**Hard-coded colours, 2026-08-27.** `COL_MENU_*` are the six-bit triples the
original *asks* for; it draws the nearest index in the installed palette,
found by `0002B820`. Three of five differ against the attract's palette. The
flight HUD's ladder colour now resolves through `resource_match_colour`;
`menu.s` still uses the direct expansions.

**Targeting, 2026-08-27.** The latch, its cycle, its per-frame expiry, the
targetability test and the per-object view bearing are ported. Reading them
corrected a live fault: both copies of the ring search published the page ring
for the sprite's terrain clip where the original publishes the clip ring, so
models beyond the near bias were clipped against the wrong ring's silhouette.

**The attract flight, 2026-08-18.** Two symptoms were reported from watching
it. One is fixed and one is open.

*Fixed - the sky panned the wrong way.* `render_clear` negated the heading to
index the sky bank, on a note claiming the negation was the original's. It is
not: the original's `NOT` at 00017251 is applied to a 32-bit view angle, and
this port's heading has already been mapped out of that angle by
`a = (128 - h) AND 255`. Substituting gives `strip = (2h + 159) AND 511`,
which matches the original's expression at every heading tested. Applying the
negation again reversed the pan, and the 0x30000000 term - the 159 - was
missing altogether. See SKY_ORIGIN_BIAS.

*WITHDRAWN - there is no view-heading/motion-angle split.* This entry claimed
00019DFC was a separately-driven view heading that the port was missing, and
that was wrong. 0000D98C reads it as `not al` / `shr al,1` into the projection
page pointer, which is the marcher's 127 - alt/2 bias: **00019DFC is the
ALTITUDE**. src/flight.s has said so in its own header the whole time -
`player_altitude ... (19DFC)` and `flt_prevalt ... (19DF6)` - and the claim
was made without checking it. The clamps that should have stopped it earlier
are in the listing too: 00018F20-00018FA6 ramps it +4 toward 0xFA and -1
toward 0x0A, and an angle wraps rather than clamping.

The view angle is not separate either. 00007D25 forms it as
`[00019D00] = [00019D04] + [00019D94 + variant*4]`, so it is the motion angle
plus a fixed per-variant offset. Those offsets read 0x00000000 for variant 1 -
the ordinary cockpit, which is what 0000698D selects - and 0xC0000000,
0x40000000, 0x80000000 for the others, which are the -90, +90 and 180 degree
side and rear views. So for the shipping variant the port's use of the motion
angle directly is correct, and the offsets matter only when those views are
ported.

The last thread is closed too, and the port was already right. The two-tap
filter at 000194E0 smooths the ALTITUDE across frames -
`al = [00019DFC]; al += [00019DF6]; rcr al,1`, with 0000D3C0 latching the
previous value at frame start - and src/flight.s now does exactly that after
its climb/sink step with the 68030 extend-bit rotate (`add.b` then `roxr.b`).

**Resolved 2026-08-18: the CPU simulation cadence is one DOS tick per frame.**
The outer loop at `000069CC`/`00006AEE` calls `0000D3C0` and then waits in
`00015B78`; the second loop also calls the driver once after `00018D20` and
waits before repeating. Inside the frame driver, `00018D20` is the single
input/demo dispatch that falls into the flight handler at `00018F94`. The
recording therefore supplies one input record and one integration per frame,
independent of how many VBLs a Falcon render happened to consume.

The CPU path now follows that contract: `game_tick` performs one
`demo_tick`/`flight_tick` pair, or one keyboard-driven `flight_tick`, and
`attract_frame` advances one screen tick. `frame_vbls` remains a bounded timing
diagnostic in `main.s`; it no longer scales simulation or demo playback. This
was a behaviour fix, not a timing optimisation: catch-up integration made a
slow renderer fly a different recorded path.

**Recovered, and the port simply does something else.** These need no more
disassembly; the arithmetic is already written down.

**CPU alignment pass 2026-08-18: source-matched and Hatari-checked.**
`render_terrain_ring` now consumes the generated raw `.DTL` A/B tables and
runs the whole walk in the original's 10.22 coordinates: the camera is
`flt_x`/`flt_y` unconverted, every increment is the raw `imul` high word
(an earlier revision shifted it "to 16.16" by five bits, which halved the
DOS step - 10.22 to 16.16 is six bits - so the march covered twice the
file's depth per ring), the map cell is the top ten bits exactly as the
`shld` pair extracts them, and 32-bit overflow is the map wrap. The ring
centre accumulates by A_i and two halves sweep outward from it. The Falcon's
160 two-pixel presentation columns are the centred crop of the fully walked
192 DOS source columns. There is no B_i lateral rescale: the ring order,
signs, raw source tables, and lateral step remain DOS-defined.

The same pass corrected three consumers of the recovered horizon walker
against the listing (see the map's rotated-horizon section): the walker
builds the shear centre-out with a sign flip and an accumulator reset at
column 96, so `backdrop_dy` now pivots at the screen centre instead of a
ramp pivoted at the right edge; the sky fill pairs strips with columns right
to left, `origin + 191 - c`, so the backdrop is no longer mirrored; and the
terrain tilt reads `backdrop_dy` word-indexed - the byte-indexed read was
painting every odd source column's spans off-screen, which is what the
vertical-stripe frames were.

The object depth path was aligned in the same sitting (see the map's object
draw stage): `object_view_transform` had the DOS matrix's two outputs
swapped, and the elevation-page ring find compared a 10.22 key against a
`>>6` table - between them, an object twenty map units out read ring 249's
page instead of ring 41's. The transform now stores forward = X*sin - Y*cos
as `00024B45`-`00024B67` does, `ring_z_table` is table 4 verbatim, and the
find is the DOS two-stage unsigned search with the `0x1800000` near-bias,
checked against an x86 transcription over the real HIGH.DTL with zero
mismatches across the depth range.

**The missing test facility is only a verification gap.** It must select a
camera state without selecting between renderer behaviours. The removed flags
chose candidate marchers, geometry and tilt; the CPU path now has one source
of behaviour, and a fixed-camera capture can verify it without changing it.

**Platform deviations, deliberate and documented.** These stay, but each one
should carry its reason next to what the original does.

- `draw_span` clips to the surface. The original's writes wrap inside a
  256x256 buffer addressed as `ch:cl` and its 182-row transfer window drops
  what falls outside; a framebuffer row is a multiply here, so an unclipped
  negative row writes 40 MB past the screen.
- `render_clear` paints a `COL_GROUND` base below the sky strip. When the roll
  shear pushes `h` past -42, rows above the 150-byte source strip are left
  untouched, matching the DOS fill's persistent surface instead of inventing
  pixels by repeating strip row 0. Falcon keeps one logical RGB565
  `terrain_history`: it restores that surface into the next work buffer before
  terrain, then updates it before objects and cockpit/HUD composition. Copying
  the fully composited display buffer would carry those later pixels into the
  next terrain frame and create the observed upper-field trash.

  The screen-to-flight boundary is separate: both Falcon targets may still
  contain TPIC/COMA pixels when the replay begins. `render_reset_surface`
  seeds each target once from the active ground entry and rebuilds its
  backdrop after the DEMO header has installed the camera. This is a
  transition clear, not a new per-frame terrain clear, and it removes title
  residue from the first replay frame in both CPU and DSP builds.

  For positive `h`, the same 8-bit surface address wraps source bytes `0..h-1`
  to screen rows `214-h..213`; the Falcon overlays that lower segment before
  terrain and cockpit composition.

  Measured 2026-08-18, and it points at removal: with the seed at page row 0
  every column's first emitting ring fills from its own row down to
  RING_PAGE_ANCHOR, so rows below the silhouette are terrain and rows 214..239
  sit under the console. Three demo captures agree - 9654 COL_GROUND pixels
  visible before the seed was corrected, zero in every frame since. That is
  evidence and not proof: three frames cannot establish that no camera reaches
  it, and the fill is also the fallback when CONSOL1S fails to load. It should
  come out, but only alongside a way to render the same camera before and
  after, which is the same thing the fan restructure is waiting on.

**Not recovered yet - these need disassembly before they can be ported.**

- Live mission entry outside the attract fixture. The ten-entry factory
  dispatch, authored model banks, `00024E05`/`00024FED` order, `0002514D`
  frame tables, mission state handlers, replay target selection, callback
  table, transient pool, and traced weapon/effect states are active for the
  recorded attract streams. The browser still has no general playable-mission
  menu/control path.
- The HUD's event-populated variant branch. The fixed console, HUDS overlay,
  green sight line, and phase-gated `0000D88C` COMA tail are active where DOS
  reaches them; attract/phase 1 skips that tail. The DOS null-gated
  `[00019D1C]`/`[00019D24]` tables remain zero until the owning event graph
  populates them.
- The mission parser's briefing-only metadata and gameplay completion rules.
- Live keyboard/joystick firing gates and the real menu handoff remain outside
  (`src/object.s`). The attract cycle selects the matching mission resource
  block, authored SG banks, and `DEMO<N>.SCR` on each pass; QEMU-traced
  event-only object states are now ported rather than left dormant.
- `src/start.s` is a video-mode scaffold, and the MFP vector stays with TOS.

**Two projections that must agree.** Terrain and authored objects now use the
same `ring_page_table` indexed by the `.DTL` ring search. `object_find_page`
ports the DOS `00024CC0`-`00024D73` depth and altitude lookup, and the only
remaining conversion is the Falcon surface's bottom-up 213-row anchor. An
object standing on ground the renderer drew at row R therefore uses that same
page row rather than a second analytic projection.

## Immediate queue

The file boundary, stream decoder, scalar start tuple, and CPU integration are
now verified for `0.MIS`. The next work should be:

1. establish and maintain the function map;
2. resolve the 15 currently reported indirect-control-flow sites;
3. trace from flat entry `0x1538` to the outer initialization and main loop;
4. name the DOS timer, input, and allocation boundaries;
5. ~~recover the object-record field contract and port one target type~~ - the
   contract is recovered (see below) and mission type 3 is ported end to end;
   eight of nine mission-factory types remain, in ascending order of what they
   need: type 6 (only its `update` field, `000233A3`'s `22DD0`, is unknown),
   type 0/1/2 (the shared allocator-init state `00023F60`, plus draw `24E05`
   for 1/2), type 4/5 (state `23CF0`, only its 64-byte opening decoded so far),
   type 7/8 (target-selection AI, the most complex of the eight);
6. define silent sound and local-only network interfaces from observed calls;
7. add mission completion/failure state and a restartable local loop;
8. validate the CPU path before resuming the DSP terrain kernel.

### The supported replay boundary is the first bounce (2026-09-08)

DEMO1 has 777 records, and the flight arithmetic still matches the original
for all of them ("The replay, checked against the original at the same
record", below). Record index 284 - the 285th, cursor 2293 - is the no-damage
bounce: `00019461` arms the screen-shake countdown, and from the next timer
tick the original pans its display through `00001DF1` (attribute-controller
pixel pan) and `00015BBC` (CRTC start offset plus the `00015B60` table). The
JavaScript browser now applies those recovered offsets to its cropped target
surface and continues the authored replay. The Falcon path still stops at
that presentation boundary because its 320-wide target has no recovered VGA
page-margin equivalent. The timer arithmetic itself is closed, by
`src/shake.s` and `tools/check-shake-contract.py` against forty cases captured
in the running original.

The cross-machine acceptance procedure therefore traces the first 284 records
of DEMO1 across DOS, JavaScript, 68030 and 68060. The browser-only sequence
witness now runs all four authored passes with the target adaptation. Passes 2,
3 and 0 remain outside the cross-machine parity slice until the display shake
is recovered. What that recovery needs is recorded in
`analysis/functions/browser-attract.md#shake-timer`: all four phase values
captured with CRTC and attribute-controller state, the full page contents and
the scanout at matching boundaries, then the page margins preserved on the
target and the complete displayed window compared.

### The first complete-frame pair: DEMO1 record 20, cockpit (2026-09-22)

The first DOS/Falcon complete-frame comparison at a matching replay and
publication boundary exists now. Its verdict was **DIVERGENCE, 58,028 of
76,800 pixels identical**. After the terrain-registration fix in "The second
pair" it is **66,121**
(`build/acceptance/frames/complete-frame-comparison.json`). The list below
is the first capture's; items 3 and 4 note what the fix changed.

**How the pair is taken.**

- DOS: `work/capture_dos_frame.py --record 20` runs the *shipped* executable
  on a scratch copy of `img/comanche.hdd`. It stops at `00006AE9`, the flight
  loop's `call 000189C2`, once `[0x19ECC]` reaches 173 (record*8 + 13). There
  it writes the gate's Alt `[0x1AA8]`, P `[0x1A89]` and KYLE `[0x265ED]` bytes
  through the gdbstub and lets `000165FD` write `SNAP_001.PCX`. It releases P
  at `000189E2` and restores all three bytes. No executable byte is patched.
- Falcon: `tools/capture-target-frame.py --record 20` stops at the main
  loop's `publish_screen` when `demo_cursor` = 173, and saves the RGB565
  buffer that `d0` names.

**Why these two instants are the same frame.**

- `00015B78` programs the CRTC from `[0x19CAC]` (the page just drawn, plus
  one byte). Only after that does it flip `[0x19CA8]` (`00015BF7`-`00015C01`).
- The writer reads `[0x19CA8] XOR 0x7D00` (`0001667B`), which is the page on
  screen. At `00006AE9` of loop N+1, that page holds loop N's frame: rendered
  by `0000D3C0`, followed by the consumed record and the `00015B78` publish.
- The port's loop has the same order: `frame_driver`, then `demo_tick`
  inside it, then the exchange and `publish_screen`.
- The phase is checked, not assumed. DOS records 19 and 21 score worse than
  20 in every region: view 61.6 / **66.4** / 58.1 %, cockpit
  86.4 / **87.2** / 85.7 %.

**The displayed window is page x 4, by measurement.** The CRTC start is
page + 1 byte, and one Mode X byte is four pixels. The static cockpit agrees:
at pan x 4, 25,110 of 28,800 cockpit-row pixels match, and no other offset
from 0 to 8 exceeds 17,498. `[0x19DBC]`, `[0x15B60]` and `[0x19DC4]` were all
0. `tools/compare-terrain.py` still takes the left 320 columns; that is now a
known 4-pixel misregistration, not an open question.

**The oracle is deterministic enough.** Two independent DOS captures at cursor
173 differ in 51 pixels, all inside x 145-157, y 113-125: the effect over the
designated tank. The Falcon capture is byte-identical across runs.

**What differs, largest first.** Each item was cropped and scaled beside the
original. They are not yet decoded unless stated.

1. **Weapon fire is not ported, and this changes the scene.** The DOS HUD
   reads `HELLFIRE 0011` and `CHAFF:23`; the port reads 0012 and 24. DEMO1's
   record 11 sets byte 2 (`flt_trig1`, `[0x19DF2]`); record 7 sets byte 3
   (`flt_trig2`, `[0x19DF3]`, the target cycle, which *is* ported). DOS
   consumes `[0x19DF2]` at `000191FC`/`00019205`. It then reaches `0001920B`,
   sets `[0x19D81]` = 1, clears `[0x1B29]`/`[0x1B3C]` and calls the weapon
   handler `[0x19D68 + 4*[0x19D88]]` (`0001922E`). The port ORs the byte in
   (`src/demo.s`) and never consumes it, as `game_tick`'s status line says.
   The chaff decrement's path has not been traced; do not assume it is this
   one.
   **Launches ported 2026-09-22** - see "Weapon fire, ported" below. The
   re-captured frame reads `HELLFIRE 0011` like DOS.
2. **The targeted object differs.** DOS draws a tank ahead with the
   designator box on it, and its right MFD shows that tank at `RANGE:063`.
   The port has nothing ahead, and its MFD shows the brown model pair at
   `RANGE:049`. Whether this follows from item 1 is not yet established.
3. **Terrain: 66.4 % in rows 0-139, and most of that is misregistration.**
   The variant 7 pair below found it: the port draws its 3D view four pixels
   left of where DOS shows it. Scored against the DOS page at x 0, the r20
   view (rows 20-129, x 40-279) matches 80.8 %. At x 4, where the cockpit
   correctly sits, it matches 55.7 %. The first reading here ("shade bands a
   few rows apart") was that shift seen at 320x240. The sky, index 14 in
   11,373 of the top 40 rows' pixels, matches exactly, so palette
   conversion is not involved.
4. **HUD.** The altitude reads 222 on DOS and 224 on the port. The pitch
   ladder's dashes lay at slightly different slopes; after the terrain fix they
   match, because the shear index shared the offset. The port's sight line
   ends in the L-shaped tick already listed under "What the matched
   side-by-side still shows". The port draws the dashed box left of the IR
   lamp (element `0x2A`); DOS does not, at this frame.
5. **Map and sky objects.** The left MFD matches in 62.5 % of its pixels. Two
   distant object dots in the sky are cyan on DOS and dark on the port.

### Capture identity gate (2026-10-05)

`tools/capture-target-frame.py` now selects the replay stream and camera as
well as its cursor. The cursor alone repeats in all four attract passes and
cannot identify the mission/resource family. The publication breakpoint
requires `demo_active = 1`, `attract_demo_pass = --pass`, and
`view_variant = --variant`; every dumped field is checked again before the
metadata reports `CAPTURED`. Defaults select DEMO1's cockpit. For the fixed
camera pair, use `--record 245 --pass 1 --variant 7`.

The probe builds and runs the stock 68030/14 MB, CPU-only configuration,
executes Hatari directly with a bounded Python subprocess timeout, and records
the invocation plus program, TOS, Hatari executable, capture-tool and frame
SHA-256 hashes. Starting a rerun invalidates its previous success metadata.
`CAPTURED` establishes the requested target checkpoint, not DOS equality.

Validation: `python3 tools/test-capture-target-frame.py` passes the matching
identity, six wrong/missing identity cases and timeout invalidation. A real
Hatari run with `--record 20 --pass 1 --variant 1 --out
build/frame-pair/falcon-r20-identity` rebuilt the target and captured cursor
173 with active replay 1, pass 1 and variant 1. Its frame SHA-256 is
`8555a6c221f0e77d44af59a239c9eee3725011d78935641b35709daad4fc595a`,
identical to the retained r20 target frame. The browser proof gate passes.
Existing complete-frame DOS divergence remains open; this change improves
capture identity and reproducibility without changing game semantics.

### The second pair: DEMO1 record 245, fixed camera (2026-09-22)

DEMO1 flies variant 7 from record 207 to 357 (`work/replay_dos/view-demo1.json`).
Record 245 (cursor 1973) was captured with the same two tools, with
`--variant 7` on the DOS side and `view_variant` = 7 on the Falcon side. The
verdict is **DIVERGENCE, 41,267 of 76,800 pixels**
(`build/acceptance/frames/complete-frame-demo1-r245.json`) as first captured,
**53,283** after the terrain fix below, **76,183** after the console fix. The r20 pair remains the gate
artifact, `complete-frame-comparison.json`.

**The port's terrain is four pixels left of the original's.** This frame has
almost no HUD, so the view region can be scored at every offset. Against the
DOS page at x -6..6, the 3D view (rows 20-167, x 40-279) peaks sharply at
x 0: **98.4 %**, falling to 89.7 % at either neighbour. The r20 cockpit frame
also peaks at 0 (80.8 %) and not at 4 (55.7 %). The cockpit bitmap, by
contrast, peaks at 4, as the CRTC start requires. So the port places the
terrain in the wrong coordinate frame, and the listing says which:

- `00025C32` indexes the per-column horizon at `[x>>1 + 0x3CB4E]` on an
  array based at `0x3CB40` (the note at `src/hud.s`'s element-5 blit). With x
  a page coordinate, **page x 0 is terrain column 14**.
- The port puts column 14 at *surface* x 0 (`TERRAIN_VIEW_FIRST` = 14 in
  `src/dsp/proto.inc`, used by `src/render.s`'s span and sky writers). But
  surface x 0 is page x 4 (`PAGE_VIEW_X`, `src/inc/comanche.s`).
- The visible window should therefore start at column 16, or equivalently
  every terrain surface x should be `2*(c - 14) - PAGE_VIEW_X`.

**Fixed the same day.** `TERRAIN_VIEW_FIRST`/`LAST` are 16/175 again in
`src/dsp/proto.inc` and `jsComanche/dos-runtime.js`, and `CMD_VERSION` is 11.
Every consumer uses the same relation, surface x = 2*(c - `TERRAIN_VIEW_FIRST`),
and each was checked against its DOS origin:

- The span and sky writers (`src/render.s`; the JavaScript `drawTerrainSpan`
  and `renderClear`) place column c at page x 2*(c-14), so at surface x
  2*(c-16).
- The HUD's horizon-sheared element (`src/hud.s`, `00025C32`) indexes
  `(page x >> 1) + 14`, which is `(surface x >> 1) + 16`.
- Object placement (`src/object.s`) takes compose column v into column
  c = v - 32, then lands on the same transfer.
- The sprite terrain clip (`src/sprite.s`) is the reverse of that
  conversion.

Re-captured with the fixed build, the view region peaks at page x 4 in both
pairs: 81.1 % (r20) and 98.4 % (r245), each against the same DOS frame as
before. The whole frames rise from 58,028 to **66,121** and from 41,267 to
**53,283** of 76,800. The r20 pitch ladder's slope, listed as a HUD
difference above, now matches: it was the shear index's share of the same
offset.

**The variant 7 console was never painted. Fixed the same day.** DOS showed
`consol5s.dta`'s banner on black in rows 168-239. The port matched 126 of
those 23,040 pixels, because it still showed the attract title page there.
The decode:

- Every DOS console load is followed by `0001687D`. It copies the whole
  decoded image, opaque, into the draw page, one plane at a time through
  `00016BB0`: at pass entry (`0000698D`-`0000699E`) and in every view
  case's shared tail (`000196C5`-`000196CF`). After the flip, `00016B50`
  copies the displayed page into the other one.
- Nothing repaints those rows afterwards. `00006FEF` limits the terrain
  transfer to the image's clear words, and `CONSOL5S.DTA` is clear in
  exactly rows 0-167. `0000D8AE` draws no cockpit above variant 5.
- The port loaded `consol5s.dta` in `console_select_variant` but only ever
  drew a console in `hud_draw`, which runs for variant 1 alone. It also
  never staged `CONSOL2S`-`CONSOL5S.DTA`, so the load failed.
  `render_reset_surface`'s note had called the title residue "the picture".

`render_history_console` (`src/render.s`) now draws the loaded console's
opaque pixels into `terrain_history`, the port's persistent page, at
`000196CF`'s point in the tail (`src/view.s`). `tools/build-run.sh` stages
`CONSOL1S`-`CONSOL5S`. Clear pixels are skipped: on DOS those are the pixels
the transfer overwrites from the separate compose surface.

Re-captured, rows 168-239 match **23,040 of 23,040**, and the whole frame
**76,183 of 76,800** (99.2 %). Of the 617 remaining pixels, most are the
burning object and a few are sky dots.

**The weapon gap is visible here too.** The object ahead of the fixed camera
is burning on DOS and intact on the port. That is consistent with the
unported fire dispatch at `0001920B`-`0001922E` (r20 item 1), but it has not
been traced to that shot.

### Weapon fire, ported (2026-09-22)

The replay's trigger 1 now fires. The record is
`analysis/functions/browser-attract.md#weapon-fire`. In summary:

- **Ported and checked.** The dispatch `000191B6`-`0001922E`, the rocket and
  Hellfire launchers `00022B00`/`00022F90` and their states
  `000241C0`/`00024680` are in `src/object.s`. So are the six shared banks
  (`000066E2`-`000067AE`) and the frame-indexed draw `0002519D`, through
  which `00024997`'s BOOM explosions now draw.
  `tools/check-weapon-launch.py` compares every launch in DOS's supported
  first 284 records of DEMO1 (35 shots, traced by
  `work/trace_weapon_fire.py`): **35/35 exact** in every launch field,
  ammunition count and rail parity.
- **Not yet checked: flight.** The missile states were transcribed from the
  listing but have not been traced tick by tick against DOS. In the r20
  re-capture the port's Hellfire detonates on its slot-26 target, the brown
  model pair at `RANGE:049`. DOS's slot 26, at `RANGE:063`, is the green tank,
  still ahead of the missile. That traces back to r20 item 2 (a different
  object in the same slot), not to the missile code.
- **Slot numbers differ in 22 of 35 launches, and the first difference has
  a cause.** DOS index 130 is one past every 130-entry array, so its
  "active" byte is `[000219A3]`, slot 0's sprite byte. A write watchpoint
  shows a BULL flare taking it at cursor 21 (`00022A69`) and releasing it at
  cursor 253 (`000244D5`). Missile lifetimes may explain the later
  differences; that is not settled.
- **The countermeasure chain that launches BULL/CHAF, decoded and not
  ported.**
  - `000077A0` is the threat display. It walks slots 130..31 and, for any
    active slot with a non-zero aux byte `[00021DB3]` and |lateral>>24| < 0x14
    and |depth>>24| < 0xF, draws a blip through `00025B27` and sets
    `[00019D93]` = 1.
  - `00023EA7` (type 4/5 state `00023CF0`) sets `[00019D92]`, and
    `000235EF` sets `[00019D94]`.
  - After the movement core, `00019555`-`0001959E` launches BULL
    (`00022A00`: flare `[00019D8E]` - 1, active count `[00019D90]` + 1,
    timer 0x14, state `00024480`, bank `[00019E74]`) when `[00019D93]` or
    `[00019D94]` is set, altitude > 0x0A and no flare is active. It launches
    CHAF (`00022AA0`: `[00019D8D]` - 1, `[00019D8F]` + 1, timer 0x1E, state
    `000244A0`, bank `[00019E78]`) when `[00019D92]` is set and altitude > 0x14.
  - Both then run `00022A54`'s common tail: draw `0002519D`, position and
    altitude from the flight, and `000074C0`'s counter redraw.
  - This is what took DOS's chaff to 23 at r20. It needs the `00023CF0`
    enemy state first.
- **Pages 0 and 3-5** (`00022890`, `00022E70`, `000231B2`, `000230B0`) are not
  reached in the supported range and are not ported. A trigger on them is
  consumed without a launch. The browser's weapon functions are still the
  earlier model and are recorded as Unproven.

### The mobile ground unit, the countermeasure chain and four blitter faults (2026-10-06)

The "targeted object differs" item of the first frame pair (item 2 above) had
a single cause, and it was upstream of everything the comparison had been
looking at: **the mission factory installed the wrong state on every DEMO1
object.** Every placement but the fixed one is type 2, whose DOS factory
(`000233DB`) installs state `00023CF0`; the port installed the default
latch-only state, so the tanks never moved, never turned their turrets, never
aimed and never raised the threat flag that makes the helicopter drop chaff.
`CHAFF:24` against DOS's `23`, a stationary tank, the wrong slot numbers for
the player's own weapons and a missing target all follow from it.

**How it was measured.** `work/trace_replay_flight.py --objects` stops the
shipped executable at `000234CE` - every state handler has run, nothing has
drawn - and writes every per-slot array the handlers touch, one row per frame
(`work/replay_dos/objects-demo1.json`, 300 passes). `tools/trace-falcon-objects.py`
stops the port at `object_update_done`, the same instant, and compares the two
by `demo_cursor`. Both traces are generated, not committed (`work/replay_dos/` is ignored):

```sh
python3 work/trace_replay_flight.py --objects --records 300 --out work/replay_dos/objects-demo1.json
python3 work/trace_replay_flight.py --sprites --records 22  --out work/replay_dos/sprites-demo1.json
python3 tools/trace-falcon-objects.py --records 285 --run-vbls 16000 --slots 23-130 --tolerance 4
```

 `--sprites` does the same for every entry to the scaled
blitter `000253CD` (slot, frame, column, page row, scale), so a draw can be
compared with the draw it should have been.

**What is ported** (`src/object.s`, all cited by address in the routine
headers):

- `00023CF0-00023F55`, the mobile ground unit: the move, the ground target
  `height*2 + 0x0B`, the three-probe steering with its latched direction, the
  `(speed >> 21) + 1` turn, the health and hold exits into the aim, the aim
  at `00023E55` (bearing through `000256C8` from the frame snapshot, the
  `(altitude << 20) + 0x1E000000` range limit, the `[00019DB8] & 0xC` chaff
  gate, the one's-complement arc test, the turret walk by 3, the fire on the
  `[00021F75]` timer mask) and the damage tail through `000227BF`. `OBJ_FIRE`
  is the per-object `[00021FB0]` shot routine pointer.
- `00022CA1`, `00022D33`, `00022DD0`, the three shot routines, and the shells
  they install: `000234E0` and `000236D0` with the shared proximity tail at
  `0002357B-000236C1` (the hit on the player: shake, damage cells, hull,
  `[00019E49]`).
- `00019555-0001959E`, the countermeasure decision at the end of every flight
  tick, the launchers `00022A00`/`00022AA0` and the cloud states
  `00024480`/`000244A0`.
- `000227D8` was not what the port had: it installs the BOOM wreckage handler
  pair at the parent's position, it does not copy the parent. Every child of
  a destroyed object was an inert slot.
- `object_move` now takes the Q31 products at `[heading*8]` exactly as
  `000248E4-00024914` does (it used the 8.8 table, up to 0.4% per step).
- DOS has one destruction byte at `00021B29`; the port had three readings of
  it, so a weapon's kill never reached the state waiting for it.

**Result against the oracle** (285 passes, DEMO1): for the placed objects
`active`, `altitude`, `health`, `hold`, `phase`, `speed` and `timer` match
**285/285 in every slot**, `heading` and `steer` match for six of the eight
tanks, `[00019D8F]` (chaff in the air) matches 285/285, and the weapon launches
land in DOS's slot in 29 of 35 cases (13 before; `tools/check-weapon-launch.py`:
35/35 launches exact in every field either way). The frame pair's chaff
readout is 23 and its altitude readout 222, as DOS's are.

**What is not reproducible, and why.** The tank's aim is gated on
`[00019DB8] & 0xC`, which the timer ISR steps on wall-clock ticks
(`src/shake.s`); DOS and the port run at different speeds, so which frames the
gate lets through cannot agree. The turret variant (`[00021F57]`) therefore
walks differently, and with it the second model of every pair draw. This is
the original's own nondeterminism, not a defect to chase; the distribution is
faithful, the frame-by-frame value is not.

**Open, measured.**

- ~~Slots 27 and 28 diverge in heading from cursor 1837 and 1997~~ - closed the
  same day: see "Positions in the original's own units" below.
- DOS's `[000219A3]` sprite array holds 1 in every slot at start; the port
  holds 0. Nothing reads it before a wreckage state writes it.
- The JavaScript reference was brought to DOS parity for these states the
  same day (`tools/check-js-objects.js`, which plays the oracle's recorded PRNG
  into it); its player weapons and everything downstream of a hit remain open.

**Four faults the frame pair exposed in the blitters and loaders, all fixed:**

1. **Object sprites ignored the roll shear.** `000254C0-000254C4` add the
   backdrop's per-column offset `[eax + 0x3CB20]` to every destination
   column's row; the terrain spans carry the same offset. The port drew the
   whole sprite at one row, so under roll a tank landed ~30 pixels below the
   terrain it stands on, behind the cockpit. The blitter now shears per column
   and clips per column after the shear; the silhouette test still compares in
   page space.
2. **A night mission's models were never recoloured.** `0002B903` copies a
   bank's palette to `00015F84` and runs the mission's palette variant
   `[0002A980]` (the green night transform) before the nearest-colour remap;
   `0002B8C5` does not. The ten mission slots (`0000653D-000066B2`, `0000683B`)
   and `CHAF`, `STGR`, `HELL`, `ROCK` (`000066FF`-`00006765`) call the first;
   `BULL`, `BOOM`, `CONS`, `HUDS` (`00006787`-`000067E9`) the second. The
   port applied the variant to the terrain palette only, so DOS's green tank
   was brown. The fireball correctly stays orange.
3. **The bank validator refused two valid banks.** `sprite_bank_validate`
   demanded a palette offset of at least 769, a check with no counterpart in
   `00015E6E`; `CHAF.RLE` (palette at 0x1B4) and `BULL.RLE` (0x148) failed it
   and never loaded, so the chaff and flare launchers had no model. The bound
   is now the record table's own size.
4. **The HUD recomputed its altitude readout.** `[00019E00]` is stored by the
   flight tick at `00019391`; the port recomputed it at draw time from the
   frame's own state, one tick ahead of what DOS shows. It is stored in
   `flight_tick` now.

Smaller: `[00019D8F]`/`[00019D90]` are zeroed at mission load (`0000685E`);
`tools/capture-target-frame.py`, `tools/check-weapon-launch.py` and the new
object tracer start Hatari through its GEMDOS drive so symbols load when the
program's text is resident (Hatari 2.6 refuses `symbols` before that, which
made the old fixed-VBL arming fail silently); `COMANCHE_DETAIL=1` stages the
MEDIUM setting the DOS oracle runs, and **a frame pair taken at HIGH against
a MEDIUM original measures the setting, not the port** (67,436 against 62,624
of 76,800 pixels on record 20, from nothing but that byte).

**Frame pairs now** (MEDIUM, `tools/compare-complete-frame.py`): record 20
**67,442** of 76,800 (it was 61,829 at HIGH and 66,084 in the earlier
report), record 245 **76,185**. Left on record 20, in order of size: the
tank's second model (the rng-gated turret) in both views, the left MFD, and
the cyan sky blip.

### Positions in the original's own units, the rest of the unit states and the shake (2026-10-06)

**Object positions are 10.22 now.** They were 16.16, which drops the low six
bits of every step. Six of the eight DEMO1 tanks tracked DOS to a few LSB for
1,800 ticks and then their steering probe (an equality test on the ground
height under the next step) flipped on a position that differed by 0.002 map
units; the fate of tanks 24, 27, 28 and 30 diverged from there. Positions are the
mission file's map units shifted 22 (`src/mission.s`), the map index is the top ten
bits (`shld ebx,eax,0xa` twice), `object_move`'s step is the Q31 high dword as it
stands, and the bearing, aspect, transform, weapon launch, hit scans and blast
read and write them without conversion (the view transform halves nothing: it
takes `flt_x - X` and shifts the *difference* down 6 into its 16.16 matrix, which
is exact where the old difference of two floors was not). **Result: tanks 23-27
are bit-exact against `work/replay_dos/objects-demo1.json` in x, y, heading,
steer, altitude, health, phase, timer and active for all 740 recorded passes**
(cursor 13..5925); `tools/check-weapon-launch.py` now compares launch positions
exactly and passes 35/35.

**More of the unit family, all from the listing** (`src/object.s`): `00023F60`,
the allocator's default state (types 1, 6, 7, 8): the variant spin, the early
move, the ground target `height*2+0x2C`, the engagement range
`((kind^1)<<6 + 0x96) << 0x16`, the jitter, the falling-wreck tail `0002414C`;
`00023840`, the type 4 wingman (formation point `0xEE800000 * [00019CBC]` behind the
helicopter, installs itself as `[00022368]`); the guided missile `00024860-00024B16`
(the Stinger of page 3 and a tank's Hellfire: homing capped at 0x19 a tick, max of
ground and target altitude, proximity 8/6 damage then the player chain); the timed
blast `00024310` (page 4's bomb: 0x78 ticks, then 0x64 damage and a BOOM child on
everything within fifty map units and the player's death); launchers `00022E70`,
`000231B2`, `000230B0` (pages 3, 4, 5). The old "default state" was a latch and a
`rts` and the old `object_state_move`/`object_altitude_step` were halves of
`00024860` read without it; they are gone. Page 0's gun (`00022890`, `000244E0`) is
ported with the live-key half of the dispatch (`000191CD-000191FA`: Space and KP5
held on page 0, their make latches `[00001B29]/[00001B3C]` elsewhere; Tab and
Return's latches select targets at `00019230`; KP0 and KP. step the turn rate at
`000192A9`). No attract pass reaches page 0, so it was checked by poking the same
held key and page into both machines (`work/trace_replay_flight.py --poke-from`,
`tools/trace-falcon-objects.py --poke-from`): over 45 passes with a lock on slot 26
the cannon rounds in slots 127-129 match DOS in position, heading, altitude, frame
and speed. The fields DOS aliases through its 30-entry arrays (f9, health, hold,
variant on slots above 30) differ by construction.

**The two pair draws were one body, and wrong for both.** `00024FED` (the tanks)
draws A then B at `variant >> 3`, or B at `(variant+4) >> 3` then A, around the
page-row line 0x82; `00024E05` (types 1 and 6) adds a mirrored turret at
`(-variant+4) >> 3`, eight source rows lower (`[000253CC]`, which
`sprite_draw_scaled` now adds to the record's Y offset). The port applied 24E05's
mirrored azimuth to 24FED's turret in the cockpit view.

**The left MFD's markers were rejected** by a shift of 17 where 12.20 -> 16.16 needs
19 (`0000772D`'s `cl = 0x17` less four fractional bits): a tank 62 units ahead
plotted at 31 rows against a window of 22. Fixed; the dot DOS shows is the first
thing the frame pair gains from it.

**The run no longer stops at the first bounce.** `src/main.s` ended the whole game
when a screen shake was armed (`shake_presentation_unproven`), so nothing past DEMO1
record 284 - and none of DEMO2/3/0 - had ever run on the Falcon. The shake is the
CRTC start address (`00015BB3`: page+1 plus `[ebx*4 + 00015B60]` for the phase, in
82-byte rows) plus the attribute controller's pixel pan (`00001DF1`: phase << 1,
which is one pixel per two in a 256-colour mode). Worked through, phase p moves the
displayed window by (0,0), (-3,+1), (+2,+2), (-1,+3) pixels against rest, and
`shake_present` does that to the finished frame. The DOS page is 328 wide and its
margins hold real pixels the window slides over (the PCX of record 20 shows them);
the port renders the 320x240 window only, so the revealed margin takes the edge
pixel. That is the one recorded deviation, and it lasts the ten timer ticks
`00019461` arms. The sticky `shake_presentation_unproven` stays as the witness.

**What the longer run shows** (superseded by the update below: the draw walk). With the game running to record 740, tanks 23-27
stay exact; 28, 29, 30 fall out at the first hit that DOS applies and the port does
not (cursor 4357-4637), because the player's target latch `[00019D10]` differs from
4061 (DOS latches slot 30, the port 28): the candidate `[00019D18]` is the last slot
`00024DA4` accepts in draw order, and the port accepts a different last one. Whether
the culprit is the silhouette archive it compares against, the sort order, or the
shear byte is not yet known - the DOS inputs are recorded
(`work/trace_replay_flight.py --marks`, 1,870 tests) and the port's are not.

**Update, same day: the draw walk was backwards, and objects keep what the allocator
does not write.** The draw pass walked `object_order` nearest-first; `00024BDA` walks
it from the far end, so the targetability candidates came in the wrong order. Fixed,
and the latch now matches DOS in 755 of 760 passes (the exception is cursor
2885-2925). The second finding is in `00023297`: the allocator writes the active flag,
state, draw, models, speed, X, Y, heading, altitude, damage byte, aux, health, f9,
hold and the shot routine - and **not** the timer `[00021E35]`, the steering latch
`[00021EB7]`, the sprite `[000219A3]`, the previous position, the previous altitude
`[00021AA7]` or the target latch. `000227A6` clears only the 130 active flags. So a
mission's objects inherit the previous mission's values for those fields: DEMO2's
tanks start with timers 11, 11, 11, 22, 11, 209, 46, which is what DEMO1 left in those
slots. `object_init` used to zero the whole table and `object_factory_fill` cleared
those fields, which was false for every mission after the first and is now gone. The
first call seeds the program image's non-zero defaults instead (altitude and previous
altitude 170, sprite 1, position 0x40000000/0xD4800000, read from
`re/unpacked/comanche-flat32.bin`). Same-day review by a second reader found two real
faults in new code, both fixed: `rcr al,1` leaves SF alone, so `jns` at `000248C6` and
`000246EA` tests the sign of the preceding `sub` byte, not of the rotated value (a
homing missile turned the long way round whenever the two differed), and a duplicate
`object_launch_common` label that left the flare launcher returning early.

**Frame pair, DEMO1 record 20 (variant 1): 67,438 -> 75,530 of 76,800 identical, in
five findings that each came from measuring rather than reading.** The frame was
scored 67,438 with the horizon, the left MFD map and a displaced far ridge all
"close"; a shift search per row band showed the far band 2 pixels right and the near
band 2 pixels left of DOS, 100% and 97% of the pixels in each - a registration
fault, not a content one.

1. **The roll has a horizontal half.** `00007DC3-0000968A`'s unrolled walker writes,
   per step, both the vertical column offset `[0x3CB40+c]` and a source displacement
   pair at `[0x31B20+8c]` from the same `dh`: `v = byte(0x30 -/+ dh)`, flat source
   column `v >> 2`. `00006FEF` assigns every run of surface row `k` (32..213) the
   record `0x31B30+8k`, so screen row `y` reads record `c = 183 - y`, and `00007AA0`
   copies each row from there: the terrain is a rotation done as two shears. Read
   off DOS's own records at record 20 (flat columns 10..14 in five 40-row bands,
   `work/replay_dos/runbase-r20.bin`) and fitted with slope 25 on all 192 records.
   `render_row_shear` in `src/render.s` applies it to the finished terrain/object
   band; terrain, sky and objects shift together and the cockpit drawn after does
   not. The DOS surface is 192 columns and the window shows 160, so a shifted row
   exposes real columns on one side; the sky fill, terrain spans and sprites paint
   columns 0..15 and 176..191 into margin buffers (`COLBASE`) and `render_row_shear`
   takes each row from [margin | window | margin]. Measured 2026-10-07: records
   50, 80, 120 and 250 are pixel-exact, the rest 76610-76800 of 76800; the old
   edge replication cost 800 pixels at record 80 and 900 at record 120.
2. **The left MFD map uses the stale basis.** `0001587B-0001586D` read
   `[00019CB0]/[00019CB4]`, built by `00007D25` from the angle the frame started
   with, not the angle the tick has since advanced; the port rebuilt it from
   `flt_angle`. One table step differs, which is a different sample grid: 57.6%
   against 99.6% of the DOS pixels (offline sampler, `work/` scratch). Now reads
   `view_sin/view_cos`.
3. **Object depth and lateral are DOS-exact.** `00024B2E-00024B70` halves each
   delta and keeps `edx` of every product, 12.20 floors; the port computed 16.16
   from a delta shifted six bits early, so a ring search could land one ring off.
   `OBJ_DEPTH20/OBJ_LATERAL20` hold the exact values for the ring search
   (`00024CC7`), the column divide (`00024D84`, `00025261`) and the lock aim
   (`00022C60`); the 16.16 fields stay for their other readers as the floor.
   Measured against `work/replay_dos/depth-r20-h{1,2}.bin` (both passes): within 2
   16.16 units before, exact floors now.
4. **The C and T gauges** (`0000D532-0000D5AB`): bars at page x 0x30/0x38, a
   0x16-row black clear and `level >> 3 + 1` rows in `[0002A37C]` / `[0002A379]`;
   the console art's baked bars were showing instead. Needed four more resolved
   named colours (`0002AB5F-0002ABBF`) and the torque byte `[00019D84]`
   (`00018FB7-00018FE2`) in `flight_tick`. The F bar at 0x110 (fuel `[00019D60]`, seeded from the
   mission's `[00019D5C]`, one less per tick) is drawn too. The fuel-exhausted branch
   `00018E10-00018E44` is ported (collective dragged to zero from the saved
   `[00019D83]`, flight end at -0x10E, forced in Hatari: collective 0, stop at
   -270); what stays out is its engine-out voice (`0001899A` -> `00004F6E`, sound)
   and the mission teardown at `0002873D`, which `game_tick` stands in for with
   the same stop as any unrecovered mission end.
5. **A clamp the original does not have.** `object_draw` for the target view
   clamped a negative panel row to 0 and shifted logically; a missile at page row
   242 against a top of 162 was parked on the panel's first row. Signed now.

What is left in that frame is the turret variant (`[00019DB8]`, wall-clock), three
sky marks whose palette differs, the edge exposure above, and the target view's top
row. The weapon-launch check now lands in DOS's slot 33 of 35 (29 before); a
frame-pair comparison is only a measurement if both sides are the same iteration -
the DOS capture is the frame rendered in the iteration whose record consumption
takes `[00019ECC]` to the wanted cursor, its console drawn after the tick, which is
what the port's `publish_screen` at that cursor holds too.

**Ten more DEMO1 frame pairs (DOS captured with `work/capture_dos_frame.py`, scored
by the same tool pair) - 96.4% to 99.7% identical:** records 10, 30, 50, 80, 120, 160,
250, 340, 370, 400 score 75,600 / 75,576 / 75,790 / 74,841 / 74,064 / 74,877 / 76,255 /
76,117 / 76,063 / 76,589 of 76,800, with records 20 and 245 at 75,530 and 76,175. Four
more faults came out of them, each read off the listing:

- **Only the 168 terrain rows reach the screen.** `00007AA0` copies surface rows 46..213
  and nothing else, so in the external views (no cockpit) the page's title art stays
  below row 168. `sprite_draw_scaled` clipped at the whole screen and the sky fill's
  wrapped strip segment landed past the band: a near explosion and a dark wedge painted
  over the art (record 120: 65,688 -> 74,029).
- **The chase camera's helicopter** (`00024C0A-00024C3D`, variant 6): the pitch
  accumulator's low byte becomes the elevation bias `[0002237F]`, which `00024E0F` and
  the elevation lookup add to the page row, and `[0002237E]` sends the blit to
  `00025606`, which shears the model by the walker's base alone instead of the
  per-column offset. The port's note claimed `[0002237F]` had no writer; `00024C25` is
  it. Frames 17 and 49(m) now, as DOS draws.
- **No lock, no march** (`00007868`): the right MFD still shows `000079F0`'s copy of
  the compose surface, which then holds the main view - 80 x 44 samples at flat column
  `0x38 + x`, surface row `162 - 2r`. The port drew nothing there (record 370:
  72,543 -> 76,063). The window is kept before `render_row_shear` because the surface
  is the unsheared one.
- Records inside a screen shake cannot be compared: `[00019DBC]` is advanced by the
  timer ISR in wall-clock time, so the phase the DOS page was rendered with and the one
  read at capture differ (record 300: 63.6% for that reason alone).

Two more from the second reviewer pass and a left-MFD check: page 0's markers scaled the
12.20 lateral/depth with a shift written for another unit (26 -> 28; record 370's three
markers now land on DOS's exactly), and the target-view clip's `muls.l` read a stale high
word of d6 for sprites straddling the panel's top or left edge.

Open in those frames, in order of size: the turret variant (`[00019DB8]`), the player
helicopter's exact look in the chase view (frames match, pixels do not), the explosion
sprite shape, the three sky marks (DOS maps their source indices to teal DAC entries the
nearest-colour search over the final palette does not reach - the installed palette at
sky load time is probably not the final one), and the edge columns the row shear exposes.

**DEMO2, DEMO3 and DEMO0 on the Falcon**, against `work/replay_dos/objects-pass{1,2,3}.json`
(`tools/trace-falcon-objects.py --pass N`). DEMO2 at its first pass is exact in
everything except the `variant` byte; speed, steer, chaff and the unit family follow.
What diverges after that is the wander at `00024100` (`[00019DB8] & 3 - 2` added to
the heading of any unit beyond engagement range): `[00019DB8]` is a free-running
generator DOS advances in wall-clock time, so tank headings, and everything the
terrain probe reads from them, cannot be matched pass for pass and the later demos
inherit that history through the carried-over fields above. DEMO0's static oil
tanks are exact in x, y, heading, health, active and speed. DEMO3's wingman and
ground units at slot 19 are exact; slots 12 and 13 wander. That is where the
object layer stops being checkable against a single DOS capture.


### The attract camera, closed (2026-09-01)

The largest remaining difference in the attract cycle was not the terrain, the
objects or the console. It was that the port watched the replay from the wrong
place for 42% of it. It is ported and certified now; the decode, the wiring
and the short list of what is still dropped are in
`analysis/functions/falcon-attract.md`, "The attract camera, ported". What
follows is the finding that produced it.

The flight itself is settled and needs no further work:
`work/trace_replay_flight.py` stops the DOS oracle at `00019555`, once per
integration tick, and reads the whole flight state through the gdbstub. The
port's arithmetic reproduces the original's `[0x19CD4]`/`[0x19CD8]`/
`[0x19D04]`/`[0x19DFC]` and all five rates for **777/777** ticks of DEMO1 and
**676/676** of DEMO2, and `tools/certify-replay-flight.py` shows the running
Falcon build agreeing with the original at the same record under Hatari.

What is missing is `[0x19D86]`. The replay records carry `'1'`..`'7'` in their
key byte, `0001959F` turns them into view variants, and `00007D25` uses the
variant to index both the view-angle offsets at `[0x19D94]` and the camera
handlers at `[0x7BC9]`. Variants 6 and 7 relocate the viewpoint - a chase
camera fifteen map cells back (`00007C26`) and a fixed ground camera at
`[0x19CE4]`/`[0x19CE8]` (`00007CC5`). DEMO1 selects 6 at record 30, 7 at 206
and returns to the cockpit at 357.

All five pieces are done: `[0x19D86]` and the `0x02`-`0x09` cases,
`00007D25`'s angle and its handler table, both external cameras with
`000256C8`'s bearing, and the per-variant `consol<n>s.dta` loads.
`0001985B`-`000198B6` turned out to be what writes
`[0x19CE4]`/`[0x19CE8]`/`[0x19DF8]`, inside the `'7'` key's own case.

**A mission-parser fault came out of it.** `00029213`'s eight-value block and
the number after it were crossed with three `mission_skip_line` calls instead
of read; they are nine numbers, and the third skip was eating the first
placement record. The original parses nine records for the attract's first
mission, types `0,2,2,2,2,2,2,2,2`, and the type-0 one installs the fixed
slot-31 object that the variant-7 camera aims at. The port had eight and no
slot 31.

A side-by-side of the attract flight is now a renderer comparison rather than
a comparison of two different cameras.

### The right MFD, and what was left of it (2026-08-27)

At this point in the investigation the right panel was still black because
page 2's handler, `00007860`, was not ported. It is not an overlay: it
substitutes the locked target's viewpoint, marches a second view, runs an
object pass and restores. Seven pieces, of which four were done:

- **done** - `0001B26C`, the 80-column marcher (`mfd_march_target_view`);
  `00024DA4-00024DFC`, the targetability test; `0001922C-000192A3`, the latch
  and its cycle with `0000D439-0000D45E`'s expiry; `00024CB8`, the per-object
  view bearing; `00007860`'s camera substitution; and the composition into
  the 80x44 rect (`MFD row = (162 - page_row) / 2`).
- **done** (cont.) - `000079AF-000079E3`, the `RANGE` readout, with its value
  latched at `0000D43D`.
- **left** - `00024B17`'s object pass into the substituted view, which is what
  puts the target in the panel. That is the whole of what is missing now.

**The panel draws, 2026-08-28.** The lock held - object 26 from VBL 1107 to
1244, expiring through `0000D449` - and the rect fills with terrain. Two
faults stood between a working marcher and a black panel, both closed in the
same session:

- **A stale seed.** `00024BD0` clears `[0x19D18]` before the object walk and
  `00024BE1` clears `[ecx + 0x21BAB]` per slot, in front of the active and
  depth tests. The port cleared neither there - the targetability byte was
  cleared inside `object_mark_targetable`, which only runs for objects that
  survive every cull. So `00019275` seeded the latch from a slot that had
  passed the test in an *earlier* frame, and `0000D449` dropped the lock in
  the same frame the cycle took it. A Hatari watchpoint on the latch caught
  the clear at `object_target_validate`'s own epilogue.
- **A span the window discarded.** `mfd_view_occl` read `0xFF` across all 80
  columns, so spans *were* emitted - and the writer rejected every one whose
  top was above panel row 0. The original never makes that decision: it
  writes the whole span into the shared 256x256 surface and `000079F0`
  copies a 44-row window out of it afterwards, so a span starting above row
  162 still paints every row inside the window. Collapsing those two steps
  into one write means intersecting the span with the window, which clamps
  at **both** ends; only the bottom did.

  This is the common case rather than an edge. `0001B2D0` takes the page
  index bias from the **target's** altitude, and the height map is in half
  units of the altitude scale (`camh = 127 - alt/2` against a full-scale
  height byte), so a ground-level camera reads page 255 for terrain barely
  above it on every ring below about six. The panel is therefore a flat fill
  - the nearest ring saturates the occlusion - which is what the original's
  own marcher does with the same camera. At this stage the missing target
  composition was `00024B17`; it was closed in the target-view pass recorded
  below.

### What the original's own attract shows (2026-08-28)

Captured with `python work/set_boot_mode.py comanche` and
`python work/run_qemu.py --timeout 110 --shot 40 --shot 55 --shot 70
--shot 85`, into `work/qemu_out/screen_t<sec>.png`. Read these before
judging any attract difference by eye:

- `screen_t40` - pass one: **red** canyon, black starfield sky, `HELLFIRE`,
  and the right MFD holding a bridge structure with `RANGE:160`.
- `screen_t55` - a later pass: green/brown canyon under a **blue clouded**
  sky, right MFD holding two fuel tanks with `RANGE:286`.
- `screen_t70`/`screen_timeout` - the animated title.
- `screen_t85` - the title over a **green** starfield scene, which is what
  settles that the port's all-green presentation is a real DOS pass and not
  a palette fault. Do not conclude otherwise from a single frame: the passes
  differ in terrain family, palette *and* sky.

**Corrected 2026-08-28 - this section first read `screen_t55`'s panel as a
flat fill and concluded the port's flat panel was faithful. It is not.**
Zoom `screen_t40`'s right MFD and the original shows a curved horizon,
textured terrain below it, black sky above, and the target model standing on
it. Measured over the same 3520-pixel rect: **112 distinct colours with 712
pure-black pixels in the original, against 1 terrain colour in the port.**
The port's flat panel is a defect, not fidelity. The lesson is the one this
guide already carries - a 320x240 thumbnail of a 80x44 panel cannot tell a
flat fill from a rendered one, and the first reading was made from one.

### `00024B17` into the target view, and `RANGE` - the decode

The decode below was the contract used to implement both routines; the
remaining direct-RGB565 difference is recorded with the implementation.

**The surface geometry, now fully decoded.** `0001B26C` paints **40** surface
bytes, not 80: the forty unrolled writers at `0001C1A0` load `cl` with
`0x3F..0x2C` (the outward-left sweep) and `0x40..0x53` (the outward-right
one), so the view occupies bytes `0x2C..0x53` of the **even** field of the
256x256 surface. `0001B895` onward then copies each row's 40 bytes to
`+0x80` - the odd field - which is exactly where `000079F0`'s planes 1 and 3
read from. So the panel is 40 rendered columns duplicated into 80 pixels,
and writing both pixels of the pair (which `.span` does) IS that copy. The
vertical mapping is confirmed independently: the span writer's `inc ch` is a
256-byte stride, `000079F0` steps `-0x200` = two rows, and `0xA22C` is row
162 - so `panel row = (162 - page row) / 2` as ported.

**The marcher is now verified against the original, 4800/4800, and the flat
panel is not its fault.** Two real faults came out of this decode and are
fixed - the ring step is 3 (`0001B883`, `0001B838`, and the triple
silhouette archive at `0001B85E`) where the port walked 2, and the camera was
a 16.16 value handed to a marcher that walks in 10.22 (`000078BD` reads
`[0x20C6C]`, already 10.22; the port needed `00024C58`'s six left shifts).
With both in, `work/compare_mfd_march.py` reproduces the original's own
occlusion archive exactly - **every one of 60 steps by 80 columns** - driven
by the camera captured at `0000790E`. With either fix missing the first step
already diverges. The generated tables are not in question either: the port's
`ring_page_table` is byte-identical to the original's runtime projection
buffer at `[0x19E5C]`, 46080/46080.

Run the same model on the **port's** inputs and it produces the port's flat
panel exactly - page 255 in all 80 columns on step 0. So the assembly agrees
with the model and the model agrees with DOS; the inputs are what differ.

**The fault is `OBJ_VIEW_BEARING`, and the original says what it should be.**
`000078BD-00007903` places the camera at `object + 0x10000000 * (-sin, +cos)`
of `[0x21CAF]`, and in the captured frame that puts it **32 units from the
target on the player's side**:

| | original (captured) | port (VBL 1200) |
|---|---|---|
| object | (665, 236) | (242, 235) |
| player | (911, 154) | (263, 293) |
| object -> player | (+246, -82) | (+21, +58) |
| camera offset | **(+30, -11)** - same direction | **(-20, +25)** - not |
| terrain under the camera | 1, camera height index 7 | **45**, index 7 |

The original's camera stands on open ground beside the target and looks back
at it. The port's is buried 38 height units inside a hillside, so every
sample in every direction is far above it, every column saturates at 255 on
the first step, and one span fills the window. That is the flat panel, and it
is a correct render of a camera in the wrong place.

`[0x21CAF]` is `object_aspect`'s `not.b` of the octant bearing at
`00024C58-00024CB8`. The captured value checks out against the geometry -
slot 30 stores 178, and 178 of 256 is 250 degrees, whose `(-sin, +cos)` is
`(+0.939, -0.344)` against an object-to-player direction of `(+0.949,
-0.316)`.

**Closed 2026-08-28. The bearing was wrong for every object, for three
independent reasons.**

1. **The ratio correction table was transcribed 256 bytes long.** `00024C9B`
   divides the smaller magnitude by the larger one *shifted right ten*, so
   `00024C9D`'s index is the ratio scaled by **1024**, not 256. The table at
   `000223A5` is the arctan ramp 0..63 over indices 0..1024 - 1025 bytes. The
   locked object's ratio is 380, which read past the end.
   `tools/prepare-original-test.py` now transcribes it with the 1023 bytes
   after it as well: `00024C95`'s `je` only rules out `max < 1024`, and for
   `max` in [1024,2047] the divisor is 1 and the index runs to 2047, so the
   original reads those bytes too. Reproducing the image is faithful where a
   clamp would be a second behaviour.
2. **`move.l 0(a1,d7.l),d7` against `[ebx*4 + 0x22385]`.** The octant selects
   a *dword*. Unscaled, octant 1 read four bytes straddling two entries -
   `0x00007F00` where the entry is 0 - so the bearing came out of the wrong
   quadrant. Now `0(a1,d7.l*4)`.
3. **`moveq #0,d4` sat between the difference and `bpl`**, and moveq sets N
   and Z from its own operand. The sign test never fired: `00024C64`'s
   `sets bl` was always 0 and `00024C68`'s one's-complement magnitude was
   never taken, so every object with a negative X or Y difference had the
   wrong octant *and* the wrong ratio. The zero now loads before the move
   that sets the flags.

Verified end to end, prediction before measurement: the geometry wants 241 -
the camera offset must point along the object-to-player direction `(+21,+58)`,
which 241 gives as `(+11.5,+29.9)` and the port's 113 gave as `(-11.5,-29.8)`,
a half-turn out. The port now stores **241**. `mfd_view_occl` reads
`b6 b6 b4 b4 b2 b2 ...` - graded, in pairs - where it read `ff` across all 80
columns, and the panel draws **23 distinct colours with a horizon and
textured slopes** where it drew one flat fill.

**This is `object_aspect`, so it is not only the target view.** The same `d7`
is what `00024CA6` adds the object's heading to for the sprite aspect index,
so every object sprite in the main view was choosing its frame from the same
wrong bearing. That half is not separately verified yet - the aspect index
needs a capture of `[0x2237D]` against the port for the same object.

**The object pass.** `00007860` calls `0001B26C` and then `00024B17` with the
camera globals substituted, and `00024B17` is the *same* routine the flight
frame runs - so its sprites go through the same blitter into the shared
surface, and `000079F0` copies the window afterwards. The port cannot reuse
`object_draw_pass` as it stands, because that routine writes RGB565 straight
to `work_screen` at flight-view coordinates; DOS gets the redirection for
free from a surface the port deliberately does not keep. Deciding that is
the work: either give the object pass a destination argument, or keep the
80-column view in an intermediate the way DOS does. It should wait until the
terrain in that panel is right, because the model stands on it.

**`RANGE` - ported 2026-08-28.** `0000D43D` latches `[ecx*4 + 0x20A64]` into
`[0x19D14]` - the locked object's depth, taken *before* the validity test, so
the frame that drops the lock still latches it - and `000079D6-000079DE`
prints `[0x19D14] >> 20` (the port's `OBJ_DEPTH` is `world<<16`, so `>>16`)
through `0000D8F5`, already ported as `hud_draw_value`. `000079C3`/`000079CA`
put the row at `0xD7` and the element at `0x20`; `hud_bank`'s `0x16..0x1F`
are the 3x5 digits and `0x20` is the 23x5 label beside them.

**The x anchor, which was recorded here as unresolved, is settled - and it
was not an offset to fit.** `000079B9` writes `0x75` (117), and the original
draws the readout at x 193. The reason is structural: `0000D693-0000D6FC`
dispatches **both** MFD bodies through the one handler table at `0x19E10`, so
a handler draws at the **left** panel's coordinates and the right panel is
the same picture `MFD_PANEL_STEP` further along. `000079F0`'s own destination
says so - `0x37CE` is page row 174, byte column 18, and `18*4 = 72 = MFD_X` -
and `mfd_march_target_view`'s span writer already followed that convention.
`0x75 + MFD_PANEL_STEP - PAGE_VIEW_X` puts element `0x20`'s 23 pixels at 193
and `hud_draw_value`'s units digit at 227.

Verified as a bounding box rather than by eye: the readout occupies
**x 193..227 on rows 211..215** in `build/frame-range2.png` and in
`work/qemu_out/screen_t55.png` alike.

One Falcon difference, recorded where it is made. The DOS machine has one VGA
DAC, so `00025B27` has no palette to select; here each bank carries its own
RGB565 expansion, so the readout selects HUDS's palette exactly as
`hud_draw_dynamic` does around its own `00025B27` calls. Without it the
glyphs draw through whatever the terrain left installed and come out grey -
which is what the first build did, at the right position and in the wrong
colour.

### The object fan, closed 2026-08-31

Found while reading `0002519D` beside the port, not from a symptom. The
original never projects an object sprite twice: `00024D9F` and `00025274`
store `v` in `[0x22365]`, and the shared blit tail's `0002543A` adds that
byte to the destination column. **`v` is where the sprite is drawn.**

The port had an independent pinhole in `object_draw_sprite` -
`160 + 160 * lateral / depth`, under a comment reasoning that "the fan spans
lateral/depth in -1..+1 across the surface". That is a different fan.
Measured over the captured `MEDIUM.DTL`, `B` is exactly `z/100` for **all 180
rings** (`8*z/B` = 800.00 at every one), so the original's fan is
`128 + 800 * lateral / z_ring` - a half-fan of 200 surface pixels of lateral
per unit depth, not 160. Every object was pulled a fifth of the way toward
the centre, and further the more off-axis it was.

This is the horizontal half of the "two projections that must agree" rule
below, and it can be checked without DOS at all, because the port's own
marcher steps each column by `B/2` in the same 10.22 accumulator: the column
`v` names and the column the marcher walks to that lateral offset must be the
same. Over the port's seven live objects at replay record 86 they now agree
to about one column (197/196.8, 159/158.2, 71/69.6, 46/44.6, 44/42.2) - the
residue is `v` dividing by the ring's quantised `z` where the marcher
accumulates exactly. The pinhole disagreed by up to **50 columns**: slot 25
sat at surface x 183 and belongs at 290.

Two smaller faults came out with it, both order:

- **The three fan exits are culls.** `00024D8A`, `00024D93` and `00024D9A`
  jump to `00024E03`, which is `pop ebx` / `ret` - it discards the return
  address of `00024C45`'s caller and returns past it, so an object whose fan
  column is off the screen is not drawn at all. The port treated them as
  "skip the targetability marking" and drew on.
- **`v` is published before the slot test, not after.** DOS computes and
  stores it at `00024D84-00024D9F` and only then reaches `00024DA4`'s
  `cmp ecx, 0x1E`. The port had the slot test first, which was harmless while
  `v` was private and leaves every slot past 30 without a column now that it
  is not.

### The object prologue and the designator, closed 2026-08-31

A second pass down the same routine, reading `0002519D` and `000253CD` beside
the port rather than working from a symptom. Five more differences, all
between the port and the listing:

- **Two culls in the draw walk that the original does not have.** `00024BCB`
  tests the active byte and the depth sign and dispatches; that is all. The
  port also rejected anything past `OBJ_DRAW_RANGE` (992 map units, reasoned
  from how far the march reaches) and anything with `|lateral|` past its
  depth. The original culls on both counts but in the shared prologue and at
  its own bounds, and the bounds differ: `00024C45` rejects a depth above
  `0x1FFFFFFF`, **512** units, and the fan test is the band on `v`, about 50
  degrees either side rather than 45.
- **512 is structural.** `00024CC7` forms the ring-search key as `depth << 3`,
  and that passes 2^32 at exactly 512 units. Past the bound the key wraps and
  the search hands back a near ring for a far object - measured, an object at
  669 units landed on ring 97 with size band 2. Drawing further than the
  original is not generosity; it is drawing garbage.
- **The size band divided by the wrong thing.** `00024D21` divides `2^27` by
  the **ring's** lateral increment. The port divided 1600 by the object's own
  depth, which is the same quantity only up to the ring's quantisation.
- **The ramp is not in the image.** `000253D2` indexes a table at `0x1D7EC`
  and a pool at `0x1DBEC`; both hold *code* in the shipped file - an unrolled
  `rep stosd` - and are built at startup. Read out of the running original,
  ramp `127 - index` is exactly `index + 1` bytes long and its bytes sum to
  **64** at every one of the 128 entries, which confirms the port's
  `(index + 1) * 4` 8.8 scale is the right reading of the resampling.
- **`0000D460-0000D478` was never ported, so the target designator could not
  draw.** With a valid lock the original stores `2 * [0x21BAB]` and
  `[0x21C2D]` into `[0x19D1C]`/`[0x19D24]`, and `0000D428` clears the entry
  each frame. `object_target_validate` stopped at the latch drop. This file
  used to record those two tables as "zero until the owning event graph
  populates them"; the owning graph is the target latch, which now works.

**And the bank was wrong, which is what a fabricated gate was hiding.** Both
blits at the end of the frame driver go through `0002599E`, whose first
instruction is `mov esi, [0x19E90]` - not the `[0x19E94]` that `00025B27`
reads for the HUDS glyphs. Captured at a frame holding a lock, `[0x19E90]` is
`0x3B59A8` and its SG header declares **57 elements**: `CONS.RLE`. The port
drew from `COMA.RLE`, got a helicopter across the frame, and had been given a
`phase == 5` gate to suppress it - a gate the original does not have, and
which also suppressed the designator. `0000D4B7-0000D4CB` reaches `0000D88C`
for console variant 1, which is what the attract runs.

**Verified against the original's own pixels.** `0000D88C`'s element - weapon
byte plus one, so CONS element 1 - is the **centre cross** at the sight.
Comparing a port frame against a DOS frame over the same 60x42 region, the
cross now occupies exactly the original's coordinates: the left arm at
`(152..157, 90)`, the right arm at `(165..170, 90)` and the vertical arms at
`(161, 81..)` and `(161, 94..99)`. The designator box draws over the locked
object at `2 * [0x21BAB] - PAGE_VIEW_X`, which for the captured lock is the
slot the port's own targetability test picked.

**Recorded, not ported: `000254C4`.** The sprite blitter shears each column's
drawn row by the horizon, exactly as the terrain span writer does, and keeps
the unsheared row for the occlusion compare. The port's `sprite_blit` does
not. It stays a decode rather than a change because the attract cannot tell
the difference: the original's own `[0x3CB40]` reads 0 across all 192 columns
at a captured replay frame, with roll and pitch both zero. A capture with a
rolled camera has to come first.

### The replay, checked against the original at the same record (2026-08-28)

Asked to investigate the replay's flight path, mission and objects. The
method that makes this answerable is **indexing by replay record, not by
time**: `00018D15` advances `[0x19ECC]` by eight once per frame and the port's
`demo_cursor` does the same from the same initial 13, so the cursor value is
a shared clock and the two machines can be compared at the same replay
position however differently they are paced.
`work/dump_marcher_tables.py --want-cursor N` stops the original there;
a Hatari conditional breakpoint on `demo_cursor` stops the port.

**Mission: identical.** The original's own resource-name table at `0x2A320`
reads `Np44.dta d4.dta c4.dta sky4.rle` plus `lh66 spin tank turr radr fuel
hoke`; the port's `mission_palette_name`, `mission_map_family`,
`mission_sky_number` and `mission_sprite_names` hold exactly that list in the
same order, with `mission_index` 1 and `mission_kind` 1. Stronger than the
names: the port's loaded height map is **byte-identical** to the original's
over a 149,797-byte sample of the 1 MB map, so it is the same terrain, not
just the same filename.

**Flight path: bit-exact, at two independent points.**

| | record 17 | record 26 |
|---|---|---|
| raw X | `0x41A77822` = `0x41A77822` | `0x4139E8EF` = `0x4139E8EF` |
| raw Y | `0x46A815A3` = `0x46A815A3` | `0x42B1EC39` = `0x42B1EC39` |
| angle | `0xF6B6CACB` = `0xF6B6CACB` | `0xF8B49E09` = `0xF8B49E09` |
| altitude | 140 = 140 | 147 = 147 |

The port's cursor reads one record ahead of the original's for the same
state, because the port integrates inside `game_tick` and *then* renders
while the original latches at `0000D3CA` and integrates at `0000D413` after
the renderer. The rendered state sequence is the same; only which record has
been *read* when the state is observed differs.

**The picture, side by side (2026-08-28 snapshot).** `build/replay-compare.png` puts the port above
the original at nearly the same state. The terrain silhouette, horizon,
cockpit, compass ribbon, sight line, ladder, `SPEED`, `CHAFF`/`FLARE` and the
MFD frames all agree, and the HUD glyph positions were separately measured
identical to the pixel. Three differences are visible and all three are known
gaps rather than new ones: the right MFD's **target model** (`00024B17`, not
yet ported at this snapshot), the left MFD's **cursor overlay** (`000075A1`, not decoded), and
colour. Colour is the RGB565 boundary of rule three and it is not a bug -
`lsr #1` from the six-bit DAC to five bits measures **unbiased** (mean error
2.02 of 255, bias 0.00, against 3.98/+3.98 for rounding), so the residual is
5-bit quantisation, not a wrong conversion.

### The console differences, closed 2026-08-28

Working from the record-matched side-by-side rather than from a list, four
differences in the fixed console and the left panel were named and closed.

- **`000075A1`, the map's own-ship marker.** `00007580` is three instructions
  longer than the map body: element 3 of the instrument bank at page x `0x70`,
  bottom row `0xCE`, through `0002599E`. That blitter is the fourth
  combination - plane-chunked like `00025880` so the left edge snaps to the
  four-pixel byte boundary, but index 0 transparent - and the port had the
  other three. It is the white cross in the original's left panel.
- **`mfd_draw_markers` drew through the wrong palette**, the same fault the
  `RANGE` readout had: its elements are HUDS records through `00025B27`, so
  they need HUDS's expansion named. Checked while there, the window
  arithmetic is right - `000075B5`'s scale is `0xFFFFFFFF / (zoom >> 5)` =
  1023 at the captured zoom, and against the original's own object arrays the
  same formula and window draw 3 of 10 live slots.
- **`00007464-000074B7` and `000074C0-00007503`, the value readouts.** Four
  digits of the selected weapon's count at x `0x27` walking left from row
  `0xD6`, and two digits each of chaff and flare at x `0x133`. HUDS records
  `0x0A..0x13` - the 4x7 glyph set, not `0000D8F5`'s 3x5 one - and no
  leading-zero suppression, which is why the original reads `0011` and not
  `11`. The values needed the parser: `000291D0-00029209` reads two
  countermeasure counts, **six** weapon loads and fuel, where the port had
  been skipping those lines blind. Parse verified undisturbed - start tuple
  unchanged, `mission_object_count` still 8, chaff 24, flare 24, loads
  500/62/12/4/2/0, fuel 5000.
- **`00007442-0000745F`, the page indicator mark**, a one-row write through
  `00025C55` at `0xC + ([0x19D88] << 3)`. `[0x22364]` is its *count*, not an
  element index.

Against the original at the same replay state the port now reads
`0012 HELLFIRE` to its `0011` and `CHAFF:24 FLARE:24` to its
`CHAFF:23 FLARE:24`, in the same glyphs at the same positions: the port never
fires, so its counts stay at the authored loadout. `00026BAE`'s 15/25
override comes from a mission-script handler whose route from the attract is
not traced and is not carried.

**A 68030 trap worth remembering.** `sprite_draw_page` loads `d3` with its
blitter flags and does not restore it, so a `d3` loop counter is reset to 1
by every call and `dbra` never reaches -1. That hung the frame, and it looked
exactly like a renderer fault - a blank screen with the backdrop still on it
and every status word healthy.

### What the matched side-by-side still shows (open)

With the console differences closed, `build/final2.png` puts the port beside
the original at the same replay state. Terrain, horizon, sky, compass, sight
line, ladder, `SPEED`, the weapon box, `CHAFF`/`FLARE`, the map with its
own-ship cross, the radar and the F-key labels all agree. Three things do
not:

1. ~~**The right MFD is black where the original holds a target view.**~~
   **Closed 2026-08-31 - two faults in `object_mark_targetable`, both in the
   two lines that turn DOS numbers into this port's.** See below.
2. ~~`00007530`'s element `0x2A` at x `0x48` row `0xAE` and the blink chain
   gated on `[0x19DE8] & 3` - the dashed box left of the IR lamp.~~
   **Misattributed; corrected 2026-09-28.** `00007530` is MFD page 4's
   handler (the table at `0x19E10`), not a console element, and the attract
   never selects page 4. It is ported with the other page handlers - see
   "MFD bodies" in `analysis/functions/falcon-attract.md`. The dashed box
   itself is still unexplained. The unported lamp and gauge blits at
   `0000D4C4-0000D641` (elements `0x26+[0x19D8C]` at `(0x24, 0xA8)` and
   `(0x118, 0xA8)`, `0x34/0x35` at `(0x8C, 0x99)`, `0x36/0x37` at
   `(0xBB, 0x99)`) are the next place to look.
3. A tick at the foot of the sight line, and one object dot on the map, both
   at this frame only.

### The targetability test, closed 2026-08-31

The measurement the entry above asked for was never needed: both faults are
visible in the listing beside the port, and the capture then certified them
rather than finding them. Neither is in a test - all five compares were
right - and both are in a conversion into the port's own units.

- **`v`'s dividend was shifted seven places instead of four.** `00024CC7`'s
  `shl edi,3` belongs to the *ring search key*; `00024D84`'s dividend is
  `esi`, reloaded from `[ecx*4 + 0x2085C]` at `00024D46` and never shifted.
  Both DOS object arrays are 12.20 (`[0x20A64] >> 20` is the `RANGE` readout,
  already ported as `>> 16`) and this port's are 16.16, so the dividend needs
  the four shifts of the fixed-point difference and nothing else. With seven,
  every quotient came out eight times too big and the accepted band
  `[5, 0xF5)` shrank to `lateral / (B>>3)` in `[-15, +14]` - a few degrees
  either side of dead centre. Everything else failed `00024D93`/`00024D9A`.
- **The silhouette was read one bias short.** `00024DEA` indexes the clip
  ring's archived row by `v`, and that row's 192 entries begin `0x20` into
  its 256-byte record - `0000F2F1`-`0000F2FF` archive them at `[0x19E60] +
  ring*256 + 0x20`. The source column is `v - 0x20`, the same bias the
  horizon read already carried through `0x3CB20`. The port stores only the
  192 and was indexing them by `v`, i.e. 32 columns to the right.

**Certified against the original's own bytes, at an instruction.** A
`--at-marcher --with-target` capture (`work/dump_marcher_tables.py`) freezes
one frame's lateral, depth, horizon, silhouette archive and the DTL tables
together with the bytes the test wrote. Running the corrected model over the
original's own inputs:

- of the four live slots, the model reproduces the original's accept/reject
  on all four, and on the one it accepted - slot 30 - reproduces
  `[0x21BAB] + 0x2E = 99` **exactly**;
- the archive dump settles the bias without argument: 192 non-zero bytes per
  256-byte ring record at offsets **32..223**, nothing outside;
- and the silhouette compare discriminates on this very object. The original
  reads `133`, which the object's page row 136 passes; entry `v` of the
  written window reads `168`, which it fails. The mis-indexed read rejected
  the one object the original accepted, independently of the scale fault.

**Measured before and after on the same build and VBL.** At VBL 3400/3700,
before: `object_target_default` 0, `object_target_latch` 0, and the right MFD
rect **1 distinct colour** - black. After: default 29/30, latch 30, `RANGE`
296..335 units, and the rect **18 distinct colours with a horizon, black sky
and textured slopes**. The original's own `screen_t40` panel measures 112
over the same rect; at that date the remaining difference was `00024B17`'s
model.

### The target-view object pass, closed 2026-09-08

`00007860` now calls the native `object_draw_pass` after
`mfd_march_target_view`, with the locked target's position and view basis
installed for the duration and the cockpit camera restored before `RANGE` and
the rest of the HUD. The target pass does not clear the main frame's target
bytes or default latch, matching the DOS routine's secondary composition call.

The target marcher archives its 80-column silhouette at the three ring slots
written by `0001B84E`. Object sprites select the matching archive by their clip
ring and are clipped in the right MFD's 80x44 RGB565 crop. This keeps the
authored model pair in front of or behind the target-view terrain instead of
drawing it through the ridge or using the cockpit horizon for every depth.

Verified in Hatari after `bash tools/build-run.sh --no-run`: the right MFD
contains the recovered target terrain, the model pair and the `RANGE` readout;
the cropped capture is `build/target-ring-final-mfd.png`. The only platform
difference in this path is the direct chunky RGB565 crop in place of DOS's
shared planar surface plus `000079F0` copy.

### The replay itself is faithful; its pace is not

Worth separating, because "the replay looks wrong" has two very different
halves and only one of them is open.

**The flight integration is verified exact.** The camera-state audit below
stepped the DEMO0 start state and `flight_tick` with the recorded inputs and
matched DOS memory snapshots 004..018 at ticks 11..291 - raw X, raw Y, full
angle, altitude, forward velocity and lateral velocity, all exactly. One
replay record in, one identical state out. Nothing in the object/bearing/MFD
work of 2026-08-28 touches that path, and nothing needed to.

**What the replay draws inside that path did change on 2026-08-28**, and all
of it is visible during the flight: object sprites are drawn at all
(`aspect_row`), their bearings and therefore their sprite facings are right
(`00024C58-00024CB8`), the target lock holds, and the right MFD renders its
target view with a `RANGE` readout.

**The pace is the open half.** `demo_tick` consumes one record per rendered
frame, which is what `00018CDB` does, so the replay's speed IS the frame
rate - and the port's is ~1.8 fps, so a 775-record `DEMO0` takes about seven
minutes where the original took roughly a minute. Nothing about the recorded
flight is wrong; it is played back several times too slowly, and the fix for
that is frame time, not fidelity.

**Do not try to settle the original's rate on the QEMU oracle.**
`work/replay_rate.py` measures the guest at **162 records/second** - 324
records in 2.0 s - because TCG has no 486 timing model and the replay is
paced by rendering. The oracle settles what the program computes, never how
long it took.

### The port's frame rate, measured 2026-08-28

`demo_cursor` advances one 8-byte replay record per game frame, and sampling
it through `work/hatari_probe.sh` at VBL 1500..4500 gives ~15 records per 500
VBLs - **one game frame per ~33 VBLs, about 1.8 fps** on Hatari's cycle-exact
Falcon030. The main loop is not the cause: it waits for one VBL and then
runs, so this is render time. This is recorded as a measurement, not started
as work - rule 4 and `../PORTING.md` own it - but it is the largest single
gap between this attract and the original's, and no amount of pixel fidelity
substitutes for it.

**Superseded - the latch was checked, and it stayed 0.** Measured by printing it through
`hud_draw_value` in a throwaway build. The cause is upstream of everything in
this section: **the attract draws no object sprites at all.** `object_aspect`
is entered hundreds of times per frame and never reaches its ring search,
whose only preceding exit is the model-bank check - so for every object that
reaches the draw handler, both `object_draw_model_bank` and `OBJ_MODEL_A` are
null. Some active objects do carry a model pointer, so the banks are not
entirely unloaded.

Nothing in the targeting chain can fire without that, and pieces 4, 6 and 7
cannot be validated either, because `00007860` gates on a non-zero latch. The
gap is pre-existing and was simply invisible until something depended on it.

Narrowed further: there are two disjoint populations. Objects that **do**
carry a model reach the dispatch but are handled by `object_draw_fixed`,
which gates on `object_fixed_phase <= 5` and draws nothing - and that gate is
**correct**, it is `00024C0A`'s test of `[0x19D86]` and the routine already
records that the traced attract route never opens it. The objects that reach
`object_draw_sprite` are a different set, and those have `OBJ_MODEL_A` null.

**Corrected, 2026-08-28.** An earlier revision of this paragraph said no
mission placement is ever installed. That was a measurement error - the
counter sat on the type-0 branch of `object_spawn_mission` and there are two
`object_factory_install` call sites. The factory works: 8 records entered, 8
installed through `.allocate_standard`, no allocator failures, and both slot
lookups return 0 with `f2`=2 (tank) and `f3`=3 (turr).

**Resolved to a specific test, 2026-08-28.** A four-value probe - shown all
at once, which is what finally gave a consistent picture - reads 422 objects
entering `object_draw_sprite`, **all 422 with a non-null `OBJ_MODEL_A`**, 422
entering `object_aspect`, and **zero** reaching its ring search. So every
drawn object has a model, and an earlier claim in this paragraph that they
did not was wrong.

The exit is not the model check but the test after it. `.model_bank_ready`
reads the SG palette pointer at `bank+4`, bounds-checks it against
`OBJECT_BANK_BYTES-770` (which passes), then requires `3D` at
`bank + pointer + 770`. **That marker test is what fails.**

The assets are correct: decoding the KRL containers gives palette pointers of
`0x1024D` (TANK), `0x72FC` (TURR) and `0xF2FE` (LH66), each with `0x33 0x44`
at pointer+770. What does not add up is the bank *in memory* - its first word
reads 0 through `OBJ_MODEL_A` at draw time and 19 through a direct `lea`, and
neither is `SG`. The name and load status for the slot are both correct. Two
reads of the same address disagreeing is the sharpest lead.

**The objects are placed, and four of them should be on screen (2026-08-28).**
Read out of a RAM dump rather than inferred: eight tank/turret objects are
active with correct model pointers. Three sit behind the viewer and one is
outside the fan, which the culls reject correctly. The remaining four are at
83, 213, 271 and 368 map units - far inside `OBJ_DRAW_RANGE` of 992 - with
`|lateral|/depth` between 0.43 and 0.88, comfortably within the fan. **They
should draw and do not.**

**The trace settles that this is a bug and not fidelity.** The QEMU exec
trace of the attract (`re/seeds-flat-traced.txt`) contains `00024C45`,
`0002519D`, `00024FED`, `00025880`, `000253CD` and `0002514D`, and also
`00007860`, `0001B26C` and `00024B17` - so the original runs the whole object
pass during attract, and the target view with it. Checking the trace should
have been the first move, not the last.

**Localised by a marker bisect.** Coloured blocks at fixed screen positions,
one per stage, all in one run: `object_aspect` is entered, passes the model
bank check and passes the palette-pointer bounds test, then **fails
`cmpi.w #$3344,(a2)`** - the `3D` model-record marker. That is what the very
first counter said; the RAM analysis that contradicted it was reasoning about
an address the code does not compute.

**Narrowed to one variable.** Exact 32-bit readback - values latched in BSS
during `object_aspect` and emitted as raw pixels during `hud_draw_dynamic`,
which runs last so nothing overwrites them - shows `OBJ_MODEL_A(a0)` is
*exactly* `mission_sprite_banks + 2 banks` (slot 2, tank.rle, the mission's
`f2=2`), `a0` is exactly 28 records past the table base, and
`object_draw_palette` is a sane palette address. But
**`object_draw_model_bank` holds `0x59ea`** - and `object_aspect` prefers the
global over the object's own field, so the marker test reads from a wrong
base and fails.

That value is a **code** address, and it moves with the binary across builds.
Latching all three at **one instant** - an earlier comparison across separate
runs misled me - shows the global matches *neither* `OBJ_MODEL_A` nor
`OBJ_DRAW`, so it was not written from this object at all.

Eliminated by measurement, not assumption: a duplicate symbol; bad linker
placement (the three globals sit consecutively at `0xcf87c`/`0xcf880`/
`0xcf884`); a stale `OBJ_SIZE`; `a0` misaligned (it is exactly
`object_table + 28*76`); `object_pair_project_row` clobbering `a0`; and an
`object_order` overrun (`object_depth_sort` writes exactly `OBJ_COUNT` words
into an `OBJ_COUNT`-word array). `object_draw_palette`, written from the same
base on the next line, arrives correctly.

**Closed 2026-08-28: it was a stray write, and the watchpoint named it in
one run.** A Hatari conditional breakpoint on the global's runtime address,
armed just before the demo flight,

```
b ($ee8e2).l < $1f0c4 && ($ee8e2).l ! ($ee8e2).l :once :file hit.ini
```

(the value went bad, *and* it changed on this instruction) stopped at PC
`$22798`, ten bytes past `object_aspect`'s entry - which is its own second
instruction:

```
object_aspect
        movem.l d1-d7/a1-a2,-(sp)
        move.l  d1,aspect_row           ; <- four bytes into a two-byte slot
```

`aspect_row` was `ds.w 1`, sitting immediately before `object_draw_model_bank`
in BSS, so the long store wrote `d1`'s low word over the **high** word of the
bank pointer. That is the whole "code address": the readings `0x59da`,
`0x59e0`, `0x59e6`, `0x59ea` and `0x5980` were never code at all - they are
the *surviving low half* of a correct BSS pointer with its top zeroed, which
is why they moved with every relink and matched nothing that was compared
against them. `object_draw_palette`, written one line later and one long
past the damage, arrived intact for the same reason.

The store had no DOS counterpart to keep: `00024C45`'s prologue is
`cmp dword [ecx*4+0x20a64], 0x1fffffff` / `jg 0x24e03` / `xor ebx,ebx` and
stores nothing, `d1` is not in this routine's documented input contract, and
nothing in the tree ever read `aspect_row`. It is a leftover of the
pre-recovery elevation band, which took the projected row from the caller;
the recovered routine takes the band from the `.DTL` page row at
`00024D5E-00024D71` instead. Both the store and the reservation are removed.

Verified: at VBL 3200 `object_draw_model_bank` reads `0x004D5978`, a bank
address, where it read `0x00005980` before; and `build/frame3600.png` shows
object sprites on the terrain for the first time.

**The generalisable part** is that a wrong pointer with a plausible *low*
half is a neighbour-overwrite signature, not a wrong-value signature - the
half that survived is the clue, and comparing the whole value against
candidate sources (which is what several rounds here did) can only ever
fail. `work/check_store_widths.py` now checks the whole tree for a store
wider than the `ds.b`/`ds.w`/`ds.l` slot it names; run it after adding BSS.
It reports 0 across `src/` and reproduces this one against the parent commit.

**A method note, because it has now cost three times.** Single counters shown
one at a time through `hud_draw_value` produced three wrong conclusions here.
Showing four values at once resolved it immediately - a lone number has
nothing to contradict a wrong placement, and three decimal digits mod 1000
lose the top of every value besides. For this class of question use the
debugger: `tools/grab-frame.sh` already drives Hatari with `--parse dbg.ini`,
so a script can dump a memory range straight to a log in hex. Note that
script rewrites `dbg.ini` each run, so invoke Hatari directly with your own.

Decoded from `0.MIS`, mission 1 holds 11 records of **eleven** fields each -
`f0..f10`; a seven-field grouping does not align, which was an earlier
mistake here - with types `{0:2, 1:1, 2:8}`. The eight type-2 records all
carry `f2=2, f3=3`: sprite slots `tank.rle` and `turr.rle`. Type 2 falls to
the factory's default handler, which binds the bank from `OBJ_MODEL_A`/`B`.
Those eight are precisely the objects that should draw and be targetable, and
DOS's own MFD capture shows a tank.

The leading suspicion is ordering: `mission_sprite_status` is read at HUD
time, long after the spawn, so a spawn that runs *before*
`sprite_mission_load` would see a non-zero status then and a zero one later -
which fits every measurement taken.

The paragraph below remains true but is **not** what blocks this:

Their source is the **transient/effect allocator** at `000227BF`: it searches
slots 130 down to 31 and activates one by copying a position, without setting
a model or a draw handler, so the slot keeps whatever it last held. In the
original those objects take their bank from the six shared dynamic banks at
`0x19E74-0x19E88` - `000249B4` points field 2 at `[0x19E88]`, BOOM, in the
wreckage transition - and **this port has no binding for them**, which
`object_transition_home` already records as a Difference. That is the gap to
close.

Ruled out: the mission's sprite slots. Mission 1 names `lh66`, `spin`,
`tank`, `turr`, `radr`, `fuel` and `hoke`, and `tools/build-run.sh` stages
exactly those seven.

Still open: what types mission 1 places in slots 1..30, and whether they reach
the pair handlers - types 1/6 and the default do bind the bank from
`OBJ_MODEL_A`/`B`, so they ought to draw. Read that from the port's own
parser rather than re-deriving the record format out-of-band; an attempt at
the latter found no alignment giving valid type bytes, so any conclusion from
it would be a guess.

### The object-record contract, and one type ported end to end

2026-08-21. Phase 5's object system had three pieces recovered but not
connected: the table layout, the allocator, and a handful of state-handler
fragments - with the dispatch from a mission placement's own type byte to a
spawn factory entirely unfound, and `object_spawn_mission` deliberately empty
because of it (`X86-M68K-MAP.md`'s own note: "a single TANK bank cannot stand
in for those factories").

That dispatch is now recovered in full: a 10-entry table at `0002231C`,
indexed by the type byte mission parsing already extracts, calling one of
nine factories. Mission type 3 - the oil tank, and the only type `0.MIS`'s
training mission places - is ported completely: its factory, its own state
handler and destruct sequence, the transient-pool allocator its destruction
stage spawns from, and the wreckage state every destroy sequence converges on.

Three corrections came out of finishing this slice, all to code already
marked "ported":

- `object_transition_home` installed a speculative placeholder
  (`object_state_move`) instead of the address its own comment already named
  (`000237B0`) - the comment was ahead of the code, not wrong.
- `object_reap`, the per-frame sweep that instantly deactivated anything
  `object_blast` had damaged, is retired outright. It was never a DOS
  mechanism - the original has no generic reap pass - and it actively
  conflicted with the recovered handler graph: a destroyed object stays
  active through a destruct stage and a further ~20-tick wreckage hold before
  the DOS original itself deactivates it, and the old sweep would have
  cleared it, and decremented the mission's target count, on the very first
  tick after damage was set. `object_state_wreckage` now owns both, at the
  point the original actually reaches them.
- **The dispatch table itself was first misread.** An early pass over
  `0002231C` reported type 3 landing on `000233BF`, installing state
  `00023B50` - the routine with the multi-stage steering probe. A direct
  re-read of the raw table bytes, done twice independently after the first
  Hatari verification below (which had only checked position/count, not
  cross-checked the state address against the table by hand) turned up a
  completely different order: type 3 is actually `00023446`, installing
  `00023A8C` - a far simpler handler whose alive path is a bare `ret` and
  whose destruct sequence is four stages, not fifteen. `object_state_static`
  and `object_terrain_probe` are not wasted work - they faithfully port
  `00023B50`/`00023AD0`, which the corrected table assigns to dispatch index
  9 - but nothing in `0.MIS` through `3.MIS` places that type, so they are
  now explicitly unwired rather than misattributed. `object_state_idle` is
  the new, correct port of `00023A8C`, and `object_spawn_mission` now
  installs it for type 3. Re-verified the same way as below after the fix.

Verification used Hatari's debugger in read-only memory-inspection mode
(`--parse` scripts; its `s`/`c` continue-from-nested-breakpoint mechanism does
not resume execution in this build, confirmed by isolated tests - a tooling
gap, not a mistake in the harness). Absolute addresses were computed as
`TEXT + comanche.map's own relocatable offset`, since GEMDOS symbol autoload
did not trigger against the `_d` build. Confirmed at three breakpoints against
`comanche_d.tos`: all 20 of `0.MIS`'s oil-tank placements spawn at their exact
mission coordinates with the right state handler installed; a later attract
pass loading mission 1 (8 type-2 placements, unrecovered) correctly spawns
nothing, proving the type gate does not false-positive.

### The oil tank's draw handler traced to an asset, but not yet wired

Still 2026-08-21. `0002514D`, the draw handler both the oil-tank factory and
dispatch index 9 install, calls the same address already ported as
`object_aspect` for its bearing math but does its own, simpler elevation
lookup (a direct shift of the projected screen row, not `object_aspect`'s
ring-depth search) - so it needs its own body, confirmed not a reuse.

**The scale computation already shipped in `object_draw_sprite` is correct.**
Its source comment describes `000253CD` computing a "ramp length of index+1"
from a literal `64`; neither exists in `000253CD`'s bytes. What actually
happens: `000253CD` reads two static tables, `sprite_scale_offsets` and
`sprite_scale_masks`, and the `(index+1)` linear law the port already
implements *emerges* from those tables' own construction (every mask row
sums to exactly 64, verified against all 256 raw table entries) rather than
being computed by any instruction. Reconstructing the real magnification
curve from the raw table bytes and comparing against the shipped
`1600/z, clamped 127, +1, <<2` formula matches exactly at every sampled
point, 2.0x down to 1/64x. Only the comment's mechanism description needs
fixing; the value was never wrong.

**The oil tank's own model resource is now identified: `FUEL.RLE`.** Every
mission-placed object's model pointer (object field 2) turns out to be set
generically, for all nine factories alike, by the shared allocator's own
success-path continuation (`000232A8`, reached by fallthrough from `00023297`
and not yet ported - the current `object_alloc` only covers the scan) from a
placement field this session had not traced before: `f2`, a **per-mission**
resource-slot index into that mission's own trailing resource-list entries.
For `0.MIS`, every oil tank's `f2=2` resolves to slot 2, `fuel.rle` - and
`FUEL.RLE`'s own bytes confirm it independently: decoding its `KRL1` wrapper
and replicating `0002514D`'s exact walk (`model+[model+4]+0x302`) by hand
lands precisely on a `"3D"` magic record, with an azimuth table that is
constant across all 32 entries - the correct signature for a shape that
looks the same from every side. Cross-checking against `1.MIS` confirms `f2`
is mission-local, not a fixed ID: its own type-2 objects carry the same
`f2=2`, which resolves to `tank.rle` in that mission's own resource list.

What this closes and what it still leaves open: the draw handler's frame
math is understood and its input data is identified, but nothing captures
`f2` yet (`mission.s`'s parser already reads and discards it), no per-mission
slot→name table exists on the Falcon side, and `object_spawn_mission` does
not set the model field. `0002514D` itself remains unported. An oil tank
still spawns, collides and destructs correctly but draws nothing.

### The silhouette gap was the wrong detail level

2026-08-27. Closed, and not by fitting anything. The port generated its whole
depth/projection package from **HIGH.DTL**. The shipped install runs
**MEDIUM**.

The evidence chain, each link checkable:

1. `00026211-0002626E` selects the file from the detail byte `[00025DD4]`:
   `'0'` loads `high.dtl`, `'1'` `medium.dtl`, anything else `low.dtl`. Each
   goes through `00015DD0` with `eax = 0x00019EE0`, so the file lands *at*
   `0x19EE0` and its own first dword becomes the ring count `[0x19EE0]`.
2. Every consumer then reads the tables at **fixed absolute addresses**:
   `0000D9BB` the lateral increment from `0x19EE4` (file + 4), `0000D99B` the
   forward increment from `0x1A2CC` (+1004), `00015ADA`/`00015B0A` the
   projection slope and bias from `0x1A6B4` and `0x1AA9C` (+2004, +3004), and
   `000251CA`/`00024D1B` the depth totals from `0x1AE84` (+4004). Those are
   the table boundaries only for a 250-entry file. For medium.dtl they land
   partway into a neighbouring table - and the original reads them anyway.
3. Two QMP captures of the attract flight, at different times and cameras,
   both read `[0x19EE0] = 180`. That is `medium.dtl`'s declared count.
4. Their captured slope and bias arrays are byte-identical to `medium.dtl`
   at offsets 2004 and 3004.
5. `00015AD9` decoded as
   `page[k] = clamp(high32(((k-128)<<24) * high32(slope * 0x03000000)) + bias,
   0, 0xFF00) >> 8` reproduces the original's own built pages **180/180
   exactly** from those inputs.
6. `tools/prepare-original-test.py`, changed to read `medium.dtl` at the
   original's fixed offsets, now generates a `ring_page_table` that is
   **180/180 identical** to the pages dumped out of the running original.

`OBJ_RING_STEPS` went from 250 to 180 with it - the object ring search had
been walking 70 entries past the end of a 180-entry table.

This is what eight parameter fits were fitting around: not a scalar that was
slightly off, but the wrong detail level's data read through the right
program's offsets. The silhouette measurement below predates the correction
and needs re-running.

All five inputs are now confirmed against the running original's memory:
`ring_b_table` at `0x19EE4`, `ring_a_table` at `0x1A2CC`, `ring_z_table` at
`0x1AE84`, `ring_page_table` against `00015AD9`'s built pages, and the
backdrop horizon at `0x3CB40` - 180/180, 180/180, 180/180, 180/180 and
192/192 respectively.

**The next question is the marcher's arithmetic, and the harness for it now
exists.** `0000F2F1` copies the finished per-column occlusion to
`[0x19E60] + ring*256 + 0x20` at the end of every ring, so
`--silhouette` captures the original's answer for all 180 rings of a frame.
`tools/compare-marcher.py` scores a model of `0000D950` against it.

Where that stands, stated so nobody has to re-derive it:

```
153 rings scored (27 skipped as uniform)
  ring  27: exact 184/192  mean  -0.29  max|e| 28
  ring  29: exact 167/192  mean  -4.51  max|e| 73
  ring 179: exact  31/192  mean  -1.46  max|e| 21
overall 5308/29376 columns exact (18.1%)
```

**Two measurements narrowed this on 2026-08-27.**

*The reference is 112 columns wide, not 192.* `0000F2F1` writes the main
view's 192-byte occlusion at `[0x19E60] + ring*256 + 0x20`; `0001B84E`, the
side/rear view's own marcher, then writes 80 bytes at `+ 0x58`. Byte offsets
`0x58..0xA7` are array indices 56..135, so the middle 80 columns of every
ring's record belong to the other view. `tools/compare-marcher.py` now scores
only indices 0..55 and 136..191. (The rest of that path restores what it
touches - `00007913-0000793D` pops `[0x19D00]`, the camera and the derived
basis pair back - so registers are only inconsistent inside its window.)

*The marcher is not self-modifying; the emitters are.* Diffing running code
against the image over `0x06BF0-0x0F320` gives 0 patched runs in
`0x0D950-0x0F320` and 382 in the emitters. Static reading of the marcher is
therefore complete and the remaining error is a misreading of code that is
plainly there. Each emitter has two patch sites: the colour-map base in its
`mov al, byte [ebx + 0xFFFF]`, and the `add ch, 0` at +0x12 - which for the
first block is `0x0000AF62`, exactly where `backdrop_build`'s walker stores at
`00007E02`. The backdrop shear and the terrain span start are the same
per-column quantity, written to the sky array and patched into the emitter.
This port's `draw_span` has no per-column term; that is the next difference to
settle.

Restricting to the 112 valid columns did **not** close the gap - 16.1%
overall - and a third round eliminated every remaining structural suspect **by
measurement**:

- **Right renderer.** `000261FE` switches `[0x19C94]` from `0x0000D950` to
  `0x000137F0` unless `[0x25DD9]` is `'}'`. Captured: `[0x25DD9]` is `'}'` and
  `[0x19C94]` is `0xD950`. (`0x137F0` is a second full marcher with its own
  emitter bank at `0x10760`; `0001451D` is its silhouette copy, to the same
  `+0x20` destination. It does not run in this configuration.)
- **Right columns.** Extracting all 192 `cmp ah, byte ptr [esp + N]` sites
  from the marcher gives offsets `0x77`->`0x18` then `0x70`->`0xCF`, which
  against the two stack bases is indices 95->0 then 96->191.
- **Right step order.** Interleaving the sample and step instructions shows
  the descending half samples at the centre then steps, and the trailing
  `sub` at `0x0E5E5` is discarded by the turn's pops before one `add` and the
  first ascending sample.
- **No self-modification**, right page alignment (`[0x19E5C]` is `0x30A000`),
  right height map (`[0x19E6C]`, with the emitter's patched colour base
  exactly 1 MB above it).

**What is actually wrong is the capture's phase, not the model.** The reads
are now atomic - `work/dump_marcher_tables.py` issues QMP `stop` before a
sample and `cont` after, so no capture mixes two frames' *memory*. That is
not the same as sampling at the same point in a frame: the frame driver
latches, renders, then integrates, so at an arbitrary freeze the camera can
already belong to the next frame while the silhouettes belong to the last.
One frozen capture reads camera `0x6A400000 / 0xBB800000 / angle 0x80000000`
- perfectly round mission-start values - against non-trivial silhouettes,
which is that hazard in the open. The score moving between 16.1% and 4.8%
with nothing but the freeze position is the same evidence.

**So the required step is a breakpoint, and only a breakpoint.** Stop at
`0000F317`, the marcher's `ret`, after its last silhouette copy and before
`00007AA0` and the rear-view pass. QEMU's HMP has no breakpoint; the gdbstub
does. `work/gdbstub_probe.py`'s header records that the gdbstub was flaky on
this build - but that was for continuous sampling with `wait=off`, and a
single break-and-read is a different pattern worth trying on its own.

Until that exists, `tools/compare-marcher.py`'s number is not a measurement of
the marcher, and nothing may be tuned to it.

**Superseded reading, kept because it was wrong in an instructive way.** The shape of that result -
near-exact at the first structured ring, decaying with depth, mean error
near -1.5 rows - is the signature of a *bearing* difference, and there is one.
`sub_0001B26C`, called from `00007909` after the terrain render, is a second
marcher for the side/rear view. It recomputes `[0x19CB0]` and `[0x19CB4]`
from `[0x19D00]` for its own direction, and `0001B84E` writes its silhouettes
into the same `[0x19E60]` region `0000F2F1` uses. `00007903` also rewrites
`[0x19D00]`, and `000078FA` subtracts from `[0x19CD4]` - the camera X itself.

Every timed sample therefore captured state already mutated after the pass it
was supposed to describe: the model was driven by the rear view's sin/cos and
scored against silhouettes that may be either view's. The 18.1% figure below
measures that inconsistency, not the marcher.

**The fix is a consistent snapshot, not a better model.** A timed sample
cannot give one; the capture has to stop at a known instruction. Break at
`0000F317` - the marcher's own `ret`, after its last silhouette copy and
before `00007AA0` and the rear-view pass - and dump there.
`work/gdbstub_probe.py` is the existing tool for stopping at an address; the
QMP path in `work/dump_marcher_tables.py` cannot express a breakpoint. Until
that snapshot exists, do not draw any conclusion from
`tools/compare-marcher.py`'s score, and above all do not tune anything to
improve it.

Also worth carrying forward from reading the emitter at `0000AF50`: it is not
a suspect. It stores the new projected row into the column's slot
unconditionally, computes the span length as old minus new, indexes the
unrolled writer at `0x6BF0` by that length, and returns to `0x0000DA05`
without touching the walk's accumulators. It also shows the surface column
encoding directly - the first sampled column writes surface column `0xBF`,
the second `0x3F`, the third `0xBE` - which is the plane-pair doubling.

The original shape of the lead, kept for the record. The first ring with any structure is 184/192
with a mean error of a third of a row, and it decays with depth while the mean
error stays near -1.5 - most columns off by one or two rows, more of them the
further out the march goes. That is an accumulation difference in the ring
centre, not a structural misreading. Ruled out already: the forward and
lateral increments never reach 2^31 in medium.dtl, so `imul` operand
signedness is not it (the depth table at `0x1AE84` does pass 2^31 from ring
128, which is a different consumer and already handled).

**Do not tune the model, and do not tune the port to the model.** Read
0000D9E9-0000DA29 and the turn at 0000E5E9 again for where a rounding or an
extra step differs; the harness will confirm a reading, it must not be used to
search for one.

Two traps are baked into the harness because both cost a step:

- Rings 0 to about 40 are UNIFORMLY ZERO in the reference. A model matching
  them "192/192" has matched a constant - which is exactly how this was first
  misreported. `--min-distinct` skips them.
- The silhouette cannot be recovered from the drawn surface instead: the sky
  is composited into the same 256x256 buffer, so the first painted row per
  column is the sky, not the terrain.

### The backdrop is settled, by capture rather than by fitting

2026-08-27. The silhouette gap below was recorded as needing "more
disassembly", then reclassified as needing a runtime capture because the
tables the transfer at `00007AA0` reads all start at or after `0x32B20` and
the flat content region ends at exactly `0x32B20` - every one of them is BSS.
`work/dump_marcher_tables.py` now takes that capture over QMP.

Two results.

**What `00007AA0` reads is a run list, not four per-column tables.** Read off
the listing: `ecx = word [ebp*4 + 0x38B20]` is a run length with the two
odd-byte plane flags in its high word, `esi = dword [ebp*4 + 0x32B20]` plus
`[dword [ebp*4 + 0x3AB20]]` is the source, `edi = dword [edx*4 + 0x34B20]` is
the destination with `edx = ebp` or `ebp + 0x800`, and the loop runs
`[0x19E4C]` times. The capture confirms it: 261 entries, run lengths from 1 to
82, and 176 distinct source-base pointers eight bytes apart. The earlier
"four per-column tables at 0x32B20, 0x34B20, 0x38B20 and 0x3AB20" reading is
superseded.

**`backdrop_build` is verified exact.** `0x3CB40`'s 192-byte horizon array
dumps directly, and the port's walker reproduces it to the byte at three
independent cameras:

```
marcher-45.json  roll=-133 pitch=  0 lim=  0  mismatches=0/192
marcher-70.json  roll=-111 pitch=  6 lim=  6  mismatches=0/192
marcher-95.json  roll=  27 pitch= 27 lim= 27  mismatches=0/192
```

All three sit on the pitch clamp, and the arrays wrap through 0/255 mid-array
exactly where the byte arithmetic says they should. That is the backdrop
transform, its clamp, both half-sweeps, the turn at `0000968A` and the byte
wrap, all confirmed against the original's own memory.

One honest correction rides with it. The pitch-limit guard removed on
2026-08-27 was a real invention - `00007D98` subtracts into `dl` alone and the
result wraps rather than going negative - but with the roll clamped to +/-133
at `000190FB`/`00019107`, `hi8(|roll| * 0x40)` reaches exactly `0x21` and no
further, so the limit can never actually wrap on this path. The fix is the
correct transcription; it is not a visible bug fix, and this capture is what
settles that either way.

The remaining silhouette gap below is therefore *not* in the backdrop. It is
in the marcher's projection or depth schedule.

**Correction, same day:** the sentence that stood here said the run list was
"the next thing to reduce". It is not, and disassembling its producer is what
showed why. `sub_00006FEF` builds it by scanning the surface row by row for
spans that are not `0xFFFFFFFF` and emitting one run per span - `0xFF` is the
not-painted marker, so the list is an incremental-update mechanism that says
which spans changed, and carries no projection information at all.

What that disassembly *did* settle is the anchor. `00006FEF` starts its source
at `[00019E70] + 0x2011` - surface row 32, column 17 - and its destination at
`[000014C4] + 0x39FA`, which is VGA row 181 exactly (`0x39FA / 0x52 = 181`).
It walks `0xB6` = 182 rows with the source row increasing and the destination
decreasing by `0x52`, so

    screen row = 181 - (surface row - 32) = 213 - surface row

confirming `RING_PAGE_ANCHOR`/`OBJECT_PAGE_ANCHOR` = 213 from the producer
itself rather than from the transfer's shape. `000055DE` also fixes the
surface once at `(0x0004CC20 & 0xFFFF0000)` = `0x00040000` and never moves it.

**The per-pixel surface oracle now exists.** `--surface --shot --wait-flight`
dumps the original's 256x256 terrain surface together with the camera that
drew it and a screendump that proves what it is. Two guards were needed and
both earned their place:

- **Residency.** The replay-mode flag read as 1 at 3.5 seconds, before DOS had
  finished booting, and the first "capture" was uninitialised memory. The tool
  now waits until 16 bytes at flat `0x25880` match `comanche-flat32.bin`
  before believing any read.
- **Replay mode.** `[00019ED0]` is 1 only while a `DEMO<n>.SCR` replay plays
  (`00019A4E` sets it, `00018C87` and `00019AF4` clear it, `000199B5` uses
  `0xFFFFFFFF` for recording). That is the only reliable "we are in a terrain
  flight" test.

One misreading is worth recording with them, because it nearly sent this the
wrong way. "Fraction of the window painted" looked like it should separate
terrain from a full-screen image, and a good terrain frame turns out to be
~90% painted - the sky is drawn into this same surface, and only spans no
writer reached stay `0xFF`. A high figure is not evidence against terrain. The
screendump is what settles it, which is why the tool takes one.

A captured frame: camera `x=0xFE5CE640 y=0x40759FD2 angle=0x4EE24A19
alt=128`, 261 runs, 88.3% painted, with `screen-11.ppm` showing the original
in cockpit view over lit terrain.

What remains is the comparison itself. `tools/compare-silhouette.py` is
retired - it depended on the removed pinned-camera build - so the surface dump
needs either `tools/compare-terrain.py` taught to read a raw 256x256 surface
instead of a PCX, or a small comparator of its own. The dump is the better
input of the two: no PCX decode, no palette round trip, and the camera that
drew it is in the JSON beside it.

### The terrain has a number now, and it is not a good one

2026-08-17. Both cameras pinned, so this is the first measurement of this
port's terrain against what COMANCHE.EXE draws rather than against a model of
the port.

**Pinning.** `PIN_CAMERA=1 bash tools/oracle-capture.sh` freezes the original
at DEMO0's start record - twelve NOPped sites, and its late frames are
byte-identical to each other. `--demo-camera` prints that record: X 511.3,
Y -147.0, angle `0x094E1776`, alt 80. Positions transfer unconverted, because
both renderers index the same map the same way. The heading does not: the DOS
accumulator's top nine bits index a 512-entry table where this port's heading
indexes a 256-entry one, so it halves to 9 - and then becomes `128 - 9 = 119`,
because DOS heading 0 faces -Y and this port's faces +Y. That conversion was
already on record under *Mission-driven spawning, and the axis convention*.
Taken literally at 9 the two cameras point 100 degrees apart and the diff
measures the mistake; at 119 the two frames are recognisably one place.

**A colour diff does not work yet** and the reason is not the geometry: it
comes back 100% differing with zero exact matches at any vertical offset,
because the original shades its palette per depth and this port renders
C1.DTA's entries flat. Until the ramp is reproduced, colour says nothing.

**So the measurement is the silhouette** - the first non-sky row per column,
which depends only on the projection, the depth schedule and the camera.
`tools/compare-silhouette.py`:

```
port minus original : mean -32.64 rows, median -34, stdev 21.44
  exact  1%   within 2 rows  7%   within 5  18%   within 10  23%
```

The port's terrain stands about **33 rows too tall**, and the 21-row spread
says it is not a simple offset - the shapes differ as well.

**It is not the new marcher.** Running the same pinned camera through the
column-major path gives mean -32.44 and stdev 21.38, and the two port
marchers agree with *each other* to mean -0.20 and stdev 0.85 with 69% of
columns identical. So the fault is shared, older than either, and lives in
what they have in common: the projection constant, `horizon_table`, or the
altitude term. Camera height is the cheapest to rule out - `PROJ_SCALE` at
150 and the `alt/2 + 1` term are both recovered but neither has ever been
checked against a frame the original drew.

**What the number is not.** Four explanations were tested and eliminated:

- *The new ring-major marcher.* The column-major path at the same pinned
  camera gives -32.44 and 21.38, and the two marchers agree with each other
  to mean -0.20, stdev 0.85, 69% of columns identical.
- *Residual camera error.* This viewpoint sits in a valley with close ridges,
  so it was reasonable to suspect that a small position error was being
  amplified. It is not: moving the port's camera one whole map unit in X
  changes its own silhouette by stdev 1.07 rows, with 65% of columns still
  exact and 97% within two. A one-unit error costs one row, not thirty-three.
- *Camera height.* Raising `BENCH_ALTITUDE` from 80 to 128 improves the mean
  to -17.6 but worsens the spread to 28.6, and 64 worsens both. It trades
  offset against shape rather than fixing either, which is not what a wrong
  camera height looks like.
- *A horizontal scale error.* Compressing the port's silhouette about the
  centre finds a best factor of 1.38, but the spread only moves from 21.44 to
  21.15. Nothing is corrected.

So it is neither camera nor loop order nor a simple similarity transform. It
is shared by both marchers, which leaves what they have in common:
`PROJ_SCALE` at 150, and `horizon_table` - the per-depth bias curve.

**Both of those are now eliminated too, and the way they failed is the
useful part.** `FLAT_HORIZON=1` in `prepare-original-test.py` holds the curve
at `SCREEN_HORIZON` while leaving z and 1/z on the DTL's values. Doing so
changes the frame by **54 pixels** and the silhouette statistics not at all,
because the curve is only 138 at the nearest rings - which sit behind the
cockpit - and converges to 62-69 within about eight of them. Over the visible
depth range the original's horizon curve is already flat, so it cannot be
what bends this port's terrain. And `PROJ_SCALE` moves the mean without
touching the spread: 150 gives -32.6/21.4, 100 gives -25.1/23.4, 75 gives
-19.0/22.2.

That is the signature to reason from. **Every parameter tried moves the mean
and leaves the spread at 21 rows**: altitude, projection scale, horizon
curve, horizontal rescale, and a pure bearing shift (whose best fit is a
shallow, noisy minimum at -75 px rather than the sharp one a rotation would
give). A discrepancy that survives every similarity transform is not a
mis-set constant in the projection - the two silhouettes differ in shape.

Two more were tried after that and behaved the same way. The **fan
half-width**: `00007AA0` sets the VGA Map Mask to `0x0302` - planes 0 and 1 -
copies a run, then `0x0C02` for planes 2 and 3 and repeats, which in Mode X
writes each source byte to two adjacent pixels. So a terrain column IS exactly
two pixels after all, the 1.71 reading above was wrong, and the original's 192
columns span 384 pixels of which the 328-wide screen shows the middle. Setting
`FAN_HALF_TAN` to `0.96 * 320/384 = 0.80` to match that visible angle gives
-29.6/23.3 against -32.6/21.4. And the **collision position restore**: the
freeze had held the altitude write at `0001943D` but not the X and Y restores
at `00019429`/`00019433` two instructions above it, so a single ground contact
could have moved the camera off the demo's start. Freezing those too changes
nothing - and confirms the camera was already pinned, because the captured
silhouette is identical across every settled frame.

**Eight parameters, one behaviour.** Camera position, altitude, projection
scale, horizon curve, horizontal rescale, bearing shift, fan half-width and
the collision restore all move the mean and leave the spread at 21-23 rows.
That is the finding, and it is a negative one: whatever is wrong is not a
scalar in the projection, because no scalar in the projection can change the
shape of a profile.

Which points at what is being measured rather than what is drawing it. The
comparison takes the original's **left 320 columns** of a 328-wide frame, on
the reasoning that the DOS view is that window; and the fill at `00016EC0`
writes its 192 terrain columns to byte offsets 16-111 and 144-239 of a
256-byte row, which is not obviously the full screen width. If the original's
terrain viewport is narrower than its frame, or centred rather than
left-aligned, the two silhouettes are sampling different bearings per column
and no camera parameter will ever reconcile them. Establishing that mapping -
which screen columns the DOS terrain viewport actually occupies - is the next
step, and it is a question about the fill's geometry rather than about the
renderer.

### Camera state audit and display-window correction

Verified 2026-08-24 against the running DOS replay. The DEMO0 start state and
the port's `flight_tick` transcription were stepped with the recorded inputs,
then compared with DOS memory snapshots from the active demo. DOS snapshots
004 through 018 match the port at ticks 11 through 291 exactly for raw X, raw
Y, full angle, altitude, forward velocity, and lateral velocity. The apparent
Falcon view being several metres forward is therefore not a flight-integration
or camera-position error; changing the camera position would make the replay
less faithful.

The remaining camera-adjacent discrepancy recovered from the DOS Mode X
transfer is presentation geometry: the high-detail marcher emits 192 source
columns, each expanded to two pixels, and the page-aligned 320-pixel display
window shows source columns 14..173. The port had been presenting 16..175.
`src/dsp/proto.inc` now uses 14..173 for the CPU, DSP host, and DSP kernel, and
bumps the shared command version so stale geometry cannot handshake silently.
**Reversed 2026-09-22:** the display starts at page x 4, not 0, so 16..175 was
right. See "The second pair" and `X86-M68K-MAP.md`, "The column mapping, end
to end". This is a four-pixel horizontal correction, not a behavioural camera offset;
the 21-row silhouette discrepancy recorded above still needs a same-state
pixel capture after the palette/backdrop parity work.

## The target machine is the 14 MB Falcon030

Settled 2026-08-17. The Falcon030 shipped as 1, 4 or 14 MB of ST-RAM and this
port targets the largest of the three. That is a decision, not a deferral: it
buys the two 1024x1024 maps at full resolution, the sky's whole 512-strip
panorama and a decode staging buffer that never has to be freed, and the
alternative was spending engineering on a smaller footprint instead of on
fidelity.

What it costs is the common machine. Measured under Hatari at
`--memsize 4 --ttram 0`, a 4 MB Falcon completes its memory test at 4096 KB
and then never starts `comanche.tos` - the boot screen sits there unchanged.
`release/comanche.map` says why: **4.45 MB of BSS** against 4,194,304 bytes of
ST-RAM, so the program cannot load before TOS takes a byte of it. 8 MB runs,
but 8 was never a factory configuration, so on real hardware this is a 14 MB
machine or nothing.

Where it goes:

| Object | BSS | What |
|---|---:|---|
| `render.o` | 2,097,838 | the two 1024x1024 original maps |
| `sprite.o` | 773,360 | sprite banks and the sky's 512 strips |
| `resources.o` | 700,002 | `RESOURCE_BUFFER_BYTES`, the decode staging buffer |
| `dsp_host.o` | 327,818 | |
| `start.o` | 324,796 | two 320x240x16 screen buffers |
| `attract.o` | 301,396 | |

If a 4 MB build is ever wanted, the route is known and none of it touches
fidelity: the staging buffer is transient by construction - sized for "the
largest pair of terrain maps at 661,796 bytes; the sprite loader reuses it
afterwards" - so it is live only across load and could be overlapped with a
buffer already allocated, or released before the first frame. That alone
lands the total near 3.75 MB. Recorded so the option stays open; not on the
roadmap while 14 MB is the target.

### Matching the two sides by time does not work, and here is the evidence

Recorded so the next attempt does not repeat it. With the original pinned to
attract pass 0 it flies DEMO0 on the D1/C1 pair - the same map the port has -
so both sides run the same recorded flight and it is tempting to find the
same instant in each and subtract. Two ways were tried and both fail:

1. **By search.** Score every port frame against every captured DOS frame on
   a luminance signature over the terrain band. A coarse port sweep, eight
   frames 150 VBLs apart, gave a best pair at 14.07 mean luminance. Refining
   to sixteen frames 10 VBLs apart - fifteen times finer - moved it only to
   12.33. A residual that barely responds to sampling density is not sampling
   error, and 12 of 255 is far above the two or three units palette rounding
   would explain.
2. **By tick arithmetic.** The DOS capture writes one frame in three, so
   `SNAP_n` is demo tick `(n-17)*3`; `SNAP_233` is tick 648, which against a
   demo starting near VBL 1870 should be the port's VBL 2518. Capturing
   2450-2600 scored *worse*, 15.35, with the best pairs scattered across
   `SNAP_020`, `SNAP_035` and `SNAP_235` - no coherent minimum at all.

The reason both fail is the same: rolling terrain is self-similar, so a
whole-frame signature cannot tell one ridge from another, and the landscape
of scores is flat wherever you sample it. Any number produced this way
describes the search, not the renderer.

**So the camera has to be pinned, not found.** The pieces are on record: the
demo loader at `00019A2D` reads the start record into `[00019CD4]` X,
`[00019CD8]` Y, `[00019D04]` heading and the byte `[00019DFC]` altitude,
parks its cursor in `[00019ECC]` and zeroes roll and pitch, and the port has
`BENCH_X`/`BENCH_Y`/`BENCH_HEADING`/`BENCH_ALTITUDE` for the same job. What
is still missing is which routine advances `[00019CD4]`/`[00019CD8]` during
normal flight - the writers reachable by name sit inside the rear-view block
at `00007886`-`00007931` and handler 6 at `00007C26`, neither of which is the
main path. Find that, hold the four globals at the demo's own start values,
build the port with `BENCH_*` from `--demo-camera`, and the comparison
becomes a subtraction.

### The depth schedule is three flat tiers where the original is a curve

Measured 2026-08-17 from `HIGH.DTL` itself. Table 4, read **unsigned** in
10.22, is the cumulative depth - signed it wraps negative at the far end,
which is what made an earlier reading accumulate table 0 instead and get
861.9. Read correctly it gives **250 steps to 985.2 map units**, and the step
grows as a smooth curve:

| z | 10 | 25 | 50 | 100 | 200 | 400 | 600 | 900 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| original step | 0.74 | 1.20 | 1.69 | 2.39 | 3.40 | 4.79 | 5.89 | 7.19 |
| port step | 1 | 1 | 4 | 4 | 16 | 16 | 16 | 16 |

**The far distance is not the problem** - 992 against 985.2 is 0.7% and the
`MARCH_*` comment in `proto.inc` was right about it. The problem is the
sampling between here and there. `MARCH_NEAR_STEPS` 32 at one unit,
`MARCH_FAR_STEPS` 24 at four and `MARCH_FAR2_STEPS` 54 at sixteen cover the
range in **110 steps against the original's 250**, so the port is 1.5-3x too
coarse through the mid field and 2-5x too coarse beyond 128 units, and it
changes rate in two abrupt jumps where the original ramps continuously. That
is what reads as a different level of detail: terracing at the tier
boundaries and a blocky far field, on a draw distance that is otherwise
correct.

**Why the tiers exist, and what 1:1 actually costs.** The original is
ring-major: the function map's own row for `0000D950` says the outer loop
walks the 250 depth rings and the inner walks all 192 columns of one ring.
So a ring's step is computed once and spent across every column, and a
depth schedule read from a table costs the original nothing at all.

`src/render.s` is the other way round - `.column` is the outer loop and
`.depth` the inner - and in that order a per-sample step is a multiply per
sample **per column** rather than per ring. That is what the power-of-two
tiers buy: `lsl.l` at two boundaries instead of 160 multiplies per depth.
The tiers are not a shortcut somebody took instead of reading the table;
they are what the table costs in a column-major marcher.

So making the schedule 1:1 means one of:

1. **Restructure the marcher to ring-major**, as the original is. Then the
   `.DTL` drives the march directly and for free. It also makes two other
   recovered behaviours natural rather than awkward - the original archives
   each ring's horizon array as the sprite-clip silhouette, and the emitter's
   `[old, new)` span convention is expressed per ring. This is the honest
   target and it is a rewrite of the inner renderer, not an edit.
2. **Keep column-major and pay the multiply**, which is measurable but two
   costs at once: 250 samples against 110 is already 2.3x the marching work
   before a single `muls` is added.

Either way the frame time moves a long way, so this wants measuring against
the 17.37 FPS the current schedule holds rather than assuming. `MEDIUM.DTL`
carries 180 steps to 618 units and `LOW.DTL` 100 to 357, so the same table
supplies the two lower detail levels the runtime selector still owes, and
both of those are cheaper than HIGH - which is the point of them.

### What the terrain renderer still owes the original

**Closed 2026-08-31, except one, and that one is blocked on recovery rather
than on work.** Taken in order:

1. The backdrop *is* the original's: `backdrop_build` was verified 192/192
   against `0x3CB40` on 2026-08-27, and the one term it was still missing -
   `00007DB5`'s screen shake - is now carried too. `flight_shake_tick` ports
   the timer ISR's generator and countdown at `00001DB5-00001DE7` and
   `00019461` arms it again on the no-damage bounce. The phase's two other
   consumers are VGA display hardware (`00001DF1`'s pixel pan, `00015BBC`'s
   CRTC start) and stay out; the tick rate is the platform boundary, recorded
   at the routine.
2. Detail levels are no longer collapsed **for the schedule**. `src/dtl.s`
   loads the `.DTL` the settings byte `[0x25DD4]` names and rebuilds the ring
   tables and the 256-byte projection pages from it - `00015AD9` ported
   directly - so the Detail menu selects 250, 180 or 100 depth rings instead
   of writing a byte nothing read. `ring_steps` replaced the build-time
   `RING_STEPS` everywhere a ring is walked; the constant is now only the
   storage bound. Measured: forcing HIGH.DTL gives `ring_steps` 250, all 250
   forward increments equal to the file's own table 1, and all 64,000 page
   bytes equal to an independent model of `00015AD9` run on that file.
3. The flight HUD was restored earlier and is unchanged by this.

4. **The two option toggles are ported too, and the composition they needed
   is no longer an open question.** This was recorded here as blocked on RE.
   It was not; it needed a watchpoint.

   `[0x25DD9]` swaps the 192-column marcher `0000D950` for the 96-column
   `sub_000137F0`. That routine is the same marcher with the lateral step
   doubled *before* the product (`shl eax,1` at `00013862`/`00013873`, and
   `high32(2B*sin)` is not `2*high32(B*sin)`), 48 samples per half sweep, and
   an emitter bank at `0000F320` whose blocks carry **two** occlusion stores
   instead of one - so a marched column owns the pair `(c, c+1)`.

   Its presentation was the piece that looked missing. The 96-column emitter
   bank carries compose bytes 16..111 only - block A - and so does its sky
   fill `00016EC0`, yet a capture with `[0x19C94]` poked to `0x000137F0` shows
   block B freshly written and byte-identical to block A (17469/17472 of the
   visible field, against 14051 on the 192-column path where the two blocks
   genuinely differ). A write watchpoint on one block-B byte named the writer
   in one run: **`0001453D`**. After the ring loop the 96-column marcher runs
   an unrolled `rep movsd` of 0x18 dwords - 96 bytes - from `surface+0x10` to
   `surface+0x90`, stepping both by 0xA0 so the pair advances one 256-byte
   row, for all 256 rows, ending in the `ret` at `00015854`. It copies block A
   over block B, which is how one marched column reaches four screen pixels
   through the transfer's two plane passes. The port writes the four pixels
   directly instead of copying a block, which is the same picture.

   `[0x25DD8]` is not a "fill family" - it is **sky on/off**. `000261AF`
   installs `0x1757E`/`0x1CAD0`/`0x1757E` in the three fill slots and only
   replaces them with the sourced fills `0x17230`/`0x1C920`/`0x16EC0` when the
   byte is `'}'`. `0001757E` is a flat viewport fill: `rep stosd` of
   `[0x2A37E]` - a capture reads it as palette entry 255 - 96 bytes, skip 32,
   96 bytes, skip 32, which is both compose blocks of every row. Wiring it
   also fixed a real divergence: `00016EC0`/`00017230` open with
   `or esi,esi / je 0x1757E`, so a missing sky bank falls through to that same
   flat fill, where this port returned without painting anything and left the
   previous page showing.

   The third emitter bank, 40 blocks at `0001C1A0` with the fill `0x1C920`, is
   **not** a third detail level for the main view: `[0x19C9C]` is read at
   `0001B29C`, inside `sub_0001B26C`, so it belongs to the MFD target view -
   which this port already carries separately.

**Nothing on the terrain renderer is open.** The main view has exactly two
column configurations and both are certified against the original's own
silhouette archive; see the Status note on `render_terrain_ring`.

The three gaps as they were first written, for the record:

1. **The backdrop is not the original's.** The original draws a rotated,
   pitch-offset horizon from `00007D60`/`00007DC3`; this port blits `SKY2.RLE`
   flat from the image's top. The marchers themselves never read pitch, so
   this is backdrop work - see *What "the renderer has no pitch" actually
   means* in `X86-M68K-MAP.md` for what has to be recovered first.
2. **Detail levels are collapsed.** The original ships three marchers chosen
   by the settings byte `00025DD4`; the port has one routine whose column
   count is a build-time constant, and the Detail menu lines now set a value
   nothing reads.

   Corrected 2026-08-17: the build-time constant was also set to the wrong
   value, and "highest" was never the original's highest. Horizontal run
   lengths in the terrain band of the game's own screenshots are
   overwhelmingly even - 2px 2839, 4px 860, 6px 385, 8px 190, against 582
   single-pixel runs - so the DOS renderer puts **one terrain column on two
   screen pixels**. `TERRAIN_HALF=1` reproduces that distribution almost entry
   for entry (2px 2788, 4px 1364, 6px 344, 8px 240); the old default
   `TERRAIN_HALF=0` inverts it to 4745 single-pixel runs and renders the field
   at twice the resolution the original ever had. Both build scripts now
   default to 1. The name is a leftover from when 320 rays was assumed to be
   the target - 0 is the finer-than-DOS mode, not the faithful one - and
   renaming it belongs with the runtime detail selection this gap describes.
   It is also 1.63x faster: 17.37 FPS at 57.6 ms against 10.68 at 93.6.
3. **The authored flight HUD is now restored from the DOS calls.** `HUDS.RLE`
   is staged and loaded as its own bottom-first column-major bank, separate from
   `CONS.RLE`; the Falcon loader reverses each column once into top-down order.
   `src/hud.s` ports the `0000D703-0000D852` path and `0000D8F5`: the compass
   marker and heading window, `SPEED` label and digits, clearance ladder and
   value, velocity-derived centre ring, and the `00025CA2` green sight line.
   The fixed console elements `0x09`, `0x25`, and `0x39` remain at the DOS
   coordinates from `00007403`/`00007443`/`000077BE`. The old fabricated bars,
   ticks, and cockpit geometry are not used. The `0000D88C` tail is phase-gated
   through the recovered `COMA.RLE` bank exactly as DOS, so attract phase 1
   does not draw the large helicopter; its later branch remains null-gated
   until the event graph populates its value tables.

   Removed with them, from `src/main.s`: the frame counters painted into rows
   0-5 now build only under `TELEMETRY`, which defaults to `BENCHMARK_CAMERA`.
   The DOS program draws nothing there, so an ungated build could not be
   diffed against the original at all. `tools/read-telemetry.py` still reads
   them from any `BENCHMARK=1` build, and `TELEMETRY=1` forces them on
   without pinning the camera.

The oracle for the terrain now exists, and it needed no new DOS-side
harness: the game writes its own 328x240 PCX screenshot when the developer
key sequence is enabled - see *The game will take its own screenshot* in
`X86-M68K-MAP.md` - and `tools/compare-terrain.py` diffs it against a Hatari
capture. What is left is to run it: place both sides at the same viewpoint
(`--demo-camera` prints the one DEMO0.SCR starts from, and the port's BENCH_*
defines pin it), capture each, and read the number. Until that is done the
paragraph below still describes the state of the evidence.

Formerly, and still true of every figure quoted before this point: **there was
no oracle for the terrain.** Every pixel-exact figure on record compares the DSP
kernel against this port's own CPU renderer, or the port against
`tools/render-node-reference.js`, which models the port. Nothing compares
either against what `COMANCHE.EXE` draws. Building that - a pinned-camera
DOSBox capture of the Mode X page against a Hatari capture of the same
viewpoint, using the TSR pattern `tools/dosbox` already has for the DAC - is
what would turn "is the renderer complete?" into a number instead of an
opinion, and it should come before more renderer work, not after.

### The menu layer, in the order its pieces depend on each other

Phase 5's gate needs menus, and the attract cycle now ends where one begins.
The leaf is done: the text engine at `00027034` and the `KF4b` font are
ported and verified pixel-exact (`src/menu.s`,
`tools/render-menu-ref.py`), and the in-flight options bar at `000265C0`
draws over the flight view on Escape, recording its five hotspots. What that
opened, in dependency order:

1. ~~**The four drop-down panels**~~ - done. The bevelled translucent box,
   the bar and row highlights, the group walk that computes row counts and
   widths, the separator skipping and the arrow-key navigation are ported and
   verified line by line against the oracle. Choosing a line is ported too:
   all seven boolean options through
   `00026AB6`'s `xor al,6` on the brace inside the string, and all four radio
   groups with their marks poked from the settings before every redraw. What
   remains are the Game column's four lines, which no dispatcher case covers
   because they belong to the shortcuts printed in their own text - Escape
   already serves Return to Game - and the **effects** - the detail level feeds the renderer selectors
   at `0002617A`, the volumes wait on the audio phase, and the controller type
   waits on there being more than a keyboard - and **Save Menu Settings** and
   **Abort Mission**, which want a settings file and a mission-end path.
   Choosing one of those does nothing rather than something invented.

   Note the menu is only operable in free flight: during the attract cycle any
   key leaves the attract, which is what the DOS build does, so there is never
   a demo running under an open menu.
2. **The pointer and cursor-key selection model** at `000264C4`/`00026F27`,
   which are the only readers of the hotspot records this port now writes.
   Still open, and now the only open item in this list - which corrects the
   dependency order the list is named for. Items 3 and 4 landed without it, so
   it was never a prerequisite for them: the screens are driven by the arrow
   keys and Return that the list driver reads itself, and the pointer is a
   second input path onto the same selection rather than the thing the
   selection is built on.
3. ~~**The pilot-select and main-operations screens**~~ - done, and they came
   in as one routine rather than as two screens. `00027DB4` is the list-menu
   driver the original's whole out-of-flight flow is built on: main operations,
   campaign select, mission select and the briefing's accept/reject pair are the
   same code pointed at different sections of the text block at `00029B2C`, and
   the pilot roster is that same driver pointed at `COMANCHE.NAM`'s own records.
   `src/screen.s` ports it as a per-frame state machine, because the original
   blocks on the retrace wait at `00015B78` and this loop cannot. The box
   geometry, the `0xFA` row-count seed, the selection wrap and the `[00027DAD]`
   pilot sub-mode that makes one fixed geometry serve both layouts are all the
   listing's. Credits (`00028DB5`) came with them - the first menu screen that
   is not a list at all.
4. ~~**The attract exit**~~ - done. It lands on the main menu, where the
   original goes, instead of in free flight.

### The end of a flight (2026-10-07)

Every way a flight ends lands at `0002873D` (`mission_end`, `src/debrief.s`): the
abort keys Alt+A / Alt+Q at `000189C2` (`input_session_keys`), an empty tank at
`00018E23`, the wreck at `00018EF6` (reached through the player damage chain,
`000194A3`/`00018EE3`, ported 2026-10-07) and the options bar's Abort Mission at `00026E09` (not
wired). It runs the statistics `00028261` (`mission_stats`), clears the object
table (`000227A6`, `object_clear_active`), and then takes one of three roads
on `[00019ED4]` / `[00019D91]`: the attract's next pass, the menu, or the pilot's
record and the debrief.

* **Statistics** - goals destroyed, hull, enemies killed, weapons and fuel
  remaining, the score they add up to and the sentence chosen
  (`00028261`, `000286F9`, `00028C25`). Checked against the original at two
  DEMO1 cursors with Alt+A poked into both machines
  (`work/trace_mission_end.py` / `tools/...` `--poke`), and against a live
  300-frame abort (`work/trace_mission_live.py`): every field and the text equal,
  except where the original's player hull has taken a hit the port's damage
  chain does not yet apply (score 2032 against 1913 at cursor 2405, all of it
  the 7% of hull).
* **Pilot record** (`pilot_record_lost`, `pilot_record_won`, `roster_sort`,
  `roster_format`, `roster_save`) - the won/lost branches of `000287E2-000289F2`,
  the ranking sort `00029F36` and its digit refresh `0002A0AD`, and the write
  of `COMANCHE.NAM`. The roster's dwords are little-endian (the DOS file) and are
  swapped on use. Checked on abort and on a crash (kills added, nothing else);
  the won branch and the setback branch are transcribed and **Unproven**.
* **The score screen** (`SCR_ID_DEBRIEF` in `screen.s`) - the picture
  (`lose3.dta` / `win3.dta`), the `0002628E` box and the patched text, until
  Escape, then the main menu. Measured against the original's own PCX of it.
* Findings that fixed the menu screens too: the picture a menu-chain screen shows
  starts at page column 4 (the CRTC starts one byte in), `0002628E` draws the
  bottom bar on row h-1 with a two-row black shadow and left/right edges
  (the old box was a row too tall), the list highlight is `00026FD9`'s flat
  fill and not a box, and `ah=2` at `00027E5E` / `00028A6B` starts the text pen
  on pixel 1 of its byte. The box interior is still halved per RGB565 pixel
  rather than through `0002AA18`'s nearest-palette table, and the named colours
  are the exact triples: both documented platform differences.

No synthetic flight exit is installed. `Q` is ordinary unmapped input until
the DOS options-bar Abort Mission chain at `00025DEF`/`00027DD2` is ported.

### The mission list's gate, the briefing and the loading box (2026-10-07)

The list no longer starts the mission. `src/screen.s` now follows `00028F3F`:

* **Row colours** (`screen_mission_colours`, `00028F46-00028FBA`): blue once flown,
  green for the next, orange for a starred row whose predecessors are not all
  flown; the letter goes into the row's markup and into `[00029F22]`
  (`screen_mission_ink`). The list opens on the pilot's last choice
  (`00028FBA-00028FE1`).
* **Locked rows** (`00029016`, `00026E90`): an orange row is turned away with
  "You must finish GREEN missions." over the bare picture, any key returns.
* **Briefing** (`briefing_build`, `00029063-00029119`; screen `0002936C-000294D2`): the
  name and the description wrapped to 0x118 with the font's own widths, a flat
  highlight over "I accept / I reject this mission", Escape and reject go back to
  the list, accept puts up `Loading Mission...` (`000294D7`) and only then starts the
  mission. Wrap checked line-for-line against the original's own PCX of the
  screen (`build/frame-pair/dos-menu-brief`); 58509 of 76800 pixels identical, the
  rest the documented box darkening.
* Fixed on the way: the list drew a second highlight on the last row whenever the
  first was selected (`menu_fill` clobbered the marked-line register).

The options menu's Game column is complete too (2026-10-07): **About Comanche**
(`00026E21-00026E8F`, over the bar, until a key) and **Save Menu Settings**
(`00026D8B-00026DF8`: the 35 bytes at `00025DBC` to `Comanche.MNU`, then "Menu Settings
Saved"). The toggle cases also store the flipped brace into `[00025DD8 + n]`
(`00026AC6` and its six siblings), which the port had left in the menu text alone while
the renderer's gates read the settings block.

The main operations menu is complete as well: **Your Stats** (`00028B37-00028C20`: the
template at `00028AB5` patched with the pilot's name, score, victories and kills, right
aligned by `00028C25`) and **RAH-66 Overview** (`00028DFE-00028EC1`, the side screen's own
ZOVE animation without its count, until a key - `attract_overview`).

**New pilots** (`0002800C-000281FE`): Return on an empty slot, or Delete on any, opens
the name box ("Enter Your Name:", `ah=1`, at most 0x16 characters and 0x6C pixels, the
unshifted and shifted tables at `000019E9`/`00001969`), and Return writes the record
(head, name, tail, cleared progress and flags), ranks and saves. The keys come through a
port of the DOS key queue `[00001B70]` (`key_queue`, newest in the low byte).

Not ported: the pointer and Tab paths of the list driver.

### The JavaScript reference catches up (2026-10-07)

The five ports above and the player damage chain were written from the listing
into `src/` first. The executable reference now has them too, derived from the DOS
listing and used the other way round - the 68030 sources were read afterwards as a
cross-check. `jsComanche/dos-pilot.js` (statistics, pilot record, ranking, roster
layout), `dos-menu.js` (mission list scan, row colours, lock, briefing wrap, Your
Stats, options toggles and Game column, name entry), `dos-damage.js` (death block,
engine, T gauge, tail rotor, crash response, object collision) and the data module
`dos-text-data.js` carry them as pure functions over explicit state, with function
records `#mission-end-statistics`, `#mission-end-route`, `#roster-ranking`,
`#player-damage-chain`, `#mission-list-scan`, `#mission-list-gate`,
`#mission-briefing`, `#menu-your-stats`, `#menu-options-game`, `#pilot-name-entry`
and `#menu-text-data` in `analysis/functions/browser-attract.md`. The gate is
`node tools/prove-browser-attract.js`, which runs `tools/prove-browser-menus.js`.

Checked against DOS captures (`work/replay_dos/mission-end-c213.json`,
`mission-end-c2405.json`, `mission-live-abort300.json`, `mission-live-win300.json`):
the statistics' patched score screen and counters byte for byte, and the pilot record
update, ranking and debrief text of a live abort **and a live win** (the won path was
recorded above as Unproven; it now agrees with the original over the whole roster).
The player damage chain was checked against the original too, with a new probe that
pokes damage state at a breakpoint (`work/trace_player_damage.py`, see
`docs/DOS-ORACLE.md`): 26 of 26 crash tails exact including the RNG they stirred, a
100-record wreck, a sinking wreck, a damaged engine and tail rotor over 60 ticks, and
37 of 37 object-collision samples (`node tools/check-js-damage.js`). Not checked
against DOS: the drawing (boxes, text placement, the file write's own bytes). Everything else
named above was also run in the original directly with random inputs
(`work/dos_call.py`, `node tools/check-js-dos-calls.js`): the statistics (80 cases),
number and percentage writers, ranking sort (61, which reorders), both pilot-record
paths (160, including the promotion stamp and the setback walk), mission-list scan,
decode and line skipper, the briefing wrap (60), row colours and list choice,
Your Stats, the option toggles and the name entry (36 scripted sessions) - all agree.

**Historical 2026-10-07 native audit (DOS wins).** The first two readings below
were corrected by source inspection and the 2026-10-10 native checks; the
remaining bullets retain their dated audit scope rather than certifying current
code. Current corrections are recorded at the top of this plan.

* Withdrawn: "`roster_sort` swaps the whole 43-byte name record." Its name
  exchange was already 40 bytes; the actual native defect was rounding the
  ten-byte campaign rows down to eight bytes. Stride/exchange lengths are now
  separate and all 41 DOS roster cases pass on both CPU cores. The last three
  name bytes remain with their seat, as DOS does.
* Withdrawn: "`src/flight.s` has nothing for `000192EE-0001934F`." The existing
  native collision block implements that test and now matches 37 recorded DOS
  decisions on both CPU cores. This checks the branch decision, not crash
  aftermath or a connected live mission. The browser's flight collision remains
  dormant because its mobile-object wall-clock RNG is not DOS-exact.
* `flt_crash_drop` (`[00019DC4]`) is never zeroed by a view selection (`0001687D`,
  reached from `000196CF` by all seven select cases) or by `0002873D`; the original
  zeroes it at both (and `[00019DBC]`/`[00019DC0]`, the shake phase and countdown, at
  `0002874D-00028757`, which `mission_end` also leaves alone). The same `000196B4` entry also clears the target latch and the
  threat blip for the two external-camera keys, which the JavaScript had left alone
  and now clears (the DOS object fixtures are unchanged).
* `pilot_record_lost`, `pilot_record_won` and `pilot_record_done` skip the update when
  `roster_ok` is clear; the original has no such test. After the wreck's countdown
  reaches zero `flight_tick` carries on with the tick (`00018EF6` leaves at once).
* `screen_fill_missions` writes a 0 at the last byte of a mission slot even when the
  title fills it (`0002A286` writes none) and guards its scans against the stream end.
* `mission_target_count` is a word; `[00028260]` is a byte. Neither shows in the
  shipped missions.

The briefing fixture the project notes give - the original's four lines "If you're
going to see the world, ..." - is the first mission of **1.MIS** ("Werewolves on
Patrol"), the file the pilots' campaign byte selects, not of 0.MIS (whose first
mission is "Oil Tank Holiday"). The JavaScript wrap reproduces those four lines
exactly.

### The wreck's sinking window (2026-10-07)

`[00019DC4]` rises 0x52 - one 82-byte page row - a tick while a wrecked hull's rotor is
stopped (`00018F5F`), and `00015BC9` adds it to the CRTC start, so the picture slides UP
the page; `0001687D` (every console blit, so the view change at 45 rows) zeroes it. The rows
the window slides into are not unknown: a capture of the original at 40 rows of sink
(`work/trace_player_damage.py --scenario wreck --screendump-drop 40`) shows the lower rows of
the console image, which `0001687D` blitted below the page's 240 (the dark panel, the knob
cluster, the seat). `console_rgb` now caches all 290 rows and `shake_present` reads rows
240.. from it - which also replaces the edge replicate at the bottom of an ordinary shake.

### Output-exact sample skipping, measured (2026-10-07)

The hypothesis in `docs/PERFORMANCE-2026-09-30.md` - skip samples that cannot pass the
horizon test - was measured on DEMO1 record 20 from the port's own archive. The projection
page (`ring_page_table`) is monotonic in its index for every one of the 250 rings, and the
sample index is `byte(camh + height)`, so a ring's largest possible page row over the map's
actual height range (0..121 here, `camh` 57) is one table read, `page_r[camh + Hmax]` (or
`page_r[255]` when the byte add wraps). A column whose horizon already meets that bound cannot
paint in that ring: 6,478 of 48,000 samples (13.5%), zero of them painting samples in the
original's own archive. The static whole-table maximum (255 for the near rings) prunes nothing.
That is about 2% of a frame; a local height pyramid would prune more only for the mid rings,
because the far rings' lateral spans cover the whole 1024-cell map. Not implemented.

### The live command keys (2026-10-07)

Found while answering what was missing from the game logic: `0001959F`'s command chain was fed
only by the replay (`demo_key`), so in live play the view keys 1-8, the MFD page keys (F1-F12,
Q/A/W/S), the weapon page keys (Z X C V B N), the hand-dropped flare and chaff (`'`, `;`) and
the double rocket (M) did nothing - the player could only fire the Hellfire page the mission
starts on. `main.s` now pops the key interrupt's queue (`key_queue`, `[00001B70]`) once a frame
as `00006AF4` does and runs `game_command`, whose keyboard half (`game_command_keys`,
`00019AFF-00019C88`) is ported with both layouts (the ThrustMaster WCS option's too). Not carried:
`I`/`U`/`O` (record, replay and save a flight as DEMO1.SCR - a development feature) and `J`
(joystick calibration).

### The KYLE cheat column (2026-10-07)

The original ships a hidden fifth options column. Inside the options bar, with Backspace held,
the four makes K Y L E (the key queue reads `0x25152612`) toggle `[000265ED]`, which is the
'C' of "Cheat" in the bar's own string (0xFF ends the text there, 0x43 spells the word;
`00026012-0002603F`). Its two items are `00026B49` **Fix Damage** (hull to `[00019E44]`,
wreck countdown 0x64, cue 0, speed ceiling 0x1800000, the eight damage cells to 0x0A) and
`00026B88` **Reload** (fuel `[00019D5C]` to `[00019D60]`, the six weapon stores from
`[00019D44..58]`, chaff 15, flares 25), each with its message box (`00026E90`). Ported in
`menu.s`/`game.s`; the live key pop in `main.s` is held while the bar is up, as the bar is
its own loop in the original. Verified in Hatari through the queue: hull 5 -> 30, fuel 0x1000 ->
0x2710, both boxes shown.
