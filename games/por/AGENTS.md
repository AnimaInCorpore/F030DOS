# Project: Pool of Radiance (1988, SSI) — Decode, Disassemble + Prove, Understand, Port

**Goal:** analyze the DOS game *Pool of Radiance* (1988, Strategic Simulations
Inc. / TSR) — code and data — far enough that the whole game runs natively on
an Atari Falcon030, with every ported subsystem traceable to the DOS behaviour
it reproduces.

This is a **port**, not a reassembly: the DOS original is the authority for
semantics and data layouts; the Falcon owns video, input, timing, memory and
audio hardware. The analysis discipline is the one from the sibling
`../F030Underworld` project — verify, quote, document, then implement — and the
Falcon-side structure follows the target seams shared with `../F030Comanche`.

There is no reconstructed C source to port from; the DOS binaries are the
authority. Follow `../F030Method/METHOD.md` for each vertical slice:

1. **Decode** the required data over the full in-scope corpus and independently
   check representative semantics.
2. **Disassemble + prove** the loader/address model and rebuild the source files
   byte-for-byte, while separately guarding known data and recording why every
   entry point is code.
3. **Understand** the slice as a behavioural contract: inputs, outputs, side
   effects, arithmetic widths and original-run fixtures tied to source ranges.
4. **Port** only that grounded contract, then compare original, host reference
   and target at declared checkpoints.

The reassembly artefact is a **reconstruction proof, not a deliverable** — no
x86 binary ships on a Falcon. Byte equality proves emitted encodings and file
structure; it does not by itself classify bytes as code or prove behaviour.
Residue emitted as `db` is classified as data, padding, fixup/relocation,
non-selectable encoding, self-modified/generated code, overlap, or unresolved.
The remaining unresolved ranges and indirect edges are the finite worklist.

Presentation and data conversion may run ahead of phase 3 where the format is
already verified, but nothing may enter the port without a source —
`PORTING.md` §Nothing without a source.

## Mandatory function-level port policy

The hashed shipped DOS executable and its captured execution are the sole
behavioural authority. Reassembly, decompiler output, a recovered source tree,
the browser reference, and 68000 code are evidence or implementations; none
may overrule DOS. For every function represented in browser or target code,
maintain the `METHOD.md` §4.2 function record: DOS identity and evidence,
recovered contract and fixtures, browser/target symbols, and an explicit
difference ledger against DOS. Record and prove even “no difference”; an
unresolved difference is `Unproven` and cannot enter a supported path. Start
the deterministic browser reference with the first function; use its controlled
experiments to identify function roles, contracts, side effects and Falcon
seams, then confirm each finding against DOS before recording it. Land its
fixtures before or with each supported target slice.
## Implementation-source links

Every JavaScript/browser and 68000/m68k function source that implements or exposes a recovered DOS function must carry an adjacent comment or docstring linking to the durable function record and naming the disassembled DOS function symbol plus canonical range/entry (for example, `DOS: FUN_0000_1234; record: <stable-function-record>`). Use the same stable function ID in both implementation sources; a separate map or file-level comment is not enough. Code with no DOS counterpart must say `N/A - platform replacement` or `Target artefact` at the definition.


## Workspace

| Path | Content |
|---|---|
| `assets/001627_pool_of_radiance.7z` | Source archive (956,498 B, 2016-07-17): 2× 720 KB DOS floppy images. **Never modify.** |
| `game/POR/disk1.img`, `disk2.img` | Raw 720 KB FAT12 images (737,280 B each). Pristine reference. **Keep pristine.** |
| `game/POR/Disk1/`, `Disk2/` | Extracted disk contents (7 files). Pristine, `chmod a-w`. |
| `work/expanded/` | ARC-expanded game data (257 files: `START.EXE`, `GAME.OVR`, `*.DAX`, `*.PIC`, portraits, manifests, savegames). Derived — the analysis target. |
| `work/` | Decoders, probes and reassembly scratch (`*.py`, `stage.sh`). |
| `work/probe/` | Rendered PNGs and dumps. Derived, regenerable. |
| `analysis/` | Notes, dumps, format docs (`analysis/<topic>.md`). |
| `PORTING.md` | Roadmap and the per-slice porting plan. |
| `../F030Method/METHOD.md` | Portable playbook — how to decode/disassemble/prove/port *any* DOS game to a 68k Atari. Written here, moved to the family's parent repo 2026-08-21. |
| `analysis/cross-project.md` | Shared RE-technique ledger of the eleven-project family. **Generated** by `../F030Method/gen_cross_project.py` — edit there, not here. |
| `src/common/` | Target-neutral 68000-clean sources (`*.s`). |
| `src/target/<name>/` | Per-target back ends: `falcon` (Videl/RGB565), `st` (contract only). |
| `tools/` | Host-side converters, contract checks, frame capture and comparison. |
| `release/` | Built `.tos` + `PORCACHE/` converted data. Derived, ignored. |
| `build/` | Captured frames. Derived, ignored. |
| `img/` | Built emu images (to be created) — DOS boot disk/HDD for the dynamic oracle. |
| `../F030F29/`, `../F030Comanche/` | Falcon 68030/Videl implementation references. |
| `../F030Method/` | The family's parent repo: `METHOD.md`, the cross-project generator, and the master copies of the shared QEMU DOS-oracle harness (`dos/`, with `sync.py`). |
| Siblings listed in `../F030Method/README.md` | Family manifest; projects carrying the DOS harness are checked by `../F030Method/dos/sync.py`. |
| `../F030Arcade/third_party/` | vasm, vlink, TOS images, Hatari support files. |

