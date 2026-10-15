#!/usr/bin/env python3
"""Check that the Falcon fills the original's tables exactly as the build used to.

N/A - target validation harness. Runs the production debug build
(release/comanche_d.tos, built by tools/build-run.sh with the player's files
staged beside it) in Hatari, stops at attract_start - after src/origexe.s has
read COMANCHE.EXE and menu_init has loaded the .DTL - and dumps every table
build/port_tables.s reserves. Each dump must equal the same label's bytes in
build/original_test.s, the host reference tools/prepare-original-test.py
generates from the local install.

ring_invz_table and ring_horizon_table are expected to stay zero: they have no
reader in the port, so neither the build nor src/dtl.s fills them any more.
The comparison needs the staged COMANCHE.MNU to select HIGH ('0', what
build-run.sh stages), because the reference is generated from HIGH.DTL.

    HATARI=/path/to/patched/hatari python3 tools/check-orig-exe-load.py
"""
import json
import os
import re
import shutil
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location('cpu_check', ROOT / 'tools/check-cpu-compatibility.py')
support = module_from_spec(spec)
spec.loader.exec_module(support)
spec = spec_from_file_location('prepare', ROOT / 'tools/prepare-original-test.py')
prepare = module_from_spec(spec)
spec.loader.exec_module(prepare)

UNFILLED = {'ring_invz_table', 'ring_horizon_table'}
# Tables the sources used to carry, checked against the flat image directly:
# label, flat address, count, element bytes (4 = little-endian longs).
FROM_FLAT = (('zove_frames', 0x28E75, 6, 1), ('coma_frames', 0x59C8, 36, 1),
             ('pan_wobble', 0x5985, 64, 1), ('attract_gamma', 0x2B7D0, 64, 1),
             ('resource_gamma', 0x2B7D0, 64, 1), ('snd_rate_tab', 0x4998, 18, 4))
EXTRA = (('horizon_table', prepare.DEPTH_SAMPLES * 2), ('ring_steps', 2))
# The music driver's block mirrors flat 0002C48C-0002DA00 (src/music.s); its
# table ranges must hold the flat image's bytes at their own offsets.
MUSIC_BASE, MUSIC_END = 0x2C48C, 0x2DA00
MUSIC_TABLES = ((0x2C619, 0x30), (0x2C70D, 0x2DA00 - 0x2C70D))


def reference_tables(path):
    """{label: big-endian bytes} for every dc.b/dc.w/dc.l run in the file."""
    symbols, tables, label = {}, {}, None
    for line in path.read_text().splitlines():
        code = line.split(';', 1)[0].rstrip()
        m = re.match(r'^([A-Za-z_]\w*)\s*=\s*(\S+)$', code)
        if m:
            symbols[m.group(1)] = m.group(2)
            continue
        m = re.match(r'^([A-Za-z_]\w*):?$', code)
        if m:
            label = m.group(1)
            tables.setdefault(label, bytearray())
            continue
        m = re.match(r'^\s+dc\.([bwl])\s+(.*)$', code)
        if not (m and label):
            continue
        width = {'b': 1, 'w': 2, 'l': 4}[m.group(1)]
        for item in m.group(2).split(','):
            item = symbols.get(item.strip(), item.strip())
            value = int(item[1:], 16) if item.startswith('$') else int(item, 0)
            tables[label] += (value & ((1 << (8 * width)) - 1)).to_bytes(width, 'big')
    return tables


