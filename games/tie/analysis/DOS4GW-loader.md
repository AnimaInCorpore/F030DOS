# P1.1 — `DOS4GW.EXE` ground truth (the DOS4G extender/loader)

Target: `game/SWTieCD/TIECD/DOS4GW.EXE` (0x40CCC = 265,420 B), copy at `work/dos4gw.exe`.
Banner @ 0x25C: **`DOS/4G  Copyright (C) Rational Systems, Inc. 1987 - 1993`**.

This is the loader for the two standard **LE** targets (`Z_TIE__.EXE`,
`DETVESA.EXE`; `TIE.EXE` turned out to be a plain 16-bit program —
2026-08-21 corrections in `DOS4G-header.md` / `P1.5-launchers.md`). The
analysis of DOS4GW *itself* below (interrupt census, env/option strings, the
two-mode layout, the D32 kernel) stands; the §Answers it once gave about the
*target's* format are withdrawn there.

## What it is

`DOS4GW` is a **two-mode extender** in one MZ file:

- **16-bit bootstrap half** (file 0x200–0x2FFFF): real-mode Watcom 16-bit
  (flat, 32-bit operand sizes) code + strings + data. Runs under DOS,
  negotiates the environment (VCPI / DPMI host / HIMEM v2+ XMS /
  DOS16M.386 VDD / VMM4G), allocates extended memory, places the *target*'s
  16-bit half at linear 0, patches thunks, then hands off.
- **32-bit "D32 kernel"** (file 0x30000–0x40CCC): 32-bit Watcom image =
  DPMI host + 32-bit app loader. Strings in it: `D32_KERNEL`,
  `SEGEXE_LOADER`, `LINEXE_LOADER`, `VMM4G`, `WATCOM program`,
  `Executing %s with initial registers:`, `WATCOM patch level .a`.
  530 functions swept (46.7% byte coverage — the rest is strings/tables/
  zero BSS): **`work/dos4gw32.txt`**.

Usage (from embedded strings, 0x3EED2+): `DOS4GW <executable.xxx>` —
the target hybrid is passed as argument. Options (env/cmdline tokens in the
same block): **verbose, fix34, crashp, autolock, qa, quiet, monout**
(`quiet` @ 0x3EED2).

Boot chain context (from `AGENTS.md`): `Z_TIE2__.EXE` execs
`dos4gw.exe` + `Z_TIE__.EXE` (args `/trebla /320`, env `DOS4GPATH`/`PATH`).

## MZ header (verified)

```
e_magic MZ  e_cblp=0x74  e_cp=0x7B  e_crlp=0x4E  e_cparhdr=0x20 (hdr 0x200 B)
e_minalloc=1 e_maxalloc=0xFFFF  e_ss=0x0121  e_sp=0x2382  e_csum=0xF7CD
e_ip=0x001E  e_cs=0x01BD   ← code segment = 0x01BD (base 0x1BD0)
e_ovno=0  e_res1=0 (0x1C-0x1F)
e_res2 (0x20-0x3B) as u32 LE: 0x00280000, 0x98C, 0x994, 0x9A0, 0x9A6, 0x9AA, 0x9AE
e_lfanew (0x3C) = 0x000009B4
```

Unlike the target hybrids (whose `e_lfanew` = 0x2A50 LE/DOS4G header),
DOS4GW's own extension is a *different, simpler* layout (no `LE` magic
anywhere in the file). The e_res2 block holds 6 u32 pointers
(0x98C…0x9AE) and e_lfanew = 0x9B4 — **all point inside the
255-entry GDT/segment template table (0x2C4–0xABC)** below, i.e. into
specific pre-built descriptor slots. Semantics: TBD (see Open).

## Extension region 0x40–0xABC (the MZ 0x200-byte header tail)

