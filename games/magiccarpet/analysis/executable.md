# Executable model — initial audit

Status: the primary MZ container and LE container arithmetic are **RESOLVED**
for `CARPET.EXE`. The DOS/4G startup hand-off and protected-mode placement are
now **PARTIALLY RESOLVED** by a live QEMU byte match; the demand-load policy
and the runtime meaning of one signed-looking internal fixup remain **TBD**.

The measurements below come from `MagCarp/CARPET/CARPET.EXE` in the supplied
archive. Recreate the extracted file and run:

```text
python tools/re/mzinfo.py game/MagCarp/CARPET/CARPET.EXE
```

## MZ loader

The first 32 bytes are:

```text
4d 5a 92 01 15 00 06 00 06 00 86 00 ff ff 99 02
00 08 00 00 16 02 00 00 40 00 00 00 00 00 00 00
```

| quantity | value |
|---|---:|
| file size | 715,009 B (`0xAE901`) |
| MZ header | `0x60` B (6 paragraphs) |
| DOS image end | `0x2992` |
| MZ load module | `0x2932` B |
| relocations | 6 at file `0x40` |
| entry | `0000:0216`, file `0x276` |
| stack fields | `0299:0800` |
| bytes after MZ image | `0xABF6F` B |
| MZ relocation targets | 6/6 inside the MZ image |
| SHA-256 | `f9198424f98cca045b15746114fac90827994e4f99cb5c4ae75b36782fc0919c` |

The six relocation records are standard DOS `(offset u16, segment u16)`
records. They remain confined to the small loader image. The entry starts with
a short jump over the Watcom C runtime copyright string; that string is not an
instruction stream. The loader image must therefore be decoded as a bounded
16-bit MZ program, not swept into the LE payload.

The MZ header's optional new-header pointer at file `0x3C` is `0x2998`. Six
zero/padding bytes separate the DOS image end at `0x2992` from the LE signature.

## Watcom LE payload

The LE signature is at file `0x2998`. The header reports:

| field | value |
|---|---:|
| format level | `0` |
| CPU / OS type | `0x0002` / `0x0001` |
| module flags | `0x00000200` |
| object pages | 139, size `0x1000` |
| entry | object 1, offset `0x52178` |
| stack | object 3, offset `0xA2C00` |
| last page bytes | `0x301` |
| object table | LE offset `0xC4`, 4 objects |
| object page map | LE offset `0x124` |
| entry table | LE offset `0x35A` |
| fixup page / record tables | LE offsets `0x35B` / `0x58B` |
| imported names | LE offset `0x21B49` |
| data pages | LE offset `0x24600` |

The measured object directory is:

| object | virtual size | base | flags | page index/count |
|---:|---:|---:|---:|---:|
| 1 | `0x6C0AE` | `0x10000` | `0x2045` | 1 / 109 |
| 2 | `0x124` | `0x80000` | `0x2043` | 110 / 0 |
| 3 | `0xA2C00` | `0x90000` | `0x2043` | 110 / 29 |
| 4 | `0x304` | `0x140000` | `0x2043` | 139 / 1 |

The object/page arithmetic is now checked by
`python tools/re/audit_le.py game/MagCarp/CARPET/CARPET.EXE --stats`:

- the 139-entry object page map is identity, with page flags zero;
- the data-page span is `0x24600..0xAE901`, ending exactly at EOF;
- the object page counts sum to all 139 module pages;
- the fixup page walk consumes every page interval and ends at the import
  module table (`0x2F23 + 0x215BE == 0x244E1`);
- 15,984 records produce 15,984 source sites, all source type 7 (32-bit
  offset) and all targeting internal objects.

This resolves the **file-to-object** mapping, not the complete loader/runtime
model. The object bases in the LE directory are the protected-mode logical
bases to use for object-relative addresses; the DOS/4G hand-off and whether
the mapped pages are copied eagerly or demand-loaded still require runtime
evidence. Do not treat the contiguous bytes after `0x2998` as one object or
assign them the MZ file offset as a protected-mode origin.

## Live protected-mode placement

The reproducible runtime probe is:

```text
set QEMU_SYSTEM_I386=C:\Program Files\Qemu\qemu-system-i386.exe
python tools/re/probe_runtime.py --seconds 6 --interval 0.01
```

It samples QEMU's flat protected-mode `CS:EIP`, reads the bytes at that guest
linear address and searches those bytes in the pristine executable. Nine
matches in one run agree on the same delta:

```text
guest linear = executable file offset + 0xDBA10
```

Measured examples include guest `0x156B60` → file `0x7B150`, guest `0x14CCE1`
→ file `0x712D1`, guest `0x152D16` → file `0x77306`, and guest `0x15B9BC`
→ file `0x7FFAC`. The source file start of
the LE data pages (`0x24600`) therefore maps to guest `0x100010`; object 3's
file-backed start (`0x91600`) maps to `0x16D010`, and the mouse error string at
file `0xAAD30` maps to guest `0x186740` under this measured placement.

