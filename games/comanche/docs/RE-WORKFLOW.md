# DOS reverse-engineering workflow

The distribution and measured binary boundaries are documented in
[ASSET-INVENTORY.md](ASSET-INVENTORY.md). The important rule for Comanche is:
extract the installation, unpack `COMANCHE.EXE`, and only then disassemble it.

The current installed tree contains 92 files totalling 7,037,871 bytes. The
on-disk `COMANCHE.EXE` is only 61,154 bytes because it is LZEXE 0.91-packed;
its unpacked load image is 386,823 bytes. The rest is overwhelmingly external
game data.

## Asset preparation

The ready-to-copy hard-disk directory is:

```text
assets/extracted/comanche_hdd/
```

It represents `C:\COMANCHE\`. The raw floppy images, floppy files, rebuilt
SFX, and payload extraction are retained under
`assets/extracted/001758_comanche/` for reproducibility.

`OVERKILL.EXE` is an LHA self-extractor, not the game executable. The actual
game binary is `COMANCHE.EXE` inside the extracted installation.

## Unpack the main executable

`COMANCHE.EXE` has the LZEXE 0.91 `LZ91` marker at MZ offset `0x1C`. Its
packed bootstrap entry is `0ED1:000E`; the real program entry recorded by the
bootstrap is `0000:09BC`.

Use a standard `UNLZEXE` implementation before any static analysis:

```bash
unlzexe assets/extracted/comanche_hdd/COMANCHE.EXE \
  re/unpacked/COMANCHE.UNPACKED.EXE
```

If no standalone `UNLZEXE` is available, the Rust `lzexe` crate provides a
compatible command-line tool (`cargo install lzexe`). Keep the resulting
executable in the ignored `re/unpacked/` directory.

## First pass

```bash
python tools/re/mzinfo.py re/unpacked/COMANCHE.UNPACKED.EXE
python tools/re/codemap.py re/unpacked/COMANCHE.UNPACKED.EXE
```

`mzinfo.py` establishes the MZ header, load-module size, entry point, stack,
and relocations. `codemap.py` gives a rough code/data map; it is a heuristic,
not a disassembly proof.

## Trace the milestone route before porting

Static recovery is not the source-generation boundary. Before creating or
changing JavaScript or M68k sources for a milestone, run that milestone on the
authoritative DOS image under QEMU's TCG `exec,nochain` execution extension with a repeatable
input schedule. Capture the reached function entries, indirect-call targets,
resource reads and pointer assignments, state transitions, and per-frame order;
pair the execution log with state/memory snapshots and a checked-in route
manifest. Then create the JavaScript and M68k function records/sources only for
the contracts represented by that route. Anything not reached or not explained
stays `dormant`/`Unproven`, even if a disassembler or browser experiment makes
it look plausible.

For the current attract route, the reproducible helpers are
`work/run_qemu_exec_trace.py`, `work/trace_attract_report.py`, and
`work/inspect_qemu_state.py`; their reports live under `work/qemu_out/`.
Future milestones must provide the same three classes of evidence before their
source files are treated as part of a supported port.

## Image layout

The unpacked load module is 386,823 bytes, but it is not 386,823 bytes of
material. The measured layout is:

| Image range | Size | Contents |
|---|---:|---|
| `0x00000`-`0x016FF` | 5,888 | Real-mode bootstrap: XMS/VCPI detection, GDT/IDT build, mode switch |
| `0x01700`-`0x3421F` | 207,648 | The 32-bit flat program: code, tables, strings |
| `0x34220`-`0x5E7C7` | 173,287 | Zero-filled BSS emitted by the linker |

The trailing zero run is 44.8% of the file. Coverage percentages must be
measured against the 207,648-byte content region, not the load-module size;
`disasm.py` detects and excludes the BSS automatically and prints both
figures. The last seven bytes of the image, at `0x5E700`, are `KF.` followed
by two `mov ax,ax` filler instructions - the author's initials, and a useful
sanity marker that the unpack produced the whole image.

## Segment model

This is the fact that decides which tool is correct, so it is worth stating
precisely: **the bootstrap is 16-bit, and the game is 32-bit flat.** The two
need different address models, and mixing them produces confident nonsense.

The bootstrap builds its GDT with a descriptor helper at `0000:14A7` that
takes the base in `EAX`, the selector's byte index in `SI`, and the access and
flag bytes in `CX`, with the limit hardwired to `0xFFFF`. Its seven call sites
at `0000:0B21`-`0000:0B95` are ordinary code, so the entire descriptor table
is recoverable statically:

| Selector | Base | Granularity | Type | Role |
|---|---|---|---|---|
| `0x08` | image `+0x1700` | 4 GiB, 32-bit | data | Game `DS`/`ES`/`SS` |
| `0x10` | image `+0x0000` | 64 KiB, 16-bit | code | Bootstrap's own protected-mode code |
| `0x18` | image `+0x1700` | 64 KiB, 16-bit | data | 16-bit view of the same data |
| `0x20` | image `+0x1700` | 4 GiB, 32-bit | code | **The game's code segment** |
| `0x28` | `0x000A0000` | 64 KiB | data | VGA framebuffer |
| `0x30` | `0x00000000` | 4 GiB, 32-bit | data | Flat physical/linear window |
| `0x38` | extender arena | 4 GiB, 32-bit | data | Extended-memory arena, reached through `GS` |

The `MOV EAX, imm32` immediates feeding those calls are MZ relocation entries,
so the bases are load-address-relative; the offsets from the image base are
fixed and are what the table records.

Two consequences do all the work:

1. Selectors `0x08` and `0x20` share one base. Code and data therefore use a
   single origin, so a pointer read out of a table is directly a code or data
   offset in the same address space, with no per-segment bookkeeping.
2. That base is image offset `0x1700`. Disassembling with that origin makes
   every printed address identical to the offset the program itself uses.

The handoff runs `MOV CR0` at `0000:0BB5`, the CS-relative store at
`0000:0BCB`, `LJMP 0x10:0x0C01` at `0000:0BFC` into 16-bit protected mode, and
then `LJMP 0x20:0x1538` at `0000:0C01` into the 32-bit segment. **Flat offset
`0x1538` is the 32-bit entry point**, and the code there loads `DS`/`ES`/`SS`
with `0x08`, `FS` with `0x30`, and `GS` with `0x38`, which is what confirms
the table above against running behaviour rather than against its own
construction.

The IDT is a static 256-entry template at image `0x70`, every vector a 386
interrupt gate through selector `0x20`. It is patched at runtime, so the
offsets in the file are placeholders and are not handler addresses.

## Recursive disassembly

Two passes, one per address model. Neither is a fallback for the other.

The bootstrap, in `seg:off`:

```bash
python tools/re/disasm.py re/unpacked/COMANCHE.UNPACKED.EXE \
  --out re/listings/comanche-bootstrap.lst \
  --seed 0000:09BC \
  --scan-calls 0 \
  --no-inline-detect
