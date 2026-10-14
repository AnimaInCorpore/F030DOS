# UW data formats (verified headers, `work/expanded/`)

All offsets/fields below were verified against actual file bytes, not guessed.
"LE" = little-endian. All files are LZH-expanded copies in `work/expanded/`.

## `.GR` — sprite archives (DATA/*.GR) — container + type 4/8/0x0a pixel formats RESOLVED (2026-08-25)

**Container, code-verified** against the actual parser in `UW.EXE`
(`FUN_CODE_TAIL__078b17` @ file `0x078B17`, in the FBOV overlay pool —
decompiled in `work/ghidra_export/uw_c.c` around line 324043; reads a 1-byte
type tag + 2-byte count, then `fread`s `(N+1)*4` bytes as the table in one
call — see §"Code cross-reference" below):

```
[u8  type   ]  -- NOT a "version": equals an extension-table index (see below)
[u16LE N    ]  -- record count
[ (N+1) x u24LE table entries @3, 4-byte stride (3-byte value + 1 pad) ]
```

`table[0] == 3+4*(N+1)` always (it points at its own end, i.e. the start of
record 0 — redundant but genuinely stored, not implicit). `table[N] ==
filesize` exactly on every file (confirmed on all 33 `.GR` files). Record
*i* spans `[table[i], table[i+1])` for `i = 0..N-1`.

*(This supersedes two earlier, wrong drafts of this section: the first
assumed `table[0]` was record 0's start with no earlier entries, which
only happened to hold for GENHEAD.GR because its record 0 is zero-length.
The second — arithmetically self-consistent but structurally wrong —
treated bytes 3-4 as 2 bytes of padding and started an N-entry table at
byte 7; that landed on the identical record boundaries by coincidence
[`7+4N == 3+4(N+1)`], so every pixel-format finding below, which only
depends on record boundaries, is unaffected — but it silently left bytes
5-6 unexplained. They're `table[0]`'s low 3 bytes, not padding.)*

**The type byte is a shared-loader selector, not a per-file version.**
`FUN_CODE_TAIL__078b17` takes a `type` parameter and asserts the file's
first byte equals it, then builds the path from a 5-entry extension table
at file `0x060710`: `.gr\0 .tr\0 .cr\0 .sr\0 .ar\0` (terminated `0xFFFF`),
indexed as `type*4+0x1421`. So `type=1` *is* "this is a `.gr` file" — and
this is independently confirmed by `.TR`'s own header (already documented
below): every `.TR` file's first byte is `2`, matching `.tr`'s table index.
`.cr`/`.sr`/`.ar` share this same loader but no such extensions exist in
`work/expanded/` — either unused in the shipped game or hidden under
different names.

**Code cross-reference** (all in the FBOV overlay pool, `CODE_TAIL`,
addresses = file offsets):
- `FUN_CODE_TAIL__078b17` (file `0x078B17`) — open+parse container (above).
- `FUN_CODE_TAIL__078c6c` (file `0x078C6C`) — per-record seek+read (last
  record's size comes from `ftell()`, not `table[N]`, but resolves to the
  same value since `table[N]==filesize`).
- `FUN_CODE_TAIL__07905c` (file `0x07905C`) — generic per-resource-type
  engine: opens the container, then for each record calls an
  **`alloc(size)`** callback followed by a **`process(buffer,size,index)`**
  callback — the process callback is where per-record pixel decoding
  (header parse + `type=8` decompression) must happen. Its address resolves
  to a Borland overlay logical segment (`0x390:0x7a`/`0x57`/`0x5c`/`0x8e` for
  different resource wrappers) — that indirection is **no longer a blocker**:
  the overlay map is resolved (`analysis/uwexe.md` §13.6) and all of these
  routines sit in **overlay unit row 114** (file `0x78A80`, code `0xB61`,
  stub `0x5E750`/seg `0x5B55`, 24 entry points), which was resident at
  segment `0x6B60` in the 2026-08-23 trace — so the relocated unit can be
  read out of `work/trace/uw.ram` and disassembled as one segment.
