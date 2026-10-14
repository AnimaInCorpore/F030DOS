#!/bin/sh
# Run every built variant and decode the isa-debug-exit code.
#   AL is reported as (AL << 1) | 1, so rc 3/5/7/9 <=> AL 1/2/3/4.
decode() {
  case "$1" in
    3) echo "0x18  address = CS.base + 0x3F8   (architecturally correct)";;
    5) echo "0x20  address = 0x3F8             <-- SEGMENT BASE DROPPED";;
    7) echo "0x30  address = 0x2000 + 0x3F8    (the non-zero-base segment)";;
    9) echo "other selector";;
    37) echo "two passes: CS.base+0x3F8 then 0x3F8   (tracks current state)";;
    67) echo "two passes: 0x3F8 then CS.base+0x3F8   (tracks current state)";;
    35) echo "two passes: both CS.base+0x3F8         (cached per address)";;
    69) echo "two passes: both 0x3F8                 (cached per address)";;
    *) echo "no report from the exit device (rc=$1)";;
  esac
}
printf '%-11s %-9s %-4s %s\n' variant cpu rc "loaded selector / effective address"
for img in seg_base seg_ctrl seg_plain seg_fs seg_fscs seg_twice seg_twicerev; do
  for cpu in 486 pentium; do
    timeout 25 qemu-system-i386 -M pc -cpu "$cpu" -m 16 \
      -drive file="$img.img",format=raw,if=floppy,index=0 -boot a \
      -display none -no-reboot \
      -device isa-debug-exit,iobase=0xf4,iosize=0x04 >/dev/null 2>&1
    rc=$?
    printf '%-11s %-9s %-4s %s\n' "$img" "$cpu" "$rc" "$(decode $rc)"
  done
done
