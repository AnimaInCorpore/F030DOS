# Executable container — `PANZER.EXE`

Status: `RESOLVED` for the container (2026-10-05) — `PANZER.EXE` is the
DOS/4GW extender (file `0..0x344A4`) followed by the game's own bound
executable (file `0x344A4..EOF`: an MZ stub, then the `LE` header at
`0x36E3C`). There is **no trailing overlay outside the LE module**. The earlier
reading below that treated the last `0x344A4` bytes as an unclassified "tail"
came from reading the LE data-pages offset as an absolute file offset; see
"Correction: LE base" first. Sections after it are retained as measured
evidence, but statements about a "tail", "trailing region" or an LE entry at
file `0x7B7EC` are superseded.

## Correction: LE base

The LE header's data-pages offset (`0x23E00`) is relative to the start of the
bound executable, which is the second `MZ` at `0x344A4` (its `LE` header is
`0x2998` bytes into it). The shared identity
`base + data_pages_off + (pages-1)*page_size + last_page_bytes == filesize`
holds only with that base: `0x344A4 + 0x23E00 + 110*0x1000 + 0xA3D = 0xC6CE1`
(exact EOF). With base 0 it fell `0x344A4` short, and the gap was named a tail;
that its size equals the base is the giveaway.

Recomputed with `work/le_map.py`:

| Item | Value |
|---|---|
| Bound-exe base | file `0x344A4` (`MZ`), LE header at `0x36E3C` |
| LE page 1 | file `0x582A4` (identity page map: page *n* at `0x582A4 + (n-1)*0x1000`) |
| Object 1 (code) | linear `0x10000`, pages 1..99, file `0x582A4..0xBB2A4` |
| Object 2 (data) | linear `0x80000`, pages 100..111, file `0xBB2A4..0xC6CE1` |
| Entry | object 1 + `0x579EC` -> file `0xAFC90`: `EB 78 "WATCOM C/C++32 Run-Time system. (c) Copyright by WATCOM International Corp."`, the Watcom start stub that jumps over its banner |
| Fixups | 17,237, all source type 7 (32-bit offset), all internal |

The old model put the entry at file `0x7B7EC`, which is mid-instruction
garbage (`00 47 B8 ...`); the Watcom banner at `0xAFC92` is the evidence for
the new one. The `0xA974` helper that "copied the tail" copied an ordinary LE
data page, and the measured `+0x124D5C` file-to-RAM delta is the load placement
of the game's LE pages. A full 16 MB RAM dump
(`python3 work/probe_memory.py --seconds 12 --ram-size 0x1000000 --output
work/qemu_out/pg_ram16.bin`, then `python3 work/le_map.py` with that file)
checks it page by page: in 104 of 111 pages every byte that differs from the
file lies on a fixup site. The seven others are all object 2 (writable data)
or the startup code's own page (page 88, 2 bytes at `+0xA60`), i.e. bytes the
running game wrote, not a different placement.

`+0x124D5C` is exactly `0x17D000 - 0x582A4`: DOS/4GW placed object 1 (LE
page 1) at physical RAM `0x17D000`, page-aligned, and the 99 code pages end at
`0x1E0000`, where object 2 starts. Thus the measured stalled-loop address
`EIP = 0x1B3DBA` is game code: object 1 + `0x36DBA`, file `0x8F05E` (LE page 55).
The timer wait is in the game, not in the extender, and every runtime address
in this note converts with the same constants.

The stalled timer wait is resolved: see "Startup stall: no mouse driver".

## Startup stall: no mouse driver

The splash stall was never a loader or timer-hook problem. Chain, all read from
the RAM dumps (`work/probe_stall_stack.py`) and confirmed with breakpoints
(`work/probe_break_trace.py`); addresses are runtime, file = runtime - `0x17D000
+ 0x582A4`:

| Runtime | File | What it is |
|---|---|---|
| `0x1B3D8E` | `0x8F032` | `Delay(ms)`: waits until the dword at `0x1E21BA` has advanced `ms*60/1000` ticks. Called with 2000 from `0x180165` (the credits hold) |
| `0x1B6DD7` | `0x9207B` | the only writer of that dword (`inc [0x1E21BA]`), a timer callback registered through the Miles AIL timer API |
| `0x1D25B7` / `0x1D26DF` / `0x1D27E8` | `0xAD85B..` | AIL `register_timer` / `start_timer` / `set_timer_frequency` (16 slots, status 0/1/2, period in microseconds) |
| `0x1D234B` | `0xAD5EF` | hooks INT 8 with `int 21h AH=25h` to master ISR `0x1D21F3` and programs the PIT; `0x1D21F3` runs the slots, and it **was** running at the stall |
| `0x1B7AEF` | `0x92D93` | `InitMouseAndTimer(640, 480)`, called from `0x17D3F7` |

`0x1B7AEF` begins with `int 33h`, `AX=0` and returns 0 at once, before it
registers the timer callback, unless `AX == 0xFFFF`. The oracle had no mouse
driver, so `0x1B6DD7` was never registered and `Delay` could never end. The AIL
state in the stalled dump agrees: only two callbacks were registered, neither
the tick routine, and the game's own return value was 0.

