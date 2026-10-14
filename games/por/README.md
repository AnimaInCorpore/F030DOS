# F030POR — Pool of Radiance for Atari Falcon030

Reverse-engineering and native porting workspace for SSI's DOS *Pool of
Radiance*. The hashed `START.EXE` and `GAME.OVR` build and its captured
execution decide behaviour; host conversion and Falcon output are implementations.

## Current status — reviewed 2026-10-10

The Falcon presentation endpoint is implemented: `make title-smoke` compares
the full 128,000-byte RGB565 page with host palette expansion and has recorded
identical results at both 4 MB and 14 MB. This proves presentation of a converted
image, not the original screen layout or a playable game.

The executable/38-overlay structure and important image/dungeon/script formats
are recovered. Native screen composition, font/text, dungeon view and game
rules remain unfinished. ECL framing and inline text are decoded; full script
entry discovery and opcode semantics are still open. Input integration has not
started. Audio remains deferred.

The governing roadmap and per-slice evidence are in
[PORTING.md](PORTING.md#slice-status). Binary and renderer findings are in
[analysis/executables.md](analysis/executables.md); format contracts are in
[analysis/data-formats.md](analysis/data-formats.md). Follow
[AGENTS.md](AGENTS.md) and the shared [method](../F030Method/METHOD.md).
This status review did not rerun the target smoke test or promote gameplay support.

Original media, extracted data, generated binaries and captures remain local;
do not add them to source commits.
