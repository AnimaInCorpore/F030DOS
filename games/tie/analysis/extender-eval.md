# DOS4G extender replacements for `Z_TIE__.EXE` — ZRDX & DOS/32A evaluation

✗ **Verdict withdrawn (2026-08-21) — the premise was wrong.** The original
verdict read: *"NOT usable as drop-in replacements … TIE's file is not a
normal DOS4G program (small 16-bit client stub + standard-LE 32-bit module
bridged via DPMI). It is a monolithic dual-half hybrid with absolute linear
cross-references and a private header."* The audit
(`work/audit_headers.py`, `analysis/DOS4G-header.md`) shows the file **is
exactly the thing the verdict said it is not**: a 10.7 KB Watcom 16-bit stub
plus a standard-LE 32-bit module — the normal DOS4G program shape both
extenders are built for. Every "mismatch" below traces to the withdrawn
model or to one field misread; the sharpest one:

- *"object table @ file 0xC4 — which is 16-bit **code** `5f 5e 5a 5b c3`,
  object 1 'size' = 0x5B5A5E5F → allocation fails"* — the LE
  `object_table_off` is **LE-relative**: `0x2A50 + 0xC4 = 0x2B14`, where the
  real table parses cleanly (obj1 vsize 0xAAE83 base 0x10000, obj2 vsize
  0x46470 base 0xC0000). Reading it as an absolute file offset landed in stub
  code, and the "impossible object size" became the proof of a private
  format.

**New status: RESOLVED 2026-08-21 — DOS/32A retested empirically and works**
(P3.3; §Verdict below: it reaches the identical `ERROR #3` CD-check text the
DOS4GW chain reaches). The custom mini-loader plan is deleted per its own
instruction — see the tombstone at the bottom.

## ✗ Withdrawn: "the TIE file's runtime geometry"

The section below is kept as quoted history — every row rests on the
withdrawn hybrid model (`DOS4G-header.md` maps each reading to its LE
reality; the real geometry is obj1 → linear 0x10000, obj2 → 0xC0000, entry
linear 0x8B4E4, relocation via 27,438 ordinary LE fixups):

> | Region | Linear range | Content (withdrawn reading) |
> |---|---|---|
> | MZ header | `0x00–0x3F` | "pure container: entry `e_ip=e_cs=0:00`, `e_rels=0`, never executed" — actually a real stub program, entry file 0x36E, 6 relocations |
> | 16-bit entry table | `0x40–0x5F` | "6× 24-bit entry points" — actually the MZ relocation table |
> | 16-bit half | `0x40–0x46470` | does not exist; the stub ends at 0x2A4E, and `0x46470` is object 2's virtual size (= initial ESP) |
> | extender gap / image @ `0x7E000` | the base was deduced from treating file `0x3F002` as the entry; withdrawn (`DOS4G-header.md` §Withdrawn) |
> | entry `≈0x7E002`, "dwEntry 0x00010002" | cpu_type/os_type read as an entry field; real entry obj1+0x7B4E4 |

What survives of the consequences list: the game really does query the DOS4G
vendor API (`RATIONAL DOS/4G` @ file 0xE9C3D, img+0xAAC3D) — standard DPMI
0A00 vendor-query behaviour, and a *client-API* compatibility question for a
replacement extender, which DOS/32A explicitly emulates (below). The
"absolute linear references into the 16-half, all < 0x46470" observation was
DGROUP-relative data addressing into object 2 — the family's empty-xref
lesson (`cross-project.md` §3) in yet another costume.

## ZRDX (`work/zrdx`, cloned)

Freeware DOS4G-compatible extender (RAW/XMS/SMM, no DPMI host needed) +
`zrxbind` binder + `zrxsetup` base config tool.
- Repo ships **no prebuilt stub** (`stub0_le.asb` missing); building needs
  Borland C 3.1 / MASM. `bin/zrxbind.exe` is a plain 16-bit DOS MZ (works).
- Binder: for MZ files it reads `e_lfanew` (→ 0x2A50 for TIE) and treats the
  app as a **standard LE/LX module**; expects standard object/fixup structures.
- ~~TIE mismatch (all four fail)~~ **✗ all four withdrawn (2026-08-21):**
  1. ~~Header parse fails (object table @ file 0xC4 = code, size 0x5B5A5E5F)~~
     — the offset is LE-relative (→ 0x2B14); the header **is** a standard-LE
     module description and parses cleanly.
  2. ~~Needs linear 0 / 0x7E000~~ — no fixed geometry exists; bases come from
     the object table, applied via fixups, exactly what an LE loader does.
  3. ~~Doesn't patch TIE's thunk tables / entry stubs~~ — neither exists
     (fixup-record tails and object flag words, `DOS4G-header.md`).
  4. Re-*binding* would overwrite `[0x40 … e_lfanew)` — true, but that region
     is the ordinary Watcom stub, and running the file needs no rebind.
- Remaining real obstacle for ZRDX: **no prebuilt stub ships** (build needs
  Borland C 3.1 / MASM), so a ZRDX test is not one command the way DOS/32A's
  is.
- Value: PM-bootstrap template (RAW/XMS/SMM modes, no DPMI dependency).

## DOS/32A (`work/dos32a`, cloned — v9.12 2006, Narech Koumar)

The more serious candidate: full commercial-grade DOS4G replacement
("drop-in replacement for DOS/4GW"), Apache-like license (v8.00 Liberty
Edition), **prebuilt binaries included** (`binw/dos32a.exe` 27.5 KB extender,
`sb.exe` 64 KB binder, `stub32a/c.exe`), config profiles in `d32/` including
`dos4gw.d32` (emulate DOS4GW as closely as possible) and `pmodew.d32`.
Full DPMI server (version 0.9, vendor API), VCPI+XMS+SMM allocation,
compression tooling (`sc.exe`), docs.

