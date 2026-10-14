"""N/A - DOS oracle harness for the first map-geometry port contracts.

Capture one real entry/exit per function. Additional fixtures invoke the
unchanged DOS body in a private experiment, with interrupts masked and every
changed byte/register restored before the connected game resumes.
"""
import time
from probe_tail_write import rsp_registers

BASE = 0x1E0000
SPECS = {
    'sub_00010976': (0x10976, 0x10A17, bytes.fromhex('535156575589e5')),
    'sub_00048105': (0x48105, 0x48171, bytes.fromhex('56575589e5')),
}
REGISTER_INDEX = {'EAX': 0, 'ECX': 1, 'EDX': 2, 'EBX': 3, 'ESP': 4,
                  'EBP': 5, 'ESI': 6, 'EDI': 7, 'EIP': 8, 'EFLAGS': 9}


class GeometryProbe:
    def __init__(self, rsp, qmp, read, record):
        self.rsp, self.qmp, self.read, self.record = rsp, qmp, read, record
        self.points, self.pending, self.done = {}, {}, set()
        record['geometry_contracts'] = []

    def write(self, address, data):
        for i in range(0, len(data), 512):
            part = data[i:i + 512]
            if self.rsp.command(f'M{address + i:x},{len(part):x}:{part.hex()}') != 'OK':
                raise RuntimeError('DOS fixture memory write failed')

    def set_regs(self, raw, changes):
        for name, value in changes.items():
            i = REGISTER_INDEX[name] * 8
            raw = raw[:i] + value.to_bytes(4, 'little').hex() + raw[i + 8:]
        if self.rsp.command('G' + raw) != 'OK':
            raise RuntimeError('DOS fixture register write failed')

    def arm(self, exe, delta):
        self.delta = delta
        for name, (entry, end, prefix) in SPECS.items():
            for v, phase, expected in ((entry, 'entry', prefix),
                                       (end, 'exit', b'\xc2\x04\x00' if name.endswith('48105') else b'\xc3')):
                f = v + 0x482A4
                address = f + delta
                if exe[f:f + len(expected)] != expected or self.read(address, len(expected)) != expected:
                    raise RuntimeError(f'geometry boundary mismatch: {name} {phase}')
                if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                    raise RuntimeError('geometry breakpoint rejected')
                self.points[address] = (name, phase)

    def inputs(self, name, regs):
        if name.endswith('10976'):
            style = self.read(BASE + 0xCCB1, 1)[0]
            return {'style': style,
                    'maxWidth': int.from_bytes(self.read(BASE + 0xCC88, 2), 'little'),
                    'maxHeight': int.from_bytes(self.read(BASE + 0xCC86, 2), 'little'),
                    'recordHex': self.read(BASE + 0x21D6 + style * 24, 24).hex(),
                    'widthBefore': self.read(regs['EAX'], 2).hex(),
                    'heightBefore': self.read(regs['EDX'], 2).hex(),
                    'aliasOutputs': regs['EAX'] == regs['EDX']}
        index = int.from_bytes(self.read(regs['ESP'] + 4, 4), 'little')
        return {**{k.lower(): regs[k] for k in ('EAX', 'EDX', 'EBX', 'ECX')},
                'index': index,
                'rowBefore': self.read(BASE + 0xC61C + (index & 255) * 20, 20).hex()}

    def outputs(self, name, inputs, before, after):
        if name.endswith('10976'):
            return {'widthHex': self.read(before['EAX'], 2).hex(),
                    'heightHex': self.read(before['EDX'], 2).hex(),
                    'eax': after['EAX']}
        return {'rowHex': self.read(BASE + 0xC61C + (inputs['index'] & 255) * 20, 20).hex(),
                'eax': after['EAX'], 'edx': after['EDX']}

    def hit(self, regs, at):
        name, phase = self.points[regs['EIP']]
        if phase == 'entry':
            self.pending[name] = {'functionId': name, 'kind': 'connected-poland',
                                  'at': at, 'input': self.inputs(name, regs),
                                  'registersBefore': regs.copy()}
            return
        event = self.pending.pop(name)
        before = event['registersBefore']
        if regs['ESP'] != before['ESP']:
            raise RuntimeError('geometry entry/exit stack mismatch')
        event['output'] = self.outputs(name, event['input'], before, regs)
        event['registersAfter'] = regs.copy()
        self.record['geometry_contracts'].append(event)
        # Retain one connected witness. Remove both breakpoints before isolated calls.
        for address in [p for p, pair in self.points.items() if pair[0] == name]:
            self.rsp.command(f'z0,{address:x},1')
            del self.points[address]
        self.isolated(name)
        self.done.add(name)

    def isolated(self, name):
        original_raw = self.rsp.command('g')
        original = rsp_registers(original_raw)
        saved = []
        def save_write(address, data):
            saved.append((address, self.read(address, len(data))))
            self.write(address, data)
        private = 0xF00000
        stack, buffer = private + 0x100, private + 0x200
        # Includes every callee spill/local beneath the synthetic stack, not
        # just the explicitly written return slot and output buffers.
        save_write(private, self.read(private, 0x300))
        self.write(private, b'\x90')
        self.write(stack, bytes(16))
        self.write(buffer, bytes.fromhex('a5' * 16))
        if self.rsp.command(f'Z0,{private:x},1') != 'OK':
            raise RuntimeError('private return breakpoint rejected')
        if name.endswith('10976'):
            cases = [(0, 0, 0, 0, 0, 0, 0, False),
                     (1, 23, 15, 0, 11, 0, 17, False),
                     (255, 65535, 65535, 255, 255, 255, 255, False),
                     (0, 65535, 32768, 1, 1, 1, 1, False),
                     (3, 255, 255, 0, 255, 0, 255, False),
                     (2, 24, 17, 7, 9, 13, 2, True)]
        else:
            cases = [(0, 0, 0, 0, 0),
                     (0x12345678, 0xABCDEF01, 0xFFFF0001, 0x80008000, 1),
                     (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 255),
                     (65536, 65537, 65538, 65539, 0xABCD0100)]
        try:
            for case in cases:
                checkpoint = len(saved)
                changes = {'ESP': stack, 'EIP': SPECS[name][0] + 0x16D000,
                           'EFLAGS': original['EFLAGS'] & ~0x300}
                if name.endswith('10976'):
                    style, width, height, sx, ox, sy, oy, alias = case
                    data = bytearray(24)
                    data[2], data[0], data[11], data[7] = sx, ox, sy, oy
                    save_write(BASE + 0xCCB1, bytes([style]))
                    save_write(BASE + 0xCC88, width.to_bytes(2, 'little'))
                    save_write(BASE + 0xCC86, height.to_bytes(2, 'little'))
                    save_write(BASE + 0x21D6 + style * 24, data)
                    save_write(buffer, bytes.fromhex('a5' * 16))
                    changes.update(EAX=buffer + 1, EDX=buffer + (1 if alias else 3))
                    self.write(stack, private.to_bytes(4, 'little'))
                else:
                    ax, dx, bx, cx, index = case
                    save_write(BASE + 0xC61C + (index & 255) * 20, bytes.fromhex('a5' * 20))
                    changes.update(EAX=ax, EDX=dx, EBX=bx, ECX=cx)
                    self.write(stack, private.to_bytes(4, 'little') + index.to_bytes(4, 'little'))
                self.set_regs(original_raw, changes)
                before = rsp_registers(self.rsp.command('g'))
                inputs = self.inputs(name, before)
                self.qmp.hmp('cont')
                limit = time.monotonic() + 3
                while self.qmp._cmd({'execute': 'query-status'})['return']['running']:
                    if time.monotonic() > limit:
                        self.qmp.hmp('stop')
                        raise RuntimeError('isolated DOS function timed out')
                    time.sleep(0.002)
                after = rsp_registers(self.rsp.command('g'))
                if after['EIP'] != private:
                    raise RuntimeError('isolated DOS function returned to wrong PC')
                expected_sp = stack + (8 if name.endswith('48105') else 4)
                if after['ESP'] != expected_sp:
                    raise RuntimeError('isolated DOS function stack imbalance')
                preserved = ('EBX', 'ECX', 'ESI', 'EDI', 'EBP')
                if any(after[r] != before[r] for r in preserved):
                    raise RuntimeError('DOS function violated recovered register preservation')
                self.record['geometry_contracts'].append({
                    'functionId': name, 'kind': 'isolated-dos-body', 'input': inputs,
                    'output': self.outputs(name, inputs, before, after),
                    'registersBefore': before, 'registersAfter': after,
                    'interruptsMasked': True})
                for address, data in reversed(saved[checkpoint:]):
                    self.write(address, data)
                del saved[checkpoint:]
        finally:
            self.qmp.hmp('stop')
            self.rsp.command(f'z0,{private:x},1')
            for address, data in reversed(saved):
                self.write(address, data)
            self.set_regs(original_raw, {})

    def finish(self):
        if self.pending or self.done != set(SPECS):
            self.record['problems'].append('geometry contracts not completed for both functions')
