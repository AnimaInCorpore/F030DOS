# UW.EXE — Static Analysis (Phase 1)

Target: `work/expanded/UW.EXE` — 561,744 bytes (0x89250). The game executable of
*Ultima Underworld* (1992, Sierra).

## 1. Identity (verified)

- **16-bit DOS EXE**, Borland **Turbo C++ (1990)** — CRT string at file `0x5F2F4`:
  `Turbo C++ - Copyright 1990 Borland Intl.`
- No `NE`/`NP` signature anywhere in the file; there is no `e_lfanew` field —
  `e_lfarlc = 0x3E` means bytes `0x3E..0x3F` are already the first relocation
  entry, so a naive 4-byte read at file `0x3C` straddles the header/relocation-
  table boundary and happens to print `0x10000` (see §2).
- Disassembly mode: **16-bit x86**. Load base assumption: **file offset 0 → 0x10000**
  (standard lowest 16 KB boundary).

## 2. MZ header — ✗ **rewritten 2026-08-20, see `analysis/reassembly.md` §2**

The previous version of this table had `e_ip`, `e_cs` and `e_lfarlc` shifted by
one field, mis-multiplied the image size, and invented an `e_lfanew`. All four
errors and the reasoning that fixed them are in **`analysis/reassembly.md` §2**,
which is now the authoritative container reference (it is verified continuously:
the file is rebuilt from generated source to the same SHA-256).

Raw bytes, file `0x00..0x1F` (re-read from the file, not from the old note):

```
4d 5a 30 01 36 03 68 0c  20 03 00 00 ff ff 8b 63
80 00 00 00 00 00 c5 0e  3e 00 00 00 01 00 fb 30
```

| off | field | value | note |
|---|---|---|---|
| 0x02 | e_cblp | 0x0130 (304) | bytes in last page |
| 0x04 | e_cp | 0x0336 (822) | pages |
| 0x06 | e_crlc | 0x0C68 (3,176) | relocation entries |
| 0x08 | e_cparhdr | 0x0320 (800 par) | header = 0x3200 |
| 0x0A | e_minalloc | 0 | |
| 0x0C | e_maxalloc | 0xFFFF | |
| 0x0E | e_ss | 0x638B | initial SS (load-relative) |
| 0x10 | e_sp | 0x0080 | |
| 0x12 | e_csum | 0x0000 | |
| 0x14 | **e_ip** | **0x0000** | ✗ was given as 0x0EC5 |
| 0x16 | **e_cs** | **0x0EC5** | ✗ was given as 0x0000 |
| 0x18 | e_lfarlc | 0x003E | relocation table @ file 0x3E |
| 0x1A | e_ovno | 0x0000 | no *DOS* overlays (Borland does its own) |

- **Image size** `(822−1)×512 + 304 = 420,656 = **0x66B30**`. ✗ The old note said
  `0x66250` and inferred a "zeroed BSS at the boundary" from the 0x8E0 gap; there
  is no gap. 0x66B30 is exactly where the `FBOV` overlay pool starts.
- ✗ **There is no `e_lfanew`.** `e_lfarlc = 0x3E`, so the u32 read at 0x3C ran
  into the first relocation entry and produced the phantom `0x10000`. Likewise
  the "e_reloc = 0x30FB at 0x1E" is not a field — 0x1C..0x3D is TLINK's reserved
  area, and `e_crlc` at 0x06 is the only relocation count.

## 3. Entry point & load model

- Entry CS:IP = **0x0EC5:0x0000** → file offset
  `e_cparhdr*16 + (e_cs << 4) + e_ip = 0x3200 + 0xEC50 =` **0x11E50**.
- ✗ **The old entry point was wrong** (`0x1010:0x0EC5` → linear 0x10FC5 → file
  0xFC5), because §2 had `e_ip` and `e_cs` swapped. It was then described as
  *"valid code: a dispatcher-style function using `bp`-relative locals … It is
  mid-function in appearance, i.e. the linker entry sits inside a larger code
  block — normal for Borland linkers"*. File 0x10FC5 actually holds
  `ec ed ee ef f0 f1 …`, a byte ramp — data. **When a finding needs an excuse
  for why it looks wrong, check the field it rests on.**
- File 0x11E50 needs no excuse; it is the standard Borland `C0.ASM` start:
  `mov dx,0x5c0f` (DGROUP, patched by relocation 0) `/ mov [cs:0x23c],dx /
  mov ah,0x30 / int 0x21 / mov bp,[2] / mov bx,[0x2c] / mov ds,dx`.
  Full listing and the three-way DGROUP cross-check: `reassembly.md` §2.
- ~~**Open question (boot test):** the 141 KB tail beyond file 0x66250 is *not*
  loaded by the DOS loader … the tail must be self-loaded … read
  0x66250..0x89250 into **0x76250** (contiguous with the loaded image)~~ —
  **answered on the running game, and the guess was wrong** (§13.3). The tail is
  a Borland `FBOV` **overlay pool**: nothing self-loads it contiguously, and the
  `0x10000 + file_off` linear mapping assumed here (and used by the §4 sweep) is
  not the runtime mapping. Measured: the *image* sits at `file + 0x2760`
  (load segment 0x0596); overlays are swapped into a buffer above the stack at
  addresses that vary per load.

## 4. Code layout (capstone sweep, 16-bit, base 0x10000)

Sweep: `python C:/Arbeit/F030TieFighter/work/sweep16.py work/expanded/UW.EXE 0x10000 0x000 0x89250 work/uw16.txt`

- **2,685 candidate functions, 363,841 B (64.8%)** of the file.
- Table: `work/uw16.txt` — `start size ntargets` (start = 0x10000 + file offset).
- Note: "functions" starting below file 0x3106 (e.g. 0x1016A) fall inside the
  header/relocation zone and are likely false positives.
- Code density is fairly uniform from file 0x3100 to EOF (5–77 fn per 64 KB),
  with sparse regions at 0x4E000–0x5F000 and 0x60000–0x6D000 (data: strings,
  tables).

Largest functions (by size, B):

| start | size | targets |
|---|---|---|
| 0x015A3A | 3,214 | 1,604 |
| 0x08479B | 2,974 | 1,035 |
| 0x097314 | 2,934 | 1,029 |
| 0x01BD9B | 2,734 | 1,174 |
| 0x051576 | 2,667 | 1,334 |
| 0x026244 | 2,560 | 965 |
| 0x014E9F | 2,507 | 1,245 |
| 0x0856D0 | 2,478 | 1,066 |

0x015A3A contains the "Runtime overlay error" string (0x15A6C) — a strong hint at
the self-load/overlay machinery (see §3).

## 5. Relocation table @ file 0x3E — ✗ **format corrected 2026-08-20**

