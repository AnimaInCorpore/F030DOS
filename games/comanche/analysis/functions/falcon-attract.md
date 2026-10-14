# Falcon CPU attract route record

This is the durable source-selection record for the Atari Falcon 68030
attract-mode milestone. It is subordinate to the DOS executable and its
captured route; it does not promote the browser or a historical Falcon source
tree into an authority.

## Authority and route witness

| Field | Record |
|---|---|
| DOS image | `re/unpacked/COMANCHE.UNPACKED.EXE` |
| DOS SHA-256 | `4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697` |
| Trace method | QEMU TCG `exec,nochain`, repeatable attract inputs, and active-state snapshots |
| Trace runners | `work/run_qemu_exec_trace.py`, `work/trace_attract_report.py`, `work/inspect_qemu_state.py` |
| Route reports | `work/qemu_out/attract-trace-report.txt`, `work/qemu_out/object-state-walk.txt` |
| Source boundary | Only entries and resources reached by this route are active in the milestone; the DSP, live controls, sound, menu handoff, and completion paths remain dormant/Unproven |

The trace reaches the attract/frame driver, replay/flight integration,
mission-resource selection, the authored object factory, the 130-slot update
pass, the callback table and transient allocator, terrain/object transform and
draw pass, and the BULL/CHAF/ROCK/HELL/STGR/BOOM effect handlers. The shared
dynamic-bank assignments are BULL `00019E74`, CHAF `00019E78`, ROCK
`00019E7C`, HELL `00019E80`, STGR `00019E84`, and BOOM `00019E88`.

## Route

### Countdown correction (2026-09-05)

DOS side/title loops load ECX with 300 at `00005795` and 600 at `00005974`.
The corresponding `LOOP` instructions at `000057E0` and `00005AD6` consume that
saved counter after keyboard polling; poll flags do not determine expiration.
Fanfare loads 480 at `0000585B`, loops at `00005886`, and can also end on sound
completion at `00005882`/`00005884`. The silent Falcon milestone keeps its
existing fixed 480-tick fanfare policy; this is not proof of DOS audio timing.

A fresh no-key QEMU `exec,nochain` run used the DOS hash above, PC/486, 16 MB,
snapshot disk `img/comanche.hdd` with geometry 66/16/63, and `-dfilter
0xb6d0..0xbb23`. Flat base was `0x6040`; the captured entry bytes at flat
`00005690` matched the canonical unpacked image. Command, identity, register
snapshot, screenshot and trace are in `build/attract-dos/`. The trace recorded
600 title-loop entries at `000059ED`; side/fanfare loop-head blocks appeared
299/479 times because their first iterations share the preceding setup block.

Before correction, the Falcon's `.screen_no_key` branch consumed flags from
`tst.w input_events`, whose zero result expired the screen even with a nonzero
timer. A native baseline reached demo setup after only two attract ticks, at
VBL 639 (`build/attract-baseline/`). `tst.w attract_timer` now re-establishes the
intended counter condition immediately before the branch. This changes the
Falcon to match the recovered counter semantics; no new DOS behavior is added.
The browser already uses the explicit counter and needs no semantic change.

`tools/check-attract-timing.py` checks every observed counter value through the
600-tick title and 300-tick side paths, plus the silent fanfare policy, then
captures an actual completed flight frame. See the
[CPU compatibility record](cpu-compatibility.md) for both CPU results. These
logical-tick tests do not close the open DOS wall-clock cadence or full rendered
frame parity gates.

The active source route is:

```
00005690 attract entry
  -> opening screen / 000059ED animation tick
  -> 00018C29 / 00018D20 replay load and one-record feed
  -> 00018F94 flight integration
  -> 0000D3C0 frame driver
       -> 0000D950 terrain setup and 250-ring / 192-column CPU march
       -> 000234A4 descending 130-slot object update
            -> 00023A8C / 00023B50 / 00023CF0 / 00023F60 / 00023840 state handlers
            -> 000234E0 / 000237B0 / 000241C0 / 00024480 / 000244A0
               / 00024680 / 00024860 transient handlers
       -> 00024B17 transform, depth selection, and draw dispatch
            -> 00024E05 / 00024FED pair draw
            -> 0002514D model draw
       -> 00007AA0 surface/cockpit boundary
       -> replay/input boundary; next DOS tick
```

The opening route also reaches the DOS-backed image and overlay contracts:
`BACK.DTA`, `TPIC.DTA`, `RH66SIDE.DTA`, `ZOVE.RLE`, and `COMA.RLE`.
Each pass selects its authored D/C map, active P/NP palette, SKY bank,
mission SG slots, and `DEMO<n>.SCR` before the flight frame. The Falcon
keeps that dependency order and uses a linear RGB565 surface as a target
adaptation of the DOS 328×240 Mode X page.

## Attract route

DOS authority: `00005690-00005AE3`, with the opening-screen successor at
`000059ED`. The Falcon counterpart is `src/attract.s` and the startup boundary
in `src/start.s`/`src/main.s`. This record proves the pass counter, opening
resource order, replay handoff, and draw-before-tick boundary; TOS/VBL timing
and sound remain platform gates.

## Replay flight

DOS authority: `00018C29-00019A2D` and `00018F94-0001959E`. `src/demo.s`,
`src/game.s`, and `src/flight.s` consume the authored 13-byte header and fixed
8-byte records, preserve the 10.22 flight state until the documented 16.16
surface boundary, and integrate exactly one record per rendered frame.

## Menu

DOS authority: the menu/text and settings helpers around
`0002615C-00027276`. This family is deliberately dormant in the supported
attract slice; its source annotations retain the recovered DOS ranges and the
TOS/RGB565 counterpart without claiming live menu parity.

The Falcon counterpart is `src/menu.s`. The JavaScript attract runtime does
not expose this handoff. A complete menu-input fixture and a paired DOS/frame
comparison are **Unproven**.

## Frame driver

DOS authority: `0000D3C0-0000D8F5`. `src/frame.s`, `src/render.s`,
`src/object.s`, `src/hud.s`, and `src/console.s` preserve the snapshot,
terrain, object pass, restore, replay, and cockpit order. Double buffering and
VIDEL publication are Falcon platform adaptations.

## Terrain renderer

DOS authority: `0000D950-0000F317`, using the recovered HIGH.DTL tables and
the shared Q31 data. `src/render.s` is the CPU-only 250-ring/192-column
counterpart; no DSP implementation is active in this milestone.

## Resources

DOS authority: `00016381-0001687D`, the mission parser at
`000290C6-00029359`, and the mission factory inputs at `000068A5-00006947`.
`src/resources.s`, `src/mission.s`, and `src/sprite.s` preserve authored file
names, resource selection, little-endian fields, SG bank boundaries, and
palette/sprite data before native Falcon storage.

<a id="original-data-loader"></a>
### The original's tables at startup (2026-10-14)

Until 2026-10-14 the program carried about 90 KB generated from the local
install into `build/original_test.s`: the Q31 sine (`00032120`), the KF4b menu
font (`00027276`), the menu, name-entry and debrief texts, the roster and
settings defaults, the view, bearing and sprite-ramp tables, and HIGH.DTL's
ring tables and projection pages. None of it is now part of the program:

- `src/origexe.s` (`orig_exe_load`, run by `start.s` before `init`) reads the
  player's `COMANCHE.EXE`, checks it is the 1990 file (61,154 bytes,
  rotate-and-add checksum `$EFA67E1F`), LZEXE-unpacks the load image to flat
  `00032B20` (flat `F` is image offset `0x1700 + F`) and copies each table
  from the flat address `tools/prepare-original-test.py` uses, swapping the
  little-endian longs; it repacks the font and derives `sin_table` the same
  way. A missing or different file prints one line and exits before anything
  is changed.
- The ring tables come from the .DTL the detail byte selects: `dtl_cached`
  starts at the image's own `[0x25DAB]` value `$63`, which no settings byte
  matches, so the first `dtl_apply_settings` loads it - as `00026211` does.
  A failed first load stops `main`.
- `build/port_tables.s` (assembled) holds only the port's constants,
  `invz_table` and empty storage; `build/original_test.s` stays as host
  reference for the tools.
- Six tables the sources carried as `dc` lines go the same way: the ZOVE
  cycle `00028E75`, the COMA walk `000059C8`, the pan wobble `00005985`
  (`attract.s`), the matching ramp `0002B7D0` (`attract.s` and
  `resources.s`) and the RATE dither masks `00004998` (`sound.s`). A scan of
  every `dc` table in `src/` for its little-endian bytes in the flat image
  found no other of 16 bytes or more.

**Check.** `tools/check-orig-exe-load.py` runs `comanche_d.tos` in Hatari,
dumps every table at `snd_init` (the loader's, before `menu_init` writes into
the texts) and at `attract_start` (the .DTL ones) and compares them with
`build/original_test.s` and, for the six, the flat image: all 44 equal. `ring_invz_table` and
`ring_horizon_table` have no reader and stay zero. Shifting one copy's flat
address by a byte fails the check.

**Found on the way: `render_rebuild_horizons` overflowed.** The startup load
ran it for HIGH for the first time, and samples 79 and 80 (depth 512 and 528
map units) came out on rows 153 and 78 instead of 77: `depth << 23` wraps 32
bits from 512 on. No HIGH ring reaches that far (the last is at 492.6), so
those samples now take the fallback row, which is the generator's result.
A detail-level change in the menu would have hit the same bug before.

**Replay frames depend on startup time.** `flt_shake_rng`, the DOS PRNG that
places smoke and debris, advances on the Timer C stream (`flight_shake_tick`),
not per frame, so the particles at a replay record shift with how long
startup took. Record 20 (`tools/capture-target-frame.py --record 20`): the old
build with an inert 794-byte code pad is pixel-identical, but the old build
with nothing but a delay loop before `init` differs in 125 pixels, and with
one after it in 125. Intermediate builds of this change differed from the old
one in 61 and 58 pixels (particles over the target, then the right MFD); the
final build is pixel-identical to it at record 20. Compare replay frames with
this sensitivity in mind, or mask the particles.

## Object pass

DOS authority: `00023297-000234A4`, `00023A8C-00024997`, and
`00024B17-000253CD`. `src/object.s` preserves the 30-slot mission allocator,
130-slot descending update, callback/effect states, Q31 viewer transform,
HIGH.DTL page selection, depth ordering, and model draw dispatch. RGB565
surface writes are the explicit Falcon adaptation. Hatari capture at a later
replay tick is required to close pixel parity; source selection is already
route-proven by the QEMU reports above.

## Falcon source mapping

