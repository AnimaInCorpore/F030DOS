# Falcon RGB565 presentation function record

Updated 2026-08-25. This is the first assembled and Hatari-executed Falcon
target seam for the UW2 port. The DOS executable and captured DOS execution
remain authoritative; this record describes a target artefact required by the
selected Falcon Videl output mode, not a claim that DOS itself used RGB565.
This is one of the method's explicit graphics exceptions: it may replace the
VGA/Videl mechanism after the logical framebuffer contract is recovered, but
it may not replace DOS game functions, input-driver behavior or game flow.

## `uw2_indexed_to_rgb565`

| Field | Record |
|---|---|
| DOS identity | **N/A — platform replacement.** DOS produces a 320×200 indexed framebuffer and source-form `PALS.DAT` 6-bit DAC bytes; VGA register timing is not translated into a Videl instruction sequence. |
| Purpose | Build a 256-entry RGB565 lookup from one PALS.DAT palette, then expand the complete indexed surface into a chunky Falcon page. |
| Inputs | `uw2_falcon_build_rgb565_lut`: `a0` = 768-byte RGB triples, `a1` = 512-byte LUT. `uw2_falcon_present_rgb565`: `a0` = 64,000-byte index8 surface, `a1` = 128,000-byte destination page, `a2` = LUT. |
| Outputs | One big-endian RGB565 word per source pixel; channel quantisation is `round(component6 × 31/63)`, `round(component6 × 63/63)`, and `round(component6 × 31/63)`. |
| Side effects | Writes only the caller-provided LUT/page; preserves the documented data/address registers and uses no Videl register. |
| Browser counterpart | `browser/uw2-cutscene.js`: `paletteToRgb565`, `frameToRgb565`, and `drawFrame`; the indexed LPF surface remains the canonical DOS-derived equality surface. |
| Falcon implementation | `src/target/falcon/present.s`: `uw2_falcon_build_rgb565_lut`, `uw2_falcon_present_rgb565`; exact build is recorded by `Makefile`, with MC68030 restriction and Motorola syntax. |
| Difference ledger | **Target artefact:** indexed/DAC bytes become a chunky RGB565 page; browser bytes are explicitly big-endian to match the target word order. **Hatari evidence:** the MC68030 smoke page is byte-identical to the host contract. **Unproven:** Videl timing/register values, physical scanout, palette-update timing, and full DOS-to-Falcon framebuffer equality. |
| Status | **Ported/Verified for the deterministic MC68030 function under Hatari.** Physical Falcon scanout and integration with the recovered game frame remain **Unproven**. |

## Evidence and smoke fixture

`work/check_falcon_present.py` computes the deterministic host expectation for
the varied palette and 320×200 index pattern in `src/target/falcon/smoke.s`.
`make check` assembles the source with `-m68030`, retains the vasm listing and
vlink map, and checks the host contract. `make hatari-smoke` runs the same
artifact under Hatari's Falcon030 machine, derives the TOS load base from the
debugger register dump, checks `falcon_smoke_status`, and compares the complete
128,000-byte page. The current captured page hash is
`76ab89e0c75830569a872be6400c636fe90509d3915e0cfdde7424ddc1b40f06`.
