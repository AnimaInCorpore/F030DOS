#!/usr/bin/env python3
"""Audit the LPF cutscene containers (CUTS/CSxxx.Nxx).

Structure measured across all 39 LPF files in work/extracted; see
analysis/data-formats.md, "LPF". UW1's doc had only a partial reading of the
0x80-byte header and nothing below it -- the large-page layer is new here.

  0x00  "LPF "
  0x04  u16  0x0100                  constant in all 39
  0x06  u16  nLargePages             1..6
  0x08  u32  nRecords                total records (frames)
  0x0C  u16  0x0100                  constant (max records per large page)
  0x0E  u16  0x0500                  offset of the large-page directory
  0x10  4CC  "ANIM"                  the only content type present
  0x14  u16  0x0140 = 320            width
  0x16  u16  0x00C8 = 200            height  -> VGA mode 13h
  0x18  u16  0                       constant
  0x1A  u16  0x0101 or 0
  0x1C  u16  0x0100                  constant
  0x40  u32  == the nRecords at 0x08 (duplicated)
  0x44  u32  small, varies

  0x0500  large-page directory: 256 x { u16 baseRecord, u16 nRecords,
          u16 nBytes }, of which the first nLargePages are used.
  0x0B00  ( = 0x0500 + 256*6 ) large pages, each occupying 0x10000 bytes:
          page k at 0x0B00 + k*0x10000, starting with an 8-byte header --
          the same {baseRecord, nRecords, nBytes} triple as the directory
          entry, plus a zero u16 -- then nRecords u16 record sizes, then the
          record payloads back to back.

Verified: sum(entry.nRecords) == header nRecords in 39/39 files; every page
repeats its directory entry in 39/39; sum(record sizes) == nBytes in 60/64
pages (the four exceptions are reported by --check, and are NOT explained).

Container accounting is audited here. The recovered record/frame decoder and
the deterministic intro fixture export live in work/cutscene_export.py.
"""
import argparse
import struct
from collections import Counter
from pathlib import Path

ROOT = Path("work/extracted")
DIR_OFFSET = 0x0500          # also stored in the u16 at 0x0E
PAGE_BASE = 0x0B00           # DIR_OFFSET + 256*6
PAGE_STRIDE = 0x10000


def lpf_files():
    return [f for f in sorted(ROOT.rglob("*"))
            if f.is_file() and f.read_bytes()[:4] == b"LPF "]


def header(d):
    return dict(
        n_pages=struct.unpack_from("<H", d, 0x06)[0],
        n_records=struct.unpack_from("<I", d, 0x08)[0],
        dir_offset=struct.unpack_from("<H", d, 0x0E)[0],
        content=d[0x10:0x14].decode("latin1"),
        width=struct.unpack_from("<H", d, 0x14)[0],
        height=struct.unpack_from("<H", d, 0x16)[0],
    )


def pages(d):
    """Yield (index, dir_entry, page_header, [record sizes])."""
    h = header(d)
    for k in range(h["n_pages"]):
        entry = struct.unpack_from("<3H", d, h["dir_offset"] + 6 * k)
        p = PAGE_BASE + k * PAGE_STRIDE
        phdr = struct.unpack_from("<4H", d, p)
        sizes = struct.unpack_from(f"<{entry[1]}H", d, p + 8)
        yield k, entry, phdr, list(sizes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="run every invariant")
    ap.add_argument("--file", help="dump one file's structure")
    a = ap.parse_args()
    files = lpf_files()

    if a.file:
        f = next(x for x in files if x.name == a.file)
        d = f.read_bytes()
        h = header(d)
        print(f"{f}: {len(d)} B")
        print(f"  {h['content']} {h['width']}x{h['height']}, "
              f"{h['n_records']} records in {h['n_pages']} large page(s)")
        for k, e, ph, sizes in pages(d):
            print(f"  page {k}: base={e[0]} n={e[1]} nBytes={e[2]}  "
                  f"header repeats entry: {ph[:3] == e} (pad={ph[3]})")
            print(f"    sizes sum={sum(sizes)}  zero-length={sizes.count(0)}/{len(sizes)}")
        return

    rec_ok = pg_ok = 0
    size_ok = size_tot = 0
    zero = tot = 0
    anomalies = []
    for f in files:
        d = f.read_bytes()
        h = header(d)
        entries = [e for _, e, _, _ in pages(d)]
        rec_ok += sum(e[1] for e in entries) == h["n_records"]
        pg_ok += all(ph[:3] == e for _, e, ph, _ in pages(d))
        for k, e, _, sizes in pages(d):
            size_tot += 1
            if sum(sizes) == e[2]:
                size_ok += 1
            else:
                anomalies.append((f.name, k, e[1], e[2], sum(sizes),
                                  sum(sizes) - e[2], -(2 * e[1] + 8)))
            zero += sizes.count(0)
            tot += len(sizes)
    n = len(files)
    print(f"{n} LPF files, {size_tot} large pages, {tot} records")
    print(f"  sum(entry.nRecords) == header nRecords : {rec_ok}/{n}")
    print(f"  every page repeats its directory entry : {pg_ok}/{n}")
    print(f"  sum(record sizes) == page nBytes       : {size_ok}/{size_tot}")
    print(f"  zero-length records (unchanged frames) : {zero}/{tot} "
          f"({100 * zero // tot}%)")
    if anomalies:
        print("\n  UNEXPLAINED -- these pages' record sizes do not sum to nBytes;")
        print("  the residual equals -(2*n + 8) exactly in every case, i.e. the")
        print("  page header + size table, but why only here is not known:")
        print(f"    {'file':<13} {'pg':>2} {'n':>4} {'nBytes':>7} {'sum':>7} "
              f"{'resid':>7} {'-(2n+8)':>8}")
        for row in anomalies:
            print(f"    {row[0]:<13} {row[1]:>2} {row[2]:>4} {row[3]:>7} "
                  f"{row[4]:>7} {row[5]:>7} {row[6]:>8}")


if __name__ == "__main__":
    main()
