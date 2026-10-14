# x86-32 to 68000 translation (bounded)

Status: **PARTIALLY RESOLVED**. A typed translator emits 68000 source for twelve
recovered functions that pass DOS fixtures in Falcon030 Hatari: seven that also
have hand-written ports (three RNG, two string helpers, two geometry functions
with `ebp` frames) and five that have none, the clipped shape draws
`sub_00058AB4` and `sub_00058F9E` (pixels mapped through a table) with their row
copies `sub_00058EB8` and `sub_00059476` (32 connected Poland witnesses, 23 of
them clipped, 271,911 bytes) and the static-frame compositor `sub_00014BF6` (one
connected witness, 316,428 bytes, arena at the DOS virtual base, its present call
a recorded boundary). Of the 643 inventory functions it can emit 344 (measured
2026-10-06), 142 of them with every callee implemented; 52 of its 75 rules are
exercised by a validated function, 23 are implemented but `Unproven`.
It is not a whole-game translator and does not claim to become one.
Method basis: `../F030Method/METHOD.md` section 4.3b (bounded translation) and
`../F030Method/analysis/f030ct-translator-review.md` (the SNES translator's
pipeline, which this follows in spirit; none of its code or its 65816 model is
reused).

## What exists

- `tools/x86x/translate.py`: decodes a function's bytes from the hash-checked
  `game/EXE/PANZER.EXE` (spans from `work/re/functions.txt`, relocation sites
  from the LE fixups via `tools/re/disasm_le.py`), lowers each instruction
  through an explicit rule table and writes vasm source. Every emitted line
  carries the DOS address, the instruction bytes and its mnemonic; every lowering
  carries a rule id. A function with any instruction lacking a rule is **not
  emitted**: it is reported as `UNSUPPORTED` with the reason. Nothing is guessed.
- The core (`Build`, `reachable`, `lower`, `translate`, `shim`) is
  build-independent. `pg_build()` is the PANZER.EXE adapter: image and hash,
  function table, 32-bit fixup sites -> (object, offset), the data object held in
  a0. Another 32-bit flat build would add its own adapter and its own evidence;
  by `../F030Method/DEPENDENCIES.md` the tool stays in PG until a second consumer
  has validated its own contracts.
- `tools/x86x/coverage.py`: the §4.3b coverage report. Separate counts for
  decoded, implemented, closed under calls and DOS-validated functions; per rule,
  how many functions use it and whether a validated function exercises it; the
  blocking reasons of the rest; `--assemble` assembles all implemented functions
  (an emitter syntax check, no behavioural claim).
- `src/common/x86rt.i`: 68000-only macros (`LD32LE`, `ST32LE`, `LD16LE`,
  `ST16LE`, `PUSH32`, `POP32`, `IMUL32`, `IMUL32R`, `UMUL64`, `SMUL64`,
  `MOVSB/W/D`, `REP_MOVSB/W/D`, `STOSB/D`, `REP_STOSB/D`, `REPNE_SCASB`).

- `translate.py --boundary <function>`: calls to the named function become `bsr
  boundary_<name>` (x86 register roles, DOS stack arguments) instead of being
  translated; the symbol is supplied by the harness and the output names it. A
  boundary is a substitution, so its contract is verified separately (below).
- `work/probe_compose_contracts.py`, `tools/collect-compose-fixtures.py`,
  `src/target/falcon/compose-fixture.s`, `tools/check-native-compose.py`: the
  compositor witnesses and the gate. The harness **places the captured DOS state
  at its DOS virtual addresses** (arena at `$1E0000`, shape images and the bitmap
  where DOS held them) on a 14 MB Falcon030 in Hatari, so every pointer DOS stored
  in memory is a valid native address; this settles the pointer representation
  question for translated code in a harness (see "Next" for the product).
- `work/probe_shape_contracts.py`, `tools/collect-shape-fixtures.py`,
  `src/target/falcon/shape-fixture.s`, `tools/check-native-shape.py`: the DOS
  witnesses and the native gate of `sub_00058AB4` and `sub_00058F9E`, which have
  no hand-written port (`analysis/functions/sub_00058AB4.md`, `sub_00058F9E.md`).

