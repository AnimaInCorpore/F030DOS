#!/usr/bin/env python3
"""N/A - production-emitter instruction/sequence bench on Musashi's 68000.

Independent integer models check result widths and branch decisions. This is a
synthetic lowering test, not DOS evidence. Native DOS gates remain mandatory.
Requires capstone and machine68k in the chosen interpreter, plus vasm/vlink.
"""
import argparse
import bisect
import hashlib
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import translate as T
from machine68k import Machine, CPUType, Register as R
from validation.profile import summarize

CODE, STACK, STOP = 0x10000, 0x80000, 0x90000


def encoding(op, size, condition):
    prefix = b'\x66' if size == 2 else b''
    # Dead compare; result-producing operation; move result to edx; conditional
    # branch choosing ebx=1/2; ret. Include byte/word/long upper-bit preservation.
    dead = prefix + (bytes.fromhex('3c55') if size == 1 else bytes.fromhex('3d55000000') if size == 4 else bytes.fromhex('3d5500'))
    byte, wide = {'add': ('00d8', '01d8'), 'sub': ('28d8', '29d8'),
                  'and': ('20d8', '21d8'), 'xor': ('30d8', '31d8'),
                  'test': ('84c0', '85c0'), 'inc': ('fec0', 'ffc0'),
                  'dec': ('fec8', 'ffc8')}[op]
    result = prefix + bytes.fromhex(byte if size == 1 else wide)
    move = prefix + bytes.fromhex('88c2' if size == 1 else '89c2')
    branch = bytes([{'je': 0x74, 'jne': 0x75, 'js': 0x78, 'jns': 0x79}[condition], 7])
    return dead + result + move + branch + bytes.fromhex('bb01000000eb05bb02000000c3')


