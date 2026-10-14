# `.LFD` / `.LFB` — the LucasArts resource container (todo P2.1)

**Status: RESOLVED (container) + RESOLVED for 8 of 15 record types;
`PANL` structure-only, `SHIP` header-only.**
Decoded 2026-08-22 from the bytes alone; every model below was validated over
**every record of that type in the whole tree** (`game/SWTieCD/TIECD`, 175
files, 2,184 records), not on samples. Regression check:

```
python3 work/lfd_audit.py game/SWTieCD/TIECD      # exit 0 == every invariant holds
```

Current output (2026-08-22):

```
files: 175   with RMAP index: 105   without: 70
DELT 370 decoded 370/370      SHIP 234  header only (234/234)
ANIM 355 decoded 355/355      MASK  70  consumer identified; encoding TBD
PLTT 296 decoded 296/296      XACT  56  (TBD)
VOIC 239 decoded 239/239      BMAP  26  (TBD)
GMID 179 decoded 179/179      FONT   5  (TBD)
FILM 149 decoded 149/149      MTRX   5  (TBD)
BLAS 103 decoded 103/103
PANL  70 structure 70/70
TEXT  27 decoded  27/27
failures: 0
```

Tools: `work/lfd.py` (container), `work/lfd_delt.py` (payload decoders),
`work/lfd_extract.py` (→ PNG), `work/lfd_audit.py` (whole-tree check).

## 1. Container — RESOLVED

A `.LFD` is a flat chain of records, each a 16-byte header followed by its
payload. There is no directory of file offsets and no alignment or padding.

```
struct LfdRecord {
    char  type[4];      // 'RMAP' 'DELT' 'ANIM' 'PLTT' 'PANL' 'MASK' 'TEXT'
                        // 'VOIC' 'BLAS' 'GMID' 'FILM' 'SHIP' 'XACT' 'BMAP'
                        // 'FONT' 'MTRX'
    char  name[8];      // zero-padded ASCII, not NUL-terminated when 8 chars
    u32le length;       // payload bytes, excluding this 16-byte header
};                      // followed by `length` payload bytes
```

**Correction (2026-08-22).** The previous reading in `data-formats.md` —
*"`[u32 "RMAP"] [ascii "resource"] [u8 version (30|50|70)]` then
`N × (type(4) + name(12) + offset(4))`"* — is **withdrawn**. The name field is
**8** bytes, the trailing u32 is a **length**, not an offset, and there is no
version byte: the `30|50|70` bytes read as a "version" were the low byte of the
first entry's length field. `RMAP` is not a header, it is an ordinary record
that happens to come first.

Verified invariants (all 175 files):

1. Records chain contiguously from offset 0; the last one ends **exactly** at EOF.
2. **105 files open with an `RMAP` record.** Its payload is the index: a copy
   of every following record's 16-byte header, in file order. Length is always
   a multiple of 16, the entry count always equals the record count, and every
   entry matches its record's `(type, name, length)` byte for byte.
3. **70 files have no `RMAP`** — all of `CP320/` and `CP640/`; they start
   straight at the first `PANL`. This is a per-directory split, not a defect.
4. `.LFB` is the same format as `.LFD` (see §7).

## 2. `PLTT` — palette range — RESOLVED (296/296)

```
u8 first, u8 last            // inclusive palette index range
u8 rgb[3][last-first+1]      // one RGB triplet per index, in order
u8 k                         // count of 4-byte trailer entries
u8 trailer[4][k]
```

Component bytes span the full `0x00..0xFF`; they are **not** stored in the
6-bit VGA DAC range. The cockpit loader at `FUN_00043B6C` shifts the loaded
palette bytes right by two before the active cockpit palette is used, so the
runtime VGA-facing values are 6-bit. The trailer semantics remain TBD.

`k` is **0 in 293 of 296** records. The three with `k > 0` are:

| record | k | trailer bytes |
|---|---|---|
| `RESOURCE/CITY.LFD` `PLTT:palace02` | 2 | `32 01 d0 d1` · `32 07 d2 d6` |
| `RESOURCE/CITY.LFD` `PLTT:flash1` | 2 | `32 01 d0 d1` · `32 07 d2 d6` |
| `RESOURCE/CREDITS.LFD` `PLTT:colors` | 1 | `32 13 8f 60` |

Their semantics are **TBD** — three samples is too thin to name the fields, and
both `CITY.LFD` names (`flash1`, `palace02`) plus the shared leading `0x32`
would make "colour-cycling range" a guess, not a reading. Left undecoded.

## 3. `DELT` — sparse paletted bitmap — RESOLVED (370/370)

