#!/usr/bin/env python3
"""N/A - build/run the m68k contract harness and compare captured DOS outputs."""
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
from validation.checkpoints import byte_difference
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, default=ROOT / 'build/geometry-native')
parser.add_argument('--translated', action='store_true',
                    help='run the x86->68000 generated functions (tools/x86x) instead of src/common/geometry.s')
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
toolroot = ROOT.parent / 'F030Arcade/third_party/chorensha/tools'
vasm = Path(os.environ.get('VASM', toolroot / 'vasmm68k_mot_mac')).resolve()
vlink = Path(os.environ.get('VLINK', toolroot / 'vlink_mac')).resolve()
hatari = Path(shutil.which(os.environ.get('HATARI', 'hatari'))).resolve()
tos = Path(os.environ.get('TOS', ROOT.parent / 'F030Comanche/tools/toolchain/tos402.rom')).resolve()
fixture_path = ROOT / 'tests/fixtures/dos-geometry.json'
fixture = json.loads(fixture_path.read_text())
inputs, expected = bytearray(), bytearray()
for case in fixture['cases']:
    data, value, result = bytearray(64), case['input'], case['output']
    if case['functionId'] == 'sub_00010976':
        data[0:2] = bytes([1, value['style']])
        struct.pack_into('<HH', data, 2, value['maxWidth'], value['maxHeight'])
        data[6] = value['aliasOutputs']
        data[8:32] = bytes.fromhex(value['recordHex'])
        data[32:34] = bytes.fromhex(value['widthBefore'])
        data[34:36] = bytes.fromhex(value['heightBefore'])
        expected.extend(bytes.fromhex(result['widthHex'] + result['heightHex']))
        expected.extend(struct.pack('<I', result['eax']))
    elif case['functionId'] == 'sub_00048105':
        data[0:2] = bytes([2, value['index'] & 255])
        struct.pack_into('<4I', data, 4, *[value[k] for k in ('eax', 'edx', 'ebx', 'ecx')])
        data[20:40] = bytes.fromhex(value['rowBefore'])
        struct.pack_into('<I', data, 40, value['index'])
        expected.extend(bytes.fromhex(result['rowHex']))
        expected.extend(struct.pack('<II', result['eax'], result['edx']))
    else:
        raise ValueError('fixture uses an unimplemented function')
    inputs.extend(data)
(out / 'geometry-input.bin').write_bytes(inputs)
(out / 'geometry-input.inc').write_text(f'NUM_FIXTURES equ {len(fixture["cases"])}\n')
(out / 'expected.bin').write_bytes(expected)
assemble = [str(vasm), str(ROOT / 'src/target/falcon/geometry-fixtures.s'), '-quiet',
            '-Felf', '-m68000', '-I' + str(ROOT / 'src/common'),
            '-o', str(out / 'geometry.o'), '-L', str(out / 'geometry.lst')]
link = [str(vlink), str(out / 'geometry.o'), '-q', '-Rstd', '-b', 'ataritos',
        '-tos-flags', '1', '-e', '_main', '-M',
        '-o', str(out / 'PGGEOM.TOS')]
if args.translated:
    # The harness includes "geometry.s"; vasm finds this generated file in the working directory first.
    subprocess.run([sys.executable, str(ROOT / 'tools/x86x/translate.py'), 'sub_00010976', 'sub_00048105',
                    '--out', str(out / 'geometry.s'), '--report', str(out / 'translate.report.txt')], check=True)
subprocess.run(assemble, cwd=out, check=True)
with (out / 'PGGEOM.map').open('w') as log:
    subprocess.run(link, cwd=out, check=True, stdout=log, stderr=subprocess.STDOUT)
command = [str(hatari), '--machine', 'falcon', '--cpulevel', '3', '--cpuclock', '16',
           '--cpu-exact', 'true', '--compatible', 'true', '--frameskips', '0', '--fpu', 'none',
           '--memsize', '4', '--tos', str(tos), '--patch-tos', 'true', '--mmu', 'true',
           '--dsp', 'off', '--monitor', 'rgb', '--sound', 'off', '--fast-boot', 'true',
           '--fast-forward', 'true', '--confirm-quit', 'off', '--disable-video', 'on',
           '--run-vbls', '1200', '--alert-level', 'fatal', 'PGGEOM.TOS']
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
record = {'status': 'Unproven', 'assemble': assemble, 'link': link, 'command': command,
          'implementation': 'x86-translated' if args.translated else 'hand-written',
          'sha256': {str(path): sha(path) for path in (vasm, vlink, hatari, tos, fixture_path,
                  ROOT / 'src/common/geometry.s', ROOT / 'src/target/falcon/geometry-fixtures.s',
                  ROOT / 'src/common/x86rt.i', ROOT / 'tools/x86x/translate.py',
                  ROOT.parent / 'F030Method/validation/flags.py', ROOT.parent / 'F030Method/validation/checkpoints.py',
                  out / 'PGGEOM.TOS', Path(__file__), *([out / 'geometry.s'] if args.translated else []))}}
try:
    with (out / 'hatari.log').open('w') as log:
        proc = subprocess.run(command, cwd=out, stdin=subprocess.DEVNULL,
                              stdout=log, stderr=subprocess.STDOUT, timeout=60)
    record['hatariReturncode'] = proc.returncode
    result = out / 'PGGEOM.OUT'
    actual = result.read_bytes() if result.is_file() else b''
    record['firstByteDifference'] = byte_difference(expected, actual)
    if proc.returncode or actual != expected:
        raise RuntimeError(f'm68k differs from DOS: {len(actual)} bytes, expected {len(expected)}; see {out}')
    record.update(status='Verified contract fixtures', bytesCompared=len(actual),
                  cases=len(fixture['cases']), resultSha256=sha(result))
    print(f'{len(fixture["cases"])} m68k/DOS fixtures equal ({len(actual)} bytes), Falcon030 Hatari '
          f'({"x86-translated" if args.translated else "hand-written"})')
finally:
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
