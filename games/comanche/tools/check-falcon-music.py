#!/usr/bin/env python3
"""Check the Falcon music driver (src/music.s) write for write against the original.

N/A - target artefact: a test driver, no DOS routine.
Record: analysis/functions/sound-driver.md section 9

What runs: tools/music-test.s is assembled with src/music.s into a stand-alone
TOS program that replays the original's own captures (build/sound/*.json,
work/trace_sound_writes.py, captured on MS-DOS 6.22 under QEMU with a YM3812):
every driver command, song start and stop, timer tick and song placement in
the order the original made them, with the card's status reads answered as
the original's card answered them. For every op it compares, against the
capture: the OPL2 register writes in order, the AL a command returns, and the
driver's variables (a weighted sum over the non-pointer bytes, which the
capture's per-op deltas reconstruct from the image's bytes).

Captures of the PC speaker or the MPU-401 are listed and skipped: the Falcon
has neither behind those ports (src/music.s, "Differences").

Usage: python3 tools/check-falcon-music.py [--out build/falcon-music]
                                           [--cpu 68030|68060] [--no-run]
Exits 0 only if every op of every compared capture matches.
"""
import argparse
import glob
import json
import os
import pathlib
import struct
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "extracted" / "comanche_hdd"
FLAT = ROOT / "re" / "unpacked" / "comanche-flat32.bin"
FLAT_SHA256 = "a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c"
MUS_BASE, MUS_END = 0x2C48C, 0x2DA00
ARENA_BASE, ARENA_BYTES = 0x400000, 0x40000
# The bytes the checksum covers (tools/music-test.s has the same list).
RANGES = [(0x2C49C, 0x2C4A2), (0x2C4A4, 0x2C4E8), (0x2C568, 0x2C5D3), (0x2D10D, 0x2D11F)]
SKIP = {"detect-absent": "detects devices 1 and 4 (speaker, MPU-401)",
        "device-switch": "selects devices 4 and 1"}


def tool(env, mac, win):
    if os.environ.get(env):
        return os.environ[env]
    arcade = pathlib.Path(os.environ.get("F030ARCADE_ROOT", ROOT.parent / "F030Arcade"))
    mac_path = arcade / "third_party" / "chorensha" / "tools" / mac
    if sys.platform == "darwin" and mac_path.exists():
        return str(mac_path)
    return str(ROOT / "tools" / "toolchain" / win)


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"{' '.join(map(str, cmd))} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout + r.stderr


def decode_music(data):
    """The loader 00015E6E's containers: KRL0 stored, KRL1 run-length, else raw."""
    tag, size = data[:4], struct.unpack_from("<I", data, 4)[0] if len(data) >= 8 else 0
    if tag == b"KRL0":
        return data[8:8 + size]
    if tag == b"KRL1":
        out, at = bytearray(), 8
        while len(out) < size:
            b = data[at]; at += 1
            if b < 0xC0:
                out.append(b)
                continue
            v = data[at]; at += 1
            out += bytes([v]) * min(b & 0x3F, size - len(out))
        return bytes(out)
    return data


def checksum(mem):
    total = 0
    for lo, hi in RANGES:
        for a in range(lo, hi):
            total += mem[a - MUS_BASE] * (a - MUS_BASE + 1)
    return total & 0xFFFFFFFF


