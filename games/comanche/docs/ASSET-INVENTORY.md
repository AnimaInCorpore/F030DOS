# Comanche asset inventory

This document records the layout of the supplied DOS distribution and the
current reverse-engineering boundaries. The original archive and all derived
game data are local ignored artifacts; they must not be committed.

## Distribution layers

The supplied `assets/001758_comanche.7z` archive contains three raw 1.44 MB
FAT12 floppy images:

| Image | Size | Contents |
|---|---:|---|
| `disk01.img` | 1,474,560 bytes | Installer, LHA utilities, `OVERKILL.002` |
| `disk02.img` | 1,474,560 bytes | `OVERKILL.001` |
| `disk03.img` | 1,474,560 bytes | `OVERKILL.000` |

The extracted images are under:

```text
assets/extracted/001758_comanche/001758_comanche/disk01.img
assets/extracted/001758_comanche/001758_comanche/disk02.img
assets/extracted/001758_comanche/001758_comanche/disk03.img
```

The floppy root files are under
`assets/extracted/001758_comanche/files/`. `INSTALL.BAT` reconstructs the
self-extracting installer with:

```text
copy /b overkill.000+overkill.001+overkill.002 overkill.exe
```

The reconstructed `OVERKILL.EXE` is a 4,059,001-byte MZ self-extracting LHA
archive. Its 1,604-byte MZ load module ends at file offset `0x664`; the LHA
payload begins there and is 4,057,365 bytes.

The payload extraction is kept at:

```text
assets/extracted/001758_comanche/installed/
```

It contains 92 files totalling 7,037,871 bytes. The explicit copy intended to
represent the installed `C:\COMANCHE` directory is:

```text
assets/extracted/comanche_hdd/
```

