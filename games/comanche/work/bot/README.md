# A pilot bot for the port

N/A - target harness. It plays the Falcon port under Hatari the way a player
would, to find what the attract replay cannot: live input, mission outcomes,
the campaign's progression and the saved roster.

- `hbot.py` starts Hatari (the F030Arcade build; 060/EmuTOS/TT-RAM by
  default) with a control FIFO. Keys go in as IKBD scancodes, always written
  in hex (`0x01`): a one-character argument is taken as a character, so
  `keydown 1` presses "1", not Esc. State comes out through the debugger:
  one `parse` of a script of `savebin`s, run between emulation steps, reads
  the flight state, all 130 object slots, the target latch, ammunition,
  screen and menu variables by symbol. `symbol()` names an address through
  the disassembler, which is how object state handlers are told apart.
- `pilot.py` flies one mission. It steers by bearing, sets the collective
  notch (E/D, `00001BA6`) for the terrain ahead, routes around ground the
  terrain follow cannot climb (byte(2h + 1) near the altitude ceiling), locks
  with Tab, fires the weapon for the target (Stinger and the locked gun at
  helicopters; the wingman's and own Hellfires and rockets at ground units),
  drops flares when an enemy shell is near, and defends from the ground
  against the patrol helicopters, which in the original too ignore a landed
  helicopter and destroy a hovering one. It can use the game's own KYLE
  cheat column (`00026012`; Fix Damage `00026B49`, Reload `00026B88`) and
  counts every use, so a win with repairs is never reported as a clean one.
- `campaign.py` boots the game and plays the mission list in order: it reads
  the row colours (`screen_mission_ink`: blue flown, green next, orange
  locked), flies the first green mission, ends a won one with Alt+A, and
  records each result in `results.json`.

```sh
python3 work/bot/campaign.py build/bot-campaign 10 2400
```

The roster is the staged `release/68060/COMANCHE.NAM`, so progress carries
from one run to the next exactly as a player's does; a rebuild restages it.
