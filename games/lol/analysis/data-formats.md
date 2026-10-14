# Data formats — initial inventory

Every entry records its evidence scope explicitly; unresolved families remain
**TBD** until a size/offset invariant and a rendered or runtime-checked sample
is recorded.

| family | examples | initial role | status |
|---|---|---|---|
| PAK containers | `DATA/**/*.PAK` | sequential file directory | **RESOLVED** |
| CPS images | `DATA/**/*.PAK:*.CPS` | 320×200 indexed image with VGA palette and Frame4 payload | **RESOLVED** |
| Westwood v3 fonts | `DATA/ENG/STARTUP.PAK:FONT9P.FNT`, `INTRO.FNT`, `NEW6P.FNT`, `NEW8P.FNT` | indexed 4bpp glyphs with absolute offset, width and height/Y-offset tables | **RESOLVED** |
| DIP text tables | `STARTUP.PAK:LOLINTRO.DIP`, `HISTORY.DIP`; `FINALE2.PAK:LOLFINAL.DIP` | 16-bit offset table followed by NUL-terminated CP437 strings | **RESOLVED** |
| level text tables | `L01.PAK:LEVEL01.ENG`, `.FRE`, `.GER` | same 16-bit offset/NUL-terminated CP437 string table | **RESOLVED** |
| EMC2 level resources | `L01.PAK:LEVEL1.INI`, `LEVEL1.INF` | `FORM`/`EMC2` container with `ORDR`, optional `TEXT` and `DATA` chunks | **PARTIALLY RESOLVED** |
| CMZ/WLL level geometry | `L01.PAK` … `L29.PAK` | LCW/Frame4 geometry stream plus 12-byte wall mapping records | **RESOLVED** |
| VCN/VMP area tiles | `KEEP.PAK`, `FOREST1.PAK` … `YVEL.PAK` | LCW/Frame4 4bpp 8×8 tile store plus masked tile-index table | **RESOLVED** |
| TLC color remaps | `L01.PAK` … `L29.PAK:LEVEL##.TLC` | 21×256 byte remap tables | **RESOLVED** |
| XXX automap legends | `L01.PAK` … `L29.PAK:LEVEL#.XXX` | 12-byte legend records | **RESOLVED** |
| DAT decorations | `KEEP.PAK`, `FOREST1.PAK` … `YVEL.PAK:*.DAT` | count-prefixed 72-byte decoration-property records | **RESOLVED** |
| TLK/VOC archives | `DATA/00.TLK` … `DATA/29.TLK` | directory of named, contiguous Creative Voice File chunks | **RESOLVED** |
| language/runtime packages | `DATA/ENG/*.PAK` | English UI, introductions, finale and voice resources | TBD |
| level packages | `DATA/L01.PAK` … `DATA/L29.PAK`, `O##*.PAK` | level and object data | TBD |
| shared packages | `DATA/GENERAL.PAK`, `MUSIC.PAK`, `VOC.PAK` | common assets, music and digitized speech | TBD |
| rendering tables | `DATA/{ENG,FRE,GER}/BLEND.TAB`, `BLEND2.TAB` | 256×256 byte lookup tables for weighted 6-bit VGA palette blending | **RESOLVED** |

`python tools/re/pakinfo.py game/cd/DATA --verify-tree` verifies the PAK
directory invariant across 132 files and 2,297 entries: each directory is a
sequence of little-endian file offsets followed by NUL-terminated names, an
empty name terminates the directory, and the terminal offset equals the file
size. For `DATA/ENG/INTRO1.PAK`, the directory ends at `0x36`, data starts at
`0x3A`, and the three entries partition the file at `0x2446`, `0x2AC7` and
`0x3CC9`.

