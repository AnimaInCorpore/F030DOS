# Resident startup and first resource path

Status: the first resident startup resource path is **IDENTIFIED** from direct
16-bit call targets and embedded filenames. Its exact runtime timing and
error/fallback behaviour remain **TBD** until the DOS oracle is available.

## Static call chain

The CD English MZ image has one direct far call to `_Main_Program` at file
`0xE0AB` (`9A 06 00 37 08`, target `0837:0006`, file `0xAB76`). The recovered
TDINFO symbol names make the first calls in `_Main_Program` unambiguous:

| caller file offset | target | argument evidence |
|---:|---|---|
| `0xABF5` | `_Open_Quick_File` | `DS:0x1174` → `INTROVOC.PAK` |
| `0xAC1B` | `_Load_Font` | `DS:0x1181` → `intro.fnt` |
| `0xAC3C` | `_Load_Font` | `DS:0x118B` → `NEW8P.FNT` |
| `0xAC97` | `_Load_Alloc_Data` | `DS:0x1195` → `LOLINTRO.DIP` |

The filenames are stored in the resident data image at file `0x20AD4` and
following. The package inventory supplies the corresponding case-insensitive
entries: `STARTUP.PAK` contains `INTRO.FNT` at `0x11038..0x12C5C`, `NEW8P.FNT`
at `0x138E9..0x14F2F`, and `LOLINTRO.DIP` at `0x186D3..0x18FBB`.
`INTROVOC.PAK` is a separate 110-entry voice package; its directory ends at
`0x661` and its first data offset is `0x665`.

This establishes the first resource family touched by the resident program:
the startup path opens the voice package, then loads two startup fonts and an
intro data blob before continuing into the intro/menu setup. It does not yet
prove whether `_Find_File` obtains the font entries through a package table or
falls back to a DOS path; that distinction is the next oracle check.

## Loader contracts recovered statically

`_Open_Quick_File` first closes/frees any previous quick-file state, calls
`Low_Level_Open_Quick_File`, and allocates `record_count * 0x12 + 4` bytes for
the returned directory table. The low-level routine opens the named file,
reads the PAK-style offset/name directory, uppercases each entry name, and
copies one `0x12`-byte record per entry. These operations agree with the
independent PAK directory parser, but the exact in-memory field meanings are
not assigned beyond the measured record stride.

`_Load_Font` calls `_Find_File`, opens the result, reads a two-byte size, then
allocates `size + 0x10` bytes and reads the remainder. It accepts the Westwood
v3 marker `00 05` at payload offset `+2`/`+3`. The new `tools/re/fontinfo.py`
decoder validates the complete v3 tables and renders both startup fonts.

`_Load_Alloc_Data` calls `_Open_File`, queries `_File_Size`, allocates the
file-sized buffer, reads the whole file and closes the handle. The loaded
`LOLINTRO.DIP` is a 16-bit offset table followed by NUL-terminated CP437
strings. `tools/re/dipinfo.py` validates the invariant across all nine `.DIP`
witnesses in the English, French and German package trees, including the
startup `LOLINTRO.DIP`/`HISTORY.DIP` pair and the `FINALE2.PAK` finale text.

## Evidence boundary

All offsets above are from `DATA/ENG/LANDS.EXE` and its exact CD package tree.
The static call edge and loader functions are resident MZ-image code; they do
not depend on the installed `MAIN.EXE` `FBOV` tail. No new indirect execution
seed is added here: the `_Main_Program` edge is a direct far call, and its
resource callees are already direct calls in the recovered body.
