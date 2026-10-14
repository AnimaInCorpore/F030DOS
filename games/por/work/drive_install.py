#!/usr/bin/env python3
r"""Drive Pool of Radiance's real INSTALL.EXE to completion, reacting to what
is on screen instead of to a stopwatch.

The dynamic oracle for POOL.CFG (AGENTS.md Next steps §8): INSTALL.EXE is the
only program that writes POOL.CFG, so the format is recovered by running the
original installer and reading the file it produces.

work/probe_install2.py drives the same install from a fixed time schedule,
which cannot survive the copy phase: PKUNPAK asks for a specific disk, and how
long each extraction takes is not knowable in advance. This driver polls the
VGA text plane (run_qemu.dump_text_screen) and answers each prompt as it
appears, swapping the floppy QEMU has in drive A: to whichever disk the
installer just asked for.

    python work/drive_install.py [--timeout 900] [--hard-disk | --floppy]

The guest only ever sees scratch copies of game/POR/*.img -- those are the
tracked pristine reference and INSTALL.EXE writes to its disks.
"""
import argparse
import os
import re
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


def scratch(name, src):
    dst = os.path.join(STAGE, name)
    if not os.path.exists(dst) or os.path.getmtime(dst) < os.path.getmtime(src):
        os.makedirs(STAGE, exist_ok=True)
        shutil.copyfile(src, dst)
    return dst


DISK1 = scratch('install_disk1.img', os.path.join(ROOT, 'game', 'POR', 'disk1.img'))
DISK2 = scratch('install_disk2.img', os.path.join(ROOT, 'game', 'POR', 'disk2.img'))

# Which physical disk carries which archive, from the ARC directories:
#   disk1.img = SSI MASTER DISK  (DISKA.ARC, DISKB.ARC, SAVE.ARC, INSTALL.EXE)
#   disk2.img = SSI MASTER DISK B (DISKC.ARC)
ARC_DISK = {'DISKA.ARC': DISK1, 'DISKB.ARC': DISK1, 'SAVE.ARC': DISK1,
            'DISKC.ARC': DISK2}


class Driver:
    def __init__(self, qmp, verbose=True):
        self.qmp, self.verbose = qmp, verbose
        self.in_a = DISK1
        self.seq = 0

    def log(self, msg):
        if self.verbose:
            print(f'  {msg}', flush=True)

    def screen(self):
        self.seq += 1
        return rq.dump_text_screen(self.qmp, f'drv{self.seq:03d}')

    def key(self, k):
        r = self.qmp.hmp(f'sendkey {k}')
        if r and r.strip():
            self.log(f'sendkey {k} -> {r.strip()!r}')

    def insert(self, img):
        if self.in_a == img:
            return False
        r = self.qmp.hmp(f'change floppy0 "{img.replace(chr(92), "/")}"')
        self.in_a = img
        self.log(f'drive A: <- {os.path.basename(img)}'
                 + (f' -> {r.strip()!r}' if r and r.strip() else ''))
        return True


# Option order as printed on the form, left to right.
DISPLAY = ['cga', 'ega', 'tandy16']
SOUND = ['pc', 'tandy', 'silent']


