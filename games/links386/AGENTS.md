# F030Links386 — working rules

## Goal

Disassemble and understand *Links 386 CD* well enough to port its observable
behaviour to an Atari Falcon030. The project is reverse-engineering-only until
the original executable's runtime model and the Falcon seams are grounded.

## Source and derived data

- `assets/Links 386 CD (1995)(Access Software).iso` is the supplied source
  image. Never modify it.
- `game/cd/` is an exact ISO extraction and remains a pristine reference tree.
- `work/install/` is the minimum installed tree staged from `INSTALL.INI`.
- `work/` contains regenerable listings, DOS images, probes and scratch.
- `analysis/` contains measured facts and one document per format or runtime
  component. Record `RESOLVED`, `IDENTIFIED`, `PARTIALLY RESOLVED` or `TBD`.

## Disassembly rules

1. Parse the MZ header and relocation table before widening code coverage.
2. Keep the 0x2C524-byte MZ image separate from the 0x5D747-byte appended
   region until the DOS/4G loader contract is demonstrated.
3. Treat the MZ entry as 16-bit startup code. Do not infer a protected-mode
   origin from the first string or from an unrelocated operand. The first
   executable audit found a `DOS/4G` banner at file `0x122A2`, but that banner
   does not by itself resolve the appended payload.
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

1. The startup trace now reaches the identified MZ EXP-loader path
   (`0x26C61` -> `0x2832B` -> `0x28AB8`), including EXP 0's separate DX
   runtime block, selector allocation and load-image descriptor checks. Prove
   which callback/return contract carries that state into the final
   selector-backed transfer to EXP 1's `EIP=0x7F064`.
2. Determine the exact role of EXP 0 and the runtime stub in the protected-mode
   startup chain, including how the `[0x1BD6]` offset used by the `0x3447`
   dispatch path is populated.
3. The `10049` failure is a fault recursion, and the fault is now attributed
   to the **oracle**, not to the game. `0xC2C136` executes
   `mov ds, cs:[0x3F8]`; the fault entry `0xC2C99F` repeats the same load 18
   more times, each nested fault taking one entry off the interrupt-stack free
   list at `DS:0x1A6C` until `0xC2B71F` jumps to the fatal handler. Measured
   with `work/watch_mirror.py`: nothing writes linear `0xC2A3F8` after extender
   startup, the slot holds the correct `0x0010` at the faulting instruction,
   and a `Z3` read watchpoint shows the load dereferencing **linear `0x3F8`**
   — IVT vector `0xFE`, whose offset word `0xFF53` is exactly the `#GP` error
   code `0xFF50` once the RPL bits are masked. `work/segtest/` confirms the
   cause in isolation — a 512-byte boot sector, no DOS, no extender: QEMU
   11.1.1 drops the **`CS`** override on a data reference when `DS`/`ES`/`SS`
   bases are all zero, and a controlled `FS`-versus-`CS` pair with identical
   bases isolates the override register as the only difference. So `10049` is
   an oracle defect, not a Links 386 property. It is decided per execution (not
   cached), and the archived Windows-QEMU capture shows the identical fault
   chain, so no nearby release is known good. Patching the game is ruled out:
   a diagnostic build replacing all 25 `mov ds, cs:[0x3F8]` sites removes the
   `10049` — which closes the causal chain — and then dies on
   `push dword cs:[0x3F8]` at `0xC357E3`, one of ~130 CS-override references
   in the extender. **Get a correct oracle before working behind the gate**
   (`work/segtest/UPSTREAM.md` is a ready-to-send report; run `work/segtest/`
   as the acceptance test on any candidate emulator), and until then treat
   everything past the mouse gate as unmeasured. Do not reopen the `INT 28h`/`IDT[0x28]` line: those samples are
   V86/EMM386 state at the DOS prompt after the game has exited. Do not
   re-derive a memory value from a `#GP` error code; read the address.
4. Decode one resource or course record and document its format before porting.

## Cross-port documentation rule

When a change or investigation establishes a confirmed finding, correction,
tool/workflow lesson, or other fact that can help more than this repository,
update the authoritative shared documentation in the same session and
regenerate any derived copies. Always do this; do not leave transferable
findings only in chat, code, or generated output. Keep project-specific details
in the local canonical document and upstream the reusable rule with its
evidence, scope, and status.
