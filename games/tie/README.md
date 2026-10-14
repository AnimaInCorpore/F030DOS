# F030TieFighter — TIE Fighter CD for Atari Falcon030

Reverse-engineering workspace for the DOS *TIE Fighter CD* build. The hashed
selected executable and original execution decide behaviour.

## Current status — reviewed 2026-10-10

There is no Falcon game runtime or connected JavaScript game reference yet.
`Z_TIE__.EXE` is a Watcom LE image, not the withdrawn private DOS4G/OLX model,
and the full executable has byte-identical rebuild evidence. Extensive LFD
container/palette/image/animation decoding and function identification are
recorded. FILM handlers and SHIP headers are mapped; complete opcode meanings,
SHIP rendering and runtime-built PANL tables remain open.

The DOS/extender boot path works, but the game's genuine MSCDEX/CD check
still blocks the selected original game route. Restore measured original
execution and recover the required renderer/resource contracts before the first
browser/native slice. Reassembly and naming counts are not gameplay completion.

[analysis/todo.md](analysis/todo.md) owns the work queue;
[analysis/ztie.md](analysis/ztie.md) owns executable/startup evidence;
[analysis/LFD.md](analysis/LFD.md) owns resource contracts;
[analysis/reassembly.md](analysis/reassembly.md) owns rebuild evidence.
This review does not rerun the DOS route or change any evidence grade.

Follow [AGENTS.md](AGENTS.md) and the shared [method](../F030Method/METHOD.md).
Original media, installed assets, listings and emulator outputs remain local.
