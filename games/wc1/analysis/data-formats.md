# WC1 data formats (verified against `release/WC1DATA/`)

All offsets and fields below were verified against actual file bytes, not
guessed. "LE" = little-endian. Staging is `make data` (plain unzip of the
three user-supplied disk images — the DOS disks use no archiving of their own).

Semantics that come from the reconstruction rather than from the bytes are
attributed to `../wc1-re` explicitly. Anything unproven is marked **TBD**.

## 1. `INSTALL.DAT` — logical-file table — RESOLVED

928 B = **58 × 16-byte records**, the final record zero-filled as terminator
(the port stops on an empty name: `src/mission.s` `tst.b (a0); beq .done`).
57 real records, matching the 57 shipped files exactly.

```
struct DiskFileRecord {      /* wc1-re/include/wcdata.h:491 */
    char          name[13];  /* 8.3, NUL-padded, no guaranteed terminator */
    signed char   diskNumber;
    unsigned char fileClass;
    unsigned char logicalFile;
};
```

First bytes verified: `44 49 53 4b 2e 30 30 31 00 00 00 00 00 01 07 ff`
(`DISK.001`, disk 1, class 7, logical 0xFF).

- **`logicalFile`** is how the runtime addresses a resource; `0xFF` means the
  file is not reachable that way. The port compares byte **offset 15** of each
  record against `MISSION_ARCHIVE_LOGICAL = 16`.
- **`fileClass`** groups the resource kind: `2` art/shape (`*.VGA`,
  `SHIP.Vxx`), `3` `SHIPTYPE.Vxx`, `4` `PCSHIP.Vxx`, `5` `COCKPIT.VGA`,
  `6` `MIDGAME.Vxx`, `7` everything else.
- **Verified numbering rules** (these are the DOS rules the port already
  implements, now confirmed against the table):
  - `MODULE.000` → logical **16**.
  - `PCSHIP.Vnn` → logical `nn + 18`; DOS selects the cockpit with
    `mode + 17`, so `mode` is 1-based (`mode 1` → 18 → `PCSHIP.V00`).
  - `SHIP.Vnn` **and** `SHIPTYPE.Vnn` → logical `nn + 23`; DOS `load_ship()`
    uses `type + 22`, again 1-based. Capital ships and fighters therefore
    share **one type-number space**, and no shipped `nn` collides:
    fighters use 0–3, 9–13, 29; capitals use 6, 7, 8, 15, 17, 18, 21.

### Decoded table

