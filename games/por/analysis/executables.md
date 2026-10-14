# `START.EXE` and `GAME.OVR` (verified)

The two code files in `work/expanded/`. Nothing below is disassembled yet —
the header/structure pass plus the first disassembly pass. Tooling:
`work/disasm.py` (16-bit recursive descent, capstone), `work/overlay.py`
(overlay directory), `work/disasm_ovr.py` (per-unit descent). Listings:
`work/start16.txt`, `work/game16.txt`.

## `START.EXE` — 47,936 B — the loader stub

MZ header, raw bytes @ file 0x00 (verified):

```
4d 5a 40 01 5e 00 e4 00 3b 00 7c 1a 7c aa 92 0f
00 20 00 00 06 00 00 00 1c 00 00 00
```

| field | value | note |
|---|---|---|
| `e_magic` | `MZ` | |
| `e_cblp` | `0x0140` (320) | bytes in last page |
| `e_cp` | `0x005E` (94) | pages |
| `e_crlc` | `0x00E4` (228) | relocations |
| `e_cparhdr` | `0x003B` (59) | header = 944 B |
| `e_minalloc` | `0x1A7C` | 6,780 par = 108,480 B ≈ 106 KB minimum extra |
| `e_maxalloc` | `0xAA7C` | |
| `e_ss:e_sp` | `0x0F92:0x2000` | |
| `e_csum` | `0x0000` | |
| `e_cs:e_ip` | `0x0000:0x0006` | **entry point** |
| `e_lfarlc` | `0x001C` | reloc table @ file 0x1C, 228 × 4 B |
| `e_ovno` | `0` | |

`(94 - 1) * 512 + 320 = 47,936` = **exactly the file size**, so there is no
appended data past the load image (unlike `../F030Underworld`'s `UW.EXE`,
which self-loads a 141 KB tail). Reloc table occupies 0x1C..0x3AF (912 B,
padded to the 944 B header); **code starts at file 0x3B0**.

Disassemble as **16-bit x86**, load base = wherever DOS puts it; entry
`CS:IP 0000:0006` is relative to the load segment.

### Strings (verified, `strings -n 6`)

```
GAME.OVR                          pool.cfg / POOL.CFG
Please insert startup disk.       Please insert overlay disk.
Unable to find POOL.CFG           Overlay error, program abort!
Not enough memory to run game.  You need  more bytes.
tempsize                          Runtime error
PATH=
```

Read together with the file-name strings, `START.EXE` is the resident stub: it
finds `POOL.CFG`, sizes memory, loads `GAME.OVR`, and owns the overlay manager
and the runtime-error handler.

## `GAME.OVR` — 232,379 B — the game overlay

**No MZ header.** A raw image loaded by the stub above. First bytes:

```
54 50 4f 56 | 21 | 54 69 6d 65 20 74 6f 20 73 61 76 65 20 79 6f 75 72 20 67 61 6d 65 2e 20 20 5b 72 65 74 75 72 6e 5d
"TPOV"        33   "Time to save your game.  [return]"                                          (33 chars)
55 89 e5 83 ec 24 …
push bp; mov bp,sp; sub sp,0x24
```

- `TPOV` = **T**urbo **P**ascal **OV**erlay — **CONFIRMED** by reading the
  loader, see §Turbo Pascal and §Overlay mechanism below.
- The byte after it, `0x21` = 33, is exactly the length of the string that
  follows: **Pascal length-prefixed strings**. The same pattern recurs
  throughout (`0x24`=36 before a 36-char string, `0x25`=37 before a 37-char
  string, `0x23`=35 before a 35-char string — all checked).
- `9a 34 06 bb 05` a few bytes in is `call far 05BB:0634` — the overlay
  far-calls back into a fixed segment. Recovering that segment at runtime is
  the highest-value item for the dynamic-oracle step.

### Trailer table — **RESOLVED** (it is not a trailer)

The "53-entry ascending `u16` table at 0x38B51" recorded in the first pass is
the **fixup block of the last overlay unit** (segment 0x198), not a file-level
structure. That unit's code runs 228,568..232,273 and its declared
`fixupSize` is 106 B = 53 × `u16`, ending exactly at EOF. Every unit has one;
this was simply the last. See §Overlay mechanism.

That also explains the far-return epilogues immediately before it
(`89 ec 5d ca 08 00`, `55 89 e5 89 ec 5d cb`): they are the end of that unit's
*code*, and the fixup table begins right after.

### Strings of interest (verified)

- **Credits**: `scenario created by: tsr, inc.`, `jim ward`, `david cook`,
  `steve winter`, `mike breault`; `ssi special projects`, programming
  `scot bayless`, `brad myers`, `keith brors`, `russ brown`, `ted greer`;
  graphic arts `tom wahl`, `fred butts`, `darla marasco`, `victor penman`,
  `susan halbleib`, `dave shelley`; developer `george mac donald`.
- **Copy protection**: `USE THE TRANSLATION WHEEL TO DECIPHER THE CODE WORD.`,
  `MATCH THE ESPRUAR RUNE (OUTER RING) WITH THE DETHEK RUNE (INNER RING)`,
  `INPUT THE CODE WORD:`, `Sorry, that's incorrect.` — the classic code-wheel
  check, and an early, self-contained disassembly target.
- **Combat UI**: `~COMBAT ~WAIT ~FLEE ~PARLAY`, `~COMBAT ~WAIT ~FLEE ~ADVANCE`,
  `~HAUGHTY ~SLY ~NICE ~MEEK ~ABUSIVE`, `Both sides wait.`,
  `The monsters flee.`, ` dies.`, ` is hit for `, ` points of damage.`,
  `The entire party is killed!`, `The END!`. The leading `~` marks the
  hot-key letter — the menu renderer is worth finding early, it will pin the
  font and text-window code.
- `Unable to find item file` (also in `START.EXE`) → the `ITEMS` reader.

## Turbo Pascal — **CONFIRMED**

`START.EXE` installs four interrupt handlers from one routine at `05BB:006E`
(linear 0x5C1E), with `DS = CS`:

```
mov dx,0x00ce | mov ax,0x2500 | int 21h    ; INT 00h divide-by-zero -> 05BB:00CE
mov dx,0x00d5 | mov ax,0x2523 | int 21h    ; INT 23h Ctrl-C         -> 05BB:00D5
mov dx,0x009d | mov ax,0x2524 | int 21h    ; INT 24h critical error -> 05BB:009D
mov dx,0x00c6 | mov ax,0x253f | int 21h    ; INT 3Fh overlay        -> 05BB:00C6
```

The three handlers that survive read as a Turbo Pascal runtime-error table —
each loads a code into `AX` and falls into a common abort path at `05BB:00D8`:

| handler | first instruction | code | Turbo Pascal meaning |
|---|---|---|---|
| `05BB:00C6` (INT 3Fh) | `mov ax,0x00d0` | **208** | **Overlay manager not installed** |
| `05BB:00CE` (INT 00h) | `mov ax,0x00c8` | **200** | Division by zero |
| `05BB:00D5` (INT 23h) | `mov ax,0x00ff` | **255** | Ctrl-C / user break |

208 and 209 are Turbo Pascal's *overlay* error codes, and the shipped string
`Overlay error, program abort!` matches. Together with the Pascal
length-prefixed strings and the `TPOV` magic, the toolchain is **Turbo Pascal
with the Overlay unit** (5.x/6.0 era; the exact version is still TBD).

The INT 3Fh vector installed here is only the *error stub*; the real manager
replaces it during startup. The second `mov ax,0x253f` site (linear 0x57A6)
restores a handler at `CS:0248` on shutdown.

## Overlay mechanism — **RESOLVED**

`START.EXE` is a thin resident stub: **223,317 of the program's ~270 KB of code
lives in `GAME.OVR`**, reached through `INT 3Fh`.

Each overlaid Pascal unit keeps a small **resident stub segment** in
`START.EXE`. Layout, verified against **all 38** units (`work/overlay.py`):

```
+0x00  CD 3F 00 00        INT 3Fh, DW 0000 — the "load this unit" stub
+0x04  u32LE fileOffset   start of the unit's code inside GAME.OVR
+0x08  u16LE codeSize
+0x0A  u16LE fixupSize    bytes of segment-fixup table following the code
+0x0C  u16LE entryCount   number of 5-byte thunks at +0x20
+0x0E  u16LE              TBD (runs 0..398 across units, not a running total
                          of entryCount)
+0x10  16 B zero
+0x20  entryCount x (CD 3F, u16LE offsetInUnit, 00)   entry thunk table
```

**Chain invariant, exact for all 38 units:**
`fileOffset + codeSize + fixupSize == fileOffset(next unit)`, and the last unit
ends at **232,379 = the exact size of `GAME.OVR`**. No gaps, no slack:

| | |
|---|---|
| units | 38 |
| code | 223,317 B |
| fixup tables | 9,058 B |
| entry thunks | **774** |

`sum(entryCount) == 774` matches the number of `INT 3Fh` stubs found by
scanning `START.EXE` independently.

**Entry chain.** The program entry (`0000:0006`) is 49 consecutive far calls.
**38 of them target `<unitSegment>:0020`** — the head of each unit's thunk
table, i.e. that unit's initialization routine. The remaining 11 are ordinary
resident calls. This is the Turbo Pascal unit-initialization chain.

**Segment `05BB` is the resident runtime**, shared with the overlay: the far
call `05BB:0634` recorded in the first pass at `GAME.OVR+0x39` targets
`START.EXE` linear 0x61E4. Overlay code calling back into the resident stub is
exactly what the model predicts.

## Disassembly state

| | instructions | routines | coverage |
|---|---|---|---|
| `START.EXE` (`work/start16.txt`) | 3,956 | 133 | 14 % of the load image |
| `GAME.OVR` (`work/game16.txt`) | 82,921 | 1,363 | 37 % of unit code |

