#!/usr/bin/env python3
"""N/A - build the Falcon show-frame program and check its video memory against DOS pixels.

The expected bitplane bytes come from an independent host conversion of the
captured DOS pixels; they are never produced by the m68k code. The same run
checks that the XBIOS mode switch took effect (mode word, physical base)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def planar(pixels):
    out = bytearray()
    for group in range(0, len(pixels), 16):
        chunk = pixels[group:group + 16]
        for plane in range(8):
            word = 0
            for i, value in enumerate(chunk):
                word |= ((value >> plane) & 1) << (15 - i)
            out += struct.pack('>H', word)
    return bytes(out)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--name', default='poland_tactical')
parser.add_argument('--monitor', choices=('vga', 'rgb'), default='vga')
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
meta_path = ROOT / f'tests/fixtures/dos-frame-{args.name}.json'
meta = json.loads(meta_path.read_text())
if sha(ROOT / 'game/EXE/PANZER.EXE') != meta['authority']:
    raise ValueError('wrong DOS build')
pixels = (ROOT / f'tests/fixtures/dos-frame-{args.name}.pixels').read_bytes()
palette = (ROOT / f'tests/fixtures/dos-frame-{args.name}.palette').read_bytes()
if hashlib.sha256(pixels).hexdigest() != meta['pixelsSha256']:
    raise ValueError('frame fixture hash mismatch')
(out / 'frame.pixels').write_bytes(pixels)
(out / 'frame.palette.bin').write_bytes(b''.join(
    struct.pack('>L', palette[3 * i] << 16 | palette[3 * i + 1] << 8 | palette[3 * i + 2]) for i in range(256)))
expected = planar(pixels)
(out / 'expected.bin').write_bytes(expected)
toolroot = ROOT.parent / 'F030Arcade/third_party/chorensha/tools'
vasm = Path(os.environ.get('VASM', toolroot / 'vasmm68k_mot_mac')).resolve()
vlink = Path(os.environ.get('VLINK', toolroot / 'vlink_mac')).resolve()
hatari = Path(shutil.which(os.environ.get('HATARI', 'hatari'))).resolve()
tos = Path(os.environ.get('TOS', ROOT.parent / 'F030Comanche/tools/toolchain/tos402.rom')).resolve()
assemble = [str(vasm), str(ROOT / 'src/target/falcon/showframe.s'), '-quiet', '-Felf',
            '-m68000', '-I' + str(ROOT / 'src/common'), '-o', str(out / 'frame.o'),
            '-L', str(out / 'frame.lst')]
link = [str(vlink), str(out / 'frame.o'), '-q', '-Rstd', '-b', 'ataritos',
        '-tos-flags', '1', '-e', '_main', '-M', '-o', str(out / 'PGFRAME.TOS')]
subprocess.run(assemble, cwd=out, check=True)
with (out / 'PGFRAME.map').open('w') as log:
    subprocess.run(link, cwd=out, check=True, stdout=log, stderr=subprocess.STDOUT)
(out / 'dbg.ini').write_text('logfile dbg.txt' + chr(10) + 'b VBL = 1500 :once :file grab.ini' + chr(10))
(out / 'grab.ini').write_text(chr(10).join(['m $ffff9800 1024', 'm $ffff8201 1', 'm $ffff8203 1',
                                             'm $ffff820d 1', 'quit']) + chr(10))
command = [str(hatari), '--machine', 'falcon', '--cpulevel', '3', '--cpuclock', '16',
           '--cpu-exact', 'true', '--compatible', 'true', '--frameskips', '0', '--fpu', 'none',
           '--memsize', '4', '--tos', str(tos), '--patch-tos', 'true', '--mmu', 'true', '--dsp', 'off',
           '--monitor', args.monitor, '--sound', 'off', '--fast-boot', 'true', '--fast-forward', 'true',
           '--confirm-quit', 'off', '--disable-video', 'on', '--run-vbls', '2400',
           '--alert-level', 'fatal', '--parse', 'dbg.ini', 'PGFRAME.TOS']
sources = [ROOT / 'src/common/c2p.s', ROOT / 'src/target/falcon/showframe.s', Path(__file__)]
record = {'status': 'Unproven', 'assemble': assemble, 'link': link, 'command': command,
          'sha256': {str(p): sha(p) for p in [vasm, vlink, hatari, tos, meta_path, out / 'PGFRAME.TOS', *sources]}}
want_mode = {'vga': 0x1b, 'rgb': 0x12b}[args.monitor]
want_montype = {'vga': 2, 'rgb': 1}[args.monitor]
try:
    with (out / 'hatari.log').open('w') as log:
        proc = subprocess.run(command, cwd=out, stdin=subprocess.DEVNULL,
                              stdout=log, stderr=subprocess.STDOUT, timeout=300)
    record['hatariReturncode'] = proc.returncode
    result = out / 'PGFRAME.OUT'
    data = result.read_bytes() if result.is_file() else b''
    if proc.returncode or len(data) != 8 + len(expected):
        raise RuntimeError(f'no complete result ({len(data)} bytes); see {out}')
    physbase, mode, montype = struct.unpack('>LHH', data[:8])
    record.update(physbase=physbase, mode=mode, montype=montype)
    mask = 0x1df if args.monitor == 'vga' else 0x1ff   # the PAL bit carries no meaning on a VGA monitor
    if (mode & mask) != (want_mode & mask) or montype != want_montype or physbase & 0xff:
        raise RuntimeError(f'video mode not as requested: mode {mode:#x} montype {montype} base {physbase:#x}')
    if data[8:] != expected:
        first = next(i for i in range(len(expected)) if data[8 + i] != expected[i])
        raise RuntimeError(f'video memory differs from the DOS pixels at byte {first}; see {out}')
    # Videl registers and palette as the emulated hardware holds them after the run.
    dump = {}
    for line in (out / 'dbg.txt').read_text(errors='replace').splitlines():
        address, _, rest = line.partition(': ')
        if len(address) == 8 and rest:
            dump[int(address, 16)] = bytes.fromhex(''.join(rest[:48].split()))
    regs = b''.join(dump.get(a, b'') for a in (0xffff8201, 0xffff8203, 0xffff820d))
    videl_base = regs[0] << 16 | regs[1] << 8 | regs[2] if len(regs) == 3 else None
    hw_palette = b''.join(dump[0xffff9800 + 16 * i] for i in range(64))
    if videl_base != physbase:
        raise RuntimeError(f'Videl base {videl_base} differs from Physbase {physbase:#x}')
    for i in range(256):
        want = bytes([palette[3 * i] & 0xfc, palette[3 * i + 1] & 0xfc, 0, palette[3 * i + 2] & 0xfc])
        if hw_palette[4 * i:4 * i + 4] != want:
            raise RuntimeError(f'Videl palette entry {i} is {hw_palette[4 * i:4 * i + 4].hex()}, want {want.hex()}')
    record.update(status='Verified chunky-to-planar conversion, mode switch, Videl base and palette',
                  bytesCompared=len(expected), resultSha256=sha(result))
    print(f'PASS native frame ({args.monitor}): mode {mode:#x}, base {physbase:#x}, '
          f'{len(expected)} planar bytes equal the independent host conversion of the DOS pixels; '
          f'Videl base and all 256 palette entries match')
finally:
    (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
