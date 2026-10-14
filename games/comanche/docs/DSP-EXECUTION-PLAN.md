# DSP execution plan: from assembled kernel to measured frames

This is the concrete execution sequence for the DSP56001 terrain workstream,
written against the tree as it stands (2026-08-14, with the uncommitted
`USE_DSP` integration in the working copy). It does not replace
[PORTING.md](../PORTING.md), which remains the strategy and constraints
document, and it does not change the priority rule in
[PORTING-PLAN.md](PORTING-PLAN.md): this is phase 7 work, resumed here because
the CPU path is far enough along to serve as oracle and the kernel exists.

The Falcon attract milestone has now been recreated as a CPU-only 68030 path.
This document remains a later optimization plan: the DSP route is not linked
or supported until a separate DOS route trace proves the DSP-facing boundary
and the CPU attract path has a captured Falcon validation result.

## 2026-09-28: the terrain stays on the CPU

Everything below this section is the earlier kernel plan and may change
completely. It kept its speed by replacing the 1024×1024 map with
downsampled tiles, which is not the DOS picture. This section records why no
DSP route yet reaches the full DOS terrain at 20 fps. It also records what
was done instead.

**Where the cost is.** At HIGH detail the DOS marcher takes 250 rings × 192
columns, about **48,000 samples per frame**. Each sample reads one height
cell and one colour cell from the full 1024×1024 map; the far rings sample
about ten cells apart laterally, so no downsampled tile gives the same bytes.
The DSP holds 32K words of SRAM, of which about 16K X are free under XBIOS,
so it cannot hold the map. Every sample therefore starts as a 68030 read of
ST-RAM, whatever then does the projection.

**Host port.** Moving a sample through HI08 costs 0.5-2.3 µs per word
(`§2`). The 68030's page lookup and horizon compare cost well under that. A
walker that feeds the DSP one word per sample is slower than one that decides
itself.

**SSI DMA.** The ScummVM `ssi-dma-c2p` work
(`scummvm/devtools/atari-falcon030/tools/ssi-dma-c2p/README.md`, measured
under Hatari 2026-09-23) sends DMA playback to the DSP's SSI receiver and the
DSP's transmitter to DMA record. The DSP can therefore write screen memory
without the CPU. Its measured rates, each way:

| mode | rate | note |
|---|---:|---|
| free-running, 25.175 MHz, 4 stereo tracks | 786,720 B/s | the 68030 must `STOP`, or words are lost |
| free-running, 32 MHz | 1,000,000 B/s | unproven on hardware |
| handshake, the kernel ScummVM ships | ~375 KB/s | 64 KB each way in 170-175 ms with the 68030 busy |

A walker keeps the 68030 busy, so the handshake row is the one that applies.
At 20 fps a frame lasts 50 ms, which is 19 KB each way at that rate, or 39 KB
at the free-running one. What the terrain needs:

| per frame | bytes | at 786 KB/s | at 375 KB/s |
|---|---:|---:|---:|
| input, HIGH: 48,000 samples × (height, colour) | 96 KB | 122 ms | 256 ms |
| input, LOW / 96 columns: 9,600 samples | 19 KB | 24 ms | 51 ms |
| output, 320×168 terrain as 8 bit-planes | 54 KB | 68 ms | 143 ms |
| output, 320×168 terrain as RGB565 | 108 KB | 137 ms | 287 ms |

Input and output run at the same time, so the frame costs the larger of the
two. At best, that is about 15 fps (LOW detail, planar output, a mode the busy
walker cannot use). In practice it is about 7 fps. Sending height and colour
is already the smallest useful input: the walker cannot tell which samples
paint without projecting them itself. Sending heights alone would need a
second round trip for the painting samples' colours. There are three more
costs:

- DMA record writes one contiguous block, so the whole terrain rectangle is
  rewritten every frame.
- The DMA shares the ST-RAM bus with the walker and VIDEL.
- The route takes the DSP and sound DMA away from sound. Giving one pair to
  sound drops the link to 590 KB/s.

The route's real merit here is fidelity rather than speed. A planar 8-bit
screen shows the VGA palette exactly (6 bits per channel), which RGB565
cannot. Revisit with `SSIECHO.TXT`/`HSC2P` figures from a real Falcon: the
conclusion changes only if the link turns out about five times faster than
Hatari shows.

**What was done instead: the CPU marcher.** `render_terrain_ring` was made
3.1× faster without changing a value. See `analysis/functions/falcon-attract.md`,
"The marcher, made fast". The cost fell from about 10.3M to 3.4M cycles per
frame, certified against DOS again and verified pixel-identical to the
previous build. The remaining routes to 15-20 fps on a stock Falcon are:

- DOS's own detail settings (`LOW.DTL`, the 96-column marcher). The original
  shipped them for the same reason, and they are DOS-exact at their setting.
- Output-exact skipping. A column's samples lie on a straight line, so a
  max-height hierarchy can skip runs that cannot pass `ja`. It has to respect
  0000D9F6's byte wrap, and its gain is not yet measured.
- The rest of the frame: `render_copy_surface` and `render_clear` together now
  cost more than half as much as the marcher.

On a 68060 the same code reaches full HIGH detail with room to spare.

## Route-first source rule

Every milestone, including this DSP milestone, begins by tracing the
authoritative DOS route that exercises the work being ported. Use QEMU's TCG
`exec,nochain` execution telemetry with repeatable inputs and state/memory snapshots to identify the
reached DOS functions, indirect callbacks, resource reads, state transitions,
and frame-order boundary. Create the JavaScript reference and M68k/DSP source
only from that route and link each implementation to its durable function
record and route manifest. A kernel or host path not represented by the traced
route remains `dormant`/`Unproven`; CPU/DSP parity can validate a route but
cannot establish what DOS did.

Two sibling projects feed this plan and are cited throughout:

- **F030TREX** (`~/Work/F030TREX`) — the same author's PS1 T-Rex port. Its
  `OPTIMIZATION.md` is a measurement log for exactly this machine profile, and
  several of its findings are imported below as facts rather than re-derived.
- **F29** (`reference/f030f29/`) — comparison material for host-port idioms
  and blitter span filling (`dp_hc.s`, `f29.s:send_data/receive_data`).

Everything in this document is Hatari-derived or counted from source unless
explicitly marked as measured on hardware. Per the F030TREX findings (§2),
Hatari flatters both processors; hardware checkpoints are built into the
phases.

**Current-boundary note, 2026-08-18.** The DSP is only an accelerator for the
recovered CPU terrain result. The historical benchmark sections below mention
retired camera and geometry switches; they are measurements, not active
behavior. The only build options are `USE_DSP` and `PARITY_TILE`.

**Bring-up correction, 2026-08-18.** The live DSP host path decoded each
rectangle's height byte correctly but then divided that row count by four before
the longword fill. That was a compositor bug, not a DOS geometry choice: one
longword covers the two adjacent RGB565 pixels in one row, not four rows. The
divide is removed from `src/dsp_host.s`; the standalone DSP build now assembles
through the headless DOSBox-X path and reports the checked P-memory extents.

## 1. Where the tree stands

What exists and is committed:

- a complete DSP kernel (`src/dsp/comanche.asm`): command/tile/rectangle
  protocol, two-level depth march, fan setup, rectangle emission — written
  correct-first, **assembled but never executed**;
- the fixed-point design (`src/dsp/proto.inc` FIX_*), verified by modelling
  the kernel's arithmetic against the CPU renderer to within one row
  (commit 6532b90) — a model diff, not an execution diff;
- toroidal tile residency with edge-strip transfers in the protocol and the
  kernel (commit 235a4b9);
- generated, schedule-driven tables (`tools/gen-dsp-tables.py` reads
  `proto.inc`, so schedule changes propagate).

What the uncommitted working copy adds: `dsp_init`/`dsp_render` on the host,
`render_frame_path` with CPU fallback, telemetry rows for `dsp_status` and
`dsp_xavail`, `.LOD` staging in the build, and the 128→64 near-tile retreat
after `Dsp_Available` reported 16,040 free X words (XBIOS keeps 344).

What has never happened: **no DSP instruction of this kernel has ever run.**
The one live attempt fell back to the CPU silently and pixel-identically,
which is what prompted the telemetry rows. The first milestone of this plan is
therefore correctness on the real transport, not speed.

## 2. Facts imported from F030TREX

These were measured or established there and are treated as ground truth here.
File references are into `~/Work/F030TREX`.

**The memory overlay.** One 32K-word external SRAM sits behind all three DSP
address spaces (`TREX/dsp/trex_dsp.asm:3499-3512`):

| Space | On-chip | External mapping into the SRAM |
|---|---|---|
| P | `$0000-$01FF` | `$0200-$7FFF` → word `addr` |
| X | `$0000-$00FF` | `$0100-$3FFF` → word `addr + $4000` |
| Y | `$0000-$00FF` | `$0100-$3FFF` → word `addr` |

Consequences for this kernel:

1. **`Y:$0200` upward is external P.** Our Y map (far tile at `Y:$0040`,
   tables and rect buffers up to about `Y:$2135`) is safe only while the
   kernel stays inside internal P (`$0000-$01FF`). The moment the program
   grows past `P:$01FF` it lands on top of the far tile. T-Rex hit exactly
   this class of fault (a normal array executed as code). Add its `.lod`
   P-extent check (`trex_dsp.asm:3530-3532`) to `tools/build-dsp.sh` with a
   hard ceiling of `$01FF`, failing the build on overflow.
2. **X external is the SRAM's upper half**, which only high P aliases —
   nothing realistic conflicts there. A full 16,384-word X tile is physically
   addressable (`X:$0000-$3FFF`, 256 internal + 16,128 external words); only
   the XBIOS reservation stands in the way. That keeps the 128×128 option
   alive as a contingency (§8) without making it the plan.
3. Internal/external is contiguous in addresses but not in timing: internal
   is 0-wait, external is governed by the BCR — next point.

**The BCR trap.** The 56001 resets with maximum wait states in the bus
control register, Hatari's DSP core ignores BCR entirely, and this kernel
never writes it. A kernel that meets its budget in Hatari can be many times
slower on hardware purely on external X/Y accesses. Write `m_bcr` explicitly
in `main:` init (the equate exists at `src/dsp/ioequ.inc:21`), and verify on
hardware what XBIOS left there. This is invisible in every emulator run.

