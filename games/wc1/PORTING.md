# Porting plan

This is the per-slice implementation plan. The project strategy, workspace
rules, conventions, toolchain and the prioritised task list live in
[AGENTS.md](AGENTS.md); verified DOS data formats live in
[analysis/](analysis/). Keep this file describing *how the current slice is
built*, and put new findings about the original game in `analysis/`.

Status reviewed 2026-10-10: executable native title/flight/cannon-combat
prototype, with campaign/navigation/missile and complete behaviour gaps. The
diagnostic `FlightSceneDepthMerge` and full DOS/browser route remain Unproven;
source availability is not acceptance. This review does not rerun target tests.
**Correction, 2026-10-14:** the checkout is a Git repository (local, no
remote) and is included in the F030DOS publication copy at the owner's
request; "no Git repository, excluded from publication" is historical.

The hashed 1990 DOS `WC.EXE` binary and its captured execution are the
behavioural authority. `wc1-re` is supporting evidence, not a substitute for
DOS. A slice becomes supported only when each represented function has the
`METHOD.md` §4.2 record (DOS contract/fixtures, browser and Falcon symbols, and
an explicit difference ledger) and the deterministic browser reference plus
target checks pass. Use the browser harness to explore a function's role and
side effects, but confirm each resulting claim against DOS before recording it.

## Current vertical slice

`src/start.s`, `src/vbl.s`, `src/main.s`, `src/input.s`, `src/front.s`,
`src/game.s`, `src/object.s`, `src/mission.s`, `src/resource_io.s`,
`src/resources.c`, `src/c2p_fast.s`, `src/render.s`, and `src/hud.s` form the
current Falcon slice. The 68030 owns a 320x200 indexed draw buffer and
expands each completed frame through the loaded palette into a 320x200 RGB565
Videl back page. Each page is 128,000 bytes and is handed to VBL.
`src/c2p_fast.s` is the target presentation converter: it expands eight
indexed pixels per iteration and stores native RGB565 words directly. The
architecture-neutral `src/c2p.c` remains the golden-pixel reference used by
the host smoke test. The transformed indexed-shape renderer has a separate
zero-angle flight fast path with cached source-coordinate maps; the title
callback keeps that path disabled so attract timing remains independent of
renderer layout and cache effects.

The front end keeps the DOS `Title_Sequence()` frame counts: 25 opening
subtitle frames, 110 establishing frames, a 100-frame `TITLE.VGA` logo zoom,
eleven 70-frame credits separated by 40-frame intervals, and a 150-frame
tail. Its hidden-page conversion leaves VBL serviceable, and `front.s`
simulates logical title updates lost while a Falcon page is being transferred,
so the attract sequence reaches the menu on the source timeline instead of
stretching by the renderer's transfer latency. It renders the original
`TITLE.VGA` subtitle/credit font and logo data,
plus the seven `PLANETS.VGA` constellation sprites created by DOS
`generate_stars()`, projected through the original title script's 24.8 pitch
sweep. Its first action sphere retains the three Dralthi and one Hornet title
ships, drives their canned records 32–35, selects the original fighter view
frames, inverse-rasterizes the source sparse art at DOS angle/scale, and
performs record 32's `ShipExplosion()` hand-off through original
`OBJECTS.VGA` EXPLOSION1 frames. Record 35's seven paired laser-cannon bursts
use the original hardpoints, projectile velocity/lifetime, and section-six
sprite. The later credit action sphere now follows record 36's stock-memory
asteroid-field preload: source section-16 ASTEROID1..6 frames (including their
forward/reverse animation rules), three initial and up-to-twenty hazard slots,
source camera speed transition, movement ranges, and depth order. As DOS seeds
the field from its clock, the Falcon uses a repeatable local seed for now.
Record 32 also completes its source seven-object packet-four/packet-five debris
burst and its eight source-style constellation-dust particles. Asteroid
collision fragments and music remain pending. Escape skips
directly to that menu; Return or Space starts the current flight slice. The
flight frame order is:

1. poll the Falcon IKBD/TOS console queue;
2. advance the fixed-point player state;
3. render the space/cockpit scene, including cached mobile fighters through
   the DOS 3Space eye frame;