```sh
python3 tools/x86x/translate.py sub_00010976 sub_00048105 \
  --out build/x86x/geometry.s --report build/x86x/geometry.report.txt
python3 tools/check-native-geometry.py --out build/n-geom-tr --translated   # fresh directory
python3 tools/check-native-loader.py --out build/n-load-tr --translated     # strings and geometry
python3 tools/check-native-rng.py --out build/n-rng-tr --translated
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd --out work/qemu_out/shape-1 \
  --script work/routes/poland.json --seconds 60 --shape-contracts            # menus and compositor
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd --out work/qemu_out/shape-2 \
  --script work/routes/poland.json --seconds 60 --shape-contracts axis_turn  # tactical map, clipped
python3 tools/collect-shape-fixtures.py work/qemu_out/shape-1/route.json work/qemu_out/shape-2/route.json
python3 tools/check-native-shape.py --out build/n-shape-1                   # translated only
python3 work/drive_menu.py --hdd work/qemu_out/pg-merged.hdd --out work/qemu_out/compose-6 \
  --script work/routes/poland.json --seconds 60 --compose-contracts          # not with --shape-contracts
python3 tools/collect-compose-fixtures.py work/qemu_out/compose-6/route.json
python3 tools/check-native-compose.py --out build/n-comp-1                  # 14 MB Falcon, arena at $1E0000
VASM=... python3 tools/x86x/coverage.py --out build/x86x/coverage.txt --assemble
```

## Conventions

| x86 | 68000 | Note |
|---|---|---|
| eax, ecx, edx, ebx, esi, edi | d0, d1, d2, d3, d4, d5 | 32-bit; `ax`..`di` and `al`..`bl` are the low word/byte (a `move.w`/`move.b` leaves the upper bits, as on x86) |
| ah, ch, dh, bh | bits 8..15 of d0..d3 | read through d7 (`move.w`, `lsr.w #8`); written with `ror.w #8` around a `move.b`; `mov`, ALU, `test` and `adc/sbb r,r` forms |
| ebp | a6 | frame pointer; `mov ebp,esp`, `mov esp,ebp`, `push`/`pop ebp`, `leave`, `[ebp+disp]` |
| esp | a7 | `add`/`sub esp,imm` -> `lea`; `[esp+disp]`; `push`/`pop` of registers, immediates and dwords |
| segment registers | none | flat model: `push`/`pop` of `es`, `ds`... keep only the 4-byte stack effect, and a function that reads one is not translatable |
| (arena) | a0 | base of the LE object-2 data; a fixup into object 2 (immediate or displacement field) becomes `a0 + offset` |
| scratch | d6, d7, a1 | clobbered by lowered instructions; the `movs` macros also borrow a2 across the copy |
| (captured condition) | a2 | holds one `Scc` result between a flag-setting instruction and a later jump (see below); clobbered |

**Memory.** All x86 memory, including the stack, is little-endian bytes: a
32-bit access is four byte accesses, a 16-bit access two, because x86 data may
be unaligned and the 68000 faults on unaligned words. `push` is therefore
`PUSH32` (four byte stores), so `[ebp+disp]`/`[esp+disp]` operands and the
argument a `ret n` pops read the same bytes DOS would; `bsr` pushes the native
return address, which no rule reads. An effective address is
`[a0 if the displacement is relocated] + base + index * scale + disp`; an absolute
address without a relocation and a segment override are refused. Pointers held
in registers are native addresses; the translator has no rule that reads a DOS
virtual pointer from memory and rebases it (`call dword ptr [mem]` is refused
for that reason, and a translated function that stores a pointer into the arena
stores a native one; see "Next").

**Control flow.** A function is the set of instructions reachable from its entry
(the inventory span may be padded or overrun; `sub_00060926`'s span is 5,343
bytes for 55 bytes of code). A `jmp` to another recovered function's entry is a
tail call (`bra`); other control flow leaving the span, an indirect jump,
undecodable bytes or a fall-through into unreachable bytes is refused. `jecxz`
and `loop` are counted branches on d1.

