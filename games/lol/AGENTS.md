# F030LOL — working rules

## Goal

Disassemble and understand the DOS game *Lands of Lore: The Throne of Chaos*
well enough to port its observable behaviour to an Atari Falcon030. The
project is reverse-engineering-only until the original executable’s runtime
model and Falcon seams are grounded.

## Source and derived data

- `assets/LOL_CD_001.iso` is the supplied source image. Never modify it.
- `game/cd/` is an exact ISO extraction and remains a pristine reference tree.
- `work/install/` is a derived English DOS install staged from the CD.
- `work/` contains regenerable listings, DOS images, probes and scratch.
- `analysis/` contains measured facts and one document per format or runtime
  component. Record `RESOLVED`, `IDENTIFIED`, `PARTIALLY RESOLVED` or `TBD`.

## Disassembly rules

1. Parse the MZ header and every relocation before widening code coverage.
2. Keep the 0x21300-byte MZ load image separate from the 0x33985-byte appended
   region until its loader/overlay contract is demonstrated.
3. Treat `DATA/ENG/LANDS.EXE` and `DATA/HARDRIVE/MAIN.EXE` as distinct linked
   variants. Compare them; do not silently substitute one for the other.
4. Add indirect targets to `re/seeds.txt` only with evidence and a note in the
   relevant analysis document.
5. A re-encodable byte range is evidence of encoding, not automatically
   evidence that the range is code; guard proven data regions.
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

1. Continue the Borland runtime and resident code/data boundary work into the
   first live resource-loading path; the startup family is already identified.
2. Use the DOS oracle to observe startup and one menu transition with XMS.
3. Continue EMC2 work from the established wordcode/control-flow invariants:
   recover dynamic call targets and Lands of Lore system-call signatures before
   Falcon implementation. The BLEND consumer and exact palette operation are
   now resolved in `analysis/blend.md`.

## Cross-port documentation rule

When a change or investigation establishes a confirmed finding, correction,
tool/workflow lesson, or other fact that can help more than this repository,
update the authoritative shared documentation in the same session and
regenerate any derived copies. Always do this; do not leave transferable
findings only in chat, code, or generated output. Keep project-specific details
in the local canonical document and upstream the reusable rule with its
evidence, scope, and status.