```

Use `--scan-calls 0` here. Byte-scanned `call rel16` targets otherwise seed
large parts of the 32-bit image as 16-bit code, which inflates coverage
without producing a single correct instruction.

The game, in 32-bit flat:

```bash
python tools/re/disasm.py re/unpacked/COMANCHE.UNPACKED.EXE \
  --flat 1700 \
  --out re/listings/comanche-flat32.lst \
  --scan-calls 2 \
  --no-inline-detect \
  --inline-terminator nul \
  --inline-string 15cdc --inline-string 15d40 --inline-string 15dd0 \
  --inline-string 15e6e --inline-string 16381
```

The five `--inline-string` routines are Comanche's resource-loader family, and
they are not optional. Each opens with `pop ebx`, taking its own return address
as a pointer to a NUL-terminated filename placed directly after the call, and
between them they have 77 call sites naming 48 distinct resources. Without the
declaration the decoder walks straight into the filename bytes after every one
of those calls.

`--inline-terminator nul` is equally load-bearing. The scanner's original
convention was the F29 high-bit terminator, which runs past Comanche's NUL and
stops on the first following byte with bit 7 set - typically the `0x82` of a
`jb rel32`. Decoding then resumed two bytes inside a real instruction. The
symptom is a `db` line whose quoted text ends a few bytes past the terminator;
declaring the routines but leaving the terminator wrong scored *worse* than not
declaring them at all.

`--flat ORIGIN` switches the decoder to 32-bit, addresses to plain 32-bit
offsets, and the call scanner to `call rel32`. Seeds are plain offsets, not
`SEG:OFF`; a selector is not a paragraph and cannot be reinterpreted as one,
so the tool rejects that form rather than guessing. Flat seeds live in
`re/seeds-flat.txt`, separate from the 16-bit `re/seeds.txt`, because an
address from the wrong model is silently plausible in the other.

The current flat pass reaches 33,614 instructions and 120,430 bytes, 58.0% of
the content region, from 138 call targets.

That percentage is measured against a denominator that includes every table and
string in the image, so it is not the number to read. Counted properly nothing
is left over:

    decoded by the pass       120,514
    identified as data         69,750
    padding                    17,384
    unaccounted                     0
    undecoded inside a func         0

Every byte of the content region is in exactly one of the first three rows, and
both of the last two are empty. That is what a complete disassembly of code and
data means here: an instruction the walk decoded, a row that says what the
bytes are, or padding.

The last line is the strict one. It counts bytes inside a routine the store has
identified that the walk never decodes, and closing it meant splitting 21
routines around the data they carry - strings they print, tables they read, the
blank pilot record pilot_select_ui ends with. A routine that contains data is
not one row, it is code, data, code.

The barrier check is what kept that honest. Fourteen of the runs first
annotated as data came back as "known data regions disassembled as code" once
the new seeds reached the routines around them: they were never data, they were
code nothing had walked into yet. They were withdrawn. The remaining indirect control flow
is the productive place to work: 15 sites, of which the `jmp dword ptr`
entries are jump tables that can be read straight out of the image because
data shares the code origin.

### Calls through a pointer in memory

`resolve_pointer_calls` follows two shapes the direct-`call rel` scan cannot
see at all:

```text
call dword ptr [0002A980]
mov ebx, dword ptr [0002A980] / call ebx
```

The pointer is a constant in the image, so the target is statically knowable.
This is worth having for a reason beyond coverage: that second shape at
`00006501` is how the resource palette remap at `0002B949` is reached, and
because no scan could see the edge, the whole question of which palette the
terrain uses survived a DAC capture, a purpose-built TSR and a long argument
with rendering evidence before being found by reading the bytes by hand.

Two rules keep it honest. A slot still holding zero is skipped - those are
vectors filled at runtime, and there are many. And the register shape accepts
any register the program actually calls through, not only the ones
`--function-pointer-reg` admits for immediates: the evidence is different in
kind, since a memory slot holding a code address that gets loaded and called is
a function pointer by construction, where `mov si,0xFC00` is a data pointer that
merely resembles one.

**What it is worth now is nothing, and the guard is what shows that.** The
figures this section used to quote - 30,284 -> 31,230 instructions and
108,522 -> 115,138 bytes, 52.3% -> 55.4% - are withdrawn. They were measured
before `pad` rows became barriers, and the gain was not code.

The resolver returns eight targets. Six are already in `re/seeds-flat.txt`,
recorded there when they were first resolved, so they are reached with or
without it. The other two are `0000270F` and `000040E2`, and neither is code:
`0000270F` is 0x62D bytes inside `dma_buffer_8k`, and `000040E2` is
`dma_len_word`, the sound-record sentinel that `sound_playback` compares
against its voice slots and never dereferences.

That is where 55.4% came from. `dma_buffer_8k` is 8192 bytes of 0x80, which
decodes forever without a junk opcode, so the descent walked in at `0000270F`
and counted the fill as instructions. With the barrier in place both targets
stop dead and the pass reaches the same 30,305 instructions whether the
resolver runs or not.

The resolver is not wrong to exist - `00006501` is how the palette remap at
`0002B949` is reached, and that edge was found no other way - but on this
image every target it still contributes beyond the seeds file is a data
pointer that resembles a function pointer, which is the failure this section
warns about two paragraphs above. Anything it produces needs the same barrier
check before it is believed.

### --known-data as a barrier

`--known-data ADDR[:LENGTH][=NAME]` takes an address in the notation this tool
prints, and with a length it becomes a barrier: the descent stops rather than
walking into the region. That keeps established tables out of the coverage
figure and, more usefully, reports where a walk tried to enter one - each of
those is a defect upstream, either a seed that is not code or a function whose
end the descent could not see.

Three generators feed the pass, all reading the annotation store:

```bash
python3 tools/re/known-data-args.py   # --known-data barriers
python3 tools/re/func-seeds.py        # --seed per settled func row
python3 tools/re/gap-seeds.py         # --seed per unreached filler-led run
```

`func-seeds.py` matters because a routine the store has identified is an entry
point the walk may have no other way to reach. span_writer_unrolled is 1,023
bytes entered only through `lea ebx,[ebx*4+00006BF0] / jmp ebx`, a computed
target, with no direct call anywhere; one seed at its head walks the whole run.

`gap-seeds.py` finds what is left by looking for the linker rather than for
code: it seeds an unreached run only when the run OPENS with the `2E 8B C0`
inter-routine filler, which is the linker saying a routine starts there.
Decoding cleanly is not evidence on its own - `01 02 03 04` at 00004C8B
disassembles perfectly happily as `add dword ptr [edx],eax` - so the filler is
the discriminator and the decode probe only a second check.

Its output belongs in `re/seeds-flat.txt` rather than being regenerated each
run. It reads the listing, so a run without the seeds produces a listing with
the gaps back and the next run rediscovers them: left unrecorded, coverage
oscillates between two states instead of converging. Recorded, it converges in
five passes.

Generate the barrier arguments from the annotation store:

```bash
python3 tools/re/disasm.py ... $(python3 tools/re/known-data-args.py)
```

`table`, `data`, `string` and `pad` rows all become barriers. `pad` was added
last and matters most: a run recorded as this linker's 0x80 fill is
established as not being code, and 0x80 repeated decodes forever without a
junk opcode, so a walk that enters one produces thousands of plausible
instructions and counts every byte. `dma_buffer_8k` alone is 8192 bytes of it.

Treat the guarded number as the real one. The unguarded pass reports 56.4%
because it counts tables it walked through.

`--scan-calls 1` is now safe and is the setting used. This section previously
said 2 was "the highest setting that leaves every known data region alone" and
that 1 "reaches 66% but disassembles data regions as code". Both were true when
there were a handful of barriers; with 244 the pass reports "all 244 known data
regions left alone" at either setting, and the 66% was mostly tables being
walked. 1 is worth 52.3% -> 53.1% of honest coverage.

An earlier version of this section quoted 71 and 76 regions "disassembled as
code". Those figures were wrong: `--known-data` compared its argument against
`Addr.linear`, which is `IMAGE_ORIGIN + off`, so under `--flat 1700` it was
matching flat addresses against linear ones and reporting whichever regions
happened to sit 0x1700 away. The barrier work fixed the conversion; the real
count is single digits.
0x00       end of string
0xFC       skip (742 of them in the data - inter-column padding)
0xFD/0xFF  layout codes
0xFE       record a hotspot: pen position and eax into 8-byte records
           at 00026550, count at 00026590
0x7C '|'   escape; next byte selects a colour
0x01-0x0A  direct colour codes
otherwise  blit a glyph
```

