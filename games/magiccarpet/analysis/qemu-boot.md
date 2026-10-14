# DOS oracle — initial boot check

Status: **RESOLVED** for construction and boot of the Magic Carpet DOS image;
the first protected-mode startup gate is **IDENTIFIED** and requires a DOS
mouse driver.

## MS-DOS 6.22 source media

The required genuine install floppies were found in sibling projects. The
following sets are byte-identical; the first is used in place and is not
copied into this project:

```text
../F030TieFighter/img/Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)/
../F030Underworld/img/Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)/
../F030Underworld2/img/Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)/
```

The harness-required media hashes are:

| file | bytes | SHA-256 |
|---|---:|---|
| `Disk1.img` | 1,474,560 | `B88030401122D234EA6AAFBA3CFED7DE2B7B1782700A67BE5498EDCA6F9FEC5D` |
| `Disk2.img` | 1,474,560 | `E1D48A415495A17D65316D5328A91D7DF0910FB1E42B0B07E7DBF8A4B4DF305A` |

## Reproduction

Build a boot-only image:

```powershell
$env:F030_DOS_FLOPPIES = 'C:\Arbeit\F030TieFighter\img\Microsoft MS-DOS 6.22 Plus Enhanced Tools (3.5)'
python work/build_dos_hdd.py --no-boot
```

The builder produced `img/magiccarpet.hdd`, 268,886,016 bytes, with geometry
521 cylinders / 16 heads / 63 sectors and partition LBA 63. QEMU exited with
`rc=21` from `QUIT.COM` after 4.8 seconds.

The first game-start image was built with:

```powershell
python work/build_dos_hdd.py --run-game --no-boot
$env:QEMU_SYSTEM_I386 = 'C:\Program Files\Qemu\qemu-system-i386.exe'
python work/run_qemu.py --timeout 30 --shot 5
```

That run also reached `QUIT.COM` (`rc=21`) after 11.2 seconds. The scheduled
screenshot returned `<no screendump>`, so this proves the boot/command path but
does not yet prove which title or startup state the game reached. Use a VGA
memory capture or a working QMP screenshot on the next run before drawing
behavioural conclusions.

## First startup observation

To keep `QUIT.COM` from ending QEMU before the screen could be captured, the
exit device was disabled for one bounded run:

```powershell
python work/run_qemu.py --exit-port none --timeout 15 --shot 5 --shot 10
```

The VGA text plane and both screenshots show:

```text
ERROR : MOUSE DRIVER NOT FOUND.
C:\CARPET>
```

This is a runtime-backed startup contract: `CARPET.EXE` returns after the
mouse-driver check, and `QUIT.COM` then runs in the normal image. The game
archive and the installed DOS tree contain no conventional mouse driver.

The sibling Suppdisk does contain Microsoft's 307-byte `FAKEMOUS.COM`. It was
extracted without modifying the source media and staged in `C:\CARPET`, then
called before `CARPET.EXE`. Under QEMU, the batch trace stops at that command:
there is no post-driver marker and DOS returns to a prompt. Repeating with the
`isapc` machine profile gives the same result, so this is currently a
**PARTIALLY RESOLVED** compatibility experiment rather than evidence that the
game accepts the fake driver. The derived test commands were:

```powershell
mcopy -i "...\Suppdisk.img" ::FAKEMOUS.COM work\img_build\FAKEMOUS.COM
mcopy -o -i "img\magiccarpet.hdd@@32256" work\img_build\FAKEMOUS.COM ::/CARPET/FAKEMOUS.COM
python work/run_qemu.py --exit-port none --timeout 10 --shot 6
python work/run_qemu.py --machine isapc --exit-port none --timeout 8 --shot 5
```

`work/run_qemu.py` now exposes optional `--machine` and repeatable `--device`
switches so these DOS-device checks are reproducible without changing the
default `pc` oracle.

## Protected-mode runtime mapping

The transient protected-mode window can be sampled with:

```powershell
$env:QEMU_SYSTEM_I386 = 'C:\Program Files\Qemu\qemu-system-i386.exe'
python tools/re/probe_runtime.py --seconds 6 --interval 0.01
```

The live bytes match the primary executable at a stable
`guest linear = file offset + 0xDBA10` delta. This confirms the DOS/4G image is
actually relocated and executing before the mouse check; it does not yet prove
that all LE pages are resident simultaneously. The mapping and its limits are
recorded in `analysis/executable.md`.

The same error is present in the protected-mode image at file `0xAAD30`, or
object 3 offset `0x19730`. The LE fixup reverse-xref query

```text
python tools/re/audit_le.py game/MagCarp/CARPET/CARPET.EXE --target 3:0x19730
```

finds one source at file `0x58DF2` / logical `0x447F2`. The surrounding bytes
decode as `push 0x19730` followed by `call 0x5CC03`; the raw immediate is
object-relative (`30 97 01 00`) and is therefore expected to be patched by the
LE loader. This links the runtime message to a specific fixup-backed source
site without claiming the surrounding routine's complete semantics.
