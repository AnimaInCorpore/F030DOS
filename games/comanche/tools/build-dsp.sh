#!/bin/bash
# Assemble the Comanche DSP source into release/comanche.lod.
#
# ASM56000 is a DOS4GW program, so it runs under DOSBox and needs 8.3 names.
# DOSBox Staging installs outside PATH on Windows, hence the explicit default;
# override with DOSBOX=... when needed.
set -e

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

DOSBOX=${DOSBOX:-$(command -v dosbox-x || command -v dosbox-staging || command -v dosbox || true)}
if [ -z "$DOSBOX" ]; then
    DOSBOX="$ROOT/tools/toolchain/dosbox/dosbox.exe"
fi
[ -x "$DOSBOX" ] || { echo "error: no dosbox found (set DOSBOX=...)" >&2; exit 1; }

ASM56K=${ASM56K:-"$ROOT/tools/toolchain/asm56k"}
[ -d "$ASM56K" ] || { echo "error: asm56k not found at $ASM56K" >&2; exit 1; }

DSP_SOURCE=${DSP_SOURCE:-src/dsp/comanche.asm}
[ -f "$DSP_SOURCE" ] || { echo "error: DSP source not found at $DSP_SOURCE" >&2; exit 1; }

BUILD="$ROOT/build/dsp"
rm -rf "$BUILD"
mkdir -p "$BUILD" release

# The depth and row tables are derived from proto.inc, so they are rebuilt
# here rather than committed stale.
python3 "$ROOT/tools/gen-dsp-tables.py" >/dev/null

cp "$DSP_SOURCE" "$BUILD/DSP.ASM"
cp src/dsp/*.inc "$BUILD/" 2>/dev/null || true
cp "$ASM56K/ASM56000.EXE" "$ASM56K/CLDLOD.EXE" "$ASM56K/DOS4GW.EXE" "$BUILD/"

cat > "$BUILD/BUILD.BAT" <<EOF
@ECHO OFF
ASM56000.EXE -q -a -bDSP.CLD -z -lDSP.LST DSP.ASM
IF ERRORLEVEL 1 EXIT 1
CLDLOD.EXE DSP.CLD > DSP.LOD
EXIT
EOF

case "$(basename -- "$DOSBOX")" in
    dosbox-x*)
        # DOSBox-X has a headless SDL path on macOS, while DOSBox Staging's
        # texture output aborts before mounting the build directory when no
        # OpenGL display is available. Keep the command-line override usable
        # for either emulator family.
        SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-dummy} "$DOSBOX" \
            -nogui -nomenu -noautoexec -fastlaunch -exit \
            -c "mount c $BUILD" -c "c:" -c "BUILD.BAT" \
            >/dev/null 2>&1 || true
        ;;
    *)
        "$DOSBOX" --noprimaryconf --set output=texture "$BUILD/BUILD.BAT" >/dev/null 2>&1 || true
        ;;
esac

if [ ! -s "$BUILD/DSP.LOD" ]; then
    echo "error: no DSP.LOD produced - assembler errors follow" >&2
    sed -n '/^ *[0-9]* *[0-9]* *E /p;/error/Ip' "$BUILD/DSP.LST" 2>/dev/null | head -30 >&2
    exit 1
fi

# ASM56000 still emits a .cld after errors, so trust its summary line rather
# than grepping for "error" - ioequ.inc is full of "Parity Error" comments.
ERRORS=$(sed -n 's/^\([0-9][0-9]*\)[[:space:]][[:space:]]*Errors[[:space:]]*$/\1/p' "$BUILD/DSP.LST" | tail -1)
if [ "${ERRORS:-1}" != "0" ]; then
    echo "assembler reported ${ERRORS:-?} error(s):" >&2
    grep -nE "^[[:space:]]*[0-9]+[[:space:]]+.*\*\*\*|ERROR:" "$BUILD/DSP.LST" | head -30 >&2
    exit 1
fi

# P memory has two legal regions. One 32K-word SRAM sits behind all three
# DSP spaces on the Falcon, and external P is the same memory as the Y alias
# at the same address: a P block between $0200 and $17FF would sit on the
# far tile and the tables and be overwritten at runtime - a fault borrowed,
# already-made, from F030TREX. Internal P ends at $01FF; the cold section
# lives at $1800 above the Y working set.
python3 - "$BUILD/DSP.LOD" <<'EOF' || exit 1
import sys
blocks = []
addr = None
count = 0
active = False
for line in open(sys.argv[1]):
    t = line.split()
    if not t:
        continue
    if t[0] == "_DATA":
        if active and count:
            blocks.append((addr, addr + count - 1))
        active = len(t) >= 3 and t[1] == "P"
        addr = int(t[2], 16) if active else None
        count = 0
    elif t[0].startswith("_"):
        if active and count:
            blocks.append((addr, addr + count - 1))
        active = False
    elif active:
        count += len(t)
if active and count:
    blocks.append((addr, addr + count - 1))
hot = max((e for s, e in blocks if s < 0x200), default=0)
cold = max((e for s, e in blocks if s >= 0x1800), default=0)
print(f"DSP P extents: internal ${hot:04X} (ceiling $01FF), "
      f"cold ${cold:04X} (ceiling $3FFF)")
bad = [b for b in blocks
       if b[1] > 0x3FFF or (b[1] >= 0x200 and b[0] <= 0x17FF)]
if bad:
    for s, e in bad:
        print(f"error: P block ${s:04X}-${e:04X} lands on the Y working set "
              f"($0200-$17FF) or past $3FFF", file=sys.stderr)
    sys.exit(1)
EOF

cp "$BUILD/DSP.LOD" release/comanche.lod
echo "wrote release/comanche.lod ($(wc -c < release/comanche.lod) bytes)"
