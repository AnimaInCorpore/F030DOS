#!/usr/bin/env python3
"""N/A - coverage report for the bounded translator (METHOD.md section 4.3b).

Runs every inventory function through `translate.py` and reports three separate
sets: decoded (reachable from the entry inside the span), implemented (every
instruction has a rule) and DOS-validated (a native gate compares the generated
code with DOS fixtures: the functions named in VALIDATED). For each rule it
counts the functions using it and whether a validated function exercises it; a
rule no validated function uses is implemented but `Unproven`. The blocking
reasons of the unimplemented functions are listed most frequent first.

    python3 tools/x86x/coverage.py --out build/x86x/coverage.txt [--assemble]

`--assemble` writes every implemented function to one file and assembles it with
`$VASM` (a syntax check of the emitter; it proves nothing about behaviour).
"""
import argparse
import collections
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import translate as T  # noqa: E402

# Functions whose generated code passes a native DOS-fixture gate (tools/check-native-*.py --translated).
VALIDATED = {
    'sub_00063375': 'check-native-rng.py', 'sub_0006337B': 'check-native-rng.py', 'sub_0006339F': 'check-native-rng.py',
    'sub_00060907': 'check-native-loader.py', 'sub_00060926': 'check-native-loader.py',
    'sub_00010976': 'check-native-geometry.py', 'sub_00048105': 'check-native-geometry.py',
    'sub_00058AB4': 'check-native-shape.py', 'sub_00058EB8': 'check-native-shape.py',
    'sub_00058F9E': 'check-native-shape.py', 'sub_00059476': 'check-native-shape.py',
    'sub_00014BF6': 'check-native-compose.py',
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--assemble', action='store_true')
    args = ap.parse_args()
    build = T.pg_build()
    decoded, implemented, blocked = [], {}, collections.Counter()
    example, rule_users, source = {}, collections.defaultdict(set), []
    for vaddr, file_off, name in build.functions:
        try:
            _, _, code = build.function(name)
            T.reachable(vaddr, code, vaddr)
            decoded.append(name)
        except T.Unsupported as error:
            blocked[f'decode: {generalize(error)}'] += 1
            example.setdefault(f'decode: {generalize(error)}', name)
            continue
        try:
            lines, info = T.translate(name, build)
        except T.Unsupported as error:
            key = generalize(error)
            blocked[key] += 1
            example.setdefault(key, name)
            continue
        implemented[name] = info
        source += lines
        for rule in info['rules']:
            rule_users[rule].add(name)
    missing = sorted(set(VALIDATED) - set(implemented))
    # Call closure: a function is linkable only when every callee (transitively) is implemented.
    callees = {n: set(re.findall(r'\b(?:bsr|bra) (?:x86_)?(sub_\w+)', '\n'.join(lines_of(n, build)))) for n in implemented}
    closed = set(implemented)
    changed = True
    while changed:
        changed = False
        for n in list(closed):
            if not callees[n] <= closed:
                closed.discard(n)
                changed = True
    report = [f'# Translator coverage of {build.name} sha256 {build.sha256}', '',
              f'inventory {len(build.functions)}; decoded {len(decoded)}; implemented {len(implemented)}; '
              f'closed under calls {len(closed)}; DOS-validated {len(set(VALIDATED) & set(implemented))}'
              + (f' (NOT implemented any more: {", ".join(missing)})' if missing else ''),
              f'implemented bytes {sum(i["bytes"] for i in implemented.values())}', '',
              '## Rules: functions using each, and whether a validated function exercises it', '']
    for rule in sorted(rule_users):
        users = rule_users[rule]
        gates = sorted({VALIDATED[u] for u in users if u in VALIDATED})
        report.append(f'{rule:14} {len(users):4} functions  '
                      + (f'validated by {", ".join(gates)}' if gates else 'Unproven (no validated function uses it)'))
    report += ['', '## Implemented functions', '']
    report += [f'{n} {i["bytes"]} bytes {i["instructions"]} instructions'
               + (' [validated]' if n in VALIDATED else '') + (' [closed]' if n in closed else
               f' [calls unimplemented: {" ".join(sorted(callees[n] - set(implemented)))}]' if callees[n] - set(implemented) else
               ' [calls not closed]')
               for n, i in implemented.items()]
    report += ['', '## Blocking reasons of the others (first instance in brackets)', '']
    report += [f'{c:5} {k}  [{example[k]}]' for k, c in blocked.most_common()]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.assemble:
        asm = args.out.with_suffix('.s')
        asm.write_text('\n'.join(['        include "x86rt.i"', '        section text,code'] + source) + '\n')
        vasm = os.environ.get('VASM')
        if not vasm:
            raise SystemExit('--assemble needs $VASM')
        proc = subprocess.run([vasm, str(asm), '-quiet', '-Felf', '-m68000', '-I' + str(T.ROOT / 'src/common'),
                               '-o', str(args.out.with_suffix('.o'))], capture_output=True, text=True)
        report += ['', f'## Assembly check of all implemented functions: {"ok" if proc.returncode == 0 else "FAILED"}',
                   proc.stdout + proc.stderr]
        if proc.returncode:
            args.out.write_text('\n'.join(report) + '\n')
            raise SystemExit(proc.stdout + proc.stderr)
    args.out.write_text('\n'.join(report) + '\n')
    sys.stdout.write('\n'.join(report[:4]) + '\n')


def lines_of(name, build):
    return T.translate(name, build)[0]


def generalize(error):
    text = re.sub(r'0x[0-9a-fA-F]+', '#', str(error))
    text = re.sub(r'^[0-9A-F]{4,}: ', '', text)
    return re.sub(r'\b\d+\b', 'N', text)


if __name__ == '__main__':
    main()