Note the shape of the colour branch at `000270B1`: it loads the **default first**
and then overrides, so any unlisted letter renders white - which is why `|w`
works in the data without appearing in the code. Reading the chain as a plain
switch would have produced a wrong table with `|w` missing.

Every colour target is a `colour_constants` entry resolved at startup by
`palette_match_nearest`. So the chain now closes end to end: **loaded palette →
weighted nearest-colour match → resolved index → markup code → the blitter's
`bh`**. That last link is also the answer to the one thing left open when the
font block was recorded - `bh` is the text colour, set here, which is why the
blitter appeared to write two values to one address.

Three subsystems recovered in three separate commits turned out to be one
pipeline. Worth remembering when a routine looks incomplete: the missing half
may already be in the store under another name.

### A state block is inventoried, not decoded - and the ledger should show that

`00019D80`-`0001B26C` is the game's global variable block: data, 75% zero, not
one `0xC3` byte in 5,356. There is no structure to recover. It is 104 distinct
globals touched from 989 absolute `[0x...]` operands in reached code, and the
only useful deliverable is an inventory ranked by site count, which regenerates
from the listing in one pass.

The temptation is to give the whole region a row and book 1,317 bytes of
material as classified. **Don't.** Naming a region is not the same as
understanding its contents, and this store's value is that a classified byte
means something was proved about it. Only nine globals here have a decoded use,
so only those nine got rows; the ledger moved 24 bytes and the remaining
hundred-odd stay outstanding, which is the honest reading.

Two were pinned while building the inventory, both from arithmetic rather than
from naming:

- `00019DC4` is stepped `add 0x52` and clamped `cmp ...,0x300C`. `0x300C / 0x52`
  is exactly 150, so it is a row offset into a surface with an **82-byte row
  pitch** - and `0x52` is the same advance the font blitter uses between pixel
  pairs, so both touch the same surface.
- `00019DFC` is a byte accumulated with add/sub across 44 sites and read by both
  renderers as `mov al,[0x19DFC] / not al / shr al,1` into the low byte of
  `00019EDC` - a heading, though the angular convention is not established and
  is not claimed.

The single most-referenced global in the block, `00019D80`, has 386 of its 388
sites as `add al,byte [0x19D80]` at a 0x42 stride inside `terrain_setup_192` -
one per column of the unrolled setup, twice per column. A site count that lopsided
is itself the finding: it says the global is a per-frame constant folded into
every column, not a variable the setup reads once.

### The bitmap font block, and letting a signature be a coincidence

`00027276` opens with the ASCII bytes `KF4b`, and "KF" is the author's initials -
the same two letters the image's own trailing marker uses. The tempting read is a
resource-container magic. It is not one: `KF` occurs exactly once in the whole
flat image, and no file in the installed tree begins with it. The signature is
local to this block, and treating it as a format tag would have sent the next
session looking for a container that does not exist.

What the block actually is, established from its two readers rather than from
its bytes:

```text
+0x000  "KF4b", then height 0x0A (10 rows) and a 1 byte at +5
+0x008  128-byte width table, character code -> advance width (2..10, 104 used)
+0x088  128-word offset table, offsets relative to the BLOCK BASE 00027276
+0x188  glyph data, width*4 bytes per glyph
```

