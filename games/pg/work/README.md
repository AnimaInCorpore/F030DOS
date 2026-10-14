# Regenerating derived work

`dosimg.py`, `run_qemu.py`, `mbr.asm` and `gdbstub_probe.py` are synchronized
from `../F030Method/dos/`. The per-game `build_dos_hdd.py` is the local half,
configured for the recovered unpatched tree. It stages a pinned CuteMouse
driver before the original launcher to satisfy the startup timer dependency.
See `../analysis/executable.md` for the driver identity, successful menu route
and the `--without-mouse` diagnostic control.

`probe_timer_runtime.py` locates the checked wait routine in stopped RAM,
validates its relocated operand and increment callback, and prints the live
timer slots. Run `python3 work/test_timer_probe.py` from the repository root
for the placement rejection checks. Those checks validate the probe, not a
game implementation.

`drive_menu.py` sends PS/2 input to the unchanged DOS guest and retains stopped
screen/RAM/register checkpoints. The measured standalone Poland schedule is
`routes/poland.json`; see [the route record](../analysis/scenario-route.md) for
scope, resource identities and the remaining loader contracts. From the root:

```text
python3 work/drive_menu.py --hdd work/qemu_out/pg-mouse.hdd \
  --out work/qemu_out/poland-verified --script work/routes/poland.json \
  --seconds 50 --trace --open-files
python3 work/test_menu_route.py
```

Choose a fresh output directory. `--open-files` arms a checked DOS wrapper
after the main-menu capture and records requests, not successful handles or
reads. `CAPTURED` reports harness completion; visually verify the retained
tactical checkpoint. The broad DOS-call log reaches its polling limit and is
marked truncated. This host harness does not establish JavaScript/m68k parity.

Add `--file-io` to capture matched open returns, reads, seeks and closes at
checked DOS boundaries. Run `python3 work/check_file_io.py OUTPUT_DIRECTORY`
to compare returned bytes and measured file positions with the five pristine
Poland resources. See [the loader record](../analysis/scenario-loader.md).
