#!/bin/bash
# Assemble and link the CPU-only 68030 attract milestone into
# release/comanche.tos.
#
# Use the checked-in Windows tools by default, with the native macOS tools
# from the sibling F030Arcade project as the Darwin fallback. Override with
# VASM=... / VLINK=... if a different toolchain is required.
set -e

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

# CPU selection changes the instruction mechanism only. Stock Falcon/68030
# remains the default; the 060 image uses exact software wide multiplication.
TARGET_CPU=${TARGET_CPU:-68030}
case "$TARGET_CPU" in
    68030) DEFAULT_OUTDIR=release; OBJECT_DIR=build ;;
    68060) DEFAULT_OUTDIR=release/68060; OBJECT_DIR=build/cpu-68060 ;;
    *) echo "error: TARGET_CPU must be 68030 or 68060" >&2; exit 1 ;;
esac

# Where the staged program and its assets land. Overridable so two
# captures can run at once without overwriting each other's binary -
# a shared release/ silently swaps the program under a running probe.
OUTDIR=${OUTDIR:-$DEFAULT_OUTDIR}

F030ARCADE_ROOT=${F030ARCADE_ROOT:-"$ROOT/../F030Arcade"}
MAC_TOOL_ROOT="$F030ARCADE_ROOT/third_party/chorensha/tools"

if [ -z "${VASM:-}" ]; then
    if [ "$(uname -s)" = "Darwin" ] && [ -x "$MAC_TOOL_ROOT/vasmm68k_mot_mac" ]; then
        VASM="$MAC_TOOL_ROOT/vasmm68k_mot_mac"
    else
        VASM="$ROOT/tools/toolchain/vasmm68k_mot.exe"
    fi
fi

if [ -z "${VLINK:-}" ]; then
    if [ "$(uname -s)" = "Darwin" ] && [ -x "$MAC_TOOL_ROOT/vlink_mac" ]; then
        VLINK="$MAC_TOOL_ROOT/vlink_mac"
    else
        VLINK="$ROOT/tools/toolchain/vlink.exe"
    fi
fi

[ -x "$VASM" ]  || {
    echo "error: vasm not executable at $VASM" >&2
    echo "       set VASM=/path/to/vasmm68k_mot to override it" >&2
    exit 1
}
[ -x "$VLINK" ] || {
    echo "error: vlink not executable at $VLINK" >&2
    echo "       set VLINK=/path/to/vlink to override it" >&2
    exit 1
}

echo "$TARGET_CPU toolchain: vasm=$VASM vlink=$VLINK"

mkdir -p build "$OBJECT_DIR" "$OUTDIR"

# The runtime loader consumes the original terrain pair from the program's
# directory. A missing pair is an installation error, not a reason to invent a
# landscape. Stage every shipped terrain family because the attract/demo state
# selects them by pass.
ASSET_ROOT="$ROOT/assets/extracted/comanche_hdd"
STAGED_TERRAIN=0
if [ -f "$ASSET_ROOT/D1.DTA" ] && [ -f "$ASSET_ROOT/C1.DTA" ]; then
    for n in 1 2 3 4; do
        cp "$ASSET_ROOT/D$n.DTA" "$ASSET_ROOT/C$n.DTA" "$OUTDIR"/
    done
    STAGED_TERRAIN=1
echo "staged runtime terrain: D1.DTA..D4.DTA/C1.DTA..C4.DTA"

# The first fixed resource in each mission list is the active DOS palette.
# P44 is the normal fourth palette; NP44 is the authored night-vision palette
# used by mission 1. Stage both families so the attract replay never falls
# back to the selected Cn.DTA palette.
STAGED_PALETTES=""
for f in "$ASSET_ROOT"/P*.DTA "$ASSET_ROOT"/NP*.DTA; do
    [ -f "$f" ] || continue
    cp "$f" "$OUTDIR"/
    STAGED_PALETTES="$STAGED_PALETTES $(basename "$f")"
done
[ -n "$STAGED_PALETTES" ] && echo "staged runtime palettes:$STAGED_PALETTES"
else
    echo "error: original D1.DTA/C1.DTA terrain pair is required" >&2
    exit 1
fi

for f in HIGH.DTL MEDIUM.DTL LOW.DTL; do
    [ -f "$ASSET_ROOT/$f" ] || { echo "error: missing original $f" >&2; exit 1; }
    cp "$ASSET_ROOT/$f" "$OUTDIR"/