Git: branch `main`. `assets/`, `game/` (pristine disks) and `work/*.py` are
tracked, as in `../F030Underworld`. `work/expanded/` and `work/probe/` are
**not** — they are derived, and `sh work/stage.sh` rebuilds both from `assets/`
and re-verifies every file against the ARC CRCs.

## Conventions

- `assets/` and `game/` are the untouched reference; everything under `work/`
  is derived and reproducible from `sh work/stage.sh`.
- One doc per format/component in `analysis/`; **verified header bytes must be
  quoted, not guessed.** Mark anything unproven `TBD`, never as fact.
- **Update the docs as you work:** every new finding (format, tool quirk,
  workflow, next step) goes into the right `analysis/*.md` (or `AGENTS.md`
  §Next steps) immediately — never leave results only in the chat log.
  Tool-usage lessons (DOSBox-X / capstone / unar behaviour) go into
  `analysis/tools.md`.
- **Cross-project lessons:** transferable methods across the eleven-project family
  are collected in `analysis/cross-project.md` — read it before inventing a
  method. It is generated by `../F030Method/gen_cross_project.py`; edit the
  body there and re-run so all copies stay in sync. Its closing §What to
  adopt here (POR) is this project's standing import list — and the reverse
  is a duty: when a finding here is transferable, upstream it to
  `../F030Method` (the generator body, or `METHOD.md` for phase/port policy)
  in the same session that records it locally.
- Verify reassembled output byte-for-byte against `work/expanded/` (and against
  the ARC CRC-16 for the archive layer, via `work/arcverify.py`).
- A format is only "RESOLVED" when a decoder round-trips it and the result is
  *looked at* — for graphics that means a rendered PNG, not a plausible size.
- DOSBox-X is the dynamic oracle for the **DOS** side; **Hatari** is the
  dynamic oracle for the **Falcon** side. After any change to the presented
  picture, capture a frame and compare it — never approve one by eye.
- **The port target is not fixed.** Atari ST and Falcon030 are both live, so
  nothing outside `src/target/<name>/` may assume either. `src/common/` is
  assembled `-m68000` and `src/common/inc/por.s` carries no hardware constants;
  `make test` enforces both. Build with `make TARGET=falcon|st`. Contract:
  `src/target/st/README.md`, rationale: `PORTING.md` §Target back ends.
- The port draws in 8-bit indexed with the DOS palette index preserved; only a
  target back end turns indices into hardware pixels. No VGA/EGA bitplane
  emulation: the 4 bpp DOS pixels are unpacked on the host by
  `tools/convert_data.py`.
- **Do not invent game rules.** A subsystem is ported after the DOS routine
  that implements it has been read. See `PORTING.md` §The authority problem.
- `tools/convert_data.py` converts only formats marked RESOLVED in
  `analysis/data-formats.md`; unrecognised blocks are skipped and counted.
  `src/inc/por.s` and the converter must agree — `make test` enforces it.
- **Decode, don't transcode.** Converters parse DOS records field by field and
  emit big-endian, target-aligned output; they never copy a DOS record and
  byte-swap in place. Bit-packed source becomes plain values. The decoded DOS
  layout in `analysis/` is the durable knowledge and is never edited to suit a
  target — see `PORTING.md` §Data representation policy.
- **Fidelity contract.** Preserve observable game semantics over the declared
  supported scope, including arithmetic widths and overflow; a claim of 100 %
  fidelity is a test conclusion, never an implementation intention.
  Graphics/sound hardware access is investigated far enough to reproduce its
  observable result. See `PORTING.md` §Fidelity policy.

## Distribution & install chain (verified)

- **Two 720 KB DOS floppies**, both plain FAT12 with the standard IBM boot
  record. BPB @ file 0x00 (identical on both images, bytes quoted):
  `eb 34 90 | "IBM  3.3" | 00 02 | 02 | 01 00 | 02 | 70 00 | a0 05 | f9 |
  03 00 | 09 00 | 02 00` → 512 B/sector, 2 sectors/cluster, 1 reserved,
  2 FATs, 112 root entries, **1,440 sectors = 737,280 B**, media `0xF9`
  (720 KB DSDD), 3 sectors/FAT, 9 sectors/track, 2 heads. Boot code is the
  non-system stub (`Non-System disk or disk error`).
- **Disk 1**: `DISKA.ARC` (283,778 B, 1988-12-09), `DISKB.ARC` (344,744 B,
  1988-12-12), `SAVE.ARC` (9,325 B, 1988-12-05), `INSTALL.EXE` (32,032 B,
  1988-12-10), `PKUNPAK.EXE` (15,112 B, 1988-08-02).
  **Disk 2**: `DISKC.ARC` (338,379 B, 1988-12-07), `PKUNPAK.EXE` (same file).
- **All game data ships ARC-packed** (SEA/PKARC). `unar` unpacks all four
  archives; the on-disk `PKUNPAK.EXE` is the authentic unpacker (use it under
  DOSBox-X for byte-exact verification). 257 entries total, compression
  methods **2, 3, 4, 8, 9** (237× method 8 = crunched). Every expanded file
  matches its stored CRC-16/ARC — `python3 work/arcverify.py` → *257 OK, 0 bad*.
  ARC entry header layout verified in `analysis/data-formats.md`.
