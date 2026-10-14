#!/usr/bin/env python3
"""N/A - build/run the native harness of the x86-translated compositor sub_00014BF6 against DOS witnesses.

The harness places the captured DOS state at its DOS virtual addresses (arena at $1E0000, so
the pointers DOS stored in memory are valid native addresses) on a 14 MB Falcon030 and compares
the arena windows, the destination bitmap region and the argument log of the present boundary
(sub_000481AB, a stub: the DOS function is not translated) with the DOS output.
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
import zlib

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
fixture_path = ROOT / 'tests/fixtures/dos-compose.json'
fixture = json.loads(fixture_path.read_text())
blob = zlib.decompress((ROOT / 'tests/fixtures/dos-compose.bin.z').read_bytes())
if sha(ROOT / 'game/EXE/PANZER.EXE') != fixture['authority'] or hashlib.sha256(blob).hexdigest() != fixture['binSha256']:
    raise ValueError('wrong DOS build or fixture data')
ARENA = 0x1E0000


def data(entry):
    return blob[entry['offset']:entry['offset'] + entry['bytes']]


def even(b):
    return b + (b'\0' if len(b) & 1 else b'')


records, expected = bytearray(), bytearray()
for c in fixture['cases']:
    body = bytearray(struct.pack('>L', len(c['windowsBefore'])))
    for w in c['windowsBefore']:
        body += struct.pack('>LL', w['offset'], w['bytes']) + even(data(w['data']))
    body += struct.pack('>L', len(c['shapeDraws']))
    for d in c['shapeDraws']:
        head, sprite = data(d['head']), data(d['sprite'])
        body += struct.pack('>LLLL', d['args'][1], len(head), d['spriteOffset'], len(sprite)) + even(head) + even(sprite)
    stride = c['desc'][1] + 1
    rx0, ry0, rx1, ry1 = c['region']
    width, height = rx1 - rx0 + 1, ry1 - ry0 + 1
    rows = data(c['bitmapBefore'])
    assert len(rows) == width * height
    body += struct.pack('>LLLLL', c['desc'][0], stride, ry0 * stride + rx0, width, height) + even(rows)
    records += struct.pack('>L', len(body)) + body
    for w in c['windowsAfter']:
        expected += data(w['data'])
    expected += data(c['bitmapAfter'])
    expected += bytes(c['present']) + bytes(8 - len(c['present'])) + struct.pack('<L', len(c['present']))
(out / 'COMPIN.BIN').write_bytes(struct.pack('>L', len(fixture['cases'])) + records)
(out / 'compose-input.inc').write_text(f'NUM_CASES equ {len(fixture["cases"])}\n')
(out / 'expected.bin').write_bytes(expected)
toolroot = ROOT.parent / 'F030Arcade/third_party/chorensha/tools'
vasm = Path(os.environ.get('VASM', toolroot / 'vasmm68k_mot_mac')).resolve()
vlink = Path(os.environ.get('VLINK', toolroot / 'vlink_mac')).resolve()
hatari = Path(shutil.which(os.environ.get('HATARI', 'hatari'))).resolve()
tos = Path(os.environ.get('TOS', ROOT.parent / 'F030Comanche/tools/toolchain/tos402.rom')).resolve()
translate = [sys.executable, str(ROOT / 'tools/x86x/translate.py'), 'sub_00014BF6', 'sub_00058AB4', 'sub_00058EB8',
             '--boundary', 'sub_000481AB', '--out', str(out / 'compose.s'), '--report', str(out / 'translate.report.txt')]
subprocess.run(translate, check=True)
assemble = [str(vasm), str(ROOT / 'src/target/falcon/compose-fixture.s'), '-quiet', '-Felf', '-m68000',
            '-I' + str(ROOT / 'src/common'), '-o', str(out / 'compose.o'), '-L', str(out / 'compose.lst')]
link = [str(vlink), str(out / 'compose.o'), '-q', '-Rstd', '-b', 'ataritos', '-tos-flags', '1', '-e', '_main', '-M',
        '-o', str(out / 'PGCOMP.TOS')]
subprocess.run(assemble, cwd=out, check=True)
with (out / 'PGCOMP.map').open('w') as log:
    subprocess.run(link, cwd=out, check=True, stdout=log, stderr=subprocess.STDOUT)
command = [str(hatari), '--machine', 'falcon', '--cpulevel', '3', '--cpuclock', '16',
           '--cpu-exact', 'true', '--compatible', 'true', '--frameskips', '0', '--fpu', 'none',
           '--memsize', '14', '--tos', str(tos), '--patch-tos', 'true', '--mmu', 'true',
           '--dsp', 'off', '--monitor', 'rgb', '--sound', 'off', '--fast-boot', 'true',
           '--fast-forward', 'true', '--confirm-quit', 'off', '--disable-video', 'on',
           '--run-vbls', '6000', '--alert-level', 'fatal', 'PGCOMP.TOS']
sources = [ROOT / 'src/common/x86rt.i', ROOT / 'tools/x86x/translate.py',
           ROOT.parent / 'F030Method/validation/flags.py', ROOT / 'src/target/falcon/compose-fixture.s',
           out / 'compose.s', fixture_path, ROOT / 'tests/fixtures/dos-compose.bin.z', Path(__file__)]
record = {'status': 'Unproven', 'implementation': 'x86-translated (no hand-written port exists); '
          'sub_000481AB is a recorded boundary stub', 'assemble': assemble, 'link': link, 'command': command,
          'sha256': {str(p): sha(p) for p in [vasm, vlink, hatari, tos, out / 'PGCOMP.TOS', *sources]}}
try:
    with (out / 'hatari.log').open('w') as log:
        proc = subprocess.run(command, cwd=out, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=300)
    record['hatariReturncode'] = proc.returncode
    result = out / 'COMPOUT.BIN'
    actual = result.read_bytes() if result.is_file() else b''
    if proc.returncode or actual != expected:
        diff = sum(a != b for a, b in zip(actual, expected)) + abs(len(actual) - len(expected))
        raise RuntimeError(f'translated compositor differs from DOS: {len(actual)}/{len(expected)} bytes, {diff} differ; '
                           f'hatari returncode {proc.returncode}; see {out}')
    record.update(status='Verified compositor contract fixtures', bytesCompared=len(actual),
                  cases=len(fixture['cases']), resultSha256=sha(result))
    print(f'PASS {len(fixture["cases"])} native compositor fixture(s) (x86-translated sub_00014BF6 + shape draws, '
          f'present boundary stubbed), {len(actual)} DOS bytes, Falcon030 14MB, arena at the DOS virtual base')
finally:
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
