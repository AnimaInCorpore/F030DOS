#!/usr/bin/env python3
r"""Convert game/SWTieCD/cd/SWTIECD.BIN (raw MODE1/2352) to a 2048-byte/sector
ISO that QEMU (-cdrom) and 86Box can mount.

The .cue says `TRACK 01 MODE1/2352`, i.e. every sector on disk is 2352 bytes:
    12 sync + 3 header (min/sec/frame) + 1 mode + 2048 user data + 288 EDC/ECC
and 623,837,424 / 2352 = 265,237 sectors exactly.  Emulators want just the user
data, so copy bytes [16:2064] out of each sector.

TIE.EXE refuses to start without the CD ("ERROR #3: You must insert TIE-Fighter
CD into your cd-rom drive"), so the CD is part of a working image set -- but DOS
also needs an ATAPI CD-ROM *device driver* before MSCDEX can assign a letter.
See analysis/qemu-boot.md.

Usage: python work/bin2iso.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'game', 'SWTieCD', 'cd', 'SWTIECD.BIN')
DST = os.path.join(ROOT, 'game', 'SWTieCD', 'cd', 'SWTIECD.iso')

RAW, USER, OFF = 2352, 2048, 16

size = os.path.getsize(SRC)
if size % RAW:
    sys.exit(f'{SRC}: {size} B is not a whole number of 2352-byte sectors')
sectors = size // RAW
print(f'{sectors} raw sectors -> {sectors * USER} B ISO')

with open(SRC, 'rb') as fi, open(DST, 'wb') as fo:
    done = 0
    while True:
        chunk = fi.read(RAW * 512)                 # 512 sectors at a time
        if not chunk:
            break
        fo.write(b''.join(chunk[i + OFF:i + OFF + USER]
                          for i in range(0, len(chunk), RAW)))
        done += len(chunk) // RAW
        if done % 51200 == 0:
            print(f'  {done}/{sectors}')

with open(DST, 'rb') as f:
    f.seek(16 * USER + 1)                          # ISO9660 PVD, sector 16
    magic = f.read(5)
print(f'wrote {DST} ({os.path.getsize(DST)} B); PVD magic = {magic!r}')
if magic != b'CD001':
    sys.exit('not a valid ISO9660 -- check the track mode in the .cue')
