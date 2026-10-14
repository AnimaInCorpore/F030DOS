#!/usr/bin/env python3
r"""One-off driver for INSTALL.EXE's two-floppy-drive copy phase (A: source,
B: blank target), which work/run_qemu.py's single-floppy CLI can't express.
Not part of the shared dos-oracle harness -- reuses its Qmp/screendump/mtool
helpers by importing run_qemu.py as a module.

Usage: python work/probe_install2.py <timeout> "<schedule literal>"
Schedule entries: (time, 'key'|'shot'|'changeA'|'changeB'|'info', payload)
"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_qemu as rq

ROOT = os.path.dirname(HERE)
HDD = os.path.join(ROOT, 'img', 'por.hdd')
STAGE = os.path.join(HERE, 'img_build')

# INSTALL.EXE writes to its own disks (POOL.CFG, and it may mark a disk as
# installed), and QEMU attaches floppies read-write.  game/POR/*.img are the
# tracked pristine reference -- AGENTS.md "Keep pristine" -- so they are never
# handed to the guest directly.  The guest gets scratch copies under work/,
# which is derived and regenerable.
def scratch(name, src):
    dst = os.path.join(STAGE, name)
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
        os.makedirs(STAGE, exist_ok=True)
        shutil.copyfile(src, dst)
    return dst


PRISTINE_A = os.path.join(ROOT, 'game', 'POR', 'disk1.img')
PRISTINE_B = os.path.join(ROOT, 'game', 'POR', 'disk2.img')
FLOPPY_A = scratch('install_disk1.img', PRISTINE_A)
FLOPPY_DISK2 = scratch('install_disk2.img', PRISTINE_B)
FLOPPY_B = os.path.join(STAGE, 'blank_startup.img')

TIMEOUT = float(sys.argv[1]) if len(sys.argv) > 1 else 60
SCHEDULE = eval(sys.argv[2]) if len(sys.argv) > 2 else []


def main():
    cyls, heads, secs, part_off = rq.geometry(HDD)
    qmp_port = rq.free_port()
    drive = f'file={HDD.replace(chr(92), "/")},format=raw,if=none,id=hd0,cache=writeback'
    cmd = [rq.QEMU, '-M', 'pc', '-cpu', '486', '-m', '16',
           '-drive', drive,
           '-device', f'ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={cyls},heads={heads},secs={secs}',
           '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
           '-qmp', f'tcp:127.0.0.1:{qmp_port},server=on,wait=off',
           '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
           '-drive', f'file={FLOPPY_A.replace(chr(92), "/")},format=raw,if=floppy,index=0',
           '-drive', f'file={FLOPPY_B.replace(chr(92), "/")},format=raw,if=floppy,index=1']
    print('$', ' '.join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    qmp = rq.Qmp(qmp_port)
    print('info block:', qmp.hmp('info block'))

    t0 = time.time()
    pending = sorted(SCHEDULE)
    while time.time() - t0 < TIMEOUT:
        rc = proc.poll()
        if rc is not None:
            break
        now = time.time() - t0
        while pending and pending[0][0] <= now:
            _, action, payload = pending.pop(0)
            if action == 'key':
                qmp.hmp(f'sendkey {payload}')
                print(f'  [{now:5.1f}s] sendkey {payload}')
            elif action == 'shot':
                print(f'  [{now:5.1f}s] screenshot:', rq.screendump(qmp, f't{int(now)}'))
            elif action == 'changeA':
                r = qmp.hmp(f'change floppy0 "{payload.replace(chr(92), "/")}"')
                print(f'  [{now:5.1f}s] change A -> {payload}: {r}')
            elif action == 'changeB':
                r = qmp.hmp(f'change floppy1 "{payload.replace(chr(92), "/")}"')
                print(f'  [{now:5.1f}s] change B -> {payload}: {r}')
            elif action == 'info':
                print(f'  [{now:5.1f}s] info block:', qmp.hmp('info block'))
        time.sleep(0.2)

    rc = proc.poll()
    if rc is None:
        print(f'--- TIMEOUT after {TIMEOUT}s ---')
        print('screenshot:', rq.screendump(qmp, 'timeout'))
        qmp.hmp('quit')
        time.sleep(1)
        proc.kill()
    else:
        print(f'--- QEMU exited rc={rc} ---')
    qmp.close()
    out = proc.stdout.read()
    if out.strip():
        print('--- qemu stdout ---\n' + out)


if __name__ == '__main__':
    main()
