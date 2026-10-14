#!/usr/bin/env python3
r"""Read the MZ-side selector table, and `[0x587C]` in particular, out of the
guest.

`analysis/executable.md` measures the `10049` failure down to one word: the
extender loads `DS` from `CS:0x3F8`, that word is a mirror of MZ-side
`[0x587C]`, it should hold `0x0010`, and it held `0xFF50` at the fault.  The
document's first next measurement is to read `[0x587C]` itself -- if the source
is already wrong, the publish path is innocent and the DPMI mode-switch return
at file `0x2884` is the lead; if it is right, the corruption is below the
publish sites and a write watchpoint on linear `0xC2A3F8` is the next step.

`[0x587C]` is DS-relative and the MZ data segment is not known ahead of the
run, so the address is *measured*, not assumed.  The init block at file
`0x27C7F..0x27CCA` writes twelve known constants into `[0x5878..0x588F]`:

    [0x5878]=0x0008 [0x587A]=0x0018 [0x587C]=0x0010 [0x587E]=0x0060
    [0x5880]=0x0048 [0x5882]=0x0118 [0x5884]=0x0090 [0x5886]=0x0098
    [0x5888]=0x0130 [0x588A]=0x0138 [0x588C]=0x0110 [0x588E]=0x00C8

Eleven of them anchor the table in a RAM dump; the twelfth -- `[0x587C]`, the
word under test -- is a two-byte hole in the pattern, so the search cannot
assume the answer it is asked to measure.  None of those bytes exist in
`LCD.EXE` on disk (the block writes them at runtime), so a hit is a runtime
fact and not a copy of the file.

Each capture stops the CPU first: the RAM dump, the register dump and the
screen then describe one instant, and the screen says which phase that instant
belongs to instead of leaving it to the wall clock.

    python work/read_mz_selector_table.py --at 20 --at 26
    python work/read_mz_selector_table.py --at 20 --key 22:y --at 30 --at 40
"""
import argparse
import os
import re
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg
import run_qemu                      # Qmp, geometry, screendump, stale, OUTDIR

QEMU = dosimg.host_tool('qemu-system-i386')
ROOT = dosimg.find_project_root(__file__)
OUTDIR = run_qemu.OUTDIR

# (offset, value) of the init block at file 0x27C7F..0x27CCA.  None marks the
# word under test: it is matched as a wildcard, never as a constant.
TABLE = [(0x5878, 0x0008), (0x587A, 0x0018), (0x587C, None), (0x587E, 0x0060),
         (0x5880, 0x0048), (0x5882, 0x0118), (0x5884, 0x0090), (0x5886, 0x0098),
         (0x5888, 0x0130), (0x588A, 0x0138), (0x588C, 0x0110), (0x588E, 0x00C8)]
TABLE_BASE = TABLE[0][0]
UNDER_TEST = 0x587C                  # mirrored to the extender's CS:0x3F8
PAIRED = 0x57EC                      # mirrored to CS:0x3FA (0x29D88 writer)


def anchor_re():
    """The eleven known words as a byte pattern with the word under test as a
    two-byte hole."""
    out = b''
    for _off, val in TABLE:
        out += b'..' if val is None else re.escape(struct.pack('<H', val))
    return re.compile(out, re.S)


def probe_dump(path):
    """Every place the selector table is resident, with what it holds."""
    ram = open(path, 'rb').read()
    hits = []
    for m in anchor_re().finditer(ram):
        base = m.start() - 0  # pattern starts at TABLE_BASE
        ds_lin = base - TABLE_BASE
        word = lambda off: struct.unpack_from('<H', ram, ds_lin + off)[0]
        hits.append({
            'table_lin': base,
            'ds_linear': ds_lin,
            'ds_para': ds_lin >> 4 if ds_lin % 16 == 0 else None,
            'under_test': word(UNDER_TEST),
            'paired': word(PAIRED) if 0 <= ds_lin + PAIRED < len(ram) - 1 else None,
            'window': ram[ds_lin + TABLE_BASE: ds_lin + TABLE_BASE + 24],
        })
    return hits, ram


