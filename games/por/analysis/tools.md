# Tool notes

Lessons that cost time once. Add to this file the moment a tool surprises you —
per `AGENTS.md` §Conventions. Two machines are in use; sections below the
`## Windows machine` divider are that machine's, the rest is macOS.

## `7zz` (7-Zip 26.02, Homebrew)

- **Reads FAT12 floppy images directly.** `7zz l game/POR/disk1.img` lists the
  disk; `7zz x -oDisk1 disk1.img` extracts it with original timestamps. No
  loopback mount, no `hdiutil`, no `mtools` needed.
- **Cannot read ARC.** `7zz x DISKA.ARC` fails with `Can't open as archive: 1`
  and reports `Files: 0` — it does *not* error out loudly, so a script that
  ignores the exit code will silently produce an empty tree. Use `unar`.

## `unar` / `lsar` 1.10.7 (Homebrew, The Unarchiver)

- The ARC unpacker that works. `unar -q -f -D -o <outdir> <file.ARC>`:
  `-D` = do not create an enclosing folder, `-f` = overwrite,
  `-q` = quiet. Verified byte-exact against the ARC directory CRCs on all
  257 entries (`python3 work/arcverify.py`).
- `lsar <file>` lists without extracting and prints the detected format
  (`game/POR/Disk1/SAVE.ARC: ARC`).
- There is **no** `-l` flag on `unar` — that is what `lsar` is for.

## `PKUNPAK.EXE` (shipped on both disks, 15,112 B)

The authentic unpacker. Not needed for routine work now that `unar` is
CRC-verified, but it is the tie-breaker if a future ARC entry ever disagrees.
Needs DOSBox-X.

## Python

- `python3` 3.14.7, `capstone` 5.0.7, `Pillow` 12.3.0 are all present.
- Project decoders live in `work/`: `arcverify.py` (ARC directory + CRC),
  `dax.py` (container + RLE), `gbimage.py` (image header + EGA → PNG).
  Import them rather than re-deriving a format.

## Rendering discipline

A size identity is not a decoded image. `17 + h*wb*4 == size` matched for both
the planar and the packed interpretation of the pixel data; only rendering both
and **looking at them** showed planar to be noise and 4 bpp packed to be
correct. `work/probe/` holds the contact sheets. Keep doing this.

## DOSBox-X 2026.08.02 (Homebrew)

Installed, not yet used. `dosbox-staging` is also present. Nothing to report
until `img/` has a bootable DOS disk — record the machine profile and the
capture recipe here when it does.

## vasm `vasmm68k_mot`

- `addq`/`subq` take an immediate of **1..8 only**. `addq.w #16,d0` is
  `error 2026: operand value out of range` — use `add.w #16,d0`. Easy to hit
  when the increment is a named constant (`PORI_PALETTE_COUNT`) whose value is
  not obvious at the call site.
- `rept <n>` / `endr` unrolls cleanly inside a `dbra` loop; used by
  `src/present.s` for the 8-pixel expansion body.
- Includes resolve relative to the **including file**, so `include "inc/por.s"`
  works with the assembler invoked from the project root.

## vlink / TOS executables

**Link order picks the entry point.** A TOS program begins execution at the
first byte of its TEXT segment; `vlink -e _main` sets the ELF entry but the TOS
loader ignores it. Moving `start.s` out of first position silently produced a
binary that entered at `main` instead — it built cleanly, ran, and simply never
set up Videl, so `grab-frame.sh` reported `could not read Videl base (got '')`.
The Makefile now forces `$(TARGET_DIR)/start.s` first.

## Hatari (Homebrew) — the Falcon oracle

Capture recipe: `bash tools/grab-frame.sh <vbl> <out.png>`, or `make
title-smoke` for the full compare. It sets a debugger breakpoint at a VBL
count, reads the three Videl base bytes (`$ffff8201/8203/820d`), dumps RAM with
`savebin`, and slices the page out of the dump. The same capture boundary is
used by the F29 and Comanche siblings; keep the RAM-dump guard size documented
and validated locally when changing it.

