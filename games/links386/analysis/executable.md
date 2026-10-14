# LCD.EXE — executable container

Status: **PARTIALLY RESOLVED; startup reaches the MZ/P3 loader path and EXP 0 runtime object is measured, final MZ-to-P3 transfer TBD. The `10049` failure is RESOLVED as a QEMU defect, not a property of the game: QEMU 11.1.1 drops the `CS` segment override on a data reference when `DS`/`ES`/`SS` bases are all zero, confirmed in isolation by `work/segtest/`. The oracle must be fixed or replaced before anything behind the mouse gate counts as measured**.

The primary target is the root-level `LCD.EXE` from the supplied Links 386 CD
image. The measurements below were made from that file by streaming it from
the ISO; regenerate them after extraction with:

```text
python tools/re/mzinfo.py game/cd/LCD.EXE
python tools/re/p3info.py game/cd/LCD.EXE --offset 0x2C524 --all --dump-load-dir work/listings
```

| quantity | value |
|---|---:|
| file size | 564,331 bytes (`0x89C6B`) |
| MZ header | `0x1400` bytes (`320` paragraphs) |
| relocations | `1,232` (`0x4D0`) |
| MZ entry | `0020:0000`, file `0x1600` |
| DOS-mapped image end | `0x2C524` |
| load module after header | `0x2B124` bytes |
| appended bytes after MZ image | `0x5D747` bytes |
| DOS/4G marker | file `0x122A2` |

## Appended P3 stream

