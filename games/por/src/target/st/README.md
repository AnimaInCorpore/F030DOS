# Atari ST back end — not implemented

This directory is deliberately empty of code. It exists so the **contract** is
visible and so nothing in `src/common/` may quietly assume a Falcon.

Per `PORTING.md` §Nothing without a source, no ST code is written until someone
actually targets an ST; a speculative back end would be invented work with
nothing to verify it against.

## What an ST back end must provide

`src/common/` references these symbols and nothing else that touches hardware.
Providing them is the whole job.

| symbol | kind | contract |
|---|---|---|
| `_main` | entry | **must be linked first** — a TOS executable begins at the first byte of TEXT |
| `target_init` / `target_deinit` | routine | take and release the machine; restore every touched register on exit |
| `render_surface` | `ds.l 1` | pointer to the 320×200 **8-bit indexed** surface that common code draws into |
| `target_hidden_page` | `ds.l 1` | the page `target_present` writes into |
| `target_present` | routine | `a0` = indexed surface, `a1` = hidden page. Turn indices into hardware pixels |
| `target_build_lut` | routine | `a0` = `PORI` bank base; prepare whatever `target_present` needs from its palette |
| `target_flip` | routine | publish the drawn page |
| `target_frame_count` | `ds.l 1` | incremented once per vertical blank |

## What is different from the Falcon back end

- **Bitplanes.** The ST has no chunky or true-colour mode. `target_present`
  becomes a chunky-to-planar conversion into 4 bitplanes, not a palette
  expansion — the single largest piece of work here.
- **Palette registers are real.** The Falcon back end never programs a palette
  because it presents in RGB565. An ST back end must load `$FF8240..$FF825E`
  from the bank's palette table, which `tools/convert_data.py --target st`
  already emits as `$0RGB` words (`PORI_PAL_ST`).
- **68000, not 68030.** `src/common/` is assembled `-m68000` for exactly this
  reason. Misaligned word access is an address error on a 68000, not merely
  slow, so the alignment rule in `PORTING.md` §Data representation policy is
  mandatory here rather than advisory.
- **Colour depth.** The DOS art is 16-colour EGA and the ST shows 16 colours at
  320×200, so no colour reduction is needed — a plain ST has 3 bits per gun
  against the STE's 4, which is the only fidelity question.

## Building it, once it exists

    make TARGET=st

`TARGET` selects `src/target/<name>/`; `src/common/` is shared unchanged.
