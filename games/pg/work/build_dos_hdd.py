#!/usr/bin/env python3
r"""Build img/panzergeneral.hdd -- bootable MS-DOS 6.22 disk running the game.

    python F030PanzerGeneral/work/build_dos_hdd.py            # build + bootstrap boot
    python F030PanzerGeneral/work/build_dos_hdd.py --no-boot  # build only
    python F030PanzerGeneral/work/build_dos_hdd.py --run-game --no-boot

Seeded by F030Method/dos/sync.py --init F030PanzerGeneral.  The shared half (dosimg.py,
run_qemu.py, mbr.asm, gdbstub_probe.py) is synced from that master and must not
be edited here; this file is the per-game half and is yours.

Layout rules, boot-record invariants and the five things that make the image
actually boot: dosimg.py's module docstring.  Procedure and gotchas: write them
up in this project own qemu-boot.md / DOS-ORACLE.md as you hit them.
"""
import os
import argparse
import hashlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = dosimg.find_project_root(__file__)
WORK = os.path.join(ROOT, 'work', 'img_build')
parser = argparse.ArgumentParser(description=__doc__)
for flag in ('no-boot', 'run-sound', 'run-game', 'hold', 'use-no-sound'):
    parser.add_argument('--' + flag, action='store_true')
mouse_options = parser.add_mutually_exclusive_group()
mouse_options.add_argument('--without-mouse', action='store_true')
mouse_options.add_argument('--mouse-stub', action='store_true',
                           help='diagnostic INT 33h TSR; does not supply mouse input')
parser.add_argument('--out', default=os.path.join(ROOT, 'img', 'panzergeneral.hdd'))
parser.add_argument('--mouse-driver', default=os.path.join(HERE, 'dos_files', 'ctmouse.exe'))
args = parser.parse_args()
OUT = os.path.abspath(args.out)

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
# Per-game diagnostic switches below: `--run-sound` enters SOUND.BAT, `--run-game`
# enters PG.BAT, `--hold` omits QUIT.COM for timeout/screen inspection, and
# `--use-no-sound` replaces SOUND.CFG with the DOS-generated no-sound result
# captured by the sound-installer probe.
#
GAME_TREE = os.path.join(ROOT, 'game')
GUEST_DIR = '/PG'
SIZE_MB = 32

mouse = args.run_game and not (args.without_mouse or args.mouse_stub)
if mouse:
    if not os.path.isfile(args.mouse_driver):
        sys.exit('missing CuteMouse driver; see analysis/executable.md; '
                 '--without-mouse reproduces the diagnostic startup stall')
    with open(args.mouse_driver, 'rb') as stream:
        driver_hash = hashlib.sha256(stream.read()).hexdigest()
    if driver_hash != '822cf550c9e19a22785722d2306aa08ede10ff20bfe931d5a81a15f77c5f363e':
        sys.exit('mouse driver differs from the pinned CuteMouse 2.1b4 binary')

img = dosimg.DosImage(OUT, size_mb=SIZE_MB, work_dir=WORK,
                      label='panzergeneral')
print('game files: %d' % img.add_tree(GUEST_DIR, GAME_TREE))
if args.use_no_sound:
    no_sound_cfg = os.path.join(ROOT, 'work', 'sound-cfg-after-no-sound.bin')
    if not os.path.isfile(no_sound_cfg):
        sys.exit('missing DOS-generated no-sound config; run the sound installer first')
    img.add_file(no_sound_cfg, '/PG/EXE/SOUND.CFG')
img.add_bytes(b'FILES=50\r\nBUFFERS=30\r\n', '/CONFIG.SYS')
then = b''
if args.mouse_stub:
    # PANZER.EXE's init (runtime 0x1B7AEF) issues INT 33h AX=0 and returns
    # without installing its timer ISR unless AX comes back 0xFFFF, so the
    # first Delay never ends without a mouse driver.  This 43-byte TSR hooks
    # INT 33h: fn 0 -> AX=FFFF BX=2, fn 3 -> BX=CX=DX=0, anything else IRET.
    #   jmp init | cmp ax,0 | jne n3 | mov ax,-1 | mov bx,2 | iret
    #   n3: cmp ax,3 | jne d | xor bx,bx | xor cx,cx | xor dx,dx | iret
    #   d: iret | init: mov ax,2533h | mov dx,102h | int 21h
    #   mov dx,14h | mov ax,3100h | int 21h
    img.add_bytes(bytes.fromhex(
        'EB19' '3D0000' '7507' 'B8FFFF' 'BB0200' 'CF' '3D0300' '7507'
        '31DB' '31C9' '31D2' 'CF' 'CF' 'B83325' 'BA0201' 'CD21'
        'BA1400' 'B80031' 'CD21'), '/MOUSE.COM')
    then += b'C:\\MOUSE.COM\r\n'
if mouse:
    img.add_file(args.mouse_driver, '/CTMOUSE.EXE')
    then += b'C:\\CTMOUSE.EXE /P > C:\\MOUSE.LOG\r\n'
then += b'CD \\PG\r\n'
if args.run_sound:
    then += b'CALL SOUND.BAT > C:\\SOUND.LOG\r\n'
if args.run_game:
    then += b'CALL PG.BAT > C:\\PG.LOG\r\n'
if not args.hold:
    then += b'C:\\QUIT.COM\r\n'
img.add_bytes(dosimg.expand_autoexec(then), '/AUTOEXEC.BAT')
# --- end per-game block ------------------------------------------------------

img.write()

if not args.no_boot:
    print('\n--- bootstrap boot (in-guest EXPAND) ---')
    env = dict(os.environ)
    qemu = r'C:\Program Files\qemu\qemu-system-i386.exe'
    if 'QEMU_SYSTEM_I386' not in env and os.path.isfile(qemu):
        env['QEMU_SYSTEM_I386'] = qemu
    rc = subprocess.call([sys.executable, os.path.join(HERE, 'run_qemu.py'),
                          '--hdd', OUT, '--timeout', '120', '--cat', '::/BOOT.LOG'],
                         env=env)
    if rc != 0:
        sys.exit('bootstrap boot failed -- see output above')