def model(op, size, condition, regs):
    mask = (1 << (size * 8)) - 1
    a, b = regs[0] & mask, regs[3] & mask
    value = {'add': a + b, 'sub': a - b, 'and': a & b, 'xor': a ^ b,
             'test': a, 'inc': a + 1, 'dec': a - 1}[op] & mask
    zero, sign = value == 0, bool(value & (1 << (size * 8 - 1)))
    taken = {'je': zero, 'jne': not zero, 'js': sign, 'jns': not sign}[condition]
    result = list(regs)
    if op != 'test':
        result[0] = (regs[0] & ~mask) | value
    result[2] = (regs[2] & ~mask) | value
    result[3] = 2 if taken else 1
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--vectors', type=int, default=24)
    args = parser.parse_args()
    if args.vectors < 8:
        parser.error('at least eight discriminating vectors required')
    args.out.mkdir(parents=True, exist_ok=False)
    forms = [(op, size, condition) for op in ('add', 'sub', 'and', 'xor', 'test', 'inc', 'dec')
             for size in (1, 2, 4) for condition in ('je', 'jne', 'js', 'jns')]
    source = ['        include "x86rt.i"', '        section text,code']
    sites, entries = [], {}
    authority = hashlib.sha256(b''.join(encoding(*form) for form in forms)).hexdigest()
    for index, form in enumerate(forms):
        code = encoding(*form)
        for mode in ('conservative', 'optimized'):
            name = f'fixture_{index}_{mode}'
            build = T.Build('synthetic flags', code, authority, [(0x1000, 0, name)])
            lines, info = T.translate(name, build, optimize=mode == 'optimized')
            source += lines
            sites += info['sourceMap']
            entries[index, mode] = name
    generated = '\n'.join(source) + '\n'
    asm = args.out / 'flags.s'
    asm.write_text(generated)
    tools = T.ROOT.parent / 'F030Arcade/third_party/chorensha/tools'
    vasm = os.environ.get('VASM', str(tools / 'vasmm68k_mot_mac'))
    vlink = os.environ.get('VLINK', str(tools / 'vlink_mac'))
    subprocess.run([vasm, str(asm), '-quiet', '-Fvobj', '-m68000', '-I' + str(T.ROOT / 'src/common'),
                    '-o', str(args.out / 'flags.o')], check=True)
    with (args.out / 'flags.map').open('w') as stream:
        subprocess.run([vlink, '-brawbin1', '-Ttext', hex(CODE), '-M',
                        '-o', str(args.out / 'flags.bin'), str(args.out / 'flags.o')],
                       stdout=stream, stderr=subprocess.STDOUT, check=True)
    symbols = {}
    for line in (args.out / 'flags.map').read_text().splitlines():
        match = re.match(r'\s+0x([0-9a-f]{8})\s+(\S+?):', line)
        if match:
            symbols[match[2]] = int(match[1], 16)
        else:
            match = re.match(r'\s+(\S+): .*value 0x([0-9a-f]+)', line)
            if match:
                symbols[match[1]] = int(match[2], 16)
    mapping = {'sourceSha256': authority, 'generatedSha256': hashlib.sha256(generated.encode()).hexdigest(),
               'linkedSha256': hashlib.sha256((args.out / 'flags.bin').read_bytes()).hexdigest(),
               'generatorSha256': hashlib.sha256(Path(T.__file__).read_bytes()).hexdigest(), 'sites': sites}
    owners = sorted((symbols[site['label']], site['label']) for site in sites if site['emittedLines'])
    addresses = [address for address, _ in owners]
    traces = {mode: {'sourceSha256': authority, 'generatedSha256': mapping['generatedSha256'],
                     'linkedSha256': mapping['linkedSha256'],
                     'checkpoints': [], 'events': []} for mode in ('conservative', 'optimized')}
    machine = Machine(CPUType.M68000, 2048)
    binary = (args.out / 'flags.bin').read_bytes()
    machine.mem.w_block(CODE, binary)
    randomizer = random.Random(1030)
    for index, form in enumerate(forms):
        op, size, condition = form
        mask = (1 << (size * 8)) - 1
        edge = [0, 1, mask, 1 << (size * 8 - 1), (1 << (size * 8 - 1)) - 1, 2, mask - 1, 0x55]
        edge_b = [0, mask, 1, 1 << (size * 8 - 1), 1, 2, 2, 0x55]
        for vector in range(args.vectors):
            regs = [randomizer.getrandbits(32) for _ in range(6)]
            if vector < len(edge):
                regs[0] = (regs[0] & ~mask) | edge[vector]
                regs[3] = (regs[3] & ~mask) | edge_b[vector]
            want = model(op, size, condition, regs)
            key = f'{index}:{vector}'
            for mode, trace in traces.items():
                trace['checkpoints'].append(key)
                for register, value in zip((R.D0, R.D1, R.D2, R.D3, R.D4, R.D5), regs):
                    machine.cpu.w_reg(register, value)
                machine.cpu.w_reg(R.SR, 0x2000 | randomizer.randrange(32))
                machine.cpu.w_reg(R.A7, STACK)
                machine.mem.w32(STACK, STOP)
                machine.cpu.w_pc(symbols[entries[index, mode]])
                steps = 0
                while machine.cpu.r_pc() != STOP:
                    pc = machine.cpu.r_pc()
                    owner = bisect.bisect_right(addresses, pc) - 1
                    if owner < 0 or not CODE <= pc < CODE + len(binary):
                        raise RuntimeError(f'unmapped executed target PC {pc:#x}')
                    cycles = machine.cpu.execute(1).cycles
                    trace['events'].append({'checkpoint': key, 'label': owners[owner][1], 'cycles': cycles})
                    steps += 1
                    if steps > 200:
                        raise RuntimeError(f'timeout: {form} {mode} vector {vector}')
                got = [machine.cpu.r_reg(register) & 0xffffffff for register in (R.D0, R.D1, R.D2, R.D3, R.D4, R.D5)]
                if got != want or machine.cpu.r_reg(R.A7) != STACK + 4 or machine.mem.r32(STACK) != STOP:
                    raise AssertionError((form, vector, mode, regs, want, got))
    (args.out / 'source-map.json').write_text(json.dumps(mapping, indent=2) + '\n')
    results = {'kind': 'synthetic instruction tests; not DOS parity', 'forms': len(forms), 'vectors': args.vectors,
               'seed': 1030, 'python': sys.version,
               'dependencies': {str(path): hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    for path in (vasm, vlink, sys.modules['machine68k'].__file__, Path(__file__),
                                 T.ROOT / 'src/common/x86rt.i',
                                 T.ROOT.parent / 'F030Method/validation/flags.py',
                                 T.ROOT.parent / 'F030Method/validation/profile.py')},
               'sourceMapSha256': hashlib.sha256((args.out / 'source-map.json').read_bytes()).hexdigest()}
    for mode, trace in traces.items():
        (args.out / f'{mode}.events.json').write_text(json.dumps(trace) + '\n')
        results[mode] = summarize(mapping, trace)
    (args.out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
    print(f'PASS {len(forms)} forms x {args.vectors} vectors x 2 mechanisms; independent result/branch models')
    print('Musashi cycles per case:', {mode: results[mode]['cyclesPerCheckpoint'] for mode in traces})


if __name__ == '__main__':
    main()
