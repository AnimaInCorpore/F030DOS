# Reassembly ratchet — P4.2 harness (also closes P1.4's stub sweep)

**Status: the whole EXE reassembles byte-identically — 99.9 % of it emitted from
source, 0.1 % (1,154 B) still copied.**

**But "emitted from source" is not "understood."** The builder prints both, and
the second number is the one that matters:

| region | emitted | quality of what is emitted |
|---|---|---|
| 16-bit stub | rebuilt | 83.5 % real instructions (net of the data guard) |
| obj1 code | rebuilt | 93.2 % real instructions (net of the data guard) |
| fixup tables | generated | 100 % — all 27,438 records round-trip |
| **obj2 data** | rebuilt | **58.8 % typed**; 41.2 % is raw `db` |
| MZ + LE headers, import table | copied | — |

```
python3 work/build_ztie.py          # -> work/build/Z_TIE__.EXE, 1,031,495 B
```

| region | file range | bytes | source |
|---|---|---|---|
| MZ header | `0x000000..0x000060` | 96 | copied |
| **16-bit stub** | `0x000060..0x002A4E` | **10,734** | **rebuilt** (`work/ratchet/stub.bin`) |
| pad to LE header | `0x002A4E..0x002A50` | 2 | copied |
| LE hdr + obj table | `0x002A50..0x002E4C` | 1,020 | copied |
| **fixup page table** | `0x002E4C..0x00314C` | **768** | **generated** (`work/build_fixups.py`) |
| **fixup records** | `0x00314C..0x03D7DC` | **239,248** | **generated** (`work/build_fixups.py`) |
| import table + pad | `0x03D7DC..0x03D800` | 36 | copied |
| **obj1 pages (code)** | `0x03D800..0x0E8800` | **700,416** | **rebuilt** (`work/ratchet32/stub.bin`) |
| **obj2 pages (data)** | `0x0E8800..0x0FBD47` | **79,175** | **rebuilt** (`work/obj2/obj2.bin`, `type_obj2.py --emit`) |

The builder prints that table every run, and labels each region REBUILT,
GENERATED or COPIED, because **"byte-identical" alone means nothing here** —
a build made entirely of copied regions passes trivially. The numbers that
matter are in the quality table at the top: how much of the emitted source
is proven instructions (stub 83.5 %, obj1 93.2 %) or typed data (obj2
58.8 %). *(Re-verified byte-identical on the Windows host 2026-08-26.)*

(Note the obj2 file-backed region is **79,175 B**, not the 287,856 B of
`work/ghidra/z_tie_obj2.raw` — that slice is zero-extended to the object's
virtual size for Ghidra. Do not feed it to the builder.)

**Both code units reassemble byte-exactly.**

| unit | size | gross | **net of data guard** | passes |
|---|---|---|---|---|
| 16-bit MZ stub | 10,734 B | 84.5 % | **83.5 %** | 8 |
| **32-bit code object (obj1)** | **700,416 B** | 93.7 % | **93.2 %** | 8 |

### Correction (2026-08-22): the earlier scores were inflated

~~"MZ stub 86.3 %, obj1 93.8 %"~~ counted **string literals as real
instructions**. Text decodes into x86 that re-encodes identically, so it sails
through the ratchet — byte-exactness cannot catch it, because the bytes *are*
right. Measured on the stub: of 666 B in printable runs ≥12 chars, **342 B
(51 %) were being scored as code**, including the whole 144-byte
`WATCOM C Run-Time system code` banner, `Not enough memory`, `Stack Overflow!`
and 24 others.

Worse, the doc claimed those bytes were "never reached by descent" — they were
reached, by the **orphan scan** seeding the gap the entry jump skips over
(`0x30E` is `jmp +0xCB`, jumping *over* the banner).

