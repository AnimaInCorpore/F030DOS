# F030Underworld2 — Ultima Underworld II for Atari Falcon030

Reverse-engineering and porting workspace for the selected DOS *Ultima
Underworld II* build. DOS execution decides behaviour.

## Current status — reviewed 2026-10-10

The port has a canvas-only browser intro/display slice and a separately
assembled, Hatari-verified Falcon RGB565 presentation seam. The seam's complete
128,000-byte page matches its host fixture; this is not equality with an original
DOS game frame or proof of physical VIDEL scanout.

Browser keyboard events stop at the emulated BIOS INT 16h queue. The recovered
keyboard/character consumers and main game loop are not integrated. Neither
the browser nor Falcon implementation is a playable 3D game yet.

The executable rebuilds byte-identically with a whole-file classification audit;
standard GR archives and several other asset families have exact rebuild
evidence. The original DOS route reaches character creation and gameplay.
Semantic function/VM recovery and connected menu/gameplay contracts remain open.

[PORTING.md](PORTING.md) owns the roadmap, fixture commands and fidelity
boundaries. [AGENTS.md](AGENTS.md) owns detailed findings; the shared
[method](../F030Method/METHOD.md) governs new slices. This status review did
not rerun the original or target captures. Generated game assets and emulator
outputs are not new source changes.