- `FUN_CODE_TAIL__0793f0` (file `0x0793F0`) — master startup loader: opens
  `data/allpals.dat`, then calls the `.gr` engine ~20 times by name
  (`"question"`, `"objects"`, `"animo"`, `"buttons"`, `"cursors"`, …),
  confirming these files are all loaded through the same generic path.
- VGA confirmed as **320×200 unchained ("Mode X") 4-plane** — palette DAC
  writes via ports `0x3C8`/`0x3C9` (`FUN_2ec4_005b`, file `0x21E9B`); pixel
  writes via Map Mask port `0x3C4`/`0x3C5` index 2, framebuffer
  `A000:(x>>2)+(199-y)*80` (`FUN_2ec4_008f`, file `0x21ECF`); the blitter
  (`FUN_2ec4_00dc`, file `0x21F1C`) does a straight 1-byte-per-pixel,
  4-plane-interleaved copy with **no RLE/compression logic in the blit
  itself** — consistent with decompression happening earlier, in the
  still-unlocated `process` callback.

Record header is **5 bytes**, not 12: `[u8 type][u8 width][u8 height][u8 b3][u8 b4]`.

- **`type=4`: raw 8bpp indexed pixels, row-major.** Payload length ==
  `width*height` **exactly** — confirmed byte-exact on **all 617 non-empty
  `type=4` records across the 32 standard archives** (DOORS, CHARHEAD,
  ARMOR_F/M, SPELLS, etc.
  are pure `type=4`). E.g. DOORS.GR record 0: `04 20 40 00 08` → `w=32
  h=64`, payload
  2048 B = 32×64 exact. SPELLS.GR record 0: `04 10 12 20 01` → `w=16 h=18`,
  payload 288 B = 16×18 exact.
  **Visually verified** (`work/gr_render.py`, `PALS.DAT` palette 0, VGA
  6-bit→8-bit scaled): CHARHEAD.GR rec0 → a bearded head portrait, DOORS.GR
  rec0 → a wooden door with a handle, SPELLS.GR rec0 → a dagger icon,
  ARMOR_F.GR rec0 → an armor-piece icon. All four render as coherent,
  recognizable art — confirms container, header, pixel layout, and palette
  simultaneously.
