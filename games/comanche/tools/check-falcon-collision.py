#!/usr/bin/env python3
"""Check production flight collision decisions against instruction-bound DOS.

N/A - target validation harness. Copies only the existing collision block;
crash/terrain exits become observed results, without running their aftermath.
"""
import hashlib
import json
import os
import struct
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('cpu_check', ROOT / 'tools/check-cpu-compatibility.py')
support = module_from_spec(spec)
spec.loader.exec_module(support)


def main():
    fixture_path = ROOT / 'work/replay_dos/damage-collide.json'
    capture = json.loads(fixture_path.read_text())
    samples = capture['samples']
    if not samples:
        raise ValueError('Empty DOS collision capture')
    production = (ROOT / 'src/flight.s').read_text()
    block = production.split('\n.lock_kept\n', 1)[1].split('        ; Terrain follow,', 1)[0]
    constants = '\n'.join(line for line in (ROOT / 'src/inc/comanche.s').read_text().splitlines()
                          if line.startswith(('OBJ_STATE ', 'OBJ_X ', 'OBJ_Y ', 'OBJ_ACTIVE ', 'OBJ_ALTITUDE ', 'OBJ_SIZE ')))
    inputs = bytearray()
    expected = bytearray()
    for sample in samples:
        table = bytearray(30 * 100)
        for obj in sample['objects']:
            if obj['slot'] == 0:
                continue
            base = (obj['slot'] - 1) * 100
            struct.pack_into('>I', table, base + 8, obj['state'])
            struct.pack_into('>I', table, base + 20, obj['x'] & 0xffffffff)
            struct.pack_into('>I', table, base + 24, obj['y'] & 0xffffffff)
            table[base + 37] = obj['active']
            table[base + 38] = obj['altitude']
        player = sample['player']
        inputs += struct.pack('>IIBB', player['x'] & 0xffffffff,
                              player['y'] & 0xffffffff, player['altitude'], 0) + table
        expected += bytes([sample['outcome'] == 'collision'])
    for cpu in (68030, 68060):
        out = ROOT / f'build/check-collision-{cpu}'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'inputs.bin').write_bytes(inputs)
        source = f'''
{constants}
; Pointer identity seam: only equality is observed; no handler is called.
object_state_wreckage = $237b0
        text
        global _main
_main
        lea inputs,a3
        lea results,a4
        move.w #{len(samples)-1},d7
.next
        move.l (a3)+,flt_x
        move.l (a3)+,flt_y
        move.b (a3)+,player_altitude
        addq.l #1,a3
        lea object_table,a0
        move.w #2999,d5
.copy
        move.b (a3)+,(a0)+
        dbra d5,.copy
        bsr collision_test
        move.b d0,(a4)+
        dbra d7,.next
test_done
        clr.w -(sp)
        trap #1
collision_test
{block}
        moveq #0,d0
        rts
.crash
        moveq #1,d0
        rts
        data
inputs
        incbin "{out / 'inputs.bin'}"
        bss
flt_x
        ds.l 1
flt_y
        ds.l 1
player_altitude
        ds.w 1
object_table
        ds.b 3000
results
        ds.b {len(expected)}
        end
'''
        (out / 'test.s').write_text(source)
        vasm = os.environ.get('VASM', str(support.TOOLS / 'vasmm68k_mot_mac'))
        vlink = os.environ.get('VLINK', str(support.TOOLS / 'vlink_mac'))
        support.run([vasm, str(out / 'test.s'), '-quiet', '-Felf', f'-m{cpu}',
                     '-o', str(out / 'test.o')], ROOT, out / 'assemble.log')
        support.run([vlink, str(out / 'test.o'), '-q', '-Rstd', '-b', 'ataritos',
                     '-e', '_main', '-o', str(out / 'check.tos')], ROOT, out / 'link.log')
        support.entry_breakpoint(out, 'check.tos', 'b pc = test_done :once :file done.ini\n')
        (out / 'done.ini').write_text(f'savebin results.bin results ${len(expected):x}\nquit\n')
        (out / 'results.bin').unlink(missing_ok=True)
        command = support.emulator_command(out, cpu, 'check.tos', 'boot.ini')
        (out / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
        support.run(command, out, out / 'hatari.log')
        actual = (out / 'results.bin').read_bytes()
        if actual != expected:
            raise AssertionError(f'MC{cpu}: collision outcomes {actual.hex()} != DOS {expected.hex()}')
        result = {'cpu': cpu, 'samples': len(samples), 'status': 'PASS',
                  'fixture_sha256': hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
                  'source_sha256': hashlib.sha256(production.encode()).hexdigest(),
                  'program_sha256': hashlib.sha256((out / 'check.tos').read_bytes()).hexdigest(),
                  'output_sha256': hashlib.sha256(actual).hexdigest()}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'PASS MC{cpu}: {len(samples)} DOS collision decisions', flush=True)


if __name__ == '__main__':
    main()
