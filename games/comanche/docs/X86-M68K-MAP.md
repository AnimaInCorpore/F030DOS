# DOS x86 to Falcon 68030 map

This is the durable traceability index between the unpacked DOS program and
the Falcon implementation. It is not a claim that x86 instructions translate
one for one to 68030 instructions, nor the complete function ledger. It records
which recovered DOS behaviour a Falcon routine replaces and the evidence used
to make that association; the linked `METHOD.md` §4.2 function record holds the
full DOS contract, browser counterpart/fixtures and difference ledger.

The MC68030 remains primary. The optional MC68060 image replaces unsupported
wide multiply instructions with exact partial products, and adapts vector/cache
handling at the Falcon boundary. Both preserve the same recovered numeric
contracts; RGB565 conversion remains a separate presentation exception. See
the [CPU compatibility record](../analysis/functions/cpu-compatibility.md) for
interfaces, differences and executed checks.

The Falcon implementation sources for the first CPU-only attract milestone are
now present under `src/`. Their source-selection and route witness are recorded
in `analysis/functions/falcon-attract.md`; later source rows remain targets
until their own DOS route is traced.

## Porting rule

Use the [function-level porting specification](FUNCTION-PORTING.md) for
per-routine contracts and source-comment fields. Keep canonical identities,
split/merged mappings, numeric layouts, and specific fixtures in the linked
records; the map and adjacent comments identify implementations, while
acceptance artifacts establish the verified scope.

This map governs a faithful port of the hashed DOS binary's behaviour. The
disassembly, browser model and Falcon counterpart may be restructured, but
captured DOS execution decides mechanics, arithmetic, sequencing and visible
results. After the milestone route is traced, use the browser harness to
investigate and reproduce a function before its Falcon port, then confirm its
hypotheses against the DOS route and preserve them as fixtures.
Platform differences must be explicit and local; an unproven mechanic is not
replaced by an approximation.

### Route-first milestone rule

Before any JavaScript or M68k source is created or changed for a milestone,
trace that milestone through the authoritative DOS executable with QEMU's TCG
`exec,nochain` execution extension, a repeatable input schedule, and state/memory snapshots.
Record the reached function entries, indirect callback targets, resource
pointer assignments, state transitions, and frame order in a durable route
manifest. Generate only the JavaScript/M68k sources represented by that route;
unreached or unexplained functions remain `dormant`/`Unproven` and cannot be
used to support the milestone. The browser and Falcon implementations are
validation counterparts, never the authority that defines the route.

Use flat game addresses relative to the shared selector base at image offset
`0x1700`. Bootstrap addresses retain `seg:off` form and should normally map to
a Falcon platform replacement rather than translated game code.

The DOS binary authority is `re/unpacked/COMANCHE.UNPACKED.EXE`, SHA-256
`4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697`.
Every source annotation and map row must resolve to that image and a canonical
flat range, or say `N/A - platform replacement`.

For every represented function, the function record names the DOS fixture,
browser symbol/fixture, Falcon symbol, and each difference from DOS. The map
row is not enough by itself: state and prove even “no difference”; an
unresolved difference is `Unproven` and cannot enter a supported path.

## Browser attract milestone (2026-08-25)

`jsComanche/dos-runtime.js` is the current browser counterpart for the first
recreation slice. Its durable §4.2 function records are in
`analysis/functions/browser-attract.md`. It is grounded in the rows below rather than being a second
behavioural authority: `00005690-00005AE3` drives the pass/screen schedule,
`00018C29/00019A2D` supplies the fixed `DEMO<n>.SCR` replay, the terrain rows
at `0000D950-0000F317` consume the authored `HIGH.DTL`/D/C maps, and the
palette/sky, opening-screen, and cockpit/HUD rows supply the composition rules.
The browser uses a linear 320×240 RGB565-equivalent surface as a platform
adaptation of the left 320 columns of DOS's 328×240 Mode X page; Falcon pixel
parity remains a separate capture gate recorded in the Falcon route record.

The implementation confirms the following reusable boundaries for every port:

- `SKY<n>.RLE` is 512 column-major strips × 150 rows, not a 320×240 raster;
- DTA palette bytes are six-bit DAC values shifted left by two, while SG bank
  palettes are six-bit and must be translated into the active palette; and
- screen composition draws the authored page and overlay first, then advances
  the animation/pan state, while terrain uses the same 192-column backdrop tilt
  and strict ring-major occlusion contract.
- flight composition is not a guessed cockpit: `CONSOL1S.DTA` is a 328×290
  top-row-aligned image with transparent index `255`, `CONS.RLE` supplies the
  three fixed opaque instruments at the recovered coordinates, and `HUDS.RLE`
  is a separate column-major bottom-first bank for the authored overlay;
- the HUD's `SPEED`, clearance, compass, reticle, and sight line are reached by
  DOS `0000D703-0000D887`; the browser keeps the `00025CA2` integer line walk
  and fixed green `0x47E8`, while the phase-gated `0000D88C` COMA tail remains
  skipped in attract phase 1.

The attract route was traced before the browser sources were expanded: the
QEMU TCG execution report and active-slot snapshots identify the frame driver,
replay/flight path, mission factory, callback table, transient allocator,
terrain/object transform, and effect/destroy handlers. The route artifacts are
`work/qemu_out/attract-trace-report.txt`,
`work/qemu_out/object-state-walk.txt`, and the reproducible runners in
`work/run_qemu_exec_trace.py`, `work/trace_attract_report.py`, and
`work/inspect_qemu_state.py`. Future milestones must add the equivalent route
manifest before adding JavaScript or M68k sources.

The browser simulation is driven through an explicit `advanceTicks(count)`
seam. Its 60 Hz fixture clock is presentation-only evidence for a runnable
page; DOS wall-clock cadence is still `Unproven`, so no port may treat 60 Hz as
the game's recovered rate. The page records an ordered tail of replay input
bytes, transition/record events, pre-draw and post-tick state checkpoints, and
canonical RGB565 framebuffer hashes for fixture callers. The connected page
contains only the canvas: it exposes no DOM keyboard path, mission selector,
pause control, restart control, persisted file cache, or diagnostic panel.

The browser implementation intentionally leaves live keyboard input, sound,
menu handoff, and mission completion outside this fixture. The authored
mission object factory, replay callback dispatch, transient weapon/effect
children, state/update pass, viewer transform, DTL projection, depth sort, and
SG/effect draw pass are active in all four attract missions; QEMU TCG execution
and active-slot snapshots are retained under `work/qemu_out/`. Any
later Falcon or DSP milestone must preserve the shared boundaries above and
add its own function-record fixture and route manifest before widening that
scope.

Classification evidence uses a separate closed grade: `executed/content-matched`
for a runtime observation or output comparison; `ratchet+guard` for a static
decode backed by an independent target/encoding check and an explicit data
guard; or `sweep-inferred` for a recursive/linear classification that has not
yet crossed either stronger gate. The Evidence field must name the grade and
the concrete witness. Confidence remains semantic confidence and must not be
used as a substitute for classification evidence.

## Kind, status and confidence

Three closed sets, and they answer different questions. Keeping them in one
field is what produced thirteen unmanaged phrasings of "platform something"
and made the substitution surface impossible to enumerate.

**Kind** — what the Falcon code *is*, relative to the original:

| value | meaning |
|---|---|
| `translated` | the Falcon code implements the DOS routine |
| `adapted` | grounded in a DOS routine, same observable result, different mechanism — a surface port, a DSP path. METHOD.md §4.1 adaptation |
| `replaced` | the DOS algorithm is not carried over; the platform does the job. A DOS authority may still be named, and should be |

`replaced` is the substitution surface METHOD.md §4.2 asks to be closed and
reviewed as a whole. `docs/SUBSTITUTIONS.md` is generated from these fields by
`tools/substitutions.py`; `--check` fails if it is stale or if a header
carries a Kind outside the set. The boundary that matters is `adapted` versus
`replaced`: an `adapted` routine still owes fidelity to the original's
result, and quietly restating one as the other is how the category widens.

**Status** — how far the work has got:
`unclassified`, `recovered`, `ported`, `partial`, `verified`, `dormant`.

**Confidence** is `low`, `medium`, or `high` and must describe the current
evidence, not how plausible a provisional name sounds.

## Function map

| DOS address/range | DOS name or role | Contract and side effects | Falcon counterpart | Status | Confidence | Evidence |
|---|---|---|---|---|---|---|
| `00001538-000018D3` | protected-mode game entry | Loads DS/ES/SS with `0x08`, FS with `0x30`, GS with `0x38`, then derives three globals the rest of the image depends on: `[000014B4]` = `0x170<<4` = the selector base `0x1700`; `[000014C8]` = `0xB8000 - 0x1700` text VRAM; **`[000014C4]` = `0xA0000 - 0x1700` = `0x9E900` graphics VRAM** - the base every blitter and the presentation layer reads. | `src/start.s` plus the Falcon platform layer. Only `[000014C4]` carries over, and only as "this is the surface pointer"; the derivation itself is DOS-specific | recovered | high | Decoded in full; confirms from the game side the GDT that was derived from the bootstrap side. |
| `000014E4` and `00001510` | IDT gate installers | `000014E4` (31 callers) writes a 386 interrupt gate - type `0x8E` through selector `0x20`, 32-bit offset split across `+0` and `+6`. `00001510` (19 callers) writes a 16-bit gate - type `0x86` through selector `0x10`, offset high word forced to zero. | none - the Falcon has its own exception and interrupt model | recovered | high | Both decoded; together they explain why the IDT template in the file holds placeholder offsets. |
| `00001950` | BIOS shift-state read | FS is the flat selector, so `fs:[0x417]` is physical `0x417`, the `0040:0017` BIOS keyboard flag byte. Masks the low nibble, writes it back, passes bits 4-6 on. This is the origin of the shift state that selects between the two scancode tables. | Falcon IKBD status; the two-table selection carries over, the BIOS data area does not | recovered | high | Decoded; the address resolves through the documented flat selector. |
| `00015DD0-00015E6D` | DOS file reader | Takes an inline NUL-terminated filename, uppercases it, opens read-only, reads `0xFA00`-byte chunks until a short read, closes the handle, and records the byte count. | `src/mission.s:mission_read_file` and the DTA reader in `src/resources.s` | ported | high | Flat listing shows `Fopen`/`Fread`/`Fclose`, the `0xFA00` loop, and the shared byte-count store; Hatari verification requires the Falcon mission path to use bounded `0x1000` transfers. |
| `00015CDC` | file existence probe | Uppercases an inline NUL-terminated name into a `'$'`-terminated DOS string and asks for it without reading; the carry flag is the answer. Called by the catalog walk at `0002A121` and four startup sites. | `src/mission.s:mission_probe_campaign`, a GEMDOS `Fopen`/`Fclose` on the same patched name | ported | high | Five call sites, each with an inline filename; `0002A12D` skips a campaign on carry set. |
| `0002A104-0002A1AC` | campaign catalog | The startup step at `0000561F`. Walks `0.MIS` through `9.MIS`; for each that exists, reads it into the arena, decodes it, takes the file's own catalog title - the first `{...}` in the stream, ahead of any mission - and lays it over the campaign screen's row at `00029C03 + n*0x20` behind two spaces, plants `00 00 FF 00` one row further on as the end of the list, and records the file's digit in the table at `00029D47`. The row cursor only advances for a file that was found. | `src/screen.s:screen_fill_campaigns`, using `src/mission.s:mission_probe_campaign` and `mission_load_campaign`; the same rows and the same digit table, in the same place inside the text block | ported | high | Ten-entry loop at `0002A115`, probe at `0002A121`, patched read at `0002A139`, decode at `0002A14A`, brace pair at `0002A15D`/`0002A165`, `0x2020` prefix at `0002A170`, `0xFF0000` at `0002A17E`, digit store at `0002A18F`. Both shipped catalogs read back in Hatari. |
| `0002A1AD-0002A299` | per-pilot mission list | Reads the SELECTED PILOT's campaign file - pilot `[00029701]`, that pilot's campaign `[00029702+pilot]`, the digit table `[00029D47+campaign]`, patch and read - then lays up to ten mission titles into the mission screen's rows at `00029D95 + n*0x20` behind `"\|g  "`, padding each with `0xFC` and terminating it. Each entry also records two flags: `[00029F18+n]` is set when the closing brace is followed by `'*'`, and `[00029F2C+n]` holds the digit after that star plus one. `[00029EF0+n*4]` keeps a pointer into the stream for the briefing. | `src/screen.s:screen_fill_missions` and `screen_select_campaign` | ported | high | Rows and both flags read back in Hatari for both campaigns; the description pointers are not kept, because no briefing screen reads them yet. |
| `0002A2F8-0002A31C` | mission stream decoder | If the stream does not begin with `{`, XORs each little-endian dword with `0x11120603` (memory bytes `03 06 12 11`) in place. | `src/mission.s:mission_decode` | verified | high | Flat listing gives the exact dword loop and constant; applying it to `0.MIS` produces the readable `{Comanche Training}` stream and Hatari reaches the parsed start state. |
| `000290C6-00029359` plus `0002A2BF-0002A2F7` | selected mission scalar/object parser | Skips the resource list, parses decimal scalar lines and the start tuple, then walks the object records. | `src/mission.s:mission_parse` and `src/game.s:game_init` | ported | high | Flat listing shows the `<` boundary, decimal helper, `<<22/<<24` coordinate conversion, and object-line loop; Hatari's mission-present and missing-file frames use different start positions. |
| `00006BF0-00006FEF` | unrolled vertical span writer | Duff's device: the caller jumps N stubs into an array of 255 `mov [ecx],al` / `inc ch` pairs and falls through to a `ret`, writing 256-N pixels. `inc ch` adds `0x100` per pixel, so the surface has a 256-byte stride and `ecx` is `row:column` as `ch:cl`. Colour in `al`. | `src/render.s:TERRAIN_PAINT`, inline in each column loop | recovered | high | Decoded in full; the terminating `mov [ecx],al` / `ret` at `00006FEC` bounds it exactly, and its 192 callers all reach it through `lea ebx,[ebx*4+0x6bf0]` / `jmp ebx`. |
| `0000D950-0000F317`, `000137F0-00015854` and `0001B26C-0001C191` | voxel terrain renderer, three detail levels | Ring-major: the outer loop walks the .DTL's 250 depth rings, the inner all 192 columns of one ring laterally. The page index AL starts as `NOT(alt)>>1` = `127 - floor(alt/2)`, so against the page's `(k-128)` the **effective camera height is alt/2 + 1**. Per sample: pack X:Y into a 10-bit index with `shld ebx,edx,0xa` / `shld ebx,edi,0xa`, sample the heightmap with `add al,gs:[ebx]` (GS = arena selector `0x38`), look the page byte up, and compare against that column's running horizon held in a stack array. On `ja` (strictly above), the emitter paints **[old horizon, new top)** - the projected row itself goes to the next deeper sample - and stores the new top. Page rows land on the 240-row screen unscaled as `screen row = 213 - page row` (the 256x256 surface is stored upside down; an earlier reading said 198 and the anchor table below corrects it). Zeroes the horizon array and calls the viewport fill before starting; archives each ring's horizon array (the sprite-clip silhouette). The ring loop's page pointer advances by `inc word [00019EDD]` - plus 0x100 per ring with the alt-bias low byte untouched - and the ring restart pair popped at `0000F301` is the centre pushed at `0000D9B9`, so the centre accumulates ring to ring. | `src/render.s` - one parameterised column marcher; the three DOS copies differ only in column count and bank, so they collapse into one Falcon routine with a detail parameter. Camera term, span convention and 1:1 rows adopted 2026-08-17 | recovered | high | `0000D950` and `000137F0` decoded instruction-for-instruction identical apart from setup target and fill pointer; `0001B26C` proven by `call` at `00007909`, the only reference into its window. Each marcher's `ja` targets stride 48 bytes from its own bank's block 0, binding renderer to bank 1:1. Span convention read off emitter block 0 at `0000AF50`: `ch` starts at the OLD horizon, the Duff entry is `256 - (old - new)`, and the new top is stored before the jump. |
| `00007D25-0000AF4E` and `000107A0-000137E9` | per-column ray/scale setup | Reads `[00019D04]`, indexes `[ebx*4+00019D94]` by the variant byte `[00019D86]`, and derives `[00019CB0]`/`[00019CB4]` from a table at `00032120` read at `[ebp]` and `[ebp+0x200]`. That table is the shared Q31 sine table and `+0x200` is +90°, so the pair is the **sin and cos of the view heading**, not an unexplained scale pair. | folded into the Falcon renderer's per-frame setup; use the platform's own sin/cos or the same Q31 table | recovered | high | Identical prologues at both addresses; each is called from exactly one renderer (`0000D950` and `000137F0` respectively) and from nowhere else. Table verified as sine: entry 0 = 0, entry 128 = `0x7FFFFFFF`. |
| `00019C94` selected at `000261F4`/`00026207` | detail-level selection | `[00019C94]` holds `0000D950` or `000137F0`, chosen by whether `[00025DD9]` is `0x7D`; the frame is rendered by `mov eax,[0x19c94]` / `call eax` at `0000D3F5`. The same routine installs the matching viewport fill pointer. | a detail setting read once at mode change, not per frame | recovered | high | Both stores decoded; `0000D3F5` was already on record as an indirect call site with unknown target, and this supplies it. |
| `0001757E-00018999` and `0001CAD0-0001D7EB` | strided viewport fill, plain members | Reads a destination base from `[00019E70]`, adds `+0x10` (`0001757E`) or `+0x2C` (`0001CAD0`), and replicates the single byte at `[0002A37E]` into all four lanes of the fill dword. Body is 512 (resp. 256) copies of `mov ecx,0x18 / rep stosd / add edi,0x20`: writes 96 bytes, skips 32, 128-byte stride, spanning 64 KiB (resp. 32 KiB). | none yet - a parameterised fill on the Falcon side; the 96-of-128 stride must be reproduced from the destination surface's real pitch, not copied as a constant | recovered | high | Decoded in full from the entry; both bounded by their terminating `ret`. Entry confirmed by `000261AF` storing `0001757E` into `[00019C98]`/`[00019CA0]`. |
| `00016EC0-00017213`, `00017230-00017579`, `0001C920-0001CAB2` | strided viewport fill, sourced variants | Each reads a source pointer from `[00019CA4]` and jumps to its plain counterpart (`0001757E` or `0001CAD0`) when that pointer is null; otherwise copies from the source with per-variant `ecx`/`edi` setup. | none yet - same Falcon fill/blit path as the plain members, with the source-present case as the blit | recovered | medium | Decoded from each entry to its `ret`; the null-check-and-fall-back to a plain member is what groups the family. Per-variant geometry read but not yet tied to a known surface. |
| `000261AF-000261D8` | viewport fill selector | Writes `[00019C98]`, `[00019C9C]`, `[00019CA0]` with plain members by default; on `cmp byte [00025DD8],0x7D` installs the sourced variants instead. | Falcon: a small render-mode struct or jump table set once at mode change, not per frame | recovered | high | Decoded in full; the pointers it writes match the family entries above, and the adjacent `00019C94` is already on record as the target of `mov eax,[0x19c94]` / `call eax` at `0000D3F5`. |
| `0000AF50-0000D34C`, `0000F323-00010793`, `0001C1A0-0001C917` | per-column span emitters, three banks | 192, 96 and 40 specialised blocks, one per terrain column per bank - almost certainly the three `.DTL` detail levels. Each block holds its column in an immediate `mov cl,imm8`, reads its run length from a dedicated stack slot between `esp+24` and `esp+127`, pushes its own return address, and jumps into the span writer above. **Self-modifying:** each block's `mov al,[ebx+0xffff]` carries a placeholder displacement that init patches with the real source address. | `src/render.s:TERRAIN_PAINT` - one macro instantiated per sweep direction and detail level, its column clip and address from the per-frame `ring_cols` | recovered | high | 328 occurrences of the 7-byte `lea ebx,[ebx*4+0x6bf0]` signature in three clusters; 192 distinct `cl` immediates in bank 1; the patcher at `00006279` writes each block's `+4` dword at a 48-byte stride. |

Add rows only when an address is supported by control flow, cross-references,
runtime observation, or a decoded data contract. Large coordinators may be
split into several Falcon routines; several DOS wrappers may map to one Falcon
platform routine. Record either case explicitly.

## Per-routine source annotation