- **`type=0x0a` (10): 4-bit packed indexed pixels, FLAT nibble stream (no
  per-row byte alignment), +1 trailing byte** (always present, purpose TBD
  — terminator?). `payload_len == ceil(width*height/2) + 1`, confirmed
  **exactly on all 20 non-empty `type=0x0a` records** in the corpus
  (CURSORS.GR ×19, QUESTION.GR ×1) — including odd-width records (e.g.
  `w=11 h=12`, `w=43 h=15`) that only fit the flat-stream formula and
  disproved an earlier per-row-padded version (off by exactly `h` bytes on
  every odd-width record — the tell that rows aren't byte-aligned). Nibble
  values are small (≤0xD), consistent with a local 16-entry palette (not
  yet identified — probably a fixed remap table, not a direct `PALS.DAT`
  slice). Only used by these two small UI-cursor files. **Visually
  verified** (grayscale nibble×17, packing math only — true colors
  unknown): QUESTION.GR rec0 → a literal "?" glyph; CURSORS.GR rec0/rec1 →
  crosshair-style cursors; rec4/rec12 → distinct pointer/arrow cursor
  shapes, all clean with no shearing artifacts. Confirms the packed layout
  independently of the `type=4` path.
- **`type=8`: nibble-packed, RLE-compressed 16-colour pixels — RESOLVED.**
  Used by OBJECTS.GR (464 records), WEAPONS.GR (224), ANIMO.GR (64),
  BUTTONS.GR (108), and VIEWS.GR (1): 769 records total. The 5-byte record
  header's first four bytes are followed by `[u16LE nibble_count]` beginning at
  record byte `+4` — so the legacy `b4` byte is the count's low byte — and
  then `ceil(nibble_count/2)` packed bytes, high nibble first. The unpacked
  stream uses a run/literal grammar: controls greater than 2 emit a run,
  control 2 groups run-only items, control 1 emits no run, and control 0
  selects the wider run-length form. Every emitted nibble passes through the
  16-byte auxiliary palette selected by `b3` from `ALLPALS.DAT`.

  `work/gr8_decode.py` decodes **769/769** records without overrun. The
  original decoder emits `w*h`, `w*h+1`, or `w*h+2` bytes; UW1's distribution
  is 197/258/314 records respectively. `work/gr8_encode.py` reverses the
  measured greedy grammar and re-encodes **769/769 byte-identically**, including
  the unconsumed low nibble in odd-length final packed bytes. This result was
  first recovered in UW2 and then checked against UW1's complete corpus; the
  same engine format is confirmed, not assumed.
- **`b3`/`b4` semantics:** for `type=8`, `b3` is the auxiliary-palette index
  and `b4` is the low byte of the u16 nibble count. For `type=4`, the two
  fields remain resource metadata rather than pixel dimensions.
  Empirically constant within same-`(width,height)` groups — e.g.
  ARMOR_F.GR's 64 records form 5 distinct size-classes, each with its own
  fixed `(b3,b4)`, repeated in blocks of 3 consecutive records (plausibly 3
  material-tier variants per armor-piece slot; unconfirmed). No arithmetic
  relationship to width/height found (ruled out as a hotspot/hash of them).
  CHARHEAD.GR: all 28 populated portraits share one identical
  `w=34 h=34 b3=0x84 b4=0x04` — constant across the whole file, so at least
  there it's file/class-level metadata, not per-image content.
- **Empty records** exist (`offsets[i-1]==offsets[i]`, span 0): e.g.
  GENHEAD.GR records 0–4 (of 64) and CHARHEAD.GR records 28–55 (of 56) —
  gaps in a portrait/head table (unused slots).
- **`PANELS.GR` is a loader-level outlier**: it keeps the same outer offset
  table but has no 5-byte per-record headers. UW1 has four records with spans
  `9462, 9462, 9462, 360` bytes. Records 0–2 are raw 8bpp panels, exactly
  `83×114` pixels each; the apparent `00 00 00 00 ee …` "header" is simply
  the first five pixels. `work/gr_render.py PANELS.GR <0|1|2>` renders them
  with `PALS.DAT` palette 0. The dimensions are caller-supplied, not stored.
- **`PANELS.GR` record 3 remains open**: it is a 360-byte blob with a layout
  distinct from the three panels. Its factorisations have not yielded a
  coherent image or a verified structure, so the renderer deliberately does
  not interpret it.

Reproduce with `work/gr_probe.py` (structural dump of every file),
`work/gr_render.py <FILE.GR> <record#> <palette#>` (PNG render via Pillow),
and the validation commands in `work/rebuild.py`.

`ALLPALS.DAT` is 513 bytes: 32 auxiliary 16-entry palettes plus one trailing
byte. `work/gr_encode.py`, exercised by `python work/rebuild.py --gr-rebuild`,
rebuilds all **32 standard `.GR` archives byte-identically**. `PANELS.GR` is
still excluded because its fourth record is divergent; the first three
records are now covered by the raw-panel renderer above.

TBD: `PANELS.GR` record 3; the local 4-bit palette used by `type=0x0a`.

## `.TR` — 3D texture/terrain tiles (DATA/F16.TR, F32.TR, W16.TR, W64.TR) — RESOLVED

```
[u8  version=2]
[u8  tile dimension (16 | 32 | 64) @1]
[u16LE record count N @2]
[N x u32LE file offsets @4, uniform stride = dim*dim]
[dim x dim raw tile bytes per record, no per-record header]
```

Verified:
| file  | dim | N   | rec0   | stride  | filesize |
|-------|-----|-----|--------|---------|----------|
| F16   |  16 |  52 | 0x00D8 | 0x100   |  13,528  |
| F32   |  32 |  52 | 0x00D8 | 0x400   |  53,464  |
| W16   |  16 | 210 | 0x0350 | 0x100   |  54,608  |
| W64   |  64 | 210 | 0x0350 | 0x1000  | 861,008  |

All tables monotonic, uniform stride = dim×dim, 4-byte gap between table
end and first record (same invariant as .GR). W16 and W64 share the same
table start (0x350) and the same first data block — the F (floor?) and
W (wall?) families are parallel tile sets; 52 floor tiles, 210 wall tiles.

Tile bytes are raw per-pixel values: floor tiles ~0xEC–0xEF with sparse
0x79–0x7C breaks; wall tiles ~0x9B–0x9E shading values with 0x03 (clear?)
markers. Values look like palette indices or 4-bit shade pairs — final
interpretation needs the texture blitter in UW.EXE.

## `CNV.ARK` — conversation/script archive (558,007 B = 0x883B7) — container skeleton known, byte-exact offset-table decode TBD

```
[u16LE header @0x00 = 0x0140 (320)]
[(u16LE offset, u16LE id) pairs from 0x02, 4-byte stride, 29 non-zero pairs,
 zero-padded toward 0x140]
[u24LE offset clusters @~0x162, 4-byte stride (3-byte value + pad)]
[data pool from ~0x140 onward]
```

Two earlier drafts of this section proposed conflicting header decodes;
re-checked against raw bytes, neither reproduces as originally stated:
- A flat u32LE stride-4 read from byte 0 gives `0x140, 0x05020000, 0x19480000,
  0x4B9A0000, …` — not ascending, contradicting the "ascending offset table"
  claim it was cited for.
- `(u16 offset, u16 id)` pairs from byte 2 DO reproduce the previously-quoted
  ascending numbers (0x502, 0x1948, 0x4B9A, 0x6D54, 0x95E4, 0xAC9C, 0xC854,
  0xE00A, 0xEE48 = pairs 1–9, id=0) — but only by dropping pair 0 (offset 0)
  and splicing in the unrelated header value, so even that quoted example
  wasn't a clean single-field read. The id field does step 0→1→2 in blocks of
  10/10/9 pairs (29 total, matching the "29 pairs" claim but not the old
  "10/10/8" id-count). The offsets do resolve to real record starts — id=0
  offsets 0x502 and 0x6D54 both land exactly on `28 08 00 00 …
  "find_barter_total2" 00 …` (byte-verified) — which contradicts the old
  "id 0 = conditions / id 1 = actions" labeling, since `find_barter_total2`
  was cited as an id-1 "action" name. So the (offset,id)-pair container shape
  is a reasonable working hypothesis; id-field semantics, per-id counts, and
  record grammar are NOT resolved.

Data pool: repeating ASCII identifier names (`find_barter_total2`,
`do_inv_delete`, `do_demand`, `check_inv_quality`, …) interleaved with small
u8/u16 opcode/parameter bytes — serialized condition/action script nodes,
e.g. @0x6D54 (byte-verified):
`28 08 00 00 | 13 11 00 00 | 00 00 | 04 | 0E 2F 00 | 52 00 | 11 00 |
"find_barter_total2" 00 | 01 00 11 01 29 01 0B 00 | "fin…"…`
80 distinct identifiers in the whole file; each of the 97 conversation blocks
references them (top names ×97: find_barter1, find_inv0, x_obj_stuff,
x_obj_pos, x_traps, x_skills, set_attitude, remove_talker, add_to_npc_inv,
take_from_npc_inv, place_object, set_race_attitude, gronk_door,
set_likes_dislikes, pause, do_decline, do_judgement, end_barter,
setup_to_barter, count_inv, set_inv_quality, …).
u24LE clusters just past the header, e.g. @0x162: `EE 1E 03 00`,
`FE 2F 03 00`, `0C 43 03 00` = 0x031EEE, 0x032FFE, 0x03430C (byte-verified).
File length ≡ 3 (mod 4): 4×139,501 + 3 = 558,007. This is the
**conversation/dialogue + trigger-script** database (CRIT-style names like
gronk_door, Lurk reference the creature world).

TBD: id-field semantics, exact per-id counts, record grammar, u24 cluster role.

## `LEV.ARK` — level archive (290,864 B = 0x47030) — container skeleton RESOLVED

```
0x0000: u16LE 135 (record count)
0x0002: u16LE 542 (0x21E; meaning TBD)
0x0004: variable-length record stream (mostly 10 B: u16 id, u32 start, u32 end;
        some records carry trailing extra words; null records (0,0,0);
        0xF0-sentinel records (u16 0, u32 0x0000F0, u32 0x0000F0, u16 0xF0))
0x….  : data pool up to 0x47030
```

**Corrected model (2025-06, byte-verified):** the earlier "135×12 B" table was
mis-aligned. The real records are a *variable-length stream*; key records
(verified against raw bytes):

| rec | id | start  | end    | size   | note |
|-----|----|--------|--------|--------|------|
| 0   | 0  | 0x7E26 | 0xFA2E | 0x7C08 | + trailing u16 0x7636 (= start−0x7F0) |
| 1   | 1  | 0x1F23E| 0x26E46| 0x7C08 | + trailing u32 0x2EA4E + u16 0x6656 |
| 2   | 3  | 0x3E25E| 0x45E66| 0x7C08 | |
| 3+  | 4  | 0x45FE6| 0x46166| 0x180  | 384-B chunks ×3 (contiguous, +0x180 stride) |
| …   | 4  | 0x46C60| 0x46CDA| 0x7A   | 122-B chunks ×4 (see below) |
| …   | 4  | 0x46F3C| 0x46FB6| 0x7A   | last chunk ends exactly at EOF |

**The three 0x7C08 (31,752 B) blobs are 63×63 grids of 8-byte (4×u16LE)
cells** (63·63·8 = 31,752 ✓). `0xF0` (240) is the global empty sentinel:
- **Grid A @0x7E26 (id 0):** mostly `(0xF0,0,0xF0,0)`; scattered populated
cells e.g. row 1: `(0xF0,0,0xF0,0xFF80)`, `(0xF0,0,0x0061,0xFF40)`;
row 2: `(0x1441,0x3F81,0xF7C1,0x00F0)`, `(0x00C0,…)`, `(0x20C0,0,0x0061,0)…`.
- **Grid B @0x1F23E (id 1):** cells e.g. row 1: `(0x1081,0xB3C5,0x1081,0x0005)`
with the 2nd u16 stepping +0x40 (64) per cell → indices into a table of
64-byte records; flags in 4th u16 (0x0005, 0x37C5…).
- **Grid C @0x3E25E (id 3):** cells e.g. `(0xF0,0,0x24A1,0)`,
`(0x2491,0,0x2489,0)`, descending ~0x24xx values (pointers?)

So the level = **three parallel 63×63 attribute grids** + smaller chunks.
Tail chunks (id 4): 384-B chunks start e.g. `00 F0 F0 FF 14 14 40 EA …`
(0xF0 sentinel + data); 122-B chunks are 61×u16 index lists, e.g.
`00 0F 17 09 06 07 08 30 31 3D 3C 3E 3B 39 38 35 C0 C1 C2 C3 91 84 99 9F…`
(object/entity instance ids or tile-type lists). Unlisted regions between
chunks hold RLE-ish byte streams (descending bytes punctuated by 0xF0,
e.g. @0x45D66 `F9 F4 FB F0 EF EE ED EC E0 DF E9 F5 …`).

TBD: 63×63 grid geometry (world/sector map? 64−1?), per-grid field
semantics, record 1's trailing words, the 542 header field. Needs the
EXE level-loader (see `uwexe.md`; boot trace) to pin down.

## `STRINGS.PAK` — global string table (227,230 B) — PARTIALLY RESOLVED

Exact leading bytes: `b5 00 09 8f  ff ff 0a a3  ff ff 0d a3  ff ff 20 b1 …`
Read as u32LE: `0x8F0900B5  0xFFFF0AA3  0xFFFF0DA3  0xFFFF20B1 …`.
- `u32[0] = 0x8F09_00B5`: lo16 = 0x00B5 = **181** (entry count); hi16 = 0x8F09
  (special first-entry tag, not 0xFFFF).
- `u32[1..] = 0xFFFF_xxxx`: (u16 val, 0xFFFF) pairs — a 181-entry index/hash
  table (3-tier: hash → block table → per-block u16 arrays + encoded strings).
- V low byte = sequential string index, high byte = category/hash.
- String pool start + string-byte encoding still TBD. 3,075 ASCII runs ≥ 4 chars.
- **Reader**: fetched by the archive resource subsystem (file `0x3c000..0x3e600`,
  see `uwexe.md` §9); top-level lookup routine not yet identified.
  The EXE opens it via pool-A u16 0x0BBF (`DATA\strings.pak` @ file 0x5FBBF).
  At runtime the pool is reached as `ES:[0x019A:0x0BBF]` — a string-compare
  loop at file 0x21B6D (`36 3A 01 9A BF 0B`) implies **pool A loads at
  segment 0x19A0 (linear 0x19A00) at runtime** (first concrete evidence for
  the runtime pool base; still to confirm by boot trace).

## `XMI` — music (SOUND/AW01..15, UW01..15) — IDENTIFIED

Big-endian IFF-like: `FORM` (u32 BE size) `XDIR`
  → `INFO` chunk (size 2, payload `01 00`)
  → `CAT ` chunk → body starts `XMID` → nested `FORM` (u32 BE) `XMID`
     → `XMTI` track: u16 tempo, u8 channel count, song pointers,
       16-byte instrument names ("VIOLIN","VIOLA","CELLO","BASS"),
       note events.
Custom format (not standard CMI/XM). TBD: event encoding.

## `.VOC` — standard Creative Voice (42 files in SOUND/)

Magic `43 72 65 61 74 69 76 65 20 56 6f 69 63 65 20 46 69 6c 65` + `1a`
(0x1A terminator @19) + standard fixed header fields: `[u16LE
header_size=0x1A @20] [u16LE version=0x010A @22] [u16LE checksum=0x1129
@24]`. First real block starts @26: type 0x01 (Sound Data) + 3-byte LE
block length. Decode with ffmpeg, no custom decoder.

## `N0x` page files (CRIT/*PAGE.N00/.N01, CUTS/CS*.N00..N07)

- **`CRxxPAGE.N00`** (creature/critic page index, 78–17,461 B):
  ```
  [u16LE 0x2000 (8192)] [u8 0x00] [u8 id stream from offset 3: 01 02 03 ff 04 ff 05 ff …]
  ```
  u8 page-id stream with 0xFF filler/terminator bytes (page slots).
- **`CRxxPAGE.N01`** (823–32,002 B):
  `[u16LE 0x8020 (32800)] [u8 0x00] [u8 id stream from offset 3: 01 02 03 04 05 06 07 ff ff …]`
  Same shape, different header (0x8020 vs 0x2000 — likely a flag/size).
- **`CSxxx.N00`** (cutscene trigger/scene tables, 10–1,682 B):
  u16-LE value streams, e.g. CS001.N00 (646 B):
  `01 00 0a 00 02 00 01 00 00 00 f0 00 00 00 01 00 04 00 1e 00 00 00 1e 00
  09 00 02 00 1e 00 05 00 …` — repeating 0x1E (30) and 0xF0 (240); likely
  (scene, type, param) tuples. Semantics TBD (cross-ref XMI/song index 30?).
- **`CSxxx.N01..N07`** (also `.N10..N17`, `.N20..N25`) = `LPF ` resource
  container. 47 files in CUTS/ carry the `LPF ` magic: 32 with a literal
  `.N01..N07` suffix + 9 `.N10..N17` + 6 `.N20..N25` (verified — same
  format, not just the narrower `N01..N07` range); up to 347,073 B =
  CS012.N01, 324,770 B = CS000.N07:
  ```
  [ascii "LPF "] [u16LE 0x0100] [u16LE group count (1..6)] [u32LE resource count]
  [resource records: [u8 0x00][u16LE 0x0001][u8 name_len=4][4CC, e.g. "ANIM"]
   [u16LE 0x0140 (=320)][u32LE 0x00C8 (=200)][payload …]]
  ```
  First resource in every examined LPF file is an `ANIM` record carrying
  320×200 (VGA mode-13h) dimensions → cutscene animation frames. Only
  4CC observed so far: ANIM.

  **Full 0x80-byte header (verified across CS000.N01/.N07, CS001.N01/.N07,
  CS012.N01):**
  ```
  0x00 "LPF "  0x04 u16 0x0100  0x06 u16 group_count (1..6)  0x08 u32 res_count
  0x0C u8 0    0x0D u16 0x0001  0x0F u8 5   0x10 "ANIM"  0x14 u16 0x0140 (320)
  0x16 u32 0x000000C8 (200)  0x1A u16 0x0101  0x1C u16 0x0100
  0x22..0x3F zeros  0x40 u32 N (≤ res_count; CS001.N01=31, CS000.N01=10,
  CS001.N07=6, CS012.N01=5)  0x44 u32 M (6 for CS001.N01, else 0)  0x48..0x7F zeros
  ```
  N = probably frame/patch count of the group; M unknown. Only ONE "ANIM"
  4CC per file even when group_count > 1 → group descriptors either repeat
  later in the stream or live elsewhere (TBD).

  **Payload @0x80 (CS001.N01, 55,366 B) — partial:** first 4 × 16-B records
  e.g. `(u16 0x0038, u16 0x0006, u16 0x0400, u16 0x787B, …)` (rects
  56×6, 56×6, 28×11, 8×10 with (x0,x1) pairs), then 16×(v,v;0,v) u8-pair
tables (v = 0x1B,0x2B,…,0xFB), 16×(u8,u8) tables, then ~27,491 (u8,u8)
  pairs of DDA-like coordinate/step data (x in 0..255, descending steps).
  Looks like per-scanline horizon/DDA tables for the 3D cutscene renderer.
  Semantics TBD (needs the EXE cutscene renderer).

  **EXE cross-ref:** path templates live in string-pool B: `CUTS\csXXX.nXX`
  (0x603EE, err-msg), `CUTS\csXXX.n00` (0x60418), `crit\cr00page.n00`
  (0x606B8), `crit\assoc.anm` (0x606CA) → u16 pool-B offsets 0x03EE/0x0418/
  0x06B8/0x06CA (pool B base 0x60000). No literal "LPF" magic in the EXE —
  the LPF files flow through the generic resource/archive subsystem.

## `ASSOC.ANM` — creature↔animation table (384 B, CRIT/)

First 168 B = 21 × 8-byte NUL-padded creature names:
`gngob32 skela lizman bat wiza spider gazer troll femwiz slug fire ghoul
demon ghost graygob reaper rat femfite imp golem hedless`. Second name
block (88 B, 11 names): `wizb rotgrub wisp batskull Lurk fight32 dwarf32
shadow tybal eye litening`. Remainder (128 B) = u16LE index tables
mapping names → animation/sprite sets. (32 creature entries total.)

## `.SYS` fonts (DATA/) — header verified, glyph packing TBD

```
[u16 1] [u16 A] [u16 B] [u16 C] [u16 D] [u16 E] [zeros…]
```
| file        | sz   | A  | B | C  | D | E |
|-------------|------|----|---|----|---|---|
| FONT4X5P    |  497 |  4 | 2 |  4 | 1 | 5 |
| FONT5X6I    | 1028 |  7 | 3 |  7 | 1 | 6 |
| FONT5X6P    |  901 |  6 | 4 |  6 | 1 | 5 |
| FONTBUTN    | 1234 | 12 | 4 |  6 | 2 | 9 |
| FONTBIG     | 3949 | 30 | 5 | 15 | 2 |11 |
| FONTCHAR    | 2679 | 20 | 4 | 10 | 2 | 9 |

Interpretation (consistent across all 6): `[u16 1][u16 maxw][u16 minw][u16 maxw][u16 planes][u16 height]`,
i.e. proportional fonts carry min/max width (5X6I italic: 3..7, 5X6P: 4..6).
Glyph data starts at 0xB0 (4X5P) / 0xF2 (5X6P) — header is zero-padded to a
per-font size. 4X5P: 107 glyphs × 3 B (20-bit 4×5 raster) = 321 B = file tail ✓.
4X5P glyph bytes e.g. `02 40 40 00 40 04 a0 a0 00 …` (MSB-first row packing).

## `.BYT` — 320×200 screen buffers (9 × 64,000 B, DATA/)

BLNKMAP, CHARGEN, CONV, MAIN, OPSCR, PRES1, PRES2, WIN1, WIN2 — raw
8-bit 320×200 frames (64,000 = 320·200). PRES1 (~86.7% zero) and PRES2
(~85.1% zero) are mostly zero; BLNKMAP dominated by values 58–60. These
are pre-rendered UI/background screens (or DDA-shaded map screens).

## `.DAT` quick headers (DATA/)

| file         | sz    | first 16 B                                        | notes |
|--------------|-------|---------------------------------------------------|-------|
| WEAPONS.DAT  |   448 | `0b 00 00 00 00 19 64 9f 00 81 95 95 00 95 6d 5b` | 11 weapon entries? |
| TERRAIN.DAT  |  1024 | `00 00 00 00 00 00 07 00 00 00 0a 00 0a 00 …`      | sparse u32 table |
| MONO.DAT     |  4096 | `00 01 02 03 …`                                   | sequential (identity table) |
| LIGHT.DAT    |  4096 | `00 01 02 03 …`                                   | same shape as MONO |
| OBJECTS.DAT  |  3554 | `01 0f 06 04 02 5a 19 a0 …`                       | mixed |
| PLAYER.DAT   |   301 | `47 52 4f 4e 4b 45 59 00` = "GROKEY" + zeros      | **save file** (player name field) |
| XFER.DAT     |  1536 | `f1 f1 66 f1 f1 a6 a8 ba …`                       | RLE-ish |
| CMB.DAT      |    60 | `95 00 16 81 15 01 e1 80 …`                      | opcode-ish |
| SKILLS.DAT   |   187 | `14 10 0c 0c …` (values 12–20)                    | per-skill stats |
| PALS.DAT     |  6144 | `00 00 01 00 00 00 3f 25 3f …`                    | 2048×3 palette (6144 B) |
| ALLPALS.DAT  |   513 | `00 01 63 64 65 66 …`                             | palette index lists |
| GRAVE.DAT    |   512 | all zero                                          | grave markers (empty = none dead?) |
| SHADES.DAT   |    96 | `38 00 05 00 fd ff 03 00 …`                      | (u16,u16,u16) triples |
| BABGLOBS.DAT |   388 | `01 00 22 00 02 00 56 00 …` = (1,0x22)(2,0x56)…  | (u16 id, u16 ptr) pairs |
| COMOBJ.DAT   |  —    | (in ZDATA? or DATA; see UW.EXE string "comobj.dat")| |

## `WEAPONS.CM` (32 B)

Unexamined; likely combat matrix stub.
