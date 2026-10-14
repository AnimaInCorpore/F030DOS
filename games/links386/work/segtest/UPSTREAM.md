# QEMU i386 TCG: `CS` segment override dropped on data references when DS/ES/SS bases are all zero

*Prepared from the F030Links386 investigation. Not yet submitted.*

## Summary

On the i386 TCG target, an explicit `CS` segment override on a **data**
reference is ignored — the effective address is computed as `disp32` instead
of `CS.base + disp32` — whenever the `DS`, `ES` and `SS` bases are all zero.
The same override works correctly as soon as any default base is non-zero, and
an `FS` override with an identical base value is always applied correctly.

Real 386-and-later hardware applies the override unconditionally.

## Reproducer

`segtest.asm` in this directory is a 512-byte boot sector: no OS, no paging, its
own GDT, one instruction, verdict via `isa-debug-exit`. Each candidate address
holds a *valid* selector so the test reports an address rather than faulting.

```
nasm -f bin          segtest.asm -o seg_base.img
nasm -f bin -DCTRL   segtest.asm -o seg_ctrl.img
nasm -f bin -DPLAIN  segtest.asm -o seg_plain.img
nasm -f bin -DFSTEST segtest.asm -o seg_fs.img
nasm -f bin -DFSCS   segtest.asm -o seg_fscs.img
nasm -f bin -DTWICE  segtest.asm -o seg_twice.img
./run_segtest.sh
```

`CS.base` is `0x1000`, so the correct answer is always the word at
`CS.base + 0x3F8 = 0x13F8`.

| variant | instruction | DS/ES/SS bases | expected | actual |
|---|---|---|---|---|
| `seg_base` | `mov ds, cs:[0x3F8]` | 0 | `0x13F8` | **`0x3F8`** |
| `seg_ctrl` | `mov ds, cs:[0x3F8]` | `0x2000` | `0x13F8` | `0x13F8` |
| `seg_plain` | `mov ebx, cs:[0x3F8]` | 0 | `0x13F8` | **`0x3F8`** |
| `seg_fs` | `mov ebx, fs:[0x3F8]`, FS base `0x2000` | 0 | `0x23F8` | `0x23F8` |
| `seg_fscs` | `mov ebx, fs:[0x3F8]`, FS base `0x1000` | 0 | `0x13F8` | `0x13F8` |

`seg_plain` and `seg_fscs` are the controlled pair: identical displacement,
identical segment **base value**, identical instruction shape, identical
segment state — only the override register differs, and only `CS` loses its
base. So this is neither specific to `mov Sreg, m` nor a general "overrides
ignored in flat mode" behaviour.

`seg_twice` executes the same load at the same address twice, with non-zero
bases for one pass and zero bases for the other; the answers differ per pass
and reverse with the order (`-DTWICEREV`), so the behaviour tracks the current
segment state deterministically rather than being cached per code address.

## Environment

- QEMU 11.1.1, TCG (the only accelerator available), macOS/aarch64 host.
- Identical on `-cpu 486` and `-cpu pentium`.
- The same divergence was previously observed under a Windows QEMU build on
  x86_64 (identical `v=0d e=ff50 IP=0008:00002136` fault chain in a guest), so
  it appears to be neither host- nor 11.1.1-specific. Which versions are
  affected has not been bisected.

## Impact

Found because it breaks a real 1995 DOS program. Phar Lap 386|DOS-Extender
keeps its ring-0 data selector in a `CS`-relative slot and reloads it with
`mov ds, cs:[0x3F8]` on every ring-0 service entry, at which point `DS`, `ES`
and `SS` bases are all zero. Under this bug it loads the word at linear
`0x3F8` — real-mode IVT vector `0xFE`, `F000:FF53` — takes `#GP(0xFF50)`, and
the fault handler re-executes the same load until the extender's interrupt
stack pool is exhausted, reporting `Phar Lap fatal err 10049: Ran out of stack
buffers`. The failure is completely stable and looks exactly like a guest bug.

Any 32-bit flat DOS target (DOS/4G, DOS/4GW, `LE`, Phar Lap `P3`) runs in the
triggering state for its whole life, so this is likely to affect more guests
than the one that found it.
