# DOS source map

This file is the index to DOS-function records and their Falcon owners. For the on-disk data
formats those functions consume, see [../analysis/data-formats.md](../analysis/data-formats.md);
for project strategy and tasks, see [../AGENTS.md](../AGENTS.md).

The hashed 1990 DOS `WC.EXE` binary and captured execution are the behavioural
authority. The local `wc1-re` reconstruction is graded supporting evidence
only. Each represented function needs the `METHOD.md` §4.2 record — DOS
identity/evidence, recovered contract and fixtures, browser/Falcon symbols and
a difference ledger — before it can enter a supported path. This map is the
current migration index and does not by itself establish any function's
contract. These are the initial groupings used by the Falcon port:

- `src/main.c` establishes the series/mission selection and outer game entry.
- `src/nav.c:Title_Sequence()` owns the animated intro and title-menu flow.
- `src/cmpgn.c` defines the packed mission records and loads 32 mission slots
  from the campaign packet.
- `src/nav.c` owns navigation labels, objectives, and mission flight-path
  presentation.
- `src/brains.c` and `src/logic.c` own the mission/object state machines.
- `src/ship.c` owns weapon selection, projectiles, damage, and explosions.
- `src/dib.c` and `src/screen.c` expose the software raster contracts used by
  the game-facing code.
- `src/disk.c` owns the logical-file/packet resource boundary.
- `src/sdl/resources.c` documents the Origin packet and LZW container rules.
- `src/killbrd.c` owns WC1's sparse shape-frame command decoder.
- `analysis/functions/PacketLoad.md` records the packet-loader seam; its
  verified `0xFF` empty-slot branch remains Unproven as a 1990 DOS function
  until the WC.EXE entry/range and direct return fixture are recovered.
- `analysis/functions/ShapeTransformAxis.md` records the Falcon-only
  zero-angle transformed-shape fast path; it preserves the existing indexed
  sample rule and is fenced out of the title callback so renderer speed does
  not alter the accepted attract cadence.
- `analysis/functions/FlightSceneDepthMerge.md` records the diagnostic
  bounded merge of the currently represented 3Space world classes. Its 1990
  DOS identity, source slot/tie order, browser fixture, and dynamic oracle
  comparison remain **Unproven**; it is expressly not a supported path.

