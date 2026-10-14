# Falcon3 resource inventory

Status: `PARTIALLY RESOLVED`.

## Container

`FALCON3.RES` is a normal ZIP archive. The extraction pass verifies all member
CRCs before writing the installed tree to `game/FALCON3/`. The current tree
contains 698 ZIP members, including the 697 files copied into the DOS image.

The installed tree has no extension-wide bitmap contract. Candidate visual
assets use several sizes and names, including:

| Asset | Bytes | Runtime role suggested by name |
|---|---:|---|
| `TITLEPIC` | 16,532 | title artwork |
| `WARROOM` | 25,898 | War Room screen |
| `COCKPIT` | 97,176 | cockpit artwork |
| `TITLE` | 34,338 | title/credits artwork |
| `INTRO1` | 5,523 | intro animation frame/data |
| `INTRO2` | 9,134 | intro animation frame/data |

The byte-level image encoding is now verified for the fixed-size screen assets
`VICTEXT`, `LOSETEXT`, `DRAWTEXT`, and `HTLINFBK.BIN`: each is exactly 64,004
bytes, with a little-endian header of `width=320`, `height=200`, followed by
exactly 64,000 one-byte pixel indices. They render as 320x200 indexed VGA
frames; for example, `VICTEXT` is readable Victory text and `HTLINFBK.BIN`
is the Falcon menu background. Diagnostic renders are retained at:

```text
work/qemu_out/victext_grayscale.png
work/qemu_out/victext_high_contrast.png
work/qemu_out/htlinfbk_grayscale.png
work/qemu_out/htlinfbk_high_contrast.png
```

The palette used for those diagnostic renders is an index-to-gray mapping,
not yet the game's captured VGA palette. The variable-size assets such as
`WARROOM`, `COCKPIT`, `TITLEPIC`, `TITLE`, `INTRO1`, and `INTRO2` do not share
this four-byte-header contract; their compression/encoding still needs to be
identified.

## Verified `COCKPIT` chunk index

`COCKPIT` is a 97,176-byte resource with a six-entry little-endian offset
index in its first 12 bytes:

```text
000C  2F39  5E3E  BE50  F1E2  F5F7
```

At each indexed offset, the loader reads a 16-bit payload length. For the
first five entries, the length word plus payload ends exactly at the next
indexed offset; the sixth payload ends at `0x10F59`:

| Chunk | Offset | Payload bytes | End |
|---:|---:|---:|---:|
| 0 | `0x000C` | `0x2F2B` (12,075) | `0x02F39` |
| 1 | `0x2F39` | `0x2F03` (12,035) | `0x05E3E` |
| 2 | `0x5E3E` | `0x6010` (24,592) | `0x0BE50` |
| 3 | `0xBE50` | `0x3390` (13,200) | `0x0F1E2` |
| 4 | `0xF1E2` | `0x0413` (1,043) | `0x0F5F7` |
| 5 | `0xF5F7` | `0x1960` (6,496) | `0x10F59` |

Static code in the tail opens the runtime pathname at `DS:0454` (the same
address seen for `COCKPIT` in the DOS trace), reads the 12-byte index, seeks to
the indexed offsets, reads each length word, streams the payload through the
shared DOS read/seek/close dispatcher, and then calls an asset post-processor.
This verifies the index contract and its use by the loader, but not the pixel
packing, compression method, or palette. The remaining `0x10F59..0x17B98`
tail is 27,711 bytes and is still unresolved. Structural metadata is saved by
`work/parse_chunked_resource.py` to
`work/qemu_out/cockpit_chunk_index.json`.

## Runtime read contract

A corrected raw-GDB probe captured the returned bytes at the DOS read wrapper,
with the breakpoint temporarily removed while the `INT 21h` instruction ran.
The active cockpit path is:

| File position | Requested | Destination | Meaning |
|---:|---:|---:|---|
| `0x0000` | 12 | `7D0D:0000` | six-entry index |
| `0xF5F7` | 2 | `7D0D:000C` | chunk-5 length `0x1960` |
| `0xF5F9` | 2,048 + 2,048 + 2,048 + 352 | `6F7D:65D8` | chunk-5 payload |
| `0x000C` | 2 | `7D0D:0000` | chunk-0 length `0x2F2B` |
| `0x000E` | 12,075 | `7D0D:5DC0` | chunk-0 payload |

