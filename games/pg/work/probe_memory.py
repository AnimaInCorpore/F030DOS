#!/usr/bin/env python3
"""Measure whether the physical tail of PANZER.EXE is resident in RAM.

This is intentionally a residency probe, not an overlay-loader detector.  It
captures physical memory from a running DOS oracle, then searches for diverse,
source-unique 32-byte windows from the bytes after the declared LE end.  A
consistent ``guest address - file offset`` delta is useful evidence of a
runtime copy; it does not by itself identify which loader or game subsystem
placed the bytes there.

The image must already have been built with ``--use-no-sound --run-game
--hold``.  Example::

    python3 work/build_dos_hdd.py --use-no-sound --run-game --hold --no-boot
    python3 work/probe_memory.py --seconds 8
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "game" / "EXE" / "PANZER.EXE"
LE_DECLARED_END = 0x9283D
WINDOW = 32
MIN_DIVERSE_BYTES = 8
sys.path.insert(0, str(ROOT / "work"))
import run_qemu  # noqa: E402


def unique_hit(ram: bytes, needle: bytes, minimum: int) -> int | None:
    """Return a RAM address only when the byte window has one RAM hit."""
    first = ram.find(needle, minimum)
    if first < 0 or ram.find(needle, first + 1) >= 0:
        return None
    return first


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=8.0,
                        help="let the DOS oracle run before the snapshot")
    parser.add_argument("--stride", type=lambda value: int(value, 0),
                        default=0x100,
                        help="file stride for tail windows (default: 0x100)")
    parser.add_argument("--min-ram", type=lambda value: int(value, 0),
                        default=0x100000,
                        help="ignore lower physical memory when searching")
    parser.add_argument("--ram-size", type=lambda value: int(value, 0),
                        default=0x400000,
                        help="physical RAM bytes to capture (default: 0x400000)")
    parser.add_argument("--hdd", default=run_qemu.HDD)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "work" / "qemu_out" / "pg_ram_probe.bin")
    args = parser.parse_args()

    if args.stride <= 0:
        parser.error("--stride must be positive")
    if args.ram_size < WINDOW or args.min_ram >= args.ram_size:
        parser.error("--ram-size must exceed --min-ram and the window size")
    if not EXE.exists():
        parser.error(f"missing {EXE}; run work/extract_game.py first")

    exe = EXE.read_bytes()
    if LE_DECLARED_END >= len(exe):
        parser.error("PANZER.EXE is shorter than its declared LE end")

    cyls, heads, secs, _part_offset = run_qemu.geometry(args.hdd)
    port = run_qemu.free_port()
    drive = (f"file={str(args.hdd).replace(chr(92), '/')},format=raw,"
             "if=none,id=hd0,cache=writeback")
    command = [run_qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", drive,
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,"
                          f"cyls={cyls},heads={heads},secs={secs}",
               "-boot", "c", "-display", "none", "-vga", "std",
               "-no-reboot", "-qmp",
               f"tcp:127.0.0.1:{port},server=on,wait=off"]
    print("$", " ".join(command), flush=True)

    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_qemu.stale(str(args.output))
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    qmp = run_qemu.Qmp(port)
    try:
        time.sleep(args.seconds)
        result = qmp.hmp(
            f'pmemsave 0x0 0x{args.ram_size:X} '
            f'"{str(args.output).replace(chr(92), "/")}"')
        if result.startswith("<qmp"):
            raise RuntimeError(result)
        deadline = time.monotonic() + 3.0
        while (not args.output.exists()
               or args.output.stat().st_size != args.ram_size):
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"RAM snapshot is missing or short: {args.output}")
            time.sleep(0.05)
    finally:
        qmp.hmp("quit")
        qmp.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    ram = args.output.read_bytes()
    tail_offsets = range(LE_DECLARED_END, len(exe) - WINDOW + 1,
                         args.stride)
    candidates = 0
    source_ambiguous = 0
    matches: list[tuple[int, int]] = []
    deltas = Counter()
    for file_offset in tail_offsets:
        window = exe[file_offset:file_offset + WINDOW]
        if len(set(window)) < MIN_DIVERSE_BYTES:
            continue
        if exe.find(window, file_offset + 1) >= 0:
            source_ambiguous += 1
            continue
        candidates += 1
        guest_address = unique_hit(ram, window, args.min_ram)
        if guest_address is None:
            continue
        matches.append((file_offset, guest_address))
        deltas[guest_address - file_offset] += 1

    print(f"RAM snapshot: {args.output} ({len(ram)} bytes)")
    print(f"tail region: file 0x{LE_DECLARED_END:X}..0x{len(exe):X}")
    print(f"source-unique diverse windows: {candidates} "
          f"(source-ambiguous skipped: {source_ambiguous})")
    print(f"unique RAM matches: {len(matches)}")
    if deltas:
        print("deltas:", ", ".join(f"0x{k:X} ({v})"
                                    for k, v in deltas.most_common()))
        file_offset, guest_address = matches[0]
        print(f"first match: file 0x{file_offset:X} -> "
              f"guest 0x{guest_address:X}")
    else:
        print("no unique tail windows found in captured RAM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
