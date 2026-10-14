# Pool of Radiance data formats (verified, `work/expanded/`)

All offsets/fields below were verified against actual file bytes, not guessed.
"LE" = little-endian. All files are ARC-expanded copies in `work/expanded/`
(rebuild + re-verify with `sh work/stage.sh`).

Status legend: **RESOLVED** = a decoder round-trips it and the result has been
looked at. **TBD** = unproven, do not build on it.

---

## `.ARC` — the distribution archives — **RESOLVED**

`DISKA.ARC`, `DISKB.ARC`, `DISKC.ARC`, `SAVE.ARC`. Classic SEA/PKARC. Entry
header is 29 B, verified against `DISKA.ARC` @ 0x00:

```
1a 08 | 38 58 38 44 31 2e 44 41 58 00 5e 5e 5e | 2f 1b 00 00 | 84 11 | ee 69 | 61 da | ef 25 00 00
 ^  ^    "8X8D1.DAX\0" + unzeroed padding        ^ csize=6959  ^date  ^time   ^crc    ^ usize=9711
 |  method 8
 0x1A entry magic
```

```
0x00 u8      0x1A            entry magic
0x01 u8      method          0 = end-of-archive marker
0x02 char13  name            NUL-terminated; trailing bytes are NOT always zeroed
0x0F u32LE   compressedSize
0x13 u16LE   DOS date
0x15 u16LE   DOS time
0x17 u16LE   CRC-16/ARC      of the *expanded* data (poly 0xA001, init 0)
0x19 u32LE   originalSize
0x1D ...     data
```

Archive ends with the 2-byte marker `1A 00`.

Verified over all four archives: **257 entries**, methods **2** (×9),
**3** (×3), **4** (×5), **8** (×237), **9** (×3); every expanded file matches
its stored size *and* CRC — `python3 work/arcverify.py` → `257 entries, 257
OK, 0 bad`.

Method meanings (from the XADMaster/unar reference, `work/arc_ref_*`):

| method | name | pipeline |
|---|---|---|
| 2 | None | stored raw |
| 3 | Packed | RLE90 |
| 4 | Squeezed+packed | Squeeze prefix code → RLE90 |
| 8 | Crunched+packed (LZW) | `0x0C` marker, LZW(4096 codes, clear 256) → RLE90 |
| 9 | Squashed | LZW(8192 codes, clear 256) |

RLE90: `90 00` = literal `90`; `90 c` (c≥2) = previous literal c−1 times;
`90 01` = invalid. Bitstreams are LSB-first within each byte. The LZW decoder
emits the **full string of the code just read** (for code == next free entry:
the entry is added first); `string(old)+firstbyte(new)` is the *table add*.
Swapping those two in the first port of `work/arcunpack.py` failed the CRC of
the first method-8 file.

**Tool note:** 7-Zip 26.02 cannot open ARC (`Can't open as archive`).
`unar` 1.10.7 handles all four (macOS). On the Windows machine, pure-Python
`work/arcunpack.py` expands all four (257/257 CRC-clean, 2026-08-21); it is the
`unar` replacement in `stage.sh` there. `PKUNPAK.EXE` on disk 1/2 remains the
authentic unpacker — use it under DOSBox-X/86Box if a byte-exact second
opinion is ever needed.

## `DISK<target><source>` — install manifests — **RESOLVED**

24 plain-text files, CR (`0x0D`) separated, terminated by `0x1A`. Example,
`DISK1A` (130 B):

```
8x8d1.dax  cpic1.dax  dungcom.dax  ecl1.dax  geo1.dax  item1.dax
mon1cha.dax  mon1itm.dax  randcom.dax  sprit1.dax  walldef1.dax<0x1A>
```

- `<target>`: `1`–`8` = the eight floppy install disks; `H` = hard disk
  (`DISKHA`+`DISKHB`+`DISKHC` = 92 entries); `O` and `S` = the two boot-disk
  layouts, differing by **exactly one entry** — `DISKOB` lists `game.ovr`,
  `DISKSB` lists `start.exe`, everything else identical.
- `<source>`: `A`/`B`/`C` = which of `DISKA.ARC` / `DISKB.ARC` / `DISKC.ARC`
  the listed files come from.

Verified: every name in every manifest is a member of the archive its suffix
names — **24/24 consistent**. `DISK1B` (`GAME.OVR`) is the only manifest in
upper case; all others are lower case.

**Coverage.** The union of all 24 manifests is **92 names**, and the `H` set
alone is those same 92 — so the eight floppy targets partition exactly the
files the hard-disk target installs. The remaining **166 of 257** archive
members are never named in any manifest:

| never named | n |
|---|---|
| `PIC*.PIC` | 62 |
| `HEAD*` | 41 |
| `DISK*` manifests themselves | 24 |
| `BODY*` | 21 |
| `CHRDATA*.SAV/.ITM/.SPC` | 16 |
| `ITEMS`, `SAVGAMA.DAT` | 2 |

`INSTALL.EXE` is the consumer. Both its manifest-selection logic and how it
places these 166 unnamed files are **TBD** (read it in step 1 of `AGENTS.md`
§Next steps).

---

## `.DAX` — the Gold Box container — **RESOLVED**

89 files, 1,044 blocks. `work/dax.py` verifies every one.

```
[u16LE tableSize]                    # bytes; always 9 * blockCount
[blockCount x 9-byte block record]:
    u8    blockId
    u32LE offset                     # relative to end of header (2 + tableSize)
    u16LE unpackedSize
    u16LE packedSize
[packed blocks, contiguous, in table order]
```

Worked example, `ICON.DAX` (1,287 B), bytes quoted from file:

| @ | raw | id | offset | unpacked | packed |
|---|---|---|---|---|---|
| 0x02 | `00 00 00 00 00 31 01 e2 00` | 0x00 | 0 | 305 | 226 |
| 0x0B | `80 e2 00 00 00 31 01 d7 00` | 0x80 | 226 | 305 | 215 |
| 0x14 | `01 b9 01 00 00 31 01 c5 00` | 0x01 | 441 | 305 | 197 |
| 0x1D | `81 7e 02 00 00 31 01 b9 00` | 0x81 | 638 | 305 | 185 |
| 0x26 | `02 37 03 00 00 31 01 ca 00` | 0x02 | 823 | 305 | 202 |
| 0x2F | `82 01 04 00 00 31 01 ce 00` | 0x82 | 1025 | 305 | 206 |

`tableSize = 0x0036 = 54 = 6 × 9`; data starts at `2 + 54 = 56`;
`56 + 1231 = 1287` = file size.

Invariants checked on all 89 files: first offset is 0, `off[k+1] == off[k] +
packed[k]`, `2 + tableSize + sum(packed) == filesize`.

**Block ids.** 206 distinct ids across the set; 224 blocks have the high bit
set. In `ICON.DAX` the ids pair as `0x00/0x80`, `0x01/0x81`, `0x02/0x82` — the
high bit marks a **paired variant** of the same logical block (two states of
one icon). Whether the same rule holds for every family is **TBD**.

## Block payload codec — **RESOLVED**

PackBits-style RLE on signed control bytes:

```
n = int8(ctrl)
n <  0 : emit the next single byte (-n) times
n >= 0 : copy the next (n + 1) bytes literally
```

**1,044 of 1,044** blocks decode to exactly their declared `unpackedSize`
(`python3 work/dax.py`). Note this codec applies *inside* `.DAX` only —
`.PIC`, `BODY*` and `HEAD*` store their pixels raw.

## Image header + pixel format — **RESOLVED**

The same 17-byte header prefixes `.PIC` frames, the bare `BODY*`/`HEAD*` files
and every image-carrying `.DAX` block:

```
u16LE height          rows
u16LE widthBytes      width_px = widthBytes * 8;  bytes/row = widthBytes * 4
u32LE 0               zero except TITLE.DAX blocks 0x01/0x02, which carry 1
u8    frameCount      repeat count for multi-element blocks (see below)
8 B   cgaRemap        16-entry x 4-bit CGA colour-reduction table (see below)
```

Payload: `height * widthBytes * 4` bytes, **4 bits per pixel, high nibble is
the left pixel**, values indexing the standard 16-colour EGA palette.

**Confirmed from the DOS code** (2026-08-21): `entry_02AD` in overlay unit
`18E` reads `srcByte >> 4` for even pixels and `srcByte & 0x0f` for odd ones,
then expands each nibble into four EGA planes. See
`analysis/executables.md` §Unit 18E. The planar form exists only in memory —
the file is always packed.

Quoted headers:

| source | raw first 8 B | geometry |
|---|---|---|
| `BODY1` | `30 00 0b 00 00 00 00 00` | 88 × 48 |
| `HEAD0` | `28 00 0b 00 00 00 00 00` | 88 × 40 |
| `PIC0.PIC` frame 0 | `58 00 0b 00 00 00 00 00` | 88 × 88 |
| `TITLE.DAX` block 0x01 | `c8 00 28 00 01 00 00 00` | 320 × 200 |
| `ICON.DAX` block 0x00 | `18 00 03 00 00 00 00 00` | 24 × 24 |
| `CHEAD.DAX` block 0x00 | `0a 00 03 00 00 00 00 00` | 24 × 10 |

`size == 17 + height * widthBytes * 4` holds **exactly** for 441 of the 1,044
`.DAX` blocks. A further **50** are arrays of *N* same-geometry elements after
a single header — e.g. `8X8D1.DAX` block 0x01: `unpacked = 2257`,
header says 8 × 8 px (32 B/element), `(2257 - 17) / 32 = 70` tiles exactly.

Confirmed by rendering, not by arithmetic alone: `work/gbimage.py` writes PNGs;
`TITLE.DAX` block 0x01 is the 320×200 SSI / AD&D title screen
(`work/probe/TITLE_01_0.png`), `BODY1` is an armoured torso, `HEAD0` a blond
head, `PIC11.PIC` a gravestone with skeletal hands rising across 8 frames.

