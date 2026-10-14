# `work/` — derived artifacts (NOT pristine; `game/` is the reference)

Index of every derived artifact + the exact command that produces it. Convention
(shared with UW1): if you can't regenerate an artifact, it isn't trusted. Layout
proposal (mirrors UW1's `work/`): move into `work/sweeps/`, `work/ghidra/`,
`work/extracts/` when P1.3 starts; update this file when moving.

## Source copies / extractions

| artifact | how it was made | note |
|---|---|---|
| `z_tie__.exe` (1,031,495 B) | copy of `game\SWTieCD\TIECD\Z_TIE__.EXE` | the game (MZ stub + standard Watcom LE, re-resolved 2026-08-21); DOS4GW input |
| `z_tie_32.raw` (773,447 B = 0xBCD47) | slice of `z_tie__.exe` file `0x3F000:` | **legacy extract**: offset 0 = file 0x3F000 (`img+0`), a pure file-offset alias — but the LE data pages start at **0x3D800**, so the extract misses the first 0x1800 B of object 1, and the old "runtime = 0x7E000 + off" note is withdrawn (`analysis/ztie.md` §4) |
| `z_tie_16.raw` (10,736 B) | slice of `z_tie__.exe` (the MZ stub) | ~~"partial 16-bit half, P1.4 redoes 0x40–0x46470"~~ — this IS the whole 16-bit program (stub 0x60–0x2A4E + header slack); there is no larger half (2026-08-21) |
| `tie.exe`, `z_tie2.exe`, `dos4gw.exe`, `detvesa` (copies) | copies of the pristine EXEs | launcher / extender sweep targets |
| `zrdx/`, `dos32a/` | source clones (P0 extender evaluation) | verdict: `analysis/extender-eval.md`; keep prebuilt `dos32a\binw\dos32a.exe` (usable on-target DPMI host) |

## Sweeps & dumps (regeneration)

| artifact | command | doc |
|---|---|---|
| `analysis/32bit/functable_v2.txt` + `uncovered_v2.txt` (4,030 fns, 84.6%) | `python work/sweep32.py work/z_tie_32.raw` (reads `analysis/32bit/strings.txt` for anchors) | `analysis/32bit/P1.2-functable-v2.md` |
| `z_tie_16bit_half_sweep.txt`, `detvesa_16bit_half_sweep.txt` | `python work/sweep16.py <file> <base_addr> <region_start> <region_end> [outdir prefix]` (region args per target; base_addr = linear address region_start loads at) | P1.4 pending; per-target invocations in `P1.5-launchers.md` |
| `analysis/32bit/16bit_TieExe.txt` / ~~`32bit_TieExe.txt`~~ / `16bit_ZTie2.txt` | `work/sweep16.py` / ~~`work/sweep32.py`~~ on `tie.exe` / `z_tie2.exe` regions | `P1.5-launchers.md` — **the 32-bit TIE.EXE sweep is void** (TIE.EXE is plain 16-bit; 2026-08-21), and `16bit_TieExe.txt` stops at 0x395B of a program that runs to 0x7B50 |
| **LE container audit** (prints the full MZ+LE map, both samples) | `python work/audit_headers.py game/SWTieCD/TIECD/Z_TIE__.EXE` (also: `TIE.EXE`, `Z_TIE2__.EXE`, `DETVESA.EXE`) | `analysis/DOS4G-header.md` |
| **LE fixup decode / reverse-xref index** | `python work/audit_fixups.py --stats` · `--page=N` · `--target=OBJ:OFF` (path + LE offset hardcoded to `Z_TIE__.EXE` @ 0x2A50) | `analysis/DOS4G-header.md` §Fixups |
| **source-module map** (38 C modules from the image's own assert strings, 0 overlapping spans) + function attribution | `python3 work/module_map.py [--lines] [--functions <export>] [--names work/ghidra/obj1_names.txt]` → `work/ghidra_export/module_map.txt` (`--lines` adds the 1,286 (file,line) anchors + monotonicity check; `--names` emits the 786-entry rename map for `TieNameByModule.java`) | `analysis/functions.md` §5c |
| `work/ghidra/obj1_notes.txt` — 750 functions annotated with the strings they reference (evidence for naming, not names) | `python3 work/string_xrefs.py --annotate work/ghidra/obj1_notes.txt` | `analysis/functions.md` §4d |
| **bulk decompile corpus** `work/ghidra_export/obj1_c.c` (4.9 MB, all 3,528 obj1 functions, 8 failures; **gitignored**) | add `-postScript TieDecompile.java 10000 bb000 "$PWD/work/ghidra_export/obj1_c.c"` to the single `-import` run | `analysis/functions.md` §4c |
| decompiled evidence: `work/ghidra_export/panl_blitter.c` (`FUN_0004977C`, the PANL opcode set), `xactor.c` / `xrect.c` (FILM opcode callees), `cockpit2.c` (0x48600–0x4F000), `check_system_requirements.c` | `-postScript TieDecompile.java <lo> <hi> <out>` inside the single `-import` run (`analysis/functions.md` §Regeneration) | `analysis/LFD.md` §5–6b |
| ad hoc x86-32 disasm at a file offset (used to trace the CD-check routine) | `python work/disas_at.py <file_off_hex> [len_hex] [--before n_hex]` (path hardcoded to `game/SWTieCD/TIECD/Z_TIE__.EXE`; near `call`/`jmp` targets are already correct file offsets — PC-relative, no fixup needed; only absolute-address operands need `audit_fixups.py`) | `analysis/ztie.md` §7 item 10 |
| `dos4gw16.txt` (1,755 fns) / `dos4gw32.txt` (530 fns) | `work/sweep16.py dos4gw.exe …` two regions (0x1BD0–0x2FFFF / 0x30000–0x40CCC) | `analysis/DOS4GW-loader.md` |
| `dos4gw16_plain.txt` / `dos4gw16_dis.txt` (~10 MB each) | rizin full 16-bit disasm of DOS4GW's 16-bit half (rizin 0.8.2: multiple `-c` flags, `af @ addr` with space) | `analysis/DOS4GW-loader.md` |
| `analysis/32bit/strings.txt` | rizin `iz` (vaddr column is garbage — 0.8.2 section-init bug; **use paddr column = image-relative**) | `P1.2-functable-v2.md` §limits |
| `analysis/32bit/entry_stub.txt`, `16bit_stub.txt` | capstone/rizin dumps of entry-stub & 16-bit half | `DOS4G-header.md` |

**Address conventions** (re-based 2026-08-21 — the authoritative table is
`analysis/ztie.md` §4):
- `img+X` = file `0x3F000+X` = `z_tie_32.raw[X]` — a **pure file-offset
  alias** (all string-pool citations remain valid). ✗ withdrawn: "= runtime
  linear 0x7E000+X" and "16-bit half linear = file offset".
- Runtime linears: obj1 `0x10000 + (file − 0x3D800)`; obj2
  `0xC0000 + (file − 0xE8800)` (`analysis/DOS4G-header.md`).
- sweep32 output addresses are file offsets (rizin base-0x3F000 convention).
- **Verify once** at P1.3 (Ghidra import) that every table's address column is what its
  header claims before cross-referencing.

## Data-format decoders (P2)

| artifact | command | doc |
|---|---|---|
| LFD container reader / record lister | `python3 work/lfd.py <file.lfd> [...]` | `analysis/LFD.md` §1 |
| LFD payload decoders (DELT/ANIM/PLTT/PANL/TEXT + VOC & GMID checks) | imported as `lfd_delt` — no CLI | `analysis/LFD.md` §2–6 |
| **whole-tree LFD audit** (container invariants + every payload; exit 0 = all hold) | `python3 work/lfd_audit.py game/SWTieCD/TIECD` | `analysis/LFD.md` |
| PNG extraction, one file | `python3 work/lfd_extract.py <out_dir> <file.lfd> [...]` | `analysis/LFD.md` §10 |
| PNG extraction, whole tree (**5,835 PNGs**, gitignored — write outside the repo) | `python3 -c "import sys; sys.path.insert(0,'work'); import lfd, lfd_extract; lfd_extract.main('/tmp/lfdall', list(lfd.iter_lfd('game/SWTieCD/TIECD')))"` | `analysis/LFD.md` §10 |

`lfd*.py` read `game/` **read-only**; nothing is written back into the pristine tree.

## Reassembly ratchet (P4.2)

| artifact | command | doc |
|---|---|---|
| `work/ratchet/stub.{asm,bin,lst}` — 16-bit MZ stub, byte-exact at **83.5 % net** (84.5 % gross) | `python3 work/ratchet16.py` (~2.7 s) | `analysis/reassembly.md` |
| `work/ratchet32/stub.{asm,bin,lst}` — **32-bit obj1, all 700,416 B, byte-exact at 93.2 % net** (93.7 % gross) | `python3 work/ratchet16.py --unit obj1 --out work/ratchet32 --orphan-rounds 5` (~70 s) | `analysis/reassembly.md` |
| `work/build/Z_TIE__.EXE` — **the whole 1,031,495 B file, byte-identical**, 99.9 % emitted from source / 0.1 % (1,154 B headers) copied | `python3 work/build_ztie.py` (run both ratchets + `type_obj2.py --emit` first; needs `nasm` on PATH — Windows: `C:\msys64\mingw64\bin`) | `analysis/reassembly.md` |
| LE fixup tables re-encoded + verified (27,438/27,438 records round-trip) | `python3 work/build_fixups.py` | `analysis/reassembly.md` |
| `work/obj2/obj2.{asm,bin}` — obj2 classified (58.8 % typed) and emitted, re-assembles byte-exactly | `python3 work/type_obj2.py --emit` | `analysis/reassembly.md` |

Both `.bin` outputs are verified with `cmp` against the original bytes; a rebuild
that is not byte-identical is a failed run, not a partial result. Outputs are
gitignored (the obj1 listing alone is 24 MB).

## DOS oracle (regeneration)

Boot image + headless QEMU harness — full procedure in `analysis/qemu-boot.md`.

| artifact | command | doc |
|---|---|---|
| `img/tie.hdd` (268,886,016 B) + `img/tie.hdd.geom.json` | `python work/build_dos_hdd.py` (reads the genuine DOS 6.22 floppies in `img/` + `game/SWTieCD/TIECD` + `game/SWTieCD/TIE.CD` + `work/dos32a/binw/dos32a.exe` → `C:\DOS\DOS32A.EXE`) | `analysis/qemu-boot.md` |
| `img/img_build/mbr.bin` (446 B) | `nasm -f bin work/mbr.asm -o work/img_build/mbr.bin` — re-run and diffed against `dosimg.MBR_CODE` on every build | `analysis/qemu-boot.md` |
| `game/SWTieCD/cd/SWTIECD.iso` (543,205,376 B) | `python work/bin2iso.py` — strips the 2352→2048 raw sector framing off `SWTIECD.BIN` (MODE1/2352) so QEMU/86Box can mount it | `analysis/qemu-boot.md` |
| `work/cd_probe/*` | `7z e -owork/cd_probe game/SWTieCD/cd/SWTIECD.iso SUPPORT/TIE.CD SUPPORT/INSTALL.BAT SUPPORT/PATCH197.BAT INSTREC.CFG INSTMAX.CFG AUTORUN.INF` — the disc's own install scripts; they settle what `TIE.CD`/`INSTALL.CFG`/`CDROM.CFG` mean | `analysis/qemu-boot.md` §Install semantics |
| guest screenshots / logs (`work/qemu_out/`, gitignored) | `python work/run_qemu.py --timeout N [--shot SEC] [--key SEC:KEY] [--cat ::/BOOT.LOG]` | `analysis/qemu-boot.md` |

`work/dosimg.py`, `work/run_qemu.py` and `work/mbr.asm` are **byte-identical
across all four sibling projects** (UW1, UW2, TIE, F29); only
`build_dos_hdd.py` and `set_boot_mode.py` differ per game. Keep them in sync —
see `analysis/cross-project.md`.

## Upstream clones (committed as plain subtrees; their `.git` is not in the repo)
- `dos32a/` — github.com/amindlost/dos32a @ `06d8e3a0b239` (DOS/32A v9.12, Apache-like license)
- `zrdx/` — github.com/DosWorld/zrdx @ `18acbf115d15` (ZRDX extender + ZBIND)
Verdict on both: `analysis/extender-eval.md` (rejected as DOS4GW drop-in replacements;
dos32a.exe kept as on-target DPMI host).

## Scratch / to clean
- ~~`tie32_fix.py`, `__pycache__/`~~ — cleaned up 2026-08-26 (`__pycache__`
  regenerates; delete freely).
- `sweep16.py` / `sweep32.py` are shared with UW1 (`C:\Arbeit\F030Underworld\work\`);
  keep in sync or fork explicitly.

## Ghidra (P1.3 — pipeline built, first naming pass applied; detail `analysis/functions.md`)

Per-object import (obj1 code @ linear 0x10000, obj2 data @ 0xC0000), **not**
one blob at 0x3F000 — that one-liner predates the LE re-resolution.

| artifact | command | doc |
|---|---|---|
| `work/ghidra/z_tie_obj{1,2}.raw` | `python work/slice_objects.py` (reuses `audit_fixups.py`'s LE parse; self-checks against a known string) | `analysis/functions.md` §1 |
| `work/ghidra/obj{1,2}_seeds.txt` (5,149 / 3,608 addrs; obj2's generated but unused by design) | `python work/gen_ghidra_seeds.py` | `analysis/functions.md` §1 |
| `work/ghidra/TIE.gpr`+`.rep` (Ghidra project; programs `z_tie_obj1.raw` 3,186 fns, `z_tie_obj2.raw` data-only) + `work/ghidra_export/obj1_functions.txt` | `analyzeHeadless` × 2 + 3 Java postScripts — full invocation in `analysis/functions.md` §7 | `analysis/functions.md` |

Toolchain note: **this Ghidra install has no PyGhidra** — `.py` postScripts
fail headlessly; use plain `.java` GhidraScripts (auto-compiled, no manual
javac). Ghidra compiles every `.java` in `-scriptPath` as one bundle, so one
script's compile error silently blocks every other script in that directory —
`analysis/functions.md` §2.
