#!/usr/bin/env python3
"""Check the Falcon output path of src/sound.s (DMA ring, VBL refill, resampler) in Hatari.

N/A - target artefact: a test driver, no DOS routine.
Record: analysis/functions/sound-falcon.md#verification

tools/sound-dma-test.s brings the digital layer up the way the game does
(COMANCHE.CFG, SND1/SPEAK banks, the Sound Loud radio), runs a timeline of
effects over 600 VBLs and logs every byte the refill writes to the ring. Hatari
records its own audio output to a WAV (control fifo: hatari-path soundout,
hatari-shortcut recsound). This script then checks

  1. the refill: underruns, bytes made, the lead it kept;
  2. the ring: from the request of the explosion on, the ring holds exactly what
     the documented resampler produces from the mixer bytes of jsComanche/
     dos-sound.js (the mixer is proven against DOS by check-falcon-sound.py);
  3. the output: the WAV Hatari played is not silent, its activity follows the
     ring's (correlation of the 100 ms RMS series), and the explosion lasts as
     long in the WAV as in the ring.

Usage: python3 tools/check-falcon-dma.py [--out build/falcon-dma]
"""
import argparse
import math
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import time
import wave

ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "extracted" / "comanche_hdd"
RS_STEP = 59238
RATE = 25175000 / 2048          # 12,292.48 Hz


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


def build(out):
    vasm = tool("VASM", "vasmm68k_mot_mac", "vasmm68k_mot.exe")
    vlink = tool("VLINK", "vlink_mac", "vlink.exe")
    objs = []
    for src in ("tools/sound-dma-test.s", "src/sound.s", "src/krl.s"):
        obj = out / (pathlib.Path(src).stem + ".o")
        run([vasm, str(ROOT / src), "-I", str(ROOT / "src"), "-quiet", "-Felf", "-m68030",
             "-DTARGET_CPU=68030", "-o", str(obj)])
        objs.append(str(obj))
    run([vlink, *objs, "-q", "-Rstd", "-b", "ataritos", "-tos-flags", "1", "-e", "_main",
         "-o", str(out / "DMATEST.TOS")])


def fifo_send(path, line):
    fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
    try:
        os.write(fd, (line + "\n").encode())
    finally:
        os.close(fd)


def hatari(out, timeout):
    for name in ("DMASTAT.TXT", "DMARING.BIN", "DMARIN2.BIN", "SNDDONE.TXT", "dma.wav", "ctl.fifo"):
        (out / name).unlink(missing_ok=True)
    for f in ("SND1.RLE", "SPEAK1.RLE", "SPEAK0.RLE", "COMANCHE.CFG"):
        shutil.copy(ASSETS / f, out / f)
    tos = os.environ.get("TOS", str(ROOT / "tools" / "toolchain" / "tos402.rom"))
    exe = shutil.which(os.environ.get("HATARI") or "hatari")
    if not exe:
        sys.exit("hatari not found; set HATARI")
    fifo = out / "ctl.fifo"
    cmd = [exe, "--memsize", "14", "--tos", tos, "--patch-tos", "true", "--mmu", "true",
           "--frameskips", "0", "--monitor", "rgb", "--machine", "falcon", "--dsp", "off",
           "--cpulevel", "3", "--fpu", "none", "--fast-boot", "true", "--sound", "44100",
           "--cpu-exact", "true", "--compatible", "true", "--confirm-quit", "off",
           "--disable-video", "on", "--harddrive", str(out), "--auto", "C:\\DMATEST.TOS",
           "--cmd-fifo", str(fifo), "--log-file", str(out / "hatari.log"), "--alert-level", "fatal"]
    started = time.time()
    with (out / "hatari-stdout.txt").open("w") as log:
        proc = subprocess.Popen(cmd, cwd=out, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT)
        try:
            while not fifo.exists() and time.time() - started < 30:
                time.sleep(0.1)
            time.sleep(0.5)
            fifo_send(fifo, f"hatari-path soundout {out / 'dma.wav'}")
            fifo_send(fifo, "hatari-shortcut recsound")
            while time.time() - started < timeout:
                if (out / "SNDDONE.TXT").exists():
                    time.sleep(1.0)
                    break
                if proc.poll() is not None:
                    break
                time.sleep(0.5)
            if proc.poll() is None:
                fifo_send(fifo, "hatari-shortcut recsound")
                time.sleep(1.0)
                fifo_send(fifo, "hatari-shortcut quit")
                try:
                    proc.wait(15)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
    return time.time() - started