Every ported source-level function must have a compact header immediately
above its label. Helpers with no separate DOS entry inherit their parent
routine's address and say so; Falcon/TOS-only routines use `N/A - platform
replacement` rather than inventing a DOS address. The header must distinguish
the recovered DOS contract from work added only to make the Falcon target run:

```asm
; DOS: flat 000xxxxx-000yyyy, <routine or data contract>.
; Record: <checked-in function-record path and fixture IDs>.
; Route: <milestone route manifest and reached-entry witness>.
; Browser: <symbol/file, or N/A - platform adapter>.
; Port: <Falcon-specific implementation or platform boundary>.
; Preserved: <arithmetic, ordering, data, side effects, and visible result>.
; Difference: <DOS change IDs, or none - equality fixture ID>.
; Kind: <translated/adapted/replaced>[ - <what the platform does instead>].
; Status: <status>; <validation or explicit gap>.
```

`Kind` and `Status` each take a value from their set above and nothing else.
A strategy phrase such as "platform surface port" belongs after the dash on
the `Kind` line, not in place of a status.

The source header links to the durable record; it does not replace it. A
browser experiment may help identify a purpose or seam, but its result is only
a hypothesis until DOS evidence and a fixture confirm it.

When a routine is deliberately not ported, record why in the same header:
`DOS: ...; Port: dormant/stopped; Status: unrecovered` or
`DOS: N/A - platform replacement`. Do not use a generic file header as the
only provenance for a function, and do not describe a guessed value as
preserved. The corresponding address and evidence still belong in this map.

## Resource formats loaded at startup

| DOS address/range | Role | Contract | Falcon counterpart | Status | Confidence | Evidence |
|---|---|---|---|---|---|---|
| `00005604-000066C5` plus `0002A320` and the fill loop at `0002913C` | startup manifest and mission-supplied filenames | The startup sequence names 27 resources inline. **21 of those slots are rewritten from the mission file.** `0002913C` runs 21 iterations; per slot it takes the pointer from `[ebx*4 + 0002A320]` and copies a whole name - at most 12 characters, terminated by space, `;` or `<`, then space-padded - out of the mission stream. A separate reset at `00029127` first writes `'-'` into the ten sprite slots, and the startup skips any slot still holding `'-'` (`cmp byte [00006525],0x2D`). | Falcon: read the resource names from the parsed mission data. **Do not reproduce writing into string literals** - build the names into a table | recovered | high | Fill loop decoded with its terminator and padding; table start bounded by the code preceding `0002A320`; the trailing spaces in the shipped inline names are that padding. |
| `00029582-00029B2C` ← `COMANCHE.NAM` | pilot roster | 1,450 bytes. 8 records of 43 bytes, format ` \|b<FD><FD><digit>\|g <name>` padded with `<FC>` and NUL-terminated - the same markup `text_render_loop` interprets - then the DEL prompt and a trailer. The image holds a default roster with blank names which the file overwrites. | `src/screen.s:screen_roster_load`, into the same 43-byte record shape; the markup is already handled by the text renderer. The image's default copy is not committed, so a missing file leaves the buffer zeroed and a short read is refused rather than indexed into. The save side, `00027D92`, is not ported | ported | high | File offset 344 (`"\|p (Press DEL to enter a new player)"`) lands exactly on image `000296DB`, where the 8 default records end. Shipped file has names where the image has blanks. |
| `00025DBC-00025DDF` ← `COMANCHE.MNU` | settings | Only 35 bytes: six little-endian word pairs (screen coordinates), `0x03` at `+0x17` (joystick axis-presence mask), ASCII `"1003"`, then `"}}}}}{{"` at `+0x1C`. **Those trailing characters are the mode flags** the viewport-fill and terrain-renderer selectors test with `cmp byte [00025DD8],0x7D` - `0x7D` is `'}'`. | a small Falcon settings record; the detail/fill choice must come from configuration, not be hardcoded | recovered | high | Load site decoded (`mov eax,00025DBC` / inline `"Comanche.MNU"`); the field offsets line up with `00025DD3`, `00025DD8` and `00025DD9`, all previously seen as unexplained constants in the renderer selectors. |

## Object table, field by field

The table is a structure of arrays - 14 dword fields of 130 entries at stride
`0x208` from `0001FC30`, then 13 byte fields at stride `0x82` from `000218A0`.
That layout is 386 addressing rather than a contract, and the port does not
reproduce it, but it has one property worth keeping: **every field is already a
contiguous array of one width**, so each is annotated separately and each can be
emitted for a 68k. A record of mixed-width fields could not be.

The two aggregate rows that stood here before said "14 x 130 dwords" and "13 x
130 bytes" and gave no way to emit either.

| dword field | name | byte field | name |
|---|---|---|---|
| -2 | `obj_draw_order` | 0 | `obj_heading` |
| -1 | `obj_speed` | 1 | `obj_active` |
| 0 | `obj_draw_fn` | 2 | `obj_anim` |
| 1 | `obj_state_fn` | 3 | `obj_altitude` |
| 2 | `obj_model_a` | 4 | `obj_prev_alt` |
| 3 | `obj_model_b` | 5 | `obj_damage` |
| 4 | `obj_lateral` | 6 | `obj_byte_6` |
| 5 | `obj_depth` | 7 | `obj_byte_7` |
| 6 | `obj_x` | 8 | `obj_view_bearing` |
| 7 | `obj_y` | 9 | `obj_byte_9` |
| 8 | `obj_prev_x` | 10 | `obj_byte_10` |
| 9 | `obj_prev_y` | 11 | `obj_timer` |
| 10 | `obj_dword_10` | 12 | `obj_byte_12` |
| 11 | `obj_dword_11` | | |

The split checks itself. Each field array holds one uniform default, and the
exported values are exactly the ones the aggregate rows had recorded: `obj_x` is
130 copies of `40000000`, `obj_y` of `D4800000`, `obj_state_fn` of `00024860`
and `obj_draw_fn` of `0002514D`. A field boundary that was off by one entry
would not produce that.

## Object table

| DOS address/range | Role | Contract | Falcon counterpart | Status | Confidence | Evidence |
|---|---|---|---|---|---|---|
| `00020040-0002189C` | object table, dword fields | 12 parallel arrays of 130 entries, 1-based (code displacements are base-4), stride `0x208`. Field 0 per-object draw/update fn, 1 tick fn, 2 model pointer, 6/7 X/Y, 8/9 previous X/Y. Statically initialised to one repeated default per field; live values written at runtime. | a 130-entry array of object structs on the Falcon side; the DOS layout is structure-of-arrays for 386 addressing and should not be reproduced field-scattered | recovered | high | All 12 displacements appear as `[reg*4 + disp]` in reached code. Field 1's default `00024860` copies 6→8 and 7→9 with `ecx` as index; field 0's default `0002514D` walks field 2 and checks the `"3D"` magic `0x4433`. |
| `000234A4-000234D3` | per-frame object update pass | `mov ecx,0x82`, then for each slot with its active flag set: `mov eax,[ecx*4+00020244] / call eax` - the object's own state handler - then `jmp 00024B17`. Called by the frame driver. This is the `call eax at 000234C8` on record since the first indirect scan. | `src/object.s:object_update_pass` | ported | high | Decoded in full; the dispatch reads object field 1, whose handler set is already enumerated. **Ported:** wired into `frame_driver` at the recovered point; walks all 130 slots descending so a handler that spawns cannot run its own child in the same frame. |
| — | *allocation is bounded at 30, iteration at 130* | The allocator scans `mov ecx,0x1E` (30) for a free slot, but the update pass iterates `mov ecx,0x82` (130). Slots beyond the first 30 are populated some other way - statically or from the mission - so **sizing the Falcon object array by the allocator's bound would silently drop them**. | size by 130 | recovered | high | Both bounds read directly from their loops; the 30-bound also appears in the blast loop and the cockpit dispatcher. |
| `00023297` plus `00023392-000234A4` | object allocator and spawn factories | `00023297` scans the active-flag array `[ecx + 00021921]` downward from `0x1E` for a clear slot, so the **live object set is 30** while the tables are sized 130. `00023297` itself falls into a shared init at `000232EF` that unconditionally installs state `00023F60` and draw `00024FED` - **not `00024860`**, which is only the *image's* static default and is never the state a mission factory's object actually starts in. Nine spawn factories each call the allocator and then override some combination of field 0 (draw), field 1 (state) and a third pointer field at displacement `00021FB0`; `00023462` is the exception, using fixed slot 31 without allocating. The dispatch from a placement's own type byte to one of these nine is `0002231C`, immediately below. | `src/object.s:object_alloc` / `object_spawn_at_parent` / `object_clone_fields` | ported | high | Allocator decoded with all 8 callers; every factory decoded with its literal handler addresses, including the shared-init correction. The `00021FB0` field is confirmed by 30 consecutive copies of its default `00022D33` starting exactly at `00021FB4`. **Not written by the allocator (2026-10-07, measured):** timer `[00021E35]`, steer latch `[00021EB7]`, sprite `[000219A3]`, previous X/Y and altitude, target latch `[00021BAB]`; `000227A6` clears only the active flags, so a mission's objects inherit the previous mission's values (DEMO2 tanks start with DEMO1's leftover timers) - `object_init` and `object_factory_fill` now do the same. **Ported:** allocator scans 30 descending, table sized 130; the clone tail is factored out of `object_spawn_at_parent` so `object_scan_upper` (below) can share it, matching the DOS control flow, which falls from one allocator into the other's tail rather than duplicating it. |
| `0002231C` | mission placement type → spawn factory dispatch | Ten consecutive dwords, indexed by the placement's own type byte (`f0`, already parsed into `mission_obj_type` - see *Mission-driven spawning*): `mov edx,[eax*4+0002231C] / call edx`, from a loop at `00006932-00006947` inside the mission's own resource-load routine. **Corrected 2026-08-21: a first pass at this table was misread; every entry below is a direct re-read of the raw image bytes at `0002231C`, cross-checked twice independently (byte-for-byte agreement).** Entries, in type order: 0→`00023462` (fixed slot 31, state `23800`, draw `24C0A`), 1→`00023392` (state `23F60`, draw `24E05`), 2→`000233DB` (state `23CF0`, model `22D33`), 3→`00023446` (state `23A8C`, draw `2514D`) - **the oil tank**, 4→`00023424` (state `23840`, draw `24FED`), 5→`000233F7` (state `23CF0`, model `22DD0`), 6→`000233A3` (state `23F60`, draw `24E05`, model `22DD0`), 7→`00023297` (bare allocator, state/draw remain `23F60`/`24FED`), 8→`00023413` (state `23F60`, model `22DD0`), 9→`000233BF` (state `23B50`, draw `2514D`). A type ≥ 10 is rejected earlier, at parse time (`0002929B`), by aborting the mission load outright (`int 21h`/`AH=9` then `jmp 000018D3`) - **not** a silent per-placement skip. | `src/object.s:object_spawn_mission`; `jsComanche/dos-runtime.js:spawnMissionObjects` | ported | high | Table base, entry count and index formula decoded and byte-verified at `00006932-00006947`; QEMU trace confirms active mission slots and the type-2/type-3 state/draw entries during attract. |
| `000191B6-0001922E`, `00022B00-00022CA0`, `00022F90-000230AD`, `000241C0-0002430D`, `00024680-0002485E`, `0002519D-0002528B`, `000066E2-000067AE` | weapon fire: trigger dispatch, rocket and Hellfire launchers and states, frame-indexed draw, shared banks | Dispatch calls `[00019D68 + 4*[00019D88]]` after consuming one `[00019DF2]`. Launch point = flight position + high(rail*pub cos/sin) +/- high(ahead*pub sin/cos), rail `[00022880]` negated per launch. Rocket: 8.24 altitude, rate -pitch<<22 or the lock's lead, gravity 0x100000/tick. Hellfire: timer exit at 0x80, steer <=0x14 via `000256C8` whose `esi` is a min/2+max distance, descent (diff-1)/(2*dist/speed)+3. Proximity over slots 30..1, damage 6/5 or 0x50 to `[00021F93]`. DOS slot 130 aliases element 0 of the next array (active[130] = `[000219A3]`). | `src/object.s` `weapon_*`, `object_state_rocket`, `object_state_hellfire`, `object_draw_frame`; `src/view.s` `view_bearing_point` | ported (launch) | high | `tools/check-weapon-launch.py`: 35/35 DEMO1 launches exact against `work/replay_dos/weapon-demo1.json`. Flight states transcribed, not yet traced per tick. Pages 0/3/4/5 and the BULL/CHAF countermeasure chain (`000077A0`, `00019555-0001959E`, `00022A00`/`00022AA0`, `00024480`/`000244A0`) not ported; decoded in `PORTING-PLAN.md`, "Weapon fire, ported". |
| `00023CF0-00023F55` | mobile ground unit state: dispatch types 2 and 5 (factories `000233DB`, `000233F7`) | Destruction byte `[00021B29]` first (`00023F24` tail: one `000227BF` child at stages 0-1, `00024997` at 0x0F). Alive: timer, latch, then health <= 6 or hold -> straight to the aim; otherwise move (`000248E4`), ground target `height*2+0x0B` (byte arithmetic), equal -> steer byte 0; else the three-probe steering through `00023AD0` (`+0x20`, `-0x40`, `+0x60`, default minus) and a `(speed>>21)+1` turn with the move reverted. The aim at `00023E55`: `000256C8` from the frame snapshot `[00019CDC]/[00019CE0]`, range limit `(alt<<20)+0x1E000000` (+0x87 when targetable), `[00019DB8]&0xC` with chaff in the air suppresses, `[00019D92]=1`, one's-complement arc test < 0x10, fire on the `[00021F75]` timer mask through `[00021FB0]`, else the turret `[00021F57]` walks by 3. | `src/object.s:object_state_mobile` | ported | high | `work/replay_dos/objects-demo1.json` (300 DOS passes) against `tools/trace-falcon-objects.py`: active/altitude/health/hold/phase/speed/timer 285/285 in every slot; heading/steer exact for six of eight tanks (the other two diverge from cursor 1837/1997 on 16.16 vs 10.22). Aim gate is wall-clock (`[00019DB8]`), so the turret variant is not reproducible frame by frame. |
| `00022CA1`, `00022D33`, `00022DD0`; `000234E0`, `000236D0`, `0002357B-000236C1` | the three tank shot routines and the two shell states | Each shot routine scans 130 down for a hundred free slots and writes timer 0, aux 8, active, draw `0002514D`, speed `0x04000000`, the shooter's X/Y/heading/altitude, the state and a bank (`ROCK`/`STGR`/`HELL`). `000234E0` sinks one unit a tick; `000236D0` homes on the player's altitude; both end in the proximity tail: altitude within 0x0F and X,Y within 5 map units of the frame viewer is a hit on the player (flare spares it, `[00019E49]` spares it, else shake `[00019DC0]=10`, two damage cells, hull -2..-5, `[00019D94]=1`), the same three tests against `[00022368]` hurt the allied object. | `src/object.s:object_fire_*`, `object_state_shell_rock`, `object_state_shell_stinger`, `shell_proximity` | ported | medium | First stinger shell in DEMO1 is at record 255; checked only by the object snapshots, no tick-by-tick shell trace yet. `[00022368]` is zero until a type 4 placement runs and DOS then reads the aliased element 0 of each array; the port skips the test with no ally (Difference, Unproven). The hit sound `00004E8E` (SND1 id 5, `0002360C`) is made (`SndFX` in `shell_player_hit`, `analysis/functions/sound-falcon.md`). |
| `00019555-0001959E`, `00022A00-00022AF8`, `00024480-000244D5` | the countermeasure chain | At the end of every flight tick: `[00019D93]`/`[00019D94]` -> flare branch, `[00019D92]` -> chaff branch; altitude above 0x0A / 0x14 and none of that kind in the air -> launch. Launch: `[00019D8E]`/`[00019D8D]` -1, in-the-air count `[00019D90]`/`[00019D8F]` +1, timer 0x14/0x1E, state `00024480`/`000244A0`, BULL/CHAF bank, draw `0002519D`, the flight position and altitude. The states drop altitude and timer by one a tick and free the slot at zero; the chaff animates sprite 1..8. `[00019D8A]` and `000074C0` are the console redraw this port does every frame. | `src/object.s:countermeasure_tick`, `object_launch_flare`, `object_launch_chaff`, `object_state_flare`, `object_state_chaff`; `src/flight.s:flight_tick` | ported | high | `[00019D8F]` matches DOS in 285/285 passes; the frame pair's CHAFF readout is 23. `[00019D93]` is `000077A0`'s threat blip, not drawn here, so it stays zero. Counts are zeroed at mission load (`0000685E`). |
| `000254B1-000254F4` (`000254C0-000254C4`) | the scaled sprite blitter's per-column roll shear | `dh += [eax + 0x3CB20]` for each destination column: the backdrop's per-column vertical offset, the same one the terrain spans carry. The terrain silhouette test compares the UNsheared page row. | `src/sprite.s:sprite_draw_scaled` | ported | high | Frame pair record 20: the tank lands inside the designator box on both sides. The target-view surface is unrolled and takes no shear. |
| `00023F60-000241B9` | the allocator's default state (types 1, 6, 7, 8) | Variant `-= 0x10` every tick, latch, timer, the move first; destruction byte -> the falling wreck `0002414C`; hold undoes the move; ground target `height*2+0x2C` against the altitude (undo the move above 0x14, climb 8 above 4, descend 8 below 4); aim: range `((kind^1)<<6+0x96)<<0x16`, fire on the timer mask when `|bearing-heading| < 0xC`, then hold 0x0B above the latched viewer altitude; wider angles jitter by `(rng&7)+4` (near) or `(rng&3)-2` (far) or turn 0x0C. | `src/object.s:object_state_unit`, `object_unit_wreck` | ported | high | `work/replay_dos/objects-pass1.json` (DEMO2) for the first run on the Falcon; DEMO2 has not been traced on the Falcon yet. |
| `00023840-00023A86` | type 4: the player's wingman | Formation point `0xEE800000 * [00019CBC/CB8]` behind the frame viewer (the weapon-page-5 target when one is latched, +9 altitude), heading turns 8 toward it when more than 4 off, flies on only beyond `0x19000000`, ground target `height*2+0x22`; installs itself as `[00022368]`; the same falling wreck. | `src/object.s:object_state_ally`, factory `.ally` | ported | medium | DEMO3 has one; not yet traced on the Falcon. |
| `00024860-00024B16` | the guided missile | Target `[00021D31]` (slot 31 for a tank's Hellfire, the latch for the Stinger); heading toward it by at most 0x19 a tick; the altitude law with the target's altitude as a floor; ground `<= height*2+1` or timer 0x80 ends it; from timer 3 the first of slots 30..1 within altitude 0x14 and five map units takes 8 (6 without `[00019DB8]&0xC0`), else the player test and the hit chain `000235CB`. | `src/object.s:object_state_guided`, `weapon_fire_stinger` | ported | high | Slot 126 in DEMO1 (a player Stinger) is the first one the oracle shows; its heading follows DOS only when the latch does. |
| `00024310-00024470`, `000231B2`, `000230B0` | the timed blast and the page 4/5 launchers | Blast: timer to 0x78, then BOOM wreckage, every slot 30..1 within 0x32 altitude and fifty map units takes 0x64 and gets a child, the player dies; page 4 stands it on the latched target (ground+0x0B); page 5 launches a Hellfire from `[00022368]`. | `src/object.s:object_state_bomb`, `weapon_fire_bomb`, `weapon_fire_wingman` | ported | medium | 238 DEMO1 passes run the blast in DOS. |
| `00024E05-00024F01`, `00024FED-00025148` | the two pair draws | `00024FED`: A then B at `variant>>3` (row <= 0x82) or B at `(variant+4)>>3` then A; `00024E05` adds a mirrored B at `(-variant+4)>>3` lowered 8 source rows via `[000253CC]`. | `src/object.s:object_draw_pair_24fed`, `object_draw_pair_24e05`, `object_draw_model_b` | ported | high | They used to share one body. |
| `00015BB3-00015BE6`, `00001DF1-00001E00`, `00015B60` | the screen shake's display window | CRTC start `page+1 + table[phase] (0,81,164,245)` in 82-byte rows plus pixel pan `phase<<1` (one pixel per two): the window moves (0,0), (-3,+1), (+2,+2), (-1,+3) against rest. | `src/shake.s:shake_present`, `src/main.s` | adapted | medium | Margins the DOS page holds are not rendered (edge replicate); Unproven. |
| `0002B903` (vs `0002B8C5`), `0002A99D`, `0000653D-000066B2`, `0000683B`, `000066FF-00006787` | which SG banks get the night palette variant | `0002B903` copies the bank's palette to `00015F84` and calls `[0002A980]` before the nearest-colour remap; `0002B8C5` does not. Variant callers: the ten mission slots and `CHAF`, `STGR`, `HELL`, `ROCK`. Plain: `BULL`, `BOOM`, `CONS`, `HUDS`. | `src/sprite.s:sprite_palette_from_bank` (`sprite_palette_variant`), `src/resources.s:resource_palette_variant_at` | ported | high | Read from the call opcodes in the undecoded `000066B8-0000683B` range of the flat image. Night tanks are green; the fireball is orange in both. |
| `000237B0-000248A0` | per-object state machine | Field 1 holds the object's *current state* routine, not a fixed handler. The QEMU attract trace reaches the mission states plus the transient handlers `000234E0`, `000236D0`, `000237B0`, `000241C0`, `00024480`, `000244A0`, `00024680`, and `00024860`; the replay callback table at `00019D68` is the producer. `000237B0` is the wreckage state every destroy sequence converges on through `00024997`: it holds the destroyed sprite frame for 20 ticks, then deactivates. `00024480`/`000244A0` are the short-lived BULL/CHAF effects, while `000234E0`/`000236D0`/`000241C0`/`00024680`/`00024860` are the ROCK/HELL/STGR moving child paths. | `jsComanche/dos-runtime.js:objectStateProjectile/objectStateTimedProjectile/objectStateEffectA/objectStateEffectB/objectStateGuided/objectStateExplosion` | ported | high | QEMU `exec,nochain` trace plus active-slot snapshots in `work/qemu_out/attract-trace-report.txt` and `work/qemu_out/object-state-walk.txt`; the common-bank load order at `000066E2-000067A4` resolves BULL=`00019E74`, CHAF=`00019E78`, ROCK=`00019E7C`, HELL=`00019E80`, STGR=`00019E84`, BOOM=`00019E88`. The browser proof exercises a DEMO1 trigger through callback state `00024680` and the HELL bank. |
| `00023A8C-00023AC7` | the oil tank's own state (mission type 3) | Alive path is a bare `ret` - nothing moves, nothing ticks. Destruction path reuses the destroy flag `00021B29` itself as a stage counter once triggered: stage 1 (the trigger) spawns one child from the transient pool (`000227BF`) and plays a sound, advancing to stage 2; stages 2-3 just count; stage 4 hands off to `00024997` - four stages total, not fifteen. | `src/object.s:object_state_idle` | ported | high | All 31 bytes decoded from the regenerated flat listing (`00023A8C-00023AC7`); the alive path's single `ret` leaves nothing to mis-port. Confirmed dynamically in Hatari (memory reads only, `TEXT`-relative addressing - see *Verification ladder*): all 20 of `0.MIS`'s placements spawn at their exact mission coordinates with `OBJ_STATE` pointing at this routine's Falcon address. |
| `00023B50-00023CE4` plus `00023AD0-00023B4B` | dispatch index 9's state, and its shared steering probe | Not the oil tank - see the correction on the dispatch table above; kept ported because it is real, decoded code, currently unwired. Alive path: re-latch home position from current every tick; go inert at health ≤ 2; hold in place while a dword field at `00022028` (new, previously undocumented - `OBJ_HOLD`) is nonzero; otherwise move by speed/heading (the same arithmetic as `00024900`, inlined rather than called - the DOS routine inlines it too, everywhere) and run a heading-steering trial against `00023AD0`: revert to home, re-apply the move at a perturbed heading, resample the ground under the result via the SAME map index `00024915` uses but a **different target formula**, `sample*2+0xb` versus `00024915`'s `sample*2+20`, and compare against the object's own (unchanged) altitude, leaving the DOS `cmp`'s flags live across the call for the caller's `je`/`jne`. Destruction path: 15 stages, not 4. | `src/object.s:object_state_static` and `object_terrain_probe` | ported | high | Every instruction decoded from the regenerated flat listing and cross-checked against the raw image bytes. No decoded mission (`0.MIS`-`3.MIS` so far) places dispatch index 9, so this routine's real per-object defaults - and therefore whether its steering probe is ever live - remain unconfirmed, unlike the oil tank case this was originally (mis-)written for. |
| `000227BF` | transient/effect object pool scan | Descending 100-slot scan, `130` downto `31` - disjoint from the mission-object pool `00023297` scans (`1`-`30`) - then falls straight into `000227D8`, which installs a BOOM wreckage handler pair at the parent's position (state `000237B0`, draw `0002519D`, model `[00019E88]`, sprite 1, the parent's X/Y/altitude) - it does not clone the parent, the same one the low-pool allocator reaches. Used by the oil tank's own destruction stage 1 and, per the object-draw research, by the player's own weapon-fire spawner. | `src/object.s:object_scan_upper`, sharing `object_clone_fields` with `object_spawn_at_parent` | ported | high | Full 8-byte body decoded (`mov edx,ecx / mov ecx,0x64 / mov ebx,0x82` then the scan loop falling into `000227D8`). |
| `00032120-00032B20` | shared Q31 sine table | 640 entries of 4 bytes: 0-511 one revolution at amplitude `0x7FFFFFFF`, and 512-639 a byte-exact copy of 0-127 forming a quarter-wave overhang. Cosine is the same table at `+0x200` (+128 entries = +90°); there is no separate cosine table, and the overhang is what keeps the highest cosine index in bounds. Object physics indexes it `[ebx*8+...]` with an 8-bit heading; the terrain setups index it `[reg*4+...]`. | one shared table or the platform's sin/cos; keep the overhang or mask the index, and preserve Q31 for the fixed-point multiplies | recovered | high | Entry 0 = 0, entry 128 = `0x7FFFFFFF`, entry 384 = `-0x80000000`; entries 512-639 compare equal to 0-127. Highest cosine index 639 lands at `00032B1C`, the last dword before the image end. |
| `00026AB6-00026E90` plus `00025DD8-00025DDE` | options handler and the settings encoding | **Seven boolean options.** Each is one byte in the `COMANCHE.MNU` buffer holding `'{'` or `'}'`, toggled with `xor al,6` because `0x7B ^ 6 = 0x7D`. So every `cmp byte [...],0x7D` in the binary is an "option on?" test and the brace characters are a two-state flag that happens to be printable. Keys `0x14`, `0x15`, `'0'`, `'1'`, `'2'`, `'-'`, `'.'` map to `00025DD8`-`00025DDE` in order. Known effects: `DD8` viewport fill sourced-vs-plain, `DD9` terrain detail level, `DDE` the joystick-to-velocity gate. Shipped: five `'}'` (on), two `'{'` (off). | a settings struct of booleans; **do not carry the `'{'`/`'}'` encoding** - it is a storage trick, not a contract | recovered | high | Handler decoded with every key and target byte; the shipped values read from the asset and the `0x7D` tests already on record in three other subsystems. |
| `0001644B` plus `00016355` and `00015F28` | **the `KRL1`/`KRL0` resource codec** | `res_open_d` at `00015E6E` reads an 8-byte header and dispatches on the tag. `KRL0` is stored: `00015F28` copies it out in 8KB blocks. `KRL1` is compressed: `0001644B` is a byte RLE - a byte below `0xC0` is a literal, `0xC0` or above is a run of `byte & 0x3F` copies of the next byte. Both share the 8KB input buffer at `0002FB14` and the refill at `00016355`. For `SG` banks the palette lives **inside** the decompressed image, at the offset the bank header's `+4` dword gives, introduced by an `0x0C` marker and holding 256 RGB triples with 8-bit components. Ten banks carry a second 768-byte block after it. | Decode at load time into the Falcon sprite bank. The codec is byte-serial and trivially portable; **no runtime need to keep the compressed form** | recovered | high | Verified against the shipped assets, but **not** by the byte count - the decoder is bounded by the header's length field, so that check is circular and was withdrawn. What holds across all 21 `SG` banks: the `0x0C` palette marker lands exactly where the bank header's `+4` pointer says, at a byte the decoder never consults, and every directory record's span equals `width*height`. Note the header length can be smaller than the stream - eight banks leave up to 54,477 bytes undecoded, and their directories are still complete. This replaces the earlier failed attempt to read the sprite directory straight out of the `.RLE` bytes - the file is compressed, so file layout never was memory layout. |
| `00025880-00025DBC` | sprite blitter family and the sprite directory | Eight routines. `00025880` (20 refs) decodes an **8-byte directory record** indexed by `[00022364]` from the resource base `[00019E90]`: `+0` width, `+1` height, `+2` signed X offset, `+3` signed Y offset, `+4` dword relative offset to pixel data. The parameter block is `[00022364]` index, `[00022366]` Y, `[0002587C]` X. Destination pitch is `0x52`. Three of the eight validate the `'SG'` marker (`cmp word [esi],0x4753`) at the resource head before drawing. Per row the blitter writes four `rep movsb` runs of `width/4` bytes to the *same* address, cycling the Sequencer plane mask `0x102/0x202/0x402/0x802` through port `0x3C4`, then does `sub edi,0x52`. **Two pixel layouts ship, and a bank's layout is a property of that bank**: `TANK.RLE` and `HUDS` store pixels **column major**, `data[x*height + y]`, with rows **bottom first**; `COMA.RLE`, `CONS.RLE` and `ZOVE.RLE` store exactly what this blitter consumes - each row as four plane chunks of `ceil((width-p)/4)` bytes, also rows **bottom first** because the destination walks upward. A sprite is `width*height` bytes either way, so only rendering tells them apart. `src/sprite.s`; the **directory record layout carries over unchanged**, the planar `/4` and the plane-mask writes do not. Both bank families are normalized to column-major, top-down Falcon pixels at load: `sprite_bank_deplane` handles the plane-chunked family and `sprite_bank_flip_rows` handles `TANK`/`HUDS`. | recovered | high | Record fields read directly off `[esi + ebx*8 + n]`; all eight extents bounded by the next entry. Span checked in all 21 banks. Column major was settled by rendering `HUDS` sprite 1, a 192x5 compass ribbon whose bottom-first rows become upright only after the load-time reversal; the planar family by `COMA` drawing upside down and diagonally hatched until both the chunking and the row reversal were applied. |
| — | *the 82-byte row pitch, confirmed three ways* | `mov ebp,0x52 / mul ebp` in the sprite blitter, the `add 0x52` step and `0x300C` (=150×82) clamp on `surface_row_offset`, and the font blitter's `add edi,0x52` between pixel pairs. Three unrelated routines agree. | the Falcon surface pitch is its own; what carries over is that **one pitch is shared by terrain, sprites and text** | recovered | high | Independently derived in three separate regions before being connected. |
| `0000D3C0-0000D8F5` | **the frame driver** | The whole frame, in order: latch heading into turn input; copy viewer position to the frame snapshot; **push viewer X, Y and heading**; render terrain via `[00019C94]`; object update pass `000234A4`; **pop them back**; surface blit `00007AA0`; demo/input `00018D20`; variant-gated cockpit sprites. Four callers. | `src/frame.s:frame_driver`; `jsComanche/dos-runtime.js:drawTerrainStage/drawCockpitStage` | ported | high | Decoded in full; QEMU TCG trace reports nonzero `000234A4`, `00024B17`, and object draw handlers in the attract replay. The browser preserves frame-start terrain/object state, then consumes one replay record before cockpit/HUD composition. |
| — | *two consequences of the above* | **(1)** The viewpoint is saved and restored *around* the render call, so the terrain renderer mutates `[00019CD4]`/`[00019CD8]`/`[00019DFC]` and the driver undoes it. A port that passes the viewpoint by value will not reproduce that. **(2)** `[00019CDC]`/`[00019CE0]`, previously recorded as the player position from the blast code, are a per-frame *copy* of the viewer position made here - not an independent player entity - so the flight rollback reads the 10.22 snapshot and the object compositor keeps its own 16.16 copy. | `src/flight.s` (`flt_frame_x/y`), `src/frame.s` (`frame_viewer_x/y`) | recovered | high | Both read directly off the push/pop pairs and the two `mov` copies at `0000D3CF`/`0000D3D9`. |
| `00015B78-00015C14` | frame boundary: vsync, rate counter, page flip | **43 call sites - the most-called routine in the image.** Waits for vertical retrace on `0x3DA` bit 3, increments a frame counter, publishes and restarts it every 10 frames (`[00019DDC]` → `[00019DE4]`), then writes the CRTC display start from `[00019CAC]`. | `src/` VBL handler - this single routine is what "publish the display buffer at VBL" replaces. Keep the page-offset global as the buffer selector; the 10-frame counter is the original's own FPS measure and is optional | recovered | high | Decoded in full; the retrace poll, the counter window and the CRTC write are all in one 156-byte body, and the extent is bounded by the next entry rather than guessed. |
| `00015C14-00015CDC` | display mode set | `mov ax,0x12 / int 0x22` through the extender, then direct Attribute/Sequencer/Graphics/CRTC programming (`0x3C0`, `0x3C4`, `0x3CE`, `0x3D4`). A tweaked mode, not a plain BIOS one. | Falcon VIDEL setup; **the geometry cannot be inferred from a mode number** because the original does not use one | recovered | high | Decoded; the register writes follow the extender call directly. |
| `00016560-00016EC0` | VGA planar presentation layer | Plane control via Sequencer map mask, Graphics Controller write-mode-1 latched copies, chunky-to-planar de-interleave (`0001687D`: map mask `0x102`/`0x202`/`0x402`, source advanced one byte per pass), a per-plane `rep movsd` of `0x139E` dwords = 20,088 bytes from `0003CC20` to `[000014C4] + [00019CA8]`, and a 256×3 DAC upload through `0x3C9`. | **Deleted, not translated.** The Falcon has a chunky framebuffer, so the plane machinery has no counterpart. Carry over only the contracts: chunky staging buffer, VRAM base plus page offset, 20,088 bytes per plane worth of surface, and the 768-byte palette upload. | recovered | high | 20 port writes decoded across the region; the four hot entries have 18, 14, 13 and 5 callers and each was decoded at its head. |
| `00006FEF-00007BCD` | cockpit/HUD element drawing | Called from the frame entry before the terrain setup. The fixed cockpit entries set `[00022364]`/`[00022366]`/`[0002587C]` and call `00025880` or `0002599E`; the flight overlay at `0000D703-0000D8F5` adds HUDS compass, speed, clearance, reticle and sight-line work. Almost every cockpit entry is gated on the console variant `[00019D86]` - `000073D0` alone has 14 callers and opens `cmp byte [00019D86],1` - so the cockpit remains element-by-element and variant-dependent. | `src/hud.s` and `src/main.s`; `CONS.RLE` fixed elements plus the separate `HUDS.RLE` overlay, with RGB565 blitters and the DOS sight-line arithmetic | ported for the attract slice | high | The fixed elements `0x09`/`0x25`/`0x39` and the authored `0000D703-0000D852` overlay are verified in Hatari flight captures. The `0000D88C` COMA tail is phase-gated exactly as DOS and is skipped at attract phase 1, so no large helicopter is drawn over the flight. The later `[19D1C]/[19D24]` branch remains null-gated exactly as DOS until the event graph populates it. |
| `00007AA0` (+ `00007DC3-0000968A` records, `00006FEF` row map) | surface blit and the BSS layout it implies. **Roll's horizontal half (2026-10-07):** the blit copies each row from `run source + [record]` with the record at `0x31B30 + 8k` (k = the surface row 0..181 counted from 32, screen row `y` -> record `c = 183 - y`), written by the same unrolled walker that writes the vertical column offsets: `v = byte(0x30 -/+ dh)`, flat column `v >> 2`; see `render_row_shear` | Sets the VGA Sequencer map mask to `0x03`, page-selects with `cmp byte [00019D87],0` / `mov edx,0x800`, then walks four parallel arrays at `00038B20`/`00038B22` (words), `00032B20` and `0003AB20` (source, one indirect) and `00034B20` (destination, page-selected). Those addresses are past `00032B20`, the end of the content region, so they are **BSS** - absent from the image but part of the runtime surface layout. | the Falcon double-buffer descriptor; the `0x800` page offset and 0x2000 array spacing are the shape to reproduce, the plane mask is not | recovered | medium | Decoded in full; array bases and strides read directly, but their contents are runtime-only and cannot be confirmed statically. |
| `000194E0` (inside the player flight handler) | flight integration core | **Correction: the earlier reading of this row had `[00019DFC]` as the heading. It is the ALTITUDE**, in half-map-byte units - the renderer's AL bias loads `127 - [19DFC]/2`, the ground clamp compares it against `terrain*2`, and the frame driver's first two instructions latch it into `[00019DF6]`, so `rcr` of their sum is one-step **altitude** smoothing. The heading is `[00019D04]`, a full 32-bit angle: `[19D04] += [19D08]` (turn rate), then `>>23` indexes the shared Q31 table (512 steps per turn, twice the fan's grid) and the position integrates by **high-32 multiplies**: `X += hi32(fwd*sin) + hi32(lat*cos)`, `Y -= hi32(fwd*cos) - hi32(lat*sin)`, with `[00019CC8]` forward and `[00019CD0]` lateral velocity in 10.22 per frame. | `src/game.s` - the whole motion model; the 32-bit angle and hi32 products must be kept or demo playback diverges | recovered | high | Decoded in full with every operand traced; the altitude identification is fixed three ways (renderer bias, ground clamp `2h+1` compare at `00019374`, driver latch at `0000D3C5`). |
| `00018F94-0001959E` | the player flight handler | Runs per frame. In order: wounded sink (`[19E39]` negative: altitude-1 per frame above 10, max speed halved to `$800000`); damping of all five rates by `v -= sar(v,cl) OR (v>0)` with `cl` = 5/5/4/4/3 for forward/lateral/turn/roll/pitch, or 3/3/2/2/1 when collective `[19D82] <= $10`; turn `[19D08] += axis1<<14` (keyboard pair `[19DEE]` gives `+/-1<<22`; a damaged cell in `[19E38]` adds a `$600000` spin), clamped `+/-$4000000`; roll `[19CF0] += (axis1+8)>>4` clamp `+/-133`; **lateral `[19CD0] += axis1<<12`, clamped `+/-$800000`**; pitch `[19CF4] += (16-axis2)>>5` clamp `+/-33`; forward `[19CC8] -= axis2<<11` clamped to `[-max/2, max]`, max `[19CCC]` = `$1800000`; fire counters `[19DF2]/[19DF3]` dispatch one shot per frame; rudder keys add `+/-$400000` to the turn rate; a 30-slot proximity scan (`\|dx\|,\|dy\| <= 5` map units, heading-aligned, type != `$237B0`) restores the frame snapshot, reverses lateral, halves-and-reverses forward, pops altitude +4 and damages a subsystem - the collision bounce; terrain follow: `c = alt - (2h+1)`; buried deeper than 2 is a crash, 0..2 pops out, airborne with `c <= 6` and collective `<= 6` zeroes every rate (landing), otherwise altitude steps toward the collective by `(\|c-thr\|>>4)+3` up or `+4` down, saturated. Then the core above. | `src/game.s` - exact demo flight integration; the unported live joystick/control contract exits rather than synthesising axes | recovered | high | Whole span decoded instruction by instruction; constants quoted from the listing. |
| `00018C29`/`00019A2D` plus `DEMO*.SCR` | demo record/playback | `[00019ED0]` selects live (0) / playback (1) / record (-1) at the input dispatcher's tail. The file: dword length (=filesize-4), then viewer X, Y (10.22), the 32-bit flight angle, and the altitude byte - the 13-byte start state - then 8-byte records, one per frame: key into the FIFO head, collective `[19D82]`, two trigger bytes OR'd into the pending-shot counters, and two signed 16-bit axes. No terminator: playback ends at the length and, in attract, jumps to the next pass. All four shipped files divide exactly; the mission XOR key does not apply. | `src/demo.s` loader and per-frame feed; the header converts `>>6` to 16.16 and the altitude lands as-is in the DOS unit `player_altitude` already uses | recovered | high | Loader, reader, recorder and saver all decoded; formats verified byte-level against DEMO0-DEMO3. |
| `00005690-00005AE3` plus `00028C3E` | the attract state machine | An endless cycle: `[19ED5]` counts passes 0-3; even passes show RH66SIDE.DTA with the ZOVE.RLE frame loop for 300 ticks, odd passes FANFARE.RLE over BACK.DTA for 480 ticks then the TPIC.DTA/COMA.RLE panning title for 600; completion sets the attract flag `[19ED4]`, which makes the menu layer skip itself, force campaign 0 mission `[2975A]` = the pass counter, and load `DEMO<N>.SCR` just before the first frame. Demo end or mission end loops to the next pass; any key at any point - FIFO head during screens, sticky latch `[1B75]` during flight - clears the flag into the real menu. Menu option 4 restarts the cycle. | `src/attract.s` state machine; each pass selects the parsed mission resource block before loading its D/C pair and SKY<N>, and the port stops after any-key exit because the real menu/live-control contract is not installed. It re-blits the panned image where the original moves the CRTC start. The screen geometry, the pan, the overlay anchor and the palette rule are set out under *The attract screens* below | recovered | high | Every state transition quoted from the listing; tick counts and asset names read at their load sites; the pan, gate, clamp and wobble arithmetic at `000059ED-00005AD6` ported instruction for instruction. |
| `000196B4` (inside `00019681`) | frame entry into the renderer | Zeroes `[00019D10]`/`[00019D93]`, calls `00006FEF`, `0002B949`, `0001687D`, then pushes `[00019CD4]`, `[00019CD8]` and the heading byte and calls `00007D25` (`terrain_setup_192`). | the Falcon frame loop's call into the terrain setup | recovered | high | Decoded; this is the concrete producer of the viewer position and heading the terrain renderer consumes. |
| `00018DF9` | joystick-to-velocity gate | `cmp byte [00025DDE],0x7D`, then `mov eax,[00019DD0] / shl eax,0xE / add [00019D08],eax`. `00025DDE` is MNU offset 34, shipped as `'{'`, so this path is **off by default** in the retail build. | a Falcon control-mode setting; do not assume the branch is taken | recovered | high | Settings byte traced to the loaded `COMANCHE.MNU` and its shipped value read from the asset. |
| `00018A06-00018C29` | analogue joystick read | `cli`, trigger the four game-port one-shots with `out 0x201`, then poll `in al,0x201` up to 1000 times, masking with the axis-presence byte `[00025DD3]` and incrementing one counter per axis while its bit stays high. Stores four 16-bit counts at `00019DD4`. **The axis value is the iteration count**, so it is a function of host CPU speed. | replace outright with a Falcon joypad/joystick read; only the four-axis result contract at `00019DD4` and the presence mask carry over, not the timing loop | recovered | high | Routine decoded in full; the four `rcr`/`adc` pairs map to the four stored words, and the consumers at `00019911`-`00019967` read them back. |
| `000189C2-00018A06` | input/event poll | Flag-driven poll over `[00001AA8]`, `[00001A89]`, `[00026 5ED]`, `[00001A8E]`, `[00001A80]`, dispatching to handlers. 18 callers - the most-called routine in its region. | a Falcon event poll called from the same points in the game loop | recovered | medium | Entry and caller count established; individual flag meanings not yet resolved. |
| `00001969` and `000019E9` | scancode → ASCII tables | Two 128-byte tables indexed directly by PC scancode, shifted and unshifted. `000280C1` reads unshifted, tests for zero (no character), then re-reads shifted when the shift state at `[00001A9A]` masked by `[00001AA6]` is set. | a Falcon IKBD scancode table; the two-table shifted/unshifted split carries over, the PC scancode numbering does not | recovered | high | Bases confirmed by position: scancode `0x02`→`1`/`!`, `0x10`→`q`/`Q`, `0x1E`→`a`/`A`, `0x2C`→`z`/`Z`, `0x39`→space in both. |
| `00027034-00027276` plus `00029570-00029EF0` | menu/HUD text markup renderer and its data | A byte-code interpreter over NUL-terminated strings. `0xFC` skip, `0xFD`/`0xFF` layout codes, `0xFE` records a hotspot (pen position and `eax` into 8-byte records at `00026550`, count at `00026590`), `0x7C` `'\|'` plus a letter selects a colour, `0x01`-`0x0A` are direct colour codes, anything else blits a glyph. Colours resolve to the `colour_constants` block: default/`w` white, `r` red, `g` green, `b` blue, `p` magenta, `y` amber, `o` orange. The data is 52 strings for the pilot-select and main-operations screens. | `src/menu.s:menu_text_draw`, the byte-code ported whole - including `$FD`'s six-pixel advance, which is one Mode X byte column plus two single-pixel steps (`00027185` carries an `inc ebp` the listing hides in a not-taken path). Hotspots are kept as X and Y rather than as the DOS pen offset with the page base and pan subtracted. Two platform deviations, both at the head of `src/menu.s`: the colours are the six-bit triples `0002AA85`-`0002ABCC` names, converted to RGB565 rather than quantised to the installed palette, and the shadow is black rather than palette index 0, which in every palette this port loads is the reserved sentinel | ported | high | Interpreter decoded in full including every colour branch; each target is a `colour_constants` entry, closing palette → resolved index → markup code → blitter `bh`. |
| `00027276-00027D92` | bitmap font block | Self-describing proportional font. `+0x000` `"KF4b"` signature, height `0x0A` (10 rows); `+0x008` 128-byte width table (104 nonzero, widths 2-10); `+0x088` 128-word offset table, **offsets relative to the block base `00027276`**; `+0x188` glyph data at `width*4` bytes each - 4 bytes per column, one 32-bit column mask, 10 rows used. | Generated into the build by `tools/prepare-original-test.py:emit_menu_font`, the way the Q31 sine table already is - 2,844 bytes of the original executable are not committed. Without `re/unpacked` the build fails before linking, so the port has no menu text rather than invented menu text. The former `tools/gen_menu_font.py` 5x7 font was removed because it was not derived from the game | ported | high | Offset delta equals `width*4` for every consecutive used character (2→8 … 10→40). First glyph offset 392 lands exactly on `000273FE`, the end of the offset table. Both consumers decoded. |
| `000268DB` and `00027196` | font string-width and glyph blit | Width: `lodsb` over a NUL- or `0xFF`-terminated string summing `[eax+0002727E]`. Blit: width lookup, `movzx esi,word [esi*2+000272FE]`, `add esi,00027276` to absolutise, then VGA Sequencer map-mask write (`mov al,2 / mov dx,0x3C4 / out dx,ax`) and an unrolled column walk advancing the destination by `0x52` between pixel pairs. | one Falcon text routine over a chunky framebuffer; the plane-mask write and the `0x52` advance are VGA-planar artefacts and do not carry over | recovered | medium | Both decoded from their readers of the width and offset tables; the blitter's exact pixel-pair addressing was read but not fully interpreted. |
| `0002B820-0002B89D` plus `0002ABD0`, `0002AFD0`, `0002B3D0`, `0002B7D0` | weighted nearest-colour palette search | Argmin over a 256-entry 3-byte RGB palette at `0002A680`. Each component difference indexes its own 256-entry table of `c*min(k,256-k)^2`, `c` = `30^2`/`55^2`/`15^2` - a perceptual luma weighting R 0.30 / G 0.55 / B 0.15 with the square folded in; `min(k,256-k)` takes the absolute value of the wrapped byte difference. Target RGB and search bounds are globals at `0002B810`-`0002B81A`; the best index returns in `bl`. | Falcon: the same weighted match against the VIDEL palette, or a precomputed inverse-lookup table; the weights and the wrap-folding are the parts worth carrying over | recovered | high | Routine decoded in full; the three table constants verified as exact arithmetic series across all 256 entries; 12 callers located. |
| `0002A374-0002A37D` | resolved colour constants | Ten palette indices resolved at startup by the matcher from fixed 6-bit VGA triples: white, three greys, blue, red, green, magenta, orange, amber. | resolve once against the Falcon palette at load, same as the original | recovered | high | All ten call sites decoded with their literal RGB targets and destination globals. `0002A37E`, the viewport fill's colour byte, is the next byte after the block. |
| `0002D7F0-0002DBF0` plus `000055ED` | scanline row table and its relocation | 256 dwords of row byte-offsets for a 192-byte-pitch surface: entries 0-198 are `(255-k)*192`, 199-255 are zero. `000055ED` patches all 256 in place by adding the destination base from `[00019E70]`, the same base `viewport_fill_*` writes to, turning offsets into absolute row addresses. | rebuild from the Falcon surface's own base and pitch - the 192 is a DOS-side constant and the table must not be copied | recovered | high | Relocation loop decoded in full (`mov ecx,0x100` / `add [esi],ebx` / `loop`); static entries verified as the exact arithmetic series. |
| `000218A0-00021FBC` | object table, byte fields | 14 parallel arrays of 130 entries, stride `0x82`, same 1-based convention, contiguous with the dword fields. | folded into the same Falcon object struct | recovered | medium | 13 of the 14 displacements appear in reached code as `[reg + disp]`; `00021921` is byte field 1, already on record as the flag array tested by the cockpit dispatcher. |
| `00027DB4-00027FBF` plus the text block at `00029B2C` | **the list-menu driver**, and the screens it selects from | The widget the original's whole out-of-flight flow is built on: main operations, campaign select, mission select and the briefing's accept/reject pair are this one routine pointed at different `0xFF`-separated sections of the text block. `[00027DB0]` is the caller's section base, `[00027DAC]` the screen id, `[00027DAD]` a sub-mode flag. `00027DCD` redraws, then `00027E9F` calls the retrace wait at `00015B78` and `00027EA4` reads the key FIFO, looping until a key ends it. Geometry: the `0002628E` call four instructions in is `bl=0x0E, bh=0x34, dl=0x1E, dh=0xA0` = 208x160 at (56,30), and `00027DE6` takes the text one 4-pixel unit further in; `00027E7B` advances `0x3D8` per line, which is twelve 82-byte rows of the 328-wide Mode X page; `00027E13` seeds a row counter at `0xFA` and `00027E73` increments it per drawn line, so what is left at the `0xFF` is the item count the selection is clamped against. The highlight at `00027DF7` decomposes against that pitch as `0x99C` = 30 scanlines = the box top `dl`, plus `0xB88` = 3 rows: selection N marks text line 3+N. `[00027DAD]` adds the two further rows of `0x7B0` and takes the seed to `0xF8`. | `src/screen.s`. The blocking loop becomes a per-frame state machine - the same accommodation `src/attract.s` already makes, and for the same reason: `src/main.s` owns one update and one publish per VBL, and a routine that spins inside a frame stops the pacing the demo and the flight both depend on. The two Mode X plane selects it draws through (`00026FD9`, `00016B50`) and their 82-bytes-per-plane row math do not survive onto a linear 16-bit surface; what does is the pair `src/menu.s` already ports, the bevelled box `0002628E` and the markup interpreter `00027034` | ported | high | Section walk, box registers, row pitch and count seed decoded. The highlight geometry was settled 2026-08-19 after being misread against the text BASELINE rather than the cell top - text sits two scanlines into its own cell - and the same `[00027DAD]` flag settles the item count at the 7 the main menu actually has. Hatari: the attract exit lands on the main menu with the selected pilot in the header. |
| `00028CE8-00028DFF` | main operations screen and its dispatcher | Loads `RAH66.DTA` at `00028CE8`, sets the pilot sub-mode `[00027DAD]` at `00028D71` and clears it at `00028D7D`, fills the header's pilot name at `00028D3C-00028D5C`, then dispatches the driver's returned index over seven cases. `al=0` Begin Mission loads `MISSION.DTA` and falls into campaign select at `00028F05` - it does **not** start flying. `00028D9F` calls `00028216` for Choose Another Pilot, `00028DB5` is Credits, and `00028ECA` zeroes the pass counter before re-entering the attract at `00005690`, which increments it again - so Demo always lands on pass 1, never on the pass the cycle had reached. | `src/screen.s:screen_enter` and its `.main_ops` dispatch | ported | high | All seven cases decoded. Four are ported; Your Stats and RAH-66 Overview are screens this port has not recovered, and selecting one does nothing rather than pretending. Hatari: each ported case reaches its screen and returns. |
| `00028DB5-00028DF9` | the credits screen | The first menu screen that is not a list: loads `credit1.dta` from the inline name at `00028DBF`, **empties the key buffer at `00028DE4`**, waits at `00028DEB` for any key, and returns to the menu at `00028DF9`. No box, no lines, no selection - the image IS the screen. | `src/screen.s`, screen id 4: a mode that draws the backdrop and stops | ported | high | The buffer flush is not tidiness - the keypress that opened the screen is still in the FIFO and would close it again on the very next frame. This port hit that failure from the other direction on the Demo option, where a held key re-exited the attract the instant it restarted, so the original's guard is reproduced rather than rediscovered. Hatari: CREDIT1.DTA renders in full and any key returns to the menu. |
| `00028F05-00028F4B` and `0002A1AD-0002A299`, plus `00029038` | campaign select, mission select, and the mission-list fill | `00028F11` and `00028F4B` hand the driver text-block sections **2 and 4**, not id+1: section 3 is the briefing's accept/reject pair, which no numbered screen uses, so deriving the mapping as id+1 works for the two adjacent screens and then quietly points mission select at the briefing. `00028F16` opens campaign select on `[00029702 + [00029701]]` - the campaign that pilot is already flying - rather than on the first, and `00028F2F` stores the choice back into the roster slot. `00028F3A` resolves the per-pilot mission list before `00028F3F` draws it, and `0002A1AD` writes the titles **into the text block itself**: the rows at `00029D95` ship as `0xFC` fill, `0002A1FE` skips the catalog title's closing brace, `0002A212` plants an end marker per row so a row with no title terminates the screen, `0002A273` prefixes `"\|g  "`, `0002A27E` strides `0x20`, `0002A28A` pads and terminates, and `0002A1F7` caps at ten. `00029038` then patches the selected digit into `"N.MIS"` and loads it, and `00005B33` loads that mission's resources before the frame loop runs. | `src/screen.s:screen_fill_missions` and `.mission_chosen`, which loads the mission, selects its terrain family and sky, spawns its objects and enters flight | ported | high | Sections, seed, stride, colour prefix, fill byte and the ten cap decoded and reproduced. Not ported: `00028F3A`'s per-campaign file switch - this port fills the rows from the one stream `mission_init` already decoded, so every campaign shows the same ten titles. Both halves of the load matter: without the resource selection behind the record the player flies whatever map the attract left staged, which is how this first came out on the attract's night terrain regardless of the choice. |
| `00005604` and `00028216-00028240`, plus `00029570-00029702` | the pilot roster, `COMANCHE.NAM` | `00005604` reads the file over the image's own default copy at `00029582` through the inline-filename reader `00015DD0`, which is why the two are byte-compatible. The 43-byte record layout is in *Resource formats loaded at startup* above; what the screen layer adds is where its fields are read - the name at +9, the campaign digit at +5, and the scalars behind the records, of which `[00029701]` is the selected pilot and the eight bytes at `[00029702]` are the campaign each pilot is on. `00028216` points the driver at `00029570`, eighteen bytes ahead of the records, so the header is the screen's first three lines and not a separate string; it sets no screen id and loads no background, so Escape does not back out of it - exactly as on the main menu - and it keeps that screen's `RAH66.DTA`. `00028240` stores the returned index as the selected pilot, and `00028D3C-00028D5C` copies that pilot's name, `0x16` bytes, into `00029B44`, the first `0xFC` of the main menu header's fill. | `src/screen.s:screen_roster_load` and the pilot screen, which carries an internal id 3 the original does not have. The image's default roster is not committed, so a missing file leaves the buffer zeroed and the name fill writes nothing; a short read is refused rather than indexed into. Header and records are declared as one adjacent region, because the driver walks out of the one and into the other | ported | high | Record stride, both field offsets and both scalars decoded; the `0x2B` stride, `0x16` length and destination are the original's. Not ported: `00027D92`, the write back to `COMANCHE.NAM`, so a pilot or campaign choice survives the session and not the program. Tab, Del and the roster's own sub-mode are also unported - the DEL prompt row is excluded from the pilot store rather than implemented. |
| `0002A9E6`, `0002AA18` and `0002573F` | VGA DAC index, 768-byte palette upload, Mode X screen-base bookkeeping | The DAC write-index and data pair, the full 256x3 palette upload behind it, and the page-base arithmetic the Mode X screens keep. | none - `N/A - platform replacement`. RGB565 and a linear surface replace all three | recovered | high | Recorded because they look like work and are not: all three sit in the middle of the credits and menu chain and were decoded before it was clear that no port was owed. |

## Object draw stage

`00024B17` is one routine doing three things, and reading it settled what two
table fields are for.

It first rotates every active object's position relative to the **frame viewer
snapshot** - `[00019CD4]`/`[00019CE0]`, not the live player position - writing
the sideways component into field 4 and the forward one into field 5. That is
what the snapshot in `frame_driver` exists for; using the live position would
make objects lead or lag the terrain by a frame.

It then selection-sorts an index list and walks it from 130 down to 1, calling
each object's field-0 draw handler. Objects are painted **far to near**, which
is the only depth resolution sprites get.

The index list is field **-2**, which the table map had recorded as "unknown
(zero)". It holds zero in the image because it is written only at runtime.
`00024BDA` reads it as `mov ecx,[ebp*4 + 0001FC2C]` and uses the result as an
object index, and `00024BB3`-`00024BC1` exchanges its entries - so it is a
draw-order list, not per-object data. Field 5 is its sort key, and is also the
cull in the shared draw prologue `00024C45` and the scale input for `0002519D`.

Field 0 is called from exactly one place, `00024BFC`. The other twenty sites
naming that displacement are all spawn-time writes, which is why searching for
a call to it finds nothing.

| DOS | Falcon |
|---|---|
| view transform `00024B17`-`00024B7F` | `object_view_transform` |
| depth sort `00024B81`-`00024BC9` | `object_depth_sort` |
| draw walk `00024BCB`-`00024C09` | `object_draw_pass` |
| sprite handler `0002519D` | `object_draw_sprite` plus `sprite_draw_scaled`, with a different scale curve - see below |

The CPU transform now uses the DOS Q31 pair built by `00007D25`, indexed from
the full `flt_angle`. The matrix, read off `00024B45`-`00024B67` rather than
paraphrased: **forward field 5 `[00020A64]` = `hi32(sin*dx/2) -
hi32(cos*dy/2)`** - the same `(sin, -cos)` forward axis the terrain marcher
walks - and **lateral field 4 `[0002085C]` = `hi32(cos*dx/2) +
hi32(sin*dy/2)`**, with the deltas halved 10.22 values, so both land at
world`*2^20`. An earlier revision of this paragraph stated the matrix the
other way round and the port stored it that way, which turned the object
field a quarter turn against the terrain. The Falcon coordinates remain
16.16, so the 68030 uses the corresponding full-product Q31 multiply at that
platform scale.

The ring search that follows (`00024CC0`-`00024D16`) shifts that forward
depth left by 3 - world`*2^23`, the exact unit of `.DTL` table 4's raw
running total, since the marcher's per-ring step is `high32(A*sin)` = A/2
map units - and searches the raw words UNSIGNED, twice with one cursor:
first with the key pulled `0x1800000` (three map units) nearer when that
does not underflow (`00024CCA jae`), selecting the ring whose archived
silhouette clips the sprite, then continuing from that entry with the
unbiased key and the remaining count for the elevation/scale ring. A key
past ring 249 runs the DOS scan off the table into code bytes and lands on
the reject at `00024E03`; the port rejects directly. `src/object.s` now
reproduces this search verbatim over the verbatim `ring_z_table`.
Placement then indexes the selected ring's 256-byte projection page with the
same byte-wide altitude expression at `00024D5E`-`00024D73`. The Falcon converts
that DOS bottom-up page row to screen Y with the recovered 213-row anchor only
at the RGB565 surface boundary. `src/object.s:object_find_page` is shared by
the pair-order test and sprite compositor, so neither path uses an analytic
row approximation.

## Object rotation, and a claim that was wrong

An earlier note in this file and in the annotations said `0002519D` selected
the rotation frame with `mov bl,[00019DFC] / not bl / add bl,[ecx+00021A25] /
rcr bl,1`. That was wrong. The value goes to `[00022366]`, and `000253CD` adds
it to a row accumulator at `00025458` - it is the DOS **bottom-up surface Y**.
`0002519D`
selects no frame at all: it passes the object's byte field 1 straight through,
and that field is an animation counter, incremented and wrapped against 20, 8
and 7 by the state handlers at `000237B0`, `000244B6` and `00024659`.

The rotation is in the shared prologue `00024C45`, whose tail reads:

```
inc ebx / shr ebx,1        bearing viewer->object, an atan2 by octant
add al,[ecx+0002189F]      plus the object's own heading
add al,4 / shr al,3        rounded into 32 steps -> [0002237D]
```

`0002514D` then indexes a 32-byte table at `model+2` with that step, adds an
elevation lookup from `model+0x22`, and the sum is the sprite index. Both
tables live inside the `'3D'` model record, so they are asset data. The Falcon
loader finds the record at the SG bank's palette offset plus 770, validates the
`3D` marker, and `object_aspect` now ports the shared prologue with the exact
octant table at `00022385` and ratio-correction bytes at `000223A5`.

Three bugs were found getting this working, and one non-bug that cost more than
all of them.

The mirror bit was tested *after* the bounds check, so every mirrored frame read
as index 32768 and was rejected without drawing. A test spawn used `MULU` on a
signed offset. And `object_aspect` took its row from `d2`, which holds the
depth, so every object measured the same elevation and landed in one band.

The scaffolding those bugs were found with - a spawn placing eight tanks in
view, and per-slot instrumentation - has since been removed. Mission records
now feed the recovered factory dispatch: authored f2/f3 resource slots select
model banks and palettes, the ten dispatch entries choose the recovered draw
families, and the fixed type-0 path owns slot 31. The event-only target/state
graph is still kept dormant where its handler body has not been ported; the
attract draw path does not turn every mission object into a TANK.

The non-bug: three objects appeared not to draw, and reading the source could
not explain it because the explanation was not in the source. **The helicopter
flies.** By the VBL a capture is taken it has closed some sixty units on objects
placed relative to its *start* position, so the depth-ring search and its
nearer-silhouette key decide whether the object is still in the authored draw
range. Every prediction of where an object should appear had assumed a
stationary camera.

What settled it was recording the projected row per object slot and capturing
the same scene at two VBLs: every row had moved *down*, by 99 for the nearest
and 22 for the farthest, in proportion to how close each was. That
instrumentation is kept behind `OBJ_DEBUG` in `src/inc/comanche.s`, because a
capture shows what is on screen and says nothing about what a routine computed
for something that is not. **Two captures at different times are worth more than
either alone whenever the camera is moving.**

The byte-wide arithmetic is deliberate on both sides. The adds and the shift
are byte operations in the original, so the sum wraps at 256 and the result is
0..31 by construction. Doing it in words needs an explicit modulo and gets the
wrap at the half-turn boundary wrong.

## Word and long, the recurring 68k fault

Three separate bugs on this path had the same shape: a value produced as a word
and consumed as a long.

- `sprite_draw_scaled` took the sprite index with `move.l d0,d4 / lsl.l #3,d4`
  while checking it with `cmp.w`. `object_aspect` returned it with `move.w
  d1,d0`, leaving the high half stale, so the bounds check passed and the
  record address was wild - a bus error inside the inner pixel loop, nowhere
  near the actual mistake.
