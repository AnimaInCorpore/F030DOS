#!/bin/bash
# Make the ORIGINAL write its own frames, so the port can be diffed against
# what COMANCHE.EXE actually draws.
#
#   bash tools/oracle-capture.sh [outdir] [seconds]
#
# The game already contains the writer: 000165FD dumps the visible page as a
# 328x240 PCX and increments the digits of the name at 000165F0, so successive
# calls give SNAP_001.PCX, SNAP_002.PCX and so on. What guarded it was the
# developer key gate at 000189C2, and driving that gate from the keyboard did
# not work - see the header of tools/compare-terrain.py for the twelve attempts
# and the two unsettled reasons.
#
# So this does not drive the gate, it removes it. Three conditional jumps stand
# between the gate's entry and the call:
#
#   000189C9  js 00018A05   Alt released    -> return
#   000189D2  js 000189EB   P released      -> skip
#   000189DB  je 000189EB   feature != 0xFF -> skip
#
# NOPping all three makes the writer fire every time the gate is reached, which
# is once per frame, and the incrementing name turns that into a numbered
# sequence of everything the original drew. That is a strictly better oracle
# than one keystroke-triggered shot: no timing, no parity, no key array.
#
# The patch is applied to a COPY of the unpacked executable on a scratch drive.
# Neither assets/ nor re/unpacked/ is written.
set -e

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# cygpath only exists under MSYS2/Cygwin. Elsewhere the path is already
# native, so pass it through - DOSBox is a native Windows binary and rejects
# the POSIX-style /c/... path Bash hands back from pwd.
to_host_path() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

OUTDIR=${1:-build/oracle}
SECONDS_TO_RUN=${2:-45}
# Write one frame in STRIDE. Every frame costs a 25 KB PCX and the game slows
# to a crawl under it: a 40s every-frame run never got past the first demo, so
# it never reached the pass that flies DEMO0 on the D1/C1 pair - the only map
# the port loads. The counter reuses the feature byte at 000265ED, which the
# gate patch has already made dead.
STRIDE=${3:-20}

ASSETS="$ROOT/assets/extracted/comanche_hdd"
EXE="$ROOT/re/unpacked/COMANCHE.UNPACKED.EXE"
[ -d "$ASSETS" ] || { echo "error: no game tree at $ASSETS" >&2; exit 1; }
[ -f "$EXE" ]    || { echo "error: no unpacked exe at $EXE" >&2; exit 1; }

# The Windows checkout ships dosbox-staging under tools/toolchain/dosbox/,
# next to the DLLs it needs - tools/toolchain/dosbox.exe is a bare copy with
# no siblings and fails to load. Prefer the working bundled copy, then fall
# back to PATH for platforms (e.g. macOS via Homebrew) with no bundled binary.
if [ -z "${DOSBOX:-}" ]; then
    if [ -x "$ROOT/tools/toolchain/dosbox/dosbox.exe" ]; then
        DOSBOX="$ROOT/tools/toolchain/dosbox/dosbox.exe"
    else
        DOSBOX=$(command -v dosbox-staging || command -v dosbox || true)
    fi
fi
[ -n "$DOSBOX" ] || { echo "error: no dosbox found (set DOSBOX=...)" >&2; exit 1; }

CDRIVE="$ROOT/build/oracle-cdrive"
rm -rf "$CDRIVE" "$OUTDIR"
mkdir -p "$CDRIVE" "$OUTDIR"

