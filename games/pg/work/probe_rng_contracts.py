"""N/A - original DOS RNG contracts; private calls restore all memory/registers."""
import time
from probe_geometry_contracts import GeometryProbe, BASE
from probe_tail_write import rsp_registers

SPECS = {'sub_00063375': (0x63375, 0x6337A, b'\xb8'),
         'sub_0006337B': (0x6337B, 0x6339E, b'\x52\xe8'),
         'sub_0006339F': (0x6339F, 0x633AE, bytes.fromhex('5289c2'))}

class RngProbe(GeometryProbe):
    def __init__(self, rsp, qmp, read, record):
        self.rsp, self.qmp, self.read, self.record = rsp, qmp, read, record
        self.points, self.pending, self.done = {}, {}, False
        record['rng_contracts'] = []

    def arm(self, exe, delta):
        for name, (entry, end, prefix) in SPECS.items():
            for v, expected in ((entry, prefix), (end, b'\xc3')):
                address, f = v + 0x482A4 + delta, v + 0x482A4
                if exe[f:f+len(expected)] != expected or self.read(address, len(expected)) != expected:
                    raise RuntimeError('RNG checked boundary differs')
        for v, phase in ((0x6337B, 'entry'), (0x6339E, 'exit')):
            address = v + 0x482A4 + delta
            if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                raise RuntimeError('RNG breakpoint rejected')
            self.points[address] = phase

    def input(self, regs):
        return {'seedHex': self.read(BASE+0x74F0, 4).hex(), 'eax': regs['EAX']}

    def output(self, regs):
        return {'seedHex': self.read(BASE+0x74F0, 4).hex(), 'eax': regs['EAX']}

    def hit(self, regs, at):
        if self.points[regs['EIP']] == 'entry':
            self.pending = {'functionId': 'sub_0006337B', 'kind': 'connected-poland',
                'at': at, 'input': self.input(regs), 'registersBefore': regs.copy()}
            return
        event = self.pending
        if regs['ESP'] != event['registersBefore']['ESP']:
            raise RuntimeError('RNG connected stack imbalance')
        event.update(output=self.output(regs), registersAfter=regs.copy())
        self.record['rng_contracts'].append(event)
        self.pending = {}
        for address in self.points:
            self.rsp.command(f'z0,{address:x},1')
        self.points.clear()
        self.isolated()
        self.done = True

    def isolated(self):
        raw = self.rsp.command('g')
        original = rsp_registers(raw)
        private, stack = 0xF00000, 0xF00100
        saved_private, saved_seed = self.read(private, 0x300), self.read(BASE+0x74F0, 4)
        self.write(private, b'\x90')
        if self.rsp.command(f'Z0,{private:x},1') != 'OK':
            raise RuntimeError('RNG private return rejected')
        try:
            cases = [('sub_00063375', 0xA5A5A5A5, 0x12345678)]
            cases += [('sub_0006337B', seed, 0xA5A5A5A5) for seed in
                      (0, 1, 0xFFFFFFFF, 0x80000000, 0x12345678)]
            cases += [('sub_0006339F', 0xA5A5A5A5, seed) for seed in
                      (0, 1, 0xFFFFFFFF, 0x80000000)]
            chain_seed = 1
            for number in range(len(cases) + 8):
                name, seed, argument = (cases[number] if number < len(cases)
                    else ('sub_0006337B', chain_seed, 0xA5A5A5A5))
                self.write(BASE+0x74F0, seed.to_bytes(4, 'little'))
                self.write(stack, private.to_bytes(4, 'little'))
                self.set_regs(raw, {'EIP': SPECS[name][0]+0x16D000, 'ESP': stack,
                    'EAX': argument, 'EFLAGS': original['EFLAGS'] & ~0x300})
                before = rsp_registers(self.rsp.command('g'))
                inputs = self.input(before)
                self.qmp.hmp('cont')
                limit = time.monotonic()+3
                while self.qmp._cmd({'execute': 'query-status'})['return']['running']:
                    if time.monotonic()>limit:
                        self.qmp.hmp('stop')
                        raise RuntimeError('RNG DOS private call timed out')
                    time.sleep(0.002)
                after = rsp_registers(self.rsp.command('g'))
                if after['EIP'] != private or after['ESP'] != stack+4 or any(
                    before[r] != after[r] for r in ('EDX','EBX','ECX','ESI','EDI','EBP')):
                    raise RuntimeError('RNG return/register contract differs')
                output = self.output(after)
                self.record['rng_contracts'].append({'functionId': name,
                    'kind': 'isolated-dos-chain' if number >= len(cases) else 'isolated-dos-body',
                    'input': inputs, 'output': output, 'registersBefore': before,
                    'registersAfter': after, 'interruptsMasked': True})
                if number >= len(cases):
                    chain_seed = int.from_bytes(bytes.fromhex(output['seedHex']), 'little')
        finally:
            self.qmp.hmp('stop')
            self.rsp.command(f'z0,{private:x},1')
            self.write(private, saved_private)
            self.write(BASE+0x74F0, saved_seed)
            self.set_regs(raw, {})

    def finish(self):
        if not self.done or self.pending:
            self.record['problems'].append('RNG contracts did not complete')