- **e_crlc = 3,176 entries × 4 B → spans 0x3E..0x31DE**, then 34 zero bytes of
  slack to the end of the header at 0x3200.
- Format: standard DOS **`(offset u16, segment u16)`**; target file offset =
  `0x3200 + (segment << 4) + offset`.
- **All 3,176 entries are valid**: every target is inside the image, all are
  unique, 53 distinct segments, highest target file 0x61546.
- Entry 0 = `(offset 0x0001, segment 0x0EC5)` → file **0x11E51**, the `0x5C0F`
  immediate of `mov dx,0x5c0f` at the entry point: the first fixup patches
  DGROUP in the CRT start, as `C0.ASM` requires.
- ✗ **The previous reading was `(page u16, offset u8, pad u8=0x0E)`**, from which
  this section concluded that only *"the first ~700 entries are valid … the
  remainder contain out-of-range pages (Borland-specific extension or a second
  table)"*, and that entry 0 patched file 0x1C5. All of that is an artefact of
  the wrong stride — and it propagated into `cross-project.md` as "UW1's
  relocation table … carries junk entries with pages past `e_cp`, which crash a
  stock loader" (withdrawn there too). Nothing about the table is unusual.
- Also withdrawn with it: the claim that "file 0x1C0–0x1E0 is a table of u32 far
  pointers … object/vtable-like". That range is inside the relocation table
  (0x3E..0x31DE); the "far pointers" were relocation records.

## 6. String pool

