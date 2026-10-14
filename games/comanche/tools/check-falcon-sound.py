#!/usr/bin/env python3
"""Check the Falcon digital mixer (src/sound.s) byte for byte against the original.

N/A - target artefact: a test driver, no DOS routine.
Record: analysis/functions/sound-falcon.md#verification

What runs: tools/sound-mixer-test.s is assembled with src/sound.s and src/krl.s
into a stand-alone TOS program. It loads the three sample banks the way the game
does (src/sound.s snd_banks_load), interprets a script of calls to the same entry
points the game uses (snd_fx, snd_speech_a/b, snd_voice, snd_reset, snd_rate,
snd_fill) and writes every byte the mixer produces to SNDOUT.BIN, under Hatari
(Falcon, 68030, TOS 4.02, cycle exact). tools/gen-falcon-sound-script.js writes
the script and the expected bytes:

  dos     the mixed bytes of the original, captured on MS-DOS 6.22 under QEMU
          (build/sound/digital-*.json, work/trace_sound_writes.py), each capture
          played twice - with the capture's own 0x800-byte fills and with every
          fill cut into pieces of unequal size - plus the two transfer curves
          against the executable's image (00004A0A, 00004C0A);
  js      random call sequences on jsComanche/dos-sound.js, which
          tools/check-js-sound.js holds identical to the original on the same
          captures.

Usage: python3 tools/check-falcon-sound.py [--out build/falcon-sound] [--random N]
                                           [--seed N] [--cpu 68030|68060] [--no-run]
Exits 0 only if every span matches.
"""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "extracted" / "comanche_hdd"


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


def build(out, cpu):
    vasm = tool("VASM", "vasmm68k_mot_mac", "vasmm68k_mot.exe")
    vlink = tool("VLINK", "vlink_mac", "vlink.exe")
    objs = []
    for src in ("tools/sound-mixer-test.s", "src/sound.s", "src/krl.s"):
        obj = out / (pathlib.Path(src).stem + ".o")
        run([vasm, str(ROOT / src), "-I", str(ROOT / "src"), "-quiet", "-Felf", f"-m{cpu}",
             f"-DTARGET_CPU={cpu}", "-o", str(obj)])
        objs.append(str(obj))
    run([vlink, *objs, "-q", "-Rstd", "-b", "ataritos", "-tos-flags", "1", "-e", "_main",
         "-o", str(out / "SNDTEST.TOS")])


def hatari(out, timeout, cpu):
    for name in ("SNDOUT.BIN", "SNDDONE.TXT"):
        (out / name).unlink(missing_ok=True)
    for bank in ("SND1.RLE", "SPEAK1.RLE", "SPEAK0.RLE"):
        shutil.copy(ASSETS / bank, out / bank)
    # the 68060 image runs on the TOS the 060 build is run with (tools/run.sh)
    default_tos = ROOT / "tools" / "toolchain" / "tos402.rom"
    if cpu == "68060":
        default_tos = ROOT.parent / "F030Arcade" / "third_party" / "tos" / "etos512de.img"
    tos = os.environ.get("TOS", str(default_tos))
    exe = shutil.which(os.environ.get("HATARI") or "hatari")
    if not exe:
        sys.exit("hatari not found; set HATARI")
    cmd = [exe, "--memsize", "14", "--tos", tos, "--patch-tos", "true", "--mmu", "true",
           "--frameskips", "0", "--monitor", "rgb", "--machine", "falcon", "--dsp", "off",
           "--cpulevel", "6" if cpu == "68060" else "3", "--fpu", "none", "--fast-boot", "true", "--sound", "off",
           "--fast-forward", "true", "--cpu-exact", "true", "--compatible", "true",
           "--confirm-quit", "off", "--disable-video", "on", "--harddrive", str(out),
           "--auto", "C:\\SNDTEST.TOS", "--log-file", str(out / "hatari.log"),
           "--alert-level", "fatal"]
    started = time.time()
    with (out / "hatari-stdout.txt").open("w") as log:
        proc = subprocess.Popen(cmd, cwd=out, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT)
        try:
            while time.time() - started < timeout:
                if (out / "SNDDONE.TXT").exists():
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
    return time.time() - started


def compare(out):
    got = (out / "SNDOUT.BIN").read_bytes()
    want = (out / "expected.bin").read_bytes()
    spans = json.loads((out / "manifest.json").read_text())
    groups = {}
    bad = []
    if len(got) != len(want):
        print(f"length: the program wrote {len(got)} bytes, {len(want)} expected")
    for s in spans:
        a = got[s["offset"]:s["offset"] + s["length"]]
        b = want[s["offset"]:s["offset"] + s["length"]]
        key = (s["source"], s["name"].split(" fill ")[0].split(" resample ")[0])
        g = groups.setdefault(key, [0, 0, 0, 0])
        g[1] += s["length"]
        g[3] += 1
        same = sum(x == y for x, y in zip(a, b)) if len(a) == len(b) else 0
        g[0] += same
        if len(a) == len(b) and same == len(b):
            g[2] += 1
        else:
            bad.append((s, a, b))
    print(f"{'scenario':42} {'source':6} {'bytes':>20} {'spans':>12}")
    total_bytes = total_match = total_spans = total_ok = 0
    for (source, name), g in groups.items():
        print(f"{name:42} {source:6} {g[0]:>9}/{g[1]:<9} {g[2]:>5}/{g[3]:<5}")
        total_match += g[0]; total_bytes += g[1]; total_ok += g[2]; total_spans += g[3]
    print(f"{'TOTAL':42} {'':6} {total_match:>9}/{total_bytes:<9} {total_ok:>5}/{total_spans:<5}")
    for s, a, b in bad[:5]:
        at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        print(f"MISMATCH {s['name']} ({s['source']}): first difference at byte {at}: "
              f"got {a[at:at + 8].hex()} want {b[at:at + 8].hex()}")
    return total_match == total_bytes and len(got) == len(want) and not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/falcon-sound")
    ap.add_argument("--random", type=int, default=2)
    ap.add_argument("--seed", type=int, default=20261007)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--cpu", choices=("68030", "68060"), default="68030",
                    help="the CPU the test program is built for and run on (default 68030)")
    ap.add_argument("--no-run", action="store_true", help="only compare an existing SNDOUT.BIN")
    args = ap.parse_args()
    out = (ROOT / args.out).resolve()
    if not args.no_run:
        out.mkdir(parents=True, exist_ok=True)
        print(run(["node", str(ROOT / "tools" / "gen-falcon-sound-script.js"), str(out),
                   "--random", str(args.random), "--seed", str(args.seed)]).strip())
        build(out, args.cpu)
        seconds = hatari(out, args.timeout, args.cpu)
        print(f"Hatari ran {seconds:.0f} s")
    if not (out / "SNDOUT.BIN").exists():
        sys.exit("the test program wrote no SNDOUT.BIN (see hatari-stdout.txt / hatari.log)")
    ok = compare(out)
    print("RESULT:", "every byte identical" if ok else "DIFFERENCES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
