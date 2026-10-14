// The DOS object-2 arena remains byte-addressed and little-endian.

// DOS: sub_00010976, vaddr 0x10976..0x10A18, file 0x58C1A..0x58CBC.
// Record: analysis/functions/sub_00010976.md; expected values: DOS fixtures.
export function sub_00010976(state, output, widthOffset, heightOffset) {
  const view = new DataView(state.buffer, state.byteOffset, state.byteLength);
  const record = 0x21d6 + state[0xccb1] * 24;
  const width = (Math.imul(view.getUint16(0xcc88, true), state[record + 2] + 1)
    + state[record]) >>> 0;
  const height = (Math.imul(view.getUint16(0xcc86, true), state[record + 11] + 1)
    + state[record + 7] + 1) >>> 0;
  const result = new DataView(output.buffer, output.byteOffset, output.byteLength);
  result.setUint16(widthOffset, width & 0xffff, true);
  result.setUint16(heightOffset, height & 0xffff, true);
  return { eax: height };
}

// DOS: sub_00048105, vaddr 0x48105..0x48174, file 0x903A9..0x90418.
// Record: analysis/functions/sub_00048105.md; expected values: DOS fixtures.
export function sub_00048105(state, bounds, stackIndex) {
  const offset = (stackIndex & 0xff) * 20;
  const view = new DataView(state.buffer, state.byteOffset, state.byteLength);
  view.setUint32(0xc620 + offset, bounds.eax & 0xffff, true);
  view.setUint32(0xc624 + offset, bounds.edx & 0xffff, true);
  view.setUint32(0xc628 + offset, bounds.ebx & 0xffff, true);
  view.setUint32(0xc62c + offset, bounds.ecx & 0xffff, true);
  return { eax: offset, edx: bounds.ecx & 0xffff };
}