It has been verified to contain the same 92 files and matching SHA-256 hashes.
Copy this directory to a DOS hard disk as `C:\COMANCHE\`. `C.BAT` launches
the game. `AUTOEXEC.XMS` expects `C:\DOS\HIMEM.SYS`; `BOOTXMS.BAT` is an
optional boot-floppy helper and is not required when using an existing DOS
hard disk.

## Code and data inventory

The installed tree is overwhelmingly external game data:

| Item | Size | Interpretation |
|---|---:|---|
| `COMANCHE.EXE` on disk | 61,154 bytes | LZEXE-compressed main executable |
| Unpacked `COMANCHE.EXE` load image | 386,823 bytes / 377.8 KiB | MZ load module, including the linker's zero-filled BSS |
| — real-mode bootstrap | 5,888 bytes | Image `0x00000`-`0x016FF`: XMS/VCPI probe, GDT/IDT build, mode switch |
| — 32-bit flat program | 207,648 bytes | Image `0x01700`-`0x3421F`: all game code, tables, and strings |
| — zero-filled BSS | 173,287 bytes | Image `0x34220`-end: address space, not content |
| `SOUNDSET.EXE` | 2,790 bytes | Auxiliary sound utility |
| Installed non-EXE data | 6,973,927 bytes | Missions, terrain, graphics, sound, music, and animation data |

The two installed executables occupy only 0.91% of the on-disk installation.
The porting denominator is the 207,648-byte flat region, not the 377.8 KiB
load-module size: 44.8% of that file is BSS the linker emitted and never
wrote anything into. Even 207,648 bytes is an upper bound on code, because it
also holds tables, strings, and alignment; the instruction-byte count is an
analysis result. The current 32-bit recursive-descent pass reaches 33,614
instructions and 120,514 bytes of it, 58.0% of the content region, measured
with the annotation store used as a data barrier. Every remaining byte is
identified as data by a row or is padding: 69,750 and 17,384 respectively,
with none unaccounted and none left undecoded inside a routine.

The inventory includes sound and music files for completeness, but they are
out of scope for the first playable Falcon milestone. Network functionality
is not part of the initial port and should not be introduced as a runtime
dependency.

`OVERKILL.EXE`, `LHA.EXE`, and `COPYR.EXE` are distribution/installer tools,
not Comanche gameplay code.

## Executable unpacking boundary

`COMANCHE.EXE` is packed with LZEXE 0.91. It has the `LZ91` marker at MZ
offset `0x1C`, and the bootstrap's information block reports:

```text
packed entry:       0ED1:000E
real entry:         0000:09BC
compressed size:    0x0ED1 paragraphs
temporary space:    0x4FB2 paragraphs
decompressor size:  0x01B2 bytes
```

The current `tools/re/disasm.py` must not be run directly on the packed
executable. First produce an unpacked MZ executable with a standard `UNLZEXE`
implementation, then run `mzinfo.py`, `codemap.py`, and `disasm.py` on that
output. LZEXE's original documentation and source are available at
<https://bellard.org/lzexe/>.

The unpacked program enters a 386 protected-mode/custom DOS-extender path and
then runs as a flat 32-bit program: one code selector and one data selector,
both based at image offset `0x1700`, with no far pointers and no segment
relocations past the extender. `tools/re/disasm.py` handles both halves —
`seg:off` for the bootstrap, `--flat 1700` for the game. The selector table,
the 32-bit entry point at flat `0x1538`, and the two-pass procedure are
recorded in [RE-WORKFLOW.md](RE-WORKFLOW.md). A DOSBox debugger capture is
still the right tool for computed jump targets and for observing resource
reads at runtime. The unusual Comanche mode switch is discussed in
<https://www.os2museum.com/wp/maximum-overkill/>.

## Measured resource markers

The installed tree contains 39 `.DTA` files (5,946,286 bytes), 32 `.RLE`
files (958,996 bytes), three `.DTL` files (5,004 bytes each), two `.MIS`
files, and four `.SCR` files. These observations are format markers, not yet
complete decoders:

- Every `.DTA` file begins with the eight-byte ASCII signature `Kyle DTA`.
  The following little-endian words are consistent with geometry fields across
  several families: `P11.DTA` carries `15, 21, 16, 22`, while
  `MISSION.DTA` carries `327, 239, 320, 200`. The large `D1.DTA`--`D4.DTA`
  files carry 1023/1024-scale values. The field roles and payload encoding
  still need to be proven against runtime reads.
- Every `.RLE` file begins with `KRL0` or `KRL1`. The container version does
  **not** predict the payload: 30 files are `KRL1` and 2 are `KRL0`, and both
  versions appear in more than one family. The payload marker in the first 64
  bytes does predict it, and all 32 files have been classified by it:

  | marker | files | contents |
  |---|---:|---|
  | `SG` | 21 | graphics: `COMA`, `LH66`, `TANK`, `TURR`, `SPIN`, `SKY1`-`SKY4`, `ZOVE`, `HUDS`, `RADR`, `BOOM`, `BULL`, `CHAF`, `FUEL`, `HELL`, `HOKE`, `ROCK`, `STGR`, `CONS` |
  | `MS3-KGF'91` | 8 | music: `MUSDAY`, `MUSNIGHT`, `MUSVOLC`, `MUSWIN`, `MUSLOSE`, `WINMUS`, `BIGWIN`, `FANFARE` |
  | `K1` | 3 | digitised sound: `SND1`, `SPEAK0`, `SPEAK1` |

  **The `KRL1` codec and the `SG` sprite format are decoded.** The container is
  compressed - which is what the extension means, and why reading a `.RLE`
  file's bytes as though they were the runtime layout does not work.

  `KRL1` file: `"KRL1"`, then a dword giving the **decompressed** size, then a
  byte RLE stream. A byte below `0xC0` is a literal; `0xC0` or above is a run of
  `byte & 0x3F` copies of the following byte. `res_open_d` at `00015E6E` reads
  the 8-byte header, allocates the declared size and calls `0001644B`; `KRL0`
  files are stored and copied out by `00015F28` instead. **This is the same
  codec the `.DTA` terrain files use** - `src/resources.s` already decodes it -
  so one decoder serves both families.

  The decompressed image is the sprite bank:

  | offset | contents |
  |---|---|
  | `+0` | `'SG'` |
  | `+2` | sprite count, word |
  | `+4` | dword offset to the palette block |
  | `+8` | directory, **1-based**, 8-byte records |
  | | `+0` width, `+1` height, `+2` signed X offset, `+3` signed Y offset, `+4` dword offset to the pixel data from the image base |

  The header is simply **record 0** of that directory, which is why every access
  in the code is 1-based `[esi + ebx*8]`.

  Pixel data is uncompressed and stored **column major**: pixel `(x, y)` sits
  at `data[x * height + y]`, so a column is contiguous and columns run left to
  right. The rows in each column are stored bottom first for the DOS blitter;
  the Falcon loader reverses each column into its top-down chunky form. A
  sprite still occupies exactly `width * height` bytes.

  That layout was established by rendering, not by reading the blitter, and the
  distinction matters. `00025880` consumes each scanline as four chunks of
  `width/4` bytes, one per VGA plane, and walks the destination upward with
  `sub edi,0x52`. Applied to the file bytes, that produces diagonal hatching.
  Both descriptions are right about different buffers: the game builds a planar
  copy at load time and the blitter reads that copy, so the planar interleave
  and the bottom-first order describe the runtime form, not the file.

  `HUDS` sprite 1 is what settles it - a 192x5 compass ribbon whose letters are
  upright only when the column-major reading is combined with the bottom-first
  row order. The same load-time reversal makes its SPEED label upright on the
  Falcon surface.
  `TANK`'s 51 entries then read as a smooth rotation sequence with track links
  resolved, which a wrong stride does not produce by accident.

  The palette block begins with an `0x0C` marker and holds 256 RGB triples with
  **six-bit** components, ready for the VGA DAC: the largest component across
  all 21 banks is 63, and twelve of them reach it exactly. These are not the
  eight-bit values that the `shr al,2` at `000164BC` narrows - that code serves
  the other palette path, the one reading a marker out of the input stream,
  which never runs for an `SG` bank because an `SG` bank carries its palette
  inside the decompressed image. Ten banks carry a second 768-byte block after
  the palette.

  Two independent checks establish this, and one earlier check did not.
  Decoding to the size the header declares proves nothing - the decoder is
  bounded by that field, so it is circular. What does hold, across all 21 `SG`
  banks: every directory record's span to the next equals `width * height`, and
  the `0x0C` marker is found at exactly the offset the header's `+4` pointer
  gives - 21 of 21, at a byte position the decoder never consults.

  Two consequences for anything reading these files. The header length can be
  **smaller than the stream**: eight banks leave between 194 and 54,477 bytes
  undecoded, and that is correct behaviour, since the sprite directory is
  complete in every case. And the byte `width`/`height` fields **cannot express
  the `SKY` backdrops**, which are special SG payloads containing 512
  column-major strips of 150 bytes whose data starts at offset 16; a reader
  that trusts `width * height` there gets only the 16-byte special record.
  The browser attract renderer now consumes that exact 512x150 boundary and
  derives the visible strip origin from the full 32-bit view angle.

  Do not apply one decoder to all `.RLE` files, and do not infer the family
  from the filename: `SND1.RLE` and `FANFARE.RLE` are sound and music despite
  sharing the extension with the sprite files, which is what makes the marker
  the only safe discriminator. This matters for scope as well as for decoding -
  the routines that consume `SND1.RLE` are sound playback and therefore
  deferred, and they read as image code until the marker is checked.
