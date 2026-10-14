"""N/A - capture original Poland loader state; no game implementation."""
import hashlib
import capstone

BASE = 0x1E0000
SPECS = {'sub_00037216': (0x37216, 0x37E74),
         'sub_00037E75': (0x37E75, 0x382DB),
         'sub_0003AFF3': (0x3AFF3, 0x3B290)}


class LoaderStateProbe:
    def __init__(self, rsp, read, out, record):
        self.rsp, self.read, self.out, self.record = rsp, read, out, record
        self.points, self.pending, self.done = {}, {}, set()
        self.read_pending, self.positions = {}, {}
        self.string_pending = {}
        record['loader_state'] = []
        record['loader_reads'] = []
        record['loader_strings'] = []

    def arm(self, exe, delta):
        for name, (entry, end) in SPECS.items():
            for v, phase, prefix in ((entry, 'entry', bytes.fromhex('53515256575589e5')),
                                      (end, 'exit', b'\xc3')):
                f = v + 0x482A4
                address = f + delta
                if exe[f:f + len(prefix)] != prefix or self.read(address, len(prefix)) != prefix:
                    raise RuntimeError(f'loader state boundary mismatch: {name}')
                if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                    raise RuntimeError('loader state breakpoint rejected')
                self.points[address] = (name, phase)
            decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
            raw = exe[entry + 0x482A4:end + 0x482A4]
            for ins in decoder.disasm(raw, entry):
                if ins.mnemonic != 'call' or ins.op_str != '0x66170':
                    continue
                for v, phase in ((ins.address, 'read-entry'),
                                 (ins.address + ins.size, 'read-exit')):
                    f, address = v + 0x482A4, v + 0x482A4 + delta
                    # The original five-byte call and following instruction
                    # establish this boundary; relocated operands after it may differ.
                    expected = exe[f:f + (5 if phase == 'read-entry' else 1)]
                    if self.read(address, len(expected)) != expected:
                        raise RuntimeError(f'loader read boundary mismatch: {v:x}')
                    if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                        raise RuntimeError('loader read breakpoint rejected')
                    self.points[address] = (name, phase)
        for name, entry, end, prefix in (
                ('sub_00060907', 0x60907, 0x60925, bytes.fromhex('51508a0a')),
                ('sub_00060926', 0x60926, 0x6095C, bytes.fromhex('51565789c7'))):
            for v, phase, expected in ((entry, 'string-entry', prefix),
                                        (end, 'string-exit', b'\xc3')):
                address, f = v + 0x482A4 + delta, v + 0x482A4
                if exe[f:f + len(expected)] != expected or self.read(address, len(expected)) != expected:
                    raise RuntimeError('string helper boundary mismatch')
                if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                    raise RuntimeError('string helper breakpoint rejected')
                self.points[address] = (name, phase)

    def memory(self, address, size):
        return b''.join(self.read(address + i, min(4096, size - i)) for i in range(0, size, 4096))

    def save(self, name, data):
        (self.out / name).write_bytes(data)
        return {'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

    def hit(self, regs, at):
        name, phase = self.points[regs['EIP']]
        if phase == 'string-entry':
            if not self.pending:
                return
            source = self.read(regs['EDX'], 64)
            destination = self.read(regs['EAX'], 64)
            if 0 not in source or 0 not in destination:
                raise RuntimeError('string capture exceeds terminated 64-byte scope')
            if regs['EAX'] == regs['EDX']:
                raise RuntimeError('this string fixture requires distinct buffers')
            self.string_pending[name] = {'functionId': name, 'at': at,
                'input': {'sourceHex': source.hex(), 'destinationHex': destination.hex()},
                'registersBefore': regs.copy()}
            return
        if phase == 'string-exit':
            if name not in self.string_pending:
                return
            event = self.string_pending.pop(name)
            before = event['registersBefore']
            if regs['ESP'] != before['ESP'] or any(regs[r] != before[r]
                    for r in ('EBX', 'ECX', 'ESI', 'EDI', 'EBP')):
                raise RuntimeError('string helper register/stack contract differs')
            event.update(registersAfter=regs.copy(), output={
                'destinationHex': self.read(before['EAX'], 64).hex(),
                'eaxReturnsDestination': regs['EAX'] == before['EAX'],
                'edxSourceDelta': (regs['EDX'] - before['EDX']) & 0xffffffff})
            self.record['loader_strings'].append(event)
            return
        if phase == 'read-entry':
            size = regs['EDX'] * regs['EBX']
            if size > 0x20000:
                raise RuntimeError('loader read exceeds bounded capture scope')
            stream = regs['ECX']
            self.read_pending[name] = {
                'functionId': name, 'calleeId': 'sub_00066170',
                'callVaddr': regs['EIP'] - 0x16D000, 'at': at,
                'destination': regs['EAX'], 'stream': stream,
                'fileOffset': self.positions.get((name, stream), 0),
                'itemSize': regs['EDX'], 'itemCount': regs['EBX'],
                'registersBefore': regs.copy()}
            return
        if phase == 'read-exit':
            # Some return boundaries are also branch joins (e.g. 0x38199).
            # A hit without the paired call is not an fread return witness.
            if name not in self.read_pending:
                return
            event = self.read_pending.pop(name)
            if regs['EIP'] - 0x16D000 != event['callVaddr'] + 5:
                raise RuntimeError('loader read returned at the wrong boundary')
            if regs['ESP'] != event['registersBefore']['ESP']:
                raise RuntimeError('loader stream read stack mismatch')
            if regs['EAX'] > event['itemCount']:
                raise RuntimeError('loader stream returned too many items')
            size = regs['EAX'] * event['itemSize']
            number = len(self.record['loader_reads'])
            event.update(returnedItems=regs['EAX'], registersAfter=regs.copy(),
                         data=self.save(f'loader-read-{number:03}.bin',
                                        self.memory(event['destination'], size)))
            self.positions[(name, event['stream'])] = event['fileOffset'] + size
            self.record['loader_reads'].append(event)
            return
        arena = self.memory(BASE, 0x33240)
        event = {'functionId': name, 'phase': phase, 'at': at, 'registers': regs.copy(),
                 'arena': self.save(name + '-' + phase + '.obj2', arena)}
        if phase == 'entry':
            self.pending[name] = regs['ESP']
        else:
            if self.pending.pop(name) != regs['ESP']:
                raise RuntimeError('loader entry/exit stack mismatch')
            def u16(offset):
                return int.from_bytes(arena[offset:offset + 2], 'little')
            def u32(offset):
                return int.from_bytes(arena[offset:offset + 4], 'little')
            cells = (u16(0xCC90) + 1) * (u16(0xCC8E) + 1)
            if cells > 0x20000:
                raise RuntimeError('loader array exceeds bounded capture scope')
            event.update(maxWidth=u16(0xCC90), maxHeight=u16(0xCC8E), cells=cells)
            for field, offset in (('stmWords', 0xCB84), ('mapWords', 0x17934)):
                address = u32(offset)
                event[field] = {'address': address, **self.save(
                    name + '-' + field + '.bin', self.memory(address, cells * 2))}
            event['layers'] = []
            for index in range(arena[0x21BE]):
                layer = arena[0xBA94 + arena[0x21B9] * 15 + index]
                if arena[0x21C0 + layer] or arena[0xCCA1 + layer] not in (1, 2):
                    continue
                width = arena[0xCCA1 + layer]
                address = u32(0xCBA0 + layer * 4)
                event['layers'].append({'index': index, 'layer': layer,
                    'itemSize': width, 'address': address, **self.save(
                        f'{name}-layer-{layer:02}.bin', self.memory(address, cells * width))})
            for address in [p for p, pair in self.points.items() if pair[0] == name]:
                self.rsp.command(f'z0,{address:x},1')
                del self.points[address]
            self.done.add(name)
        self.record['loader_state'].append(event)

    def finish(self):
        if self.pending or self.read_pending or self.string_pending or self.done != set(SPECS):
            self.record['problems'].append('requested loader/class state contracts did not complete')
