#!/bin/bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VBL=${1:-800}
OUT=${2:-$ROOT/build/frame.png}
HATARI=${HATARI:-hatari}
TOS=${TOS:-$ROOT/../F030Arcade/third_party/tos/tos404.img}
MEMSIZE=${MEMSIZE:-14}
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
rm -f por-grab.log frame.bin frame-ram.bin
cat > grab.ini <<EOF
logfile por-grab.log
b VBL = $VBL :once :file por-read-base.ini
EOF
cat > por-read-base.ini <<EOF
m \$ffff8201 1
m \$ffff8203 1
m \$ffff820d 1
m \$70 4
savebin frame-ram.bin \$0 \$$RAM_DUMP_HEX
quit
EOF

timeout -k 5 $((30 + VBL / 20)) "$HATARI" \
    --memsize "$MEMSIZE" --tos "$(to_host_path "$TOS")" --fast-boot true \
    --cpu-exact true --compatible true --patch-tos true --frameskips 0 \
    --monitor rgb --machine falcon --confirm-quit off --mmu true --fast-forward true \
    --sound off --disable-video on --run-vbls $((VBL + 50)) \
    --parse grab.ini --log-file por-hatari.log por.tos >/dev/null 2>&1 || true

BASE=$(sed -n 's/.*FFFF820[13D]: \([0-9a-f][0-9a-f]\).*/\1/p' por-grab.log | tr -d '\n')
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
TMP_PPM="$ROOT/build/.por-rgb565-frame.ppm"
python3 "$ROOT/tools/rgb565_to_ppm.py" frame.bin "$TMP_PPM"
magick "$TMP_PPM" "$OUT"
rm -f "$TMP_PPM"
echo "wrote $OUT"
