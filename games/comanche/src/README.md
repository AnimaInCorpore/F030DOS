# Falcon 68030 CPU attract port

This source tree is the first recreated Falcon milestone. It is CPU-only:
there is no DSP object or DSP link in the supported build. The active route is
the DOS attract cycle, and every active source file links to the durable route
record in `analysis/functions/falcon-attract.md`.

The route was traced first through the genuine DOS image with QEMU TCG
`exec,nochain`, repeatable inputs, and active-state snapshots. The port covers
the reached opening screens, pass-selected D/C/palette/sky resources,
`DEMO<n>.SCR` replay, DOS flight integration, the 192-column CPU terrain
march, the authored mission object factory, callback/effect handlers, depth
sort, and one DOS tick per rendered frame. Falcon VIDEL/TOS setup and linear
RGB565 storage are explicit platform adaptations.

The route record, not this source directory or the browser, is the authority:

- `analysis/functions/falcon-attract.md` records the reached DOS entries,
  resources, state transitions, frame order, source mapping, and gaps.
- `work/run_qemu_exec_trace.py`, `work/trace_attract_report.py`, and
  `work/inspect_qemu_state.py` reproduce the DOS route evidence.
- `tools/build-run.sh` builds the CPU-only TOS image; `tools/run.sh` starts it
  in Hatari as a Falcon030.

Untraced live controls, menu handoff, sound, mission completion, and DSP work
remain dormant/Unproven. The copied F29 sources under
`reference/f030f29/src/` remain comparison material only.
