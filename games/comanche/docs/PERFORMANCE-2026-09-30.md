# Five frames per second: optimized CPU attract investigation

Measured 2026-09-30 on `origin/dos-fidelity-audit`, commit
`df8a1dc67ccb6602ad83adac1cbbbba4bebd06c6`, built separately in
`../F030Comanche-fast`. These results do not describe master. No rendering
implementation was changed in this investigation.

## Measurements

F030Arcade's third-party Hatari 2.6.1-devel (2026-09-22), cycle-exact
16 MHz 68030, 14 MB ST-RAM, TOS 4.02, RGB 60 Hz, DSP off. Host fast-forward
and disabled video accelerate capture only. This is emulator evidence,
not real-Falcon certification. Profiler frequency: 16,042,494 cycles/s.

The unstripped executable was staged as `PERF.TOS` to avoid ambiguous
long-name auto-launch resolution. SHA256:
`56505ab3c2a436848c40e2e84a983c92e6da3cb7f5d501ce55777d788879fe5e`.
The stripped build is
`bb708ee0ba0cd51ece5ecc9cc58d3691c088309a65632e91b39d7f44b93afa92`.

Instruction-bound `frame_driver` endpoints use
`demo_cursor = 13 + 8*K`. Records 60..80 give 20 replay advances, avoiding
the view/resource changes in the earlier interval. Cycle totals include
the complete intervening game loop, interrupts and publishing.

| Setting | Cycles (20 frames unless stated) | ms/frame | fps | VBL delta |
|---|---:|---:|---:|---:|
| HIGH, 192 columns | 126,652,498 | 394.7 | 2.53 | 470 |
| MEDIUM, 192 columns | 108,660,506 | 338.7 | 2.95 | 404 |
| LOW, 96 columns | 76,003,008 | 236.9 | 4.22 | 282 |
| HIGH, records 220..240, fixed view 7 | 132,113,282 | 411.8 | 2.43 | 491 |
| HIGH, records 10..20, cockpit view 1 | 91,270,954 (10 frames) | 568.9 | 1.76 | 339 |
| LOW/96, records 10..20, cockpit view 1 | 61,506,430 (10 frames) | 383.4 | 2.61 | 228 |

Detail settings were changed only in the staged `COMANCHE.MNU`: offset
0x18 is '0' HIGH, '1' MEDIUM, '2' LOW; offset 0x1D is '{' for the
96-column path instead of the staged '}' full-column path. Original assets
were untouched and the staged settings were restored after capture.
The later HIGH interval explicitly captured view 7, 250 rings and
`terrain_lowres = 0`; it is an external view, not a cockpit benchmark.

HIGH records 60..80 split:

| Function | Cycles/frame | ms/frame | Share |
|---|---:|---:|---:|
| `render_terrain_ring` | 3,521,768 | 219.5 | 55.6% |
| `render_copy_surface`, both calls | 1,418,135 | 88.4 | 22.4% |
| `render_clear` | 926,896 | 57.8 | 14.6% |
| `object_depth_sort` | 214,424 | 13.4 | 3.4% |
| Remaining execution | 251,402 | 15.7 | 4.0% |

These are exclusive address-range costs from Hatari's profile postprocessor;
callee costs such as `ring_mul_q31_raw` remain in the remainder. The profile
reports an undefined previous PC at the ROM timer caller boundary; the totals
and exclusive instruction costs do not rely on inclusive call propagation.

Records 30..40 are unsuitable as a steady-rate benchmark: console loading and
`resource_palette_remap` consume 50,129,400 cycles, 41.8% of that interval.
The interval measures a real transition cost, which must be reported
separately rather than used to characterize sustained rendering.

The cockpit interval explicitly captured view 1 at both ends. At HIGH,
`console_draw_rows` costs 99.4 ms/frame, `mfd_march_target_view` 40.8 ms,
and `mfd_draw_map` 12.9 ms. LOW/96 reduces the main terrain to 72.4 ms
and the target-view march to 18.8 ms, but console rendering remains 99.7 ms.
Thus external-view performance is not a cockpit performance claim.

## Is 5 fps possible?

**At LOW/96 in the external view, it is a credible optimization target,
not yet demonstrated.**
The two copies cost 1,417,377 cycles/frame in that measurement. Eliminating
one predicts 192.7 ms/frame, about 5.19 fps, if all other costs stay fixed.
This has only about 7 ms of headroom and is not an all-camera minimum.
The LOW/96 cockpit is only 2.61 fps; removing one copy would predict about
2.95 fps there. Five fps in the cockpit needs multiple additional savings.

**At HIGH, minor tuning is insufficient.** Five fps allows 200 ms, about
3.208 million cycles/frame, versus the measured 6.333 million. The marcher
alone costs 219.5 ms. Removing one copy predicts only 2.85 fps; removing
both predicts 3.26 fps. Even the impossible upper bound of removing both
copies and all backdrop work leaves about 249 ms/frame, around 4.02 fps.
With both copies removed but the backdrop unchanged, the marcher would still
have to shrink by about 49% to fit the total budget. These are bounds and
estimates, not measured speedups.

