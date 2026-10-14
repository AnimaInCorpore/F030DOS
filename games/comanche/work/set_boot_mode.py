#!/usr/bin/env python3
r"""Rewrite CONFIG.SYS / AUTOEXEC.BAT inside img/comanche.hdd without rebuilding.

A full build_dos_hdd.py run recopies 7.3 MB of game data; swapping the two boot
files in place with mtools takes under a second, so iterate with this.

Modes:
  bootstrap  no memory manager; expand HIMEM/EMM386/... from the KWAJ `.??_`
             archives with the genuine EXPAND.EXE, then QUIT.COM.  Run once
             after a rebuild -- CONFIG.XMS wants C:\DOS\HIMEM.SYS to exist.
  xms        the game's own shipped config (CONFIG.XMS: HIMEM, DOS=HIGH,
             BUFFERS=30, FILES=30); report MEM /C and the game directory; QUIT.
  comanche   xms + launch C:\COMANCHE\COMANCHE.EXE, the way C.BAT does.  Does
             NOT quit -- the game owns the screen, so end the run with
             run_qemu.py --timeout and read the screenshots it captures.
  shell      xms, then drop to COMMAND.COM (interactive poking with a display).

The memory config is not a choice: BOOTXMS.BAT copies CONFIG.XMS/AUTOEXEC.XMS
onto a boot floppy, so those two files *are* what the game shipped as its
runtime.  `EMMXXXX0` appears once in the unpacked COMANCHE.EXE, so the program
can detect EMS -- but nothing shipped provides it.  If a run needs EMM386, that
is a finding to record with its evidence, not a knob to turn first.

Usage: python work/set_boot_mode.py <mode>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = dosimg.find_project_root(__file__)
HDD = os.path.join(ROOT, 'img', 'comanche.hdd')
PART_OFF = json.load(open(HDD + '.geom.json'))['part_offset']

# Verbatim from assets/extracted/comanche_hdd/CONFIG.XMS.
XMSCFG = (b'DEVICE=C:\\DOS\\HIMEM.SYS\r\n'
          b'DOS=HIGH\r\n'
          b'BUFFERS=30\r\n'
          b'FILES=30\r\n')

HEAD = b'@ECHO OFF\r\nPROMPT $P$G\r\nPATH C:\\DOS\r\n'

MODES = {
    'bootstrap': (b'FILES=30\r\nBUFFERS=20\r\n', dosimg.expand_autoexec()),
    'xms': (
        XMSCFG,
        HEAD +
        b'ECHO === xms === > C:\\BOOT.LOG\r\n'
        b'VER >> C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n'
        b'DIR C:\\COMANCHE >> C:\\BOOT.LOG\r\n'
        b'ECHO === xms done === >> C:\\BOOT.LOG\r\n'
        b'C:\\QUIT.COM\r\n'),
    'comanche': (
        XMSCFG,
        HEAD +
        b'ECHO === comanche === > C:\\BOOT.LOG\r\n'
        b'C:\\DOS\\MEM.EXE /C >> C:\\BOOT.LOG\r\n'
        b'C:\r\nCD \\COMANCHE\r\n'
        b'ECHO --- launching COMANCHE.EXE --- >> C:\\BOOT.LOG\r\n'
        b'COMANCHE.EXE\r\n'
        b'ECHO --- COMANCHE.EXE returned --- >> C:\\BOOT.LOG\r\n'
        b'C:\\QUIT.COM\r\n'),
    'shell': (XMSCFG, HEAD + b'C:\r\nCD \\COMANCHE\r\n'),
}


def put(data, guest):
    tmp = os.path.join(ROOT, 'work', 'img_build', os.path.basename(guest))
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    open(tmp, 'wb').write(data)
    subprocess.run([dosimg.host_tool('mcopy'), '-o', '-i',
                    f'{HDD}@@{PART_OFF}', tmp, guest],
                   check=True, env=dict(os.environ, MTOOLS_SKIP_CHECK='1'))


def main(argv):
    if len(argv) != 1 or argv[0] not in MODES:
        sys.exit('usage: set_boot_mode.py <%s>' % '|'.join(MODES))
    config, autoexec = MODES[argv[0]]
    put(config, '::/CONFIG.SYS')
    put(autoexec, '::/AUTOEXEC.BAT')
    print('boot mode: %s' % argv[0])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