| DOS route contract | Falcon source | Kind | Status | Route proof |
|---|---|---|---|---|
| `00005690-00005AE3` attract state, opening screens, draw-before-tick | `src/attract.s` | adapted - TOS/RGB565 surface | ported | `#attract-route`, opening entries and transition order in the QEMU report |
| `00018C29-00019A2D` replay header/records | `src/demo.s` | translated | ported | `#replay-flight`, all four DEMO streams and fixed 8-byte records |
| `00018F94-0001959E` flight integration | `src/flight.s` | translated | ported | `#replay-flight`, replay-fed state transitions |
| `0000D3C0-0000D8F5` frame order | `src/frame.s`, `src/main.s` | adapted - Falcon double buffer | ported | `#frame-driver`, render/update/input order |
| `0000D950-0000F317` high-detail terrain | `src/render.s` | translated/adapted - CPU surface | ported | `#terrain-renderer`, HIGH.DTL 250×192 walk |
| `00016381-0001687D`, DTA/KRL/resource consumers | `src/resources.s`, `src/sprite.s`, `src/mission.s` | adapted - GEMDOS/native buffers | ported | `#resources`, named loads and decoded boundaries |
| `000068A5-00006947`, `00023297-0002349C` factory | `src/attract.s`, `src/object.s` | translated/adapted - native structs | ported | `#object-pass`, active slots and f2/f3 bank resolution |
| `000234A4` object update pass | `src/object.s` | translated | ported | `#object-pass`, descending 130-slot walk |
| `00024B17-000253CD` transform/sort/model draw | `src/object.s`, `src/sprite.s` | adapted - RGB565 sprite draw | ported | `#object-pass`, nonzero draw entries and HIGH.DTL scale |
| `N/A` TOS/Falcon startup, VIDEL, VBL, linear scanout | `src/start.s`, `src/vbl.s` | replaced - platform boundary | ported | Falcon build/start path; DOS behavior is not claimed |

The active build is CPU-only. `USE_DSP=0` is a source invariant for this
milestone, not a selectable behavior flag. DSP host/kernel sources are not
part of the supported link, and the CPU renderer is the only terrain path.

## Corrections of 2026-08-26

A function-by-function re-check of every `; DOS:` record in `src/` against
`re/listings/comanche-flat32.lst` corrected six recorded behaviours and a
group of citations. Each is fixed at the source, with the DOS instruction
named next to it:

1. `backdrop_build` (`src/render.s`) clamped the pitch limit to zero when
   `0x21 - hi8(|roll| * 0x40)` went negative. 00007D93/00007D98 hold 0x21 in
   the whole of `edx` and subtract `ah` from `dl` alone, so the limit is an
   8-bit difference zero-extended back: it wraps to 0xFF rather than going
   negative, and the clamp widens instead of closing. The guard was a second
   behaviour the original does not have.
