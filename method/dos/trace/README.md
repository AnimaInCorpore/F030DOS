# Execution telemetry for the DOS oracle

The family's answer to the question a static sweep cannot answer: *which bytes
are actually code?* A QEMU TCG plugin records what executed; a calibration step
ties those guest addresses back to file offsets.

This is the DOS counterpart to the telemetry MAME feeds `jsm68kdisassembler`
in F030Arcade, with one structural advantage: QEMU exposes a supported plugin
API, so there is no emulator fork to maintain.

## Address and dump rules

Keep DOS `seg:off`, guest physical, guest linear and file-offset coordinates
separate. In real mode, physical/linear is normally `(seg << 4) + off`, subject
to A20 and wrap rules. Protected-mode DOS extenders add selector, descriptor
and DPMI state; record those before translating an address. A segment:offset or
linear address is not automatically a file offset or a Ghidra address.

QEMU's monitor uses `x` for virtual memory and `xp` for physical memory;
`pmemsave` saves physical memory. Consequently,
`pmemsave 0 0xA0000 ram.bin` ends at `0x9FFFF`; it does not dump the VGA
aperture. Capture that separately, for example:

```
pmemsave 0xA0000 0x20000 vga-aperture.bin
```

Preserve VGA registers and palette state alongside the dump. The IVT is at
physical address zero; protected-mode captures additionally need the IDT,
GDT/LDT and DPMI state.

## Packers and coverage exports

`-d in_asm,exec` identifies executed translation blocks, but it is not an
unpacked-image dump or a stable per-byte coverage format. When a packer reaches
its decoded entry point, capture RAM or the relevant memory writes at that
transition and validate the bytes against the runtime map. Use the shared TCG
plugin for per-byte execution telemetry. `drcov` output is optional
visualization glue: rebase it to the analyzed image and preserve scenario,
overlay-unit and file-offset identity when overlays reuse one address.

The QEMU GDB stub is useful for stopping and correlating state from Ghidra or
IDA, but it does not infer segment bases, loader mappings or reliable C types.
DOSBox-X's debugger remains the complementary interactive DOS workflow; use a
hardware emulator only when timing or device compatibility requires it.

Flags byte layout:

| bit | name | meaning |
|---|---|---|
| 0 | `EXEC` | byte was part of an executed instruction |
| 1 | `START` | an executed instruction began here |
| 2/3/4 | `R8`/`R16`/`R32` | read as a byte / word / long |
| 5 | `WRITE` | written |
| 6 | `SEXT` | at least one read was sign-extended |

Bits 2-6 need `--mem` and record accesses made by code *inside* the window,
i.e. by the program rather than by DOS reading into its buffers.

**It does not generate a port.** The arcade pipeline gets a Falcon port almost
free because 68000 → 68030 is the same ISA, so its disassembly *is* the port
and a byte-identical rebuild proves it. x86 → 68030 has no such property.
What this buys is *traceability*: every byte it marks is code because it ran,
not because a heuristic said so.

## Parts

| File | Role |
|---|---|
| `x86trace.c` / `Makefile` | The TCG plugin. One flags byte per guest linear address: `EXEC`, `START`, read widths, `WRITE`, `SEXT`. Also tallies I/O ports and can log DOS calls. |
| `run_trace.py` | Boots an oracle image with the plugin attached, drives it with keys, screenshots, dumps RAM, and quits *gracefully* over QMP. |
| `trace_coverage.py` | Votes on the load base by hunting load-module windows in the RAM dump, then reports coverage against the MZ image. |
| `trace_overlay.py` | Folds overlay-buffer coverage onto the overlay *file's* offsets, so units that shared an address stay separate. |

```
make
python trace/run_trace.py --hdd img/por.hdd --seconds 60 \
    --lo 0 --hi 0xA0000 --out work/por.trace \
    --memdump work/por.ram --memdump-at 40 --shot 40
python trace/trace_coverage.py --exe work/expanded/START.EXE \
    --trace work/por.trace --ram work/por.ram --data-from 0x7400

# overlay units, keyed to GAME.OVR's own offsets rather than to addresses
python trace/run_trace.py --hdd img/por.hdd --seconds 55 \
    --lo 0 --hi 0xA0000 --out work/por.trace \
    --memdump work/por.ram --memdump-at 45 \
    --ovl work/por.ovl --ovl-lo 0x1F000 --ovl-hi 0x40000
python trace/trace_overlay.py --ovr work/expanded/GAME.OVR \
    --flush work/por.ovl --ram work/por.ram
```