`work/build_dos_hdd.py --mouse-stub` adds a 43-byte INT 33h TSR (`AX=0` ->
`AX=FFFF BX=2`, everything else returns). With it `0x1B7AEF` returns 1 and the
no-sound image runs on from the credits to the main menu (640x480, "START
GAME / LOAD / QUIT" over the map) within 34 s, captured in
`work/qemu_out/screen_t18.png` and `screen_t34.png`. The stub does not emulate
mouse input; a real driver or QEMU PS/2 mouse plus CuteMouse is the next
oracle step once input matters.

## Selection and identity

The shipped `INSTALL.NFO` specifies start command `PG`. The recovered
`PG.BAT` enters `EXE`, runs `UNIVBE`, optionally runs `LOADPATS`, and executes
`PANZER.EXE` on both the Gravis and non-Gravis paths. The selected artifact is:

| Field | Value |
|---|---|
| Path | `game/EXE/PANZER.EXE` |
| Size | 814,305 bytes (`0xC6CE1`) |
| SHA-256 | `115ADA29636B32C3E07446FDF4569D97324D357A1E71DAFB859DD95C3CB69A86` |
| Variant | unpatched five-volume base tree |

The patch disk was not applied; its files and hashes are recorded in
`analysis/source-media.md`.

## MZ bootstrap

The file begins with a conventional `MZ` header, but its raw dword at offset
`0x3C` is `0x09B40000`, not a usable extended-header pointer. The relocation
table is instead authoritative for the 16-bit bootstrap:

| Field | Value |
|---|---:|
| Header size | `0x200` bytes |
| Image boundary | `0x200..0xF444` |
| Relocations | 78; all 78 target within the MZ image |
| Entry | `CS:IP = 0x01BD:0x2382`, file offset `0x4152` |
| MZ image tail | 751,773 bytes after the MZ image boundary |

The first-stage entry bytes are preserved as evidence:

```text
BF 00 00 8E D7 81 C4 0E 12 BE BD 01 2B F7 8B C6
B1 04 D3 E0 48 36 A3 E6 0C 36 89 26 DC 0C BE 25
```

## LE protected-mode module

A scan of the appended area found one candidate whose LE tables and fixups
validate: the `LE` header at file offset `0x36E3C`. The shared LE parser was
run against that header and validated against the module’s declared data end,
not the physical EOF, because this file has a trailing region.

| Field | Value |
|---|---:|
| Format level | `0` |
| CPU / OS | `0x0002` / `0x0001` (386-class DOS module) |
| Module flags | `0x00000200` |
| Pages | 111 × `0x1000`; last page `0xA3D` |
| Data pages | absolute file offset `0x23E00` |
| Declared module end | `0x9283D` |
| Object table | `0x36F00`, 2 objects |
| Page map | `0x36F30`, identity map |
| Fixup records | `0x372B7..0x580B2` |
| Fixups | 17,237 source sites; all are internal 32-bit-offset fixups |
| Entry | object 1 + `0x579EC`, linear `0x679EC`, file offset `0x7B7EC` |
| Stack | object 2 + `0x33240`; auto-DS object 2 |

The object map is:

| Object | Linear base | Virtual size | Pages | Flags |
|---:|---:|---:|---|---:|
| 1 | `0x10000` | `0x625F5` | 1 + 99 | `0x2005` |
| 2 | `0x80000` | `0x33240` | 100 + 12 | `0x2003` |

The LE module’s declared end is before physical EOF. The remaining
`0x344A4` bytes begin at file offset `0x9283D`; they contain code-like bytes,
DOS/4GW/WATCOM runtime strings, and Panzer General resource/path strings.
They are retained in the exact executable and are not assigned LE object
addresses yet.

## DOS oracle witness

The per-game builder is configured for the recovered tree:

```text
python work/build_dos_hdd.py --no-boot
python work/build_dos_hdd.py --run-game --hold --no-boot
python work/build_dos_hdd.py --use-no-sound --run-game --hold --no-boot
```

The bootstrap image passed under genuine MS-DOS 6.22 and exited through
`QUIT.COM` after 3.2 seconds; `BOOT.LOG` expanded the six DOS support tools.
Launching the untouched shipped `SOUND.CFG` through `PG.BAT` reaches DOS/4GW
1.96 and reports Mel fatal error 25/trap 15: failure to detect a MIDI sound
card. This is an environment configuration failure, not a container parse
failure.

Running the shipped `SOUND.BAT` and selecting its `No Sound` option writes a
DOS-generated 59-byte configuration (SHA-256
`60FAE4AC4BC69DB0CC7D89BFD36FDFFB2D74B318A189801126C8E6E6A1800F8C`). Using
that configuration only for the diagnostic oracle run reaches the SSI
“Presents” startup frame and remains in protected-mode graphics. The generated
screen captures are under `work/qemu_out/`; the title/menu progression and the
trailing region’s caller-level loader/file-I/O semantics remain to be traced.

## Runtime placement witness

Status: `PARTIALLY RESOLVED` — the trailing bytes are proven resident in the
captured protected-mode address space, and the first 4 KiB transfer into that
range is identified. The caller-level LE handoff semantics remain open.

With the no-sound image held at the startup frame, the live CPU probe sampled
`EIP = 0x1B4FC5` and `0x1B3DBA`, matching file offsets `0x90269` and `0x8F05E`
and giving a measured delta of `0x124D5C`. A physical-RAM snapshot taken after
eight seconds provides the stronger tail witness:

```text
python3 work/probe_memory.py --seconds 8
source-unique diverse windows: 710 (source-ambiguous skipped: 60)
unique RAM matches: 326
deltas: 0x124D5C (326)
first match: file 0x9283D -> guest 0x1B7599
```

The probe tests source-unique, diverse 32-byte windows at a `0x100` file
stride, and searches physical RAM above `0x100000`. This establishes a
consistent runtime copy/mapping for the measured startup state; it does not
establish that the tail is a standard LE object, an executable overlay, or
which loader performed the placement.

A shared TCG trace adds file-I/O evidence:

```text
python3 ../F030Method/dos/trace/run_trace.py --hdd img/panzergeneral.hdd \
  --seconds 8 --lo 0 --hi 0x400000 \
  --out work/qemu_out/pg.trace \
  --memdump work/qemu_out/pg.trace.ram --memdump-at 7 \
  --int21log work/qemu_out/pg.int21 \
  --int21callers work/qemu_out/pg.int21.callers
```

The trace logged 3,627 DOS calls. After the LE-header inspection, the
handle-5 stream performs 4 KiB reads through the file’s physical end; 53 reads
overlap the tail, and the final read is `file 0xC62A4..0xC6CE1` (the exact EOF).
The same runtime delta maps active tail call sites `0x1D4E95`, `0x1D4F77` and
`0x1D8BA8` to file offsets `0xB0139`, `0xB021B` and `0xB3E4C`; those sites
issue DOS reads, seeks and closes during subsequent resource activity. The
tail is therefore not merely an unobserved byte suffix: startup reads it and
tail-resident code later participates in file I/O. The trace still does not
identify whether the contiguous resident bytes came from the LE loader, a
custom copy, or another startup buffer.

A companion trace with `--mem` marked every byte in guest range
`0x1B7599..0x1EBA3D` with the plugin’s `WRITE` flag (`214,180 / 214,180`
bytes). This confirms that the resident tail range was written during the run,
but the sidecar has no timestamp or source-PC attribution, so it does not yet
identify the copying instruction or distinguish a loader write from a game
write.

A hardware write-watchpoint installed before boot closes that attribution gap:

```text
python3 work/probe_tail_write.py --seconds 30
stop: T05thread:p01.01;watch:1b7599;
copy range: 0x144E0..0x154E0 -> 0x1B7000..0x1B8000; 4096 bytes
source == PANZER file 0x922A4: True
code/file matches: ['0xA976']
```

The stopped CPU is in a 16-bit protected-mode segment (`CS = 0x0070`, base
`0x119660`). The reported `EIP = 0x0E66` has linear address `0x11A4C6` and
matches file offset `0xA976`, so the watchpoint stops immediately after the
preceding static sequence:

```text
0xA972  D1 E9       shr  cx,1
0xA974  F3 A5       rep  movsw
0xA976  D1 D1       rcl  cx,1       ; stopped EIP
0xA978  F3 A4       rep  movsb
```

At the stop, `DS` has base `0x12160`, `ES` has base `0x1B7000`, and the
post-copy `SI`/`DI` values are `0x3380`/`0x1000`. Thus the preceding
`rep movsw` copied the exact file range `0x922A4..0x932A4` from the staging
buffer `0x144E0..0x154E0` to `0x1B7000..0x1B8000`. The first byte of the
LE-external tail, file offset `0x9283D`, is destination `0x1B7599` (offset
`0x599` in that block), matching the independently measured `+0x124D5C`
mapping. This identifies a concrete 16-bit MZ-image transfer helper and its
source bytes; it does not yet identify the caller that requested the block or
prove that every later block uses the same path.

The splash remains stalled, but the timer failure is now narrowed to the
protected-mode handoff. After dynamically calibrating the current wait-loop
code, a watchpoint on its patched timer operand (`0x1E21BA`) observed no write
for eight seconds; a breakpoint on candidate `file 0x9207B` (`runtime
0x1B6DD7`) also did not fire. The CPU remained at `runtime 0x1B3DBA` (file
`0x8F05E`), the loop that waits for that timer value to advance.

The protected-mode IDT is not empty: vector `0x08` is the gate
`f3 42 70 00 00 8e 00 00` (`CS:IP = 0x0070:0x42F3`). A pre-boot breakpoint on
that gate stopped during startup, proving that IRQ0 enters the extender/MZ
handler. Single-stepping its common path maps the executed bytes to the MZ
image’s interrupt-dispatch code (`file 0xEE12..0xEE4C`), returns to the gate,
and then transfers to selector `0x0080:0x0020` (runtime bytes matching file
`0x1DCD4`). It never reaches the game’s `0x9207B` increment routine in this
stalled state. Timer-hook installation or dispatch after the IRQ0 handler, and
the early state transition, are therefore still `TBD`; this is not evidence
that QEMU stopped delivering hardware interrupts.

## Seeds and recursive descent (2026-10-05)

`re/seeds.txt` now holds 15 evidence-carrying seeds: the declared entry
(`0x679EC`, the Watcom stub) and 14 functions measured in the oracle (the
mouse/timer init, `Delay`, the tick callback, the Miles AIL timer routines and
master ISR, two slot callbacks, the `int` wrapper). Each carries its evidence and
a confidence. `tools/re/disasm_le.py` reads them, refuses a seed outside object
1, inside known data or mid-instruction, and walks the code object by recursive
descent. Symbols are `sub_<vaddr>` (LE linear address, object 1 base `0x10000`),
tied to the executable hash above; `runtime = vaddr + 0x16D000`.

Result (reproduce: `python3 tools/re/disasm_le.py --functions
work/re/functions.txt --gaps work/re/gap_candidates.txt`):

| Measure | Value |
|---|---:|
| Object 1 size | 0x62535 bytes (402,741) |
| Decoded from the 15 seeds | 328,833 bytes, 97,013 instructions, **81.6%** |
| Functions (call targets plus seeds) | 635 |
| Switch tables resolved | 26 |
| Unresolved indirect sites | 87 (83 `call` through a memory pointer, 2 `call reg`, 1 `jmp eax`, 1 switch table whose bound is not proven) |
| Known-data regions (39) wrongly decoded | **0** |
| Decode conflicts | 2 |
| Unreferenced prologue-shaped candidates | 101 routines, 19,096 bytes (reported, not seeds) |

Coverage means little without the data guard (METHOD.md §2.3), so both are
reported together. The guard here is only what is provable from the image:
runs of four or more consecutive fixups into object 1 (pointer tables) and the
Watcom banner. Strings and other data in object 1 are not yet guarded, so the
zero is "no pointer table or banner decoded", not "no data decoded".

- **Switch tables:** the compiler emits `jmp dword ptr cs:[eax + table]` with a
  fixup on the displacement and a `cmp reg, N` / `ja` bound before it. A table
  is resolved only when that bound is found and every entry is a fixup into
  object 1; otherwise the site stays unresolved. The 26 resolved tables feed
  their entries back into the walk (coverage 61.8% before, 81.6% after).
- **The two conflicts are one idiom:** the same inlined `repne scasb` string
  routine, at `0x71197` and `0x71221`, jumps into the middle of a 66-prefixed
  `test ax, imm16` whose immediate (`89 CF`) is a hidden `mov edi, ecx`, the
  overlapping-instruction trick of ledger §2. They are real code, not errors,
  but the tool still counts them until the idiom is modelled.
- **Remaining 73 KB:** 18.4% of the object is not decoded. A sample shows
  weather and other strings, tables, and routines no seeded path reaches
  (functions entered only through the 83 `call [memory pointer]` sites, such as
  `[0x55DC]` and `[0xEFF0]`). A relocation-aware cross-reference gives 499
  object-1 fixup targets, 224 of them undecoded and only 4 with a standard
  prologue, so address-taken targets are mostly data, not callbacks; they were
  **not** promoted. The 101 prologue-shaped candidates are shape-only evidence.
- **207 of the 635 function starts lack the `push ebp; mov ebp, esp` prologue**:
  these are the Miles AIL and runtime routines (for example `0x651F3`,
  `0x6534B`), which use another convention. Do not use the prologue as the
  function-start test on its own.

## Reassembly ratchet and data guard (2026-10-05)

`tools/re/ratchet_le.py` re-encodes every decoded instruction of object 1 with
NASM, compares it at its intended offset with the original bytes (raw file bytes,
before loader fixups), demotes only the mismatching instruction to `db`, then
rebuilds the whole object. Branches are `$`-relative with an explicit short or
near form. Each instruction is assembled in its own 16-byte slot, so a wrong
length cannot shift its neighbours and no `nasm -l` listing is parsed.
Frozen in `re/ratchet-baseline.txt`; regenerate with `python3
tools/re/ratchet_le.py --baseline` (needs `nasm` on PATH).

| Measure | Value |
|---|---:|
| Instructions decoded | 97,013 |
| Re-encoded exactly by NASM | 96,271 (99.24%) |
| Alternate encoding, bytes kept with the mnemonic | 678 (0.70%) |
| Demoted to `db` | 64 |
| Real-instruction bytes (exact plus alternate) | 328,522 of 402,741 (81.6%) |
| Whole-object SHA-256 of the rebuild equals the original | yes |

- **Alternate encodings:** Watcom emits register-register ALU and MOV with the
  direction bit set (`8B EC` for `mov ebp, esp`, `03 D3` for `add edx, ebx`);
  NASM always picks the other form and nothing selects it. These 678 are emitted
  as `db` with the mnemonic in a comment, recognised only when the two bytes
  differ by exactly that bit and a swapped ModRM. Wide immediates need `strict
  dword`/`strict word` (`sub esp, 4` is `81 EC 04 00 00 00`, `cmp ax, 1` is
  `66 3D 01 00`); disp32 on a small displacement needs `dword`.
- **The 64 residual demotions** are 42 `mov` and a handful of `xchg`, `rep`
  forms, `movzx` and a `cmp`/`sub` accumulator form; mostly segment-prefixed or
  prefix-ordered encodings (`26 66 8B ...`). They are still byte-exact as `db`.
- **Data guard extended** to 56 NUL-terminated printable runs of 10 or more
  characters (95 regions in all); none is decoded. Shorter strings, numeric
  tables and padding remain unguarded, so this is a floor.
- **What this does not show:** that the 18.4% not decoded is data (a sample
  contains unreached routines), nor that any mnemonic is understood. It proves
  that the decoded instructions are the right bytes and the right lengths.

## Indirect calls: where the 87 sites go (2026-10-05)

The 87 unresolved sites group by pointer operand: 66 are `call dword ptr [abs]`
through an object-2 global, the rest go through a stack argument (`[esp+0x44]`
9, `[ebp+0x20]` 5, callback frames), a register or a table. For the 66:

1. **Statically resolvable (5 sites):** `tools/re/disasm_le.py` now also reads
   object-2 fixups (initialised pointer data) and `mov [loc], imm32-with-fixup`
   stores (`resolve_pointers`, fixed point in `build`).
2. **Display driver loaded at run time (49 sites, 9 globals):** the globals at
   object-2 offsets `0x55B8..0x55E8` are a 13-entry export vector copied, rebased,
   from `LIB/DRV/VESA480.DLL` (19,028 bytes, an `LX` driver with no entry table) to
   RAM `0x218AED`. Evidence: the DLL's first 52 bytes are the vector (link
   addresses `0x110DC, 0x13E7B, ...`), all nine addresses seen in the menu dump
   equal `0x218AED + vector[i]`, and after applying its 261 fixups at that base the
   loaded image equals the file byte for byte except in `0x430..0xBFF` (runtime-
   written tables) and a few bytes at the end. The 26 calls through `[0x55DC]`
   (export 9, palette write) and the other 23 are the display driver API; it is part
   of every route's dependency closure. See `analysis/display-driver.md`: exports 0, 5,
   8 and 9 (mode info, vsync, palette read and write) have confirmed cdecl contracts
   from disassembly and a traced run; the three copy exports (6, 7, 11) are still open.
   *(An earlier version of this note guessed `EXE/A32GFX.DLL`; that was wrong.
   The role of `A32GFX.DLL` is not established.)*
