# UW2 data formats (diffed against `C:\Arbeit\F030Underworld\analysis\data-formats.md`)

Per-format sections, each checked against UW1's already-resolved reading
before decoding anything from scratch (`AGENTS.md` convention). Record which
UW1 invariants hold and which don't — don't re-derive what still applies.

## The shared `.ARK` container — one format behind CNV, LEV, BYT and SCD — RESOLVED (2026-08-22)

**This supersedes the per-file container readings below.** `LEV.ARK` was
described (2026-08-21) as having "a different variable-size blob layout with
its own embedded index table". ✗ Withdrawn: it is the *same* container as
`CNV.ARK`, and so are `BYT.ARK` and `SCD.ARK`. Tool: `python work/ark.py`.

```
0x00  u16      slot count N     SCD 16, BYT 11, CNV 320, LEV 320
0x02  u32      purpose not determined; 0 in all four shipped files
0x06  u32[N]   record offset    0 = empty slot
      u32[N]   flags            bit0 compress-on-write, bit1 stored compressed,
                                bit2 padded / growable in place
      u32[N]   stored size in bytes
      u32[N]   padded / allocated size
records                          at 0x06 + 16*N, with NO gap
```

✗ **Corrected 2026-08-23.** This block previously started the four arrays at
`0x02`, called the leftover 4 bytes "slack", and put records at
`header_end + 4`. That is **wrong by one slot**. The game reads offsets at
`6 + 4*slot` (`ark_read_slot`, file `0x72843`), so the old slot *i* was really
game slot *i−1*, and the old slot 0 was the header `u32` at offset `0x02`, not
a record.

Confirmed from the data: `u32@6 == 6 + 16*N` exactly in SCD (`0x106`), LEV
(`0x1406`) and BYT (`0xB6`), and CNV's slot 0 is genuinely empty. After the fix
there is no slack, and the used-slot counts rise — **SCD 15→16, BYT 10→11** —
because the last real record was being dropped off the end.

The LZSS self-check still reported **200/200** under the old numbering, because
the shift is uniform. A self-consistent check is not a correct one; it took the
*game's own* indexing arithmetic to catch this.

The flag semantics also come from `ark_write_slot` (`0x720C1`) rather than from
observation: bit 0 requests compression on write, bit 1 records that the stored
record *is* compressed, and bit 2 marks a record padded so it can grow in place
— the pad being `(15 * len) / 100`.

| file | size | slots | used | header ends | first record | flags |
|---|---|---|---|---|---|---|
| `SCD.ARK` | 8,950 | 16 | 16 | `0x0106` | `0x0106` | `{0}` |
| `BYT.ARK` | 173,241 | 11 | 11 | `0x00B6` | `0x00B6` | `{1,3}` |
| `CNV.ARK` | 281,109 | 320 | 102 | `0x1406` | `0x1406` | `{3}` |
| `LEV.ARK` | 428,861 | 320 | 107 | `0x1406` | `0x1406` | `{1,3,7}` |

A compressed record is `u32 uncompressed_length` then the LZSS stream decoded
in the `CNV.ARK` section. **Every record whose flag has bit 1 set decodes
exactly — 200 of 200 across all four files**, output length matching the
header `u32` *and* the source consumed to the byte. Records with the bit clear
are plain data.

### Re-compressed, and what that pins down — 2026-08-22

`python work/rebuild.py --ark` runs an independently written encoder
(`work/lzss_encode.py`) over every compressed record:

| | |
|---|---|
| our stream decompresses to the identical data | **200 / 200** |
| byte-identical to the shipped stream | **9 / 200** |
| total size ours vs shipped | +0.24 % |

The 200/200 is the bidirectional confirmation — the format is understood well
enough to *write*, not just to read. The **9 exact matches** are the more
interesting number: those are records where no match-selection ambiguity
arises, so they prove the encoding itself — flag bit order, offset/length
packing, ring semantics — is exactly right, and isolate the remaining
difference to *which* match the original picked.

That difference is now characterised, by walking a shipped stream and
computing the best match available at each of its decision points:

- The original is **greedy-longest**: it took the longest available match
  **78 times out of 78** — never shorter, never longer.
- Its tie-breaking is **not positional**: among equal-length candidates it
  chose the nearest 56 times and the furthest 54 times out of 110. A ~50/50
  split is the signature of a matcher whose answer depends on its internal
  search order — a binary search tree over the ring, whose traversal depends
  on insertion history — rather than on distance.

So reproducing all 200 needs the original *matcher* reimplemented, not a
better policy. For scale, greedy/prefer-nearest lands within 0.02 % of the
shipped total and a lazy variant beats it by 2.7 % — the original is not
optimising hard.

The flag is a bitfield, and the evidence for bit 1 specifically is that
`LEV.ARK` stores **134-byte records both ways**: 32 of them compressed
(flag 3) and 18 uncompressed (flag 1), same size, same shape. Bits 0 and 2
are unexplained — bit 2 appears only in `LEV.ARK` (flag 7) and `SCD.ARK` uses
flag 0 on populated slots, so bit 0 is *not* an in-use marker.

`LEV.ARK` decompressed record sizes: **32,264 ×50**, 134 ×32, 4,096 ×4, and
one each of 756, 2,754 and 1,620. The 50 large records are presumably the
levels; their internal layout is **not** decoded here.

### The 32,264-byte records ARE the level buffer, and it opens with a 64×64 grid

The call-graph pass (`ghidra.md` §13) surfaced `FUN@0x33BFA` — **37 callers**,
one of the busiest functions in the binary:

```
if ((x | y) & 0xFFC0) return NULL;              ; both must be < 64
return far [0x188c] + ((y << 6) + x) * 4;       ; 64x64 grid, 4 bytes per cell
```

`[0x188c]` has exactly **one writer**, `FUN@0x927C0`:

```
if ([0x188c] | [0x188e]) return;                ; allocate once
malloc(0x7E08)                                  ; 0x7E08 = 32,264
[0x188c]:[0x188e] = result
```

**`0x7E08` = 32,264 = precisely the decompressed size of the 50 large
`LEV.ARK` records.** The buffer and the record are the same thing.

#### Offset `0x0000..0x3FFF` — a 64×64 grid of 4-byte cells — RESOLVED

Three independent confirmations:

1. `FUN@0x33BFA`'s arithmetic — `x,y < 64`, stride 4, so the grid ends at
   `63*64+63` × 4 + 4 = **16,384** bytes.
2. `FUN@0x927F7` copies **`0x1000` = 4,096 four-byte cells** into the buffer
   from offset 0, then sets `[0x1890] = 1` (a loaded flag). 4,096 × 4 = 16,384.
3. The data agrees. Taking a real record (slot 1) and reading the first
   16,384 bytes as 4,096 × (u16, u16): word 0 takes only **54 distinct
   values**, and the most common — **1,669 of 4,096 cells** — is **`0x00F0`**,
   which is the *same global empty sentinel UW1's own doc documents for
   `LEV.ARK` grids*. Random data does not do that. The low nibble of word 0 is
   a small field (3,609 zeros, 475 ones, a handful of others).

So UW2 uses **64×64 × 4 bytes** where UW1 used 63×63 × 8 — which is why the
2026-08-21 pass, looking for UW1's `0x7C08` blobs, found none.

#### The rest of the buffer — mapped, and the object arrays decoded

`FUN@0x2BA41` is the buffer's layout routine. It first walks all 4,096 grid
cells doing `and es:[bx+2], 0x3F` — **masking each cell's word 1 down to 6
bits** — then derives five sub-pointers at fixed offsets:

| offset | size | global | content |
|---|---|---|---|
| `0x0000` | `0x4000` (16,384) | `[0x188c]` | 64×64 grid, 4 B/cell |
| `0x4000` | `0x1B00` (6,912) | `[0x2578]` | **256 objects × 27 B** |
| `0x5B00` | `0x1800` (6,144) | `[0x25a6]` | **768 objects × 8 B** |
| `0x7300` | `0x01FA` (506) | `[0x259e]` | — |
| `0x74FA` | `0x070C` (1,804) | `[0x259a]`, `[0x25a2]` | — |
| `0x7C06` | u16 | — | zeroed by `FUN@0x92836` |
| `0x7C08` | `0x0200` (512) | — | used by `FUN@0x92910`/`0x92997` |

#### Object references are a 10-bit index, and the two arrays tile it exactly

`FUN@0x2C2F9` (29 callers) resolves an object reference and gives the whole
model away:

```
id = (word >> 6) & 0x3FF                      ; 10-bit index, bits 6..15
if (id >= 0x100)  ptr = [0x25a6] + (id - 0x100) * 8      ; shl ax,3
else              ptr = [0x2578] + id * 27               ; mov dx,0x1b / imul
```

So indices **0–255** live in the `0x4000` region at **27 bytes** each and
**256–1023** in the `0x5B00` region at **8 bytes** each — and both region
sizes come out exact: `256 × 27 = 6,912 = 0x1B00` and `768 × 8 = 6,144 =
0x1800`. **1,024 objects**, no slack in either array. The 27 is read directly
off `mov dx,0x1b / imul` (and a second site does `add dx,-0x1b` to step back
one entry), so the stride is measured, not inferred from the factorisation.

The same model appears twice more, from the call-graph pass — which is a
third and fourth sighting rather than a re-reading of the same code:

- **`obj_ptr_from_index` (`0x2C3AC`, 28 callers)** — the same dispatch but
  taking a raw index instead of extracting one from a packed word:
  `idx < 0x100 → [0x2578] + idx*27` (again a literal `mov dx,0x1b / imul`),
  else the 8-byte array.
- **`obj_index_from_ptr` (`0x2C362`, 30 callers)** — the **inverse**:
  `ptr < [0x25a6]` → `(ptr − [0x2578]) / 27`, else the 8-byte path. A divide
  by 27 recovering the index is about as direct a confirmation of a 27-byte
  stride as one could ask for.