| Offset | Size | Content |
|---|---|---|
| `0x40` | 8 | u32 pair `0x0009B600, 0x0009F100` — runtime XMS addresses (Δ 0x3B00) |
| `0x48` | 4 | u32 `0x0001BD00` (= 0x1BD0 << 4, the 16-half code segment) |
| `0x4C` | 0x104 | **65× (u16 seg, u16 off) far-pointer table**. Segments: `0x01BD`×52 (base 0x1BD0), `0x07E2`×7 (base 0x7E20), `0x0000`×4, `0x00F3`, `0x0991`. Linear targets span 0x111A–0xB8D5 (16-bit half). First entry `0x01BD:0x0348` = **0x1F18 = the 16-bit entry** (below). Role: dispatch/fixup table (TBD). |
| `0x200` | 0x5C | **Loader control block**: far pointers (u16 seg,off) to runtime XMS structures — 0xD2600, 0xD8018, 0xDB218, 0xDDEBD, 0x97C64, 0x9960, 0xD600, plus `0x180000` (the D32 kernel base, below) and small u16 fields (0x48, 0x20, 0x40, 0x15, 0x18…) |
| `0x25C` | 41 | banner `DOS/4G  Copyright (C) Rational Systems, Inc. 1987 - 1993` |
| `0x2C4` | 0x800 | **255× 8-byte GDT/segment-descriptor template**: u32 pair `0x00008600, 0x00180000` (= base 0x8600 / limit 0x1800 placeholder, or seg 0x8600 → base32 0x180000 mapping — both readings open). Pre-allocated descriptor slots the loader copies to XMS and patches per segment. |

## 16-bit bootstrap (file 0x200–0x2FFFF)

Layout: data/strings 0x200–0x1BD0 (error tables, string pools), code
0x1BD0–0x2FFFF (mixed with more data; 1,755 functions swept, 81.1%
coverage — **`work/dos4gw16.txt`**).

**16-bit entry = 0x1F18** (first table entry; `0x1F19` is the first
sensible instruction — 0x1F18 is `pop ss`, so the jump target is
0x1F18-with-a-word-on-stack or 0x1F19):

```
0x1F19  mov  ax, cs
        cmp  word es:[0x0C], ax      ; PSP check
        jne  0x1F30
        mov  ax, [0x10C2]            ; install INT 0 (div-error) handler
        mov  word es:[0x0A], ax     ;   vectors into the PSP (0x0A/0x0C)
        mov  ax, [0x10C4]
        mov  word es:[0x0C], ax
0x1F30  cmp  byte [0x2F], 3         ; DOS4G flag byte in MZ header
        jb   0x1F3B
        mov  eax, [0x10F2]          ; 32-bit value when flag ≥ 3
0x1F3B  ret
```

### Interrupt model (verified by full-file byte search)

| INT | Purpose | Occurrences in DOS4GW.EXE |
|---|---|---|
| 0x43 (XMS) | | **0** — never called directly |
| 0x17 (SMM) | | **0** |
| 0x20 (VMM) | | **0** |
| 0x12 (DPMI) | | 1 (16-bit, misaligned hit @ 0x2A6CB); kernel-side DPMI calls via 0x2000 real-mode gates (TBD) |
| 0x15 (VCPI) | | 19 — the PM-mode-switch path |
| 0x21 (DOS) | | 207 |

Conclusion: extended memory is handled **through the DPMI 0x2000 real-mode
interrupt gate** (DPMI host executes `int 0x43` in RM), not by direct
INT 43h — consistent with the strings `DPMI host error (need 64K XMS)`
(0x1C7E), `cannot lock stack` (0x1C9F), `program must be built -AUTO for
DPMI` (0x1BE9).

### Environment / module / option strings (16-bit region)

- **Env var names** (tables @ 0x14823, 0x14B27, 0x14FC0):
  `D32_KERNEL`, `DOS4G_GET_APPPATH` (the "DOS4GPATH" the boot chain uses),
  `DOS4G_GETENV`, `DOS4GX_SPAWN_CMDLINE`, `EXPLOAD`/`EXP_LOADER`,
  `INIT`, `LOADER`, `UNLOAD`, `FREEMAP`, `REL`, `UNREL`, `CANLOAD`,
  `VSUPERRESIZE`, `VSUPERFREE`, `DVX_HOME_DIR`, `DVX_Process_Manager`,
  `LIBPATH32`, `LIBPATH`, `COMSPEC`, `PATH`, `DOS4GLOADER`,
  `CONFIG4G`, `SWMODE=`, `DOS16M=`.