- Full dump (300 strings ≥ 6 ASCII): `work/uw_strings.txt` (`offset  string`).
- Confirms the complete data-access map (all previously known refs plus new ones):
  `DATA\uw.cfg`, `DATA\weapons.dat`, `DATA\weapons.cm`, `DATA\skills.dat`,
  `DATA\chrgen.dat`, `DATA\chargen.byt`, `DATA\cmb.dat`, `DATA\cnv.ark`,
  `DATA\lev.ark`, `DATA\grave.dat`, `DATA\strings.pak`, `DATA\blnkmap.byt`,
  `DATA\pres1.byt`, `DATA\pres2.byt`, `DATA\main.byt`, `ZDATA\objects.dat`,
  `comobj.dat`, `data/pals.dat`, `data/allpals.dat`, `player.dat`,
  `babglobs.dat`, `bglobals.dat`, `sounds.dat`, `uw00.xmi`, `SAVE0\`,
  `SAVE_REG`, `uwedit.exe`, plus fonts (`font5x6i.sys`, `font5x6p.sys`,
  `font4x5p.sys`, `fontbig.sys`, `fontchar.sys`).
- Error strings: "Runtime overlay error" (0x15A6C), "Divide error",
  "Underworld exiting, divide by zero.", "Cannot run Underworld.",
  "Could not read data." / "Could not write data.", "Resource problem or internal
  error.", "Error code XXXX", "Not enough disk space for save game.",
  "gr no parse data %s", "Thank you, and you, may i add, for using the Underworld
  Editor$".
- Save games: `SAVE0\` is the working directory; `SAVE1\`–`SAVE4\` are the
  persistent slots and each has a `desc` file. `SAVE0\lev.ark` is the working
  level archive, while `bglobals.dat`/`babglobs.dat` are background globals
  used by save/restore. `SAVE_REG` is a separate regular-save path.

## 7. Open questions (resolve via boot / dynamic test)

1. **Tail loading**: ~~confirm the game self-loads file 0x66250..0x89250 at
   0x76250~~ — **RESOLVED 2026-08-20, and not as assumed: there is no self-load.**
   The loader image ends at file 0x66B2F (last block `CODE_830`); file
   0x66B30..0x89250 (141,088 B) is a **Borland `FBOV` overlay pool** of 64
   overlay units, swapped into a buffer above the stack on demand via 602
   `INT 3Fh` thunks. Measured under QEMU — see §13.3, mapped in §13.6. (The "Runtime overlay
   error" string at file 0x15A6C, guessed at here, is indeed the Borland overlay
   manager's.)
2. **Entry semantics**: ~~trace file `0x11E50` forward to find the full CRT
   start / `main` call chain~~ — **RESOLVED 2026-08-25, see §11 and §14.2**.
   The CRT far call at `0x11F58` resolves through FBOV stub row 109 to the
   overlay entry at file `0x77420`.
3. ~~**Reloc table tail**: decode entries 700..3111 (pages > 822) — Borland
   segment/overlay metadata?~~ — **RESOLVED, see §5**: there is no tail. All
   3,176 entries decode cleanly under the `(offset u16, segment u16)` format.
4. **e_cparhdr = 800 paragraphs**: confirm what the loader skips and where the
   first *real* code section starts (candidate: file 0x3100+, after relocs).

## 8. File-offset ↔ Ghidra-address mapping (verified, 2026-08-19)

Authoritative mapping, confirmed from the GhidraDosToolbox `DosLoader.java`
source and re-verified by tiling (831 CODE blocks sum to exactly 0x66B30):

- **Main image**: 831 `CODE_0..CODE_830` blocks tile file `0x3200..0x66B30`
  contiguously, each 16-byte aligned. A block's Ghidra segment counts from the
  **load module**, not from the file: `seg = 0x1000 + ((blockFileStart - 0x3200) >> 4)`;
  the within-block offset = `F - blockFileStart`. Equivalently, and much easier
  to use: **`ghidra_linear = file + 0xCE00`**, i.e. `file = (seg<<4) + off - 0xCE00`.
  - ⚠ The tempting `ghidra_linear = 0x10000 + file` (Ghidra's stated image base)
    is **wrong by exactly 0x3200** — the `e_cparhdr` header is not mapped. It
    produces plausible, well-formed, wrong function names for every address;
    `work/gdbstub_probe.py` shipped this bug once. Check any new mapping against
    the verified examples below before trusting a single name.
- **CODE_TAIL** (file `0x66B30..0x89250`, 141,088 B): Ghidra raw address value ==
  file offset (separate address space).
- Verified examples (file → Ghidra seg:off → contents):
  - `0x5fcdc → 6c8b:022c` = `ff ff ff` then `SAVE0\lev.ark` (string starts at
    file `0x5fcdf`; the distinct `DATA\lev.ark` string is elsewhere, at file
    `0x60578`)
  - `0x60025 → 6c8b:0575` = `DATA\cnv.ark`
  - `0x5fbb8 → 6c8b:0108` = `DATA\strings.pak` (bytes at `0x5fbb8` are `00 00`;
    the string itself starts 2 B later, at file `0x5fbba`)
  - `0x607f6 → 6d5f:0006` = `DATA\player.dat`
  - `0x5f511 → 6be9:0481` = `DATA\uw.cfg`
- This is how to translate any `work/uw_strings.txt` / `work/uw16.txt` file offset
  into a Ghidra address for lookup.

## 9. File I/O layer (INT 21h sites mapped to functions)

Raw-byte scan for `mov ah,NNh; int 21h` (single open site, a few read/seek sites):

**Low-level DOS primitives** (handle table at `[BX*2 + 0x1e80]`):

| AH | file | Ghidra | function |
|----|------|--------|----------|
| 0x3D open   | 0x13ece | 20b9:011a | FUN_20b9_011a (name in DS:DX, access CX→AL, OR 0x8000 = read) |
| 0x3F read   | 0x13fb4 | 20b9:0224 | FUN_20b9_0221 |
| 0x3C fcreate| 0x13d4e | 20a1:013e | FUN_20a1_0138 |
| 0x40 close  | 0x13d6b | 20a1:015b | FUN_20a1_0151 |
| 0x40 close  | 0x1503d | 2174:06fd | FUN_20b9_02fa |
| 0x42 lseek  | 0x13ba7 | 206b:02f7 | FUN_206b_02e9 |

**Archive resource subsystem** @ file `0x3c000..0x3e600` (Ghidra blocks `48a7..4a74`,
46 functions) — the LEV.ARK / CNV.ARK / STRINGS.PAK **record fetcher**:

- setdrive (AH=0x3E) @ 0x3cc54, 0x3cce0, 0x3d9c8, 0x3d9d1
- read (AH=0x3F) @ 0x3ce81, 0x3cffa
- lseek (AH=0x42) @ 0x3da0b
- `dos_close_drive` @ 0x3dd9a (4a74:045a)

Pattern is **setdrive + lseek + read by absolute file offset** → this is where
archive records (levels, conversations, strings) are fetched. The top-level
readers (LoadLevel / LoadConversation / LoadStrings) call into this subsystem but
have **no direct xrefs** to the subsystem functions (16-bit far-call /
function-pointer dispatch; a raw scan of all 1,550 direct `9A` far-calls found
none targeting blocks 0x48a7–0x4a74), so identifying them needs a far-call-graph
pass or a boot trace (see `analysis/ghidra.md` §6).

Note: this 0x3c000..0x3e600 region is **mixed CRT + I/O**, not one clean module.
E.g. `FUN_4a74_017e` (4a74:017e, the largest fn here) is actually the **DOS/INT
2Fh multiplex initializer** (builds the PSP+0x4A vector table, calls
`DosGetVersion`). The setdrive/lseek/read sites above are the archive I/O;
the surrounding large functions do data/string handling.

## 10. String-pool reference mechanism — ✗ **"two pools" withdrawn 2026-08-20**

**There are no string pools. There is one DGROUP**, file `0x5F2F0..0x66B30`
(30,784 B, initialised data + BSS), based at segment `0x5C0F` — the immediate in
the entry instruction that relocation 0 patches (`reassembly.md` §2). The static
file, the relocation table and the QEMU measurement of `DS = 0x61A5` all agree.

✗ What this section used to say, and why each part was wrong:

- *"Pool A ≈ file `0x5F000..0x5FFFF` starts with the `INT 3Fh` overlay thunk
  table"* — the thunks are a separate region **before** DGROUP, occupying
  `0x5D7D0..0x5F2E4` (667 `CD 3F` sites, 552 of them back-to-back), and they
  stop 12 bytes short of DGROUP's start. ✗ The "u16 offset + u8 segment"
  record layout was **not** right — see §13.6 for the byte-verified
  correction (`CD 3F` + one inline u16, no segment byte; segment identity
  comes from which of 115 paragraph-aligned clusters the site sits in).
- *"Pool B ≈ file `0x60000..0x60FFF`: a second, differently arranged copy … →
  two independent string pools (one per data segment in the huge model)"* —
  both ranges are inside the one DGROUP (`0x60000` is `DS:0x0D10`). The
  duplicated literals are ordinary Borland behaviour: string constants are not
  merged across translation units, so a name used in two modules is emitted
  twice. No second segment is involved.
- The pool boundaries were drawn on round 64 KB numbers (`0x5F000`, `0x60000`,
  `0x61000`) because the real base was unknown. Once it is known — `0x5F2F0`,
  not a round number — the "structure" disappears.
- The 270 strings of `work/uw_strings.txt` are all DGROUP literals.

**Reference mechanism (why all static scans came up empty):**

- 0 code immediates, 0 u32 (off,seg) far pointers, 0 Ghidra refs, 0 CALL/JMP
  targets point into the pools. No `mov seg, imm` loads of the pool segments
  either (the only 0x6E00-family immediates are unrelated).
- Instead, the pools are addressed as **DS:u16** with DS loaded to the pool's
  own segment at runtime, and the u16 offsets are stored in **data tables** in
  the globals region (file `0x4E4xx..0x5007A`, block 0x49010 = runtime DS 0x55E1,
  verified at entry: file 0x3200 does `push 0x55E1; pop DS / push 0x55E1; pop ES`;
  PSP is at DS:0 — classic Borland CRT start).
- Confirmed table records (u16 offset, u16 id) whose u16 resolves against a
  **round 0x10000 base** to Pool B strings (the game's structures use 64 KB-
  aligned string bases; the exact runtime base is a boot-test item):
  - `0x4F78A`: `50 00 06 00 60 00 | 58 00 03 00 68 00 | 48 00 06 00 70 00 …`
    → base+0x50 = "charhead", base+0x48, next-pointers 0x60/0x68/0x70/0x80.
  - `0x5DE1A`: `7a 00 06 00` → base+0x7A = "respond".
  - More (off,id) runs at 0x4E440..0x4FCxx (barter/condition/action tables).
  The u16 offsets are unique per string within each pool copy, so decoders can
  resolve id→string via base candidates {0x5F000, 0x60000} (u16 = F − base).
- The id words look like conversation **op/condition codes** (matches the
  named conditions/actions of CNV.ARK, e.g. `respond`, `do_offer`, `x_skills`).
- STRINGS.PAK (data file) is therefore a *separate* game-string table; the
  embedded pools hold the exe's own constants (file paths, error strings,
  condition/action names). Both coexist at runtime.

## 11. Pass 2: entry chain, CRT, core subsystems (2026-08-25)

From the full 17.58 MB `uw_c.c` export (2,041 fns incl. CODE_TAIL) +
GhidraDosToolbox auto-naming (see `functions.txt`):

**Entry / CRT chain:**
- ✗ **Withdrawn.** This subsection read the DOS entry as `1010:0EC5` = file
  `0x32C5`, landing **mid-function** in `crt_psp_init`: *"builds the PSP,
  `call 0x3429`, `retf` @ 0x32EA — the real start resumes at 0x32EB (PSP/PCD
  arg handling, `push 0x55E1; pop DS/ES`)"*. That entry point doesn't exist —
  §2/§3 traced it to a swapped `e_ip`/`e_cs` read — and under the corrected
  mapping the claim doesn't even parse: `crt_psp_init` (1000:0000, size 115)
  covers file `0x3200..0x3273`, and file `0x32C5` falls past the end of it —
  unrelated bytes, not a mid-function landing.
- The real entry is file **`0x11E50`** (§2/§3 above; `analysis/reassembly.md`
  §2): `mov dx,0x5c0f` (DGROUP) `/ mov [cs:0x23c],dx / mov ah,0x30 / int 0x21`
  (DosGetVersion) `/ mov bp,[2]` (PSP top-of-memory) `/ mov bx,[0x2c]` (PSP
  environment segment) `/ mov ds,dx` — standard Borland `C0.ASM` start.
- **The post-CRT program chain is now pinned.** At file `0x11F58`, the real
  entry pushes the startup arguments and far-calls `0x5B3B:0x0043`. That is
  stub row 109 (`stub file 0x5E5B0`), thunk 7; its operand is code offset
  `0x0000` in the unit at file `0x77420` (code `0x7C3`, fixups `0x10A`, 17
  entry points). The unit's first four functions are the program wrapper:

  ```
  main          0x77420  -> main_init 0x77460
                          -> game_loop 0x7760B
                          -> main_shutdown 0x775C6
  ```

  `main` has the UW2 shape: guarded stack prologue, argc/argv pushes, init,
  loop, video/state teardown calls, shutdown, `xor ax,ax`, `retf`. The latest
  save trace executed 1,058 bytes of row 109's 1,987-byte code unit (53%),
  independently confirming that this statically resolved unit is the live
  program wrapper. The smaller Borland CRT functions listed above remain CRT
  support routines; they are not the game `main`.

**Named subsystems (auto-names, trustworthy as hints):** — ✗ **addresses/names
below are stale, corrected 2026-08-21; see `analysis/functions.md` "Applied
renames" for the current, byte-verified table.** 13 of the seg:off values in
this table were wrong (a stale-header-constant reverse-mapping bug), so
`input_vbi_poll`/`input_mouse21h`/`input_mouse33` were withdrawn or renamed
(`input_vbi_poll` turned out to be two VGA palette get/set functions, not
VBI-wait; `input_mouse21h` turned out to be a BIOS-RTC→DOS-clock sync
routine, not mouse; `input_mouse33` had no INT 33h evidence), and
`dos_close`/`dos_findfirst` were reassigned to correct addresses and renamed
`dos_write`/`dos_getcwd` respectively (AH=0x40 is Write not Close; AH=0x47 is
Get Current Directory not FindFirst). Left as-is below for the historical
record; do not use these addresses.

| function | where | role |
|---|---|---|
| `input_vbi_poll` | 3142:00f3 | VBI-synchronized input latch |
| `input_kb_direct` | 3142:02ef | direct keyboard read |
| `input_mouse21h` | 3142:02bb | mouse via INT 21h |
| `input_mouse33` / `input_mouse33b` | 317d:000a / 31a7:01fe | INT 33h mouse |
| `msg_displaystring` | 2f1f:0ab5 | message display (59 inrefs — core) |
| `rt_errhub_1/2/3` | 2d74:04d7 / 20b9:0444 / 2101:010a | Borland runtime error hubs (errhub_1 has 45-way out-degree — the abort path) |
| `file_create_read` | 1fbe:022d | create+read file |
| `dos_findfirst` / `dos_filecontrol` / `dos_lseek` / `dos_open` / `dos_close` | 2174:01af/03d9/043e/0772, 22a0:060d | DOS file layer |
| `dos_close_drive` | 4a74:045a | archive-subsystem (0x3C000–0x3E600) close |

- `FUN_2397_00d0` is the single most-called function (199 callers) — core
  utility (allocator/string class method).

**Game-state machinery:** `FUN_3fc1_11b4` (file 0x33FC4; block 3FC1 =
`CODE_597`, file 0x32E10..0x34460, 6,960 B) is a VBI keyboard
latch (calls both `input_vbi_poll` and `input_kb_direct`; flags at
`DAT_1325_007e/00c4`, latch `cRam0001064d`, bit 0x40 of `uRam0001052f`).
`FUN_3fc1_1556` (258 KB decompiled — decompiler over-merged; starts with
"bad instruction data" warning) is a **state machine over
`DAT_1325_00c6`/`DAT_1325_0080` states 3–6** (clamped to 3..6) — the mode
handler (combat/exploration/menu transitions). Block 0x3FC1 (file
0x32E10..0x34460, 6,960 B — one of the largest single code blocks) is a strong
candidate home for the main game loop; confirm by tracing the transition calls,
not the decompiler text.

**CODE_TAIL hubs** (the 141 KB region, 559 fns): 0x06AE24 (27 inrefs,
32 B — stub/trampoline), 0x06893C (11), 0x068B00 (12), 0x0692EE (11),
0x06CEC8 (10), 0x0792EE (11) — the dispatch spine. Note these are *overlay*
segments (§13.3), so their runtime addresses vary per load; a high in-ref count
here is a static fact about the pool, not a hot spot.

**Runtime string-pool base (2025-06)** — ✗ **withdrawn 2026-08-20, see §13.2.**
The claim was that file `0x21B6D` = `cmp ES:[0x019A:0x0BBF],AL` put pool A at
runtime segment 0x19A0. The bytes actually disassemble as
`cmp al,[ss:bx+di]` + `call word 0x2142:word 0xbbf` — a far-call target, not a
pool reference — and the measured DGROUP is **0x61A5 = file 0x5F2F0**. The
remaining, still-valid part of this note: the pool offsets are not immediates
in the main code region; they are reached via the (u16, id) tables of §10.

**Still open:** the frame/state handlers below the resolved event pump; the
program entry and wrapper are resolved in §11/§14.2, and the event chain is
resolved in §14.3. The static save chain is resolved in §14.1; the overlay map
is resolved in §13.6.

## 12. Artifacts

- `work/gdbstub_probe.py` — the runtime probe (§13); `work/probe7.log` is the
  run the §13 numbers come from, `work/qemu_out/probe_*.png` its screenshots.
- `work/uw16.txt` — function sweep (2,685 entries).
- `work/uw_strings.txt` — string pool (270–300 entries).
- `work/ghidra_export/{uw_c.c, functions.txt, disasm.txt, memory_layout.txt}` —
  full 17.58 MB C export incl. CODE_TAIL (2,041 fns).
- Rizin 16-bit disassembly available on demand:
  `rizin -q -c "e asm.bits=16" -c "pd 100 @ 0xEC50" work/expanded/UW.EXE`
  (rizin auto-parses the MZ header and addresses by its own vaddr,
  `0xEC50 = e_cs:e_ip`, not the file offset — this is the same real entry as
  file `0x11E50` elsewhere in this doc (`0x11E50 = e_cparhdr*16 + 0xEC50`),
  just rizin's addressing convention rather than this doc's. Live-tested:
  `@ 0x11E50` does *not* land on the entry in rizin. The previous example used
  `0x10FC5`, which is confirmed **data** — a byte ramp, `ec ed ee ef f0 f1 …`
  — not code, so it was disassembling the wrong location.)
  Rizin gotchas: it loads the MZ at 0x10000 and **prints addresses in its own
  segment mapping** (e.g. file 0x21B30 shows as `3000:1B30`); linear address
  = 0x10000 + file offset. Ghidra's `disasm.txt` block headers use the same
  segment notation (`CODE_x : 31a7:0000..`), where the range covers the whole
  block's span, not just that segment.

## 13. Runtime facts, measured under QEMU (2026-08-20)

Read off the **running** game with `work/gdbstub_probe.py` (QMP
`human-monitor-command`: `info registers`, `xp`, `screendump`, `sendkey`),
log `work/probe7.log`. Nothing here is inferred from the static image; the
static claims it overturns are marked ✗.

### 13.1 Where the program lives

An 8-candidate signature search (`work/probe11.log`, upgraded
`gdbstub_probe.py`) located 16-byte windows taken from `UW.EXE` in guest RAM:
**6 of 8** located signatures agree on the same delta, which calibrates
everything else:

| Quantity | Measured |
|---|---|
| `runtime linear` | `file + 0x2760` (for the DOS-loaded image only — see 13.3) |
| load module base | `0x05960` — i.e. file `0x3200` (`e_cparhdr`) lands there |
| load segment / PSP | **`0x0596`** / **`0x0586`** |
| `DS` (DGROUP) | **`0x61A5`** = file `0x5F2F0` |
| Ghidra segment | `runtime segment + 0xA6A` (offsets unchanged) |

Consistent with `MEM /C`'s 618 KB largest executable block (free memory starts
at `0x5800`, env + PSP, then the image at `0x5960`).

**Relocation cross-check.** File `0x23F26` holds `BA 8E 57` = `mov dx,0x578E`;
at runtime that same instruction runs with `DS=ES=SS=0x5D24`, and
`0x578E + 0x0596 = 0x5D24`. The image is relocated by the load segment exactly
as expected, and the residency check below sees the same thing at the entry
point: file `0x3200` has `68 e1 55` (`push 0x55E1`), RAM has `68 77 5b`
(`push 0x5B77` = `0x55E1 + 0x596`).

### 13.2 DGROUP is at file 0x5F2F0 — ✗ the "pool A @ seg 0x19A0" guess is withdrawn

`DS = 0x61A5` in every sample taken while the main module runs → DGROUP base =
file `0x5F2F0`, and the bytes there are the canonical Borland prologue:

```
5F2F0: 00 00 00 00 'Turbo C++ - Copyright 1990 Borland Intl.' 00 'Null pointer assign…'
```

so `DS:0x0004` is the CRT banner (which §1 already located at file `0x5F2F4`).
`SS = DS` while the main module runs (`SP ≈ 0x911A..0x92BA`), the classic
Borland SS==DS model.

✗ **§11's "pool A is mapped at runtime segment 0x19A0" is withdrawn.** It rested
on reading file `0x21B6D` as `cmp ES:[019A:0BBF],AL`. The actual instructions
(`ndisasm -b 16`, no `-u` — see AGENTS.md) are:

```
00021B69  363A01            cmp al,[ss:bx+di]
00021B6C  9ABF0B4221        call word 0x2142:word 0xbbf
```

The `0x0BBF` is the **offset half of a far call target**, not a pool offset;
the `36` is an `SS:` prefix, not `ES:`. Independently: relative to the real
DGROUP, `DATA\strings.pak` (file `0x5FBBA`) sits at `DS:0x08CA`, not `0x0BBF`.

### 13.3 ✗ CODE_TAIL is not a self-loaded contiguous block — it is a Borland overlay pool

The tail's first 16 bytes were found at `0x69290` = `file + 0x2760`, which looks
like "the tail is loaded contiguously after the image". Checking the *whole*
region instead of 16 bytes kills that reading (16 B sampled every 4 KB):

| Region | Windows matching RAM |
|---|---|
| image, file `0x3200..0x66B30` | **73 / 100** (the rest are applied relocations / mutated data) |
| tail, file `0x66B30..0x89250` | **1 / 35** — everything past the first chunk is **zeros** |

And the tail's first 16 bytes say what it really is:

```
66B30: 46 42 4f 56 | 10 27 02 00 | 60 d8 05 00 | 9f 00 00 00
       "FBOV"        ovrsize       exeinfo       segnum
       sig           0x22710       0x5D860       159
