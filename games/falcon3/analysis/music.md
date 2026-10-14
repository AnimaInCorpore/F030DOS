# Music inventory and next playback experiment

Status: `PARTIALLY RESOLVED`, 2026-09-13. This is static resource analysis;
the DOS sequencer, device selection and Falcon playback remain unverified.

## Immediate next milestone

Produce a **standalone Falcon player of one demanding, correctly initialized
Falcon 3.0 song**, with a Munt reference recording, complete audio-output
comparison and underrun counts. Use the game's actual event sequence and
instrument state before spending more time optimizing a synthetic voice loop.
Game integration follows after this player is measured; this investigation
adds no dependency to the graphics-first game milestone.

First establish which extension family the original selects for its Roland
configuration, how it consumes the setup resource, and how it handles the
six files rejected by the strict reader. Capture DOS file opens and outgoing
MPU-401 bytes at startup and a music transition. Preserve message framing,
event order, tempo changes, bank state and the selected file hashes. These
are unresolved inputs to a correct sample-bank capture, not optional polish.

## Source and extraction

The supplied ISO still matches the archive record:
`6079944302e1aa8bd604f480a592b505cb73e8f0bc1d0875709134a20d214d80`.
The derived trees were absent in this checkout. On this macOS host,
`tar -tf assets/FALCON3.ISO` returned success with no listed members. The
following recovered the tree and verified all 698 ZIP members / 10,630,258
uncompressed bytes:

```sh
7zz x assets/FALCON3.ISO -ogame/cd -y
python3 tools/extract_resources.py
```

The extracted executable hash is
`01c190669084a3047c01688303baf39329e7c68ffb576aa3a9e272da4ea428d8`.
The supplied image was not modified. Extraction success is based on member
counts and CRCs, not the archive command's exit status alone.

## Corpus findings

`MUSIC/` contains **150 files / 111 distinct byte streams**, all carrying
SMF headers. There are 26 `.MID`, 26 `.MDI`, 26 `.MII`, and 24 each of `.ADL`,
`.ALB`, `.ALI`. These are alternate resources, not 150 distinct songs.
Suffix-to-device selection is **TBD**; do not choose a Roland arrangement
from its extension alone.

The analyzer checks full chunk extents, then uses Mido 1.3.3 to decode events.
**144 files pass; six are rejected** with `running status without last_status`:

- `H.MID`, `H.MDI`, `H.MII` share SHA-256
  `d54a914def09c01ea456e6e4bba98ee2d2852a7394959dd8bd1e1dc043181fd8`.
- `J.ADL`, `J.ALB`, `J.ALI` share SHA-256
  `bd0ed202e5eaa69e598a0f020d3a331575bd190d060f99f54cd97b97b479b4f9`.

No reference file was repaired or silently skipped. The report includes the
rejections and the command returns failure because corpus coverage is
incomplete. This does not establish that the DOS game cannot play those files;
its track termination and parsing behavior must settle the discrepancy.

Preliminary maxima over the **accepted subset**:

| Family | Parsed / total | Peak counted keys after a tick | Most note starts in 151 ms | Most starts at one tick |
| --- | ---: | ---: | ---: | ---: |
| `.ADL` | 23 / 24 | 12, `A.ADL` | 17, `A.ADL` | 12 |
| `.ALB` | 23 / 24 | 10, `C.ALB` | 14, `N.ALB` | 9 |
| `.ALI` | 23 / 24 | 10, `C.ALI` | 17, `F.ALI` | 9 |
| `.MDI` | 25 / 26 | 20, `R.MDI` | 21, `R.MDI` | 13 |
| `.MID` | 25 / 26 | 36, `T.MID` | 24, `T.MID` | 12 |
| `.MII` | 25 / 26 | 17, `D.MII` | 26, `F.MII` | 13 |

These are **event statistics, not sounding polyphony or performance results**.
Each note-on adds a counted key until note-off; equal-pitch retriggers count
independently. CC120/123 clear counted keys. Sustain pedal, release tails,
one-shot percussion behavior, voice stealing, bank mapping and proprietary
driver behavior are not simulated. Several files use pedal controllers;
`B.MID` also has 120 unmatched note-offs under this model. Same-tick ordering
comes from a stable Mido track merge, not a DOS trace.

