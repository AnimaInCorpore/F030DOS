# FlightSceneDepthMerge — bounded 3Space world-object depth queue

Status: **Unproven diagnostic slice.** It improves the current Falcon flight
view but is not a supported port path: the 1990 DOS `WC.EXE` overlay entry and
an execution capture for this renderer sequence have not yet been recovered.

## DOS identity and evidence

- Authority image: `release/WC1DATA/WC.EXE`, SHA-256
  `576359ede27e6ff3d973d5f6b9db2e79f640fd2a883386268952ccf3c2445f78`.
- Canonical 1990 DOS function symbol and range: **TBD**. `WC.EXE` uses VROOM
  overlays; treating the 170,160-byte file tail as a flat image is known to be
  invalid, so no inferred tail address is recorded as a DOS function.
- Supporting evidence only: the 1996 Kilrathi Saga reconstruction labels
  `Draw_3Space_Frame()` at `0x00429DD0`; its order is
  `transform_objects_to_your_view()`, `update_star_field()`, fixed-child
  placement, `sort_object_depth()`, then
  `draw_sorted_objects_to_buffer()`. The supporting source gives the latter
  two at `0x00436460` and `0x00436520`; the transform function is
  `0x0041A1D0`.
- That reconstruction is not authority for the 1990 build, its similarity
  grade for these functions is **unavailable** in this workspace: on
  2026-09-10 `make -C ../wc1-re -n report FILTER=Draw_3Space_Frame` required
  absent `code-full/`, a rebuilt Win32 executable, and an original 1996
  executable. The 1990/1996 behavioural delta is unmeasured. All claims below
  remain **Unproven** until checked against DOS.

## Recovered/implemented contract

`resource_draw_flight_scene()` owns one Falcon-only bounded queue for the
world objects currently represented by the diagnostic flight slice:

- eight dust and seven star records from `PLANETS.VGA`;
- up to eight non-eye mission ships from the compact roster;
- the 40-slot cannon projectile/LASER_SPARK pool; and
- the eight-slot `EXPLOSION1` pool.

It derives each queue key as an unsigned 16-bit `distance >> 8`, sorts those
keys far-to-near, and draws the resulting item list. Equal keys preserve the
target collection order (background, ships, projectiles, explosions). The
cockpit, target-lock shape, and HUD are screen overlays, not members of the
world-object queue.

The maximum is `(9 - 1) + 40 + 15 + 8 = 71` entries. The storage is static
and bounded; no Falcon heap allocation, packet I/O, or VBL-disabled resource
load happens during scene drawing.

## Implementations and fixtures

- Browser/JavaScript: **none**. A deterministic browser reference has not
  yet been started, so this record cannot enter a supported browser/target
  path.
- Falcon target: `src/resources.c:resource_draw_flight_scene()` and the
  adjacent `flight_scene_*` projection/draw helpers.
- Falcon wrapper: `src/render.s:render_scene` invokes the merged queue before
  the target-lock overlay.
- Host fixture: `tools/resource_loader_smoke.c` constructs a retained star
  field, Dralthi, laser pair, and `EXPLOSION1`; it requires all four scene
  kinds in the queue and non-increasing recorded DOS-sized depths. Run
  `make resource-smoke`.
- Static fixture: `make test` requires the merger symbol, its record, and the
  host seam. `make build` verifies m68k link integration.

The exported `resource_flight_scene_order[]` and
`resource_flight_scene_depth[]` arrays are target-fixture telemetry, not game
state or a new source-data format. An order word is `(kind << 8) | index`,
where kinds 1–4 are background, ship, projectile, and explosion.

## Difference ledger against DOS

| Area | Falcon behaviour | Evidence/status |
| --- | --- | --- |
| Sort key | Unsigned 16-bit `distance >> 8`, far-to-near | Matches 1996 supporting source; **Unproven** for DOS 1990. |
| Object capacity | Separate bounded 15 + 8 + 40 + 8 collections, merged as 71 potential entries | Falcon storage seam; differs structurally from DOS's shared object arena; visual equivalence **Unproven**. |
| Equal depths | Stable target collection order: background, ships, projectiles, explosions | Explicit target policy; source slot identity for every retained class is not yet recovered; **Unproven**. |
| Visibility bookkeeping | Each class retains its existing projection/draw validity checks; queue candidates may be rejected by that draw helper | Target implementation detail; source screen-sentinel timing is **Unproven**. |
| Star-field update timing | `game_tick` advances the retained star field before the scene merger | The 1996 supporting sequence calls `update_star_field()` after transform and before sort; equivalence for the 1990 frame boundary is **Unproven**. |
| Overlay order | Cockpit/target lock/HUD remain outside the world queue | Existing Falcon architecture; DOS correspondence **Unproven**. |
| Browser reference | No implementation or shared fixture | **Unproven**. |

## Open proof

1. Recover the 1990 DOS overlay table and the canonical ranges for the frame,
   transform, depth-sort, and sorted-draw functions.
2. Capture a controlled DOS frame containing overlapping star/dust, ship,
   projectile, and explosion art; compare its order, tie rule, and clipping
   against a browser fixture and the Falcon indexed buffer.
3. Replace the target collection-order tie policy with verified original
   object-slot order, including the source allocator's simultaneous-object
   limits, before promoting this slice beyond diagnostic status.
