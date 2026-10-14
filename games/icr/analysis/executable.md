# Executable container — IndyCar Racing v1.05

Status: `PARTIALLY RESOLVED` — the container is parsed and the runtime memory
map is now measured from a whole-RAM dump, so file offsets and linear addresses
can be related in both directions. The declared entrypoint is *not* resolved:
the two readings of the LE `EIP` field disagree and neither lands on a function
boundary (§ "Declared entrypoint").

Authority: `game/installed/INDYCAR.EXE`, 742,377 bytes, SHA-256
`5B8BD9AA115C0E8CCD012617B161B44CE02124AA5875F2182EFA132ECA5B8B5A`.

## MZ and LE layout

The DOS stub has a 0x20-paragraph header, 78 relocation entries, initial
`CS:IP = 01BD:23582`, and initial `SS:SP = 0121:0340`. Its declared MZ image
ends at file offset `0xF44E`. A real `LE\0\0` header begins at file offset
`0x27BDC`; incidental signatures elsewhere do not satisfy the header/table
consistency checks.

The LE header describes a 32-bit DOS/4GW-style image with 4 KiB pages, 0x66
pages, two objects, and data pages beginning at file offset `0x2A400`:

| Object | Virtual size | Base | Page-table index | Pages | Flags |
|---|---:|---:|---:|---:|---:|
| 1 | `0x4F7B9` | `0x10000` | 1 | 80 (`0x50`) | `0x2005` |
| 2 | `0x82B80` | `0x60000` | 81 (`0x51`) | 22 (`0x16`) | `0x2003` |

The object page map was read out rather than assumed: it is the identity for
both objects (object 1 = pages 1..80, object 2 = pages 81..102), every entry is
type 0 (a legal physical page, not iterated or compressed), and the page size
is `0x1000`. That makes the whole static file↔virtual relation a single
subtraction:

```text
file = vaddr + 0x1A400      for vaddr 0x10000..0x76000
```

Object 1 therefore occupies file `0x2A400..0x7A400` (vaddr `0x10000..0x60000`)
and object 2 file `0x7A400..0x90400` (vaddr `0x60000..0x76000`, of a `0x82B80`
virtual size — the remainder is uninitialized). The LE pages end at file
`0x90400`, and the file continues for another `0x24FE9` bytes.

## Declared entrypoint — `TBD`

The LE header declares `EIP object 1, EIP 0x4D254` and `ESP object 2,
ESP 0x82B80`. `0x82B80` is *exactly* object 2's virtual size, i.e. the initial
stack pointer is the top of the auto-data object, which is evidence that these
fields are object-relative rather than flat addresses. Under that reading the
entry is vaddr `0x5D254` = file `0x77654`.

An earlier revision of this document recorded file `0x67654`, which is the
other reading (`EIP` treated as a flat address, so `0x4D254 - 0x10000` into
object 1). Both readings disassemble as 32-bit code — that test does not
separate them — and **neither lands on a function boundary**: `0x67654` is
inside a `mul`/`sub` sequence and `0x77654` is inside a function that ends
five instructions later at a `pop ebx; ret`. The runtime map below also shows
the image is not loaded at its declared object bases, so the entrypoint stays
`TBD` pending a capture of the transfer out of the DOS/4GW loader. Nothing
downstream may cite `0x67654` as measured.

## Runtime memory map — measured 2026-08-26

Captured with `python work/gdbstub_probe.py --wait 100 --dump-ram` at the
copy-protection prompt (see [`copy-protection.md`](copy-protection.md)), which
`pmemsave`s all 16 MB of guest RAM and then matches every 4 KB of the file
against it on the host. This replaces the earlier single-sample estimate: a
64-byte window every 4 KB, matched exactly, gives the following resident
blocks. Every delta below is `linear − file`.