def main():
    release = ROOT / 'release'
    program = 'comanche_d.tos'
    for need in (program, 'COMANCHE.EXE', 'HIGH.DTL', 'COMANCHE.MNU'):
        if not (release / need).is_file():
            sys.exit(f'missing release/{need}: run tools/build-run.sh first')
    if (release / 'COMANCHE.MNU').read_bytes()[0x18] != ord('0'):
        sys.exit('release/COMANCHE.MNU does not select HIGH; the reference is HIGH.DTL')
    reference = reference_tables(ROOT / 'build/original_test.s')
    flat = (ROOT / 're/unpacked/comanche-flat32.bin').read_bytes()
    for label, addr, count, width in FROM_FLAT:
        raw = flat[addr:addr + count * width]
        reference[label] = b''.join(raw[i:i + width][::-1] for i in range(0, len(raw), width))
    labels = ([(l, n) for l, n in prepare.LOADED_STORAGE] + list(EXTRA)
              + [(l, c * w) for l, _, c, w in FROM_FLAT])

    out = ROOT / 'build/check-orig-exe-load'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    # The staged game files and the debug build only: a comanche.tos beside
    # comanche_d.tos is the same 8.3 name to TOS, which then runs the stripped
    # one and the symbols do not match.
    for f in release.iterdir():
        if f.is_file() and (f.name == program or f.name == f.name.upper()):
            shutil.copy2(f, out / f.name)
    # Two stops. snd_init is main's first call after orig_exe_load, before
    # anything writes into the texts (menu_init marks radio items in
    # menu_group_text, the roster fills menu_screen_text's pilot field);
    # attract_start comes after menu_init's .DTL load. `symbols comanche_d.tos`
    # is refused at TEXT ("program TEXT address invalid"); `symbols prg` takes
    # them from the program GEMDOS just ran.
    loader = [(l, n) for l, n in labels if not l.startswith('ring_') and l not in dict(EXTRA)]
    dtl = [(l, n) for l, n in labels if (l, n) not in loader]

    def saves(items):
        lines = []
        for label, size in items:
            # The DRI symbol table keeps 22 characters, so the bearing table is
            # reached through the octant table it follows in port_tables.s.
            if label == 'object_bearing_correction':
                lines.append(f'savebin octant_and_bearing.bin object_octant_table ${32 + size:x}')
            else:
                lines.append(f'savebin {label}.bin {label} ${size:x}')
        return '\n'.join(lines) + '\n'
    support.entry_breakpoint(out, program, '')
    (out / 'arm.ini').write_text('symbols prg\nb pc = snd_init :once :file early.ini\n')
    (out / 'early.ini').write_text(saves(loader) + f'savebin music_mem.bin music_mem ${MUSIC_END - MUSIC_BASE:x}\n'
                                   + 'b pc = attract_start :once :file done.ini\n')
    (out / 'done.ini').write_text(saves(dtl) + 'quit\n')
    command = support.emulator_command(out, 68030, program, 'boot.ini')
    command[command.index('--run-vbls') + 1] = '3000'
    (out / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    support.run(command, out, out / 'hatari.log', timeout=600)

    pair = out / 'octant_and_bearing.bin'
    if pair.is_file():
        (out / 'object_bearing_correction.bin').write_bytes(pair.read_bytes()[32:])
    failures = 0
    for label, size in labels:
        dump = out / f'{label}.bin'
        if not dump.is_file():
            print(f'FAIL {label}: no dump (the program never reached attract_start)')
            failures += 1
            continue
        actual = dump.read_bytes()
        expected = bytes(size) if label in UNFILLED else bytes(reference[label])
        if len(expected) != size:
            print(f'FAIL {label}: reference has {len(expected)} bytes, storage {size}')
            failures += 1
        elif actual != expected:
            first = next(i for i, (a, b) in enumerate(zip(actual, expected)) if a != b)
            print(f'FAIL {label}: byte {first} is {actual[first]:02x}, expected {expected[first]:02x}')
            failures += 1
        else:
            print(f'ok   {label} ({size} bytes{", zero: no reader" if label in UNFILLED else ""})')
    dump = out / 'music_mem.bin'
    block = dump.read_bytes() if dump.is_file() else b''
    for addr, size in MUSIC_TABLES:
        actual = block[addr - MUSIC_BASE:addr - MUSIC_BASE + size]
        if actual != flat[addr:addr + size]:
            print(f'FAIL music tables at {addr:08X}: not the image\'s {size} bytes')
            failures += 1
        else:
            print(f'ok   music tables at {addr:08X} ({size} bytes)')
    if failures:
        sys.exit(f'{failures} table(s) differ')
    print(f'PASS: all {len(labels)} tables equal build/original_test.s, '
          f'the music tables the flat image')


if __name__ == '__main__':
    main()