| # | name | disk | class | logical |
|---|---|---|---|---|
| 0 | `DISK.001` | 1 | 7 | **0xFF** |
| 1 | `WC.EXE` | 1 | 7 | 0 |
| 2 | `INSTALL.DAT` | 1 | 7 | **0xFF** |
| 3 | `GAME.PAL` | 1 | 7 | **0xFF** |
| 4 | `ARROW.VGA` | 1 | 2 | 15 |
| 5 | `FONTS.FNT` | 1 | 7 | 1 |
| 6 | `CONVERT.PAL` | 1 | 7 | **0xFF** |
| 7 | `PCSHIP.V00` | 1 | 4 | 18 |
| 8 | `SHIP.V06` | 1 | 2 | 29 |
| 9 | `SHIP.V07` | 1 | 2 | 30 |
| 10 | `SHIP.V08` | 1 | 2 | 31 |
| 11 | `SHIP.V15` | 1 | 2 | 38 |
| 12 | `SHIP.V17` | 1 | 2 | 40 |
| 13 | `INSTALL.EXE` | 1 | 7 | **0xFF** |
| 14 | `MUSIC.MID` | 1 | 7 | 8 |
| 15 | `MODULE.000` | 1 | 7 | 16 |
| 16 | `PLANETS.VGA` | 1 | 2 | 13 |
| 17 | `OBJECTS.VGA` | 1 | 2 | 4 |
| 18 | `STRAX.DRV` | 1 | 7 | **0xFF** |
| 19 | `WINGLDR.TIM` | 1 | 7 | 60 |
| 20 | `COCKPIT.VGA` | 1 | 5 | 9 |
| 21 | `CAMP.000` | 1 | 7 | 59 |
| 22 | `DISK.002` | 2 | 7 | **0xFF** |
| 23 | `PCSHIP.V01` | 2 | 4 | 19 |
| 24 | `PCSHIP.V02` | 2 | 4 | 20 |
| 25 | `PCSHIP.V03` | 2 | 4 | 21 |
| 26 | `PCSHIP.V04` | 2 | 4 | 22 |
| 27 | `PILOTANM.VGA` | 2 | 2 | 3 |
| 28 | `SCRAMBLE.VGA` | 2 | 2 | 2 |
| 29 | `SHIP.V18` | 2 | 2 | 41 |
| 30 | `SHIP.V21` | 2 | 2 | 44 |
| 31 | `SHIPTYPE.V00` | 2 | 3 | 23 |
| 32 | `SHIPTYPE.V01` | 2 | 3 | 24 |
| 33 | `SHIPTYPE.V02` | 2 | 3 | 25 |
| 34 | `SHIPTYPE.V03` | 2 | 3 | 26 |
| 35 | `SHIPTYPE.V09` | 2 | 3 | 32 |
| 36 | `SHIPTYPE.V10` | 2 | 3 | 33 |
| 37 | `SHIPTYPE.V11` | 2 | 3 | 34 |
| 38 | `SHIPTYPE.V12` | 2 | 3 | 35 |
| 39 | `SHIPTYPE.V13` | 2 | 3 | 36 |
| 40 | `SHIPTYPE.V29` | 2 | 3 | 52 |
| 41 | `COMMUNIC.DAT` | 2 | 7 | 14 |
| 42 | `WINGMEN.VGA` | 2 | 2 | 12 |
| 43 | `MIDGAME.V02` | 2 | 6 | 66 |
| 44 | `DISK.003` | 3 | 7 | **0xFF** |
| 45 | `SUPERTM.DRV` | 3 | 7 | 57 |
| 46 | `TM.DRV` | 3 | 7 | 58 |
| 47 | `INTRO.DAT` | 3 | 7 | 61 |
| 48 | `TALKING.VGA` | 3 | 2 | 7 |
| 49 | `BRIEFING.VGA` | 3 | 2 | 5 |
| 50 | `RECROOM.VGA` | 3 | 2 | 6 |
| 51 | `BRIEFING.000` | 3 | 7 | 11 |
| 52 | `MIDGAME.V00` | 3 | 6 | 64 |
| 53 | `MIDGAME.V01` | 3 | 6 | 65 |
| 54 | `MIDGAME.V03` | 3 | 6 | 67 |
| 55 | `TITLE.VGA` | 3 | 2 | 10 |
| 56 | `SAVEGAME.WLD` | 3 | 7 | 17 |
| 57 | `(terminator)` | 0 | 0 | 0 |

## 2. Origin packet container — RESOLVED

**47 of the 57 shipped files** are Origin packets. Layout (implemented and
verified by `resource_load_packet()` in `src/resources.c`, mirroring
`wc1-re/src/sdl/resources.c`):

```
[u32LE declared_size]                @0x00   == file size
[u32LE entry[0]]                     @0x04   entry[0].offset == end of directory
[u32LE entry[1]] …                           one entry per section
    bits 31..24 : compression  0 = raw, 1 = Origin LZW, 0xFF = absent
    bits 23..0  : section start offset (mask 0x00FFFFFF)
[section 0] [section 1] …
```

- `section_count = (entry[0].offset >> 2) − 1`.
- Section end = the next entry's offset, or `declared_size` for the last
  section. Sizes are therefore implicit; there is no per-section length field.
- A **type-1** section begins with a `u32LE` decompressed size; the remaining
  `section_size − 4` bytes are the LZW stream.

Worked example, `MODULE.000` @0x00:
`45 56 00 00 | 1c 00 00 01 | 06 01 00 01 | 4f 1a 00 01 | 7f 29 00 01 |
4f 54 00 01 | 8e 55 00 01`
→ `declared_size = 0x5645 = 22,085` (exactly the file size),
`entry[0] = 0x0100001C` → LZW, offset 28 → directory is 28 B →
`section_count = (28 >> 2) − 1 = 6`. Section spans: 234, 6,473, 3,888,
10,960, 319, 183 B.

### Compression byte `0xFF` = absent section — RESOLVED (2026-08-20)

`0xFF` entries appear **mid-directory**, not only as trailers, and every one
of them is **zero length** (the next entry repeats the same offset). Verified:

| file | sections | `0xFF` at | all zero-length |
|---|---|---|---|
| `SHIP.V21` | 38 | 17–36 (20 consecutive) | yes |
| `BRIEFING.000` | 56 | 3, 6, 7, 11, 15, 19, 23, 27, 31, 35, 39, 43, 47 | yes |
| `PCSHIP.V04` | 10 | 1, 2, 3, 4, 5, 8 | yes |
| `COCKPIT.VGA` | 9 | 3 | yes |
| `SHIPTYPE.V29` | 3 | 1 | yes |
| `TM.DRV` | 4 | 2 | yes |
| `SUPERTM.DRV` | 4 | — (trailer only) | yes |

