#!/usr/bin/env bash
# Assemble the WC1 DSP56001 C2P transport worker to release/WC1C2P.LOD.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
DOSBOX=${DOSBOX:-$(command -v dosbox-staging || command -v dosbox || true)}
ASM56K=${ASM56K:-"$ROOT/../F030Comanche/tools/toolchain/asm56k"}
BUILD="$ROOT/build/dsp-c2p"

[ -n "$DOSBOX" ] && [ -x "$DOSBOX" ] || {
    echo "error: DSP build needs dosbox-staging or dosbox (set DOSBOX=...)" >&2
    exit 1
}
[ -d "$ASM56K" ] || {
    echo "error: ASM56000 tools not found: $ASM56K" >&2
    exit 1
}

mkdir -p "$BUILD" "$ROOT/release"
rm -f "$BUILD/WC1C2P.LOD" "$BUILD/WC1C2P.LST" "$BUILD/WC1C2P.CLD"
cp "$ROOT/src/dsp/wc1c2p.asm" "$BUILD/WC1C2P.ASM"
cp "$ROOT/src/dsp/ioequ.inc" "$ROOT/src/dsp/c2pproto.inc" "$BUILD/"
cp "$ASM56K/ASM56000.EXE" "$ASM56K/CLDLOD.EXE" "$ASM56K/DOS4GW.EXE" "$BUILD/"

cat > "$BUILD/BUILD.BAT" <<'EOF'
@ECHO OFF
ASM56000.EXE -q -a -bWC1C2P.CLD -z -lWC1C2P.LST WC1C2P.ASM
IF ERRORLEVEL 1 EXIT 1
CLDLOD.EXE WC1C2P.CLD > WC1C2P.LOD
EXIT
EOF

(cd "$BUILD" && "$DOSBOX" --noprimaryconf --set output=texture BUILD.BAT) \
    >/dev/null 2>&1 || true

[ -s "$BUILD/WC1C2P.LOD" ] || {
    echo "error: no WC1C2P.LOD produced; see $BUILD/WC1C2P.LST" >&2
    exit 1
}
ERRORS=$(sed -n 's/^\([0-9][0-9]*\)[[:space:]][[:space:]]*Errors[[:space:]]*$/\1/p' \
    "$BUILD/WC1C2P.LST" | tail -1)
[ "${ERRORS:-1}" = "0" ] || {
    echo "error: ASM56000 reported ${ERRORS:-?} error(s); see $BUILD/WC1C2P.LST" >&2
    exit 1
}

cp "$BUILD/WC1C2P.LOD" "$ROOT/release/WC1C2P.LOD"
echo "wrote release/WC1C2P.LOD ($(wc -c < "$ROOT/release/WC1C2P.LOD") bytes)"