# The asset tree, minus its own executable: the patched one replaces it.
cp "$ASSETS"/* "$CDRIVE"/ 2>/dev/null || true
rm -f "$CDRIVE/COMANCHE.EXE"

# Image offsets in this repository count from the first byte after the MZ
# header, and the flat selector base is image offset 0x1700 - so a flat address
# F is at file offset headersize + 0x1700 + F. Getting that wrong by the
# 512-byte header is the mistake carve-flat.py warns about.
python3 - "$EXE" "$CDRIVE/COMANCHE.EXE" "$STRIDE" <<'PY'
import os, struct, sys
src, dst, stride = sys.argv[1], sys.argv[2], int(sys.argv[3])
exe = bytearray(open(src, 'rb').read())
base = struct.unpack_from("<H", exe, 8)[0] * 16 + 0x1700

# The 20 bytes from 000189C9 up to the call at 000189DD hold the three guards.
# Replace them with a countdown on the now-dead feature byte, so the writer
# fires once every STRIDE times the gate is reached instead of every time.
#
#   000189C9  FE 0D ED 65 02 00     dec  byte [000265ED]
#   000189CF  75 1A                 jne  000189EB        (skip this frame)
#   000189D1  C6 05 ED 65 02 00 nn  mov  byte [000265ED], STRIDE
#   000189D8  90 90 90 90 90        nop  x5              (fall into the call)
#   000189DD  E8 1B DC FF FF        call 000165FD        (untouched)
ORIGINAL = bytes.fromhex("783a"          # js  00018A05
                         "803d891a000000"  # cmp byte [00001A89], 0
                         "7817"            # js  000189EB
                         "803ded650200ff"  # cmp byte [000265ED], 0xFF
                         "740e")           # je  000189EB
off = base + 0x189C9
got = bytes(exe[off:off + len(ORIGINAL)])
if got != ORIGINAL:
    sys.exit(f"error: 000189C9 holds {got.hex()}, expected {ORIGINAL.hex()} - "
             "the executable is not the one this patch was measured against")
if not 1 <= stride <= 255:
    sys.exit("error: stride must be 1..255")

patch = (b'\xfe\x0d\xed\x65\x02\x00'
         b'\x75\x1a'
         b'\xc6\x05\xed\x65\x02\x00' + bytes([stride])
         + b'\x90' * 5)
assert len(patch) == len(ORIGINAL) == 20, (len(patch), len(ORIGINAL))
exe[off:off + len(patch)] = patch
print(f"  patched 000189C9: three guards -> countdown, one frame in {stride}")

# Force the attract pass counter to 0 so the cycle always flies DEMO0.SCR.
# 000056E3 loads [00019ED5], 000056E8 increments it and 000056EA masks it to
# 0..3; DEMO<pass>.SCR is what the pass then plays. The port replays DEMO0 on
# the D1/C1 pair and has no other terrain, so a comparison can only happen on
# pass 0 - and a 170s capture at stride 12 never reached it naturally, because
# the cycle starts at 1 and each pass costs two screens plus a full demo.
# inc al -> xor al,al leaves the mask a no-op and pins the pass at 0.
INC_AL = bytes.fromhex("fec0")
off = base + 0x56E8
got = bytes(exe[off:off + 2])
if got != INC_AL:
    sys.exit(f"error: 000056E8 holds {got.hex()}, expected {INC_AL.hex()}")
exe[off:off + 2] = bytes.fromhex("30c0")          # xor al, al
print("  patched 000056E8: inc al -> xor al,al   (attract pass pinned to 0)")

# PIN_CAMERA=1 freezes the viewpoint, so every captured frame is one known
# camera instead of a moment in a flight. Matching the two sides by time does
# not work - see PORTING-PLAN.md for the numbers that rule it out - and this
# removes the need to.
#
# 000194F7 accumulates the heading, 00019503 indexes the shared sine table at
# 00032120, and four sites integrate position from the pair: forward speed
# [00019CC8] against cos into [00019CD8] and against sin into [00019CD4], then
# lateral [00019CD0] against both. That is the whole of it - those two are the
# only sine-table consumers on the main path, the others being the rear-view
# block's own marcher at 0001B275 and the object movers.
#
# Freezing position alone was not enough and the reason is worth keeping: the
# view still changed across 47-83% of the terrain band, which looked like a
# camera moving hard and was in fact the helicopter DESCENDING. The HUD in the
# captures said so plainly - SPEED:192 altitude 084 in an early frame,
# SPEED:000 altitude 002 in a late one. The collective at 000193DA compares the
# demo's target against [00019D82] and climbs or sinks by a rate derived from
# the error, through 000193EF and 0001940C, and it flew the frozen helicopter
# into the ground. With those held too, the machine decelerates to SPEED:000,
# holds altitude 084, and frames 36-40 of a 40-frame capture are byte
# identical. That settled hover is the pinned viewpoint, and because position
# was frozen from the demo loader onward it is exactly the X and Y that
# compare-terrain.py --demo-camera prints.
FREEZE = [
    (0x194F7, "0105049d0100",   "heading accumulate"),
    (0x19528, "2915d89c0100",   "Y -= fwd*cos"),
    (0x19535, "0115d49c0100",   "X += fwd*sin"),
    (0x19542, "0115d49c0100",   "X += lat*cos"),
    (0x1954F, "0115d89c0100",   "Y += lat*sin"),
    (0x18F29, "8005fc9d010004", "altitude += 4"),
    (0x18FA6, "802dfc9d010001", "altitude -= 1"),
    # The collective, which is what actually flew the helicopter into the
    # ground on the first attempt: 000193DA compares the demo's target against
    # [00019D82] and then climbs or sinks by a rate derived from the error.
    # The two clamps behind them are NOPped as well, because with the
    # arithmetic gone their jae would run on a stale carry.
    (0x193EF, "0005fc9d0100",   "collective climb"),
    (0x193FB, "c605fc9d0100ff", "clamp to 0xFF"),
    (0x1940C, "2805fc9d0100",   "collective sink"),
    (0x19418, "c605fc9d010000", "clamp to 0"),
    (0x1943D, "a2fc9d0100",     "ground-collision altitude restore"),
    # The same collision path restores POSITION from [00019CDC]/[00019CE0] two
    # instructions earlier, and freezing only the altitude left those live. A
    # single ground contact then moves the camera somewhere the demo's start
    # record does not describe - which is invisible in the frame, because the
    # result is still plausible terrain on the right map.
    (0x19429, "a3d49c0100",     "ground-collision X restore"),
    (0x19433, "a3d89c0100",     "ground-collision Y restore"),
]
if os.environ.get("PIN_CAMERA", "0") != "0":
    for flat, hexbytes, what in FREEZE:
        want = bytes.fromhex(hexbytes)
        o = base + flat
        got = bytes(exe[o:o + len(want)])
        if got != want:
            sys.exit(f"error: {flat:08X} holds {got.hex()}, expected {want.hex()}")
        exe[o:o + len(want)] = b'\x90' * len(want)
    print(f"  patched {len(FREEZE)} sites: camera frozen at the demo start record")

# DUMP_BASE/DUMP_LEN: write a flat memory range to the snapshot file instead of
# the PCX header, which is how a BSS table gets out of the running original.
#
# The renderer's column mapping is not in the executable. 00007AA0 drives the
# terrain transfer entirely from per-column tables at 00032B20, 00034B20,
# 00038B20 and 0003AB20 plus the horizon array at 0003CB40, and the 207,648-
# byte flat content region ends at exactly 00032B20 - every one of them is BSS,
# built at runtime, and so is the column count at 00019E4C, which is zero in
# the image and written once at 00007145. That is why eight parameter fits
# against the terrain oracle each moved the mean and left the spread: they were
# fitting scalars to a mapping that is not in the file.
#
# The writer at 000165FD already creates a file, writes to it and closes it.
# Only the first write is retargeted - 0001664E's source and 00016653's count -
# so the dump lands at the head of the file and the untouched pixel loop
# appends its PCX data after it. Take the first DUMP_LEN bytes and ignore the
# rest; the file is not a PCX any more and is not meant to be.
#
# CX is 16-bit here, as it is in the game's own reader at 00015E23, so a
# request over 65535 would be truncated silently rather than refused.
dump_base = os.environ.get("DUMP_BASE", "")
if dump_base:
    dump_len = int(os.environ.get("DUMP_LEN", "0"), 0)
    dump_at = int(dump_base, 0)
    if not 1 <= dump_len <= 0xFFFF:
        sys.exit(f"error: DUMP_LEN must be 1..65535, got {dump_len}")

    SRC = bytes.fromhex("ba70650100")             # mov edx, 00016570
    o = base + 0x1664E
    got = bytes(exe[o:o + len(SRC)])
    if got != SRC:
        sys.exit(f"error: 0001664E holds {got.hex()}, expected {SRC.hex()}")
    exe[o:o + len(SRC)] = b'\xba' + struct.pack("<I", dump_at)

    CNT = bytes.fromhex("66b98000")               # mov cx, 0x0080
    o = base + 0x16653
    got = bytes(exe[o:o + len(CNT)])
    if got != CNT:
        sys.exit(f"error: 00016653 holds {got.hex()}, expected {CNT.hex()}")
    exe[o:o + len(CNT)] = b'\x66\xb9' + struct.pack("<H", dump_len)
    print(f"  patched 0001664E/00016653: snapshot writes "
          f"{dump_len} bytes from {dump_at:08X} instead of the PCX header")

open(dst, 'wb').write(exe)
PY

cat > "$CDRIVE/../oracle-run.conf" <<EOF
[sdl]
output = texture
fullscreen = false
[render]
aspect = false
glshader = none
[dosbox]
machine = svga_s3
memsize = 16
[cpu]
core = auto
cycles = fixed 20000
[mixer]
nosound = true
[autoexec]
mount c $(to_host_path "$CDRIVE")
c:
COMANCHE.EXE
exit
EOF

echo "running the original for ${SECONDS_TO_RUN}s..."
"$DOSBOX" --noprimaryconf --nolocalconf --conf "$CDRIVE/../oracle-run.conf" \
    >/dev/null 2>&1 &
DOSPID=$!
sleep "$SECONDS_TO_RUN"

# SIGTERM then SIGKILL, and never an unbounded wait. The macOS DOSBox does not
# always stop on SIGTERM, and the plain `wait` that used to follow this hung
# until the caller's own timeout killed the script - which happens AFTER the
# capture, so the run looked like a failure and left every snapshot stranded on
# the scratch drive with nothing copied out. Hatari behaves the same way here;
# see the note in tools/grab-frame.sh.
kill "$DOSPID" 2>/dev/null || true
for _ in $(seq 20); do
    kill -0 "$DOSPID" 2>/dev/null || break
    sleep 0.5
done
kill -9 "$DOSPID" 2>/dev/null || true
wait "$DOSPID" 2>/dev/null || true

shopt -s nullglob
SHOTS=("$CDRIVE"/SNAP_*.PCX "$CDRIVE"/snap_*.pcx)
if [ ${#SHOTS[@]} -eq 0 ]; then
    echo "no SNAP_*.PCX written - the gate patch did not fire" >&2
    exit 1
fi
for f in "${SHOTS[@]}"; do cp "$f" "$OUTDIR"/; done
echo "captured ${#SHOTS[@]} frames into $OUTDIR"