```

- **`FBOV`** = Borland's overlay-pool magic.
- `ovrsize = 0x22710` = the pool payload `len(file) − 0x66B40`, **exactly**.
- `segnum = 159` — ✗ **not** 159 overlay segments: it is the row count of the
  segment table at `exeinfo`, covering every linker segment of the program.
  **64 of them are overlaid**; see §13.6, resolved 2026-08-23.
- **667 `CD 3F` byte sites**, all inside the DOS-loaded image and none in the
  tail = 64 stub signatures + **602 real thunks** + 1 the installer reads the
  vector number from (§13.6).
- `Runtime overlay error` at file `0x15A6C` is that manager's error string.

Proof that overlays are swapped rather than mapped: sampling caught code running
at two addresses in the overlay buffer whose bytes were then located in the file —
at **different** deltas, so no single mapping exists.

| Runtime `CS:IP` | linear | bytes found in `UW.EXE` at | implied delta |
|---|---|---|---|
| `6C65:03D3` | `0x6CA23` | file `0x786C4` | `-0xBCA1` |
| `6AE3:0030` | `0x6AE60` | file `0x73DB0` | `-0x8F50` |

The overlay buffer sits just above the stack (`SS:SP ≈ 0x6AB6A`), around
`0x69290..0x6D000`.

**Consequence for symbolication:** a runtime address in the overlay buffer must
**not** be translated with the `+0x2760` image delta. It will still "resolve" to
a `FUN_CODE_TAIL__*` name, because the 559 tail functions tile the region densely
and *any* address there lands inside one — that is not evidence. Identify
overlay code by matching its bytes back into the file, as above.

**Consequence for reassembly:** the build must reproduce the FBOV pool, its 64
overlay units and the 602 `INT 3Fh` thunk sites — this is now a first-class
item, not a "tail" appendix. (`work/reasm/uwreasm.py` already rebuilds the pool
byte-for-byte; §13.6 says what those bytes *are*.)

### 13.4 The EIP histogram is dominated by a timer ISR Ghidra never saw

File `0x24A2A..0x24AE4` (runtime `26D8:040A`) is an interrupt handler with **no
Ghidra function** — it is only reachable through a vector installed at runtime,
so the static analysis never disassembled it. It is the single hottest address
in every sampled game state, which means an EIP histogram of this program says
more about the ISR than about the game:

```
24A2A  cmp word [cs:0x2],0      ; reentrancy guard
24A3C  cld / push ax..ds        ; save all
24A46  mov [cs:0x3b4],ss        ; save caller stack,
24A50  mov ss,cs / mov sp,0x3b4 ;   switch to a private stack in the code segment
24A5E  mov si,[cs:0x11c]        ; slot loop, 16 slots
24A65  cmp word [cs:si+0x6a],2  ;   slot active?
24A6D  mov ds,[cs:si+0x48]      ;   per-slot data segment
24A74  ..[cs:si+0x8c/0x8e]      ;   32-bit accumulator vs period [cs:si+0xd0/0xd2]
24AB8  call word far [cs:si+4]  ;   per-slot far callback on wrap
24ABD  inc word [cs:0x11c] / cmp ..,0x10 / jna
24ACA  restore ss:sp, pop all
```

A 16-slot, period-accumulating callback dispatcher on a private stack — a
sound/timing driver's IRQ handler. `SS == CS == 0x26D8` with `SP ≈ 0x3B4` in a
sample is the tell that the ISR is what got caught.

### 13.5 What the game does in each state

Driven with QMP `sendkey`; screenshots in `work/qemu_out/probe_*.png`.

| State | Reached by | Hottest code (excluding the ISR) |
|---|---|---|
| Title card | ~55 s after boot | file `0x1ED82` = `FUN_2b06_0ace+0x54`: **`int 67h` with `AX=5000h`** — EMS *map multiple pages*. The title/cutscene path is EMS-paging-bound. |
| Intro cutscene | 1–2× `ret`/`esc` | same EMS wrapper + overlay-buffer code |
| Main menu (Introduction / Create Character / Acknowledgements) | 3× `esc` | file `0x23F11` = `FUN_30a9_0281`, a far thunk that switches `DS=ES=SS` to the relocated segment `0x5D24` and `SP=0x448`, then calls file `0x23A48` = `FUN_3074_0108` |
| Live dungeon / game panel | Create Character accepted; `F1` | `F1` opens the command panel; its first item is **Save Game**. `ret` executes it and writes the `UW\\SAVE0` save targets. |

The EMS wrapper builds a page-map array at `DS:0x22EA` from its arguments,
loads the handle from `DS:0x22E8`, `CX` = count, `AX = 0x5000`, `int 67h`, and
returns 1/0 on `AH`.

A 4th `esc` at the main menu **quits to DOS**; `AUTOEXEC.BAT` then runs
`QUIT.COM` and QEMU exits 21. That is a clean, deterministic full-game
round trip — boot → title → menu → exit — in ~80 s.

### 13.6 Overlay map — **RESOLVED** (2026-08-23)

Tool: **`work/overlay_map.py`** (prints the table below and cross-checks it
against a run's telemetry). Everything here is read out of the binary or
measured in RAM; the checks that make each claim falsifiable are quoted.

For far calls emitted by pool code, **`work/ovl_resolve.py`** applies the
same exeinfo rule transferred from UW2: the `V` operand in `lcall V:off` is a
byte offset into the table at `0x5D860`, not a segment. It resolves
`seg = u16[0x5D860 + V]` and then `file = 0x3200 + (seg << 4) + off`; an
`INT 3Fh` result is followed through its stub descriptor to the pool body.
The audit sees 4,158 pool call patterns, including 602 distinct overlay
function entries reached through the 64 stub segments.

✗ **Corrects "159 overlay segments" (§13.3, `AGENTS.md`)** — 159 is the number
of rows in the `FBOV` header's segment table, i.e. *every* linker segment of
the program. **64 of them are overlaid.**
✗ **Corrects "62/115 thunk clusters matched"** — the cluster-by-gap-size
heuristic was the wrong unit of analysis. There are exactly **64 stub
segments**, they are table rows, and they tile the thunk region with no
remainder.

**The segment table (file `0x5D860` = the `FBOV` header's `exeinfo`).**
Exactly `segnum` = **159 rows** of `{u16 seg, u16 size_bytes, u16 type,
u16 flags}`, ending at `0x5DD58` — where the `uwedit.exe` string starts.
`seg` is file-relative (`file = 0x3200 + seg*16`); the DOS loader relocates
every one of them, which the RAM dump confirms: **all 159 rows read back
`seg + 0x596`** (the measured load segment, §13.1) and nothing else changed.
Types: `1` × 49, `3` × 64, `0` × 35, `4` × 11. Consecutive rows chain by
`seg + size_bytes/16`.

**`type == 3` = overlaid.** The 64 type-3 rows tile file `0x5DD90..0x5F2E4`
— exactly the region holding the `INT 3Fh` thunks. Each is a *stub segment*:

| offset | field | on disk | at runtime |
|---|---|---|---|
| `+0x00` | `CD 3F 00 00` — the stub's own entry | same | same |
| `+0x04` | u32 pool offset, relative to pool code start `0x66B40` | e.g. `0x0000` | manager adds the base → `0x00066B40` |
| `+0x08` | u16 code size | | |
| `+0x0A` | u16 fixup-table size (u16 offsets, descending, `0000`-terminated) | | |
| `+0x0C` | u16 entry-point count | | |
| `+0x0E`, `+0x12`, `+0x1C` | manager list links — each holds **another stub's segment** when set (`+0x12` in 63 of 64 stubs, `+0x0E` in 28, `+0x1C` in 26; the rest zero) | `0000` | e.g. `0x6052` |
| `+0x10` | **resident segment, `0` = not loaded** (60 of 64 zero at dump time) | `0000` | e.g. `0x6CD8` |
| `+0x18` | near callback offset — **two values only**, `0x04B6` (35 stubs) and `0x0A3B` (29); the resolver special-cases `0x4B6` (`cmp word [es:0x18],0x4B6`) | `0000` | |
| `+0x1a`/`+0x1b` | flag byte / lock-refcount byte (written by the resolver) | `0000` | |
| `+0x20` | `nent` × 5-byte thunks | | patched, see below |

`0x20 + 5*nent == size_bytes` **for all 64 rows**, so the stub is exactly its
header plus its thunks.

**The thunk record is proven, not inferred.** All **602** thunks are
`CD 3F` + u16 + a `00` pad byte, and every operand is **< its own unit's code
size** — i.e. it is an entry offset into the overlay unit. That accounts for
every `CD 3F` byte pair in the load module:

    667 sites = 64 stub signatures (+0x00) + 602 thunks + 1 at file 0x5D7D0
                                              (the byte the installer reads
                                               the vector number from, 0x5D7D1)

**The pool.** The 64 units tile `0x66B40..0x8923E` in table order, paragraph
aligned, 0–160 B of padding between them, 18 B left at the end;
132,461 B of code + 7,578 B of fixups. `ovrsize` (`0x22710`) is exactly the
pool payload `len(file) - 0x66B40` — a cleaner statement than "tail size − 16".

**Dispatch: the manager patches the thunk in place.** ✗ *Corrects the
expectation that the handler's `call far dword ptr ds:[0x26]` jumps into the
overlay.* That slot is **not runtime-patched** — in RAM it holds the plain
relocated disk value `0EC5:3C50`, which points at the last byte of segment
`0x0EC5`, and that byte is `CB` = `retf`: a do-nothing hook. The real
mechanism is visible in the RAM dump: **70 of the 602 thunks read back as
`EA <off> <seg>`** — a far `jmp` straight into the resident unit, each target
landing on a `55 8B EC` (`push bp; mov bp,sp`) prologue. That is why the
record is 5 bytes and why the handler does `sub word [bp+2],2`: backing the
saved `IP` up by 2 puts it on the (now patched) 5-byte instruction, so the
`IRET` re-executes the thunk as a far jump. First call pays the interrupt;
every later call is a direct far jump.

**The overlay manager is one segment**: row 49, `seg 0x39A0`, file
`0x3CC00..0x3DE47` (4,679 B, type 1). Installer `0x3CD39`; `INT 3Fh` handler
`0x3D0E4` (= `+0x4E4`); the resolver it calls is `+0x594` (`file 0x3D194`) —
it reads `[es:0x10]` to test residency and writes `[es:0x1a]/[es:0x1b]`; the
DOS read that pulls a unit off disk is `+0x3FC` (`file 0x3CFFC`); and **14 of
the load module's 28 `INT 67h` (EMS) sites sit in this segment**
(`0x3D5E7..0x3DAAE`) — the manager's EMS cache.

**Measured against a live run** (§14). Of 26 reads issued by the manager's
read site, **25 load exactly one unit** — `seek == 0x66B40 + pool offset` and
`len == code + fixups`, matching the table with no slack. The 26th is the
startup block read (`seek 0x66B40, len 0x1DC0`) that pulls rows 89–92 in one
go. Three further units (rows 94, 104, 110) *executed* without any DOS read
in the log, which points at the manager's EMS cache (the `INT 67h` sites
above) rather than a second disk path — plausible and unproven; an `INT 67h`
log would settle it.

At dump time four units were resident, and their bytes in the buffer are
**90–94 % identical to the file** (the rest are applied fixups, the same
signature the load module shows in §13.1):

| row | unit @ file | code | resident seg | linear |
|---|---|---|---|---|
| 113 | `0x783E0` | `0x5FF` | `0x6CD8` | `0x6CD80` |
| 114 | `0x78A80` | `0xB61` | `0x6B60` | `0x6B600` |
| 136 | `0x829F0` | `0xA90` | `0x6D39` | `0x6D390` |
| 152 | `0x88A00` | `0x7CC` | `0x6AE3` | `0x6AE30` |

**Consequence for Ghidra**: the pool is no longer an undifferentiated
`CODE_TAIL`. Each unit has a file range, a load segment (its stub's `+0x10`
when resident) and its own fixup table, so units can be imported one at a
time — the "decompile per unit, not per file" rule in
`analysis/cross-project.md`.

## 14. Execution telemetry (2026-08-23)

First run of the family's QEMU TCG plugin (`../F030Method/dos/trace/`, see
`analysis/qemu-boot.md` §*Execution telemetry*) on UW1 — until now it had only
been exercised on POR, and the Borland `FBOV` case was untested. Command
lines and outputs: `work/trace_run1.log`, `work/trace/`.

```
python ../F030Method/dos/trace/run_trace.py --hdd img/uw.hdd --seconds 130 \
    --lo 0 --hi 0xA0000 --out work/trace/uw.trace \
    --memdump work/trace/uw.ram --memdump-at 115 \
    --key 70:esc --key 90:esc --shot 60 --shot 100 \
    --int21log work/trace/uw.int21 \
    --ovl work/trace/uw.ovl --ovl-lo 0x69290 --ovl-hi 0x6E000
