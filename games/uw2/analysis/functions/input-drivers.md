# DOS input-driver boundary

Updated 2026-08-25. **Mandatory rule for every port:** run the authoritative DOS
function and feed/read it through the same emulated DOS keyboard and
pointing-device I/O contract. Do not invent input semantics or improve the game
flow; graphics and sound are the only broad mechanism exceptions. This record
defines that boundary for every
browser, host and Falcon slice. The hashed DOS executable and its captured
execution remain authoritative. Physical device packets and browser events are
only transport inputs; game logic must see the recovered DOS driver results.

## Pointing-device client

| Field | Record |
|---|---|
| DOS identity | `UW2.EXE` recovered client routines in the `0x3133` module: reset/detect entry `0x247F8`, motion-counter entry `0x24817`, position/button entry `0x24833`; the `INT 33h` instructions are at `0x24806`, `0x2481A`, and `0x24836` in `work/reasm/out/uw.asm`. |
| Recovered calls | Reset/detect clears `AX`, calls `INT 33h`, and tests `AX`; motion calls `AX=0x000B`, consumes `CX:DX`, scales both axes through the following helper; state calls `AX=0x0003`, returns the button bits from `BX & 3`. |
| Driver evidence | `analysis/qemu-boot.md` exhaustively finds exactly these three mouse subfunctions and no raw mouse fallback. `work/mouse_driver.asm` implements the DOS-oracle driver and records the verified `AX=0`, `AX=3`, and `AX=0x0B` contracts. |
| Browser counterpart | None in the current canvas runtime. The browser port has no mouse driver, pointer transport, or DOM click path; this DOS contract remains analysis evidence. |
| Status | **Identified; excluded from the current display slice.** A future connected game-flow port must implement this boundary before mouse input can affect state. |

The DOS-side driver currently used by the oracle is itself a test-environment
driver, not a claim that the retail disks shipped `MOUSE.COM`: the boot record
states that no genuine driver was present and that `work/mouse_driver.asm` was
added to make the oracle controllable. Its I/O contract is valid evidence for
what the executable asks of `INT 33h`; packet decoding and hardware setup remain
target/host mechanism details behind that contract.

The driver source clamps absolute position to `X=0..639`, `Y=0..199`. The
640×400/1280×800 screenshot geometry used by the visual fixtures is separate
from those driver units; relative QEMU movement was measured against the
screenshot, but the choice consumer's final coordinate conversion is not
promoted until its DOS code is recovered.

## Keyboard client

| Field | Record |
|---|---|
| DOS identity | `fn_24358` at recovered entry `0x24358` in `work/reasm/out/uw.asm`; the routine performs BIOS `INT 16h` function `AH=1` (check) and, when a key is available, `AH=0` (read), returning the BIOS `AX` word; otherwise it returns zero. |
| Runtime evidence | The live boot notes prove the main menu ignores keyboard navigation. The name field later accepts keyboard input, so the full caller/consumer coverage is not yet complete for character creation. |
| Browser counterpart | `browser/uw2-input.js`: `queueKeyboardEvent` converts the browser transport event to a standard PC BIOS AX word; `bios16` and `keyboardRoutine24358` implement the recovered queue and wrapper. |
| Status | **Identified; BIOS queue boundary implemented.** The recovered game consumer and DOS timing/order remain Unproven; no browser key changes game state. |

## Mandatory flow and difference ledger

```text
physical/browser device → emulated DOS driver/I/O contract
                         → recovered DOS consumer → authoritative game flow
```

- **Grounded:** function identity, call numbers, return registers, and the
  observed mouse-only main-menu behavior above.
- **Target artefact:** browser event objects, Falcon device reads, and the
  standard PC set-1-to-BIOS-word conversion used to reach the same
  driver-visible values.
- **Graphics/sound exception:** Canvas/Videl and audio backends may replace
  their hardware mechanisms after their logical contracts are recovered.
- **Unproven:** any direct browser keyboard navigation, unrecorded driver
  subfunctions, timing not covered by a DOS fixture, or a direct DOM-event to
  game-state shortcut. Such behavior cannot enter a supported path.

## Timing boundary

Input delivery is ordered by the authoritative DOS timing service, not by the
browser's event arrival or monitor refresh. The recovered `INT 8` PIT scheduler
and its runtime divisor/slot periods are recorded in
`analysis/subsystems.md` and `analysis/ghidra.md` §17. The port must preserve
the proven position of mouse/keyboard polling, motion-counter clearing,
acknowledgement, and consumer execution within that schedule. The current
browser fixture cadence is presentation-only; exact DOS input/game-flow
cadence remains `Unproven` until captured from a controlled DOS run.

The current browser input module intentionally exposes only the recovered BIOS
keyboard queue and `fn_24358` wrapper. It has no mouse dispatcher, unsupported
subfunction path, or browser-side game consumer. See
`analysis/functions/translation-policy.md`.
