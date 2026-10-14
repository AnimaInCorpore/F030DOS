# Project: Wing Commander (1990, Origin Systems) — Decode, Port, Verify

**Goal:** analyze the DOS game *Wing Commander* (1990) — code and data — far
enough that the whole game runs natively on an Atari Falcon030, with every
ported subsystem traceable to the DOS behaviour it reproduces.

This is a **port**, not a reassembly: the DOS original is the authority for
semantics and data layouts, the Falcon owns video, input, timing, memory and
audio hardware. The analysis discipline is otherwise the same as the sibling
`F030Underworld` project — verify, quote, document, then implement.

## Mandatory function-level port policy

The hashed 1990 `WC.EXE` DOS binary and its captured execution are the sole
behavioural authority. `../wc1-re`, disassembly, reassembly, the browser
reference and Falcon code are evidence or implementations; none may overrule
DOS. For every function represented in browser or target code, maintain the
`METHOD.md` §4.2 function record: DOS identity and evidence, recovered contract
and fixtures, browser/target symbols, and an explicit difference ledger against
DOS. Record and prove even “no difference”; an unresolved difference is
`Unproven` and cannot enter a supported path. Start the deterministic browser
reference with the first function; use controlled experiments to identify its
role, contract, side effects and Falcon seam, then confirm each finding against
DOS before recording it. Land its fixtures before or with each supported target
slice.
## Implementation-source links

Every JavaScript/browser and 68000/m68k function source that implements or exposes a recovered DOS function must carry an adjacent comment or docstring linking to the durable function record and naming the disassembled DOS function symbol plus canonical range/entry (for example, `DOS: FUN_0000_1234; record: <stable-function-record>`). Use the same stable function ID in both implementation sources; a separate map or file-level comment is not enough. Code with no DOS counterpart must say `N/A - platform replacement` or `Target artefact` at the definition.


## Workspace

| Path | Content |
|---|---|
| `WC_Disk1..3.zip` | Source disks (3× 3.5″ DOS disks, 1990-09, 3,373,737 B on disk / 57 files). Supplied by the user. **Never modify, never commit.** |
| `release/WC1DATA/` | Extracted DOS data (57 files, `make data`). Derived — the analysis target. Ignored by git. |
| `release/WC1CACHE/` | Host-converted big-endian caches (`MISSION.BIN`, `make falcon-data`). Derived. Ignored. |
| `release/*.tos` | Built Falcon executables (`wc1.tos`, `wc1_debug.tos`). Ignored. |
| `analysis/` | Verified findings, dumps, format docs (`analysis/<topic>.md`). |
| `docs/DOS-SOURCE-MAP.md` | DOS-function → Falcon-owner contract map. |
| `PORTING.md` | Roadmap and the per-slice porting plan. |
| `src/`, `include/` | Falcon 68030 sources (`*.s` assembly, `resources.c`/`c2p.c` freestanding C). |
| `tools/` | Host-side converters, contract checks, smoke tests, frame capture. |
| `build/` | Captured frames and diagnostics. Ignored. |
| `docs/CROSS-PROJECT.md` | Shared RE-technique ledger of the sibling F030 projects. **Generated** by `../F030Method/gen_cross_project.py` — edit the body there, never this copy. |
| `../wc1-re/` | Reconstructed WC1 source — graded supporting evidence only; it reconstructs the 1996 Kilrathi Saga Win32 build, not the 1990 DOS target. |
| `../F030Method/` | The family's parent repo: `METHOD.md` (the four-phase playbook and the phase-4 fidelity/grounding policies), the ledger generator, and the master DOS-oracle harness (`dos/`, with `sync.py`). |
| `../F030Comanche/` | Falcon 68030/Videl implementation reference. |
| `../F030Arcade/third_party/` | vasm, vlink, TOS images, Hatari support files. |

## Conventions

- `WC_Disk*.zip` is the untouched reference; everything under `release/` is
  derived and reproducible from `make data` + `make falcon-data`.
- One doc per format/component in `analysis/`; **verified header bytes must be
  quoted, not guessed.** Mark anything unproven `TBD`, never as fact.
