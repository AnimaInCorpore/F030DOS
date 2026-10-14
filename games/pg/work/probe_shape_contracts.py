"""N/A - DOS oracle probe: entry/exit witnesses of the clipped shape draw sub_00058AB4.

The function takes (clip, shape, index, x, y) on the stack (analysis/rendering.md)
and reads no globals (its translation has no arena access); sub_00058F9E takes the
same arguments and maps pixels through a 256-byte table at arena offset 0x6E48. A
witness is: the clip record and its bitmap descriptor, the shape image's header and
sprite table through the next entry plus the sprite's own bytes (the next entry
bounds it), the table, the whole destination bitmap before and after the call
(saved with `pmemsave`, paging is off so linear = physical), and EAX at the return. Expected values are DOS output
only; nothing is generated here.
"""
import struct

FUNCS = {'sub_00058AB4': (0x58AB4, bytes.fromhex('558bec83c4b0535657')),
         'sub_00058F9E': (0x58F9E, bytes.fromhex('558bec83c4b0535657'))}   # same arguments; pixels mapped through TABLE
ARENA = 0x1E0000               # runtime base of LE object 2
TABLE = 0x6E48                 # 256-byte pixel translation table read by sub_00058F9E (`[eax + 0x6e48]`)
FILE_DELTA = 0x482A4           # vaddr -> file offset for object 1
MAX_CASES = 16
SPRITE_CAP = 0x10000


class ShapeProbe:
    def __init__(self, rsp, qmp, read, record, out, activate_at=None):
        self.rsp, self.qmp, self.read, self.record, self.out = rsp, qmp, read, record, out
        self.points, self.pending, self.seen, self.count = {}, {}, set(), 0
        self.activate_at = activate_at          # route checkpoint after which to capture (None: from the start)
        self.entries = {}
        record['shape_contracts'] = []

    def arm(self, exe, delta):
        for name, (vaddr, prefix) in FUNCS.items():
            f = vaddr + FILE_DELTA
            address = f + delta
            if exe[f:f + len(prefix)] != prefix or self.read(address, len(prefix)) != prefix:
                raise RuntimeError(f'shape primitive entry mismatch: {name}')
            self.entries[address] = name
        if self.activate_at is None:
            self.activate()

    def activate(self):
        for address, name in self.entries.items():
            if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                raise RuntimeError('shape breakpoint rejected')
            self.points[address] = ('entry', name)

    def u32s(self, address, count):
        return list(struct.unpack(f'<{count}I', self.read(address, 4 * count)))

    def save(self, address, size, name):
        path = self.out / name
        self.qmp.hmp(f'pmemsave {address:#x} {size:#x} "{path.as_posix()}"')
        if not path.is_file() or path.stat().st_size != size:
            raise RuntimeError(f'pmemsave of {size} bytes at {address:#x} failed')
        return name

    def hit(self, regs, at):
        kind, name = self.points[regs['EIP']]
        if kind == 'entry':
            self.entry(name, regs, at)
        else:
            self.exit(regs, at)

    def entry(self, name, regs, at):
        esp = regs['ESP']
        ret, clip, shape, index, x, y = self.u32s(esp, 6)
        rect = self.u32s(clip, 5)
        desc = self.u32s(rect[0], 5)
        key = (name, shape, index, x, y, tuple(rect))
        if key in self.seen or self.count + len(self.pending) >= MAX_CASES:
            return
        if desc[1] > 1023 or desc[2] > 1023 or not desc[0] or desc[4]:
            return                                     # outside the measured bitmaps or a shadow descriptor
        entry0, entry1 = self.u32s(shape + 8 + 8 * index, 2), self.u32s(shape + 16 + 8 * index, 2)
        if not entry0[0] < entry1[0] <= entry0[0] + SPRITE_CAP:
            return                                     # the sprite's extent is not bounded by the next entry
        n = self.count + len(self.pending)
        size = (desc[1] + 1) * (desc[2] + 1)
        head = 8 + 8 * (index + 2)                     # image header and the table through the next entry
        ev = {'functionId': name, 'kind': 'connected-poland', 'at': at, 'args': [clip, shape, index, x, y],
              'retAddress': ret, 'esp': esp, 'clip': rect, 'desc': desc, 'tableEntry': entry0, 'nextEntry': entry1,
              'headHex': self.read(shape, head).hex(), 'spriteOffset': entry0[0],
              'spriteFile': self.save(shape + entry0[0], entry1[0] - entry0[0], f'shape-{n}.sprite'),
              'spriteBytes': entry1[0] - entry0[0],
              'tableHex': self.read(ARENA + TABLE, 256).hex(), 'tableOffset': TABLE,
              'beforeFile': self.save(desc[0], size, f'shape-{n}.before'), 'bitmapBytes': size,
              'registers': {k: regs[k] for k in ('EAX', 'EBX', 'ECX', 'EDX', 'ESI', 'EDI', 'EBP')}}
        self.seen.add(key)
        self.pending[ret] = (n, ev)
        if ret not in self.points:
            if self.rsp.command(f'Z0,{ret:x},1') != 'OK':
                raise RuntimeError('shape return breakpoint rejected')
            self.points[ret] = ('exit', name)

    def exit(self, regs, at):
        item = self.pending.get(regs['EIP'])
        if item is None or regs['ESP'] != item[1]['esp'] + 4:
            return
        n, ev = item
        del self.pending[regs['EIP']]
        ev['afterFile'] = self.save(ev['desc'][0], ev['bitmapBytes'], f'shape-{n}.after')
        ev['eax'] = regs['EAX']
        ev['exitAt'] = at
        self.record['shape_contracts'].append(ev)
        self.count += 1
        for address in [p for p, v in self.points.items() if v[0] == 'exit' and p not in self.pending]:
            self.rsp.command(f'z0,{address:x},1')
            del self.points[address]
        if self.count >= MAX_CASES:
            for address, v in list(self.points.items()):
                if v[0] == 'entry':
                    self.rsp.command(f'z0,{address:x},1')
                    del self.points[address]

    def finish(self):
        if self.count == 0:
            self.record['problems'].append('no shape-draw witness')