```
# data-access widths + every I/O port the guest touches
python trace/run_trace.py --hdd img/por.hdd --seconds 55 \
    --lo 0 --hi 0xA0000 --out work/por.trace --mem --io work/por.io
```

`--int21log` dumps the raw DOS calls if you need to see what the overlay
manager is doing. Note that a register handle of 0 is *valid* (it is `eax`),
so plugin code must track found-ness separately -- treating the handle as a
pointer and null-checking it silently zeroes every `eax` read.

Two rules the implementation exists to enforce:

- **Quit through QMP, never SIGKILL.** The sidecar is written from the
  plugin's atexit callback; a killed QEMU produces no telemetry at all.
- **Schedule the RAM dump, don't defer it.** The guest can end the run itself
  (POR walks into its copy protection and exits, taking QEMU with it), so a
  dump left to the timeout path may never be written. `--memdump-at` exists
  because that happened.

## Measured on Pool of Radiance, 2026-08-23

Against `work/expanded/START.EXE` (load module 46,992 B), booting `img/por.hdd`
on an untouched copy of the image.

**Calibration.** 45 of 61 distinctive windows agreed on load base `0x107A0`
(segment `0x107A`), reproduced identically across three separate runs. The
independent confirmation is that `START.EXE +0x6` shows as executed — exactly
the `e_ip = 0x0006` in the MZ header.

**Coverage.**

| Run | Load module | Code region `0x0..0x7400` | Data region `0x7400..EOF` |
|---|---|---|---|
| Undriven, 60 s | 9,364 / 46,992 = **19.9 %** | 9,364 / 29,696 = 31.5 % | **0 / 17,296 = 0.0 %** |
| Driven with keys | 9,716 / 46,992 = **20.7 %** | 32.7 % | 0.0 % |

For comparison, `analysis/executables.md` reports the static disassembler
covering 10,290 / 46,992 B = 21 % of the same image.

**What the numbers say.** Dynamic coverage is not higher than the static
sweep, and chasing a bigger percentage is the wrong reading. Two things are
new. First, the known-data guard is *exact*: zero bytes executed in the 17,296 B
DGROUP region that `analysis/executables.md` had independently declared data by
construction — two methods, arrived at separately, agreeing perfectly. Second,
every marked byte is proven code rather than inferred, which is the property
`no-invention` actually needs.

**The cliff: copy protection.** An undriven run stalls on the translation-wheel
code word, and wrong answers make `START.EXE` exit (which ends the QEMU run).
Coverage past ~21 % is gated on answering the wheel, not on longer runs — the
driven run added only 352 bytes. Getting the harness through that prompt is the
highest-value next step, and is worth more than any amount of extra runtime.

**Overlays are the real limitation.** `GAME.OVR` content was located resident
between `0x22000` and `0x3E000`, with roughly 8.3 KB executed inside it. This
plugin keys telemetry by *linear address*, so two overlay units occupying the
same address at different times merge into one indistinguishable record. POR
(Turbo Pascal `TPOV`, 38 units) and UW1/UW2 (Borland `FBOV`) all do exactly
that. Overlay-aware keying — `(unit, offset)` rather than address — is the
prerequisite before these numbers mean anything for overlay code.

## Hardware surface, measured (POR, 2026-08-23)

`--io` tallies every `in`/`out` the guest executes and records the PC that
first touched each port. No QEMU contrib plugin does this: `hwprofile` covers
memory-mapped device regions only (`qemu_plugin_hwaddr_is_io`), and DOS-era
hardware is programmed through port I/O.

Attributing each port to the code that first touched it separates the game
from the machine around it. 24 ports were touched; **9 of them are the
game's**:

| origin | ports |
|---|---|
| `START.EXE` | `0040` `0042` `0043` (PIT), `0061` (speaker gate), `00C0`, `03CE`/`03CF` (VGA graphics ctrl) |
| an overlay unit | `03C4`/`03C5` (VGA sequencer — 48,371 writes, the map-mask plane writes) |
| DOS/BIOS/TSR | `0020` `0064` `0070` `0071`, and two port-probe sweeps at `02F2-02F7` / `06F2-06F7` |

That table is the hardware half of the substitution list §4.2 of `METHOD.md`
asks to be enumerated and closed — produced mechanically instead of read out
of a disassembly by hand.

