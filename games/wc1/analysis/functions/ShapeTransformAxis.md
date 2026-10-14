# raster_zero_angle_fastpath — axis-aligned transformed sprite kernel

Status: **Target artefact**. This is a Falcon performance seam inside the
existing transformed sparse-shape renderer, not a new DOS function. No DOS
symbol or address is claimed for the helper.

## DOS identity and evidence

- DOS identity: **N/A - platform replacement** for the Falcon renderer's
  axis-aligned hot path. The DOS-derived raster rule it preserves is the
  existing `rle_round_ratio()` nearest-sample contract in `src/resources.c`.
- Supporting evidence: the source shape-frame and inverse-sampling rules are
  documented from `wc1-re/src/killbrd.c` and the existing WC1 target fixture;
  `../F030Arcade/PORTING.md` supplies only the 68030 cache-layout technique.

## Recovered/implemented contract

For `angle == 0`, the transformed sampler's two source coordinates are
separable. The helper builds one exact integer X sample for each destination
column and one exact integer Y sample for each destination row, using the same
signed `rle_round_ratio()` operation and the same `scale_x`/`scale_y` values as
the general path. It then samples the decoded transparent scratch frame and
writes only non-`0xff` pixels into the already-clipped destination rectangle.

Negative scale components (the existing horizontal/vertical flip encoding),
solid recolouring, transparent gaps, source bounds, destination bounds, and
the 320-byte row stride are retained. Rotated calls use the general path.

The setup/map builder and pixel loop are separate functions so the repeated
flight loop remains small in the 68030's direct-mapped 256-byte instruction
cache. The title callback fences this target path out to keep its accepted
VBL-coupled attract cadence unchanged.

## Implementations and fixtures

- Target helpers: `src/resources.c:build_transform_axis_maps()`,
  `src/resources.c:draw_transform_axis_pixels()`, and
  `src/resources.c:draw_shape_frame_axis_aligned()`.
- Existing caller: `src/resources.c:draw_shape_frame_transformed()`.
- Target path: `resource_intro_rendering == 0` (flight/scaled effects only).
- Existing resource fixture: `make resource-smoke` validates the decoded
  indexed shape/cockpit path; `make test truecolor-smoke build` validates the
  target integration and presentation seam.
- Visual fixture: Hatari capture at the established title checkpoint must
  remain unchanged; the title fence was added after an unfenced capture
  demonstrated phase drift.

## Difference ledger against DOS

| Area | Target behaviour | Evidence/status |
| --- | --- | --- |
| Source sample rounding | Reuses `rle_round_ratio()` exactly | Source-level equivalence; target artefact. |
| Flip handling | Preserves signed scale denominators | Same denominator passed from the existing transform setup; target artefact. |
| Transparency | Preserves `0xff` scratch holes | Existing sparse-frame contract and resource fixture. |
| Rotated path | Unchanged general sampler | Explicit branch; target disassembly retains the existing `divsll` loop. |
| Title timing | Fast path disabled during intro callback | Hatari capture/timing guard; avoids renderer-speed phase drift. |
| DOS function identity | No direct DOS replacement claimed | **N/A - platform replacement**. |

## Open proof

An isolated byte-for-byte target-vs-general transformed-frame fixture covering
all four flip modes and scale boundaries remains future work before applying
the map kernel to additional room or campaign paths.
