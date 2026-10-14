#!/usr/bin/env python3
"""N/A - collect checked original DOS RNG calls; no generated expected values."""
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
cases=route['rng_contracts']
if len(cases)!=19 or {c['functionId'] for c in cases}!={'sub_00063375','sub_0006337B','sub_0006339F'}:
    raise ValueError('RNG fixture set incomplete')
chain=[c for c in cases if c['kind']=='isolated-dos-chain']
if len(chain)!=8 or any(a['output']['seedHex']!=b['input']['seedHex'] for a,b in zip(chain,chain[1:])):
    raise ValueError('DOS chained state not preserved')
fixture={'authority':route['exe_sha256'],'virtualBase':0x1e0000,
         'routeSha256':hashlib.sha256(raw).hexdigest(),'probeSha256':route['rng_probe_sha256'],
         'hddSha256':route['hdd_sha256'],'qemuSha256':route['qemu_sha256'],'command':route['command'],'cases':cases}
path=ROOT/'tests/fixtures/dos-rng.json'
path.write_text(json.dumps(fixture,indent=2)+'\n')
print(f'{len(cases)} original DOS RNG fixtures retained: {path}')
