# Bootable DOS 6.22 image + headless QEMU oracle

**Status: RESOLVED (2026-08-20).** `img/uw.hdd` boots genuine MS-DOS 6.22 from a
FAT16 partition and runs `UW.EXE` under QEMU with no display; the intro cutscene
renders and screenshots come back over QMP.

This is the project's dynamic oracle: the thing that answers questions the static
disassembly cannot (tail load address, DS/pool base at runtime, main loop).

## Rebuild from scratch

```bash
python work/build_dos_hdd.py          # ~40 s: build, bootstrap-boot, arm EMS mode
python work/set_boot_mode.py uw       # switch what the image does on boot
python work/run_qemu.py --timeout 45  # run headless, screenshot on timeout
```

Inputs, all already in the repo:

| Input | Role |
|---|---|
| `img/Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)/Disk1.img` | IO.SYS, MSDOS.SYS, COMMAND.COM, **the genuine boot record (sector 0)**, EXPAND/DEBUG/FDISK/MSCDEX/… |
| `…/Disk2.img` | `HIMEM.SY_`, `SHARE.EX_`, `SMARTDRV.EX_` |
| `work/expanded/` | the 290 LZH-expanded game files → `C:\UW` |
| `work/mbr.asm` | MBR chain-loader source (assembled + diffed against the constant in `dosimg.py` on every build) |

Tools: mtools 4.0.49, nasm 3.02 (both `C:\msys64\mingw64\bin`), QEMU 11.1.0,
ffmpeg 9.0 (PPM→PNG for screenshots).

## Files

| File | Role |
|---|---|
| `work/dosimg.py` | the reusable builder (**identical copy in F030Underworld2 and TIE**) |
| `work/build_dos_hdd.py` | UW1 layout + memory config on top of `dosimg.py` |
| `work/set_boot_mode.py` | rewrite CONFIG.SYS/AUTOEXEC.BAT in place (<1 s vs ~20 s rebuild) |
| `work/run_qemu.py` | headless runner: deterministic exit, screenshot, guest-file readback |
| `work/gdbstub_probe.py` | runtime probe: register sampling, RAM↔file residency checks, `sendkey` driving (see below) |
| `work/mbr.asm` | MBR source |
| `img/uw.hdd` + `img/uw.hdd.geom.json` | the image and its geometry sidecar |

`img/dos622.hdd` is the **superseded** first attempt (8 MB, hand-built FAT/MBR,
never booted; still tracked in git). It can be deleted. `run_qemu.py` only
considers images that have a `.geom.json` sidecar precisely so a stray disk like
this cannot be picked up by accident — `dos622.hdd` sorts ahead of `uw.hdd` and
silently won a plain glob.

## Image layout

34 062 336 B (34.06 MB) raw, **66 cyl × 16 heads × 63 sect** (65 520 + 1008 sectors).
MBR at LBA 0; one active type-06 FAT16 partition at **LBA 63 … 65582**
(CHS 0/1/1 … 65/0/63), 16 339 clusters × 2048 B.

```
C:\ IO.SYS  MSDOS.SYS  COMMAND.COM  QUIT.COM  CONFIG.SYS  AUTOEXEC.BAT
C:\DOS\     EXPAND DEBUG FDISK FORMAT ATTRIB SYS CHKDSK MSCDEX
            + HIMEM.SYS EMM386.EXE MEM.EXE SHARE.EXE XCOPY.EXE SMARTDRV.EXE
C:\UW\      UW.EXE + DATA\ CRIT\ CUTS\ SOUND\   (290 files)
```

## The five rules that make it boot

Every one of these was a real failure first. They are asserted in
`dosimg.py::_install_boot_record`, so a violation fails the build, not the boot.

1. **A hard disk needs an MBR partition table.** A "superfloppy" image (FAT
   written at LBA 0, no partition table) boots nothing *and* DOS will not assign
   it a drive letter — `DIR C:` comes back empty. This is what had blocked the
   sibling TIE project.
2. **Use the genuine MS-DOS 6.22 boot record** (sector 0 of `Disk1.img`), keeping
   its code and replacing only the BPB at `0x0B..0x3D` with what mformat
   computed. mformat's own boot code hangs in QEMU.
3. **IO.SYS must be root entry 0 and MSDOS.SYS entry 1**, with IO.SYS's first
   3 sectors consecutive — so copy them before anything else, and never pass
   `mformat -v LABEL` (it spends entry 0 on a volume label; the label goes in the
   BPB instead). Verified from the boot record's own code, see below.
