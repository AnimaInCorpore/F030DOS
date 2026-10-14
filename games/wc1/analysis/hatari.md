# Hatari — the dynamic oracle (Falcon 030 / Videl)

How to run and photograph this port, the machine model it assumes, and the
pitfalls that cost time. Same role `86Box` plays in the sibling
`F030Underworld` project: **after any change to the presented picture, boot
and look.**

## 1. Machine model

| Setting | Value | Why |
|---|---|---|
| `--machine falcon` | Falcon030 | target |
| `--tos` | `../F030Arcade/third_party/tos404.img` | TOS 4.04; 4.02 and 2.06de also present |
| `--memsize` | **14** (MB) | Makefile default; the design target is a stock 4 MB machine — see below |
| `--monitor rgb` | RGB | Videl 16-bit true colour |
| `--mmu true`, `--cpu-exact true`, `--compatible true` | on | 68030 accuracy |
| `--patch-tos true`, `--fast-boot true` | on | skip ROM boot delays |
| `--sound off` | off | audio is not ported; keeps runs deterministic |
| `--frameskips 0` | 0 | every VBL is rendered — required for frame counting |

`MEMSIZE` is overridable (`make run MEMSIZE=…`). The two 128,000-byte RGB565
Videl pages, the 320×200 indexed draw buffer and the three 72 KiB resource
slots are deliberately sized to coexist with GEMDOS on a **stock 4 MB
Falcon** (`PORTING.md`), so the 14 MB default is headroom, not a requirement.

**Verified 2026-08-20:** the title sequence is byte-identical at `MEMSIZE=4`
and `MEMSIZE=14` — same Videl base `$12EA34` at VBL 2800:

```sh
MEMSIZE=4 bash tools/grab-frame.sh 2800 build/align-check-4mb.png
```

The **flight** slice with all three resource slots occupied has **not** been
captured at 4 MB. Do that before claiming stock-machine support.

## 2. Commands

```sh
make smoke TOS=/path/to/tos404.img     # headless, 600 VBLs, exits on its own
make run   TOS=/path/to/tos404.img     # interactive
bash tools/grab-frame.sh <vbl> <out.png>
```

`make smoke` runs with `--benchmark --disable-video on`: it proves the program
boots, allocates and reaches its loop, but it renders nothing you can look at.
**It is not a verification of the picture.** Use `grab-frame.sh` for that.

## 3. How `grab-frame.sh` captures a frame

Hatari has no "dump the Videl page" command, so the script reconstructs it:

1. Writes `grab.ini` with a one-shot breakpoint `b VBL = <n> :once :file
   wc1-read-base.ini`.
2. That second script reads the Videl base registers `$FFFF8201`, `$FFFF8203`,
   `$FFFF820D` (high/mid/low byte of the screen base) and vector `$70`, then
   `savebin`s **all of ST-RAM plus a guard region** and quits.
3. The script parses the three base bytes back out of `wc1-grab.log`,
   `dd`s the 128,000-byte page out of the RAM dump at that offset, and
   `tools/rgb565_to_ppm.py` + ImageMagick turn it into a PNG.

Requires `timeout` (coreutils) and `magick` on PATH — both present here via
Homebrew.

### Gotchas (all already resolved in the script)

- **The base register is three separate bytes**, not a longword. Reading only
  `$FFFF8201`/`$FFFF8203` gives a base rounded to 256 bytes and the picture
  tears; `$FFFF820D` is the low byte and is mandatory on Falcon.
- **The page can sit above nominal ST-RAM.** GEMDOS may place the RGB565
  `Mxalloc` block in the final top-of-ST-RAM aperture, so the dump covers
  `memsize + max(frame_bytes, 0x10000)` and the extracted range is validated
  against the actual dump size, never against an unresolved pointer.
- **Videl is in 16-bit true colour**, so the dump is big-endian RGB565 words —
  decode before writing PNG. A raw-bytes-as-indexed read produces a garbled
  image that looks like a renderer bug.
- `--fast-forward true` is what makes a 2,800-VBL capture take ~40 s instead
  of ~56 s of wall-clock at 50 Hz.