Coverage is recursive descent from real entry points, so the remainder is
reached through indirect calls (Pascal procedure variables, method dispatch)
and data-driven jumps — expected for this compiler, and the reason Ghidra is
worth using next.

## Video — first evidence

- **EGA sequencer writes** in unit `18E` (`GAME.OVR` 217,565..228,438):
  `mov al,2 | mov dx,0x3c4 | out dx,al` selects **Sequencer register 2 = Map
  Mask**, the EGA plane-select. Also `0x3CE`/`0x3CF` (Graphics Controller).
  So the DOS renderer writes **EGA planes**, unpacking the packed 4 bpp data
  at blit time — consistent with the pixel format resolved in
  `analysis/data-formats.md`, and it means the port's host-side unpack does
  the same job earlier.
- **No `0x3C0` (Attribute Controller) writes and no `INT 10h`** in unit `18E`
  — an early signal from this 37 %-covered pass. A later byte-complete scan of
  both binaries confirmed it program-wide and settled the palette question in
  `PORTING.md` §Open risks: see §The palette question below and
  `analysis/dos-oracle.md` §8.

## Unit `18E` — the renderer (Ghidra, 2026-08-21)

Decompiled with Ghidra 12.1.3 headless: **30 functions, 29 decompiled**, seeded
from the unit's 20 usable entry thunks (4 of its 24 thunk slots are `0xFFFF`
placeholders). Artefacts in `work/ghidra_export/unit18E{.c,_functions.txt,_disasm.txt}`;
recipe in `analysis/tools.md`.

### DGROUP base = paragraph `0x740` — verified

Turbo Pascal splits code and data, so the globals the unit references
(`0x497E`, `0x260A`, `0x4E20`, `0x4FB0`, `0x5140`) are **DS-relative**, not
offsets into the unit image. The abort path in `START.EXE` loads `DS` with
`mov dx,0x740`, predicting DGROUP at load-image linear `0x7400`. Checking
`DS:260A` → linear `0x9A0A` gives

```
01 02 04 08 00 00 00 00 40 10 04 01 80 20 08 02
```

`01 02 04 08` are the EGA Sequencer Map Mask plane selects, and this is the
**only** occurrence of that byte sequence in the whole load image. DGROUP base
confirmed; DS-relative globals can now be read straight out of `START.EXE`.

### `DS:497E` — the video-mode selector

Every drawing routine in the unit branches on `*(char *)0x497E`, which takes
three values:

| mode | path | source consumed per row | evidence |
|---|---|---|---|
| 0 | resident copy helper (`05BB:…`) with a row table at `DS:4E20` | `widthBytes * 2` | 2 bits/pixel → **CGA** |
| 1 | EGA planar, Sequencer `0x3C4/5`, row table at `DS:4FB0` | 4 bytes per 8-pixel group | **EGA** |
| 2 | resident copy helper with a row table at `DS:5140` | `widthBytes * 4` | 4 bits/pixel linear → **Tandy/PCjr 16-colour** |

All three consume `height * widthBytes * 4` bytes for a mode-1/2 image, which
is exactly the payload size the container arithmetic predicts.

### `entry_19A5` — the blitter

`entry_19A5(record, charRow, byteCol)`. It reads only two fields of the record:
`*record` = **height** and `record[1]` = **widthBytes**, matching the image
header in `data-formats.md`. Vertical position is in 8-row units
(`local_6 = param_2 * 8`), horizontal in bytes. The EGA branch is:

```c
out(0x3c4, 2);                                  /* select Map Mask      */
for (row ...) for (col ...) for (plane = 0..3) {
    out(0x3c5, planemask[plane]);               /* 01 02 04 08          */
    screen[rowtable[row] + col] = src[i++];     /* one byte per plane   */
}
out(0x3c5, 0x0f);                               /* restore all planes   */
```

Pixels are taken from `record + 0x17` (23), not `+0x11` (17) as in the file —
the in-memory record carries a 6-byte prefix ahead of the on-disk header.

### `entry_02AD` — packed → planar expander. **This settles the pixel format.**

```c
if (pixelIndex & 1) nib = srcByte & 0x0f;       /* odd  pixel: low nibble  */
else                nib = srcByte >> 4;         /* even pixel: HIGH nibble */
mask = 0x80;                                    /* walks right across 8 px */
for (plane = 0; plane <= 3; plane++)
    if (planemask[plane] & nib)
        dest[0x17 + ...] |= mask;               /* set that pixel's plane bit */
mask >>= 1;
```

The shipped art is **4 bits per pixel, packed, high nibble = left pixel**, and
this routine expands it into four EGA planes at load time. That is the same
layout `analysis/data-formats.md` derived from size identities and confirmed by
rendering — now **confirmed a second time, from the DOS code itself**, which is
the standard this project holds ported behaviour to.

It also explains why the raw file bytes decode as packed and render as noise
when read as planar: the planar form only ever exists in memory, after this
routine runs.

### `entry_24ED`/`entry_25F1` — the record allocator, and the real record layout

`entry_011B` is the unit's load entry point: it reads the 17-byte on-disk
header **field by field** (six reads of 2/2/2/2/1/8 bytes — exactly 17),
passes height/widthBytes/the-9th-byte to `entry_24ED` to allocate the
in-memory record, copies the zero `u32` and the remaining 8 bytes through
unread, then calls `entry_02AD` to decode pixels. `entry_24ED` is the
allocator (GetMem + FillChar) and fixes the record layout — offsets below are
verified by three independent, mutually-consistent sites: `entry_24ED`'s own
writes, `entry_011B`'s copy targets, and `entry_02AD`/`entry_19A5`'s reads
(`((int *)param_1)[N]` at `N=0,1,4` = byte offsets 0, 2, 8, matching exactly):

```
+0x00  u16  height                     (entry_24ED, from the on-disk header)
+0x02  u16  widthBytes                 (entry_24ED, from the on-disk header)
+0x04  u32  0 (copied verbatim, unread by this unit)
+0x08  u8   frameCount                 (entry_24ED, from the on-disk header's 9th byte)
+0x09  8 B  cgaRemap (copied verbatim from the on-disk header, see below)
+0x11  u16  frameStride                computed: height * widthBytes * (2|4), not on disk
+0x13  u32  far ptr to mask buffer     only allocated if requested; 0 otherwise
+0x17  ...  pixel data
```

This corrects the earlier reading of `entry_19A5` as "a 6-byte prefix ahead of
the on-disk header": there is no prefix. The 17-byte on-disk header is copied
into the record **unshifted**, at the same offsets it has in the file
(`+0x00`..`+0x10`); the loader then *splices in* 6 new bytes — a computed
per-element stride and an optional far pointer — between the copied header and
the pixel data, which is why pixel data lands at `+0x17` instead of the file's
`+0x11`. `entry_25F1` is the matching deallocator: it frees the mask buffer
(if the far pointer is non-zero) and then the main block
(`frameCount * frameStride + 0x17` bytes), and zeroes the caller's pointer.

### The 9 unknown header bytes — RESOLVED (2026-08-21)

Byte 0 (record `+0x08`, file offset 8) is the **frameCount** read above.
`entry_02AD` uses it directly as a loop bound (`((int *)param_1)[4]`, i.e.
byte offset 8) in all three video-mode branches — confirmed against real data:
`8X8D1.DAX` block `0x01`'s byte is `0x46` = 70, exactly the "70 × 8×8 tiles"
already established by size arithmetic in `analysis/data-formats.md`, and a
scan of all 778 image headers in `work/expanded/` finds only 9 distinct
values (`1` × 728, `70` × 42, `128` × 2, plus six singletons), `1` being the
ordinary single-image case.

Bytes 1-8 (record `+0x09..+0x10`, file offset 9-16) are a **16-entry, 4-bit
CGA colour-reduction table**. `entry_02AD`'s `DS:497E == 0` (CGA) branch —
and *only* that branch — calls `entry_007B(recordPtr + 9, recordSeg, nibble)`
for every decoded pixel nibble; `entry_007B` copies those 8 bytes into a local
buffer and returns nibble `param_3` from it (odd index = low nibble, even =
high), i.e. a lookup indexed 0-15 by the raw 4 bpp source colour. The result
feeds a second table (`DS:260E`) that produces the actual CGA output bits.
Confirms as a *colour-reduction* table, not a general remap, because every
value it ever returns is bounded to **0-3** — checked across all 778 headers,
zero exceptions — exactly CGA's 4-colour range, and never touching the
0-15 range that would be needed to move between arbitrary EGA colours.
The already-quoted examples in `analysis/data-formats.md` decode cleanly under
this reading: `BODY1`'s 8 bytes → nibbles `0,1,1,1,2,2,1,3,1,3,1,1,3,2,3,3`,
all ≤ 3, same for `HEAD0` and `PIC0.PIC`.

**The EGA branch (`DS:497E == 1`) never calls `entry_007B` and never reads
these 8 bytes** — confirmed by reading that branch in full (it uses only the
already-known `DS:260A` plane-mask table). So for the EGA-targeting port,
`cgaRemap` is dead data: read it only far enough to skip it correctly, and
carry `frameCount` for multi-element blocks.

One byte-order note found while checking this: the "always zero" `u32` at
`+0x04` is not quite always zero — `TITLE.DAX` blocks `0x01` and `0x02` (the
two title-screen variants) both carry `1` there. No code in unit `18E` reads
that field (`entry_011B` only copies it through), so its meaning, if any,
stays open.

### Blit-time transparency — RESOLVED (2026-08-21), corrects the `entry_1BAB` lead

The mask buffer optionally allocated by `entry_24ED` (`+0x13`, above) is a
real colour-key mechanism, not speculative. `entry_02AD` builds it while
decoding: whenever the record has a non-zero far pointer there, every pixel
nibble is compared against `param_2` — a **caller-supplied transparent-colour
index**, threaded from `entry_011B`'s own `param_2` all the way down, i.e. it
is not hardcoded to colour 0 — and a mask bit is set wherever the pixel
matches. This runs on **all three** video-mode branches, EGA included (the
EGA branch's `entry_0000` call at `DS:497E == 1` builds the mask the same way
the CGA/Tandy branches do inline).

