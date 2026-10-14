#!/usr/bin/env python3
r"""Rewrite CONFIG.SYS / AUTOEXEC.BAT inside img/uw.hdd without rebuilding it.

A full build_dos_hdd.py run copies 10 MB of game data (~18 s); swapping the two
boot files in place with mtools takes well under a second, so iterate with this.

Modes:
  stage1  no memory managers; expand HIMEM/EMM386/MEM/SHARE from the .??_
          KWAJ archives with the genuine EXPAND.EXE, then QUIT.COM.
  ems     HIMEM + EMM386 RAM (UW probes for `EMMXXXX0`), report MEM /C, QUIT.
  uw      ems + launch C:\UW\UW.EXE.  Does NOT quit: the game owns the screen,
          so end the run with --timeout and a screendump.
  shell   ems, then drop to COMMAND.COM (for interactive poking with -display).

Usage: python work/set_boot_mode.py <mode>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCOPY = dosimg.host_tool('mcopy')   # not a hardcoded MSYS path: the oracle also runs on macOS
# optional 2nd argument selects a different image (e.g. a reassembled build)
HDD = (os.path.join(ROOT, sys.argv[2]) if len(sys.argv) > 2
       else os.path.join(ROOT, 'img', 'uw.hdd'))
STAGE = os.path.join(ROOT, 'work', 'img_build')
PART_OFF = json.load(open(HDD + '.geom.json'))['part_offset']

MEMCFG = (b'DEVICE=C:\\DOS\\HIMEM.SYS\r\n'
          b'DEVICE=C:\\DOS\\EMM386.EXE RAM\r\n'
          b'DOS=HIGH,UMB\r\n'
          b'FILES=30\r\n'
          b'BUFFERS=20\r\n')

HEAD = (b'@ECHO OFF\r\n'
        b'PROMPT $P$G\r\n'
        b'PATH C:\\DOS\r\n')

MODES = {
    'stage1': (
        b'FILES=30\r\nBUFFERS=20\r\n',
        HEAD +
        b'C:\r\nCD \\DOS\r\n'
        b'ECHO === stage1 === > C:\\BOOT.LOG\r\n'
        b'VER >> C:\\BOOT.LOG\r\n'
        b'EXPAND HIMEM.SY_ C:\\DOS\\HIMEM.SYS >> C:\\BOOT.LOG\r\n'
        b'EXPAND EMM386.EX_ C:\\DOS\\EMM386.EXE >> C:\\BOOT.LOG\r\n'
        b'EXPAND MEM.EX_ C:\\DOS\\MEM.EXE >> C:\\BOOT.LOG\r\n'
        b'EXPAND SHARE.EX_ C:\\DOS\\SHARE.EXE >> C:\\BOOT.LOG\r\n'
        b'CD \\\r\nECHO === stage1 done === >> C:\\BOOT.LOG\r\n'
        b'C:\\QUIT.COM\r\n'),
    'ems': (
        MEMCFG,
        HEAD +
        b'ECHO === ems === > C:\\BOOT.LOG\r\n'
        b'VER >> C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n'
        b'ECHO === ems done === >> C:\\BOOT.LOG\r\n'
        b'C:\\QUIT.COM\r\n'),
    'uw': (
        MEMCFG,
        HEAD +
        b'ECHO === uw === > C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n'
        b'C:\r\nCD \\UW\r\n'
        b'ECHO --- launching UW.EXE --- >> C:\\BOOT.LOG\r\n'
        b'UW.EXE\r\n'
        b'ECHO --- UW.EXE returned --- >> C:\\BOOT.LOG\r\n'
        b'CD \\\r\n'
        b'C:\\QUIT.COM\r\n'),
    'shell': (MEMCFG, HEAD + b'C:\r\nCD \\UW\r\n'),
}


def mcopy(local, guest):
    env = dict(os.environ, MTOOLS_SKIP_CHECK='1')
    p = subprocess.run([MCOPY, '-o',
                        '-i', f'{HDD}@@{PART_OFF}', local, guest],
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        sys.exit(f'mcopy failed: {p.stdout}{p.stderr}')


def main():
    if not 2 <= len(sys.argv) <= 3 or sys.argv[1] not in MODES:
        sys.exit(f'usage: set_boot_mode.py {{{"|".join(MODES)}}} [image.hdd]')
    mode = sys.argv[1]
    config, autoexec = MODES[mode]
    for name, data in (('CONFIG.SYS', config), ('AUTOEXEC.BAT', autoexec)):
        p = os.path.join(STAGE, name)
        open(p, 'wb').write(data)
        mcopy(p, '::/' + name)
    print(f'{os.path.relpath(HDD, ROOT)} set to mode "{mode}"')
    print('--- CONFIG.SYS ---\n' + config.decode())
    print('--- AUTOEXEC.BAT ---\n' + autoexec.decode())


if __name__ == '__main__':
    main()