One reading worth checking rather than trusting: `00C0` takes **136,299
writes** from `START.EXE`, which is a lot for the DMA controller that
normally lives there. Port `0xC0` is also the SN76496 on Tandy 1000 / PCjr,
and a 1988 SSI Gold Box title supporting Tandy sound would fit — but nothing
here proves it, and the port list cannot tell you which device the game
*thinks* it is talking to. Treat it as a lead into the disassembly.

## Data widths, measured

With `--mem`, the same POR boot records 253,108 bytes read as `R8`, 244,054
as `R16`, 435,034 written — the evidence for what is a `char` and what is a
`short` when writing the 68k structs.

**`SEXT` is much weaker than it looks on 16-bit targets, and the count says
so: 10 bytes in the whole run.** The flag catches sign-*extending loads*, and
16-bit x86 barely has any: it sign-extends in registers with `cbw`/`cwd`
after an ordinary load, which is invisible to a memory callback. So width is
well evidenced here and signedness essentially is not. Recovering signedness
still means reading the code — `../F030F29/docs/X86DISASSEMBLE.md` §2's
`0x80`-and-up trap is still paid the hard way. Expect `SEXT` to be worth more
on the 32-bit siblings (TIE, CMN) where `movsx` is common.

## Measured on Ultima Underworld 1, 2026-08-23

The Borland `FBOV` case, previously untested. One 130 s boot of `img/uw.hdd`
driven `esc`, `esc` (title → intro cutscene → main menu), window `0..0xA0000`,
overlay window `0x69290..0x6E000`.

**Calibration reproduced a number measured another way.** 49 of 87 windows
vote load base `0x5960` — the value UW1's QMP signature probe had arrived at
months earlier. Two independent methods, same answer.

**The known-data guard came back exact**: **0** of the 30,784 B between the
measured DGROUP and the end of the load module executed, against 42,867 /
377,072 = 11.4 % of the code region. The same clean split POR produced.

**Overlay keying carried to `FBOV` unchanged, and better than on POR**: 418
flush records, 15 with executed bytes, **15 of 15 identified by content**
(100 %), 16,349 pool bytes attributed to units and written keyed by file
offset. The reason it is easy here is worth stating: UW1's overlay manager
loads units with ordinary `INT 21h AH=3Fh` reads, so `--int21log` alone gives
(file offset, buffer, length) per load — 25 of its 26 reads are exactly one
unit, `len == code + fixups`.

**What the run could not see**: UW1 caches overlays in EMS (14 `INT 67h` sites
inside the overlay-manager segment alone), and three units executed with no DOS
read in the log. `--int21log` does not cover `INT 67h`; **an EMS log is the obvious
next feature** for any game that needs `EMM386`.

Full write-up, including the overlay map the telemetry confirmed:
`F030Underworld/analysis/uwexe.md` §13.6 + §14.

## Status

Prototype, exercised on two games (POR / Turbo Pascal `TPOV`, UW1 / Borland
`FBOV`). Deliberately **not** in `dos/sync.py`'s `SHARED` list: no project
carries a copy — every user invokes these masters by relative path
(`../F030Method/dos/trace/...`), so there is nothing to sync. The Makefile
has an MSYS2 recipe producing `x86trace.dll` (needs a QEMU built with plugin
support plus its `libqemu_plugin_api.a` import stub — point `QEMU_IMPLIB` at
it); that recipe has not yet been exercised against a real Windows QEMU, so
CMN's `work/run_qemu_exec_trace.py` remains the `-d exec,nochain` fallback
until it is.

Overlay keying works on both overlay families; the flush-and-identify approach
assumes nothing beyond "DOS reads overwrite the buffer", which is why it
carried across unchanged — and it is also exactly the assumption an EMS-cached
load breaks (UW1, above).

POR coverage of overlay code is 3.1 % against the static disassembler's 80 %,
and the gap is the copy-protection wheel, not the method. UW1's 11.6 % of pool
bytes is likewise a statement about the run (front end only, no Create
Character), not about the binary.

The read-width/write/sign-extension bits (`R8`/`R16`/`R32`/`WRITE`/`SEXT`,
the flags table above) are implemented behind `--mem`; of the arcade
sidecar's extras only `CODE_POINTER` remains unimplemented. The `--ovl`
interaction is resolved: each flush still clears its region's live flags (so
the next resident unit starts clean), but the flushed coverage is folded
into a union array and `--out` reports that union — the two outputs compose,
and the overlay window is required to nest inside `--lo`/`--hi` (the plugin
refuses to start otherwise).