The concrete next investigation is surface ownership. Render terrain and
objects directly into the logical persistent surface, then transfer once
into the physical work surface before composing cockpit/HUD. This could
replace restore plus store with one transfer. Preserve view-change frame
tails, console painting, right-MFD writes, object persistence and VBL-owned
scanout; a simple deletion of either copy is incorrect. Prove complete
composed frames at identical replay records across cockpit and external
views before claiming a saving.

The next cockpit candidate is `console_draw_rows`: it currently tests all
76,800 source pixels each frame, even the transparent canopy, and performs
palette lookups for opaque pixels. Precomputed exact opaque runs and cached
RGB565 pixels could remove those repeated tests and conversions. Runs must
preserve interior holes, the page-x crop and palette reload/remap boundaries;
the existing first/last row bounds alone are not sufficient. No saving has
been measured for this candidate, and no console code was changed.

For HIGH, a second substantial change is required: measure output-exact
sample skipping (with the DOS byte-wrap projection contract), or recover
and validate a DSP boundary that actually reduces the measured cost. Neither
is implemented or established by these measurements. Do not change the
terrain geometry, maps, horizon seed or replay cadence to meet the number.

## Reproduction and evidence

Ignored captures are in `../F030Comanche-fast/release/`: `high-profile.txt`,
`medium-profile.txt`, `low96-profile.txt`, `cockpit-profile.txt` (despite its
filename, the last is fixed view 7), `early-profile.txt` and
`early-low96-profile.txt` (cockpit), and corresponding `*-stdout.txt` and
`*-summary.txt`. Build with `bash tools/build-run.sh`; the older branch needs
`python` on PATH as well as Python 3 and the retained original assets and
unpacked DOS image. No assembly edits are required.

Debugger setup: `symbols autoload exec`, then a VBL 1000 trace breakpoint
whose command file installs the record-conditioned start breakpoint. Start
file evaluates VBL, enables `profile on`, and installs the end breakpoint.
End file evaluates VBL, runs `profile stats`, saves the profile and quits.
Use `:once :trace :file <file>` for automatic chaining; a plain stopping
breakpoint can leave a headless capture in the interactive debugger.

Explicit launch options: `--machine falcon --cpulevel 3 --cpuclock 16
--cpu-exact true --compatible true --memsize 14 --dsp off --monitor rgb
--frameskips 0 --patch-tos true --fast-boot true --sound off --fast-forward
true --disable-video on --confirm-quit off --run-vbls 60000`, with explicit
TOS, harddrive, `--auto C:\PERF.TOS` and debugger parse file. Use Hatari's
`tools/debugger/hatari_profile.py -st -f 10 <profile>` for exclusive costs.

DOS listing was consulted at 0000D950 (zero horizon, complete ring traversal),
0000D9F6-0000D9FF (byte-wrapped projection and unsigned visibility),
00007AA0 (run transfer), and 00016EC0/00017230 (authored sky paths).
This investigation introduces no new DOS contract or supported function.

## Marcher hotspot investigation

The follow-up reads the actual instruction costs of `render_terrain_ring`,
not its callers or retired DSP benchmarks. HIGH records 60..80 execute
960,000 samples (48,000 per frame). Only 175,465 pass the DOS unsigned
horizon test: 18.28%. Of those, 56,282 emitters have no span left after
surface clipping. They must still update the horizon; they cannot simply
be discarded as samples. Source and listing were checked at 0000D9E9,
0000D9EE/0000D9F2, 0000D9F6/0000D9F9, 0000D9FB/0000D9FF,
0000AF50-0000AF75, and 0000F2E5-0000F2FF.

| Work inside the marcher | ms/frame | Share of marcher |
|---|---:|---:|
| Map-index extraction and combination | 48.91 | 22.28% |
| Height fetch plus byte-wrapped bias addition | 31.00 | 14.12% |
| Projection-page lookup | 11.65 | 5.31% |
| Bias register reload | 6.39 | 2.91% |
| Horizon compare and visibility branch | 14.02 | 6.39% |
| Coordinate advance and sample-loop control | 20.79 | 9.47% |
| Visible-sample emitter, clipping and span stores | 56.52 | 25.75% |
| Horizon archive and its setup | 14.36 | 6.54% |
| Other ring setup and routine work | 15.88 | 7.23% |

The actual RGB565 stores account for only 11.28 ms/frame, 5.14% of the
marcher. The 56.52 ms emitter row includes all its setup and clipping.
The two indexed height/bias instructions are the largest individual
instruction costs, together 31.00 ms/frame. Map indexing is the largest
separable computation repeated on every sample. Ring multiplication is
not the principal hotspot: its callee costs are about 2.87 ms/frame in
this interval and excluded from the marcher-exclusive table above.

