# Project: Ultima Underworld 2 (1993, Origin) — Decode, Disassemble + Prove, Understand, Port

**Goal:** fully analyze the DOS game *Ultima Underworld II: Labyrinth of Worlds
(1993)* — code and data — and port its observable behaviour to the Atari
Falcon030. Byte-exact reconstruction remains a proof technique for recovered
encodings rather than the definition of port fidelity.

UW2 is the **same engine family as UW1** (`../F030Underworld`), which is
the mature sibling project. Almost everything it learned applies here directly:
check its findings against UW2 before decoding anything from scratch.

## Mandatory function-level port policy

The hashed shipped DOS executable and its captured execution are the sole
behavioural authority. Reassembly, decompiler output, a recovered source tree,
the browser reference, and 68000 code are evidence or implementations; none
may overrule DOS. For every function represented in browser or target code,
maintain the `METHOD.md` §4.2 function record: DOS identity and evidence,
recovered contract and fixtures, browser/target symbols, and an explicit
difference ledger against DOS. Record and prove even “no difference”; an
unresolved difference is `Unproven` and cannot enter a supported path. Start
the deterministic browser game runtime with the first function; the page itself
must boot and run the game path. Use its controlled experiments to identify
function roles, contracts, side effects and Falcon seams, then confirm each
finding against DOS before recording it. Asset viewers and fixture panels are
diagnostic overlays only. Land its fixtures before or with each supported
target slice. The connected browser game path must reach UW2's real startup
flow—main menu or deterministic attract mode—with all functions already marked
supported; isolated function pages do not count.

Input I/O is a mandatory emulation boundary, not a second authority. A browser,
host, or Falcon input layer must translate physical pointer/keyboard data into
the recovered DOS keyboard or pointing-device driver contract, then let the
authoritative DOS function consume and return that driver-visible state. It
must preserve the proven data widths, units, button/key transitions, queues,
polling/acknowledgement semantics, ordering and relevant error results. It
must not call menu helpers directly, inject state, synthesize game actions,
invent game transitions, bypass an unported function, or improve the
DOS-authoritative flow. The exact driver contract is recovered from this DOS
build; it is never guessed from a browser API.

Any convenience input that DOS does not provide—such as keyboard navigation
for a mouse-only DOS menu—is a browser/test-harness difference only. It must be
labelled in the function record, excluded from the supported game-flow fixture,
and unable to change supported game state. If the keyboard driver contract is
not yet recovered, keyboard game input remains `Unproven` and is not replaced
by direct arrow/Enter logic. Graphics and sound are the explicit target
hardware exceptions: their Canvas/Videl/audio mechanisms may differ after the
logical contracts are recovered, but they may not change input-driven game
flow or state.

Timing is an equally mandatory part of the authoritative flow. Preserve the
DOS timer/input/frame ordering and measured cadence wherever it affects state,
animation, audio, races, or polling. UW2's recovered timer module installs an
`INT 8` PIT scheduler with a runtime divisor, drift-free timer-slot
accumulators, and runtime slot periods; those values must come from DOS
oracle captures or replay fixtures. Do not substitute browser
`requestAnimationFrame`, host timers, a monitor refresh specification, or an
assumed 60 Hz for the DOS game tick. A 60 Hz Falcon/Videl presentation target
is only a display target. Until the DOS cadence and its display relationship
are measured, the timing path is `Unproven`; a fixture cadence may keep the
diagnostic browser page watchable but must not be called DOS game-flow parity.

Function-level JavaScript must stay as close to the recovered DOS function as
possible. Do not add `throw` paths, assertions, validation, clamps, defaults,
retries, logging branches, or other defensive behaviour that the DOS function
does not contain. Preserve fall-through, returns, widths, wrapping, side
effects, ordering, and known unsupported-input behaviour; mark an unknown case
`Unproven` instead of improving it. Assertions and error reports belong in
build/fixture/parity harnesses. Necessary host or target boundary checks must
be outside the semantic function, labelled `Target artefact`, and must not
change valid DOS results. The durable record is
`analysis/functions/translation-policy.md`.
## Implementation-source links

Every JavaScript/browser and 68000/m68k function source that implements or exposes a recovered DOS function must carry an adjacent comment or docstring linking to the durable function record and naming the disassembled DOS function symbol plus canonical range/entry (for example, `DOS: FUN_0000_1234; record: <stable-function-record>`). Use the same stable function ID in both implementation sources; a separate map or file-level comment is not enough. Code with no DOS counterpart must say `N/A - platform replacement` or `Target artefact` at the definition.


**68000 output is never guessed.** `m68k` is not a sufficient target
declaration: every target routine must name the exact CPU (here MC68030 when
using Falcon030-specific features), assembler/compiler and version, syntax,
ABI/calling convention, memory/alignment and privilege assumptions, and output
format. The declared toolchain must be CPU-restricted and reject unsupported
instructions/addressing modes. Retain the source, build configuration or
command, object/binary hash, and assembler listing/disassembly. Before a
routine is called a 68000 counterpart, run its contract fixtures in the
declared emulator or on the Falcon and compare canonical outputs and side
effects. An unassembled hand-written snippet is `Illustrative`, not `Ported`
or `Verified`, and cannot enter a supported target path. A passing JavaScript
fixture proves the contract boundary, not m68k instruction legality or target
execution. Shared code targets the lowest declared CPU; MC68030-specific
extensions belong only in the Falcon target seam with their fallback boundary
recorded.

## Workspace

| Path | Content |
|---|---|
| `assets/UW2_Disk1..5.zip` | Source ROMs (5× 3.5″ DOS disks). **Never modify.** |
| `game/Disk1..5/` | Extracted game disks (pristine reference copies). **Keep pristine.** |
| `work/extracted/D1..D5/` | LZH-expanded game data, per source disk. Derived — the disassembly target. |
| `work/` | Scripts, sweeps, modified copies for testing. |
| `img/` | `uw2.hdd` (+ `.geom.json`) — bootable DOS 6.22 + UW2 disk, **works**; genuine DOS 6.22 install floppies. See `analysis/qemu-boot.md`. |
| `analysis/` | Notes, dumps, format docs (`analysis/<topic>.md`). |
| `PORTING.md` | **The plan** — phase status against `../F030Method/METHOD.md`, what is out of order, order of work. |

## Conventions

- `game/` is the untouched reference; all patched/reassembled variants live in `work/`.
- One doc per format/component in `analysis/`; verified header bytes must be
  quoted, not guessed.
- **Update the docs as you work:** every new finding (format, tool quirk,
  workflow, next steps) goes into the right `analysis/*.md` (or `AGENTS.md`
  §Next steps) immediately — never leave results only in the chat log.
