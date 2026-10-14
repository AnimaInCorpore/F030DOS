# `Z_TIE__.EXE` — Ghidra import + semantic function naming (P1.3)

Status: **pipeline built and verified; first naming pass applied (10/10)**.
Companion to `analysis/ztie.md` (container/layout) and `analysis/32bit/functable_v2.txt`
(the capstone sweep this pass seeds from). Mirrors UW1's `analysis/functions.md`
structure and its verified-anchor-only naming discipline.

## 1. Import model — per object, not one blob

The old `AGENTS.md` one-liner ("extract 32-bit image, base 0x3F000, Raw Binary
x86-32") predates the LE re-resolution and is superseded. `Z_TIE__.EXE` is an
MZ stub + standard Watcom LE module with **two objects at two different
bases** (`ztie.md` §2/§4); importing them as one blob at 0x3F000 would put
obj2's data at the wrong linear address entirely. Following the POR
per-unit-import pattern (`cross-project.md` §1 "Turbo Pascal's scheme…" /
`todo.md` P1.3), each object is sliced to its own flat file and imported
separately:

| object | slice | base | file range | script |
|---|---|---|---|---|
| obj1 (code) | `work/ghidra/z_tie_obj1.raw` (0xAB000 B) | linear `0x10000` | file `0x3D800..0xE8800` | `work/slice_objects.py` |
| obj2 (data) | `work/ghidra/z_tie_obj2.raw` (0x46470 B) | linear `0xC0000` | file `0xE8800..EOF` physical (0x13547 B) + zero BSS pad to vsize | `work/slice_objects.py` |

`slice_objects.py` reuses `work/audit_fixups.py`'s already-verified LE parse
(doesn't re-derive the object table), asserts the page map is identity before
treating either object as one contiguous slice (a reordered map would make a
flat slice wrong), and self-checks against a known string
(`"You must run TIE.EXE for the game.\n"` at obj2+0x1A).

**obj2 gets no function-seeding.** It is the data/DGROUP object; of the 4,030
sweep rows only 20 land past file 0xE8800 (vs. 4,010 in obj1) — noise, not
real code (`ztie.md`'s own "16-bit-mode clusters"/data-table caveat on the
sweep). Function-creation heuristics on a data segment manufacture false
positives (cross-project.md §1 "known-data guard"), so obj2 is imported for
default auto-analysis only (mainly ASCII string detection) and stays
available for the P2 data-format work; it carries no functions by design.

## 2. Toolchain note: Jython is not available here

**Re-confirmed on the macOS host 2026-08-22** (Homebrew Ghidra 12.1.3,
`/opt/homebrew/Cellar/ghidra/12.1.3/libexec`, openjdk@21): the same
`Ghidra was not started with PyGhidra. Python is not available` error, so the
Java-postScript rule below is a property of a stock Ghidra install, not of one
machine. The bundled `pyghidra` wheels sit unused in
`libexec/Ghidra/Features/PyGhidra/pypkg/dist/`; `python3 -c "import pyghidra"`
fails — enabling it would mean pip-installing that package and launching via
`pyghidraRun`, which nobody has needed yet.

`analyzeHeadless` on this machine has **no PyGhidra** — `.py` GhidraScripts
fail with `GhidraScriptLoadException: Ghidra was not started with PyGhidra`.
(Comanche's `tools/re/annotations.py` generates a `.py` postScript; that
assumes a different Ghidra install/config than this one.) Confirmed working:
plain **Java** GhidraScripts dropped in `-scriptPath`, auto-compiled by
Ghidra's own script bundle system — no manual `javac`/jar step needed (unlike
the GhidraDosToolbox *extension*, which is a different, heavier mechanism
that doesn't apply to a raw x86-32 import anyway). One gotcha: Ghidra
compiles every `.java` file in the scripts directory as **one bundle** — a
compile error in any script (e.g. `TieExport.java`'s first draft returning
`Reference[]` from `getReferencesTo`, which actually returns a
`ReferenceIterator`) silently blocks every other script in that directory
from loading too ("`skipping TieRename.java`" with no other explanation) —
check the full log for `error:` lines, not just the top-level
`GhidraScriptLoadException`, when a script "not found."

## 3. Address conventions (reminder — full table `ztie.md` §4)

- obj1 linear = `0x10000 + (file − 0x3D800)`, file ∈ [0x3D800, 0xE8800).
- obj2 linear = `0xC0000 + (file − 0xE8800)`, file ∈ [0xE8800, 0xFBD47) physical.
- Every address below was converted file→linear **programmatically** (a
  one-line Python loop), never by hand — see UW1's `functions.md` for what
  hand reverse-computation cost there (13/20 renames on the wrong function
  from a stale header constant). Two independent values cross-check exactly
  against the LE header's own EIP field: `crt_entry` = file 0xB8CE4 → linear
  0x8B4E4, matching `ztie.md` §1's "obj1+0x7B4E4" verbatim.

## 4. Applied renames (obj1, all verified, 18)

Seeded first from `work/gen_ghidra_seeds.py` (4,010 sweep starts + LE fixup
targets landing in obj1 → 5,149 unique seeds; `TieSeedFunctions.java`:
made=2,409, already_covered=2,652 [auto-analysis got there first],
failed=88, total=5,149). Then `TieRename.java` applies the 15-anchor table
below (expected on a clean run: created=3, renamed=12, split=1 —
§Regeneration); the 16th name, `stk_stack_check`, is applied by
`TieFixStackCheck.java` (§5). *(Table completed 2026-08-26 — the five
names added after the first pass had been applied in the scripts but never
recorded here.)*

| name | linear | file | evidence |
|---|---|---|---|
| `game_main` | 0x010010 | 0x3D810 | obj1+0x10, right after the object's own trap bytes. Real prologue confirmed by direct disassembly (§5): `push 0x68 ; call 0xB8AEE` (Watcom stack-check helper) then the standard `push ebx/ecx/esi/edi/ebp ; mov ebp,esp ; sub esp,0x48`. Argv-parsed; calls `check_system_requirements(6,1)`. `ztie.md` §7 item 10. |
| `check_system_requirements` | 0x0672D5 | 0x94AD5 | Call target of `game_main`. Runs system-requirement probes into one status code 0–4; status 3 (CD check) is traced in full below it. `ztie.md` §7 item 10. |
| `print_string_obj2off` | 0x08B490 | 0xB8C90 | Shared helper, takes an obj2-relative string offset and prints it (the `"ERROR #%d:"` family and others — 14 inrefs, consistent with a shared utility). `ztie.md` §7 item 10. |
| `find_cd_drive_via_mscdex` | 0x089448 | 0xB6C48 | Loops MSCDEX-reported drive letters, tries `\ASTREAM\A.WRK` on each; first success wins. A real MSCDEX probe, not a config/file check. `ztie.md` §7 item 10. |
| `mscdex_build_drive_check_req` | 0x08956C | 0xB6D6C | Builds a DPMI real-mode register block: `AH=0x15 AL=0x0B` (INT 2Fh AX=150Bh, MSCDEX Drive Check); checks `BX==0xADAD` signature. `ztie.md` §7 item 10. |
| `mscdex_build_install_check_req` | 0x089520 | 0xB6D20 | Builds `AH=0x15 AL=0x00` (INT 2Fh AX=1500h, MSCDEX Installation Check); reads back BX/CX = drive count / first drive letter. `ztie.md` §7 item 10. |
| `probe_astream_a_wrk` | 0x08E0EF | 0xBB8EF | Tries to open `\ASTREAM\A.WRK` on a candidate drive, flags/mode 0xDD8. `ztie.md` §7 item 10. |
| `dpmi_rmcs_call` | 0x08FF23 | 0xBD723 | Common path both MSCDEX builders go through (27-byte sweep-recognized function, matches `functable_v2.txt`'s own size for this row); chains onward to `dpmi_simulate_real_mode_interrupt`. `ztie.md` §7 item 10. |
| `dpmi_simulate_real_mode_interrupt` | 0x08FF48 | 0xBD748 | Contains file 0xBD80D. Stages `AX=0x0300` (file 0xBD7E6) then `mov eax,0x31 ; int 0x31` (file 0xBD80D) = DPMI "Simulate Real Mode Interrupt". Explains why grepping for literal `1500h`/`150Bh` 16-bit immediates found nothing: AH/AL are written as separate byte-stores into the RMCS, never one `mov ax,imm16`. `ztie.md` §7 item 10. |
| `crt_entry` | 0x08B4E4 | 0xB8CE4 | LE module entry (obj1+0x7B4E4, from the LE header's own EIP field). Watcom C/C++32 CRT: `jmp short` over its own banner — a legitimately 2-byte function body (jmp is terminal). `ztie.md` §1. |
| `trace_log_file_line` | 0x09F20C | 0xCCA0C | The trace logger every module-map reference site calls (`eax`=filename obj2-offset, `edx`=source line); byte-verified disassembly at 0xA2770 (§5c). Plainly returns (`ret 4` @ 0x9F22E). |
| `stk_stack_check` | 0x08B2EE | 0xB8AEE | Watcom's `__STK` stack-overflow check — 16 B, `xchg [esp+4],eax ; call 0x8B301 ; mov eax,[esp+4] ; ret 4`; target of all 133 `push imm32 ; call` prologues (§5). Applied by `TieFixStackCheck.java`. |
| `panl_blit_lfd` | 0x04977C | 0x76F7C | The `PANL` blitter — its opcode walk (`0xFB` bias / `0xFC` x-advance / `0xFD` run / `0xFE` end-of-row / `0xFF` end-of-panel) tiles all 70 LFD `PANL` records exactly (189/200 and 456/480 rows). `LFD.md` §5. |
| `panl_blit8` | 0x04C280 | 0x79A80 | 8-bit PANL-family renderer (same opcode set, `FB`=2 B / `FC`=3 B variant, straight into the VGA framebuffer); reached via the 39-entry dispatch table @ linear 0xC1EA4, slot 7. `LFD.md` §9. |
| `panl_blit16` | 0x04E71C | 0x7BF1C | 16-bit sibling of `panl_blit8` — same dispatch table, block 2. `LFD.md` §9. |
| `lfd_find_record` | 0x097020 | 0xC4820 | The generic LFD record lookup (XRES.C, 324 B): start at `(count+2)*0x10`, walk `offset += length + 0x10`; hands back bytes, never interprets them. `LFD.md` §9. |
| `load_cockpit_lfd_records` | 0x043B6C | 0x7136C | `FUN_00043710` passes the resource name in EAX, `0x15928 + 0x0E*index + 2` in EDX, and `3` in EBX. The routine builds `CP640\\<name>.LFD`, walks the three positional records into that table, compares the third record type with `PLTT`, and shifts the loaded palette bytes right by two. `LFD.md` §2 and §9 item 1. |
| `decode_cockpit_mask_rle` | 0x044008 | 0x71808 | The direct call at file 0x711CF loads EAX from the table's second slot (`0x1592E + 0x0E*index`), i.e. the `MASK` record returned by `load_cockpit_lfd_records`. The body consumes zero-escaped row spans, handles the 0/0 and 0/FF long-run forms for widths other than 320, writes the normalized stream to the cockpit buffer, and reverses each row when ECX is non-zero. `LFD.md` §9 item 1. |

Each renamed function also carries a plate comment with the same evidence,
and (when the anchor cited sits mid-function, e.g. `dpmi_simulate_real_mode_interrupt`'s
file-0xBD80D `int 0x31` site) an EOL comment at the exact byte.

## 4b. Bulk naming from the module map — 804 of 3,528 (2026-08-26)

`work/module_map.py --names` emits an address→name map for every function inside
one of the 38 module spans, and `TieNameByModule.java` applies it. **786 named,
0 failures, 0 misses.** With the 18 hand-verified names that is **804 of 3,528
functions (22.8 %)**, up from 10.

The scheme encodes **only what the binary states**:

```
XACTOR_L0971      module XACTOR.C, lowest source line its own trace calls report
XMEMHDL_08bb9c    module XMEMHDL.C, no trace call inside -> address
```

This is a §4-grade verified anchor — module membership comes from the LE fixup
table and the line from the `trace_log_file_line` call operands — but it is
**provenance only**. A name like `XACTOR_L0971` says where the function came
from, not what it does; a semantic name still needs its own anchor. The script
only touches `FUN_*` symbols and only on an exact entry-point match, so
hand-verified names are never overwritten and the §5b "names a function that
merely contains the address" hazard cannot recur.

Coverage by module: XFILM 115, XACTOR 92, XPAL 52, XINPATTR 52, XVIEW 44,
XIO 35, XFONT 34, XCANVAS 31, XMEMHDL 28, XBM 24, …

**A free cross-check.** The FILM opcode callees traced independently in
`LFD.md` §6b land on sensible, adjacent lines:

| opcode | function | line |
|---|---|---|
| 13 (two-way branch) | `XACTOR_L0474` / `XACTOR_L0484` | adjacent, as a paired if/else should be |
| 4 | `XACTOR_L0971` | |
| 6 / 7 / 8 | `XACTOR_L1059` / `L1104` / `L1133` | ascending with opcode order |
| 14 | `XACTOR_L1230` | |
| 11 and 12 | both `XRECT_L0043` | the same routine, as the dispatch said |

None of that was used to derive the names; it falls out of them.

Metrics are unchanged by the pass: 3,528 functions, 91.6 % union, 64.7 % sweep
agreement.

## 4c. Bulk decompile corpus — 3,528 functions (2026-08-23)

`work/ghidra_export/obj1_c.c` (4.9 MB, 179,116 lines) holds Ghidra's C for
**every function in obj1**, each with a `// ==== <name> @ <addr>  body=N B ====`
header, produced by the same single `-import` run as everything else (§5,
"never use `-process`"):

```
  -postScript TieDecompile.java 10000 bb000 "$PWD/work/ghidra_export/obj1_c.c"
```

3,528 written, **8 decompile failures** (99.8 %). Names from §4/§4b carry
through, so 813 of the headers are meaningful (`XACTOR_L0971`, `panl_blit_lfd`,
`lfd_find_record`) and 2,715 are still `FUN_*`.

**The corpus is a reading aid, not the artifact of record.** The proven
disassembly is `work/ratchet32/stub.asm`, which re-assembles to the original
bytes (`analysis/reassembly.md`); the C does not and cannot. Ghidra's output
invents names, synthesises control flow and silently drops what it cannot
render — this session it omitted a `2E` segment prefix from an `or` and printed
branch targets in decimal. Read it to understand a routine, then cite the flat
address and check the bytes. `F030Method/METHOD.md` §4.2 ("nothing without a
source") applies to anything ported out of it.

Adopted from UW2, which keeps the same pair — `disasm.txt` alongside `uw_c.c`
(`F030Underworld2/analysis/ghidra.md` §5). It is **gitignored** (4.9 MB,
regenerable in one run); the small per-topic decompiles cited by
`analysis/LFD.md` stay committed as evidence for specific claims.

**What it changes in practice:** questions that used to cost a pipeline run each
are now a grep. "Which functions call the LFD record lookup?" — six, in
seconds — where previously I decompiled one candidate at a time and burned
several passes guessing which to try.

## 4d. String cross-references — 750 functions annotated (2026-08-23)

`work/string_xrefs.py` walks every obj1→obj2 fixup, reads the NUL-terminated
string starting **exactly at the target**, and attributes it to the enclosing
function. A string-pool cross-reference is one of the verified anchors §4 allows.

- **750 of 3,528 functions** reference at least one string
- **678** reference exactly one — the strongest naming candidates
- **178** of those are still `FUN_*`
- 288 distinct strings; output: `work/ghidra/obj1_notes.txt`

**It names nothing.** What a function *does* with a string it references is an
inference; the file is evidence for a later, per-case naming pass.

### Read from the fixup target, not from the enclosing run

First version mapped the target into the typed string run from
`work/type_obj2.py` and reported the whole run. Binary tables that sit
immediately before a literal share its run *and* its NUL, so it reported
`PPPPHHHHPPPHHHoptions.cfg` where the code actually points at `options.cfg`, and
`ssSTRINGS.DAT` for `STRINGS.DAT`. Reading from the fixup target fixed it.

### Two failed attempts at a quality filter, both worth recording

I tried twice to score the extraction's precision and both classifiers were
worse than the data:

- "contains a lowercase run and punctuation" rejected `.TFR`, `/320`,
  `DEMO.TIE`, `ADLIB.LFD`, `MICRO.FNT` — all real.
- "no vowel and no punctuation ⇒ table bytes" rejected `320x200`, `640x480`,
  `PLTT`, `brfpnl`, `cmbtfly1`, `trnfly1` — all real.

So no precision figure is quoted. A handful of entries (`BJFNREBRJRFVJVRJFVJV`,
`p`pppppppppppppALPHA`) really are table bytes that happen to be printable and
NUL-terminated, and I could not separate them automatically without discarding
real strings. Recorded as a known residue instead of a number.

**It immediately overturned a claim**: `PLTT` is referenced from
`FUN_00043B6C`, so `LFD.md`'s "no tag comparison exists anywhere in the image"
was too strong. See there.

## 5. Under-sized bodies: Watcom's `__STK` stack check — **diagnosed 2026-08-22**

~~"`game_main` and `check_system_requirements` — the two created fresh with no
prior sweep coverage — exported at 10 bytes each … Likely cause:
`createFunction` was called after only a minimal `disassemble()` at the entry,
without a full flow-following re-analysis pass."~~ — **that guess is
withdrawn.** The cause is specific, systemic, and byte-verified.

**133 function prologues in obj1 are `push imm32 ; call 0x8B2EE`**, e.g.

```
00010010  6868000000    push 0x68          ; game_main
00010015  e8d4b20700    call 0x8b2ee
000672d5  68b0000000    push 0xb0          ; check_system_requirements
000672da  e80f400200    call 0x8b2ee
```

and `0x8B2EE` is **Watcom's runtime stack-overflow check** (`__STK`), 16 bytes,
which plainly *returns*:

```
0008b2ee  87442404      xchg dword ptr [esp+4], eax   ; frame size -> eax
0008b2f2  e80a000000    call 0x8b301                  ; cmp eax,esp / cmp eax,[0x1308c]
0008b2f7  8b442404      mov  eax, dword ptr [esp+4]   ; restore eax
0008b2fb  c20400        ret  4                        ; pops the pushed immediate
```

(the checker at 0x8B301 compares against a stack limit at `0x1308c`, then `ss`
against `[0x12b50]`, and only on failure calls the reporter at 0xB0ACB.) The
pushed immediate is the frame requirement — `game_main` pushes 0x68 = 104 for
`sub esp,0x48` + 5 saved registers.

Ghidra's *Non-Returning Functions - Discovered* analyzer marks it **no-return**
(`hasNoReturn` reads `true`), so flow stops immediately after the call and the
function exports with a body of exactly **10 bytes** (`push` + `call`). Of the
133 sites, **84 were function starts in the pre-repair table and all 84 had
10-byte bodies** — systemic, not the 2 cases this section first recorded.

Also corrected: **`probe_astream_a_wrk`'s 10 bytes are genuine, not truncation**
— `push ebx ; xor ebx,ebx ; call 0x8E0D4 ; pop ebx ; ret` is exactly 10 bytes
and complete. `crt_entry`'s 2-byte body was already known-good.

### The repair — **ADOPTED** (verdict reversed 2026-08-22)

Clearing the no-return flag alone changes nothing: the verdict is baked into each
call instruction at disassembly time as flow type **`CALL_TERMINATOR`** with a
null fall-through (and `isFallThroughOverridden()` is `false`, so there is
nothing to "clear"). What works is `Instruction.setFlowOverride(FlowOverride.
CALL)` per site, plus removing the `FUN_*` tail that had adopted the rest of the
body, then recreating with `CreateFunctionCmd(..., recreateFunction=true)` —
`work/ghidra_scripts/TieFixStackCheck.java`, now part of the pipeline.

**Correction — the earlier scale and verdict were both wrong.** This section
previously said:

> ~~"Of the 133 sites, **84 were function starts in the pre-repair table and all
> 84 had 10-byte bodies** — systemic, not the 2 cases this section first
> recorded."~~ and ~~"**But it makes the table worse overall** … body union
> 91.6 % → 76.2 %, agreement with the capstone sweep 64.7 % → 55.8 % … So the
> script stays **out of the documented pipeline**."~~

Both were measured on a **database I had corrupted myself** — an earlier broken
`TieRename.java` run created truncated functions with `CreateFunctionCmd`, and I
then diagnosed my own damage as a Ghidra defect and "repaired" it against a
clean baseline. Re-measured on clean single-shot builds:

| | fns | body union | agrees with sweep | truncated `__STK` callers |
|---|---|---|---|---|
| clean baseline | 3,529 | 91.6 % | 64.7 % | **1** |
| clean + `__STK` repair | 3,528 | 91.6 % | 64.7 % | **0** |

Of the 133 `__STK` prologue sites, **114** are function starts on a clean build
and exactly **one** of them is truncated. The repair changes exactly that one
function — `check_system_requirements` **10 → 3,097 bytes**, absorbing the
split-off tail `FUN_000672DF` (3,087 B) — and leaves both metrics untouched. It
is harmless and it fixes the real defect, so it is adopted.

The same correction applies to the trace logger `0x9F20C`: on a clean build the
three `XACTDELT.C` functions are **211 / 340 / 103 bytes**, not the 52 / 41 / 38
I reported, and exactly **one** function in the whole image ends on a call to it
(`FUN_000A8198`, 80 B, possibly legitimate). There was no epidemic there either.

`TieFixNoReturn.java` (the bounded variant) is kept for the case where a wrong
no-return verdict does appear, and its two usage traps still stand: a module span
bound is not an instruction boundary, so `getInstructionAt(lo)` returns null and
a walk-forward loop silently finds 0 sites — iterate
`Listing.getInstructions(AddressSet, true)`.

### Never use `-process`: do everything in one `-import` run

Three separate wrong conclusions in this document traced back to the same cause,
so it is now a rule. `analyzeHeadless -process` **saves the project**, and the
saved state drifted badly across even read-only-looking runs: after a rebuild
that exported 3,528 functions, a few `-process` runs (decompile, probe) left the
project holding **3,118** functions with `check_system_requirements` **gone
entirely**.

Run the whole chain — seed → rename → repair → export → decompile → probe — as
`-postScript`s of a single `-import`, and delete `TIE.gpr`/`TIE.rep` first. That
is what the regeneration command below now does, and it is reproducible.

(One residual: the in-process function count reads 3,530 while `TieExport`
writes 3,528. Not chased; treat the export as the artifact.)

### Decompiling the CD-check root

With the repair in place, `check_system_requirements` decompiles —
`work/ghidra_export/check_system_requirements.c`, 425 lines — and it corroborates
the byte-level trace in `ztie.md` §7 item 10 from a completely different
direction:

```c
uVar2 = stk_stack_check();                       /* the __STK prologue, named */
...
if ((_LAB_00013548 == 0) &&
    (DAT_000356ff = find_cd_drive_via_mscdex(), DAT_000356ff == '\0')) {
    iStack_2c = 3;                               /* status 3 == the CD failure */
}
```

That is the `0x13548` global the project chased and closed as a dead end: it is
a **genuine CD-check bypass** — when non-zero the probe is skipped entirely —
which is exactly why it was worth chasing, and it is still never set to non-zero
anywhere (`todo.md` P3.2). The status codes (2 and 3) and the call into
`find_cd_drive_via_mscdex` match the existing trace.

## 5b. The Ghidra function table is NOT reproducible across runs (2026-08-22)

Rebuilding the project from scratch on the macOS host — same Ghidra 12.1.3,
same `z_tie_obj1.raw`, same seed file, same three scripts, the exact
regeneration command in §"Regeneration" — produced a **materially different**
table. Both are kept: `work/ghidra_export/obj1_functions.txt` is the original
Windows run the sections above describe; `obj1_functions.macos.txt` is the
2026-08-22 macOS rebuild.

| | Windows run | macOS rebuild |
|---|---|---|
| functions | 3,186 | **3,529** |
| common starts | 3,086 | 3,086 |
| starts unique to that run | 100 | **443** |
| common starts, identical size | 2,334 | 2,334 |
| common starts, **differing** size | 752 | 752 |

So `analysis/functions.md`'s "3,186 functions" is **one measurement of a
heuristic tool, not an invariant of the binary** — cite it with its run, and
re-derive rather than trust it when a count matters. (Ghidra's own
`-import` + auto-analysis is order- and state-dependent; the committed
Windows table also came from a session where `TieExport.java` was re-run via
`-process` after a fix, per §"Regeneration".)

### The `getFunctionContaining` hazard — `game_main` moved

`TieRename.java` resolves each anchor with `fm.getFunctionContaining(addr)`,
which accepts **any** function covering the address, including one that starts
*before* it. In the macOS rebuild that fired:

- obj1 starts `cc eb fd` = `int3 ; jmp $` (a trap at 0x10000), then **13 NOP
  pad bytes** 0x10003–0x1000F, then the real code at **0x10010**
  (`push 0x68 ; call 0x8B2EE ; push ebx/ecx/esi/edi/ebp ; mov ebp,esp ;
  sub esp,0x48`) — byte-verified by disassembling `z_tie_obj1.raw[0:48]`,
  and exactly what the anchor comment in `TieRename.java` claims.
- The Windows run had a function **at** 0x10010, 10 bytes (the §5 truncation).
- The macOS run created one at **0x10003, 904 bytes** — it swallowed the NOP
  pad. `getFunctionContaining(0x10010)` found it, so `game_main` was renamed
  onto a function whose entry point is **13 bytes before its own anchor**.

(The seed `0x10003` comes from the LE fixup table, which
`work/gen_ghidra_seeds.py` documents as "a real cross-reference site, not
necessarily a function start" — so the pad function was seeded, not invented by
Ghidra.)

**FIXED 2026-08-22.** `TieRename.java` now resolves with `getFunctionAt` and,
when a *different* function covers the anchor, removes it and re-creates at the
anchor (`CreateFunctionCmd`, `recreateFunction=true`); it also reverts any
same-named function left at another entry to its default name rather than
deleting it. On a clean rebuild it reports `split=1` and `game_main` lands at
**0x10010 with 891 bytes** — and 891 + the 13 pad bytes is exactly the 904 the
unfixed run had at the wrong entry, which corroborates both readings. The
final table is 3,529 functions at 91.6 % union / 64.7 % sweep agreement:
same as the unfixed run, with `game_main` correct. All 10 anchors now land on
their exact entry points.

## 5c. Source-module map from the assert strings — **NEW 2026-08-22**

`Z_TIE__.EXE` was built with `assert()`-style diagnostics, so obj2 carries the
**38 original C source-file names** of the LucasArts "X" presentation library.
Every reference to one is an LE fixup targeting that string, and the linker laid
each translation unit out contiguously — so the span of a module's own reference
sites bounds that module's code.

```
python3 work/module_map.py [--functions work/ghidra_export/obj1_functions.macos.txt]
                                          # -> work/ghidra_export/module_map.txt
```

**The 38 spans are strictly ordered and do not overlap at all** (0 overlaps),
covering linear `0x088F92..0x0B3263`. That is the check that makes the layout
assumption safe to build on: 38 independent ranges derived from 1,671 reference
sites falling into disjoint, monotonically increasing blocks is not something a
wrong model produces.

The modules, largest first: `XFILM.C` (13.2 KB, 163 refs), `XPAL.C` (13.0 KB),
`XACTOR.C` (11.1 KB, 176 refs), `XINPATTR.C` (5.5 KB), `XMEMHDL.C` (5.0 KB),
`XFONT.C` (5.0 KB), `XVIEW.C` (4.5 KB), `XINPCALL.C` (4.3 KB), `XBM.C`,
`XRES.C`, `XCANVAS.C`, `XSTYLE.C`, `XRECT.C`, `XDIRTY.C`, `XACTANIM.C`,
`XACTDELT.C`, `XACTCUST.C`, `XACTRAW.C`, `XBTN*.C` (5 widget modules),
`XIO.C`/`XFILE.C`/`XFILEDIR.C`, `XMEM*.C` (4), `XTIMER.C`, `XCURSOR.C`,
`XFADE.C`, `XREMAP.C`, `XDIALOG.C`, `XPAINT.C`, `XVIEWADD.C`, `GAMESND.C`.

**787 of the 3,529 obj1 functions fall inside a module span** — provenance for
each of them that needs no guessing: `XFILM.C` 115, `XACTOR.C` 92, `XPAL.C` 52,
`XINPATTR.C` 52, `XVIEW.C` 45, `XIO.C` 35, `XFONT.C` 34, and so on. The spans
are deliberately conservative (min..max of *reference* sites, so a module's
lead-in and tail-out code falls outside), which is why this is a floor, not a
count.

The other **2,742 functions sit outside every span** — expected, since these 38
modules are the presentation library only. The flight model, 3-D renderer and
CRT are in that remainder and carry no source-name anchors.

### (file, line) anchors — the map is finer than filenames

Each reference site is the `imm32` of a `mov eax, <file>` feeding a call to
**`0x9F20C`**, and the `mov edx, imm32` in the same register setup carries the
**source line number**. Verified by disassembly at `0xA2770` (`XACTDELT.C`):

```
000a2785  6a01            push 1
000a2787  bb0e000000      mov  ebx, 0xe
000a278c  ba99000000      mov  edx, 0x99        ; line 153
000a2791  8b0d6e2f0100    mov  ecx, [0x12f6e]
000a2797  b814120000      mov  eax, 0x1214      ; obj2 offset of "XACTDELT.C"
000a279c  c1f910          sar  ecx, 0x10
000a279f  e868caffff      call 0x9f20c          ; trace logger -- `ret 4`, it returns
```

`python3 work/module_map.py --lines` recovers **1,286 (file, line) anchors**.
The line is taken from the nearest preceding `mov edx, imm32`, which is a
heuristic — so it is validated the only way that matters:

**Address order tracks source-line order almost perfectly.** Out-of-order pairs
are **137 of 57,939 = 0.2 %**, and **25 of the 27 modules with ≥10 anchors are
perfectly monotonic (0 inversions)**. The exceptions are `XPAL.C` (0.8 %) and
`XVIEW.C` (2.3 %). A byte-level mis-read would not produce that.

So every function in these modules can be placed in its original source file
*and* bracketed by line number — the strongest anchor available short of real
symbols, and all of it derived from the binary.

### What this unlocks

- **The `FILM` chunk opcodes** (`LFD.md` §9 item 2) now have a precise target
  instead of "read the film player": the block types map onto their own actor
  modules — `XACTDELT.C`, `XACTANIM.C`, `XACTCUST.C`, `XACTRAW.C`, `XVIEW.C`,
  with the shared base in `XACTOR.C` — which matches the census finding that
  each block type uses its own opcode set. Two switch jump tables sit inside
  `XFILM.C` (11 entries at `0x0A882C`, 10 at `0x0A8A70`, all targets within the
  module).
- **Naming**: a function's module (and now its source-line bracket) is a
  verified anchor in the §4 sense — it comes from the binary's own fixup table —
  so `FUN_*` names can carry a module prefix without inventing anything about
  what they do.

### The trace logger and the decompile pass — superseded by §5

`0x9F20C` is the trace logger and it **returns** (`ret 4` at `0x9F22E`). Ghidra
marks it non-returning, but on a clean build that costs almost nothing — see the
correction in §5: the `XACTDELT.C` functions are 211/340/103 bytes, not the
truncated 52/41/38 an earlier corrupted database showed, and only one function in
the image ends on a call to it. The "decompile pass stalled" reading recorded
here is withdrawn with the rest of that measurement.

## 6. Not yet named (next pass)

*(Refreshed 2026-08-26 — the earlier list predated §4b/§4c/§5: the body
repair is adopted into the pipeline, `check_system_requirements` and the
bulk corpus decompile, and the provenance pass has named 804.)*

- **Semantic naming from string-xref anchors** — 678 functions reference
  exactly one string (§4d, `work/ghidra/obj1_notes.txt`), 178 of them still
  `FUN_*`; name per case from those anchors plus the decompile corpus
  (§4c), never in bulk — a name still needs its own §4-grade anchor.
- **FILM opcode handlers** (`LFD.md` §9 item 2) — read the block-type actor
  modules (`XACTDELT.C`, `XACTANIM.C`, `XACTCUST.C`, `XACTRAW.C`, `XVIEW.C`
  over the shared `XACTOR.C`, sequenced by `XFILM.C`) to turn the recorded
  field effects into meanings.
- **`MASK` format** — characterize the row-span contract consumed by
  `decode_cockpit_mask_rle` (`FUN_00044008`) and its dimension/mode inputs
  (`LFD.md` §9 item 1).
- **`SHIP` renderer** (`LFD.md` §9 item 3) — lives in the 2,742 functions
  outside every module span (the 38 named modules are the presentation
  library only).
- **obj2 data typing** — label the known string pools and the structured
  unknowns `type_obj2.py` lists (a 3,086 B `01 00` array, a powers-of-two
  run, a `0x16D`-delta ramp — `reassembly.md` §obj2); feeds P2.x and the
  build's typed share.

## 7. Files

- `work/slice_objects.py` — obj1/obj2 slicer (regeneration command, §1).
- `work/gen_ghidra_seeds.py` — seed-list generator; `work/ghidra/obj{1,2}_seeds.txt`
  (5,149 / 3,608 addresses; obj2's is generated but **unused** by design, §1).
- `work/ghidra_scripts/TieSeedFunctions.java` — seeds function starts from a
  seed-list arg (idempotent: skips anything `getFunctionContaining` already
  covers).
- `work/ghidra_scripts/TieRename.java` — applies §4's table (idempotent: same
  contains-check, then rename vs. create).
- `work/ghidra_scripts/TieExport.java` — dumps `addr size inrefs name` for
  every function in the current program.
- `work/ghidra/` — the Ghidra project (`TIE.gpr`/`TIE.rep`), two programs:
  `z_tie_obj1.raw` (function count varies per run — §5b), `z_tie_obj2.raw`
  (data, no functions).
- `work/ghidra_export/obj1_functions.txt` — the full function table from the
  **Windows** run (§4's names are grep-able there);
  `obj1_functions.macos.txt` — the 2026-08-22 macOS rebuild (3,529 functions,
  91.6 % union / 64.7 % sweep agreement, all 12 anchors on exact entry points).
  They differ substantially (§5b); neither supersedes the other, but the macOS
  table scores better on both metrics defined in §5;
- `work/ghidra_scripts/TieFixStackCheck.java` — the `__STK` repair, **now part of
  the pipeline** (§5: it fixes the one truncated function and leaves both metrics
  unchanged); `TieFixNoReturn.java` — the bounded variant, for a wrong no-return
  verdict elsewhere; `TieDecompile.java` — decompile an address range;
  `TieProbe.java` — one-shot state probe;
- `work/ghidra_export/obj1_c.c` — **the bulk decompile corpus**, all 3,528
  functions (§4c; gitignored, regenerate with the pipeline);
  `check_system_requirements.c` and the per-topic decompiles cited by
  `analysis/LFD.md` stay committed as evidence; `*_import.log` / `*_process*.log` — full
  headless run logs, kept for the exact tool-quirk evidence in §2.

### Regeneration

**One `-import` run, never `-process`** (§5). Delete the project first — the
scripts are ordered so the repair follows the renames:

```
python work/slice_objects.py
python work/gen_ghidra_seeds.py

GH=/opt/homebrew/Cellar/ghidra/12.1.3/libexec/support        # macOS
export JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home
rm -rf work/ghidra/TIE.gpr work/ghidra/TIE.rep
$GH/analyzeHeadless work/ghidra TIE \
  -import work/ghidra/z_tie_obj1.raw -processor x86:LE:32:default \
  -loader BinaryLoader -loader-baseAddr 0x10000 -loader-blockName OBJ1_CODE \
  -scriptPath work/ghidra_scripts \
  -postScript TieSeedFunctions.java "$PWD/work/ghidra/obj1_seeds.txt" \
  -postScript TieRename.java \
  -postScript TieNameByModule.java "$PWD/work/ghidra/obj1_names.txt" \
  -postScript TieFixStackCheck.java \
  -postScript TieExport.java "$PWD/work/ghidra_export/obj1_functions.macos.txt" \
  -postScript TieDecompile.java <loHex> <hiHex> "$PWD/work/ghidra_export/<out>.c"

# obj2 (data) -- separate import, no function seeding by design
$GH/analyzeHeadless work/ghidra TIE \
  -import work/ghidra/z_tie_obj2.raw -processor x86:LE:32:default \
  -loader BinaryLoader -loader-baseAddr 0xC0000 -loader-blockName OBJ2_DATA
```

Generate the name map first:
`python3 work/module_map.py --functions work/ghidra_export/obj1_functions.macos.txt --names work/ghidra/obj1_names.txt`

Expected on a clean run: `TieSeedFunctions made=2409 already_covered=2652
failed=88`, `TieRename created=3 renamed=14 split=1`, `TieNameByModule
named=785 already_named=1`, `TieFixStackCheck repaired=1`, `TieExport wrote
3528`.
(`ClearFlowAndRepairCmd` WARN lines during analysis are normal and pre-date this
pass.)

The Windows-host equivalent used `"C:/tools/ghidra_12.1.3_PUBLIC/support/analyzeHeadless"`
and produced 3,186 functions (§5b — the table is not reproducible across hosts).
