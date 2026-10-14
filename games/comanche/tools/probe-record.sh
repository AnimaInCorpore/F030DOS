#!/bin/bash
# Dump the frame at a replay RECORD rather than at a VBL.
#
#   bash tools/probe-record.sh <outdir> <K> [K ...]
#   PROBE_AT=demo_tick bash tools/probe-record.sh <outdir> <K> [K ...]
#
# For each K, breaks at PROBE_AT (default object_draw_pass) the first time
# demo_cursor = 13 + 8K - record K of the replay - and writes
# <outdir>/tp-K.bin, the 320x240 RGB565 buffer render_target points at, and
# <outdir>/tps-K.bin, ring_silhouette (250 rings x 192 bytes).
# At object_draw_pass the buffer holds the sky and terrain alone; at
# demo_tick it holds the previous frame, composed.
#
# Use it to compare two builds whose speed differs. The replay advances one
# record per rendered frame, so a faster build shows a different game frame
# at any given VBL and tools/grab-frames.sh compares unrelated pictures. The
# record is the game's own clock (see docs/CROSS-PROJECT.md §7).
#
# Two passes, because Hatari's savebin cannot dereference render_target.
# Symbols load at VBL 600, after GEMDOS has started the program; before that
# the debugger has no basepage to read them against.
#
# N/A - target artefact: emulator harness, no DOS counterpart.
set -e

OUT=${1:?usage: probe-record.sh <outdir> <K> [K ...]}
shift
KS=("$@")
[ ${#KS[@]} -gt 0 ] || { echo "no records given" >&2; exit 1; }
[ ${#KS[@]} -le 14 ] || { echo "at most 14 records per run" >&2; exit 1; }
AT=${PROBE_AT:-object_draw_pass}

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
to_host_path() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}
if [ -n "$(ls -A "release/AUTO" 2>/dev/null)" ]; then
    echo "error: release/AUTO is not empty - TOS would boot it instead of comanche_d.tos" >&2
    exit 1
fi
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

run() {
    printf 'logfile probe-log.txt\nb VBL = 600 :once :quiet :file probe-init.ini\n' \
        > release/dbg.ini
    (cd release && timeout -k 10 1500 "$HATARI" \
        --memsize 14 --tos "$(to_host_path "$TOS")" \
        --patch-tos true --frameskips 0 --monitor rgb \
        --machine falcon --dsp off --fast-boot true --sound off \
        --fast-forward true --cpu-exact true --compatible true \
        --confirm-quit off --disable-video on --run-vbls 60000 \
        --parse dbg.ini --log-file hatari.log --alert-level fatal \
        comanche_d.tos </dev/null >probe-stdout.txt 2>&1) || true
}

write_init() {
    {
        echo "symbols comanche_d.tos"
        local i=0
        for k in "${KS[@]}"; do
            echo "b pc = $AT && (demo_cursor).l = $((13 + 8 * k)) :once :file probe$i.ini"
            i=$((i + 1))
        done
        echo "cont"
    } > release/probe-init.ini
}

n=${#KS[@]}
last() { [ "$1" -eq $((n - 1)) ] && echo quit || echo cont; }

write_init
i=0
for k in "${KS[@]}"; do
    { echo "e (render_target).l"; last $i; } > release/probe$i.ini
    i=$((i + 1))
done
run
mapfile -t ADDR < <(grep -o 'value at (\$[0-9a-f]*).l = \$[0-9a-f]*' \
    release/probe-stdout.txt | sed 's/.*= \$//')
if [ ${#ADDR[@]} -ne $n ]; then
    echo "pass 1 reached ${#ADDR[@]} of $n records" >&2
    exit 1
fi

write_init
i=0
for k in "${KS[@]}"; do
    {
        echo "savebin tp-$k.bin \$${ADDR[$i]} 153600"
        echo "savebin tps-$k.bin ring_silhouette 48000"
        last $i
    } > release/probe$i.ini
    i=$((i + 1))
done
rm -f release/tp-*.bin release/tps-*.bin
run
mv release/tp-*.bin release/tps-*.bin "$OUT"/
echo "wrote $((2 * n)) dumps to $OUT"