- **Update the docs as you work:** every new finding (format, tool quirk,
  workflow, next step) goes into the right `analysis/*.md` (or `AGENTS.md`
  §Next steps) immediately — never leave results only in the chat log.
  Tool-usage lessons (Hatari/vasm/vlink/m68k-elf-gcc behaviour) go into the
  doc for that tool.
- `../wc1-re` is supporting evidence for the 1990 DOS binary, not authority
  for game semantics or data layouts. DOS VGA, BIOS and extender code is **not**
  translated literally.
- **Two things about that evidence have to stay visible, because a readable
  reconstruction is the easiest evidence to overrate** (`../F030Method/METHOD.md`
  §4.2, fourth rank). First: `wc1-re` reconstructs *Wing Commander* as shipped
  in the **1996 Kilrathi Saga Win32 re-release**, while this port targets the
  **1990 DOS** game and reads DOS data files. The delta between the two builds
  is not claimed to be large — it is *unmeasured*, which is a different state
  and must not be written as if it were zero. Second: `wc1-re`'s own
  `make report` scores per-function machine-code similarity against the retail
  executable, so the tree is explicitly not uniform; when a port function cites
  a reconstruction function, record its grade and the DOS evidence that
  confirms it. `analysis/wcexe.md` identifies DOS `WC.EXE` as the same Borland
  Turbo C++ 1990 model as `../F030Underworld`'s `UW.EXE`, so the family's
  disassembly machinery is available whenever the DOS authority needs reading.
- **When a finding here is transferable** — a technique, a trap, a correction —
  upstream it in the same session that records it locally: RE technique or tool
  gotcha to `../F030Method/gen_cross_project.py`'s body (then re-run it), phase
  or port policy to `../F030Method/METHOD.md`, harness fix to
  `../F030Method/dos/` (then `python dos/sync.py --push`). Project-local
  findings — a format, an address, a routine — stay in `analysis/`.
- Every ported function gets a DOS function record, browser fixture and Falcon
  validation target before it is folded into a supported main-loop path.
- DOS `short`-sized state stays 16-bit where the recovered source depends on
  it; Falcon pointers and addresses are 32-bit. World vectors keep the DOS
  24.8 fixed-point representation (`FIX_SHIFT = 8`).
- Falcon output is 16-bit RGB565 true colour. Rendering stays linear 8-bit
  indexed until the final palette expansion — no VGA bitplane emulation.
- **DOS is the behavioural authority; Hatari checks the Falcon implementation**:
  after any change to the presented picture, capture a target frame and look at
  it, then compare the applicable DOS contract. Hatari alone cannot establish
  DOS fidelity. See `analysis/hatari.md`.
- Original game data is supplied by the user and is never committed.

## Distribution & install chain (verified)

- **Three DOS disks**, 57 files, no archiving or packing at the disk level —
  every file is stored plainly and `make data` simply unzips all three into
  `release/WC1DATA/`.
- **`INSTALL.DAT`** (928 B) is the logical-file table: **58 × 16-byte records**,
  the last one zero-filled as terminator, so 57 real entries — exactly the 57
  shipped files. Record layout (matches `DiskFileRecord` in
  `wc1-re/include/wcdata.h:491`):

  ```
  [char name[13]] [s8 diskNumber] [u8 fileClass] [u8 logicalFile]
  ```

  `logicalFile == 0xFF` means "not addressable as a logical file"
  (`DISK.00n`, `INSTALL.DAT`, `INSTALL.EXE`, `GAME.PAL`, `CONVERT.PAL`,
  `STRAX.DRV`). The runtime looks resources up by **logical id**, never by
  name. Full decoded table in `analysis/data-formats.md`.
- Verified logical-id rules used by the port: `MODULE.000` = **16**
  (`MISSION_ARCHIVE_LOGICAL`), `PCSHIP.Vnn` = `nn + 18` (the DOS
  `mode + 17` cockpit rule), and `SHIP.Vnn`/`SHIPTYPE.Vnn` = `nn + 23` (the
  DOS `type + 22` rule). Capital ships (`SHIP.Vxx`) and fighters
  (`SHIPTYPE.Vxx`) **share one type-number space** — no shipped `nn` collides.
