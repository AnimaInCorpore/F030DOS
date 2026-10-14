# QEMU headless boot & diagnostics — MS-DOS 6.22 + TIE CD

Goal: a booting MS-DOS 6.22 that runs the game, observable without a display.
Emulator: **QEMU 11.1.0 (Windows build)** at `C:\Program Files\Qemu\qemu-system-i386.exe`.
Debug: **MSYS2 gdb 17.2** via `-s` (GDB stub on `:1234`).

## Status board

| Thing | Verdict |
|---|---|
| Bootable `C:` hard disk (`img/tie.hdd`) | **RESOLVED 2026-08-20** — boots genuine DOS 6.22, `C:\TIECD` fully populated, 170 MB free |
| Guest-driven headless exit (`QUIT.COM`) | **WORKS** — QEMU exit code 21 |
| Screenshots via QMP `screendump` | **WORKS** — PPM → PNG |
| Full launcher chain TIE.EXE → Z_TIE2__ → DOS4GW → Z_TIE__ | **WORKS** — verified stage by stage |
| DOS/32A as a DOS4GW replacement (P3.3) | **RESOLVED 2026-08-21** — `C:\DOS\DOS32A.EXE Z_TIE__.EXE /trebla /320` (`work/set_boot_mode.py dos32a`) reaches the identical `ERROR #3` text; `analysis/extender-eval.md` §Verdict |
| The game actually starting | **BLOCKED** — `Z_TIE__.EXE`'s own CD check (ERROR #3); needs a CD-ROM drive letter (see below) |
| Static xrefs into the 32-bit image | **RESOLVED 2026-08-21** — the fixup table itself is the xref index (`work/audit_fixups.py --target=OBJ:OFF`); the CD-check string has one source site, file 0x3DAC3 / linear 0x102C3 |
| Floppy `A:` boot (genuine DOS 6.22) | WORKS — SeaBIOS + 2 genuine 486 BIOSes |
| AUTOEXEC.BAT batches writing files | WORKS — reliable headless observation |
| QEMU `-soundhw sb16` | NOT SUPPORTED ("invalid option"). **Decision: no sound in the first implementation** |
| QEMU serial sink (`-serial file:` / `-chardev file`) | **NO-OP** — file stays 0 bytes (hence the 22 empty `img/serial*.log`) |
| mformat boot sector | **HANGS** in QEMU — use the genuine DOS sector |
| mtools `mtype`/`mcat` on missing file | **DUMPS RAW IMAGE** (misleading) — check the exit status |
| GDB 16-bit real-mode disasm | **MIS-DECODES** as x86-64 |

## The `C:` problem — RESOLVED

**Old symptom:** `DIR C:` printed nothing from the `A:` prompt under SeaBIOS,
`phoenix_winpro486e_103` and `award_sis486g_fullyes`. Because three BIOSes
agreed, the fault was correctly located in DOS rather than the BIOS — but the
suspected causes (CHS truncation, `AH=48` vs `AH=8`) were wrong.

**Actual cause:** `img/tie-dos.img` was a **superfloppy** — an mformat FAT16
volume written at LBA 0 with *no MBR partition table* — and its patched BPB had
`rootent=0` and a `total32` (1 048 576) larger than the drive's CHS-derived size
(1 032 192). DOS assigns drive letters to *partitions*, enumerated from the MBR
partition table; a partitionless fixed disk gets no letter at all, which is
exactly the empty `DIR C:`.

**Fix:** `img/tie.hdd`, built by `work/build_dos_hdd.py` + `work/dosimg.py`:
MBR partition table at LBA 0, one active type-06 FAT16 partition at LBA 63, the
genuine DOS 6.22 boot record with a correct BPB. `img/tie-dos.img` and
`tie-dos.img.bak` are superseded and can be deleted.

## Rebuild from scratch

```bash
python work/build_dos_hdd.py            # ~3 min: build, bootstrap-boot, arm dos4gw mode
python work/set_boot_mode.py tie        # switch what the image does on boot
python work/run_qemu.py --timeout 120   # run headless, screenshot on timeout
python work/bin2iso.py                  # one-off: SWTIECD.BIN (MODE1/2352) -> .iso
```

