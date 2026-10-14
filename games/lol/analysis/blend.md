# BLEND palette tables

Status: **RESOLVED**

`BLEND.TAB` and `BLEND2.TAB` are 65,536-byte direct lookup tables. The linear
index is `(source_pixel << 8) | destination_pixel`, and the byte at that
index is the palette index to write after blending the two pixels.

## Exact reconstruction

The table is made from one 256-entry VGA palette `P`, whose components are
the original 6-bit values (`0..63`). For every source index `s`, destination
index `d`, and channel `c`:

```text
mixed[c] = min(63, ((P[s][c] * 22) >> 6) + ((P[d][c] * 42) >> 6))
```

The output is the palette index whose RGB triplet has the least squared
Euclidean distance to `mixed`. Equal distances select the highest index,
because the original scan updates the winner on `<=`.

The first `0xFFFC` bytes are exact under this reconstruction. The final four
bytes in every language copy of both files are the common residue
`E4 D5 02 00`; they are retained as shipped rather than treated as lookup
cells.

## Palette witnesses

| table | palette witness | cross-check |
|---|---|---|
| `BLEND.TAB` | `FINALE1.PAK:RETURN.CPS` | exact through byte `0xFFFB` |
| `BLEND2.TAB` | `FINALE1.PAK:EYE2.CPS` | exact through byte `0xFFFB` |

`EYE2.CPS`, `FACE.CPS` and `TAPPING.CPS` carry the same palette in all three
language packages. The files are language-identical as well:

- `BLEND.TAB` SHA-256: `f709c1f4f765bd123cf4e0311b4b3f9e013c349e02e48a3602e00e87cb0bcc07`
- `BLEND2.TAB` SHA-256: `ff3043ebbc274a5ae80aaeafb3a15a8a4aa1155aa0ed248ad3e914e8b7749e85`

The corpus witness is implemented by
[`tools/re/blendinfo.py`](../tools/re/blendinfo.py), using
`--check-finale FINALE1.PAK`. The runtime operation is therefore a palette
lookup, not an opaque effect-specific compression format: Falcon code can
recreate the tables at load time or ship the validated tables directly.