- The clip paths built skipped-pixel counts with `move.w`/`neg.w` and fed them
  to `MULS.L`.
- `DIVU.W` could not hold the source step and silently left it unwritten.

A fourth, found 2026-08-22, is the same fault in the declaration rather than
in the code. `mission_start_y` was `ds.w 1` while every access to it is a long:
`mission_parse` writes it with `move.l`, `mission_init` clears it with
`clr.l`, and `game.s` reads it with `move.l` into `player_y`. It was two bytes
short, so the long write ran on into `mission_start_heading` and the long read
brought it back - the helicopter's start Y carried the start heading in its
fractional half, 0 to 255 of a 16.16 unit. It survived only by an accident of
ordering: `mission_parse` writes the heading immediately after the Y that had
just clobbered it, so the heading was always correct and only the coordinate
was quietly wrong, by about four thousandths of a map unit.

None of the four is visible in the source without asking, for each value,
which half of the register the next instruction reads - and the fourth is not
visible in the code at all, only in the BSS declaration two hundred lines
away. `ds.w` next to a `move.l` is the same bug as `move.w` next to a
`MULS.L`.

The crash reporting in `src/start.s` exists because of this. It floods the
screen in a colour chosen by vector - red bus, green address, blue illegal -
and paints the faulting PC and all fifteen registers as binary pixel rows.
`a1 = 1EF46413` is what identified the last one; reading it out of BSS instead
would have needed a symbol address that moves with every build.

