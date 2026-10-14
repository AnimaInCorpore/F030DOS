#!/usr/bin/env python3
"""Execute production FUN_00029F36/refresh in Hatari against DOS captures.

N/A - target validation harness. The routine is extracted verbatim from
src/debrief.s, with production constants/macros; no semantic transcription.
Capture: python3 work/dos_call.py roster-sort --out
work/replay_dos/dos-call-roster-sort.json
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('cpu_check', ROOT / 'tools/check-cpu-compatibility.py')
support = module_from_spec(spec)
spec.loader.exec_module(support)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'work/replay_dos/dos-call-roster-sort.json')
    parser.add_argument('--source', type=Path, default=ROOT / 'src/debrief.s',
                        help='Production source; override for regression negative controls')
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    cases = fixture['cases']
    if fixture['entry'] != '00029F36' or not cases:
        raise ValueError('Expected nonempty FUN_00029F36 DOS fixture')
    production = args.source.read_text()
    swap_macro = 'BSWAP   macro' + production.split('BSWAP   macro', 1)[1].split('endm', 1)[0] + 'endm'
    routine = production.split('\nroster_sort\n', 1)[1].split('\nroster_save\n', 1)[0]
    constants = '\n'.join(line for line in (ROOT / 'src/inc/comanche.s').read_text().splitlines()
                          if line.startswith('ROSTER_'))
    inputs = bytearray()
    expected = bytearray()
    for case in cases:
        before = bytes.fromhex(case['roster_in'])
        after = bytes.fromhex(case['roster_out'])
        if len(before) != 1450 or len(after) != 1450:
            raise ValueError('Invalid roster size')
        inputs += before + bytes([case['selected_in'], 0])
        expected += after + bytes([case['selected_out'], 0])
    for cpu in (68030, 68060):
        out = ROOT / f'build/check-roster-{cpu}'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'inputs.bin').write_bytes(inputs)
        source = f'''
        include "src/inc/cpu.s"
{constants}
{swap_macro}
        text
        global _main
_main
        lea inputs,a3
        lea results,a4
        move.w #{len(cases)-1},d7
.next
        lea roster_buffer,a0
        move.w #1449,d6
.load
        move.b (a3)+,(a0)+
        dbra d6,.load
        move.b (a3)+,debrief_pilot
        addq.l #1,a3
        bsr roster_sort
        lea roster_buffer,a0
        move.w #1449,d6
.save
        move.b (a0)+,(a4)+
        dbra d6,.save
        move.b debrief_pilot,(a4)+
        clr.b (a4)+
        dbra d7,.next
test_done
        clr.w -(sp)
        trap #1
roster_sort
{routine}
        data
inputs
        incbin "{out / 'inputs.bin'}"
        bss
roster_buffer
        ds.b 1450
debrief_pilot
        ds.w 1
results
        ds.b {len(expected)}
        end
'''
        (out / 'test.s').write_text(source)
        vasm = os.environ.get('VASM', str(support.TOOLS / 'vasmm68k_mot_mac'))
        vlink = os.environ.get('VLINK', str(support.TOOLS / 'vlink_mac'))
        support.run([vasm, str(out / 'test.s'), '-quiet', '-Felf', f'-m{cpu}',
                     f'-DTARGET_CPU={cpu}', '-o', str(out / 'test.o')], ROOT, out / 'assemble.log')
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
            index = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), min(len(actual), len(expected)))
            raise AssertionError(f'MC{cpu}: case {index // 1452}, byte {index % 1452} differs')
        result = {'cpu': cpu, 'cases': len(cases), 'status': 'PASS',
                  'fixture_sha256': hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
                  'source_sha256': hashlib.sha256(production.encode()).hexdigest(),
                  'program_sha256': hashlib.sha256((out / 'check.tos').read_bytes()).hexdigest(),
                  'output_sha256': hashlib.sha256(actual).hexdigest()}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'PASS MC{cpu}: {len(cases)} DOS rosters and selected pilots', flush=True)


if __name__ == '__main__':
    main()
