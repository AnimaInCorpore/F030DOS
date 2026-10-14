# Publication status

Prepared 2026-10-14 from the committed HEADs of the thirteen F030 DOS port
repositories and F030Method; `sources` in
[publication-inventory.json](publication-inventory.json) names the imported
commit of each. F030WC1 was added the same day at the owner's request, after
its working tree got a first commit (disks and build trees ignored); this
reverses the earlier "publication skipped" decision recorded in F030Method.

Status: **private review candidate; not approved for public distribution.**
License: undecided.

## Preparation

- Fresh history. The development repositories are unchanged and remain the
  homes of the ports; this copy is refreshed from their commits with
  `tools/publication.py sync`, never from a working tree. Uncommitted work in
  them (on 2026-10-14: a regenerated `cross-project.md` in every port and
  pending edits in F030PanzerGeneral) is not part of the copy.
- The first import screened 3,105 committed paths: 842 candidates, 1,793
  local-only and 470 excluded, recorded per path with the reason. The
  decisions are screening results, not legal findings. WC1 added 52
  candidates; none of its committed files failed the screen.
  - Local-only by location: `game/`, `assets/`, `img/`, captures and recorded
    fixtures, Ghidra projects and exports, reassembly output, extracted or
    unpacked data, listings, vendor toolchains (DOSBox, Hatari and vasm
    binaries, TOS ROMs), build output, and every binary or non-text format
    (MS-DOS 6.22 floppies, manuals as PDF, LFD/ARC/LZH game files).
  - Excluded by content: text with more than 400 lines of x86 code, decompiler
    output, more than 64 lines of literal data, a 512-element numeric array, a
    long hexadecimal payload, oversized generated text, string dumps of the
    game program; vendored DOS/32A and ZRDX extender sources (own licenses).
  - Comanche's `reference/` (a copy of F29's documents) and PanzerGeneral's
    DOS-recorded `tests/fixtures/` and register trace are local-only.
- One content screen was overridden after review: `games/f29/src/sincos.s`, a
  computed table (all 4,500 longs equal `round(sin(2*pi*i/3600)*2^31)` within
  257, float32 rounding; F29's own table is 1,024 words).
- Comanche, F29, POR and WC1 build from this copy. Comanche's, F29's and
  WC1's programs built here are byte-identical to the ones built in their
  development repositories (2026-10-14).

## Remaining blockers

1. **Provenance and rights review.** Analysis documents, function records and
   the ports' sources quote addresses, constants and short code fragments of
   the originals by design (every routine cites the DOS routine it came
   from). Whether that is acceptable, and where the limit lies, is an owner
   decision; the mechanical screen only removes the bulk forms.
2. **Embedded game content in Comanche.** `comanche.tos` carries about 3.5 KB
   of `COMANCHE.EXE`'s data tables, generated into `build/original_test.s` by
   `tools/prepare-original-test.py` from the player's copy at build time
   (`tools/release.py` finds them; 32 more bytes match `COMANCHE.NAM`). A
   public binary needs those tables loaded from the player's `COMANCHE.EXE` at
   run time, a change in F030Comanche. F29 and POR carry none that the check
   can see (POR checked against its expanded DOS data; F29's data is not on
   the preparing machine, so F29 is unchecked).
3. **WC1: resolved for the release check.** Since F030WC1 98493d2
   (2026-10-14) the title text, `get_right_shape()`'s frame/flip rows and the
   explosion debris sets are read from the player's `WC.EXE`; `wc1.tos`
   contains no 32-byte block of it. Smaller transcribed DGROUP tables remain
   in `src/resources.c` (cockpit lights, canned title sequences, the
   EXPLOSION1 animation, Hornet hardpoints; listed in
   `games/wc1/analysis/wcexe.md`) and are part of the rights review.
4. **Regeneration gaps.** Comanche's JS reference uses two tables extracted
   from the DOS image (`jsComanche/object-bearing.js`, `sine-q31.js`), which
   are excluded; the reference needs a generator that reads the player's copy.
   PanzerGeneral's contract tests need their DOS-recorded fixtures.
5. **Dependencies.** Builds need F030Arcade's `third_party/` (vasm, vlink,
   ASM56000, TOS images, patched Hatari); F030Arcade's own publication is in
   review. Comanche's build needs Python `capstone`.
6. **Documentation links** still use the development layout (`../F030Method`,
   `../F030Arcade`, sibling ports).

## Checks

```sh
python3 tools/publication.py check            # the index
python3 tools/publication.py check --history  # every commit
python3 tools/publication.py check --ready    # also fails until status is approved-for-publication
```
