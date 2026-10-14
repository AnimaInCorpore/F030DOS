# TIE data formats — status board

Consolidated status of every game-data format. Convention (shared with
`C:\Arbeit\F030Underworld\analysis\data-formats.md`): "LE" = little-endian; verified
bytes are quoted, never guessed; each item carries a status marker
(`RESOLVED` / `PARTIALLY RESOLVED` / `IDENTIFIED` / `TBD`), its verification scope
(which files, how many), and open questions. All paths under
`game\SWTieCD\TIECD\` (pristine reference). Decoders land here as they mature
(todo P2.x); deep per-format docs live next to this file.

## RESOLVED

### `STRINGS.DAT` (14,611 B) — global string table
695× u32LE offsets @ 0x0000 (first 0x0AE0, [695] = 0 terminator) + NUL-terminated pool
0xAE0–0x3953. Invariant: offsets strictly ascending, all ≥ 0xAE0. Verified on the single
file (it is the only one). Detail + dump + decoder: `STRINGS.DAT.md`, `STRINGS.DAT.txt`,
`decode_strings.py`.

### `.PAL` — raw RGB triplets
99 B = 33 colors. `RANGE.PAL` = brightness ramp (e0→4b→63→7b→97→af→cb→e3→ff repeating).
Verified on both observed files. No decoder needed.

### `.LFD` / `.LFB` container + 8 of its 15 record types — **P2.1–P2.1c, 2026-08-22**
Master doc: **`analysis/LFD.md`**. Tools `work/lfd.py` / `lfd_delt.py` /
`lfd_extract.py`; regression `python3 work/lfd_audit.py game/SWTieCD/TIECD`.
```
struct { char type[4]; char name[8]; u32le length; }   /* 16 B */ + length payload bytes
```
Verified over the **whole tree** — 175 files, 2,184 records, 0 failures. The 70
cockpit files are **always exactly `PANL, MASK, PLTT` sharing one name**, so the loader
indexes the trio positionally. The cockpit loader still compares the third record
with `PLTT` before shifting its loaded palette bytes right by two; there is no
general tag lookup for the `PANL`/`MASK` pair.
The generic record lookup is `FUN_00097020` (XRES.C). Records
chain from offset 0 and the last ends exactly at EOF; 105 files open with an `RMAP`
record whose payload is a copy of every following record header (entry count and
every `(type,name,length)` match); the 70 files in `CP320/`+`CP640/` have no `RMAP`.
Resolved payloads (all-records scope): `DELT` 370/370 (sparse RLE bitmap),
`ANIM` 355/355 (5,467 DELT frames), `PLTT` 296/296 (index range + RGB),
`TEXT` 27/27 (2,303 strings),
`VOIC` 239/239 + `BLAS` 103/103 (**standard Creative VOC v1.10**),
`GMID` 179/179 (**`MIDI` + MDpg/MThd/MTrk**, same as the 4 standalone `.GMD`),
`FILM` 149/149 (**the scene sequencer** — 2,939 blocks / 26,266 chunks; its
block list is the resource set of one scene, which is what pairs a `PLTT` with a
`DELT`: 86 % of the ambiguous records now resolve from it). Chunks are
`{u16 time; u16 lenBytes; u16 opcode; params}` — ~~opcode-first~~ **corrected
2026-08-22**, the opcode is the *third* word; **20 opcodes**, each with a fixed
parameter count, partitioning by block type (15 = PLTT only, 18 = VIEW only,
19–28 = VOIC only). What each *does* is still TBD.
Answered: `.LFB` is the same container (`EMPEROR.LFB` byte-identical to the `.LFD`;
`SCENE10.LFB` = the `.LFD` minus one `FILM` record) — the 15/16-bit-depth hypothesis
is **refuted**; `RES320` vs `RES640` differ only in 10 `XACT` effect sprites; all
`SHIP` records byte-identical (59 in `SPECIES.LFD`, all 78 across `SPECIES*.LFD` —
`LFD.md` §8).
`PANL` **structure only** 70/70 — ~~"`0xFD cnt val` run / `0xFE` end of row /
else literal pixel"~~ **withdrawn 2026-08-22**: the real opcode set (from the blitter
`FUN_0004977C`) is `0xFB` bias (3 B) / `0xFC` x-advance (2 B) / `0xFD` run (3 B) /
`0xFE` end of row / `0xFF` end of panel / literal (byte split into width+colour). The
old model desynchronised on 29,070 `0xFC` opcodes and produced plausible-but-wrong
images. Rows are now exactly 189 or 200 (CP320) / 456 or 480 (CP640). **Pixels are not
statically decodable** (runtime-built tables) — `lfd_extract.py` no longer renders PANL.
`SHIP` **header only** 234/234 (`LFD.md` §6c: `u16 length = len-2`, `0x0100`, u16
spans that must be read **unsigned** — 7 capital ships exceed 32,767 — and an i16
bounding box; the geometry past 0x24 is **not** decoded and wants the renderer in
`Z_TIE__.EXE`). Also found: `RESOURCE/SPECIES*.LFD` is a **third variant**, not a copy
— 26 of its 78 `SHIP` records differ from `RES320`/`RES640` (which agree on all 78).
`MASK` consumer identified (`FUN_00044008`), encoding still TBD; `SHIP` geometry, `XACT` 56, `BMAP` 26, `FONT` 5,
`MTRX` 5, and the `FILM` chunk opcodes. See `LFD.md` §9.
~~**Withdrawn 2026-08-22** (old reading, quoted): `[u32 "RMAP"] [ascii "resource"]
[u8 version (30|50|70)] [N × (type(4) + name(12) + offset(4))]`~~ — the name field
is **8** bytes, the trailing u32 is a **length** not an offset, there is no version
byte (that was the low byte of the first entry's length), and `RMAP` is an ordinary
record, not a file header.

## IDENTIFIED (magic / top-level layout verified, record semantics TBD)

### `.TIE` missions — `MISSION/` (76× `B#M#XX.TIE` + `H*` + `TRAIN.TIE`)
Header `ff ff 16 00 0d 00 03 00 00 00 02 00 00 01 …` + **plain English briefing text
@ ~0x15** ("The first wave of freigh…"). Scope: header verified on several files.
Open: field-by-field header semantics; record structure after the text; `H*`/`TRAIN`
variants.