## Mission-driven spawning, and the axis convention

`00029240` parses the placement records. Each is eleven fields and lands in
parallel arrays:

| field | destination | meaning |
|---|---|---|
| f0 | `[ebx+0002222A]` | type, rejected if 10 or more |
| f1..f3 | `[00022248]`, `[00022284]`, `[000222A2]` | unread |
| f4 | `[ebx*4+000220A4]`, `shl eax,0x16` | **X** |
| f5 | `[ebx*4+0002211C]`, `shl eax,0x16` | **Y** |
| f6 | `[0002220C]` | heading |
| f7..f10 | `[000222C0]`, `[000222DE]`, `[000222FC]`, `[ebx*4+00022194]` | unread |

`shl eax,0x16` puts the value's integer part straight into DOS's 10.22
position format, so a mission coordinate is **whole map units**. The port's
parser had been shifting by 14, making every mission coordinate a quarter of
what the file says; it now shifts by 16 for its own 16.16.

**The two renderers do not share a Y axis.** The DOS mover at `00024900` does
`X += speed * [ebx*8+00032120]` and `Y -= speed * [ebx*8+00032320]`, and those
tables begin 0.000 and 1.000, so they are sine and cosine and DOS heading 0
faces **-Y**. This port's terrain fan is `F = (sin h, cos h)`, so its heading 0
faces **+Y**. Positions need no conversion - both index the same height map the
same way - but every direction does, and `sin(128-h) = sin h` with
`cos(128-h) = -cos h` makes the conversion `128 - h`.

That is not cosmetic. With the heading taken literally the helicopter starts
its first mission flying away from every objective in it.

A mission file is a catalog: 0.MIS holds 139 placement lines across several
blocks, of which the first mission's are the 20 before the next `<`. Each
record has three delimiter events - resource-list open, resource-list close,
then the boundary before the next title - so selecting mission 1 or later must
cross all three events for every preceding record before treating the next
delimiter as the selected resource-list open. The parser reads exactly the
selected block's placement lines.

Three bugs found here, all older than this change. The later-record selector
had crossed only the first two delimiters, so mission 1 started scanning at its
title and left the map and sky families at `-1`; attract then took its normal
asset-failure path and returned through `Pterm0`. The selector now crosses the
three recovered delimiter events per prior record. `mission_read_file` pushed
`Fread`'s arguments as (count, buf) instead of (buf, count), so GEMDOS read the
file to whatever address the count happened to be - 4096, in the middle of low
memory - and still returned the byte count. The caller saw a successful read
into an untouched buffer, the decode XORed zeros into the key pattern, the
parse failed, and the mission had silently never loaded. And the record parser
parked its array index in `d2`, which `mission_read_number` uses as its
multiplier, so every index was garbage after the first field.

## The palette, and what the ramp is actually for

The port takes a resource palette and puts it on screen unaltered. That is what
the original does too, which took decoding the ramp to be sure of.

`0002B89D` builds `palette_rgb` from the raw palette and does **not** treat the
components alike: R and G go through the ramp at `0002B7D0`, B is only
`shl al,1`. But `palette_rgb` has exactly one reader - the nearest-colour search
at `0002B854` - and both DAC uploads bypass it, `0002A9E7` sending raw bytes
from `00015F84` and `0002AA00` from the copy at `0002A380`.

So the ramp defines the space colours are **matched** in, not the space they are
**displayed** in. It matters only for reproducing which index the game would
*choose* for a given colour: it maps a 6-bit component onto 0..127 on a curve -
`0,1,2,4,5,7,8,10,12 ... 124,126,127`, compressive low and near-linear above -
and the search minimises a squared error weighted 30/55/15 across R/G/B, which
is luminance weighting with the squaring folded into three 256-entry tables.

**Which resource supplies the display palette is settled, by measurement.** A
DAC dump taken from the running game matches `P12.DTA` on 193 of 256 entries;
the 63 that differ are entries 1-63 in one contiguous run, which is the BIOS
text-mode reset the dump suffered on the way out. The next best candidate
matches 35 of 768 bytes. The capture is kept at `re/captures/dac-mission0.bin`.

That confirms the static trace: `000064C9` saves P12's palette into `0002A380`
immediately after `p2.dta` loads, and the flight loop at `000069CC` - frame
driver, flip - ends at `000069D6` uploading the DAC from that buffer every
frame. C1.DTA's own palette is never uploaded.

**The index transform is at load time, and finding it settles everything.**

`0002B949`, the tail of `rle_payload_setup`, runs after every image load - for
the colour map it is reached by `call 0002B949` at `00006509`, immediately after
the `c2.dta` load. It takes the file's OWN palette, just placed at `00015F84`,
matches each of entries 1..254 against `palette_rgb` through the nearest-colour
search, and builds a 256-byte translate table with 0 and 255 pinned to
themselves. Then it rewrites the entire decoded image in place through that
table, two bytes a pass. “Entire” is the full 1 MiB decoded map, not a 16-bit
loop window; leaving the later quarters in the source index space produces
isolated palette-colour trash in otherwise correct terrain.

So a resource's palette describes what its indices **mean**, and the indices are
converted at load into the **active** palette's space. Everything reconciles:

- C1.DTA's own palette is what makes C1's map read as terrain - it is the
  authored meaning of those indices;
- the DAC holds P12's palette, because that is the active one;
- the framebuffer holds P12 indices, because the map was remapped at load;
- the span emitter writes map bytes untranslated, because the translation
  already happened.

The garish render that made me doubt the trace was C1's *un-remapped* indices
through P12's palette - a combination that never exists in the running game.

**This also settles what the port should do.** DOS is forced to quantise C1's
colours into P12's 256 entries because it has one DAC. The Falcon still keeps
that indexed relationship: it loads the mission's authored P/NP palette,
translates the decoded Cn map into that active palette's indices, and only then
expands the active entries to RGB565. The true-colour surface changes the final
storage format, not the picture's colour choice.

The first cold-boot attract flight is the recovered mission-1 replay, not a
forced DEMO0/day-file substitution: `0.MIS` selects `DUI Enforcement`, family
C4, kind 1, and `NP44.DTA`. The kind-1 transform at `0002A99D` runs before
`0002B949`; the Falcon's `resource_night_map` is the precomputed exact output
of that DOS transform plus the `0002B820-0002B9BA` nearest-colour pass for the
authored C4/NP44 pair. This is why the first port frame is green like the DOS
night-vision presentation while retaining the original replay and map.

**In the draw path there is no transform.** The renderer reads the colour map with
`mov al,[ebx + base]` at `0000AF52` and about thirty sibling sites - the base is
patched into each of them at `00005BBF`, which is why the map pointer has only
three references - then dispatches by span length into the unrolled writer at
`00006BF0`, which is `mov [ecx],al / inc ch` repeated. The byte reaches the
framebuffer untranslated.

So the terrain's colours are simply C1's indices through whatever the DAC holds,
and the contradiction is in the measurement rather than the game. **82.6% of the
terrain uses indices 0-63** - exactly the range the BIOS text-mode reset
destroyed in a dump taken after the game exits. That capture measured only the
17% of the palette the terrain barely uses. It identifies P12 correctly and says
nothing about how the ground looks.

Settling it needs the TSR capture, which samples while the video mode is still
13h and so preserves entries 0-63. Until then the port keeps C1's palette,
because that is the one that demonstrably renders C1's map as terrain.

## Object scaling, and why the port does not reproduce it

`0002519D` scales a sprite by searching a per-column ramp for the object's
distance, then dividing `0x08000000` by that band's entry and clamping to
`0x7F`; `add al,0x80 / not al` turns it into a byte that is zero when nearest.

That ramp is **table 4 of the `.DTL` file**, and the divisor is table 0 at the
same index. Both are installed asset data, not code: the shipped files carry
table 4 as table 0 times 100, running from 21,838 to 41,323,167 across 250
columns in `HIGH.DTL`, and `LOW`/`MEDIUM` carry different curves over 100 and
180 columns. So the original's object scaling **changes with the detail level**,
and reproducing it means loading a `.DTL` and following the byte into
`000253CD`, which is not decoded.

The port uses the recovered HIGH.DTL relation directly: the original's table-0
divisor is `z/100`, so the scale index is `min(3200/z,127)` and the selected
ramp length is `index+1`. The Falcon 8.8 scale passed to the blitter is that
length times four; there is no independent object-size constant.

One thing that is *not* a free choice: every frame of a sprite set shares one
scale. The frames are one object seen from different angles, so sizing each to
a fixed world span would shrink a broadside view exactly when it should be at
its widest.

Two implementation notes that cost a capture each. The source step is
`source/destination` in 16.16, which exceeds 16 bits as soon as a sprite
shrinks - the normal case - so it needs `DIVU.L`; with `DIVU.W` it overflows,
leaves the step unwritten and nothing is drawn at all. And the clip paths build
their skipped-pixel counts with `move.w`/`neg.w` but feed them to `MULS.L`,
which reads all 32 bits, so those counts need an explicit `EXT.L`.

## Reading DOS data on the 68030

Every multi-byte field in an installed resource is little-endian, because the
files are x86 structures written verbatim. Single bytes - widths, heights, the
signed sprite offsets - need nothing. Count words and dword offsets have to be
assembled a byte at a time.

This is worth stating separately because it does not fail gracefully and it
does not look like an endianness bug when it happens. `TANK.RLE` declares a
decompressed size of `0x0001084E`; read as a 68k long that is `0x4E080100`,
about 1.3 GB, so the loader rejected the bank on its size check before
decoding anything. The visible symptom was simply that no sprite appeared.

The one thing that reads correctly either way is an ASCII tag. `'KRL1'` and
`'SG'` are byte-ordered, so comparing them as a big-endian long or word is
right - which is exactly what makes the mistake easy to miss, since the
signature check passes and only the numbers are wrong.

Diagnosing this from a black screen is slow. What made it quick was a four
pixel status block written at a fixed place on the surface, coloured by the
loader's return code: green loaded, red file missing, yellow bank rejected.
The capture then says which half of the path to look at. `sprite_overlay` in
`src/sprite.s` keeps it.

## The campaign list is built from the files, and that is what a roster byte means

The campaign screen's rows ship as `0xFC` fill and the mission screen's rows
ship the same way. Neither is decoration waiting to be replaced: both are
written at runtime, and until `0002A104` was ported this port had one campaign
because it had one hard-coded stream.

`0002A104` runs at `0000561F`, before `COMANCHE.NAM` and before anything else
reads a mission. It probes `0.MIS` through `9.MIS` with `00015CDC`, and for
each file that exists it reads it, decodes it, and takes the first `{...}` in
the stream - the file's own catalog title, which sits ahead of every mission
record. `0.MIS` is `Comanche Training` and `1.MIS` is `Operation Maximum
Overkill`. The title goes over the row behind two spaces and the row cursor
advances; a file that is not installed advances nothing, so the list is dense.

The important product is the other one. `0002A18F` writes the file's digit into
a ten-byte table at `00029D47`, indexed by the row it just wrote. **The
campaign a pilot carries in the roster at `[00029702+pilot]` is a position in
that list, not a filename**, and the two only coincide when every numbered file
from zero upward is installed. `0002A1AD` and `00029038` both open with the
same four instructions to resolve one into the other, and `0002A1BB` and
`0002904D` both override the result with zero while the attract flag
`[00019ED4]` is set - which is why the demo passes always fly the first
catalog entry's missions and never the campaign the player was last looking at.

There is one arena, `0003CC20`, and it always holds the campaign whose missions
are current: `0002A139` fills it during the catalog walk, `0002A1D1` refills it
when the mission screen opens, `00029063` refills it again before the briefing.

The Falcon now keeps the same dependency order at startup: it builds the
catalog, parses mission 0, and only then loads the selected D/C terrain pair
and `SKY<N>`. That makes the direct/default mission the authored day mission
(`D1.DTA`/`C1.DTA`/`SKY2.RLE`) instead of a hard-coded backdrop. The natural
attract cycle is a separate, easily confused case: DOS increments its pass
counter before the first opening, so the first flight is pass 1, mission 1
(`D4.DTA`/`C4.DTA`/`SKY4.RLE`, the nighttime “DUI Enforcement” record). The
day `DEMO0` pass appears when the counter wraps to 0; changing the first
attract pass to force it would no longer match DOS.
So loading a campaign is also what gives a mission index its meaning, and the
port's `mission_buffer` is that arena. `mission_select`'s record number indexes
whatever was loaded last.

### The table lives inside the text block, and that broke a shortcut

`00029D47` is not a spare page of BSS. It is the eleven zero bytes between the
campaign screen's `0xFF` terminator at `00029D45` and the briefing pair's first
line at `00029D51`, and the digits are safe there only because no screen ever
renders that gap: the driver takes an absolute base per screen and nothing
points it at that one - `00029404` reads the accept/reject pair directly.

That last point stopped being a curiosity when `0002A104` was ported, because
this port was *not* taking absolute bases. It reached each screen by counting
`0xFF` terminators from the top of the block, which is correct for as long as
the block is the image's. `0002A17E` plants an `0xFF` of its own one row past
the last campaign found. With the two shipped files installed the campaign
screen ends seven rows early and every screen after it in the count moves, so
mission select would have landed on the leftover fill rows - and with a
different set of installed files it would land somewhere else again. A walk
over a block the program writes into is a walk over a moving target. The bases
are `00029B32`, `00029BEC` and `00029D81`, written at `00028D1E`, `00028F11`
and `00028F4B`, and `src/screen.s` now holds them as offsets.

### The star, and what it is for

Each mission record's closing brace may be followed by `'*'`, and `0002A234`
records that in `[00029F18+n]`. Both shipped catalogs star their back half:
missions 5-9 of `Comanche Training`, 3-9 of `Operation Maximum Overkill`. A
digit after the star is kept at `[00029F2C+n]` as digit+1, so that zero can mean
"no digit"; only the last entry of each file carries one, `*0` and `*1`.

`00028F50-00028FB8` is what reads the first flag. It walks the pilot's
hundred-byte progress record at `[000297BC + pilot*100 + digit*10]` alongside
the rows and colours each one: `'b'` for a mission already flown, `'g'` for one
that is open, and `'o'` for a starred mission whose predecessors are not all
flown - the running count of completed missions and the row index are compared
directly, so the first gap locks everything starred after it. `00029016` then
refuses a row whose remembered colour is `'o'` and puts
`"|o  You must finish |gGREEN|o missions."` from `000269D5` on the screen.
That pass is recovered here and not yet ported; the two flag arrays it needs
are.

## The options menu's drop-downs, and a table that is not what it reads as

Recovered ahead of its implementation, because the shape decides the port's
data structures and one plausible reading of it is wrong.

