# UW2.EXE subsystem map

What the named functions add up to. Every address here is a **file offset**
and every entry is backed by an instruction quoted in
`work/ghidra_export/symbols.txt` (tier 1 = read and verified). Nothing in this
file is inferred from a name alone.

Conversion: image `seg:off` → file `0x2E00 + (seg<<4) + off`; Ghidra flat →
file `− 0xD200`; runtime linear → file `− delta` (delta is per-boot,
`0x2F50` on the calibrated run). **Only valid below file `0x71B80`** — above
that is the overlay pool, which has no fixed mapping (`ghidra.md` §14).

## Graphics

| what | where |
|---|---|
| blitter, runs with `ES=0xA000` | segment `0x0085` |
| VGA library far entries | save `SS:SP` to `cs:[0x43f0]/[0x43f2]`, switch to stack `0x372c:0x4fa8` |
| `gfx_select_bitmap` = `0x85:0x48f4` | `0x07F44` |
| `gfx_clipped_rect` | `0x08342` |
| clip window | `[0x3df4]`, `[0x3df6]`, `[0x3df8]`, `[0x3dfa]` |
| bit-depth expanders (8bpp+xlat, 5bpp, 4bpp, 4bpp+xlat) | `0x065C:0x7F0C` trampoline, 6 doors |
| 32 auxiliary 16-entry palettes | `ALLPALS.DAT` → `DGROUP:0x6732` |

## Sprites / display slots

64 records of 16 bytes in segment `0x5f1c`: flag word `+0`, x `+2`, y `+4`,
w `+5`, h `+7`, layer `+9`, shape `+0x0b`.

| | |
|---|---|
| `sprite_set_shape` | `0x02EEB` |
| `sprite_mark_dirty` | `0x03029` |
| `sprite_flush_lists` | `0x03130` |

## Mouse cursor

Nested hide depth `[0x26c]`, drawn flag `[0x26e]`, position `[0x268]/[0x26a]`,
extents `[0x2300] [0x2302] [0x2384] [0x238e]`, 4-deep id stack `[0x23be]`
indexed by `[0x282]`.

| | |
|---|---|
| `cursor_hide` / `cursor_show` | `0x1E7B7` / `0x1E7CD` |
| `cursor_redraw` | `0x1E76B` |
| `cursor_set_bitmap` | `0x1EE3C` |
| `cursor_stack_pop` | `0x1EDA6` |

The full cursor function records, asset evidence and browser difference ledger
are in [`analysis/functions/cursor.md`](functions/cursor.md).

The input boundary is a separate contract from cursor drawing. Static and live
DOS evidence show that this build reads the pointing device only through
`INT 33h` subfunctions `AX=0` (reset/detect), `AX=3` (position/button status),
and `AX=0x0B` (motion counters); no raw mouse IRQ path is present. A browser or
Falcon adapter must emulate those driver-visible calls and let the recovered
consumer drive cursor position, hit testing and state flow. It must not turn a
DOM click directly into a menu result. The keyboard driver/consumer contract
for the current browser slice is not yet recovered, so browser keyboard
navigation is `Unproven` and remains outside the supported game path. Graphics
and sound backends are the explicit hardware-substitution exceptions; this
does not relax input or game-flow fidelity.

## Objects

1,024 records: indices 0–255 are **27 bytes** at far ptr `[0x2578]`, 256–1023
are **8 bytes** at `[0x25a6]`. A reference is a 10-bit index in bits 6..15 of
a word. Word 0 bits 0..8 = item id (512 types, `COMOBJ.DAT`). Current object
far ptr `[0x2246]`. Byte `+9` = coarse angle, word `+0x0b` = goal / target,
byte `+0x15` bits 0..5 = animation state.

| | |
|---|---|
| `obj_ptr_from_word` / `obj_ptr_from_index` | `0x2C2F9` / `0x2C3AC` |
| `obj_index_from_ptr` / `obj_link_from_word` | `0x2C362` / `0x2BFC7` |
| `obj_create` | `0x33C2F` |
| `npc_set_heading_dir8` / `npc_set_anim_state` / `npc_set_goal` | `0x189D9` / `0x18954` / `0x1BA8F` |

## Level

64×64 grid of 4-byte cells at far ptr `[0x188c]`; the whole level buffer is a
32,264-byte `LEV.ARK` record (`data-formats.md`).

| | |
|---|---|
| `grid64_cell_ptr` | `0x33BFA` |
| `level_buf_alloc` / `level_grid_copy_in` / `level_buf_layout` | `0x927C0` / `0x927F7` / `0x2BA41` |

## Conversation VM

42 opcodes, `ghidra.md` §11. Memory `[0x4704]`, stack `[0x46fc]`, fn-ptr array
`[0x470e]`, code `[0x471e]`, IP `[0x471a]`, SP `[0x46fa]`, frame `[0x4726]`.

| | |
|---|---|
| `conv_load` / `conv_parse` / `conv_vm_run` | `0x74E15` / `0x75863` / `0x75A95` |
| `conv_register_builtin` / `conv_init_fnptr_array` | `0x765E6` / `0x75A12` |
| `conv_mem_read` / `conv_stack_read` | `0x765A7` / `0x765D0` |
| `conv_publish_vars` | `0x7DD53` |