2. `hud_refresh_clearance` (`src/hud.s`) computed 00019370's `shl al,1 / inc
   al` and 00019374's `sub al,[00019DFC]` in words with a clamp at 255, and
   built the map index with `lsl.w`, which shifts the row out of a 16-bit
   register and leaves the upper half of the index register standing. Both are
   now byte- and long-exact, and the write is gated to the above-ground branch
   as 00019391 is.
3. `frame_driver` (`src/frame.s`) pushed and popped `player_heading`.
   0000D3EA pushes the altitude byte [00019DFC]; the heading is not saved by
   the original at all. It also pushed the published 16.16 copies rather than
   0000D3DE/0000D3E4's 10.22 [00019CD4]/[00019CD8].
4. `frame_driver` stored the terrain history before the object draw pass, on a
   note that placed the object pixels outside the persistent surface.
   000234A4 ends in `jmp 0x24b17`, so the draw pass runs ahead of 0000D40E's
   transfer to the visible page and its pixels are part of what persists.
5. `instruments_draw` (`src/hud.s`) drew a hard element `0x09`. 00007403 reads
   `[00019D88] + 7`, and the selector is real state - 000063BB seeds it with 2
   at mission start, 00019B83-00019BC3 are its key writers. The fitted
   constant is replaced by the selector, seeded where DOS seeds it.
6. `sprite_overlay` (`src/sprite.s`) carried 00025880's function record. It is
   a capture harness with no DOS counterpart and is now labelled as one.

Citations corrected, with the reason each was wrong:

- `attract_tick_side`/`attract_tick_title` split the title tick at
  00005A1B/00005A1C, which is inside the six-byte instruction at 00005A1A, and
  labelled 000059ED "ZOVE animation tick" - the ZOVE tick is 0000579A-000057E0
  with its frame table at 0x28E75, not 0x59C8.
- `instruments_draw`, `hud_draw`, `hud_draw_sight_line`,
  `hud_plot_sight_pixel`, `object_state_move`, `object_reap` and
  `screen_roster_set_campaign` named addresses that are mid-instruction
  (00007443, 000077BE, 00025D31, 000248A0, 00028F39) rather than entries or
  range ends.
- `flight_reset` cited the flight handler for a value that comes from
  000063EC; `flight_tick`'s `.damp` cited 000194E0 for the damping at
  00019007-0001907C; `demo_start` cited the record consumer 00018CBC for the
  loader at 00019A2D; `object_init` cited the table's storage range for the
  reset code at 000227A6.

Differences newly recorded rather than closed, each naming the instruction it
drops: the keyboard turn term (0001908A-000190A5) and damage yaw
(000190AB-000190B4) in `flight_tick`; the crash shake counter
[00019DC0] (00019461) and the shake offset it drives through [00019DBC]
(00007DB5, 00015BBC); the sin/cos publication to [00019CB8]/[00019CBC]
(0001950F/0001951B); the third console blit and digit chain
(00007442-0000745F, 00007464 onward); and the replay record's key byte, which
00018CDB pushes into the 00001B70 FIFO for the unrecovered command chain at
0001959F - it is not the "save hotkey" the previous note called it, and the
shipped DEMO streams carry eight or nine of them mid-flight.

## Invented code removed, 2026-08-27

Follow-up to the corrections above, removing port-only mechanics rather than
annotating them. Each entry names what the original does instead.

1. **A second previous-position triple.** The object field map carried both
   `OBJ_PREV_X/Y/ALT` ("field 8", "field 9", "byte field 4") and
   `OBJ_HOME_X/Y/ALT` ("disp 0002107C", "disp 00021284", "disp 00021AA7").
   Those are the same three arrays. 00024860 and 00023B63 latch into them,
   00023AD0 and 00023C93 revert from them, and 000249C7-000249E9 restores X, Y
   and altitude out of them. The duplication meant the factory's placement and
   the state latch wrote different words and the terrain probe read the wrong
   one. The `HOME` set is gone and `OBJ_SIZE` drops from 84 to 72.
2. **A generic damage sweep (`object_reap`).** It walked all 130 slots, cleared
   every object whose damage byte had bit 0 set, and counted mission targets
   down. Nothing in the original does this: retirement is 000237BF's active
   clear inside the object's own wreckage state. It was dormant, but it was a
   second object lifetime sitting beside the recovered one.
3. **A mission target counter (`object_targets_left`).** Decremented in
   `object_state_wreckage` between the slot check and the end cue, where
   000237CC-000237FD has no such step, and in the sweep above. It had no
   remaining reader and is deleted.
4. **A live-object population count.** `object_live` was incremented and
   decremented across spawn, clone and retirement paths; 000227A6 and 000237BF
   keep no such count. The draw pass recounts its order array every frame
   regardless, so all five update sites were dead as well as invented. The
   recount stays; the counter's pretence of being game state does not.
5. **The console visibility apparatus.** `console_build_floor` derived a
   per-column "lowest visible row" table, a solid-row boundary and a ground
   fill row count from CONSOL1S.DTA. 00006FEF transfers the whole surface and
   the console is composited over it; none of the three exists. The floor's
   consumer had already been taken out of the marcher's occlusion seed - it is
   the `CONSOLE_BOUND` case rule one names - and what was left had no CPU-path
   reader at all. The row-span index over the asset's transparency survives,
   relabelled as what it is: a load-time index, not a recovered contract.
6. **The incremental console repaint.** `console_draw_upper` and the branch in
   `hud_draw` that called it repainted only the canopy above the solid row on a
   DSP frame and returned early. Both machines now compose the full console,
   as 00006FEF does every frame.
7. **`flt_crashes`**, a port-only collision counter with no reader.
8. **`SEAMLESS_WORLD`**, a third build option - dead, unread, and forbidden by
   rule one. The wrap it named is 00019359/00019362's ten-bit `shld` pair and
   needs no flag.
9. **`COL_COCKPIT` and `COL_COCKPIT_EDGE`**, two RGB565 constants with no
   derivation, no citation and no use. The `COL_MENU_*` family beside them is
   sound: its six-bit triples are the immediates 0002AA85-0002ABCC stores
   before calling the palette matcher, and every one matches.
10. **`clear_bottom`**, written unconditionally through a dead branch - the
    stump of the console-derived fill bound.

Two transcodes were corrected while collapsing the fields:

- `object_transition_home` wrote `prev = prev` twice and an extra altitude
  copy that 00024997 does not contain, and did its work in a different order.
  It now follows 00024997-000249E9 instruction for instruction. Its one open
  step is 000249B4's field-2 store of the shared BOOM bank pointer
  [00019E88], which this port has no binding for; that is recorded, not faked.
- `object_terrain_probe` ended in `cmp.b OBJ_ALTITUDE(a0),d0`, which on the
  68030 is `d0 - operand` and so carries the opposite sign to 00023B45's
  `cmp byte [00021A25 + slot], al`. Every current caller tests only equality,
  so nothing changed on screen; the flags are now the original's.

Nineteen routines carried prose provenance instead of the mandatory §4.2
record - among them `object_state_static`, `object_state_idle`,
`object_state_wreckage`, `object_scan_upper`, `object_terrain_probe`,
`object_factory_fill`, `object_factory_install`, the pair-draw family, and
`sprite_palette_rebind_bank`. Each was verified against its range and given
the full record; the difference each one hides is now written down next to it.

Measured cost: removing the console span bound and the incremental repaint
costs frame time, so a capture pinned to a VBL count now lands earlier in the
demo than it did. That is the correct trade under rule one - the bound was
never measured against the renderer without it - and it is why the acceptance
check is the attract flight, not a fixed tick.

## Accuracy: object/terrain occlusion, 2026-08-27

The marcher was audited against `0000D950-0000F317` group by group. Its shape
is the original's: the 0xC0-byte per-column horizon zeroed at `0000D96B`, the
two half-sweeps from the centre (`esp+0x77` down to `esp+0x18` is column 95
down to 0; the `pop/pop/push` at `0000E5E9` restores the ring centre and the
ascending half starts at `esp+0x70`, column 96), the byte-wide page lookup at
`0000D9F6`, the `ja` horizon test, the per-ring page advance at `0000F2DE`,
and the accumulate-from-the-previous-ring centre. All of that already matched.

One stage did not exist here at all. `0000F2E5-0000F2FF` copies the finished
192-entry horizon out to `[00019E60] + ring*256 + 0x20` at the end of every
ring, and the model blitter reads it back: `00025223/0002522E` point
`[00022358]` at the object's own ring, `000254CF/000254D5` load one entry per
surface column, and `000254D9`'s `cmp bl,bh / jb` drops every sprite pixel
sitting below the terrain in front of it. Without it, a model behind a ridge
draws straight through the ridge.

Implemented:

- `src/render.s` keeps `ring_silhouette`, one 192-entry row per ring in the
  port's screen-row units, and `render_ring_occlusion` resolves a ring's row
  the way `00025223` resolves its base.
- `src/object.s` publishes the ring `object_find_page` already searched for
  (`object_project_ring`) and arms `sprite_occl` around the model blit, as
  `00025223` arms `[00022358]`.
- `src/sprite.s` applies it in `sprite_draw_scaled`. `000254D9`'s test is
  monotonic in the row - the skipped pixels are always a contiguous run at the
  bottom of the column - so the whole run comes off the column's row count
  instead of costing a compare per pixel. The same pixels are written, in the
  same order. Non-object callers never arm the pointer and are untouched.

The source column is the DOS one: this port presents 192 source columns as two
pixels each and crops to the recovered page window, so `screen x >> 1 +
TERRAIN_VIEW_FIRST` is the entry `000254C0`'s `rol al,1` reaches on the DOS
surface. That mapping is `render_clear`'s, not a new one.

A second stage was missing with it. `00024D78-00024D82` and
`00025251-00025257` both refuse to draw an object whose projected page row is
below 1 or above 0xFD - those are the projection page's own clamps, so a row
landing on them means the projection ran off the page rather than resolving a
position on it. Neither of this port's two page lookups tested it; both do now,
and both report the refusal the way their callers already handle a no-draw.

Verified by Hatari capture at VBL 4600 and 5400: terrain, cockpit, HUD and
sight line unchanged, and sprites above the silhouette still draw. The scatter
of small marks high in the sky in those captures is SKY4.RLE's own content -
the night bank the attract pass selects with NP44 - not an object draw.

The span writer at `00006BF0-00006FEF` was checked at the same time: it is a
fully unrolled `mov [ecx],al / inc ch` chain, one pixel per row up the
256-byte-pitch surface, which is what `draw_span` already carries as its
documented true-colour adaptation. No deviation there.

## Accuracy: sprite placement, 2026-08-27

`src/sprite.s` was audited against the blitters at `00025880`, `0002599E`,
`0002590F` and `00025B27`. The original has three draw routines, not one, and
they are not interchangeable:

| DOS | bank | source | transparency | X placement |
|---|---|---|---|---|
| `00025880-0002590E` | `[00019E90]` | plane-chunked, row-major, bottom row first | opaque | `000258A6` shifts X - xoff right by two: a four-pixel VGA byte boundary |
| `0002599E-00025A4C` | `[00019E90]` | the same | `or al,al / je`, index 0 | the same |
| `00025B27-00025BB5` | `[00019E94]` | column-major, bottom row first | `or al,al / je`, index 0 | `00025B94` takes the plane from the low two bits of X - xoff and `00025B9F` the byte column from the rest - nothing is quantised |

(`0002590F-0002599D` is the fourth: the same geometry read backwards, screen
into bank, saving the background behind a moving sprite. This port redraws the
frame instead and does not need it.)

The console's fixed elements and the attract overlays go through `00025880`
(`00007420`, `0000743D`, `000077B8`, `000057C3`, `00005A74`); the HUD's own
elements and the value glyphs go through `00025B27` (`0000D882`, `000074A7`,
`0000751D`, `00007633`, `0000778B`). This port had one writer with the
quantisation always on, so **every HUD element was being snapped to a
four-pixel grid the original places to the pixel** - including the velocity
sight ring at `0000D882`, whose whole job is to sit exactly where the velocity
vector points. `sprite_blit` now takes the placement rule as a flag beside the
mask flag, and the two entries carry the DOS routine each one is.

Which bank belongs to which blitter is now settled by the data rather than
assumed. Every frame's payload in all 21 installed banks is exactly
`width * height` bytes, measured from the gaps between consecutive data
offsets. `00025880` reads `4 * (width >> 2)` bytes per row, so it can only
draw a bank whose widths are all multiples of four - and that is exactly
CONS.RLE, COMA.RLE and ZOVE.RLE, the three it is called with. Every bank with
a width that is not (TANK, HELL, HOKE, ROCK, STGR, TURR, RADR, LH66, HUDS,
BOOM, BULL, CHAF, SPIN, FUEL) is drawn by a column-major routine. The
deplaner's comment claimed a ceil chunk split as the original's rule; the
original's is `width >> 2`, equal chunks, and the two agree on every bank it
ever sees.

Left open, recorded rather than guessed: `[00019E94]`, the bank pointer
`00025B27` reads, has no writer anywhere in the disassembled range -
`[00019E90]` is written at `0000575B`, `00005920` and `00028E51`, and
`[00019E98]` at `000058D4` and `000064A8`, but its neighbour never is. The
port passes the bank per call site, so nothing depends on resolving it yet.
Also unported: `00025B27` reads the X offset with `movzx` where `00025880`
uses `movsx`. Only CONS.RLE has frames with the high bit set (46 and 48), and
those are drawn through `00025880`, so no shipped frame can tell the two
readings apart.

## Accuracy: mission parser and object heading, 2026-08-27

`src/mission.s` was checked field for field against `000290C6-00029359`, with
the shipped `0.MIS`/`1.MIS` decoded (XOR by `0x11120603`, `0002A2F8`) and read
alongside. The scalar and record layouts match: family, start X/Y `shl 22`,
angle `shl 24`, the two bytes, the six, the one, the eight damage bytes each
less one, the target total, then `f0..f10` per record with X and Y at `shl 22`.
The six line skips that cross the scalars land exactly on the first `*` record
in every mission block. Four things were wrong or missing.

**The object heading byte was in the wrong convention.** `object_move` added
both terms and read the heading through this port's inverted player
convention; those two errors cancel, so objects moved correctly and
`OBJ_HEADING` held a byte that was not `0002189F`'s. But `00024CA8` adds that
same byte straight into the model's aspect index, and `00023835` fills it from
`[00019D04] >> 24`, so the stored byte has to be the original's. `000248E4`
subtracts the Y term (`sub dword [Y], edx`) exactly as the flight core does at
`00019528`. Fixed at the sign: `object_move` now subtracts, the mission
parser stores `f6` raw, `object_state_fixed` takes `flt_angle >> 24`, and
`object_aspect` is left alone because it was already right. `mission_heading_import`
now applies only to the player's start heading, which is the one value this
port genuinely keeps inverted.

**The end-of-mission cue could never fire.** `00029240` zeroes `[0002824B]`
and `0002926C` counts one per `*` record; `object_state_wreckage` walks that
count down at `000237DE` and raises the cue at zero. Nothing here seeded it,
so `000237DC`'s test always found zero. `mission_parse` now counts the `*`
records and `object_spawn_mission` seeds the countdown. Every shipped mission
has a non-zero count (0.MIS 8-20 per block, 1.MIS 3-26).

**The mission target total was not counted.** `000292C0-000292CC` counts
records whose `f1` is 2 or 3 into `[00028260]`. Recorded now as
`mission_target_count`. (This is the total the removed `object_targets_left`
decrement was pretending to serve; the count is real, the decrement was not.)

**Two bounds were missing.** `00029186` rejects a family index above 5 -
`0002919A` indexes a six-entry table at `0002A984` whose only non-trivial
entry is index 1's night-vision transform at `0002A99D`, the rest pointing at
the bare `ret` at `0002A99C`, which confirms the port's `mission_kind == 1`
gate. And `00029292` aborts the parse once the record index passes 30. The
port now rejects both instead of carrying on. Recorded rather than reproduced:
the original's per-record byte arrays are `0x1E` apart, so its own 31st record
writes one byte into the next array; no shipped mission has more than 30.

`resource_palette_variant` was checked against `0002A99D-0002A9E5` and is
exact - the `(2R + 5G + B) >> 3` brightness, `brightness >> 2` red, the
`+ 10` green clamped at `0x3F`, and `(B + brightness) >> 1` blue. The original
computes those in byte registers and this port in words; six-bit inputs cannot
reach the wrap either way.

## Audit: menu.s and screen.s, 2026-08-27

The last two unaudited files. Neither is on the attract route - the cycle only
reaches them through `attract_stop` - and every routine in them is already
marked partial, so the standard here was to establish what the original does
and record it, not to change layout that no capture can check.

Verified exact:

- `screen_draw`'s list geometry is `00027DD9-00027DE1`'s to the byte:
  `bl = 0x0E`, `bh = 0x34`, `dl = 0x1E`, `dh = 0xA0`, and the port's
  `SCR_BOX_X = $0E*4` / `SCR_BOX_W = $34*4` convert the box's byte columns to
  pixels while Y and H pass through. The row pitch is `00027E7B`'s
  `add ebp, 0x3D8` - 12 rows of `0x52` - which is `SCR_ROW_H = 12`, and
  `00027E3C` uses the same 12 for the highlight.
- `menu_box`'s line order and its `bh - 1` top run match `0002628E`: the box
  is drawn with Map Mask `0x0F`, so its width is in four-pixel byte columns
  and the top line's one-short run plus `0002630E`'s Map Mask `0x07` single
  byte is `bh*4 - 1` pixels.
- `menu_hotspot_add` matches `00027042-0002706E`: the pen position less the
  page base `[00019CAC]` and the pan `[00019DC4]`, the id beside it, and the
  count at `[00026590]` incremented.
- The interpreter's control bytes are the original's: `0xFC` skip, `0xFE`
  hotspot, `0x00`/`0xFF` end, `0x7C` escape with `0x72`/`0x67`/`0x62` colour
  selectors at `000270B7-000270D0`, and `0xFD` at `00027176`.

Two records were wrong and are corrected:

- `menu_text_width` cited `000268DB` as a string-width reader and claimed
  control-byte skips as preserved. `000268DB` is the inner loop of the block
  measurement at `000268C5-00026915`, which walks a table of block pointers at
  `000265A0`, skips each string's first byte, and finally stores
  `(widest + 0x12) >> 2` as the box byte width at `000265FF` and the line
  count at `000265F7`. `000268E4` adds the width-table entry for **every**
  byte between the terminators - it does not discount the escapes, and the
  table at `0002727E` has real widths for them (`0x7C` is 2, `0xFD` is 4, and
  126 entries above `0x7F` are non-zero). The port's skips are therefore a
  difference, not a preservation, and a string carrying colour escapes
  measures narrower here than in DOS. Recorded as Unproven rather than
  changed: there is no capture of the menu to check a layout change against.
- `menu_radio_init` cited "shipped menu defaults in 00025DBC-00025DDF". Most
  of that range is not menu data: `00025DBC-00025DC7` is the analogue
  calibration block the replay loader reads at `00018B82-00018C23` - three
  min/centre/max pairs, 999/999/200 and 200/999/999 in the image - and what
  follows it is a string. Only `00025DD9-00025DDC` is menu state, patched into
  the block drawer at `000268A5-000268BE`. No DOS routine that reads a
  defaults table has been traced; the marked line comes from the authored
  strings, and that is now what the record says.

## Verified against DOS memory: backdrop_build, 2026-08-27

The first result from `work/dump_marcher_tables.py`, which reads the original's
own BSS over QMP. `0x3CB40`'s 192-byte horizon array is what `backdrop_build`
computes, and the port reproduces it **to the byte at three independent
cameras** - 0/192 mismatches at roll -133, -111 and +27, each sitting on its
pitch clamp, with the arrays wrapping through 0/255 mid-array exactly where
the byte arithmetic puts the wrap.

That confirms, against the original's memory rather than against a picture:
the transform and its clamp, `[00019D80]`'s base, both half-sweeps, the turn
at `0000968A` that zeroes accumulator and rounding together, the `sub`/`add`
sign flip across the centre, and the byte wrap.

It also corrects one of this session's own claims. The pitch-limit guard
removed earlier was a genuine invention - `00007D98` subtracts into `dl`
alone, so the limit wraps rather than going negative - but the roll is clamped
to +/-133 at `000190FB`/`00019107`, which caps `hi8(|roll| * 0x40)` at exactly
`0x21`. The limit can never reach the wrap on this path, so the change is the
correct transcription and not a visible fix. The capture is what settles that
in either direction, which is the point of having it.

**The producer is decoded too, and it corrects the plan's next step.**
`sub_00006FEF` builds the run list by scanning the surface row by row for
spans that are not `0xFFFFFFFF` - `0xFF` is the not-painted marker - and
emitting one run per span. It is an incremental-update mechanism: it says
which spans changed, and carries no projection information. The note written
earlier the same day, that the run list was the next thing to reduce for the
silhouette, is wrong and is corrected in `docs/PORTING-PLAN.md`.

What it does settle is the surface-to-screen anchor, independently of the
transfer: the source starts at `[00019E70] + 0x2011` (surface row 32, column
17), the destination at `[000014C4] + 0x39FA` (VGA row 181 exactly, since
`0x39FA / 0x52 = 181`), and 182 rows run with the source increasing while the
destination decreases by `0x52`. So `screen row = 213 - surface row`, which is
`RING_PAGE_ANCHOR` and `OBJECT_PAGE_ANCHOR` confirmed from the producer.
`000055DE` fixes the surface at `0x00040000` once and never moves it.

The same dumps supersede the recorded shape of the surface transfer's tables.
`00007AA0` reads a **run list**, not four per-column tables: `0x38B20` holds a
run length with the two odd-byte plane flags in its high word, `0x32B20` a
source offset, `0x3AB20` a pointer to that run's source base, and `0x34B20`
the destination in either of two halves selected by `[00019D87]`, for
`[00019E4C]` entries. The capture shows 261 runs of length 1 to 82 over 176
source bases eight bytes apart. That run list is the next thing to reduce for
the terrain silhouette, and it is now data rather than a question.

## The terrain oracle exists, 2026-08-27

`work/dump_marcher_tables.py --surface --shot --wait-flight` captures the
original's 256x256 terrain surface out of flat `0x40000`, with the camera that
drew it and a screendump that proves what it is. A confirmed frame: camera
`x=0xFE5CE640 y=0x40759FD2 angle=0x4EE24A19 alt=128`, 261 transfer runs,
`screen-11.ppm` showing the original in cockpit view over lit terrain.

Two guards were needed, and both were found by getting it wrong first:

- `[00019ED0]` read as 1 at 3.5 seconds - before DOS had booted - and the
  first capture was uninitialised memory. The tool now waits for 16 bytes at
  `0x25880` to match the image before believing any read.
- "Fraction of the window painted" looked like a way to tell terrain from a
  full-screen image. It is not: the sky is drawn into this same surface, so a
  good terrain frame is ~90% painted and `0xFF` marks only what no span
  reached. Two captures were read as "not terrain" on that basis and were
  terrain. The screendump settles it, which is why the tool takes one.

This is what the eight parameter fits never had. The comparison itself is the
remaining step: `tools/compare-silhouette.py` is retired with the pinned
camera it depended on, so the surface needs `tools/compare-terrain.py` taught
to read a raw surface, or a comparator of its own. The dump is the better
input either way - no PCX decode, no palette round trip, and the camera in
the JSON beside it.

## The projection is 1:1 now, 2026-08-27

The terrain package was generated from HIGH.DTL. The shipped install runs
MEDIUM: `00026240` loads `medium.dtl` when the detail byte `[00025DD4]` is
`'1'`, and two QMP captures of the attract flight both read the resulting
count `[0x19EE0] = 180`, with slope and bias arrays byte-identical to
`medium.dtl` at offsets 2004 and 3004.

The offsets are the second half of it. `00015ADA` and `00015B0A` read the
slope and bias from the absolute addresses `0x1A6B4` and `0x1AA9C`, and the
marcher reads its increments from `0x19EE4` and `0x1A2CC`. Against a file
loaded at `0x19EE0` those are +4, +1004, +2004 and +3004 - the table
boundaries of a 250-entry file, and *not* of the 180-entry file actually
loaded. The original reads them anyway, so the port must too.

`00015AD9` is now decoded and verified: its formula reproduces the original's
own built pages 180/180 from the captured inputs, and after pointing
`tools/prepare-original-test.py` at `medium.dtl` and the original's fixed
offsets, the port's generated `ring_page_table` is **180/180 identical to the
pages dumped out of the running original**. `OBJ_RING_STEPS` follows from 250
to 180; the object ring search had been walking 70 entries past the end.

Status changes: `render_horizon_for_depth` and `object_find_page` now index a
table that is the original's byte for byte. The 21-row silhouette spread that
survived eight parameter fits was this - the wrong detail level's data read
through the right program's offsets - and the standing instruction not to
adjust the marcher was correct: nothing in the marcher needed adjusting.

## Terrain data package: verified 1:1, 2026-08-27

Every table the marcher consumes is now confirmed byte-for-byte against
memory read out of the running original (`work/dump_marcher_tables.py`):

| Port table | DOS address | Result |
|---|---|---|
| `ring_b_table` (lateral increment) | `0x19EE4` (file + 4) | **180/180** |
| `ring_a_table` (forward increment) | `0x1A2CC` (file + 1004) | **180/180** |
| `ring_z_table` (cumulative depth) | `0x1AE84` (file + 4004) | **180/180** |
| `ring_page_table` (projection pages) | built by `00015AD9` | **180/180** |
| backdrop horizon | `0x3CB40` | **192/192** at three cameras |

That is the whole input side of the terrain renderer, and it settles the
question the eight parameter fits were really about: none of these values was
slightly wrong, they were the wrong file's.

## The emitters are self-modified; the marcher is not (2026-08-27)

Diffing the running original's code against the image over `0x06BF0-0x0F320`:

```
span writer 06BF0-0AF50:    1 run patched
emitters    0AF50-0D350:  382 runs patched
MARCHER     0D950-0F320:    0 runs patched
```

**The marcher's walk is not self-modifying.** Static reading of
`0000D950-0000F317` is therefore complete, and any model that disagrees with
the original is misreading code that is plainly there - not missing a runtime
patch. That narrows the remaining search to a re-read rather than a capture.

**The emitters are, twice per column.** Each block's
`mov al, byte [ebx + 0xFFFF]` displacement is patched to the live colour-map
base, and each block's `add ch, 0` at +0x12 is patched with a small value
(0x1A, 0x19, ... varying by column). That second site is `0x0000AF62` for the
first block - which is exactly where `backdrop_build`'s walker stores at
`00007E02`, alongside the horizon byte it writes to `0x0003CB9F`.

So the backdrop shear and the terrain spans are the same quantity applied
twice: the walker writes each column's horizon byte into the sky array AND
patches it into that column's span emitter, so a span starts at
`old occlusion + that column's horizon offset`. The port's `draw_span` starts
its span at the stored occlusion row with no per-column term. That is a
recorded difference to settle next, and it is now evidence rather than a
guess.

