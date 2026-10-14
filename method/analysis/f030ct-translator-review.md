# F030CT translator: lessons for the DOS-port strategy

Reviewed 2026-09-27. The strategic change is to automate repeated recovery and
translation work inside a proven route, with source-mapped failures and
independent comparisons. Canonical policy is in [METHOD.md](../METHOD.md)
§0.4, §2.6, §4.3b, §4.5a and §4.6a; this note records the evidence behind it.
F030CT remains an external SNES technique provider, outside the DOS-family
manifest. No CT source, game media, runtime or hardware requirement is adopted.

## Inspected version and verification

- F030CT HEAD: `cf3d3c832b2397840d98f5d53b5fc7e949bc9867`, with local changes
  in the translator, runtime, renderers and notes, and untracked comparison
  tools. The file hashes below identify the inspected versions; HEAD alone
  does not describe this working tree.
- Disassembly submodule: `eeae27acdb6565e96d1d796a3d60792c250c0aa1`.
- Normalized U.S. v1.0 ROM SHA-256:
  `06d1c2b06b716052c5596aaa0c2e5632a027fee1a9a28439e509f813c30829a9`.
  Media stays in its existing untracked location.
- New execution check: read-only ROM loading and `listing.parse_diz`, which
  completed in about one second. Result: **105,374 placed instructions, 4,590
  labels, 12,878 symbols; 88,199 byte-backed entries and 17,175 untraced entries;
  zero placement warnings**. The untraced entries do not acquire verified
  widths from this result. CT's prose records an older 17,170 count.
- Translation, gameplay, timing and renderer results discussed below are
  reported in CT's notes; they were not rerun or independently certified in
  this review. `analysis/translator.md` is explicitly an inherited SMK design
  document. CT-specific evidence is in `analysis/ct.md` and the current code.

Reproduce the placement check from `../F030CT` with the locally supplied ROM:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import hashlib
from tools.smkx import __main__ as M, listing
rom = M.load_rom(M.ROOT / 'assets/Chrono Trigger (USA).zip')
lst = listing.parse_diz(M.LISTING, rom)
print('ROM SHA-256:', hashlib.sha256(rom).hexdigest())
print('placement:', {
    'instructions': len(lst.insn_at), 'labels': len(lst.labels),
    'symbols': len(lst.symbols),
    'byte_backed': sum(i.traced for i in lst.insn_at.values()),
    'untraced': sum(not i.traced for i in lst.insn_at.values()),
    'warnings': len(lst.warnings)})
