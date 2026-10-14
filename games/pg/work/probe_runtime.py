#!/usr/bin/env python3
"""Capture the live DOS/4GW placement of the selected PANZER.EXE.

The LE object bases are linker addresses, not a promise about the linear
address assigned by DOS/4GW.  This probe samples the running protected-mode
CPU through QMP, reads the bytes at flat ``CS:EIP`` and matches an unrelocated
window back to the pristine executable.  It is deliberately a small runtime
witness: it does not infer a tail mapping or turn a byte match into a code
classification.

The image must already have been built with ``--use-no-sound --run-game``.
For example::

    python3 work/build_dos_hdd.py --use-no-sound --run-game --hold --no-boot
    python3 work/probe_runtime.py --seconds 8
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "game" / "EXE" / "PANZER.EXE"
sys.path.insert(0, str(ROOT / "work"))
import run_qemu  # noqa: E402


def register(text: str, name: str) -> int | None:
    match = re.search(rf"\b{name}\s*=\s*([0-9A-Fa-f]+)", text)
    return int(match.group(1), 16) if match else None


def segment_base(text: str, name: str) -> int | None:
    match = re.search(rf"\b{name}\s*=\s*[0-9A-Fa-f]+\s+([0-9A-Fa-f]+)", text)
    return int(match.group(1), 16) if match else None


def guest_bytes(qmp, address: int, count: int = 32) -> bytes:
    raw = qmp.hmp(f"xp /{count}xb 0x{address:X}")
    values = []
    for token in raw.split():
        token = token[2:] if token.lower().startswith("0x") else token
        if len(token) == 2 and all(c in "0123456789abcdefABCDEF" for c in token):
            values.append(token)
    try:
        return bytes.fromhex("".join(values[:count]))
    except ValueError:
        return b""


def all_hits(haystack: bytes, needle: bytes) -> list[int]:
    hits = []
    start = 0
    while needle:
        hit = haystack.find(needle, start)
        if hit < 0:
            break
        hits.append(hit)
        start = hit + 1
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=8.0)
    parser.add_argument("--interval", type=float, default=0.01)
    parser.add_argument("--min-eip", type=lambda value: int(value, 0),
                        default=0x100000,
                        help="only inspect flat EIPs at or above this address")
    args = parser.parse_args()

    exe = EXE.read_bytes()
    hdd = run_qemu.HDD
    cyls, heads, secs, _part_offset = run_qemu.geometry(hdd)
    port = run_qemu.free_port()
    drive = (f"file={str(hdd).replace(chr(92), '/')},format=raw,"
             "if=none,id=hd0,cache=writeback")
    command = [run_qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
               "-drive", drive,
               "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,"
                          f"cyls={cyls},heads={heads},secs={secs}",
               "-boot", "c", "-display", "none", "-vga", "std",
               "-no-reboot", "-qmp",
               f"tcp:127.0.0.1:{port},server=on,wait=off"]
    print("$", " ".join(command), flush=True)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    qmp = run_qemu.Qmp(port)
    seen = set()
    deltas = Counter()
    samples = 0
    try:
        started = time.monotonic()
        while time.monotonic() - started < args.seconds:
            info = qmp.hmp("info registers")
            eip = register(info, "EIP")
            cs_base = segment_base(info, "CS")
            cr0 = register(info, "CR0")
            if (eip is not None and cs_base == 0 and cr0 is not None
                    and cr0 & 1 and eip >= args.min_eip):
                samples += 1
                blob = guest_bytes(qmp, eip)
                hits = all_hits(exe, blob[:10]) if len(blob) >= 10 else []
                key = (eip, blob[:10], tuple(hits))
                if key not in seen:
                    seen.add(key)
                    if hits:
                        delta = eip - hits[0]
                        deltas[delta] += 1
                        print(f"  EIP 0x{eip:X} -> file 0x{hits[0]:X}; "
                              f"delta 0x{delta:X}; bytes {blob[:16].hex(' ')}",
                              flush=True)
                    else:
                        print(f"  EIP 0x{eip:X} -> no file hit; "
                              f"bytes {blob[:16].hex(' ')}", flush=True)
            time.sleep(args.interval)
    finally:
        qmp.hmp("quit")
        qmp.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    print(f"protected-mode samples: {samples}")
    if deltas:
        print("deltas:", ", ".join(f"0x{k:X} ({v})"
                                    for k, v in deltas.most_common()))
    else:
        print("no flat protected-mode file matches captured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
