# `WC.EXE` — static identity (Phase 0)

Target: `release/WC1DATA/WC.EXE` — **302,384 bytes (0x49D30)**. The DOS game
executable of *Wing Commander* (1990, Origin Systems).

**Status: behavioural authority; static reconnaissance incomplete.** The
hashed 1990 DOS binary and its captured execution decide every ported-function
contract. `../wc1-re` is readable, graded supporting evidence for a different
(1996 Win32) build; it may guide investigation but cannot settle an ambiguity
or override DOS. This document starts the binary evidence needed by the
function records; extend it with disassembly and DOS captures as each record
requires, so the next person does not repeat the header work.

## 1. Identity (verified)

- **16-bit DOS MZ executable**, Borland **Turbo C++ (1990)** — CRT string at
  file `0x12EC4`: `Turbo C++ - Copyright 1990 Borland Intl.`, immediately
  followed by the classic Borland `Null pointer assignment` / `Divi…` CRT
  message block.
- `0x30FB` at file `0x1E` and `0x726A` at file `0x20` — the Borland linker
  signature. **Byte-identical to `UW.EXE`** in the sibling `F030Underworld`
  project, which carries the same CRT string at its own `0x5F2F4`.
- Only two `MZ` occurrences in the whole file (`0x0` and `0x90CD`; the latter
  is incidental data, not a second header).
- Disassembly mode would be **16-bit x86**, Borland CRT entry chain — the same
  model `F030Underworld` established for `UW.EXE`.

## 2. MZ header (raw bytes verified @ file 0x00–0x3F)

Raw: `4d 5a 80 00 03 01 5b 04 20 01 00 00 ff ff 20 1f | 80 00 00 00 00 00 00
00 3e 00 00 00 01 00 fb 30 6a 72 00 00 …`

| off | field | value | note |
|---|---|---|---|
| 0x00 | e_magic | `MZ` | |
| 0x02 | e_cblp | 0x0080 (128) | < 512 ✓ |
| 0x04 | e_cp | 0x0103 (259) | pages |
| 0x06 | e_crlc | 0x045B (1,115) | reloc entries |
| 0x08 | e_cparhdr | 0x0120 (288 par) | header = 4,608 B (0x1200) |
| 0x0A | e_minalloc | 0x0000 | |
| 0x0C | e_maxalloc | 0xFFFF | takes all available memory |
| 0x0E | e_ss | 0x1F20 | initial SS (relative) |
| 0x10 | e_sp | 0x0080 | |
| 0x12 | e_csum | 0x0000 | |
| 0x14 | **e_ip** | **0x0000** | entry IP |
| 0x16 | e_cs | 0x0000 | entry CS (relative) |
| 0x18 | e_lfarlc | 0x003E | reloc table @ file 0x3E |
| 0x1A | e_ovno | 0x0000 | root module |
| 0x1E | — | 0x30FB | Borland signature |
| 0x20 | — | 0x726A | Borland signature |

Entry **CS:IP = 0000:0000** relative to the load base, i.e. the first byte of
the load module at **file offset 0x1200**.

## 3. Load model — overlaid (verified), unlike `UW.EXE`

Sanity: `(e_cp − 1) × 512 + e_cblp = 258 × 512 + 128 = 132,224 B (0x20480)` —
the image the DOS loader maps. Minus the 4,608-byte header, the load module is
**127,616 B**.

The file then continues for another **170,160 B (0x298B0)**, from file
`0x20480` to `0x49D30`.

That tail is the **VROOM overlay payload**, not a self-loaded contiguous
extension:

- `Runtime overlay error` at file `0x1440` — inside the load module, i.e. the
  root module's own overlay manager error path.
- `Expanded Memory fully used.` at file `0x15D82`, alongside `Origin-FX
  drivers` — the game moves resources and overlays through EMS when present.
- **910 `INT 3Fh` stubs (`CD 3F`)**, every one of them inside the load module
  and **none in the tail** — the Borland **VROOM** overlay signature. The root
  module calls overlaid routines through those stubs; the overlay manager
  patches each site as it faults the segment in from the appended payload.

