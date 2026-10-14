# `mov r, cs:[disp32]` under QEMU — minimal test

A 512-byte boot sector that isolates the addressing question behind
Links 386's `Phar Lap fatal err 10049`. No DOS, no extender, no paging: it
enters 32-bit protected mode, sets up its own GDT, executes one instruction
and reports what address that instruction dereferenced.

## Result (QEMU 11.1.1, TCG, macOS/aarch64 host)

| variant | instruction | segment state | effective address | verdict |
|---|---|---|---|---|
| `seg_base` | `mov ds, cs:[0x3F8]` | DS/ES/SS base 0 | `0x3F8` | **base dropped** |
| `seg_ctrl` | `mov ds, cs:[0x3F8]` | DS/ES/SS base `0x2000` | `CS.base + 0x3F8` | correct |
| `seg_plain` | `mov ebx, cs:[0x3F8]` | DS/ES/SS base 0 | `0x3F8` | **base dropped** |
| `seg_fs` | `mov ebx, fs:[0x3F8]` | FS base `0x2000`, DS/ES/SS base 0 | `FS.base + 0x3F8` | correct |
| `seg_fscs` | `mov ebx, fs:[0x3F8]` | FS base `0x1000`, DS/ES/SS base 0 | `FS.base + 0x3F8` | correct |

Identical on `-cpu 486` and `-cpu pentium`.

`seg_plain` and `seg_fscs` are the controlled pair: same displacement, same
segment **base** value (`0x1000`), same instruction shape, same flat state —
only the override register differs, and only the `CS` one loses its base. So
this is not "overrides are dropped in flat mode"; it is **the `CS` override
specifically, on a data reference, when `DS`/`ES`/`SS` bases are all zero.**
`seg_ctrl` shows the same `CS` override working as soon as the default bases
are non-zero.

On a 386 the override applies unconditionally in every one of these cases, so
every "base dropped" row is an emulator divergence.

## Why it matters

Links 386's extender executes `2E 8E 1D F8 03 00 00` (`mov ds, cs:[0x3F8]`) at
`0xC2C136` in exactly the flat state above. Under this defect it loads the
word at linear `0x3F8` — IVT vector `0xFE`, `F000:FF53` — instead of its own
`0x0010`, and `0xFF53` is not a valid selector, so it takes `#GP` and the
handler re-executes the same load until the interrupt-stack pool empties.
See `analysis/executable.md`.

## Two further variants

`seg_twice` runs the same load at the same address twice — non-zero default
bases for one pass, zero for the other — and `seg_twicerev` reverses the
order. The answers follow the current segment state and reverse with the
order, so the behaviour is decided per execution rather than cached per code
address: no warm-up or ordering trick avoids it.

`UPSTREAM.md` is a ready-to-send bug report built from these results. It has
not been submitted.

## Build and run

```text
nasm -f bin        segtest.asm -o seg_base.img
nasm -f bin -DCTRL segtest.asm -o seg_ctrl.img
nasm -f bin -DPLAIN  segtest.asm -o seg_plain.img
nasm -f bin -DFSTEST segtest.asm -o seg_fs.img
nasm -f bin -DFSCS   segtest.asm -o seg_fscs.img
nasm -f bin -DTWICE    segtest.asm -o seg_twice.img
nasm -f bin -DTWICEREV segtest.asm -o seg_twicerev.img
./run_segtest.sh
```

The verdict is the `isa-debug-exit` code, `(AL << 1) | 1`; the same answer is
written to the text screen as `DS=xx` so a run is readable without the exit
device.
