# Playing Comanche on the Falcon

This is the player's guide to the Falcon programs: what you need, how to
install them, and the keys. The release packs it as `COMANCHE.TXT`. The port
is a preview: it is checked against the DOS original in emulators and has not
been run on a real Falcon yet.

## The two programs

- `COMANCHE.TOS` - for a Falcon030 (68030) with 14 MB of RAM. It plays the
  sound effects but no music. It is slow on a stock Falcon: about 2 frames a
  second in the cockpit in Hatari.
- `COMAN060.TOS` with `OPLDATA.BIN` - for a Falcon with a CT60 or CT63
  (68060) accelerator and TT-RAM (FastRAM). It plays the music and the
  effects; the music is an OPL2 (AdLib) emulation running on the Falcon's DSP.
  About 20 frames a second in Hatari's 68060 model. It does not run on a
  68030.

Both need an RGB/TV or VGA monitor. Only the RGB setup has run so far (in
Hatari).

## What you need from the DOS game

Your own copy of *Comanche: Maximum Overkill* (NovaLogic, 1992), installed
on a PC or in DOSBox. No game data comes with the programs: they read the
original's files when they start. `COMANCHE.EXE` must be the 61,154-byte file
of the original three-disk release; the program checks it and refuses another
version with a message naming the file.

## Installation

1. Make a folder on the Falcon's hard disk or CompactFlash card, for example
   `C:\COMANCHE`. The game needs about 10 MB.
2. Copy every file of the installed DOS game into it (upper or lower case
   names both work). The DOS programs and batch files are not used, but they
   do no harm.
3. Copy `COMANCHE.TOS` into the same folder - or, on a 68060,
   `COMAN060.TOS` and `OPLDATA.BIN`.
4. For the music (`COMAN060.TOS` only), `COMANCHE.CFG` must select the
   AdLib: its third character is the music device, and `3` is the AdLib. If
   the DOS game was set up for another sound card, replace the file's content
   with the ten characters `0132700000` (no line end).
5. Optional: the detail level. The game keeps it in `COMANCHE.MNU`, as in
   DOS; the shipped file says Medium. Change it in the game: press Esc in
   flight, pick Detail, then Save Menu Settings.

## Running

Start the program from the desktop. Do not run anything else that uses the
DSP at the same time (an MP3 player, a DSP accessory); the music then stays
silent.

The game starts with its attract cycle: title screens and recorded flights.
Press Space for the main menu. *Begin Mission* leads to the campaign, the
mission list and the briefing; Return starts the flight. *Exit to DOS*, the
menu's last row, quits to the desktop.

## Keys in flight

The port takes the keyboard only; the joystick is not read.

| Key | Action |
|---|---|
| Keypad 8 / 2 | nose down (faster) / nose up (slower) |
| Keypad 4 / 6 | turn left / right |
| `E` / `D` | collective up / down (climb, descend) |
| Tab | lock a target |
| Space | fire |
| `Z` `X` `C` `V` `B` `N` | gun, rockets, Hellfire, Stinger, bomb, the wingman's weapon |
| `;` / `'` | chaff / flare |
| `1` ... `8` | views (1 the cockpit, 7 and 8 outside views) |
| F1 ... F6, F7 ... F12 | page the left and the right cockpit display |
| Esc | the options bar: detail, sound, music, save settings |
| Alt+A | end the mission (the debrief follows; Esc leaves it) |

## If something goes wrong

- A message about `COMANCHE.EXE` at start: the file is missing or is not the
  file of the original three-disk release.
- No music on `COMAN060.TOS`: check `COMANCHE.CFG` (step 4), that
  `OPLDATA.BIN` is in the folder, and that nothing else holds the DSP.
- A bright red screen that stays: the port caught a CPU exception and holds
  the machine on purpose. Note what was happening and reset. Reports are
  welcome: the project's docs/HARDWARE-TEST.md says what helps most.