**Host-port transfer modes and the safety rule** (`OPTIMIZATION.md:364-412`,
`trex_m68030.s:1469-1509`). The port is one register deep; a word written
while TXDE is clear is silently lost. Two modes are proven:

- *Blind block:* test TXDE once, then stream the whole block with
  `move.l (aN)+,$FFFFA204` — this is also what TOS 4.02's `Dsp_BlkUnpacked`
  does internally. **Safe only when the DSP-side receive loop is pure
  `jclr`+`movep` store, nothing else between reads.** T-Rex lost exactly one
  word per frame, layout-dependently, when the receive loop did a
  multiply-accumulate between reads.
- *Per-word poll:* one `btst` per word, for any receive loop that works
  between reads, and for host reads whenever the DSP's emit cadence is not
  provably faster than the host's consume cadence.

Measured cost: ≈2.3 µs per word (~37 CPU cycles) including XBIOS call
overhead; a hand-rolled loop is cheaper. TOS 4.02's `Dsp_BlkUnpacked` also
only advances the low 16 bits of its source address, so XBIOS block calls
need 64 KiB-aligned buffers — another reason to keep the hand-rolled
transfers this project already has. Host-side reads of `$FFFFA204` arrive
zero-extended.

**Pipelining patterns that worked** (`OPTIMIZATION.md:2689-2710`): send
fire-and-forget, collect the ack at the start of the next slot; fetch results
into a host buffer, *launch the next unit of DSP work, then* unpack; keep
every command one-directional (a DSP that replies mid-block deadlocks); have
the ack carry the reply's word count. Measured −24.4 ms/frame there without
touching the DSP program.

**Measurement discipline** (`OPTIMIZATION.md:383-412, 1395-1458`). The current
CPU-only attract harness runs Hatari with `--mmu true --dsp off` (`tools/run.sh`
and the capture scripts). A future DSP benchmark may opt into `--dsp emu`, but
that is not part of the supported Falcon attract build. Under that future DSP
mode CPU instruction execution is charged **zero time** (bus traffic and IO
wait states only), DSP cycle counting is simplified, and DSP external-RAM
wait states are ignored. Consequences:

- bus-dominated stages (clears, fills, transfers) are trustworthy;
  arithmetic-heavy loops are systematically flattered — including every
  CPU-renderer percentage recorded so far;
- binary layout moves numbers by tens of milliseconds; toggle features with
  data flags, not by removing code, and verify with `cmp -l` that exactly one
  longword differs; pin hot loops with `cnop` and keep the fill loop within
  the 256-byte instruction cache;
- compare equal frame counts, not wall-clock windows (the telemetry
  delta-capture procedure in PORTING.md already does this);
- schedule a hardware run at the end of phases 1 and 4. No number in this
  document is final until it has survived one.

## 3. Phase 0 — first light

Goal: one real DSP-rendered frame, diffed against the oracle. The integration
in the working copy is close but has a set of known defects, each found by
reading the seam; fix these before any timing is taken seriously.

1. **Status handshake mismatch.** The kernel sends `RES_S_BUSY` after
   draining the command and tile (`src/dsp/comanche.asm:127-128`), then
   `RES_S_DONE` from `send_rects`. The host's `dsp_drain_rects` expects
   `RES_S_DONE` as the *first* word (`src/dsp_host.s:300-306`), so every
   frame would error out and fall back. Consume BUSY first — and keep it,
   because it distinguishes "never started" from "hung mid-frame" on a
   timeout.
2. **`dsp_init` passes garbage to the tile upload.** It calls
   `dsp_upload_tiles` with whatever `a0`/`a1` survived three `trap #14`s
   (`src/dsp_host.s:149-151`); the routine expects `a0` = command block,
   `a1` = map source. It also never initialises the command block's version,
   sequence, or flags for the upload commands.
3. **The kernel ignores `CMD_F_RENDER`.** `frame_loop` renders and pushes
   rectangles after *every* non-halt command (`comanche.asm:123-133`),
   including the init-time tile uploads, whose sender never drains — the
   kernel blocks in `send_word` and the next host command times out. Honour
   the flag: tile-only commands acknowledge with one status word and loop.
4. **The tile upload sends the wrong data.** `dsp_send_tile` widens only the
   height byte; the colour field of the packed word is never filled
   (`dsp_host.s:249-260`), so all terrain would render as palette entry 0.
   And `dsp_upload_tiles` sends `TILE_NEAR_WORDS` *consecutive* map bytes —
   rows 0-3 of the 1024-wide map — not a 64×64 window
   (`dsp_host.s:279-287`). Needed: a windowed gather (64 rows, source stride
   1024) interleaving height and colour maps, writing dest indices in the
   toroidal convention (`dest = (y&63)<<6 | (x&63)`, matching the kernel's
   masked addressing; the host's own 16.16 positions truncate to the same
   cells).
5. **The far tile does not exist.** No decimated source, no uploader; the far
   march would read uninitialised Y. Build a whole-map 8:1 pair once at load
   time (128×128 bytes each — trivial in Falcon RAM), then treat the far tile
   exactly like the near tile: initial 4,096-word window fill, edge strips
   after. Decimation filter: start with max (PORTING.md's argument — it
   preserves ridge lines), compare against average on captures.
6. **Nothing sends strips.** `dsp_render` always sends `TILE_WORDS=0`
   (`dsp_host.s:213-216`). Track the last uploaded integer cell per tile on
   the host; when the camera crosses a cell boundary, prepend the crossed
   row/column strips (the protocol and kernel already carry them). At current
   flight speeds this is a few hundred words per frame — sub-millisecond.
7. **Init order.** `dsp_init` runs before the maps are decoded? It does not:
   `resources_init` runs first in `main` — but the upload reads
   `original_height_map` directly, so keep that ordering explicit and assert
   `mission_status` before uploading.

Then the oracle gate. The CPU renderer marches 64@1 + 32@4 to 192 units
against full-resolution data; the kernel marches 32@1 + 28@8 to 256 against a
decimated far tile. A pixel diff of those two is meaningless. Add a **parity
build**: a build-time switch that makes the CPU renderer consume the DSP
schedule (steps, far shift, and far samples read from the same decimated
array) so the two produce comparable frames. Diff at the pinned benchmark
camera plus at least two others (one on a tile diagonal, one at a tile
boundary crossing), tolerance ±1 row from the documented reciprocal rounding.

Exit gate: a `USE_DSP=1` capture whose telemetry rows show `dsp_status = 0`
and a non-zero rectangle count, matching the parity-build CPU capture within
tolerance, three cameras, plus one capture taken *while flying* whose strips
demonstrably keep the window coherent (no seam, no stale terrain).

### Phase 0 outcome (2026-08-14)

First light achieved: `USE_DSP=1` frames are **pixel-identical** to the
`PARITY_TILE=1` build — zero differing pixels below the telemetry rows — at
all three gate cameras: the pinned benchmark camera, a 45-degree heading
(the fan edges at their sqrt(2) extreme and the windows on the diagonal),
and a map-edge position (the map mask wrapping through every gather), with
`dsp_status = 0`, both windows resident, and ~7,500 records streamed per
frame. Beyond the seven defects listed above,
live bring-up found and fixed six more, all invisible to inspection and all
caught by the telemetry rows, the Hatari debugger, or the host-side record
log:

1. **FIX_DIR is now 2.22, FIX_POS 11.13.** `cos(0) << 15` is exactly +1.0,
   which 1.23 wraps to −1.0 — every axis-aligned heading rendered backwards
   — and the fan edges reach √2. Separately, an 8.16 position carries only
   eight integer bits, so the far-tile index `(pos >> 19) & 63` repeated
   with a 256-unit period and half the far tile was unreachable.
2. **ASM56000 encodes immediates ≤ $FF to data registers as left-aligned
   short form**: `move #RES_S_BADVER,x0` loads $FF0000, not $FF. Version
   compares, status words, masks and the ybuffer seed were all silently
   fractions. Every data-register immediate now carries the `#>` long
   prefix — the same idiom F030TREX uses throughout, and the register dump
   (`X0: ff0000`) is what gave it away.
3. **The 56001's `rep asr` parks the shifted-out bits in a0, and `and`
   cleans a1 only** — the `rep asl` that rebuilt the row base dragged six
   fraction bits back in, displacing samples along x by up to 63 cells,
   growing with depth as the fan's fractional step accumulated. One
   `move a1,a` (which clears a0) before each shift-up fixes it. Found by
   diffing the host-side record log against a Python model of the parity
   marcher, record by record.
4. **The rectangle emission now streams.** The buffered protocol capped at
   RECT_MAX = 2,048 records and smooth terrain wants ~7,500 — the cap
   silently amputated three quarters of the screen, and Y memory cannot
   hold the worst case. Each record now goes to the port as its sample is
   found; the host drain was already sentinel-terminated and needed no
   change, and the host composites while the DSP marches — a piece of
   phase 3 that correctness forced early.
5. **`render_background` never set `render_target`**, so the first DSP
   frame's sky fill went through a zero pointer over the vector table. Only
   the DSP path took that route, which is why the CPU-only builds never saw
   it.
6. **The drain timeout was a frame-time ceiling in disguise**: the DONE
   header arrives only after the march, and 200,000 poll iterations fire
   inside an unoptimised ~135 ms march. Now 2,000,000 — a liveness
   backstop is allowed to cost a second, once, on a dead DSP.

Also landed with the phase: the `#>`-audit and BCR init in the kernel, the
P-extent guard in `tools/build-dsp.sh` (the kernel sits at ~$1CC of the $1FF
ceiling), the decimated far pair and its builder, strip-based window
maintenance on both axes, the tile-only command acknowledgement, the
in-bounds clip on the host fill, and bring-up telemetry rows 2-7 (status, X
words offered, strips accepted, records drawn, first record verbatim) plus a
2,048-record host-side log for offline diffing. The parity marcher and its
generated projection table are permanent fixtures: they are the oracle for
every kernel change from here on.

