# c2p_present_rgb565 — Falcon presentation seam

Status: **Target artefact**. This function has no DOS counterpart: DOS
presents indexed VGA memory, while the Falcon Videl page is a native RGB565
surface. It is nevertheless recorded because it is a target function in the
supported title and flight paths.

## DOS identity and evidence

- DOS identity: **N/A - platform replacement**. No DOS function is claimed.
- The DOS-side rendering contract remains an indexed 320x200 buffer and the
  loaded `GAME.PAL` palette. The Falcon-specific conversion is not evidence of
  DOS semantics.
- Supporting technique: `../F030Arcade/PORTING.md` documents direct native
  word stores and unrolled 68030 hot loops; its renderer is supporting
  implementation evidence only.

## Recovered/implemented contract

`wc1_indexed_to_rgb565(indexed, rgb565, palette)` converts exactly
`320 * 200 = 64000` source bytes. For each source index `i`, it writes the
  16-bit word `palette[i]` to the destination in native big-endian memory
  order. Null pointers are a no-op, matching the host/reference fixture.

The target implementation expands eight pixels per loop and uses direct
`move.w` stores. The host `src/c2p.c` implementation remains the
architecture-neutral golden-pixel reference used by `make truecolor-smoke`.

## Implementations and fixtures

- Falcon target: `src/c2p_fast.s:wc1_indexed_to_rgb565`.
- Host/reference: `src/c2p.c:wc1_indexed_to_rgb565`.
- Callers: `src/main.s:present_flight_frame` and
  `src/front.s:front_present_frame`.
- Fixture: `tools/c2p_smoke.c`, run by `make truecolor-smoke`; it compares the
  host converter against explicit big-endian expected bytes.
- Static seam coverage: `tools/check_contracts.py` requires the target source,
  Makefile ownership split, and this record identifier.

## Difference ledger against DOS

| Area | Falcon target behaviour | Evidence/status |
| --- | --- | --- |
| Source pixels | Reads the completed indexed 320x200 surface | Existing Falcon rendering contract; target artefact. |
| Palette lookup | Uses the 256-entry RGB565 palette already expanded from `GAME.PAL` | Verified palette/resource fixtures; target artefact. |
| Destination format | Writes native big-endian RGB565 words to Videl memory | Verified by `make truecolor-smoke` and Hatari frame capture; platform replacement. |
| Timing | Eight-pixel unrolled 68030 loop with direct word stores | Target performance implementation; no DOS equivalent is claimed. |
| DOS semantics | No function-level semantic replacement claimed | **N/A - platform replacement**. |

## Validation

The accepted evidence is:

1. `make test truecolor-smoke build` passes;
2. Hatari title capture remains pixel-identical to the pre-optimization
   capture at the established VBL checkpoint; and
3. the target object disassembly contains the eight-pixel direct-word loop,
   while the host reference continues to pass the byte-order fixture.

This optimization changes only the Falcon presentation seam. It does not
change indexed pixels, palette values, title timing, input, or DOS-derived
game state.
