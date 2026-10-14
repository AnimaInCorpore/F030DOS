#!/usr/bin/env python3
"""Boot a DOS oracle image under QEMU with the x86trace plugin attached.

Records which guest bytes executed, then quits QEMU *gracefully* over QMP so
the plugin's atexit callback actually runs -- a killed QEMU writes no sidecar.
Also dumps conventional memory at the end, which is what calibrates guest
linear addresses back to file offsets (see trace_coverage.py).

    python trace/run_trace.py --hdd img/por.hdd --seconds 45 \
        --lo 0 --hi 0xA0000 --out work/por.trace --memdump work/por.ram

Keys are sent as `--key 20:ret` (at t=20 s send Return), matching run_qemu.py.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import dosimg

QEMU = dosimg.host_tool('qemu-system-i386')
# QEMU plugins are .so on macOS/Linux and .dll on Windows (see Makefile).
PLUGIN = os.path.join(HERE, 'x86trace.dll' if sys.platform == 'win32'
                      else 'x86trace.so')


def free_port():
    """An unused QMP port from the OS -- same rule as run_qemu.py: a fixed
    port makes two concurrent runs fight, and the loser looks like a guest
    crash."""
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def stale(*paths):
    """Delete previous runs' artefacts before asking QEMU for new ones, so a
    capture that never arrives cannot be answered by the last run's file."""
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


