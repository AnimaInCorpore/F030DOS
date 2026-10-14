import { sub_0006337B } from './rng.mjs';
// DOS sub_0003AFF3, vaddr 0x3AFF3..0x3B291; record sub_0003AFF3.md.
export function sub_0003AFF3(state, virtualBase) {
  const view = new DataView(state.buffer, state.byteOffset, state.byteLength);
  const scenario = state[0x28eed];
  for (let side = 0; side < 2; side++) {
    let count = 0, sum = 0;
    for (let slot = 0; slot < 200; slot++) {
      const record = 0x11c54 + slot*98 + side*49;
      let value = 0xff;
      if (state[record+0x1f]) {
        count++;
        sum += state[record+0x28];
        const cls = state[0x179b0 + view.getUint16(record+0x15,true)*50 + 0x14];
        if (cls === 7) value = 7;
        else if (cls < 11) {
          const percent = ((sub_0006337B(state,virtualBase).eax & 0xff)*100) >> 8;
          if (percent < state[0x2c13+scenario*2+side]) value = 7;
          else {
            // Evaluate the second call before the scenario/class exclusions,
            // exactly as DOS does; those exclusions must not skip a call.
            const odd = side !== 0 && state[0x2b84] <= 41 &&
              (sub_0006337B(state,virtualBase).eax & 1) !== 0;
            if (odd && scenario !== 6 && scenario !== 38 && cls >= 8) value = 1;
            else if (side !== 0 && scenario === 30 && cls === 3) value = 1;
            else value = cls;
          }
        }
      }
      state[0x10694+slot*2+side] = value;
    }
    const numerator = ((sum & 0xffff) + ((count & 0xffff) >> 1)) & 0xffff;
    view.setUint16(0x1dd92+side*2,count ? Math.trunc(numerator/count) : 0,true);
  }
  return { eax: 1 };
}