4. **BPB `hidden` (0x1C) = the partition's start LBA**, and total16/total32
   describe the *partition*, not the disk. The boot record adds `hidden` to every
   sector number it computes. (The earlier hand-rolled builder wrote
   `PART_SECTORS` into 0x1C, i.e. into `hidden` while believing it was `total32`.)
5. **The BPB's CHS must match what the emulator reports.** Geometry lives in
   `img/uw.hdd.geom.json`; `run_qemu.py` reads it. Never hardcode it — a stale
   `cyls=65` against a rebuilt 66-cylinder image made the guest hang for 12
   minutes with no output.

### Boot record disassembly (why rule 3 is exact)

`ndisasm -b 16 -o 0x7c00 -k 0,62` on `Disk1.img` sector 0:

```
7CC1  mov bx,0x500          ; load first root-dir sector to 0000:0500
7CD2  call 0x7d81           ;   AL=1 sector
7CD7  mov di,bx             ; entry 0
7CD9  mov cx,0xb
7CDC  mov si,0x7de6         ; -> "IO      SYSMSDOS   SYS"
7CDF  repe cmpsb            ; entry 0 must be IO.SYS
7CE1  jnz 0x7ced            ;   else "Non-System disk or disk error"
7CE3  lea di,[bx+0x20]      ; entry 1
7CE9  repe cmpsb            ; must be MSDOS.SYS
7D05  mov ax,[bx+0x1a]      ; IO.SYS first cluster
7D1A  mov bx,0x700          ; load to 0070:0000
7D1D  mov cx,0x3            ; exactly 3 sectors, read consecutively --
                            ; the FAT is never walked, hence "contiguous"
```

Root-dir LBA is computed as `hidden + resv + nfat*spf` (`0x7C84..0x7C97`), which
is where rule 4 bites.

### MBR

`work/mbr.asm`, 446 bytes, assembled with
`nasm -f bin work/mbr.asm -o work/img_build/mbr.bin`. Relocates itself
0000:7C00 → 0000:0600, scans the four partition entries for the active one,
reads its boot sector back to 0000:7C00 via **INT 13h AH=42h (LBA)** with an
**AH=02h CHS fallback**, then `jmp 0:0x7C00` with `DL` = drive and `DS:SI` = the
partition entry. The LBA path is what makes it geometry-proof; a CHS-only MBR
with baked-in 18/2 geometry failed against QEMU's 63/16 translation.

`dosimg.py` keeps the assembled bytes as a constant and re-assembles + diffs
`mbr.asm` on every build, so the two cannot drift.

## Headless observation

The Windows QEMU build has no working serial sink (confirmed again here — this
is why the TIE project accumulated 22 empty `serial*.log` files). Three channels
replace it:

1. **`C:\QUIT.COM` → isa-debug-exit.** 8 bytes: `mov dx,0F4h / mov al,0Ah /
   out dx,al / int 20h`. With `-device isa-debug-exit,iobase=0xf4,iosize=0x04`
   QEMU exits with code `(0x0A<<1)|1 = 21`, so the *guest* ends the run. Any
   other exit means it hung or crashed. The trailing `INT 20h` keeps the same
   .COM harmless on real hardware and in 86Box.
2. **Screenshots** via QMP `screendump` → PPM → PNG (ffmpeg). Works in graphics
   modes, which is what the game uses.
3. **Guest files**, read back with `mtype`. `AUTOEXEC.BAT` redirects everything
   into `C:\BOOT.LOG`. *Caveat (from TIE):* `mtype`/`mcat` on a **missing** file
   dump the raw image and look like content — always check the exit status.

A 4th channel, `pmemsave 0xB8000 4000` decoded as 80×25 CP437, is in
`run_qemu.py` for text-mode hangs.

## Probing the running game (`work/gdbstub_probe.py`)

```bash
python work/gdbstub_probe.py --wait 55 --samples 60 --key esc --key esc --key esc
python work/gdbstub_probe.py --wait 40 --chase 120     # hunt overlay code

# keyboard-only Create Character path, ending in live gameplay
python work/gdbstub_probe.py --wait 55 --samples 20 \
  --key esc --key esc --key esc \
  --key ret --key ret --key ret --key ret --key ret --key ret --key ret --key ret --key ret \
  --text codex --post-key ret --chase 80

# after entering the dungeon, F1 opens the command panel; its first item is Save Game
python work/gdbstub_probe.py --wait 55 --key esc --key esc --key esc \
  --key ret --key ret --key ret --key ret --key ret --key ret --key ret --key ret --key ret \
  --text codex --post-key ret --post-key f1

# on a temporary image, continue: Return (Save Game), Return (slot I), type a
# description, Return. The resulting SAVE1 directory is the persistent slot.
```

