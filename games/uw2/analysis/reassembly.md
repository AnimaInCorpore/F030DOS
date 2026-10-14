# `UW2.EXE` reassembly ratchet

**Status: RESOLVED (2026-08-24; whole-file classification updated 2026-08-26).**
The complete shipped `UW2.EXE` is reassembled byte-for-byte from generated NASM
source, and an automated audit classifies every byte as decoded code or an
explicit data/padding range. The check covers the MZ header, relocation table,
DOS-loaded image, FBOV header, and overlay pool.

```text
original  sha256 b07d9fde7bfb8a44e0c75388ad1bbbcd99207841f056f711a78ea51af90ea120
rebuilt   sha256 b07d9fde7bfb8a44e0c75388ad1bbbcd99207841f056f711a78ea51af90ea120
```

Run it with:

```bash
python3 work/reasm/uw2reasm.py --passes 8
```

The small UW2 wrapper reuses the proven encoder and per-instruction listing
verifier from `../F030Underworld/work/reasm/uwreasm.py`. It supplies the
binary-specific inputs: the UW2 executable, Ghidra's `0xD200` skew, NASM path,
the UW2 data guard, FBOV unit/fixup bounds, and the mechanically resolved
overlay switch targets. After the rebuild it reruns the same descent and writes
the whole-file classification result to `work/reasm/out/report.json`. No
opaque whole-file byte blob is included; data is emitted as explicit ranges.

## Measured result

The descent used the verified entry point plus 2,239 Ghidra function starts,
535 explicit code-island starts, 94 VM2 handler starts, and 489 FBOV switch
table targets. It found 157,847 decoded instructions in 3,445 function entries
after the proven data guards. The UW2-specific renderer and guard pass
converges in one NASM pass:

| measure | result |
|---|---:|
| file size | 675,968 B |
| real mnemonic instructions | 157,847 / 157,847 (100.00%) |
| forced `db` fallbacks | 0 |
| bytes emitted as real instructions | 414,013 / 675,968 (61.2%) |
| bad decode starts | 5 |
| out-of-range branch targets | 159 |
| unrelocated far-transfer sites | 4,206 |

The fallback file is now empty apart from its header. The eight formerly
non-canonical reachable encodings are named UW2-local macros: fixed-count
shift/rotate forms, Borland's 32-bit direction-bit register forms, redundant
prefix order, and one group-2 shift encoding. The listing verifier still
compares every emitted line at its intended file offset. The generated source,
listing, rebuilt binary, fallback list (`fallbacks.txt`) and machine-readable
result are written to `work/reasm/out/` by the command above — the directory
is not committed, so regenerate it before citing those artifacts (a clean
checkout does not contain them).

The 61.2% figure is reachable-instruction coverage, deliberately not a claim
that the rest is code. The whole-file audit now reports:

| classification | bytes |
|---|---:|
| unique decoded instruction bytes | 413,484 |
| explicit data/padding bytes | 262,484 |
| unclassified bytes | 0 |
| overlapping code/guard bytes | 0 |

The guard records the embedded lookup tables at `0x3E460..0x3EC30` and
`0x3F750..0x3FF40`, indexed graphics data at `0x44C3..0x49ED`, the
graphics-record pool at `0x5519C..0x5B660`, keyboard/UI/wave tables at
`0x639D0..0x64620`, the 15×256 palette LUT at `0x10100..0x11000`, all 77
FBOV overlay-unit fixup tails and paragraph gaps, and the resolved indirect
switch tables. There is no remaining byte-level code/data classification
worklist. “Fully decoded” here means mechanically complete and byte-verified;
semantic naming, call contracts, and the remaining asset/VM investigations are
still separate porting work.
