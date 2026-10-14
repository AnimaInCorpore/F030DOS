#!/usr/bin/env python3
"""Compare production debrief number/percentage routines to DOS call fixtures.

N/A - target validation harness. Extracts the actual native routine bodies;
DOS fixture outputs, rather than a second arithmetic model, decide equality.
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
    parser.add_argument('--source', type=Path, default=ROOT / 'src/debrief.s')
    parser.add_argument('--cpu', type=int, choices=(68030, 68060), action='append')
    parser.add_argument('--fixtures', type=Path, default=ROOT / 'work/replay_dos')
    args = parser.parse_args()
    production = args.source.read_text()
    routines = '\n'.join(name + '\n' + production.split('\n' + name + '\n', 1)[1].split('\n        rts', 1)[0] + '\n        rts'
                         for name in ('debrief_percent', 'debrief_number'))
    expected = bytearray()
    initial = bytearray()
    commands = []
    identities = {}
    counts = {}
    for kind, entry in (('format-number', '00028C25'), ('percent', '000286F9')):
        path = args.fixtures / f'dos-call-{kind}.json'
        fixture = json.loads(path.read_text())
        if fixture['entry'] != entry or not fixture['cases']:
            raise ValueError(f'Missing or wrong DOS fixture: {path}')
        identities[kind] = hashlib.sha256(path.read_bytes()).hexdigest()
        counts[kind] = len(fixture['cases'])
        for case in fixture['cases']:
            offset = len(expected)
            buffer = bytes.fromhex(case['buffer_out'])
            expected += buffer
            initial += bytes([0xfc if kind == 'format-number' else 0xaa]) * len(buffer)
            commands.append(f'        lea results+{offset + fixture["base"]},a1')
            if kind == 'format-number':
                commands += [f'        move.l #${case["value"]:08x},d0',
                             f'        move.l #{case["width"]},d1', '        bsr debrief_number']
            else:
                commands += [f'        move.l #${case["score_in"]:08x},debrief_score',
                             '        clr.l debrief_last_pct',
                             f'        move.l #${case["total"]:08x},d1',
                             f'        move.l #${case["count"]:08x},d2', '        bsr debrief_percent',
                             f'        move.l debrief_score,results+{len(expected)}',
                             f'        move.l debrief_last_pct,results+{len(expected)+4}']
                expected += case['score_out'].to_bytes(4, 'big') + case['last_out'].to_bytes(4, 'big')
                initial += bytes(8)
    for cpu in args.cpu or (68030, 68060):
        out = ROOT / f'build/check-debrief-{cpu}'
        out.mkdir(parents=True, exist_ok=True)
        (out / 'initial.bin').write_bytes(initial)
        (out / 'test.s').write_text('        text\n        global _main\n_main\n' +
                                  '\n'.join(commands) + '\ntest_done\n        clr.w -(sp)\n        trap #1\n' +
                                  routines + '\n        data\nresults\n' +
                                  f'        incbin "{out / "initial.bin"}"\n' +
                                  '        bss\ndebrief_score\n        ds.l 1\ndebrief_last_pct\n        ds.l 1\n        end\n')
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
        if not (out / 'results.bin').is_file():
            raise AssertionError(f'MC{cpu}: production routines did not reach test_done; see {out / "hatari.log"}')
        actual = (out / 'results.bin').read_bytes()
        if actual != expected:
            index = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), min(len(actual), len(expected)))
            raise AssertionError(f'MC{cpu}: DOS output differs at byte {index}')
        result = {'cpu': cpu, 'cases': counts, 'status': 'PASS', 'fixtures_sha256': identities,
                  'source_sha256': hashlib.sha256(production.encode()).hexdigest(),
                  'program_sha256': hashlib.sha256((out / 'check.tos').read_bytes()).hexdigest(),
                  'output_sha256': hashlib.sha256(actual).hexdigest()}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'PASS MC{cpu}: {counts} DOS cases, buffers and score counters', flush=True)


if __name__ == '__main__':
    main()