- **Options** (0x14FD8+): `verbose`, `verb`, `skipinit`, `skipSYM`,
  `noclose`, `noignr`, `estub`; 32-bit region: `fix34`, `crashp`,
  `autolock`, `qa`, `quiet`, `monout`.
- **EXP modules** (0x148D8+): `EXPLOAD.EXP`, `4GWPRO.EXP`,
  `CONFIG4G.EXP`, `LINEXE.EXP`, `SEGEXE.EXP`, `USERERR.EXP`;
  `invalid EXP executable format` (0x14960). The D32 kernel can be
  swapped/extended via EXP files (`D32_KERNEL` env var).
- **DOS/16M support** (0x1829–0x1B76): `not a DOS/16M executable`,
  `no DOS memory for transparent segment`, `you must specify an extended
  memory range (SET DOS16M= )`, `unsupported DOS16M switchmode choice`,
  `requires DOS/16M` (0x12424), `The DOS16M.386 virtual device driver was
  never loaded` (0x1CC5), `HIMEM.SYS not version 2` (0x1D39),
  `not enough available extended memory (XMIN)`,
  `protected mode available only with 386 or 486`.
- **Loader search** (0x15078+): `Searching LIBPATH32=%s for %s%s`,
  `DOS4GLOADER.dll/.exe/.com`, `linexe`, `COMSPEC`.

## 32-bit D32 kernel (file 0x30000–0x40CCC)

- 530 functions (46.7% — strings/tables/zero regions dominate):
  **`work/dos4gw32.txt`**.
- Launch string `Executing %s with initial registers:` (0x3F0BF) +
  `CS` `DS` `E…` dump — the kernel prints initial regs then starts the
  32-bit app (matches the PEP-stack convention of the image entry stub).
- Kernel self-placement: **linear 0x180000** (u32 `0x180000` in the
  0x200 control block + the 255×(0x8600, 0x180000) template pair).
  32-bit code addresses file-offsets directly (LDT base = alloc − 0x30000
  trick); e.g. the 0x200 block's `0x0F4E03FC` = far 0x0F4E:0x03FC.
- Internal 16-bit segment tables (0x3ED37+): (0x8000, 0x0B53),
  (0x9800, 0x0B91), … — kernel's own 0x80000/0x98000-segment maps.
- `can't lock extender kernel in memory` (0x3EF50+) — kernel is XMS-locked
  after load (`autolock` option).

## Answers to `analysis/DOS4G-header.md` open items

✗ **Items 1–3 withdrawn (2026-08-21).** All three "resolved" a structure that
does not exist — the target is a standard LE module (`DOS4G-header.md`, with
each old reading quoted beside its reality). Kept for the record:

1. ~~Thunk-record taxonomy — RESOLVED: 11-byte records `[u16 type][07 10]
   [u24 target32][u16 target16]`, type ∈ {1,2,3}~~ — the bytes at 0xAD8C and
   0x26C00 are ordinary **LE fixup records** inside the one record table
   (`0x314C..0x3D7DC`). `07 10` is a record *start* (source type 7 = 32-bit
   offset; flags 0x10 = 32-bit internal target: `07 10 <srcoff u16>
   <obj u8> <toff u32>`), and the "u16 type" was the tail of the *previous*
   record's target dword — the 11-byte reading spliced one record's tail
   onto the next record's head. Both "re-alignments" of this cluster (the
   9-byte and the 11-byte reading) were wrong the same way: a stride guessed
   from a marker instead of a format decoded from the header. Full decode:
   `work/audit_fixups.py` (27,438 records, walk lands exactly on every page
   boundary).

2. ~~16-bit entry-stub pair 0x2045/0x2043 — RESOLVED (form): two
   calling-convention variants of one segment-array-builder~~ — `0x2045` and
   `0x2043` are the two **object flag words** (obj1 READABLE·EXECUTABLE·
   PRELOAD·BIG_32BIT, obj2 READABLE·WRITABLE·PRELOAD·BIG_32BIT). The
   "verified" disassembly at file 0x2085/0x2083 was real bytes inside the MZ
   stub that decode plausibly at two boundaries — a jump-into-the-middle
   reading of code that has nothing to do with entries. (A name that
   resolves is not evidence; `cross-project.md` §7.)

