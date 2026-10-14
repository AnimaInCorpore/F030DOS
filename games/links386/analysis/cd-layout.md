# CD layout

Status: **IDENTIFIED**.

The CD root contains the executable and a minimum-install manifest. Large
course/video/audio files are also present on the CD and should stay in the
pristine extraction until a format-specific experiment needs them.

The reproducible setup is:

```text
python tools/extract_cd.py
python tools/stage_install.py
```

The staged tree is derived and ignored. It is not a second source of truth:
the ISO and `game/cd/` remain the reference inputs.

The minimum installation is currently staged as 54 files totaling 8,474,396
bytes. A genuine MS-DOS 6.22 floppy set was found in the sibling project
`C:\Arbeit\F030Underworld2\img\Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)`.
`Disk1.img` through `Disk3.img` and `Suppdisk.img` are 1,474,560-byte FAT12
images; `Disk1.img` has the DOS boot sector and the expected `IO.SYS` and
`MSDOS.SYS` entries. The same set is also present under `F030Underworld`.

Using that directory through `F030_DOS_FLOPPIES`,
`work/build_dos_hdd.py --no-boot` produced the derived
`img/links386.hdd` (67,608,576 bytes; 131 cylinders, 16 heads, 63 sectors;
partition offset 32,256). QEMU is available at
`C:\\Program Files\\qemu\\qemu-system-i386.exe`; the image has now passed the
bootstrap boot test. The game-level runtime result is recorded in
`analysis/executable.md`.
