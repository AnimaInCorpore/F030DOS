#!/bin/bash
# Run the CPU-only attract milestone in Hatari as a Falcon030.
#
# --memsize 14 IS the target, not a development convenience. The Falcon030
# shipped as 1, 4 or 14 MB and this port targets the 14 MB machine: BSS is
# 4.45 MB, mostly the two 1024x1024 maps at 2 MB, the sprite banks, the sky's
# 512 strips and the resource staging buffer. Measured 2026-08-17, a 4 MB
# machine completes its memory test and then never starts the program.
set -e

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

TARGET_CPU=${TARGET_CPU:-68030}
case "$TARGET_CPU" in
    68030) CPU_LEVEL=3; DEFAULT_PRG=release/comanche.tos
           DEFAULT_TOS="$ROOT/tools/toolchain/tos402.rom" ;;
    68060) CPU_LEVEL=6; DEFAULT_PRG=release/68060/comanche.tos
           DEFAULT_TOS="$ROOT/../F030Arcade/third_party/tos/etos512de.img" ;;
    *) echo "error: TARGET_CPU must be 68030 or 68060" >&2; exit 1 ;;
esac

export PATH="/c/msys64/ucrt64/bin:$PATH"

# cygpath only exists under MSYS2/Cygwin. Elsewhere the path is already
# native, so pass it through - without this the interactive run cannot start
# outside Windows at all, which is the whole point of watching the game.
to_host_path() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi
}

if [ -z "${HATARI:-}" ]; then
    if [ "$(uname -s)" = "Darwin" ] && command -v hatari >/dev/null 2>&1; then
        HATARI=$(command -v hatari)
    else
        HATARI="$ROOT/tools/toolchain/hatari.exe"
    fi
fi
TOS=${TOS:-$DEFAULT_TOS}

[ -x "$HATARI" ] || { echo "error: hatari not found at $HATARI" >&2; exit 1; }
[ -f "$TOS" ]    || { echo "error: TOS rom not found at $TOS" >&2; exit 1; }

PRG=${1:-$DEFAULT_PRG}
[ -f "$PRG" ] || { echo "error: $PRG not built - run tools/build-run.sh" >&2; exit 1; }

PRG_DIR=$(cd -- "$(dirname -- "$PRG")" && pwd)
PRG_NAME=$(basename -- "$PRG")

# TOS boots C:\AUTO\*.PRG before the program named on the command line, and
# a program that never returns means the one named here never runs at all. A
# stale release/AUTO/GAME.PRG did exactly that: every capture taken with it in
# place showed that old build, byte-identical whatever had been rebuilt.
if [ -n "$(ls -A "$PRG_DIR/AUTO" 2>/dev/null)" ]; then
    echo "error: $PRG_DIR/AUTO is not empty - TOS would boot it instead of $PRG_NAME" >&2
    exit 1
fi

# Mount the program directory explicitly and use Hatari's in-emulation path.
# This avoids relying on positional-argument auto-detection, which can leave
# TOS at the desktop with some Windows Hatari builds.
"$HATARI" --memsize 14 --tos "$(to_host_path "$TOS")" --patch-tos true \
          --frameskips 0 --monitor rgb --machine falcon --dsp off \
          --cpulevel "$CPU_LEVEL" --fpu none \
          --harddrive "$(to_host_path "$PRG_DIR")" \
          --auto "C:\\$PRG_NAME"
