# Falcon030 toolchain

The active scripts use local copies of the tools needed to build and inspect a
Falcon executable:

The first Falcon source slice is now restored under `src/` as a CPU-only
attract-mode build. The source-selection record is
`../analysis/functions/falcon-attract.md`; DSP remains a later, dormant
optimization route.

| Component | Location | Purpose |
|---|---|---|
| vasm | `tools/toolchain/vasmm68k_mot.exe` | Motorola-syntax 68030 assembler |
| vlink | `tools/toolchain/vlink.exe` | Atari TOS linker |
| Hatari | `tools/toolchain/hatari.exe` | Falcon030 emulator and debugger |
| TOS | `tools/toolchain/tos402.rom` | TOS 4.02 ROM image |
| DOSBox | `tools/toolchain/dosbox/` | Runs the legacy DSP assembler |
| DSP56000 tools | `tools/toolchain/asm56k/` | DSP56001 assembler and loader |

`tools/build-run.sh` assembles the CPU-only attract source set in `src/*.s` and
puts the stripped executable in `release/comanche.tos`. `tools/run.sh` starts
that file as a Falcon030 without requiring a DSP kernel. `tools/grab-frame.sh` performs a two-pass Hatari
debugger capture: it reads the Videl framebuffer address first, then dumps the
frame and converts it to an image.

The toolchain is not the source-selection authority. Before creating or
building a JavaScript or M68k source for a milestone, trace that milestone's
route in the authoritative DOS image with QEMU's TCG `exec,nochain` execution
telemetry, repeatable inputs, and state/memory snapshots. The route manifest and DOS function record
select the sources and their supported symbols; Hatari/build output then
validates the M68k counterpart. Sources outside the traced route remain
`dormant`/`Unproven` rather than becoming supported through successful assembly.

The copied Hatari executable depends on the MSYS2 UCRT runtime. On a Windows
development machine this is available at `/c/msys64/ucrt64/bin`; if Hatari
starts silently and produces no log, set `PATH` to the matching runtime before
running it.

## macOS

The checked-in vasm and vlink tools are Windows PE binaries. When the sibling
F030Arcade checkout is present, `build-run.sh` automatically selects its native
macOS pair:

```text
F030Arcade/third_party/chorensha/tools/vasmm68k_mot_mac
F030Arcade/third_party/chorensha/tools/vlink_mac
```

The paths can also be supplied explicitly when the checkout is elsewhere:

```bash
export F030ARCADE_ROOT=~/Work/F030Arcade
# or use explicit tools:
# export VASM=$F030ARCADE_ROOT/third_party/chorensha/tools/vasmm68k_mot_mac
# export VLINK=$F030ARCADE_ROOT/third_party/chorensha/tools/vlink_mac
export HATARI=/opt/homebrew/bin/hatari
export TOS=$PWD/tools/toolchain/tos402.rom

bash tools/build-run.sh
bash tools/grab-frame.sh 800 build/frame.png
```

The vasm and vlink binaries are the sibling F030Arcade project's; Hatari is the
Homebrew build. On other platforms, or if that project is not present, the
script falls back to the checked-in Windows tools and reports the selected paths.
Building vasm and vlink from source also works if a suitable native pair is
needed.

Two portability fixes were needed for those commands to work at all, and both
are in the scripts rather than in a wrapper: `build-run.sh` resolves `python3`
before `python`, and `grab-frame.sh` only calls `cygpath` when it exists. The
capture path is the documented way to verify a Falcon change, so it has to run
on the machine the change is made on.

## Probing memory with the Hatari debugger

A `--parse` script plus a VBL breakpoint reads any address out of a running
build, which is how the exception vectors were verified:

```text
b VBL = 800 :once :file probe.ini      # dbg.ini
m $00000008 4                          # probe.ini
quit
```

Two things make this waste time if they are not known in advance. **The VBL
count includes TOS booting**, so a breakpoint below roughly VBL 700 fires before
the program has started and reads whatever TOS last left there - a probe at VBL
120 reported the exception vectors still pointing into ROM, which looked exactly
like an installation bug. `grab-frame.sh` defaults to 800 for the same reason.
And **redirect stdin from `/dev/null`**: a debugger command that errors drops
Hatari into an interactive prompt, where it waits for input that never comes
and the run hangs until its timeout rather than reporting anything.

