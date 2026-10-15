# Comanche sound: the original's driver, its data and its call interface

Recovered 2026-10-07, DOS first (`AGENTS.md`, "The porting procedure"): every statement below was read off
`re/listings/comanche-flat32.lst` and the raw flat image `re/unpacked/comanche-flat32.bin`
(SHA-256 `a2c2b50d4e2d85ecbf210440927927323b0a176613beb25d74c0cdde8dae1a6c`, addresses are flat), and
the parts that matter for a port were then **checked against the running original**: the JavaScript
reference `jsComanche/dos-sound.js` replays the same calls as the DOS driver on QEMU and its output is
byte-for-byte the original's (section 9). What is read but not proven is marked **Unproven**.

This is the recovery half of phase 8 ("Deferred systems", `docs/PORTING-PLAN.md`). The silent-sound
boundary of that plan stands: nothing in the game's logic depends on a sound result except two screen
lengths (section 8). Status correction reviewed 2026-10-10: the digital half of
section 10's interface has since been implemented and wired into the native game;
its isolated mixer/DMA evidence and platform differences are in
[sound-falcon.md](sound-falcon.md). The music and FM half followed on 2026-10-15
(section 13): `src/music.s` replays all 23 of the original's OPL2 captures write
for write. What it drives - a synthesiser behind its register sink - and hardware
validation remain open; this does not promote the first silent playable
acceptance scope.

The §4.2 function records of the JavaScript routines are in `analysis/functions/browser-attract.md`,
sections `sound-driver-module`, `-core`, `-ms3`, `-effects`, `-opl`, `-mpu`, `-speaker`, `-digital`.

## 1. The shape of it, in one page

* **Two layers.** (1) The *music and FM driver* at `0002B9CF-0002C4A0`: it plays MS3 songs and a
  small table of FM sound effects on one of five devices (PC speaker, Sound Blaster FM, AdLib,
  Roland MT-32 through an MPU-401, nothing). Its only outputs are port writes: OPL2 register pairs to
  `0x388/0x389` (helper `0002C1B8`) or MPU-401 bytes to `0x330/0x331` (helpers `0002BF88`, `0002BFD9`).
  (2) The *digital effect layer* at `00004E0C-000053D5`: three 8-bit sample slots mixed in software into
  a Sound Blaster DMA double buffer (11,111 Hz, mono). All explosions, weapon sounds, the rotor and
  every spoken cue go through this layer when the configuration has a Sound Blaster
  (`COMANCHE.CFG` byte 1 = `1`, which the shipped file has). **Without it, only the SND1 effects 1..7
  fall back to the FM driver; speech has no fallback and is silent.**
* **One tick.** The PIT is programmed to `0x47B4` (18356, `00001CEB`): 1,193,182 / 18,356 = **65.0 Hz**.
  Its ISR `00001D20` calls the dword `[0002C48C]` once per interrupt (`00001D2C`). A successful device
  select stores `0002BBF2` there (the music tick), failure and start-up leave `0002B9F6` (a `ret`). The
  tick runs the sequencer and the per-channel pitch pass; nothing else of the driver is timed.
* **One command entry.** `0002B9CF`, `ax` = `command << 12 | parameter`: 0-2 play FM effect `al`
  (volume nibble in `ah`), 3 select device `al`, 4 pause, 5 resume, 6 "is a song playing" (`al` =
  `[0002C49E]`), 7 set music volume `al`, 8 detect device `al`. Songs start through `0002BD00`
  (`al` = flags, `ebx` = pointer), stop through `0002BEDC`.
* **The data.** Songs are `MS3` (a 48-byte header and a stream of `9n/8n/Cn/En` events with 65 Hz
  delays), stored bare (`.MS3`) or in `KRL0`/`KRL1` containers (`.RLE`). The OPL2 instrument table
  (128 patches of 16 bytes), the F-number table, the effect table and the voice maps are in the
  executable's data segment, not in any file.

## 2. Configuration, devices and what selects what

### 2.1 `COMANCHE.CFG` (10 ASCII bytes -> `[0x53D8..0x53E1]`, `00005528-00005559`, loaded at `0000554F-00005559`)

Startup (`000054F7`): `SOUNDSET.EXE` missing -> prints the string at `0x16539` (`Please run Comanche from its
directory`, via `00016562`); command-line tail non-empty (PSP `+0x80`, `00005510-00005522`) or `Comanche.CFG` missing ->
string at `0x164FF` (`Please type SOUNDSET to configure program`, via `0001652B`).

| byte | shipped | read at | meaning |
|---|---|---|---|
| `[53D8]` | `'0'` | never read (only the load destination `mov eax,0x53D8` at `0000554F`) | unused by COMANCHE.EXE |
| `[53D9]` | `'1'` | `0000558A-00005591` | `&0xF` -> `[0x19DF9]` and `DET`/mixer mode argument: **digital effect device** (0 none -> effects via FM; 1..4 all run the identical SB code: tables `0x4102/0x4116/0x412E` have the same entry in slots 1-4; `>4` rejected by `00004FBD/00004FC0` and `0000507C`) |
| `[53DA]` | `'3'` | `000055BD-000055C4`, `000055CF-000055D6`, `000069EF` | `&0xF` -> **music device** passed to FM cmd 8 (detect) and cmd 3 (select): 1 = PC speaker (port 0x61 / PIT ch2, `0002C432-0002C47D`), 2 and 3 = OPL at 0x388 (`0002C1B8-0002C1E8`, `0002C312`), 4 = MPU-401 at 0x330/0x331 (`0002BF88-0002C010`), 5 = "none" (all driver hooks are `ret`: `0002C485-0002C48A`; the song clock still runs, so a song still ends); and the literal `'1'` suppresses mission music (`000069EF`) |
| `[53DB]` | `'2'` | `00005566-00005577` | `((x&0xF)<<4)+0x200` -> `[0x1EF4]` SB base port (0x220) |
| `[53DC]` | `'7'` | `0000557D-00005585` | `x&7` -> `[0x1EF0]` SB IRQ (vector `8+irq`, `00001F70-00001F8A`) |
| `[53DD..53E1]` | `'0'` | never read | unused (DMA channel is hard-coded to 1: `00001FD1-00001FF6`) |

### 2.2 `COMANCHE.MNU` (35 bytes -> `[0x25DBC]`, read at `00005660-0000567E`; written by menu item "Save Menu Settings", selector 0x02 at `00026D8B` via `00015D40` ebx=0x23)

Settings block `[0x25DD4..0x25DD7]` = file bytes 24..27 = `'1','0','0','3'` (shipped): detail Medium, **Sound Loud**,
**Music Loud**, controller Keyboard. (`0x25DD5`, `0x25DD6` ASCII `'0'`/`'1'`/`'2'` = first/second/third radio line.)

| radio | menu selector (`00026CC2`) | value | effect |
|---|---|---|---|
| Sound Loud | `0x20` | `[0x25DD5]='0'` | `MODE(al=[0x19DF9])` (mixer on, transfer table `0x4C0A`) |
| Sound Soft | `0x21` | `'1'` | `MODE(al=[0x19DF9])` then `[0x5307]=0x4A0A` (table `0x4A0A`) |
| Sound Off | `0x22` | `'2'` | `MODE(al=0)` (mixer stops). With `[19DF9]==0` effects go through FM and are **not** affected by this radio; Music Off (pause) mutes FM effects too since cmd 4 sets the global mute `[0x2C49F]` |
| Music Loud | `0x24` | `[0x25DD6]='0'` | `[0x2C5A8]=0xFA`, `[0x19DF0]=0x5000`, `FM(0x5000)` (resume) |
| Music Soft | `0x25` | `'1'` | `[0x2C5A8]=0x73` in the radio handler (`00026D59`) but **`0x64`** in `000267F3` (`00026818`); `[0x19DF0]=0x5000`, `FM(0x5000)` |
| Music Off | `0x26` | `'2'` | `[0x19DF0]=0x4000`, `FM(0x4000)` (pause; `[0x2C5A8]` unchanged) |

`[0x2C5A8]` is the music master volume byte: `0x2BCA2 mul byte [0x2C5A8]` scales the per-channel base volume
`[0x2C5A9+ch]`; it is set to `0xFF` at every device init (`0002BAB0`). Therefore FM **cmd 7 is never used**; the effect
volume nibble is never used (0.5). The static defaults in the image if `COMANCHE.MNU` is missing are `'2','1','1','4'`
(bytes at `00025DD4`): Sound Soft / Music Soft.

### 2.3 What the config digits mean (decoded from SOUNDSET.EXE)