The same tool decodes all 265 CPS entries in the extracted CD tree using the
10-byte header, 768-byte VGA palette and Frame4 payload. Two independent
intro images were rendered and visually inspected:
`work/probes/INTRO1-VIRGIN.png` and `work/probes/INTRO2-SUNRISE.png`. The CPS
layout is **RESOLVED** for this corpus. `python tools/re/fontinfo.py`
validates the Westwood v3 font header, indexed arrays and glyph-byte spans for
`INTRO.FNT` (174 glyph slots, 170 active, 111 unique data blobs) and
`NEW8P.FNT` (226 slots, 172 active, 139 unique data blobs); both render to
visually inspected sheets under `work/probes/`. `python tools/re/dipinfo.py`
validates all nine `.DIP` witnesses across English, French and German: the
first 16-bit offset is the table size, offsets are nondecreasing, every string
is NUL-terminated, and the final slot is the empty sentinel at the last byte.
The same tool validates the three `L01.PAK` language tables, each with 164
slots and 163 nonempty strings. All 58 `LEVEL#.INI`/`.INF` resources share a
`FORM`/`EMC2` layout with `ORDR` and `DATA` chunks, with an optional big-endian
`TEXT` offset table; the chunk bounds and text invariant are established by
`python tools/re/emc2info.py`. The same tool validates the interpreter framing:
`ORDR` and `DATA` are big-endian `uint16` arrays, non-sentinel function offsets
stay inside `DATA`, Lands of Lore entry points begin at offset `+1`, and every
entry instruction is in the 19-opcode core domain. A static walk of all 1,475
non-sentinel entries keeps 71,863 reachable instructions and 3,642 distinct
branch targets inside `DATA`; observed system-call dispatch IDs occupy
`0x00..0xBE` within the interpreter's 8-bit call domain. Dynamic return/tail
call targets and system-call meanings remain TBD.
`python tools/re/levelinfo.py` validates all 29 level geometry packages: every
CMZ entry is a Frame4 stream that decodes to 1,024 blocks of four bytes, except
`L24.PAK`, whose blocks are nine bytes; every WLL entry has a 2-byte shape index
and 12-byte wall records with VMP values in `0..6`. `python
tools/re/areainfo.py` validates all 13 VCN/VMP pairs, including both YVEL
variants: each VCN has exact 4bpp tile storage (`tile_count × 32` bytes), and
every masked VMP reference falls within its matching VCN tile count. The full
renderer remains a separate unresolved consumer.
`python tools/re/tlcinfo.py` validates all 29 TLC entries as exact `21 × 256`
byte tables. `python tools/re/xxxinfo.py` validates all 29 XXX entries as
12-byte records, 73 records total. The record semantics are now bounded to the
automap legend family; string lookup integration remains TBD.
`python tools/re/datinfo.py` validates the 12 area DAT tables as a 16-bit record
count followed by 681 total 72-byte decoration-property records.
`python tools/re/tlkinfo.py` validates all 30 `DATA/*.TLK` archives: a leading
directory-end offset, NUL-terminated names with increasing payload endpoints,
five zero padding bytes, and 4,912 contiguous Creative Voice File chunks
(11,134 type-1 voice blocks). The remaining resource families stay TBD.
`python tools/re/blendinfo.py` validates all six `BLEND*.TAB` files as exact
`256 × 256` byte matrices. `BLEND.TAB` is byte-identical across ENG/FRE/GER,
as is `BLEND2.TAB`. `python tools/re/blendinfo.py game/cd/DATA/ENG/BLEND.TAB
--check-finale game/cd/DATA/ENG/FINALE1.PAK` reproduces the first `0xFFFC`
bytes of both tables exactly: `BLEND.TAB` uses the raw 6-bit VGA palette from
`RETURN.CPS`, while `BLEND2.TAB` uses `EYE2.CPS` (the same palette is also used
by `FACE.CPS` and `TAPPING.CPS`). For source index `s` and destination index
`d`, each channel is
`min(63, ((P[s] * 22) >> 6) + ((P[d] * 42) >> 6))`; the result is the nearest
entry in `P` by squared RGB distance, with the last equal-distance index
winning. The common final four bytes are the legacy residue `E4 D5 02 00`.
See [analysis/blend.md](blend.md) for the complete witness and rendering
implication.