## MSYS2 support tools

Use the MSYS2 shell at `C:\msys64\usr\bin\bash.exe` with the UCRT64 tools
first on `PATH`:

```bash
export PATH=/ucrt64/bin:/usr/bin:$HOME/.cargo/bin:$PATH
```

The installed support packages are:

```bash
pacman -S --needed mingw-w64-ucrt-x86_64-python \
  mingw-w64-ucrt-x86_64-python-capstone \
  mingw-w64-ucrt-x86_64-nodejs \
  mingw-w64-ucrt-x86_64-ripgrep \
  mingw-w64-ucrt-x86_64-imagemagick rust
cargo install lzexe --locked
```

`lzexe` installs the `unlzexe` command used to unpack the supplied
`COMANCHE.EXE`. The frame-grab script discovers the MSYS2 `magick` command
automatically; no separate Windows ImageMagick installation is required.

## vlink segfaults on a relocation in a BSS section (2026-08-27)

**If the linker segfaults with no diagnostic, check which section your new code
landed in before suspecting anything else.**

`vasm` will happily assemble instructions into a `bss` section. Any of them
needing a relocation - `lea sym,An`, `move.l sym,Dn` - then produces a
`.relaBSS`: relocations against a section with no data. `vlink` does not
reject that, it crashes:

```
readtbyte(src=0x31)                      support.c:559
writereloc(dst=0x2e)                     support.c:686
writesection(dest="", secoffs=46)        targets.c:1192
elf32_reloc                              t_elf32.c:302
```

`dest` is the target section's data pointer, empty because the section is
`SHT_NOBITS`, so the relocation writes through a wild pointer.

This bites easily because **every file in `src/` ends in a `bss` section**, so
code appended near the end of a file - by hand, or by a script inserting
before `end` - lands in BSS rather than text. Put an explicit `text` directive
before it.

Finding the offending object takes seconds: scan the `.o` files for a REL/RELA
section whose `sh_info` target is `SHT_NOBITS`.

```
  hud.o          .relaBSS         -> NOBITS BSS (52 bytes)
```

A newer vlink does not help - v0.18a built from source from
`http://sun.hasenbraten.de/vlink/` crashes identically. Worth reporting
upstream as a missing input check, but the input really is invalid.

**Superseded diagnosis, kept because it was wrong in a way worth remembering.**
This was first recorded here as a "relocation ceiling": the build appeared to
sit on an edge where one more relocation anywhere crashed the link, while 400
bytes of relocation-free code linked fine. Every observation was accurate and
the conclusion was wrong - the probes used to measure it were themselves being
appended into BSS, which is why relocation-free nops were fine, why every file
"failed", and why deleting an unreferenced routine bought no headroom. There
is no ceiling. Measuring carefully is not the same as measuring the right
thing.

## Two more ways to lose an initialiser or a label (2026-08-27)

Both of these assembled cleanly and were found only by running.

**A `dc.w` in a `bss` section is zero-filled at load.** The loader does not
carry initialisers out of `bss`, so a constant written there reads as 0 at run
time. `menu_settings` hit this once; `render_page_anchor` hit it again, where
it would have made the terrain-occlusion anchor 0 and inverted every
comparison that uses it. Put initialised data in `text` or `data`. Every file
in `src/` ends in a `bss` section, so appending to the end of a file lands
there by default - and appending *after* the `end` directive is worse still,
because vasm silently ignores everything past it and the symbols simply do not
exist.

**Local labels are scoped to the preceding global label.** Inserting a routine
between a `bsr .half` and the `.half` it refers to moves the target into the
new routine's scope, and the link fails with an undefined `<routine> .half`.
When adding a routine near another, put it after the whole of the neighbour's
local block - not merely after its `rts`.

## Registers a wrapper must not modify (2026-08-27)

`sprite_draw_page` subtracts the view-window margin from `d1` and falls into
the shared blitter. The first version did that in the caller's register, and
`hud_draw_value` keeps its own running x in `d1` and steps one digit at a
time - so every digit landed four pixels further left than the last and the
final one printed over the SPEED label. The wrappers save and restore `d1`.

The general form: a wrapper that adjusts an argument in place is only safe if
no caller reuses that register across the call. Save it.