- **`WC.EXE` expects its data in the working directory**; the Falcon port
  reads everything through a `WC1DATA\` prefix under the release folder.

## `WC.EXE` (302,384 B, 16-bit Borland Turbo C++ 1990)

The behavioural authority for the port. `../wc1-re` may accelerate analysis,
but every inferred function contract or difference is checked against this
1990 DOS binary and its captured execution.

- MZ header (raw bytes @ file 0x00, verified):
  `4d 5a 80 00 03 01 5b 04 20 01 00 00 ff ff 20 1f | 80 00 00 00 00 00 00 00
  3e 00 00 00 01 00 fb 30 6a 72 …`
  → `e_cblp = 0x0080`, `e_cp = 0x0103` (259), `e_crlc = 0x045B` (1,115),
  `e_cparhdr = 0x0120` (288 par = 4,608 B), `e_ss = 0x1F20`, `e_sp = 0x0080`,
  `e_ip = 0x0000`, `e_cs = 0x0000`, `e_lfarlc = 0x003E`, `e_ovno = 0`.
- `0x30FB` / `0x726A` at file 0x1E/0x20 — the **Borland linker signature**,
  byte-identical to `UW.EXE` in the sibling `F030Underworld` project.
- CRT string @ file `0x12EC4`: `Turbo C++ - Copyright 1990 Borland Intl.` —
  **the same compiler as UW.EXE**, so the same 16-bit disassembly model
  applies (`e asm.bits=16`, Borland CRT entry chain).
- **Borland VROOM overlays, not self-loading.** Loader image =
  `(e_cp−1)×512 + e_cblp = 132,224 B (0x20480)`; the file continues for another
  **170,160 B (0x298B0)**. That tail is the overlay payload: **910 `INT 3Fh`
  stubs (`CD 3F`)** sit in the load module and **none** in the tail, and
  `Runtime overlay error` @ file `0x1440` is the manager's error path. This is
  where WC.EXE **differs** from UW.EXE, whose tail is self-loaded contiguously
  — mapping WC.EXE's tail flat would produce plausible-looking nonsense.
  Overlay-table layout: **TBD**.
- Other verified strings: `OriginFX Graphic System / Chris Roberts / John
  Miles` @ `0x157AF`, `OriginFX Sound System by Herman Miller` @ `0x157E0`,
  `Origin-FX drivers` + `Expanded Memory fully used.` @ `0x15D82`,
  `Loading WING COMMANDER.  Please` @ `0x1302A`.

See `analysis/wcexe.md`.

## Data inventory & format findings (headers verified)

Full tables in `analysis/data-formats.md`. Summary:

### Origin packet container — **RESOLVED**
**47 of 57 shipped files** are Origin packets (`.VGA`, `PCSHIP.Vxx`,
`SHIPTYPE.Vxx`, `SHIP.Vxx`, `MODULE.000`, `BRIEFING.000`, `MUSIC.MID`,
`FONTS.FNT`, `*.DRV`, `CAMP.000`, `INTRO.DAT`, `WINGLDR.TIM`):

```
[u32LE declared_size]              @0  == file size
[u32LE entry[0..N-1]]              @4  directory; entry[0].offset == directory end
    bits 31..24 = compression: 0 = raw, 1 = Origin LZW, 0xFF = absent
    bits 23..0  = section start offset