That also explains the grid's word 1: the same 10-bit field at bits 6..15 is a
**tile→object link**, which is exactly what `level_buf_layout` clears with
`& 0x3F` on load. Consistent with the file data, where word 1's observed
values are small (top three: 0, 36, 19) — the links are built at runtime, not
stored.

#### The object record's fields — PARTIALLY RESOLVED (2026-08-22)

Every field access inside the **29 callers** of `obj_ptr_from_word` was
collected, together with the shift/mask applied within the next three
instructions. Offsets read: `+0x00, +0x01, +0x02, +0x03, +0x04, +0x06` (inside
the 8-byte record every object has) and `+0x13, +0x15, +0x16` (only reachable
on the 27-byte entries). The bitfields, with the number of sites doing each:

| word | bits | extraction | sites |
|---|---|---|---|
| `+0x00` | 0–8 | `& 0x1FF` | **19** |
| `+0x00` | 9–11 | `shr 9 & 7` | 5 |
| `+0x00` | 15 | `shr 0xF` | 10 |
| `+0x02` | 0–6 | `& 0x7F` | 11 |
| `+0x02` | 10–12 | `shr 0xA` | 4 |
| `+0x02` | 13–15 | `shr 0xD` | 4 |
| `+0x04` | 0–5 | `& 0x3F` | 3 |
| `+0x04` | **6–15** | `shr 6 & 0x3FF` | 6 |
| `+0x06` | 0–5 | `& 0x3F` | 4 |
| `+0x06` | **6–15** | `shr 6 & 0x3FF` | 9 |

**Words `+0x04` and `+0x06` each hold a 10-bit object index in bits 6–15** —
the identical encoding `obj_ptr_from_word` consumes and the identical encoding
in each grid cell's word 1. So an object carries **two object links**, and the
same 16-bit "6-bit field + 10-bit link" cell type is used in three places.

#### The 9-bit field at `+0x00` is an item id — confirmed from outside the EXE

`COMOBJ.DAT` ("common object") is **5,634 B = 2 + 512 × 11**: a 2-byte header
and **exactly 512 fixed-size entries**, which is precisely the range of a
9-bit id. Entry 0 is `00 82 01 60 14 00 c5 a0 00 14 11`, entry 511 is all
zeros but for a trailing `0x10`. A field width read out of the code and an
asset file's size agreeing to the byte is the kind of check worth having.

(The `u16` header is `0x0E01`; per-entry field meanings are not decoded.)

#### Still not decoded

The `0x7300` (506 B) and `0x74FA` (1,804 B) regions, the `0x7C08` 512-byte
area, the u16 at `0x7C06`, the meaning of each object bitfield beyond the two
links and the item id, the 19-byte extension on the 27-byte entries (`+0x08`
… `+0x1A`, of which only `+0x13`/`+0x15`/`+0x16` were seen used), and the
grid's word-0 fields.

**One lead on the last of those**: `TERRAIN.DAT` is **512 B = 256 × u16 with
only 15 distinct values** — the shape of a terrain-class lookup for 256 tile
ids. Whether the grid's word 0 indexes it is not established.

### The grid cell's fields — RESOLVED (2026-08-22)

`set_tile_region` (`0x84527`) writes tiles over a rectangle, and its
field-masking and range guards give the cell layout directly:

| bits | field | guard in the setter |
|---|---|---|
| byte 0, bits 0–3 | **tile type** | `cmp 0xa` → 10 types |
| byte 0, bits 4–7 | **floor height** | 0..0x0e |
| byte 1, bits 2–5 | **floor texture** | `cmp 0xf` |
| byte 2, bits 0–5 | **wall texture** | `cmp 0x3f` |

Checked against a real decompressed level record (4,096 cells), three fields
land inside their guards exactly: tile type takes 7 distinct values with a
maximum of **9** (the `cmp 0xa` allows 0–9), floor texture maxes at 15, wall
texture at 58 (`≤ 0x3f`).

**Floor height did not fit at first, and the mismatch is the interesting
part.** The data reaches **15** while the setter only permits 0–14. Across
eight levels, height 15 occurs on **21,031 cells and every single one has tile
type 0** — 100%, no exceptions. So 15 is not a height: it is what solid/unused
tiles carry, which is precisely why a setter that writes *real* heights stops
at 14. The discrepancy confirms the layout rather than undermining it, and it
also explains the `0xF0` sentinel documented earlier — a cell of `0x00F0` is
tile type 0 with height 15, i.e. **solid rock**.

## `LEV.ARK` — level archive — container shape holds, grid layout does NOT — PARTIALLY RESOLVED (2026-08-21, container superseded above)

UW1: `work/expanded/DATA/LEV.ARK`, 290,864 B (`0x47030`). UW2:
`work/extracted/D3/DATA/LEV.ARK`, 428,861 B (`0x68B3D`). Both audited with
`work/lev_audit.py` (new, self-contained, run unchanged against both files —
read its docstring before trusting any record boundary it prints).

### Two corrections to UW1's own doc, found while calibrating the parser against UW1's file first

Before touching UW2, `lev_audit.py` was run against UW1's own `LEV.ARK` to
reproduce the numbers UW1's doc already publishes. Two of that doc's claims
don't hold byte-for-byte:

- Its "key records" table labels the third grid **`id 3`**; the actual bytes
  at that record are **`id 2`** (start/end match the doc exactly —
  `0x36656..0x3E25E` — only the id column is off by one).
- "last chunk ends exactly at EOF" is not quite right either: the last
  *documented* chunk ends at `0x46FB6`, and the file is `0x47030` —  a
  **122 B tail past every parsed record**, filled with a boring repeating
  `40 00` pattern, not part of any record. Small, but it means UW1's own file
  already has an uncovered tail; UW2 having one too (below) isn't new
  behavior, just a much bigger one with actual content in it.
- More fundamentally: **no simple parser resolves UW1's own record stream
  cleanly.** A greedy single-record-lookahead walk derails silently (a
  coincidental false match one record deep turns everything after it to
  garbage — reproduced during development). Full backtracking (try every
  possible trailing-byte skip, require the *rest* of the stream to also
  parse) is more honest but **fails outright** for UW1's 135 records under
  any tried skip/id constraints — meaning some record shape in the true
  format isn't the simple "10 B + optional 2/4/6/8 B trailing" model either
  doc assumes. `lev_audit.py` instead does greedy-with-resync (scan forward
  on failure for the next self-consistent position), which reaches all
  records in both files but should be read as **best-effort past the first
  ~10 records**, not byte-verified the way the rest of this project's
  RESOLVED claims are.

### What holds for UW2

- **Header shape**: two `u16` at offset 0 (count, then a second field) —
  structurally the same. Values differ a lot: UW2 `count=320` (vs UW1's 135,
  ×2.37 — plausibly more levels, since UW2 spans several worlds where UW1 has
  one 9-level dungeon, but no byte-level level count is confirmed here) and
  **`field2=0`** (vs UW1's 542/`0x21E`) — UW1's field2 numerically satisfies
  `field2 + 0x7C08 = grid-A-start`, so a zero here is itself informative: no
  such relationship can hold for UW2 since it has no `0x7C08` grid at all
  (next point).
- **Record shape**: `u16 id, u32 start, u32 end` base, some records carrying
  2 (occasionally more) trailing bytes before the next record — confirmed by
  hand for UW2's first ~6 records byte-by-byte, and holds for the rest via
  the resync parser (320/320 parsed, only 6 small resyncs of 8–16 B each, vs
  UW1's 18 resyncs — proportionally UW2's stream is *more* self-consistent
  under this model, not less).
- **Null records** (`start=end=0`) — present in UW2 too (e.g. record indices
  6, 7, 9 in the dump). UW1's specific `0xF0`-sentinel shape (`start=end=0xF0`
  plus trailing `0xF0`) wasn't specifically checked for UW2 — TBD.

### What does NOT hold for UW2

- **UW1's "three parallel 63×63×8 B grids" (`0x7C08` = 31,752 B each) is
  absent.** Exhaustively scanned (every 2-byte-aligned `(u32,u32)` pair in
  the header region, both files): UW1 shows the expected hits at its 3 known
  grid offsets; **UW2 has zero records of size `0x7C08` anywhere.** UW2's
  per-level attribute data is not laid out as 3 identically-sized grids.
- **Instead**: ~16 records with *variable* sizes in the 6,696–10,903 B range
  (id 0 and id 1 records specifically). These all open with an **identical
  34-byte prefix** — `08 7e 00 00 0f f0 00 00 00 ee ff 00 0f 12 0f 24 0f 00
  36 0f 48 0f 5a 0f 6c 0f 7e 0f 90 0f a2 0f b4 0f` — read as `u16`s from
  offset 12 the values step **`+0x12` (18) each entry** (`0x0F12, 0x0F24,
  0x0F36, …, 0x0FB4`), i.e. a small fixed-stride offset/index table shared
  across every one of these blobs. UW1's grids have no such embedded
  sub-header — they start directly with raw cell data. **IDENTIFIED, not
  decoded** — this is a real, repeated structural element, but what the
  index table addresses within its own blob is unknown.
- **`0xF0`-sentinel density in these UW2 blobs is ~0.3–0.5%** — far below
  what UW1's "mostly-empty, `(0xF0,0,0xF0,0)`-per-cell" grids would produce.
  Either UW2 doesn't use `0xF0` as an empty-tile sentinel the same way, or
  these blobs aren't fixed-8-byte-cell grids at all (variable/compressed
  encoding is consistent with the shared index-table prefix above).
- **New record ids**: UW2 uses ids `0–7`; ids **5, 6 and 7 don't appear in
  UW1 at all** and are common (28, 24 and 4 occurrences respectively — 17.5%
  of all 320 records combined). Unidentified; likely related to whatever
  UW2-specific content the extra worlds need (`AGENTS.md` Next-steps #3 —
  `VOIC*`/`SDFX*` — may be relevant here, or may not).
