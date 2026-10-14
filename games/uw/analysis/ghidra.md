# UW.EXE — Ghidra workflow (16-bit x86 Real Mode)

How to use Ghidra 12.1.3 + the GhidraDosToolbox extension for this project,
the loader model it creates, verified facts about the resulting image, and the
pitfalls that cost time (all already resolved).

## 1. Tooling

| Piece | Where | Notes |
|---|---|---|
| Ghidra 12.1.3 PUBLIC | `C:\tools\ghidra_12.1.3_PUBLIC` | JDK 21 (MS OpenJDK) bundled; headless via `support\analyzeHeadless` |
| GhidraDosToolbox ext | source `C:\tools\GhidraDosToolbox` (prebuilt zip `dist\`) | adds the **`x86:LE:16:Real Mode Ex`** language, the **experimental MZ loader** ("Old-style DOS Executable (MZ)(Experimental)"), a DOS/BIOS data-type archive, `DosSyscallAnalyzer` (maps `INT 21h` etc. to named DOS functions via `data/x86_msdos6_interrupt_functions`), and scripts |
| Installed ext copy | `C:\Users\sasch\AppData\Roaming\ghidra\ghidra_12.1.3_PUBLIC\Extensions\GhidraDosToolbox` | this is the location Ghidra 12 actually scans (`~/.ghidra/extensions` is *not* scanned by this install) |

### Local modifications (kept in `C:\tools\GhidraDosToolbox\src`)

The stock extension loader crashes on UW.EXE; three patches (recompiled with
plain `javac` against the Ghidra jars, classes dropped into the installed
`lib\GhidraDosToolbox.jar`):

1. **Out-of-range segment filter** (`processMemoryBlocks`): needed for the
   **38 relocation entries that target frame `0x0000`** — real entries, not
   junk. UW.EXE's Borland relocation table has **3,176 entries, all valid
   and in-range** (`uwexe.md` §5); an earlier reading with the wrong record
   stride made ~2,474 of them look like garbage pages past `e_cp`, which is
   what this filter used to be blamed on. Frame `0x0000` produces a bogus
   `0:0` segment and crashes the stock loader
   (`Address Overflow in subtract: 0000:0000 + 575184`). Now segments whose
   start file offset falls outside `[0, endOffset)` are skipped.
2. **Tail block** (`processMemoryBlocks`): the DOS loader only maps the
   `e_cp`-page loader image, file 0x3200..0x66B2F (image size 0x66B30
   exactly, no zero-BSS gap — see `uwexe.md` §2). The remaining 141,088 B
   (file 0x66B30..0x89250) is *not* self-loaded contiguously: it is a
   Borland **`FBOV`** overlay pool — 159 segments, reached through 667
   `INT 3Fh` thunks, swapped into a buffer above the stack at runtime (see
   `uwexe.md` §13.3). The loader still creates **`CODE_TAIL`** (file
   0x66B30..0x89250, rwx, its own address space) so the *whole file* is
   analyzable in one program; it tiles the pool 1:1 with file offset, which
   is what static analysis needs even though it is not the runtime mapping.
   This resolves open question §7.1 of `uwexe.md`, not as originally assumed
   (statically verified: the tail is dense, valid code — 559 functions —
   reached only via the overlay mechanism, not a self-load).
3. **`processRegisters` cast fix**: `block.getStart()` is a `GenericAddress`
   for blocks in non-segmented spaces (e.g. the `HEADER` block in
   `AddressSpace.OTHER_SPACE`); the old `(SegmentedAddress)` cast before the
   space check threw `ClassCastException`.

Rebuild recipe (no gradle needed):
```
CP=$(find /c/tools/ghidra_12.1.3_PUBLIC/Ghidra -path "*/lib/*.jar" |
     while read p; do cygpath -m "$p"; done | tr '\n' ';')
javac -nowarn -cp "$CP" -d out C:/tools/GhidraDosToolbox/src/main/java/ghidradostoolbox/*.java
jar uf .../Extensions/GhidraDosToolbox/lib/GhidraDosToolbox.jar -C out ghidradostoolbox
```
(Also note: the installed ext dir needed a `module.properties` file written
(Ghidra 12 format); the shipped `extension.properties` alone is not enough.)

## 2. Headless import + analysis (the whole pipeline)

```
cd C:/Arbeit/F030Underworld
C:/tools/ghidra_12.1.3_PUBLIC/support/analyzeHeadless \
    work/ghidra UW16 \
    -import work/expanded/UW.EXE
```

- Project: `work/ghidra/UW16` (must `mkdir -p work/ghidra` first).
- Loader/language are chosen by **opinion**, no flags needed: the experimental
  loader (tier 59, beats the core MZ loader) + language **`x86:LE:16:Real Mode`**.
- Auto-analysis includes `DosSyscallAnalyzer` → `int 21`/`int 10`/BIOS calls
  are named (`DosOpenFile`, `VideoSetMode`, …) and a DOS/BIOS structure
  data-type archive is installed.
- One run: import+analysis ≈ 3 min (decompiler switch analysis dominates).

### Flags that *actually* work (12.1.3)

- `-processor` takes the **language ID**, not the display name:
  `x86:LE:16:Real Mode` works; "Intel/AMD 16-bit x86 Real Mode" does **not**.
- `-loader` is **broken** in 12.1.3 (`LoaderService.getLoaderClassByName` sees
  an empty registry; even "Raw Data" fails) — rely on opinion or `-processor`.
- `-process UW.EXE -postScript UWExport.java -scriptPath work/ghidra_scripts`
  runs post-scripts on the imported program.
- PyGhidra is **not** started by `analyzeHeadless` → write post-scripts in
  Java (or a different tool).

## 3. Resulting address model (verified, from `work/ghidra_export/memory_layout.txt`)

| Space / block | Range | Content |
|---|---|---|
| `PSP` `0FEC:0000..00FF` | 256 B | synthesized PSP (not populated), DOS header struct applied to `Headers` |
| `Headers` `0FFC:0000..003F` | 64 B | MZ header bytes |
| `CODE_0..CODE_n` | `1000:0` … `7167:0..22bf` (last), per-segment blocks, some merged up to 8,896 B | the loader image (file 0x3200..0x66B2F). Blocks derive from the relocation table; `CS=seg`, `DS=0FEC` per block. Last block `CODE_830` (0x7167:0..0x22bf) ends at file 0x66B2F — there is no zero-BSS gap before it (see §1 item 2 / `uwexe.md` §2); the block is real content through to the boundary. |
| `CODE_TAIL` | 141,088 B (file 0x66B30..0x89250), rwx, its own address space | the Borland `FBOV` overlay-pool tail (not self-loaded — see §1 item 2 / `uwexe.md` §13.3). **Verified mapping: `CODE_TAIL::X` = file offset `X` exactly** (byte dumps at `::066b62` and `::067b30` match file 0x66b62/0x67b30 with delta 0). First instruction `CODE_TAIL::066b62` = `PUSH BP` (file 0x66b62). |

Consequences:

- **Address ↔ file offset**: for the tail, trivially `CODE_TAIL::X` = file `X`. For the main image: `file = ((seg−0x1000)<<4) + off + 0x3200` (image starts at file 0x3200 = `e_cparhdr`; verified against `CODE_830` 0x7167:0x22bf → file 0x66B2F).
- The `CODE_TAIL` address space also exposes a synthetic `HEADER::0000..31ff` (12,800 B, the MZ header + relocations, read-only) and an `int::` interrupt-vector space (1,024 B) — both visible in `memory_layout.txt`.
- Entry symbol **`entry` @ `1000:0000`** (Ghidra moved the linker entry
  `0x1010:0EC5` back to the discovered function start; 115 instr, 10 in-refs).
- 2,041 functions total (1,482 in the loader image, 559 in `CODE_TAIL`).
  This supersedes the 2,685 capstone-sweep candidates (`work/uw16.txt`).

## 4. Exports

`work/ghidra_scripts/UWExport.java` (post-script) writes to
`work/ghidra_export/`:

| File | Size | Content |
|---|---|---|
| `memory_layout.txt` | 836 lines | all blocks, ranges, perms |
| `functions.txt` | 2,041 | `addr size(instr count) inrefs name` |
| `disasm.txt` | 112,637 lines / 1.9 MB | full 16-bit disassembly, per-block |
| `uw_c.c` | 17.6 MB, 2,037 fns | decompiler C, `// @ addr` headers; `__cdecl16far` calling convention, `undefined2/4` everywhere (16-bit decompiler has no real types yet) |

Ghidra-12 API notes that bit the script (all now correct in the committed
file): `Function.getEntryPoint()` (not `getEntry()`),
`MemoryBlock.isRead/isWrite/isExecute`, `Listing.getInstructions(addr, bool)`,
`DecompInterface.decompileFunction(fn, timeout, monitor)`,
`DecompileResults.getDecompiledFunction().getC()`, refs via
`ReferenceManager.getReferencesTo(addr)` (no `getFunctionReferencesTo`),
`println()` not `printplain()`, `monitor.setMessage()` (no `startTask`), and
Java not Python (PyGhidra off in headless).

## 5. Recommended working style (GUI or headless)

1. **Open the existing program** (`work/ghidra/UW16`) — don't re-import
   (loader/language choice is locked per program).
2. Cross-reference by **string constants**: all `DATA\*` / `CRIT\*` paths live
   in the string pool; Ghidra's `x86 Constant Reference Analyzer` already
   linked most of them. Use them as anchors for data loaders.
3. The `DosSyscallAnalyzer` naming means you can `grep` the disassembly for
   `DosCreateFile`, `DosRead`, `DosSeek`… to find the I/O core without reading
   raw `int 21` sequences.
4. Rename aggressively as semantics are identified (CRT start, data-load
   order, level manager, save/load, overlay tail init); names persist in the
   project, exports stay aligned.
5. 16-bit decompiler output is readable but noisy: expect `__cdecl16far`,
   `in_XX`/`unaff_XX` registers, and "may have set the stack pointer"
   warnings (CF-flag returns and Borland's `bl` calling convention). Treat
   the C as a hypothesis layer; `disasm.txt` + `uw_strings.txt` remain ground
   truth.
6. After any analysis change, re-run `UWExport.java` (≈15 min, dominated by
   decompiling ~2,000 fns) to refresh `work/ghidra_export/`.

## 6. State (2026-08-19)

- [x] extension installed + patched, jar updated in all three locations
- [x] program imported, auto-analyzed (`DosSyscallAnalyzer` active)
- [x] exports generated (`work/ghidra_export/`)
- [x] **semantic pass 1** (2026-08-19/20): 20 renames applied via
      `work/ghidra_scripts/UWRename.java` (APPLIED 20/20): DOS INT 21h
      wrappers (`dos_findfirst`/`_lseek`/`_open`/`_close`/…), CRT chain
      (`crt_psp_init`→`crt_heapinit`[MZ entry]→`crt_startup`), input cluster
      (`input_vbi_poll`/`input_kb_direct`/`input_mouse33`), 3 error hubs
      (`rt_errhub_1..3`), and the self-load candidate `file_create_read`
      (FCREATE+INT 0x1A). Details + rationale: `analysis/functions.md`.
- [x] **semantic pass 1 correction** (2026-08-21): a byte-level audit found 13
      of those 20 renames landed on the wrong function (seg:off reverse-computed
      with a stale `0x2000` header constant instead of the verified `0x3200`,
      consistently missing the function that actually contains the cited
      evidence). Fixed via `work/ghidra_scripts/UWRenameFix.java`
      (`APPLIED 24/24`) — retargeted the DOS-wrapper family and, once the same
      bug turned up there too during a spot-check, the input cluster; gave the
      wrongly-squatted functions an honest name (`dos_deletefile`) or their
      default name back; withdrew 3 rows with no safe single target
      (`dos_close_after_msg`, `dos_close_drive`, `input_mouse33`). **19**
      semantic names now live (was 20). `work/renames.csv` and
      `analysis/functions.md` updated to match; full detail and byte evidence
      in `analysis/functions.md`.
- [x] **file↔Ghidra address mapping verified** (2026-08-19): 831 CODE blocks tile
      file 0x3200..0x66B30 (sum exactly 0x66B30); `seg = 0x1000 + (blockFileStart>>4)`,
      `off = F - blockFileStart`; CODE_TAIL raw value == file offset. Full table of
      verified examples in `analysis/uwexe.md` §8. Helper: `UWFileToFn.java`.
- [x] **file I/O layer mapped** (`UWFnsInRange.java` + raw `mov ah,NNh;int 21h`
      scan): low-level primitives (open 20b9:011a / read 20b9:0221 / fcreate
      20a1:0138 / close 20a1:0151 / lseek 206b:02e9) and the **archive resource
      subsystem** @ file 0x3c000..0x3e600 (blocks 48a7..4a74, 46 fns,
      setdrive+lseek+read-by-offset) that fetches LEV/CNV/STRINGS records.
      Details: `analysis/uwexe.md` §9.
- [x] **string-pool reference mechanism** (`UWPoolRefs.java`): 111,801 main-space
      instructions scanned → 0 direct refs into pool 0x5f000..0x61700; no u32
      far-pointer table. Strings resolved at runtime (STRINGS.PAK ids or separate
      seg/off immediates). `analysis/uwexe.md` §10.
- [ ] semantic pass 2: locate program `main`/game loop (big inrefs=0 tail fns
      0x9192e/0x83447/0x804d9; `int 0x67` cluster 0x3d5e7..0x3daae), the
      **top-level** LEV/CNV/STRINGS readers (callers *into* the 0x3c000..0x3e600
      subsystem — `UWCallers.java` shows no direct xrefs, so a far-call-graph or
      boot trace is needed), and the save (SAVE0\lev.ark) machinery
- [x] re-export (`UWExport.java`) after the pass-1-correction semantic change
      (2026-08-21) to refresh `functions.txt`/`uw_c.c`/`disasm.txt` — all three
      now reflect the 19 corrected names.

**Ghidra script toolkit**: `work/ghidra_scripts/UWExport.java` (full
re-export), `UWRename.java` (batch renames — canonical table, for a fresh
import), `UWRenameFix.java` (one-time corrective pass for a project that
already has the old buggy table applied — see "semantic pass 1 correction"
above), `UWPoolRefs.java` (reference scans). `work/ghidra_scripts_old/`
holds earlier-iteration scripts not yet promoted/reconciled with this doc:
`UWStrRefs.java`, `UWFileToFn.java` (file-offset → Ghidra addr + containing
fn), `UWFnsInRange.java` (list fns by file range + size), `UWCallers.java`
(incoming xrefs of an address) — despite being listed here as if they were
in `ghidra_scripts/`, only `UWRename.java`'s path was actually reconciled in
this pass; treat the others' location as unverified until checked. Run:
`analyzeHeadless … -postScript <name>.java -scriptPath <dir the script is
actually in>`.