**The panels are groups of strings, terminated by `0xFF`.** They run
consecutively from `00026607` - **not** `00026618`, which is seventeen bytes
in and where the second string starts. The eight runtime row counts at
`000265F7` and the eight widths at `000265FF` sit between, and mistaking their
end for the group's start costs the Game column its first line, `About
|yComanche`. Driving the original is what showed it: its Game panel opens
with About Comanche selected, five rows, not four. The groups are: Game is `"Return to Game \"Esc\""`, `"Save Menu
Settings"`, `"Abort Mission \"Alt-A\""`, `"|rExit to DOS \"Alt-Q\""`; Detail
is three levels, then a `|` `0xF9` separator, then the brace booleans
`"} Clouds"` and `"{ Small Pixels"`; the next group is the three sound
volumes, and so on. One group per bar column, in bar order.

**Their row counts and widths are computed at load, not stored.**
`000268C5-00026915` walks each group to its `0xFF`, counting strings into
`cl` and tracking the widest into `ebp`, then writes `[ebx+000265F7] = cl`
and `[ebx+000265FF] = (ebp + 0x12) >> 2` - the row count and the panel width
in Mode X byte columns, so eighteen pixels of border around the widest line.
**The bytes sitting at `000265F7` in the image are not those counts.** They
read `02 02 02 02 ...`, which is coherent enough to be believed - it would
make every panel three rows - and it contradicts the four rows Game plainly
has. They are dead initialiser bytes; the runtime values are the ones above.
A port that copies the table out of the image gets a menu that is wrong in a
way that looks deliberate.

**Selection is a column and a row, packed to one byte to name exceptions.**
`[00026594]` is the column, wrapped against the bar's hotspot count less one
(the bar's trailing `0xFE` marks the end position, not an item, which is why
`00025E9F` decrements the count the text engine returned). `[00026598]` is
the row, wrapped against that column's count. Scancode `0x4B` steps the
column left and `0x4D` right, each resetting the row to zero; `0x48` and
`0x50` step the row, storing the direction in `[0002659C]` first.

`00025FA3` then forms `([00026594] << 4) | [00026598]` and compares it
against `0x13`, `0x23`, `0x27` and `0x2C`, adding the stored direction again
on a match. Those are the separator rows - the `|` `0xF9` inline images - so
the four constants are simply "column 1 row 3, column 2 rows 3, 7 and 12 are
not selectable". Nothing else in the loop knows a separator from an item.

**The radio marks are poked into the strings.** Before each redraw the loop
writes `0x20` or `0x60` into fixed bytes inside the drop-down text
(`00026712`, `0002672A`, `00026743`, `00026755` for one group, `000266B8`
onward for the next) according to the settings bytes `00025DD4-00025DD7`, so
the selected line of a radio group carries a backtick and the others a
space. The `'{'`/`'}'` booleans documented above are the same trick for
toggles.

**The panels are bevelled and translucent.** `0002628E` draws a mid-grey top
line, a dark-grey bottom line, and an interior that does not fill at all - it
reads every byte already on the screen and remaps it through the table at
`0005CE20`, which `0002AA50` builds by **halving each channel** of every
palette entry and matching the result back into the palette. So the options
bar and its drop-downs are smoked glass over the flight view. `src/menu.s`
halves the RGB565 channels directly and keeps the answer, having no palette
to quantise back into.

The rest of the geometry, all from `000264B1` and `00026F21`: the bar's box is
the full 320 pixels by fourteen rows; the selected column's label sits under a
light-grey block twelve rows tall, starting two rows above the text and one
byte column left of it, ending two byte columns short of the next hotspot; a
panel is `rows * 11 + 3` tall from row 15, one byte column left of its label
and `(widest + 0x12) & ~3` pixels wide; its rows are eleven pixels apart with
text from row 18 and the selected row's highlight twelve rows tall from row 16.
Panel text is green, set once at `00026F97` before the whole group, so every
line inherits whatever the previous line's last colour code left - only Game's
first line carries `|g` and only its last carries `|r`.

One quirk reproduced deliberately: `00026F21` never sets the plane register
before its text loop, so a panel's horizontal sub-column is whatever the bar's
own text left behind. With the shipped bar that is two pixels, which is what
`src/menu.s` adds.

**The Game column has no dispatcher case at all.** `00026AB6` holds no
comparison for selectors `0x00`-`0x03`, so pressing Return on Return to Game,
Save Menu Settings, Abort Mission or Exit to DOS does nothing in the original.
Those four lines are driven by the shortcuts printed in their own text - Esc,
Alt-A, Alt-Q - which the key loop handles above the dispatcher. Escape closing
the bar **is** Return to Game.

**Choosing a line is `0x1C`, and the dispatcher is a flat chain.** `0002612F`
packs the same `(column << 4) | row` and hands it to `00026AB6`, which is one
long run of `cmp al, <selector>`. Seven of its cases are the boolean options,
and all seven work the same startling way: they `xor al,6` **the first
character of the string** - `'{' ^ 6` is `'}'` - and mirror the result into a
settings byte. The brace in the text is the flag; drawing the line is what
reads the setting, because the font's `{` and `}` glyphs are an empty and a
filled checkbox, and the backtick that `00025EA5` pokes into the radio lines
is the selected-radio mark. The widgets are characters.

The seven, as selector and the string whose brace they flip: `0x14` Clouds
`000266A0`, `0x15` Small Pixels `000266A9`, `0x2D` ThrustMaster WCS
`00026767`, `0x2E` Rotor Control `0002677A`, `0x30` Artificial Horizon
`000267AC`, `0x31` HID Indicators `000267C1`, `0x32` HID Compass `000267D2`.
Escape leaves the loop at `0002615C` and the block at `0002617A` then pushes
the settings into the renderer selectors.

**The radio groups are the same idea one step out.** `00026CC2` writes
`'0'`-`'2'` into `00025DD4` for the detail level, `00026CE3` and `00026D2C`
the same into `00025DD5` and `00025DD6` for sound and music volume, and
`00026BD5` `'0'`-`'3'` into `00025DD7` for the controller. Nothing else
happens at the moment of choosing: `00025EA5` reads those four bytes before
every redraw and pokes a space into each line of the group and a backtick
into the chosen one, and the font's backtick is the selected-radio glyph.
`src/menu.s` holds the chosen line's offset rather than the digit, which is
the same fact in the form the redraw wants.

Shipped defaults, readable straight out of the strings: Detail Medium, Sound
Loud, Music Loud, Keyboard.

Still open: the **effects** of those settings - the detail level feeds the
renderer selectors at `0002617A`, and the volumes wait on the audio phase -
and Save Menu Settings and Abort Mission, which want a settings file and a
mission-end path. Note that selectors at `0x40` and above name a fifth column
and beyond, so `00026AB6` is shared with a menu that has more columns than
this one.

## The game will take its own screenshot, and that is the terrain oracle

`000165FD` writes the visible page to a file, and it is reachable from the
shipped executable. It builds a 128-byte header from the template at
`00016570` - `0A 05 01 08`, then xmax `0x147` = 327, ymax `0xEF` = 239, hdpi
328, vdpi 240 - creates the file named at `000165F0`, **`SNAP_001.PCX`**,
writes the header, reads the *back* page plane by plane through the Graphics
Controller, and finishes with the DAC read back at `000166FF` behind an `0x0C`
marker, each component shifted left twice. A 328x240 eight-bit PCX.

**A `.DTA` is that same file with the manufacturer field signed over.** From
+8 onward they agree exactly - xmax, ymax, the 128-byte header, the PCX
run-length payload, the `0x0C` palette. What differs is the first eight bytes:
a PCX opens `0A 05 01 08` followed by real xmin and ymin words, a `.DTA`
spends all eight on the tag `Kyle DTA`. So the origin fields of a `.DTA` are
the letters ` DTA` and must be read as zero rather than subtracted - do
otherwise and `RH66SIDE.DTA` measures -17112 pixels wide. One decoder reads
both, which is what makes the game's own screenshots directly comparable with
this port's captures.

**How to make it fire**, from the gate at `000189C2`. The keyboard ISR at
`00001B96` stores each raw byte at `[scancode & 0x7F + 00001A70]`, bit 7 set
on release, and mirrors makes only into `00001AF0`. The gate then wants
`[00001AA8]` - scancode `0x38`, **Alt** - and `[00001A89]` - scancode `0x19`,
**P** - to both read as pressed, and the feature byte `[000265ED]` to be
anything but `0xFF`. That byte is toggled at `0002602C` when the rolling key
history at `00001B70` reads `0x25152612` as a dword: scancodes `0x12 0x26
0x15 0x25`, which is E, L, Y, K in memory and **K, Y, L, E** as typed. The
author's name enables the developer screenshot.

So the procedure is: run the game, Escape into the options bar, type KYLE,
Escape back, then hold Alt and press P. `tools/compare-terrain.py` decodes
what lands and diffs it against a Hatari capture of this port; it is validated
against a case with a known answer - the port's own `BACK.DTA` attract frame
against the shipped asset, 76,800 of 76,800 pixels identical.

## What "the renderer has no pitch" actually means

Stated loosely before, and wrong in a way worth correcting: **the terrain
marchers never read pitch.** Searching all three (`0000D950-0000F317`,
`000137F0-00015854`, `0001B26C-0001C191`) for `[00019CF4]`, the pitch
accumulator, for the pair it derives, or for the horizon byte `[00019D80]`
returns nothing. The march is a function of viewer position, the direction
scale `[00019CB0]`/`[00019CB4]`, and the map. So the port's marcher is not
missing pitch, and adding it there would be wrong.

What pitch drives is everything around the march:

- **The backdrop horizon.** `00007D60` reads roll `[00019CF0]` and pitch
  `[00019CF4]`, passes both through a function selected per console variant
  from the table at `00007BC9`, and gets back a slope `[00019CF8]` and an
  offset `[00019CFC]`. The offset is clamped symmetrically against
  `0x21 - (|slope| * 0x40 >> 8)` - so the steeper the roll, the less pitch
  travel is allowed - and `[00019D80]` becomes `offset - [00019DBC] - 0x32`.
  An unrolled walker from `00007DC3` then steps `ebp` by the slope across the
  screen, taking a row from `0x30 - dh` each step. That is a **rotated,
  pitch-offset horizon**, and it is what the port replaces with a flat blit of
  `SKY2.RLE` placed one-to-one from the image's top.
- The cockpit gauges: `0000D505` scales pitch into a 22-frame needle.
- The object placement at `00022973`, `00022C3D` and `00024C20`.

So closing this gap is backdrop work, not marcher work, and it needs three
things recovered first: the per-variant slope/offset function behind
`00007BC9`, the unrolled walker's exact row arithmetic, and how the sky image
is sampled along a line that is no longer screen-aligned. All three are
recovered below; two smaller unknowns remain before code can be written that
is 1:1.

## The rotated horizon, recovered end to end

The three things named above, in the order the frame computes them. Nothing
here is a proposal: every line is decoded from the flat listing.

**1. The per-variant transform is a jump table of five tiny functions.**
`00007D60` loads roll `[00019CF0]` into `eax` and pitch `[00019CF4]` into
`ecx`, calls `[ebx*4 + 00007BC9]`, and stores the returned `eax` to slope
`[00019CF8]` and `ecx` to offset `[00019CFC]`. `ebx` is the same variant byte
`[00019D86]` the prologue used two instructions earlier for the heading table,
so one index selects both. The eight table entries hold seven distinct
targets, and every one of them is a handful of instructions:

| Variant | Target | Effect on (slope, offset) |
|---:|---|---|
| 1 | `00007BF0` | bare `ret` - **identity**: slope = roll, offset = pitch |
| 2 | `00007C00` | `xchg`/`neg`/`sar 2`/`shl 2` - slope = pitch\*4, offset = -roll/4 |
| 3 | `00007C10` | as above with the other sign - slope = -pitch\*4, offset = roll/4 |
| 4 | `00007C20` | `neg ecx` / `neg eax` - slope = -roll, offset = -pitch |
| 5 | `00007C25` | bare `ret` - identity again |
| 6 | `00007C26` | **not a slope transform - a chase camera.** Keeps roll, offset = 0 |
| 7 | `00007CC5` | **not a slope transform - a fixed ground camera.** slope = offset = 0 |

Entries 6 and 7 are the two that **move the viewpoint**, which is the reason
`0000D3DE`/`0000D3EA` push `[00019CD4]`/`[00019CD8]`/`[00019DFC]` around the
render and pop them back afterwards. Decoded and confirmed in the running game
2026-09-01:

- `00007C26` subtracts `turn * 4` from `[00019D00]` so the view trails the
  turn, then `[00019CD8] += hi32(0x0F000000 * cos)` and `[00019CD4] -=
  hi32(0x0F000000 * sin)` - fifteen map cells straight back along the view -
  and finally clamps the altitude up to `byte(2h + 12)` so the camera cannot
  sink into the terrain.
- `00007CC5` replaces `[00019CD4]`/`[00019CD8]` with `[00019CE4]`/`[00019CE8]`
  and the altitude with `[00019DF8]`, then sets `[00019D00]` from a bearing to
  slot `0x1F` (`000256C8`) plus 128.

They are selected by the `'1'`..`'8'` keys through `0001959F`
(`00019696`/`00019769`/`00019799`/`000197C9`/`000197F9`/`00019829`/
`00019854`/`000198E5`), and the shipped `DEMO*.SCR` streams send them
mid-flight - `DEMO1` at records 30, 206 and 357. **Ported 2026-09-01** in
`src/view.s`, with the whole basis certified against the original at variants
1, 6 and 7; see `analysis/functions/falcon-attract.md`, "The attract camera,
ported", for what is carried and the short list of what is not.

**`0000698D` stores 1 into `[00019D86]`**, and the comparisons scattered
through `0000D350`-`0000D4C4` test it against 1 and 5. So the ordinary
cockpit view takes the identity: **slope is the roll accumulator and offset
is the pitch accumulator, untransformed.** The port already produces both -
`flt_roll` and `flt_pitch` in `src/flight.s`, at the documented ±133 and ±33.
The input exists; only the consumer is missing.

**2. The clamp and the bias byte.** `00007D7F`-`00007DBE`, exactly:

```
lim    = 0x21 - hi8(|slope| * 0x40)      ; the steeper the roll, the less
offset = min(offset, lim)                ; pitch travel is allowed
offset = max(offset, -lim)               ; (00007D93..00007DAD)
[00019CFC] = offset
[00019D80] = byte(offset - [00019DBC] - 0x32)
```

Note `00007DB2` is `add eax, 0` with an imm8 slot - a patch point, currently
zero.

**3. The walker is 192 unrolled blocks, one per column.** From `00007DC3`,
with `ebp` zeroed and `ecx` held at `0x80`, each block is:

```
ebp += [00019CF8]                  ; the slope accumulator, 8.8 fixed point
edx  = ebp + 0x80                  ; round to nearest
dh   = hi8(edx)                    ; this column's integer row offset
horizon = byte(0x32 - dh + [00019D80])
[0x3CB40 + col] = horizon          ; the per-column horizon array, 192 bytes
[0x0AF62 + 0x30*col] = horizon     ; and self-patched into the span emitter
```

so the horizon is `0x32 - dh(col) + bias`: **roll shears it column by column
through the accumulator, pitch shifts all 192 together through the bias
byte.** The same block also derives a second pair from `0x30 - dh` via
`sar al,3` / `rcr bl,1` into `0x31B20`-`0x31FFC`, eight bytes per column, read
back through `lea ebp,[ebp*8 + 0x31B30]` at `000070C8`, `0000710E`, `00007222`
and `00007268` - **that pair is not yet identified.**

**4. The sky is drawn per column, upward, from its own strip.** The consumer
of `0x3CB40` is the sourced viewport fill - `00016F05` reads
`dh = [edi + 0x3CB40]` - and the loop body settles the sampling question:

```
esi = bank + col_from_heading*0x96   ; 0x96 = 150 = one column strip
ebp = bank + 0x12C00                 ; 512*150, the wrap limit
dl  = 0x6F                           ; first screen column, and it counts DOWN
repeat 150 times:                    ; exactly 150 triplets, 00016F0B..000171F9
    dec dh                           ; walk UP from the horizon row
    lodsb                            ; next byte of this column's strip
    mov [edx], al                    ; edx is row:column as dh:dl
esi += 0x96 ; edi -= 2 ; dec dl ; wrap esi to bank on reaching ebp
```

So each screen column takes one 150-byte sky strip, painted bottom-to-top
starting at that column's horizon row, and the strip is chosen by heading -
which is why `SKY2.RLE` is stored as 512 column strips of 150 and carries far
more width than the screen: **the extra width is the roll-shear and heading-pan
margin.** This variant steps `edi` by 2 and `esi` by two strips for 96 columns
(`ecx = 0x60`); the sibling at `00017230` is the same loop at full rate.

**5. `[00019DBC]` is the impact shake, and it is zero at rest.** Not a
placement constant, which is what it looked like from the subtraction alone.
The timer interrupt at `00001D20` runs a `xor 0xA50A50A0` / `add 0x50A05` /
`ror 3` PRNG on `[00019DB8]`, takes `and eax,3`, and stores it to
`[00019DBC]` **only while the countdown `[00019DC0]` is non-zero**, forcing
zero on the last tick. That countdown is set to `0x0A` at `00018F4C`,
`00019461`, `000235F6` and `00024453`, and to `5` at `00024352` - the last
two inside `00024310`, already on record as the destruction state. So an
explosion shakes the view for ten ticks. The value drives three things at
once: the VGA attribute controller's pixel-pan register `0x13` as `value*2`
(`00001DF1`), the CRTC start address through a four-entry table at
`00015B60` (`00015BBC`), and the horizon bias byte. `sub_00001CF5` cancels
all of it.

With the shake at rest the bias collapses, and the whole backdrop reduces to

```
horizon(col) = byte(offset - dh(col))          ; offset = clamped pitch
```

**6. The surface is 256x256 at flat `0x40000`, two interleaved fields.**
`000055DE` computes `0x4CC20 & 0xFFFF0000` = `0x40000` into `[00019E70]`, so
the byte at `(row<<8)|col` is `0x40000 + (dh<<8) + dl` - the 256-byte stride
the span writer's `inc ch` already implied. The `dl` question is answered by
the full-rate fill at `00017230`: `dl` starts at `0xDF` and the loop opens
with `ror dl,1`, but the tail at `0001756D` does `rol dl,1` then `dec dl`, so
**the rotate is not a column step - it is undone every iteration.** The net
step is `dec dl`, and the write column is `ror(counter)`, which puts even
columns at byte offsets `0x6F` down and odd columns at `0xEF` down. A row is
therefore two interleaved 128-byte fields, and the 192-column terrain
viewport occupies bytes 16-111 of each. The 96-column sibling at `00016EC0`
starts at `0x6F` with a plain `dec dl` and no rotate, writing only the even
field - which is exactly what half detail means here.

Both unknowns are now closed. The Falcon walks the DOS surface's full 192
source columns and expands each source byte to two adjacent RGB565 pixels.
The centred 160-column presentation window is cropped at composition, so the
sky cursor advances one authored strip per DOS source column and the horizon
shear uses the same full-rate walk and reversed horizon-array order. The bank
is transposed to row-major at load, which makes a per-column vertical offset a
strided write rather than the original's linear `lodsb` walk.

## The .DTL is loaded verbatim at 00019EE0, which specifies the fan statically

The previous note said tables A at `0001A2CC` and B at `00019EE4` are BSS the
loader fills, that they read as all-ones in the image, and that a runtime dump
was therefore needed to know what the fan is built from. The first two are
true and the conclusion was wrong.

There are **no writes to either address anywhere in the listing** - every one
of the twelve references is a read. They are not computed. The `.DTL` file is
read straight into memory at `00019EE0`, and its five 1000-byte tables land at
fixed addresses:

| address | table | what |
|---|---|---|
| `00019EE0` | count | 250 for `HIGH.DTL`; the marchers' ring limit |
| `00019EE4` | 0 | **B, the per-ring lateral step** |
| `0001A2CC` | 1 | **A, the per-ring forward increment** |
| `0001A6B4` | 2 | the projection slope source |
| `0001AA9C` | 3 | the projection bias |
| `0001AE84` | 4 | cumulative depth |

Every one of those is confirmed by the listing's own use of it, not by
arithmetic on the layout: `00015ADA` loads `esi` with `0x1A6B4` and indexes
`[eax*4 + 0x1AA9C]` to build the pages, `00024CD6` loads `ebx` with `0x1AE84`
for the object scaler, and `[00019EE0]` is compared as the ring limit at
`0000F305`, `00014531`, `00015ADF`, `0001B886` and `00024CDB`.

So the fan is fully specified by the file, statically, and nothing about it
needs reading out of a running program. The earlier "all ones" measurement was
of the uninitialised image, which says nothing about what the loader puts
there - and the check that concluded "A equals HIGH.DTL table 1 in 0/250
entries" was comparing the file against uninitialised memory rather than
against itself.

**What remains open is narrower than it was.** The marcher accumulates the
ring start along the forward axis only, then steps 192 columns laterally, and
`B_i` is `z_i/100` - so 192 steps sweep `1.92 * z` from the axis in one
direction, which cannot centre a symmetric fan. The offset that would centre
it is not in `0000D99A`. The remaining candidate is `sub_00007D25`, which
`0000D950` calls before any of this and which is 0x322A bytes of per-column
setup - only its prologue has been read.

## The terrain and sky pipeline, read end to end

Everything here is read from the flat listing. Where something is inferred
rather than decoded it says so.

### Order of a frame

`0000D950` is the high-detail marcher and it drives the whole thing:

1. `call 00007D25` - the per-column setup, below.
2. `mov gs, 0x38` - the arena selector. Heights are read `gs:[ebx]`; colours
   are read `[ebx + 0xFFFF]` through DS, so the two maps sit in different
   selectors and the colour map is one 64K-1 window on from the height index.
3. `call [00019C98]` - the viewport fill, which paints the sky. The pointer is
   set from the menu at `000261AF` (`0001757E`) and `000261D6` (`00017230`),
   so **the Detail setting selects the fill routine**, and `00017230` is the
   full-rate one.
4. `sub esp, 0xC0` then `rep stosd` of 0x30 dwords - a **192-byte per-column
   horizon array on the stack**, zeroed.
5. `edi = [00019CD4]`, `ebx = [00019CD8]` - the camera.
6. `[00019EDC] = [00019E5C]` with its low byte replaced by `NOT(alt) >> 1` -
   the projection page pointer, 256-byte aligned, whose low byte carries the
   camera bias `127 - alt/2`.

### The ring loop, `0000D99A`

```
edi += A_i * [00019CB0]      ; X += A_i * sin
ebx -= A_i * [00019CB4]      ; Y -= A_i * cos      -> forward is (sin, -cos)
push edi ; push ebx          ; the ring's start point
esi = B_i * sin              ; the lateral step, constant across the ring
ebp = B_i * cos
```

`A` is `0001A2CC` and `B` is `00019EE4`, which are `.DTL` tables 1 and 0 -
the file is loaded verbatim at `00019EE0`. The position **accumulates**; it is
not recomputed from a cumulative depth.

### The sample, `0000D9E9`

```
shld ebx, edx, 0xa           ; ebx  = (Y >> 22) << 10
shld ebx, edi, 0xa           ;      | (X >> 22)
add  al, gs:[ebx]            ; page index = bias + height, BYTE arithmetic
mov  ah, [eax]               ; the row, from the page
cmp  ah, [esp + 0x77]        ; against this column's stack horizon
ja   emit                    ; strictly above
sub  edx, esi                ; next column
sub  edi, ebp
```

The page is built at `00015B24` as
`clamp(high32((k - 128) << 24 * slope_i) + bias_i, 0, 0xFF00) >> 8`, with
`slope_i = high32(dtl2[i] * [00019CEC])` and `bias_i = dtl3[i]`. It is EDX
that receives the bias, so the product is the high half of a 64-bit multiply.

### The fan is symmetric: two half-sweeps from the centre

This was the one thing the pipeline read left open - the marcher appeared to
step 192 columns in a single lateral direction from a start point on the view
axis, which cannot centre a fan. It does not. It sweeps twice.

The emitter blocks carry their column as an immediate, and reading all 192 of
them gives the order directly: 191, 63, 190, 62, 189, 61 ... down to 144, 16,
then 64, 192, 65, 193 ... up to 111, 239. Low field 16-111 and high field
144-239, 96 blocks each - the two interleaved 128-byte fields of the
256-stride row - and the traversal starts at offset 63 in both, descends to
16, then resumes at 64 and ascends to 111. Outward from the middle, both ways.

The turnaround is in the sample chain. All 192 sample bodies are a fixed
32-byte stride except one 40-byte gap after sample 95, and those extra bytes
decode as:

```
2b d6   sub edx, esi        ; finish the 96th column
2b fd   sub edi, ebp
58      pop eax             ; the page pointer
5a      pop edx             ; restore Y   <- the ring centre, pushed at 0000D9BA
5f      pop edi             ; restore X   <- pushed at 0000D9B9
50      push eax
03 d6   add edx, esi        ; the second half sweeps the other way
03 fd   add edi, ebp
```

which is exactly what the `push edi` / `push ebx` before the samples is for,
and why the remaining 96 bodies carry `add` where the first 96 carry `sub`.

**So the view axis is the fan's centre, as one would expect, and this port's
centred fan is geometrically right.** The two differ only in how the same
points are reached - the original from the middle outward in two directions,
this port linearly from one edge - which is a rounding difference, not a
bearing one. The "heading is the fan's edge" hypothesis recorded earlier
today was wrong, and its withdrawal stands for the additional reason that the
disassembly contradicts it outright.

That leaves the substantive differences at two rather than four: the forward
vector's sign, and the horizon that is never applied.

### The emitter, `0000AF50 + 0x30 * col`

One 48-byte block per column, and the column index is immediate:

```
mov cl, 0xBF                 ; the COLUMN - 191 in block 0, counting down
mov al, [ebx + 0xFFFF]       ; the colour, from the colour map
mov bl, [esp + 0x77]         ; the OLD horizon
mov ch, bl                   ; ch:cl is row:column - the 256-stride surface
add ch, 0                    ; <- imm8 PATCH SLOT
mov [esp + 0x77], ah         ; store the new horizon
sub bl, ah                   ; span length = old - new
lea ebx, [ebx*4 + 0x6BF0]    ; a stub per length
push 0xDA05 ; jmp ebx        ; Duff's device, returning to the next sample
```

`00006BF0` is an unrolled array of `mov [ecx],al` / `inc ch` pairs, 4 bytes
each, so jumping in `length*4` writes `length` pixels stepping one buffer row
at a time.

**And that `add ch, 0` is the pitch and roll.** Its imm8 lives at `0000AF62`
and the walker at `00007DC3` writes `byte(0x32 - dh + [00019D80])` into
`[0000AF62 + 0x30*col]` for all 192 columns, every frame. Roll shears the
value column by column through the slope accumulator; pitch shifts all 192
together through the bias byte. The horizon is applied by **self-modifying the
emitter**, not by a term in the projection - which is why searching the
marchers for a pitch input found nothing.

### The sky, `00017230`

```
esi = bank + col_from_heading * 0x96   ; 0x96 = 150, one column strip
dl  = 0xDF                             ; counts DOWN; ror dl,1 at the loop top
                                       ; is undone by rol dl,1 at the tail
