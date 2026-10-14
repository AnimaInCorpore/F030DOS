; Target-neutral UW2 presentation constants.
;
; The recovered DOS cutscene and graphics paths expose a 320x200 row-major
; indexed surface.  Palette entries remain the source PALS.DAT 6-bit DAC
; triples until a target presentation seam consumes them.

UW2_FRAME_WIDTH       = 320
UW2_FRAME_HEIGHT      = 200
UW2_FRAME_STRIDE      = UW2_FRAME_WIDTH
UW2_FRAME_BYTES       = UW2_FRAME_WIDTH*UW2_FRAME_HEIGHT
UW2_PALETTE_ENTRIES   = 256
UW2_PALETTE6_BYTES    = UW2_PALETTE_ENTRIES*3
