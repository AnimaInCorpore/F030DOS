# EMC2 level scripts

Status: **PARTIALLY RESOLVED**

The 29 level packages contain one `LEVEL#.INI` and one `LEVEL#.INF` script.
All 58 are IFF-like `FORM` resources whose form type is `EMC2`. The observed
chunk sequences are:

- `ORDR`, `TEXT`, `DATA` for 53 resources;
- `ORDR`, `DATA` for five `INF` resources (`L05`, `L13`, `L15`, `L20` and
  `L25`).

Chunks are even-padded, and the declared `FORM` size equals the complete file.
`TEXT`, when present, is a big-endian 16-bit offset table. Its first offset is
the table size; offsets are strictly increasing, strings are CP437 and
NUL-terminated, and the final byte is the string-table terminator.

## Wordcode contract

`ORDR` and `DATA` are big-endian arrays of 16-bit words. An `ORDR` entry of
`0xFFFF` is absent. A valid Lands of Lore function uses `DATA[ordr[n] + 1]` as
its first instruction word. The instruction decoder is:

1. `code & 0x8000`: opcode 0 with a 15-bit parameter;
2. otherwise `code & 0x4000`: the low byte is a signed parameter;
3. otherwise `code & 0x2000`: the following DATA word is the parameter;
4. otherwise the instruction has parameter zero.

The opcode is `(code >> 8) & 0x1F`, except for the first form, which forces
opcode 0. The core interpreter has 19 opcodes (`0..18`): jumps, return/value
and stack operations, register/base-pointer access, stack-pointer changes,
system calls, conditional jumps, negation, evaluation and a dynamic return/
jump. The system-call operand is narrowed to an 8-bit dispatch ID by the
interpreter.

`python tools/re/emc2info.py` validates the container, TEXT table, word
framing, entry points, instruction parameters and statically resolvable
control-flow paths. Across the corpus it covers:

- 1,475 non-sentinel function entries and 28,362 sentinel entries;
- 71,863 statically reachable instructions;
- 3,642 distinct conditional/unconditional branch targets;
- 8,971 system-call instructions using 154 IDs in `0x00..0xBE`.

With `--stack`, the same walker propagates an abstract script-local stack
depth along every statically resolvable path. It records 10,179 syscall-state
witnesses for the 8,971 unique syscall instructions; all 154 observed IDs have
at least one depth witness, and 121 IDs are reached at more than one relative
depth. The depth is measured from the ORDR entry and deliberately excludes
values already present on the caller's stack, so it is evidence about script
stack flow rather than a claimed native argument count. The immediate `addSP`
cleanup witness remains the stronger call-boundary signal: 8,026 of 8,971
syscall instructions have it, covering 122 IDs.

The tool also carries a 192-slot name cross-reference for the LoL-specific
dispatch table. This names the common IDs in reports (for example, `0x09` as
`loadLevelGraphics`, `0x0A` as `loadBlockProperties`, `0x0B` as
`loadMonsterShapes`, and `0x63` as `loadSoundFile`). These labels are a
ScummVM-derived cross-reference, not yet a native DOS proof of function
addresses or stack signatures. In the first-level `LEVEL1.INI` initializer,
the local bytecode visibly calls those IDs with filename/table parameters from
its `TEXT` chunk, which establishes the practical call boundary for the
Falcon port.

Static walking stops at return and tail-call instructions whose targets come
from the runtime stack. System-call IDs are bounded, but their Lands of Lore
semantics, stack signatures, and the dynamic call graph are not yet recovered.

The interpreter contract is cross-checked against the public ScummVM EMC
implementation, which reads `ORDR`/`DATA` as big-endian words, starts non-Kyra1
functions at `ordr[n] + 1`, and dispatches the 19 core opcodes:
<https://raw.githubusercontent.com/scummvm/scummvm/master/engines/kyra/script/script.cpp>

The public LoL1 closure memo reports the corresponding 192 game-specific
opcode slots as fully decompiled; this workspace treats that as a useful
cross-reference while independently validating the supplied DOS corpus:
<https://raw.githubusercontent.com/KForestland/lands-of-lore-1-re/main/docs/closure_memo.md>

The optional `--calls` report records a local stack-boundary witness whenever
the next instruction is `addSP N`. Four IDs show deliberate call-site arity
variation (`0x38` `initMonster`, `0x5E`
`playCharacterScriptChat`, `0x7A` `playDialogueTalkText`, and `0x84`
`updateBlockAnimations2`). The other 32 IDs have no immediate cleanup witness
and may return values, branch through script code, or use a different stack
boundary; they remain unresolved until native disassembly or DOS tracing ties
the calls to their resident handlers.

The corpus validator is [tools/re/emc2info.py](../tools/re/emc2info.py).
