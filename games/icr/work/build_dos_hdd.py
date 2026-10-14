#!/usr/bin/env python3
r"""Build img/icr.hdd -- bootable MS-DOS 6.22 disk running the game.

    python F030ICR/work/build_dos_hdd.py            # build + bootstrap boot
    python F030ICR/work/build_dos_hdd.py --no-boot  # build only

Seeded by F030Method/dos/sync.py --init F030ICR.  The shared half (dosimg.py,
run_qemu.py, mbr.asm, gdbstub_probe.py) is synced from that master and must not
be edited here; this file is the per-game half and is yours.

Layout rules, boot-record invariants and the five things that make the image
actually boot: dosimg.py's module docstring.  Procedure and gotchas: write them
up in this project own qemu-boot.md / DOS-ORACLE.md as you hit them.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = dosimg.find_project_root(__file__)
WORK = os.path.join(ROOT, 'work', 'img_build')
OUT = os.path.join(ROOT, 'img', 'icr.hdd')

dosimg._verify_mbr(os.path.join(HERE, 'mbr.asm'), os.path.join(WORK, 'mbr.bin'))

# --- per-game block: everything below here is a claim about THIS game --------
#
# GAME_TREE   the extracted, pristine game directory to stage onto the image.
# GUEST_DIR   where it lands in the guest; the game own .BAT/.CFG may care.
# SIZE_MB     big enough for DOS + the tree, with room for logs written back.
# CONFIG.SYS  what the game needs resident.  Check the binary for `EMMXXXX0`
#             (EMS) and `XMSXXXX0` (XMS) before deciding -- guessing here costs
#             a boot cycle each time.  HIMEM/EMM386 are expanded in-guest by
#             dosimg bootstrap, so they are available.
# AUTOEXEC    expand_autoexec() ends with C:\QUIT.COM so the guest terminates
#             the run itself (QEMU exit 21).  Put the game own launcher line
#             in `then=` once booting is proven, not before.
#
GAME_TREE = os.path.join(ROOT, 'game', 'installed')
TRACK_TREE = os.path.join(ROOT, 'game', 'tracks')
GUEST_DIR = '/INDYCAR'
SIZE_MB = 32

img = dosimg.DosImage(OUT, size_mb=SIZE_MB, work_dir=WORK,
                      label='icr')
print('game files: %d' % img.add_tree(GUEST_DIR, GAME_TREE))
# Track archives are a separate install layer.  Preserve each archive's
# directory so repeated setup filenames do not collide and the game sees the
# conventional C:\INDYCAR\TRACKS\<track> layout.
print('track files: %d' % img.add_tree(GUEST_DIR + '/TRACKS', TRACK_TREE))
# README.DOC says the game uses conventional + XMS memory and recommends no
# EMS.  HIMEM is expanded by the bootstrap AUTOEXEC before the oracle launch.
img.add_bytes(b'DEVICE=C:\\DOS\\HIMEM.SYS\r\nDOS=HIGH\r\n'
              b'FILES=40\r\nBUFFERS=30\r\n', '/CONFIG.SYS')
img.add_bytes(dosimg.expand_autoexec(
    then=b'CD C:\\INDYCAR\r\nINDYCAR.EXE > C:\\GAME.LOG\r\n'
         b'C:\\QUIT.COM\r\n'),
              '/AUTOEXEC.BAT')
# --- end per-game block ------------------------------------------------------

img.write()

if '--no-boot' not in sys.argv:
    print('\n--- bootstrap boot (in-guest EXPAND) ---')
    rc = subprocess.call([sys.executable, os.path.join(HERE, 'run_qemu.py'),
                          '--timeout', '120', '--cat', '::/BOOT.LOG'])
    if rc != 0:
        sys.exit('bootstrap boot failed -- see output above')