**Why the marcher could not be measured, and what to do instead.**
`sub_0001B26C` is a second marcher - the side/rear view - reached from
`00007909` after the terrain pass. It recomputes `[0x19CB0]`/`[0x19CB4]` for
its own bearing and `0001B84E` writes its silhouettes into the same
`[0x19E60]` region as `0000F2F1`; its caller rewrites `[0x19D00]` at
`00007903` and subtracts from the camera X at `000078FA`. Any sample taken on
a timer therefore describes a different view than the silhouettes beside it,
and the decaying-with-depth error that looked like an accumulation bug is the
signature of exactly that bearing mismatch. The capture needs a breakpoint at
`0000F317` - the marcher's `ret`, after its last silhouette copy and before
`00007AA0` and the rear-view pass. `work/gdbstub_probe.py` is the tool for it.

Ruled out on the way: the emitter at `0000AF50` is not a suspect. It stores
the new projected row unconditionally, takes the span length as old minus
new, indexes the unrolled writer at `0x6BF0` by it, and returns to
`0x0000DA05` without touching the walk's accumulators.

**Still open: the marcher's own arithmetic.** The reference is now sound -
`0000F2F1`'s per-ring occlusion copy, captured for all 180 rings - and
`tools/compare-marcher.py` scores a model of `0000D950` against it. The model
does not reproduce the original: 18.1% of columns exact overall, 184/192 at
the first ring with any structure, decaying with depth at a mean error near
-1.5 rows. That shape says accumulation in the ring centre, not a structural
misreading. Signedness is ruled out - neither increment table reaches 2^31.

Two corrections to earlier notes in this same document, both mine:

- The "80 bytes of 0xFF" in the reference window was an `xp` text-parsing
  artefact, not memory. A `pmemsave` of the region shows solid data.
- "Rings 0-2 exact 192/192" proved nothing: those rings are uniformly zero in
  the reference, so any model matches them. The harness now skips uniform
  rings by default for exactly this reason.

The rule stands and is now enforced by the harness's own output: do not tune
the model, and do not tune the port to the model. It confirms a reading of
0000D9E9-0000DA29; it must not be used to search for one.

## Invention sweep, 2026-08-27 (second pass)

Four of the five outstanding items closed; one deliberately not.

1. **`draw_span`'s "missing" per-column term did not exist.** It already
   subtracts `backdrop_dy[col]` from both ends of the span, which is
   `0000AF5E`'s shifted start with an unchanged length. The earlier note
   claiming otherwise was wrong and is withdrawn.
2. **The deplaner's ceil chunk split** is now `000258C6`'s `width >> 2`,
   equal chunks. Indistinguishable on every bank that reaches it, so this
   costs nothing and removes an invented rule.
3. **The object order array** is now `00024B77`'s identity fill over all 130
   slots, sorted whole and walked whole with the active test inside the loop,
   as `00024BCB` does. The compaction is gone and with it `object_live` - a
   population count the original does not keep and that four routines had
   been maintaining as if it were game state.
4. **Three never-read diagnostic counters** (`object_culled_range`,
   `object_culled_fan`, `object_drawn`) deleted.
5. **`menu_text_width`** now adds the width-table entry for every byte
   between the terminators, as `000268E4` does, instead of skipping the
   interpreter's control bytes. `MENU_TAB = 6` was checked and is correct:
   `0002717B`'s `inc ebp` is four pixels and the two mask shifts add two.

**Not fixed, and stated as such: `menu_radio_init`.** The settings are four
characters at `00025DD4`. The image ships `'2','1','1','4'`; a capture of the
running game reads `'1','0','0','3'`, with the cached copy at `00025DAB` also
`'1'` - so `COMANCHE.CFG` is loaded over them by a mapping that is not a
straight copy. Only the first byte is traced (`00026211`, which is why this
port generates from medium.dtl - a third independent confirmation). The other
three have no traced consumer and no known character-to-line mapping, so the
back-tick scan stays: replacing it with a guess would be the same invention
somewhere else. The evidence a future trace needs is recorded at the routine.

## Trace-seeded disassembly, 2026-08-27

A 90-second QEMU `-d exec,nochain` trace of the attract cycle: 34,458,026
block executions at **2,701 distinct entry points**, all inside the flat
program region. Re-disassembling from those seeds and merging over the
heuristic listing gives 63.1% coverage, up from 59.3% - but the number is the
lesser half. Every traced entry is a point where the instruction alignment is
*proven*, which is what settles the code-versus-data question the heuristic
listing cannot answer and which AGENTS.md warns against treating as answered.

Workflow and the extraction trap are in `docs/RE-WORKFLOW.md`;
`tools/re/trace-seeds.py` is the reducer.

**One live behavioural difference confirmed.** The in-flight command chain at
`0001959F` executes 26 distinct blocks during the attract. This port drops the
replay records' key bytes because that chain is unrecovered - a difference
already recorded at `demo_tick`, but recorded there as though its consumer
might be dormant. It is not dormant; the original runs it during the very
sequence this milestone reproduces, so the dropped keys are a live divergence
in the attract, not a deferred one.

