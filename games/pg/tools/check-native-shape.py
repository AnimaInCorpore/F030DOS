#!/usr/bin/env python3
"""N/A - build/run the native harness of the x86-translated shape draws sub_00058AB4/sub_00058F9E against DOS witnesses.

There is no hand-written port of this function: the generated code
(tools/x86x/translate.py) is the only implementation, so this gate is the first
fixture-backed check of translator rules no hand port exercised.
"""
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
fixture_path = ROOT / 'tests/fixtures/dos-shape.json'
fixture = json.loads(fixture_path.read_text())
blob = (ROOT / 'tests/fixtures/dos-shape.bin').read_bytes()
if sha(ROOT / 'game/EXE/PANZER.EXE') != fixture['authority'] or hashlib.sha256(blob).hexdigest() != fixture['binSha256']:
    raise ValueError('wrong DOS build or fixture data')


IMAGE_BYTES = 0x40000      # harness image buffer: header, table and the sprite at its own offset


def even(data):
    return data + (b'\0' if len(data) & 1 else b'')


inputs, expected = bytearray(), bytearray()
for c in fixture['cases']:
    head = blob[c['head']['offset']:c['head']['offset'] + c['head']['bytes']]
    sprite = blob[c['sprite']['offset']:c['sprite']['offset'] + c['sprite']['bytes']]
    before = blob[c['before']['offset']:c['before']['offset'] + c['before']['bytes']]
    after = blob[c['after']['offset']:c['after']['offset'] + c['after']['bytes']]
    table = bytes.fromhex(c['tableHex'])
    if len(table) != 256 or c['tableOffset'] != 0x6E48:
        raise ValueError('unexpected pixel table')
    if c['spriteOffset'] + len(sprite) > IMAGE_BYTES or len(head) > c['spriteOffset'] or len(sprite) >= 65536:
        raise ValueError('sprite does not fit the harness image buffer')
    body = even(head) + even(sprite) + even(before) + table
    header = struct.pack('>19L', *c['clip'], c['bitmap']['maxX'], c['bitmap']['maxY'], c['index'], c['x'], c['y'],
                         *c['region'], len(head), len(before), 76 + len(body),
                         {'sub_00058AB4': 0, 'sub_00058F9E': 1}[c['functionId']], c['spriteOffset'], len(sprite))
    inputs += header + body
    expected += after + struct.pack('<I', c['eax'])
(out / 'shape-input.bin').write_bytes(inputs)
(out / 'shape-input.inc').write_text(f'NUM_CASES equ {len(fixture["cases"])}\nRESULT_LEN equ {len(expected)}\n')
(out / 'expected.bin').write_bytes(expected)
toolroot = ROOT.parent / 'F030Arcade/third_party/chorensha/tools'
vasm = Path(os.environ.get('VASM', toolroot / 'vasmm68k_mot_mac')).resolve()
vlink = Path(os.environ.get('VLINK', toolroot / 'vlink_mac')).resolve()
hatari = Path(shutil.which(os.environ.get('HATARI', 'hatari'))).resolve()
tos = Path(os.environ.get('TOS', ROOT.parent / 'F030Comanche/tools/toolchain/tos402.rom')).resolve()
subprocess.run([sys.executable, str(ROOT / 'tools/x86x/translate.py'), 'sub_00058AB4', 'sub_00058EB8',
                'sub_00058F9E', 'sub_00059476',
                '--out', str(out / 'shape.s'), '--report', str(out / 'translate.report.txt')], check=True)
assemble = [str(vasm), str(ROOT / 'src/target/falcon/shape-fixture.s'), '-quiet', '-Felf', '-m68000',
            '-I' + str(ROOT / 'src/common'), '-o', str(out / 'shape.o'), '-L', str(out / 'shape.lst')]
link = [str(vlink), str(out / 'shape.o'), '-q', '-Rstd', '-b', 'ataritos', '-tos-flags', '1', '-e', '_main', '-M',
        '-o', str(out / 'PGSHAPE.TOS')]
subprocess.run(assemble, cwd=out, check=True)
with (out / 'PGSHAPE.map').open('w') as log:
    subprocess.run(link, cwd=out, check=True, stdout=log, stderr=subprocess.STDOUT)
command = [str(hatari), '--machine', 'falcon', '--cpulevel', '3', '--cpuclock', '16',
           '--cpu-exact', 'true', '--compatible', 'true', '--frameskips', '0', '--fpu', 'none',
           '--memsize', '4', '--tos', str(tos), '--patch-tos', 'true', '--mmu', 'true',
           '--dsp', 'off', '--monitor', 'rgb', '--sound', 'off', '--fast-boot', 'true',
           '--fast-forward', 'true', '--confirm-quit', 'off', '--disable-video', 'on',
           '--run-vbls', '2400', '--alert-level', 'fatal', 'PGSHAPE.TOS']
sources = [ROOT / 'src/common/x86rt.i', ROOT / 'tools/x86x/translate.py',
           ROOT.parent / 'F030Method/validation/flags.py', ROOT / 'src/target/falcon/shape-fixture.s',
           out / 'shape.s', fixture_path, ROOT / 'tests/fixtures/dos-shape.bin', Path(__file__)]
record = {'status': 'Unproven', 'implementation': 'x86-translated (no hand-written port exists)',
          'assemble': assemble, 'link': link, 'command': command,
          'sha256': {str(p): sha(p) for p in [vasm, vlink, hatari, tos, out / 'PGSHAPE.TOS', *sources]}}
try:
    with (out / 'hatari.log').open('w') as log:
        proc = subprocess.run(command, cwd=out, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    record['hatariReturncode'] = proc.returncode
    result = out / 'PGSHAPE.OUT'
    actual = result.read_bytes() if result.is_file() else b''
    if proc.returncode or actual != expected:
        # report per case
        pos, report = 0, []
        for i, c in enumerate(fixture['cases']):
            n = c['after']['bytes'] + 4
            a, e = actual[pos:pos + n], expected[pos:pos + n]
            diff = sum(x != y for x, y in zip(a, e)) + abs(len(a) - len(e))
            report.append(f'case {i} ({c["functionId"]} index {c["index"]} at {c["x"]},{c["y"]}): {diff} of {n} bytes differ')
            pos += n
        record['caseReport'] = report
        raise RuntimeError(f'translated sub_00058AB4 differs from DOS: {len(actual)}/{len(expected)} bytes; '
                           + '; '.join(report) + f'; see {out}')
    record.update(status='Verified shape-draw contract fixtures', bytesCompared=len(actual),
                  cases=len(fixture['cases']), resultSha256=sha(result))
    print(f'PASS {len(fixture["cases"])} native shape-draw fixtures (x86-translated sub_00058AB4/sub_00058F9E), '
          f'{len(actual)} DOS bytes, Falcon030 4MB')
finally:
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
