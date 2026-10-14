# The digital effect layer on the Falcon (`src/sound.s`)

Written 2026-10-07. This is the Falcon half of phase 8 for the **digital** layer of the original's sound:
three 8-bit sample slots, the request routines that fill them, the software mixer and the two transfer curves.
The recovery is `analysis/functions/sound-driver.md` (section 4 the layer, section 5 every call site, section 10
the interface); its executable reference is `jsComanche/dos-sound.js`, held identical to the running original by
`tools/check-js-sound.js`. The music and FM driver (`0002B9CF-0002C4A0`) is **not** part of this record; the
interface left for it is at the end.

## What it is

```
 game code                        src/sound.s                              Falcon
 ---------                        -----------                              ------
 weapons, wrecks, speech   ->  snd_fx / snd_speech_a / snd_speech_b   slots (3)  ->  snd_fill  (DOS arithmetic)
 rotor, menu               ->  snd_voice / snd_reset / snd_rate                         |  11,111 Hz, unsigned
 options radios, screens   ->  snd_mode / snd_apply_sound                               v
                                                                       snd_resample (platform, linear)
 VBL handler (50 Hz)       ->  snd_vbl  ----------------------------->  ring, 4096 B, ST-RAM, 12,292 Hz signed
                                                                                          |  sound DMA, repeat
                                                                                          v
                                                                                       DAC (matrix: DMA -> DAC only)
```

* **DOS arithmetic, byte-exact:** slot choice and starting (`00004EA2`), the FX/speech/voice entries
  (`00004E8E`, `00004E2E`, `00004E26`, `00004F6E`), reset (`000050B4`), the dither mask (`00004E0C`), the mixer
  mode (`00004FE4`), the fill (`00005220`) with the Loud/Soft tables (`00004C0A`, `00004A0A`), the bias table
  (`00004A02`) and the error feedback. The two curves are built at start-up from their recovered formulas
  (Loud `clamp(i - 128, 0, 255)`, Soft `i >> 1`, `i = 0..511`) and are equal to the executable's bytes.
* **Platform replacement (no DOS counterpart):** everything between the mixer's bytes and the DAC - the resampler
  (`snd_resample`), the ring and its VBL refill (`snd_vbl`), the XBIOS sound set-up (`snd_dma_open`), starting and
  stopping the DMA (`snd_dma_start/stop`), the interrupt masking that replaces `cli`/`sti`, the request log.

### Platform differences (the ledger of everything the Falcon does differently)

