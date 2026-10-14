#!/usr/bin/env python3
"""N/A - build/run isolated native loader against unchanged DOS fixtures."""
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
parser.add_argument('--translated', action='store_true',
                    help='use the x86->68000 generated string and geometry functions (tools/x86x) '
                         'instead of src/common/strings.s and geometry.s')
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
fixture_path = ROOT / 'tests/fixtures/dos-loader.json'
fixture = json.loads(fixture_path.read_text())
if sha(ROOT / 'game/EXE/PANZER.EXE') != fixture['authority']:
    raise ValueError('wrong DOS authority')
for name, identity in fixture['resources'].items():
    source = ROOT / 'game/DAT' / name
    if sha(source) != identity['sha256'] or source.stat().st_size != identity['bytes']:
        raise ValueError('wrong resource identity')
    shutil.copyfile(source, out / name)
state = bytearray(0x220000)
for span in fixture['input']['stateSpans']:
    data = bytes.fromhex(span['hex'])
    state[span['offset']:span['offset'] + len(data)] = data
(out / 'loader-input.bin').write_bytes(state)
spans, expected, strings = bytearray(), bytearray(), bytearray()
if not fixture['strings']:
    raise ValueError('direct DOS string contracts required')
for sample in fixture['strings']:
    strings.extend(bytes([1 if sample['functionId'] == 'sub_00060907' else 2, 0, 0, 0]))
    strings.extend(bytes.fromhex(sample['input']['destinationHex'] + sample['input']['sourceHex']))
    expected.extend(bytes.fromhex(sample['output']['destinationHex']))
    expected.extend(struct.pack('<II', int(sample['output']['eaxReturnsDestination']),
                                sample['output']['edxSourceDelta']))
(out / 'loader-strings.bin').write_bytes(strings)
expected.extend(struct.pack('<I', fixture['output']['eax']))
ranges = [(s['offset'], s['hex']) for s in fixture['output']['stateSpans']]
ranges += [(a['address'] - fixture['virtualBase'], a['hex']) for a in fixture['output']['arrays']]
for offset, value in ranges:
    data = bytes.fromhex(value)
    spans.extend(struct.pack('>II', offset, len(data)))
    expected.extend(data)
for read in fixture['output']['reads']:
    expected.extend(struct.pack('<III', read['itemSize'], read['itemCount'], read['returnedItems']))
(out / 'loader-spans.bin').write_bytes(spans)
(out / 'loader-input.inc').write_text(f'NUM_SPANS equ {len(ranges)}\nNUM_READS equ {len(fixture["output"]["reads"])}\nNUM_STRINGS equ {len(fixture["strings"])}\n')
(out / 'expected.bin').write_bytes(expected)
toolroot = ROOT.parent / 'F030Arcade/third_party/chorensha/tools'
vasm = Path(os.environ.get('VASM', toolroot / 'vasmm68k_mot_mac')).resolve()
vlink = Path(os.environ.get('VLINK', toolroot / 'vlink_mac')).resolve()
hatari = Path(shutil.which(os.environ.get('HATARI', 'hatari'))).resolve()
tos = Path(os.environ.get('TOS', ROOT.parent / 'F030Comanche/tools/toolchain/tos402.rom')).resolve()
assemble = [str(vasm), str(ROOT / 'src/target/falcon/loader-fixture.s'), '-quiet', '-Felf',
            '-m68000', '-I' + str(ROOT / 'src/common'), '-o', str(out / 'loader.o'),
            '-L', str(out / 'loader.lst')]
link = [str(vlink), str(out / 'loader.o'), '-q', '-Rstd', '-b', 'ataritos',
        '-tos-flags', '1', '-e', '_main', '-M', '-o', str(out / 'PGLOAD.TOS')]
if args.translated:
    # loader-fixture.s includes "strings.s" and "geometry.s"; vasm finds these generated files in the
    # working directory first.
    subprocess.run([sys.executable, str(ROOT / 'tools/x86x/translate.py'), 'sub_00060907', 'sub_00060926',
                    '--out', str(out / 'strings.s'), '--report', str(out / 'translate.report.txt')], check=True)
    subprocess.run([sys.executable, str(ROOT / 'tools/x86x/translate.py'), 'sub_00010976', 'sub_00048105',
                    '--out', str(out / 'geometry.s'), '--report', str(out / 'translate-geometry.report.txt')],
                   check=True)
subprocess.run(assemble, cwd=out, check=True)
with (out / 'PGLOAD.map').open('w') as log:
    subprocess.run(link, cwd=out, check=True, stdout=log, stderr=subprocess.STDOUT)
command = [str(hatari), '--machine', 'falcon', '--cpulevel', '3', '--cpuclock', '16',
           '--cpu-exact', 'true', '--compatible', 'true', '--frameskips', '0', '--fpu', 'none',
           '--memsize', '4', '--tos', str(tos), '--patch-tos', 'true', '--mmu', 'true',
           '--dsp', 'off', '--monitor', 'rgb', '--sound', 'off', '--fast-boot', 'true',
           '--fast-forward', 'true', '--confirm-quit', 'off', '--disable-video', 'on',
           '--run-vbls', '1800', '--alert-level', 'fatal', 'PGLOAD.TOS']
sources = [ROOT / 'src/common' / name for name in ('geometry.s', 'strings.s', 'loader.s')]
sources.append(ROOT.parent / 'F030Method/validation/flags.py')
sources += [ROOT / 'src/target/falcon/loader-fixture.s', Path(__file__), fixture_path,
            ROOT / 'src/common/x86rt.i', ROOT / 'tools/x86x/translate.py']
if args.translated:
    sources += [out / 'strings.s', out / 'geometry.s']
record = {'status': 'Unproven', 'assemble': assemble, 'link': link, 'command': command,
          'sha256': {str(p): sha(p) for p in [vasm, vlink, hatari, tos, out / 'PGLOAD.TOS', *sources]}}
try:
    with (out / 'hatari.log').open('w') as log:
        proc = subprocess.run(command, cwd=out, stdin=subprocess.DEVNULL,
                              stdout=log, stderr=subprocess.STDOUT, timeout=60)
    record['hatariReturncode'] = proc.returncode
    result = out / 'PGLOAD.OUT'
    actual = result.read_bytes() if result.is_file() else b''
    if proc.returncode or actual != expected:
        mismatch = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), None)
        raise RuntimeError(f'native loader differs from DOS: {len(actual)}/{len(expected)} bytes; first mismatch {mismatch}; see {out}')
    record.update(status='Verified Poland success contract fixture',
                  strings='x86-translated' if args.translated else 'hand-written',
                  bytesCompared=len(actual), reads=len(fixture['output']['reads']), resultSha256=sha(result))
    print(f'PASS native sub_00037E75 (strings {"x86-translated" if args.translated else "hand-written"}): '
          f'{len(actual)} DOS bytes, globals/six arrays/23 reads, Falcon030 4MB')
finally:
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
