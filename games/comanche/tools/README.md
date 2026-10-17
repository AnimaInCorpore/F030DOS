# Project tools

## Falcon030 toolchain

The first Comanche Falcon source slice is now present under `src/` as a
CPU-only attract-mode milestone. Its route/source boundary is recorded in
`analysis/functions/falcon-attract.md`; DSP remains dormant until its own DOS
route is traced.

Status reviewed 2026-10-10: the CPU tree now also includes live/menu/combat,
debrief and digital-effect extensions. The attract acceptance gates remain
open; these tools validate their stated contracts, not a complete game.

The Bash build currently invokes `python`. On a host exposing only `python3`,
the following tested adapter keeps the script on that interpreter without a
system installation change (run these lines in Bash):

```bash
python() { python3 "$@"; }
export -f python
bash tools/build-run.sh
TARGET_CPU=68060 bash tools/build-run.sh
```

- `build-run.sh` assembles and links the CPU-only 68030 side into
  `release/comanche.tos` and rejects DSP renderer options. Its variables:
  `TARGET_CPU=68060` the accelerator image (`release/68060/`, loaded into
  TT-RAM); `OPL2=1` the music through `../F030OPL2`'s DSP kernel (writes
  `OPLDATA.BIN`; run only with the 68060 image so far); `HWTEST=1` links
  `src/hwtest.s`, the report written to `HWTEST.TXT` at quit (see
  `docs/HARDWARE-TEST.md`); `OUTDIR` stages the build elsewhere.
- `run.sh` launches the CPU-only program in Hatari as a Falcon030 with DSP off.
- `grab-frame.sh` captures the active Videl framebuffer at a chosen VBL.
  **Do not lower the VBL count below roughly 1200** for a standalone build,
  and use about 5000 when the staged D1/C1 terrain pair is being loaded at
  startup. TOS has to boot and auto-start the program first; capture earlier
  and the dump is TOS's own screen buffer or the still-empty framebuffer.
- `grab-frames.sh <outdir> <vbl>...` captures many frames from **one** Hatari
  pair instead of two runs per frame: pass 1 breaks at every requested VBL to
  read the Videl base, pass 2 breaks again to dump each. The whole sequence
  costs what its last frame used to. Use it for anything with a timeline -
  the attract cycle above all, where single frames say nothing about whether
  a pan, an animation or a state change is right. Set `GRAB_SETUP` to
  debugger commands run at the first breakpoint of both passes when a capture
  needs state the headless harness cannot reach through input, e.g.
  `GRAB_SETUP=$'symbols comanche_d.tos\nw menu_open 0 1'`. `GRAB_SETUP2` does
  the same at the second breakpoint, for a poke that only means something once
  the program is already in the state - injecting a keypress into a menu that
  has not drawn itself yet is swallowed. Values must be plain decimal: a `$`
  hex literal leaves Hatari at its interactive prompt and the run hangs.
- `render-menu-ref.py` is a host pixel model for `src/menu.s`: the DOS text engine at
  `00027034` in Python, emitting the exact pixel writes a marked-up string
  produces. `--check <frame.bin>` compares them against a capture, which is
  how menu text is checked without needing the background under it. A match
  against this transcription alone does not establish DOS fidelity.
- `probe-record.sh <outdir> <K>...` dumps the frame buffer and
  `ring_silhouette` at replay record K instead of at a VBL. Use it whenever
  two builds differ in speed: the replay advances one record per rendered
  frame, so a faster build shows a different game frame at every VBL and a
  VBL-keyed comparison compares unrelated pictures. `PROBE_AT=demo_tick`
  dumps the previous frame composed; the default, `object_draw_pass`, dumps
  sky and terrain alone.
- `compare-terrain.py` diffs a frame the ORIGINAL drew against the same frame
  from this port. It compares original frame evidence, alongside the complete-
  frame and state-contract checks; it is not the only DOS-backed check here.
  The DOS side needs no
  harness: the game writes its own 328x240 PCX when the developer sequence is
  enabled (options bar, type KYLE, then hold Alt and press P). `--demo-camera`
  only prints the recorded DEMO0 start for inspection; current parity capture
  uses the attract cycle's actual demo flight.
- `prove-browser-attract.js` is the deterministic proof gate for the connected
  JavaScript slice. It audits source provenance, compares the generated Q31
  table with the hashed DOS image, checks all four authored attract resource
  families and palette representations, and exercises pass-one replay ordering
  without relying on a live browser clock.
- `check-falcon-roster.py` extracts the production ranking/refresh routines and
  compares every roster byte and selected pilot with direct DOS-call fixtures
  on both CPU cores. `check-falcon-debrief.py` checks the production number and
  percentage writers' buffers and score counters against DOS cases.
  `check-falcon-collision.py` checks the existing production collision block's
  decisions at the instruction boundary, with explicit exit/pointer seams.
  These are function checks; file writes, crash aftermath, the connected live
  route, graphics and hardware remain separate gates. Records:
  `analysis/functions/browser-attract.md`.
