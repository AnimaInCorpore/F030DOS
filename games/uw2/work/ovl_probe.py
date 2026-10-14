#!/usr/bin/env python3
"""Probe Borland's INT 3Fh overlay manager on the running oracle.

`ghidra.md` §14 established the wall: overlay code has no fixed linear address,
so ~210 KB of this binary cannot be breakpointed or mapped statically. The only
way through is the overlay manager's *runtime* state.

Entry point: the `INT 3Fh` vector. Every overlaid call goes through a 5-byte
stub `CD 3F <3 bytes>` in the resident image, so breaking on the handler and
reading the return address off the stack identifies **which stub** fired — and
the stub's address is an image address, which converts to a file offset
normally. That gives one (stub -> overlay) observation per hit.

Usage:  python work/ovl_probe.py [--wait 40] [--hits 6]
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdbstub_probe as P                                      # noqa: E402
from rsp_break import Rsp, QMP_PORT, RSP_PORT                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wait', type=int, default=40)
    ap.add_argument('--hits', type=int, default=6)
    ap.add_argument('--timeout', type=int, default=60)
    a = ap.parse_args()

    qmp = P.Qmp(QMP_PORT)

    def xp(addr, n):
        t = qmp.hmp(f'xp /{n}xb 0x{addr:x}')
        v = [x[2:] if x.startswith('0x') else x for x in t.split()]
        v = [x for x in v if len(x) == 2 and all(c in '0123456789abcdef' for c in x)]
        return bytes.fromhex(''.join(v[:n]))

    exe = open(P.default_exe(), 'rb').read()
    image_end = ((struct.unpack_from('<H', exe, 0x04)[0] - 1) * 512
                 + struct.unpack_from('<H', exe, 0x02)[0])

    ivt = xp(0x3F * 4, 4)
    off, seg = struct.unpack('<HH', ivt)
    handler = (seg << 4) + off
    print(f'INT 3Fh vector = {seg:04x}:{off:04x} -> linear {handler:#07x}')

    # calibrate delta so image addresses can be named
    sigs = P.pick_signatures(exe, P.find_overlay_pool(exe))
    found, carry = {}, b''
    for base in range(0, 0xA0000, 0x4000):
        blk = xp(base, 0x4000)
        if len(blk) != 0x4000:
            continue
        blob = carry + blk
        for label, o in sigs:
            if label not in found:
                i = blob.find(exe[o:o + 16])
                if i >= 0:
                    found[label] = (base - len(carry) + i) - o
        carry = blk[-15:]
        if len(found) == len(sigs):
            break
    import collections
    delta = collections.Counter(found.values()).most_common(1)[0][0]
    print(f'delta {delta:#07x}; handler is '
          f'{"INSIDE the image" if 0 <= handler - delta < image_end else "outside the image"}'
          f' (file {handler - delta:#07x})')

    print(qmp.hmp(f'gdbserver tcp::{RSP_PORT}').strip())
    rsp = Rsp(RSP_PORT)
    print('Z0 ->', rsp.set_break(handler))
    for k in range(a.hits):
        rsp.cont_nowait()
        try:
            rsp.wait_stop(a.timeout)
        except Exception as e:
            print(f'  hit {k}: none within {a.timeout}s ({type(e).__name__})')
            break
        regs = P.parse_regs(qmp.hmp('info registers'))
        ss, sp = regs.get('SS', 0), regs.get('ESP', 0) & 0xFFFF
        frame = xp((ss << 4) + sp, 6)
        rip, rcs, flags = struct.unpack('<HHH', frame)
        stub = (rcs << 4) + rip
        f = stub - delta
        tag = f'file {f:#07x}' if 0 <= f < image_end else 'NOT an image address'
        pre = xp(stub - 5, 5)
        print(f'  hit {k}: returns to {rcs:04x}:{rip:04x} -> {tag}; '
              f'stub bytes {pre.hex(" ")}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
