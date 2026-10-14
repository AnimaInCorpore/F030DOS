# F030Underworld — Ultima Underworld for Atari Falcon030

Reverse-engineering workspace for the DOS *Ultima Underworld*. The selected
hashed `UW.EXE` and original execution remain the behavioural authority.

## Current status — reviewed 2026-10-10

This is still a reverse-engineering project: no connected JavaScript game
reference or Falcon runtime is implemented. The executable, including its
Borland FBOV overlay pool, rebuilds byte-identically. Important GR image
formats and whole standard archives also have exact reconstruction evidence.
These are encoding/asset contracts, not proof of game behaviour.

The original runs under genuine MS-DOS in QEMU. Recorded routes reach intro,
menu, keyboard-driven character creation, live 3D gameplay and save-slot flows.
The resident main/event-pump and overlay dispatch are recovered; frame/state
handlers below that pump, remaining resource formats and the first connected
browser/native slice are the next work.

[AGENTS.md](AGENTS.md#next-steps) owns the current work queue.
[analysis/uwexe.md](analysis/uwexe.md) records runtime/overlay contracts;
[analysis/reassembly.md](analysis/reassembly.md) records rebuild evidence;
[analysis/data-formats.md](analysis/data-formats.md) records assets; and
[analysis/qemu-boot.md](analysis/qemu-boot.md) records original DOS execution.
This review reads existing evidence and does not rerun those captures.

Follow the shared [method](../F030Method/METHOD.md) for DOS → recovered
contracts → DOS-validated JavaScript → native m68k. Original media, extracted
data, listings and emulator artifacts remain local.
