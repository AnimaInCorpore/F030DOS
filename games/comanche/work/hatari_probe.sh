#!/bin/bash
# Run release/comanche_d.tos headless under Hatari with a debugger script and
# print the debugger log.
#
#   bash work/hatari_probe.sh <run-vbls> <<'DBG'
#   logfile comanche-dbg.txt
#   b VBL = 3600 :once :file probe.ini
#   DBG
#
# Auxiliary scripts named by :file must already exist in release/. Written
# because tools/grab-frame.sh rewrites dbg.ini on every run, so a probe cannot
# share it, and because the debugger's own output only reaches the log file.
#
# N/A - target artefact: emulator harness, no DOS counterpart.
set -e
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
VBLS=${1:-4100}
TOS=${TOS:-"$ROOT/tools/toolchain/tos402.rom"}
HATARI=${HATARI:-$(command -v hatari)}

cat > "$ROOT/release/dbg.ini"
rm -f "$ROOT/release/comanche-dbg.txt"
(cd "$ROOT/release" && timeout -k 10 $((90 + VBLS / 20)) "$HATARI" \
    --memsize 14 --tos "$TOS" --patch-tos true --frameskips 0 \
    --monitor rgb --machine falcon --dsp off --fast-boot true --sound off \
    --fast-forward true --cpu-exact true --compatible true --confirm-quit off \
    --disable-video on --run-vbls "$VBLS" --parse dbg.ini \
    --log-file hatari.log --alert-level fatal comanche_d.tos \
    </dev/null >hatari-stdout.txt 2>&1) || true
cat "$ROOT/release/comanche-dbg.txt" 2>/dev/null
echo "--- stopped at ---"
grep -E "^CPU=" "$ROOT/release/hatari-stdout.txt" | tail -1