**Two of my own claims from this session, corrected by the same trace.**

- `0002ABD0` is *not* code. An earlier reading of the trace put the hottest
  address in the game inside that table; that was an extraction error (see
  below) and the port's "squared colour tables" citation was right all along.
- The 96-column renderer at `000137F0` does *not* execute in the attract. An
  earlier count of 73 blocks there came from the same error. `[00025DD9]` is
  `'}'`, `[00019C94]` is `0x0000D950`, and the trace agrees: zero entries in
  `000137F0-00014000` or in its emitter bank at `00010760`.

Both came from reading QEMU's `pc` field as EIP when it is the **linear**
address: the flat address is `pc - cs_base` with `cs_base = 0x00006040`. Off
by `0x6040`, the seeds render tables as overlapping nonsense - and that
nonsense is what exposed it. The corrected reducer documents it at the top.

**Not reached by an attract trace**, and so still open: the menu region
`00027276-00027D92`, the 96-column renderer and its emitter. Those need a
trace driven with `--key` into the menu, and one taken under a configuration
that selects the other renderer.

## The replay's in-flight commands, ported 2026-08-27

The trace proved `0001959F` runs during the attract, so the dropped record key
bytes were a live divergence rather than a deferred one. Two of its cases are
now ported - and they are exactly the two the shipped DEMO streams carry:

```
0x1A '['   00019649  dec [00019D88];  if it went negative, set 5
0x1B ']'   0001965E  inc [00019D88];  if it reached 6, set 0
both       00019674  [00019D89] = 1, then call 000073D0
```

`[00019D88]` is the console page `instruments_draw` reads as element = page + 7
(`00007403`). Until now the port held page 2 for the whole attract while the
original stepped it; a capture at VBL 4600 now shows the lower-left readout on
a different page - "WINGMAN" where it read "CANNON" - which is the recorded
keys arriving.

Placement follows the original's loop rather than the record read: `00018CDB`
pushes the byte into the `00001B70` FIFO inside the frame driver, and
`00006AF4` pops and dispatches it immediately after `00006AEE`'s call to that
driver returns. So `frame_driver` parks the byte at `demo_tick` and dispatches
it after `game_tick`, before the console is drawn - which is also why
`00019674` calls `000073D0` itself.

Not ported, and named at the routine so the gap is legible: `0x28`/`0x27`
(the weapon paths at `00022A00`/`00022AA0`), `0x3B-0x40` and
`0x41-0x44`/`0x57`/`0x58` (the left and right MFD page selects through
`[000072E6]`/`[000072E7]`), and `0x02` (the console variant load through
`[00019D86]`, `consol1s.dta` at `0001969D`).

## menu_radio_init closed by a keyed trace, 2026-08-27

The last known invention. A second exec trace driven with `--key` into the
menu (`spc` exits the attract; `[00019ED4]` goes 1 -> 0) reached the menu
chain at `00028C3E`, the list menu at `00027DB4`, the text interpreter, the
bevelled box and the block measurement at `000268C5` - 2,931 distinct entry
points across both traces.

That exposed the mechanism at `00025EB3-00025F7D`. For each group the original
writes `0x20` into every one of that group's mark slots, then compares the
group's setting character against `'0'`, `'1'`, `'2'`, ... and writes `0x60`
into the slot that matches. **`0x60` is a back-tick** - so the back-tick this
port was scanning for is DOS's own mark, written in by this routine, not
authored text. The port had the dataflow inverted: it read the mark to infer
the setting, which left a setting no way to move a mark, and the handlers at
`00026BD9-00026BFA` and `00026CC6` write exactly those setting characters.

`menu_radio_init` now runs the original's direction, over the group slots
already recorded in `menu_radios` (`000266B8`/`000266C5`/`000266D2` for sound,
`00026712`/`0002672A`/`00026743`/`00026755` for control), with the character
selecting the Nth entry of its group.

The four characters are recovered rather than asserted: a QMP capture reads
`00025DD4-00025DD7` as `'1','0','0','3'`, and `00026211`, `00025F07`,
`00025F42` and `00025EC1` resolve those bytes as detail, sound, music and
control - Detail Medium, Sound Loud, Music Loud, Keyboard, which is what the
port had claimed all along and can now show. The `COMANCHE.CFG` parser that
fills them is still untraced and is recorded as the remaining difference.

Still unreached by either trace: `00027276-00027D92`, and the 96-column
renderer at `000137F0` with its emitter at `00010760`.

## Visual comparison against the same attract pass, 2026-08-27

Captured the original's attract cycle through QEMU while reading the pass
counter `[00019ED5]` and the replay flag, so the port and the original can be
compared on the *same* pass rather than on whichever frame each happened to be
showing. That matters: a DOS daylight frame next to a port night-vision frame
looks like a palette bug and is not one. On pass 1 both are the green
night-vision presentation, which confirms the NP44 variant path.

Differences found, on matching passes:

1. **The HUD's numbers were malformed** - the port read `SPEED:1 1` where the
   original reads `SPEED:106`. `0000D8F5` zeroes `edx` before every
   `div ecx`, so each divide gets a clean 32-bit dividend. `hud_draw_value`
   was feeding `DIVU.W` a `d4` whose high word still held the previous
   divide's remainder (`move.w d3,d4` writes only the low half), so the tens
   digit came from a garbage dividend. Now `DIVUL.L`, which is the 32-bit
   divide `div ecx` actually is. Verified: `SPEED:121`, three clean digits.
   The clearance readout shares the routine and is fixed with it.
2. **Both MFD panels are empty.** The original shows a top-down moving map in
   the left panel (terrain from above, a waypoint marker, a crosshair) and a
   second terrain view in the right. Located but not ported:
   `000072EB` draws the F-key tab highlights (un-highlight `[000072E8]` as
   element `page*2+0x0D`, highlight `[000072E6]` as `page*2+0x0E`, then the
   same pair for the right side), and `00007580` draws the left panel -
   `call 00015855` with `[00019C90]` and `edi = 0x37CE` to build the image,
   then element 3 through the masked blitter at X `0x70`, Y `0xCE`.
3. **CHAFF/FLARE do not count down** - the original's read 06/21 against the
   port's 24/24. `000074C0` draws them from `[00019D8D]`/`[00019D8E]`, which
   the mission parser fills from `0.MIS`'s `24,24` line (a third independent
   confirmation of that parse); what is missing is the weapon system that
   decrements them, which is outside this milestone.

## The left MFD map view, ported 2026-08-27

`00007580` calls `00015855` with the zoom in `ebx` and a destination of
`0x37CE`; `00015855` forms the view basis, offsets the origin and calls
`0001591A` once per Mode X plane, advancing a quarter step between planes;
`0001591A` samples one row. Recovered from those three:

```
basis      esi = high32(zoom * [00019CB0]),  ebp = high32(zoom * [00019CB4])
origin     X = [00019CD4] + 8*esi,  Y = [00019CD8] - 8*ebp        0001587B
per pixel  X += ebp/4,  Y += esi/4                                000158AA
per row    X -= esi/4,  Y += ebp/4                                00015ABD
sample     index = (Y>>22)<<10 | (X>>22) into [00019E64]          0001592A
extent     20 bytes per row, written outward from the centre -
           0x0A..0x13 forward and 0x09..0x00 backward - times four
           planes: 80 pixels wide, 0x2C = 44 rows
position   0x37CE is byte column 18 of row 174, so pixel (72, 174)
```

`[00019E64]` is the colour map, captured as `0x00209FC0` - the height map at
`[00019E6C]` plus exactly 1 MB, which is how that pair is laid out. The port
walks the 80 columns once instead of four planes, because a chunky surface has
no reason to; the samples and their order along each row are the original's.

Two notes worth keeping. The zoom `[00019C90]` was captured (`0x08000000`)
rather than assumed. And the row's backward half was invisible for a while
because the disassembler prints small displacements in decimal - `[edi + 9]`,
not `[edi + 0x9]` - so a regex looking for hex found ten writes where there
are twenty, and the panel looked half as wide as it is.

The right panel's equivalent is now `mfd_draw_target_view`, including its
secondary object pass. Still not ported and recorded: the overlay blit of
element 3 at `000075A1` that puts the waypoint marker and crosshair over the
map. It is not decoded.

## Terrain renderer: what is certified and what is not, 2026-08-27

Asked directly whether the terrain renderer is faithfully ported. The honest
breakdown, because the three levels are not the same claim:

**Its inputs are certified 1:1.** All five tables match the running original's
own memory byte for byte - `ring_a`, `ring_b`, `ring_z` and `ring_page_table`
at 180/180 each, and the backdrop horizon at 192/192 across three cameras.
That is a measurement, not a reading.

**Its structure is certified against the disassembly.** Measured, not assumed:
the 192 column-compare sites resolve to indices 95..0 then 96..191; the sample
and step instructions interleave as modelled and the turn's trailing `sub` is
discarded by the pops; the region is not self-modified (0 patched bytes in
`0000D950-0000F320` against 382 in the emitters); the selected renderer is
`0x0000D950` (`[00025DD9]` is `'}'`); and the emitter stores the new row
unconditionally without touching the walk's accumulators.

**Its output is NOT certified, and one caveat about the number matters.**
`tools/compare-marcher.py` scores 4.6-16.1% - but that figure compares *a
Python model of DOS's marcher* against *DOS's own silhouette*. It does not
involve the port at all. A failing score there says my reading of `0000D950`
is incomplete; it is not evidence about the 68030 code either way.

Ruled out as the cause, each by measurement: the reference window (the rear
view's 80-byte overwrite at `+0x58` is excluded), atomicity (QMP `stop`
freezes the machine for the whole capture), and the camera source (the frame
driver's latch at `0000D3CA` is used now instead of `[00019CD4]`, which its
own integration advances at `0000D413` before the sample). None closed it.

What remains is capture phase: freezing at an arbitrary instant can still pair
one frame's state with another frame's silhouettes, and the scores swing with
where the freeze lands. **A breakpoint at `0000F317` is the only thing that
settles it** - the marcher's own `ret`, after its last silhouette copy and
before `00007AA0` and the rear-view pass.

And a second step is needed after that, which is worth stating now: even a
perfect model only certifies the *reading*. Certifying the *port* means
rendering it at a captured DOS camera and diffing the surfaces. That needs a
diagnostic capture path in the port - the `PARITY_TILE` precedent, not a
behaviour flag.

## The marcher is certified, and the breakpoint is what did it (2026-08-27)

The section above ends by naming a breakpoint at `0000F317` as the only thing
that would settle the score. It was, and this records the outcome.

`tools/compare-marcher.py` now reproduces `0000D950` **exactly**: 17,248 of
17,248 columns over all 152 non-uniform rings of a captured frame, every ring
112/112 with a maximum error of 0, replicated on two independent captures at
different cameras. **The model did not change to get there.** The measurement
did - `--at-marcher` stops the guest at the marcher's own `ret` through QEMU's
gdbstub, and the same model went from 16.1% to 100.0%.

The eight structural hypotheses raised against the old scores were all wrong,
and each cost a round trip. The lesson is recorded in `AGENTS.md` as step 5 of
the porting procedure: when a model is right in shape and wrong in numbers,
suspect the measurement before the model.

