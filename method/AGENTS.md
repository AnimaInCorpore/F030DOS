# F030Method agent guide

`METHOD.md` is the governing shared porting policy for the projects in the
`README.md` manifest. Read the relevant method sections before changing policy
or applying it to a port; use `DEPENDENCIES.md` for shared dependency ownership.

## Route-scoped analysis

For each slice, preserve the recovered DOS function inventory but prioritize
deep analysis by the active route's transitive dependency closure
(`METHOD.md` §0.1–§0.3). The inventory is an accountability map, not a demand to
finish whole-game analysis before delivering a slice. Do not exclude a path
because one trace missed it; tie exclusions to the selected build and
configuration, and close every dependency that can execute in supported scope.

## Mandatory executable reference

Follow `METHOD.md` §4.3a: **DOS execution → recovered contracts → DOS-validated
JavaScript reference → native m68k implementation of the same contracts**.
JavaScript is the executable semantic reference in the middle. It is not the
behavioral authority, a required Falcon runtime, or a compulsory code generator.
The hashed DOS executable and captured execution settle every disagreement.
Preserve numerical and byte-order semantics explicitly. A supported target game
function requires its JavaScript counterpart and the shared DOS contract
fixtures; hardware adapters follow the method's explicit Target artefact rule.

## Ground-truth function IDs

Every ported function uses its canonical DOS function name as the shared ID
across records, JavaScript/m68k annotations, route manifests and fixtures
(`METHOD.md` §4.2). For stripped code, use the established disassembly symbol
tied to the hashed build and verified entry. Implementation names are aliases;
target-only adapters are explicitly N/A and must not acquire invented DOS IDs.

## Shared policy propagation

Edit canonical policy in `METHOD.md`. Put the transferable rule in
`gen_cross_project.py`, then regenerate the master and all child ledgers with
`python3 gen_cross_project.py`. Do not edit generated copies directly.
Run `python3 gen_cross_project.py --check` after propagation. Preserve existing
work and each port's local scope; shared reference policy does not change its
minimum hardware target or claim its implementation verified.
