# Poland loader: successful resource reads

Status: `PARTIALLY RESOLVED` (2026-10-06). The selected DOS Poland route now
has matched open returns, DOS read results and byte-for-byte resource evidence.
Decoded scenario state and the complete transitive loader/display closure are
still open. The authority is the unpatched `PANZER.EXE`, SHA-256
`115ada29636b32c3e07446fdf4569d97324d357a1e71dafb859dd95c3cb69a86`.

## Scope and reproduction

Use the real CuteMouse/no-sound disk and menu inputs in
[scenario-route.md](scenario-route.md), on QEMU `pc`, CPU `486`, 16 MB and
standard VGA. This probe sends input and observes stopped memory; it does not
write game state. It uses the corrected LE page map, not the superseded tail
interpretation. Object 1 is at RAM `0x17D000`, object 2 at `0x1E0000`;
`runtime = file + 0x124D5C = vaddr + 0x16D000` for these captures.

```text
python3 work/drive_menu.py --hdd work/qemu_out/pg-mouse.hdd \
  --out work/qemu_out/poland-io-3 --script work/routes/poland.json \
  --seconds 50 --file-io
python3 work/check_file_io.py work/qemu_out/poland-io-3
```

Choose a fresh output directory. This run omits the broad trace plugin;
`--file-io` implies the open-entry probe and adds checked instruction
boundaries in `work/probe_file_io.py`. The runtime prefixes must match the
selected file bytes before arming. Paging must be off and data/stack segments
flat; each file-I/O stop also checks the code segment base. A main-menu pause
may be inside the extender's non-flat IRQ gate, so its sampled CS is not the
file wrapper's execution context.

The metadata retains helper/tool hashes, open stacks, return values, I/O
registers, destinations and returned byte hashes. Captured read buffers are
saved immediately, before the CRT reuses them. They are raw resource evidence,
not decoded game-state fixtures. `check_file_io.py` verifies the returned
length/hash, each measured file range and full byte coverage of all five
resources against the pristine distribution. It does not certify format
decoding or JavaScript/native parity.

## Measured results

All six opens succeeded. SCENSTAT, GAME001 and MAP01.SET use handle 5;
MAP01.STM opens as handle 6 while MAP01.SET remains open. Both arrow opens
reuse handle 5. Handle identity is scoped by open/close lifetime, not filename.

| Resource | File position | Requested | Returned | Destination RAM |
|---|---:|---:|---:|---:|
| SCENSTAT.BIN | 0 | 6656 | 6656 | `0x211080` |
| SCENSTAT.BIN | 6656 | 4096 | 344 | `0x10F038` |
| GAME001.SCN | 0 | 4096 | 447 | `0x10F038` |
| MAP01.SET | 0 | 4096 | 2139 | `0x10F038` |
| MAP01.STM | 0 | 4096 | 576 | `0x11003C` |
| AXARROW1.SHP | 0 | 1442 | 1442 | `0x3DD4EE` |

All 11,604 distinct resource bytes match the file hashes recorded in
`scenario-route.md`. The probe paired requests with returns by operation and
stack address and tracked successful seeks. The first arrow open measures its
length and closes without reading; the second performs the full read.
The guest reached the Poland tactical screen (Prestige 228, Fair weather),
exited QEMU normally and left the source disk unchanged. The capture
was repeated on a freshly rebuilt `work/qemu_out/pg-merged.hdd`, using the
integrated builder, into `work/qemu_out/poland-io-merged`. All five full-byte
checks passed again; the tactical PPM hashes are
`6e8a24fde97a63ac2e354deb60926f129612bf19ba47081e6739d2b66ddeba98`
and `904af82a5e8a1b6e450908d943b85699483bb3cc52d04f9894d78a07a94f3929`.
Both screens were visually checked for the tactical state; screen byte equality
is not claimed by this wall-time input schedule.
The initial probe
`poland-io-1` captured only the low-level arrow read; the missing stream reads
led to the additional checked CRT wrapper below. The rejected
`poland-io-2` run stopped at its execution-context guard and is not proof.

## Recovered DOS identities and boundaries

Use the existing disassembly's canonical `sub_<vaddr>` names. The inventory
`work/re/functions.txt` is regenerated from the 21 evidence-carrying seeds;
it retains all 642 recovered entries. Descriptive names below are aliases.

| Canonical DOS ID | File range | Recovered boundary |
|---|---|---|
| `sub_00067FC8` | `0xB026C..0xB0431` (end exclusive) | Stack-argument open; returned EAX captured at epilogue `0xB0428` |
| `sub_00067E50` | `0xB00F4..0xB0207` | Read wrapper; binary `INT 21h` at `0xB0139`, text branch at `0xB0171` |
| `sub_0006B929` | `0xB3BCD..0xB3BEC` | Stream's direct DOS read at `0xB3BD4` |
| `sub_00067F63` | `0xB0207..0xB0248` | Seek; DOS call at `0xB021B`, reconstructed return at `0xB0242` |