**Flags.** A conditional jump reads the nearest preceding flag-setting
instruction (`cmp`, `test`, `add`, `sub`, `and`, `or`, `xor`, `inc`, `dec`,
`neg`; the shifts for Z, S and C only) whose lowering leaves the same flags in
CCR (register and byte-memory forms, `cmp` through d7; not a read-modify-write
store, `xor ah,ah`, `esp` arithmetic or `shift by cl`). Between them there may be
other conditional jumps (Bcc leaves CCR alone), or instructions that do not
change the x86 flags and are not control flow: then the condition is captured
right after the producer (`Scc d7`, `movea.l d7,a2`) and the jump tests a2
(`move.l a2,d7`, `tst.b d7`, `bne`). Nothing in the chain may be a branch target
(flags would come from several paths); one captured condition per producer; a
`call` in between is refused. `cmp`/`sub` map `je jne js jns jl jge jle jg jb jae
jbe ja jo jno` to the same-condition 68000 branch (N, Z, V, C equal SF, ZF, OF,
CF); after `inc`/`dec` the carry conditions are refused because x86 leaves CF
alone, and after a shift the OF conditions are refused. `adc`/`sbb` are accepted
only directly after an instruction whose lowering leaves X = CF (`add`/`sub`
register and byte forms, shifts, `neg`) and become `addx`/`subx`.

**ABI shims.** A generated body keeps x86 register roles. For a function with
an entry in `SHIMS` the translator also emits the hand-written port's calling
convention as a wrapper: register inputs are moved all at once (through the
stack, so cycles such as `d1->edx, d3->ecx, d2->ebx` are safe), the one dword
stack argument of a `ret 4` function is pushed little-endian, declared outputs
are returned and every other register (d0-d7, a1, a2, a6) is restored. The
generated file then drops into the existing harnesses unchanged.

## Rules (the whole policy)

Rule ids as `coverage.py` reports them. **Validated** means a function whose
generated code passes a native DOS-fixture gate uses the rule; **Unproven**
means the rule is implemented and assembles but no DOS fixture has exercised it
yet (a wrong Unproven rule cannot be detected until one does).

| Group | Rules | Status (2026-10-06, `coverage.py`) |
|---|---|---|
| stack | `push.r32` `pop.r32` `push.ebp` `pop.ebp` `push.seg` `pop.seg` `push.m32` `esp.adjust` `mov.ebp.esp` `mov.esp.ebp` `leave` `ret` `ret.n` | Validated (geometry, loader, RNG, shape) |
| stack | `push.imm` | Unproven |
| moves | `mov.r.imm` `mov.r.r` `mov.r.m` `mov.m.r` (8/16/32 bits, LE memory, arena fixups) `movzx` `cdq` `mov.ah` `mov.r.ah` | Validated |
| moves | `mov.m.imm` `lea` `movsx` `cwde` `xlatb` | Unproven |
| arithmetic | `alu.r.imm` `alu.r.r` `alu.r.m` `alu.m.r` `alu.r.ah` `inc.r` `inc.m` `dec.r` `imul.imm` `imul.r.r` `imul.64` `mul.64` `not` `shift.imm` `rotate` `adc` `adc.ah.ah` `test.r.r` `test.m.imm` `test.ah` | Validated (`imul.r.r`, `SMUL64`, `adc`: domain limits, see ledger) |
| arithmetic | `alu.m8.imm` `alu.m8.r` `alu.m.imm` `cmp.m.imm` `cmp.m.r` `inc.m8` `dec.m` `dec.m8` `imul.r.m` `neg` `shift.cl` `sbb` `adc.imm` `sbb.imm` `test.r.imm` `alu.ah` `cmp.ah` `cmp.r.ah` `xor.ah.ah` | Unproven |
| strings | `repne.scasb` `rep.movsb` `rep.movsd` `rep.stosb` `rep.stosd` | Validated (loader, shape) |
| strings | `movsb` `movsw` `movsd` `rep.movsw` `stosb` `stosd` | Unproven |
| control | `jcc` `jcc.captured` `jmp` `call` `cld` | Validated |
| control | `jmp.tail` `jecxz` `loop` `nop` | Unproven |

