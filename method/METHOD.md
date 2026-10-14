# Porting a DOS game to a 68000/68030 Atari — a working method

A portable playbook extracted from F030POR (*Pool of Radiance*, 1988, SSI) and
its siblings: `../F030Underworld` (UW1), `../F030Underworld2` (UW2),
`../F030TieFighter` (TIE), `../F030F29` (F29), `../F030Comanche` (CMN),
`../F030Falcon3` (F3), `../F030Links386` (L386), `../F030LOL` (LOL), and
`../F030MagicCarpet` (*Magic Carpet*, 1994/1995), and `../F030WC1` (WC1 —
recorded as pairing a source reconstruction with the 1990 DOS binary as
behavioural authority under §4.2; its working copy in this workspace is
currently a stub), `../F030ICR` (ICR —
*IndyCar Racing*, 1994), and `../F030PanzerGeneral` (PG — *Panzer General*,
1994). It is written so a different DOS game can start from scratch without
rediscovering the same traps.

Nothing here is theory. Every rule exists because skipping it cost time on a
real project, and the cost is named so you can judge whether it applies to
yours.

This file is the *phase* playbook; its reverse-engineering companion is
`CROSS-PROJECT.md` — one body generated from `gen_cross_project.py` (this
repo, edit there) into this repo and every project, collecting the techniques
that transfer with each one attributed to the project that paid for it. The
two documents cite each other rather than repeating each other.

---

## 0. The shape of the work

Four phases, in order **for each vertical slice**. Do not wait to understand the
whole program before porting the title screen, but do not port title-screen
behaviour before its formats, instructions and observable contract have passed
their gates. Findings may send a slice back to an earlier phase; that is evidence
correcting the model, not a reason to keep several unproven models alive.

| phase | output | done when |
|---|---|---|
| **1. Decode** | a corpus-tested description of each required format | the parser consumes every shipped input in scope exactly, all structural invariants hold, and representative semantics have an independent check |
| **2. Disassemble + prove** | a loader/address map and conservative instruction corpus | the files rebuild byte-for-byte, every code/data overlap is explicit, and every entry point records why it is code |
| **3. Understand** | behavioural contracts for the current slice | inputs, outputs, side effects, arithmetic widths and oracle cases are recorded against source ranges |
| **4. Port** | validated target slices | the original, host reference and target agree at the declared comparison points, and substitutions and deviations are explicit |

Keep three proofs separate:

1. **Reconstruction** proves that the container model and emitted encodings can
   reproduce the file bytes.
2. **Classification** establishes whether a range is code, data, padding,
   mixed-use, or part of an alternate/runtime-generated instruction stream.
3. **Behaviour** proves what that code does for a stated input and machine
   state.

Byte-exact reassembly is the phase-2 pivot, but it proves only the first item.
The known-data guard and execution telemetry support the second; static reading
plus controlled original runs support the third. A plausible listing that blurs
these claims is worse than none because it looks like evidence.

**Presentation scaffolding may run ahead** once a data format is verified. It
must be marked as a target artefact, not as recovered game behaviour. This gives
an early end-to-end pipeline without letting placeholder logic become the port.

**Keep storage geometry separate from display geometry.** A resource header may
carry a visible mode, a stored pitch/maxima, an allocation capacity, and a
palette or other tail at different boundaries. Derive the decoded extent and
termination from the original consumer's read loop plus corpus invariants;
record stored width/height, visible viewport, capacity, and tail separately.
Do not let a display-mode pair or a plausible buffer size become the port
contract. Comanche's `CONSOL1S.DTA` is the worked correction: its header says
320x200 for the VGA display but the consumer decodes a 328x290, 95,120-byte
surface before a separate 769-byte palette tail.

### 0.1 Plan the dependency closure of one observable route

Keep one active delivery slice in the project's existing port plan. Start from
the last verified checkpoint and name the next player-visible result, the
supported build/configuration and the symbol where it attaches. For the first
slice, the route starts at boot and reaches the connected startup flow required
by §4.3a. An isolated decoder or renderer can be a useful prerequisite without
being a supported game slice. Use [templates/port-slice.md](templates/port-slice.md)
as a starting shape; link existing route manifests and function records instead
of maintaining duplicate descriptions.

Build the dependency list from §4.2d's DOS route and the static callers,
callees and data consumers that explain it. Include more than direct calls:

- initialization and shared-state producers, resource loads and file positions;
- indirect dispatch, callbacks, interrupts, overlay residency and lifetime;
- input-driver poll/acknowledgement and timer ordering;
- the platform seams, converters, toolchain and capture tools needed to execute
  and verify the route.

For each item record a stable ID, its provider, what consumes it, the required
contract/representation, evidence link, status, and next validation command.
An edge means **the consumer cannot satisfy its contract until the provider
satisfies this requirement**. A library being present or a function being
implemented does not establish that edge. Track dependency readiness separately
from §4.2's evidence grade and function implementation status.

Follow prerequisites transitively until each ends at an already verified
contract, a new item in this slice, or an enumerated platform substitution.
Group mutually dependent routines into one boundary with explicit shared-state
ownership and initialization; a call-graph cycle is not permission to stub a
return value. A single trace establishes only its executed route. Static
branches, indirect targets and callbacks that can occur in the declared scope
need their own witness or an explicit unresolved entry. Narrow the supported
scope when necessary; do not claim an unobserved path absent.

The slice is ready for supported integration only when every required edge is
accounted for and no unresolved dependency can execute on that path. Fixtures
may inject captured state to test a function in isolation, but they do not
replace its producer in connected game flow. Deferred features remain in the
inventory, with the route/configuration that excludes them recorded. Disabling
sound, for example, does not justify omitting a timer or completion callback
that game flow still consumes.
Panzer General's no-sound startup still needs a DOS mouse driver: its mouse
reset gate precedes registration of the callback that advances the splash
wait counter. Loading the driver closes that route dependency; bypassing the
wait would conceal it (`F030PanzerGeneral/analysis/executable.md`).

### 0.2 Schedule the next discriminating measurement

Choose work by what unlocks the active route, in this order:

1. **Trustworthy evidence:** correct media/build identity, address mapping,
   oracle settings, and an emulator that executes the relevant path correctly.
2. **Reachability:** drive the original through its launcher, protection,
   initialization and input gates to the required checkpoint.
3. **Contract closure:** settle the missing state producer, dispatch target,
   format or timing rule that prevents the next connected transition.
4. **Implementation and parity:** land the browser and target counterparts,
   then run routine fixtures and the cumulative connected route.
5. **Measured performance:** optimize a proven bottleneck while retaining the
   same behavioural fixtures (§4.6a).

Among equally blocking items, prefer the smallest experiment that distinguishes
the competing readings; use cross-project reuse as a tie-breaker. Record the
question, competing predictions, command, observable result and decision it
will enable. Set a bounded capture/run limit appropriate to the experiment.
If it produces no new distinguishing evidence, change the probe or its
preconditions before repeating it. Leave the exact blocker and next experiment
in the plan, and work on independent prerequisites where possible.

This is why POR's copy-protection route is worth more than longer undriven
coverage runs (§3.5), and why the L386 `10049` investigation requires an oracle
acceptance test before trusting post-gate behaviour (the ledger's L386 adopt
list). A missing prerequisite does not justify a guessed game implementation.
Progress is the next verified connected route and its remaining blockers;
function counts and disassembly percentages are supporting inventories.

### 0.3 Keep discovery broad and proof route-scoped

Build enough of a whole-build map to identify the selected executable, loader
and address spaces, entry and dispatch landmarks, resources, and recovered
functions. Then deepen the analysis along the active slice's transitive
dependency closure. A complete disassembly, decompilation, or contract set for
the entire game is not a prerequisite for the first supported result.

The recovered-function inventory is an accountability map, not the work queue:
retain every recovered DOS function and its identity/status, including entries
that remain `Identified` or `Unproven`, but require full contracts and parity
evidence before a function enters supported flow. For each function or branch
deferred from the declared route, record the scope/configuration and evidence
that excludes it. One trace failing to reach a function is not exclusion;
every path that can execute within the supported scope still needs a witness or
an explicit unresolved blocker (§0.1).

Expand the route after its current connected result passes cumulative
regression. At each iteration, either close that observable result or leave one
named blocker with its next discriminating measurement (§0.2). Do not use
function counts, code coverage, or a long list of partially analysed routines
as a substitute for route progress.

### 0.4 Automate the checked work within each slice

Prefer deriving repetitive structure from verified inputs over transcribing it
again: byte placement, address maps, dispatch tables, function/source links,
fixture plumbing and, where suitable, native code. Keep human analysis focused
on unresolved semantics, state ownership and the next observable transition.
The four phases remain the gates; automation carries their evidence forward.

F030CT's 65816-to-68030 translator demonstrates this approach through a checked
listing adapter, context-aware discovery, flag analysis, source emission and
runtime diagnostics. Its SNES instruction model is not an x86 frontend, and its
successful runs are not DOS evidence. The inspected implementation, measured
placement check and limits of its reported parity are recorded in
[the translator review](analysis/f030ct-translator-review.md).

Adopt the approach incrementally in the existing active slice:

1. Retain one small DOS capture and a passing JavaScript contract fixture at a
   stable function boundary. Establish the current native result where one
   exists; a missing oracle remains the first blocker.
2. Automate the largest repeated task blocking that slice. For code generation,
   start with one recovered routine or recurring idiom whose widths, memory
   effects and exits are known, under §4.3b. A whole-game translator is not a
   prerequisite; hand-written native implementations remain valid.
3. Produce a deterministic source map and unresolved-work report with the
   build. Replay the DOS, JavaScript and target comparisons before extending
   the supported route. Feed each new failure back as a retained fixture or
   recovery task, not an automatically accepted behaviour.
4. Record whether the experiment reduced manual transcription or diagnosis
   time, the remaining reachable unknowns, and its code/memory/timing cost.
   Expand only if it helps deliver the next verified transition. Extract a
   shared tool after a second consumer validates its own contracts
   (`DEPENDENCIES.md`), not because the first prototype can emit more code.

---

## 1. Decode the data

### 1.1 Follow the distribution chain to the bottom

Start at the shipped media and unwrap every layer before analysing anything:

```
archive/image  →  filesystem  →  per-game archive  →  expanded files
```

For POR: a `.7z` → two 720 KB FAT12 floppy images → four SEA/PKARC archives →
257 files. Each layer had a surprise: 7-Zip reads FAT12 images directly but
**cannot read ARC and does not fail loudly** — it reports success with zero
files, so a script that ignores exit codes silently produces an empty tree.

A layer can also hide *inside* an executable. UW2's `INSTALL.EXE` is LZEXE
0.91-packed — `LZ91` at file 0x1C, `e_crlc = 0`, `e_cparhdr = 2` — so MZ
arithmetic on it describes the unpacker stub, not the program. Unwrap such a
file first, or every §2.1 signal reads wrong. CMN's `COMANCHE.EXE` is the
worked example at scale: 61 KB packed, 386,823 B unpacked with `unlzexe`, and
every analysis artefact derives from the unpacked image only.

**Make the whole chain one reproducible script** (`work/stage.sh`) that ends in
an integrity check. ARC and most archive formats store a per-file CRC; use it.
"257 entries, 257 OK, 0 bad" is a fact you can build on. Also record the hash of
each shipped image, an extracted-file manifest, and the exact tool version and
arguments. An extractor exit code without an expected entry count, byte count
and CRC/hash check is not a successful stage.

Keep both packed and unpacked executables. Hash them and record the command that
relates them; the packed file is distribution evidence, while the unpacked image
is analysis input. Never silently replace one with the other under the same
name.

### 1.2 Never edit the pristine copy

Three tiers, enforced by directory:

- `assets/` — as shipped. Never modified.
- `game/` — extracted, made read-only where practical. The reference.
- `work/` — derived, regenerable, git-ignored.

If a derived tree is reproducible by script, do not commit it. F030POR's
expanded data and 3.3 MB disassembly listings are ignored; the scripts that make
them are not.

### 1.3 Resolve containers by arithmetic, then confirm by eye

Container formats fall out of invariants, not guesswork. For a directory-style
container, look for:

- offsets that are monotonic
- `offset[k+1] == offset[k] + size[k]` (a cumulative chain)
- `header + Σ sizes == filesize` exactly

When all three hold across *every* file of that type, the container structure is
strongly supported. The arithmetic does not yet establish what its fields mean.
POR's `.DAX` container fell out in one pass this way and then verified on all 89
files and 1,044 blocks.

Do the same for the *file set*: sizes that are all `1 + n*K` tell you the file
is a count byte plus `n` fixed records.

### 1.4 A size identity is not a decoded asset

**The single most important rule in phase 1.**

POR's pixel data satisfied `17 + h*wb*4 == size` under *both* a planar and a
packed interpretation. The arithmetic could not distinguish them. Rendering both
and looking at them could: planar was noise, packed was the title screen.

So: for any visual format, **render it and look**. Keep the contact sheets. For
audio, listen and inspect a waveform/event dump; for maps or scripts, emit a
human-readable form and exercise it against original behaviour. A decoder that
produces the right number of bytes is only a structural check.

Keep the representations distinct: **stored bytes → decoded values → runtime
state → displayed/heard result**. Compression, delta frames, palettes and
hardware expansion can make two adjacent arrows individually plausible while
the end result is wrong. State which arrow each test covers.

Later, phase 3 confirmed the packed reading from the DOS code itself. That is the
ideal: two independent confirmations, one from data, one from code.

### 1.5 Record evidence state, and write TBD when it is TBD

Every format doc marks unproven fields `TBD`. The temptation is to write a
plausible field name because it makes the table look finished. Don't — the next
person cannot tell your guess from your measurement, and neither can you in a
month.

For each non-trivial field or rule, record one of these states:

| state | minimum evidence |
|---|---|
| **Hypothesis** | explains the observation but has not predicted another one |
| **Structural** | holds over the full corpus and satisfies bounds/size invariants |
| **Code-backed** | a cited original routine reads or writes it that way |
| **Runtime-backed** | a controlled original run demonstrates the interpretation |