def build_script(captures, image):
    """MUSIC.SCR and, per op, the expectation."""
    script = bytearray()
    expect = []
    def span(addr, data):
        if not ARENA_BASE <= addr and addr + len(data) <= ARENA_BASE + ARENA_BYTES:
            raise SystemExit(f"a song at {addr:x} is outside the test arena")
        b = struct.pack(">IH", addr, len(data)) + data
        return b + (b"\0" if len(data) & 1 else b"")
    for name, cap in captures:
        mem = bytearray(image[MUS_BASE:MUS_END])
        placed = set()
        spans = []
        ops = []
        for op in cap["ops"]:
            if op["op"] == "start" and op["ebx"] not in placed:
                song = decode_music((ASSETS / op["file"]).read_bytes())
                if len(song) != op["size"]:
                    raise SystemExit(f"{name}: {op['file']} decodes to {len(song)}, the capture has {op['size']}")
                spans.append((op["ebx"], song))
                placed.add(op["ebx"])
            if op["op"] == "start_bytes":
                spans.append((op["ebx"], bytes.fromhex(op["hex"])))
        script += b"\x01" + struct.pack(">H", len(spans)) + b"".join(span(a, d) for a, d in spans)
        for op in cap["ops"]:
            writes = [w for w in op["writes"] if w[0] == "o"]
            status = [w[1] for w in op["writes"] if w[0] == "s"]
            kind = op["op"]
            if kind in ("command", "effect"):
                ax = op["ax"] if kind == "command" else op["ebp"] & 0xFFFF
                b = b"\x02" + struct.pack(">HH", ax, len(status)) + bytes(status)
                script += b + (b"\0" if len(status) & 1 else b"")
            elif kind in ("start", "start_bytes"):
                script += b"\x03" + struct.pack(">HI", op["al"], op["ebx"])
            elif kind == "stop":
                script += b"\x04"
            elif kind == "tick":
                script += b"\x05"
            elif kind == "poke_bytes":
                script += b"\x06" + span(op["address"], bytes.fromhex(op["bytes"]))
            else:
                raise SystemExit(f"{name}: op {kind} has no script form")
            for addr, value in op["delta"]:
                if MUS_BASE <= addr < MUS_END:
                    mem[addr - MUS_BASE] = value
            al = op["ret_al"] if kind in ("command", "effect") else 0
            expect.append((name, op["i"], kind, al, checksum(mem), [(w[1], w[2]) for w in writes]))
    script += b"\x00"
    return bytes(script), expect


def build(out, cpu):
    vasm = tool("VASM", "vasmm68k_mot_mac", "vasmm68k_mot.exe")
    vlink = tool("VLINK", "vlink_mac", "vlink.exe")
    objs = []
    for src in ("tools/music-test.s", "src/music.s"):
        obj = out / (pathlib.Path(src).stem + ".o")
        run([vasm, str(ROOT / src), "-I", str(ROOT / "src"), "-quiet", "-Felf", f"-m{cpu}",
             f"-DTARGET_CPU={cpu}", "-o", str(obj)])
        objs.append(str(obj))
    run([vlink, *objs, "-q", "-Rstd", "-b", "ataritos", "-tos-flags", "1", "-e", "_main",
         "-o", str(out / "MUSTEST.TOS")])


def hatari(out, timeout, cpu):
    for name in ("MUSOUT.BIN", "MUSDONE.TXT"):
        (out / name).unlink(missing_ok=True)
    arcade = pathlib.Path(os.environ.get("F030ARCADE_ROOT", ROOT.parent / "F030Arcade"))
    exe = os.environ.get("HATARI") or str(arcade / "third_party" / "hatari" / "build" / "src" / "hatari")
    if cpu == "68060":
        tos = arcade / "third_party" / "tos" / "etos512de.img"
        cpuopt = ["--cpulevel", "6", "--cpuclock", "32", "--fpu", "internal", "--ttram", "64",
                  "--addr24", "false"]
    else:
        tos = ROOT / "tools" / "toolchain" / "tos402.rom"
        cpuopt = ["--cpulevel", "3", "--cpuclock", "16", "--fpu", "none"]
    cmd = [exe, "--machine", "falcon", "--memsize", "14", "--tos", str(os.environ.get("TOS", tos)),
           *cpuopt, "--cpu-exact", "true", "--compatible", "true", "--patch-tos", "true",
           "--fast-boot", "true", "--dsp", "off", "--monitor", "rgb", "--frameskips", "0",
           "--sound", "off", "--fast-forward", "true", "--disable-video", "on",
           "--confirm-quit", "off", "--harddrive", str(out), "--auto", "C:\\MUSTEST.TOS",
           "--log-file", str(out / "hatari.log"), "--alert-level", "fatal"]
    started = time.time()
    with (out / "hatari-stdout.txt").open("w") as log:
        proc = subprocess.Popen(cmd, cwd=out, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT)
        try:
            while time.time() - started < timeout:
                if (out / "MUSDONE.TXT").exists():
                    time.sleep(0.5)
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
    return time.time() - started, exe