QEMU's raw **gdbstub was tried first and abandoned**: with `wait=off` it accepts
the connection but drops commands intermittently on this build. Everything is
done over QMP `human-monitor-command` instead — `info registers`, `xp`,
`screendump`, `sendkey` — with the CPU never stopped. Samples are therefore
racy, but the game spins, so repeated samples are representative.

What it produces, and the traps behind each (all of these were real failures):

- **`info registers` parsing.** QEMU prints `ES =1234 …` — with a *space* before
  the `=` — and the flags register is `EFL`, not `EFLAGS`. Splitting on
  whitespace and requiring `=` inside the token silently loses **every segment
  register**, reporting `CS=DS=ES=SS=0000`; every linear address computed from
  that is then wrong and looks merely odd rather than broken. Match with a regex
  that tolerates the space.
- **The guest runs in V86 mode** (`CR0=…11`, `CPL=3`, `DS16` descriptors) because
  `EMM386` is loaded. `linear = (seg<<4) + off` still holds.
- **Calibration by signature.** 8 candidate 16-byte signatures from the game
  exe are located by scanning RAM in 16 KB `xp` chunks (with 15-byte overlap,
  or a hit straddling a chunk boundary is missed). Majority vote, not
  unanimity: for UW1, 6 of 8 located signatures agree on `linear = file +
  0x2760`, load segment `0x0596`.
- **A 16-byte match proves 16 bytes.** Sampling the *whole* file (16 B every
  4 KB) against RAM is what revealed that UW1's 141 KB "tail" is not resident at
  all — it is a Borland `FBOV` overlay pool (`analysis/uwexe.md` §13.3). Expect
  ~70–75 % matches in the loaded image: the misses are applied relocations.
- **`sendkey` drives the game.** For UW1: 3× `esc` walks title → intro →
  main menu; the 4th `esc` quits to DOS, `AUTOEXEC.BAT` runs `QUIT.COM`, and
  QEMU exits 21. So **the monitor socket dying mid-probe is a normal outcome**,
  not an error — the probe treats a closed QMP connection as "guest exited".
- **Screenshots per step** (`work/qemu_out/probe_*.png`) are what let a register
  histogram be attributed to a known game state. Sample without a screenshot and
  you cannot say which state you measured.
- **Create Character is keyboard-drivable.** From the main menu, nine `ret`
  presses accept the default sex, handedness, class, attack/defense choice,
  weapon, skill, portrait, and difficulty screens; `--text NAME` fills the
  name field and presses Enter. A final `--post-key ret` accepts the character
  and reaches the live 3D dungeon. QEMU's HMP mouse move did not visibly move
  the cursor in the headless `-display none` setup, so this verified path does
  not depend on mouse input.
- The corresponding telemetry run is `work/trace/uw_char.trace` with RAM,
  overlay, and INT 21 sidecars. It reached 19.0% of the load-module code
  region and 19 overlay units; no save-related DOS activity occurred because
  no save command was reached. This is evidence about the driven run, not a
  binary-wide coverage claim.
- **The in-game command panel is `F1`.** Its first item is `SAVE GAME`. The
  earlier note calling this `F2` was a key-label error, corrected 2026-08-25
  from the rendered panel. On a temporary image, `F1 → ret → ret → codex →
  ret` created `UW\\SAVE1\\` and copied `LEV.ARK` (294,960 B), `BGLOBALS.DAT`
  (7,998 B), `PLAYER.DAT` (312 B), and `DESC` (5 B, ASCII `codex`); `SAVE0\\`
  held the same four files. The shorter `F1 → ret` flow independently
  produces the working `SAVE0\\LEV.ARK` and `BGLOBALS.DAT`. Use a temporary
  image for this probe because it writes the guest filesystem.
- **`taskkill` stray QEMUs first.** A probe that dies mid-run orphans its QEMU,
  which keeps the QMP port, and the next run fails with "Failed to find an
  available port".

## Memory configuration

