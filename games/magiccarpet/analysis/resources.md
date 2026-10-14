# Resource audit — main menu screen

Status: the `MAINMENU.DAT` / `MAINMENU.PAL` pair is **RESOLVED** as a raw
320×200 indexed VGA screen plus a 256-entry palette. The `FONT0`–`FONT2`
container, table layout and normal-mode glyph command stream are **RESOLVED**;
the screen-sprite pairs below, the non-screen sprite families, menu-region
mask, compact FLC animation family, and several indexed world images are
**RESOLVED**; other resource formats remain **TBD**.

## Measured files

| file | bytes | SHA-256 | invariant |
|---|---:|---|---|
| `DATA/SCREENS/MAINMENU.DAT` | 64,000 | `E89A03630B7ED294BBBD2DD8B5154614121D323733B0AF0BAB99695078379A69` | exactly `320 × 200` one-byte pixel indices; 221 indices are used |
| `DATA/SCREENS/MAINMENU.PAL` | 768 | `222A636FC382F8E9B8BB5D8DBE3C4D392B9BC211C4985A0C6BDAE81B88493915` | exactly 256 sequential RGB triplets; every component is in VGA's `0..63` range |

The palette is therefore interpreted as 6-bit VGA DAC values in ordinary
`R,G,B` triplet order. The renderer scales each component to 8-bit PNG space
with `(value << 2) | (value >> 4)`, preserving both endpoints (`0 → 0`,
`63 → 255`).

The same size invariant holds across the screen family: `GCONFIG.DAT`,
`LANGUAGE.DAT`, `PMULTI.DAT` and `PPERF.DAT` are also 64,000 bytes, and each
has a matching 768-byte `.PAL` file. This cross-check is independent of the
single rendered preview.

## Reproduction

```text
python tools/re/render_screen.py \
  game/MagCarp/CARPET/DATA/SCREENS/MAINMENU.DAT \
  game/MagCarp/CARPET/DATA/SCREENS/MAINMENU.PAL \
  re/unpacked/MAINMENU.png
```

The derived preview shows a coherent 320×200 title-room background (globe,
framed portrait and shelving), which is consistent with the filename and
supports the indexed-screen interpretation. The renderer writes only under
`re/unpacked/`; the archive extraction remains pristine.

## Font resources

All six files in the `DATA` root named `FONT0.TAB`, `FONT0.DAT` through
`FONT2.TAB`, `FONT2.DAT` begin with `RNC\x01`. Their 18-byte big-endian RNC1
headers declare exact packed lengths, one chunk, and valid packed CRCs. The
decoder also reproduces the declared unpacked CRCs:

| pair | packed TAB → raw | packed DAT → raw | raw glyphs |
|---|---:|---:|---:|
| `FONT0` | 671 → 1,536 | 1,380 → 8,177 | 256 |
| `FONT1` | 536 → 1,638 | 416 → 3,952 | 273 |
| `FONT2` | 369 → 774 | 808 → 4,587 | 129 |

The decompressed `.TAB` files are exactly six bytes per entry: a little-endian
32-bit absolute offset into the corresponding `.DAT`, followed by a
little-endian 16-bit dimension word. The low byte is the observed glyph width
and the high byte the observed height. The first `.DAT` word repeats the glyph
count; the first table offset is zero for that header, and the first actual
glyph payload starts at offset `0x2`. Offsets are monotonic, and each actual
record ends with `0x7F` in all three fonts. The remaining record bytes are a
compact row-RLE glyph stream. For each row, a positive token copies that many
literal pixel bytes, a high-bit token skips `0x100 - token` blank columns and
then copies a literal run, and `0x00` ends the row. After the declared number
of rows, `0x7F` terminates the record. The decoded literal values are
consistent within each font family: `FONT0` uses `0x40`, `FONT1` and `FONT2`
use `0x01`, while the screen `SFONT` variants use their own palette indices.

Static evidence is the common protected-mode draw routine at executable file
offset `0x75365`: its callers load the table entry's 32-bit data offset and
dimension bytes, and its normal no-mode branch implements the token behavior
above. This ties the decoded resource grammar to the game's renderer rather
than only to repeated byte patterns.

    python tools/re/decompress_rnc.py game/MagCarp/CARPET/DATA/FONT0.TAB game/MagCarp/CARPET/DATA/FONT0.DAT game/MagCarp/CARPET/DATA/FONT1.TAB game/MagCarp/CARPET/DATA/FONT1.DAT game/MagCarp/CARPET/DATA/FONT2.TAB game/MagCarp/CARPET/DATA/FONT2.DAT --out-dir re/unpacked/fonts
    python tools/re/audit_fonts.py re/unpacked/fonts/FONT0.TAB.raw re/unpacked/fonts/FONT0.DAT.raw

The RNC decoder is limited to the RNC1 variant present in these files and
verifies both CRCs before emitting derived output.