| DOS | Falcon | why |
|---|---|---|
| Sound Blaster DMA channel 1, auto-init, two 0x800-byte halves, 11,111 Hz (DSP time constant `0xA6`, `00001FBC`) | sound DMA in repeat mode over one 4096-byte ST-RAM ring, 8-bit mono **signed**, **12,292.48 Hz** | the Falcon has no 11,111 Hz; 25.175 MHz / 2048 (`Devconnect` prescale 7) is the nearest rate its DAC offers (12,292 against 12,517 for the STe-compatible clock, 9,834 below) |
| the SB IRQ calls the fill for the half that finished | the 50 Hz VBL calls `snd_vbl`, which reads the DMA frame counter (`$FF8909/0B/0D`, until two reads agree), and renders `SND_TARGET` (1024 B, 83 ms) minus the lead | the main loop runs at ~2 fps; the VBL is the only regular code |
| the mixer runs at 11,111 Hz into the SB buffer | the mixer still runs at 11,111 Hz (so it stays exact) into `snd_rs_buf`; `snd_resample` converts with `out = a + ((c - a) * f >> 15)`, `f = frac(phase) >> 1`, phase step `59238/65536` = 11,111.11 / 12,292.48 | exact mixer, simple documented resampler |
| unsigned bytes, silence `$80` | signed bytes: the mixer byte xor `$80` | the DMA's format |
| `cli`/`sti` around the request routines | every public entry raises the IPL to 7 for its whole body and restores the SR | the fill runs at level 4 (VBL) on the Falcon |
| `00004FE4` MODE starts/stops the SB, rebuilds the buffers | `snd_dma_start` clears the ring, resets the resampler and starts the DMA (`Setbuffer`, `Buffoper 3`); `snd_dma_stop` stops it (`Buffoper 0`) | same moments |
| `00004FBB` DET probes the SB DSP | `snd_det`: types 1..4 try `Locksnd` + a ST-RAM ring; type 0 and > 4 fail as in the DOS | the result feeds the same `[00019DF9]` |
| shift/bias patched into the mix loop's immediates (`0000527A/C`, `000052A4/7`, `000052D0/3`) | fields of the slot record | same values, same moments |
| the three slots interleaved per output byte | the three slots are summed one after another over passes of up to 512 bytes, then the dither pass runs; a slot with step 0 below its limit contributes one byte computed once | the slots share nothing but the sum; verified byte-exact with every cut of the fill |
| `[000040F2/F6/FA]` hook calls at slot changes | omitted | all four mode tables point them at a bare `ret` (`00004E0B`) |
| missing `COMANCHE.CFG` / `SOUNDSET.EXE` exit with "Please type SOUNDSET" (`00005528-0000553A`, `000054FD-0000550A`) | a missing `.CFG` leaves the digital layer off; `SOUNDSET.EXE` is not looked for | neither belongs to a Falcon install |
| sample banks are bump-allocated without a bound | three fixed buffers (80,000 / 200,000 / 24,000 bytes for banks that decode to 74,649 / 192,530 / 20,066); a bank that does not load leaves its pointer 0 ("not loaded", as `00004E34` tests); with no SND1 `[00019DF9]` is cleared | platform |
| (none) | the DMA ring is zeroed at start; the writer restarts at the play position if the DMA overtakes it | platform; `snd_stat_under` counts it (0 in every run) |
| (none) | the exception pad writes `$FF8901` = 0 | a crash must not loop a 4 KB buffer for ever |

The DSP is not touched: no `Dsptristate`, no DSP route in the matrix; only DMA playback -> DAC is connected
(`Setmode 2` 8-bit mono, `Settracks 0,0`, `Setmontracks 0`, `Soundcmd 4,2` matrix adder input, `Devconnect 0,8,0,7,1`).
Attenuation and the converters' state are not changed.

## Function records

All routines are in `src/sound.s`; every non-obvious line carries its DOS address. Registers follow the DOS
(`eax d0, ebx d1, ecx d2, edx d3, ebp d4, esi a0`) and every public entry preserves every register.

