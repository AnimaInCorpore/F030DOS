# UW2.EXE — Ghidra workflow (16-bit x86 Real Mode)

Ghidra headless import/export of `UW2.EXE`, and what's specific to UW2 versus
the shared pipeline. Read `C:\Arbeit\F030Underworld\analysis\ghidra.md` first
— tooling, the loader patches, and the export script mechanics are identical
and not repeated here.

## 1. Tooling

Same as UW1 §1: Ghidra 12.1.3 + the patched GhidraDosToolbox extension,
installed **globally** at
`C:\Users\sasch\AppData\Roaming\ghidra\ghidra_12.1.3_PUBLIC\Extensions\GhidraDosToolbox`
— not per-project — so the three loader patches (out-of-range segment filter,
`CODE_TAIL` block, `processRegisters` cast fix) applied to `UW2.EXE`
automatically. No UW2-specific loader changes were needed.

## 2. Headless import + export (2026-08-21)

```
cd C:/Arbeit/F030Underworld2
C:/tools/ghidra_12.1.3_PUBLIC/support/analyzeHeadless.bat \
    work/ghidra UW2_16 \
    -import work/extracted/D3/UW2.EXE \
    -postScript UWExport.java -scriptPath work/ghidra_scripts
```

- Project: `work/ghidra/UW2_16`. Loader/language chosen by opinion, same as
  UW1: **Old-style DOS Executable (MZ)(Experimental)** +
  **`x86:LE:16:Real Mode:default`**.
- `work/ghidra_scripts/UWExport.java` is UW1's script with only the `outdir`
  changed (`work/ghidra_export/` under this repo). Do not re-derive it.
- One run, import through export: analysis 140 s, decompile loop the rest —
  **≈15 minutes total**, dominated by decompiling 2,257 functions.
- **Exit code 0. Import succeeded, project saved.**

## 3. Resulting address model — RESOLVED

`work/ghidra_export/memory_layout.txt`, checked programmatically (not by eye):

| Space / block | Range | Content |
|---|---|---|
| `HEADER` | `HEADER::0000..2dff` (11,264 B) | MZ header + relocation table, matches `e_cparhdr*16` exactly |
| `CODE_0..CODE_777` | `1000:0000` … `7e87:0000..050f` (778 blocks) | the loader image. **Verified zero gaps and zero overlaps** across all 778 blocks (script-checked via linear `seg*16+off`); first block starts at linear `0x10000`, last ends at `0x7ED7F` |
| `int` | `int::0000..03ff` (1,024 B) | synthetic interrupt-vector space |
| `CODE_TAIL` | `CODE_TAIL::071b80..0a507f` (210,176 B) | the `FBOV` overlay pool tail |

**File ↔ Ghidra address**, verified two independent ways:

- `CODE_0` starts at `1000:0000`, which is file `0x2E00` (`e_cparhdr*16`, the
  first byte of the loader image) — so `file = header_size + ((seg−0x1000)<<4) + off`,
  same form as UW1.
- `CODE_TAIL` linear range `0x71B80..0xA507F` matches the file arithmetic in
  `AGENTS.md` exactly (`image_size=0x71B80`, `filesize=0xA5080`) — the tail
  block's raw offset **is** the file offset, no translation needed, same as UW1.

**Ghidra skew = `0xD200`, confirmed** (was TBD): predicted from
`0x10000 − e_cparhdr*16 = 0x10000 − 0x2E00 = 0xD200`. Applied to DGROUP's
verified file offset (`0x68E80`, `AGENTS.md`): `0x68E80 + 0xD200 = 0x76080` =
seg `7608:0000`. **`CODE_742` starts at exactly `7608:0000`** — a block
boundary Ghidra derived independently from the relocation table, landing on
the exact byte the file arithmetic predicted. Two unrelated derivations, one
answer.

## 4. Relocation-application gap — IDENTIFIED, not a coverage problem

Import logged **222 "Failed to process relocation"** and **277 "Skipping
out-of-range segment"** — both far above UW1's single documented anomaly (38
entries, all frame `0x0000`). Root-caused by checking the actual block list
(`work/ghidra_export/memory_layout.txt`) instead of trusting the log alone:

- **The 222 failures come from only 4 distinct linker-frame segments**
  (`018e`, `01dc`, `07ea`, `0213` — each with many relocation entries inside
  it). All 4 are **absent from the block-start list**: e.g. relocation-segment
  `0x018e` → Ghidra `118e:0000`, which falls *inside* `CODE_94`
  (`1188:0000..1188:00df`), not at its own block start. The loader's linker
  frames got coalesced into a larger neighboring block during import (the same
  merging UW1 §1 item 2 describes — "some merged up to 8,896 B"), and
  whatever indexes relocations by exact block-start segment then fails to
  find one for `018e`. **Consequence: instructions inside these 4 segments may
  carry the unpatched linker-relative segment immediate instead of the
  resolved one — unverified which, if any, actually matter; treat
  segment-immediate operands in `CODE_94`/`CODE_105`/`CODE_114`/`CODE_221` as
  suspect until checked against `disasm.txt` by hand.**
- **The 277 skipped segments are the *out-of-range* filter working as
  designed**, not a new problem: every sampled value (`0025`, `8000`,
  `9105`, …) resolves (as a linker frame, +0x1000 base) to a file offset at or
  past `image_size` (`0x71B80`) — i.e. these are references into the `FBOV`
  overlay tail, which is deliberately *not* given per-segment blocks (it's one
  `CODE_TAIL` block instead, per UW1 §1 item 2). This is exactly the filter's
  job; the count is just bigger here because UW2's tail is reached from more
  places than UW1's.
- Frame `0x0000` — the specific 38-entry anomaly `AGENTS.md` carried over from
  UW1 and marked TBD — **did not appear in this log at all** (`grep` for
  `0000:0000` in the skip list: zero hits). That doesn't resolve the original
  TBD (which asks about the *stock DOS loader's* behavior, not Ghidra's
  experimental one) but is worth recording: whatever Ghidra's loader does with
  frame-0 relocations, it isn't logging them as out-of-range the way it does
  for tail references.

Practical takeaway: **byte coverage is complete and exact** (§3's zero-gap
check), so `disasm.txt` and `uw_c.c` can be trusted as covering the whole
image. The open risk is narrow and named: segment-immediate operands
specifically inside `CODE_94`, `CODE_105`, `CODE_114`, `CODE_221`.

✗ **That last sentence is withdrawn — see §4b.** The risk does not exist, and
the root-cause story above does not reproduce.

## 4b. The §4 relocation risk, checked and dismissed — RESOLVED (2026-08-22)

§6 carried "spot-check `CODE_94`/`CODE_105`/`CODE_114`/`CODE_221` for stale
segment-immediate operands" as an open box. Checked. **There is nothing to
spot-check**, and two of §4's claims do not survive.

### The four named blocks contain no relocation targets at all

Parsing the MZ table (2,809 entries) and `memory_layout.txt` (780 blocks) and
mapping every target to its containing block:

| block | Ghidra range | file range | relocation targets inside |
|---|---|---|---|
| `CODE_94` | `1188:0000..00df` | `0x4680..0x475F` | **0** |
| `CODE_105` | `11cf:0000..010f` | `0x4AF0..0x4BFF` | **0** |
| `CODE_114` | `1210:0000..007f` | `0x4F00..0x4F7F` | **0** |
| `CODE_221` | `17e8:0000..002f` | `0xAC80..0xACAF` | **0** |

Nothing in those blocks is a relocation target, so nothing there can have been
left unpatched. **All 2,809 targets fall inside some block** (zero unmapped).

### §4's root cause does not reproduce

- ✗ "*4 distinct linker-frame segments (`018e`, `01dc`, `07ea`, `0213`)*" —
  the table has **53** distinct segment values and **none of them is any of
  those four**. They are not MZ relocation segments.
- ✗ "*whatever indexes relocations by exact block-start segment then fails to
  find one*" — testable, and it gives the wrong numbers: relocations whose
  `seg+0x1000` has no block starting there number **1,812 across 41
  segments**, not 222 across 4.

The 222 log lines were real, but they came from an import log this repo does
not keep, and neither their count nor their segment ids can be re-derived from
the file plus the block list. Recorded as **not reproducible** rather than
explained away.

### What actually matters downstream, and it is fine

The real question for anyone reading `disasm.txt` is whether segment
immediates are *relocated* or *raw file* values — because a mixture would be
the dangerous case. Diffing Ghidra's text for `CODE_9` (which does contain two
relocation targets) against capstone on the same file bytes: 24 instructions
each, and every difference is cosmetic (`0x6` vs `6`, `1000:00e3` vs a flat
address, register case). **No operand value differs.** The two relocation
targets at file `0x2EAE`/`0x2EB2` hold the raw word `0x5F1C`, and `0x5F1C` is
exactly what Ghidra prints (`PUSH 0x5f1c / POP DS`).

So **Ghidra's export carries unrelocated, file-native segment values
uniformly** — which is precisely what §§10b–10f depend on (`runtime = static +
L`, with `L = (delta + 0x2E00) >> 4`). There is no stale-versus-fresh
inconsistency anywhere in the export, so the caveat is removed rather than
narrowed.


## 5. Exports

`work/ghidra_export/` (2026-08-21):

| File | Size | Content |
|---|---|---|
| `memory_layout.txt` | 784 lines | all blocks, ranges, perms |
| `functions.txt` | 2,265 | `addr size(instr count) inrefs name` |
| `disasm.txt` | 130,137 lines / 2.17 MB | full 16-bit disassembly, per-block |
| `uw_c.c` | 12.98 MB, 2,257/2,265 fns (8 timed out or failed) | decompiler C, `// @ addr` headers |

## 6. State (2026-08-21)

- [x] extension picked up automatically (global install, no per-project setup)
- [x] program imported, auto-analyzed, exported — see §2
- [x] address model verified programmatically, zero gaps/overlaps — §3
- [x] Ghidra skew `0xD200` confirmed against the DGROUP CRT-string offset — §3
- [x] relocation-application gap root-caused (4 merged segments) — §4
- [~] semantic pass 1 (UW1-style renames): **seeded, not done** — §12.
      17 verified names + 224 string-annotated functions in
      `work/ghidra_export/symbols.txt`. UW1's
      `work/ghidra_scripts/UWRename.java` targets UW1's own addresses — do not
      run it unmodified against this project.
- [x] locate `main`/game loop, the top-level LEV/CNV/STRINGS readers, and the
      save (SAVE0\lev.ark) machinery — **`main` `0x88940`, `game_loop`
      `0x88B3F` (§27), `main_init`'s 45-step boot order and `main_shutdown`'s
      9-step teardown (§32), and the save/restore module in overlay 149 (§33)**.
      A save is a directory copy of `SAVE0\` into `SAVE1..4\`; there is no
      bespoke save format. Same open items UW1 §6 lists for
      itself; check UW1's answers against UW2 before re-deriving. **Started,      not finished — §7**: traced the direct callers of the mouse-read
      routines and found a much bigger structure (an apparent global
      callback-dispatch mechanism) than "the game loop calls the mouse
      reader directly."
- [x] spot-check `CODE_94`/`CODE_105`/`CODE_114`/`CODE_221` (§4) — **done,
      and the risk was void**: those blocks contain zero relocation targets,
      and Ghidra's export carries raw file segment values uniformly (verified
      by diffing a block that *does* contain targets against capstone). §4b.

## 7. Tracing the game loop: a callback-dispatch layer, not a direct call — IDENTIFIED, not resolved

Starting point: `analysis/qemu-boot.md`'s live EIP histogram showed the
segment-3133 mouse-read helpers (`FUN_3133_06e7`, `FUN_3133_0703`) as the
hottest code during real gameplay. Tracing every `CALL`/`CALLF` in
`disasm.txt` whose target linear address matches either function (script,
not grep-by-eye — both functions' Ghidra addresses converted to linear and
matched against every call operand in the 130K-line export) finds **exactly
one call site each, both in the same block, `CODE_389` (`31cd:0000..01bf`)**:

```
CALL 0x3000:1a17   ; -> FUN_3133_06e7  (motion-read)
CALL 0x3000:1a33   ; -> FUN_3133_0703  (position/button-read)
```

These calls sit inside `FUN_31cd_000d` and `FUN_31cd_0050` — but those two
have **`inrefs=0` in Ghidra's own analysis**, and grepping the full
decompiled `uw_c.c` for either name finds only their own definitions, no
call sites. **Nothing in this binary reaches them by an ordinary direct
call.** Their decompilation explains why:

```c
void __cdecl16far FUN_31cd_000d(void)
{
  undefined2 in_BX;
  puRam00030752 = &stack0xfff4;
  DAT_60ff_029e = 0x1d03;        // <- this function's own "ID"
  DAT_60ff_02a0 = FUN_3133_06e7();
  DAT_60ff_02a2 = in_BX;
  return;
}
```

`__cdecl16far`, a private-stack switch (`puRam00030752`/the `0x510`-ish
scratch area seen in the raw disassembly), and `RETF` — this is a
**callback trampoline shape**, not an ordinary subroutine: reached via an
indirect far call, not `CALL near`. **This is not an isolated pair.**
Grepping `uw_c.c` for the same shape finds a whole family sharing one
detail: every one of them writes a distinct small constant into the *same*
global, `DAT_60ff_029e`, as its first real action —

```
FUN_3133_0755  DAT_60ff_029e = 0x1aab;   -> FUN_3133_0000
FUN_3133_0791  DAT_60ff_029e = 0x1ae7;   -> FUN_3224_0107
FUN_3133_07cd  DAT_60ff_029e = 0x1b23;   -> FUN_3133_03a3
FUN_3133_0809  DAT_60ff_029e = 0x1b5f;   -> FUN_3133_02ec
FUN_3133_0881  DAT_60ff_029e = 0x1bd7;   -> FUN_3133_05c8
FUN_3133_08bd  DAT_60ff_029e = 0x1c13;   -> FUN_3133_0236
FUN_3133_08f9  DAT_60ff_029e = 0x1c4f;   -> FUN_3133_01d0
FUN_3133_0935  DAT_60ff_029e = 0x1c8b;   -> FUN_3133_0189
FUN_31cd_000d  DAT_60ff_029e = 0x1d03;   -> FUN_3133_06e7  (mouse motion)
FUN_31cd_0050  DAT_60ff_029e = 0x1d46;   -> FUN_3133_0703  (mouse position)
FUN_31e9_039b  DAT_60ff_029e = 0x2257;   -> FUN_31e9_0074
FUN_3224_002f  DAT_60ff_029e = 0x229b;   -> FUN_31cd_00d8
```

— a uniform, mechanical pattern (same shape, sequential-looking constants
in the `0x1aab..0x229b` range, one per thunk), strongly suggesting an
**auto-generated per-function trampoline table**, not hand-written
per-callsite code. This is *not* the 1,006 `INT 3Fh` overlay thunks already
documented in `AGENTS.md` (those are 5-byte `CD 3F` pairs at file
`0x66AB0..0x68E7E`; these are full `push`/`stack-switch`/`call`/`pop`
sequences living around file `0x24xxx`, a different mechanism entirely).

**The strongest lead for what reads `DAT_60ff_029e` back**: one caller,
`FUN_31e9_02ba`, writes `DAT_60ff_029e = 0x3000` (a *segment*, not an
offset/ID like the others — and `0x3000` is exactly the frame base this
whole document's jump/call targets have been expressed relative to) and a
sibling `DAT_60ff_029c = 0x217d` immediately before `func_0x00005bb3()` — a
call through a fixed low address rather than a resolved function name,
Ghidra's usual signature for an indirect call it couldn't statically
resolve. The two globals sit 2 bytes apart, exactly the layout of a real
4-byte `offset:segment` far pointer split across two 16-bit variables.
**Original working hypothesis (below) — ✗ withdrawn, disproved on the
oracle, 2026-08-21**: "`DAT_60ff_029e`/`DAT_60ff_029c` is a global 'current
handler' far-pointer pair that something else sets and invokes generically."
Computed the pair's address the same way as every `FUN_` label in this
document (Ghidra seg:off → linear → minus the `0xD200` skew → file offset →
plus the boot's calibrated `delta`) and watched it live during real
gameplay for 80 samples over ~20 s, spanning multiple hits inside the very
mouse-read trampolines that are supposed to write it
(`work/qemu_out`-style probe, reusing `gdbstub_probe.py` as a library
against an already-running session). The value **never changed**:
`029c=0x00c4, 029e=0x0701` in 78/80 samples, matching none of the ID
constants above and no plausible segment value. The address computation
that works for ordinary `FUN_`/data labels does not hold here.

**Why, and the better-supported replacement hypothesis**: every function in
this family carries Ghidra's own warning, *"This function may have set the
stack pointer"* — and the raw disassembly confirms it, explicitly:
`CLI / MOV DX,SS / MOV SP,0x510 / STI / CALL ...`, a hardcoded switch to a
fixed mini-stack before the real call, undone symmetrically afterward. A
decompiler whose stack-frame model assumes `SP` is well-behaved will
misattribute writes relative to a hand-managed stack like this — which
means `DAT_60ff_029e = 0x1d03` is more likely **Ghidra mislabeling a push
onto that fixed `0x510` stack** as a global-variable write, not evidence of
a real, fixed, cross-function global. Given every one of the "ID" constants
(`0x1aab`..`0x229b`) sits in the exact numeric range that this document's
own `0x3000:XXXX` jump/call-target convention uses, the far more likely
reading is that **each constant is that thunk's own resume/continuation
offset within the shared `0x3000` frame** — consistent with a
hand-rolled cooperative-scheduling or continuation mechanism built on a
fixed low-memory stack, not a discoverable "current handler" variable at a
fixed address at all.

**What this changes**: the mouse-read functions still are not called by
straightforward direct `CALL` (that part stands — `inrefs=0`, no call sites
in `uw_c.c`), but the mechanism reaching them is a fixed-stack
continuation/coroutine scheme rather than a pointer pair this project's
existing tools can read back with a simple address computation. Confirming
it precisely would need single-stepping or a breakpoint at the moment one
of these thunks is entered/resumes — `gdbstub_probe.py`'s
sampling-over-QMP approach can observe *that* code runs, but not *catch it
mid-transition* the way a real debugger would. That is a different kind of
tool than anything built so far in this project, not a small extension of
the existing polling probe.

## 8. Real breakpoints on QEMU's gdbstub — the tool §7 said didn't exist yet

§7 ended needing single-stepping or a breakpoint. `qemu-boot.md` records
that UW1 tried QEMU's raw gdbstub once, for *continuous register sampling*,
and abandoned it as flaky. That is a different job from *set one
breakpoint, stop once, read the stack* — worth retrying narrowly rather
than ruled out by the earlier note. It worked cleanly on the first attempt
and every attempt after:

- Enable it live, on an already-running, already-in-game session, over QMP
  — no need to relaunch QEMU with `-s`/`-gdb`: `human-monitor-command
  "gdbserver tcp::1234"`.
- Speak the wire protocol directly with a ~100-line hand-rolled Python RSP
  client (`$packet#checksum` framing, `Z0`/`z0` breakpoints, `g` for
  registers, `m` for memory, `c`/`s` to run) rather than pulling in `gdb`
  (not installed on this Mac) or wrangling `lldb`'s own assumptions about
  the target. Full control over every byte on the wire made the one real
  timeout hit (below) immediately diagnosable instead of mysterious.
- **The technique**: breakpoint a function's *entry point*, continue, and
  when it hits, read `SS:SP` off the register set and fetch 4 bytes from
  that physical address — for a function reached by `CALL far`/`CALLF`,
  those 4 bytes are the return `IP` then `CS`, i.e. the literal instruction
  the CPU will resume at. This identifies the true caller **regardless of
  whether the call was direct or computed** — it doesn't matter that Ghidra
  static analysis gives up with `inrefs=0`; the CPU always knows where it
  came from.

