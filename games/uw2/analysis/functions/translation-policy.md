# Function-level translation policy

This is the UW2 application of `F030Method/METHOD.md` §4.2c. The hashed DOS
executable and controlled DOS execution remain authoritative. A browser or
Falcon function counterpart must preserve the recovered DOS function as
closely as the evidence permits; it is not a place to improve, sanitize, or
reinterpret the original.

## Mandatory rule

The function body contains recovered DOS behaviour only. Do not add error
checking, assertions, validation, clamps, default values, retries, logging
branches, or early returns unless the DOS function demonstrably contains that
behaviour. If the original has no error handling, the counterpart has no
invented error handling either.

Preserve fall-through, return values, widths and signedness, wrapping and
overflow, side effects, ordering, and the original result for unsupported or
invalid inputs where that result is known. If a malformed or unrepresentable
case cannot be reproduced safely, mark it `Unproven`/`Unsupported`; do not add a
new semantic branch and call it parity.

## Where checks belong

| Layer | Permitted checks | Fidelity rule |
|---|---|---|
| DOS-function counterpart | Only checks present in the recovered DOS function | Must not change valid DOS outputs or add a new error path |
| Host/target boundary | API, memory-safety, endian, alignment or resource checks required by the platform | `Target artefact`; must be outside the semantic function and documented |
| Build/fixture/parity harness | Assertions, hashes, invariant checks, diagnostics and failure reports | May reject a test; must never alter the function result or game flow |

For example, `browser/uw2-cutscene.js` and `browser/uw2-reference.js` may
reject a truncated imported file at the host parsing boundary so the browser
does not crash. Such a rejection is not evidence that the original DOS game
performed the same check and must not be copied into a recovered game-function
counterpart without DOS evidence.

Every difference belongs in the function record's ledger. “No added handling”
is a valid and important result; defensive convenience is not.
