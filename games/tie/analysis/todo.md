# TODO — path to complete disassembly (code + data)

Legend: [ ] open · [x] done · [~] partial · gates = things that block others.
Condensed 2026-08-26: narrative detail lives in the per-topic master docs
(`ztie.md`, `functions.md`, `LFD.md`, `data-formats.md`, `reassembly.md`,
`qemu-boot.md`, `extender-eval.md`, `DOS4G-header.md`, `DOS4GW-loader.md`);
this file is status, residuals and order — keep it that way.

State (2026-08-26): `Z_TIE__.EXE` is an MZ stub + standard Watcom **LE**
module (obj1 code @ 0x10000 from file 0x3D800, obj2 data @ 0xC0000 from
0xE8800; entry linear 0x8B4E4) and `TIE.EXE` is a plain 16-bit Watcom
program — the "DOS4G OLX hybrid / private header / thunk records / 0x7E000
base" model is **withdrawn** across the docs (old readings quoted in
`DOS4G-header.md`). The LE fixup table is the reverse-xref index
(`work/audit_fixups.py --target=OBJ:OFF`). P2.1 (LFD) is done at whole-tree
scope; the boot oracle works end to end on two extenders and is blocked only
on the game's own CD check — fully traced as a genuine MSCDEX probe with no
static/config bypass (`ztie.md` §7 item 10). The Ghidra pipeline is built and
804 of 3,528 obj1 functions are named (`functions.md`). The whole EXE
reassembles byte-identically (`reassembly.md`).

## Phase 1 — Static disassembly (no dynamic oracle needed)

- [x] **P1.1 `DOS4GW.EXE` ground-truth disassembly** **DONE 2026-08-19** —
  `analysis/DOS4GW-loader.md` + sweeps `work/dos4gw16.txt` (1,755 fns, 81.1%)
  / `work/dos4gw32.txt` (530 fns, 46.7%). Rational DOS/4G 1987–1993; 16-bit
  entry 0x1F18/9; 32-bit D32 kernel self-placed @ linear 0x180000; usage,
  options and env vars mapped. No INT 43h/17h/20h → XMS via DPMI 0x2000 RM
  gate; VCPI INT 15h = mode switch. The 2026-08-21 target-side corrections
  (thunk taxonomy, entry-stub pair, 0x7E000 base — all withdrawn) are quoted
  in `DOS4GW-loader.md` §Answers. **Still open** (→ P3.2): XMS alloc sizes,
  demand-load vs full-copy of the 191 pages, DOS/16M + VMM4G fallback paths,
  GDT-template semantics.
- [x] **P1.2 32-bit image function sweep v2** **DONE 2026-08-18** —
  `work/sweep32.py` → `analysis/32bit/functable_v2.txt`: **4,030 functions,
  84.6% byte coverage** of `work/z_tie_32.raw`, 94.3% of v1 starts recovered;
  uncovered 14.5% classified in `uncovered_v2.txt`. Method + limits:
  `analysis/32bit/P1.2-functable-v2.md`. Addresses valid as file offsets
  (the runtime column is superseded — `ztie.md` §4). **Residuals → P1.4.**
- [ ] **P1.3 Function naming + decompilation** — pipeline built + verified;
  master doc **`analysis/functions.md`**. Status: per-object Ghidra import
  (obj1 @ 0x10000, obj2 @ 0xC0000; no PyGhidra → Java postScripts; one
  `-import` run, **never `-process`**); **804 of 3,528 functions named**
  (786 module-map provenance names from the image's own assert strings +
  1,286 (file,line) anchors, 18 hand-verified incl. the fully traced
  CD-check chain); the `__STK` body repair is adopted into the pipeline
  (`check_system_requirements` decompiles and corroborates `ztie.md` §7
  item 10, incl. the closed `0x13548` bypass); bulk decompile corpus
  `work/ghidra_export/obj1_c.c` (reading aid, not the artifact of record);
  750 functions annotated with string xrefs (`work/ghidra/obj1_notes.txt`).
  Function counts are per-run measurements, not invariants (3,186 Windows
  vs 3,529 macOS — `functions.md` §5b).
  **Next: `functions.md` §6** (semantic naming from string-xref anchors →
  FILM-opcode module reads → `MASK` format via `FUN_00044008` → obj2 data
  typing → `SHIP`-renderer hunt).