### `snd_start`
DOS `00004EA2-00004F6D` (`sub_00004EA2`). Start a sample on a slot: `bl < $80` is the slot; `$FF` the first idle slot
(silence record playing), else the slot already playing this record, else slot 0 if `dl = 0`, else the sound is
dropped; `$FE` skips the idle search. Slot gets record, limit, step (`ecx`, or the record's word when 0), position 4.0,
shift `dl`, bias `[00004A02 + dl]`. **Difference:** shift/bias in the slot record, not patched code. **Verified:**
byte-exact (below). Kind: translated.

### `snd_voice`
DOS `00004F6E-00004FBA`. Stage a sample as the slot's next; a slot still holding the silence record starts it at
once (tail jump into `00004EA2`). The rotor loop is this routine called again and again with the same record.
Verified byte-exact (digital-rotor, random scenarios).

### `snd_reset`
DOS `000050B4-000051B6`. Every staged sample becomes the silence record (step 0, shift 0, bias 0); every slot not
already playing it switches to it. Verified byte-exact.

### `snd_rate`
DOS `00004E0C-00004E25`. `[00004194]` = dword `[00004998 + 4 * al]`, `al <= $11`. The table is in `snd_rate_tab`.
Verified byte-exact (masks 0, 1, 5, 9, 17 in digital-mix; all of 0..17 and 18..217 in the random scenarios).

### `snd_speech` (`snd_speech_a`, `snd_speech_b`)
DOS `00004E2E` (SPEAK1, `[00019E9C]`) and `00004E26` (SPEAK0, `[00019EA0]`), common body from `00004E34`. Nothing if the
bank is not loaded or slot 2's staged sample differs from what it is playing; slot 2, or slot 1 when slots 0 and 1 are
both idle; skipped if the record already plays on slot 0 or 1; `dl = 0`, `ecx = 0`. Verified byte-exact.

### `snd_fx`
DOS `00004E8E-00004EA1`. With `[00019DF9]` set: `eax = [SND1 + 4 * id] + SND1`, then `snd_start`. Clear: the id goes to the
FM driver's command entry `snd_fm_command` (an empty routine until the music driver is ported). Verified byte-exact.

### `snd_sample_ptr`
The inline `mov eax,[esi+ebp*4] / add eax,esi` of `00004E9D`, `00004E6B`, `000189A6` as a routine, with the little-endian read.

### `snd_fill`
DOS `00005220-0000531A` with the restage stubs `000051C0-00005213`, `00005320-00005373`, `00005380-000053D3`.
`d0` bytes into `a0`. Per output byte: each slot contributes `((byte at position >> 16) >> shift) + bias` (8-bit
wrap) and advances by its step, after taking its staged sample when `position >> 16 >= limit`; `t = sum +
err[counter & mask] + 1`; `err[...] = (t >> 2) & $FF`; output `curve[t >> 1]`; counter + 1. **Difference:** any count
into any buffer (the DOS fills one 0x800 half); slot-by-slot summing over passes of 512; the constant-slot shortcut
(see the ledger). **Verified:** 233,472 DOS bytes, twice (see below).

### `snd_mode`
DOS `00004FE4-000050AF`. Curve back to Loud; a running mode is stopped; a mode above 4 returns (mode byte unchanged);
otherwise the mode is stored, the slots are reset (`000050A3`) and for 1..4 the output starts. `$FF` (the start-up call
`0000559F`) therefore only stops. **Difference:** stop/start are the DMA path.

### `snd_apply_sound`, `snd_apply_settings`
DOS `00026843-0002687C` (the sound half of `000267F3`) and the live radio handlers `00026CE3`, `00026CF9`, `00026D19`
(the same three calls): `'0'` Loud: `MODE([00019DF9])`; `'1'` Soft: `MODE([00019DF9])` then the soft curve
(`[00005307] = 00004A0A`); `'2'` Off: `MODE(0)`. The music half of `000267F3` (`000267F3-00026842`) is not ported.

### `snd_init`, `snd_det`, `snd_shutdown`
DOS `00005528-000055AF` (CFG, `[00019DF9] = cfg[1] & $F`, DET, `MODE($FF)`, `RATE(2)`) and `00006B28-00006B2A`
(`MODE(0)` at exit). See the ledger for DET and the CFG.

### `snd_bank_load`, `snd_banks_load`, `snd_title_bank_load`
DOS `00015E6E` (`KRL0`/`KRL1` loader) and `0001644B` (`krl_decode`, now `src/krl.s`), used for `snd1.rle` (`000058D4`,
`000064A8`), `speak0.rle` (`0000681D`), `speak1.rle` (`00006859`). The banks keep their little-endian `K1` layout.

### `snd_mixer_init`
The image's initial bytes `00004142-000041B7` (slots idle on the silence record, limit 0, step 0, position 4.0, counter 0,
mask 0, 2048 error bytes `$80`) and the two curves.

### Platform routines (no DOS counterpart)
`snd_dma_open`, `snd_dma_start`, `snd_dma_stop`, `snd_vbl`, `snd_resample`, `snd_log`: see the ledger above. The refill's
lead is `snd_wr - snd_played` (bytes ahead of the DMA); `snd_vbl` renders `SND_TARGET` minus the lead, split at the ring's
end.

## Call sites

`src/inc/snd.s` has the macros (`SndFX`, `SndSpeechA`, `SndSpeechB`, `SndFXDist`); they keep every register and the condition
codes, because no sound call may change the code around it. Rows are those of `sound-driver.md` section 5.

