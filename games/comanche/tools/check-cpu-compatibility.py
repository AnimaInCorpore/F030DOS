#!/usr/bin/env python3
"""Execute the production wide-product macros on both Hatari CPU cores.

N/A - target test harness, not DOS game logic. Requires vasm, vlink, Hatari
and an EmuTOS ROM supporting both CPUs. Override VASM, VLINK, HATARI, TOS.
Expected signed/unsigned products are calculated independently with Python
integers. Inputs cover carry/sign boundaries and deterministic random pairs.
"""
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT.parent / 'F030Arcade/third_party/chorensha/tools'


def run(command, cwd, log, timeout=120):
    with log.open('w') as output:
        subprocess.run(command, cwd=cwd, stdout=output,
                       stderr=subprocess.STDOUT, timeout=timeout, check=True)


def emulator_command(out, cpu, program, script):
    tos = Path(os.environ.get('TOS', ROOT.parent /
                              'F030Arcade/third_party/tos/etos512de.img')).resolve()
    if not tos.is_file():
        raise RuntimeError(f'Missing ROM: {tos}; set TOS to an appropriate ROM')
    return [os.environ.get('HATARI', shutil.which('hatari') or 'hatari'),
            '--machine', 'falcon', '--cpulevel', str((cpu // 10) % 10),
            '--memsize', '14', '--tos', str(tos), '--patch-tos', 'true',
            '--mmu', 'true', '--fpu', 'none', '--dsp', 'off',
            '--frameskips', '0', '--monitor', 'rgb', '--fast-boot', 'true',
            '--sound', 'off', '--fast-forward', 'true', '--cpu-exact', 'true',
            '--compatible', 'true', '--confirm-quit', 'off', '--disable-video', 'on',
            '--run-vbls', '6000', '--harddrive', str(out),
            '--auto', 'C:\\' + program, '--parse', script,
            '--alert-level', 'fatal']


def entry_breakpoint(out, program, commands):
    (out / 'boot.ini').write_text(
        'b GemdosOpcode = $4b && OsCallParam = 0 :trace :once :file program.ini\n')
    (out / 'program.ini').write_text('b pc = TEXT :trace :once :file arm.ini\n')
    (out / 'arm.ini').write_text(f'symbols {program}\n' + commands)


def main():
    edge = [0, 1, 2, 0x7fff, 0x8000, 0xffff, 0x10000, 0x10001,
            0x7fffffff, 0x80000000, 0x80000001, 0xffff0000, 0xffffffff]
    pairs = [(a, b) for a in edge for b in edge]
    rng = random.Random(68060)
    pairs += [(rng.getrandbits(32), rng.getrandbits(32)) for _ in range(1024)]
    mask = (1 << 64) - 1
    expected = bytearray()
    for a, b in pairs:
        sa = a if a < 0x80000000 else a - (1 << 32)
        sb = b if b < 0x80000000 else b - (1 << 32)
        signed = ((sa * sb) & mask).to_bytes(8, 'big')
        expected += signed + signed + (a * b).to_bytes(8, 'big') + signed
    vasm = os.environ.get('VASM', str(TOOLS / 'vasmm68k_mot_mac'))
    vlink = os.environ.get('VLINK', str(TOOLS / 'vlink_mac'))
    for cpu in (68030, 68060):
        out = ROOT / f'build/check-cpu-{cpu}'
        out.mkdir(parents=True, exist_ok=True)
        source = r'''
        include "src/inc/cpu.s"
        global _main, test_done, products, test_status
        text
_main
        lea inputs,a0
        lea products,a1
        move.l #$44556677,d4
        move.l #$55667788,d5
        move.l #$66778899,d6
        move.w #COUNT-1,d7
.next
        move.l #$11223344,d2
        move.l (a0),d0
        move.l 4(a0),d3
        MulS64 d3
        move.l d1,(a1)+
        move.l d0,(a1)+
        cmpi.l #$11223344,d2
        bne .failed
        cmp.l 4(a0),d3
        bne .failed

        move.l (a0),d0
        move.l 4(a0),d1
        MulS64D2
        move.l d2,(a1)+
        move.l d0,(a1)+
        cmp.l 4(a0),d1
        bne .failed

        move.l (a0),d0
        move.l 4(a0),d1
        MulU64D2
        move.l d2,(a1)+
        move.l d0,(a1)+
        cmp.l 4(a0),d1
        bne .failed

        move.l (a0),d0
        MulS64 4(a0)
        move.l d1,(a1)+
        move.l d0,(a1)+
        cmpi.l #$44556677,d4
        bne .failed
        cmpi.l #$55667788,d5
        bne .failed
        cmpi.l #$66778899,d6
        bne .failed
        addq.l #8,a0
        dbra d7,.next
        move.w #1,test_status
        bra test_done
.failed
        move.w #2,test_status
test_done
        clr.w -(sp)
        trap #1
        data
inputs
INPUTS
        bss
test_status
        ds.w 1
products
        ds.b COUNT*32
        end
'''.replace('COUNT', str(len(pairs))).replace(
            'INPUTS', '\n'.join(f'        dc.l ${a:08x},${b:08x}' for a, b in pairs))
        (out / 'test.s').write_text(source)
        run([vasm, str(out / 'test.s'), '-quiet', '-Felf', f'-m{cpu}',
             f'-DTARGET_CPU={cpu}', '-o', str(out / 'test.o')], ROOT, out / 'assemble.log')
        run([vasm, 'src/cpu.s', '-quiet', '-Felf', f'-m{cpu}',
             f'-DTARGET_CPU={cpu}', '-o', str(out / 'cpu.o')], ROOT, out / 'cpu.log')
        run([vlink, str(out / 'test.o'), str(out / 'cpu.o'), '-q', '-Rstd',
             '-b', 'ataritos', '-e', '_main', '-o', str(out / 'check.tos')],
            ROOT, out / 'link.log')
        entry_breakpoint(out, 'check.tos', 'b pc = test_done :once :file done.ini\n')
        (out / 'done.ini').write_text(
            f'savebin products.bin products ${len(expected):x}\n'
            'savebin status.bin test_status $2\nquit\n')
        for name in ('products.bin', 'status.bin'):
            (out / name).unlink(missing_ok=True)
        command = emulator_command(out, cpu, 'check.tos', 'boot.ini')
        (out / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
        run(command, out, out / 'hatari.log')
        actual = (out / 'products.bin').read_bytes()
        assert (out / 'status.bin').read_bytes() == b'\0\1', 'Register preservation failed'
        assert actual == expected, f'MC{cpu}: wide-product mismatch'
        result = {'cpu': cpu, 'pairs': len(pairs), 'products': len(pairs) * 4,
                  'sha256': hashlib.sha256(actual).hexdigest(), 'status': 'PASS',
                  'program_sha256': hashlib.sha256((out / 'check.tos').read_bytes()).hexdigest()}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'PASS MC{cpu}: {len(pairs)*4} full-width products; preserved registers', flush=True)


if __name__ == '__main__':
    main()
