#!/usr/bin/env python3
r"""Rewrite CONFIG.SYS / AUTOEXEC.BAT inside img/por.hdd without rebuilding it.

Modes:
  stage1   no memory managers; expand HIMEM/EMM386/MEM/SHARE from the .??_
           KWAJ archives with the genuine EXPAND.EXE, then QUIT.COM.
  shell    plain CONFIG.SYS, drop to a C:\> prompt (interactive poking).
  install  plain CONFIG.SYS, run A:\INSTALL.EXE directly (the floppy is
           attached separately via run_qemu.py --floppy). Does NOT quit:
           the installer owns the screen, so end the run with --timeout
           and drive it with --key/--shot.

Usage: python work/set_boot_mode.py <mode>
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# mtools is located the same way the shared harness locates it -- $MCOPY /
# $DOS_TOOLS / $PATH / the Windows MSYS2 prefix.  See dosimg.host_tool().
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg
# optional 2nd argument selects a different image
HDD = (os.path.join(ROOT, sys.argv[2]) if len(sys.argv) > 2
       else os.path.join(ROOT, 'img', 'por.hdd'))
STAGE = os.path.join(ROOT, 'work', 'img_build')
PART_OFF = json.load(open(HDD + '.geom.json'))['part_offset']

PLAIN = b'FILES=30\r\nBUFFERS=20\r\n'
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
    'shell': (PLAIN, HEAD + b'C:\r\n'),
    'install': (PLAIN, HEAD + b'A:\r\nINSTALL.EXE\r\n'),
}


def mcopy(local, guest):
    env = dict(os.environ, MTOOLS_SKIP_CHECK='1')
    p = subprocess.run([dosimg.host_tool('mcopy'), '-o',
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
