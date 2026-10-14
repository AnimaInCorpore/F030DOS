# Poland scenario route

Status: `PARTIALLY RESOLVED`. The unchanged unpatched DOS executable can be
driven from boot through the main menu and standalone Poland selection to the
first tactical map. The file-open boundary and selected resources are measured;
scenario decoding, complete callback closure and rendering contracts remain
unproven. No JavaScript or Falcon source is justified by this witness alone.

## Selected scope and reproduction

Inputs retain the executable, MS-DOS 6.22, no-sound configuration and pinned
CuteMouse 2.1b4 `/P` identities in [executable.md](executable.md). The scenario
uses the untouched menu's default difficulty and controls. The host sends only
keyboard and PS/2 motion/button input; it does not write game state.

```text
python3 work/drive_menu.py --hdd work/qemu_out/pg-mouse.hdd \
  --out work/qemu_out/poland-verified --script work/routes/poland.json \
  --seconds 50 --trace --open-files
python3 work/test_menu_route.py
```

Use a fresh output directory for every run. The recorder rejects an existing
directory, checks the executable hash, and uses QEMU `-snapshot` so the source
disk remains unchanged. `route.json` retains actual event times, input script,
host tool, executable, source disk, QEMU and plugin hashes, checkpoint hashes,
file requests, emulator return status and evidence limitations.

Validated on macOS/QEMU 11.1.2, `pc`, `486`, 16 MB and standard VGA, with the
shared `F030Method/dos/trace/x86trace.so`. The broad plugin logs are retained
but reach their 400,000 DOS-call limit through polling: they are **truncated**
and cannot establish a complete ordered resource history. The independently
bounded file-open probe below records the selected menu-to-map window. Its
breakpoints perturb wall time; event timestamps are a reproduction schedule,
not recovered DOS game timing or instruction-phase frame parity.

## Observable checkpoints

The committed schedule is `work/routes/poland.json`. Space at seconds 6, 9 and
12 advances startup to the main menu. PS/2 motion `(96,-32)` puts the cursor
over the `S` button; the press/release opens standalone scenario selection.
Motion `(-154,34)` selects Poland; `(0,69)` reaches Start Scenario. These are
measured device inputs under the pinned driver's acceleration, not pixel
coordinates or a portable mouse-motion formula.

The checkpoints retain the screen, all 16 MB physical RAM and CPU/segment
registers while QMP has the guest stopped:

| Checkpoint | Scheduled second | Observed result |
|---|---:|---|
| `main_menu` | 15 | Start Game / campaign and scenario controls |
| `scenario_menu` | 19 | Standalone scenario list and difficulty/control options |
| `poland_selected` | 23 | Poland highlighted; September 1, 1939 briefing text |
| `poland_briefing` | 28 | European map with Germany-to-Poland arrow |
| `axis_turn` | 34 | Initial Axis turn transition (display phase can vary) |
| `poland_tactical` | 43 | Tactical hex map, units, Prestige 228 and Fair weather |

The long interactive discovery and repeated fixed schedules independently
reached the tactical map. This establishes reachability; it does not recover
all displayed state producers or prove every screenshot phase identical.
`CAPTURED` means the script, required file-request sequence and artifact gates
completed. It does not mean function parity or Falcon support.

## File-open boundary

The checked entry is file `0xB026C`, runtime `0x1D4FC8` in these captures,
with delta `+0x124D5C`. Its prefix `53 51 52 56 57 83 EC 0C` is validated
against the selected executable before arming the breakpoint at `main_menu`.
The caller's return address is `[ESP]` and the filename pointer is `[ESP+4]`:
five pushes and twelve local bytes make the later load at `0xB0274`
(`mov esi,[esp+0x24]`) read that same argument. These captures use flat
protected-mode CS/DS/SS bases, with paging disabled; this is not a generic
segmented-address probe.

The listing then skips leading spaces (`0xB0278..0xB027E`), combines access
flags and invokes `INT 21h`, AH=`0x3D`, at `0xB029E`. The probe records the
entry request, not the DOS return handle, error or successful read size.
It removes the breakpoint, steps the first instruction and reinstalls it
before continuing, so repeated requests execute rather than stopping forever
at the same PC.

Observed order after main-menu arming:

| Request | Caller return address | File offset of return |
|---|---:|---:|
| `..\dat\scenstat.bin` | `0x1D3073` | `0xAE317` |
| `..\dat\game001.scn` | `0x1D3073` | `0xAE317` |
| `..\dat\map01.set` | `0x1D3073` | `0xAE317` |
| `..\dat\map01.stm` | `0x1D3073` | `0xAE317` |
| `..\dat\axarrow1.shp` (twice) | `0x1D4FC2` | `0xB0266` |

Return addresses are interior call-site evidence, **not function IDs**.
The expected request sequence is checked in the schedule. Other file-opening
paths, resources preloaded before arming, failed opens and reads are not ruled
out by this one boundary witness.

## Resource identities

These are exact base-distribution files, kept pristine in `game/DAT/`:

| File | Bytes | SHA-256 |
|---|---:|---|
| `SCENSTAT.BIN` | 7000 | `5b0c86f7d8004b7716359f4c396bf2e2785ccf469ef1577ebca7edac6e9ba67b` |
| `GAME001.SCN` | 447 | `783e96a812fd4e52632492b5c5f9e26485d1d21833f3aab3eb4913a3aacb683a` |
| `MAP01.SET` | 2139 | `e7cf7386bedf879b1bc04c0d1d1c74d1639b0ed9766e3d4fa007b9604c63f1ff` |
| `MAP01.STM` | 576 | `e63b056d2ab471ef2202ad989deb1c6425cef691c635b264df6b7e9b136ac83f` |
| `AXARROW1.SHP` | 1442 | `077e77924c8d220652c9dca2e669b760258ba0e1192b516ff0714df379412a50` |

`MAP01.SET` also contains literal names `..\dat\tacmap.shp`,
`..\dat\tacmap.tgf` and `..\dat\map01.stm` near its beginning. These are
static resource references, not proof that this probe saw those reads. Record
them in the loader's dependency closure before implementing it.

## Next discriminating measurement

Successful open returns and all selected raw resource bytes are now captured
and checked in [scenario-loader.md](scenario-loader.md). The entry-only
witness above remains its own earlier evidence grade.

The selected next slice is the DOS Poland loader, connected to this verified
menu route. Continue from the measured successful handles/reads to decoded
destination state, and map each
`GAME001.SCN`/`MAP01.SET` field to the instruction that consumes it. In
particular, settle how the TACMAP families are loaded or reused. Retain the
complete reached-function inventory and indirect callbacks; only then build
the JavaScript decoder/reference fixtures for this closure and carry them to
m68k. Tactical rendering, moves, attacks, turn completion and other scenarios
remain unproven, with no exclusion claim based on this trace.
