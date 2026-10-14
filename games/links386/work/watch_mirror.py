#!/usr/bin/env python3
r"""Find who writes the extender's `CS:0x3F8` mirror, with a QEMU watchpoint.

`analysis/executable.md` measures the `10049` failure to one word: the
extender's `0xC2C136` loads `DS` from `cs:[0x3F8]`, the word held `0xFF50`, and
the MZ-side source `[0x587C]` is measured correct at the gate and after the
fatal return (`work/read_mz_selector_table.py`).  So the wrong value is written
below the publish sites, inside a window one ring-0 entry wide -- which no
timed capture can be inside.  Only a watchpoint can.

This boots the oracle image with the gdbstub and QMP both attached, arms `Z2`
write watchpoints and `Z0` breakpoints on linear addresses, drives the
mouse/keyboard gate over QMP, and records every hit: the PC read back through
QMP (the stub reports *that* it stopped, not *where*), the guest mode, and the
watched words before and after.

    python work/watch_mirror.py --watch 0xC2A3F8:2 --break 0xC2C136 \
        --key-on-prompt y --timeout 90

Addresses are **linear**, which is what QEMU's x86 TLB sees: segment base
folded in, paging not yet applied.  A watchpoint therefore catches a write
through any selector that lands on the address, which is the point -- the
suspected writer reaches the slot through a descriptor that is only live
between interrupts.  It does not catch a write to a different linear address
that paging maps onto the same physical page.
"""
import argparse
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg
import run_qemu
import rsp as rsp_mod

QEMU = dosimg.host_tool('qemu-system-i386')
ROOT = dosimg.find_project_root(__file__)
OUTDIR = run_qemu.OUTDIR
PROMPT = 'wish to continue using keyboard equivalents'