The appended region is not an undifferentiated tail. It is an exact stream of
two adjacent Phar Lap 386 `P3` flat-model EXP records. The field meanings below
follow the published Phar Lap EXP header layout
([RBIL Phar Lap EXP header](https://delorie.com/djgpp/doc/rbinter/it/20/16.html));
the offsets and arithmetic are measured from `LCD.EXE`.

| record | file range | load image | flags | protected-mode entry |
|---|---:|---:|---:|---:|
| EXP 0, runtime candidate | `0x2C524..0x2FC5F` (`0x373B` bytes) | `0x2C724..0x2FC5F` (`0x353B` bytes) | `0x0002` | `EIP=0` in the record header |
| EXP 1, game image | `0x2FC5F..0x89C6B` (`0x5A00C` bytes) | `0x2FE5F..0x89C6B` (`0x59E0C` bytes) | `0x0003` | `CS:EIP=0000:0x7F064` |

The partition is exact:

```text
0x2C524 + 0x373B + 0x5A00C = 0x89C6B = LCD.EXE file size
```

Both records are level 1 (flat-model), use a 0x180-byte header, have no
relocation, segment-information, symbol, GDT, LDT, IDT or TSS table, and place
their load image at record offset `0x200`. EXP 1 declares `ESP=0x3C66C`, a
0x5000-byte stack, `memory_requirements=0x9AA84`, minimum extra memory `1` and
maximum extra memory `0x200000`. Its flags have bit 0 set, so the on-disk load
image is packed; the declared initial EIP is therefore in the unpacked memory
image, not directly in `LCD.exp1.load`.

The Watcom32 runtime banner is at original file `0x82C9A` (EXP 1 load-image
offset `0x52E3B`). The `DOS/4G` text at original file `0x122A2` remains a
measured string in the MZ-side loader/runtime; it is not the container
signature. The earlier wording “DOS/4G marker” was useful as a search anchor
but did not establish the appended-region format; the two `P3` headers now do.

## EXP 1 pack expansion

The Phar Lap `-pack` stream has now been decoded. Each token starts with a
little-endian 16-bit count. Counts without bit 15 copy that many literal bytes;
counts with bit 15 set read a one-byte pattern length. A zero pattern length
expands to zero bytes; otherwise the pattern repeats until the requested count
is emitted. The new helper reproduces the declared image size exactly:

```text
python tools/re/exp_unpack.py game/cd/LCD.EXE --offset 0x2FC5F \
  --output work/listings/LCD.exp1.expanded.load
python tools/re/disasm32.py work/listings/LCD.exp1.expanded.load \
  --origin 0 --offset 0x7F064 \
  --output work/listings/LCD.exp1-entry32-expanded.lst
```

The packed `0x59E0C` bytes expand to `0x9AA84` bytes. At `EIP=0x7F064`, the
first bytes are `EB 78`, which skip the Watcom copyright string and land at
`0x7F0DE`; the recovered code there begins `FB 83 E4 FC 8B DC` (`STI`, align
the stack, save the stack pointer). This resolves the packing blocker while
leaving the exact 16-bit-to-protected-mode hand-off open.

The P3 runtime blocks are separate from the load images and are present even
when a record has no relocation or descriptor tables of its own. Their first
words identify them as `DX` records:

| record | runtime block | measured fields |
|---|---:|---|
| EXP 0 | `0x2C6A4..0x2C724` (`0x80` bytes) | `DX`; `NISTACK=6`, `ISTKSIZE=1` |
| EXP 1 | `0x2FDDF..0x2FE5F` (`0x80` bytes) | `DX`; `NISTACK=20`, `ISTKSIZE=3` |

EXP 0's load image begins with the Phar Lap copyright banner. At load-image
offset `0x32` it contains `C5S2S2PA`, and its table at load-image offset
`0x200` begins with a six-entry descriptor/table record whose measured fields
include `+0x0A=+0x0E=0x14`, `+0x12=+0x16=0x0A`, and `+0x06=0x2E`. These bytes
match the validation checks in the MZ-side loader below. This identifies EXP 0
as a runtime/descriptor payload candidate, while EXP 1 remains the game image.

EXP 0 is not a second game entry point. Its header declares `EIP=0`, `ESP=0`
and no stack, while its load image begins with the Phar Lap copyright banner;
its separate runtime block begins with a small `DX` descriptor-like record.
This makes it a runtime/stub payload candidate rather than executable game
code. EXP 1 is the game image: its expanded entry is the Watcom32 startup at
`EIP=0x7F064`.

## MZ-side handoff lead

The MZ load module contains an executable-format parser, but it is not yet
proven to be the self-handoff. At load addresses `0x5596..0x5B8A`, the parser
reads DOS file handles, recognizes `P3` plus the Phar Lap `PA`/`PE`/`P@`/`PD`
variants, and builds a normalized header. Its MZ/MP path synthesizes equivalent
load-image fields before reading the selected image. The observed references to
this parser at `0x4F45` and `0x53FB` occur in generic file-open/metadata paths.

The MZ also contains a more complete loader path. The 16-bit MZ-side routine
at `0x26C61`, reached by the call at `0x26A9C`, calls the file/format wrapper
at `0x3AD:0x0006` (the MZ routine at `0x4ED6`) and records the selected image
metadata. The surrounding startup routine checks `[0x5BAE]` at `0x26C14`;
when that state is active it reaches `0x26C21`, whose near call targets
`0x2832B`.
That routine again invokes the wrapper, then at `0x284E1` checks for the `P3`
signature (`0x3350`), level 1, a valid packed-image flag, and the absence of
unsupported relocation/segment state. It calls `0x28AB8`, which uses the P3
load-size fields at header offsets `0x2A/0x2C` to allocate and load the image.
The same path recognizes Phar Lap `PA`/`PE`/`P@`/`PD` records, and on success
installs descriptor/table pointers around `0x28903..0x289AC`.

This is strong evidence for the target's own MZ-side EXP loader. It still does
not prove that the measured `0x3DC8` entry chain is the caller of this path for
the appended EXP stream: the apparent handoff after table installation is through
runtime indirection, and the exact selector/base setup leading to EXP 1's
`EIP=0x7F064` remains to be recovered.

The call at `0x2854F` supplies `0x28AB8` with the normalized header, source
handle/offset and an output far-pointer slot. `0x28AB8` allocates the load
image, obtains a selector through `0x20:0x0442`, stores it in `[0x5BB4]`, and
uses runtime-mediated reads to populate the selector-backed object. It then
validates the selector at offset `0x32` for `C5` and checks the descriptor/table
record at offset `0x200`. EXP 0 satisfies those measured checks. This proves
the selector-creation and EXP 0 validation stage and, as the trace below now
shows, that this static path is reached during startup; it still does not prove
that the selector-backed object is the final EXP 1 image or that execution
transfers to EXP 1's entry at `EIP=0x7F064`.

### Startup trace confirmation

A fresh Y-path QEMU capture with `-d in_asm,exec,pcall,int,guest_errors`
records the relevant translation blocks under one runtime code-segment base.
The `exec` transitions are important: `in_asm` alone reports translated blocks,
while `exec` shows the taken branch. Matching the resident instruction bytes
back to the MZ file gives this measured sequence:

```text
runtime 0x2B065 -> 0x2B231       MZ call at 0x26A9C -> routine 0x26C61
runtime 0x2B28E -> 0x0094A6      relocated 0x3AD:0006 -> MZ wrapper 0x4ED6
runtime 0x2B1E4 -> 0x2B1F1       [0x5BAE] branch falls through
runtime 0x2B1F1 -> 0x2C8FB       near call 0x26C21 -> routine 0x2832B
runtime 0x2CB1F -> 0x2D088       near call 0x2854F -> routine 0x28AB8
```

The far-call word is relocated at runtime: the source bytes at MZ `0x26CBE`
encode `0x3AD:0006`, while the trace executes `0x94A:0006` and enters the
wrapper at runtime `0x94A6`. This is why a fixed subtraction from a QEMU trace
address is not a valid file map for this executable. The trace upgrades
`0x26C61 -> 0x2832B -> 0x28AB8` from a static lead to a startup-reached path.
It does not show the full `0x3447` selector-backed dispatch (`A1 D6 1B` and
`lcall [0x3174]`), so `[0x1BD6]` and the final transfer to EXP 1 remain open.

One additional dispatch lead narrows that indirection. `0x28AB8` allocates a
selector and stores it in `[0x5BB4]`; the loader then uses that selector as the
`ES` base while validating the normalized loaded object. A protected-mode
dispatch/exception path at `0x3447` checks `[0x5BAE]`, forms a far pointer from
`[0x5BB4] << 16 | [0x1BD6]`, and executes `lcall [0x3174]`. The selector is
therefore dynamically created, while `[0x1BD6]` is a runtime-populated offset
candidate. This is the strongest measured MZ-to-loaded-image transfer lead so
far, but the write to `[0x1BD6]` and its exact relation to EXP 1's unpacked
`EIP=0x7F064` are still unresolved.

A raw-byte search confirms the boundary: the MZ image contains only the
`A1 D6 1B` read at `0x3455`, with no encoded store to `[0x1BD6]`; the expanded
EXP 1 image contains no literal reference to that address either. The value is
therefore supplied through runtime state or a dynamically loaded component,
not by a direct static assignment in either recovered image.

By contrast, the `0x3DC8` launcher calls `0x2C6:0x000E` with four
argument-like words, then calls `0x2C6:0x019D` and `0x2C6:0x0B6B` as part of
command-line/configuration processing. Selector `0x2C6` is an LDT selector and
is dynamically established, so these calls are protected-mode runtime calls;
the static offset `0x000E` should not be equated with EXP 1's initial EIP.

The actual MZ entry at `0x1600` first jumps to `0x160D`, establishes the DOS
stack/data segments and parses the command tail, then jumps back to `0x1602`.
That trampoline calls the MZ routine at `0x29C:0x0008` (file `0x3DC8`) and
then the DOS exit routine at `0x20:0x0159` (file `0x1759`). The `0x3DC8`
routine performs CPU/FPU checks and launcher/configuration work. No direct
static call edge from this `0x3DC8` routine to `0x26C61`, `0x2832B` or
`0x28AB8` is present in the measured MZ image; the dynamic capture proves that
another startup path reaches the loader, but not which callback/return contract
connects it to the `0x3DC8` launcher or to the final EXP 1 transfer.

## DOS-oracle boundary

The minimum install now boots under genuine MS-DOS 6.22. The floppy source is
the sibling project directory recorded in `analysis/cd-layout.md`; QEMU is
`C:\\Program Files\\qemu\\qemu-system-i386.exe`. A bootstrap-only run exits
cleanly through the test `QUIT.COM`, and `BOOT.LOG` confirms that DOS 6.22
expands `HIMEM.SY_`, `EMM386.EX_`, `MEM.EX_`, `SHARE.EX_`, `XCOPY.EX_` and
`SMARTDRV.EX_`.

The first controlled game boot loaded `HIMEM.SYS` and `EMM386.EXE RAM`, reported
617 KB largest executable memory and 14,928 KB free EMS, then launched
`GOLFCD.BAT`. Matching the CD's own `BOOT.DAT` instead with `EMM386.EXE NOEMS`
reported 618 KB largest executable memory and also reproduced the same result.
With no mouse driver, the program offers its keyboard-equivalent prompt: `N`
exits with a user-exit message, while `Y` reaches
`Phar Lap fatal err 10049: Ran out of stack buffers`. A derived INT 33h driver
from the sibling DOS-oracle work removes the prompt, but the same Phar Lap
error remains. The result is also unchanged with 32 MB guest RAM and with
QEMU's debug-exit device removed.

The embedded runtime records are not using the documented default stack
settings: EXP 0 requests 6 interrupt stacks of 1 KB, and EXP 1 requests 20
stacks of 3 KB. These fields are the Phar Lap `NISTACK`/`ISTKSIZE` parameters
([Open Watcom Linker Guide](https://open-watcom.github.io/open-watcom-v2-wikidocs/lguide.html#runtime-pharlap-only)). A derived EXP 0 patch changing its values to
20×3 KB did not change the oracle result. This makes the error a useful
runtime boundary, but not evidence that the executable's declared stack pool
is undersized. A second derived test expanded EXP 1 to 64 interrupt stacks of
4 KB; it produced the same `10049` immediately after the mouse/keyboard gate.
The failure is therefore not relieved by increasing either P3 record's
declared interrupt-stack pool.

Removing `EMM386.EXE` entirely while retaining HIMEM produced the same
10049, so the observed boundary is not specific to EMS/VCPI setup either.

Timed QEMU samples refine that boundary. While the game waits at its mouse
prompt, a full-RAM capture places the expanded EXP 1 prompt string at linear
`0x261B3`, exactly `0x16000 + 0x101B3`; EXP 1 is therefore resident and the
game has reached its own mouse gate. After sending `Y`, the screen shows
`10049` and returns to the DOS prompt. The post-`Y` register sample is in a
DOSX protected-mode thunk (`CS=0116`, `EIP=0x110F`), while the earlier prompt
wait samples use the resident extender/VMM region around `CS=f000`.
Capturing `0xF0000` shows executable extender/VMM code that does not
byte-match the packed or expanded Links images. The measured failure is thus
in the DOSX/VMM service path entered from the game's early mouse/keyboard
startup, before the title/menu, rather than in a Links resource.

An instruction-level QEMU trace of the same transition identifies the first
stack-buffer machinery. A DOSX routine around logical `0x106D89..0x106DB6`
checks the active stack state and far-calls the runtime service pointer at
`CS:0x907C`. The observed `CS=0116,EIP=0x110F` state decodes to linear
`0x226F`, whose entry is `INT 28h`; it returns through the DOSX idle/service
stub at `0x22CF`. The resident VMM helper at `0xF6C4C` tests for stack segment
`0xDA80` and compares `ESP` with `0xF218`. When the helper reports that a
stack transition is required, `0xF7188` saves the old stack pointer at
`0xF210`, loads the saved `SS:SP` pair from the selected buffer descriptor,
and calls the pending service. The surrounding `0xF88F5`/`0xFA644` path is
therefore the measured stack-buffer boundary immediately around the failing
startup service. The fatal handler itself is now identified in the same
resident trace: `0xC2CF07` restores the saved error-handler `SS:SP`,
`0xC2CF16` pushes severity/value `1` and error code `0x2741` (decimal
`10049`), and `0xC2CF23..0xC2CF66` builds the error record before jumping to
the common handler at `0xC2A4C1`. Its immediate transfer condition is also
measured: after establishing the resident data segment, the dispatcher at
`0xC2B719` tests its DS-relative link/context word at `DS:0x1A6C`, and
`0xC2B71F` jumps to `0xC2CF07` when that value is zero.
The alternate branch packages the saved interrupt state and returns through
`IRETL`. A related resident entry path at `0xC2B876` reads the previous
`DS:0x1A6C` value into the current frame and writes the current frame address
back to that slot, confirming that the word is an active context-chain link,
not a game-data address. The message formatter and numeric error code are
therefore no longer ambiguous; the remaining root cause is why this context
link is absent when the startup service dispatches. This localizes the
failure to the resident DOSX/VMM stack-switch/error path rather than the
game's resource loader.

### Correction: the `INT 28h`/#GP pair is not on the failure path

An earlier reading of this trace named `INT 28h` at `CS=0116:EIP=0x110F`
(linear `0x226F`) and the following #GP `e=0142` as the immediate fault, and
the all-zero `IDT[0x28]` at `IDT=0x14CB80 + 0x140` as the reason. Both
observations are real and both are about the wrong context.

`work/qemu_out/links-y.log` holds 21,552 `v=28` records and 21,552 matching
`v=0d e=0142` records, but only **seven of each occur before the fatal
transition**; the remaining 21,545 are the `COMMAND.COM` idle loop after the
game has already exited. Their register dumps settle what they are:
`EFL=0x27202` has `EFLAGS.VM` set, `CPL=3`, and every segment base is exactly
`selector << 4` (`CS =0116 00001160`). That is **V86 mode**, where EMM386
reflects every `INT n` through #GP by design, so the pair is ordinary DOS
idling. `IDT=0x14CB80`/`GDT=0x14D380` are EMM386's tables; while the extender
is running the same trace reports `IDT=0x0000F59C`, `GDT=0x00C02000` and
`LDT=0x00C12000`. The zero `IDT[0x28]` measurement and the sibling
Underworld 2 comparison were both taken in the DOS-side V86 context and say
nothing about the extender's dispatch.

The same caution applies to the sub-1 MB addresses named above —
`0x106D89..0x106DB6`, `CS:0x907C`, `0xF6C4C`, `0xF7188`, `0xF88F5`, `0xFA644`.
They were recorded without noting which descriptor tables were live in the
sample they came from, so each needs re-checking against `EFLAGS.VM`, `CR3`,
`GDT`, `LDT` and `IDT` before it is used again. The `0xC2B719` dispatcher
reading `DS:0x1A6C` is the exception: it is inside the extender's own code
segment and the block trace below confirms it as the exact transfer into the
fatal handler.

### The measured failure chain

The failing transition is interrupt event `114196` of `links-y.log` and is
entirely inside the extender, which is resident with `CS` base `0xC2A000`
(limit `0x1FFFF`, `CS32`, DPL 0), `DS=SS=0x0060` (base 0, limit `0x106FFF`),
and `CR3=0x00165000` unchanged across every sample below:

```text
114196  v=21          cpl=0  IP=0008:0000B7DE  pc=0x00C357DE  EAX=0x2510  ESP=0x91758
114197  v=0d e=ff50   cpl=0  IP=0008:00002136  pc=0x00C2C136              ESP=0x9238C
114198  v=0d e=ff50   cpl=0  IP=0008:0000299F  pc=0x00C2C99F              ESP=0x92F98
   ...  16 further identical faults, ESP rising by 0xC00 each time
114215  v=0d e=ff50   cpl=0  IP=0008:0000299F  pc=0x00C2C99F              ESP=0x9FB98
114216  v=21          cpl=3  V86 -- real-mode DOS prints the message (INT 29h follows)
```

The instruction bytes come from `work/qemu_out/links-y-inasm.log`:

- `0xC2C112` is the extender's `INT 21h` entry: `push ds/eax/ebx/ebp`,
  `push 0`, `mov ebp,esp`, `test dword [ebp+0x18], 3`, `je 0xC2C136`.
  `[ebp+0x18]` is the saved `CS`, so the branch is taken for a ring-0 caller,
  which is what this `INT 21h` is.
- `0xC2C136` is `2E 8E 1D F8 03 00 00` — `mov ds, cs:[0x3F8]`.
- The word at `CS:0x3F8` (linear `0xC2A3F8`) reads `0xFF50`. With `TI=0` that
  is GDT index `0x1FEA`, far past the `0xFFF` GDT limit, so the load raises
  #GP with the selector as its error code — which is exactly `e=ff50`.
- The extender's fault entry at `0xC2C984` tests `cs:[0x3FA]` against `1` and
  on match falls through `0xC2C99E` to `0xC2C99F`, which is the *same*
  `mov ds, cs:[0x3F8]`. The handler therefore reraises its own fault.
- Every re-entry consumes a fresh interrupt stack: `ESP` steps by exactly
  `0xC00` = 3 KB and the recursion runs 19 deep. Those are EXP 1's declared
  `ISTKSIZE=3` and `NISTACK=20`, so the pool is honoured and correctly sized.

The dispatcher is measured block by block. `work/qemu_out/links-y-exec-chain.log`
repeats one six-block cycle 18 times and then breaks out of it:

```text
0xC2C984 -> 0xC2AC4E -> 0xC2B680 -> 0xC2B687 -> 0xC2B738 -> 0xC2B83B -> 0xC2C984 ...
                                    0xC2B687 -> 0xC2CF07                (last pass)
```

- `0xC2AC4E` is the vector-`0x0D` IDT stub: `push 0x0D`, `jmp 0xC2B680`.
- `0xC2B680` is `push ds`, `push 0x10`, `pop ds`. The dispatcher takes its data
  segment from an **immediate**, not from `cs:[0x3F8]`, which is why it keeps
  working while the handler entry cannot.
- `0xC2B687` files `EAX`/`EBX`/the vector into `ds:[0x2504]`, `ds:[0x2508]`,
  `ds:[0x2510]`, and `0xC2B6EC` saves the interrupted `SS:ESP` to
  `ds:[0x24FC]`/`ds:[0x24F8]`.
- `0xC2B719..0xC2B738` is the interrupt-stack pool itself:

```text
0xC2B719:  cmp  dword ds:[0x1A6C], 0
0xC2B71F:  je   0xC2CF07            ; -> push 1, push 0x2741 (10049)
0xC2B725:  push word 0
0xC2B729:  push word ds:[0x587E]    ; interrupt-stack SS
0xC2B72F:  push dword ds:[0x1A6C]   ; head of the free list
0xC2B734:  lss  esp, [esp]          ; switch onto it
0xC2B738:  pop  dword ds:[0x1A6C]   ; head = the next link, stored at stack top
```

`DS:0x1A6C` is therefore the head of a singly linked free list of interrupt
stacks, each stack's first dword being the next link; the `lss` is what makes
`ESP` step by one `ISTKSIZE` unit per nested fault. An earlier note in this
document already identified `0xC2B719`/`0xC2B71F` as the transfer into
`0xC2CF07` on a zero `DS:0x1A6C` and called the missing context link the
remaining root cause. That is now answered: the link is zero because 19 nested
faults consumed every entry. The other candidate exhaustion route in the
`INT 21h` handler — `0xC2C1B5` reading `ds:[0x19F8]` and `0xC2C1BD` branching
to `0xC2CEFA` when it is null — was **not** taken; `0xC2CEFA` never appears in
either capture.

`10049 "Ran out of stack buffers"` is therefore literally accurate and still
the terminal symptom of an unbounded fault recursion, not an undersized pool.
That retro-explains the two derived stack experiments recorded above: raising
EXP 0 to 20x3 KB and EXP 1 to 64x4 KB could not have changed the outcome,
because a recursion consumes whatever pool it is given.

Two measurements bound what `CS:0x3F8` is. They come from
`work/qemu_out/links-y-exec-chain.log`, a separate capture of the same
configuration that reproduces the failure identically (18 re-entries of the
fault handler at `0xC2C984`, matching the 18 repeats plus one initial fault
counted in `links-y.log`). That log re-enters the block at `0xC2C13D` — the
instruction immediately after the `mov ds` — 363 times before the failure, so
the word held a valid selector on every earlier ring-0 entry. And once the
pool is exhausted the extender's fatal path runs `0xC2CF07` (restore
`SS:ESP` from `ds:[0x587C]`/`ds:[0x58D2]`), `0xC2CF16` (`push 1`,
`push 0x2741` = decimal 10049) and `0xC2CF23` (`cli`; `mov ds, cs:[0x3F8]`)
through to `0xC2CF2B` **without a twentieth fault**, so the word is valid
again by then. `0xFF50` is thus a transient value occupying a window, and the
failure is a ring-0 `INT 21h` delivered inside that window — not a permanent
corruption of the extender image.

The caller inside that window is measured as well. At `0xC35792..0xC357DE` the
extender issues `INT 21h AH=51h` (get PSP), `AH=50h` (set PSP from
`ds:[0x58CE]`), builds the far pointer `EBX=0x05BD:0x0B3B` with `ECX=4`, pushes
the words `0x0875`, `0x0BCB`, `1` and `[ebp+8]`, sets `DS=SS`, writes `0x0D8B`
into both halves of `SS:[ebp-0x20]`, and issues `INT 21h AX=2510h` with
`DS:EDX = 0060:0x9176C`. `0x05BD` and `0x0D8B` are themselves selectors whose
bases are the selector value `<< 4` (`0x5BD0`, `0xD8B0`), the extender's
low-memory alias convention; the client code runs under `CS=0x05BD` at CPL 3.

### What `CS:0x3F8` is, and what it should hold

The failing service is identified. `0xC2D080` tests `AH` against `0x25` and
branches to `0xC319DC`, which dispatches `INT 21h AH=25h` on `AL`:

```text
0xC319DC:  cmp al, 0x0E   / je 0xC2C112
0xC319E4:  cmp al, 0x10   / je 0xC2C112
0xC319EC:  cmp al, 0x11   / je 0xC2C41B
```

So `0xC2C112` is not a generic `INT 21h` prologue: it is the routine that
installs a protected-mode handler for vectors `0x0E` and `0x10`, and the call
that fails is **"install the protected-mode `INT 10h` handler"**. The block
sequence in the exec-chain capture confirms the entry — `0xC319DC` ->
`0xC319E4` -> `0xC2C112` -> `0xC2C136` -> fault.

The word itself is a mirror of an MZ-side variable, and all three publishing
instructions are static. Using this run's MZ code skew — linear = file offset
+ `0x45D0`, verified on the four sites named in this section — the `LCD-loader`
listing gives:

| file | instruction | source |
|---:|---|---|
| `0x27A8A` | `mov es:[0x3F8], ax` | `ax` from `[0x587C]` |
| `0x27C96` | `mov es:[0x3F8], ax` | `ax` from `[0x587C]` |
| `0x29D88` | `mov es:[0x3FA], ax` | `ax` from `[0x57EC]` |

All three load `ES` from the immediate `0x1277` first. So `cs:[0x3F8]` mirrors
MZ-side `[0x587C]` and `cs:[0x3FA]` mirrors `[0x57EC]` — and the extender's own
`0xC2C16F` reads `ds:[0x57EC]` directly, which is the same variable seen from
the other side.

**The intended value of `CS:0x3F8` is `0x0010`.** File `0x27C8B..0x27C96` is:

```text
00027C8B  b8 10 00        mov ax, 0x10
00027C8E  a3 7c 58        mov [0x587C], ax
00027C91  ba 77 12        mov dx, 0x1277
00027C94  8e c2           mov es, dx
00027C96  26 a3 f8 03     mov es:[0x3F8], ax
```

Three independent measurements corroborate `0x0010`: the exception dispatcher
hardcodes the same selector (`0xC2B680` is `push ds; push 0x10; pop ds`); every
`cpl=0` register dump in `links-y.log` shows `DS =0010 0000d8b0`; and the fatal
handler at `0xC2CF07` loads its `SS` from `ds:[0x587C]`. The observed `0xFF50`
is therefore a wrong value in a known slot, not an unknown one.

The same init block is the extender's selector table, recovered statically:

```text
[0x5878]=0x0008  [0x587A]=0x0018  [0x587C]=0x0010  [0x587E]=0x0060
[0x5880]=0x0048  [0x5882]=0x0118  [0x5884]=0x0090  [0x5886]=0x0098
[0x5888]=0x0130  [0x588A]=0x0138  [0x588C]=0x0110  [0x588E]=0x00C8
```

`[0x587E]=0x0060` is the interrupt-stack `SS` the dispatcher pushes at
`0xC2B729`, and `0x0060` is the `SS` in every `cpl=0` dump — so the table reads
correctly against the runtime.

`[0x587C]` has a second writer, and it is the lead worth following. File
`0x2878..0x2884` is

```text
00002878  8e 06 0c 58     mov es, [0x580C]
0000287C  ff 1e 0e 58     lcall [0x580E]
00002880  0f 82 60 01     jb 0x29E4
00002884  8c 1e 7c 58     mov [0x587C], ds
00002888  8c 0e 7a 58     mov [0x587A], cs
```

preceded by `mov ax, 1` at `0x2875`. That is the DPMI mode-switch entry
contract — `AX` bit 0 set for a 32-bit client, a far call through the pointer
the host supplied, carry set on failure — after which the routine records the
`DS` and `CS` the host handed back. `[0x587C]` therefore tracks the data
selector produced by a mode switch, which is exactly the kind of value that can
be transiently wrong. The observed run does not take the DPMI path: events
`114190..114195` of `links-y.log` show each ring-0 `INT 21h` reflected down to
`CS=0x05BD` at CPL 3 and then `INT 67h AX=0xDE0C` — the VCPI "switch to V86
mode" call — so every DOS service is a mode round trip, and the fault falls on
the entry of the round trip that follows.

The open item is now narrow and directly testable: `CS:0x3F8` should hold
`0x0010` and holds `0xFF50`, so the question is which of the two publishing
sites wrote it, with what in `[0x587C]`, and whether `[0x587C]` was captured
from a mode switch that returned something other than `0x0010`.

The static trace cannot finish this on its own. The window between the last
successful load (the `0xC2C13D` entry at exec-chain line 1,553,564) and the
first fault (line 2,346,148) holds 387,720 block executions, and no register
dump in `links-y.log` ever shows a data selector based at `0xC2A000`, so the
final write reaches the resident image through a descriptor that is only live
between interrupts.

### Measured: the MZ-side source `[0x587C]` is correct

`work/read_mz_selector_table.py` reads the word out of a running guest.
`[0x587C]` is DS-relative and the MZ data segment is not known before the run,
so the address is measured rather than assumed: the init block writes twelve
known constants into `[0x5878..0x588F]`, and eleven of them anchor the table in
a stopped-CPU RAM dump while `[0x587C]` itself is matched as a two-byte hole,
so the search cannot assume the value it is asked to measure. None of those
bytes occur in `LCD.EXE` on disk, so a hit is a runtime fact and not a copy of
the file. Each capture stops the CPU before dumping, so the screen, the
registers and the RAM describe one instant and the screen names the phase.

The run reproduces this section's calibration independently. A signature vote
of the MZ load module against conventional RAM puts the load image at linear
`0x59D0` — load segment `0x059D`, file skew `0x45D0`, matching the skew used
above and the `CS=0x05BD` the client code runs under — and the selector table
resolves at linear `0x13128`, so the MZ data segment is paragraph `0x0D8B`
(linear `0xD8B0`, `0x7EE` paragraphs above the load segment). That is exactly
the base QEMU prints for the extender's ring-0 `DS =0010` in `links-y.log`, now
re-derived from this run alone. Exactly one copy of the table is resident, so
there is no ambiguity about which copy was read.

Four captures of one run — at the mouse prompt (26.0 s, 30.1 s), and after `Y`
with `Phar Lap fatal err 10049` and the `C:\LINKS386>` prompt on screen
(32.1 s, 35.0 s):

| capture | phase | `[0x587C]` |
|---|---|---:|
| 26.0 s | mouse/keyboard gate | `0x0010` |
| 30.1 s | mouse/keyboard gate | `0x0010` |
| 32.1 s | after the fatal return | `0x0010` |
| 35.0 s | after the fatal return | `0x0010` |

The full table reads `0800 1800 1000 6000 4800 1801 9000 9800 3001 3801 1001
c800` at every capture — the init block's twelve constants, unmodified.
**`[0x587C]` holds `0x0010`, the intended value, both while the game is live at
its gate and after the fatal handler has returned to DOS.** The source is not
wrong, and the DPMI mode-switch return at file `0x2884` is not implicated: that
path would have left a wrong value in `[0x587C]`, and it did not.

The paired slot reads `[0x57EC] = 0x0000` at every capture. That is the word
the extender reads directly at `0xC2C16F` and the source of the `CS:0x3FA`
mirror written at file `0x29D88`; its meaning is not yet assigned, and no
conclusion is drawn from the zero here beyond recording it.

Two facts follow, and they narrow the question rather than answer it. First,
the mirror `CS:0x3F8` diverges from a source that stays correct, so the
corruption is in the publish path or below it, not in `[0x587C]`. Second, the
timed capture cannot see the fault window at all: `0xFF50` occupies the mirror
for the span of one ring-0 entry, and both the prompt and the post-fatal
captures fall outside it, which is why every sample above reads the settled
value. Only a write watchpoint can name the writer.

### Measured: nothing writes the mirror, and the mirror is correct at the fault

The watchpoint is `work/watch_mirror.py` on `work/rsp.py`, a GDB
remote-serial client with `Z2`/`Z3` support (the `Z0` half is derived from
`F030Comanche/work/rsp.py`). QEMU's x86 watchpoint takes the address the TLB
sees — the **linear** address, segment base folded in, paging not yet applied
— so it catches a write through any selector that lands on the slot, which is
what a writer reaching it through a transient descriptor would need.

**A `Z2` write watchpoint on linear `0xC2A3F8`, armed from boot, traps four
writes in a whole run, all inside extender startup (1.9 s–2.5 s), and none
afterwards — the failure at ~4 s included.** In order:

| t | PC after the store | storing instruction | leaves |
|---|---|---|---:|
| 1.9 s, 2.1 s | linear `0xa6c4`, CS base 0 | `rep movsw` (real/V86) | `0x0000` |
| 2.5 s | linear `0x1c84e`, CS base `0x18140` | `rep stosd es:[edi], eax` with `eax=0` at `0x1c84c` | `0x0000` |
| 2.5 s | linear `0x1c4de`, CS base `0x18140` | `rep movsd es:[edi], [esi]` at `0x1c4dc` | `0x0010` |

The last one is the extender relocating itself. `0x1c4c1..0x1c4cb` builds
`ESI = 0x1277 << 4` from a **relocated** immediate — image offset `0x16af3` is
in the MZ relocation table, so at runtime it is `(0x1277 + 0x59D) << 4 =
0x18140`, exactly the CS base the copying code runs under — and `ES=DS=0xC8`
with `EDI` from `[0x1b94]`. So the bound extender image inside the MZ module is
block-copied to its resident home at `0xC2A000`, carrying `CS:0x3F8` with it.
That is the publish path, and it runs once.

This also fixes the extender's file identity: **resident linear `L` is file
offset `L - 0xC2A000 + 0x13B70`**. `0xC2C112` and `0xC2C984` disassembled from
the file at that mapping are byte-identical to what the guest executes, so the
whole resident extender is statically addressable.

At the failing execution of `0xC2C136`, with the CPU stopped on the
instruction:

```text
x  (linear, guest paging)  0xC2A3F8 = 0x0010
pagewalk CR3=0x165000  PDE@0x16500c=0x161027  PTE@0x1610a8=0x164a67
  -> physical 0x1643F8 = 0x0010
single step -> EIP = 0x0C4E = linear 0xC2AC4E, the vector-0x0D IDT stub
```

The operand is `0x0010`, the page tables that reach it are present and clean,
and the instruction faults anyway.

### Correction: `0xFF50` is not the value of `CS:0x3F8`

`-d int` reproduces the archived chain exactly — `v=0d e=ff50` nineteen times,
first at `pc=00c2c136`, then eighteen at `pc=00c2c99f` with `ESP` stepping
`0xC00` — so this is the same failure, not a different one. What is wrong is
the reading of the error code. This document previously stated that "the word
at `CS:0x3F8` (linear `0xC2A3F8`) reads `0xFF50`". It does not; it reads
`0x0010`, live, at the faulting instruction. `0xFF50` was **inferred** from the
`#GP` error code on the rule that a bad segment load reports the selector, and
that inference pointed at the wrong address.

A `Z3` **read** watchpoint names the address the instruction actually
dereferences, which no register dump shows. Armed on linear `0x3F8` at the
gate, it fires in lockstep with the fault, every hit reporting `PC = 0xC2AC4E`
with the exception frame beneath it — `[ESP]=0xff50` (error code),
`[ESP+4]=0x2136` (faulting EIP, i.e. `0xC2C136`), `[ESP+8]=0x8` (CS).

So `mov ds, cs:[0x3F8]` at `0xC2C136` read **linear `0x3F8`** — the
displacement with a *zero* segment base — not `CS:0x3F8 = 0xC2A3F8`. Linear
`0x3F8` is IVT vector `0xFE`, holding `F000:FF53`, and its offset word is
`0xFF53`. A `#GP` error code carries the selector with bits 1:0 replaced by the
IDT/EXT flags, so selector `0xFF53` reports as `0xFF50` — the observed code,
exactly. `0xFF53` has GDT index `0x1FEA`, and the GDT limit at the fault is
`0xFFF` (index `0x1FF`), so the load is out of range and `#GP` is correct
behaviour *for the address that was read*.

### The CS override is dropped only when every default segment base is zero

The same instruction form works elsewhere. A `Z3` read watchpoint on linear
`0xC2A3F8` armed from boot traps `mov ds, cs:[0x3F8]` at three other sites —
reported at `0xC2D0B4`, `0xC2C7D4` and `0xC31A33`, each the `cmp word
[0x5784], 0` that follows the load — and every one of them reads `0xC2A3F8`
and gets `0x0010`. The override is applied there and dropped at `0xC2C136`.

The one state that separates them, in the samples taken:

| | ES base | SS base | DS base | CS base | result |
|---|---|---|---|---|---|
| fault at `0xC2C136` | `0x00000000` | `0x00000000` | `0x00000000` | `0xC2A000` | reads `0x3F8` |
| successful read | `0x0000d8b0` | `0x00000000` | `0x0008d5e0` | `0xC2A000` | reads `0xC2A3F8` |

The override is dropped exactly when **all** default segment bases are zero.

### Confirmed in isolation: the emulator drops the `CS` override

`work/segtest/` is a 512-byte boot sector that reproduces this with no DOS, no
extender, no paging and no Links code: it enters 32-bit protected mode, builds
its own GDT with a non-zero `CS` base, plants a *valid* selector at each
candidate address so the test reports an address instead of faulting, executes
one instruction and reports through `isa-debug-exit`.

| variant | instruction | segment state | effective address | verdict |
|---|---|---|---|---|
| `seg_base` | `mov ds, cs:[0x3F8]` | DS/ES/SS base 0 | `0x3F8` | **base dropped** |
| `seg_ctrl` | `mov ds, cs:[0x3F8]` | DS/ES/SS base `0x2000` | `CS.base + 0x3F8` | correct |
| `seg_plain` | `mov ebx, cs:[0x3F8]` | DS/ES/SS base 0 | `0x3F8` | **base dropped** |
| `seg_fs` | `mov ebx, fs:[0x3F8]` | FS base `0x2000`, DS/ES/SS base 0 | `FS.base + 0x3F8` | correct |
| `seg_fscs` | `mov ebx, fs:[0x3F8]` | FS base `0x1000`, DS/ES/SS base 0 | `FS.base + 0x3F8` | correct |

Identical on `-cpu 486` and `-cpu pentium`, QEMU 11.1.1 (TCG, macOS/aarch64
host). Three things follow, and the last one is the reason the pair was built:

- It is not specific to `mov Sreg, m`: `seg_plain`, an ordinary `mov r32, m`,
  loses the base the same way.
- It is not "overrides are dropped in flat mode": `seg_fs` applies an `FS`
  override under exactly the same flat state.
- `seg_plain` and `seg_fscs` are a controlled pair — same displacement, same
  segment **base value** (`0x1000`), same instruction shape, same flat state,
  differing only in the override register — and only the `CS` one loses its
  base.

So the defect is **the `CS` override on a data reference, when `DS`/`ES`/`SS`
bases are all zero**. On a 386 the override applies unconditionally in every
row above, so every "base dropped" row is a divergence on the emulator's side,
not in Links 386 or in 386|DOS-Extender. The earlier attribution to a
translator "flat mode" optimisation was an inference from a correlation; this
replaces it with a measurement, and narrows it — the condition involves the
default bases, but the *victim* is `CS` alone.

**Consequence: the `10049` boundary is an artefact of the QEMU oracle, not a
property of the game.** That retro-explains everything this document already
recorded about it — why enlarging either P3 record's interrupt-stack pool
changed nothing, why removing EMM386 changed nothing, why 32 MB changed
nothing, and why the recursion is unbounded: the handler re-executes the same
wrongly-addressed load. `-cpu pentium` reproduces `10049` identically, so it
was never a CPU-model selection either.

Nothing observed past the mouse/keyboard gate under this QEMU is evidence
about Links 386 until the oracle is fixed or replaced.

### Three further measurements on the defect

**It is decided per execution, not cached per code address.** `seg_twice`
executes the same load at the same address twice, with the default bases
non-zero for one pass and zero for the other. Pass 1 reads `CS.base + 0x3F8`
and pass 2 reads `0x3F8`; `seg_twicerev` reverses the order and the answers
reverse with it. So the emulator tracks the current segment state
deterministically — this is not a stale translation, and no warm-up or
ordering trick avoids it.

**It is not new, and not specific to this host.** `work/qemu_out/links-y.log`
was captured under the Windows QEMU build recorded above, a different build on
a different host architecture, and it shows the identical
`v=0d e=ff50 IP=0008:00002136` chain. Two independent QEMU builds diverge the
same way, so this is not a fresh 11.1.1 regression and there is no reason to
expect a nearby release to be sound. Which versions are affected is still
unmeasured — only 11.1.1 is installed here.

**Patching the game around it is not a workaround.** As a diagnostic,
`work/patched/LCD.EXE` replaces all 25 `mov ds, cs:[0x3F8]` sites with the
extender's own immediate idiom `push 0x10 / pop ds / nop` — seven bytes for
seven, no structural change, and equivalent because the slot is measured
`0x0010`. Staged into the derived `img/links386_qemufix.hdd`, **the `10049`
disappears.** That closes the causal chain end to end: remove the reads that
the emulator misaddresses and the fault recursion does not happen.

It then fails at the next one. The run reports `Abnormal program termination:
Memory protection fault, CS:EIP = 0008h:0000B7EAh` — resident `0xC357EA`,
which is the `pop ds` of

```text
0xC357DE  cd 21                    int 0x21           ; the AX=2510h call
0xC357E0  83 c4 06                 add esp, 6
0xC357E3  2e ff 35 f8 03 00 00     push dword cs:[0x3F8]
0xC357EA  1f                       pop ds
```

— the same variable through a different instruction form, in the very caller
this document already identified. A sweep of the bound image finds ~40
references to `cs:[0x3F8]`, ~42 to `cs:[0x3FA]` and ~48 other CS-relative
references (linear disassembly from each prefix byte, so an upper bound).
Patching them all would be rewriting the extender, which destroys the fidelity
that makes the oracle worth having. **The fix belongs in the emulator.**
`work/patched/` and `img/links386_qemufix.hdd` are diagnostic artefacts and are
not a behavioural authority for anything.

### Next measurements

1. ~~Read MZ-side `[0x587C]` out of the guest at the mouse prompt and again
   after the fatal return.~~ Done; `0x0010` at both.
2. ~~Add a `Z2` write watchpoint on linear `0xC2A3F8`.~~ Done; four writes, all
   in startup, the last the extender's own relocation copy. No writer exists.
3. ~~Confirm the emulator divergence with a minimal protected-mode test
   case.~~ Done; `work/segtest/`, five variants, see the table above.
4. Get a correct oracle before continuing behind the gate. Patching the game
   is ruled out (above), and so is waiting for a nearby QEMU release, since two
   independent builds already diverge. What is left:
   (a) report it upstream — `work/segtest/UPSTREAM.md` is a ready-to-send
   report and `work/segtest/` is a self-contained reproducer;
   (b) find or build a QEMU that is correct, and re-run `work/segtest/` against
   it as the acceptance test before trusting it;
   (c) `dosbox-x` is installed and could boot `img/links386.hdd`
   (`imgmount 2 img/links386.hdd -size 512,63,16,131 -t hdd`, then
   `boot -l c`), but it would cost the whole QMP/gdbstub instrumentation stack
   the harness is built on, so it is a second opinion rather than a
   replacement.
   Whichever lands, run `work/segtest/` first, then re-run the gate and confirm
   `10049` is gone, before treating anything behind it as measured.

## Consequence for disassembly

`LCD.exp0.load`, `LCD.exp1.load` and `LCD.exp1.expanded.load` are derived
images, not new source files. The first conservative listing covers only the
MZ load module; the expanded EXP 1 image is now suitable for fixed-address
32-bit disassembly. `EIP=0x7F064` being greater than the packed on-disk load
size `0x59E0C` is an expected container consequence, not evidence of a bad
header parse.

The MZ header has `e_ss:e_sp = 2B0C:0064`, which lands at the MZ image end
when combined with the `0x1400` header. The first entry bytes are a 16-bit
startup sequence containing a short jump and two far calls. The P3 records and
the expanded EXP 1 image now identify both sides of the container; only the
final indirect MZ-to-P3 hand-off remains open.

The CD also contains `INSTALL.EXE`, `INSTALL2.EXE`, `BOOT.EXE` and
`AUTOBOOT.EXE`. They are installer/launcher candidates, not substitutes for
the game target. `INSTALL.INI` identifies the files copied by the minimum
installation; `tools/stage_install.py` records that selection reproducibly.

## Open questions

- Is EXP 0 the bound stub's runtime/descriptor payload, and how does the MZ
  startup chain connect the validated object to the EXP 1 loader?
- What is the complete MZ-to-P3 hand-off sequence, including selector setup and
  the transition to EXP 1's recovered entry at `EIP=0x7F064`?
- How does the static dispatch path at `0x3447` populate `[0x1BD6]` before forming
  `[0x5BB4] << 16 | [0x1BD6]`, and how does that offset relate to EXP 1's
  recovered entry?
- ~~What writes `0xFF50` to the extender's `CS:0x3F8`?~~ **Closed: nothing
  does.** A `Z2` write watchpoint traps four writes in a whole run, all in
  extender startup, the last being the extender's own relocation copy, and the
  slot holds `0x0010` at the fault. `0xFF50` is the `#GP` error code for
  selector `0xFF53`, which is the word at linear `0x3F8` — the address the
  faulting instruction actually dereferenced.
- ~~Does the emulator drop an explicit `CS` override on a data reference when
  `DS`/`ES`/`SS` bases are all zero?~~ **Yes, confirmed** by `work/segtest/`
  on QEMU 11.1.1, with a controlled `FS`-versus-`CS` pair isolating the
  override register as the only difference. Which QEMU versions carry it, and
  whether another emulator gets the gate right, are open.
- Why is a ring-0 `INT 21h AX=2510h` issued from `0xC357DE` inside that window?
  The window itself is no longer suspicious — the mirror is correct throughout
  — but the call is still the entry that meets the addressing divergence.
- Which files are needed to reach the title/menu without a mounted CD?
