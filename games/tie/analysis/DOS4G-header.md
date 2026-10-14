# `Z_TIE__.EXE` / `DETVESA.EXE` — standard Watcom **LE** modules (DOS/4G)

✗ **Withdrawn (2026-08-21): the "DOS4G OLX hybrid with a private header"
model.** This document previously described both files as monolithic dual-half
hybrids — a 16-bit flat half at linear 0, a private header at `0x2A50`, a
selector table, 9/11-byte thunk records, and a 32-bit image at file `0x3F000`
hard-fixed to linear `0x7E000`. **Every field of that model is a standard LE
structure read at the wrong offset, with the wrong stride, or with the wrong
base.** Re-measured with an assumption-free parser
(`python work/audit_headers.py <exe>` — struct.unpack only, reads nothing from
the docs). Two arithmetic identities close the question, on both samples:

- `data_pages_off + (pages−1)·page_size + bytes_on_last_page`
  = `0x3D800 + 190·0x1000 + 0x547` = **`0xFBD47` = the file size, exactly**
  (DETVESA: `0xBA00 … 0x3E8D9` = its file size, exactly);
- `fixup_record_table + fixup_page_table[last]` = `0x314C + 0x3A690`
  = **`0x3D7DC` = the import-module-table offset, exactly.**

The old readings are quoted below, each mapped to what the bytes actually are,
because several of them are cited from other docs and each looked *right* for
a reason.

## What each withdrawn reading actually is

