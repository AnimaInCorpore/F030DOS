# `Z_TIE__.EXE` — static analysis master (32-bit game image)

Status: **mapped, named at provenance level** — container re-resolved
2026-08-21 (the "OLX hybrid" model is withdrawn: the file is a standard
Watcom **LE** module, `DOS4G-header.md`); function inventory v2 done (P1.2,
file offsets valid, runtime column superseded); Ghidra pipeline built and
804 of 3,528 functions named (P1.3, `functions.md`); runtime claims pending
boot (P3.2, §7 below). This is the TIE analog of UW1's
`analysis/uwexe.md`: one master doc per executable, details in the linked docs.

Target: `game\SWTieCD\TIECD\Z_TIE__.EXE` — 1,031,495 bytes, the game.
Run by `DOS4GW.EXE` (Rational DOS/4G 1987–1993 extender; ground truth in
`DOS4GW-loader.md`), or by any standard-LE-capable loader.

## 1. Identity (re-verified 2026-08-21, `work/audit_headers.py`)

- **MZ stub + standard Watcom LE module.** The stub (file `0x00..0x2A4E`) is a
  real 16-bit Watcom program — entry `0000:030E` → file `0x36E`
  (`E9 CB 00` + `WATCOM C Run-Time system code`), 6 relocations at 0x40 — and
  `e_lfarlc` = 0x40 makes the dword @0x3C a genuine `e_lfanew` = **0x2A50** →
  `LE`.
- LE module: 2 objects — obj1 (code) base `0x10000`, vsize 0xAAE83, file
  `0x3D800..0xE8800`; obj2 (data/DGROUP) base `0xC0000`, vsize 0x46470
  (0x32470 of it BSS), file `0xE8800..0xFBD47`. 191 × 4 KB pages, identity
  page map, data pages ending exactly at EOF. Entry = obj1+`0x7B4E4` →
  linear **0x8B4E4**, file **0xB8CE4** (the Watcom C/C++32 CRT: `jmp short`
  over its own banner). Full map + the withdrawn-readings table:
  **`DOS4G-header.md`**.

> ✗ **Withdrawn (2026-08-21):** *"DOS4G 'OLX' hybrid: 16-bit client half +
> LE/DOS4G private header + 32-bit image; MZ is a pure container
> (`e_ip=e_cs=0:00`, `e_rels=0`) never executed by DOS; `dwEntry = 0x00010002`
> = image base+2; selector table @ 0x2B44 (191 entries, N·0x10000)."*
> Every element was a standard LE structure misread — the "selector table" is
> the object page map (u24 big-endian page numbers), `0x00010002` is
> cpu_type/os_type, and the MZ entry fields were read at 0x20/0x22 instead of
> 0x14/0x16. `DOS4G-header.md` quotes each old reading beside its reality.

## 2. Layout (re-verified 2026-08-21)

| Offset | Size | Content |
|---|---|---|
| `0x0000` | 0x60 | MZ header: real entry `0000:030E`, 6 relocations @ 0x40, `e_lfanew` @ 0x3C = 0x2A50 |
| `0x0060` | 10,734 B | **16-bit Watcom stub program** (runs only when executed without an extender; `DOS4GPATH`/`PATH` strings; CRT banner @ 0x371; behaviour TBD) |
| `0x2A50` | 0xC0+ | **LE header**; object table @ 0x2B14, page map @ 0x2B44, fixup page table @ 0x2E4C, resident name table @ 0x2E40 |
| `0x314C` | → `0x3D7DC` | **fixup record table**: 27,438 records, 100 % 32-bit-offset/internal (`work/audit_fixups.py --stats`); the old "thunk clusters @ 0xAD8C / 0x26C00" both lie inside it |
| `0x3D800` | → `0xE8800` | **object 1 (code)**, linear `0x10000 + (file − 0x3D800)` |
| `0xE8800` | → `0xFBD47` | **object 2 (data)**, linear `0xC0000 + (file − 0xE8800)`, + 0x32470 B BSS |

**Runtime geometry:** object bases come from the object table and the loader
applies the fixups — there is no target-fixed base. ✗ *Withdrawn: "image
placed at linear 0x7E000, hard-fixed by CRT immediates 0x7E00/0x7E10"* — that
rested on treating file `0x3F002` as the entry; the real entry is file
0xB8CE4, and what the `0x7E00`/`0x7E10` immediates at file 0x3F0BA/0x3F116 do
is unread under the correct map (TBD, no longer load-bearing).

