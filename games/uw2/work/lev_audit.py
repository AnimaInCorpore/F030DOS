#!/usr/bin/env python3
"""Independent LEV.ARK audit: header + variable-length record stream + data-pool
coverage.  Implements the model documented in F030Underworld's
analysis/data-formats.md #LEV.ARK (container skeleton RESOLVED there): from
file offset 4, a stream of mostly-10-byte records (u16 id, u32 start, u32 end)
with some carrying trailing extra bytes before the next record.

Two things learned building this (see this project's analysis/data-formats.md
#LEV.ARK for the full writeup, since they qualify UW1's own "RESOLVED" tag):

1. A naive fixed-stride or single-record-lookahead parse silently derails --
   even on UW1's own file, a coincidental false match one record deep produces
   a "valid-looking" record and every record after it is garbage. Full
   backtracking (try every record's trailing-skip choice, require the REST of
   the stream to also parse) is more correct but FAILS to find any solution at
   all for UW1's 135 records under any reasonable skip/id constraints --
   meaning the true format has at least one record shape this script doesn't
   model (a wider trailing field, or a non-offset use of start/end for some
   record type). Documented, not solved.
2. So this script uses a pragmatic middle ground: greedy with a 1-step
   lookahead, and on outright failure, RESYNC by scanning forward for the next
   position where two consecutive records validate. This reached 320/320 for
   UW2 with only 6 small resyncs -- good enough to characterize the format,
   NOT a byte-verified parse. Treat record boundaries beyond the first
   several as best-effort; cross-check anything load-bearing by hand.

Usage: python work/lev_audit.py <LEV.ARK> [...]
"""
import struct
import sys

MAX_ID = 0x20         # every id seen in either file so far is <= 7
RESYNC_WINDOW = 4000   # bytes to search forward when resyncing


def hexdump(data, base=0, length=None):
    if length is None:
        length = len(data)
    out = []
    for off in range(0, length, 16):
        chunk = data[off:off + 16]
        hexs = " ".join("%02x" % b for b in chunk)
        txt = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append("%08X  %-47s  |%s|" % (base + off, hexs, txt))
    return "\n".join(out)


def parse(data, count, fsize):
    def valid(off):
        if off + 10 > fsize:
            return None
        id_, start, end = struct.unpack_from("<HII", data, off)
        if id_ <= MAX_ID and start <= end <= fsize:
            return (id_, start, end)
        return None

    recs, resyncs = [], []
    off, n = 4, 0
    while n < count and off < fsize:
        v = valid(off)
        if v is None:
            found = None
            for cand in range(off, min(off + RESYNC_WINDOW, fsize - 10), 2):
                if valid(cand) and valid(cand + 12):
                    found = cand
                    break
            if found is None:
                print("  !! resync failed from off 0x%X after record %d" % (off, n))
                break
            resyncs.append((off, found))
            off = found
            v = valid(off)
        id_, start, end = v
        chosen = 2
        for skip in (2, 0, 4, 6, 8):
            if valid(off + 10 + skip) or n == count - 1:
                chosen = skip
                break
        trailing = data[off + 10:off + 10 + chosen]
        recs.append({"i": n, "off": off, "id": id_, "start": start, "end": end,
                     "size": end - start, "trailing": trailing})
        off += 10 + chosen
        n += 1
    return recs, off, resyncs


def audit(path):
    with open(path, "rb") as fh:
        data = fh.read()
    fsize = len(data)
    print("=" * 78)
    print("FILE  %s" % path)
    print("SIZE  %d bytes (0x%X)" % (fsize, fsize))
    print("=" * 78)

    count, field2 = struct.unpack_from("<HH", data, 0)
    print("header: count=%d (0x%X)  field2=%d (0x%X)" % (count, count, field2, field2))
    print(hexdump(data[0:16], 0))
    print()

    recs, stream_end, resyncs = parse(data, count, fsize)
    print("parsed %d/%d records; stream 0x4..0x%X; %d resyncs" %
          (len(recs), count, stream_end, len(resyncs)))
    for s, f in resyncs:
        print("  resync: off 0x%X -> 0x%X (skipped %d B)" % (s, f, f - s))
    print()

    ids = {}
    for r in recs:
        ids[r["id"]] = ids.get(r["id"], 0) + 1
    print("id histogram:", ids, " (sums to %d)" % sum(ids.values()))
    print()

    sizes = sorted({r["size"] for r in recs})
    print("distinct sizes (%d): %s" % (len(sizes), sizes))
    print()

    print("first 10 records:")
    for r in recs[:10]:
        print("  [%3d] off=0x%X id=%d start=0x%X end=0x%X size=0x%X trailing=%s"
              % (r["i"], r["off"], r["id"], r["start"], r["end"], r["size"],
                 r["trailing"].hex()))
    print()

    # coverage / gap analysis (data pool spans vs file)
    spans = sorted([(r["start"], r["end"]) for r in recs if r["end"] > r["start"]])
    cursor = stream_end
    gaps = []
    for s, e in spans:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < fsize:
        gaps.append((cursor, fsize))
    print("last covered end 0x%X ; filesize 0x%X ; %d gap(s), %d total gap bytes"
          % (cursor, fsize, len(gaps), sum(e - s for s, e in gaps)))
    for g in gaps[:10]:
        print("  gap 0x%X..0x%X (%d B): %s" % (g[0], g[1], g[1] - g[0],
              hexdump(data[g[0]:min(g[0] + 32, g[1])], g[0])))
    print()

    # size==0x7C08 (UW1's 63x63x8B grid) sanity check
    grids = [r for r in recs if r["size"] == 0x7C08]
    print("records with UW1's grid size (0x7C08): %d" % len(grids))
    print()


if __name__ == "__main__":
    for p in sys.argv[1:]:
        audit(p)
