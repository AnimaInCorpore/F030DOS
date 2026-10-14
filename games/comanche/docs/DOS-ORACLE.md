# The DOS oracle: running the original headless

*Established 2026-08-23. The family harness (`../F030Method/dos/`) seeded into
`work/`, plus the per-game half written here.*

Comanche was the last member of the family without the shared QEMU DOS oracle
(`CROSS-PROJECT.md` §6). It is also the member whose open question needs one:
the terrain marcher sits 21-23 rows off its reference through eight parameter
fits, and `METHOD.md` §4.2 uses that as the family's worked example of *tuning
against a measurement you doubt*. No scalar in a projection changes the shape
of a profile, so what closes it is a run of the original, not a ninth fit.

## What now exists

| | |
|---|---|
| `img/comanche.hdd` | 32 MB, MBR + FAT16, genuine MS-DOS 6.22, the 94-file game tree at `C:\COMANCHE` |
| `work/build_dos_hdd.py` | builds it; the per-game half, never synced |
| `work/set_boot_mode.py` | swaps CONFIG.SYS/AUTOEXEC.BAT in place (1 s) instead of rebuilding (7.3 MB recopy) |
| `work/{dosimg,run_qemu,gdbstub_probe}.py`, `work/mbr.asm` | the shared half — **synced**, never edited here (`python dos/sync.py` from `../F030Method` reports drift) |

## Route tracing is the porting gate

The QEMU DOS oracle is not only for screenshots. Before a milestone creates or
changes JavaScript or M68k source, its actual DOS route must be traced with
QEMU's TCG `exec,nochain` execution extension, a repeatable input schedule, and state/memory
snapshots. The route record must identify reached function entries, indirect
callbacks, resource pointers, state transitions, and frame order. JavaScript
and M68k sources are then generated from those traced contracts and linked to
their function records; an unreached or unexplained function remains
`dormant`/`Unproven` and is not part of the milestone.

For the current attract milestone, use `work/run_qemu_exec_trace.py` to collect
the execution stream, `work/trace_attract_report.py` to fold it onto the DOS
address ranges, and `work/inspect_qemu_state.py` to capture the active object
slots. Keep the resulting route report beside the milestone's browser proof.

```
python work/build_dos_hdd.py          # build + bootstrap boot
python work/set_boot_mode.py comanche # arm the game launcher
python work/run_qemu.py --timeout 100 --key 20:esc --shot 22 --shot 45
```

## The memory config is not a choice

Every value in `build_dos_hdd.py`'s per-game block is read out of a file the
game shipped, not picked:

- `C.BAT` — `c:` / `cd \comanche` / `comanche`, so the guest directory is
  `C:\COMANCHE` and the launcher is `COMANCHE.EXE`.
- `CONFIG.XMS` — `DEVICE=C:\dos\himem.sys`, `DOS=HIGH`, `BUFFERS=30`,
  `FILES=30`. HIMEM only; no EMM386.
- `BOOTXMS.BAT` copies `CONFIG.XMS`/`AUTOEXEC.XMS` onto a boot floppy, which is
  what makes those two files the *shipped runtime*, not just two files.

`EMMXXXX0` appears once in the unpacked `COMANCHE.EXE`, so the program can
detect EMS — but nothing shipped provides it. If a run turns out to need
EMM386, that is a finding to record with its evidence, not a knob to turn
first.

## The detail level IS a choice, and both sides must make the same one

Unlike the memory config above, this one is set rather than recovered, and it
has to be set the same way in two places or nothing measured is meaningful.

`00026211` picks a `.DTL` from the detail byte at `[00025DD4]` - `'0'` high,
`'1'` medium, anything else low - and `00015DD0` reads the chosen file to
`0x19EE0`, so the file's own first dword becomes the ring count and every
later consumer indexes fixed absolute offsets into it. The three files declare
250, 180 and 100 rings in the same 5004-byte layout.

**The shipped install selects `'1'`, medium.** `COMANCHE.MNU`'s settings block
is at `+0x18` and its first byte is that character. This project builds the
port for HIGH detail, so the oracle has to be moved to match:

    img/comanche.hdd   offset 0x392018   '1' -> '0'