| rows | DOS site | where in the port | arguments |
|---|---|---|---|
| 3-5 | `00005596`, `0000559F`, `000055AF` | `main.s` -> `snd_init` | CFG, DET, `MODE($FF)`, `RATE(2)` |
| (568B) | `0000568B` | `main.s` -> `snd_apply_settings`, before `attract_start` | |
| 8 | `00005692` | `attract_next_pass` | `MODE(0)` |
| 11, 12 | `00005765`, `00005856` | `attract_next_pass` (side, fanfare branches) | `apply` |
| 14, 16 | `00005891`, `0000594D`, `00005963` | `attract_frame` (fanfare -> title) | `MODE(0)`, SND1 load, `apply`, `VOICE` SND1 id 3, bl 2, dl 1 |
| 20-22 | `00005AF0`, `00005B24`, `00005B35` | `attract_stop` (key), `attract_start_demo` (expiry), `screen_mission_start` | `MODE(0)`, `RESET`, `MODE(0)` |
| 25 | `00006A0E` | `flight_mission_sound_start` (`flight.s`) | `SFXA 6` |
| 26 | `00006A99` | `flight_announcer` (called from `main.s` before the frame) | every 32nd iteration, `SFXA` of table `08 04 0D 0F 0D 0E` |
| 27 | `00006B2A` | `snd_shutdown` from `deinit` | `MODE(0)` |
| 30 | `00007857` | `hud_threat_sound` (`hud.s`, in `instruments_draw`) | `SFXB 2` on the rising edge of the sight-window flag (own copy of `[00019D93]`) |
| 31, 32 | `000189B2`, `000189BD` | `flight_rotor` (mission start, fuel out `00018E44`, Esc bar closed) | `VOICE` SND1 id 3 or the silence record, bl 2, dl 2 |
| 33-35 | `00018F79`, `00019488`, `000194DB` | `flight.s` (`flight_tick`) | `SFXA 11`; `SFXA 2/3`; `FX 5` |
| 36, 48 | `00022876`, `00024A2C` | `object_boom_sound` (from `object_clone_fields`, `object_transition_home`) | `FX 1, bl $FF, dl = distance class <= 4` |
| 37-41 | `000228FD`, `00022B6C`, `00022EB9`, `00022FD9`, `00023123` | `weapon_fire_gun/rocket/stinger/hellfire/wingman` | `FX 7 bl $FE`; `FX 4 ecx $20000`; `FX 4`; `FX 4`; `FX 4 dl 1` |
| 42 | `000231FD` | `weapon_fire_bomb` | `SFXB 1` |
| 43, 44 | `0002360C`, `00024469` | `shell_player_hit`, `object_state_bomb` | `FX 5` |
| 45-47 | `0002432B`, `0002433B`, `0002434C` | `object_state_bomb` | `SFXA 9`; `FX 2`; `FX 6` |
| 49-56 | `000237F8`, `00023940`, `00023956`, `00023A20`, `00023AAD`, `00023CCA`, `00023F3B`, `0002415D` | `object_state_wreckage`, `object_state_ally`, `object_state_idle`, `object_state_static`, `object_state_mobile`, `object_unit_wreck` | `SFXA 7`; `12`; `10`; `5`; `1` (x4) |
| 57 | `00025DFD` | `flight_menu_silence` (Esc opens the bar, `game.s`) | `VOICE` silence, bl 2, dl 0 |
| 63-68 | `00026851`, `00026861`, `00026878`, `00026CF3`, `00026D09`, `00026D26` | `snd_apply_sound`, from `snd_apply_settings` and the radio handler in `menu.s` | `MODE` / soft curve / `MODE(0)` |
| 73, 74 | `0002876D`, `00028777` | `mission_end` (`debrief.s`) | `MODE(0)`, `RESET` |

**Not wired, and why:** rows 1, 6, 7, 9-10, 13, 15, 17-19, 23-24, 28-29, 58-62, 69-72, 75-80 are the FM/music driver.
Row 1 (the FM fallback of `00004E8E`) goes to `snd_fm_command`, an empty routine. Nothing else of the 80 sites is missing.

