#!/usr/bin/env python3
"""Set one breakpoint on the running DOS oracle and read the machine state.

`analysis/ghidra.md` section 8 described this technique and used a client that
was written in-session and never committed; this is that client, kept.

QEMU's gdbstub is enabled *live* over QMP on an already-booted guest
(`human-monitor-command "gdbserver tcp::1234"`), so nothing has to be relaunched
with `-s`. The RSP wire protocol is spoken directly -- `$packet#checksum`
framing, `Z0`/`z0`, `g`, `m`, `c` -- rather than driving gdb or lldb, which
keeps every byte on the wire visible when something times out.

Breakpoint addresses are given as *file offsets* into UW2.EXE; the file->linear
delta is calibrated first (the same signature hunt `gdbstub_probe.py` uses), so
the caller never has to care what this boot's load segment turned out to be.

Usage:
  python work/rsp_break.py --at 0x112CC                    # the VM entry
  python work/rsp_break.py --at 0x112CC --wait 70 --key esc
  python work/rsp_break.py --attach --at 0x112CC \
      --mouse=-80,65 --click 1.5
"""
import argparse
import atexit
import binascii
import collections
import os
import socket
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdbstub_probe as P            # noqa: E402  (Qmp, geometry, signatures)

QMP_PORT = 4444
RSP_PORT = 1234


class Rsp:
    """Minimal GDB remote-serial-protocol client."""

    def __init__(self, port, timeout=30):
        self.s = socket.create_connection(('127.0.0.1', port), timeout=timeout)
        self.buf = b''

    def send(self, data):
        pkt = data.encode()
        csum = sum(pkt) & 0xFF
        self.s.sendall(b'$' + pkt + b'#' + b'%02x' % csum)

    def _read_packet(self, timeout=None):
        if timeout is not None:
            self.s.settimeout(timeout)
        while True:
            i = self.buf.find(b'$')
            j = self.buf.find(b'#', i + 1) if i >= 0 else -1
            if i >= 0 and j >= 0 and len(self.buf) >= j + 3:
                body = self.buf[i + 1:j]
                self.buf = self.buf[j + 3:]
                self.s.sendall(b'+')
                return body.decode('latin1')
            chunk = self.s.recv(4096)
            if not chunk:
                raise EOFError('gdbstub closed the connection')
            self.buf += chunk.replace(b'+', b'', 1) if chunk.startswith(b'+') else chunk

    def cmd(self, data, timeout=30):
        self.send(data)
        return self._read_packet(timeout)

    def set_break(self, linear):
        return self.cmd(f'Z0,{linear:x},1')

    def set_watch(self, linear, n=1, kind=3):
        """Z2=write, Z3=read, Z4=access watchpoint."""
        return self.cmd(f'Z{kind},{linear:x},{n}')

    def clear_break(self, linear):
        return self.cmd(f'z0,{linear:x},1')

    def mem(self, linear, n):
        r = self.cmd(f'm{linear:x},{n:x}')
        if r.startswith('E'):
            return b''
        try:
            return binascii.unhexlify(r)
        except binascii.Error:
            return b''

    def cont_nowait(self):
        """Send `c` without blocking -- lets the harness drive the guest over
        QMP while the breakpoint rides in the background (the pattern
        ghidra.md section 9 used to catch a rare event)."""
        self.send('c')

    def wait_stop(self, timeout):
        return self._read_packet(timeout)