- **`DISK<target><source>` manifests** (24 plain-text files inside the archives,
  CR-separated, `0x1A` terminated) drive `INSTALL.EXE`: `<target>` ∈ `1`–`8`
  (floppy install set), `H` (hard disk), `O`/`S` (the two boot-disk layouts —
  they differ by exactly one entry, `game.ovr` vs `start.exe`); `<source>` ∈
  `A`/`B`/`C` names the source archive. Every listed name was checked to be a
  member of the archive its suffix names — **24/24 consistent**. `DISK1B` is
  the only manifest written in upper case. The manifests cover **92 of the 257**
  archive members; the other 166 (all `PIC*`/`BODY*`/`HEAD*`/`CHRDATA*`,
  `ITEMS`, `SAVGAMA.DAT` and the manifests themselves) are never named — how
  `INSTALL.EXE` places those is **TBD**.
- **Runtime**: `START.EXE` loads `GAME.OVR` from the current directory and
  reads `POOL.CFG`; on failure it prints `Please insert startup disk.` /
  `Please insert overlay disk.` / `Overlay error, program abort!`.

## `START.EXE` (47,936 B) and `GAME.OVR` (232,379 B)

- **`START.EXE`** — MZ, header bytes @ file 0x00 verified:
  `4d 5a 40 01 5e 00 e4 00 3b 00 7c 1a 7c aa 92 0f 00 20 00 00 06 00 00 00
  1c 00 00 00` → `e_cblp = 0x0140`, `e_cp = 0x005E` (94 pages),
  `e_crlc = 0x00E4` (228 relocs), `e_cparhdr = 0x003B` (59 par = 944 B),
  `e_minalloc = 0x1A7C`, `e_maxalloc = 0xAA7C`, `e_ss = 0x0F92`,
  `e_sp = 0x2000`, `e_ip = 0x0006`, `e_cs = 0x0000`, `e_lfarlc = 0x001C`,
  `e_ovno = 0`. Image `(94-1)*512 + 320 = 47,936` = **exactly the file size**,
  so nothing is appended past the load image. Disassemble as **16-bit x86**.
  Entry **CS:IP 0000:0006**, relocation table at file 0x1C (228 × 4 B), code
  from file 0x3B0.
- **`GAME.OVR`** — **no MZ header**; a raw overlay image loaded by the stub in
  `START.EXE`. First bytes: `54 50 4f 56 | 21 | "Time to save your game.  [return]" | 55 89 e5 83 ec 24`
  → the leading `TPOV` reads as a *T*urbo *P*ascal *OV*erlay marker (**TBD**,
  unconfirmed), followed immediately by length-prefixed strings (`0x21` = 33 =
  the exact length of the string that follows) and a `push bp; mov bp,sp;
  sub sp,0x24` C/Pascal prologue.
- **Turbo Pascal — CONFIRMED.** `START.EXE` installs INT 00h/23h/24h/3Fh
  handlers that load Turbo Pascal runtime-error codes **200** (divide by zero),
  **255** (Ctrl-C) and **208** (*Overlay manager not installed*). `TPOV` is
  therefore Turbo Pascal OVerlay. See `analysis/executables.md` §Turbo Pascal.
- **Overlay mechanism — RESOLVED.** `START.EXE` is a thin resident stub; the
  game is 38 Turbo Pascal overlay units inside `GAME.OVR`, reached through
  `INT 3Fh`. Each unit keeps a resident header + entry-thunk table in
  `START.EXE`; the directory chain
  `fileOffset + codeSize + fixupSize == next fileOffset` is **exact for all 38
  units** and accounts for every one of the 232,379 bytes — 223,317 B code,
  9,058 B fixups, **774 entry thunks**. The program entry is a 49-call far-call
  chain, 38 of which are unit initialisations. Rebuild the map with
  `python3 work/overlay.py`. The "53-entry u16 trailer table" recorded in the
  first pass was simply the **last unit's fixup block**.

## Data inventory & format findings (headers verified)

`work/expanded/` — 257 files, 2.4 MB. Full detail in `analysis/data-formats.md`.

### `.DAX` — the Gold Box container — **RESOLVED**

89 files, 1,044 blocks. Verified on **all** of them (`python3 work/dax.py`):

```
[u16LE tableSize]                    # bytes; always 9 * blockCount
[blockCount x 9-byte block record]:
    u8    blockId                    # high bit = paired variant (see ICON.DAX)
    u32LE offset                     # relative to end of header (2 + tableSize)
    u16LE unpackedSize
    u16LE packedSize
[packed blocks, contiguous, in table order]
```

Invariants checked on all 89 files: first offset 0, `off[k+1] == off[k] +
packed[k]`, and `2 + tableSize + sum(packed) == filesize`.

### Block payload codec — **RESOLVED**

PackBits-style RLE on signed control bytes: `n = int8(ctrl)`; `n < 0` → emit
the next byte `-n` times; `n >= 0` → copy the next `n + 1` bytes literally.
**1,044 of 1,044 blocks** decode to exactly their declared `unpackedSize`.

### Image header + pixel format — **RESOLVED**

The same 17-byte header appears in `.PIC` frames, in the bare `BODY*`/`HEAD*`
files and inside RLE-expanded `.DAX` blocks:

```
u16LE height          rows
u16LE widthBytes      width_px = widthBytes * 8;  bytes/row = widthBytes * 4
u32LE 0               zero except TITLE.DAX blocks 0x01/0x02 (= 1)
u8    frameCount      repeat count for multi-element blocks
8 B   cgaRemap        16-entry x 4-bit CGA colour-reduction table, CGA-only
```

Payload is **4 bpp packed, high nibble = left pixel**, indexing the standard
16-colour EGA palette. `size == 17 + height * widthBytes * 4` holds exactly for
441 of 1,044 `.DAX` blocks; 50 more are arrays of *N* same-geometry elements
after one header (e.g. `8X8D1.DAX` block 1 = **70 × 8×8 tiles** — `frameCount`
byte confirms `0x46` = 70 exactly). Confirmed by rendering: `TITLE.DAX` block
0x01 is the **320×200 SSI/AD&D title screen** (`work/probe/TITLE_01_0.png`),
`ICON.DAX` is 6 × 24×24, `CHEAD.DAX` 24×10. The trailing 9 bytes (`frameCount`
+ `cgaRemap`) are read from the DOS code, not guessed — see
`analysis/executables.md` §Unit `18E`.

The remaining 553 blocks are **not** images — `ECL`, `GEO`, `ITEM`, `MON*CHA`,
`MON*ITM`, `MON*SPC`, `SPRIT`, `WALLDEF`. Those are the open formats.

### File classes

| Class | n | State |
|---|---|---|
| `*.DAX` containers | 89 | container + RLE **RESOLVED**; per-family payloads mixed (see table in `analysis/data-formats.md`) |
| `PIC*.PIC` | 62 | **RESOLVED** — `[u8 frameCount][frameCount × 3893 B]`, frame = `[u32LE tag][17-B image header][3872 B = 88×88]`. 62/62 match `size == 1 + count*3893`. Frame 0 = base picture, frames 1..n = sparse animation overlays. |
| `BODY1..37` | 21 | **RESOLVED** — bare image, header `30 00 0b 00 …` → **88×48**, 2,129 B |
| `HEAD0..74` | 41 | **RESOLVED** — bare image, header `28 00 0b 00 …` → **88×40**, 1,777 B |
| `DISK*` manifests | 24 | **RESOLVED** — install file lists (above) |
| `START.EXE`, `GAME.OVR` | 2 | MZ header resolved; code TBD |
| `CHRDATA1-6.SAV/.ITM/.SPC` | 16 | shipped pre-made characters. `CHRDATA1.SAV` (285 B) starts `0e "THRENDER GRONE"` → length-prefixed name. **Partially decoded (2026-08-21)**: name, all 6 ability scores (`+0x10`-`0x15`) + 18/percentile STR (`+0x16`), plus age/level/exp/weapon/armor/status inferred from UI order — see `analysis/data-formats.md` §The 285 B character/monster record. Most of the record (HP, saves, spells, inventory) still TBD. |
| `SAVGAMA.DAT` | 1 | 13,137 B savegame. TBD. |
| `ITEMS` | 1 | 2,050 B item table (`START.EXE`: `Unable to find item file`). TBD. |

## Toolchain (macOS-native)

| Tool | Status | Use |
|---|---|---|
| vasm `vasmm68k_mot` (`../F030Arcade/third_party/vasm/`) | installed | 68030 assembly (`-Felf -m68030`) |
| vlink (`../F030Arcade/third_party/vlink/`) | installed | TOS linking (`-b ataritos -tos-flags 1`) |
| Hatari (Homebrew) | installed | **Falcon dynamic oracle**, frame capture |
| TOS 4.04 (`../F030Arcade/third_party/tos/tos404.img`) | installed | Falcon boot ROM |
| ImageMagick `magick` + `timeout` (coreutils) | installed | RGB565 → PNG frame capture |
| 7-Zip 26.02 (`7zz`, Homebrew) | installed | `.7z` and **FAT12 floppy images**. Cannot read ARC. |
| `unar` / `lsar` 1.10.7 (Homebrew) | installed | **ARC unpacking** (verified on all 4 archives, 257/257 CRC-clean) |
| `PKUNPAK.EXE` (disk 1/2) | on disk | authentic ARC unpacker for byte-exact verification (needs DOSBox-X) |
| Python 3.14.7 + capstone 5.0.7 | installed | format decoders, 16-bit disassembly, probes |
| Pillow 12.3.0 | installed | EGA render checks (`work/gbimage.py`) |
| DOSBox-X 2026.08.02 (Homebrew) | installed | **dynamic oracle**; `dosbox-staging` also present |
| ffmpeg 9.0 | installed | audio experiments (no audio assets identified yet) |
| Ghidra | **to install** | 16-bit real-mode decompilation (see `../F030Underworld/analysis/ghidra.md` for the DOS workflow + gotchas) |
| QEMU 11.1 + mtools (Homebrew) | installed | **INSTALL.EXE oracle** (`work/drive_install.py`), reading guest-written files |
| rizin | **not installed** | optional second opinion |

Override any path on another machine: `make VASM=… VLINK=… TOS=… MEMSIZE=…`.

## Test machines

**DOS side** — DOSBox-X, 8086/286-class, EGA, no sound card in the first
implementation; `START.EXE`/`GAME.OVR` are 16-bit real mode and the shipped art
is EGA (4 bpp, 320×200). Machine profile and boot recipe go in
`analysis/tools.md` once a bootable `img/` exists.