done
echo "staged runtime depth tables: HIGH.DTL/MEDIUM.DTL/LOW.DTL"

# The original's own tables - sine, menu font and texts, roster and settings
# defaults, view, bearing and sprite-ramp tables - are read from the player's
# COMANCHE.EXE at startup (src/origexe.s), not built into the program.
[ -f "$ASSET_ROOT/COMANCHE.EXE" ] || { echo "error: missing original COMANCHE.EXE" >&2; exit 1; }
cp "$ASSET_ROOT/COMANCHE.EXE" "$OUTDIR"/
echo "staged runtime tables: COMANCHE.EXE"

# Stage the default and mission-selected SG banks. The DOS mission resource
# list supplies ten inline names and the factory indexes them through f2/f3;
# staging only TANK would silently turn every attract object into a tank.
# CHAF/STGR/HELL/ROCK/BULL/BOOM are the six shared weapon and effect banks
# mission setup loads at 000066E2-000067AE, whatever the mission list names.
RUNTIME_SPRITES="TANK.RLE LH66.RLE SPIN.RLE FUEL.RLE TURR.RLE RADR.RLE HOKE.RLE CHAF.RLE STGR.RLE HELL.RLE ROCK.RLE BULL.RLE BOOM.RLE"
STAGED_SPRITES=""
for f in $RUNTIME_SPRITES; do
    if [ -f "$ASSET_ROOT/$f" ]; then
        cp "$ASSET_ROOT/$f" "$OUTDIR"/
        STAGED_SPRITES="$STAGED_SPRITES $f"
    fi
done
[ -n "$STAGED_SPRITES" ] && echo "staged runtime sprites:$STAGED_SPRITES"

# The mission backdrops are real assets selected by the mission/demo resource
# list. A missing sky must not turn into a hand-drawn gradient.
for f in SKY1.RLE SKY2.RLE SKY3.RLE SKY4.RLE; do
    [ -f "$ASSET_ROOT/$f" ] || { echo "error: missing original $f" >&2; exit 1; }
    cp "$ASSET_ROOT/$f" "$OUTDIR"/
done
echo "staged runtime skies: SKY1.RLE..SKY4.RLE"

# The attract cycle: recorded demo flights, the two openings' screens and
# their overlay banks. Absent files degrade one screen or the whole cycle,
# never the build.
ATTRACT_STAGED=""
# RAH66.DTA is the menu chain's own background, loaded at 00028CE8 through the
# same Kyle DTA path as the attract screens, so it stages with them.
for f in DEMO0.SCR DEMO1.SCR DEMO2.SCR DEMO3.SCR \
         BACK.DTA TPIC.DTA RH66SIDE.DTA ZOVE.RLE FANFARE.RLE RAH66.DTA MISSION.DTA COMANCHE.NAM CREDIT1.DTA LOSE3.DTA WIN3.DTA \
         COMANCHE.MNU; do
    if [ -f "$ASSET_ROOT/$f" ]; then
        cp "$ASSET_ROOT/$f" "$OUTDIR"/
        ATTRACT_STAGED="$ATTRACT_STAGED $f"
    fi
done
[ -n "$ATTRACT_STAGED" ] && echo "staged attract:$ATTRACT_STAGED"

# This port is built for HIGH detail: tools/prepare-original-test.py generates
# HIGH.DTL's 250 rings and src/dtl.s caches '0'. COMANCHE.MNU's settings block
# is at +0x18 and its first byte is the detail character 00026211 reads -
# '0' high, '1' medium, anything else low. The shipped install says '1', so
# leaving it alone would have dtl_apply_settings reload MEDIUM.DTL over the
# build's own tables at startup and the port would run medium after all.
#
# Patched in the STAGED copy only. assets/extracted/ is the original's own
# bytes and stays untouched; this is the same byte the Detail menu writes, so
# it is a configuration choice, not a modified asset.
#
# COMANCHE_DETAIL selects the staged character for comparison runs against the
# DOS oracle, which runs the shipped install's MEDIUM ('1'): the detail level
# changes which ring an object falls in and what occludes it, so a frame pair
# taken at HIGH against a MEDIUM original measures the setting, not the port.
# The default stays '0'.
if [ -f "$OUTDIR/COMANCHE.MNU" ]; then
    COMANCHE_DETAIL="${COMANCHE_DETAIL:-0}" python - "$OUTDIR/COMANCHE.MNU" <<'PATCH_MNU'