dh  = [edi + 0x3CB40]                  ; this column's horizon row
repeat 150: dec dh ; lodsb ; mov [edx],al
```

Each screen column takes one 150-byte strip of `SKY2.RLE`, and the first strip
is chosen from the view angle - `NOT([00019D00]) - 0x30000000 >> 0x17`, times
150. The bank's 512 strips are one revolution, which is why it is far wider
than the screen. `0x3CB40` is the same 192-byte horizon array the walker
fills, so the sky and the terrain share one horizon.

**`dec dh` walks the surface down and the screen UP, and the wrap is the whole
mechanism.** Earlier notes here called the strip "painted upward from the
horizon row"; that is the surface's direction, and the surface is upside down
(see *To the screen*). Byte `i` is written at surface row `(h - 1 - i) AND
0xFF`, and `h` is small - at rest `byte(0x32 - 0 + byte(0 - 0 - 0x32))` is
exactly 0 - so the subtraction wraps on the first or second byte and the run
lands in the high rows, which are the top of the screen. Through
`screen = 213 - surface row`:

> **`screen row = ((i - h) AND 0xFF) - 42`**, and for every `i` that does not
> wrap, simply `i - 42 - h`.

So in level flight the strip's bytes 42..149 occupy screen rows 0..107, its
first 42 bytes are above the screen, and the last byte sits at row 107 - well
below the terrain's own far horizon at `213 - 136 = 77`, which overwrites the
overlap. The bytes that wrap the other way land at screen rows >= 214 and are
outside the transferred window, so a port that simply clips the linear form
reproduces the modular one exactly.

The 42 rows above the screen are not slack: they are the headroom the backdrop
pans into. `h` is what the walker wrote. An earlier reading here said the
fill consumes the horizon array backwards and that the Falcon must reverse
the walker order into `backdrop_dy`; both halves of that were wrong, read off
`edi = 0xBF / dec edi` without noticing the fill's own surface column counts
down beside it. Decoded properly, `00017273`'s iteration k draws surface
byte column `ror(0xDF - k)` - logical column `191 - k`, right to left - takes
`dh` from `[0x3CB40 + (191 - k)]`, and reads strip `origin + k`. So the
horizon array is indexed by screen column **identically** in the fill and in
the emitter patches (the walker's step j stores to emitter block j and
`h[95-j]`, then `h[j]` - the same centre-out order the ring marcher samples
in), and the strips pair with columns **right to left**: column c takes strip
`origin + 191 - c`. The walker itself is two half-ramps with a sign flip:
`sub al,dh` while it patches columns 95..0, an accumulator reset at
`0000968A` (column 96 gets `dh = 0` exactly), then `add al,dh` for columns
97..191 - one straight shear line pivoting at the screen centre.

### To the screen

`00006FEF` compares the 256x256 surface at `0x40000` against a shadow copy and
records up to 2,048 changed runs as (length, source, destination, row-record)
quads. `00007AA0` then copies them: Map Mask `0x0302` for planes 0 and 1, a
run of bytes, then `0x0C02` for planes 2 and 3 and the run again - so **each
source byte becomes two adjacent screen pixels**, and 192 terrain columns span
384, of which the 328-wide Mode X page (four planes of 82) shows the middle.

**And it is what fixes the vertical mapping, because it walks both ends in one
loop.** The prologue at `00006FEF` is exact:

```
edx = [00019E70] + 0x2011      ; surface row 0x20 = 32, column 0x11
ecx = 0xB6                     ; 182 rows
esi = [000014C4] + 0x39FA      ; VGA A000 window + 181*82
[00019E54] = esi
...per row: inc dh             ; source row RISES
            sub [00019E54],0x52 ; destination row FALLS
```

`0x39FA` is `181 * 82` exactly, `[000014C4]` is the A000 window (`0000156E`),
and the resting CRTC start is zero - entry 0 of the shake table at `00015B60`,
whose dwords are `0, 0x51, 0xA4, 0xF5, 0x148, 0x199`. So surface row 32 is VGA
row 181, surface row 213 is VGA row 0, and

> **screen row = 213 - surface row**, over a terrain viewport of VGA rows
> 0..181.

**The surface is stored upside down, and that inverts the reading of every
routine that touches a row.** Three independent things only make sense this
way: the emitter's `inc ch` walks a span UP the screen, not down; the
marcher's `cmp ah,[esp+0x77]` / `ja` lets the occlusion row CLIMB with
distance, which is a silhouette rising toward the horizon rather than sinking;
and the page build's row rising with terrain height puts high ground high.

Note also that the region entry above covering `00006FEF-00007BCD` as
cockpit/HUD element drawing is wrong at its start: `sub_00006FEF` itself is
this scanner, and the twelve sprite entries begin after it.

### What this port does differently

| | original | `src/render.s` | matters? |
|---|---|---|---|
| loop order | ring-major | ring-major since 2026-08-17 | no |
| fan | two half-sweeps from the centre | same order over all 192 source columns; raw B_i, no presentation rescale | was linear from one edge |
| ring position | accumulated by raw `A_i` | same accumulation and Q31 high-word arithmetic at 16.16 scale, capture pending | was `z_i * direction` |
| forward | `(sin, -cos)` of the DOS Q31 angle | Q31 `flt_angle`, with the DOS `-cos` Y step | no |
| row | page lookup, clamped 0 and 255 | page lookup since 2026-08-17 | no |
| anchor | `screen = 213 - page row`, viewport 182 rows | same since 2026-08-18 | was 15 rows |
| horizon | self-patched into the emitter, per column | same since 2026-08-18 | was inverted |
| Falcon terrain x | DOS source bytes are expanded to adjacent pixels by the VGA transfer | source column `c` covers RGB565 x `2*(c-16)` and `2*(c-16)+1` for visible `c=16..175`; all 192 columns are still walked | platform |
| sky | strip byte i at `screen = i - 42 - h` | same since 2026-08-18; one authored strip is consumed per DOS source column, with only the centred 160-column composition window retained | was anchored at row 0 |
| span clip | free: writes wrap inside the 256x256 surface | clipped in `TERRAIN_PAINT` against the per-frame `ring_cols` | platform |
| occlusion seed | zeroed array = page row 0 | `RING_PAGE_ANCHOR` since 2026-08-18 | was the cockpit line |
| sprite scale | `(min(3200/z,127)+1)/64`, capped 2x | HIGH.DTL table-0 relation since 2026-08-18 | was 56, 12% oversized |
| projectile life | 128 ticks: `inc`/`js` on `[00021E35]` | 128 since 2026-08-18 | was 16, 8x short |
| sprite frame | `azimuth[(b+4)>>3 & 31] + elev[(e+bias)>>4]` from the "3D" record | exact model record loaded and selected by `object_aspect`; pair handlers preserve DOS A/B order and model-B azimuth bias | attract object factory/draw verified against DEMO1 TANK/TURR slots and QEMU active-object trace |

**Hatari capture completed 2026-08-18.** The source and generated tables now
match the recovered loop, and the attract demo was run through VBL 4000 with a
fresh RAM/framebuffer dump. The corrected CPU build reached the checkpoint
with altitude `0x7C`, zero collision bounces, cockpit composition, and visible
terrain relief. A fixed-camera capture would improve pixel-to-pixel comparison
but is not needed to prove that the old full-height terrain slab was caused by
the flight-state bug.

**The three row-space rows above were all one mistake.** The surface being
upside down was not read until 2026-08-18, and everything derived from a row
inherited it: the anchor came from the 199-entry scanline table at `0002D7F0`
(a 192-pitch surface with no reader in the listing, and not the 256-stride one
the emitter writes) instead of from the transfer, which put the whole picture
15 rows high; the horizon byte was added to a top-down screen row where the
original adds it to a bottom-up surface row, so pitch and roll moved the
terrain the wrong way; and the sky was blitted from screen row 0 downward
where the original hangs it 42 rows above the screen. At the true anchor there
are 42 rows of headroom above the screen; when a hard roll moves the strip past
that headroom, the DOS fill has no source bytes for the rows above it and leaves
the persistent surface untouched. The port now does the same instead of
repeating strip row 0, which had manufactured thin vertical lines wherever
that pixel was a cloud edge.

The zero-attitude edge remains the direct sanity check: the DOS equation puts
the sky/ground boundary at row 108 (`-SKY_TOP_BIAS + SKY_IMAGE_ROWS`) before
terrain overwrites it. Under the Falcon mapping the same edge is emitted by
the visible 160-column crop of the fully walked 192-column source field.

Note what the level capture cannot show, since it was nearly taken as proof on
its own: with the horizon byte at zero, sky and terrain sit where they would
with `BACKDROP_TILT` off entirely, and the first attempt at the shear capture
measured a flat 108 across all columns because `BENCH_ROLL` had been written
into the branch of `game_init` the pinned camera does not assemble. A tilt
test that does not move is not a passing tilt test.

**And the occlusion seed was the fourth row-space mistake.** `0000D976`
reserves `0xC0` bytes of stack and `rep stosd` zeroes `0x30` dwords, so all
192 of the original's columns start at page row 0 - the bottom of the surface.
An earlier port seeded them at `console_floor`, the deepest row the cockpit
lets a column show, reasoning that spans below it are invisible. They are, but
the seed is not a clip. A sample at or below it fails the `bge` and is dropped
**without advancing the occlusion**, so every near ring under the cockpit line
was discarded rather than drawn and then covered, and the band between the
sky's bottom edge and the terrain's top went unpainted. The current CPU and DSP
paths seed the recovered page row 0 / screen row 213 contract instead.

That hole predates the anchor work and was invisible while the sky image ran
from screen row 0 down 150 rows, because sky pixels filled it and read as
haze. Anchoring the strip correctly ends it at `107 - h`, so the same hole
began showing the `COL_GROUND` base instead - a green block across the lower
third, measured at 8803 of 12800 pixels in rows 100-139, in a colour
(`$2A24`) that does not appear in the terrain palette at all. Seeding at
`RING_PAGE_ANCHOR` restores the original's behaviour and closes it.

**The forward vector is not a difference, and the check that proves it also
condemns the silhouette metric.** This port's heading runs opposite to the DOS
accumulator through the `128 - h` mapping already on record, and in a 256-step
table `sin(128-h) = sin(h)` with `cos(128-h) = -cos(h)`. So the port's
`(sin, cos)` of its own heading IS the DOS `(sin, -cos)`. At `BENCH_HEADING`
119 against DOS index 9 both come out `(+0.2191, -0.9757)` exactly.

Applying the sign again - which the specification appeared to call for -
produces `(+0.2191, +0.9757)`, a provably wrong basis. It measured **-13.86
mean with an 11.26 spread against the correct code's -32.64 and 21.44**: the
metric improved by nearly half on a change that breaks the geometry.

That is the sixth time a silhouette figure has pointed the wrong way today and
the least ambiguous. **The metric is retired.** It cannot distinguish a better
renderer from a differently-wrong one, and no further change should be
justified by it. What remains usable is the disassembly, and per-value
comparison against it.

So one substantive difference is left, not two: the per-column horizon the
original writes into `0000AF62 + 0x30*col` every frame and this port does not
apply at all.

## WITHDRAWN: the fan-edge result was measured on a broken frame

The section that stood here reported that starting the fan on the heading
axis rather than centring it cut the silhouette spread from 28.07 to 14.60,
and called it the first structural correction the measurement had confirmed.
**It is withdrawn.** So is the follow-on scan that put a sharp minimum of 8.65
at a column offset of 82.

Both were measured without looking at the frames. When looked at, neither
reference render resembles the original at all: they are flat brown slabs in
40-pixel blocks with an unpainted blue band below the terrain. The low spread
at column offset 82 is low precisely because that frame's silhouette is nearly
flat - a blob edge scores well against any profile.

The page-build fix behind them is real and stands: `00015B24` takes the HIGH
32 bits of the `imul`, because `add edx,[00019CC4]` puts the bias in EDX, and
before that fix the reference painted terrain over the whole frame. But
fixing it only moved the tool from producing nothing to producing something
wrong, and every figure taken from it since is a measurement of that wrong
thing.

**The pattern is the lesson.** Five times today a number has been trusted
without the artefact behind it being looked at - the image width, zsh
argument splitting, a black backdrop, a frame with no sky, and now this. The
metric is `compare-silhouette.py` and it will happily score a degenerate
frame. Nothing from the reference should be recorded again until the frame it
renders is recognisable as the same place as the original's, by eye, first.

What still stands is what was read rather than measured: the `.DTL` load
address at `00019EE0` with its five tables, the accumulated ring position,
forward as `(sin, -cos)`, the page build with both clamps, and the proven
equivalence of `PROJ_SCALE/z` to the file's own slope.

## STATUS of the Python reference: renders, but not correctly

The retired Python marcher rendered terrain across the whole frame with no
horizon, so its projection was wrong and none of its output was evidence. Three
numbers were recorded from it - -42.2/18.6 for the plain orientation, and
-46.1/19.2 and -39.6/32.5 for swapped and flipped axes - and all three are
artefacts: `compare-silhouette.py` locates terrain as the first row that is
not sky-blue, so a frame containing no sky reports row 8 in every column and
the reported "mean" is 8 minus the original's own mean horizon. Withdrawn.

What that does not withdraw is the structural reading below, which comes from
the listing rather than from the reference.

## How the CPU fan is built from the DOS tables

The DOS setup and ring loop are the authority. The CPU port now consumes the
same A/B words emitted from `HIGH.DTL`; the Falcon's true-colour surface only
expands each of the 192 source columns to two pixels and crops the outer 16
source columns at the composition boundary.

```
0000D974  edi = [00019CD4]                  ; X
0000D97A  ebx = [00019CD8]                  ; Y
0000D98C  al  = [00019DFC] ; not al ; shr 1  ; 127 - alt/2
0000D995  [00019EDC].low = al                ; the page pointer's low byte
loc_0000D99A:                                ; once per RING, ecx = ring
0000D99B  eax = [ecx*4 + 0001A2CC]           ; table A
0000D9A2  imul [00019CB0]                    ; * sin
0000D9A8  edi += edx                         ; X += A_i * sin
0000D9AA  eax = [ecx*4 + 0001A2CC]
0000D9B1  imul [00019CB4]                    ; * cos
0000D9B7  ebx -= edx                         ; Y -= A_i * cos
0000D9B9  push edi ; push ebx                ; the ring's start point
0000D9BB  eax = [ecx*4 + 00019EE4]           ; table B
0000D9C2  imul [00019CB0] ; esi = edx        ; lateral step, sin component
0000D9CA  eax = [ecx*4 + 00019EE4]
0000D9D1  imul [00019CB4] ; ebp = edx        ; lateral step, cos component
```

Four things, and the first two are the ones that matter.

**The ring position is accumulated, not computed from z.** `edi`/`ebx` carry
forward across rings and each ring adds `A_i`. `render_terrain_ring` now does
the same with the raw 10.22 A table and the DOS signed high-word product,
converted to the Falcon's 16.16 coordinates.

**Current coordinate correction (2026-09-08):** the historical 16.16 wording
above describes an older target implementation. The current native marcher
and the corrected JavaScript marcher accumulate raw DOS 10.22 coordinates.
JavaScript had mixed a 16.16 camera with raw DTL increments, producing tall
terrain streaks. It now preserves raw camera/step arithmetic through the map
lookup; see `analysis/functions/browser-attract.md#terrain-coordinate-correction-2026-09-08`
for the regression and retained DOS capture check.

**Forward is `(sin, -cos)`, not `(sin, cos)`.** `X += A*sin` and `Y -= A*cos`.
That is the -Y convention the axis-convention note already records for the
mission spawner, and it applies to the marcher too. The lateral step is
`X -= B*cos`, `Y -= B*sin` - perpendicular, and also negative in both.

**Tables A at `0001A2CC` and B at `00019EE4` are runtime-filled in DOS.**
The `.DTL` loader supplies A from table 1 and B from table 0. The Falcon build
emits those same raw words into `ring_a_table` and `ring_b_table`, so the CPU
reference does not derive either table from a guessed depth curve.

**The DOS emitter walks two half-sweeps from the pushed start point.** The CPU
walk mirrors that order over all 192 DOS source columns. The 320-pixel Falcon
surface keeps the centred source columns 16..175 after expansion; it does not
choose a different terrain geometry or rescale B_i.

## The two halves are interleaved, and that is the shape difference

Captured from the running original on 2026-08-23 with `PIN_CAMERA=1
DUMP_BASE=0x31000 DUMP_LEN=0xC000 bash tools/oracle-capture.sh`, because none
of it is in the executable: `00007AA0` drives the terrain transfer entirely
from BSS, and the flat content region ends at exactly `00032B20` where the
first of its tables begins.

`sub_0000D3C0` runs marcher -> objects -> `00007AA0` -> input, so `00007AA0`
is the composition transfer, and it runs its column list twice:

```
00007AA0  ax = 0x0302   ; Map Mask planes 0 and 1
00007ADA  add esi, [eax]        ; eax = [ebp*4 + 0003AB20]
00007B2E  cmp ebp, [00019E4C]   ; 261 runs
00007B36  ax = 0x0C02   ; Map Mask planes 2 and 3
00007B6F  add esi, [eax + 4]    ; the SAME pointer, four bytes on
                                ; [00019E50] = 521 bounds the second pass
```

**`[ptr+4] - [ptr+0]` is 128 on all 521 runs.** Not approximately, not mostly:
128 every time. And 128 is the distance between the two blocks the fill writes
its 192 columns into - `00016EC0` fills byte offsets 16-111 and 144-239 of a
256-byte row, and `144 - 16 = 128`.

So the two plane-pairs read the same relative position in *different halves of
the compose buffer*. Block A goes to planes 0 and 1, which are screen pixels
`4b+0` and `4b+1`; block B goes to planes 2 and 3, pixels `4b+2` and `4b+3`.
**The halves interleave**: source column n of block A lands immediately left of
source column n of block B, and in a flat 0-191 numbering those two are
ninety-six apart.

Measured geometry, from the same capture:

| | |
|---|---|
| runs | 261 planes 0/1, 260 planes 2/3 |
| screen row stride | 82 bytes (153 of 158 deltas) |
| terrain band | 168 rows |
| widest run | 82 bytes = 164 px per pass, 328 px both |
| narrow rows | 1-12 bytes at the bottom - the console aperture |
| window, block A | columns 23-104 |
| window, block B | columns 151-232 |

Seven columns are dropped from each end of each block, so **164 of the 192
source columns reach the screen**, two pixels each.

### CORRECTION 2026-08-23: the interleave does not reorder anything

The paragraph above concluded that the halves interleave *columns* and that the
original draws 0,96,1,97 where the port draws 0,1,2,3. That is wrong, and it
was wrong the same way the fan-edge result was: a structure was read off the
transfer alone without checking what the fill puts in the buffer.

`00016EC0` fills block A by walking `sub edi, 2` from `edi = 0xBE` down to 0
against `dec dl` from `dl = 0x6F` down to 0x10 - ninety-six destination
columns taking every OTHER entry of the 192-entry horizon array. So compose
column `16 + k` carries source column `2k`: **block A is the even columns.**
With block B holding the odd ones, the plane interleave puts source column
`2k` at pixels `4b+0,4b+1` and `2k+1` at `4b+2,4b+3` - adjacent source columns
landing adjacent on screen. The two-block split and the +128 are a Mode X
plane-writing convenience, not a reordering, and they reconstruct a plain
linear left-to-right field.

The block layout itself is confirmed independently: the flat-colour fill at
`0001757E` walks `edi += 0x10`, 96 bytes, `edi += 0x20`, 96 bytes, which is
16-111 and 144-239 with 32-byte gaps.

What survives from the capture is the geometry, which was measured rather than
inferred: 261 and 260 runs, an 82-byte row stride, a 168-row band, 82 columns
taken from each block, and the console aperture narrowing the bottom rows. What
does not survive is the claim about ordering.

**Block B holding the odd columns is inferred, not observed**, and looking for
the matching pass turned up something that undercuts the premise instead.

There is no odd-column sibling. What sits after `00016EC0`'s loop is
`00017230`, a DIFFERENT fill: `ecx = 0xC0` where `00016EC0` has `0x60`, and
`ror dl, 1` per column at `00017273` instead of `dec dl`. That rotate makes the
destination byte cycle through only eight values - EF, F7, FB, FD, FE, 7F, BF,
DF, a single clear bit walking round - which is not a linear column walk at
all. Two fills with different column counts and different addressing are two
schemes, not two halves of one.

And `00016EC0` is reached indirectly. `[00019CA0]` holds it, written at
`000261EA`, with `0001757E` - the flat-colour fill - as the alternative at
`000261C3`; both writes are in the detail/settings region around `00026211`.
The slot is read at `000137FC`, which is inside `sub_000137F0`, the MEDIUM
detail marcher. The high-detail marcher is `0000D950`.

Two of those doubts were then settled by reading the slots themselves, over 167
pinned snapshots:

| slot | value | |
|---|---|---|
| `[00019C94]` | `0000D950` | the HIGH marcher, which is the one the port implements |
| `[00019CA0]` | `00016EC0` | the sky fill analysed above IS the active one |
| `[00019CA4]` | `003DE8F8` | sky bank loaded |
| `[00019CA8]` | `0` (161) / `0x7D00` (6) | page base only, never a sub-page pan |

So `00016EC0` is not a medium-detail-only routine: the fill slot is shared and
the high marcher runs it. The model was read off the right code after all.

**`[00019CA8]` kills the windowing theory.** It only ever holds 0 or `0x7D00`,
the two page bases, so the display start is always page-aligned and the visible
320 pixels ARE the left 320 of the 328-pixel logical line.
`tools/compare-terrain.py`'s assumption is correct, and the 21-23 row spread is
not an artefact of sampling the wrong window. That was the standing suspect in
`PORTING-PLAN.md` and it is now ruled out.

**RESOLVED: block B is the odd columns.** `00017230` is the 192-column sky
fill and it writes BOTH blocks in one pass. Its loop tail is the key:

```
00017271  mov dl, 0xdf          ; 223
loc_00017273:
00017273  ror dl, 1             ; the ADDRESS byte
00017275  mov dh, [edi + 0003CB40]
          ... 150 strip bytes up the column ...
0001756D  rol dl, 1             ; undo it
0001756F  dec dl                ; the STORED value walks 223 down to 32
00017571  dec edi               ; horizon entry 191 down to 0
00017572  dec ecx               ; 192 iterations
```

`ror(dl,1)` is `dl/2` when `dl` is even and `dl/2 + 128` when it is odd, so the
destination alternates between the two blocks while `edi` walks every entry:

| `edi` | `dl` | address byte | block |
|---|---|---|---|
| 191 | 223 | 239 | B |
| 190 | 222 | 111 | A |
| 189 | 221 | 238 | B |
| ... | ... | ... | ... |
| 1 | 33 | 144 | B |
| 0 | 32 | 16 | A |

So **block A column `16 + edi/2` holds the even horizon entries and block B
column `144 + (edi-1)/2` holds the odd ones**, which is exactly what the
transfer's `+128` needs to reconstruct a linear left-to-right field. The
even/odd reading is now recovered from code rather than inferred, and the
withdrawal in the correction above was right: the interleave reorders nothing.

`00016EC0` is the same fill at half resolution - 96 iterations, `dec dl` with
no rotate, `sub edi, 2`, block A only - and it belongs to a DIFFERENT path.
There are three dispatch slots, all read from the same capture:

| slot | value | |
|---|---|---|
| `[00019C94]` | `0000D950` | the HIGH marcher, 192 columns |
| `[00019C98]` | `00017230` | the 192-column fill, both blocks |
| `[00019C9C]` | `0001C920` | unidentified |
| `[00019CA0]` | `00016EC0` | the 96-column fill, block A only |

`[00019CA0]` is read at exactly one site, `000137FC`, inside `sub_000137F0` -
the MEDIUM marcher. So `00016EC0` never runs on the high path, and the chain
closes: the high marcher walks 192 columns, `00017230` lays them into both
blocks even/odd, and `00007AA0` reads both `+128` apart and interleaves them
into the plane pairs as one linear field.

### The column mapping, end to end