The same six-byte table and DAT record layout is present without RNC
compression in the screen-local `SFONT0`–`SFONT2` pairs:

| pair | TAB bytes | DAT bytes | glyphs | observed dimensions |
|---|---:|---:|---:|---|
| `SFONT0` | 1,446 | 5,766 | 241 | width 3–10, height 8 |
| `SFONT1` | 1,446 | 10,819 | 241 | width 1–20, height 14 |
| `SFONT2` | 1,446 | 16,210 | 241 | width 4–23, height 20 |

This cross-family match makes the six-byte table interpretation and normal
row-RLE decoder **RESOLVED** for the available font resources. The executable
contains the corresponding renderer: its table-entry wrapper reads the
32-bit offset and two dimension bytes, then the common draw routine consumes
the row tokens and writes the literal pixels. Other mode-flag branches in
that renderer and the untabled animation formats remain **TBD**.

## Screen sprites

The same table/RLE structure validates directly, without RNC compression, for
the screen sprite pairs:

| pair | table entries (incl. header) | DAT bytes | observed width | observed height | decoded nonzero pixels |
|---|---:|---:|---:|---:|---:|
| `MMSPR` | 8 | 3,266 | 1–41 | 1–33 | 2,960 |
| `GCSPR` | 12 | 26,096 | 30–87 | 33–73 | 24,170 |
| `CONFSPR` | 15 | 24,453 | 8–68 | 12–75 | 23,433 |
| `PMULTSPR` | 26 | 29,491 | 8–28 | 9–47 | 27,299 |
| `LANGSPR` | 5 | 1,371 | 66–73 | 33–34 | 831 |
| `SPTRS` | 33 | 8,408 | 3–24 | 5–28 | 6,524 |

All 93 non-header records end at the table-defined boundary with `0x7F`;
the row decoder consumes every record without overflow. This resolves the
screen sprite container format and its normal renderer path.

## Untabled screen resources

`MMMASK.DAT` is **RESOLVED** as a raw 320×200 menu-region mask: it is exactly
64,000 bytes, uses 12 values (`0..11`), and has no matching palette. The
indices form contiguous UI regions rather than a normal color image, so the
file is used as a hit-test/selection mask. A diagnostic rendering is available
at `re/unpacked/MMMASK.png`.

`GLOBE.DAT`, `TIMER.DAT`, and `SCROLL.DAT` are **RESOLVED** as compact FLC
animations. Their 12-byte headers contain the FLC magic `0xAF12`, dimensions
`320×200`, and a declared delta-frame count. Each file then stores one initial
full frame followed by that many delta records. The initial record contains a
256-color palette chunk (`type 0x0004`) and a BRUN full-frame chunk
(`type 0x000F`); later records use SS2 delta chunks (`type 0x0007`), with
explicit empty records in `SCROLL`.

| file | bytes | declared deltas | physical records | first stored size → chunk size |
|---|---:|---:|---:|---:|
| `TIMER.DAT` | 4,428 | 3 | 4 | 4,568 → 4,130 |
| `GLOBE.DAT` | 93,520 | 30 | 31 | 8,400 → 7,716 |
| `SCROLL.DAT` | 114,994 | 26 | 27 | 2,408 → 2,200 |

The first record’s stored size is inconsistent with its chunk boundaries; all
subsequent records are internally consistent. `tools/re/normalize_flic.py`
rebuilds a standard 128-byte FLC header, patches that first size from the
measured chunk end, and verifies that all records consume the source exactly.

The same six-byte table and row-RLE record grammar also validates these
non-screen sprite families after RNC decompression where applicable:

| family | table entries | DAT bytes | observed width | observed height | decoded nonzero pixels |
|---|---:|---:|---:|---:|---:|
| `MSPR0-0`, `MSPR0-1`, `MSPR1-0` | 87 each | 21,709–21,848 | 4–91 | 5–36 | 17,217–17,383 |
| `HSPR0-0`, `HSPR0-1`, `HSPR1-0` | 87 each | 72,220–72,490 | 5–128 | 5–44 | 63,835–64,333 |
| `BUILD0-0` | 69 | 18,761 | 1–48 | 1–48 | 12,995 |
| `BUILD1-0` | 78 | 20,474 | 1–48 | 1–48 | 14,473 |
| `POINTERS` | 9 | 1,927 | 11–22 | 11–17 | 1,527 |

All 669 non-header records in these nine pairs terminate at their table-defined
boundaries with `0x7F`. This extends the resolved sprite grammar beyond the
screen-only resources and leaves the larger world/map and audio data as the
next separate families to classify.

## World and map resources

`TMAPS.TAB`, `TMAPS0-0.TAB`, and `TMAPS1-0.TAB` are 5,300-byte tables of 530
little-endian 10-byte entries: `<u32 decoded_size><u32 absolute_offset><u16
tag>`. The final entry is a zero-length EOF sentinel. The corresponding data
files begin with an eight-byte `BULLFROG` prefix and then contain 528 indexed
RNC1 streams plus one 36-byte raw record. `tools/re/audit_tmaps.py` validates
the offsets, RNC CRCs, decoded sizes, and record headers.

