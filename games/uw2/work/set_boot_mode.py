#!/usr/bin/env python3
r"""Rewrite CONFIG.SYS / AUTOEXEC.BAT inside img/uw2.hdd without rebuilding it.

A full build_dos_hdd.py run recopies 11 MB of game data; swapping the two boot
files in place with mtools takes under a second, so iterate with this.

Modes:
  bootstrap  no memory managers; expand HIMEM/EMM386/... from the KWAJ `.??_`
             archives with the genuine EXPAND.EXE, then QUIT.COM.
  ems        HIMEM + EMM386 RAM (UW2 probes for `EMMXXXX0`); report MEM /C; QUIT.
  uw2        ems + MOUSE33.COM + launch C:\UW2\UW2.EXE.  Does NOT quit -- the
             game owns the screen, so end the run with run_qemu.py --timeout
             and read the screenshot it captures.
  shell      ems + MOUSE33.COM, then drop to COMMAND.COM (interactive poking
             with a display).

Usage: python work/set_boot_mode.py <mode>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDD = os.path.join(ROOT, 'img', 'uw2.hdd')
STAGE = os.path.join(ROOT, 'work', 'img_build')
PART_OFF = json.load(open(HDD + '.geom.json'))['part_offset']

MEMCFG = (b'DEVICE=C:\\DOS\\HIMEM.SYS\r\n'
          b'DEVICE=C:\\DOS\\EMM386.EXE RAM\r\n'
          b'DOS=HIGH,UMB\r\n'
          b'FILES=30\r\n'
          b'BUFFERS=20\r\n')

HEAD = b'@ECHO OFF\r\nPROMPT $P$G\r\nPATH C:\\DOS\r\n'

MODES = {
    'bootstrap': (b'FILES=30\r\nBUFFERS=20\r\n', dosimg.expand_autoexec()),
    'ems': (
        MEMCFG,
        HEAD +
        b'ECHO === ems === > C:\\BOOT.LOG\r\n'
        b'VER >> C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n'
        b'DIR C:\\UW2 >> C:\\BOOT.LOG\r\n'
        b'ECHO === ems done === >> C:\\BOOT.LOG\r\n'
        b'C:\\QUIT.COM\r\n'),
    'uw2': (
        MEMCFG,
        HEAD +
        b'ECHO === uw2 === > C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n'
        b'C:\\MOUSE33.COM >> C:\\BOOT.LOG\r\n'
        b'C:\r\nCD \\UW2\r\n'
        b'ECHO --- launching UW2.EXE --- >> C:\\BOOT.LOG\r\n'
        b'UW2.EXE\r\n'
        b'ECHO --- UW2.EXE returned --- >> C:\\BOOT.LOG\r\n'
        b'CD \\\r\nC:\\QUIT.COM\r\n'),
    'shell': (MEMCFG, HEAD + b'C:\\MOUSE33.COM\r\nC:\r\nCD \\UW2\r\n'),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in MODES:
        sys.exit(f'usage: set_boot_mode.py {{{"|".join(MODES)}}}')
    config, autoexec = MODES[sys.argv[1]]
    for name, data in (('CONFIG.SYS', config), ('AUTOEXEC.BAT', autoexec)):
        p = os.path.join(STAGE, name)
        open(p, 'wb').write(data)
        r = subprocess.run([dosimg.host_tool('mcopy'), '-o', '-i',
                            f'{HDD}@@{PART_OFF}', p, '::/' + name],
                           capture_output=True, text=True,
                           env=dict(os.environ, MTOOLS_SKIP_CHECK='1'))
        if r.returncode != 0:
            sys.exit(f'mcopy failed: {r.stdout}{r.stderr}')
    print(f'img/uw2.hdd set to mode "{sys.argv[1]}"')


if __name__ == '__main__':
    main()