`data_guard()` now flags NUL-terminated printable runs ≥8 **and** any printable
block ≥16 (the banner has no NUL in it, so a NUL-only rule missed it entirely),
plus zero runs ≥8. Guarded offsets are excluded from orphan seeding and
subtracted from the score. String bytes scored as code dropped from 342 B to
138 B on the stub. The remaining 138 B are runs shorter than the ≥16 threshold —
**the net figure is still slightly optimistic**, and is reported as such rather
than tuned until it looks clean.

obj1 barely moves on the *string* guard (93.8 → 93.7 %) because it is nearly
pure code: only 1,390 B of 700 KB. The strings live in obj2.

### Second round: function-pointer tables (2026-08-22)

A sharper test than string-scanning — check the ratchet against ground truth
already established elsewhere. The four FILM/typeCode dispatch tables from
`LFD.md` §6b are function-pointer arrays, i.e. **data**, and **all 116 B of them
were being scored as code**. The string guard cannot see them: they are neither
text nor zeros.

`pointer_table_guard()` fixes this **from the binary, not by heuristic**: a run
of LE fixup *source* sites in obj1 spaced exactly 4 bytes apart is an array of
relocatable dwords — a jump or dispatch table. That finds **4,312 B**, of which
**3,342 B were being counted as instructions**, and all four known tables are now
guarded:

```
obj1 NET  93.7 % -> 93.2 %
```

Still byte-identical, and `nasm` on the emitted `.asm` standalone still
reproduces the original exactly.

### Known remaining weaknesses

- **2,074 overlapping decoded bytes in obj1** (101 in the stub): more than one
  decoding claims the same byte, which means some seed is wrong. It does not
  affect output — `emit()` walks offsets in order, takes the instruction that
  *starts* at each, and the ratchet proves the bytes — but the instruction set
  contains contradictions and the score counts one of them.
- **138 B of short printable runs** in the stub are still decoded as code
  (below the ≥16 threshold).
- So **93.2 % / 83.5 % remain upper bounds**, not exact figures.

Both rebuilds are verified byte-identical with `cmp` against the original — for
obj1, `cmp work/ghidra/z_tie_obj1.raw work/ratchet32/stub.bin`.

```
python3 work/ratchet16.py                       # stub  -> work/ratchet/
python3 work/ratchet16.py --unit obj1 \
        --out work/ratchet32 --orphan-rounds 5  # obj1  -> work/ratchet32/
```

`--unit obj1` seeds from the capstone sweep (`analysis/32bit/functable_v2.txt`)
plus Ghidra's function starts — 7,538 seeds, no single entry point — and
`--range LO HI` restricts it to a slice, e.g. one module span. obj1 scores
*higher* than the stub precisely because those seeds cover it so well: only
**1,544 B of 700 KB is never reached**.

## obj1: where the 6.2 % goes

43,994 B demoted across 18,148 instructions, dominated by branches — `je` 7,816,
`jmp` 6,242, `jne` 6,196, `jge` 2,170, `jle` 1,988, `jl` 1,708 — plus `mov`
7,377 and `call` 2,415. The branch share is the drift cascade (below) that a
batch size of 1 would mostly remove, at a cost of thousands of passes.

`mov` at 7,377 B is the largest non-branch class and is mostly a form **NASM
will not produce**: Watcom emits `mov eax, eax` as `8B C0` (direction bit set)
where NASM always assembles `89 C0`. No operand syntax forces it; UW1 hit the
same class (`F030Underworld/analysis/reassembly.md` §5). These have to stay `db`
or be emitted as raw bytes.

## Original context — the 16-bit stub

```
python3 work/ratchet16.py [--out work/ratchet]     # ~2.5 s, 8 passes
```

Output: `work/ratchet/stub.asm` (131 KB), `stub.bin` (10,734 B, **byte-identical
to the original**), `stub.lst`.

## Why byte-exactness is not the achievement

Coverage percentages do not test a disassembly — a wrong instruction length
silently corrupts every byte after it and still looks like a listing. The
ratchet emits assembler, assembles it, compares **per instruction at each line's
intended offset**, demotes every mismatch to `db`, and repeats. That loop always
terminates at byte-exact, so byte-exactness is the **invariant**. The number that
means something is the score: bytes emitted as real instructions over total.