| Input | Role |
|---|---|
| `img/Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)/Disk1.img` | IO.SYS, MSDOS.SYS, COMMAND.COM, **the genuine boot record (sector 0)**, EXPAND/DEBUG/FDISK/MSCDEX/… |
| `…/Disk2.img` | `HIMEM.SY_`, `SHARE.EX_`, `SMARTDRV.EX_` |
| `game/SWTieCD/TIECD/` | the 391-file game tree → `C:\TIECD` |
| `game/SWTieCD/TIE.CD` | 8-byte marker → `C:\TIE.CD` (see below) |
| `work/mbr.asm` | MBR chain-loader source (re-assembled + diffed on every build) |

Tools: mtools 4.0.49, nasm 3.02 (`C:\msys64\mingw64\bin`), QEMU 11.1.0, ffmpeg 9.0.

## `img/tie.hdd` layout

268.9 MB raw, **521 cyl × 16 heads × 63 sect**. MBR at LBA 0; one active type-06
FAT16 partition at **LBA 63 … 524222** (CHS 0/1/1 … 520/0/63), 32 741 clusters ×
8192 B. Geometry sidecar: `img/tie.hdd.geom.json` (read by `run_qemu.py` —
never hardcode geometry).

```
C:\ IO.SYS  MSDOS.SYS  COMMAND.COM  QUIT.COM  CONFIG.SYS  AUTOEXEC.BAT  TIE.CD
C:\DOS\     EXPAND DEBUG FDISK FORMAT ATTRIB SYS CHKDSK MSCDEX
            + HIMEM.SYS EMM386.EXE MEM.EXE SHARE.EXE XCOPY.EXE SMARTDRV.EXE
C:\TIECD\   391 files, incl. ASTREAM\ CP320\ CP640\ MISSION\ RES320\ RES640\
            RESOURCE\ MT32\ SB16\ SC55\           (~95 MB; 170 MB free)
```

### `C:\TIE.CD` — how the launcher finds the game

`TIE.EXE` contains the literal string **`c:\tie.cd`**. The file is 8 bytes,
`43 3A 5C 54 49 45 43 44` = `C:\TIECD` (no terminator), and on the CD it sits at
the **root**, one level *above* `TIECD\` — i.e. `game/SWTieCD/TIE.CD`, not
`game/SWTieCD/TIECD/`. The real installer copies it to `C:\`.

Without it `TIE.EXE` runs the **CD installer** (`Z_INST__.EXE`, "TIE Fighter CD
Installer V1.0") instead of the game — verified by screenshot on this image's
first run. Correcting AGENTS.md's earlier note: `TIE.CD` is *not* part of the
`TIECD/` tree.

## Remaining blocker: the CD-ROM drive

With `C:\TIE.CD` in place, `TIE.EXE` gets past the installer and into its own
launcher, then stops:

```
Loading TIE-Fighter CD.  Please wait....
ERROR #3:  You must insert TIE-Fighter CD into your cd-rom drive.
If the CD is already in the drive and you still get this error, then check to
make sure that your cd-rom drivers are loaded. …
```

### Where the check lives — IDENTIFIED (2026-08-20)

The message is **not** in `TIE.EXE`, `Z_TIE2__.EXE`, `TIEAUTO.EXE` or
`DETVESA.EXE` — a tree-wide grep puts `ERROR #` and `You must insert` **only in
`Z_TIE__.EXE`**, i.e. in the game itself. Running the chain stage by stage from
AUTOEXEC confirms it (guest `C:\CHAIN.LOG`):

| Step | Command | Result |
|---|---|---|
| 1 | `Z_TIE2__.EXE` (no `/trebla`) | `You must run TIE.EXE for TIE-Fighter CD` — the guard fires, as documented |
| 2 | `DOS4GW.EXE Z_TIE__.EXE /trebla /320` | **`ERROR #3` directly** |
| 3 | `TYPE C:\TIE.CD` | `C:\TIECD` — marker present and readable |

So **the whole boot/launcher chain works end to end**: DOS boots, `C:` is
recognised, `TIE.EXE` finds `c:\tie.cd`, `Z_TIE2__` clears its `/trebla` guard,
DOS4GW loads the 1 031 495-byte 32-bit image — and *then* the game's own CD
detection fails. Nothing before the game is at fault.

Message strings (file / `img+` / linear, using §Address mapping):

