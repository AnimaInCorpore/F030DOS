#!/usr/bin/env python3
"""Capture controlled shake inputs/outputs in the running shipped DOS ISR.

Target artefact. Uses a disposable QEMU disk snapshot; edits only the three
shake-state dwords while stopped at 00001DB5, never the DOS instructions.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from inspect_qemu_state import Qmp, default_hdd, QEMU, ROOT
from dump_marcher_tables import wait_for_program, linear
from rsp import Rsp


def main():
    root = Path(ROOT)
    out = root / 'build/shake-contract'
    out.mkdir(parents=True, exist_ok=True)
    hdd = default_hdd()
    geometry = json.loads(Path(hdd + '.geom.json').read_text())
    command = [QEMU, '-M', 'pc', '-cpu', '486', '-m', '16', '-snapshot',
               '-drive', f'file={hdd},format=raw,if=none,id=hd0',
               '-device', 'ide-hd,drive=hd0,bus=ide.0,unit=0,' +
               ','.join(f'{k}={geometry[k]}' for k in ('cyls', 'heads', 'secs')),
               '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
               '-qmp', 'tcp:127.0.0.1:4677,server=on,wait=off',
               '-gdb', 'tcp:127.0.0.1:4678']
    with (out / 'qemu.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            qmp = Qmp(4677)
            assert wait_for_program(qmp, process, 120), 'DOS startup not reached'
            rsp = Rsp(4678, timeout=60)
            entry, done, state = linear(0x1db5), linear(0x1e03), linear(0x19db8)
            assert rsp.set_break(entry) == 'OK'
            assert rsp.cont_until_stop(), 'timer ISR not reached'
            image = root / 're/unpacked/comanche-flat32.bin'
            image_bytes = image.read_bytes()
            assert hashlib.sha256(image_bytes).hexdigest() == 'a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c'
            assert bytes.fromhex(rsp.cmd(f'm{entry:x},4e')) == image_bytes[0x1db5:0x1e03], 'Live ISR differs from selected DOS image'
            rows = []
            cases = [(seed, phase, count) for seed in (0, 1, 0xffffffff, 0x80000000, 0xa50a50a0)
                     for phase in (0, 3) for count in (0, 1, 2, 10)]
            for index, values in enumerate(cases):
                if index:
                    assert rsp.cont_until_stop(), 'next timer ISR not reached'
                registers = qmp.hmp('info registers')
                # Verify the phase against QMP independently of the RSP stop reply.
                assert 'EIP=00001db5' in registers, registers
                payload = struct.pack('<3I', *values).hex()
                assert rsp.cmd(f'M{state:x},c:{payload}') == 'OK'
                assert rsp.clear_break(entry) == 'OK'
                assert rsp.set_break(done) == 'OK'
                assert rsp.cont_until_stop(), 'timer exit not reached'
                assert 'EIP=00001e03' in qmp.hmp('info registers')
                actual = bytes.fromhex(rsp.cmd(f'm{state:x},c'))
                rows.append({'input': list(values), 'output': list(struct.unpack('<3I', actual))})
                assert rsp.clear_break(done) == 'OK'
                assert rsp.set_break(entry) == 'OK'
            image = root / 're/unpacked/comanche-flat32.bin'
            result = {'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                      'entry': '00001DB5', 'exit': '00001E03',
                      'state': ['00019DB8', '00019DBC', '00019DC0'],
                      'command': command, 'rows': rows}
            (out / 'dos.json').write_text(json.dumps(result, indent=2) + '\n')
            print(f'Captured {len(rows)} DOS ISR cases -> {out / "dos.json"}', flush=True)
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