### `.WRK` cutscene audio — `ASTREAM/` (A.WRK, SCENE*.WRK, OS1-V3.WRK …)
5-byte header `00 00 00 00 00`; then nibble data dominated by `2a 00 2a 00` /
`15 15 15` (IMA-ADPCM-like silence patterns). Scope: header verified on A.WRK + others.
Open: codec params (IMA-ADPCM variant? channels? sample rate?), header fields, IMUSE
integration. Note: duplicate files differ only `-` vs `_` (`OS1-V3.WRK` / `OS1_V3.WRK`,
byte-identical sizes) — the game probably matches one naming style.

### ~~`.GMD` — MIDI container~~ → **RESOLVED 2026-08-22 with `GMID`**, see `LFD.md` §6
`MIDI` magic + `u32be` payload length, then `MDpg` / `MThd` / `MTrk` chunks — the chunk
walk ends exactly on the payload end in all 4 standalone `.GMD` files and all 179 `GMID`
records. (The old `QuMDpg` (14 B) / `hd` (6 B) reading mis-split the chunk headers.)
Still open: `MDpg` contents (iMUSE), MT-32 track structure, instrument map.

### `.FNT` fonts — `MICRO/SMALL/TINY` (+`64` variants)
8×8 bitmap font data; `MICRO.FNT`: `04 05` header then glyph rows (e.g. `f0 f0 f0 f0`).
Open: glyph packing (rows-per-glyph, char range, the `64` variant difference).

## OBSERVED (header bytes quoted, format unassigned — todo P2.2 / P2.6)

### `.PNL` / `.INT` — `CP320/`, `CP640/` (cockpit UI per resolution)
- `.PNL` (9 KB–86 KB): binary object tree; bytes look like tagged records
  (`fd 43 0a fe 4c 38 …`, embedded tags `PL8`, `L8`). It uses the same `0xFD`/`0xFE`
  bytes as the LFD `PANL` record (`LFD.md` §5) but is **not** that format: run through
  the `PANL` decoder these files yield 1,011–3,205 rows, far past any screen height.
- `.INT` (all exactly 1,589 B): `01` + named entries referencing LFD images
  (`GUNBT12`, `FWD`, `GUNBT10`, …) — interface object lists.

### `.ICO` / `.ANI` / `.FLC` — custom packed icons/animation (NOT standard FLIC)
`ICONS640.ICO` (25 KB); `ICONSBLU/GRN/PUR/RED.ANI` (15.6 KB each); `.FLC` (22.8 KB;
`ICONSBLU.FLC` starts `22 59 00 00 12 af b0 00 …`). Plan: try ffmpeg FLI decode, then
hand-decode (todo P2.6).

### `.TFR` high scores — `NEWACE7/10`, `TOPACE7/10` (3,856 B each)
Mostly zeroed; head `00 00 00 01`. Cross-ref: 32-bit string pool has `.TFR` /
`__temp__.tfr` (img+0x0BACE4) and embedded `newtarm`/`tietext0` filenames
(`uncovered_v2.txt`) — read the TFR handler in the image to pin the layout.

### `.LBM` — `HRESICON.LBM`
Presumed standard Amiga LBM; **unverified**. Check chunk layout (`BMHD`) before assuming.

## Trivial / housekeeping
- `CREDITS.TXT` — plain text. `TEMP.FLC` — stray temp file (game writes it at runtime;
  don't delete in reassembly, it's part of the reference tree). `SCENE11.BAK`,
  `TIESPCH2.BAK` — backups.
- `MT32/`, `SB16/`, `SC55/IMUSE.INI` — IMUSE device-selection variants copied by
  `run.bat` (`mididevice=default|mt32|fluidsynth`).

## Method (carried over from UW1's data-formats.md)
- Quote exact header bytes for every claim; mark each item's verification scope
  (which files, how many).
- When a format is resolved, record its **invariant** (e.g. "first record offset ==
  table_end + 4, verified on all N files") and the cross-check that proves it.
- Corrections stay in the doc, dated, with the old (wrong) reading quoted.
- Cross-reference the EXE: path templates + magic strings in the 32-bit image
  (`analysis/32bit/strings.txt`, `functable_v2.txt`) identify the reader function —
  decompiling it is the fastest route to record semantics (UW1 did this for LPF/ANIM).