> **Do not carry the `UW.EXE` model across.** `F030Underworld` concluded that
> UW.EXE self-loads its 141 KB tail contiguously at `0x10000 + file_off` and
> analyses it as one flat `CODE_TAIL` block. WC.EXE must not be mapped that
> way: same compiler, same linker, but the tail is a **swapped overlay pool**
> whose segments only make sense once the overlay table is read. Loading it
> flat would produce plausible-looking nonsense. Overlay table layout: **TBD**.

## 4. Verified strings (file offsets)

| offset | string |
|---|---|
| `0x01440` | `Runtime overlay error` |
| `0x12EC4` | `Turbo C++ - Copyright 1990 Borland Intl.` |
| `0x12FBB` | `Original FMem %lu.  Current FMem %lu.  Current NMem %u.` |
| `0x1302A` | `Original FMem %s.` … `gamedat` … `Loading WING COMMANDER.  Please` |
| `0x13070` | `Origin` / `Version %s.` / `Pre animation: %lu.` / `Post animation: %lu` |
| `0x1330B` | `Origin Systems' service line.  We are sorry for the inconven…` |
| `0x157AF` | `OriginFX Graphic System` / `Chris Roberts` / `John Miles` |
| `0x157E0` | `OriginFX Sound System` / `by` / `Herman Miller` / `Artwork` / `Denis Loubet` |
| `0x15D82` | `Origin-FX drivers` / `Expanded Memory fully used.` / `Full` / `Limited` |

`gamedat` and the `FMem`/`NMem` diagnostics confirm a far/near heap split and
a data directory concept, both consistent with the reconstruction.

<a id="title-sequence-strings"></a>
### Title_Sequence() strings (verified 2026-10-14)

`Title_Sequence()`'s opening subtitle and its eleven credits are data in
DGROUP, reached through near pointers:

| what | where | evidence |
|---|---|---|
| DGROUP | segment `0x11CC`, DS:0000 = file `0x12EC0` | C0 entry at CS:0000 (file `0x1200`): `BA CC 11` `mov dx,11CCh`, then `2E 89 16 3E 02` `mov cs:[023Eh],dx`; DS:0004 is the Borland copyright at file `0x12EC4` |
| opening subtitle pointer | DS:264E (file `0x1550E`) = `0x27BB` | the overlay pushes it at file `0x3C608`: `FF 36 4E 26` `push word [264E]` |
| credit pointer table | DS:2767 (file `0x15627`), 11 words, `0x27F7`..`0x2A5D` | the overlay reads it at file `0x3C72E`: `D1 E3` `shl bx,1`, then at `0x3C730` `FF B7 67 27` `push word [bx+2767]` |
| the twelve strings | DS:27BB..DS:2A76, 700 bytes with their NULs | contiguous, in pointer order |

Both reads sit in the VROOM overlay payload (§3), in one routine. Line counts
per string (opening, then credits 1..11): 2, 3, 7, 6, 7, 3, 6, 5, 2, 1, 2, 2.

The 1990 strings are **not** wc1-re's 1996 ones: the software-engineers
credit has no trailing newline, and the OriginFX Graphic System credit has no
"by" line. The Falcon port transcribed the 1996 text until 2026-10-14; it now
reads these bytes from the player's `WC.EXE` at title load
(`src/resources.c` `load_intro_strings`), so the repository carries no copy.
`tools/resource_loader_smoke.c` checks the twelve loaded strings against an
FNV-1a over the DOS bytes (`0x20116327`) and the line counts above; pointing
the table one word off fails it.

## 5. Open questions

1. **Overlay table layout** — where the root module records overlay segment,
   file offset and size. Two entry points: the code around the
   `Runtime overlay error` string at `0x1440`, and the `INT 3Fh` stub sites
   (each is `CD 3F` followed by the overlay/entry operands VROOM patches).
2. **Which subsystems live in overlays** — likely the non-flight rooms
   (briefing, rec room, talking heads), matching the resources still
   unported. Would tell the port which DOS code paths are mutually exclusive.
3. **EMS policy** — `Full` / `Limited` at `0x15D82` suggests at least two
   memory configurations. The port already hits this: DOS only loads the
   alternate asteroid set (`OBJECTS.VGA` section 17) on the expanded-memory
   configuration, so the Falcon deliberately uses sections 13 and 16 only.

None of these block the port. Open them only when the reconstruction is
ambiguous about behaviour the Falcon slice actually needs.
