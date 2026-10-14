# Rendering inner loop — IndyCar Racing v1.05

Status: `IDENTIFIED` — the 12 KB of code the practice session spends 88% of
its time in is located and characterised as a self-modifying textured-span
drawer. Its per-span constants are patched into the instruction stream at
runtime and are **not** recoverable from the executable. The framebuffer it
draws into and the live palette are `RESOLVED`. Nothing above it — the polygon
setup, the scene walk, the camera — has been located yet.

## How it was found

`work/drive_protection.py` reaches a practice session and samples the EIP
there, which is the only state where the renderer is the hot code (a sample
taken at a menu or at the copy-protection gate says only where the game
waits):

```text
python work/drive_protection.py --key 8:ret --key 16:ret --key 24:ret \
    --key 34:ret --key "48:up 40000" --dump-ram --sample 150
```

Three runs (40, 150 and 200 samples) agree. Binning the 200-sample run by
4 KB of file offset:

```text
194/200 samples resolve to a file offset, spanning 0x050487..0x09c125
  0x09a000..0x09afff   67 (33.5%)  cumulative  33.5%
  0x099000..0x099fff   62 (31.0%)  cumulative  64.5%
  0x098000..0x098fff   47 (23.5%)  cumulative  88.0%
  0x09b000..0x09bfff   12 ( 6.0%)  cumulative  94.0%
  0x09c000..0x09cfff    2 ( 1.0%)  cumulative  95.0%
```

**88% of the session's time is in file `0x098000..0x09AFFF`, 12 KB; 94% within
16 KB.** The `0x050487..0x09C125` span in the first line is the range of the
outliers, not a concentration — reading it as the hot region would be wrong by
a factor of twenty, and an earlier draft of this document did exactly that
from the top-N list alone. The individual hot addresses:

```text
 17x 0x001d9530 file 0x09a654    9x 0x001d950e file 0x09a632
  8x 0x001d8ba8 file 0x099ccc    7x 0x001d95d4 file 0x09a6f8
  5x 0x001d8c4c file 0x099d70    5x 0x001d7d2a file 0x098e4e
```

The mapping was re-measured from a RAM dump taken in the session and came back
identical to the one measured at the gate, so the load is deterministic across
runs.

## What the loop is

Disassembled from the session RAM dump at linear `0x1D94E0`
(file `0x09A604`):

```text
0x1D9516  add  esi, [esp]              ; step the source
0x1D9519  sub  edi, 5                  ; <- immediate patched at runtime
0x1D951F  jge  0x1D9528
0x1D9521  dec  esi
0x1D9522  add  edi, 0x4A               ; <- immediate patched at runtime
0x1D9528  mov  al, [esi]               ; fetch
0x1D952A  mov  [ebx], al               ; store
0x1D952C  dec  ebx                     ; walk the destination backwards
0x1D952D  dec  ecx                     ; span counter
0x1D952E  je   0x1D954E
0x1D9530  add  dword ptr [0x1D9510], 0xFFF9E4F1   ; patches its own operand
0x1D953A  add  edx, 0xFFF9E4F1
0x1D9540  add  ebp, 0xFFF3C9E2
0x1D9546  jl   0x1D9554
0x1D9548  add  edx, ebp
0x1D954A  jge  0x1D9500
0x1D954C  jmp  0x1D9516
```

A byte-per-pixel copy with a Bresenham-style error accumulator in `edx`/`ebp`
stepping the source, an unrolled set of near-identical span loops, and a setup
block above them (`0x1D955C..0x1D95BE`) that writes computed values into the
loops' immediate fields:

```text
0x1D957B  mov  [0x1D95EB], eax
0x1D9580  mov  [0x1D960D], eax
0x1D9585  mov  [0x1D9629], eax        ; one value, three copies of the loop
```

## The constants are not in the file

This is the part that matters for the port. Over the 320 bytes at file
`0x09A604`:

| Comparison | Bytes differing | Meaning |
|---|---:|---|
| file vs session RAM | 92 of 320 | fixups **and** runtime patches, indistinguishable |
| RAM at the gate vs RAM in the session | 34 of 320 | runtime patches alone |

The second row is the proof: it is the same process, the same memory, no
reload in between — only the state changed. Examples:

```text
0x1D9508   file 00 00 ff    gate 31 fd ff    session f1 e4 f9
0x1D9510   file 00 00 ff ff gate 0b c1 fe ff session 0a 41 cb fc
0x1D951B   file 00          gate 01          session 05
0x1D9524   file 00          gate 0e          session 4a
```

The file holds `00`/`ff` placeholders; the running code holds the stepping
constants for the span being drawn. Any attempt to recover this routine's
behaviour from `INDYCAR.EXE` alone recovers the placeholders. The contract has
to come from the setup block that computes the values, plus captured runtime
state — see the general rule in `../F030Method/CROSS-PROJECT.md`.

## Framebuffer and palette — `RESOLVED`