- **Uncovered tail, much bigger and non-trivial**: 1,204 B past the last
  parsed record (`0x68689..0x68B3D`), versus UW1's 122 B of boring filler.
  UW2's tail contains **readable text**: short clean fragments early on —
  `CAVE MOUTH`, `CAMP SITE`, `FIRST NIGHT`, `YETI LAIR` (each with exactly
  one stray non-ASCII byte spliced into the middle, e.g. `CAVE MOU` + `0x7F`
  + `TH`) — followed by a long run of similarly-broken but largely legible
  prose mentioning **"ANODUS"** and describing hazards ("abundant and
  dangerous", "ball-throwing", "intelligent") in what reads like in-game
  journal/lore text. The single-stray-byte-in-otherwise-clean-ASCII pattern,
  repeating at irregular but short intervals, looks like a simple
  compression scheme (LZ/RLE-style control bytes left undecoded, literal
  bytes passing through as plain ASCII) rather than corruption — **IDENTIFIED
  only; decoding it is a separate follow-up, not attempted here.**

### Net read

UW1's "container skeleton" (header + record stream + data pool) carries over
as a *shape*. Everything UW1 resolved about the *contents* of that shape (the
three 63×63 attribute grids specifically) does not — UW2's per-level data is
organized differently (variable-size blobs with a shared index-table header,
no `0x7C08` grids, much lower `0xF0` density) and the archive gained a
sizeable trailing text blob UW1 never had. Treat UW1's `analysis/uwexe.md`
grid-semantics work as inapplicable to UW2 without further evidence — don't
port the 63×63 assumption forward.

**TBD / next, if this format is picked up again**: identify what the 34-byte
index table addresses (its stride of 18 and start value `0x0F12` may point
back into the same blob); decode the tail text's stray-byte pattern (compare
byte offsets of the stray bytes across multiple words — a fixed period would
point at XOR/RLE, an irregular one at dictionary/LZ); confirm whether ids
5/6/7 correlate with specific worlds by cross-referencing record order
against the tail's level-name strings.

## `.GR` (sprite archives) — container + type=4/0x0a formats hold exactly — RESOLVED (2026-08-21)

UW1: 30–33 files under `work/expanded/DATA/*.GR`. UW2:
`work/extracted/D1..D4/DATA/*.GR`, **35 files**, scattered across four disks
rather than one directory — `work/gr_render.py`'s `find_data_file()` globs
`D*/DATA/<name>` to paper over this. Names mostly match UW1's
(`SPELLS.GR`, `CURSORS.GR`, `CHARHEAD.GR`, `OBJECTS.GR`, …); UW2 renames
UW1's `WEAPONS.GR` to `WEAP.GR` and adds two names with no UW1 counterpart,
`GEMPT.GR` and `GHED.GR` (not yet examined).

### What holds — everything UW1 resolved, byte-for-byte

- **Container**: `u8 type; u16LE N @1; (N+1)×u24LE table @3 (4B stride)` —
  confirmed exactly on `SPELLS.GR`, `QUESTION.GR`, `CURSORS.GR`: `table[0] ==
  3+4*(N+1)` and `table[-1] == filelen` on every file checked, no exceptions.
- **The file-level `type` byte is the same shared-loader extension index UW1
  found**, not a per-format version: every UW2 `.GR` file checked carries
  `type=1`, and UW2's lone `.TR` file (below) carries the equivalent byte as
  `2` — exactly UW1's documented `.gr`/`.tr` pair from the `.gr\0 .tr\0 .cr\0
  .sr\0 .ar\0` extension table. One shared loader, unchanged mapping, across
  both games.
- **Record header** (5 B: `type, w, h, b3, b4`) and both resolved pixel
  formats carry over exactly:
  - `type=4` (raw 8bpp): `SPELLS.GR` record 0 is `w=16 h=18 b3=0x20 b4=0x01`,
    **identical dimensions and b3/b4 to UW1's own SPELLS.GR record 0** — very
    likely the same spell icon, reused asset. `payload_len == w*h` exactly.
    `CHARHEAD.GR` record 1: `w=64 h=70`, payload 4,480 B = 64×70 exact.
  - `type=0x0a` (4-bit packed, flat nibble stream, +1 trailing byte):
    `QUESTION.GR` (`w=16 h=16`, payload 129 = `(256+1)//2+1`) and
    `CURSORS.GR` record 0 (`w=13 h=13`, payload 86 = `(169+1)//2+1`) both
    match the formula exactly.
  - `type=8`: still compressed, still unresolved — `OBJECTS.GR` record 0 is
    `type=8 w=16 h=16 payload_len=65` for `w*h=256` (≈3.9× ratio), same open
    problem UW1 has. Not attempted here either.
- **Empty records exist in the same places conceptually**: `CHARHEAD.GR`
  records 0 and a scattered set through the 160s are zero-span, same pattern
  UW1 documented for its own `CHARHEAD.GR`/`GENHEAD.GR`.

### Visually verified — the check UW1's own retrospective flagged as missing for `.TR` (below), done here for `.GR` too

`work/gr_render.py` (adapted from UW1's script, container comment corrected
to describe `type` as the loader index rather than "version", table-offset
math unchanged since it was already right) rendered, against
`work/extracted/D3/DATA/PALS.DAT` palette 0:

- `SPELLS.GR` record 0 → a recognizable spell-icon sprite (small weapon/bolt
  shape).
- `QUESTION.GR` record 0 → a plain "?" glyph.
- `CURSORS.GR` record 0 → a crosshair/target cursor shape.
- `CHARHEAD.GR` record 1 → a clearly legible green orc/troll character
  portrait.

Four renders, both resolved pixel formats, zero mismatches — this is not a
stride coincidence, it's real sprite data rendering as real game art.

For the cursor specifically, `CURSORS.GR` record 0 carries auxiliary palette
index `23`; `ALLPALS.DAT[23*16..+16]` maps its nibbles into `PALS.DAT` palette
0. The cursor capture pair confirms the nonzero mapped colours and that nibble
0 leaves the underlying pixels unchanged for this record. This is a
record-specific runtime result, not a generic claim about every type-`0x0A`
record; header byte `+4`, the trailing byte and generic transparency remain
open. The durable cursor function and difference record is
[`analysis/functions/cursor.md`](functions/cursor.md).

**Historical snapshot (2026-08-22):** type-8 decompression and `b3`/`b4`
semantics were not yet attempted here. They are resolved below in §`.GR` type
8 (2026-08-23). `PANELS.GR`'s divergent header and `GEMPT.GR`/`GHED.GR` remain
separate open format questions.

## `.GR` — the type census the "RESOLVED" label above glosses over (2026-08-22)

`python work/rebuild.py --gr`, over all 35 files, **1,749 records**:

| record type | count | share | state |
|---|---|---|---|
| `0x08` | **736** | 42 % | **decoded; encoder resolved** |
| `0x04` (raw 8bpp) | 666 | 38 % | decoded |
| empty | 323 | 18 % | — |
| `0x0a` (packed 4-bit) | 20 | 1 % | decoded |
| `0x00` | 3 | 0 % | — |
| `0xa2` | 1 | 0 % | — |

This census was written before the type-8 decoder was closed. The container and
all three pixel formats are now decoded; the type-8 encoder is resolved below.
`work/gr_encode.py` now re-emits all 34 standard archives byte-identically;
only the divergent `PANELS.GR` record 3 remains open.

### `ALLPALS.DAT` — 32 auxiliary 16-entry palettes — RESOLVED (2026-08-22)

**513 B = 32 × 16 + 1.** `FUN@0x8BC38` reads its first `0x200` bytes verbatim
to `DGROUP:0x6732`, which is the base the 4bpp expanders index as
`0x6732 + 16 × palette`. Verified against a live capture: see `ghidra.md`
§10d — the bytes the oracle showed at `SI = 0x6732 + 16 × 23` are
`ALLPALS.DAT` offset `368 = 16 × 23`, byte for byte.

### The `.GR` load path — and why the type-8 decoder is not on it

`gfx_init` (`0x8BC38`) → per-archive wrapper (`0x8B89B`) →
`gr_archive_load` (`0x8B798`, walks the offset table at `[0x672c]`, sizing
each record) → `gr_record_read` (`0x8B435`, seek + read). `gr_record_read`
reads each record **raw**, and `gr_archive_load` checks the byte count against
the size the table predicts — so **no pixel decoding happens at load time**.
The type-8 decoder is therefore in the *draw* path, not the load path, which
is where a further attempt should start. ✓ **That call was right** — see the
resolution below; the decoder is reached from `shape_draw` (`0x1D543`).

**Live dispatch check — 2026-08-25.** A fresh oracle session reached the 3D
starting room with the image-to-linear calibration agreeing at `delta=0x2F50`.
Breakpointing the image-resident dispatch entry at file `0x112CC` and issuing
a chest-area mouse action stopped with `BX=0x000A`. This is the format byte
used to index the dispatch table, so the live interaction exercised the flat
4-bit type `0x0A` path, not type 8. It confirms the breakpoint and dispatch
interpretation; it does not count as a negative type-8 result because the
starting room contains no known type-8 inventory sprite.

**Clean-room follow-up — 2026-08-25.** After a fresh reboot (to remove a
stale gdbstub stop state), the post-`INT 33h AX=3` boundary at file `0x24838`
returned `CX=0x0254`, `DX=0x0077`, i.e. driver-visible position `(596,119)`.
Moving to the room container at `(400,130)` and clicking stopped at
`0x112CC` with `EBX=0x0000000A`. Starting with a Fighter and then sampling all
six visible inventory-grid cells likewise produced six `0x0A` dispatches:
`grid-1` through `grid-6`, with no `BX=8` hit. This is a bounded negative
result for the starting-room/container and empty-inventory scenes only; it
does not downgrade the corpus-wide type-8 decode or prove that later level
objects cannot reach it. The next live target is a populated inventory or a
later level/object scene, not another click in this room.