- `check-js-sound.js` runs the JavaScript sound driver (`jsComanche/dos-sound.js`) against the
  captures of `work/trace_sound_writes.py` (the original's OPL2/MPU-401/speaker writes and the mixer's
  output, `build/sound/*.json`, derived and git-ignored) and, with `--natural FILE`, against a whole
  run of the game with its timer interrupts. It exits non-zero on any difference. Spec:
  `analysis/functions/sound-driver.md`.
- `check-falcon-sound.py` builds `sound-mixer-test.s` with `../src/sound.s` and runs it under Hatari: the Falcon digital
  mixer against the DOS captures (`build/sound/digital-*.json`), the JavaScript reference, the image's curves and an
  integer model of the resampler, byte for byte (`gen-falcon-sound-script.js` writes the script and the expected bytes).
  `check-falcon-dma.py` runs `sound-dma-test.s`: the DMA ring, the VBL refill and Hatari's recorded audio output.
  `js-sound-stream.js` is its helper; `decode-sound-log.py` prints the request log a debugger dumped from the game
  (`snd_log_buf`). Record: `analysis/functions/sound-falcon.md`.
- `export-sound-trace.js` plays a song through the JavaScript driver and writes its OPL2 writes in the
  `../F030OPL2` trace format (`W <us> <context> <reg> <value>`, 65.0 Hz ticks); `--against` compares
  with a capture of the original.
- `check-js-objects.js` runs the JavaScript attract reference and compares its
  object table, frame by frame, with the DOS snapshots captured at `000234CE`
  (`work/replay_dos/objects-*.json`, generated and git-ignored). Rows are
  joined by the replay cursor; the one value taken from the oracle is the
  wall-clock PRNG `[00019DB8]` that gates the tanks' aim, injected per frame.
  The demos DOS played before the captured one are run first (drawing stubbed
  out), because DOS's per-slot arrays carry from one demo to the next.
  `node tools/check-js-objects.js --all` prints per-field match counts for
  the mission slots and, for the transient slots, per routine (countermeasure
  clouds, wreckage, enemy shells, player weapons); `--trace SLOT`,
  `--find-state ADDR` and `--align SLOT` show the first differences. It is
  the executable record of what the reference still gets wrong (the player's
  weapons and everything that follows from a hit), so a mismatch there is a
  finding, not a harness fault.
  `node tools/check-js-objects.js --gun` is the pass/fail check for the
  cannon (`00022890`/`000244E0`), the live-key dispatch (`000191B6-0001922E`)
  and the target cycle (`00019230-000192A3`): `work/replay_dos/objects-gun-dos.json`
  is the DOS object table with Space held on console page 0 at replay cursors
  101-124 of DEMO1 (`work/trace_replay_flight.py --objects --records 45
  --poke-from 101 --poke-to 125`), the harness applies the same poke at the
  same instant, and slots 127-129 are compared on every frame (active, x, y,
  heading, altitude, sprite, speed, previous position and altitude, aux,
  state, draw) together with the lock, candidate, console page and pending
  counts. It exits non-zero on any difference. The object pass runs without
  its pixels, but not without its terrain march: the per-ring horizon the
  targetability test reads is archived by `drawTerrain`, so only the span
  writer is stubbed.
- `trace-browser-replay.js` emits one JavaScript post-flight state row per
  DEMO1.SCR cursor, including the replay bytes and frame hash.
- `trace-falcon-replay.py` emits the corresponding flight-publish rows from
  Hatari's 68030/68060 debug images. `compare-boundary-traces.py` joins DOS,
  JavaScript, 68030 and 68060 by the DEMO byte cursor and stops at the first
  unequal field; incomplete captures remain **Unproven**.
- `compare-complete-frame.py` compares a full 320×240 RGB565 target frame
  against a DOS 328×240 PCX after the documented palette conversion. It
  requires explicit page, pan, camera and replay-tick metadata on both sides.
- `trace-browser-sequence.js` runs all four attract passes in one deterministic
  sequence and reports transitions, replay command keys, external-camera keys,
  and terrain-buffer reuse. Unsupported camera paths are reported as
  **Unproven**, not treated as no-ops.
- `audit-function-matrix.py` emits the implementation-wide source/function
  matrix. A source-header scan is only a prerequisite; every reached row still
  needs its DOS contract, JavaScript/M68k counterparts, fixture and exact route
  witness.
- `acceptance-report.py` fingerprints the exact DOS/source/build/toolchain
  inputs, reruns the browser gate, checks the recorded CPU/countdown evidence,
  validates the boundary/sequence artifacts, and writes
  `docs/ACCEPTANCE-REPORT.md`. It returns 1 while any DOS-fidelity gate is
  **Unproven** or divergent. Use `check-attract-timing.py --artifact-dir` to
  keep odd/even and 68030/68060 timing evidence in separate directories.
- `run_qemu_exec_trace.py`, `trace_attract_report.py`, and
  `inspect_qemu_state.py` are the route-first milestone tools. Run the genuine
  DOS image under QEMU's execution extension with a repeatable input schedule,
  fold the executed blocks onto the DOS map, and snapshot the active state and
  object slots before creating or changing JavaScript/M68k sources. The route
  report is the source-generation boundary; an unreached or unexplained path
  remains dormant/`Unproven`.
