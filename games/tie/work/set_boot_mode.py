#!/usr/bin/env python3
r"""Rewrite CONFIG.SYS / AUTOEXEC.BAT inside img/tie.hdd without rebuilding it.

A full build_dos_hdd.py run recopies 95 MB of game data; swapping the two boot
files in place with mtools takes under a second, so iterate with this.

Modes:
  bootstrap  no memory managers; expand HIMEM/EMM386/... from the KWAJ `.??_`
             archives with the genuine EXPAND.EXE, then QUIT.COM.
  dos4gw     LucasArts' own config (HIMEM + `EMM386.EXE 2560 RAM` +
             DOS=HIGH,UMB, per BOOTTIE.EXE); report MEM /C; QUIT.
  tie        dos4gw + launch C:\TIECD\TIE.EXE directly.  Not `run.bat`: that is
             the sound-selection menu, and this machine has no sound card
             (QEMU's Windows build rejects -soundhw).  Does NOT quit -- end the
             run with run_qemu.py --timeout and read the screenshot.
  shell      dos4gw, then drop to COMMAND.COM in C:\TIECD.
  dos32a     dos4gw config + run C:\DOS\DOS32A.EXE Z_TIE__.EXE /trebla /320
             instead of the DOS4GW chain (P3.3 retest: does DOS/32A load the
             standard-LE 32-bit image the same way DOS4GW does?). Output goes
             to C:\DOS32A.LOG; success = the same ERROR #3 CD-check text.

Usage: python work/set_boot_mode.py <mode>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MSYS = r'C:\msys64\mingw64\bin'
HDD = os.path.join(ROOT, 'img', 'tie.hdd')
STAGE = os.path.join(ROOT, 'work', 'img_build')
PART_OFF = json.load(open(HDD + '.geom.json'))['part_offset']

# Verbatim from BOOTTIE.EXE's embedded boot-disk template.
MEMCFG = (b'DEVICE=C:\\DOS\\HIMEM.SYS\r\n'
          b'DEVICE=C:\\DOS\\EMM386.EXE 2560 RAM\r\n'
          b'DOS=HIGH,UMB\r\n'
          b'FILES=40\r\n'
          b'BUFFERS=20\r\n')

HEAD = b'@ECHO OFF\r\nPROMPT $P$G\r\nPATH C:\\DOS\r\n'

MODES = {
    'bootstrap': (b'FILES=40\r\nBUFFERS=20\r\n', dosimg.expand_autoexec()),
    'dos4gw': (
        MEMCFG,
        HEAD +
        b'ECHO === dos4gw === > C:\\BOOT.LOG\r\n'
        b'VER >> C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n'
        b'DIR C:\\TIECD >> C:\\BOOT.LOG\r\n'
        b'ECHO === dos4gw done === >> C:\\BOOT.LOG\r\n'
        b'C:\\QUIT.COM\r\n'),
    'tie': (
        MEMCFG,
        HEAD +
        b'ECHO === tie === > C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n'
        b'C:\r\nCD \\TIECD\r\n'
        b'ECHO --- launching TIE.EXE --- >> C:\\BOOT.LOG\r\n'
        b'TIE.EXE > C:\\TIE.LOG\r\n'
        b'ECHO --- TIE.EXE returned --- >> C:\\BOOT.LOG\r\n'
        b'CD \\\r\nC:\\QUIT.COM\r\n'),
    'shell': (MEMCFG, HEAD + b'C:\r\nCD \\TIECD\r\n'),
    'dos32a': (
        MEMCFG,
        HEAD +
        b'ECHO === dos32a === > C:\\BOOT.LOG\r\n'
        b'C:\r\nCD \\TIECD\r\n'
        b'ECHO --- launching DOS32A Z_TIE__.EXE --- >> C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\DOS32A.EXE Z_TIE__.EXE /trebla /320 > C:\\DOS32A.LOG\r\n'
        b'ECHO --- DOS32A returned --- >> C:\\BOOT.LOG\r\n'
        b'CD \\\r\nC:\\QUIT.COM\r\n'),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in MODES:
        sys.exit(f'usage: set_boot_mode.py {{{"|".join(MODES)}}}')
    config, autoexec = MODES[sys.argv[1]]
    for name, data in (('CONFIG.SYS', config), ('AUTOEXEC.BAT', autoexec)):
        p = os.path.join(STAGE, name)
        open(p, 'wb').write(data)
        r = subprocess.run([os.path.join(MSYS, 'mcopy.exe'), '-o', '-i',
                            f'{HDD}@@{PART_OFF}', p, '::/' + name],
                           capture_output=True, text=True,
                           env=dict(os.environ, MTOOLS_SKIP_CHECK='1'))
        if r.returncode != 0:
            sys.exit(f'mcopy failed: {r.stdout}{r.stderr}')
    print(f'img/tie.hdd set to mode "{sys.argv[1]}"')


if __name__ == '__main__':
    main()