That is the byte inside the image's own copy of `COMANCHE.MNU`; the extracted
asset under `assets/extracted/` is left at `'1'`, because it is the original's
bytes. `tools/build-run.sh` patches the same byte in the STAGED copy, so the
target and the oracle agree. Confirm a capture is on the right one by its own
report - `dump_marcher_tables.py` prints `250 rings` - or by checking that the
per-ring divisors it captures are `HIGH.DTL` table 0 rather than `MEDIUM.DTL`'s.

Get this wrong and nothing announces it. A 250-ring port against a 180-ring
capture produces tables that match nothing, and every symptom reads as a port
fault: `tools/prepare-original-test.py` records that generating from high
against a medium oracle once produced "250 pages that matched none of the
original's 180". The detail level is the first thing to check when a terrain
or projection comparison disagrees everywhere at once.

The flight state and the view basis do NOT depend on it - they are not derived
from the `.DTL` tables - so `certify-replay-flight.py` passes either way. It is
`certify-marcher.py`, the object fan column and the projection pages that
diverge, and only the first of those says so out loud (`ring_steps: N
(DIFFERS from the capture's M)`).

## Verified 2026-08-23 (macOS, QEMU 10.x)

1. **Boot.** Bootstrap mode expanded HIMEM/EMM386/MEM/SHARE/XCOPY/SMARTDRV
   in-guest with the genuine `EXPAND.EXE`; QEMU exited **21** (clean
   `QUIT.COM`) after 3.3 s.
2. **The tree is there.** `xms` mode: `DIR C:\COMANCHE` reports 96 entries,
   7,425,266 bytes, 25 MB free.
3. **The game runs.** `comanche` mode reaches the attract demo and renders
   terrain — captured at 12 s, 25 s, 45 s and 70 s, two visually distinct
   scenes (red canyon, green valley), cockpit and HUD complete.
4. **It is drivable, which is the part that was blocked.**
   `--key 20:esc --key 30:ret` leaves the demo and lands on the **Main
   Operations Menu** with *Begin Mission* selected (`work/qemu_out/screen_t35.png`).

Point 4 matters because `tools/oracle-capture.sh` records the opposite result
for the DOSBox route: *"a 40s every-frame run never got past the first demo, so
it never reached the pass that flies DEMO0 on the D1/C1 pair — the only map the
port loads."* Under QEMU the run is steerable, so reaching that map is a
question of which keys, not of whether.

## Two oracles, and they answer different questions

Neither replaces the other:

| | `tools/oracle-capture.sh` (DOSBox) | this (QEMU) |
|---|---|---|
| Frames | the game's **own** writer at `000165FD` — 328x240, 8 bpp, exact page | QMP `screendump`, 640x480 upscaled VGA |
| Executable | a **patched** copy (three jumps NOPped at `000189C9/D2/DB` to remove the developer-key gate) | the shipped `COMANCHE.EXE`, unmodified |
| Driving | none; it runs and dumps | `sendkey` on a schedule |
| Platform | DOSBox | genuine MS-DOS 6.22 |

The DOSBox route gives the *better pixels* — an exact 8-bit page in the game's
own format, which is what `tools/compare-terrain.py` wants for a byte-level
diff. The QEMU route gives the *real product on real DOS*, and can be steered
to a chosen scene. The obvious next step is the combination — stage the patched
`COMANCHE.UNPACKED.EXE` onto `comanche.hdd` instead of the shipped one, drive to
the D1/C1 map with `sendkey`, and read the numbered `SNAP_nnn.PCX` files back
off the image with mtools (`run_qemu.py --cat`). That exact route was not
taken. A better one replaced it on 2026-09-22: `work/capture_dos_frame.py`
leaves the executable **unmodified**. It stops at the flight loop's gate call
(`00006AE9`) at a chosen replay cursor, writes the gate's key and feature
bytes through the gdbstub, and lets the game's own `000165FD` write
`SNAP_001.PCX` to a scratch copy of the image. That file is then read back
with mtools. The page it saves is the one on screen, so it is the frame
published after the record at that cursor. See `PORTING-PLAN.md`, "The first
complete-frame pair".

