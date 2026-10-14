# Magic Carpet Plus archive layout

Status: **RESOLVED** for the archive container and the top-level runtime
trees. Individual `.DAT`, `.TAB`, level and sound formats remain **TBD**.

The source is `assets/Magic_Carpet_Plus_1995.zip`. `python
tools/extract_archive.py` verifies and extracts it without changing the
archive. The measured source hash is:

```text
SHA-256  B78238AB830AEB24EA3E5C8A63FBFBC8D169BA5F8314CC49A89692A564670EF6
```

The archive has 252 entries, of which 238 are files, and 132,588,028 bytes of
uncompressed data. The outer `MagCarp/` directory is preserved in `game/`.

| tree | files | uncompressed bytes | role |
|---|---:|---:|---|
| `MagCarp/CARPET/` | 216 | 130,112,376 | primary installed runtime tree |
| `MagCarp/CARPET.CD/` | 17 | 2,460,362 | CD-side maps, level data and sound setup |
| `MagCarp/CARPET/INTRO/` | 12 | 112,104,778 | intro/title/outro media; keep separate in first static pass |
| `MagCarp/CARPET/MOVIE/` | 6 | 1,567,123 | movie frames; keep separate in first static pass |

The primary executable is `MagCarp/CARPET/CARPET.EXE`. The same archive also
contains `HIDDEN.EXE` and `SELECT.EXE`, which share the MZ/LE loader shape but
are separate linked variants. `DOS4GW.EXE` is the small DOS/4G extender copied
with the game; `_DOS4GW.EXE` is a different larger runtime artifact and is not
treated as the game's protected-mode image.

The archive's `run.bat`, `dosbox.conf` and `IAFIX.BAT` are launch/support files,
not disassembly targets. Keep their observations available for the DOS oracle,
but do not mistake them or `SELECT.EXE` for the main game image.
