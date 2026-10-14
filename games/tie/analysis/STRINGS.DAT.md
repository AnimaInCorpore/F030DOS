# `STRINGS.DAT` — global string table (decoded)

File: `TIECD\STRINGS.DAT`, 14,611 bytes. Single global string table used by the game
for all user-visible text (menus, HUD, damage reports, briefing verbs, help text).

## Format

```
offset 0x0000: 696 × uint32 LE offsets          (bytes 0x0000–0x0ADE)
  [0..694]     offset into string pool (all ≥ 0xAE0)
  [695]       0x00000000  (terminator / count marker)
offset 0xAE0:  string pool — NUL-terminated, no alignment padding,
               contiguous, ASCII (latin-1 safe), runs to end of file (0x3953)
```

Verified: offsets strictly ascending; 695 distinct strings; pool occupies
`0xAE0–0x3953` (11,812 bytes) exactly.

## Decode (reusable)

```python
import struct
d = open("STRINGS.DAT","rb").read()
tbl = struct.unpack("<696I", d[:0xAE0])          # last entry = 0
strings = [d[o:d.index(b"\0", o)].decode() for o in tbl[:-1]]
```

Full dump: `analysis/STRINGS.DAT.txt` (695 lines: `index offset length  text`).

## Content map (by index region)

| Range | Content |
|---|---|
| 0–9 | ship system names: `Auto Ejection System`, `Hyper Drive System`, `Lasers and Ion Cannons`, `Flight Control System`, `Engines`, `Targeting Computer`, `Shield System`, `Warhead Launch System`, `Beam System`, `Communications System` |
| 10–18 | errors/boot: `Error! Not Enough Memory!`, `Error! The following file is missing or inaccessible: `, `Initializing Combat Sequence...`, `Charging Weapons Systems...`, `Powering Up Sensor Arrays...`, `Aligning Targeting HUD...`, `Configuring Combat Multi-view Display...`, `Disk Error! Is CD-ROM Inserted?`, `Press 'R' to Retry, 'F' to Fail` |
| 19–21 | joystick calibration prompts |
| 22–27 | HUD labels: `Level:`, `Segments Left:`, `Segments Done:`, `Targets Hit:`, `Score:` |
| 29–37 | mission outcome verbs: `arrived.`, `destroyed.`, `attacked.`, `captured.`, `inspected.`, `boarded.`, `finished docking.`, `disabled.`, `survived until other goals completed.` |
| 100–130 | noun/phrase fragments for dynamic sentences: `flight groups`, `rookie pilots` … `ace pilots`, `top-ace pilots`, `stationary craft`, `craft returning to base`, `craft attacking in response`, … |
| 685–694 | wingman order help: ` SHIFT-A    Assign current target to wingman.` … ` SHIFT-W    Wait for further orders.` |

## Usage

- The 32-bit image references strings by **index** (small immediates) — when
  decompiling (Ghidra/Rizin), resolve index → text via this table.
- Reassembly: this file must be rebuilt byte-exact, or offsets re-derived.
