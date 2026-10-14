"""N/A - attribute measured target costs to canonical DOS sites per logical checkpoint.

python3 -m validation.profile source-map.json events.json
Events: {sourceSha256, generatedSha256, linkedSha256, checkpoints: [key, ...], events:
[{checkpoint, label, cycles}, ...]}. Zero-work checkpoints remain in denominator.
Cycles come from the collector; this tool does not estimate target timing.
"""
import argparse
import json


def summarize(source_map, trace):
    if not source_map.get('sourceSha256') or source_map['sourceSha256'] != trace.get('sourceSha256'):
        raise ValueError('source build identity mismatch')
    if not source_map.get('generatedSha256') or source_map['generatedSha256'] != trace.get('generatedSha256'):
        raise ValueError('generated code identity mismatch')
    if not source_map.get('linkedSha256') or source_map['linkedSha256'] != trace.get('linkedSha256'):
        raise ValueError('linked binary identity mismatch')
    checkpoints = trace['checkpoints']
    if not checkpoints or len(set(checkpoints)) != len(checkpoints):
        raise ValueError('nonempty unique logical checkpoints required')
    sites = {}
    for site in source_map['sites']:
        if site['label'] in sites:
            raise ValueError('duplicate source label')
        sites[site['label']] = site
    totals = {}
    for event in trace['events']:
        if event['checkpoint'] not in checkpoints or event['label'] not in sites:
            raise ValueError('unmapped source site or checkpoint')
        cycles = event['cycles']
        if type(cycles) is not int or cycles < 0:
            raise ValueError('cycles must be a nonnegative integer')
        site = sites[event['label']]
        key = (site['functionId'], site['pc'])
        totals[key] = totals.get(key, 0) + cycles
    return {'checkpoints': len(checkpoints), 'cycles': sum(totals.values()),
            'cyclesPerCheckpoint': sum(totals.values()) / len(checkpoints),
            'sites': [{'functionId': f, 'pc': pc, 'cycles': cost,
                       'cyclesPerCheckpoint': cost / len(checkpoints)}
                      for (f, pc), cost in sorted(totals.items(), key=lambda item: (-item[1], item[0]))]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_map')
    parser.add_argument('events')
    args = parser.parse_args()
    with open(args.source_map) as stream:
        source_map = json.load(stream)
    with open(args.events) as stream:
        trace = json.load(stream)
    print(json.dumps(summarize(source_map, trace), indent=2))


if __name__ == '__main__':
    main()