First timing point, taken the project's way (delta of `render_count` over
delta of VBLs between two captures of one build, pinned camera, 320 rays,
measured-Hatari): **DSP path 2.39 FPS (20.9 VBLs, ~418 ms/frame); CPU path
4.04 FPS (12.4 VBLs, ~247 ms/frame).** The DSP path being slower is the
expected phase 0 shape, and the comparison is distorted in both directions:
the `--mmu` core charges the CPU marcher's arithmetic nothing (its 4 FPS
will not survive hardware), while the DSP march's cycles are modelled but
its host side — the per-word polled transport and the movem-heavy fill that
dominate the 418 ms alongside the ~130 ms REP-shift march — is flattered
too, and the bring-up logging is still in the loop. Those three terms are
exactly phases 2 and 4.

## 4. Phase 1 — measure the machine

Everything below this line is sized by numbers that are currently assumed.
Take them in one sweep with the fixed benchmark camera; record each as
measured-Hatari or measured-hardware in this document.

1. **DSP memory map assertions.** Host-fill X and Y with position-dependent
   patterns through the port; kernel checksums back. Proves the tile
   addressing, the internal/external boundary behaviour at `X:$00FF/$0100`,
   and that the OMR data-ROM bit is in the state the kernel assumes. Cheap,
   and it converts the §2 overlay table from imported fact to verified fact
   for this kernel's layout.
2. **BCR.** Read what XBIOS left in it; set it explicitly; on the hardware
   run, time a fixed external-heavy loop with BCR at reset default vs 0 to
   know the multiplier this machine actually applies.
3. **HI08 sustained rates** with the real loops (not `dsp_put`): command
   block out, 4,096-word tile out, 2,048-word drain in. Words/ms in each
   direction, Hatari and hardware.
4. **Kernel cycles per depth step**, via Hatari's DSP profiler, and a
   host-side frame bracket (time from command send to DONE) for the same
   frame. The two together separate march cost from transport cost.
5. **CPU fill costs** in the real video mode: sequential fill, vertical
   1-pixel span fill, the same via the blitter (PORTING.md's triple, now
   actually executable). This decides §9's options.
6. **Stage split of the full frame** - which no longer has a mechanism. The
   `BENCH_*` bisection switches were removed on 2026-08-18, so this step needs
   the measurement harness rebuilt before it can run.

## 5. Phase 2 — transport and composition fast paths

The current transport is the slowest correct shape: `bsr` per word, `btst`
plus timeout decrement per word, `movem` of eleven registers per rectangle
(`dsp_host.s:349-386`). At a thousand-plus rectangles per frame the overhead
is estimated in the 10 ms class — comparable to the march itself. Rebuild it
on the T-Rex idioms:

1. **Restructure every DSP receive loop into pure `jclr`+`movep` inside a
   hardware `DO`** (command, tile payload). This makes the blind-block
   contract structural, after which the host sends with one TXDE rendezvous
   per block and streams `move.l` — the F29 `send_data` shape, ~5× fewer bus
   operations per word than `dsp_put`.
2. **Drain into a buffer, then fill.** Host reads with a tight per-word
   `btst` (the kernel's `jsr send_word` emit cadence does not provably outrun
   a bare host read loop, so per-word polling stays; it is cheap when it is
   two instructions). No subroutine calls, no timeout arithmetic in the loop
   — liveness comes from one coarse bound outside it. Separating drain from
   fill also frees the DSP at the earliest possible moment, which §6 needs.
3. **Rebuild the fill.** One flat routine over the buffered records: palette
   pre-expanded to 256 longwords (colour doubled) so width-2 rectangles store
   `move.l` per row; a computed dispatch for small heights (straight-line
   stores for h≤8, loop above); constants and pointers register-resident
   across the whole pass; loop pinned with `cnop` and kept inside the
   256-byte I-cache per the T-Rex discipline.
4. **Resolved: seed the kernel from the DOS page anchor.** The earlier
   console-floor seed was an optimisation that changed the visible terrain:
   samples at or below that seed were discarded without advancing occlusion.
   The DOS renderer zeroes its 192-entry horizon array, which corresponds to
   screen row 213 in the Falcon surface. `dsp_send_floor` now uploads
   `TERRAIN_PAGE_ANCHOR-1` for all 192 source columns and the kernel copies that
   value into its y-buffer; the CPU parity marcher uses the same seed.
5. **Early-out.** The kernel currently marches all 60 steps of every column;
   the CPU renderer stops when the occlusion row passes the top. Terminate
   the column with `ENDDO` when the row reaches zero (or the column's floor
   seed), respecting the DO-loop restrictions the kernel already documents.
6. **Optional, measured: DSP-side rectangle merging.** Neighbouring columns
   that produce the same top/height/colour become one wider record — port
   words and fill loops both shrink. Requires holding one column's records
   for one column's latency before flushing. Do it only if the phase-1
   numbers show drain+fill dominating; it is the kind of cleverness that
   should be bought with a measurement.

Exit gate: transport+fill for a benchmark frame under a measured budget (to
be set from phase 1; the working target is ≤5 ms), pixel-identical output.

### Phase 2 outcome (2026-08-15)

**5.22 FPS from 2.39 — the frame fell from 418 ms to 192 ms (2.18×), and
the DSP path now beats the CPU reference's 4.04 FPS under Hatari.** The
three-camera parity gate holds at zero differing pixels with every change
in.

What went in: the kernel's receive loops are pure jclr/movep hardware-DO
drains, so the host streams the command block and every payload blind after
one TXDE rendezvous per block; the drain and fill collapsed into one flat
loop — no subroutines, no per-record movem, no per-word timeout arithmetic,
a liveness countdown that only ticks while the port is empty, and a
per-height limit table that turns the bounds check into a desync detector;
the console-floor occlusion seed uploads once at init (CMD_F_TILE_FLOOR into
the retired rectangle buffer's space) and the kernel seeds each frame's
ybuffer from it, cutting emitted records from 7,506 to 5,183 (−31%) — the
reference renderer's measured 35% column bound, now saving march, port and
fill together. The record log became a DSP_RECT_LOG build option; its
default cost was a branch per record in the hot loop.

Deferred, with reasons: ENDDO early-out (illegal from a JSR'd step — it
pops the wrong stack frame; phase 4's inlining makes it legal), rectangle
merging and the height-dispatch fill (both wait for numbers that say the
drain or fill still dominates — after this rebuild the march is ~130 of the
192 ms, so they do not).

The remaining frame is the march's REP-shift tax, which is phase 4 by
name.

## 6. Phase 3 — pipeline the frame

Serialised, the frame cannot fit: march plus composition exceed the budget at
any useful ray count. Two stages, in order:

**Stage A — overlap within the frame (no latency change).** Reorder
`frame_driver`: build and send the command *first*, then run everything the
CPU owns that does not need the terrain — background fill, object update and
reap, `game_tick`, console span preparation — and only then drain and fill,
then object draw, console, HUD. The DSP march hides behind the CPU's own
work; the residual wait at the drain is the measure of imbalance. No protocol
change, no latency change; this alone should cut the frame time by whichever
of the two stages is shorter.

**Stage B — frame-offset pipeline (the T-Rex pattern).** Drain frame N's
rectangles into the buffer, immediately launch frame N+1's command (strips
included), then composite N while the DSP marches N+1. The march hides
behind the *entire* CPU frame, not just its terrain-independent part; the
cost is one frame of terrain latency against the HUD. Two things make that
acceptable to try: the original itself renders terrain from the viewpoint as
it stood before the frame's input (`frame.s` header — a deliberate skew this
port preserves), and the flight model's frame-to-frame camera delta at 20 FPS
is small. Decide on feel and on the measured gain, and keep it a build
switch; Stage A remains the fallback shape.

VBL policy stays as is: composite into the back buffer, publish at VBL, two
surfaces. Take the flip-quantisation into account when reading frame times
(a 21 ms frame displays at 25 FPS; the telemetry reports both).

Exit gate: wall frame time ≈ max(DSP frame, CPU frame) + drain, measured at
matched frame counts, both stages compared.

### Phase 3 outcome (2026-08-15)

**Both stages measure 7.71 FPS at 130 ms — and that equality is the
finding.** Stage A (launch before the object update pass, collect after)
and stage B (`DSP_PIPELINE=1`, collect last frame's march and launch this
frame's) landed within noise of each other and barely above phase 4's
7.54, with the parity gate at zero and a flying run clean through 846
strips.

The reason is that phase 2's streamed emission already completed the
overlap this phase existed to build: the host drains and fills records
while the march produces them, the fill consumes at least as fast as the
march emits, and so the march costs the frame nothing beyond the
drain-paced fill it hides inside. Moving its cover around the frame -
which is all either stage does - moves nothing.

### Fill options outcome (2026-08-15)

**The 160-ray geometry measures 9.47 FPS at 106 ms against 320's 7.71 at
130 ms, oracle-exact against its own parity build, with the 320 path
regression-clean.** Records halve to 2,595 and each fill store is a
longword covering the ray's both pixels. Cumulative since first light:
2.39 → 9.47, near 4×.

SUPERSEDED 2026-08-18: the geometry is no longer build-selected. 160 columns
on two pixels each is the original's own geometry - its transfer gives each
source byte two adjacent screen pixels - so `TERRAIN_HALF` was removed and
proto.inc states `TERRAIN_COLS` and `TERRAIN_XSTEP` outright. The paragraph
below describes the arrangement while it was still selectable.

The geometry was build-selected: `TERRAIN_HALF` went to both
assemblers' command lines and everything derived in proto.inc - columns,
step, the fan constant, and the protocol version, which carries the
geometry so a host and a stale kernel from different widths refuse each
other loudly instead of rendering half-width records into full-width
offsets. That guard promptly caught its own bring-up: the first capture
run raced a stale `.lod` and every frame fell back visibly rather than
corrupting. Three portability finds along the way: ASM56000 rejects
forward references in EQU expressions (the geometry block moved above its
first use), spells the conditional close `ENDIF`, and the generator's row
offsets had been quietly derived from the ray count rather than the
surface stride - correct at 320 by coincidence, wrong at every other
width.

320 was the build default and 160 one `TERRAIN_HALF=1` away; since 2026-08-18
160 is the only geometry and the flag is gone. The
run-it-on-hardware feel comparison decides the shipping default. The
24 ms the halving actually bought - against ~45 ms of removed drain and
march work - confirms where the frame now lives: ~85-90 ms of background,
console, HUD and loop overhead that no ray-count change touches. DSP-side
record merging is therefore parked (it shaves single-digit milliseconds
at best on a frame this shape); **phase 6's composition work is the next
lever by the numbers**, with the height-dispatch fill folded into it when
the fill's residual share justifies it.

Both shapes are kept: stage A is the default (no added latency), and
`DSP_PIPELINE=1` stays built and gated for the day the march outgrows its
cover again - a 320-ray hardware profile where DSP wait states bite, a
longer schedule, or a mid tile. The frame is now host-bound: roughly 40 ms
of drain-paced fill against 90 ms of background, console, HUD and loop
overhead. The next levers are phase 2's deferred fill options (merging,
the height dispatch) and phase 6's composition work, in that order of
evidence.