Reading: the directory is a **fixed section index** per resource class — 38
slots for a capital ship, 10 for a `PCSHIP`, 3 for a `SHIPTYPE` — and a
resource that does not use a slot marks it absent rather than renumbering.
`SHIP.V21` (the smallest capital ship, 47,855 B) leaves 20 of its 38 view
slots empty.

**Falcon implementation (2026-09-10):** `resource_load_packet()` now accepts a
`0xFF` entry only when its section start and end offsets are identical and lie
within the declared packet. It returns success with
`resource_packet_compression == 0xFF` and `resource_packet_size == 0`, without
reading a payload, so callers can preserve the source's fixed section index.
`tools/resource_loader_smoke.c` proves this against `PCSHIP.V04` section 1;
`make resource-smoke` is the reproducible check. The 1990 DOS routine's
return/error convention for this case remains **Unproven**; see
`analysis/functions/PacketLoad.md`.

## 3. Origin LZW — RESOLVED

Variable-width LZW, 9→12 bits, as implemented in `decode_origin_lzw()`
(`src/resources.c`) and asserted by `tools/check_contracts.py`
(`ORIGIN_LZW_MAX_CODES = 0x1000`):

| code | meaning |
|---|---|
| `0x000`–`0x0FF` | literal byte |
| `0x100` | clear — reset table, code width back to 9 |
| `0x101` | stop |
| `0x102` | first assignable code |
| `0x1000` | table ceiling |

## 4. `GAME.PAL` (1,120 B) — RESOLVED

Standard IFF ILBM, **not** an Origin packet. Verified @0x00:

```
46 4f 52 4d 00 00 04 58 49 4c 42 4d 42 4d 48 44
00 00 00 14 00 01 00 01 00 00 00 00 08 02 00 00
```

`FORM` / size 0x458 = 1,112 (+8 = 1,120 ✓) / `ILBM` / `BMHD` size 0x14 = 20
(w=1, h=1, x=0, y=0, nPlanes=8, masking=2), then `CMAP` with 256 RGB triples.

The port walks to `CMAP` and expands it into a Falcon RGB565 lookup table,
then applies the DOS cockpit reset of palette slots **185–191** so solid intro
sprites use the source dark-blue `$BF` entry rather than raw-palette black.
`make resource-smoke` reports `palette=256`.

## 5. `MODULE.000` (22,085 B) — campaign archive — sections 0–3 RESOLVED

6 Origin-LZW sections. Sections 0–3 carry the mission headers, nav points,
objectives and 32 ship records; their packed layouts are mirrored in
`include/wc1_data.h` from `wc1-re/src/cmpgn.c` and size-asserted by
`tools/check_contracts.py`:

| record | packed size | Falcon cache size |
|---|---|---|
| `MissionHeaderDisk` | 0x18 | — |
| `MissionNavPointDisk` | 0x4D | 0x4E (`FALCON_MISSION_NAV_BYTES`) |
| `MissionObjectiveDisk` | 0x40 | — |
| `MissionShipDisk` | 0x2A | 0x2C (`FALCON_MISSION_SHIP_BYTES`) |

`tools/convert_data.py` decodes these on the host and writes them aligned and
big-endian to `release/WC1CACHE/MISSION.BIN` (237,120 B, 0x40-byte header).
`src/mission.s` validates that cache and falls back to direct
`INSTALL.DAT` → `MODULE.000` → LZW loading when it is missing or invalid.
Strings, pixels, sparse shape streams and unknown packed data are deliberately
left in their original byte form.

**Sections 4–5: TBD.** Subsequent campaign archives are not staged.

## 6. Sparse shape frames — RESOLVED

The run-command stream decoded by `DecodeShapeFrame()`
(`wc1-re/src/killbrd.c`), reproduced in `src/resources.c` and `src/render.s`.
Drawn as source palette indices straight into the indexed buffer, preserving
DOS transparent gaps. Backs the cockpit frame, target lock, fighters, capital
ships, projectile bolts, `LASER_SPARK`, `EXPLOSION1`, debris and asteroids.

Fighter art is a **62-view lattice** selected by `get_right_shape()`, scaled
8.8 and projected through the `transform_objects_to_your_view()` eye frame.
Largest supplied fighter shape: **72,860 B** — the reason the Falcon resource
manager uses three 72 KiB slots, matching WC1's own three DOS object slots.

## 7. Not yet decoded

