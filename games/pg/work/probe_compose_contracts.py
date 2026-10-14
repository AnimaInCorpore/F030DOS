"""N/A - DOS oracle probe: entry/exit witnesses of the static-frame compositor sub_00014BF6.

The compositor draws four shapes through sub_00058AB4 into the 640x480 back buffer
and then calls sub_000481AB four times (present). A witness holds what the call can
read: arena windows (rect records, globals, shape pointers), the destination bitmap
before and after, each shape draw it makes (arguments, shape header and sprite
bytes) and the argument of every sub_000481AB call, in order. Expected values are DOS
output only; the present function is a recorded boundary, not translated.
"""
import struct

ENTRY = 0x14BF6
ENTRY_BYTES = bytes.fromhex('535152565755' '89e5' '81ec00000000')
SHAPE = 0x58AB4
PRESENT = 0x481AB
FILE_DELTA = 0x482A4
ARENA = 0x1E0000
# arena windows (offset, bytes) the compositor and its callee can read
WINDOWS = [(0xC000, 0x2000), (0x17800, 0x200), (0x28E00, 0x200)]
RECORDS = 0xC61C
GLOBALS = {'idx_a': 0x28EEA, 'idx_b': 0x28EE6, 'idx_c': 0x28EE7, 'idx_d': 0xCCBC, 'shape_index': 0x28EEF}
MAX_CASES = 4
SPRITE_CAP = 0x10000
UNBOUNDED_WINDOW = 0x20000


