# Installer and code-set provenance — IndyCar Racing v1.05

Status: `IDENTIFIED` — the source configuration and split code archive explain
the primary installed tree. The installer UI itself remains unmeasured.
Correction reviewed 2026-10-10: runtime launch is now recorded through menus
and a driven practice session in [runtime.md](runtime.md) and
[menu-flow.md](menu-flow.md); it is no longer an unobserved launch prerequisite.

## Shipped setup path

`INSTALL.BAT` changes to `INSTALL` and runs `INSTALL.EXE`. The accompanying
`EZI.CFG` is the stronger distribution-level description:

| Field | Value |
|---|---|
| `Name` / `Description` | `IndyCar` / `IndyCar Racing` |
| `Disks` | `2` |
| `HowToStart` | `INDYCAR` |
| `MergeSet` | `INDYCAR` |
| `CodeExec` | `indycar` |
| `CodeDrive` / `CodePath` | `C` / `\INDYCAR` |
| `CodeSpace` | `2340` KB |
| `GraphicsRequired` / `VGARequired` | `YES` / `YES` |
| `DosMajor` / `DosMinor` | `3` / `3` |
| `CPUType` | `1 80386` |

The two code-set records are:

```text
DiskSet 1
   CODE  INDYCAR.001
DiskSet 2
   CODE  INDYCAR.002
```

This establishes that `UCC.EXE`, `SD.EXE` and `INSTALL.EXE` are setup/runtime
support binaries, not the game authority. `INDYCAR.001` starts with a 40-byte
merge prefix and an LHA level-0 stream; `INDYCAR.002` is the continuation.

## Reconstructed archive and installed tree

Run the following from the project root:

```text
python tools/re/extract_media.py
python tools/re/merge_indycar.py
python tools/re/extract_install.py
```

`tools/re/extract_install.py --test-only` runs the archive check without
rewriting the derived installed tree. The merged archive is
`work/INDYCAR.MERGED`, 1,084,877 bytes, SHA-256
`3EBB2AC3FA30D82A4EBCFDE3F77DAD223611EEF8D07DDD29B6326EA001F5EB36`.
7-Zip 26.02 reports an LHA stream at offset 40, 37 files, 2,623,966 expanded
bytes and `Everything is Ok`. The expanded files are under
`game/installed`; their hashes are recorded in
[`installed-manifest.md`](installed-manifest.md).

The eight track LZH archives are a separate install layer. They are all
tested and expanded into per-track trees under `game/tracks` without flattening
their repeated setup filenames; see [`tracks.md`](tracks.md).

## Primary executable

`game/installed/INDYCAR.EXE` is 742,377 bytes with SHA-256
`5B8BD9AA115C0E8CCD012617B161B44CE02124AA5875F2182EFA132ECA5B8B5A`. Static
strings identify:

- `IndyCar Racing`, `Version 1.05`, and `Copyright (c) 1993-4`;
- `WATCOM C/C++32 Run-Time system`;
- `DOS/4GW Professional Protected Mode Run-time`, version build date
  `Feb 17 1994 11:54:25`.

The executable is therefore the current analysis authority. Its MZ header has
78 relocation entries and a 32-paragraph header; the DOS/4G/DOS/4GW runtime
and the large appended image require container/address analysis before code
coverage is widened.