`SOUNDSET.EXE` (LZEXE, `unlzexe` unpacks it) writes `COMANCHE.CFG` as `0`, digital, music, port, IRQ and
five more `0`s. Read off its code (the digits at `1d2d`, `1e87`, `1a29`): the **digital** digit is
1 for the first menu row "Sound Blaster Compatible" and 0 for "No Digital Sound"; the **music** digit
is `4 - row` of the menu "Roland MT-32/LAPC-1 (4), Sound Blaster Compatible (3), Adlib/Adlib
Compatible (2), PC Speaker (1), No Music (0)"; the **port** digit is the row number + 1 of
`210..260`; the IRQ menu has the rows 2, 3, 5, 7 and stores a digit from a table SOUNDSET fills at run time
(`cs:[08D6 + row]`, zero in the file: **Unproven** which digits it holds; the game uses `digit & 7`, and the shipped
file's `7` is IRQ 7). The shipped `0132700000` is therefore
*Sound Blaster digital, Sound Blaster FM, port 220, IRQ 7*. The driver's device numbers are the same
digits: 1 PC speaker, 2 and 3 OPL2 (identical routines), 4 MPU-401, 5 empty (not offered by SOUNDSET).

## 3. The music and FM driver

### 3.1 Command entry and the device model

`0002B9CF` stores `ax` at `[0002C4A0]` and indexes the dword table at `0002C5D9` with the high nibble of
`ah`: `0,1,2` -> `0002BB09` (effect), `3` -> `0002B9F7` (select), `4` -> `0002BBC1` (pause: silence all
channels and set `[0002C49F]` = 0xFF, which refuses key-ons), `5` -> `0002BBD0` (resume), `6` ->
`0002BBBB` (`al` = `[0002C49E]`), `7` -> `0002BB01` (`[0002C5A8]` = `al`), `8` -> `0002BBDA` (jump through
the *detect* slot of device `al`, 0..5), `9..15` -> `0002B9F3` (`al` = 0). A selected device is a column of
seven routines copied into seven slots (`0002C649, 0002C665, 0002C681, 0002C69D, 0002C6B9, 0002C6D5,
0002C6F1`, each followed by a column per device 0..5 at +4):

| slot | role | speaker (1) | OPL2 (2, 3) | MPU-401 (4) | none (5) |
|---|---|---|---|---|---|
| `0002C649` | init (returns `al` = 0 on failure) | `0002C432` | `0002C312` | `0002C135` | `0002C485` (`ret`) |
| `0002C665` | end of tick | `0002C43B` | `0002C37F` | `0002C01D` | `0002C486` |
| `0002C681` | silence all (also on shutdown) | `0002C43C` | `0002C354` | `0002C0FA` | `0002C487` |
| `0002C69D` | note: `ch`, `ah` = pitch (0 = off), `cl` = velocity | `0002C443` | `0002C3C9` | `0002C01E` | `0002C488` |
| `0002C6B9` | pitch: `ch`, `ah` | `0002C45F` | `0002C380` | `0002C07D` | `0002C489` |
| `0002C6D5` | patch: `ch`, `al` = patch | `0002C47E` | `0002C254` | `0002C0CA` | `0002C48A` |
| `0002C6F1` | detect | `0002C47F` | `0002C1EA` | `0002C18A` | `0002C482` |

*Select (command 3, `al` = 1..5).* A device already selected is shut down: the ten effect flags
`[0002C5C9]` are cleared, the music silenced, its silence routine called. The new column is copied, the
pause flag cleared, init called. If init returns `al` = 0 the tick vector is `0002B9F6` and the command
returns 0 (the game then does not use the device); otherwise the music is stopped, the ten channels'
state reset (master volume `[0002C5A8]` = 0xFF, both envelope cursors of every channel at the default
envelope `0002D5D0`), `[0002C48C]` = `0002BBF2`, and the command returns 0xFF. Device 5's init is a `ret`,
so its "result" is whatever the last slot copy left in `al` (0x82): it counts as success, the song clock
runs, nothing is written (capture `openmus-none`).

*Startup order* (`000055B4-000055D8`): command `0x80|device` (detect); if it returns non-zero, command
`0x30|device` (select). `[0002C48C]` therefore stays `ret` and no song ever ends when the detect fails
(section 8).

### 3.2 Variables (flat addresses; all inside the image, so a port can keep the layout)

| address | size | meaning |
|---|---|---|
| `0002C48C` | dword | tick vector |
| `0002C490` | dword | cursor of the next event |
| `0002C494`, `0002C498` | dword | the song being played / the song queued behind it (0 = none) |
| `0002C49C`, `0002C49D` | byte | flags the playing / the queued song was started with |
| `0002C49E` | byte | 0xFF while a song runs |
| `0002C49F` | byte | 0xFF while paused |
| `0002C4A0` | word | the `ax` of the last command |
| `0002C4A2` | word | ticks until the next event |
| `0002C4A4` | 16 bytes | last note per MIDI channel (written, never read) |
| `0002C4B4`, `0002C4C4` | 10 bytes each | channel links / the song's patch per channel (copied from the header) |
| `0002C4D4` | 10 bytes | the patch loaded on the channel (0xFF = none) |
| `0002C4E4` | byte | the selected device |
| `0002C4E8`, `0002C528` | 10 dwords each | pitch-envelope cursor / its start |
| `0002C568` | 10 bytes | pitch offset set by the `En` events |
| `0002C578` | 10 bytes | the pitch the channel was last keyed at (plus transpose) |
| `0002C588` | 10 bytes | the pitch last sent to the device (0xFF = none) |
| `0002C598`, `0002C5A9` | 10 bytes each | the loaded patch's transpose / volume scale |
| `0002C5A8` | byte | music master volume |
| `0002C5B9` | 10 bytes | channel keyed on |
| `0002C5C9` | 10 bytes | non-zero: the channel belongs to an effect, for that many more ticks |
| `0002D10D`, `0002D116` | 9 bytes each | OPL: the patch's byte 1 / the shadow of register B0 |
| `0002D404` | dword | which half of an effect is being played |
| `0002D161` | word | the MPU wait count (`[00001C8E] << 5`) |

Channels are music channels 0..9 (a note's channel nibble is 4 bits, but the arrays hold ten: a channel 10..15
would index into the next array; the shipped songs use 0..7). Which physical voice or MIDI channel a music channel
reaches is a table per device: OPL `0002D131` (channels 0..7 -> voices 0..7, 9 -> voice 8, others none),
MIDI `0002D141` (channels 0..7 -> MIDI 1..8, 9 -> 9, others mute).

### 3.3 MS3 songs

All multi-byte numbers in the files are little endian; the pointer the driver is given points at the `M`.

| offset | size | meaning |
|---|---|---|
| 0x00 | 14 | `MS3-KGF'91 ` + `0A 0D 1A` (signature, never checked by the driver) |
| 0x0E | 2 | a word the driver never reads (the files carry 0x003F, 0x007F, 0x00FF, 0x000F, ...) |
| 0x10 | 10 | channel links: byte n of channel c non-zero = every event of c also plays on channel n-1 (chained: OPENMUS 5 -> 6 -> 7) |
| 0x1A | 6 | unused |
| 0x20 | 10 | patch loaded on each channel when the song starts (becomes the channel's song patch) |
| 0x2A | 6 | unused |
| 0x30 | ... | events up to `FF 2F` |

*Events.* A status byte, its data, then the delay to the NEXT event. `9n note vel delay`: note on, channel
n. `8n delay`: note off (it names no note: the channel's last note is released). `Cn patch delay`: load
`patch` on channel n **now** and make it the channel's song patch. `En x delay`: set channel n's pitch
offset to `x`; it is added to the pitch every tick from then on (FANFARE uses it for slides: 80 of its
156 events). `Dn x delay` and `Bn x y delay`: skipped. Any other status byte is treated as `Dn`. `FF 2F`
(as the first two bytes of an event) ends the song. The delay is one byte below 0x80, or two bytes
`((b0 & 0x7F) << 7) | b1` (the driver does not mask `b1`). A delay of 0 means the next event happens in
the same tick. The driver counts ticks in `[0002C4A2]` (a song starts with 1, so the first tick plays the
first events) and takes events until it reaches a non-zero delay.

The shipped songs never use `Bn`, `Dn`, an unknown status or a channel above 9; two songs built by the probe
(`synthetic-events`, `synthetic-links`) do, and the JavaScript agrees with the original on them.

*Playing an event.* A `9n` or `8n` on a channel whose effect flag `[0002C5C9+n]` is non-zero is dropped
(an effect owns the channel until it expires). Otherwise, for a note on or off: if the channel's song patch differs
from the loaded patch it is loaded (the device's patch routine); then the note `x2` is keyed on, or the channel keyed off
(see 3.4); then the channel's link (`[0002C4B4+n]` - 1) is processed the same way (patch, key) until the link is 0.

*Flags of `0002BD00`* (`al`): bit 0 = queue behind a song that is playing (otherwise start at once), bit 1 =
loop. When the song ends (`FF 2F`) every channel without an effect is keyed off and the tick count is 1;
then, in order: the queued song starts (and the queue clears), else the same song restarts if bit 1 was set,
else `[0002C494]` = 0. `[0002C49E]` is 0 from the end until the next start, which is what command 6 reports.
A song consisting only of `FF 2F` with the loop flag (`MENUMUS1.MS3`) therefore silences every channel on
every tick. `0002BD00` with `ebx` = 0 does nothing.

*Containers (the loader `00015E6E`).* A music file loaded with `15E6E` begins `KRL0` or `KRL1` and a dword
size. `KRL0`: the `size` bytes that follow are the song. `KRL1`: the bytes that follow are run-length coded
(`0001644B`): a byte below 0xC0 is literal; otherwise `count = byte & 0x3F` and the next byte repeats
`count` times; until `size` bytes are produced. `.MS3` files (`OPENMUS`, `MENUMUS1`, `MENUMUS2`) are read
raw by `00015DD0` into the BSS buffers `0002DB10` and `0002DF10`. The song's address is where the loader
leaves it: an allocation of the game's bump allocator `00025777` (heap pointers, e.g. `003BE7CC` for the
mission music), the signature at the pointer.

The eleven shipped songs (measured from the files; "ticks" is the sum of the delays):

| file | container | bytes (decoded) | events | ticks (65 Hz) | channels used | patches (header, program changes) | note range | links |
|---|---|---|---|---|---|---|---|---|
| OPENMUS.MS3 | bare | 754 | 234 | 741 | 0,1,2,3,4,5 | 32 31 31 58 5A 70 00 38 ; prog 31 58 5A 70 | 26-80 | ch5>ch6 ch6>ch7 |
| MENUMUS1.MS3 | bare | 51 | 0 | 0 | - | 58 31 31 31 52 54 33 49 | - | ch6>ch7 |
| MENUMUS2.MS3 | bare | 1203 | 384 | 2015 | 0,1,2,3,4,5,6 | 58 31 31 31 52 54 33 49 | 38-83 | ch6>ch7 |
| FANFARE.RLE | KRL0 | 519 | 156 | 278 | 0,1,2,3,4,5,6,7 | 58 58 32 56 24 2B 5C 5D | 34-84 | - |
| MUSDAY.RLE | KRL1 | 11613 | 3854 | 10191 | 0,1,2,3,4,5,6,7 | 32 32 21 48 31 21 32 32 | 30-69 | - |
| MUSNIGHT.RLE | KRL1 | 2280 | 743 | 3126 | 0,1,2,3,4 | 5F 0A 0A 0A 00 00 00 00 ; prog 0A 21 5F | 38-62 | - |
| MUSVOLC.RLE | KRL1 | 13024 | 4324 | 8841 | 0,1,2,3,4,5,6,7 | 15 32 32 32 72 72 19 34 | 33-81 | - |
| MUSWIN.RLE | KRL1 | 4761 | 1570 | 2869 | 0,1,2,4,5,6,7 | 58 5E 5A 72 31 31 54 72 | 45-79 | ch0>ch8 ch7>ch3 |
| MUSLOSE.RLE | KRL1 | 1647 | 532 | 2240 | 0,1,2,4,5 | 31 31 5C 48 5E 54 4C 56 | 40-84 | ch2>ch3 |
| WINMUS.RLE | KRL1 | 1077 | 342 | 1295 | 0,1,2,3,4,5,6,7 | 58 58 31 31 31 59 59 59 | 34-66 | - |
| BIGWIN.RLE | KRL1 | 8899 | 2948 | 11695 | 0,1,2,3,4,5,6,7 | 58 36 31 31 5A 00 00 00 ; prog 31 33 52 54 58 5A 5C 5E 70 72 | 2-88 | - |

Only `OPENMUS.MS3`, `MENUMUS1`, `MENUMUS2`, `FANFARE.RLE`, `MUSDAY`, `MUSNIGHT`, `MUSWIN` and `MUSLOSE` are
named by game code or by the two shipped mission files (`0.MIS` day, `1.MIS` night); `MUSVOLC`, `WINMUS`
and `BIGWIN` are on disk but reached by nothing in this install (**Unproven** whether other missions use
them). All shipped songs use music channels 0..7 only.

### 3.4 Channels, patches, the key-on and the tick

*Loading a patch* (`0002BF3A/BF43`, `al` = patch 0..127): `[0002C4D4+ch]` = patch; the channel's pitch
envelope pointer = the dword `[0002D5E6 + 4*patch]` (both cursor and start); scale = `[0002D550+patch]`
(all 0x80); transpose = `[0002D4D0+patch]` (all 0); then the device's patch routine. All 128 pointers
point at `0002D5D2` (`00 80`: "add 0, then hold") except patches 125 and 127, which point at `0002D5D4`
(a 17-step pitch wobble, `0C 0A F6 05 0A FB 00 05 F7 0F 00 FC 09 FF 02 00 0A 81`: the channel's pitch is the base
pitch plus the current step, so it jitters by up to a few quarter-tones around the base while the effect or its tail
runs, and keeps jittering after the channel is keyed off until the channel is used again; `81` loops it, `80` holds).

*Key* (`0002BC8B`, `ch`, `ah` = pitch index (0 = off), `cl` = velocity). Off (or paused): `[0002C5B9+ch]` =
0, device note routine with `ah` = 0. On: `hi = (scale[ch] * master) >> 8` (8-bit multiply, high byte),
`cl = ((hi + 1) * ((cl << 1) & 0xFF)) >> 8`, the envelope cursor is rewound, `[0002C5B9+ch]` = 1, the pitch
`ah + transpose` becomes `[0002C578+ch]`, `[0002C588+ch]` = 0xFF (so the next tick sends it), then the
device note routine. For the default scale 0x80 and master 0xFF the velocity passes unchanged. Music
passes `ah` = 2 x note; effects pass their table pitch.

*The tick* (`0002BBF2`): (1) if a song runs, the sequencer; (2) for channels 9 down to 0: `ah` = base pitch
`[0002C578+ch]`; if the effect time `[0002C5C9+ch]` is non-zero it is decremented and, when it reaches 2, the
channel is keyed off (`ah` = 0); `ah += [0002C568+ch]`; the envelope: take the byte at the cursor, 0x80 =
keep, 0x81 = rewind to the start and take again, else `ah += byte` and the cursor advances; if `ah` differs
from `[0002C588+ch]` it is stored there and the device's pitch routine is called with it; (3) the device's
end-of-tick slot. The key-on is therefore made with the channel's previous
pitch and the pitch (A0/B0) follows in the next pitch pass: in the same tick for a song's note (the sequencer
runs before the pitch pass), in the next tick for an effect, which a command starts between ticks. Quirk found by the captures: the OPL write helper
returns with `ax` = 0, so after the effect expiry's key-off `ah` is 0 and the pitch routine is called with
pitch 0 (F-number `0x0083`).

### 3.5 The OPL2 device (devices 2 and 3)

Port protocol of `0002C1B8` (all writes of the driver): `out 0x388, reg`; delay; `out 0x389, value`;
delay. The delays are two and four passes of a loop that counts `[00001C8E]` down (a start-up calibration,
`0002C1C2-0002C1E5`); they separate the writes in time and are not part of the stream.

*Init* (command 3, 118 writes, capture `select-adlib`): `01 <- 20` (waveform select), `08 <- 00`, `BD <- C0`
(deep tremolo and vibrato, rhythm off), then for each of the nine voices `40+carrier offset <- 3F` and `B0+v <- 00`;
then `B0+v <- 1F` and patch 0 on channels 0..7 (voice 8 belongs to channel 9, which gets a patch with
its first `Cn`). *Detect* (command `0x80+d`): `04 <- 60`, `04 <- 80`, read status (must be 0 in the top three
bits), `02 <- FF`, `04 <- 21`, wait, read status (must be 0xC0 in the top three bits), `04 <- 60`, `04 <- 80`.

*Operators.* Voice v has its two operators at the offsets in `[0002D11F+v]` (the first operator: 00 01 02 08
09 0A 10 11 12) and `[0002D128+v]` (the second, the carrier in FM mode: 03 04 05 0B 0C 0D 13 14 15).

*Patch* (16 bytes at `0002C70D + 16*patch`; the loaded bytes are 11, byte 15 is 0x80, the rest 0):

| byte | register |
|---|---|
| 0 | `20 + carrier` (tremolo, vibrato, sustain, KSR, multiplier) |
| 1 | not written: kept in `[0002D10D+v]` as the carrier's level/KSL base for the key-on |
| 2 | `60 + carrier` (attack, decay) |
| 3 | `80 + carrier` (sustain level, release) |
| 4 | `E0 + carrier` (waveform) |
| 5 | `20 + first operator` |
| 6 | `40 + first operator`, written inverted (`xor 3F`) |
| 7, 8, 9 | `60`, `80`, `E0 + first operator` |
| 10 | `C0 + v` (feedback, connection) |

Loading starts with `B0+v <-` the B0 shadow with the key bit cleared.

*Key on.* `40 + carrier <- (byte1 | min((cl >> 2) + 0x20, 0x3F)) ^ 0x3F`, then `B0+v <- shadow | 0x20`.
*Pitch.* `w = word[0002CF0D + 2*ah]` (F-number in bits 0..9, block in 10..12): `shadow = (w >> 8) | (shadow & 0xE0)`,
`A0+v <- w & 0xFF`, `B0+v <- shadow`. *Key off:* `B0+v <- shadow & 0xDF`. The F-number table has 24 entries per
octave starting at F-number 0x83 (a quarter-tone each), and a song note n is keyed at index 2n.
Observation (arithmetic on the shipped words with the chip's 49,716 Hz): MIDI note 60 sounds at 198 Hz and
note 69 at 334 Hz, 4.8 semitones below concert pitch; the MPU path sends the plain note.

An example, the first tick of `OPENMUS.MS3` (66 writes, from the capture): for channels 0..5 the patch from
the header is loaded (`B0 <- 1F`, then the eleven registers), the first notes are keyed (`40+carrier`,
`B0 <- key`), and the pitch pass follows (`A0`, `B0`) on the next tick.

### 3.6 The MPU-401 device (device 4)

The driver talks to the MPU-401 in UART mode (command `0x3F`); the intelligent-mode prefixes (`0xD0`, `0xDF`)
are sent to `0002BFAA`, which is a bare `ret`. `0002BF88` waits for bit 6 of `0x331` to clear and writes
the byte to `0x330`; `0002BFD9` the same for `0x331` and then waits for the acknowledge on `0x330`.
*Init*: the MT-32 SysEx at `0002D163` (`F0 41 10 16 12`, then, with a running checksum reset by `FC`,
address `20 00 00` and the 20-character text "Maximum Overkill" + two spaces, then the checksum (`FD`)
and `F7`; `FF` ends) which puts that text on the MT-32's display, then command `3F`. *Silence*: `B0+n 7B 00`
for the 16 MIDI channels, then init again. *Note*: `9c note vel` (note `ah >> 1`, velocity capped 0x7F), off
`8c note 40`. *Pitch*: `E0+c lo hi` where P = `((pitch - base + 0x18) & 0xFF) * 0xAA`, lo = low 7 bits of 2P, hi =
bits 8..14 of 4P (a bend that follows the envelope and the `En` offsets). *Patch*: `Cc (map[patch] - 1)` with
the map at `0002D183` (identity for 1..0x7B, with `0002D1FD..` changed to 73 7F 71). *Detect*: `FF` to
`0x331`, expect `FE`, once more if not.

### 3.7 The PC speaker (device 1)

One voice (channel 0): note on sets PIT channel 2 (`out 43, B6`, `out 42` low, `out 42` high with the word at
`0002D203 + 2*ah`) and bits 0..1 of port `0x61`; off clears bit 1. The init and silence clear bit 1.

### 3.8 FM effects (command 0, 1, 2)

Entry `0002BB09`, table `0002D408`, 25 entries of 8 bytes (two voice records of 4 bytes: duration in ticks,
patch + 1, pitch, volume factor):

| id | first voice (ticks, patch, pitch, volume) | second voice | used by the game (FM fallback) |
|---|---|---|---|
| 0 | dur 10, patch 31, pitch 0x80, vol 0x50 | - |  |
| 1 | dur 10, patch 125, pitch 0x42, vol 0x7F | - | explosion (SND1 id 1) |
| 2 | dur 15, patch 109, pitch 0x96, vol 0x64 | - | timed blast stage 2 |
| 3 | dur 2, patch 110, pitch 0x32, vol 0x64 | - |  |
| 4 | dur 4, patch 115, pitch 0x63, vol 0x7F | dur 4, patch 111, pitch 0x63, vol 0x7F | rocket, Hellfire, Stinger, wingman Hellfire launch |
| 5 | dur 35, patch 127, pitch 0x5F, vol 0x7F | - | player hit, crash, killed |
| 6 | dur 10, patch 125, pitch 0x42, vol 0x7F | - | timed blast detonation |
| 7 | dur 3, patch 114, pitch 0x42, vol 0x7F | - | cannon burst |
| 8 | dur 20, patch 39, pitch 0x32, vol 0x7F | - |  |
| 9 | dur 20, patch 40, pitch 0x28, vol 0x64 | - |  |
| 10 | dur 20, patch 41, pitch 0x50, vol 0x50 | - |  |
| 11 | dur 10, patch 42, pitch 0x32, vol 0x64 | - |  |
| 12 | dur 10, patch 43, pitch 0x32, vol 0x64 | - |  |
| 13 | dur 10, patch 44, pitch 0x64, vol 0x7F | - |  |
| 14 | dur 10, patch 45, pitch 0x64, vol 0x7F | - |  |
| 15 | dur 10, patch 46, pitch 0x64, vol 0x7F | - |  |
| 16 | dur 10, patch 47, pitch 0x64, vol 0x64 | - |  |
| 17 | dur 10, patch 48, pitch 0x64, vol 0x64 | - |  |
| 18 | dur 10, patch 49, pitch 0x64, vol 0x64 | - |  |
| 19 | dur 10, patch 50, pitch 0x64, vol 0x64 | - |  |
| 20 | dur 10, patch 51, pitch 0x64, vol 0x64 | - |  |
| 21 | dur 10, patch 52, pitch 0x64, vol 0x64 | - |  |
| 22 | dur 10, patch 53, pitch 0x64, vol 0x64 | - |  |
| 23 | dur 10, patch 54, pitch 0x64, vol 0x64 | - |  |
| 24 | dur 10, patch 55, pitch 0x64, vol 0x64 | - |  |

Algorithm (`ax` = `volume << 8 | effect`; the game always passes volume 0, i.e. full, `0002BBA0-0002BBAB`).
*Presence test:* the **second** voice is played first if the dword at `0002D40C + effect` is non-zero (the
original indexes this with the effect number, not 8x it: the test reads the neighbouring entries' bytes,
which is non-zero for every effect from 1 on, so effects with one voice also play a second half made of zeros -
duration 0, patch `0xFF`, pitch 0 - that keys a channel off through the out-of-table patch 255; the first half then takes the same channel); then the
first. *One voice (`0002BB51`):* the first free channel (`[0002C5B9+ch]` = 0) of the device's list at
`0002C619 + 8*device` (OPL: 7 6 5 4 3 2 1 9; MPU: 7 6 5 4 3 2 1 0; speaker: 0), the last of the list if all are
taken; `[0002C5C9+ch]` = duration; load patch `byte1 - 1`; key at pitch `byte2` with
`cl = (byte3 * volume) >> 8` where `volume` = the nibble << 4 (0xFF for 0). The channel is keyed off when its
time reaches 2 (3.4), so an effect lasts `duration - 2` ticks; while it lasts the song's events on that channel
are dropped. Only the ids 1, 2, 4, 5, 6, 7 are used by the game (via `00004E8E` when no digital device exists);
the others are unreferenced.

## 4. The digital effect layer

### 4.1 Hardware and start-up

`COMANCHE.CFG` digital digit non-zero: `00004FBB` probes the Sound Blaster (`[00004116 + 4*type]`, all four
types `00001EF6`), `00004FE4(al)` prepares two 0x800-byte half buffers at `[00004FD4]` (0x20E2 or 0x30E2 so that
neither crosses a 64 KB boundary, `00005023-00005063`) filled with 0x80; mode 1..4 then starts the SB
(`00001F49`: DSP time constant `0xA6` = 11,111 Hz, 8-bit mono, DMA channel 1 auto-init, IRQ `[00001EF0]`, port
`[00001EF4]`); the IRQ's ISR `00002050` calls `00005220` (the fill) for the half that just finished. At game
start `00004FE4(0xFF)` only prepares the buffers; the mixer is started by `000267F3` ("apply sound settings") and
stopped by `00004FE4(0)` at every screen change. `00004E0C(al)` sets the dither mask `[00004194]` from the
dword table `00004998` (the game calls it with 2: mask 0x1F).

### 4.2 Sample banks

#### 4.2.1 FX `00004E8E`, bank `[0x19E98]` = SND1.RLE (7 samples), `ebp` = id; FM fallback table `0002D408+8*id`

| id | limit / step | length at 11.1 kHz | used by (rows) | meaning (from the call context; the code never names them) |
|---|---|---|---|---|
| 1 | 27081 / `FFFF` | 2.4 s | 36, 48 | explosion at the spawn/transformation of a BOOM wreckage; distance-attenuated (`dl`=0..4) |
| 2 | 13052 / `8000` | 2.3 s (half-rate source) | 46 | timed-blast stage 2 (tick 0x64) |
| 3 | 728 / `FFFF` | 65 ms | 16, 31 (via VOICE, not FX) | **rotor loop** (looped by staging the same pointer on slot 2) |
| 4 | 11712 / `FFFF` | 1.05 s | 38 (x2 pitch), 39, 40, 41 (dl=1) | missile/rocket launch (rocket page 1, Hellfire page 2, Stinger page 3, wingman Hellfire page 5) |
| 5 | 7748 / `FFFF` | 0.70 s | 35, 43, 44 | the player being hit / crashing / killed by the blast |
| 6 | 11536 / `8000` | 2.1 s (half-rate source) | 47 | timed-blast detonation (tick 0x78) |
| 7 | 2753 / `FFFF` | 0.25 s | 37 | cannon burst (`bl=0xFE`: re-trigger the same slot) |

If `[0x19DF9]==0` the same ids go to FM cmd 0 (`ax=id`), which indexes the 8-byte records at `0002D408+8*id`
(two 4-byte voice records per id; id 4 is the only one with both halves filled: `04 74 63 7F | 04 70 63 7F`).

#### 4.2.2 SFXA `00004E2E`, bank `[0x19E9C]` = SPEAK1.RLE (15 samples), `al` = id

| id | limit / step | length | used by (rows) | meaning (call context) |
|---|---|---|---|---|
| 1 | 15050 / `FFFF` | 1.35 s | 53, 54, 55, 56 | common "object destroyed" cue played with every wreck of a mission object (oil tank, type 9, mobile units, default units) |
| 2 | 3282 / `FFFF` | 0.30 s | 34 | crash cue, variant A (`rng&1==0`) |
| 3 | 4016 / `FFFF` | 0.36 s | 34 | crash cue, variant B |
| 4 | 13024 / `FFFF` | 1.17 s | 26 (cell1 = engine) | "engine failed" warning |
| 5 | 14256 / `8000` | 2.6 s | 52 | wingman destroyed |
| 6 | 17158 / `FFFF` | 1.54 s | 25 | mission start |
| 7 | 19552 / `FFFF` | 1.76 s | 49 | last mission goal destroyed |
| 8 | 15408 / `FFFF` | 1.39 s | 26 (cell0 = tail rotor) | "tail rotor failed" warning |
| 9 | 6890 / `84A7` (step 0.518) | 1.20 s | 45 | timed-blast countdown cue (tick 0x46) |
| 10 | 10024 / `8000` | 1.8 s | 51 | wingman attack-order acknowledgement |
| 11 | 20680 / `FFFF` | 1.86 s | 33 | crashing helicopter, chase-view switch |
| 12 | 9255 / `8000` | 1.7 s | 50 | wingman acknowledgement when the wingman is the latch |
| 13 | 15152 / `FFFF` | 1.36 s | 26 (cells 2 and 4: target select, target lock) | system-failure warning |
| 14 | 14000 / `FFFF` | 1.26 s | 26 (cell5 = gun) | gun failed warning |
| 15 | 14704 / `FFFF` | 1.32 s | 26 (cell3 = rocket launcher) | rocket launcher failed warning |

Damage cells (`[0x19E38..3D]`, start 0x0A each, decremented by hits `00019494-000194B2` and `00023617-00023637`,
negative = failed): cell0 `[19E38]` tail rotor (`000190AB`), cell1 `[19E39]` engine (`00018F96`), cell2 `[19E3A]`
target-select key (`0001924C`), cell3 `[19E3B]` rocket launcher (`00022B09`, `000073F2`), cell4 `[19E3C]` target-lock
hold (`000192CF`), cell5 `[19E3D]` gun (`0002289B`, `000073DF`). The announcer table (`19E28..19E2D`, indexed `ecx=1..6`
= cell0..cell5) is `08 04 0D 0F 0D 0E`. Static contents of the flags `[19E30..35]` are 0; they are re-zeroed at every
mission load by `0000688B` and set once per failure by `00006A8B`.

#### 4.2.3 SFXB `00004E26`, bank `[0x19EA0]` = SPEAK0.RLE (2 samples)

| id | limit / step | length | used by | meaning |
|---|---|---|---|---|
| 1 | 12277 / `FFFF` | 1.10 s | row 42 | timed-blast launch (weapon page 4) |
| 2 | 7775 / `FFFF` | 0.70 s | row 30 | hostile entering the sight window (rising edge) |

Both SFXA and SFXB: `esi==0` (bank not loaded) -> return (`00004E34`); a pending one-shot on slot 2
(`[0x417A]!=[0x4156]`, `00004E39-00004E45`) -> return; slot choice `bl=2`, or `bl=1` when slots 0 and 1 are both
idle (`00004E47-00004E61`); skipped if the sample is already playing in slot 0 or 1 (`00004E70-00004E7E`);
started with `dl=0, ecx=0` via `00004EA2`. There is **no FM fallback** for SFXA/SFXB (they never test `[19DF9]`).

### 4.3 Slots and requests

Three slots; slot s has the playing sample `[0000414E+4s]`, limit `[0000415A+4s]` (the record's first word), step
`[00004142+4s]`, position `[00004166+4s]` (16.16, 4.0 at the start: the two header words are skipped), and a
*staged* sample `[00004172+4s]` with step `[0000417E+4s]`, shift `[0000418D+s]` and bias `[0000418A+s]`. A slot
holding the silence record `000040E2` (limit 15, step 0, eleven 0x80 bytes) is idle. The shift `dl` (0..7) is a
right shift of the sample byte applied in the mix loop; its bias comes from `[00004A02 + dl]` = `00 40 60 70 78 7C 7E 7E`
(both are patched into the loop's immediates at `0000527A/C`, `000052A4/7`, `000052D0/3`).

* `00004EA2(eax = sample, bl = slot spec, dl = shift, ecx = step or 0)`: `bl < 0x80` = that slot; `0xFF` = the first
  idle slot, else the slot already playing exactly this sample, else slot 0 if `dl` = 0, else the sound is dropped;
  `0xFE` = skip the idle search. The slot's sample, limit, step (`ecx`, or the record's word when 0) and position 4.0
  are set; **starting is immediate** (the old sample is simply replaced).
* `00004E8E` (`ebp` = id in SND1, `bl`, `dl`, `ecx` from the caller): when `[00019DF9]` is 0 it is
  `mov eax, ebp; jmp 0002B9CF` (the FM fallback), else `eax = [bank + 4*ebp] + bank` into `00004EA2`.
* `00004E2E` / `00004E26` (`al` = id in SPEAK1 / SPEAK0): nothing if the bank is not loaded or slot 2 still
  has a one-shot staged; slot 2, or 1 if slots 0 and 1 are both idle; skipped if that sample is already playing
  on slot 0 or 1; `dl` = 0, `ecx` = 0.
* `00004F6E(eax = sample, bl = slot, dl, ecx)`: *stages* the sample as the **next** one of the slot (pointer, step,
  shift, bias are stored); if the slot is idle it starts at once. The mixer takes the staged sample when the playing one
  ends: staging the same sample again is how the rotor loops.
* `000050B4`: every staged sample becomes the silence record (step 0, shift 0, bias 0), and every playing sample that is not
  already silence is replaced by it (limit 15, step 0, position 4).

### 4.4 The fill (`00005220`, once per half buffer)

For each of the 0x800 output bytes: for each slot, if `position >> 16 >= limit` the staged sample becomes the playing
one (limit, step, shift, bias reloaded, position = 4.0); `v = ((byte at (position >> 16) of the sample) >> shift) + bias`
(8-bit), `position += step`; `sum = v0 + v1 + v2`; the dither: `e = [00004198 + (counter & [00004194])]`,
`counter` is `[00004190]` (incremented), `t = sum + e + 1`, the new error byte is `(t >> 2) & 0xFF`, the table index
is `t >> 1`, and the output is the byte at `table + index` where the 512-byte table is `4C0A` (Sound Loud: `clamp(index - 128, 0, 255)`) or `4A0A` (Sound
Soft: `index >> 1`), the displacement written into the instruction at `00005305` (`[00005307]`). The error feedback
makes an idle mix (three silence slots, `sum` = 384) settle at index 256, which is why silence comes out as 0x80.

## 5. Who calls what, and when

Every call site of the eleven entry points (80, found twice, once in the listing and once by scanning the
image for relative branches and absolute dwords; no indirect use exists). Section 9 lists which of them the
natural-flow capture saw the game execute (49 of the 80, plus two reached through a routine that tail-jumps into the entry).

#### 5.0 Corrections to the working model (the rows below cite them as "0.n")

1. `VOICE 00004F6E`: `eax`=sample record pointer, `bl`=slot 0..2, **`ecx` = pitch step (16.16 fraction added per
   output sample; 0 = use the record's own word at +2)**, not "length/loop"; **`dl` = attenuation index 0..7**
   (full volume, 1/2, 1/4 ... as a right shift) not a priority class. Evidence: `00004F01-00004F13` (word at `[esi]`
   -> per-slot limit `[0000415A+4*slot]`, `ecx` or word at `[esi+2]` -> step `[00004142+4*slot]`, position
   `[00004166+4*slot]=0x40000` = byte 4); `00004F2D-00004F64` (dl -> shift count byte patched into the mix loop at
   `0000527A/000052A4/000052D0` and bias `[00004A02+dl]` into `0000527C/000052A7/000052D3`; table `00 40 60 70 78
   7C 7E 7E`).
2. Sample record layout (`K1` bank): `u16 limit, u16 step, u8 pcm[...]`; playable bytes are record+4 .. record+limit-1;
   `step=0xFFFF` ~ 1.0 (native rate), `0x8000` = half-rate recording. Bank layout: `'K1'`, `u16 count`, then `count`
   dword offsets from the bank start beginning at +4, so **id N (1-based) -> `[bank+4*N]`**: this is why
   `00004E6B` (`mov eax,[esi+eax*4]`) and `00004E9D` (`[esi+ebp*4]`) use unscaled 1-based ids (id 0 would read the
   `'K1',count` header dword).
3. Slot allocation inside `00004EA2` (reached by FX and by SFXA/B and by VOICE when the slot is idle): `bl<0x80` = that
   slot; `bl=0xFF` = first idle slot (slot 0,1,2, idle == `0x40E2`), else the slot already playing this exact sample
   pointer, else (if `dl==0`) steal slot 0, else drop the sound; `bl=0xFE` = skip the idle search (same-sample slot,
   else steal slot 0 if `dl==0`, else drop). Addresses `00004EA8-00004EF3`.
4. `MODE 00004FE4` called at **`0000559F` with `al=0xFF`** (the "present" result of DET, `00001F43 mov eax,-1`):
   `cmp bl,4` fails at `00005079`, so it only stops the old mode, rebuilds the DMA double buffer and fills it with
   `0x80`, then returns 0 **without starting the mixer**. The mixer is really started by `000267F3` (see c.).
5. Effect volume nibble of FM cmd 0-2 is never supplied by game code: the only FM-effect entry is `00004E89 jmp
   FM` with `eax=ebp` (`ah=0`), which `0002BBA0-0002BBAB` turns into full level (`ah=0 -> 0xFF`). FM cmd 7 (set
   music volume) is **never issued** by the game (no `mov ah,0x70` in the image); the volume is poked straight into
   `[0002C5A8]` (see c.).
6. SB mixer facts (for the spec author): DSP time constant `0xA6` (`00001FBC-00001FC6`) = 11,111 Hz, 8-bit mono,
   DMA channel 1, double buffer of `2*0x800` bytes at `[4FD4]` (`00005220` toggles `[4FDC]^0x800`), IRQ vector
   `8+[1EF0]`; the ISR at `00002050` calls the filler `00005220` (`000020D5`). Per output sample: three voices summed,
   `+dither`, `>>2`, then a 512-byte transfer table: **Loud = `0x4C0A`, Soft = `0x4A0A`** (`[00005307]` is the patched
   displacement of `00005305 mov al,[eax+0x4C0A]`). Loud is a clipping high-gain curve, Soft a ~linear one.
7. The PIT ISR `00001D20` calls `[0002C48C]` once per tick (`00001D2C`); the PIT divisor is `0x47B4`
   (`00001CEB`) = 65.0 Hz, so the music engine tick (`0002BBF2`) is 65 Hz.

#### 5.1 Mixer-layer startup, music device, attract cycle (`00004E89`-`00005B35`)

| # | site | target | enclosing routine / situation | exact arguments | guard | plain event |
|---|---|---|---|---|---|---|
| 1 | `00004E89` | FM (jmp) | inside FX `00004E8E` (`00004E87 mov eax,ebp / jmp`) | `eax=ebp` -> `ax=1..7`, `ah=0` = FM cmd 0, `al`=effect id | `cmp byte [0x19DF9],0` (`00004E8E`) equal 0 | any FX call on a machine without digital sound plays the same id through the FM/OPL effect table at `0002D408+8*id` |
| 2 | `000050A3` | RESET | inside MODE `00004FE4` | none | only after the `al<=4` test (`00005079`) | every successful mixer (re)start first clears the three slots to `0x40E2` |
| 3 | `00005596` | DET | startup (`000054F7` entry via `jmp` at `00001886`) | `al=[0x53D9]&0xF` (`0000558A-0000558F`), also stored in `[0x19DF9]` (`00005591`) | after `COMANCHE.CFG` read | SB detect from CFG byte 1 |
| 4 | `0000559F` | MODE | startup | `al=0xFF` (DET success value), see 0.4 | `or al,al` nonzero (`0000559B`) | only prepares the buffers, mixer stays off; if DET==0, `[19DF9]=0` (`000055A6`) and MODE is skipped |
| 5 | `000055AF` | RATE | startup | `al=2` (`000055AD`) -> `[0x4194]=0x1F` | always | picks the mixer dither mask |
| 6 | `000055C6` | FM | startup | `al=[0x53DA]&0xF`, `ah=0x80` (cmd 8 detect device) after `[0x19DF0]=0x5000` (`000055B4`) | always | probe the music device named in CFG byte 2 |
| 7 | `000055D8` | FM | startup | `al=[0x53DA]&0xF`, `ah=0x30` (cmd 3 select device) | only if the detect returned `al!=0` (`000055CB`) | install the music device driver |
| 8 | `00005692` | MODE | attract state machine `00005690-00005AE3`, label `00005690` | `al=0` (`xor al,al` at `00005690`) | entered from `00018C98` (demo end while attract), `000287B2` (mission end while attract), `00028ED1` (menu item 4 "restart the cycle") and by fall-through from startup `0000568B` | mixer off at the start of every attract pass |
| 9 | `000056C4` | MSTOP | same | none | always | stop whatever music is left |
| 10 | `000056DE` | FM | same | `ax=[0x19DF0]` (`000056D8`) = `0x5000` or `0x4000` | always | re-assert the music enable state: `0x5000` resume (Music Loud/Soft), `0x4000` pause (Music Off); `[2C494]` is zeroed first (`000056C9`) |
| 11 | `00005771` | MSTART | attract, even pass (`[19ED5]` after `inc/and 3` even, `000056E3-000056F3`): RH66SIDE.DTA + ZOVE.RLE side view | `al=2` (`0000576A`, loop), `ebx=0x2DB10` = buffer of **MENUMUS2.MS3** loaded raw at `000056F9-00005703` | after `000267F3` (`00005765`) | looping menu theme under the 300-frame ZOVE side view (`ecx=0x12C`, `00005795`); this pass does not poll the song |
| 12 | `00005851` | MSTART | attract, odd pass (back.dta screen) | `al=0` (`00005849`, play once, no loop), `ebx=[0x19E8C]` = FANFARE.RLE (stored at `00005805`) | directly followed by `000267F3` (`00005856`, applies mixer/music settings) | fanfare, once |
| 13 | `0000587D` | FM | same, wait loop `00005860-00005886` | `ax=0x6000` (`00005879`) = cmd 6 query, returns `al=[0x2C49E]` | each iteration after `[0x1B70]==0` (no key); `ecx` counts `0x1E0`=480 frames (`0000585B`) | loop until the fanfare ends (`al==0`) or 480 retrace frames pass; then `[0x19ED4]=1` (`00005888`) |
| 14 | `00005891` | MODE | same, after the loop | `al=0` (`0000588F`) | falls out of the loop (song ended or 480 frames) | mixer off before the title screen |
| 15 | `00005896` | MSTOP | same | none | same | stop the fanfare (it is a one-shot, may be cut at 480 frames) |
| 16 | `00005963` | VOICE | attract title screen (TPIC.DTA + COMA.RLE pan), after `snd1.rle` -> `[0x19E98]` (`000058D4`) | `eax=[SND1+0xC]+SND1` = **SND1 id 3** (`00005958-00005961`), `bl=2`, `dl=1`, `ecx=0` (`00005952-00005956`) | after `000267F3` (`0000594D`) | helicopter rotor loop at half amplitude under the title (slot 2, restaged forever because staged==current) |
| 17 | `0000596F` | MSTART | same | `al=0` (`00005968`), `ebx=0x2DB10` = **OPENMUS.MS3** loaded raw at `000058AA-000058B4` | always on this screen | opening music, once |
| 18 | `00005ACC` | FM | title loop `000059ED-00005AD6` | `ax=0x6000` (`00005AC8`) | each iteration when `[0x1B70]==0`; `ecx` starts `0x258`=600 (`00005974`) | loop ends when the opening music finishes (`al==0`, falls to `00005ADC [19ED4]=1`) or 600 frames |
| 19 | `00005AE9` | FM | label `00005AE3`: common exit of attract/menu transitions (e.g. xrefs `000057DA,000057E9,00005873,00005AC6,00006A31,0000648F,00018CB7,000287BF,00028AB0`) | `ax=[0x19DF0]` (`00005AE3`) | always at that label | restore pause/resume per the Music setting |
| 20 | `00005AF0` | MODE | same | `al=0` (`00005AEE`) | always | mixer off for the menu |
| 21 | `00005B24` | RESET | same, after the object table clear `000227A6` (`00005B1F`) | none | always | clear mixer slots |
| 22 | `00005B35` | MODE | same, after `call 00028C3E` (menu system, `00005B2E`) returns (i.e. when a mission is started from the menu) | `al=0` (`00005B33`) | executed on return from the menu | mixer off before the mission loader runs |

#### 5.2 Mission start, flight loop, exit (`00006xxx`)

The mission-load code runs through `00006494` (entered by `jmp` from `000063FB`), loads the sound banks, then
`000069CC` renders the first frame, `000069DB` re-applies the sound settings and `000069E0` stages the rotor.

| # | site | target | enclosing routine / situation | exact arguments | guard | plain event |
|---|---|---|---|---|---|---|
| 23 | `000069EA` | MSTOP | mission start, after the first frame | none | always | stop menu/attract music |
| 24 | `00006A00` | MSTART | mission start | `al=2` (`000069F8`, loop), `ebx=[0x19E8C]` (`000069FA`) = the mission file's music (`THEME` slot -> MUSDAY / MUSNIGHT / MUSVOLC .RLE, loaded at `000067F3-00006806`) | **`cmp byte [0x53DA],0x31` not equal** (`000069EF`): CFG music device `'1'` skips it | mission music, looped; unconditional in attract demos too |
| 25 | `00006A0E` | SFXA | mission start (after `[0x19D91]=1`, `00006A05`) | `al=6` (`00006A0C`) | always (SFXA returns at once if `[19E9C]==0`) | SPEAK1 id 6, the mission-start voice |
| 26 | `00006A99` | SFXA | per-frame flight loop `00006A13-00006B0F`, damage announcer `00006A68-00006A9F` | `al=[0x19E27+ecx]` (`00006A92`), `ecx=6..1`, id table (image bytes `19E28..19E2D`) = `08 04 0D 0F 0D 0E` | `([0x19DE8] & 0x1F)==0` (every 32nd frame, `00006A68`), flag `[0x19E2F+ecx]==0` (`00006A79`) and cell `[0x19E37+ecx]` negative (`00006A82-00006A89`); sets the flag first (`00006A8B`) | one spoken "system failed" warning per damaged subsystem per mission |
| 27 | `00006B2A` | MODE | `00006B27` shutdown routine (called from `00006B14` and from 9 error exits per the listing: `000164E3, 0002529F, 000252D1, 0002531E, 00025352, 00025387, 000253B9, 00025800, 00029359`; `00006B14` is entered by `jns` at `000189FF` Alt-Q, `00026E11` options "Exit to DOS", `00028DAB` menu exit) | `al=0` (`00006B28`) | `cli` first | exit to DOS: mixer off |
| 28 | `00006B2F` | MSTOP | same | none | same | music off |
| 29 | `00006B38` | FM | same | `ax=0x3000` (`00006B34`) = cmd 3 select device 0 | same | releases the music device (`0002B9F7` shutdown path, `0002BA29` leaves tick = `ret`) |
| 30 | `00007857` | SFXB | cockpit overlay `000077A0-0000785C` (called at `0000D646` from the flight overlay of the frame driver) | `al=2` (`00007855`) | `[0x19D93]` (a hostile object, aux byte `[21DB3+n]!=0`, projects inside the centre window `|x|<0x14,|y|<0x0F`, `000077E8-00007819`) is now 1 **and** was 0 last frame (`[0x19D95]`, `00007843-00007853`) | SPEAK0 id 2 when a threat first enters the sight window |

#### 5.3 Rotor loop, player flight handler, damage (`0001899A`, `00018Fxx`, `0001942x`)

| # | site | target | enclosing routine / situation | exact arguments | guard | plain event |
|---|---|---|---|---|---|---|
| 31 | `000189B2` | VOICE (jne tail-jump) | rotor loop switch `0001899A-000189BD`, called from `000069E0` (mission start), `00018E44` (fuel out, below), `0001999D` (after the in-flight options menu) | `eax=[SND1+0xC]+SND1` = **SND1 id 3** (`000189A0-000189A9`), `bl=2`, `dl=2`, `ecx=0` (`0001899A-0001899E`) | `[0x19D82]!=0` (collective/throttle byte, `000189AB-000189B2`) | rotor sample staged (and looping) on slot 2 at 1/4 amplitude |
| 32 | `000189BD` | VOICE (jmp) | same | `eax=0x40E2` (`000189B8`), `bl=2`, `dl=2`, `ecx=0` | `[0x19D82]==0` | rotor silenced (silence record staged; takes effect at the next loop boundary) |
| 33 | `00018F79` | SFXA | player flight handler, crashing branch `00018F45-00018F7E` | `al=0x0B` (`00018F77`) | `[0x19E49]!=0` death cue (`00018EE3`), hull `[0x19E40]` negative (`00018F17`), cockpit view `[0x19D86]==1` and `[0x19DC4]+=0x52` per frame has reached `0x0E6A` (`00018F5F-00018F70`); one-shot because `00019820` changes the view | SPEAK1 id 11 at the moment the dying helicopter's view switches to the chase camera |
| 34 | `00019488` | SFXA | crash response `00019424-000194DB` (entered `jmp 00019424` from the object-proximity test `000192EE-0001934A` or the terrain test `00019354-0001937E`) | `al=([0x19DB8]&3)+2` (`0001947B-00019486`), i.e. 2 or 3 | `[0x19E49]==0` (`00019442`) **and** `([0x19DB8]&3)<2` (`00019484 jae` skips both the `add` and the call) | random crash scream/impact voice, SPEAK1 id 2 or 3, half of all crashes |
| 35 | `000194DB` | FX | same | `ebp=5` (`000194D6`), `bl=0xFF`, `dl=0`, `ecx=0` (`000194D0-000194D4`) | same block (every crash event not already dead); after `[0x19E40] -= ([0x19DB8]&3)` (`000194BE-000194C1`) and `[0x19E49]=1` if hull went negative (`000194C7-000194C9`); `000194D0` is reached either way | SND1 id 5, crash/hit thump at full volume |

#### 5.4 Weapon fire and impacts (`00022xxx-00024Axx`; weapon page `[0x19D88]`, table `[0x19D68+4*page]` = `22890,22B00,22F90,22E70,231B2,230B0`)

| # | site | target | enclosing routine / situation | exact arguments | guard | plain event |
|---|---|---|---|---|---|---|
| 36 | `00022876` | FX | `000227BF` transient/explosion spawn (BOOM wreckage at parent `ecx`), xrefs `00018F8F,00023A81,00023AA6,00023CC3,00023F34,000241B4,000243F4` | `ebp=1` (`00022871`), `bl=0xFF`, `dl=al` (`0002286D`), `ecx=0`; `dl=((max(|dx|,|dy|)+min(|dx|,|dy|)/2)>>29)` of the parent vs viewer `[19CD4],[19CD8]` (`00022839-00022862`) | `dl<=4` (`00022865-00022868`), else silent | SND1 id 1 explosion, quieter with distance (class 0..4 = 0..640 map units) |
| 37 | `000228FD` | FX | weapon page 0 gun fire `00022890-00022963` | `ebp=7` (`000228F8`), `bl=0xFE` (`000228F2`), `dl=0`, `ecx=0` | `[0x19D2C]` ammo nonzero and gun cell `[0x19E3D]` not negative (`00022890-000228A0`), a free object slot (`000228AC`); after `[0x19D2C]-=2` | cannon burst, SND1 id 7 |
| 38 | `00022B6C` | FX | weapon page 1 rocket launcher `00022B00-00022BD0` (ROCK bank `[0x19E7C]`, state `000241C0`) | `ebp=4` (`00022B67`), `bl=0xFF`, `dl=0`, **`ecx=0x20000`** (`00022B62`, double pitch) | `[0x19D30]!=0`, cell `[0x19E3B]` not negative (`00022B07-00022B10`), free slot | rocket launch, SND1 id 4 at 2x pitch |
| 39 | `00022EB9` | FX | weapon page 3 Stinger from `00022E70` (STGR `[0x19E84]`, guided state `00024860`) | `ebp=4` (`00022EB4`), `bl=0xFF`, `dl=0`, `ecx=0` | `[0x19D38]!=0`, free slot | Stinger launch, SND1 id 4 native pitch |
| 40 | `00022FD9` | FX | weapon page 2 Hellfire from `00022F90` (HELL `[0x19E80]`, state `00024680`) | `ebp=4` (`00022FD4`), `bl=0xFF`, `dl=0`, `ecx=0` | `[0x19D34]!=0`, free slot | Hellfire launch, SND1 id 4 |
| 41 | `00023123` | FX | weapon page 5 wingman Hellfire `000230B0-000231B1` | `ebp=4` (`0002311E`), `bl=0xFF`, **`dl=1`** (`0002311A`), `ecx=0` | `[0x19D40]!=0`, `[0x22368]` (wingman) nonzero and active (`000230EF-00023100`) | wingman-fired Hellfire at half volume |
| 42 | `000231FD` | SFXB | weapon page 4 timed blast launcher from `000231B2` (state `00024310`) | `al=1` (`000231FB`) | `[0x19D3C]!=0` and target latch `[0x19D10]!=0` (`000231B2-000231C2`), free slot | SPEAK0 id 1 when the blast charge is placed |
| 43 | `0002360C` | FX | shell hit on the player, tail `000235CB-0002365B` shared by the three tank shell states | `ebp=5` (`00023607`), `bl=0xFF`, `dl=0`, `ecx=0` | shell within `0x1400000` (5 map units) and altitude `0x0F` of the viewer (`0002357B-000235C5`); not spared by flares (`[0x19DB8]&0xC` && `[0x19D90]`, `000235CB-000235E4`); `[0x19E49]==0` (`000235E6`) | player hit, SND1 id 5 |
| 44 | `00024469` | FX | timed-blast state `00024310`, blast tail `000243FE-0002446F` | `ebp=5` (`00024464`), `bl=0xFF`, `dl=0` | tick >= `0x78` and the viewer inside `0x32` altitude / `0xC800000` (50 map units) (`00024404-00024440`); sets hull -1 and `[0x19E49]=1` first | player killed by the blast, SND1 id 5 |
| 45 | `0002432B` | SFXA (jmp) | timed-blast state `00024310-00024329` | `al=9` (`00024329`) | object timer `[ecx+0x21E35]==0x46` (`00024320`) | SPEAK1 id 9 at tick 70 of the blast (countdown cue) |
| 46 | `0002433B` | FX (jmp) | same, `00024330-0002433B` | `ebp=2` (`00024336`), `bl=0xFF`, `dl=0`, `ecx=0` | timer `==0x64` (`0002431E`) | SND1 id 2 at tick 100 |
| 47 | `0002434C` | FX | same, `00024340-00024351` | `ebp=6` (`00024347`), `bl=0xFF`, `dl=0`, `ecx=0` | timer `>=0x78` (`00024326`) | SND1 id 6 detonation at tick 120, object becomes wreckage `000237B0` |
| 48 | `00024A2C` | FX | `00024997-00024A32` shared "becomes BOOM wreckage" tail (jumped to from the shell/missile/unit states, 22 xrefs) | `ebp=1` (`00024A27`), `bl=0xFF`, `dl=al` (`00024A23`, same distance class formula, `00024A00-00024A18`), `ecx=0` | class `<=4` (`00024A1B`) | SND1 id 1 explosion for any projectile or object that turns into wreckage |

#### 5.5 Speech cues in object state machines

| # | site | target | enclosing routine / situation | exact arguments | guard | plain event |
|---|---|---|---|---|---|---|
| 49 | `000237F8` | SFXA | wreckage state `000237B0` (a destroyed mission object finishing its 0x14 frames) | `al=7` (`000237F6`) | object slot `<=0x1E` (`000237C6`), goal flag `[ecx+0x21F39]!=0`, goals-left `[0x2824B]` decremented (`000237DE`) **reaches 0**, `[0x19E49]==0`; sets `[0x19E49]=1` (`000237EF`) | last mission goal destroyed: SPEAK1 id 7 (and the mission-complete cue starts the end countdown) |
| 50 | `00023940` | SFXA | wingman (type 4) state `00023840-00023A07`, `00023927-00023945` | `al=0x0C` (`0002393E`) | wingman heading-settle timer `[ecx+0x21E35]` (re-armed to 0x0F at `0002390A/0002391E`) decremented to 0 (`00023927`) and player latch `[0x19D10]==[0x22368]` (the wingman itself, `0002392F-0002393C`) | wingman acknowledgement, SPEAK1 id 12 |
| 51 | `00023956` | SFXA | same | `al=0x0A` (`00023954`) | same timer expiry, latch is some other slot (`or bl,bl`) and weapon page `[0x19D88]==5` (`0002394B`) | wingman attack-order acknowledgement, SPEAK1 id 10 |
| 52 | `00023A20` | SFXA | wingman destruction `00023A08-00023A86`, first stage | `al=5` (`00023A1E`) | `[ecx+0x21B29]==1` (`00023A08-00023A0F`), then `[0x19D40]=0` | wingman lost, SPEAK1 id 5 |
| 53 | `00023AAD` | SFXA | oil tank (type 3, state `00023A8C`) destruction stage 1 | `al=1` (`00023AAB`), after `call 000227BF` (SND1 #1 boom) | `[ecx+0x21B29]` goes 0->1 (`00023A96-00023A9F`) | SPEAK1 id 1 |
| 54 | `00023CCA` | SFXA | dispatch type 9 state `00023B50-00023CE4`, destruction stage 1 | `al=1` (`00023CC8`), after `000227BF` | `[ecx+0x21B29]<=1` and incremented (`00023CB3-00023CBC`) | SPEAK1 id 1 |
| 55 | `00023F3B` | SFXA | mobile ground unit state `00023CF0-00023F55` (types 2 and 5), destruction stage 1 | `al=1` (`00023F39`), after `000227BF` | `[ecx+0x21B29]<=1` (`00023F24-00023F2D`) | SPEAK1 id 1 |
| 56 | `0002415D` | SFXA | allocator default state `00023F60`, falling wreck `0002414C` (types 1, 6, 7, 8) | `al=1` (`0002415B`) | `[ecx+0x21B29]==1` (`0002414C-00024153`), then incremented | SPEAK1 id 1 |

#### 5.6 Options menu / settings (`00025Dxx`, `000262xx`, `000267F3`, `00026Cxx`, `00026Dxx`)

| # | site | target | enclosing routine / situation | exact arguments | guard | plain event |
|---|---|---|---|---|---|---|
| 57 | `00025DFD` | VOICE | options-menu entry `00025DEF-00025E06`, called from `00019998` (key code 1 = Esc in flight, handler `00019988-000199A2`; `0001999D` then re-evaluates the rotor) and `00027F61` (main menu bar item 1) | `eax=0x40E2`, `bl=2`, `dl=0`, `ecx=0` (`00025DEF-00025DF8`) | always | silences slot 2 (rotor loop / speech slot) while the menu is open |
| 58 | `00025E06` | FM | same | `ax=0x4000` (`00025E02`), cmd 4 = pause (sets mute flag `[0x2C49F]=0xFF`, `0002BBC1-0002BBCD`) | always (not saved to `[19DF0]`) | music (and FM effects) muted while the menu is open |
| 59 | `00026283` | FM | menu exit block `0002617A-0002628D` (after Esc at `0002615C`; also applies detail level `00026211-00026278`) | `ax=[0x19DF0]` (`0002627D`) | always | resume iff Music is not Off |
| 60 | `0002680D` | FM | **`000267F3` "apply sound settings"** (called from `0000568B, 00005765, 00005856, 0000594D, 000069DB`) | `ax=0x5000` (`00026803`), `[0x19DF0]=ax`, `[0x2C5A8]=0xFA` (`000267FC`) | `[0x25DD6]=='0'` (Music Loud) | music resume at level 0xFA |
| 61 | `00026829` | FM | same | `ax=0x5000`, `[0x2C5A8]=0x64` (`00026818`) | `[0x25DD6]=='1'` (Music Soft) | music resume at level 0x64 |
| 62 | `0002683E` | FM | same | `ax=0x4000` (`00026834`), `[0x19DF0]=ax` | `[0x25DD6]=='2'` (Music Off) | music pause |
| 63 | `00026851` | MODE | same | `al=[0x19DF9]` (`0002684C`) | `[0x25DD5]=='0'` (Sound Loud); table stays `0x4C0A` (MODE reset `[5307]`) | digital mixer on, loud curve |
| 64 | `00026861` | MODE | same | `al=[0x19DF9]` (`0002685C`), then `[0x5307]=0x4A0A` (`00026866-0002686B`) | `[0x25DD5]=='1'` (Sound Soft) | mixer on, soft curve |
| 65 | `00026878` | MODE | same | `al=0` (`00026876`) | `[0x25DD5]=='2'` (Sound Off) | mixer off |
| 66 | `00026CF3` | MODE | radio handler `00026CC2-00026D8A` (selector `0x20` = Sound Loud) | `al=[0x19DF9]` (`00026CEE`), `[0x25DD5]='0'` (`00026CE7`) | menu selector `0x20` | live switch to Loud |
| 67 | `00026D09` | MODE | same (`0x21` = Sound Soft) | `al=[0x19DF9]` (`00026D04`), `[0x25DD5]='1'`, then `[0x5307]=0x4A0A` (`00026D0E-00026D13`) | selector `0x21` | live switch to Soft |
| 68 | `00026D26` | MODE | same (`0x22` = Sound Off) | `al=0` (`00026D24`), `[0x25DD5]='2'` | selector `0x22` | live switch to Off |
| 69 | `00026D48` | FM | same (`0x24` = Music Loud) | `ax=0x5000`, `[0x19DF0]=ax`, `[0x2C5A8]=0xFA` (`00026D37`), `[0x25DD6]='0'` | selector `0x24` | live Loud |
| 70 | `00026D6A` | FM | same (`0x25` = Music Soft) | `ax=0x5000`, `[0x19DF0]=ax`, **`[0x2C5A8]=0x73`** (`00026D59`), `[0x25DD6]='1'` | selector `0x25` | live Soft (level differs from row 61, see Unproven) |
| 71 | `00026D85` | FM | same (`0x26` = Music Off) | `ax=0x4000`, `[0x19DF0]=ax`, `[0x25DD6]='2'` | selector `0x26` | live Off (pause) |

#### 5.7 Mission end, debrief, menu music (`000287xx`, `00028Axx`, `00028Cxx`)

| # | site | target | enclosing routine / situation | exact arguments | guard | plain event |
|---|---|---|---|---|---|---|
| 72 | `00028743` | FM | `0002873D` mission-end chain (entered from `000189F2` Alt-A abort, `00018E23` fuel `[0x19D60]==-0x10E`, `00018EF6` wreck countdown done, `00026E09` options "Abort Mission") | `ax=[0x19DF0]` (`0002873D`) | always | restore music state |
| 73 | `0002876D` | MODE | same | `al=0` (`0002876B`) | always | mixer off |
| 74 | `00028777` | RESET | same, after `00028772` statistics | none | always | clear slots |
| 75 | `00028781` | MSTOP | same, after `000227A6` | none; `[0x2C494]=0` follows (`00028786`) | always | stop mission music |
| 76 | `00028A23` | MSTART | debrief entry `00028A1F` (reached from the **won** path `000288ED-000289F0` or the **not-won** path `0002887B-000288E8`) | `al=2` (loop, `00028A21`), `ebx=eax` = return of `LOADALLOC` for the `theme.rle` placeholder (`000289FA-00028A0C` won: mission-file slot 8 = MUSWIN.RLE; `000288C3-000288D5` not won: slot 10 = MUSLOSE.RLE) | won = hull standing and `[0x2824E]` (all goals destroyed) (`000287CC-000287DC`), otherwise lose music | win or lose theme, looped, over the debrief screen |
| 77 | `00028CD7` | MSTART | menu music `00028C3E` (skipped when `[0x19ED4]==1`, i.e. attract, `00028C3E-00028C45`) | `al=0` (`00028CD0`), `ebx=0x2DB10` = **MENUMUS1.MS3** (51 bytes) loaded raw at `00028CA2-00028CAC` | `[0x19ED4]!=1` | menu intro, once |
| 78 | `00028CE3` | MSTART | same | `al=3` (bit0 queue behind the song now playing, bit1 loop), `ebx=0x2DF10` = **MENUMUS2.MS3** loaded raw at `00028CB9-00028CC3` | same | looping menu theme queued behind MENUMUS1 |

#### 5.8 Inside the music driver itself

| # | site | target | enclosing routine | exact arguments | guard | event |
|---|---|---|---|---|---|---|
| 79 | `0002BAA4` | MSTOP | device init `0002BA36-0002BAFE` (cmd 3 with `al` 1..5) | none | device init function `[0x2C649]` returned nonzero (`0002BA9A-0002BAA2`) | clean state, then `[0x2C5A8]=0xFF`, `[0x2C494]=0`, `[0x2C48C]=0x2BBF2` (tick installed) |
| 80 | `0002BD5F` | MSTOP | MSTART `0002BD00` (play-now branch) | none | `ebx!=0`, not queued | stop old song before the new one (`[0x2C49E]=0xFF` follows, `0002BD6D`) |

(`000020D5`: the SB IRQ ISR calls the filler `00005220`; `00001D2C` calls the music tick through
`[0x2C48C]`. Neither is a call into one of the 11 targets, listed for completeness.)

### 5.9 Where the music buffers come from

Loader facts: `00015E6E` (inline filename, loads and unpacks into a **fresh bump allocation** `00025777`, returns
`eax` = allocation start, CF=0) reads the 8-byte header with `int 21h/3Fh cx=8` (`00015EC2`), dispatches on
`'KRL1'` (`00015ED6`, decompress `0001644B`) or `'KRL0'` (`00015F0B`, stored: `00015F36-00015F62` copies the file
bytes after the header), the dword at +4 is the **decompressed length** (`00015EDD mov edx,[esi]`). The returned
pointer is the allocation start (**not** `+1`; the `inc eax` seen at `00015F28` in the listing is the second byte of
the `je` at `00015F27`). The buffer therefore starts at file offset 8, i.e. `4D 53 33 2D 4B 47 46 27 39 31 20 0A 0D 1A`
= `'MS3-KGF'91 \n\r\x1A'` (verified on MUSDAY, MUSNIGHT, MUSVOLC, MUSWIN, MUSLOSE, WINMUS, BIGWIN, FANFARE after RLE
decoding). `00015DD0` loads a file raw to `[eax]` (no header; 0xFA00-byte reads), size left in `[00015DC8]`. In both
cases **`ebx` passed to MSTART points at the `'M'` of `MS3-KGF`**; MSTART itself reads `ebx+0x10..0x19` (10 bytes),
`ebx+0x20..0x29` (10 bytes) and starts the event stream at `ebx+0x30` (`0002BD28-0002BD59`).

| file | loaded at | pointer variable / address | passed to MSTART at | flags |
|---|---|---|---|---|
| MENUMUS2.MS3 | `000056F9-00005703` raw to `0x2DB10` (even attract pass) | fixed buffer `0x2DB10` | `00005771` | `al=2` loop |
| FANFARE.RLE (KRL0, 519 bytes) | `000057EE-000057FF` `LOADALLOC` (odd pass) | `[0x19E8C]` (`00005805`) | `00005851` | `al=0` once |
| OPENMUS.MS3 (754 bytes) | `000058AA-000058B4` raw to `0x2DB10` | `0x2DB10` | `0000596F` | `al=0` once |
| THEME slot = MUSDAY / MUSNIGHT / MUSVOLC.RLE | `000067EE-00006806` `LOADALLOC` of the placeholder `'theme.rle   '` (mission-file slot 6) | `[0x19E8C]` (`00006806`) | `00006A00` | `al=2` loop, skipped if `[0x53DA]=='1'` |
| MUSWIN.RLE (mission-file slot 8) | `000289FA-00028A0C` `LOADALLOC` of the placeholder `'theme.rle   '` at `0x28A0C` (won path) | local `eax`->`ebx` (not stored) | `00028A23` | `al=2` loop |
| MUSLOSE.RLE (slot 10) | `000288C3-000288D5` placeholder at `0x288D5` (not-won path) | local `eax`->`ebx` | `00028A23` | `al=2` loop |
| MENUMUS1.MS3 (51 bytes) | `00028CA2-00028CAC` raw to `0x2DB10` | `0x2DB10` | `00028CD7` | `al=0` |
| MENUMUS2.MS3 (1203 bytes) | `00028CB9-00028CC3` raw to `0x2DF10` | `0x2DF10` | `00028CE3` | `al=3` queue + loop |

What selects day / night / volcano: **only the mission file**. `0002913C-00029178` copies the 21 filenames of the
`<`...`<` list of the mission into the inline placeholders listed at `0002A320`; slot 6 (7th name, ptr `0x67F3`) is the
mission music, slot 8 (`0x28A0C`) the win music, slot 10 (`0x288D5`) the lose music. Shipped files (decoded with the
`03 06 12 11` XOR): `0.MIS` = `musday.rle / muswin.rle / muslose.rle`; `1.MIS` = `musnight.rle / muswin.rle /
muslose.rle`. `MUSVOLC.RLE`, `WINMUS.RLE`, `BIGWIN.RLE` exist as files but no string for them exists in the executable
and none of the two shipped missions names them (see Unproven). The mission music pointer `[0x19E8C]` is reloaded
at every mission start (`00006806`), the attract writes the same variable with FANFARE (`00005805`).

Note: `0x2DB10` is also the demo record/playback buffer (`00018C43`, `000199BF`), so the music buffer is clobbered
whenever a demo is recorded; the music data is only read while the song plays.

## 6. Sound variables of the game

| variable | meaning | writers | readers |
|---|---|---|---|
| `[19DF9]` | digital-effect mode, 0 = none | `00005591` (`CFG[1]&0xF`), `000055A6` (=0 if DET returned 0) | `00004E8E` (route), `0002684C,0002685C,00026CEE,00026D04` (MODE arg) |
| `[19E8C]` | pointer to the current "theme" song (MS3 data) | `00005805` (FANFARE.RLE, attract), `00006806` (mission THEME slot) | `0000584B` (fanfare), `000069FA` (mission) |
| `[19E90]` | **sprite bank** (not audio): ZOVE.RLE / COMA.RLE / CONS.RLE | `0000575B`, `00005920`, `000067C6`, `00028E51` | `00025880,0002590F,0002599E` (sprite blitters) |
| `[19E94]` | **sprite bank** HUDS.RLE (not audio) | `000067E4` | `00025A4D,00025B27,00025BB6` |
| `[19E98]` | SND1.RLE bank (`K1`, 7 samples) | `000058D4` (title), `000064A8` (mission load, `snd1.rle`) | `00004E97` (FX), `00005958` (title rotor), `000189A0` (flight rotor) |
| `[19E9C]` | SPEAK1.RLE bank (15 samples) | `00006859` (mission load) | `00004E2E` (SFXA) |
| `[19EA0]` | SPEAK0.RLE bank (2 samples) | `0000681D` (mission load) | `00004E26` (SFXB) |
| `[19DF0]` | last "music enable" command word: `0x5000` resume / `0x4000` pause | `000055B4` (init `0x5000`), `00026807,00026823,00026838` (apply), `00026D42,00026D64,00026D7F` (radios) | `000056D8`, `00005AE3`, `0002627D`, `0002873D` (all as `ax` to FM) |

Neither `[19E9C]` nor `[19EA0]` is ever cleared; they hold the first mission's banks. `[19E98]` has no null test in
FX; it is non-zero whenever FX is reachable (flight or title).

## 7. What the music tick does to the game's timing, and what the game waits for

* **Only two places query the song**: `0000587D` (fanfare screen, attract odd pass) and `00005ACC` (title screen).
  Both are frame loops paced by `00015B78` (waits for the VGA vertical retrace, port `0x3DA` bit 3, `00015B81-00015B84`)
  with input poll `000189C2`:
  * fanfare: up to `0x1E0`=480 frames (`0000585B`); ends early when `FM(0x6000)` returns 0; either exit sets
    `[0x19ED4]=1` (attract flag, `00005888`); a key (`[0x1B70]!=0`, `0000586C`) goes to `00005AE3` with the flag still 0
    (real menu).
  * title: up to `0x258`=600 frames (`00005974`); ends early when the opening song finishes; same flag/exit rules
    (`00005ABF-00005AD6`).
  * The even-pass ZOVE screen (`00005795`, 300 frames) and the mission demos do not poll the song.
* The song query result is `[0x2C49E]`: set to `0xFF` by MSTART (`0002BD6D`), cleared only by the driver's tick when the
  event stream hits `0x2FFF` (`0002BD80-0002BD88`, `0002BE0F-0002BE1D`) or by MSTOP. The tick is `[0x2C48C]`, driven
  by the 65 Hz PIT ISR. **If no music device is installed** (cmd 8 failed at `000055CB`, so cmd 3 never ran,
  `[0x2C48C]` stays `0x2B9F6 = ret`), the song never ends and both screens run their full 480/600 frames; with a
  working device, **and with device 5 "none"** (hooks are `ret` but the tick `0002BBF2/0002BE68` still advances the song
  clock) the screen length equals the song length in 65 Hz ticks, bounded by 480/600 frames. With `MENUMUS1` queueing
  `MENUMUS2` (row 78) the queue only advances when the tick runs.
* All other branches on sound state are about configuration, not playback: `00004E8E` on `[19DF9]`; `000055CB`
  on the detect result; `000069EF` on CFG music device `'1'`; `0000559B` on DET; `00004E34/00004E45` (bank absent,
  speech slot busy); the radios on `[25DD5]/[25DD6]` (`00026843-00026878`, `000267F3-0002683E`).
* **No gameplay logic (flight, AI, mission end, scoring) depends on sound completion.** The flight loop `00006A13` is
  paced by `00015B78` and the replay records, not by the mixer or the music. SND/speech calls are fire-and-forget
  (they only skip if busy), the debrief music (`00028A23`) is looped and never polled.
* UI timing that does depend on the sound subsystem state: (i) the fanfare/title durations above; (ii) the Esc options
  menu: entry mutes music (`00025E06`) and silences slot 2 (`00025DFD`), exit resumes per `[19DF0]` (`00026283`) and
  re-stages the rotor via `0001899A` (`0001999D`).

## 8. The silent boundary, restated for this driver

* The music driver and the mixer can be absent: nothing in flight, AI, mission end or scoring reads their state.
* Two UI loops read the song: `0000587D` (the fanfare screen, up to 480 frames) and `00005ACC` (the title
  screen, up to 600 frames) poll command `0x6000` and end early when it returns 0. With a working device the
  screen lasts as long as the song (OPENMUS = 741 ticks = 11.4 s, FANFARE = 278 ticks = 4.3 s) or the frame
  budget; with no device ("silent") the song never ends and both loops run their full length. A silent
  implementation must therefore answer the query with a fixed, documented value; which one is a
  decision about the title and fanfare durations, not about sound.
* `COMANCHE.CFG` byte 2 = `1` (speaker) suppresses mission music (`000069EF`).
* Hardware detection results gate the digital path (`[00019DF9]`) and the music device; both default to "absent" on
  a machine without the card.

## 9. The oracle probe and what the captures prove

`work/trace_sound_writes.py` (record `sound-driver-module`) stops the original, running on genuine MS-DOS 6.22
under QEMU on a snapshot of the disk image, at the instructions that produce the stream:

| address | what | taken |
|---|---|---|
| `0002C1B8` | OPL write helper: `ah` register, `al` value | before it runs |
| `0002C20E`, `0002C237` | the OPL detection's two status reads | after each `in al, dx` (status in `al`) |
| `0002BF88`, `0002BFD9` | MPU data / command byte (`--mpu`) | before; the routine is skipped and `0002BFD9` returns `FE` |
| `0002C436`, `0002C440`, `0002C455`, `0002C45C`, `0002C469`, `0002C475`, `0002C47B` | PC speaker `out`s | before |
| `0002C434`, `0002C43E`, `0002C453`, `0002C45A` | the `in al, 0x61`s | after |
| `00005220` | the digital fill | the 0x800 bytes it wrote, read back |

*Detection and the hardware gap.* QEMU has a YM3812 model (`-device adlib`), so the driver's own detection
passes (status `00` then `C0`) and nothing is forced for the OPL. QEMU has no MPU-401 and no PC speaker
behind the driver's ports that matters, and no Sound Blaster is attached (the game's DSP probe fails, so
`[00019DF9]` = 0 and FM effects work); the MPU-401 routines are skipped and answered as described in the
table, the Sound Blaster is not needed because the probe calls the mixer's fill itself.

The fixtures are derived and git-ignored (`build/sound/*.json`, `build/sound-natural/`); `sh work/capture_sound_fixtures.sh` regenerates the direct ones (about half an hour on QEMU, one guest at a time), `NATURAL=400 sh work/capture_sound_fixtures.sh` adds the natural run.

*Two modes.* `direct`: the game is stopped as a demo replay arms (so its stack, timer and tables are alive);
the driver's data region `0002C48C-0002DC00` and the mixer's records are put back to the image's bytes; then
the probe CALLS the driver's entries with chosen inputs, one op at a time, interrupts off, a breakpoint on an unused `nop`
(`0002C48B`) as the return address. A *tick* op is `call [0002C48C]`, exactly what the ISR does. Each op records the
writes it caused, the returned `al` and every byte that changed in the driver's variable windows. The song bytes are
placed above the allocator's top as the loader leaves them. `natural`: the game boots with an AdLib and runs freely;
the gdbstub is connected before the program loads, every entry of the driver and the digital layer, every OPL write and
every ISR entry is logged, with the driver's variables at each entry.

*What the proof tool compares* (`node tools/check-js-sound.js`): for `direct` captures, after every op the writes in
order (for the digital layer the mixed bytes), the returned `al` and the byte-level change of the variable windows;
for the `natural` capture, the whole interleaved write stream of one run of the game, with the original's timer
interrupts replayed at the position in the stream where they arrived (an interrupt can arrive inside a driver call
at any instruction; the JavaScript runs the call with the interrupt before each store after that position until the
driver's variables at the interrupt equal the original's).

| capture | what it does | calls | port writes | mixed bytes | result |
|---|---|---|---|---|---|
| `bigwin` | BIGWIN.RLE, whole (unreferenced; 20 program changes, channel links) | 11724 | 7746 | - | identical |
| `detect-absent` | every device detected with no card in the guest (status 0xFF): AL = 0 for the OPL devices | 10 | 131 | - | identical |
| `device-switch` | devices 4, 3, 1, 4, 2, 5, 3 selected in turn with a song and an effect running: every device's shutdown and init routine | 88 | 987 | - | identical |
| `digital-cannon` | SND1 id 7 with bl = 0xFE (re-trigger), id 5 (player hit) | 17 | 0 | 16384 | identical |
| `digital-explosion` | SND1 id 1 at full volume and at distance class 3, 16 fills each (the sample plays out) | 41 | 0 | 65536 | identical |
| `digital-launch` | SND1 id 4 at double pitch (rocket), native (Hellfire, Stinger), attenuated (wingman) | 31 | 0 | 40960 | identical |
| `digital-mix` | three slots at once, a drop and a steal, speech with slot 2 busy, the soft curve, five dither masks, reset | 37 | 0 | 32768 | identical |
| `digital-rotor` | SND1 id 3 staged on slot 2 with VOICE and looped through the restage, then silenced | 26 | 0 | 34816 | identical |
| `digital-speech` | SPEAK1 id 4 (engine failed) and 6, SPEAK0 id 2 | 31 | 0 | 43008 | identical |
| `effect-over-music` | OPENMUS playing, effects 4 and 5 taking channels from it | 226 | 394 | - | identical |
| `effects-mpu` | FM effects 1, 2, 4, 5, 6, 7 on the MPU-401 | 188 | 623 | - | identical |
| `effects-speaker` | FM effects 1, 2, 4, 5, 6, 7 on the PC speaker | 188 | 334 | - | identical |
| `effects-volume` | effects 0, 4, 5, 24 with volume nibbles 1, 8, 15 | 494 | 682 | - | identical |
| `effects` | FM effects 0..24 one after the other, 40 ticks each | 1027 | 1099 | - | identical |
| `fanfare-mpu` | FANFARE on the MPU-401 (pitch bends from the E events) | 304 | 573 | - | identical |
| `fanfare-speaker` | FANFARE on the PC speaker | 304 | 93 | - | identical |
| `fanfare` | FANFARE.RLE (KRL0), 300 ticks | 304 | 479 | - | identical |
| `menumus1` | MENUMUS1.MS3 (an empty song) looped: every tick ends it and restarts it | 44 | 862 | - | identical |
| `menumus2` | MENUMUS2.MS3, the menu loop, 2100 ticks (one whole pass and the restart) | 2104 | 1408 | - | identical |
| `musday-mpu` | MUSDAY on the MPU-401, 400 ticks | 404 | 906 | - | identical |
| `musday` | MUSDAY.RLE (KRL1), the day mission music, played to the end (10191 ticks) | 10214 | 9874 | - | identical |
| `muslose` | MUSLOSE.RLE, whole | 2264 | 1822 | - | identical |
| `musnight` | MUSNIGHT.RLE, the night music, whole | 3154 | 2095 | - | identical |
| `musvolc` | MUSVOLC.RLE, whole (reached by no code in this install) | 8874 | 11049 | - | identical |
| `muswin` | MUSWIN.RLE, whole | 2904 | 4869 | - | identical |
| `openmus-mpu` | OPENMUS on the MPU-401 (bytes and command bytes) | 764 | 1524 | - | identical |
| `openmus-none` | OPENMUS on device 5 (the empty device): the song runs, nothing is written | 54 | 0 | - | identical |
| `openmus-speaker` | OPENMUS on the PC speaker (port 0x43, 0x42, 0x61 values) | 764 | 157 | - | identical |
| `openmus-volume` | command 7 (volume 0x55) and OPENMUS | 125 | 208 | - | identical |
| `openmus` | OPENMUS.MS3, the title music, 760 ticks (to its end at 741 and past it) | 764 | 999 | - | identical |
| `queue-and-loop` | FANFARE with OPENMUS queued behind it, then MENUMUS2 looped, pause, resume, query, stop | 494 | 652 | - | identical |
| `select-adlib` | detect (command 0x8003) and select (0x3003) on the AdLib: the 118-write init | 2 | 124 | - | identical |
| `select-bad` | device 0 and 6, commands 9 and 15, query, device 3 | 8 | 118 | - | identical |
| `select-sb` | the same on device 2 (Sound Blaster FM) | 2 | 124 | - | identical |
| `synthetic-events` | a song built by the probe: Bn, Dn and unknown (A0) events, a two-byte delay, delays of 0, channels above 9, negative pitch offset, mid-note program change, loop | 524 | 349 | - | identical |
| `synthetic-links` | a song built by the probe: channel links 0 to 1 to 2 with different patches | 64 | 244 | - | identical |
| `winmus` | WINMUS.RLE, whole (unreferenced) | 1324 | 1094 | - | identical |
| `wrap-inc-bx` | OPENMUS placed so that a note velocity byte is at 0x42FFFF: the 16-bit `inc bx` at 0002BDED | 65 | 208 | - | identical |

Total: 38/38 sound captures identical (49956 ops, 51827 writes, 233472 mixed bytes).

*The natural run* (`node tools/check-js-sound.js --natural build/sound-natural/natural-attract.json`): natural run: 17757 ticks, 16381 driver calls (65 songs, 1551 interrupted by a tick, 39 adoptions of the game's own writes), 139775 writes identical. the game was booted with an AdLib in the guest and ran its attract cycle (title, fanfare, menu music, mission demos with weapons fire and explosions, mission music) for 17,757 timer ticks (273 s of game time). The log has 16,381 entries of the driver (65 of them song starts) and 139,775 OPL2 writes. Replayed on the JavaScript driver (every ISR entry a tick, every driver entry that call with the registers it had, the song bytes at the cursor as the original had them) the write stream is identical, write for write, **including 1,551 timer interrupts that arrived inside a driver call**, which the replay puts at the first memory access (or port write) after the recorded stream position where the driver's 437 bytes of variables equal the original's at the ISR's entry. The only inputs adopted from the original are the two the game writes to the driver's variables itself, the music volume `[0002C5A8]` and the current-song pointer `[0002C494]` (adopted at 39 entries), and the bytes of the song buffer, which the game reuses (`0002DB10` is also its demo buffer) while a song still plays from it. The capture stops at its time budget inside the last ISR's writes; those are not compared. Two natural runs were captured (the second after the probe's last change); the game is not deterministic to the tick, and both replay.

*Call sites reached by the game in the natural run.* 49 of the 80 call sites were executed by the game in this run (17757 ISR entries, about 273 s of game time): `000050A3` (158x), `00005596` (1x), `000055AF` (1x), `000055C6` (1x), `000055D8` (1x), `00005692` (26x), `000056C4` (26x), `000056DE` (26x), `00005771` (13x), `00005851` (13x), `0000587D` (6240x), `00005891` (13x), `00005896` (13x), `00005963` (13x), `0000596F` (13x), `00005ACC` (7800x), `00005AE9` (26x), `00005AF0` (26x), `00005B24` (26x), `00005B35` (26x), `000069EA` (26x), `00006A00` (26x), `00006A0E` (26x), `00006A99` (17x), `00007857` (57x), `00018F79` (1x), `00019488` (42x), `000194DB` (170x), `00022876` (188x), `00022B6C` (1114x), `00022EB9` (154x), `00022FD9` (208x), `000231FD` (14x), `0002360C` (46x), `00023940` (3x), `00023956` (3x), `00023A20` (1x), `00023AAD` (18x), `00023F3B` (34x), `0002415D` (22x), `0002434C` (28x), `00024A2C` (2110x), `00026283` (66x), `0002680D` (66x), `00026851` (66x), `00028743` (1x), `0002876D` (1x), `00028777` (1x), `00028781` (1x). Sites not in the table: 000069E0, 000234C5. Two events came in through a routine that tail-jumps into the sound entry, so the return address names the caller of that routine: `000069E0` calls the rotor switch `0001899A` (rows 31 and 32), and `000234C5` is the object update loop's `call eax` at `000234C8` into a state handler that ends in `jmp 00004E8E` or `jmp 00004E2E` (rows 45 and 46).

## 10. What the 68030 side needs

(The Falcon implementation is not written here: this is the contract the JavaScript reference proves.)

| call | meaning |
|---|---|
| `snd_init(cfg)` | startup of `000055B4-000055D8`: `command(0x8000 \| device)` (detect, with the card's status answers); if non-zero `command(0x3000 \| device)` (select: for the OPL device the 118 writes above; the tick vector becomes the music tick). The digital side: probe, buffers, `MODE`, dither mask 2. |
| `snd_tick()` | what the PIT ISR does 65.002 times a second (1,193,182 / 18,356; the host needs a divider or a timer of its own, a 200 Hz timer cannot make it): the music tick. Runs sequencer, effect timers, pitch pass; returns after at most a few dozen OPL writes. |
| `snd_music_start(flags, song)` | `0002BD00`: `flags` bit 0 queue, bit 1 loop; `song` = the MS3 signature address; loaders: `.MS3` raw, `KRL0`/`KRL1` (`decodeMusicFile`). |
| `snd_music_stop()` | `0002BEDC`. |
| `snd_music_playing()` | command 6, `al` = `[0002C49E]`; the title and fanfare loops use it. |
| `snd_music_volume(level)`, `snd_music_pause()`, `snd_music_resume()` | `[0002C5A8]` = 0xFA (Music Loud) or 0x64 / 0x73 (Music Soft: the two options code paths disagree, **Unproven** which a given run has); commands 4 and 5 (`ax` = `[00019DF0]` = 0x4000 / 0x5000). |
| `snd_effect_fm(id)` | command 0 with `al` = id (1..7), used only if there is no digital device. |
| `snd_fx(id, slot, shift, step)`, `snd_speech_a(id)`, `snd_speech_b(id)`, `snd_voice(sample, slot, shift, step)`, `snd_reset()`, `snd_rate(n)` | the digital layer's request routines (4.3). |
| `snd_fill(out)` | `00005220`: 0x800 bytes of 8-bit unsigned mono, 11,111 Hz, to the half buffer the audio DMA is about to need; the Falcon can fill a stereo or 16-bit buffer from these bytes. |
| OPL sink | `(register, value)` pairs in order, no timing inside a call; the tick count at which they are made is the only clock. `tools/export-sound-trace.js` writes them as the F030OPL2 trace format (`W <microseconds> <context> <reg> <value>`) at the PIT's tick period (15,384.07 us); that file plays on `opl-rt-fixture trace` and reproduces the music. |
| MPU sink | bytes to a MIDI out; the MT-32's initialisation text is sent once. |

The JavaScript reference is the executable form of that contract: every call above exists in `dos-sound.js` with
the same argument registers, and a port that passes the same fixtures behaves like the original on those inputs.

## 11. Unproven and blocked

Established by this work (the first group by the captures, the second by reading only):

*Proven by capture (equal to the original on the inputs of section 9):*

* every OPL2 register write of every shipped song played whole (all eleven, on a YM3812 model), of the FM effects 0..24, of the device
  select and detection (card present and absent), and of 267 s of the game's own attract cycle with its timer interrupts; the MPU-401
  bytes and PC speaker port values of OPENMUS and FANFARE (and 400 ticks of MUSDAY on the MPU-401); the driver's variables after every
  call; the digital mixer's output for the SND1 and SPEAK banks (explosion, launch, cannon, rotor loop, speech, slot choice, curves, dither).

*Unproven or open:*

1. **What anything sounds like.** No audio was auditioned: the captures prove the register stream, the mixed bytes and the
   driver's variables, not what a chip or a Sound Blaster does with them. QEMU's AdLib is a model, not a measurement of a chip; the status
   values it returns during detection (0x00, then 0xC0) are what the detection expects, and a real card is **Unproven**.
2. **The MPU-401 and the MT-32.** Bytes only (the probe answers the acknowledge); the MT-32's reaction, the time-out path of `0002BFD9`
   (it pops 16-bit registers off a 32-bit frame) and the intelligent-mode prefixes (never sent) are **Unproven**.
3. **The Sound Blaster programming** (`00001F49`, `00002050`, DMA, the 11,111 Hz time constant `0xA6`, the IRQ number: the digit table
   SOUNDSET fills at run time) was read, not run: QEMU's SB was not attached and the probe calls the mixer's fill itself.
4. **The 65.0 Hz rate** is the PIT divisor `0x47B4` read from `00001CEB`, 1,193,182 / 18,356; it was not measured against a wall clock.
5. **Reads of memory the machine does not have.** Every one-voice FM effect plays a second half that loads patch 255, whose
   envelope pointer comes from a table that runs into a relocated table of the game; a tick that arrives between the effect's two
   halves reads through `0x61800004` (the first half takes the channel again). The natural capture has such ticks, the direct ones do not. The captures
   take what QEMU's 16 MB PC returns there (0x00, "open bus", measured); on another machine this byte is whatever the bus gives, and
   it decides whether the null channel's pitch is rewritten every tick. The JavaScript counts such reads (`machine.openBusReads`).
6. **The word at 0x0E of an MS3 file and the six unused header bytes** are never read by the driver. `MUSVOLC`, `WINMUS` and
   `BIGWIN` are reachable by nothing in this install.
7. **The Music Soft level**: `0x64` in `000267F3` against `0x73` in the radio handler; which one a run ends up with depends on what the player
   touched last.
8. **Effects 0, 3 and 8..24 of the FM table** have no caller in the shipped game; effect 3 is the rotor, which is digital only.
9. **Interrupts inside driver calls.** The original's timer interrupt can arrive between any two instructions of a driver call; the natural
   capture shows it does (section 9). The replay reconstructs each interleaving from the original's variables at the interrupt's entry; it
   does not prove that the original's *sound* is independent of where the interrupt lands.

The following were found by the static caller study (`80` call sites, see section 5) and not by capture:

1. **What the samples actually say or sound like.** All names in 2.1-2.3 are inferred from the call context (event,
   guard, duration, pitch); no sample was auditioned. SPEAK1 id 1 (played at every object destruction) may be a short
   voice line or a debris sound; ids 2/3 (0.3 s) are likely short screams/impacts. SND1 ids 2 and 6 are half-rate
   recordings used at the timed blast; their identity as "pre-blast thump / detonation" is by tick order only.
2. **MUSVOLC.RLE, WINMUS.RLE, BIGWIN.RLE**: no reference in `COMANCHE.EXE`, none of `0.MIS`/`1.MIS` names them. They
   must be named by mission files not shipped here (only `0.MIS` and `1.MIS` exist in the install; the Comanche
   campaign loader walks `0.MIS`..`9.MIS`, `0002A104`). The slot mechanism (21 names, `0002913C`) can carry any
   <=12-character name into slots 6/8/10, but which mission uses which is not provable from this install.
3. Whether `COMANCHE.CFG` bytes `[53D8]` and `[53DD..53E1]` are used by SOUNDSET.EXE only (not analysed; the game
   never reads them).
4. **Music master volume**: `0x64` (apply function `000267F3`, `00026818`) versus `0x73` (radio handler,
   `00026D59`) for "Music Soft" is a genuine disagreement in the image; which value is audible at a given moment
   depends on whether the menu or a screen change touched the setting last. The DOS 8.3 file `COMANCHE.MNU` always
   stores the radio digits, not the volume.
5. Mixer modes 1-4 of `[19DF9]`/CFG byte 1: the code treats them identically (all table entries equal), so any
   distinction is made by SOUNDSET (e.g. SB, SB Pro) and is not visible in the game.
6. `00005B35`: it is the instruction after `call 00028C3E` (the menu); that `00028C3E` returns exactly when a mission
   is started is inferred from the straight-line code (the menu system's exit paths were not walked).
7. The retrace rate of the 328x240 mode that paces the 480/600-frame loops (`00015B78`) is assumed ~60 Hz, not
   measured; the music tick is 65.0 Hz from the PIT divisor `0x47B4`.
8. The FM driver internals (record format at `0002D408+8*id`, the odd `0002BB20-0002BB2C` presence test which
   reads the dword at `0x2D40C+al` rather than `+8*al`) were only inspected as far as the call interface requires;
   whether every FM effect id 1..7 sounds as intended on the OPL is not established.
9. `0002BAA4`'s init-failure semantics for device 5: `[0x2C649]=0x2C485` is a bare `ret`, so `al` is left at whatever
   the previous table load put there (`0x82` on the traced path, `0002BA87`), which the caller treats as "init ok".
   This depends on the exact code sequence and was derived by reading, not by running.
10. The semantic names for weapon pages 4 and 5 ("timed blast", "wingman Hellfire") follow `docs/X86-M68K-MAP.md`
    rows 272/280 and the code at `000230B0-000231F1`; weapon names are not stored in the executable.

## 12. Transferable findings (for `../F030Method/gen_cross_project.py`, not yet upstreamed)

`AGENTS.md` asks for these to go into the shared cross-project document; that regenerates the copy in thirteen sibling
repositories, which this work could not touch, so they are recorded here in the form the shared document should take.

* **Capture a device driver at its port helper, call it with interrupts off.** Stop the guest where it is alive (a known
  instruction of the main loop), put the driver's data back to the image's bytes, point `eip` at the routine with a
  return address on a breakpointed padding byte, and set `eflags` = 2. The driver's output is then a function of the call
  sequence, and a clock is an input (here: a `tick` is `call [vector]`). The same capture, replayed in a language of
  choice, is the executable specification.
* **A helper's register clobbers are part of its contract.** The OPL write helper returns with `ax` = 0 because its delay
  loop counts `ax` down; a caller then passes `ah` on as data. Port every routine with explicit registers, and let the
  first capture that exercises a path find it.
* **Natural capture: connect the debugger before the program loads, and step over foreign hits.** The linear addresses the
  breakpoints use belong to DOS before the program is resident; `c` from such a stop returns at once. Ignore stops until a
  signature is in memory; step (`s`) over an unknown stop address.
* **A timer interrupt lands inside driver calls; reconstruct it from state.** Log the driver's variables at every entry
  of the interrupt and of the driver; replay each call with the interrupt placed at the first memory access or port write,
  after the recorded stream position, where the replayed variables equal the original's. A load-then-store of a shared
  byte (read, interrupt, store) makes stores stale: hook loads as well as stores.
* **Buffers the game shares are not constants.** The song buffer is also the demo buffer; log the bytes at the cursor with
  the state instead of trusting the file.
* **Unmapped reads are 0 on QEMU's PC, not 0xFF.** Measure it by calling `mov al, [addr]` in the guest.
* **Reading the cfg off the setup program.** The configuration digits' meaning is in the setup program's menu code
  (`4 - row`, `row + 1`, a table filled at run time), not in the game; unpack it (`unlzexe`) and read the menu handlers.

## 13. The Falcon driver (2026-10-15)

`src/music.s` is the 68k translation of `0002B9CF-0002C4A0`, written against the JavaScript reference and the
listing. Its variables and tables are one block that mirrors flat `0002C48C-0002DA00`; `src/origexe.s` copies
the tables (`0002C619`, `0002C70D-0002DA00`) out of the player's `COMANCHE.EXE`. Song and envelope cursors are kept
in DOS address space, so the 16-bit `inc bx` (`0002BDED`) and patch 255's out-of-image envelope (section 11, item 5)
behave as in the original. Its only output is `music_opl_write` (register, value).

*Proof.* `tools/check-falcon-music.py` builds `tools/music-test.s` with `src/music.s` and replays, under the patched
Hatari, every op of every non-MPU, non-speaker capture of section 9: each command, song start, stop, tick and song
placement, with the card's status reads answered as the original's card answered them. Per op it compares the OPL2
writes in order, the returned `al`, and a weighted sum over the driver's non-pointer variables reconstructed from the
capture's deltas. Result on both CPUs (68030 TOS 4.02 and 68060 EmuTOS, Hatari 2.6.1-devel of 2026-09-22): **23
captures, 46,759 ops, 46,499 writes, every op identical.** Not compared: the nine captures of devices 1 and 4.

*Platform differences.* (1) Devices 1 and 4 detect as absent: the Falcon has no PC speaker or MPU-401 behind those
ports. (2) The public entries mask interrupts, so a tick lands before or after a driver call, never inside it
(section 11, item 9). (3) The status port: with no synthesiser it reads 0xFF, so the detect fails as on a PC without the
card - the tick vector stays `ret`, no song ends and the fanfare and title screens run their full counts, which is the
port's timing so far. A synthesiser sets `music_chip_present`; the status is then a YM3812's as the detect drives it.
`MUSIC_CHIP=1` builds that status in without a synthesiser, and logs the register stream with markers.
(4) The heap songs (theme, debrief) are played at 64 KB-aligned DOS addresses; the original's heap addresses vary
by run.

*The game's calls.* At every site of section 5.9 and the commands of 5.1-5.7 (`src/music.s` "The game's music
calls", `docs/X86-M68K-MAP.md`). A `MUSIC_CHIP=1` 68060 build was run through the attract, the menu, a mission, the
options bar and the debrief: the order of song starts (flags) and commands is the original's natural capture's, pass
for pass; the fanfare screen ends with its song (279 ticks); mission start sends 0x5000 and the theme looped; the bar
sends 0x4000 and 0x5000; Alt+A sends 0x5000 and the debrief song looped; Esc to the menu sends 0x5000, MENUMUS1 once
and MENUMUS2 queued. The register streams of a natural run are not compared across the two machines: each song's first
writes carry the B0 shadow the previous song left, and the two runs' screen lengths differ (QEMU's VGA retrace is not
paced, so the original's frame budgets run out within a few dozen ticks there).

*Open.* What the stream sounds like: no synthesiser is attached yet. The planned one is F030OPL2 (the DSP56001 OPL2
renderer of `../F030OPL2`), for the 68060 image; it needs its register-to-event decoder on the 68k and the DAC shared
with the digital effects.