- `LOW.DTL`, `MEDIUM.DTL`, and `HIGH.DTL` are each exactly 1,251 little-endian
  dwords. **The layout is now decoded**: dword 0 is a column count - 100, 180
  and 250 - followed by **five tables of 250 dwords each**.

  The file loads at flat `00019EE0`, and the sizes prove it before any decoding
  does: the unclassified span there is `0001B26C - 00019EE0` = 5,004 bytes, and
  each `.DTL` is exactly 5,004 bytes. The image's built-in default for dword 0
  is 200, a fourth value that no shipped file uses, and all five tables are
  uniformly 1 in the image.

  The three terrain renderers index tables 0 and 1 by column
  (`[ecx*4 + 00019EE4]` and `[ecx*4 + 0001A2CC]`), and `surface_blit_b` reads
  table 2 from `0001A6B4`. In the shipped files table 2 falls monotonically from
  a large value - the shape of a reciprocal or one-over-depth table - while
  tables 0, 1 and 3 rise monotonically. Table 4 spans the full signed range.

  Note the column count is independent of the emitter bank sizes (192/96/40):
  the tables are sized for 250 columns regardless of which bank draws them, so
  do not equate the `.DTL` count with a bank.
- Each `.SCR` begins with a little-endian payload length equal to file size
  minus four bytes: 6,205/6,229/5,421/7,277 for `DEMO0.SCR` through
  `DEMO3.SCR`. **The record stream is now decoded**: 4-byte length, then a
  13-byte header, then N fixed 8-byte input records. All four files divide
  exactly - 774, 777, 676 and 908 records with no remainder - which is what
  confirms the size rather than any one file doing so.

  The four-byte prefix is not a separate header field: it **is** the recorder's
  write cursor. The load at `00019A2D` transfers to `0002DB0C`, which is the
  cursor global, with the record buffer following at `0002DB10`; the save at
  `00019AD0` writes from the same address with length `[0002DB0C] + 4`. That is
  why the prefix always equals file size minus four - the cursor and the buffer
  are read and written as one block. The 13 bytes therefore sit inside the
  buffer ahead of the first record rather than being a file header.

  The demo number comes from `[0002975A]` and is patched into the filename's
  digit; both copies of the `"demo1.scr"` string have their own patch site.

  The layout comes from the recorder at `00018C42`, which appends the same
  eight bytes to its buffer:

  | offset | size | source global |
  |---|---|---|
  | `+0` | byte | `00001B70` |
  | `+1` | byte | `00019D82` |
  | `+2` | byte | `00019DF2` |
  | `+3` | byte | `00019DF3` |
  | `+4` | word | `00019DC8` |
  | `+6` | word | `00019DCC` |

  In the shipped demos `+1` is constant per file (37, 124, 21, 1) and the two
  words are small signed values, consistent with a mode byte and two axis
  deltas. The recorder caps the buffer at `0x2000`, and every shipped demo is
  comfortably inside that.