Two calls are deliberately **not** a transcription: `hud_threat_sound` (row 30) runs the sight-window test of `000077E8-00007819`
on its own flag pair, because the real `[00019D93]` also drives the blip and the countermeasure chain (`object_threat_blip`,
`00019555`), which this port does not compute and which would change the simulation; and `flight_announcer` counts its own
`[00019DE8]` (the HUD's blink reads the VBL count in its place, a recorded deviation in `hud.s`).

## Verification

| what | how | result |
|---|---|---|
| the mixer against the DOS captures | `python3 tools/check-falcon-sound.py`: `tools/sound-mixer-test.s` + `src/sound.s` + `src/krl.s` under Hatari (Falcon, 68030, TOS 4.02, cycle exact) interprets the same call sequences as `build/sound/digital-*.json` through the entry points the game uses, loads the banks with the game's loader, and writes every mixed byte | **233,472 of 233,472 DOS bytes identical** (6 captures, 114 fills), and again with every fill cut into pieces of unequal size (1..1000 bytes): 233,472 of 233,472 |
| against the JavaScript reference | the same program on random call sequences (`tools/gen-falcon-sound-script.js`; every `bl`, shifts 0..7, steps, staging, reset, masks 0..217, both curves) replayed on `jsComanche/dos-sound.js` | 1,812,480 of 1,812,480 bytes identical (2 scenarios of ~260 requests) |
| the 68060 | `python3 tools/check-falcon-sound.py --cpu 68060` (built `-m68060`, run on Hatari's 68060 with EmuTOS); the 68060 game image also boots with the digital layer up (digital flag 1, the same request log) | 2,425,581 of 2,425,581 bytes identical; the DMA test and the hook run were made on the 68030 only |
| the two curves | dumped from the 68030 and compared with the image bytes at `00004A0A` and `00004C0A` | 1,024 of 1,024 |
| the resampler | `snd_resample` in random output sizes (1..1024) over four effects, against an integer model of the documented arithmetic | 145,133 of 145,133 bytes identical |
| the DMA path | `python3 tools/check-falcon-dma.py`: `tools/sound-dma-test.s` brings the layer up like the game (CFG, banks, the Loud radio), runs a 650-VBL timeline (explosion, rotor, a voice, the Soft radio, Sound Off), logs every ring byte; Hatari records its own audio to a WAV (`hatari-path soundout`, `hatari-shortcut recsound` through `--cmd-fifo`, 44,100 Hz) | 560 refills, **0 underruns**, 137,340 bytes rendered; from the explosion's request on the ring equals the resampler model over **40,000 of 40,000 bytes**; the explosion is 2.43 s long in the ring and 2.44 s in the WAV (the sample is 27,081 bytes = 2.44 s); the rotor's RMS on the Soft curve is **0.50** of the Loud curve (1.97 / 3.90); the WAV is not silent (321,305 non-zero frames, peak 5,248), its 100 ms RMS series correlates 0.97 with the ring's, and its last second after Sound Off has RMS 0.0 |
| the CPU cost of the refill | the same program times a fixed workload (8,000,000 loop iterations) in VBLs with the mixer off and with it on | 50 VBLs off; 52 with the rotor (**+4 %**); 53 with the rotor and a voice (**+6 %**), in Hatari's cycle-exact 68030 |
| the hooks | the request log (`snd_log_buf`, `tools/decode-sound-log.py`) dumped at VBL 30,000 of a normal Hatari run of the attract cycle (sound off, fast-forward) | 263 requests, below |
| regressions | `score2.sh 10 1` / `50 6` | 76,741 / 76,800 of 76,800. Record 10 has been 76,686 (before any change), 76,698 (module split and link order only, sound code unreferenced) and 76,741 (hooked): it follows the link layout, is deterministic for one layout, and does not depend on the sound running |

The hook run, the log summarised (`python3 tools/decode-sound-log.py log.bin cnt.bin --summary`; the VBL is the first request of its kind;
the log keeps the last 512 requests, 263 had been made):

| request | count | first at VBL | event |
|---|---|---|---|
| `MODE($FF)`, `RATE(2)` | 1, 1 | 0 | `snd_init` |
| `MODE(1)` / `MODE(0)` / `RESET` | 9 / 11 / 23 | 29 | start-up apply, every attract pass, each screen, each mission start |
| `VOICE` slot 2 dl 1 | 2 | 531 | the rotor under the title |
| `VOICE` slot 2 dl 2 | 3 | 2363 | the rotor switch at mission start (the silence record: the demo's collective is 0) |
| `SFXA 6` | 3 | 2363 | the mission-start voice |
| `FX 4` ecx 0 / ecx `$20000` | 14 / 62 | 2546 / 3650 | Hellfire and Stinger / rocket launches |
| `FX 1` dl 0 / 1 / 3 | 72 / 15 / 8 | 2703 / 5618 / 17524 | explosions at distance classes 0, 1, 3 |
| `SFXA 1` | 7 | 2703 | an object destroyed |
| `FX 5` | 13 | 6257 | the player hit |
| `SFXB 1` | 2 | 10814 | the timed blast placed |
| `SFXA 9`, `FX 2`, `FX 6` | 2, 2, 2 | 11861, 12243, 12494 | the timed blast's countdown, tick 100, detonation |
| `SFXB 2` | 6 | 12683 | a hostile enters the sight window |
| `SFXA 2` / `3` | 3 / 1 | 16814 / 22848 | the crash scream |
| `SFXA 15` | 1 | 16932 | "rocket launcher failed" (cell 3 went negative: the announcer) |

Not reached by that run (they are the same macros at their DOS addresses, but unexercised): the cannon (`FX 7`), the wingman's
Hellfire and acknowledgements (`SFXA 12`, `10`, `5`, `FX 4` dl 1), the oil tank and the falling wreck, the last-goal cue (`SFXA 7`),
the crash chase-view cue (`SFXA 11`), the fuel-out rotor switch and the Esc bar (a keyboard-driven flight).

## Unproven

* **What anything sounds like.** No audio was auditioned. The WAV Hatari writes is checked for length, silence and
  correlation with the ring, not for taste. The Loud curve is the DOS's and maps a single slot's swing to half its size
  (`index = t >> 1`, output `index - 128`): the effects are quiet by construction.
* **Real hardware.** The route (`Locksnd`, `Setmode 2`, `Settracks`, `Setmontracks`, `Soundcmd 4,2`, `Devconnect 0,8,0,7,1`)
  is the one `../F030MXDRV` hardened against the sound-matrix state a previous program can leave (its
  `docs/architecture.md`, "Falcon audio-path constraints"); prescale 7 on the 25.175 MHz clock is in the DAC's valid set
  (1-5, 7, 9, 11). None of it was run on a Falcon here, and Hatari does not reproduce a hostile initial matrix. The DMA
  frame counter is read until two reads agree because the three byte reads are not atomic on hardware; Hatari never shows
  the difference.
* **The CPU cost of the refill** was measured only in Hatari's cycle-exact 68030 (below), not on a 16 MHz machine.
* **The Sound Blaster programming** (`00001F49`, `00002050`, the DSP, the IRQ number) was never run in the original's
  capture either (sound-driver.md section 11, item 3); the Falcon path replaces it.
* `COMANCHE.CFG` bytes other than the second are not read (digital digits 2..4 are the same Sound Blaster code in the DOS).

## Interface left for the music driver

`sound-driver.md` section 10 is the contract. What this layer provides and expects:

* `snd_fm_command` (empty, `src/sound.s`) is `0002B9CF`: `ax` = command, in `d0`. `snd_fx_core` jumps there when
  `[00019DF9]` is 0, with `d0` = the effect id (FM command 0).
* `snd_apply_settings` is `000267F3`; its music half (`[00025DD6]`: `$FA`/`$64` level, `0x5000`/`0x4000` to `[00019DF0]`
  and the FM command) goes in front of the call to `snd_apply_sound`. The live radios (`menu.s` `.radio`) must call it for
  group 2 as `snd_apply_sound` is called for group 1 (the digit is already stored in `menu_settings`).
* The sites of the not-wired rows sit beside the wired ones: `attract_next_pass` (rows 9-11), `attract_frame` fanfare/title
  (12-15, 17-18), `attract_stop`/`attract_start_demo`/`screen_mission_start` (19, 23-24), `flight_menu_silence` (58-59),
  `mission_end` (72, 75), `snd_shutdown` (28-29), `debrief` (76), the menu screens (77-78).
* The 65 Hz tick (`00001D20` calls `[0002C48C]`) needs a timer of its own; Timer C at 200 Hz cannot make it
  (`sound-driver.md` section 10). The 50 Hz VBL already calls `snd_vbl`; the OPL2/MPU sinks are `../F030OPL2`'s.
* The title and fanfare screens still run their fixed 480/600 frames: the song-finished test (`0000587D`, `00005ACC`)
  needs the music driver.