The four captured chunk-5 buffers concatenate byte-for-byte to the file’s
`0xF5F9..0x10F59` payload, and the final capture matches the file’s
`0x000E..0x2F39` payload. This proves that the DOS I/O layer supplies raw
resource bytes; any packing or transformation is performed by the higher-level
loader after the reads. The capture is retained as
`work/qemu_out/cockpit_io_trace.json` and the `cockpit_read_*.bin` files.

The runtime snapshot also resolves the shared output callback table: resident
state entries point into segment `7A1D`, where the callbacks include literal
copy, `0xAB`-sentinel skip, planar copy, and zero-sentinel skip variants. The
planar callback writes through VGA sequencer map-mask port `0x3C5`, uses an
80-byte row stride, and rotates the plane mask as it advances. This establishes
the VGA writer machinery, but the exact callback invocation for the cockpit
resource and the final palette are still open.

## Runtime transform trace

A focused probe now identifies the active chunked-loader instance at runtime:
linear address `0x25DBD` (`CS:IP = 23D3:208D`) reads its pathname from
`DS:0454`, which is `COCKPIT` in the live DOS process. After the chunk-5 length
read, it enters the resident state-8 stream path through `13DB:81F9` and
`13DB:8001`, then reaches the stream-copy callback at `13DB:7FD7`.

That callback does not consume the on-disk bytes directly. During the cockpit
load it exposes generated working buffers at `6F7D:53D4`: a 4,096-byte block
and a final 3,328-byte block were observed, and neither matches a substring of
the raw 6,496-byte chunk-5 payload. This is runtime evidence of a higher-level
transform between DOS reads and VGA output. The captured blocks and event log
are retained at `work/qemu_out/cockpit_stream_00_6f7d_53d4_1000.bin`,
`work/qemu_out/cockpit_stream_01_6f7d_53d4_0d00.bin`, and
`work/qemu_out/cockpit_pipeline_trace.json`; the probe is
`work/trace_cockpit_pipeline.py`.

The bounded run did not stop at the final planar-writer entry, so the exact
screen destination and palette programming remain unresolved. The current
result narrows the next pass to the stream decoder/state table rather than the
DOS file layer.

The executable provides one useful overlay clue: the ASCII token `COCKPIT` is
at file offset `0x4CFC4`, inside RTLink segment 7, whose directory load slot is
`0x1E10`. The `WARROOM` token at `0xC2B47` is inside segment 31, also assigned
to `0x1E10`, and is surrounded by the menu string pair `WAR ROOM`/`WARROOM`;
it is therefore treated as a UI label rather than proof of a resource-loader
reference. Multiple records sharing `0x1E10` are consistent with an overlay
slot reused across screens, but the active record still needs a code-aware
signature or write-trace confirmation.

## Oracle-rendered evidence

The DOS oracle successfully loaded the installed tree and rendered:

- the War Room, showing the no-squadron/no-theater state and the
  `INSTANT ACTION` monitor;
- the F-16 cockpit after entering Instant Action, including HUD, radar,
  weapon panel, and terrain.

The corresponding captures are retained at:

```text
work/qemu_out/screen_t34.png   War Room
work/qemu_out/screen_t49.png   cockpit
work/qemu_out/screen_t55.png   cockpit in continued flight
```

## Runtime file-open trace

The DOS oracle was also traced at all 94 `INT 21h` sites in the MZ image,
filtering for `AH=3Dh` (open). The saved trace contains 77 open events and
shows the actual asset names passed to DOS:

| Phase | Observed opens |
|---|---|
| War Room setup | `WARROOM`, `BARROOM`, `BUTTON1`, `BUTTON3` |
| Instant Action setup | `instact.mis`, `RADEC.Dat`, `MainSeq.Dat`, `FalcObj.Bin`, `sobjects`, `comed.irq` |
| Cockpit setup | `COCKPIT`, `alt.irq`, `isldat.irq`, `ARMSDATA\\ARMSTABL.DAT` |

The complete event log is `work/qemu_out/file_open_trace.json`. This confirms
that `COCKPIT` and `WARROOM` are ordinary installed files opened directly by
the running game, rather than names inferred only from the ZIP inventory.
The raw pixel encoding and palette are still TBD. The earlier unreliable read
sidecar was discarded; the newer trace above is the authoritative byte-level
capture.

The fixed-size decode is a verified control, but the runtime observations for
the variable-size assets are not yet a claim that those raw files have been
decoded. The next resource pass should trace the loader and recover the game's
palette while testing the `WARROOM` and `COCKPIT` formats. The runtime probe
has retained War Room and Instant Action RAM snapshots to support that trace
without another boot.
