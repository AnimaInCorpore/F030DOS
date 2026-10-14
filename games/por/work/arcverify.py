#!/usr/bin/env python3
"""Verify work/expanded/ against the ARC directory entries in game/POR/.

ARC entry header (29 B, verified against DISKA.ARC @0x00):
    0x00 u8      0x1A magic
    0x01 u8      compression method (0 = end-of-archive marker)
    0x02 char13  filename, NUL-terminated (tail bytes not always zeroed)
    0x0F u32LE   compressed size
    0x13 u16LE   DOS date
    0x15 u16LE   DOS time
    0x17 u16LE   CRC-16/ARC of the *expanded* data
    0x19 u32LE   original size
Data follows; archive ends with the 2-byte marker 1A 00.
"""
import struct, sys, os

ARCS = ["game/POR/Disk1/DISKA.ARC", "game/POR/Disk1/DISKB.ARC",
        "game/POR/Disk1/SAVE.ARC",  "game/POR/Disk2/DISKC.ARC"]
EXPANDED = "work/expanded"

def crc16_arc(buf):
    crc = 0
    for b in buf:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc

def entries(path):
    d = open(path, "rb").read()
    o = 0
    while o + 29 <= len(d) and d[o] == 0x1A:
        m = d[o + 1]
        if m == 0:
            break
        name = d[o + 2:o + 15].split(b"\0")[0].decode("latin1")
        csz, dt, tm, crc, osz = struct.unpack("<IHHHI", d[o + 15:o + 29])
        yield m, name, csz, crc, osz
        o += 29 + csz

def main():
    total = bad = 0
    methods = {}
    for arc in ARCS:
        for m, name, csz, crc, osz in entries(arc):
            total += 1
            methods[m] = methods.get(m, 0) + 1
            p = os.path.join(EXPANDED, name)
            if not os.path.exists(p):
                print(f"MISSING  {name:14s} ({os.path.basename(arc)})"); bad += 1; continue
            data = open(p, "rb").read()
            if len(data) != osz:
                print(f"SIZE     {name:14s} got {len(data)} want {osz}"); bad += 1; continue
            got = crc16_arc(data)
            if got != crc:
                print(f"CRC      {name:14s} got {got:04x} want {crc:04x}"); bad += 1
    print(f"{total} entries, {total - bad} OK, {bad} bad; methods {dict(sorted(methods.items()))}")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
