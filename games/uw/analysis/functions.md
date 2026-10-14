# UW.EXE — semantic function naming pass (2026 session)

Status: **first pass applied, then corrected**. An initial batch of 20
renames (2026-08-19/20) landed via `work/ghidra_scripts/UWRename.java`
(verified `APPLIED 20/20`). A byte-level audit (2026-08-21) then found that
**13 of those 20 had been applied to the wrong function**: the CSV's seg:off
values were reverse-computed from real, correctly-found file-offset evidence,
but using a stale header constant (`0x2000` instead of the verified `0x3200`
— see `analysis/uwexe.md` §2/§8), which consistently landed the rename on
some other, unrelated function nearby (not the one containing the cited
evidence). Two of the DOS-wrapper rows also carried a wrong DOS-function
label independent of the address bug (`AH=0x47` is *Get Current Directory*,
not *Find First*; `AH=0x40` is *Write*, not *Close*).

A corrective pass (`work/ghidra_scripts/UWRenameFix.java`, verified
`APPLIED 24/24`) retargeted every confirmed-wrong row to its true
evidence-bearing function (found by locating the `CODE_nnn` block that
contains the cited file offset in `memory_layout.txt`, then the enclosing
Function in `functions.txt` — algebra alone is not reliable for this
direction), gave the wrongly-squatted functions an honest name where one
could be independently confirmed (`dos_deletefile`) or their default
`FUN_seg_off` name back otherwise, and withdrew 3 rows entirely where the
true evidence sits in bytes Ghidra has never disassembled/functionized, or
is otherwise genuinely ambiguous. **33 semantic names were live** before this
follow-on pass (see the tables below; `work/renames.csv` is the current
source of truth). `work/ghidra_export/functions.txt`/`disasm.txt`/`uw_c.c` have been
re-exported (full `UWExport.java` run) to match.

Method: the 2,041 Ghidra functions were classified with capstone over the raw
EXE bytes (INT-vector + DOS AH extraction per function, `work/int21.py`,
`work/classify.py`, `work/ahdump.py`), plus out-degree analysis of the
decompiled call graph (`uw_c.c`). Renames are committed only with a
**verified** anchor: a concrete `INT n` / AH immediate, the MZ entry point,
or an exact cross-project control-flow match whose UW1 call target is resolved
through the exeinfo table. Everything else stays `FUN_*` for the next pass.

## Address ↔ name conventions (reminder)

- Loader image: Ghidra block `CODE_n` = `seg:off`; **file offset = `((seg−0x1000)<<4)+off+0x3200`**.
  So `206b:003f` ↔ file `0x138ef`.
- ⚠ **That formula is one-directional in practice.** Forward (seg:off → file)
  it's simple algebra. Reverse (file → seg:off), algebra alone is not
  reliable enough for finding a rename target: you must look up which
  `CODE_nnn` block (`work/ghidra_export/memory_layout.txt`) contains the
  target file offset, then `seg = 0x1000 + (blockFileStart>>4)`,
  `off = F - blockFileStart`, then find the enclosing *Function* (not just
  the block) in `functions.txt`. Using a wrong header constant here (`0x2000`
  instead of `0x3200`) is exactly what put 13 of the first 20 renames on the
  wrong function — see "Status" above.
- Tail (`CODE_TAIL`): address **== file offset** exactly.
- MZ entry `0x1010:0EC5` (linear 0x10FC5) sits inside the function now named
  `crt_heapinit` (`1ec5:0246`); Ghidra's original `entry` symbol (1000:0000)
  is the PSP-init code just before it.

## Applied renames (all verified)

### DOS INT 21h wrappers (file-I/O core) — ✗ **seg:off corrected 2026-08-21**

These are the raw `int 21` thunks; the game's higher-level I/O funnels through
`func_0x00012276` / `FUN_1222_0047` (a generic DOS-call dispatcher that takes
the AH as an argument — see `file_create_read` below).

Every row below was reverse-computed onto the wrong function in pass 1 (see
"Status"); the table now shows the corrected seg:off, matching the cited file
offset (also corrected where the original citation was itself imprecise —
`dos_filecontrol`/`dos_lseek` were off by 14–41 B, landing in a neighbouring
function within the same block).

