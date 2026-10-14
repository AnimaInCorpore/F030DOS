#!/usr/bin/env python3
"""N/A - native display-driver copy build and independent DOS output comparison."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
fixture_path = ROOT / 'tests/fixtures/dos-draw.json'
fixture = json.loads(fixture_path.read_text())
if sha(ROOT / 'game/EXE/PANZER.EXE') != fixture['authority']:
    raise ValueError('wrong DOS build')
inputs, expected = bytearray(), bytearray()
for case in fixture['cases']:
    max_x, max_y = case['desc'][1], case['desc'][2]
    bitmap_rect = case['rect'][1:] if case['export'] == 11 else [0, 0, max_x, max_y]
    screen_rect = case['args'][1:]
    if case['export'] == 7:
        mode, payload = 1, bytes.fromhex(''.join(case['screenBefore']['rows']))
        piece = bytes.fromhex(''.join(case['bitmapAfter']))
    else:
        mode, payload = 0, bytes.fromhex(''.join(case['sourceRows']))
        piece = bytes.fromhex(''.join(case['screenAfter']['rows']))
    inputs += struct.pack('>13L', mode, max_x, max_y, *bitmap_rect, *screen_rect, len(payload), len(piece))
    inputs += payload + (b'\0' if len(payload) & 1 else b'')
    expected += piece
(out / 'draw-input.bin').write_bytes(inputs)
(out / 'draw-input.inc').write_text(f'NUM_CASES equ {len(fixture["cases"])}\nRESULT_LEN equ {len(expected)}\n')
(out / 'expected.bin').write_bytes(expected)
toolroot = ROOT.parent / 'F030Arcade/third_party/chorensha/tools'
vasm = Path(os.environ.get('VASM', toolroot / 'vasmm68k_mot_mac')).resolve()
vlink = Path(os.environ.get('VLINK', toolroot / 'vlink_mac')).resolve()
hatari = Path(shutil.which(os.environ.get('HATARI', 'hatari'))).resolve()
tos = Path(os.environ.get('TOS', ROOT.parent / 'F030Comanche/tools/toolchain/tos402.rom')).resolve()
assemble = [str(vasm), str(ROOT / 'src/target/falcon/draw-fixture.s'), '-quiet', '-Felf',
            '-m68000', '-I' + str(ROOT / 'src/common'), '-o', str(out / 'draw.o'),
            '-L', str(out / 'draw.lst')]
link = [str(vlink), str(out / 'draw.o'), '-q', '-Rstd', '-b', 'ataritos',
        '-tos-flags', '1', '-e', '_main', '-M', '-o', str(out / 'PGDRAW.TOS')]
subprocess.run(assemble, cwd=out, check=True)
with (out / 'PGDRAW.map').open('w') as log:
    subprocess.run(link, cwd=out, check=True, stdout=log, stderr=subprocess.STDOUT)
command = [str(hatari), '--machine', 'falcon', '--cpulevel', '3', '--cpuclock', '16',
           '--cpu-exact', 'true', '--compatible', 'true', '--frameskips', '0', '--fpu', 'none',
           '--memsize', '4', '--tos', str(tos), '--patch-tos', 'true', '--mmu', 'true', '--dsp', 'off',
           '--monitor', 'rgb', '--sound', 'off', '--fast-boot', 'true', '--fast-forward', 'true',
           '--confirm-quit', 'off', '--disable-video', 'on', '--run-vbls', '3000',
           '--alert-level', 'fatal', 'PGDRAW.TOS']
sources = [ROOT / 'src/common/draw.s', ROOT / 'src/target/falcon/draw-fixture.s', Path(__file__)]
record = {'status': 'Unproven', 'assemble': assemble, 'link': link, 'command': command,
          'sha256': {str(p): sha(p) for p in [vasm, vlink, hatari, tos, fixture_path, out / 'PGDRAW.TOS', *sources]}}
try:
    with (out / 'hatari.log').open('w') as log:
        proc = subprocess.run(command, cwd=out, stdin=subprocess.DEVNULL,
                              stdout=log, stderr=subprocess.STDOUT, timeout=120)
    record['hatariReturncode'] = proc.returncode
    result = out / 'PGDRAW.OUT'
    actual = result.read_bytes() if result.is_file() else b''
    if proc.returncode or actual != expected:
        raise RuntimeError(f'native draw copy differs from DOS: {len(actual)}/{len(expected)} bytes; see {out}')
    record.update(status='Verified measured display-driver copy domain', bytesCompared=len(actual),
                  resultSha256=sha(result))
    print(f'PASS native gfx_copy_rect: {len(fixture["cases"])} DOS fixtures, {len(actual)} bytes, Falcon030 4MB')
finally:
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
