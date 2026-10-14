# CPU arithmetic and Falcon platform compatibility

## Contract and scope

Stock Falcon **MC68030 at 16 MHz remains the primary CPU target**. The current
program requires 14 MB ST-RAM; this work does not make it fit a 4 MB Falcon.
`TARGET_CPU=68060` selects a separate image for a Falcon with an MC68060
accelerator, compatible supervisor OS, and the same VIDEL/MFP/IKBD hardware.
It does not select a different game, precision level, renderer or replay.
The CPU attract route is the validation scope; physical accelerator acceptance
and the existing open DOS/full-game parity gates remain separate.

The arithmetic implementation may change with the architecture. Its recovered
DOS numerical semantics may not: operand width, signedness, wrap, carry, shift,
division and rounding/truncation boundaries are part of each function's
contract. Internal multiword representation is allowed when canonical results
match. There is no new floating-point, saturation or reduced-precision path.
VGA palette-to-VIDEL RGB565 conversion is a documented presentation exception;
it does not authorize quantizing flight state, projection or fixed-point math.

## Byte-order boundary

DOS x86 is little-endian; both supported m68k CPUs are big-endian. Endianness
changes the encoding in memory, not precision or the value used by arithmetic.
Decode original numeric fields once at the loader boundary. Keep original
assets byte-for-byte, native runtime state in target order, and generated m68k
numeric tables already in target order. RGB565 words use target memory order;
browser RGBA output is a separate serialization. Do not swap an entire asset:
ASCII tags, palette channels, pixels and compression tokens are byte streams.

The inspected production readers already implement this distinction:

| Boundary | Existing mechanism |
|---|---|
| `demo_start` / `demo_tick` | Explicit LE32 X/Y/angle/length assembly and LE16 replay axes into native state |
| `dtl_build` and its swap helpers | Decode original LE32 coefficients before exact integer products |
| DTA and SG/KRL loaders | Decode numeric dimensions/offsets; retain tag, pixel and palette byte order |
| `mission_decode` | DOS XOR `0x11120603` has bytes `03 06 12 11`; native XOR constant is `0x03061211` to preserve those bytes |
| Browser `dos-data.js` | Explicit byte readers with signed conversion, independent of host byte order |

No extra swaps are needed merely to move from 68030 to 68060. Native raw
memory is not directly comparable to a little-endian DOS state dump: decode
fields before comparing canonical values. The attract harness additionally
checks the loaded replay header and first signed axes against an independent
Python decode of the original file. The browser proof compares every installed
replay header/axis record with Node's explicit little-endian readers.

## Exact product seam

DOS identity is inherited from the consuming records in
[falcon-attract.md](falcon-attract.md),
[the semantic map](../../docs/X86-M68K-MAP.md), and their per-site DOS addresses.
The helper itself is **N/A — platform replacement**, not a recovered game
function. The authority remains `COMANCHE.UNPACKED.EXE`, SHA-256
`4498ab2b797379a492208aed4ed1947bcea0dccde3363fb98d03e8318cefd697`.

