#!/usr/bin/env python3
"""Compare captured DOS ISR cases with production JavaScript and native code.

Target artefact. Run work/capture_shake_contract.py first. Tests the actual
src/shake.s on both Hatari CPUs, including the independent clock adapter.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    fixture = ROOT / 'build/shake-contract/dos.json'
    evidence = json.loads(fixture.read_text())
    assert evidence['image_sha256'] == hashlib.sha256(
        (ROOT / 're/unpacked/comanche-flat32.bin').read_bytes()).hexdigest()
    rows = evidence['rows']
    js = r'''
const fs = require('fs');
const assert = require('assert/strict');
require('./jsComanche/sine-q31.js');
require('./jsComanche/object-bearing.js');
require('./jsComanche/dos-damage.js');
require('./jsComanche/dos-runtime.js');
const api = globalThis.ComancheRuntime;
const fixture = JSON.parse(fs.readFileSync('build/shake-contract/dos.json'));
for (const row of fixture.rows) {
  const [rng, phase, countdown] = row.input;
  const state = {rng, phase, countdown};
  api.shakeTimerTick(state);
  assert.deepEqual([state.rng, state.phase, state.countdown], row.output);
}
const state = {rng: 0, phase: 0, countdown: 10, accumulator: 0};
api.advanceShake200Hz(state, 2000);
const direct = {rng: 0, phase: 0, countdown: 10};
for (let tick = 0; tick < Math.floor(2000 * 1193182 / (200 * 0x47b4)); ++tick)
  api.shakeTimerTick(direct);
assert.deepEqual([state.rng, state.phase, state.countdown], [direct.rng, direct.phase, direct.countdown]);
assert.equal(state.accumulator, (2000 * 1193182) % (200 * 0x47b4));
const split = {rng: 0, phase: 0, countdown: 10, accumulator: 0};
for (const ticks of [1, 2, 17, 800, 0, 1180]) api.advanceShake200Hz(split, ticks);
assert.deepEqual(split, state);
for (const roll of [-133, 0, 133]) for (const pitch of [-100, 0, 100]) {
  const base = api.buildBackdropDy(roll, pitch, 0);
  for (let phase = 1; phase <= 3; ++phase) {
    const shaken = api.buildBackdropDy(roll, pitch, phase);
    assert.deepEqual(Array.from(shaken), Array.from(base, x => x - phase));
  }
}
console.log(JSON.stringify(state));
'''
    clock = json.loads(subprocess.check_output(['node', '-e', js], cwd=ROOT))
    print(f'PASS JavaScript: {len(rows)} captured DOS cases; clock partition and horizon checks', flush=True)
    spec = importlib.util.spec_from_file_location('cpu_check', ROOT / 'tools/check-cpu-compatibility.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    expected = b''.join(value.to_bytes(4, 'big') for row in rows for value in row['output'])
    expected += b''.join(clock[key].to_bytes(4, 'big') for key in ('rng', 'phase', 'countdown', 'accumulator'))
    for cpu in (68030, 68060):
        out = ROOT / f'build/shake-contract/{cpu}'
        out.mkdir(parents=True, exist_ok=True)
        source = '''
        global _main, test_done, results
        global flight_shake_tick, flight_shake_clock
        global flt_shake_rng, flt_shake_phase, flt_shake_timer, shake_clock_accumulator
        text
_main
        lea inputs,a0
        lea results,a1
        move.w #COUNT-1,d7
.next
        move.l (a0)+,flt_shake_rng
        move.l (a0)+,flt_shake_phase
        move.l (a0)+,flt_shake_timer
        bsr flight_shake_tick
        move.l flt_shake_rng,(a1)+
        move.l flt_shake_phase,(a1)+
        move.l flt_shake_timer,(a1)+
        dbra d7,.next
        clr.l flt_shake_rng
        clr.l flt_shake_phase
        move.l #10,flt_shake_timer
        clr.l shake_clock_accumulator
        move.w #1999,d7
.clock
        bsr flight_shake_clock
        dbra d7,.clock
        move.l flt_shake_rng,(a1)+
        move.l flt_shake_phase,(a1)+
        move.l flt_shake_timer,(a1)+
        move.l shake_clock_accumulator,(a1)+
test_done
        clr.w -(sp)
        trap #1
        data
inputs
INPUTS
        bss
results
        ds.b RESULT_BYTES
        end
'''.replace('COUNT', str(len(rows))).replace('RESULT_BYTES', str(len(expected))).replace(
            'INPUTS', '\n'.join('        dc.l ' + ','.join(f'${v:08x}' for v in row['input']) for row in rows))
        (out / 'test.s').write_text(source)
        vasm = os.environ.get('VASM', str(helper.TOOLS / 'vasmm68k_mot_mac'))
        vlink = os.environ.get('VLINK', str(helper.TOOLS / 'vlink_mac'))
        for name, path in [('test', out / 'test.s'), ('shake', ROOT / 'src/shake.s')]:
            helper.run([vasm, str(path), '-quiet', '-Felf', f'-m{cpu}',
                        '-o', str(out / f'{name}.o')], ROOT, out / f'{name}.log')
        helper.run([vlink, '-b', 'ataritos', '-e', '_main', '-o', str(out / 'check.tos'),
                    str(out / 'test.o'), str(out / 'shake.o')], ROOT, out / 'link.log')
        helper.entry_breakpoint(out, 'check.tos', 'b pc = test_done :once :file done.ini\n')
        (out / 'done.ini').write_text(f'savebin results.bin results ${len(expected):x}\nquit\n')
        (out / 'results.bin').unlink(missing_ok=True)
        helper.run(helper.emulator_command(out, cpu, 'check.tos', 'boot.ini'), out, out / 'hatari.log')
        actual = (out / 'results.bin').read_bytes()
        assert actual == expected, f'MC{cpu} shake contract mismatch'
        result = {'status': 'PASS', 'cpu': cpu, 'dos_cases': len(rows), 'host_ticks': 2000,
                  'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest(),
                  'program_sha256': hashlib.sha256((out / 'check.tos').read_bytes()).hexdigest(),
                  'source_sha256': hashlib.sha256((ROOT / 'src/shake.s').read_bytes()).hexdigest()}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'PASS MC{cpu}: {len(rows)} DOS cases and independent clock adapter', flush=True)
        # Exercise the actual interrupt installation, chained TOS clock, and
        # restoration with game rendering idle. This detects a frame-coupled
        # adapter and a handler that accidentally suppresses the OS tick.
        timer_source = '''
        include "inc/cpu.s"
        global _main, timer_done, timer_results, vector_base, display_screen
        global vbl_install, vbl_remove, flight_shake_clock
        global flt_shake_rng, flt_shake_phase, flt_shake_timer, shake_clock_accumulator
        text
_main
        clr.l -(sp)
        move.w #$20,-(sp)
        trap #1
        addq.l #6,sp
        move #$2700,sr
        movec vbr,d0
        move.l d0,vector_base
        move.l d0,a0
        move.l $70(a0),old_vbl
        moveq #0,d0
        move.b $fffffa17.w,d0
        andi.w #$f0,d0
        addq.w #5,d0
        lsl.w #2,d0
        adda.w d0,a0
        move.l a0,timer_vector
        move.l (a0),old_timer
        move.b $ffff8201.w,display_screen+1
        move.b $ffff8203.w,display_screen+2
        move.b $ffff820d.w,display_screen+3
        bsr vbl_install
        move.l $4ba.w,d7
        move #$2300,sr
.wait
        move.l $4ba.w,d0
        sub.l d7,d0
        cmpi.l #200,d0
        bcs .wait
        move #$2700,sr
        move.l $4ba.w,d0
        sub.l d7,d0
        move.l d0,timer_results
        move.l flt_shake_rng,timer_results+4
        move.l shake_clock_accumulator,timer_results+8
        bsr vbl_remove
        move.l vector_base,a0
        move.l $70(a0),d0
        cmp.l old_vbl,d0
        bne timer_done
        move.l timer_vector,a0
        move.l (a0),d0
        cmp.l old_timer,d0
        bne timer_done
        move.l #1,timer_results+12
timer_done
        bra timer_done
        bss
vector_base
        ds.l 1
display_screen
        ds.l 1
old_vbl
        ds.l 1
old_timer
        ds.l 1
timer_vector
        ds.l 1
timer_results
        ds.l 4
        end
'''
        (out / 'timer.s').write_text(timer_source)
        for name, path in [('timer', out / 'timer.s'), ('vbl', ROOT / 'src/vbl.s')]:
            helper.run([vasm, str(path), '-quiet', '-Felf', f'-m{cpu}', f'-DTARGET_CPU={cpu}',
                        '-I' + str(ROOT / 'src'), '-o', str(out / f'{name}.o')], ROOT, out / f'{name}.log')
        helper.run([vlink, '-b', 'ataritos', '-e', '_main', '-o', str(out / 'timer.tos'),
                    str(out / 'timer.o'), str(out / 'vbl.o'), str(out / 'shake.o')], ROOT, out / 'timer-link.log')
        helper.entry_breakpoint(out, 'timer.tos', 'b pc = timer_done :once :file timer-done.ini\n')
        (out / 'timer-done.ini').write_text('savebin timer-results.bin timer_results $10\nquit\n')
        (out / 'timer-results.bin').unlink(missing_ok=True)
        helper.run(helper.emulator_command(out, cpu, 'timer.tos', 'boot.ini'), out, out / 'timer-hatari.log')
        raw = (out / 'timer-results.bin').read_bytes()
        ticks, rng, remainder, restored = [int.from_bytes(raw[i:i+4], 'big') for i in range(0, 16, 4)]
        assert 200 <= ticks <= 202, ticks
        count, expected_remainder = divmod(ticks * 1193182, 200 * 0x47b4)
        expected_rng = 0
        for _ in range(count):
            value = ((expected_rng ^ 0xa50a50a0) + 0x50a05) & 0xffffffff
            expected_rng = ((value >> 3) | (value << 29)) & 0xffffffff
        assert (rng, remainder, restored) == (expected_rng, expected_remainder, 1), (rng, remainder, restored)
        result['timer_hook'] = {'status': 'PASS', 'tos_ticks': ticks, 'pit_events': count,
                                'vectors_restored': True,
                                'program_sha256': hashlib.sha256((out / 'timer.tos').read_bytes()).hexdigest()}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'PASS MC{cpu}: {ticks} chained TOS ticks with rendering idle; both vectors restored', flush=True)


if __name__ == '__main__':
    main()
