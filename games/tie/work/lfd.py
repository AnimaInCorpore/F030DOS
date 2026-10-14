#!/usr/bin/env python3
"""LFD/LFB container reader for TIE Fighter (todo P2.1).

Verified byte-wise over all 175 .LFD/.LFB files in game/SWTieCD/TIECD
(see analysis/LFD.md).  Every file is a flat chain of 16-byte-headed records:

    struct { char type[4]; char name[8]; u32le length; }  followed by `length` bytes

105 files open with an `RMAP` record whose payload is the index: one copy of
each following record's 16-byte header, in file order.  The 70 cockpit files
in CP320/ and CP640/ have no RMAP and start straight at the first PANL.
The last record always ends exactly at EOF.
"""
import struct, sys, os

HDR = struct.Struct("<4s8sI")
HDR_SIZE = HDR.size          # 16


class Record:
    __slots__ = ("type", "name", "length", "offset", "data")

    def __init__(self, type_, name, length, offset, data):
        self.type, self.name, self.length = type_, name, length
        self.offset, self.data = offset, data

    @property
    def id(self):
        return f"{self.type}:{self.name}"

    def __repr__(self):
        return f"<{self.type} {self.name!r} len={self.length} @0x{self.offset:X}>"


def _ascii(b):
    return b.split(b"\0")[0].decode("ascii", "replace")


def read_header(buf, off):
    type_, name, length = HDR.unpack_from(buf, off)
    return _ascii(type_), _ascii(name), length


def parse(buf):
    """-> (records, rmap_entries or None).  Raises ValueError on a broken chain."""
    if len(buf) < HDR_SIZE:
        raise ValueError("shorter than one record header")
    records, off = [], 0
    while off < len(buf):
        if off + HDR_SIZE > len(buf):
            raise ValueError(f"truncated header at 0x{off:X}")
        t, n, l = read_header(buf, off)
        end = off + HDR_SIZE + l
        if end > len(buf):
            raise ValueError(f"record {t}:{n} @0x{off:X} runs {end - len(buf)} B past EOF")
        records.append(Record(t, n, l, off, buf[off + HDR_SIZE:end]))
        off = end

    entries = None
    if records[0].type == "RMAP":
        rmap = records.pop(0)
        if rmap.length % HDR_SIZE:
            raise ValueError(f"RMAP length {rmap.length} is not a multiple of {HDR_SIZE}")
        entries = [read_header(rmap.data, i * HDR_SIZE)
                   for i in range(rmap.length // HDR_SIZE)]
        if len(entries) != len(records):
            raise ValueError(f"RMAP lists {len(entries)} entries, file holds {len(records)}")
        for e, r in zip(entries, records):
            if e != (r.type, r.name, r.length):
                raise ValueError(f"RMAP entry {e} != record {r}")
    return records, entries


def load(path):
    with open(path, "rb") as fh:
        return parse(fh.read())


def iter_lfd(root):
    """Yield every .LFD/.LFB path under `root`."""
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f.upper().endswith((".LFD", ".LFB")):
                yield os.path.join(dirpath, f)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        try:
            records, entries = load(path)
        except ValueError as exc:
            print(f"{path}: FAIL {exc}")
            continue
        print(f"{path}: {len(records)} records, "
              f"{'RMAP index' if entries is not None else 'no RMAP'}, "
              f"{os.path.getsize(path)} B")
        for r in records:
            print(f"   {r.type:4} {r.name:<8} {r.length:>8} @0x{r.offset:06X}")
