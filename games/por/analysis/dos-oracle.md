# DOS dynamic oracle (DOSBox-X)

Purpose: observe what the game actually does to hardware, for the questions
static analysis narrows but cannot close. First target is the palette
(`PORTING.md` §Open risks 1).

**Status: harness works, question NOT settled.** The blocker is named in §3.

## 1. Harness

`img/oracle/` — rebuild with `make oracle-stage`, run with `make oracle`.

```
img/oracle/GAME/        all 257 expanded files, mounted as C:
img/oracle/DISK1,DISK2/ the original disk contents, for INSTALL.EXE
img/oracle/*.conf       DOSBox-X configurations
img/oracle/*.log        captured logs
```

Headless recipe:

```sh
timeout -k 5 45 env SDL_VIDEODRIVER=dummy \
    dosbox-x -conf io.conf -nogui -fastlaunch -silent
```

- `SDL_VIDEODRIVER=dummy` runs with no window. Required for automation.
- `-silent` exits after `[autoexec]`; `timeout -k` is still needed because a
  program that waits for a key never returns. **Plain `timeout` is not enough**
  — DOSBox-X survived `SIGTERM` in testing and needed `-k` (`SIGKILL`).

### Logging

The `[log]` section takes per-category levels, not just booleans:
`true, false, debug, normal, warn, error, fatal, never`. Categories include
`int10`, `io`, `vga`, `vgagfx`, `vgamisc`, `int21`, `fileio`, `exec`.

```ini
[log]
logfile = io.log
int10   = debug
io      = debug
vga     = debug
```

`int10` logging is confirmed working — it reports the two BIOS `Set Video Mode 3`
calls during boot, so an absence of further entries is a real absence, not a
misconfigured logger.

### Reading DOS console output

**The DOS screen is invisible under the dummy video driver.** Programs that
write through the BIOS or straight to video memory show nothing at all. The
workaround for anything that uses DOS output is to redirect to a file on the
mounted drive and read it from the host:

```
dir start.exe > c:\probe1.txt
```

That confirmed the mount and the file listing. It does **not** work for
`START.EXE` or `INSTALL.EXE`, which produced empty files — they do not print
through DOS.

## 2. What the oracle has established

With `GAME/` mounted as `C:` and `START.EXE` run:

| observation | value |
|---|---|
| `INT 10h` calls from the game | **0** (only the 2 BIOS boot `Set Video Mode 3`) |
| video port writes (`0x3Cx`) | **0** |
| `POOL.CFG` created | no |
| `START.EXE` stdout | empty |
| process behaviour | blocks until killed |

## 3. The blocker

`START.EXE` never reaches the game. It carries the strings `Unable to find
POOL.CFG`, `Please insert startup disk.` and `Please insert overlay disk.`, and
no `POOL.CFG` ships in the archives — `INSTALL.EXE` creates it. So the run above
almost certainly stops at a startup check and waits for a key.

**That means the zero counts above say nothing about the palette.** They are
consistent with "the game never programs one" and equally consistent with "the
game never got that far". Do not cite them as evidence either way.

`INSTALL.EXE` cannot be driven blind: it is interactive and also prints through
the BIOS, so under a dummy driver there is nothing to read and nothing to answer.
Redirecting a keystroke file into it does not help if it reads via `INT 16h`.

## 4. Next steps, in order of expected cost

