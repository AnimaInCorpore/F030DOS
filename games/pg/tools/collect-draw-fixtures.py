#!/usr/bin/env python3
"""N/A - collect checked original DOS display-driver copy calls; no generated expected values."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('route',type=Path)
args=parser.parse_args()
raw=args.route.read_bytes()
route=json.loads(raw)
if route['status']!='CAPTURED' or not route['hdd_unchanged'] or route['qemu_returncode']:
    raise ValueError('completed unchanged DOS route required')
if hashlib.sha256((ROOT/'game/EXE/PANZER.EXE').read_bytes()).hexdigest()!=route['exe_sha256']:
    raise ValueError('wrong DOS build')
dll=hashlib.sha256((ROOT/'game/LIB/DRV/VESA480.DLL').read_bytes()).hexdigest()
cases=route['draw_contracts']
if {c['export'] for c in cases}!={6,7,11}:
    raise ValueError('draw fixture set incomplete: need exports 6, 7 and 11')
for c in cases:
    # The reference checks only the measured domain: unclipped, equal spans, no shadow buffer.
    a=c['args'][1:]
    s=c['rect'][1:] if c['export']==11 else [0,0,c['desc'][1],c['desc'][2]]
    if c['desc'][4] or a!=c['clippedDest'] or (a[2]-a[0],a[3]-a[1])!=(s[2]-s[0],s[3]-s[1]):
        raise ValueError('fixture outside the measured 1:1 domain')
for c in cases:
    if c['export']!=7:
        c.pop('screenBefore')   # destination is fully overwritten; only export 7 reads the screen
fixture={'authority':route['exe_sha256'],'driverDllSha256':dll,'driver':route['draw_driver'],
         'screen':{'width':640,'height':480},
         'routeSha256':hashlib.sha256(raw).hexdigest(),'probeSha256':route['draw_probe_sha256'],
         'hddSha256':route['hdd_sha256'],'qemuSha256':route['qemu_sha256'],'command':route['command'],
         'cases':cases}
path=ROOT/'tests/fixtures/dos-draw.json'
path.write_text(json.dumps(fixture,indent=2)+'\n')
print(f'{len(cases)} original DOS display-driver fixtures retained: {path}')