**One real deviation fell out of the certified reference.** `0000D9B1`/`0000D9B7`
truncate first and subtract second - `imul` keeps `edx`, then `sub ebx, edx`.
The port negated the multiplicand and added, which is not the same rounding:
`high32(A*-C)` is `-high32(A*C)-1` whenever the low half is non-zero, and it
was non-zero for all 180 rings of the captured frame, so the error accumulated
once per ring. Now `sub.l d0,ring_cy`.

**The port's data is certified in use.** `tools/compare-port-tables.py` runs
the certified model on the port's generated tables instead of the original's
and scores 17,248/17,248. That is a stronger claim than the field-by-field
comparison it replaces: a table can be byte-correct and still be indexed
wrong, scaled wrong or paired with the wrong companion.

Two things fell out of building it. Comparing `D1.DTA` to the captured height
map reported that essentially every byte differed, which reads as a broken RLE
decoder - the decoder is exact and **the attract flies D4**. And the first
attract replay's resources, read out of the original at `0x2A320`, are
`Np44.dta d4.dta c4.dta sky4.rle`: the attract flies **mission 1**, which
`attract_next_pass`'s pre-increment is what produces.

Still not certified: the port's own rendered output. That needs a same-camera
surface diff through a diagnostic capture path.

## Function records added 2026-08-27 (second session)

| Port symbol | DOS | Kind | Status |
|---|---|---|---|
| `mfd_draw_labels` | `000072EB-000073C0` | translated | ported |
| `mfd_draw_target_view` | `00007860-00007942` | adapted - direct RGB565 target crop | ported; secondary object pass and RANGE verified |
| `console_start_state` | `000063BB-000063C9` | translated | ported, measured |
| `hud_draw_horizon_line` | `0000D49A-0000D4B2`, `sub_00025BB6` | adapted | ported |
| `menu_load_settings` | `00005665-0000567E` | translated | ported |
| `menu_apply_options` | `000268A5-000268BE` | translated | ported |
| `resource_match_colour` | `0002B820-0002B89C` | translated | ported, certified 5/5 |
| `resource_resolve_named_colours` | `0002AA85-0002AB3F` | translated | ported |
| `sprite_draw_page` / `_page_opaque` | `00025B27` / `00025880`, page coords | adapted | ported |
| `mfd_march_target_view` | `0001B26C-0001B34F` | translated | ported; called by target-view handler and archived silhouette consumed by object pass |
| `object_mark_targetable` | `00024DA4-00024DFC` | translated | ported, formula certified |
| `object_target_cycle` | `0001922C-000192A3` | translated | ported |
| `object_target_validate` | `0000D439-0000D45E` | translated | ported |

Each carries its full record at the definition. Three of them exist because a
capture contradicted a reading, and those are the ones worth naming here:

- **`resource_match_colour`** was certified against five captured slots before
  it was written. The port had a hard-coded `COL_MENU_GREEN` where the
  original resolves the nearest palette index; three of the five named colours
  are not exact in the attract's palette, so the constant was the right colour
  by accident and the wrong mechanism.
- **`object_mark_targetable`**'s projection had two wrong readings - the
  divisor is the ring's lateral increment and not the object's depth, and the
  search key is `depth << 3`. Both were caught by a capture with an
  **off-centre** target; the first capture had one dead centre, where every
  candidate formula agrees. Two more, closed 2026-08-31, were not in the
  formula at all but in the two lines that convert DOS numbers into this
  port's: the dividend took the search key's `shl edi,3` as well as the
  12.20-to-16.16 difference (eight times too large, so only a near-centred
  object could pass), and the clip ring's silhouette was indexed by `v`
  where the archive's 192 entries start `0x20` into their 256-byte record.
  Certified against the original's own frozen frame - the model reproduces
  its accept/reject on every live slot and its `[0x21BAB]` byte exactly, and
  the archive reads 192 non-zero bytes at offsets 32..223 and nothing
  outside. See `docs/X86-M68K-MAP.md`.
- **`object_draw_sprite`'s screen column was invented.** The original stores
  the same `v` in `[0x22365]` and the shared blit tail adds it to the
  destination column at `0002543A`, so `v` *is* the sprite's x; the port had
  a pinhole `160 + 160 * lateral / depth` reasoned out from the fan's shape.
  `B` is exactly `z/100` on every ring, so the original's half-fan is 200
  pixels of lateral per unit depth and objects were pulled a fifth toward the
  centre. Closed 2026-08-31, and checkable without DOS: the column `v` names
  and the column the port's own marcher steps to that lateral now agree to
  about one column, where the pinhole was out by up to fifty.
- **`object_draw_pass` carried two culls the original does not have**, and at
  bounds it does not use: a 992-unit range test and a `|lateral| > depth` fan
  test, both in the walk. `00024BCB` tests only the active byte and the depth
  sign. The original's range cull is `00024C45`'s `0x1FFFFFFF` - 512 units,
  and structural, because `depth << 3` wraps there - and its fan cull is the
  band on `v`. Closed 2026-08-31 along with the size band, which divided 1600
  by the object's own depth where `00024D21` divides `2^27` by the ring's
  lateral increment.
- **`object_target_validate` stopped one instruction short of the designator.**
  `0000D460-0000D478` stores `2 * [0x21BAB]` and `[0x21C2D]` into the
  `[0x19D1C]`/`[0x19D24]` pair and `0000D428` clears the entry each frame;
  without them the null gate at `0000D8C5` skipped the marker forever. This
  record used to call those tables event-populated and dormant. They are the
  target latch's own output.
- **`hud_draw_variant_tail` read the wrong bank, and a fabricated gate hid it.**
  Its two blits go through `0002599E`, which reads `[0x19E90]`; captured at a
  frame holding a lock that pointer's SG header declares 57 elements - CONS,
  not COMA. Drawing COMA put a helicopter across the frame, and the
  `phase == 5` test added to suppress it also suppressed the designator. With
  the right bank, `0000D88C`'s element is the sight's centre cross and its
  four arms land on the original's exact coordinates.
- **`hud_draw_horizon_line`** did not draw at first, because its gate byte
  `[0x267AC]` ships as `'{'` in the image and reads `'}'` at run time. Chasing
  that corrected this project's record of where the settings come from -
  `COMANCHE.MNU`, not `COMANCHE.CFG`.

**One live fault found while reading, not while testing.** Both copies of the
ring search published the *page* ring for the sprite's terrain clip, where
`00024D06` publishes the *clip* ring - the `0x1800000`-biased one. Models
beyond the bias were clipped against the wrong ring's silhouette. Fixed;
`object_project_ring` is the clip ring and `object_b_ring` the other.

## The replay flight is exact; the attract camera is not (2026-09-01)

Reported as "the flight path of the attract looks strange - we're flying into
the hills". The flight path is not strange and is not different. It is
byte-identical to the original's, and the thing that is wrong is where the
camera stands while that path is flown.

**Measured, not argued.** `work/trace_replay_flight.py` is new: it boots the
DOS oracle, stops at `00019555` - the instruction after the movement core at
`000194E0-0001954F` has written `[0x19CD4]`/`[0x19CD8]` - and reads the whole
flight state through the gdbstub's own `m` packet, once per integration tick.
Capturing at an instruction rather than an instant is the same METHOD rule
that took the marcher from 16.1% to 100.0%, and it matters more here: the
frame driver latches, renders and only then integrates.

Three results, all equalities:

| Comparison | Result |
|---|---|
| Port arithmetic vs original, DEMO1 over `d4.dta` | 777/777 ticks identical |
| Port arithmetic vs original, DEMO2 over `d3.dta` | 676/676 ticks identical |
| Running port under Hatari (VBL 3500) vs original at the same record | record 73: X, Y, angle, altitude all identical |

Identical means every field: `flt_x`, `flt_y`, `flt_angle`,
`player_altitude` and all five rates. `tools/certify-replay-flight.py` is the
third row - it dumps `flt_x`/`flt_y`/`flt_angle`/`player_altitude` and
`demo_cursor` out of Hatari and looks the cursor up in the DOS trace, so the
join is the record index both machines have consumed rather than a frame
number neither shares.

The pass-to-stream-to-terrain mapping is measured too, by stopping at
`00019A4E` as each replay arms (`--replays`):

| Attract pass | Stream | Mission resources |
|---:|---|---|
| 0 | `demo1.scr` | `Np44.dta d4.dta c4.dta sky4.rle` |
| 1 | `demo2.scr` | `p34.dta d3.dta c3.dta sky4.rle` |
| 2 | `demo3.scr` | `p23.dta d2.dta c2.dta sky3.rle` |
| 3 | `demo0.scr` | `p12.dta d1.dta c1.dta sky2.rle` |

`attract_next_pass`'s 1, 2, 3, 0 and `attract_start_demo`'s
`mission_select(pass)` reproduce that exactly; the running port reports
`pass=1 family=3 sky=4` at VBL 3500, which is `d4.dta`/`sky4.rle`.

**What is actually wrong.** The record's key byte selects the VIEW, and this
port drops it. `00007D25` builds the view basis as

```text
[0x19D00] = [0x19D04] + [ebx*4 + 0x19D94]      ; ebx = variant [0x19D86]
call [ebx*4 + 0x7BC9]  with eax = roll, ecx = pitch
```

Both tables read out of the *running* game at variants 1, 6 and 7, not off the
image: offsets `0, -90, +90, 180` degrees for variants 1..4 and zero for 5..7,
handlers `0x7BF0, 0x7C00, 0x7C10, 0x7C20, 0x7C25, 0x7C26, 0x7CC5, 0x7C25`.
Variants 6 and 7 are not roll/pitch transforms at all - they **move the
viewpoint**, which is why `0000D3DE`/`0000D3EA` push `[0x19CD4]`/`[0x19CD8]`/
`[0x19DFC]` around the render and pop them back:

- **`00007C26`, variant 6 - chase.** Subtracts `turn * 4` from `[0x19D00]`, so
  the camera trails the turn; then `[0x19CD8] += hi32(0x0F000000 * cos)` and
  `[0x19CD4] -= hi32(0x0F000000 * sin)`, fifteen map cells straight back along
  the view; then clamps the altitude up to `byte(2h + 12)` so the camera never
  sinks into the ground. Keeps roll, zeroes pitch.
- **`00007CC5`, variant 7 - fixed ground camera.** Replaces `[0x19CD4]`/
  `[0x19CD8]` with `[0x19CE4]`/`[0x19CE8]` and the altitude with `[0x19DF8]`
  (captured live: a real 10.22 map point at altitude 12), takes a bearing to
  slot `0x1F` through `000256C8`, adds 128 and shifts it into `[0x19D00]`.
  Zeroes both roll and pitch.

`0001959F`'s scancode cases `0x02`..`0x08` are the `'1'`..`'7'` keys that set
`[0x19D86]` to 1..7 (`00019696`, `00019769`, `00019799`, `000197C9`,
`000197F9`, `00019829`, `00019854`). The shipped streams use them:

| Stream | Camera keys |
|---|---|
| `DEMO1.SCR` | rec 30 `0x07` -> 6, rec 206 `0x08` -> 7, rec 357 `0x02` -> 1 |
| `DEMO2.SCR` | rec 221 `0x07` -> 6, rec 318 `0x02` -> 1 |
| `DEMO3.SCR` | rec 258 `0x08` -> 7, rec 367 `0x07` -> 6, rec 448 `0x02` -> 1 |