3. **Resolved from the menu dump (7 globals, 6 distinct functions):** `[0x74F8]`, `[0x74FC]`,
   `[0x7500]`, `[0x7D24]`, `[0x7D28]`, `[0x7D30]` and `[0xB7CC]` hold object-1
   functions (`0x63D40` is a bare `ret`, a default handler). They are seeds of
   medium confidence: seen as values, writers unobserved.
4. **Null at the menu (the rest):** `[0x7D2C]`, `[0x7F4E..0x7F5A]`, `[0xEFF0]`,
   `[0xF000]`, `[0xF004]`, `[0x5491]` read 0 here; they belong to other states
   (an install routine nulls `0xEFF0/0xF000/0xF004` at `0x4AB4D..0x4AB61`).

`re/seeds.txt` now has 21 seeds plus 9 `DYNPTR` records (not code seeds).
Descent: 97,204 instructions, 329,429 bytes (81.8%), 642 functions. The ratchet
baseline was re-frozen as a reviewed increase: 96,462 exact, 678 alternate, 64
demoted (unchanged), 329,118 real-instruction bytes.

## Startup timer dependency resolved (2026-10-06)

Status: `RESOLVED` for the measured splash stall. The no-sound configuration
was necessary but insufficient: the oracle also needs a real DOS mouse driver.
The unchanged executable now progresses through credits and reaches the main
menu with Start Game, Load and Quit visible. This is DOS reachability evidence;
there is still no JavaScript or Falcon implementation.