### `.GR` type 8 — RESOLVED 2026-08-23 (`ghidra.md` §25)

**Nibble-packed 16-colour data, RLE-compressed, drawn through an auxiliary
16-entry palette.** Implemented in `work/gr8_decode.py` and **validated against
all 736 type-8 records in the game**:

- **736/736**: the payload byte count is exactly `ceil(nibble_count / 2)` — the
  u16 at `+4` describes every record's payload with zero slack.
- **736/736** decode without overrunning the stream.
- Output is never short: 119 records land exactly on `w*h`, 452 on `w*h + 1`,
  165 on `w*h + 2`, and nothing else. The 1–2 trailing pixels are padding in
  the final group; the original overruns identically — it stops on the same
  `si >= bp` test and the caller only ever reads `w*h` bytes out of the scratch
  buffer.
- **Visual check**: `OBJECTS.GR`'s type-8 records render as recognisable UW2
  inventory art — axes, swords, maces, bows, gauntlets, boots, helmets, rings,
  a shield, and the "Fist" icon — in correct colours, using the aux palette the
  record's byte `+3` selects (`work/gr8_objects_sheet.png`).

### The `.GR` census, closed out (2026-08-23)

Across all 34 `*.GR` files, **1426 records**:

| type | count | status |
|---|---|---|
| 4 | 666 | raw 8bpp — long resolved |
| **8** | **736** | **nibble-packed 16-colour RLE — resolved, see above** |
| 0x0a | 20 | flat 4-bit — long resolved |
| — | 4 | `PANELS.GR`, which is not in this format at all |

`python work/rebuild.py --gr-rebuild` rebuilds all 34 standard `.GR` archives
byte-identically. It intentionally skips `PANELS.GR`: its first three records
are raw 8bpp panels without the standard per-record headers, and record 3 is
still undetermined.

**`PANELS.GR` has no per-record headers.** Its first three records are exactly
`8848 = 79 × 112` bytes of raw 8bpp, and render as UW2's stone UI panels: the
equipment paperdoll with its circular slots, the container grid, and the stats
panel reading `STR DEX INT VIT MANA EXP`. The bytes I had been reading as a
"type" (`0`, `0xa2`) are simply the first pixel. Dimensions are not in the file
— the caller must supply them.

**`PANELS.GR` record 3 is not determined.** 336 bytes, 7 distinct values (163
appears 197 times, then 205–208, two 162s and three 0s). All sixteen
factorisations were rendered, in palette colour and in false colour, and none
produces coherent structure — no straight edges, no recognisable shape. It may
not be an image. Recording it as open rather than picking a plausible-looking
dimension.

### Target-neutral indexed export — IDENTIFIED (2026-08-25)

`work/asset_export.py` is the first port-side converter. It expands two verified
source records into a small `UW2I` cache consumed by the browser reference and
the future target backend:

| fixture | source | dimensions | source pixels |
|---|---|---:|---|
| `objects-000` | `D3/DATA/OBJECTS.GR`, record 0, type 8 | 16×16 | RLE-decoded and translated through `ALLPALS.DAT` |
| `t64-000` | `D2/DATA/T64.TR`, record 0 | 64×64 | raw indexed tile bytes |

The cache header is 44 bytes, big-endian, and fixed-size. Its u32 offsets are
4-byte aligned. The payload is row-major one-byte-per-pixel indices followed
by one 256-entry `PALS.DAT` palette in the original 6-bit DAC form. Header
metadata records the source kind and record, the global palette index, the
type-8 auxiliary palette index (`0xffff` for T64), pixel/palette offsets and
lengths, and source-record length. No Falcon video address or palette-word
encoding is present.

`analysis/pixel-fixtures.json` is the regression oracle: it stores source-file
and source-record hashes, dimensions, logical pixel hashes, palette hashes, and
complete cache hashes. `python3 work/asset_export.py --check` passes for both
fixtures; `--out-dir work/pixel_assets` emits the two regenerable caches. This
proves deterministic host expansion and the common seam only. It does not yet
prove DOS/Falcon framebuffer equality.

### Browser reference — IDENTIFIED (2026-08-25)

`browser/index.html` is the first mandatory browser test vehicle for the
function-level port. `browser/uw2-fs.js` implements the DOS boundary:
normalized names and `open/read/seek/tell/close` over `Map`-cached `Uint8Array`
files. It supports clean in-memory mode for tests and host-only versioned
persistent mode: IndexedDB stores imported bytes, while localStorage stores
only path/size/source-variant/SHA-256 metadata. `browser/uw2-reference.js`
maps only `LBACK000.BYT`, `CS000.N01`, `CS000.N02`, and `CS000.N12` to host
resources.

The active browser decoder is the cutscene path in `browser/uw2-cutscene.js`:
LPF page/record lookup, ANIM delta decoding, indexed framebuffer conversion,
and canvas presentation. `browser/uw2-game.js` loads the four explicit source
files and schedules their connected intro phases. The checked-in pixel and
cutscene manifests remain analysis/build oracles; the page does not load them,
compute hashes, or display validation status. The browser is an implementation
of this display slice, never the behavioral authority; DOS identity and
behavior remain grounded in the recovered executable and captured execution.

### Type 6 — implemented, but **unvalidated**

The same decoder handles type 6 with 5-bit pixels (`cx = 2` to the setup, a
32-entry palette). `unpack5` in `work/gr8_decode.py` is a faithful
instruction-for-instruction transcription of the loop at `0x94F7` — the
original threads one 16-bit `AX` through `ror`/`shr`/`xchg` and the intermediate
high bits matter, so it is transcribed rather than re-derived.

**UW2 contains no type-6 records**, so none of it has been tested against real
data. It is kept for UW1 and labelled untested; do not trust it until a type-6
record exists to check it against.

### The format

```
header   u8 format(=8), u8 width, u8 height, u8 aux_palette_index
payload  u16LE nibble_count, then ceil(nibble_count/2) bytes,
         two 4-bit values per byte, HIGH nibble first
```

The unpacked nibbles are an RLE stream. Every emitted value is translated
through the 16-byte aux palette (`ALLPALS.DAT[aux*16 .. +16]`), giving an index
into `PALS.DAT`. Each iteration is *optionally a run, then always a literal
group*:

| control | meaning |
|---|---|
| `> 2` | run of `control` copies of the next nibble |
| `2` | the next N items are **run-only** (no literal group each) |
| `1` | no run |
| `0` | run length escapes wider |

Lengths use a nibble-escape ladder — one nibble `1..15`; `0` then `b != 0` gives
`(b << 4) \| next` (8-bit); `0,0` gives four nibbles big-endian (16-bit). Type 6
is the same decoder with **5-bit** pixels and a 32-entry palette (`cx = 2` to
the setup at `0x9423`, which copies `cx * 16` palette bytes).

The decode chain is

```
shape_draw 0x1D543 -> lcall 0x2133:0x0f83 -> thunk 0x250B3 (DS/ES/SS = 0x60d8)
  -> 0x65c:0x7f0c = file 0x112CC:  call word ptr cs:[bx + 0x6d30]   (bx = format, UNSCALED)
  -> format 8 = file 0x9499
```

`0x9499` reads a **u16 nibble count**, unpacks two 4-bit pixels per source byte
(high nibble first) into scratch `0x43bf:0`, then calls the RLE stage at
`0x954D`, where a control byte selects a run or a literal sequence and **every
emitted byte passes through `xlatb`** — the translation table being the aux
palette selected by the record header.

Everything the section below established survives and is now explained: the
jump-table dispatch is why no `cmp al,8` window exists; the u16 the decoder
reads is why `b4` measured as the nibble count's low byte; and `b3`'s range of
0–7 is the aux palette index.

All three of the gaps flagged when this was first written are closed: the
`al <= 2` cases are the run-only / no-run / wider-length controls above, the
setup at `0x9423` copies `cx * 16` palette bytes to `0x65c:0` for `xlatb`, and
the `cx = 1` vs `cx = 2` variant is simply 16- vs 32-entry palette, i.e. 4- vs
5-bit pixels.

### Type-8 encoder — RESOLVED (2026-08-24)

`work/gr8_encode.py` is the inverse of the decoder's RLE grammar. Its measured
rules are maximal runs of at least three values, adjacent runs grouped under
control `2`, separate run-length escapes for the control-zero path, and a
two-pixel final overrun rule (the first padding value participates in run
scanning when two padding values are present). It re-encodes **736/736** type-8
records byte-identically.

For odd nibble counts, the low nibble of the final packed byte is not consumed
by the decoder. Shipped files contain nonzero values there, so the encoder
carries that unreferenced nibble from the source record; omitting it would make
the decoded pixels correct but the file differ.

#### The original attempt, kept for its measurements

**Established.** The record header's byte `+4` (`b4`) is the payload's **nibble
count, low byte**: across all **736** type-8 records, `(2 × payload_bytes − b4)
mod 256` is only ever **2 or 3** — 338 records at 2, 398 at 3, nothing else.
(The 2-vs-3 split is whether the final nibble is used.) Byte `+3` (`b3`) is
**not** the count's high byte: the full differences `2n − ((b3<<8)|b4)` land on
`(2 or 3) − 256k` for many different `k`, so `b3` is an independent field
taking values 0–7. A nibble-count header is consistent with a
**nibble-oriented** stream, which fits the ~4× ratio against `w*h` (65 bytes
for 256 pixels — roughly half what flat 4bpp would need, i.e. 4bpp plus a run
encoding).

**Ruled out.**

- *The type byte is not dispatched by a byte compare.* The whole binary
  contains only 4 `cmp al,4`, 3 `cmp al,8` and 2 `cmp al,0x0a` sites, and **no
  window of 96 bytes contains all three**.
