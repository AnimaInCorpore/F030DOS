# Bootable DOS 6.22 image + headless QEMU oracle (UW2)

**Status: RESOLVED (2026-08-20).** `img/uw2.hdd` boots genuine MS-DOS 6.22 from a
FAT16 partition and runs `UW2.EXE` under QEMU with no display; the opening
"Dear Avatar, Greetings, my old friend!" cutscene renders and screenshots come
back over QMP.

## Rebuild from scratch

```bash
python work/build_dos_hdd.py           # ~40 s: build, bootstrap-boot, arm EMS mode
python work/set_boot_mode.py uw2       # switch what the image does on boot
python work/run_qemu.py --timeout 60   # run headless, screenshot on timeout
```

Inputs:

| Input | Role |
|---|---|
| `img/Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)/Disk1.img` | IO.SYS, MSDOS.SYS, COMMAND.COM, **the genuine boot record (sector 0)**, EXPAND/DEBUG/FDISK/MSCDEX/… |
| `…/Disk2.img` | `HIMEM.SY_`, `SHARE.EX_`, `SMARTDRV.EX_` |
| `work/extracted/D1..D5` | the LZH-expanded install disks → merged into `C:\UW2` |
| `work/mbr.asm` | MBR chain-loader source (re-assembled + diffed on every build) |

Tools: mtools 4.0.49, nasm 3.02, QEMU 11.1.0, ffmpeg 9.0 (PPM→PNG for
screenshots) — same versions via Homebrew on macOS and MSYS2 on the original
Windows machine. `dosimg.host_tool()` finds each one through `$<PROG>` (e.g.
`NASM=`), `$DOS_TOOLS`, `$PATH`, then the MSYS2 prefix, so nothing here is
Windows-only; see "Cross-project" below.

## Files

| File | Role |
|---|---|
| `work/dosimg.py` | the reusable builder — synced copy; **master in `C:\Arbeit\F030Method\dos\`** |
| `work/build_dos_hdd.py` | UW2 layout + memory config |
| `work/set_boot_mode.py` | rewrite CONFIG.SYS/AUTOEXEC.BAT in place (<1 s vs ~20 s rebuild) |
| `work/run_qemu.py` | headless runner: deterministic exit, screenshot, guest-file readback |
| `work/mouse_driver.asm` | minimal from-scratch INT 33h driver — see "A real mouse, from scratch" below |
| `img/uw2.hdd` + `img/uw2.hdd.geom.json` | the image and its geometry sidecar |

## Image layout

33.4 MB raw, **66 cyl × 16 heads × 63 sect**. MBR at LBA 0; one active type-06
FAT16 partition at **LBA 63 … 65582**, 16 339 clusters × 2048 B.

```
C:\ IO.SYS  MSDOS.SYS  COMMAND.COM  QUIT.COM  MOUSE33.COM  CONFIG.SYS  AUTOEXEC.BAT
C:\DOS\     EXPAND DEBUG FDISK FORMAT ATTRIB SYS CHKDSK MSCDEX
            + HIMEM.SYS EMM386.EXE MEM.EXE SHARE.EXE XCOPY.EXE SMARTDRV.EXE