```
i16 left, top, right, bottom          // inclusive bounding box, screen coords
repeat until a u16 0x0000 terminator:
    u16 v                             //  v>>1 = pixel count of this span
    i16 x, y                          //  span start, absolute screen coords
    if (v & 1) == 0:  u8 px[v>>1]                 // raw
    if (v & 1) == 1:  RLE, until v>>1 pixels emitted:
                          u8 op
                          op & 1 :  (op>>1) copies of the next byte
                          else   :  (op>>1) literal bytes follow
```

Every payload ends exactly at its terminator — no trailing bytes anywhere.
Spans are sparse: a pixel no span covers is **transparent**, and only **77 of
370** records cover their whole bounding box (the rest are cut-outs composited
over a background). Both encodings are in use: 46,637 RLE spans vs 33,593 raw.

Proof beyond the invariants: `RESOURCE/AWARDS.LFD` `DELT:medlroom`
(320×200) renders as the Imperial medal-ceremony hall, in correct colours,
using its own same-named `PLTT`.

## 4. `ANIM` — DELT sequence — RESOLVED (355/355)

```
u16 frameCount
frameCount x { u32le length; u8 delt[length]; }   // each a §3 DELT payload
```

5,467 frames total; frame counts run 1..176. Each frame carries its own
bounding box, so frames may differ in size and position.

**Two degenerate frames exist in the tree** and are data, not a decode error:
`RESOURCE/EMPIRE.LFD` and `RESOURCE/INSTALL.LFD`, both `ANIM:cursors` frame 4 —
a 10-byte payload whose box is `(15973, 15960, -27, -40)` followed immediately
by the terminator, i.e. no spans. `lfd_extract.py` skips them by name in its log.

## 5. `PANL` — cockpit panel — **STRUCTURE RESOLVED, PIXELS NOT** (70/70)

**Correction (2026-08-22). The previous reading was wrong and its images were
wrong-but-plausible** — the exact failure mode `F030Method/METHOD.md` warns
about. Withdrawn:

> ~~"No header at all; a byte stream, laid out row by row from the top left:
> `0xFD cnt val` = run of `cnt` pixels of colour `val`; `0xFE` = end of row, the
> rest of the row is transparent; anything else = one literal pixel. … no row
> ever exceeds [the screen width]. Row counts land on exactly two values per
> resolution … 190 / 201 / 457 / 481."~~

That model ignored two escape bytes, so it desynchronised on the **29,070
`0xFC` opcodes** in the tree and rendered them as pixels. The extra row in
190/201/457/481 was the desynchronisation showing up as an unterminated
remainder.

The truth comes from the blitter, **`FUN_0004977C`** (1,561 B, found by scanning
every validated function start for `cmp` against `0xFD`/`0xFE`; it is the only
one that handles both). Its row loop is literally:

```c
while ((b = *p) != 0xfe) {
    if      (b == 0xfb) { bias = p[1];              p += 3; }
    else if (b == 0xfc) { x += tbl1[p[1]]; ...      p += 2; }
    else if (b == 0xfd) { w = *(u16 *)(p + 1);      p += 3; }
    else                { w = (b & mask) | (((b >> shift) + bias) << 8); p += 1; }
    ...                                     /* emit: low byte -> width table,
                                               high byte -> colour          */
}
p++;                                        /* consume the 0xFE */
```

So the opcode set is:

| byte | size | meaning |
|---|---|---|
| `0xFB` | 3 | sets a **colour bias** added to subsequent literals |
| `0xFC` | 2 | **advances the x position** via two runtime tables (a transparent skip) |
| `0xFD` | 3 | **run**: u16 operand — low byte indexes a width table, high byte is the colour |
| `0xFE` | 1 | end of row |
| `0xFF` | 1 | **end of panel**, followed by 0–2 bytes of `0x0A` padding |
| else | 1 | **literal**, split by a mask/shift held in the panel struct into (width index, colour) |

Verified over all 70 records: the walk consumes each payload exactly, every one
ends on `0xFF` (there are exactly 70 `0xFF` bytes in all PANL payloads — one
each), and the row counts are exactly

| | 189 rows | 200 rows | 456 rows | 480 rows |
|---|---|---|---|---|
| `CP320/` | 28 | 9 | – | – |
| `CP640/` | – | – | 26 | 7 |

**200 and 480 are the screen heights**, which the wrong model never produced.

**Pixels are not decodable statically.** A literal's split into width and colour
uses a mask and shift held in the panel struct (`param_2 + 0x7884` / `+ 0x788D`),
and both `0xFC` and the emit path index tables at linear `0x1B854` and `0x1BA54`
that the game **builds at run time** — reading those addresses out of the file
yields code, not a table. `decode_panl()` therefore returns the **token stream**,
not pixels, and `lfd_extract.py` no longer renders PANL at all (the tree now
extracts 5,835 PNGs, down from 5,905). Recovering the pixels needs either the
init code that fills those tables or a runtime dump — i.e. P3.2.

