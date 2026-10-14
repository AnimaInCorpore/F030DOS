# Distribution and resource archive

Status: `RESOLVED` for the outer image and ZIP container; installed-file
semantics beyond the ZIP extraction are not yet required.

## Source image

The supplied source is `assets/FALCON3.ISO`:

| Property | Measured value |
|---|---:|
| Size | 25,946,112 bytes |
| SHA-256 | `6079944302E1AA8BD604F480A592B505CB73E8F0BC1D0875709134A20D214D80` |
| CD README | Falcon 3.0 v3.05, dated 1995-09-22 |

The image is extracted with `tar -xf` to `game/cd/`. The game files are at
the CD root; the manuals and hardware utilities are not part of the initial
disassembly target.

## `FALCON3.RES`

`game/cd/FALCON3.RES` begins with the ZIP local-file signature `50 4B 03 04`.
It is not a Falcon-specific opaque resource stream:

| Property | Measured value |
|---|---:|
| On-disc size | 6,495,807 bytes |
| ZIP members | 698 |
| Uncompressed member bytes | 10,630,258 |
| Compressed member bytes | 6,421,919 |
| CRC check | `zipfile.testzip()` returned no failing member |
| `FALCON3.EXE` member | 1,373,671 bytes, 479,473 compressed |

`tools/extract_resources.py` performs the CRC check and writes the archive
members to `game/FALCON3/`. It is safe to rerun; it does not delete files.
The extracted tree is the pristine reference for analysis, while all patches
and generated views belong under `work/` or `re/`.

The CD's `XTRACT.LST` names the installed root executable and resource
families. The archive contains the executable, `*.BIN` aircraft/object data,
`*.DAT`/`*.IDX` tables, image/panel resources, sound data, and `MEDIA/`,
`MUSIC/`, and `ARMSDATA/` subtrees. No format has been inferred from a file
extension alone.