import os, pathlib, sys
p = pathlib.Path(sys.argv[1])
want = os.environ.get("COMANCHE_DETAIL", "0")
b = bytearray(p.read_bytes())
if len(b) > 0x18 and b[0x18] != ord(want):
    was = chr(b[0x18])
    b[0x18] = ord(want)
    p.write_bytes(bytes(b))
    print(f"staged COMANCHE.MNU: detail '{was}' -> '{want}'")
PATCH_MNU
fi

# The digital sound layer (src/sound.s): the three sample banks the original
# loads at the title and at mission load (snd1.rle 000058D4/000064A8, speak0.rle
# 0000681D, speak1.rle 00006859) and COMANCHE.CFG, whose second byte is the
# digital device (000054F7-0000558F; the shipped file selects the Sound Blaster
# path, which the Falcon replaces with its sound DMA). A missing bank is
# reported by the game as "not loaded", never replaced; a missing .CFG leaves
# the digital layer off.
SOUND_STAGED=""
for f in SND1.RLE SPEAK1.RLE SPEAK0.RLE COMANCHE.CFG; do
    if [ -f "$ASSET_ROOT/$f" ]; then
        cp "$ASSET_ROOT/$f" "$OUTDIR"/
        SOUND_STAGED="$SOUND_STAGED $f"
    fi
done
[ -n "$SOUND_STAGED" ] && echo "staged runtime sound:$SOUND_STAGED"

# The music (src/music.s): the three MS3 songs the attract and the menu read
# raw (OPENMUS 000058AA, MENUMUS1/2 00028CA2/00028CB9, 000056F9) and the KRL
# songs read by name or through a mission's resource lines 6, 8 and 10
# (FANFARE 000057EE; MUSDAY/MUSNIGHT/MUSVOLC, MUSWIN/WINMUS/BIGWIN, MUSLOSE).
MUSIC_STAGED=""
for f in OPENMUS.MS3 MENUMUS1.MS3 MENUMUS2.MS3 FANFARE.RLE MUSDAY.RLE MUSNIGHT.RLE \
         MUSVOLC.RLE MUSWIN.RLE MUSLOSE.RLE WINMUS.RLE BIGWIN.RLE; do
    if [ -f "$ASSET_ROOT/$f" ]; then
        cp "$ASSET_ROOT/$f" "$OUTDIR"/
        MUSIC_STAGED="$MUSIC_STAGED $f"
    fi
done
[ -n "$MUSIC_STAGED" ] && echo "staged runtime music:$MUSIC_STAGED"

# COMA.RLE is the bank the original's cockpit blitters read - the one writer of
# their resource base at 00005920 loads it by name.
# All five, not just the first. console_select_variant patches the digit into
# "CONSOL1S.DTA" and console_init loads it at RUNTIME, so a variant whose file
# is missing keeps the previous one on screen. The attract needs more than
# CONSOL1S: 00019689's cases load consol1s..consol4s for variants 1..4 and
# consol5s for 5, 6 and 7 alike, and DEMO1 spends 178 frames in variant 6 and
# 153 in variant 7 - 41% of the pass wanting CONSOL5S.
CONSOLE_STAGED=""
for f in CONSOL1S.DTA CONSOL2S.DTA CONSOL3S.DTA CONSOL4S.DTA CONSOL5S.DTA; do
    if [ -f "$ASSET_ROOT/$f" ]; then
        cp "$ASSET_ROOT/$f" "$OUTDIR"/
        CONSOLE_STAGED="$CONSOLE_STAGED $f"
    fi
done
[ -n "$CONSOLE_STAGED" ] && echo "staged runtime consoles:$CONSOLE_STAGED"

if [ -f "$ASSET_ROOT/COMA.RLE" ]; then
    cp "$ASSET_ROOT/COMA.RLE" "$OUTDIR"/
    echo "staged runtime cockpit: COMA.RLE"
fi

# CONS.RLE holds the 57 instrument elements the cockpit panel is built from.
if [ -f "$ASSET_ROOT/CONS.RLE" ]; then
    cp "$ASSET_ROOT/CONS.RLE" "$OUTDIR"/
    echo "staged runtime instruments: CONS.RLE"
fi