The instruction-level dependency explains the failure:

- File `0x92E53..0x92E78` resets the mouse through `INT 33h`, function zero,
  via `0xAFC75`. At `0x92E6A` it requires returned AX = `0xFFFF`; otherwise
  it returns failure before the later timer registration.
- File `0x92F90` supplies callback offset `0x39DD7`; `0x92F96` calls the
  timer-slot allocator at `0xAD85B`. The subsequent calls at `0x92FB4` or
  `0x92FC6` configure 60 or 70 Hz, and `0x92FD4` starts the slot through
  `0xAD983`. In the measured 480-row mode the slot period is `0x411A`.
- The callback maps to file `0x9207B`, runtime `0x1B6DD7`. Its instruction
  at `0x92086` increments the relocated dword `0x1E21BA`, which the wait
  routine at file `0x8F032` compares at `0x8F068`.
- The IRQ0 route reaches the timer dispatcher at file `0xAD497`, runtime
  `0x1D21F3`, through extender selectors `0x0070` and `0x0080`. It scans 17
  slots; state 2 admits a slot, with elapsed/period and callback tables at
  data offsets `0x7632`, `0x7676` and `0x75CC` respectively. The no-driver
  snapshot had active slots 0, 1 and 16, but none pointed to the increment
  callback. With CuteMouse, slot 1 is state 2 and callback `0x1B6DD7`.

