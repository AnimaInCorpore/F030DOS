# Executable model — initial audit

Status: the MZ header, mapped-image boundary and relocation table are
**RESOLVED** for the two initial DOS executables. The CD `LANDS.EXE` appended
region is **RESOLVED** as Borland C++ 3.x Turbo Debugger TDINFO/TDS v3.16 data,
including its version-specific post-record tables. Its runtime mapping is
**RESOLVED**: it is outside the DOS load image and is not an overlay pool.

## English CD runtime: `DATA/ENG/LANDS.EXE`

Measured from the extracted CD tree with `python tools/re/mzinfo.py`:

| quantity | value |
|---|---:|
| file size | 357,509 B (`0x57485`) |
| SHA-256 | `5c0c5478df61a421a04d86ef10548ab73e775ed15d79d35bfa88c4ef5a5ec21c` |
| MZ header | `0x2800` B (640 paragraphs) |
| DOS image end | `0x23B00` |
| DOS load module | `0x21300` B |
| relocation records | 2,151 at file `0x3E` |
| entry | `0000:0000`, file `0x2800` |
| stack | `2128:0080`, file `0x23B00` |
| appended region | `0x33985` B, file `0x23B00..EOF` |

The first bytes at the entry are:

```text
BA 16 1D 2E 89 16 91 02 B4 30 CD 21 8B 2E 02 00
8B 1E 2C 00 8E DA A3 7D 00 8C 06 7B 00 89 1E 77 00
```

This is the familiar Borland 16-bit startup shape: load DGROUP, save the
relocated segment, query the DOS version, capture the PSP fields and load DS.
The file also contains `Borland C` at `0x1F964` and
`Borland overlay manager` at `0x21F54`.

The stack invariant is useful: `0x2800 + (0x2128 << 4) + 0x80 = 0x23B00`,
exactly the MZ image end. The appended bytes begin with `FB 52`, the
little-endian TDINFO signature, followed by version `3.16` and a `0x20`-byte
extension. The header reports 3,583 names, 5,597 symbols, 167 modules and a
42,233-byte name pool (`0xA4F9`) at file `0x4CF8C`. The pool contains exactly
3,583 NUL-terminated names, including compiler/runtime symbols and source
names such as `__setargv__`, `_Main_Program` and `.\FILEINIT.C`.

Using the standard TDINFO record widths, the records occupy file
`0x23B50..0x4AE84`. The compact v3.16 extension then supplies a coverage
offset count of `0xE95`; the remaining tables are:

```text
coverage map:               161 × 2 = 0x0142 bytes
coverage offsets:         0xE95 × 2 = 0x1D2A bytes
module optimization flags:   167 × 4 = 0x029C bytes
total:                                0x2108 bytes
```

The total ends exactly at the name pool. The compact extension also reports
zero class, parent, scope-class, module-class, browser and optimized-symbol
records for this executable, with a zero debug-flags word. The French and
German `LANDS.EXE` files and all three supplied `FINALE.TDS` witnesses satisfy
the same table equation with their own counts. `python tools/re/tdinfo.py
game/cd/DATA/ENG/LANDS.EXE` checks the table end and the extension's relative
name-pool offset, in addition to verifying all 5,597 symbol addresses resolve
inside the MZ image.

The French and German `LANDS.EXE` witnesses carry the same `FB 52` TDINFO
v3.16 structure with their corresponding counts. The supplied `FINALE.TDS`
files begin with the same format, providing separate same-toolchain witnesses.

This is debugger-only data appended after the image, not a DOS-loaded overlay:
no relocation targets enter the tail, and the tail is not `FBOV`. Keep it out
of the disassembly and do not apply the installed `MAIN.EXE` overlay mapping
to it. The TDS symbol records are useful later for naming and cross-checking
addresses, but they do not by themselves add indirect execution seeds.

## Installed DOS variant: `DATA/HARDRIVE/MAIN.EXE`

This file is a separate linked variant, not a copy of `LANDS.EXE`:

| quantity | value |
|---|---:|
| file size | 356,928 B (`0x57240`) |
| SHA-256 | `10a9bdce8e234a917da36bbdfe5434add3d9ce01f0ea9b132a95b2fd1ef03e23` |
| MZ header | `0x3800` B (896 paragraphs) |
| DOS image end | `0x3CC40` |
| DOS load module | `0x39440` B |
| relocation records | 3,226 at file `0x3E` |
| entry | `0000:0000`, file `0x3800` |
| stack | `393C:0080`, file `0x3CC40` |
| appended region | `0x1A600` B |

All 2,151 `LANDS.EXE` relocations and all 3,226 `MAIN.EXE` relocations point
inside their respective MZ images under the standard `(offset, segment)` DOS
record interpretation. That establishes the initial mapped-image boundary;
it does not classify the CD tail. The installed `MAIN.EXE` is different: its
appended region begins with:

```text
3CC40: 46 42 4F 56 F0 A5 01 00 50 FC 02 00 27 01 00 00
       F  B  O  V  ovrsize 0x1A5F0  exeinfo 0x2FC50  segnum 295
```

`0x1A5F0 + 16 = 0x1A600`, exactly the file tail size, so the installed
variant's tail is **RESOLVED** as a Borland `FBOV` overlay pool. The CD
`LANDS.EXE` tail is the separate TDINFO/TDS case described above and must not
inherit this mapping by analogy.

## CD versus installed link

The two files share the Borland startup family but are not interchangeable
linked images:

| quantity | CD `LANDS.EXE` | installed `MAIN.EXE` |
|---|---:|---:|
| MZ header | `0x2800` | `0x3800` |
| DOS load module | `0x21300` B | `0x39440` B |
| MZ image end | `0x23B00` | `0x3CC40` |
| relocation records | 2,151 | 3,226 |
| appended format | TDINFO/TDS v3.16 | `FBOV` |
| appended bytes | `0x33985` B | `0x1A600` B |
| `CD 3F` overlay-call opcode in MZ image | 0 | 531 |

At the entry, both variants have the same startup bytes from offset `+3`
through `+0x5D`; the first three bytes contain different relocated DGROUP
values (`BA 16 1D` versus `BA 2D 2E`), and the first mismatch after that
common run is at `+0x5E`. The next mismatch is another linked address, and
the load-module sizes, relocation counts and segment ranges then diverge
substantially. This is evidence of a common toolchain/startup shape,
not evidence that one executable can stand in for the other. Analyze their
MZ images and appended contracts separately.

The opcode scan is an additional contract check: the CD MZ image contains no
`CD 3F` overlay dispatch sites, while the installed image contains 531. The
CD build therefore has no evidence of the installed variant's Borland
overlay-call path; its generic `_Load_Overlay`/`_Ovlhandler` symbols are not
enough to establish a live overlay model.

## First disassembly boundary

Start with `LANDS.EXE` file offsets `0x2800..0x23B00` in 16-bit mode. Keep the
header, relocation table, proven strings/data, and appended region out of a
linear sweep. Add only the MZ entry and evidence-backed indirect targets from
`re/seeds.txt`.