- *The decoder is not on the load path.* `gfx_init` → `gr_archive_load`
  (`0x8B798`) → `gr_record_read` (`0x8B435`) reads every record **raw** and
  merely checks the byte count against the offset table. No pixel work
  happens at load.
- *It is not one of the four decode doors.* Those are bit-depth expanders
  (8bpp+xlat, 5bpp, 4bpp raw, 4bpp+xlat) keyed on a depth code, and none
  produces 256 pixels from 65 bytes.

**Oracle attempt, 2026-08-22 — also negative, and the reason is useful.**
Drove a fresh character into the 3D view with `work/drive.py` (the scripted
sequence reproduced cleanly on a second run) and hunted a 16-byte signature
from `OBJECTS.GR` record 4 — header included, `08 10 10 00 83 00 23 01 …` — in
guest RAM, intending to set a **read watchpoint** on it and let the decoder
identify itself.

- **0 hits in `0x00000..0xA0000`** (conventional memory).
- **0 hits in `0x00000..0x110000`** after widening past the EMS page frame.
- The page-frame region `0xC0000..0xEFFFF` holds no `.GR` data at all — only
  a BIOS-extension signature at `0xC0000` and what looks like EMM386's own
  code at `0xEC000`.

So the archives are **not resident in the first megabyte during gameplay**.
`AGENTS.md` records that UW2 uses EMS rather than XMS, and under `EMM386` the
EMS backing store lives in extended memory above 1 MB, with only a 64 KB
window mapped at a time. Finding the buffer by signature therefore needs a
scan of all 16 MB, and HMP `xp` makes that impractical — the 1 MB scan alone
takes minutes.

**Static attempt on the callback, 2026-08-22 — blocked, and the blocker is
structural.** `gr_archive_load`'s full signature turns out to be
`(name, start, count, alloc_far, post_far)`: per record it allocates through
`lcall [bp+0x0c]`, reads raw, then calls **`lcall [bp+0x10]` with
`(buf_lo, buf_hi, size, index)`** — a post-processing callback that gets
exactly the buffer, and therefore the best decoder candidate in the binary.
Its address comes from `push 0x3b8 / push 0x5c` at the call site, i.e.
`0x03b8:0x005c`.

✗ **Corrected 2026-08-23** — the three bullets below were sound, but the
conclusion they supported ("that address cannot be resolved from the file") is
superseded. `0x3b8` is a **byte offset into the FBOV `exeinfo` table**, not a
segment: it resolves to segment `0x6509`, stub 12, descriptor `0x0377`, body at
file **`0x8B5C7`** (`ghidra.md` §§19–20, `work/ovl_resolve.py 0x3b8:0x005c`).

Reading it also **eliminates it as the decoder**: `post_far` never references
`[bp+6]`/`[bp+8]`, so it never touches the buffer. It is an allocator — it
records each record's packed `(bank<<12)|paragraph` address in `[0x2184]`,
indexed from the shape-slot table `[0x2188]`, and advances `[0x1504]` by
`ceil(size/16)`. The `.GR` type 8 search must move to whoever reads those
tables at draw time.

The original reasoning, kept because the third bullet is still a useful check:

- **`0x3b8` is not one of the 53 MZ relocation segments** (`0x65c`, the VM
  segment resolved in `ghidra.md` §10c, *is* — so the check discriminates).
- All **14** `push 0x3b8` sites live in `CODE_TAIL`, the Borland `FBOV`
  overlay pool, whose relocations are applied by the *overlay manager* at load
  time and not by the DOS loader.
- Mapping it naively as an image segment (`0x2E00 + 0x3b8*16 + 0x5c` =
  `0x69DC`) lands on a function that ends in a **near `ret`** — which cannot
  be the target of an `lcall`, so the mapping is demonstrably wrong rather
  than merely unverified.

This is the same wall as the `INT 3Fh` thunks (`ghidra.md` §10b): **overlay
segment values have no fixed file mapping.** It explains why several routes to
this decoder have dead-ended.

**Both remaining routes tried, both blocked — 2026-08-22.**

- *Breakpoint the `lcall [bp+0x10]` site at file `0x8B84A`.* **Impossible as
  posed**: `0x8B84A` is past the image end `0x71B80`, i.e. inside the overlay
  pool, which has no fixed linear address. The attempt produced a
  false-looking "did not execute" before the cause was spotted; `rsp_break.py`
  now refuses such targets outright (`ghidra.md` §14).
- *Decode the `FBOV` overlay directory.* Done as far as it goes (`AGENTS.md`,
  `exeinfo`), and it **confirms the blocker rather than removing it**: the
  174-entry table lists resident image segments only, and none of the small
  segments overlay code far-calls through.

So the `.GR` type-8 decoder needs the **overlay manager's runtime state** —
where a given overlay is currently resident — which means instrumenting
`INT 3Fh` or the manager itself. That is a distinctly bigger piece of work
than anything attempted here, and it would unblock the whole overlaid third of
the binary at once, so it is worth doing properly rather than for this one
format.

### The bit-depth expander family, identified — and it is *not* the `.GR` types

Worth recording because it looks like a lead and is not one. The graphics
library's decode API (`ghidra.md` §10e) has four working doors, and reading
all four shows a clean set of **bit-depth expanders**, selected by a depth
code, each preloading an `cx << 4`-byte translation table via `FUN@0x9423`:

| door | table | per iteration | depth |
|---|---|---|---|
| `BX=0x04` | (larger, via `0x948B`) | `lodsb / xlatb / stosb` | 8 bpp + translate |
| `BX=0x06` | `cx=2` → 32 B | 5 bytes → 8 pixels, `ror ax,3` / `ror ax,6` | **5 bpp** |
| `BX=0x08` | `cx=1` → 16 B | 1 byte → 2 pixels, no `xlatb` | 4 bpp raw |
| `BX=0x0A` | `cx=1` → 16 B | 1 byte → 2 pixels, with `xlatb` | 4 bpp + translate |

These are keyed on a **bitmap depth code** (the caller's record byte 0, values
0–5), not on the `.GR` record type byte. `.GR` type `0x08` packs 256 pixels
into 65 bytes (~2 bpp), which none of these produce, so the `.GR` type-8
decoder is somewhere else and was not found.

## `.TR` (terrain tiles) — merged into one file, container holds, visually verified — RESOLVED (2026-08-21)

UW1 ships four files (`F16.TR`, `F32.TR`, `W16.TR`, `W64.TR` — floor/wall ×
two resolutions each, 52+210=262 tiles total). **UW2 ships exactly one,
`work/extracted/D2/DATA/T64.TR`** (1,049,640 B) — no separate floor/wall or
multi-resolution files exist anywhere in `work/extracted`.

### Container — identical model, consolidated content

`u8 version=2; u8 dim=64 @1; u16LE N=264 @2; N×u32LE offsets @4, uniform
stride = dim*dim (4,096 B)` — the exact same shape as UW1's per-file model,
including the same "4-byte gap between table end and first record" UW1
documented (table ends at `4+264*4=0x424`, `table[0]=0x428`).

**264 table slots, but only 256 hold real data.** `table[-1]` (the last of
the 264 offsets) equals the file length exactly, and the trailing 8 entries
all share that same value — i.e. 8 zero-span placeholder slots at the end,
the identical "`offset[i]==offset[i-1]`" empty-record idiom UW1's own `.GR`
docs already established, just applied to `.TR` here for the first time.
Real data spans `table[0]..table[-1]` = exactly `256 × 4,096` B, confirmed
by division with no remainder. **256 is suspiciously close to UW1's 262
(52+210)** — consistent with UW2 collapsing the floor+wall+resolution split
into one flat 64×64 set with a handful of tiles added or dropped, though the
exact per-tile correspondence wasn't attempted.

### Visually verified (UW1's own `cross-project.md` explicitly criticized its `.TR` finding as "resolved on a stride identity alone" — done properly here)

`work/tr_render.py`, same palette-loading approach as `gr_render.py`,
rendered three tiles from spread-out indices:

- tile 0 → a stone archway/doorway texture (clearly a wall tile).
- tile 100 → a blue rocky/icy surface texture.
- tile 200 → a brown dirt/ground texture with an embedded blue
  crystal/mineral vein (clearly a floor tile with a decorative variant).

Three renders spanning the index range, all clearly real, distinct terrain
art — the merged-file, single-resolution hypothesis is now render-verified,
not just arithmetic.

**Not attempted**: which of the 256 real tiles are "floor" vs "wall" by
convention (no header field distinguishes them — would need either the
renderer code or systematic visual sampling across all 256); the 8 empty
slots' purpose; per-tile correspondence against UW1's 262 originals.

## `STRINGS.PAK` — global string table — Huffman coding fully decoded — RESOLVED (2026-08-22)

UW1: `work/expanded/DATA/STRINGS.PAK`, 227,230 B. UW2:
`work/extracted/D1/DATA/STRINGS.PAK`, 429,896 B (`0x68F48`). Both decode with
`work/strings_decode.py` (new, self-contained, run unchanged against either
file — pass the path as its one positional argument).

UW1's own doc had this as **PARTIALLY RESOLVED** with "string pool start +
string-byte encoding still TBD". Both are resolved here, for both games.

### The format, in full

```
u16LE  node_count                                     (181 — identical in UW1 and UW2)
node_count × { u8 char, u8 parent, u8 left, u8 right }   @0x02
u16LE  block_count                                    @0x02 + 4*node_count
block_count × { u16LE block_id, u32LE file_offset }   ascending by both fields
per block, at file_offset:
    u16LE  string_count
    string_count × u16LE  byte offset, relative to the end of this offset array
    Huffman bit stream
```

It is a **canonical-shaped Huffman tree walked bit by bit**: MSB-first within
each byte, `0` → `left`, `1` → `right`, starting from the root; on reaching a
leaf, emit its `char` and restart at the root. `0xFF` in *both* `left` and
`right` marks a leaf. **`'|'` (0x7C) is the string terminator**, not `0x00`
(`0x00` is not in the alphabet at all). Every string starts on a byte
boundary, which is what makes the per-string `u16` offsets usable.