- the marcher walks 192 source columns;
- even columns go to compose block A at `16 + edi/2`, odd to block B at
  `144 + (edi-1)/2`;
- the transfer takes an 82-column window from each block - A columns 23-104,
  B columns 151-232 - so source columns **14 to 177**, 164 of the 192;
- each contributes two pixels, giving 328 pixels of logical line;
- the display does NOT start at page x 0. `[00019CA8]` is page-aligned, but
  `00015BB7` programs the CRTC start from `[0x19CAC]`, which `00015C06` sets
  to `[0x19CA8] + 1` byte. So the visible field starts at page x 4 and is
  source columns **16 to 175**.

**Corrected 2026-09-22.** This entry used to read "the left 320 of those" and
columns 14 to 173. On that basis the port's crop was moved from 16..175 to
14..173, which placed the terrain four pixels left of the cockpit. Paired
DOS/Falcon frames showed it directly: the terrain matched the DOS page at x 0
(98.4 % in a fixed-camera frame), the cockpit at x 4 (`PORTING-PLAN.md`,
"The second pair"). `TERRAIN_VIEW_FIRST`/`LAST` are back to 16/175 in
`src/dsp/proto.inc` and `jsComanche/dos-runtime.js`, with `CMD_VERSION` 11.

**CLOSED 2026-09-01: `0001453D` writes 144-239, and it is a block copy.**
A write watchpoint on one block-B byte, taken with `[0x19C94]` poked to
`0x000137F0`, stopped inside an unrolled run at `00014CC7`. Its head is at
`0001453D`, immediately after the ring loop's `cmp ecx,[0x19EE0] / jb`:

```
0001453D  add esp, 0xc0            ; drop the 192-byte occlusion array
00014543  mov edi, [0x19E70]       ; the surface, 0x40000
00014549  add edi, 0x10            ; block A, compose byte 16
0001454C  mov esi, edi
0001454E  add edi, 0x80            ; block B, compose byte 144
00014554  mov ecx, 0x18            ; 96 bytes
00014559  rep movsd
0001455B  add edi, 0xa0            ; 96 + 160 = one 256-byte row
00014561  add esi, 0xa0
          ... unrolled 256 times, ending in the ret at 00015854 ...
```

So the 96-column path marches half the columns into block A and then copies
block A over block B, and the transfer's two plane passes paint the same byte
twice: **one marched column is four screen pixels.** The pair table at
`0x31B30` is unchanged between the two paths - measured, `pass2 - pass1` is
`+0x80` or `-0x7f` on both - so the block interleave is not what changes; the
content of block B is.

Measured, with `[0x19C94]` poked mid-flight: block A equals block B at the
same column offset for **17469/17472** of the visible field on the 96-column
path, against **14051/17472** on the 192-column path, and the block-B bytes
are not stale (only 1361/17472 survive from the previous 192-column frame).
The original's own silhouette archive confirms the pairing from the other
side: `occl[2k] == occl[2k+1]` for **10080/10080** of the columns the main
view owns, against 6229/10080 on the 192-column path.

**Superseded, for the record:** `00016EC0` writes compose columns 16-111
only - `dl` is forced to `0x6F` and walks down to `0x10`, and `[00019E70]`
supplies only the high half of the address, so the low byte never reaches
144-239. The transfer reads both blocks, `+128` apart, on every one of its 521
runs. Something fills 144-239 and it is neither this routine nor `00017230`,
whose `ror dl, 1` cycles through eight values. Until that writer is found the
even/odd reading remains a hypothesis.

### What this means for the port

`src/render.s` walks 192 source columns and presents source columns 16..175
as two-pixel columns - 320 pixels, with the remaining logical-line margin
off-screen, in flat order.
Three things differ from the above, and the third is the one that matters:

Under the correction above, the ordering is the same on both sides and the
difference reduces to the window:

- 164 source columns reach the screen, not 160;
- taking 82 from each block at offsets 23-104 and 151-232 means source columns
  14 to 177, while the display, from page x 4, exposes source columns 16 to 175.
  The port now uses that same visible window; source columns 174..177 remain
  in the logical line's off-screen right margin.

Both are offsets, not shape. So this capture does NOT explain the 21-23 row
spread, and the honest position is that the spread is still unexplained.

### 328 is a logical line on both machines, so there is no boundary here

Recorded as a platform deviation first, and withdrawn the same day by the
project owner: there is no VGA 328-pixel mode either. 82 bytes per plane is the
CRTC Offset register - the LOGICAL scanline - while the display window stays
320 wide and the extra 8 pixels sit off-screen for hardware panning.
`[00019CA8]` is that start offset: `00015BF7` loads it immediately before the
CRTC writes at `00015C3D`/`00015C89`, `0000D6BF`/`0000D6FC` move it by 0x1A,
and the snapshot writer reads the other page with `[00019CA8] XOR 0x7D00`. So
the PCX the oracle captures is the full 328-pixel line, and what a player sees
is a 320-pixel window into it.

VIDEL does the same thing. `$FFFF8210` is the line width in words and is
independent of the displayed width - `src/start.s` already writes
`SCREEN_WIDTH` there. Setting it to 328 gives the Falcon the original's
geometry exactly: a 328-pixel virtual line, a 320-pixel view, 8 pixels off the
right, and the display start reproducing what `[00019CA8]` does.

So `TERRAIN_VIEW_FIRST` should not exist. The port crops because its surface
was made the width of its display; with the virtual line widened it can draw
all 164 source columns the transfer carries and let the hardware choose the
320 it shows, which is what the original does.

Two consequences worth having written down:

- The port showing 160 columns is not necessarily four short. 160 two-pixel
  columns is exactly the visible 320, so the original's extra four may be
  entirely off-screen margin. Which it is depends on `[00019CA8]`, which is
  four bytes and is now dumpable.
- `tools/compare-terrain.py` takes the original's LEFT 320 columns of the
  328-wide PCX. That is an assumption about where the display window sat, not
  a measurement, and `PORTING-PLAN.md` already named establishing it as the
  next step. Reading `[00019CA8]` at the pinned camera settles it.

  **Measured 2026-09-22:** the window starts at page x **4**. `00015BB7`
  programs the CRTC from `[0x19CAC]` = page + 1 byte, and one Mode X byte is
  four pixels. The static cockpit of a paired frame matches 25,110 of 28,800
  rows at x 4, against at most 17,498 at any offset from 0 to 8 (`PORTING-PLAN.md`,
  "The first complete-frame pair"). `compare-terrain.py`'s left-320 window is
  therefore misregistered by four pixels.

  **And so is the port's own terrain.** Its 3D view peaks at page x 0 (98.4 %
  in a fixed-camera frame), not at 4. `00025C32`'s `[x>>1 + 0x3CB4E]` puts
  column 14 at page x 0, and the port puts column 14 at surface x 0, which
  is page x 4 (`PORTING-PLAN.md`, "The second pair").

This is recovered, not yet ported. The renderer change it implies has not been
made, and the 21-row measurement has not been re-run against it.

## The projection is exactly right, which leaves the sampling

Read out of `0000D9E9` rather than inferred, because eight parameter fits had
failed and none of them was going to be the answer.

The original does not compute a row. Each sample is five instructions:

```
xor  ebx, ebx
mov  eax, [esp]              ; the page pointer, 256-byte aligned, and its low
                             ; byte is 127 - alt/2 - the camera bias
shld ebx, edx, 0xa           ; ebx = (Y >> 22) << 10
shld ebx, edi, 0xa           ;     | (X >> 22)          - the map index
add  al, gs:[ebx]            ; page index = bias + height, BYTE arithmetic
mov  ah, [eax]               ; the row, straight out of the page
cmp  ah, [esp + 0x77]        ; against this column's horizon on the stack
ja   ...                     ; strictly above: emit
sub  edx, esi                ; the ring's lateral step, constant per ring
sub  edi, ebp
```

and the page it indexes is built at `00015B24` as

```
page[k] = clamp((k - 128) * slope_i + bias_i, 0, 0xFF00) >> 8
```

Three things fall out, and the third is the point.

**The byte wrap on `add al` cannot fire.** `D1.DTA`'s heights run 0 to 187,
and with the bias at 127 - alt/2 the index only wraps above 168 - which is 2
cells in 1,048,576. It is real arithmetic and it is not what differs.

**Both clamps are real**, at page row 0 and 255, where this port clamps at
row -1 instead. That is a saturation difference at the extremes, not a shape
difference across a profile.

**And the projection is exactly equivalent.** Expanding the page index,
`page[(127 - alt/2 + h) - 128] = (h - alt/2 - 1) * slope_i + bias_i`, against
this port's `horizon_i - (h - alt/2 - 1) * PROJ_SCALE / z_i` with
`horizon_i = 198 - bias_i>>8` and `screen row = 198 - page row`. The two agree
if and only if `PROJ_SCALE / z_i == slope_i`, where `slope_i` is
`high32(dtl2[i] * [00019CEC])`. Checked numerically across all 250 steps:

| i | 0 | 2 | 10 | 50 | 100 | 200 | 249 |
|---|---|---|---|---|---|---|---|
| ratio | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9999 |

So the projection formula, the per-depth slope, the bias curve and the camera
term are all correct, and the silhouette comparison's 33-row offset with its
21-row spread cannot come from any of them. Nor from the column width, which
the Mode X copy settles at 2:1, nor from the depth schedule, which the
ring-major marcher now takes from the same file.

**Which leaves what is sampled rather than how it is projected.** The index is
`(Y >> 22) * 1024 + (X >> 22)` and this port forms `Y * 1024 + X` from the
integer halves of its own 16.16 - the same shape. So the remaining candidate
is the map itself: whether `original_height_map` holds `D1.DTA` in the
orientation the DOS arena holds it, or transposed, mirrored, or offset. A map
read on the wrong axis produces terrain of the right character and the wrong
profile everywhere, which is exactly the signature that survived eight
parameter fits.

Testing that wants a heightmap dump out of DOSBox at a known camera and a
byte comparison against `original_height_map` - the same trick the palette bug
needed, one level down.

## The transfer from the render buffer to the screen, and the column question

`sub_00006FEF`, called from `00006994` and the frame entry `000196C5`, is what
moves the 256x256 render surface at flat `0x40000` onto the VGA page. It is
the routine that answers what a terrain column is worth in screen pixels, and
it was never decoded because nothing had needed the answer before the
silhouette comparison did.

What it sets up:

```
edx = [00019E70] + 0x2011      ; 0x40000 + row 32, column 17 of a 256-byte row
ecx = 0xB6                     ; 182 outer iterations
esi = [000014C4] + 0x39FA      ; the VGA page, 14,842 in
edi = 0x3CC20 + 0xE7E8         ; a per-cell compare array, eax = -1
  inner: ecx = 0x52            ; 82
```

**0x52 is 82, and 82 is the CRTC stride per plane** - the same number
`00015B78` programs and the attract notes already record as "328 pixels". So
the screen is Mode X, four planes of 82 bytes, and the transfer walks 82 bytes
per plane per row over 182 rows. `[ebx*4 + 0x38B22]` is indexed by `ebx`,
which the loop carries as the plane.

~~That is as far as this goes for now, and the open question is stated rather
than guessed: **the terrain's 192 columns land on 328 screen pixels, which is
1.71 pixels per column, not 2.**~~

**SUPERSEDED, and it was wrong.** That inference took `0x52` off *this*
routine, and the paragraph below works out that this routine is the dirty-span
builder rather than the pixel transfer - so the stride it programs was never
the terrain's column rate. The actual transfer is `sub_00007AA0`, and it
settles the ratio by mechanism rather than by arithmetic: it copies each span
twice at the same destination, once through plane mask `0x302` and once
through `0xC02`. In Mode X that puts one source byte on planes 0+1 and the
next on planes 2+3, so **one source byte is two adjacent screen pixels**,
exactly as *The column mapping, end to end* concludes above - 164 of the 192
columns reach the screen, 328 pixels of logical line, and the page-aligned
display shows source columns 16..175 (corrected 2026-09-22). `src/render.s` lays those down
at two pixels each, so the port's presentation geometry needed no change; the
run-length histogram's odd runs are the sprite and HUD layers over the field,
not a fractional column rate.

**And the rest of it says this is not the pixel transfer at all.** It is the
dirty-span builder. `edi` walks a shadow copy at `0x3CC20+0xE7E8` comparing
words against `eax = -1`, `loopne`/`loope` scan for runs that changed, and each
run is recorded as a quad indexed by `ebx`:

| slot | holds |
|---|---|
| `[ebx*4 + 0x38B20]` | the run's length |
| `[ebx*4 + 0x32B20]` | source, `ebp + edx`, into the 256-stride render buffer |
| `[ebx*4 + 0x34B20]` | destination, `ebp + [00019E54]`, into the VGA page |
| `[ebx*4 + 0x3AB20]` | `[ebp*8 + 0x31B30]` |

`ebx` runs to `0x800` - 2,048 spans - and the total lands in `[00019E4C]`.
Something else consumes the list and does the copying. So the original repaints
only what changed, which is the same shape as this port's incremental
composition, arrived at independently.

Two things fall out that correct earlier readings:

- **`0x31B30` is indexed per ROW, not per column.** `ebp` at `000070C8` is
  `[00019E58]`, the row counter, and the stride is 8. The note under *The
  rotated horizon* guessed a per-column pair from the walker's side; it is a
  per-row record, and the walker fills it per row.
- **`inc dh` walks the source row down while `sub [00019E54], 0x52` walks the
  destination up.** That is `screen row = 198 - page row` again, from an
  independent site, and it is the second confirmation of the 1:1 row mapping
  that `PROJ_SCALE`'s note rests on.

What is still not answered is the column mapping, because this routine only
records pointers - the arithmetic that turns a buffer column into a plane and
a pixel lives in whatever consumes `[00019E4C]` spans. That is the next
artifact, and until it is decoded the silhouette comparison cannot be
reconciled: 192 terrain columns over 328 pixels is 1.71 pixels per column and
this port lays down a different number, so each screen column samples a
different bearing and no camera or projection parameter can close the gap.

## The oracle works, and the first thing it measured was a bug

`tools/compare-terrain.py` recorded twelve driven attempts to reach the
developer screenshot through the KYLE / Alt-P key sequence, and the two
reasons it kept failing. The gate does not have to be driven. It can be
removed: `000189C9`, `000189D2` and `000189DB` are the three conditional
jumps between the gate's entry and the `call 000165FD`, and the writer
increments the digits of its own filename at `0001672E`-`00016769`, so
replacing those twenty bytes with a countdown on the now-dead feature byte
makes the game write `SNAP_001.PCX`, `SNAP_002.PCX` and onward, one frame in
N, entirely on its own. `tools/oracle-capture.sh` does that to a copy of the
unpacked executable on a scratch drive; neither `assets/` nor `re/unpacked/`
is touched.

It is accurate. `SNAP_001.PCX`'s DAC read-back matches `BACK.DTA`'s shipped
palette to 0.01 of a component and `SNAP_038.PCX` matches `TPIC.DTA`'s to
0.09, so the `000166FF` read-back and the shift-left-two are faithful.

**And the first frame it was pointed at found a real defect.** The port's
`BACK.DTA` screen differed from the original's own by 6,223 pixels of 76,800.
The cause is one assumption in two places: `src/attract.s` unpacked
`w*h + 769` bytes through the run-length decoder and read the palette out of
the result, and `tools/render-attract-ref.py`'s `load_dta` did exactly the
same. **The `0x0C` palette block is not run-length encoded** - it sits raw in
the last 769 bytes of the file. Feeding it through the decoder turns every
component of `0xC0` or more into a run token and shifts the table down from
there. `BACK.DTA` carries such a byte in **entry 1**, so its palette was wrong
from the second colour on and its logo rendered in horizontal bands;
`TPIC.DTA`'s first is in entry 179 and `RH66SIDE.DTA`'s in entry 225, which is
why those two corrupted only their high indices and still looked plausible.

This is precisely the failure the reference renderer existed to prevent. Its
header says it was written from the disassembly rather than from the 68k "so a
shared mistake would have to be made twice" - and it was made twice, so the
two agreed and the agreement measured nothing. Every "pixel-identical" figure
for the attract screens was port against port.

Reading the tail raw takes the `BACK.DTA` screen to **0 differing pixels of
76,800 against the frame `COMANCHE.EXE` drew of itself**. A corroborating
sign: with the palette correct, `ZOVE.RLE`'s translation into `RH66SIDE`'s
screen palette is 256/256 identity, where the corrupted table made it 227 -
the note in *The attract screens* had already observed that ZOVE "hardly
needs" translating, and it turns out to need none at all.

## The sky, and an index that kept a bit

`SKY2.RLE` is an ordinary bank: `'SG'`, a count word, and at +4 the dword
offset of a `0x0C` palette block - 76,816 for SKY2, exactly where the image
at +16 ends. **The image is not a 320x240 raster** (an earlier version of
this note said it was, and drawing it that way sheared the clouds into
diagonal streaks): the payload is **512 column strips of 150 bytes**,
column major like TANK and HUDS, and the single directory record's width
byte names the strip length, 150. That is the shape the original's
per-column backdrop walker consumes, and the 512-column width is sampling
margin for its roll shear. The DOS loop selects its first strip from the full
view angle and advances one strip per source column. The Falcon walks all 192
source columns, expands the centred visible columns to two-pixel slots, then
transposes the bank row-major at load (`sky_init`). Its palette is **six-bit**,
like every bank's, while `C1.DTA`'s terrain palette is **eight-bit**, and the
two agree on one entry of 256. The port had been drawing the sky's indices
through the terrain's table.

The original resolves that the way it resolves every bank: one VGA DAC, so
`0002B8C5` builds a nearest-colour table and rewrites the bank's pixels into
the installed palette at load. `src/sprite.s:sky_palette_build` keeps the
authored sky bytes but builds the equivalent RGB565 lookup in the active
mission palette; the Falcon has no DAC, but it does not get a second colour
space for the backdrop.

The viewport fill is a separate part of that boundary. DOS seeds the visible
column with colour index 255 before the sourced strip writes its rows. The
Falcon does the same with active palette entry 255, including rows above a
positively pitched strip. Without that seed, the first replay retained the
title page's sand-coloured COMA pixels in those untouched rows.

There is one night-sky-specific source convention at the same boundary. SKY4's
payload is overwhelmingly source index 1; in the DOS first replay that field
continues to show the active viewport colour, while the sparse non-1 marks are
drawn over it. The Falcon therefore binds SKY4 index 1 to active entry 255
after the recovered palette lookup. Treating it as an ordinary near-black
RGB565 colour produced the large dark band that the DOS frame does not have.

Underneath that sat a second defect, and it is the one worth remembering.
`render_clear`'s sky loop doubled the index into `d1` for the word-sized
palette lookup, but cleared `d1` only **once, before the loop**. From the
second pixel on, bit 8 of the doubled value survived `move.b`, so every index
of 128 or more sent the *next* pixel 256 entries past the end of the palette.
Against `colour_palette`, with the rest of the image's data behind it, that
was the horizontal noise across the whole sky; against a table with nothing
but BSS behind it, it was black. The fix is to let the addressing mode scale
the index - `0(a2,d1.w*2)` - so nothing ever writes `d1`'s high bits.

Verified against the asset: in the rows above everything else, every pixel of
the drawn sky equals `SKY2.RLE`'s own image through its own palette, and every
remaining difference lower down is HUD, telemetry, canopy or terrain drawn
over it.

## The attract screens: 328x240, one DAC, and a pan that is an address

The attract cycle's state machine was ported before the surface it paints on
was measured. Four things were wrong at once, and each of them is a fact about
the original that the assets or the listing state plainly.

**The screen is 328x240, not 320x200.** `BACK.DTA` and `RH66SIDE.DTA` measure
328x240 in their own headers, the CRTC row stride at `00015BB7` is `0x52` per
plane - 328 pixels across four planes - and `TPIC.DTA` is 328x**390**, which
is the 240 rows shown plus the 150 the title pan travels. The DOS view is the
left 320 columns of a Mode X page, full height. Letterboxing a 200-row view
into 240 threw away a fifth of every screen and offset the rest by 20 rows.

**The pan is the display start address.** `00015BC9` adds `[00019DC4]` into
the CRTC start, and `00005A79` adds `0x52` to that counter once per tick,
clamped at `0x300C`. Both constants divide by `0x52` exactly: the pan runs row
0 to row 150, one row per tick. Nothing moves in the framebuffer. This port
has no 328-wide page to scroll, so it re-blits from the decoded image at the
pan row, which also erases the overlay - the job the original needs its second
page for.

**The overlay's anchor is bottom-left, and its coordinates are the
self-modified bytes.** `00025880` computes the destination as
`([0002587C] - record.xoff) / 4` for the byte column and
`([00022366] + record.yoff) * 0x52` for the row, then walks **upward** with
`sub edi,0x52`. So `[0002587C]` fixes the left edge and `[00022366]` the
**bottom** row. The cycle writes `[0002587C] = 0xAF` with `[00022366] = 0x4B`
for `ZOVE` (`00005776`, `00005780`) and `0xA0` for `COMA` (`000059ED`), whose
Y then animates: held at `0x5D` until the pan reaches row 93 (`00005A20`
compares `0x1DCA`, which is `93 * 0x52`), stepped by `+2`, clamped to
`[0x5D, 0xF8]`, decremented once per tick after the pan saturates
(`00005A8C`), reversed to `-1` in the last 45 ticks and `-2` in the last 40
(`00005AA7`). The 64-entry bump at `00005985` is added **only** while the
sprite sits clamped at `0xF8`, two ticks per entry - it wobbles the
helicopter, not the pan. Before the gate opens the sprite is not drawn at all.

**One VGA DAC means one palette, so a bank is translated into the screen's.**
The bank palette inside `COMA.RLE` and `ZOVE.RLE` never reaches the DAC.
`0002B8C5` copies it to `[00015F84]`, `0002B949` builds a 256-entry
nearest-colour table from it to the installed palette, and then - the step
that is easy to miss, at `0002B9BA` - **rewrites the bank's entire pixel
payload through that table, in place**, two bytes per iteration to the end of
the data. Only after that does the blitter's plain `rep movsb` land in the
right colours.

The match itself is `0002B820`: weighted squared error, weights **30, 55 and
15**, measured in six-bit DAC space with red and green passed through the
64-entry ramp at `0002B7D0` and blue simply doubled; the per-channel squared
tables are `0002ABD0`, `0002AFD0` and `0002B3D0`, and they hold exactly
`(w*d)^2`. Candidates are scanned 1..254 in order, the first minimum wins, an
exact match stops the scan, and indices 0 and 255 are forced to themselves.

**The animation tick follows the draw.** In the side loop at `0000579A` and
the title loop at `000059ED`, DOS selects the current table entry, calls the
blitter, waits for retrace, reads input, and only then advances the animation
cursor and the pan state before the `LOOP` test. The first side frame is ZOVE
record 0; the first title frame is COMA record 0 over TPIC row 0. The Falcon
publishes the current state and then runs `attract_tick`, preserving that
ordering rather than advancing into the next record before painting.

How much this matters depends on the pair. `ZOVE.RLE`'s palette **is**
`RH66SIDE.DTA`'s divided by four - 224 of its 256 entries agree within one
DAC step - so 227 of its translations are the identity and drawing it raw is
nearly right. `COMA.RLE` is authored against something else entirely, only 4
of 256 entries landing within four units of `TPIC.DTA`'s, and drawn
untranslated the Comanche is coloured noise in the shape of a helicopter.
Index 0 makes the same point in miniature: `(0,63,0)` in COMA's palette,
`(0,0,0)` in TPIC's, and it fills the record's three right-hand padding
columns - a full-height green bar beside the sprite, or the night sky.

`src/attract.s` composes the two tables rather than rewriting the payload -
one RGB565 entry per bank index, already looked up through the screen palette
- which draws the same pixels and leaves `COMA.RLE` intact for the cockpit
that also reads it.

**DTA palettes are eight bits per component - the DAC's six, shifted up by
two.** The screen *writer* proves it: `000166FF` reads all 768 DAC bytes back
through port `0x3C9`, shifts each **left twice**, and stores that behind the
`0x0C` marker it has just written. So a DTA palette component is the DAC value
times four, and going the other way - which is what the match at `0002B820`
needs - is a `>>2`. The measured files agree: `CONSOL1S.DTA` reaches 252 and
`TPIC.DTA` 188, neither of which fits six bits, and `src/console.s` already
read the field as 8-bit. Reading it as 6-bit shifts every component two places
up and wraps red away entirely, which is what mottled the title logo.

The candidate side of the match is built the same way in both places:
`0002B89D` walks the installed six-bit palette at `[0002A380]` into
`[0002A680]`, red and green through the `0002B7D0` ramp and blue doubled -
the exact key form `src/attract.s` stores beside each RGB565 entry.

## The displayed window is not the page (2026-08-27)

Every DOS coordinate that reaches a blitter is a **page** x, and the page is
wider than the screen. The Mode X row is `0x52` bytes per plane - 82 x 4 =
**328 pixels** - and the displayed window is 320, which is 80 bytes. The two
spare bytes are one byte column of margin at each side, so

    surface x = page x - 4

The offset is exactly **one Mode X byte column**, which is why it is 4 and not
some arbitrary number. `PAGE_VIEW_X` in `src/inc/comanche.s` names it.