**Falcon side** — Hatari, `--machine falcon --monitor rgb --mmu true
--cpu-exact true --compatible true --patch-tos true`, TOS 4.04, sound off in
every automated run. `MEMSIZE` defaults to 14 MB in the Makefile, but the
**design target is a stock 4 MB Falcon**. Verified 2026-08-20: the title screen
renders identically at `MEMSIZE=4` and `MEMSIZE=14` — same Videl base
`$0219D8`, byte-identical page. See `PORTING.md` §Memory.

## Verification harness

| Command | Checks | Last result (2026-08-20) |
|---|---|---|
| `sh work/stage.sh` | rebuild `game/POR/*` + `work/expanded/` from `assets/` | 257 files staged |
| `python3 work/arcverify.py` | every expanded file vs. the ARC size + CRC-16 | **257 entries, 257 OK, 0 bad** |
| `python3 work/dax.py` | `.DAX` container invariants + RLE round-trip | **89/89 containers OK; 1044/1044 blocks OK** |
| `python3 work/gbimage.py --dax work/expanded/TITLE.DAX` | EGA decode → PNG | 2 × 320×200, title screen correct |
| `python3 work/imghdr.py` | image-header `frameCount`/`cgaRemap` fields, corpus-wide | **778 headers, 778 OK, 0 bad** |
| `python3 work/ecl.py --validate` | ECL instruction encoding vs. all 29 blocks | **29/29 first scripts decode cleanly, ending on `0x00`**; the flat whole-block walk covers only ~6 % (blocks are not flat streams) |
| `python3 work/ecl.py --text` | ECL inline text, whole corpus | **2,904 distinct strings, 146,873 chars** of real game prose |
| `make build` | vasm + vlink | `por.tos` 1,765 B, `por_debug.tos` 7,967 B |
| `make test` | `src/inc/por.s` vs. `tools/convert_data.py` contracts | `POR Falcon contracts: OK` |
| `make falcon-data` | DOS art → `PORI` banks | 8 images, 0 blocks skipped |
| `make title-smoke` | boot Hatari, capture the published page, compare | **128,000 bytes identical**; `PORSTAT.BIN` = `STATUS_OK` |
| `make reasm` | reassemble every overlay unit + `START.EXE`, rebuild both originals | **`GAME.OVR` and `START.EXE` byte-identical**; 80 % of overlay code emitted as real instructions |
| `make decompile` | Ghidra headless over all 38 units, then index them | 1,102 functions, 1,082 decompiled, 748/758 entry points |
| `python3 work/drive_install.py` | drive the real `INSTALL.EXE` under QEMU, read back `POOL.CFG` | **"Installation complete" in ~18 s; 35-byte `POOL.CFG`** (2026-08-21) |

## Next steps

**0. ~~Stage and expand all ARC data~~ DONE** — `work/expanded/` (257 files,
   `unar`, all 4 archives CRC-verified against the ARC directory).

1. **~~Static disassembly~~ DONE (first pass)** — `work/disasm.py`,
   `work/overlay.py`, `work/disasm_ovr.py`; listings `work/start16.txt`
   (3,956 insns, 133 routines) and `work/game16.txt` (82,921 insns, 1,363
   routines, 37 % of unit code). Overlay mechanism and Turbo Pascal identity
   resolved — `analysis/executables.md`. Remaining: `POOL.CFG` parsing, the
   real overlay manager, `main` and the game loop.

2. **~~Reassembly proof~~ DONE** — `make reasm`. All 38 overlay units and the
   `START.EXE` load image reassemble, and both original files rebuild
   **byte-identical** (`work/reasm.py`, `work/rebuild.py`). **195,421 of
   223,317 overlay code bytes (87.5 %)** are real reassembled instructions,
   leaving **27,896 bytes** of `db`. `START.EXE` reports 16.7 % because ~37 %
   of that file is DGROUP data by construction and much of the rest is
   `INT 3Fh` thunks, which are 2 instruction bytes plus 3 of operand each.

   *This figure has been wrong twice, both times by trusting the reported
   number over the emitted output.* It read 80 % from `44f7c71` until
   2026-08-22, stale because `a9ea473` fixed `reasm.py`'s capstone→NASM `ptr`
   stripping and nobody re-measured. It then read 88.2 % for one commit,
   because `reasm.py` computed the score by summing the sizes of every
   instruction the *walk* found rather than the ones the *emitter* wrote — and
   the emitter runs a linear cursor, so any instruction at an offset a longer
   preceding instruction covers is skipped and was being double-counted;
   `INT 3Fh` thunks were counted as 5 instruction bytes rather than 2. Both are
   fixed: the counter is now taken inside `emit()`, and it agrees with the NASM
   listing on all 38 units. If you need this number, run `make reasm`.

