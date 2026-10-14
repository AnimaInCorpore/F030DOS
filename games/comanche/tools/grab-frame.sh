#!/bin/bash
# Headless Hatari frame grab.
#
#   bash tools/grab-frame.sh [vbl] [out.png]
#
# Runs release/comanche.tos, breaks at a VBL count, reads the displayed buffer
# address out of the Videl base registers, dumps it and converts it to PNG.
#
# Two passes, because Hatari's savebin cannot dereference a pointer: the first
# reads the address, the second dumps from it. The address is stable for a
# given build but moves whenever the BSS layout changes, so it is never
# hard-coded.
set -e

# Runtime DTA loading happens before the first frame when release/ contains
# the installed terrain pair. 5000 leaves enough headroom for Hatari's GEMDOS
# disk emulation; a missing asset is an error, not a procedural scene.
VBL=${1:-5000}
OUT=${2:-build/frame.png}

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# The Hatari build is an MSYS2 UCRT64 one and will not even start without its
# runtime DLLs on PATH - it exits silently with status 0, writing no log at all.
export PATH="/c/msys64/ucrt64/bin:$PATH"

if [ -z "${HATARI:-}" ]; then
    if [ "$(uname -s)" = "Darwin" ] && command -v hatari >/dev/null 2>&1; then
        HATARI=$(command -v hatari)
    else
        HATARI="$ROOT/tools/toolchain/hatari.exe"
    fi
fi
TOS=${TOS:-"$ROOT/tools/toolchain/tos402.rom"}
if [ -z "${MAGICK:-}" ]; then
    MAGICK=$(command -v magick || true)
fi
MAGICK=${MAGICK:-/c/Program Files/ImageMagick-7.1.2-Q16-HDRI/magick.exe}

WIDTH=320
HEIGHT=240
FRAME_BYTES=$((WIDTH * HEIGHT * 2))

mkdir -p build

# TOS boots C:\AUTO\*.PRG before the program named on the command line, and
# a program that never returns means the one named here never runs at all. A
# stale release/AUTO/GAME.PRG did exactly that: every capture taken with it in
# place showed that old build, byte-identical whatever had been rebuilt.
if [ -n "$(ls -A "release/AUTO" 2>/dev/null)" ]; then
    echo "error: release/AUTO is not empty - TOS would boot it instead of comanche.tos" >&2
    exit 1
fi

# Hatari covers roughly 90 emulated VBLs per wall second here, so a fixed
# timeout silently truncated long runs and returned a stale or empty capture.
TIMEOUT=$((90 + VBL / 40))

# cygpath only exists under MSYS2/Cygwin. Elsewhere the path is already native,
# so pass it through - without this the capture cannot run outside Windows at
# all, which is the whole documented verification path for a Falcon change.
to_host_path() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

run_hatari() {
    # -k, because plain SIGTERM does not stop the macOS Hatari: runs were seen
    # still going 58 minutes after a 215-second timeout, and several of them at
    # once starve the machine badly enough that later captures time out too,
    # which reads as a flaky harness rather than as leftover processes.
    (cd release && timeout -k 10 $TIMEOUT "$HATARI" \
        --memsize 14 --tos "$(to_host_path "$TOS")" \
        --patch-tos true --frameskips 0 --monitor rgb \
        --machine falcon --dsp off --fast-boot true --sound off \
        --fast-forward true \
        --cpu-exact true --compatible true \
        --confirm-quit off --disable-video on --run-vbls $((VBL + 200)) \
        --parse dbg.ini --log-file hatari.log --alert-level fatal \
        comanche.tos </dev/null >/dev/null 2>&1) || true
}

cat > release/dbg.ini <<EOF
logfile comanche-dbg.txt
b VBL = $VBL :once :file grab.ini
EOF

# Pass 1: the VBL handler copies display_screen into the Videl base registers,
# so those three bytes are the address of the last completed frame.
cat > release/grab.ini <<'EOF'
m $ffff8201 1
m $ffff8203 1
m $ffff820d 1
quit
EOF

rm -f release/comanche-dbg.txt
run_hatari

ADDR=$(awk -F': ' '/FFFF820[13D]/{printf "%s", substr($2,1,2)}' release/comanche-dbg.txt | tr '[:upper:]' '[:lower:]')

if [ ${#ADDR} -ne 6 ]; then
    echo "could not read the Videl base (got '$ADDR') - did the program start?" >&2
    tail -20 release/comanche-dbg.txt 2>/dev/null >&2 || true
    exit 1
fi

echo "display buffer at \$$ADDR"

cat > release/grab.ini <<EOF
savebin frame.bin \$$ADDR \$$(printf '%x' $FRAME_BYTES)
quit
EOF

rm -f release/frame.bin
run_hatari

[ -s release/frame.bin ] || { echo "no frame dumped" >&2; exit 1; }

node tools/fb2png.js release/frame.bin build/frame.ppm $WIDTH $HEIGHT
if [ -x "$MAGICK" ]; then
    "$MAGICK" build/frame.ppm "$OUT"
    echo "wrote $OUT"
else
    echo "wrote build/frame.ppm (ImageMagick not found, no PNG conversion)"
fi
