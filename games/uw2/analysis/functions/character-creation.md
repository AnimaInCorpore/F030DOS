# Character-creation entry slice

Updated 2026-08-25. This is a DOS evidence record, not a supported browser
slice. The canvas runtime deliberately does not display captured character
screens or expose a fixture entry into this flow.

The live DOS oracle reaches:

`main menu → Create Character → Choose character sex → Male/Female`

and continues through handedness, class, skill, portrait, difficulty, name,
confirmation, and the 3D starting room. The browser must not claim any of
those transitions until the recovered DOS consumers, input ordering, drawing
side effects and timing are connected.

## DOS evidence

The live oracle is documented in [`analysis/qemu-boot.md`](../qemu-boot.md).
The main menu is mouse-only, and the full observed flow is driven through the
emulated DOS `INT 33h` boundary plus keyboard input for the name field.

| Stable record | DOS identity and range | Recovered purpose | Status |
|---|---|---|---|
| `uw2_character_create_entry` | `FUN_CODE_TAIL__07bb2d`, file `0x07BB2D–0x07BB4A`, 30 bytes | Calls `FUN_CODE_TAIL__07a280(1)`, invokes `FUN_CODE_TAIL__07b8a4`, then calls `func_0x2344`; returns the character-creation result. | Recovered; browser invocation Unproven. |
| `uw2_character_create_run` | `FUN_CODE_TAIL__07b8a4`, file `0x07B8A4–0x07BB2C`, 649 bytes | Allocates creation records, loads `chrbtns`, `skills.dat`, and `chrgen.dat`, builds choice entries, and calls the choice-screen routine. | Recovered and observed in DOS; not in the browser runtime. |
| `uw2_character_choice_screen` | `FUN_CODE_TAIL__07b2f8`, file `0x07B2F8–0x07B533`, 572 bytes | Prepares and renders a choice screen, samples mouse selection, and returns the selected result. | Identified; exact drawing, timers, allocation, cursor and return side effects remain Unproven. |
| `uw2_character_main_menu_boundary` | DOS startup/menu evidence at `main` `0x088940` and `game_loop` `0x088B3F` | Establishes the mouse-only menu boundary. | Observed in DOS; no supported browser entry. |

The exact recovered wrapper shape is retained because the function boundary
matters more than an instruction-shaped rewrite:

```c
undefined1 FUN_CODE_TAIL__07bb2d(void) {
    FUN_CODE_TAIL__07a280(1);
    uVar1 = FUN_CODE_TAIL__07b8a4();
    func_0x00002344();
    return uVar1;
}
```

The disassembled/decompiled source is retained in
[`work/ghidra_export/uw_c.c`](../../work/ghidra_export/uw_c.c), and
`work/symbols.py` emits the stable names used by this record.

## Browser boundary

The captured character fixtures remain analysis assets only; no character module
is present in the browser runtime or loaded by `browser/index.html`. The
supported browser runtime contains only the canvas display and the keyboard
transport boundary:

```text
browser keydown → BIOS AX word → emulated INT 16h queue → recovered consumer
```

No browser event calls a character-selection helper, changes a character field,
or enters this DOS flow. The next function-level slice is the
recovered DOS choice consumer, followed by handedness and the remaining
creation states.