def launch(a):
    P.kill_strays()
    cyls, heads, secs, _ = P.geometry(a.hdd)
    cmd = [P.QEMU, '-M', 'pc', '-cpu', '486', '-m', '16',
           '-drive', f'file={a.hdd},format=raw,if=none,id=hd0,cache=writeback',
           '-device', f'ide-hd,drive=hd0,bus=ide.0,unit=0,'
                      f'cyls={cyls},heads={heads},secs={secs}',
           '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
           '-qmp', f'tcp:127.0.0.1:{QMP_PORT},server=on,wait=off']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    atexit.register(lambda: proc.kill() if proc.poll() is None else None)
    print(f'qemu started, waiting {a.wait}s for the guest to settle')
    time.sleep(a.wait)
    if proc.poll() is not None:
        sys.exit('QEMU exited early:\n' + proc.stdout.read())
    return proc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--at', default='0',
                    help='breakpoint, as a FILE offset into UW2.EXE (hex ok)')
    ap.add_argument('--hdd', default=P.default_hdd())
    ap.add_argument('--exe', default=P.default_exe())
    ap.add_argument('--wait', type=int, default=60,
                    help='seconds to let the guest boot before arming')
    ap.add_argument('--hit-timeout', type=int, default=120)
    ap.add_argument('--attach', action='store_true',
                    help='attach to an already-running, already-navigated '
                         'session (work/drive.py) instead of booting a fresh '
                         'one -- the only way to reach in-game-only code')
    ap.add_argument('--key', action='append', default=[],
                    help='key to send after arming, to drive the guest')
    ap.add_argument('--mouse', action='append', default=[], metavar='DX,DY',
                    help='relative mouse move after arming; repeatable')
    ap.add_argument('--click', action='append', default=[], metavar='HOLD',
                    help='left-click after arming, held HOLD seconds; repeatable')
    ap.add_argument('--watch-sig', metavar='HEX',
                    help='hunt this byte signature in guest RAM, then set a READ '
                         'watchpoint on it -- finds the code that consumes a '
                         'buffer when you do not know who does')
    ap.add_argument('--dump', action='append', default=[], metavar='SEG:OFF/N',
                    help='extra guest memory to dump at the hit, e.g. DS:24f4/32'
                         ' (SEG may be a register name or a hex value)')
    a = ap.parse_args()
    target_file = int(a.at, 0)

    # `file + delta` is only valid for the DOS-mapped image. CODE_TAIL is the
    # Borland FBOV overlay pool: overlays are swapped into a buffer at an
    # address that differs per load, so a tail file offset corresponds to no
    # fixed linear address. A breakpoint there silently never fires, and the
    # result is indistinguishable from "this code did not execute" -- which is
    # exactly the wrong conclusion. Refuse instead.
    _exe = open(a.exe, 'rb').read()
    _image_end = ((struct.unpack_from('<H', _exe, 0x04)[0] - 1) * 512
                  + struct.unpack_from('<H', _exe, 0x02)[0])
    if target_file and target_file >= _image_end:
        sys.exit(f'{target_file:#07x} is at or past the image end '
                 f'{_image_end:#07x}: it is in the FBOV overlay pool, which has '
                 f'no fixed linear address, so a breakpoint there can never '
                 f'fire. See AGENTS.md on the overlay pool.')

    if a.attach:
        proc = None
        print('attaching to the running session on QMP', QMP_PORT)
    else:
        proc = launch(a)
    qmp = P.Qmp(QMP_PORT)
    exe = open(a.exe, 'rb').read()

    def xp(addr, n):
        t = qmp.hmp(f'xp /{n}xb 0x{addr:x}')
        vals = [tok[2:] if tok.startswith('0x') else tok for tok in t.split()]
        vals = [v for v in vals if len(v) == 2
                and all(c in '0123456789abcdef' for c in v)]
        try:
            return bytes.fromhex(''.join(vals[:n]))
        except ValueError:
            return b''

    sigs = P.pick_signatures(exe, P.find_overlay_pool(exe))
    found, carry = {}, b''
    for base in range(0x00000, 0xA0000, 0x4000):
        d = xp(base, 0x4000)
        if len(d) != 0x4000:
            continue
        blob = carry + d
        for label, off in sigs:
            if label not in found:
                i = blob.find(exe[off:off + 16])
                if i >= 0:
                    found[label] = (base - len(carry) + i) - off
        carry = d[-15:]
        if len(found) == len(sigs):
            break
    votes = collections.Counter(found.values())
    if not votes:
        sys.exit('could not calibrate the file->linear delta')
    delta, agree = votes.most_common(1)[0]
    hdr = int.from_bytes(exe[0x08:0x0A], 'little') * 16
    print(f'delta {delta:#07x} ({agree}/{len(found)} signatures agree), '
          f'load segment {(delta + hdr) >> 4:#06x}')

    if a.watch_sig:
        sig = bytes.fromhex(a.watch_sig)
        # NB: the game uses EMS, and the page frame lives above 0xA0000 --
        # scanning only conventional memory finds nothing (learned the hard way).
        top = 0x110000
        print(f'hunting {len(sig)}-byte signature {sig.hex(" ")} in 0..{top:#x}')
        found = []
        carry = b''
        for base in range(0x00000, top, 0x4000):
            blk = xp(base, 0x4000)
            if len(blk) != 0x4000:
                continue
            blob = carry + blk
            start = 0
            while True:
                i = blob.find(sig, start)
                if i < 0:
                    break
                found.append(base - len(carry) + i)
                start = i + 1
            carry = blk[-(len(sig) - 1):]
        print(f'  {len(found)} hit(s): {[hex(x) for x in found[:6]]}')
        if not found:
            return 1
        linear = found[0]
        print(qmp.hmp(f'gdbserver tcp::{RSP_PORT}').strip())
        rsp = Rsp(RSP_PORT)
        print('Z3 ->', rsp.set_watch(linear, len(sig), 3))
        rsp.cont_nowait()
        try:
            stop = rsp.wait_stop(a.hit_timeout)
        except (socket.timeout, EOFError) as e:
            print(f'NO READ within {a.hit_timeout}s ({type(e).__name__})')
            return 1
        print('stopped:', stop[:120])
        regs = P.parse_regs(qmp.hmp('info registers'))
        cs, eip = regs.get('CS', 0), regs.get('EIP', 0)
        lin = (cs << 4) + (eip & 0xFFFF)
        print(f'  CS:IP = {cs:04x}:{eip & 0xFFFF:04x} -> linear {lin:#07x} '
              f'-> file {lin - delta:#07x}')
        for k in ('DS', 'ESI', 'ES', 'EDI', 'EBX', 'ECX'):
            if k in regs:
                print(f'  {k:4s} {regs[k]:#010x}')
        return 0

    linear = target_file + delta
    print(f'breakpoint: file {target_file:#07x} -> linear {linear:#07x}')
    print(qmp.hmp(f'gdbserver tcp::{RSP_PORT}').strip())

    rsp = Rsp(RSP_PORT)
    print('Z0 ->', rsp.set_break(linear))
    rsp.cont_nowait()
    for spec in a.mouse:
        try:
            dx, dy = (int(v, 0) for v in spec.split(',', 1))
        except (ValueError, TypeError):
            sys.exit(f'--mouse wants DX,DY, got {spec!r}')
        time.sleep(1)
        qmp.hmp(f'mouse_move {dx} {dy}')
        print(f'mouse_move {dx} {dy}')
    for value in a.click:
        try:
            hold = float(value)
        except ValueError:
            sys.exit(f'--click wants seconds, got {value!r}')
        if hold < 0:
            sys.exit(f'--click hold must be non-negative, got {value!r}')
        time.sleep(1)
        qmp.hmp('mouse_button 1')
        time.sleep(hold)
        qmp.hmp('mouse_button 0')
        print(f'click (held {hold}s)')
    for k in a.key:
        time.sleep(2)
        qmp._cmd({'execute': 'send-key', 'arguments':
                  {'keys': [{'type': 'qcode', 'data': k}]}})
    try:
        stop = rsp.wait_stop(a.hit_timeout)
    except (socket.timeout, EOFError) as e:
        print(f'NO HIT within {a.hit_timeout}s ({type(e).__name__}) -- '
              f'a real negative result: this code did not execute.')
        return 1
    print('stopped:', stop[:120])

    raw = qmp.hmp('info registers')
    regs = P.parse_regs(raw)
    print('--- registers ---')
    for k in ('CS', 'EIP', 'DS', 'ESI', 'ES', 'EBX', 'SS', 'ESP', 'EBP'):
        if k in regs:
            print(f'  {k:4s} {regs[k]:#010x}')
    ds, si = regs.get('DS', 0), regs.get('ESI', 0) & 0xFFFF
    es, bx = regs.get('ES', 0), regs.get('EBX', 0) & 0xFFFF
    for lbl, seg, off, n in (('DS:SI (token stream)', ds, si, 64),
                             ('ES:BX (caller record)', es, bx, 16)):
        lin = (seg << 4) + off
        got = xp(lin, n)
        print(f'  {lbl} = {seg:04x}:{off:04x} -> linear {lin:#07x}')
        print(f'    guest: {got.hex(" ")}')
        f_off = lin - delta
        if 0 <= f_off < len(exe):
            print(f'    file {f_off:#07x}: {exe[f_off:f_off + n].hex(" ")}')
            print(f'    identical: {got == exe[f_off:f_off + n]}')
        else:
            print('    (outside the file image)')

    for spec in a.dump:
        where, _, n = spec.partition('/')
        segtxt, _, offtxt = where.partition(':')
        seg = regs.get(segtxt.upper(), None)
        if seg is None:
            seg = int(segtxt, 16)
        # offsets may be REG+HEX, e.g. BP+10, so a stack argument can be read
        # without knowing BP in advance
        if '+' in offtxt:
            base, _, add = offtxt.partition('+')
            off = (regs.get('E' + base.upper(), regs.get(base.upper(), 0)) & 0xFFFF) \
                + int(add, 16)
        else:
            off = int(offtxt, 16)
        n = int(n or 32)
        lin = (seg << 4) + off
        got = xp(lin, n)
        f_off = lin - delta
        print(f'  {spec} = {seg:04x}:{off:04x} -> linear {lin:#07x} '
              f'(file {f_off:#07x})')
        print(f'    guest: {got.hex(" ")}')
        if 0 <= f_off < len(exe):
            print(f'    file : {exe[f_off:f_off + n].hex(" ")}')
            print(f'    identical: {got == exe[f_off:f_off + n]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
