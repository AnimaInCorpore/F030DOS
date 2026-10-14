#!/usr/bin/env python3
r"""Build img/uw.hdd -- bootable MS-DOS 6.22 disk running Ultima Underworld 1.

    python work/build_dos_hdd.py            # build + in-guest EXPAND bootstrap
    python work/build_dos_hdd.py --no-boot  # build only

    # boot a reassembled build without touching the reference image:
    python work/build_dos_hdd.py --no-boot --game-dir work/reasm/out/game \
                                 --out img/uw_reasm.hdd

UW1 is a 16-bit real-mode game that probes for `EMMXXXX0` (verified: the string
occurs twice in UW.EXE, alongside "Out of EMS Memory.$"), so the runtime config
is HIMEM + EMM386 RAM.  All layout/boot-record rules live in work/dosimg.py;
run modes live in work/set_boot_mode.py.  Procedure: analysis/qemu-boot.md.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLOPPIES = os.path.join(ROOT, 'img', 'Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)')
WORK = os.path.join(ROOT, 'work', 'img_build')
EXPANDED = os.path.join(ROOT, 'work', 'expanded')     # 290 LZH-expanded game files
OUT = os.path.join(ROOT, 'img', 'uw.hdd')


def _opt(flag, default):
    """--flag VALUE, resolved against the project root."""
    if flag in sys.argv:
        return os.path.join(ROOT, sys.argv[sys.argv.index(flag) + 1])
    return default


EXPANDED = _opt('--game-dir', EXPANDED)
OUT = _opt('--out', OUT)

dosimg._verify_mbr(os.path.join(ROOT, 'work', 'mbr.asm'),
                   os.path.join(WORK, 'mbr.bin'))

img = dosimg.DosImage(OUT, size_mb=32, floppy_dir=FLOPPIES, work_dir=WORK,
                      label='UW_DOS')
n = img.add_tree('/UW', EXPANDED)
print(f'game files: {n}')
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
                           os.path.join(ROOT, 'work', 'set_boot_mode.py'), 'ems', OUT])
