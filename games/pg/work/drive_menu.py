#!/usr/bin/env python3
"""Drive the unmodified DOS menu via QEMU PS/2 input, retaining checkpoints.

N/A - host oracle harness. Commands are JSON objects on stdin; --script replays
a saved list with absolute `at` times. `-snapshot` preserves the source disk.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import select
import subprocess
import sys
import time

import run_qemu
from probe_tail_write import Rsp, rsp_registers, parse_segment_dump
from probe_timer_runtime import locate_timer_wait
from probe_file_io import FileIoProbe
from probe_geometry_contracts import GeometryProbe
from probe_draw_contracts import DrawProbe
from probe_writers import WriterProbe
from probe_loader_state import LoaderStateProbe
from probe_rng_contracts import RngProbe
from probe_shape_contracts import ShapeProbe
from probe_compose_contracts import ComposeProbe

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_script(script, seconds):
    """Reject invalid schedules before launching a guest."""
    events = script['events'] if isinstance(script, dict) else script
    previous = -1
    names = set()
    for event in events:
        when = event['at']
        if not math.isfinite(when) or not 0 <= when < seconds or when < previous:
            raise ValueError('event times must be finite, ordered and within --seconds')
        previous = when
        if event['kind'] not in ('key', 'move', 'button', 'capture', 'wait', 'quit'):
            raise ValueError('unknown event kind')
        if event['kind'] == 'capture':
            name = event['name']
            if not name.replace('-', '').replace('_', '').isalnum() or name in names:
                raise ValueError('checkpoint names must be safe and unique')
            names.add(name)
    return [dict(event) for event in events]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hdd', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--script', type=Path)
    ap.add_argument('--seconds', type=float, default=180)
    ap.add_argument('--trace', action='store_true')
    ap.add_argument('--open-files', action='store_true',
                    help='arm the checked file-open wrapper at the main_menu checkpoint')
    ap.add_argument('--file-io', action='store_true',
                    help='also capture matched open returns, reads, seeks and closes')
    ap.add_argument('--geometry-contracts', action='store_true')
    ap.add_argument('--draw-contracts', action='store_true')
    ap.add_argument('--shape-contracts', nargs='?', const='start',
                    help='capture entry/exit witnesses of the shape draws sub_00058AB4/sub_00058F9E, '
                         'from the start or from the named route checkpoint')
    ap.add_argument('--writers', nargs='?', const='back', choices=('back', 'map'),
                    help='write-watch sample pixels of the back buffer or the map-view bitmap')
    ap.add_argument('--compose-contracts', nargs='?', const='start',
                    help='capture entry/exit witnesses of the static-frame compositor sub_00014BF6 '
                         '(not together with --shape-contracts), optionally from a route checkpoint')
    ap.add_argument('--loader-state', action='store_true')
    ap.add_argument('--rng-contracts', action='store_true')
    args = ap.parse_args()
    args.open_files = args.open_files or args.file_io or args.geometry_contracts or args.draw_contracts or args.writers or args.loader_state or args.rng_contracts or args.shape_contracts or args.compose_contracts
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    hdd = args.hdd.resolve()
    cyls, heads, secs, _ = run_qemu.geometry(str(hdd))
    port = run_qemu.free_port()
    gdb_port = run_qemu.free_port()
    command = [run_qemu.QEMU, '-M', 'pc', '-cpu', '486', '-m', '16',
               '-drive', f'file={hdd},format=raw,if=none,id=hd0',
               '-device', f'ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={cyls},heads={heads},secs={secs}',
               '-snapshot', '-boot', 'c', '-display', 'none', '-vga', 'std', '-no-reboot',
               '-qmp', f'tcp:127.0.0.1:{port},server=on,wait=off']
    if args.open_files:
        command += ['-gdb', f'tcp:127.0.0.1:{gdb_port}']
    if args.trace:
        plugin = ROOT.parent / 'F030Method/dos/trace/x86trace.so'
        command += ['-accel', 'tcg', '-plugin',
                    f'{plugin},lo=0,hi=0x400000,out={out}/exec.trace,int21log={out}/int21.log,int21callers={out}/int21.callers',
                    '-d', 'plugin']
    record = {'command': command, 'hdd_sha256': digest(hdd),
              'exe_sha256': digest(ROOT / 'game/EXE/PANZER.EXE'),
              'tool_sha256': digest(__file__), 'events': [], 'checkpoints': [], 'file_opens': []}
    if record['exe_sha256'] != '115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86':
        raise ValueError('this route requires the recorded unpatched PANZER.EXE')
    record['qemu_sha256'] = digest(run_qemu.QEMU)
    if args.file_io:
        record['file_io_probe_sha256'] = digest(ROOT / 'work/probe_file_io.py')
    if args.geometry_contracts:
        record['geometry_probe_sha256'] = digest(ROOT / 'work/probe_geometry_contracts.py')
    if args.draw_contracts:
        record['draw_probe_sha256'] = digest(ROOT / 'work/probe_draw_contracts.py')
    if args.writers:
        record['writers_probe_sha256'] = digest(ROOT / 'work/probe_writers.py')
    if args.shape_contracts and args.compose_contracts:
        raise SystemExit('--shape-contracts and --compose-contracts both use the shape primitive breakpoint')
    if args.compose_contracts:
        record['compose_probe_sha256'] = digest(ROOT / 'work/probe_compose_contracts.py')
    if args.shape_contracts:
        record['shape_probe_sha256'] = digest(ROOT / 'work/probe_shape_contracts.py')
    if args.loader_state:
        record['loader_state_probe_sha256'] = digest(ROOT / 'work/probe_loader_state.py')
    if args.rng_contracts:
        record['rng_probe_sha256'] = digest(ROOT / 'work/probe_rng_contracts.py')
    if args.trace:
        record['plugin_sha256'] = digest(plugin)
    source_script = json.loads(args.script.read_text()) if args.script else None
    script = validate_script(source_script, args.seconds) if source_script is not None else None
    record['script_sha256'] = digest(args.script) if args.script else None
    record['status'] = 'Unproven'
    record['problems'] = []
    with (out / 'qemu.log').open('w') as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        qmp = None
        rsp = None
        open_entry = None
        io_probe = None
        geometry_probe = None
        loader_probe = None
        rng_probe = None
        draw_probe = None
        writer_probe = None
        shape_probe = None
        compose_probe = None
        try:
            qmp = run_qemu.Qmp(port)
            if args.open_files:
                rsp = Rsp(gdb_port)
                rsp.command('qSupported:multiprocess+;xmlRegisters=i386')
                rsp.command('?')
                qmp.hmp('cont')
            started = time.monotonic()

            def read_memory(address, count):
                reply = rsp.command(f'm{address:x},{count:x}')
                if reply.startswith('E'):
                    raise RuntimeError(f'GDB memory read failed at {address:#x}: {reply}')
                return bytes.fromhex(reply)

            def wait_until(deadline):
                while time.monotonic() < deadline:
                    status = (qmp._cmd({'execute': 'query-status'})
                              if rsp and open_entry else None)
                    if status and not status.get('return', {}).get('running', True):
                        regs = rsp_registers(rsp.command('g'))
                        probes = [p for p in (io_probe, geometry_probe, loader_probe, rng_probe, draw_probe, writer_probe, shape_probe, compose_probe) if p]
                        if (writer_probe and regs['EIP'] != open_entry and
                                not any(regs['EIP'] in p.points for p in probes) and writer_probe.owns_stop()):
                            writer_probe.hit_watch(regs, round(time.monotonic() - started, 3))
                            qmp.hmp('cont')
                            continue
                        if regs['EIP'] != open_entry and not any(regs['EIP'] in p.points for p in probes):
                            raise RuntimeError(f'unexpected file probe stop: {status}, {regs}')
                        segments = parse_segment_dump(qmp.hmp('info registers'))
                        if any(segments.get(segment, (None, None))[1] != 0
                               for segment in ('CS', 'DS', 'SS', 'ES')):
                            raise RuntimeError('file-I/O breakpoint has non-flat segments')
                        at = round(time.monotonic() - started, 3)
                        if regs['EIP'] == open_entry:
                            stack = read_memory(regs['ESP'], 8)
                            caller = int.from_bytes(stack[:4], 'little')
                            pointer = int.from_bytes(stack[4:], 'little')
                            raw_path = read_memory(pointer, 260)
                            if b'\0' not in raw_path:
                                raise RuntimeError('file-open path is not terminated within 260 bytes')
                            path = raw_path.split(b'\0', 1)[0].decode('cp437')
                            event = {'at': at, 'entry': open_entry, 'caller': caller, 'path': path}
                            record['file_opens'].append(event)
                            if io_probe:
                                io_probe.on_open(event, regs)
                        else:
                            next(p for p in probes if regs['EIP'] in p.points).hit(regs, at)
                        eip = regs['EIP']
                        active = eip == open_entry or any(eip in p.points for p in probes)
                        if active and rsp.command(f'z0,{eip:x},1') != 'OK':
                            raise RuntimeError('could not remove file breakpoint')
                        rsp.command('s')
                        if active and rsp.command(f'Z0,{eip:x},1') != 'OK':
                            raise RuntimeError('could not restore file breakpoint')
                        qmp.hmp('cont')
                    time.sleep(min(0.01, max(0, deadline - time.monotonic())))
            print('READY: key/move/button/capture/wait/quit JSON commands', flush=True)
            while proc.poll() is None and time.monotonic() - started < args.seconds:
                if script is not None:
                    if not script:
                        break
                    event = dict(script.pop(0))
                    delay = event.get('at', 0) - (time.monotonic() - started)
                    if delay > 0:
                        wait_until(min(started + args.seconds, time.monotonic() + delay))
                    elif writer_probe:
                        wait_until(time.monotonic() + 0.05)   # service pending watchpoint stops
                else:
                    remaining = args.seconds - (time.monotonic() - started)
                    if not select.select([sys.stdin], [], [], max(0, remaining))[0]:
                        break
                    line = sys.stdin.readline()
                    if not line:
                        break
                    event = json.loads(line)
                event['at'] = round(time.monotonic() - started, 3)
                record['events'].append(event)
                kind = event['kind']
                if kind == 'key':
                    reply = qmp.hmp('sendkey ' + event['key'])
                elif kind in ('move', 'button'):
                    inputs = ([{'type': 'rel', 'data': {'axis': axis, 'value': event[axis]}}
                               for axis in ('x', 'y')] if kind == 'move' else
                              [{'type': 'btn', 'data': {'button': event.get('button', 'left'),
                                                      'down': event['down']}}])
                    reply = qmp._cmd({'execute': 'input-send-event', 'arguments': {'events': inputs}})
                    for _ in range(400):  # a probe stop may land just before the input; service it and retry
                        if not (writer_probe and reply and 'VM not running' in str(reply)):
                            break
                        wait_until(time.monotonic() + 0.0005)
                        reply = qmp._cmd({'execute': 'input-send-event', 'arguments': {'events': inputs}})
                    if not reply or 'error' in reply:
                        raise RuntimeError(f'input rejected: {reply}')
                elif kind == 'capture':
                    name = event['name']
                    if not name.replace('-', '').replace('_', '').isalnum():
                        raise ValueError('checkpoint name must be alphanumeric, hyphens or underscores')
                    qmp.hmp('stop')
                    try:
                        if rsp and name == 'main_menu':
                            # A wall-time stop can catch the extender's IRQ
                            # handler with temporary segment registers. Observe
                            # normal execution again; never rewrite the context.
                            for attempt in range(51):
                                context = qmp.hmp('info registers')
                                segments = parse_segment_dump(context)
                                if all(segments.get(s, (None, None))[1] == 0
                                       for s in ('DS', 'SS', 'ES')):
                                    event['context_retries'] = attempt
                                    break
                                if attempt == 50:
                                    raise RuntimeError('main menu never reached flat data context')
                                qmp.hmp('cont')
                                time.sleep(0.01)
                                qmp.hmp('stop')
                        shot = out / (name + '.ppm')
                        ram = out / (name + '.ram')
                        qmp.hmp(f'screendump "{shot.as_posix()}"')
                        registers = qmp.hmp('info registers')
                        (out / (name + '.registers.txt')).write_text(registers)
                        qmp.hmp(f'pmemsave 0 0x1000000 "{ram.as_posix()}"')
                        vram = out / (name + '.vram')   # 640x480 8-bit linear framebuffer (VGA BAR0)
                        qmp.hmp(f'pmemsave 0xfd000000 0x4b000 "{vram.as_posix()}"')
                        record['checkpoints'].append({'name': name, 'at': event['at'],
                                                      'screen_sha256': digest(shot),
                                                      'ram_sha256': digest(ram),
                                                      'vram_sha256': digest(vram)})
                        if writer_probe and name == writer_probe.activate_at:
                            writer_probe.activate()   # watch only the tactical screen's drawing
                        if shape_probe and name == shape_probe.activate_at:
                            shape_probe.activate()
                        if compose_probe and name == compose_probe.activate_at:
                            compose_probe.activate()
                        if rsp and name == 'main_menu':
                            segments = parse_segment_dump(registers)
                            cr0 = re.search(r'\bCR0=([0-9a-fA-F]+)', registers)
                            if (not cr0 or int(cr0[1], 16) & 0x80000000 or
                                    any(segments.get(segment, (None, None))[1] != 0
                                        for segment in ('DS', 'SS', 'ES'))):
                                raise RuntimeError('file probe requires flat segments and paging off')
                            exe = (ROOT / 'game/EXE/PANZER.EXE').read_bytes()
                            delta, _ = locate_timer_wait(qmp, exe)
                            open_entry = 0xB026C + delta
                            if read_memory(open_entry, 8) != exe[0xB026C:0xB0274]:
                                raise RuntimeError('file-open entry does not match selected build')
                            if rsp.command(f'Z0,{open_entry:x},1') != 'OK':
                                raise RuntimeError('could not arm file-open breakpoint')
                            if args.file_io:
                                io_probe = FileIoProbe(rsp, read_memory, out, record)
                                io_probe.arm(exe, delta)
                            if args.geometry_contracts:
                                geometry_probe = GeometryProbe(rsp, qmp, read_memory, record)
                                geometry_probe.arm(exe, delta)
                            if args.draw_contracts:
                                draw_probe = DrawProbe(rsp, qmp, read_memory, record)
                                draw_probe.arm(exe, delta)
                            if args.writers:
                                writer_probe = WriterProbe(rsp, qmp, read_memory, record, args.writers)
                                writer_probe.arm(exe, delta)
                            if args.compose_contracts:
                                compose_probe = ComposeProbe(rsp, qmp, read_memory, record, out,
                                                             None if args.compose_contracts == 'start' else args.compose_contracts)
                                compose_probe.arm(exe, delta)
                            if args.shape_contracts:
                                shape_probe = ShapeProbe(rsp, qmp, read_memory, record, out,
                                                         None if args.shape_contracts == 'start' else args.shape_contracts)
                                shape_probe.arm(exe, delta)
                            if args.loader_state:
                                loader_probe = LoaderStateProbe(rsp, read_memory, out, record)
                                loader_probe.arm(exe, delta)
                            if args.rng_contracts:
                                rng_probe = RngProbe(rsp, qmp, read_memory, record)
                                rng_probe.arm(exe, delta)
                    finally:
                        qmp.hmp('cont')
                    reply = str(shot)
                elif kind == 'wait':
                    wait_until(min(started + args.seconds, time.monotonic() + event['seconds']))
                    reply = 'waited'
                elif kind == 'quit':
                    break
                else:
                    raise ValueError(f'unknown command: {kind}')
                print(f"{event['at']:7.3f} {kind}: {reply}", flush=True)
            if script:
                record['problems'].append('deadline or guest exit before all scripted events')
            if io_probe:
                io_probe.finish()
            if geometry_probe:
                geometry_probe.finish()
            if loader_probe:
                loader_probe.finish()
            if rng_probe:
                rng_probe.finish()
            if draw_probe:
                draw_probe.finish()
            if writer_probe:
                writer_probe.finish()
            if shape_probe:
                shape_probe.finish()
            if compose_probe:
                compose_probe.finish()
            expected = source_script.get('expected_file_opens') if isinstance(source_script, dict) else None
            if expected is not None and [item['path'] for item in record['file_opens']] != expected:
                record['problems'].append('file-open sequence differs from the captured route')
            record['status'] = 'CAPTURED' if not record['problems'] else 'Unproven'
        except Exception as error:
            record['problems'].append(str(error))
            raise
        finally:
            if qmp:
                qmp.hmp('quit')
                qmp.close()
            if rsp:
                rsp.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            record['qemu_returncode'] = proc.returncode
            record['hdd_unchanged'] = digest(hdd) == record['hdd_sha256']
            if proc.returncode != 0 or not record['hdd_unchanged']:
                record['status'] = 'Unproven'
                record['problems'].append('emulator exit failure or changed source disk')
            if args.trace:
                record['dos_call_log_truncated'] = 'LOG FULL' in (out / 'qemu.log').read_text()
                trace = out / 'exec.trace'
                if not trace.is_file() or trace.stat().st_size != 0x400000:
                    record['status'] = 'Unproven'
                    record['problems'].append('execution sidecar missing or incomplete')
            (out / 'route.json').write_text(json.dumps(record, indent=2) + '\n')
    return 0 if record['status'] == 'CAPTURED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