4. draw the HUD;
5. expand the indexed frame into the hidden RGB565 page; and
6. exchange the two Videl pages at VBL.

The flight background is now the source `generate_stars()` layout rather than
the earlier diagnostic dots: eight moving dust records and seven far-star
records use the retained `PLANETS.VGA` frames, the 24.8 eye-frame projection,
the source dust size/streak lattice, and off-screen respawn. The diagnostic
flight renderer now merges those records, compact-roster ships, cannon
projectiles/LASER_SPARKs, and `EXPLOSION1` effects through one bounded
far-to-near queue. Its 1990 DOS function identity, allocator slot order,
tie rule, and dynamic oracle fixture remain Unproven; see
`analysis/functions/FlightSceneDepthMerge.md`. Missiles, hazards, capital
internal effects, and the other omitted object classes remain outside it.

This follows the useful part of `F030Comanche`: platform setup and page
publication stay separate from game state and rendering. In particular, the
VBL platform seam owns the **active MC68030 VBR table** (`VBR+$70`), not a
hard-coded address-zero vector: TOS 4.04 may relocate its vector base. The
2026-09-10 capture exposed that omission by dumping TOS desktop/executable
memory after a nominal flight transition; see `analysis/hatari.md` and
`analysis/functions/FalconVblPresentation.md`. It does not copy Comanche's
terrain code because WC1 uses a different resource and object model.

## DOS behaviour slices

The following is a migration index, not a substitute for per-function records.
Each `wc1-re` reference must carry its build/fidelity grade and be confirmed
against `WC.EXE` or a DOS capture before the corresponding function can be
marked supported. The source reconstruction is divided into contracts rather
than a mechanical file copy:

| DOS reference | Falcon owner | Status |
| --- | --- | --- |
| `src/main.c`, `src/nav.c:Title_Sequence()` | `src/main.s`, `src/front.s`, `src/resources.c` | original title font, opening text, credits, logo zoom, menu, timing, seven-sprite constellation, title-script 24.8 camera pitch/projection, action-sphere-16 Dralthi/Hornet sparse sprites, record-32 EXPLOSION1, seven-sprite debris, and eight dust-particle hand-off, record-35 paired laser bursts, and record-36 stock-memory asteroid hazards; asteroid fragments and music passes pending |
| `src/cmpgn.c` mission packet records | `include/wc1_data.h`, `src/mission.s`, `tools/convert_data.py` | sections 0–3 cached as aligned big-endian records, including nav triggers/preloads and all three initial ship orientation fields |
| `src/nav.c`, `src/hudmsg.c`, `src/cockpt.c` nav/target hand-off | `src/game.s`, `src/object.s`, `src/hud.s`, `src/resources.c` | 24.8 active-sphere detection and roster replacement; `check_target()`'s retained/nearest-visible-hostile selection seam and target-slot HUD readout |
| `src/brains.c`, `src/logic.c` mission/object state | `src/game.s`, `src/object.s`, `src/resources.c` | player/initial spawns, entry-nav roster, triggers, and `fix_velocity()`-style three-axis forward movement |
| `src/ship.c`, `src/spc.c`, `src/geom.c` cannon collision base | `src/game.s`, `src/object.s`, `src/render.s`, `src/resources.c` | `fire_fixed_projectile_weapon()` loadouts for Hornet/Rapier/Scimitar/Raptor; source hardpoints, projectile speed/lifetime/refire, combined-radius `check_for_collision()`, `inflict_damage()` fore/aft shield and directional armor reduction, per-hull shield recharge, and retained OBJECTS.VGA sections 6/8/7/9 including LASER_SPARK. Internal systems, pilot damage, destruction, missiles, and enemy fire remain pending |
| `src/dib.c`, `src/screen.c`, `src/geom.c` raster contracts | `src/render.s`, `src/resources.c`, `src/hud.s`, `src/c2p_fast.s` | indexed-to-RGB565 presentation, original cockpit/target lock, source PCSHIP section-seven bars/lamps and readout positions, and the mobile-fighter eye-frame, 62-view, scale path; the diagnostic all-class depth queue is recorded separately as Unproven |
| `src/spc.c:generate_stars()`, `update_star_field()` | `src/game.s`, `src/render.s`, `src/resources.c` | eight source-style dust records and seven far-star records from `PLANETS.VGA`, projected in the flight eye frame with source dust frame selection and respawn; merged with the represented ship/projectile/explosion classes by the Unproven `FlightSceneDepthMerge` target seam |
| `src/disk.c`, `src/sdl/resources.c` packet/resource access | `src/mission.s` | INSTALL.DAT lookup; raw and Origin LZW mission sections |
| `src/sdl/resources.c`, `src/killbrd.c` packet/shape decoding | `src/resource_io.s`, `src/resources.c` | bounded generic packet loader; `GAME.PAL`, player `PCSHIP.Vxx`, and two `SHIPTYPE.Vxx` cache slots |