The authored full-screen images are 328 wide too: `CONSOL1S.DTA`, `TPIC.DTA`
and `BACK.DTA` all carry 327 in their first header word, so their first four
columns are off-screen left and a blit that starts at source column 0 puts the
whole layer four pixels right.

Four independent measurements against a DOS capture agreed on +4 before this
was changed: the SPEED label (page 44, DOS screen 40), the F1 highlight (DOS
71..88 against the port's 75..92, same width), the sight line (page `0xA5` =
165, DOS screen 161), and the console **art** correlated over three
element-free strips. It was not per-element - the whole layer was offset, art
included, which is why elements agreed with each other and not with DOS.

**The surface is RGB565, so this is 4 pixels and 8 BYTES.** Subtract it from
the pixel x before it is doubled into a byte offset; correcting the byte
offset halves it.

The blitters take the page x in three different forms, which is worth keeping
straight: `00025B27` and `00025BB6` as a pixel, `00025C55` as a byte column
(`[0x2587C] >> 2`), and `00025A4D` as a byte offset added to the row base
(`[0x22365]`, so x4 pixels).

`sprite_draw_page` / `sprite_draw_page_opaque` in `src/sprite.s` apply the
conversion for callers holding page coordinates. The menu and screen paths
still call `sprite_draw` directly - their coordinates are page coordinates
too (`0002628E`'s `bl` is an X in four-pixel byte units) but nothing has been
measured there.

## The settings come from COMANCHE.MNU, not COMANCHE.CFG

A correction: this project recorded the CFG as the source of the settings
block at `0x25DD4`. It is not.

`00005566-00005585` parses `COMANCHE.CFG` and sets up **sound**: `[0x53DB] & 0xF`
becomes the port (`<<4`, `+0x200` - `0x220` for the shipped file) and
`[0x53DC] & 7` the IRQ. Its ten digits are `"0132700000"` and none of them
reaches `0x25DD4`.

`00005675` loads **`COMANCHE.MNU`** to `0x25DBC`, so the settings block at
`0x25DD4` is that file at `+0x18`. The shipped 35-byte file's bytes 24..34 are
`'1','0','0','3'` then `'}'` x5 and `'{'` x2, which is exactly what a capture
of the running original reads back; twelve little-endian words precede them.

`000268A5-000268BE` then copies bytes 4..10 into the menu text, **by source
address and not in the order the toggle table lists**:

    [0x25DD8]->[0x266A0]  [0x25DD9]->[0x266A9]  [0x25DDA]->[0x267AC]
    [0x25DDB]->[0x267C1]  [0x25DDC]->[0x267D2]  [0x25DDD]->[0x26767]
    [0x25DDE]->[0x2677A]

so the two joystick entries come last, after the three HUD ones. `0x267AC` is
Artificial Horizon, and the image ships `'{'` (off) there while the shipped
MNU turns it on - which is why the horizon line does not draw from the image's
own bytes.

## Named colours are matched, not authored

`0002AA85-0002AB3F` resolves a set of named colours once, when the mission
palette is installed. Each is the **nearest index in that palette** to an
authored six-bit triple, found by `0002B820`: red and green ramped through
`0002B7D0`, blue only doubled, distance `(30r)^2 + (55g)^2 + (15b)^2`, strict
improvement so the first minimum wins, over the range `[0x2B814]..[0x2B810]`
which a capture reads as 1..254.

The consequence for the port: **`COL_MENU_*` are what DOS asks for, not what
it draws.** Against the attract's np44 palette, measured - `GREY_L` and
`GREY_D` land exactly, `GREY_M` becomes `(1B,1B,1B)`, `BLUE` becomes
`(0F,2F,3F)` and `GREEN` becomes `(0F,3F,0F)`. Anything drawing into a
palette-indexed surface should resolve through `resource_match_colour`; the
direct RGB565 expansions are only right where the port owns the colour
outright.

A transcription trap: the three component stores are **not** written in R,G,B
order. Reading them in listing order swaps green and blue - taking `0x2A378`'s
triple as written gave index 104 against the original's 9. Read the block by
address.

## The MFD bodies, and the target view

`0000D693-0000D6FC` drives both MFD bodies through a six-entry handler table
at `0x19E10`, indexed by the page byte. The table is static content and a
capture reads it back unchanged:

| page | handler  | | port |
|------|----------|--|--|
| 0 | `0x075B0` | the moving map | `mfd_body_075B0` |
| 1 | `0x07710` | upper-slot threat scope, element `0x31` | `mfd_body_07710` |
| 2 | `0x07860` | the target view | `mfd_draw_target_view` |
| 3 | `0x076B0` | '*' goal counters, element `0x38` | `mfd_body_076B0` |
| 4 | `0x07530` | systems diagram and damage overlays, element `0x2A` | `mfd_body_07530` |
| 5 | `0x07690` | key-help panel, element `0x33` | `mfd_body_07690` |
| override | `0x07670` | failed MFD, element `0x32` | `mfd_body_07670` |

All of them are dispatched by `mfd_draw_panel` (`0000D64B-0000D6FC`), which
also carries the held-key map zoom. Record: `analysis/functions/falcon-attract.md`
"MFD bodies".

Between the two bodies `[0x19CA8]` moves by `0x1A` - 26 bytes, 104 pixels -
and comes back off afterwards. Two override tests can replace the chosen
handler (`[0x1AA5]`, `[0x19E3E]`/`[0x19E3F]`); neither fires in the captured
attract, where they read `0xFF`, 5 and 1. `[0x1AA5]` is the key-state byte
for scancode `0x35` ('/') held; the pair are damage-array entries 6 and 7.

**The page bytes are not the image's.** `0x72E6`/`0x72E7` ship as 0 and 1, but
`000063C2`/`000063C9` overwrite them at mission start with 0 and **2**, so the
right MFD comes up on the target view. Measured: a capture at the first
attract replay reads `[0x72E7]` = 2 with the previous-page byte and the dirty
flag both still 0, and the function-key chain sets both of those, so the key
path cannot be what put it there.

`000079F0` transfers the finished view: 20 byte columns x 4 planes = **80 x 44
pixels** at `0x37CE + [0x14C4] + [0x19CA8]`, source stepping `-0x200` per
screen row - two source rows per MFD row - over source rows 162 down to 76.
So `MFD row = (162 - page_row) / 2`. Horizontally the four plane bases are
`+0`, `+0x80`, `+1`, `+0x81` with a source stride of 2, which de-interleaves
as: even MFD x from source column 44 + x/2, odd from 172 + (x-1)/2.

`0001B26C`, the view's marcher, is `0000D950` with four changes: an 80-column
occlusion array, its own horizon at `0x3CB78`, a forward step of
`A[i] + A[i+1]`, a lateral step of `B[i] << 1`, and **samples in column
pairs** - the compares step by two (`[esp+0x3E]` then `[esp+0x3C]`) and the
span writer at `0001C1B0`/`0001C1B4` stores into *both* `[esp+0x3E]` and
`[esp+0x3F]`. Reading the step of two without the paired store gives a striped
picture and a wrong model.

## Targeting: two rings, and a divisor that is not the depth

`00024CC0-00024DFC` projects an object and decides whether it can be a target.
Two readings of it are wrong in ways nothing on screen would show, and a
capture caught both.

**The ring search runs twice over one cursor.** The key is `depth << 3`
(`00024CC7`), and the first pass uses a key pulled `0x1800000` nearer when
that does not borrow. That first ring - the **clip ring** - is what
`00024D06` stores as `[0x22358]`, and it is what the sprite blitter clips
against. The search then *continues from the same cursor* for the unbiased
key, and that second ring is the one whose lateral increment divides and whose
projection page is read. **They are not the same ring** whenever the object is
beyond the bias: the captured frame has clip ring 80 and page ring 81. This
port published the second ring for the clip in both copies of the search,
which clipped models against the wrong ring's silhouette.

**The divisor is the ring's lateral increment, not the object's depth.**
`00024D28` loads `[ebx + 0x19EE4]` and it is still in `ebp` at `00024D87`:

    v = 128 + lateral / (B[page_ring] >> 3)

`v` is therefore a half-scale x centred on 128, not a pixel x. Two independent
checks: the horizon read is `[0x3CB20 + v]` and `0x3CB20` is the `0x3CB40`
array minus 32, so `v = 128` selects entry 96, the centre of 192; and the
designator sits at `2 * (v - 0x2E)`, so `v = 128` gives page x 164 against the
sight centre's page `0xA5` = 165.

Verified against a captured frame with an **off-centre** target - an earlier
capture had one dead centre, where every candidate formula agrees and nothing
is proved. Object 27: lateral -19458571, depth 119499752, so key 955998016,
page ring 81, `B >> 3` = 1212253, giving `v = 112`, and `[0x21BAB] + 0x2E`
reads 112. The designator closes too: `horizon[80]` = 8 with row 76 gives
`~(8+76) - 0x29` = 130, and `[0x21C2D]` reads 130.

The rest of the tail: `[0x21C2D]` is kept only below `0xC8`, `v - 0x2E` must
be above 3 and at most `0xA0`, the object's page row must not be below the
clip ring's silhouette **entry** `v`, and then `[0x21BAB] = v - 0x2E` and
`[0x19D18] = index`.

**Entry `v`, not column `v` - the silhouette carries the same 0x20 bias the
horizon array does (2026-08-31).** `00024DEA` adds `v` to `[0x22358]`, which
is `[0x19E60] + ring*256`, and the marcher archives each ring's 192 finished
columns at `[0x19E60] + ring*256 + 0x20` (`0000F2F1`-`0000F2FF`: `shl edi,8`,
`add edi,[0x19E60]`, `add edi,0x20`, `rep movsd` of `0x30` dwords). So the
source column is `v - 0x20`, exactly as it is for the horizon read through
`0x3CB20`, and the two biases are the same bias. Read out of the original
rather than argued: a `pmemsave` of `[0x19E60]` over 180 rings has exactly
192 non-zero bytes per 256-byte record, at offsets **32..223**, and nothing
outside them. A port that stores only the 192 must therefore index them by
`v - 0x20`; indexing by `v` reads a column 32 to the right. On the captured
frame that is the difference between the original's `133`, which the object's
page row 136 passes, and `168`, which it fails - so the mis-indexed read
rejected the one object the original accepted.

**`v` is the sprite's own destination x, not just a targetability
intermediate (2026-08-31).** `00024D9F` stores it in `[0x22365]`; `0002519D`
recomputes the whole projection for the sprite handler and stores the same
value at `00025274`; and the shared blit tail reaches `0002543A`
`add dl, byte ptr [0x22365]` - so `dl`, the destination byte column, is `v`
plus the record's own hotspot walk. There is no second projection for the
sprite, and none is needed: **`B` is exactly `z/100` for every ring** - `8*z/B`
measures 800.00 across all 180 entries of the captured `MEDIUM.DTL` - so
`v = 128 + 800 * lateral / z_ring` is the same fan the marcher walks, whose
per-column lateral step is `B/2` in its 10.22 accumulator. An object therefore
lands on the terrain column that has its lateral offset, which is what makes
the two projections agree horizontally the way `ring_page_table` makes them
agree vertically.

A port that substitutes a pinhole `half_width * lateral / depth` gets a
different fan: the original's half-fan is 200 surface pixels of lateral per
unit of depth, so a 160-pixel half-width pulls every object toward the centre
by a fifth, growing with the offset, and off the terrain feature it stands on.
Checked in the port's own units over a captured frame, the two agree to about
one column - the residue is the ring quantisation, since `v` divides by the
ring's `z` where the marcher accumulates exactly - while the pinhole was
wrong by up to 50 columns.

**The three fan exits are culls, not skips.** `00024D8A` (`B >> 3` zero),
`00024D93` (`v >= 0xF5`) and `00024D9A` (`v < 5`) all jump to `00024E03`,
which is `pop ebx` / `ret`: it discards the return address of `00024C45`'s
*caller* and returns past it, so the object is not drawn at all. A port that
treats them as "skip the targetability marking" draws objects the original
culls.

**The dividend is `[0x2085C]` as stored, and only `edi` is shifted.**
`00024CC7`'s `shl edi,3` forms the *ring search key*; `esi` is reloaded from
`[ecx*4 + 0x2085C]` at `00024D46` and `00024D84` divides that value
unshifted. Both object arrays are 12.20 - `[0x20A64] >> 20` is the `RANGE`
readout in whole map units - so a port holding them in another fixed point
converts the lateral by that difference alone. This port's are 16.16: the key
is seven left shifts (four to 12.20, three for `shl edi,3`) and the dividend
is **four**. Carrying the key's seven into the dividend makes every quotient
eight times too big, which narrows the accepted band `[5,0xF5)` to a few
degrees either side of dead centre and leaves `[0x19D18]` at zero on almost
every frame.

`0001922C-000192A3` cycles the latch `[0x19D10]` over 1..`0x1E`, skipping
objects whose `0x21BAB` is clear and giving up at the starting index; an empty
latch seeds from `[0x19D18]`. It is driven by the select key or by a pending
count the replay stream ORs into `[0x19DF3]`. `0000D439-0000D45E` drops the
lock when the locked object's `0x21BAB` has gone to zero - the byte is rebuilt
every frame, so a target leaving the screen expires its own lock.

## The object draw walk, and what is and is not a cull

`00024BCB-00024C09` walks all 130 order slots descending and has exactly two
tests: `00024BE8` on the active byte and `00024BF1`'s `js` on the forward
depth. `00024BE1` clears `[0x21BAB]` for every slot it visits, in front of
both. Then it dispatches `[ecx*4 + 0x2003C]`. **There is no range cull and no
fan cull in the walk.** Both exist, but in the shared prologue and at their
own bounds:

- `00024C45`'s first instruction rejects a forward depth above `0x1FFFFFFF` -
  512 map units in 12.20. That bound is structural, not a taste in draw
  distance: `00024CC7` forms the ring-search key as `depth << 3`, which passes
  2^32 at exactly 512 units, so one unit further the key wraps and the search
  returns a near ring for a far object. Measured on a captured frame, an
  object at 669 units came out on ring 97 with size band 2 where the original
  culls it outright.
- The fan cull is `00024D93`/`00024D9A`'s band on `v`, about 50 degrees either
  side, not a 45-degree `|lateral| > depth` test.

## The sprite size band, and the ramp table that is not in the image

`00024D21-00024D3E` divides `0x8000000` by the **ring's** lateral increment
`[ebx + 0x19EE4]`, clamps the quotient to `0x7F`, and stores `127 - index` in
`[0x22354]`. `000253D2` indexes `[eax*4 + 0x1D7EC]` with that and adds
`0x1DBEC` to get a ramp pointer.

**Neither table is in the shipped image.** Flat `0x1D7EC` and `0x1DBEC` hold
code there - an unrolled `rep stosd` clear - and the runtime overwrites both,
so this is a rule-4 case: read them out of the running game or read nothing.
Captured at a flight frame, the offset table is 128 monotonic dwords and the
ramp for `127 - index` is exactly `index + 1` bytes long with its bytes
summing to **64** at every one of the 128 entries. So the ramp resamples a
sprite's 64 native source pixels onto `index + 1` destination pixels, and
`0002543A`/`00025458`'s hotspot walks are that resampling applied to the
record's own anchor. A blitter taking an 8.8 scale reproduces it with
`(index + 1) * 4`.

Because `B` is `z_ring/100`, `2^27/B` is `1600/z_ring` in whole map units -
but the divisor is the **ring's** `z`, not the object's own depth. The two
agree to the ring quantisation near the camera and diverge inside a coarse far
ring.

## The target designator, and the two bank pointers

There are two bank pointers, and which blitter reads which decides which bank
a HUD element comes from:

- `[0x19E90]` - read by `00025880`, `0002590F` and `0002599E`. Captured at a
  flight frame that holds a lock it is `0x3B59A8`, whose SG header declares
  **57 elements**: `CONS.RLE`, the instrument bank.
- `[0x19E94]` - read by `00025B27` and `00025BB6`. That is `HUDS.RLE`.

The designator chain, all of it through `[0x19E90]`:

- `0000D418-0000D428`: a console variant above 5 skips the whole block;
  otherwise this page half's `[ebx*4 + 0x19D1C]` is cleared before the latch
  is even read, so a frame that ends without a lock draws no marker.
- `0000D460-0000D478`: with a valid lock, `[0x19D1C]` takes `2 * [0x21BAB]`
  (the page x) and `[0x19D24]` takes `[0x21C2D]` (the row). Both are indexed
  by `[0x19D87]`, the page half. This is what fills the two tables the map
  previously recorded as "zero until the owning event graph populates them" -
  the owning graph is the target latch, and it fills them every frame there is
  a lock. Captured: `[0x19D1C] = 154`, `[0x19D24] = 119`, latch 26.
- `0000D88C-0000D8A9`: element `[0x19D81] + 1` at page `(0xA4, 0x5A)` through
  `0002599E`. With the weapon byte 0 that is CONS element 1, and it is the
  **centre cross** at the sight - four arms around `(161, 90)` on the Falcon
  surface, verified pixel-for-pixel against the original's own frame.
- `0000D8AE-0000D8F4`: gated only by `[0x19D86] > 5` and the null `[0x19D1C]`.
  `0002590F` saves the page under the marker into element `5 + [0x19D87]` -
  it reads the page and writes the *bank*, programming the graphics
  controller's read-map select - and `0000D350-0000D385` blits that element
  back opaquely at the top of the next frame. That pair is DOS restoring its
  single page; a target that repaints every frame has nothing to do with it.
  Element `4`, drawn transparently at the same x and row, is the marker
  itself: the bright corner-bracket box the original puts over its target.

## Decoded, not ported: the sprite's per-column horizon shear

`000254C4` adds `[eax + 0x3CB20]` to `dh` inside the sprite blitter's column
loop, where `eax` is the same `2 * byte column` index the silhouette read
uses. So an object sprite is sheared by the horizon per column exactly as a
terrain span is - and `000254C2` keeps the **unsheared** row in `bl` for
`000254D9`'s clip, so the shear moves the picture without moving the
visibility test, the same rule the terrain span writer follows.

This port's `sprite_blit` does not shear. It is recorded rather than fixed
because the attract cannot distinguish the two: the original's own
`[0x3CB40]` reads 0 across all 192 columns at a captured replay frame, with
roll and pitch both zero, so every column's shear is zero there. It needs a
capture with a rolled camera before it can be verified.

## Data and format map

## JavaScript reference for the mission-end, menu and damage routines

The executable reference in `jsComanche/` carries these routines from the listing
(2026-10-07); each row's record is a section of `analysis/functions/browser-attract.md`.

| DOS address/range | Role | JavaScript | Record | Status |
|---|---|---|---|---|
| `00028261-000284B0`, `000286F9`, `00028C25` | mission statistics, percentage writer, number formatter | `dos-pilot.js` `missionStatistics`, `percentField`, `formatNumber`; native `debrief_percent`, `debrief_number` | `#mission-end-statistics` | ported; 80 random statistics cases and 4 DOS captures agree; 2026-10-10: 80 fresh number and 80 percentage cases agree on JS and both native CPUs (`tools/check-falcon-debrief.py`), not whole-route certification |
| `0002873D-00028A1F` | every flight's end: object clear, route, pilot record | `dos-pilot.js` `missionEnd`, `pilotRecordWon`, `pilotRecordLost` | `#mission-end-route` | ported; 160 random record cases and a live win and abort agree |
| `00029F36-0002A0FE` | ranking sort and digit refresh, roster layout | `dos-pilot.js` `rosterSort`, `rosterRefreshRanks`, `ROSTER` | `#roster-ranking` | ported; 61 DOS-called rosters agree |
| `00018EE3-00019002`, `000190AB-000190B4`, `000192EE-0001934F`, `00019424-000194DB`, `00026B49-00026B87` | death block, engine, T gauge, tail rotor, object collision, crash response, repair | `dos-damage.js`, entered by `dos-runtime.js` `flightTick` (not the object collision) | `#player-damage-chain` | ported; checked against DOS captures (crash tails, wreck, engine, 37 collision samples); the object collision is not entered by the browser flight |
| `0002A1AD-0002A299`, `0002A2F8-0002A31C` | mission list scan, mission file decode | `dos-menu.js` `scanMissionList`, `decodeMissionImage` | `#mission-list-scan` | ported; DOS-called on 42 files |
| `00028F3F-00029033`, `00026E90` | row colours, choice store, lock | `dos-menu.js` `missionRowColours`, `missionListChoice` | `#mission-list-gate` | ported; 60 + 50 DOS-called cases agree |
| `00029038-00029119`, `0002A29A` | briefing wrap, line skipper | `dos-menu.js` `buildBriefing`, `skipLine` | `#mission-briefing` | ported; 60 DOS-called wraps agree, the original's four-line screen reproduced |
| `00028B37-00028C20` | Your Stats text | `dos-menu.js` `yourStatsScreen` | `#menu-your-stats` | ported; 30 DOS-called cases agree |
| `00026AB6-00026E8F` | options toggles, Game column | `dos-menu.js` `optionsToggle`, `optionsGameAction` | `#menu-options-game` | ported; the toggles DOS-called (28 cases), the Game column Unproven |
| `0002800C-000281FE`, `00001BE8-00001BFA` | new-pilot name entry, key FIFO | `dos-menu.js` `nameEntryKey`, `createPilot`, `keyFifoPush` | `#pilot-name-entry` | ported; 36 scripted sessions of the real routine agree |

Function recovery should update the appropriate durable document when it
establishes a resource format, structure size, fixed-point field, table, or
global-state contract. Keep full disassembly listings, memory dumps, original
assets, and generated binaries in their ignored locations; this document
contains addresses and conclusions only.

## Sound driver (2026-10-07)

The music and FM driver is recovered and proven in JavaScript only (`jsComanche/dos-sound.js`, checked against the original by
`tools/check-js-sound.js`); no Falcon source yet - the 68030 interface is specified in `analysis/functions/sound-driver.md`, section 10.
The **digital effect layer** is on the Falcon since the same day: `src/sound.s`, its call sites and its verification are in
`analysis/functions/sound-falcon.md`. Records of the JavaScript routines: `analysis/functions/browser-attract.md#sound-driver-core`
and its siblings.

| DOS range | what | JavaScript | Falcon | status |
|---|---|---|---|---|
| `0002B9CF-0002B9F2`, `0002BB01-0002BBF1` | command entry and the commands (effect, select, pause, resume, query, volume, detect) | `command`, `cmd*` | `snd_fm_command` (empty interface) | proven; Falcon pending |
| `0002BBF2-0002BC7B`, `0002BC8B-0002BCE9`, `0002BF12-0002BF87` | the 65 Hz tick, key on/off, silence, patch load | `musicTick`, `keyChannel`, `silence`, `loadPatch` | none | proven |
| `0002BD00-0002BEEF`, `00015E6E` | song start/stop, event reader and sequencer, KRL0/KRL1 loader | `startMusic`, `readEvent`, `sequencer`, `decodeMusicFile` | loader: `snd_bank_load` (banks only) | proven |
| `0002BB09-0002BBBA`, `0002D408` | FM effects | `cmdEffect`, `effectHalf` | none | proven |
| `0002C1B8-0002C431` | OPL2 device | `oplInit`, `oplPatch`, `oplNote`, `oplPitch`, `oplDetect` | none | proven |
| `0002BF88-0002C1B7` | MPU-401 device | `mpu*` | none | proven (bytes) |
| `0002C432-0002C481` | PC speaker device | `speaker*` | none | proven (port values) |
| `00004EA2-00004F6D` | start a sample on a slot | `stageSample` | `snd_start` | ported, byte-exact |
| `00004F6E-00004FBA` | stage a sample as the slot's next (the rotor loop) | `stageVoice` | `snd_voice` | ported, byte-exact |
| `00004E26-00004E86` | speech cues (SPEAK0, SPEAK1) | `speech` | `snd_speech_a`, `snd_speech_b` | ported, byte-exact |
| `00004E8E-00004EA1` | effect from SND1 (FM fallback at `00004E87`) | `digitalEffect` | `snd_fx` | ported, byte-exact |
| `000050B4-000051B6` | reset | `resetMixer` | `snd_reset` | ported, byte-exact |
| `00004E0C-00004E25` | dither mask | `setRate` | `snd_rate` | ported, byte-exact |
| `00005220-000053D5` | the mixer fill | `fill` | `snd_fill` | ported, byte-exact (233,472 DOS bytes) |
| `00004FE4-000050AF` | mixer mode (start/stop) | - | `snd_mode` | ported; the SB start/stop is the DMA path (platform) |
| `00004FBB-00004FCF`, `00005528-000055AF`, `00006B28-00006B2A` | DET, start-up (CFG, MODE, RATE), exit | - | `snd_det`, `snd_init`, `snd_shutdown` | ported; DET is the Falcon's sound lock |
| `00004142-000041B7`, `00004A0A`, `00004C0A` | the mixer's initial state and curves | image bytes | `snd_mixer_init` | equal to the image |
| `000267F3-0002687C`, `00026CE3-00026D2B` | apply settings (sound half), the live radios | - | `snd_apply_sound`, `snd_apply_settings`, `menu.s` `.radio` | ported; music half pending |
| `00001F49`, `00002050`, `00001FBC` | the Sound Blaster's DSP, IRQ and time constant | - | `snd_dma_open/start/stop`, `snd_vbl`, `snd_resample` | N/A - platform replacement |