3. **~~Raise the reassembly score~~ — the code/data map is essentially
   complete (2026-08-22).** `work/dbmap.py` splits the 27,896-byte `db`
   residue by what it actually is, using the demoted-instruction list
   `work/reasm.py` now writes per unit (`work/reasm/*.forced.json`):

   | category | bytes | share of the 223,317 B |
   |---|---|---|
   | emitted as instructions, byte-exact round-trip | 195,427 | 87.5 % |
   | demoted instructions — recovered as code, only `db` because NASM re-encodes them differently | 17,140 | 7.7 % |
   | Turbo Pascal `ShortString` constants | 8,608 | 3.9 % |
   | zero padding | 993 | 0.4 % |
   | unit header + thunk table | 874 | 0.4 % |
   | **unexplained** | **275** | **0.1 %** |

   So **95.2 % of overlay code is identified as code** and 4.7 % as data, with
   272 bytes left over — not the ~20 % the raw reassembly percentage suggests.

   **The caveat that matters:** the byte-exact proof covers the 87.5 %, *not*
   the 95.2 %. A demoted instruction is emitted as raw `db`, so it round-trips
   trivially and the proof says nothing about whether the walk decoded it
   correctly. Those 17,159 bytes are claimed code, not proven code.

   The 275 unexplained bytes are ~123 B of text fragments (where `dbmap.py`'s
   `ShortString` chain parser loses sync on a length byte that occurs inside
   the text), 30 B of stray zeros, 107 B of other short runs, and **12 B in
   three indirect far calls** — `CALL FAR [0x6A78]` at unit `0E2` +0D63,
   +0EA3 and +30F8. **Chased and closed (2026-08-22):** `DS:0x6A78` is not a
   single vector but the base of a **34-entry array of far procedure
   pointers**, built at run time by `0E2:33CC` and indexed by `DS:0x6779`
   (`0E2:0EA3` does `di = [0x6779] * 4` before the call). Every entry points at
   a unit `0E2` thunk, so all 34 targets were already seeded — the indirect
   calls hide no code. Slot 0 is the one that moves: `051:0071` (the routine
   ECL opcode `0x24` calls) repoints it at `096:20AE`, and `051:0040` and
   `0E2:33CC` reset it to `0E2:0A88`, making it a mode hook over an otherwise
   fixed table.

   **No `case`/dispatch offset tables exist in the code segment** — `dbmap.py`
   looks for runs of u16 instruction starts and finds none. That does *not*
   mean the game has no dispatch tables: the `DS:0x6A78` array above is exactly
   one, it is just **built at run time in DGROUP by a run of `MOV` pairs**
   rather than stored as static data a disassembler would trip over. Together
   with the compare-chain dispatchers already read (`020:32DF`, `020:0B1A`,
   `147:01CA`), the picture is that this build never emits a static jump table
   in the code segment. (An earlier version of `dbmap.py` reported six tables
   in unit `0B6`; they were runs of zero words, and zero is a valid instruction
   start. Zero is now excluded.)

   All **758 overlay entry points are now instruction starts** in the emitted
   rebuild; three were not until `reasm.py` was taught that an instruction may
   not span an entry point (see item 2).

4. **~~Decompile the units~~ DONE** — `make decompile`. All 38 units,
   **1,102 functions, 1,082 decompiled**, covering **748 of 758** resident
   entry points. Index: `work/ghidra_export/index.txt` (`work/funcmap.py`).

5. **Understand every routine** (phase 3, the large one). Work the index by
   unit, naming behaviour and citing it in `analysis/`. Start with the largest
   internal functions (`0D9:19E6`, `020:21FF`, `0B6:196F`, `058:144F`) and the
   units already identified: `18E` = renderer, `131` = dungeon-view
   raycaster/orchestrator, `18A` = wall-tile blit dispatcher — closes the loop
   back into `18E`'s own image-record conventions
   (`analysis/executables.md` §Unit `131`, §Unit `18A`).

