# F030ICR — working rules

## Goal

Disassemble and understand the DOS *IndyCar Racing* v1.05 build well enough to
port its observable behaviour to an Atari Falcon030. The DOS executable and
captured execution remain the authority; no port is claimed until the runtime
model is grounded.

## Source and derived data

- `assets/` contains the supplied floppy images. Never modify them.
- `game/` is the exact extracted/install tree and is derived.
- `work/` contains regenerable listings, DOS images, probes and scratch.
- `analysis/` contains measured facts and one document per format or runtime
  component. Record `RESOLVED`, `IDENTIFIED`, `PARTIALLY RESOLVED` or `TBD`.

## Disassembly rules

1. Preserve disk boundaries and record hashes before extracting or installing.
2. Establish the game executable from the launcher and runtime; do not select
   `UCC.EXE`, `SD.EXE` or `INSTALL.EXE` by name or size alone.
3. Parse the executable container and relocations before widening code coverage.
4. Add indirect targets to `re/seeds.txt` only with evidence and a note in
   the relevant analysis document.
5. Treat a re-encodable byte range as encoding evidence, not automatically as
   code; guard proven data regions.
6. Run the original under the DOS oracle and compare observations with static
   analysis before naming game subsystems.

The shared method and technique ledger are authoritative:
`../F030Method/METHOD.md` and `analysis/cross-project.md`.

## Port policy

When porting starts, the hashed shipped DOS executable and captured execution
are the sole behavioural authority. Reassembly, decompiler output, browser
models and 68000 code are evidence or implementations; none may overrule DOS.
For every represented function, maintain the `METHOD.md` §4.2 function record,
including DOS identity/evidence, recovered contract and fixtures, implementation
symbols, and an explicit difference ledger. Unresolved differences are
`Unproven` and cannot enter a supported path.

## Cross-port documentation rule

When a change establishes a transferable technique, correction or workflow
lesson, update `../F030Method/gen_cross_project.py` in the same session and
regenerate the copies. Keep project-specific facts in `analysis/`.

