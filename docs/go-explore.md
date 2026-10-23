# Go-Explore for testing the ports

Status: recommended method, not yet implemented (recorded 2026-10-19). Use it
when a port improvement needs inputs that reach further into a game than the
existing fixtures, captures and bots do - for the original's execution
coverage as for the Falcon port's tests - before writing another hand-played
session, scripted route or reward-driven agent.

## The method

Go-Explore (Ecoffet et al., *First return, then explore*, Nature 2021;
https://github.com/uber-research/go-explore) keeps an archive of every
distinct coarse state it has reached ("cells"), picks a rarely visited or
recently productive cell, **returns** to it by restoring a snapshot, and only
then explores with random input. Depth is never paid for twice, and side
paths are kept even when they look unproductive. Reward-only exploration
(PPO) under-covers exactly that: STEArcade's Kung-Fu Master pilot gained
0.55% over random input and stayed on its first floor.

## In this family

- **The original (DOS).** `method/METHOD.md` §3.5 (development home:
  F030Method): cells over the QEMU DOS oracle, return with `savevm`/`loadvm`
  over QMP, novelty from the execution-telemetry plugin (`dos/trace/`), one
  coverage map per cell.
- **The port (Falcon, Hatari).** A cell is a coarse key of the port's own
  state - screen or menu id, options-bar column and row, mission, flight or
  debrief phase, a hull band. Comanche's harness has the pieces
  (in F030Comanche; here after the next `tools/publication.py sync`):
  `games/comanche/work/bot/fsession.py` reads that state and injects IKBD keys
  through Hatari's debugger (on Windows as well), `menu_sweep.py` is the
  deterministic per-item check, and `ppo_menu.py` the reward-driven variant
  to compare against. Return is a replay of the cell's input timeline from the
  program start (the session is lock-step, one job per frame); a Hatari
  memory snapshot would make it cheaper.
- **Both together.** A timeline that reaches a cell in the original and in
  the port is a lock-step comparison input: the port's state at that point
  against the original's, as `start_state.py`/`compare_start.py` already do
  for mission starts.

Go-Explore finds shortcuts and edge paths; it is not a human-like player. For
human-like play prefer a rule-based pilot with human timing (Comanche's
`work/bot/pilot.py`) or imitation of recorded sessions.

## Not chosen: DreamerV3

DreamerV3 (Hafner et al., *Mastering diverse control tasks through world
models*, Nature 2025; https://github.com/danijar/dreamerv3, MIT licence,
JAX) learns a world model from pixels and trains its policy inside it. It is
considered and not chosen as the explorer (2026-10-23):

- It is reward-driven, a stronger form of the PPO variant above, so it goes
  where the reward points and does not keep side paths; coverage is the goal
  here.
- It needs a GPU, a Gym-style wrapper over QEMU and Hatari, a reward per game
  and still hundreds of thousands of frames; Hatari runs lock-step, one job
  per frame.
- Its play is not human-like either.

Where it may still help: as the explore step for action cells (Comanche or
F29 combat) if random input inside Go-Explore dies before it finds anything
new - only once Go-Explore runs and stalls there. A world model trained on the
original and checked against the port's runs could flag divergences, but only
over game state (VGA and Falcon screens differ), and the lock-step comparison
(`start_state.py`/`compare_start.py`) already checks that exactly.

## References

- https://github.com/uber-research/go-explore - code of the papers (archived
  2022; licence marked "Other" - read it before reusing code).
- https://github.com/conglu1997/intelligent-go-explore - a foundation model
  choosing interesting cells.
- F030Arcade `docs/go-explore.md` and STEArcade `docs/go-explore.md` - the
  arcade siblings (MAME telemetry for the 68000 disassembler; a cell archive
  over `playbot.py`).