## Overlay manager

`ghidra.md` §15. Code segment `0x35FF` (file `0x38DF0`), data segment `0x63BA`
(file `0x669A0`), pool base global `[0x114]`, `exeinfo` table at `DS:0x01A0`.

| | |
|---|---|
| `ovl_int3f_handler` / `ovl_load` | `0x392D9` / `0x39389` |

## Sound

| | |
|---|---|
| `play_sound_effect` / `play_positional_snd` | `0x21635` / `0x214D3` |
| `ems_map_page` (`INT 67h AH=44h`, handle `[0x22c0]`) | `0x1E3BE` |

Assets live in EMS-backed extended memory, **not** conventional RAM — a
signature hunt through the first megabyte finds nothing (`qemu-boot.md`).

## Borland runtime

`fopen 0x11D1C`, `fclose 0x1199D`, `fseek 0x11F27`, `ltoa 0x131BE`,
`strcpy 0x13DB1`, `strcat 0x13D13`,
`farmalloc 0x14864`, `farfree 0x1477E`, `near_free 0x14C00`,
`heap_alloc 0x74626`, `heap_free 0x747BE`, `rand 0x12307`,
`isqrt32 0x2506F`, `dos_error_to_errno 0x13147` (errno `[0x96]`).


## Overlay call resolution

Pool code far-calls as `lcall V:off` where **V is a byte offset into the FBOV
`exeinfo` table** at file `0x66B40`, not a segment: `seg = u16 at 0x66B40 + V`,
`file = 0x2E00 + (seg<<4) + off`. 95% of the pool's 4,269 call sites resolve to
a function entry, an INT 3Fh stub or a prologue. Tool: `work/ovl_resolve.py`.
Decode in `ghidra.md` §19; supersedes the "cannot be mapped statically" note in
AGENTS.md.

## Graphics module — segment `0x0085`, file base `0x3650`

Hand-written assembly, entered only through **50 stack-switching thunks** that
move `DS`/`ES`/`SS` to data segment `0x372c` (file `0x3A0C0`) and run on the
private stack `0x372c:0x4FA8`, saving the caller's `SS:SP` in the code segment
at `cs:0x43F0`. Twenty dispatch again through a 40-entry near-jump table at
`cs:0x5278` (file `0x88C8`). Full map in `work/gfx_api.txt`; decode in
`ghidra.md` §18.

`gfx_select_bitmap 0x7F44` (thunk) -> `gfx_jumptable 0x88C8` ->
`gfx_select_bitmap_impl 0x67E5`. `gfx_clipped_rect 0x8342` -> body `0x6A6E`
direct. `gfx_blit_8arg 0x5824` is the widest entry (8 word slots).

Rendering target is **VGA Mode X**, 320x200 unchained planar at `0xA000`
(`ghidra.md` §24) — row stride 80 from `[0x36a8]`, plane masks expanded from the
static 4-byte seeds `0f 0e 0c 08` and `01 03 07 0f`. Dispatch is one clipper
(`gfx_clip_and_dispatch 0x58E6`) plus twelve inner loops selected through
`[0xdc2]` (§22). Eleven of the twelve loops are still unread.

## Timer service — segment `0x223b`, file base `0x251B0`

A hand-written assembly module, position-independent (no relocations between
`0x25190` and `0x25C82`) with its own BSS, its own 512-byte interrupt stack and
a `"Test"` stack canary at `cs:0x1B0`. Full decode in `ghidra.md` §17.

`timer_isr 0x255BA` (INT 8, `cs:0x40A`), `timer_install_int8 0x256D4`,
`timer_uninstall_int8 0x25720`, `timer_set_divisor 0x25750` (PIT ch0, mode 3),
`svc_resolve 0x2556A`, `svc_call 0x255A2`, `svc_call_code_0x64 0x25C78`.

This timer service is the DOS game-flow timing authority for the port. The
browser and Falcon runners must preserve its captured divisor, per-tick
increment, slot periods, drift-free accumulator subtraction, and the proven
position of input polling and frame publication. A monitor/VBL refresh rate or
an assumed 60 Hz value is not a substitute for these runtime values. The
current Falcon 60 Hz choice is a presentation target only; the exact DOS
cadence and its relationship to display refresh remain `Unproven` until
captured from a controlled DOS run.

Seventeen scheduler slots: 16 registrable (`svc_resolve` rejects index `>=
0x10`) plus slot 16 reserved, pre-wired by the installer to `cs:0x51D`. Each
slot holds a far callback + its `DS`, a state word (`2` = armed), and a u32
accumulator/period pair. The ISR adds `cs:0x114` to every armed accumulator and
fires on overflow, **subtracting the period rather than zeroing** — so the
schedule is drift-free.

Reached by **103 static far calls** from a contiguous caller region
`0x1F6xx`–`0x228xx` at ~40 distinct entry offsets, almost all passing a context
handle from DGROUP `[0x2b6]` or `[0x2b8]`. Twenty entry points share the
prologue `push ds/si/di; pushf; cli`, some behind a `push bp; mov bp,sp` frame.

Periods and the PIT divisor are runtime state — the port must read them from
the DOS oracle, not assume them. The structure above is static and portable.