- **Mark status explicitly:** every finding carries `RESOLVED` / `PARTIALLY
  RESOLVED` / `IDENTIFIED` / `TBD`, and a resolved item records its invariant(s)
  and verification scope (which files, how many checked). Corrections stay in the
  doc, dated, with the old (wrong) reading quoted. *(Convention borrowed from the
  TIE project — adopt it from day one rather than retrofitting it.)*
- **Techniques shared by the thirteen projects in the `../F030Method/README.md`
  manifest live in [`analysis/cross-project.md`](analysis/cross-project.md)**.
  Read it before inventing a method. It is generated
  by `../F030Method/gen_cross_project.py` — edit the body there so all copies
  stay in sync, and upstream transferable findings from here the same way.
  The parent repo also holds the authoritative `METHOD.md` Decode →
  Disassemble + Prove → Understand → Port playbook and the master
  DOS-oracle harness (`dos/`, with `sync.py`).
- Verify reassembled output byte-for-byte against `work/extracted/`.

## `UW2.EXE` (675,968 B = 0xA5080, 16-bit Borland Turbo C++ 1990)

`work/extracted/D3/UW2.EXE` — the only root-level file the install produces.
Everything in this section is measured from the file, not inferred; regenerate
with `python work/mz_audit.py work/extracted/D3/UW2.EXE`.

### MZ header — RESOLVED

Raw bytes, file `0x00..0x1F`:

```
00000000  4d 5a 80 01 8e 03 f9 0a  e0 02 00 00 ff ff d0 6e  |MZ.............n|
00000010  80 00 00 00 00 00 72 0e  3e 00 00 00 01 00 fb 30  |......r.>......0|
```

| off | field | value | note |
|---|---|---|---|
| 0x00 | e_magic | `4d 5a` = `MZ` | |
| 0x02 | e_cblp | 0x0180 (384) | bytes used on the last page |
| 0x04 | e_cp | 0x038E (910) | pages, header included |
| 0x06 | e_crlc | 0x0AF9 (2,809) | relocation entries |
| 0x08 | e_cparhdr | 0x02E0 (736 par) | header = **0x2E00 B** |
| 0x0A | e_minalloc | 0x0000 | |
| 0x0C | e_maxalloc | 0xFFFF | wants all of memory |
| 0x0E | e_ss | 0x6ED0 | |
| 0x10 | e_sp | 0x0080 | |
| 0x12 | e_csum | 0x0000 | |
| 0x14 | **e_ip** | **0x0000** | ← 0x14 is `e_ip`, 0x16 is `e_cs`, *in that order* |
| 0x16 | **e_cs** | **0x0E72** | |
| 0x18 | e_lfarlc | 0x003E | reloc table @ file 0x3E |
| 0x1A | e_ovno | 0x0000 | no *DOS-loader* overlays (the `FBOV` pool is Borland's own) |

There is **no `e_lfanew` in this file.** `e_lfarlc = 0x3E`, so the relocation
table *starts before* the word a PE would put at 0x3C: file `0x3C..0x3D` is the
tail of the reserved area (`00 00`) and `0x3E..0x3F` (`01 00`) is the offset
word of relocation entry 0. Read as a u32 those four bytes give `0x00010000` —
which is exactly the value UW1's doc reported as "`e_lfanew = 0x10000`, Borland
junk". ✗ Withdrawn (same mistake in both docs, corrected 2026-08-20): it is
relocation data, and a real-mode MZ has no `e_lfanew` at all.

| quantity | formula | value |
|---|---|---|
| header size | `e_cparhdr*16` | `0x2E00` |
| image size = end of the DOS-mapped image | `(e_cp-1)*512 + e_cblp` | `0x71B80` |
| entry point | `hdr + (e_cs<<4) + e_ip` | **`0x11520`** |
| stack top | `hdr + (e_ss<<4) + e_sp` | `0x71B80` |
| DGROUP | `hdr + (dgroup<<4)`, `dgroup = 0x6608` | **`0x68E80`** |

`e_ss:e_sp` lands *exactly* on the image end, and the `FBOV` signature sits
*exactly* there too, so three independent readings agree on `0x71B80`. UW1 has
the same three-way agreement at its own `0x66B30`, which is what makes this
arithmetic safe to trust.

### Entry point = Borland `C0.ASM` startup — RESOLVED

File `0x11520` (`ndisasm -b 16 -o 0x11520`, cross-checked with capstone
`CS_MODE_16`):

```
011520  BA0866            mov dx,0x6608          ; DGROUP
011523  2E89164502        mov [cs:0x245],dx
011528  B430              mov ah,0x30
01152A  CD21              int 0x21               ; DOS get-version
01152C  8B2E0200          mov bp,[0x2]
011530  8B1E2C00          mov bx,[0x2c]          ; PSP environment segment
011534  8EDA              mov ds,dx
011536  A39400            mov [0x94],ax
```

Byte-for-byte the shape UW1 has at *its* entry `0x11E50` (`mov dx,0x5C0F`) and
`UWSOUND.EXE` at `0x400` (`mov dx,0x0465`) — the same `C0.ASM`, three times.

**Relocation entry 0 is `(offset 0x0001, segment 0x0E72)` → file `0x11521`**,
i.e. the immediate of that first `mov dx`. So the static DGROUP segment is
readable straight out of the file and `DGROUP = e_cparhdr*16 + (dgroup<<4)`.

### Relocation table — RESOLVED

2,809 entries × 4 B at file `0x3E..0x2C22`; format is the **standard DOS
`(offset u16, segment u16)`** — there is no Borland variant. Header slack
`0x2C22..0x2E00` (478 B) is all zero. Every target is unique and inside the
mapped image (`0x2E0A..0x6B08E` ⊂ `0x2E00..0x71B80`): **2,809 of 2,809 valid,
0 out of range.** The 53 distinct segments are the linker's 64 KB frames.

✗ **Withdrawn** (inherited from UW1, corrected 2026-08-20): "*format: standard
DOS `(page u16, offset u8, pad u8=0x0E)`; the first ~700 entries are valid, the
remainder contain out-of-range pages (Borland-specific extension or a second
table)*". Reading the leading u16 as a *page* is what manufactured that: 2,072
of UW2's 2,809 leading words exceed `e_cp` (2,474 of UW1's 3,176, leaving the
702 that were called "the first ~700 valid"), because they are **offsets**, not
pages. Consequence for Ghidra: the stock experimental MZ loader really does
crash on these binaries, but not on out-of-range entries — there are none. The
only candidate left in the table is the **38 entries in frame `0x0000`**
(targets `0x2E0A`, `0x2E0E`, `0x2E2D`, …; UW1 has 38 too), which is a deduction
from the table, not a measurement of the loader — **TBD** until the stock loader
is re-run and its trace read.

### Address mapping — one table, one worked check

`L` = DOS load segment (PSP+0x10; varies per run — UW1 measured `0x0596`).

