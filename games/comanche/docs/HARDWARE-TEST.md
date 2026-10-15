# Testing the 68060 image on a real Falcon

This is the procedure for the first run of the port on real hardware: an Atari
Falcon030 with a CT60 or CT63 (68060) accelerator. Everything the port has
done so far ran in Hatari, whose 68060 model has no caches, no superscalar
pairing and no shared-bus cost, so its frame rates are estimates and nothing
in this file has been seen on hardware yet. The test answers, in order:
does it start, does it look and sound right, how fast is it, and does it quit
cleanly.

## What only hardware can show

- **Speed.** Hatari's 68060 model charges about one cycle per instruction and
  nothing for caches, pairing or the shared 16 MHz ST-RAM bus, which every
  frame's 153,600-byte copy to the screen page crosses. Hatari (2.6.1-devel,
  binary of 2026-09-22) gives about 20 fps in the attract's flights and 20-23
  fps in live flight; a CT60 may be faster or slower.
- **Caches.** The port pushes the 68060's data cache (`CPUSHA DC`) before the
  screen page is shown and at every VBL, so a copyback-cached ST-RAM is
  covered; Hatari does not model the cache, so this has never been tested.
- **The DSP music.** F030OPL2's kernel has only run on Hatari's emulated
  56001 here, paced by the 200 Hz system timer.
- **TOS.** Every run so far used EmuTOS 1.2.1; CT60 TOS 4.04 is untested.
- **VGA.** The port has a Videl setup for VGA monitors that has never run.

## The test build

```sh
TARGET_CPU=68060 OPL2=1 HWTEST=1 OUTDIR=build/hwtest-060 bash tools/build-run.sh
```

- `TARGET_CPU=68060`: the accelerator image (software 64-bit products, the
  program loaded into TT-RAM, `CPUSHA DC` before every frame is shown).