Beyond frames, the harness carries two instruments the DOSBox route has no
equivalent for, both documented in `CROSS-PROJECT.md` §6 and `METHOD.md` §3.5:

- **`work/gdbstub_probe.py`** reads the running program over QMP — calibrates
  `file -> linear` by majority vote over RAM signature windows, then
  residency-checks the image. Two standing lessons travel with it: the hottest
  EIP is probably an interrupt handler (`SS == CS`, small `SP`), and screenshot
  every driven step or you cannot say which state you measured.
- **`../F030Method/dos/trace/`** — the QEMU TCG plugin that records which bytes
  actually executed, folds them onto the load module, and tallies the I/O ports
  the game touches. On a 32-bit flat program like this one it also records
  access widths, which is direct evidence for field types. Running it against
  the terrain marcher would answer "is this code even reached in the scene I am
  comparing" — a question eight parameter fits never asked.

## One rule that binds this and the port's other "oracle"

`docs/DSP-EXECUTION-PLAN.md` uses the word *oracle* for the CPU renderer
checking the DSP renderer. That is a parity check between two of **our**
implementations: it proves the DSP path agrees with the 68030 path and says
nothing whatever about what DOS drew. Only this document's oracle is ground
truth. Keep the two words apart in commit messages and doc prose, because a
sentence like "oracle-exact at zero differing pixels" reads as DOS fidelity and
is not.

## Dumping the marcher's runtime tables (2026-08-27)

`work/dump_marcher_tables.py` boots the same image and reads flat memory over
QMP at chosen times, writing `work/qemu_out/marcher-<seconds>.json`:

```bash
python3 work/dump_marcher_tables.py --at 45 --at 70 --at 95
```

It exists because the tables the surface transfer at `00007AA0` consumes are
all at or after `0x32B20`, and the 207,648-byte flat content region ends at
exactly `0x32B20` - they are BSS and cannot be read out of the image. Each
sample captures the `[0x19E4C]`-entry run list (length and the two odd-byte
plane flags from `0x38B20`, source offset from `0x32B20`, source base pointer
from `0x3AB20`, and both destination halves from `0x34B20`), the 192-byte sky
horizon array at `0x3CB40`, and the camera, roll, pitch and surface pointers
beside them so a dump is anchored to a known viewpoint.

This is DOS ground truth in the sense this document's last section insists on:
it is the original's own memory, not a parity check between two of our
implementations. Its first use verified `backdrop_build` to the byte at three
cameras - see `docs/PORTING-PLAN.md`.

### Capturing a terrain frame

```bash
python3 work/dump_marcher_tables.py --surface --shot --wait-flight 220 --settle 8
```

`--wait-flight` waits for two things in order: the flat image to be resident
(16 bytes at `0x25880` matching `re/unpacked/comanche-flat32.bin`) and then
`[0x19ED0]` to read 1, which is true only while a `DEMO<n>.SCR` replay plays.
Both guards are load-bearing - without the first, the replay flag matches on
uninitialised memory seconds before DOS has booted.

The result is `surface-<n>.bin` (the raw 256x256 chunky surface at flat
`0x40000`), `marcher-<n>.json` (the run list, the horizon array and the camera
that drew the frame) and `screen-<n>.ppm` (what the machine was displaying, so
the capture can be confirmed by eye rather than by a heuristic).

Note when reading a surface: the sky is drawn into it too, so a good terrain
frame is around 90% painted and `0xFF` marks only what no span reached. A high
painted fraction is not evidence that the frame is a full-screen image.

### Capturing at an instruction, not an instant (2026-08-27)

`stop` freezes the machine, so every read after it belongs to one instant.
That is **atomicity, not phase**. The frame driver latches state, renders and
then integrates, so an arbitrary instant pairs one frame's inputs with another
frame's outputs - and nothing about the captured data looks wrong. The only
symptom is a model that is right in form and wrong in numbers.

The marcher model scored 4.8%-16.1% against captures taken that way, moving
with nothing but where the freeze landed. Eight structural hypotheses were
raised and eliminated against those scores; **none of them was the fault.**
Breaking at the routine's own `ret` took the same model, unchanged, to
**100.0%** - 17,248 of 17,248 columns.

