# Audio: what is known and how F030OPL2 fits

Status: `TBD` — nothing here has been measured on the Falcon, and no DOS-side
OPL register capture exists yet. This note records the assets, the measured
driver structure, an assessment of `../F030OPL2`, and the capture plan.

## Assets (unpatched base tree)

| Item | Files |
|---|---|
| Music | 18 Miles XMIDI files, `game/SOUND/ST1_GR1.XMI` .. `ST9_GR4.XMI`: nine songs, each in a `GR1` and a `GR4` arrangement (which card family each targets is **not yet established**) |
| AdLib bank | `game/EXE/STDPATCH.AD`, 4,662 bytes: a Miles timbre library. Header entries are `{patch u8, bank u8, offset u32}`; the first reads `00 00 78 05 00 00`, offset `0x578` |
| General MIDI banks | `game/EXE/GM1.BNK`, `GM2.BNK` (23,907 and 24,273 bytes) |
| Drivers | `A32ADLIB.DLL`, `A32SBFM.DLL`, `A32SBDG.DLL`, `A32MT32*.DLL`, the Gravis, Pro Audio, Tandy and speaker drivers: Miles AIL32 `.DLL`s selected by `SOUND.CFG` |
| Other sound files | `game/SOUND/*.VOC` (Creative Voice effects) and `*.WAR` (type not yet identified) |
| Configuration | the shipped `SOUND.CFG` names `a32sbfm.dll` and `a32sbdg.dll` (Sound Blaster FM and digital); under it the oracle ends in Mel fatal error 25 (no MIDI card detected), see `analysis/executable.md` |

## Runtime structure measured so far

The game uses the Miles AIL timer service. Measured in the oracle (details and
addresses in `analysis/executable.md`, "Startup stall: no mouse driver"):
16 timer slots (status 0 free / 1 stopped / 2 running, period in microseconds),
a master timer in slot 16 that hooks INT 8 and programs the PIT, and per-slot
callbacks. One slot ran at 100 Hz (period 10,000 µs) and another at 4 Hz. The
game's own `Delay` tick is a separate registered callback. A DOS-faithful music
port must reproduce when the sequencer is stepped relative to this timer, not
only the note data.

## F030OPL2 assessment (2026-10-05)

`../F030OPL2` emulates a nine-voice OPL2 on the Falcon DSP at 49.17 kHz, with a
68030-side register decoder, a real-time MIDI player and a register-trace
player (`W <µs> <t|g> <reg> <val>`). Its own notes report the DSP output
bit-exact against its integer host model, no late periods on the 20 densest
songs of a 244-song corpus, and a worst period of about 94% of the DSP budget
on its rhythm stress stream. **The 244 songs span five games (Falcon 3,
Underworld 1 and 2, Panzer General, Ultima 4); an earlier summary here
mis-stated them as 244 Panzer General songs.** Panzer General contributes the
18 files above.

**A good match for:** the synthesiser back end. Same chip class as
`A32ADLIB.DLL` and `A32SBFM.DLL`, nine voices, a decoder that accepts stamped
register writes, and a PCM flag path (its player calls it "silent PCM flags"; whether it can carry the VOC effects is unchecked).

**Not yet a match for:** how the game sounds.

- The test is self-consistency, not fidelity: the DSP model is block-rate (32
  frames) for envelopes and the low-frequency oscillator and is documented as
  not chip exact; it was never compared against a real OPL2 or an emulator
  register trace. No audio has been auditioned.
- Its instruments are ScummVM's General MIDI AdLib bank, not `STDPATCH.AD`.
- `xmi2mid.py` drops XMIDI controllers 110-120 (loop, branch and callback
  controls) and does not unroll loops; whether Panzer General's files use
  them is unchecked.
- Timing against the AIL timer callbacks above is unchecked.
- No physical Falcon validation, and the emulator DSP needs the calibrated
  Hatari (see `../F030Method/analysis/sibling-port-lessons.md`).

## Plan (not started)

1. Capture the game's own OPL register writes in the DOS oracle: QEMU provides
   an `adlib` device (`-device adlib`, YM3812); generate an AdLib `SOUND.CFG`
   with the shipped `SOUND.BAT` instead of the no-sound one, then log writes to
   ports `0x388/0x389` (the shared TCG trace's I/O logging is the first candidate; no method is
   proven yet) with timestamps.
   Verify that the oracle's own capture is correct before using it.
2. Replay that stream through F030OPL2's `trace` mode: it yields the game's true
   timbres and timing without a Miles engine, and is the ground truth against
   which a General MIDI or `STDPATCH.AD` engine can be compared.
3. Load `STDPATCH.AD` into the F030OPL2 engine in place of the General MIDI
   bank; `scummvm/audio/miles_adlib.cpp` already parses the format.
4. Decide `GR1` versus `GR4` from the capture, and check the XMI controllers
   the converter drops.
5. Digital effects (VOC) and any Sound Blaster DMA path are a separate item;
   they share the DSP with the OPL, and SSI-DMA colour conversion cannot be used
   at the same time.