- **Hatari occasionally ignores the debugger `quit`** and is killed by the
  harness timeout instead (`Killed: 9` on stderr). Observed twice in about a
  dozen runs, with no pattern by memory size, cold/warm start, or `make` vs.
  direct invocation. **The capture is unaffected** — `savebin` completes at the
  breakpoint, before the quit — so `grab-frame.sh` tolerates it with `|| true`
  and validates the dump afterwards instead. Do not "fix" this by shortening
  the timeout; that would start truncating real dumps.
- `--disable-video on` plus `--fast-forward true` keeps a 600-VBL capture at
  about 8–9 s wall clock.
- The Videl base is read from the log, never assumed: on this project it lands
  at `$0219D8` at both `MEMSIZE=4` and `MEMSIZE=14`, because the pages are
  `Mxalloc`ed from the bottom of free ST-RAM after `Mshrink`.

## Verification, not inspection

`tools/check_frame.py` compares the captured Videl page against the host
expansion of the same source bytes and requires them to be **byte-identical**.
Prefer that to looking at the PNG: the rendering-discipline note above exists
because a wrong pixel interpretation once satisfied every size identity.

## capstone 5.0.7 — the 16-bit disassembler

`work/disasm.py` is the project's disassembler (recursive descent, 16-bit real
mode). Two things cost time:

- **Capstone names far transfers `lcall` / `ljmp`, not `call far`**, and their
  operands arrive as **(segment, offset)** in that order. Matching on `call`
  silently follows nothing: coverage sat at **1 %** until this was fixed, then
  jumped to 14 % on `START.EXE`.
- **`INT 3Fh` is not an instruction boundary here.** A Turbo Pascal overlay
  stub is `CD 3F` + `DW offset` + `DB 00`, so the three descriptor bytes are
  data. Decoding them as opcodes derails the walk immediately — the first run
  reported "33 × int 3Fh" and 0 % coverage, all of it garbage. Step over 5
  bytes and continue, as the overlay manager's IRET does.

Seed the walk from real entry points, never from a linear sweep:
`work/overlay.py` extracts 774 of them from the resident stub segments.

## Ghidra 12.1.3 (Homebrew, 2026-08-20)

`brew install ghidra` — it is a **formula, not a cask** (`brew install --cask
ghidra` fails with "No Cask with this name exists"). Pulls `openjdk@21`
automatically; a separately installed Temurin is not required.

Read `../F030Underworld/analysis/ghidra.md` before the first import — it has
the 16-bit real-mode DOS workflow and its gotchas (notably: `-processor` takes
the **language ID**, and `-loader` is broken in 12.1.3). For this project,
import overlay **units** individually using `work/overlay_map.json` rather than
`GAME.OVR` as one blob: each unit is a separate code image with its own base,
its own fixup table, and a known entry-point list.

### Working recipe (verified on unit `18E`, 2026-08-21)

```sh
export JAVA_HOME=/opt/homebrew/opt/openjdk@21          # REQUIRED, see below
HL=/opt/homebrew/Cellar/ghidra/12.1.3/libexec/support/analyzeHeadless

python3 work/overlay.py work/overlay_map.json          # unit map + entry thunks
# extract <unit>.bin and <unit>.entries from the map, then:

"$HL" "$PWD/work/ghidra" POR16 \
    -import    "$PWD/work/ghidra/unit18E.bin" \
    -processor "x86:LE:16:Real Mode" \
    -scriptPath "$PWD/work/ghidra_scripts" \
    -preScript  PORSeed.java   "$PWD/work/ghidra/unit18E.entries" \
    -postScript PORExport.java "$PWD/work/ghidra_export" unit18E
```

Runtime is seconds per unit, not minutes — these are 10 KB images, not a 560 KB
EXE. Output: `unit18E.c`, `unit18E_functions.txt`, `unit18E_disasm.txt`.

- **`JAVA_HOME` must be set.** Homebrew's `openjdk@21` is keg-only, so Ghidra
  cannot find it and fails with `Unable to locate a Java Runtime` followed by
  `ERROR: Unable to prompt user for JDK path, no TTY detected`. Installing
  Temurin does not help — export `JAVA_HOME` instead.
