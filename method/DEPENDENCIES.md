# Dependencies of the porting workflow

This is the operational companion to `METHOD.md` §0.1, §0.3 and §6.1. The family
manifest remains `gen_cross_project.py`'s `TARGETS`; this document defines how
to use dependencies, not another project register or an installed-version list.
Each game keeps its active slice and dependency records in its existing port
plan, using [templates/port-slice.md](templates/port-slice.md) where useful.
Keep the recovered-function inventory broad, but record dependency readiness
for the active route's transitive closure; inventory entries outside that
closure are not automatically slice dependencies.

## Ownership and validation boundaries

| Dependency | Authority / owner | Consumer check |
|---|---|---|
| Port policy | `F030Method/METHOD.md` | Review the active slice against the relevant gates; no copied policy fork |
| Technique ledger | `F030Method/gen_cross_project.py`, `BODY` and `ADOPT` | `python3 gen_cross_project.py --check` from F030Method |
| Shared DOS harness | `F030Method/dos/`, the four files in `dos/sync.py`'s `SHARED` | `python3 dos/sync.py`, then the affected game's build/boot/capture check |
| Execution telemetry | `F030Method/dos/trace/` | Build against the actual QEMU plugin API and validate a known executed range, address mapping and output flush; see `dos/trace/README.md` |
| Shared flag/checkpoint/profile analysis | `F030Method/validation/` (import in place) | `python3 -m unittest validation.test_validation`; validate each consumer's graph/trace adapter and retain independent DOS gates; see `validation/README.md` |
| Game installation, launch and probes | Each game's builder, launcher and analysis tree | Rebuild from identified media and replay its documented route with the required settings |
| Source media, DOS, BIOS/TOS and emulator images | Locally supplied inputs and their provenance records | Hash and identify the actual selected files; retain a reproducible staging recipe |
| Host analysis and target build tools | The selected installation or source checkout | Record executable/version/build options and run the relevant parser, assembly or linking check |
| Optional translators, lowering rules and runtime helpers | The game's pinned provider and evidenced per-build rules | Reproduce generated sources/maps; validate each changed rule with DOS → JavaScript → native fixtures, helper ABI checks and the affected connected route (METHOD.md §2.6, §4.3b) |
| Browser, Falcon and optional DSP adapters | The consuming game's implementation and substitution list | Contract fixtures plus connected-route replay on the declared target |
| Code or tools borrowed from a sibling | The named provider repository and revision | Verify the consuming game's own format/ABI/behaviour fixtures before adoption |

The trace tools are invoked from their master location; they are deliberately
outside `SHARED`. Per-game `build_dos_hdd.py` and `set_boot_mode.py` are local
and are never synchronized. A tool borrowed from `F030Arcade/third_party/`,
for example, does not make F030Arcade a member of the DOS-port family or permit
the family sync to manage it.

## A reproduction record for each active slice

Record dependencies actually needed for this slice, with their transitive
build/run requirements. A recovered-function inventory is not a dependency
list, and a function count does not establish readiness. Do not install every
tool in the family just because it appears in another game's notes. Each record
needs:

- a stable dependency ID, provider/path, consumers and required capability;
- a source revision or artifact SHA-256, local patches/dirty-file hashes, and
  the command that resolves or builds it;
- host OS/architecture, executable path/version and relevant options; for an
  emulator, machine/CPU, memory, device and timing settings; for QEMU plugins,
  the header/API and plugin build identity as well;
- a validation command, working directory, input hashes, expected invariant,
  actual result, date and evidence location;
- status: `missing`, `available-unvalidated`, `validated for <scope>`,
  `blocked`, or `stale`, with the next action for any nonvalidated requirement.

For a git provider, `git -C <provider> rev-parse HEAD` and
`git -C <provider> status --short` identify the baseline and whether it has
local changes. A commit ID alone cannot reproduce dirty or untracked inputs;
retain the relevant patch/content hashes. Preserve supplied media outside
source commits according to each project's rules. For mutable guest disks,
record the base image and staging recipe, then capture from a fresh working
copy or record the exact save/configuration state that makes replay possible.

Check the command name used by the consuming script as well as interpreter
availability. Comanche's Bash build calls `python`; a host with only `python3`
needs the explicit adapter recorded in `F030Comanche/tools/README.md`. Record
that launch environment with the build, rather than assuming an interactive
shell alias is available in a child script. This is a host mechanism boundary,
not a change to game semantics.

