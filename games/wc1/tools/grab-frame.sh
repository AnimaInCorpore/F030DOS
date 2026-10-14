#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VBL=${1:-800}
OUT=${2:-$ROOT/build/frame.png}
HATARI=${HATARI:-hatari}
TOS=${TOS:-$ROOT/../F030Arcade/third_party/tos/tos404.img}
MEMSIZE=${MEMSIZE:-14}
# Optional comma-separated Hatari input schedule. Key items are
# <absolute-vbl>:<keydown|keyup>:<ST-scancode>; mouse-button items are
# <absolute-vbl>:<leftdown|leftup>, and motion items are
# <absolute-vbl>:<mousemove>:<dx>:<dy>. The first automated flight capture
# uses the title's Escape key path followed by a button state plus mouse packet:
#   HATARI_INPUT_EVENTS='1200:keydown:0x01,1202:keyup:0x01,1600:leftdown,1602:mousemove:1:0,1620:leftup,1622:mousemove:1:0'
# The scheduler polls Hatari's debugger VBL value; it is intentionally not
# paced from host wall clock.  A scheduled capture disables fast-forward so
# the FIFO monitor has time to service each edge before the next VBL.
HATARI_KEY_EVENTS=${HATARI_KEY_EVENTS:-}
HATARI_INPUT_EVENTS=${HATARI_INPUT_EVENTS:-$HATARI_KEY_EVENTS}
RAM_BYTES=$((MEMSIZE * 1024 * 1024))
FRAME_BYTES=$((320 * 200 * 2))
# GEMDOS may place a 320x200 RGB565 ($1f400-byte) Mxalloc block in Falcon's final
# top-of-ST-RAM aperture. Dump a guard region as large as the RGB565 page so a
# valid Videl base near the top of configured ST-RAM can still be extracted;
# the screen range below is checked against this actual dump, never against an
# unresolved pointer.
RAM_GUARD_BYTES=$((FRAME_BYTES > 0x10000 ? FRAME_BYTES : 0x10000))
RAM_DUMP_BYTES=$((RAM_BYTES + RAM_GUARD_BYTES))
RAM_DUMP_HEX=$(printf '%x' "$RAM_DUMP_BYTES")
case "$OUT" in
    /*) ;;
    *) OUT="$ROOT/$OUT" ;;
esac
mkdir -p "$ROOT/build"

to_host_path() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

cd "$ROOT/release"
rm -f wc1-grab.log wc1-grab.out wc1-grab-input.log frame.bin frame-ram.bin
cat > grab.ini <<EOF
logfile wc1-grab.log
b VBL = $VBL :once :file wc1-read-base.ini
EOF
cat > wc1-read-base.ini <<EOF
m \$ffff8201 1
m \$ffff8203 1
m \$ffff820d 1
m \$70 4
r
info basepage
savebin frame-ram.bin \$0 \$$RAM_DUMP_HEX
quit
EOF

HATARI_ARGS=(
    --memsize "$MEMSIZE" --tos "$(to_host_path "$TOS")" --fast-boot true
    --cpu-exact true --compatible true --patch-tos true --frameskips 0
    --monitor rgb --machine falcon --confirm-quit off --mmu true
    --sound off --disable-video on --run-vbls $((VBL + 50))
    --parse grab.ini --log-file wc1-hatari.log
)

if [ -z "$HATARI_INPUT_EVENTS" ]; then
    HATARI_ARGS+=(--fast-forward true)
    timeout -k 5 $((30 + VBL / 20)) "$HATARI" \
        "${HATARI_ARGS[@]}" wc1.tos >wc1-grab.out 2>&1 || true
else
    FIFO="$ROOT/release/wc1-grab.fifo"
    rm -f "$FIFO"
    HATARI_ARGS+=(--cmd-fifo "$FIFO")
    # Input must be observed over actual emulated frames.  Fast-forward can
    # run past a pending FIFO query before the host has read its VBL result.
    timeout -k 5 $((45 + VBL / 20)) "$HATARI" \
        "${HATARI_ARGS[@]}" wc1.tos >wc1-grab.out 2>&1 &
    HATARI_PID=$!

    for _ in $(seq 1 200); do
        [ -p "$FIFO" ] && break
        kill -0 "$HATARI_PID" 2>/dev/null || break
        sleep 0.02
    done
    [ -p "$FIFO" ] || {
        wait "$HATARI_PID" 2>/dev/null || true
        echo "Hatari did not create its command FIFO" >&2
        exit 1
    }

    fifo_command() {
        # Hatari discards the remainder of a multi-command write after a bad
        # command.  Keep one command per write, including debugger queries.
        printf '%s\n' "$1" > "$FIFO"
    }

    current_vbl() {
        local start_line attempt value
        start_line=$(wc -l < wc1-grab.out)
        fifo_command "hatari-debug evaluate VBL"
        for attempt in $(seq 1 100); do
            value=$(tail -n "+$((start_line + 1))" wc1-grab.out 2>/dev/null \
                | sed -n 's/^= %.*#\([0-9][0-9]*\).*$/\1/p' | tail -n 1)
            if [ -n "$value" ]; then
                printf '%s\n' "$value"
                return 0
            fi
            kill -0 "$HATARI_PID" 2>/dev/null || return 1
            sleep 0.02
        done
        return 1
    }

    wait_for_vbl() {
        local wanted=$1 observed
        while :; do
            observed=$(current_vbl) || return 1
            [ "$observed" -ge "$wanted" ] && {
                printf '%s\n' "$observed"
                return 0
            }
            sleep 0.02
        done
    }

    IFS=',' read -r -a INPUT_EVENTS <<< "$HATARI_INPUT_EVENTS"
    previous_vbl=-1
    for event in "${INPUT_EVENTS[@]}"; do
        if [[ "$event" =~ ^([0-9]+):(keydown|keyup):(0x[0-9a-fA-F]{1,2})$ ]]; then
            event_vbl=${BASH_REMATCH[1]}
            event_action=${BASH_REMATCH[2]}
            event_scancode=${BASH_REMATCH[3]}
            event_command="hatari-event $event_action $event_scancode"
            event_label="$event_action $event_scancode"
        elif [[ "$event" =~ ^([0-9]+):(leftdown|leftup)$ ]]; then
            event_vbl=${BASH_REMATCH[1]}
            event_action=${BASH_REMATCH[2]}
            event_command="hatari-event $event_action"
            event_label="$event_action"
        elif [[ "$event" =~ ^([0-9]+):mousemove:([-+]?[0-9]+):([-+]?[0-9]+)$ ]]; then
            event_vbl=${BASH_REMATCH[1]}
            event_command="hatari-event mousemove ${BASH_REMATCH[2]} ${BASH_REMATCH[3]}"
            event_label="mousemove ${BASH_REMATCH[2]} ${BASH_REMATCH[3]}"
        else
            echo "invalid HATARI_INPUT_EVENTS item '$event'" >&2
            exit 1
        fi
        [ "$event_vbl" -gt "$previous_vbl" ] || {
            echo "HATARI_INPUT_EVENTS must use strictly increasing VBLs" >&2
            exit 1
        }
        observed=$(wait_for_vbl "$event_vbl") || {
            echo "Hatari stopped before scheduled VBL $event_vbl" >&2
            exit 1
        }
        fifo_command "$event_command"
        printf 'target_vbl=%s observed_vbl=%s event=%s\n' \
            "$event_vbl" "$observed" "$event_label" \
            >> wc1-grab-input.log
        previous_vbl=$event_vbl
        # Give the command FIFO a turn through Hatari's event loop before the
        # next debugger query; this is host I/O settling, not event timing.
        sleep 0.02
    done
    wait "$HATARI_PID" 2>/dev/null || true
fi

# The breakpoint in grab.ini performs the guest RAM dump and quits Hatari.
# Its non-zero timeout/quit status is deliberately not treated as a capture
# failure; the checks below validate the concrete dump instead.
:

BASE=$(sed -n 's/.*FFFF820[13D]: \([0-9a-f][0-9a-f]\).*/\1/p' wc1-grab.log | tr -d '\n')
[ "${#BASE}" -eq 6 ] || { echo "could not read Videl base (got '$BASE')" >&2; exit 1; }
echo "display buffer at \$$BASE"
BASE_OFFSET=$((16#$BASE))
[ "$BASE_OFFSET" -le "$((RAM_DUMP_BYTES - FRAME_BYTES))" ] || {
    echo "Videl base \$$BASE lies outside the ${RAM_DUMP_BYTES}-byte RAM dump" >&2
    exit 1
}
[ -s frame-ram.bin ] || { echo "no single-run RAM dump" >&2; exit 1; }
dd if=frame-ram.bin of=frame.bin bs=1 skip="$BASE_OFFSET" \
    count="$FRAME_BYTES" status=none
if [ "${KEEP_RAM_DUMP:-0}" != 1 ]; then
    rm -f frame-ram.bin
fi
[ -s frame.bin ] || { echo "no framebuffer extraction" >&2; exit 1; }
mkdir -p "$ROOT/build"
# VIDEL is now in 16-bit true-colour mode; decode the captured big-endian
# RGB565 words before ImageMagick writes PNG.
TMP_PPM="$ROOT/build/.wc1-rgb565-frame.ppm"
python3 "$ROOT/tools/rgb565_to_ppm.py" frame.bin "$TMP_PPM"
magick "$TMP_PPM" "$OUT"
rm -f "$TMP_PPM"
echo "wrote $OUT"
