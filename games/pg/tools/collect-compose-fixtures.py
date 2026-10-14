#!/usr/bin/env python3
"""N/A - retain checked DOS witnesses of the compositor sub_00014BF6; no generated expected values.

Writes tests/fixtures/dos-compose.json (metadata) and dos-compose.bin.z (zlib): per case
the arena windows before/after, each shape draw's header and sprite bytes, the
destination-bitmap region before/after (the changed box widened by 16 pixels) and the
argument of every sub_000481AB call. The data sit at their DOS virtual addresses.
"""
import argparse
import hashlib
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARGIN = 16
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('routes', type=Path, nargs='+')
args = parser.parse_args()
blob, cases, provenance = bytearray(), [], []


def put(data):
    entry = {'offset': len(blob), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    blob.extend(data)
    return entry


for route_path in args.routes:
    raw = route_path.read_bytes()
    route = json.loads(raw)
    if route['status'] != 'CAPTURED' or not route['hdd_unchanged'] or route['qemu_returncode']:
        raise ValueError('completed unchanged DOS route required')
    if hashlib.sha256((ROOT / 'game/EXE/PANZER.EXE').read_bytes()).hexdigest() != route['exe_sha256']:
        raise ValueError('wrong DOS build')
    provenance.append({'route': route_path.name, 'routeSha256': hashlib.sha256(raw).hexdigest(),
                       'probeSha256': route['compose_probe_sha256'], 'hddSha256': route['hdd_sha256'],
                       'qemuSha256': route['qemu_sha256'], 'command': route['command']})
    folder = route_path.parent
    for c in route['compose_contracts']:
        w, h = c['desc'][1] + 1, c['desc'][2] + 1
        before = (folder / c['beforeFile']).read_bytes()
        after = (folder / c['afterFile']).read_bytes()
        if len(before) != w * h or len(after) != w * h:
            raise ValueError('bitmap files do not match the descriptor')
        changed = [i for i in range(w * h) if before[i] != after[i]]
        if not changed:
            continue
        xs, ys = [i % w for i in changed], [i // w for i in changed]
        box = [min(xs), min(ys), max(xs), max(ys)]
        region = [max(box[0] - MARGIN, 0), max(box[1] - MARGIN, 0), min(box[2] + MARGIN, w - 1), min(box[3] + MARGIN, h - 1)]
        rows = lambda data: b''.join(data[y * w + region[0]:y * w + region[2] + 1] for y in range(region[1], region[3] + 1))
        draws = []
        for d in c['shapeDraws']:
            draws.append({'args': d['args'], 'clip': d['clip'], 'unbounded': d['unbounded'], 'spriteOffset': d['spriteOffset'],
                          'head': put(bytes.fromhex(d['headHex'])), 'sprite': put((folder / d['spriteFile']).read_bytes())})
        cases.append({'functionId': c['functionId'], 'kind': c['kind'], 'route': route_path.name, 'at': c['at'],
                      'globals': c['globals'], 'records': c['records'], 'desc': c['desc'], 'region': region,
                      'changedPixels': len(changed), 'changedBox': box,
                      'windowsBefore': [{'offset': x['offset'], 'bytes': len(bytes.fromhex(x['hex'])),
                                         'data': put(bytes.fromhex(x['hex']))} for x in c['windows']],
                      'windowsAfter': [{'offset': x['offset'], 'bytes': len(bytes.fromhex(x['hex'])),
                                        'data': put(bytes.fromhex(x['hex']))} for x in c['windowsAfter']],
                      'shapeDraws': draws, 'bitmapBefore': put(rows(before)), 'bitmapAfter': put(rows(after)),
                      'present': [p['al'] for p in c['present']], 'eax': c['eax']})
if not cases:
    raise ValueError('no compositor witness')
fixture = {'authority': hashlib.sha256((ROOT / 'game/EXE/PANZER.EXE').read_bytes()).hexdigest(), 'routes': provenance,
           'binSha256': hashlib.sha256(blob).hexdigest(), 'cases': cases}
(ROOT / 'tests/fixtures/dos-compose.bin.z').write_bytes(zlib.compress(bytes(blob), 9))
(ROOT / 'tests/fixtures/dos-compose.json').write_text(json.dumps(fixture, indent=1) + '\n')
print(f'{len(cases)} DOS compositor witnesses retained ({len(blob)} bytes, {len(zlib.compress(bytes(blob), 9))} compressed)')
