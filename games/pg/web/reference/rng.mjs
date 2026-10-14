// DOS IDs / contracts: analysis/functions/sub_00063375.md, sub_0006337B.md,
// sub_0006339F.md. Byte-addressed little-endian object-2 state.
export function sub_00063375(state, virtualBase) {
  return { eax: (virtualBase + 0x74f0) >>> 0 };
}
export function sub_0006337B(state, virtualBase) {
  const pointer = sub_00063375(state, virtualBase).eax;
  const view = new DataView(state.buffer, state.byteOffset, state.byteLength);
  const offset = pointer - virtualBase;
  const next = (Math.imul(view.getUint32(offset, true), 0x41c64e6d) + 0x3039) >>> 0;
  view.setUint32(offset, next, true);
  return { eax: (next >>> 16) & 0x7fff };
}
export function sub_0006339F(state, virtualBase, eax) {
  const pointer = sub_00063375(state, virtualBase).eax;
  new DataView(state.buffer, state.byteOffset, state.byteLength)
    .setUint32(pointer - virtualBase, eax >>> 0, true);
  return { eax: pointer };
}
