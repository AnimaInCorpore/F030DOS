# Source media — IndyCar Racing v1.05

Status: `PARTIALLY RESOLVED` — the three source images have been FAT12
verified and extracted with disk boundaries preserved. The split code archive
and primary executable are identified; DOS-oracle execution and the shipped
runtime/launcher contract remain open.

The three supplied files are 1,474,560-byte FAT12 floppy images. Each has an
IBM 3.3 boot sector, 512-byte sectors, one sector per cluster, two FATs, 224
root entries and the `55 AA` boot signature. SHA-256 fingerprints captured on
2026-08-25:

| Disk | File | SHA-256 |
|---|---|---|
| 1/3 | `IndyCar Racing v1.05 - Papyrus - Disk 1 of 3.img` | `2B4C74D537676BD51AB08E9663414EE24252FA51FFFE91D6C9A0CE0D8EE693C1` |
| 2/3 | `IndyCar Racing v1.05 - Papyrus - Disk 2 of 3.img` | `2C0BE27BA88F93677E8B7659DB12F408CA2595D55516C0A896CADA0A4D7DD65D` |
| 3/3 | `IndyCar Racing v1.05 - Papyrus - Disk 3 of 3.img` | `6B1EE9773CAB379B905E20201F3E9470153B2D72053B973E68673E6E18DAA883` |

The root directories currently expose installer/setup material including
`INSTALL.EXE`, `INSTALL.BAT`, `UCC.EXE`, `SD.EXE`, `EZI.CFG`, `INDYCAR.001`,
`INDYCAR.002`, and track archives such as `LAGUNA.LZH` and `TORONTO.LZH`.
Preserve disk boundaries and do not treat any one executable as the game
authority until the shipped launcher and DOS runtime identify it.

The reproducible extraction command is:

```text
python tools/re/extract_media.py
```

It verifies the BPB geometry, boot signature, matching FAT copies, valid
cluster chains and non-overlapping file allocations before writing the raw
disk trees to `game/disks/disk1`, `game/disks/disk2` and `game/disks/disk3`.
The complete directory and extracted-file hash record is in
[`media-manifest.md`](media-manifest.md); the machine-readable run output is
`work/media-manifest.json`.