**`entry_0000` itself, confirmed (2026-08-21) by hand-tracing the raw bytes** —
Ghidra's decompiler fails on it (`Offset must be between 0x0 and 0x10ffef, got
0xffffffff instead!`), but it is only 0x78 bytes and reads cleanly:
`entry_0000(4 raw source bytes passed inline on the stack, colourIndex byte)`
tests both nibbles of each of the 4 bytes (8 pixels total) against
`colourIndex` — high nibble against `colourIndex << 4`, low nibble against
`colourIndex` directly — and returns one byte where **bit N is set iff pixel N
equals the transparent colour**, built with the exact `0x80 >> N` shift-and-OR
pattern used throughout this unit's plane code. The caller (`entry_02AD`)
then tests that byte's bits one at a time to decide which mask-buffer bits to
set — this is the transparency mask's actual bit-test primitive, not just the
structural inference the previous version of this note left it as.

At composite time the mask is consumed by every multi-record blit routine
found in the unit — `entry_08F5`, `entry_0D9F`, `entry_1EBA`, `FUN_0000_27a6`
— all via the same pattern: `dest = (dest & mask) | src`, i.e. destination
pixels survive wherever the source was the transparent colour, source pixels
overwrite everywhere else. This is almost certainly the `.PIC`
frame-0-plus-sparse-overlay compositor (`entry_0D9F`'s clipping arithmetic —
negative offsets, `CARRY2` overflow checks — matches compositing one record
onto another at an arbitrary row/column, not blitting straight to video
memory). It settles `analysis/data-formats.md`'s open question: transparency
is real and EGA-live — and which colour index each `.PIC` overlay frame
actually requests is *also* resolved, not left open here: see §Who calls
`entry_011B`? below, which reads all 19 real callers directly from
disassembly.

This **corrects** the previous lead on `entry_1BAB`: full reading shows it is
the **dirty-row screen-flush/present routine**, not a transparency site — it
walks a 168-entry (`0xa7`+1) per-8-row dirty table (`DS:4988` flag,
`DS:4A30`/`DS:4B80`/`DS:4CD0` span bookkeeping) and blits accumulated dirty
spans to the live EGA framebuffer at segment `0xA000`, one Sequencer-selected
plane at a time — the DOS-side analogue of this project's own VBL dirty-page
flip, at row rather than page granularity. Its `out(0x3CE,5); out(0x3CF,1)`
(Graphics Controller Mode register = write mode 1, EGA/VGA's latch-copy mode)
drives a same-segment `0xA000`→`0xA200`-offset block copy, not a colour test.

### `entry_1618` — horizontal mirror. RESOLVED (2026-08-21), by arithmetic, not rendering

Confirmed without needing a rendered image: the index arithmetic is
unambiguous on its own. In both the EGA (`DS:497E==1`) and Tandy (`==2`)
branches, the *source* index is `iVar5 = (local_6 - local_4) + local_8`, where
`local_6` starts at `rowBytes - step` and `local_4` (the *dest* index) counts
up from 0 — so as the write cursor moves forward through the row, the read
cursor moves backward through it. Every byte read this way is passed through
a bit-permutation helper before being written at the forward position:
`entry_14D5` (full 8-bit reversal — turns "pixel 0..7" into "pixel 7..0"
within one EGA plane byte) on the EGA branch, `entry_15E7` (swap the two
nibbles) on the Tandy branch, where two pixels share a byte. Backward-read +
forward-write + per-byte bit/nibble reversal is exactly what mirroring a row
requires for each pixel packing — there is no other operation that pairs
those three. The EGA branch applies the same reversal a second time,
independently, to the mask buffer (`+0x13`) when present, so a mirrored
sprite keeps its transparency mask in sync. (The CGA branch also reverses
bit-pairs per unit via `entry_155A`, but its read index is a plain forward
scan, not the same backward computation — CGA is outside the port's scope, so
this asymmetry wasn't chased further.) Likely use: mirrored sprite/portrait
facing, a common Gold Box technique — not yet tied to a specific caller.

### `entry_1EBA` — 16-pair palette substitution. RESOLVED (2026-08-21)

**Structural correction first:** `entry_1EBA` is not a 233-byte function. Ghidra
split what is actually **one 1,587-byte routine** — the largest in the unit,
narrowly beating `entry_02AD` — into nine separate "functions"
(`entry_1EBA` itself, then `FUN_0000_1fa3`, `FUN_0000_2388`, `FUN_0000_23a5`,
`FUN_0000_23be`, `FUN_0000_2473`, `FUN_0000_247a`, `FUN_0000_2485`,
`FUN_0000_2490`), because its body contains a `for`-style loop whose
increment step (`0000:1fa3  INC byte ptr [BP + -0x36]`) is reached only by a
backward `JMP`, not a `CALL` — Ghidra's function-boundary heuristic mistook
that jump target, and several others like it, for independent entry points.
Proof, read directly off the bytes: `0000:1f9d MOV byte ptr [BP+-0x36],0x0`
/ `0000:1fa1 JMP 0x0000:1fa6` / `0000:1fa3 INC byte ptr [BP+-0x36]` — a
classic init/test/increment loop, with the "increment" step sitting exactly
at what Ghidra labelled `FUN_0000_1fa3`. The chain rejoins at
`0000:2496 JMP 0x0000:1fa3` (the loop's back-edge) and the *whole* routine
ends at `0000:24ea RETF 0x10`, immediately followed by `entry_24ED`'s own
`PUSH BP` prologue at `0000:24ed` — no gap, confirming both the true extent
and that `FUN_0000_2a6c` (much further on, part of `FUN_0000_27a6`'s tail
instead) was wrongly folded into this chain in the previous pass.

**Real parameter count, from the prologue, not the decompiled signature**
(same under-counting pattern as `entry_011B` and `entry_24ED` — this project
now treats it as the default assumption for any Ghidra far-call signature,
not the exception): `RETF 0x10` cleans up **16 bytes (8 words)**, but the
recovered C signature (`undefined2 *param_1, char param_2, int param_3`) only
accounts for 4. The other 4 words are two more far pointers, confirmed by the
first two instructions in the body:

```
LES DI,[BP+0x12]; ...; CALLF 0x0000:5e0d(farptr, &local[BP-0x10], 16)  ; copy 16 B from a caller pointer
LES DI,[BP+0xe];  ...; CALLF 0x0000:5e0d(farptr, &local[BP-0x20], 16)  ; copy 16 B from a second caller pointer
```

So the real signature is **`entry_1EBA(sourceRecord, clipFlag, frameIndex,
findColours: far ptr to 16 bytes, replaceColours: far ptr to 16 bytes)`** —
the caller owns and supplies both 16-entry colour lists; they are not part of
the record or a resident table.

**Confirmed mechanism:** clones the source record (via `entry_24ED` +
`entry_25F1` bracketing the routine), then for each of up to 16
`(find, replace)` colour pairs — skipping any pair where `find == replace` —
tests every pixel exactly across all 4 EGA planes simultaneously (build a
per-plane mask from `find`'s bit pattern against the `DS:260A` plane table,
XOR each source plane byte against that mask so a full match reduces to all
1-bits, optionally gated per-pixel by a clip-region test via
`func_0x00006844`), and where a pixel matches `find`, overwrites its bits in
every plane with `replace`'s pattern. `param_3` (frame index) selects a
single frame when non-negative, or "all frames" (using the record's own
`frameCount`) when negative — matching a multi-frame `.DAX` array (e.g.
`8X8D*`) as readily as a single image.

This confirms the original guess: **exact, multi-colour palette substitution
across a whole image or one frame of it**, driven entirely by caller-supplied
colour pairs — plausibly the character-portrait recolour (hair/armour/skin
variants sharing one base image), though which caller uses it for that is
untraced.

### Who calls `entry_011B`, and with which transparent index? RESOLVED (2026-08-21)

**Correction to the previous entry:** the claim that inter-unit calls "are not
literal far calls to `018E:0039`" was wrong — it was reasoning from
`unit019`'s *decompiled C*, which is exactly the kind of imprecise
far-call modelling this file has flagged before (`func_0x0000193c(0x18e,...)`
is Ghidra failing to resolve a cross-segment target, not evidence of an
indirection layer). The raw disassembly settles it outright: `work/start16.txt`
and `work/game16.txt` both show plain `CALLF` instructions with the target
unit's nominal segment as an immediate operand —
`000038  9a20008e01  lcall 0x18e, 0x20` is `START.EXE`'s own call into unit
`18E`'s init thunk, byte for byte. Grepping both listings for
`lcall 0x18e, 0x39` (thunk #5 → `entry_011B`, per `work/overlay_map.json`)
finds **19 real call sites**, across units `019`, `069`, `0C5`, `12B`, `147`
and `18A` — no trampoline, no indirection, just `CALLF` landing on the
resident `CD 3F` thunk described earlier in this file.

**`entry_011B`'s true parameter layout** (found by reading its own prologue at
`0000:011b`, not the decompiled signature, which under-counts it exactly the
way it under-counted `entry_24ED`'s):

```
[BP+6]   far ptr   record-pointer-pointer (VAR/output param)     — Ghidra's param_1
[BP+0xA] byte      transparent-colour index                       — Ghidra's param_2
[BP+0xC] byte      want-mask-buffer flag (bit 0, -> entry_24ED)    — Ghidra's param_3
[BP+0xE] byte      a lookup/validity key for a resident helper;
                   if that lookup fails the rest of the load is skipped