The glyph stride was not assumed. Across every consecutive pair of used
characters the offset delta equals `width*4` exactly - 2→8, 3→12, … 10→40 - so a
glyph is **4 bytes per column**, one 32-bit column mask with 10 rows used. The
blitter agrees: `mov edx,[esi]` loads a column and `shr edx,1` walks it downward.
And the first glyph offset, 392, lands exactly on `000273FE`, the end of the
offset table - an internal check that the base-relative reading is right.

This one is in scope. The first milestone includes the HUD and menus, and the
build extracts this layout through `tools/prepare-original-test.py` rather
than maintaining a second, invented font.

### The music driver is deferred scope, and saying so is the result

The largest remaining hole in the data segment, `0002C70D`-`0002D16C`, is the
AdLib/OPL2 music driver's data. [PORTING-PLAN.md](PORTING-PLAN.md) and
`AGENTS.md` both exclude sound from the first playable milestone, so this is
recorded to stop the region being re-triaged as unknown, not as porting work.

The identification is not by inference. Two of the per-channel tables are the
textbook OPL2 (YM3812) operator-offset maps:

```text
0002D11F  00 01 02 08 09 0A 10 11 12   modulator offsets, 9 channels
0002D128  03 04 05 0B 0C 0D 13 14 15   carrier   offsets, 9 channels
```

and the code reading them guards on `cmp ch,9`, the OPL2's nine melodic
channels. The hardware agrees: an image-wide scan for `mov dx,imm16` followed by
`in`/`out` finds only `0x331` (MPU-401 status, polled with `test al,0x40`) and
`0x388` (OPL index) anywhere in this cluster.

Table boundaries came from the code rather than from pattern-matching, which is
what made them trustworthy: `0002C269` does `movzx ebx,al / shl ebx,4 /
add ebx,0002C70D`, a 16-byte record indexed by a byte, and `0002C396` repeats it
with base `0002CF0D` - exactly `0002C70D + 0x800`, i.e. 128 records later. That
gives 128 instrument patches followed by a 256-word monotonic pitch table.

**Worth carrying forward as a scope signal:** a good share of the remaining
unclassified material is deferred-scope sound. Coverage and ledger percentages
should not be read as distance from a playable port.

The same port scan is useful for what it found elsewhere. `0x3C4` appears at 45
sites and `0x3CE` at 18 - the VGA Sequencer and Graphics Controller - so the
original drives planar VGA directly, which the Falcon side replaces wholesale
rather than translates.

### The palette matcher, and reading weights out of a table's constants

`0002ABCD` is data (`0xC3` density 1/1000) and resolves into three 256-entry
tables of `c * min(k,256-k)^2` with `c` = 900, 3025 and 225. Those are `30^2`,
`55^2` and `15^2`, and **30 + 55 + 15 = 100**: the constants are a perceptual
luma split, R 0.30 / G 0.55 / B 0.15, with the squaring folded into the table.
Reading the constants that way is what named the tables before any code was
decoded.

The `min(k,256-k)` form is not decoration. Differences are taken with `sub al`
on bytes, so a negative difference wraps to `256-|d|`, and indexing a folded
table takes the absolute value for free. **A symmetric table usually means the
index is a wrapped signed difference.**

`0002B820` uses all three: three `lodsb` per entry (so the palette is 3-byte
RGB), each difference indexing its own weight table and summing into `edi`, with
`edx` the best distance and `ebx` the best index - a plain argmin, i.e. a
weighted nearest-colour search. Its 12 callers are one loop building an
inverse-lookup remap table and ten one-off calls resolving fixed colours to
palette indices at `0002A374`-`0002A37D`: white, three greys, blue, red, green,
magenta, orange, amber, all as 6-bit VGA DAC triples.

The byte immediately after that block, `0002A37E`, is the one
`viewport_fill_plain` replicates into its fill dword. A fill colour sitting as
the next entry after ten resolved palette indices is independent support for
reading that routine as a fill rather than the buffer clear it was first
recorded as.

The palette itself, `0002A680`, is 768 zero bytes in the image - filled at
runtime from a resource. The matcher and its tables are fully recoverable
statically; its *input* is not, which is the recurring limit in this binary.

### Rank by unclassified material, not by the tool's own list

The unreached-region table keeps re-listing regions that are already fully
classified, because data is never "reached" - the object table sat at the top of
it for two sessions after being completely recovered. Subtract the annotation
store's ranges from each region and rank by what is left. That reordering is
what surfaced the data segment as the real next target.

### The scanline row table, and a table sized to the image end

The data segment at `0002C48B` clamps to the image end, so it is 26,261 bytes,
not the 199,548 the gap list prints. Two pieces of it were unclassified.

`0002D7F0` is 256 dwords of row byte-offsets for a 192-byte-pitch surface -
entries 0 to 198 are `(255-k)*192`, entries 199 to 255 zero. It is not used as
it sits: `000055ED` patches it in place, `mov ecx,0x100 / mov ebx,[00019E70] /
mov esi,0002D7F0` then `add [esi],ebx / add esi,4 / loop`, turning every entry
into an absolute row address once the destination base is known. That base is
the same one `viewport_fill_*` writes to. **A relocated table looks like
nonsense until you find the loop that fixes it up** - the static values are
offsets, and only the patch reveals they are addresses.

The second piece, `0002D5E6`, is a 128-entry pointer table read by
`mov edx,[eax*4 + 0002D5E6]`, with 126 of 128 slots pointing at a single 20-byte
default record - the same uniformly-initialised shape as the object table's
function-pointer fields, and the same lesson: statically you recover the
default, not the live contents.

Checking the data segment also corrected the sine table. Its material ran past
the extent recorded for it, and the reason is exact: the table is **640 entries,
not 512**, with entries 512-639 a byte-exact copy of 0-127 so that the cosine
read at `index+128` never runs off the end. The largest cosine index, 639, lands
at `00032B1C` - the last dword in the image, which ends at `00032B20`. The table
is sized precisely to the image end, so a port must keep the overhang or mask
the index.

### The ret-density test has a false negative on jump-chained code

`0xC3` density separates code from data in one step and has been reliable -
renderers run about 78 per 1000, pure data 0. `00028B36`-`000290C6` reads as 0
and is code: the menu, credits and briefing screens **chain by jumping to each
other rather than returning**, so 1,424 bytes contain one `ret` against 8
`jmp rel32` and 63 `call`.

