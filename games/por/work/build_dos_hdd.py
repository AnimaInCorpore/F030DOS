#!/usr/bin/env python3
r"""Build img/por.hdd -- bootable MS-DOS 6.22 disk for driving Pool of Radiance's
real INSTALL.EXE under QEMU (the dynamic oracle for POOL.CFG's format).

    python work/build_dos_hdd.py            # build + in-guest EXPAND bootstrap
    python work/build_dos_hdd.py --no-boot   # build only

Unlike the sibling projects' build_dos_hdd.py, this one does NOT copy the game
tree onto the image: the point of this oracle is to run the *original*
INSTALL.EXE from the original floppies (game/POR/disk1.img, disk2.img,
attached via run_qemu.py --floppy) so it writes a real POOL.CFG, not to
pre-stage an already-expanded tree. All layout/boot-record rules live in
work/dosimg.py; run modes live in work/set_boot_mode.py.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOPPIES = os.path.join(os.path.dirname(ROOT), 'F030Underworld', 'img',
                         'Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)')
WORK = os.path.join(ROOT, 'work', 'img_build')
OUT = os.path.join(ROOT, 'img', 'por.hdd')

dosimg._verify_mbr(os.path.join(ROOT, 'work', 'mbr.asm'),
                   os.path.join(WORK, 'mbr.bin'))

img = dosimg.DosImage(OUT, size_mb=32, floppy_dir=FLOPPIES, work_dir=WORK,
                      label='POR_DOS')
img.add_bytes(b'FILES=30\r\nBUFFERS=20\r\n', '/CONFIG.SYS')
img.add_bytes(dosimg.expand_autoexec(), '/AUTOEXEC.BAT')
img.write()

if '--no-boot' not in sys.argv:
    # First boot expands the KWAJ-compressed HIMEM/EMM386/... with the genuine
    # EXPAND.EXE, then QUIT.COM ends the run (exit code 21).
    print('\n--- bootstrap boot (in-guest EXPAND) ---')
    rc = subprocess.call([sys.executable, os.path.join(ROOT, 'work', 'run_qemu.py'),
                          '--hdd', OUT, '--timeout', '120', '--cat', '::/BOOT.LOG'])
    if rc != 0:
        sys.exit('bootstrap boot failed -- see output above')
    subprocess.check_call([sys.executable,
                           os.path.join(ROOT, 'work', 'set_boot_mode.py'), 'shell', OUT])