```

The offset-to-role mapping isn't guessed: it comes from reading `entry_011B`'s
*own* call into `entry_02AD` (`0000:0290`, pushes `[BP+0xA]` immediately
before the record pointer, landing on `entry_02AD`'s already-confirmed
transparent-index parameter) and into `entry_24ED` (`0000:0229`, pushes
`[BP+0xC]` as the mask-request flag `entry_24ED` tests with `&1`).

**Every one of the 19 call sites was read**, straight from the raw
disassembly bytes, not the decompiled approximation:

| caller | `[BP+0xE]` (lookup key) | `[BP+0xC]` (want mask) | `[BP+0xA]` (colour) |
|---|---|---|---|
| `019`, `069`, `0C5` (×5), `12B` (×2), `147:0083` | `1`..`6`, literal, or threaded from the caller's own param | `0` | `0` |
| `147` (6 of its 8 calls) | literal, threaded, or `base+0x80` | **`1`** | `0` |
| `18A` (its 1 call) | threaded from the caller's own param | **`1`** | **`0xD` (13)** |

**Answer:** transparency is only ever *requested* (want-mask=1) by units `147`
and `18A` — never by `019`/`069`/`0C5`/`12B`, which load opaque images. And
when it is requested, **the transparent colour is 0 in 6 of 7 cases, and 13 in
the seventh** (`18A`'s one call). So the original naive guess in
`analysis/data-formats.md` — "is colour 0 transparent" — turns out to be
*usually* right, but not universally: it is a real per-call parameter, not a
hardcoded constant, and at least one caller deliberately keys on a different
colour.

This closes `PORTING.md` §Open risks 3 completely (mechanism *and* the
concrete index values), not just the mechanism as the previous entry left it.

Untouched by this pass: `[BP+0x10]`, a fourth far pointer `entry_011B` reads
at its very start and passes to `func_0x000061fe(ptr, 0xFF)` before any of the
above — no caller pushes a value there (all 19 sites push exactly 5 words),
so it reads whatever the Pascal runtime convention puts there implicitly.
Plausibly a stack-overflow guard or similar TP runtime plumbing; not chased
further, and it does not affect the parameter findings above, which come from
values callers *do* push. Also untouched: `[BP+0xE]`'s exact lookup semantics
— it is passed to `CALLF 0x0000:2473`, and the `0x0000` segment placeholder
(fixed up at load time, same convention as every other resident-helper call
in this unit) means that is a call into the *shared runtime*, not unit
`18E`'s own code. **Correction, caught while writing this up:** an earlier
version of this note called it "`FUN_0000_2473`", conflating this resident
call with unit `18E`'s own internal address `0x2473` — which is real code
(part of `entry_1EBA`'s fused body, §`entry_1EBA` above) but is a completely
different, unrelated location that only coincides numerically. The resident
helper's actual identity is still open.

### The rest of unit `18E`

The same Ghidra mis-split affects one more pair: `FUN_0000_2a6c` (body "6 B",
decompiled as a bare `return`) is not a function — it is `FUN_0000_27a6`'s own
loop-exit epilogue (`0000:2a67 JZ 0x0000:2a6c` / `... 0000:2a6c MOV SP,BP;
POP BP; RETF 0x12`), reached by a jump, not a call. Treat `entry_268E`,
`FUN_0000_27a6` and `FUN_0000_2a6c` as (at most) two real routines, not
three — not otherwise characterised this pass. `entry_00D7`/`entry_0107`
(tiny, `DS:497c/497d`-adjacent) remain unread. `entry_0000` — the other
decompilation failure (`Offset must be between 0x0 and 0x10ffef`) — is
resolved: see §Blit-time transparency above, read by hand from its 0x78 raw
bytes since Ghidra couldn't produce C for it.

## Reassembly proof (`make reasm`, 2026-08-21)

The disassembly is verified by re-encoding it and comparing, not by coverage
percentages. `work/reasm.py` emits NASM source, assembles it, and compares each
instruction's generated bytes against the original using NASM's `-l` listing.
Anything that re-encodes differently is demoted to `db` and the file is rebuilt,
so **byte-exactness is an invariant**; what moves is the ratio of bytes emitted
as real instructions. `work/rebuild.py` then reassembles everything and rebuilds
the two original files.

| | result |
|---|---|
| `GAME.OVR` | **BYTE-IDENTICAL**, 232,379 B |
| `START.EXE` | **BYTE-IDENTICAL**, 47,936 B |
| overlay units round-tripping | **38 of 38** |
| overlay code emitted as instructions | **179,485 / 223,317 B = 80 %** |
| `START.EXE` load image | 10,290 / 46,992 B = 21 % |

`START.EXE`'s lower figure is expected, not a defect: DGROUP alone (linear
`0x7400`..EOF) is 17,296 B — 37 % of the file — and is data by construction,
and the 774 five-byte overlay thunks and 38 unit headers account for much of the
rest.

Per-unit scores range from 63 % (`01D`) to 89 % (`198`), with the two largest
units at 85 % (`020`) and 84 % (`06C`). Every remaining `db` run inside a code
region is either data or code reachable only through an indirect call or jump
table — that set is the worklist for finishing the code/data map, and
`work/reasm/*.asm` locates it exactly.

### `TPOV` is the file signature — length now proven

`GAME.OVR` opens with `54 50 4f 56` and the **first overlay unit's directory
entry declares `fileOffset = 4`**, so the signature is exactly 4 bytes with no
further file-level header. The rebuild reproduces the file only when those 4
bytes are emitted ahead of unit `016`; the first attempt failed with
`unit 016 starts at 0, directory says 4`, which is what pinned it.

## Decompilation corpus — all 38 units (`make decompile`, 2026-08-21)

One headless Ghidra run over `work/ghidra/units/`, each unit imported at its own
base with `PORSeed.java` resolving its entry-thunk list by program name.

| | |
|---|---|
| units decompiled | **38 of 38** |
| functions | **1,102** |
| decompiled successfully | **1,082** (20 failures, all isolated) |
| resident entry points covered | **748 of 758** usable thunks |
| internal functions found by analysis | 354 |
| decompiler C | 2.27 MB, `work/ghidra_export/*.c` |

`work/funcmap.py` writes `work/ghidra_export/index.txt`, mapping every function
to `unit:offset`, its size, and — where it is one — the index of the resident
`INT 3Fh` thunk that reaches it. That index is the phase-3 worklist; a flat pile
of 1,102 functions is not usable, grouped and tagged by entry identity it is.

Largest internal (non-entry) functions, the natural first targets:
`0D9:19E6` (2,237 B), `020:21FF` (1,414 B), `0B6:196F` (1,354 B),
`058:144F` (1,227 B), `0B6:153C` (1,029 B).

Ghidra declined to create functions at two addresses (`0000:1213`, `0000:1241`)
because a referring thunk sits inside the body — that plus a few unreachable
slots accounts for the 10 thunks without a function.

## The palette question — RESOLVED

**The game never programs a palette.** Settled statically, byte-complete over
both binaries — see `analysis/dos-oracle.md` §8 for the final scan (adds the
15 unresolved `AH` call sites below, plus the 0x3C0/`0x3C8`/`0x3C9`/`AH=10h`
immediate-operand table) and the confirmation that the mode number itself
(`0Dh` EGA vs. `04h` CGA) comes from `POOL.CFG` line 1, not a hardcoded
`mov ax`. `PORTING.md` §Open risks 1 is closed on this evidence: the port's
16-colour EGA default is sourced, not assumed.

*Superseded, kept for the reasoning* — this was the state after the Ghidra
decompilation pass alone, before the byte-complete scan above closed the
remaining gap:

Evidence then covering **all 38 units plus `START.EXE`**:

- **No `0x3C0` write anywhere.** The EGA Attribute Controller — where the
  16-colour palette is programmed — is never touched. The only video ports used
  are the Sequencer (`0x3C4/5`, 9+3 sites) and Graphics Controller
  (`0x3CE/F`, 3 sites), both plane-selection, not colour.
- **Exactly one `INT 10h` in the whole program**, at `START.EXE` linear
  `0x572C`, inside a shared register-preserving wrapper
  (`push si/di/bp/es; int 10h; pop …; ret`). `AH` is supplied by the caller.
- Statically resolvable callers use `AH` = `02`/`03` (cursor), `09` (write
  char/attr), `0E` (teletype), `0F` (get video state). **None** is `AH=10h`
  (set EGA palette registers) or `AH=0Bh` (set CGA palette).
- **15 call sites do not resolve statically** — `AH` is loaded too far back or
  computed.

So no palette programming has been found, but absence of evidence is not
evidence of absence here: those 15 sites, plus the 20 % of overlay code still
emitted as `db` by the reassembly proof, are the gaps. **The dynamic oracle
settles this cheaply** — boot under DOSBox-X and log `INT 10h` and port writes
(`AGENTS.md` §Next steps 8). Until then the port's palette stays labelled
unproven.

## Unit `131` — the dungeon-view renderer (Ghidra, 2026-08-21)

Found by searching, not by size or thunk-count heuristics: `analysis/data-formats.md`'s
`GEO*`/`WALLDEF*` families had no known reader. A raw byte search of
`GAME.OVR` for the literal strings `GEO` and `WALLDEF` — both appear as
Pascal `ShortString`s (`\x03GEO`, `\x07WALLDEF`), each immediately followed
by `\x04.dax`, i.e. filename-construction constants — lands both inside the
same unit, file offset 202415, `seg=0x131`. That unit is small (13 functions,
~5.3 KB) and reads in full without hitting any Ghidra decompilation limits
except one (`entry_0000`, same failure signature as unit `18E`'s, not chased
this pass).

### `entry_10EA` / `entry_0E25` — the `GEO`/`WALLDEF` loaders

Build a filename (`"GEO"`/`"WALLDEF"` + region digit + `".dax"`), read it, and
copy the payload into a resident array — `*(undefined4*)0x69ba` for `GEO`,
`*(undefined4*)0x69b6` for `WALLDEF`. Full byte-level findings are in
`analysis/data-formats.md` §`GEO*.DAX` and §`WALLDEF*.DAX`; the short version:
`entry_10EA` checks the loaded size against `0x402` (**1,026** — confirms the
known `GEO` block size from the read side, independent of the container
math) and copies from source offset 2 (skipping a 2-byte header) in four
256-byte chunks — the loader is *why* the four-256-byte-region layout in
`data-formats.md` is confirmed, not guessed. `entry_0E25` checks against
multiples of `0x30c` (**780**, the known `WALLDEF` block size) and copies
`N` whole blocks into consecutive 780-byte slots.

### `entry_0327` / `entry_048A` / `entry_058F` / `entry_0358` — the `GEO` plane accessors

Read cells back out of the array `entry_10EA` filled, all indexed
`row*0x10 + col` (confirming the 16×16 shape per region): `entry_0327` is a
bounds check (`0 <= row,col < 16`); `entry_048A` reads region 0 or 1 as
nibbles (`param_1` ∈ `{0,2,4,6}` selects region+nibble); `entry_058F` reads
region 2 as a plain byte; `entry_0358` reads region 3 as one of four 2-bit
fields packed per byte. All four guard with the same pattern — clamp
out-of-range `row`/`col` to 0 or 15, and refuse entirely
(`*(char*)0x82a2 == '\0' || == '\n'`, an unidentified mode/state byte) unless
`entry_0327`'s bounds check passes.

**`entry_058F`/`entry_0358`'s callers, and three state globals (2026-08-21)**
— neither is called from anywhere in unit `131` itself (`entry_0614` only
ever calls `entry_048A`), so their consumers had to be found the same way as
`entry_011B`'s: grep raw disassembly for `lcall 0x131, 0x3e`/`0x39` (their
thunk offsets). Real callers exist in units `020`, `045`, `05F`, `0A5`, `124`.
Every call site reads the same two globals for `(row, col)` —
**`DS:0x6A0B`, `DS:0x6A0C`** — and `entry_0358`'s callers push a third,
**`DS:0x6A0D`**, as its region-selecting `param_1`. `0x6A0D`'s value must be
even for `entry_0358` to behave (same constraint as `entry_0614`'s facing
parameter), and one caller (`unit05F`) divides it by 2 to index a 4-entry
table — consistent with it being the same **cardinal-direction** value, not
a coincidence. `unit020` separately caches `0x6A0B`/`0x6A0C` and compares
against the cache to detect "has the party moved." Reading this together:
**`0x6A0B`/`0x6A0C` are almost certainly the party's current map row/col, and
`0x6A0D` its current facing** — the same three-value state `entry_0614`'s own
parameters describe, just held globally instead of passed in. This makes
region 2 (`entry_058F`, no direction input) a **per-cell property**, and
region 3 (`entry_0358`, direction-indexed like the wall planes) a
**per-direction flag distinct from wall presence** — one caller branches on
its result being `1` vs `2` specifically, consistent with a small enum
(door/stairs/special-square-in-this-direction), not confirmed further.

### `entry_0219` — draw one wall segment. RESOLVED (2026-08-21)

`entry_0219(param_1, param_2, param_3, param_4)`: `param_1` is not a record
pointer — it is an **index (1-9 at every real call site) into three parallel
10-entry tables at `DS:0xca0`/`0xcaa`/`0xcb4`** (10 bytes apart, confirmed by
reading them directly at the shared DGROUP base `0x740`; full table and the
byte-exact `offset[i]+width[i]*height[i]==offset[i+1]` proof that ties them
to `WALLDEF`'s 156-byte sub-arrays are in `analysis/data-formats.md`
§`WALLDEF*.DAX`). `param_1` selects a `(offset, width, height)` sprite slot;
`entry_0219` then walks that `width × height` rectangle of a `WALLDEF` byte
array — `*(undefined4*)0x69b6 + param_2*0x9c + slotOffset` (`0x9c` = 156,
so `param_2` selects **which of `WALLDEF`'s 5 per-region sub-arrays**, almost
certainly the wall-type/texture ID read from `GEO`) — and for every non-zero
cell calls **`func_0x000018cf` in unit `18A`** — the same unit that was
`entry_011B`'s one caller requesting a non-zero (`13`) transparent colour
(§Who calls `entry_011B`? above) — passing the cell's byte value and a screen
position (`local_a+2`, `local_8+2`, the loop indices offset by a 2-cell
border). Reads as "blit this pre-drawn wall sprite at this screen slot,"
called from `entry_0614` below with different literal slot indices
(`9`, `1`..`8`) per depth/side.

### `entry_0614` — the raycast/orchestrator. The central routine (1,981 B, the largest in the unit)

`entry_0614(direction: byte, x: char, y: char)`. Derives three more values
from the input (`(dir+2)%8`, `(dir+4)%8`, `(dir+6)%8` — right, behind, left
relative to current facing), then for **3 depth ranks** (`local_15 = 2,1,0`,
each sweeping 4/3/2 cells sideways respectively — see §The depth×side →
sprite-slot mapping below for the exact count) advances the traced cell by a
per-direction `(dx,dy)` delta read from two 8-entry tables at
`DS:0x274A`/`DS:0x2753`, querying `entry_048A`/`entry_0327` for wall presence
at each step and calling `entry_0219` to draw when a wall is found, with a
literal screen-position/style constant baked in per depth×side. Falls back to
`entry_0000` (the unit's other decompilation failure, unread) when
`DS:0x6a0a` is non-zero — a mode flag, purpose TBD.

**Two things resolved after the fact (2026-08-21), both from reading `START.EXE`
directly:**

1. **Unit `131` shares unit `18E`'s DGROUP base** (paragraph `0x740`,
   `analysis/executables.md` §DGROUP base above) — confirmed, not assumed,
   because reading `DS:0x274A` under that base produces an unmistakably real
   table (below), not noise. This is a reusable fact: DGROUP looks to be
   **one segment shared across overlay units**, not one per unit, so any
   unit's `DS`-relative globals can be read the same way once one unit's base
   is pinned down.
2. **The direction-delta tables, read at `0x740:0x274A` / `0x740:0x2753`**
   (signed bytes):

   | index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
   |---|---|---|---|---|---|---|---|---|
   | dx | 0 | 1 | 1 | 1 | 0 | -1 | -1 | -1 |
   | dy | -1 | -1 | 0 | 1 | 1 | 1 | 0 | -1 |

   An exact, clean 8-direction compass (each step a 45° rotation) — not
   guessed, read.

**Correction to the "8-direction" framing above:** `entry_0614`'s own
`direction` parameter is not free to take all 8 values in practice.
`entry_048A` (the region-0/1 accessor `entry_0614` calls for wall presence)
only has defined behaviour for `param_1 ∈ {0, 2, 4, 6}` — the odd cases fall
through its `if`/`else if` chain with no `else`, returning whatever garbage
was in an uninitialised local. Since `entry_0614` passes `direction` and its
`±2/4/6 mod 8` rotations straight through as that same parameter, and all of
those preserve parity, **`direction` itself must always be even** — i.e. one
of 4 cardinal facings, not 8. That matches this game family's well-known
4-directional dungeon movement, and the delta table's odd-indexed entries
(the diagonals) are real, verified bytes that this particular routine simply
never reads.

**This closes the "which `GEO` plane is which direction" question, cleanly:**
`entry_048A`'s four cases are exactly `direction ∈ {0, 2, 4, 6}` → {region 0
high nibble, region 0 low nibble, region 1 high nibble, region 1 low nibble}.
So `GEO`'s two nibble-packed 256-byte regions are not an arbitrary 4-plane
pack — **each of the 4 cardinal directions gets its own nibble-plane, two
directions sharing each byte** (high/low nibble). Region 2 (plain byte) and
region 3 (2-bit-packed) are not read by `entry_0614` itself — their own
callers, elsewhere, are covered above in §the `GEO` plane accessors.

### The depth×side → sprite-slot mapping. RESOLVED (2026-08-21)

Reading all three `local_15` passes in full (rather than the structural
summary above) pins down exactly which of `entry_0219`'s 10 sprite slots
(§`entry_0219`) each part of the view uses. `local_15` counts down `2, 1, 0`
— **rank 2 is the farthest visible row** (the sweep starts 2 cells ahead of
the party, `local_7/local_9` initialised from the facing delta `×2`), and
each outer iteration steps the row *back toward the party* by one cell (using
`uVar8`, the 180°-reverse direction), so rank 0 is the party's own row. Within
each rank, `entry_0614` sweeps sideways using `uVar7`/`uVar9` (the ∓90°
directions) and tests two things per cell: a wall **ahead** (facing
`param_1`, the input direction) and a wall on that **side** (facing `uVar7`
or `uVar9` itself):

| rank | depth | side sweeps | ahead-wall slot | side-A slot (`uVar7`) | side-B slot (`uVar9`) |
|---|---|---|---|---|---|
| 2 (far) | 2 cells ahead | 4 steps | **0** (run body) + **9** (run-end cap) | **1** | **2** |
| 1 (mid) | 1 cell ahead | 3 steps | **3** | **4** | **5** |
| 0 (near) | party's row | 2 steps | **6** | **7** | **8** |

This matches the sprite-size table exactly: slot size grows as rank gets
nearer (far ahead-wall: `1×2`; mid: `3×4`; near: `7×8` — the biggest sprite
in the set — and the side-wall slots grow `1×4 → 2×8 → 2×11` the same way).
Rank 2's ahead-wall is the only one handled as a **run** (a small "body" slot
`0` blitted at every wall cell, closed off with a distinct "cap" slot `9`
when the run ends) rather than one slot per cell — plausibly because a
distant straight corridor can span the whole 4-cell sweep, and drawing every
cell individually at that scale would look wrong. The `0xcbe`-range table
supplies each of these calls' base screen row, offset by a per-step `local_14`
that walks in the opposite direction to the sideways sweep (so rank 2's
row position moves one way while `local_12` advances the other), and the
`0xcd2`-range bytes are a per-slot style/orientation byte passed to
`entry_0219`'s `param_1` high bits — real values, not yet given a confirmed
meaning.

**Still open:** the `0xcd2`-range style bytes' exact meaning, whether `uVar7`
is screen-left or screen-right (not determined — "side A"/"side B" above is
neutral on purpose), and `entry_0000`'s decompilation failure in this unit
(same signature as unit `18E`'s
`entry_0000`; not confirmed to be the same kind of routine).

## Unit `18A` — the wall-tile blit dispatcher, and it closes the loop (Ghidra, 2026-08-21)

Found by following the trail, not by search: `entry_0219` (unit `131`, above)
blits every non-zero `WALLDEF` cell by calling `func_0x000018cf` in unit
`18A`. That specific function isn't decompiled cleanly, but unit `18A` is
tiny — 3 functions, 121 lines — and its other two functions turn out to
answer a bigger question than the one that led here.

### `entry_003B` — load a tile-sheet family record

`entry_003B(param_1: byte)` loads a far pointer into a 5-entry cache at
`DS:0x5D98` (`param_1*4`), reading it if already resident, or loading it
(via the same `func_0x000061e4`/`func_0x00006e7a`/`func_0x000026b0` sequence
seen throughout this project for "open a resource, fall back to an install
disk prompt on error") if the cache slot is still `0:0`. `param_1` is a
**family index, 0-4** — five slots, matching what `entry_015D` needs, below.

### `entry_015D` — blit one global tile ID. This is the connection.

`entry_015D(tileValue, maskFlag, tileID: int, x, y)`. Classifies `tileID`
into one of **5 families by range** — `1..45`→0, `46..115`→1, `116..185`→2,
`186..255`→3, `256..286`→4 (anything else, including 0, is an error path
that reads a message string from unit `18E` and aborts to the same
"overlay/install disk" error flow noted above) — then subtracts a
**per-family base offset**, a 5-entry table at `DS:0x2736`, giving a
**local frame index** within that family's record. Then either:

- `maskFlag == 0`: read `frameStride` from the family record at `+0x11`,
  copy one frame's pixel data (`record + localIndex*frameStride + 0x17`)
  into a staging buffer, and call `func_0x0000193c(recordSeg, recordOff, x, y)`
  — a generic "blit this staged record here" dispatch; or
- `maskFlag != 0`: call `func_0x00001928` directly against the family
  record and `*(undefined2*)0x4980`/`0x4982` — **the exact same DS-relative
  address unit `18E`'s `entry_1BAB` uses as "the current picture" pointer**
  (`analysis/executables.md` §Blit-time transparency) — with `param_4`'s top
  bit folded into both the tile value and the local index
  (`CONCAT11(param_4>>7,...)`, plausibly a mirror/flip flag, unconfirmed).

**Both the `+0x11`/`+0x17` record layout and the `0x4980` picture pointer are
unit `18E`'s own conventions, not unit `18A`'s.** This unit doesn't blit
pixels itself — it classifies a tile ID, picks a frame, and calls back into
the same image-record machinery §Unit `18E` already fully documents. The
dungeon renderer and the general image loader are one system, not two.

### The 5 families are the `8X8D*.DAX` tile sheets — confirmed against the whole corpus

The family frame-counts (45, 70, 70, 70, 31) are distinctive enough to check
directly: scanning every `frameCount` header byte across all 1,044 `.DAX`
blocks in `work/expanded/` (the same scan from §The 9 unknown header bytes),
**every single block with `frameCount` of 45, 70 or 31 is an `8X8D*.DAX`
block**, and every one is `8×8` px (`h=8, wb=1`) — exactly the "8×8 tile
sheets" `analysis/data-formats.md` already named but had no known consumer
for. That closes it: **`8X8D*.DAX` is the dungeon wall-tile art**, selected
by `entry_015D`'s global tile ID and drawn through `entry_0219`'s
depth-appropriate sprite slots (§Unit `131` above).

This also explains `WALLDEF`'s per-region ID remap (§`WALLDEF*.DAX` in
`analysis/data-formats.md`, from two passes ago): region-local wall-texture
IDs get a per-region constant added once they cross a threshold — turning
them into exactly the **global 1-286 tile ID space** `entry_015D` classifies
here. The remap step in the loader and the classification step in the
blitter are two ends of the same design, now both traced.

**`func_0x000018cf` — RESOLVED, and it's the whole point of this correction
(2026-08-21).** Everything from here down corrects the previous entry, which
treated `func_0x0000XXXX` names as unresolved load-time placeholders needing
either a found overlay manager or a live trace. **They were never
unresolved.** `func_0x000018cf`'s raw bytes at its one call site
(`entry_0219`, unit `131`, unit-relative `0x303`) are
`9a 2f 00 8a 01` — `CALLF 0x018A:0x002F`, a **plain, literal, fully-resolved
far call**, not a placeholder. `0x018A` is unit `18A`'s own nominal segment,
and offset `0x2F` is exactly its **thunk #3** (`work/overlay_map.json`,
`entry_count=4`, `thunks=[685, 65535, 59, 349]` — thunk 3's target `349` =
`0x15D`). So `func_0x000018cf` *is* `entry_015D` — `entry_0219` calls straight
back into the tile-classifier/blitter already fully documented above.
There is no separate, undiscovered pixel-copy routine to find; the dungeon
render pipeline this whole unit-`131`/`18A` investigation traced is complete.

**Why this was missed for so long, and what it corrects:** Ghidra's
disassembly listings label every `CALLF` whose segment operand isn't a small
number it recognises as `"0x0000:XXXX"` — but `XXXX` there is not a raw
offset needing a segment patched in. It is `realSegment × 16 + realOffset`,
a **flattened linear address**, computed from bytes that were already
completely resolved on disk. Proof: `func_0x00007242` (this project's
generic block-move helper, called dozens of times from every unit examined
this session) shows as `func_0x00007242` everywhere — and its raw bytes
decode to `CALLF 0x05BB:0x1692`, where `0x05BB × 16 + 0x1692 = 0x7242`
exactly. Reading `START.EXE` at the resulting file offset
(`0x05BB0 + 0x1692 + 0x3B0 = 0x75F2`) finds real, sensible code — a classic
Pascal `Move`: load far source/dest pointers and a count off the stack,
`CMP`/`JAE` to choose forward or backward `REP MOVSB` for overlap safety.
Every `func_0x0000XXXX` name used throughout this file (`func_0x00007242`,
`func_0x00005e0d`, `func_0x000061e4`, `func_0x000061fe`, `func_0x00005f14`,
`func_0x0000193c`, `func_0x00001928`, …) is the same story: a fully-resolved
literal call, recoverable by reading the `CALLF`'s 4 operand bytes directly
instead of trusting the decompiler's display. None of them needed dynamic
tracing — the mistake was reading Ghidra's label as raw bytes when it is a
derived value.

This **does not** retroactively cast doubt on unit `18E`'s own internal
functions (`entry_1EBA`, `FUN_0000_1fa3`, etc.) — those addresses were
independently confirmed via thunk-table targets and `RETF` boundaries within
that unit's own code, a different and still-valid method. The confusion is
specific to *external* `CALLF`s whose flattened linear value happens to look
like a plausible small offset.

## The resident Pascal RTL primitives, identified (2026-08-21)

Direct payoff of the correction above: every `func_0x0000XXXX` name this
project has been using informally all session (inferred only from calling
convention and usage pattern) is a real, findable routine in `START.EXE`'s
resident segment `0x05BB`. Read by hand, the same way `func_0x00007242`'s
`Move` body was confirmed. A new tool, `work/resolve_calls.py`, automates the
"decode this unit's `CALLF`s to real segment:offset" step for any unit (it
flags and drops implausible segments from its own byte-scan — see its
docstring — so treat unfamiliar/huge segment values it might show as noise,
not new resident code).

| name | resolved at | confirmed role | evidence |
|---|---|---|---|
| `func_00007242` | `05BB:1692` | **`Move`, overlap-safe** | loads far src/dest + count off the stack; `CMP`/`JAE` picks forward or backward `REP MOVSB` |
| `func_00005e0d` | `05BB:025D` | **`Move`, no overlap check** | same far-ptr/count loading, straight `REP MOVSB`, no direction test — the "fast path" sibling |
| `func_00007265` | `05BB:16B5` | **`FillChar`** | far dest + count + one fill byte off the stack, `REP STOSB` |
| `func_00005ed9` | `05BB:0329` | **`GetMem` (heap allocator)** | calls a near allocator helper, checks a `HeapError`-style function-pointer vector at a fixed `DS` address on failure — the standard Turbo Pascal heap-overflow hook pattern |
| `func_00005f14` | `05BB:0364` | **heap deallocator (`FreeMem`/`Release`)** | reads a size and a far block pointer off the stack, calls a near "release" helper — matches `entry_25F1`'s use exactly (§`entry_24ED`/`entry_25F1` above) |
| — | `05BB:13EF` | **`Assign`** — CONFIRMED (2026-08-22) | writes the `0xD7B0` file-record magic that `Reset`/`Rewrite` then test |
| — | `05BB:141D` | **`Reset`** (open for read) — CONFIRMED (2026-08-22) | `MOV AH,0x3Dh`, DOS open |
| — | `05BB:1426` | **`Rewrite`** (create) — CONFIRMED (2026-08-22) | `MOV AX,0x3C00`, DOS create |
| — | `05BB:1508` | **`BlockRead`** — CONFIRMED (2026-08-22) | `MOV BL,0x3Fh` (the sibling entry uses `0x40` and is `BlockWrite`) |
| — | `05BB:1570` | **`Seek`** — CONFIRMED (2026-08-22) | takes a file record and a 32-bit position |
| — | `05BB:149E` | **`Close`** — CONFIRMED (2026-08-22) | file-record validity check then DOS close |
| — | `05BB:162C` | **`Erase`** — CONFIRMED (2026-08-22) | `MOV AH,0x41h`, DOS delete; the `.SPC` saver calls it when the list is empty |
| `func_00006844` | `05BB:0C94` | **`Random(n)`** — CONFIRMED (2026-08-22) | it is `rawRandom() mod n`: the near sub-call is `05BB:0CE3`, a 32-bit LCG over the seed at `DS:0x438A`/`0x438C` whose multiplier is `0x08088405` (low word `0x8405` read literally at `CS:0x0D19`, high half built by the `SHL`/`ADD` chain) followed by `ADD AX,1 / ADC DX,0` — Turbo Pascal's `Random` exactly. Found from the other end: ECL opcode `0x08` is the scripts' random roll and calls it. The earlier "plausibly a modulo-based timing or index check" reading was the right instinct about the `DIV` and wrong about the purpose. |

**The RNG is a porting constraint, not trivia.** `AGENTS.md` §Conventions holds
game logic to bit-exact fidelity in anything the player can observe, and every
die roll in the game goes through this LCG. The port must reproduce
`seed := seed * 0x08088405 + 1` on a 32-bit seed and take `seed mod n`, with
the same seeding, or no combat sequence will match the DOS original.

This directly upgrades several earlier "presumably X" readings to confirmed
fact: `entry_24ED` (§`entry_24ED`/`entry_25F1`) really is GetMem+FillChar
composed into a record allocator, and `entry_25F1` really is its matching
deallocator — exactly as inferred from naming and usage, now backed by the
actual machine code rather than the pattern alone.

## Unit `198` — a font/glyph renderer, not the `GAME.OVR` loader (2026-08-21)

A byte search for the `GAME.OVR` string (looking for whatever code opens the
overlay file, on the theory that it might also install the real `INT 3Fh`
handler — Open question 1) finds it as a Pascal `ShortString` in `START.EXE`
at file offset 7601, **immediately** after unit `198`'s own thunk table ends
at 7589 (12 zero-padding bytes between). That positional match is real — the
six `CALLF`s this project traced back to unit `198` in earlier turns
(`0x0554`, `0x05C3`, `0x0B60`, `0x0C2D`, `0x0C83`, `0x0C9A`) are exactly its
own `entry_0554`/`entry_05C3`/`entry_0B60`/`entry_0C2D`/`entry_0C83`/`entry_0C9A`.
But reading the unit's actual code shows it is **not** a file loader: its
largest routine, `entry_006D`, branches on `DS:0x497E` (the same video-mode
selector unit `18E` uses) and draws 8-bytes-per-glyph bitmap data into EGA
planes via the identical `out(0x3C4,2)`/`out(0x3C5,...)` pattern — this is a
**character/font renderer**, reading glyph data from a table at
`DS:0x5D7E` that gets populated (`entry_000B`) by a `Move` from segment
`0x1D7`. So the `GAME.OVR`/`pool.cfg` strings most likely belong to
`START.EXE`'s own main code, positioned right after the last unit's resident
block by link order rather than by ownership — a coincidence, not a lead.

Secondary finding worth keeping despite the miss: segment `0x1D7` (source of
unit `198`'s font-table copy here, and also seen as an argument to `Move` at
the very start of unit `18E`'s `entry_011B` reading its first header field)
looks like a shared, fixed **file-read buffer** — a plausible Pascal
buffered-`Read` primitive used by more than one loader — but confirming that
needs tracing what loads `DS`/`ES` with `0x1D7` before those calls, an
argument-source search rather than a call-target one, and wasn't attempted.

**Net effect on Open question 1:** two reasonable static leads (the `AH=25h`
scan, and this string-proximity search) have now come up empty for finding
where the real `INT 3Fh` handler installs. Neither rules out a third static
approach existing, but this is a fair point to flag that continuing to guess
search terms has diminishing odds — a systematic read of `START.EXE`'s own
un-disassembled majority (86 % uncovered by the recursive-descent pass) or a
dynamic breakpoint are the remaining honest options.

## Units `045` and `020` — the `ECL` interpreter (2026-08-22)

Found by the same method as unit `131`: a byte search for the `ECL` short
string constant. The format writeup — container, instruction encoding, block
layout, coverage — is in `analysis/data-formats.md` §`ECL*.DAX`; this entry
records the routines and how they fit together.

The interpreter is split across the two units. Unit `020` (the largest in the
game, 93 functions) holds the execute loop, the dispatcher and all 61 opcode
handlers; unit `045` holds the loader and the operand machinery.

- **`entry_0353`** (unit `045`) — the loader. Builds `ECL<n>.dax`, reads it,
  copies from source offset 2 (skipping a 2-byte header) into a `FillChar`-
  zeroed 7,680 B buffer at the far pointer held in `DS:0x493F`.
- **`020:35DB`** — the **execute loop**. Takes the start PC as its one
  argument, stores it at `DS:0x494E`, then repeats { fetch the opcode byte at
  `[DS:0x493F] + PC + 0x6700`, save it to `DS:0x6D45`, call the dispatcher }
  until `DS:0x4390` or `DS:0x4960` goes non-zero. Nine call sites, each
  passing one of the five entry points from `DS:0x4944`-`0x494C`.
- **`020:32DF`** — the **dispatcher**: a `CMP AX,n / CALL handler` chain over
  opcodes `0x00`-`0x3D`, with an illegal-opcode reporter at `020:356D` for
  anything else. `0x1F` is the one value in range with no handler. The full
  map is `HANDLER` in `work/ecl.py`; it is the worklist for opcode semantics.
- **`045:0000`** (`entry_0000`) — the **operand decoder**, `entry_0000(n)`.
  Reads `n` operands into three parallel 64-entry tables indexed by operand
  number: `DS:0x6DCB` (type), `DS:0x6E4B` (value), `DS:0x6E0B` (extra); handles
  the extra byte for types 1/2/3/0x81 and the inline packed text for 0x80; and
  leaves the PC on the next opcode. Ghidra cannot decompile it — hand-traced.
- **`045:013F`** (`entry_013F`) — the **evaluator**, `entry_013F(i)`. Type 0 is
  an immediate and returns `value`; 1/3/0x80 read memory via `entry_0E2E`;
  2/0x81 return the address itself.
- **`045:06BE`** (`entry_06BE`) — `(extra << 8) + value`. Every jump target,
  gosub target and absolute address in the language goes through it.
- **`045:01C8`** — **block init**: `PC := 0x9900`, then five
  `entry_0000(1)` + `entry_06BE` pairs that read the block's 20-byte header
  into `DS:0x4944 / 0x4946 / 0x4948 / 0x494A / 0x494C`, the five script entry
  points.
- **`020:0B1A`** — an operand-count classifier, and a **trap**. An earlier pass
  took it for the interpreter's front end and its compare chain for the
  authoritative operand-count table. It is neither: it is called only by the
  conditional-skip path `020:0C5A`, and it disagrees with the handlers on five
  opcodes (`0x0C` 2 vs 3, and `0x15`/`0x25`/`0x26`/`0x2B` 0 vs variable). That
  is a latent bug in the shipped interpreter, dormant because no script guards
  one of those five with a conditional. The same earlier note guessed that a
  "further-fragmented continuation (`FUN_0000_047A`) presumed to hold the real
  per-opcode jump table" lay behind it; the real dispatcher is `020:32DF`,
  reached from `020:35DB`, and there is no jump table anywhere — both the
  dispatcher and the classifier are compare chains.
- **`DS:0x6D36`** — head of the GOSUB stack: a linked list of 6-byte nodes
  (`[0]` = return PC, `[2..5]` = far pointer to the next), pushed by `045:1991`
  and popped by `020:0A6B`, allocated and freed with the resident `GetMem`
  /`FreeMem` pair at `05BB:0329` / `05BB:0364`.

**Overlay call convention, restated because it bit this pass.** `CALLF
0x0045:0x002A` is not unit `045` offset `0x2A`. Each unit's segment opens with
a thunk table at `+0x20`, five bytes per slot, so the offset is
`0x20 + 5*slot` and the real target is `overlay_map.json`'s `thunks[slot]` —
here slot 2, target `0`, i.e. `entry_0000`. `work/resolve_calls.py` already
encodes this; reading the offset as an address lands mid-instruction and the
routine you "find" is unrelated. This is how the interpreter's four hot calls
decode: `0x2A`→`045:0000`, `0x25`→`045:013F`, `0x52`→`045:06BE`,
`0x9D`→`045:1991`.

## Unit `069` — the central game-initialisation routine (2026-08-21)

Found while chasing the `ITEMS` master-table filename (it turned out to be
data for a different caller, not consumed by this routine directly — a dead
end for that specific goal, noted honestly rather than skipped over). What
`entry_002D` (unit `069`'s only real function, 1,720 B, essentially the whole
unit) actually is turned out to be far more valuable: **the routine that
allocates and initialises nearly every resident buffer and global this
session has been reverse-engineering piecemeal, all in one place.** It is
independent, first-party confirmation of a long list of prior findings, plus
several genuinely new facts:

**Buffer allocations** (`GetMem`/`func_00005ed9`, confirmed
`analysis/executables.md` §resident Pascal RTL primitives), address and size
both read directly, not inferred:

| address | size | identity |
|---|---|---|
| `DS:0x4937` | `0x800` = 2,048 B | the `ITEMS` master table buffer — confirms `analysis/data-formats.md`'s "`2048 = 2050 - 2`, not a plain 63 B record array" note: it really is allocated as a flat 2,048 B block, not record-shaped |
| `DS:0x493B` | `0x400` = 1,024 B | unidentified — not traced to a consumer this pass |
| `DS:0x493F` | `0x1E00` = 7,680 B | the `ECL` script buffer — matches the `FillChar` size confirmed in `entry_0353` two turns ago exactly |
| `DS:0x5D7E` | `0x588` = 1,416 B | the font/glyph table unit `198`'s `entry_000B` fills |
| `DS:0x69B6` | `0x924` = 2,340 B | the `WALLDEF` buffer — `2,340 = 3 × 780`, so **a region can carry up to 3 `WALLDEF` blocks**, matching the largest observed file (`WALLDEF3/4/5.DAX`, `analysis/data-formats.md`) |
| `DS:0x69BA` | `0x400` = 1,024 B | the `GEO` buffer — `1,024`, not `1,026`: confirms the 2-byte header is genuinely excluded from the working copy, not just skipped during the one copy this session already traced |

**Dirty-row present tables** (`FillChar`-cleared here): `DS:0x4988` (168 B),
`DS:0x4A30`/`0x4B80`/`0x4CD0` (336 B / `0x150` each) — sizes match unit
`18E`'s `entry_1BAB` exactly (`analysis/executables.md` §Blit-time
transparency), confirming that routine's dirty-row table dimensions from the
allocation side instead of the consumption side.

**Unit `18A`'s tile-sheet cache**: `DS:0x5D98`, cleared to 20 B (`0x14`) —
matches the 5-entry × 4-byte far-pointer cache `entry_003B`/`entry_015D`
already established (`analysis/executables.md` §Unit `18A`).

**New: the party's starting position and facing, in the clear:**
`DS:0x6A0B = 0x0F` (row 15), `DS:0x6A0C = 1` (column 1),
`DS:0x6A0D = 6` (facing) — the exact three globals identified as the party's
live position/facing state two turns ago (`analysis/data-formats.md` §`GEO*.DAX`
regions 2/3), now with confirmed starting values. `0x6A0D = 6` is even,
consistent with the "cardinal facings only" finding for unit `131`'s
`entry_0614`.

Also confirmed: `DS:0x6A0A = 0` at init — the mode flag that gates
`entry_0614`'s fallback to `entry_0000` starts cleared (normal rendering
path active from the start, as expected).

**Not resolved:** the specific consumer of the `ITEMS` filename string that
led here in the first place, `DS:0x493B`'s purpose, and roughly two dozen
more single-byte/word flags this routine initialises
(`0x4956`-`0x4961`, `0x52D0`-`0x52D6`, `0x6A72`, `0x82A3`-`0x82AF`,
`0x54DA`/`0x54DB`, `0x6D2E`/`0x6D2F`, `0x6CCE`/`0x6CD0`, and more) whose
existence and initial value are now on record but whose individual meaning
is not. A ~90-line loop near the end (reading two far pointers from a table
at `DS:0x5E80` and writing fixed byte patterns into their `+0x11`-relative
data, branching on the video-mode selector `DS:0x497E` the same way unit
`18E` does) looks like it is pre-seeding two special image records —
plausibly the title screen's "cold"/"warm" variants this project's `build/`
directory already names — but this was not traced to confirm.

## The `DS:0x6A78` procedure-pointer table (2026-08-22)

Found from the residue end: `work/dbmap.py` reported three indirect far calls
as the only code-shaped bytes the reassembly could not explain, all in unit
`0E2` — `CALL FAR [0x6A78]` at +0D63 and +30F8, and `CALL FAR [DI+0x6A78]` at
+0EA3. The indexed form is the tell.

`DS:0x6A78` is the base of a **34-entry array of far procedure pointers**,
indexed by the byte at `DS:0x6779` (`0E2:0E9D` does `DI = [0x6779] << 2` right
before the call). The whole array is written at run time by `0E2:33CC`, a
straight run of `MOV AX,imm / MOV DX,0x00E2 / MOV [slot],AX / MOV [slot+2],DX`
quadruples, one per slot. Every immediate is a unit `0E2` **thunk offset**, so
resolving them through the `+0x20`, 5-bytes-per-slot table gives 27 distinct
targets across the 34 slots — several slots repeat (`thunk 21` appears five
times, `thunk 22` four).

Two things follow.

**The indirect calls hide no code.** All 34 targets are thunk entries, which
the reassembly walk already seeds from, so every one is disassembled. Verified
mechanically against the emitted listings: 27/27 distinct targets are
instruction starts.

**Slot 0 is a mode hook.** It is the only slot anything else writes.
`051:0071` — the routine ECL opcode `0x24` invokes — repoints it at
`096:20AE`, while `051:0040` and `0E2:33CC` itself set it back to `0E2:0A88`.
So the table is fixed except for its first entry, which selects between a unit
`0E2` implementation and a unit `096` one. Which two behaviours those are is
not established; naming them needs those routines read.

This also refines a negative result recorded the same day. `dbmap.py` finds no
`case`/dispatch offset tables anywhere in the code segment, and that is true —
but it does not mean the game has no dispatch tables. This is one, built in
DGROUP at run time by explicit assignments, where no static-data scan would
ever see it.

## Open questions

1. Which Turbo Pascal version exactly, and where does the real overlay manager
   (the one that replaces the INT 3Fh error stub) live? **Narrowed
   (2026-08-21):** the *calling* half of this is now resolved as a side
   effect of §Who calls `entry_011B`? above — inter-unit calls are plain
   `CALLF <nominalSegment>:<offset>` instructions landing on the resident
   `CD 3F` thunk, no indirection layer, confirmed by grepping raw disassembly
   for `lcall 0x18e, *`. What's still unresolved is the *handler* side: a
   byte-complete scan of `START.EXE` for `mov ax,0x253f` (the DOS "set
   interrupt vector" call used to install the error stub) finds **exactly the
   two already-documented sites** — install and shutdown-restore — and no
   third site, so the real handler is not installed via a second `AH=25h`
   call. Either it's installed by a direct vector-table write (not yet
   searched for — no unique byte signature to grep), or it's reached some
   other way not yet identified. (The previous entry's `unit019`-trampoline
   lead was itself an artifact of imprecise decompiled-C far-call modelling,
   corrected in §Who calls `entry_011B`?.)

   **The *other* half of this question — where the `func_0x0000XXXX` resident
   helpers actually live — turned out to already be resolved, and the
   "fixup table" reasoning above was wrong (2026-08-21).** `CALLF 0x0000:XXXX`
   in Ghidra's disassembly is **not** a load-time placeholder — it is Ghidra
   displaying a flattened linear address (`realSegment × 16 + realOffset`)
   for an *already fully-resolved* literal far call. `func_0x00007242`'s raw
   bytes decode to `CALLF 0x05BB:0x1692` (`0x05BB × 16 + 0x1692 = 0x7242`,
   exactly the displayed offset), and reading `START.EXE` at the
   corresponding file position finds a real Pascal `Move` intrinsic. Full
   correction and the general rule (works for every `func_0x0000XXXX` name
   used anywhere in this file) is in §`func_0x000018cf` — RESOLVED under
   Unit `18A` above, found while resolving that exact call.

   The offset-list structure this entry previously described **is real and
   correctly decoded** — unit `18A`'s 50-byte fixup table genuinely is 25
   u16LE entries, one per `CALLF`, each pointing at `CALLF address + 3` — but
   since those `CALLF`s turn out not to need a value patched in, the table's
   actual purpose at load time is now unclear rather than confirmed (a
   linker-era relocation record kept but unused at runtime is one
   possibility; not chased further). What *is* now closed is the practical
   question this was blocking: every resident helper's real location is
   recoverable by reading its `CALLF` operand bytes directly, no dynamic
   tracing required. What remains genuinely open is only the narrower
   original question — which code *installs* the real `INT 3Fh` handler
   (still not found by the `AH=25h` scan above).
2. The `+0x0E` field of the unit header.
3. ~~Where is the EGA palette programmed~~ **RESOLVED** — nowhere; the game
   never programs one. See §The palette question above and
   `analysis/dos-oracle.md` §8. `PORTING.md` §Open risks 1 is closed.
4. ~~The picture blit routine in unit `18E`~~ — found (`entry_19A5`) and the
   packed→planar expander with it (`entry_02AD`). ~~The 9 unknown
   image-header bytes~~, ~~whether transparency exists at blit time~~ and
   ~~`entry_1618`'s role~~ are now **RESOLVED** — §The 9 unknown header bytes,
   §Blit-time transparency, §`entry_1618` above (confirmed a horizontal
   mirror by index arithmetic, no rendering needed). `entry_1BAB` turned out
   to be the dirty-row screen-flush routine, not a transparency site — that
   lead was wrong, the Graphics Controller writes it pointed at were a red
   herring. ~~Which transparent-colour index `.PIC` overlay frames actually
   pass~~ is now also **RESOLVED** — all 19 real callers read directly from
   disassembly, see §Who calls `entry_011B`? above: colour 0 in 6 of 7
   mask-requesting calls, colour 13 in the seventh, and 12 of 19 callers
   don't request a mask at all. ~~`entry_1EBA`'s exact colour-substitution
   mechanism~~ is now **RESOLVED** too — see §`entry_1EBA` above: it is one
   1,587-byte routine (Ghidra had split it into nine), doing exact 16-pair
   palette substitution across all 4 EGA planes from two caller-supplied
   colour lists. Still open from unit `18E`: `entry_011B`'s `[BP+0xE]`
   lookup key resolves to a call into the *shared runtime* (not, as an
   earlier version of this note wrongly said, unit `18E`'s own code — see the
   correction in §Who calls `entry_011B`?), and that resident helper's
   identity is unknown.
5. `main` and the game loop. ~~The ECL script interpreter~~ is **RESOLVED
   (2026-08-22)** as machinery — execute loop, dispatcher, operand decode,
   evaluator, block layout, all 61 opcode handler addresses; see §Units `045`
   and `020`. What remains is **opcode semantics**: 12 opcodes are read
   (control flow and text), the other ~45 have a handler address and an
   operand count but no established meaning. That is a bounded worklist now,
   not an open question about the format.