- `.MIS` files do not begin with a shared plain-text signature; treat them as
  encoded or packed mission streams until the executable's read/decode path is
  traced.

### Console DTA storage geometry — RESOLVED for `CONSOL1S.DTA` (2026-08-25)

`CONSOL1S.DTA` is a full cockpit surface, not a 320x200 byte image. Its
`Kyle DTA` header has `327, 289, 320, 200` at offsets `+8`, `+10`, `+12`, and
`+14`. The first pair is the stored geometry: the DOS loader forms
`(327 + 1) * (289 + 1) = 95,120` decoded pixels with a 328-byte row pitch. The
last pair describes the VGA display mode and must not be used as the storage
width or height.

The PCX-style stream begins at the loader's `+128` boundary and ends after
exactly 95,120 pixels. The next byte is the `0x0C` palette marker followed by
768 palette bytes; the installed file is 19,295 bytes, so the 769-byte tail is
not image data. The Falcon `CONSOLE_BYTES = 100000` allocation is capacity,
not the decoded payload length. This boundary is checked against the shipped
file, the historical loader contract in `src/console.s`, and the current
browser decoder in `jsComanche/dos-data.js`; the other `CONSOL<n>S.DTA`
variants still need the same per-file check before being generalized.

The cross-port rule is broader than this one resource: derive stored pitch,
decoded extent, visible viewport, and palette/tail boundaries from the
consumer's read loop and corpus checks. Never substitute display-mode fields,
an allocation capacity, or a plausible older geometry for the decoded storage
contract.

For a porting milestone, this consumer contract is not a source-generation
permission by itself. Trace the milestone route in the authoritative DOS image
first with QEMU's TCG `exec,nochain` extension, including the resource read and the function that consumes it; only then
generate the JavaScript/M68k data or decoder source and link it to the route
manifest. An asset not reached or not explained by that route remains
`dormant`/`Unproven`.

The recovered flight-frame composition is now recorded alongside the storage
boundary. After terrain, the DOS frame draws `CONSOL1S.DTA` from source row 0
over the visible 320-column crop, skipping only source index `255`; index `0`
is ordinary console ink. It then draws opaque `CONS.RLE` elements `0x09` at
`(0x10,0xEA)`, `0x25` at `(0x0C,0xC9)`, and `0x39` at `(0x110,0xCB)`. The
separate `HUDS.RLE` bank supplies the masked compass marker/window, `SPEED`
label and digits, clearance ladder/value, velocity reticle, and the
`00025CA2` sight line. `HUDS` keeps the column-major bottom-first layout; the
`CONS` bank remains plane-chunked bottom-first. This is a recovered composition
contract, not a reason to draw generic canopy bars, ticks, or gauges.