This is runtime evidence for DOS/4G loading and relocating the page-backed
image. It also demonstrates why the LE directory bases (`obj1=0x10000`,
`obj3=0x90000`) must not be treated as the guest's flat linear addresses.
The sample window includes flat protected-mode selectors (`CR0=0x11`,
`CS=0x0838`, `DS=0x0828`, both with base zero) immediately before the DOS
return, but it does not yet establish whether every object page is resident
at once or faulted in on demand.

## TMAPS loader cross-check

The bounded protected-mode disassembly also ties the `TMAPS` audit to the
game’s loader. At logical code address `0x58860`, the TMAP loader indexes a
global directory in 10-byte steps, reads the data offset from entry `+0x04`,
reads the 16-bit tag from entry `+0x08`, and computes each compressed block’s
length from the following entry’s offset. It then passes the selected block
through the normal decompression path and reports `ERROR decompressing
tmap%03d` on failure. The same routine family bounds the directory at `0x211`
(529 records), matching the 530-entry local `.TAB` files including their EOF
sentinel.

This is independent executable evidence for the local `TMAPS.TAB` parser and
for treating the final zero-length entry as a directory sentinel. It does not
decode the contents after each six-byte map header; the type-3 variable tails
remain a separate **TBD** grammar.

## Object/page map and worked entry check

The identity page map makes the following file ranges unambiguous. The last
range is short because the LE header says the final page contains `0x301`
bytes.

| object | base | virtual size | mapped pages | mapped file range | interpretation |
|---:|---:|---:|---:|---:|---|
| 1 | `0x10000` | `0x6C0AE` | 1–109 | `0x24600..0x91600` | executable image; final mapped page is padded beyond virtual size |
| 2 | `0x80000` | `0x124` | none | — | zero-filled virtual object; no file-backed pages |
| 3 | `0x90000` | `0xA2C00` | 110–138 | `0x91600..0xAE600` | data/stack object; at least `0x85C00` is not file-backed |
| 4 | `0x140000` | `0x304` | 139 | `0xAE600..0xAE901` | one short file-backed page |

The LE entry is object 1 offset `0x52178`, not file offset `0x52178`:

```text
object 1 + 0x52178 = logical linear 0x62178
object page 82, physical page 83, file offset 0x76778
bytes: EB 78 "WATCOM C/C++32 Run-Time system ..."
```

The initial `EB 78` is the Watcom CRT jump over its embedded banner. The
initial stack is object 3 offset `0xA2C00`, logical linear `0x132C00`, and
auto-DS names object 3.

## Fixup table result

The fixup page table is at file `0x2CF3`; records occupy
`0x2F23..0x244E1`. The record walk closes exactly at the LE import-module
table, and `num_import_mod_entries` is zero. Every decoded record is a
32-bit-offset/internal-target record. This is enough to use the fixup table as
a reverse-xref index once object-relative targets are interpreted; it is not
permission to disassemble the raw payload without applying the object map and
fixups.

One record is intentionally left as a semantic warning rather than forced into
the normal object-range model: the record at fixup-table file offset `0x1A22E`
targets object 3 with raw offset `0xFFF6EBCD` (signed `-0x91433`) and patches
the dword at file `0x749FE`. The record encoding and table boundary are
resolved; whether this is a signed displacement or another LE relocation case
is **TBD**.

## Linked variants

`HIDDEN.EXE` is 715,521 B (`0xAEB01`, SHA-256
`b829f6b576bb5621888c08b7bbbae7a45c14fb2ad080b70dddbe52d2e46bb5fd`) and has
the same MZ header/LE layout; its object 1 virtual size is `0x6C5BE` and its
LE entry offset is `0x52688`. `SELECT.EXE` is 77,336 B (`0x12E18`, SHA-256
`31e46b3ddbf597707e247b13c85832b9548bcd05d4eed27dcc38862c21892ac3`) with a
two-object LE image and entry object 1 offset `0x1D6C`. They are comparison
inputs, not substitutes for the primary `CARPET.EXE` target.

The same structural audit was also run against both comparison inputs:

| file | LE pages / last page | page map | fixup records | data span |
|---|---:|---|---:|---|
| `HIDDEN.EXE` | 139 / `0x301` | identity | 16,043 | exact EOF |
| `SELECT.EXE` | 14 / `0xE18` | identity | 1,282 | exact EOF |

All fixups in both variants are likewise type-7 internal-offset records. This
supports the shared container parser, while the distinct object sizes, entry
offsets and linked images remain separate evidence.

## First disassembly boundary

Start with file offsets `0x60..0x2992` in 16-bit mode, or the headerless MZ
load dump at offsets `0..0x2932`. Keep the MZ header, relocation table, LE
header, object/page tables and payload out of this first listing. Add only the
MZ entry and later indirect targets supported by `re/seeds.txt`.

The reproducible bounded listing is generated with
`python tools/re/list_mz.py game/MagCarp/CARPET/CARPET.EXE --output
work/listings/CARPET-loader.lst` (or `ndisasm -b 16 -o 0x0` against the
headerless dump when NASM is available). The first seed is `0000:0216`; it
jumps to load-image offset `0x2E4`, where the 16-bit Watcom loader begins after
the CRT banner.