def parse_addr(spec, default_len):
    addr, _, ln = spec.partition(':')
    return int(addr, 0), int(ln, 0) if ln else default_len


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hdd', default=run_qemu.HDD)
    ap.add_argument('--watch', action='append', default=[], metavar='ADDR[:LEN]',
                    help='linear address to trap on write (default LEN 2)')
    ap.add_argument('--rwatch', action='append', default=[],
                    metavar='ADDR[:LEN]',
                    help='linear address to trap on *read* (Z3). Positively '
                         'identifies the effective address an instruction '
                         'dereferences, which no register dump shows.')
    ap.add_argument('--break', dest='brk', action='append', default=[],
                    metavar='ADDR', help='linear address to trap on execute')
    ap.add_argument('--read', action='append', default=[], metavar='ADDR[:LEN]',
                    help='extra linear word to read back at every hit')
    ap.add_argument('--key-on-prompt', default='',
                    help="sendkey once the mouse/keyboard gate is on screen")
    ap.add_argument('--arm-on-prompt', action='store_true',
                    help='arm only when the gate is on screen, just before '
                         'the key. An address that runs hundreds of times '
                         'during startup and once more in the failing window '
                         'is only readable this way.')
    ap.add_argument('--max-hits', type=int, default=60)
    ap.add_argument('--timeout', type=float, default=120)
    ap.add_argument('--arm-at', type=float, default=0.0,
                    help='wall-clock seconds to run before arming (the '
                         'address need not be mapped yet, but an early arm '
                         'catches load-time writes too)')
    ap.add_argument('--pagewalk', type=lambda v: int(v, 0), default=0,
                    metavar='LINEAR',
                    help='at every hit, walk CR3 by hand for this linear '
                         'address and print PDE/PTE and the frame it lands '
                         'on. A debug read follows the *current* tables; the '
                         'CPU follows its TLB, and only the walk shows which '
                         'page the address is really on.')
    ap.add_argument('--probe-ea', type=lambda v: int(v, 0), default=0,
                    metavar='LINEAR',
                    help='at every hit, read this linear address through the '
                         'guest paging (x) and physically (xp), then step one '
                         'instruction and report DS')
    ap.add_argument('--dflags', default='',
                    help="QEMU -d flags (e.g. 'int') logged to "
                         "qemu_out/watch_int.log. `int` prints one line per "
                         "exception with its vector and error code, which is "
                         "what names a fault instead of decoding a stack "
                         "frame by hand.")
    ap.add_argument('--mem', default='16')
    ap.add_argument('--cpu', default='486')
    args = ap.parse_args()

    watches = [(2, *parse_addr(s, 2)) for s in args.watch] + \
              [(3, *parse_addr(s, 2)) for s in args.rwatch]
    breaks = [(0, *parse_addr(s, 1)) for s in args.brk]
    armed = watches + breaks
    if not armed and not args.dflags:
        sys.exit('nothing to do: pass --watch, --break and/or --dflags')
    reads = [parse_addr(s, 2) for s in args.read] + \
            [(a, ln) for _k, a, ln in watches]

    os.makedirs(OUTDIR, exist_ok=True)
    qmp_port = run_qemu.free_port()
    gdb_port = run_qemu.free_port()
    cyls, heads, secs, _off = run_qemu.geometry(args.hdd)
    cmd = [QEMU, '-M', 'pc', '-cpu', args.cpu, '-m', args.mem,
           '-drive', f'file={args.hdd},format=raw,if=none,id=hd0,'
                     f'cache=writeback',
           '-device', f'ide-hd,drive=hd0,bus=ide.0,unit=0,'
                      f'cyls={cyls},heads={heads},secs={secs}',
           '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
           '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
           '-qmp', f'tcp:127.0.0.1:{qmp_port},server=on,wait=off',
           '-gdb', f'tcp:127.0.0.1:{gdb_port}']
    int_log = os.path.join(OUTDIR, 'watch_int.log')
    if args.dflags:
        run_qemu.stale(int_log)
        cmd += ['-d', args.dflags, '-D', int_log]
    print('$', ' '.join(cmd), '\n')
    log_path = os.path.join(OUTDIR, 'watch_qemu_stdout.log')
    run_qemu.stale(log_path)
    log_fh = open(log_path, 'wb')
    proc = subprocess.Popen(cmd, stdout=log_fh, stderr=subprocess.STDOUT)
    qmp = run_qemu.Qmp(qmp_port)

    if args.arm_at:
        print(f'--- running {args.arm_at:.0f}s before arming ---')
        time.sleep(args.arm_at)

    r = None
    for _ in range(40):
        try:
            r = rsp_mod.Rsp(gdb_port, timeout=1.0)
            break
        except OSError:
            time.sleep(0.25)
    if r is None:
        proc.kill()
        sys.exit('gdbstub never came up')
    def arm_all():
        for kind, addr, ln in armed:
            reply = r.insert(kind, addr, ln)
            what = {2: 'watch(w)', 3: 'watch(r)'}.get(kind, 'break')
            ok = 'OK' if reply == 'OK' else f'REFUSED ({reply!r})'
            print(f'arm {what} {addr:#x} len {ln}: {ok}')
            if reply != 'OK':
                proc.kill()
                sys.exit('the stub refused an armed address; nothing to '
                         'measure')

    # Connecting pauses the VM by itself, so an arm here happens against a
    # stopped guest and cannot be missed in the window between the two.
    if not args.arm_on_prompt and armed:
        arm_all()
    else:
        print('--- deferring the arm until the gate is on screen ---')

    def readback():
        """The watched words, through the *guest's* current translation."""
        out = []
        for addr, ln in reads:
            fmt = 'h' if ln == 2 else ('w' if ln == 4 else 'b')
            t = qmp.hmp(f'x /1x{fmt} 0x{addr:x}').strip().replace('\n', ' ')
            out.append(f'{addr:#x}={t.split(":")[-1].strip() or "?"}')
        return '  '.join(out)

    def screen_text():
        return run_qemu.dump_text_screen(qmp, 'watch_poll')

    hits = []
    key_sent = not args.key_on_prompt
    t0 = time.time()
    r.settimeout(0.4)
    r.send_cont()
    last_poll = 0.0
    while time.time() - t0 < args.timeout and len(hits) < args.max_hits:
        if proc.poll() is not None:
            print('--- QEMU exited ---')
            break
        stop = r.poll_stop()
        if stop is None:
            now = time.time() - t0
            if now - last_poll > 2.0:
                last_poll = now
                if not key_sent and PROMPT in screen_text():
                    # Interrupt, arm, resume, *then* press the key: arming
                    # needs a stopped guest, and doing it after the keypress
                    # would race the failure it is meant to catch.
                    if args.arm_on_prompt and armed:
                        print(f'  [{now:5.1f}s] gate on screen; interrupting '
                              f'to arm')
                        if r.interrupt() is None:
                            print('  (no stop reply to the interrupt)')
                        arm_all()
                        r.send_cont()
                    qmp.hmp(f'sendkey {args.key_on_prompt}')
                    key_sent = True
                    print(f'  [{now:5.1f}s] sendkey {args.key_on_prompt}')
            continue
        now = time.time() - t0
        regs = qmp.hmp('info registers')
        import re as _re
        eip = _re.search(r'EIP=([0-9a-f]{8})', regs)
        csm = _re.search(r'CS =([0-9a-f]{4}) ([0-9a-f]{8})', regs)
        ssm = _re.search(r'SS =([0-9a-f]{4}) ([0-9a-f]{8})', regs)
        espm = _re.search(r'ESP=([0-9a-f]{8})', regs)
        cr2m = _re.search(r'CR2=([0-9a-f]{8})', regs)
        cpl = _re.search(r'CPL=(\d)', regs)
        eip_v = int(eip.group(1), 16) if eip else None
        cs_sel = int(csm.group(1), 16) if csm else None
        cs_base = int(csm.group(2), 16) if csm else None
        lin = (cs_base + eip_v) if (cs_base is not None and eip_v is not None) else None
        hits.append({'t': now, 'stop': stop, 'eip': eip_v, 'cs': cs_sel,
                     'cs_base': cs_base, 'lin': lin, 'cpl': cpl and cpl.group(1),
                     'regs': regs, 'vals': readback()})
        print(f'\n--- hit {len(hits)} at {now:.1f}s: {stop.split(";")[0]} ---')
        print(f'  CS={cs_sel:#06x} base={cs_base:#010x} EIP={eip_v:#010x} '
              f'-> linear {lin:#x}  CPL={cpl and cpl.group(1)}'
              if lin is not None else f'  registers unparsed:\n{regs}')
        print(f'  words: {hits[-1]["vals"]}')
        if cr2m:
            print(f'  CR2={int(cr2m.group(1), 16):#010x}')
        if ssm and espm:
            # The exception frame, if this is a handler entry: a fault pushes
            # [error code,] EIP, CS, EFLAGS -- which names the faulting
            # instruction directly instead of leaving it to inference.
            stk = int(ssm.group(2), 16) + int(espm.group(1), 16)
            print(f'  stack at SS:ESP (linear {stk:#x}):')
            print('    ' + qmp.hmp(f'x /12xw 0x{stk:x}').strip()
                  .replace('\n', '\n    '))
        print('  ' + qmp.hmp(f'x /3i 0x{lin:x}').strip().replace('\n', '\n  ')
              if lin is not None else '')
        if args.probe_ea:
            # The same word three ways. If the CPU faults on a selector this
            # read does not show, the disagreement is in the *read path*, not
            # in the guest: `x` follows the guest's paging, `xp` is physical,
            # and the descriptor cache is what the CPU actually uses.
            ea = args.probe_ea
            print(f'  cs:[0x3F8] probes (CS base {cs_base:#x}):')
            print('    x  (linear, paged): ' +
                  qmp.hmp(f'x /4xh 0x{ea:x}').strip().replace('\n', ' '))
            print('    xp (physical):      ' +
                  qmp.hmp(f'xp /4xh 0x{ea:x}').strip().replace('\n', ' '))
        if args.pagewalk:
            lin_a = args.pagewalk
            cr3m = _re.search(r'CR3=([0-9a-f]{8})', regs)
            cr3 = int(cr3m.group(1), 16) & ~0xFFF if cr3m else None

            def phys_dword(pa):
                t = qmp.hmp(f'xp /1xw 0x{pa:x}').strip()
                tok = t.split(':')[-1].strip()
                try:
                    return int(tok, 16)
                except ValueError:
                    return None

            if cr3 is not None:
                pde_a = cr3 + ((lin_a >> 22) & 0x3FF) * 4
                pde = phys_dword(pde_a)
                print(f'  pagewalk {lin_a:#x}: CR3={cr3:#x} '
                      f'PDE@{pde_a:#x}={pde if pde is None else hex(pde)}')
                if pde and pde & 1:
                    pte_a = (pde & ~0xFFF) + ((lin_a >> 12) & 0x3FF) * 4
                    pte = phys_dword(pte_a)
                    print(f'    PTE@{pte_a:#x}={pte if pte is None else hex(pte)}')
                    if pte and pte & 1:
                        pa = (pte & ~0xFFF) | (lin_a & 0xFFF)
                        print(f'    -> physical {pa:#x} = ' +
                              qmp.hmp(f'xp /2xh 0x{pa:x}').strip())
        stepped = r.cont_from_stop(armed)
        if args.probe_ea:
            after = qmp.hmp('info registers')
            dsl = [l for l in after.splitlines() if l.startswith('DS =')]
            eipl = _re.search(r'EIP=([0-9a-f]{8})', after)
            print(f'  after one step: EIP={eipl and eipl.group(1)}  '
                  f'{dsl[0].strip() if dsl else "?"}')
        if stepped is None:
            print('  (step after the stop produced no reply; stopping)')
            break
        r.send_cont()

    print(f'\n--- {len(hits)} hit(s) in {time.time() - t0:.1f}s ---')
    print(run_qemu.dump_text_screen(qmp, 'watch_final'))
    print('screen:', run_qemu.screendump(qmp, 'watch_final'))
    print(qmp.hmp('info registers').strip())
    try:
        r.close()
    except OSError:
        pass
    qmp.hmp('quit')
    time.sleep(1)
    proc.kill()
    log_fh.close()

    if args.dflags and os.path.exists(int_log):
        size = os.path.getsize(int_log)
        print(f'\n===== -d {args.dflags} log: {int_log} ({size} B) =====')
    print('\n===== writers =====')
    seen = {}
    for h in hits:
        seen.setdefault(h['lin'], []).append(h)
    for lin, group in sorted(seen.items(), key=lambda kv: -len(kv[1])):
        first = group[0]
        print(f'{lin:#x}  x{len(group)}  first at {first["t"]:.1f}s  '
              f'CS={first["cs"]:#06x} CPL={first["cpl"]}  {first["vals"]}')
    out = open(log_path, encoding='utf-8', errors='replace').read()
    if out.strip():
        print('--- qemu stdout ---\n' + out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