Any jump-terminated state machine will do this, and this binary has several -
the object state handlers and the startup sequence are the same shape. Before
filing a region as data on ret density, count `0xE8`/`0xE9` too; a region with
dozens of calls is code whatever its ret count says.

The cheap confirmation in this case was the inline-string idiom: each of the
nine filenames is preceded by a well-formed `E8 rel32` to a known loader, and no
data region produces that by accident nine times.

### Byte statistics show that a region is structured, not how it divides

Three separate `?` candidates - `projection_curve`, `band_step_mask` and
`band_bitpattern_table` - were each guessed from byte statistics: a quadratic
run of dwords, a 0x00/0x01 mask, a field of small powers of two. All three were
fragments of **one** structure, and all three drew their boundaries in the wrong
places. `projection_curve` straddled the join, covering the tail of an offset
table and the head of the data it indexes.

The consumer settled it in one read. `000253CD` does

```text
mov eax,[00022354] / mov ebp,[eax*4 + 0001D7EC] / add ebp,0001DBEC
```

- an offset table indexed 0..255 whose values are byte offsets from `0001DBEC`.
The offsets are exactly `v[k] = 128k - k(k-1)/2`, so row `k` is `128-k` bytes
long: 128 rows, 8,256 bytes, ending precisely where the object table begins. The
row bytes are single-bit masks, so it is a scaled-sprite bit-position table.

Statistics are good at saying "this is not random". They are bad at saying where
one table stops and the next starts, because adjacent tables of different shapes
look like one table with a change of character. **Find a consumer before
committing to boundaries** - and when a candidate has sat unproven for a while,
prefer re-deriving it from a consumer over refining the guess.

### Discard xrefs that land inside bitmap data

A raw-dword scan reports 7 references to `00024900`. All seven are inside
`font_glyph_data` at `000277B9`-`00027975`: coincidental byte patterns in 1bpp
glyph bitmaps, not references at all.

Dense bitmap data will alias almost any address given enough of it, so an xref
whose *site* falls inside a known image, glyph or sample region should be
discarded before it is counted - the same discipline as the rel32-displacement
filter below, applied to the other end of the reference. Once both filters are
in place, `00024900` has no static references and is reached by fall-through,
which is the true answer.

### Filter rel32 displacements before believing a data xref

The one unresolved stretch here, `0001DCE8`-`0001F3EC`, is a 0x00/0x01 mask with
a ~2/3 duty cycle. Its reference scan is the cautionary part: 36 raw-dword hits,
and 22 are the rel32 *displacement* of a nearby call, not an address. A call
from `000077B9` to `00025880` encodes displacement `0001E0C2`, which reads as a
pointer into the range. The remaining 14 are mid-instruction coincidences like
the `0x1E0` immediate of `mov ecx,0x1e0`.

For anything in the `0001Exxx` band this is systematic, because that is the
distance between the image's low and high code. A raw-dword hit is only evidence
if the byte before it is not `0xE8`/`0xE9` and the match is not inside a longer
instruction.

### Two dispatch tables that read as empty

Two of them were first recorded as zero-filled and runtime-populated. That was
wrong, and the cause is worth stating because it is a reusable mistake: the scan
that read them stopped at the first dword that did not look like an address, and
in both cases that dword is at slot 0. `0x2003c` has a null there. `0x7bc9` is a
displacement whose valid indices start at 1, so the bytes at the displacement
are not an entry at all - the table begins at `0x7bcd`. **Read a window and
tolerate nulls; do not stop at the first miss, and do not assume the
displacement is the base.**

Seeding `0000D950` adds seven more points, to **32.7%**. That region was briefly
quarantined because it looked like data: 192 near-identical `0x30`-byte blocks,
each ending `lea ebx,[ebx*4+0x6bf0]` / `jmp ebx`, with `0x6bf0` holding one
non-address dword repeated rather than a table of pointers.

It is code, and it is the terrain span renderer. The error was reading `0x6bf0`
as a pointer table at all: `lea` computes an address and `jmp ebx` jumps **to**
it, so what sits there is 4-byte code stubs. Decoded as code it is 255 copies of
`mov byte ptr [ecx], al` / `inc ch`, closed by `mov byte ptr [ecx], al` / `ret`
at `00006FEC`. Entering N stubs in and falling through writes 256-N pixels -
Duff's device. `inc ch` adds `0x100` to `ecx` per pixel, so the destination is a
256-byte-stride buffer addressed as `ch:cl` = row:column, and each run walks
**down a column**.

The 192 blocks are its per-column callers. Each carries a distinct
`mov cl, imm8` - 192 distinct column values - its own stack slot for the run
length between `esp+24` and `esp+127`, and its own return address. The original
spent about 10 KB of code to take the loop overhead out of a vertical span fill.

That matters more to this project than the coverage points: it is independent
evidence that the DOS original draws vertical spans into a column-addressed
buffer, which is the structure `src/render.s` currently assumes on the strength
of the VoxelSpace reference alone.

The transferable rule is narrow. An indirect jump through
`lea reg,[index*4 + base]` / `jmp reg` enters an unrolled code array; it is not
a dispatch through a pointer table, and reading `base` as pointers will always
produce nonsense.

### The unreached-region table prints image offsets, not flat addresses

This one has already cost three commits, so it heads the rules for working off
that table. `disasm.py` builds
its gap list by indexing `d.image`, and prints the result under a column headed
`linear`. Every other address the flat listing prints is a *flat* address.
**The flat address of a gap is its printed `linear` value minus `0x1700`.**