The exact mission disk records recovered by `wc1-re/src/cmpgn.c` are captured
in `include/wc1_data.h`. `tools/convert_data.py` decodes the complete campaign
packet on the build host and writes the known record fields in aligned
big-endian form to `WC1CACHE/MISSION.BIN`; `src/mission.s` validates and uses
that cache before considering the source packet. Its direct path remains the
reference fallback: it reads the first campaign archive through `INSTALL.DAT`,
decodes its LZW sections into bounded ST-RAM scratch, then copies only the
current mission's records, including each nav point's four trigger pairs and
two preload-type fields. `src/game.s` mirrors
`ReleaseStaleNavTarget()` with a three-axis 24.8 proximity test; `src/object.s`
rebuilds the player/initial roster plus the ten records linked to the newly
active nav point, then applies its trigger pairs. `src/resources.c`
separately loads raw or LZW packet sections through C-callable GEMDOS
wrappers, accepts verified `0xFF` fixed-index holes as empty sections, and
expands the original `GAME.PAL` CMAP to a Falcon RGB565 lookup table,
then applies the DOS cockpit reset for palette slots 185-191 so solid intro
sprites use the source dark-blue `$BF` entry rather than raw-palette black,
selects the
player's `PCSHIP.Vxx` cockpit with the `mode + 17` DOS logical-file rule,
retains its section-seven damage packet for source bar/lamp frames, and
loads the current nav record's two `SHIPTYPE.Vxx` preload types with
`type + 22`. WC1's DOS resource manager uses three object slots; three 72 KiB
Falcon slots still fit beside the stock 4 MiB machine's two 128 KiB RGB565
pages plus indexed surface and cover the largest supplied fighter shape. When the active sphere changes, `game.s`
queues its replacement preload work and `main.s` performs it outside the
masked update/render interval; `vbl.s` now restores the foreground registers
after tail-chaining TOS. `resource_load_flight_weapons()` separately retains
the player loadout's `OBJECTS.VGA` bolt and LASER_SPARK packets during startup,
then the VBL-visible tick only updates its source-sized forty dynamic projectile
slots. `object.s` initializes a native-endian per-slot shield/armor state when
it builds the active roster; `game.s` runs collision before movement and
shield recharge afterward, matching the DOS object-loop ordering.
`resource_flight_fire()` applies `position_child()` hardpoints and
`fire_weapon()`'s forward velocity/lifetime/refire fields; `render.s` projects
those retained sparse frames through the player eye frame. Sections 4–5,
subsequent campaign archives, internal damage/explosion state, and the
scanner/VDU/comms/pilot-hand cockpit resources remain future work.

## Falcon-specific decisions

- Use a linear indexed draw buffer, then expand through the DOS palette to
  Videl's 16-bit RGB565 true-colour surface. The original VGA layout is not
  reused as a rendering contract.
- Keep the indexed renderer and palette contract unchanged, then use
  `src/c2p_fast.s` for the Falcon presentation seam: direct native RGB565
  word stores and a bounded eight-pixel unrolled loop. Keep `src/c2p.c` as the
  architecture-neutral golden-pixel reference. The legacy DSP worker and
  `dsp-wire-smoke` remain isolated diagnostics and are not required to present
  the game.
- Install only the Falcon vectors the port owns and restore them on exit.
- Keep the first asset-free boot path deterministic so Hatari frame captures
  can validate timing, RGB565 video state, and page flipping before resource
  work begins.