Found by correlating a screendump with a RAM dump taken at the same instant
(`--dump-ram` now takes the paired screenshot itself). The method needs no
knowledge of the pixel format: QEMU's output is a doubled 320x200 — every 2x2
block of the 640x400 dump is uniform, 0 exceptions in 64000 — so de-double it,
map distinct colours to arbitrary ids, and search RAM for a region with the
same *pixel-equality structure*. A palette is a bijection, so equality survives
it even though the values do not.

Three separate six-row slabs of the frame agree on two addresses: `0xA0000`,
VGA memory, and `0x23E130`. Over the whole frame the region at `0x23E130`
matches the picture with **0 mismatches in 63,999 adjacent-pixel comparisons**,
and `ram[0x23E130:+64000] == ram[0xA0000:+64000]` exactly.

That correlation proves "this buffer is what is on screen", which is not the
same as "this is the back buffer" — an earlier revision of this document said
the latter. The rasteriser settled it: it computes its destination as
`row * 0x140 + [0x23E12C]`, and `[0x23E12C]` reads `0x0024DB30`, which is
exactly `0x23E130 + 64000`. There are **two contiguous 320x200 buffers**:

| Buffer | Address | In both dumps |
|---|---|---|
| A | `0x23E130` | byte-identical to VGA memory — the displayed frame |
| B | `0x24DB30` | the value of the draw-target pointer `[0x23E12C]`; differs from A |

Both dumps — different runs, different game states — show the same assignment,
so the roles were never observed to swap; whether they ever do is not
established. The pitch is `0x140` = 320, and that constant is in the file as a
plain immediate (`imul eax, eax, 0x140`, file `0x098594`), identical in file
and RAM, so unlike the span loops' constants it *is* statically recoverable.

Both buffers and the palettes sit above the loaded image (which ends near
linear `0x1F42C5`), i.e. in heap the program allocated.

## The rasteriser above the span loops — `0x1D7454` (file `0x098578`)

Recovered from the stack, not from static cross-references: sampling ESP while
the renderer was hot and keeping the dwords that fall inside the image and are
preceded by a `call rel32` gives the live frames. 80 of 90 samples carried the
return address `0x1D67DE`, whose call is `call 0x1D7454` at `0x1D67D9` — and
that call site is a five-instruction tail, `call 0x1D67E0; call 0x1D7454; pop
ebp; ret` (file `0x0978FD`).

```text
0x1D7454  mov  ecx, [0x23C81C]      ; last row
0x1D745A  mov  eax, [0x23C818]      ; first row
0x1D7461  sub  ecx, eax
0x1D7463  jl   exit                 ; empty
0x1D7469  je   single-row path
0x1D746F  inc  ecx                  ; row count
0x1D7470  imul eax, eax, 0x140      ; * pitch
0x1D7476  add  eax, [0x23E12C]      ; + draw target
0x1D747C  mov  [0x23C804], eax      ; destination row pointer
0x1D7483  lea  esi, [ebx*4 + 0x23C828]    ; left-edge array
0x1D748A  lea  ebx, [ebx*4 + 0x23CB48]    ; right-edge array
0x1D7491  mov  ebp, [esi + 0x12C0]
0x1D7497  mov  edx, [ebx + 0x12C0]
0x1D749D  cmp  ebp, edx
0x1D74A1  xchg edx, ebp             ; order the pair
```

At the dump instant these read: first row 102, last row 134, destination row
pointer `0x256370` = buffer B + `109 * 320` — inside the row range, which is
what a rasteriser mid-polygon should look like.

**Per-scanline edge tables.** `0x23C828` and `0x23CB48` are 200 dwords apart
(`0x320` = 200 x 4), one entry per scanline, and are indexed by row. Untouched
rows hold `319` on the left and `0` on the right — a min/max span
initialisation. The `+0x12C0` displacement is 6 x 200 dwords, so the tables are
one block of at least six parallel per-scanline arrays; which of them are
`x`, and which are interpolated texture or shading terms, is not established.

**Dispatch is table-driven.** `0x1D67E0`, called just before the rasteriser,
is a two-level jump table keyed on a byte at `+0x10` of two objects:

```text
movzx eax, byte [edi + 0x10]
mov   ebx, [eax*4 + 0x1F4CB0]
mov   al,  byte [esi + 0x10]
add   ebx, [eax*4 + 0x1F4C30]
jmp   dword [ebx*4 + 0x1F4D30]
```

That, plus the indirect calls seen returning into the hot region, is how the
specialised span loops are selected.

The palette falls out of the same correlation, since the frame gives
index → RGB for every colour on screen. Searching RAM for those triples as
6-bit DAC values (`v = r >> 2`, exact for QEMU's expansion, which is `4v` for
even `v` and `4v+3` for odd) finds five palette-shaped 768-byte regions:

```text
0x215F94  98/109 known indices match   identical to 0x216594
0x216594  98/109
0x216E94  109/109   <- matches the displayed frame exactly
0x217194  109/109   <- matches the displayed frame exactly
0x217494  62/109
```

They are not a regular array — the blocks between them are not palettes — so
"a palette bank" would be overstating it; what is established is that at least
five copies exist in the heap around `0x215F94..0x217494` and that two of them
are the live one.

