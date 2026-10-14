# Regenerating derived work

From the project root:

```text
python tools/extract_archive.py
python tools/re/mzinfo.py game/MagCarp/CARPET/CARPET.EXE
python tools/re/mzinfo.py game/MagCarp/CARPET/CARPET.EXE --dump-load work/listings/CARPET.mz.load
ndisasm -b 16 -o 0x0 work/listings/CARPET.mz.load > work/listings/CARPET-loader.lst
python tools/re/list_mz.py game/MagCarp/CARPET/CARPET.EXE --output work/listings/CARPET-loader.lst
python tools/re/audit_le.py game/MagCarp/CARPET/CARPET.EXE --stats
python work/build_dos_hdd.py --no-boot
```

The archive extractor verifies all ZIP member CRCs and recreates the pristine
reference tree. The MZ helper prints the LE object metadata but does not claim a
protected-mode flat mapping. The DOS image builder stages both `CARPET` and
`CARPET.CD` once genuine DOS 6.22 floppies are available; add `--run-game` only
for an intentional runtime experiment.

`dosimg.py`, `run_qemu.py`, `mbr.asm` and `gdbstub_probe.py` are synchronized
from `../F030Method/dos/`; do not edit their project copies directly.
