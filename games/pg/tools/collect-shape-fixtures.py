#!/usr/bin/env python3
"""N/A - retain checked DOS witnesses of the clipped shape draw sub_00058AB4; no generated expected values.

Writes tests/fixtures/dos-shape.json (metadata) and dos-shape.bin (the shape
image's header and table, the sprite's bytes, and the destination-bitmap region
before and after each call). The region
is the bounding box of the pixels DOS changed, widened by 16 pixels and clipped to
the bitmap, so the surround the function must leave alone is compared too.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARGIN = 16
def collect(c, folder, route_name):
    global blob_bin
    entry, nxt = c['tableEntry'], c['nextEntry']
    w, h = c['desc'][1] + 1, c['desc'][2] + 1
    before = (folder / c['beforeFile']).read_bytes()
    after = (folder / c['afterFile']).read_bytes()
    head = bytes.fromhex(c['headHex'])
    sprite = (folder / c['spriteFile']).read_bytes()
    if len(before) != w * h or len(after) != w * h or len(sprite) != c['spriteBytes'] or c['spriteOffset'] != entry[0]:
        raise ValueError('witness files do not match the recorded sizes')
    changed = [i for i in range(w * h) if before[i] != after[i]]
    if changed:
        xs, ys = [i % w for i in changed], [i // w for i in changed]
        box = [min(xs), min(ys), max(xs), max(ys)]
    else:
        box = [c['args'][3], c['args'][4], c['args'][3], c['args'][4]]
    region = [max(box[0] - MARGIN, 0), max(box[1] - MARGIN, 0), min(box[2] + MARGIN, w - 1), min(box[3] + MARGIN, h - 1)]
    rows_before = b''.join(before[y * w + region[0]:y * w + region[2] + 1] for y in range(region[1], region[3] + 1))
    rows_after = b''.join(after[y * w + region[0]:y * w + region[2] + 1] for y in range(region[1], region[3] + 1))
    offsets = {}
    for name, data in (('head', head), ('sprite', sprite), ('before', rows_before), ('after', rows_after)):
        offsets[name] = {'offset': len(blob_bin), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        blob_bin += data
    clipped = bool(changed) and (box[0] <= c['clip'][1] or box[1] <= c['clip'][2] or box[2] >= c['clip'][3] or box[3] >= c['clip'][4])
    cases.append({'functionId': c['functionId'], 'kind': c['kind'], 'route': route_name, 'at': c['at'], 'index': c['args'][2],
                  'x': c['args'][3], 'y': c['args'][4], 'clip': c['clip'][1:], 'bitmap': {'maxX': c['desc'][1], 'maxY': c['desc'][2]},
                  'dosPointers': {'clip': c['args'][0], 'shape': c['args'][1], 'desc': c['clip'][0], 'pixels': c['desc'][0]},
                  'tableEntry': entry, 'nextEntry': nxt, 'spriteOffset': entry[0], 'changedPixels': len(changed), 'changedBox': box if changed else None,
                  'region': region, 'touchesClipEdge': clipped, 'tableOffset': c['tableOffset'], 'tableHex': c['tableHex'],
                  **offsets, 'eax': c['eax']})


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('routes', type=Path, nargs='+')
args = parser.parse_args()
blob_bin, cases, provenance = bytearray(), [], []
for route_path in args.routes:
    raw = route_path.read_bytes()
    route = json.loads(raw)
    if route['status'] != 'CAPTURED' or not route['hdd_unchanged'] or route['qemu_returncode']:
        raise ValueError('completed unchanged DOS route required')
    if hashlib.sha256((ROOT / 'game/EXE/PANZER.EXE').read_bytes()).hexdigest() != route['exe_sha256']:
        raise ValueError('wrong DOS build')
    provenance.append({'route': route_path.name, 'routeSha256': hashlib.sha256(raw).hexdigest(),
                       'probeSha256': route['shape_probe_sha256'], 'hddSha256': route['hdd_sha256'],
                       'qemuSha256': route['qemu_sha256'], 'command': route['command']})
    for c in route['shape_contracts']:
        collect(c, route_path.parent, route_path.name)

if not cases:
    raise ValueError('no bounded shape witness')
fixture = {'authority': hashlib.sha256((ROOT / 'game/EXE/PANZER.EXE').read_bytes()).hexdigest(), 'routes': provenance,
           'binSha256': hashlib.sha256(blob_bin).hexdigest(), 'cases': cases}
(ROOT / 'tests/fixtures/dos-shape.bin').write_bytes(blob_bin)
(ROOT / 'tests/fixtures/dos-shape.json').write_text(json.dumps(fixture, indent=1) + '\n')
print(f'{len(cases)} DOS shape-draw witnesses retained ({len(blob_bin)} bytes of images and regions), '
      f'{sum(c["touchesClipEdge"] for c in cases)} touch a clip edge; '
      f'{sum(c["functionId"] == "sub_00058F9E" for c in cases)} of sub_00058F9E')
