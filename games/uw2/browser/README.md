# UW2 browser port

This directory contains one browser target: a 320×200 canvas displaying the
recovered Ultima Underworld II intro framebuffer.

The runtime is limited to the port path:

- `uw2-fs.js` — DOS file open/read/seek/tell/close boundary with clean
  in-memory mode and a host-only IndexedDB persistence mode.
- `uw2-reference.js` — maps the connected DOS cutscene files to their source bytes.
- `uw2-cutscene.js` — LPF/ANIM decoding and indexed framebuffer presentation.
- `uw2-input.js` — browser key to BIOS AX-word transport and recovered keyboard poll.
- `uw2-game.js` — intro frame scheduler and canvas presentation.

The browser DOM contains only the canvas. Browser keys are queued as BIOS words;
there is no browser pause, restart, menu, character screen, cursor, fixture,
asset viewer, or diagnostic path. The current connected intro has no recovered
DOS consumer that reads the keyboard routine, so queued keys do not alter the
display.

The decoded frames are flattened into a deterministic presentation timeline.
`requestAnimationFrame` only selects which pre-decoded frame to show; it is not
the DOS simulation clock. The connected slice uses a labelled 180–240 ms
presentation cadence, not recovered DOS timing.

The page uses persistent mode when IndexedDB and WebCrypto are available. It
stores imported bytes in a versioned IndexedDB database and path/size/source
variant/SHA-256 metadata in localStorage. `?fs=memory` selects the clean
headless/test mode; that mode uses only in-memory `Map` instances and disappears
on reload.

The source boundary is:

```text
browser keydown → BIOS AX word → emulated INT 16h queue
                                      ↓
                         recovered DOS fn_24358 (0x24358)
```

Open `http://127.0.0.1:8765/F030Underworld2/browser/` from a server rooted at
`C:\Arbeit`. The loader reads only the connected `CS000.N01`, `CS000.N12`,
`CS000.N02`, and `LBACK000.BYT` source files. The file-boundary record is
[`analysis/functions/file-boundary.md`](../analysis/functions/file-boundary.md).