These states are complementary, not a simple ladder: code can reveal intent
without proving the path ran, while one runtime observation covers only its
scenario. Keep the command, fixture and source hash that reproduce each claim.
Two independent routes — normally corpus arithmetic plus code or runtime
behaviour — are the gate for calling semantics settled.

### 1.6 Make the decoder an executable specification

A decoder should fail closed and explain where it failed. It validates offsets
before use, rejects truncated records and impossible counts, consumes exactly
the declared payload, and reports trailing bytes rather than ignoring them.
Run it over the entire corpus on every change, not just the attractive sample.
Keep small fixtures for the empty/minimum case, each encoding mode, the largest
known record, and deliberately truncated or corrupt input.

Use the right proof for the format:

- For a lossless reversible format, require
  `encode(decode(original)) == original` byte-for-byte.
- If multiple byte streams encode the same values, require semantic equality
  after re-decoding and retain structural checks; a different compressed stream
  is not automatically a failure.
- If no encoder exists, compare with an independent reader or the original
  routine and keep golden decoded metadata/output. Do not call a decoder-only
  parse a round-trip.

For every converter fixture, save the source hash, decoded dimensions/counts,
and expected logical output. Contact sheets remain a human semantic check; their
machine-readable pixels or events are the regression oracle.

---

## 2. Disassemble, and prove it

### 2.1 Identify the compiler and the executable model first

This determines everything downstream. Cheap signals:

- **Length-prefixed strings** → Pascal.
- **Runtime error codes** loaded into a register just before an abort path →
  Turbo Pascal (200 = divide by zero, 208 = *overlay manager not installed*,
  255 = Ctrl-C). POR's INT 3Fh vector pointed at `mov ax,0x00d0` — 208 — which
  identified both the compiler *and* that the program is overlaid.
- **`MZ` header arithmetic**: `(e_cp-1)*512 + e_cblp` vs. the file size. If the
  file is bigger, something is appended (a self-loaded tail, overlays, data).
- **An `FBOV` signature exactly at that image end** → Borland C/C++ overlay
  pool (§2.2a). Both Underworld titles have one, and in Borland output the
  stack top `e_cparhdr*16 + (e_ss<<4) + e_sp` lands on the same boundary —
  three readings of one number.
- Copyright strings in the CRT (`Turbo C++ - Copyright 1990 Borland Intl.`).

Then decode the header *exactly*, because every field has a plausible wrong
reading. `e_ip` is at 0x14 and `e_cs` at 0x16, in that order — swapped, the
computed entry still lands on real-looking code. A relocation entry is
`(offset u16, segment u16)`, 4 bytes — read with any other stride it
manufactures "junk entries", and UW1 carried exactly that defect story for
months (2,474 of 3,176 entries "invalid"; a failure count that systematic
should itself have been the tell that the *stride* was wrong, not the file).
And there is no `e_lfanew` in a real-mode MZ: with `e_lfarlc = 0x3E` the u32
at 0x3C straddles into the relocation table and reads as a plausible constant.

The cheap insurance for all of it: compute the entry point and disassemble
twenty instructions. A CRT start is unmistakable — Borland 16-bit is
`mov dx,<DGROUP>; mov [cs:…],dx; mov ah,30h; int 21h`; Watcom is `E9 xx 00`
jumping over the embedded `WATCOM C/C++16 Run-Time system` banner (TIE's
whole launcher chain enters exactly so, and the Watcom32 CRT does the same
over its own banner) — and **if what you find needs an excuse, the field is
wrong.** TIE's "pure container never executed by DOS" model was exactly such
an excuse, and it survived across four documents until an assumption-free
header parse retired it. Bonus from the same check: in Borland
output relocation entry 0 patches that first `mov dx` immediate, so entry 0's
target word *is* the DGROUP segment; confirm it by locating the compiler
banner at the head of DGROUP (search for the string and subtract — its exact
displacement varies per binary). Full re-measurement:
`CROSS-PROJECT.md` §1.

Make the result an explicit address map, not prose scattered across notes. For
each load object record file range, header/load bias, link-time base, relocation
state, runtime range, and overlay identity where applicable. Include one worked
`file offset → logical address → runtime linear address` example and assert that
the entry point, one relocation and one known datum traverse the map correctly.
Every later citation and trace fold depends on this table.

### 2.2 Overlaid programs: find the directory, and you have the map

Many 1980s–90s DOS games are mostly overlay. POR's `START.EXE` is 47 KB of stub;
223 KB of code lives in `GAME.OVR`.

The Turbo Pascal model — worth recognising, and similar schemes exist for
Microsoft's linker:

```
INT 3Fh                     the overlay call; NOT an instruction boundary
DW  offsetInUnit            3 bytes of descriptor follow the opcode
DB  0
```

and per overlaid unit, a resident stub segment in the EXE:

```
+0x00  CD 3F 00 00        "load this unit" stub
+0x04  u32 fileOffset     into the .OVR
+0x08  u16 codeSize
+0x0A  u16 fixupSize
+0x0C  u16 entryCount     number of 5-byte thunks at +0x20
+0x20  entryCount x (CD 3F, u16 offsetInUnit, 00)
```

Verify with the chain invariant `fileOffset + codeSize + fixupSize ==
fileOffset(next)`, ending exactly at EOF. When that holds for every unit you
have an exact partition of the overlay file **and a list of real entry points**
— 774 of them for POR. That list is what makes everything after this tractable.

The program entry is usually a chain of far calls, one per unit, to each unit's
first thunk: the unit-initialisation chain.

### 2.2a The same opcode, a different scheme: Borland's `FBOV` pool

Turbo Pascal is not the only owner of `INT 3Fh`. Borland C/C++ appends its
overlays as an `FBOV` pool past the load image — UW1: 141 KB, UW2: 210 KB —
behind a 16-byte header:

```
"FBOV" | u32 ovrsize | u32 exeinfo | u32 segnum
```

`ovrsize` is the pool payload, the bytes after that 16-byte header; check it
and the reading is certain. The other two fields are the map, and both are
easy to misread:

- **`segnum` is not the overlay count.** It is the row count of the segment
  table at `exeinfo`, which describes *every* linker segment as
  `{u16 seg, u16 size_bytes, u16 type, u16 flags}`, chained by
  `seg + size_bytes/16`. Both projects read it as "overlay segments" for
  months — UW1 "159", UW2 "174". The overlaid rows are the ones with
  `type == 3`: **64 of UW1's 159, 77 of UW2's 174.**
- **Each type-3 row is a stub**, and its header is the *same shape Turbo
  Pascal's directory uses* — u32 pool offset, u16 code size, u16 fixup size,
  u16 entry count, plus a runtime `resident segment` slot — so one parser
  covers both families. The stub is 32 bytes followed by its own thunks:
  `0x20 + 5*nent == size_bytes` for every row.
- **The thunk record is `CD 3F`, u16 entry offset, `00`** — the trailing byte
  is padding, not a segment. Every operand is below its own unit's code size,
  which is what proves the reading. Counting raw `CD 3F` sites over-counts:
  UW1's 667 sites are 64 stub signatures + **602** thunks + 1 byte the
  installer reads the vector number from; UW2's 1,006 are 77 + **928** + 1.

So there *is* a static map — the same file-range partition `TPOV` gives you.
What FBOV does not give you is a static *address*: overlays are swapped into a
buffer at per-load addresses (UW1 caught two live at deltas −0xBCA1 and
−0x8F50), so a runtime address inside the pool that "resolves" to a pool
function name proves nothing — the functions tile the region densely. Match
the bytes at CS:IP back into the file instead. Keep the two apart: `TPOV`'s
directory and `FBOV`'s type-3 stubs both pin every unit to a file range; only
`TPOV` lets you treat that range as an address space of its own.

**Do not hunt for a dispatch table.** UW1's manager was expected to end in a
`call far dword ptr ds:[0x26]` into the freshly loaded unit; that slot is
never patched and points at a `retf`. What it actually does is overwrite the
5-byte thunk in place with `EA <off> <seg>` and back the saved `IP` up by two
(`sub word [bp+2],2`) so the `IRET` re-executes it as a far jump — first call
pays the interrupt, every later call is direct. That is also why the record is
5 bytes wide, and a RAM dump hands you the resolved map for free (UW1: 70 of
602 thunks patched, each landing on a `55 8B EC` prologue).

Either way: **a tail past the MZ image end is a question, not a fact.** Both
Underworld projects believed a self-load story for months; the four magic
bytes settle it in seconds. *(`../F030Underworld/analysis/uwexe.md` §13.3 and
§13.6, measured on the running game; `CROSS-PROJECT.md` §1 for the four
self-proving checks and the per-project counts.)*

### 2.2b 32-bit extender games: the map is the LE object table

A DOS/4G(W)-era game (`../F030TieFighter`) is an MZ stub plus a Watcom **LE**
module — no overlays, but the same principle: the container hands you the map.
The LE object table, object page map and fixup tables partition the file with
self-checking arithmetic (`data_pages_off + (pages−1)*page_size +
bytes_on_last_page == filesize`; the fixup page table's last entry must land
exactly on the import module table). Two consequences:

- **Immediate-scanning the raw file is structurally impossible.** Operands are
  stored object-relative and patched at load time from the fixup records, so
  no base you try makes a known string's address appear as a dword. Decode the
  fixup table instead and use it as a reverse-xref index — in TIE that turned
  the project's longest-open xref question into a single source site
  (`work/audit_fixups.py --target=OBJ:OFF`).
- **The MZ stub in front is still a real program.** Parse it with the same
  §2.1 rigour: TIE's stub fields, read loosely, got promoted into a plausible
  "private DOS4G header" model that survived five days across four documents,
  until an assumption-free header parse (`work/audit_headers.py`) collapsed
  every "private" field into the standard LE map.

### 2.3 Use recursive descent as authority; use sweeps only to find candidates

A linear sweep of 16-bit x86 can produce garbage wherever data sits in the code
segment. Recursive descent from *real* entry points contains that damage. The
overlay directory hands you those entry points; use them. A sweep or byte scan
may suggest a candidate, but it does not promote that address to code until
control flow, a loader table, a relocation-aware xref or execution telemetry
supports it.

Two capstone traps that cost hours on this project:

- **Far transfers are `lcall`/`ljmp`, not `call`**, and their operands arrive as
  **(segment, offset)** in that order. Matching on `call` follows nothing:
  coverage sat at **1 %** until this was fixed, then jumped to 14 %.
- **`INT 3Fh` is not an instruction boundary.** Decoding its 3 descriptor bytes
  as opcodes derails the walk immediately — the first run reported "33 × int
  3Fh" and 0 % coverage, all of it garbage. Step over 5 bytes and continue.
  Borland's `FBOV` thunks are the same 5-byte width (§2.2a); the trap
  transfers.

Feed the fixup/relocation table in as "these words are segments" so the walker
never decodes a fixup as code.

Keep seeds in a reviewed registry, with `address`, `address-space/object`,
`kind`, `source of evidence` and `confidence`. Record rejected candidates as
anti-seeds beside the reason. Fail the build when a seed lands outside its load
object, inside proven data, or in the middle of an existing instruction unless
mixed use or an overlapping entry is itself demonstrated. Indirect calls and
jump tables stay unresolved until their target rule is decoded; guessing all
aligned addresses turns uncertainty into false code.

And keep a **known-data guard**: an explicit list of proven-data regions
(string pools, tables, palettes), with every run asserting that none of them
was disassembled. Any technique that widens coverage can be pushed until it
manufactures code out of data, and F29 measured the trade:

| seeding policy | coverage | data regions wrongly decoded |
|---|---:|---:|
| plain descent | 40.6 % | 0 |
| every byte-scanned call target | **66.2 %** | **6 of 10** |
| two independent call sites required | 44.6 % | 0 |

**The 66 % is worthless.** Coverage is only meaningful net of the guard — and
the ratchet (§2.4) does not replace it, because data bytes that happen to
decode as instructions re-encode byte-exact and score as "real". The two
invariants are orthogonal: the ratchet proves *re-encodability*, the guard
proves *code-ness*. Run both. *(F29 `docs/X86DISASSEMBLE.md` §6,
`docs/RE-NOTES.md` §The data-region guard.)*

### 2.4 The reassembly ratchet — the core technique

**Coverage percentages do not test a disassembly.** A wrong instruction length
silently corrupts every byte after it and still looks like a listing. Reassembly
proves byte selection and encoding; it cannot prove that a re-encodable byte run
is code or that its mnemonic has been understood.

Re-encode and compare:

1. Emit assembler source from the conservative listing, retaining untouched
   regions as `db`/`incbin` with intended file offsets.
2. Assemble it and parse the assembler listing.
3. Compare each emitted instruction at its **intended** offset with the
   original bytes.
4. Demote only the mismatching instruction to `db`, record the reason, and
   rebuild.
5. Require both per-range equality and a whole-file hash match.
6. Freeze that byte-exact baseline. From then on, promote residue to instructions
   only with evidence and require every coverage regression to be an explicit,
   reviewed correction.

The initial demotion pass always terminates at byte-exact, even if everything is
data directives. Therefore **byte-exactness is a required invariant, not a
sufficient goal**. After the baseline is frozen, ordinary refinement ratchets
the mnemonic score upward. A correction that reclassifies false code may lower
it; record why, update the baseline, and prefer accuracy over a monotonic number.

> **The trap:** a byte-exact rebuild made entirely of `db` proves nothing. My
> first ratchet demoted "everything after the last label" on a mismatch and
> reported a byte-exact rebuild at **1 %** real instructions — technically
> passing, actually meaningless. Verify **per instruction**, using the
> assembler's listing output (`nasm -l`), and demote exactly the offenders. Same
> unit: **79 %**, in three passes.