python ../F030Method/dos/trace/trace_coverage.py --exe work/expanded/UW.EXE \
    --trace work/trace/uw.trace --ram work/trace/uw.ram --data-from 0x5C0F0
python ../F030Method/dos/trace/trace_overlay.py --ovr work/expanded/UW.EXE \
    --flush work/trace/uw.ovl --ram work/trace/uw.ram \
    --out work/trace/uw_pool.coverage
python work/overlay_map.py --int21 work/trace/uw.int21 \
    --coverage work/trace/uw_pool.coverage
```

- **Calibration reproduced independently**: 49 of 87 windows vote load base
  `0x5960` (segment `0x0596`) — the same value §13.1 measured by a different
  method (signature hunt via QMP).
- **Load module**: 42,867 of 407,856 B executed = 10.5 %.
- **Known-data guard is exact**: **0** of the 30,784 B from the measured
  DGROUP (`file 0x5F2F0` = image `0x5C0F0`) to the end of the load module
  executed. Code region: 42,867 / 377,072 = **11.4 %**.
- **Overlay pool**: 418 flush records, 15 of them with executed bytes, **100 %
  of those identified by content** — 16,349 of 141,072 pool bytes = 11.6 %
  executed, attributed to units (`work/trace/uw_pool.coverage` is keyed by
  *file offset*, so it can be handed to a disassembler directly).
- **32 of 64 units were touched** by the title → intro → main-menu path: 25
  loaded by single-unit reads, 4 more (rows 89–92) by the startup block read,
  3 (rows 94, 104, 110) that executed with no DOS read at all. **17 units
  actually executed**; the hottest are row 93 (70 % of its code), row 109
  (53 %), row 110 (53 %), row 133 (46 %).

Caveats that matter when reading these numbers:

- **Create Character is now keyboard-drivable.** From the main menu, nine
  `ret` presses accept the default sex, handedness, class, attack/defense
  choice, weapon, skill, portrait, and difficulty screens; the probe's
  `--text NAME` fills the name field and Enter accepts it. A final `ret`
  reaches the live 3D dungeon. The matching telemetry run is
  `work/trace/uw_char.trace`: it executed 71,807/377,072 bytes of the code
  region (19.0%), plus 19 identified overlay units. This is coverage of the
  driven run, not a binary-wide coverage claim.
- The plugin clears a region's flags when it flushes it, so overlay-buffer
  coverage lives in `uw.ovl`/`uw_pool.coverage`, never in `uw.trace`.
  `uw.trace` covers the load module (which ends at linear `0x69290`, just
  below the overlay window used here).
- The guest is ~2–3× slower with the plugin attached: the front end that
  needs ~30 s bare reaches the intro cutscene at ~60 s.

### 14.1 Static save chain — RESOLVED (2026-08-25)

UW2's resolved save model transfers to UW1 at the level of both directory
layout and call order. `SAVE0\` is a scratch working directory, not a
persistent slot; `SAVE1\`–`SAVE4\` are the four persistent slots, and the
description scanner supplies `"<not used yet>"` when a slot has no `desc`.

The static chain is:

```
savegame_menu_action  0x083920(mode, slot)
    mode == 0  -> savegame_save     0x083A97
    mode != 0  -> savegame_restore  0x0839CE (only if the slot is populated)