Refused on purpose: `int`, `in`/`out`, `cli`/`sti`, `pushfd`/`popfd`, `enter`,
`idiv`/`div` (a 64/32 division needs a checked helper and a fixture),
`repe cmps*`, indirect `call`/`jmp`, segment reads, immediates or displacements
relocated to the code object, `[ebp]` as an index register, `mov` between a
general register and `esp`/`ebp` other than the frame pair, odd stack
adjustments, a second captured condition after one producer.

## Evidence

- `sub_00063375`, `sub_0006337B`, `sub_0006339F` (6 + 36 + 16 DOS bytes) pass all
  19 DOS RNG fixtures (152 bytes, seed side effects included) in the native
  Hatari gate, in the same harness as the hand-written `src/common/rng.s`
  (`check-native-rng.py --translated`).
- `sub_00060907` (31 bytes) and `sub_00060926` (55 bytes) replace the hand-written
  `src/common/strings.s`, and `sub_00010976` (162 bytes) and `sub_00048105`
  (111 bytes) replace `src/common/geometry.s`, inside the loader gate
  (`check-native-loader.py --translated`): all 6,779 DOS output bytes of the
  `sub_00037E75` Poland route fixture are equal.
- `sub_00010976` and `sub_00048105` pass the 12 geometry fixtures (196 bytes) in
  the geometry gate (`check-native-geometry.py --translated`); the hand-written
  control run passes the same bytes. These two were the first functions with
  `ebp` frames, stack locals, 16-bit loads/stores, a stack argument (`ret 4`),
  `imul r32,r32` and relocated displacements (`[edx+0x21d8]`, `[0xccb1]`).
- Negative controls on the geometry gate (generated source mutated, same
  harness): a wrong stack-slot byte (`16(a6)` -> `17(a6)`) changes 59 of 196
  bytes; a big-endian slot read (`move.w -12(a6)` for `LD16LE`) changes 4; a
  native-endian argument push (`move.l d7,-(sp)` for `PUSH32`) changes 60. The
  earlier controls still hold (string source advance 2 -> 3: no output; one RNG
  constant: 14 of 152 bytes). A 16x16 `mulu.w` in place of `IMUL32R` changes
  **nothing**: both geometry operands stay below 2^16 in every DOS fixture, so
  the cross-term half of that rule is not distinguished by the evidence (ledger).
- **`sub_00058AB4` and `sub_00058F9E` with their row copies, no hand-written
  port** (shape gate, `check-native-shape.py`): 32 connected Poland witnesses
  from two route captures, the menus and the static-frame compositor (border,
  panel and unit art, regions of up to 69,604 bytes) and the tactical map
  renderer (terrain hexes at x = -45 and y = -25, clipped on the left and top;
  23 witnesses touch a clip edge, 3 go through the table-mapped primitive): all
  271,911 compared bytes and every EAX equal. The first run of the first eleven
  failed on every non-trivial case (5 to 3,644 bytes each): the `mov ah, al`
  rule rotated the destination register before reading the source, which shares
  it. That is the Unproven-rule failure the ledger predicted, found by the first
  fixture that exercised the rule. Negative controls on the passing 32-witness
  build: every `rep stosd` as a byte fill changes 104,862 bytes, every `rep
  movsd` as a byte copy 142,383, every `bne` to a label inverted (the
  captured-condition tests among them) 145,023. **Blind** mutations, recorded as
  domain limits of these witnesses: `SMUL64` as `UMUL64` (no negative operand
  reaches the multiply), a lost bit in `movzx` (no value reaches it), every
  `addx.b` as `add.b` (the `adc dl,dl`/`adc dh,dh` chains build the
  trivial-reject mask tested by `test dh, dl`: no witness is entirely outside
  its clip, so every bit is 0), a captured `sle` as `slt` (its equal case never
  occurs). A witness entirely outside the clip is the next one to collect.