- [ ] **P1.4 Sweep completion** (rescoped 2026-08-21 — there is no 16-bit
  half; the 10.7 KB stub is the whole 16-bit program). Done: **stub sweep**
  via the reassembly ratchet — 83.5 % net of `0x60..0x2A4E` disassembled and
  *proven by re-encoding*, entry `0000:030E`; the 1,881-byte region at
  `0x2295` is an `int n; ret` thunk table, not padding
  (`analysis/reassembly.md`). Still open:
  - what the stub does when the file runs without an extender;
  - re-sweep `TIE.EXE` as one 16-bit program `0x380..0x7B50` (P1.5
    correction; feed the 214 relocation targets in as segment words);
  - sweep the **obj1 head `0x3D800..0x3F000`** — never covered by v2 (the
    legacy extract starts at 0x3F000); `game_main` @ 0x3D810 is hand-traced
    only;
  - re-classify `uncovered_v2.txt`'s "16-bit-mode clusters" under the LE
    map (the entry-stub/thunk reading is withdrawn; most lie in obj2 data);
  - add a **known-data guard** to `work/sweep32.py` (cross-project ADOPT
    item 5 — 84.6 % is an unguarded coverage number until then; the mapped
    string pools are the ready starting set).
- [x] **P1.5 `TIE.EXE` + `Z_TIE2__.EXE`** **DONE 2026-08-18, corrected
  2026-08-21** — both launchers are plain 16-bit Watcom MZ programs
  (TIE.EXE entry 0x110C; the "DOS4G hybrid / 32-bit image @ 0x39EC" reading
  is withdrawn, old readings quoted in `analysis/32bit/P1.5-launchers.md`).
  What stands: the string-pool findings — launcher sequence, UNIVBE block,
  Z_TIE2__ guard pool, boot chain, `/trebla` marker, `/320` arg.
- [ ] **P1.6 Other EXEs** (headers + code as needed): `DETVESA.EXE` (VESA
  probe code; headers already cross-verified — same e_lfanew 0x2A50
  convention), `TIEAUTO.EXE` (CD auto-launch), `IMUSE.EXE` (device-table
  handling; **no-sound fallback behavior** — matters for the silent boot
  path), `UVCONFIG.EXE` (UniVBE fallback), `Z_INST__`/`INSTALL`/`INSTLOW`
  (installer — low priority, not runtime), `BOOTTIE.EXE` (boot-disk maker —
  low priority).
- [x] **P1.7 DETVESA as second LE sample** **DONE 2026-08-21 via the
  audit** — same stub shape and `e_lfanew` 0x2A50, standard LE (obj1 @
  0x10000 vsize 0x314EE, obj2 @ 0x50000 vsize 0x3200, entry linear 0x10254,
  data pages ending exactly at file size). Its VESA-probe *code* remains
  P1.6.

## Phase 2 — Data format decoders (`analysis/<topic>.md`, headers quoted, never guessed)