# HUDS.RLE is the separate authored flight overlay bank.  The cockpit and
# HUD use different SG banks in the DOS build: CONS is the panel hardware,
# HUDS carries the green reticle, compass ribbon, ladder and value glyphs.
if [ -f "$ASSET_ROOT/HUDS.RLE" ]; then
    cp "$ASSET_ROOT/HUDS.RLE" "$OUTDIR"/
    echo "staged runtime flight HUD: HUDS.RLE"
fi

# Stage every numbered mission stream that is installed. This is no longer a
# convenience: 0002A104 builds the campaign list by probing 0.MIS through
# 9.MIS at startup, so which of them are beside the TOS image is exactly what
# the campaign screen lists. Staging only 0.MIS would show one campaign and
# hide the port of the walk that finds the rest.
STAGED_MISSIONS=""
for n in 0 1 2 3 4 5 6 7 8 9; do
    if [ -f "$ASSET_ROOT/$n.MIS" ]; then
        cp "$ASSET_ROOT/$n.MIS" "$OUTDIR"/
        STAGED_MISSIONS="$STAGED_MISSIONS $n.MIS"
    fi
done
if [ -n "$STAGED_MISSIONS" ]; then
    echo "staged runtime missions:$STAGED_MISSIONS"
fi

# Renderer tables and the colour palette are generated from the same original
# asset family the runtime loads. The generator emits ignored build output; no
# source asset enters the release tree.
PYTHON=${PYTHON:-$(command -v python3 || command -v python)}
[ -n "$PYTHON" ] || { echo "error: no python interpreter found" >&2; exit 1; }
"$PYTHON" tools/prepare-original-test.py --source=original build/original_test.s

# The generated palette only means anything against the map the Falcon actually
# opens. Refuse to ship a build whose tables describe a different asset family:
# The generator and runtime therefore always describe the same original C1
# index space; a plausible-looking palette mismatch cannot enter the build.
SOURCE_ID=$(sed -n 's/^ORIGINAL_ASSET_SOURCE = \([0-9]*\).*/\1/p' build/original_test.s)
if [ "$STAGED_TERRAIN" = 1 ] && [ "$SOURCE_ID" != 1 ]; then
    echo "error: $OUTDIR stages D1.DTA/C1.DTA but build tables were generated" >&2
    echo "       from asset source $SOURCE_ID - the palette would not match the map" >&2
    exit 1
fi

# CPU-only is a source invariant for the first Falcon attract milestone. Do not
# silently turn a later DSP experiment into a different supported executable.
if [ "${USE_DSP:-0}" != 0 ] || [ "${PARITY_TILE:-0}" != 0 ]; then
    echo "error: the attract milestone is CPU-only; DSP options are dormant" >&2
    exit 1
fi
# MARCHER_ORACLE pins the camera to a captured DOS cockpit frame so the
# marcher's own silhouette can be diffed against the original's archive.
# It is a diagnostic build and never a game one - it freezes the camera.
MARCHER_ORACLE=${MARCHER_ORACLE:-0}
VASMDEFS="-DTARGET_CPU=$TARGET_CPU -DUSE_DSP=0 -DPARITY_TILE=0 -DMARCHER_ORACLE=$MARCHER_ORACLE -DMUSIC_CHIP=${MUSIC_CHIP:-0} -DOPL2=${OPL2:-0} -DHWTEST=${HWTEST:-0}"

# start.s comes first when present - vlink places the first object at the TEXT
# base and the entry point has to sit there for the TOS startup header.
SOURCES=""
if [ -f src/start.s ]; then
    SOURCES="start"