## 7. Phase 4 — the inner loop

This is where the frame rate actually lives. Counted from the source, the
current hidden-sample near step costs roughly **110 instruction cycles**
(~60 in `step_near`, ~45 in `step_sample`, plus the `jsr` frame): the
correct-first kernel spends its time in `rep #16` shifts for address and
height extraction and in memory round-trips through the `V_` slots. At 320
columns × 60 steps that is ~2.1M cycles ≈ **130 ms of march per frame** —
first-light will be slow, and that is expected and fine. The rewrite:

1. **Multiply-based shifts.** The 56001 shifts N bits in N cycles but
   multiplies in one; `mpy` by a power-of-two fraction is the idiom
   (T-Rex uses the same trick for its constant-time divide,
   `trex_dsp.asm:2857-2899`). `x>>16` is one `mpy` by `2^7`; `(y>>16)<<6`
   is one `mpy` by `2^13` with a pre-shifted mask (`$FC0`) so no post-shift
   is needed. Height and colour extraction likewise. This alone removes
   ~70 cycles per step.
2. **Register residency.** Ray position and step live in `a`/`b`/`x0`/`y0`
   across the march; the `V_` slots are touched at column entry/exit only.
   PORTING.md's register-allocation table is the starting contract; write it
   down in the kernel header *before* scheduling, because the one bug the
   model diff caught was exactly a clobbered live register.
3. **Precompute the far step per column.** `step_far` currently rebuilds the
   shifted delta every step (~20 cycles); it is loop-invariant.
