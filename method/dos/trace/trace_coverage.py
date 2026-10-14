#!/usr/bin/env python3
"""Map an x86trace sidecar back onto an MZ load module and report coverage.

Guest linear addresses mean nothing until they are tied to the file. That tie
is the load base, and it is *measured*, not assumed: distinctive 16-byte
windows of the load module are hunted in a RAM dump of the same run and the
delta they agree on is the base. Windows that disagree are usually applied
relocations, which is why this votes rather than trusting the first hit --
the same method gdbstub_probe.py uses to calibrate the file->linear mapping.

    python trace/trace_coverage.py --exe START.EXE --trace por.trace \
        --ram por.ram --data-from 0x7400

--data-from marks a region that is known to be data (POR's DGROUP), so the
report can state coverage of the code region separately and check that nothing
executed inside the data region -- the ledger's known-data guard, applied to a
dynamic run instead of a static sweep.
"""
import argparse
import collections
import struct
import sys


def load_module(path):
    """(bytes, header_size) of the MZ load module -- header and any overlay
    tail excluded, so offsets match what a disassembler calls image offset."""
    d = open(path, 'rb').read()
    if d[:2] not in (b'MZ', b'ZM'):
        sys.exit('%s is not an MZ executable' % path)
    e_cblp, e_cp, _, e_cparhdr = struct.unpack_from('<4H', d, 2)
    hdr = e_cparhdr * 16
    end = e_cp * 512 - ((512 - e_cblp) if e_cblp else 0)
    return d[hdr:end], hdr


def distinctive(w):
    """Reject windows too bland to identify a location (runs of one byte)."""
    return len(set(w)) >= 6


def find_base(mod, ram, step=256, width=16, want=64):
    """Vote on load base = ram_offset - file_offset over many windows."""
    votes = collections.Counter()
    tried = 0
    for off in range(0, len(mod) - width, step):
        w = mod[off:off + width]
        if not distinctive(w):
            continue
        tried += 1
        pos, seen = ram.find(w), 0
        while pos != -1 and seen < 4:          # ignore wildly repeated windows
            votes[pos - off] += 1
            seen += 1
            pos = ram.find(w, pos + 1)
        if tried >= want and votes:
            break
    return votes, tried


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--trace', required=True)
    ap.add_argument('--ram', required=True)
    ap.add_argument('--lo', default='0', help='window start used for the run')
    ap.add_argument('--data-from', default=None,
                    help='image offset where a known-data region starts')
    ap.add_argument('--base', default=None,
                    help='skip calibration and use this linear base')
    a = ap.parse_args()

    mod, hdr = load_module(a.exe)
    flags = open(a.trace, 'rb').read()
    ram = open(a.ram, 'rb').read()
    lo = int(a.lo, 0)

    print('load module: %d bytes (MZ header %d)' % (len(mod), hdr))
    print('sidecar:     %d bytes' % len(flags))
    print('ram dump:    %d bytes' % len(ram))

    if a.base is not None:
        base, votes, tried = int(a.base, 0), None, 0
    else:
        votes, tried = find_base(mod, ram)
        if not votes:
            sys.exit('calibration failed: no window of the load module found in '
                     'RAM -- was the program still resident at dump time?')
        # find_base votes in RAM-dump offsets; the dump starts at linear `lo`
        # (run_trace.py pmemsaves the plugin window, not address 0), so add
        # `lo` to get the *linear* base.  --base is documented as linear, and
        # covered() below subtracts `lo` again for the sidecar index -- with
        # the old dump-relative value that subtraction happened twice and the
        # fold was correct only for --lo 0.
        (rel, n), = votes.most_common(1)
        base = rel + lo
        total = sum(votes.values())
        print('calibration: %d/%d windows agree on base 0x%X '
              '(linear; segment 0x%04X)' % (n, total, base, base >> 4))
        for d, c in votes.most_common(4)[1:]:
            print('             runner-up 0x%X (%d)' % (d + lo, c))
        if n * 2 <= total:
            print('WARNING: no majority -- treat the base as unproven')

    def covered(rng):
        c = 0
        for i in rng:
            idx = base + i - lo          # linear base -> sidecar index
            if 0 <= idx < len(flags) and flags[idx] & 1:
                c += 1
        return c

    split = int(a.data_from, 0) if a.data_from else len(mod)
    if a.data_from and not 0 < split < len(mod):
        sys.exit('--data-from 0x%X is outside the load module (0x1..0x%X). The '
                 'guard splits the module into code below it and known data '
                 'from it to EOF, so both halves must be non-empty.'
                 % (split, len(mod) - 1))
    code_n = covered(range(0, split))
    data_n = covered(range(split, len(mod)))
    total_n = code_n + data_n

    print()
    print('executed bytes of the load module: %d / %d = %.1f%%'
          % (total_n, len(mod), 100.0 * total_n / len(mod)))
    if a.data_from:
        print('  code region  0x0..0x%X:  %d / %d = %.1f%%'
              % (split, code_n, split, 100.0 * code_n / split))
        dlen = len(mod) - split
        print('  data region  0x%X..EOF:  %d / %d = %.1f%%   <-- known-data guard'
              % (split, data_n, dlen, 100.0 * data_n / dlen))
        if data_n:
            print('  NOTE: %d executed bytes inside the known-data region. Either '
                  'the region is not purely data, or the base is wrong.' % data_n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