fi
# HWTEST=1 adds src/hwtest.s's report (HWTEST.TXT at exit) for testing on
# real hardware; it links last with krl and sound and is empty otherwise.
# krl and sound link last. The older modules reach each other with 16-bit
# `bsr`s, and the text between hud and sprite is within a few hundred bytes of
# that range; new code placed alphabetically between them pushes a branch out.
# Both are only called through `jsr`/their own module, so the end is free.
for f in src/*.s; do
    [ -f "$f" ] || continue
    name=$(basename "$f" .s)
    [ "$name" = start ] && continue
    [ "$name" = krl ] && continue
    [ "$name" = sound ] && continue
    [ "$name" = hwtest ] && continue
    SOURCES="$SOURCES $name"
done
for name in krl sound hwtest; do
    [ -f "src/$name.s" ] && SOURCES="$SOURCES $name"
done

[ -n "$SOURCES" ] || { echo "error: no 68030 sources found in src/" >&2; exit 1; }

OBJECTS=""
for name in $SOURCES; do
    [ -f "src/$name.s" ] || { echo "error: src/$name.s missing" >&2; exit 1; }
    VASM_LOG=$("$VASM" "src/$name.s" -quiet -Felf "-m$TARGET_CPU" $VASMDEFS -o "$OBJECT_DIR/$name.o" -L "$OBJECT_DIR/$name.lst" 2>&1) || { echo "$VASM_LOG"; exit 1; }
    echo "$VASM_LOG"
    # Warning 2028 is a constant that does not fit its instruction's field
    # (moveq #159 became -97, and a loop ran 65,000 times over the bss for as
    # long as shake_present existed). It is always a bug here.
    case "$VASM_LOG" in
        *"warning 2028"*) echo "error: src/$name.s has an operand that does not fit (warning 2028)" >&2; exit 1 ;;
    esac
    OBJECTS="$OBJECTS $OBJECT_DIR/$name.o"
done

# OPL2=1: the music's synthesiser, F030OPL2's DSP kernel and its 68k host
# (decoder opldec.s, refills oplhost.s), assembled from the sibling checkout
# ../F030OPL2 - it is GPL-3.0 and stays there: nothing of it is copied into
# this repository. Its upload image OPLDATA.BIN (the kernel's tables, made by
# its tools/opl/opl-upload-image) is generated into the output directory.
if [ "${OPL2:-0}" != 0 ]; then
    OPL2_ROOT=${OPL2_ROOT:-../F030OPL2}
    [ -f "$OPL2_ROOT/tools/opl/m68k/oplhost.s" ] || { echo "error: OPL2=1 needs F030OPL2 at $OPL2_ROOT" >&2; exit 1; }
    for f in opldec oplhost; do
        "$VASM" "$OPL2_ROOT/tools/opl/m68k/$f.s" -quiet -Felf "-m$TARGET_CPU" \
            -I "$OPL2_ROOT/src/m68k" -I "$OPL2_ROOT/tools/opl/dsp" -o "$OBJECT_DIR/opl2_$f.o" || exit 1
        OBJECTS="$OBJECTS $OBJECT_DIR/opl2_$f.o"
    done
    ${HOST_CXX:-c++} -std=c++17 -O1 -I "$OPL2_ROOT/tools/opl" -o "$OBJECT_DIR/opl-upload-image" \
        "$OPL2_ROOT/tools/opl/opl-upload-image.cpp" || exit 1
    "$OBJECT_DIR/opl-upload-image" "$OUTDIR/OPLDATA.BIN" || exit 1
    echo "linked F030OPL2 ($OPL2_ROOT): opldec, oplhost; staged OPLDATA.BIN"
fi

# The code uses absolute references into the TOS-allocated BSS and framebuffer
# surfaces. Keep the relocation table; -tos-fastload would leave those words
# as section offsets and makes the program write into low memory instead.
#
# PRG flags: 1 = fastload. The 68060 image adds 2|4 (load into and Malloc from
# TT-RAM): an accelerated Falcon's ST-RAM sits behind the 16 MHz bus shared
# with Videl, and the marcher, the persistent terrain surface, the maps and
# the sprite banks are all in BSS. Everything a Falcon device reads - both
# scanout pages and the sound DMA ring - is Mxalloc'd from ST-RAM explicitly
# (start.s, sound.s), so where TOS puts the program does not matter to them.
# Without TT-RAM, TOS ignores the two bits and loads into ST-RAM as before.
case "$TARGET_CPU" in
    68060) TOS_FLAGS=7 ;;
    *) TOS_FLAGS=1 ;;
esac
"$VLINK" $OBJECTS -q -Rstd -b ataritos -tos-flags $TOS_FLAGS -e _main -M"$OUTDIR/comanche.map" -o "$OUTDIR/comanche_d.tos"
"$VLINK" $OBJECTS -q -Rstd -b ataritos -tos-flags $TOS_FLAGS -s -e _main -o "$OUTDIR/comanche.tos"

echo "built $OUTDIR/comanche.tos ($(wc -c < "$OUTDIR/comanche.tos") bytes), $OUTDIR/comanche_d.tos"