UW1 ran the same ratchet to **99.98 %** real mnemonics on a 561,744 B EXE
(26 `db` left, 4 passes, ~25 s), and the delta over POR's 80 % is five design
decisions, all portable (`../F030Underworld/analysis/reassembly.md`):

- **Compare per line at the line's *intended* offset**, not where the
  assembler happened to emit it — one short instruction then localises to
  itself instead of shifting 100,000 innocents.
- **Emit branch targets `$`-relative** (`jmp short $+2+N`): no absolute
  address enters the encoding, so a flat `nasm -f bin` rebuild of a
  *segmented* program is exact and 64 KB wraparound cannot corrupt a branch.
- **Derive operand-size qualifiers from the original encoding** (capstone's
  `encoding.disp_size`/`imm_size`) instead of searching for the right form.
- **Compilers pick encodings assemblers won't.** Borland emits reg-reg
  ALU/MOV with the direction bit set (`8b ec` for `mov bp,sp`); NASM always
  picks `89 e5`, and no syntax selects the other form — 7.6 % of UW1's code.
  Generated macros that build the ModRM byte by hand keep those as
  instructions instead of `db`. POR's "short vs. near branch" demotions are
  the same class of loss.
- **Keep a whole-file hash as well as the per-line check** — a shadowed loop
  variable once truncated UW1's output by 140 KB while every emitted line was
  individually correct.

(`nasm -l` has its own traps — macro-expanded bytes attributed to the macro
definition's line, `times` runs, `%include` renumbering the listing. Read
`../F030Underworld/analysis/reassembly.md` §7 before writing a new ratchet.)

Then rebuild the *files*, not just the code images — headers, relocation tables,
directory order, fixup blocks. That is what catches structural misunderstandings:
POR's rebuild failed with `unit 016 starts at 0, directory says 4`, which is how
the 4-byte `TPOV` file signature got proven rather than assumed. Finally,
prove the source is a source and not a copy: change one string in the
generated assembly, rebuild, and require the diff to be exactly the bytes you
changed and nothing else.

Expect the score to differ by file type. 80 % for overlay code is good; 21 % for
a loader stub is fine when a third of that file is initialised data by
construction. Report both *mnemonic bytes / whole file* and *mnemonic bytes /
currently claimed code* so real data does not masquerade as missing analysis.
Always publish the known-data collision count beside either percentage.

One definition to fix in advance: "byte-identical" means identical to the
**file** image. A self-modifying program (F29 holds live state in instruction
immediates, §2.2 of its `X86DISASSEMBLE.md`) still rebuilds byte-exact from
the file, and its SMC sites are *expected* `db` residue — label them, don't
chase them.

### 2.5 Turn residue and coverage into explicit worklists

A remaining `db` run may be genuine data, padding/alignment, a relocation or
fixup field, an encoding the assembler cannot select, self-modified or generated
code, an overlapping instruction stream, or code reachable only through an
unresolved indirect transfer. Do not collapse these different states into
"unknown code". Classify each residue range and retain `unresolved` where the
evidence does not choose one.

Track four separate metrics:

- whole-file reconstruction hash;
- mnemonic coverage of claimed-code ranges;
- zero unexplained overlap with proven-data ranges; and
- scenario-scoped executed-byte coverage, after mapping runtime bytes back to
  the correct file/object instance.

The residue table and unresolved indirect edges are the finite phase-2 worklist.
Prioritise items executed by the current oracle scenario or required by the next
port slice, then items with strong xrefs. A large unexplained range is not more
important merely because it is large.

### 2.6 Recover control flow with its execution context

An address alone is not always a decoded instruction or a callable contract.
Associate each analysed entry with the selected image/load object, runtime code
identity and the state needed to interpret it. For DOS this can include code
mode and operand/address size, segment selectors/bases, overlay residency,
direction/condition flags and stack/calling convention. Carry changed state
through calls, returns, interrupts and non-local exits; a source CPU register
must not inherit assumptions from the translator's original game.
Context keys qualify the canonical DOS function ID; generated variants do not
acquire new ground-truth names or replace its inventory record.

Keep distinct contexts where they change decoding, addressing or behaviour.
Where only a value varies, prefer an explicit runtime value and a verified
generic helper to cloning the whole graph. Context merging must preserve all
possible supported successors and effects: a size cap is not permission to
pick a convenient state, drop an edge or guess a width. Unresolved state stays
in the report and blocks the affected route. CT's direct-page tracking and
per-site dispatch sets reduced analysis growth; that is a useful design
pattern, not a transferable DOS register model.

For each indirect call/jump, record the source site/context, table or pointer
producer, entry representation, index domain and extent, possible targets and
exit contexts, and their static/DOS evidence. Include callbacks installed by
writes, return-address dispatch and stack switching when present. A label
inside a table does not terminate it; a handler classified as data does not
prove the table stops there. Bound it from the actual consumer, producer and
bytes. Heuristic scans and runtime misses produce candidates to investigate,
not automatically verified targets. A miss in the port may itself be caused by
wrong arithmetic or state; confirm it against the DOS path before promotion.
Keep the unobserved but reachable edges required by §0.1 visible.

For unpacked, overlaid or self-modifying code, retain the loader/producer,
destination, captured bytes and relocation/patch rules. A native translation
of those bytes is valid only for that code instance. Prove the relevant range
immutable for its lifetime, or detect writes/reloads and invalidate or select
the corresponding verified variant before execution. A short entry signature
does not establish the identity of an entire mutable routine. A fallback may
run only if its full behaviour is validated for that scope; otherwise the
route remains unsupported. CT's WRAM overlay and patched-call handling expose
this obligation; copying its eight-byte entry check would not discharge it.

---

## 3. Understand

### 3.1 Decompile per load object, not per physical file

Import the objects described by the loader model in §2.1. For a static Turbo
Pascal overlay map, each unit can be a raw image at `0000:0000`, making
decompiler addresses equal unit offsets. For an LE image, use its object bases
and fixups. For a dynamically placed `FBOV` pool, do not invent a permanent base:
identify a runtime instance by content and translate it back to pool offsets.
The aim is one canonical address vocabulary shared by maps, listings, traces,
docs and port citations.

Seed entry points **before** analysis (a pre-script, not a post-script): a raw
binary has no entry, and auto-analysis finds almost nothing on its own. Import
the reviewed §2.3 registry and assert the number applied and rejected. For POR,
20 seeded entries became 30 discovered functions in one unit; 758 seeds became
1,102 functions across the program. Decompiler-discovered functions remain
candidates until their incoming edge or execution evidence is recorded.

### 3.2 Code and data live in different segments

The costliest single mistake of phase 3. In a segmented Pascal/C program, an
address like `0x260A` in decompiled code is a **DGROUP offset**, not an offset
into the unit you are looking at. Dumping it from the unit image returns
unrelated bytes that can look like a decoded table if you are careless.

Find DGROUP's base (POR: `mov dx,0x740 / mov ds,dx` in the abort path) and
resolve data references against the *EXE*, not the overlay. Confirm the base by
predicting something checkable: `DS:260A` → `01 02 04 08`, the EGA plane masks,
and the only occurrence of that sequence in the whole image.

### 3.3 Index the corpus around observable slices

A thousand functions as a flat list is unusable. Emit an inventory and index
mapping each recovered function to object/address, file range, size, evidence
grade, known callers/callees, touched globals, trace scenarios and — where it
is one — which resident entry point reaches it. Grouped and tagged, the same
pile becomes a worklist. The inventory remains complete as discovery proceeds,
but the active analysis queue follows §0.3's route-scoped dependency closure.

Start from an observable slice — title/menu, one gameplay action, save/load,
one audio event — and walk backward from its output or forward from its input.
Runtime call frequency and graph position are useful priorities; function size
alone is not. This avoids spending weeks naming a large decompressor or CRT
routine that the next port slice does not need.

### 3.4 Build the dynamic oracle for what static analysis cannot settle

Static analysis narrows; it rarely closes. POR's palette question: no attribute-
controller write anywhere in 38 units, exactly one `INT 10h` — a shared wrapper
whose `AH` comes from the caller — and 15 call sites where `AH` is not
statically resolvable. That is *narrowed, not settled*, and no amount of further
reading fixes it.

Define the scenario before running it: exact executable/data hashes, DOS and
emulator versions, configuration, command line, initial save/state, ordered
inputs, checkpoints and stopping condition. Capture a screenshot or state marker
at each driven step. Repeat a baseline run to expose timer, RNG or uninitialised
state differences before treating a one-off value as behaviour. When possible,
run the unmodified original through the same capture path as the control.

Run the thing and log it. Under DOSBox-X, the `[log]` section takes per-category
switches including `int10`, `io`, `vga`; with a dummy SDL video driver it runs
headless. **The DOS console is invisible under a dummy driver** — redirect DOS
output to a file on the mounted drive and read it from the host.

DOSBox-X is one half of the oracle story. The RE siblings standardised the
other: **boot genuine MS-DOS 6.22 in QEMU** and run the original headless —
shared verbatim across the family as `dosimg.py`, `run_qemu.py`, `mbr.asm`
and `gdbstub_probe.py` (`../F030Underworld/analysis/qemu-boot.md`,
`CROSS-PROJECT.md` §6; master copies in `dos/` here). The division of
labour: DOSBox-X gives
per-category *logs* with zero guest-side setup; QEMU gives the real product
on real DOS, plus instruments DOSBox-X lacks:

- **The guest ends the run.** An 8-byte `QUIT.COM` hits `isa-debug-exit`;
  QEMU exit code 21 means done, anything else means hang — no timeout
  guessing.
- **`sendkey` drives interactive programs** and QMP `screendump` /
  `pmemsave 0xB8000` read screens a dummy video driver would hide; guest-
  written files come back via mtools. (Exactly the capabilities POR's blocked
  `INSTALL.EXE` run needs — `../F030POR/analysis/dos-oracle.md` §4.)
- **`gdbstub_probe.py` reads the running program** over QMP: it calibrates
  `file → linear` from several RAM signature windows (majority vote, skipping
  relocated bytes — a single window got overwritten on the first attempt),
  then residency-checks the whole file 16 B every 4 KB. That check is what
  overturned UW1's believed-for-months self-loaded-tail model. Two standing
  lessons travel with it: **the hottest EIP is probably an interrupt handler**
  (`SS == CS`, small `SP` — exclude it before naming a "game loop"), and
  **screenshot every driven step**, or you cannot say which state you
  measured.

One rule binds both oracles: **an absence in a log is evidence only if the
run demonstrably reached the code that would have written the entry.** POR's
first oracle run reported zero `INT 10h` calls and zero video-port writes —
while `START.EXE` was in fact parked at a startup check it never got past
(`../F030POR/analysis/dos-oracle.md` §3). Prove the code path was reached;
then trust the absence.

**Keep address vocabularies separate.** A DOS `seg:off`, guest physical
address, guest linear address and file offset are different coordinates. In
real mode, physical/linear is normally `(seg << 4) + off`, subject to A20 and
wrap rules; the same byte can therefore have many valid spellings. In
protected mode, a selector indexes the GDT/LDT rather than naming a flat
segment base. Record the extender's selector and DPMI state before translating
an address. None of these values is automatically a file offset or a correct
Ghidra address.

QEMU's monitor uses `x` for virtual-memory examination and `xp` for physical
memory; `pmemsave` also saves physical memory. Therefore
`pmemsave 0 0xA0000 ram.bin` covers `0x00000..0x9FFFF` and does **not** include
the VGA aperture at `0xA0000`. Dump that aperture separately, for example
`pmemsave 0xA0000 0x20000 vga-aperture.bin`, and keep VGA registers and palette
state as separate evidence. The IVT is at physical address zero; protected
mode runs additionally need the IDT, GDT/LDT and DPMI state.

**A trace is not an unpacked image.** `-d in_asm,exec` helps locate executed
translation blocks, but it is not a decoded-memory dump or a stable per-byte
coverage format. When an unpacker reaches its decoded entry point, schedule a
RAM dump or capture the relevant memory writes at that transition, then
validate the captured bytes against the runtime address map. The shared TCG
plugin in `dos/trace/` is the authoritative telemetry path (it builds on
macOS/Linux only so far — the Makefile has no Windows plugin recipe; on
Windows, `-d exec,nochain` logging is the route-locator fallback until that
lands, per §4.2d). A `drcov` export
is optional visualization glue: rebase it to the analyzed image and retain
scenario, overlay-unit and file-offset identity, because overlay units can
occupy one address at different times.

When a DOS/DPMI trace changes segment bases or relocates far-pointer words, do
not map `in_asm` addresses to file offsets with one fixed subtraction. Pair
`exec` transitions with full resident-byte matches and the live selector/base
state; `in_asm` can show a translated block without proving that a conditional
branch was taken. This is especially important for 16-bit near calls whose
segment-relative offsets can remain valid while the runtime linear address
changes.

QEMU's GDB stub can be used with Ghidra or IDA, and Ghidra has explicit 16-bit
real/protected-mode processor languages, but a remote session does not infer
segment bases, loader mappings, compiler conventions or trustworthy C types.
Use it to stop, inspect and correlate; keep the measured DOS oracle and the
file/runtime mapping authoritative. DOSBox-X's debugger is the complementary
interactive DOS tool. Hardware emulators such as 86Box are a timing or device
compatibility fallback, not a replacement for the reproducible QEMU oracle.

### 3.4a The oracle's in-game settings are part of the oracle

"Configuration" in the scenario list above is not only DOS and QEMU. A game
that ships a settings file has an *installed* configuration, the oracle runs
whatever that file says, and if the port runs something else then every table
compared between them measures a configuration difference and reports it as a
port fault.

Comanche makes the point cheaply. It ships `HIGH.DTL`, `MEDIUM.DTL` and
`LOW.DTL` — 250, 180 and 100 depth rings in one 5004-byte layout — and
`00026211` picks one from a byte in `COMANCHE.MNU`'s settings block.
**The shipped install selects medium.** A port built for high detail marches
250 rings; a capture from an unmodified install has 180; and the ring
schedule, the projection pages and the per-ring increments then all differ.
`F030Comanche`'s table generator carries the scar: generating from high
against a medium capture "produced 250 pages that matched none of the
original's 180", which reads as a broken projection and is nothing of the
kind.

