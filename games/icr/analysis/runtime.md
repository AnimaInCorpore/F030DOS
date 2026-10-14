# First DOS-oracle observations — IndyCar Racing v1.05

Status: `PARTIALLY RESOLVED` — the canonical floppy-derived image now reaches
copy protection, the front-end menus, track metadata and a rendered practice
cockpit. The original disk error was caused by incorrect placement of the
extracted track payloads; full race, input and replay coverage remains open.

## Image and bootstrap

`work/build_dos_hdd.py --no-boot` stages the 37-file base installed tree plus
the 48 extracted track files, builds `img/icr.hdd` at 34,062,336 bytes, and
passes the MBR verification. The shared harness fix for nested directories was
required because the base tree contains `CARS/CARS93` and `EFFECTS/EFFECTS.DAT`.

The first boot under QEMU 486 with 16 MB RAM exits through `QUIT.COM` with the
expected clean code 21. `BOOT.LOG` confirms MS-DOS 6.22 and successful
expansion of the compressed HIMEM/EMM386/MEM/SHARE/XCOPY/SMARTDRV support
files. The per-game configuration uses HIMEM plus `DOS=HIGH`, following the
shipped `README.DOC` guidance for conventional and XMS memory without EMS.

## Game launch

The AUTOEXEC path is `CD C:\INDYCAR`, `INDYCAR.EXE`, then `QUIT.COM`; stdout is
captured to `C:\GAME.LOG`. The executable prints its loading banner and
Version 1.05 copyright. Initial images either omitted the tracks or flattened
their files into `C:\INDYCAR\TRACKS`, and those images reported:

```text
Miscellaneous disk error
```

The corrected builder preserves the conventional layout
`C:\INDYCAR\TRACKS\<track>\<file>`, including each track's distinct setup
files. After rebuilding, the exact supplied executable and installed tree
render the IndyCar splash screen and, after keyboard input, reach the
copy-protection prompt instead of the disk error.

A live INT 21h trace confirms subsequent opens of `controls.cfg`,
`a32sbfm.dll`, `a32sbdg.dll`, and `calib.val`; the calibration file is opened
for a `0x30`-byte read/write state block. Its absence did not block the
canonical launch now that track placement is correct.

## Copy protection and front-end flow

The canonical builder output `img/icr.hdd` used for the fresh witness was
34,062,336 bytes with SHA-256
`51F73273205270A0B63A68FF8C856B0ED2C0D3B689A66B30A2854236A7B12E22`. It
reaches the copy-protection screen after the animated introduction. The introduction
does not advance on its own in the headless run; a Space keypress advances it.
The requested page, line and word are randomized per launch. The following
manual-answer-grid checks were observed against the hash-identified
`INDYCAR.EXE`:

| Prompt | Answer | Result |
|---|---|---|
| Page 21, line 6, word 1 | `current` | accepted |
| Page 89, line 1, word 1 | `the` | rejected in one run; the typed buffer was visibly correct |

The accepted `current` run reached the main menu. An incorrect answer leaves
the prompt on screen with `Try again`; Return restarts the introductory
sequence. The answer grid used for the accepted check is [external supporting
material](https://dosdays.co.uk/media/games/indycar/Copy%20Protection%20Answers%2003-67.jpg),
not part of the supplied floppy-derived tree.

From the accepted main-menu state, Return entered `SINGLE RACE`, which reached
`CHOOSE A TRACK`; the selected New Hampshire track then displayed its metadata
and entered the single-race session menu containing `REPLAY`, `GARAGE`,
`PRACTICE`, `NEXT SESSION (QUALIFY)` and `Leave New Hampshire`. This proves
that the corrected per-track directory layout is sufficient to load track
metadata past startup. Return on the highlighted `PRACTICE` entry rendered the
cockpit and New Hampshire pit lane. A held QEMU `Up` key advanced the car from
the stationary dashboard state to a visible 15 mph / 2142 rpm state in
`work/qemu_out/practice_accelerating.png`; this is the first measured driving
input witness. A protected-mode register and RAM capture from the practice
state is recorded below. Steering, pit exit, full laps, race progression and
replay flow remain unmeasured.

## Protected-mode memory witness

A 16 MiB physical-memory dump (`ram_icr_16m_fresh.bin`, SHA-256
`535192569865B3D22FE71178DE1D2A75BF74BB707746C514F34FB30D2FADAF48`) taken
from the fresh QEMU 486 run while the game was active matched all 102 sampled
LE data-page windows. The known appended runtime code at file offset `0x93A8F`
was found at linear address `0x1C296B`; the generic file-I/O wrapper at
`0x9EDA3` appeared at `0x1CDC7F`, giving a common file-to-linear delta
`+0x12EEDC`. An earlier run found the same two windows at `0x1D296B` and
`0x1DDC7F` (`+0x13EEDC`). The one-megabyte shift proves that DOS/4GW runtime
placement is allocation-dependent and that a file-to-linear calibration must
be repeated for each boot; the earlier delta is a valid sample, not a fixed
address contract.

The DOS/4GW selectors are flat in the fresh capture (`CS=0x0180`,
`DS/SS=0x0188`, base zero), so a probe restricted to physical `0..0xA0000`
cannot see the executing image. The shared probe's no-hit result is therefore
not residency evidence for this protected-mode build.

A practice-state capture (`ram_icr_practice_16m.bin`, SHA-256
`B0D09DD28D1EC876659451D391E4952674622F53789D8645707975408630DDA1`) recorded
the same flat selectors with `EIP=0x001C982F` while the track was active. The
next dynamic boundary is steering, pit exit and a complete lap, followed by
capturing the track-load, input, graphics and sound substitutions. Track
archives are staged as `C:\INDYCAR\TRACKS\<track>` by the builder; see
[`tracks.md`](tracks.md).

## Rebuild from clean, 2026-08-26

The derived trees are regenerable and were regenerated from the immutable
floppy images to re-verify the recorded hashes end to end:

```text
python tools/re/extract_media.py
python tools/re/merge_indycar.py
python tools/re/extract_install.py
python tools/re/extract_tracks.py
python work/build_dos_hdd.py
```

`work/INDYCAR.MERGED` reproduced at 1,084,877 bytes SHA-256
`3EBB2AC3FA30D82A4EBCFDE3F77DAD223611EEF8D07DDD29B6326EA001F5EB36`, all 37
installed files and 48 track files expanded and tested, and
`game/installed/INDYCAR.EXE` re-hashed to the recorded authority value. The
image builds and boots as recorded, and the game reaches the prompt without any
keypress at ~90 s.

`build_dos_hdd.py` exits non-zero on that run: its bootstrap boot ends with
`run_qemu.py --timeout 120`, and the game now blocks at the gate instead of
falling through to `QUIT.COM`, so the run times out. The image itself is
complete and `BOOT.LOG` shows the expected bootstrap — use `--no-boot` until
the gate is passed.

## Protected-mode probing

The guest at the prompt is 32-bit protected mode, flat (`CR0.PE=1`, `PG=0`,
descriptor bases 0). The shared probe assumed real mode and reported
`0180:99E0 = 0x0b1e0` for an EIP of `0x001999D7`; it now detects the mode and
can dump RAM:

```text
python work/gdbstub_probe.py --wait 100 --dump-ram
```

Worth knowing for the next capture: the first probe of this game read the
conventional-memory-only scan as "signature NOT FOUND in RAM (overwritten at
runtime?)" for every window. Nothing was overwritten — the image is above
1 MB.