- [x] **P2.1 LFD/RMAP container** **DONE 2026-08-22** — master doc
  **`analysis/LFD.md`**; tools `work/lfd*.py`; whole-tree regression
  `python3 work/lfd_audit.py game/SWTieCD/TIECD` (exit 0 = all hold).
  Container **RESOLVED**: flat chain of `{char type[4]; char name[8];
  u32le length;}` records, verified over 175 files / 2,184 records with
  0 failures; 105 files open with an `RMAP` index record, the 70 in
  `CP320/`+`CP640/` do not; the generic lookup is `lfd_find_record`
  (XRES.C — hands back bytes, never interprets them). Payloads at
  all-records scope: `DELT` 370/370, `ANIM` 355/355 (5,467 frames), `PLTT`
  296/296, `TEXT` 27/27, `VOIC`+`BLAS` 342/342 (standard Creative VOC
  v1.10), `GMID` 179/179 (standard MIDI — also resolves the standalone
  `.GMD`). Whole tree extracts to **5,835 PNGs** (PANL no longer rendered —
  P2.1d). `.LFB` = the same container (depth hypothesis refuted); `RES320`
  vs `RES640` differ only in 10 `XACT` effect sprites — all `SHIP` records
  byte-identical (59 in `SPECIES.LFD`; all 78 across `SPECIES*.LFD`,
  `LFD.md` §8) — and `RESOURCE/SPECIES*.LFD` is a **third variant**, not a
  copy (26 of its 78 `SHIP` records differ).
  - **P2.1b `FILM` DONE 2026-08-22** (`LFD.md` §6b): 149/149 — the scene
    sequencer; chunks are `{u16 time; u16 lenBytes; u16 opcode; params}`
    (field order corrected 2026-08-22), **20 opcodes** of fixed arity;
    **dispatch found** — two `XFILM.C` jump tables, every opcode mapped to
    its handler + callee module, callees decompiled (field effects
    recorded, meanings not guessed). Resolves 86 % of the ambiguous
    palette pairings. Handler over-read characterised, not resolved.
    Opcode *meanings* TBD → `LFD.md` §9 item 2.
  - **P2.1c `SHIP` header DONE 2026-08-22** (`LFD.md` §6c): 234/234, 78
    unique models; spans are **unsigned** u16 (load-bearing for the 7
    capital ships); geometry past 0x24 deliberately undecoded — needs the
    renderer in `Z_TIE__.EXE` (`LFD.md` §9 item 3).
  - **P2.1d `PANL` CORRECTED 2026-08-22** — the old pixel model was
    plausible-but-wrong (desynchronised on 29,070 `0xFC` opcodes); the real
    opcode set came from the blitter `panl_blit_lfd`. Structure now exact
    (189/200 rows CP320, 456/480 CP640), but **pixels are not statically
    decodable** (runtime-built tables) → needs the table-init code or a
    runtime dump (P3.2).
  - **`MASK` consumer identified 2026-08-26, encoding NOT resolved** (`LFD.md` §9 item 1):
    measurements only (group sums cluster on the screen widths); it is
    *not* the PANL encoding; every `0xFD`/`0xFF`-touching function has been
    read and excluded. **The consumer is `FUN_00044008`** —
    `FUN_00043710` passes the second record pointer written by
    `FUN_00043B6C`; the row-span transform is recorded in `LFD.md` §9.
  - Still TBD: `MASK` encoding (70), `SHIP` geometry, `XACT` 56, `BMAP` 26, `FONT` 5,
    `MTRX` 5, and the `FILM` opcode meanings (`LFD.md` §9).
- [ ] **P2.2 `.PNL` + `.INT`** (CP320/CP640 cockpit UI) — `.PNL` object
  tree (tags `PL8`/`L8`; uses PANL-like opcode bytes but is **not** that
  format — multi-image containers, `LFD.md` §9), `.INT` interface object
  list (`01` + named entries → LFD images: GUNBT12/FWD/…).
- [ ] **P2.3 `.TIE` missions** (76 files) — header fields
  (`ff ff 16 00 0d 00 03 00 …`), briefing text @~0x15, rest of structure;
  `H*` + `TRAIN.TIE` variants.
- [ ] **P2.4 `.WRK` audio** (ASTREAM) — codec params (IMA-ADPCM variant?
  channels, rate), 5-byte header meaning, IMUSE integration; the `-` vs `_`
  duplicate-file rule.
- [~] **P2.5 `.GMD` MIDI** — **container RESOLVED 2026-08-22 with P2.1**
  (`LFD.md` §6): `MIDI` + `u32be` length + `MDpg`/`MThd`/`MTrk`, walk exact
  on all 4 `.GMD` files and all 179 `GMID` records. Remaining: `MDpg`
  (iMUSE) contents, MT-32 track structure, instrument mapping.
- [ ] **P2.6 Custom media** — `.ICO`/`.ANI`/`.FLC` (custom packed, **not**
  standard FLIC; try ffmpeg then hand-decode), `.FNT` 8×8 fonts (compare
  with the LFD `FONT` records, `LFD.md` §9), `.TFR` high scores (read the
  TFR handler in the image), verify `.LBM` is standard. `.PAL` (raw RGB)
  and `.GMD` are done.

## Phase 3 — Dynamic oracle

- [x] **P3.1 Fix the `C:` drive rejection** **DONE 2026-08-20** — the old
  image was a partitionless superfloppy; `img/tie.hdd` (MBR + FAT16 at LBA
  63, genuine DOS 6.22 boot record, invariants asserted at build time in
  `work/dosimg.py`) boots with `C:\TIECD` populated; chain verified end to
  end. `analysis/qemu-boot.md`.