The improved `work/probe_timer_runtime.py` locates a unique unrelocated prefix
of the wait routine in a stopped RAM snapshot and validates the relocated CMP
operand and branch. It also checks that the candidate callback increments that
same timer. This avoids calibration failure when a timed pause happens to land
in an extender IRQ gate. It rejects another executable build, ambiguous
instances, a changed wait branch and a short RAM snapshot.

### Driver identity and staging

The dependency is CuteMouse 2.1 beta 4, from the FreeDOS repository package
[ctmouse.zip](https://fd.lod.bz/repository/latest/base/ctmouse/20250409.8/ctmouse.zip).
The [upstream project](https://cutemouse.sourceforge.net/) describes its BIOS
PS/2 interface. Package SHA-256:
`f5d00e98e81d06060db0d1f36e4f51d44447fd0c794dc2cedd9a1cc696e3bee2`.
ZIP CRC verification passes. Extract only `BIN/CTMOUSE.EXE` to ignored
`work/dos_files/ctmouse.exe`; its SHA-256 is
`822cf550c9e19a22785722d2306aa08ede10ff20bfe931d5a81a15f77c5f363e`.
The builder verifies that binary identity, stages it outside the pristine game
tree, and runs `C:\CTMOUSE.EXE /P` before the original `PG.BAT`.
`MOUSE.LOG` reports `Installed at PS/2 port`.

`--run-game` now requires this pinned driver by default; `--mouse-driver`
selects its host path. `--without-mouse` explicitly reproduces the earlier
diagnostic setup. `--out` supports a separate working image without replacing
the existing oracle disk. No original game files or executable bytes changed.

### Reproduction and measured result

```text
python3 work/build_dos_hdd.py --use-no-sound --run-game --hold --no-boot \
  --out work/qemu_out/pg-mouse.hdd
python3 work/probe_timer_runtime.py --hdd work/qemu_out/pg-mouse.hdd \
  --seconds 5 --watch-seconds 4
python3 work/run_qemu.py --hdd work/qemu_out/pg-mouse.hdd --timeout 28 \
  --key 8:spc --key 12:spc --key 16:spc --shot 20 --shot 26 --cat ::/MOUSE.LOG
python3 work/test_timer_probe.py
```

Validated on macOS with `/opt/homebrew/bin/qemu-system-i386`, QEMU 11.1.2,
machine `pc`, CPU `486`, 16 MB, standard VGA, MS-DOS 6.22 and the previously
hashed DOS-generated no-sound configuration. The timer watch stopped at
`0x1B6DE8` immediately after the increment: `0x64 -> 0x65`, reporting
`watch:1e21ba`. The four placement regression tests pass. A separate
no-input run reached the credits; the three Space inputs above reached the
main menu at 26 seconds. The held game ends these screenshot runs by the
requested host timeout, so the runner's exit 1 is not a guest startup failure.

Evidence logs: `work/qemu_out/timer-20261006-mouse.log`,
`pg-mouse-run.log` and `pg-mouse-menu.log`. Menu capture:
`work/qemu_out/pg-mouse-menu.png`, SHA-256
`2c9ffc9de35526328e305e5040f86a79605e6eb14851f3a12ed884dbb561a1ac`.
These are ignored derived artifacts. Source and driver hashes plus the staging
recipe establish their inputs; the working disk is mutable, not a new authority.

## Next executable work

The active DOS route now reaches standalone Poland's tactical map through real
mouse input: see [scenario-route.md](scenario-route.md). Successful handles and
all selected raw reads are checked in [scenario-loader.md](scenario-loader.md).
Recover decoded destination state, using the existing
`sub_<vaddr>` inventory and corrected LE map. Close the TACMAP resource and
VESA480 display-driver dependencies before implementing the JavaScript reference
and m68k counterpart. The driver copy exports (6, 7, 11) are now decoded
(display-driver.md; stretch and shadow paths untraced) and the untraced exports
(2, 3, 10, 12), numeric data guards and overlapping instructions remain open;
audio remains separate in `analysis/audio.md`.
