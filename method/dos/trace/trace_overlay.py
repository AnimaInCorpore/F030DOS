#!/usr/bin/env python3
"""Fold x86trace overlay flushes onto an overlay file's own offsets.

An overlay buffer holds different units at one linear address over time, so
address-keyed telemetry merges them. The plugin flushes each region's coverage
just before it is overwritten, together with samples of the bytes that were
sitting there. This locates those samples in the overlay file and ORs the
coverage onto file offsets, which is where a disassembler needs it.

Identification is by content because DOS bookkeeping is not trustworthy across
a run: handles are recycled (POR opens 117 files and closes 233 in one boot),
so a handle number does not name a file for long. Bytes do.

    python trace/trace_overlay.py --ovr GAME.OVR --flush por.ovl \
        [--ram por.ram] [--out game_ovr.coverage]

The final flush is written from QEMU's atexit callback, which cannot read
guest memory, so its samples are zero. Pass --ram to identify that last
resident set from the run's memory dump instead.
"""
import argparse
import struct
import sys

SAMPLES, SAMPLE_SZ = 4, 32
REC_HDR = struct.calcsize('<QQ')
REC_SAMPLE = struct.calcsize('<Q') + SAMPLE_SZ


def records(path):
    d = open(path, 'rb').read()
    i = 0
    while i + REC_HDR <= len(d):
        lo, ln = struct.unpack_from('<QQ', d, i)
        i += REC_HDR
        samples = []
        for _ in range(SAMPLES):
            if i + REC_SAMPLE > len(d):
                return
            rel, = struct.unpack_from('<Q', d, i)
            samples.append((rel, d[i + 8:i + 8 + SAMPLE_SZ]))
            i += REC_SAMPLE
        if i + ln > len(d):
            return
        yield lo, ln, samples, d[i:i + ln]
        i += ln


def locate(ovr, samples):
    """File offset this region came from, by voting across its samples."""
    votes = {}
    for rel, blob in samples:
        if len(set(blob)) < 6:          # too bland to identify anything
            continue
        p = ovr.find(blob)
        if p == -1 or ovr.find(blob, p + 1) != -1:
            continue                    # absent, or not unique
        votes[p - rel] = votes.get(p - rel, 0) + 1
    if not votes:
        return None, 0
    off, n = max(votes.items(), key=lambda kv: kv[1])
    return off, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ovr', required=True)
    ap.add_argument('--flush', required=True)
    ap.add_argument('--ram')
    ap.add_argument('--ram-lo', default='0',
                    help='guest linear address where --ram starts: the --lo '
                         'given to run_trace.py, whose memdump covers the '
                         'plugin window, not address 0')
    ap.add_argument('--out')
    a = ap.parse_args()

    ovr = open(a.ovr, 'rb').read()
    cov = bytearray(len(ovr))
    ram = open(a.ram, 'rb').read() if a.ram else None
    ram_lo = int(a.ram_lo, 0)

    n = ident = blank = unident = 0
    covered_flushes = 0
    for lo, ln, samples, fl in records(a.flush):
        n += 1
        if not any(b & 1 for b in fl):
            blank += 1                  # nothing executed there; nothing to place
            continue
        covered_flushes += 1
        off, votes = locate(ovr, samples)
        if off is None and ram is not None:
            # Final flush: samples are zero, so read what was resident from
            # the RAM dump instead and identify that.  `lo` here is a guest
            # linear address; the dump starts at linear `ram_lo`, so index
            # the dump at (lo - ram_lo), not at `lo`.
            start = lo - ram_lo
            if 0 <= start and start + ln <= len(ram):
                off, votes = locate(
                    ovr, [(r, ram[start + r:start + r + SAMPLE_SZ])
                          for r, _ in samples])
        if off is None:
            unident += 1
            continue
        ident += 1
        for i in range(ln):
            if fl[i] & 1 and 0 <= off + i < len(cov):
                cov[off + i] |= 1

    hit = sum(1 for b in cov if b & 1)
    print('flush records:            %d' % n)
    print('  nothing executed:       %d' % blank)
    print('  executed + identified:  %d' % ident)
    print('  executed + unplaced:    %d' % unident)
    if covered_flushes:
        print('  identification rate:    %.1f%%'
              % (100.0 * ident / covered_flushes))
    print()
    print('%s: %d / %d bytes executed = %.1f%%'
          % (a.ovr.split('/')[-1], hit, len(ovr), 100.0 * hit / len(ovr)))
    if a.out:
        open(a.out, 'wb').write(bytes(cov))
        print('wrote %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
