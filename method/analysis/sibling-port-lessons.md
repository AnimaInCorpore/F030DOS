# Lessons from the non-DOS Falcon ports for the DOS-family ports

Surveyed 2026-10-05, after [the F030CT translator review](f030ct-translator-review.md)
(which this note does not repeat). Source: a read-only directory survey of the
sibling SNES, console, arcade and audio repos beside this one. **Every path
below was checked to exist; the numbers and claims were taken from those
repos' own notes and were not re-measured here.** Treat each item as a lead to
confirm in the DOS port that adopts it, not as verified policy. These repos are
external technique providers, not `README.md` manifest members; no media,
source or hardware requirement is adopted from them.

## Audio: the largest direct reuse

All of the manifest's AdLib/Miles games (PG, UW1/UW2, F3, ICR, MC, TIE) share
this need, so it is recorded once here.

| # | Lead | Where | Use for a DOS port | Status |
|---|---|---|---|---|
| 1 | OPL2 on the Falcon DSP: nine two-operator channels at 49.17 kHz, a 68030-side register decoder, a MIDI player and a register-trace player (`W <µs> <t\|g> <reg> <val>`) | `F030OPL2`: `tools/opl/dsp/oplrt.asm`, `tools/opl/opl-practical.h`, `tools/opl/midi/{period-stream.h,opl-upload.h}`, `tools/opl/rt-fixture.cpp` | Reuse the DSP, decoder and stream; feed it the game's own register writes | Working, emulator only; DSP output is bit-exact against its **own** integer host model, which is block-rate (32-frame) and "not chip exact"; worst period 94% of the DSP budget; no listening test; no hardware |
| 2 | Miles AdLib driver and bank loader | `scummvm/audio/miles_adlib.cpp`, `midiparser_xmidi.cpp`; Falcon glue `scummvm/backends/platform/atari/dsp-opl.cpp` | Reference for AIL bank (`STDPATCH.AD`) lookup and the driver-to-`writeReg` path | Working C++ (GPL); needs stripping of ScummVM types |
| 3 | Sound transport discipline | `F030Arcade/PORTING.md` ("Sound strategy", "DSP as co-processor"), `games/snowbros/SOUND_DRIVER.md` | Drop unchanged register writes, stamp each write with the driver's clock, pump a queue from a timer without waiting for DSP replies, batch writes, pace the driver from a clock not a call count | Measured process |
| 4 | MT-32 decision data | `F030MT32/docs/{la32-budget,live-performance}.md`; `scummvm/devtools/atari-falcon030/tools/mt32-sample-bank/RESIDENT.md` | Live synthesis reaches only about 2-4 notes; treat AdLib as the supported device for MT-32 titles and MT-32 as prerender or sample-bank only | Measured |

F030OPL2's MIDI work and its corpus gate (`tools/opl/midi-corpus.py`, 244 songs
across Falcon 3, Underworld 1/2, Panzer General and Ultima 4; the 20 densest
played with no late period) cover **five games, not each one fully**: its
instruments are ScummVM's General MIDI AdLib bank, not any game's Miles bank, and
`xmi2mid.py` drops XMIDI controllers 110-120 (the format's loop and callback
controls) and does not unroll loops. See Panzer General's
[`analysis/audio.md`](../F030PanzerGeneral/analysis/audio.md) for the worked
assessment and the DOS-register-capture plan.

## Verification and tooling