## 3. Code & data inventory (32-bit image)

- Functions: **`analysis/32bit/functable_v2.txt`** — 4,030 fns, 84.6% byte
  coverage (`work/sweep32.py`); v1 `functable.txt` (Rizin) broken, superseded.
  Addresses are valid **as file offsets**; the sweep's runtime column and its
  `0x3F000` base convention are superseded (§4), and file `0x3D800..0x3F000`
  — the true start of object 1 — was never swept. Uncovered 14.5% classified
  in `uncovered_v2.txt` (data tables, embedded filenames `emperor.lfd`/
  `capture.lfd`/`tietext0`/`newtarm`, clusters @ 0x0E6008/0x0EE9C3/0x0BA5xx
  that decode as 16-bit — classified "entry-stub/thunk bodies" under the
  withdrawn model, now simply *unexplained*, re-classify under the LE map,
  zero regions). Method/limits: `analysis/32bit/P1.2-functable-v2.md`.
- String pools (mapped, see `DOS4G-header.md`): img+`0x0A9800..0x0AB600`
  (startup/CD/IMUSE: `/trebla` @ 0x0A9809, `You must run TIE.EXE for the game.\n`
  @ 0x0A981A, `ERROR #%d:` @ 0x0A983E, `resource\`/`RES320\`/`tie.cd`/
  `foption.cfg`/`imuse.*`), img+`0x0B9000..0x0BE000` (scene .WRK paths:
  `\astream\scene13a.wrk`/`scene12a.wrk`), `.TFR`/`__temp__.tfr` @ 0x0BACE4.
- Full rizin string dump: `analysis/32bit/strings.txt` (**use the paddr column**
  = image-relative; vaddr column is garbage under rizin 0.8.2).

## 4. Address mapping (one place, use everywhere)

| notation | meaning | example |
|---|---|---|
| file | offset in `Z_TIE__.EXE` | 0xE881A |
| `img+X` (legacy alias) | file `0x3F000 + X` — a pure file-offset alias; keeps every string-pool citation valid | img+0x0A981A |
| `work/z_tie_32.raw[X]` | X into the legacy extract (offset 0 = file 0x3F000; misses file `0x3D800..0x3F000`) | [0x0A981A] |
| obj1 linear | `0x10000 + (file − 0x3D800)`, file ∈ [0x3D800, 0xE8800) | file 0xB8CE4 → 0x8B4E4 |
| obj2 linear | `0xC0000 + (file − 0xE8800)`, file ∈ [0xE8800, 0xFBD47) | file 0xE88BF → 0xC00BF |

> ✗ **Withdrawn (2026-08-21):** the runtime row *"linear = 0x7E000 + X"* (and
> "16-bit half: linear = file offset"). Object bases come from the LE object
> table; see `DOS4G-header.md`.

Worked check, both directions: `img+0x0A981A` = file 0xE881A =
`You must run TIE.EXE for the game.\n` ✓; and the CD-check string obj2+0xBF
(file 0xE88BF) has exactly one fixup source site, file 0x3DAC3 / linear
0x102C3, raw dword `BF 00 00 00`
(`python work/audit_fixups.py --target=2:0xBF`) ✓. Before P1.3 Ghidra import,
verify each table's address column against this mapping (sweep outputs claim
file offsets).

## 5. Launch context

Boot chain (verified, full version in AGENTS.md): `run.bat` → `TIE.EXE`
(plain 16-bit Watcom launcher — the "hybrid" reading is withdrawn, see the
2026-08-21 correction in `analysis/32bit/P1.5-launchers.md`) → `z_tie2__.exe`
(16-bit guard) → `dos4gw.exe z_tie__.exe /trebla /320`. `/trebla` =
anti-double-launch marker (checked again inside the image, §3 pool); `/320` =
320×200 resolution arg. Env: `DOS4GPATH`, `PATH`; config `CDROM.CFG`,
`FOPTION.CFG`, `IMUSE.INI`.

## 6. Artifacts

Indexed with regeneration commands in **`work/README.md`** (sweeps, slices,
rizin dumps). Ghidra project + exports live in `work/ghidra/`,
`work/ghidra_export/` (pipeline + regeneration: `analysis/functions.md` §7).

## 7. Open questions (resolve via boot / dynamic test → todo P3.2)

Numbered claims to verify dynamically; keep resolved items struck through with
the residual (UW1 `uwexe.md` §7 pattern):

1. **Demand-load vs full copy**: does DOS4GW read all 191 pages of the LE
   module up front, or demand-load via INT 13/21? (watch read patterns
   dynamically)
2. ~~Base/selector check: confirm runtime 0x7E000 base + `0x7E00`/`0x7E10`
   selector installs~~ **WITHDRAWN 2026-08-21** — there is no 0x7E000 base;
   the object bases are 0x10000/0xC0000 from the LE object table
   (`DOS4G-header.md`). Residual worth one probe run: residency-check the two
   objects at those linears (`gdbstub_probe.py`), and read what the
   `0x7E00`/`0x7E10` immediates at file 0x3F0BA/0x3F116 actually feed.
3. ~~Thunk-record type semantics (1/2/3)~~ **DISSOLVED 2026-08-21** — the
   "thunk records" were misaligned LE fixup records; the whole table is
   decoded statically (27,438 × 32-bit-offset/internal,
   `work/audit_fixups.py --stats`). Nothing remains to observe.
4. ~~Entry-variant selection (0x2045 vs 0x2043 stubs)~~ **DISSOLVED
   2026-08-21** — those are the two object flag words, not entry stubs.
5. ~~LE header TBD fields (dwDataSize, 0xC4/0xF4/count)~~ **RESOLVED
   2026-08-21** — all standard LE fields (`eip`, table offsets, object
   counts); withdrawn-readings table in `DOS4G-header.md`.
6. **XMS alloc sizes** via DPMI 0x2000 RM gate (no INT 43h/17h/20h in DOS4GW).
7. **DOS/16M / VMM4G fallback paths** — exercised at all on our machine?
8. ~~16-bit-half full sweep (P1.4) covers 0x40–0x46470; the 6-entry vector
   table at 0x40 still unexplained~~ **RESOLVED 2026-08-21** — the "vector
   table" is the MZ relocation table (6 × `(offset u16, segment u16)`), and
   there is no 16-bit half beyond the 10.7 KB MZ stub (`0x46470` is object
   2's virtual size). P1.4 rescoped: sweep the *stub* (0x60..0x2A4E) and
   answer what it does when run without an extender.
9. ~~Data xrefs need the LE fixups applied~~ **RESOLVED 2026-08-21** — the
   diagnosis was right (raw operands are unrelocated object-relative values;
   no immediate scan under any base can work), and the fixup-aware pass now
   exists: `work/audit_fixups.py --target=OBJ:OFF` is a full reverse-xref
   index over all 27,438 records. First customer answered: the CD-check
   string obj2+0xBF has exactly **one** source site — file 0x3DAC3, linear
   0x102C3 (`analysis/qemu-boot.md`). The routine itself is now traced — see
   item 10.
10. **CD-check routine (file 0x3DAC3 / linear 0x102C3) — RESOLVED 2026-08-21,
    static disassembly (`work/disas_at.py`, no dynamic oracle needed).**
    Traced from the `main`-shaped function at file 0x3D810 (obj1+0x10, right
    after the object's `int3; jmp $` trap + NOP padding): argv is parsed,
    then `call file:0x94AD5` (`status = check(6, 1)`) runs several
    system-requirement probes into one status code (`0`/`1`=ok, `2`/`3`/`4`
    = distinct errors, each printed via a shared "print obj2-offset string"
    helper at file 0xB8C90). Status 3 is our target and fires when
    `call file:0xB6C48(0x703)` fails — `0x703` is an obj2-relative string
    offset resolving to **`\astream\a.wrk`** (verified bytes at file
    0xE8F03: `5c 61 73 74 72 65 61 6d 5c 61 2e 77 72 6b 00`, immediately
    followed by `"rb\0strings.dat\0"`).

    `file:0xB6C48` is a **real MSCDEX probe**, not a config/file check:
    - `call file:0xB6D6C` builds a DPMI real-mode register block with
      `AH=0x15 AL=0x0B` (**INT 2Fh AX=150Bh, "MSCDEX Drive Check"**; a second
      field is set to `3` — almost certainly `DL`=drive **D:**, the API's
      only other input) and afterwards compares a field to `0xADADh` —
      MSCDEX's documented `BX=ADADh` "I am here" signature for this call. No
      answer → immediate failure.
    - `call file:0xB6D20` builds `AH=0x15 AL=0x00` (**AX=1500h, "MSCDEX
      Installation Check"**) and reads back two fields at the struct offsets
      that map to `BX`/`CX` (cross-checked against the `0xADAD`-in-`BX`
      reading above) = CD-ROM drive **count** and **first drive letter**,
      exactly the documented return values. `count==0` → immediate failure.
    - Otherwise it **loops candidate drive letters** over that range, and for
      each tries to access `\ASTREAM\A.WRK` there (`file:0xBB8EF`, flags/mode
      `0xDD8`); first success returns that drive letter (`al = drive_index +
      'a'`); exhausting the range without a hit returns failure → status 3 →
      the printed `ERROR #3` text.
    - Both INT 2Fh calls go through `file:0xBD723` → … → `mov eax,0x31`
      (file 0xBD80D, **INT 31h = DPMI**) with `AX=0300h` staged just before
      it (file 0xBD7E6) — **"Simulate Real Mode Interrupt"**. This is *why*
      the earlier grep for the literal 16-bit immediates `1500h`/`150Bh`
      found nothing (`analysis/qemu-boot.md` §"What the check is not", now
      corrected): AH and AL are written as **two separate byte-stores** into
      the RMCS structure (`mov ah,0x15` / `mov dl,0x0b` / two `mov byte ptr
      [esp+N], reg8`), never as one `mov ax,imm16` — invisible to an
      immediate-value search.
    - A global flag at file-data `0x13548` gates the whole `0xB6C48` call in
      `0x94AD5` — nonzero skips the MSCDEX probe outright. The `main`-shaped
      function's argv loop writes 0/1 to this flag along several paths, none
      triggered by `/trebla` or `/320` (their second characters `'r'`/`'3'`
      don't match the two single-letter switches it recognises, `'g'`/`'p'`).
      **CLOSED 2026-08-21 — dead end, not a shortcut.** Whole-image search
      for every reference to linear `0x13548` (raw byte pattern `48 35 01
      00`, i.e. every direct same-object absolute-address encoding — see
      caveat below): **44 raw hits, 30 inside the MZ stub before object 1
      even starts (false positives / unrelated stub bytes) or landing
      mid-instruction in what disassembles as a data/jump table around file
      0x46347 (discarded — not valid code)**, leaving 16 real sites, all
      within obj1/obj2. Classified every one
      (`work/disas_at.py` + a one-off capstone scan, both quoted in the
      P3.2 log): the **only writes are the 4 already listed above, all
      inside `main`'s argv loop, and every path through that loop nets the
      flag to 0** (init 0 at file 0x3D83B; default/no-`/`-prefix branch sets
      0 at file 0x3D954; the lone branch that sets 1 — positional filename
      argument, i.e. a `.TIE` mission name — resets it to 0 two instructions
      later at file 0x3DA07, unconditionally). The other 12 sites (file
      0x45BEE, 0x45DA0, 0x5085E, 0x5222E5, 0x5F85F, 0x69558, 0x83314,
      0x89D4B, 0x8A1B3, 0x919B9, and two `mov edi,0x13548` address-of sites
      at 0xB8F1E/0xDE80D) are all **reads**. No write anywhere in the image
      is reachable with the flag ending up nonzero. **Caveat**: this search
      only finds references encoded as the literal absolute address (which
      is how every confirmed hit above is encoded, consistent with
      same-object flat addressing needing no fixup); a reference requiring
      fixup relocation to *reach* 0x13548 would not appear in a raw-byte
      search, but no such site turned up cross-checking
      `work/audit_fixups.py --target=1:0x3548`. **Conclusion: this flag
      cannot be set from any command line or reachable code path — it is
      not a usable shortcut.**

    **Conclusion for the CD blocker**: the check needs a *working* MSCDEX
    (`AX=1500h` returning a nonzero drive count) with `\ASTREAM\A.WRK`
    actually reachable on one of the reported drives — i.e. exactly
    `analysis/qemu-boot.md`'s "driver route" (ATAPI driver + `MSCDEX.EXE` +
    `SWTIECD.iso` mounted). With the `0x13548` shortcut closed, **that route
    is the only one left** — there is no static/config-only fix.