Three things follow.

**Find the byte before trusting a capture.** It is in the game's own settings
file inside the disk image, not in the emulator's configuration. Locate the
file's bytes in the image, confirm the match is unique, and record the
absolute offset — `F030Comanche`'s is `0x392018` in `img/comanche.hdd`,
documented in its `docs/DOS-ORACLE.md`.

**Change the image, never the extracted asset.** §1.2 already forbids editing
the pristine copy, and this is the same rule one level down: patch the
installed configuration inside the image, and leave `assets/extracted/` at the
original's bytes. It is the byte the game's own options menu writes, so
changing it is a configuration choice rather than a modified asset.

**Make the capture say which side it came from.** A mismatch here is silent —
the run completes, the tables are full of plausible numbers, and only a
comparison fails. `dump_marcher_tables.py` prints its ring count; `certify-
marcher.py` prints `ring_steps: N (DIFFERS from the capture's M)`. Any harness
whose output depends on a setting should report the setting beside the data.

The disk image is normally gitignored — too large, and it carries a licensed
DOS and the whole game tree — so this byte does not travel with the repository.
Record it in the project's oracle doc with its offset and its symptom, or the
next clone silently compares two different configurations.

### 3.5 Execution telemetry: measure which bytes executed

§2.3 and §2.4 *infer* code. Telemetry records execution directly: run the
original and record which bytes the CPU actually executed. The tools are
`dos/trace/` here — a QEMU TCG plugin writing one flags byte per guest linear
address, plus `run_trace.py` to drive a run and `trace_coverage.py` to fold the
result onto an MZ load module. QEMU's plugin API is supported, so unlike the MAME half of
F030Arcade's `jsm68kdisassembler` there is no emulator fork to carry.

An executed byte proves only that the captured runtime image executed it in that
scenario. It does not prove completeness, a stable file mapping, or semantics.
Before folding flags onto a file, compare the resident bytes with that file and
account for relocations, overlays, unpacking and self-modification. Preserve the
scenario name with the coverage map; union coverage without per-scenario maps
destroys the path information needed for behavioural work.

**The percentage is not the point; the guard is.** POR, 60 s undriven boot:
9,364 of 46,992 B of `START.EXE` executed (19.9 %), against the static
disassembler's 21 % — *lower*. What is worth having is the other column:
**zero** bytes executed in the 17,296 B DGROUP that
`../F030POR/analysis/executables.md` had independently called data by
construction. Two methods derived separately, agreeing exactly. Compare §2.3's
warning about a sweep that reached 66.2 % coverage by eating six known-data
regions — coverage is only meaningful net of the guard, and this is the guard
measured rather than asserted.

**Calibrate the load base, don't assume it.** Same majority vote as
`gdbstub_probe.py`: 45 of 61 distinctive windows agreed on `0x107A0`,
reproduced across three runs. The free confirmation is that `START.EXE +0x6`
shows as executed — exactly the `e_ip` in the MZ header.

**Overlays: key by content, not by address, and never by DOS handle.** An
overlay buffer hosts different units at one address over time, and POR proves
it is not a corner case: 40 of 54 loads in one boot land on top of an earlier
one. `--ovl` flushes a region's coverage just before DOS overwrites it,
sampling the bytes that were resident; `trace_overlay.py` locates those
samples in the overlay file and folds the flags onto *file* offsets. DOS
bookkeeping was tried first and does not survive a run — POR performs 117
opens against 233 closes, so handle numbers recycle and no handle names a file
for long. Pairing `LSEEK` with reads matched RAM 1.9 % of the time; modelling
the DOS file position lifted it to 47.8 %; content search is exact. The check
that this attribution is real: folded through POR's own
`work/overlay_map.json`, **every** executed overlay byte lands inside a
documented unit — 6,870 in code ranges, 1,436 in fixup ranges, none in the
gaps. Wrong offsets would scatter into those gaps.

**Coverage is gated by the game's own gates.** POR stalls at the
copy-protection wheel, and driving it with keys added 352 bytes before
`START.EXE` exited. This is §3.4's absence rule with a number attached: a low
coverage figure measures how far the run got, not how much of the program is
code. Get through the cliff before harvesting more runtime.

**The same run yields the hardware substitution list.** `--io` tallies every
`in`/`out` and records the PC that first touched each port, which no QEMU
contrib plugin does — `hwprofile` covers memory-mapped regions only, and
DOS-era hardware is programmed through ports. Attributing each port to its
first-touching PC separates the game from the machine: POR touches 24 ports,
of which **9 are the game's** (PIT `0040/0042/0043`, speaker gate `0061`,
`00C0`, VGA graphics controller `03CE/03CF`, and VGA sequencer `03C4/03C5`
from an overlay unit). The rest are DOS, the BIOS and two TSR port-probe
sweeps. That table is what §4.2's closed substitution list wants, generated
rather than transcribed.

**Data widths come free; signedness does not.** `--mem` records the width of
every access the program makes into the window (POR: 253,108 bytes read as
byte, 244,054 as word, 435,034 written) — direct evidence for §4.4's field
types. But the sign-extension flag caught **10 bytes in a whole run**, and
that is a property of the target, not a bug: 16-bit x86 sign-extends in
registers with `cbw`/`cwd` after an ordinary load, which no memory callback
can see. Signedness still has to be read out of the code, and F29's
`0x80`-and-up trap still costs what it costs. Expect this to pay better on
the 32-bit siblings, where `movsx` is ordinary.

Two QEMU-plugin traps, each of which cost a debugging round:

- **A register handle of `0` is valid** — it is `eax`. Null-checking the
  handle like a pointer silently zeroes every `eax` read, and the symptom is
  a log of 72,316 DOS calls all reporting `AH=00`.
- **`qemu_plugin_read_memory_vaddr` asserts on `current_cpu`.** Calling it
  from the atexit callback aborts QEMU outright rather than failing, so the
  final flush cannot sample guest memory and is identified from the run's RAM
  dump instead.

### 3.6 Extract a behavioural contract before writing target code

Names and decompiler output are navigation aids, not the deliverable. For each
routine or subsystem in the next slice, record:

- source file/object range, canonical address and evidence grade;
- calling convention and input widths, signedness, units and valid state;
- return values plus memory, file, hardware and global-state side effects;
- ordering requirements and arithmetic semantics — wrapping, shifts, division,
  fixed point, table indexing and flag-dependent results; and
- oracle fixtures: captured inputs/entry state, expected outputs/exit state, and
  the observable frame, event or file change they contribute to.

Prefer fixtures at stable boundaries: decoded record in/render command out,
world state in/next state out, event stream in/audio commands out. Include zero,
sign-boundary, overflow/wrap and maximum valid cases when the path permits them.
If internal state cannot be injected on DOS, capture it at routine entry and
replay it in a host reference implementation. The contract is complete for a
slice when another implementation can be tested from it without rereading the
whole disassembly.

---

## 4. Port

### 4.1 Declare the fidelity contract before implementing it

- **Game logic — preserve observable semantics over the supported state/input
  space.** The DOS routine is the authority for *what* is computed. The target
  code may be restructured and written idiomatically; transliteration is not the
  goal. A claim of 100 % fidelity is a test conclusion, never an implementation
  intention.
- **Graphics and sound hardware — reproduce the observable result.** DOS
  register programming is evidence about ordering, values and timing, not a
  requirement to emulate the same mechanism. Timing is part of behaviour when
  it changes animation, audio, races or game state. These are the explicit
  hardware-substitution exceptions described below.
- **Input is not a free-standing hardware substitution.** Mouse and keyboard
  input must cross an emulated DOS-driver/I/O boundary before it reaches game
  logic. The recovered DOS functions remain the authority for consuming the
  driver state, returning events, changing state and advancing the game flow.

The line is **observable vs. mechanism**, not "numbers vs. pixels":

- *Logic*: anything the player can see, hear or decide on — sprite
  transparency, draw order, which animation frame plays.
- *Adaptation*: anything that only changes how those pixels reach hardware —
  bitplane layout, map-mask registers, row tables, DMA.

Write down the supported scope as well: game/version, data set, modes, input
devices and deliberately unsupported malformed-input behaviour. This prevents
"faithful" from silently meaning only the one path tested so far.

Worked example: POR's packed→planar expander exists *only* because EGA has
bitplanes. It is not ported. The entire value extracted from it is one fact —
the high nibble is the left pixel.

Two consequences people miss:

1. **Non-literal code still means bit-exact numbers.** "Semantic, not
   instruction-level" does not license 32-bit arithmetic where the original
   wraps at 16 bits, or a different signed division/shift rule because it looks
   cleaner on 68k.
2. **Verification must become behavioural.** If you are not transliterating,
   diffing instructions proves nothing — so the dynamic oracle is a
   prerequisite for claiming logic fidelity, not an optional extra.

**CPU precision adaptations preserve the numerical contract.** Different
architectures may need different instruction sequences, internal formats or
multiword intermediates. Record the DOS widths, signedness, carry/overflow,
shift and division rules, and each rounding/truncation boundary; compare the
canonical values at those boundaries. An exact multiword integer helper is a
mechanism change. Replacing fixed point with floating point, losing low product
bits or adding saturation is not justified merely by a different CPU: prove
equivalence over the supported domain or retain the original numerical rules.
Keep presentation conversion separate: VGA palette entries expanded to VIDEL
RGB565 are an explicit graphics boundary, not permission to quantize flight,
projection or simulation state. CPU selection may select equivalent mechanisms
while leaving the baseline target and its performance budget primary.

A third rule — CMN's standing one — closes the loophole the first two leave
open: **behaviour is not build-selectable.** A flag that selects between two
candidate behaviours is a decision that has not been made, and it hides the
one that is wrong: Comanche's terrain marcher carried a column-major
alternative and a ray geometry the original never had, each behind a switch,
until the rule deleted them. Recover the original's behaviour, implement it,
delete the alternative; if two readings of the listing are both plausible,
the answer is more disassembly, not a flag. (Flags that choose *which
machine* does the work — CPU vs. DSP — are fine; flags that change *what the
picture should be* are not.) *(CMN `AGENTS.md`, rule one.)*

### 4.1a m68k output is assembled and measured, never guessed

`m68k` is a processor family, not a sufficient target declaration. Every
68000-side implementation must name the exact CPU (for example MC68000,
MC68020 or MC68030), assembler or compiler, version, syntax/dialect, ABI and
calling convention, memory/alignment model, privilege assumptions, and target
link/output format. A Falcon030 target may use instructions implemented by its
MC68030, but that does not make every 68k-family instruction legal; CPU
extensions must be selected deliberately and checked against the declared
target.

The assembler/compiler is the instruction-set and syntax gate. Before a
68000-side routine is called a target counterpart, the exact toolchain must:

1. compile or assemble it with the declared CPU restriction;
2. fail the build for an instruction or addressing mode outside that CPU;
3. retain the source, command/configuration, object or binary hash, and
   assembler/compiler listing or disassembly; and
4. run the routine's contract fixtures in a 68000/68030 emulator or on the
   declared Falcon target, comparing the canonical outputs and side effects.

The vendor CPU manual and the toolchain output settle instruction legality;
the emulator or Falcon settles execution behavior. A hand-written snippet
that has not passed those gates is **Illustrative**, not a 68000 implementation
and not a function counterpart. It must not enter a supported target path or
an authoritative function record as `Ported`/`Verified`. The browser
counterpart defines and exercises the behavior contract, but a passing
JavaScript fixture does not prove that m68k source assembles or executes.

Some assemblers accept instructions which a CPU handles only through an
unimplemented-instruction exception. For example, vasm accepts 32×32→64
`MULS.L`/`MULU.L` with `-m68060`, although MC68060 UM appendix C lists them as
unimplemented. Audit emitted instructions against the hardware manual and run
boundary fixtures on that CPU without silently depending on an OS emulation
package. Comanche's exact 16-bit partial-product helper and tests are recorded
in `../F030Comanche/analysis/functions/cpu-compatibility.md`.

For shared code, assemble for the lowest CPU declared by the project, not for
the most capable machine in the family. CPU-specific code belongs in the
target seam and records its extension use and fallback boundary. Concise
68000 output is therefore generated or assembled from a checked-in source and
verified artifact; it is never produced by translating a DOS listing by eye or
by trusting a plausible-looking instruction mnemonic.

### 4.2 Nothing without a source

Nothing enters the port that has no ground-truth source in the original. Not
placeholder rules, not guessed constants, not "reasonable" defaults. If the
authority has not been read, the correct output is *nothing*.

Three categories, and everything must be in one explicitly:

| category | marking |
|---|---|
| **Grounded** | cite the hashed source image, canonical range, behavioural contract and evidence grade |
| **Target artefact** | build system, cache container, framebuffer handling — makes no claim about the original and cannot change valid-input game semantics |
| **Unproven** | `*** NOT GROUNDED IN THE ORIGINAL ***` at the definition, plus an open-risk entry; not allowed on a released execution path |

Audit periodically and expect to find things. F030POR's audit caught two: an
assumed EGA palette, and a centring rule the DOS blitter does not implement.
Both were producing correct-looking output — which is exactly why they needed
labelling rather than trusting.

Stated as the rule it is, because "nothing without a source" reads as being
about data and it is not: **never write 68k code without referring to a DOS
routine.** Every ported routine names the hashed source image, canonical range
and §3.6 contract it came from in its header; code that cannot do so does not get
written. A routine whose authority has not been read is left stopped or dormant.