UW1 is 16-bit real mode and probes for **EMS**, not XMS: `EMMXXXX0` occurs twice
in `UW.EXE` (file `0x03D974`, `0x05F3EE`) next to `EMS allocated` (`0x05FC28`),
`Out of Low Memory.$` (`0x0605F6`) and `Out of EMS Memory.$` (`0x06060A`).

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
ship **KWAJ-compressed** (`4B 57 41 4A 88 F0 27 D1`, method field `0x0003` =
LZ+Huffman). 7-Zip and mtools cannot read it. Rather than reimplement the codec,
the build copies the `.??_` files plus the genuine `EXPAND.EXE` onto the image
and boots it once with an AUTOEXEC that expands them in place, then swaps in the
real CONFIG.SYS. That first boot is automatic (`build_dos_hdd.py`); use
`set_boot_mode.py bootstrap` to redo it.

## Run modes (`work/set_boot_mode.py`)

| Mode | What the image does on boot |
|---|---|
| `stage1` | expand the KWAJ files with `EXPAND.EXE`, log, `QUIT.COM` |
| `ems` | HIMEM + EMM386 RAM, `MEM /C` into `C:\BOOT.LOG`, `QUIT.COM` |
| `uw` | `ems` + run `C:\UW\UW.EXE` (never returns — use `--timeout`) |
| `shell` | `ems`, then a `C:\UW>` prompt (for interactive use with a display) |

## QEMU invocation

```bash
qemu-system-i386 -M pc -cpu 486 -m 16 \
  -drive file=img/uw.hdd,format=raw,if=none,id=hd0,cache=writeback \
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
  as the destination. `-i` needs a Windows path (`C:\...`), not an MSYS `/c/...`.
- **`mformat -r` counts SECTORS, not entries.** `-r 512` gives 8192 root entries
  (256 KB of root directory); `-r 32` is the classic 512-entry root.
- **Partition entry offsets**: type is at `+4` (`0x1C2`), start LBA at `+8`
  (`0x1C6`), size at `+12` (`0x1CA`). An off-by-one here silently produces an
  unbootable table.
- **Python stdout is block-buffered when redirected** — run these scripts with
  `python -u`, or a hang produces an empty log and tells you nothing.
- No `-soundhw` in this build; no sound card is configured (see `AGENTS.md`).
- **Host helpers must go through `dosimg.host_tool()`.** `set_boot_mode.py`
  hardcoded `C:\msys64\mingw64\bin\mcopy.exe` and therefore failed the
  final step of `build_dos_hdd.py` on macOS (2026-08-23) *after* writing a
  perfectly good image — the traceback appears before the success lines in
  the log because stderr is unbuffered. Fixed.

## Execution telemetry (x86trace plugin)

The QEMU TCG plugin in `../F030Method/dos/trace/` answers the question a static
sweep cannot: *which bytes actually ran?* First UW1 run 2026-08-23 — numbers,
command lines and what they mean: `analysis/uwexe.md` §14. Notes from that run:

- `make` in `../F030Method/dos/trace/` builds `x86trace.so` against the host
  QEMU (11.1.0 here). `run_trace.py` finds the image geometry from the
  `.geom.json` sidecar exactly like `run_qemu.py`.
- **Quit through QMP.** The sidecar is written from the plugin's atexit
  callback; a killed QEMU produces no telemetry at all. `run_trace.py` does
  this, and schedules the RAM dump rather than deferring it to the end.
- **The plugin costs ~2–3× wall-clock.** UW1's front end that takes ~30 s bare
  needs ~60 s to reach the intro cutscene, so every `--key`/`--shot` time from
  a bare run has to be rescaled. Screenshot each step; do not assume the state.
- **The overlay window's flags are cleared on every flush**, so pick
  `--ovl-lo` at the end of the load module (UW1: `0x69290`, i.e. right above
  `SS:SP`) — a window that overlaps resident code would silently delete that
  code's coverage from the main sidecar.
- `--int21log` is the cheapest overlay oracle there is: UW1's overlay manager
  loads through ordinary `AH=3Fh` reads, so `LSEEK`+`READ` pairs give
  (pool offset, buffer, length) per unit with no reverse engineering at all.
  Caveat: it does **not** see `INT 67h`, and UW1 caches overlays in EMS.

## Cross-project

`work/dosimg.py`, `work/run_qemu.py` and `work/mbr.asm` are byte-identical in
`C:\Arbeit\F030Underworld2` (UW2, `img/uw2.hdd`) and `C:\Arbeit\F030TieFighter`
(TIE Fighter, `img/tie.hdd`); only `build_dos_hdd.py` and `set_boot_mode.py`
differ per game. The master copies live in `C:\Arbeit\F030Method\dos\` —
`python dos/sync.py` there checks every project copy, `--push` updates them;
see each project's `analysis/qemu-boot.md` for the per-game halves.