1. **Recover the `POOL.CFG` format from the disassembly.** `START.EXE` opens and
   reads it; the read is in the resident code, which is disassembled
   (`work/start16.txt`) though only 21 % is emitted as instructions. Cheapest
   path if the file is small and simple — it plausibly just records the video
   mode (`DS:497E`, values 0/1/2 = CGA/EGA/Tandy) and a data path.

   **Attempt (2026-08-21, static, Windows machine) — stalled, documenting the
   dead end.** The message table lives at file `0x1d90` (linear `0x19ff`),
   five back-to-back Pascal `ShortString` constants: `GAME.OVR`, `pool.cfg`,
   `Please insert startup disk.`, `POOL.CFG`, `Unable to find POOL.CFG` —
   confirms the strings this doc already quotes exist exactly as cited.
   `work/start16.txt`'s recursive-descent walk desyncs right at this table
   (it decodes the ASCII bytes themselves as instructions, e.g. `47`='G' →
   `inc di`) and stays garbage well past it, so the listing is unusable in
   this stretch — a real tool limitation, not just missing coverage.

   Manually decoded the generic RTL instead (capstone, by hand, cross-checked
   against raw bytes): a `Reset`-equivalent @ linear `0x6B7B` (branches on the
   Borland file-mode magic words `0xD7B0/1/2/3` = fmClosed/fmInput/fmOutput/
   fmInOut, opens `FileRec.Name` at record+`0x30`), its buffered-read fill @
   `0x6BFD` (seek to end, seek back, read 128 B, scan for `0x1A` Ctrl-Z — a
   **text-file** reader, not a fixed binary record), and `BlockRead` @
   `0x6C57`. Separately, fully decoded the overlay manager's own
   open-with-retry cluster (`0x5728`-`0x58EF`, validates a `TPOV` header) and
   confirmed — by finding every near-call in the file that targets its low
   -level open primitive `0x5861` — that it has exactly 3 callers, all inside
   that same cluster: it's **GAME.OVR-only**, not POOL.CFG.

   Could not find the actual `Assign('pool.cfg')` call site. An exhaustive
   scan of all 47,936 bytes for every way x86 can load a 16-bit immediate
   (`mov reg,imm16` all 8 regs, `lea reg,[disp16]`, `push imm16`, `mov
   [mem],imm16`) found **zero** references to any of the five strings'
   addresses anywhere in the file. This matches a documented dead end one
   project over: `F030Underworld/analysis/ghidra.md` §"string-pool reference
   mechanism" — Ghidra's exhaustive xref scan of 111,801 `UW.EXE`
   instructions found 0 direct refs into its string pool either. This engine
   family appears to resolve filename/message strings indirectly (a table
   walk or a resource id) rather than through baked-in immediates, so
   pattern-matching raw bytes can't find the reference. Ghidra's fuller
   data-flow/xref analysis is the next thing to try (not yet run on
   `START.EXE`, unlike unit `18E`) — but the same analysis already stalled on
   the equivalent problem in `F030Underworld`, so it is not a sure win.

   Net result: the "video mode + data path" guess above is neither confirmed
   nor ruled out. One refinement earned from this pass: POOL.CFG is read
   through the **text-file** RTL path (buffered, stops at Ctrl-Z), not
   `BlockRead`, so if it does carry a video-mode byte, it's more likely a
   line of text than a raw byte record.

   **Follow-up (2026-08-21, Ghidra) — resolved.** Imported `START.EXE` into
   Ghidra 12.1.3 (experimental MZ loader + `x86:LE:16:Real Mode`, chosen by
   opinion, auto-analysis on): `analyzeHeadless work/ghidra POR16_START
   -import work/expanded/START.EXE`. Direct invocation works fine from this
   git-bash — the `.bat`-needs-`cmd` note above wasn't necessary here. Ghidra
   confirmed the dead end above wasn't a tooling artifact: its own
   `ReferenceManager` also finds **zero** direct refs to the string-table
   addresses. But unlike `work/start16.txt`, Ghidra's function-boundary
   analysis doesn't desync at the string table — it leaves the strings as
   plain data and decodes the surrounding code correctly, which is what
   actually cracked it: the code right after the table (Ghidra segment
   `11a0`, starting file `0x1db0`) decompiles cleanly, and its `Assign`-style
   calls resolve to **exact** file-offset matches — `0x1dde` (`'P'` of
   `POOL.CFG`, one byte past the Pascal length prefix: this RTL helper takes
   a bare char pointer, length passed separately) for the open, and `0x1de7`
   (start of `Unable to find POOL.CFG`) for the failure path. Decompiled
   `FUN_11a0_00a4`, translated back to source:

   ```pascal
   Assign(F, 'POOL.CFG'); Reset(F);
   if IOResult <> 0 then begin Write('Unable to find POOL.CFG'); Halt end;
   Read(F, ch1); ReadLn(F);
     { ch1='E' -> mode:=1(EGA); ch1='T' -> mode:=2(Tandy); else -> mode:=0(CGA) }
   Read(F, ch2); ReadLn(F);
     { ch2='T' -> sel:=0; ch2='P' -> sel:=1; else -> sel:=2 }   { meaning: TBD }
   ReadLn(F, path1);   { -> buffer DS:0x53da }
   ReadLn(F, path2);   { -> buffer DS:0x52d8 }
   Read(F, ch3); ReadLn(F);
     flag := (ch3 = 'F')
   Close(F);
   ```

   `mode` above writes the literal offset `0x497E` (`MOV byte ptr
   [0x497E],0x1/0x2/0x0` — confirmed in the raw instruction bytes, not just
   the decompiler's guess), matching this doc's and `executables.md`'s
   `DS:497E` exactly, letter-for-letter with the CGA/EGA/Tandy encoding
   already documented. So: **`POOL.CFG` is a 5-line text file** — two
   single-letter hardware selectors (line 1 = video adapter, confirmed;
   line 2 = unidentified, T/P/else), two string lines (plausibly the "data
   path" guessed above, though there are two of them, not one), and a third
   letter tested against `'F'`. Goes beyond the original guess in every
   dimension it touches. Line 2's selector and the line-5 `'F'` flag are the
   open pieces — the dynamic oracle (item 2 below) now knows exactly what
   shape of file to expect and can confirm the rest in one capture.

   Scripts added: `work/ghidra_scripts/PORStartLayout.java` (memory map +
   entry point), `PORStartRefs.java` (xrefs + raw code-units for a file
   range), `PORStartDecomp.java` (decompile the function containing a given
   file offset). File-offset↔address mapping for `START.EXE`: `seg = 0x1000
   + ((F-0x3b0)>>4), off = (F-0x3b0)&0xF` — cross-verified against the
   known-good entry point (`e_ip=6` → `1000:0006`) and the DGROUP base
   (`0x740` paragraphs → segment `0x1740`) from `executables.md`.
2. **Run with a real video driver and screenshots.** Drop `SDL_VIDEODRIVER=dummy`,
   let DOSBox-X render, and capture frames so `INSTALL.EXE` can be driven and its
   prompts read. Slower to automate but authentic, and it validates the
   `DISK<target><source>` manifest decoding as a side effect.
   The scripted form of this already exists: the family QEMU harness
   (masters in `../F030Method/dos/` — seed this project with
   `python ../F030Method/dos/sync.py --init F030POR`; workflow write-up:
   `../F030Underworld/analysis/qemu-boot.md`) boots genuine MS-DOS 6.22 headless,
   drives interactive programs with `sendkey`, reads their screens via QMP
   `screendump` / `pmemsave 0xB8000`, and reads guest-written files
   (`POOL.CFG`) back out with mtools. Adopting it covers this step without
   giving up automation; DOSBox-X remains the tool for step 3's `io`/`int10`
   log — the two harnesses answer different halves.

   **Update (2026-08-21, Windows machine):** the QEMU side of this step is
   fully present on the `C:\Arbeit` machine at exactly the paths
   `run_qemu.py` hardcodes (QEMU 11.1, mtools in `C:\msys64`, MS-DOS 6.22
   floppies in `../F030Underworld/img/`), and `work/expanded/` is rebuilt and
   CRC-verified — see `analysis/tools.md` §Windows machine. Step 1 (static
   `POOL.CFG` recovery from `work/start16.txt`) can start immediately; the
   disassembly listings were untracked generated files and need
   regenerating with `work/disasm.py`.
3. **Once the game runs**, re-run with `io = debug` and grep for `0x3C0`
   (Attribute Controller) and `INT 10h AH=10h`/`AH=0Bh`. That settles the
   palette in one run.

## 5. Machine profile

`machine=ega`, `memsize=4`, `cputype=386`, `core=normal`, no Sound Blaster, no
PC speaker. The game is 16-bit real mode and the shipped art is EGA
(4 bpp, 320×200), so EGA is the mode whose palette matters. 608 KB conventional
memory free after boot — far more than the game's `e_minalloc` requires.

## 6. POOL.CFG recovered from the real INSTALL.EXE (2026-08-21, macOS)

**Resolved.** `INSTALL.EXE` was driven to "Installation complete" under QEMU
and the `POOL.CFG` it wrote was read back with mtools. Three installs differing
only in the form settings pin every field by variation, not by inference:

| Display Type | Sound Type | Full Intro | `POOL.CFG` |
|---|---|---|---|
| EGA | PC Sound | No | `E␍␊P␍␊C:\POOLRAD\␍␊C:\POOLRAD\␍␊N␍␊` |
| CGA | Tandy Sound | Yes | `C␍␊T␍␊C:\POOLRAD\␍␊C:\POOLRAD\␍␊F␍␊` |
| Tandy 16 Color | Silent | No | `T␍␊S␍␊C:\POOLRAD\␍␊C:\POOLRAD\␍␊N␍␊` |

35 bytes in the EGA case. Five CRLF-terminated lines, no trailing NUL, no
header:

| Line | Meaning | Values observed |
|---|---|---|
| 1 | Display type | `C` = CGA, `E` = EGA, `T` = Tandy 16 Color |
| 2 | Sound type | `P` = PC Sound, `T` = Tandy Sound, `S` = Silent |
| 3 | Path, trailing backslash included | `C:\POOLRAD\` |
| 4 | Path, trailing backslash included | `C:\POOLRAD\` |
| 5 | Full intro | `F` = yes, `N` = no |

Line 5 confirms the static reading in §4 item 1 — the code tests that letter
against `'F'` — and lines 3/4 confirm that there really are **two** paths, not
one. Note `T` is line 1's Tandy *display* and line 2's Tandy *sound*: the
letter alone does not identify the field, only the line does.

**Still TBD: what distinguishes line 3 from line 4.** Every successful install
so far put the same directory in both, so nothing observed yet separates them.
Two attempts to separate them failed and are worth recording:

- **Save Disk = Make One** crashes the installer with `Divide overflow` (blank
  720 KB 3.5" image in B:). No `POOL.CFG` is written on that path.
- **Hard Disk = None** (floppy install): `work/drive_install.py --floppy` never
  leaves the settings form, so nothing was written. That is a limitation of the
  driver's key sequence, not a proven property of `INSTALL.EXE`.

Reading a stale file is the trap here: a crashed run leaves the *previous*
run's `POOL.CFG` in place and it reads back as a plausible result. Delete it
(`mdel -i img/por.hdd@@32256 ::/POOLRAD/POOL.CFG`) before every run.

### Driving it

`work/drive_install.py` replaces the fixed-time `work/probe_install2.py` for
this job: it polls the VGA text plane and answers each prompt as it appears,
which the timed schedule cannot do because PKUNPAK's extraction times are not
knowable in advance.

    python3 work/build_dos_hdd.py          # bare DOS 6.22, no game tree
    python3 work/set_boot_mode.py install  # AUTOEXEC -> A:\INSTALL.EXE
    python3 -u work/drive_install.py --display ega --sound pc

A full install takes ~18 s of emulated time. Two findings about the form, both
read off the screen rather than assumed:

- **The cursor position *is* the selection.** Nothing else marks it; a
  screenshot cannot be used to read back a setting on a row the cursor has
  left. The "Floppies Required" footer does recompute, so it is the one
  independent confirmation the screen offers.
- **Left clamps at the leftmost option**, so a row can be set without knowing
  where the cursor started: press Left past the end, then Right *n* times.

**"SSI MASTER DISK B" is not `disk2.img`.** The sleeve label does not say which
archive PKUNPAK wants. `disk1.img` carries `DISKA.ARC`, `DISKB.ARC` and
`SAVE.ARC`; `disk2.img` carries only `DISKC.ARC`. Swapping to `disk2.img` at
that prompt stalls the install indefinitely — it cost one 12-minute run. The
driver now presses a key with the disk already in the drive and only swaps if
the prompt fails to clear.

**The guest never sees `game/POR/*.img`.** Those are the tracked pristine
reference and QEMU attaches floppies read-write, so `drive_install.py` and
`probe_install2.py` both hand it scratch copies under `work/img_build/`.
Verified after this session's runs: both originals still byte-identical.

## 7. The game runs — and why the palette is still open (2026-08-21)

With `POOL.CFG` in place the §3 blocker is gone. `make oracle-hd` mounts
`img/oracle/HD/` (INSTALL.EXE's own output, extracted from `img/por.hdd`, so
the `C:\POOLRAD\` in `POOL.CFG` resolves) and runs `START.EXE`:

```
     3       INT10:Set Video Mode 3
     8       INT10:Set Video Mode 3
330021       INT10:Set Video Mode D
330021       VGA:Blinking 0
330021       VGA:320x200, 59.92Hz, 8bpp, screen 1.333, video clock 7.16MHz, mode M_EGA
```

**Established:** the game sets **INT 10h mode 0Dh** — EGA 320×200, 16 colours,
planar — which matches the shipped art (4 bpp, 320×200) and the `machine = ega`
profile in §5. Compare §2, where the oracle saw *zero* INT 10h calls because
`START.EXE` stopped at the missing config.

**Not established: the palette.** §4 item 3 says to "re-run with `io = debug`
and grep for `0x3C0`... That settles the palette in one run." **That plan does
not work on this build and should not be retried as written.** Two measured
reasons:

- `io = debug` emits exactly three lines, all at time 0, and all of them the
  emulator's own I/O *delay* settings (`I/O 8-bit delay 1020ns`, …). It is not
  a per-port trace, so **an empty `0x3C0` grep is not evidence of anything** —
  the same "a plausible absence is not a measurement" trap the cross-project
  ledger records for UW1's relocation table.
- DOSBox-X 2026.08.02 (macOS ARM) carries only `INT10`, `VGAGFX` and `VGAMISC`
  as VGA log channels — `strings` on the binary shows no `vgaattr` or `vgadac`.
  There is no channel that reports Attribute Controller or DAC writes, so no
  `[log]` configuration recovers them.

So whether the game reprograms the 16 EGA registers or just takes mode 0Dh's
BIOS default is **TBD** — and the default cannot be assumed, because assuming
it is exactly what would put an unsourced palette into the port. Routes not yet
tried, cheapest first:

1. **Static:** find the palette writer in `GAME.OVR`/`START.EXE` — an `INT 10h`
   `AH=10h` call or a `0x3C0` `out`. The disassembly is the authority anyway,
   and this needs no emulator.
2. **`work/gdbstub_probe.py`** against the QEMU oracle: break after mode 0Dh is
   set and read the Attribute Controller state directly.
3. DOSBox-X's interactive debugger, which can watch port writes even though the
   log channels cannot.

## 8. The palette: the game never programs it (2026-08-21)

§7 left the palette open and warned the `io = debug` route cannot settle it.
It was settled statically instead — route 1 of §7 — and the answer is negative:
**nothing in the program writes a palette.**

A byte-complete scan of both binaries (100 % of the files, so *absence* is
meaningful in a way a coverage-limited listing cannot be):

| Pattern | `START.EXE` | `GAME.OVR` |
|---|---|---|
| `int 10h` (`CD 10`) | **1** | **0** |
| `mov dx,0x3C0` (`BA C0 03`) — Attribute Controller | **0** | **0** |
| `mov dx,0x3C8` / `0x3C9` — DAC index/data | 0 / 0 | 0 / 0 |
| `mov ah,0x10` (`B4 10`) — BIOS set-palette | **0** | **0** |
| `mov ax,0x10xx` (`B8 xx 10`) | 3 (all Pascal constants) | 0 |
| `mov dx,0x3C4` — Sequencer | 1 | 3 |
| `mov dx,0x3CE` — Graphics Controller | 10 | 1 |

The one `int 10h` is the resident Turbo Pascal BIOS trampoline at `0x5728`
(`push si/di/bp/es; int 10h; pop; ret`), which `GAME.OVR` reaches by far call —
that is why a 232 KB overlay contains no `CD 10` of its own. Its 16 near
callers in `START.EXE` are all console work: `AH=0Fh` get mode, `AH=00h` set
mode, `AX=1112h`/`1130h` font, `AX=0100h` cursor, `AH=09h`/`0Eh` output,
`AX=0601h` scroll, `AH=12h` alternate select. **No `AH=10h`.**

The only VGA ports the game touches are `0x3C4/0x3C5` (Sequencer) and
`0x3CE/0x3CF` (Graphics Controller) — plane mask and write mode, i.e. planar
*rendering*. Neither register file can change a colour.

**Conclusion: the colours on screen are the BIOS default palette that
`INT 10h AH=00h` loads as part of the mode set.** For the Falcon port that
means the standard EGA 16-colour palette, and it is sourced, not assumed.

*Limits of this result.* A port number computed at runtime rather than loaded
as an immediate would evade the scan. The code's style is literal ports —
`0x3C4` and `0x3CE` are both immediates — so this is unlikely, but it is not
excluded, and self-modifying code is not excluded either.

### The mode number comes from POOL.CFG

Neither binary sets mode `0Dh` with an immediate: `mov ax,0x000D` and
`mov al,0x0D` do not occur, and every `mov ax,0xd` is a Pascal argument push.
The mode is loaded from a variable, and a controlled run says which one — the
same installed game, the same disk, only `POOL.CFG` line 1 changed:

| line 1 | INT 10h mode |
|---|---|
| `E` | **0Dh** — EGA 320×200 16-colour |
| `C` | **04h** — CGA 320×200 4-colour |

which is independent confirmation of §6's line-1 mapping. `T` (Tandy) is
untested — `hd.conf` runs `machine = ega`.

### Trap: INSTALL.EXE hits Turbo Pascal's Runtime error 200

`INSTALL.EXE` intermittently dies with `Runtime error 200 at 1B06:0815` and a
cascade of `Divide overflow`, *after* the copy phase and *before* it writes
`POOL.CFG`. That is the well-known Turbo Pascal CRT delay-calibration
divide-by-zero: QEMU runs the guest at host speed, so the calibration loop
overflows. It is intermittent, so it looks like a state-dependent bug in the
harness and is not one — it cost two misdiagnosed runs here.

Retrying is enough (it succeeded first try on the retry both times). A
deterministic fix would be to slow the CPU with QEMU `-icount`. **Always
`mdel` the old `POOL.CFG` first** — a crashed run leaves the previous one in
place and it reads back as a plausible result (§6).

## 9. POOL.CFG lines 3 and 4: data path and save path (2026-08-21)

§6 left this open: every successful install put the same directory in both, so
no sample separated them. Resolved by **use** instead of by value — the
decompiled parser (§4 item 1) reads line 3 into `DS:0x53DA` and line 4 into
`DS:0x52D8`, two distinct Pascal `ShortString` buffers, so the question is
which code reads which buffer.

Scanning all 232,379 bytes of `GAME.OVR` for the two addresses and mapping
each hit to its overlay unit (`work/overlay_map.json`) gives a **disjoint**
split — no unit touches both:

| Buffer | Units referencing it | Strings in those units |
|---|---|---|
| `0x53DA` (line 3) | seg `0x019`, `0x020`, `0x069` | `.dax`, `CPIC`, `PIC`, `Loading...Please` |
| `0x52D8` (line 4) | seg `0x0BE` **only** (16 refs) | `charlist.txt`, `.cha`, `.sav`, `.itm`, `.spc` |

Every hit decodes as a real operand — `mov di, 0x52d8` / `mov di, 0x53da`,
the ShortString pointer loaded before a filename is assembled — not as a
coincidental byte pair in data. (One extra at `0xeb4e` is
`mov byte ptr [0x53da],0`, clearing the string's length byte.)

**Line 3 is the game-data path** — where the `.DAX`/`.PIC` resources are read
from. **Line 4 is the character/save path** — where `charlist.txt` and the
`.CHA`/`.SAV`/`.ITM`/`.SPC` records live. A hard-disk install puts both in
`C:\POOLRAD\`, which is why every sample so far showed them equal.

*What this does not rest on:* no install configuration was found that makes the
two differ, so the separation is proven by the code that consumes them, not by
a differing sample. Two attempts to produce one failed:

- **Save Disk = Make One** does *not* relocate line 4 while Hard Disk = C:
  (re-run successfully after the §8 retry note — the earlier `Divide overflow`
  was Runtime error 200, not this option). It still writes `C:\POOLRAD\`.
- **Hard Disk = None** (floppy install) would be the case that separates them,
  but `drive_install.py --floppy` never leaves the settings form. That is a
  gap in the driver's key sequence, not a property of `INSTALL.EXE`.

For the port the practical consequence is that the two are **not**
interchangeable even though they are equal on disk: data is read through one
and saves written through the other, so a Falcon port wanting saves on a
different medium has exactly one of them to change.
