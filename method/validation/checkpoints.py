"""N/A - exact comparisons at declared logical checkpoints, independent of clocks."""


def compare(expected, actual, fields):
    """Compare ordered {key, state} records; never sort, deduplicate or mask state.

    Keys must include every context dimension that can repeat (e.g. route,
    phase, replay pass, cursor). Adapters normalize endian/widths explicitly.
    This reports agreement, not provenance or DOS certification.
    """
    fields = tuple(fields)
    if not expected or not fields:
        raise ValueError('nonempty checkpoints and explicit fields required')
    for label, records in (('expected', expected), ('actual', actual)):
        seen = set()
        for row in records:
            key = row['key']
            if not isinstance(key, (str, int)) or isinstance(key, bool) or key in seen:
                raise ValueError(f'{label}: invalid or duplicate checkpoint {key!r}')
            seen.add(key)
            if any(f not in row['state'] or row['state'][f] is None for f in fields):
                raise ValueError(f'{label}: missing state at checkpoint {key!r}')
    for index in range(max(len(expected), len(actual))):
        want = expected[index] if index < len(expected) else None
        got = actual[index] if index < len(actual) else None
        if want is None or got is None or want['key'] != got['key']:
            return {'status': 'DIVERGENCE', 'compared': index,
                    'first': {'index': index, 'kind': 'checkpoint',
                              'expected': None if want is None else want['key'],
                              'actual': None if got is None else got['key']}}
        for field in fields:
            if type(want['state'][field]) is not type(got['state'][field]) or want['state'][field] != got['state'][field]:
                return {'status': 'DIVERGENCE', 'compared': index + 1,
                        'first': {'index': index, 'key': want['key'], 'kind': 'state',
                                  'field': field, 'expected': want['state'][field],
                                  'actual': got['state'][field]}}
    return {'status': 'PASS', 'compared': len(expected), 'first': None}


def byte_difference(expected, actual):
    """First unequal byte or length boundary; no ignored memory ranges."""
    for offset, (want, got) in enumerate(zip(expected, actual)):
        if want != got:
            return {'offset': offset, 'expected': want, 'actual': got}
    if len(expected) != len(actual):
        offset = min(len(expected), len(actual))
        return {'offset': offset, 'expected': expected[offset] if offset < len(expected) else None,
                'actual': actual[offset] if offset < len(actual) else None}
    return None