The standalone `CP320/*.PNL` / `CP640/*.PNL` files remain a separate format
(P2.2); they were never covered here.

## 6. Other resolved record types

- **`TEXT` (27/27)** — `u16 blockCount`, then per block `u16 length` + that many
  bytes of NUL-separated strings. 317 blocks, 2,303 strings across the tree.
  `RESOURCE/TITLE.LFD` `TEXT:title` is the opening crawl (1 block, 19 lines,
  starting `At the battle of Yavin`); `RESOURCE/BATTLE1.LFD` `TEXT:battle1` is
  10 blocks (`Battle One` / `Battle One Cutscene` / `AFTERMATH OF HOTH` / …).
- **`VOIC` (239/239) and `BLAS` (103/103)** — plain **Creative Voice File**
  (`.VOC`). All 342 carry the `Creative Voice File\x1a` magic, version
  **0x010A**, data offset **26**; blocks seen are type 1 (sound data, 346), 6
  and 7 (repeat / end-repeat, 14 each) and the type-0 terminator. `VOIC` and
  `BLAS` are byte-identically structured — the type tag distinguishes use
  (speech vs. blaster SFX by directory), not format. Sample-rate bytes are
  165, 166, 161 and 211.
- **`GMID` (179/179)** — `MIDI` magic + `u32be` payload length, then chunks:
  `MDpg` (LucasArts/iMUSE, 179), `MThd` (179), `MTrk` (187). The chunk walk ends
  exactly on the payload end in every record. The **4 standalone `.GMD` files**
  (`RESOURCE/BATTLE.GMD`, `CLOAKTST.GMD`, …) are the same format and also walk
  clean, so `.GMD` is resolved with `GMID`.

## 6b. `FILM` — the scene sequencer — STRUCTURE RESOLVED (149/149)

The block list answers §9's old open question "which palette belongs to which
image": a FILM *is* the set of resources one scene plays.

```
u16 version        // 4 in all 149 records
u16 frameCount
u16 blockCount
(blockCount+1) x {
    char type[4]; char name[8]; u32le length;   // NOTE: length INCLUDES this
                                                // 16-byte header, unlike the
                                                // LFD container's records
    u16 typeCode;                               // VIEW=2 VOIC=5 PLTT=4
                                                // DELT=ANIM=CUST=3 END=1
    u16 chunkCount;
    chunkCount x { u16 time; u16 lenBytes;
                   u16 opcode; u16 params[(lenBytes-6)/2]; };
    u16 terminator;                             // 2 in all 2,939 non-END blocks
}
```

**Field-order correction (2026-08-22).** ~~"`chunkCount x { u16 opcode; u16
lenBytes; u16 args[(lenBytes-4)/2] }`"~~ is **withdrawn**: the first word is a
**time/frame stamp** and the **opcode is the third word**. Both readings parse
every record, so a census settled it — the first word takes **532 distinct
values** (dominated by 0, which is what a delay looks like) while the third
takes **20**, and those 20 partition cleanly by block type. The clincher: under
the corrected reading **every one of the 20 opcodes has a single fixed
parameter count** (none ragged), which a wrong field assignment does not
produce.

A chunk with `lenBytes == 4` carries no opcode — it is the block's **end
marker**. There are 2,940 against 2,939 non-END blocks: exactly one per block
except `RESOURCE/SCENE2.LFD` `FILM:scene2_f`, whose `VIEW` block has two.

The last block is always `END` (typeCode 1, no chunks, 2-byte payload). Every
other block names an LFD record **of its own type in the same file**. Verified
across all 149 records / 2,939 blocks / **26,266 chunks**, 0 failures. Block
census: DELT 880, ANIM 842, VOIC 591, PLTT 452, VIEW 149 (always exactly one,
always first), END 149, CUST 25. Chunk lengths are 6 B (1 arg, 16,460×), 8 B
(3,326), 12 B (3,065), 4 B (no args, 2,940 — one per block, always last), 18 B
(475).

Chunk lengths are 6 B (opcode, no params — 16,460×), 8 B (1 param, 3,326),
12 B (3 params, 3,065), 4 B (the end marker, 2,940), 18 B (6 params, 475).

### The opcode table — **20 opcodes, measured** (semantics still TBD)

Each opcode has one fixed parameter count and occurs only in certain block
types. This is a census, not an interpretation — nothing here is *named*:

| op | count | params | block types |
|---|---|---|---|
| 3 | 9,775 | 0 | ANIM CUST DELT PLTT VIEW VOIC — the only universal one |
| 4 | 1,102 | 3 | ANIM CUST DELT |
| 5 | 1,015 | 3 | ANIM DELT |
| 6 | 1,406 | 0 | ANIM DELT |
| 7 | 1,176 | 1 | ANIM DELT |
| 8 | 1,629 | 1 | ANIM DELT |
| 9 | 183 | 0 | ANIM CUST DELT |
| 10 | 115 | 0 | ANIM DELT |
| 11 | 131 | 3 | ANIM DELT |
| 12 | 2 | 3 | DELT |
| 13 | 3,857 | 0 | ANIM CUST DELT |
| 14 | 156 | 1 | ANIM DELT |
| 15 | 794 | 0 | **PLTT only** |
| 18 | 365 | 1 | **VIEW only** |
| 19 / 20 / 23 / 24 | 34 / 63 / 16 / 217 | 0 | **VOIC only** |
| 25 | 815 | 3 | **VOIC only** |
| 28 | 475 | 6 | **VOIC only** |

The split is legible: 3 is shared by everything, 4–14 belong to the image
actors (DELT/ANIM/CUST), 15 is palette-only, 18 view-only, 19–28 audio-only.
The time word takes 531 distinct values, 7,967 of them 0.

### The dispatch — **FOUND** (2026-08-22)

The opcode is a **jump-table index**, which is why no compare chain mentions 15,
18, 25 or 28. Two tables in `XFILM.C`, each reached via the LE fixup index
(`work/audit_fixups.py --target=1:<obj1 offset>` finds the one instruction that
references each):

```
000a8888  mov dx, word ptr [eax + 2]        ; eax = chunk+2, so this is the OPCODE
000a888f  sub edx, 4
000a8892  add eax, 4                        ; eax now = chunk+6 = first param
000a8895  cmp dx, 0xa
000a8899  ja  0xa89af                       ; default
000a88a5  jmp dword ptr cs:[edx*4 + 0x9882c]   ; 11 entries -> opcodes 4..14