**Validated 5-hop chain from the confirmed-hot mouse-read code up to a
genuine dispatch loop** (all runtime addresses are this one boot's; boots
differ by the calibrated delta as always, `0x02F50` this run):

| # | Breakpoint (entry) | Confirmed caller (return address decoded) |
|---|---|---|
| 1 | `FUN_3133_06e7` (`INT 33h AX=0Bh`) | inside `FUN_31cd_000d` (§7's trampoline) |
| 2 | `FUN_31cd_000d` | `FUN_2beb_02c6+0x5b` |
| 3 | `FUN_2beb_02c6` | `FUN_2c22_0207+0xe` — matches a *static* call-site search exactly (`CALL 0x2000:c176`), cross-confirming the technique |
| 4 | `FUN_2c22_0207` | an **unnamed** address, runtime `0x280ab` (Ghidra has no function boundary there — the gap between named functions in `CODE_391`) |
| 5 | `0x280ab` (confirmed a clean entry: `ret` immediately precedes it, then `push si,ds,es`) | another **unnamed** address, runtime `0x1441f`, in segment `0C31` |

Reading the raw bytes at hop 4 (`capstone`, `CS_MODE_16`, straight off `xp`)
resolves everything static analysis couldn't:

```
280ab: push si / push ds / push es
280ae: call 0x2805d                  ; save the shared 0x510 scratch area
280b1: mov ax,0x6bdd / mov ds,ax / mov es,ax     ; DGROUP
280c3: mov sp,0x210c ... mov ss,0x6bdd            ; switch to a DEDICATED private stack (DGROUP:0x210C) --
                                                     not the tiny shared 0x510 buffer §7 was fixated on
280d4: mov ax,1 / push ax
280d8: lcall 0x2165,0xb27            ; == FUN_2c22_0207(1) -- confirmed: 0x2165:0xb27 is exactly
                                        runtime linear 0x22177, where hop 3's breakpoint landed
280de: (restore SS/SP)
280ea: call 0x28084                   ; restore the shared 0x510 scratch area
280f0: retf
```

The parameter `1` pushed before calling `FUN_2c22_0207` is the single most
useful new fact here: it reframes the whole hunt away from §7's
"per-handler ID written to a mystery global" toward something much more
ordinary — **`FUN_2c22_0207` looks like a generic "poll input device N"
entry point, called with a device-number argument (1 = mouse, here)**,
not a bespoke per-device callback table. Confirming that needs finding a
sibling call site with a *different* argument (0, 2, ...) — not attempted
yet, but it is a concrete, falsifiable next check rather than another
guess.

**Hop 5 is the real prize.** The bytes at runtime `0x1441f` and just before
it are a textbook **threaded-code interpreter dispatch**, not ordinary
control flow:

```
14408: mov ax,0x3d01 / mov es,ax
1440d: lodsw ax,[si]                 ; fetch a word from an SI-addressed byte-code stream
1440e: mov es:[0xdc1],al
14414: lodsw ax,[si]                 ; fetch the next word -- the "opcode"
14415: xchg bx,ax
14416: jmp word ptr [bx+0x24f4]      ; INDEX INTO A JUMP TABLE AND DISPATCH
1441a: lcall 0x2708,0x102b           ; <- one opcode's handler is exactly hop 4's call chain
1441f: lodsw ax,[si]                 ; <- returns here, and immediately fetches the NEXT opcode
14420: xchg bx,ax
14421: jmp word ptr [bx+0x24f4]      ; <- and dispatches again, same table
```

`lodsw` from an `SI`-indexed stream, straight into an indirect jump through
one fixed table (`[bx+0x24F4]`), repeated immediately after the called
handler returns rather than looping back through one central dispatch
point — this is the standard shape of **direct-threaded bytecode
execution**, the same technique classic Forth implementations and many
contemporary game "process"/script VMs use to avoid a big `switch`. Under
this reading, `lcall 0x2708,0x102b` (hop 4's target) is not "the game loop
calling the input system" in the ordinary sense — **it is one opcode's
handler in a custom virtual machine**, and the mouse-polling call chain
traced above is what executing *that one instruction* does.

**What this means for "find `main`/the game loop"**: the premise may be
wrong. If a meaningful slice of UW2's per-frame logic runs as bytecode
interpreted by this dispatcher, there may be no single flat "game loop"
function to name — the closest equivalent is this fetch-dispatch step
(runtime `0x14414..0x14421` this boot; convert via this boot's delta to
compare across sessions) plus whatever sets up `SI` to point at the actual
script/program being run. **Not yet done**: identify the jump table itself
(`DS` (or whichever segment `[bx+0x24F4]` actually resolves against —
capstone did not print an override, so it defaults to `DS`) at file offset
`0x24F4` relative to that segment, once the exact segment is confirmed);
enumerate its entries to see how many distinct "opcodes" exist and what
each does; and find what feeds `SI` initially (that answers "where does the
bytecode program live" — plausibly in the level or object data files this
project hasn't decoded yet, which would tie this straight back to the
still-open `LEV.ARK`/`CNV.ARK` format work in `AGENTS.md` item 2).

**A confirmed real-world limit of this technique, recorded rather than
hidden**: breakpointing the dispatch instruction itself (`0x14416`) and
continuing timed out after 30 s on the very first hit — this specific
segment (`CS=0C31`) is real but far less hot than the `CS=2708` render
context (9/150 vs 58/150 in the earlier histogram, `qemu-boot.md`), so it
is plausible this VM only ticks on some slower cadence (input/game-logic
events) rather than every frame, not that the gdbstub is unreliable. QEMU's
own process stayed healthy throughout (verified: a fresh screenshot right
after showed the game running normally, undisturbed) — this reads as "this
breakpoint address is rarer than assumed," not a repeat of UW1's earlier
flakiness.

## 9. The jump table, confirmed two ways, plus an unplanned second discovery

Converting hop 5's runtime address to this project's stable Ghidra
addressing (file offset, independent of any one boot's calibrated delta)
lands squarely in **`CODE_300`, `1e2b:0000..1e2b:046f`** — and its very
first instruction, at block offset 0, is:

```
1e2b:0000  JMP word ptr [BX + 0x24f4]
```

byte-for-byte the same dispatch instruction found dynamically in §8. Two
independent things confirm this is the VM's real jump table, not a
coincidence of address arithmetic:

- **Ghidra's own decompiler recognises it as a switch, unprompted.** One
  function in this block is literally named
  `switchD_1000:4057::caseD_0` — Ghidra's standard naming for a jump-table
  case target — and two *different* indirect-call sites in the same
  neighbourhood (`FUN_1e2b_00b0`, `FUN_1e2b_0289`) both carry the warning
  *"Could not recover jumptable... too many branches"*, decompiling to the
  same shape: `(*(code *)*(undefined2 *)((int)(undefined2 *)&DAT_1224_0174
  + <index>))()`. "Too many branches" from Ghidra's own switch-recovery
  heuristics is consistent with a real VM opcode table (dozens of entries),
  not an ordinary small compiler-generated `switch`.
- **The index sources differ per site**, which is exactly what a shared
  dispatcher reached from multiple contexts should look like:
  `FUN_1e2b_00b0` indexes with `in_BX` directly; `FUN_1e2b_0289` indexes
  with `*(int *)(unaff_SI + 2)` — a word read from *2 bytes into the
  SI-addressed stream*, i.e. still the same "fetch the next stream word,
  use it as an opcode" idiom as §8's raw disassembly, just decompiled from
  a different call site.

**Unplanned second discovery, right next to the first**: `FUN_1e2b_0289`
is not part of the dispatch mechanism itself — it does real, verifiable
file I/O. Raw disassembly (`disasm.txt`, same `CODE_300` block) shows,
in order: **three digits built from a register value** (`SHR AX,CL /
AND AX,0x7 / ADD AL,0x30` — the `+0x30` is the classic byte-to-ASCII-digit
idiom, done three times) written via `STOSB ES:DI` starting at a fixed
buffer offset, then **`MOV AX,0x3D00` / `INT 0x21`** (DOS `Open Existing
File`), then **`MOV CX,0x7FFF` / `MOV AX,0x3F10` / `INT 0x21`** (DOS `Read
File`, up to 32,767 B), then **`MOV AX,0x3E00` / `INT 0x21`** (DOS `Close
File`) — matched in the decompiled C as literal `DosOpenFile()` /
`DosReadFile()` / `DosCloseFile()` calls. A function that builds a filename
from digits derived from a numeric parameter, opens it, reads a large
(~32 KB) buffer, and closes it is a strong shape-match for **loading a
numbered level or save file** — directly relevant to the separate open item
in this project's checklist (§6, "top-level LEV/CNV/STRINGS readers... the
save (SAVE0\lev.ark) machinery"), found by accident while chasing the VM
dispatch rather than by looking for it.

**Not yet resolved, honestly**: the exact literal filename template (the
non-digit characters — prefix, extension) wasn't pinned down. The
digit-writing code loads `DX` with one of two different fixed offsets at
different points (`0xc28b`, then later `0xd04a`) before the actual `INT
21h` open call, and which one is live on the taken path wasn't traced
through. A direct read of that offset's bytes (via the file's initialized
DGROUP data, the same technique that worked for `FUN_1e2b_0289`'s call
chain) gave code bytes, not text — meaning the buffer is addressed via a
segment other than the one assumed (`ES`, not `DS`/DGROUP, based on the
`STOSB ES:DI` in the same routine), and confirming it needs either a live
memory read (`ES:[0xd03a]` on a running session) or more careful static
segment-tracking, not another guess. Also not attempted: enumerating
`DAT_1224_0174`'s table entries to count real opcodes, and finding what
sets `SI` before the dispatch loop starts (the "where does the bytecode
program live" question §8 ended on — this file-loading function is now the
leading candidate for supplying it).

**Attempted (2026-08-21) — did not fire, a real negative result, not a dead
end.** Armed a breakpoint on `FUN_1e2b_0289`'s entry *before* any menu
input, continued, then drove the full character-creation flow through to
the in-game view with the breakpoint riding in the background the whole
time (proved the technique itself works for this: `rsp.cont()` without
blocking, do the QMP-driven navigation, collect the stop reply afterward —
useful pattern for future sessions wanting to catch a rare event without
guessing when). **It never hit.** Confirmed via screenshot that the
character-creation navigation itself worked normally throughout (we were
genuinely in the 3D view, not frozen), so this isn't a harness problem —
**starting a brand-new character does not call this function.** That
argues for the save/load-specific reading over "generic level loader":
whatever puts you in the starting room the first time doesn't need to open
a numbered file, only *loading a save* would.

Also ruled out, cheaply, while already in the game view: the red gem/wing
icon on the control panel is a **movement control** (clicking it turned
the view — a bed and fireplace came into frame — matching classic
Ultima Underworld's click-to-turn/walk interface), not a menu access
point; plain `esc` and `f1` during gameplay do nothing menu-shaped either
(`f1` appeared to ready a weapon/hand instead). **The actual save/load UI
trigger is still unknown** — worth a few more direct guesses (other
function keys, a different UI region, a right-click) next time, but that
is now an open UI-discovery question in its own right, not a small
extension of pinning down `FUN_1e2b_0289`.

## 10. The opcode table, enumerated — ~111 primary entries, a second table close by

Resolving §9's remaining question (which segment `[bx+0x24f4]` uses)
needed one more careful live capture, because the obvious approach —
reading `DS` at the mouse call chain's own functions — is contaminated:
the hop-4/5 wrapper (`ghidra.md` §8) explicitly does `mov ax,0x6bdd / mov
ds,ax` as its *own* prologue, so `DS` measured there reflects the
wrapper's choice (DGROUP), not what the dispatch loop actually had.
Breakpointed the wrapper's *entry* instead (before its prologue runs) —
same non-blocking `cont()` + QMP-navigation pattern as §9's negative
result — and read the true, uncontaminated `DS`:

```
DS = 0x55A3   (cross-checks the very first EIP histogram, which recorded
               "DS=55A3 ES=55A3" as a real, recurring segment combo —
               this is not a one-off reading)
```

Table base = `(0x55A3<<4) + 0x24F4`. Dumped 200 entries (400 B) from
there and resolved each against `functions.txt`:

- **Entries 0–110 (111 opcodes) are a coherent table**: every value is a
  plausible near-jump offset (roughly 1,000–33,000), each pointing
  somewhere in a broad, consistent code region. Only a handful resolve to
  a *named* function boundary — most land in the same kind of unnamed
  gaps §7–§9 already ran into — but **15 of the 111 slots** (indices 0, 4,
  15, 16, 18, 20, 24, 30, 41, 53, 55, 58, 59, 76, 77) all resolve into
  **`FUN_1724_03ec`**, at only two distinct internal offsets (`+0x24` for
  13 of them, `+0x2c`/`+0x2d` for the other 2).
- **`FUN_1724_03ec` is not a stub — read the decompiled body before
  concluding that.** First guess was "shared no-op/unimplemented-opcode
  handler," which is the standard interpretation of many table slots
  converging on one address. The actual decompiled C is real fixed-point
  arithmetic against fixed low-memory state (`*(int*)0x182 * *(int*)0x18c`,
  shifted and split into high/low halves — the classic `(a*b)>>16`
  scaling idiom) with a `while` loop and multiple internal branches, not a
  stub. **Corrected reading**: several opcodes share *entry points into one
  substantive shared math routine* (different offsets select different
  behaviour variants of the same underlying calculation — a real code-reuse
  pattern, not "opcode not implemented"), plausibly perspective/scaling
  math for the renderer given the multiply-shift shape. Left as
  IDENTIFIED, not fully decoded — the exact arithmetic meaning of each
  entry offset needs a dedicated pass this session didn't spend.
- **Entries 111–133 are a run of near-zero values**, clearly not
  jump-table offsets (a table entry can't usefully be `0`, `1`, or `29` as
  a code offset this early in the image) — this is very likely a *small,
  separate data/state array* sitting between two tables in memory, not a
  sparse continuation of the opcode table.
- **Entries 134–167+ look like a second, distinct table**, and resolve to
  *named* functions far more often than the first (`FUN_1bf0_0026`,
  `FUN_1a7e_00b3`, `FUN_1b75_0267`, `FUN_1b24_0190`, `FUN_1aac_0102`,
  `FUN_1c0f_0086`, `FUN_16f8_00b0`, `FUN_1c7e_0020`, `FUN_1c24_00e6`,
  `FUN_199c_03f5`, and `FUN_1c7e_0217` repeated three times running). A
  higher named-function hit rate plus a different repeated-value pattern at
  the tail (`25664` ×3, `25814` ×2+) is consistent with this being a
  **separate opcode set for a different subsystem** (the two-table split
  common in adventure-game VMs — e.g. "world/rendering ops" vs
  "object/conversation ops") rather than a continuation of the first table.

**Not yet done**: decode `FUN_1724_03ec`'s exact math precisely; name more
than the handful of entries that happen to land on already-identified
functions in both tables; confirm the second table's true start/end
boundaries (134 is where the pattern visibly changes, not a boundary read
off any header or count field); and — the original motivating question —
find what feeds `SI` to select *which* script/program this whole
mechanism executes. That last question is the one still connecting this
investigation back to the undecoded level/conversation file formats
(`AGENTS.md` item 2).

## 10b. The threaded-code VM's table, located in the file and enumerated exactly — RESOLVED (2026-08-22)

§10 read this table live, off a running boot, and left it explicitly
unfinished: "*enumerate the table's real opcodes*", with the entry count
given as "**~111**" and the `FUN_1724_03ec` convergence as a spot
observation. All of that is now nailed down statically, and §10's live
numbers hold. `python work/vm2_table.py --verify`.

### The inner interpreter is a textbook NEXT

```
AD            lodsw                    ; ax = [ds:si], si += 2   -- fetch token
93            xchg bx, ax
FF A7 F4 24   jmp word ptr [bx+0x24f4]
```

**101 occurrences** of that exact 6-byte sequence in `UW2.EXE`, and the count
of bare `jmp [bx+0x24f4]` sites is **also 101** — i.e. *every* dispatch in the
binary is a complete NEXT, with no central loop. That is the definition of
threaded code, and it settles §8's "if real, there may be no single flat game
loop function to name": there is none, by construction.

`bx` is **not scaled** before the jump, so a token is a *byte* offset — the
script stream stores `opcode * 2`.

### Locating the table needed exactly one live number

The table is at `DS:0x24F4` and `DS` is a private segment, so the file offset
cannot be derived from the file alone. Combining §10's live `DS = 0x55A3` with
the boot delta `0x2F50` that `qemu-boot.md` records for that same run:

```
table file offset = (0x55A3 << 4) + 0x24F4 − 0x2F50 = 0x54FD4
```

A blind *pattern* search failed first — sliding a 111×`u16` window over the
whole image and keeping those spanning less than the handler region left 955
candidates, none putting 25+ entries on a handler boundary.

✗ **Withdrawn within the same session** (the claim was committed and is
corrected here): "*this table is not findable without one live-calibrated
number*". It is. §10c below finds the segment numbers in the file itself, and
plain MZ arithmetic then gives both addresses with no live input:

```
file = 0x2E00 + (segment << 4) + offset        (0x2E00 = e_cparhdr*16)
   handlers  0x065C:0000   -> 0x93C0      (= the fitted code base, exactly)
   table     0x4FCE:0x24F4 -> 0x54FD4     (= the live-derived offset, exactly)
```

The live route above still stands as an independent cross-check — it is just
not required.

### Everything after that is static and self-checking

| invariant | result |
|---|---|
| slot 111 (one past the end) is `0`, out of range | → the table is **exactly 111 slots**, not "~111" |
| `code_base + max(entry)` == the end of the handler region | `0x114D5` == `0x114D5` ✓ |
| best code base over `0x2E00..0x12000` | `0x93C0`, **unique** maximum, 63/111 vs runner-up 21 |
| every distinct target disassembles | **94/94** |
| implied runtime segment `(0x93C0 + 0x2F50) >> 4` | **`0x0C31`** |

That last row is the one that matters: §7/§9 recorded "*another unnamed
address, runtime `0x1441f`, **in segment `0C31`***" from a live gdbstub trace,
months before and by a completely different route. A fitted static base
reproducing the segment number a live trace saw is not a coincidence.

### The table

**111 slots, 94 distinct targets**, handlers occupying file
`0x999D..0x114D5` (segment offsets `0x05DD..0x8115`). 63 of the 111 land
exactly on a handler entry (the byte after a NEXT); the rest are **alternate
entry points into a handler** — e.g. `0xA459` is `0xA458 + 1`, entering one
byte past a `ret`.

§10's spot observations reproduce exactly:

- the most-shared target, file `0xA450`, is used by **13** slots — §10
  measured "13 of them" sharing `FUN_1724_03ec + 0x24` (Ghidra flat
  `0x17650`, and `FUN_1724_03ec` starts at `0x1762C`: `+0x24` ✓).
- entry values run `1180..33045`, matching §10's "roughly 1,000–33,000".

Targets disassemble as threaded-code handler prologues — `lodsw / mov di,ax`,
`lodsw / mov bx,ax / mov bx,[bx]`, `lodsw / mov cx,ax / lodsw` — i.e. each
primitive fetches its own inline operands from the same stream. `--list`
prints all 111 with two instructions of disassembly each.

### Still open

What the 101 primitives *do* (only the shape of each prologue is read here),
and the question §8 ended on and §10 repeated: **what feeds `SI`** — where the
threaded token stream comes from. Nothing in this section answers that; it
makes it cheaper to attack by giving the handler set and the table.

## 10c. What feeds `SI` — the entry path, found statically — RESOLVED (2026-08-22)

§8 ended on "*find what feeds `SI`*" and §10 repeated it as the question
"*still connecting this investigation back to the undecoded file formats*".
Answered here, without the oracle.

### The segment numbers are in the file

The far-call and far-jump operands carry the *pre-relocation* segment word, so
they can be read straight out of the image. `0x0C31` was the runtime segment
§9 saw; this boot's load segment is `L = (delta + 0x2E00) >> 4 = 0x5D5`
(the same formula gives `0x597` for the other boot, which `qemu-boot.md`
records as measured — so the formula is checked), hence static segment
`0x0C31 − 0x5D5 = 0x065C`.

Searching for far transfers with that segment word finds **exactly five**:
three `CALL FAR` — to **three different offsets**, `0x3007`, `0x7F0C` and
`0x7F12` — and two `JMP FAR` inside the segment itself. *(Corrected: an
earlier draft of this section said "three `CALL FAR 0x065C:0x7F0C`". Only the
one from the wrapper below targets `0x7F0C`.)*

### One wrapper, and `SI` is simply its third argument

All three calls go through `FUN@0x250B3` (= `0x2133:0x0F83`):

```
push bp / mov bp,sp / push di,si,ds,es
save SS:SP into cs:[0xc24], cs:[0xc26]
bp = arg1        si = arg3          <-- the token-stream pointer
ax = arg2        ds = arg4          <-- the VM's data segment
bl = arg5
ds = es = 0x60d8 ;  cli / ss = 0x60d8 / sp = 0x510 / sti   <- private VM stack
ds = arg4
lcall 0x065C:0x7F0C
… restore SS:SP, pop, return in DX:AX
```

So the interpreter does not find its stream — **it is handed one.** `SI` is an
ordinary C argument.

### All three call sites compute it the same way

```
al = es:[bx+3] ; ah = 0 ; shl ax,4 ; add ax,0x6732   ; -> arg3 = SI
push ds                                              ; -> arg4 = the VM's DS
al = es:[bx]   ; (compared against 4 just above)     ; -> arg5
```

**`SI = 0x6732 + 16 × record[3]`** — an index into an array of **16-byte**
entries at offset `0x6732` of the caller's data segment, selected by one byte
of a four-byte record whose byte 0 is first tested against `4`.

### Which data segment — the file settles §10's live reading

`0x4FCE` appears as a literal `mov ax,0x4fce` eight times inside the handler
region, and **that immediate is in the relocation table**, so at load it
becomes `0x4FCE + L`. With this boot's `L = 0x5D5` that is **`0x55A3`** —
exactly the `DS` §10 measured live. A live register reading reproduced by pure
file arithmetic; no oracle needed to know the VM's data segment.

✗ **Withdrawn** (§10d): the inference that therefore `DS = 0x4FCE` *on every
path into the segment*, and hence that the streams live at file `0x59212`. The
oracle says otherwise — see below.

### The contents at that address are NOT token streams — a real negative

Pursued properly and it does not hold up. `python work/vm2_table.py
--operands` derives each handler's inline-operand count by walking **every**
path from its entry to a terminating NEXT (the first attempt only counted
straight-line `lodsw` and gave up at the first branch, covering 43 of 111):

| | |
|---|---|
| fixed-width handlers | **83 / 111** — counts 0–10, most commonly 0 (25) and 3 (20) |
| variable-width | 24 — `lodsw` inside a loop, so the width is a runtime value |
| paths reaching `ret` (they leave the VM) | 4 — slots **0, 60, 66, 109**, the natural program terminators |

With 83 widths known, walking the 16-byte entries at file `0x59212` should
mostly succeed. It does not: over 128 consecutive entries, **59 hit an invalid
token** (odd, or beyond the 111-slot table), 26 stop at a variable-width
handler, 22 reach a terminator and 21 run off the end. A real token stream
would not produce a 46% immediate-invalid rate.

The first few entries do look regular — `(0x00C8, 0x0086, 0x0070, −6)`,
`(0x00D0, 0x0086, 0x0078, −41)`, … with words 0 and 2 stepping by 8 and word 1
pinned at `0x86` — but that regularity breaks down within about eight records,
so it is not an alternative structure either, just a locally ordered run.

**The segment is not the problem.** Handlers do reload `DS` (142 sites), but
**101 of those are `pop ds`** against 101 handlers — they push and restore
around their bodies, so `DS` at every NEXT equals `DS` at entry, and the
dispatch-time `0x4FCE` really is the entry value. The address is right; the
*bytes* are wrong.

The reading that survives is that **the streams are built at runtime**, not
shipped in the image — consistent with the caller's shape (a four-byte record
from `ES:BX`, type-tested against `4`, indexing 16-byte slots), which is what
a load-time compile step into a fixed array would look like.

So this is where static analysis stops, and the live read is now a precise
one-shot rather than a fishing trip: **breakpoint `0x065C:0x7F0C`, capture
`DS:SI` and the four bytes at the caller's `ES:BX`**, and compare the memory
against file `0x59212 + 16 × index`. If they differ, the array is
runtime-built and the question becomes what writes it.

## 10d. The oracle run — the SI formula holds, the interpretation does not — 2026-08-22

One breakpoint, and it corrects three things §10c asserted. Tool:
`work/rsp_break.py --at 0x112CC` (the RSP client §8 described and never
committed, now kept).

### What the hit measured

Breakpoint on `0x065C:0x7F0C` = file `0x112CC`, hit during the intro:

```
CS = 0C31  EIP = 7F0C        DS = 6BDD  SI = 68A2
ES = 66AD  BX = 000A         SS = 66AD  SP = 050C
```

**Confirmed:**

- `CS = 0x0C31` at `EIP = 0x7F0C` — the static segment `0x065C` plus this
  boot's `L = 0x5D5`, exactly as §10c predicted. The whole static address
  model for this segment is validated on real silicon.
- **`SI = 0x68A2` = `0x6732 + 16 × 23`.** The formula read off the three call
  sites is right, live, with index 23.
- The 16-byte entries **are built at runtime**: the file at that address is
  all zeros, the guest has real data. §10c's surviving hypothesis, confirmed.
- The caller's `ES:BX` record matches the file byte-for-byte — that part *is*
  initialised data.

**Refuted:**

- `DS` at entry is **`0x6BDD` = DGROUP**, not `0x4FCE`. `0x4FCE` is loaded by
  the *other* door (`0x065C:0x7F12` starts `mov bx,ds / mov ax,0x4fce /
  mov ds,ax`), so the segment depends on which entry was used, and §10c's
  "`DS = 0x4FCE` throughout" was wrong.
- **`0x065C:0x7F0C` is not an interpreter entry at all.** It is two
  instructions — `call word ptr cs:[bx+0x6d30]` / `retf` — a trampoline
  dispatching on `BX`, which is the wrapper's fifth argument, i.e. the record
  byte tested against `4`.
- The data at `DS:SI` is **not a token stream**. It is byte lists —
  `00 01 98 99 9a 9b 9c 9d 9e a0 a1 c1 d0 00 00 00` — 16 bytes, ascending,
  zero-padded. §10c already showed the token walk failing; this is the direct
  evidence for why.

### What `SI` actually feeds: a nibble→byte translation table

With the live `BX = 0x0A`, the trampoline resolves statically to
`cs:[0x6D30+0x0A] = 0x0039` → file `0x93F9`:

```
mov cx,1 / call 0x9423        ; 0x9423: es = 0x065C, di = 0, shl cx,4,
                              ;         rep movsb  <- copies 16 B from DS:SI
                              ;         to 0x065C:0000
mov si,bp
mov dx,0x43bf / mov es,dx / mov di,0
lodsw -> cx                   ; a length
lodsb -> al                   ; one packed byte
al & 0xF0, shr 4, xlatb, stosb    ; high nibble -> translate -> emit
al & 0x0F,        xlatb, stosb    ; low  nibble -> translate -> emit
loop
```

`xlatb` reads `DS:BX + AL`, and the table it reads is the 16 bytes just copied
to `0x065C:0000`. So **`SI` points at a 16-entry nibble→byte translation
table**, and the routine is a **4bpp→8bpp expander** writing to segment
`0x43bf` (relocated: runtime `0x4994`). That explains every property of the
data at once — the 16-byte stride, the byte-sized ascending values, the
zero padding, and why it is built at runtime rather than shipped.

**What those tables are — RESOLVED (2026-08-22).** They are the game's
**auxiliary palettes**, and they come from a file. `FUN@0x8BC38` (`gfx_init`)
opens `data/allpals.dat` and reads its first `0x200` bytes straight to
`DGROUP:0x6732` — the exact base this door indexes. `ALLPALS.DAT` is **513 B =
32 × 16 + 1**, i.e. **32 palettes of 16 entries**.

The confirmation is exact: the 16 bytes captured live at `DS:SI` in §10d were
`00 01 98 99 9a 9b 9c 9d 9e a0 a1 c1 d0 00 00 00`, at `SI = 0x68A2 =
0x6732 + 16 × 23`. Those bytes occur in `ALLPALS.DAT` at offset **368 = 16 ×
23** — the same index, byte for byte. So `SI = 0x6732 + 16 × index` selects
auxiliary palette `index`, and "built at runtime" means "read from
`ALLPALS.DAT` at startup".

### The honest consequence for the "second VM"

The 111-slot table and the 101 NEXT sites are measurements and stand. The
*label* "VM" is downgraded to IDENTIFIED: §§8/10 reached "threaded-code
interpreter" from a live trace of the *mouse* path, which runs with
`DS = 0x55A3`, a different context from the one measured here, so that reading
is not contradicted — but it is not safe to name the segment from one door.
§10e characterises it properly.

Two NEXT sites were also breakpointed directly and **neither executed**:
file `0x999D`, and file `0x114CF` — which is §8's own hop-5 address
(runtime `0x1441f`) — each given 100–120 s of boot and main menu. Clean
negatives. §8 reached that code only after driving through character creation
into the 3D view, so most of the 101 handlers are simply cold until gameplay.

## 10e. What segment `0x065C` actually is: fixed-point math, not blitting — 2026-08-22

§10d guessed "graphics/decoder library" from a single handler. Measuring all
101 says something sharper, and it is a correction: ✗ the "decoder library"
label was drawn from one door and is too narrow.

Disassembling every handler body (from each NEXT+6 to the next NEXT) gives
**12,458 instructions across 100 bodies**, profiled against a same-sized slab
of ordinary game code as a control:

| | segment `0x065C` | control (file `0x30000..0x40000`) |
|---|---|---|
| instructions | 12,458 | 27,523 |
| `mul` / `imul` / `div` / `idiv` | **5.0 %** | 0.9 % |
| `shl` / `shr` / `sar` | 3.3 % | 2.0 % |

A **5.5× enrichment in multiply/divide** is not what a blitter looks like.
Two more measurements pin it down:

- **272 sites** where a `mul`/`imul` is immediately followed by a move of
  `DX` — taking the *high* word of a 32-bit product, i.e. the `(a*b)>>16`
  fixed-point idiom. That is exactly what §10 found in `FUN_1724_03ec`, the
  routine 13 table slots share; there are 272 more of them.
- **No framebuffer access at all**: `mov ax,0xa000` occurs 6 times in the
  binary and **0 times** inside this segment. It computes; something else
  draws.

String/blit work is a minority: 22 of 100 handlers use `stos`/`movs`/`rep`,
and exactly **one** uses `xlatb` — the nibble expander §10d happened to land
on. Texture unpacking is a primitive *inside* this engine, not its purpose.

**Reading** (inference, clearly labelled): segment `0x065C` is a **fixed-point
arithmetic engine driven by a threaded command stream**, with a few decode
primitives. §10's read of `FUN_1724_03ec` as "plausibly perspective/scaling
math" is corroborated by 272 more instances of the same idiom.

✗ **Correction, made the same day the claim was written.** The paragraph above
originally also cited §7's live EIP histogram — "a private-segment context
dominating 39 % of samples, shaped like the raycaster's inner loop" — as a
third agreeing route. **It is not the same segment.** §7 recorded that context
as `CS=2708`, and `0x2708 − L` = static **`0x2133`**, whereas this segment is
static `0x065C` (runtime `0x0C31`). Two routes agree here, not three.

### What the histogram segments actually are — a corrected map

Converting §7's live segment tallies back through `static = runtime − L`
(`L = 0x5D5`) puts the pieces in order for the first time:

| §7 live | static | what |
|---|---|---|
| `CS=2708`, `DS=ES=SS=66AD` — **39 % of in-game samples** | `0x2133`, data `0x60D8` | the hot inner loop. `0x2133` is the segment holding the wrapper `FUN@0x250B3` (= `0x2133:0x0F83`), and `0x60D8` is precisely the private segment that wrapper installs (`mov dx,0x60d8 / mov ds,dx / mov es,dx / mov ss,dx`) |
| `CS=065A`, `ES=A000` — 11/150 | `0x0085` | the video blitter (the startup code far-calls `0x85:0x6e2` and `0x85:0x18`) |
| §8 hop 5, runtime `0x1441f` | `0x065C` | this segment — reached *from* the above, not itself hot |

So the shape is: **a hot loop in `0x2133` running in the `0x60D8` private
world, calling down into `0x065C` for arithmetic and decode primitives, with
`0x0085` doing the actual framebuffer writes** — which fits `0x065C` having no
`0xA000` reference of its own. Stated as the reading the addresses support,
not as proven control flow.

### The `0x7F0C` door is a 6-entry API

`call word ptr cs:[bx+0x6d30]` indexes with `BX` as a *byte* offset, so the
doors are `BX = 0, 2, 4, 6, 8, 0x0A`:

| BX | target | body |
|---|---|---|
| `0x00` | `0x6D3C` | `int3 / ret` — stub |
| `0x02` | `0x018B` | `ret` — no-op |
| `0x04` | `0x0020` | `call 0x948b / mov si,bp / mov dx,0x43bf / mov es,dx` |
| `0x06` | `0x011C` | `mov cx,2 / call 0x9423 / …` |
| `0x08` | `0x00D9` | `mov cx,1 / call 0x9423 / …` |
| `0x0A` | `0x0039` | `mov cx,1 / call 0x9423 / …` — the one the oracle caught |

Entry 6 (`0xC3CC`) points outside the segment and the words after it
(`0x0100, 0x0302, 0x0504, 0x0708…`) are an obvious ascending data run, so the
table ends at six. Four real doors, all the same shape — **pixel-format
decoder variants** differing in the translation-table size (`cx`) and which
preloader they call. This door is the *decode* face of the segment; the 101
threaded handlers are reached another way.

**Still not established**: what any individual threaded primitive computes,
and what the command stream looks like in the renderer context (the one stream
captured live came in by this decode door and was a texture palette, not a
command list). Settling that needs the game driven into the 3D view with the
breakpoint riding — the §9 pattern, and the documented character-creation
click sequence in `qemu-boot.md` — which this session did not do.

## 10f. Driven into gameplay — the stream decodes, and my rejection of it was wrong — RESOLVED (2026-08-22)

§§10c–10e rejected the token-stream reading twice. Both rejections were
wrong, for two separate reasons, and driving the game into the 3D view settles
it. `work/drive.py` (new) reproduces the navigation; `work/rsp_break.py
--attach` then breakpoints the running session.

### Getting there

`qemu-boot.md` mapped the character-creation flow but recorded no
coordinates. Reproduced here and now scripted: relative `mouse_move` units map
**1:1 relative units to screenshot pixels** in the 640×400 dump, so buttons can
be aimed at by measuring a screenshot. Absolute driver limits and the
consumer's coordinate conversion are separate contracts. One thing that had to be found the hard way —
`mouse_button 1` / `mouse_button 0` with a **0.25 s** hold registers *nothing*;
UW2 samples `INT 33h AX=3` rarely enough that the press must be held
**~1.5 s**. `drive.py` holds 1.5 s by default.

Full run: main menu → Create Character → Male → Right → Tinker → Axe →
Search → portrait → Standard → name → Keep → **the 3D starting room**.

### The breakpoint, in gameplay

Breakpoint on the NEXT at file `0x114CF` — §8's own hop-5 address, which had
*not* fired at the menu (§10d):

```
CS = 0C31  EIP = 810F        DS = 55A3  SI = 8D00
ES = 55A3  BX = 01EB         SS = 66AD  SP = 050A
```

**`DS:0x24F4` in guest RAM is byte-for-byte identical to file `0x54FD4`.**

```
guest: 98 10 d6 13 e0 13 6e 19 99 10 ef 13 b6 19 f3 19 30 1a f6 18 1a 19 07 19
file : 98 10 d6 13 e0 13 6e 19 99 10 ef 13 b6 19 f3 19 30 1a f6 18 1a 19 07 19
```

The 111-slot table enumerated statically in §10b is confirmed in memory. And
`DS = 0x55A3` = static `0x4FCE + L`, exactly as §10 measured and §10c derived.

### Two errors, both mine

1. **Wrong door.** §10c/§10d measured at `0x065C:0x7F0C`, which §10d then
   showed is the *texture-decode* trampoline, entered with `DS` = DGROUP. That
   path's `DS:SI` really is a palette, not code. The threaded engine runs on
   the *other* path, with `DS = 0x55A3` — reachable only in gameplay, which is
   why every menu-time breakpoint missed it.
2. **Wrong operand model.** The walk counted `lodsw` and multiplied by two.
   The stream is **byte-granular**: handlers use `lodsb` as well, `movsb`/
   `movsw` also consume, and a handler can consume *through a subroutine it
   calls*. Slot 91 is the worked example — `call 0xc8b2` (which itself takes
   3 bytes) then `lodsb`, so **4 operand bytes**, not the 0 the old counter
   reported.

### The captured stream decodes

64 bytes read live from `DS:SI`, walked with statically derived byte widths:

```
  +0   token 0x0b6  slot  91  handler 0xA89D   4 operand bytes: f8 28 18 c8
  +6   token 0x0b6  slot  91  handler 0xA89D   4 operand bytes: 00 28 18 c9
  +12  token 0x0b6  slot  91  handler 0xA89D   4 operand bytes: 00 20 18 ca
  +18  token 0x0b6  slot  91  handler 0xA89D   4 operand bytes: f8 20 18 cb
  +24  token 0x03e  slot  31  handler 0x110FE  4 operand bytes: 05 00 05 00
  +30  token 0x002  slot   1  handler 0xA796   4 operand bytes: 2c c8 ff 0f
  +36  token 0x036  slot  27  handler 0xD282   width is runtime-determined
```

Six instructions, 36 of the 62 captured bytes, and the walk stops exactly
where it *should* — on a handler whose width genuinely depends on a runtime
value (widths 14, 16, 18, 20, …), not on an invalid token. Four consecutive
slot-91 instructions whose operands differ regularly, and whose handler writes
an 8-byte-strided record at `[di+0x14d0]`/`[+0x14d2]`/`[+0x14d4]`, is exactly
the shape of a display list.

### Status restored

**§§8/10's "threaded-code interpreter" reading is correct**, and §10d's
downgrade of the "VM" label is withdrawn — it was drawn from the decode door
and a broken operand counter. Segment `0x065C` hosts *both*: a threaded
bytecode engine (111 slots, 101 handlers, byte-granular operands) reached with
`DS = 0x55A3`, and a small texture-decode API reached at `0x7F0C` with the
caller's `DS`. §10e's instruction census stands unchanged and now reads
naturally — a fixed-point engine executing a display list.

Re-derived with the corrected counter: **67 of 111** handlers have a fixed
byte width (0, 2, 4, 6, 8, 9, 10, 11, 14 — note the odd values, which is the
byte-granularity showing), 12 are loops, and 32 have paths that leave the VM.

**Still open**: what each primitive computes. The mechanism is now fully
decoded — table, handlers, widths, stream — so that is a naming exercise
against a live stream, not a structural unknown.

## 11. The conversation VM — a second, separate bytecode engine — RESOLVED (2026-08-22)

§§8–10 found a threaded-code interpreter dispatching through
`DAT_1224_0174` with ~111 entries, and ended on "is the conversation script
the same VM or a different one?". **Different.** UW2 runs two bytecode
engines; this section resolves the conversation one end to end. The data side
(`CNV.ARK`'s container, LZSS layer and record layout) is in
`analysis/data-formats.md`; this is the interpreter.

### The interpreter

`FUN@0x75A95`, in the overlay whose **segment base is `0x745A0`** (the same
overlay as the conversation loader `0x74E15`, the record parser `0x75863` and
the builtin-register routine `0x765E6`).

```
[0x471a] = IP, in words          [0x46fa] = stack index (SP)
[0x471e] = code array (far)      [0x46fc] = stack base (far)
[0x470e] = imported-function pointer array
[0x4726] = saved SP (frame ptr)  [0x4714] = memory size in words

entry:  if code[0] != 0x22 -> return -1
loop:   bx = code[IP]
        if bx > 0x29 -> halt
        jmp word ptr cs:[bx*2 + 0x187b]
```

**42 opcodes** (`0x00..0x29`), dispatched through a jump table at
**file `0x75E1B`** (= segment base + `0x187B`).

### Locating the table without a load-time base

`cs:[...]` needs the segment base, which is not in the file. Solved by
search rather than assumption: for every candidate base, read 42 `u16`s and
require *all* 42 targets to land inside the interpreter's own span. **Exactly
one base survives** — `0x745A0`, table at `0x75E1B` — and its entry 0 is
`0x75AE6`, the instruction immediately following the dispatch `jmp`, which is
what opcode 0 must be. That is the same technique §10 used for the *other*
VM's table, but here it converges to a unique answer instead of a fitted one.

### All 42 opcodes — RESOLVED (2026-08-22)

Every handler was read; the delegating ones are followed into their helper.
Binary ops take `a = stack[SP-1]`, `b = stack[SP]`, pop one, leave the result
on top. Helper address in brackets.

| op | mnemonic | w | behaviour |
|---|---|---|---|
| `0x00` | `nop` | 1 | advances IP only `[0x75AE6]` |
| `0x01` | `add` | 1 | `a + b` `[0x75E6F]` |
| `0x02` | `mul` | 1 | `a * b`, signed `imul` `[0x75ECC]` |
| `0x03` | `sub` | 1 | `a - b` `[0x75F05]` |
| `0x04` | `div` | 1 | `a / b`; **`0x7FFF` if `b == 0`** `[0x75F3E]` |
| `0x05` | `mod` | 1 | `a % b`; `0x7FFF` if `b == 0` `[0x75F8E]` |
| `0x06` | `or` | 1 | `(a != 0 \|\| b != 0)` `[0x75FDE]` |
| `0x07` | `and` | 1 | `(a != 0 && b != 0)` `[0x76023]` |
| `0x08` | `not` | 1 | `top = (top == 0)`, via the `neg`/`sbb`/`inc` idiom `[0x75B7C]` |
| `0x09`–`0x0E` | `gt` `ge` `lt` `le` `eq` `ne` | 1 | `a ? b` → 1/0 `[0x76068, 0x760AA, 0x760EC, 0x7612E, 0x76170, 0x761B2]` |
| `0x0F` | `jmp` | 2 | `IP = operand` (absolute, in words) |
| `0x10` | `beq` | 2 | pop; if `== 0` then `IP += 1 + operand` |
| `0x11` | `bne` | 2 | pop; if `!= 0` then `IP += 1 + operand` |
| `0x12` | `bra` | 2 | `IP += 1 + operand` |
| `0x13` | `call` | 2 | push `IP+2`; `IP = operand` `[0x761F4]` |
| `0x14` | `calli` | 2 | far-call `[0x470e] + operand*4`; **result → `[0x4708]`** `[0x762E4]` |
| `0x15` | `ret` | 1 | `IP = pop`; an empty stack halts the VM `[0x76222]` |
| `0x16` | `pushi` | 2 | push the literal operand |
| `0x17` | `pusha` | 2 | push `[0x4714] + operand + [0x4726]` (frame-relative address) |
| `0x18` | `drop` | 1 | `SP -= 1` |
| `0x19` | `swap` | 1 | exchange the top two slots |
| `0x1A` / `0x1B` | `pushbp` / `popbp` | 1 | push / pop `[0x4726]` |
| `0x1C` / `0x1D` | `setbp` / `setsp` | 1 | `[0x4726] = SP` / `SP = [0x4726]` |
| `0x1E` | `alloc` | 1 | `SP += top - 1`; with the preceding `pushi N` this reserves N slots |
| `0x1F` | `fetch` | 1 | `top = memory[top]`, memory = `[0x4704]` `[0x7624A]` |
| `0x20` | `store` | 1 | `memory[a] = b`; `SP -= 2` `[0x762B1]` |
| `0x21` | `addm1` | 1 | `a + b - 1` `[0x76277]` |
| `0x22` | `start` | 1 | `IP += 1`; required as `code[0]` |
| `0x23` / `0x24` | `setres` / `getres` | 1 | `[0x4708] = top` (SP unchanged) / push `[0x4708]` |
| `0x25` | `streq` | 1 | pop two string ids, load+expand both, push `strcmp == 0` `[0x76361]` |
| `0x26` | `halt` | 1 | clears the run flag |
| `0x27` | `say` | 1 | load string id, `@`-expand, call the builtin named **`say`** `[0x76442]` |
| `0x28` | `respond` | 1 | same, builtin **`respond`** `[0x764EA]` |
| `0x29` | `neg` | 1 | `top = -top` `[0x75EA8]` |

Three things worth calling out:

- **`[0x4708]` is the result register.** The `calli` helper's last act before
  advancing IP is `mov [0x4708], ax`, and `getres`/`setres` are the VM's only
  other users of it — that is the builtin-call return convention.
- **Strings never appear in the bytecode.** `say`/`respond`/`streq` take a
  **`STRINGS.PAK` string id**, fetch the text with the game's string loader
  (`lcall 0x148:0x97` — the same call the conversation loader makes with
  `0xE01` on failure), then run it through the `@`-substitution expander at
  `0x754F6` (`strchr(s,'@')`; unchanged text is returned as-is and not freed).
  So the CNV → STRINGS link is not just the header's block id: it is how every
  spoken line is emitted.
- **`say` and `respond` are dispatched by name, not by slot.** Both walk the
  32-byte import table comparing against the DGROUP literals `"say"`
  (`0x0BE2`) and `"respond"` (`0x0BE6`) and then call through
  `[0x470e][entry[+0x1A]*4]` — the same array `calli` uses.

*(Refines the previous commit's naming: `enter`/`leave` are recorded above as
`setbp`/`setsp`, which is what the handlers actually do — they do not push or
pop, that is `pushbp`/`popbp`.)*

### Decoded output reads as compiled code

`python work/cnv_disasm.py --slot 2`:

```
  0  start
  1  pushbp        \
  2  setbp          |  function prologue
  3  pushi 0x0000   |
  5  alloc         /
  6  pushi 0x0020  \
  8  pushi 0x0000   |  memory[0x20] = 0
 10  store         /
 11  call 0x074a
 13  call 0x0012
 15  setsp         \
 16  popbp          |  epilogue
 17  ret           /
```

A textbook frame — which is the qualitative check that the naming above is
right, on top of the quantitative ones below.

### Verified against the shipped bytecode — 102/102 each

| check | result |
|---|---|
| `code[0] == 0x22`, the interpreter's own entry condition | 102/102 |
| linear sweep with the operand widths above lands **exactly** on `code_words`, never hitting an opcode > `0x29` | 102/102 |
| every `calli` operand resolves to a function import declared in that same record | **3,485 / 3,485** |

179,694 instructions decode across the 102 conversations. Only four opcodes
(`0x00`, `0x11`, `0x25`, `0x28`) are never used by any shipped script.

The `calli` row is the one that closes the circle: the bytecode's call
operand is the import table's slot number, which is where `FUN@0x765E6`
stores the builtin's far pointer, which is what the 51 registration sites at
`0x7C39B` supply. Four separately-derived things — EXE registration table,
import table in the file, the register routine's `index*4` store, and the
bytecode's operands — all agree.

Most-called builtins across the corpus: `babl_menu` (1,233), `x_clock` (359),
`print` (359), `babl_hack` (318), `get_quest` (291), `set_quest` (127).

Tool: `python work/cnv_disasm.py [--opcodes] [--slot N]`.

## 12. Symbol table — the semantic pass, seeded — PARTIALLY RESOLVED (2026-08-22)

§6's "semantic pass 1 (UW1-style renames)" box. Not closed, but no longer
starting from nothing: `python work/symbols.py --emit` writes
`work/ghidra_export/symbols.txt`, **addresses as file offsets**, in two tiers
that are deliberately not mixed.

### Tier 1 — 17 names, each read from the code and verified

| file | name | how it was established |
|---|---|---|
| `0x011520` | `c0_startup` | MZ `e_cs:e_ip` resolves here |
| `0x074E15` | `conv_load` | mallocs `0x5000`, reads archive 2 record `[0xc66]`, calls the parser |
| `0x075863` | `conv_parse` | decodes the record header field-by-field — it *is* the layout |
| `0x075A95` | `conv_vm_run` | 42-opcode stack VM; refuses to run unless `code[0]==0x22` |
| `0x075E1B` | `conv_vm_table` | 42 jump-table slots |
| `0x0765E6` | `conv_register_builtin` | walks the 32-byte import table, `strcmp`, stores at `[0x470e]+idx*4` |
| `0x07C38C` | `conv_init` | opens `DATA\cnv.ark`, then the 51 registration sites |
| `0x0754F6` | `conv_expand_at` | `strchr(s,'@')` expander behind `say`/`respond`/`streq` |
| `0x0093C0` | `vm2_code_base` | segment `0x065C:0000`; unique best fit for the dispatch table |
| `0x054FD4` | `vm2_dispatch_table` | 111 slots; byte-identical in guest RAM (§10f) |
| `0x0250B3` | `vm2_enter` | sets `SI`=arg3, `DS`=arg4, private stack, far-calls the engine |
| `0x0112CC` | `vm2_decode_trampoline` | `call cs:[bx+0x6d30] / retf` |
| `0x0100F0` | `vm2_decode_table` | the 6 doors |
| `0x0093F9` | `vm2_expand_4bpp` | `lodsb / and 0xF0 / shr 4 / xlatb / stosb` |
| `0x009423` | `vm2_load_xlat_table` | `rep movsb` of the 16-byte xlat table to `0x065C:0000` |
| `0x0811FC` | `cuts_build_filename` | `CUTS\csXXX.nXX` + 3-bit digit groups (octal) |
| `0x089179` | `uwhome_env_lookup` | walks `environ` at `[0x2042]` for `"UWHOME"`, scans for `'='` |

The last one is new here and bears on §6's other open box: it is `getenv`
against the game's home-directory variable, and the same function references
`uw.cfg` and `\SAVE0\` — the entry point to the save machinery.

### Tier 2 — 224 functions annotated by the strings they reference, and nothing more

A reference is a fact; the *name* it suggests is not, so these are emitted as
comments for a human to promote, never as names. Coverage is **224 of 2,239
functions (10 %)**, 405 (function, string) pairs. Attribution is
nearest-preceding-function-start, because `functions.txt` gives instruction
counts rather than byte extents — good enough to read, not good enough to
apply blind.

Low coverage is the honest headline: **90 % of functions reference no DGROUP
string at all**, so this technique alone cannot carry a semantic pass. What it
does do is surface the file-touching and table-driven code, which is where the
leverage is. The richest hits validate it — `0x07C38C` (`DATA\cnv.ark`,
`babl_menu`, `babl_fmenu`, `say`) and `0x074E15` (`compare`, `random`,
`plural`) are the two conversation functions already named independently, and
`0x07DD53`/`0x07E42F` (`npc_whoami`, `npc_hunger`, `npc_goal`, `npc_gtarg`)
are the *variable* side of the import table, which nothing had located before.

Other leads it turned up, unverified: `0x071ECA` (`cnv.ark`, `test.ark`,
`byt.ark`, `scd.ark` — the archive-name table user), `0x08BC38`
(`data/allpals.dat`, `question`, `views`, `objects`), `0x07A600` (`Str:`,
`Dex:`, `Int:`, `Vit:`), `0x09C957` (`trap`, `poison trap`).

## 13. A call graph from raw bytes — 363 of Ghidra's orphans recovered (2026-08-22)

§12 seeded names but noted the real problem: 90 % of functions reference no
string, so string xrefs cannot carry the pass. The other lever is the call
graph — once one function is named, its callers are the next things worth
reading. Ghidra cannot supply it: it reports **`inrefs=0` for 1,044 of 2,239
functions**, losing the trail at every computed call and every crossing into
the overlay pool.

`python work/callgraph.py` rebuilds it arithmetically from the file:

```
9A off seg   far call  -> file = 0x2E00 + (seg << 4) + off
E8 rel16     near call -> file = site + 3 + rel
```

(near calls cannot leave their segment and blocks are contiguous in the file,
so file-space arithmetic is valid for them).

| | |
|---|---|
| call-opcode candidates scanned | 10,529 |
| edges landing exactly on a known function start | 3,014 |
| distinct callees | 1,135 |
| **Ghidra `inrefs=0` that are reachable here** | **363** |

### It is a candidate graph, and here is its noise floor

A byte scan cannot distinguish an opcode from data that happens to be `0x9A`
or `0xE8`. The filter that makes it usable is requiring the target to land
*exactly* on a known function start. Expected chance hits:
`10,529 × 2,239 / 675,968 ≈ 35` of 3,014 edges — **about 1.2 %**. Stated so
that anyone using an edge knows roughly what it is worth; a single edge is
evidence, not proof.

Two blind spots, both structural: calls through Borland's `INT 3Fh` overlay
thunks (the thunk's target has no fixed file address) and computed/indirect
calls. `conv_load` and `conv_vm_run` show **zero** raw callers for exactly
that reason — they are reached through thunks.

### Validated against a function read by hand

`--callees 0x74e15` (`conv_load`, disassembled instruction by instruction in
§10c/§11 work) returns `0x745a0`, `0x74626`, `0x747be`, `0x74ce4`, `0x75863`,
`0x75a51`, `0x765e6`, `0x7675f` — **all eight match the hand disassembly, with
nothing spurious**. And `--callers 0x75863` returns exactly `0x74e15`, which
is what the code shows.

### Two names fell straight out

The graph immediately identified the two most-called helpers in the
conversation subsystem, now tier 1:

- **`heap_alloc` (`0x074626`)** — rounds the 32-bit size up to a multiple of
  4, adds 12 bytes of overhead, then walks a free list at `[0x46f6]`. A
  **private heap**, not DOS `INT 21h` — worth knowing for a port.
- **`heap_free` (`0x0747BE`)** — validates the far pointer via `0x745d1`,
  then steps back 8 bytes to the block header.

`symbols.py` tier 1 is now 22 names.

## 14. A trap in the breakpoint tooling, and the guard against it (2026-08-22)

`rsp_break.py` takes breakpoints as **file offsets** and converts with
`linear = file + delta`. That is only valid for the **DOS-mapped image**
(file `< 0x71B80`). `CODE_TAIL` is the Borland `FBOV` overlay pool, and
`AGENTS.md` already records that overlays are swapped into a buffer at an
address that **differs per load** — so a tail file offset corresponds to no
fixed linear address at all.

A breakpoint set there simply never fires, and the tool reported exactly what
it reports for genuinely cold code:

```
NO HIT within 90s -- a real negative result: this code did not execute.
```

That is the **wrong conclusion**, and it is the dangerous kind of wrong,
because it looks like evidence. Caught while trying to breakpoint
`gr_archive_load`'s decode callback at file `0x8B84A`.

The pattern across this session is clean once you sort by the boundary:

| breakpoint | region | fired |
|---|---|---|
| `0x112CC` VM entry | image | ✓ |
| `0x114CF` NEXT site, in gameplay | image | ✓ |
| `0x999D` NEXT site, at the menu | image | ✗ (genuinely cold) |
| `0x8B84A` `.GR` decode callback | **overlay pool** | ✗ (**could not fire**) |

`rsp_break.py` now computes the image end from the MZ header
(`(e_cp−1)*512 + e_cblp`) and **refuses** a target at or past it, rather than
running for 90 seconds and producing a false negative. The three earlier
negatives in this document are all image addresses and stand unaffected.

## 15. The overlay manager is resident, and therefore readable — 2026-08-22

§14 ended on "what is needed is the overlay manager's runtime state". The
first probe found something better than a way to read that state: **the
manager itself is in the mapped image**, so it can be disassembled like any
other code. `work/ovl_probe.py` (new) reads the `INT 3Fh` vector off the
running guest.

```
INT 3Fh vector = 3bd4:04e9 -> linear 0x3c229 -> file 0x392D9   (inside the image)
```

### The handler

`FUN@0x392D9`:

```
push bp / mov bp,sp
test bp,1 / je + / ljmp 0xe72:0x3b27        ; odd-SP path goes elsewhere
push ax,bx,cx,dx,si,di,ds,es
mov ax,0x63ba / mov ds,ax                   ; the manager's DATA segment (static)
les bx,[bp+2]                               ; ES:BX = the return address = the stub
push word ptr es:[bx]                       ; the 2 bytes following CD 3F
sub word ptr [bp+2],2                       ; rewind the return address past them
call 0x39389                                ; ovl_load
… mov ds,cs:[0xe] / lcall [0x26]            ; dispatch into the overlay
```

So the 5-byte stub is `CD 3F` plus a **2-byte call descriptor**, which the
handler consumes and skips — and the manager's data segment is static
**`0x63ba`** (file `0x669A0`, immediately below the thunk block at
`0x66AB0`).

### The loader

`FUN@0x39389` addresses a **per-overlay descriptor through `ES`** — fields at
`+0x10` (a "loaded" test), `+0x18` (a function pointer it calls), `+0x1a`
(flag bits 0–3), `+0x1b`, `+0x1c` — alongside manager globals `[0x118]`,
`[0x11c]`, `[0x12c]` in `DS = 0x63ba`.

**Those descriptors are zero in the file** and are filled in at load time,
which is consistent with everything §14 established: the overlay→memory
mapping is genuinely runtime state, not a table waiting to be read.

### Status

Breaking on the handler did **not** fire in 60 s from a 40 s-in attach —
expected if overlays are resolved once and thereafter not re-trapped, or if
they were all resolved before the attach. Getting a hit means arming before
the game starts.

What has changed is the shape of the problem. It was "an opaque runtime
mechanism"; it is now "a resident, readable routine at `0x392D9`/`0x39389`
with a known data segment and a known descriptor layout".

### The manager's memory map, cross-checked

| | static seg | file | contents |
|---|---|---|---|
| code | `0x35FF` | `0x38DF0` | handler at `+0x4E9`, loader at `+0x599` |
| data | `0x63BA` | `0x669A0` | globals `[0x110]`, `[0x118]`, `[0x11C]`, `[0x12C]`; the FBOV **`exeinfo` 174-entry table at `DS:0x01A0`** |

The code base is confirmed rather than assumed: the manager does `mov ds,
word ptr cs:[0xe]`, and the word at file `0x38DF0 + 0x0E` is **`0x63BA`** —
exactly the value the handler hardcodes as `mov ax,0x63ba`. Two independent
routes to the same data segment, which also validates the
`static = runtime − L` arithmetic for this segment.

The `exeinfo` table decoded in `AGENTS.md` therefore is not a stray structure:
it lives **inside the manager's own data segment**, immediately above the
loader's globals. `CS:0x26` (the `lcall [0x26]` the handler dispatches
through) is zero in the file, i.e. another load-time slot.

### How the manager finds the pool — and it validates our own arithmetic

`FUN@0x38E64` is the manager's startup search, and it is worth reading because
it computes the image size **the same way this project does**:

```
cmp [MZ e_magic], 0x5A4D                  ; 'MZ'
ax = e_cp ; cx = e_cblp ; if cx != 0: ax--
ax:dx = ax * 512 + cx                     ; = (e_cp-1)*512 + e_cblp
loop:
  lseek to DX:AX ; read 16 bytes
  ax:dx += 0x10
  if hdr != 'FB' -> fail
  if hdr != 'OV' -> ax:dx += ovrsize ; loop      ; FBOV blocks can chain
found:
  [0x114]:[0x116] = ax:dx                 ; THE OVERLAY POOL FILE OFFSET
  es = cs:[0x10] (= DGROUP 0x6608)
  es:[0x2210]:[0x2212] = ovrsize
  close
```

Replaying it on the file: `e_cp = 910`, `e_cblp = 384` → `0x71B80`, and the
bytes there are `FBOV`. **The game's own loader confirms the image-size
formula `AGENTS.md` derives** — previously supported by three-way agreement
between `e_ss:e_sp`, the page arithmetic and the signature; now it is also
what the binary itself computes.

So the overlay-position key is `[0x114]` (32-bit, in the manager's data
segment) = the pool's file offset, and per-overlay positions will be relative
to it. It is zero in the file, set during startup.

### A correction that fell out

The manager's data segment (`0x669A0..0x670B0`) **overlaps the region
`AGENTS.md` called the thunk block**. Exactly one `CD 3F` pair, at `0x66AB0`,
lies inside it and is therefore *data*, not a thunk — consistent with it being
the only one followed by all zeros. Corrected: **1,005** thunks spanning
**`0x670E0..0x68E7E`**, not 1,006 from `0x66AB0`.

### The stub segments located — the descriptor really is at `+0x10`

`ovl_load` addresses its descriptor as `ES:+0x10`, `+0x18`, `+0x1A`, `+0x1B`,
`+0x1C`, with `ES` = the trapping stub's segment. Scanning the thunk block for
paragraph-aligned positions that have `CD 3F` at `+0x00` **and sixteen zero
bytes at `+0x10..0x1F`** finds **77** of them — and that zero window is
exactly the range the loader reads. So the stub segments are:

```
+0x00   CD 3F ..            an INT 3Fh thunk
+0x08   8 bytes, static     varied: 62 distinct patterns across the 77
+0x10   16 bytes, ZERO      <- the runtime descriptor, filled at load
+0x20   more thunks
```

Two worked examples, `0x670E0` and `0x67110`, carry `2c 00 02 00 02 00 00 00`
and `2c 00 02 00 07 00 00 00` at `+0x08` — same shape, differing in one field.

✗ **An interpretation tried and refuted.** Reading `+0x08` as
`(u16 paragraph_offset_into_pool, u16 size_in_paragraphs, u16 index, u16)` is
wrong, and its own arithmetic kills it: the largest value seen is `0x505F` =
**20,575 paragraphs**, while the pool is `0x71B90..EOF` = **13,135
paragraphs** — it does not fit. Testing anyway, only **11 of 64** computed
overlay starts land on a plausible instruction. Recorded rather than tuned,
because a mapping that is right should not need 53 exceptions.

### What remains

The `+0x08` fields' real meaning, and the startup code that fills `+0x10`. The
position is good — a known routine (`ovl_load`), a known descriptor location
(77 stub segments, offset `+0x10`), a known pool-base global (`[0x114]`) — and
finishing it would unblock the whole 210 KB overlay pool, `.GR` type 8
included.

## 16. A candidate overlay→image segment alias, and a caution — IDENTIFIED (2026-08-22)

Overlay-pool code calls the graphics library through **segment `0x18`**:
`lcall 0x18:0x48f4`, `0x18:0x4fc2`, `0x18:0x4cf2`. Image-side code calls the
same library through **segment `0x85`**, and those three offsets are exactly
the known entries:

| offset | image-side file address | name |
|---|---|---|
| `0x48f4` | `0x07F44` | `gfx_select_bitmap` |
| `0x4fc2` | `0x08612` | `vga_blit_bitmap` |
| `0x4ac1` | `0x08111` | `vga_set_clip_window` |

Three matching offsets into one library is unlikely to be coincidence, so
**`0x18` is very probably the overlay-side alias of image segment `0x85`** —
consistent with §15's finding that overlay code uses a separate segment
namespace resolved by the manager at load time. That would be the first
concrete entry in an overlay→image segment map, which §14 identified as the
blocker for the whole 210 KB pool.

⚠ **It is an inference from matching offsets, not address arithmetic, and the
arithmetic explicitly does not work.** `0x2E00 + (0x18<<4) + 0x48f4 = 0x7874`,
not `0x7F44`. A parallel reading pass asserted the mapping as though it
computed; it does not. Recorded here as IDENTIFIED so the lead is not lost and
the false derivation is not repeated.

**How to settle it**: break on `gfx_select_bitmap` (`0x7F44`, an image address,
so breakpointable) during gameplay and read the return address off the stack.
If a caller resolves into the overlay pool, the live `CS` gives the runtime
segment, and comparing that against `0x18` plus the load base tests the alias
directly.

## 17. The timer service — a 17-slot INT 8 scheduler — RESOLVED (2026-08-23)

Found by reading `0x25C78`, one of the "clean decompilation" targets. Ghidra
rendered it as `DAT_108a_0008 = DAT_108a_0008 + in_CL;` — nonsense. The real
code is the 8086 **`push imm16` idiom**: the 8086 has no `push imm16`, so Turbo
C emits `push ax / push bp / mov bp,sp / mov [bp+2],imm / pop bp` (7 bytes) per
constant. Ghidra decompiled the scaffolding and dropped the constants. Anything
matching that byte pattern must be read as assembly.

Behind it is a **hand-written assembly module** occupying the low part of
segment `0x223b`.

### Locating it: file `0x251B0`

Two independent routes agree:

1. The relocation at file `0x25C82` — the operand of `mov [bp+2],0x223b` inside
   `0x25C78` — carries segment `0x223b`, so `0x223b` is a real load-time
   segment. `file = 0x2E00 + (0x223b<<4) = 0x251B0`.
2. **There are no relocations at all between `0x25190` and `0x25C82`.** That
   region is position-independent, entirely `cs:`-relative — and every variable
   slot the code addresses is zero in the file, at exactly the offsets the code
   implies. The private stack region in particular is a zero run of 516 bytes
   starting at `cs:0x1B4` and ending at `cs:0x3B8` — precisely bracketing the
   saved `SS:SP` pair the ISR writes to `cs:0x3B4`/`cs:0x3B6`.

### The ISR — `cs:0x40A` (file `0x255BA`), on INT 8

The installer at `cs:0x524` (file `0x256D4`) proves both the vector and the
entry. It opens by saving the vector it is about to replace:

```
mov ax,0 / mov es,ax
mov bx, es:[0x20] / mov es, es:[0x22]
mov cs:[0x118], bx / mov cs:[0x11a], es   ; the pair the uninstaller restores
```

and then installs its own:

```
mov dx, 0x40a            ; the handler offset
mov ax,0 / mov es,ax
mov es:[0x20], dx        ; IVT slot 8*4 = 0x20  -> INT 8, the PIT
mov es:[0x22], ds
```

The handler itself:

```
timer_isr:                        ; cs:0x40A
  cmp cs:[2],0 / jne eoi_exit     ; reentrancy guard
  mov cs:[2],1
  push ax,bx,cx,dx,si,di,bp,es,ds
  mov cs:[0x3b4],ss / mov cs:[0x3b6],sp
  mov ss,cs / mov sp,0x3b4        ; switch to the private stack
  mov cs:[0x11c],0                ; slot index
loop:
  si = cs:[0x11c]*2
  cmp cs:[si+0x6a],2 / jne next    ; slot state must be 2 (armed)
  mov ds, cs:[si+0x48]             ; the callback's own DS
  si <<= 1                         ; dword index
  dx:ax = cs:[si+0x8c]             ; accumulator
  dx:ax += cs:[0x114]              ; the per-tick increment
  if (dx:ax < cs:[si+0xd0]) { store back; goto next }
  dx:ax -= cs:[si+0xd0]            ; SUBTRACT the period, never zero it
  store back
  lcall cs:[si+4]                  ; fire the callback, far
next:
  inc cs:[0x11c] / cmp cs:[0x11c],0x10 / jbe loop
  restore ss:sp, pop all, mov cs:[2],0
eoi_exit:
  mov al,0x20 / out 0x20,al        ; EOI to the master 8259
  cmp cs:[0x1b0],0x6554 / jne trap ; the canary, see below
```

Subtracting the period instead of zeroing the accumulator means the service is
**drift-free**: a late tick still advances the schedule by exactly one period.
Worth preserving in the port.

### The variable area, complete

Every byte from `cs:0x002` to `cs:0x124` is accounted for, and each array is
**17 entries** wide. Four boundaries confirm it independently — `0x004 + 17*4 =
0x048`, `0x048 + 17*2 = 0x06A`, `0x06A + 17*2 = 0x08C`, `0x08C + 17*4 = 0x0D0`,
`0x0D0 + 17*4 = 0x114` — as does the reset routine at `cs:0x4E1`, which zeroes
`cx=0x11` (17) words at `0x6a` and `cx=0x22` (34 = 17 dwords) words at `0x8c`.

| offset | size | contents |
|---|---|---|
| `cs:0x002` | u16 | reentrancy guard (1 = ISR active) |
| `cs:0x004` | 17 × far ptr | per-slot callback |
| `cs:0x048` | 17 × u16 | per-slot callback `DS` |
| `cs:0x06A` | 17 × u16 | per-slot state; **2 = armed** |
| `cs:0x08C` | 17 × u32 | per-slot accumulator |
| `cs:0x0D0` | 17 × u32 | per-slot period |
| `cs:0x114` | u32 | per-tick increment added to every accumulator |
| `cs:0x118` | far ptr | **saved original INT 8 vector** (restored on uninstall) |
| `cs:0x11C` | u16 | ISR loop index; `0xFFFF` when uninstalled |
| `cs:0x11E` | 4 | not yet identified |
| `cs:0x122` | u16 | the PIT divisor last programmed |
| `cs:0x124` | 16 × far ptr | dispatch tables — a *separate* registry, see below |
| `cs:0x1B0` | 4 | `"Test"` — the stack canary |
| `cs:0x1B4` | 512 | private stack, grows **down** from `cs:0x3B2` |
| `cs:0x3B4` | 2+2 | saved `SS`, saved `SP` |
| `cs:0x3B8` | — | code begins |

**16 slots or 17?** Both, and the installer settles it: `mov bx,0x51d / mov
cs:[0x44],bx / mov cs:[0x46],cs` pre-wires slot **16** — `(0x44-4)/4` — to an
internal routine at `cs:0x51D`. The resolver rejects indices `>= 0x10`, so
slots 0–15 are registrable and **slot 16 is reserved for the service itself**.

### Setting the rate — `cs:0x5A0` (file `0x25750`)

```
cli
mov al,0x36 / out 0x43,al     ; PIT ch0, lo/hi byte, mode 3, binary
mov ax,[bp+6] / mov cs:[0x122],ax
out 0x40,al / mov al,ah / out 0x40,al
```

A one-argument `timer_set_divisor(u16)` that also caches the divisor.

### The stack canary

`cs:0x1B0` holds the literal ASCII `"Test"`, sitting immediately below the
private stack's low end at `cs:0x1B4`. The ISR compares it against `0x6554`
(`"Te"`) on every exit, including the reentrant fast path. On mismatch:

```
sti / int3 / jmp $
```

— an infinite breakpoint loop. A deliberate stack-overflow trap on a 512-byte
ISR stack, not a coincidence of bytes.

### The second registry — resolve-by-code and tail-jump

Distinct from the timer slots, in the same module:

```
svc_resolve:                     ; cs:0x3BA (file 0x2556A)
  cmp bx,0x10 / jae fail         ; BX = table index, 0..15
  les bx, cs:[bx*4 + 0x124]      ; -> an array of {u16 code, u16 offset}
  if (es:bx == 0) fail
  scan for es:[bx] == AX, stride 4, terminator code 0xFFFF
  hit:  return dx:ax = es : es:[bx+2]
  fail: return 0:0

svc_call:                        ; cs:0x3F2 (file 0x255A2)
  mov bx, ss:[sp+4]              ; the caller's first stack argument
  call svc_resolve
  if (dx:ax != 0) { push dx / push ax / retf }   ; TAIL-JUMP, args left in place
  retf
```

The `cs:0x124` table is all zeros in the file and needs no relocations, so it
is **registered at runtime**. `0x25C78` is a C-side wrapper: it pushes the far
pointer `0x223b:0x09fc` (file `0x25BAC`, inside this same module) plus its own
argument, sets `AX = 0x64`, and tail-dispatches. Codes `0x64`, `0x65` and `0x67`
are used at nearby sites.

### Callers

**103 static far calls** target segment `0x223b`, from a contiguous caller
region `0x1F6xx`–`0x228xx`, at roughly 40 distinct entry offsets. Almost every
one passes a context handle first, from DGROUP `[0x2b6]` or `[0x2b8]`.

### Why this matters for the port

This is the game's **timing base**. The Falcon port needs an equivalent of the
17-slot drift-free scheduler and its per-slot periods; the periods themselves
are runtime state, so they must be read from the DOS oracle rather than
guessed. The `out 0x43 / out 0x40` divisor at `cs:0x122` is likewise runtime.
What *is* static and portable is the structure recorded above.

This does not establish a 60 Hz DOS game tick, nor does the PC monitor/VGA
refresh specification replace the PIT evidence. Display/VBL cadence and game
logic cadence must remain separate until a controlled DOS run records their
relationship. A target-side 60 Hz Falcon/Videl presentation is therefore a
display choice only; it cannot alter the authoritative timer/input/frame order.

## 18. The graphics module — segment `0x0085`, and its 50-entry API — RESOLVED (2026-08-23)

§17's timer module suggested a general lens: **hand-written assembly modules
address their own data with a `cs:` override, and Turbo C never does.** Scanning
the image for `cs:`-relative data access and clustering the hits recovers the
timer module (`0x241ae`) and the overlay manager (`0x38e10`) — both already
known, so the lens validates — plus one more cluster, 199 hits across
`0x78bb`–`0x88ba`. That range contains `gfx_select_bitmap` at `0x7F44`.

### The base, settled

§16 recorded `gfx_select_bitmap` as "`0x85:0x48f4`" without pinning the
segment. The arithmetic closes exactly:

```
file = 0x2E00 + (0x0085 << 4) + 0x48F4 = 0x2E00 + 0x850 + 0x48F4 = 0x7F44
```

So **segment `0x0085` has file base `0x3650`**, and it receives **101 static
relocations** — a module on the scale of the timer's 103.

### Entry is via a stack-switching thunk

`0x7F44` is not the graphics routine. It is one of **50 identical thunks**:

```
push bp / mov bp,sp / push di,si,ds,es
mov cs:[0x43f0], ss        ; save the caller's stack
mov cs:[0x43f2], sp
<load arguments from [bp+6].. into registers>
mov dx, 0x372c
mov ds,dx / mov es,dx      ; the module's data segment
cli / mov ss,dx / mov sp,0x4fa8 / sti    ; its private stack
call <near target>
cli / restore ss:sp from cs:[0x43f0/0x43f2] / sti
pop es,ds,si,di,bp / retf
```

All 50 use the same private stack top, `0x372c:0x4FA8`. The saved `SS:SP` pair
lives in the *code* segment at `cs:0x43F0`, exactly as the timer keeps its own
at `cs:0x3B4`.

### Two-level dispatch

Twenty of the fifty go through a **40-entry near-jump table at `cs:0x5278`**
(file `0x88C8`–`0x893C`, 3 bytes per `jmp`); the other thirty call their body
directly. `gfx_select_bitmap` is the long route:

```
thunk 0x7F44 (cs:0x48F4) -> jumptable 0x8907 (cs:0x52B7) -> body 0x67E5 (cs:0x3195)
```

The full resolved map — thunk, jump-table slot, final routine and argument
count — is regenerated into `work/gfx_api.txt`. Bodies span `cs:0x0B9B` to
`cs:0x43C5`.

Argument counts are **stack slots, not C arguments**: several entries use slots
`0x6,0xa,0xc,0xe,0x10` and skip `0x8`, which is a far pointer occupying
`0x6`–`0x9` followed by four words. The widest entry is thunk `0x8612` → body
`0x5824`, eight word slots.

### The data segment

`0x372c` → file `0x3A0C0`. Its stack top `0x4FA8` puts the segment's used
extent at least at file `0x3F068`. The relocation-free gap found in the same
sweep runs `0x3ABDA`–`0x3F64C`: the first ~2.7 KB of the data segment does
carry relocations (initialised far pointers), then 19 KB carries none and ends
just past the stack top. Consistent, though not an exact coincidence of bounds.

### What this changes

The renderer's *shape* is now static and readable: 50 public entries, their
arities, the dispatch path, the data segment and the stack discipline. That is
the interface a Falcon port has to reproduce. It does **not** decode the
blitters themselves — the bodies at `cs:0x0B9B`–`cs:0x43C5` are still to be
read, and the viewport state they consume lives in `0x372c`, which is
runtime-initialised and therefore oracle territory.

## 19. The overlay call namespace, cracked — the 210 KB pool is statically resolvable — RESOLVED (2026-08-23)

§14 named the overlay→image segment map as *the* blocker for the whole 210 KB
pool, and §16 could only offer one candidate alias, inferred from three
matching offsets and explicitly flagged as not-arithmetic. Both are now
settled, and the answer was hiding in a table already decoded.

### The route in

§18 pinned segment `0x0085`'s base and enumerated all **50** of its public
thunk offsets. That turns §16's three-offset coincidence into a real test:
scan the pool for every `lcall 0x18:xxxx` and see how many land on a thunk.

```
segment 0x18: 248 lcalls at 24 distinct offsets
   landing on a real segment-0x85 thunk entry: 24/24 distinct  (248/248 sites)
```

Perfect. §16's alias is confirmed — but the *reason* it works matters more than
the fact.

### The rule

Repeating the exercise for every overlay-side call segment, against every
possible image base, gave a table of best matches: `0x30`→`0x0e72`,
`0x58`→`0x1ab4`, `0x68`→`0x1b44`, `0x80`→`0x1b90`, `0x88`→`0x1c86`,
`0x98`→`0x1faf`, `0xf8`→`0x28c4`, `0x148`→`0x3284`, `0x150`→`0x331a`,
`0x160`→`0x341f`, `0x168`→`0x344b`. Two things stand out: every V is a
**multiple of 8**, and the map is **monotonic**. §15's `exeinfo` table is 174 ×
**8 bytes** at file `0x66B40`.

> **The V in `lcall V:off` is not a segment. It is the byte offset of an entry
> in the `exeinfo` table** — i.e. the address of the overlay descriptor,
> relative to the manager's `DS:0x01A0`.
>
> ```
> seg  = u16 at 0x66B40 + V          (V a multiple of 8, V/8 < 174)
> file = 0x2E00 + (seg << 4) + off
> ```

Reading the table directly reproduces **all 12** of the statistically-derived
pairs — two fully independent derivations agreeing, one from Ghidra's function
entries, one from the manager's own data.

### Validation across the whole pool

Applying the rule to every far call in `0x71B80..EOF`:

| | | |
|---|---|---|
| 2789 | 65.3% | land on a known image **function entry** |
| 1085 | 25.4% | land on an **INT 3Fh stub** (overlay→overlay, via the resident thunk block) |
| 176 | 4.1% | land on a `push bp; mov bp,sp` **prologue** Ghidra missed |
| 154 | 3.6% | other image address |
| 65 | 1.5% | V not a valid table offset — false hits from the naive `9A` byte scan |

**95% resolve to something that is unmistakably a call target.** A rule that
was wrong would not produce that distribution.

The 25.4% is itself a structural result: an overlay calling another overlay
does not call it directly, it calls a resident `CD 3F` stub, and the manager
resolves onward. That also explains why those V values scored badly against
Ghidra's function list — their targets are 5-byte stubs, not functions.

### What it costs to have been wrong before

AGENTS.md recorded that the small V values were "absent" from `exeinfo` and
therefore "a separate namespace … which is why they cannot be mapped
statically". The observation was correct — they are absent from the table's
*values* — but they were never values. They were **offsets into it**. Corrected
in place there.

### The `.GR` type 8 decoder

The callback `0x03b8:0x005c`, which has blocked `.GR` type 8 (42% of sprite
records) through five approaches, resolves immediately:

```
$ python work/ovl_resolve.py 0x3b8:0x005c
  exeinfo[0x3b8] (idx 119) = segment 0x6509
  file 0x067eec   [INT 3Fh stub]
  overlay stub, manager call descriptor 0x0377
```

So the decoder is an overlay routine reached through the manager with call
descriptor `0x0377`. That is not yet the decoder's body — the descriptor still
has to be turned into a pool address, which is what §15's loader at `0x39389`
does with its runtime-filled descriptors. But the target is now a *named,
single* unknown rather than an unbounded one.

### Tooling

`work/ovl_resolve.py` — `V:off` resolution, `--table` (all 174 entries),
`--audit` (the classification above), `--callers <file addr>` (which pool sites
call a given image routine). The last of these makes the pool's calls into the
image searchable for the first time.

## 20. The overlay pool's 928 function entries — RESOLVED (2026-08-23)

§19 resolved `lcall V:off` as far as a resident `CD 3F` stub. The rest of the
route was sitting in front of the stub table.

### The per-overlay block

Every `exeinfo` segment that begins `CD 3F` is a resident block laid out as:

| offset | | |
|---|---|---|
| `+0x00` | u16 | `CD 3F` — the block's own trap, descriptor `0x0000` |
| `+0x04` | u32 | the overlay's code offset **within the pool** |
| `+0x08` | u16 | the overlay's size in bytes |
| `+0x0A` | u16 | not identified |
| `+0x0C` | u32 | stub count |
| `+0x10` | 16 B | runtime descriptor — **zero in the file** |
| `+0x20` | 5 B × N | stub table: `CD 3F <u16 descriptor> 00` |

The zero 16 bytes at `+0x10` are precisely §15's runtime descriptor, whose
fields the loader at `0x39389` reads at `+0x10`, `+0x18`, `+0x1A`, `+0x1B`,
`+0x1C` — so §15's "those descriptors are zero in the file and are filled in at
load time" was describing *this* structure, seen from the other end.

**79** of the 174 `exeinfo` entries are such blocks. All 79 have
`POOL + [+0x04]` landing inside the pool, ascending with index, the largest
`0x950` bytes short of EOF. For overlay 119 the stub count field says 25 and
there are exactly 25 `CD 3F` stubs.

### The body formula

```
file = 0x71B90 + hdr[+0x04] + descriptor
```

`0x71B90`, not `0x71B80` — the pool's own 16-byte header precedes the code, as
AGENTS.md already recorded. Getting this wrong lands 16 bytes early, mid-
instruction, which is how the constant was found.

> Applied to **every stub in the binary: 930/930 — 100% — land on a
> `push bp; mov bp,sp` prologue.**

928 distinct entries (two stubs are aliases). `work/ovl_resolve.py --entries`
emits them. The 210 KB pool now has a function list.

The count does not quite reconcile with AGENTS.md's 1,005 raw `CD 3F` pairs:
930 stubs + 79 block headers = 1,009. The ~4 difference is unexplained and is
recorded rather than smoothed over — most likely a few `CD 3F` byte pairs in
the counted range are data, or two blocks share a range.

### What this does to `.GR` type 8

`data-formats.md` identified `gr_archive_load`'s fifth argument, the
`post_far(buf_lo, buf_hi, size, index)` callback taken from
`push 0x3b8 / push 0x5c`, as "a post-processing callback that gets exactly the
buffer, and therefore **the best decoder candidate in the binary**", and
recorded that `0x03b8:0x005c` "cannot be resolved from the file".

It resolves now — `exeinfo[0x3b8]` → segment `0x6509`, stub 12 at `+0x5c`
(`0x20 + 12*5`, so the offset is exactly a stub index), descriptor `0x0377`,
body at file **`0x8B5C7`**. Two things confirm the resolution independently of
§19's statistics: the body is a clean prologue, and its argument usage matches
the documented signature exactly — `[bp+0xa]` is `size`, `[bp+0xc]` is `index`.

And then it eliminates the candidate. The routine is an **allocator**:

```
post_far(buf_lo, buf_hi, size, index):
  if (size == 0) { [0x2188][index] = 0; return 1 }     ; dword stride
  [0x2188][index] = [0x1502]                           ; the next handle
  [0x2184][[0x1502]] = ([0x1506] << 12) + [0x1504]     ; packed (bank, paragraph)
  [0x1502]++
  [0x1504] += size >> 4 ; if (size & 15) [0x1504]++    ; round up to a paragraph
  return 1
```

`[0x2188]` is the shape-slot table `gfx_id_to_shape_slot` (`0x1D6F7`) already
reads. **The routine contains zero references to `[bp+6]`/`[bp+8]` — it never
touches the buffer at all.** It cannot be a decoder.

So the five-approach `.GR` type 8 hunt was chasing a callback that only
registers where each record was placed. That candidate is closed on evidence,
and the search has to move to whoever reads `[0x2184]`/`[0x2188]` at draw time.

## 21. `fatal_error`, and what its 26 call sites are worth (2026-08-23)

The first fruit of §20: the pool's named functions can now be read, and the
call sites that reach them resolved. Two of the most-called are decoded.

### `fatal_error` — file `0x8A1F1`, reached as `lcall 0x390:0x0025`

```
fatal_error(u16 code):
  strcpy(buf, DGROUP+0x1432)              ; lcall 0x30:0x2891 -> 0x13DB1 = strcpy
  buf[0x2a] = 'A' + (code >> 12)
  buf[0x2b] = '0' + ((code >> 6) & 7)
  buf[0x2c] = '0' + ((code >> 3) & 7)
  buf[0x2d] = '0' + (code & 7)
  ...
```

and the template at `DGROUP+0x1432` (file `0x6A2B2`) is

```
"Underworld can no longer run.  Error code XXXX.\r\n$"
```

whose offset `0x2A` is exactly `XXXX`. The `$` terminator is DOS `INT 21h`
`AH=09h`. So the code is rendered as **a letter for bits 12–15 plus the low 9
bits in octal** — bits 9–11 are not used.

Note how the resolution chain paid for itself here: `lcall 0x30:0x2891` is
meaningless as an address until §19's rule turns `0x30` into segment `0x0e72`,
giving file `0x13DB1`, which `symbols.py` already knew as `strcpy`.

### The codes actually raised

Of 26 call sites, 17 push a plain `imm16` immediately before:

| code | displayed | sites |
|---|---|---|
| `0x4002` | **E002** | 10 |
| `0x3015` | D025 | 2 |
| `0x3003` | D003 | 1 |
| `0x300a` | D012 | 1 |
| `0x300b` | D013 | 1 |
| `0x300c` | D014 | 1 |
| `0x300d` | D015 | 1 |

The remaining 9 compute the code rather than pushing a constant.

These match the error strings UW2 players actually see — **E002** is the
documented out-of-memory failure — which is an external check on the whole
chain: the exeinfo rule, the body formula, and the octal decode all have to be
right for `0x4002` to render as `E002`.

`0x300a` (D012) is pushed at `0x74EB4`, immediately before the
`heap_alloc(([0x471c] + 0x800) * 2)` at `0x74EEA` — an allocation-failure path,
which corroborates the reading independently of the string.

### `tbl4704_get_word` — file `0x765A7`

The most-called routine in the pool, **87 resolved callers**:

```
u16 tbl4704_get_word(int i) { return ((u16 far *)[0x4704])[i]; }
```

The array behind it is allocated at `0x74EF1` as
`heap_alloc(([0x471c] + 0x800) * 2)` — `[0x471c]` words followed by 2048 more,
with `[0x46FC]` pointing at the boundary and `[0x4714]` holding the count. All
15 references to `[0x4704]` are inside one overlay cluster (`0x74EF1`–`0x76800`,
overlay 95), so that overlay owns the structure and exports accessors. **What
the array holds is not yet established** and is not guessed at here.

## 22. The blitter's dispatch — one clipper, twelve inner loops (2026-08-23)

§18 mapped the graphics module's 50 public entries but not their bodies. The
six widest ones (5–8 stack slots — thunks `0x8612`, `0x8675`, `0x86d8`,
`0x876c`, `0x87cb`, `0x8818`) all land in one contiguous run of bodies at
`0x5824`–`0x58C5`, and they share a single shape:

```
entry:                                  ; e.g. cs:0x21D4, file 0x5824
  cmp byte ptr [0xdc5], 0               ; a mode flag
  jne alt
  mov word ptr [0xdc2], 0x5372          ; select the inner loop
  jmp cs:0x2296
alt:
  mov word ptr [0xdc2], 0x5467
  jmp cs:0x2296
```

`[0xdc2]` is a **near function pointer** — the selected inner loop — and
`[0xdc5]` is the selector. One entry (file `0x583D`) adds a second test,
`test ax, 3`, choosing a different loop for **aligned vs unaligned** starts.
That is a three-way choice: mode flag, then alignment.

Thirteen assignment sites name **twelve distinct inner loops**:

| `cs:` | file | | `cs:` | file |
|---|---|---|---|---|
| `0x06F8` | `0x003D48` | | `0x568B` | `0x008CDB` |
| `0x0729` | `0x003D79` | | `0x56E3` | `0x008D33` |
| `0x0A7F` | `0x0040CF` | | `0x581B` | `0x008E6B` |
| `0x5372` | `0x0089C2` | | `0x586D` | `0x008EBD` |
| `0x5467` | `0x008AB7` | | `0x58C7` | `0x008F17` |
| `0x5578` | `0x008BC8` | | `0x58F8` | `0x008F48` |

Note the high cluster runs to file `0x8F48`, past the `0x88C8` jump table — so
segment `0x0085` extends further than §18's "bodies span `cs:0x0B9B`–`0x43C5`",
which described only the routines the thunks call directly.

### The shared tail is the clipper

`cs:0x2296` (file `0x58E6`) is reached by every one of them. It loads the
source origin from `[0xdc6]`/`[0xdc8]`, clears bit 15 of the word at
`[[0x141b]]`, and clips the rectangle against **`[0x3df4]`, `[0x3df6]`,
`[0x3df8]`** — the same clip window `symbols.py` already records for
`gfx_clipped_rect` (`0x8342`, "clips against `[0x3df4..0x3dfa]`"). It ends at

```
jmp word ptr [0xdc2]
```

with two such `jmp` sites (`cs:0x236B`, `cs:0x2437`) and one `call`
(`cs:0x2487`).

### Why this shape matters for the port

The renderer is **one clipper plus twelve specialised inner loops**, chosen by
a mode flag and source alignment — not twelve independent blitters. A Falcon
port reproduces the clipper once and then needs only the loops the game
actually selects. Which of the twelve those are is a runtime question. ✓ **`[0xdc5]` is now
decoded — it selects transparent (colour-0-skipping) blitting, §30.**

The twelve loop bodies themselves are still unread.


## 23. The exeinfo rule covers data segments too, and the blitter mode flag (2026-08-23)

§19 established the rule for `lcall V:off`. It is not limited to calls.

Pool code loads data segments the same way — `mov ax, V / mov es, ax` — with V
again an `exeinfo` byte offset. Two independent checks confirm it, both against
values the project already knew from elsewhere:

| V | `exeinfo[V]` | file | known as |
|---|---|---|---|
| `0x0540` | `0x6608` | `0x68E80` | **DGROUP** — the address `symbols.py` hardcodes |
| `0x0198` | `0x372c` | `0x3A0C0` | the graphics **data** segment, from §18's thunks (`mov dx,0x372c`) |
| `0x0018` | `0x0085` | `0x03650` | the graphics **code** segment, §18 |

Neither `0x6608` nor `0x372c` was derived from the pool, so this is a genuine
cross-check rather than a restatement. The most-loaded are `V=0x1a0` → `0x3d14`
(50 sites), `V=0x1d0` → `0x4fce` (36), `V=0x198` → `0x372c` (31).

### `[0xdc5]` — §22's blitter selector

§22 left the mode flag undecoded because segment `0x0085` only ever reads it.
It is written from outside, always in the same shape:

```
mov ax, 0x372c          ; or, from the pool, mov ax, 0x198
mov es, ax
mov byte ptr es:[0xdc5], 1
```

**39 write sites: 20 store `1`, 19 store `0`.** So it is a plain boolean, not a
mode enumeration — the blitter picks between two inner loops per entry, and the
one entry that also tests `test ax, 3` picks between three.

`[0xdc4]`, the flag §22 found the clipper reading at `cs:0x22B0`, is written the
same way at 13 sites.

At file `0x1D765` the flag is set to `1` immediately before
`call 0x1D6F7` = `gfx_id_to_shape_slot`, so it is a **per-draw** setting, not a
global video mode. ✓ **What the two states mean is settled in §30: `[0xdc5]`
is transparency, `[0xdc4]` is clipping-enable.**

## 24. UW2 renders in VGA Mode X, and the addressing is fully static — RESOLVED (2026-08-23)

Reading one of §22's twelve inner loops — `cs:0x5372`, file `0x89C2`, the one
the widest entry selects when `[0xdc5] == 0` — settles what the renderer
actually targets.

```
mov dx, 0x3c5                        ; VGA Sequencer Data port
mov es, word ptr [0x3dfc]            ; the video segment
...
mov ax, word ptr [bp + 0x36ac]       ; row offset table, indexed by y
...
mov al, byte ptr [bp + 0x3b64]
and al, byte ptr [bp + 0x3ca8]       ; two plane-mask tables, indexed by x
out dx, al                           ; -> Map Mask
sar di,1 / sar di,1                  ; di = x / 4
...
movsb / add si, 3 / loop             ; copy every 4th source byte
```

Port `0x3C5` with a plane mask, `x/4` addressing, and a source stride of 4 is
**VGA Mode X** — 320×200 unchained planar, not linear mode 13h. `[0x3dfc]` is
`00 a0` in the file: segment `0xA000`.

The clip window is statically initialised too — `[0x3df4..0x3dfa]` reads
`00 00 / c7 00 / 3f 01 / 00 00`, i.e. **0..319 by 0..199**.

### The tables are BSS, but their builders and seeds are not

`[0x36ac]`, `[0x3b64]` and `[0x3ca8]` are all zero in the file. That is the same
shape as the problem recorded for the Comanche renderer — except here it does
**not** need the oracle, because the builders are in the image and the seeds are
static.

**Row offsets** — builder at `cs:0x2B2C` (file `0x617C`):

```
mov dx, word ptr [0x36a8]          ; the stride
loop:  mov word ptr [bx + 0x36ac], ax
       add ax, dx
       sub bx, 2 / dec cx / jne loop
```

so `row[y] = base + y * [0x36a8]`, and **`[0x36a8]` is `50 00` in the file —
80**. 80 bytes per row across 4 planes is 320 pixels, which agrees with the clip
window independently.

**Plane masks** — builder at `cs:0x2B44` (file `0x6194`) plus the expander at
`cs:0x2B53`:

```
mov si, 0x2d2c / mov di, 0x3b64 / call expander
mov si, 0x2d31 / mov di, 0x3ca8 / (falls through)
expander:  mov cx, 0x50            ; 80 iterations
           push cx / push si
           mov cx, 4 / rep movsb   ; 4 bytes, from the same seed each time
           pop si / pop cx / loop
```

80 × 4 = **320 bytes, one per x**, and both seeds are static in the file:

| table | seed at | bytes | so |
|---|---|---|---|
| `[0x3b64]` | `[0x2d2c]` | `0f 0e 0c 08` | `mask_lo[x] = {0x0f,0x0e,0x0c,0x08}[x & 3]` |
| `[0x3ca8]` | `[0x2d31]` | `01 03 07 0f` | `mask_hi[x] = {0x01,0x03,0x07,0x0f}[x & 3]` |

The blit ANDs the two — `mask_lo[x_start] & mask_hi[x_end]` — which is the
standard left-edge/right-edge plane-mask pair for a span lying inside one
4-pixel group.

### For the port

Everything the Falcon port needs to reproduce UW2's framebuffer addressing is
**static and cited**: 320×200 Mode X at `0xA000`, row stride 80, and both plane
mask tables as 4-byte seeds repeated 80 times. No oracle, no fitted constants.
The Falcon is planar as well, so the plane-mask structure carries over rather
than needing to be undone.

Still unread: the other eleven inner loops, and what `[0xdc5]`'s two states
select between (§23).

## 25. `.GR` type 8 — the decoder found, statically — RESOLVED (2026-08-23)

✗ An earlier draft of this section said the failed approaches "were all looking
on the load side". That is wrong and unfair to the prior work:
`data-formats.md` had already established that no pixel decoding happens at
load time and stated explicitly that "the type-8 decoder is therefore in the
*draw* path, not the load path, which is where a further attempt should start."
It had the right target; what it lacked was a way into the overlay/segment
namespace, which §19–§20 supplied.

Three facts that section recorded now turn out to be **corroborations**, and
they are worth stating because each was derived independently, from the data
rather than the code:

- *"The type byte is not dispatched by a byte compare — no 96-byte window
  contains `cmp al,4`, `cmp al,8` and `cmp al,0x0a`."* Correct, and now
  explained: dispatch is a **jump table**, `call word ptr cs:[bx + 0x6d30]`.
- *"Byte `+4` is the payload's nibble count, low byte: across all 736 type-8
  records `(2 × payload_bytes − b4) mod 256` is only ever 2 or 3."* The decoder
  `lodsw`s a u16 count at the head of the data and unpacks `(count+1) >> 1`
  source bytes into `count` nibbles — so the count is ≈ 2 × payload bytes,
  exactly as measured.
- *"Byte `+3` is an independent field taking values 0–7."* It is the **aux
  palette index**: `shape_draw` does `add ax, 0x6732` with a 16-byte stride
  into the `allpals.dat` block, and every emitted pixel goes through `xlatb`.

The route to the decoder starts from the tables `post_far` writes.

### The chain

```
gfx_id_to_shape_slot   0x1D6F7   id -> handle, via [0x2188] (4-byte stride, low 10 bits)
shape_handle_to_ptr    0x1D4D7   handle -> far ptr, via [0x2184] (u16, packed)
shape_draw             0x1D543   reads the record header, dispatches, blits
   record +0 = format byte, +1 = width, +2 = height, +3 = aux palette index
   format 4 -> raw, data at +5
   otherwise  lcall 0x2133:0x0f83  ------> the decoder
```

`lcall 0x2133:0x0f83` is file `0x250B3`, a stack-switching thunk of exactly the
§18 shape — it saves `SS:SP` into `cs:0x0C24`/`0x0C26`, switches `DS`/`ES`/`SS`
to segment `0x60D8` with `sp = 0x510`, and far-calls `0x65c:0x7f0c`.

That resolves to file **`0x112CC`**, which is one instruction:

```
call word ptr cs:[bx + 0x6d30]
retf
```

**A dispatch table on the record's format byte**, which the thunk loads
unscaled from `[bp+0xe]` — so the format indexes the table *by byte*, and only
even format values are valid entries:

| format | handler |
|---|---|
| 2 | `0x954B` |
| 4 | `0x93E0` |
| 6 | `0x94DC` |
| **8** | **`0x9499`** |
| 10 | `0x93F9` |

The table is only 7 words: the ramp `00 01 02 03 …` immediately after it at
`cs:0x6d3e` is a separate 256-byte LUT — the same one the screen-transition
code indexes at `0x3DCB`.

### What type 8 actually is

```
format8:                                   ; file 0x9499
  mov cx, 1
  call 0x9423                              ; setup, variant selector in CX
  si = bp                                  ; source
  es = 0x43bf ; di = 0                     ; scratch (relocated segment)
  lodsw -> dx                              ; pixel count
  cx = (count + 1) >> 1                    ; source bytes
unpack:
  lodsb / ah = al
  al &= 0xf0 ; al >>= 4 ; stosb            ; high nibble first
  al = ah ; al &= 0x0f  ; stosb            ; then low nibble
  loop unpack
  cx = count
  ds = 0x43bf ; si = 0                     ; the unpacked nibbles
  es = 0x43bf ; di = 0x5400
  call 0x954d                              ; second stage
  ax = es + 0x540                          ; result segment
  ret
```

**Stage 1 is a 4-bit unpack** — two pixels per source byte, high nibble first.
Format 6 is byte-identical except it passes `cx = 2` to the same setup, so the
two differ only in that variant selector.

**Stage 2, at `0x954D`, is RLE through a translation table:**

```
  bp = si + cx                             ; end
loop:
  if si >= bp: done
  al = *si++                               ; control
  if al <= 2: -> special cases at 0x95b9
  cx = al ; al = *si++ ; xlatb             ; run: translate one byte
  rep stosb                                ;      emit it cx times
  cx = *si++                               ; then a literal count
  while (cx--) { al = *si++; xlatb; stosb }
  jmp loop
```

Alternating run and literal segments, **every emitted byte passed through
`xlatb`** — so the 4-bit values are indices into a translation table, which is
what the record header's `+3` aux-palette index selects (`add ax, 0x6732` in
`shape_draw` — the `allpals.dat` block `gfx_init` loads). A sibling path at
`0x9575` reassembles values with `mov cl,4 / shl ax,cl / or al,[si]`.

So `.GR` type 8 is **nibble-packed 16-colour data, RLE-compressed, drawn
through an auxiliary 16-entry palette**. That is consistent with the format
being 42% of sprite records — it is the compact case.

**Not yet decoded**: the `al <= 2` special cases at `0x95B9`, the setup at
`0x9423`, and the exact meaning of the `cx = 1` vs `cx = 2` variant. Those are
needed before a byte-exact rebuild; the shape of the format is settled.

### A tooling correction

`verify_claim.py` matched needles as **substrings**, so `and al, 0xf` passed
against the instruction `and al, 0xf0` — a different instruction. Fixed to
require an exact match of the whole normalised instruction, with substring hits
reported as `NEAR MISS` instead of `PASS`. **All 93 claims made in this
session were re-run under exact matching: 93 pass, 0 failures**, so no
conclusion here rested on the flaw.

## 26. The twelve blitter loops — span lists, two target families (2026-08-23)

§22 named twelve inner loops and read one. Reading the rest changes the picture
of what the blitter *consumes*.

### The source is a span list, not a bitmap

Every loop parses the same stream. `cs:0x06F8` (file `0x3D48`) is the whole
thing in 49 bytes:

```
loop:
  lodsw                          ; row index
  shl ax, 1                      ; *2 for a word index -- and CF = bit 15
  jb  end                        ; bit 15 set = end of list
  mov bx, ax
  mov di, ss:[bx + 0x95c]        ; row -> destination offset
  lodsw / add di, ax / mov cx, ax ; x-start
  lodsw / sub ax, cx / inc ax    ; x-end -> width = x1 - x0 + 1
  mov cx, ax
  lodsw / xchg si, ax            ; source offset for this span
  rep movsb
  xchg si, ax                    ; restore the stream pointer
  jmp loop
```

So a drawable is a list of `{u16 row, u16 x0, u16 x1, u16 src_offset}`
records, terminated by a row word with **bit 15 set**. The Mode X loops parse
the identical header (`lodsw / shl ax,1 / jb` at `0x89CA`).

For the port this matters more than the pixel loops: UW2 hands the blitter
**precompiled spans**, so a Falcon implementation reproduces a span walker, not
a rectangle blitter.

### Two target families

| | addressing | row table | target segment |
|---|---|---|---|
| **Mode X planar** | `di = x/4`, `out 0x3c5` plane mask | `[0x36ac]` | `[0x3dfc]` = `0xA000` |
| **Linear** | `di = row + x`, one byte per pixel | `[0x95c]` or `[0x39d2]` | `[0x958]` = **`0x3d14`** (static) or `[0x39d0]` (runtime) |

`cs:0x06F8` and `cs:0x58C7` are the *same algorithm* on different targets —
they differ only in which pair of globals they name. Segment `0x3d14` (file
`0x3FF40`) is the offscreen bitmap, and it is the single most-loaded data
segment from the overlay pool (`V=0x1a0`, 50 sites, §23).

### The twelve, classified

| `cs:` | file | bytes | |
|---|---|---|---|
| `0x06F8` | `0x3D48` | 49 | linear, target `[0x958]` |
| `0x58C7` | `0x8F17` | 49 | linear, target `[0x39d0]` |
| `0x0729` | `0x3D79` | 512 | Mode X, unrolled ×40 |
| `0x58F8` | `0x8F48` | 510 | Mode X, unrolled |
| `0x5372` | `0x89C2` | 245 | Mode X, `movsb` + `add si,3` |
| `0x5467` | `0x8AB7` | 273 | Mode X, `lodsb`/`stosb` |
| `0x5578` | `0x8BC8` | 275 | Mode X, `rep movsb` per plane |
| `0x56E3` | `0x8D33` | 312 | Mode X, **`or al,al` per pixel — the masked/transparent blit** |
| `0x0A7F` | `0x40CF` | 324 | plane masks, no row table |
| `0x568B`/`0x581B`/`0x586D` | `0x8CDB`/`0x8E6B`/`0x8EBD` | ~85 | Mode X, short variants |

`or al, al` per pixel appears in exactly one Mode X loop, `0x56E3` — that is
transparency handling, and it is the only loop that has it.

### What `[0xdc5]` selects — narrowed, not settled

It is **not** uniformly "linear vs planar": entry `0x5824` picks between
`0x5372` and `0x5467`, both Mode X, while entry `0x5864` picks between `0x06F8`
(linear) and `0x0729` (Mode X). ✓ **Resolved in §30**: `[0xdc5]` selects **transparent** blitting, which cuts
across the linear/planar split because both families have an opaque and a
transparent variant — which is exactly why the "linear vs planar" reading
failed here. The refusal to name it on this evidence was correct; the answer
needed a byte-for-byte diff of the paired loops, not more call-site reading.

## 27. `main` and the game loop — located (2026-08-23)

§6's last open box asked for `main`, the game loop and the save machinery. The
first two are now pinned; the save machinery is not, and is left open.

### Getting there

Borland's `C0` startup (`0x11520`, already named) makes ten calls. The one to
`main` is `lcall 0x64de:0x0048` at `0x1161C` — and that lands on file
`0x67C28`, which is **an `INT 3Fh` stub**. `main` is not in the resident image
at all; it lives in the overlay pool, which is why §6 could not find it before
§§19–20. It resolves to file **`0x88940`**.

*(A caution for anyone repeating this: my hand arithmetic for a sibling call
gave `0x1E28B` where `ovl_resolve.py` gives `0x1EC8B`. Use the tool.)*

### The three levels

```
main                     0x88940
    push [bp+8] / push [bp+6]        ; argv, argc
    call 0x88976                     ; init(argc, argv)
    call 0x88b3f                     ; the game loop
    push 1 / lcall 0x498:0x4d
    mov byte [0x12b1], 1
    lcall 0x68:0x1
    push 1 / call 0x88aff            ; shutdown
    xor ax,ax / retf

game_loop                0x88B3F
    do { ax = event_pump(0) } while (ax > 3)
    lcall 0x360:0x00f2 (9)           ; -> file 0x82B35

event_pump               0x1EC8B     ; thin wrapper, passes 0
event_pump_alternating   0x1EC3E
```

`main` is a five-line driver. The loop is `do … while (result > 3)`, so the
event pump's return value doubles as the quit signal: **anything ≤ 3 ends the
game**, and the exit path is a single call with argument 9.

### The event pump alternates between two sources

```
event_pump_alternating(u8 mode):        ; 0x1EC3E
  [0x979] = 1
  if ([0x291]) {
      [0x291] = 0
      r = queued_source()               ; 0x1EADD
      if (r < 0) r = event_poll_mods(mode)   ; 0x1EBA5, already named
  } else {
      [0x291] = 1
      r = event_poll_mods(mode)
      if (r < 0) r = queued_source()
  }
  return r
```

`[0x291]` is a **round-robin toggle**: each call prefers the source the last
call did not, and falls back to the other when the preferred one is empty
(returns negative). That is a fairness guarantee between two input streams —
neither can starve the other.

`queued_source` (`0x1EADD`) carries a **one-slot pushback** at `[0x26f]`,
sentinel `0xFFFF`: it fetches via `lcall 0x1b90:0xf0c`, and when that yields 0
it consumes the pushed-back value instead, flagging that fact in `[0x277]` and
recording the event in `[0x278]`.

### The save machinery — partly located (2026-08-23)

`player_record_save` (`0x970B5`) and `player_record_load` (`0x971B2`) handle
`player.dat`: a fixed **`0x37D`-byte** record at `[0x827a]`, written through
`lcall 0x538:0x39` and read back through `lcall 0x538:0x20`, with the caller
(`0x8D2D6`) building the path by `strcat`ing `"player.dat"` from DGROUP
`0x15c8`. The record is lightly obfuscated — `key = player[0] ^ 0xAA`.

That is the *character* half. The **level save** (`SAVE0\lev.ark`) is still not
located.

### Still open `main`'s init at
`0x88976` and the shutdown at `0x88AFF` are unread, as is `0x82B35` — the loop's
exit call — which is being named separately as part of overlay 108.

## 28. The trap system — dispatcher, workers, and a three-way cross-check (2026-08-23)

Overlay 166 holds a **25-case trap dispatcher** at `0xA1C36`:

```
bx = obj.word0 & 0x3f          ; trap item id - 0x180
cmp bx, 0x18
jmp word ptr cs:[bx + 0x1b2c]  ; table at file 0xA318C
```

and the case bodies call into overlay 110, which is therefore the
**world-mutation / player-effect worker library**.

### The cross-check

Trap item ids start at `0x180`, and `STRINGS.PAK` block 4 is indexed by item
id, so item `0x180` is string 384. That gives a three-way match — dispatcher
case, item id, and string — against the callee each case invokes:

| case | item | `STRINGS` block 4 | worker |
|---|---|---|---|
| 0 | `0x180` | `a_damage trap` | `0x84A0B` |
| 1 | `0x181` | `a_teleport trap` | `0x83FB2` |
| 4 | `0x184` | `a_special effects trap` | `0x84E43` |
| 5 | `0x185` | `a_change terrain trap` | `0x84527` |
| 6 | `0x186` | `a_spelltrap` | `0x84ACB` |

Verified against the decoded strings: block 4 runs `[384] a_damage trap`,
`[385] a_teleport trap`, `[386] a_arrow trap`, `[387] a_hack trap`,
`[388] a_special effects trap`, `[389] a_change terrain trap`,
`[390] a_spelltrap`, … through `[399] a_null trap` — sixteen trap types.

Each worker's behaviour independently matches its name: `0x83FB2` writes a
destination x/y/level triple and raises a request bit; `0x84527` rewrites tile
wall/floor textures and re-settles objects when the height changes; `0x84ACB`
stores a tile coordinate then casts. Three independent routes agreeing —
dispatcher order, string table, and what the code does.

The same workers are also called directly from the main game code, so overlay
110 is a **shared** effect library, not trap-only.

### Globals pinned along the way

| | |
|---|---|
| `[0x827A]` | `0x8294`, constant — the player/character struct in DGROUP |
| `[0x827E:0x8280]` | `&objects[1]`, the player object (0x1B-byte mobile records) |
| `[0x8282]` | current dungeon level |
| `[0x24E8]`/`[0x24EA]` | current tile x/y for area effects |
| `0x6B64` | the loaded **COMOBJ.DAT** table, 11 bytes per record |

`DATA/COMOBJ.DAT` is **5634 bytes = 2 + 512 × 11**, confirming both the stride
taken from `imul dx, 0xb` and a 512-entry count — a data-side check of a
code-side reading.

Mobile object word `+0x16` is packed tile coordinates: bits 10–15 = x,
bits 4–9 = y, used identically at four sites. That also confirms §22's earlier
note about the `+0xe1` biasing at `0x84166`: it is
`dir8_from_delta_abs(x − 0x1f, y − 0x1f)`, i.e. a quadrant relative to the
tile-grid centre (31, 31).

### Left unnamed

`0x885FB` is fully read — it clears a screen-tint slot, runs a 13-frame
animation, sets bit 2 of the player field at `+0x9A`, bumps the `+0x37C` change
counter — and two of its three callers invoke it immediately before a
maximum-magnitude hit on the player. "Player death sequence" fits every
observation, but nothing in the instructions says *death*, so it stays
unnamed. Trap cases 2, 3 and 7–24 have their table entries decoded but their
bodies unread.

## 29. Magic (overlay 156) and the game-variable store (overlay 166) (2026-08-23)

### Overlay 156 — the spell-effect module

Hub at `0x9CE4C`: a spell id indexes a **4-byte-per-entry table** at `V=0x270`
(file `0x66880`) — 69 contiguous entries, ids `0x00`–`0x44`, then zeros, with a
few scattered entries beyond. `type = rec[0] >> 3`, `param = rec[3]`, and ids
with `0xC0` set bypass the table entirely to become types 12–14 with a 6-bit
parameter. `0x9CEC9` then runs a **15-way** `jmp word ptr cs:[bx+0x321]`.

### The player record, pinned

| | |
|---|---|
| `[0x827A]` | `0x8294` constant — the player/character record in DGROUP |
| `[0x827E:0x8280]` | `&objects[1]` — the player's object (27-byte mobile records) |
| `[0x827C]` | the player's **critter-property** record: `0x493C + (item_id & 0x3f) * 0x30` |
| crit record `+4` | **max HP** — object `+8` is initialised from it |
| object `+8` | **current HP** |
| player `+0x37` / `+0x38` | **current / max mana** |

The "is a critter" test used throughout is `item_id` bits 6–8 == 1
(`and ax,0x1c0 / shr 6 / cmp 1`). DGROUP `0x493C` is therefore a 64-entry,
`0x30`-stride critter table.

### Overlay 166 — traps *and* the game-variable store

The trap half is §28. The other half is the **variable store**, and it is
pinned by an external caller rather than by inference: the conversation VM at
`0x7731D` range-checks a variable index with `cmp si, 0x3ff` and then calls
`game_var_write` (`0xA194D`, op = 2) and `game_var_read` (`0xA1B9E`). Their
shared address decoding gives the storage layout:

| index range | storage |
|---|---|
| `< 0x100` | word array at **player + 0xF9** |
| `0x100`–`0x17F` | bit `i & 3` of the dword at **player + 0x66 + 4*(i>>2)** |
| `0x180`–`0x18F` | bytes at **player + 0xE6** |
| `0x190`–`0x19F` | bytes at **player + 0x36D** |

`var_apply_op` (`0xA18F8`) is an 8-way ALU — add, sub, assign, and, or, xor,
shl, equality — so conversation scripts read and write persistent game state
through a single indexed accessor pair. That is the quest-flag mechanism.

### An unprompted cross-check

Two agents working different overlays independently reached the same two
functions. Earlier project work had already named `0xA169B`
(`fire_obj_trigger`) and `0xA18AC` (`dispatch_ctx_guard`); this pass derived
the same semantics from the other side and proposed `trigger_fire` and
`trap_run_with_actor`. The existing names are kept — the point is that two
independent derivations agree, and the second added detail the first lacked
(the 16-byte subtype table at DGROUP `0x863C`, and that `0xA18AC` stashes
**two** far pointers, `[0x8634]` and `[0x8638]` — the trap and its actor).

### Left as facts, not names

`obj+0x1a` in `npc_foreach_by_id1a` (`0x9E286`): the behaviour is exact — byte
equality against a caller-supplied id — and the callers are conversation code
passing conv-variable values and the literals `0x8B`–`0x8F`/`0xA8`, which is
consistent with an NPC identity byte. No instruction proves that reading, so
the name says `id1a`, not `whoami`.

## 30. `[0xdc4]` and `[0xdc5]` — answered (2026-08-23)

§22 found the two flags, §23 established `[0xdc5]` is a boolean set per-draw,
and §26 narrowed it and then explicitly refused to name it: *"It is not
uniformly linear vs planar… Naming it would be guessing."* That refusal was
right — the tempting reading was wrong — and the answer needed a different kind
of evidence.

### `[0xdc5]` = transparent blit

The twelve inner loops pair up, and the two members of a pair are otherwise
**byte-for-byte identical**. Disassembling `0x89C2` (`dc5 == 0`) against
`0x8AB7` (`dc5 != 0`) and diffing, the only difference in the whole routine is
the pixel loop:

```
0x89C2:   movsb                        ; opaque
0x8AB7:   xor ah, ah
          lodsb / cmp al, ah / je skip / stosb    ; skip colour 0
```

Every other instruction matches, modulo branch targets. The linear pair says
the same thing more plainly — `0x3D79` is `lodsb / or al, al / je skip / stosb`
against `0x3D48`'s `rep movsb`.

So `[0xdc5]` selects **transparent (colour-0-skipping) blitting**, and it cuts
across the linear/planar split because *both* families have an opaque and a
transparent variant. That is exactly why §26's "linear vs planar" reading
failed.

### `[0xdc4]` = clipping enable

In `gfx_blit_8arg`:

```
0x5900   cmp byte ptr [0xdc4], 0
0x5905   jne 0x5909
0x5907   jmp 0x595e            ; dc4 == 0 -> skip clipping entirely
0x590E   sub si, word ptr [0x3df4]   ; otherwise clamp against the clip window
```

and the four words it clips against are exactly what the public entry
`0x18:0x4ac1` (file `0x8111`) writes — that entry stores its four arguments and
calls through to `0x6837`, which does `mov di, 0x3df4` and four `movsw`. **So
`0x18:0x4ac1` is "set clip rectangle" and `[0xdc4]` is the switch for honouring
it.**

### The caller that settles the intent

`0x83150`, the `CUTS\lbackNNN.byt` loader, brackets its work:

```
lcall 0x18:0x4a7f (x, y)          ; VGA hardware pan (waits on 0x3DA bit 3,
                                  ;  writes CRTC 0x0C/0x0D and ATC 0x33)
dc4 = 1 ; set clip rect (0, 0xc7, di, si)   ; narrowed to the visible strip
dc4 = 0 ; blit the 64000-byte full-screen background
```

Clipping is enabled only while the window is narrowed for a **panned or partial
background**, and switched off for the full-screen 320×200 blit that covers
everything anyway. A correctness-plus-speed bracket, not a mode change.

### For the port

Both flags are now port-relevant and cited: a Falcon implementation needs an
opaque and a colour-0-transparent span loop, and a clip-rect that can be
bypassed. The twelve loops collapse to roughly *two* behaviours × target ×
alignment, not twelve independent blitters.

## 31. Overlay 93 (`.ARK` container layer) and overlay 108 (cutscenes) (2026-08-25)

**Overlay 93** is the `.ARK` block-file layer — the code side of a format this
project had only ever read from the outside, and reading it is what caught
`ark.py`'s off-by-one slot (`data-formats.md`). One archive is open at a time,
in a struct at `V=0x258`: `+0` fd, `+2` slot count, `+4` the header `u32`,
`+8` the path. The four index tables are read into far buffers at DGROUP
`0x994`/`0x998`/`0x99c`/`0x9a0`.

`ark_write_slot` (`0x720C1`) is where the flag semantics come from: bit 0
requests compression, bit 1 records that the record *is* compressed, bit 2
marks it padded so it can grow in place — with `pad = (15 * len) / 100`,
computed through the Borland `LXMUL@`/`LDIV` helpers. Without bit 2, growing a
record rewrites the entire archive through `_arc.tmp` in `0x2000`-byte chunks,
decrementing every later offset and rewriting the index. Short writes go to
`fatal_error(0x4002)` — the `E002` §21 found players actually see.

**Overlay 108** is the cutscene player and its streamed speech. Filenames are
built with **octal** ASCII digits (`shr 6 / and 7 / add 0x30`, three times):
`CUTS\csXXX.nXX`, `CUTS\lbackxxx.byt`, and `SOUND\BSPnnn.VOC`. Frame data is
paged through **EMS** (`INT 67h`, `AX=5000h` map-multiple-pages) with the handle
at DGROUP `0x22C0` and the page frame at `0x22BE`.

The LPF payload question is now closed for the connected intro path. The
0x100..0x4ff block is 256 `B,G,R,0` palette entries; the directory at 0x500
maps records into 0x10000-byte pages beginning at 0x0b00; each record is a
delta stream against a persistent 320×200 indexed framebuffer. Positive signed
bytes are literal dumps, zero is a short run, negative commands are short
skips or long skip/run/dump operations, and a zero long operand ends the
record. Empty records repeat the previous frame. `analysis/data-formats.md`
and `browser/uw2-cutscene.js` contain the complete recovered rule and retain
the four known whole-page accounting anomalies rather than masking them.

The function records for the milestone are in
`analysis/functions/cutscene-intro.md`: `0x811fc` (`cutscene_chunk_filename`),
`0x828e3` (`cutscene_run`), `0x82b35` (`cutscene_play`), and `0x83150`
(`cutscene_load_lback`). The browser counterpart is a function-level
implementation, not an instruction translator: it replaces EMS/file handles
with the virtual DOS filesystem and replaces VGA memory with a canonical
indexed surface plus an explicit Falcon-oriented RGB565 presentation path.

`cutscene_play` (`0x82B35`) is **`game_loop`'s exit call** (§27): the loop ends
with `lcall 0x360:0x00f2 (9)`, which is this function with cutscene id 9.

The browser milestone deliberately stops at a verified canvas display slice.
The runtime uses explicit paths for the four connected source files; it does
not retain N00 argument parsing, octal filename helpers, sound, or cursor and
character viewers. Text, speech, command side effects, DOS timing, and the ID-9
transition remain `Unproven` until their DOS behavior is captured. The checked-in
analysis fixtures are evidence for the indexed frame boundary only; the page
does not run a fixture gate or claim that the whole overlay has been ported.

### Not determined, and worth recording

The `u32` at `.ARK` header offset `0x02` is read into the open-archive struct
and **never read back anywhere in the overlay**. It is 0 in all four shipped
files. Ruled out: not the slot count (that is the `u16` at 0), not
`offsets[0]` (the game indexes offsets at `6 + 4*slot`).

## 32. The boot sequence — `main_init`'s 45 calls, in order (2026-08-23)

§27 located `main` and its init at `0x88976` but did not read it. Resolving all
45 calls it makes — through `ovl_resolve.py` and `symbols.py` — gives the
subsystem boot order, which is what a port has to reproduce and cannot infer.

| # | call | resolves to | |
|---|---|---|---|
| 1–4 | `0x30:…` | `0x13078`, `0x13087`, `0x12512`, `0x122F6` | C runtime |
| 5 | `0x160:0x0f` | `0x36FFF` | |
| **6** | `0x538:0x5c` | **`check_data_dirs`** | verifies `data`/`crit`/`cuts` exist |
| **7** | `0x538:0x43` | **`check_8_file_handles`** | opens `a.tmp`…`h.tmp` |
| 8 | `0x148:0x0d` | `0x3564D` | |
| **9** | `0x400:0x2a` | **`level_buf_alloc`** | |
| 10–11 | | `0x1D943`, `0x835B0` | |
| **12** | near | **`uwhome_env_lookup`** | reads `UWHOME`, defaults to `"."` |
| 13–15 | | `0x20BD9`, `0x20B5A`, `0x82C17` | |
| **16** | `0x538:0x61` | **`have_free_stack_and_heap`** | → `fatal_error(0x1004)` = **B004** |
| 17–18 | | `0x20BA6`, then the heap check again | |
| 19–20 | | `0x8A1CB`, `0x8ABE0` | → `fatal_error(0x3003)` = **D003** |
| 22 | `0x4b0:0x20` | `0x9A5A0` | |
| 23–24 | | `0x20FCE`, `0x32EC` | |
| **25** | `0x3b8:0x39` | **`gfx_init`** | |
| 28 | `0x80:0x04` | `0x1E704` | input |
| 30 | `0x430:0x25` | `0x92C60` | |
| 32 | `0x460:0x20` | `0x96DC0` | |
| **34** | `0x478:0x20` | `0x97D30` | sets `[0x827a]`/`[0x827c]` — the **player record** (§29) |
| **36** | near | **`startup_paths_and_hotkeys_init`** | `argv[1]`, `"DATA\"`, `getcurdir` into `[0x5d9e]` |
| **41** | near | **`save0_seed_from_data`** | copies `DATA\{lev,scd}.ark` into `SAVE0\` |
| 37–39 | | `0x9AF21`, `0x7BCE0`, `0x99940` | |
| **42** | `0x2f8:0x101` | `0x74C13` | conversation globals (`babglobs.dat`, §25) |
| **44** | `0x3b0:0x7a` | **`gfx_reset_clip_fullscreen`** | |
| **45** | `0x3b0:0x2f` | **`palette_load_and_activate`** | last thing before returning |

### The error convention

Six steps are followed by `fatal_error`. Two push a literal — `0x1004` (B004)
after the stack/heap check, `0x3003` (D003) after `0x8ABE0` — and four pass a
**computed** value:

```
lcall 0x3b8, 0x39        ; gfx_init
mov si, ax
or ax, ax
je  skip
push si
lcall 0x390, 0x25        ; fatal_error(ax)
```

So **init functions return a `fatal_error` code in `AX`, zero meaning success**,
and `main_init` passes it straight through. That is a uniform convention across
the boot path, and it means the player-visible codes from §21 map one-to-one
onto init steps.

### For the port

The order is the deliverable: environment and filesystem checks first
(`UWHOME`, the three data directories, eight free file handles, stack and heap
headroom), then the level buffer, then graphics, input, the player record, the
conversation globals, and finally the clip window and palette. Fourteen of the
45 are named; the rest are recorded as addresses so the sequence is complete
even where the individual step is not yet identified.

The **teardown** (`main_shutdown`, `0x88AFF`) is nine far calls and, notably,
**not the reverse of boot order**: video/BIOS/DOS machine state comes off first
— BIOS video mode, the INT 24h vector, the EGA palette and DAC, and a DOS clock
resync from the CMOS RTC — so a crash after that point still leaves a usable
console. Then cwd, heap arrays, EMS, sound, `strings.pak`, and the `SAVE0` wipe
last.

### `SAVE0` is a scratch directory, not a save slot — ✗ corrected (2026-08-23)

An earlier version of this section said `lev.ark` and `scd.ark` are
"registered with a save-dir-first, `DATA\` fallback pair" and concluded that
"§6's save box is structurally answered". **Both claims were wrong**, and the
error was mine: I read the pushed arguments in *push* order. cdecl pushes
right-to-left, so the last push is the first argument.

```
push 0x1329          ; "lev.ark"      -> arg3
push 0x5d0e          ; <savedir>      -> arg2
push 0x12e2          ; "DATA\"        -> arg1
lcall 0x4a8:0x2a     ; = 0x9A02E
```

and `0x9A02E` builds `arg1 + arg3` and `arg2 + arg3` (`strcpy` then `strcat`,
both verified) and then **copies the first file to the second** — `open(src)`,
`open(dst)`, a read/write loop. It is a file copy, not a registry.

So what actually happens is:

```
boot  step 41  save0_seed_from_data 0x892A8
                   file_copy("DATA\", <UWHOME>\SAVE0\, "lev.ark")
                   file_copy("DATA\", <UWHOME>\SAVE0\, "scd.ark")

exit  step 9   dir_delete_all_files 0x99FAB
                   delete every file in <UWHOME>\SAVE0\
```

**`<UWHOME>\SAVE0\` is a scratch working directory.** It is seeded from the
shipped `DATA\` copies at startup and **wiped at shutdown**. The game mutates
the working copy during play; nothing there survives the process.

That means §6's save box is **not** answered by this. ✓ **It is answered in
§33**: the persistent saves are `SAVE1`–`SAVE4`, and overlay 149 is the
save/restore module. The path traced above is the live working set — a
different thing, and a real prerequisite for understanding the save, but not
the save itself.

`uwhome_env_lookup` (`0x89179`) does build the directory itself: `strcpy` of
`UWHOME` (or `"."`) into DGROUP `0x5d0e`, then `strcat` of `"\SAVE0\"` at
`0x89296`, in the same function. So `[0x5d0e]` is the working directory, not
bare `UWHOME` — which also means `open_prefixed_file` (`0xA4FC1`) resolves its
non-`DATA\` prefix into `SAVE0`.

## 33. The save system, properly — and a refuted reading — RESOLVED (2026-08-23)

§32's addendum found `SAVE0` and got it wrong twice: first as a "fallback
registry", then, after correcting that, as the whole answer to §6's save box.
It was neither. **Overlay 149 is the save/restore module**, and with it §6's
last box is genuinely closed.

### The layout

```
<UWHOME>\SAVE0\      working directory -- seeded from DATA\ at boot, wiped at exit
<UWHOME>\SAVE1..4\   the four save slots, each with a `desc` text file
```

The slot labels are `"I- "`, `"II- "`, `"III- "`, `"IV- "` (DGROUP `0x1A4E`,
`0x1A52`, `0x1A57`, `0x1A5D`), reached through a 4-entry pointer table at
`0x1A30` — verified: the table contains exactly those four addresses. A slot
with no `desc` file displays `"<not used yet>"` (`0x1A3F`).

```
savegame_save(slot, descbuf)          0x99E24
    textwin_read_line (max 0x1e; ESC returns 2)
    write_whole_file(description -> <slot>\desc)
    mkdir <slot>; dir_delete_all_files(<slot>)
    level_save()                      ; into the working directory
    dir_copy_all_files(working -> <slot>)

savegame_restore(slot)                0x99D5B
    dir_delete_all_files(working)
    dir_copy_all_files(<slot> -> working)
    player_dat_read(working)
    level_load()
    level_transition_hook(level, 3)   ; phase 3 = after a restore
```

So a save is *a directory copy*, and the on-disk format is simply the `.ARK`
container (§31) plus `player.dat` (overlay 142) plus a one-line `desc`. There
is no bespoke save format anywhere — which is why looking for one found
nothing.

`savedir_prepare_and_check_space` (`0x99940`) is where the
`"Not enough disk space for save game."` string earns its place: `getdfree`
(INT 21h AH=36h), then `avail * bytes_per_sector * sectors_per_cluster >=
0x4B0`. The threshold is recorded as the literal it is; nothing supports
reading a unit other than bytes onto it.

### `0x885FB` is not a death sequence — the refusal was right, the reading was wrong

§28 left `0x885FB` unnamed because "player death sequence" fit every
observation but no instruction said *death*. Holding that line was correct: the
reading is **refuted**, and the decisive evidence is a caller.

At `0x9A3E1`, inside `level_transition_hook` on the *leaving* phase, it is
called as `0x885FB(1)` — with no damage call anywhere near it. **You do not die
by walking off a level.**

What it actually is: the stock plot-flag idiom. `and dx, 0xfffb` / `add dx, 4` /
`adc ax, 0` is a one-bit write of bit 2 into the dword at player `+0x9A`,
followed by `inc byte ptr [bx + 0x37c]`. And `+0x37C` is not a free-standing
counter — `0x9AA96` turns out to be the **NPC-schedule updater**, looping
`i = 0..0x0F` over the 16 bytes at player `+0x36D`, so `+0x37C` is schedule
counter **15**. The same flag-set-plus-reschedule pair occurs at all eight
`inc byte [bx+0x37c]` sites in the binary.

The two callers that *looked* like death guard on
`bit2(+0x96) && !bit2(+0x9A)` and issue the `0xFF`-magnitude hit **themselves**,
after calling `0x885FB`. The hit was the caller's instruction, not this
function's — which is exactly the kind of adjacency that made the death reading
so tempting.

Named structurally as `plotflag_9a_bit2_set_and_reschedule`. **What the flag
means in the fiction is still not determined**; the arming branch is inside
dispatcher `0x84F4C` and the relevant message strings live in the external
string blocks, not the EXE.

## 34. The binary names its own functions — 50 conversation intrinsics (2026-08-23)

The best naming evidence in this project so far is not inference at all. At
`0x7C38C` there is a **registration table**: a straight run of

```
push <V> ; push <offset> ; push <name_ptr> ; lcall 0x2f8:0xb1
```

where `name_ptr` is a DGROUP string. Decoding all of it and resolving each
`V:offset` through `ovl_resolve.py` yields **50 conversation intrinsics named by
the game itself**, with their script-visible names:

`babl_menu` · `babl_fmenu` · `babl_ask` · `babl_hack` · `say` · `respond` ·
`print` · `pause` · `get_quest` · `set_quest` · `sex` · `show_inv` ·
`give_to_npc` · `give_ptr_npc` · `find_inv` · `take_from_npc` ·
`take_id_from_npc` · `identify_inv` · `do_inv_create` · `do_inv_delete` ·
`check_inv_quality` · `set_inv_quality` · `count_inv` · `do_offer` ·
`do_demand` · `do_decline` · `do_judgement` · `end_barter` ·
`setup_to_barter` · `set_likes_dislikes` · `give_all_stuff` · `find_barter` ·
`find_barter_total` · `gronk_door` · `set_sequence` · `set_attitude` ·
`set_race_attitude` · `take_from_npc_inv` · `add_to_npc_inv` · `place_object` ·
`transform_talker` · `remove_talker` · `teleport_player` · `teleport_talker` ·
`switch_pic` · `x_skills` · `x_traps` · `x_obj_stuff` · `x_obj_pos` ·
`x_clock` · `x_exp`

These are authoritative — the strings are what UW2's conversation compiler
resolved against. §11's decode of the conversation VM now has named entry
points for its entire intrinsic surface.

The table also identifies its overlays: **overlay 103** is the VM-argument
marshalling layer, **overlay 97** the barter/trade implementation behind
`do_offer`, `do_demand`, `setup_to_barter`, `give_all_stuff` and the rest.

## 35. The crime and ownership system (2026-08-23)

Overlay 107 is the **NPC social and placement** module, and the most complete
mechanism in it is the one behind `area_effect_at_object_tile`'s 15×15 sweep
(§28) — which turns out to be **16×16**, because `objects_in_rect_foreach`'s
loop bound is inclusive (`cmp dx, si / jl`), so `x0 = tx-7, w = 15` covers
`tx-7 … tx+8`. With the fifth parameter zero the callback fires **only for
critters** (`and ax,0x1c0 == 0x40`).

`crime_alert_owner_race` (`0x7F770`):

1. Take the owner code from the argument, or from `obj+6` bits 0–5 — but only
   when the COMOBJ record's byte 7 has bit 7 set ("has a meaningful owner").
   If there is no owner code, do nothing at all.
2. Publish the acting object in `[0x1039]`/`[0x103b]` and the owner code in
   `[0x103d]`.
3. Sweep the 16×16 tile square around the player.
4. **Erase the owner code** from the object, and — if it is a container
   (item id `0x80`–`0x8F`) — from every item in its tree.

The callback `crime_witness_react_cb` (`0x7F52B`), per critter:

- **race filter**: critter-props `+9` must equal the owner code's low 5 bits —
  only creatures *of the owner's own race* care;
- **range**: `dx² + dy²` against a per-creature notice radius, `props[+0x1e] >> 4`;
- **line of sight**: a real 3-D LOS call;
- **effect**: attitude, in `obj+0xd` bits 14–15, drops **one step** toward hostile;
- **message**: block-1 string `0xF0 + new_attitude`, decoded from `STRINGS.PAK`:

| 240 | `" is angered by your action."` |
|---|---|
| 241 | `" is annoyed by your action."` |
| 242 | `" notes your action."` |

So: **take or destroy something owned, and every creature of that race who can
see you gets one step angrier and says so — once.** The owner code is erased on
the way out, so an object can only ever incriminate you a single time.

Its callers confirm the reading: the three sites that reach it all first compute
`obj+6 & 0x3f` from the object being acted on, and one of them holds the strings
`"The "` / `"You empty the "`.

The persistence side is in the same overlay: `vendetta_state_save` / `_load`
(`0x7F49A` / `0x7F466`) shuttle this state through `player+0x308` on save and
restore, and `reset_vendetta_state` clears it on a level switch.

## 36. A second self-naming table — the VM's variable bindings (2026-08-23)

§34's registration table suggested a general technique: sweep DGROUP for
identifier-shaped strings and see which are *not* already accounted for. Of 126
such strings, 49 are §34's intrinsics; the remainder cluster into two more
groups.

`compare` `random` `plural` `contains` `append` `copy` `find` `length` are the
conversation **builtins**, bound at `0x74F5B`–`0x74FD2`.

The larger group — `npc_whoami` `npc_hunger` `npc_health` `npc_hp` `npc_arms`
`npc_power` `npc_goal` `npc_gtarg` `npc_talkedto` `npc_level` `npc_xhome`
`npc_yhome` `npc_name` `npc_attitude` `play_hunger` `play_health` `play_hp`
`play_arms` `play_power` `play_mana` `play_level` `play_sex` `play_poison`
`play_drawn` `play_name` `dungeon_level` `game_time` `game_mins` `game_days`
`new_player_exp` — are the VM's **imported variables**, and they are bound in a
single function, `conv_publish_vars` (`0x7DFA0`):

```
<compute the value into [bp-2]>
push 1                    ; element count
lea ax, [bp-2] / push ax  ; source
push <name_ptr>
lcall 0x2f8:0x98          ; = conv_import_write_by_name (0x7664D)
```

with `conv_readback_vars` (`0x7E42F`) as its counterpart through
`conv_import_read_by_name`.

### Why this matters: the game names its own record fields

Each binding says what a field *is*, in the game's own vocabulary. Several
confirm readings this project had reached by inference, from unrelated
directions:

| VM name | field | previously |
|---|---|---|
| `npc_goal` / `npc_gtarg` | `obj+0x0B` | §35 read `obj+0xb` bits 0–3 = goal, 4–11 = target |
| `npc_attitude` | `obj+0x0D` | §35 found attitude in `obj+0xd` bits 14–15 |
| `play_mana` | `player+0x37` | §29 derived current mana at `+0x37` |
| `play_level` | `player+0x3D` | overlay 154 |
| `play_hunger` | `player+0x39` | `player_food_add` |
| `play_poison` | `player+0x60` | `trap_damage_or_poison` rewrites `+0x60` bits 1–4 |

And one **closes an explicitly-open question**. §29 recorded of `0x9E286`:

> *"the name says `id1a`, not `whoami`… I have no instruction that proves that
> reading."*

`conv_publish_vars` binds `obj+0x1A` to the string **`npc_whoami`**. The
agent's caution was right and the answer was sitting in a table three overlays
away. Renamed to `npc_foreach_by_whoami`.

### The technique, generalised

Looking for places where a binary *names itself* — registration tables, symbol
arrays, script-facing bindings — has now produced 50 intrinsic names and ~30
field identifications in two passes, against roughly ten names per agent-hour
by reading code. Worth trying before reading, not after.