### DOS4G support in the source (what it is / isn't)

- **Binder stub detection** (`src/sb/sbind.asm`): identifies existing
  extenders by signature strings in the MZ file: `'DOS/32A'` @+0x9A/0x9C,
  `'STB32A'/'stub32a'` @+0x6A/0x40, **`'DOS/4G'` @+0x25A/0x25C**,
  `'PMODE/W'` @+0x55. TIE's file has **code** at 0x25A (`80 7F FF 5C 74 04 …`),
  not the signature (first `DOS/4G` string is at 0xE9C3D, in the 32-bit string
  pool) → not recognized as a DOS4G file.
- **Binder MZ fallback**: TIE's `MZ[0x18]=0x0040` matches its "reloc tab must
  be at 0040h" check and `MZ[0x3C]=0x2A50 ≠ 0` → `_exec_start=0x2A50`; the
  app is treated as a standard LE module at 0x2A50 — **which is exactly what
  it is** (2026-08-21). (Rebinding would overwrite `[0x40 … 0x2A50)`, the
  Watcom stub — unnecessary for running, only for replacing the stub.)
- **Loader** (`src/dos32a/loader.asm load_header`): standard-LE field map —
  module flags @+0x10, #objects @+0x44, object table @+0x40, fixup page table
  @+0x68, fixup records @+0x6C, entry object/offset @+0x18/+0x1C, data pages
  @+0x80. ✗ *Withdrawn:* "*TIE's header under this map: table @0xC4 (= code)
  → object 1 'Virtual_Size' = 0x5B5A5E5F → error 0x3002. Fails the parse.*"
  — that read +0x40's value as an **absolute file offset**; it is LE-relative
  (0x2A50+0xC4 = 0x2B14) and the parse succeeds, in DOS/32A exactly as in
  `work/audit_headers.py`, which uses the same field map. Under the correct
  read, this loader description is a *match*, not a mismatch.
- **"4G extensions" bit** (kernel ID block, `dos32a.asm`:84; checked in
  `int31h.asm:1221`): DPMI **0A00 vendor-API emulation** — when a 32-bit
  client queries vendor string `RATIONAL DOS/4G`, DOS32A returns its own
  0x8500 API entry (DOS4G-specific DPMI functions). The game does make that
  query (`RATIONAL DOS/4G` @ file 0xE9C3D), and this is precisely the
  compatibility surface it needs.
- **Load model**: `load 16 in lowmem` / `force load 16 low` kernel bits
  (default on) keep the 16-bit part resident at the DOS load address
  (0x1000+), and the 32-bit module is allocated by DOS32A (para/page aligned,
  XMS/VCPI/raw) with fixups applied per the LE tables — the standard model
  this file was linked for. (The "fixed geometry it cannot express" objection
  died with the geometry.)

### Verdict for DOS/32A — RESOLVED 2026-08-21: it works

The original rejection rested on the misread field map and the withdrawn
geometry, so it is void. Every layer re-read under the correct model points
the other way: the binder classifies the file as a standard LE app, the
loader's field map parses it, and the vendor-API emulation covers the one
DOS4G-specific call the game makes. **Confirmed empirically** (P3.3,
`work/set_boot_mode.py dos32a` + `work/run_qemu.py`): `C:\DOS\DOS32A.EXE
Z_TIE__.EXE /trebla /320` on `img/tie.hdd` loads the standard-LE 32-bit image
and reaches **the identical `ERROR #3` CD-check text** the DOS4GW chain
reaches (byte-for-byte, redirected to `C:\DOS32A.LOG`), plus two of its own
diagnostics: `DOS/32A warning (9004): mouse initialization failed` and
`DOS/32A warning (9003): real mode interrupt vector has been modified:
INT 24h`. DOS/32A is a working drop-in replacement for DOS4GW for this file —
no custom loader needed. The `dos32a` boot mode stays in `set_boot_mode.py`
as a second dynamic-oracle path (e.g. for isolating whether a future fix is
DOS4GW-specific vs. game-specific: run it through both extenders).

### What DOS/32A is still good for (this project)

1. **Best available template** for the custom mini-DOS4G-OLX loader: complete
   PM bootstrap (XMS/VCPI/SMM), DPMI server, interrupt translation, mode
   switching — all in plain MASM, Apache-like license (vendor with the
   "This product uses DOS/32 Advanced DOS Extender technology"
   acknowledgment).
2. `binw/dos32a.exe` as an **on-target DPMI host** for incremental
   experiments (e.g. running isolated 32-bit code paths in QEMU/86Box).
3. `d32/dos4gw.d32` profile documents which DOS4GW behaviors it emulates —
   useful cross-check while disassembling the real DOS4GW.

## Custom mini-loader plan — deleted (2026-08-26, per its own instruction)

**(2026-08-21)** the plan carried the note *"if the DOS/32A retest above
succeeds, delete this section"* — the retest succeeded (P3.3, §Verdict), so
the six-step plan is deleted. It was scoped entirely for the withdrawn
hybrid model (place halves at fixed linears 0/0x7E000, patch private
9/11-byte thunk records, entry-stub selection — every element mapped to its
LE reality in `DOS4G-header.md`; full text in git history). If a custom
loader is ever wanted after all, rewrite it as a plain LE loader — object
table + page copy + fixup application, i.e. what `audit_headers.py` /
`audit_fixups.py` already decode — with DOS/32A's source as the template
(§What DOS/32A is still good for).