The DOS call's carry is encoded into bit 31 by `rcl eax,1; ror eax,1`.
Read results are captured after those instructions, before the buffer is
consumed. A set sign bit is an error, not a byte count; the error paths and
text translation remain unproven. Close is observed at file `0xB3E4C` and
after normalization at `0xB3E52`; its nonnegative DOS EAX is not required to be
zero (these successes returned `0x3E01`). The encompassing close-function
boundary still needs its own inventory evidence.

The first four open stacks identify calls through `sub_00065FF7`,
`sub_000660BF` and `sub_000660DA` (stream-open wrappers). SCENSTAT's game caller
is `sub_00032085` (return file `0x7A585`); GAME001's game caller
is `sub_00037216` (return file `0x7F631`); MAP01.SET and MAP01.STM both come
from `sub_00037E75` (returns `0x80162` and `0x8047C`). The arrow's low-level
open callers are `sub_00063A66` and `sub_00063ADA`. Return addresses are
call-site witnesses, not new function IDs. The CRT wrappers in the table remain
unported; the selected SET/STM game contract is implemented as recorded below.

## Next discriminating measurement

### Completed loader state (2026-10-06)

`work/probe_loader_state.py`, invoked with `drive_menu.py --loader-state`,
captures the entries and completed returns of `sub_00037216` and
`sub_00037E75`. The successful `work/qemu_out/poland-state-1` route has both
stack-balanced returns, normal QEMU exit and an unchanged source disk.
Full object-2 snapshots retain all globals, alongside bounded copies of the
arrays addressed by those globals. Snapshot/hash metadata is in `route.json`.

At both completed returns, the inclusive maxima at object-2 `0xCC90` and
`0xCC8E` are 17 and 15: 18×16 cells, 288 words per map array. Pointer `0xCB84`
addresses 576 STM bytes at RAM `0x378B5F`, byte-equal to MAP01.STM. Pointer
`0x17934` addresses 576 map bytes at `0x376F4A`, equal to MAP01.SET's final
576 bytes with bit 7 of each high byte cleared. The clearing loop is vaddr
`0x38263..0x382CC`; it belongs to `sub_00037E75`, not a new DOS function.
Poland's source words already have those high bits clear. This capture proves
the resulting array equality; a nonzero-flag fixture is still needed to prove
the clearing branch dynamically.
These measurements identify the retained arrays rather than reused CRT buffers.
They do not by themselves close the rest of the loader's side effects.

The loader's geometry prerequisites `sub_00010976` and `sub_00048105` now
have DOS-validated JavaScript and m68k implementations; see their durable
function records and `docs/PORTING-PLAN.md`. No whole-loader or gameplay
implementation is claimed yet.

### Ported successful SET/STM boundary

`poland-fields-4` captures 246 paired reads across the SCN and SET loaders,
including 23 SET/STM reads: 22 from SET, one from STM. The first SET byte and
five 20-byte fields occupy 0..101, dimensions 101..105, nine discarded words
105..123. Four active layers then occupy 123..1563, followed by the retained
map words through 2139. Layer IDs 0/2/4/5 have widths 2/1/1/1 and each has
288 cells. Separate STM data remains 576 bytes. The SCN field/consumer contract
is not yet complete merely because its reads were captured.

The fixture collector verifies each paired read range against the pristine
resource, including stream lifetime and exact returned item counts. It retains
only the selected input globals, observable output globals and six arrays,
excluding CRT buffering/allocator internals and dead stack bytes. Branch joins
following read calls can also execute without the call; only a paired entry
and matching return PC prove a read. Stream positions reset for the distinct
loader lifetime, since the CRT reused its SCN stream address for SET.

`sub_00037E75` now matches these results in JavaScript and m68k. A second
measurement retains 52 direct string-copy/append contracts during loading,
including return pointer identity and source delta. Native Falcon030 4 MB
Hatari compares all 6,779 canonical bytes. Records and open differences are
in `analysis/functions/sub_00037E75.md`, `sub_00060907.md`, `sub_00060926.md`.
This closes the measured isolated successful boundary, not the connected game
or missing-file/short-read/other-configuration paths.

Trace `sub_00037216` and `sub_00037E75` from successful stream open through
consumption and return. Capture the decoded fields and owned destination
arrays, distinguishing reused CRT buffers from retained scenario state.
Map each field consumer to GAME001/SET/STM input bytes before implementing
the JavaScript contracts. The SET literals naming TACMAP.SHP/TGF remain
transitive dependencies even though this probe did not see their opens;
measure preload/reuse or other load paths. VESA480 driver exports, indirect
callbacks and error/text branches remain visible unresolved items.