- **`sub_00014BF6` (static-frame compositor), no hand-written port** (compose
  gate, `check-native-compose.py`): one connected Poland witness (the other
  call in the route, at 38 s, redraws an identical frame and changes no pixel, so it
  yields no bitmap difference and was not retained). DOS state captured at entry:
  8 KB of rect records and descriptors (`0xC000..0xE000`), the shape pointers, the
  globals, the four shapes' headers and sprite bytes (three are lone sprites whose
  extent no next table entry bounds: a fixed 128 KB window), the 640 x 480 back
  buffer; after the call: the windows, the changed region of the bitmap and the
  argument of each `sub_000481AB` call. The generated compositor, calling the
  generated `sub_00058AB4`/`sub_00058EB8` (already validated) and a stub for the
  present function, reproduces all **316,428 bytes**: the bitmap region (the whole
  frame's worth of border and panel art), unchanged windows and the present
  arguments `4, 3, 2, 1`. It passed on the first run. Negative controls on the
  passing build (unmutated control: equal): dropping one shape draw changes 28,990
  bytes, a wrong record stride (`0x15` for `0x14`) breaks the run (no output), a
  changed present argument changes 1 byte, a skipped present call 5.
  **Boundary:** `sub_000481AB` (and through it `sub_0004A485`, a dirty-rect
  present with a software cursor that calls the display driver through
  `[0x55E4]`) is not translated; the gate verifies only that the compositor calls
  it four times with `al` = 4, 3, 2, 1, never what it does. The screen path
  therefore remains unverified here.
- `UMUL64`/`SMUL64`: a Python model of the macro's instruction sequence (16x16
  `mulu.w`, 32-bit adds with X) agrees with the 64-bit product on 200,000 random
  and edge operands; the shape gate then executed `UMUL64` and `SMUL64` on
  non-negative operands.
- Coverage (`coverage.py`, 2026-10-06): inventory 643; decoded 568; implemented
  344 (111,630 DOS bytes), 142 of them closed under calls; DOS-validated 7. The
  same sweep with the translator before this session implemented 20 (the five
  validated ones and fifteen leaf helpers); the stack-slot rule alone made it 49.
  All 344 assemble with `-m68000`. Among the closed functions are the two
  sprite primitives `sub_00058AB4` (1,017 bytes) and `sub_00058F9E` (1,229 bytes)
  and the row copy `sub_00058EB8` (199 bytes) from `analysis/rendering.md`; the
  compositor `sub_00014BF6`, the map renderer `sub_00010A64` (1,102 bytes) and the
  scenario loader `sub_00037E75` (1,127 bytes) are implemented but call
  unimplemented functions (see "Next").
- Size, harness plus generated RNG code: 398 bytes of text against 390 for the
  hand-written code. No timing was measured.

## Difference ledger (against the DOS function and the hand-written port)

| Difference | Status |
|---|---|
| d6, d7, a1 and a2 are clobbered inside generated bodies; the shims save and restore everything except declared outputs | Known; shim-less (RNG) callers must treat d6, d7, a1, a2 as volatile |
| x86 flags are reproduced only for the jump that reads them (directly or captured); flags after `repne scasb`, `movs`/`stos`, high-byte writes, RMW stores, `adc`/`sbb`, rotates and the multiplies are not x86's | Outside the contract (no caller reads them); refused if a jump would |
| `IMUL32R` cross terms (operands >= 2^16) | `Unproven`: no DOS fixture distinguishes them; the 16x16 mutation passes the geometry gate |
| `SMUL64` sign correction, `adc`/`addx` carry (trivial-reject mask), `movzx` masks | Not distinguished by the 32 witnesses (non-negative multiplies, no draw entirely outside its clip): the shape gate cannot see a mutation of them |
| `MOVSD`/`MOVSW` copy a dword/word as bytes in address order | Differs from DOS only when the destination starts inside the source item; `Unproven`, no fixture |
| `repne scasb`, `movs` and `stos` assume the direction flag is clear (`cld` is a no-op, `std` has no rule) and a flat segment | Matches the DOS functions' own `cld`; segments are never read |
| Unproven rules (table above): implemented, assembled, never compared with DOS | `Unproven` until a fixture-backed function uses them |
| Null seed pointer path and unterminated or overlapping strings are translated but not exercised | `Unproven`: no DOS fixture reaches them |
| Real hardware, interrupts, stack depth on a physical machine | Not measured |

## Next