**Preserve the complete recovered DOS function inventory in every port.**
Maintain one durable function record for every recovered function, whether its
implementation is JavaScript, 68000, both, or not yet written. A function may
be `Identified`, `Unproven`, `Ported`, `Verified`, `Not applicable to the
declared scope`, or another explicitly defined project status, but it must
never disappear from the inventory or be silently replaced by a new routine.
For every function that enters a supported path, the record must additionally
name its browser and target implementation symbols/files. The record is the
durable explanation of the function, not merely a source-code comment. It must
state its original identity (hashed DOS image, canonical range, known
name/aliases and evidence grade); its recovered purpose and contract (inputs,
preconditions, outputs, state/memory/file/hardware side effects, ordering,
arithmetic and observable rendering/audio contribution); and the DOS fixtures
that substantiate those claims.

This inventory rule does not make every recovered function a release gate or
the implementation work queue. Prioritize contract recovery and parity by the
active slice's dependency closure (§0.3); keep unrelated entries explicitly
identified, unproven or deferred until a later route depends on them. Every
dependency that can execute within supported scope still needs a resolved
contract or must keep that scope blocked.

**The ground-truth function name is the function ID.** Every ported function
uses the canonical DOS function name as its shared identity in the inventory,
function record, JavaScript and m68k source annotations, route manifests and
fixture metadata. Target implementation names and descriptive titles are
aliases, not replacement IDs. Use an evidenced original symbol when available;
for a stripped binary, use the established canonical disassembly symbol (for
example `FUN_00019A2D` or the project's existing `sub_00019A2D`), tied to the
hashed DOS build and verified entry/range. Such an address-derived symbol is a
recovered identifier, not a claim to know the original developer's source name.
Do not invent a friendly name and present it as ground truth. Disambiguate
identical names across builds/overlays with the DOS image and address-space
identity; retain aliases and evidence when a verified rename is necessary.

Splitting a DOS function into target helpers retains the parent DOS function
ID on each helper plus its mapped source range. A target routine implementing
several DOS functions lists their individual IDs; a composite label must not
erase their separate inventory entries. A true target-only adapter uses an
explicit target-artifact identity and `N/A - platform replacement`, never a
fabricated DOS function ID. Missing or ambiguous DOS identity leaves a game
function `Unproven` until the boundary is recovered.

The same record must contain a **difference ledger against the DOS function**.
For every difference, name the original behaviour or mechanism, the browser
and/or Falcon replacement, the reason it is necessary, its §4.2 category, and
the fixture or target measurement that proves valid-input behaviour remains
equal. This includes CPU-width/signedness/endianness/alignment decisions,
operating-system and hardware substitutions, timing or buffering changes, and
deliberately unsupported cases. If there is no behavioural difference, say so
explicitly and cite the equality fixture; silence is not evidence of fidelity.
An unresolved difference is `Unproven`, remains visible in the record, and
cannot enter a supported path.

Use one stable record location per project (for example
`analysis/functions/<canonical-id>.md` or a checked-in function ledger) and
give every record this minimum shape:

| record part | required content |
|---|---|
| DOS identity and evidence | canonical ground-truth DOS function name as function ID; shipped-file SHA-256, canonical range/entry, build/variant, evidence grade, and the DOS capture or observation |
| recovered function | purpose, callers where known, inputs/preconditions, outputs, state and external side effects, ordering/arithmetic/format rules, and fixture IDs |
| implementations | browser symbol/file and 68000 symbol/file, or an explicit `not implemented` / `out of declared scope` state; for 68000 code also record exact CPU/toolchain/ABI, build command/configuration, object/listing/disassembly evidence and emulator/Falcon fixture result; never omit the function |
| difference ledger | each source-to-browser/target change, its category and reason, equality fixture or hardware measurement; explicit `none` when no change exists |
| open work | unproven readings, unsupported states, next measurement, and release-path status |

Every JavaScript/browser and 68000/m68k function source that implements or
exposes a recovered DOS function must carry an adjacent source comment or
docstring linking to the durable function record and naming the disassembled
DOS function symbol and canonical range/entry (for example,
`DOS: FUN_0000_1234; record: analysis/functions/0000-1234.md`). The `DOS` name
is the function ID; use that exact canonical name in the record, both
implementation sources and fixture metadata. A separate
map, file-level comment or function-record link without the disassembled DOS
name is not sufficient. Code with no DOS counterpart must say
`N/A - platform replacement` or `Target artefact` at the definition.

Two things that are also invention, and neither looks like it at the time.

**A guard the original does not have.** Bounds clamps, range checks and
sanity tests added for safety are a *second behaviour* for input nobody has
checked against the first, and they hide which one is wrong. F030Comanche
2026-08-22: porting the campaign catalog at `0002A104` acquired two title
clamps and a range check on the campaign index, all three justified as
protecting the Falcon from malformed input. None survived review. The clamps
had no platform boundary behind them at all — `rep movsb` into a data blob
runs on into the following rows on DOS exactly as it does on a 68030 — and the
range check was guarding an index that is a byte read into a table with room
for every value it can hold, where the original's own outcome is a filename
that does not open. A guard belongs only where a genuine platform boundary
forces it, and then it is documented beside what the original does. The
legitimate shape of that is Comanche's `draw_span` surface clip: DOS wraps
inside a 256x256 buffer addressed as `ch:cl`, a Falcon framebuffer row is a
multiply, and an unclipped negative row writes 40 MB past the screen.

**Tuning code to close a gap against a measurement you doubt.** Fitting a
renderer to a bad oracle is inventing behaviour with extra steps, and it
destroys the traceability more thoroughly than a guessed constant because the
result *matches* and nobody looks again. Comanche's terrain sat 21-23 rows off
its DOS oracle through eight parameter fits — camera position, altitude,
projection scale, horizon curve, horizontal rescale, bearing shift, fan
half-width, collision restore — each moving the mean and leaving the spread.
No scalar in a projection can change the shape of a profile, so the fits were
the wrong instrument, and adopting any of them would have baked a fitted
constant into a path that is otherwise the disassembly. Establish what the
original produces first; §3.4 and §4.5 are how.

**A citation is only as strong as the disassembly behind it.** The rule above
is satisfied by naming an address — but an address in a region no one proved
was code cites a guess wearing ground truth's clothes, and Ghidra will return
a plausible `FUN_xxx+0y` for any address you ask about. Rank the authority in
the routine header, because the three are not interchangeable: **executed and
content-matched to the source object** under §3.5 is strongest classification
evidence for that scenario; **reached by evidence-backed control flow, covered
by the §2.4 ratchet and clear of the data guard** is strong static evidence;
**reached only by a sweep's inference** is weakest and says so out loud. None of
the three proves semantics without §3.6's contract. Porting from the third is
allowed — a lot of code is only ever reachable through paths a run has not
driven — but it is an unproven citation, and the honest response when it turns
out wrong is to go back to §2.3/§3.5, not to adjust the port.

**A recovered source tree is a fourth evidence rank, and the easiest one to
overrate.** For a port of a shipped DOS game, the hashed target DOS executable
and its observed execution remain the **sole behavioural authority**. When
someone else has already reconstructed the game's C source, phases 1–3 can
appear to be free and the port can start on day one — `../F030WC1` is planned
to work this way, from the `../wc1-re` reconstruction (neither is currently
present in this workspace; the WC1 working copy is a stub). The tree is useful, readable
supporting evidence, but it is a claim like any other and cannot overrule the
DOS binary. It carries two questions the three ranks above do not. Answer both
in writing before citing it, once per project, not once per routine:

1. **Which build was reconstructed?** `wc1-re` reconstructs *Wing Commander*
   as shipped in the 1996 *Kilrathi Saga* Win32 re-release. F030WC1 ports the
   **1990 DOS** game and reads DOS data files. Those are two builds of one
   game, and every difference between them is silently inherited by the port
   as if it were DOS behaviour. Nothing here says they differ much — it says
   the delta is currently unmeasured, and unmeasured is not zero.
2. **What is its fidelity, and is it graded?** `wc1-re`'s own `make report`
   scores per-function *machine-code similarity* against the retail
   executable, which means the tree is explicitly not uniform: some functions
   match closely, some are reimplementations that merely behave right. A
   citation to a 40 %-similar function and one to a 99 %-similar function look
   identical in a port header. Carry the score.

The required discipline is to keep the original DOS binary as the adjudicator:
when a reconstruction and the binary disagree, investigate the DOS evidence,
record the difference, and implement the DOS behaviour. F030WC1's
`analysis/wcexe.md` identified `WC.EXE` as the same Borland TC++ 1990 model as
UW1's `UW.EXE`, so the family's §2 machinery is available — though that file,
like the rest of the WC1 analysis tree, is absent from the current workspace
stub and the identification survives only in the family ledger. Say in the
function record which evidence was read and how it was checked against DOS. A
reconstruction is a shortcut through reading code, not a repeal of the DOS
oracle.

**Keep the substitution list closed.** Replacing DOS 6.2 calls, BIOS calls
and hardware access is legitimate and unavoidable; §4.2's *target artefact*
category exists for it. What makes it safe is that the list is **enumerated
in one place per project and reviewed as a whole**. The realistic failure
mode here is not a fabricated routine — the rule above catches that. It is
the substitution category widening one locally-defensible step at a time
until it has absorbed game logic, with every individual step looking like
plumbing. A list short enough to read in one sitting makes that drift
visible; substitutions decided ad hoc at each call site do not.

### 4.2e Start every port at the listing, not at the port

Confirmed by the project owner on 2026-08-27 as the standing workflow for
F030Comanche, and general enough to state here. The full form lives in that
project's `AGENTS.md`; the parts that are not project-specific:

1. **Open the routine in the listing before opening the port.** A port's own
   comment or TODO is evidence about the port, not about the original. One
   address sat recorded for weeks as "the HUD crosshair, not decoded" and is
   part of a path that was already ported.
2. **Check the cited entry is an entry.** A mid-instruction address is a
   misread boundary, and two records in that project named interior bytes.
3. **Split static from runtime by address.** Below the image's content
   boundary a table is transcribable; at or after it, the table exists only in
   a running program and must be captured.
4. **Never trust a shipped value as a runtime value.** The image shipped `1`
   for a display option the game overwrites with `2` at mission start, and the
   feature gated on it therefore never drew.
5. **Capture at an instruction, not an instant** - see the breakpoint entry in
   `CROSS-PROJECT.md`.
6. **Put the source address on the step, not only on the routine**, so a later
   reader can check one instruction without re-deriving the whole thing.
7. **Zoom before concluding a visual difference.** Two "gaps" logged off
   320x240 thumbnails were not gaps at all.
8. **When you stop, record the decode, not the intention.** "Port the right
   panel" is worth nothing; the handler table, the page index, the routine it
   dispatches to and what that routine does starts the next attempt from a
   specification instead of a hunt.

The rule underneath is 4.2: never write target code without the original's
routine in front of you.

### 4.2a Input-driver fidelity is mandatory

> **Non-negotiable rule for every child port:** run the authoritative DOS
> function and feed/read it through the same emulated DOS keyboard and
> pointing-device I/O contract. Do not invent input semantics or improve the
> game flow. Graphics and sound are the only broad mechanism exceptions.

Every port must preserve the original input path at the function and I/O
contract level. Recover the DOS keyboard and pointing-device interfaces that
the executable actually calls, then place a target-neutral input-driver seam
between physical/browser devices and the recovered game functions. The seam
may translate a browser `KeyboardEvent`, pointer movement, button transition,
or Falcon device packet into the exact driver-visible state and may translate
the driver's returned/event data back into the host representation. It may not
replace that path with direct menu helpers, synthetic game actions, injected
state changes, or a new event ordering.

The mandatory flow is:

```text
physical/browser device → emulated DOS driver/I/O contract
                         → recovered DOS function → recovered game flow/state
```

The browser must therefore model the recovered driver calls, data widths,
button/key state, motion or scan data, queues, acknowledgement/consumption,
polling/event timing, and relevant error/absence results. The exact set is
per-project evidence, not a guessed generic API. If the DOS build reads a
standard driver such as `INT 33h`, the browser and target must feed the same
documented subfunction results to the recovered caller; if the keyboard path
is not yet recovered, keyboard game input remains `Unproven` and must not be
used to invent a transition.

Keyboard shortcuts, mouse conveniences, accessibility controls and developer
buttons that the DOS game does not have may exist only as explicitly labelled
test-harness controls. They cannot enter a supported game path, alter the
authoritative state flow, bypass an unported function, or make the game flow
more convenient than the DOS flow. A browser keyboard adapter for a DOS
mouse-only screen is still required to terminate at the emulated driver and
the recovered DOS consumer; it is not permission to add keyboard navigation.

Graphics and sound are the only broad mechanism exceptions: Canvas/Videl and
audio backends may replace VGA/register or sound-device programming after the
canonical logical pixel/audio contract is recovered. Those substitutions may
change representation and hardware mechanism, but never the input-driven game
state or ordering. Every input-driver difference and every graphics/sound
substitution belongs in the function's difference ledger with its fixture and
status.

### 4.2b DOS timing and game-flow cadence are mandatory

The port must preserve the authoritative DOS execution pace wherever timing can
affect input sampling, scheduler callbacks, animation, audio events, frame
publication, races, or game state. Do not choose 60 Hz merely because the
browser or target display commonly presents at 60 Hz, and do not infer the game
tick from a monitor/VBL specification. Recover the actual DOS timing contract
from the executable and controlled DOS runs: PIT divisor and `INT 8` cadence,
timer-slot periods and accumulators, VBL waits, busy waits, and any other
timing-dependent ordering that the function record proves. Runtime values remain
runtime values; they must be captured from the DOS oracle or replay fixture,
not replaced with a convenient constant.

The mandatory flow is:

```text
DOS timer/VBL/input event order → recovered DOS function → game state/frame/audio
```

The browser and Falcon runners must therefore use an explicit, deterministic
tick/event scheduler whose tick source and periods are documented against DOS.
`requestAnimationFrame`, `Date`, `performance.now`, browser timers, host frame
rate, and physical VBL frequency may drive presentation or pacing of an already
scheduled replay, but may not define simulation order or silently drop,
duplicate, accelerate, or delay authoritative DOS ticks. Preserve drift-free
accumulator behaviour and the original input-poll/acknowledgement position
within the tick whenever those are proven.

If the DOS cadence or its relationship to display refresh is not yet recovered,
the timing path is `Unproven`. A fixture cadence may keep a diagnostic page
watchable, but it must be labelled as a harness/presentation artefact and must
not be described as DOS game-flow parity. The current presentation target may
be 60 Hz for the Falcon display, but that is a graphics target, not permission
to alter DOS game timing. Every timing substitution and measured difference
belongs in the function's difference ledger.

### 4.2c Preserve the DOS function body; do not add defensive behaviour

> **Non-negotiable rule for every function-level JavaScript counterpart:**
> reproduce the recovered DOS function's behaviour and side effects as
> directly as practical. Do not pollute it with error checking, assertions,
> validation, clamps, defaults, retries, logging-driven branches, or other
> defensive behaviour that the original function does not have.

If the DOS function has no error handling, the counterpart must not acquire an
invented error path. Preserve its real fall-through, return values, register
widths, wrapping/overflow, side effects, ordering, and documented behaviour on
invalid or unsupported inputs. If an invalid-input case cannot be safely or
meaningfully represented in the host, record it as `Unproven` or `Unsupported`
instead of silently improving the function.

Keep the layers separate:

```text
DOS-function counterpart: recovered behaviour only
host/target boundary:     necessary API or memory-safety adaptation
test/fixture harness:     assertions, hashes, diagnostics and failure reports
```

Assertions and checks are encouraged in build scripts, contract fixtures,
parity comparators, file-import boundaries and target-ABI validation. They must
not execute as new semantic branches inside the DOS-function counterpart or
change its outputs for valid DOS inputs. A host-boundary check that is required
to prevent a browser or target crash is a documented target artefact and must
not be presented as original DOS error handling. Comments linking the function
record remain required; comments are not a substitute for preserving the
function's actual behaviour.

### 4.2d Trace the milestone route before generating sources

Before creating or changing browser or m68k source for a milestone, run the
authoritative DOS path under execution tracing (§3.5's TCG plugin, or
`-d exec,nochain` logging where the plugin is unavailable — that locates the
route; per-byte coverage still belongs to the plugin) with repeatable inputs
and state/memory snapshots. Record reached function entries, indirect
callbacks, resource reads/pointers, state transitions and frame order in a
durable, committed route manifest. Generate only the contracts represented by
that route's dependency closure; a statically possible edge missing a required
witness remains an explicit blocker, not an exclusion (§0.1, §2.6). Unreached
or unexplained code stays `dormant`/`Unproven` and cannot support the milestone.
Browser and target experiments validate the route; they do not define it.
*(CMN, 2026-08-25; its attract-route trace is
the worked example.)*

### 4.3 Do not bake in the target

Declare the lowest supported machine and its resource envelope early (§4.6a),
and defer backend-specific choices until the logical contract is known. Keep a
seam:

```
src/common/            target-neutral, lowest-common-denominator CPU
src/target/<name>/     one directory per back end
```

Put the seam at the narrowest **observable, target-neutral representation** the
original exposes before hardware adaptation. For an indexed game this is
normally an 8-bit indexed surface plus palette: common code draws indices, and a
back end alone turns them into hardware pixels. For a true-colour renderer,
audio sequencer or input path, choose the equivalent logical pixels, events or
actions rather than forcing an indexed-video abstraction. POR's indexed contract
is eight symbols; the principle, not that exact representation, is portable.

Enforce it mechanically, or it erodes:

- Assemble `src/common/` for the **lowest** CPU you might target. On 68000 a
  misaligned word access is an *address error*, not a slowdown, so if a plain ST
  is live the shared code must be 68000-clean from day one.
- Keep hardware constants out of the shared header, and **fail the build** if
  they leak in.

On the data side, the same seam applies. For indexed graphics, keep pixels
target-neutral (one byte per pixel), encode only the palette per target, and
record that encoding in the cache header so a wrong-target asset is refused
rather than shown wrong. Give other asset caches the equivalent representation
and target tags.

### 4.3a A browser/JavaScript game reference is mandatory

#### Agent rule: JavaScript is the executable semantic reference

The required workflow is:

```
hashed DOS executable + captured execution
  → recovered function/data contracts
  → DOS-validated JavaScript reference
  → native m68k implementation of the same contracts
```

JavaScript is the executable reference in the middle, not a new authority or a
required runtime on the Falcon. Agents must implement and exercise each
supported recovered function in that reference, validate its canonical outputs
and side effects against DOS evidence, then use the same fixtures to validate
the native target. Browser and target work may develop together, but a target
function cannot enter a supported path before this reference gate passes.
Both implementations retain direct links to the same DOS function record;
agreement between JavaScript and m68k cannot settle a disagreement with DOS.

This is semantic porting, not a mandatory x86-to-C-to-m68k compiler pipeline.
C-like pseudocode may aid recovery; it does not replace the executable
JavaScript reference. The current target may be hand-written m68k assembly;
there is no requirement to translate JavaScript mechanically or ship a
JavaScript engine. Preserve DOS widths, signedness, overflow, shifts,
rounding/truncation, sequencing and byte-order contracts explicitly (§4.1,
§4.4). CPU instructions, native storage and documented graphics/sound adapters
may differ while preserving the declared behavior. Target-only hardware
adapters retain the explicit Target artefact boundary and logical reference
model required below; they do not justify skipping a game-function counterpart.

**Every child project must build and maintain a browser-based JavaScript game
runtime as a phase-4 deliverable.** Start it with the first ported function and
grow it with every supported slice. The browser page itself is the playable
game/reference runtime: it boots the DOS-derived data boundary, owns the
deterministic runner, accepts game input, advances game state and presents the
canonical logical framebuffer, events and audio model. A diagnostic asset
viewer, screenshot gallery or isolated canvas demo may accompany the runtime,
but cannot satisfy this requirement. By the time a supported path reaches the
Falcon, the same game path must be runnable and deterministically testable in
the browser runtime.

#### Connected game-flow acceptance gate

An incremental browser slice is not complete merely because its JavaScript
functions pass when called from a test page. Every function marked **supported**
must be wired into the single browser game runtime together with all earlier
supported functions. The page must boot without a developer-only harness, accept
the declared input path, and reach the game's real startup flow — at minimum the
main menu or a deterministic attract-mode loop, whichever the DOS build exposes
first. The acceptance fixture records the ordered ticks/inputs, state
checkpoints, logical framebuffer/page hashes and emitted events needed to enter
and leave that flow. A function may remain an isolated `Identified` or
`Unproven` experiment, but it cannot be called part of the supported browser
port until this connected-flow gate passes.

This mandate creates an increasingly complete JavaScript port as a by-product
of the function-by-function process. It is a **host reference plus
target-artifact prototype**, not permission to fork game behaviour or declare
the Falcon done. It neither replaces the DOS oracle nor establishes that a
Falcon implementation, its Videl programming, its timing, or its performance is
correct.

The authority remains the same as for every other ported routine: the **hashed
shipped DOS executable for the target build**, its observed execution, and the
§3.6 behavioural contract recovered from them. A disassembly, reassembly,
decompiler output, recovered source tree and JavaScript model are evidence or
implementations; none may overrule the DOS binary. Each JavaScript function
cites that contract and is subject to §4.2's Grounded / Target artefact /
Unproven classification. A browser model may make an unknown visible; it must
not fill the gap with a plausible rule or tunable constant.

No target routine may be the only executable version of a recovered supported
function. Before it enters a supported Falcon path, its browser counterpart
must run the same contract fixtures and expose the same declared outputs and
side effects. A target-only hardware adapter is permitted only when it is
explicitly a §4.2 Target artefact; its logical input/output model still belongs
in the browser harness.

#### Keep four layers separate

1. **Semantic core.** Function-by-function implementations of recovered game
   behaviour, with no DOM, Canvas, wall clock, random source, file picker or
   browser event dependency. It consumes and produces the same contract-level
   values, state changes, command streams, files, or logical pixels that the
   68000 port will consume and produce.
2. **Explicit machine model.** Testable logical and target representations:
   memory/pointers where required, indexed surfaces and palettes, RGB565 or
   planar pages, pitches, dirty regions, page publication, input queues and
   audio-event queues. This is where an intended Falcon layout is modelled; it
   is a target artefact and cannot change game semantics.
3. **Deterministic runner.** A caller-controlled tick/event scheduler that
   replays recorded inputs and seeds every permitted source of randomness.
   `requestAnimationFrame`, `Date`, `performance.now`, browser timers, and DOM
   event arrival may drive presentation, but never define simulation order or
   become test input directly.
4. **Browser adapter.** Thin Canvas, audio and input adapters. The input
   adapter first implements the emulated DOS keyboard/pointing-device driver
   boundary; Canvas and audio adapters then translate the explicit logical
   model to browser APIs and back. Canvas drawing primitives, compositing, CSS
   scaling, colour management and screenshots are never canonical game output.
   The browser page uses these adapters to run the game; diagnostic overlays
   and fixture panels are subordinate, switchable views and must never replace
   the game runtime.

The core and machine model must also run headlessly, so a regression does not
depend on a browser, a monitor profile, a GPU path, or visual inspection.

#### Browser input boundary: emulate the DOS driver, do not improve the flow

Browser device events are transport data only. The browser adapter must feed
them into the emulated DOS keyboard/pointing-device driver contract, and the
semantic core must call the same recovered input functions or consume the same
driver-visible queue/state as the DOS build. The adapter must preserve the
documented units, widths, signedness, button/key transitions, queue ordering,
polling or callback timing, acknowledgement/consumption and error results.
Where the DOS executable uses `INT 33h`, for example, an adapter is allowed to
turn pointer motion into the exact `INT 33h` position/motion/button results; it
is not allowed to call `select_character()` directly because a DOM click
occurred.

This rule applies equally to keyboard and mouse. A browser-only shortcut may
be useful for a test harness, but it must be visibly labelled, excluded from
the supported game-flow fixture, and unable to create a transition that the
recovered DOS functions would not create. If a device/driver contract has not
yet been recovered, that input path stays `Unproven` and is not replaced with
guessed keyboard navigation, synthetic clicks, or direct state mutation. The
only broad mechanism substitutions are graphics and sound backends; their
logical output contracts remain subject to the normal DOS fixture chain.

#### Browser file boundary: emulate DOS, persist locally

When the DOS program opens files, the browser reference must expose a
deterministic **virtual DOS filesystem** to the semantic core. Its minimum
boundary is named byte files plus explicit `open`, `read`, `seek`, `tell` and
`close` semantics, with the original path normalization, case rules, file
positions, short reads and relevant errors documented in the function record.
The core must not call `fetch`, `File`, `FileSystemFileHandle`, IndexedDB or
`localStorage` directly.

Use browser persistence only behind that adapter:

- **IndexedDB** stores imported DOS binaries/assets, target caches, save files
  and other binary blobs as `ArrayBuffer` records. Store the canonical DOS path,
  size, source/build variant and SHA-256 beside each blob.
- **`localStorage`** stores small metadata only — selected install/profile,
  source hashes, schema version, preferences and cache indexes. Never put game
  binaries, framebuffers or save payloads there.
- A **host import adapter** may use `fetch` for a local development server or
  a file picker/File System Access API for legally supplied user files. Import
  and hash the bytes once, then run the semantic core from the virtual
  filesystem so later tests do not depend on URL layout, network availability
  or asynchronous arrival order.

The adapter must support a clean in-memory mode for headless tests and a
versioned persistent mode for interactive sessions. Clearing or migrating the
browser store must not alter the canonical fixtures. A cache hit and a fresh
import must expose identical bytes, hashes, paths, file positions and errors;
that equality is itself a filesystem fixture. Persisted user data remains
outside the repository and does not become a substitute for the hashed DOS
oracle.

#### Make it the day-to-day differential laboratory

Use the browser harness as the most convenient **ongoing** test vehicle for the
port. It should make a difference in a recovered function visible before that
difference becomes an unexplained difference in an integrated Falcon frame. It
does this by consuming structured checkpoints, not by asking a person to decide
whether two canvases “look close”.

It is also an **analysis instrument**. Build a small, controllable browser
experiment around an incompletely understood DOS function or subsystem: expose
its inputs and pre-state, single-step or replay deterministic calls, inspect
changed state/memory/events/logical pixels, and vary one documented condition
at a time. This makes the function's role, contract boundaries, coupling and
likely Falcon seam easier to identify before writing 68000 code. The experiment
may generate a hypothesis; it does not settle one. Promote an observation into
the function record only after a DOS capture, disassembly evidence, or another
explicitly graded source supports it. Keep the browser experiment and its
resulting fixtures, so the investigation becomes a permanent differential test
rather than disposable bring-up code.

For every ported function that can be called or replayed at a stable boundary,
keep a fixture with its source/contract identity, inputs and required pre-state,
then record and compare its return value, changed memory/state, emitted events,
and any affected logical-framebuffer rectangle. For a function that cannot be
injected directly on DOS, use §3.6's captured entry state or test the nearest
stable subsystem boundary instead. The harness must report the first differing
field, byte, event, or pixel with its coordinate/offset and expected versus
actual values; a Canvas diff heatmap, side-by-side page, trace view, memory
diff, and state timeline are diagnostic views of that structured result.

Gameplay tests are the same mechanism at a larger boundary: replay a recorded,
ordered input sequence against a deterministic tick schedule and compare named
checkpoints — world state, player state, RNG state where observable, inventory,
messages, audio events, render commands and canonical frame/page hashes. A
function-level regression, a renderer-region regression, and a complete
gameplay scenario therefore use one fixture format and one comparator rather
than separate ad-hoc browser demos.

The comparison chain remains deliberately two-sided. First establish DOS
capture → browser reference equality for a scenario or function contract. Then
compare browser reference → target output from the 68000 build or target
emulator, importing its canonical state/frame/event capture into the same
browser report when useful. A browser can display and localise a target failure;
it cannot manufacture the target result or substitute for the real-target run.
Use §4.5a's first-divergence procedure when a connected replay differs; retain
the last equal checkpoint so diagnosis starts before the visible symptom.

#### Model semantics, not instructions

Do not build a JavaScript 68000 emulator or a second instruction-by-instruction
translation. “68000-like JavaScript instructions” are permitted only as small,
named semantic helpers inside function-level implementations. Model the
original's required x86 behaviour exactly — widths, signedness, wraparound,
division, shifts, fixed point, flags when observable, aliasing and ordering —
then make the 68000 constraint explicit at the target boundary. In particular,
an x86 unaligned source read is still modelled as its documented bytes, while a
68000 word/long access that the target implementation makes must assert its
alignment instead of silently succeeding as JavaScript would.

Provide named helpers for `u8`, `s8`, `u16`, `s16`, `u32`, `s32`, shifts,
fixed-point multiply/divide, explicit little-/big-endian reads and writes, and
checked addresses. Do not rely on JavaScript's implicit `Number` coercions,
signed 32-bit bitwise narrowing, typed-array host byte order, `NaN`, or
out-of-range array behaviour to approximate either CPU. Use byte arrays for
bytes/pixels, `DataView` for explicitly endian numeric fields, and isolate any
wide-integer calculation in a tested helper (`Math.imul`, split words, or
`BigInt`, according to the required width). The helper's result, rounding and
overflow rule are part of the routine contract.

#### Test the model below Canvas

Run the same §3.6 fixtures through DOS capture → host reference → target
routine as §4.5 requires. Compare declared outputs and side effects, then raw
logical framebuffer bytes, raw target-page bytes, or one documented canonical
representation. Define byte order, pitch, palette encoding, clipping and page
selection in that comparison. Canvas may convert indexed pixels or RGB565 to
browser RGBA for display, but a screenshot, browser pixel readback, or an image
with a tolerance is not the regression oracle.

A passing browser harness proves only that its semantic core, its explicit
machine model, and their fixtures agree. It cannot prove real 68000 code
generation, register preservation, stack use, alignment faults, VBL/page-flip
atomicity, Videl/DMA register values, CRT/VGA timing, audio latency, memory
visibility, or performance. Those remain target tests and measurements under
§4.5–§4.8. Keep the browser reference after the 68000 implementation lands: it
is a fast differential test, not disposable scaffolding.

### 4.3b Use bounded translation to remove repeated transcription

Native code may be emitted mechanically from a verified decode or a small,
typed representation of recovered contracts. Prefer this when repeated
arithmetic, addressing or calling idioms otherwise need to be rewritten and
reviewed by hand. A full x86 translator, a new intermediate language, and
mechanical JavaScript-to-m68k compilation are not required. Generated native
code implements the same contracts as the mandatory semantic JavaScript
reference (§4.3a); it does not bypass that reference or the DOS oracle.

A lowering rule records its input domain, widths/signedness, flag dependencies,
byte order, aliasing/memory effects, exits and helper ABI. Keep game addresses
and supported variants in evidenced per-build data, not hidden emitter
exceptions. Decode against the actual source bytes and load context (§2.6);
readable listings assist placement and classification but cannot override those
bytes. An unverified listing width remains unverified even if the line has a
plausible mnemonic. Share machine-readable identities and fixture schemas
where helpful; expected results always come from retained DOS evidence.

Every generated build retains:

- source/build hashes, map and contract versions, generator/helper revisions,
  options and the exact target toolchain; identical inputs must reproduce its
  generated sources and maps;
- mappings from emitted routines/blocks and linked target PC ranges back to
  canonical DOS IDs, source ranges and contexts, plus the adjacent source
  annotations required by §4.2; synthesized helpers are explicit target
  artefacts or retain their parent DOS identity;
- separate reports for decoded, implemented and DOS-validated coverage, and
  every unsupported operation, unresolved entry/exit, indirect target or code
  variant, with its blocking route and next experiment; and
- the CPU-restricted assembly and execution evidence from §4.1a, and the same
  DOS fixtures passing through JavaScript and native code.

Unknown translation must never become a no-op, default result or successful
return. Diagnostic builds should stop at the translation/runtime boundary with
the DOS site/context, attempted operation/target, relevant state and matched
build identity. These stops are target/harness artefacts outside recovered
function semantics (§4.2c); they expose unsupported execution, not invented DOS
error handling. Support still requires no unresolved item reachable in scope.
An empty miss log or a run reaching its timeout is not a closure proof.

Validate each new lowering/helper rule with DOS-derived cases that distinguish
it from the plausible wrong implementation, then replay the affected connected
route. Include carry/borrow/overflow, signed shifts, address wrap/segment
crossings, aliasing, stack effects and helper clobbers where relevant. A
generator shared by two implementations can give both the same bug; their
agreement alone never establishes correctness. Preserve the semantic
JavaScript implementation as a readable contract, not an instruction emulator
or an unchecked copy of the native emitter.

Shared lowering/validation tools live in `validation/` (see its README and
`analysis/stearcade-implementation.md`). Flag optimization must preserve unknown
call/return requirements and conditional writes; reuse native CCR only over
proven entry boundaries and flag effects. Exercise the production emitter with
discriminating opcode/sequence tests, retain an equivalent conservative
mechanism for diagnostics, then run the same DOS/JavaScript/native contracts.
Compare at original logical checkpoints, not elapsed host or target time; never
hide missing state with equal nulls or mask stack/flag bytes without an
observation/aliasing proof. Attribute measured target costs through maps bound
to the exact source/generated/linked build and report per logical game tick or
declared checkpoint. Synthetic/simulator gains do not establish game or Falcon
hardware performance. These analysis tools do not replace any acceptance gate.

### 4.4 Decode, don't transcode

**Byte order changes storage, not the numerical value.** DOS x86 is
little-endian; MC68030 and MC68060 are both big-endian. Decode original file,
replay and captured-memory fields with their declared DOS byte order, width
and signedness, then store native target values. For example, DOS bytes
`78 56 34 12` represent `0x12345678`; a native m68k long stores that value as
`12 34 56 78`. Arithmetic registers do not need byte-swapping. A signed
16-bit axis still has exactly the same sign and range after decoding.

Define a representation at every boundary: original DOS bytes, decoded game
state, generated target tables, framebuffer and optional DSP messages. Decode
once at each boundary; do not double-swap preconverted tables or reverse text,
palette-channel bytes, compressed tokens or arbitrary whole structures. Encode
DOS-compatible output back in the DOS format. Cross-platform memory comparisons
must normalize fields explicitly, and browser readers must specify byte order
rather than inherit typed-array host order. Use non-palindromic numeric fixtures,
signed limits and mixed byte/numeric records so an accidental swap cannot pass
on zeroes alone. CMN's loaders and replay checks are indexed in
`../F030Comanche/analysis/functions/cpu-compatibility.md`.

Converters parse the original records field by field and emit the target's
representation. Never memcpy a DOS record and byte-swap in place — that bakes the
source layout into your output and makes a target change expensive.

- Emit big-endian for 68k targets; byte order is a property of the *output*
  stage alone.
- Store values, not encodings: unpack bit-packed pixels on the host.
- **Widen representation, not semantics.** A stored 24-bit archive offset may
  become an aligned u32 because `move.l` is one instruction instead of three;
  an accumulator that wraps at 16 bits may not. Document the original width and
  insert explicit masks/sign extension where the target type is wider. A blanket
  byte-swap is never the answer: in bitmaps, text and RLE streams byte order is
  *structural*, not numeric. (F29 `docs/ARCHITECTURE.md`.)
- **Align explicitly — this matters more than endianness.** DOS records are
  often odd-sized (POR: 285, 63 and 9 bytes), so in an array every other record
  lands on an odd address.
- The decoded original layout stays documented and is **never** edited to suit a
  target.

### 4.5 Verify through a chain of independent comparisons

Use the strongest equality each boundary permits:

1. **Original asset → host decoder.** Apply §1's corpus checks and compare the
   decoded logical values with an independent reader, original routine or
   observed output.
2. **Original execution → behavioural fixture.** Capture routine/state vectors,
   event streams, files or normalized frames from the scenario in §3.4.
3. **Host reference → target routine.** Feed identical fixtures to both and
   compare outputs and declared side effects. Include edge cases for wrapping,
   signedness and alignment; add deterministic generated valid cases where the
   contract permits them.
4. **DOS scenario → target scenario.** Replay the same ordered inputs and compare
   the observable checkpoints. Normalize only platform representation — palette
   encoding, pitch, bitplanes, audio sample format — never game state or content.

Require byte equality when both sides have the same representation. Otherwise
compare a documented canonical representation. A numeric tolerance is allowed
only when the original contract itself permits a range; it is not a way to make
an unexplained error pass.

F030POR's `make title-smoke` boots the emulator, captures the published page at
a vertical-blank breakpoint, and compares 128,000 bytes. Say precisely what that
proves: it shows the target and host renderer agree — it does **not** prove the
host model matches DOS. The DOS oracle and the first comparison above close
that other side of the chain.

**Probe the active vector base before accepting a VBL capture.** On 68020/030+
targets the live exception table may be relocated through VBR; writing address
zero's vector slot can appear to succeed while the CPU continues through the
OS handler. That failure can make a `savebin` capture look like renderer
corruption when it is actually the desktop or another stale page. Install and
restore through `VBR + vector_offset`, record both the live vector and the
published page base, and make the capture prove that the dumped page lies in
the target-owned allocation. If an OS VBL handler is chained, verify whether it
also rewrites the presentation base and, if so, publish only in a post-chain
trampoline before the exception return. F030WC1 established this on
Falcon/TOS 4.04 (2026-09-10): a physical `$70` update left the live VBL chain
untouched until the port read VBR; the now-live TOS VBL then overwrote a
pre-chain page base. This is target-platform evidence, not a substitute for
the DOS timing contract.

Once one result compares equal, keep the fixture and full output as the golden
regression artefact, plus a hash for the fast pass. F29 shipped three
register-clobber bugs of identical shape — a black frame, glyphs landing in I/O
space, one character per string — none visible by reading the code, all visible
in a rendered frame. A stored hash of the captured buffer at a fixed VBL catches
that class immediately; retaining the buffer and a diff tool makes the failure
diagnosable. *(F29 `docs/MENU.md`.)*

### 4.5a Find the first semantic divergence

Compare the original and the port at the same logical boundary, with identical
canonical initial state and ordered input/timer events. Record the DOS function ID,
checkpoint phase, completed game updates, interrupt/event position, RNG state
where relevant and resource/code-instance identities. Capture related state,
logical pixels and events at that boundary, or retain a replay log that
reconstructs that exact state. Registers from one tick and memory from a later
tick do not form a valid fixture. Host VBL counts, elapsed seconds and the
closest-looking screenshot are not alignment keys.

Use inexpensive per-region hashes to find the first unequal checkpoint. Keep
full states around the last equal and first unequal point; narrow that interval
with additional deterministic checkpoints. Diff fields/bytes, watch the first
incorrect write in DOS and in the implementation, and map its writer back to
the canonical function and source range. Recover the missing rule, preserve
the reproducing case, fix it and replay the cumulative route. This is the
default response to a visual mismatch before adjusting rendering constants.

Compare game state, event/command streams and logical rendering separately.
An exact renderer comparison from port-produced state only validates rendering
of that state: CT's snapshots could match its C renderer while game scripts
were starved. Independent SNES execution later exposed timing drift and an
incomplete attract cycle. In this family, captured DOS execution closes that
independent side; a second model sharing the port's scheduler or hardware
helpers cannot do so alone.

Any excluded field needs an exact range, reason and evidence that it cannot
affect future observable behaviour. Do not mask timing, RNG, stack or audio
state merely to get equal hashes; stack contents can implement dispatch or
coroutines. Representation normalization follows §4.5. Nearest-frame searches
and tolerant images may locate symptoms, but are diagnostic only and cannot
satisfy the parity gate. Retain failures, unmatched checkpoints and exclusions
in the report instead of counting only comparable pictures.

Extend replay to semantic completion: a full in-scope attract cycle, entering
and leaving the next interactive state, or the equivalent route landmark.
Report completed game transitions separately from host frames. Do not import
CT's NMI synchronization, lag limits or approximate scanline model as DOS
policy; the original's interrupt/input ordering must be recovered (§4.2b).

### 4.6 Slice the port, and let each slice prove itself

F29 is the family's worked example of phase-4 delivery (`docs/ENGINE.md`,
`docs/HUD.md`, `docs/MENU.md`); its habits transfer:

- **Cut the port into numbered slices, each landing as one commit with its own
  evidence note and observable result.** A result may be a frame, state
  transition, audio-event stream or save file; visual rendering is not the only
  oracle. A pure refactor proves itself by leaving all existing fixtures equal.
- **Land the browser reference and its deterministic fixtures before or with the
  target half of every slice.** A Falcon-only implementation cannot enter a
  supported path. The browser reference is the interactive differential lab;
  target capture is the independent hardware check (§4.3a, §4.5).
- **Name the integration point by symbol** — "Return on START clears
  `menu_active`, which is the integration point" tells the next slice exactly
  where to plug in, and why that is sufficient.
- **Make scaffolding self-checking and label it as a target artefact.** F29's HUD
  drives its three fields from `frame_count` through three *different* formulas,
  so each can be inverted back and all three must agree — a pipeline check that
  does not claim the formulas came from DOS. Scaffolding is replaced, not
  silently promoted, when the behavioural slice lands.
- **Measure after correctness, don't calculate.** F29's first bottleneck was not
  the video mode the arithmetic pointed at; it was a 153 KB backdrop copy per
  frame. "Fill cost dominates, not object count" (25.0 fps for sixteen objects,
  11.6 fps for one screen-filler) is the kind of fact you want *before*
  optimising the wrong end. Run the same behavioural fixtures before and after
  every optimization.