| String | file | img+ |
|---|---|---|
| `ERROR #%d:  ` | `0x0E883E` | `0x0A983E` |
| `Some files may be missing or damaged.` (error #1?) | `0x0E884B` | `0x0A984B` |
| `You must insert TIE-Fighter CD…` (error #3) | `0x0E88BF` | `0x0A98BF` |
| `You do not have enough memory…` | `0x0E8A92` | `0x0A9A92` |

They form a NUL-terminated pool right after `/320`, `/trebla`, `.TFR`, `cls`,
`You must run TIE.EXE for the game.\n`.

### What the check is — RESOLVED 2026-08-21 (static trace, `work/disas_at.py`)

✗ **Withdrawn: "not the standard MSCDEX drive-list call."** The old note read:
*"The 32-bit image contains no `mov eax,1500h` / `mov ax,1500h` (nor `150Bh`,
`4409h`, `440Dh`) anywhere."* That search only looked for a 16-bit immediate
load. The real code builds `AX` **one byte at a time** into a DPMI real-mode
register block (`mov ah,0x15` / `mov dl,0x0b` / two separate `mov byte ptr
[esp+N], reg8`, never `mov ax,0x150B`) — invisible to an immediate-value grep.
It **is** MSCDEX, confirmed by full trace: the routine at file 0x3DAC3 (traced
back to its caller, the `main`-shaped function at file 0x3D810) calls
`file:0xB6C48("\astream\a.wrk")`, which (1) probes `INT 2Fh AX=150Bh`
"MSCDEX Drive Check" on drive D: via `file:0xB6D6C`, checking the documented
`BX=ADADh` signature, (2) calls `INT 2Fh AX=1500h` "MSCDEX Installation
Check" via `file:0xB6D20` to get the CD-ROM drive count + first letter, then
(3) **loops those drive letters trying to open `\ASTREAM\A.WRK` on each one**
— first success wins, exhausting the range fails. Both `INT 2Fh` calls go
through DPMI `INT 31h AX=0300h` ("Simulate Real Mode Interrupt", file
0xBD80D). Full byte-level trace: `analysis/ztie.md` §7 item 10.

**Practical upshot: the driver route is the confirmed answer**, not one of
two options — MSCDEX must actually report a CD-ROM drive (`AX=1500h` →
nonzero count) with `\ASTREAM\A.WRK` reachable there. The one thing that
would have avoided needing a driver — a global flag (file-data `0x13548`)
that skips this whole probe when nonzero — is a **closed dead end (verified
2026-08-21)**: every write to it is inside `main`'s argv loop and every path
through that loop nets it to 0; the other 12 references anywhere in the 1 MB
image are all reads (`ztie.md` §7 item 10, full site-by-site classification).
No command line or code path leaves it nonzero.

- **Not a missing game file** *on the hard-disk install*. `C:\TIECD\ASTREAM\
  A.WRK` (2 935 770 B) is on the image, verified with `mdir` — irrelevant to
  this check anyway, since it probes MSCDEX drive letters directly, never
  `C:\TIECD`.
- **Not `CDROM.CFG`.** LucasArts' own `SUPPORT\INSTALL.BAT` *erases*
  `cdrom.cfg` for a hard-disk install, so it was deleted from the image and
  retested — identical `ERROR #3`. (Restored afterwards so the image matches
  the pristine `game/` tree.) Consistent with the trace: the routine never
  reads that file.

### Why static xrefs did not resolve it — and how they now do (2026-08-21)

No reference to any of those strings exists in the file as a 32-bit immediate
**or** as a 24-bit image-relative value, under any of the bases tried (0,
`0x7E000`, `0x10000`, `0x3F000`, `0x1000`, `0x8000`, `0x400000`). The
diagnosis was right: the raw file holds unrelocated object-relative operands,
patched at load time from the **LE fixup records**. The fixup-aware pass now
exists — `python work/audit_fixups.py --target=OBJ:OFF` decodes all 27,438
records into a reverse-xref index. Worked result: the CD-insert string is
obj2+0xBF (file 0xE88BF), and its **single** source site is file `0x3DAC3` /
linear `0x102C3`, raw dword `BF 00 00 00` in the file. The CD check is
localised to an instruction; naming its routine is P1.3 work.

### Install semantics, from the CD itself — verified

`SUPPORT\INSTALL.BAT` on the disc is LucasArts' manual hard-disk installer and
settles what the marker files mean:

```
mkdir %1\tiecd
copy tie.cd %1\                       <- C:\TIE.CD, exactly as this image does it
copy *.exe *.fnt *.dat *.pac *.tfr read.me %1\tiecd
erase %1\tiecd\cdrom.cfg
copy instrec.cfg %1\tiecd\install.cfg  <- "1" = recommended
copy resource\ mission\ cp320\ cp640\ res320\ res640\ ...
imuse.exe
```

**`ASTREAM\` is never copied** — it is meant to stay on the CD. `INSTREC.CFG`=`1`
(recommended), `INSTMAX.CFG`=`2` (maximum); `game/SWTieCD/TIECD/INSTALL.CFG`=`2`,
so the repo's copy is a **Maximum install**, not a raw CD dump (which is also why
it has `RUN.BAT`, `MT32/`, `SB16/`, `SC55/` and `CDROM.CFG` — none of those exist
on the disc). The disc's own `SUPPORT\TIE.CD` is 11 B (`c:\tiecd\r\n\x1a`); the
8-byte `game/SWTieCD/TIE.CD` (`C:\TIECD`, no terminator) is the installed form.
The disc holds **1 727 files / 540 MB** vs the installed copy's 391 / 95 MB.

Two of the three pieces needed to satisfy the check are ready:

- **The disc.** `game/SWTieCD/cd/SWTIECD.BIN` is raw **MODE1/2352**
  (623 837 424 B = 265 237 × 2352 exactly, per the `.cue`), which QEMU cannot
  mount. `work/bin2iso.py` extracts bytes `[16:2064]` of every sector into
  `game/SWTieCD/cd/SWTIECD.iso` (543 205 376 B, ISO9660 PVD magic `CD001`
  verified at sector 16). Attach with `run_qemu.py --cdrom <iso>` (adds
  `-device ide-cd,bus=ide.1`).
- **MSCDEX.** `MSCDEX.EXE` (25 361 B, DOS 6.22 Disk1) is installed at
  `C:\DOS\MSCDEX.EXE`.
- **Missing: a DOS ATAPI CD-ROM device driver.** MS-DOS 6.22 never shipped one —
  MSCDEX is only the redirector and will not assign a letter until a vendor
  driver has registered a unit from CONFIG.SYS. Nothing suitable
  (`OAKCDROM.SYS`, `VIDE-CDD.SYS`, `ATAPICD.SYS`, …) exists anywhere in this
  workspace or under `C:\Users\sasch\Tools`.

Once a driver is available the config is:

```
DEVICE=C:\DOS\<atapi-driver>.SYS /D:MSCD001
...
C:\DOS\MSCDEX.EXE /D:MSCD001 /L:D
```

and `C:\TIE.CD` is **not** involved in this particular check — RESOLVED, see
below: the CD is located purely via MSCDEX drive letters, never a config file.

**Route forward** (both parts now resolved, 2026-08-21):

1. *Driver route — confirmed necessary.* Obtain a DOS ATAPI driver, mount
   `SWTIECD.iso`, load `MSCDEX.EXE` so `AX=1500h` reports a real drive with
   `\ASTREAM\A.WRK` on it. See §"What the check is" above.
2. *Static route — done, dead end.* The fixup index (`work/audit_fixups.py
   --target=2:0xBF`) pinned the CD check to file 0x3DAC3 / linear 0x102C3;
   `work/disas_at.py` traced the routine end to end and closed out the one
   candidate shortcut (the `0x13548` skip flag — unreachable, see above)
   (`analysis/ztie.md` §7 item 10). There is no config-only fix; route 1 is
   the only way forward.

## Boot-record facts (verified by disassembly)

`ndisasm -b 16 -o 0x7c00 -k 0,62` on `Disk1.img` sector 0:

```
7CC1  mov bx,0x500       ; first root-dir sector -> 0000:0500
7CD7  mov di,bx          ; entry 0
7CDC  mov si,0x7de6      ; -> "IO      SYSMSDOS   SYS"
7CDF  repe cmpsb         ; entry 0 must be IO.SYS
7CE1  jnz 0x7ced         ;   else "Non-System disk or disk error"
7CE3  lea di,[bx+0x20]   ; entry 1 must be MSDOS.SYS
7D05  mov ax,[bx+0x1a]   ; IO.SYS first cluster
7D1A  mov bx,0x700       ; -> 0070:0000
7D1D  mov cx,0x3         ; 3 consecutive sectors; the FAT is never walked
```

Root-dir LBA = `hidden + resv + nfat*spf` (`0x7C84..0x7C97`). Confirms the
earlier trace notes: the boot code self-overwrites at `0x7C59` (`rep movsb`,
11 bytes to `0x7C3E`), so RAM at `0x7C3E` in a trace is the *overwritten* copy;
drive reset `AH=0` at `0x7C70`; error path is the loop at `0x7CED–0x7D03`.

## The five rules that make an image boot

Asserted in `dosimg.py::_install_boot_record`, so a violation fails the build:

1. **A hard disk needs an MBR partition table** (the old `C:` bug — see above).
2. **Use the genuine MS-DOS 6.22 boot record**, replacing only its BPB
   (`0x0B..0x3D`) with mformat's; mformat's own boot code hangs in QEMU
   (`rep movsw` at `0x7C4F`, CX=256).
3. **IO.SYS = root entry 0, MSDOS.SYS = entry 1**, IO.SYS's first 3 sectors
   consecutive. Copy them before anything else and never pass `mformat -v LABEL`
   (it spends entry 0 on a volume label; the label goes in the BPB instead).
4. **BPB `hidden` (0x1C) = the partition start LBA**; total16/total32 describe
   the *partition*, not the disk.
5. **BPB CHS must match what the emulator reports** — geometry comes from the
   `.geom.json` sidecar, never a literal.

The MBR (`work/mbr.asm`, 446 B) relocates 0000:7C00 → 0000:0600, finds the active
partition, reads its boot sector via **INT 13h AH=42h (LBA)** with an **AH=02h
CHS fallback**, then jumps with `DL` = drive and `DS:SI` = the partition entry.

## Headless observation

1. **`C:\QUIT.COM` → isa-debug-exit** (8 bytes: `mov dx,0F4h / mov al,0Ah /
   out dx,al / int 20h`). With `-device isa-debug-exit,iobase=0xf4,iosize=0x04`
   QEMU exits with code `(0x0A<<1)|1 = 21` — the guest ends its own run, so a
   different exit code means it hung. `INT 20h` keeps it harmless in 86Box.
   This replaces the dead serial sink and the whole `probe*.com` line of work.
2. **QMP `screendump`** → PPM → PNG (ffmpeg); works in graphics modes.
3. **Guest files** read back with `mtype`; `AUTOEXEC.BAT` logs to `C:\BOOT.LOG`
   and `TIE.EXE`'s own stdout is redirected to `C:\TIE.LOG`.

## Memory configuration

LucasArts' own, taken verbatim from strings embedded in `BOOTTIE.EXE` (their
boot-disk maker):

```
DEVICE=C:\DOS\HIMEM.SYS
DEVICE=C:\DOS\EMM386.EXE 2560 RAM
DOS=HIGH,UMB
FILES=40
BUFFERS=20
```

Measured on the image (`MEM /C`): **617 KB largest executable program**,
**2 560 KB free EMS**, DOS resident in the HMA. DOS4GW needs the XMS; the
2560 KB of EMS is what the IMUSE audio path expects.

### KWAJ bootstrap

`HIMEM.SY_`, `EMM386.EX_`, `MEM.EX_`, `SHARE.EX_`, `XCOPY.EX_`, `SMARTDRV.EX_`
ship **KWAJ-compressed** (`4B 57 41 4A 88 F0 27 D1`, method `0x0003` =
LZ+Huffman) — 7-Zip and mtools cannot read it. The build copies the `.??_` files
plus the genuine `EXPAND.EXE` onto the image and boots it once to expand them in
place, then swaps in the real CONFIG.SYS. Automatic in `build_dos_hdd.py`;
`set_boot_mode.py bootstrap` redoes it.

## Run modes (`work/set_boot_mode.py`)

| Mode | What the image does on boot |
|---|---|
| `bootstrap` | expand the KWAJ files with `EXPAND.EXE`, log, `QUIT.COM` |
| `dos4gw` | LucasArts memory config, `MEM /C` + `DIR C:\TIECD` → `C:\BOOT.LOG`, `QUIT.COM` |
| `tie` | `dos4gw` + run `C:\TIECD\TIE.EXE` (stdout → `C:\TIE.LOG`) |
| `shell` | `dos4gw`, then a `C:\TIECD>` prompt (interactive, with a display) |
| `dos32a` | `dos4gw` + run `C:\DOS\DOS32A.EXE Z_TIE__.EXE /trebla /320` from `C:\TIECD` (stdout → `C:\DOS32A.LOG`) — the P3.3 extender retest, confirmed working (see status board) |

`tie` runs `TIE.EXE` directly, **not `run.bat`** — that is the sound-selection
menu and this machine has no sound card.

## QEMU invocation

```bash
qemu-system-i386 -M pc -cpu 486 -m 16 \
  -drive file=img/tie.hdd,format=raw,if=none,id=hd0,cache=writeback \
  -device ide-hd,drive=hd0,bus=ide.0,unit=0,cyls=521,heads=16,secs=63 \
  -boot c -display none -vga std -no-reboot \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -qmp tcp:127.0.0.1:4555,server=on,wait=off
# add a CD:  -drive file=…/SWTIECD.iso,format=raw,if=none,id=cd0,media=cdrom,readonly=on \
#            -device ide-cd,drive=cd0,bus=ide.1,unit=0
```

**QEMU ≥ 6 rejects `cyls=`/`heads=`/`secs=` on `-drive`** ("Block format 'raw'
does not support the option 'cyls'") — CHS geometry belongs on the *device*.
This is new since the notes above were first written.

## Gotchas

- **mtools + Windows paths**: a trailing `C:\...` destination is parsed as a
  *drive letter* → `Drive 'C:' not supported`. Run mcopy with `cwd=` set and `.`
  as the destination. `-i` needs a Windows path (`C:\...`), not `/c/...`.
- **`mformat -r` counts SECTORS, not entries** — `-r 32` = 512 root entries.
- **Partition entry offsets**: type at `+4` (`0x1C2`), start LBA at `+8`
  (`0x1C6`), size at `+12` (`0x1CA`).
- **Python stdout is block-buffered when redirected** — use `python -u`.
- **GDB without a target executable** decodes real-mode bytes as x86-64. Use raw
  byte dumps + explicit register reads (`printf "pc=%04x\n", $pc`).
- **Parked machine** = EIP `0xFF53` (SeaBIOS); blank text screen = boot failed.
- **QMP `sendkey`** works but is timing-sensitive; interactive FDISK keying is
  unreliable. With `QUIT.COM` + `set_boot_mode.py` it is no longer needed.

## Cross-project

`work/dosimg.py`, `work/run_qemu.py`, `work/mbr.asm` and `work/gdbstub_probe.py`
are byte-identical in `C:\Arbeit\F030Underworld` (UW1, `img/uw.hdd`),
`C:\Arbeit\F030Underworld2` (UW2, `img/uw2.hdd`) and `C:\Arbeit\F030F29` (F29,
in `tools/dos/`); only `build_dos_hdd.py` and `set_boot_mode.py` differ per
game. Both UW images boot and run their game headless. The master copies live
in `C:\Arbeit\F030Method\dos\` — `python dos/sync.py` there checks every
project copy, `--push` updates them; UW1's `analysis/qemu-boot.md` is the
canonical write-up of the shared parts.

**`work/gdbstub_probe.py` reads the *running* program**, over QMP rather than
GDB — QEMU's gdbstub accepts the connection and then drops commands
intermittently on this Windows build, which is worth knowing before spending an
afternoon on it. Three things here make it directly useful for open question 9
(the LE fixups):

- its **residency check** diffs the on-disk image against guest RAM in 16-byte
  windows, so the applied fixups are exactly the windows that differ — the
  relocated image can be read instead of reconstructed;
- it **calibrates `file → linear` from signatures in RAM** by majority vote,
  skipping windows that contain a relocation;
- it **drives the game with `sendkey`** and screenshots each step, which is how
  to reach the ERROR #3 moment reproducibly.

⚠ Pass `--exe` here: the "largest MZ in the game tree" default picks the
installer-compressed `Z_TIE__.EXE`. Method and traps: UW1's
`analysis/qemu-boot.md` §"Probing the running game"; `analysis/cross-project.md`
§6 and §7.
