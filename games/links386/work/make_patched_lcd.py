#!/usr/bin/env python3
r"""Build the CS-override diagnostic: a derived LCD.EXE and a derived image.

`analysis/executable.md` attributes the `10049` failure to QEMU dropping the
`CS` segment override on a data reference when `DS`/`ES`/`SS` bases are all
zero (`work/segtest/` proves the emulator behaviour on its own).  This builds
the other half of the proof, inside the game: replace every
`mov ds, cs:[0x3F8]` in the bound extender with the extender's *own* immediate
idiom, and the `10049` disappears.

    2E 8E 1D F8 03 00 00    mov ds, cs:[0x3F8]      7 bytes
    68 10 00 00 00 1F 90    push 0x10 / pop ds / nop 7 bytes

Same length, no structural change, and equivalent because the slot is measured
`0x0010` at every observed read.  `push imm32 / pop ds` is not an invention:
it is what the extender's own dispatcher does at `0xC2B680`, and the byte
sequence occurs verbatim in the shipped image.

**This is a diagnostic, not an oracle.**  The patched build is not a
behavioural authority for anything about Links 386, and it does not survive
past the gate either -- it dies on `push dword cs:[0x3F8]` at `0xC357E3`, the
next CS-override read of the same variable, which is itself further evidence
for the diagnosis.  See `analysis/executable.md`.

    python work/make_patched_lcd.py           # derived exe + derived image
    python work/run_qemu.py --hdd img/links386_qemufix.hdd \
        --timeout 60 --key 8:y --key 14:y --key 22:y --shot 40

Neither `game/cd/` nor `img/links386.hdd` is touched.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosimg

ROOT = dosimg.find_project_root(__file__)
SRC = os.path.join(ROOT, 'work', 'install', 'LINKS386', 'LCD.EXE')
OUT_DIR = os.path.join(ROOT, 'work', 'patched')
OUT = os.path.join(OUT_DIR, 'LCD.EXE')
HDD = os.path.join(ROOT, 'img', 'links386.hdd')
DERIVED = os.path.join(ROOT, 'img', 'links386_qemufix.hdd')

PATTERN = bytes.fromhex('2e8e1df8030000')      # mov ds, cs:[0x3F8]
REPLACE = bytes.fromhex('68100000001f90')      # push 0x10 / pop ds / nop
IDIOM   = bytes.fromhex('68100000001f')        # the same, without the padding


def main():
    if not os.path.isfile(SRC):
        sys.exit(f'missing {SRC} -- run tools/stage_install.py first')
    data = bytearray(open(SRC, 'rb').read())
    original = bytes(data)
    # The idiom must be the extender's own, not something invented for the
    # patch -- check the shipped image still contains it before relying on it.
    if IDIOM not in original:
        sys.exit('`push 0x10 / pop ds` does not occur in this build; the '
                 'replacement would be an invention, not the extender\'s own '
                 'idiom -- re-check before patching')
    print(f'idiom `push 0x10 / pop ds` verified at file '
          f'{original.find(IDIOM):#x} in the shipped image')
    sites = [m.start() for m in re.finditer(re.escape(PATTERN), original)]
    if not sites:
        sys.exit('no `mov ds, cs:[0x3F8]` sites found -- wrong build?')
    for off in sites:
        data[off:off + len(PATTERN)] = REPLACE
    os.makedirs(OUT_DIR, exist_ok=True)
    open(OUT, 'wb').write(bytes(data))
    print(f'source  {SRC}')
    print(f'        sha256 {hashlib.sha256(original).hexdigest()}')
    print(f'patched {OUT}')
    print(f'        sha256 {hashlib.sha256(bytes(data)).hexdigest()}')
    print(f'{len(sites)} site(s) replaced, {len(original)} bytes in and out')

    if not os.path.isfile(HDD):
        sys.exit(f'missing {HDD}; build it with work/build_dos_hdd.py')
    shutil.copyfile(HDD, DERIVED)
    shutil.copyfile(HDD + '.geom.json', DERIVED + '.geom.json')
    part = json.load(open(HDD + '.geom.json'))['part_offset']
    env = dict(os.environ, MTOOLS_SKIP_CHECK='1')
    p = subprocess.run([dosimg.host_tool('mcopy'), '-o', '-i',
                        f'{DERIVED}@@{part}', OUT, '::/LINKS386/LCD.EXE'],
                       capture_output=True, text=True, env=env)
    if p.returncode:
        sys.exit(f'mcopy failed: {p.stdout}{p.stderr}')
    print(f'staged into {DERIVED} (the canonical image is untouched)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