Read the column as a flat address and a seed lands `0x1700` past the region it
was chosen for. That is far enough to be a different routine and near enough
that the result is still real code, so the mistake does not announce itself -
it produces a confident, fully-decoded, entirely mis-attributed finding. It is
the same failure the [image-offset section](#image-offsets-are-load-module-offsets)
below describes, one selector base further along, and it is worth checking the
two against each other whenever a region is picked off this table:

| printed `linear` | actual flat | what it holds |
|---|---|---|
| `0x0010a18` | `0000F318` | the terrain renderer and its setup |
| `0x001b385` | `00019C85` | the `viewport_fill_*` pointer globals |
| `0x00185bf` | `00016EC0` | `viewport_fill_src_a` |

The `startup_validation_region` candidate was a casualty of the same error and
has been withdrawn: the strings it quoted are real but sit at
`000162CB`-`000165F0`, inside the *linear-as-flat* window, while the gap it
named contains no ASCII runs of six characters or more at all. The tell was
reproducible - 69 runs and 756 `0xC3` bytes for the wrong window, 56 and 584
for the right one.

A seed taken this way also lands *inside* a routine rather than at its entry,
and an interior address has no callers by construction. Do not conclude
anything about reachability from an address that was never an entry point; find
the entry first, then test that.

### Rank unreached regions by material, not by size

`disasm.py` lists unreached regions largest first, and that ordering misdirects
effort. The largest by size is at flat `0002C48B`, 26,261 bytes - but it is 77%
zero, so it holds only 6,103 bytes of material and ranks fourth. Re-ranked by
non-zero content the real work sits at flat `0000F318` (21,523 bytes of
material, 663 pointer-like dwords), `00019C85` (17,793), and `00002046`
(11,399, and only 3% zero, so it is dense). The first of those is now resolved -
it is the terrain renderer, see above - and the ranking has moved on, but the
principle stands.

The `0002C48B` region is the data segment: nine initialised clusters in 26 KB of
otherwise uninitialised runtime state. Walking those clusters is what turned up
the handler table at `0002C5D9`, which resolved the last statically-resolvable
indirect site - `mov ecx,[ebx+0x2c5d9]` / `call ecx` at `0002B9EA` - after the
approach from the call site had already been tried. Reading a data region's
initialised clusters directly is worth doing on its own, not only as a follow-up
to a call site.

### Image offsets are load-module offsets

Every image offset in this repository counts from the first byte **after** the
512-byte MZ header, which is the model `mzinfo.py`, `disasm.py` and
`carve-flat.py` all use. The distinction is easy to lose because the file is
387,335 bytes while the load module is 386,823.

Reading a structure at file offset `0x1700 + F` instead of load-module offset
`0x1700 + F` lands 512 bytes early. That is far enough to be inside unrelated
data and near enough that the result still looks like a plausible answer: it is
what briefly made both dispatch tables above read as uninitialised, and it
produced a confident and entirely wrong conclusion that they were populated at
runtime. When a table reads as zeros, check the address model before concluding
anything about the program.

The report also lists branches into zero fill separately, and stops the
descent at each. A run of zero bytes decodes indefinitely as
`add byte ptr [eax], al`, so without that guard a single branch into BSS or
table padding produces hundreds of plausible-looking instructions and counts
as coverage — it was worth a full percentage point here. A target on that list
is a real signal: something branched there, so either it is patched at runtime
or the branch itself was decoded out of data.

`--no-inline-detect` turns off the inline-string heuristic. That idiom was
carried over from the F29 work; Comanche does not use it, and a false positive
makes the sweep skip real code as though it were text.

The disassembler follows proven control flow and leaves indirect jumps,
computed calls, and embedded data as explicit gaps. Add resolved entry points
with repeated `--seed`, or store them in the seeds file with one address per
line and an explanation after `#`.

Some DOS games place strings or fixed records directly after a call. Configure
those routines only after proving the convention in the Comanche binary:

```bash
python tools/re/disasm.py GAME.EXE \
  --inline-string 5b4c \
  --inline-record 6680:7 \
  --function-pointer-reg bp \
  --known-data fc00=palette
```

Do not trust higher coverage by itself. Guard known data regions and validate
findings with exact file sizes, table sentinels, decoded record boundaries,
and rendered output where applicable.

## External workbench: Cutter and rizin

The recursive-descent pass proves control flow but has no decompiler, no
persistent naming, and no data typing. Cutter supplies those without a JVM:
its bundled decompiler is Ghidra's, which is C++, so only Ghidra's framework
and GUI need Java, not the decompilation itself.

Carve the flat region first. External tools have no loader for a homebrew DOS
extender, so hand them exactly the 32-bit program:

```bash
python tools/re/carve-flat.py
```

**Load the carved file at base `0x0`, not at `0x1700`.** The file begins at the
selector base, so file offset 0 is flat address 0, and every address the tool
prints then matches `disasm.py --flat`, `re/seeds-flat.txt`, and
`X86-M68K-MAP.md`. Loading at `0x1700` - the obvious-looking choice, since that
is where the region sits in the file - biases every address by `0x1700`.

```bash
rizin -a x86 -b 32 -i re/annotations.rz re/unpacked/comanche-flat32.bin
```

In Cutter: *Advanced > Raw*, arch x86, bits 32, base `0x0`, offset `0x0`.

### The annotation store is the system of record

`re/annotations.txt` holds the durable classification; a Cutter project or a
rizin `.rzdb` does not, because a binary database cannot be diffed, reviewed or
merged. Analyse in Cutter, write what you proved back into the store, and
regenerate the tool state from it:

```bash
python tools/re/annotations.py check
```

`check` validates every row against the carved image - address in range, no two
owners for one byte, no duplicate names, evidence present - and prints the
ledger: how much material is classified and how much is left. It measures
against the 129,349 bytes of material - the content region less zero fill and
less the `0x80` filler runs - rather than the 207,648-byte region, because a
third of the region is zero and counting that as outstanding work overstates
the job by half again.

**The numerator must use that same definition, and for a long time it did not.**
`ledger()` counted each row's whole extent while dividing by material, so a row
over a mostly-zero region credited its zeros as classified material even though
those bytes were never in the denominator. `object_table_dwords` is 7,280 bytes
of extent carrying 1,300 bytes of material; `dma_buffer_8k` is 8,192 bytes of
pure zero. Together such rows overstated progress by about 41,000 bytes, which
printed as **89.7% when the real figure was 66.9%**. Every percentage quoted in
commit messages before that fix is inflated for the same reason, and the shape
of the error grows as more zero-heavy regions get named - so it looked most like
progress exactly when it was least real.

Each row now contributes only the material inside its own extent. If a future
change touches either side of that ratio, change both.

`export-rizin` projects the store into a script. Prefix a kind with `?` to mark
a candidate: it is exported as a comment only and never defines a function or a
data type, so an unproven guess cannot quietly become the thing later work is
built on.

Three rizin behaviours the exporter works around, all of which fail quietly:

- Lines beginning with `#` are not comments. The parser rejects the whole file
  as a single bad command.
- Evidence text containing `;` or `@` splits a `CCu` command, truncating the
  comment or executing part of it. Comments are emitted base64-encoded.
- Plain `af` on a raw blob follows control flow until it runs out. It reported
  a documented 158-byte routine as 2168 bytes spanning 88 KB. Where the store
  establishes an extent, the export uses `af+` with an explicit `afb+` block so
  the proven boundary wins over analysis.

That last point generalises: Cutter's analysis is a proposal, and `disasm.py`,
which follows only proven flow, is the check on it.

## Where a debugger is still required

Static analysis now covers both halves of the image, so
`tools/toolchain/dosbox/dosbox_with_debugger.exe` is no longer the only way
into the game code. It remains the right tool for what static analysis cannot
supply: resolving computed jump targets whose index range is not obvious,
observing the order and arguments of file reads, and capturing decoded
resource records in memory next to the file bytes that produced them.

Do not interpret the packed-file coverage result as a code estimate. The
packed bytes are mostly LZEXE bitstream/data, and the 207,648-byte content
region still includes tables, strings, and alignment. The instruction-byte
count is an analysis result, not a file size.

## Extender findings and porting consequences

The original 1992 release uses a homebrew DOS extender, not unreal mode. Its
startup enters 386 protected mode and touches memory through the current CS
before it has completed the normal protected-mode segment setup. Those are
DOS-runtime implementation details, not game-state or resource-format
requirements. The Falcon port must replace them with a small TOS/supervisor
platform layer and explicit arenas; it must not reproduce the mode switch.

One earlier note in this document claimed the extender uses expand-down data
segments. All seven descriptors have now been read out of the builder call
sites, and none of them is expand-down: every data descriptor is type `0x2`,
expand-up and writable, and the code descriptors are non-conforming and
readable. Nothing in this binary's GDT depends on expand-down semantics.

The more important porting consequence points the other way, and it is good
news. **The game itself is not segmented.** It runs in one 32-bit code
segment and one 32-bit data segment that share a base, with a 4 GiB limit and
no far pointers: there are no `call rel32` far forms, no 32-bit far jumps
anywhere in the image, and no MZ relocation beyond image `0x3695`, which is
the end of the extender. Every pointer inside the game is a plain 32-bit
offset from one origin. That translates directly to a flat 68030 address
space, so there is no segmented pointer ABI to unwind - only the extender's
first 5,888 bytes to discard.

The same analysis explains why the original executable is a poor portability
oracle: it depends on memory-manager behaviour, can fail when EMM386/EMM
emulation is active, and may require HIMEM.SYS. The 1992 protected-mode entry
also writes through a CS override immediately after setting CR0.PE. That is
reliably writable on 386/486 systems but can fail on later Pentium systems
depending on BIOS history. A startup crash in DOSBox or on modern x86 hardware
must therefore be separated from failures in the game logic or resource
decoders. See the [OS/2 Museum analysis](https://www.os2museum.com/wp/maximum-overkill/).

For dynamic analysis, capture the program after the extender has established
its protected-mode environment, using a 32-bit-aware debugger. For the port,
extract only the observable contracts from that run: file names and open/read
patterns, decoded resource records, game-state transitions, and rendering
inputs. Do not copy the DOS allocator, interrupt setup, segment descriptors,
or protected-mode entry code.

## Porting handoff and traceability

Reverse engineering serves the vertical-slice schedule in
[PORTING-PLAN.md](PORTING-PLAN.md). The goal is not a mechanical translation or
the highest possible coverage number. Recover the routines and data contracts
needed by the next playable behaviour, capture comparison evidence, and then
hand that bounded subsystem to the 68030 implementation.

Record every established routine or deliberate platform replacement in
[X86-M68K-MAP.md](X86-M68K-MAP.md). Use the flat address printed by the game
listing, not its image offset. Each entry must state its role, observable
contract and side effects, Falcon counterpart, status, confidence, and
evidence. If one DOS routine becomes several Falcon routines, or several DOS
wrappers collapse into one platform service, record that explicitly.

The minimum evidence for a `recovered` entry is one of:

- proven control flow plus consistent callers and global references;
- a decoded table or resource contract used by the routine;
- a debugger observation with captured inputs, outputs, or state changes;
- a comparison test that distinguishes the proposed behaviour from plausible
  alternatives.

When adding a seed to `re/seeds-flat.txt`, include the reason on the same line.
When identifying data, guard it from recursive descent and document its format
or ownership. Full generated listings and dumps remain ignored; the address
map and the appropriate document retain the durable conclusions.

The handoff markers are listed under [Segment model](#segment-model). The
bootstrap also reveals the runtime it expects: it probes XMS with
`int 0x2F AX=4300` and VCPI with `int 0x67 AX=DE00`, and selects one of two
memory-manager back ends accordingly. Neither belongs in the port.

## Supporting inspection

```bash
python tools/re/peek.py D2C0 --exe GAME.EXE --bytes
python tools/re/peek.py D43A --exe GAME.EXE --words
python tools/re/xref.py E4C5 --exe GAME.EXE
```

`peek.py` and `xref.py` still work in image offsets, so a flat address from
the 32-bit listing has to be biased by `0x1700` before it is passed to them.

The F29-specific tools under `tools/re/reference_f29/` document one proven
archive/RLE/model pipeline, but their constants must not be assumed for
Comanche.

## Element width, and getting DOS data onto a 68k

A table's element width decides whether it survives the move to a Falcon. A
dword table has to be reordered, a word table differently, a byte array and a
string not at all - and nothing in the store could say which, so every row that
is a `table` or `data` carries an `elem=N` tag in its evidence, N in 1, 2 or 4.
`annotations.py check` validates it: only table and data rows may have one, the
value must be a legal width, and the extent must be a multiple of it.

The tag is `elem=` rather than `width=` because evidence prose already says
things like "width=1012" about pixels, and a validator that reads those as
element widths turns a description into an error.

`tools/re/export-data.py` then emits the tagged regions as 68k source. **It does
not byte-swap.** A swap has to know where every multi-byte field begins and
fails silently when it does not; instead each element is decoded from the image
as a little-endian value and re-emitted as a `dc.b`, `dc.w` or `dc.l` constant,
and the assembler writes it big-endian because that is what a 68k assembler
does. A region with no `elem=` tag is refused rather than guessed at.

Run this exporter only after the milestone route has identified the consumer
and the data region it actually reaches. Static width evidence makes an export
safe; the QEMU route makes it relevant to the milestone. The corresponding
JavaScript decoder/data source and M68k emission must both link to the same DOS
record and route manifest.

```bash
python3 tools/re/export-data.py                    # every tagged region
python3 tools/re/export-data.py sin_table_q31      # named regions only
```

Currently 131 regions and 40,398 bytes convert, and the output assembles under
vasm. Every emitted block round-trips: re-encoding the constants little-endian
reproduces the original image bytes exactly.

**That round-trip tests the exporter, not the widths.** An earlier version of
this section called it "the check that the widths and offsets are right rather
than merely plausible", which it is not: the swap is symmetric, so a block
emitted at the wrong width swaps back to the original just as cleanly as one
emitted at the right width. It catches an exporter that loses or reorders
bytes, and nothing else. The widths themselves rest on the consumers found by
`find-consumers.py`, which is a separate kind of evidence and the only kind
that settles them.

89 regions are skipped as zero-filled, 17,647 bytes of them. Those are buffers
the program fills at run time, with only the linker's zero fill on disk, and
byte order does not apply to a region that holds no value yet. Emitting them
would have put kilobytes of `dc.b 0` in front of the data that matters -
`krl_input_buffer` alone is 0x2000 bytes.

Every `table` and `data` row now carries an `elem=`: 201 of 201, 55,353 of
55,353 bytes. The last 29 were short runs that no read reaches, and they were
closed on three different grounds rather than one:

- 18 hold a single repeated byte value, all of them zero. No element width
  changes such a region's image and none can be wrong, so they are recorded as
  1 on that ground and the evidence says so - it is not a claim about fields.
- 3 are `2E 8B C0` alignment filler, the `cs: mov eax,eax` this linker pads
  with, and became `pad` rows like the ones already on record.
- the rest were misread boundaries rather than unknowns, and reading them
  properly removed the gap instead of labelling it.

That last group is the useful one. `00019E10` is a 6-entry dword pointer
table, but a byte read at `00019E27` had split its last entry off as a
one-byte field; the read is `[ecx + 00019E27]` with `ecx` counted down from 6
by `loop`, so it never touches the base and the sixth dword is whole. Its
value, `00007690`, appears as an immediate fallback in the same routine.
Likewise the three bytes ahead of `str_menu_labels_b` were the string's own
`|r` colour marker: `mov esi, 000265C0` is followed by `call` into
text_render_loop, so the row began three bytes late.

## Trace-seeded disassembly (2026-08-27)

Heuristic coverage cannot tell code from data; execution can. The workflow:

```bash
python3 work/run_qemu_exec_trace.py --seconds 90 \
    --log work/qemu_out/attract-exec.log
python3 tools/re/trace-seeds.py work/qemu_out/attract-exec.log \
    -o re/seeds-flat-traced.txt
python3 tools/re/disasm.py re/unpacked/COMANCHE.UNPACKED.EXE \
    --flat 1700 --content-end 32B20 --no-inline-detect \
    --seeds re/seeds-flat-traced.txt \
    -o re/listings/comanche-flat32-traced.lst
```

A 90-second attract run logs 34,458,026 block executions at 2,701 distinct
entry points. Merging the traced listing over the heuristic one
(`comanche-flat32-merged.lst`, traced lines winning) gives 63.1% of the
201,760-byte flat region, up from 59.3% - and, more usefully, every traced
entry is a point where the instruction alignment is proven rather than
guessed.

**The trap, which cost a round here:** QEMU's exec line is
`Trace 0: <host> [<cs_base>/<pc>/...]` and `pc` is the **linear** address, not
EIP. The flat address is `pc - cs_base` (0x00006040). Read as EIP, every seed
is 0x6040 too high; the disassembler then renders the colour tables at
0x0002ABD0 as overlapping nonsense and the hottest "code" in the game appears
to be a data table. The garbage output is what exposed it - trust a listing
that looks wrong over an extraction that looks right.

**What a 90-second attract trace does and does not reach.** It executes the
main marcher (202 entries), the palette matcher at 0x0002B820 (24) and the
in-flight command chain at 0x0001959F (26). It never reaches the 96-column
renderer at 0x000137F0, its emitter at 0x00010760, or the menu region
0x00027276-0x00027D92 - those need a trace driven with `--key` into the menu,
or a saved configuration that selects the other renderer.


## Hatari throughput: what helps and what does not (measured 2026-08-28)

The port runs at about 1.8 game frames per second on the emulated Falcon, so
every capture is a wait. Three things were measured rather than assumed.

- **`--fast-forward true` is already on** in `tools/grab-frame.sh` and
  `work/hatari_probe.sh`. It removes the frame-rate limiter; it does not make
  the emulated machine faster.
- **Do not turn off `--cpu-exact`/`--compatible` to go faster.** It makes the
  *host* about 5x faster - 2100 VBLs in 4.0 s against 20.2 s - and the
  *emulated* machine about 2.5x slower per game frame: 83 VBLs per replay
  record against 33. Reaching the same replay record therefore takes longer
  in wall clock (~23 s against ~17 s), and the changed timing means a VBL
  number no longer names the same game state in both modes. Cycle-exact is
  both the accurate setting and the fast one.
- **`statesave`/`--memstate` looked like the real win and does not work here
  yet.** The debugger has `statesave`, and a snapshot taken at the first
  replay record writes a 1.6 MB `.sav`. Restoring it does not run: Hatari
  also writes a `<file>.debug` sidecar holding the breakpoints that were live
  when the snapshot was taken, and `--memstate` replays it, replacing the
  probe's own breakpoint with one that matches immediately. With the sidecar
  deleted Hatari loads the state and exits without executing an instruction.
  Worth another attempt - it would turn a 17-second probe into a
  one-second one - but it is recorded as not working rather than as a
  workflow.

What actually made the captures cheap was not an emulator flag: it was
indexing them by **replay record** instead of by VBL, so a probe can stop at
the game state it wants instead of at a wall-clock guess. See the replay
comparison section of `PORTING-PLAN.md`.
