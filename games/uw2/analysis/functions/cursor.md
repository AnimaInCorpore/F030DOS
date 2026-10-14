# DOS cursor function records

Updated 2026-08-25. The hashed DOS executable and captured DOS execution are
authoritative. This record separates the recovered cursor state functions from
the canvas-only browser slice. Cursor data is retained here as DOS evidence;
the current browser runtime does not load cursor assets or pointer state.

## Recovered DOS functions

| Stable record | DOS entry/range | Recovered contract | Status |
|---|---|---|---|
| `uw2_cursor_redraw` | `fn_1e76b`, `0x01E76B–0x01E7B6` | If `[0x26E]` is nonzero, repairs the covered rectangle through the DOS blitter, using cursor position `[0x268]/[0x26A]`, stored width/height `[0x238E]/[0x2384]`, and extents `[0x2300]/[0x2302]`; returns the visibility byte. | Code-backed; exact underlying blitter/clip timing remains open. |
| `uw2_cursor_hide` | `fn_1e7b7`, `0x01E7B7–0x01E7CC` | Increments the nested hide word `[0x26C]`; the first hide invokes the recovered covered-region operation. | Code-backed. |
| `uw2_cursor_show` | `fn_1e7cd`, `0x01E7CD–0x01E7ED` | Decrements `[0x26C]`; when the count reaches zero, calls `cursor_redraw`, clears `[0x26E]`, and invokes the DOS cursor drawing primitive. | Code-backed. |
| `uw2_cursor_set_bitmap` | `fn_1ee3c`, `0x01EE3C–0x01EEA1` | Loads the cursor record through the DOS resource functions, reads width/height from record bytes `+1/+2`, stores `width/2-1`, `height/2`, and the cursor identifier in the cursor globals. | Code-backed for state; resource-loader and blitter side effects remain open. |
| `uw2_cursor_for_region` | `fn_1eea2`, `0x01EEA2–0x01EF75` | Scans the registered cursor regions and selects a bitmap when the cursor position lies inside a region. | Identified; complete region table and call path remain `Unproven`. |

The exact DOS bodies are retained in
[`work/reasm/out/uw.asm`](../../work/reasm/out/uw.asm). The stable symbols are
also emitted by `work/symbols.py` and `work/ghidra_export/symbols.txt`.

## Cursor asset evidence

`D4\DATA\CURSORS.GR` record 0 is a type-`0x0A` 13×13 flat high-nibble-first
bitmap with one trailing byte. Its header byte `+3` selects auxiliary palette
The captured record, palette mapping, and RGB565 quantisation described
below remain analysis evidence. The current browser runtime does not read
`CURSORS.GR`, `ALLPALS.DAT`, or `PALS.DAT`.

For this record, nibble 0 is treated as transparent because the two captured
DOS frames differ only in the recorded cursor boxes and the zero-nibble cells
preserve the underlying capture. This was runtime-backed by the removed cursor
viewer for record 0; it is not promoted to a generic type-`0x0A` rule. The meaning of header byte
`+4`, the trailing byte and the general type-`0x0A` transparency contract stay
`Unproven`.

The primary/alternate capture pairs are recorded in
[`analysis/character-fixtures.json`](../character-fixtures.json). Outside the
recorded 52×52 cursor boxes the pairs are byte-identical. The removed cursor
viewer built a clean backing image by copying the alternate image's clean area
over the primary cursor box and then documented the behavior-level redraw. None
of that capture or cursor drawing path is loaded by the current canvas runtime.

## Browser counterpart and difference ledger

| DOS record | JavaScript counterpart | Difference/status |
|---|---|---|
| `uw2_cursor_set_bitmap` | None in the current browser runtime | Cursor assets and extents remain DOS evidence; the canvas slice does not load cursor resources. |
| `uw2_cursor_hide` / `uw2_cursor_show` | None in the current browser runtime | No cursor state or browser pointer path is retained. |
| `uw2_cursor_redraw` | None in the current browser runtime | The current canvas presents only the connected cutscene framebuffer. |
| DOS screen/cursor presentation | None in the current browser runtime | The deleted character/cursor viewers were outside the supported canvas display slice. |

No browser input event calls a cursor or character-selection helper. Mouse and
cursor behavior remain documented DOS evidence for a future game-flow slice.
