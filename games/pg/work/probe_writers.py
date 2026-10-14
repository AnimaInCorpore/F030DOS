"""N/A - DOS oracle probe: which code writes the 640x480 back buffer.

Write-watchpoints (GDB Z2) on a few sample pixels of the back-buffer bitmap whose
descriptor sits at object-2 0xC3C4 (analysis/rendering.md). Each stop records
the writer's EIP (after the write), registers, a stack excerpt and the EBP chain
so the writer can be mapped to the recovered function inventory offline. It
records which code wrote, not what the game means by it.
"""
import struct

# target -> (descriptor address, sample pixels (name, x, y) in that bitmap's own coordinates)
TARGETS = {
    # the 640 x 480 back buffer
    'back': (0x1EC3C4, [('terrain', 330, 300), ('unit-tank', 100, 322), ('text-bar', 150, 8),
                        ('panel-button', 600, 120), ('hex-line', 300, 250), ('terrain-2', 460, 60),
                        ('border', 5, 470), ('strength-box', 50, 262)]),
    # the 555 x 426 map-view bitmap, shown on screen at (20, 20); points from the Poland tactical frame
    'map': (0x1EC3D8, [('terrain', 310, 280), ('unit-tank', 80, 302), ('forest', 160, 180)]),
}
MAX_HITS = 8000
RECORD_FROM = 0.0


class WriterProbe:
    def __init__(self, rsp, qmp, read, record, target='back'):
        self.rsp, self.qmp, self.read, self.record = rsp, qmp, read, record
        self.descriptor, self.samples = TARGETS[target]
        self.target = target
        self.activate_at = {'back': 'axis_turn', 'map': 'poland_selected'}[target]   # route checkpoint
        self.points = {}
        self.armed = False
        self.addresses = {}
        self.last = {}
        record['writer_hits'] = []

    def arm(self, exe, delta):
        base, max_x, max_y = struct.unpack('<III', self.read(self.descriptor, 12))
        expected = {'back': (639, 479), 'map': (554, 425)}[self.target]
        if (max_x, max_y) != expected or not base:
            raise RuntimeError('bitmap descriptor not as measured')
        stride = max_x + 1
        self.record['writer_watch'] = {'target': self.target, 'descriptor': self.descriptor, 'pixelBase': base,
                                       'samples': [{'name': n, 'x': x, 'y': y, 'address': base + y * stride + x}
                                                   for n, x, y in self.samples]}
        for n, x, y in self.samples:
            address = base + y * stride + x
            self.addresses[n] = address

    def activate(self):
        """Insert the watchpoints; called while the guest is stopped at a checkpoint."""
        for n, address in self.addresses.items():
            if self.rsp.command(f'Z2,{address:x},1') != 'OK':
                raise RuntimeError('write watchpoint rejected')
            self.last[n] = self.read(address, 1)[0]
        self.armed = True

    def owns_stop(self):
        return self.armed

    def hit_watch(self, regs, at):
        if at < RECORD_FROM or len(self.record['writer_hits']) >= MAX_HITS:
            return
        changed = []
        for n, address in self.addresses.items():
            value = self.read(address, 1)[0]
            if value != self.last[n]:
                changed.append(n)
                self.last[n] = value
        stack = struct.unpack('<16I', self.read(regs['ESP'], 64))
        chain, ebp = [], regs['EBP']
        for _ in range(6):
            try:
                prev, ret = struct.unpack('<II', self.read(ebp, 8))
            except RuntimeError:
                break
            chain.append(ret)
            if prev <= ebp or prev - ebp > 0x10000:
                break
            ebp = prev
        self.record['writer_hits'].append({'at': at, 'changed': changed, 'values': dict(self.last), 'eip': regs['EIP'],
                                           'regs': {k: regs[k] for k in ('EAX', 'EBX', 'ECX', 'EDX', 'ESI', 'EDI', 'EBP', 'ESP')},
                                           'stack': list(stack), 'ebpChain': chain})

    def finish(self):
        if not self.record['writer_hits']:
            self.record['problems'].append('no back-buffer writes observed')
