# Source media — Panzer General

Status: `RESOLVED` for the unpatched base distribution — the outer archive has
passed CRC verification, all six FAT12 images have been extracted and hashed,
the DOS installer volumes have been recovered, and the launcher-selected
executable is identified. The patch disk remains separate and unapplied.

The supplied ZIP is
`assets/Panzer General (1994)[3.5][us]_ima.zip` with SHA-256:

`7D5D1DDF1513852A379BB77628711EABAA0C3760D7E360052F56FB20E9844FFF`

All members are 1,474,560-byte floppy images. The ZIP CRC32 values are recorded
here as the first extraction check:

| Member | CRC32 |
|---|---:|
| `disk1.ima` | `DCE3F66B` |
| `disk2.ima` | `5F41B4D2` |
| `disk3.ima` | `E5F164EA` |
| `disk4.ima` | `5513427D` |
| `disk5.ima` | `E880F856` |
| `disk patch.ima` | `654D211F` |

Keep the patch disk separate from the five base disks. Once extracted, record
each image hash, FAT12 directory and installed-file hash before selecting the
DOS executable or mixing patched and unpatched resource trees.

## Reproducible staging

Run from the project root:

```text
python work/stage_media.py
```

The script uses Python 3.12.10 `zipfile`, checks the archive SHA-256 and all
stored ZIP CRCs, validates both FAT12 copies and writes only the ignored
`work/media/` tree. The complete machine-readable result is
`work/media/manifest.json`.

The archive passed with six members, each exactly 1,474,560 bytes. The
extracted floppy-image SHA-256 values are:

| Disk | FAT12 volume label | Image SHA-256 |
|---|---|---|
| `disk1.ima` | `PGDISK1_V1` | `09C5FCB30E66437E39C0B6710C9DB8FC26B7C571B742C64E1758FD4F25289CC8` |
| `disk2.ima` | `PGDISK2_V1` | `37ED46C8BBB75A8FF3AA44303398BD5686FB338E5AE14298DD874BB1CD9ADC57` |
| `disk3.ima` | `PGDISK3_V1` | `8723F89816101E216D9D76A42499D46C5A6C622CB141C14EF9F985851D098514` |
| `disk4.ima` | `PGDISK4_V1` | `253C22507EBB93AE36C2D1827E739EAB3ADE76A877D43EE642A18D08F77B72CD` |
| `disk5.ima` | `PGDISK5_V1` | `13565EA20DE062B4C88C1E7C6E051104BD6AF9A5CF94A221994A462BFBE485F2` |
| `disk patch.ima` | `NO NAME` | `6F16860E9E69C04337039324345927C19C5DCC9DC837461E7B4E8FB90F69D8AE` |

All six images use the same 512-byte-sector, 1-sector/cluster FAT12
geometry. The base distribution contains `DATA.A00` through `DATA.A04`,
each beginning with the ARJ signature `60 EA`, plus `DEARJ.EXE`,
`INSTALL.EXE`, `BOOT.NFO` and `INSTALL.NFO` on disk 1. The patch disk is
separate and contains `PATCH.EXE` and `PATCH.RTP`; it has not been applied.

The patch files are retained as separate provenance inputs:

| File | Size | SHA-256 |
|---|---:|---|
| `PATCH.EXE` | 45,450 | `8528CE58BB1190F86E38AD79DE7A2C4DCACAF1D7D85A486FE1563BB869D6FF18` |
| `PATCH.RTP` | 74,384 | `C79558532A2B23345CBD976A59EB94EE50CA9E9577AC53EB2C1907CB61847EB1` |

## Recovered install tree

Run from the project root:

```text
python work/extract_game.py
```

This invokes the supplied `DEARJ.EXE` under DOS, processing `DATA.A00`
through `DATA.A04` in one output directory. The DOS logs report 889/889
`CRC OK` entries and no bad entries. The four volume-boundary continuations
are restored as single logical files:

| Logical file | Volume pieces |
|---|---|
| `DAT/A_036_6.SHP` | `DATA.A00` + `DATA.A01` |
| `DAT/A_079_2.SHP` | `DATA.A01` + `DATA.A02` |
| `DAT/FINALE.SHP` | `DATA.A02` + `DATA.A03` |
| `EXE/GM2.BNK` | `DATA.A03` + `DATA.A04` |

The generated `game/` tree contains 885 logical files and 15,866,334
uncompressed bytes. It is the unpatched base tree and must not be mixed with
the separate patch disk until patch behavior is measured.

`INSTALL.NFO` names `\PG` as the install directory and `PG` as the start
command. The recovered `PG.BAT` changes into `EXE`, runs `UNIVBE`, optionally
loads Gravis Ultrasound patches, and then executes `PANZER.EXE`; that file is
therefore the build selected for executable analysis.
