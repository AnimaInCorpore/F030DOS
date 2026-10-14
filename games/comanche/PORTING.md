# Porting the VoxelSpace renderer to the Falcon030 DSP

This document turns the DSP56001 proposal for F030Comanche into an
implementation and bring-up plan. It describes the intended architecture,
but it does not treat the expected frame rate as proven until the kernel has
been benchmarked on the target Falcon hardware.

This is a subordinate performance workstream. The governing project roadmap
is [docs/PORTING-PLAN.md](docs/PORTING-PLAN.md): DOS behaviour recovery, the
x86-to-68030 traceability map, and a CPU-correct playable mission take priority.
Do not advance this DSP path when doing so displaces a missing behavioural
contract or CPU parity gate. Resume it after profiling identifies terrain
ray-marching as the relevant bottleneck in the correct CPU implementation.

**Current-boundary note, 2026-08-18.** The active renderer is the recovered DOS
terrain walk over the installed D/C assets and HIGH/MEDIUM/LOW `.DTL` tables;
the active flight path is the recovered mission/replay integration. The old
VoxelSpace reference, generated maps/palettes, pinned-camera measurements and
`TERRAIN_HALF`/`BENCH_*` switches are historical material below, not runtime
sources or behavior choices. Only `USE_DSP` and `PARITY_TILE` remain build
options, and an unrecovered mechanic is stopped or dormant rather than guessed.

## Scope and current baseline

The active program now contains a small CPU-only flight slice around the
68030/TOS scaffold. It proves the following pieces:

- Falcon startup and restoration of the previous TOS video state;
- a 320x240 16-bit working/display buffer pair;
- VBL-driven VIDEL buffer publication;
- an IKBD make/break scan-code handler with a VBL-stable input snapshot;
- a y-buffer voxel terrain pass over the **full 1024x1024** original map, in
  16.16 fixed point, with a per-column occlusion row and an early-out;
- a flight test: continuous forward motion, turn, climb/dive, map wrapping,
  and terrain following;
- a GEMDOS runtime decoder loading the original D1/C1 maps at full resolution,
  plus build-time generation of the palette and renderer lookup tables;
- assembly, linking, Hatari execution, and framebuffer capture.

The renderer port should be developed in layers. First reproduce the reference
VoxelSpace image on the 68030, then move only the height-field hot path to the
DSP, and retain 68030 composition because the DSP has no direct Falcon-RAM or
VIDEL-framebuffer path. This gives every DSP optimization a pixel-correct
reference and makes failures in fixed-point arithmetic distinguishable from
failures in the host protocol.

The reference renderer is deliberately built with the structure the DSP kernel
is planned to use, so that the two can be diffed rather than merely compared:
one ray per surface pixel in the current 320-ray quality path, a near-to-far
march, and vertical spans. The earlier 160-ray path remains the performance
baseline. The renderer differs from the eventual DSP only in doing the
arithmetic on the 68030.

A few tuning facts are worth recording, because each of them produced an image
that looked like a renderer fault and was not one:

- **Relief scales with the projection scale, not with altitude.** The row
  difference between two samples at the same distance is
  `(h2 - h1) * PROJ_SCALE / z`, in which camera height does not appear.
  Climbing or descending changes where the terrain sits on screen, never how
  much relief it shows.
- **The centre of the map is a plain.** Heights around (512,512) run 0-56
  against a global maximum of 187. A correct render there looks flat. The
  flight starts near (64,160), which the height field's local standard
  deviation identifies as broken terrain.
- **Flight speed interacts with when a frame is captured.** At a quarter of a
  map unit per frame the camera had left the interesting terrain long before
  the capture VBL.
- **The sine table cannot steer the fan per column.** Ray angles quantized to
  the table's 1/256-turn grid give only 64 distinct directions across a
  90-degree fan, so a 320-column frame rendered as 64 unique columns five
  pixels wide - visible as heavy vertical striping that looked like a
  resolution fault. The renderer now interpolates each column's ray step
  between the fan's two edge vectors, as VoxelSpace does, reading the sine
  table twice per frame for the camera basis only. That also makes the
  projection planar rather than cylindrical, and it is the same basis the
  DSP command block already carries in `CMD_W_DIR_*`/`CMD_W_RIGHT_*`.
- **The VoxelSpace reference supplies useful shape conventions, not exact
  Comanche tuning.** The active renderer now uses its roughly 90-degree fan,
  direct C1 colour classes without synthetic height ramps, and a dense-near /
  coarse-far depth schedule. The projection scale is currently 48 as a flatter
  starting point; the original palette and exact runtime constants remain to
  be decoded.

## Initial implementation scope

The first playable Falcon milestone is intentionally local and visual. It
includes graphics, input, game state, missions, local resource loading, HUD,
and frame presentation. It explicitly omits sound, music, networking, and
network-facing services. Sound assets may remain in the inventory for later
work, but the initial build and runtime must not depend on them.

## Original binary sizing and runtime boundary

The supplied DOS installation is 7,037,871 bytes across 92 files, but the
installed non-executable assets account for 6,973,927 bytes. The main
`COMANCHE.EXE` is 61,154 bytes on disk because it is LZEXE 0.91-packed; after
unpacking, its load image is 386,823 bytes. That figure is not the size of the
program: 173,287 bytes of it are the linker's zero-filled BSS and 5,888 bytes
are the real-mode bootstrap, leaving a **207,648-byte 32-bit flat program** at
image offset `0x1700`. That is the porting denominator, and it is still an
upper bound on code because it also holds tables, strings, and alignment.

The executable enters a custom 386 protected-mode/DOS-extender path, but only
the first 5,888 bytes are segmented. The game proper runs in one 32-bit code
segment and one 32-bit data segment that share a base, with no far pointers
and no segment relocations. Its pointer model therefore maps onto a flat
68030 address space directly; what has to be replaced is the extender's
memory and mode management, not a segmented ABI. The external resource files
remain the bulk of the initial porting work: their object and mission formats,
streaming behaviour, and memory footprint must be mapped before deciding what
belongs in Falcon RAM, DSP memory, or streamed storage. The first terrain test
now loads the local original `D1.DTA`/`C1.DTA` pair at runtime through GEMDOS
and falls back deterministically when the files are absent or invalid.
`tools/prepare-original-test.py` generates the palette and lookup tables used
by the current renderer, from that same pair.

It did not always. The generator preferred the VoxelSpace `D25.png`/`C28W.png`
reference pair whenever those files happened to be present locally, while
`src/resources.s` always loaded `D1.DTA`/`C1.DTA`, so the build indexed
Comanche's colour bytes through VoxelSpace's palette and nothing in the build
output said so. Asset selection is now explicit, defaults to the original pair,
is recorded in the generated tables as `ORIGINAL_ASSET_SOURCE`, and
`tools/build-run.sh` fails the build if the staged runtime maps and the
generated palette do not come from the same family. Mission, object, sound, and network formats are
still deliberately deferred. See
[docs/ASSET-INVENTORY.md](docs/ASSET-INVENTORY.md) and
[docs/RE-WORKFLOW.md](docs/RE-WORKFLOW.md).

## Target frame architecture

The proposed division of work is:

| 68030 | DSP56001 |
|---|---|
| Input, game state, camera movement, resource loading | Heightmap sampling and ray marching |
| Camera state and command submission | Fixed-point coordinate stepping |
| HUD, objects, menus, and non-terrain drawing | VoxelSpace `ybuffer` occlusion test |
| VIDEL setup, VBL, and final buffer presentation | Terrain pixels or compact vertical-span output |

