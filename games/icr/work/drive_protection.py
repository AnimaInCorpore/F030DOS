#!/usr/bin/env python3
r"""Drive the DOS oracle through the copy-protection gate and keep going.

The gate is a manual lookup with a randomly selected challenge, so it cannot
be answered by a fixed `run_qemu.py --key` script: the page/line pair differs
every run.  This driver reads the challenge the game itself selected out of
guest memory, answers it from the tables recovered in
`tools/re/protection.py`, and confirms acceptance from the game's own flag
rather than from the picture.

Nothing is patched.  The executable is the recorded authority build, the
challenge is the one the game chose, and the answer is checked by the game's
own comparison at 0x1BF38C.

    python work/drive_protection.py                 # answer, then run on
    python work/drive_protection.py --shot 3 --key 6:ret --shot 14

`--shot` and `--key` are scheduled in seconds **after acceptance**, not after
boot: the attract sequence's length varies from run to run, so a schedule
anchored at boot drifts against the state it means to drive.

Addresses (all linear = physical; the guest is 32-bit flat, see
analysis/executable.md):

    0x212D28  formatted prompt text, the sprintf destination at 0x1BF64F
    0x1EBDAC  the typed answer buffer
    0x1EBDA8  challenge index, stored at 0x1BF62C
    0x1EBD90  answered flag, set by the answer callback 0x1BF350
    0x1EBD94  accepted flag, 1 only when the hash matched
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools', 're'))
import dosimg                                                   # noqa: E402
import gdbstub_probe as probe                                   # noqa: E402
import protection                                               # noqa: E402

PROMPT_BUF = 0x212D28
ANSWER_BUF = 0x1EBDAC
IDX_ADDR = 0x1EBDA8
ANSWERED = 0x1EBD90
ACCEPTED = 0x1EBD94

ROOT = dosimg.find_project_root(__file__)
OUTDIR = os.path.join(ROOT, 'work', 'qemu_out')


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--hdd', default=os.path.join(ROOT, 'img', 'icr.hdd'))
    ap.add_argument('--first-poll', type=float, default=60.0,
                    help='seconds before looking for the prompt')
    ap.add_argument('--deadline', type=float, default=240.0)
    ap.add_argument('--shot', type=float, action='append', default=[],
                    help='extra screenshot N seconds after acceptance')
    ap.add_argument('--sample', type=int, default=0, metavar='N',
                    help='after the last event, take N EIP samples 0.2 s '
                         'apart and report them as file offsets')
    ap.add_argument('--stack', type=int, default=0, metavar='BYTES',
                    help='with --sample, also read BYTES at ESP each time and '
                         'histogram the dwords that fall inside the loaded '
                         'image -- return-address candidates for the call '
                         'chain above the hot code')
    ap.add_argument('--dump-ram', action='store_true',
                    help='pmemsave all of guest RAM after the last event and '
                         'measure the file->linear mapping from it, instead '
                         'of assuming the deltas recorded in analysis/')
    ap.add_argument('--key', action='append', default=[], metavar='SEC:KEY',
                    help='QMP sendkey SEC seconds after acceptance, e.g. '
                         '20:down or 24:ret. Repeatable. A screenshot is '
                         'taken after each key.')
    args = ap.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    # Capture tags carry the event index, its time and its key, so they differ
    # between runs instead of overwriting -- which means last run's pictures
    # would otherwise sit beside this run's and read as evidence from it.
    # Clear the whole set up front; probe.stale() only covers a repeated tag.
    import glob
    for old in glob.glob(os.path.join(OUTDIR, 'drive_*.ppm')) + \
            glob.glob(os.path.join(OUTDIR, 'drive_*.png')):
        os.remove(old)
    cyls, heads, secs, _ = probe.geometry(args.hdd)
    port = probe.free_port()
    cmd = [probe.QEMU, '-M', 'pc', '-cpu', '486', '-m', str(probe.MEM_MB),
           '-drive', f'file={args.hdd},format=raw,if=none,id=hd0,'
                     f'cache=writeback',
           '-device', f'ide-hd,drive=hd0,bus=ide.0,unit=0,'
                      f'cyls={cyls},heads={heads},secs={secs}',
           '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
           '-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04',
           '-qmp', f'tcp:127.0.0.1:{port},server=on,wait=off']
    log = open(os.path.join(OUTDIR, 'drive_qemu_stdout.log'), 'wb')
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)

    qmp = None
    t0 = time.time()
    while time.time() - t0 < 30 and qmp is None:
        try:
            qmp = probe.Qmp(port)
        except OSError:
            time.sleep(0.5)
    if qmp is None:
        proc.kill()
        sys.exit('QMP never came up')

    def xp(addr, n):
        t = qmp.hmp(f'xp /{n}xb 0x{addr:x}')
        vals = [tok[2:] if tok.startswith('0x') else tok for tok in t.split()]
        vals = [v for v in vals
                if len(v) == 2 and all(c in '0123456789abcdef' for c in v)]
        try:
            return bytes.fromhex(''.join(vals[:n]))
        except ValueError:
            return b''

    def dword(addr):
        b = xp(addr, 4)
        return int.from_bytes(b, 'little') if len(b) == 4 else None

    def shot(tag):
        ppm = os.path.join(OUTDIR, f'drive_{tag}.ppm')
        png = os.path.join(OUTDIR, f'drive_{tag}.png')
        probe.stale(ppm, png)
        qmp._cmd({'execute': 'screendump', 'arguments': {'filename': ppm}})
        for _ in range(30):
            if os.path.exists(ppm) and os.path.getsize(ppm):
                break
            time.sleep(0.2)
        try:
            subprocess.run([dosimg.host_tool('ffmpeg'), '-y', '-loglevel',
                            'error', '-i', ppm, png], capture_output=True)
        except (OSError, SystemExit):
            pass
        print(f'  screenshot: {png if os.path.exists(png) else ppm}')

    time.sleep(args.first_poll)
    print(f'--- polling for the prompt from t={args.first_poll:.0f}s ---')
    idx = None
    while time.time() - t0 < args.deadline:
        buf = xp(PROMPT_BUF, 32)
        if buf.startswith(b'Page '):
            text = buf.split(b'\0')[0].decode('latin-1')
            idx = dword(IDX_ADDR)
            print(f'--- prompt at t={time.time() - t0:.0f}s: {text!r}, '
                  f'challenge index {idx} ---')
            break
        time.sleep(2.0)
    if idx is None:
        proc.kill()
        sys.exit('the prompt never appeared -- raise --deadline')

    data = protection.read_exe()
    i, page, line, h = protection.tables(data)[idx]
    answer = protection.answer_for_index(idx, data)
    print(f'  table says index {i} is page {page}, line {line}, '
          f'hash {h:#010x}')
    if f'Page {page}, line {line}' not in text:
        proc.kill()
        sys.exit(f'the table disagrees with the screen text {text!r} -- stop '
                 f'and re-measure the data delta before trusting anything')
    print(f'  answering "{answer}"')
    shot('prompt')

    for ch in answer:
        qmp.hmp(f'sendkey {ch}')
        time.sleep(0.4)
    typed = xp(ANSWER_BUF, 8).split(b'\0')[0].decode('latin-1', 'replace')
    print(f'  guest answer buffer now {typed!r}')
    qmp.hmp('sendkey ret')

    for _ in range(20):
        time.sleep(0.5)
        if dword(ANSWERED):
            break
    ok = dword(ACCEPTED)
    print(f'--- answered={dword(ANSWERED)} accepted={ok} '
          f'({"PASSED" if ok else "REJECTED"}) ---')
    shot('answered')

    # Everything after the gate is scheduled relative to acceptance, not to
    # boot: the attract sequence's length varies between runs, so a schedule
    # anchored at t0 drifts against the state it is meant to drive.
    t_ok = time.time()
    events = ([(w, None) for w in args.shot]
              + [(float(k.split(':', 1)[0]), k.split(':', 1)[1])
                 for k in args.key])
    for n, (when, key) in enumerate(sorted(events, key=lambda e: e[0]), 1):
        time.sleep(max(0.0, when - (time.time() - t_ok)))
        if qmp.dead:
            print('  guest exited')
            break
        if key:
            print(f'  +{when:.0f}s sendkey {key}')
            qmp.hmp(f'sendkey {key}')
            time.sleep(1.5)
            shot(f'{n:02d}_{int(when)}s_{key}')
        else:
            shot(f'{n:02d}_{int(when)}s')

    # ---- where is the code, in the state we just drove to? ---------------
    runs = None
    if args.dump_ram:
        ram_path = os.path.join(OUTDIR, 'ram_session.bin')
        probe.stale(ram_path)
        # Pair the dump with the picture of the same moment: correlating the
        # two is how the framebuffer is found, and a screenshot from any other
        # instant would correlate against the wrong frame.
        shot('ram')
        nbytes = probe.MEM_MB << 20
        qmp.hmp(f'pmemsave 0 {nbytes} "{ram_path}"')
        for _ in range(60):
            if os.path.exists(ram_path) and os.path.getsize(ram_path) >= nbytes:
                break
            time.sleep(0.5)
        if os.path.getsize(ram_path) >= nbytes:
            exe = open(protection.EXE, 'rb').read()
            runs, unmatched = probe.mapping_report(
                exe, open(ram_path, 'rb').read())
            print(f'--- mapping in this state ({unmatched} windows nowhere) ---')
            for d, lo, hi, n in runs[:8]:
                print(f'  delta {d:#010x}  file {lo:#08x}..{hi:#08x}  '
                      f'{n} windows -> linear {lo + d:#010x}..{hi + d:#010x}')

    if args.sample:
        import collections
        hist = collections.Counter()
        modes = collections.Counter()
        stack_hist = collections.Counter()
        for _ in range(args.sample):
            raw = qmp.hmp('info registers')
            rr = probe.parse_regs(raw)
            m = probe.cpu_mode(raw, rr)
            if 'CS' not in rr:
                continue
            segs_i = probe.parse_segs(raw)
            hist[probe.linear(m, rr, segs_i, 'CS', rr.get('EIP', 0))] += 1
            modes[m] += 1
            if args.stack and m == 'pm32':
                sp = probe.linear(m, rr, segs_i, 'SS', rr.get('ESP', 0))
                blob = xp(sp, args.stack)
                for k in range(0, len(blob) - 3, 4):
                    v = int.from_bytes(blob[k:k + 4], 'little')
                    if 0x18F2DC <= v <= 0x1F32DC:
                        stack_hist[v] += 1
            time.sleep(0.2)

        def to_file(lin):
            """Prefer a delta measured in this very run; fall back to the one
            recorded in analysis/executable.md, and say which was used."""
            if runs:
                for d, lo, hi, _ in runs:
                    if lo <= lin - d <= hi:
                        return lin - d, f'measured {d:#x}'
            f = lin - 0x13EEDC
            if 0x50400 <= f <= 0xB4400:
                return f, 'recorded 0x13eedc'
            return None, 'outside every known block'

        print(f'--- EIP samples in this state (n={sum(hist.values())}, '
              f'modes: {dict(modes)}) ---')
        # The top-N list alone cannot say how concentrated the code is: the
        # tail could be spread anywhere. Report the share that falls inside
        # the sampled span, so "the hot region is X" is a number and not an
        # impression formed from the first few rows.
        offs = [to_file(l)[0] for l in hist.elements()]
        inside = [o for o in offs if o is not None]
        if inside:
            lo, hi = min(inside), max(inside)
            print(f'  {len(inside)}/{len(offs)} samples resolve to a file '
                  f'offset, spanning {lo:#08x}..{hi:#08x} '
                  f'({(hi - lo) / 1024:.1f} KB)')
            # min..max is an outlier's range, not a concentration. Bin the
            # samples so the answer to "where does the time go" is a share of
            # the total rather than the first few rows of the top-N list.
            bins = collections.Counter(o & ~0xFFF for o in inside)
            cum = 0
            print('  by 4 KB file bin:')
            for b, n in bins.most_common(8):
                cum += n
                print(f'    {b:#08x}..{b + 0xFFF:#08x}  {n:3d} '
                      f'({100.0 * n / len(offs):4.1f}%)  '
                      f'cumulative {100.0 * cum / len(offs):5.1f}%')
        for lin, n in hist.most_common(25):
            f, how = to_file(lin)
            where = f'file {f:#08x}  ({how})' if f is not None else how
            print(f'  {n:3d}x  {lin:#010x}  {where}')

        if stack_hist:
            # Anything on the stack can look like a code address; only report
            # the ones preceded by a call. The E8 test is done offline against
            # the RAM dump, so print the candidates with their file offsets
            # and let the caller filter.
            print(f'--- stack dwords inside the image '
                  f'({len(stack_hist)} distinct) ---')
            for v, n in stack_hist.most_common(20):
                f, how = to_file(v)
                print(f'  {n:3d}x  {v:#010x}  '
                      + (f'file {f:#08x} ({how})' if f is not None else how))

    qmp.close()
    proc.kill()
    log.close()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