- **Prefer a change in the offline converter over a change in unfamiliar hot
  target code when it preserves the logical asset contract.** F29 turned
  degenerate 2-corner line faces into thin quads at conversion time rather
  than teaching the DSP edge-walker about zero-width spans — the proven
  pipeline stayed untouched. A diagnostic converter flag such as
  `--no-line-quads` may preserve the experiment and reference fixture, but it is
  not a second shipping behaviour; release assets come from one recorded mode.
- In assembly, **document register ownership at every public routine** —
  which registers a caller may rely on surviving the call. All three F29 menu
  bugs above were this, and each routine was correct in isolation.
- At every slice boundary, document the data/ABI contract, ownership and the
  symbol where the next slice attaches. Test that boundary independently before
  relying on an end-to-end frame to localise failures.

### 4.6a Check feasibility early; optimize after parity

At slice planning, name the minimum machine: CPU/clock, usable RAM, display
mode, required DSP or other hardware, and the recovered simulation cadence.
Record a resource budget before committing to representations. Include resident
code/data, peak simultaneously live assets, decoded and converted copies,
framebuffers, queues, stack and scratch space. For DSP work, include program
and X/Y storage plus CPU packing, transfer, waiting and composition costs.
Separate one-time loading from steady-state work; an average frame or a title
screen allocation does not establish the worst case for gameplay.

