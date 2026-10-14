# F030MagicCarpet — working rules

## Goal

Disassemble and understand the DOS game *Magic Carpet* (Bullfrog Productions,
1994; Magic Carpet Plus distribution, 1995) well enough to port its observable
behaviour to an Atari Falcon030. This project is reverse-engineering-only until
the original executable's runtime model and the Falcon seams are grounded.

## Source and derived data

- `assets/Magic_Carpet_Plus_1995.zip` is the supplied source archive. Never
  modify it.
- `game/` is an exact, reproducible archive extraction and remains a pristine
  reference tree.
- `work/` contains regenerable listings, DOS images, probes and scratch.
- `analysis/` contains measured facts and one document per format or runtime
  component. Record `RESOLVED`, `IDENTIFIED`, `PARTIALLY RESOLVED` or `TBD`.

## Disassembly rules

1. Parse the MZ header and all six MZ relocations before widening code
   coverage.
2. Keep the 16-bit MZ loader image (`0x60..0x2992`) separate from the appended
   Watcom LE payload (`0x2998..EOF`). Do not feed the LE payload to a 16-bit
   decoder or assume that its file offset is its protected-mode address.
3. Treat `CARPET.EXE`, `HIDDEN.EXE` and `SELECT.EXE` as separate linked
   variants. Use `CARPET.EXE` as the primary target; compare the other two
   only when a difference is measured.
4. Add indirect targets to `re/seeds.txt` only with evidence and a note in the
   relevant analysis document.
5. A re-encodable byte range is evidence of encoding, not automatically
   evidence that the range is code; guard proven data and LE tables.
6. Run the original under the DOS oracle and compare observations with static
   analysis before naming game subsystems.

The shared method and technique ledger are authoritative:
`../F030Method/METHOD.md` and `analysis/cross-project.md`.

## Mandatory function-level port policy

When porting starts, the hashed shipped DOS executable and its captured
execution are the sole behavioural authority. Reassembly, decompiler output,
a recovered source tree, the browser reference, and 68000 code are evidence or
implementations; none may overrule DOS. For every function represented in
browser or target code, maintain the `METHOD.md` §4.2 function record: DOS
identity and evidence, recovered contract and fixtures, browser/target symbols,
and an explicit difference ledger against DOS. Record and prove even “no
difference”; an unresolved difference is `Unproven` and cannot enter a
supported path. Start the deterministic browser reference with the first
function; use its controlled experiments to identify function roles, contracts,
side effects and Falcon seams, then confirm each finding against DOS before
recording it. Land its fixtures before or with each supported target slice.
## Implementation-source links

Every JavaScript/browser and 68000/m68k function source that implements or exposes a recovered DOS function must carry an adjacent comment or docstring linking to the durable function record and naming the disassembled DOS function symbol plus canonical range/entry (for example, `DOS: FUN_0000_1234; record: <stable-function-record>`). Use the same stable function ID in both implementation sources; a separate map or file-level comment is not enough. Code with no DOS counterpart must say `N/A - platform replacement` or `Target artefact` at the definition.


## Current next steps

Reviewed 2026-10-10 against `analysis/executable.md`, `qemu-boot.md` and
`resources.md`; this is a documentation review, not a fresh DOS capture.

1. Preserve the resolved Watcom LE object/page-map and fixup arithmetic and
   measured protected-mode placement. Resolve demand loading and the remaining
   internal fixup's runtime meaning; do not reintroduce guessed flat origins.
2. Supply the required DOS mouse driver and capture the next original
   title/menu transition beyond the measured mouse-driver check.
3. Recover the connected game route and its required function contracts before
   beginning JavaScript/native gameplay. No port runtime exists yet.
4. Extend the already-decoded screen/palette/font/sprite/animation families into
   the resource consumers needed by that route; level/game semantics remain open.

## Cross-port documentation rule

When a change or investigation establishes a confirmed finding, correction,
tool/workflow lesson, or other fact that can help more than this repository,
update the authoritative shared documentation in the same session and
regenerate any derived copies. Always do this; do not leave transferable
findings only in chat, code, or generated output. Keep project-specific details
in the local canonical document and upstream the reusable rule with its
evidence, scope, and status.
