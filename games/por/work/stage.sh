#!/bin/sh
# Rebuild every derived tree from assets/001627_pool_of_radiance.7z.
# Nothing under assets/ or game/ is modified; work/expanded/ is rebuilt.
#
#   sh work/stage.sh          from the project root
#
# Requires: 7zz (7-Zip 26+, reads 7z and FAT12 images), unar (reads ARC).
set -e
cd "$(dirname "$0")/.."

ASSET=assets/001627_pool_of_radiance.7z

# 1. raw floppy images -> game/POR/  (pristine, 720 KB FAT12)
if [ ! -f game/POR/disk1.img ]; then
    mkdir -p game/POR
    7zz x -o/tmp/por_stage -y "$ASSET" >/dev/null
    mv /tmp/por_stage/001627_pool_of_radiance/disk*.img game/POR/
    rm -rf /tmp/por_stage
fi

# 2. FAT12 contents -> game/POR/Disk1, Disk2  (pristine)
for n in 1 2; do
    if [ ! -d "game/POR/Disk$n" ]; then
        7zz x -o"game/POR/Disk$n" -y "game/POR/disk$n.img" >/dev/null
        chmod -R a-w "game/POR/Disk$n"
    fi
done

# 3. ARC contents -> work/expanded/  (derived, the analysis target)
# unar where present (macOS); otherwise the pure-Python decoder, which
# round-trips all four archives CRC-clean on Windows (2026-08-21).
if command -v unar >/dev/null; then
    rm -rf work/expanded
    mkdir -p work/expanded
    for a in game/POR/Disk1/DISKA.ARC game/POR/Disk1/DISKB.ARC \
             game/POR/Disk1/SAVE.ARC  game/POR/Disk2/DISKC.ARC; do
        unar -q -f -D -o work/expanded "$a" >/dev/null
    done
else
    python3 work/arcunpack.py
fi

# 4. byte-exact check against the ARC directory CRCs
python3 work/arcverify.py
