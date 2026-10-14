"""N/A - host evidence check: compare captured DOS reads with pristine files."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('SCENSTAT.BIN', 'GAME001.SCN', 'MAP01.SET', 'MAP01.STM', 'AXARROW1.SHP')


def check(out):
    record = json.loads((out / 'route.json').read_text())
    problems, covered, counts = [], {}, {}
    if record['status'] != 'CAPTURED' or not record['hdd_unchanged']:
        problems.append('route did not pass capture/source-disk gates')
    for event in record.get('file_io', []):
        if event['kind'] != 'read' or event['return_eax'] >= 0x80000000:
            continue
        path, position = event['path'], event['position']
        if path is None or position is None or not path.lower().startswith('..\\dat\\'):
            problems.append('read has no measured DAT path/position')
            continue
        name = path.replace('\\', '/').split('/')[-1].upper()
        if name not in REQUIRED:
            problems.append(f'read outside declared resource set: {name}')
            continue
        data = (out / event['data_file']).read_bytes()
        source = (ROOT / 'game/DAT' / name).read_bytes()
        if (len(data) != event['return_eax'] or
                hashlib.sha256(data).hexdigest() != event['data_sha256'] or
                data != source[position:position + len(data)]):
            problems.append(f'captured read differs from pristine {name} at {position}')
        covered.setdefault(name, set()).update(range(position, position + len(data)))
        counts[name] = counts.get(name, 0) + 1
    for name in REQUIRED:
        size = (ROOT / 'game/DAT' / name).stat().st_size
        if covered.get(name, set()) != set(range(size)):
            problems.append(f'incomplete raw-byte witness for {name}')
        print(f'{name}: {len(covered.get(name, set()))}/{size} bytes, {counts.get(name, 0)} reads')
    for problem in problems:
        print('Unproven:', problem)
    return not problems


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    raise SystemExit(0 if check(parser.parse_args().out) else 1)