The [MC68060 User's Manual](https://www.nxp.com/docs/en/data-sheet/MC68060UM.pdf),
appendix C, lists 32×32→64 integer multiply as unimplemented. vasm accepting
`muls.l d3,d1:d0` under `-m68060` does not guarantee native execution: using it
can require the OS integer emulation package. Ordinary 32-bit-result long
multiply and 32-bit-dividend long divide are distinct supported forms.

`src/inc/cpu.s` isolates all existing wide-product sites in `dtl.s`, `flight.s`,
`hud.s`, `object.s`, `render.s` and `view.s`:

| Interface | Inputs | Outputs | Preserved |
|---|---|---|---|
| `MulS64 source` | signed d0, source | d1:d0, high:low | all other registers |
| `MulS64D2` | signed d0, d1 | d2:d0 | d1 and other registers |
| `MulU64D2` | unsigned d0, d1 | d2:d0 | d1 and other registers |

CCR is scratch; callers consume the numerical result and establish their own
subsequent branch flags. Existing truncation/shift instructions remain at the
call sites. MC68030 expands these macros to its original native instruction.
MC68060 calls `cpu_mulu64`/`cpu_muls64` in `src/cpu.s`:

- Four unsigned 16×16 products are accumulated with carries into all 64 bits.
- Signed multiplication subtracts the opposite unsigned operand from the high
  half for each negative input. This produces the signed two's-complement
  product modulo 2^64, including INT_MIN, without an absolute-value overflow.
- There is no allocation, FPU, DOS-visible state or exception-emulation package
  dependency. The helpers preserve their non-result registers and balance the
  stack. Their target-only implementation has no separate browser game rule.

Difference ledger: instruction sequence, scratch CCR, code size and execution
cost differ; numerical outputs do not. The 68030 hot path retains its native
operations. The existing browser Q31/DOS fixtures continue to define the same
consuming functions; CPU-to-CPU equality alone is not proof against DOS.

## Program placement

The 68060 image is linked with PRG flags 7 (fastload, load into TT-RAM,
Malloc from TT-RAM); the 68030 image keeps flags 1. An accelerated Falcon's
ST-RAM sits behind the 16 MHz bus shared with Videl, and the program's 8.3 MB
of BSS - maps, persistent surface, sprite banks - is the working set. Every
buffer a device reads is allocated with `Mxalloc(...,0)`: both scanout pages
(`start.s`) and the sound DMA ring (`sound.s`). On a machine without TT-RAM
the flags are ignored. Measured in Hatari's 060 profile this alone moved the
cockpit benchmark from 7.9 to 13.6 fps; see
[the 68060 performance record](../../docs/PERFORMANCE-2026-10-14-68060.md).

## Vectors and framebuffer publication

`start.s` reads VBR after entering supervisor mode. Exception, VBL and IKBD
install/restore operations address that table instead of assuming address zero.
The program leaves VBR and the OS cache policy unchanged. `ScreenCachePush`
emits `CPUSHA DC` only on MC68060, before publishing RGB565 writes to VIDEL and
after vector updates. The VBL publication also pushes pending stores to cover
an interrupt between the buffer swap and the main publisher.

These are **N/A — Falcon platform replacements**. Hardware can observe RAM
independently of a copyback cache; an instruction-compatible renderer alone is
not sufficient. Full-cache pushes are conservative, with accelerator timing
still unmeasured. No MC68030 cache operation is added. Relocated-VBR execution,
physical cache/scanout behavior and accelerator-specific OS teardown still
require hardware acceptance; VBR-zero emulator startup is not that proof.

## Reproduction and evidence

Build from the repository root with the installed original assets:

```sh
bash tools/build-run.sh
TARGET_CPU=68060 bash tools/build-run.sh
python3 tools/check-cpu-compatibility.py
python3 tools/check-attract-timing.py
python3 tools/check-attract-timing.py --cpu 68060
python3 tools/check-attract-timing.py --even-pass
python3 tools/check-attract-timing.py --cpu 68060 --even-pass
node tools/prove-browser-attract.js
```

Outputs are separate: `release/` and `release/68060/`, with CPU-specific object
directories. `TARGET_CPU=68060 bash tools/run.sh` selects the accelerator image
and Hatari CPU level 6. The default runner keeps TOS 4.02/68030. The 68060
runner defaults to the sibling EmuTOS ROM; set `TOS` to a ROM supporting that
CPU, and `HATARI`, `VASM` and `VLINK` to override tools. Neither test uses an FPU
or DSP. These emulator checks are correctness checks, not accelerator speed
measurements.

Validation tools: vasm 1.7b (M68k backend 2.0d, Motorola syntax 3.6c), vlink
0.15, Hatari 2.6.1 on macOS. Both CPU fixture runs use the same EmuTOS ROM,
SHA-256 `0bf89da31af7039b79261383242193fe44afaf3733e05ad6e87bd24a0450a20a`.
Tool paths, executable hashes and version output are retained in
`build/cpu-toolchain.json`. This pins the tools actually exercised rather than
assuming a sibling checkout's current binaries are interchangeable.

The arithmetic harness executes 1,193 operand pairs, four interface forms per
pair, on each CPU: **4,772 exact products per CPU, all passing**, including
register-preservation checks. Python arbitrary-precision integers independently
compute expected signed and unsigned outputs. Both dumps have SHA-256
`937041ae93416fedbcada0156326185e874a2557b9c1c7f0057b2645c147872c`.
Generated assembly, actual command, logs and result JSON are retained under
`build/check-cpu-{68030,68060}/`.

The attract harness observes each screen tick, waits for a completed flight
publication, checks the exception marker, and dumps the RGB565 framebuffer and
camera state. It tests 600 title/300 side-screen ticks and the existing silent
port's 480-tick fanfare policy. Its `--even-pass` debugger seed selects the other
opening; it does not claim a complete four-pass replay test. Run artifacts are
under each image directory as `timing-*`; archive them before the next run.

On 2026-09-05, both CPU builds completed the odd-pass countdown and first
flight publication without a captured exception. First-frame RGB565 and camera
bytes matched across CPUs. The frame SHA-256 is
`2129902495dea4999975cf0f30a7008d2ccb1d4f1567d8f117c9edd3b847cca9`.
Artifacts are archived in `build/attract-{68030,68060}-odd/`. Hatari needed VBL
2442 on MC68030 and 26582 on MC68060; the latter was still doing palette
remapping at VBL 23999. This is not a measured physical accelerator slowdown.

Both CPU builds also passed the debugger-selected even opening: exactly 300
side-screen ticks followed by a completed flight frame, with equal camera and
RGB565 bytes. Frame SHA-256:
`a80f70a2bfbbf58b484fca97411a7203cb6345526cfe77bb92642467cbc72a06`.
Artifacts are in `build/attract-{68030,68060}-even/`.

An emitted-TEXT instruction audit found 16 full-width multiply sites in the
68030 image and zero in the 68060 image. No MOVEP/CHK2/CMP2/CAS2/CALLM/RTM
instructions were found in either. This bounded audit supplements the vendor
manual and the execution tests; it does not prove every possible instruction
path or OS service compatible. The browser attract proof passed all seven
groups, including source links, DOS Q31 arithmetic, assets, transitions,
objects, terrain and sprite projection.
