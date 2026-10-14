"""N/A - DOS oracle harness for the VESA480.DLL copy exports 6, 7 and 11.

Captures connected-game witnesses: entry arguments, the bitmap descriptor and
source pixels, the screen rectangle before and after, read from the linear
framebuffer (PCI BAR0 of the emulated VGA, which maps the same bytes the bank
windows address). Expected values are DOS output only.
"""
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/re'))
import lx_dll  # noqa: E402

DRIVER_BASE = 0x218AED
LFB = 0xFD000000
SCREEN_W, SCREEN_H = 640, 480
EXPORTS = {6: 0x1263, 7: 0x37B7, 11: 0x24E0}
PER_EXPORT = 6


class DrawProbe:
    def __init__(self, rsp, qmp, read, record):
        self.rsp, self.qmp, self.read, self.record = rsp, qmp, read, record
        self.points, self.pending, self.count = {}, {}, {n: 0 for n in EXPORTS}
        self.seen = set()
        record['draw_contracts'] = []

    def arm(self, exe, delta):
        image, _ = lx_dll.rebased(DRIVER_BASE)
        for n, off in EXPORTS.items():
            address = DRIVER_BASE + off
            if self.read(address, 48) != image[off:off + 48]:
                raise RuntimeError(f'display driver export {n} not at {DRIVER_BASE:#x}')
            if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                raise RuntimeError('draw breakpoint rejected')
            self.points[address] = ('entry', n)
        self.record['draw_driver'] = {'base': DRIVER_BASE,
                                      'imageSha256': hashlib.sha256(lx_dll.image()).hexdigest()}

    def u32s(self, address, count):
        return list(struct.unpack(f'<{count}I', self.read(address, 4 * count)))

    def screen(self, x0, y0, x1, y1):
        rows = [self.read(LFB + y * SCREEN_W + x0, x1 - x0 + 1).hex() for y in range(y0, y1 + 1)]
        return {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'rows': rows}

    def bitmap_rows(self, desc, x0, y0, x1, y1):
        stride = desc[1] + 1
        return [self.read(desc[0] + y * stride + x0, x1 - x0 + 1).hex() for y in range(y0, y1 + 1)]

    def hit(self, regs, at):
        kind, n = self.points[regs['EIP']]
        if kind == 'entry':
            self.entry(n, regs, at)
        else:
            self.exit(regs, at)

    def entry(self, n, regs, at):
        esp = regs['ESP']
        ret, arg1, a, b, c, d = self.u32s(esp, 6)
        ev = {'functionId': f'vesa480_export_{n}', 'export': n, 'kind': 'connected-poland', 'at': at,
              'args': [arg1, a, b, c, d], 'retAddress': ret, 'esp': esp}
        if n == 11:
            rect = self.u32s(arg1, 5)
            desc = self.u32s(rect[0], 5)
            ev['rect'] = rect
            sx0, sy0, sx1, sy1 = rect[1:]
        else:
            desc = self.u32s(arg1, 5)
            sx0, sy0, sx1, sy1 = 0, 0, desc[1], desc[2]
        ev['desc'] = desc
        key = (n, (a, b, c, d), tuple(desc[1:3]), tuple(ev.get('rect', [0])[1:]))
        if key in self.seen:
            return
        dx0, dy0, dx1, dy1 = max(a, 0), max(b, 0), min(c, SCREEN_W - 1), min(d, SCREEN_H - 1)
        ev['clippedDest'] = [dx0, dy0, dx1, dy1]
        # Edge and reject cases are not the connected witness.
        if sx0 < 0 or sy0 < 0 or sx1 > desc[1] or sy1 > desc[2] or dx1 < dx0 or dy1 < dy0:
            return
        if n == 7:
            ev['screenBefore'] = self.screen(a, b, c, d)
        else:
            ev['sourceRows'] = self.bitmap_rows(desc, sx0, sy0, sx1, sy1)
            ev['screenBefore'] = self.screen(dx0, dy0, dx1, dy1)
        self.seen.add(key)
        self.pending[ret] = ev
        if ret not in self.points:
            if self.rsp.command(f'Z0,{ret:x},1') != 'OK':
                raise RuntimeError('draw return breakpoint rejected')
            self.points[ret] = ('exit', n)

    def exit(self, regs, at):
        ev = self.pending.get(regs['EIP'])
        if ev is None or regs['ESP'] != ev['esp'] + 4:
            return
        del self.pending[regs['EIP']]
        n = ev['export']
        if n == 7:
            ev['bitmapAfter'] = self.bitmap_rows(ev['desc'], 0, 0, ev['desc'][1], ev['desc'][2])
        else:
            ev['screenAfter'] = self.screen(*ev['clippedDest'])
        ev['registersAfter'] = {k: regs[k] for k in ('EAX', 'EBX', 'ECX', 'EDX', 'ESI', 'EDI', 'EBP', 'ESP')}
        self.record['draw_contracts'].append(ev)
        self.count[n] += 1
        for address in [p for p, v in self.points.items() if v == ('exit', n) and p not in self.pending]:
            self.rsp.command(f'z0,{address:x},1')
            del self.points[address]
        if self.count[n] >= PER_EXPORT:
            for address, v in list(self.points.items()):
                if v == ('entry', n):
                    self.rsp.command(f'z0,{address:x},1')
                    del self.points[address]

    def finish(self):
        for n in EXPORTS:
            if self.count[n] == 0:
                self.record['problems'].append(f'no draw witness for export {n}')