| file(s) | size | note |
|---|---|---|
| `MUSIC.MID` | 139,707 B | 41-section packet; not standard SMF at the container level |
| `WINGLDR.TIM` | 5,596 B | 3-section packet, timing/sequence data |
| `STRAX.DRV`, `TM.DRV`, `SUPERTM.DRV` | 4,869 / 29,283 / 65,281 B | Origin-FX sound drivers (packets) |
| `COMMUNIC.DAT` | 12,320 B | **not** a packet |
| `SAVEGAME.WLD` | 6,624 B | **not** a packet |
| `CONVERT.PAL` | 256 B | raw, one byte per palette slot |
| `BRIEFING.000` / `.VGA` | 222,360 / 290,931 B | 56 / 11 sections |
| `RECROOM.VGA`, `SCRAMBLE.VGA`, `TALKING.VGA`, `PILOTANM.VGA`, `WINGMEN.VGA`, `MIDGAME.Vxx` | — | scene/character packets |

## 8. Packet inventory (measured)

Every staged file that parses as an Origin packet, with its section count and
the set of compression bytes present.

| file | bytes | sections | compression present |
|---|---|---|---|
| `ARROW.VGA` | 299 | 1 | LZW |
| `BRIEFING.000` | 222,360 | 56 | LZW, absent |
| `BRIEFING.VGA` | 290,931 | 11 | LZW |
| `CAMP.000` | 651 | 3 | LZW |
| `COCKPIT.VGA` | 28,434 | 9 | LZW, absent |
| `FONTS.FNT` | 7,664 | 4 | LZW |
| `INTRO.DAT` | 630 | 1 | LZW |
| `MIDGAME.V00` | 64,561 | 7 | LZW |
| `MIDGAME.V01` | 51,885 | 7 | LZW |
| `MIDGAME.V02` | 62,986 | 7 | LZW |
| `MIDGAME.V03` | 37,231 | 7 | LZW |
| `MODULE.000` | 22,085 | 6 | LZW |
| `MUSIC.MID` | 139,707 | 41 | LZW |
| `OBJECTS.VGA` | 74,985 | 18 | LZW |
| `PCSHIP.V00` | 79,186 | 10 | LZW |
| `PCSHIP.V01` | 89,328 | 10 | LZW |
| `PCSHIP.V02` | 71,847 | 10 | LZW |
| `PCSHIP.V03` | 86,409 | 10 | LZW |
| `PCSHIP.V04` | 16,108 | 10 | LZW, absent |
| `PILOTANM.VGA` | 88,377 | 5 | LZW |
| `PLANETS.VGA` | 10,548 | 12 | LZW |
| `RECROOM.VGA` | 151,583 | 13 | LZW |
| `SCRAMBLE.VGA` | 165,009 | 10 | LZW |
| `SHIP.V06` | 92,859 | 38 | LZW |
| `SHIP.V07` | 90,532 | 38 | LZW |
| `SHIP.V08` | 102,872 | 38 | LZW |
| `SHIP.V15` | 99,824 | 38 | LZW |
| `SHIP.V17` | 87,302 | 38 | LZW |
| `SHIP.V18` | 94,854 | 38 | LZW |
| `SHIP.V21` | 47,855 | 38 | LZW, absent |
| `SHIPTYPE.V00` | 43,254 | 3 | LZW |
| `SHIPTYPE.V01` | 50,639 | 3 | LZW |
| `SHIPTYPE.V02` | 40,923 | 3 | LZW |
| `SHIPTYPE.V03` | 47,874 | 3 | LZW |
| `SHIPTYPE.V09` | 45,287 | 3 | LZW |
| `SHIPTYPE.V10` | 49,511 | 3 | LZW |
| `SHIPTYPE.V11` | 53,016 | 3 | LZW |
| `SHIPTYPE.V12` | 50,607 | 3 | LZW |
| `SHIPTYPE.V13` | 45,517 | 3 | LZW |
| `SHIPTYPE.V29` | 8,799 | 3 | LZW, absent |
| `STRAX.DRV` | 4,869 | 3 | LZW |
| `SUPERTM.DRV` | 65,281 | 4 | LZW, absent |
| `TALKING.VGA` | 137,800 | 12 | LZW |
| `TITLE.VGA` | 150,008 | 18 | LZW |
| `TM.DRV` | 29,283 | 4 | LZW, absent |
| `WINGLDR.TIM` | 5,596 | 3 | LZW |
| `WINGMEN.VGA` | 29,963 | 12 | LZW |

**47 packets.** The remaining 10 staged files are not packets:

| file | bytes |
|---|---|
| `COMMUNIC.DAT` | 12,320 |
| `CONVERT.PAL` | 256 |
| `DISK.001` | 50 |
| `DISK.002` | 50 |
| `DISK.003` | 50 |
| `GAME.PAL` | 1,120 |
| `INSTALL.DAT` | 928 |
| `INSTALL.EXE` | 51,230 |
| `SAVEGAME.WLD` | 6,624 |
| `WC.EXE` | 302,384 |
