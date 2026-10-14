# GAME001 scenario fields and state closure

Status: PARTIALLY RESOLVED. Original unpatched PANZER.EXE is the authority;
SHA-256 `115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86`.
`sub_00037216`, vaddr 0x37216..0x37E75, consumes GAME001.SCN through
`sub_00066170`. `poland-fields-4/route.json` retains 223 paired consumer reads,
exactly covering all 447 pristine bytes. Positions below are file offsets;
destinations are object-2 offsets unless explicitly local to the loader frame.
These are observed fields, not a substitute loader or guessed game model.

| File bytes | Size | Destination / meaning established by consumer |
|---|---:|---|
| 0..10 | 10 | 1DD68, five interleaved country slots for two sides |
| 10..14 | 4 | 179A8, signed value controls three setup words |
| 14..16 | 2 | 1DDC2 |
| 16 | 1 | 2AD9 |
| 17..21 | 4 | 2ADF, 2AE0, 2AE1, 2AE2 individually |
| 21..25 | 4 | 2B81, 2B82, 2B83, 2B84 individually; last three feed date normalization |
| 25..27 | 2 | 28EF3, 28EF6; intervening 28EF5 is cleared by code |
| 27..31 | 4 | 1D29C |
| 31..33 | 2 | 1DDCA |
| 33..35 | 2 | frame local -14, side unit counts 11/11 |
| 35..37 | 2 | frame local -10, side reserve counts 0/0 |
| 37..117 | 80 | 11B3C, coordinate-word pairs terminated by FFFF |
| 117..119 | 2 | frame local -18, count 1 |
| 119..123 | 4 | 108BC, counted dword list; Poland FFFFFFFF |
| 123..127 | 4 | frame local -24; split words copied/added to 178CC/178CE |
| 127..131 | 4 | 2B2D, 2B2F two words |
| 131..139 | 8 | F15C |
| 139..447 | 308 | 22 unit rows of 14 input bytes |

Units are stored at `11C54 + slot*98 + side*49`. Each 14-byte input row
writes record offsets 15 (word), 17 (word), 14 (byte), 19 (word), 1B (word),
1D (word), 1F (byte), 25 (byte), 28 (byte), in that order. The first two
words select 50-byte equipment records at 179B0. Other field meanings remain
explicitly unnamed until their downstream contracts establish them. Two sides
each load slots 0..10; the reserve loop beginning at slot 80 is not executed
by Poland but remains in the inventory/scope investigation.

The raw writes do not settle final unit state. Subsequent code builds names
through sub_0002A980, copies equipment bytes 25/26, clears derived record
fields, updates side counters, and optionally calls sub_0003AF00. After the
SET/STM loader, sub_00039244 builds map-dependent lists; sub_0003AFF3 visits
200 slots per side and assigns class bytes at 10694, consuming sub_0006337B.
It also computes side averages at 1DD92/1DD94. Difficulty dispatch changes
178CC/178CE through integer arithmetic. Every producer/branch must be closed
before the complete scenario loader can enter supported connected flow.

Next contract: sub_00063375 seed pointer, sub_0006337B random transition,
sub_0006339F seed store. An unchanged DOS capture plus boundary seeds and a
chained sequence will distinguish full 32-bit state from narrowed outputs.
Never substitute JavaScript Math.random or emulator wall time for these calls.
