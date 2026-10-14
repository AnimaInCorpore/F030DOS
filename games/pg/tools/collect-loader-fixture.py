#!/usr/bin/env python3
"""N/A - retain original loader inputs/outputs, verifying each stream range."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE_HASH = '115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def collect(route_path):
    raw = route_path.read_bytes()
    route = json.loads(raw)
    if (route['status'] != 'CAPTURED' or not route['hdd_unchanged'] or
            route['qemu_returncode'] != 0 or route['exe_sha256'] != EXE_HASH):
        raise ValueError('completed unchanged DOS route required')
    directory = route_path.parent
    def captured(info):
        data = (directory / info['file']).read_bytes()
        if len(data) != info['bytes'] or sha(data) != info['sha256']:
            raise ValueError('captured bytes disagree with route metadata')
        return data
    states = {e['phase']: e for e in route['loader_state']
              if e['functionId'] == 'sub_00037E75'}
    before, after = (captured(states[phase]['arena']) for phase in ('entry', 'exit'))
    count = before[0x21BE]
    table = 0xBA94 + before[0x21B9] * 15
    index = before[0x28EE8]
    spans = [(0x21B9, 1), (0x21BE, 1), (0x21C0, 15), (table, count),
             (0xCBA0, 60), (0xCCA1, 15), (0xCB84, 4), (0x17934, 4),
             (0xCB88, 8), (0xCC28, 40), (0xCC86, 12), (0xCCB1, 3),
             (0x28EE8, 1), (0xC61C + index * 20, 20), (0x1DD72, 80)]
    prefix_end = before.index(0, 0x1D34C)
    spans.append((0x1D34C, prefix_end - 0x1D34C + 1))
    spans.append((0x21D6 + before[0xCCB2] * 24, 24))
    def retain(arena, ranges):
        return [{'offset': offset, 'hex': arena[offset:offset + size].hex()}
                for offset, size in ranges]
    reads = [e for e in route['loader_reads'] if e['functionId'] == 'sub_00037E75']
    streams = list(dict.fromkeys(e['stream'] for e in reads))
    if len(streams) != 2:
        raise ValueError('expected independent SET and STM stream lifetimes')
    names = dict(zip(streams, ('MAP01.SET', 'MAP01.STM')))
    resources = {name: (ROOT / 'game/DAT' / name).read_bytes() for name in names.values()}
    positions = {name: 0 for name in resources}
    read_contracts = []
    for read in reads:
        name = names[read['stream']]
        data = captured(read['data'])
        offset = read['fileOffset']
        if offset != positions[name] or data != resources[name][offset:offset + len(data)]:
            raise ValueError('loader stream position/bytes differ from resource')
        if read['returnedItems'] != read['itemCount']:
            raise ValueError('this fixture requires complete reads')
        positions[name] += len(data)
        read_contracts.append({key: read[key] for key in
            ('callVaddr', 'itemSize', 'itemCount', 'returnedItems', 'fileOffset')}
            | {'resource': name, 'bytes': len(data), 'sha256': sha(data)})
    if any(positions[name] != len(data) for name, data in resources.items()):
        raise ValueError('fixture does not cover each resource completely')
    output_ranges = [(0xCB88, 8), (0xCC28, 40), (0xCC86, 12),
                     (0xCCB1, 3), (0xC61C + index * 20, 20), (0x1DD72, 80)]
    arrays = [{**{k: layer[k] for k in ('layer', 'itemSize', 'address')},
               'hex': captured(layer).hex()} for layer in states['exit']['layers']]
    for name in ('stmWords', 'mapWords'):
        info = states['exit'][name]
        arrays.append({'kind': name, 'address': info['address'], 'hex': captured(info).hex()})
    return {'authority': EXE_HASH, 'functionId': 'sub_00037E75',
            'kind': 'connected-poland-success', 'virtualBase': 0x1E0000,
            'routeSha256': sha(raw), 'probeSha256': route['loader_state_probe_sha256'],
            'collectorSha256': sha(Path(__file__).read_bytes()),
            'command': route['command'], 'hddSha256': route['hdd_sha256'],
            'qemuSha256': route['qemu_sha256'],
            'resources': {name: {'bytes': len(data), 'sha256': sha(data)}
                          for name, data in resources.items()},
            'strings': route.get('loader_strings', []),
            'input': {'stateSpans': retain(before, spans)},
            'output': {'stateSpans': retain(after, output_ranges), 'arrays': arrays,
                       'eax': states['exit']['registers']['EAX'], 'reads': read_contracts}}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('route', type=Path)
    args = parser.parse_args()
    fixture = collect(args.route)
    out = ROOT / 'tests/fixtures/dos-loader.json'
    out.write_text(json.dumps(fixture, indent=2) + '\n')
    print(f'{len(fixture["output"]["reads"])} paired DOS reads retained: {out}')
