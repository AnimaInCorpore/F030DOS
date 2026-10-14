# Browser DOS file boundary

Updated 2026-08-25. This is a target/host boundary record, not a claim that
the browser implements a DOS disk, FAT, directory manager, or file driver.
The DOS executable and captured execution remain authoritative for the file
operations used by the connected cutscene functions.

## Boundary contract

| Field | Record |
|---|---|
| DOS identity | File-handle behavior used by `cutscene_run` (`0x828E3`) and `cutscene_load_lback` (`0x83150`); no separate browser-side DOS function is claimed. |
| Browser implementation | `browser/uw2-fs.js`: `normalizeDosPath`, `open`, `read`, `seek`, `tell`, `close`; `browser/uw2-reference.js`: `hostLoader`, `readDosFile`. |
| Connected files | `D3\CUTS\LBACK000.BYT`, `D4\CUTS\CS000.N01`, `D4\CUTS\CS000.N02`, and `D4\CUTS\CS000.N12`. |
| Status | **Target artefact / Ported for the connected display slice.** |

The semantic boundary is named byte files with independent integer handles.
Paths are normalized to DOS-style uppercase names. `open` starts at position
zero; `read` copies at most the requested bytes and advances the position;
`seek` supports origins 0, 1, and 2 and clamps to the file; `tell` returns the
position; `close` releases the handle. The implementation keeps source bytes
in `Uint8Array` form and copies them at the boundary so the decoder cannot
mutate the cached source file.

## Host modes

The adapter supports two modes:

- `mode: "memory"` is the clean headless/test mode. It uses only JavaScript
  `Map` instances and disappears on reload.
- `mode: "persistent"` is the interactive browser mode when IndexedDB and
  WebCrypto are available. IndexedDB stores the imported bytes in a versioned
  database; localStorage stores only the path/size/source-variant/SHA-256
  metadata index. The current page selects this mode by default and can select
  memory mode with `?fs=memory`.

Persistence is entirely behind `uw2-reference.js` and `uw2-fs.js`. The semantic
cutscene code never calls `fetch`, IndexedDB, localStorage, File APIs, or a
browser clock. A cache hit and a host import expose the same byte stream and
handle semantics. The host loader maps only the four connected resources; it
does not provide directory enumeration, file creation/deletion, attributes,
timestamps, FAT/sector emulation, or save-game storage.

## Difference ledger

- **Target artefact:** host `fetch` imports source files; DOS disk sectors and
  filesystem internals are not emulated.
- **Target artefact:** resident `Uint8Array` bytes replace DOS disk/EMS storage
  for this display slice.
- **Target artefact:** IndexedDB persistence is an interactive cache only; it
  cannot change the imported source bytes or game behavior.
- **Unproven/out of scope:** malformed paths, invalid handles, directory
  operations, DOS error return conventions, file locking, and save files are
  not part of the connected browser path.