class Qmp:
    """Minimal QMP client -- same shape as run_qemu.py's, including the rule
    that a dropped socket is a normal outcome (the guest can end the run)."""

    def __init__(self, port):
        self.s = None
        for _ in range(40):
            try:
                self.s = socket.create_connection(('127.0.0.1', port), timeout=2)
                break
            except OSError:
                time.sleep(0.25)
        if self.s is None:
            raise RuntimeError('QMP never came up')
        self.f = self.s.makefile('rw')
        self.f.readline()
        self.cmd({'execute': 'qmp_capabilities'})

    def cmd(self, obj):
        try:
            self.f.write(json.dumps(obj) + '\n')
            self.f.flush()
            while True:
                line = self.f.readline()
                if not line:
                    return None
                m = json.loads(line)
                if 'event' in m:
                    continue
                return m
        except (OSError, ValueError):
            return None

    def hmp(self, line):
        m = self.cmd({'execute': 'human-monitor-command',
                      'arguments': {'command-line': line}})
        return (m or {}).get('return', '')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--hdd', required=True)
    ap.add_argument('--seconds', type=float, default=45.0,
                    help='how long to let the guest run before quitting')
    ap.add_argument('--lo', default='0', help='window start (guest linear)')
    ap.add_argument('--hi', default='0xA0000', help='window end (exclusive)')
    ap.add_argument('--out', required=True, help='telemetry sidecar path')
    ap.add_argument('--memdump', help='pmemsave the window to this path')
    ap.add_argument('--memdump-at', type=float, default=None,
                    help='seconds at which to dump (default: just before the '
                         'end). The guest can end the run by itself, so a dump '
                         'left to the end may never happen.')
    ap.add_argument('--key', action='append', default=[],
                    help='SECONDS:KEY, e.g. 20:ret')
    ap.add_argument('--shot', action='append', default=[], type=float,
                    help='screendump at SECONDS (repeatable)')
    ap.add_argument('--int21log', help='log INT 21h calls here (DOS-level '
                                       'view of overlay loading)')
    ap.add_argument('--int21callers', help='log INT 21h far return addresses '
                                          'to a parallel sidecar')
    ap.add_argument('--io', help='tally of every I/O port the guest touches')
    ap.add_argument('--mem', action='store_true',
                    help='record data-access width and signedness, not just '
                         'execution')
    ap.add_argument('--ovl', help='overlay flush log: coverage of the overlay '
                                  'buffer, split per resident unit')
    ap.add_argument('--ovl-lo', default=None, help='overlay buffer start')
    ap.add_argument('--ovl-hi', default=None, help='overlay buffer end')
    ap.add_argument('--port', type=int, default=0,
                    help='QMP port (default: an unused one from the OS)')
    a = ap.parse_args(argv)

    lo, hi = int(a.lo, 0), int(a.hi, 0)
    if a.ovl:
        if not (a.ovl_lo and a.ovl_hi):
            sys.exit('--ovl needs --ovl-lo and --ovl-hi')
        olo, ohi = int(a.ovl_lo, 0), int(a.ovl_hi, 0)
        # The plugin indexes its flags array with (ovl - lo), so the overlay
        # window must nest inside the coverage window; the plugin enforces
        # the same rule, but fail here with the friendlier message.
        if not (lo <= olo < ohi <= hi):
            sys.exit('--ovl window 0x%x..0x%x must nest inside --lo/--hi '
                     '0x%x..0x%x' % (olo, ohi, lo, hi))
    if not os.path.exists(PLUGIN):
        sys.exit('%s not built -- run make in %s'
                 % (os.path.basename(PLUGIN), HERE))
    for p in (a.out, a.memdump):
        if p:
            os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)

    # keys and screenshots share one timeline, so a shot can be scheduled
    # immediately after the key it is meant to document.  Built (and
    # validated) BEFORE QEMU starts: a malformed --key must not exit with an
    # orphaned QEMU already running.
    events = []
    for k in a.key:
        when, _, key = k.partition(':')
        try:
            t = float(when)
        except ValueError:
            key = ''
        if not key:
            sys.exit('--key wants SECONDS:KEY, e.g. 20:ret; got %r' % k)
        events.append((t, 'key', key))
    # Shots are numbered as well as timestamped: two --shot values in the
    # same integer second must not overwrite each other.
    events += [(t, 'shot', i) for i, t in enumerate(a.shot)]
    if a.memdump:
        # Scheduled, not deferred to the end: START.EXE reaching its copy
        # protection and exiting takes QEMU with it, and a dump that only runs
        # on the timeout path would silently never be written.
        when = a.memdump_at if a.memdump_at is not None else max(0.0, a.seconds - 1.0)
        events.append((when, 'memdump', None))
    events.sort(key=lambda e: e[0])

    geom = a.hdd + '.geom.json'
    dev = ['-device', 'ide-hd,drive=hd0,bus=ide.0']
    if os.path.exists(geom):
        g = json.load(open(geom))
        dev = ['-device', 'ide-hd,drive=hd0,bus=ide.0,cyls=%d,heads=%d,secs=%d'
               % (g['cyls'], g['heads'], g['secs'])]

    port = a.port or free_port()
    # Same guest as run_qemu.py (-M pc, -cpu 486): telemetry must run on the
    # machine the oracle runs on, or a CPUID/instruction-availability branch
    # can diverge between the run being measured and the run being trusted.
    cmd = [QEMU, '-accel', 'tcg', '-M', 'pc', '-cpu', '486', '-m', '16',
           '-drive', 'file=%s,format=raw,if=none,id=hd0'
           % a.hdd.replace(chr(92), '/')] + dev + [
           '-boot', 'c', '-display', 'none', '-no-reboot',
           '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
           '-qmp', 'tcp:127.0.0.1:%d,server=on,wait=off' % port,
           '-plugin', '%s,lo=0x%x,hi=0x%x,out=%s%s%s%s%s%s'
           % (PLUGIN, lo, hi, a.out,
              (',int21log=%s' % a.int21log) if a.int21log else '',
              (',int21callers=%s' % a.int21callers) if a.int21callers else '',
              (',io=%s' % a.io) if a.io else '',
              ',mem=on' if a.mem else '',
              (',ovl=%s,ovl_lo=0x%x,ovl_hi=0x%x'
               % (a.ovl, int(a.ovl_lo, 0), int(a.ovl_hi, 0))) if a.ovl else ''),
           '-d', 'plugin']
    print('+ ' + ' '.join(cmd))
    proc = subprocess.Popen(cmd)

    qmp = Qmp(port)
    t0 = time.time()
    shot_dir = os.path.dirname(os.path.abspath(a.out))
    for when, kind, val in events:
        wait = when - (time.time() - t0)
        if wait > 0:
            time.sleep(wait)
        if proc.poll() is not None:
            break
        if kind == 'key':
            print('  key %-6s @ %5.1fs' % (val, time.time() - t0))
            qmp.hmp('sendkey %s' % val)
        elif kind == 'shot':
            shot = os.path.join(shot_dir,
                                'shot_%02d_t%03d.ppm' % (val, int(when)))
            # Stale-delete first: shot names repeat across runs, and a
            # screendump that never arrives must not be answered by the
            # previous run's picture.
            stale(shot)
            print('  shot         @ %5.1fs -> %s' % (time.time() - t0, shot))
            qmp.hmp('screendump "%s"' % shot.replace(chr(92), '/'))
            for _ in range(20):
                if os.path.exists(shot) and os.path.getsize(shot) > 0:
                    break
                time.sleep(0.1)
            if not os.path.exists(shot):
                print('  WARNING: screendump produced no file')
        else:
            print('  memdump      @ %5.1fs -> %s' % (time.time() - t0, a.memdump))
            qmp.hmp('pmemsave 0x%x %d "%s"'
                    % (lo, hi - lo, a.memdump.replace(chr(92), '/')))
            for _ in range(60):
                if (os.path.exists(a.memdump)
                        and os.path.getsize(a.memdump) == hi - lo):
                    break
                time.sleep(0.25)

    wait = a.seconds - (time.time() - t0)
    if wait > 0 and proc.poll() is None:
        time.sleep(wait)

    if proc.poll() is None:
        # Graceful quit: the plugin writes its sidecar from an atexit callback,
        # so SIGKILL here would silently produce no telemetry at all.
        qmp.hmp('quit')
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        print('WARNING: QEMU had to be killed; sidecar may be missing')

    ok = os.path.exists(a.out) and os.path.getsize(a.out) == hi - lo
    print('sidecar %s: %s' % (a.out, 'ok' if ok else 'MISSING/short'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