def form_keys(drv, hard_disk, display='ega', sound='pc', full_intro=False,
              save_disk=False):
    """Fill the settings form. Each row is driven by clamping the cursor to the
    leftmost option (Left repeats past the end are ignored) and then stepping
    Right, so no assumption is made about where the cursor starts.

    Row order and option order are read off the screen itself, see
    analysis/dos-oracle.md."""
    def row(lefts, rights=0, then_down=True):
        for _ in range(lefts):
            drv.key('left'); time.sleep(0.12)
        for _ in range(rights):
            drv.key('right'); time.sleep(0.12)
        if then_down:
            drv.key('down'); time.sleep(0.12)

    row(3, DISPLAY.index(display))  # Display Type
    row(3, SOUND.index(sound))      # Sound Type
    row(2, 1)                       # Floppy A      -> 3.5"
    row(3, 2)                       # Floppy B      -> None
    row(2, 0)                       # Master Drive  -> A:
    row(5, 0 if hard_disk else 4)   # Hard Disk     -> C:  /  None
    row(2, 0 if save_disk else 1)   # Save Disk
    row(2, 0 if full_intro else 1)  # Full Intro
    row(2, 0, then_down=False)      # Finished      -> Yes
    time.sleep(1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=float, default=900)
    ap.add_argument('--display', choices=DISPLAY, default='ega')
    ap.add_argument('--sound', choices=SOUND, default='pc')
    ap.add_argument('--full-intro', action='store_true')
    ap.add_argument('--save-disk', action='store_true',
                    help="Save Disk = Make One (writes the save disk in B:)")
    ap.add_argument('--floppy', action='store_true',
                    help='configure a floppy install (Hard Disk = None) '
                         'instead of installing to C:')
    args = ap.parse_args()
    hard_disk = not args.floppy

    cyls, heads, secs, part_off = rq.geometry(HDD)
    port = rq.free_port()
    cmd = [rq.QEMU, '-M', 'pc', '-cpu', '486', '-m', '16',
           '-drive', f'file={HDD.replace(chr(92), "/")},format=raw,if=none,'
                     f'id=hd0,cache=writeback',
           '-device', f'ide-hd,drive=hd0,bus=ide.0,unit=0,'
                      f'cyls={cyls},heads={heads},secs={secs}',
           '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
           '-qmp', f'tcp:127.0.0.1:{port},server=on,wait=off',
           '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
           '-drive', f'file={DISK1.replace(chr(92), "/")},format=raw,if=floppy,index=0',
           '-drive', f'file={os.path.join(STAGE, "blank_startup.img").replace(chr(92), "/")},'
                     f'format=raw,if=floppy,index=1']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    qmp = rq.Qmp(port)
    drv = Driver(qmp)

    t0 = time.time()
    stage = 'boot'
    last = ''
    idle = 0
    while time.time() - t0 < args.timeout:
        if proc.poll() is not None:
            print(f'--- QEMU exited rc={proc.returncode} ---')
            break
        scr = drv.screen()
        now = time.time() - t0
        if scr != last:
            idle = 0
            tail = [l for l in scr.splitlines() if l.strip()][-2:]
            print(f'[{now:6.1f}s] {stage}: ' + ' | '.join(tail), flush=True)
        else:
            idle += 1
        last = scr

        if stage == 'boot' and 'Installation Utility' in scr:
            stage = 'form'
            print(f'[{now:6.1f}s] form is up -- filling it in', flush=True)
            form_keys(drv, hard_disk, args.display, args.sound,
                      args.full_intro, args.save_disk)
            continue

        if stage == 'form' and 'Begin Full Installation' in scr:
            stage = 'menu'
            drv.key('down'); time.sleep(0.3)      # -> Begin Full Installation
            drv.key('ret')
            print(f'[{now:6.1f}s] chose Begin Full Installation', flush=True)
            time.sleep(1.0)
            continue

        # --- copy phase: answer whatever disk the installer asks for ---
        m = re.search(r"Can't find:\s*A:(\S+)", scr)
        if m and m.group(1) in ARC_DISK:
            drv.insert(ARC_DISK[m.group(1)])
            time.sleep(0.5); drv.key('ret'); time.sleep(1.0)
            continue

        if 'press a key' in scr or 'Press <Return>' in scr:
            # Try the disk already in the drive first; if PKUNPAK then says it
            # cannot find the archive, the handler above swaps and retries.
            drv.key('ret'); time.sleep(1.5)
            if drv.screen() == scr:            # prompt did not clear
                other = DISK2 if drv.in_a == DISK1 else DISK1
                drv.insert(other); time.sleep(0.5)
                drv.key('ret'); time.sleep(1.5)
            continue

        if 'Installation complete' in scr:
            print(f'[{now:6.1f}s] installation complete')
            time.sleep(1.0)
            break

        if idle > 25:
            print(f'[{now:6.1f}s] screen idle -- stopping')
            break
        time.sleep(1.0)

    print('--- final screen ---')
    print(drv.screen())
    try:
        qmp.hmp('quit'); time.sleep(1); proc.kill()
    except Exception:
        pass
    qmp.close()


if __name__ == '__main__':
    main()