- `render-attract-ref.py` renders the attract screens straight from the
  installed assets - Kyle DTA decode, KRL sprite banks, the recovered
  bottom-up planar layout, the bank-to-screen colour translation - as the
  oracle a Falcon capture is compared against. It is written against the
  disassembly rather than against `src/attract.s`, so a mistake shared by
  both would have to be made twice.
- `fb2png.js` converts a raw 16-bit RGB565 framebuffer dump to PPM.
- The former `render-node-reference.js` and `read-telemetry.py` were removed as
  misleading parity tools: they contained synthetic camera/colour data and
  telemetry pixels, not DOS behaviour.
- `build-dsp.sh` assembles a DSP56001 source through the local DOSBox copy.
- The former `gen_menu_font.py` was removed: its 5x7 glyphs were invented.
  `prepare-original-test.py:emit_menu_font` extracts the game's own `KF4b`
  font instead.
- `prepare-original-test.py` validates and decodes the original Comanche
  `D1.DTA`/`C1.DTA` PCX-style maps at full 1024x1024 resolution into ignored
  build output. It writes `build/port_tables.s`, the only part render.s
  assembles (the port's constants, `invz_table`, empty storage), and the host
  reference `build/original_test.s` with the original's tables as the
  Falcon loads them at startup (`src/origexe.s`, `src/dtl.s`).
- `check-orig-exe-load.py` runs `comanche_d.tos` in Hatari and compares every
  table the program loads with `build/original_test.s`.
- `capture-target-frame.py` keeps only `comanche_d.tos` in its directory and
  loads symbols with `symbols prg`: with `comanche.tos` beside it TOS ran
  that one (both are COMANCHE.TOS in 8.3), and Hatari 2.6.1 refuses
  `symbols comanche_d.tos` there ("program TEXT address invalid").

Tool paths can be overridden with `VASM`, `VLINK`, `HATARI`, `TOS`, `DOSBOX`,
and `ASM56K`. The default binaries are local copies under `tools/toolchain/`.

## Reverse-engineering helpers

- `re/mzinfo.py` — DOS MZ header, relocation, and memory-layout inspection.
- `re/codemap.py` — heuristic code/data segmentation.
- `re/disasm.py` — recursive-descent disassembler with two address models:
  16-bit `seg:off` by default, and 32-bit flat under `--flat ORIGIN`. Optional
  inline-data, indirect-call, seed, and known-data configuration. Run it on the
  unpacked `COMANCHE.EXE`, not the LZEXE-packed file.
- `re/carve-flat.py` — extracts the 32-bit flat program out of the unpacked
  load module so external tools can load it without a DOS-extender loader.
  Load the result at base `0x0`: the file begins at the selector base, so its
  addresses are already the flat addresses every other tool and document uses.
- `re/annotations.py` — validates `re/annotations.txt`, the committed
  classification store, and projects it into a workbench. `check` prints the
  ledger; `export-rizin` writes a rizin/Cutter script; `export-ghidra` writes a
  Ghidra script recreating the same rows as functions, labels and plate
  comments. The store is the system of record because a Cutter project, a rizin
  `.rzdb` or a Ghidra `.gpr` cannot be diffed or reviewed - analyse in the
  workbench, write what you proved back here, regenerate the tool state. Both
  exporters keep a `?` candidate as a comment only, so an unproven reading
  cannot become load-bearing merely by being imported.

  Ghidra earns its place on the two questions recursive descent cannot answer:
  "what reads this address" across the whole image, and a decompiler for
  handlers currently reachable only as installed targets. Load the
  `carve-flat.py` output at base 0 as `x86:LE:32:default` and apply the script
  with `analyzeHeadless -postScript`; the generated file's header carries the
  exact invocation and the warning about pointing it at the wrong image. The
  *GhidraDosToolbox* extension does NOT apply here - its loader and INT mapping
  target 16-bit real-mode DOS, while this game's code is the 32-bit flat region
  behind a custom extender, and the 16-bit bootstrap it would help with is
  already classified in `re/listings/comanche-bootstrap.lst`.
- `re/peek.py` — instruction, word, or byte inspection at an arbitrary offset.
- `re/xref.py` — direct caller/jumper search.
- `re/asset_probe.py` — measured `.DTA`/`.RLE`/`.DTL`/`.SCR` marker and
  candidate-header inspection; it deliberately does not decode payloads.

The supplied Comanche executable uses an LZEXE 0.91 bootstrap and then enters
a 386 protected-mode/custom DOS-extender path. The repository does not bundle
an LZEXE unpacker, so use a standard `UNLZEXE` implementation before the MZ
helpers. The post-transition image is handled by `disasm.py --flat 1700`;
`tools/toolchain/dosbox/dosbox_with_debugger.exe` is for the questions static
analysis cannot answer, such as computed jump targets and runtime resource
reads. See `docs/RE-WORKFLOW.md`.

The contents of `re/reference_f29/` are deliberately isolated because they
encode F29 Retaliator-specific archive, compression, sound, model, and scene
formats. Use them as templates after Comanche's formats have been identified.
