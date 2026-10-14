#!/usr/bin/env python3
"""Drive the running DOS oracle: mouse, keyboard, screenshots, breakpoints.

`analysis/qemu-boot.md` mapped UW2's character-creation flow by hand over QMP
and noted the fiddly part -- "verify cursor-vs-button-rectangle with a pixel
ruler before clicking rather than eyeballing". This keeps that work: QEMU is
launched once and left running, and every later invocation attaches to the
same QMP socket, so a sequence can be built up and checked a step at a time.

  python work/drive.py start                 # launch, detached, and wait
  python work/drive.py shot menu             # -> work/qemu_out/drive_menu.png
  python work/drive.py move 0 30             # relative, 30 ~ one menu line
  python work/drive.py click
  python work/drive.py key m
  python work/drive.py text Avatar
  python work/drive.py stop

Scale, from qemu-boot.md: at the main menu `move 0 30` advances the crosshair
exactly one entry and `move 30 0` moves it right within a line.
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdbstub_probe as P            # noqa: E402

QMP_PORT = 4444
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qemu_out')
PIDFILE = os.path.join(OUT, 'drive.pid')


def qmp():
    return P.Qmp(QMP_PORT)


def start(wait):
    os.makedirs(OUT, exist_ok=True)
    P.kill_strays()
    hdd = P.default_hdd()
    cyls, heads, secs, _ = P.geometry(hdd)
    cmd = [P.QEMU, '-M', 'pc', '-cpu', '486', '-m', '16',
           '-drive', f'file={hdd},format=raw,if=none,id=hd0,cache=writeback',
           '-device', f'ide-hd,drive=hd0,bus=ide.0,unit=0,'
                      f'cyls={cyls},heads={heads},secs={secs}',
           '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
           '-qmp', f'tcp:127.0.0.1:{QMP_PORT},server=on,wait=off']
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    open(PIDFILE, 'w').write(str(p.pid))
    print(f'qemu pid {p.pid}, waiting {wait}s')
    time.sleep(wait)
    print('ready' if p.poll() is None else 'QEMU DIED')


def shot(tag):
    q = qmp()
    ppm = os.path.join(OUT, f'drive_{tag}.ppm')
    png = os.path.join(OUT, f'drive_{tag}.png')
    for f in (ppm, png):
        if os.path.exists(f):
            os.remove(f)
    q._cmd({'execute': 'screendump', 'arguments': {'filename': ppm}})
    time.sleep(1.2)
    if not os.path.exists(ppm):
        sys.exit('no screendump produced')
    subprocess.run([P.FFMPEG, '-y', '-loglevel', 'error', '-i', ppm,
                    '-vf', 'scale=iw*2:ih*2:flags=neighbor', png],
                   check=True)
    os.remove(ppm)
    print(png)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'start':
        return start(int(args[0]) if args else 65)
    if cmd == 'stop':
        if os.path.exists(PIDFILE):
            try:
                os.kill(int(open(PIDFILE).read()), 9)
            except (ProcessLookupError, ValueError):
                pass
            os.remove(PIDFILE)
        P.kill_strays()
        return print('stopped')
    if cmd == 'shot':
        return shot(args[0] if args else 'now')
    q = qmp()
    if cmd == 'move':
        print(q.hmp(f'mouse_move {int(args[0])} {int(args[1])}').strip() or 'ok')
    elif cmd == 'click':
        # UW2 samples INT 33h AX=3 infrequently enough that a short press is
        # missed entirely -- 0.25 s never registers, 1.5 s always does.
        hold = float(args[0]) if args else 1.5
        q.hmp('mouse_button 1')
        time.sleep(hold)
        q.hmp('mouse_button 0')
        time.sleep(0.6)
        print(f'click (held {hold}s)')
    elif cmd == 'key':
        for k in args:
            q._cmd({'execute': 'send-key',
                    'arguments': {'keys': [{'type': 'qcode', 'data': k}]}})
            time.sleep(0.2)
        print('keys', args)
    elif cmd == 'text':
        for ch in args[0]:
            k = ch.lower() if ch.isalpha() else {'.': 'dot', ' ': 'spc'}.get(ch, ch)
            q._cmd({'execute': 'send-key',
                    'arguments': {'keys': [{'type': 'qcode', 'data': k}]}})
            time.sleep(0.15)
        print('typed', args[0])
    elif cmd == 'regs':
        print(q.hmp('info registers'))
    else:
        sys.exit(f'unknown command {cmd}')


if __name__ == '__main__':
    main()