- [ ] **P3.2 Boot the game** + runtime observation. Checklist = the open
  items in **`ztie.md` §7**: (1) demand-load vs full copy of the 191 LE
  pages, (2-residual) residency-check obj1/obj2 at 0x10000/0xC0000 and read
  what the `0x7E00`/`0x7E10` immediates feed, (6) XMS alloc sizes via DPMI
  0x2000, (7) DOS/16M/VMM4G fallback paths. **Blocker: the game's own CD
  check** (item 10, RESOLVED statically) — a genuine MSCDEX probe
  (`INT 2Fh AX=1500h/150Bh` via DPMI) trying `\ASTREAM\A.WRK` on each
  MSCDEX-reported drive; its one candidate shortcut (the `0x13548` skip
  flag) is a **closed dead end**. **Driver route is the only unblock**: a
  DOS ATAPI driver (missing — a download, needs user sign-off on the
  source) + `MSCDEX.EXE` (already at `C:\DOS`) + `SWTIECD.iso` (built,
  `work/bin2iso.py`); config lines ready in `qemu-boot.md` §Remaining
  blocker. Booting also feeds P2.1d (PANL runtime tables) and `MASK`
  (instrument the cockpit load, `LFD.md` §9).
- [x] **P3.3 DOS/32A retest** **DONE 2026-08-21** — `work/set_boot_mode.py
  dos32a` reaches the identical `ERROR #3` CD-check text the DOS4GW chain
  reaches; confirmed working drop-in (`analysis/extender-eval.md`
  §Verdict). The custom mini-loader plan is deleted (unnecessary — its
  premise was withdrawn).

## Phase 4 — Reassembly & verification

- [ ] **P4.1 CD check** — diff the `TIECD/` folder vs the `SWTIECD.iso`
  file system (1,727 files / 540 MB on disc vs 391 / 95 MB installed —
  `qemu-boot.md` §Install semantics; `ASTREAM\` is never copied by the
  installer): is the folder copy complete? Does the runtime ever need the
  CD beyond `\ASTREAM\`?
- [~] **P4.2 Build order + byte-exact harness** — **the whole 1,031,495 B
  EXE reassembles byte-identically; 99.9 % emitted from source, 0.1 %
  (1,154 B: MZ + LE headers, import table) copied** (`work/build_ztie.py`;
  re-verified 2026-08-26 on the Windows host). Quality of what is emitted
  (`analysis/reassembly.md`): stub **83.5 %** / obj1 **93.2 %** real
  instructions net of the data + pointer-table guards (upper bounds; 2,074
  overlapping decodes remain), fixup tables **100 %** (all 27,438 records
  round-trip, `work/build_fixups.py`), obj2 **58.8 % typed** / 41.2 % raw
  `db` (`work/type_obj2.py --emit`). Remaining: emit the copied header
  regions, type obj2's unknowns (P2.x feeds this), and compute fixups from
  the code's relocatable operands (what a real build does) instead of
  re-encoding decoded records.
- [ ] **P4.3 Working build** — reassembled game boots to menu → cutscene →
  mission (86Box or QEMU; shares P3.2's CD-driver blocker).

## Toolchain gaps

- [x] **Ghidra** — installed on both hosts; headless verified end to end.
  **No PyGhidra on either host** (`functions.md` §2), and the function
  table is **not reproducible across runs** (§5b) — treat any count as one
  measurement.
- [x] **rizin** — macOS 0.9.1 (the three documented 0.8.2 gotchas no longer
  apply; one new: `rz-bin -zz` for headerless files); Windows 0.8.2. See
  the AGENTS.md toolchain table.
- [x] ~~Install keystone (P4.2)~~ — **not needed**: the ratchet uses `nasm`
  (macOS `/opt/homebrew/bin`, Windows `C:\msys64\mingw64\bin` — not on the
  default PATH). 7-Zip is installed (`C:\Program Files\7-Zip`, not on
  PATH); ImHex still to install (verification aid).
- [ ] **Host note:** the docs carry `C:\Arbeit\…` / `C:\tools\…` paths
  while a second git-synced working copy lives at
  `/Users/saschaspringer/Work/F030TieFighter`. Decide once whether to port
  the paths wholesale or keep them as the Windows-host record.

## Suggested order (updated 2026-08-26)

**P1.3 continuation** (`functions.md` §6: semantic naming → FILM-opcode
module reads → obj2 typing) ∥ **P2.1 leftovers** (`SHIP` geometry via the
renderer → `MASK` format via `FUN_00044008` → `XACT`/`BMAP`/`FONT`/`MTRX`,
`LFD.md` §9) — **CD driver decision** (user sign-off on an ATAPI-driver
source; the single P3.2 blocker) → **P3.2** boot + runtime observation
(also unblocks PANL pixels and the MASK consumer) → P4.1 + P4.2 remainder
in parallel. P1.4 and P1.6 slot in anytime.