C:\UW2\     UW2.EXE + DATA\ CRIT\ CUTS\ SOUND\   (305 files)
```

### The five install disks merge cleanly — RESOLVED

`work/extracted/D1..D5` hold the same four-directory layout the installer
produces. Merging all five yields **305 unique guest paths with zero
collisions** (verified by walking every tree and comparing full relative paths),
so `dosimg.add_tree('/UW2', D1..D5)` is a faithful stand-in for running
`INSTALL.EXE`. `UW2.EXE` is the only root-level file; it comes from D3. All 305
names are already 8.3-clean, so mcopy mangles nothing (the builder asserts this).

## The five rules that make it boot

Every one was a real failure first, and each is asserted in
`dosimg.py::_install_boot_record` so a violation fails the build, not the boot.

1. **A hard disk needs an MBR partition table.** A "superfloppy" image (FAT at
   LBA 0, no partition table) boots nothing *and* DOS will not assign it a drive
   letter — `DIR C:` comes back empty.
2. **Use the genuine MS-DOS 6.22 boot record** (sector 0 of `Disk1.img`), keeping
   its code and replacing only the BPB at `0x0B..0x3D` with mformat's. mformat's
   own boot code hangs in QEMU.
3. **IO.SYS must be root entry 0 and MSDOS.SYS entry 1**, with IO.SYS's first
   3 sectors consecutive — the boot record compares those two names literally at
   `0x7CD7`/`0x7CE3` and then reads 3 consecutive sectors to `0070:0000` without
   ever walking the FAT. So copy them first, and never pass `mformat -v LABEL`
   (it spends entry 0 on a volume label; the label goes in the BPB instead).
4. **BPB `hidden` (0x1C) = the partition's start LBA**; total16/total32 describe
   the *partition*, not the disk. The boot record computes the root-dir LBA as
   `hidden + resv + nfat*spf`.
5. **The BPB's CHS must match what the emulator reports.** Geometry lives in
   `img/uw2.hdd.geom.json`; `run_qemu.py` reads it. Never hardcode it — a stale
   cylinder count against a rebuilt image hangs the guest with no output.

The MBR (`work/mbr.asm`, 446 B) relocates 0000:7C00 → 0000:0600, finds the active
partition, reads its boot sector via **INT 13h AH=42h (LBA)** with an **AH=02h
CHS fallback**, then jumps with `DL` = drive and `DS:SI` = the partition entry.
The LBA path is what makes it geometry-proof.

## Headless observation

The Windows QEMU build has no working serial sink. Three channels replace it:

1. **`C:\QUIT.COM` → isa-debug-exit.** 8 bytes: `mov dx,0F4h / mov al,0Ah /
   out dx,al / int 20h`. With `-device isa-debug-exit,iobase=0xf4,iosize=0x04`
   QEMU exits with code `(0x0A<<1)|1 = 21`, so the *guest* ends the run; any
   other exit means it hung. The trailing `INT 20h` keeps it harmless elsewhere.
2. **Screenshots** via QMP `screendump` → PPM → PNG (ffmpeg) — works in the
   graphics modes the game uses.
3. **Guest files** read back with `mtype` (`AUTOEXEC.BAT` logs to `C:\BOOT.LOG`).
   *Caveat:* `mtype`/`mcat` on a **missing** file dump the raw image and look
   like content — always check the exit status.

## Probing the running game (`work/gdbstub_probe.py`)

```bash
python work/gdbstub_probe.py --wait 55 --samples 60 --key esc --key esc --key esc
```

Byte-identical copy of UW1's probe — self-discovers `img/uw2.hdd`,
`work/extracted/D3/UW2.EXE`, the `0xD200` Ghidra skew and the FBOV pool
straight from the MZ header, no UW2-specific edits needed. Two runs on
2026-08-21 (macOS):

- **File→linear calibration**: 6 of 7 signature windows agreed on
  `delta = 0x02B70` (this varies per boot — UW1 measured `0x2760`); this
  boot's load segment was `0x0597`, PSP `0x0587` (`load_seg = (delta +
  e_cparhdr*16) >> 4`).
- **Residency, now measured for UW2 instead of assumed by analogy**: image
  `69/111` 16-byte windows matched RAM (62%; misses are applied relocations —
  e.g. file `0x2E00`'s `68 1c 5f` reads back as `68 b3 64`, a patched segment
  immediate). FBOV tail: `1/52` matched (2%) — **the overlay pool is not
  resident**, same conclusion as UW1 (`F030Underworld/analysis/uwexe.md`
  §13.3), now confirmed on UW2's own bytes rather than inherited.
- **String-pool base register — RESOLVED, same answer as UW1**: there is no
  separate string pool, only DGROUP, addressed via `DS`. DGROUP's static file
  offset is `0x68E80` (above); at this boot's delta that predicts linear
  `0x68E80 + 0x02B70 = 0x6B9F0` = seg `6B9F:0000` — and `DS=6B9F` is exactly
  what every EIP sample recorded, across the intro cutscene, both menu-idle
  loops and the credits scroll (2 runs, ~30 samples, zero exceptions).
  UW1's finding (`uwexe.md` §13.1) transfers unchanged.
- **Game state map via `sendkey`**: boot → title (~55 s) → feast cutscene
  ("*The time has come to take pleasure...*") → castle/town exterior slide →
  3×`esc` → main menu (`Introduction` / `Create Character` /
  `Acknowledgements`, crosshair cursor parked on `Introduction`).
- **The main menu ignores keyboard navigation — new finding, not yet known
  for UW1 either.** `down` was a no-op (pixel-identical screenshot); `ret`
  and `c` both just activated whatever the cursor already sat on
  (`Introduction`), paging through the credits scroll (Paul Neurath → Warren
  Spector → Doug Church → "Creature Art" credits) instead of selecting a
  different entry. The menu is mouse-driven, so `sendkey` alone cannot reach
  **Create Character** — this is what blocks the `main`/game-loop hunt below,
  not a missing keystroke.
- **Timing is not inferred from the monitor.** The DOS image installs the
  recovered `INT 8` PIT scheduler documented in `analysis/ghidra.md` §17;
  its divisor and timer-slot periods are runtime values. Browser/Falcon game
  flow must preserve captured DOS tick/input/frame ordering. A 60 Hz display
  target or generic VGA refresh assumption is not evidence of the DOS game
  cadence, which remains `Unproven` until captured from a controlled run.
- **QMP `mouse_move` tried and root-caused — no working mouse path exists in
  this boot image, real or fake.** `mouse_move` (tested up to delta 300) and
  `mouse_button` produce **zero pixel change** — two screenshots straddling
  the call are byte-identical (confirmed by hash, not eyeball). `info mice`
  shows QEMU's virtual PS/2 mouse present and current, so the hardware side
  is fine; the gap is in the guest. Neither `work/extracted/D1..D5` nor the
  DOS 6.22 floppy set carries a real INT 33h driver (`MOUSE.COM`/`.SYS`) —
  searched, absent. The floppy set's `Suppdisk.img` does carry a
  `FAKEMOUS.COM` (307 B, 1994-05-31), which looked promising enough to
  disassemble in full (`ndisasm -b 16 -o 0x100`):
  it hooks **INT 15h**, and its handler (installed at `CS:0x103`) only acts
  on `AH=C2h` (the BIOS Pointing Device Interface) — for every subfunction it
  recognises (`AL=0,1,2,3,5,6,7`: enable, reset, sample rate, resolution,
  init, status, set-handler) it chains to the real BIOS handler and then
  unconditionally forces `clc` (success) before `iret`, regardless of what
  the real handler returned. **It fakes "yes, a cooperative pointing device
  is here" for detection purposes; it never synthesizes real position or
  button data.** The name is literal. It exists to silence installers that
  abort when `INT 15/AH=C2h` reports failure — not to provide a cursor.
  Loading it (tested, `work/img_build` scratch boot, not committed) changed
  nothing: it printed `Pointing device or this program previously installed`
  and exited without hooking anything, because QEMU/SeaBIOS already sets
  BIOS Data Area `0040:0010` bit 2 (the equipment-word "pointing device
  installed" flag) by default and `FAKEMOUS`'s own double-install guard
  (`mov al,[es:0x10] / test al,4 / jnz <exit>`) treats that as "already
  handled" — but this is moot, since even a fresh install would only fake
  BIOS-level success, not move a cursor. **Conclusion: this boot image has
  no software layer, real or fake, that could turn our injected PS/2 packets
  into whatever UW2.EXE reads.** Getting real mouse control would need a
  genuine INT 33h driver added to the image — not present in any asset this
  project currently owns, so sourcing one is a call for the user, not
  something to fetch autonomously.
- **Static analysis (2026-08-21) closes the question of whether a driver
  would even help** — it would, and nothing else could. Searched
  `work/ghidra_export/disasm.txt` (130K lines, the full 16-bit disassembly)
  exhaustively for every alternative mouse path:
  - **`INT 0x33` (mouse): exactly 3 call sites in the whole binary**, all
    inside one small routine, `CODE_388` (segment `3133`, file
    `0x3133×16=0x31330`). Before ever calling it, the routine defensively
    checks the interrupt-vector-table entry for vector `0x33` (`DI=0xCC`,
    i.e. `0x33×4`) against a sentinel — the standard cautious idiom for "is
    anything hooked here" — then: `AX=0`+`INT 33h`, result tested with
    `TEST AX,AX`/`JZ` (the textbook reset/detect call, `AX=0xFFFF` iff a
    driver answered); `AX=0xB`+`INT 33h` (**Read Motion Counters**); `AX=3`
    +`INT 33h` (**Get Mouse Position and Button Status**). Textbook,
    standards-compliant Microsoft Mouse Driver client code — nothing
    home-grown here.
  - **`INT 0x15` (BIOS): exactly 2 call sites, neither is `AH=C2h`.** Both
    are `AH=0x87`/`0x88` (Move Extended Memory Block / Get Extended Memory
    Size) — ordinary XMS-probing calls with nothing to do with pointing
    devices. `FAKEMOUS.COM`'s fakery targets an interface (`INT 15/AH=C2h`)
    UW2.EXE never calls, so it was never going to matter here regardless of
    its install-guard issue above.
  - **No custom IRQ12 handler is possible**: a slave-PIC EOI (`OUT 0xA0,AL`
    or `0xA1`) is mandatory for any IRQ8-15 handler, since IRQ12 cascades
    through the slave 8259 — and there are **zero** accesses to ports
    `0xA0`/`0xA1` anywhere in the entire binary (checked every `IN`/`OUT` on
    `0x60/0x64/0x20/0x21/0xa0/0xa1`). The sole `OUT 0x20,AL` (master-PIC EOI)
    sits inside an unrelated register-save-all, stack-switching ISR
    epilogue — shaped like the game's own timer tick handler, not mouse.
  - **Conclusion: UW2.EXE reads the mouse exclusively through the standard
    `INT 33h` software interface.** There is no raw-hardware fallback to
    find by looking harder — a genuine `INT 33h` driver loaded before
    `UW2.EXE` is both necessary and sufficient to unblock the menu.
- **`main` / the in-game loop: still TBD, but the blocker is gone.** Driving
  past Create Character no longer needs a sourced driver — see immediately
  below — so this is now a live probing target rather than something
  stalled on an external dependency. UW1 hits the identical wall
  (`uwexe.md` §13.7); once this is exercised further the fix is worth
  upstreaming to `F030Method` since it blocks all the sibling projects
  identically.

### A real mouse, from scratch — RESOLVED (2026-08-21)

No genuine `INT 33h` driver exists in any asset this project owns, and
fetching a third-party one isn't something to do unattended — so
`work/mouse_driver.asm` implements the three subfunctions UW2.EXE actually
calls (previous section) directly against the 8042 hardware, from public
protocol references: register contract from `stanislavs.org/helppc/int_33-
{0,3,b}.html`, 8042 command set from `stanislavs.org/helppc/8042.html`,
packet format from the University of Toronto's "PS/2 Mouse Interfacing"
reference. 120-odd lines of NASM, assembled by `build_dos_hdd.py` and staged
onto the image as `MOUSE33.COM`; loaded by `set_boot_mode.py`'s `uw2` and
`shell` modes right after the memory managers.

**Design: poll, don't interrupt.** Rather than hook IRQ12 (which needs the
slave-PIC EOI dance and correct PIC-mask handling to avoid ever wedging the
machine), the driver *polls* the 8042 output buffer directly whenever
UW2.EXE calls `AX=0/3/0Bh`: status port `0x64` bit 0 says a byte is waiting,
bit 5 says it came from the aux device rather than the keyboard — a byte
that isn't ours is left completely alone for the normal `IRQ1` path, so a
wrong assumption here could at worst leave the mouse inert, not break
keyboard input. Packets resync on byte 1's always-1 framing bit, so one
dropped byte can't permanently misalign the stream. X maps straight through;
Y is negated once (hardware `Y+` = away/up, screen `Y+` = down) — both
directions and the scale were verified visually, not assumed, per below.

**Verified working, live, end to end** — `MOUSE33.COM` loads by default now,
so any future `run_qemu.py`/`gdbstub_probe.py` run against `uw2`/`shell` mode
reproduces this without extra setup. From the untouched main
menu, `mouse_move 0 30` over QMP moved the crosshair from `Introduction` to
`Create Character` exactly one line, a second `mouse_move 0 30` continued on
to `Acknowledgements`, and `mouse_move 30 0` moved it right within a line —
both axes, correct direction, sane scale, no calibration hacks needed.
`mouse_button 1` then `mouse_button 0` on `Create Character` **entered
character creation** ("Choose character sex: Male / Female") — the first
time anything in this project has driven UW2 past its main menu. Keyboard
(`sendkey esc`) was re-checked immediately after and still works, so the
polling approach isn't silently eating keyboard bytes.

This establishes the DOS input contract, not permission for a port to shortcut
the flow: a browser, host or Falcon must feed the same `INT 33h` driver-visible
results to the recovered DOS consumer. The separate keyboard path must use the
recovered BIOS `INT 16h` contract; an unrecovered consumer or scan-code mapping
stays `Unproven`. Graphics and sound are the only broad mechanism exceptions.
See [`analysis/functions/input-drivers.md`](functions/input-drivers.md).

**Driving further probes**: `gdbstub_probe.py` has no mouse verb yet
(`--key` is keyboard-only) — everything below was done by using it as a
library against an already-running, already-navigated QEMU session
(`import gdbstub_probe as gp`, `gp.Qmp(port)`, then `qmp.hmp('mouse_move dx
dy')` / `'mouse_button 1'` directly), not a documented CLI flag. Worth
adding `--mouse dx,dy` / `--click` properly interleaved with `--key` if this
becomes routine. Also worth upstreaming `mouse_driver.asm` to `F030Method`
once it's seen more use here — UW1 and the other sibling DOS games likely
hit the identical missing-driver wall.

### Character creation, mapped end to end (2026-08-21)

Driven purely by `mouse_move`/`mouse_button` (plus keyboard for the name
field) from an already-booted session, no reboot between steps needed since
QMP accepts fresh connections against a still-running QEMU. Full linear
flow, one screen per choice, layout consistent enough that the cursor often
lands correctly on the next screen's default button without adjustment:

```
Main menu: Create Character
  -> Choose character sex: Male / Female
  -> Select handedness: Right / Left
  -> Pick a class: Fighter / Mage / Bard / Tinker / Druid / Paladin / Ranger / Shepherd
  -> Pick a skill (2 options, class-dependent — Mage: Mana / Casting)
  -> Choose a portrait (5 faces)
  -> Select difficulty: Standard / Easy
  -> Name: <text field, plain sendkey per letter, `ret` to confirm>
  -> Keep this character? Yes / No
  -> drops straight into the 3D game view
```

One click missed its target and landed on a neighbour (`Fighter` intended,
`Mage` selected) — not a bug, just the cursor sitting a few px outside a
button's rectangle after a coarse move; a follow-up small corrective move
before clicking fixed it every other time. Worth remembering when scripting
this again: verify cursor-vs-button-rectangle with a pixel ruler before
clicking rather than eyeballing, the same lesson as calibrating the driver
itself.

### First look at live 3D gameplay — EIP histogram

150 samples (~30 s) taken after reaching the in-game view (wooden starting
room, inventory panel, health orb, spell-gesture icons). Calibration
recalibrated fresh for this boot per the usual method — `delta 0x02F50` this
run (varies per boot, as always).

- **The segment-3133 mouse-reading block (identified in the static-analysis
  section above) is the single hottest code in the whole sample**:
  `FUN_3133_06e7` (32/150) and `FUN_3133_0703` (17/150) alone account for a
  third of all samples. Static analysis only proved *that* UW2.EXE reads the
  mouse via `INT 33h`; this is the dynamic confirmation that it does so
  **every frame**, i.e. this block sits directly inside whatever the
  in-game main loop is — its caller is the next thing to trace in Ghidra.
- **A strong, new lead for the video-blit routine**: one segment-register
  combination — `CS=065A DS=42E9 ES=A000 SS=3D01` — appeared in 11/150
  samples with `ES=0xA000`, the classic VGA framebuffer segment. Code
  running with the framebuffer loaded in ES is a direct, structural signal
  ("it's touching video memory"), not a name-based guess.
- **A strong lead for the renderer's own inner loop**: a second combination,
  `CS=2708 DS=66AD ES=66AD SS=66AD`, dominates the *segment* tally (58/150,
  39%) despite no single EIP address dominating within it — consistent with
  a loop that iterates over many small addresses (e.g. a column-by-column
  raycaster) inside one private working segment distinct from DGROUP
  (`6BDD` this run).
- `FUN_2c9a_0269` reappeared here (in-game) having also been a top hit at
  the *menu* in the very first probe session — a candidate for a low-level
  "yield" / "wait for timer tick" utility shared by both states, rather than
  anything game-loop-specific.
- Not yet resolved: which exact function *is* `main`/the game loop that
  calls the segment-3133 block every frame. The next step is static, not
  dynamic — trace inbound calls to `FUN_3133_06e7`/`FUN_3133_0703` and to
  the `CS=2708` block in `work/ghidra_export/disasm.txt` or the decompiled
  `uw_c.c`, now that dynamic sampling has narrowed the search from "the
  whole 660 KB binary" to a handful of named functions.

### Real breakpoints, not just sampling — QEMU's gdbstub, retried narrowly

The line above turned out to need more than static tracing alone could
finish — Ghidra loses the trail wherever a call is computed rather than
direct (`inrefs=0`, no call sites anywhere in `uw_c.c`). The fix was
dynamic after all, just not more sampling: QEMU's gdbstub, enabled *live* on
an already-running session over QMP (`human-monitor-command "gdbserver
tcp::1234"`, no relaunch needed) and driven with a ~100-line hand-rolled
Python RSP client rather than `gdb` (not installed here) or `lldb`. This is
a narrower use than what was tried once for UW1 and abandoned as flaky
(continuous register sampling) — set one breakpoint, stop once, read the
stack — and it worked cleanly on the first try and every try after. Full
technique, the validated call chain it produced, and where it led (a
threaded-code interpreter dispatch, not a flat loop) are in
`analysis/ghidra.md` §8 — that finding changes what "find `main`" even
means for this binary, so it belongs with the rest of the static analysis
rather than duplicated here.

**RSP stop-state lesson — 2026-08-25.** `work/rsp_break.py` intentionally
leaves QEMU stopped at the breakpoint after printing the registers. Closing
the RSP client and reconnecting to the same live QEMU can then return `T02`
while handling `Z0`; that is the existing gdbstub stop state, not evidence
that the newly requested address ran. A subsequent `c`/QMP `cont` can also
remain ambiguous when a previous breakpoint is still installed. For a new
oracle claim, either keep one RSP connection alive through the full
clear/set/continue/wait sequence or reboot the guest before re-arming. The
2026-08-25 inventory probe used a fresh reboot and a single connected RSP
sequence; its `BX=0x0A` results are therefore not inferred from a stale stop.

## Memory configuration

UW2, like UW1, is 16-bit real mode and probes for **EMS**, not XMS: `EMMXXXX0`
appears in `UW2.EXE` alongside `Out of EMS Memory.$` and `Out of Low Memory.$`.

```
DEVICE=C:\DOS\HIMEM.SYS
DEVICE=C:\DOS\EMM386.EXE RAM
DOS=HIGH,UMB
FILES=30
BUFFERS=20
```

gives **618 KB largest executable** + **14 928 KB free EMS** (`MEM /C`, verified).

### KWAJ bootstrap

`HIMEM.SY_`, `EMM386.EX_`, `MEM.EX_`, `SHARE.EX_`, `XCOPY.EX_`, `SMARTDRV.EX_`
ship **KWAJ-compressed** (`4B 57 41 4A 88 F0 27 D1`, method `0x0003` =
LZ+Huffman), which 7-Zip and mtools cannot read. Instead of reimplementing the
codec, the build puts the `.??_` files plus the genuine `EXPAND.EXE` on the image
and boots it once to expand them in place, then swaps in the real CONFIG.SYS.
That first boot is automatic; `set_boot_mode.py bootstrap` redoes it.

## Run modes (`work/set_boot_mode.py`)

| Mode | What the image does on boot |
|---|---|
| `bootstrap` | expand the KWAJ files with `EXPAND.EXE`, log, `QUIT.COM` |
| `ems` | HIMEM + EMM386 RAM, `MEM /C` + `DIR C:\UW2` into `C:\BOOT.LOG`, `QUIT.COM` |
| `uw2` | `ems` + run `C:\UW2\UW2.EXE` (never returns — use `--timeout`) |
| `shell` | `ems`, then a `C:\UW2>` prompt (interactive use with a display) |

## QEMU invocation

```bash
qemu-system-i386 -M pc -cpu 486 -m 16 \
  -drive file=img/uw2.hdd,format=raw,if=none,id=hd0,cache=writeback \
  -device ide-hd,drive=hd0,bus=ide.0,unit=0,cyls=66,heads=16,secs=63 \
  -boot c -display none -vga std -no-reboot \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -qmp tcp:127.0.0.1:4555,server=on,wait=off
```

**QEMU ≥ 6 rejects `cyls=`/`heads=`/`secs=` on `-drive`** ("Block format 'raw'
does not support the option 'cyls'") — CHS geometry belongs on the *device*.

## Gotchas

- **mtools + Windows paths**: a trailing `C:\...` destination is parsed as a
  *drive letter* → `Drive 'C:' not supported`. Run mcopy with `cwd=` set and `.`
  as the destination. `-i` needs a Windows path, not an MSYS `/c/...` one.
- **`mformat -r` counts SECTORS, not entries** — `-r 32` = 512 root entries.
- **Partition entry offsets**: type at `+4` (`0x1C2`), start LBA at `+8`
  (`0x1C6`), size at `+12` (`0x1CA`).
- **Python stdout is block-buffered when redirected** — use `python -u`, or a
  hang gives you an empty log.
- No `-soundhw` in this QEMU build; no sound card is configured.

## Cross-project

`work/dosimg.py`, `work/run_qemu.py`, `work/mbr.asm` and `work/gdbstub_probe.py`
are byte-identical in `C:\Arbeit\F030Underworld` (UW1, `img/uw.hdd`),
`C:\Arbeit\F030TieFighter` (TIE Fighter, `img/tie.hdd`) and `C:\Arbeit\F030F29` (F29, in
`tools/dos/`); only `build_dos_hdd.py` and `set_boot_mode.py` differ per game.
The master copies live in `C:\Arbeit\F030Method\dos\` — `python dos/sync.py`
there checks every project copy, `--push` updates them.

**Verified end to end on macOS from a clean tree** (2026-08-21): the synced
files already resolved their host tools portably; `set_boot_mode.py` still had
a hardcoded `C:\msys64\mingw64\bin` + `mcopy.exe` (it isn't synced — it differs
per game) and needed the same `dosimg.host_tool('mcopy')` swap. With that,
`build_dos_hdd.py` → `set_boot_mode.py uw2` → `run_qemu.py --timeout 60`
produced the identical result documented above: MBR verified against a fresh
nasm build, all 305 files merged with zero collisions, KWAJ bootstrap expanded
cleanly, and the Lord British feast cutscene rendered in the timeout
screenshot. The `CR0=80000011`/TSS/LDT registers `--timeout`'s register dump
shows mid-game are EMM386's V86-mode monitor, not a fault — expected once
`ems`/`uw2` mode loads `EMM386.EXE RAM`. UW1's
`analysis/qemu-boot.md` is the canonical copy of this document and carries the
boot-record disassembly in full.

**`work/gdbstub_probe.py` reads the *running* game** — register sampling,
RAM↔file residency checks, EIP histograms symbolicated against
`ghidra_export/functions.txt`, and `sendkey` to drive the game. It needs no
per-game adaptation: on this project it already resolves `img/uw2.hdd`,
`work/extracted/D3/UW2.EXE`, a Ghidra skew of `0xD200` and the `FBOV` overlay
pool at `0x71B80` by itself (verified). It is QMP-based on purpose — QEMU's
gdbstub drops commands on this Windows build. Method and traps: UW1's
`analysis/qemu-boot.md` §"Probing the running game". What it already overturned
for both UW titles: `analysis/cross-project.md` §1 and §6.

## Two harness gotchas worth keeping (2026-08-22)

- **A click must be held ~1.5 s.** `mouse_button 1` / `mouse_button 0` with a
  0.25 s hold registers *nothing* — UW2 samples `INT 33h AX=3` rarely enough
  to miss it. `work/drive.py` holds 1.5 s by default. The 2026-08-21 notes
  above say clicking works but do not mention the hold, which cost several
  silent no-op clicks before it was spotted.
- **Relative mouse units are 1:1 with screendump pixels** in the 640x400 dump,
  so buttons can be aimed by measuring a screenshot rather than by trial.
  This does not redefine the absolute `INT 33h` driver position limits in
  `work/mouse_driver.asm`; capture geometry and driver units remain separate
  until the choice consumer's coordinate conversion is recovered.
- **Background shell commands start in the repo root, not the persisted
  working directory.** A backgrounded `python3 work/drive.py start` silently
  did nothing because it resolved against the wrong path; always `cd` or use
  absolute paths in a backgrounded step.

### The asset archives are not in conventional memory

Hunting a `.GR` record signature through guest RAM during gameplay found
**nothing in `0..0x110000`**, and the EMS page-frame region holds no asset
data. The archives live in EMS-backed extended memory above 1 MB. Any future
"find this buffer in RAM" probe has to account for that — `gdbstub_probe.py`
and `rsp_break.py` both scan conventional memory only.
