# Reassembly — UW.EXE rebuilt byte-for-byte from generated source

**Status: RESOLVED (2026-08-20).** `work/expanded/UW.EXE` (561,744 B) is
reproduced **byte-for-byte** by assembling generated NASM source. Same
SHA-256, whole file, including the MZ header, the relocation table, the
DOS-loaded module and the Borland `FBOV` overlay pool.

```
original  sha256 b05b8d8cae54144c386070d56dfdd8dacad38869f2920a6c35813a1d75c80a7b
rebuilt   sha256 b05b8d8cae54144c386070d56dfdd8dacad38869f2920a6c35813a1d75c80a7b
```

Regenerate and verify (≈25 s, converges in 4 passes):

```bash
python work/reasm/uwreasm.py
```

Artifacts in `work/reasm/out/`: `uw.asm` (10.7 MB, 173,761 lines), `uw.bin`
(the rebuild), `uw.lst` (nasm listing), `fallbacks.txt`, `report.json`.

## 1. What "recreated" means here

The source is a *source*, not a byte dump wearing a costume:

- The MZ header fields `e_cblp`, `e_cp`, `e_crlc`, `e_cparhdr` and `e_lfarlc`
  are **computed** from the layout (`IMAGE_END % 512`, `NRELOC`, …), not copied.
- The relocation table is **regenerated** from the fixup list; `e_crlc` is
  `($ - reloc_table) / 4`.
- The header slack is `times HDR_SIZE - ($ - $$) db 0`, not 34 literal zeros.
- 163,004 of 163,030 instructions (**99.98 %**) are real mnemonics. Only 26 are
  pinned with `db` (§5).
- No `incbin`. Nothing is read from the original at assembly time.

**Edit-propagation check.** Replacing the CRT banner string
`Turbo C++ - Copyright 1990 Borland Intl.` with an equal-length marker on one
source line and rebuilding changed **exactly the 38 byte positions where the
two strings differ, and nothing else** — not the header, not the relocation
table, not a single downstream instruction. Command in `work/reasm/out/`;
patched variant kept as `uw_patched.asm` / `uw_patched.bin`.

## 2. Container model (all fields verified against the bytes)

Raw header, file `0x00..0x1F`:

```
4d 5a 30 01 36 03 68 0c  20 03 00 00 ff ff 8b 63
80 00 00 00 00 00 c5 0e  3e 00 00 00 01 00 fb 30
```

| off | field | value | note |
|---|---|---|---|
| 0x02 | e_cblp | 0x0130 | bytes in last page |
| 0x04 | e_cp | 0x0336 (822) | pages |
| 0x06 | e_crlc | 0x0C68 (3,176) | relocation entries |
| 0x08 | e_cparhdr | 0x0320 (800) | header = **0x3200** |
| 0x0A/0x0C | e_minalloc / e_maxalloc | 0 / 0xFFFF | |
| 0x0E/0x10 | e_ss / e_sp | 0x638B / 0x0080 | stack, load-relative |
| 0x12 | e_csum | 0 | |
| **0x14** | **e_ip** | **0x0000** | ← see correction below |
| **0x16** | **e_cs** | **0x0EC5** | ← see correction below |
| 0x18 | e_lfarlc | 0x003E | relocation table |
| 0x1A | e_ovno | 0 | no DOS overlays (Borland does its own) |

Region map:

| file range | size | content |
|---|---|---|
| `0x00000..0x0003E` | 62 | MZ header |
| `0x0003E..0x031DE` | 12,704 | relocation table, 3,176 × 4 B |
| `0x031DE..0x03200` | 34 | header slack, all zero |
| `0x03200..0x66B30` | 407,856 | **load module** (what DOS loads) |
| `0x66B30..0x89250` | 141,088 | **`FBOV` overlay pool**, 159 segments |

`image size = (e_cp − 1) × 512 + e_cblp = 821 × 512 + 304 = 420,656 = 0x66B30`,
which lands *exactly* on the `FBOV` signature — the two facts confirm each other.

### ✗ Four corrections to §2/§3/§5 of `uwexe.md`