4. **Parallel moves.** With packed samples there is one X read (map) and one
   Y read (scaled reciprocal) per step — one slot each, foldable into the
   position adds. The bias walk rides the second Y access. Then, last,
   software-pipeline the fetch one step ahead (the address stream is
   data-independent; PORTING.md's argument), shallow enough not to fight the
   early-out.
5. **Emission stays cold.** The emit path can afford its current shape;
   spend nothing there until the march is at target.

Targets, to be confirmed against the phase-1 profile: **≤24 cycles per
hidden near step** in the first rewrite (≈29 ms at 320 rays, ≈14 ms at 160,
before early-out savings), stretch ≤16. Then the 160/320 decision is made
from measurements, not taste — 160 is the stock-machine default candidate,
320 the quality switch, both kept building as today.

### Phase 4 outcome (2026-08-15)

**7.54 FPS from 5.22 — the frame fell from 192 ms to 133 ms, and the
three-camera parity gate holds at zero differing pixels.** Cumulative since
phase 0: 2.39 → 7.54, 3.16×, with the oracle exact throughout.

The worked design went in as written: the dual-lane 48-bit position walk
with the compensated step pair and the host's mid-range camera pinning, the
L-pair constant loads, multiply-based shifts with pre-shifted masks, the
pre-scaled height field, the bias table with the row base folded in, and
the step bodies inlined into the DO loops with the ENDDO early-out. The
march outgrew internal P and the kernel is now split: hot code inside
$0-$1FF, once-per-frame code at $1800 above the Y working set, with the
build guard enforcing both regions.

Two faults found on the way, both worth their entries in the family album:

1. **The pipeline's far hand-off marched one near-step deep.** The inlined
   body advances past its last sample by design; the far prologue now steps
   back once before the first far stride. The compensated pair subtracts as
   exactly as it adds - the borrow the negative lane forces is what the
   folded minus-one paid for.
2. **The accumulator's low word struck again.** After the index mpys, AND
   cleans a1/b1 only - b0 still held the product's fraction bits, and the
   48-bit `add b,a` carried them into the index whenever a0+b0 wrapped:
   sparse, position-dependent, one-cell sample flips that surfaced as a
   handful of one-row silhouette shifts at the diagonal and map-edge
   cameras only. One `move b1,b` per extraction purges it. Phase 0's
   asr-residue bug, one register over; the diagnosis ran through the
   record log against a frankenbuild of the phase-2 kernel, and the final
   pointer came from noticing that both kernels' walks and tables verified
   exact while the emitted rows still jittered by a cell.

The frame now splits roughly march ~35 ms against ~95 ms of host-side
drain-paced fill and untouched CPU frame work — the balance phase 3's
overlap and the fill/merge options exist to attack. The measured march
lands near the ≤24-cycle paper target's prediction.

### The worked design (written before implementation, phase 2 measured)

The register pressure is the whole problem: positions, steps, shift
constants, masks, the sample, the camera height and the reciprocal cannot
all be register-resident on four data registers and two accumulators. Four
56001 mechanisms dissolve it:

1. **Both coordinates walk in one accumulator.** A is 48 bits: posy lives
   in a1, posx in a0, and one 48-bit `add y,a` advances both lanes in one
   cycle. Two provisos, both handled at setup rather than per step: the
   x-lane's sign would leak a borrow into the y-lane, so the stored step
   pair pre-compensates (`stepy' = stepy + (stepx >> 23)`); and a genuine
   x-lane wrap would carry, so the host pins the camera's raw position to
   the middle of its range (`(raw & $3FFFFF) | $400000` — bit 22 and above
   sit over every index bit both tiles use, so residues are untouched).
2. **Paired constants load in one cycle through L space.** `move l:<addr,y`
   fills y1:y0 from X:addr and Y:addr together: the step pair, the two
   shift-multipliers, the two masks, and the camz8/$FF00 pair each cost one
   cycle to bring in, so nothing needs to stay resident and the registers
   stay liquid. L pairs need the X side of the low addresses, which the
   near tile currently owns — so the tile moves to X:$1000 and is fetched
   through `x:(r0+n0)` with n0 = $1000, which is the same one-cycle access
   with no added instruction. X:$40-$FFF becomes spare (the phase-5 mid
   tile's natural home).
3. **The height arrives pre-scaled.** Repacking the sample as
   `height<<8 | colour` (spare byte moves to the top) makes `packed & $FF00`
   exactly the `dz << 8` term's subtrahend: `dz8 = camz8 - (packed & $FF00)`
   with no shift at all, and no sign trap since bit 23 is always clear.
4. **The steps inline into the DO bodies.** Dropping the JSR per step saves
   its overhead and, more importantly, makes `ENDDO` legal for the
   early-out — from a called subroutine it would pop the wrong stack frame,
   which is why phase 2 deferred it.

The per-frame bias walk also absorbs the row base (frame_setup writes
`bias + rowbase` into the scaled table), removing one add per step. Counted
on paper the inlined hidden-path body lands at 25-28 cycles before
parallel-move folding, against ~110 today; the march at 320 rays drops from
~130 ms toward ~31 ms. The parity marcher needs only the packed-format
change: the dual-lane walk is arithmetically identical to independent adds
once wraps are pinned away, and the re-centering touches no index bit.

## 8. Phase 5 — tiles and level-of-detail

The 64×64 retreat cost full-detail radius: the near march stops at 32 units
because the tile is camera-centred. Recover quality in this order:

1. **Frustum-place the near tile.** Origin ahead of the camera along the
   heading instead of centred: the same 4,096 words give ~48-56 near steps
   forward. The toroidal strips already make re-placement cheap; a turn
   sweeps the origin and costs a few strips per frame (bounded by turn rate;
   estimate ≤0.5 ms at full rudder, measure it). The march length becomes
   heading-dependent at the diagonal — clamp near steps to what the
   placement guarantees and let the far march absorb the rest, exactly as
   the 32-step clamp does today.
2. **A mid tile in the spare X.** X has ~11.9K free words above the near
   tile inside the XBIOS ceiling. A second 64×64 tile at 2:1 (4,096 words,
   ±64 units) turns the schedule into 32@1 + 16@2 + far@8 — the 8:1 far data
   stops being visible at 33 units, which is the current scheme's weakest
   pixel. A third level at 4:1 fits too if captures justify it. All of it is
   schedule-table work (`gen-dsp-tables.py` already derives from
   `proto.inc`) plus one more strip source on the host; the kernel gains one
   more `DO` block per column, one branch per column as before. Inspect the
   level seams against the oracle the way PORTING.md prescribes for
   near/far.
3. **Contingency: the full 128×128 near tile.** Physically addressable
   (§2), blocked only by the XBIOS reservation. Taking it means owning the
   DSP outside the XBIOS allocator (raw host-port bootstrap, or reserving
   around whatever the 344 words prove to be in phase 1). Costs: the XBIOS
   loader convenience, TOS-friendliness on exit, and coexistence with
   anything else that might use the DSP later (sound). Decide only if the
   mid-tile ladder's captures still show the near boundary; do not spend it
   pre-emptively.

The far tile stays 64×64@8:1 in Y (±256 units, past `HIGH.DTL`'s 250). The
packed word's spare byte remains unspent — the mid tile is a cleaner use of
memory than a second sample squeezed into the near word.

One more schedule shape to weigh here: the VoxelSpace reference
(github.com/s-macke/voxelspace) marches a smoothly *growing* step —
`z += dz; dz += 0.2` — rather than fixed tiers, and the DOS original's 250
DTL steps reaching ~985 units imply a similar table-driven curve. The
kernel's schedule is already table-driven per step (reciprocal and bias walk
together), so tier granularity is a generator decision, not a kernel
rewrite: more, smaller tiers approximate the smooth curve and soften the
near/mid/far seams at no inner-loop cost beyond the per-tier delta swap.

## 9. Phase 6 — composition beyond the flat clear

Only after the pipeline exists, because overlap changes what is worth buying:

1. **320×200.** The original's aspect. Forty fewer rows is −17% on the
   clear, the fill's worst case, and VIDEL's scanout share of the bus —
   the last being a term no CPU optimisation can otherwise touch. T-Rex
   carries the register-programmed Videl mode pattern with save/restore
   (`trex_m68030.s:2760-2896`); Chō Ren Sha's timing table is the other
   precedent (PORTING.md). Cost: re-deriving the console/horizon layout,
   which is currently tuned for 240 rows. Decide with a capture comparison,
   not in the abstract.
2. **Stop repainting what did not change.** The DSP knows each column's
   final occlusion row; the previous frame's rows are one 320-word array
   away. Sky repair (copy from a pristine sky strip where the silhouette
   dropped) plus ground-remainder rectangles from the kernel would replace
   the full background pass. **Caution imported from T-Rex:** its delta-clear
   variant measured *slower* than the flat clear — dirty tracking has real
   constant costs. Prototype behind a flag, measure at matched frames,
   adopt only on a clear win.

### Phase 6 outcome (2026-08-15)

**320 rays: 9.79 FPS at 102 ms; 160 rays: 12.10 FPS at 83 ms — both
oracle-exact at zero differing pixels, flying clean.** Cumulative since
first light: 2.39 → 12.10 at the 160 geometry, five-fold.

The incremental composition went in as designed, resting on two invariants
the earlier phases established: terrain records tile [top, floor) exactly,
and the floor seed keeps them off the solid console block. So the static
backdrop — sky, ground base, console, fixed instruments — renders once
into a template by the same routines the classic path calls per frame; the
kernel appends each column's final occlusion row after the record sentinel
(one counted strip, sub-millisecond); the host keeps a silhouette history
per buffer and repairs only the spans that receded; sprites recorded
unclipped by a hook in the scaled blit are restored from the template
before the next frame's records land, with list overflow buying one
classic backdrop frame instead of a ghost. A buffer's history initialises
to row zero — assume terrain reached the top — so its first incremental
frame repaints its sky once and is exact thereafter; every classic-path
frame (seed, fallback, heal) resets it the same way.

The one wrong assumption cost a debugging round and is worth recording:
the console floor is the row from which the console is solid TO THE
BOTTOM — `console_build_floor` scans upward for the first clear pixel —
not the first opaque row. The canopy struts float ABOVE that boundary with
transparency around them; terrain paints behind them and the classic path
repainted them every frame without anyone noticing that dependency. The
first incremental build measured 11.7/15.1 FPS and had lost the struts'
upper halves — ~1,000 differing pixels the gate caught precisely.
`console_draw_upper` now repaints just the floating region (bounded by the
new `console_solid_row`), most of whose rows are two-read skips, and the
honest numbers stand above. The parity gate needed no changes to serve as
this machinery's oracle: the template is built by the classic path's own
routines, so any composition bug is a differing pixel.

The remaining frame splits roughly march-and-fill against object, game,
HUD and loop overhead. The next candidates by the numbers: the 320×200
question (item 1 above), the ~15 ms class of remaining fill work, and —
before any of it — the hardware run this document has owed since phase 1.

### Where the frame actually goes (2026-08-16)

The first stage split taken with the frame's own profiler, `USE_DSP=1`,
320 rays, benchmark camera, Hatari:

| build | frame time | implies |
|---|---:|---|
| baseline | 122.1 ms (8.19 FPS) | |
| `BENCH_NO_TERRAIN=1` | 81.6 ms (12.25 FPS) | terrain stage **40.5 ms**, 33% |
| `BENCH_NO_HUD=1` | 108.7 ms (9.20 FPS) | HUD **13.4 ms**, 11% |

A third isolation names most of it: `BENCH_NO_OBJECTS=1` measures **78.0 ms
(12.82 FPS)**, so the **object pass costs 44.1 ms - 36% of the frame, more
than the entire terrain stage.** The split is therefore objects 44.1, terrain
40.5, HUD 13.4, and about 24 ms of `game_tick`, buffer exchange, loop and VBL
quantisation.

**The remaining ~68 ms - 56% of the frame - is neither terrain nor HUD.** It is the object
pass, `game_tick`, the surface and template work outside the terrain stage,
the buffer exchange and loop overhead. Every phase of this plan so far has
optimised the third of the frame that the march and fill occupy, on the
assumption that they dominated. At 320 rays they do not, and the largest
single stage is one no phase has ever examined.

What follows from it, in the order rule four puts them: **cull before
drawing** - `object_draw_pass` transforms, depth-sorts and scale-blits every
one of `0.MIS`'s 139 placements, and the cheapest work is the sprite never
drawn because it is behind the viewer, past the march's 992 units, or under
terrain already written; then **stream what survives** - scaled sprite
blitting is regular per-pixel work over a known rectangle, which is the
same shape as the terrain fill the kernel already serves, and the first
DSP candidate outside the march.

Two cautions on these numbers. `BENCH_NO_TERRAIN` also removes whatever
background and template painting sits inside the terrain stage, so 40.5 ms
is the stage, not the march alone. And this is Hatari, which charges the
68030's arithmetic differently from silicon - the hardware run this document
has owed since phase 1 is now the gate on believing any of it.

The harness needed fixing first, and the failure is worth recording: the
`BENCH_NO_*` defines were not in `build-run.sh`'s forwarded list, so every
stage isolation silently built the unmodified program. Three separate
measurements came back at exactly 8.19 FPS. A stage split whose parts agree
to the decimal is a broken harness, not a result.

**On SSI/DMA (§10), asked directly:** no. Both directions of DSP transport
live inside the 40.5 ms terrain stage and were estimated at ~1 ms inbound and
~3 ms outbound at 320 rays. Removing all of it buys about 3% of the frame and
cannot touch the 68 ms. The contingency stands as written - revisit only if a
larger tile makes inbound traffic a measured cost.

### The cull, measured: right code, wrong target

Built as designed - a range test against `OBJ_DRAW_RANGE` and a fan test on
`|lateral| > depth`, both single compares taken before the handler runs, so a
rejected object pays neither the three 32-bit divides in `object_draw_sprite`
nor a blit. With the per-frame counters the standing check demands.

The counters, read out of memory at VBL 5000 on the benchmark camera:

    object_culled_range = 0
    object_culled_fan   = 10
    object_drawn        = 0

and the frame moved 122.1 ms to 121.1 ms, which is noise.

**Nothing was being drawn.** Ten objects survive the active and
behind-the-viewer tests and every one is off the side of the screen; none is
in front of the camera at all. So the 44.1 ms that `BENCH_NO_OBJECTS`
removes is not sprite blitting - it is `object_view_transform` and
`object_depth_sort` running over all 130 slots regardless of how many are
alive. The sort is the recovered selection sort, O(n²), which is ~8,450
`.depth_of` calls per frame to order ten objects that are then all discarded.

That is the same principle one level up, and the real fix: **compact the
active objects into a list first, then transform and sort only that list.**
Ten survivors instead of 130 slots turns the sort's 8,450 comparisons into
45. The cull stays - it is correct, its counters prove it fires, and it will
matter the moment objects are in view - but it is not what buys the 44 ms.

Worth stating plainly because it is the point of the standing check: without
the counters this would have read as "culling gains 1 ms, not worth it". The
counters say instead that the cull never had anything to cull, and point at
the stage that actually costs.

### Compaction: 122.1 ms to 79.1, and the frame's largest stage is gone

`object_depth_sort` filled the identity 1..130 and sorted all of it;
`object_draw_pass` then walked all 130. Both now work on the **active** slots
only - the fill collects them into `object_order`, records `object_live`, and
the sort and the draw loop run to that count.

The ordering is unchanged for everything observable: the draw loop always
skipped inactive objects, so where a dead slot sat in the order was never
visible. Only the cost changes, and it changes by the square: **20 live
objects among 130 slots** on the benchmark camera, so the O(n²) selection sort
went from ~8,450 depth lookups a frame to ~190.

**122.1 ms → 79.1 ms, 8.19 → 12.65 FPS, a 1.54× frame.** The check that makes
it believable is independent: `BENCH_NO_OBJECTS` measured 78.0 ms, which is
what removing the stage *entirely* buys. Compaction lands 1.1 ms off that
bound, so the object pass now costs about a millisecond instead of 44.

One measurement caveat, learned from the counters disagreeing between runs.
The cull tallies read 10 fan-culled before compaction and 0 after, which looks
like a regression and is not: object positions at a given VBL depend on how
many frames have been rendered by then, and the faster build has run ~1,265
update passes to the slower one's 819. **Counter comparisons between builds of
different speed are not like-for-like** - the objects are genuinely somewhere
else. Compare counters at equal *frame* counts, or against a frozen camera
with `BENCH_FREEZE`.

The revised split, with terrain 40.5 ms and HUD 13.4 unchanged: the frame is
now terrain 40.5, HUD 13.4, and ~25 ms of everything else. Terrain is once
again the largest single stage, which is where the DSP plan's own phases
resume - and this time on measured grounds rather than assumed ones.

### Pipelining is a no-op twice, which names the critical path

`DSP_PIPELINE=1` measures **79.1 ms, 12.64 FPS** against the default shape's
79.1 ms and 12.65. Identical, and identical for the second time - phase 3
recorded the same equality at 7.71 FPS when the frame was nearly twice as
long and 44 ms of object work still lay over the march.

That equality now says something it could not say then. Stage B overlaps the
march with the *entire* remaining frame; if the frame were waiting on the DSP,
that would show. It does not, at either frame length. **The march is not the
critical path - the host is.** Inside the 40.5 ms terrain stage the cost is
the drain and the fill, not the marching.

Two consequences, and they point opposite ways to the plan's stated order:

- **Phase 4's inner-loop rewrite buys nothing.** Making the kernel's march
  faster shortens a stage that is already finishing early. Do not spend it.
- **The host-side drain and fill are the lever**, which is exactly where
  §6.1 of F030TREX says the work belongs anyway, and where Chō Ren Sha's
  technique applies directly: a length pre-baked by the DSP as a **jump offset
  into an unrolled ladder**, so a run costs its writes and nothing else - no
  counter, no loop branch, no per-span setup. The kernel already emits
  counted records; making the count a jump offset is a protocol change of one
  field.

The frame after this session: terrain 40.5 ms, HUD 13.4, everything else ~25.
Those figures belong to the historical DSP experiment, not to the current
CPU-only attract milestone.

### The ladder is the right change and this harness cannot measure it

Stopped before writing it, on the harness's own terms. §2 records that Hatari
under `--mmu true --dsp emu` charges **CPU instruction execution zero time**
and counts only bus traffic and IO waits. The unrolled ladder removes a
`dbra` per row - instruction overhead - while emitting exactly the same
stores. **Its measured gain here is structurally zero**, and a null result
would say nothing about the change.

That is not an argument against the ladder. It is an argument that the
hardware run this document has owed since phase 1 is now a *prerequisite* for
the next step rather than a nicety: the remaining CPU-side wins are
instruction-count wins, and this harness is blind to exactly those.

What Hatari can still measure honestly is **bus traffic**, which points the
work at store count rather than store cost:

- **Fewer stores.** The fill writes every pixel of every record. Records that
  a nearer record will overwrite are pure overdraw, and the kernel emits them
  far-to-near, so it knows. Rule four's first clause applies inside the
  terrain stage exactly as it applied to the objects.
- **Wider stores.** At 320 rays `TERRAIN_XSTEP` is 1, so the fill is
  `move.w` per pixel; the 160-ray path already doubles the colour into a
  longword and gets both pixels in one access. Merging horizontally adjacent
  records of equal colour and span into one longword run would buy the same
  halving at full quality - and the record stream is already sorted by
  column.

Both are measurable here today. The ladder, and phase 4's inner loop, are
hardware work.

### What F030TREX says about the two things we are about to do

Its `OPTIMIZATION.md` is a measurement log for this machine profile, and two
of its sections bear directly on culling the object pass and offloading what
survives.

**§6.1 qualifies "move as much as possible to the DSP".** In its own words: a
DSP pixel engine would have to send pixels or spans back to the 68030, which
**replaces arithmetic cost with communication cost**. That project keeps pixel
coverage and framebuffer writes on the CPU deliberately. It does not
contradict rule four - it sets where the line falls. What travels well is
*decisions*: which sprites survive, which pixels are covered, how long each
run is. What travels badly is the pixels themselves. Chō Ren Sha lands on the
same side of that line - its DSP emits an RLE of spans, and the 68030 does
every `move (a1)+,(a2)+`.

**§2.3f is the cautionary tale for the culling we are about to write.** T-Rex
built a triangle-culling prepass, validated it against byte-identical
framebuffers, and only later established with DSP breakpoints that it **had
never killed a single triangle in any validated run**. The images matched
because both arms ran the same unculled path. Four independent defects each
sufficed to keep the stage inert, and two of them reported healthy-looking
numbers while doing so - a capacity overrun whose sentinel was overwritten by
the next increment, and a one-hot cursor that sign-extended at bit 23 and
silently stopped after twelve cells.

Its §6.2 generalises the same failure from the other end: an ordering-table
key that clamped every triangle into the last bucket for 125 frames, where
"pixel counts, survivor counts and timings all stayed plausible while the
depth order was gone."

**So the standing check for this work: an optimisation must report a counter
proving it did something, and the counter must be one that cannot be
manufactured by the failure path.** Not a frame time, not a pixel diff -
kills, culled sprites, coverage bits set, runs emitted. This project has now
hit the same class of failure three times in one day: `BENCH_NO_*` defines
that were not forwarded and produced three identical measurements, and before
that the row-count table read from dead initialisers. The pattern is a stage
that silently does nothing while every aggregate number stays believable.

Two more transferable pieces, both measured there: **range-restricted walks** -
visit only the cells a survivor's clamped screen box overlaps, and exit at the
first cell that fails - which is what took its prepass back inside the frame
budget; and a budgeting lesson from §6.2, where removing the Z-buffer was a
*net loss* until the register it freed was spent on the pixel loop. Its
conclusion is worth carrying verbatim: budget the two as one step, not two.

### The Chō Ren Sha coverage bitmap, and why it fits the object pass

`F030Arcade/third_party/chorensha/sources/atari` solves exactly the problem
rule four now points at, on this machine, with the DSP. Worth reading before
designing anything: `dsprite.asm` and `graphics.s:clear_sprites`.

Its per-frame loop is `receive_sprite_infos`, `draw_inverted_masks`,
`create_rle_data`, `send_rle_data`, `swap_sprite_infos`, `draw_masks`. The
DSP holds a **one-bit-per-pixel coverage bitmap of the whole screen**, 24 bits
to a DSP word, `16+256+16` wide - the play area plus a guard column each side
so a sprite straddling an edge needs no clipping test. `draw_masks` ORs each
sprite's 16x16 mask into it; the 1,885 masks are uploaded once at boot, not
per frame.

`create_rle_data` then scans that bitmap and emits the **exact union** as
alternating offset/length pairs in screen-word units. Three things make the
scan cheap: `rol a` walks bits through carry so the inner test is one
instruction; a whole packed word that tests zero skips 24 pixels at once
(`_skip_empty_data`), which is the common case on a mostly empty screen; and
the offsets accumulate through `b` with pre-loaded constants for
pixel/word/line steps rather than being recomputed.

The consumer is the part worth stealing outright.
`graphics.s:clear_sprites` reads a length word and does
`jmp .jump(pc,d0.w)` **into a sixteen-deep unrolled ladder of
`move (a1)+,(a2)+`** - the run length is pre-baked by the DSP as a jump
offset, so restoring a run costs the copies and nothing else: no counter, no
loop branch, no per-run setup. `RLE_LONG_EVEN_BIAS = RLE_RESTORE_WIDTH+4`
handles runs longer than the ladder by wrapping through a preceding `BRA.W`,
and a negative offset word ends the stream. Their figure is ~4,000 RLE values
per frame for a bullet-hell screen.

**Against what this port does now.** `dsp_restore_rects` restores a bounding
rectangle per sprite from the template. That pays three times over: a
rectangle is mostly not sprite, so its transparent margin is restored anyway;
overlapping sprites restore shared pixels twice; and each rectangle carries
its own setup. A coverage bitmap pays once for the exact union, and the
scan-and-emit half of it is DSP work of precisely the regular kind rule four
admits - the same kernel already owns a screen-sized array of per-column
occlusion rows, so the machinery is not foreign to it.

The order rule four sets still holds: cull first, because a sprite culled
never sets a coverage bit either, and the bitmap gets cheaper for free.

## The original's renderer, decoded (2026-08-15)

An instruction-level read of the DOS marcher (re/listings, `0000D950`
onward) against this port's three renderers. The headline correction to
the semantic map: the original is not a per-column raycaster. It is a
**depth-ring renderer** — the outer loop walks 250 constant-z rings front
to back, the inner walks all 192 columns of one ring laterally in world
space, and there is neither a multiply nor a divide in the inner loop:
projection is one byte lookup in a per-ring 256-entry page, built once per
detail level as `clamp((relheight−128)·K/z + horizon_ring)`.

What all three implementations share, exactly: the per-column rising
occlusion row with strictly-above acceptance; front-to-back order; a
1024×1024 toroidal map addressed height and colour at one index; colour
bytes carried to the surface **unmodified** — the original has no fog, no
distance shading; a planar (flat) fan — the .DTL lateral table satisfies
`lat = z/100` exactly, so all samples of a ring lie on one line and one
reciprocal per ring serves every column, which is the same geometry as
this port's linear fan interpolation.

Where they differ, and what phase 7 did about it:

| | DOS original | 68030 classic | DSP kernel |
|---|---|---|---|
| Traversal | z-major rings | column-major rays | column-major rays |
| Columns | 192/96/40 by .DTL bank | 320 | 320 or 160 |
| Viewport | 192 px wide (x=32..223) | full width | full width |
| Depth schedule | 250 asset-defined steps to ≈985 | 83 steps to 992 (adopted) | 83 steps to 992 (adopted) |
| Projection | per-ring 256-byte page | bias[z] + dz·invz, tables | bias[z] + dz·rscale, tables |
| Slope | 150/z, page rows 1:1 on the 240-row screen (recovered) | 150 at 1:1 rows (adopted, corrected 2026-08-17) | same (adopted) |
| Camera height | alt/2 + 1 in map bytes - the AL bias is 127-floor(alt/2) against the page's k-128 | adopted | adopted |
| Span rows | [old horizon, new top): the projected row goes to the next deeper sample | adopted (2026-08-17) | adopted |
| Fan half-tan | 0.96 | adopted | adopted |
| Horizon | per-ring curve 60→137 | same curve, .DTL table 3 | same |
| Early-out | none; page saturation | per-column, output-equal | ENDDO, output-equal |
| Map residency | two flat 1 MB maps, GS | two flat maps | toroidal windows + resident 32:1 whole-map tile |
| Pitch | global row bias | CMD_W_PITCH trim | same word |
| Roll | per-column shear, self-modified into emitters | not implemented | not implemented |
| Sprites vs terrain | per-ring silhouette archive clips them | painted over | painted over |
| Sky | per-column fill to the terrain horizon | image to a fixed row, terrain overwrites | same via template |

The two structural inventions the original used and this port does not
need: the 48-byte self-modifying emitter blocks (a Duff's-device span
writer per column, patched at init with the colour-map base and per frame
with the roll shear) exist because the 386 had no cheap indexed span
setup — the Falcon's record stream and host fill replace them; and the
2-D projection-page table exists because the original could afford 64,000
bytes of table per detail switch but not a multiply per sample — the
56001 does the multiply in one cycle, so the kernel keeps the curve in 83
reciprocal words instead of 250×256 bytes.

Still open against the original, in order of visibility: sprite
depth-clipping against the terrain (the original archives each ring's
silhouette and clips sprites at their own depth; a cheap port-shaped
equivalent is the kernel emitting ybuffer checkpoints at the two tier
boundaries), the roll shear (a per-column row offset at fill time, the
natural hook being the host's record fill), and the 192-column cockpit
viewport question, which is a presentation choice this port has so far
deliberately declined in favour of full-width terrain.

### Phase 7 outcome (2026-08-15)

**The original's projection package, adopted whole: slope 180, camera
height alt/2, depth to 992 units, fan half-tangent 0.96, the DOS ground
clamp, the sky image. 320 rays: 9.76 FPS at 102 ms - the 992-unit march
cost three tenths of a frame against phase 6's 256-unit one.** The
terrain is pixel-exact between the kernel and the parity marcher at all
three gate cameras.

The range came almost free: at 32:1 a 32x32 window IS the map, so the
third tier is a resident tile in the X half of the SRAM, uploaded once,
never streamed - the camera pin costs one world-minus-local pair per
frame, added once per column at the far2 prologue. The march grew from
60 to 83 steps; the hot section overflowed internal P and the
once-per-column prologues and tile drains moved cold to pay for it.

Two defects found by the gate, one by arithmetic: the parity build never
built the resident tile (its far2 spans rendered height-zero ground in
palette colour 0 - 4,134 pixels); the z=1 reciprocal times the new scale
passes +1.0 in the kernel's 1.23 rebuild, so the store now goes through
the limiter and the generator clamps its copy to the same $7FFFFF; and
the taller projection lifted distant spawned objects into the gate
cameras' view, where render-speed-dependent positions made the two
builds' sprites diverge - gate builds now freeze the object pass
(BENCH_FREEZE), which put the sprites at equal positions and shrank the
diff to a ≤180-pixel band of sprite-layer divergence at rows 49-71 that
is STILL OPEN: terrain agrees everywhere, the far2 cell selection is
proven bit-identical in simulation, and the remaining difference sits in
the object layer between the composed and the direct build. It is
invisible in play and does not gate the attract work; it is recorded
here so it does not get forgotten.

The flight model also moved onto a real time base this phase: per-VBL
rates scaled by the VBLs the frame consumed, so ground speed is the
machine's, not the renderer's. The 160-ray geometry's re-gate and
re-measure ride with the next build cycle.

### The projection package corrected to 1:1 (2026-08-17)

Phase 7 adopted the recovered package through a conversion premise - "the
original's 200-row view, scaled by 240/200" - that phase 8b's own
discovery invalidated hours later: **the DOS mode is 328x240**, and the
two claims sat unreconciled in this file. An audit against the primary
sources settled it: the original's page rows land on its 240-row screen
**unscaled**, as `screen row = 198 - page row`.

The evidence, each item checkable from the repo: the in-game screenshot
writer's own header at `000165FD` says ymax 239/vdpi 240; the scanline
table at `0002D7F0` gives the terrain surface 199 usable rows - a
viewport, not a screen; `SKY2.RLE` is authored 320x240; and decoding
`CONSOL1S.DTA` puts the windshield's measured bottom at row 138, which is
exactly where the .DTL's nearest-ring bias (page 60) lands under the 1:1
mapping - the asset and the cockpit art agree only at 1:1. Under the old
conversion the port drew every slope 20% too steep and the far horizon 15
rows too low (76 against the original's 62).

Three corrections landed together, as a package like the original one:

- **Slope 150 and bias `198 - (dtl3 >> 8)`** in both generators; the far
  horizon is now row 62, the nearest ring row 138. The 198 anchor is
  confirmed to one row either way; the KYLE/Alt-P DOS screenshot pins it
  exactly once that recipe works.
- **Camera height alt/2 + 1**: the marcher's AL bias is `NOT(alt)>>1 =
  127 - floor(alt/2)`, and the page's `(k - 128)` puts the level plane
  one map byte above alt/2. Host, both CPU marchers and the object
  placement all carry the +1 now; without it everything projected 150/z
  rows high and objects floated.
- **The DOS span convention**: the original's emitter paints
  `[old horizon, new top)` and gives the projected row itself to the next
  deeper sample; the port painted `[new top, old occ)`. All three
  renderers now emit one row below the projected row down to the stored
  row inclusive, clamp the projected row at -1 rather than 0 (so the top
  screen row still goes to a deeper sample, matching the original's page
  saturation), and the floor seed became the LAST VISIBLE row (the host
  uploads console floor minus one) so the composed console is never
  touched. The kernel's early-out moved from stored-zero to
  stored-negative and remains output-equal; CMD_VERSION went to 6 so a
  stale .lod refuses rather than painting one row off.

Sub-row caveat, recorded so nobody chases it as a bug: DOS floors the
combined `(k-128)*slope + bias` sum once, in the page build; the port
floors the projection term and adds an integer bias, so specific dz/z
pairs can land one row apart. The anchors (level plane, horizon rows)
are exact; only mid-slope boundaries can differ, below the port's own
column-resampling differences.

Deliberate deviations that remain, unchanged by this correction: the
tiered schedule against 250 rings, the decimated far tiers, the
320-column full-width fan against the original's windshield (whose
cutout measures ~300 px wide - the DOS blit stretches its 192 rendered
columns into it through per-span copy records built at `00006FEF`; not
fully decoded), and the renderer heading at 256 steps of an 8.8 sine
against the original's 512 steps of the Q31 table - that last one is an
open fidelity item, not a platform necessity.

### The far field at 4:1 and 16:1, and the sky's real shape (2026-08-17)

Two fidelity items in the same pass, both from looking at what the screen
actually shows against the original.

**The far tiers halve their cells.** The far tile moves from 8:1 to 4:1
(64 cells now span 256 units, march z=36..128 at 4-unit steps) and the
resident whole-map tier from 32:1 to 16:1 - where a 64x64 tile IS the
1024-unit torus exactly, so the 2x2 replication the 32:1 tile needed is
gone and the field mask wraps at the map's own period. The schedule is
now 32+24+54 = 110 steps to z=992 against the old 83; lateral and depth
sampling double everywhere past the near tier, which was the visibly
blocky part of every frame. The march grows ~33%; the phase-3 result
that the march hides entirely under the CPU frame absorbs it (re-measure
recorded below). Same SRAM budget: both tiles stay 4096 words, the
decimated host pair grows to 256x256 bytes.

**Known window artifact, now written down**: every tier marches to
exactly its half-window depth, but a fan-edge sample lies up to
1.386*z from the camera per axis (forward 1, lateral 0.96, heading
diagonal), so the outer ~28% of each tier's depth can wrap the toroidal
window at the fan's edge columns and sample a line from the window's
other side. Scale-invariant - the 8:1 tiling had it in the same
proportion - pre-existing, and pixel-identical between kernel and parity
because both wrap the same way; the original has flat maps and no
windows, so it never does this. Fixing it means marching each tier only
to half-window/1.386 or growing windows; neither fits this pass.

**The sky was never a 320x240 raster.** SKY2.RLE's payload is 512 column
strips of 150 bytes - column major like TANK and HUDS, the shape the
original's per-column backdrop walker consumes, with the extra width as
roll-shear margin; the single directory record's width byte says 150.
Drawn row-major it produced exactly the sheared diagonal cloud streaks
the port shipped. `sky_init` now transposes the leftmost 320 strips into
a row-major image at load (which 320 of the 512 the original anchors is
not recovered; the choice is recorded), `render_clear` blits all 150
authored rows, and the mountain silhouette along the image's base sits
below the terrain horizon, showing only where terrain leaves it
uncovered - as in the original in level flight, which has pitch to
expose it and this port does not yet.

## Phase 8: the attract mode (2026-08-15, first light)

**The DOS attract cycle runs on the Falcon: openings, the panning title,
and recorded demo flights through the original's own flight integration,
looping in the original's pass structure with any key out into free
flight.** The recovery that carries it is instruction-level and recorded
in docs/X86-M68K-MAP.md: the corrected flight model (the old map had
`[19DFC]` as the heading; it is the altitude, and the heading is the
32-bit angle `[19D04]` through Q31 hi-multiplies), the DEMO*.SCR byte
format verified against all four shipped recordings, and the state
machine at 00005690 with its exact tick counts and any-key exits.

New on the Falcon side: `flight.s` (the integration ported
arithmetic-for-arithmetic - five-rate damping with the `or al,bl` quirk,
the axis scalings and clamps, the terrain-follow ladder with the landing
stop and the original's crash threshold, the 9-bit altitude average, and
hi32 products against the sine table extracted verbatim from the image
at 00032120), `demo.s` (loader and per-tick record feed - one record per
integration tick, two VBLs per tick, which is the recording's ~25 Hz),
and `attract.s` (the cycle, the Kyle DTA screen decoder with its
in-stream palette, the extracted ZOVE/COMA animation tables, the pan
with its wobble, double-buffered screen flips, and overlay sprites drawn
through their bank's own palette - the shared flight palette painted
COMA's opaque black ground bright green). Free flight now rides the same
integration with the keyboard synthesised onto the stick axes.

What first light taught, in order: the screen DTAs decode their palette
through the same RLE stream as the pixels; FANFARE.RLE is the fanfare
audio, not a graphic - the opening shows BACK.DTA alone, as a silent
port must; the boot takes ~1,200 VBLs before the cycle begins (the map
decompressions), which had every early capture reading uninitialised
VRAM as a defect; screens must flip like the game or the pan tears; and
a screen-to-flight transition needs a two-frame surface reseed - one
classic repaint per buffer, console included - because the screens paint
over both persistent surfaces and the incremental composition otherwise
keeps compositing over title art.

Deliberately not in this first light, each recorded where it lives:
the startup/default mission now follows its authored D1/C1/SKY2 resource
list, and each attract pass selects its own mission's D/C pair and sky (the
first natural flight is pass 1, the nighttime SKY4 record; DEMO0/day appears
when the counter wraps to pass 0); BACK.DTA's centre is a runtime composite
this pass renders as its stored dark plate; the overlay
positions are eye-placed pending capture comparison against DOSBox; the
collision bounce and damage spin of the flight handler are constants on
record, not yet code; and the attract exits to free flight where the
original exits to a menu this port does not have yet. Music and the
speech sample wait on rule one's later audio phase.

## Phase 8b: the attract mode, measured against its own assets

**Everything the first light left to the eye is now taken from the
original.** The state machine was right; the surface it painted on was
not, and four independent errors were sitting on top of each other. Each
is set out with its evidence in `docs/X86-M68K-MAP.md` under *The attract
screens*; in short:

- **The screen is 328x240, not 320x200.** The DTA headers say so, the
  CRTC stride `0x52` per plane says so, and TPIC's 390 rows are the 240
  shown plus the 150 the pan travels. The letterbox is gone.
- **The pan is the CRTC start address**, one row per tick to row 150,
  and the 64-entry bump rides the *helicopter*, not the pan. The
  helicopter is not drawn at all until the pan reaches row 93.
- **The overlay anchor is bottom-left**, `[0002587C]` fixing the left
  edge and `[00022366]` the bottom row, which is what
  `sprite_draw_opaque` already implemented for the cockpit.
- **A bank is translated into the screen's palette at install**, by a
  nearest-colour table the original then runs the whole pixel payload
  through. Untranslated, COMA is coloured noise shaped like a
  helicopter.

What made this tractable was tooling, and both pieces are worth keeping.
`tools/grab-frames.sh` breaks N times inside one Hatari pair instead of
running two passes per frame: ten frames of the cycle now cost what one
used to, which is the difference between guessing at a sequence and
watching it. `tools/render-attract-ref.py` renders the same screens
straight from the installed assets, independently of the 68k, and it is
what turned "the helicopter looks speckled" into "the bank is authored
against a different palette" in one comparison rather than one capture
cycle per hypothesis. The oracle habit that carried the DSP kernel works
just as well on a title screen.

Still open after this pass: mission-specific object banks and the remaining
type-specific runtime consumers; BACK.DTA's centre is a runtime composite
rendered here as its stored plate; the fanfare's early exit needs the
audio phase, so the opening holds its full 480 ticks; and the cycle still
leaves into free flight where the original leaves into a menu.
3. **Blitter span fill.** The project has prior art in-tree: F29's polygon
   filler runs the blitter in halftone mode with per-line restarts
   (`reference/f030f29/src/dp_hc.s`, 1994 — the exact 16-word halftone
   colour-fill trick), and its span drawer programs destination/count/start
   per segment (`f29.s` `.dh_run`). For 16-bit vertical runs the setup is
   ~5 register writes per rectangle vs h word-stores; it can only win for
   tall rectangles, and only in shared mode does it buy overlap. The
   phase-1 fill measurements decide; wire it as a fill-path alternative
   behind the same rectangle buffer if the numbers say so.

## 10. Phase 7 — SSI/DMA tile streaming (contingency only)

The full design — crossbar register values, DSP-mastered clock at ~1 MB/s,
ping-pong buffers with generation/CRC, and the two open blockers (68030
data-cache coherency against DMA writes; sound-DMA ownership) — already
exists in F030TREX `OPTIMIZATION.md` §7.4 and in PORTING.md's transport
section. Do not build it on spec. The HI08 strip traffic is estimated well
under a millisecond per frame; SSI streaming becomes interesting only if
phase-5 re-placement or a future 128×128 tile makes inbound map traffic a
measured frame cost, and it collides with the deferred sound milestone's
claim on the connection matrix. Revisit with numbers.

## Where the frame goes now (2026-08-17), and why the DSP cannot take it

Re-measured after the column-width correction and the parallel-move pass.
USE_DSP=1, TERRAIN_HALF=1, benchmark camera, 5000 VBLs.

| build | frame time | implies |
|---|---:|---|
| baseline | 54.9 ms (18.22 FPS) | |
| `BENCH_NO_TERRAIN=1` | 31.9 ms | terrain stage **23.0 ms, 42%** |
| `BENCH_NO_HUD=1` | 41.5 ms | HUD **13.4 ms, 24%** |
| `BENCH_NO_OBJECTS=1` | 53.0 ms | objects **1.9 ms, 3%** |

leaving about 16.6 ms of `game_tick`, buffer exchange, loop and VBL
quantisation.

**The object pass is fixed.** It was 44.1 ms and the largest stage in the
frame when the split was last taken; compaction took it to 1.9. Nothing more
is owed there.

**The terrain stage is not computation.** On a USE_DSP build the DSP does the
marching; what the 68030 spends 23.0 ms on is draining records and writing
pixels. The viewport is 320x140, and at TERRAIN_XSTEP=2 `draw_span` already
stores one longword per two pixels, so a full repaint is 22,400 longword
stores. At the 16 cycles a store to ST-RAM costs on a 16 MHz 68030 that is
**22.4 ms against a measured 23.0** - the stage is its own memory traffic
and essentially nothing else.

**So it cannot move to the DSP, and not for want of trying.** The DSP has no
bus access to Falcon screen memory. Everything it produces leaves through a
16-bit host port one word at a time and the 68030 writes it. Work moves to
the DSP profitably only when it is compute-heavy and output-light; a screen
fill is the opposite, and the marching that *was* compute-heavy is already
there.

The lever on 23.0 ms is therefore **writing fewer pixels, not moving work**.
That is what the incremental composition does - build the static backdrop
into a template once, keep a silhouette per buffer, repair only the spans
that receded - and it is already active on this path. Beyond it the
candidates are:

1. **The HUD's 13.4 ms**, which is the same problem one stage over: console
   art blitted per frame. The incremental path already persists the solid
   console block and repaints only the floating canopy, so what remains is
   that repaint plus the instruments. Worth a stage split of its own before
   assuming.
2. **Merging adjacent same-colour spans** in the record stream so the host
   issues fewer, longer runs. The DSP can do this merging - it is
   compute-heavy and output-light, which is exactly the profitable shape.
3. **The unprofiled 16.6 ms.** It is the second largest block in the frame
   and nothing has ever been isolated inside it.

## Audited against F030MXDRV's DSP56001 notes (2026-08-17)

`../F030MXDRV/docs/dsp56001-notes.md` distils the manual rules that project
learned the hard way. Checking this kernel against each found one real gap,
three already handled, and bounded what is left.

| Rule | This kernel |
|---|---|
| A parked modifier register is a time bomb for every later `(Rn)+` walker | **The gap.** M0-M7 were never written; the kernel ran on the reset value. Now set explicitly at `main`. |
| `DO`/`REP` with a zero count runs 65,536 times | Handled. The four variable-count receives in `recv_tile` are the only non-immediate loops, and `tst a` / `jeq recv_tile_none` catches zero before the count reaches `x1`. |
| An indirect address forms before the preceding `Rn` write retires; one instruction must separate them | Handled, and all 20 `nop`s say so in their comments. Every one sits in the frame prologue, the receives or init - **the three march bodies contain none**, so there is nothing to reclaim in the hot path. |
| `(Rn+Nn)` pairs same-numbered registers only | Satisfied: `(r0+n0)`, `(r1+n1)`, `(r4+n4)`, `(r5+n5)`. |
| `TST` sees all 56 bits, so an `MPY` fraction must be purged first | Satisfied, and found independently here: the `move b1,b` before `add b,a` in each march body exists for exactly this reason, with a comment describing the same trap. The later `tst a`/`tst b` are safe because `MOVE` and `TFR` into a full accumulator zero the LSP. |
| Short absolute addressing avoids an extension word and external RAM | Satisfied: the per-column scalars are `VL_*` at L addresses 10-16, inside the 6-bit short-address window, and every reference uses `l:<`. |

**What is left is structural rather than oversight.** The per-sample cost is
two multiplies and two masks to form the tile index, one multiply for the
projection, and an external tile read. Three candidates were considered and
rejected with reasons:

- **`MAC` for the projection.** The `mpy`/`add` pair looks like a `mac`
  waiting to happen, but both already carry their operand fetch in a parallel
  field, so folding them saves one instruction and costs one to get the bias
  into the accumulator first.
- **Hoisting the `l:<VL_*` reloads.** `VL_STEP`, `VL_SHIFT`, `VL_MASK` and
  `VL_DZ` are invariant across a column's march and reloaded per sample
  anyway, because all four data registers are live: the mask, the shift pair,
  the dz constant and the reciprocal cannot coexist in `x0/x1/y0/y1`.
- **The `VL_POS` spill.** The walking position is stored and restored every
  sample because `a` is the only 48-bit adder and the index arithmetic needs
  it. Two accumulators, three uses.

The one unexplored item is `jsr emit_rect` on every accepted sample. Three
call sites, so inlining costs cold-island code space for a few cycles on the
accepting path only - worth measuring if the march is ever the frame's
critical path again, which the last stage split says it is not.

## 11. Robustness

The DSP stays an accelerator, never a dependency — `render_frame_path`'s
fallback shape is right and stays. Add:

- **Resync instead of abandon.** A timeout mid-drain currently leaves the
  port half-full and every later frame broken. On any protocol error: drain
  reads until `RECT_END` or a bounded count, and if that fails, reload the
  kernel (`Dsp_LoadProgram` is milliseconds) and re-upload tiles. Count
  resyncs in a telemetry row; zero is the acceptance value, but one must not
  end the mission.
- **Version discipline.** Bump `CMD_VERSION` on any protocol change; the
  kernel already rejects mismatches loudly (`RES_S_BADVER`).
- **Benchmark matrix.** `USE_DSP={0,1}` × `PARITY_TILE={0,1}` × the attract
  demo checkpoint, captured at matched VBL counts. The CPU oracle build is
  part of the matrix forever; terrain geometry is fixed by the DOS 192-source
  column walk and the displayed source window 16..175.

## 12. Budget and targets

Estimated stage costs after phases 2-4, stock profile, to be replaced by
phase-1/phase-4 measurements (all Hatari-optimistic until the hardware
checkpoints):

| Stage | 192 source columns / 320-pixel surface | Notes |
|---|---:|---|
| DSP march | remeasure | fixed DOS source walk |
| Strips + command | remeasure | HI08, current command geometry |
| Drain (buffered) | remeasure | per-word poll |
| Fill (rebuilt) | remeasure | bus-bound; merging reduces |
| Background+console+HUD+game | remeasure | current bounded passes |

Pipelined (stage B): frame ≈ max(march, CPU total) + drain, to be measured
with the fixed source geometry and quantised by VBL.

Targets, unchanged in spirit from PORTING.md but now attached to phases:
**15 FPS floor** after phase 3; every figure re-taken on real hardware before
it is quoted as a target for the fixed source geometry.

## 13. Order of work

1. Phase 0 defect list, far tile, strips, parity build, first-light diff.
2. Phase 1 measurement sweep (including one hardware run).
3. Phase 2 transport/fill rebuild + ybuffer seeding + early-out.
4. Phase 3 stage A overlap; then stage B behind a switch.
5. Phase 4 inner-loop rewrite against the profiler.
6. Phase 5 frustum placement, then the mid tile.
7. Phases 6/7 strictly by measurement.

The kill criteria from PORTING.md stay in force at every step: if a measured
number invalidates the shape — SRAM smaller than believed, HI08 slower than
believed, fill costs dominating regardless — the answer is a smaller world,
a shorter view, or the CPU renderer, not a cleverer kernel.