The frame should be a producer/consumer exchange rather than a stream of
individual pixels:

```text
68030 game update
        |
        v
compact frame command -> DSP ray marcher -> back-buffer pixels/spans
                                                |
                                                v
                              68030 composition -> VIDEL flip at VBL
```

Never send a pixel at a time through the host interface. Batch every frame's
traffic into one transfer block in each direction.

## Strategy: what the DSP is actually for

The sections below establish the constraints; this is the conclusion they add
up to, stated once so the rest of the document has something to serve.

**The DSP's value here is not that it is a fast coprocessor. It is that it is
the only place in the machine where map accesses are free.** A 68030-side
renderer would issue roughly 38,400 map fetches per frame across the same
16-bit bus it needs for framebuffer writes, and those two demands would
contend for every cycle. The DSP has private SRAM, so its inner-loop memory
traffic costs the rest of the machine nothing. That is the whole argument for
using it, and it is a memory argument rather than an arithmetic one.

The corollary sets the boundary: the DSP sits on the far side of a narrow
pipe, so **work belongs on the DSP only when moving it there reduces what has
to cross.** Ray marching qualifies — 38,400 map samples collapse into about a
thousand span records. Anything that would increase the volume crossing HI08
does not qualify, however parallel it looks.

That yields five decisions:

1. **The DSP owns ray marching, occlusion, and span merging.** Merging and
   viewport clipping happen on the DSP because they are nearly free there and
   they shrink the expensive side. The 68030 should never receive a span it
   will not draw.
2. **Keep both ray-count modes available.** The current best-quality
   experiment renders 320 terrain columns, one per 16-bit surface pixel, so
   it removes the visible two-pixel horizontal striping of the earlier path.
   The 160-ray path remains the performance baseline: it doubles each ray
   horizontally and uses one `move.l` for the two adjacent pixels. The quality
   path doubles the ray march and uses one word store per surface pixel; its
   frame-time cost must be measured before it becomes the default runtime mode.
3. **Target the original's low detail level, and treat that as fidelity
   rather than compromise.** `LOW.DTL`, `MEDIUM.DTL` and `HIGH.DTL` open with
   100, 180 and 250, which read as view distances in map units. A 100-120
   sample depth is the original game's own low setting, not a Falcon-specific
   concession.
4. **Map in over SSI/DMA, spans out over HI08.** The bulk, one-directional,
   latency-tolerant traffic goes on the free path; the small, synchronous,
   per-frame traffic goes on the path that costs about a millisecond.
5. **Pipeline or it does not fit.** The DSP renders frame N+1 while the 68030
   composites frame N. Serialised, the two stages exceed the frame budget.

Keep the 68030 reference renderer working throughout, not as a fallback but as
the correctness oracle every DSP change is diffed against.

### When to abandon this shape

The strategy rests on measurements that have not been taken. State the kill
criteria now, while they are cheap to state:

- If DSP SRAM is materially smaller than 16 KWords of X, the tile drops to the
  next power of two down — 64x64, not something in between — which halves the
  view distance to roughly 45-64 units and puts the whole approach in doubt.
- If the SSI clock cannot be DSP-mastered and the rate falls back to the audio
  range, tile streaming stops being free and tile residency returns as a
  frame-time risk.
- If a measured vertical span fill is far worse than the page-miss estimate,
  the bottleneck is composition rather than ray marching, and halving the
  column count again will buy more than any DSP optimization.

In any of those cases the honest answer is a smaller world, a shorter view
distance, or a 68030-only renderer — not a more clever kernel.

## The DSP has no path to Falcon RAM

This section replaces an earlier assumption that shared Falcon RAM was
available to both processors and merely needed benchmarking. On the Falcon030
the DSP56001 is not a bus master. It reaches the rest of the machine only
through the HI08 host port at `$FFFFA200`-`$FFFFA207` and through the SSI.
There is no shared command buffer, no shared span queue, and no DSP write path
to the VIDEL framebuffer.

Three parts of the earlier plan depended on that assumption and do not
survive it:

- the memory-layout row placing the frame command and span queue in shared
  Falcon RAM;
- the "direct surface" output backend, described as the best target;
- the frame budget, which costed the ray march but not the transport.

The corrected shape is that **HI08 is the only transport**, so every byte the
DSP consumes or produces is a host-port word, and the map cannot simply be
pointed at. Two consequences drive the rest of this document: output must be
compact enough to push through the port, and the map must be resident in DSP
memory, which bounds how much terrain the kernel can see at once.