1. **`e_ip` and `e_cs` were swapped.** The doc read `e_ip = 0x0EC5, e_cs = 0`.
   The file has `e_ip = 0x0000, e_cs = 0x0EC5`, so the entry is
   `header + (e_cs << 4) + e_ip = 0x3200 + 0xEC50 =` **file `0x11E50`**, not
   `0x32C5` or `0x10FC5`. Both previously claimed entry points are *data*:
   `0x10FC5` holds `ec ed ee ef f0 …`, a byte ramp. What made the wrong reading
   survive is that §3 explained the mismatch away — "the linker entry sits
   inside a larger code block … normal for Borland linkers". The real entry is
   textbook Borland `C0.ASM` and needs no excuse:

   ```
   11e50  mov dx, 0x5c0f          ; DGROUP
   11e53  mov [cs:0x23c], dx
   11e58  mov ah, 0x30
   11e5a  int 0x21                ; DosGetVersion
   11e5c  mov bp, [0x0002]        ; PSP: top of memory
   11e60  mov bx, [0x002c]        ; PSP: environment segment
   11e64  mov ds, dx
   ```

2. **The image-size arithmetic was wrong**: `0x66250` was quoted where
   `(822−1)×512 + 304 = 0x66B30`. The 0x8E0 gap invented a "zero-BSS tail"
   between 0x66250 and the overlay pool that does not exist.

3. **There is no `e_lfanew`.** The doc reported `e_lfanew = 0x10000` at 0x3C and
   called it "Borland junk". `e_lfarlc = 0x3E`, so bytes `0x3E..0x3F` are the
   first relocation entry — the u32 read at 0x3C straddled the header/table
   boundary. This is a plain MZ; there is no extended header and no `NE`/`PE`.

4. **The relocation-table format was wrong**, and this one propagated furthest.
   The doc described `(page u16, offset u8, pad u8 = 0x0E)` and concluded that
   only "the first ~700 entries are valid", the rest holding "out-of-range pages
   (Borland-specific extension or a second table)". DOS relocations are
   `(offset u16, segment u16)`. Decoded correctly:

   | check | result |
   |---|---|
   | entries | 3,176, all decodable |
   | targets inside the image | **3,176 / 3,176** |
   | duplicate targets | **0** |
   | distinct segments | 53 |
   | highest target | file `0x61546` |

   Every entry is valid. `cross-project.md` repeated the derived claim that UW1's
   table "carries junk entries with pages past `e_cp`, which crash a stock
   loader" — that was an artefact of the wrong format, not a property of the file.

   Entry 0 is `(offset 0x0001, segment 0x0EC5)` → file `0x11E51`, the `0x5C0F`
   immediate of `mov dx, 0x5c0f` above: the first fixup patches DGROUP in the
   CRT start, exactly as Borland's `C0.ASM` requires.

### DGROUP, confirmed three independent ways

| derivation | value |
|---|---|
| immediate at the entry point, patched by relocation 0 | segment `0x5C0F` |
| `+` measured load segment `0x0596` (`uwexe.md` §13.1) | `0x61A5` = **measured runtime `DS`** |
| `header + (0x5C0F << 4)` | file **`0x5F2F0`** = **measured DGROUP offset** |

The static file and the QEMU measurement agree without adjustment. DGROUP runs
`0x5F2F0..0x66B30` (30,784 B, initialised data + BSS).

This also retires the "Pool A / Pool B" reading of `uwexe.md` §10: there are not
two string pools. There is one DGROUP, and the "second copy" at `0x60000` is
just the same literals emitted again by a different translation unit — Borland
does not merge string constants across modules. The `INT 3Fh` thunks that §10
placed "at the start of pool A" actually occupy `0x5D7D0..0x5F2E4`, ending
12 bytes before DGROUP begins.

## 3. Method

**Discovery — recursive descent, never a linear sweep** (`cross-project.md` §1).
Seeds: the entry point, plus 2,012 function starts from the Ghidra export
(`file = (seg << 4) + off − 0xCE00`; `CODE_TAIL::` addresses are already file
offsets). Far-call targets are followed only when the segment word is a
*relocation site* — that is what makes `9A`/`EA` operands trustworthy. `INT 3Fh`
is treated as a 5-byte call thunk (`CD 3F`, `dw offset`, `db segment`) and
descent resumes after the record; 474 were walked this way.