class ComposeProbe:
    def __init__(self, rsp, qmp, read, record, out, activate_at=None):
        self.rsp, self.qmp, self.read, self.record, self.out = rsp, qmp, read, record, out
        self.points, self.pending, self.count, self.seen = {}, None, 0, set()
        self.hits, self.skipped = 0, []
        self.activate_at = activate_at
        self.entries = {}
        record['compose_contracts'] = []

    def arm(self, exe, delta):
        self.delta = delta
        for name, vaddr, prefix in (('compose', ENTRY, ENTRY_BYTES),
                                    ('shape', SHAPE, bytes.fromhex('558bec83c4b0535657')),
                                    ('present', PRESENT, bytes.fromhex('53515256575589e581'))):
            f = vaddr + FILE_DELTA
            if exe[f:f + len(prefix)] != prefix or self.read(f + delta, len(prefix)) != prefix:
                raise RuntimeError(f'compositor probe entry mismatch: {name}')
            self.entries[name] = f + delta
        if self.activate_at is None:
            self.activate()

    def activate(self):
        if self.rsp.command(f'Z0,{self.entries["compose"]:x},1') != 'OK':
            raise RuntimeError('compositor breakpoint rejected')
        self.points[self.entries['compose']] = ('compose',)
        self.record['compose_armed'] = {'entry': self.entries['compose'], 'delta': self.delta}

    def u32s(self, address, count):
        return list(struct.unpack(f'<{count}I', self.read(address, 4 * count)))

    def save(self, address, size, name):
        path = self.out / name
        self.qmp.hmp(f'pmemsave {address:#x} {size:#x} "{path.as_posix()}"')
        if not path.is_file() or path.stat().st_size != size:
            raise RuntimeError(f'pmemsave of {size} bytes at {address:#x} failed')
        return name

    def insert(self, address, tag):
        if address not in self.points:
            if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                raise RuntimeError('breakpoint rejected')
        self.points[address] = tag

    def remove(self, address):
        if address in self.points:
            self.rsp.command(f'z0,{address:x},1')
            del self.points[address]

    def hit(self, regs, at):
        tag = self.points[regs['EIP']]
        if tag[0] == 'compose':
            self.enter(regs, at)
        elif tag[0] == 'shape':
            self.shape(regs, at)
        elif tag[0] == 'present':
            self.present(regs, at)
        else:
            self.leave(regs, at)

    def enter(self, regs, at):
        self.hits += 1
        if self.pending is not None or self.count >= MAX_CASES:
            return
        esp = regs['ESP']
        ret = self.u32s(esp, 1)[0]
        windows = [(o, self.read(ARENA + o, n)) for o, n in WINDOWS]
        key = hash(b''.join(w for _, w in windows))
        if key in self.seen:
            self.skipped.append(('duplicate', at))
            return
        g = {name: self.read(ARENA + off, 1)[0] for name, off in GLOBALS.items()}
        recs = [self.u32s(ARENA + RECORDS + 20 * g[k], 5) for k in ('idx_a', 'idx_b', 'idx_c', 'idx_d')]
        descs = {tuple(self.u32s(r[0], 5)) for r in recs}
        if len({d[0] for d in descs}) != 1 or any(d[4] for d in descs):
            self.skipped.append(('several bitmaps or shadow', at, g, [list(d) for d in descs]))
            return                                       # draws to several bitmaps or a shadow descriptor
        desc = list(next(iter(descs)))
        if desc[1] > 1023 or desc[2] > 1023:
            self.skipped.append(('large bitmap', at, desc))
            return
        n = self.count
        size = (desc[1] + 1) * (desc[2] + 1)
        self.seen.add(key)
        self.pending = {'functionId': 'sub_00014BF6', 'kind': 'connected-poland', 'at': at, 'esp': esp, 'ret': ret,
                        'globals': g, 'records': recs, 'desc': desc,
                        'windows': [{'offset': o, 'hex': w.hex()} for o, w in windows],
                        'beforeFile': self.save(desc[0], size, f'compose-{n}.before'), 'bitmapBytes': size,
                        'shapeDraws': [], 'present': [], 'valid': True, 'n': n,
                        'registers': {k: regs[k] for k in ('EAX', 'EBX', 'ECX', 'EDX', 'ESI', 'EDI', 'EBP')}}
        self.insert(ret, ('leave',))
        self.insert(self.entries['shape'], ('shape',))
        self.insert(self.entries['present'], ('present',))

    def shape(self, regs, at):
        if self.pending is None:
            return
        esp = regs['ESP']
        ret, clip, shape, index, x, y = self.u32s(esp, 6)
        entry0, entry1 = self.u32s(shape + 8 + 8 * index, 2), self.u32s(shape + 16 + 8 * index, 2)
        unbounded = not entry0[0] < entry1[0] <= entry0[0] + SPRITE_CAP
        if unbounded:                                  # a lone sprite: no next entry bounds it; take a fixed window
            entry1 = [entry0[0] + UNBOUNDED_WINDOW, entry1[1]]
        n, k = self.pending['n'], len(self.pending['shapeDraws'])
        head = 8 + 8 * (index + 2)
        self.pending['shapeDraws'].append({
            'args': [clip, shape, index, x, y], 'clip': self.u32s(clip, 5), 'tableEntry': entry0, 'nextEntry': entry1,
            'unbounded': unbounded,
            'headHex': self.read(shape, head).hex(), 'spriteOffset': entry0[0],
            'spriteFile': self.save(shape + entry0[0], entry1[0] - entry0[0], f'compose-{n}-{k}.sprite'),
            'spriteBytes': entry1[0] - entry0[0]})

    def present(self, regs, at):
        if self.pending is not None:
            self.pending['present'].append({'eax': regs['EAX'], 'al': regs['EAX'] & 255, 'at': at})

    def leave(self, regs, at):
        ev = self.pending
        if ev is None or regs['EIP'] != ev['ret'] or regs['ESP'] != ev['esp'] + 4:
            return
        self.pending = None
        for address in (ev['ret'], self.entries['shape'], self.entries['present']):
            self.remove(address)
        if not ev['valid'] or len(ev['shapeDraws']) != 4 or len(ev['present']) != 4:
            self.record['problems'].append(f'compositor call at {ev["at"]} skipped: {len(ev["shapeDraws"])} draws, '
                                           f'{len(ev["present"])} present calls, valid={ev["valid"]}')
            return
        ev['afterFile'] = self.save(ev['desc'][0], ev['bitmapBytes'], f'compose-{ev["n"]}.after')
        ev['windowsAfter'] = [{'offset': o, 'hex': self.read(ARENA + o, n).hex()} for o, n in WINDOWS]
        ev['exitAt'] = at
        ev['eax'] = regs['EAX']
        ev['registersAfter'] = {k: regs[k] for k in ('EAX', 'EBX', 'ECX', 'EDX', 'ESI', 'EDI', 'EBP', 'ESP')}
        del ev['valid']
        self.record['compose_contracts'].append(ev)
        self.count += 1

    def finish(self):
        self.record['compose_hits'] = self.hits
        self.record['compose_skipped'] = self.skipped[:20]
        if self.count == 0:
            self.record['problems'].append('no compositor witness')