| from | to | formula |
|---|---|---|
| file `F` ∈ `0x2E00..0x71B80` | real-mode linear | `(L<<4) + F − 0x2E00` |
| file `F` ≥ `0x68E80` | `DGROUP:off` | `off = F − 0x68E80` |
| file `F` ∈ `0x2E00..0x71B80` | Ghidra address | `F + 0xD200` (= `0x10000 − e_cparhdr*16`) — **RESOLVED**, confirmed against the DGROUP CRT-string offset, `analysis/ghidra.md` §3 |
| file `F` < `0x2E00` | — | header; not mapped by anything |
| file `F` ≥ `0x71B80` | — | **no fixed mapping exists** (overlay pool, below) |

Worked check: DGROUP is derived from the *code* (the `mov dx,0x6608` immediate
that reloc 0 patches), and the first thing at the address it predicts is the CRT
banner Borland puts at the head of DGROUP —

```
00068E80  27 06 00 00 00 00 00 00  54 75 72 62 6f 20 43 2b  |'.......Turbo C+|
00068E90  2b 20 2d 20 43 6f 70 79  72 69 67 68 74 20 31 39  |+ - Copyright 19|
```

so file `0x68E88` = `DGROUP:0008` = `Turbo C++ - Copyright 1990 Borland Intl.` ✓
(the displacement is *not* a constant across binaries — UW1 and `UWSOUND.EXE`
carry it at DGROUP+4; search for the string and subtract). Two more that land:
`Out of Low Memory.$` = `DGROUP:13A4` (file `0x6A224`), `Out of EMS Memory.$` =
`DGROUP:13B8` (file `0x6A238`).

### The rest

- CRT string `Turbo C++ - Copyright 1990 Borland Intl.` at file `0x68E88` —
  **same compiler as UW1**, so disassemble as 16-bit x86.
- **Same shape as UW1 — and, like UW1, it is not a self-load: the tail is a
  Borland `FBOV` overlay pool** (verified in the file, 2026-08-20). The DOS
  loader maps only the `e_cp`-page image; the tail is the overlay pool:

  ```
  71B80: 46 42 4f 56 | f0 34 03 00 | 40 6b 06 00 | ae 00 00 00
         "FBOV"        ovrsize       exeinfo       segnum
         sig           0x334F0       0x66B40       174
  ```

  **`exeinfo` decoded (2026-08-22)**: it points at a **174 × 8-byte table** at
  file `0x66B40..0x670B0`, records `(u16 segment, u16, u16, u16)`, segments
  **ascending**, 159 distinct. The count matches the header's `segnum = 174`.
  It lists the **resident image segments** — `0x0085` (blitter), `0x065C` (the
  threaded engine), `0x2133`, `0x4FCE` are all present — and contains **none**
  of the small segment values that overlay code far-calls through (`0x0030`,
  `0x0098`, `0x0148`, `0x02F8`, `0x0300`, `0x0308`, `0x0338`, `0x0390`,
  `0x03B8` are all absent as *values*). ✗ **Corrected 2026-08-23**: the original
  continued "So those are a separate namespace resolved by the overlay manager
  at load time, which is why they cannot be mapped statically". The observation
  was right and the inference was wrong. Those small numbers are not segment
  values at all — they are **byte offsets into this very table**:

      seg  = u16 at 0x66B40 + V        (V a multiple of 8, V/8 < 174)
      file = 0x2E00 + (seg << 4) + off

  So `0x0030` is entry 6, `0x03B8` is entry 119, and so on. The pool **can** be
  mapped statically: 95% of its 4,269 far-call sites land on a known function
  entry, an INT 3Fh stub or a `push bp; mov bp,sp` prologue. See `ghidra.md`
  §19 and `work/ovl_resolve.py`. The `.GR` decoder callback `0x03b8:0x005c`
  resolves to file `0x67EEC`, an INT 3Fh stub with call descriptor `0x0377`.
  The pool itself has **no directory**: overlay code starts immediately at
  `0x71B90`, right after the 16-byte header.

  `ovrsize + 16 = 0x33500 = 0xA5080 − 0x71B80` exactly, i.e. the pool is file
  `0x71B80..EOF` — note that is `0x71B80`, not the `0x71B40` previously assumed —
  and `0x71B80` is the same number the image-size and stack-top arithmetic above
  produce. **174 overlay segments**, reached through **1,005 `INT 3Fh` thunks**
  (raw `CD 3F` pairs, *all* inside the mapped image, packed at a 5-byte stride
  in file **`0x670E0..0x68E80`** — ✗ corrected 2026-08-22 from "1,006 …
  `0x66AB0..0x68E80`": the pair at `0x66AB0` lies inside the **overlay
  manager's own data segment** (static `0x63BA`, file `0x669A0..0x670B0`,
  `ghidra.md` §15) and is data, not a thunk — i.e. the block immediately before DGROUP — UW1 has
  667 of them in the equivalent place, `0x5D7D0..0x5F2DF`, just below *its*
  DGROUP `0x5F2F0`). `Runtime overlay error`, the Borland overlay manager's own
  string, is at file `0x15030`. UW1 proved the same structure on the *running* game: overlays are
  swapped into a buffer above the stack at addresses that differ per load, so
  **there is no single tail→memory mapping to find**. Read UW1
  `analysis/uwexe.md` §13.3 before spending any time looking for one.
- Ghidra still wants the tail as a `CODE_TAIL` block in order to disassemble it —
  reuse UW1's loader patches (`analysis/ghidra.md` §1) rather than rebuilding
  them — but treat that block as an *overlay pool*, not as code at a fixed
  address. In particular, a runtime address that "resolves" to a `CODE_TAIL`
  function name proves nothing: the functions tile the region, so every address
  in it resolves. Match the bytes back into the file instead.
- ⚠ Ghidra's image base is **not** `0x10000 + file offset` — the `e_cparhdr`
  header is not mapped, so the skew is `0x10000 − e_cparhdr*16` (UW1 `0xCE00`,
  UW2 `0xD200`; the mapping table above is the one place to read it from).
  **RESOLVED** (2026-08-21): confirmed on import — `0x68E80 + 0xD200 = 0x76080`
  = seg `7608:0000`, and Ghidra's own block list has `CODE_742` starting at
  exactly that address, derived independently from the relocation table. The
  wrong skew produces well-formed wrong function names for every address. UW1
  `analysis/uwexe.md` §8, this project's `analysis/ghidra.md` §3.
- Uses **EMS**, not XMS: `EMMXXXX0` appears twice (file `0x39B69` in code,
  `0x68F96` = `DGROUP:0116`) alongside `Out of EMS Memory.$` and
  `Out of Low Memory.$`.

## Distribution

Five disks, all game data LZH-packed (same scheme as UW1). Disk1 carries the
installer (`INSTALL.EXE`, `INSTALL.OLB`, `INSTALL.DAT`) and `UWSOUND.EXE`.
Archive families across the five disks: `DATA*`, `CRIT*`, `CUTN*`, `VOIC*`,
`SDFX*`, `BASE*` — note `CUTN`/`VOIC`/`SDFX` where UW1 had `CUTS`/`SOUND`.