### Three corrections to UW1's reading, all from the same root mistake

UW1's doc read the node table as a *hash/index* table:

- ✗ "`u32[0] = 0x8F09_00B5`: lo16 = 0x00B5 = 181 (entry count); hi16 = 0x8F09
  (special first-entry tag, not 0xFFFF)". There is no such tag: `0x00B5` is
  the node count, and the next two bytes are node 0's `char`/`parent`
  (`0x09` = TAB, parent 137 — UW2 has `0x09`/parent 137 there too).
- ✗ "`u32[1..] = 0xFFFF_xxxx`: (u16 val, 0xFFFF) pairs — a 181-entry
  index/hash table (3-tier: hash → block table → …)". The recurring `FF FF`
  is `left = right = 0xFF`, i.e. **the leaf marker** — it appears in the
  early entries precisely because the leaves are stored first.
- ✗ "V low byte = sequential string index, high byte = category/hash". Those
  two bytes are `char` and `parent`; the "sequential" low byte looked
  sequential because the leaves are **sorted by character code**.

### Verified — two independent invariants, on both files

|  | UW1 | UW2 |
|---|---|---|
| nodes / leaves / internal | 181 / 91 / 90 | 181 / 91 / 90 |
| full binary tree (`2L−1 == N`) | ✓ | ✓ |
| root = last node, `parent == 0xFF` | ✓ | ✓ |
| blocks | 122 | 136 |
| block table end == first block offset | `0x5B4` ✓ | `0x608` ✓ |
| strings decoded / malformed | 10,984 / **0** | 13,166 / **0** |
| decoded characters | 301,661 | 484,315 |
| last string's last byte vs EOF | `0x3779E` / `0x3779E` | `0x68F48` / `0x68F48` |
| **bytes unaccounted for** | **0** | **0** |

The coverage row is the strong one: decoding every string in every block and
tracking the highest byte index consumed lands *exactly* on EOF in both
files, with no slack. Combined with "block table ends exactly where the first
block starts", the entire file is accounted for by the model — there is no
undecoded region left to hide a mistake in.

⚠ **Refined by the rebuild (below):** that check tracks the *highest* byte
index reached, so it proves nothing about gaps *inside* the file. There are
some — six blocks across the two games carry 1–2 unreferenced bytes after
their last indexed string. Small, and now accounted for, but the original
wording implied a completeness the check did not actually establish.

### Rebuilt byte-for-byte — RESOLVED (2026-08-22)

Decoding a format proves you can read it; **re-emitting it byte-for-byte
proves you understood it**, because every field guessed wrong or quietly
skipped turns into a diff. `python work/rebuild.py --strings` reconstructs the
whole file — node table, every string re-encoded from its decoded text using
codes derived by walking the stored tree's parent links, block table with
recomputed offsets — and compares:

| file | original | rebuilt | result |
|---|---|---|---|
| UW2 `STRINGS.PAK` | 429,896 B | 429,896 B | **IDENTICAL** |
| UW1 `STRINGS.PAK` | 227,230 B | 227,230 B | **IDENTICAL** |

Per-string offsets come out equal without being copied, which independently
re-proves the bit order, the code assignment and the `'|'` terminator.

**One thing had to be found to get there.** A first attempt came out 2 bytes
short on UW2 and 6 on UW1. The cause is *unreferenced* trailing data: UW2's
block `0x0008` has `1c 38` after its last indexed string, and UW1 has five
such tails. They are **not zero padding** — decoded as a Huffman stream they
come out as **spaces**, i.e. the original encoder left a little trailing
whitespace behind. The rebuild carries those bytes verbatim; they are the only
thing besides the node table that is copied rather than regenerated.