PY
```

## What transfers

| Evidence in F030CT | Consequence for the DOS method |
|---|---|
| [listing.py](../../F030CT/tools/smkx/listing.py), `parse_diz`, checks listed bytes, opcode and length against ROM; lines without byte evidence are marked untraced. | Machine-check placement and preserve evidence grades. A readable listing is not an authority for ambiguous decoding. |
| [analyze.py](../../F030CT/tools/smkx/analyze.py), `Ctx`, `State`, `canon`, carries widths, bank, direct page and stack effects through calls and exits. [CT's direct-page account](../../F030CT/analysis/ct.md#direct-page) reports analysis shrinking from roughly 580,000 to 140,000 nodes when ordinary D values became runtime state. | Track the DOS mode, segment/overlay and calling context that actually changes behaviour; keep varying data dynamic when equivalent. A context cap must never discard a supported successor. |
| [Per-site dispatch](../../F030CT/analysis/ct.md#pointer-dispatch-targets-per-site) replaces bank-wide target seeding. [ctx_seed_loop.py](../../F030CT/scripts/ctx_seed_loop.py) maps a runtime miss back to its source site and appends its target. | Make unresolved edges actionable by site and context. In DOS ports, the automatic append becomes a candidate record pending original-code/execution validation: a faulty port can compute a wrong target. |
| [The short-table failure](../../F030CT/analysis/ct.md#jump-tables-cut-short-the-attract-battles-stop-2026-09-25-night) read 12 of 122 battle entries and 5 of 57 enemy-AI entries. [tables.txt](../../F030CT/tools/smkx/tables.txt) records corrected extents with reasons; [table_audit.py](../../F030CT/scripts/table_audit.py) surfaces suspects, including empty tables. | Establish table extents from consumers, producers and bytes. Interior labels and handlers hidden in data blocks must not silently truncate the graph. Heuristic audits generate questions, not proofs of the final extent. |
| [emit.py](../../F030CT/tools/smkx/emit.py) emits unsupported-operation stops; [smkx_pc.py](../../F030CT/scripts/smkx_pc.py) maps linked offsets through generated labels to original addresses. [__main__.py](../../F030CT/tools/smkx/__main__.py) fixes Python's hash seed and emits coverage/unsupported reports. | Prefer bounded native lowering where it saves transcription. Require deterministic inputs/output, complete source maps, explicit residual work and diagnostic boundary stops; retain the separate DOS-validated semantic JavaScript reference. |
| [Code in WRAM](../../F030CT/analysis/ct.md#code-in-wram), `PATCHED_CALLS`, overlay checks and coroutine stack regions handle executable bytes and continuations that are not static ROM calls. | Record code lifetimes, patch producers, possible variants and non-local control flow. Validate the whole translated code instance or its write/invalidation scheme; checking eight entry bytes alone is insufficient. A small interpreter also needs its own behavioural evidence. |
| [The reference-interpreter finding from SMW](../../F030CT/analysis/porting-notes.md#from-f030smw-2026-09-24-evening-a-reference-65816-the-carry-bug-liveness-is-safe-after-all) describes checkpoint sums → RAM diff → writer watchpoint → routine. It corrected an earlier attribution of a carry-merge bug to flag liveness. | Localize the first divergent state before changing the suspected subsystem. Keep discriminating rule fixtures and compare conservative/optimized mechanisms. CT's inspected `liveness.py` still conservatively keeps all flags at escaped/unknown returns; SMW's precise-liveness result is not a measured CT result. |

For x86, the transferable structure is a verified decode/context graph,
contract boundary, native lowering and differential harness. The 65816
register map, bank rules, return conventions and SNES I/O scheduler need new
DOS-specific recovery. Reusing their constants would repeat the very mistakes
the automation is intended to remove.

## What the success reports do not establish

[The latched-scanline investigation](../../F030CT/analysis/ct.md#the-latched-scanline-and-the-page-cache-2026-09-25-late-evening)
records missing characters and stalled scripts even though snapshots matched
the project's C renderer. Rendering port-produced state correctly did not
establish that the game produced the correct state.

[The independent snes9x comparison](../../F030CT/analysis/ct.md#snes9x-as-the-reference-2026-09-27)
then exposed animation/main-loop drift.
[The longer attract replay](../../F030CT/analysis/ct.md#a-whole-attract-cycle-the-nmi-in-step-with-the-main-loop-2026-09-27)
reports that previous 12,800–14,000 port-frame tests reached only about game
frame 5,900. A subsequent 32,000-port-frame run reached game frame 18,989 in
the second cycle, and all 123 captured pictures matched the internal renderer.
Only 44 of 77 non-flat comparisons were within the independent comparison's
1% pixel criterion. The notes still identify snapshots whose memory and
registers came from different times, palette limitations and a missing effect.

[s9x_compare.py](../../F030CT/scripts/s9x_compare.py) searches nearby frames and
tolerates channel differences up to 8/255. This is useful diagnosis, but it
cannot satisfy the DOS method's aligned state and exact canonical-output gate.
CT's main-loop/NMI synchronization and forced interrupt after eight lag VBLs
also need their own original-system timing evidence; neither becomes a DOS
timing policy. Count completed semantic transitions and compare coherent
checkpoints, including failed or unmatched ones.

Likewise, `ctx_seed_loop.py` returning zero can mean a frame limit, timeout or
another stop without a dispatch miss. Its exit status is not a support gate.
CT's finite target sets, table guards and opcode fallbacks improve diagnosis;
absence of a trap in one run does not prove closure over a supported scope.

## Adoption order

1. On the active DOS route, make a coherent original checkpoint and its
   semantic JavaScript fixture the first acceptance boundary. Preserve the
   existing minimum target and cumulative connected-flow requirements.
2. Add the missing context/dispatch/code-instance records and map failures to
   canonical DOS function IDs. Automate placement, reports and fixture replay
   before considering a new compiler framework.
3. Pilot native lowering only on a bounded, evidenced routine or repeated
   idiom. Assemble for the declared CPU, execute the same DOS fixtures, and
   measure whether the pilot saves manual work within its resource budget.
4. Expand the verified route; optimize a measured cost using the retained
   conservative result and first-divergence harness. Share a tool after a
   second DOS consumer validates it. No mandatory common translator is added.

The [slice template](../templates/port-slice.md) carries these records into each
game's existing plan. Policy propagation changes no port's verification status.

## Inspected source hashes

SHA-256 of the relevant local files at review time. These identify the dirty
source observations above; they do not pin future sibling edits or reproduce
unretained emulator runs.

| File in F030CT | SHA-256 |
|---|---|
| `tools/smkx/__main__.py` | `75ec801e67af4c64f63ba037483dbf73197d3f105abb5d34de69616ec544eea2` |
| `tools/smkx/listing.py` | `61b676cd248be5e6eedbc24944f519d2e4eda739a73162391c0a40eb4035f280` |
| `tools/smkx/analyze.py` | `18cff86aa0dcb1f535e878d25e303792782ba6df9995d03ec2bb16a16d636b04` |
| `tools/smkx/emit.py` | `e64e9646a766c650076b0ea01d9d2e4932a772b34aaefaaa2811d35eed0998de` |
| `tools/smkx/liveness.py` | `10b1f81ecb4146b26d5e17d1b023ec68de2c6d1e788bbe844e9c29b6ff2d84a8` |
| `tools/smkx/tables.txt` | `a878c2b5047669f91dd2be5f43e1f5ad830909e36df8a65a71b158effa6578e5` |
| `scripts/ctx_seed_loop.py` | `a69f90ed6627d834dae07e37c5c1837bc4a702c0a008ea0ed7434029acab69eb` |
| `scripts/table_audit.py` | `627786857348ab4261dc9cf7d973bb3f9e9dff3e013a91f45f1d64cef595be2a` |
| `scripts/smkx_pc.py` | `081467ee81ef171edb0394e8cef8af01dd5364dc27bd0d0da4f177b83c9dc3e9` |
| `scripts/s9x_compare.py` | `0fde28f770d7542e394b61fc9384ae18aa82e98c62b2fac1da6afb8e1f710e9b` |
| `falcon/smkx_rt.s` | `3743e17d4fa2779acc039e0a511bacd2f5c95fa137c76aa3fbac5bd249750f99` |
| `analysis/ct.md` | `7a35b95216d80662487667cace12ccbb986af75db38da63feeb5465b72a42b88` |
| `analysis/porting-notes.md` | `0c3dc95393c2c4f4c9f52218051207ac8fc73c46414909def2d2a87fcc1fca56` |