- **Present path.** `sub_000481AB` -> `sub_0004A485` (454 instructions, indirect
  calls through `[0x55E4]` (driver export 11, the validated `gfx_copy_rect`
  contract), `[0x55CC]` and a software-cursor overlay) is the next function to
  take from boundary to translated: it needs an indirect-call rule that maps a
  loaded DOS function pointer to a native adapter (and stops on an unknown
  target, as �4.3b requires) and the cursor helpers `0x49A23`, `0x49A3E`,
  `0x49DD7`, `0x4981F`, `0x49B61`, `0x49B25`, `0x5AA27`.
- **Pointer representation in the product.** The harness places state at the DOS
  virtual base, which needs RAM at `$1E0000..$400000` and holds only because the
  test program is small (the harness checks it ends below the arena). A product
  needs either an allocator that places the arena there on a Falcon with enough
  memory or boundary adapters that translate pointers; neither exists. The scenario loader
  `sub_00037E75` is unblocked by the same mechanism.
- **Done: functions nobody has ported by hand** (`sub_00058AB4`, `sub_00058F9E`
  and their row copies, above), including clipped draws and the table-mapped
  primitive (its one global, the 256-byte table at arena `0x6E48`, is captured
  at entry and staged in the harness arena). Next witnesses: a draw entirely
  outside its clip (the trivial-reject mask). The compositor is done
  (above); a second compositor witness with changed pixels (a redraw after the
  map changes) and the map renderer `sub_00010A64` (needs `sub_00010EB2`,
  `sub_000485BE` and the arena at the DOS base) are next, then a whole-frame
  comparison against `tests/fixtures/dos-frame-poland_tactical.*`.
- **Pointer representation.** The scenario loader `sub_00037E75` translates but
  stores pointers it receives from the allocator into the arena, where the DOS
  fixture holds DOS virtual addresses, and reads pointers back from the arena
  and dereferences them. Generated code uses native addresses, so either the
  arena must sit at the DOS virtual base (a target harness placement: on a 14 MB
  Falcon the loader state `0x1E0000..0x400000` lies inside the program's own TPA)
  or the boundary adapters must translate. The hand-written loader uses
  `pg_virtual_pointer`; generated code cannot. Decide this before any generated
  function that stores or loads pointers is validated.
- **Runtime boundary.** The loader's three callees outside the implemented set
  are `sub_00063D1E`, `sub_00063D41` and `sub_00066170`. The hand-written loader
  replaces the DOS stream calls with the `pg_open`/`pg_read`/`pg_close` adapters
  (`src/common/loader.s`); `analysis/scenario-loader.md` names the open wrappers
  it measured (`sub_00065FF7`, `sub_000660BF`, `sub_000660DA`, `sub_00067FC8`) but
  not these three, so their identity is TBD. Whatever they are, runtime functions
  are target adapters written by hand with the DOS register convention, never
  translated.
- **Division.** `idiv`/`div` block 25 functions; a checked 64/32 helper with a
  divide-by-zero stop (§4.3b: a boundary stop, not invented DOS error handling)
  and a fixture are needed.
- 53 functions have control flow leaving their inventory span (shared tails or
  mis-sized spans: inventory work in `tools/re/disasm_le.py`, not a rule); 42
  use immediates relocated into the code object (function pointers); 22 call
  through data pointers.

## Time and effort (METHOD 4.3b step 4)

Session 1 (three RNG functions): the translator and macros. Session 2 (two string
helpers): reachability extents, 8-bit registers, the flag model, byte memory
operands, segment stack effects, `repne scasb` and the shim generator. Session 3
(two geometry functions, this one): little-endian stack slots, `ebp` frames,
16-bit operands, general effective addresses with relocated displacements, `imul
r32,r32`, `ret n`, the stack-argument shim, the build adapter split, rule ids
and the coverage report, then the broad rule set (memory immediates, `lea`,
`movsx`, high-byte registers, string moves and stores, tail calls, counted
branches, 64-bit multiplies, `adc`/`sbb` on X, captured conditions), then the
shape-draw probe, fixture and gate. The seven hand-ported functions saved no
work; the four shape functions (2,752 DOS bytes, 1,140 instructions, with
run-length decoding, clipping and a pixel table) went from witnesses to a
passing native gate with one rule fix, two harness fixes and no transcription.
That is the first saving. The compositor (227 bytes, plus the boundary option,
the absolute-base harness, a probe and a collector) passed on its first run.
