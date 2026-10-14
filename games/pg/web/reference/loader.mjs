import { sub_00010976, sub_00048105 } from './geometry.mjs';
import { sub_00060907, sub_00060926 } from './strings.mjs';

// DOS sub_00037E75, vaddr 0x37E75..0x382DC, file 0x80119..0x80580.
// Record: analysis/functions/sub_00037E75.md. DOS fixture: dos-loader.json.
// The byte arena starts at virtualBase; stored pointers retain DOS addresses.
// io is the explicit N/A logical binary-resource adapter, not decoded state.
// Selected contract: successful opens and complete binary reads (Poland).
export function sub_00037E75(state, virtualBase, io) {
  const view = new DataView(state.buffer, state.byteOffset, state.byteLength);
  const u16 = offset => view.getUint16(offset, true);
  const u32 = offset => view.getUint32(offset, true);
  const set16 = (offset, value) => view.setUint16(offset, value & 0xffff, true);
  const set32 = (offset, value) => view.setUint32(offset, value >>> 0, true);
  const path = () => {
    let end = 0x1dd72;
    while (state[end] !== 0) end++;
    return String.fromCharCode(...state.subarray(0x1dd72, end));
  };
  const makePath = (nameOffset = 0xcc28) => {
    sub_00060907(state, 0x1dd72, state, 0x1d34c);
    sub_00060926(state, 0x1dd72, state, nameOffset);
    return path();
  };
  const read = (stream, size, count, call) => io.read(stream, size, count, call);
  const set = io.open(makePath());
  read(set, 1, 1, 0x37ef5);
  const fields = [0x37f0d, 0x37f22, 0x37f37, 0x37f4f, 0x37f64]
    .map(call => read(set, 20, 1, call));
  const maximum = data => new DataView(data.buffer, data.byteOffset, 2).getUint16(0, true);
  set16(0xcc90, maximum(read(set, 2, 1, 0x37f79)));
  set16(0xcc8e, maximum(read(set, 2, 1, 0x37f8e)));
  sub_00060907(state, 0xcc28, fields[2]);
  for (let index = 0; index < state[0x21be]; index++) read(set, 2, 1, 0x37fe4);
  state[0xccb1] = state[0xccb2];
  set16(0xcc88, u16(0xcc90) - 1);
  set16(0xcc86, u16(0xcc8e));
  const extent = new Uint8Array(4);
  sub_00010976(state, extent, 0, 2);
  const dimensions = new DataView(extent.buffer);
  const width = Math.min(dimensions.getUint16(0, true), 640);
  const height = Math.min(dimensions.getUint16(2, true), 426);
  const left = (554 - width) >> 1;
  const top = (426 - height) >> 1;
  sub_00048105(state, { eax: left, edx: top,
    ebx: (width + left - 1) >>> 0, ecx: (height + top - 1) >>> 0 }, state[0x28ee8]);
  state[0xccb1] = state[0xccb3];
  const cells = Math.imul(u16(0xcc90) + 1, u16(0xcc8e) + 1) >>> 0;
  for (let index = 0; index < state[0x21be]; index++) {
    const layer = state[0xba94 + state[0x21b9] * 15 + index];
    if (state[0x21c0 + layer] !== 0) continue;
    const size = state[0xcca1 + layer];
    if (size !== 1 && size !== 2) continue;
    const pointer = u32(0xcba0 + layer * 4);
    set32(size === 1 ? 0xcb88 : 0xcb8c, pointer);
    state.set(read(set, size, cells, size === 1 ? 0x38157 : 0x38194), pointer - virtualBase);
  }
  sub_00060907(state, 0xcc28, fields[2]);
  const stm = io.open(makePath(0xcc2a));
  state.set(read(stm, 2, cells, 0x38224), u32(0xcb84) - virtualBase);
  io.close(stm);
  const map = u32(0x17934) - virtualBase;
  state.set(read(set, 2, cells, 0x38256), map);
  io.close(set);
  // DOS column-major traversal of a row-major array; no invented row flip.
  for (let x = 0; (x & 0xffff) <= u16(0xcc90); x = (x + 1) >>> 0) {
    for (let y = 0; (y & 0xffff) <= u16(0xcc8e); y = (y + 1) >>> 0) {
      const index = Math.imul(y & 0xffff, (u16(0xcc90) + 1) & 0xffff) + (x & 0xffff);
      state[map + index * 2 + 1] &= 0x7f;
    }
  }
  return { eax: u16(0xcc90) + 1 };
}