Result: 163,030 instructions, 2,243 function entries, 398,047 B.

**Known-data guard.** Descent is forbidden from entering proven-data regions and
the guard is asserted every run (`known_data()` in the script):

| region | why it is data |
|---|---|
| `0x00000..0x03200` | MZ header + relocation table + slack |
| `0x109DE..0x119DE` | palette shading LUT — see §4 |
| `0x5F2F0..0x66B30` | DGROUP |

**Emission.** Branch targets are written `$`-relative (`jmp short $+2+N`,
`jz near $+4+N`, `call $+3+N`). No segment model enters the encoding, so
real-mode 64 KB wraparound cannot corrupt a branch — the reason a flat
`nasm -f bin` rebuild of a segmented program is exact at all. Far transfers keep
their literal `seg:off` (`call 0x5b3b:0x0043`).

**Verification.** Every emitted line carries its intended file offset in a
sidecar map. After each `nasm` run the listing is parsed and each line's emitted
bytes are compared against the original bytes *at its intended offset* — which
makes the check immune to layout shift, so the first wrong instruction is
localised even when everything after it has moved. Lines that disagree walk a
variant ladder and the file is regenerated. The last rung is `db`, which always
matches, so **byte-exactness is guaranteed by construction**; the ladder only
decides how much of the file is real mnemonics.

## 4. New finding: the palette shading LUT at `0x109DE`

The fallback list pointed at it — a cluster of nonsense "SSE instructions"
repeating on a 0x100 stride. It is a **16 × 256 palette attenuation table**,
file `0x109DE..0x119DE`, exactly `0x1000` bytes:

| row | @ | property |
|---|---|---|
| 0 | 0x109DE | **the exact identity map**, `00 01 02 … ff` |
| 1 | 0x10ADE | 242 distinct values |
| … | | 224, 206, 188, 174, 160, 146, 135, 124, 113, 102, 91, 80, 69 |
| 15 | 0x118DE | **all zero** |

`shade[level][colour] → darker colour`. The structure is bounded by code on both
sides (`cc c3` = `int3; ret` immediately before, real code immediately after) and
the round `16 × 256` with identity at one end and zero at the other is the kind
of invariant that has to land (`cross-project.md` §4, level 3). Ghidra had
claimed functions inside it; that is what put it into the descent in the first
place.

## 5. Borland encodings NASM will not produce

Borland's code generator makes choices NASM's encoder does not. These are
*equivalent instructions with different bytes*, so a text round-trip loses them.

**Fixed with generated macros** (defined at the top of `uw.asm`): Borland emits
register-to-register ALU and MOV with the **direction bit set** — `8b ec` for
`mov bp,sp`, `33 c0` for `xor ax,ax` — where NASM always picks the `d=0` form
(`89 e5`, `31 c0`). NASM has no qualifier for this, so `uwreasm.py` generates one
macro per (mnemonic, width) that pins the ModRM byte:

```asm
%macro mov_rr 2
        db 0x8b, 0xc0 | ((rn_ %+ %1) << 3) | (rn_ %+ %2)
%endmacro
...
        mov_rr bp, sp                   ; assembles to 8b ec
```

Covers `add/or/adc/sbb/and/sub/xor/cmp/mov/xchg`, byte and word: 10,760
instructions, 6.6 % of the code. Without it they would all be `db`.

**Fixed by deriving the qualifier from the original encoding.** capstone's
`encoding.disp_size` / `imm_size` / `modrm` say which form was used, so the
qualifier is computed, not guessed:

| original | naive NASM | emitted |
|---|---|---|
| `83 8f 08 00 08` disp16 | `83 4f 08 08` disp8 | `or word [word bx+0x8], byte 0x8` |
| `8b 47 00` disp8 = 0 | `8b 07` no disp | `mov ax, [byte bx]` |
| `83 c6 10` imm8 | `81 c6 10 00` imm16 | `add si, byte 0x10` |