- `OPL2=1`: the music played by F030OPL2's OPL2 emulation on the Falcon's DSP
  (needs `../F030OPL2`; writes `OPLDATA.BIN`, the DSP kernel's tables).
- `HWTEST=1`: `src/hwtest.s`, a report written to `HWTEST.TXT` when the
  program quits. It reads counters only; the game runs exactly as without it.

The tester needs two files of the build, `comanche.tos` and `OPLDATA.BIN`,
plus their own copy of the DOS game. No game data is in the program: it reads
the original's tables from `COMANCHE.EXE` when it starts.

## What the tester needs

- A Falcon030 with a CT60/CT63, TT-RAM (FastRAM) present and enabled, CT60
  TOS 4.04 or EmuTOS. A plain 68030 Falcon cannot run this image: the 68060
  instructions it uses do not exist on the 68030.
- Free space on a hard disk or CompactFlash partition: about 10 MB.
- An RGB/TV monitor or a VGA monitor. Both have a Videl setup in the port;
  only the RGB one has ever run (in Hatari).
- The DOS game *Comanche: Maximum Overkill* (NovaLogic, 1992), installed on a
  PC or in DOSBox. The port checks `COMANCHE.EXE`: it must be the 61,154-byte
  file of the original three-disk release, SHA-1
  `5edc4b65658b6a9b7a5dcf997d1787b55194470f`. Another version is refused with
  a message naming the file.
- A camera or phone, for anything that goes wrong on screen.

## Installing

1. Make a folder on the Falcon's drive, for example `C:\COMANCHE`.
2. Copy **every file** of the DOS installation into it. Exactly the files
   below are read; the others (the DOS `.EXE`s, batch files) are ignored.
   Short 8.3 names, upper or lower case, both work.
3. Copy `COMANCHE.TOS` and `OPLDATA.BIN` from the test package into the same
   folder.
4. `COMANCHE.CFG` (the DOS SOUNDSET result) selects the music device by its
   third character. It must be `3`, the AdLib: if the DOS install was set up
   with another card, replace the file's content with the ten characters
   `0132700000` (no line end), the setting the port was tested with.
5. Detail level: `COMANCHE.MNU` stores it in its 25th byte - `0` High, `1`
   Medium, `2` Low. The shipped file says `1` (Medium); the Hatari figures are
   for High. Either change that byte to `0` with a hex editor, or set
   *Detail: High* in the game's options bar during the first flight and
   choose *Save Menu Settings*. Write down which level the test ran at.

Files the port reads (the size and SHA-1 of each file of the original
release are listed at the end of `TESTING.TXT` in the test package):

| Group | Files |
|---|---|
| Program tables | `COMANCHE.EXE` |
| Settings, roster | `COMANCHE.CFG`, `COMANCHE.MNU`, `COMANCHE.NAM` |
| Campaigns | `0.MIS`, `1.MIS` |
| Terrain | `D1.DTA`..`D4.DTA`, `C1.DTA`..`C4.DTA`, `HIGH.DTL`, `MEDIUM.DTL`, `LOW.DTL` |
| Palettes | `P11` `P12` `P21` `P22` `P23` `P31` `P32` `P33` `P34` `P43` `P44`, `NP14` `NP23` `NP24` `NP34` `NP44` (`.DTA`) |
| Skies | `SKY1.RLE`..`SKY4.RLE` |
| Units, weapons | `TANK` `LH66` `SPIN` `FUEL` `TURR` `RADR` `HOKE` `CHAF` `STGR` `HELL` `ROCK` `BULL` `BOOM` (`.RLE`) |
| Cockpit | `CONS.RLE`, `HUDS.RLE`, `CONSOL1S.DTA`..`CONSOL5S.DTA` |
| Attract, menus | `DEMO0.SCR`..`DEMO3.SCR`, `BACK.DTA`, `TPIC.DTA`, `RH66SIDE.DTA`, `RAH66.DTA`, `MISSION.DTA`, `CREDIT1.DTA`, `ZOVE.RLE`, `COMA.RLE`, `FANFARE.RLE` |
| Debrief | `WIN3.DTA`, `LOSE3.DTA`, `BIGWIN.RLE` |
| Sound | `SND1.RLE`, `SPEAK0.RLE`, `SPEAK1.RLE` |
| Music | `OPENMUS.MS3`, `MENUMUS1.MS3`, `MENUMUS2.MS3`, `MUSDAY.RLE`, `MUSNIGHT.RLE`, `MUSVOLC.RLE`, `MUSWIN.RLE`, `MUSLOSE.RLE`, `WINMUS.RLE` |

## Running

Start `COMANCHE.TOS` from the desktop (or from a shell). Do not run anything
that uses the DSP at the same time (an MP3 player, a DSP accessory): the
music needs the DSP and falls back to silence when it is busy.

Use the program in this order, so every report has the same parts:

1. **Attract, one full cycle - about four minutes.** Do not touch anything.
   It runs the title screens, the RAH-66 page and the NovaLogic logo, and
   four recorded flights - night vision (green), red canyon, desert, green
   valley - with the title in between, then starts over. Let it run until
   the night flight comes round a second time.
2. **A live mission - two to three minutes.** Press Space. Main menu:
   *Begin Mission*; campaign *Comanche Training*; the first mission; Return
   at the briefing. Fly with the keyboard (the port turns joystick
   reporting off): keypad 8 speeds up (nose down), keypad 2 slows down,
   keypad 4/6 turn, `E`/`D` collective up/down, Tab to lock a target, Space to
   fire, `Z X C V B N` to pick the gun, rockets, Hellfire, Stinger, bomb or
   the wingman's weapon, `;` chaff, `'` flare. Views are the number keys
   `1`..`8` (1 the cockpit, 7 and 8 outside views); `F1`..`F6` and
   `F7`..`F12` page the two cockpit displays. Fire some weapons near
   targets, and fly a while in an outside view too.
3. **End the mission** with Alt+A. The debrief comes up with its music;
   press Esc.
4. **Quit** from the main menu: *Exit to DOS* (the last row), Return. The
   desktop must come back looking as before.
5. Copy `HWTEST.TXT` from the game folder. It is written at step 4; a crash
   or a reset before that leaves no report.

## What to watch and note

Write down, for each step: what you saw and heard, and anything wrong.

- **Picture.** Clean 320x240 colour picture, centred, no flicker, no
  tearing bands, no garbage lines or blocks. On VGA: whether the monitor
  syncs at all.
- **Music.** The opening theme at once; a melody, not noise; steady speed,
  no clicks, no stutter, no drop-outs. The menu song, the mission's song in
  flight, the debrief song.
- **Sound effects.** Rotor, gun, missile launches, explosions, the voice
  warnings, mixed with the music.
- **Speed.** How smooth the flights feel. The report measures the frame
  rate; Hatari's 68060 model gives about 20 fps (see the sample below).
- **Input.** The keys respond at once during the flight; no stuck keys.
- **Exit.** The desktop's colours, resolution and mouse are back.

If the screen turns **bright red** and stays, the port caught a CPU
exception (bus error, address error or illegal instruction) and holds the
machine there on purpose. Photograph it, note what was happening, and reset.
A freeze without red, or a reset by itself, is a different failure: note
that too.

## The report

`HWTEST.TXT` looks like this (numbers from Hatari, 68060 model):

```
REPORT_SAMPLE
```

- `[machine]`: the cookies, in hexadecimal (`_CPU` `$0000003C` = 60, the
  68060; `CT60` present on a CT60),
  the TOS, the monitor TOS reports and which Videl setup the port chose,
  the 68060's cache control (CACR) and revision (PCR), and whether the
  program was loaded into TT-RAM - it should be.
- `[clock]`: the run's length and the measured refresh rate (about 60 Hz on
  RGB; VGA modes differ).
- `[frames]`: rendered frames per second, separately for the attract's
  recorded flights and for live flight, the average VBLs a frame took, the
  worst frame, and how many frames took 1, 2, ... 8 or more VBLs. The first
  frame after a title screen, a menu or a load is counted as not timed and
  left out. A few attract frames over 8 VBLs are normal: Hatari shows five
  in a cycle, most likely where a recorded flight loads its terrain.
- `[music]`: whether the DSP stream ran, how much sound it delivered against
  the time that passed - the two should be within a fraction of a second -
  and protocol errors, which should be 0.

## What to send back

1. `HWTEST.TXT`.
2. The hardware: Falcon model, CT60 or CT63 and its clock, TT-RAM size, TOS
   version, monitor type and connection, the drive used.
3. The detail level the test ran at.
4. The notes from each step, and photos or a phone video of anything wrong.
   A short phone video of a flight with sound is the best evidence of all.