- **Raw import lands at `0000:0000`**, so a unit's Ghidra address equals its
  offset within the unit — the same numbering `work/game16.txt` and
  `work/overlay_map.json` use. No rebasing needed.
- **Seed entries in a `-preScript`, not a post-script.** A raw binary has no
  entry point, so auto-analysis finds almost nothing on its own. `PORSeed.java`
  disassembles and creates functions at the unit's thunk offsets *before*
  analysis; on unit `18E` that turned 20 seeds into 30 discovered functions.
- **Thunk slots may be `0xFFFF` placeholders** — unit `18E` declares 24 entries
  of which 4 are unused. Filter to `offset < codeSize` before seeding.

### Batch mode: all 38 units in one run

`make decompile` does the whole corpus in a single headless invocation:
`work/extract_units.py` writes `work/ghidra/units/*.bin` and
`work/ghidra/entries/*.entries`, then `-import <units-dir>` imports them all and
`PORSeed.java` resolves each program's entry list by name
(`<programName minus .bin>.entries`). Keep the `.bin` and `.entries` files in
**separate directories** — `-import` on a directory tries to import everything
in it, including text files.

Ghidra tags exported files with the program name, so they land as
`unit18E.bin_functions.txt`, not `unit18E_functions.txt`. Two functions were
refused with `Failed to create function ... since its body contains referring
thunk`; that is benign and leaves those addresses uncovered.

### DS-relative globals are not in the unit image

The costliest mistake of this pass: Turbo Pascal puts code and data in separate
segments, so an address like `0x260A` in decompiled unit code is a **DGROUP
offset**, not an offset into the unit. Dumping `0x260A` from `unit18E.bin`
returns unrelated *code* bytes and looks like a decoded table if you are not
careful.

Resolve them against `START.EXE` instead: DGROUP base is paragraph **`0x740`**
(from `mov dx,0x740 / mov ds,dx` in the abort path), so

    load-image linear = 0x7400 + <DS offset>

Verified: `DS:260A` → linear `0x9A0A` → `01 02 04 08`, the EGA plane masks, and
the only occurrence of that sequence in the load image.

## NASM 3.02 (Homebrew) — the reassembly proof

`brew install nasm`. Driven by `work/reasm.py`; see `analysis/executables.md`
§Reassembly proof.

- **Verify per instruction with `-l`, never by diffing the whole binary.** The
  first version of the ratchet demoted "everything after the last label" when a
  build differed, which collapsed unit `18E` to **1 %** real instructions while
  still reporting a byte-exact rebuild. A byte-exact rebuild made entirely of
  `db` proves nothing. Parsing the listing gives each source line's generated
  bytes, so exactly the mismatching instructions get demoted — the same unit
  then scored **79 %** in 3 passes.
- Listing format is `<line> <8-hex addr> <hex bytes> <source>`, with wrapped
  continuation lines carrying no line number; accumulate those into the
  previous line.
- capstone → NASM syntax needs three fixes: `word ptr [bx]` → `word [bx]`,
  `es:[di]` → `[es:di]`, and `lcall 0x5bb, 0x0` → `call far 0x5bb:0x0`.
  Branch targets must become labels so NASM computes displacements itself;
  anything else is left for the ratchet to demote.
- Short vs. near branch encodings are the main legitimate demotion: NASM may
  pick a different form than the original compiler did.

## Not installed on this machine (macOS)

rizin/Cutter, QEMU.

---

## Windows machine (`C:\Arbeit`, user `sasch`, inventory 2026-08-21)

Temporary note: the project moved to a second machine. Paths here override the
macOS defaults in `Makefile` and `work/stage.sh` until those are
parameterised; nothing in this section changes the analysis itself.

### Present and verified

