#!/usr/bin/env python3
r"""Build img/tie.hdd -- bootable MS-DOS 6.22 disk running TIE Fighter CD.

    python work/build_dos_hdd.py            # build + in-guest EXPAND bootstrap
    python work/build_dos_hdd.py --no-boot  # build only

The game runs from the folder copy, not the CD: `TIE.CD` contains `C:\TIECD`
and `CDROM.CFG` is `0 8202`, so the whole 95 MB tree goes to C:\TIECD and no
MSCDEX is needed.

Memory config is LucasArts' own: BOOTTIE.EXE (their boot-disk maker) writes
exactly `DEVICE=...\HIMEM.SYS`, `DEVICE=C:\DOS\EMM386.EXE 2560 RAM` and
`DOS=HIGH,UMB` -- verified as literal strings inside BOOTTIE.EXE.  DOS4GW needs
XMS; EMM386 supplies VCPI plus the 2560 KB of EMS the IMUSE/audio path expects.

This image supersedes `img/tie-dos.img`, whose `C:` DOS never recognised.  The
cause is now understood: that image was a *superfloppy* (FAT at LBA 0, no MBR
partition table) with `rootent=0` and a `total32` larger than the drive's
CHS-derived size.  See analysis/qemu-boot.md and work/dosimg.py.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOPPIES = os.path.join(ROOT, 'img', 'Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)')
WORK = os.path.join(ROOT, 'work', 'img_build')
GAME = os.path.join(ROOT, 'game', 'SWTieCD', 'TIECD')
OUT = os.path.join(ROOT, 'img', 'tie.hdd')

dosimg._verify_mbr(os.path.join(ROOT, 'work', 'mbr.asm'),
                   os.path.join(WORK, 'mbr.bin'))

img = dosimg.DosImage(OUT, size_mb=256, floppy_dir=FLOPPIES, work_dir=WORK,
                      label='TIE_DOS')
print(f'game files: {img.add_tree("/TIECD", GAME)}')

# TIE.EXE reads `c:\tie.cd` (literal string in TIE.EXE) to find the game
# directory; the file is 8 bytes of `C:\TIECD` and lives at the CD *root*, one
# level above TIECD/.  Without it TIE.EXE runs the CD installer instead of the
# game -- which is exactly what the first boot of this image did.
img.add_file(os.path.join(ROOT, 'game', 'SWTieCD', 'TIE.CD'), '/TIE.CD')

# DOS/32A (P3.3 extender retest, confirmed working -- analysis/extender-eval.md
# §Verdict): staged into C:\DOS so `work/set_boot_mode.py dos32a` can run it
# against Z_TIE__.EXE without a separate manual copy step.
img.add_file(os.path.join(ROOT, 'work', 'dos32a', 'binw', 'dos32a.exe'), '/DOS/DOS32A.EXE')

img.add_bytes(b'FILES=40\r\nBUFFERS=20\r\n', '/CONFIG.SYS')
img.add_bytes(dosimg.expand_autoexec(), '/AUTOEXEC.BAT')
img.write()

if '--no-boot' not in sys.argv:
    print('\n--- bootstrap boot (in-guest EXPAND) ---')
    rc = subprocess.call([sys.executable, os.path.join(ROOT, 'work', 'run_qemu.py'),
                          '--timeout', '120', '--cat', '::/BOOT.LOG'])
    if rc != 0:
        sys.exit('bootstrap boot failed -- see output above')
    subprocess.check_call([sys.executable,
                           os.path.join(ROOT, 'work', 'set_boot_mode.py'), 'dos4gw'])