def load_base(ram, exe_load):
    """Where the MZ load module sits, by the same signature vote the rest of
    the harness uses: several distinctive windows must agree on one delta."""
    votes = {}
    step = max(0x400, len(exe_load) // 64)
    for off in range(0, len(exe_load) - 16, step):
        win = exe_load[off:off + 16]
        if len(set(win)) < 6:                       # not distinctive enough
            continue
        pos = ram.find(win)
        if pos >= 0 and ram.find(win, pos + 1) < 0:  # unique in RAM too
            votes[pos - off] = votes.get(pos - off, 0) + 1
    if not votes:
        return None, {}
    best = max(votes.items(), key=lambda kv: kv[1])
    return best[0], votes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hdd', default=run_qemu.HDD)
    ap.add_argument('--at', action='append', default=[], type=float,
                    metavar='SEC', help='stop and capture at SEC seconds')
    ap.add_argument('--key', action='append', default=[], metavar='SEC:KEY',
                    help='QMP sendkey at SEC seconds, e.g. 22:y')
    ap.add_argument('--timeout', type=float, default=0,
                    help='seconds to run (default: last event + 5)')
    ap.add_argument('--mem', default='16')
    ap.add_argument('--cpu', default='486')
    ap.add_argument('--load', default=os.path.join(ROOT, 'work', 'listings',
                                                   'LCD.load'),
                    help='MZ load image, for the independent base vote')
    args = ap.parse_args()

    schedule = [(t, 'cap', None) for t in args.at]
    for spec in args.key:
        when, _, key = spec.partition(':')
        if not key:
            sys.exit(f'--key wants SEC:KEY, got {spec!r}')
        schedule.append((float(when), 'key', key))
    if not schedule:
        sys.exit('nothing to do: pass at least one --at SEC')
    schedule.sort()
    timeout = args.timeout or schedule[-1][0] + 5

    os.makedirs(OUTDIR, exist_ok=True)
    qmp_port = run_qemu.free_port()
    cyls, heads, secs, _off = run_qemu.geometry(args.hdd)
    cmd = [QEMU, '-M', 'pc', '-cpu', args.cpu, '-m', args.mem,
           '-drive', f'file={args.hdd},format=raw,if=none,id=hd0,'
                     f'cache=writeback',
           '-device', f'ide-hd,drive=hd0,bus=ide.0,unit=0,'
                      f'cyls={cyls},heads={heads},secs={secs}',
           '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
           '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
           '-qmp', f'tcp:127.0.0.1:{qmp_port},server=on,wait=off']
    print('$', ' '.join(cmd), '\n')
    qemu_log = os.path.join(OUTDIR, 'seltab_qemu_stdout.log')
    run_qemu.stale(qemu_log)
    log_fh = open(qemu_log, 'wb')
    proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT)
    qmp = run_qemu.Qmp(qmp_port)

    exe_load = open(args.load, 'rb').read() if os.path.exists(args.load) else b''
    captures = []
    cap_n = [0]

    def capture(tag, now):
        """One instant: CPU stopped, then screen + registers + RAM."""
        ram_path = os.path.join(OUTDIR, f'seltab_{tag}.ram')
        run_qemu.stale(ram_path)
        qmp.hmp('stop')
        text = run_qemu.dump_text_screen(qmp, f'seltab_{tag}')
        shot = run_qemu.screendump(qmp, f'seltab_{tag}')
        regs = qmp.hmp('info registers')
        qmp.hmp(f'pmemsave 0 0xA0000 "{ram_path}"')
        for _ in range(100):
            if os.path.exists(ram_path) and os.path.getsize(ram_path) == 0xA0000:
                break
            time.sleep(0.1)
        qmp.hmp('cont')
        if not os.path.exists(ram_path):
            print(f'  [{now:5.1f}s] {tag}: NO RAM DUMP')
            return
        hits, ram = probe_dump(ram_path)
        base, votes = load_base(ram, exe_load) if exe_load else (None, {})
        captures.append((tag, now, hits, base, regs, text, shot))
        print(f'\n===== capture {tag} at {now:.1f}s =====')
        print('--- VGA text plane ---')
        print(text)
        print('--- registers ---')
        print(regs.strip())
        if base is not None:
            print(f'MZ load image base (signature vote): {base:#x} '
                  f'-> load segment {base >> 4:#x}, file skew '
                  f'{base - 0x1400:#x}; votes {dict(sorted(votes.items(), key=lambda kv: -kv[1])[:3])}')
        else:
            print('MZ load image: not located in conventional RAM')
        if not hits:
            print('selector table: NOT RESIDENT (init block has not run, or '
                  'the segment is gone)')
        for h in hits:
            ds = f'{h["ds_para"]:#06x}' if h['ds_para'] is not None else \
                 f'(not paragraph-aligned, linear {h["ds_linear"]:#x})'
            print(f'selector table at linear {h["table_lin"]:#x} '
                  f'-> DS {ds}, DS linear {h["ds_linear"]:#x}')
            print(f'  [{UNDER_TEST:#06x}] = {h["under_test"]:#06x}   '
                  f'(expected 0x0010; the word mirrored to CS:0x3F8)')
            paired = (f'{h["paired"]:#06x}' if h['paired'] is not None
                      else '<outside dump>')
            print(f'  [{PAIRED:#06x}] = {paired}   '
                  f'(the word mirrored to CS:0x3FA)')
            print(f'  {TABLE_BASE:#06x}: ' + h['window'].hex(' ', 2))
            if base is not None:
                print(f'  DS - load segment = '
                      f'{(h["ds_linear"] - base) >> 4:#06x} paragraphs')
        print(f'screen: {shot}   ram: {ram_path}')

    t0 = time.time()
    pending = list(schedule)
    rc = None
    while time.time() - t0 < timeout:
        rc = proc.poll()
        if rc is not None:
            break
        now = time.time() - t0
        while pending and pending[0][0] <= now:
            _, kind, payload = pending.pop(0)
            if kind == 'key':
                qmp.hmp(f'sendkey {payload}')
                print(f'  [{now:5.1f}s] sendkey {payload}')
            else:
                cap_n[0] += 1
                capture(f'c{cap_n[0]}_t{now:.0f}', now)
        time.sleep(0.1)

    if rc is None:
        print(f'\n--- ran to {timeout:.0f}s; stopping ---')
        qmp.hmp('quit')
        time.sleep(1)
        proc.kill()
    else:
        print(f'\n--- QEMU exited rc={rc} '
              f'({"clean QUIT.COM" if rc == run_qemu.CLEAN_EXIT else "UNEXPECTED"})'
              f' after {time.time() - t0:.1f}s ---')
    qmp.close()
    log_fh.close()
    out = open(qemu_log, encoding='utf-8', errors='replace').read()
    if out.strip():
        print('--- qemu stdout ---\n' + out)

    print('\n===== summary =====')
    for tag, now, hits, base, _regs, _text, _shot in captures:
        vals = ', '.join(f'{h["under_test"]:#06x} @ DS linear {h["ds_linear"]:#x}'
                         for h in hits) or 'table not resident'
        print(f'{tag} ({now:.1f}s): [{UNDER_TEST:#06x}] = {vals}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
