#!/usr/bin/env python3
"""Count actual Falcon screen ticks, then stop at the first flight frame.

N/A - target harness. Build first with tools/build-run.sh (TARGET_CPU=68060
for the accelerator image). --even-pass changes only the initial pass counter
through the debugger to test the other authored opening without a full replay.
The 480 fanfare ticks test the existing silent-port policy; DOS can also leave
that screen on sound completion. Title/side loops are DOS 600/300 ticks.
"""
import argparse
import collections
import hashlib
import importlib
import json
from pathlib import Path
import re
import shutil

support = importlib.import_module('check-cpu-compatibility')
ROOT = support.ROOT


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cpu', type=int, choices=(68030, 68060), default=68030)
    ap.add_argument('--even-pass', action='store_true')
    ap.add_argument('--artifact-dir', type=Path,
                    help='copy the run evidence here, keeping it separate from the staged program')
    args = ap.parse_args()
    vbl_limit = 160000 if args.cpu == 68060 else 24000
    out = ROOT / ('release' if args.cpu == 68030 else 'release/68060')
    if not (out / 'comanche_d.tos').is_file():
        ap.error('Build the selected CPU image first')
    artifact = ((ROOT / args.artifact_dir).resolve() if args.artifact_dir else out)
    artifact.mkdir(parents=True, exist_ok=True)
    commands = ('b pc = attract_frame :trace :file timing-sample.ini\n'
                'b pc = demo_start :trace :once :file timing-seed.ini\n'
                'b pc = flight_tick :trace :once :file timing-axis.ini\n'
                'b pc = render_clear :trace :once :file timing-render.ini\n'
                'b pc = exc_report :once :file timing-failed.ini\n'
                f'b VBL = {vbl_limit-1} :once :file timing-failed.ini\n')
    if args.even_pass:
        commands += 'w attract_pass 0 1\n'
    support.entry_breakpoint(out, 'comanche_d.tos', commands)
    (out / 'timing-sample.ini').write_text('m b attract_active 10\n')
    (out / 'timing-seed.ini').write_text(
        'b pc = flight_reset :trace :once :file timing-header.ini\n')
    (out / 'timing-header.ini').write_text(
        'savebin timing-header.bin flt_x $c\n'
        'savebin timing-length.bin demo_length $4\n'
        'savebin timing-altitude.bin player_altitude $1\n')
    (out / 'timing-axis.ini').write_text('savebin timing-axis.bin flt_axis1 $4\n')
    (out / 'timing-render.ini').write_text(
        'b pc = publish_screen :once :file timing-done.ini\n')
    (out / 'timing-failed.ini').write_text('r\nd pc 8\nm exc_pc 4\nquit\n')
    (out / 'timing-done.ini').write_text(
        'savebin timing-final.bin attract_active $a\n'
        'savebin timing-fault.bin exc_vector $2\n'
        'savebin timing-view.bin view_angle $14\n'
        'savebin timing-vbr.bin vector_base $4\n'
        "savebin timing-frame.bin '(display_screen).l' $25800\nquit\n")
    evidence_names = ('timing-final.bin', 'timing-fault.bin', 'timing-view.bin', 'timing-vbr.bin', 'timing-frame.bin',
                      'timing-result.json', 'timing-header.bin', 'timing-length.bin', 'timing-altitude.bin',
                      'timing-axis.bin', 'timing-command.json', 'timing.log')
    for name in evidence_names:
        (out / name).unlink(missing_ok=True)
        if artifact != out:
            (artifact / name).unlink(missing_ok=True)
    command = support.emulator_command(out, args.cpu, 'comanche_d.tos', 'boot.ini')
    command[command.index('--run-vbls') + 1] = str(vbl_limit)
    (out / 'timing-command.json').write_text(json.dumps(command, indent=2) + '\n')
    support.run(command, out, out / 'timing.log', timeout=480)
    log = (out / 'timing.log').read_text(errors='replace')
    samples = []
    for match in re.finditer(r'> m b attract_active 10\n([^\n]+)', log):
        line = match[1]
        data = re.match(r'[0-9a-fA-F]+:\s+((?:[0-9a-fA-F]{2}\s+){9}[0-9a-fA-F]{2})', line)
        if not data:
            raise RuntimeError(f'Unrecognized debugger sample: {line}')
        raw = bytes.fromhex(data[1])
        samples.append(tuple(int.from_bytes(raw[i:i+2], 'big') for i in range(0, 10, 2)))
    expected = [(1, 1, 2, 2, t) for t in range(300, 0, -1)] if args.even_pass else (
        [(1, 2, 1, 1, t) for t in range(480, 0, -1)] +
        [(1, 3, 1, 1, t) for t in range(600, 0, -1)])
    screens = [row for row in samples if row[1] != 0]
    assert screens == expected, f'Screen countdown mismatch: {collections.Counter(r[1] for r in screens)}'
    assert (out / 'timing-final.bin').is_file(), f'Flight publication not reached; inspect {out / "timing.log"}'
    assert (out / 'timing-fault.bin').read_bytes() == b'\0\0', 'Target exception'
    final = (out / 'timing-final.bin').read_bytes()
    assert final[:4] == b'\0\1\0\0', 'Did not reach attract flight'
    frame = (out / 'timing-frame.bin').read_bytes()
    assert len(frame) == 320 * 240 * 2, 'Incomplete RGB565 capture'
    demo = (out / f'DEMO{2 if args.even_pass else 1}.SCR').read_bytes()
    header = b''.join(int.from_bytes(demo[i:i+4], 'little').to_bytes(4, 'big') for i in (4, 8, 12))
    assert (out / 'timing-header.bin').read_bytes() == header, 'Replay LE32 header decode'
    assert int.from_bytes((out / 'timing-length.bin').read_bytes(), 'big') == int.from_bytes(demo[:4], 'little'), 'Replay length decode'
    assert (out / 'timing-altitude.bin').read_bytes() == demo[16:17], 'Replay byte field changed'
    axes = b''.join(int.from_bytes(demo[i:i+2], 'little', signed=True).to_bytes(2, 'big', signed=True) for i in (21, 23))
    assert (out / 'timing-axis.bin').read_bytes() == axes, 'Replay signed LE16 axes decode'
    result = {'cpu': args.cpu, 'pass': 2 if args.even_pass else 1,
              'screen_ticks': dict(collections.Counter(row[1] for row in screens)),
              'status': 'PASS', 'checkpoint': 'publish_screen',
              'replay_byte_order': 'PASS',
              'frame_sha256': hashlib.sha256(frame).hexdigest(),
              'program_sha256': hashlib.sha256((out / 'comanche_d.tos').read_bytes()).hexdigest()}
    (out / 'timing-result.json').write_text(json.dumps(result, indent=2) + '\n')
    if artifact != out:
        for name in evidence_names:
            source = out / name
            if source.is_file():
                shutil.copy2(source, artifact / name)
    print(f'PASS MC{args.cpu}: {result["screen_ticks"]}; reached first flight render')


if __name__ == '__main__':
    main()
