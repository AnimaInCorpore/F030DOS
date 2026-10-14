# Falcon VBL presentation ownership

Status: **Target artefact — verified on Hatari, but not a DOS function
record.** This is a platform replacement for Falcon Videl page publication;
it makes no claim about DOS game semantics.

## DOS identity and evidence

- DOS identity: **N/A - platform replacement**. The DOS program owns VGA and
  PC timer/interrupt setup, while the Falcon implementation owns Videl page
  publication and TOS vector chaining.
- No browser implementation exists: this is a target-only hardware boundary.

## Implemented contract

`vbl_install()` reads the MC68030 Vector Base Register (VBR), saves the live
VBL vector at `VBR + $70`, and installs `vbl`. `vbl_remove()` restores that
same saved vector through the saved VBR base. The handler increments the target
frame counter, tail-chains TOS while preserving foreground registers, then
publishes the completed RGB565 page by writing its three Videl base bytes in a
post-chain trampoline. The order is deliberate: TOS 4.04 republishes its own
desktop base inside its VBL handler.

## Evidence and fixture

- Falcon target: `src/vbl.s:vbl_install`, `vbl_remove`, and `vbl`.
- Target visual fixture: `tools/grab-frame.sh` stops at a Hatari VBL and dumps
  the page identified by `$FFFF8201/$FFFF8203/$FFFF820D`.
- Failure observed 2026-09-10 before this record: an address-zero `$70` write
  left Hatari/TOS 4.04's live VBR table unchanged. After the VBR fix, a
  pre-chain Videl write was still overwritten by TOS's own VBL desktop-page
  publication. Both failures made the capture read desktop/executable memory
  after flight had started.
- Required regression: an entered 14-MB flight capture must show the port's
  RGB565 cockpit/scene page, not the TOS desktop page. The `HATARI_KEY_EVENTS`
  fixture is recorded in `analysis/hatari.md`.

## Difference ledger against DOS

| Area | Falcon behaviour | Status |
| --- | --- | --- |
| Interrupt/vector base | Reads MC68030 VBR and modifies `VBR+$70` | Target platform requirement; verified on Hatari. |
| Page publication | Updates Falcon Videl RGB565 base after the chained TOS VBL, still before exception return | N/A - platform replacement. |
| DOS game timing | Does not assert a DOS timer/VBL equivalence | Unproven; separate DOS function records remain required. |
