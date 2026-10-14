#!/usr/bin/env python3
"""N/A - fixture collector; expected values come only from a completed DOS run."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('route', type=Path)
args = parser.parse_args()
raw = args.route.read_bytes()
route = json.loads(raw)
assert route['status'] == 'CAPTURED' and route['hdd_unchanged']
assert route['exe_sha256'] == '115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86'
cases = route['geometry_contracts']
assert len(cases) == 12
assert {case['functionId'] for case in cases} == {'sub_00010976', 'sub_00048105'}
fixture = {'authority': route['exe_sha256'], 'routeSha256': hashlib.sha256(raw).hexdigest(),
           'command': route['command'], 'probeSha256': route['geometry_probe_sha256'],
           'hddSha256': route['hdd_sha256'], 'qemuSha256': route['qemu_sha256'],
           'collectorSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'cases': []}
for i, case in enumerate(cases):
    fixture['cases'].append({'id': f'geometry-dos-{i:02d}', **case})
out = ROOT / 'tests/fixtures/dos-geometry.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(fixture, indent=2) + '\n')
print(out)