```bash
python3 work/dump_marcher_tables.py --wait-flight 240 --at-marcher \
        --silhouette --heightmap --surface
python3 tools/compare-marcher.py work/qemu_out/marcher-6.json
```

`--at-marcher` breaks at `0000F317`, the marcher's `ret` - after its last
silhouette copy and before `00007AA0` and the rear-view pass. QEMU takes
`-gdb tcp:...` alongside `-qmp`, so the break goes through the stub and the
reads still go through QMP. `work/rsp.py` is the whole client, about sixty
lines. Three things make it reliable:

- **Connecting to the gdbstub pauses the VM by itself**, so the breakpoint is
  armed against a stopped guest and cannot be missed.
- **The stub reports *that* it stopped, not *where*.** Read the PC back
  through QMP `info registers` and check it. A wrong-address stop otherwise
  yields a capture that looks phase-coherent and is not.
- **The stub takes linear addresses.** With paging off under the extender,
  linear = physical = `FLAT + flat_address`. Do not reuse an EIP here: the
  exec trace's `Trace 0: [cs_base/pc/...]` second field is already linear.

### Poking the original at a breakpoint: the damage chain (2026-10-07)

`work/trace_player_damage.py` does what a keyboard cannot: it stops the replay at
a chosen cursor, writes the player's damage state straight into the running
original (`M` packet: the death cue and timer, the hull, the damage cells, the
altitude, or the player's position beside a mission object) and records what the
flight handler then does, one row per event. Several breakpoints at once work
(`Z0` for each; resume with `Rsp.cont_from_break` of the address just hit), and
the stops tell the story: `00019424` then `0001947B` then `000194E0` is a crash
with its damage tail, `000192EE` then `00019424` an object collision and
`000192EE` then `00019352` none. Reads at `0001947B` and `000194E0` pair the
state the damage tail was given - including the wall-clock RNG `[00019DB8]` -
with the state it left, so a function that depends on the one input a port cannot
reproduce is still checked exactly: `tools/check-js-damage.js` feeds the
captured RNG to the JavaScript and compares 26 of 26 crashes, 98 + 99 + 60 flown
ticks and 37 of 37 collision-box samples.

Things learned while building it:

- **The stub's `g` packet reports `eip` as the offset in the extender's flat
  code segment**, i.e. the flat address the listing quotes, not the linear one
  that `Z0` and `m`/`M` take (`linear = 0x6040 + flat`). Compare the register
  with flat addresses; subtracting `0x6040` from it makes every stop look
  foreign and the loop spins.
- **Run on a snapshot** (`-drive ...,snapshot=on`): the original writes to its
  disk during a run, and the writeback drive `trace_replay_flight.py` uses
  rewrites the image.
- **Align a capture with the port by records consumed**, `(cursor - 13) / 8`,
  not by row number: a view change inside the death block (`00018F72` calls
  `00019820`, whose tail `000196B4-0001975B` runs the frame driver again) consumes
  an extra record and ticks the wreck's countdown once more inside one tick, so
  rows after it are two records further on than their index says.
- Forcing the altitude to zero at the end of every tick is a cheap crash
  generator: it gave 40 crashes in 40 ticks, including the one that crossed the
  hull to negative and fourteen crashes of the wreck that followed.

### Calling a routine of the original with chosen inputs (2026-10-07)

The cheapest oracle for a pure routine is the routine itself. `work/dos_call.py`
stops the original as a replay arms (so its stack, interrupts and tables are alive),
writes the inputs through the gdbstub (`M` for memory, `P` for registers, EIP last),
sets a breakpoint on the instruction that ENDS the routine - before it executes, so no
return address is needed - resumes, and reads the outputs from memory and registers.
No keyboard, no menu walk, no frame. It takes a few seconds a fixture and the inputs
are whatever the generator draws from a fixed seed: the number formatter and the
percentage writer, the mission statistics, the ranking sort, the mission-list scan,
decode and line skipper, the briefing wrap loop, the pilot-record paths, the row
colours and the list choice, Your Stats, the option toggles, and the new-pilot name
entry (the real key loop driven by poking `[00001B70]` at each pass of `0002807E`).
`tools/check-js-dos-calls.js` replays the same inputs through the JavaScript and
compares every output byte (14 routines, 700-odd cases, all agreeing).

Rules that made it reliable:

- Pick the ENTRY and the END from the listing so the slice has no screen or file
  call in it (`28B3C` rather than `28B37` for Your Stats; `290C0` for the wrap loop,
  not the builder; `2A1E6` for the list scan, past its file read); a slice that
  draws is harmless but slow, one that waits for a key needs the key poked.
- Set EFLAGS (`0x202`) yourself: the original's `rep movs` assume the direction
  flag is clear and not every path clears it.
- Fill every output buffer with a marker first (`0xCC`, `0xEE`, `0xAA`) so a byte
  the routine leaves alone is told from one it writes; the JavaScript side maps the
  marker to its own untouched value.
- Mind overlaps the BSS layout hides: the tenth mission name slot at `00029ED5`
  runs into the text-pointer table at `00029EF0`; compare only what the routine owns.
- The ISR keeps running while the routine does: a routine of a few hundred
  instructions never meets a PIT tick in practice, and one that reads the wall-clock
  RNG can be checked by poking `[00019DB8]` immediately before it.

### Some state is per-frame, and a capture can legitimately read zero

`--with-target` keeps taking the breakpoint until `[0x19D18]` is non-zero.

The targeting bytes - `0x21BAB` (targetable), `0x21C2D` (designator row),
`[0x19D10]` (the latch) and `[0x19D18]` (its seed) - are rebuilt every frame:
`00024BE1` clears the per-object byte and the object pass re-sets it for
whatever is on screen. So a single stop lands on a frame with nothing
targetable as often as not. One capture read all zeros while an earlier one
read a latch of 30; the field is not dead, the frame was empty.

**And an empty-looking frame is not the only trap - a centred one is worse.**
The first frame that did have a target had it dead centre, where every
candidate projection formula agrees. It looked like confirmation and proved
nothing. Only an off-centre target discriminates, which is what caught two
wrong readings of the targetability projection: the divisor is the *ring's*
lateral increment and not the object's depth, and the search key is
`depth << 3`. See `docs/X86-M68K-MAP.md`.

## Dumping the PORT's own RAM (2026-08-28)

The sections above are about the DOS oracle. The Falcon side has an
equivalent and it is worth using far earlier than it was here: `Hatari`'s
debugger, which `tools/grab-frame.sh` already drives with `--parse dbg.ini`.

```
# dbg.ini
logfile comanche-dbg.txt
b VBL = 4600 :once :file mem.ini
# mem.ini
savebin ram.bin $0 $c00000
quit
```

Three things that cost a run each:

- **The script must end in `quit`.** Without it the debugger waits and the
  log stays empty, which reads as "the breakpoint never fired".
- **`grab-frame.sh` rewrites `dbg.ini` every run**, so invoke Hatari directly
  for your own script; copy the invocation out of its `run_hatari()`.
- **Bare symbol names and `info basepage` silently abort the script.** Use
  `m $hexaddr <count>` or `savebin`.

**The linker's symbol values are not runtime addresses**, and no constant
offset maps them - a delta derived from one symbol failed on the next. Locate
structures by content: a sprite bank is `SG` followed by a plausible element
count and palette pointer; the object table is found by searching for words
*exactly* equal to a bank base, since a range test across the 1.68 MB bank
array matches image data and floods you with false positives.

**Why this matters more than it sounds.** An on-screen counter drawn through
`hud_draw_value` shows three decimal digits, modulo 1000, one value at a
time. Five conclusions in the object investigation were drawn from such
counters and all five were wrong - three from instrumenting the wrong
instance of a duplicated code path, one from reading a stale symbol address,
one still unexplained. The first RAM dump settled in a single run what the
counters had been contradicting themselves about for a dozen builds.

## Capturing the sound driver's port writes (2026-10-07)

`work/trace_sound_writes.py` turns the original's sound driver into a stream of register writes. Spec and results:
`analysis/functions/sound-driver.md`; records `#sound-driver-*` in `analysis/functions/browser-attract.md`; proof tool
`tools/check-js-sound.js`.

```bash
python3 work/trace_sound_writes.py direct --scenario openmus --out build/sound/openmus.json
python3 work/trace_sound_writes.py direct --scenario openmus-mpu --mpu --out build/sound/openmus-mpu.json
python3 work/trace_sound_writes.py natural --seconds 300 --out build/sound-natural/natural-attract.json
sh work/capture_sound_fixtures.sh                               # all of the direct captures (NATURAL=400 adds the natural run)
node tools/check-js-sound.js                                    # every capture in build/sound
node tools/check-js-sound.js --natural build/sound-natural/natural-attract.json
```

What made it work, and what bit:

- **A card the guest does not have.** QEMU's `-audiodev none,id=snd0 -device adlib,audiodev=snd0` is a YM3812 model, and the
  driver's own detection (`0002C1EA`: timer 1 started, status read back as `C0`) passes on it, so nothing is forced. QEMU has no
  MPU-401: its ready poll (`0002BF96`) would spin on 0xFF forever, so `--mpu` breaks at `0002BF88` and `0002BFD9`, logs `al`, and
  returns for the guest (`esp += 4`, `eip` = the return address; `0002BFD9` returns `FE`). No Sound Blaster is attached, so the
  game's own probe (`00004FBB`) fails and `[00019DF9]` is 0: effects take the FM path, which is what the capture wants.
- **Breakpoint at the port helper, not at the `out`.** `0002C1B8` takes register and value in `ah` and `al`; stopping at its entry
  gives both and the caller (`[esp]`) at the cost of one `Z0`. The two status reads of the detection are stopped on the instruction
  after each `in al, dx`, the PC speaker's `out`s before and its `in`s after, so every value the driver reads from or writes to a
  port is in the log.
- **Call the routines, do not wait for the game.** Like `dos_call.py`: stop as the replay arms (`00019A4E`), put the driver's
  data back to the image's bytes (`0002C48C-0002DC00`, and the mixer's records `000040E2-00004200`), then set registers and
  `eip` through the gdbstub and run to a breakpoint on a padding `nop` (`0002C48B`) that nothing reaches, with a return address
  pushed there. **`eflags` = 0x002 (interrupts off)**: the PIT would otherwise tick the music behind the probe's back, and a `tick`
  op is simply `call [0002C48C]`, which is what the ISR does at `00001D2C`. A whole song of 10,000 ticks takes about a minute.