| Tool | Path | Notes |
|---|---|---|
| Python 3.12.10 + capstone 5.0.7 + Pillow 12.1.1 | Windows Store (`WindowsApps`) | `python`/`python3` both work; all `work/*.py` decoders run unmodified |
| 7-Zip 26.02 | `C:\Program Files\7-Zip\7z.exe` | 7z + FAT12 as on macOS; **ARC re-confirmed unreadable** here too (`Cannot open the file as archive`) |
| **`work/arcunpack.py`** | project | the ARC gap-closer: pure-Python SEA/PKARC decoder ported from XADMaster/unar (ref sources kept in `work/arc_ref_*`). Verified 2026-08-21: **257/257 files, all CRC-16 match** (methods {2:9, 3:3, 4:5, 8:237, 9:3}). Use it instead of `unar`; `stage.sh` falls back to it where `unar` is absent |
| NASM 3.02 | `C:\Users\sasch\AppData\Local\bin\NASM\nasm.exe` | `make reasm NASM=...`; the Makefile default is a brew path |
| Ghidra 12.1.3 PUBLIC | `C:\tools\ghidra_12.1.3_PUBLIC` | exactly the pinned version; headless = `support\analyzeHeadless.bat` (`.bat`, run via `cmd`). Java 21 Hotspot at `C:\Program Files\Microsoft\jdk-21.0.12.8-hotspot` — export `JAVA_HOME` to it, same as the macOS note. **GhidraDosToolbox** extension is built (`C:\tools\GhidraDosToolbox`) and installed in `~/.ghidra/extensions` |
| QEMU 11.1 | `C:\Program Files\Qemu\qemu-system-i386.exe` | **exactly the path `F030Method/dos/run_qemu.py` hardcodes** — the QEMU DOS-oracle harness runs here as-is |
| mtools | `C:\msys64\mingw64\bin\{mcopy,mdir,mtools}.exe` | **exactly the `MSYS` path `run_qemu.py` hardcodes** |
| MS-DOS 6.22 floppies | `../F030Underworld/img/Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)` | shared with UW1; input for `build_dos_hdd.py` when the POR oracle image is built |
| DOSBox Staging 0.82.2 | `C:\Users\sasch\AppData\Local\Programs\DOSBox Staging\dosbox.exe` | *staging*, not DOSBox-X: `img/oracle/*.conf` are DOSBox-X-syntax and must be rewritten, or use the `--logging=int10,io,vga --log-file=...` command line instead |
| 86Box 6.0 | `C:\Users\sasch\AppData\Local\Microsoft\WinGet\Packages\86Box.86Box_…\86Box.exe` | second dynamic oracle; the right tool for a `PKUNPAK.EXE` byte-exactness pass |
| 7z asset + pristine disks | `assets/`, `game/POR/` | intact after the move; only `work/expanded/` was missing (now rebuilt by `arcunpack.py`) |

### Not present / not usable here

- `unar`/`lsar`, DOSBox-**X**, rizin — irrelevant or superseded (see above).
- **Falcon toolchain**: `../F030Arcade/third_party/{vasm,vlink,hatari}` are
  **source trees only** on this machine — no `vasmm68k_mot`/`vlink`/`hatari`
  binaries, so `make build`/`title-smoke` do not run until Windows builds are
  installed. TOS 4.04 image is present (`third_party/tos/tos404.img`).
- **git-bash here is minimal**: `ls`, `grep`, `head` etc. are *not* on the PATH
  of its `/usr/bin/bash` — surprising, and it breaks `stage.sh` and the
  Makefile's `grep`-based steps. Workaround used in this session: drive
  everything through `python` (or `powershell.exe -NoProfile -Command`).
- No WSL, no Docker, no choco/scoop. Per project direction: stay native
  Windows + Python; no WSL/Docker detours.

### Status at time of writing

`work/expanded/` rebuilt and CRC-verified (257/257). `work/start16.txt`,
`work/game16.txt`, `work/reasm/`, `work/ghidra_export/` are **not present** —
generated artefacts that were never tracked; regenerate with
`work/disasm.py`, `make reasm`, `make decompile` (with the path overrides
above) when needed. Next step unchanged: recover the `POOL.CFG` format from
`START.EXE` (static), then drive `INSTALL.EXE` through the QEMU harness.