**Irreducible — 26 instructions pinned with `db`** (0.016 %), each keeping its
mnemonic in a comment. Full list in `work/reasm/out/fallbacks.txt`:

- opcode aliases with no NASM syntax: `82` for `80`, `/6` for `/4` on the shift
  group (`c0 75`, `d2 f7`), `f6 /1` for `f6 /0`, `ff /1` (`ff ca` = `dec dx`)
  where NASM emits the short `4a`;
- prefix order (`f3 2e a4`: NASM normalises the segment prefix ahead of `rep`)
  and doubled segment prefixes (`2e 36 …`);
- 6 sites where capstone reads *data* as x87/BND exotica.

## 6. Coverage, net of the data guard

| region | bytes | real instructions |
|---|---|---|
| MZ header + relocation table | 12,800 | 0 % (data) |
| load module, code + tables | 370,128 | 72.4 % |
| overlay stub area (`INT 3Fh`) | 6,944 | 60.4 % |
| DGROUP | 30,784 | 0 % (data) |
| FBOV overlay pool | 141,088 | 79.0 % |
| **whole file** | **561,744** | **70.9 %** |

The per-region percentages above do not currently reconcile arithmetically with
the confirmed total (`code_bytes: 398047` in report.json, ≈14,400 B / 3.6 % short
when the stated percentages are weighted by region size) — the whole-file 70.9 %
figure is independently confirmed correct; the per-row split needs re-deriving
from the actual descent output.

The remaining ~29 % is genuine data: DGROUP, the shading LUT, jump/dispatch
tables between functions, and the string literals. Descent-time anomalies stay
small — 40 undecodable starts, 1 out-of-range branch target, 14 guard hits.

## 7. Tool notes (cost real time — read before touching the harness)

- **nasm listing, macro expansions.** Bytes from a macro are listed against the
  *macro definition's* line number, marked `<1>`. They must be re-attributed to
  the invoking line or every macro-emitted instruction looks like it produced
  nothing. `times` runs print as `00<rep DBh>` — that leading `<` is **not** a
  macro marker, and treating it as one silently glues a `times` run's first byte
  onto the previous line.
- **Never `%include`.** It renumbers the listing and breaks line↔offset mapping.
  The macros are emitted inline for exactly this reason.
- **Emit one source line per generator line.** Pushing a multi-line string as a
  single element desynchronises every line number after it, and the failure
  looks like "NASM rejects 4,000 valid instructions".
- **capstone quirks in `CS_MODE_16`**: `98`/`99` are printed with their 32-bit
  names `cwde`/`cdq` (they are `cbw`/`cwd` without a `0x66` prefix — 1,560 sites
  here); string instructions get explicit operands NASM rejects (`rep movsb byte
  [es:di], byte [si]`); `les`/`lds` print a bare `ptr` (`les di, ptr [bp+6]`) —
  that one alone accounted for 4,139 of the first run's 4,268 fallbacks;
  `lcall`/`ljmp` need translating to `call far`/`jmp far`; `enter`'s nesting
  level is printed signed.
- **`nasm -O0`** so the assembler never re-optimises a size that was chosen
  deliberately, and `-w-label-redef-late` so one genuine error does not bury
  itself under a cascade of "label changed during code generation".
- **Watch for variable shadowing in the emitter.** A loop reusing the names `lo`
  and `hi` inside the region walker truncated the output at 420,768 bytes — the
  per-line verifier reported zero mismatches because every *emitted* line was
  right; only the whole-file compare caught it. Keep both checks.

## 8. What this unlocks

The build order question from `AGENTS.md` §Next steps 4 is answered for the
executable: there is no build order, there is one source file and one `nasm`
invocation. What remains for a full game rebuild is the **data** side — the
formats still open in `data-formats.md` (`CNV.ARK`, `.GR`, `.TR`, `.SYS` glyphs,
`.XMI`) — plus the LZH repacking layer if the distribution disks are to be
reproduced rather than just the installed tree.

For the port itself the useful consequence is different: `uw.asm` is now a
complete, addressable inventory of the program. Every instruction has a file
offset, every function a label, and any region can be replaced with hand-written
code and re-verified against the original in 25 seconds.