The trace confirms the effect end to end: over DEMO1 the original's variant
runs are 1 x 31, 6 x 176, 7 x 151, 1 x 419, and `[0x19D00]` differs from
`[0x19D04]` by up to 54/256 of a turn - about 76 degrees - through the two
external stretches. **327 of DEMO1's 777 records, 42% of the first attract
pass, are not flown from the cockpit at all.** This port renders every one of
them from the cockpit at the helicopter's own position, pointing the view
straight down a flight vector that was authored to be watched from behind and
from the ground. That is the whole of the reported symptom.

In variant 1 the two angles still differ by 0..4 units. That is not a second
camera: `[0x19D00]` is written during the render and this trace samples after
the integration, so the difference is one tick of turn - the same one-frame
skew `frame_driver` already preserves. The port reads `flt_angle` at render
time and is correct there.

## The terrain owns 168 rows, not the screen (2026-09-01)

Reported from the running port: "the outside-view of the comanche shows an
area at the bottom which is not being painted as terrain." It was, and the
first thing to rule out was the camera - `--at-render` was added to
`tools/certify-replay-flight.py` for exactly that, stopping at `render_clear`
so `flt_x`/`flt_y`/`player_altitude` are the CAMERA the frame marches from
rather than the helicopter `frame_driver` pops back. Both external views match
the original on all seven fields there, camera position and clamped altitude
included. Not the camera.

**`00007AA0` does not blit a rectangle.** It walks a run list - lengths and
flags at `0x38B20`, sources at `0x32B20`, destinations at `0x34B20`, count at
`[0x19E4C]` - and the list is built from the loaded console image's
transparency. Dumped out of the running original at two variants:

| Variant | Console | Runs | Shape |
|---|---|---:|---|
| 6 | `consol5s` | 168 | every run `len 82` - a full-width rectangle |
| 1 | `consol1s` | 261 | runs of 1..60 bytes - the canopy's own outline |

Different shapes, **identical row extent**: both start at source `0x042E11`
and end at `0x04D5xx` on the surface's 256-byte row stride - surface rows
46..213, which through `screen row = 213 - surface row` is screen rows
**0..167**. The terrain owns 168 rows and nothing below them.

Measured on the pictures, last terrain row per column:

```text
original, chase camera   168 in every column - flat
this port, chase camera  171 at column 0 ... past 240 by column 240 - sheared
```

Two faults, and the second only exists because of the first:

1. `draw_span` clipped at `SCREEN_HEIGHT-1`, and `render_clear`'s ground base
   ran the full column. Both now stop at `TERRAIN_VIEW_ROWS-1`.
2. Below the viewport the original leaves its single visible page alone, and
   during the attract that page is the title art - a screendump of the
   original at variant 6 shows COMANCHE MAXIMUM OVERKILL under the terrain.
   `render_reset_surface` seeded the WHOLE surface with the ground entry, and
   its own status note called that "removes attract-title residue at replay
   entry". The residue is the picture. It now seeds the viewport only.

The port's sheared bottom edge was the roll shear reaching rows the original
never blits: `backdrop_dy` is subtracted from both ends of the span, which is
right - `00007DC3` patches it into the emitter's `add ch` and it moves the
whole span - but with no viewport bound the bottom end ran off the screen.

**This is only ever visible where the console is not drawn.** `0000D4C4`
skips the cockpit for every variant except 1, so 72 rows that the console
covers in the cockpit are bare in the chase and fixed cameras. Every earlier
capture in this project was a cockpit frame, which is why a wrong bound
survived to here.

The marcher is unaffected and re-certified at **15120/15120 columns (100.0%)**:
the clip is on the span write, not on the occlusion array the silhouettes come
from.

**Still different.** The port now leaves the region standing, but what is
standing there is not the original's title art - a capture shows the port's
own attract page content instead. Which screen the compositor leaves in those
72 rows before `demo_start`, and where it places it, is the next thing to
settle; the bound itself is now the original's.

## The attract camera, ported (2026-09-01)

All of the above is now implemented, in `src/view.s` plus the wiring named
below. `view_basis_build` is `00007D25`: the view angle from
`view_angle_offsets` (generated verbatim from the image at `00019D94`), its
Q31 pair, and a nine-entry jump table that is `[00007BC9]`. The seven handlers
are `00007BF0`, `00007C00`, `00007C10`, `00007C20`, `00007C25`, `00007C26` and
`00007CC5`; `view_select` is `0001959F`'s `0x02`-`0x09` cases and their shared
tail at `000196B4`.

What had to move with it, each because the original does it and the port did
not:

- `src/render.s` takes `[00019CB0]`/`[00019CB4]` and `[00019D00]` instead of
  re-deriving a basis from `flt_angle`, and `backdrop_build` takes
  `[00019CF8]`/`[00019CFC]` instead of the roll and pitch accumulators.
- `src/flight.s` publishes `0001950F`/`0001951B`'s sin/cos pair. It was
  recorded as having no observer; `000198A5`/`000198B6` place variant 7's
  camera ten map cells back along it.
- `src/object.s`'s draw stage reads the LIVE `[00019CD4]`/`[00019CD8]` and the
  view pair, as `00024B2E`/`00024B45` do, not the frame snapshot. Its update
  stage keeps `0002381F`'s LATCHED altitude, which now matters: with an
  external view selected the live byte is the camera's.
