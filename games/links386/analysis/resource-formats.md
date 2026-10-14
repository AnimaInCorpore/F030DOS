# Links 386 resource and course records

Status: **PARTIALLY RESOLVED**.

The CD includes two related binary families. `*.REC` files are course-associated
records with a small readable header followed by binary state. `*.TIL`, `*.SPL`,
`*.WVL` and several `*.LZ` files use an `MDmd` resource container.

## Course record header

`BANFF1.REC` is 3,025 bytes. Its first fields are stable and directly readable:

| offset | measured value | observation |
|---:|---|---|
| `0x00` | little-endian `0x0100` | record/version word |
| `0x02..0x31` | `BANFF SPRINGS` padded with spaces | 48-byte course-title field |
| `0x32` onward | `MARK CARVER`, then NUL-separated short fields | player/record metadata area; subfield meanings are not assigned |
| `0x42` | `0x07C9` | binary metadata word |
| `0x44` | `0x0310` | binary metadata word |
| `0x46` | `0x003E` | binary metadata word |
| `0x4A` | `1` | binary metadata word |
| `0x4E` | `MALE.MGA` | referenced golfer asset name |

The same layout appears in the other records: `BANFF2.REC` and `BANFF3.REC`
retain the `BANFF SPRINGS` title while changing the player/metadata fields;
`BRUCE.REC` and `CHRIS.REC` use `HARBOUR TOWN`. The body after the header is
binary and contains repeated structured blocks, but their field widths and
units need runtime or cross-record correlation before naming.

## `MDmd` resource container

The resource files begin with the four-byte signature `MDmd`, followed by the
same `0x010A` marker and `0x007A` header value. The little-endian dword at
offset `0x0A` behaves as an entry count in the sampled files: `CDBLANK.TIL`
has `1`, `BANFF1.SPL` has `2`, and `BOBCAT1.WVL` has `0x5F` (95). The header
contains an ASCII `INDEX~` marker at `0x2C`.

The container is recursive. `CDBLANK.TIL` contains a nested `MDmd` record at
file offset `0x8B` naming `TILE.BLK`. `BANFF1.SPL` contains nested records at
`0x9C` and `0x415`, naming `SPLASH.COL` and `SPLASH.BLK`. This establishes the
archive/index boundary without assuming that the following compressed bytes
are directly drawable pixels.

No protected-mode seeds were added from these observations.

## Next measurement

Correlate one `*.REC` body with a runtime-loaded course or scorecard, then
decode the child `MDmd` payload lengths and compression flags. The DOS oracle
is the required way to validate those interpretations after the segment-override
defect described in [executable.md](executable.md) is fixed or a correct emulator
passes `work/segtest/`. Correction reviewed 2026-10-10: the current blocker is
trustworthy original execution, not merely acquiring DOS installation media.