- **A helper that returns with a register changed.** `0002C1B8`'s delay loops count AX down, so it returns with AX = 0. The caller at
  `0002BC28` reads AH afterwards, so the first effect that expired in the tick produced a pitch write the JavaScript did not. The
  difference showed up on the first capture that exercised it and nowhere else: every routine in the JavaScript passes its
  registers on, and a helper's clobbers are part of its contract.
- **Natural runs: connect early.** Connect the gdbstub before the program is resident (the start-up detection and device
  selection, `000055B4-000055D8`, happen in the first 2.5 s). Breakpoint addresses are linear addresses, so DOS's own real-mode
  code hits some of them while it boots; a stop at an address that is not one of ours is stepped over (`s`), never continued
  from, or the same stop repeats forever. Ignore stops until the signature at `00025880` is in memory.
- **An interrupt can land inside a driver call.** The natural capture shows ISR entries between the writes of one command (the PIT
  ISR calls the music tick while the game's main thread is inside `0002B9CF`). Reconstructing the interleaving takes the original's
  variables at the ISR's entry (read at every ISR and driver entry, 437 bytes) and a replay that interrupts the call before each
  store after the recorded write position until the variables are the original's.
- **Memory the PC does not have reads as 0x00.** The null second voice of a one-voice FM effect loads patch 255, whose envelope
  pointer comes from the relocated table at `0002D7F0` read through an out-of-table index (`0x61800004`); the effect's first half
  takes the same channel next, so only a tick that arrives between the halves (the natural run has them) reads through it. QEMU's 16 MB PC returns 0x00 there (measured by calling `mov al, [addr]` in the guest at six such addresses); the
  JavaScript does the same and counts the reads.
