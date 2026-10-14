# AGENTS.md

Working agreement for AI agents (and humans) in this repository. These rules
are mandatory.

## This is a publication copy, not a development home

- The ports are developed in their own repositories next to this checkout
  (`../F030Comanche`, `../F030F29`, `../F030POR`, ...), the shared method in
  `../F030Method`. Fix code and documentation **there**, commit there, then
  carry the commit here with `tools/publication.py sync`. Do not develop a port
  in `games/<game>/`.
- An edit made here (a link, a path) is three-way merged by the next sync; keep
  such edits rare and say why in the commit message. Prefer a fix in the
  development repository.
- The build entry points stay as imported: the root `Makefile` supplies the
  toolchain locations (`F030ARCADE_ROOT`, `F29_ROOTS`, `VASM`, `VLINK`,
  `HATARI`, `TOS`) instead of rewriting the ports' paths.

## What may be committed

- Only paths that `docs/publication-inventory.json` lists as `candidate`, plus
  the files this copy owns (`README.md`, `AGENTS.md`, `Makefile`,
  `.gitignore`, `tools/`, `docs/`). `python3 tools/publication.py stage`
  indexes exactly those; `make check` must pass before every commit.
- Never commit game media, disk or DOS installation images, data extracted,
  unpacked or converted from a game, string dumps, traces or captures of the
  original, disassembly or decompiler output of a game program, data tables
  copied from one, build products, vendor binaries or ROMs.
- A failed content screen can be overridden only with
  `tools/publication.py accept <path> "<evidence>"` after reviewing the file,
  and only with evidence that it is not game content (for example: "computed
  table, matches round(sin(2*pi*i/3600)*2^31)"). The acceptance is bound to the
  file's hash; a changed file is screened again. Location rules (game media,
  vendor trees) are never overridden.
- The checks are engineering controls, not a rights review. They do not make
  anything publishable on their own (see `docs/PUBLICATION.md`).

## Release and publication

- `make release VERSION=<v>` packs the Falcon programs and a `README.TXT`; no
  game data. A program that carries game content stops the release; pass
  `--allow-embedded` to `tools/release.py` only with the owner's approval.
- Keep the states in `tools/release.py` and the root `README.md` in step with
  each port's README when syncing.
- A release is `make release VERSION=<v>`, a `v<v>` tag and a GitHub release
  with the zip (README.md, Release). Run it with each game's files in place so
  the embedded-content check runs; `README.TXT` names any program it could not
  check (F29 in 0.1-preview).
- Creating a release or changing the repository's visibility needs the
  owner's explicit approval each time.

## Tools and emulator

- The toolchain and emulator come from `../F030Arcade/third_party` (vasm,
  vlink, ASM56000, the TOS images, the patched Hatari). Use only the patched
  Hatari for runs, screenshots and measurements, and name the Hatari build
  beside every throughput figure; keep emulator timing apart from real-Falcon
  measurements.
- Each port's own `AGENTS.md` governs work in that port's development
  repository; `method/METHOD.md` is the shared porting procedure.
