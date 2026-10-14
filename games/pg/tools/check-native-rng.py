#!/usr/bin/env python3
"""N/A - native RNG fixture build and independent DOS output comparison."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'F030Method'))
from validation.checkpoints import compare as compare_checkpoints, byte_difference
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--translated', action='store_true',
                    help='run the x86->68000 generated functions (tools/x86x) instead of src/common/rng.s')
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
fixture_path = ROOT / 'tests/fixtures/dos-rng.json'
fixture = json.loads(fixture_path.read_text())
if sha(ROOT / 'game/EXE/PANZER.EXE') != fixture['authority']:
    raise ValueError('wrong DOS build')
inputs, expected = bytearray(), bytearray()
ids = {'sub_00063375': 1, 'sub_0006337B': 2, 'sub_0006339F': 3}
for case in fixture['cases']:
    inputs.extend(bytes([ids[case['functionId']], 0, 0, 0]))
    inputs.extend(bytes.fromhex(case['input']['seedHex']))
    inputs.extend(struct.pack('<I', case['input']['eax']))
    expected.extend(bytes.fromhex(case['output']['seedHex']))
    expected.extend(struct.pack('<I', case['output']['eax']))
(out / 'rng-input.bin').write_bytes(inputs)
(out / 'rng-input.inc').write_text(f'NUM_CASES equ {len(fixture["cases"])}\n')
(out / 'expected.bin').write_bytes(expected)
toolroot = ROOT.parent / 'F030Arcade/third_party/chorensha/tools'
vasm = Path(os.environ.get('VASM', toolroot / 'vasmm68k_mot_mac')).resolve()
vlink = Path(os.environ.get('VLINK', toolroot / 'vlink_mac')).resolve()
hatari = Path(shutil.which(os.environ.get('HATARI', 'hatari'))).resolve()
tos = Path(os.environ.get('TOS', ROOT.parent / 'F030Comanche/tools/toolchain/tos402.rom')).resolve()
assemble = [str(vasm), str(ROOT / 'src/target/falcon/rng-fixtures.s'), '-quiet', '-Felf',
            '-m68000', '-I' + str(ROOT / 'src/common'), '-o', str(out / 'rng.o'),
            '-L', str(out / 'rng.lst')]
link = [str(vlink), str(out / 'rng.o'), '-q', '-Rstd', '-b', 'ataritos',
        '-tos-flags', '1', '-e', '_main', '-M', '-o', str(out / 'PGRNG.TOS')]
if args.translated:
    # The harness includes "rng.s"; vasm finds this generated file in the working directory first.
    subprocess.run([sys.executable, str(ROOT / 'tools/x86x/translate.py'), 'sub_00063375', 'sub_0006337B',
                    'sub_0006339F', '--out', str(out / 'rng.s'), '--report', str(out / 'translate.report.txt')],
                   check=True)
subprocess.run(assemble, cwd=out, check=True)
with (out / 'PGRNG.map').open('w') as log:
    subprocess.run(link, cwd=out, check=True, stdout=log, stderr=subprocess.STDOUT)
command = [str(hatari), '--machine', 'falcon', '--cpulevel', '3', '--cpuclock', '16',
           '--cpu-exact', 'true', '--compatible', 'true', '--frameskips', '0', '--fpu', 'none',
           '--memsize', '4', '--tos', str(tos), '--patch-tos', 'true', '--mmu', 'true',
           '--dsp', 'off', '--monitor', 'rgb', '--sound', 'off', '--fast-boot', 'true',
           '--fast-forward', 'true', '--confirm-quit', 'off', '--disable-video', 'on',
           '--run-vbls', '1200', '--alert-level', 'fatal', 'PGRNG.TOS']
sources = [ROOT / 'src/common/rng.s', ROOT / 'src/common/x86rt.i', ROOT / 'tools/x86x/translate.py',
           ROOT.parent / 'F030Method/validation/flags.py', ROOT.parent / 'F030Method/validation/checkpoints.py',
           ROOT / 'src/target/falcon/rng-fixtures.s', Path(__file__)]
if args.translated:
    sources.append(out / 'rng.s')
record = {'status': 'Unproven', 'assemble': assemble, 'link': link, 'command': command,
          'sha256': {str(p): sha(p) for p in [vasm,vlink,hatari,tos,fixture_path,out/'PGRNG.TOS',*sources]}}
try:
    with (out / 'hatari.log').open('w') as log:
        proc = subprocess.run(command, cwd=out, stdin=subprocess.DEVNULL,
                              stdout=log, stderr=subprocess.STDOUT, timeout=60)
    record['hatariReturncode'] = proc.returncode
    result = out / 'PGRNG.OUT'
    actual = result.read_bytes() if result.is_file() else b''
    record['checkpointComparison'] = compare_checkpoints(
        [{'key': f'{case["functionId"]}:{i}', 'state': {'outputHex': expected[i * 8:(i + 1) * 8].hex()}}
         for i, case in enumerate(fixture['cases'])],
        [{'key': f'{case["functionId"]}:{i}', 'state': {'outputHex': actual[i * 8:(i + 1) * 8].hex()}}
         for i, case in enumerate(fixture['cases'])], ['outputHex'])
    record['firstByteDifference'] = byte_difference(expected, actual)
    if proc.returncode or actual != expected:
        raise RuntimeError(f'RNG differs from DOS: {len(actual)}/{len(expected)} bytes; see {out}')
    record.update(status='Verified RNG contract fixtures', implementation='translated' if args.translated else 'hand-written', bytesCompared=len(actual),
                  cases=len(fixture['cases']), resultSha256=sha(result))
    print(f'PASS {len(fixture["cases"])} native RNG fixtures ({"x86-translated" if args.translated else "hand-written"}), {len(actual)} DOS bytes, Falcon030 4MB')
finally:
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
