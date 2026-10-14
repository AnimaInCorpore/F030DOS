#!/usr/bin/env python3
"""Probe RTLink segment destinations in the running Falcon3 image.

This is Falcon3-specific: RTLink stores separate load segments rather than a
Borland FBOV pool. It reports prefix and full-payload byte matches only;
relocations, runtime writes, zero-filled regions, and shared data can make a
match ambiguous.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HDD = ROOT / "img" / "falcon3.hdd"
EXE = ROOT / "game" / "FALCON3" / "FALCON3.EXE"
PORT = 4556
sys.path.insert(0, str(ROOT))
from tools.re import rtlink
import work.gdbstub_probe as qemu


def measure_segments(qmp, segments, data):
    """Return first-64-byte match counts for every declared RTLink segment."""

    def xp(addr: int, count: int) -> bytes:
        text = qmp.hmp(f"xp /{count}xb 0x{addr:x}")
        vals = []
        for token in text.split():
            token = token[2:] if token.startswith("0x") else token
            if len(token) == 2 and all(
                    c in "0123456789abcdef" for c in token.lower()):
                vals.append(token)
        return bytes.fromhex("".join(vals[:count]))

    result = {}
    for seg in segments:
        size = seg["paragraphs"] * 16
        if not size:
            continue
        sample = min(64, size)
        wanted = data[seg["code_offset"]:seg["code_offset"] + sample]
        got = xp(seg["load_segment"] << 4, sample)
        same = sum(a == b for a, b in zip(wanted, got))
        result[seg["index"]] = {
            "load_segment": seg["load_segment"],
            "code_offset": seg["code_offset"],
            "paragraphs": seg["paragraphs"],
            "same": same,
            "sample": sample,
        }
    return result


def print_measurement(label, measurement):
    print(f"--- {label} ---")
    print("segment load-segment file-code-offset paragraphs exact/checked")
    for index in sorted(measurement):
        seg = measurement[index]
        print(f"{index:02d} {seg['load_segment']:04x} "
              f"0x{seg['code_offset']:06x} {seg['paragraphs']:5d} "
              f"{seg['same']:02d}/{seg['sample']:02d}")


def screenshot(qmp, name):
    outdir = Path(qemu.OUTDIR)
    outdir.mkdir(parents=True, exist_ok=True)
    ppm = outdir / f"{name}.ppm"
    png = outdir / f"{name}.png"
    qmp._cmd({"execute": "screendump",
              "arguments": {"filename": ppm.as_posix()}})
    time.sleep(1.0)
    if ppm.exists():
        subprocess.run([qemu.FFMPEG, "-y", "-loglevel", "error",
                        "-i", str(ppm), str(png)], capture_output=True)
    return png if png.exists() else ppm


def dump_memory(qmp, name):
    """Save the 16 MiB guest physical address space for offline comparison."""

    outdir = Path(qemu.OUTDIR)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{name}.bin"
    qmp.hmp(f'pmemsave 0 0x1000000 "{path.as_posix()}"')
    if not path.exists():
        raise RuntimeError(f"QEMU did not create {path}")
    return path


def compare_full_segments(ram_path, measurement, data):
    """Print the strongest full-segment matches grouped by load segment."""

    ram = ram_path.read_bytes()
    groups = {}
    for index, seg in measurement.items():
        base = seg["load_segment"] << 4
        size = seg["paragraphs"] * 16
        wanted = data[seg["code_offset"]:seg["code_offset"] + size]
        got = ram[base:base + len(wanted)]
        same = sum(a == b for a, b in zip(wanted, got))
        groups.setdefault(seg["load_segment"], []).append((same, len(wanted), index))
    print("full-segment matches by load segment:")
    for load_segment in sorted(groups):
        ranked = sorted(groups[load_segment], reverse=True)
        summary = ", ".join(f"{index}={same}/{size}"
                            for same, size, index in ranked[:4])
        print(f"  {load_segment:04x}: {summary}")


def main() -> None:
    geometry = json.loads((HDD.with_suffix(HDD.suffix + ".geom.json")).read_text())
    data = EXE.read_bytes()
    audit = rtlink.audit(EXE, None)
    segments = audit["segments"]

    qemu.kill_strays()
    g = geometry
    cmd = [
        qemu.QEMU, "-M", "pc", "-cpu", "486", "-m", "16",
        "-drive", f"file={HDD.as_posix()},format=raw,if=none,id=hd0,cache=writeback",
        "-device", f"ide-hd,drive=hd0,bus=ide.0,unit=0,cyls={g['cyls']},"
                   f"heads={g['heads']},secs={g['secs']}",
        "-boot", "c", "-display", "none", "-vga", "std", "-no-reboot",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=0x04",
        "-qmp", f"tcp:127.0.0.1:{PORT},server=on,wait=off",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    try:
        print("waiting for the War Room baseline ...", flush=True)
        time.sleep(50)
        qmp = qemu.Qmp(PORT)
        baseline = measure_segments(qmp, segments, data)
        print_measurement("War Room baseline", baseline)
        warroom_ram = dump_memory(qmp, "rtlink_warroom_ram")
        compare_full_segments(warroom_ram, baseline, data)
        print("sending War Room -> Instant Action navigation ...", flush=True)
        for key in (['right'] * 4) + (['up'] * 4):
            qmp.hmp(f"sendkey {key}")
            time.sleep(0.8)
        qmp.hmp("sendkey ret")
        time.sleep(7.0)
        if qmp.dead:
            raise RuntimeError("QEMU guest exited during Instant Action transition")

        after = measure_segments(qmp, segments, data)
        print_measurement("Instant Action", after)
        instant_ram = dump_memory(qmp, "rtlink_instant_ram")
        compare_full_segments(instant_ram, after, data)
        changed = []
        for index in sorted(baseline):
            before = baseline[index]["same"]
            now = after[index]["same"]
            if before != now:
                changed.append((index, before, now))
        print("changed first-64-byte match counts:",
              changed if changed else "none")
        regs = qemu.parse_regs(qmp.hmp("info registers"))
        if "CS" in regs and "EIP" in regs:
            print(f"CS:IP={regs['CS']:04x}:{regs['EIP']:04x} "
                  f"linear=0x{(regs['CS'] << 4) + regs['EIP']:05x}")
        print("screenshot:", screenshot(qmp, "rtlink_after"))
        qmp.close()
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