| File range | Delta | Linear | Windows | What |
|---|---:|---|---:|---|
| `0x002000..0x004000` | `+0x007150` | `0x009150..0x00B150` | 3 | real-mode MZ stub, in conventional memory |
| `0x00A000..0x00F000` | `+0x124C50` | `0x12EC50..0x133C50` | 6 | DOS/4GW extender |
| `0x010000..0x021000` | `+0x1052EC` | `0x1152EC..0x1262EC` | 18 | DOS/4GW extender |
| `0x02A400..0x04F400` | `+0x115424` | `0x13F824..0x164824` | 38 | LE image, first part — **copy A** |
| `0x02A400..0x04F400` | `+0x13E328` | `0x168728..0x18D728` | 38 | LE image, first part — **copy B** |
| `0x050400..0x0B4400` | `+0x13EEDC` | `0x18F2DC..0x1F32DC` | 60/102 | LE image remainder **and** the appended region, one block |
| `0x0A1124..` (data) | `+0x13FEDC` | `0x1E0000..` | 11 | the module's data, one page above the code delta |

Four things in that table contradict the previous model and are load-bearing
for every later analysis:

1. **The guest is `pm32` flat, not real mode.** `CR0.PE=1`, `PG=0`, `CR3=0`,
   and `CS`/`DS`/`SS` all have descriptor base `0` with a 4 GB limit, so linear
   equals physical and a selector value carries no address information. The
   probe used to compute `(sel << 4) + (EIP & 0xFFFF)` here and printed the
   result as a linear address; see `../F030Method/CROSS-PROJECT.md`.
2. **The seam is at file `0x50400`, not at the LE page end `0x90400`.** The
   `+0x13EEDC` block runs straight through the boundary between the LE pages
   and the appended region without a discontinuity. The appended region is not
   a separate address space; it is the tail of one resident block.
3. **The first `0x25000` bytes of the LE image are resident twice**, at two
   deltas, both matching exactly. Neither copy is "the" image, and a majority
   vote over a handful of byte windows would have picked one and reported it as
   the mapping.
4. **Code and data are displaced by exactly `0x1000`** — code at `+0x13EEDC`,
   data at `+0x13FEDC`. Reading a string with the code delta lands one page
   short and yields a *different, valid-looking* string from the same table:
   file `0xA11A4` + `0x13EEDC` = `0x1E0080` is `"Bad file create"`, while the
   string actually at file `0xA11A4` is `"Page %d, line %d, word 1?"`, resident
   at `0x1E1080`. This one is easy to get wrong and self-consistent when wrong.

The `+0x13EEDC` figure agrees with the earlier single-sample estimate — runtime
`0x1D296B` ↔ file `0x93A8F`, and the DOS file-I/O wrapper at `0x1DDC7F` ↔ file
`0x9EDA3` — so those records stand; what changes is their scope. The primary
`Miscellaneous disk error` text is at file offset `0xA0168`.

### Load-time fixups rewrite the image

Of 102 LE-image windows, 13 match RAM exactly and 47 more match within 8 of 64
bytes; the differences are the loader's applied fixups. The clearest instance
is the copy-protection wait loop, file `0x5AAFB` ↔ linear `0x1999D7`:

```text
file 83 3d 5c 32 00 00 00 75 03 43 eb f4 83 3d 70 3b 00 00 00 …
ram  83 3d 5c 32 1e 00 00 75 03 43 eb f4 83 3d 70 3b 1e 00 00 …
                 ^^                                   ^^
```

The file stores data-object-relative operands (`0x0000325C`) and the loader
adds the data base `0x1E0000` (`0x001E325C`). Two consequences: an exact
byte-window search *under-reports* residency on any fixed-up page, so a
"NOT FOUND in RAM" result there is not evidence of absence; and a static
operand cannot be read as an address without adding the same base.
One capture's `+0x13EEDC` value is a valid sample, not a fixed address
contract. A fresh builder-output run placed the same code windows at
`0x1C296B` and `0x1CDC7F`, respectively, with delta `+0x12EEDC`; DOS/4GW
placement is allocation-dependent and must be calibrated per boot.

The loader/runtime path opens `C:\INDYCAR\INDYCAR.EXE` itself, then
`controls.cfg`, `a32sbfm.dll`, `a32sbdg.dll`, and `calib.val`. A fixed `0x30`
byte read is issued for `calib.val`; the supplied floppy-derived install tree
does not contain that generated first-run file.