Every decoded map record begins with `<u8 type><u8 subtype><u16 width><u16
height>`. In `TMAPS`, 316 type-2 records are exact raw 8-bit `width × height`
grids. The 213 type-3 records also begin with a `width × height` indexed grid,
but carry a variable-length tail after it; the tail sizes vary by subtype, and
the recurring `FA F1` byte pair is not yet tied to a field boundary, so the
tail grammar remains **TBD**. `TMAPS1-0` has
the same 316/213 split, with two type-2 records whose stored dimensions do not
describe the full payload (records 153 and 156), so those are retained as
explicit exceptions rather than silently reinterpreted.

The decompressed `BLK0-0`, `BLK1-0`, `BLK0-1`, and `BLK1-1` files have no header
and divide exactly into 32×32 indexed tiles: 44 tiles in each `*-0` file and
152 tiles in each `*-1` file. Contact sheets are available under
`re/unpacked/world/`, generated by `tools/re/render_tiles.py`.

Several additional indexed images are now **RESOLVED** by exact dimensions and
coherent palette-backed renders:

| resource | decoded pixels | palette | interpretation |
|---|---:|---|---|
| `BOOKBKG.DAT` | 64,000 | `BOOK.PAL` | 320×200 indexed book background |
| `SMATITLE.DAT` | 64,000 | `SMATITLE.PAL` | 320×200 indexed title disc image |
| `SKY.DAT`, `SKY1-0.DAT` | 65,536 each | `SMALTIT.PAL` | 256×256 indexed sky/map images |

The local `LEVELS.DAT` resource is also **RESOLVED** as one decompressed level
record: 38,812 bytes consisting of a 48-byte generation header, a zero-filled
1,042-byte reserved block, 2,095 18-byte entity slots, and a 12-byte footer.
`tools/re/audit_level.py` reports 545 active entities after excluding empty and
padding slots, with class counts `{2: 432, 3: 1, 5: 65, 10: 40, 11: 4,
12: 3}`. The header values are `(135530, 1921, 41339, 2834, 0, 1, 0, 200,
50, 30, 16, 18)`, and the footer is `(27, 1, 0, 0, 0, 0)`. This matches the
published [Magic Carpet level format reference](https://github.com/michaelhoward/MagicCarpetFileFormat/blob/master/magic%20carpet%20file%20format.txt)
at the byte-layout level; the exact meaning of the first header word and
footer fields remains open.

`TABLES.DAT` is **PARTIALLY RESOLVED** as an 83,456-byte bank of 326 rows ×
256 bytes after RNC decompression. `DTABLES.DAT` is an uncompressed bank with
the same dimensions. `TABLES` has uniform rows `0`, `63`, `322`, and `325`;
`DTABLES` has uniform rows `0`, `63`, `322`, `324`, and `325`. Both banks peak
near identity at row 32 (`244/256` and `241/256` entries respectively), with
the first 64 rows forming a distinct fade/remap region and rows 64–319 forming
the larger lighting/remap body. They differ in 19,470 byte positions, so they
are variants rather than duplicate copies. `tools/re/audit_tables.py` checks
the shape, row classes, identity trend, hashes, and pairwise differences.

This identification is based on the local byte structure and the executable’s
own world-resource loading path. The exact table-row semantics in Magic Carpet
remain open until tied to a live renderer call or decoded world effect.

## Audio and music directories

All 48 `SNDS*`/`MUSIC*` `.TAB` files decompress as RNC1 and share a 32-byte
directory format: a 26-byte filename field, a 32-bit member-byte count, and a
16-bit parameter. Across the family there are 319 entries, all with parameter
`0x005A`; 298 entries name `.RAW` members, while the music tables name seven
each of `.HMP`, `.ROL`, and `.GEN` members. The 32-bit total at offset `0x1A`
equals the sum of the directory member counts. `tools/re/audit_audio_tab.py`
validates this structure.

The RNC decoder was re-run against all 136 RNC1 files in the primary `DATA`
directory with no failures.

The `MUSIC0` payloads decode successfully as RNC1 and their member counts
exactly consume the decoded data. The `SNDS1` and `SNDS13` examples do as well;
`SNDS0-0` has two duplicate directory aliases (`FIRE.RAW` and `NULL.RAW`), so
its member-count sum exceeds the unique decoded data by those aliases. The
`MUSIC1` directory tables and all three `.DAT` payloads now decode
successfully. `MUSIC1-0.DAT` exercises a valid empty distance/length Huffman
table for a literal-only chunk; the local RNC decoder accepts that case and
verifies the declared CRC and output size. The actual sample encoding and the
HMP/ROL/GEN payload grammars therefore remain **TBD**.