```
`section_count = (entry[0].offset >> 2) − 1`; section end = next entry's
offset, or `declared_size` for the last. A type-1 section starts with a
`u32LE` decompressed size, then a 9–12-bit LZW stream (clear 0x100, stop
0x101, first 0x102, max 0x1000).

**New finding (2026-08-20):** compression byte **`0xFF` marks an absent
section** and is always **zero length** (verified on `SHIP.V21` ×20,
`COCKPIT.VGA`, `PCSHIP.V04`, `BRIEFING.000`, `SHIPTYPE.V29`, `TM.DRV`,
`SUPERTM.DRV`). `resource_load_packet()` currently rejects anything that is
not 0 or 1, so those holes read as a hard failure rather than "empty" — see
§Next steps 5.

### `GAME.PAL` (1,120 B) — **RESOLVED**
Standard IFF ILBM, not a packet: `46 4f 52 4d 00 00 04 58 49 4c 42 4d 42 4d
48 44 00 00 00 14 00 01 00 01 00 00 00 00 08 02 00 00` → `FORM` 1,112 /
`ILBM` / `BMHD` 20 B (w=1, h=1, nPlanes=8, masking=2), then `CMAP` with 256
RGB triples. The port expands it to an RGB565 lookup table and applies the
DOS cockpit reset of slots 185–191 (`$BF` = dark blue, not raw-palette black).

### `MODULE.000` (22,085 B) — campaign archive, **sections 0–3 RESOLVED**
`45 56 00 00 1c 00 00 01 06 01 00 01 4f 1a 00 01 …` → declared 22,085 (= file
size), directory 28 B, **6 sections, all Origin LZW**. Sections 0–3 carry the
mission headers, nav points, objectives and 32 ship records mirrored in
`include/wc1_data.h` (`MissionHeaderDisk` 0x18, `MissionNavPointDisk` 0x4D,
`MissionObjectiveDisk` 0x40, `MissionShipDisk` 0x2A). **Sections 4–5: TBD.**

### Sparse shape frames — **RESOLVED** (per `wc1-re/src/killbrd.c`)
`DecodeShapeFrame()` run-command stream, drawn straight to the indexed buffer
with DOS transparent gaps preserved. Backs the cockpit, fighters, capital
ships, projectiles and explosion sets.

### Not yet decoded
`MUSIC.MID` (41 sections) and `WINGLDR.TIM` audio, `COMMUNIC.DAT` (12,320 B,
not a packet), `SAVEGAME.WLD` (6,624 B, not a packet), `CONVERT.PAL`
(256 B raw), `BRIEFING.000`/`BRIEFING.VGA`/`RECROOM.VGA`/`TALKING.VGA`/
`PILOTANM.VGA`/`SCRAMBLE.VGA` scene packets, `*.DRV` sound drivers.

## Toolchain (macOS-native)

| Tool | Status | Use |
|---|---|---|
| vasm `vasmm68k_mot` (`../F030Arcade/third_party/vasm/`) | installed | 68030 assembly (`-Felf -m68030`) |
| vlink (`../F030Arcade/third_party/vlink/`) | installed | TOS linking (`-b ataritos -tos-flags 1`) |
| `m68k-elf-gcc` 16.2.0 (Homebrew) | installed | freestanding C (`resources.c`, `c2p.c`) |
| Hatari (Homebrew) | installed | **dynamic oracle**, Falcon machine + frame capture |
| TOS 4.04 (`../F030Arcade/third_party/tos/tos404.img`) | installed | Falcon boot ROM (4.02 and 2.06de also present) |
| Python 3.14.7 | installed | converters, contract checks, format probes |
| ImageMagick `magick` + `timeout` (coreutils) | installed | RGB565 → PNG frame capture |
| `unzip` | installed | disk staging (`make data`) |
| `dosbox-staging` + `ASM56000` (`../F030Comanche`) | optional | legacy DSP56001 diagnostic only |

Override any path on another machine: `make VASM=… VLINK=… M68K_CC=… TOS=…`.

## Falcon test machine

Hatari, `--machine falcon --monitor rgb --mmu true --cpu-exact true
--compatible true --patch-tos true`, TOS 4.04. Sound is off in every automated
run.

`MEMSIZE` defaults to **14** MB in the Makefile, but the **design target is a
stock 4 MB Falcon** (`PORTING.md`: the three 72 KiB resource slots are sized to
fit beside the two RGB565 pages and the indexed surface). Verified 2026-08-20:
the title sequence renders **identically at `MEMSIZE=4` and `MEMSIZE=14`** —
same Videl base `$12EA34` at VBL 2800. Whether the *flight* slice with all
three resource slots occupied still fits in 4 MB is **untested** — see
§Next steps 10. See `analysis/hatari.md` for the capture recipe and its gotchas.

## Verification harness (all green, 2026-08-20)

| Command | Checks | Last result |
|---|---|---|
| `make build` | vasm + vlink + m68k-elf-gcc | `wc1.tos` 70,637 B, `wc1_debug.tos` 103,453 B |
| `make test` | static porting contracts (`tools/check_contracts.py`) | `WC1 Falcon contracts: OK` |
| `make truecolor-smoke` | indexed → RGB565 expansion | `64000 indexed pixels, 128000 display bytes` |
| `make falcon-data-smoke` | `MISSION.BIN` vs. the DOS packet | `237120 bytes, mission 4 entry-nav=0 player=1; source-equivalent` |
| `make resource-smoke` | palette / cockpit / sparse decoder vs. staged data | `status=007b palette=256 cockpit-sections=9 pixels=286` |
| `bash tools/grab-frame.sh <vbl> <png>` | live Falcon frame | title logo confirmed at VBL 2800 |
| `make fixture` | asset-free integration path | refuses to overwrite staged data |

One known build warning: `Attributes of section .data were changed from
r--- to rw-- in hud.o` (vlink) — harmless, `hud.s` puts mutable state in a
read-only-declared section.

## Next steps

**0. ~~Stage and decode the disks~~ DONE** — 57 files, `INSTALL.DAT` table and
   Origin packet/LZW container fully resolved; 47 packets inventoried.
1. **Flight rendering completeness** — the diagnostic renderer now merges its
   represented stars/dust, fighters, projectiles/sparks, and `EXPLOSION1`
   effects through a bounded far-to-near queue
   (`analysis/functions/FlightSceneDepthMerge.md`), but that seam is
   **Unproven**: the 1990 overlay entries, original allocator slot/tie order,
   browser fixture, and DOS capture are still absent. Missiles, hazards,
   capital onboard effects, and every other object class remain open.
2. **Behaviour dispatcher & pilot goals** (`wc1-re/src/brains.c`,
   `src/logic.c`) — current hostiles only turn toward the player and fire.
   Missiles, capital onboard explosions/shockwaves and asteroid collision
   fragments belong with this slice.
3. **Campaign packet completion** — `MODULE.000` sections 4–5, then the
   subsequent campaign archives; extend `tools/convert_data.py` and
   `include/wc1_data.h` in lock-step and re-run `make falcon-data-smoke`.
4. **Cockpit interaction** — scanner, VDUs, comms and the pilot-hand
   resources; `PCSHIP.Vxx` sections beyond the retained section seven.
5. **~~Absent-section handling~~ DONE (2026-09-10)** —
   `resource_load_packet()` accepts a verified compression `0xFF` zero-length
   hole as an empty fixed-index section. `PCSHIP.V04` section 1 is covered by
   `make resource-smoke`; direct 1990 DOS return/error behaviour remains
   Unproven before using these holes in a supported room/campaign path.
6. **Non-flight rooms** — briefing, rec room, scramble, talking heads,
   save/pilot/campaign screens (`BRIEFING.*`, `RECROOM.VGA`, `SCRAMBLE.VGA`,
   `TALKING.VGA`, `PILOTANM.VGA`, `SAVEGAME.WLD`).
7. **Audio** — `MUSIC.MID`, `WINGLDR.TIM`, `*.DRV`. Deliberately deferred:
   nothing in the current game loop, build or acceptance checks may depend
   on it until the flight slice is complete.
8. **Time policy** — DOS seeds the title asteroid field and star layout from
   the clock; the Falcon uses a repeatable seed. Pick a target-side policy
   and record it here.
9. **Version control** — this workspace is **not a git repository** (every
   sibling project is). `.gitignore` is already correct; `git init` when the
   owner wants history.
10. **Confirm the stock-4 MB target** — the title sequence is verified at
    `MEMSIZE=4`, the flight slice is not. Capture a flight frame at
    `MEMSIZE=4` with all three resource slots loaded; if it fails, either
    lower the default `MEMSIZE` claim in `PORTING.md` or fix the allocation.

## Cross-port documentation rule

When a change or investigation establishes a confirmed finding, correction,
tool/workflow lesson, or other fact that can help more than this repository,
update the authoritative shared documentation in the same session and
regenerate any derived copies. Always do this; do not leave transferable
findings only in chat, code, or generated output. Keep project-specific details
in the local canonical document and upstream the reusable rule with its
evidence, scope, and status.