The terrain map family is now decoded far enough for the first Falcon test:

- `D1.DTA` and `C1.DTA` have the `Kyle DTA` signature and a 16-byte header.
  Their first four little-endian words are `1023, 1023, 1024, 768`; the first
  two describe a 1024x1024 map and the latter two are display-related fields.
- The payload after that header uses PCX-style byte RLE. Decoding until
  1,048,576 bytes yields the complete 1024x1024 map. `D1.DTA` is the height
  map and `C1.DTA` is the matching colour map for the first terrain family.
- `tools/prepare-original-test.py` validates those fields and decodes both
  maps at full resolution into ignored build output, one byte per sample, plus
  the sine and reciprocal-depth tables the renderer reads. The 68030 reference
  renderer marches the complete 1024x1024 map. Height samples run 0-187.
- `C1.DTA` is a genuine 256-entry palette index, not a small class field: it
  uses 213 distinct values over 0-221. The distribution is heavily skewed -
  55% of all samples fall in indices 0-15 - and the index does not track
  height, since mean `D1` height per index sits between 23 and 65 for almost
  every index. So `C1` is a terrain-type map, and neither its high nibble nor
  terrain height is a usable stand-in for the palette.
- `C1.DTA` carries the original 768-byte VGA palette immediately after the
  `0x0C` colour-map prefix and its 1 MiB RLE payload. The generator extracts
  that palette and expands it to the Falcon's RGB565 table; there is no colour
  ramp or height-derived palette in the active path.
- A 768-byte VGA palette is not present in the obvious executable locations:
  the only VGA-range run there is a 1,032-byte monotonic grey ramp at file
  offset `0x23c9e` (flat `0x2259e`), which is a gamma or fade table. The
  terrain palette is an asset tail, not executable data.

The first runtime loader is now in `src/resources.s`. It opens `D1.DTA` and
`C1.DTA` from the program's current directory through GEMDOS, checks the
`Kyle DTA` signature, decodes the 16-byte-header-plus-PCX-RLE stream into two
1024x1024 BSS maps, and stops with an error when either file is missing or
invalid. The generated build maps remain ignored reference inputs; they are no
longer linked into the `.TOS` image.

The build-time generator and this runtime loader must agree on both the asset
family and the colour index space. They now use the original D/C family and its
palette, and `tools/build-run.sh` refuses to link a build whose staged maps and
generated palette come from different sources. Mission files select the other
terrain families and sky assets through the recovered resource blocks; no
generated landscape or palette is substituted when an original asset is absent.

`tools/build-run.sh` stages the D1/C1 terrain pair and the current `0.MIS`
stream into ignored `release/` output when the local installed tree is
available, so Hatari exercises the same runtime path as a copied
`C:\COMANCHE` installation.

The first Falcon loader should therefore dispatch by both extension and
signature/subtype. A filename-only `.RLE` decoder or a single generic `.DTA`
layout would silently mix terrain, sprites, screens, and audio data.

The first mission file boundary and scalar parser are now ported. The DOS flat
path at `0002A104` probes numbered `0.MIS`-`9.MIS` files; the shared reader at
`00015DD0` uppercases the inline name and reads in `0xFA00`-byte chunks until a
short read. The Falcon currently loads `0.MIS` with bounded `0x1000`-byte
GEMDOS transfers into a 16 KiB BSS buffer, preserving the raw byte stream and
EOF contract at the current TOS/Hatari boundary.

The DOS decoder at `0002A2F8` XORs non-plain streams with the repeating memory
bytes `03 06 12 11`; this turns `0.MIS` into line-oriented ASCII beginning
`{Comanche Training}`. `src/mission.s` now extracts the two title fields, the
resource-list boundary, mission kind, start X/Y/heading, and the number of
object lines. The start tuple uses quarter-tile DOS units, so `300,800,0`
becomes Falcon 16.16 coordinates `(75,200)` and heading `0`. Object field
semantics and handlers remain deferred.
