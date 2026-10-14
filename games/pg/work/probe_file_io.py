"""N/A - host oracle probe at checked DOS file-I/O instruction boundaries.

Addresses use the selected executable's file coordinates. The caller supplies
the measured relocation delta and a stopped, flat, paging-disabled guest.
This captures runtime observations; it does not implement game file semantics.
"""
import hashlib


POINTS = {
    0xB0428: ('open_return', bytes.fromhex('83c40c5f5e5a595bc3')),
    0xB0139: ('read_before', bytes.fromhex('cd21d1d0d1c8')),
    0xB013F: ('read_after', bytes.fromhex('89c689442408')),
    0xB0171: ('read_before', bytes.fromhex('cd21d1d0d1c8')),
    0xB0177: ('read_after', bytes.fromhex('89c389c6')),
    0xB3BD4: ('read_before', bytes.fromhex('cd21d1d0d1c8')),
    0xB3BDA: ('read_after', bytes.fromhex('89c285c07d0a')),
    0xB021B: ('seek_before', bytes.fromhex('cd2166368907')),
    0xB0242: ('seek_after', bytes.fromhex('83c4045f59c3')),
    0xB3E4C: ('close_before', bytes.fromhex('cd21d1d0d1c8')),
    0xB3E52: ('close_after', bytes.fromhex('85c07c0e')),
}


class FileIoProbe:
    def __init__(self, rsp, read_memory, out, record):
        self.rsp, self.read_memory = rsp, read_memory
        self.out, self.record = out, record
        self.points, self.opens, self.pending, self.handles = {}, {}, {}, {}
        record['file_io'] = []

    def arm(self, exe, delta):
        for offset, (kind, prefix) in POINTS.items():
            address = offset + delta
            if exe[offset:offset + len(prefix)] != prefix:
                raise RuntimeError(f'file-I/O static prefix mismatch at {offset:#x}')
            if self.read_memory(address, len(prefix)) != prefix:
                raise RuntimeError(f'file-I/O runtime prefix mismatch at {address:#x}')
            if self.rsp.command(f'Z0,{address:x},1') != 'OK':
                raise RuntimeError(f'cannot arm file-I/O breakpoint at {address:#x}')
            self.points[address] = kind

    def on_open(self, event, regs):
        if regs['ESP'] in self.opens:
            raise RuntimeError('nested open at the same stack address')
        event['stack_hex'] = self.read_memory(regs['ESP'], 64).hex()
        self.opens[regs['ESP']] = event

    def hit(self, regs, at):
        kind = self.points[regs['EIP']]
        esp = regs['ESP']
        if kind == 'open_return':
            # Five pushes + 12 local bytes precede this epilogue.
            event = self.opens.pop(esp + 32, None)
            if event is None:
                raise RuntimeError('open return without matched entry')
            result = regs['EAX']
            event['return_eax'] = result
            event['return_at'] = at
            if result < 0x80000000:
                self.handles[result] = {'path': event['path'], 'position': 0}
            return
        operation, phase = kind.split('_')
        key = (operation, esp)
        if phase == 'before':
            if key in self.pending:
                raise RuntimeError('unmatched nested file-I/O operation')
            handle = regs['EBX']
            binding = self.handles.get(handle, {})
            event = {'kind': operation, 'at': at, 'pc': regs['EIP'],
                     'handle': handle, 'path': binding.get('path'),
                     'position': binding.get('position'), 'registers_before': regs.copy()}
            if operation == 'read':
                event.update(destination=regs['EDX'], requested=regs['ECX'])
            self.pending[key] = event
            return
        event = self.pending.pop(key, None)
        if event is None:
            raise RuntimeError('file-I/O return without matched request')
        result = regs['EAX']
        event.update(return_eax=result, return_at=at, pc_after=regs['EIP'])
        binding = self.handles.get(event['handle'])
        if result < 0x80000000:
            if operation == 'read':
                if result > event['requested'] or result > 0x100000:
                    raise RuntimeError('read result exceeds request or bounded capture size')
                data = b''.join(self.read_memory(event['destination'] + i,
                                                min(4096, result - i))
                                for i in range(0, result, 4096))
                filename = f"read-{len(self.record['file_io']):04d}.bin"
                (self.out / filename).write_bytes(data)
                event.update(data_file=filename, data_sha256=hashlib.sha256(data).hexdigest())
                if binding is not None:
                    binding['position'] += result
            elif operation == 'seek' and binding is not None:
                binding['position'] = result
            elif operation == 'close':
                self.handles.pop(event['handle'], None)
        self.record['file_io'].append(event)

    def finish(self):
        if self.opens or self.pending:
            self.record['problems'].append('incomplete file-I/O operation at capture end')