6. **Finish the data formats** (`analysis/data-formats.md`): the 553
   non-image `.DAX` blocks. ~~`WALLDEF` + `GEO`~~ (dungeon geometry and the 3D
   view) are **RESOLVED (2026-08-21)**, read via unit `131`
   (`analysis/executables.md` §Unit `131`): `GEO` is a 2-byte header + four
   256-byte (16×16) planes, two of which are now tied exactly to the 4
   cardinal directions; `WALLDEF` is N × 780-byte blocks, each 5 wall-types ×
   10 fixed-size pre-drawn "distance sprites" (proven by an exact
   offset/size chain across all 9 gaps, not guessed) whose per-region ID
   remap feeds directly into `8X8D*.DAX`'s 5 tile-sheet families (unit `18A`,
   §Unit `18A` — `8X8D*` is now confirmed as the dungeon wall-tile art, not
   just "8×8 tile sheets"). `GEO`'s other 2 planes are narrowed too — queried
   against party position/facing globals (`DS:0x6A0B/C/D`), one a per-cell
   property, one a per-direction special-feature flag, see
   `analysis/data-formats.md` §`GEO*.DAX`. ~~Which depth/side selects which
   `WALLDEF` sprite slot~~ is **RESOLVED** too — the full 3-rank × 2-side
   sweep is mapped to its 10 sprite slots exactly
   (`analysis/executables.md` §The depth×side → sprite-slot mapping). The
   dungeon-view geometry is now understood well enough to reconstruct the
   on-screen layout without further RE.
   ~~`ECL`~~ (encounter/event scripts) is **RESOLVED end to end (2026-08-22)**
   — container, instruction encoding *and* block layout. Loader `entry_0353`
   in unit `045`; the interpreter is the execute loop `020:35DB`, the
   dispatcher `020:32DF` (complete opcode→handler map, valid range `0x00`-`0x3D`,
   `0x1F` has no handler), the operand decoder `045:0000`, the evaluator
   `045:013F`, the address builder `045:06BE` and the block init `045:01C8`.
   A block is **not** a flat stream: it opens with a **20-byte header of five
   `01 [01 lo hi]` records** that init files into `DS:0x4944`-`0x494C` as the
   block's five script entry points, and the rest is a control-flow graph
   rooted there. Two findings did the work: **four opcodes (`0x15`, `0x25`,
   `0x26`, `0x2B`) read their own operand count out of the stream**, and a
   **conditional (`0x16`-`0x1B`) guarding a `GOTO`/`END`/`RETURN` leaves the
   fallthrough live**. Also corrected: the classifier at `020:0B1A` is *not*
   the operand-count authority (it disagrees with the handlers on five
   opcodes; `0x0C` takes 3 operands, not 2 — worth 25 points of coverage on its own), and
   `0x00` is the `END` instruction, not a separator. Result: **29/29 headers
   parse and 97.7 % of the corpus payload decodes from control flow alone**,
   the 1.9 % residue being trailing data tables. `work/ecl.py --validate`.
   The inline text is fully decoded (6-bit packed ASCII): `work/ecl.py
   --text` recovers 1,826 strings / 115,502 chars of real game prose, each one
   now anchored to a decoded instruction rather than a byte scan.
   **The address space is resolved too**: five regions from `045:070B` +
   `045:0E2E`/`045:0C93`, three of words, one of the script's own bytes, and a
   region-4 switch onto game state that puts **party X/Y/facing at
   `0xC04B`/`0xC04C`/`0xC04D`** — the last as `facing/2`, independently
   confirming the 4-directional finding from the dungeon view.
   **Opcode semantics: 27 of 61 read** (`work/eclops.py <op>` prints any
   handler with its far calls resolved). Beyond control flow and text: `0x09`
   `SET`, `0x03` `CMP` (and with it the six flags, so `0x16`-`0x1B` are
   `== != < > <= >=`), `0x04`-`0x07` `ADD`/`SUB`/`DIV`/`MUL`, `0x08` `RANDOM`,
   `0x2A` indexed load, `0x2F`/`0x30` `AND`/`OR`. `0x08` pinned the resident
   `05BB:0C94` as Turbo Pascal `Random` — a `seed*0x08088405+1` LCG at
   `DS:0x438A` that **the port must reproduce bit-exactly**.
   Also read: `0x27` `MKITEMS` (the item-creation instruction) and `0x1C`
   `DROPITEMS` (its inverse), plus `045:0489`, the forward-range probe, whose
   step arithmetic writes down the **cardinal directions — 0 = −Y, 2 = +X,
   4 = +Y, 6 = −X**, even values only.
   `0x0B` `ADDMONS` is the encounter-setup instruction, and reading it added
   three far-pointer fields to the **285 B character/monster record** —
   `+0x7F` (a second list), `+0xC8` (inventory head, third independent
   confirmation) and `+0x104` (**next participant**) — plus the encounter list
   head `DS:0x5CF4` and its **hard cap of 63 participants** at `DS:0x4392`.
   `0x29` `ENCOUNTER` is the encounter prompt — three message strings, five
   option bytes, and an outcome of 1, 2 or 3 written back to the variable
   operand 4 names; the corpus shows its strings are announcements like
   *"THE MONSTERS STAND READY"*. `0x0C` is the same mechanism with the prompt
   removed (identical setup and range clamp, no store site at all).
   Also: `0x35` `STOREIDX` (the exact counterpart of `0x2A`'s indexed load),
   `0x0D` `ENCNEAR`, and six short handlers (`0x0F 0x31 0x33 0x34 0x39 0x3D`)
   read in structure but ending in unit `124`/`198` calls this pass did not
   chase. `0x34`'s handler reads the operand *index* out of an uninitialised
   local — a latent bug in the shipped code, and it occurs exactly once in the
   corpus.
   **Tally: 32 named, 1 partial (`0x24`), 6 structure-only, 22 untouched**
   (`0x0A 0x0E 0x10 0x14 0x1D 0x1E 0x20 0x21 0x22 0x23 0x28 0x2B 0x2C 0x2D
   0x2E 0x32 0x36 0x37 0x38 0x3A 0x3B 0x3C`). See
   `analysis/data-formats.md` §`ECL*.DAX`.
   The shared 285 B character/monster record (`CHRDATA*.SAV`/`MON*CHA.DAX`)
   is **partially decoded** (2026-08-21) — name, ability scores, and 5 more
   fields, see the `CHRDATA1-6.SAV` row above and
   `analysis/data-formats.md` §The 285 B character/monster record; most of
   the record is still TBD. The 63 B item record's **container is RESOLVED
   (2026-08-22)** — ECL opcode `0x27`'s loader walks a block in 63-byte steps
   with no header, and 46/46 `ITEM*.DAX` blocks, 105/105 `MON*ITM.DAX` blocks
   and all 6 `CHRDATA*.ITM` files are exact multiples of 63, so an item file is
   a flat `N × 63 B` array; the record's internal fields are still undecoded.
   The 9 B record behind `MON*SPC.DAX`/`CHRDATA*.SPC` is **RESOLVED as a
   container and refuted as a spell list (2026-08-22)**: it is the list hanging
   off character record `+0x7F`, 9 B nodes chained at `+5`, files are flat
   `N × 9 B` arrays (42/42 blocks, 4/4 files), and the shipped cleric and
   magic-user have **zero** records while a fighter has four — so whatever byte
   0's type selector means, it is not memorised spells. See
   `analysis/data-formats.md` §The 9 B `+0x7F` record. `SPRIT*.DAX` is **RESOLVED
   (2026-08-22)**: a multi-frame sub-container, `[u8 count]` + per frame
   `{4 B, u16 height, u16 widthBytes, 13 B, height*widthBytes*4 pixels}`, the
   offset chain landing exactly on the block length for **88/88** blocks, and
   the frames render as one monster at the dungeon view's three distance ranks
   (`work/probe/sprit/`). `ITEMS` is **RESOLVED (2026-08-22)**: a
   2-byte header + **128 × 16 B** item-*type* records, read by unit `069`
   (`Reset`, `Seek` past the header, `BlockRead` into `DS:0x54E0`), and the
   63 B item record's **`+0x2E` is the index into it** — verified against all
   667 item records in the game, every value 1-93. **Field-level work
   (2026-08-22):** item record `+0x00` is a Pascal `ShortString` holding the
   item's **name**, and in the 16 B `ITEMS` record fields 2/3 and 9/10 are two
   `(count, sides)` **dice pairs** (`f3`/`f10` take only the polyhedral values
   `{0,1,2,3,4,6,8,10,12,20}`; `058:12C0` multiplies one out), field 13 is a
   **7-bit mask** and field 14 a flag byte. `SAVGAMA.DAT` is **RESOLVED
   (2026-08-22)**: ten `BlockWrite`s summing to exactly 13,137 B — the region
   number, the ECL interpreter's four variable/script buffers (2,048 + 2,048 +
   1,024 + 7,680), the 5-byte party block at `DS:0x6A0B`, three more bytes and
   a 328-byte local. Verified by decoding the embedded ECL slice: it is region
   2's script, matching `ECL2.DAX` block `0x14` entry for entry. Only the last
   two records (1 B and 328 B, both stack locals) are untraced. Cross-reference each against the
   routine in `GAME.OVR` that reads it — a format is not resolved until the
   reader agrees.