The transport itself is affordable if the output stays compact. A rectangle
record is two 24-bit words — a precomputed framebuffer offset, then width,
height and colour — as set out under [Commit output](#4-commit-output). At 320
terrain columns and a few runs per column, a frame is still on the order of a
thousand words, which is a small part of a 50 ms budget at 20 FPS. Measure it
before relying on it, but the arithmetic is not marginal — the map residency
question below is.

### The SSI/DMA path is real, but not a drawing accelerator

The DSP's second connection to the machine is its SSI, wired to the Falcon's
programmable sound connection matrix. That matrix documents two routings which
move data between DSP and ST-RAM with no 68030 involvement at all:

- **DSP transmit to DMA record** — the DSP's SSI output is written into an
  ST-RAM buffer by the audio DMA controller.
- **DMA playback to DSP receive** — an ST-RAM buffer is streamed into the DSP.

**Do not size this path from the audio sample-rate table.** The familiar
49,170 Hz ceiling is a property of the CODEC, and a `DSP <-> DMA` routing never
touches the CODEC. The real limit is the SSI bit clock. On the DSP56001 the
serial clock is `Fosc / (4 * (7*PSR+1) * (PM+1))`, so with the prescalers at
minimum a 32 MHz part gives an 8 MHz bit clock. At 16 bits per word that is
500,000 words per second, or **about 1 MB/s** — roughly five times what the
audio-rate figure suggests. Sixteen bits per slot also happens to carry the
packed height/colour pair exactly, with none of the padding a 24-bit word
would need.

Even so, it is not a way to draw. Pointing the DMA record buffer at the
framebuffer and letting the DSP write the screen still fails on rate: a
320x240 16-bit surface is 153,600 bytes, so a full frame takes about 154 ms,
or 6.5 FPS. More fundamentally, the audio DMA is a linear write into one
buffer at a fixed cadence — it cannot scatter pixels, cannot stride down a
column, and cannot be told to fill a range. It is a pipe, not a blitter, and
the expensive part of composition is precisely the strided scatter.

Nor does it help the span queue, because the span queue is not the problem.
About a thousand 24-bit words per frame costs the 68030 roughly a millisecond
of host-port reads, against the tens of milliseconds it spends writing pixels.
Moving that millisecond onto the DMA would be optimizing the wrong term.

**Where the path earns its place is the other direction: tile streaming.**
`DMA playback -> DSP receive` pushes map data into the DSP continuously, in the
background, at zero CPU cost. At 1 MB/s the frame budget at 20 FPS is 25,000
map samples — about **1.5 full 128x128 tiles per frame**, and a single
128-sample edge strip costs 0.26 ms. That does not merely smooth the reload
spike; it makes tile residency a much softer constraint than the X-memory
table implies, because the resident window can be replaced far faster than the
camera can invalidate it. A rolling window updated aggressively becomes
realistic, and the earlier framing of tile reload as a worst-case frame cost
should be revisited once the rate is confirmed on hardware.

Before relying on it, establish:

1. The exact matrix programming for both routings, and which side is SSI clock
   master. The 1 MB/s figure assumes the DSP drives the clock at `Fosc/4` and
   that the crossbar and DMA controller will slave to it; if the crossbar
   insists on its own internal divider, the rate falls back towards the
   audio-clock range. This is the single measurement the whole tile-streaming
   argument rests on. The repository has the DSP-side SSI equates in
   `src/dsp/ioequ.inc` but no Falcon-side matrix code; this is new ground here.
2. How the DMA's circular buffer and current-pointer registers are polled to
   know how much has actually arrived, since there is no completion signal.
3. That the DSP can service SSI receive interrupts without disturbing the
   ray-march loop's timing — an interrupt in the middle of a hardware `DO`
   loop is exactly the case the loop-rules section warns about.
4. Whether occupying the record or playback path conflicts with the later
   sound milestone. Sound is deferred, so this is not a blocker now, but it
   should be a known cost rather than a surprise.

## Stock machine profile

Every budget in this document is against the stock Falcon030, not an upgraded
one:

| Part | Stock figure | Consequence for this port |
|---|---|---|
| CPU | 68030 at 16 MHz | The composition side is not fast. Treat 68030 work as a budget line, not as free. |
| FPU | None fitted | Irrelevant here; everything is fixed-point anyway. |
| Memory bus | 16 bits wide | The defining bottleneck. A 32-bit CPU behind a 16-bit bus means every `move.l` to RAM is two bus cycles. |
| RAM | ST-RAM only, 1/4/14 MB | No Fast-RAM without a third-party expansion. Do not plan around it. |
| Video | VIDEL, shares ST-RAM with the CPU | True-colour video DMA steals a substantial share of the bus during active display. |
| Blitter | Present | The obvious candidate for span fills; see the stride note below. |
| DSP | DSP56001 at 32 MHz, ~16 MIPS | The figure the ray-march budget uses. |
| DSP RAM | 32 KWords of 24-bit external SRAM | Commonly documented as X and Y of 16 KWords each, plus the 56001's on-chip 512-word P and 256-word X/Y. Verify the split before sizing the tile — it is what decides the tile. |

Two consequences deserve to be stated in numbers rather than left implicit.

**Surface writes are expensive.** A 320x240 16-bit surface is 153,600 bytes.
On a 16-bit bus at 16 MHz, a bus cycle of two clocks gives a ceiling of about
16 MB/s, so writing that surface once is roughly 9.6 ms *at the theoretical
peak, with no wait states and no video contention*. Real ST-RAM with VIDEL
active in a true-colour mode will be materially worse. Against a 50 ms budget
at 20 FPS, and roughly 24 ms of DSP ray marching, the arithmetic only closes
if the 68030's composition of frame N overlaps the DSP's render of frame N+1.
The pipelining step is therefore mandatory, not an optimization to try later.

**Vertical spans fight the framebuffer layout.** A span is a vertical run, but
the surface is row-major with a 640-byte stride, so consecutive pixels of one
span are 640 bytes apart and defeat DRAM page mode entirely. This is the
single most likely reason for span expansion to come in far slower than a
byte-count estimate suggests. Measure a vertical fill before committing, and
if it is as bad as expected, evaluate in this order: the Blitter with a
configured stride; accumulating a column-major intermediate and transposing
once per frame; or emitting spans grouped so that several columns are advanced
together in one pass down the screen.

## Hardware assumptions to verify

The figures above are the planning profile, not a verified memory map. Before
committing the renderer to a particular layout, establish these facts on the
actual Falcon or the exact emulator configuration:

1. Which DSP X/Y addresses are internal, external, or mirrored, and how much
   external SRAM the target machine actually has.
2. The capacity, word width, wait states, and address increment behaviour of
   each memory upgrade.
3. Sustained HI08 throughput in words per frame, in both directions, with the
   handshake the kernel will really use, and how deeply the DSP56001's host
   data registers buffer — that depth bounds how far a request stream can be
   pipelined ahead.
4. The precise Host Interface/HI08 handshake and reset behaviour.
5. Whether the 68030 data cache must be disabled, flushed, or invalidated
   around the host-port transfer buffers.

Keep the output backend behind one interface, so that a future machine with a
different transport does not require reworking the kernel.

## Falcon precedent from the Chō Ren Sha port

The local `F030Arcade/third_party/chorensha` reference is useful for Falcon
platform boundaries, but not for Comanche data formats. Its Atari source
confirms several implementation rules that apply here:

- Allocate display surfaces from ST-RAM with GEMDOS `Malloc` mode 0, align the
  result before publishing it to VIDEL, and keep any SuperVidel aliasing behind
  machine detection. The current Comanche scaffold's static TPA surfaces are
  suitable for bring-up; the release allocator should move to this explicit
  ST-RAM path before Fast-RAM configurations are accepted.
- Save and restore the VBL and IKBD vectors, and consume keyboard make/break
  bytes in the IKBD interrupt. The Comanche input slice follows this pattern
  on real Falcon hardware; its Hatari bring-up also drains the non-blocking
  TOS console queue so focused host keys work when raw ACIA delivery is not
  enabled.
- Use two CPU-owned surfaces and publish only the completed display pointer at
  VBL. Chō Ren Sha's sprite path also keeps intermediate data in a buffer and
  lets the CPU expand it into the working surface. That is a useful precedent
  for Comanche's DSP span queue, but its sprite RLE restore-block protocol is
  not a Comanche resource decoder.
- The Falcon source uses explicit Host Interface polling: clear/raise host
  flags, wait on HSR data-empty/data-full bits, and transfer grouped records
  through the `$FFFFA204` host data register. This validates the command/status
  direction of the Comanche DSP plan; the Comanche command block still needs
  its own version, sequence, ownership, and timeout fields.
- Its proven RGB/TV mode is a 256x240, 50 Hz true-colour timing profile. The
  Comanche reference surface remains 320x240 because the current capture and
  mission-port plan use that width; do not copy the 256-pixel VIDEL constants
  without retesting the intended mode and line width.

The reference also detects `_MCH`, `_CPU`, `_VDO`, `SupV`, and `_SND` cookies
and probes Fast-RAM. Those checks belong in Comanche's platform layer before
hardware-specific optimizations, not in the mission or renderer code. Its
audio initialization is intentionally not part of the first Comanche loop.

## Memory layout

The DSP56001's Harvard architecture is useful because one X-memory and one
Y-memory operand can be moved in parallel. A practical first layout is:

| DSP space | Initial allocation | Notes |
|---|---|---|
| P-memory | Kernel and protocol constants | The 56001 has 512 words of internal program RAM. Budget the kernel against that before assuming external P. |
| X-memory | Resident map tile, one word per sample | Height and colour packed together; see below. |
| Y-memory | Decimated far tile, `ybuffer`, reciprocal table, camera basis, span buffers, scratch | Roughly 6,000 of 16,384 words. Load `ybuffer[x]` once per column so the inner loop does not need a second Y read. |
| Host port | Frame command in, rectangle records out | Two 24-bit words per record. No shared memory exists; see the transport section above. |

### Pack height and colour into one word

The proposal treated the parallel height/colour fetch as the intended fast
path:

```asm
; Pseudocode: one X and one Y operand in the same DSP move slot.
move    x:(height_ptr)+,a   y:(colour_ptr)+,b
```

Prefer packing the height and colour of a sample into a single 24-bit word
instead. The DSP is word-oriented with 24-bit data registers, so an 8-bit
height plus an 8-bit colour plus eight spare bits is exactly one word and one
fetch. That is not merely tidier:

- it halves map traffic and map residency, which is the binding constraint;
- one address generator advances instead of two, freeing a register and
  removing a second wrap calculation;
- it dissolves the "fetch colour eagerly or only after the occlusion test"
  question below, because there is no separate colour fetch to schedule;
- the free X or Y slot in the parallel move becomes available for the
  reciprocal-table read instead.

Keep the split-array form as the fallback if the spare byte turns out to be
needed for a precomputed value.

### The map does not fit, and that is the design constraint

Give the map an explicit word budget before choosing a tile size. Counted in
DSP words with height and colour packed one sample per word, against the
16 KWords of X memory the stock split is expected to provide:

| Map | Samples | DSP words | Share of a 16 KWord X | Verdict |
|---|---:|---:|---:|---|
| 1024x1024 full map | 1,048,576 | 1,048,576 | 6400% | Impossible by a wide margin |
| 512x512 | 262,144 | 262,144 | 1600% | Impossible |
| 256x256 | 65,536 | 65,536 | 400% | Still four times over |
| **128x128 tile** | **16,384** | **16,384** | **100%** | **Exactly fills X. This is the answer.** |
| 64x64 tile | 4,096 | 4,096 | 25% | Fits easily, but too short a view |

The general form, since the split is still unverified: with height and colour
packed one sample per word, samples equal words, so the largest tile is
`T = floor(sqrt(X_words))`, rounded **down to a power of two**. Halving X to
8 KWords does not give 90x90 — it gives 64x64, because the next power of two
down is the only size that keeps addressing cheap.

That rounding is the reason to take 128x128 rather than something with slack.
A power-of-two tile makes the address `(y << 7) + x` with a mask, which the
AGU does for free; 112x112 would need a multiply per sample in the innermost
loop. An earlier revision of this section recommended 112x112 to leave margin
for streaming — that was the wrong trade. Take the power of two, fill X
exactly, and put the streaming staging buffer in **Y**, which has roughly
14 KWords free once the `ybuffer`, reciprocal table, camera basis, and span
buffers are placed. Stage an incoming tile or edge strip in Y, then commit it
into X between frames; a full 16,384-word commit is about a millisecond of DSP
time and an edge strip is negligible.

### Rejected: fetching map samples from the 68030 on demand

An obvious way to escape the tile limit is to leave the whole 1024x1024 map in
Falcon RAM and have the DSP ask for samples as it needs them: the DSP computes
an address, sends it over HI08, the 68030 gathers the height and colour and
sends them back. It removes tile residency, streaming, and the view-distance
ceiling in one move. It also does not work, and the reason is worth recording
because the idea recurs.

The 68030 side of that loop can be written very tightly — two instructions,
small enough to sit in the 256-byte instruction cache:

```asm
        move.l  $A204.w,d6          ; address offset from the DSP
        move.l  (a5,d6.l),$A204.w   ; gather packed height/colour, return it
```

The instruction count is not what defeats it. Count bus cycles instead: a
16-bit bus makes that three longword transactions, six bus cycles per sample.
At 160 columns and 120 depth samples that is 19,200 samples per frame, so
**14.4 ms of 68030 time with no wait states anywhere**, about 21.6 ms once the
DSP port is treated as the slower I/O device it is, and about 36 ms with the
handshake included — and the handshake is not optional, because reading `HRX`
when it is empty returns stale data and HI08 does not stall the 68030. Compare
0.9 ms to drain a rectangle list. Batching into 32-sample strips amortises the
polling but not the per-sample host write, and still lands near 18 ms.

**The deeper objection is latency, not throughput.** Every sample is a
synchronous round trip, so the DSP blocks waiting for the 68030 and the 68030
blocks waiting for the DSP, 19,200 times per frame. At a microsecond per round
trip that is 19 ms during which *neither* processor is doing useful work. The
design converts two processors running in parallel into two processors taking
turns, and once that happens their individual speeds stop mattering — the
frame rate is set by the round-trip time alone.

Two structural problems sit underneath the arithmetic:

- **A ray is not memory-coherent.** It steps diagonally through the map at a
  fractional slope, so consecutive samples are not consecutive in RAM. The
  68030 cannot service a request with a fast linear copy or the Blitter; it is
  a scattered gather with computed addresses, which is the expensive kind.
- **Demand fetching is a cache with no reuse.** A resident tile is also a
  cache of Falcon RAM, but one that is reused: 16,384 samples loaded once and
  hit by 19,200 ray samples per frame, for many frames. Held 30 frames it
  fetches 546 samples per frame at a reuse factor of 35. Demand fetching has a
  reuse factor of exactly 1, so it moves an order of magnitude more data, on
  the expensive path instead of the free one.

The general rule this illustrates: bulk prefetch on the DMA path beats demand
fetch on the host path, and any demand-fetch scheme that tries to become
efficient converges on caching a region — which is a tile.

Request/response between the two processors is not the problem in itself; its
*granularity* is. The same handshake once per frame costs nothing and is worth
having — the DSP announcing "I am about to leave tile (3,7)" so the 68030 can
start a DMA is exactly the right use of the host port. Per sample it is fatal;
per tile it is free.

#### Interleaving fixes the latency but not the throughput

The blocking version above can be pipelined, and should be if it is ever
built: because the address stream is data-independent, the DSP can issue the
request for sample `N+1` before looking at sample `N`, so neither processor
waits on the other. That removes the whole 19 ms of mutual stalling and is a
large improvement.

It does not remove the 68030's work. Six bus cycles per sample still have to be
executed 19,200 times, so the CPU cost falls from about 36 ms to about 29 ms —
21.6 ms of bus traffic plus the poll that now falls through immediately rather
than spinning. With composition on top:

| Design | CPU per frame | + composition | Ceiling | Headroom in a 50 ms frame |
|---|---:|---:|---:|---:|
| Interleaved demand fetch | 28.8 ms | 47.8 ms | 20.9 FPS | 2.2 ms |
| Resident tile, drain rectangles | 0.9 ms | 19.9 ms | 50.3 FPS | 30.1 ms |

Two milliseconds of headroom is not a frame budget; game state, HUD, input,
and mission logic have to come from somewhere. So interleaving does not make
demand fetching the primary design — it makes it a **viable contingency**, and
that is worth recording, because the kill criteria above include a DSP SRAM
figure that has not been measured. If X memory turns out too small to hold a
useful tile, an interleaved demand-fetch renderer is a real fallback rather
than a dead end.

The better contingency is a hybrid: keep the near tile resident and demand-fetch
only the far field. At eight-unit steps the far march is 24 samples per column,
or 3,840 per frame, which is **5.8 ms of 68030 time** — affordable. That keeps
full-resolution near terrain in X and buys unlimited view distance for the cost
of a few milliseconds, and it is the shape to reach for if the far tile will
not fit in Y.

### The view distance problem, solved with two levels of detail

The tile limit is a real problem and worth solving properly rather than
accepting. The answer is not more memory but less resolution where it cannot
be seen: distant terrain occupies few pixels, so storing it at full detail
wastes the scarcest resource in the machine.

Keep a full-resolution near tile in X and a decimated far tile in Y:

| Level | Tile | Decimation | Words | Space | Reach |
|---|---|---:|---:|---|---:|
| Near | 128x128 | 1:1 | 16,384 | X, exactly full | ±64 units |
| Far | 64x64 | 8:1 | 4,096 | Y, alongside working data | ±256 units |

Y has room: the far tile, a 320-entry `ybuffer`, a reciprocal table, span
buffers and scratch still fit comfortably within the 16,384-word budget.

The depth loop splits at the near/far boundary into two hardware `DO` loops —
64 steps of one unit through the near tile, then 24 steps of eight units
through the far tile. That is **one branch per column, not per sample**, and
the coarser far steps mean fewer samples overall:

- 88 samples per column instead of 120, so about **8.8 ms of ray march**
  instead of 12.0 ms;
- **256 units of view distance** instead of 90-128, which exceeds the
  original's `HIGH.DTL` value of 250.

Longer view, fewer samples, 4,096 extra words. Both figures need confirming
against a rendered image rather than a spreadsheet — the near/far seam is the
thing to inspect, and the far tile's decimation filter matters, since averaging
an 8x8 block flattens ridge lines that a maximum would preserve. Try both and
compare against the 68030 reference.

### 128x128 is barely enough on its own

A tile does not give its full width as view distance. Centred on the camera, a
128x128 tile reaches only 64 units in every direction — half the depth range
this document has been assuming. An earlier revision claimed a 128x128 tile
"only just contains" a 120-unit view; that was wrong, and the correction
matters because it is what forces the tile to track the frustum rather than
the camera.

Placed around the view frustum instead of centred on the camera, the same tile
gives up to 128 units straight ahead and about 90 on the diagonal. That is the
honest figure for a single-level tile: **roughly 90-128 units depending on
heading**, which brackets the original's `LOW.DTL` value of 100 and sits below
its `MEDIUM.DTL` of 180. The two-level scheme above is what lifts it past
`HIGH.DTL`; the rest of this section applies to the near tile.

For scale, the frustum itself is not the problem — a 120-deep, 60-degree view
is only about 8,300 samples as a triangle. It is the axis-aligned bounding box
of that triangle when the camera faces a diagonal, about 183x183 or 33,000
samples, that will not fit. Two options follow, and they should be measured
rather than assumed:

1. Accept the heading-dependent view distance and let the far clip pull in
   when the camera faces a tile diagonal. Cheap, but the horizon visibly
   breathes as the player turns.
2. Re-place the tile on heading change as well as on movement. At the SSI rate
   a full tile refill is under one frame, so this is affordable — it is the
   payoff for the streaming path, and the reason that path is worth building
   before the tile policy is finalised.

`D1.DTA`/`C1.DTA` decode to a 1024x1024 pair, so the full map is three orders
of magnitude beyond what the DSP can hold, and it cannot be pointed at in
Falcon RAM either. The earlier advice to "start with a 256x256 or 512x512
packed map" is not achievable on a stock machine; `tools/prepare-original-test.py`
emits a 256x256 tile, which is correct for the CPU reference renderer but is
not a DSP-resident asset.

The kernel must therefore work on a resident tile around the camera, and tile
residency becomes a first-class part of the design rather than an
optimization:

1. Confirm the installed DSP SRAM size first — the tile budget follows from it
   and nothing above should be treated as settled until it is measured.
2. Decide what happens at the tile edge: clamp, repeat, or reload. Ray marching
   to maximum depth will leave the tile.
3. Cost the reload, but try the SSI/DMA route first. Streaming a tile through
   HI08 competes with span output in the same frame and costs 68030 time,
   whereas `DMA playback -> DSP receive` runs in the background at no CPU cost
   and, at the rate derived above, can replace the resident window faster than
   the camera invalidates it. If that rate holds on hardware, tile residency
   stops being a frame-time risk and becomes a memory-size question only.
4. Consider a two-resolution scheme — full detail near, decimated far — before
   accepting a short view distance. This is the natural place to spend the
   spare byte in the packed word.

If the tile economics do not work out, the honest fallback is a smaller world
or a 68030-side renderer, not a larger assumed memory.

Power-of-two dimensions are useful, but hardware modulo needs care. A single
linear modulo buffer does not automatically implement independent two-
dimensional X and Y wrapping for a row-major map. Begin with explicit masked
coordinates and row-base calculation; replace this with AGU modulo addressing
only after the address sequence has been proven and benchmarked.

## Host protocol

Use a small, versioned command block, sent as a fixed sequence of 24-bit words
through the host port. The exact packing should be defined in a shared include
file used by both sides, and the first version should carry at least:

- protocol version and frame sequence number;
- player X/Y position and camera height;
- heading, pitch, horizon, and projection scale;
- resident tile origin, and whether a tile upload follows this command;
- maximum depth and ray step;
- viewport width/height and output mode;
- command flags and a completion/status value.

Keep the word count fixed and the field order stable, so both sides can drive
the transfer from a `DO` loop and a counted `move` rather than from a parser.
A variable-length command over a port with no framing is a resynchronization
problem waiting to happen; put variable-length data, such as a tile upload,
after the fixed block and give its length a field inside that block.

Recommended ownership rules, with the host port as the only channel:

1. The 68030 waits for the DSP to signal that the previous frame is complete
   and its command registers are free.
2. It writes the fixed command words, then the ready flag last.
3. The DSP drains the whole command block into local memory before starting
   the hot loop, so a late host write cannot change a live parameter.
4. The DSP finishes all span stores, then publishes the span count and
   completion status.
5. The 68030 reads the span count, drains that many words, expands them into
   the back buffer, and flips at VBL.

The DSP can hold two output buffers locally and fill one while the host drains
the other, which is where the pipelining lives now that there is no shared
memory to double-buffer. Add a timeout and a DSP reset/error path on the host
side; a dead or desynchronized DSP must not leave the Falcon with interrupts
disabled, a permanently hidden screen, or a half-drained port.

## Fixed-point representation

The DSP has no FPU. Keep normalized quantities and world coordinates in formats
that match their ranges instead of forcing every value into 1.23 fractional
format.

| Quantity | Suggested first format | Reason |
|---|---|---|
| Sine/cosine and normalized ray vectors | signed 1.23 | Full precision for values in approximately `[-1, 1)`. |
| World/map X and Y | signed 11.13, or tile-local 8.16 | See the range note below. |
| Height and camera height | signed 8.16 or widened integer | Avoid overflow when subtracting terrain and camera heights. |
| Depth | positive integer or unsigned fixed-point | Simple monotonic stepping and cheap table indexing. |
| Reciprocal `1/z` | LUT in a documented fractional format | Removes division from the inner loop. |
| Screen coordinates and `ybuffer` | integer pixels | Comparisons and stores are pixel operations. |

An earlier revision of this table proposed signed 8.16 for world coordinates.
In a 24-bit register that gives an integer range of `[-128, +128)`, which
cannot address the 1024x1024 map the `D1.DTA` family decodes to; a ray would
wrap or saturate long before reaching the map edge. Either widen to 11.13,
which covers `[-1024, +1024)` with 13 fractional bits, or keep world
coordinates tile-local and carry the tile origin separately — which is the
better fit given that the map is tile-resident anyway. Whichever is chosen,
state it in the shared include and test a ray that crosses the extreme.

The formats are starting points, not an ABI. Document every shift at the
boundary and add saturation/overflow tests. In particular:

- arithmetic shifts of negative coordinates must have defined map-floor
  behaviour;
- a 24-bit product may need a 56-bit accumulator before scaling back;
- projection constants must be widened before multiplication;
- map coordinates must be masked or clamped before forming an address;
- pitch and horizon must not allow a projected span outside the viewport to
  corrupt the command or framebuffer buffer.

Precompute a reciprocal table for the depth range and, where useful, per-column
ray increments. The 68030 can submit camera sin/cos, while the DSP can derive
the column rays from a compact camera basis. Avoid calculating a general sine
or a division for every ray-march step.

## DSP kernel pipeline

Implement the kernel in the following order:

### 1. Prepare one frame

Load the command block, clear the `ybuffer`, select the map/tile, and prepare
the camera basis. The current quality path has one `ybuffer` entry per
surface pixel: 320 entries for a 320-pixel surface. Keep both the terrain
column count and the surface width configurable and independent; the legacy
160-ray path deliberately uses one entry for two horizontal pixels.

### 2. Prepare one column

Initialize the ray position from the player position, compute the per-column
step vector, and load that column's occlusion value into a register. Do not
read and write `ybuffer[x]` on every depth iteration.

### 3. March the ray

For each depth step:

1. Convert the fixed-point ray position to tile indices.
2. Form the packed map address.
3. Fetch the packed height/colour word, freeing the other bus for the
   reciprocal-table read in the same move slot.
4. Advance the ray position with fixed-point adds.
5. Project the terrain height using the reciprocal-depth value.
6. If the projected row is visible above the current occlusion value, record a
   vertical span and update the local occlusion value.

Use a single hardware `DO` loop for the depth loop only after the instruction
sequence and loop restrictions of the selected DSP assembler have been tested.
Do not depend on nested zero-overhead loops until the DSP56001 documentation
and generated listing prove that the nesting is valid and fast.

### 4. Commit output

There is one backend, because HI08 is the only transport: the DSP emits span
records into a local output buffer, and the 68030 reads that buffer through
the host port and expands the records into the back buffer, retaining
ownership of VIDEL and the other screen layers.

Emit **rectangles carrying a precomputed framebuffer offset**, two 24-bit words
each:

| Word | Fields | Notes |
|---|---|---|
| 1 | `fb_offset:24` | Byte offset into the back buffer. A 320x240 16-bit surface is 153,600 bytes, so 24 bits is ample. |
| 2 | `width:8`, `height:8`, `colour:8` | Width in pixels, height in rows, colour or palette index. |

The 68030 side is then a fill loop with no address arithmetic at all — it adds
the line stride and stores, `height` times, `width/2` longwords per row:

```asm
        move.l  $A204.w,d2          ; fb_offset
        move.l  $A204.w,d3          ; width:height:colour
        ; ...expand colour into d4, then store d4 down the column
```

This replaces an earlier single-word `{top:8, bottom:8, colour:8}` format with
the column implicit in emission order. The change costs one extra word per
record — a few hundred words per frame, well under a millisecond — and buys
three things:

- **No per-span address calculation on the 68030.** Deriving `y*640 + x*2` cost
  roughly a millisecond per frame of shifts and adds on the side of the machine
  that can least afford it. The DSP forms the offset while it already has the
  coordinates in registers.
- **The horizontal doubling becomes data, not code.** `width` is simply 2 under
  the 160-column scheme, and the fill loop does not special-case it.
- **Horizontally adjacent runs can merge.** Where neighbouring columns share a
  colour and vertical extent, the DSP emits one wider rectangle and the 68030
  writes more bytes per store. Merging is nearly free on the DSP and strictly
  reduces work on the 68030.

Keep a reserved sentinel word to end the list, and keep `colour` at eight bits
by sending a palette index if the chosen VIDEL mode needs more — expand it
during composition rather than widening the record.

An earlier revision listed a "direct surface" backend in which the DSP writes
the back buffer itself, and called it the best target. It is not available on
this hardware at all; see the transport section.

## Cycle-optimized inner-loop guidance

The expanded inner-loop draft supplied with this project is a useful scheduling
template. Its strongest ideas are:

- keep ray position and per-column step values in registers;
- overlap the two ray-coordinate adds with a reciprocal-table read;
- use both memory buses in the same move slot — with a packed map word that
  means the map fetch on one bus and the reciprocal-table read on the other;
- keep the current occlusion row in a register rather than loading
  `ybuffer[x]` for every depth sample;
- make span emission a cold path and keep the depth loop branch-light.

The draft should not be copied verbatim into `src/dsp/comanche.asm`. It is
cycle-level pseudocode until it assembles, the generated listing is inspected,
and the arithmetic is compared against the scalar renderer. In particular:

### Software-pipeline the depth loop

The single most useful structural property of this kernel is that **the address
stream is data-independent**. The ray position is an accumulation of `dx`/`dy`
that owes nothing to the samples coming back, so the address for depth step
`N+1` can be formed before the sample at step `N` has been looked at. Nothing
in the fetch path has to wait on the arithmetic path.

Schedule the loop accordingly: issue the map fetch for `N+1` while projecting
and occlusion-testing `N`. One iteration of prologue and epilogue buys a loop
body in which the memory access and the arithmetic overlap instead of
alternating. This matters more than the instruction count, because map wait
states are listed as unmeasured — and a pipelined loop absorbs them, while a
sequential one exposes every one of them.

Two constraints bound how far to take it:

- **Prefetch depth trades against the `ybuffer` early-out.** A column that
  becomes fully occluded should stop marching, but samples already requested
  past that point are wasted. At depth one or two the waste is negligible;
  a deep prefetch pipeline can throw away a noticeable fraction of the fetches
  it issues on terrain with near occluders.
- **Do not let the prologue and epilogue break the hardware `DO` loop.** The
  loop-rules section applies: confirm in the listing that the pipelined body
  still satisfies the DSP56001's restrictions before assuming the schedule.

### Protect live values

`A` and `B` are DSP accumulators, not ordinary 24-bit variables. If they hold
the complete ray coordinates, a parallel map fetch must not overwrite one of
them with the map sample and then attempt to restore it from only an integer
field. Preserve the complete coordinate, or deliberately keep the integer and
fractional parts in separate documented registers. The same rule applies to
`X1`/`Y1`: a height sample, camera height, reciprocal, and colour value cannot
all occupy the same temporary at once.

A workable starting allocation is:

| Resource | Suggested lifetime |
|---|---|
| `A` / `B` | Full ray X/Y positions, or projection accumulators after the ray positions have been copied to scratch |
| `X0` / `Y0` | Current-column `dx` / `dy` increments |
| `X1` / `Y1` | Packed map sample and the current reciprocal value |
| `R0` | Map address generator, subject to the actual tile-address calculation |
| `R1` | Span output pointer |
| `R2` | Reciprocal-depth table or another per-step table |
| One accumulator/register | Current `ybuffer`/occlusion row for the column |

This is a starting point, not an ABI. The final allocation should be driven by
the assembler's parallel-move constraints and by the values that must survive
the projection and span paths.

### Schedule one read per bus

The DSP can issue one X-memory and one Y-memory data move in a parallel move,
but this does not provide two independent reads of the same memory space in
one slot. With the packed map word there is one map read per depth step, which
leaves the other bus for the reciprocal-table read and makes the depth loop's
memory schedule trivial. Load `ybuffer[x]` once when entering the column, and
keep the span store off the hot path.

An earlier revision proposed benchmarking eager against deferred colour
fetching. Packing removes that choice. If the split-array layout is ever
reinstated, the trade-off returns: deferring the colour fetch until a sample
passes the occlusion test wins on sparse terrain, while fetching both together
wins when memory latency dominates and the colour rides the otherwise-idle
bus. Do not assume the nominal one-cycle parallel move survives external wait
states either way.

### Form the real two-dimensional address

An expression such as `x:(r0+n0)` is only correct if `r0` already points at the
appropriate row and `n0` is the intended signed element offset. For a
row-major tile the address normally contains both coordinates, for example
`row_base(map_y) + map_x`. A modulo value such as `$03FF` can wrap a 1024-word
linear region, but it does not by itself implement independent X/Y wrapping of
a two-dimensional tile. Keep the explicit row-base/mask version as the
reference and introduce AGU modulo only after its address trace matches that
reference.

Tile wrapping is also a game/format decision, and it is the point where the
resident-tile constraint becomes visible in the rendered image. Repeating the
tile, clamping at its edge, and reloading a new tile produce three different
worlds; AGU wrap must not silently turn an out-of-range coordinate into an
infinite repeating one. Decide this deliberately and record it, because it is
the difference between a bounded map, a visible seam, and a frame-time spike.

### Keep projection algebra separate from colour

The projection operation should be expressed and tested as one equation before
it is scheduled into parallel moves, for example:

```text
projected_y = horizon - (terrain_height - camera_height) * reciprocal_z + pitch
```

The supplied draft's sample instructions overwrite the height temporary and
subtract colour/height values in the wrong accumulator before the multiply. It
also overwrites live ray state and then restores only partial values. Treat
that sequence as a register-scheduling sketch, not as a correct implementation.
Keep a short scalar/fixed-point reference expression beside the assembly and
verify every shift and sign before collapsing operations into parallel moves.

### Keep the 9-11 cycle figure honest

The draft's approximately 9-11 cycles per depth step is a useful microbenchmark
target for a hidden, local-memory iteration. It is not a complete frame cost.
The following are outside that optimistic inner-loop figure and must be measured
separately:

- map and reciprocal-table wait states;
- map-coordinate address formation and wrap handling;
- conditional branches and loop termination;
- visible-sample projection and occlusion updates;
- span record stores;
- subroutine call/return overhead for `DrawVerticalSpan`;
- the HI08 transfer of the command block in and the span buffer out;
- tile reload traffic on the frames where the camera crosses a tile boundary;
- 68030 span expansion into the back buffer.

The last three are not inner-loop overheads at all — they are separate frame
costs that scale with output size and camera motion rather than with depth
iterations, and the ray march cannot be tuned to hide them.

Do not call a span-drawing subroutine from the nominal hot loop until its cost
is known. Prefer an inline short store, a compact span record, or a separate
cold path that is entered only when a sample becomes visible. Benchmark at
least a flat/hidden scene, an all-visible scene, maximum depth, and external
map memory.

### Validate hardware-loop and branch rules

Use one zero-overhead `DO` loop for the depth samples only after the selected
ASM56000 syntax and DSP56001 loop rules have been confirmed in the listing. The
loop-end label, iteration count, conditional skip path, and any call or return
inside the loop can affect both correctness and timing. Keep the outer column
loop explicit until the inner loop is stable; do not assume nested hardware
loops are free or even supported in the desired form.

## Rendering correctness

Keep a scalar reference renderer on the 68030 or on the development host. For
the same camera command, compare:

- map indices at selected depth steps;
- fixed-point ray positions;
- projected screen rows;
- `ybuffer` values after each column;
- emitted spans and their colours;
- final framebuffer output.

The `ybuffer` convention must be written down in code. A common convention is
to initialize each column to the bottom of the viewport, then accept a sample
only when it projects above the stored occlusion row, draw the interval between
the two rows, and move the stored row upward. The near/far traversal order and
the interval endpoints must match the reference implementation exactly or
holes and overdraw will appear even when the arithmetic is otherwise correct.

Validate map edges, negative coordinates, maximum depth, flat terrain, a single
peak, and a horizon-level camera before profiling textured terrain.

## Performance plan

The proposal's planning workload was 320 columns multiplied by roughly 120
depth samples, or about 38,400 inner-loop iterations per frame. At 10 cycles
per iteration and 16 MIPS that is 384,000 cycles, or roughly 24 ms of pure ray
marching — against a 50 ms budget at 20 FPS, with composition still to pay
for. The 160-ray path was selected as the initial performance baseline for
that reason; the 320-ray quality path is now implemented and must be measured
against it. Neither estimate is a guarantee.

Note also that 120 depth samples is a view distance of 120 map units, and a
128x128 tile supplies that only when the camera faces along a tile axis — on a
diagonal heading it supplies about 90. Either the depth range varies with
heading or the tile is re-placed as the camera turns; see the tile-size
section. The full 1024x1024 map is not something the kernel will ever see at
once.

The 68030 side is budgeted in the [stock machine profile](#stock-machine-profile):
roughly 24 ms of DSP ray marching plus surface composition that cannot be
assumed cheap on a 16 MHz 68030 behind a 16-bit bus. The two must overlap.

### There is no measured CPU baseline: the figure has been withdrawn

An earlier revision of this section recorded a measured 89.6 ms / 11.16 FPS
baseline at 160 rays and treated the rest of the performance plan as a
comparison against it. **That figure is withdrawn.** It did not measure a
running program, and no replacement can be taken until the renderer survives
more than a few frames.

The program stops after **three or four rendered frames** under Hatari. The
loop does not exit and no exception is taken - TOS's exception handler at
`$e00f78` is never entered - but control ends up back in TOS on TOS's own
stack, with the VBL vector at `$70` still holding this program's handler, so
`deinit` never ran either. Bisecting the frame body attributes it to the
terrain pass: with `BENCH_NO_TERRAIN=1` the loop reaches 48 frames and keeps
going; with `render_scene` enabled it stops at three or four. That is the top
blocker for every number in this document.

The withdrawn figure's own supporting evidence turns out to be the symptom. It
was recorded that "captures at VBL 2100 and 2500 are byte-identical across the
whole surface", and that was read as proof of a correctly pinned camera.
Byte-identical captures are equally what a stalled program produces, and that
is what was happening: captures at different VBLs with the camera **unpinned
and flying** are also byte-identical. A pinned camera and a dead loop are
indistinguishable by that test, so it cannot serve as one. The check that does
distinguish them is a counter that advances per rendered frame.

Two further faults were found while establishing this, each of which
independently prevented any frame time from being read back. Both are fixed:

- **The VBL handler did not chain.** It replaced TOS's handler at `$70` and
  ended in `RTE`, so TOS's own per-frame work stopped, including advancing
  `_frclock` at `$466`. Any later TOS call that waits on the frame clock then
  blocked forever, which is where the program was found sitting. `src/vbl.s`
  now owns the vector and tail-chains to the handler it displaced.
- **The frame-rate readout could not work under the capture harness.** It
  encoded a window derived from the program's own VBL counter, which reads
  zero whenever the VBL is not reaching the program - exactly the condition
  the unchained handler created. It now encodes the counters directly.

`input_poll` also reads the IKBD ACIA at `$fffffc00` directly while TOS's IKBD
interrupt is still installed, so the two race for bytes from the same device. A
benchmark build no longer calls it, which is right for a timed loop regardless;
the arbitration itself remains an open bug on the interactive path.

When the stall is fixed, the measurement to take is not a single frame time.
Split the frame into surface clear, ray march, span composition and HUD before
quoting anything: the strategy above turns on composition being the term the
DSP cannot help with, and `render_clear` alone writes all 153,600 bytes of the
surface - at least 9.6 ms by this document's own peak-bandwidth figure - which
the terrain pass then overwrites almost entirely below the horizon. Note also
that the ray count changed from 160 to 320 after the withdrawn figure was
recorded, so even as a rough comparison it did not describe the current build.

### How the frame rate is read out

`draw_counters` in `src/main.s` encodes two counters as binary pixel fields at
the top left of the surface: row 0 is `render_count`, row 1 is `frame_count`.
One pixel per bit, most significant first, 32 pixels each.
`tools/read-telemetry.py` decodes a captured surface and reports both.

The time base is the emulator's, not the program's:

```text
frames_per_second = render_count / (run_vbls / vbl_rate)
```

`--run-vbls` stops Hatari after a known number of emulated 50 Hz VBLs, so the
elapsed time is known independently of anything the program believes. Row 1 is
reported so that a VBL which never reaches the program is visible as a zero
rather than silently becoming the measurement - which is precisely how the
withdrawn figure came about.

Startup is not negligible and must be excluded: decoding the two 1 MiB maps
through Hatari's GEMDOS emulation takes tens of seconds of emulated time, so a
window that starts at VBL 0 measures mostly map loading. Take two captures and
use the delta in `render_count` over the delta in VBLs.

A benchmark build is produced without editing any tracked constant:

```bash
BENCHMARK=1 BENCH_ALTITUDE=60 bash tools/build-run.sh
```

Measure these counters per frame:

- DSP cycles or start/end timestamps;
- depth iterations and early exits;
- visible spans and total span pixels;
- map reads and output stores;
- host-port words transferred in each direction, and wait time;
- tile reload words, and how often a reload happens;
- 68030 composition time and missed VBLs.

Keep a fixed benchmark camera and map so changes are comparable. Use a stable
frame budget rather than allowing unusually easy scenes to hide a worst-case
stall. Useful initial acceptance targets are:

- no visible tearing or buffer ownership corruption;
- a sustained 15 FPS floor on the chosen target mode;
- a 20-25 FPS goal at 320-pixel surface width, measured separately for the
  160-ray performance path and the 320-ray quality path, at the agreed depth
  range;
- bounded worst-case frame time, even at maximum depth and dense terrain.

Profile on a real Falcon as well as Hatari. Emulator performance is useful for
functional debugging, but it does not model every external-memory wait state or
cache interaction of an upgraded machine.

## Step-by-step implementation plan

The following sequence begins only after the first playable CPU mission and
its fixed-camera/state comparisons satisfy the gates in
`docs/PORTING-PLAN.md`. The existing CPU renderer, protocol skeleton, and
experiments may be maintained in the meantime, but they are not the primary
integration schedule.

1. **Reference image:** retain or refine the scalar VoxelSpace renderer and
   establish golden screenshots for fixed camera commands.
2. **Measure the machine:** read back the installed DSP SRAM size and its X/Y
   split, measure sustained HI08 throughput in both directions, and time three
   68030 surface writes in the real video mode — a sequential fill, a vertical
   span fill, and the same vertical fill through the Blitter. Everything below
   is sized by those numbers, and all of them are currently assumed rather
   than known.
3. **Protocol stub:** add a 68030 command producer and a DSP idle/acknowledge
   kernel using the register definitions in `src/dsp/ioequ.inc`.
4. **Memory test:** fill known X/Y patterns, verify map sample addressing,
   parallel moves, wrapping, and external-memory timing.
5. **Fixed-point test:** compare ray stepping and projection against the scalar
   reference over a grid of positions, headings, pitches, and depths.
6. **Tile upload:** push a packed map tile through HI08, read it back, and
   confirm it byte for byte against the source. Time the upload; that time is
   the tile reload cost.
7. **DSP span renderer:** emit packed span records into a double-buffered
   local output buffer and let the 68030 read and composite them.
8. **Pipeline:** overlap game update, DSP rendering, span expansion, and VBL
   presentation with explicit buffer ownership.
9. **Tile streaming:** handle the camera crossing a tile boundary without a
   frame-time spike, using whichever edge policy was chosen. Try the
   `DMA playback -> DSP receive` matrix routing here before spending 68030
   time on tile uploads through HI08.
10. **Game integration check:** integrate the optimized terrain path into the
    already playable CPU-correct mission without changing its game-state,
    object, HUD, or local-resource contracts. Sound, music, and networking
    remain deferred.
11. **Release profile:** repeat the tests with the intended RAM size, tile
    size, video mode, and DSP configuration rather than the generous
    development Hatari configuration.

## Common failure modes

- **Map samples look scrambled:** packed byte/word layout or DSP address
  increments are wrong. Test X and Y memory with repeating labelled patterns.
- **Terrain drifts or explodes at distance:** fixed-point scaling, sign
  extension, or reciprocal-table format is inconsistent.
- **Holes or a solid wall:** `ybuffer` initialization, traversal direction, or
  span endpoint convention does not match the reference renderer.
- **Frame rate collapses with colour enabled:** map reads or external memory
  wait states dominate; separate map, projection, and output timings.
- **Frame time spikes as the camera moves in one direction:** a tile boundary
  is being crossed and the reload is not amortized.
- **Intermittent tearing:** the 68030 is compositing into the scanout buffer,
  or the buffer flip is not happening at VBL.
- **DSP appears to hang:** host flags, reset sequencing, command publication,
  or a hardware-loop termination condition is wrong. Add a timeout and status
  breadcrumbs before optimizing.
- **Span expansion costs far more than the pixel count suggests:** vertical
  runs in a row-major surface stride by 640 bytes and defeat DRAM page mode.
  Compare against a sequential fill of the same pixel count before blaming the
  span format.
- **The fast path is no faster:** the 68030 is waiting on the host interface or
  expanding too many spans. Benchmark transport and composition separately
  from the ray-march loop.
- **Captures at different VBLs are byte-identical:** this is *not* evidence of
  a correctly pinned camera. A stalled or dead loop produces exactly the same
  result, and has. Confirm with a counter that advances per rendered frame
  before concluding anything from a stable image, and confirm the camera is
  pinned by unpinning it and watching the same counter.
- **A TOS call never returns:** a handler installed on a TOS vector is not
  chaining, so TOS's per-frame work has stopped and anything waiting on
  `_frclock` at `$466` waits forever. Check `$466` is still advancing before
  suspecting the routine that appears to hang.

## Source locations

- `src/main.s` — VBL-paced 68030 game loop and buffer exchange.
- `src/game.s` — local flight state and first input-driven update.
- `src/input.s` — IKBD scan-code handler and input snapshot.
- `src/render.s` — CPU y-buffer/vertical-span reference renderer.
- `src/hud.s` — 68030 HUD composition after terrain rendering.
- `src/start.s` — Falcon startup, VIDEL setup, and buffer allocation.
- `src/vbl.s` — VBL publication of the display buffer. Owns the `$70` vector
  and tail-chains to the handler it displaced, so TOS keeps advancing
  `_frclock`.
- `src/inc/comanche.s` — shared surface, terrain, and game-state constants.
- `src/dsp/proto.inc` — the 68030/DSP command and rectangle protocol, included
  by both assemblers so the field layout cannot drift.
- `src/dsp_host.s` — 68030 side of that protocol: command publish, result
  drain, rectangle fill. Built but not yet called by the frame loop.
- `tools/prepare-original-test.py` — build-time map decode, palette and table
  generation, with explicit `--source` asset selection.
- `tools/read-telemetry.py` — decodes the binary counter fields out of a
  captured surface and reports frames rendered and frame time.
- `src/dsp/ioequ.inc` — DSP56001 Host Interface and peripheral equates.
- `src/dsp/comanche.asm` — assembled DSP host-interface echo/acknowledge
  stub; it deliberately does not render terrain yet.
- `tools/build-dsp.sh` — DOSBox-wrapped DSP56000 assembler build.
- `reference/f030f29/src/dsp_3d.asm` — comparison material for an existing
  Falcon DSP-oriented renderer; it is not a Comanche implementation.