savegame_save(slot)              0x083A97
    build SAVE<slot>\\; read/write <slot>\\desc
    level_save()                  0x08369E  -> SAVE0\\lev.ark
    dir_copy_all_files(SAVE0\\, SAVE<slot>\\)  0x083D49

savegame_restore(slot)           0x0839CE
    dir_copy_all_files(SAVE<slot>\\, SAVE0\\)  0x083D49
    level_load()                  0x0835FC  <- SAVE0\\lev.ark
    apply post-restore state      0x083E9B

file_copy                       0x083C72
slot-content check               0x083BE6
scan SAVE1..4\\desc              0x0837A4
```

The `08369E`/`0835FC` roles are established by their path reference to
`SAVE0\\lev.ark`, their use from save versus restore, and the adjacent level
transition routine (`083E19` does save-then-load). The `083C72` body opens a
source and destination, copies in `0xF000`-byte chunks, verifies/writes, and
closes; `083D49` enumerates `*.*` and calls it for every file. This is the same
directory-copy architecture UW2 documents in its save module, not a bespoke
save-file format.

The runtime F1 probe independently produced `UW\\SAVE0\\LEV.ARK` (290,864 B)
and `UW\\SAVE0\\BGLOBALS.DAT` (7,998 B). A complete temporary-image slot-I
probe (`F1` → `ret` → `ret` → description `codex` → `ret`) then produced
`SAVE1\\` with `LEV.ARK` (294,960 B), `BGLOBALS.DAT` (7,998 B), `PLAYER.DAT`
(312 B), and `DESC` (5 B, exactly `codex`); `SAVE0\\` held the same four
files. The latest caller-sidecar run is `work/trace/uw_save_callers_cs.*`;
the older compact trace remains `work/trace/uw_save.*`.

### 14.2 Main and game loop — RESOLVED (2026-08-25)

The UW2 main-resolution method transfers directly. The call at resident file
`0x11F58` is not a direct call into the overlay pool: it targets the relocated
stub `0x5B3B:0x0043`. In the on-disk stub, that address is the eighth 5-byte
`INT 3Fh` thunk; the thunk operand is `0`, so the overlay map resolves it to
row 109, unit file `0x77420`, entry offset `0`.

```text
main          0x77420
    main_init  0x77460       ; pushes [bp+8], [bp+6], calls init
    game_loop  0x7760B       ; event pump until result <= 3, then frame work
    shutdown   0x775C6
