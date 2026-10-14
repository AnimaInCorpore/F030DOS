#!/usr/bin/env python3
"""Inventory the supplied SMFs; static demand estimates, not DOS replay proof.

Requires mido==1.3.3. See analysis/music.md for scope and unresolved semantics.
This offline analysis tool does not implement a recovered DOS game function.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
import hashlib
import importlib.metadata
import json
from pathlib import Path
import struct

import mido


def validate_chunks(data: bytes) -> tuple[int, int, int]:
    """Require complete SMF chunks and no unaccounted trailing bytes."""
    if data[:8] != b'MThd\0\0\0\6':
        raise ValueError('not a six-byte-header SMF')
    fmt, tracks, division = struct.unpack('>HHH', data[8:14])
    if fmt not in (0, 1) or not tracks or not 0 < division < 0x8000:
        raise ValueError('unsupported SMF format, tracks or time division')
    if fmt == 0 and tracks != 1:
        raise ValueError('type 0 must have one track')
    pos = 14
    for _ in range(tracks):
        if data[pos:pos+4] != b'MTrk' or pos+8 > len(data):
            raise ValueError(f'missing track chunk at {pos:#x}')
        size = int.from_bytes(data[pos+4:pos+8], 'big')
        pos += 8+size
        if pos > len(data):
            raise ValueError('truncated track')
    if pos != len(data):
        raise ValueError(f'{len(data)-pos} unaccounted bytes')
    return fmt, tracks, division


def sysex_only_messages(data: bytes) -> list[dict]:
    """Inspect one-track setup files while retaining F0/F7 continuation framing."""
    fmt, tracks, _ = validate_chunks(data)
    if fmt != 0 or tracks != 1:
        raise ValueError('SysEx setup inspection requires one type-0 track')
    pos, end = 22, len(data)
    pending = None
    messages = []

    def vlq() -> int:
        nonlocal pos
        value = 0
        for _ in range(4):
            if pos >= end:
                raise ValueError('truncated setup VLQ')
            byte = data[pos]
            pos += 1
            value = (value << 7) | (byte & 127)
            if not byte & 128:
                return value
        raise ValueError('oversize setup VLQ')

    while pos < end:
        vlq()  # Delta time is counted by the general MIDI analysis.
        status = data[pos]
        pos += 1
        if status == 0xff:
            pos += 1  # Meta type.
            length = vlq()
            pos += length
            if pos > end:
                raise ValueError('truncated setup metadata')
            continue
        if status not in (0xf0, 0xf7):
            raise ValueError('non-SysEx channel event in setup file')
        length = vlq()
        payload = data[pos:pos+length]
        pos += length
        if len(payload) != length:
            raise ValueError('truncated setup packet')
        if status == 0xf0:
            if pending is not None:
                raise ValueError('new SysEx before previous message finished')
            pending = bytearray()
        elif pending is None:
            raise ValueError('standalone F7 escape requires separate interpretation')
        pending.extend(payload)
        if payload.endswith(b'\xf7'):
            raw = bytes(pending[:-1])
            if any(byte >= 128 for byte in raw):
                raise ValueError('non-data byte inside completed SysEx')
            entry = dict(bytes=len(raw), prefix=raw[:7].hex(),
                         sha256=hashlib.sha256(raw).hexdigest())
            if raw[:4] == bytes.fromhex('41101612') and len(raw) >= 8:
                entry.update(address=raw[4:7].hex(), data_bytes=len(raw)-8,
                             roland_checksum_valid=(sum(raw[4:]) & 127) == 0)
            messages.append(entry)
            pending = None
    if pending is not None:
        raise ValueError('unfinished SysEx at end of setup file')
    return messages


def analyze(path: Path, window_ms: float) -> dict:
    data = path.read_bytes()
    fmt, tracks, division = validate_chunks(data)
    midi = mido.MidiFile(path, clip=False)
    if (midi.type, len(midi.tracks), midi.ticks_per_beat) != (fmt, tracks, division):
        raise ValueError('header disagreement with Mido')
    for track in midi.tracks:
        if not track or track[-1].type != 'end_of_track':
            raise ValueError('track does not finish with end_of_track')
        if sum(m.type == 'end_of_track' for m in track) != 1:
            raise ValueError('multiple end_of_track events')

    tick = 0
    seconds = 0.0
    tempo = 500000
    keys = Counter()
    event_types, controllers = Counter(), Counter()
    programs, bank_selects = set(), set()
    channel_notes, programs_at_note_on = Counter(), Counter()
    current_program = [None]*16
    starts = deque()
    same_tick = Counter()
    note_count = unmatched_offs = 0
    peak_event = peak_settled = peak_attacks = 0
    peak_event_at = peak_settled_at = peak_attack_at = 0.0
    sysex = []
    window = window_ms/1000
    for msg in mido.merge_tracks(midi.tracks):
        if msg.time:
            count = sum(keys.values())
            if count > peak_settled:
                peak_settled, peak_settled_at = count, seconds
        tick += msg.time
        seconds += mido.tick2second(msg.time, division, tempo)
        event_types[msg.type] += 1
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        elif msg.type == 'program_change':
            current_program[msg.channel] = msg.program
            programs.add(msg.program)
        elif msg.type == 'control_change':
            controllers[msg.control] += 1
            if msg.control in (0, 32):
                bank_selects.add((msg.channel, msg.control, msg.value))
            if msg.control in (120, 123):
                for key in list(keys):
                    if key[0] == msg.channel:
                        del keys[key]
        elif msg.type == 'sysex':
            raw = bytes(msg.data)
            sysex.append(dict(bytes=len(raw), prefix=raw[:8].hex(),
                              sha256=hashlib.sha256(raw).hexdigest()))
        elif msg.type == 'note_on' and msg.velocity:
            keys[msg.channel, msg.note] += 1
            note_count += 1
            channel_notes[msg.channel+1] += 1
            program = current_program[msg.channel]
            programs_at_note_on[str(program) if program is not None else 'unspecified'] += 1
            same_tick[tick] += 1
            starts.append(seconds)
            while starts and seconds-starts[0] >= window:
                starts.popleft()
            if len(starts) > peak_attacks:
                peak_attacks, peak_attack_at = len(starts), seconds
        elif msg.type == 'note_off' or (msg.type == 'note_on' and not msg.velocity):
            key = msg.channel, msg.note
            if keys[key]:
                keys[key] -= 1
                if not keys[key]:
                    del keys[key]
            else:
                unmatched_offs += 1
        count = sum(keys.values())
        if count > peak_event:
            peak_event, peak_event_at = count, seconds
    count = sum(keys.values())
    if count > peak_settled:
        peak_settled, peak_settled_at = count, seconds
    if abs(seconds-midi.length) > 1e-6:
        raise ValueError('tempo conversion disagrees with Mido iterator')
    setup = None
    if sysex and not note_count and all(m.is_meta or m.type == 'sysex' for t in midi.tracks for m in t):
        setup = sysex_only_messages(data)
    return dict(file=path.name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
                format=fmt, tracks=tracks, ticks_per_quarter=division, seconds=seconds,
                note_ons=note_count, programs_zero_based=sorted(programs),
                programs_at_note_on=dict(sorted(programs_at_note_on.items())),
                note_ons_by_channel=dict(sorted(channel_notes.items())),
                bank_selects=sorted(bank_selects), event_types=dict(sorted(event_types.items())),
                controllers=dict(sorted(controllers.items())), sysex_packets=sysex,
                sysex_setup_messages=setup,
                peak_key_down_event_order=peak_event, peak_key_down_event_seconds=peak_event_at,
                peak_key_down_after_tick=peak_settled, peak_key_down_after_tick_seconds=peak_settled_at,
                peak_note_ons_same_tick=max(same_tick.values(), default=0),
                peak_note_ons_in_window=peak_attacks, peak_note_window_seconds=peak_attack_at,
                unmatched_note_offs=unmatched_offs, remaining_key_down=count,
                track_names=[t.name for t in midi.tracks if t.name])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('game/FALCON3/MUSIC'))
    parser.add_argument('--output', type=Path, default=Path('work/music-analysis/inventory.json'))
    parser.add_argument('--attack-ms', type=float, default=151.0)
    args = parser.parse_args()
    if args.attack_ms <= 0:
        parser.error('--attack-ms must be positive')
    files = sorted(p for p in args.source.iterdir() if p.is_file())
    if not files:
        raise SystemExit('No music files found')
    results, errors, hashes = [], [], set()
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes.add(digest)
        try:
            results.append(analyze(path, args.attack_ms))
        except Exception as exc:
            errors.append(dict(file=path.name, sha256=digest, error=str(exc)))
    report = dict(mido=importlib.metadata.version('mido'), attack_window_ms=args.attack_ms,
                  scope='Static SMF analysis; DOS device selection and playback semantics unverified',
                  limitations=['Key-down counts omit pedal-held notes and release tails.',
                               'Repeated equal-pitch starts count independently until note-off.',
                               'Controllers 120/123 clear counted keys; other controllers are inventoried only.',
                               'Same-tick order is Mido stable track merge, not a DOS execution witness.',
                               'SysEx, loops, program mapping and driver-specific events are not executed.',
                               f'Window counts retain all starts for {args.attack_ms:g} ms, even if a note ends earlier.'],
                  files=len(files), parsed=len(results), unique_files=len(hashes),
                  extension_counts=dict(sorted(Counter(p.suffix for p in files).items())),
                  errors=errors, results=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(f'{len(files)} files, {len(results)} parsed, {len(errors)} rejected, '
          f'{report["unique_files"]} unique byte streams; {args.output}')
    for suffix in report['extension_counts']:
        group = [r for r in results if r['file'].endswith(suffix)]
        if not group:
            continue
        peak = max(group, key=lambda r:r['peak_key_down_after_tick'])
        attack = max(group, key=lambda r:r['peak_note_ons_in_window'])
        burst = max(r['peak_note_ons_same_tick'] for r in group)
        print(f'{suffix}: {len(group)} files; peak keys {peak["peak_key_down_after_tick"]} '
              f'({peak["file"]}); starts/{args.attack_ms:g} ms {attack["peak_note_ons_in_window"]} '
              f'({attack["file"]}); same-tick starts {burst}')
    if errors:
        raise SystemExit('Incomplete corpus: '+', '.join(e['file'] for e in errors))


if __name__ == '__main__':
    main()