The two side executables, for the record (`work/mz_audit.py`, 2026-08-20):

| file | size | shape |
|---|---|---|
| `game/Disk1/INSTALL.EXE` | 70,656 B | **LZEXE 0.91-packed** — `LZ91` at file `0x1C`, `e_crlc = 0`, `e_cparhdr = 2`; the real header is inside. Unpack before analysing. |
| `game/Disk1/UWSOUND.EXE` | 32,848 B | plain MZ, 187 relocs, `e_cs:e_ip = 0000:0000` → entry = header = `0x400`, and the bytes there are the same Borland `C0.ASM` (`ba 65 04 2e 89 16 45 02 b4 30 cd 21`, DGROUP `0x0465`). No `FBOV`; it has a 10,736 B tail past its `0x5660` image end that is **not yet identified — TBD**. |

**The five expanded trees merge with zero collisions** (verified: 305 unique
guest paths → `DATA/`, `CRIT/`, `CUTS/`, `SOUND/` plus `UW2.EXE` from D3), so
merging them is a faithful stand-in for running `INSTALL.EXE`. All 305 names are
already 8.3-clean.

## Toolchain

Identical to UW1 — see its `AGENTS.md` for the full table. In short: Ghidra
12.1.3 + GhidraDosToolbox (16-bit real-mode import, patched MZ loader, headless
pipeline), Python 3 + capstone, nasm/ndisasm, mtools, 7-Zip for the LZH layer,
QEMU as the headless oracle, 86Box as fallback.

Local scripts: `work/sweep16.py`, `work/sweep32.py` (function sweeps),
`work/uw2_strings.txt`, `work/mz_audit.py`, `work/lev_audit.py`,
`work/gr_render.py`, `work/tr_render.py`, `work/strings_decode.py`,
`work/cnv_audit.py`, `work/cnv_decode.py`, `work/cnv_disasm.py`,
`work/lpf_audit.py`, `work/vm2_table.py`, `work/rsp_break.py`,
`work/drive.py`.
`mz_audit.py`, `lev_audit.py`, `gr_render.py`, `tr_render.py` and
`strings_decode.py` run unchanged against UW1's equivalent files — pass the
path. `cnv_audit.py` is UW2-only: it reads this project's `UW2.EXE` overlay
code as well as the archive.

## Dynamic oracle — WORKS

`img/uw2.hdd` boots genuine MS-DOS 6.22 and runs `UW2.EXE` headless under QEMU;
the opening cutscene renders and screenshots come back over QMP.

```bash
python work/build_dos_hdd.py           # build img/uw2.hdd (+ first boot)
python work/set_boot_mode.py uw2       # pick what the image does on boot
python work/run_qemu.py --timeout 60   # run headless, screenshot on timeout
```

Config is HIMEM + `EMM386 RAM` → 618 KB conventional / 14,928 KB EMS. Full
procedure, the five boot-record invariants and the gotchas:
`analysis/qemu-boot.md`.

## The plan

**`PORTING.md` is the plan** — where this project stands against METHOD.md's
four phases, what is out of order, and the order of work. Read it before
picking up anything below.

The short version: the data side is the deepest in the family, the code side's
byte-exact rebuild and whole-file code/data classification are now
**RESOLVED** (`analysis/reassembly.md`), and the port has its first
target-neutral pixel seam but no target backend/build. The next critical-path
items are semantic function/VM recovery and the unresolved `PANELS.GR` record
3; standard `.GR` archive emission and type `0x08` record encoding are now
proven.

## Findings log

What follows is the record, not the plan: each entry is a finding with its
evidence and date, kept in the order it was learned. Most are DONE. The
still-open ones are collected and sequenced in `PORTING.md` rather than left
to be spotted in here.

1. **Static disassembly of `UW2.EXE`** — **DONE** (2026-08-21): imported with
   UW1's patched loader, the 210 KB tail landed in `CODE_TAIL` as expected,
   exports written to `work/ghidra_export/`. Full writeup, the verified
   address model, and one identified-but-narrow relocation-application gap
   (4 merged linker frames, listed by name): `analysis/ghidra.md`. Next here
   is a semantic pass (name functions, find `main`/game loop) — not started.