```

The wrapper is structurally the same as UW2's resolved `main`: it performs the
stack guard, calls init and the event loop, runs the final state/video hooks,
calls shutdown with argument `1`, returns zero with `retf`. Telemetry from
`work/trace/uw_save_callers_cs.*` attributes 1,058 executed code bytes to row
109, or 53% of its 1,987-byte code area.

### 14.3 Event pump — **RESOLVED** (2026-08-25)

The `game_loop` call at file `0x7761B` is `lcall 0x0070:0x066A`. Applying
the UW2-derived exeinfo rule gives `exeinfo[0x70]` (row 14) = segment
`0x1BC4`, hence resident file `0x1F4AA`. The bytes there are a `push bp /
mov bp,sp` wrapper that pushes mode `0` and calls the alternating pump at
`0x1F455`.

The complete resident chain is:

```text
event_source_queued       0x1F2EA  (2be8:026a)
    -> low-level fetch     0x1BC4:0x0FA9
event_poll_mods            0x1F3B8  (2be8:0338)
    -> mode!=0 helper      0x1F338  (2be8:02b8; left auto-named)
event_pump_alternating     0x1F455  (2be8:03d5)
    -> queued/poll fallback through [0x12E]
event_pump                 0x1F4AA  (2be8:042a)
    -> called by game_loop