The alphabets differ slightly (both 91 leaves, coincidentally): UW2 adds
`0x1A` and `%`, drops `^` and `` ` ``. Bit-order was determined by trial —
the other three combinations produce visible garbage, MSB-first/`0`=left
produces English from byte 0 (`"Hey, its all the game strings"`, the same
developer joke that opens UW1's file).

### Block-id map (UW2, from the decoded content)

| block ids | count | content |
|---|---|---|
| `0x0001`–`0x000A`, `0x0018` | 11 | 512 strings each — general UI/messages (`0x1`), character creation (`0x2`), book/scroll titles (`0x3`), object names (`0x4`), qualifiers (`0x5`), spells (`0x6`), talk/UI (`0x7`), `0x18` = "` for level `" |
| `0x0C00`–`0x0C2B` | 18 | short blocks (1–13 strings) — cutscene/endgame text (`0x0C00` = "Dear Avatar,\nGreetings, my old friend!") |
| `0x0E00`–`0x0EA8` | 107 | one block per **conversation**; slot = `block_id − 0x0E00` |

### Cross-file check against `CNV.ARK` — the conversation blocks line up

The 107 conversation blocks were checked against `CNV.ARK`'s record table
(below). With the mapping **`CNV` table index `i` ↔ `STRINGS` block
`0x0E00 + i − 1`**, *all 102* of CNV's records match a string block
(0 unmatched on the CNV side); 5 string blocks (slots 0, 12, 33, 58, 64) have
no conversation record. The three neighbouring shifts (0, +1) leave 12–24
mismatches on both sides, so the −1 alignment is not a coincidence of
density. Two independently-parsed files agreeing on the same 102-element set
is the check that makes the block-id map above real rather than a guess.

**Not attempted**: what the 5 record-less string blocks are for; the meaning
of the block-id numbering gaps (`0x0B`–`0x17`, `0x19`–`0xBFF`); whether the
`0x0C xx` ids follow a scheme.

## `CNV.ARK` — conversation archive — container RESOLVED, record grammar TBD (2026-08-22)

UW1: 558,007 B (`0x883B7`). UW2: `work/extracted/D4/DATA/CNV.ARK`,
281,109 B (`0x44A15`).

### UW1's container reading was wrong; the real one is much simpler

UW1's doc proposed `[u16 header 0x0140] [(u16 offset, u16 id) pairs, 29
non-zero] [u24LE offset clusters @~0x162]`, and flagged its own example as
"not a clean single-field read". ✗ **Withdrawn.** The table is plain
**`u32LE` offsets**, and reading them as `(u16, u16)` pairs is what
manufactured both the "id" field (the always-zero high half of a small
offset) and the "u24 clusters" (mis-split u32s). Measured on UW1's file:

```
u16LE  count = 320  @0x00
320 × u32LE  record offset (0 = empty slot)  @0x02   → ends 0x502
data pool @0x502
```

97 non-zero offsets, strictly ascending, all inside the file, and the table
ends at `0x502` — **exactly** where the first record starts. 97 also matches
UW1's own doc text elsewhere ("each of the 97 conversation blocks…"), which
the 29-pair reading never explained.

### UW2 keeps the table and adds three parallel arrays

Same `u16 count = 320`, but **four** parallel `u32LE[320]` arrays, not one:

| array | file offset | content |
|---|---|---|
| 0 | `0x0002` | record offset into the file (`0` = empty slot) — **102 non-zero**, ascending |
| 1 | `0x0502` | slot flag: **`3` for every one of the 102 slots that has a record**, and only `0` or `1` on the 320−102 empty slots |
| 2 | `0x0A02` | record size |
| 3 | `0x0F02` | record size (a duplicate of array 2 — the two differ *only* at slot 0, which has no record) |

Header ends at `0x1402`; 4 zero bytes of slack; the data pool starts at
`0x1406`.

**Verified:** array 2 equals the gap to the next record for **102 of 102**
records, and `sum(size) = 275,983 = 0x44A15 − 0x1406` exactly — the records
**tile the pool with zero slack**, right up to EOF. Array 1 partitioning
cleanly into "3 ⟺ has a record" is a second, independent consistency check on
the same 102-element set — the same set the `STRINGS.PAK` cross-check above
lands on.

### The conversation VM's 51 builtins, read out of `UW2.EXE` — RESOLVED (2026-08-22)

`python work/cnv_audit.py --builtins`. The function that opens the archive
also registers the VM's entire builtin table, so both are recoverable from one
place. At file **`0x7C39B`** (in `CODE_TAIL`, i.e. an overlay) sits:

```
PUSH BP / MOV BP,SP / PUSH SI
MOV  AX,[0x4834]
ADD  AX,0x400
PUSH word ptr [0x4836]      ; segment of a work buffer
PUSH AX                     ; offset  = [0x4834] + 0x400
PUSH 0xc59                  ; DGROUP:0C59 = "DATA\cnv.ark"
CALLF 0x0000:3009
ADD  SP,0x6
OR   AX,AX
JGE  ...                    ; AX < 0 = failure
```

and immediately after it, a **contiguous run of 51 identical sequences**:

```
PUSH 0x338 / PUSH 0x89 / PUSH 0xc82 / CALLF 0x0000:3031   ; "babl_menu"
PUSH 0x338 / PUSH 0x9d / PUSH 0xc8c / CALLF 0x0000:3031   ; "babl_fmenu"
…
```

`CALLF 0x0000:3031` has **exactly 51 call sites in the whole file**, all of
them here, so this is the complete table. Reading each name pointer against
DGROUP gives, in registration order:

| | | | |
|---|---|---|---|
| `babl_menu` | `babl_fmenu` | `say` | `respond` |
| `get_quest` | `set_quest` | `sex` | `babl_ask` |
| `print` | `show_inv` | `give_to_npc` | `find_inv` |
| `take_from_npc` | `take_id_from_npc` | `identify_inv` | `do_offer` |
| `do_demand` | `do_decline` | `do_judgement` | `end_barter` |
| `setup_to_barter` | `pause` | `set_likes_dislikes` | `do_inv_create` |
| `do_inv_delete` | `check_inv_quality` | `set_inv_quality` | `count_inv` |
| `babl_hack` | `give_all_stuff` | `gronk_door` | `set_sequence` |
| `set_attitude` | `set_race_attitude` | `take_from_npc_inv` | `add_to_npc_inv` |
| `place_object` | `transform_talker` | `remove_talker` | `x_skills` |
| `x_traps` | `x_obj_stuff` | `x_obj_pos` | `find_barter` |
| `find_barter_total` | `give_ptr_npc` | `x_clock` | `x_exp` |
| `teleport_player` | `teleport_talker` | `switch_pic` |  |

**This closes the loop with UW1's data-side finding.** UW1's doc lists the
identifier strings it found inside `CNV.ARK`'s pool — `find_barter_total2`,
`do_inv_delete`, `do_demand`, `gronk_door`, `set_likes_dislikes`, `pause`,
`do_decline`, `do_judgement`, `end_barter`, `setup_to_barter`, `count_inv`,
`set_inv_quality`, `x_obj_stuff`, `x_obj_pos`, `x_traps`, `x_skills`,
`set_attitude`, `remove_talker`, `add_to_npc_inv`, `take_from_npc_inv`,
`place_object`, `set_race_attitude` — and called them "serialized
condition/action script nodes" without knowing what they bound to. They are
**imports**: each conversation record names the engine builtins it calls, and
this table is the other end of that link. A second, separate builtin group
lives just before these in DGROUP (`compare`, `random`, `plural`, `contains`,
`append`, `copy`, `find`, `length`, `val`, `say`, `respond` at
`DGROUP:0BA7..0BEE`), which is **not** registered through this call site —
what registers those is TBD.

### The registration argument is a far pointer into the overlay thunk table — IDENTIFIED

Each site pushes `(u16 seg, u16 off)` before the name, i.e. `register(name,
far_fn)` with the segment pushed first — the normal 16-bit far-pointer push
order. Three things say `far_fn` targets an `INT 3Fh` overlay thunk:

- Only **three** distinct segment values occur (`0x0300`, `0x0308`, `0x0338`),
  and offsets are **distinct within each segment**.
- **All 51 offsets are ≡ 2 (mod 5)** — the 5-byte stride of the `INT 3Fh`
  thunk table. (Re-measured here and matching `AGENTS.md`: **1,006** `CD 3F`
  pairs spanning `0x66AB0..0x68E7E`, dominant gap 5.)
- Fitting the one unknown — the load-time segment base — puts **33 of 51** far
  pointers *exactly* on a `CD 3F` byte pair, and the remaining 18 exactly one
  byte off. Against a null of **0.10 / 51** averaged over all 32,768 candidate
  bases, and with no base anywhere scoring ≥ 40, this is not a fit artefact.

**Why this is IDENTIFIED and not RESOLVED:** the base cannot be pinned
statically — two bases (`0x61C4`, `0x61C9`, five apart, i.e. one thunk stride)
tie at 33, and the residual ±1 byte on 18 entries is unexplained by a uniform
5-byte record (the gap histogram shows the table is *not* uniformly strided:
868 gaps of 5, but also 77 of 32 and a scattering of others). Settling it
needs a live read — breakpoint the registration routine on the oracle and dump
the far pointer it receives — not more static fitting.

### Record body: LZSS-compressed, and the layout comes from the loader — RESOLVED (2026-08-22)

UW1 stores its records plain; **UW2 compresses them**, which is what the
`0xFF` bytes interrupting identifiers in a raw dump are. Both the compression
and the record layout were read out of `UW2.EXE`, then verified against all
102 records — `python work/cnv_decode.py`.

#### The load path

`FUN@0x74E15` (in `CODE_TAIL`) is the conversation loader:

```
malloc(0x5000)                  -> [0x46f2]:[0x46f4]   the scratch buffer
lcall 0x2e8:0x48 (2, [0xc66], buf)                     read record [0xc66] of archive 2
lcall 0x2e8:0x39 (2)                                   close
push cs / call 0x75863                                 parse it
```

The `0x5000` (20,480 B) buffer is the first check that fell out: the `u32` at
record `+0x00` reaches **18,086** at most across the 102 records — it fits,
and the next-largest candidate field does not. It is the uncompressed length.

#### Compression — textbook Okumura LZSS

Ring `N = 4096`, `F = 18`, `THRESHOLD = 2`, ring zero-filled with the write
cursor starting at `N − F = 4078`. Flag byte, **low bit first**; `1` = literal
byte, `0` = a two-byte pair with

```
offset = i | ((j & 0xF0) << 4)          length = (j & 0x0F) + 3
```

**The stream starts at record `+0x04`**, not at `+0x0E`. That was the single
correction that unlocked everything: `+0x04` is the first flag byte (only ever
`0x7F`, `0xBF` or `0xDF` — a few literals then an early match into the
still-zero ring, which is how the compressor encodes the header's zero
fields), and `+0x00..0x03` is the uncompressed length. The "always `28 08 00
00` at `+0x05`" constant measured earlier is simply the first four *decoded*
bytes, identical in every record.

Verified on all 102: output length equals the header `u32` **and** the source
stream is consumed exactly, with no bytes left over — both at once, 102/102.
Max match offset observed is **4095**, so the ring really is 4096 (2048 decodes
this one file identically but cannot be the true size).

#### Record layout, straight off the parser at `0x75863`

| off | width | meaning |
|---|---|---|
| `+0x00` | u32 | skipped by the parser (`add [0x46f2],4`); constant `0x00000828` in every record |
| `+0x04` | u32 | **code size in words** — the parser `malloc`s `words*2` for the bytecode |
| `+0x08` | u16 | → global `0x4712` |
| `+0x0A` | u16 | **`STRINGS.PAK` block id** — global `0x3498` |
| `+0x0C` | u16 | memory size in words — `malloc((words + 0x800) * 2)`, so VM data then a 2,048-word stack |
| `+0x0E` | u16 | import count |
| `+0x10` | … | import records |
| … | | `code_words * 2` bytes of bytecode |

Import record: `u16 name_length`, `char name[length]` (no NUL in the stream —
the parser copies it out and terminates it itself), then four `u16`s. The
parser stores the first at table entry `+0x1A` and the second at `+0x18`.

#### Four independent invariants, all 102/102

| check | result |
|---|---|
| LZSS output length == `u32 @+0x00` **and** source fully consumed | 102/102 |
| every import name is a valid C identifier | 102/102 |
| `0x10 + import table + 2*code_words` == uncompressed length (the record tiles exactly) | 102/102 |
| `u16 @+0x0A` == `0x0E00 + slot − 1`, the conversation's `STRINGS.PAK` block | 102/102 |

The last row is the payoff: the record's own header names its string block,
and it agrees with the `−1` slot mapping derived independently from the two
files' index tables and from the record's `+0x0F` byte. Four separate routes
to the same alignment.

#### The import table binds to the builtins found in the EXE

Every conversation carries the **same 94 imports** (only 3 distinct tables
exist across all 102 records, differing in the trailing fields). The fourth
field splits them cleanly into two namespaces, each densely numbered from 0:

| kind | count | slots | what |
|---|---|---|---|
| `0x0111` | 63 | 0–62 | **functions** |
| `0x010F` | 31 | 0–30 | **variables** — `game_days`, `game_mins`, `game_time`, `dungeon_level`, `riddlecounter`, `new_player_exp`, and the `npc_*` / `play_*` state pairs |

**51 of the 63 functions are exactly the EXE registration table** documented
above — a complete match, no misses in either direction. Nine more
(`compare`, `random`, `plural`, `contains`, `append`, `copy`, `find`,
`length`, `val`) are the second DGROUP group, registered at file `0x74F55`
through `FUN@0x765E6`. That routine walks this very table with a 32-byte
stride, `strcmp`s the name, and writes the builtin's far pointer to
`[0x470e] + entry[+0x1A] * 4` — so **an import's first field is its index into
the VM's function-pointer array**, which is why the numbering is dense.

#### The bytecode — decoded, and it is a *second* VM

`analysis/ghidra.md` §11 has the interpreter (`FUN@0x75A95`, 42 opcodes,
jump table at file `0x75E1B`). It is **not** the threaded-code engine of
`ghidra.md` §§8–10 — different dispatch site, different table, 42 opcodes vs
~111. UW2 runs two bytecode engines.

All 102 conversations disassemble cleanly: a linear sweep lands exactly on
`code_words` every time, and all **3,485** `calli` operands resolve to a
function import declared in that same record — i.e. the bytecode's call
operand is the import slot, which is where `FUN@0x765E6` writes the builtin's
far pointer, which is what the 51 registration sites supply. 179,694
instructions total. Tool: `python work/cnv_disasm.py`.

### The variable half of the import table — RESOLVED (2026-08-22)

The 63 **function** imports are bound by `FUN@0x765E6` writing a far pointer
into `[0x470e]`. The 31 **variable** imports are bound by a completely
different mechanism, found via the string-xref pass (`ghidra.md` §12):

```
[bp-2] = <the value, computed inline>
push 1 / push &[bp-2] / push "npc_whoami"
lcall 0x2f8:0x98          ; publish(name, &value, 1)
```

i.e. each variable's *current* value is recomputed and published **by name**,
rather than a pointer being registered once. `FUN@0x07DD53` does 30 of them;
`FUN@0x0792AD` does `npc_attitude` (twice).

The partition is exact — of 32 publish sites, 30 distinct names:

| check | result |
|---|---|
| variable imports (kind `0x010F`) published here | **30 / 31** |
| names published that are *not* a variable import | **0** |
| overlap with the 63 function imports | **0** |

**`riddlecounter` is the one variable never published** — and the string does
not occur anywhere in `UW2.EXE`, nor in UW1's `UW.EXE`. Every conversation
declares it as an import and no engine code provides it: a dangling import,
recorded as such rather than assumed to be bound somewhere unseen.

### The three unregistered function imports — RESOLVED (2026-08-22)

`add_event`, `do_input_wait` and `gronk_trigger` are declared by all 102
conversations and registered nowhere. None of the three strings occurs
anywhere in `UW2.EXE` — the same situation as `riddlecounter`. So they are
**dangling imports**, and the obvious worry is that a `calli` on one would
jump through an uninitialised pointer.

It would not. The function-pointer array is **pre-filled with a default
handler** before any registration runs (`FUN@0x75A12`):

```
ax = [0x4718] * 4 ; malloc          ; -> [0x470e]:[0x4710]
for si in 0 .. [0x4718]-1:
    es:[bx]   = 0x00ed              ; every slot gets the same
    es:[bx+2] = 0x02f8              ; far pointer 0x2f8:0x00ed