def model(stream, req_phase, req_have, count):
    """The resampler of src/sound.s over [0x80] * req_have + stream, from req_phase."""
    data = [0x80] * req_have + list(stream)
    out = []
    phase = req_phase
    while len(out) < count:
        i = phase >> 16
        if i + 1 >= len(data):
            break
        a, c = data[i], data[i + 1]
        f = (phase & 0xFFFF) >> 1
        out.append(((a + (((c - a) * f) >> 15)) & 0xFF) ^ 0x80)
        phase += RS_STEP
    return bytes(out)


def rms_series(samples, rate, window=0.1):
    n = int(rate * window)
    out = []
    for i in range(0, len(samples) - n + 1, n):
        seg = samples[i:i + n]
        out.append(math.sqrt(sum(x * x for x in seg) / n))
    return out


def pearson(a, b):
    n = min(len(a), len(b))
    if n < 3:
        return 0.0
    a, b = a[:n], b[:n]
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if sa == 0 or sb == 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def active_span(samples, threshold):
    first = next((i for i, x in enumerate(samples) if abs(x) > threshold), None)
    if first is None:
        return None
    last = len(samples) - 1 - next(i for i, x in enumerate(reversed(samples)) if abs(x) > threshold)
    return first, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/falcon-dma")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--no-run", action="store_true")
    args = ap.parse_args()
    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.no_run:
        build(out)
        print(f"Hatari ran {hatari(out, args.timeout):.0f} s")
    for needed in ("DMASTAT.TXT", "DMARING.BIN"):
        if not (out / needed).exists():
            sys.exit(f"missing {needed}: the test program did not finish (see hatari-stdout.txt)")
    stat = struct.unpack(">16I", (out / "DMASTAT.TXT").read_bytes()[:64])
    (refills, under, made, vbls, loglen, digital, req_phase, req_have, req_wr, v_off, v_rotor, v_voice,
     w_l0, w_l1, w_s0, w_s1) = stat
    log = (out / "DMARING.BIN").read_bytes()
    log2 = (out / "DMARIN2.BIN").read_bytes()
    ok = True
    print(f"refills {refills}, underruns {under}, bytes rendered {made}, VBLs {vbls}, "
          f"ring log {loglen} bytes, digital flag {digital}")
    print(f"CPU cost of the refill (a fixed workload, in VBLs): mixer off {v_off}, rotor {v_rotor} "
          f"(+{100 * (v_rotor - v_off) / v_off:.1f} %), rotor and voice {v_voice} (+{100 * (v_voice - v_off) / v_off:.1f} %)")
    print(f"explosion requested at ring byte {req_wr} (resampler phase {req_phase:#x}, {req_have} buffered)")
    if not digital:
        print("FAIL: snd_init did not enable the digital layer"); ok = False
    if under:
        print(f"FAIL: {under} underruns"); ok = False
    # 2. the ring against the model
    run([ "node", str(ROOT / "tools" / "js-sound-stream.js"), str(out / "expl.bin"), "40"])
    stream = (out / "expl.bin").read_bytes()
    signed = [b - 256 if b > 127 else b for b in log]
    want = model(stream, req_phase, req_have, 40000)
    got = log[req_wr:req_wr + len(want)]
    same = sum(a == b for a, b in zip(got, want))
    print(f"ring vs model of the explosion: {same}/{len(want)} bytes identical "
          f"({len(want) / RATE:.2f} s of output)")
    if same != len(want) or len(got) != len(want):
        at = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), None)
        print(f"FAIL: first difference at {at}"); ok = False
    # Sound Loud against Sound Soft on the same rotor loop: the soft curve is the half-gain one
    def rms(a, b, source):
        seg = source[a:b]
        mean = sum(seg) / len(seg)
        return math.sqrt(sum((x - mean) ** 2 for x in seg) / len(seg))
    signed2 = [b - 256 if b > 127 else b for b in log2]
    loud, soft = rms(w_l0, w_l1, signed), rms(w_s0, w_s1, signed2)
    print(f"rotor RMS in the ring: Loud {loud:.2f}, Soft {soft:.2f} (ratio {soft / loud:.2f}, the curves' gain ratio is 0.5)")
    if not 0.4 < soft / loud < 0.6:
        print("FAIL: Sound Soft is not half of Sound Loud"); ok = False
    span = active_span(signed[req_wr:req_wr + len(want)], 0)
    print(f"explosion active in the ring for {(span[1] - span[0]) / RATE:.2f} s" if span else "FAIL: ring silent")
    # 3. Hatari's own output
    wav_path = out / "dma.wav"
    if not wav_path.exists() or wav_path.stat().st_size < 1000:
        print("FAIL: Hatari wrote no audio recording"); return 1
    with wave.open(str(wav_path)) as w:
        rate, ch, width, frames = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(frames)
    fmt = "<%dh" % (len(raw) // 2)
    pcm = struct.unpack(fmt, raw)
    left = pcm[0::ch]
    nz = sum(1 for x in left if x)
    peak = max(abs(x) for x in left)
    print(f"WAV: {rate} Hz, {ch} ch, {width * 8} bit, {frames / rate:.2f} s, {nz} non-zero frames, peak {peak}")
    if nz == 0:
        print("FAIL: the recording is silent"); ok = False
    ring_rms = rms_series(signed, RATE)
    wav_rms = rms_series(left, rate)
    best = (-2, 0)
    for lag in range(-len(ring_rms), len(wav_rms)):
        a = ring_rms[max(0, -lag):]
        b = wav_rms[max(0, lag):]
        if min(len(a), len(b)) < 30:
            continue
        r = pearson(a, b)
        if r > best[0]:
            best = (r, lag)
    print(f"activity correlation, ring vs WAV (100 ms RMS): {best[0]:.3f} at offset {best[1] * 0.1:.1f} s")
    if best[0] < 0.9:
        print("FAIL: the WAV does not follow the ring"); ok = False
    # the explosion's length in the WAV (the ring's active span, rescaled, starts where the series align)
    thr = max(40, peak // 100)
    segments = []
    run_start = last_hot = None
    for i, x in enumerate(left):
        if abs(x) > thr:
            if run_start is None:
                run_start = i
            elif i - last_hot > rate * 0.3:
                segments.append((run_start, last_hot))
                run_start = i
            last_hot = i
    if run_start is not None:
        segments.append((run_start, last_hot))
    print("WAV activity segments (threshold %d): " % thr
          + ", ".join(f"{a / rate:.2f}-{b / rate:.2f} s ({(b - a) / rate:.2f} s)" for a, b in segments))
    if span and segments:
        ring_len = (span[1] - span[0]) / RATE
        wav_len = (segments[0][1] - segments[0][0]) / rate
        sample_len = 27081 / (1e6 / 90)     # SND1 id 1: limit 27081 bytes at 11,111 Hz, step 0xFFFF
        print(f"explosion: {ring_len:.2f} s in the ring, {wav_len:.2f} s in the WAV, "
              f"{sample_len:.2f} s by the sample's own length")
        if abs(ring_len - sample_len) > 0.1 or abs(wav_len - sample_len) > 0.1:
            print("FAIL: the explosion's length is not the sample's"); ok = False
    # Sound Off at VBL 560 (the radio's MODE(0)) stops the DMA: the last second is silent
    tail = left[-rate:]
    tail_rms = math.sqrt(sum(x * x for x in tail) / len(tail))
    print(f"WAV, last second after Sound Off: RMS {tail_rms:.1f}")
    if tail_rms > 2:
        print("FAIL: the output goes on after MODE(0)"); ok = False
    print("RESULT:", "output path verified" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