7. ~~The 9 unknown header bytes~~ **RESOLVED (2026-08-21)** — frame-repeat
   count + a CGA-only colour-reduction table, irrelevant to the EGA port. See
   §Image header + pixel format above and `analysis/executables.md` §Unit
   `18E`. ~~Still open: the `u32` frame tag in `.PIC`~~ **RESOLVED (2026-08-22)**:
   it is the frame's **display duration**, `tag × 70 ms`. The driver `11D:0251`
   multiplies it by 7 and compares against elapsed time from `198:0AF0`, which
   counts hundredths of a second. Shipped values run 0-20 (0 to 1.4 s), not
   `0x00`-`0x0F` as the partial sample suggested. The port needs it: pacing is
   per-frame, not one global rate.

8. **~~Dynamic oracle — POOL.CFG~~ RESOLVED (2026-08-21).** `INSTALL.EXE`
   driven to completion under QEMU by `work/drive_install.py`; the `POOL.CFG`
   it writes is five CRLF lines — display letter, sound letter, two paths,
   full-intro flag — pinned by three installs that differ only in the settings.
   See `analysis/dos-oracle.md` §6. Lines 3 and 4 are resolved in §9: line 3 is
   the game-data path (`.DAX`/`.PIC`, units `0x019`/`0x020`/`0x069`) and line 4
   the character/save path (`charlist.txt`, `.CHA`/`.SAV`/`.ITM`/`.SPC`, unit
   `0x0BE` alone) — a disjoint split, equal on disk only because a hard-disk
   install puts both in `C:\POOLRAD\`.
   With a real `POOL.CFG` in hand `START.EXE` gets past its config check and
   sets **INT 10h mode 0Dh** (EGA 320x200, `make oracle-hd`), and `POOL.CFG`
   line 1 is what selects it — `C` gives mode 04h instead. **The palette is
   settled: the game never programs one** (`analysis/dos-oracle.md` §8). No
   `0x3C0`/DAC access and no `AH=10h` exists in either binary, byte-complete,
   so the colours are the BIOS default the mode set loads — the standard EGA
   16-colour palette for the port. The `io = debug` / grep-`0x3C0` plan in §4
   could never have settled it and should not be retried (§7).

   *Superseded, kept for the reasoning:*
   **Dynamic oracle — harness DONE, question OPEN.** `make oracle` runs the
   game headless under DOSBox-X with `int10`/`io`/`vga` logging
   (`analysis/dos-oracle.md`). It reports **zero** `INT 10h` calls and **zero**
   video-port writes from the game — but that proves nothing yet, because
   `START.EXE` stops before touching hardware: no `POOL.CFG` exists and only
   `INSTALL.EXE` creates one. Next: recover the `POOL.CFG` format from
   `work/start16.txt`, or run with a real video driver so `INSTALL.EXE` can be
   driven and read. The sibling QEMU harness does the latter headless —
   `sendkey` to drive, `screendump` to read the prompts, mtools to read back
   the created `POOL.CFG` (`analysis/dos-oracle.md` §4, cross-project §6).
   Then the palette settles in one run.

9. **Extend the rebuild outward**: `work/rebuild.py` reproduces `START.EXE` and
   `GAME.OVR`. The remaining layers are the ARC archives and the two `.img`
   floppies — `work/arcverify.py` already checks the ARC layer by CRC, so this
   is mostly packaging.

## Cross-port documentation rule

When a change or investigation establishes a confirmed finding, correction,
tool/workflow lesson, or other fact that can help more than this repository,
update the authoritative shared documentation in the same session and
regenerate any derived copies. Always do this; do not leave transferable
findings only in chat, code, or generated output. Keep project-specific details
in the local canonical document and upstream the reusable rule with its
evidence, scope, and status.