000a8aa3  mov dx, word ptr [esi + 2]
000a8aac  sub eax, 0x13
000a8ab2  cmp ax, 9
000a8ac1  jmp dword ptr cs:[eax*4 + 0x98a70]   ; 10 entries -> opcodes 19..28
```

**This independently confirms the field-order correction above.** The bounds are
`4..14` and `19..28` — exactly the two opcode groups the data census produced,
arrived at from the code with no reference to the data. And `19..28` cannot be a
*length* (lengths are even and ≤18), which settles that the dispatched word is
the opcode.

Two more 4-entry tables (`0x0A7D78`, `0x0A8258`) dispatch `sub 2 / cmp 3` =
**typeCode 2..5** — the `VIEW=2, DELT/ANIM/CUST=3, PLTT=4, VOIC=5` values above.

| op | params | handler | calls → module |
|---|---|---|---|
| 4 | 3 | `0x0A88AD` | `0x0928EC` XACTOR.C |
| 5 | 3 | `0x0A88CE` | `0x0933D8` XACTOR.C |
| 6 | 0 | `0x0A88EF` | `0x092C2C` XACTOR.C |
| 7 | 1 | `0x0A88FE` | `0x092DE0` XACTOR.C |
| 8 | 1 | `0x0A8912` | `0x092EEC` XACTOR.C |
| 9 | 0 | `0x0A8926` | no call — stores a u16 at **actor+0x5A** |
| 10 | 0 | `0x0A8932` | no call — stores a u16 at **actor+0x5C** |
| 11 | 3 | `0x0A893E` | `0x09ABB0` **XRECT.C**, on **actor+0x18** |
| 12 | 3 | `0x0A8960` | `0x09ABB0` **XRECT.C**, on **actor+0x20** |
| 13 | 0 | `0x0A8982` | branches on a word → `0x091710` / `0x091770` XACTOR.C |
| 14 | 1 | `0x0A89A0` | `0x0932CC` XACTOR.C |
| 19 | 0 | `0x0A8AC9` | `0x095874`, `0x095898` (audio, unattributed) |
| 20 | 0 | `0x0A8AEA` | `0x0958BC` |
| 21 | — | `0x0A8AF5` | `0x0958E0` — **handler exists, opcode never occurs in the data** |
| 22 | — | `0x0A8B03` | `0x095900` — likewise |
| 23 | 0 | `0x0A8C01` | `0x095AAC` |
| 24 | 0 | `0x0A8C1E` | no call |
| 25 | 3 | `0x0A8B16` | `0x095874/898/8E0/900` |
| 28 | 6 | `0x0A8B73` | the same four plus `0x095920`, `0x095940` |
| 26, 27 | — | — | both point at the default target `0x0A8C25` — **not implemented** |

What this gives without naming anything: 9 and 10 write two **adjacent u16
fields** of the actor; 11 and 12 run the **same XRECT.C routine** over two
different sub-structures at actor+0x18 and +0x20; 13 is a **two-way branch** on
a word; 25 and 28 are a **nested pair** in the audio layer (28 calls 25's four
helpers plus two more). Opcodes 3, 15 and 18 are outside both tables and are
handled before the dispatch.

### The one-word over-read — characterised (2026-08-22)

Every handler reads **one word past its own chunk**: opcode 4 (3 params, len 12)
loads chunk+6/+8/+10 *and pushes* chunk+12; opcode 14 (1 param, len 8) loads
chunk+6 and chunk+8. Both halves of the conflict are now nailed down:

- **The stride really is `len`.** Re-tested explicitly: `stride = len` tiles the
  payload exactly in **149/149** records, `stride = len+2` fails in **149/149**.
  The container decode is not in doubt.
- **The over-read word really is used.** The decompiled callees consume it —
  opcode 8's writes `actor+0x4E = param0` *and* `actor+0x50 = <over-read>`;
  opcode 14's sets bit 0 of `actor+0x47` from param0 and **bit 1 from the
  over-read**.
- **And it does not look like a free-running time stamp.** Across the whole
  tree the word after an opcode-7/8 chunk takes only **7 distinct values**
  (0, ±64, ±128, ±192) and after an opcode-14 chunk only **2** (0 and 1,
  matching its boolean use) — against **531** distinct values for the time word
  overall.

Concretely, in `ABACK.LFD` `FILM:award11`:

```
word11  time=0  len=8  op=14  params=[1]     <-- this chunk
word15  time=0  len=6  op=13  params=[]      <-- handler also reads word15 (=0)
```

So the handler reads the **following chunk's first word** as its second
parameter, and that value is 0 in 149 of 156 opcode-14 cases and 1,141 of 1,176
opcode-7 cases — i.e. usually a no-op. Whether that is a latent bug in the film
player or deliberate field aliasing is **not decidable from the data**, and it is
left open rather than guessed. It does not affect decoding.

### What the handlers do to the actor (from the decompiled callees)

Field effects only — still no opcode names:

| op | effect |
|---|---|
| 6 | `actor+0x44 = param0` (u16) |
| 7 | if a hook pointer at `+0x0C` of a looked-up object is non-null, call it; else `actor+0x4A = param0`, `actor+0x4C = over-read` |
| 8 | `actor+0x4E = param0`, `actor+0x50 = over-read` |
| 9 | `actor+0x5A = param0` |
| 10 | `actor+0x5C = param0` |
| 11 / 12 | same **XRECT.C** routine `0x09ABB0` on `actor+0x18` / `actor+0x20` |
| 13 | two-way branch on a word → `0x091710` / `0x091770` (XACTOR.C) |
| 14 | bit 0 of `actor+0x47` from param0, bit 1 from the over-read |

Every one of these callees opens with the same `FUN_0009F20C(1)` trace call and a
`DAT_00012F48 >> 0x10 > 2` verbosity guard — the (file, line) logger of
`functions.md` §5c, which is what made the module map possible.

Sources: `work/ghidra_export/xactor.c` (92 functions), `xrect.c` (17).

### Applied: palette selection (§9 item 7, now largely answered)

`lfd_extract.py` uses a record's FILM to decide which `PLTT`s are live for it,
falling back to "every PLTT in the file" only when no FILM references it.
**593 of 725 DELT+ANIM records (82 %) are referenced by a FILM; in the files
that actually have more than one palette — where the choice matters — it is
470 of 545 (86 %).** A same-named `PLTT` is still applied last, since
frame-accurate ordering needs the opcodes.

Known limitation, unfixed on purpose: a record in **no** FILM still gets every
palette in its file merged, which renders wrong where a file holds many —
`RESOURCE/AWARDS.LFD` `DELT:trnships` is the clear case (9 palettes; no FILM in
the tree references it). Pairing it with `PLTT:trnshps` on the strength of the
similar name would be a guess, so it is left visibly wrong.

## 6c. `SHIP` — 3-D models — **HEADER RESOLVED, geometry TBD** (2026-08-22)

234 records in `RESOURCE/`, `RES320/` and `RES640/` `SPECIES*.LFD`, but only
**78 unique models** (§8). Sizes 509 B (`ASTROID1`) to 32,577 B.

Header, every field verified across all 78 unique records:

```
0x00 u16  length      // == record length - 2, in all 78 (self-describing)
0x02 u16  0x0100      // identical in all 78
0x04 u16  0           // all 78
0x06 u16  0           // all 78
0x08 u16  spanX
0x0A u16  spanY
0x0C u16  spanZ
0x0E u16  spanMax     // == max(spanX, spanY, spanZ), all 78
0x10 u32  ?           // semantics unknown -- see below
0x14 i16  minX, minY, minZ, maxX, maxY, maxZ    // bounding box
0x20 u8   ?           // observed 1..39
0x21 u8   ?           // observed 1..5
0x22 u16  ?           // 0 in 72 records, 2 in 6
```

The spans are **unsigned**: `spanX == (maxX - minX) & 0xFFFF` holds in all 78,
and the `& 0xFFFF` is load-bearing — the seven capital ships (`ESCRT`, `INTERD`,
`LTCAL`, `CRUSB`, `DREAD`, …) have extents past 32,767, e.g. `ESCRT` spans
40,998 stored as `-24538`. Reading them as `i16` fails on exactly those seven.

**A rejected reading, recorded so it is not re-derived:** `u32@0x10` is exactly
`128 * spanMax` in **49 of 78** records, which looks like a scale or radius —
but across the other 29 the ratio runs from 35.0 to 512.0, so it is *not* that
relation. The field is left unnamed.

`0x20`/`0x21` look like counts (part count and level-of-detail count would fit
the ranges, and `TIEFTR` has 3/2 against `ASTROID1`'s 1/1) — **not recorded as
fact**, since nothing in the data pins them.

### Geometry: not decoded, deliberately

Past 0x24 this is a real 3-D model format and none of the cheap structural
probes closed it. What was tried and what it showed:

- Scanning for runs of `i16` triples inside the model bounding box (i.e. a flat
  vertex array) finds only fragments — 5 triples in all of `XWING` (8,986 B),
  41 across `TIEFTR` in six short runs. So vertices are **not** stored as one
  flat `i16` triple array in model space; they are per-part, or in a local
  space, or not `i16` triples at all.
- The 24-byte block at 0x08 (spans + `0x10` + bbox) **recurs** later in the
  record — in `ASTROID1` at 0x2E, with 8 extra bytes before the repeated bbox —
  so parts carry their own bounds in the same shape as the header.
- No plausible offset table sits right after the header (the u16s at 0x24 are
  not increasing in-range offsets).

Decoding this faithfully wants the model renderer in `Z_TIE__.EXE` — now
reachable, since the Ghidra pipeline works (`analysis/functions.md`). Guessing a
vertex/face layout that merely produces plausible-looking geometry is exactly
what `F030Method/METHOD.md` forbids.

## 7. `.LFB` — the twins question — ANSWERED

There are exactly **2** `.LFB` files, both in `RESOURCE/`, and the standing
"15/16-bit colour depth" hypothesis is **refuted**:

- `EMPEROR.LFB` is **byte-identical** to `EMPEROR.LFD` (428,163 B, md5 equal).
- `SCENE10.LFB` (202,584 B) is `SCENE10.LFD` (206,124 B) **minus one record** —
  the LFD's `FILM:sece_f`. Every other record is byte-identical; only `RMAP`
  differs, exactly as dropping one entry requires.

So `.LFB` is the same container with the same record types — a content variant,
not a depth variant.

## 8. `RES320/` vs `RES640/` — ANSWERED

**Three-way (added 2026-08-22).** `RES320` and `RES640` agree on **all 78**
`SHIP` records and all 18 shared `XACT` records — but `RESOURCE/SPECIES*.LFD` is
**not** just a third copy: **26 of its 78 `SHIP` records differ** from the
`RES320`/`RES640` version (52 are byte-identical), and it holds no `XACT` at
all. So the model set the game loads depends on which directory it reads, and
`RESOURCE/` is its own variant — worth pinning before any port trusts one copy.

`SPECIES2.LFD` and `SPECIES3.LFD` are **byte-identical** between the two
resolution directories. `SPECIES.LFD` differs in exactly **10 of 88** records:

- all **59 `SHIP` records are byte-identical** — the 3-D ship data is
  resolution-independent;
- **18 of 28 `XACT` records are byte-identical**;
- the remaining **10 `XACT` records are differently named per resolution** and
  the 640 versions are consistently much larger, e.g. `BOOM_NLR` 22,197 B
  (RES320) vs `BOOM_N1A` 67,723 B (RES640), `XPLO01` 9,009 vs `XPLO01A` 26,230,
  `EMBER`/`SPARK`/`ZAP`/`HIT`/`SURFHI` likewise.

So the split is purely the resolution-dependent effect sprites; everything else
is shared.

## 9. Open — next pass

1. **`MASK` (70)** — the companion to `PANL` (same name, same file), 8–4,691 B.
   **Consumer identified 2026-08-26; encoding still TBD.** Measurements only,
   deliberately
   not turned into a model after the §5 lesson: splitting each payload at `0xFF`
   bytes gives groups whose sums cluster on the **screen widths** — 320 occurs
   1,220× across `CP320/` and 640 occurs 1,028× across `CP640/` — but with a
   long tail (384, 256, 224, 128, 64 …), groups-per-record ranging 0–80+, and
   **5 records containing no `0xFF` at all**. Suggestive, not sufficient.

   **`MASK` is not the `PANL` encoding** — tested directly: run the §5 opcode
   walk over the MASK payloads and **62 of 70 hit `0xFF` on the first byte**
   (0 rows, payload unconsumed); 5 more consume without ever seeing `0xFF`.
   A clean exclusion.

   **Where the consumer is *not*** (checked, so the next pass need not
   re-tread):
   - `FUN_0004977C` (the PANL blitter) has exactly **one** caller,
     `FUN_00048530` — a coordinate set-up calling a 2-D rotation helper
     (`FUN_0004905C`) four times and the blitter once. No second byte stream.
   - `FUN_000356B0` compares `0xFD`/`0xFE`/`0xFF` but is unrelated game logic
     (sentinels in a lookup table, not an RLE).
   - `FUN_0004C280` (8-bit) and `FUN_0004E71C` (16-bit) are **two more
     PANL-family renderers**, not MASK consumers — see below.

   **The loader is positional for the cockpit trio, and its MASK consumer is now
   identified.** Two findings from
   pulling that thread:

   - **All 70 cockpit files are exactly `PANL, MASK, PLTT`, in that order, with
     all three records sharing one name** (70/70) — a measurement, and it stands.
   - ~~"which is why no tag comparison for `PANL`, `MASK` or `PLTT` exists
     anywhere in the image"~~ — **too strong, corrected 2026-08-23.** A `PLTT`
     string *is* present and *is* referenced: `work/string_xrefs.py` shows
     `FUN_00043B6C` referencing `.LFD`, `CP640\` and **`PLTT`**, i.e. the
     cockpit path builder. `PANL`/`MASK`/`RMAP` still do not appear as literals,
     so the loader is not doing a general tag lookup — but the flat "no tag
     comparison exists" claim was wrong, and `FUN_00043B6C` is the **loader-side
     MASK-path lead**, sitting exactly in the loader region the earlier search
     was circling.
   - The direct consumer is `FUN_00044008` (file 0x71808). `FUN_00043710`
     loads EAX from its resource table's second slot at obj2-relative
     `0x1592E + 0x0E*index`; `FUN_00043B6C` writes the three slots in the
     positional order `PANL, MASK, PLTT`, and the call is at file `0x711CF`.
     The consumer decodes the MASK stream row by row: a leading byte is kept,
     non-zero bytes advance the row span, `0x00` introduces a 255-byte escape,
     and on widths other than 320 a second `0x00`/`0xFF` form extends the span
     by another 256 bytes. Its non-zero mode reverses each decoded row. This is
     enough to identify the consumer and wire contract, but not yet enough to
     assign a complete standalone MASK format because the caller supplies the
     active dimensions and mode flag.
   - The LFD record lookup itself is `FUN_00097020` in **XRES.C** (324 B): it
     starts at offset `(count + 2) * 0x10`, walks `offset += length + 0x10`
     testing each record via `FUN_000972A8`, and returns the matched record's
     offset and its length from header `+0x0C`. Generic — it hands back bytes
     and never interprets them.

   So the MASK consumer is now identified, while the standalone payload contract
   remains open. Every `0xFD`/`0xFF`-touching function outside this path has now
   been read and excluded.

### Two more PANL renderers — the opcode set confirmed a third time

`FUN_0004C280` (448 B, 8-bit) and `FUN_0004E71C` (736 B, 16-bit) run the same
opcode set as §5 straight into the VGA framebuffer (`_DAT_00007A04`, `0xA0000`,
with a per-row pointer table at `0x1BC94`): bytes `< 0xFB` are literals, `0xFB`
sets the colour bias, `0xFC`/`0xFD` are runs, and **`0xFF` returns**. They make
the literal split concrete, with the shift/mask hardcoded rather than taken from
the panel struct:

```c
colour = (b >> 2) + bias;      /* FUN_0004C280 */
count  = (b & 3) + 1;
```

Both take a flag that, when set, writes the **bias colour instead of the
literal's** — i.e. the same geometry drawn as a flat silhouette. Decompiled:
`work/ghidra_export/panl_blit8.c`, `panl_blit16.c`. Callers: `0x4C221`/`0x4C254`
and `0x4E6C0`/`0x4E6ED`.

**Correction (same day).** ~~"it means the `0xFC`/literal width semantics are
recoverable after all for these two variants"~~ — **withdrawn.** These two do
*not* draw the LFD `PANL` records, so it buys nothing for §5. Their encoding is
related but **not identical**:

| | `FUN_0004977C` (LFD `PANL`) | `FUN_0004C280` / `FUN_0004E71C` |
|---|---|---|
| `0xFB` | **3** bytes | **2** bytes |
| `0xFC` | **2** bytes | **3** bytes (colour, count; drawn as `c`,`c+1` dither) |
| `0xFD` | 3 bytes | 3 bytes |
| `0xFE` | end of row | falls through to a row-index increment |
| `0xFF` | end of panel | `return` |

The LFD `PANL` payloads tile exactly **only** under the `FUN_0004977C` sizes
(`FB=3, FC=2`), and only those sizes give the exact 189/200/456/480 row counts —
so the cockpit records are drawn by `FUN_0004977C`, and **PANL pixels stay
blocked** on the tables it builds at run time. What the 8/16-bit pair does give
is the literal split in concrete form (`colour = (b>>2) + bias`,
`count = (b&3) + 1`, with `param_1` acting as a **transparent colour key**),
which is the shape `FUN_0004977C`'s mask/shift almost certainly takes.

### The renderer dispatch table — linear `0xC1EA4`

Neither draw wrapper has a direct caller; they are reached through a **39-entry
function-pointer table** in obj2 at linear `0xC1EA4`, which is **3 blocks of
13** — display mode × primitive. Blocks 0 and 1 are 8-bit (differing in one
slot); block 2 diverges from slot 7 onward into the 16-bit routines
(`0x4E6C0`, `0x4EE14`, `0x4F190`, `0x4F2D8`, `0x4F450`, `0x4F528`). **Slot 7 of
each block is the panel draw** — `0x4C224` for 8-bit, `0x4E6C0` for 16-bit.

Note `0x4C224`: the table points there while Ghidra starts that function at
`0x4C221`. The fixup target is authoritative — another case of fixup targets
being better function seeds than Ghidra's own starts (`functions.md` §5b).

The standalone `CP320/*.PNL` / `CP640/*.PNL` files end on `0xFF` under **both**
models but with data still trailing, in all 18 files — consistent with them
being **multi-image containers** rather than a single stream. Still P2.2.
2. **`FILM` chunk opcodes** — the container is resolved (§6b); the 26,266
   chunks' opcodes are not. This is what scene *playback* (timing, motion,
   frame-accurate palette switches) needs. **The target is now precise**
   (`analysis/functions.md` §5c): the image's own assert strings give a
   source-module map, and the block types map onto their own actor modules —
   `XACTDELT.C`, `XACTANIM.C`, `XACTCUST.C`, `XACTRAW.C`, `XVIEW.C` over a
   shared `XACTOR.C`, sequenced by `XFILM.C` (115 functions). That matches the
   census result that each block type uses a different opcode set. Read those,
   don't guess from frequencies.
3. **`SHIP` geometry** — header resolved (§6c), the model data past 0x24 is
   not. Needs the renderer in `Z_TIE__.EXE` — and note the module map
   (`functions.md` §5c) does **not** help here: all 38 named modules are the
   "X" presentation library, so the 3-D engine is somewhere in the 2,742
   functions with no source-name anchor. Feeds any port that draws ships.
4. **`XACT` (56)** — resolution-dependent effect sprites (§8).
5. **`BMAP` (26)**, **`FONT` (5)**, **`MTRX` (5)** — `FONT:font6` of
   `RESOURCE/EMPIRE.LFD` starts `20 00 60 00 08 00 06 00 04 00 00 00` then a
   run of small values that look like per-glyph widths, consistent with first
   char 0x20 and 0x60 glyphs — **unverified**, listed as a starting point only.
6. **PLTT component range** — **resolved for the cockpit path.** The source
   components are full `0x00..0xFF` values, while the loader converts them for
   the 6-bit VGA DAC.
   `FUN_00043B6C` is that palette-load routine: it shifts the loaded PLTT bytes
   right by two before handing the palette to the active renderer. The source
   records remain full `0x00..0xFF` component bytes; VGA-facing values are
   `0..0x3F`. The three non-zero PLTT trailer records still need their field
   semantics.
7. ~~**Which palette belongs to which image**~~ — **answered by `FILM`**, §6b:
   86 % of the ambiguous records now resolve from the block list instead of the
   name heuristic. Residual: records in no FILM (§6b), and frame-accurate
   ordering, which needs the opcodes (item 2).

## 10. Extraction

```
python3 work/lfd_extract.py <out_dir> <file.lfd> [more...]
python3 -c "import sys; sys.path.insert(0,'work'); import lfd, lfd_extract; \
            lfd_extract.main('/tmp/lfdall', list(lfd.iter_lfd('game/SWTieCD/TIECD')))"
```

The whole tree yields **5,835 PNGs** (370 DELT + 5,465 ANIM frames; 2 empty ANIM
frames skipped, §4). **PANL is not rendered** — its pixels are not statically
decodable (§5). Output is RGBA, uncovered pixels
alpha 0. Names are `<dir>_<file>_<record>[_<frame>].png` — the directory and
the extension are both part of the name because `CP320`/`CP640` and
`EMPEROR.LFD`/`.LFB` repeat record names.