- `src/frame.s` saves and restores the port's 16.16 copy of the viewpoint with
  the 10.22 pair, gates the target latch on `[00019D86] > 5` (`00019255`,
  `0000D418`) and the cockpit on `[00019D86] == 1` (`0000D4C4`, whose other
  branch reaches `0000D8AE`'s immediate return). `src/hud.s` carries
  `000073D0`'s own copy of that gate.
- `src/main.s` dispatches the replay key where `00006AF4` does - after the
  frame driver returns - because the view cases call the frame driver twice
  themselves.

**One fault in the mission parser fell out of this, and it was silently
costing an object.** `00029213`'s eight-value block and the number after it
were being crossed with three `mission_skip_line` calls rather than read.
They are nine numbers, not two lines, and the third skip was eating the first
placement record. Measured against the original: it parses **nine** records
for the attract's first mission, `[0x19D64] = 9`, types `0,2,2,2,2,2,2,2,2`;
this port saw eight, all type 2. The missing type-0 record is dispatch entry
0 of the table at `0002231C`, `00023462`, which installs the fixed slot-31
object - and slot 31 is exactly what `00007CC5` aims the fixed camera at
through `000256C8`, and what `00024C0A` draws in the external views. The port
had no slot 31 at all: its variant-7 camera pointed at an object that did not
exist. Nine records and nine active slots now, against the original's nine.

**Certified against the original**, `tools/certify-replay-flight.py` with
`--view`, comparing the running Falcon build at the same replay record:

| Sample | Flight state | View basis |
|---|---|---|
| variant 1 | x, y, angle, altitude match | all six fields match |
| variant 6 | x, y, angle, altitude match | all six fields match |
| variant 7 | x, y, angle, altitude match | all six fields match |

"All six" is the variant byte, the view angle, its sin and cos, and the
backdrop slope and offset. Two phase traps had to be closed to get a reading
at all, and both are the "capture at an instruction" rule again: the Falcon
sample is taken at `flight_publish`, the port's own `00019555`, because a VBL
sample can land inside the render where the camera has moved `flt_x`; and the
view basis is looked up one record BEHIND the flight state, because both
machines build the basis at the top of the frame and consume the record at
the bottom.

**What is still not carried**, each named at the instruction it drops:

- `00007C35`-`00007C46`, the further `0xA0000000` swing the chase camera takes
  while the player-destroyed byte `[00019E49]` is set. Its writers are all in
  the damage handlers this milestone does not carry, and `src/flight.s`
  already treats the same flag as zero at `00019442`.
- `000196CF`/`0001971A`/`00019715` call `0001687D`, `00016B50` and `00015B78` -
  VGA page publication and plane selects, with no Falcon counterpart.
- `0001970B`/`00019756` call `000072C4`, which is not decoded.
- Variant 5's `0000D703` branch and variants 2-4's `0000D8B7` marker restore.
  Neither is reachable from the shipped demo streams, which use only 1, 6
  and 7.
- The extra frames the tail renders are composed into the Falcon back buffer
  and only the last is published; DOS is single-buffered and shows each.

## MFD bodies

Ported 2026-09-28. Before this the port hard-wired the map on the left and the
target view on the right, so a function key moved the highlight and left the
body as the console art had it. `0000D64B-0000D6FC` is now `mfd_draw_panel`.

**Dispatch.** `0000D693` reads the left page `[0x72E6]`, indexes the six-entry
table at `0x19E10` - read out of the hashed image as `075B0 07710 07860 076B0
07530 07690`, matching the running capture - and calls it; `0000D6BF` adds
`0x1A` to `[0x19CA8]`, the right body is drawn from `[0x72E7]`, and
`0000D6FC` takes it back off. Every writer a body reaches adds `[0x19CA8]`
(`00015855`, `000079F0`, `00025880`, `0002599E`, `00025B27`), so a handler
draws the same picture on either side; the port's `mfd_body_offset` is that
dword in pixels, and the map, its markers, the target view's span writer and
its RANGE readout now read it instead of a fixed right-panel constant. Two
overrides replace the table's choice, in this order:

- `[0x1AA5]` non-negative forces `00007690`. `0x1A70` is the key-state array
  `00001B96` fills by scancode (`src/input.s` `key_state`), so this is
  scancode `0x35`, '/', held.
- `[0x19E3E]` (left) / `[0x19E3F]` (right) negative forces `00007670`. These
  are entries 6 and 7 of the eight-byte damage array `0002921A` parses and
  decrements, so an authored 0 disables that MFD from mission start.

`[0x19C8C]` is written 0 then 1 around the two calls and read nowhere in the
image; it is not carried.

**Zoom.** `0000D64B-0000D689` steps `[0x19C90]` by `0x800000` once per frame
while ',' (`[0x1AA3]`) is held, up to `0x10000000`, and down while '.'
(`[0x1AA4]`) is held, to `0x2000000`. The dword ships as `0x08000000` in the
image (static content, below `0x32B20`). The port's `mfd_zoom` is that dword;
the map and its markers read it. The three preset keys at `00019C5E-00019C7A`
belong to the unported console-key dispatcher and are not here.

**Handlers.** All draw their panel element opaque through `00025880` at
`(0x48, 0xAE)`, the left panel's bottom-left, from the bank at `[0x19E90]`
(`CONS.RLE`, 57 elements).

| Page | Entry | Element | Then |
|---|---|---|---|
| 0 | `000075B0` | map | `00007580` map view and own-ship cross, then slots 30..1 as markers (already ported) |
| 1 | `00007710` | `0x31` | slots `0x82` down to `0x1F` with a marker byte, `sar 0x17` on lateral/depth, windows `-0x28<x<0x28`, `-0x16<y<0x16` around `(0x6F, 0xC4)`, through `00025B27` |
| 2 | `00007860` | - | the target view (already ported) |
| 3 | `000076B0` | `0x38` | `[0x2824D]` at `(0x8E, 0xC6)` and `[0x2824B]` at `(0x8E, 0xD0)`, two digits each through `00007504` |
| 4 | `00007530` | `0x2A` | when `[0x19DE8] & 3` is non-zero, element `0x2B + i` through `0002599E` for each negative entry `i` of `[0x19E38..0x19E3D]` |
| 5 | `00007690` | `0x33` | nothing |
| override | `00007670` | `0x32` | nothing |

`[0x2824D]` and `[0x2824B]` are both counted up from the '*' placement records
at `00029266`/`0002926C`; only `[0x2824B]` is counted down, at `000237DE`, as
starred objects are retired. They are `mission_star_count` and
`object_endcue_hold` here. Page 4's frame gate has the opposite sense from
the map's target blink at `0000763A`: the overlays are skipped when the low
two bits are zero. The port reads `[0x19DE8]` as `frame_count`, as the map's
blink already does.

**Verified** in Hatari at VBL 4000 of the attract. The attract itself only
reaches pages 0 and 2, and its frame is byte-identical before and after the
change. Every other page was forced with a temporary, uncommitted poke at the
dispatcher: pages 4/3 (with damage entries 0 and 2 forced negative), 1/5,
both overrides (entries 6 and 7 negative), and 2/0 (the map drawn on the
right). All render inside their bezels, with the function-key highlight
matching the forced page. There is no DOS capture of pages 1, 3, 4 or 5 yet.
The next check is a keyed QEMU trace pressing F2/F10/F5/F12.

**Owed:** the browser reference has no counterpart for any MFD body - these
four handlers, the dispatcher, or the older map (`000075B0`) and target view
(`00007860`). It also lacks the damage array, the star counters and the key
array they read. Until those land, these rows are Falcon-ported but not
browser-validated, which the method requires before they count as supported.
The browser also still draws the whole cockpit layer at page x without the
4-pixel `PAGE_VIEW_X` margin the Falcon now applies everywhere, sight line
included.

**Test-harness trap found on the way:** a stale `release/AUTO/GAME.PRG`, dated
2026-09-01 and unknown to every tool, was being booted by TOS before
`comanche.tos`. It never returns, so every capture from `release/` since then
showed that old build, whatever had just been built. It is moved aside as
`release/AUTO.stale-20260901`. `tools/grab-frame.sh`, `tools/grab-frames.sh`
and `tools/run.sh` now refuse to run with a non-empty `AUTO` folder. Captures
recorded between 2026-09-01 and this fix should be re-taken before they are
relied on.

**Sight line, fixed alongside.** `hud_plot_sight_pixel` (`00025D2D`) wrote the
page x of `00025CA2`'s walk straight to the surface. It was the one page-x
writer still missing the `PAGE_VIEW_X` margin, so the line left the fixed
cross 4 pixels right of centre; the DOS captures show it leaving the centre
gap. It also wrote a fixed RGB565 green where DOS writes the palette index
`[0x2A37A]`; it now reads that index, as `hud_draw_solid_column` does.

## The marcher, made fast (2026-09-28)

`render_terrain_ring` was the frame's largest cost by a wide margin. A Hatari
CPU profile of VBL 3000-4500 (cycle-exact 68030, `profile on` / `profile
save`, cycles folded onto `comanche.map`) measured about **10.3 million
cycles per rendered frame** in the marcher and its span writer. HIGH detail
walks 250 rings × 192 columns, about 48,000 samples, so that is about 215
cycles a sample. The attract rendered 24 frames in those 1,500 VBLs.

Where the cycles went, read off the per-instruction profile:

- **Instruction-cache thrash.** The 68030's instruction cache is 256 bytes,
  direct-mapped by address bits 4-7. The column loop (164 bytes) called
  `draw_span` 900 bytes away, on the same cache lines. Every painted sample,
  23% of them, evicted the loop, and the loop's instructions missed about
  once per four passes.
- **Loop state in memory.** The page pointer, the column step and the
  column count were read, and the count written, on every sample.
- **Per-span overhead.** A span averages 2.2 rows. `draw_span` spent more on
  `movem`, clipping and addressing than on those stores, and the call site
  re-read `backdrop_dy` twice around it.

The rewrite changes none of the arithmetic. It changes where each value
lives:

- The horizon is **one byte of page row per column**, as DOS keeps it in its
  0xC0-byte stack array. The test is 0000D9FB's `cmp ah,[esp+n] / ja` as one
  `cmp.b / bhi`, and the column is a walking pointer: `-(a3)` for the falling
  half, `(a3)+` for the rising one. This replaces DOS's unrolled samples, with
  their falling `[esp+0x77]`, `[esp+0x76]` … displacements.
- `ring_silhouette` is now **DOS's own bytes of page rows** too, 192 per ring.
  The object pass's targetability test (00024DEA) reads it without the
  conversion it needed before. The sprite clip (000254CF) converts to a screen
  row, since it compares screen rows. `tools/certify-marcher.py` reads bytes.
- The span writer is the `TERRAIN_PAINT` macro, inline in each loop. It
  replaces 0000AF50's per-column emitter blocks and 00006BF0's Duff's device.
  Its clip and address come from `ring_cols`, which is rebuilt once per frame
  from `backdrop_dy` and `render_target`. Colours come from `ring_pal32`, a
  per-frame table holding each flight-palette entry as an RGB565 pair.
- The map index is `(Y >> 12) & ~0x3FF | X.hi >> 6`. That is the same 20
  bits 0000D9EE/0000D9F2's `shld` pair extracts, in 7 register instructions.
- The measured audit build used `ring_mul_q31_raw` and `mul_s32_64`, selected
  through the `_CPU` cookie. After mainline integration, `ring_mul_q31_raw`
  uses the shared `inc/cpu.s` macros: native `MULS.L Dh:Dl` for 68030 and the
  four-partial-product path for the 68060 build. Both give the exact 64-bit
  product; the duplicate runtime helpers are removed.

**Measured:** about **3.4 million cycles per frame**, 3.1× faster. The hidden
sample costs about 41 cycles and a painting one about 90 plus its stores.
The same 1,500 VBLs now render 62 frames instead of 24.

**Verified identical to the previous build:**

- `tools/certify-marcher.py work/qemu_out/marcher-11.json` still scores
  20608/20608 columns exact against the original's own archive at `[0x19E60]`.
- `tools/probe-record.sh`, new, compares the two builds at the same replay
  record, since a faster build shows a different game frame at any given
  VBL. It breaks at `object_draw_pass` or `demo_tick` when
  `demo_cursor = 13 + 8K`, then dumps `render_target` and `ring_silhouette`. It covered records 30-240, in steps
  of 30:
  - the terrain buffer and the silhouette, at HIGH detail and at low detail
    (`[0x25DD9]` staged as `'{'`);
  - the composed frame (objects, sprite clip, HUD) at both details, and again
    after the multiply change.

  Every pixel and every silhouette byte was identical.

**What the frame spends now.** Per flight frame the marcher is about 58% of
the cycles. Next come `render_copy_surface` (two full-screen copies, 1.2M
cycles) and `render_clear` (0.8M), then `object_depth_sort` (0.2M). The
attract runs at about 2.5 frames per second on the cycle-exact 68030, up
from 1.

## Difference ledger

### 2026-09-30 map-index mechanism optimization

The `TERRAIN_SAMPLE` helper retains parent DOS ID `sub_0000D950`, specifically
0000D9EE/0000D9F2's two SHLD operations. Five 68030 instructions now extract
the unsigned top ten bits of X and Y with register BFEXTU, position Y in
bits 10..19 and combine X in 0..9. Byte-wrapped bias, map bytes, projection,
strict unsigned horizon comparison and accumulated coordinates are unchanged.
There is no JavaScript contract change; this is an equivalent native mechanism.

HIGH records 60..80 measure 3,394,678.7 marcher cycles/frame against
3,521,767.6 baseline, 3.61% less; cockpit records 10..20 improve 3.22%.
Both intervals preserve all history pixels and silhouette bytes at their
endpoints. Retained DOS fixtures score 15120/15120 (192-column cockpit) and
17472/17472 (96-column); the runtime MEDIUM increments and projection pages
also match captured DOS data. This does not promote complete-frame or hardware
acceptance. Cache alignment was tested and rejected as slightly slower.
See `docs/PERFORMANCE-2026-09-30.md` for the hotspot split, failed experiments,
phase/settings corrections, evidence paths and limitations.

- The attract's view selectors and both external cameras are ported and
  certified, 2026-09-01; what remains of them is the short list at the end of
  "The attract camera, ported".
- DOS VGA/Mode X memory, CRTC start-address panning, and palette ports are
  replaced by Falcon VIDEL setup, double buffering, and RGB565 words.
- DOS little-endian resource fields are decoded byte-by-byte before native
  Falcon use; authored file bytes are not rewritten into guessed structures.
- The replay and object state arithmetic, source resource selection, 192-column
  terrain walk, strict occlusion, callback selection, object ordering, and
  draw-before-tick sequencing remain DOS contracts.
- Falcon VBL cadence, GEMDOS scheduling, sound, keyboard/joystick input, menu
  handoff, mission completion, and DSP timing are outside this route and remain
  Unproven.

No source in this milestone is justified by the browser alone. The browser
record `analysis/functions/browser-attract.md` is a validation counterpart;
the route reports and the DOS function rows above are the source boundary.

## Proof gate

The source-level checks are:

```text
PYTHON=<Windows Python> tools/build-run.sh
tools/run.sh
node tools/prove-browser-attract.js
python tools/substitutions.py --check
```

The build must produce `release/comanche.tos` with no DSP object or DSP host
symbol. A Falcon capture is the next validation step; until that capture is
recorded, this document proves source selection and build coverage, not
pixel-for-pixel Falcon/DOS equality.

## Audit branch integration (2026-09-30)

`dos-fidelity-audit` is merged with the existing mainline target-view object
pass, weapon launchers, and displayed source window 16..175. The optimized
marcher's archive remains one byte of DOS page row per column. Main-view
sprite clipping converts that byte through `render_page_anchor`; target-view
sprite clipping retains its separate word-sized screen-row archive.

The shared `inc/cpu.s` macros remain the single wide-product mechanism and
VIDEL publication cache boundary for the 68030/68060 builds. The audit's
parallel runtime CPU detector/product helpers are superseded by those macros.
All six MFD pages and live zoom are retained. Browser camera state stays in
raw DOS coordinates; the audit's selector timeline, bearing corrections,
168-row terrain transfer bound, and fixture-clock remainder fix are retained.
The browser composes the selected console in external views as well as the
cockpit. The function records describe these consolidated symbols; historical
capture counts elsewhere continue to refer to their named pre-merge builds.

Merge validation: `node tools/prove-browser-attract.js --dos-marcher
work/qemu_out/marcher-11.json` passes, including 20608/20608 retained DOS
terrain-horizon comparisons. Both 68030 and 68060 builds succeed, and
`tools/check-attract-timing.py` on each CPU verifies 480 fanfare ticks, 600
title ticks, replay byte order, and the first completed flight publication.
These checks retain their existing timing/presentation scope.

The 68030 diagnostic marcher also matches 20608/20608 scored columns over
184 non-uniform rings, 192/192 backdrop entries, 64000/64000 projection-page
bytes, and both 250-entry increment tables against `marcher-11.json`.
`tools/certify-marcher.py` now stops at the first main `object_draw_pass`
after terrain completion; the merge run reached it at VBL 5722. Stopping at
VBL 3200 captured the wrong terrain family, and VBL 5200 found the map loaded
before a completed march. Neither failed VBL capture is renderer evidence.
Retained captures without a `pages_file` use their captured DTL slope/bias
arrays in the browser gate's independent projection oracle.
