#!/usr/bin/env python3
"""N/A - retain original class-setup inputs/outputs; no reference oracle."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def sha(data):
    return hashlib.sha256(data).hexdigest()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('route', type=Path)
args = parser.parse_args()
raw = args.route.read_bytes()
route = json.loads(raw)
if route['status'] != 'CAPTURED' or not route['hdd_unchanged'] or route['qemu_returncode']:
    raise ValueError('completed unchanged DOS route required')
if sha((ROOT/'game/EXE/PANZER.EXE').read_bytes()) != route['exe_sha256']:
    raise ValueError('wrong DOS build')
events = {e['phase']: e for e in route['loader_state'] if e['functionId']=='sub_0003AFF3'}
def arena(phase):
    info = events[phase]['arena']
    data = (args.route.parent / info['file']).read_bytes()
    if len(data) != info['bytes'] or sha(data) != info['sha256']:
        raise ValueError('captured state identity differs')
    return data
before, after = arena('entry'), arena('exit')
ranges = [(0x74f0,4),(0x11c54,200*98),(0x28eed,1),(0x2b84,1),
          (0x2c13+before[0x28eed]*2,2),(0x10694,400),(0x1dd92,4)]
equipment = set()
for side in range(2):
    for slot in range(200):
        record = 0x11c54+slot*98+side*49
        if before[record+0x1f]:
            index = int.from_bytes(before[record+0x15:record+0x17],'little')
            offset = 0x179b0+index*50+0x14
            if offset >= len(before):
                raise ValueError('equipment byte outside bounded arena')
            equipment.add(offset)
ranges += [(offset,1) for offset in sorted(equipment)]
out_ranges = [(0x74f0,4),(0x10694,400),(0x1dd92,4)]
def spans(data,ranges):
    return [{'offset':offset,'hex':data[offset:offset+size].hex()} for offset,size in ranges]
before_regs,after_regs=events['entry']['registers'],events['exit']['registers']
if any(before_regs[r]!=after_regs[r] for r in ('ESP','EDX','EBX','ECX','ESI','EDI','EBP')):
    raise ValueError('DOS class setup preservation differs')
fixture={'authority':route['exe_sha256'],'functionId':'sub_0003AFF3',
         'virtualBase':0x1e0000,'routeSha256':sha(raw),
         'probeSha256':route['loader_state_probe_sha256'],'collectorSha256':sha(Path(__file__).read_bytes()),
         'hddSha256':route['hdd_sha256'],'qemuSha256':route['qemu_sha256'],'command':route['command'],
         'input':{'stateSpans':spans(before,ranges)},
         'output':{'stateSpans':spans(after,out_ranges),'eax':after_regs['EAX']},
         'registersBefore':before_regs,'registersAfter':after_regs}
path=ROOT/'tests/fixtures/dos-unit-classes.json'
path.write_text(json.dumps(fixture,indent=2)+'\n')
print(f'Captured 400 class bytes, side averages and seed: {path}')