Independent check, not just the harness's own word:

```
cmp <(python3 -c "…load_stub()…") work/ratchet/stub.bin   # identical
```

### The unit

MZ stub of `Z_TIE__.EXE`: file `0x60..0x2A4E`, **10,734 B**
(`(pages-1)*512 + lastpage - header`, all from the MZ header), entry `CS:IP =
0000:030E` → image offset `0x30E`, 6 relocations (all segment fields, none a
code seed).

### Score, and where the rest went

*(Pre-guard snapshot — the data guard re-scored the stub to 84.5 % gross /
**83.5 % net**; the §Correction above explains the delta. Kept because the
reachability story and the demotion classes still hold.)*

| | bytes | |
|---|---|---|
| real instructions | **9,264** | 86.3 % |
| demoted to `db` | 596 | 310 instructions that would not re-encode |
| never reached by descent | 975 | data — the `WATCOM C Run-Time system` banner at `0x311`, strings, tables |
| padding/zero tail | *(inside the above)* | |

Reachability came in two stages: **5,953 B from the entry** by seeded recursive
descent, then **+3,806 B from an orphan scan** (seed the start of each uncovered
gap, accept the descent only if it ends on a real tail instruction — `ret`,
`jmp`, `iret` or `int`). ~250 rounds, still 2.5 s.

Demotions are now `mov` 100, `sub` 52, `cmp` 44, `je` 40, `add` 32, `or` 28,
`outsb` 22, `jb` 22 — encoding-width disagreements and a few probable
data-as-code decodes. `call`, which dominated at 372 B, is gone entirely (below).

### Getting the stub from 48.4 % to 86.3 % (pre-guard gross)

Four changes, in the order they paid:

1. **Orphan-gap scan** (+3,806 B reachable) — seed the start of each uncovered
   region, accept the descent only if it ends on a real tail instruction.
2. **Indirect `call`/`jmp` forms** emitted directly instead of rejected.
3. **Forced operand widths** — retry a mismatch as `strict byte` / `strict word`
   before demoting, batch-probed in one NASM run since those forms are
   position-independent. Rescued 32 instructions.
4. **Demote position-dependent mismatches one at a time** — worth ~4 points on
   its own, and the most important of the four.

That last one is METHOD.md §2.4's trap in a new guise. A single instruction
whose re-encoding is one byte short shifts every later label, so *all* its
downstream branches read as mismatches. Demoting them together throws away
hundreds of correct instructions to fix one. Non-branch mismatches are
position-independent and genuinely wrong, so they can be demoted together;
branch mismatches must be demoted **earliest-first, one per pass**, and the rest
re-tested once the drift ahead of them is gone. Doing this dropped `call` from
372 B of losses to zero.

The drift's own root cause here: instructions carrying a **`2E` CS segment
prefix** that capstone does not render in `op_str`, e.g. `2e 0d 0a 2a` printed
as `or ax, 0x2a0a`. Emitting that loses the prefix byte and shifts everything
after it.

## Findings worth carrying across projects

**`55 8B EC` prologue anchoring does not work on this target.** It occurs
**exactly once** in the whole stub — Watcom's 16-bit codegen barely uses `bp`
frames. The orphan-gap scan is what unlocked the +3,806 B; prologue patterns
that work elsewhere found nothing here.

**`nasm -O0` made the score WORSE here: 81.6 % → 75.6 %.** UW1's harness uses
`-O0` so the assembler cannot re-optimise a size it chose (its
`analysis/reassembly.md` §7), but that assumes an emitter that forces sizes with
explicit `strict` forms. This emitter instead *takes* the size NASM picks, and
NASM's default choices happen to match Watcom's more often than `-O0`'s do.
The lesson transfers only together with explicit size forcing.

## Also settles part of P1.4