Both the back buffer and the palettes sit above the loaded image (which ends
near linear `0x1F42C5`), i.e. in heap the program allocated, not in a mapped
file region.

## The pipeline above it

Walking the call graph out of the fixed-up RAM dump (rel32 targets are valid
there, unlike in the file) gives three more layers.

### A display-list interpreter — `0x1BEDAC` (file `0x07FED0`)

```text
0x1BEDAC  lodsd                          ; next opcode from the list at esi
0x1BEDAD  jmp dword [eax*4 + 0x1EBC40]   ; dispatch
```

Threaded code: each handler ends by fetching the next opcode and jumping
again. The table at `0x1EBC40` has **19 entries**, all pointing into
`0x1BEDAA..0x1BF1AD`; entry 19 onward is a different structure (an identity
byte table `00 01 02 03 …`). `0x1BED80` and `0x1BED94` are thin wrappers that
save the registers, set `esi` to the list (from `[eax]` and from `eax`
respectively) and enter the interpreter.

This is why the stack histogram was dominated by `0x1BEE27`, `0x1BF0D1`,
`0x1BED8D` and `0x1BEDA1` — they are returns inside the interpreter, not
separate subsystems.

### A scene dispatcher — `0x1989D4` (file `0x059AF8`)

Takes a packed `eax`: index in the low 16 bits, class in the high 16. Bounds
checks the class (`cmp esi, 5; ja out`) and jumps through a 6-entry table at
`0x1989BC`. Every case has the same shape:

```text
mov  eax, [esi + 0x1FB500]   ; object pointer, table per class
call 0x1D6740                ; store 6 dwords (edx, ebx, ecx + 3 stack args)
call 0x1BED80                ; run that object's display list
```

with the per-class object tables at `0x1FB494`, `0x1FB4A8`, `0x1FB4AC`,
`0x1FB500` and the globals `0x2037E8`/`0x2037F0`. Note `0x1D6740` is *not* a
draw call — it is a six-field parameter setter that ends in `ret 0xc`.

### Span build, then rasterise — `0x1D6774..0x1D67DF` (file `0x097898`)

```text
0x1D6774  push ebp
          [0x23C820] = [0x21C9F4]      ; from globals
          [0x23C818] = [0x21C9F8]      ; first row
          [0x23C824] = [0x23C81C] = 0  ; last row cleared
          [0x23C7F4] = [0x23C7F8] = [0x23C7FC] = 0
          … lodsd / loop, calling the two-level dispatcher 0x1D67E0 per item …
0x1D67D9  call 0x1D7454                ; rasterise the accumulated spans
0x1D67DE  pop ebp
0x1D67DF  ret
```

The handlers the dispatcher reaches (`0x1D67FC`, `0x1D681B`, `0x1D683E`, …,
via the pointer table at `0x1F4D30`) call `0x1D4A0B`/`0x1D46B5`, re-enter the
dispatcher, and maintain `0x23C7F4`/`0x23C7F8` — exactly the variables this
routine clears on entry. So the loop accumulates edges into the per-scanline
tables and the tail rasterises them.

### How this routine is entered is unknown

`0x1D6774` has **no rel32 call and no jmp targeting it anywhere in resident
memory**, and searching the whole 16 MB dump for a stored dword pointing
anywhere into `0x1D6774..0x1D67DD` returns exactly one hit — `0x1D67DE` at
`0x262AA8`, which is the live return address on the stack, not a table entry.
It is neither in the interpreter's opcode table nor in the `0x1F4D30` table.
The routine demonstrably runs (its `call 0x1D7454` return address was on the
stack in 80 of 90 samples), so control reaches it by an address computed into
a register. An exhaustive pointer search coming back empty is evidence about
the *mechanism*, not about the routine.

## Not yet established

- the setup block's inputs: what `eax`, `edx`, `ebp`, `esi`, `edi` and `[esp]`
  hold on entry, and which of them are texture pitch, source step and span
  length
- how `0x1D6774` is entered (above): the address is computed, so the caller
  must be found dynamically, not by search
- what the 19 display-list opcodes do, and what produces the lists
- the camera and the transform stage: nothing between the scene dispatcher and
  the per-object span build has been identified as geometry
- which of the six-plus parallel per-scanline arrays are `x` and which are
  interpolants
- the two jump tables at `0x1F4CB0`/`0x1F4C30` and the target table at
  `0x1F4D30`: their extent, and what the `+0x10` type byte selects
- whether the several near-identical span loops are an unrolled inner loop, a
  clipped/unclipped pair, or separate specialisations per direction
- whether buffers A and B ever exchange roles, and what performs the copy to
  VGA memory
- which of the five palette regions is the source and which the working copy,
  and what the other three are for

A `METHOD.md` §4.2 function record cannot be written for the span loops yet:
their DOS contract is not recovered, only their location and their
self-modifying nature. `0x1D7454` is closer — its inputs are named variables
and its destination arithmetic is fully readable — but its edge-table contract
depends on the unlocated producer.
