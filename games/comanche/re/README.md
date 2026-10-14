# Reverse-engineering workspace

- `seeds.txt` is committed: it contains only addresses and reasoning.
- `listings/` contains generated disassembly listings.
- `resources/` contains extracted archive resources.
- `unpacked/` contains decompressed resources.
- `assets/extracted/comanche_hdd/` is the generated DOS hard-disk tree and is
  ignored; it contains the 92-file `C:\COMANCHE` installation.
- The main executable is LZEXE 0.91-packed. Unpack it into `unpacked/` before
  feeding it to the generic MZ tools; see `docs/RE-WORKFLOW.md`.
- `docs/X86-M68K-MAP.md` is the committed semantic index from recovered flat
  x86 addresses to Falcon routines. Update it whenever a function is named,
  replaced by a platform service, ported, or verified.

The generated directories are ignored. Do not place original game data,
decompressed resources, rendered screenshots, or complete disassembly listings
under version control.