| # | Lead | Where | Use for a DOS port |
|---|---|---|---|
| 5 | DSP-calibrated Hatari: stock Hatari runs the DSP at twice hardware speed and mis-models the host port | fork at `F030Arcade/third_party/hatari`; `F030Arcade/DEBUGGING.md` ("DSP runs at twice hardware speed", `dp on`/`dp stats`, `--run-vbls prg:N`); `F030MXDRV/tools/hatari_binary.py` warns on a non-calibrated binary; `F030TREX/OPTIMIZATION.md` §2.7 (first hardware run 2.06x slower than the emulator, identical output bytes) | Use the calibrated build for every DSP timing claim. **F030POR uses Homebrew Hatari and METHOD.md has no such policy yet.** |
| 6 | DSP kernel gate: host C model, bit-exact word comparison on random frames under Hatari, cycle profile between labels | `F030OPL2/tools/opl/{rt-bench-gate.py,profile-labels.py}`, `F030OPL2/docs/validation.json` (records source hashes), `F030SID/tools/profile_dsp.py`, `F030CT/tools/{dsp_model.c,dsp_rand.c}`; native DSP assembler without DOSBox: `F030Arcade/scripts/assemble-dsp.sh` | Template for any DSP offload (c2p, audio, terrain) |
| 7 | Host 68030 model harness: machine68k/Musashi plus vasm, emitted sequences checked against a reference for every live-flag subset; whole-program runs checksum state every N interrupts | `F030CT/tools/{emit_bench.py,emit_tests.py,ctx_run.py}` | Fits x86 flag lowering (ADC/SBB, shifts, DAA). The x86 reference semantics must be written; cycles from the model are relative only |
| 8 | Native hook with check mode: run the native routine, restore state, run the translation, compare memory; interrupts masked for the native pass | `F030CT/tools/smkx/natives.txt`, `falcon/ct_lz.s` (`CTX_LZ_CHECK=1`), `F030SMK/analysis/porting-notes.md` (~l.1714: 311 of 340 calls identical, about 10x per call) | Hot decompressors and `rep movs` loops |
| 9 | 030 measurement idioms | `F030FFVI/scripts/{smkx_profile,smkx_pc}.py` (timer-C PC sampling mapped to source routines); `F030CT/scripts/tc_bench`; `F030TREX/OPTIMIZATION.md` §3.9 (instruction-cache ladder: a 552-byte loop shrunk to 248 bytes gave -38% at identical output) | Profile before tuning; keep an output hash with every microbenchmark. A wall-time counter is not CPU time (`F030SMK/analysis/porting-notes.md` ~l.2088) |
| 10 | NatFeats stderr channel and routine-test recipe | `F030CT/falcon/tctest.s` (ten-line `nf_id`/`nf_call`); `F030Arcade/DEBUGGING.md` ("Regression-test a routine without a debugger": extract routines by label, use synthetic inputs, make the stub callee clobber every register outside the routine's contract) | Cheap per-routine native tests |

## Output runtime and data layout

| # | Lead | Where | Note |
|---|---|---|---|
| 11 | 030 chunky-to-planar (8bpp full-screen, rect and 4bpp) and a DMA double-buffered mixer with a starvation silence loop | `scummvm/backends/graphics/atari/atari-c2p-asm.S`, `scummvm/backends/mixer/atari/atari-mixer.cpp` | Useful for VGA-mode games and Sound Blaster digital audio. The DSP-side SSI-DMA c2p is the stronger measured result (786 KB/s each way, bit-exact) but cannot coexist with DSP OPL audio and is unproven on hardware. Videl base: write the low byte last (`F030SMK/analysis/porting-notes.md` ~l.2625) |
| 12 | Endianness idioms | `F030CT/analysis/translator-speedup.md` (byte swaps were 9% of CT's instructions); `ASM56000/CLAUDE.md` | Keep guest memory little-endian, 16-bit access as `move.w` plus `ror.w #8`, read-only tables with a big-endian twin view; never read or write structs raw, use byte-wise helpers. Lazy swapping per register is untested |

## Not adopted, and why

- 65816 translator internals, PPU/Mode 7/HDMA compositors, tile planners, SPC700
  and `ref65816` pieces: SNES-specific; the ideas that transfer are in the F030CT
  review.
- DSP true-colour renderers: chunky RGB565 measured slower than planar
  (`F030SMK/analysis/porting-notes.md` ~l.1664).
- SSI-DMA c2p as the default display path: conflicts with DSP audio, no hardware
  evidence.
- Live MT-32 synthesis; F030MXDRV (YM2151) and F030SID: wrong chip or infeasible.
- F030Arcade 68k-to-68k relocation, JIT and MAME-cheat harnesses.
- F030AUX, F030PicoDrive and the Amiga/PiStorm material (hardware or OS
  projects); `f030finalfight` and `f030galaga88` (plain ports, no reusable
  tooling).
- Absolute emulator speed figures: use them only for A/B comparisons.
- The SNES porting-notes cross-copy protocol: `gen_cross_project.py` already
  covers that role.
