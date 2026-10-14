#!/usr/bin/env python3
r"""Build img/uw2.hdd -- bootable MS-DOS 6.22 disk running Ultima Underworld 2.

    python work/build_dos_hdd.py            # build + in-guest EXPAND bootstrap
    python work/build_dos_hdd.py --no-boot  # build only

UW2 ships across five install disks; `work/extracted/D1..D5` are the LZH-expanded
trees, which the installer merges into one directory.  They merge without a
single collision (305 unique paths -> DATA/ CRIT/ CUTS/ SOUND/ + UW2.EXE), so
add_tree() takes all five at once.

Like UW1, UW2 is 16-bit real mode and probes for `EMMXXXX0` (the string appears
in UW2.EXE next to "Out of EMS Memory.$"), so the runtime config is
HIMEM + EMM386 RAM.  Layout/boot-record rules: work/dosimg.py.
Procedure and gotchas: analysis/qemu-boot.md.

UW2.EXE's main menu needs a real mouse (verified: it calls INT 33h AX=0/3/0Bh
and nothing else, analysis/qemu-boot.md "Probing the running game") but the
DOS 6.22 floppies carry no driver, so work/mouse_driver.asm -- a from-scratch
minimal INT 33h driver, assembled here and loaded by set_boot_mode.py's `uw2`
and `shell` modes -- is staged onto the image as /MOUSE33.COM.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOPPIES = os.path.join(ROOT, 'img', 'Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)')
WORK = os.path.join(ROOT, 'work', 'img_build')
EXTRACTED = os.path.join(ROOT, 'work', 'extracted')
OUT = os.path.join(ROOT, 'img', 'uw2.hdd')

dosimg._verify_mbr(os.path.join(ROOT, 'work', 'mbr.asm'),
                   os.path.join(WORK, 'mbr.bin'))

mouse_com = os.path.join(WORK, 'mouse_driver.com')
dosimg.run('nasm', '-f', 'bin', os.path.join(ROOT, 'work', 'mouse_driver.asm'),
           '-o', mouse_com)

disks = [os.path.join(EXTRACTED, d) for d in sorted(os.listdir(EXTRACTED))
         if os.path.isdir(os.path.join(EXTRACTED, d))]
print('merging install disks:', [os.path.basename(d) for d in disks])

img = dosimg.DosImage(OUT, size_mb=32, floppy_dir=FLOPPIES, work_dir=WORK,
                      label='UW2_DOS')
print(f'game files: {img.add_tree("/UW2", *disks)}')
img.add_file(mouse_com, '/MOUSE33.COM')
img.add_bytes(b'FILES=30\r\nBUFFERS=20\r\n', '/CONFIG.SYS')
img.add_bytes(dosimg.expand_autoexec(), '/AUTOEXEC.BAT')
img.write()

if '--no-boot' not in sys.argv:
    print('\n--- bootstrap boot (in-guest EXPAND) ---')
    rc = subprocess.call([sys.executable, os.path.join(ROOT, 'work', 'run_qemu.py'),
                          '--timeout', '120', '--cat', '::/BOOT.LOG'])
    if rc != 0:
        sys.exit('bootstrap boot failed -- see output above')
    subprocess.check_call([sys.executable,
                           os.path.join(ROOT, 'work', 'set_boot_mode.py'), 'uw2'])