The stub sweep P1.4 asked for is done as a side effect: **83.5 % net**
(84.5 % gross) of it is disassembled and proven by re-encoding. Its **1,881-byte region at `0x2295` is
an `int n; ret` thunk table**, not padding — `cd 00 c3 cd 01 c3 cd 02 …`. (An
earlier read of that region as "all zeros" was a misread of a printable-ASCII
dump; the dots were non-printable bytes, not NULs.)

What P1.4 still wants: what the stub *does* when the file runs without an
extender, and the `TIE.EXE` re-sweep as one 16-bit program.

### Bugs this exposed, worth remembering

capstone prints **small branch targets in decimal** (`0`, `8`), not hex. A
target regex of `0x[0-9a-f]+` therefore misses them, and if the fallback path
emits the operand as an absolute immediate the result assembles cleanly and
silently shifts every later label. It cost a debugging round here.

### Scaling to 700 KB — two O(n²) bugs

Neither showed up on a 10 KB unit; both made the full object look intractable
(two runs killed after 10+ minutes with no output):

- **`set(insns)` rebuilt per instruction.** `to_nasm` takes the label set, and
  two callers passed `set(insns)` *inside* a loop over all instructions —
  200k × building a 200k-element set. Hoisting it to one `labelset` per pass is
  the difference between "never finishes" and 70 s.
- **A fresh capstone `Cs` per `descend()` call**, i.e. per orphan seed per round.

Also: `--orphan-rounds` now bounds the orphan scan. At 700 KB with 7,538 seeds
its marginal value is small, and it was the first suspect before the real
culprits turned up by reading rather than waiting.

## obj2 — typed, not just emitted

`work/type_obj2.py` classifies all 79,175 file-backed bytes from evidence
already in hand, and `--emit` writes NASM that re-assembles to them exactly:

| | bytes | |
|---|---|---|
| pointer | 1,708 | 2.2 % — a 32-bit fixup **source** site; the LE table says so |
| string | 16,655 | 21.0 % |
| zero | 28,176 | 35.6 % |
| **unknown** | **32,636** | **41.2 % — emitted as raw `db`, not guessed at** |

The largest unknown runs are listed by the tool so the next pass knows where to
look; several have obvious shape without an obvious meaning — a 3,086 B array of
`01 00`, a 1,140 B run of powers of two, a 790 B ramp whose u16 deltas are a
near-constant `0x16D`/`0x16E`. **None of them is named here.**

One repeat of a lesson: the string rule first required NUL termination and
missed a 921 B message block at `obj2+0x4B` starting `Some files may b…` —
exactly how the ratchet's guard first missed the WATCOM banner. Both now accept
any printable block ≥16.

## What is still copied — 1,154 B, 0.1 %

LE header + object table (1,020 B), import module table (36 B), MZ header
(96 B), pad (2 B). `work/audit_headers.py` parses every field of the first;
regenerating them is the same exercise as the fixup tables, just smaller.

A caveat on the fixup generator: it re-encodes from *decoded* records, so it
proves the decoder is lossless and the encoding is understood. It does **not**
yet compute fixups from the code's relocatable references, which is what a real
build does — that needs the operands themselves classified as relocatable, and
is the step after obj2.

## Next points, cheapest first

1. **Branch drift on obj1** — a smaller `--branch-batch` recovers most of the
   ~34 KB of demoted branches; needs the pass count bounded some other way
   (e.g. demote per drift region rather than per pass).
2. **`mov 8B/89` direction-bit forms** — NASM cannot emit them; emit as raw
   bytes and count them honestly, or accept the loss.
3. **Segment prefixes** — detect a prefix byte in the original that capstone
   omitted and emit it explicitly, rather than demoting the instruction.
4. `outsb` (22 B) and friends are probably **data decoded as code** — the
   orphan scan's tail-quality filter is not strict enough there.
5. Port UW1's remaining design decisions (`F030Underworld/analysis/reassembly.md`),
   which took that project to **99.98 %** on a 561 KB EXE.