Early estimates and isolated transfer/fill probes test feasibility; label them
as estimates or target artefacts. They do not establish game fidelity or an
achieved frame rate. After the first correct connected implementation, measure
the same route on the minimum target, retaining its machine configuration,
peak memory/stack usage and stage timings. Distinguish emulator measurements
from physical Falcon measurements. State the required headroom and evidence
for it rather than adopting an unexplained family-wide percentage.

If the budget fails, isolate the largest measured cost, change one mechanism,
and rerun the same parity fixtures and resource measurement. CPU/DSP movement,
caching and asset conversion each retain the DOS logical contract and their
transport/ownership costs. A faster average must not conceal tick loss, input
reordering or a peak allocation failure. If the supported machine cannot meet
the contract, report that feasibility blocker or explicitly revise the support
matrix; do not change game behaviour to make the benchmark pass.

For translated code, measure context/code growth and helper overhead as well
as rendering. Use liveness, block fusion, direct memory/I/O paths or native
loop replacements only with complete entry/exit and clobber contracts,
including indirect callers, interrupts and unusual returns. Retain a
conservative implementation for differential diagnosis; both mechanisms must
satisfy the same DOS contract. Test combined changes as well as isolated rules:
the SNES ports initially blamed precise flag liveness for a carry-merge bug in
the emitter. Report game updates, interrupt delivery, input consumption and
published pictures separately; faster rendering cannot establish game pace.

### 4.7 Audio: port the interface, not the code

Deferred here, but F29 has walked it (`docs/SOUND-DRIVER.md`,
`docs/ADLIB-BACKEND.md`, `docs/MPU401-BACKEND.md`): an era-typical DOS driver
is one entry point (`AH` = function, `AL` = parameter) dispatching to
per-device tables — so the target's audio slots in as *one more device table*,
and the sequencer stays device-independent exactly as the original is. Read
the thinnest back end for structure (MPU-401: it sends events) and the richest
for musical meaning (AdLib: OPL2 register semantics named every opcode). The
validation trick that paid for the whole chapter: patterns are not
self-terminating, so deriving extents independently from the sequence table
and requiring all 74 to tokenise *exactly* onto their boundaries validated 27
opcode definitions at once.

### 4.8 The final port gate

"It boots" is the beginning of integration, not completion. Before calling a
supported path ported, require:

- a clean build from hashed pristine assets with recorded tool versions;
- a maintained inventory of every recovered DOS function; functions outside
  the declared route remain explicitly identified, unproven or deferred, not
  counted as supported;
- the slice dependency closure (§0.1, §0.3), including callbacks, state
  producers and validation tools, with no required edge missing or stale;
- for generated code, reproducible inputs/maps and a reviewed unresolved-work
  report (§4.3b); dispatch extents and runtime code variants are evidenced;
- full-corpus tests for every required converter and no unexplained trailing or
  skipped data;
- no `Unproven` item reachable on that path;
- a reviewed, closed list of platform substitutions and known deviations;
- a browser/JavaScript reference that deterministically exercises the supported
  path through its function and scenario fixtures, with its outputs equal to
  the corresponding DOS captures wherever comparison is possible;
- host/target equality for the slice's routine and state fixtures;
- replay of the corresponding DOS and target scenarios at the same logical
  checkpoints, with coherent state captures and semantic completion rather
  than only a host-frame limit (§4.5a); and
- measured timing, memory and stack headroom on the lowest supported target.

Publish the support matrix and failures as precisely as the successes. A port
may intentionally ship with unsupported paths, but a limitation is named with
the scenario that exposes it; it is never hidden behind the word "complete".

---

## 5. Practices that paid off regardless of phase

**One reproducible command and evidence record per claim.** Every number in the
docs comes from a target: `make reasm`, `make test`, `make title-smoke`,
`make decompile`. The record names the claim/status, source hashes and address
space, command/tool version, fixture or scenario, result and last verification
date. A claim you cannot re-run is a claim you cannot defend after a refactor;
an address without its image hash and mapping is not a durable citation.

**Write the tool lesson down the moment it bites.** `analysis/tools.md` is the
highest-value file in the project per byte. Examples that each cost real time:
capstone's `lcall` operand order; a TOS executable enters at the first byte of
TEXT so **link order picks the entry point** and `-e` does not override it;
Homebrew's `openjdk@21` is keg-only so Ghidra aborts with no TTY to prompt on;
`brew install ghidra` is a formula, not a cask.

**Correct the record when you find you were wrong.** POR's docs carry several
corrections — a "53-entry trailer table" that turned out to be a fixup block, a
commit message that overstated what was recorded. Leaving a wrong claim in place
because it is embarrassing to fix is how a project's documentation stops being
usable. F29 practises the strong form, worth copying whole: withdraw **in
place**, quote the old wrong reading, say **why it looked right**, name what
always contradicted it and nobody noticed — and if the doc is a generated or
mirrored copy, flag that the fix has not yet reached the upstream, or the next
regeneration reinstates the error. Re-reading a routine you have already
written up is first-class work, not rework; F29's history is full of "I had it
backwards" commits, and each one made the corpus more trustworthy, not less.

**Treat a parallel worker's output as a claim, not a result.** F29 merged an
independent worktree's findings by (1) re-running the tool *in that worktree*
to verify the metric mechanically, (2) spot-checking the two most valuable
findings against independent prior work, then (3) auditing everything else
address by address from raw bytes. Roughly half was rejected — including a
seed that the same source material's own prose called data. Rejections were
recorded as comments beside the seeds so nobody re-adds them without cause: a
worklist says where to work, anti-seeds say where not to.

**A wrong result from a check is sometimes a measurement bug.** Before
changing code because a check failed, confirm the check measures what it
claims — F29's cleanest instance ran the *unmodified original* through the
same capture pipeline and got the same garbage, which acquitted the port in
one control experiment. (A frame grabbed too early shows the TOS desktop; a
rate divided by the wrong interval is plausible and meaningless.)

**Instrument the path that actually runs; a duplicated code path defeats a
single counter.** Comanche's object investigation produced *two* confident
wrong conclusions from counters that were on the wrong instance of a
duplicated block - first "the fixed-type gate explains it", then "no mission
placement is ever installed". Both were overturned by moving the same counter
a few lines. `object_spawn_mission` has two `object_factory_install` call
sites and the counter sat on the branch that never runs. **Before trusting a
zero, grep for other call sites of whatever you are counting.** And prefer an
instrument that dumps several values at once over one that shows a single
number: with one number there is nothing to contradict a wrong placement.

**A degenerate sample confirms every hypothesis and proves none.** The first
captured frame that had a locked target had it dead centre, where
`128 + lateral/divisor` gives 128 for *any* divisor. The reading looked
confirmed and was wrong in two places. Only an off-centre sample
discriminated. When a measurement agrees with your model, check whether the
sample could have disagreed - if it could not, you have measured nothing.

**Per-frame state legitimately reads zero, so gate the capture on the
condition.** Comanche's targeting bytes are cleared and rebuilt every frame;
a single stop lands on an empty frame as often as not, and one did. The fix
is a predicate on the breakpoint - keep taking it until the frame is the
interesting one - not a conclusion that the field is dead.

**And the gate has to advance the guest, which a plain continue does not.**
QEMU re-tests a breakpoint at the PC it is resuming from, so continuing from
the stop halts again on the same instruction with no frame having elapsed. The
predicate then re-reads *one frozen frame* for however many rounds it is given
and the loop reports that the condition never held - which reads as a rare
frame and is a stuck one. `F030Comanche`'s marcher dumper had this: 400 rounds
said the condition never held, 1500 said it identically, and the second run is
the tell, because a real gate would have found something. Lift the breakpoint,
single-step, re-arm, then continue. Two symptoms of the same cause: a repeated
capture that returns byte-identical rows looks like a frozen guest, and a gated
one looks like an absent condition.

**A displacement is not an index.** Transcribing x86 stack-relative code,
`cmp ah, [esp+0x3E]` names a *stack offset*; the array index is that minus
wherever the array starts in the frame - `0x3E - 0x18 = 38` after six pushes.
Carrying `0x3E` across as the index ran a loop twenty-two entries past an
eighty-byte array. The same class: a table read `[ebx + 0x3CB4E]` against an
array based at `0x3CB40` carries a `+14` that is part of the *addressing*,
not of the table.

**Read the producer of a value, not only its consumer.** `idiv ebp` says
nothing about what `ebp` holds; in Comanche it had been loaded ninety bytes
earlier from a per-ring table, not from the object field the surrounding code
made obvious. Assuming the obvious source gave a formula that was wrong by a
factor of the ring geometry and still produced plausible numbers.

**The bugs that survive assembly are the ones that draw a wrong picture
rather than fail.** A span writer that read two address registers it never
set sampled arbitrary memory as a palette and produced a correctly shaped
landscape in the wrong colours. A constant that was a stack offset wrote past
an array and turned the screen red. Neither is a crash at the point of the
error, and neither is caught by "it builds". Capture the picture and compare
it; that is the test.

**Reverting a bad edit can silently drop a good one.** `git checkout <file>`
to undo a messy attempt also removed an unrelated correct change made in the
same pass, and the loss showed up two builds later as wrong colours. Either
commit the good part before experimenting, or re-check the whole diff after
any wholesale revert.

**An empty xref scan is a statement about your reference mechanism, not about
the data.** Three siblings hit "no reference to this address anywhere" —
unrelocated LE operands (TIE), DGROUP-relative addressing (UW1), an address
that was *inside an instruction* (F29) — and in every case the data was fine
and the address model was wrong. Verify the model end to end with one worked
example before concluding anything from an empty scan.

**A plausible failure count is not evidence of a defect.** UW1's misread
relocation stride produced "2,474 invalid entries of 3,176" — far too
systematic to be a decoding error, which is exactly why the wrong story
survived. When a container looks mostly-broken in a regular way, suspect your
stride before the file.

**Say "narrowed, not settled".** It is a legitimate and useful state. What is
not legitimate is letting it read as settled because the evidence points one
way.

The full technique ledger — the evidence-strength ladder, the idioms that
derail a disassembler, the bookkeeping conventions — is `CROSS-PROJECT.md`
in this repo, generated into every project. Read it before inventing a
method.

---

## 6. Tooling that worked (macOS)

| need | tool | note |
|---|---|---|
| archives, FAT12 images | `7zz` (7-Zip 26+) | reads floppy images directly; **cannot** read ARC |
| ARC/LZH | `unar` / `lsar` | verified byte-exact against stored CRCs |
| 16-bit disassembly | Python + `capstone` | fine for a seeded recursive-descent walker |
| reassembly proof | `nasm` | verify per instruction with `-l` and retain a whole-file hash; never rely on a binary diff alone |
| decompilation | Ghidra (headless) | `-processor "x86:LE:16:Real Mode"`; `-loader` is broken in 12.1.3 |
| DOS oracle (logs) | DOSBox-X | `[log]` per-category: `int10`, `io`, `vga`; dummy SDL driver for headless |
| DOS oracle (real DOS) | QEMU + MS-DOS 6.22 + mtools | the sibling harness (§3.4): `sendkey`, `screendump`, QMP probe |
| execution telemetry | QEMU TCG plugin (`dos/trace/`) | which bytes ran (§3.5); needs `qemu-plugin.h` + glib headers to build |
| 68k assembly | vasm / vlink | `-Felf`; link `start.s` first for TOS |
| target oracle | Hatari | VBL breakpoint + `savebin`, then compare byte-for-byte |
| rendering checks | Python + Pillow | contact sheets for semantics, pixel/event fixtures for regression |

This table is the macOS instance. The RE siblings run the analysis stack on
Windows (QEMU 11.1, mtools 4.0.49, nasm 3.02); the Windows-specific traps —
mtools' host-side overwrite prompt, the no-op QEMU serial sink, QEMU's
`ES =1234` register formatting — are collected in `CROSS-PROJECT.md`
§6–7.

`../F030Underworld/analysis/ghidra.md` documents the 16-bit DOS import workflow
and its extension patches; read it before a first Ghidra import rather than
rediscovering them. `../F030Underworld/analysis/reassembly.md` does the same
for the reassembly ratchet's encoder and `nasm -l` handling.

### 6.1 Treat tools and sibling code as explicit dependencies

Use [DEPENDENCIES.md](DEPENDENCIES.md) for ownership, reproduction records,
cross-game reuse and the shared-update procedure. A path in a sibling checkout
is a locator, not a version pin or a passing acceptance test. Record the actual
revision/hash, configuration and validation result used by the slice. When a
dependency changes, revalidate its affected consumers before reusing their old
results. Shared documents distribute policy; shared harness checks establish
copy equality. Neither establishes that a game's oracle boots or its port is
ready.