| New name | seg:off | file | evidence |
|---|---|---|---|
| `dos_getcwd` (was `dos_findfirst`) | 206b:003b | 0x138ef | INT 21h **AH=0x47 GET_CURRENT_DIRECTORY** — `mov dl,[bp+6]` (drive) / `mov si,[bp+8]` (buffer) matches the DL/DS:SI calling convention exactly. Not FindFirst (that's AH=0x4E, DS:DX=path + CX=attribute) |
| `dos_filecontrol` | 206b:0274 | 0x13b27 | INT 21h AH=0x44 IOCTL (AL=subfn, BX=handle, CX=count, DX=buffer) |
| `dos_lseek` | 206b:02e9 | 0x13ba7 | INT 21h AH=0x42 LSEEK (AL=method, BX=handle, CX:DX=offset). Same function `analysis/uwexe.md` §9 already catalogued as a "low-level primitive" — see the "Not yet named" note below |
| `dos_open` | 20b9:011a | 0x13ece | INT 21h AH=0x3D OPEN_FILE (AL=mode, DS:DX=filename); updates the handle table at `[BX*2+0x1e80]` on success. Same function `analysis/uwexe.md` §9 already catalogued as a "low-level primitive" |
| `dos_write` (was `dos_close`) | 2174:06be | 0x14ffe | INT 21h **AH=0x40 WRITE** — `mov bx,[bp+6]` (handle) / `mov cx,[bp+0xa]` (count) / `mov dx,[bp+8]` (buffer) matches WRITE's calling convention, not Close (AH=0x3E takes only a handle) |
| `msg_displaystring` | 2eb4:001e | 0x21d5e | INT 21h AH=9 DISPLAY_STRING (`lds dx,[bp+6]` then `int 21`); 16 B, inrefs=0 |
| `dos_deletefile` (new) | 2174:01af | 0x14aef | INT 21h AH=0x41 DELETE_FILE (`mov dx,[bp+6]` then `int 21`). This is the function pass 1 wrongly named `dos_findfirst` |

**Withdrawn — no function safe to rename:**

- **`dos_close_after_msg`** (was 2397:010c, reverted to `FUN_2397_010c`, which
  is itself an unrelated multi-parameter bounds/range-check routine). The
  cited evidence is real — AH=9 DISPLAY_STRING at file 0x15a65, then what is
  actually AH=0x40 WRITE (not Close) at file 0x15a8b — but it sits in bytes
  Ghidra's auto-analysis never disassembled at all: blocks `CODE_382`/`CODE_383`
  (segments 2273/2275, file 0x15930–0x15bff) are empty in `disasm.txt`, and
  segment 2275 has zero functions in `functions.txt`. There is no Function
  object there to rename without first running the disassembler at that
  address — beyond the scope of a rename.
- **`dos_close_drive`** (was 4a74:045a, reverted to `FUN_4a74_045a`). The
  cited evidence splits across two unrelated things: three genuine AH=0x3E
  CLOSE sites (file 0x3d9c8/0x3d9d1/0x3d9db) that Ghidra disassembled but
  never wrapped in a Function (start of block `CODE_635`, before the first
  function `FUN_4a74_00ef`), and one AH=0x30 site (file 0x3db00) that *is*
  inside a real function, `FUN_4a74_017e` — but per `analysis/uwexe.md` §9
  that function's actual role is the INT 2Fh multiplex initializer, and
  AH=0x30 there is **GET_DOS_VERSION**, not "get current drive" (that's
  AH=0x19). Renaming `FUN_4a74_017e` "dos_close_drive" would be exactly the
  same kind of mislabel this pass is fixing. The function that was wrongly
  squatting on the name (`FUN_4a74_045a`) isn't a DOS int21h wrapper at all:
  byte evidence shows a BIOS/XMS-style extended-memory block-move helper
  (tries a driver entry point with AH=0x0B, falls back to INT 15h AH=0x87) —
  flagged for a future, dedicated naming pass rather than guessed here.

All 22 direct `int 21` sites in the image were enumerated (`work/int21.py`);
the rest set AH via a register (not an immediate) and are the FIND/EXEC
variants. The bulk of file traffic uses the `func_0x...` dispatcher rather
than a direct `int 21`.

### CRT startup chain (around the MZ entry)

| New name | seg:off | evidence |
|---|---|---|
| `crt_psp_init` | 1000:0000 | PSP-chain walk + command-line parse; Borland CRT PSP init; inrefs=10 (was `entry`) |
| `crt_heapinit` | 1ec5:0246 | **MZ entry** (linear 0x10FC5). Borland CRT heap/BRK init: `0x1234` fill, `0x7fff/−0x7fff` heap sentinels |
| `crt_startup` | 1030:000a | callee of `crt_heapinit`; atexit/cmdline post-init |

The real entry's post-CRT far call at file `0x11F58` resolves through FBOV row
109 to `main` at unit file `0x77420`; its wrapper calls `main_init` `0x77460`,
`game_loop` `0x7760B`, and `main_shutdown` `0x775C6`. The separate CRT support
functions above remain useful names, but are not the game `main`.

### Input / VBI cluster (0x23600–0x23800) — ✗ **seg:off corrected 2026-08-21, same bug as the DOS wrappers**

Found during the "lighter" Phase 1.5 spot-check of this row family: 3 of 5
rows' original seg:off sat on **34 zero bytes each** — not code, not even
disassembled. All 5 rows' cited file offsets were real; the reverse seg:off
conversion just landed them on the wrong (empty) segment (same stale-constant
bug as the DOS wrappers). True locations cluster in Ghidra block `CODE_457`
(segment `301e`, file 0x23605–0x237dc) plus one in segment `309d`. The theme
turns out broader than "input": video palette + BIOS-RTC clock sync +
keyboard + mouse, short utility routines sitting next to each other in the
file.

| New name | seg:off | evidence |
|---|---|---|
| `video_palette_get` (was half of `input_vbi_poll`) | 301e:0225 | INT 10h AX=0x1009 then AX=0x1015 (file 0x23613/0x23623) — **not** VBI-wait; get-palette-block / get-individual-DAC-register |
| `video_palette_set` (was the other half of `input_vbi_poll`) | 301e:0261 | INT 10h AX=0x1002 then AX=0x1010 (file 0x23655/0x2367a) — set-palette-block / set-individual-DAC-register |
| `clock_sync_rtc_to_dos` (was `input_mouse21h`) | 301e:02a9 | INT 1Ah AH=4/2 (read RTC date/time) then INT 21h **AH=0x2B/0x2D SET DATE/SET TIME** (file 0x2369a/0x236af) — **not** mouse; AH=0x2D/0x2B are Set Time/Set Date, mislabeled "mouse query" in pass 1 |
| `input_kb_direct` | 301e:03e8 | INT 0x16 AH=1 poll / AH=0 read (file 0x237ca/0x237d0) — confirmed correct, only the address moved |
| `input_mouse33b` | 309d:0098 | reads the INT 33h vector via the IVT (`0:0xCC`), calls INT 33h to detect the mouse driver (file 0x23c6e) — confirmed correct, only the address moved |

**Withdrawn:** `input_mouse33` (was 317d:000a, reverted to `FUN_317d_000a`,
which is a generic keyed linked-list/handle-table lookup — no INT 33h
anywhere in it). Its cited "region" (file 0x237da) resolves to a 6-byte stub
(`301e:03f6`, left unnamed) that merely calls `input_kb_direct`'s code rather
than containing INT 33h itself. `input_mouse33b` keeps its "b" suffix for
minimal diff even though there's no longer a confirmed "a" site.

### High out-degree hubs (runtime error/abort dispatch)

Top of the call-graph out-degree ranking; all share the same callee set
(`FUN_1278_00e0`, `FUN_1278_0121`, `FUN_12b8_00c5`, `FUN_1300_000d` = the
CRT abort/`_exit`/print-error family). Likely the shared fatal-error /
assert / "overlay error" dispatcher. Named `rt_errhub_*` as placeholders until
their distinct roles are separated.

| New name | seg:off | out-degree |
|---|---|---|
| `rt_errhub_1` | 2d74:04d7 | 45 |
| `rt_errhub_2` | 20b9:0444 | 42 |
| `rt_errhub_3` | 2101:010a | 40 |

### File create+read (self-load candidate)

| New name | seg:off | evidence |
|---|---|---|
| `file_create_read` | 1fbe:022d | FCREATE (AH 0x3C) + random-access read (heavy INT 0x1A) + FCLOSE; 464 B, inrefs=0. **Primary candidate for the tail/overlay self-load** — needs runtime confirmation of the 0x76B30 base. |

### Cutscene exit path — resolved from UW2

| New name | CODE_TAIL file | evidence |
|---|---|---|
| `cutscene_run` | 0x7479b | Large `CUTS` renderer called by the exit handler; its relative call position and region setup match UW2 `cutscene_run` `0x828e3`. |
| `cutscene_play` | 0x75339 | `game_loop` reaches this through `lcall 0x0348:0x0084` with argument `9`; the body selects the cutscene region and calls `cutscene_run` at `0x7479b`, matching UW2 `0x82b35 → 0x828e3`. |

### Event pump cluster — resolved from the UW2 correspondence

The resident image contains the same contiguous event chain as UW2, with
different globals and low-level callees but identical control-flow roles. The
four entries below are named in `work/renames.csv` and the idempotent Ghidra
script:

| New name | seg:off | file | evidence |
|---|---|---|---|
| `event_source_queued` | 2be8:026a | 0x1f2ea | One-slot pushback at `[0x111]`, sentinel `0xffff`, flag `[0x119]`, recorded value `[0x11a]`; fetches through `0x1bc4:0x0fa9`. |
| `event_poll_mods` | 2be8:0338 | 0x1f3b8 | Low-level poll, empty-result `0xffff`, timer-pair capture, and modifier bits `0x400/0x200/0x100`; nonzero mode calls the adjacent ring-buffer helper at `0x1f338`. |
| `event_pump_alternating` | 2be8:03d5 | 0x1f455 | Alternates queued and modifier sources via `[0x12e]`, falling back to the other source when the preferred result is negative. |
| `event_pump` | 2be8:042a | 0x1f4aa | Thin wrapper pushes mode `0` and calls `event_pump_alternating`. |

The exact top-level edge is now independently resolved: `game_loop` at
`0x7760b` executes `lcall 0x0070:0x066a`; `work/ovl_resolve.py` reads
`exeinfo[0x70]` (row 14) as segment `0x1bc4`, producing resident file
`0x1f4aa`. The exit edge `lcall 0x0348:0x0084` resolves to stub row 105 and
then to pool body `0x75339` (`cutscene_play`), so the remaining state-handler
work is below the event/cutscene paths rather than another unresolved main
entry.

## Not yet named (next pass)

- **Frame/state handlers below `game_loop`** — the top-level wrapper, resident
  event-pump chain, and cutscene exit path are now resolved. The next target is
  the frame/state work after the pump and after `cutscene_play`.
- **LEV.ARK / CNV.ARK / STRINGS.PAK readers** — the *record-fetch layer* is now
  located: the **archive resource subsystem** at file `0x3c000..0x3e600` (Ghidra
  blocks `48a7..4a74`, 46 functions; setdrive 0x3E + lseek 0x42 + read 0x3F by
  absolute file offset; close @ file 0x3dd9a, `FUN_4a74_045a` — name withdrawn
  2026-08-21, see the DOS-wrapper table above). The string-pool paths
  (`DATA\lev.ark` @ 6c8b:022c, `DATA\cnv.ark` @ 6c8b:0575, `DATA\strings.pak`
  @ 6c8b:0108) are **not** statically referenced (0 direct refs across 111,801
  instructions; no u32 far-pointer table) — they are resolved at runtime
  (STRINGS.PAK ids or separate seg/off immediates). So the *top-level* readers
  are found by a **far-call-graph** pass upward from the subsystem (no direct
  xrefs into it), or by boot-tracing the open/read sequence. See `uwexe.md` §9–10.
- **File I/O primitives (name next)** — ✗ **partially resolved 2026-08-21**:
  the premise that these are "low-level, distinct from the already-named
  dos_open/dos_close/dos_lseek (2174 block, the stdio thunks)" was itself a
  symptom of the seg:off bug — there is no separate 2174-block stdio layer;
  `dos_open`/`dos_lseek` now correctly point at `FUN_20b9_011a`/`FUN_206b_02e9`,
  the exact functions this bullet used to call "distinct, name next as
  sys_*". Still genuinely unnamed: read `FUN_20b9_0221`, fcreate
  `FUN_20a1_0138`, close `FUN_20a1_0151` / `FUN_20b9_02fa` (2174:06fd) — real
  DOS AH=0x3F/0x3C/0x3E wrappers, distinct from `dos_write`/`dos_deletefile`/
  `dos_filecontrol`/`dos_getcwd` above. `dos_close` is free again (the
  function that had that name reverted) — a good candidate for
  `FUN_20a1_0151` or `FUN_20b9_02fa`, whichever is the real AH=0x3E close;
  rename `dos_read`/`dos_fcreate`/`dos_close` to complete the family.
- **Save machinery** (`SAVE0\lev.ark`, `player.dat` = "GROKEY" save) — **static
  chain resolved 2026-08-25 by transferring UW2's save model**. `SAVE0\` is
  the working directory; the four persistent slots are `SAVE1\`–`SAVE4\`,
  each with a `desc` file. `FUN_CODE_TAIL__083920` is the menu dispatcher;
  `083a97` is `savegame_save` (`level_save` `08369e` into `SAVE0\`, then
  `dir_copy_all_files` `083d49` to the selected slot), and `0839ce` is
  `savegame_restore` (slot to `SAVE0\`, then `level_load` `0835fc`). The
  shared helpers are `083c72` (`file_copy`), `083d49` (directory copy),
  `0837a4` (scan slot descriptions), and `083be6` (slot-content check).
  Call order, path literals, and the UW2 directory-copy structure support the
  roles; the F1 runtime flow is independently confirmed to write the working
  `UW\SAVE0\LEV.ARK`/`BGLOBALS.DAT`, and the complete slot-I flow copied
  `LEV.ARK`, `BGLOBALS.DAT`, `PLAYER.DAT`, and `DESC` into `UW\SAVE1\`.
- The `int 0x67` cluster (25 sites) and `int 0xCE` (TURBO switch) at
  0x11196/0x11282/0x11380/0x1147c/0x1158d.

## Files

- `work/renames.csv` — the applied rename table (old, seg:off, new, rationale);
  corrected 2026-08-21; now extended with four event-pump rows, all tied to
  byte-level evidence or the verified UW2 structural correspondence.
- `work/ghidra_scripts/UWRename.java` — idempotent applier (match-by-current
  FUN_seg_off name), for a **fresh** import/re-import; its table now encodes
  the corrected mapping directly (original default name → final correct
  name), so a clean run never passes through the withdrawn intermediate
  names. Moved here 2026-08-21 from `work/ghidra_scripts_old/` to match this
  doc and `analysis/ghidra.md` (which always claimed this location).
- `work/ghidra_scripts/UWRenameFix.java` — the one-time corrective script
  actually run against the already-mutated `work/ghidra/UW16` project on
  2026-08-21 (`APPLIED 24/24`); matches by the CURRENT (possibly wrong)
  semantic name, so it only makes sense to run once, against a project that
  already has the old buggy `renames.csv`/`UWRename.java` applied.
- `work/ovl_resolve.py` — resolves pool `lcall V:off` operands through the
  UW1 `FBOV` exeinfo table and follows INT 3Fh stubs to their pool bodies.
- `work/int21.py`, `work/ahdump.py`, `work/classify.py`, `work/refscan.py` —
  the capstone classifiers / AH dumpers / string-ref scanner.
- Ghidra scripts (`work/ghidra_scripts_old/`): `UWFileToFn.java` (file-offset →
  Ghidra addr + containing fn), `UWFnsInRange.java` (list fns by file range +
  size), `UWCallers.java` (incoming xrefs of an address). These still live in
  the `_old` directory despite being referenced as `work/ghidra_scripts/*` in
  `analysis/ghidra.md` — only `UWRename.java`'s path was corrected in this
  pass; the others have the same discrepancy and were out of scope here.
  `UWPoolRefs.java` (scan for refs into a file-offset range) and
  `UWStrRefs.java` are also referenced there; `UWPoolRefs.java` is actually in
  `work/ghidra_scripts/`, `UWStrRefs.java` is in `work/ghidra_scripts_old/`.
- `work/ghidra_export/memory_layout.txt` — the authoritative block → file-offset
  tiling (basis of `uwexe.md` §8).
