#!/usr/bin/env python3
r"""Build img/comanche.hdd -- bootable MS-DOS 6.22 disk running Comanche.

    python F030Comanche/work/build_dos_hdd.py            # build + bootstrap boot
    python F030Comanche/work/build_dos_hdd.py --no-boot  # build only

Seeded by F030Method/dos/sync.py --init F030Comanche.  The shared half (dosimg.py,
run_qemu.py, mbr.asm, gdbstub_probe.py) is synced from that master and must not
be edited here; this file is the per-game half and is yours.

Layout rules, boot-record invariants and the five things that make the image
actually boot: dosimg.py's module docstring.  Procedure and gotchas: write them
up in docs/DOS-ORACLE.md as you hit them.

Why this exists: the terrain marcher sits 21-23 rows off a measurement nobody
had, and eight parameter fits could not close it (METHOD.md 4.2, CROSS-PROJECT
adopt item 2).  This image is how the original gets measured instead of fitted.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = dosimg.find_project_root(__file__)
WORK = os.path.join(ROOT, 'work', 'img_build')
OUT = os.path.join(ROOT, 'img', 'comanche.hdd')

dosimg._verify_mbr(os.path.join(HERE, 'mbr.asm'), os.path.join(WORK, 'mbr.bin'))

# --- per-game block: everything below here is a claim about THIS game --------
#
# Every value here is read out of a file the game shipped, not chosen:
#
#   assets/extracted/comanche_hdd/C.BAT     `c:` / `cd \comanche` / `comanche`
#                                           -> the guest directory is C:\COMANCHE
#                                              and the launcher is COMANCHE.EXE
#   assets/extracted/comanche_hdd/CONFIG.XMS
#                                           DEVICE=C:\dos\himem.sys / DOS=HIGH /
#                                           BUFFERS=30 / FILES=30
#                                           -> HIMEM only; the game's own boot
#                                              disk loads no EMM386
#   BOOTXMS.BAT                             copies CONFIG.XMS/AUTOEXEC.XMS onto a
#                                           boot floppy -- i.e. those two files
#                                           *are* the shipped runtime config
#
# `EMMXXXX0` does appear once in the unpacked COMANCHE.EXE, so the program can
# detect EMS -- but the shipped config does not provide it, so neither does this
# image.  If a run turns out to need it, that is a finding to write down with
# the evidence, not a knob to turn first.  HIMEM.SYS is expanded in-guest by
# dosimg's bootstrap and lands in C:\DOS\, which is where CONFIG.XMS expects it.
#
# 7.3 MB of game tree + DOS: 32 MB leaves room for logs and screendumps.
#
GAME_TREE = os.path.join(ROOT, 'assets', 'extracted', 'comanche_hdd')
GUEST_DIR = '/COMANCHE'
SIZE_MB = 32

img = dosimg.DosImage(OUT, size_mb=SIZE_MB, work_dir=WORK, label='COMANCHE')
print('game files: %d' % img.add_tree(GUEST_DIR, GAME_TREE))
img.add_bytes(b'DEVICE=C:\\DOS\\HIMEM.SYS\r\nDOS=HIGH\r\n'
              b'BUFFERS=30\r\nFILES=30\r\n', '/CONFIG.SYS')
img.add_bytes(dosimg.expand_autoexec(), '/AUTOEXEC.BAT')
# --- end per-game block ------------------------------------------------------

img.write()

if '--no-boot' not in sys.argv:
    print('\n--- bootstrap boot (in-guest EXPAND) ---')
    rc = subprocess.call([sys.executable, os.path.join(HERE, 'run_qemu.py'),
                          '--timeout', '120', '--cat', '::/BOOT.LOG'])
    if rc != 0:
        sys.exit('bootstrap boot failed -- see output above')