cutscene_play              0x75339  (row-105 pool body; argument 9)
    -> cutscene_run         0x7479B
```

This is a control-flow match to UW2's resolved chain, not an address guess:
the queued function has the one-slot `0xFFFF` pushback and record flag, the
poll function returns `0xFFFF` for an empty low byte and attaches timer and
modifier bits, and the alternating function flips its toggle before falling
back to the other source on a negative result. The top-level return test is
therefore confirmed as `event_pump(0) > 3`.

The loop's exit call, `lcall 0x0348:0x0084` after pushing `9`, resolves to
stub row 105 and then to pool body file `0x75339`, now named `cutscene_play`.
Its relative call at `0x753C4` lands at `0x7479B`, the corresponding
`cutscene_run` body. This closes the cutscene side of the exit path; the next
dynamic target is the state transition after that player returns.

### 14.4 Still open

- **The frame/state path below the event pump**: Create Character is now
  driven reproducibly and the live dungeon frame is captured. The trace
  artifacts are `work/trace/uw_char.*`; they raise executed code-region
  coverage to 19.0%, but do not identify every state handler.
- **EMS-cached overlay loads** are inferred, not logged (see §13.6). Adding an
  `INT 67h` log to the plugin would close it.
- **`.GR` `type=8`** was blocked on "which overlay unit is this, and where
  does it live at runtime?" — that blocker is gone. Both the container parser
  (`0x78B17`) and the `type=8` `process` callback (`0x7905C`) are in **row
  114's unit**: file `0x78A80`, code `0xB61`, stub `0x5E750` (seg `0x5B55`,
  24 entry points) — i.e. unit offsets `+0x97` and `+0x5DC`. That unit was
  loaded during the traced run and was **resident at dump time at segment
  `0x6B60`**, so its relocated code can be read straight out of
  `work/trace/uw.ram`. See `analysis/data-formats.md` §`.GR`.
- **Data formats otherwise unaffected** by this work: `CNV.ARK`, `.TR`,
  `.SYS` glyphs, `.XMI`.
