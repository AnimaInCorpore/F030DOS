#!/usr/bin/env python3
"""N/A - retain one captured DOS frame (indexed pixels + palette) for the display path.

Pixels are the oracle's 640x480 8-bit framebuffer; the palette is recovered from
the matching screendump, which is only possible for indices the frame uses
(each must map to exactly one colour). Unused indices are zero and unproven."""
import argparse
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('capture_dir',type=Path)
parser.add_argument('name')
args=parser.parse_args()
route=json.loads((args.capture_dir/'route.json').read_text())
if route['status']!='CAPTURED' or not route['hdd_unchanged'] or route['qemu_returncode']:
    raise ValueError('completed unchanged DOS route required')
if hashlib.sha256((ROOT/'game/EXE/PANZER.EXE').read_bytes()).hexdigest()!=route['exe_sha256']:
    raise ValueError('wrong DOS build')
vram=(args.capture_dir/(args.name+'.vram')).read_bytes()
ppm=(args.capture_dir/(args.name+'.ppm')).read_bytes()
head=ppm.split(b'\n',3)
if head[0]!=b'P6' or head[1]!=b'640 480' or head[2]!=b'255' or len(head[3])!=640*480*3 or len(vram)!=640*480:
    raise ValueError('unexpected capture geometry')
rgb=head[3]
palette={}
for i,index in enumerate(vram):
    colour=rgb[3*i:3*i+3]
    if palette.setdefault(index,colour)!=colour:
        raise ValueError(f'palette index {index} maps to two colours')
table=bytearray(768)
for index,colour in palette.items():
    table[3*index:3*index+3]=colour
dest=ROOT/'tests/fixtures'
(dest/f'dos-frame-{args.name}.pixels').write_bytes(vram)
(dest/f'dos-frame-{args.name}.palette').write_bytes(bytes(table))
(dest/f'dos-frame-{args.name}.json').write_text(json.dumps({
    'authority':route['exe_sha256'],'routeSha256':hashlib.sha256((args.capture_dir/'route.json').read_bytes()).hexdigest(),
    'screen':'640x480 8-bit','pixelsSha256':hashlib.sha256(vram).hexdigest(),
    'screendumpSha256':hashlib.sha256(ppm).hexdigest(),'usedIndices':len(palette),
    'note':'palette recovered from the screendump; entries for unused indices are zero and unproven'},indent=2)+'\n')
print(f'{args.name}: {len(palette)} palette indices used; fixture written to {dest}')