Costs include pipeline, cache and ST-RAM effects; zero or low attributed
cycles on a particular instruction do not make that instruction free.
Summing static nominal timings or multiplying instruction-count reductions
by these attributed averages is not a measured speedup.

The baseline was repeated at the same instruction/record endpoints and
reproduced exactly 3,521,767.6 marcher cycles and 6,332,624.9 total cycles
per frame. The first cache-alignment experiment was invalid: emitted zero
padding decoded across the first `move.l d6,d0`, changing 435 silhouette
bytes and 643 history bytes at record 80. It is excluded from performance
claims. Branching over that padding restored byte equality.

The corrected alignment experiment costs 3,526,648.8 marcher cycles/frame
(0.14% slower), 6,343,270.8 whole-loop cycles/frame, and 44,972.15 marcher
instruction-cache misses/frame versus 44,557.8 baseline. Both the 153,600-byte
terrain/object history and 48,000-byte silhouette are identical at record 80.
The alignment was removed. Padding must be checked in the emitted code,
regardless of assembler documentation or directive spelling.

Ignored evidence: `baseline-hotspot-profile.txt`, `safe-hotspot-profile.txt`,
their logs, and the matching `*-history.bin` / `*-silhouette.bin` dumps in
`../F030Comanche-fast/release`. `aligned-*` is the invalid zero-padding
experiment, not a faster or supported renderer.

### Direct bit-field extraction candidate

The seven instructions that form the map index were replaced experimentally
by five: `BFEXTU d6{0:10},d0; SWAP d0; LSR.L #6,d0;
BFEXTU d5{0:10},d1; OR.W d1,d0`. Both unsigned ten-bit cells come from the
same coordinate bits as DOS's two SHLD operations. Height reads, byte-wrap
bias, projection, unsigned compare, cumulative coordinates and ring order
are unchanged. No behavioral flag was added. The change is in the separate
`../F030Comanche-fast/src/render.s` working tree; master source is unchanged.

| Interval | Baseline marcher cycles/frame | Candidate | Marcher saving | Whole-frame fps before/after |
|---|---:|---:|---:|---:|
| HIGH external, 60..80 | 3,521,767.6 | 3,394,678.7 | 3.61% | 2.533 / 2.583 |
| HIGH cockpit, 10..20 | 3,710,631.6 | 3,591,307.2 | 3.22% | 1.758 / 1.779 |

The external interval saves 127,089 marcher cycles, 7.92 ms/frame. Whole
frame savings are 1.91% externally and 1.19% in the cockpit. Both intervals
match the baseline's entire history surface and every silhouette byte at
their endpoints. This is implementation parity, distinct from DOS evidence.

The retained `marcher-cockpit.json` DOS fixture has 180 rings, so its staged
settings explicitly select MEDIUM. Capture is at `object_draw_pass` after
the main marcher has completed, rather than at an arbitrary VBL. The
unchanged scoring code in `tools/certify-marcher.py` reports
**15,120/15,120 scored columns exact**, maximum error zero; height-map prefix
and all 192 backdrop columns also match DOS. Uniform rings and the 80-column
archive portion overwritten by DOS's rear view retain the existing scorer's
exclusions. This does not certify complete DOS frames or real hardware.
The 96-column DOS fixture also passes **17,472/17,472 scored columns exact**.
Both captures' 180 forward and lateral increments match the DOS JSON values
exactly. All 46,080 projection-page bytes match the retained DOS MEDIUM page
dump (the low-resolution fixture uses that same schedule). The old scorer's
comparison with compile-time HIGH tables prints differences because the
fixture deliberately loads MEDIUM; those generated HIGH tables are not the
authority for this fixture. The explicit runtime-versus-DOS comparisons pass.

The old harness assumptions were not valid for this branch: the build now
stages HIGH, whereas the retained fixture is MEDIUM. An initial capture had
250 runtime rings against a 180-ring fixture and was rejected. The adapter
in ignored `build/check-bits-dos.py` changes only launch, fixture settings
and the capture breakpoint; it uses the existing generator and scorer.
The successful result is `build/bits-dos-check.txt`. Performance evidence
is `bits-hotspot-profile.txt`, `bits-cockpit-profile.txt`, the corresponding
baseline profiles and byte dumps. Candidate speed is measured on the normal
replay binary, not the camera-pinned fixture binary.

The larger next target remains work on rejected samples. A conservative
height hierarchy could skip only sample groups proved unable to beat the
horizon. Its bound must include the byte-wrapped bias/projection lookup and
the exact accumulated coordinates, and retain every archive consumer's
result; treating a maximum raw height or an idealized ray as the bound is
insufficient. This remains an unimplemented hypothesis, with no speed claim.
Optimizing row stores or the four ring multiplies alone cannot reclaim
the much larger sample-path cost.