Keep artifact lineage alongside the results: media → installed/unpacked
executable → loader map → capture → canonical fixture → browser/target result.
Record converter revision/options, source hashes and target/format tags on
caches. A changed source, map, capture setting or converter makes dependent
results stale until rechecked. Keep previous fixtures as evidence; never
regenerate expected DOS output from the implementation being tested.

## Reuse across games without inheriting assumptions

Reuse the smallest proven capability. UW1's `FBOV` experience is a useful
starting point for UW2, but each build still supplies its own directory,
relocations, fixtures and runtime calibration. L386's P3/EXP records are not
Watcom LE objects simply because both games contain a DOS/4G string. The
ledger records both examples; the container and address model select the
adapter, not the family name.

Before sharing a helper, name its input/output contract, error behaviour,
widths/endianness, ownership and supported variants. Keep game-specific
addresses, assets and policies in explicit per-game data/adapters. Validate
the original consumer and a second intended consumer before calling an
extraction reusable across those games. Until then it is a local candidate,
not a new dependency every sibling must adopt. A new generalization does not
justify broadening scope or weakening a known-data guard.

F030CT and the other SNES ports are external technique providers, not members
of `TARGETS`. Their 65816 frontend, memory map, interrupt scheduling and renderer
are not DOS dependencies. Record any borrowed component separately, including
dirty-file hashes: a design note copied from an older sibling is not evidence
that the current checkout includes its fixes. Keep diagnostics and generated
output tied to the exact linked build; a stale map can misidentify the writer
of the first differing byte. Shared generation never makes the generated
implementation an independent oracle for its own expected fixtures.

Keep recovered game-function identities and per-build evidence even when
implementations share a helper. A source reconstruction from another build
can accelerate reading; it cannot supply the consuming DOS build's authority
(`METHOD.md` §4.2). Optional sound, networking or DSP work becomes a prerequisite
only where the declared route and target contract require it. Existing
project-specific target requirements remain binding.

## Change a shared dependency in a reviewable order

1. **Inspect before writing.** Check git status in the provider and affected
   consumers. From F030Method, run `python3 gen_cross_project.py --check` and
   `python3 dos/sync.py`. Diff every unexpected mismatch and upstream local
   corrections before regenerating or pushing.
2. **Define the impact.** Name changed contracts, affected consumers, the
   reproducing failure and their smallest relevant checks. Fix the master,
   preserving the fixture that demonstrates the failure. Documentation-only
   changes need regeneration/link/diff checks, not emulator runs.
3. **Validate the provider and an affected consumer.** For a harness fix, run
   the failure reproduction and a representative existing boot/capture path.
   For an interface change, update its adapters and fixtures together. A tool
   reporting its version or files matching byte-for-byte is not a runtime test.
4. **Propagate from the owner.** Regenerate ledgers with
   `python3 gen_cross_project.py`; synchronize changed harness masters with
   `python3 dos/sync.py --push`. These commands write across the registered
   workspace. Review their destination lists first and preserve unrelated local
   changes. Do not run the push merely to make a check green.
5. **Close the consumer results.** Rerun both drift checks and the affected
   consumer checks. Record provider revision/hashes, consumer revisions and
   results together in the change note. Name consumers that could not be
   exercised as `available-unvalidated` or `blocked`; copy equality is not
   validation. Retain the prior dependency identity and evidence for a targeted
   rollback, then rerun affected checks if a rollback is needed.

### What the current preflight does and does not prove

`gen_cross_project.py --check` checks all registered ledger paths, including
missing ones. Its write mode creates destination directories: do not use it
to infer that a missing checkout has been restored. `dos/sync.py` checks the
first seeded harness location (`work/` before `tools/dos/`) in each existing
registered project. If a project has both locations, inspect both and establish
which its builder imports before an update.

The harness check reports an existing unseeded project as `absent` without
failing; it does not report a missing project directory. It also does not test
per-game builders, tool availability or guest execution. Review every `TARGETS`
member needed for the work explicitly, including whether the checkout and
required media exist. An active route that needs an absent oracle is blocked
even when the family drift checks exit zero. Seed it only after reviewing the
destination and filling in the game's own launcher/memory requirements. Keep
unrelated unavailable projects visible without blocking independent slices.