2. **Diff the formats against UW1 before decoding them.** UW1's
   `analysis/data-formats.md` already resolves LEV.ARK's container and its
   3×63×63 attribute grids and the LPF/ANIM cutscene header, and has partial
   readings of STRINGS.PAK, `.GR`, `.TR` and `CNV.ARK`. Confirm-or-diff is far
   cheaper than starting over; record which UW1 invariants hold for UW2 and
   which do not.
   - **`LEV.ARK`: DONE** (2026-08-21, this project's own
     `analysis/data-formats.md`). The container *shape* (header + variable
     record stream + data pool) holds; the *contents* mostly don't — no
     `0x7C08` 63×63 grids anywhere in UW2's file, a different variable-size
     blob layout with its own embedded index table instead, 3 new record ids
     UW1 doesn't have, and a 1,204 B trailing text blob (level names +
     lore-like prose, likely compressed) that UW1's file doesn't carry at
     all. Don't port UW1's grid-semantics work forward without new evidence.
   - **`.GR` / `.TR`: DONE** (2026-08-21) — both carry over from UW1 and are
     render-verified; see `analysis/data-formats.md`.
   - **`STRINGS.PAK`: DONE** (2026-08-22, `analysis/data-formats.md`). Fully
     decoded, for **both** games: a 181-node Huffman tree (`u8 char, parent,
     left, right`; `0xFF/0xFF` = leaf, last node = root), a `(u16 id, u32
     offset)` block table, and per block a `u16` count + `u16` per-string
     byte offsets + an MSB-first bitstream terminated by `'|'`. 13,166 UW2
     strings (10,984 UW1) decode with **zero** malformed and **zero** bytes
     unaccounted for — the last string ends exactly on EOF in both files.
     Tool: `python work/strings_decode.py [path] [--dump out.txt]`. Corrects
     three claims in UW1's own doc (it read the Huffman node table as a
     hash/index table) — UW1's `STRINGS.PAK` section should be updated from
     PARTIALLY RESOLVED to RESOLVED from here.
   - **`CNV.ARK`: container DONE, record grammar still TBD** (2026-08-22).
     UW1's `(u16 offset, u16 id)` pair reading is withdrawn — it is a flat
     `u32LE[320]` offset table (UW1: 97 records, pool starts exactly at the
     table end). UW2 adds three more parallel `u32[320]` arrays (a `3`/`0`/`1`
     slot flag and the record size, stored twice); its 102 records **tile the
     data pool with zero slack**. Conversation slots cross-check against
     `STRINGS.PAK`: `CNV` index `i` ↔ string block `0x0E00 + i − 1`, all 102
     matched.
   - **`CNV.ARK` follow-up** (2026-08-22, same doc): the conversation VM's
     **51 builtins are recovered by name** out of `UW2.EXE` — one contiguous
     run of 51 `PUSH seg / PUSH off / PUSH name / CALLF` sites at file
     `0x7C39B`, right after the code that opens `DATA\cnv.ark`; that call
     target has exactly 51 sites in the whole file, so the table is complete.
     They are the other end of the identifier strings UW1 found *inside*
     `CNV.ARK` and could not explain. The `(seg, off)` argument is a far
     pointer into the `INT 3Fh` overlay thunk table (all 51 offsets ≡ 2 mod 5,
     the thunk stride; 33/51 land exactly on a `CD 3F` against a null of
     0.10/51) — IDENTIFIED, base not statically pinnable. Also: **UW2's
     records are LZSS-compressed where UW1's are plain**, and the byte at
     record `+0x0F` is the conversation id in all 102 records.
     Tool: `python work/cnv_audit.py`. *(Superseded in part by the next
     bullet: the "stream starts at `+0x0E`" reading recorded here was wrong —
     it starts at `+0x04` — and the match encoding is now solved.)*
   - **`CNV.ARK` record body: DONE** (2026-08-22). The compression *is* LZSS
     (Okumura, N=4096/F=18/THRESHOLD=2, ring zero-filled, cursor at N−F, flag
     low-bit-first) and **the stream starts at record `+0x04`**, not `+0x0E`
     as first assumed — `+0x00` is the uncompressed length. The record layout
     was read off the parser at `0x75863` rather than guessed: skipped u32,
     code size in words, u16, **`STRINGS.PAK` block id**, memory size in
     words, import count, import records, then `code_words*2` bytes of
     bytecode. Four invariants hold 102/102, including "the record tiles
     exactly" and "the header's block id equals `0x0E00 + slot − 1`". The 94
     imports split into 63 functions (51 = the EXE table above, 9 = the
     second DGROUP group) and 31 game-state variables, each densely numbered.
     Tool: `python work/cnv_decode.py`.
   - **Conversation bytecode: DONE** (2026-08-22, `analysis/ghidra.md` §11).
     `FUN@0x75A95` is a 42-opcode stack VM (IP `[0x471a]`, SP `[0x46fa]`,
     dispatch `jmp cs:[bx*2+0x187b]`), and it is **not** the threaded-code
     engine of §§8–10 — **UW2 runs two separate bytecode VMs**. The jump table
     is at file `0x75E1B`; its segment base `0x745A0` was found by requiring
     all 42 targets to land inside the interpreter, which has exactly one
     solution. All 102 conversations disassemble to exactly `code_words`, and
     all 3,485 `calli` operands resolve to a declared function import — so
     bytecode operand, import slot, the register routine's `index*4` store and
     the EXE registration table all agree. Tool: `work/cnv_disasm.py`.
   - **All 42 conversation opcodes decoded** (2026-08-22, `ghidra.md` §11):
     arithmetic (`add mul sub div mod neg`), logic (`and or not`), the six
     comparisons, control flow (`jmp beq bne bra call calli ret halt`), stack
     and frame (`pushi pusha drop swap pushbp popbp setbp setsp alloc`),
     memory (`fetch store addm1`), the `[0x4708]` result register
     (`setres getres`), and three string ops (`streq say respond`). Two
     findings beyond the table: `[0x4708]` is the builtin-call **return
     register** (the `calli` helper writes it), and **strings never appear in
     the bytecode** — `say`/`respond`/`streq` take a `STRINGS.PAK` **id**,
     fetch it with the game's string loader and run it through the
     `@`-substitution expander at `0x754F6`. Disassembled output reads as a
     textbook compiled frame.
   - **LPF/ANIM cutscene containers and intro frame payload: DONE**
     (2026-08-25). 39 files. The `0x80` header and 256-entry large-page
     directory at `0x0500` (`{u16 baseRecord, nRecords, nBytes}`), pages at
     `0x0B00 + k*0x10000`, and non-record-order directory mapping are
     measured. The four whole-page accounting anomalies remain explicitly
     unexplained. The `0x100..0x4ff` palette is 256 `B,G,R,0` entries; record
     payloads are persistent 320×200 indexed ANIM deltas with literal, short
     run, skip, long skip/run/dump and end operations. Empty records repeat the
     previous frame. `CS000.N01`, `CS000.N12`, and `CS000.N02` are checked
     source/palette/page/record/every-frame fixtures by
     `work/cutscene_export.py --check` and `analysis/cutscene-fixtures.json`.
     Separately, cutscene filenames are built in **octal** (`FUN@0x811FC`,
     3-bit digit groups), which is why the shipped set has `CS040`/`CS403` and
     `.N10`–`.N15`. Tools: `work/lpf_audit.py` for container accounting and
     `work/cutscene_export.py` for the recovered frame decoder. Text, speech,
     exact timing, and the remaining unbalanced pages are still `Unproven`.
   - **The threaded-code VM's table: located and enumerated** (2026-08-22,
     `ghidra.md` §10b). It is at **file `0x54FD4`** with **exactly 111 slots**
     (not "~111"), 94 distinct targets, handlers at file `0x999D..0x114D5`
     (code base `0x93C0` — a *unique* best fit, 63/111 vs runner-up 21, and
     `(base+delta)>>4 = 0x0C31`, the segment §9 saw live). **101** NEXT
     sequences `lodsw / xchg bx,ax / jmp [bx+0x24f4]`, and every bare dispatch
     in the binary is one of them — so there is no central loop, which settles
     §8's "there may be no single flat game loop to name". Tokens are byte
     offsets (`bx` unscaled), so the stream stores `opcode*2`. Locating the
     table turns out to need **no** live input: the far-call operands carry the
     pre-relocation segment words, and `file = 0x2E00 + (seg<<4) + off` gives
     the handlers (`0x065C:0000` → `0x93C0`) and the table (`0x4FCE:0x24F4` →
     `0x54FD4`) exactly. (A first attempt claimed a live number was required;
     withdrawn in `ghidra.md` §10b, same day.) Tool: `work/vm2_table.py`.
   - **What feeds `SI`: ANSWERED** (2026-08-22, `ghidra.md` §10c) — the
     project's oldest open question, and it needed no oracle run. The VM
     segment is entered by exactly **three** far calls, all through one
     wrapper `FUN@0x250B3`, which sets `SI` from its **third argument** and
     `DS` from its fourth, after switching to a private stack. All three call
     sites compute **`SI = 0x6732 + 16 × record[3]`** — an index into 16-byte
     entries in the caller's data segment, keyed off a 4-byte record whose
     byte 0 is tested against `4`. The interpreter does not find its stream;
     it is handed one. `DS = 0x4FCE` is settled from the file (its `0x24F4`
     holds the table, 110/111 entries in range; DGROUP's is all zeros), so the
     streams sit at **file `0x59212 + 16 × index`**.
   - **Oracle run done — the `SI` formula holds, the interpretation did not**
     (2026-08-22, §10d). One breakpoint at `0x065C:0x7F0C`. Confirmed:
     `CS = 0x0C31` at `EIP = 0x7F0C` (the static address model, on real
     silicon); **`SI = 0x68A2 = 0x6732 + 16×23`**, the formula exactly; and
     the 16-byte entries **are runtime-built** (file zeros, guest populated).
     Refuted: `DS` there is **DGROUP**, not `0x4FCE` (that is the *other*
     door, `0x7F12`); `0x7F0C` is a two-instruction trampoline
     `call cs:[bx+0x6d30] / retf`, not an interpreter entry; and the data is
     **not** a token stream. **`SI` points at a 16-entry nibble→byte
     translation table**, `rep movsb`'d to `0x065C:0000` and used by `xlatb`
     in a **4bpp→8bpp expander**. So segment `0x065C` looks like a
     graphics/decoder library; the 111-slot table and 101 NEXT sites stand as
     measurements, but "VM" is downgraded to IDENTIFIED until it is clear
     which door §§8/10's live mouse-path trace came in by. New tool
     `work/rsp_break.py` (the RSP client §8 described and never committed).
   - **Segment `0x065C` characterised — fixed-point math, not blitting**
     (2026-08-22, §10e; corrects §10d's "decoder library", which was drawn
     from one handler). Census of all 101 handler bodies, 12,458 instructions:
     **5.0 % mul/div against 0.9 %** in a control slab of ordinary game code, a
     5.5× enrichment; **272** `mul`-then-take-`DX` sites, i.e. the `(a*b)>>16`
     fixed-point idiom §10 found in `FUN_1724_03ec`; and **zero** framebuffer
     (`0xA000`) references — it computes, something else draws. Only 22/100
     handlers do string/blit work and exactly one uses `xlatb`. Reading
     (inference, labelled): a fixed-point engine driven by a threaded command
     stream. *(Corrected same day: §7's "39 % of samples" histogram context is
     `CS=2708` = static **`0x2133`**, a **different** segment — it is not a
     third agreeing route.)*
   - **Corrected architecture map** (§10e): converting §7's live segment
     tallies through `static = runtime − L` puts them in order — a hot loop in
     static **`0x2133`** (39 % of in-game samples) running in the **`0x60D8`**
     private world the wrapper `FUN@0x250B3` installs, calling down into
     **`0x065C`** for arithmetic and decode primitives, with **`0x0085`**
     (`ES=0xA000`) doing the framebuffer writes — which fits `0x065C` having
     no `0xA000` reference of its own. The `0x7F0C` trampoline is a **6-entry
     API**: two stubs and four pixel-format decoder variants.
   - **`CNV.ARK`'s three unregistered function imports: RESOLVED**
     (2026-08-22). `add_event`, `do_input_wait` and `gronk_trigger` are
     declared by all 102 conversations, occur nowhere in `UW2.EXE`, and are
     **dangling** — but harmless: `FUN@0x75A12` pre-fills the whole
     function-pointer array with a default stub `0x2f8:0x00ed` before any
     registration, so an unimplemented builtin is safe by design. 18 of the 63
     function imports are never called at all; `say`/`respond` are among them,
     which independently confirms §11 (they dispatch **by name** via opcodes
     `0x27`/`0x28`, not by slot). `do_input_wait` is called exactly once, in
     conversation 47 — a developer-joke rat monologue left in the shipped
     game, i.e. test content.
   - **`CNV.ARK`'s variable imports: RESOLVED** (2026-08-22, first fruit of
     §12's string-xref pass). The 31 variable imports are bound by a
     *different* mechanism from the 63 functions: `publish(name, &value, 1)`
     via `lcall 0x2f8:0x98`, with each value recomputed inline rather than a
     pointer registered once. `FUN@0x07DD53` publishes 30, `FUN@0x0792AD`
     publishes `npc_attitude`. The partition is exact — 30/31 covered, **0**
     names published that aren't variable imports, **0** overlap with the
     function imports. `riddlecounter` is never published and the string
     appears in neither UW2.EXE nor UW1's UW.EXE: a **dangling import**.
   - **The `.ARK` container is shared — CNV, LEV, BYT, SCD** (2026-08-22,
     `analysis/data-formats.md`). Supersedes LEV.ARK's "different
     variable-size blob layout" reading. One container: `u16` slot count, then
     four parallel `u32[N]` arrays (offset / flag / size / size), records at
     `header_end + 4`. **Flag bit 1 = LZSS-compressed**, and every such record
     across all four files decodes exactly — **200/200**. Evidence for the bit:
     LEV stores 134-byte records both compressed (flag 3, ×32) and plain
     (flag 1, ×18). LEV's decompressed sizes are 32,264 ×50, 134 ×32,
     4,096 ×4. Tool: `work/ark.py`.
   - **`LEV.ARK` level records joined to the code** (2026-08-22). `[0x188c]`
     has one writer, `FUN@0x927C0`, which `malloc`s **`0x7E08` = 32,264 B** —
     exactly the decompressed size of the 50 large `LEV.ARK` records, so the
     record *is* the level buffer. Its first **16,384 B are a 64×64 grid of
     4-byte cells**, confirmed three ways: the cell-pointer function's
     arithmetic, a 4,096×4-byte copy loop (`FUN@0x927F7`, which then sets
     `[0x1890]=1`), and the data — 54 distinct values in word 0, of which
     **1,669 of 4,096 cells are `0x00F0`, UW1's documented empty sentinel**.
     UW2 uses 64×64×4 where UW1 used 63×63×8, which is why the earlier pass
     found no `0x7C08` blobs.
   - **The level buffer mapped and its object arrays decoded** (2026-08-22).
     `FUN@0x2BA41` lays the buffer out: grid at `0`, then regions at
     `+0x4000` (`0x1B00`), `+0x5B00` (`0x1800`), `+0x7300` (`0x1FA`),
     `+0x74FA` (`0x70C`), a u16 at `+0x7C06` and 512 B at `+0x7C08`.
     `FUN@0x2C2F9` gives the object model: a **10-bit index at bits 6..15** of
     a word, where **0–255 → 27-byte** entries (`mov dx,0x1b / imul`) and
     **256–1023 → 8-byte** entries (`shl ax,3`). Both regions come out exact —
     `256×27 = 0x1B00`, `768×8 = 0x1800` — so **1,024 objects, no slack**. The
     same 10-bit field in each grid cell's word 1 is a tile→object link, which
     the layout routine clears with `& 0x3F` on load (links are built at
     runtime, not stored — the file's word-1 values are all small).
   - **Object record fields: PARTIALLY RESOLVED** (2026-08-22). Harvested every
     field access in the 29 callers of `obj_ptr_from_word` with its shift/mask.
     The 8-byte common record: `+0x00` bits 0–8 / 9–11 / 15, `+0x02` bits 0–6 /
     10–12 / 13–15, and **`+0x04` and `+0x06` each carrying a 10-bit object
     link in bits 6–15** — the same "6-bit field + 10-bit link" word type used
     by `obj_ptr_from_word` and by each grid cell's word 1, in three places.
     The 9-bit field at `+0x00` is an **item id**, confirmed from outside the
     EXE: `COMOBJ.DAT` is **5,634 B = 2 + 512 × 11**, exactly 512 entries for a
     9-bit id. Open: the `0x7300`/`0x74FA`/`0x7C08` regions, the per-field
     meanings, the 19-byte mobile extension, and the grid's word-0 fields —
     for which `TERRAIN.DAT` (512 B = 256 × u16, 15 distinct values) is a
     lead, unconfirmed.
   - **Call graph rebuilt from raw bytes** (2026-08-22, `ghidra.md` §13).
     Ghidra reports `inrefs=0` for **1,044 of 2,239** functions (computed
     calls, overlay crossings); `work/callgraph.py` resolves `9A`/`E8` call
     opcodes arithmetically and recovers a caller for **363** of them.
     Candidate graph with a stated **~1.2 %** chance-hit floor, and two
     structural blind spots (INT 3Fh thunks, indirect calls). Validated: the
     eight callees it reports for `conv_load` are exactly the eight in the
     hand disassembly, nothing spurious. It immediately named `heap_alloc`
     (`0x74626`) and `heap_free` (`0x747BE`) — a **private heap, not INT 21h**,
     which matters for the port.
   - **Semantic pass seeded** (2026-08-22, `ghidra.md` §12). New
     `work/symbols.py --emit` writes `work/ghidra_export/symbols.txt` in two
     deliberately separate tiers: **17 verified names** (the conversation
     loader/parser/VM/registrar, the threaded engine's base/table/entry/decode
     API, the octal `CUTS` filename builder, and `uwhome_env_lookup` — which
     is `getenv("UWHOME")` and also references `uw.cfg` and `\SAVE0\`, the way
     in to the save machinery §6 still lists as open); and **224 functions
     annotated by the DGROUP strings they reference** (10 % of 2,239),
     emitted as comments only, because a reference is a fact but the name it
     suggests is not. Low coverage is the honest headline — 90 % of functions
     reference no string — so this seeds a semantic pass, it does not do one.
   - **§4's relocation risk checked and dismissed** (2026-08-22, `ghidra.md`
     §4b, closing the last of §6's three open boxes that was cheap to close).
     `CODE_94`/`105`/`114`/`221` contain **zero** relocation targets, so there
     was nothing that could be stale; all 2,809 targets map into a block. Two
     of §4's claims don't reproduce — its four "linker-frame segments" are not
     among the table's 53 segment values, and its proposed indexing failure
     gives 1,812/41 rather than 222/4 (marked **not reproducible**, since the
     import log isn't kept). What matters downstream is settled instead:
     Ghidra's export carries **unrelocated, file-native segment values
     uniformly** (diffed `CODE_9` against capstone — only cosmetic
     differences), which is exactly what `runtime = static + L` relies on.
   - **Driven into gameplay; the stream decodes — RESOLVED** (2026-08-22,
     §10f). `work/drive.py` scripts the full character-creation flow (mouse
     units map **1:1 to 640×400 screenshot pixels**; a click must be **held
     ~1.5 s** or UW2 never samples it). Breakpointing §8's own hop-5 address
     in the 3D view gives `DS = 0x55A3`, and **`DS:0x24F4` in guest RAM is
     byte-for-byte identical to file `0x54FD4`** — the 111-slot table is
     confirmed in memory. The live `DS:SI` **is** a token stream and decodes:
     6 instructions, 36 bytes, stopping exactly on a genuinely variable-width
     handler. My two earlier rejections were both wrong — wrong door (`0x7F0C`
     is the texture-decode trampoline) and a **word**-granular operand counter
     when the stream is **byte**-granular (handlers use `lodsb`, and consume
     through called subroutines). §§8/10's "threaded-code interpreter" reading
     is correct and §10d's downgrade is withdrawn.
   - **Possible lead on the loader, found by accident** (2026-08-21,
     `analysis/ghidra.md` §9): `FUN_1e2b_0289`, sitting right next to the
     VM dispatch table traced in item 4 below, builds a filename from
     digits derived from a register value and does real
     `DosOpenFile`/`DosReadFile` (≤32,767 B)/`DosCloseFile` calls — the
     right shape for loading a numbered level/save file. The literal
     filename template (prefix/extension) wasn't pinned down yet; needs
     either a live memory read or more static segment-tracking, not
     another guess (see §9 for exactly what's missing).
3. **Decode what UW2 adds** — `VOIC*` (speech; UW2 is the talkie-era release) and
   `SDFX*` have no UW1 counterpart.
4. **Use the oracle for the questions statics cannot answer** — **MOUSE
   BLOCKER RESOLVED, `main`/game-loop hunt reframed by a major architecture
   find** (2026-08-21). Detailed history in `analysis/qemu-boot.md`
   §"Probing the running game" and `analysis/ghidra.md` §§7–8; this entry is
   the current-status summary only.
   - **String-pool base register: RESOLVED**, same answer as UW1 — no
     separate pool, `DS` stays pinned to DGROUP throughout.
   - **Mouse: RESOLVED.** The main menu is genuinely mouse-only (static
     analysis: UW2.EXE calls only `INT 33h AX=0/3/0Bh`, nothing else exists
     to fall back to) and no real driver exists in any asset this project
     owns, so `work/mouse_driver.asm` implements exactly those three
     subfunctions from scratch against the 8042 hardware and loads by
     default in `uw2`/`shell` boot mode. Verified live end to end: drove a
     full character straight through character creation
     (`qemu-boot.md` §"Character creation, mapped end to end" has the full
     menu tree) into real 3D gameplay — first time in this project.
   - **`main`/the game loop: still open, but the search itself changed
     shape.** A live EIP histogram found the mouse-read code is the hottest
     in the game (confirming it runs every frame) and surfaced two more
     leads: an `ES=0xA000` (VGA framebuffer) segment context for the
     screen-blit routine, and a private-segment context dominating 39% of
     samples, shaped like the raycaster's inner loop. Tracing callers with
     Ghidra alone dead-ended (`inrefs=0`, indirectly-dispatched trampolines)
     and one hypothesis about the mechanism (a global handler-pointer pair)
     was tested live and **disproved** — recorded as withdrawn, not hidden.
     What actually worked: QEMU's gdbstub, enabled *live* over QMP and
     driven with a hand-rolled Python RSP client (narrower retry of
     something UW1 tried once for a different purpose and called flaky) —
     breakpoint a function's entry, read the return address straight off
     the stack, works regardless of whether the call was direct or
     computed. Walked a real, verified 5-hop call chain up from the
     mouse-read code and landed on **a threaded-code/bytecode interpreter
     dispatch loop** (`lodsw` fetch from a script stream → indirect jump
     through a table) — the mouse poll turned out to be *one opcode's
     handler* in a custom VM, not something the main loop calls directly.
     If real, there may be no single flat "game loop" function to name;
     `ghidra.md` §8 has the exact addresses/bytes. **The jump table itself
     is now confirmed two independent ways** (§9): Ghidra's own decompiler
     names one case target `caseD_0` and flags two separate indirect-call
     sites "too many branches" unprompted, both resolving to the same
     `DAT_1224_0174`-based table my own raw-byte tracing found. Still open:
     enumerate the table's real opcodes, and find what feeds `SI` — see
     item 2's new bullet above for a promising, accidentally-found lead on
     exactly that.
   - `mouse_driver.asm` and the gdbstub technique are both worth
     upstreaming to `F030Method` — UW1 hits the identical missing-driver
     wall, and narrow-scope breakpointing is a generically useful capability
     none of the sibling projects' tooling has yet.
5. **Reassembly plan**: build order (EXE + data files) and a byte-exact
   verification harness against `work/extracted/`. **Started** (2026-08-22):
   `work/rebuild.py --strings` reconstructs `STRINGS.PAK` from its decoded
   strings — node table, per-string Huffman re-encoding using codes walked out
   of the stored tree, recomputed block table — and both **UW2 (429,896 B) and
   UW1 (227,230 B) come out byte-identical**. The per-string offsets match
   without being copied, which re-proves the bit order, code assignment and
   `'|'` terminator independently of the decoder. It also caught something the
   decode-side coverage check could not: six blocks across the two games carry
   1–2 *unreferenced* trailing bytes which decode to spaces, not padding —
   carried verbatim.
   `work/rebuild.py --ark` then re-compresses every `.ARK` record with an
   independent encoder (`work/lzss_encode.py`): **200/200 round-trip** (our
   stream decompresses to identical data) and **9/200 byte-identical** to the
   shipped stream. The 9 are the records with no match-selection ambiguity, so
   they prove the encoding itself — flag order, offset/length packing, ring
   semantics — is exact, and isolate the rest to match *choice*. That choice
   is characterised: the original is **greedy-longest** (78/78 matches took
   the longest available) but its tie-breaking is **not positional** (56
   nearest vs 54 furthest of 110) — the signature of a search-tree matcher.
   Reproducing all 200 needs the original matcher, not a better policy.
   `work/rebuild.py --tr` rebuilds `T64.TR` (1,049,640 B) from its decoded
   tiles: **byte-identical**. `.GR` type `0x08` is now **RESOLVED for decoding
   and record-level encoding** (2026-08-24, `work/gr8_decode.py` +
   `work/gr8_encode.py`, `analysis/data-formats.md` §`.GR` type 8): all
   **736/736** records unpack, RLE-decode and re-encode byte-identically, with
   output lengths `w*h`, `w*h+1`, or `w*h+2` (119/452/165). Static analysis
   resolved the draw-path jump table and the record-selected auxiliary palette;
   no live breakpoint is needed. `work/gr_encode.py` now rebuilds all 34
   standard `.GR` archives byte-identically; the only remaining `.GR` gap is
   the divergent `PANELS.GR` record 3. The old pre-resolution census and
   failed draw-path hunt remain in `analysis/data-formats.md` as dated history,
   not current blockers.
   - **`UW2.EXE` ratchet and whole-file map: RESOLVED** (2026-08-24; full
     classification 2026-08-26, `analysis/reassembly.md`).
     `work/reasm/uw2reasm.py` reuses the UW1 Borland encoder/verifier with the
     UW2 `0xD200` Ghidra skew, explicit structural-data guards, UW2-local
     exact-encoding macros, FBOV fixup bounds and resolved overlay switch
     targets. One pass produces the same 675,968-byte file and SHA-256
     `b07d9fde7bfb8a44e0c75388ad1bbbcd99207841f056f711a78ea51af90ea120`.
     The final descent has 157,847 byte-exact mnemonic instructions in 3,445
     function entries, 0 forced `db` fallbacks, and 414,013 instruction-size
     bytes (413,484 unique bytes). The automated whole-file audit classifies
     all 675,968 bytes as code or explicit data/padding, with 0 unclassified
     and 0 code/guard overlaps. Semantic names, contracts and port code remain
     separate work.
   - **First target-neutral pixel slice: IDENTIFIED** (2026-08-25).
     `work/asset_export.py` emits deterministic big-endian `UW2I` caches for
     one verified type-8 `OBJECTS.GR` sprite and one `T64.TR` tile. The shared
     8-bit indexed surface contract is `src/common/indexed_surface.h`, and
     `analysis/pixel-fixtures.json` records source, logical-pixel and cache
     hashes. The mandatory browser reference is now a canvas-only DOS cutscene
     display in `browser/`: it imports only the connected cutscene files through
     the virtual DOS file boundary, renders the indexed/RGB565 display surface,
     and routes browser key events into the recovered BIOS queue. The boundary
     has a clean `Map`/`Uint8Array` memory mode and a host-only versioned
     persistent mode: IndexedDB stores bytes and localStorage stores only
     path/size/source-variant/SHA-256 metadata. The MC68030 Falcon seam in `src/target/falcon/present.s` is
     assembled under the declared CPU restriction and `make hatari-smoke` reads
     its status plus the complete 128,000-byte page; the page matches the host
     contract byte-for-byte. Physical Videl scanout and equality against a
     recovered DOS game frame remain `Unproven`.
   - **Canvas-only browser display / BIOS keyboard boundary** (2026-08-25).
     The runtime no longer exposes captured character screens, fixture buttons,
     status text, pause/restart shortcuts, fallback menus, or asset diagnostics.
     `browser/uw2-input.js` converts browser key events into BIOS AX words and
     implements `fn_24358`'s `INT 16h` check/read wrapper. No mouse driver,
     cursor/character viewer, sound path, or recovered DOS keyboard consumer is
     loaded speculatively, so browser keys cannot change game state. Character
     creation, handedness and remaining game-flow states remain outside the
     supported browser path.

## Cross-port documentation rule

When a change or investigation establishes a confirmed finding, correction,
tool/workflow lesson, or other fact that can help more than this repository,
update the authoritative shared documentation in the same session and
regenerate any derived copies. Always do this; do not leave transferable
findings only in chat, code, or generated output. Keep project-specific details
in the local canonical document and upstream the reusable rule with its
evidence, scope, and status.
