# Regenerating derived work

From the project root:

```text
python tools/extract_cd.py
python tools/re/mzinfo.py game/cd/LCD.EXE
python tools/re/mzinfo.py game/cd/LCD.EXE --dump-load work/listings/LCD.load
python tools/stage_install.py
python work/build_dos_hdd.py --no-boot
```

The first command extracts the supplied ISO into `game/cd/`; the second audits
the MZ container; the third writes the load-image dump; the fourth stages the
`[MIN_INSTALL]` files listed in the CD's `INSTALL.INI`; and the fifth builds
`img/links386.hdd` once genuine DOS 6.22 floppies are available. Add
`--profile max` to `stage_install.py` only when a
course-resource experiment needs the optional `[MAX_INSTALL]` files. Add
`--run-game` to the image builder to launch `GOLFCD.BAT` after boot.

`dosimg.py`, `run_qemu.py`, `mbr.asm` and `gdbstub_probe.py` are synchronized
from `../F030Method/dos/`; do not edit their project copies directly.

After the bootstrap pass, rewrite the derived disk for the game oracle with
`python work/set_boot_mode.py game`. Use
`python work/set_boot_mode.py game --no-mouse` only for the controlled
keyboard-equivalent prompt experiment; both modes leave the canonical CD
extraction unchanged.

## Targeted measurements

`read_mz_selector_table.py` is project-specific and reads the MZ-side selector
table out of a running guest, `[0x587C]` in particular:

```text
python work/read_mz_selector_table.py --at 26 --key 28:y --at 32
```

It stops the CPU before every capture, so the screen, the registers and the
RAM dump describe one instant, and it locates the table by the eleven known
constants around the word under test rather than by an assumed data segment.

`watch_mirror.py` (on `rsp.py`, a GDB remote-serial client with `Z0`/`Z2`/`Z3`)
breakpoints and watchpoints **linear** addresses while QMP drives the game:

```text
python work/watch_mirror.py --watch 0xC2A3F8:2 --key-on-prompt y
python work/watch_mirror.py --break 0xC2C136 --pagewalk 0xC2A3F8 \
    --key-on-prompt y --arm-on-prompt
python work/watch_mirror.py --rwatch 0x3F8:2 --key-on-prompt y --arm-on-prompt
python work/watch_mirror.py --dflags int --key-on-prompt y --max-hits 1
```

`--arm-on-prompt` defers arming until the mouse/keyboard gate is on screen, so
an address that runs hundreds of times during startup and once more in the
failing window is readable. `--rwatch` is what identifies the effective address
an instruction really dereferences; `--dflags int` logs one line per exception
with its vector and error code. `rsp.py` is project-local; the `Z0` half comes
from `F030Comanche/work/rsp.py`.

## Diagnostic artefacts, not authorities

`work/patched/LCD.EXE` and `img/links386_qemufix.hdd` are a derived build that
replaces the extender's 25 `mov ds, cs:[0x3F8]` sites with its own
`push 0x10 / pop ds / nop` idiom, to prove that QEMU's dropped `CS` override
causes the `10049`. It does: the error disappears, and the run then dies on the
next CS-override read of the same variable. Neither artefact is a behavioural
authority for anything about Links 386. Rebuild with the loop in
`analysis/executable.md`; `img/` is gitignored.

`work/segtest/` is the standalone reproducer for the emulator defect, with
`UPSTREAM.md` ready to send.
