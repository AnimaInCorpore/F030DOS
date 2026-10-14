# `FALCON3.EXE` container audit

Status: `PARTIALLY RESOLVED`: the DOS MZ image, the RTLink v1 appended-tail
directory and the loader's seek/read/zero-fill contract are resolved,
including the nine bytes the final record declares past end of file
(2026-09-13, [Overlay loader contract](#overlay-loader-contract)), and so are
thunk dispatch, caller reload, parent chaining and overlap eviction
([Overlay selection and eviction](#overlay-selection-and-eviction)). Compiler
and runtime identification remain open, as do the save/restore and flag
`0x20` callback entries, which the traced route never reaches.

The measurements below come from the `FALCON3.EXE` member extracted from
`FALCON3.RES`. Re-run them with:

```text
python tools/re/mzinfo.py game/FALCON3/FALCON3.EXE
```

## MZ header

The first 32 bytes are:

```text
4d 5a 51 01 fe 00 9d 0a c0 02 d7 58 ff ff 2c 75
00 08 00 00 6c 07 a3 1a 1e 00 00 00 00 00 4f 00
```

| Offset | Field | Value |
|---:|---|---:|
| `0x00` | signature | `MZ` |
| `0x02` | bytes on last page | `0x0151` (337) |
| `0x04` | pages | `0x00FE` (254) |
| `0x06` | relocations | `0x0A9D` (2,717) |
| `0x08` | header paragraphs | `0x02C0` → `0x2C00` bytes |
| `0x0E` | SS | `0x752C` |
| `0x10` | SP | `0x0800` |
| `0x14` | IP | `0x076C` |
| `0x16` | CS | `0x1AA3` |
| `0x18` | relocation table | `0x001E` |
| `0x1C` | overlay number | `0` |

The DOS image boundary is `0x1FB51`:

```text
image size       0x1FB51 (129,873) bytes
load module      0x1CF51 (118,609) bytes after the 0x2C00 header
entry            1AA3:076C = file 0x1DD9C
stack top        752C:0800 = relative linear 0x75AC0
appended bytes   0x12FA96 (1,243,798) bytes after the MZ image
file SHA-256     01c190669084a3047c01688303baf39329e7c68ffb576aa3a9e272da4ea428d8
```

The MZ header does not describe the appended bytes as a DOS load module. The
resident image contains RTLink overlay-manager strings such as `Cannot find
overlay file`, `Open error on overlay file`, and `Read error on overlay file`.
The appended region is therefore kept separate from the resident load image.
The RTLink directory audit below resolves its on-disk record boundaries and
load-slot metadata, but does not assign the segments one fixed runtime address.

## Entry stub

The entry bytes at file `0x1DD9C` begin:

```text
01DD9C  2e 8c 06 86 0a       mov  word ptr cs:[0x0A86],es
01DDA1  2e 8c 1e 88 0a       mov  word ptr cs:[0x0A88],ds
01DDA6  bb a3 1a             mov  bx,0x1AA3
01DDA9  8e db                mov  ds,bx
01DDAB  1e                   push ds
01DDAC  e8 36 00             call 0x1DDE5
```

This is real-mode 16-bit startup code. The first automated descent must use
the MZ entry and remain bounded to the MZ load image; it must not treat the
tail as a continuation of the resident image.

## RTLink v1 appended-tail directory

The directory is a 70-record table at file offset `0x1E24F`, immediately
inside the resident MZ image. Each record is 18 bytes and uses the following
measured layout:

| Offset | Size | Meaning |
|---:|---:|---|
| `0x00` | 2 | load segment; an MZ relocation target in all 70 records, so the runtime value is stored + `0x046F` |
| `0x02` | 2 | filename offset within the RTLink segment |
| `0x04` | 3 | segment-header offset in paragraphs |
| `0x07` | 1 | flags; stored `0x04` for records 2–70 and `0x01` for record 71. `0x01` preload at startup (`1AA3:08B5`); `0x02` loaded (set `1AA3:044B`, cleared `1AA3:01D9`); `0x04`/`0x08` enable the cache hook; `0x08` also makes `+02h` an indirect pointer; `0x10` locks against eviction (`1AA3:01B2`, set only by restore at `1AA3:09D6`); `0x20` replaces the file read with a callback (`1AA3:0340`) |
| `0x08` | 2 | memory size in paragraphs, never below the stored size at `0x10`; the loader zero-fills the excess (`rtlink.py` still prints it as `unknown1`) |
| `0x0A` | 2 | relocation-record count |
| `0x0C` | 2 | parent record index, loaded after this record while `[0BF2h]` ≠ 0 (`1AA3:0458`–`0472`); `0xFFFF` ends the chain and index 0 is the empty record (`rtlink.py` still prints it as `unknown2`) |
| `0x0E` | 2 | directory segment index, 2 through 71 |
| `0x10` | 2 | code/data size in paragraphs |

The first record is an empty segment alias: records 2 and 3 share header
offset `0x1FB60`, and record 2 declares zero paragraphs. For every adjacent
record, the declared end of the preceding segment equals the next header
offset. The chain has 38,001 segment relocation records and covers declared
storage from `0x1FB60` through `0x14F5F0`.

The directory's filename offset resolves through the resident RTLink segment
anchor at file `0x1D630` to `FALCONCD.EXE` at file `0x1E91E`. This is the
internal overlay source name stored by the linker; no external `.OVL` or
`.RTL` file is present in the extracted game tree. The thunk list begins at
`0x1E99D` and contains 303 records of the form `E8 near-call`, `EA far-jump`,
target offset, target segment, and a zero-based directory index.

The final record declares an end at `0x14F5F0`, while the executable ends at
`0x14F5E7`, nine bytes earlier. All preceding boundaries are exact. This is
now resolved against DOS (see [Overlay loader contract](#overlay-loader-contract)):
the loader requests the paragraph-rounded size, DOS returns nine bytes short
with CF clear, and the loader, which tests only CF, continues. The nine bytes
are not file content and the loader never writes them. The earlier working
reading, "paragraph-rounded final storage with nine implicit zero/padding
bytes", was right about the rounding and wrong about the zeros: in the traced
run those destination bytes were already zero before the read, which is prior
memory contents, not a loader fill. Only record 71 has memory paragraphs
beyond its stored size (`0x153E` vs `0x1499`); the loader's zero-fill covers
that excess from the first paragraph after the loaded data, so it does not
reach the nine bytes either.

Re-run the audit with:

```text
python tools/re/rtlink.py game/FALCON3/FALCON3.EXE
python tools/re/rtlink.py game/FALCON3/FALCON3.EXE --json > work/rtlink.json
```

The parser is read-only and never writes the supplied executable. Its current
audit result is: 70 records, 38,001 valid segment relocations, 303 thunks, 0
directory-chain breaks, and a stored/declared tail delta of `-9` bytes.

## Runtime load mapping

The DOS oracle was sampled in the War Room with the RTLink boundary forced to
the measured MZ image end, `0x1FB51`, rather than treating the appended bytes as
one resident block. Six of seven distinctive MZ windows agreed on the same
file-to-linear delta:

```text
file -> linear delta: 0x1AF0
load-module base:     0x046F0 (segment 0x046F)
PSP segment:          0x045F
MZ residency sample:  20/29 windows (69%)
```

The mismatching MZ windows are not evidence of a bad load by themselves: the
MZ relocation table patches words, and runtime data can overwrite resident
bytes. One sampled window at file `0x1C160` gave `0x1506` instead of the
majority delta and is retained as an outlier rather than forced into the model.

No sampled `CS:IP` landed outside the MZ image during the War Room sample. A
same-delta scan over the appended region found 30/304 matching 16-byte windows,
but that is not evidence of a contiguous resident tail: RTLink records declare
separate load segments and the directory/headers themselves include zero and
metadata regions. The direct runtime samples confirm state-dependent writes at
the declared probe addresses, but do not yet identify the active overlay
record unambiguously.

**Correction (2026-09-13).** The per-segment probe below used the load-segment
word as stored in the file. That word is an MZ relocation target in all 70
records, and the traced loader writes every segment to the relocated value
(stored + `0x046F`; segment 71 goes to `0x64DD`, not `0x606E`). The table and
the War Room/Instant Action comparison that follow therefore sampled `0x46F0`
bytes below every real destination. Their 64/64 matches do not show
residency, and their cause is unexplained; re-measure at relocated addresses
before reusing any of these counts.

The per-segment probe then checked the declared destination directly as
`load_segment << 4` and compared the first 64 bytes of each non-empty segment.
After a 50-second War Room settle, these records matched exactly:

| Segment | Load segment | File code offset | Match |
|---:|---:|---:|---:|
| 16 | `0x5E0B` | `0x06BAA0` | 64/64 bytes |
| 17 | `0x5E0B` | `0x06D910` | 64/64 bytes |
| 71 | `0x606E` | `0x13AC60` | 64/64 bytes |

Most other slots had few or no matching bytes, which is consistent with
selective RTLink residency or runtime mutation. The match is only a probe of
the alleged destination address, not by itself proof of residency: several
payloads begin with zero-filled or metadata-heavy regions.

The same probe captured a second state after sending four `Right` keys, four
`Up` keys, and `Enter` from the War Room. The resulting screenshot is the
cockpit at [`work/qemu_out/rtlink_after.png`](../work/qemu_out/rtlink_after.png),
and the CPU was executing at `0629:35D1` (linear `0x09861`). The first 64-byte
match counts changed as follows:

| Segment | War Room | Instant Action |
|---:|---:|---:|
| 11 | 13/64 | 0/64 |
| 12 | 12/64 | 1/64 |
| 13 | 27/64 | 0/64 |
| 14 | 5/64 | 0/64 |
| 15 | 27/64 | 0/64 |
| 16 | 64/64 | 51/64 |
| 17 | 64/64 | 51/64 |
| 18 | 1/64 | 5/64 |
| 21–28 | 12–13/64 | 11–12/64 |

Segments 11–18 and 21–28 are therefore the clearest working-set transition
signal. Segments 16, 17, and 71 remain at their probed addresses, but 16 and
17 lose 13 matching bytes after the transition; this is runtime mutation or
relocation activity, not proof that those segments were unloaded. The probe
also saves complete 16 MiB guest-memory snapshots as
`work/qemu_out/rtlink_warroom_ram.bin` and
`work/qemu_out/rtlink_instant_ram.bin`. Full-segment byte totals are useful
for ranking candidates, but remain ambiguous because zero-filled and shared
data regions match coincidentally. A code-aware signature or write-trace pass
is still needed to name the active overlay with confidence. Re-run with
`python work/rtlink_runtime_probe.py`.

## Overlay loader contract

Status: `RESOLVED` for the seek, read, zero-fill and relocation path of records
without flag `0x20`, 2026-09-13. Which record is loaded, and what it evicts,
is in [Overlay selection and eviction](#overlay-selection-and-eviction).

The resident RTLink loader is in segment `1AA3` (file `0x1D630`). With BX
pointing at the directory record (`[0A8Ah]`, CS-relative):

| DOS address | Effect |
|---|---|
| `1AA3:02D6`–`0304` | code position = (`header_paragraphs` + ⌈`relocations` / 4⌉) × 16, in CX:DX |
| `1AA3:0306`–`0329` | if `[record+02h]` + 1 (through one indirection when flag `0x08` is set) equals `[0BF7h]`, add the 32-bit value the far pointer `[0BF9h]` addresses |
| `1AA3:032F` | `INT 21h AX=4200h` seek on handle `[0A8Eh]` |
| `1AA3:0340` | flag `0x20` set: call the patched far address at `1AA3:0383` instead of reading |
| `1AA3:0349`–`0352` | first chunk = `0x1000` − (((P − 1) & `0x7F`) + 1) paragraphs for start paragraph P, so it ends on a `0x80`-paragraph file boundary; later chunks are `0xF80` paragraphs |
| `1AA3:0354`–`037B` | read `[record+10h]` paragraphs into `load_segment:0000`, advancing DS; **only CF is tested** (`jb 038D`, error `0x13F`) |
| `1AA3:0398`–`03A7`, `0620` | zero-fill from `load_segment + [record+10h]` up to `load_segment + [record+08h]` |
| `1AA3:03F4`–`0445` | read relocation records in batches of at most `0x58`; here AX **is** compared with CX (`1AA3:0420`); each fixup adds `[0A86h]` + `0x10`, the PSP-derived load base |
| `1AA3:044B` | set flag `0x02` in the record |

`work/rtlink_tail_read_trace.py` arms GDB breakpoints from boot on the seek
(`1AA3:0332`/`0334`) and read (`1AA3:036A`/`036C`) and follows the timed
War Room → Instant Action route from `qemu-boot.md`; the end screen is the
cockpit in flight. The saved result is `work/qemu_out/rtlink_tail_read_trace.json`:

- 60 seeks and 60 segment loads (72 read calls), no CF, and no breakpoint hit
  outside the expected `1F12:xxxx` sites. In every seek the requested position
  equals the unbased code position, so the `[0BF9h]` addend was not applied.
- Every load wrote to the record's relocated load segment. Six runtime slots
  were used: `2165`, `227F`, `5B0E`, `6148`, `626E` and `64DD`.
- Segment 71 is the first overlay loaded: `0xFBA0` bytes from `0x13AC60`,
  then `0x4DF0` bytes requested from `0x14A800`, **`0x4DE7` returned, CF
  clear**. The loader proceeds. The nine destination bytes past the returned
  count were `00` before and after the read.
- The other 71 reads returned the full count, and the last 32 bytes written
  equal the file bytes at the traced position.

Load order in this run:

```text
71 3 5 3 5 3 13 7 4 3 4 3 4 3 32 31 4 50 56 50 66 50 66 50 66 50 66 50 66 50
66 50 66 50 66 50 32 37 32 57 65 57 65 57 32 50 32 3 30 5 3 7 9 10 8 18 5 3 4 6
```

Re-run with `python work/rtlink_tail_read_trace.py` after
`python work/set_boot_mode.py falcon3`.

## Overlay selection and eviction

Status: `RESOLVED` for the shipped option settings, 2026-09-13: static reading
of segment `1AA3`, confirmed by `work/rtlink_dispatch_trace.py`. The
save/restore entries and the flag `0x20` callback are statically described but
were not reached on the traced route.

| DOS address | Effect |
|---|---|
| file `0x1E99D` (`1AA3:136D`) | 303 ten-byte thunks: `call 058D`, `jmp far` (relocated segment), `dw index`; indexes 1–68, 66 distinct records |
| `1AA3:058D`–`05D6` | dispatcher: take the index at thunk + 8; push a 6-byte frame (index, caller IP, caller CS) at `[0A74h]:[0A72h]+[0A70h]`; error handler `0A48` with AX = 2 when the stack reaches `[0A76h]` (`[0C1Dh]` = `0x1E0`, 80 frames) |
| `1AA3:05D8`–`05F7` | option bit 0 of `[0C0Dh]` (stored `0x0001`): the caller's far return becomes `1AA3:0701` |
| `1AA3:0603` | load the callee: `021C` with AX = index; the dispatcher then returns into the thunk's far jump |
| `1AA3:0705`–`0754` | return: pop the frame (AX = 3 error on underflow), restore the caller's return address; while frames remain, `021C` for the index in the frame below |
| `1AA3:021C`–`0249` | AX = −1 returns; otherwise `[0A8Ah]` = record, and memory 0 or flag `0x02` goes straight to the exit |
| `1AA3:0275`–`02AA` | unload (`02A2`) every loaded record whose paragraph range [load segment, load segment + memory) overlaps the new record's; a refusal is error AX = 6 naming both segments (`024C`) |
| `1AA3:01B2`–`01EA` | unload: flag `0x10` refuses with CF; cache hook if `[0A84h]` ≠ 0 and flag `0x0C`; clear `0x02`; option `0x100` fills the freed paragraphs with `8E8Eh` |
| `1AA3:02AD`–`02C5` | cache hook `1C97:0003` if `[0A84h]` ≠ 0 and flag `0x0C`; otherwise the file load above |
| `1AA3:0454`–`0475` | exit: unless the load failed, and while `[0BF2h]` ≠ 0 (stored `0xFF`), load the parent index at `+0Ch`; `021C` recurses |
| `1AA3:0896`–`08C3` | startup: load every flag-`0x01` record |
| `1AA3:092B`/`0934`, `097F`/`098B` | save and restore the loaded set; restore clears `[0BF2h]` while it loads each index and sets or clears flag `0x10` |

Settings in the shipped file make several branches inert. `[0C1Bh]` is 0 and
`1C97:0003` is `stc; retf`, so `[0A84h]` is never set (`1AA3:080F`–`081F`) and
no overlay cache is used. `1AA3:0383` is `lcall 0000:0000` with no relocation
entry, no writer in the listing and no instruction that sets flag `0x20`.

The stored parent indexes form a tree, written as segment numbers: 8–15 and
18 → 7; 16–17 → 15; 19–20 → 18; 21–28 → 20; 32–70 → 31. The empty segment 2
is index 0; segment 71 and segment 2 itself hold `0xFFFF`.

The dispatch probe breaks only at the needed-load branch (`1AA3:0275`), at
each eviction (`1AA3:02A2`) and at the save/restore bodies, so the timed
navigation is unaffected; the end screen is the cockpit in flight. Result
(`work/qemu_out/rtlink_dispatch_trace.json`):

- 60 needed loads: 1 startup preload (71), 36 thunk calls, 21 return reloads
  and 2 parent-chain loads (7 after 13, 31 after 32). The order is identical
  to the read trace. Every thunk-call load matches the index in the top
  return frame, and the deepest stack at a load was 4 frames.
- 55 evictions. Every evicted range overlaps the incoming record's, every
  evicted record carried flags `0x06`, and none was locked. The most frequent
  pairs are 66 evicting 50 and 50 evicting 66, eight times each.
- No save or restore call.
- At the end: `[0C0Dh]` = `0x0001`, `[0A84h]` = 0, `1C97:0003` still
  `stc; retf`, `1AA3:0383` still `lcall 0000:0000`; the loaded records are
  segments 6, 7, 8, 18 and 71.

Re-run with `python work/rtlink_dispatch_trace.py`.

## Runtime file access

To identify the screen/resource boundary, a second oracle attached to the
running DOS process and set breakpoints on all 94 MZ `INT 21h` sites. At each
`AH=3Dh` open it read the caller's `DS:DX` pathname before single-stepping over
the interrupt. The resulting 77-event log is
`work/qemu_out/file_open_trace.json`.

The trace observes `WARROOM` during menu setup and `COCKPIT` during the
War-Room-to-Instant-Action transition, followed by `instact.mis`, `RADEC.Dat`,
`MainSeq.Dat`, `FalcObj.Bin`, `sobjects`, IRQ data, and `ARMSDATA` files. This
is direct runtime evidence for the asset-loading sequence. It does not yet
decode the files or identify which RTLink record contains each loader call.

Static correlation has now tied the `COCKPIT` open to a family of tail-loader
routines. They read a 12-byte six-offset index, seek to each indexed position,
read a 16-bit chunk length, stream that chunk with the shared DOS dispatcher,
and pass the resulting buffer to an asset post-processor. The six `COCKPIT`
payload boundaries are exact through file offset `0x10F59`; the final 27,711
bytes and the payload semantics remain unresolved. See
`analysis/resources.md` for the table and the generated structural metadata.

The active runtime copy is now identified as the loader instance at linear
`0x25DBD` (`23D3:208D`), whose `DS:0454` pathname is `COCKPIT`. Its chunk-5
path enters resident state 8 and the stream-copy callback at `13DB:7FD7`.
That callback exposes generated 4,096-byte and 3,328-byte working blocks at
`6F7D:53D4`, neither byte-identical to the raw file payload. This confirms a
post-read transform in the resident stream machinery; the final planar write
and palette path remain open. The detailed evidence is in
`work/qemu_out/cockpit_pipeline_trace.json`.

A follow-up raw-GDB capture temporarily removes the dispatcher breakpoint while
each `INT 21h` executes, then restores it at the wrapper return. It captured
the `COCKPIT` header, chunk-5 length and 6,496-byte payload, followed by the
chunk-0 length and 12,075-byte payload. The returned bytes match the installed
file exactly, so the DOS layer is not the compression boundary; the remaining
transform is higher-level code. The detailed trace is
`work/qemu_out/cockpit_io_trace.json`.

## Initial hypotheses to test

- The resident code uses an RTLink overlay manager; the appended data is now
  identified as an internal RTLink v1 segment stream, not a compressed resource
  archive. Its seek/read contract and its selection and eviction policy are
  resolved (see *Overlay loader contract* and *Overlay selection and
  eviction*).
- `EMMXXXX0` occurs in the resident image, consistent with the documented EMS
  requirement. The DOS oracle now reaches Instant Action flight with only
  `HIMEM.SYS` and `DOS=HIGH`; campaign and Red Flag EMS use remain untested.
- The main executable carries `COPYRIGHT 1991 SPHERE, INC. ALL RIGHTS RESERVED
  V3.05`; compiler/runtime identification is not yet settled from this string
  alone.