The 151 ms statistic counts every start in a sliding window even if its note
ends sooner. It approximates demand on the prototype's recorded-attack pool,
but is not a measured stream count or a failure verdict. A 16-note burst test
does not cover repeated starts approaching that rate. Likewise, the raw
36-key peak in `T.MID` cannot establish 36 audible voices without its actual
driver and note-lifetime behavior.

The parsed `.MID`, `.MDI`, `.MII` subsets contain respectively 65, 66, 65
distinct program-change numbers. These are zero-based MIDI program values,
not verified factory instrument identities. Some notes precede an explicit
program change; the report labels their program `unspecified` instead of
assuming the receiver's startup state.

## A concrete bank-initialization prerequisite

`Y.MID` contains **no note-ons**. Its 286 SMF SysEx packets reassemble into
**83 complete Roland data-write messages**, all with valid checksums:

| Address family | Completed messages | Interpretation in Munt's memory map |
| --- | ---: | --- |
| `05xxxx` | 8 | Patch memory |
| `08xxxx` | 64 | User timbre memory |
| `03xxxx` | 9 | Temporary patch / nearby state |
| `10xxxx` | 1 | System state |
| `04xxxx` | 1 | Temporary timbre memory |

The address interpretation is backed by the local
[Munt memory map](../../F030MT32/third_party/munt/mt32emu/src/MemoryRegion.h:94).
This resource can change instrument definitions and program mapping. Capturing
only factory presets would therefore be an unjustified default until the
original initialization route is known. Which music/effect paths use these
definitions remains **TBD**.

The first complete write targets `05 00 00`, with 128 data bytes. Its initial
F0 packet carries only the Roland header/address; following F7 continuation
packets carry data and finally the checksum/terminator. Sending each decoded
Mido `sysex` event as a newly framed complete message would corrupt this
resource. The analyzer retains the raw F0/F7 framing for these setup files,
joins continuations, then checks message boundaries and Roland checksums.

`Y.MID` and `Y.MDI` are byte-identical, SHA-256
`b14c4bb22657382a10b96ddb18894ebbee406025b9d2b8c5e17c74073194a73c`.
`Y.MII` has a different hash; its packets also form 83 checksum-valid writes.
The three must not be assumed interchangeable without comparing the selected
initialization and its effects.

## Relationship to the resident sample prototype

The [ScummVM-workspace prototype](../../scummvm-falcon030/devtools/atari-falcon030/tools/mt32-sample-bank/RESIDENT.md)
passed standalone, stock-clock Hatari SSI tests for 32 sounding sample voices,
including 16 short recorded attacks, or eight continuous streams plus 24
resident sustains. It used three factory patches and scripted control packets;
no Falcon 3.0 file was played by it.

After DOS resource selection and bank setup are resolved:

1. Render a reference with the actual initialization and correct song variant.
   Measure sounding notes/partials, release overlap, controller use and the
   busiest attack windows. Choose the worst relevant cue from that evidence.
2. Prepare the required patch samples and implement a standalone MIDI-driven
   demo with correct note-off, pedal, pitch bend, level/pan and smooth joins.
   Measure live packet construction as well as DSP and host transfers.
3. Replay the whole song and loop/transition cases through Falcon SSI. Require
   intact timing/output and zero underruns, then audition against the reference.
   Physical Falcon verification follows; game/speech/DSP contention is a
   further integration gate, since no playable game runtime exists here yet.

If this fails, change the sound strategy explicitly: shorter or shared attack
data, a documented voice policy, or pre-rendered cue segments. Do not silently
drop notes or claim the synthetic 32-voice result covers the songs.

## Reproduce the inventory

```sh
python3 -m venv work/midi-venv
work/midi-venv/bin/python -m pip install 'mido==1.3.3'
work/midi-venv/bin/python tools/test_analyze_music.py
work/midi-venv/bin/python tools/analyze_music.py
```

The final command currently exits nonzero for the six rejected files while
writing `work/music-analysis/inventory.json`. It retains every file hash,
program/controller statistics, peak times, framing/checksum observations and
explicit model limitations. The unit controls cover a known tempo change and
three-note burst across tracks, truncated input, and fragmented SysEx with
both valid and invalid checksums. All generated game data and the local Python
environment remain ignored.

Mido's [SMF documentation](https://mido.readthedocs.io/en/stable/files/midi.html)
describes the track merge and tempo conventions used for this static analysis.
Neither Mido agreement nor the numeric checks substitute for the original DOS
sequencer's observed behavior.