## 4. Capture a frame the game actually renders

The attract sequence follows the DOS `Title_Sequence()` timeline, so the VBL
number selects what you photograph:

| VBL | What should be on screen |
|---|---|
| ~100 | opening subtitle text |
| ~1,600 | establishing star field / constellation |
| **~2,800** | **`TITLE.VGA` logo zoom** — verified 2026-08-20 |
| ~3,000+ | credits, then action spheres |
| after `Escape` | **Start Vega Campaign** menu |

Verified reference: `bash tools/grab-frame.sh 2800 build/align-check-vbl2800.png`
→ `display buffer at $12ea34`, logo rendered, ~41 s.

If a capture cannot distinguish the change you made from its absence, it has
not verified anything — pick a VBL where the affected pass is on screen.

## 5. Flight capture and VBR ownership

`grab-frame.sh` can now replay deliberate input with `HATARI_INPUT_EVENTS`
(`HATARI_KEY_EVENTS` remains a key-only compatibility alias). Its
comma-separated syntax is `<absolute-vbl>:<keydown|keyup>:<ST-scancode>` for
keys, `<absolute-vbl>:<leftdown|leftup>` for the Hatari mouse button, and
`<absolute-vbl>:mousemove:<dx>:<dy>` for relative mouse motion. It polls
Hatari's `VBL` debugger value and disables fast-forward while a schedule is
active, so event selection is not based on host wall-clock timing. Each edge is
written alone to Hatari's command FIFO. Use separate make/break edges:
Hatari's single `keypress` form can place both bytes in one VBL, which a
per-frame game poll may miss.

The accepted 14-MB title-to-flight transition recipe is:

```sh
MEMSIZE=14 \
HATARI_INPUT_EVENTS='1200:keydown:0x01,1202:keyup:0x01,1600:leftdown,1602:mousemove:1:0,1620:leftup,1622:mousemove:1:0' \
bash tools/grab-frame.sh 2200 build/flight-14mb-vbl2200.png
```

It taps Escape (`0x01`) through the title poll, then uses the front end's
native mouse-button/`INPUT_FIRE` route to accept **Start Vega Campaign**. The
motion pair is required: Hatari's `leftdown` only changes its button state,
whereas the TOS `Initmouse` callback that feeds this port is entered by the
next relative-mouse packet. Return (`0x1c`) and Space (`0x39`) did not reach
the TOS-console accept path under FIFO injection in the 2026-09-10 capture; do
not substitute them in the automated fixture without a separate evidence
record.

**Critical correction, 2026-09-10:** a pre-fix flight dump consisted partly of
executable words because `src/vbl.s` installed its handler at physical `$70`.
TOS 4.04's active MC68030 vector table was relocated through VBR, leaving the
live VBL vector unchanged; the dumped base was therefore TOS's desktop page,
not a port-published page. After that was corrected, TOS still overwrote a
pre-chain Videl page write with its own desktop base. `vbl_install()`/
`vbl_remove()` now use `VBR+$70`, and page publication occurs in the
post-TOS-chain trampoline. Every visual capture script records `info basepage`
as an allocation diagnostic alongside the Videl base. Re-run the recipe above
after any VBL/startup change; the framebuffer must be a port RGB565 page, never
desktop or executable memory.

The same build previously completed `make smoke MEMSIZE=4` for 600 VBLs at
roughly 100 VBL/s. That confirms cold boot and allocation only; the stock-4-MB
flight target remains untested and must not be claimed from the 14-MB fixture.

## 6. Legacy DSP diagnostic

`make dsp-wire-smoke TOS=…` assembles `release/WC1C2P.LOD` and runs a
DSP56001 transport self-test, asserting a `0000` status word in
`release/DSPWIRE.BIN`. It needs `dosbox-staging` and `ASM56000` from
`../F030Comanche`.

**It is not part of the game path.** The 68030 does the indexed→RGB565
expansion (`src/c2p_fast.s`); `src/c2p.c` is the host/reference fixture. The
DSP worker is retained only as an isolated transport diagnostic. Do not
reintroduce it into the presentation path without a measurement that justifies
it.
