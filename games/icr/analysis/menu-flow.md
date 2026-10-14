# Menu and session flow — IndyCar Racing v1.05

Status: `PARTIALLY RESOLVED` — the path from the copy-protection gate to a
running practice session is traced and reproducible under the DOS oracle, and
the car can be driven out of the pits from a scripted run. The screens are
recorded as observations; the code behind them has not been disassembled yet,
and the option/garage subtrees are unvisited.

## Reproducible path

Every step below is scheduled in seconds **after** the gate is passed, because
the attract sequence's length varies between runs
([`copy-protection.md`](copy-protection.md)):

```text
python work/drive_protection.py --key 8:ret --key 16:ret --key 24:ret \
                                --key 34:ret --shot 48 --shot 110
```

| + s | Key | Resulting screen |
|---:|---|---|
| 0 | — | **main menu**: `SINGLE RACE` (highlighted), `CHAMPIONSHIP SEASON`, `2-PLAYER RACE`, `PRESEASON TESTING`, `CARS`, `OPTIONS`, `EXIT` |
| 8 | `ret` | **CHOOSE A TRACK**: `Milwaukee`, `Nazareth`, `New Hampshire` (highlighted), `Portland`, `Toronto` — a scrolling list; the three installed tracks above it (`Laguna Seca`, `Long Beach`, `Michigan`) are off-screen |
| 16 | `ret` | **track card** for the highlighted track |
| 24 | `ret` | **SINGLE RACE session menu**: `REPLAY`, `GARAGE`, `PRACTICE` (highlighted), `NEXT SESSION (QUALIFY)`, `Leave <track>` |
| 34 | `ret` | **practice session** — the 3D cockpit view, car stationary in the pits |

`down`/`up` move the highlight; a separate run confirmed `down` then `ret` on
the track list selects `Portland` instead of the default `New Hampshire`.

## What the screens establish

**The track list is driven by the installed tree.** All eight extracted track
directories appear, which confirms that the builder's
`C:\INDYCAR\TRACKS\<track>\<file>` layout — not a flattened one — is what the
game reads. See [`tracks.md`](tracks.md) and the disk-error history in
[`runtime.md`](runtime.md).

**The track card carries per-track data worth decoding.** For Portland:

```text
Portland International Raceway
Portland, OR USA
1.950 miles   5 Laps
Temp: 70°F   Wind: NO WIND
NO RAIN
Lap Record: 0:59.007   118.993 mph
```

Length, lap count, lap record and the weather defaults are candidates for
fields in the per-track files, and the card is a cheap oracle for checking any
decode of them.

**The simulation ticks in the pits.** Two captures 62 s apart show an
identical frame except the engine temperature, `196°F` → `187°F`, with the
tachometer steady at 2000 rpm, 40 gal of fuel and first gear selected. The
session is running a model, not holding a still image — which makes the pit
view a stable, low-variance state to sample against.

## Not yet covered

- `GARAGE`, `OPTIONS`, `CARS`, `REPLAY`, `CHAMPIONSHIP SEASON`,
  `2-PLAYER RACE`, `PRESEASON TESTING`, `NEXT SESSION (QUALIFY)`
- driving beyond a first-gear roll out of the pit box (below): no steering,
  braking, gear change or lap has been exercised

## Driving

The car responds to held keys. QMP's `sendkey` takes a hold time in
milliseconds, which the driver passes through unchanged, so a throttle
application is `--key "50:up 3000"`:

```text
python work/drive_protection.py --key 8:ret --key 16:ret --key 24:ret \
    --key 34:ret --shot 46 --key "50:up 3000" --key "56:up 3000" \
    --key "62:up 3000" --shot 70 --shot 80
```

Three throttle applications move the car out of the pit box: the pit-lane
frame gives way to a view down the pit exit with the grandstand on the left,
the speedometer reads `7` mph and manifold pressure rises from `30` to
`37 in.Hg` while the tachometer holds 2000 rpm in first gear. By the last
capture the car has rolled further and come to rest — `0` mph, `30 in.Hg`,
engine temperature down to `192°F`.

That makes the renderer, the HUD and the vehicle model all observable from a
scripted run, which is the state the port has to be compared against. What is
*not* yet established is any of the code behind them.

## Not yet located in the executable

No menu, session or physics routine has been found in `INDYCAR.EXE` yet — the
flow above is behaviour, captured from the outside. The renderer's inner loop
*has* been located from a session sample; see [`renderer.md`](renderer.md).
The measured runtime map in [`executable.md`](executable.md) and the seeds in
`re/seeds.txt` are what a search for the rest starts from.