The Falcon slice now ports a deliberately narrow part of that boundary:
`src/front.s` reproduces `Title_Sequence()`'s startup frame counts and Escape
skip. Its hidden-page conversion leaves the VBL serviceable and advances one
logical title update per completed page, preventing a slow transfer from
replaying the source sequence in bursts. `src/resources.c` retains the original
`TITLE.VGA` subtitle font, reads the opening text and the eleven credits from
the player's `WC.EXE` through the DOS pointers at DS:264E and DS:2767
([record](../analysis/wcexe.md#title-sequence-strings)), takes the
`get_right_shape()` frame/flip rows and the explosion debris sets from the
same data segment ([record](../analysis/wcexe.md#shape-and-debris-tables)),
and keeps the
three-frame fixed-point logo zoom and
the seven `PLANETS.VGA` frames selected by DOS `generate_stars()`, projected
through the title script's 24.8 pitch path. It also retains the original
Dralthi/Hornet shape packets for action sphere 16 and renders the four canned
records 32–35 through the standard fighter frame/flip/rotation path. Record
32's destruction now follows `advance_canned_sequence()` → `ShipExplosion()`
with original `OBJECTS.VGA` EXPLOSION1 frames and the source animation/growth
table. Record 35's command-three events now fire their two original laser
cannon hardpoints through `OBJECTS.VGA` section six with source velocity and
lifetime. The credit transition now follows record 36 and the original
`load_ship(OBJECT_TYPE_ASTEROID_FIELD)` stock-memory branch: section 16 backs
ASTEROID1/3/5 and the missing expanded-memory types fall back to them, section
13 is retained for later rock fragments, and a source-shaped 20-slot hazard
field starts with three asteroids. Their frame sequences, source velocity/
placement ranges, camera 150-unit speed, and depth order are ported. DOS seeds
this backdrop from its clock; the Falcon keeps a repeatable independent seed
until a target-side time policy is selected. It then presents the **Start Vega
Campaign** menu shape; Return or Space enters the current first-flight slice.
Record 32 also reaches `Create_explosion_debris()`'s source four-set,
seven-sprite packet-four/packet-five burst and its eight constellation-dust
particles, including their 40-tick lifetimes. Asteroid collision fragments,
music, save-game menu,
campaign alternatives, and pilot rooms are not yet ported.
`tools/convert_data.py` decodes the fully understood sections 0–3 and emits
aligned big-endian mission records in `WC1CACHE/MISSION.BIN`. `src/mission.s`
validates this versioned cache and uses it first; it retains the direct
`INSTALL.DAT`/`MODULE.000` Origin-LZW route as an asset-compatible fallback.
The converter does not blindly alter string, pixel, sparse shape, compressed,
or unknown packed data. `src/object.s` then
instantiates the player, the eight initial mission slots, and the ten records
attached to the entry nav point following the opening parts of
`prepare_mission()` and `set_up_action_sphere()`. It also retains nav trigger
pairs and preload types, and `src/game.s` follows `ReleaseStaleNavTarget()`
to replace the active roster when the player enters a different active sphere.
The current flight layer now uses the recovered DOS 24.8 fixed-point
representation for positions, full three-axis radius comparisons, and
`fix_velocity()`-style forward movement. It retains all three packed mission
orientation fields and projects cached mobile fighters with
`transform_objects_to_your_view()`/`get_right_shape()`'s eye-frame, scale, and
62-view selection rules. Its compact `check_target()` path keeps a selected
visible ship and otherwise chooses the nearest visible hostile from the active
roster (falling back to a friendly contact); the current HUD exposes that
active object slot pending the full cockpit target-box renderer.

`src/resources.c` is the separate, generic packet seam: backed by the
freestanding GEMDOS functions in `src/resource_io.s`, it reads bounded raw or
Origin-LZW sections from a named staged data file and accepts verified `0xFF`
fixed-index holes as empty sections. It expands the CMAP in
`GAME.PAL` to a Falcon RGB565 lookup table, including the DOS cockpit reset of
slots 185-191, and decodes `COCKPIT.VGA` section 0. Once
the mission establishes the player type, it applies
`InitializeCockpitResources()`'s `mode + 17` logical-file rule to load the
appropriate `PCSHIP.Vxx` cockpit. It similarly applies `load_ship()`'s
`type + 22` rule to cache the entry nav's two `SHIPTYPE.Vxx` preload types.
The renderer follows `DecodeShapeFrame()` in `wc1-re/src/killbrd.c` to draw the
original target lock, cockpit frame, and cached mobile-fighter shape as source
palette indices, preserving DOS transparent gaps. Its fighter pass follows
`transform_objects_to_your_view()` and `get_right_shape()` for the eye-frame
projection, scale, and directional frame. It also retains the player hull's
needed `OBJECTS.VGA` projectile packets before flight. `game.s` calls the
source-shaped `fire_fixed_projectile_weapon()` subset: Hornet, Rapier,
Scimitar, and Raptor guns use their exact enabled hardpoint records, bolt
velocity/lifetime, and refire delay in a forty-slot dynamic projectile pool.
Before movement, its cannon slots now reproduce `check_for_collision()`'s
ascending-slot combined-radius test and `object_collision()`'s
damage-capacity-minus-counter/2 shot damage. A hit takes the original
`LASER_SPARK` section-nine animation path while `inflict_damage()`'s
fore/aft shield and directional armor selection runs against the target's
native-endian three-axis frame; `replenish_shields()`'s per-hull cadence runs
after motion. The non-player `internal_damage()` branch now keeps its source
event loop and accumulation state, including pilot/system state, and
`ShipExplosion()` is represented by a
retained `EXPLOSION1` effect pool; destroyed contacts are removed from the
compact active roster. Capital onboard explosions/shockwaves and missiles
remain later source slices. Enemy fixed cannon fire is now sourced from the
recovered fighter loadouts: its range and forward-cone gates run before
owner-tagged projectiles enter the same dynamic pool, and the player damage
table is consumed on impact. Hostile fighter records use the same local-frame
target conversion for bounded yaw/pitch pursuit before firing.
`src/c2p_fast.s` expands each source palette index to one native big-endian
RGB565 word in the hidden Videl page, using the Falcon-specific unrolled
68030 presentation seam. `src/c2p.c` is the architecture-neutral reference
used by the pixel fixture. The old DSP C2P worker remains available only as an
isolated transport diagnostic; `make dsp-wire-smoke` no longer participates in
the game build or frame presentation.

The overall flight loop remains a diagnostic gameplay slice. It renders one
mission-selected cockpit and the player-plus-two-entry-nav preload shapes
through the mobile-fighter projection/view path and a bounded shared
world-object depth queue. `analysis/functions/FlightSceneDepthMerge.md`
records that queue's stars/dust, ship, cannon-effect, and `EXPLOSION1` merge:
the supporting 1996 routine names are known, but the 1990 DOS overlay entries,
source slot/tie order, browser reference, and dynamic oracle fixture remain
Unproven, so it is not a supported path. The three 72 KiB Falcon slots fit
alongside the stock 4 MiB Falcon's three frame surfaces; the largest supplied
fighter shape is 72,860 bytes. Fixed player and enemy projectile bolts are visible and
move with their source hardpoints/frame. They now convert to the original
impact spark, consume source shield/armor state, run the non-player
internal-damage branch, route enemy impacts through the player damage table,
and hand destroyed contacts to a retained `EXPLOSION1` effect. Missiles remain
outside this slice.
WC1's other cockpit and ship resources, behaviour dispatcher, sound, campaign
UI, later mission packet sections, and remaining
object classes are not yet ported. Later nav preload replacement is already
queued by the action-sphere transition and serviced outside the masked render
interval; the Falcon VBL trampoline preserves the foreground register state
while the TOS VBL chain runs.

`include/wc1_data.h` mirrors the packed `MissionHeaderDisk`,
`MissionNavPointDisk`, `MissionObjectiveDisk`, and `MissionShipDisk` records
from `wc1-re/src/cmpgn.c`, including their verified sizes. Keep that file in
lock-step with the DOS source when the campaign loader is implemented.