| Withdrawn reading | LE reality (audited) |
|---|---|
| MZ is a "pure container": entry "`e_ip=e_cs=0:00`" (read at 0x20/0x22), "`e_rels=0`", "never executed by DOS" | a real Watcom 16-bit stub program. `e_ip`@0x14 = `0x030E`, `e_cs`@0x16 = 0 → entry at file **`0x36E`**: `E9 CB 00` + `WATCOM C Run-Time system code`. `e_crlc`@0x06 = **6**, table at `e_lfarlc` = 0x40 |
| "6-entry vector table of 24-bit offsets `0x3DE, 0x46A, 0x4E0, 0x52D, 0x551, 0x57E` at 0x40 = 16-bit-half entry points" | the six **MZ relocation entries** (`offset u16, segment u16` each, segment 0). All six targets land inside the stub image `[0x60, 0x2A4E)` |
| "`dwEntry = 0x00010002` → 32-bit entry at image base + 2" | two u16 fields at LE+0x08: `cpu_type` = 2 (386) and `os_type` = 1 |
| "selector-table size 0xBF" | `module_num_pages` = 191 (0xBF) |
| "`dwDataSize` = 0x7B4E4, semantics TBD" | `eip` = 0x7B4E4 — the entry offset within object 1 |
| "16-bit half extent 0x46470" | `esp` = 0x46470 (initial ESP; equals object 2's virtual size, i.e. the stack starts at the top of DGROUP) |
| "shared loader constants 0xC4 / 0xF4 / 2 / 2" | `object_table_off` / `object_page_map_off` (both **LE-relative**) / `num_objects` / `auto_ds_object` |
| "selector table @ 0x2B44: dword N = N·0x10000, selector N → linear N·64K" | the **object page map** (4 B/entry: page number as **u24 big-endian** + flags u8). An identity map's entry *i* is bytes `00 00 (i+1) 00`, which reads as the little-endian dword `(i+1)·0x10000` — this is why the selector story looked perfect |
| "name tags `\x07t_z\x07ie__` @ 0x2E40" | the **resident name table** (LE+0x58 = 0x3F0): length-prefixed module name records |
| "24-bit offset table @ 0x2E50 (0x06A6, 0x0D5C, 0x15FF …)" | the **fixup page table** (LE+0x68 → file 0x2E4C): 192 ascending u32 offsets into the fixup record table |
| "9-byte / 11-byte thunk records @ 0xAD8C and 0x26C00+" | both offsets lie inside the single **fixup record table** (`0x314C..0x3D7DC`). `07 10` is a record *start* — source type 7 (32-bit offset), flags 0x10 (32-bit internal target) — and the "u16 type" in front of it was the tail of the *previous* record's target dword. See `work/audit_fixups.py` |
| "'thunk table start' 0xAD8C (+0x70)" | `import_module_table_off` = 0x3AD8C (LE-relative, → file 0x3D7DC). File 0xAD8C is just a point inside the fixup record table |
| "32-bit image starts at file 0x3F000 (+0x50 = image start ≫8)" | `resource_table_off` = 0x3F0 (LE-relative). The data pages actually start at `data_pages_off` = **0x3D800** — the old `z_tie_32.raw` extract begins 0x1800 bytes into page 2 |
| "16-bit entry stubs at file 0x2045 / 0x2043 (two calling-convention variants of one function)" | the two **object flag words**: obj1 `0x2045` = READABLE\|EXECUTABLE\|PRELOAD\|BIG_32BIT, obj2 `0x2043` = READABLE\|WRITABLE\|PRELOAD\|BIG_32BIT. (File 0x2045/0x2043 land inside the MZ stub's code, which is why "verifying" them found real-looking instructions — a name that resolves is not evidence) |
| "32-bit real entry at file 0xAAE83" | object 1's **virtual size** (0xAAE83, first dword of the object table @ 0x2B14) |
| "count 0xAB / 0xAC" | obj1 `page_map_entries` = 171 (0xAB) / obj2 `page_map_index` = 172 (0xAC) |
| "file offsets 0x3A991 / 0x3ACC9 into the thunk cluster" | `fixup_sect_size` = 0x3A991 / `loader_sect_size` = 0x3ACC9 |
| remaining rows of the old field table | land on other standard LE header / object-table fields; re-derive from `audit_headers.py`'s printed map, not from this table's history |

**Why the wrong model held.** It was *cross-verified* — against `DETVESA.EXE`,
which is the same standard format, so every "shared constant" matched by
construction. Every misread produced well-formed structure (big-endian page
numbers as `N·0x10000` dwords; flag words as file offsets that disassemble; a
records table that parses on the wrong stride). And the founding excuse — "the
MZ entry points at the header, so DOS never executes it" — came from reading
`e_ip`/`e_cs` at 0x20/0x22 instead of 0x14/0x16. The family rule that catches
all of it (`cross-project.md` §1): decode the container with an
assumption-free parser and disassemble twenty instructions at the computed
entry — **if what you find needs an excuse, the field is wrong.**

---

## The MZ stub (file `0x00..0x2A4E`)

| quantity | value |
|---|---|
| header | `e_cparhdr` = 6 → 0x60 |
| DOS image | `(e_cp−1)·512 + e_cblp` = `(22−1)·512 + 78` = **0x2A4E** (10,830 B) |
| entry | `0000:030E` → file **0x36E** = `E9 CB 00` + `WATCOM C Run-Time system code` |
| stack | `SS:SP = 02A5:0800` |
| relocations | 6 × (offset u16, segment u16) @ 0x40..0x58; all targets in-image |
| `e_lfanew` | `e_lfarlc` = 0x40 ≥ 0x40, so the dword @0x3C is real: **0x2A50** → `LE` |

The stub is a genuine 10.7 KB Watcom 16-bit program (it is what runs if the
file is executed *without* the extender; `DOS4GPATH`/`PATH` strings live in
it). What exactly it does — print an error, or locate and exec `DOS4GW.EXE`
itself — is **TBD** (small and eminently readable; 16-bit sweep it).

## The LE module (header @ `0x2A50`)

Key fields (full map: `python work/audit_headers.py game/SWTieCD/TIECD/Z_TIE__.EXE`):

| field | value |
|---|---|
| signature / cpu / os | `LE`, 386, os_type 1 |
| pages | 191 × 0x1000, last page 0x547 B |
| entry | object 1 + `eip` 0x7B4E4 → linear **0x8B4E4**, file **0xB8CE4** |
| stack | object 2 + `esp` 0x46470 |
| object table | file 0x2B14, 2 objects |
| object page map | file 0x2B44, identity (u24-BE page + flags) |
| fixup page table / records | file 0x2E4C / 0x314C..0x3D7DC |
| data pages | file **0x3D800** (absolute), span ends exactly at EOF |
| auto DS object | 2 |

| object | base | vsize | flags | pages | file |
|---|---|---|---|---|---|
| 1 (code) | `0x00010000` | 0xAAE83 | R·X·PRELOAD·BIG32 | 1..171 | `0x3D800..0xE8800` |
| 2 (data/DGROUP) | `0x000C0000` | 0x46470 | R·W·PRELOAD·BIG32 | 172..191 | `0xE8800..0xFBD47` |

Object 2 maps 20 pages (0x14000 B) of a 0x46470 B object — the remaining
**0x32470 B are BSS** (zero-filled by the loader). `audit_headers.py` flags
this as `*** MISMATCH ***` on the ceil(vsize/page) check; for a data object
with BSS that is the expected reading, not an error.

**The entry point is the "CRT tag" the old doc recorded.** File 0xB8CE4 is
`EB 76` (`jmp short`) followed immediately by
`WATCOM C/C++32 Run-Time system (c) Copyright by WATCOM …` — the Watcom CRT
enters on a short jump over its embedded banner (all three 16-bit Watcom
programs in the chain do the same: `TIE.EXE` @ 0x110C, `Z_TIE2__.EXE` @ 0x192,
the stub here @ 0x36E). The old doc's "CRT tag @ img+0x79CE5" (= file
~0xB8CE5) was the real entry point, unrecognised.

## Address model (one place, use everywhere)

```
object 1:  linear = 0x10000 + (file − 0x3D800)      file ∈ [0x3D800, 0xE8800)
object 2:  linear = 0xC0000 + (file − 0xE8800)      file ∈ [0xE8800, 0xFBD47)
                                                    + BSS to linear 0x106470
```

The legacy `img+X` notation (= file `0x3F000 + X`) remains a valid pure
**file-offset alias** — every string-pool citation in the docs still lands —
but its old runtime column (`0x7E000 + X`) is withdrawn, and `z_tie_32.raw`
misses the true image start by 0x1800 bytes (file `0x3D800..0x3F000`).

Worked check (fixups as the reverse-xref index): the CD-check string
`You must insert TIE-Fighter CD…` is obj2+0xBF (file 0xE88BF, = img+0xA98BF).
`python work/audit_fixups.py --target=2:0xBF` → exactly **one source site**:
file `0x3DAC3`, linear `0x102C3`, raw dword in file `BF 00 00 00`. The raw
operand is the unrelocated object-relative offset — which is why no immediate
scan under any base could ever find it (`ztie.md` §7 item 9, resolved).

## Fixups

`work/audit_fixups.py` decodes the whole table: **27,438 records, 100 %
source type 7 (32-bit offset), 100 % internal targets** (`--stats`), record
walk landing exactly on every page boundary and the table ending exactly at
the import module table. `--target=OBJ:OFF` lists every source site for a
target — the only xref mechanism that works on an LE image, since raw
operands are stored object-relative and patched at load time.

## Withdrawn: the `0x7E000` runtime geometry

> *"file offset 0x3F000 is file-space only. The CRT entry function stores
> selector-base words 0x7E00/0x7E10 as immediates into 16-half data slots
> `[0xD15A]`/`[0xD160]` … the image's linear base is hard-fixed at 0x7E000."*

Withdrawn 2026-08-21. That deduction treated file `0x3F002` as the module
entry ("dwEntry = base+2"); the real entry is file 0xB8CE4 / linear 0x8B4E4,
and the object bases are 0x10000/0xC0000 from the object table, applied by
the loader through ordinary fixups. File 0x3F002 is mid-page code at linear
~0x11802; what the routines at file `0x3F0BA`/`0x3F116` actually do with the
`0x7E00`/`0x7E10` immediates is unread under the correct map — **TBD**, and
no longer load-bearing for anything.

## DETVESA.EXE — the second sample

Identical structure, smaller: same stub shape (image 0x2A4E, entry 0x36E,
`e_lfanew` 0x2A50), LE with 2 objects — obj1 base 0x10000 vsize 0x314EE
(R·X·BIG32), obj2 base 0x50000 vsize 0x3200 (R·W·BIG32) — 51 pages, identity
page map, entry linear 0x10254 (file 0xBC54), data pages `0xBA00..0x3E8D9`
= file size exactly.

`TIE.EXE` is **not** a third sample: it is a plain, self-contained 16-bit
Watcom MZ program (no LE anywhere in it) — see the 2026-08-21 correction in
`analysis/32bit/P1.5-launchers.md`.

## What survives from the withdrawn model

- The **string pools and their offsets** (img+`0x0A9800..0x0AB600` startup/CD/
  IMUSE, img+`0x0B9000..0x0BE000` scene `.WRK`, CRT banner, `RATIONAL DOS/4G`
  @ img+0xAAC3D) — all file-offset facts, unaffected.
- The **boot chain** and `/trebla`/`/320` semantics (string-verified).
- The **function sweep** `functable_v2.txt` *as file offsets* (its runtime
  column and the 0x3F000 base convention are superseded; the file misses
  `0x3D800..0x3F000`).
- The `DOS4GW.EXE` analysis (`DOS4GW-loader.md`) — a different binary; only
  its "Answers" about this file are withdrawn there.

## Open

1. What the MZ stub does when run directly (10.7 KB, 16-bit sweep it).
2. The `0x7E00`/`0x7E10` immediates at file 0x3F0BA/0x3F116 — real code,
   unknown purpose, no longer assumed to be a base.
3. `entry_table_off` = 0x3FB — decode the (tiny) LE entry table.
4. `module_flags` = 0x200 meaning for this loader; `os_type` = 1 under DOS/4G.
5. Demand-load vs full copy of the 191 pages — unchanged, dynamic
   (`ztie.md` §7).