def compare(out, expect):
    got = (out / "MUSOUT.BIN").read_bytes()
    at = 0
    per = {}
    bad = []
    for name, i, kind, al, csum, writes in expect:
        p = per.setdefault(name, [0, 0, 0])
        if at + 8 > len(got):
            bad.append((name, i, kind, "the program's output ends here"))
            break
        n, ral, left, rsum = struct.unpack_from(">HBBI", got, at)
        at += 8
        pairs = [tuple(got[at + 2 * k:at + 2 * k + 2]) for k in range(n)]
        at += 2 * n
        p[1] += 1
        p[2] += len(writes)
        problems = []
        if pairs != writes:
            k = next((k for k, (a, b) in enumerate(zip(pairs, writes)) if a != b), min(len(pairs), len(writes)))
            problems.append(f"writes differ from write {k}: Falcon {pairs[k] if k < len(pairs) else None} "
                            f"(of {len(pairs)}), DOS {writes[k] if k < len(writes) else None} (of {len(writes)})")
        if kind in ("command", "effect") and ral != al:
            problems.append(f"AL {ral:02X}, DOS {al:02X}")
        if left:
            problems.append(f"{left} status reads the original made were not made")
        if rsum != csum:
            problems.append("the driver's variables differ")
        if problems:
            bad.append((name, i, kind, "; ".join(problems)))
        else:
            p[0] += 1
    print(f"{'capture':24} {'ops':>15} {'writes':>8}")
    for name, (ok, ops, writes) in per.items():
        print(f"{name:24} {ok:>7}/{ops:<7} {writes:>8}")
    print(f"{'TOTAL':24} {sum(p[0] for p in per.values()):>7}/{sum(p[1] for p in per.values()):<7} "
          f"{sum(p[2] for p in per.values()):>8}")
    for b in bad[:8]:
        print(f"MISMATCH {b[0]} op {b[1]} ({b[2]}): {b[3]}")
    return not bad and at == len(got)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/falcon-music")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--cpu", choices=("68030", "68060"), default="68030")
    ap.add_argument("--only", help="comma-separated capture names")
    ap.add_argument("--no-run", action="store_true", help="only compare an existing MUSOUT.BIN")
    args = ap.parse_args()
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    image = FLAT.read_bytes()
    import hashlib
    if hashlib.sha256(image).hexdigest() != FLAT_SHA256:
        sys.exit(f"{FLAT} is not the recorded image")
    captures = []
    for f in sorted(glob.glob(str(ROOT / "build" / "sound" / "*.json"))):
        name = pathlib.Path(f).stem
        if name.startswith("digital"):
            continue
        if args.only and name not in args.only.split(","):
            continue
        cap = json.loads(pathlib.Path(f).read_text())
        if cap.get("image_sha256") != FLAT_SHA256:
            sys.exit(f"{name}: captured against another image")
        if cap.get("mpu") or "speaker" in name or name in SKIP:
            print(f"skipped  {name}: {SKIP.get(name, 'MPU-401' if cap.get('mpu') else 'PC speaker')}")
            continue
        captures.append((name, cap))
    script, expect = build_script(captures, image)
    if not args.no_run:
        (out / "MUSIC.SCR").write_bytes(script)
        (out / "MUSTAB.BIN").write_bytes(image[MUS_BASE:MUS_END])
        build(out, args.cpu)
        seconds, exe = hatari(out, args.timeout, args.cpu)
        print(f"Hatari ({exe}) ran {seconds:.0f} s, {args.cpu}")
    if not (out / "MUSOUT.BIN").exists():
        sys.exit("the test program wrote no MUSOUT.BIN (see hatari-stdout.txt / hatari.log)")
    ok = compare(out, expect)
    print("RESULT:", "every op identical" if ok else "DIFFERENCES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
