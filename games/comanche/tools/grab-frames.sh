#!/bin/bash
# Headless Hatari capture of MANY frames from one run.
#
#   bash tools/grab-frames.sh <outdir> <vbl> [vbl ...]
#
# grab-frame.sh costs two full Hatari runs per frame, and the attract cycle
# only starts around VBL 1200 - watching it one frame at a time is minutes
# each and the frames do not even come from the same run. This keeps the two
# passes but breaks N times inside them: pass 1 reads the Videl base at every
# requested VBL, pass 2 dumps each of those addresses. The cost of the whole
# sequence is the cost of its last frame.
#
# Emulation is deterministic, so the address read at VBL n in pass 1 is the
# buffer being displayed at VBL n in pass 2.
set -e

OUTDIR=${1:?usage: grab-frames.sh <outdir> <vbl> [vbl ...]}
shift
VBLS=("$@")
[ ${#VBLS[@]} -gt 0 ] || { echo "no VBLs given" >&2; exit 1; }
# Hatari keeps at most 16 conditional breakpoints. Past that it accepts the
# commands, fires none of them, and writes an empty log - so pass 1 reads zero
# display bases and the failure looks like a capture bug rather than a limit.
# Ask for a sweep in batches of 16 instead.
if [ ${#VBLS[@]} -gt 16 ]; then
    echo "error: ${#VBLS[@]} VBLs requested; Hatari allows 16 breakpoints." >&2
    echo "       split the sweep into batches of 16 or fewer." >&2
    exit 1
fi

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

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

mkdir -p "$OUTDIR" build

# TOS boots C:\AUTO\*.PRG before the program named on the command line, and
# a program that never returns means the one named here never runs at all. A
# stale release/AUTO/GAME.PRG did exactly that: every capture taken with it in
# place showed that old build, byte-identical whatever had been rebuilt.
if [ -n "$(ls -A "release/AUTO" 2>/dev/null)" ]; then
    echo "error: release/AUTO is not empty - TOS would boot it instead of comanche.tos" >&2
    exit 1
fi

LAST=${VBLS[${#VBLS[@]}-1]}
TIMEOUT=$((120 + LAST / 30))

to_host_path() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

run_hatari() {
    (cd release && timeout -k 10 $TIMEOUT "$HATARI" \
        --memsize 14 --tos "$(to_host_path "$TOS")" \
        --patch-tos true --frameskips 0 --monitor rgb \
        --machine falcon --dsp off --fast-boot true --sound off \
        --fast-forward true \
        --cpu-exact true --compatible true \
        --confirm-quit off --disable-video on --run-vbls $((LAST + 200)) \
        --parse dbg.ini --log-file hatari.log --alert-level fatal \
        comanche.tos </dev/null >/dev/null 2>&1) || true
}

# Every breakpoint script must hand control back, or Hatari sits at the
# interactive prompt and the run looks like a hang. Only the last one quits.
write_breakpoints() {
    : > release/dbg.ini
    echo "logfile comanche-dbg.txt" >> release/dbg.ini
    local i=0
    for v in "${VBLS[@]}"; do
        echo "b VBL = $v :once :file g$i.ini" >> release/dbg.ini
        i=$((i + 1))
    done
}

# GRAB_SETUP: debugger commands run at the FIRST breakpoint of both passes,
# before anything is read. This is how a capture reaches a state the program
# only enters on input the headless harness cannot send - the options bar, a
# paused mission, a menu page. Run identically in both passes, so the address
# pass 1 reads is still the buffer pass 2 dumps.
#
#   GRAB_SETUP=$'symbols comanche_d.tos\nw menu_open 0 1' bash tools/grab-frames.sh ...
# GRAB_SETUP2 does the same at the SECOND breakpoint, for state the program
# must already be running in before the poke means anything - a keypress into
# a menu that has not drawn itself yet is swallowed. GRAB_SETUP3 is the THIRD,
# which a multi-step UI needs: reaching the mission screen is an any-key out of
# the attract and then two separate Returns, and delivering the two Returns as
# one held key runs the selection straight past the screen being captured.
# Write key edges in HEX, with a '$' on every byte. Hatari's memwrite takes
# DECIMAL byte values, so `w input_pending 20 00` writes 0x1400 - bits 10 and
# 12 - and the Return you meant (bit 13, 0x2000) never arrives. This cost four
# full capture runs to find, because two of the three pokes in the walk below
# happen to survive the mistake and hide it: 08 is 8 in either base, and 80
# becomes 0x50, which is still nonzero and so still trips the attract's
# any-key exit. Only the Return failed, which reads as a bug in the menu.
# Write `w input_pending $20 $00`.
#
# GRAB_SETUP4 is the FOURTH, and it exists for the same reason the third does.
# Once the campaign screen lists more than one campaign there is a selection to
# move before the second Return means anything, so reaching the SECOND
# campaign's missions is four steps, not three.
emit_setup() {
    if [ "$1" -eq 0 ] && [ -n "${GRAB_SETUP:-}" ]; then
        printf '%s\n' "$GRAB_SETUP"
    fi
    if [ "$1" -eq 1 ] && [ -n "${GRAB_SETUP2:-}" ]; then
        printf '%s\n' "$GRAB_SETUP2"
    fi
    if [ "$1" -eq 2 ] && [ -n "${GRAB_SETUP3:-}" ]; then
        printf '%s\n' "$GRAB_SETUP3"
    fi
    if [ "$1" -eq 3 ] && [ -n "${GRAB_SETUP4:-}" ]; then
        printf '%s\n' "$GRAB_SETUP4"
    fi
}

i=0
for v in "${VBLS[@]}"; do
    {
        emit_setup $i
        echo "m \$ffff8201 1"
        echo "m \$ffff8203 1"
        echo "m \$ffff820d 1"
        if [ $i -eq $((${#VBLS[@]} - 1)) ]; then echo "quit"; else echo "cont"; fi
    } > "release/g$i.ini"
    i=$((i + 1))
done
write_breakpoints

rm -f release/comanche-dbg.txt
echo "pass 1: reading ${#VBLS[@]} display bases..."
run_hatari

# No mapfile: the Bash here is 3.2, where it does not exist.
ADDRS=()
while IFS= read -r line; do
    ADDRS+=("$line")
done < <(awk -F': ' '/FFFF820[13D]/{printf "%s", substr($2,1,2); if (++n % 3 == 0) printf "\n"}' \
    release/comanche-dbg.txt | tr '[:upper:]' '[:lower:]')

if [ ${#ADDRS[@]} -ne ${#VBLS[@]} ]; then
    echo "expected ${#VBLS[@]} display bases, read ${#ADDRS[@]}" >&2
    tail -20 release/comanche-dbg.txt 2>/dev/null >&2 || true
    exit 1
fi

i=0
for v in "${VBLS[@]}"; do
    echo "  VBL $v -> \$${ADDRS[$i]}"
    {
        emit_setup $i
        echo "savebin f$i.bin \$${ADDRS[$i]} \$$(printf '%x' $FRAME_BYTES)"
        if [ $i -eq $((${#VBLS[@]} - 1)) ]; then echo "quit"; else echo "cont"; fi
    } > "release/g$i.ini"
    i=$((i + 1))
done
write_breakpoints

rm -f release/f*.bin
echo "pass 2: dumping frames..."
run_hatari

i=0
for v in "${VBLS[@]}"; do
    BIN="release/f$i.bin"
    [ -s "$BIN" ] || { echo "no frame dumped for VBL $v" >&2; exit 1; }
    OUT=$(printf '%s/vbl%05d.png' "$OUTDIR" "$v")
    node tools/fb2png.js "$BIN" build/frame.ppm $WIDTH $HEIGHT
    if [ -x "$MAGICK" ]; then
        "$MAGICK" build/frame.ppm "$OUT"
        echo "wrote $OUT"
    else
        cp build/frame.ppm "${OUT%.png}.ppm"
        echo "wrote ${OUT%.png}.ppm (no ImageMagick)"
    fi
    i=$((i + 1))
done