```

So an unregistered import resolves to a shared stub at `0x2f8:0x00ed`
(offset `0xED` ≡ 2 mod 5 — thunk-aligned, consistent with the overlay model),
and `FUN@0x765E6` only ever *overwrites* that default. Unimplemented builtins
are safe by design.

Measured against the shipped bytecode: of the 63 function imports, **18 are
never called by any conversation** — including `add_event` and
`gronk_trigger`. `say` and `respond` are in that list too, which is a good
independent check on `ghidra.md` §11: they are invoked by the dedicated
opcodes `0x27`/`0x28`, which dispatch **by name** through the import table
rather than by slot, so they correctly never appear as a `calli` operand.

**`do_input_wait` is called exactly once** in the whole corpus — conversation
slot 47, `STRINGS` block `0x0E2E`, at word 1808:

```
1803  pushi 0x24
1805  say                  ; string 0x24
1806  pushi 0x0
1808  calli do_input_wait   <-- resolves to the default stub
1810  drop
1811  pushi 0x25
1813  say                  ; string 0x25
```

which is exactly "speak a line, wait for input, speak the next". The two
strings are a developer joke left in the shipped game — a rat monologue that
threatens to "kill Lord British, buy EA, sell them off to get an airplane"
— i.e. **test content**, which is a satisfying explanation for why the only
call to an unimplemented builtin in the entire game is here. The `u16` at `+0x08`, the constant `0x0828` at `+0x00`, and
the imports' third and fourth fields (`0x0000` / `0x0129` / `0x012B`) are
unexplained. (All 42 opcodes are now decoded — `ghidra.md` §11.)

## `LPF` cutscene containers (`CUTS/CSxxx.Nxx`) — container and frame payload RESOLVED (2026-08-25)

39 files carry the `LPF ` magic in `work/extracted`, 2,896 B to 393,182 B.
`python work/lpf_audit.py`. UW1's doc stopped at a partial reading of the
first `0x80` bytes and guessed at two fields (`N = probably frame/patch
count`, `M unknown`); the large-page layer below it is new here, and one of
UW1's guesses is now settled.

### Header — measured across all 39 files

| off | width | value | note |
|---|---|---|---|
| `0x00` | 4CC | `LPF ` | |
| `0x04` | u16 | `0x0100` | constant in all 39 |
| `0x06` | u16 | 1–6 | **number of large pages** — this is UW1's "group count" |
| `0x08` | u32 | 9–0x31 | **total record (frame) count** |
| `0x0C` | u16 | `0x0100` | constant — max records per large page |
| `0x0E` | u16 | `0x0500` | **offset of the large-page directory** |
| `0x10` | 4CC | `ANIM` | the only content type in any file |
| `0x14` | u16 | `0x0140` = 320 | width |
| `0x16` | u16 | `0x00C8` = 200 | height → VGA mode 13h |
| `0x18` | u16 | `0` | constant |
| `0x1A` | u16 | `0x0101` or `0` | |
| `0x1C` | u16 | `0x0100` | constant |
| `0x40` | u32 | — | **duplicates** the record count at `0x08` |
| `0x44` | u32 | small, varies | |

UW1 read `0x0C..0x0F` as `u8 0 / u16 0x0001 / u8 5`; the real split is two
`u16`s, `0x0100` and `0x0500`, and the second is a *file offset* that the
structure below confirms. UW1's "`0x40 u32 N (≤ res_count)`" is exactly equal
to the record count in all 39 UW2 files, not merely ≤ it.

### Large pages — the layer UW1 never reached

```
0x0500  directory: 256 × { u16 baseRecord, u16 nRecords, u16 nBytes }
0x0B00  ( = 0x0500 + 256*6 )  large pages, stride 0x10000:
        page k at 0x0B00 + k*0x10000
            u16 baseRecord, u16 nRecords, u16 nBytes, u16 0   (repeats the entry)
            u16 size[nRecords]
            record payloads, back to back
```

| check | result |
|---|---|
| `sum(entry.nRecords)` == the header's record count | **39/39** |
| every page at `0x0B00 + k*0x10000` repeats its own directory entry | **39/39** |
| `sum(record sizes)` == that page's `nBytes` | **60/64 pages** |

The page-repeat row is the strong one: it is a 6-byte match at a computed
address, in every page of every file, so both the `0x10000` stride and the
`0x0B00` base are confirmed rather than assumed.

**Pages are not stored in record order.** `CS012.N01` has pages covering
records 4, 12, 24, **0**, 36, 44 in that file order — the directory is the
mapping, and reading pages sequentially would scramble the animation.

**36% of all records (631 of 1,722) are zero-length**, i.e. frames that repeat
the previous one — consistent with delta-coded animation, and the reason a
49-frame cutscene fits in six pages.

### The four pages that do not balance — recorded, not explained

`CS002.N07` p0, `CS000.N03` p0, `CS000.N06` p0, `CS002.N02` p0. In each the
residual `sum(sizes) − nBytes` is **exactly `−(2·nRecords + 8)`** — the size
table plus the page header — i.e. their `nBytes` counts the whole page where
the other 60 count only the payloads. Why these four and not the rest is
**not known**, and no rule is recorded that would paper over it. All four are
single-page files whose page 0 is dominated by 4-byte records.

### Filenames are built in *octal* — RESOLVED

`FUN@0x811FC` does `strcpy(buf, "CUTS\\csXXX.nXX")` (`DGROUP:111A`) then
overwrites the digits from two integer parameters with
`sar ax,6 / and al,7 / add al,0x30` — repeated for shifts 6, 3, 0 on the
first parameter (`buf+7..9`) and 3, 0 on the second (`buf+12..13`). Three-bit
groups, so **the numbers in these filenames are octal**. That is why the
shipped set contains `CS040`, `CS403` and extensions `.N10`–`.N15` with no
digit above 7 anywhere. `CUTS\lbackxxx.byt` (`DGROUP:10F6`) and
`CUTS\csXXX.n00` (`DGROUP:1129`) are the other two templates.

Same digit idiom as the level/save loader in `ghidra.md` §9, which is a point
in favour of that reading too.

**And the same for the music files — confirmed from the shipped filenames
(2026-08-22).** `music_request_track`'s loader builds `uwr00.xmi` (template at
`DGROUP:031F`) with the identical 3-bit construction: `sar ax,3 / add al,0x30`
for the first digit, `and al,7 / add al,0x30` for the second. The prediction
that follows is testable without touching the code: octal filenames can never
contain an 8 or a 9. The 34 shipped `.XMI` files are `UWA01..07, 10..17, 30,
31` and `UWR` the same — **digits `01234567` only, no 8 or 9 anywhere**. So
`UWR17` is track 15, not 17, and a port that counts in decimal will look for
files that do not exist.

### Palette and record payload — RESOLVED 2026-08-25

The 0x400 bytes at `0x100..0x4ff` are 256 four-byte palette entries in
`B,G,R,0` order. The colour channels are 8-bit values and the fourth byte is
zero in the connected intro files. The DOS player copies this block into its
VGA palette staging area before presenting the corresponding chunk. `LBACK`
files are 64,000 indexed pixels and use the palette active for the associated
cutscene chunk; the browser fixture uses `CS000.N02`'s palette for
`LBACK000.BYT`, matching the captured exterior frame.

Each record starts with a four-byte header. If header byte 1 is nonzero, the
little-endian word at bytes 2–3 is the initial byte position; odd positions
are rounded up to the next even position. Otherwise decoding starts at byte 0.
The command stream begins at byte 4 and updates a persistent 320×200 indexed
framebuffer, initially zero-filled. A record with no payload repeats the
previous frame.

The signed-byte commands are:

| command | action |
|---|---|
| `1..127` | copy that many literal bytes and advance the destination |
| `0` | read a count and value byte, fill the count with the value |
| `-1..-127` with low 7 bits nonzero | skip the low-seven-bit count |
| negative command with low 7 bits zero, signed u16 positive | long skip by that value |
| the same with signed u16 zero | end this record |
| the same with signed u16 negative and `raw & 0x7fff >= 0x4000` | run `((raw & 0x7fff) - 0x4000)` bytes with the following value |
| the same with signed u16 negative and `raw & 0x7fff < 0x4000` | copy that many following literal bytes |

The implementation is [`work/cutscene_export.py`](../work/cutscene_export.py)
and its browser counterpart is [`browser/uw2-cutscene.js`](../browser/uw2-cutscene.js).
Both retain the four whole-page accounting anomalies recorded above instead
of silently treating them as payload pages. The connected `CS000.N01`,
`CS000.N12`, and `CS000.N02` fixtures are balanced payload pages and decode
deterministically; their source, palette, record-count, page-balance, and every
indexed-frame hash are checked by `analysis/cutscene-fixtures.json`.

This interpretation agrees with the independently published UW1/UW2 format
description's LPF page and delta-stream model ([format specification](https://bootstrike.com/Ultima/Online/uwformat.php)); the local disassembly and
the shipped-file hash fixtures are the authority for this port. The N00
command stream remains a separate DOS-analysis layer and is not loaded by the
current canvas runtime; the browser uses the four explicit connected source
files. Text, speech, exact DOS timing, and every command's visual side effect
remain explicitly marked `Unproven` until their DOS path is captured.