**RESOLVED (2026-08-21)** — the 9 trailing header bytes split in two, per
`entry_24ED`/`entry_02AD` in overlay unit `18E` (`analysis/executables.md`
§Unit `18E`): byte 0 is a **repeat count** (consumed by all three video-mode
branches of `entry_02AD` as the multi-element loop bound — e.g. `8X8D1.DAX`
block 1's `0x46` = 70, matching the already-known "70 × 8×8 tiles"), and the
remaining 8 bytes are a **16-entry, 4-bit CGA colour-reduction table**
(`entry_007B`, indexed by the raw 4 bpp source nibble, consumed only by
`entry_02AD`'s `DS:497E == 0` / CGA branch — the EGA branch this project ports
never reads it). Re-reading the byte examples already quoted here confirms it:
every one decodes to `frameCount = 1` + 8 nibble-pairs whose 16 values all fall
in **0-3**, exactly the range a 16→4-colour table requires, checked against
all 778 headers in `work/expanded/` (`python3 work/imghdr.py` → `778 headers,
778 OK, 0 bad`):
`BODY1` → count `01`, remap `01 11 22 13 13 11 32 33`; `HEAD0` → count `01`,
remap `01 11 22 23 03 11 32 31`; `PIC0.PIC` → count `01`,
remap `00 11 22 21 02 11 12 33`. **Consequence for the port:** the EGA-only
port needs `frameCount` (for multi-tile blocks like `8X8D*`) but can ignore
`cgaRemap` entirely — it is CGA-mode compatibility data with no EGA reader.

## `.PIC` — pictures with animation frames — **RESOLVED**

62 files.

```
[u8 frameCount]
[frameCount x 3893-byte frame]:
    u32LE duration       frame display time, in units of 70 ms (below)
    17 B  image header   always 88 x 88 in the shipped set
    3872 B pixels        88 x 88 at 4 bpp
```

Verified: **62/62** files satisfy `size == 1 + frameCount * 3893`. Shipped
sizes are 3,894 / 7,787 / 11,680 / 15,573 / 19,466 / 23,359 / 27,252 / 31,145 B
= 1 to 8 frames.

Frame 0 is the full base picture; frames 1..n are **sparse overlays** — mostly
colour 0 with only the moving part drawn (verified visually on `PIC11.PIC`).

### The `u32` frame tag is the frame's duration — **RESOLVED (2026-08-22)**

The animation driver is `11D:0251`. A loaded picture is a directory at
`DS:0x6A1C`: a count byte, a flag byte, then 8-byte slots of
`{u32 duration, far pointer to the decoded bitmap}` — the same structure
`12B:00A8` builds for `SPRIT` (below), because it is the same loader.
`DS:0x6A1D` holds the current frame, 1-based, wrapping back to 1 when it passes
the count (`11D:02B2`).

```
11D:027C   LES AX,[DI+0x6A16]     ; the frame's u32 tag  (0x6A1C + 8*i - 6)
11D:0288   MOV CX,7 / XOR BX,BX
11D:028D   CALLF 05BB:0279        ; a 32x32 multiply -> tag * 7
11D:029B   <elapsed> := now - lastFrameChange
11D:02A1   if elapsed > tag * 7:  advance the frame, reset lastFrameChange
```

`now` comes from `198:0AF0`, which reads the system time and folds it into a
single 32-bit count of **hundredths of a second** — `hour * 0x57E40` (360,000)
`+ minute * 0x1770` (6,000) `+ …`. So the unit is 7 hundredths and

> **frame duration = tag × 70 ms.**

Shipped values run **0 to 20**, not `0x00`-`0x0F` as an earlier note recorded
from a partial sample — so 0 ms to 1.4 s. A tag of 0 makes `elapsed > 0` true
on the next tick, i.e. a single-tick frame. Examples: `PIC0.PIC` is four frames
of a flat 140 ms; `PIC114.PIC` holds 910 ms then flicks through two 70 ms
frames; `PIC117.PIC` runs 1120, 350, 280, 840, 700, 980, 1050 ms.

**The port needs this**: frame pacing is observable, and the timings are
per-frame rather than a single rate.

**RESOLVED (2026-08-21):** transparency at blit time is real but **not**
hardcoded to colour 0 — `analysis/executables.md` §Unit `18E` traces a general
colour-key mechanism: `entry_02AD` builds a 1-bit-per-pixel mask (in a buffer
the loader allocates on request) by comparing every decoded pixel against a
caller-supplied "transparent index" parameter, and the blit/composite routines
(`entry_08F5`, `entry_0D9F`, `entry_1EBA`, `FUN_0000_27a6`) all apply it the
same way: `dest = (dest & mask) | src`. Which index each `.PIC` overlay frame
actually passes is decided by `entry_011B`'s caller outside unit `18E`, and
that is now resolved too (2026-08-21): all 19 real call sites into
`entry_011B` were read from raw disassembly (`analysis/executables.md` §Who
calls `entry_011B`?). Only units `147` (6 of 8 calls) and `18A` (its 1 call)
ever request a mask buffer at all — the other 12 calls (units `019`, `069`,
`0C5`, `12B`) load opaque images. Where a mask *is* requested, the transparent
index is **colour 0 in 6 of 7 cases, and colour 13 in the seventh**
(`18A`'s call) — so the original guess in this file was usually right, but
transparency is a genuine per-call parameter, not a hardcoded constant.

## `BODY*` / `HEAD*` — character-generator portraits — **RESOLVED**

21 `BODY*` files, all 2,129 B, header `30 00 0b 00 …` → **88 × 48**
(`17 + 48*11*4 = 2129`). 41 `HEAD*` files, all 1,777 B, header `28 00 0b 00 …`
→ **88 × 40** (`17 + 40*11*4 = 1777`). Raw, no RLE. File numbering is sparse
(`BODY1, BODY2, …, BODY37`; `HEAD0 … HEAD74`) — the gaps are presumably
appearance-table indices. **TBD.**

---

## `.DAX` families — what each one holds

Generated by classifying every block against the image-header rule.

| family | files | blocks | image | array | other | geometry / record size |
|---|---|---|---|---|---|---|
| `8X8D1-8.DAX` | 8 | 45 | 0 | 44 | 1 | 8×8 tile sheets (70, 45, 31 … tiles/block) — **the dungeon wall-tile art**, confirmed 2026-08-21: unit `18A`'s `entry_015D` classifies a global tile ID into exactly these 5 frame-count families (45/70/70/70/31) to pick which sheet+frame to blit, see `analysis/executables.md` §Unit `18A` |
| `BACPAC.DAX` | 1 | 1 | 0 | 1 | 0 | 40 × 24×24 |
| `CBODY.DAX` | 1 | 128 | 128 | 0 | 0 | 24×24 |
| `CHEAD.DAX` | 1 | 56 | 56 | 0 | 0 | 24×10, 24×8 |
| `COMSPR.DAX` | 1 | 26 | 26 | 0 | 0 | 24×24 |
| `CPIC1-8.DAX` | 8 | 218 | 218 | 0 | 0 | 24×24, 24×48, 48×24 |
| `DUNGCOM.DAX` | 1 | 1 | 0 | 1 | 0 | 25 × 24×24 |
| `FINAL5.DAX` | 1 | 8 | 5 | 0 | 3 | 120×120, 56×32, 16×48 |
| `ICON.DAX` | 1 | 6 | 6 | 0 | 0 | 24×24 |
| `RANDCOM.DAX` | 1 | 1 | 0 | 1 | 0 | 6 × 24×24 |
| `SQRPACI.DAX` | 1 | 2 | 0 | 2 | 0 | 128 × 24×24 |
| `TITLE.DAX` | 1 | 2 | 2 | 0 | 0 | 320×200 |
| `WILDCOM.DAX` | 1 | 1 | 0 | 1 | 0 | 34 × 24×24 |
| `ECL1-8.DAX` | 8 | 29 | 0 | 0 | 29 | **not images** — 5,548 … 7,656 B |
| `GEO1-8.DAX` | 8 | 29 | 0 | 0 | 29 | **not images** — every block exactly **1,026 B** |
| `WALLDEF1-8.DAX` | 8 | 38 | 0 | 0 | 38 | **not images** — multiples of **780 B** (1–3) |
| `ITEM1-8.DAX` | 8 | 46 | 0 | 0 | 46 | **not images** — multiples of **63 B** |
| `MON1-8CHA.DAX` | 8 | 172 | 0 | 0 | 172 | **not images** — every block exactly **285 B** |
| `MON1-8ITM.DAX` | 8 | 105 | 0 | 0 | 105 | **not images** — multiples of **63 B** (1–6) |
| `MON1-8SPC.DAX` | 6 | 42 | 0 | 0 | 42 | **not images** — multiples of **9 B** |
| `SPRIT1-8.DAX` | 8 | 88 | 0 | 0 | 88 | **not images** — 2,000 … 3,128 B, sub-container **TBD** |

The digit in `8X8D`*n*, `CPIC`*n*, `ECL`*n*, `GEO`*n*, `ITEM`*n*, `MON`*n*`*`,
`SPRIT`*n*, `WALLDEF`*n* is the **install-disk / region number 1–8**, matching
the `DISK<n>A/B/C` manifests.

## Record sizes shared with the savegame files — sizes **RESOLVED**, character record partially decoded

The record sizes tie the shipped monster data to the shipped character data:

| record | size | appears in |
|---|---|---|
| character | **285 B** | `CHRDATA1-6.SAV` (6 × 285 B) **and** all 172 `MON*CHA.DAX` blocks |
| item | **63 B** | `CHRDATA*.ITM` (63/126/189) , `MON*ITM.DAX`, `ITEM*.DAX` — all exact multiples |
| the 9 B record (see §The 9 B `+0x7F` record) — **not spells** | **9 B** | `CHRDATA*.SPC` (9/18/36), `MON*SPC.DAX` — all exact multiples |

So **monsters and player characters use the same 285-byte record**, and the
`*CHA`/`*ITM`/`*SPC` triple is the same shape as a saved character's
`.SAV`/`.ITM`/`.SPC` triple. `CHRDATA1.SAV` starts
`0e 54 48 52 45 4e 44 45 52 20 47 52 4f 4e 45 00 …` = `[u8 len=14]"THRENDER GRONE"` —
a length-prefixed name at offset 0, consistent with the Pascal strings in
`GAME.OVR`.

### Hit points: `+0x32` is the maximum, `+0x11B` the current (2026-08-22)

The single most important pair of fields in the record, and undocumented until
now. Found by taking `+0x11B` off `work/structmap.py`'s unread list (55
references, 10 units) and noticing what the arithmetic around it does.

**The code.** `06C:26FB` adds 3 to `+0x11B`, then compares the result against
`+0x32` and writes back the smaller — a heal capped at a maximum:

```
06C:26FB  ADD byte ptr ES:[DI+0x11B],3
06C:2704  MOV AL,ES:[DI+0x11B]
06C:270C  CMP AL,ES:[DI+0x32]
06C:2715  MOV AL,ES:[DI+0x32]        ; clamp
06C:271C  MOV ES:[DI+0x11B],AL
```

`035:070A` subtracts a value from it (`SUB ES:[DI+0x11B],AL`), `06C:2272`
decrements it, and `03B:066C`, `06C:2267` and `06C:22F3` all test it against 0.
Damage, healing, and a death check.

**The data.** Across **178 shipped records** — 172 monsters in `MON*CHA.DAX`
and the 6 `CHRDATA*.SAV` characters — `+0x11B <= +0x32` holds **178/178**, and
the two are equal in every one of them, which is what records saved at full
health should look like. The values track monster power exactly as hit points
would:

| monster | `+0x32` |
|---|---|
| GOBLIN GUARD | 4 |
| ORC | 5 |
| HOBGOBLIN | 6 |
| GOBLIN LEADER | 7 |
| ORC LEADER | 8 |
| OGRE | 21 |
| OGRE LEADER | 32 |

with the full monster range running 3 to 110, and the six level-1 characters
holding 5 to 11.

**Note the offset collision.** `+0x32` is maximum hit points in the
**285 B character/monster** record and the signed magic value in the **63 B
item** record (§the item record above). Same displacement, two structures —
precisely the trap `work/structmap.py`'s docstring warns about, and the reason
its table now lists both meanings for that offset.

### `+0x10D` — a runtime boolean, and the `MON*CHA` container (2026-08-22)

`+0x10D` is the third-busiest unread offset (72 references, 15 units) and is a
strict boolean: every write is `0` or `1` and every test is against `0` or `1`.

What can be said:

- **All shipped data holds `1`** — 6/6 `CHRDATA*.SAV` characters and
  **172/172** `MON*CHA.DAX` monster records. So it is not a
  character-versus-monster marker, which was the first thing worth ruling out.
- It is set to `1` on a **freshly duplicated record**: `045:1B68` does
  `GetMem(0x11D)`, `Move` 285 bytes from an existing record, `+0x10D := 1`,
  then nulls `+0x104`.
- It is cleared to `0` at `045:0B98` and `045:1AFF`, and set back to `1` at
  `035:05FD`, `035:0980` and four sites in `03B`.
- Consumers branch on it being `0` — `058:002F` calls `10A:00CA` only in that
  case.

So it starts set in every record on disk and is cleared at run time in specific
situations. **What those situations are is not established** and no name is
recorded for it here.

**The `MON*CHA.DAX` container is confirmed while checking this**: every one of
its 172 blocks is an exact multiple of 285, giving 172 monster records with
readable names in the `+0x00` `ShortString` (`GOBLIN GUARD`, `ORC LEADER`,
`HOBGOBLIN LDR`, `OGRE`, …) — the same flat `N × record` shape as the item and
9 B files, and the same name field.

### The `+0x108` per-combat state block — 22 B, runtime only (2026-08-22)

`+0x108` is the most heavily used field in the character/monster record — 230
references across 13 units — and was entirely unknown. It is a **third
runtime-only far pointer**, alongside `+0x7F` and `+0xC8`: the loader nulls all
three together the moment a record comes off disk (`0BE:0C44`-`0x0C6B`), so
none of them is persisted.

It points at a **22-byte block**, and the whole lifecycle is readable:

- **allocated** `GetMem(0x16)` then `FillChar(block, 0x16, 0)` — `05F:13BC`
- **freed** `FreeMem(record + 0x108, 0x16)` and re-nulled while walking the
  participant list through `+0x104` — `03B:1213`

That is a per-participant block created for a battle and torn down with the
encounter, i.e. **per-combat state**. What `05F:13D7` onward puts in it:

| field | set to |
|---|---|
| `+0x09` | a facing value: `DS:0x2F0[ DS:0x6A0D / 2 ]`, the party facing folded through a 4-entry table, then re-derived as `(v + 4) / 8` when `record[+0x10E] == 1` |
| `+0x13` | `1` when a value exceeds `[DS:0x4937]+0x67C` |
| `+0x0A` | a far pointer — `058:1316` follows it, then tests `+0x76` on the target |

`+0x0C` and `+0x0E`-`+0x15` are read widely but not traced. The `DS:0x2F0`
table's four entries were **not** read: the address is DGROUP-relative and this
pass did not verify the base convention for a data offset, only for the
resident code addresses where it is already established.

### `+0x17` is an array base, not a field — a lead, not a result (2026-08-22)

Recorded because it is the second-busiest unread offset (99 references, 13
units) and because the obvious reading of it is wrong.

`0AC:0000` walks `[bp-0xB]` upward from 0 and reads `record[i + 0x17]`, so
`+0x17` is the **base of a byte array inside some record**, not a scalar.
Entries with **bit 7 set** are live (`CMP ...,0x7F / JBE skip`); the low seven
bits are shifted left four and used to index a **16-byte-stride table at
`DS:0x3195`**, which is read from five units (`0AC`, `0D2`, `0E2`, and
`DS:0x3196` for the second byte of an element).

A 7-bit index into a 16-byte-stride table is the same shape as the `ITEMS`
access (`item[+0x2E] << 4` into `DS:0x54E0`), but `DS:0x3195` is a **different**
table and this pass did not establish what it holds, nor which record owns the
`+0x17` array — the routine takes its base as a parameter. All six shipped
characters have `0x00` at `+0x17`, which is consistent with an empty array and
tells us nothing more.

Left here deliberately as a characterised lead. `python3 work/structmap.py 0x17`
lists every site.

### The 9 B `+0x7F` record — container **RESOLVED**, and it is **not** the spell list (2026-08-22)

Chased because the previous pass left `+0x7F` as "a second list head, contents
not identified" and noted that `MON*SPC.DAX`'s "9 B spell record" was the
obvious guess. It is a 9-byte record, and the guess is wrong.

**Structure.** `+0x7F` heads a singly-linked list built exactly like the
inventory at `+0xC8`: `GetMem(9)` per node, `Move` 9 bytes from the source,
then the **4-byte far "next" pointer at `+5`** is zeroed. Read from three
independent sites — ECL opcode `0x0B` builds it (`020:0715`-`0x074C`), the
destructor `0B6:0072` walks and frees it, and the saver `0BE:0A06` writes it.
So the on-disk record is 9 bytes of which only **bytes 0-4 are payload**; 5-8
are the link.

**Container.** Flat `N × 9 B` arrays, no header — the same shape as the item
files: **42/42 `MON*SPC.DAX` blocks** and **4/4 `CHRDATA*.SPC` files** are exact
multiples of 9.

**The saved files still contain live heap pointers.** `CHRDATA1.SPC` reads

```
5a 00 00 ff 00 | 07 00 e6 4e     <- next = 4EE6:0007, a heap address
61 00 00 ff 00 | 00 00 e7 4e
1a 00 00 ff 00 | 09 00 e7 4e
2f 00 00 ff 00 | 00 00 00 00     <- end of list
```

The game writes the nodes out verbatim, stale pointers and all, and zeroes them
again on load. Useful as confirmation of the layout, and a reminder that a
savegame's bytes are not all meaningful.

**Why it is not the spell list.** Pair each shipped character's class-level
bytes (`+0x96`-`0x9D`) with its record count:

| character | levels `+0x96`-`0x9D` | `.SPC` records |
|---|---|---|
| THRENDER GRONE | `00 00 01 00 00 00 00 00` | **4** |
| BAKSHI | `01 00 01 00 00 01 00 00` | 1 |
| RHIANNON | `00 00 01 00 00 01 00 00` | 1 |
| BROTHER SEAN | `01 00 00 00 00 00 00 00` | **0** |
| DARKSTAR | `00 00 00 00 00 01 00 00` | **0** |
| PHINEAS | `00 00 00 00 00 00 01 00` | 2 |

The two characters with a single level in one slot each and *no* records are
the two whose slots nothing else uses — and the character with the most records
has a level in the same slot as two others that have one record each. However
the eight slots map to classes, a memorised-spell list cannot give 4 to one
single-classed character and 0 to two others of different single classes. The
`.SPC` extension is the only thing that ever suggested "spell", and it is not
evidence.

Absence of the file means only that the list is empty: the saver
(`0BE:09C2` onward) `Assign`s `<name>.spc` and then **`Erase`s it**
(`05BB:162C`, `INT 21h AH=41h`) when `+0x7F` is null, or `Rewrite`s
(`05BB:1426`, `INT 21h AH=3Ch`) and writes the nodes when it is not.

**What byte 0 is.** A type selector. Consumers walk the list comparing byte 0
against specific constants — `0x0C` and `0x26` at `06C:0531` and `100:11B1`,
`0x26` and `0x80` at `06C:2F7E` — and the shipped data uses `0x5A`, `0x61`,
`0x1A` and `0x2F`, so the space is wider than the handful tested. The `06C`
site is suggestive: it scans for types `0x0C`/`0x26` **immediately after
writing the character's STR and STR-percentile fields** at `+0x10`/`+0x16`,
which reads like a magical Strength adjustment and would make the list one of
active modifiers. That is a *reading of one call site*, not an established
meaning, and the remaining four payload bytes are undecoded.

### The 285 B character/monster record — partially decoded (2026-08-21)

Found the roster-display routine the same way as every loader this session:
a byte search for the D&D ability-score labels (`STR `, `INT `, `WIS `, …)
lands in unit `0C9`'s `entry_004A`, which reads the record pointed to by a
far pointer at `DS:0x5CF0` and displays it field by field. Every offset below
is read from that code, then cross-checked against `CHRDATA1.SAV`'s real
bytes — all of them fit a plausible AD&D character exactly, not just a
type-compatible value:

| offset | field | evidence | `CHRDATA1.SAV` value |
|---|---|---|---|
| `0x00` | name, Pascal `ShortString` (len byte + up to 15 chars, 16 B total) | length-prefixed, `entry_004A` reads it directly | `"THRENDER GRONE"` (already known) |
| `0x10`-`0x15` | **STR, INT, WIS, DEX, CON, CHA** (1 B each) | `entry_0904(param_2)`, called in a `param_2 = 0..5` loop matching the label order, reads `recordPtr + param_2 + 0x10` | `17, 12, 12, 17, 16, 15` — all valid ability scores |
| `0x16` | STR exceptional/percentile ("18/xx") | `entry_0904` special-cases `param_2==0 && *(recordPtr+0x10)==0x12`(=18) to also read `*(recordPtr+0x16)` — the textbook AD&D 18/percentile-Strength rule | `0` (correct: this character's STR is 17, not 18, so percentile doesn't apply) |
| `0x30` | word, formatted as a plain number; **Age**, by UI-label order (see below) | `func_0x000010ed(...,*(recordPtr+0x30),...)` right after the NPC check, right before the ability-score loop | `52` — plausible character age |
| `0x84` | byte, gates an early NPC-only display branch | `if (0x7f < *(recordPtr+0x84)) { ...NPC-only... }` in `entry_004A` | `0` |
| `0x96`-`0x9D` | 8 B, **class levels**, by UI-label order ("Level") | looped `local_8 = 0..7`; each non-zero byte gets displayed, joined by `/` for multiple — matches Gold Box multi-classing exactly | `00 00 01 00 00 00 00 00` — one class slot, level 1 (a fresh level-1 single-class character) |
| `0xAC`-`0xAF` | two words, displayed as a pair; **Experience**, by UI-label order ("Exp") | `FUN_0000_10E8(...,*(recordPtr+0xac),*(recordPtr+0xae),...)` | `32, 0` — low XP, consistent with a starting character |
| `0xCC`-`0xCF` | far pointer, non-null gates a "Weapon" display | matches the `Weapon` label's position in the UI string table | `0:0` (unarmed in this save) |
| `0xD4`-`0xD7` | far pointer, non-null gates an "Armor" display | matches the `Armor` label's position | `0:0` (unarmored in this save) |
| `0x10C` | byte, index into a 13-byte-stride string table (`index*0x0D + 0x105B` in unit `198`) — **Status** | last field `entry_004A` displays, matching the `Status` label | `0` (first/default status entry) |
| `0x7F`-`0x82` | far pointer, a second list head; contents not identified | handed back by `045:0423` alongside the inventory head, when ECL opcode `0x0B` loads a monster (2026-08-22) | — |
| `0xC8`-`0xCB` | far pointer, **inventory list head** (63 B items chained at `+0x2A`) | three independent sites: unit `0C9`'s `entry_0EFB`, its redraw continuation, and now `045:0423` (2026-08-22) | — |
| `0x32` | **maximum hit points** | see §Hit points below (2026-08-22) | 11 |
| `0x11B` | **current hit points** | see §Hit points below (2026-08-22) | 11 |
| `0x84` | bit 7 is the NPC gate; **bits 0-6 are a separate value** | `05F:1448` masks it `AND 0x7F` and compares the result against constants (e.g. `0x66`); all six shipped characters hold `0x00` (2026-08-22) | `0` |
| `0x108`-`0x10B` | far pointer to a **22 B per-combat state block** — see §The `+0x108` per-combat state block | the most-referenced field in the record: 230 references across 13 units (2026-08-22) | — |
| `0x10E` | a mode byte, tested against 0 and 1 beside the `+0x108` logic | `05F:1414`, `05F:1450` (2026-08-22) | — |
| `0x104`-`0x107` | far pointer, **next participant** — the link the encounter list at `DS:0x5CF4` is built on | ECL opcode `0x0B` walks it to append, `045:0766` walks it to find a participant's index (2026-08-22) | — |

**Confidence:** the name field and `STR`..`CHA` (+ the 18/percentile rule) are
read directly from the code with no inference beyond matching argument
order to loop index — as solid as this project's other RESOLVED formats.
`Age`/`Level`/`Exp`/`Weapon`/`Armor`/`Status` are inferred by matching code
*order* to the UI label string's *order* (`"(NPC) Age STR INT WIS DEX CON
CHA Level Exp Weapon Armor Status"`), not from a field name in the code
itself — very likely right given every value cross-checks, but held to a
slightly lower standard than the directly-read fields. The large gaps
(`0x17`-`0x2F`, `0x31`-`0x83`, `0x85`-`0x95`, `0x9E`-`0xAB`, `0xB0`-`0xCB`,
`0xD8`-`0x10B`) are still undecoded — likely HP, saving throws, spell
slots, inventory, and the rest of a full AD&D character sheet, none of
which `entry_004A`'s roster-summary view needs to touch. This is the same
285 B layout `MON*CHA.DAX` uses, so it applies to monster stat blocks too,
though a monster record likely doesn't populate every field a PC does.

**A second, detail-stats screen** (`entry_0607`, same unit, labelled
`"AC HP THAC0 d + - Damage Encumbrance Movement"`) reads six more offsets
from the same record — `0x102` (word), `0x110`, `0x115`, `0x117`, `0x119`,
`0x11C` (all bytes) — but **held to a lower confidence tier than the fields
above**: unlike the ability-score loop, the AC/HP display calls
(`FUN_0000_10D4`/`func_0x000010cf`) don't show an obvious direct record
offset in the decompiled arguments, so this pass could not confirm which of
the six labels each of the six offsets belongs to. Two are plausible enough
to note, not to rely on: `0x117`/`0x119` read as a base value plus a
separately-displayed signed modifier (`"+N"`/`"-N"`) — the shape of a base
stat with a magic-item bonus, AC being the obvious candidate; `0x11C` (the
record's second-to-last byte, value `9` in `CHRDATA1.SAV`) gets conditionally
doubled or halved by two more checks before display — the shape of a
movement rate modified by encumbrance or terrain. `0x110`
(`func_0x000010f2`'s argument is `0x3C` minus this byte) and `0x102`, `0x115`
are read but not confidently tied to a label at all. Treat all six as
"known to be read here, not known to be *which* stat" until traced further.

### The character record's inventory, and the 63 B item record — container **RESOLVED (2026-08-22)**, fields still open

Found via the classic Gold Box item-action menu (`"Ready / Use / Trade /
Drop / Halve / Join / Sell / Id"`, plus `"Must be Readied"`, `"Drop It?"`),
the same unit `0C9`, function `entry_0EFB`. **The character's inventory is a
singly-linked list**, not a flat array:

- **character record `+0xC8`** (4 B, far pointer) — head of the inventory
  list, read as `*(undefined4*)(recordPtr + 200)`, checked for null before
  walking it.
- **item record `+0x00`** — a Turbo Pascal `ShortString`: **the item's name**
  (2026-08-22). `CHRDATA1.ITM` reads `06 "Flail "` and `0c "Banded Mail "`,
  and every `.ITM`/`ITEM*.DAX` record in the game yields a readable name the
  same way. A second, space-padded name follows immediately (`"Flail"`,
  `"Mail"`) — its own field boundaries are **not** established.
- **item record `+0x39`** (1 B) — the **quantity** (2026-08-22). Proved against
  the data: of the 42 item records in the game whose name begins with a number,
  **42 of 42** have that number in `+0x39` — `11 Darts` → 11, `20 Quarrel(s)`
  → 20, `7 Gold Statuette` → 7, and so on, with no exceptions.
- **item record `+0x32`** (1 B, **signed**) — a per-item magic value
  (2026-08-22). The signedness is read from the code: `058:12D4` guards with
  `CMP ...,0 / JLE`, a *signed* test, before adding `value << 3` to a weapon
  score at `058:12DE`. `06C:224D` decrements it, `06C:08C2` sets it to 1 and
  `06C:21BC` to 0.

  The distribution is 0 for 458 of 667 items, then 1 (124), 2 (42), 3 (17), a
  thin tail to 12 — and two negatives. Named examples: `Wand` and
  `Efreeti Bottle` 10, `Manual` 12, `Ring` 3, `Magic User Scroll` 2,
  `Broad Sword` **−2**, `Necklace` **−5**.

  A bonus for weapons and armour (negative on cursed items) and a charge count
  for wands and the like, in one byte interpreted by category, is the reading
  the values invite. What is *read* is narrower: the byte is signed, positive
  values raise a weapon's score by eight each, and something consumes it one at
  a time. No dispatch on the item category was traced.
- **item record `+0x2E`** (1 B) — the **item-type index** into the 128-entry
  `ITEMS` table (see the `ITEMS` bullet). Read at `058:12A0` and `0C9:157A`,
  both doing `index << 4` into the buffer at `DS:0x54E0`; checked against all
  667 item records in the game, every value is 1-93 (2026-08-22). It sits
  immediately after the link below, which is a consistency check on both.
- **item record `+0x2A`** (4 B, far pointer) — each item's "next" link,
  confirmed at two independent call sites (`entry_0EFB` itself, and a
  Ghidra-fragmented continuation of the same function that redraws the list)
  — `nextItem = *(undefined4*)(itemPtr + 0x2A)`, looped until null.

This is a different pointer from the `+0xCC` ("Weapon") and `+0xD4`
("Armor") far pointers `entry_004A` already established — those are almost
certainly direct "currently equipped" references, separate from the general
inventory list head at `+0xC8`, though whether they point *into* the same
list or hold independent copies isn't determined.

**What blocked going further:** the function that actually displays each
item's fields while walking the list, `FUN_0000_10c5`, has a Ghidra-flagged
instruction overlap (`"Instruction at (ram,0x10c9) overlaps instruction at
(ram,0x10c7)"`), and checking the raw disassembly independently confirms a
real byte-alignment discontinuity at the same spot — a `PUSH AX` that should
be followed by a 5-byte `CALLF` at `0x10c4` instead has the next listed
instruction at `0x10c5`, one byte off, with garbage (`DEC SI`, `MOV BX,...`)
in between. This is a genuine decode ambiguity, not a function this pass
chose not to read — the same category as the ECL loader's earlier false
start, and treated the same way: documented as blocked rather than forced
through with a guess. The 63 B item record's own internal fields (name,
type, damage, charges, value) remain fully undecoded.

**The item *containers* are resolved (2026-08-22)**, from the other end — ECL
opcode `0x27`, the scripts' item-creation instruction (§Opcode semantics).
Its loader reads a `.DAX` block whole and walks it in **63-byte steps with no
header at all**, `Move`ing each record into a fresh `GetMem(0x3F)` node and
prepending it to the list:

```
020:1B65  MOV AX,0x3F ; PUSH AX ; CALLF Move        ; one 63 B record
020:1B6E  <zero the new node's +0x2A far pointer>
020:1B76  ADD word ptr [BP-0x67],0x3F               ; step to the next
020:1BE9  CMP AX,[BP-0x69] ; JAE done               ; until the block is used up
```

So an item file is a **flat array of N × 63 B records**, and unlike `GEO`/`ECL`
there is no 2-byte prefix. Checked against the data, and it holds without a
single exception:

| family | blocks/files | all exact multiples of 63 |
|---|---|---|
| `ITEM1-8.DAX` | 46 | 46/46 (1-58 records each) |
| `MON*ITM.DAX` | 105 | 105/105 |
| `CHRDATA1-6.ITM` | 6 files | 6/6 (63, 126 or 189 B) |

157 containers, zero remainders — the strongest kind of confirmation available
here, since a wrong record size would fail almost immediately. The `+0x2A`
far-pointer "next" link is confirmed a third time by this handler, which
explicitly zeroes it on load. The record's internal fields are still undecoded;
what is now known is the container, and that a saved character's `.ITM` file is
simply its inventory list flattened.

## `GEO*.DAX` — dungeon map data — **RESOLVED (container), planes TBD (2026-08-21)**

Every block is exactly **1,026 B** across all 72 blocks in `GEO1-8.DAX`
(verified, `python3 work/dax.py`-style block enumeration). The `2 + 32*32`
single-grid guess was **wrong** — the loader, `entry_10EA` in overlay unit
`131` (`analysis/executables.md` §Unit `131`), settles the real layout: a
2-byte header (`00 04` in every sampled block — constant, purpose TBD, and
explicitly *skipped*, not copied, by the loader), followed by **four
256-byte (16×16-cell) grids**, not one 1,024-cell grid. The resident buffer
this loads into is allocated at exactly `1,024 B` (`0x400`) in the central
init routine (`analysis/executables.md` §Unit `069`) — independent
confirmation that the header really is excluded from the working copy, not
merely skipped during the one load this project has directly traced:

```
u16    header               constant 00 04 in every sampled block; TBD
16x16  region 0  (+0x002)   nibble-packed (2 planes: high/low nibble)
16x16  region 1  (+0x102)   nibble-packed (2 planes: high/low nibble)
16x16  region 2  (+0x202)   plain byte per cell
16x16  region 3  (+0x302)   2-bit-packed (4 planes: bits 6-7/4-5/2-3/0-1)
```

Confirmed two ways: `entry_10EA` copies the payload as four explicit 256-byte
`func_0x00007242` moves at destination offsets `0x000`/`0x100`/`0x200`/`0x300`
(source offset starts at 2, skipping the header) into a resident array at
`*(undefined4*)0x69ba`; and the three region-2/3 accessor functions in the
same unit (`entry_048A`, `entry_058F`, `entry_0358`) all index with
`row*0x10 + col` (a 16-wide stride) into exactly those offsets, with bit
extraction matching each region's packing (nibble/byte/2-bit respectively).
A real block's bytes match this cleanly — `GEO1.DAX` block `0x12` region 3
row 0: `00 00 04 40 01 10 10 00 …`, which decodes as four independent 2-bit
fields per byte under exactly the `>>6`/`(x&0x30)>>4`/`(x&0xc)>>2`/`x&3`
split `entry_0358` uses.

**Regions 0/1 — RESOLVED (2026-08-21):** each of the 4 cardinal directions
(N/E/S/W — the game's dungeon facing is 4-directional, not 8) gets its own
nibble-plane, two directions packed per byte: `entry_0614` only ever calls
the region-0/1 accessor (`entry_048A`) with an even `direction` value
(0, 2, 4, 6 — confirmed by that accessor having no defined behaviour for odd
values, and every caller preserving `direction`'s parity through `mod 8`
rotations), and those four values map exactly to {region 0 high nibble,
region 0 low nibble, region 1 high nibble, region 1 low nibble}. Which
literal direction is 0 vs. 2 vs. 4 vs. 6 is not pinned down (needs the
direction-delta table's orientation, `analysis/executables.md` §`entry_0614`,
matched against a real dungeon map). **Regions 2/3 — narrowed (2026-08-21):**
not read by `entry_0614`, but their accessors (`entry_058F`, `entry_0358`)
have real external callers (units `020`, `045`, `05F`, `0A5`, `124`, found by
the same thunk-offset grep used for `entry_011B`) — see
`analysis/executables.md` §the `GEO` plane accessors. Both are queried
against what look like the party's live position/facing (`DS:0x6A0B`
row, `0x6A0C` col, `0x6A0D` direction). Region 2 (`entry_058F`, no direction
input) is a **per-cell property** — floor/ceiling/special-square is still the
best guess (sampled values cluster around `0x80` with small deviations
`0x87`, `0x89`, `0x8B`). Region 3 (`entry_0358`, direction-indexed like the
wall planes) is a **per-direction flag distinct from wall presence** — one
caller branches on its value being `1` vs `2`, suggesting a small enum
(door/stairs/special feature in that direction), unconfirmed.

## `WALLDEF*.DAX` — wall-tile sprite sheets — **RESOLVED (2026-08-21)**

Blocks are exact multiples of **780 B** (1–3 per file, verified across all 8
regions: `780`, `1560 = 2×780`, `2340 = 3×780` — and the resident buffer this
loads into is allocated at exactly `2,340 B` in the central init routine,
`analysis/executables.md` §Unit `069`, confirming 3 blocks/region is the true
maximum, not just the largest sample observed). The loader, `entry_0E25` in
unit `131`, copies each 780 B block into a resident per-region array at
`*(undefined4*)0x69b6 + regionIndex*780`, then walks it as **five 156-byte
sub-arrays** (`780 = 5 * 156`, confirmed by the loop bounds: outer `local_d`
1..5, inner `local_11` 0..0x9b=155) applying a per-region remap — any byte
`>= *(uint*)0x2740` (a threshold) gets a per-region constant added to it,
turning region-local wall-texture IDs into a shared/global ID space. **That
global space is now identified** (2026-08-21): unit `18A`'s `entry_015D`
classifies exactly this range (1-286) into the 5 `8X8D*.DAX` tile-sheet
families by frame count — see `analysis/executables.md` §Unit `18A`. The
threshold value itself, and each of the 5 `WALLDEF` sub-arrays' selecting
index (almost certainly the `GEO` cell value from the matching
direction-plane), are still not pinned down.

**Each 156-byte sub-array is a packed sheet of 10 fixed-size sprites**, one
per depth/screen-position "slot," read straight out of `START.EXE`'s DGROUP
(paragraph `0x740`, shared with unit `18E` and `131`) at the three parallel
tables `entry_0219` (the tile blitter, called from `entry_0614`) indexes by
its `param_1` (the literal `1`..`9` "wall type" constants at every
`entry_0219` call site in `entry_0614`):

| slot | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| offset (`DS:0xca0`) | 0 | 2 | 6 | 10 | 22 | 38 | 54 | 110 | 132 | 154 |
| width (`DS:0xcaa`) | 1 | 1 | 1 | 3 | 2 | 2 | 7 | 2 | 2 | 1 |
| height (`DS:0xcb4`) | 2 | 4 | 4 | 4 | 8 | 8 | 8 | 11 | 11 | 2 |

Not a guess: `offset[i] + width[i]*height[i] == offset[i+1]` holds **exactly**
for all 9 gaps, and the last slot's `offset + width*height = 156` — the full
sub-array, with no slack. Each byte in a slot's `width × height` rectangle is
one screen cell's tile-ID, blitted cell-by-cell (skipping zero — no tile) by
`entry_0219` at screen position `(row+2, col+2)` via a call into unit `18A`.
Slot sizes run from `1×2` (slots 0 and 9, the smallest) up to `7×8` (slot 6,
the largest) — a small, hand-placed set of "distance sprites" for a
fixed-perspective view where nearer wall segments are simply bigger
pre-drawn rectangles, not projected geometry. This is the same technique
`analysis/executables.md` §`entry_0614` already inferred from the render
loop's structure; the sprite-sheet table is the confirming detail.


## `ECL*.DAX` — encounter/event scripts — container, instruction encoding, **block layout and the address space RESOLVED**; 32 of 61 opcodes named (2026-08-22)

Found the same way `GEO`/`WALLDEF` were: a byte search for the `ECL` short-string
constant (`\x03ECL\x04.dax`) locates the loader, `entry_0353` in overlay unit
`045`. Confirmed from raw disassembly, not decompiled approximation:

```
LES DI,[0x493F]; PUSH ES; PUSH DI      ; dest = the far ptr already held at DS:0x493F
MOV AX,0x1E00; PUSH AX                  ; count = 7680
MOV AL,0x0;   PUSH AX                   ; fill value = 0
CALLF FillChar                          ; (func_00007265, analysis/executables.md
                                         ;  §resident Pascal RTL primitives)
```

then the same "build `ECLn.dax`, open, read" sequence unit `131` uses for
`GEO`/`WALLDEF`, then a `Move` (`func_00007242`) that copies from **source
offset 2** — a 2-byte header, skipped, matching `GEO`'s container exactly —
into the zeroed buffer.

### The interpreter — the six routines everything below is read from

| routine | role |
|---|---|
| `020:35DB` | **execute loop** — `PC := arg`, then `{ fetch opcode at PC; dispatch }` until `DS:0x4390` or `DS:0x4960` is set |
| `020:32DF` | **opcode dispatcher** — a `CMP AX,n / CALL handler` chain, the complete opcode→handler table |
| `045:0000` | **operand decoder** `entry_0000(n)` — reads `n` operands, advances the PC |
| `045:013F` | **operand evaluator** `entry_013F(i)` — resolves operand `i` to a value |
| `045:06BE` | **address builder** `entry_06BE(value, extra)` = `(extra << 8) + value` |
| `045:01C8` | **block init** — `PC := 0x9900`, then reads the five-entry header |

Reading these required the overlay call convention, which is worth restating
because it is easy to get wrong: `CALLF 0x0045:0x002A` is *not* unit `045`
offset `0x2A`. Each unit's segment opens with a **thunk table at `+0x20`, five
bytes per slot** (`work/resolve_calls.py`), so `0x2A` is slot
`(0x2A-0x20)/5 = 2`, and `overlay_map.json`'s `thunks[2]` for unit `045` is
`0` — `entry_0000`. Likewise `0x52` → slot 10 → `045:06BE`, `0x25` → slot 1 →
`045:013F`, `0x9D` → slot 25 → `045:1991`. Decoding the offset as a raw
address lands mid-instruction and reads as nonsense.

### Instruction encoding — **RESOLVED**

```
instruction := [u8 opcode] [operand × N]        ; N from the table below
operand     := [u8 type] [u8 value]             ; 2 bytes …
                  [u8 extra]                    ; … + 1 more iff type ∈ {1,2,3,0x81}
                  [u8 text × value]             ; … + `value` more iff type == 0x80
```

**Valid opcodes are `0x00`-`0x3D`**, and every one has a handler in the
dispatch chain at `020:32DF` **except `0x1F`**, which falls into the
illegal-opcode reporter at `020:356D` and therefore cannot occur in valid
code. The full opcode→handler map is `HANDLER` in `work/ecl.py`.

**Operand count per opcode**, taken from each handler's own
`MOV AL,n / PUSH AX / CALLF entry_0000`:

| operands | opcodes |
|---|---|
| 1 | `01 02 0A 0E 11 12 1D 20 2D 32 34 36 38 39 3C` |
| 2 | `03 08 09 0F 10 22` + `25 26 2B` (variable, below) |
| 3 | `04 05 06 07 0B 0C 21 28 2A 2F 30 35 37 3B` + `15` (variable) |
| 4 | `14 23` |
| 5 | `2E` |
| 6 | `1E 2C` |
| 8 | `27` |
| 14 | `29` |
| 0 | `00 0D 13 16-1B 1C 24 31 33 3A 3D` |

**This is not the same table as the classifier at `020:0B1A`**, which an
earlier pass in this project used as the authority. The classifier is a
compare-chain that returns an operand count, but it is consulted **only** by
the conditional-skip path (`020:0C5A`); the handler is what runs for a normal
instruction. They disagree on five opcodes:

| opcode | classifier says | handler consumes |
|---|---|---|
| `0x0C` | 2 | **3** |
| `0x15` | 0 | **3 + N** |
| `0x25` | 0 | **2 + N** |
| `0x26` | 0 | **2 + N** |
| `0x2B` | 0 | **2 + N** |

The `0x0C` disagreement alone is worth 25 percentage points of control-flow
coverage (72.4 % with the classifier's 2, 97.7 % with the handler's 3).
The divergence is a genuine latent bug in the shipped interpreter — a
conditional guarding one of those five instructions would skip the wrong
number of bytes — but **no block in the corpus does that** (checked: 0
occurrences), so it never fires.

**The variable-length construct — this is what desynced every earlier walk.**
Four opcodes read their own operand count out of the instruction stream. The
handler decodes its fixed operands, evaluates one of them, backs the PC up one
byte (`DEC word ptr [0x494e]`) and calls `entry_0000` again with that value,
so `entry_0000` resumes at exactly the right byte and appends `N` more
operands:

```
020:19D6   entry_0000(2)              ; 0x25 / 0x26: two fixed operands
020:19DE   sel   := entry_013F(1)
020:19E9   count := entry_013F(2)
020:19F1   DEC [0x494E]               ; back up one byte
020:19F9   entry_0000(count)          ; N more operands, in the same tables
020:1A18   CMP [0x6D45],0x25          ; 0x25 -> PC := addr(operand sel+1)  (GOTO)
                                      ; 0x26 -> gosub that address
```

| opcode | fixed | count comes from | meaning |
|---|---|---|---|
| `0x15` (`020:1035`) | 3 | operand 3 | a menu: 3 fixed + N choices |
| `0x25` (`020:19E6`) | 2 | operand 2 | `ON sel GOTO` over N addresses |
| `0x26` (`020:19E6`) | 2 | operand 2 | `ON sel GOSUB` over N addresses |
| `0x2B` (`020:11D8`) | 2 | operand 2 | 2 fixed + N |

`entry_013F` returns `value` unchanged for a type-`0x00` operand, so `N` is
statically known whenever the count operand is an immediate — which it is
everywhere in the corpus. Any other type would be a memory read and the
instruction would not be statically decodable; `work/ecl.py` raises rather
than guess.

**Operand addressing modes**, from `entry_013F`:

| type | meaning |
|---|---|
| `0x00` | immediate — `value` is the operand |
| `0x01`, `0x03`, `0x80` | indirect via `entry_0E2E((extra<<8) + value)` |
| `0x02`, `0x81` | the address `(extra<<8) + value` itself |

There is deliberately **no operand-type whitelist**: `entry_0000` special-cases
only `1/2/3` (extra byte), `0x80` (inline text) and `0x81`, and treats every
other type byte as a plain 2-byte operand.

`045:070B` classifies a 16-bit ECL address into one of five regions, which
names the address spaces the scripts use and independently pins the buffer:

| range | region |
|---|---|
| `0x4900`-`0x4CFF` | interpreter globals |
| `0x6B00`-`0x6EFF` | operand/variable tables (`0x6DCB`, `0x6E0B`, `0x6E4B` …) |
| `0x9700`-`0x98FF` | 512 B |
| `0x9900`-`0xB6FF` | **the ECL script buffer** — exactly 0x1E00 = 7,680 B |
| anything else | 4 |

### Block layout — **RESOLVED (2026-08-22)**

A block opens with a **20-byte header: five 4-byte records, each written as a
`01 [01 lo hi]` instruction**. `045:01C8` sets `PC := 0x9900` and then runs
five `entry_0000(1)` + `entry_06BE` pairs over them, filing the five addresses
into `DS:0x4944 / 0x4946 / 0x4948 / 0x494A / 0x494C` — the block's **five
script entry points**, which the game later hands to the execute loop
(`020:3134`, `020:3151`, `020:3741`, `020:3658`, `020:38DD`, …; unit `0A5` also
runs `DS:0x4946` directly at `0A5:0AE4` and `0A5:0CFF`). Encoding them as real
`01` GOTO instructions is what makes entry #1 work by simply falling in at
`PC = 0`. **All 29 blocks parse**, and the entry offsets are not always just
past the header — `ECL7.DAX` block `0x17` enters at `+0x213`, so `+0x14`-`+0x212`
is data.

So a block is **not** a flat instruction stream, and no amount of fixing a
linear walk would ever have made it one. It is a control-flow graph rooted in
those five entries. Control flow, all read from the handlers:

| opcode | | effect |
|---|---|---|
| `0x00` | `END` | `020:009A` sets `DS:0x4390`, so `020:35E9` exits the loop; also unwinds the call stack |
| `0x01` | `GOTO` | `020:0105` `PC := entry_06BE(operand 1)` |
| `0x02` | `GOSUB` | `045:19E8` pushes the PC onto a linked stack of 6-byte nodes headed at `DS:0x6D36`, then jumps |
| `0x13` | `RETURN` | `020:0A82` pops that stack into the PC and frees the node |
| `0x25`/`0x26` | `ON … GOTO/GOSUB` | over the N trailing operands |

**The conditional skip is the rule that makes the walk work.** `020:0C5A`
steps the PC past a conditional (`0x16`-`0x1B`, one per flag in
`DS:0x6D3E`-`0x6D43`) and then re-enters the decoder for the *next*
instruction only when the guard flag is clear — i.e. the guarded instruction
is either executed or skipped. When it is a `GOTO`, an `END` or a `RETURN`,
**its fallthrough is live too**: `IFCLR0 / GOTO x` is exactly how the scripts
write `if cond goto x`. Modelling that is worth the whole result — without it
a control-flow walk reaches ~16 % of a block, with it **97.7 %**.

**Corpus result** (`python3 work/ecl.py --validate`):

```
20-byte 5-entry header parses     : 29/29 blocks
decoded by control flow alone     : 171620/175624 = 97.7% of payload
  left over: 3424 B in 93 islands (1.9%)
```

The leftovers are dominated by **trailing data tables** — sorted byte runs and
small-value arrays sitting at the end of a block (the largest are 464 B, 325 B,
213 B and 207 B), plus 24 single-byte gaps between scripts. A little of it is
unreached code, e.g. a real `TEXT` instruction at `ECL8.DAX` `0x0d` +6640
(`WHEN YOU REST, FATIMA TELLS YOU OF HER TRIBE.`) that nothing in the five
entry points' reachable graph calls. `work/ecl.py`'s `sweep()` will linear-scan
the leftovers and gets the number to 99.7 %, but it is a **heuristic that is
known to be wrong sometimes** — a sweep that starts inside a data table decodes
the table as code and then runs on into real instructions and swallows them.
It is a way to look at the residue, not evidence, and `--text` does not use it.

### Inline packed text — type `0x80` — **RESOLVED (2026-08-22)**

A type-`0x80` operand is followed by **`value` bytes of inline 6-bit-packed
text**, embedded directly in the instruction stream. Confirmed in the handler
at unit `045:0x1186`, which advances the interpreter's own program counter
(`INC word ptr [0x494E]`) once per byte consumed, looping while its counter
`< value` — so the operand's encoded size is `2 + value`.

The packing is four 6-bit codes per three bytes:

```
state 1:  code = cur >> 2                        (consumes a byte)
state 2:  code = ((prev << 6) + (cur >> 2)) >> 2 (consumes a byte)
state 3:  code = ((prev << 4) + (cur >> 4)) >> 2 (consumes a byte)
state 4:  code = cur & 0x3F                      (consumes NO byte)
```

Each 6-bit code becomes a character via `unit 045:0x06E3`, which is not a
lookup table at all but **plain 6-bit ASCII** — the whole routine is
`code > 0x1F ? code : code + 0x40`, i.e. the printable ASCII range
`0x20`-`0x5F` stored in six bits. A zero code terminates. The game text is
therefore upper-case only, which matches the shipped screens.

`python3 work/ecl.py --text` recovers **1,826 distinct strings / 115,502
characters**, every one of them attached to a decoded instruction at a known
offset — real, coherent Pool of Radiance prose, e.g.

> `YOU ARE USHERED INTO THE STUDY WHERE DIRTEN WAITS.  'I AM ABOUT TO JOURNEY`
> `TO THE TEMPLE, WILL YOU COME WITH ME?'`

Opcodes carrying text: `0x12` displays it, `0x11` asks a yes/no question, and
`0x15` is a menu whose question and N choices are consecutive text operands of
one instruction — e.g. `ECL1.DAX` `0x12` +310, *"THE PLAZA AHEAD IS CROWDED
WITH MONSTERS. HOW WILL YOU PROCEDE?"* / *"STRIDE BOLDLY FORWARD!"* /
*"DISGUISE PARTY AS MONSTERS."* / *"SNEAK, REMAINING UNSEEN"*. That grouping is
a decode result, not an inference: the three choices are operands 4-6 of the
same `0x15`, which is only visible once the variable operand count is decoded.

### The `+0x6700` discrepancy — **RESOLVED (2026-08-22)**

The interpreter reads at `buffer + PC + 0x6700` while the buffer is only
`0x1E00` (7,680) bytes. The explanation is a deliberate 8086 wrap: `045:01C8`
(and `069:03B6`) set the initial `PC` to **`0x9900`**, and

```
0x9900 + 0x6700 = 0x10000  ->  & 0xFFFF  =  0
```

so the effective index is **`(PC + 0x6700) mod 65536`** and block offset =
`(PC - 0x9900) & 0xFFFF`. `045:070B`'s `0x9900`-`0xB6FF` region check is the
independent confirmation: that range is exactly the buffer's 7,680 bytes.

### Opcode semantics — 32 of 61 named, 1 partial, 6 read in structure only (2026-08-22)

Each of these is read from its handler; `work/eclops.py <op>` prints any
handler with its far calls resolved through the thunk tables. `op1`..`opN` are
the evaluated operands, `[opN]` the ECL address operand N encodes. All 61
opcodes occur at least once in the corpus, which is itself a check on the
decoder — a wrong operand table produces an implausible histogram.

| op | name | meaning | freq |
|---|---|---|---|
| `0x09` | `SET` | `[op2] := op1`; if operand 1 is a string type (≥ `0x80`), stores the string instead (`045:0F81`) | 14.5 % |
| `0x01` | `GOTO` | `PC := [op1]` | 10.6 % |
| `0x03` | `CMP` | compare `op1` with `op2` → the six flags; string operands take `045:1853`, numbers `045:1929` | 9.4 % |
| `0x12` | `TEXT` | display the text operand | 8.7 % |
| `0x00` | `END` | stop the script — sets `DS:0x4390`, which is what `020:35E9` tests | 6.4 % |
| `0x02` | `GOSUB` | push the PC on the `DS:0x6D36` stack, `PC := [op1]` | 5.7 % |
| `0x16`-`0x1B` | `IFEQ` `IFNE` `IFLT` `IFGT` `IFLE` `IFGE` | run the next instruction only if the matching flag is set | 12 % |
| `0x13` | `RETURN` | pop the stack into the PC | 2.7 % |
| `0x25`/`0x26` | `ONGOTO`/`ONGOSUB` | jump/gosub to the `op1`-th of the N trailing address operands | 2.9 % |
| `0x2F`/`0x30` | `AND`/`OR` | `[op3] := op1 & op2` / `op1 \| op2`, byte result, **and** compares that result against 0 so a conditional can follow | 3.5 % |
| `0x04` | `ADD` | `[op3] := op1 + op2` | 2.0 % |
| `0x05` | `SUB` | `[op3] := op2 − op1` — note the order, read from `MOV AX,[BP-4] / SUB AX,[BP-6]` | 0.5 % |
| `0x06` | `DIV` | `[op3] := op1 / op2` | 0.2 % |
| `0x07` | `MUL` | `[op3] := op1 * op2` | 0.1 % |
| `0x08` | `RANDOM` | `n := op1; if n < 255 then n := n+1; [op2] := Random(n)` | 0.9 % |
| `0x2A` | `LOADIDX` | `[op3] := *([op1] + op2)` — an indexed load, the array primitive | 1.7 % |
| `0x11` | `ASKYN` | ask a yes/no question | 1.8 % |
| `0x15` | `MENU` | prompt + N choices, all text operands of the one instruction | 0.1 % |

`0x04`-`0x07` share handler `020:01A0` and `0x2F`/`0x30` share `020:0ED5`; both
switch on `DS:0x6D45`, the saved opcode. `0x08`'s `Random` is the resident
`05BB:0C94` — a 32-bit LCG, `seed := seed * 0x08088405 + 1` at `DS:0x438A`,
then `mod n`. See `analysis/executables.md` §The resident Pascal RTL
primitives; **the port has to reproduce it exactly** or no die roll matches.

**The six flags** live at `DS:0x6D3E`-`0x6D43` and are all written together by
one comparator, which zeroes the block first, so they are only meaningful
immediately after a `CMP` (or an `AND`/`OR`). For `CMP a, b`:

| flag | set when | conditional |
|---|---|---|
| `0x6D3E` | `a == b` | `0x16` |
| `0x6D3F` | `a != b` | `0x17` |
| `0x6D40` | `a < b`  | `0x18` |
| `0x6D41` | `a > b`  | `0x19` |
| `0x6D42` | `a <= b` | `0x1A` |
| `0x6D43` | `a >= b` | `0x1B` |

Comparison is **unsigned** (`JAE`/`JBE`/`JA`/`JB`). `020:0C5A` runs the guarded
instruction only when the flag is *set*, so `0x16` reads as "if equal" — which
is what fixes the earlier placeholder names.

### The ECL address space — **RESOLVED (2026-08-22)**

Every address an operand encodes goes through the region classifier `045:070B`
and then the load/store pair `045:0E2E` / `045:0C93`. Each region index is a
deliberate 16-bit wrap, the same trick as the PC's `-0x6700` bias — e.g. region
0's `0x6E00 + 2*0x4900 = 0x10000 → 0`, so the biased base *is* the region base.

| region | address range | storage |
|---|---|---|
| 0 | `0x4900`-`0x4CFF` | 16-bit words at `[DS:0x4933] + 0x6E00 + 2*addr` |
| 1 | `0x6B00`-`0x6EFF` | 16-bit words at `[DS:0x4937] + 0x2A00 + 2*addr`; reads also consult `045:07C7` and writes `045:0A90`, so some slots are live game values rather than plain storage |
| 2 | `0x9700`-`0x98FF` | 16-bit words at `[DS:0x493B] − 0x2E00 + 2*addr` |
| 3 | `0x9900`-`0xB6FF` | **bytes of the script buffer itself**, `[DS:0x493F] + 0x6700 + addr` — scripts read and write their own code |
| 4 | everything else | a hand-written window onto game state, below |

Region 4 is not storage at all — it is a switch. The identified entries:

| address | reads |
|---|---|
| `0x00B1` | `DS:0x6D34` |
| `0x00FB` / `0x00FC` | `DS:0x6D30` / `DS:0x6D32` |
| `0x033D` | party facing (`DS:0x6A0D`) |
| `0xC04B` | **party X** (`DS:0x6A0B`, sign-extended) |
| `0xC04C` | **party Y** (`DS:0x6A0C`, sign-extended) |
| `0xC04D` | **party facing / 2** (`DS:0x6A0D` divided by 2) |
| `0xC04E` / `0xC04F` | `DS:0x6A0E` / `DS:0x6A0F` |

`0xC04B`-`0xC04F` are all over the scripts, which is what makes an ECL listing
legible — `CMP C04F #0x84 / IFEQ` is a test on game state, not an opaque
address. `0xC04D` returning `DS:0x6A0D / 2` is an independent confirmation of
the dungeon-view finding that the facing global takes even values and the game
is 4-directional (§`GEO*.DAX`, `analysis/executables.md` §Unit `131`) — the
script language only ever sees 0-3.

| `0x27` | `MKITEMS` | the item-creation instruction: seven evaluated operands become seven dwords in the 28 B parameter block at `DS:0x6752`, then operand 8 selects — `0xFF` does nothing, `< 0x80` loads that block of `ITEM<region>.dax` and prepends **every** 63 B record in it to the list at `DS:0x676E`, `>= 0x80` rolls `op8 - 0x80` items from the parameter block. The region number is `DS:0x52D4`; a failed load prints `Unable to find item file` and halts | 0.5 % |
| `0x1C` | `DROPITEMS` | the inverse: `FillChar(DS:0x6752, 28, 0)` and then frees the whole `DS:0x676E` list, node by node, following the `+0x2A` far pointer — plus `DS:0x4392 := 0`, `DS:0x82AD := 0`, `DS:0x6D49 := 8` | 1.6 % |
| `0x0C` | *(partial)* | `DS:0x6D47 := op1`, `[DS:0x4937]+0x580 := op2`, `DS:0x6D48 := op3`; computes the free range ahead with `045:0489`, clamps `op2` to it, then calls `045:055D` with those and the string at `DS:0x828E`. The pieces are read; the instruction is **not** confidently named | 1.2 % |

| `0x0B` | `ADDMONS` | the encounter-setup instruction: `op1` is a monster type, `op2` a count (0 reads as 1), `op3` a combat-picture index. Loads a 285 B monster record, then appends `op2` copies of it to the participant list | 2.1 % |

| `0x29` | `ENCOUNTER` | the encounter prompt — three message strings, five option bytes, a result code written back to `[op4]` | 0.6 % |
| `0x24` | `RUNENC` | run or redraw the pending encounter; **partially read** | 1.5 % |

| `0x35` | `STOREIDX` | `*([op2] + op3) := op1` — the exact counterpart of `0x2A`'s indexed load | 0.1 % |
| `0x0D` | `ENCNEAR` | if `[DS:0x4937]+0x582 > 0`, decrement it and re-run `0x0C`'s display call with the new distance | 0.6 % |

**Smaller handlers, read but not all namable.** `0x31`, `0x33`, `0x3D`, `0x39`
and `0x0F` are short and their structure is plain, but each ends in a unit
`124`/`198` call whose meaning this pass did not chase, so they are recorded as
structure only:

| op | structure |
|---|---|
| `0x31` | if `DS:0x82A9` is set: call `124:0181`, then clear `DS:0x82A9` and `DS:0x82A6` |
| `0x33` | `DS:0x5D82 := 1`, `DS:0x5D83 += 1` on both paths; additionally clears `DS:0x82A5` when it was set |
| `0x3D` | `198:0C9A(1, 1, 0x0F, 0x0F)`, then `DS:0x82A4 := 1` |
| `0x39` | `198:0C9A(1, 0x11, 0x26, 0x16)` — a text window at rows/cols (1,17)-(38,22) — then string slot 0 and the `DS:0x5CF0` party list |
| `0x0F` | `[op2] := 198:0A17(&local, 10)`; **operand 1 is never evaluated** |

**A latent bug in opcode `0x34`.** Its handler calls `entry_0000(1)` and then
evaluates an operand whose *index* it reads out of an uninitialised local:

```
020:2E23  CALLF entry_0000(1)
020:2E28  8a 46 ff   MOV AL,[BP-1]     ; read ...
020:2E2C  CALLF entry_013F             ; ... and used as the operand index
020:2E31  88 46 ff   MOV [BP-1],AL     ; ... written only afterwards
```

`SUB SP,2` at `020:2E1D` is the only thing that touches that slot before the
read, and the far call in between builds its frame below the caller's SP, so
`[BP-1]` holds whatever the stack happened to contain. The operand tables are
64 entries and the index is a byte, so it can also read past them. The opcode
occurs **exactly once** in the whole corpus (`ECL7.DAX` `0x11` +0x437) and its
single operand is the immediate `1` — which is what the handler evidently meant
to pass. Recorded as an observation about the shipped code, not as something
the port needs to reproduce; whether it is observable at all depends on stack
contents this pass did not trace.

**`0x29` is the encounter prompt**, and it is worth setting out because `0x0C`
turns out to be the same mechanism with the prompt removed. Its fourteen
operands:

| operand | use |
|---|---|
| 1 | `DS:0x6D47` |
| 2 | `[DS:0x4937]+0x580` — a maximum distance |
| 3 | `DS:0x6D48` |
| 4 | **the result address** — the handler writes an outcome code here |
| 5-9 | five bytes into a local array, values 0-4 in the corpus |
| 10-12 | up to three message strings |
| 13-14 | two more bytes |

It then runs `045:0489`, the forward-range probe, and clamps operand 2 against
it — exactly the sequence `0x0C` performs — before three `045:055D` calls and
unit `198`'s text output. Every write back to the operand-4 address is one of
just **three values, 1, 2 or 3**; there are thirteen such store sites and no
other constant among them.

The corpus corroborates the reading independently. Real instances carry
operands 10-12 like *"THE MONSTERS STAND READY"*, *"THE MONSTERS PREPARE"* and
*"THE ORCS READY THEIR SPEARS"*, with operand 4 consistently the same variable
(`r1[0x379]` throughout `ECL1.DAX`) — an announcement plus a returned outcome.

`0x0C` sets the identical `DS:0x6D47` / `+0x580` / `DS:0x6D48` triple, runs the
same probe and clamp and calls `045:055D`, but has **no store site at all**, so
it displays without returning anything. What the five option bytes and the
three outcome codes individually mean is **not** established — that needs
`045:055D` and units `12B`/`124` read, which this pass did not do.

**`0x24`** is recorded as partial. It dispatches on two pending-encounter flags
(`DS:0x82AD`, `DS:0x829A`): with neither set it hands off to unit `041`, `035`
or `03B` depending on `[DS:0x4937]+0x6D8` and `+0x5C4`; with one set it runs the
range probe and clamp and, when `[DS:0x4933]+0x1CC` says the 3D view is not up,
loads the `BACPAC` backdrop (`CS:0x1860`) and a series of `ICON` assets
(`CS:0x1867`) through `147:0022` and `147:01CA`. Which of those paths is
"start combat" is not determined without reading those units.

**`0x0B` in full**, because it says a lot about three other formats. It bails
immediately if `DS:0x4392` is already `0x3F`, then:

```
045:0423(op1, &rec, &items, &second)   ; GetMem(0x11D=285), load record op1
                                       ;   through unit 0BE (the character/save
                                       ;   unit), then hand back rec[+0xC8] and
                                       ;   rec[+0x7F]
020:04BA  Move(rec, local, 0x11D)      ; the 285 B record
020:0516  buf := "CPIC"                ; CS:0x448, a Pascal short string
020:0529  147:01CA(buf, op3, DS:0x6D49); load the combat picture
020:052E  walk [DS:0x5CF4] to the end via +0x104, append a GetMem'd copy
020:058B  INC [DS:0x4392]              ; per monster, stop at 0x3F
```

`147:01CA` is the game's generic asset loader: it takes the first five
characters of the name and compares them against `CHEAD`, `CBODY`, `COMSPR` and
friends, so `"CPIC"` + index is the monster's combat portrait out of
`CPIC*.DAX`. `DS:0x6D49` is the file number, which opcode `0x1C` initialises
to 8.

That gives three new fields in the **285 B character/monster record**, all far
pointers, all read from code rather than inferred from a UI layout:

| offset | meaning |
|---|---|
| `+0x7F` | a second list head, contents not identified |
| `+0xC8` | inventory list head — confirmed here for the third time |
| `+0x104` | **next participant**, the link the encounter list is built on |

and four interpreter globals:

| global | meaning |
|---|---|
| `DS:0x5CF4` | head of the encounter participant list (285 B records, `+0x104`) |
| `DS:0x5CF0` | a second participant list head; opcode `0x00` saves and restores it |
| `DS:0x4392` | participant count, **hard cap 63** — both `0x0B` entry and its inner loop test it |
| `DS:0x6D49` | asset file number for `147:01CA`, set to 8 by `0x1C` |

**`045:0489` — the forward-range probe, and the facing encoding.** Called with
(party X, party Y, facing), it walks forward up to **two** squares, asking unit
`131`'s GEO wall query (`131` thunk 4) whether each step is blocked, and returns
how many squares are clear. If `[DS:0x4933]+0x1CC` is zero — not in the 3D view
— it returns 2 unconditionally. Its stepping arithmetic is where the cardinal
directions are actually written down:

| facing | step |
|---|---|
| `0` | `Y -= 1` (north) |
| `2` | `X += 1` (east) |
| `4` | `Y += 1` (south) |
| `6` | `X -= 1` (west) |

Only even values are handled, which is the script-side confirmation of the
dungeon-view conclusion that the game is 4-directional — and it agrees with
region 4's `0xC04D`, which hands scripts `facing / 2`.

**Still untouched: 22 opcodes** — `0x0A 0x0E 0x10 0x14 0x1D 0x1E 0x20 0x21
0x22 0x23 0x28 0x2B 0x2C 0x2D 0x2E 0x32 0x36 0x37 0x38 0x3A 0x3B 0x3C`. Each has a handler address and an operand count
(`HANDLER` and `OPERANDS` in `work/ecl.py`) and nothing more. The heaviest are
`0x0B` (2.1 %, `020:044D`, allocates and copies — some list/inventory
operation), `0x1C` (1.6 %), `0x24` (1.5 %, calls into five other units and
reads the party position — probably the encounter/combat entry), `0x2B`
(1.3 %), `0x3A` (1.2 %, heavy string formatting via unit `198`) and `0x0C`
(1.2 %, evaluates three operands then tests them against the party position via
`045:0489`).

### What earlier passes got wrong here, and why

Kept because each was a plausible reading that cost real time:

1. **The classifier at `020:0B1A` was taken as the operand-count authority.**
   It is only the conditional-skip helper. The handler at the other end of the
   dispatcher is what consumes the stream, and it disagrees on five opcodes.
2. **`0x00` was treated as a script separator to skip over.** It is the `END`
   instruction, with a handler that stops the execute loop.
3. **The block was assumed to be a flat stream that a linear walk should
   traverse**, and the ~6 % it managed was read as "one small unidentified
   construct". Two things were wrong: the missing construct was four opcodes
   with stream-supplied operand counts, and the layout was never linear at all.
4. **Operand types were briefly used as a validity check.** `entry_0000` treats
   any unlisted type as a plain 2-byte operand, so there is no invalid-type
   signal; the check wrongly rejected 10 of 29 blocks.
5. **A byte scan for `[op][0x80][len]` was used to recover text.** It found
   2,904 hits of which ~1,000 are garbage that happens to unpack as capitals,
   and its offsets are not instruction starts. It is superseded by the decoder,
   which anchors all 1,826 strings to real instructions.

- `SPRIT*.DAX` — **RESOLVED (2026-08-22)**: a multi-frame sub-container, one
  monster drawn at each of the dungeon view's distance ranks.

  The loader is `12B:00A8`, reached from `045:055D` — the routine the ECL
  encounter opcodes `0x0C`, `0x0D` and `0x29` all call — which selects between
  the `SPRIT` and `PIC` name constants at `045:+0x553` and `+0x559`. It caches
  the last name (8 chars at `DS:0x6A68`) and index (`DS:0x6A71`) and returns
  early when the same asset is asked for twice.

  ```
  block   := [u8 count] [entry × count]
  entry   := [u32LE duration]                          ; see §The u32 frame tag
             [u16LE height] [u16LE widthBytes]     ; the image-header pair
             [13 B, copied field-by-field into the allocated image record]
             [height * widthBytes * 4 B pixels]    ; 4 bpp, as every other image
  ```

  The 13 bytes go to image-record `+4` (2 B), `+6` (2 B, but the read cursor
  advances 3), and `+9` (8 B), which is the same 17-byte image header the rest
  of the corpus uses — `12B:0299`-`0x02F5`. The leading 4 bytes were recorded
  as unidentified when this was first written; they are the **frame duration**,
  the same field `.PIC` carries, since `12B:00A8` is also the `.PIC` loader
  (§The `u32` frame tag).

  **Proved by the offset chain, not by plausibility:** walking `count` entries
  with that arithmetic lands exactly on the block length for **88 of 88**
  `SPRIT` blocks, no slack anywhere. 82 blocks hold 3 frames, 6 hold 2.

  **And looked at**, per this project's rule for graphics. `SPRIT1.DAX` block
  `0x02` decodes to 48×80, 32×65 and 24×49 pixels — the same horned humanoid
  with weapon and shield, drawn three times at decreasing size. That is one
  monster at the three depth ranks the dungeon view uses
  (§`WALLDEF*.DAX`, `analysis/executables.md` §Unit `131`). Renders:
  `work/probe/sprit/`.

  The same walk fits **3 of the 8 `FINAL*.DAX` blocks** (`FINAL5.DAX` `0x02` is
  four 88×88 frames) and no other family — consistent with `12B:0106`
  special-casing the `FINAL` name, so that family evidently has two shapes.
  Every other `.DAX` image family is the plain single-image header already
  documented above.
- `ITEMS` (2,050 B, no extension) — the master item-**type** table.
  **RESOLVED (2026-08-22): a 2-byte header + 128 × 16 B records**, and the
  63 B item record's `+0x2E` is the index into it.

  The loader is in unit `069` (around `069:068B`), found from the `\x05ITEMS`
  short string at `069:+0x0025`. It builds the path from a per-region table at
  `DS:0x2628` with a **30-byte stride** indexed by the region number
  `DS:0x52D4`, then `Reset` (`05BB:141D`, `INT 21h AH=3Dh`) with record size 1,
  **`Seek` to byte 2** (`05BB:1570`) — skipping the 2-byte header — a
  `BlockRead` of `0x810` bytes (`05BB:1508`, `AH=3Fh`) into the fixed buffer at
  `DS:0x54E0`, and `Close` (`05BB:149E`). `0x810` is simply more than the
  2,048 that remain, so the whole payload lands in the buffer.

  `2048 / 16 = 128` exactly. The indexing is explicit in two places:

  ```
  058:12A0   MOV AL,ES:[DI+0x2E]      ; the item record's type field
  058:12A8   SHL DI,4                 ; × 16
  058:12AC   ADD DI,0x54E0            ; into the ITEMS buffer
  058:12BB   CALLF Move(..., 0x10)    ; copy the whole 16 B record
  ```

  and again at `0C9:157A`. **Checked against every item in the game:** all
  **667** records in `ITEM*.DAX`, `MON*ITM.DAX` and `CHRDATA*.ITM` have
  `+0x2E` in **1-93**, none at or above 128. 82 distinct types are used; 32 of
  the 128 slots are entirely zero.

  Field 0 of an `ITEMS` record is a selector — four sites test it against
  `2`, `0x0A`, `0x0C` and `0x0E` (`10A:020A`, `0E2:3213`, `0E2:047C`,
  `0E2:3229`). Its distribution is mostly `0`-`12`, plus an odd cluster at
  indices 74-91 where the value **equals its own index** in 9 of 11 cases
  (the exceptions being 79→78 and 84→80). That pattern is recorded, not
  interpreted. The other 15 bytes are undecoded.

  ~~`2050 = 2 + 2048`, and `2048 / 63` is not integral, so it is *not* a plain
  array of the 63-byte item record~~ — that reasoning was right and the
  conclusion held; what it could not supply was the actual record size, which
  needed the consumer. The `GetMem(0x800)` in `069`'s `entry_002D` noted
  earlier is a *different* buffer from the static `DS:0x54E0` this loader
  fills.
- **The 16 B `ITEMS` record — fields partially decoded (2026-08-22).** The
  consumer is `058:129A`, which `Move`s a record into a local and scores it:

  ```
  058:12C0   score := f9 * f10
  058:12DB   if itemRecord[+0x32] > 0: score += itemRecord[+0x32] << 3
  058:12FA   if f11 > 0:               score += f11 * 2
  058:130F   if itemRecord[+0x2E] == 0x55 and <a character condition>: score := 8
  058:133F   test f14 & 8
  ```

  | field | reading | evidence |
  |---|---|---|
  | 0 | selector | tested against `2`, `0x0A`, `0x0C`, `0x0E` at four sites |
  | 2, 3 | a **(count, sides) dice pair** | `f3` takes only `{0,1,2,3,4,6,8,10,12,20}` across all 96 live entries — the polyhedral set — and the sibling pair is multiplied as `count × sides` |
  | 9, 10 | a **second dice pair** | same value set; `058:12C0` computes `f9 * f10` as a score |
  | 11 | added doubled to the score | `058:12FA` |
  | 13 | a **7-bit mask** | never exceeds `0x7F` in any of the 96 live entries, all seven bits used, all-ones the commonest value (25 entries) |
  | 14 | flag bits | bits 0-4 and 7 occur; bit 3 tested at `058:133F` |

  The two dice pairs are equal in 65 of 96 entries. Cross-checked against named
  items, using the item record's name field and its `+0x2E` index:

  | item | type | pair A | pair B |
  |---|---|---|---|
  | Flail | 12 | 2d4 | 1d6 |
  | Silver Dagger | 8 | 1d3 | 1d4 |
  | Dart | 9 | 1d2 | 1d3 |
  | Arrow | 73 | 1d6 | 1d6 |
  | Quarrel | 28 | 1d4 | 1d4 |
  | Javelin | 21 | 1d6 | 1d6 |
  | Banded Mail | 57 | — | — |
  | Diamond Necklace | 70 | — | — |

  Weapons carry dice, armour and treasure carry zeros, and where AD&D gives a
  weapon the same damage against both size categories the two pairs are equal —
  so pair A is the vs-large column and pair B the vs-small/medium one. **That
  last mapping is corroboration from the game's own subject matter, not
  something read out of the binary**; what the code proves is that the two
  pairs are `(count, sides)` and that one of them is multiplied out. The other
  nine fields are undecoded.

- `SAVGAMA.DAT` (13,137 B) — the shipped savegame. **RESOLVED (2026-08-22):
  it is a straight dump of the ECL interpreter's state**, ten `BlockWrite`s
  whose sizes add up to the file length exactly.

  The writer is `0BE:1770`-`0x1880` (the reader at `0BE:1EB0` is the same
  sequence with `BlockRead`), reached from the `\x06savgam \x04.dat` constants
  at `0BE:+0x151A` and `+0x1CA0`; the path prefix is `DS:0x52D8`, which is
  `POOL.CFG` line 4 (§`analysis/dos-oracle.md`).

  | offset | size | source |
  |---|---|---|
  | 0 | 1 | `DS:0x52D4` — the **region number** |
  | 1 | 2,048 | `[DS:0x4933]` — **ECL variable region 0** (1,024 words) |
  | 2,049 | 2,048 | `[DS:0x4937]` — **ECL variable region 1** |
  | 4,097 | 1,024 | `[DS:0x493B]` — **ECL variable region 2** (512 words) |
  | 5,121 | 7,680 | `[DS:0x493F]` — **the ECL script buffer**, region 3 |
  | 12,801 | 5 | `DS:0x6A0B` — the party block: X, Y, facing, `+0x6A0E`, `+0x6A0F` |
  | 12,806 | 1 | `DS:0x495B` |
  | 12,807 | 1 | `DS:0x4954` |
  | 12,808 | 1 | a stack local |
  | 12,809 | 328 | a stack local |
  | | **13,137** | = the file size, exactly |

  The four ECL buffers are precisely the four regions the address classifier
  `045:070B` defines (§The ECL address space) — 1,024 + 1,024 + 512 words and
  the 7,680-byte script buffer. A Pool of Radiance save is, essentially, the
  script interpreter's memory.

  **Verified against the shipped file, using the ECL decoder as the oracle:**
  byte 0 reads **2**, and the 7,680-byte slice at +5,121 parses as an ECL block
  whose five entry points are `0x14, 0x75, 0x10E, 0x149, 0x15E` — *identical to
  `ECL2.DAX` block `0x14`*, i.e. region 2's script, exactly as the region byte
  says. `work/ecl.py`'s control-flow walk covers 99.3 % of that slice (against
  a 97.7 % corpus average, the difference being that a live buffer has had its
  self-modifying region 3 written to) and recovers real prose from it —
  `" A BUGBEAR LEADING A PARTY OF"`. The party block reads X=15, Y=4,
  facing=6, and 6 is west under the facing encoding read from `045:0489`.

  Four independent results — the savegame layout, the ECL block format, the
  region numbering and the facing encoding — agree on the same bytes.

  The last two records (1 B and 328 B) come from stack locals the writer fills
  earlier and are **not** traced to their origin.
- `PALS` — **no palette file ships**. The EGA palette is presumably programmed
  by the code, so the 16-colour default used by `work/gbimage.py` is an
  assumption until the register writes in `GAME.OVR` are read.