3. ~~Base 0x7E000 — REFINED: target-specified via the CRT immediates~~ — the
   half that was measured on *DOS4GW itself* stands: **no 0x7E00/0x7E000
   literal anywhere in DOS4GW.EXE**, and its own kernel base is 0x180000.
   The inference about the target is withdrawn: bases come from the LE
   object table (0x10000/0xC0000), applied via fixups. The measurement now
   simply *confirms* the loader has no per-target base knowledge — as a
   standard LE loader shouldn't.

4. **`dwDataSize` 0xC4/0xF4/counts — RESOLVED elsewhere (2026-08-21):** all
   standard LE header fields (`eip`, table offsets, object counts) — the
   withdrawn-readings table in `DOS4G-header.md`. Nothing to trace
   dynamically.

5. **Demand-load question — open:** no INT 13/INT 21 read-loop evidence
   yet in the kernel (would need a targeted trace of the LINEXE_LOADER
   path). Note the name: `LINEXE.EXP` / `LINEXE_LOADER` is DOS4G's **l**inear
   **exe** (LE) loader module — consistent with the corrected target format.

## Load model (synthesis)

```
DOS: EXEC DOS4GW.EXE (target as arg, env DOS4G_GET_APPPATH=…, PATH)
  16-bit bootstrap @ 0x1F19:
    - PSP/INT0-vector setup, flag check [0x2F]
    - CPU check (386+), DOS version (3.0+)
    - env: DOS16M / VMM4G / DPMI-host / plain DOS + HIMEM v2 (XMS)
    - XMS alloc: D32 kernel → 0x180000 (locked), structures @ 0x9B600/0x9F100/
      0xD2600/0xD8018/0xDB218/…; build GDT/LDT from 255-entry template
    - open target: follow e_lfanew → standard LE module (2026-08-21)
    - VCPI (INT 15h) mode switch to PM
  32-bit D32 kernel @ 0x180000 (LDT base trick):
    - DPMI host services (incl. 0x2000 RM gate → XMS/INT 21/BIOS)
    - LINEXE_LOADER ("linear exe" = LE): read object table, allocate objects
      at their bases (Z_TIE__: obj1 @ 0x10000, obj2 @ 0xC0000 + BSS), copy
      the 191 pages from data_pages_off, apply the 27,438 fixup records
    - "Executing %s with initial registers:" → jump to entry
      (obj1+0x7B4E4 = linear 0x8B4E4 for Z_TIE__)
```

(The lines this replaces — "verify DOS4GOLX hybrid, place 16-bit half @
linear 0, patch 11-byte thunks, place image @ target-fixed 0x7E000" — were
the withdrawn hybrid model; 2026-08-21.)

## Artifacts

- `work/dos4gw.exe` — copy of the extender
- `work/dos4gw16.txt` — 1,755 16-bit functions (0x1BD0–0x2FFFF, 81.1%)
- `work/dos4gw32.txt` — 530 32-bit kernel functions (0x30000–0x40CCC, 46.7%)

## Open (dynamic / next)

- GDT template semantics: base 0x8600 + limit 0x1800 (6 KB — "tstack"?)
  vs. (seg 0x8600 → base32 0x180000) mapping pairs.
- Meaning of the 65-entry (seg,off) table (dispatch? fixup list? DPMI/OS/2
  message vectors?).
- ~~Thunk type semantics~~ / ~~entry-stub variant choice~~ — **dissolved
  2026-08-21** with the hybrid model (see §Answers).
- XMS allocation sizes/order (kernel 0x180000 size? target image size + 64K?).
- DOS/16M fallback path (how a 16-bit client runs flat-16 PM without the
  D32 kernel) and the VMM4G path (DOS 5+ VMM).
- `D32_KERNEL` / EXPLOAD module swap mechanics (4GWPRO.EXP = Pro version?).
- e_res2/e_lfanew pointer table (0x98C…0x9B4 into the GDT region).
